# -*- coding: utf-8 -*-
"""QQ阅读参考核心及 AstrBot 下载适配。

依赖: aiohttp, pycryptodome, bcrypt
账号配置: MySQL qq_reader_auth/login_state 多账号；CONFIG 只保留固定客户端字段。
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextvars
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import gzip
import hashlib
import html
import io
import json
import os
import re
import secrets
import struct
import tarfile
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
import zlib
import zipfile
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    BinaryIO,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Union,
)
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit

import aiohttp
from astrbot.api import logger

try:
    import bcrypt as _bcrypt
except Exception:
    _bcrypt = None

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    写入运行状态值,
    已配置运行状态数据库,
    读取运行状态值,
)

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception:
    百度网盘 = None

from Crypto.Cipher import AES, DES
from Crypto.Hash import MD2, MD4
from Crypto.Util import Counter

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

# === decrypt ===
"""Pure-Python QQRead chapter decrypt (libfock algorithm recovery).

Wire format:
  enc = header_cipher(256) || body_cipher
  body = header_plain[128:256] || enc[256:]

Key schedule:
  knva = AES-128-CBC(key=c9ajudte0zb21ksg, iv=58jb6v2lzcspwymg).decrypt(embedded_ct)
  master = SHA256(fuid || knva)
  header / keypool = AES-256-CBC(master, iv=master[:16])
  content_key = SHA256(pool_entry_16_bytes || fuid || additional_key)

Mode id = int(header mode string first 8 decimal digits). Content chains:

  21123123 AES-CBC -> AES-CBC
  21132184 DES-CBC -> AES-CBC
  29344484 AES-CTR -> DES-CBC
  29859828 AES-CBC -> AES-CTR
  31344423 DES-CBC -> AES-CTR
  31932881 AES-CBC -> DES-CBC
  34232881 AES-CTR -> AES-CTR
  34941028 DES-CBC -> DES-CBC
  94859123 AES-CTR -> AES-CBC

AES-CTR: nonce=content_key[:12], BE32 counter starts at 2 (GCM data style).

"""


# knva is NOT plaintext in libfock.so; real_dec builds:
#   master_material = fuid || AES128-CBC_decrypt(KNVA_CT)
# Embedded pool at runtime get_master (0x1200ca48):
KNVA_AES_KEY = b"c9ajudte0zb21ksg"
KNVA_AES_IV = b"58jb6v2lzcspwymg"
# 32B ciphertext @ SO/runtime file offset 0x15cf0
KNVA_CIPHERTEXT = bytes.fromhex(
    "8f400c5fcec88186569c7c407e35d2895495f9025321cd94976e786a65f18550"
)


# mode id (first 8 digits) -> name
MODE_AES_AES = 21123123
MODE_DES_AES = 21132184
MODE_CTR_DES = 29344484
MODE_AES_CTR = 29859828
MODE_DES_CTR = 31344423
MODE_AES_DES = 31932881
MODE_CTR_CTR = 34232881
MODE_DES_DES = 34941028
MODE_CTR_AES = 94859123


def derive_knva(
    ciphertext: bytes = KNVA_CIPHERTEXT,
    key: bytes = KNVA_AES_KEY,
    iv: bytes = KNVA_AES_IV,
) -> bytes:
    """Recover knva from libfock embedded AES-128-CBC blob.

    Matches get_master @ runtime 0x1200ca48:
      key = "c9ajudte0zb21ksg", iv = "58jb6v2lzcspwymg", AES-128-CBC.
    """
    if len(ciphertext) % 16:
        raise ValueError("knva ciphertext length must be multiple of 16")
    pt = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(ciphertext)
    return pt[:16]


def _strip_padding(data: bytes, block_size: int) -> bytes:
    """按 Go 版 stripPadding 规则移除一个有效的块填充。"""
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= block_size and data.endswith(bytes([pad]) * pad):
        return data[:-pad]
    return data


def _pkcs7_unpad(data: bytes) -> bytes:
    return _strip_padding(data, 16)


def master_key(fuid: str | bytes, knva: bytes | None = None) -> bytes:
    if knva is None:
        knva = derive_knva()
    if isinstance(fuid, str):
        fuid_b = fuid.encode("utf-8")
    else:
        fuid_b = fuid
    if isinstance(knva, str):
        knva = knva.encode("ascii")
    return hashlib.sha256(fuid_b + knva).digest()


def decrypt_keypool(keypool: bytes, aes_key: bytes) -> bytes:
    """解密 Go 版 DecryptChapter 使用的二进制密钥池。"""
    if len(keypool) % 16:
        raise ValueError("keypool length must be multiple of 16")
    return _pkcs7_unpad(
        AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16]).decrypt(keypool)
    )


def decrypt_header(enc: bytes, aes_key: bytes) -> bytes:
    if len(enc) < 256:
        raise ValueError("chapter too short")
    return AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16]).decrypt(enc[:256])


def content_key(
    pool_decrypted: bytes,
    param: int,
    fuid: str | bytes,
    additional_key: str | bytes,
) -> bytes:
    """按 Go 版规则从 param 对应的 17 字节密钥槽派生正文密钥。"""
    offset = int(param) * 17
    if offset < 0 or offset + 16 > len(pool_decrypted):
        raise ValueError(
            f"pool entry index {param} out of range "
            f"(need offset {offset}+16, pool has {len(pool_decrypted)} bytes)"
        )
    pool_entry = pool_decrypted[offset : offset + 16]
    if isinstance(fuid, str):
        fuid = fuid.encode("utf-8")
    if isinstance(additional_key, str):
        additional_key = additional_key.encode("utf-8")
    return hashlib.sha256(pool_entry + fuid + additional_key).digest()


def _gunzip_loose(data: bytes) -> bytes:
    """匹配 Go maybeGunzip：允许 gzip 头前存在少量前缀。"""
    if len(data) < 2:
        return data
    start = data.find(b"\x1f\x8b")
    if start < 0:
        return data
    try:
        return gzip.decompress(data[start:])
    except (OSError, EOFError, zlib.error):
        return data


def _body(enc: bytes, header_plain: bytes) -> bytes:
    inline_body = header_plain[128:256]
    if not any(inline_body):
        return enc[256:]
    return inline_body + enc[256:]


def _aes_cbc(data: bytes, key32: bytes) -> bytes:
    if len(data) % 16:
        data += b"\x00" * (16 - len(data) % 16)
    return _strip_padding(
        AES.new(key32, AES.MODE_CBC, iv=key32[:16]).decrypt(data),
        16,
    )


def _des_cbc(data: bytes, key32: bytes) -> bytes:
    if len(data) % 8:
        data += b"\x00" * (8 - len(data) % 8)
    return _strip_padding(
        DES.new(key32[:8], DES.MODE_CBC, iv=key32[:8]).decrypt(data),
        8,
    )


def _aes_ctr(data: bytes, key32: bytes, initial_value: int = 2) -> bytes:
    ctr = Counter.new(
        32,
        prefix=key32[:12],
        initial_value=initial_value,
        little_endian=False,
    )
    return AES.new(key32, AES.MODE_CTR, counter=ctr).decrypt(data)


def mode_string_from_header(header: bytes) -> str:
    mode = header[:16].split(b"\x00", 1)[0]
    digits = bytes(b for b in mode if 48 <= b <= 57)
    if not digits:
        raise ValueError(f"no mode digits in {mode!r}")
    return digits.decode("ascii")


def mode_id_from_header(header: bytes) -> int:
    """读取 Go 版包头前 8 位 mode 整数。"""
    return int(mode_string_from_header(header)[:8])


def _parse_header_field(raw: bytes) -> int:
    """解析以 NUL 结尾的 ASCII 十进制字段。"""
    field = raw.split(b"\x00", 1)[0].strip()
    if not field or any(byte < 48 or byte > 57 for byte in field):
        raise ValueError(f"invalid integer header field: {field!r}")
    return int(field)


def _is_all_zeros(data: bytes) -> bool:
    return not any(data)


def decrypt_mode_aes_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_cbc(_aes_cbc(body, key32), key32)
    return mid


def decrypt_mode_des_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_cbc(_des_cbc(body, key32), key32)
    return mid


def decrypt_mode_ctr_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _des_cbc(_aes_ctr(body, key32), key32)
    return mid


def decrypt_mode_aes_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_aes_cbc(body, key32), key32)
    return mid


def decrypt_mode_des_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_des_cbc(body, key32), key32)
    return mid


def decrypt_mode_aes_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _des_cbc(_aes_cbc(body, key32), key32)
    return mid


def decrypt_mode_ctr_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_aes_ctr(body, key32), key32)
    return mid


def decrypt_mode_des_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _des_cbc(_des_cbc(body, key32), key32)
    return mid


def decrypt_mode_ctr_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_cbc(_aes_ctr(body, key32), key32)
    return mid


_MODE_HANDLERS: dict[int, Callable[[bytes, bytes, bytes], bytes]] = {
    MODE_AES_AES: decrypt_mode_aes_aes,
    MODE_DES_AES: decrypt_mode_des_aes,
    MODE_CTR_DES: decrypt_mode_ctr_des,
    MODE_AES_CTR: decrypt_mode_aes_ctr,
    MODE_DES_CTR: decrypt_mode_des_ctr,
    MODE_AES_DES: decrypt_mode_aes_des,
    MODE_CTR_CTR: decrypt_mode_ctr_ctr,
    MODE_DES_DES: decrypt_mode_des_des,
    MODE_CTR_AES: decrypt_mode_ctr_aes,
}


def decrypt_chapter(
    enc: bytes,
    additional_key: str | bytes,
    fuid: str | bytes,
    pool_base64: str,
    knva: bytes | None = None,
    *,
    aes_key: bytes | None = None,
    pool_decrypted: bytes | None = None,
) -> bytes:
    """移植 qqread/crypto.go 的 DecryptChapter，返回解压前后的正文字节。"""
    if isinstance(fuid, bytes):
        fuid_text = fuid.decode("utf-8", "replace")
    else:
        fuid_text = str(fuid)
    if not fuid_text:
        raise ValueError("FUID not set")
    if len(enc) < 256:
        raise ValueError(f"cipher data too small: {len(enc)}")
    if pool_decrypted is None and not pool_base64:
        raise ValueError("pool_base64 is required")
    if knva is None:
        knva = derive_knva()

    if aes_key is None:
        aes_key = master_key(fuid_text, knva)
    header = decrypt_header(enc, aes_key)
    key1 = header[:128]
    mode = _parse_header_field(key1[:8])
    param = _parse_header_field(key1[8:16])
    content_hash = key1[27:43]
    fuid_hash = key1[43:59]

    if not _is_all_zeros(fuid_hash):
        expected = hashlib.md5(fuid_text.encode("utf-8")).digest()
        if expected != fuid_hash:
            raise ValueError("FUID hash mismatch")

    if pool_decrypted is None:
        try:
            pool_bytes = base64.b64decode(pool_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid pool base64") from exc
        pool_decrypted = decrypt_keypool(pool_bytes, aes_key)
    key32 = content_key(pool_decrypted, param, fuid_text, additional_key)

    handler = _MODE_HANDLERS.get(mode)
    if handler is None:
        raise NotImplementedError(f"unsupported encryption mode: {mode}")
    step2 = handler(enc, key32, header)
    if not _is_all_zeros(content_hash):
        expected = hashlib.md5(step2).digest()
        if expected != content_hash:
            raise ValueError("content hash mismatch")
    return _gunzip_loose(step2)


def try_decrypt_chapter(
    enc: bytes,
    additional_key: str | bytes,
    fuid: str | bytes,
    pool_base64: str,
    knva: bytes | None = None,
    *,
    aes_key: bytes | None = None,
    pool_decrypted: bytes | None = None,
) -> Optional[bytes]:
    try:
        return decrypt_chapter(
            enc,
            additional_key,
            fuid,
            pool_base64,
            knva,
            aes_key=aes_key,
            pool_decrypted=pool_decrypted,
        )
    except Exception:
        return None


# === csigs ===
"""Csigs: bcrypt-like csigs algorithm ported from com.qq.reader.api.Csigs."""


MASK32 = 0xFFFFFFFF
BCRYPT_ALPHABET = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
DEC_TABLE = [-1] * 128
for _i, _ch in enumerate(BCRYPT_ALPHABET):
    DEC_TABLE[ord(_ch)] = _i

P_INIT = [
    608135816,
    -2052912941,
    320440878,
    57701188,
    -1542899678,
    698298832,
    137296536,
    -330404727,
    1160258022,
    953160567,
    -1101764913,
    887688300,
    -1062458953,
    -914599715,
    1065670069,
    -1253635817,
    -1843997223,
    -1988494565,
]

S_INIT = [
    -785314906,
    -1730169428,
    805139163,
    -803545161,
    -1193168915,
    1780907670,
    -1166241723,
    -248741991,
    614570311,
    -1282315017,
    134345442,
    -2054226922,
    1667834072,
    1901547113,
    -1537671517,
    -191677058,
    227898511,
    1921955416,
    1904987480,
    -2112533778,
    2069144605,
    -1034266187,
    -1674521287,
    720527379,
    -976113629,
    677414384,
    -901678824,
    -1193592593,
    -1904616272,
    1614419982,
    1822297739,
    -1340175810,
    -686458943,
    -1120842969,
    2024746970,
    1432378464,
    -430627341,
    -1437226092,
    1464375394,
    1676153920,
    1439316330,
    715854006,
    -1261675468,
    289532110,
    -1588296017,
    2087905683,
    -1276242927,
    1668267050,
    732546397,
    1947742710,
    -832815594,
    -1685613794,
    -1344882125,
    1814351708,
    2050118529,
    680887927,
    999245976,
    1800124847,
    -994056165,
    1713906067,
    1641548236,
    -81679983,
    1216130144,
    1575780402,
    -276538019,
    -377129551,
    -601480446,
    -345695352,
    596196993,
    -745100091,
    258830323,
    -2081144263,
    772490370,
    -1534844924,
    1774776394,
    -1642095778,
    566650946,
    -152474470,
    1728879713,
    -1412200208,
    1783734482,
    -665571480,
    -1777359064,
    -1420741725,
    1861159788,
    326777828,
    -1170476976,
    2130389656,
    -1578015459,
    967770486,
    1724537150,
    -2109534584,
    -1930525159,
    1164943284,
    2105845187,
    998989502,
    -529566248,
    -2050940813,
    1075463327,
    1455516326,
    1322494562,
    910128902,
    469688178,
    1117454909,
    936433444,
    -804646328,
    -619713837,
    1240580251,
    122909385,
    -2137449605,
    634681816,
    -152510729,
    -469872614,
    -1233564613,
    -1754472259,
    79693498,
    -1045868618,
    1084186820,
    1583128258,
    426386531,
    1761308591,
    1047286709,
    322548459,
    995290223,
    1845252383,
    -1691314900,
    -863943356,
    -1352745719,
    -1092366332,
    -567063811,
    1712269319,
    422464435,
    -1060394921,
    1170764815,
    -771006663,
    -1177289765,
    1434042557,
    442511882,
    -694091578,
    1076654713,
    1738483198,
    -81812532,
    -1901729288,
    -617471240,
    1014306527,
    -43947243,
    793779912,
    -1392160085,
    842905082,
    -48003232,
    1395751752,
    1040244610,
    -1638115397,
    -898659168,
    445077038,
    -552113701,
    -717051658,
    679411651,
    -1402522938,
    -1940957837,
    1767581616,
    -1144366904,
    -503340195,
    -1192226400,
    284835224,
    -48135240,
    1258075500,
    768725851,
    -1705778055,
    -1225243291,
    -762426948,
    1274779536,
    -505548070,
    -1530167757,
    1660621633,
    -823867672,
    -283063590,
    913787905,
    -797008130,
    737222580,
    -1780753843,
    -1366257256,
    -357724559,
    1804850592,
    -795946544,
    -1345903136,
    -1908647121,
    -1904896841,
    -1879645445,
    -233690268,
    -2004305902,
    -1878134756,
    1336762016,
    1754252060,
    -774901359,
    -1280786003,
    791618072,
    -1106372745,
    -361419266,
    -1962795103,
    -442446833,
    -1250986776,
    413987798,
    -829824359,
    -1264037920,
    -49028937,
    2093235073,
    -760370983,
    375366246,
    -2137688315,
    -1815317740,
    555357303,
    -424861595,
    2008414854,
    -950779147,
    -73583153,
    -338841844,
    2067696032,
    -700376109,
    -1373733303,
    2428461,
    544322398,
    577241275,
    1471733935,
    610547355,
    -267798242,
    1432588573,
    1507829418,
    2025931657,
    -648391809,
    545086370,
    48609733,
    -2094660746,
    1653985193,
    298326376,
    1316178497,
    -1287180854,
    2064951626,
    458293330,
    -1705826027,
    -703637697,
    -1130641692,
    727753846,
    -2115603456,
    146436021,
    1461446943,
    -224990101,
    705550613,
    -1235000031,
    -407242314,
    -13368018,
    -981117340,
    1404054877,
    -1449160799,
    146425753,
    1854211946,
    1266315497,
    -1246549692,
    -613086930,
    -1004984797,
    -1385257296,
    1235738493,
    -1662099272,
    -1880247706,
    -324367247,
    1771706367,
    1449415276,
    -1028546847,
    422970021,
    1963543593,
    -1604775104,
    -468174274,
    1062508698,
    1531092325,
    1804592342,
    -1711849514,
    -1580033017,
    -269995787,
    1294809318,
    -265986623,
    1289560198,
    -2072974554,
    1669523910,
    35572830,
    157838143,
    1052438473,
    1016535060,
    1802137761,
    1753167236,
    1386275462,
    -1214491899,
    -1437595849,
    1040679964,
    2145300060,
    -1904392980,
    1461121720,
    -1338320329,
    -263189491,
    -266592508,
    33600511,
    -1374882534,
    1018524850,
    629373528,
    -603381315,
    -779021319,
    2091462646,
    -1808644237,
    586499841,
    988145025,
    935516892,
    -927631820,
    -1695294041,
    -1455136442,
    265290510,
    -322386114,
    -1535828415,
    -499593831,
    1005194799,
    847297441,
    406762289,
    1314163512,
    1332590856,
    1866599683,
    -167115585,
    750260880,
    613907577,
    1450815602,
    -1129346641,
    -560302305,
    -644675568,
    -1282691566,
    -590397650,
    1427272223,
    778793252,
    1343938022,
    -1618686585,
    2052605720,
    1946737175,
    -1130390852,
    -380928628,
    -327488454,
    -612033030,
    1661551462,
    -1000029230,
    -283371449,
    840292616,
    -582796489,
    616741398,
    312560963,
    711312465,
    1351876610,
    322626781,
    1910503582,
    271666773,
    -2119403562,
    1594956187,
    70604529,
    -677132437,
    1007753275,
    1495573769,
    -225450259,
    -1745748998,
    -1631928532,
    504708206,
    -2031925904,
    -353800271,
    -2045878774,
    1514023603,
    1998579484,
    1312622330,
    694541497,
    -1712906993,
    -2143385130,
    1382467621,
    776784248,
    -1676627094,
    -971698502,
    -1797068168,
    -1510196141,
    503983604,
    -218673497,
    907881277,
    423175695,
    432175456,
    1378068232,
    -149744970,
    -340918674,
    -356311194,
    -474200683,
    -1501837181,
    -1317062703,
    26017576,
    -1020076561,
    -1100195163,
    1700274565,
    1756076034,
    -288447217,
    -617638597,
    720338349,
    1533947780,
    354530856,
    688349552,
    -321042571,
    1637815568,
    332179504,
    -345916010,
    53804574,
    -1442618417,
    -1250730864,
    1282449977,
    -711025141,
    -877994476,
    -288586052,
    1617046695,
    -1666491221,
    -1292663698,
    1686838959,
    431878346,
    -1608291911,
    1700445008,
    1080580658,
    1009431731,
    832498133,
    -1071531785,
    -1688990951,
    -2023776103,
    -1778935426,
    1648197032,
    -130578278,
    -1746719369,
    300782431,
    375919233,
    238389289,
    -941219882,
    -1763778655,
    2019080857,
    1475708069,
    455242339,
    -1685863425,
    448939670,
    -843904277,
    1395535956,
    -1881585436,
    1841049896,
    1491858159,
    885456874,
    -30872223,
    -293847949,
    1565136089,
    -396052509,
    1108368660,
    540939232,
    1173283510,
    -1549095958,
    -613658859,
    -87339056,
    -951913406,
    -278217803,
    1699691293,
    1103962373,
    -669091426,
    -2038084153,
    -464828566,
    1031889488,
    -815619598,
    1535977030,
    -58162272,
    -1043876189,
    2132092099,
    1774941330,
    1199868427,
    1452454533,
    157007616,
    -1390851939,
    342012276,
    595725824,
    1480756522,
    206960106,
    497939518,
    591360097,
    863170706,
    -1919713727,
    -698356495,
    1814182875,
    2094937945,
    -873565088,
    1082520231,
    -831049106,
    -1509457788,
    435703966,
    -386934699,
    1641649973,
    -1452693590,
    -989067582,
    1510255612,
    -2146710820,
    -1639679442,
    -1018874748,
    -36346107,
    236887753,
    -613164077,
    274041037,
    1734335097,
    -479771840,
    -976997275,
    1899903192,
    1026095262,
    -244449504,
    356393447,
    -1884275382,
    -421290197,
    -612127241,
    -381855128,
    -1803468553,
    -162781668,
    -1805047500,
    1091903735,
    1979897079,
    -1124832466,
    -727580568,
    -737663887,
    857797738,
    1136121015,
    1342202287,
    507115054,
    -1759230650,
    337727348,
    -1081374656,
    1301675037,
    -1766485585,
    1895095763,
    1721773893,
    -1078195732,
    62756741,
    2142006736,
    835421444,
    -1762973773,
    1442658625,
    -635090970,
    -1412822374,
    676362277,
    1392781812,
    170690266,
    -373920261,
    1759253602,
    -683120384,
    1745797284,
    664899054,
    1329594018,
    -393761396,
    -1249058810,
    2062866102,
    -1429332356,
    -751345684,
    -830954599,
    1080764994,
    553557557,
    -638351943,
    -298199125,
    991055499,
    499776247,
    1265440854,
    648242737,
    -354183246,
    980351604,
    -581221582,
    1749149687,
    -898096901,
    -83167922,
    -654396521,
    1161844396,
    -1169648345,
    1431517754,
    545492359,
    -26498633,
    -795437749,
    1437099964,
    -1592419752,
    -861329053,
    -1713251533,
    -1507177898,
    1060185593,
    1593081372,
    -1876348548,
    -34019326,
    69676912,
    -2135222948,
    86519011,
    -1782508216,
    -456757982,
    1220612927,
    -955283748,
    133810670,
    1090789135,
    1078426020,
    1569222167,
    845107691,
    -711212847,
    -222510705,
    1091646820,
    628848692,
    1613405280,
    -537335645,
    526609435,
    236106946,
    48312990,
    -1352249391,
    -892239595,
    1797494240,
    859738849,
    992217954,
    -289490654,
    -2051890674,
    -424014439,
    -562951028,
    765654824,
    -804095931,
    -1783130883,
    1685915746,
    -405998096,
    1414112111,
    -2021832454,
    -1013056217,
    -214004450,
    172450625,
    -1724973196,
    980381355,
    -185008841,
    -1475158944,
    -1578377736,
    -1726226100,
    -613520627,
    -964995824,
    1835478071,
    660984891,
    -590288892,
    -248967737,
    -872349789,
    -1254551662,
    1762651403,
    1719377915,
    -824476260,
    -1601057013,
    -652910941,
    -1156370552,
    1364962596,
    2073328063,
    1983633131,
    926494387,
    -871278215,
    -2144935273,
    -198299347,
    1749200295,
    -966120645,
    309677260,
    2016342300,
    1779581495,
    -1215147545,
    111262694,
    1274766160,
    443224088,
    298511866,
    1025883608,
    -488520759,
    1145181785,
    168956806,
    -653464466,
    -710153686,
    1689216846,
    -628709281,
    -1094719096,
    1692713982,
    -1648590761,
    -252198778,
    1618508792,
    1610833997,
    -771914938,
    -164094032,
    2001055236,
    -684262196,
    -2092799181,
    -266425487,
    -1333771897,
    1006657119,
    2006996926,
    -1108824540,
    1430667929,
    -1084739999,
    1314452623,
    -220332638,
    -193663176,
    -2021016126,
    1399257539,
    -927756684,
    -1267338667,
    1190975929,
    2062231137,
    -1960976508,
    -2073424263,
    -1856006686,
    1181637006,
    548689776,
    -1932175983,
    -922558900,
    -1190417183,
    -1149106736,
    296247880,
    1970579870,
    -1216407114,
    -525738999,
    1714227617,
    -1003338189,
    -396747006,
    166772364,
    1251581989,
    493813264,
    448347421,
    195405023,
    -1584991729,
    677966185,
    -591930749,
    1463355134,
    -1578971493,
    1338867538,
    1343315457,
    -1492745222,
    -1610435132,
    233230375,
    -1694987225,
    2000651841,
    -1017099258,
    1638401717,
    -266896856,
    -1057650976,
    6314154,
    819756386,
    300326615,
    590932579,
    1405279636,
    -1027467724,
    -1144263082,
    -1866680610,
    -335774303,
    -833020554,
    1862657033,
    1266418056,
    963775037,
    2089974820,
    -2031914401,
    1917689273,
    448879540,
    -744572676,
    -313240200,
    150775221,
    -667058989,
    1303187396,
    508620638,
    -1318983944,
    -1568336679,
    1817252668,
    1876281319,
    1457606340,
    908771278,
    -574175177,
    -677760460,
    -1838972398,
    1729034894,
    1080033504,
    976866871,
    -738527793,
    -1413318857,
    1522871579,
    1555064734,
    1336096578,
    -746444992,
    -1715692610,
    -720269667,
    -1089506539,
    -701686658,
    -956251013,
    -1215554709,
    564236357,
    -1301368386,
    1781952180,
    1464380207,
    -1131123079,
    -962365742,
    1699332808,
    1393555694,
    1183702653,
    -713881059,
    1288719814,
    691649499,
    -1447410096,
    -1399511320,
    -1101077756,
    -1577396752,
    1781354906,
    1676643554,
    -1702433246,
    -1064713544,
    1126444790,
    -1524759638,
    -1661808476,
    -2084544070,
    -1679201715,
    -1880812208,
    -1167828010,
    673620729,
    -1489356063,
    1269405062,
    -279616791,
    -953159725,
    -145557542,
    1057255273,
    2012875353,
    -2132498155,
    -2018474495,
    -1693849939,
    993977747,
    -376373926,
    -1640704105,
    753973209,
    36408145,
    -1764381638,
    25011837,
    -774947114,
    2088578344,
    530523599,
    -1376601957,
    1524020338,
    1518925132,
    -534139791,
    -535190042,
    1202760957,
    -309069157,
    -388774771,
    674977740,
    -120232407,
    2031300136,
    2019492241,
    -311074731,
    -141160892,
    -472686964,
    352677332,
    -1997247046,
    60907813,
    90501309,
    -1007968747,
    1016092578,
    -1759044884,
    -1455814870,
    457141659,
    509813237,
    -174299397,
    652014361,
    1966332200,
    -1319764491,
    55981186,
    -1967506245,
    676427537,
    -1039476232,
    -1412673177,
    -861040033,
    1307055953,
    942726286,
    933058658,
    -1826555503,
    -361066302,
    -79791154,
    1361170020,
    2001714738,
    -1464409218,
    -1020707514,
    1222529897,
    1679025792,
    -1565652976,
    -580013532,
    1770335741,
    151462246,
    -1281735158,
    1682292957,
    1483529935,
    471910574,
    1539241949,
    458788160,
    -858652289,
    1807016891,
    -576558466,
    978976581,
    1043663428,
    -1129001515,
    1927990952,
    -94075717,
    -1922690386,
    -1086558393,
    -761535389,
    1412390302,
    -1362987237,
    -162634896,
    1947078029,
    -413461673,
    -126740879,
    -1353482915,
    1077988104,
    1320477388,
    886195818,
    18198404,
    -508558296,
    -1785185763,
    112762804,
    -831610808,
    1866414978,
    891333506,
    18488651,
    661792760,
    1628790961,
    -409780260,
    -1153795797,
    876946877,
    -1601685023,
    1372485963,
    791857591,
    -1608533303,
    -534984578,
    -1127755274,
    -822013501,
    -1578587449,
    445679433,
    -732971622,
    -790962485,
    -720709064,
    54117162,
    -963561881,
    -1913048708,
    -525259953,
    -140617289,
    1140177722,
    -220915201,
    668550556,
    -1080614356,
    367459370,
    261225585,
    -1684794075,
    -85617823,
    -826893077,
    -1029151655,
    314222801,
    -1228863650,
    -486184436,
    282218597,
    -888953790,
    -521376242,
    379116347,
    1285071038,
    846784868,
    -1625320142,
    -523005217,
    -744475605,
    -1989021154,
    453669953,
    1268987020,
    -977374944,
    -1015663912,
    -550133875,
    -1684459730,
    -435458233,
    266596637,
    -447948204,
    517658769,
    -832407089,
    -851542417,
    370717030,
    -47440635,
    -2070949179,
    -151313767,
    -182193321,
    -1506642397,
    -1817692879,
    1456262402,
    -1393524382,
    1517677493,
    1846949527,
    -1999473716,
    -560569710,
    -2118563376,
    1280348187,
    1908823572,
    -423180355,
    846861322,
    1172426758,
    -1007518822,
    -911584259,
    1655181056,
    -1155153950,
    901632758,
    1897031941,
    -1308360158,
    -1228157060,
    -847864789,
    1393639104,
    373351379,
    950779232,
    625454576,
    -1170726756,
    -146354570,
    2007998917,
    544563296,
    -2050228658,
    -1964470824,
    2058025392,
    1291430526,
    424198748,
    50039436,
    29584100,
    -689184263,
    -1865090967,
    -1503863136,
    1057563949,
    -1039604065,
    -1219600078,
    -831004069,
    1469046755,
    985887462,
]

CIHAI_INIT = [1332899944, 1700884034, 1701343084, 1684370003, 1668446532, 1869963892]


def _u32(x: int) -> int:
    return x & MASK32


def _i32(x: int) -> int:
    x &= MASK32
    return x if x < 0x80000000 else x - 0x100000000


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def generate_salt(rounds: int = 4, random_bytes: Optional[bytes] = None) -> str:
    if rounds < 4 or rounds > 30:
        raise ValueError("log_rounds exceeds maximum (30)")
    salt_bytes = random_bytes if random_bytes is not None else secrets.token_bytes(16)
    if len(salt_bytes) != 16:
        raise ValueError("salt must be 16 bytes")
    salt_b64 = magic_b64_encode(salt_bytes, len(salt_bytes))
    return f"$2a${rounds:02d}${salt_b64}"


def magic_b64_decode(s: str, max_len: int) -> bytes:
    L = len(s)
    tmp = bytearray(max_len)
    out_len = 0
    i = 0
    while i < L - 1 and out_len < max_len:
        c1 = s[i]
        c2 = s[i + 1]
        if ord(c1) >= 0x80 or ord(c2) >= 0x80:
            break
        b1 = DEC_TABLE[ord(c1)]
        b2 = DEC_TABLE[ord(c2)]
        if b1 == -1 or b2 == -1:
            break
        tmp[out_len] = ((b1 << 2) | ((b2 & 0x30) >> 4)) & 0xFF
        out_len += 1
        if out_len >= max_len or i + 2 >= L:
            break
        c3 = s[i + 2]
        if ord(c3) >= 0x80:
            break
        b3 = DEC_TABLE[ord(c3)]
        if b3 == -1:
            break
        tmp[out_len] = (((b2 & 0xF) << 4) | ((b3 & 0x3C) >> 2)) & 0xFF
        out_len += 1
        if out_len >= max_len or i + 3 >= L:
            break
        c4 = s[i + 3]
        if ord(c4) >= 0x80:
            break
        b4 = DEC_TABLE[ord(c4)]
        if b4 == -1:
            break
        tmp[out_len] = (((b3 & 3) << 6) | b4) & 0xFF
        out_len += 1
        i += 4
    return bytes(tmp[:out_len])


def magic_b64_encode(b: bytes, length: int) -> str:
    sb = []
    i = 0
    while i < length:
        c1 = b[i] & 0xFF
        sb.append(BCRYPT_ALPHABET[(c1 >> 2) & 0x3F])
        c1 = (c1 & 3) << 4
        i += 1
        if i >= length:
            sb.append(BCRYPT_ALPHABET[c1 & 0x3F])
            break
        c2 = b[i] & 0xFF
        sb.append(BCRYPT_ALPHABET[(c1 | ((c2 >> 4) & 0xF)) & 0x3F])
        c1 = (c2 & 0xF) << 2
        i += 1
        if i >= length:
            sb.append(BCRYPT_ALPHABET[c1 & 0x3F])
            break
        c3 = b[i] & 0xFF
        sb.append(BCRYPT_ALPHABET[(c1 | ((c3 >> 6) & 3)) & 0x3F])
        sb.append(BCRYPT_ALPHABET[c3 & 0x3F])
        i += 1
    return "".join(sb)


def stream_to_word(data: bytes, idx_ref: List[int]) -> int:
    if not data:
        return 0
    idx = idx_ref[0]
    w = 0
    for _ in range(4):
        w = ((w << 8) | (data[idx] & 0xFF)) & MASK32
        idx = (idx + 1) % len(data)
    idx_ref[0] = idx
    return w


def blowfish_encrypt_block(P: List[int], S: List[int], l: int, r: int):
    i3 = _u32(l)
    i5 = _u32(r)
    i6 = 0
    i7 = _u32(P[0])
    while True:
        i3 = _u32(i3 ^ i7)
        if i6 > 14:
            l_out = _u32(i5 ^ P[17])
            r_out = i3
            return l_out, r_out
        s0 = S[(i3 >> 24) & 0xFF]
        s1 = S[((i3 >> 16) & 0xFF) | 0x100]
        s2 = S[((i3 >> 8) & 0xFF) | 0x200]
        s3 = S[(i3 & 0xFF) | 0x300]
        f = _u32((_u32(s0 + s1) ^ s2) + s3)
        i9 = i6 + 1
        i6 = i9 + 1
        i5 = _u32(i5 ^ _u32(f ^ P[i9]))
        s0 = S[(i5 >> 24) & 0xFF]
        s1 = S[((i5 >> 16) & 0xFF) | 0x100]
        s2 = S[((i5 >> 8) & 0xFF) | 0x200]
        s3 = S[(i5 & 0xFF) | 0x300]
        f2 = _u32((_u32(s0 + s1) ^ s2) + s3)
        i7 = _u32(P[i6] ^ f2)


def expand_with_key(P: List[int], S: List[int], key_bytes: bytes) -> None:
    idx_ref = [0]
    for i in range(len(P)):
        P[i] = _i32(P[i] ^ stream_to_word(key_bytes, idx_ref))
    block_l = 0
    block_r = 0
    for i in range(0, len(P), 2):
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        P[i] = _i32(block_l)
        P[i + 1] = _i32(block_r)
    for i in range(0, len(S), 2):
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        S[i] = _i32(block_l)
        S[i + 1] = _i32(block_r)


def expand_with_salt_and_key(
    P: List[int], S: List[int], salt: bytes, key: bytes
) -> None:
    idx_key = [0]
    idx_salt = [0]
    for i in range(len(P)):
        P[i] = _i32(P[i] ^ stream_to_word(key, idx_key))
    block_l = 0
    block_r = 0
    for i in range(0, len(P), 2):
        block_l = _u32(block_l ^ stream_to_word(salt, idx_salt))
        block_r = _u32(block_r ^ stream_to_word(salt, idx_salt))
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        P[i] = _i32(block_l)
        P[i + 1] = _i32(block_r)
    for i in range(0, len(S), 2):
        block_l = _u32(block_l ^ stream_to_word(salt, idx_salt))
        block_r = _u32(block_r ^ stream_to_word(salt, idx_salt))
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        S[i] = _i32(block_l)
        S[i + 1] = _i32(block_r)


def magic_search_final(
    password_bytes: bytes, salt_bytes: bytes, rounds_log2: int, cihai_init: List[int]
) -> bytes:
    if rounds_log2 < 4 or rounds_log2 > 30:
        raise ValueError("Bad number of rounds")
    if len(salt_bytes) != 16:
        raise ValueError("Bad salt length")
    P = list(P_INIT)
    S = list(S_INIT)
    i_arr = list(cihai_init)
    expand_with_salt_and_key(P, S, salt_bytes, password_bytes)
    loops = 1 << rounds_log2
    for _ in range(loops):
        expand_with_key(P, S, password_bytes)
        expand_with_key(P, S, salt_bytes)
    half_len = len(i_arr) >> 1
    for _round in range(64):
        for j in range(half_len):
            idx = j * 2
            l = i_arr[idx]
            r = i_arr[idx + 1]
            lr0, lr1 = blowfish_encrypt_block(P, S, l, r)
            i_arr[idx] = _i32(lr0)
            i_arr[idx + 1] = _i32(lr1)
    out = bytearray(len(i_arr) * 4)
    k = 0
    for v in i_arr:
        vv = _u32(v)
        out[k] = (vv >> 24) & 0xFF
        out[k + 1] = (vv >> 16) & 0xFF
        out[k + 2] = (vv >> 8) & 0xFF
        out[k + 3] = vv & 0xFF
        k += 4
    return bytes(out)


def search(password: str, salt_str: Optional[str] = None) -> str:
    if salt_str is None:
        salt_str = generate_salt(4)
    if len(salt_str) < 4 or salt_str[0] != "$" or salt_str[1] != "2":
        raise ValueError("Invalid salt version")
    c_rev = "\x00"
    i2 = 3
    if salt_str[2] != "$":
        c_rev = salt_str[2]
        if c_rev != "a" or salt_str[3] != "$":
            raise ValueError("Invalid salt revision")
        i2 = 4
    i3 = i2 + 2
    if salt_str[i3] != "$":
        raise ValueError("Missing salt rounds")
    rounds_log2 = int(salt_str[i2:i3])
    if rounds_log2 < 4:
        raise ValueError("Bad number of rounds")
    if rounds_log2 > 30:
        raise ValueError("rounds exceeds maximum (30)")
    salt_b64 = salt_str[i2 + 3 : i2 + 25]
    if len(salt_b64) != 22:
        raise ValueError("Bad bcrypt-like salt length")
    pwd_bytes = password.encode("utf-8")
    if c_rev >= "a":
        pwd_bytes = password.encode("utf-8") + b"\x00"
    salt_bytes = magic_b64_decode(salt_b64, 16)
    # QQ 阅读使用 $2a$ 变体；bcrypt C 扩展会自行处理末尾 NUL，
    # 传入原始密码即可得到与下方兼容实现相同的 csigs。
    if (
        _bcrypt is not None
        and c_rev == "a"
        and len(password.encode("utf-8")) <= 72
        and len(salt_bytes) == 16
    ):
        try:
            return _bcrypt.hashpw(
                password.encode("utf-8"), salt_str.encode("ascii")
            ).decode("ascii")
        except (TypeError, ValueError, UnicodeError):
            pass
    out_bytes = magic_search_final(pwd_bytes, salt_bytes, rounds_log2, CIHAI_INIT)
    sb = ["$2"]
    if c_rev >= "a":
        sb.append(c_rev)
    sb.append("$")
    if rounds_log2 < 10:
        sb.append("0")
    if rounds_log2 > 30:
        raise ValueError("rounds exceeds maximum (30)")
    sb.append(str(rounds_log2))
    sb.append("$")
    sb.append(magic_b64_encode(salt_bytes, len(salt_bytes)))
    sb.append(magic_b64_encode(out_bytes, len(CIHAI_INIT) * 4 - 1))
    return "".join(sb)


# === tar ===
"""Tar stream reader (response body is tar of encrypted chapter blobs)."""


def tar_decrypt(stream: Union[BinaryIO, bytes]) -> Dict[str, object]:
    """Port of TarDecompressor.decrypt. Returns map of filename -> bytes, plus code."""
    result: Dict[str, object] = {}
    try:
        if isinstance(stream, (bytes, bytearray)):
            bio = io.BytesIO(stream)
        else:
            data = stream.read()
            bio = io.BytesIO(data)
        with tarfile.open(fileobj=bio, mode="r|*") as tar:
            for member in tar:
                if member.isdir():
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                result[member.name] = f.read()
        result["code"] = 0
        return result
    except Exception as e:
        logger.debug(f"QQ阅读参考 tar 解析失败：错误={type(e).__name__}")
        result["code"] = -1
        return result


# === config (embedded, minimal) ===
# Account / client identity used by chapter API + csigs.
# knva is derived from SO constants (derive_knva), not configured.
# The dynamic key pool is cached only in this process.
CONFIG: Dict[str, str] = {
    "loginType": "50",
    "c_platform": "android",
    "c_version": "qqreader_8.3.3.0888_android",
    "channel": "10005136",
    "qrsn": "0022ece0af3ed4d0052148e33e8bce20ab31a706cf9af04b",
    "usid": "",
    "uid": "",
    "fuid": "89306811035542cd868d49def7d3857d",
}

_固定配置已加载 = False
_固定配置加载锁 = threading.Lock()
_QQ阅读配置上下文 = globals().get("_QQ阅读配置上下文") or contextvars.ContextVar(
    "mantou_qq_reader_account_config", default=None
)


class ConfigManager:
    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.login_type = "50"
        self.c_platform = "android"
        self.c_version = ""
        self.channel = ""
        self.qrsn = ""
        self.usid = ""
        self.uid = ""
        self.fuid = ""
        self.key_pool: Optional[str] = None
        self._knva_cache: bytes | None = None
        self._decryption_cache: tuple[str, str, bytes, bytes, bytes] | None = None
        self._decryption_cache_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        当前配置 = _QQ阅读配置上下文.get()
        if 当前配置 is not None:
            return 当前配置
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConfigManager()
            return cls._instance

    def _knva_bytes(self) -> bytes:
        with self._decryption_cache_lock:
            if self._knva_cache is None:
                self._knva_cache = derive_knva()
            return self._knva_cache

    def 获取解密材料(self) -> tuple[bytes, bytes, bytes]:
        """按当前 fuid 和密钥池缓存 KNVA、主密钥及已解密密钥池。"""
        with self._decryption_cache_lock:
            fuid = str(self.fuid or "")
            pool_b64 = str(self.key_pool or "")
            if not fuid or not pool_b64:
                raise ValueError("QQ阅读解密材料不完整")
            cached = self._decryption_cache
            if cached is not None and cached[0] == fuid and cached[1] == pool_b64:
                return cached[2], cached[3], cached[4]
            knva = self._knva_bytes()
            aes_key = master_key(fuid, knva)
            try:
                pool_bytes = base64.b64decode(pool_b64, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("invalid pool base64") from exc
            pool_decrypted = decrypt_keypool(pool_bytes, aes_key)
            if len(pool_decrypted) < 16:
                raise ValueError("QQ阅读解密密钥池为空")
            self._decryption_cache = (fuid, pool_b64, knva, aes_key, pool_decrypted)
            return knva, aes_key, pool_decrypted

    def _cache_valid(self, pool_b64: str) -> bool:
        if not pool_b64 or not self.fuid:
            return False
        try:
            fuid = str(self.fuid)
            with self._decryption_cache_lock:
                cached = self._decryption_cache
                if cached is not None and cached[0] == fuid and cached[1] == str(pool_b64):
                    return len(cached[4]) >= 16
            raw = base64.b64decode(pool_b64, validate=True)
            pool = decrypt_keypool(raw, master_key(fuid, self._knva_bytes()))
            return len(pool) >= 16
        except Exception:
            return False

    def _load_key_pool_cache(self) -> Optional[str]:
        return self.key_pool

    def _save_key_pool_cache(self, pool_b64: str) -> None:
        with self._decryption_cache_lock:
            self.key_pool = pool_b64
            if not (
                self._decryption_cache is not None
                and self._decryption_cache[0] == str(self.fuid or "")
                and self._decryption_cache[1] == str(pool_b64 or "")
            ):
                self._decryption_cache = None

    def apply(self, m: Dict[str, Any]) -> None:
        if "loginType" in m:
            self.login_type = str(m["loginType"])
        if "c_platform" in m:
            self.c_platform = str(m["c_platform"])
        if "c_version" in m:
            self.c_version = str(m["c_version"])
        if "channel" in m:
            self.channel = str(m["channel"])
        if "qrsn" in m:
            self.qrsn = str(m["qrsn"])
        if "usid" in m:
            self.usid = str(m["usid"])
        if "uid" in m:
            self.uid = str(m["uid"])
        if "fuid" in m:
            new_fuid = str(m["fuid"])
            if new_fuid != self.fuid:
                with self._decryption_cache_lock:
                    self.fuid = new_fuid
                    self._decryption_cache = None
            else:
                self.fuid = new_fuid


def load_config_once() -> None:
    global _固定配置已加载
    if _固定配置已加载:
        return
    with _固定配置加载锁:
        if _固定配置已加载:
            return
        with ConfigManager._lock:
            if ConfigManager._instance is None:
                ConfigManager._instance = ConfigManager()
            ConfigManager._instance.apply(CONFIG)
        _固定配置已加载 = True


@contextmanager
def QQ阅读账号上下文(登录态: dict[str, Any] | None):
    """固定本次异步任务及其子任务的账号，不修改其它下载的身份。"""
    load_config_once()
    当前配置 = ConfigManager()
    当前配置.apply(CONFIG)
    当前配置.uid = str((登录态 or {}).get("ywguid") or "")
    当前配置.usid = str((登录态 or {}).get("ywkey") or "")
    基础配置 = ConfigManager._instance
    if 基础配置 is not None and 基础配置.fuid == 当前配置.fuid:
        当前配置.key_pool = 基础配置.key_pool
    token = _QQ阅读配置上下文.set(当前配置)
    try:
        yield 当前配置
    finally:
        _QQ阅读配置上下文.reset(token)


# === fetcher ===
"""Fetcher: book info / list / toc / content / sign / manju."""


UA = "okhttp/3.12.13"
SIGN_TAIL = "B74H5a2Yh73gfu8F"
QQ阅读批量章节数 = 200
QQ阅读批量最大动态并发数 = 100
# 正文请求和失败窗口按实际批次数动态限流，连接池继续复用同一异步会话。
QQ阅读批量请求安全并发数 = 100
QQ阅读失败章节重试窗口 = 31
QQ阅读失败章节重试轮数 = 3
QQ阅读解密最大动态并发数 = max(4, min(64, (os.cpu_count() or 4) * 2))
QQ阅读出版书最大动态并发数 = 16
_QQ阅读密钥池异步锁: asyncio.Lock | None = None
_QQ阅读签名执行器: ThreadPoolExecutor | None = None
_QQ阅读签名执行器锁 = threading.Lock()
_QQ阅读解密执行器: ThreadPoolExecutor | None = None
_QQ阅读解密执行器锁 = threading.Lock()


def 计算QQ阅读批量并发数(批次数量: int) -> int:
    """按批次数量和网关限流上限计算实际请求并发。"""
    count = max(1, int(批次数量 or 1))
    return max(
        1,
        min(
            QQ阅读批量最大动态并发数,
            QQ阅读批量请求安全并发数,
            count,
        ),
    )


def 创建QQ阅读HTTP会话(
    *, concurrency: int = QQ阅读批量最大动态并发数
) -> aiohttp.ClientSession:
    """创建下载期间复用的异步连接池。"""
    limit = max(1, int(concurrency or 1))
    connector = aiohttp.TCPConnector(
        limit=limit,
        limit_per_host=limit,
        ttl_dns_cache=300,
        keepalive_timeout=30,
    )
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=90)
    return aiohttp.ClientSession(
        headers={"User-Agent": UA},
        timeout=timeout,
        connector=connector,
    )


def _获取QQ阅读签名执行器() -> ThreadPoolExecutor:
    global _QQ阅读签名执行器
    with _QQ阅读签名执行器锁:
        if _QQ阅读签名执行器 is None or getattr(_QQ阅读签名执行器, "_shutdown", False):
            _QQ阅读签名执行器 = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="qq-reader-sign",
            )
        return _QQ阅读签名执行器


def _获取QQ阅读解密执行器() -> ThreadPoolExecutor:
    global _QQ阅读解密执行器
    with _QQ阅读解密执行器锁:
        if _QQ阅读解密执行器 is None or getattr(_QQ阅读解密执行器, "_shutdown", False):
            _QQ阅读解密执行器 = ThreadPoolExecutor(
                max_workers=max(2, min(8, os.cpu_count() or 4)),
                thread_name_prefix="qq-reader-decrypt",
            )
        return _QQ阅读解密执行器


async def _异步QQ阅读CPU函数(函数: Callable[..., Any], *参数: Any) -> Any:
    """在独立线程池运行正文解包/解密，避免挤占网页与消息线程池。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _获取QQ阅读解密执行器(), contextvars.copy_context().run, 函数, *参数
    )


async def 异步构造QQ阅读鉴权请求头(
    timestamp_ms: int,
    request_url: str | None = None,
) -> Dict[str, str]:
    """把 csigs/网关签名移出事件循环，避免阻塞网页和消息事件。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _获取QQ阅读签名执行器(),
        contextvars.copy_context().run,
        构造QQ阅读鉴权请求头,
        timestamp_ms,
        request_url,
    )


def 关闭QQ阅读签名执行器() -> None:
    global _QQ阅读签名执行器, _QQ阅读解密执行器
    with _QQ阅读签名执行器锁:
        executor = _QQ阅读签名执行器
        _QQ阅读签名执行器 = None
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)
    with _QQ阅读解密执行器锁:
        decrypt_executor = _QQ阅读解密执行器
        _QQ阅读解密执行器 = None
    if decrypt_executor is not None:
        decrypt_executor.shutdown(wait=False, cancel_futures=True)


def _获取QQ阅读密钥池异步锁() -> asyncio.Lock:
    global _QQ阅读密钥池异步锁
    if _QQ阅读密钥池异步锁 is None:
        _QQ阅读密钥池异步锁 = asyncio.Lock()
    return _QQ阅读密钥池异步锁


async def 确保QQ阅读密钥池(
    session: aiohttp.ClientSession,
    *,
    force: bool = False,
) -> bool:
    """异步刷新正文解密所需密钥池，避免在解密线程中发起网络请求。"""
    load_config_once()
    config = ConfigManager.get_instance()
    if not config.fuid:
        return False
    if not force and config.key_pool and config._cache_valid(config.key_pool):
        return True

    async with _获取QQ阅读密钥池异步锁():
        if not force and config.key_pool and config._cache_valid(config.key_pool):
            return True
        try:
            params = {"fuid": config.fuid, "type": "1"}
            request_url = _构造QQ阅读请求地址(
                "https://newminerva-tgw.reader.qq.com/sk",
                params,
            )
            async with session.get(
                "https://newminerva-tgw.reader.qq.com/sk",
                params=params,
                headers=await 异步构造QQ阅读鉴权请求头(
                    int(time.time() * 1000), request_url
                ),
            ) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        except Exception as exc:
            logger.debug(f"QQ阅读密钥池获取失败：错误={type(exc).__name__}")
            return False
        pool = (
            str((data or {}).get("pool") or "").strip()
            if isinstance(data, dict)
            else ""
        )
        if not pool or not config._cache_valid(pool):
            logger.debug("QQ阅读密钥池响应无效")
            return False
        config._save_key_pool_cache(pool)
        return True


QQ阅读网关签名版本 = "1"
QQ阅读网关设备标识 = "0"
QQ阅读可信标识盐 = ").#@!U_*#@DxL09V"
QQ阅读网关MD5密钥编码 = bytes(
    (
        0xBF,
        0xB8,
        0xB5,
        0xD6,
        0xB7,
        0xC3,
        0xC9,
        0xBC,
        0xB5,
        0xD6,
        0xD2,
        0xEE,
        0xDA,
        0xA6,
        0xAF,
        0xC0,
    )
)


def _QQ阅读网关MD5密钥() -> str:
    return bytes(value ^ 0x96 for value in QQ阅读网关MD5密钥编码).decode("ascii")


def _QQ阅读网关摘要(data: bytes, index: int) -> bytes:
    if index == 0:
        return MD2.new(data).digest()
    if index == 1:
        return MD4.new(data).digest()
    return hashlib.md5(data).digest()


def 计算QQ阅读SSign(规范参数: str) -> str:
    """按 QQ 阅读网关规则计算随请求变化的 ssign。"""
    payload = 规范参数.encode("utf-8")
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    first = _QQ阅读网关摘要(payload, checksum % 3)
    index = (checksum >> 8) % 3
    return _QQ阅读网关摘要(_QQ阅读网关摘要(first, index), index).hex()


def _构造QQ阅读网关规范参数(request_url: str, headers: dict[str, str]) -> str:
    items: dict[str, str] = {}
    try:
        pairs = parse_qsl(urlsplit(request_url).query, keep_blank_values=True)
    except ValueError:
        pairs = []
    for key, value in pairs:
        items.setdefault(str(key), str(value))
    items["qrsn"] = str(headers.get("qrsn") or "")
    items["c_version"] = str(headers.get("c_version") or "")
    items["ttime"] = str(headers.get("ttime") or "")
    return "&".join(f"{key}={items[key]}" for key in sorted(items))


def _构造QQ阅读请求地址(url: str, params: dict[str, Any]) -> str:
    query = urlencode(params, doseq=True)
    if not query:
        return url
    return f"{url}{'&' if '?' in url else '?'}{query}"


def _生成QQ阅读YWToken(value: str) -> str:
    raw = str(value or "").encode("utf-8")
    padding = 8 - len(raw) % 8
    padded = raw + bytes([padding]) * padding
    return DES.new(b"1R8SH560", DES.MODE_ECB).encrypt(padded).hex().upper()


def _稳定QQ阅读随机标识(seed: str, length: int) -> str:
    value = str(seed or "").strip() or secrets.token_hex(16)
    result = hashlib.sha256(value.encode("utf-8")).hexdigest()
    while len(result) < length:
        result += hashlib.sha256((result + value).encode("utf-8")).hexdigest()
    return result[:length]


def _补充QQ阅读网关签名(
    headers: dict[str, str],
    request_url: str,
) -> dict[str, str]:
    """为 /sk、目录和正文网关请求补齐动态签名字段。"""
    signed = dict(headers)
    timestamp_ms = str(signed.get("ttime") or int(time.time() * 1000))
    signed["ttime"] = timestamp_ms
    signed["qrtm"] = str(int(timestamp_ms) // 1000)

    config = ConfigManager.get_instance()
    if not signed.get("qrsn"):
        signed["qrsn"] = _稳定QQ阅读随机标识(
            "|".join(
                (
                    config.channel,
                    config.c_version,
                    config.login_type,
                    config.uid,
                    config.usid,
                )
            ),
            16,
        )
    if not signed.get("qrsn_new"):
        signed["qrsn_new"] = _稳定QQ阅读随机标识(
            "|".join((signed["qrsn"], config.c_platform, config.uid, config.usid)),
            36,
        )

    try:
        fuid = next(iter(parse_qs(urlsplit(request_url).query).get("fuid", [])), "")
    except ValueError:
        fuid = ""
    signed["logid"] = (
        f"{fuid}_{timestamp_ms}" if fuid else f"{secrets.token_hex(16)}_{timestamp_ms}"
    )

    login_uin = str(signed.get("uid") or "").strip()
    channel = str(signed.get("channel") or "").strip()
    c_version = str(signed.get("c_version") or "").strip()
    qrtm = signed["qrtm"]
    if login_uin and channel and c_version:
        safe_source = "|".join(
            (
                c_version,
                channel,
                login_uin,
                _QQ阅读网关MD5密钥(),
                qrtm,
                QQ阅读网关设备标识,
            )
        )
        signed["safekey"] = hashlib.md5(safe_source.encode("utf-8")).hexdigest().upper()

    qrsn = str(signed.get("qrsn") or "").strip()
    if login_uin and channel and c_version and qrsn:
        existing_trustedid = str(signed.get("trustedid") or "").strip()
        suffix = existing_trustedid[-1:] if len(existing_trustedid) >= 33 else "1"
        trusted_source = "|".join(
            (
                login_uin,
                qrsn,
                QQ阅读网关设备标识,
                c_version,
                channel,
                qrtm,
                QQ阅读可信标识盐,
                "",
            )
        )
        signed["trustedid"] = (
            hashlib.md5(trusted_source.encode("utf-8")).hexdigest().upper() + suffix
        )

    login_type = str(signed.get("loginType") or "")
    login_key = str(signed.get("usid") or "")
    if login_type not in {"50", "52"}:
        login_key = str(signed.get("ywkey") or login_key)
    if login_key:
        signed["ywtoken"] = _生成QQ阅读YWToken(login_key)

    signed["ssign"] = 计算QQ阅读SSign(_构造QQ阅读网关规范参数(request_url, signed))
    signed["ssign_version"] = QQ阅读网关签名版本
    return signed


def 构造QQ阅读鉴权请求头(
    timestamp_ms: int,
    request_url: str | None = None,
) -> Dict[str, str]:
    config = ConfigManager.get_instance()
    pwd = (
        f"{config.login_type}|||{config.c_version}|{config.c_platform}|{config.channel}|"
        f"{config.qrsn}|{config.qrsn}||||0|{timestamp_ms}|{SIGN_TAIL}"
    )
    headers = {
        "User-Agent": UA,
        "loginType": config.login_type,
        "c_platform": config.c_platform,
        "c_version": config.c_version,
        "channel": config.channel,
        "qrsn": config.qrsn,
        "usid": config.usid,
        "uid": config.uid,
        "qqnum": config.uid,
        "youngerMode": "0",
        "qrsn_new": config.qrsn,
        "ttime": str(timestamp_ms),
        "csigs": search(sha256_hex(pwd), generate_salt()),
    }
    if request_url:
        return _补充QQ阅读网关签名(headers, request_url)
    return headers


QQ阅读账号客户端版本 = "qqreader_8.5.2.0888_android"
QQ阅读账号应用版本 = "8.5.2.890"
QQ阅读账号渠道 = "10000285"
QQ阅读账号设备UA = "SM-N9760#marlin#28"
QQ阅读账号CSigs字段 = (
    "loginType",
    "ywguid",
    "ywkey",
    "c_version",
    "c_platform",
    "channel",
    "qrsn",
    "qrsn_new",
    "gselect",
    "server_sex",
    "rcmd",
    "youngerMode",
    "ttime",
)


def _获取QQ阅读账号Qrsn(config: ConfigManager) -> str:
    """返回账号接口所需的 36 位设备标识，不复用正文网关的旧标识。"""
    configured = str(config.qrsn or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{36}", configured):
        return configured
    return _稳定QQ阅读随机标识(
        "|".join(
            (
                str(config.uid or ""),
                str(config.usid or ""),
                QQ阅读账号客户端版本,
                QQ阅读账号渠道,
                "account-qrsn",
            )
        ),
        36,
    )


def _生成QQ阅读账号CSigs(headers: dict[str, str]) -> str:
    """按 Android getAcctInfo 实际字段顺序生成 csigs。"""
    # loginType=50 的 Android 请求虽然通过 uid/usid 传递登录态，
    # 但 csigs 的 ywguid/ywkey 两个槽位必须保持为空。抓包中
    # ``50|||c_version|...`` 的原文可由 bcrypt 校验通过；把 uid/usid
    # 映射到这两个槽位会使账号接口返回无效登录态。
    values = dict(headers)
    values["ywguid"] = ""
    values["ywkey"] = ""
    raw = "|".join(str(values.get(field) or "") for field in QQ阅读账号CSigs字段)
    return search(sha256_hex(f"{raw}|{SIGN_TAIL}"), generate_salt())


def 构造QQ阅读账号请求头(
    timestamp_ms: int,
    request_url: str,
) -> Dict[str, str]:
    """构造 getAcctInfo 使用的 Android 客户端请求头。

    QQ 阅读的账号接口会校验客户端设备字段。设备标识由当前登录态和
    固定客户端参数派生，只在内存中使用，不把抓包中的动态鉴权值落盘。
    """
    config = ConfigManager.get_instance()
    qrsn = _获取QQ阅读账号Qrsn(config)
    timestamp = str(int(timestamp_ms))
    seed = "|".join(
        (
            str(config.uid or ""),
            str(config.usid or ""),
            qrsn,
            QQ阅读账号客户端版本,
            QQ阅读账号渠道,
        )
    )
    device_id = _稳定QQ阅读随机标识(seed + "|device", 32)
    headers: Dict[str, str] = {
        "User-Agent": UA,
        "gselect": "-1",
        "loginType": str(config.login_type),
        "server_sex": "1",
        "tinkerid": "",
        "c_platform": str(config.c_platform),
        "c_version": QQ阅读账号客户端版本,
        "channel": QQ阅读账号渠道,
        "isScanQrCodeLogin": "0",
        "qrsn": qrsn,
        "dn": device_id,
        "qqnum": str(config.uid),
        "ua": QQ阅读账号设备UA,
        "usid": str(config.usid),
        "sid": "",
        "dt": device_id,
        "uid": str(config.uid),
        "youngerMode": "0",
        "mversion": QQ阅读账号应用版本,
        "supportTS": "3",
        "beacon_qrsn": "qqreader-",
        "os": "android",
        "QVisible": "0",
        "qrConvertLoginType": "5",
        "themeid": "3006",
        "nosid": "1",
        "ads": "1",
        "supportmh": "1",
        "qrem": "0",
        "rcmd": "1",
        "version_code": "417",
        "ttime": timestamp,
        "qrsn_new": qrsn,
    }
    headers["beacon_qrsn_new"] = "qqreader36-"
    headers["mldt"] = _稳定QQ阅读随机标识(seed + "|mldt", 48)
    headers["dete"] = device_id
    headers["ov"] = _稳定QQ阅读随机标识(seed + "|ov", 64)
    headers["osvn"] = _稳定QQ阅读随机标识(seed + "|osvn", 16)
    headers["qrsy"] = _稳定QQ阅读随机标识(seed + "|qrsy", 32).upper()
    signed = _补充QQ阅读网关签名(headers, request_url)
    signed["csigs"] = _生成QQ阅读账号CSigs(signed)
    return signed


async def 异步构造QQ阅读账号请求头(
    timestamp_ms: int,
    request_url: str,
) -> Dict[str, str]:
    """在签名线程池构造账号接口请求头，避免阻塞事件循环。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _获取QQ阅读签名执行器(),
        contextvars.copy_context().run,
        构造QQ阅读账号请求头,
        timestamp_ms,
        request_url,
    )


def 解析QQ阅读账号会员状态(data: Any) -> dict[str, Any]:
    """解析官方 getAcctInfo 的顶层账号会员字段。"""
    不可用 = {"available": False, "is_vip": False, "vip_type": "",
              "vip_expire_at": 0, "vip_expire_text": "", "checked_at": 0}
    if not isinstance(data, dict):
        return 不可用
    code = data.get("code")
    # getAcctInfo 正常响应始终携带 code=0 与 isLogin。两项任一缺失时，
    # 不把空 JSON、网关降级页或其他接口的相似字段当作有效账号状态。
    if code in (None, "") or _安全整数(code, -1) != 0:
        return 不可用
    is_login = data.get("isLogin")
    is_guest = data.get("isGuest")
    if is_login is None or not _是真值(is_login):
        return 不可用
    if is_guest is not None and _是真值(is_guest):
        return 不可用

    vip_fields = ("vipStatus", "isVip", "isMVip")
    vip_seen = any(field in data for field in vip_fields)
    vip_value = any(_是真值(data.get(field)) for field in vip_fields)

    expiry_value = data.get("vipEndTime")
    expiry_active = False
    expiry = _安全整数(expiry_value, 0)
    if expiry:
        if expiry > 100_000_000_000:
            expiry //= 1000
        expiry_active = expiry > int(time.time())
    elif isinstance(expiry_value, str):
        # 当前 Android 客户端返回 YYYY-MM-DD。只把可解析且未过期的日期
        # 作为补充证据，vipType/vipLevel 不会单独把账号判为会员。
        for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                expiry = int(time.mktime(
                    time.strptime(expiry_value.strip(), pattern)
                ))
                if pattern == "%Y-%m-%d":
                    expiry += 24 * 60 * 60 - 1
                expiry_active = expiry >= time.time()
                break
            except (ValueError, OverflowError):
                continue
    is_vip = bool(vip_value or expiry_active)
    # vipType=2 已由账号响应核实；没有可靠枚举文档时原样显示类型编号，
    # 不将其猜成超级会员或年费会员，也不据此单独认定权益有效。
    type_value = str(data.get("vipType") or "").strip()
    type_value = "".join(char for char in type_value if ord(char) >= 32 and ord(char) != 127)[:40]
    if type_value and type_value != "0":
        vip_type = f"会员（类型 {type_value}）" if type_value.isdigit() else type_value
    else:
        vip_type = "VIP会员" if is_vip else ""
    expiry_text = ""
    if expiry > 0 and isinstance(expiry_value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?", expiry_value.strip()
    ):
        expiry_text = expiry_value.strip()
    elif expiry > 0:
        try:
            expiry_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry))
        except (ValueError, OverflowError, OSError):
            expiry_text = ""
    if not expiry_text:
        expiry_text = str(data.get("vipComment") or "").strip()[:80]
    return {
        "available": True,
        "is_vip": is_vip,
        "vip_field_seen": vip_seen,
        "expiry_active": expiry_active,
        "vip_type": vip_type,
        "vip_expire_at": max(0, expiry),
        "vip_expire_text": expiry_text,
        "checked_at": int(time.time()),
    }


def 解析QQ阅读账号资料(data: Any) -> dict[str, Any]:
    """解析 getAcctInfo 返回的账号昵称、头像和手机号。"""
    会员状态 = 解析QQ阅读账号会员状态(data)
    if not 会员状态.get("available") or not isinstance(data, dict):
        return {"available": False}
    return {
        "available": True,
        "nickname": str(data.get("nick") or data.get("nickname") or "").strip(),
        "avatar_url": str(
            data.get("icon")
            or data.get("avatar")
            or data.get("avatarUrl")
            or data.get("headUrl")
            or ""
        ).strip(),
        "phone": (
            str(data.get("mobile") or "").strip()
            if re.fullmatch(r"1\d{10}", str(data.get("mobile") or "").strip())
            else ""
        ),
        "uid": str(data.get("uid") or data.get("uin") or "").strip(),
        "vip": {键: 会员状态[键] for 键 in (
            "available", "is_vip", "vip_type", "vip_expire_at", "vip_expire_text", "checked_at"
        )},
    }


QQ阅读账号信息地址 = (
    "https://commontgw.reader.qq.com/v7_6_6/nativepage/getAcctInfo"
)


async def _请求QQ阅读账号信息(session: aiohttp.ClientSession) -> dict[str, Any] | None:
    """请求官方账号资料；调用方只读取受控字段。"""
    load_config_once()
    config = ConfigManager.get_instance()
    if not (str(config.uid or "").strip() and str(config.usid or "").strip()):
        return None
    params = {"rechargeCouponSwith": "1"}
    request_url = _构造QQ阅读请求地址(QQ阅读账号信息地址, params)
    headers = await 异步构造QQ阅读账号请求头(
        int(time.time() * 1000), request_url
    )
    try:
        async with session.get(
            QQ阅读账号信息地址,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=5, sock_connect=3, sock_read=4),
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
    except Exception as exc:
        logger.debug(f"QQ阅读账号会员查询失败：错误={type(exc).__name__}")
        return None
    return data if isinstance(data, dict) else None


async def 查询QQ阅读账号资料(
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    data = await _请求QQ阅读账号信息(session)
    资料 = 解析QQ阅读账号资料(data)
    if not 资料.get("available"):
        return 资料
    config = ConfigManager.get_instance()
    try:
        # 官方用户中心以 freeType/memberType 展示会员名称；不猜 native vipType 枚举。
        async with session.get(
            "https://book.qq.com/api/user/homepage",
            headers={"Cookie": f"ywguid={config.uid}; ywkey={config.usid};",
                     "Referer": "https://book.qq.com/user-center"},
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=5, sock_connect=3, sock_read=4),
        ) as response:
            response.raise_for_status()
            homepage = await response.json(content_type=None)
        会员名称 = 解析QQ阅读官网会员名称(homepage)
        if 会员名称:
            资料["vip"]["vip_type"] = 会员名称
    except Exception as exc:
        logger.debug("QQ阅读官网会员类型补查失败：错误类型=%s", type(exc).__name__)
    return 资料


def 解析QQ阅读官网会员名称(响应: Any) -> str:
    if not isinstance(响应, dict) or str(响应.get("code")) != "0":
        return ""
    data = 响应.get("data")
    if not isinstance(data, dict):
        return ""
    if _是真值(data.get("freeType")):
        return "体验会员"
    member_type = _安全整数(data.get("memberType"), 0)
    if member_type > 0:
        return "付费会员·年费" if member_type > 1 else "付费会员"
    return ""


async def 查询QQ阅读账号VIP状态(
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    """通过官方账号接口判断当前登录态是否有有效会员。"""
    result = 解析QQ阅读账号会员状态(await _请求QQ阅读账号信息(session))
    if not result.get("available"):
        logger.debug("QQ阅读账号会员查询未返回有效登录态")
    return result


def _提取QQ阅读章节号(value: str) -> int:
    first = value.find("_")
    second = value.find("_", first + 1)
    if first < 0 or second < 0:
        raise ValueError("章节文件名无效")
    return int(value[first + 1 : second])


def 获取QQ阅读正文章节ID列表(
    catalog: list[dict[str, Any]],
    start_chapter: int,
    end_chapter: int,
) -> list[str]:
    """把过滤后的目录位置转换回正文接口需要的真实 cid。"""
    start = max(1, int(start_chapter))
    end = max(start, int(end_chapter))
    chapter_ids: list[str] = []
    for position in range(start, end + 1):
        item = catalog[position - 1] if position <= len(catalog) else {}
        chapter_id = str(item.get("cid") or position).strip()
        chapter_ids.append(chapter_id if chapter_id.isdigit() else str(position))
    return chapter_ids


def 构造QQ阅读正文章节参数(chapter_ids: list[str]) -> str:
    normalized = [
        str(chapter_id).strip() for chapter_id in chapter_ids if str(chapter_id).strip()
    ]
    if not normalized:
        return ""
    numbers = [int(chapter_id) for chapter_id in normalized if chapter_id.isdigit()]
    if len(numbers) == len(normalized) and all(
        current == numbers[0] + offset for offset, current in enumerate(numbers)
    ):
        return f"{numbers[0]}-{numbers[-1]}"
    return ",".join(normalized)


def 解密QQ阅读章节数据(
    data: bytes,
    stt: str | bytes,
    *,
    allow_refresh: bool = True,
    解密材料: tuple[bytes, bytes, bytes] | None = None,
) -> Optional[str]:
    config = ConfigManager.get_instance()
    if not config.key_pool:
        return None
    try:
        if 解密材料 is None:
            解密材料 = config.获取解密材料()
        knva, aes_key, pool_decrypted = 解密材料
        text = try_decrypt_chapter(
            data,
            stt,
            config.fuid,
            config.key_pool,
            knva,
            aes_key=aes_key,
            pool_decrypted=pool_decrypted,
        )
    except Exception:
        text = None
    if text is None and allow_refresh:
        # 网络刷新由异步下载调度器统一处理，避免解密工作线程阻塞在 HTTP 请求上。
        logger.debug("QQ阅读章节解密未命中当前密钥池")
    return text.decode("utf-8", "replace") if text else None


def _展开QQ阅读正文信息(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _展开QQ阅读正文信息(item)
        return
    if not isinstance(value, dict):
        return
    if any(key in value for key in ("chapter_id", "chapterId", "cid", "scid")):
        yield value
    for key in ("items", "data", "list", "chapters"):
        nested = value.get(key)
        if isinstance(nested, (dict, list)):
            yield from _展开QQ阅读正文信息(nested)


def _解析QQ阅读正文信息(members: dict[str, object]) -> dict[str, str]:
    """从正文包 info 文件建立真实章节 ID 与 UUID 的映射。"""
    mapping: dict[str, str] = {}
    for name, raw in members.items():
        normalized_name = str(name).replace("\\", "/").lower()
        if not normalized_name.endswith(("info.txt", "info.json")):
            continue
        if not isinstance(raw, (bytes, bytearray)):
            continue
        try:
            payload = json.loads(bytes(raw).decode("utf-8-sig", "replace"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for item in _展开QQ阅读正文信息(payload):
            chapter_id = str(
                item.get("chapter_id")
                or item.get("chapterId")
                or item.get("cid")
                or item.get("scid")
                or ""
            ).strip()
            if not chapter_id:
                continue
            for key in (
                chapter_id,
                item.get("chapter_uuid"),
                item.get("chapterUuid"),
                item.get("uuid"),
            ):
                normalized_key = str(key or "").strip()
                if normalized_key:
                    mapping[normalized_key] = chapter_id
    return mapping


def _QQ阅读章节文件候选键(name: str) -> list[str]:
    normalized = str(name).replace("\\", "/").rsplit("/", 1)[-1]
    values = [normalized]
    if normalized.endswith("_s"):
        stem = normalized[:-2]
        values.append(stem)
        if "_" in stem:
            values.append(stem.rsplit("_", 1)[-1])
    return values


def _匹配QQ阅读正文章节文件(
    members: dict[str, object],
    requested_ids: list[str],
) -> dict[str, tuple[str, object]]:
    requested_set = set(requested_ids)
    info_mapping = _解析QQ阅读正文信息(members)
    matched: dict[str, tuple[str, object]] = {}

    for name, value in members.items():
        normalized_name = str(name).replace("\\", "/").lower()
        if normalized_name.endswith(("info.txt", "info.json")) or name == "code":
            continue
        chapter_id = ""
        候选键 = _QQ阅读章节文件候选键(str(name))
        # 官方正文包的数字文件名是实际章节号；info.txt 的 UUID 可能跨章节重复，
        # 因此必须先使用文件名中的目录 ID，避免把第 1 章映射到其他章节。
        for candidate in 候选键:
            if candidate.isdigit() and candidate in requested_set:
                chapter_id = candidate
                break
        if chapter_id:
            if chapter_id not in matched:
                matched[chapter_id] = (str(name), value)
            continue
        for candidate in 候选键:
            target = info_mapping.get(candidate) or (
                candidate if candidate in requested_set else ""
            )
            if target in requested_set:
                chapter_id = target
                break
        if not chapter_id:
            try:
                legacy_id = str(_提取QQ阅读章节号(str(name)))
            except (TypeError, ValueError):
                legacy_id = ""
            if legacy_id in requested_set:
                chapter_id = legacy_id
        if chapter_id and chapter_id not in matched:
            matched[chapter_id] = (str(name), value)
    return matched


def _规范QQ阅读正文业务码(value: Any) -> str:
    normalized = str(value if value is not None else "").strip()
    digits = normalized[1:] if normalized.startswith("-") else normalized
    return normalized if digits.isascii() and digits.isdigit() and len(digits) <= 20 else ""


class _QQ阅读正文响应错误(RuntimeError):
    """只携带受控分类，不把正文接口原文放进异常或日志。"""

    def __init__(
        self,
        category: str,
        *,
        http_status: int = 0,
        code: Any = "",
    ) -> None:
        super().__init__("正文响应处理失败")
        self.category = (
            category
            if category in {"响应包无效", "响应缺失", "接口业务失败"}
            else "响应包无效"
        )
        self.http_status = (
            http_status
            if isinstance(http_status, int) and 100 <= http_status <= 599
            else 0
        )
        self.code = _规范QQ阅读正文业务码(code)


def _检查QQ阅读正文响应(package: bytes, http_status: int = 0) -> None:
    """HTTP 成功仍须排除空响应和非正文错误页；不记录响应原文。"""
    sample = package.lstrip(b"\xef\xbb\xbf \t\r\n")
    if not sample:
        raise _QQ阅读正文响应错误("响应包无效", http_status=http_status)
    if sample.startswith((b"{", b"[")):
        code: Any = ""
        if len(sample) <= 1024 * 1024:
            try:
                payload = json.loads(sample)
            except (UnicodeError, ValueError, TypeError):
                payload = None
            if isinstance(payload, dict):
                for key in ("code", "ret", "retcode", "errcode", "error_code"):
                    normalized = _规范QQ阅读正文业务码(payload.get(key))
                    if normalized:
                        code = normalized
                        break
        raise _QQ阅读正文响应错误("响应包无效", http_status=http_status, code=code)
    lowered = sample[:512].lower()
    if lowered.startswith((b"<!doctype", b"<html", b"<head", b"<body", b"<?xml")):
        raise _QQ阅读正文响应错误("响应包无效", http_status=http_status)


def _QQ阅读正文项失败原因(value: Any) -> str:
    if isinstance(value, _QQ阅读正文响应错误):
        return value.category
    if value is None or value == "章节响应缺失":
        return "响应缺失"
    if value == "章节解密失败":
        return "解密失败"
    if isinstance(value, bytes):
        return "" if value.decode("utf-8", "replace").strip() else "实际空正文"
    return "" if str(value).strip() else "实际空正文"


def _解析QQ阅读正文章节业务失败(
    members: dict[str, object], requested_ids: list[str]
) -> dict[str, str]:
    """仅把 info 中与本次真实 cid 一致的非零业务码用于缺失诊断。"""
    requested_set = set(requested_ids)
    failures: dict[str, str] = {}
    for name, raw in members.items():
        normalized_name = str(name).replace("\\", "/").lower()
        if not normalized_name.endswith(("info.txt", "info.json")):
            continue
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > 1024 * 1024:
            continue
        try:
            payload = json.loads(bytes(raw).decode("utf-8-sig", "replace"))
        except (TypeError, ValueError):
            continue
        for item in _展开QQ阅读正文信息(payload):
            chapter_id = str(
                item.get("chapter_id")
                or item.get("chapterId")
                or item.get("cid")
                or item.get("scid")
                or ""
            ).strip()
            if chapter_id not in requested_set:
                continue
            code = _规范QQ阅读正文业务码(item.get("code"))
            if code and int(code) != 0:
                failures[chapter_id] = code
    return failures


def 解析QQ阅读正文批次(
    package: bytes,
    chapter_ids: list[str],
) -> list[Any]:
    result, _, _ = 解析QQ阅读正文批次带统计(package, chapter_ids)
    return result


def 解析QQ阅读正文批次带统计(
    package: bytes,
    chapter_ids: list[str],
    解密材料: tuple[bytes, bytes, bytes] | None = None,
) -> tuple[list[Any], int, int]:
    """解析正文包，并返回实际匹配数和解密失败数。"""
    _检查QQ阅读正文响应(package)
    members = tar_decrypt(package)
    if members.get("code") != 0:
        raise _QQ阅读正文响应错误("响应包无效")
    requested_ids = [
        str(chapter_id).strip() for chapter_id in chapter_ids if str(chapter_id).strip()
    ]
    if 解密材料 is None:
        try:
            解密材料 = ConfigManager.get_instance().获取解密材料()
        except Exception:
            解密材料 = None
    chapter_map: Dict[str, Any] = {}
    for chapter_id, (name, value) in _匹配QQ阅读正文章节文件(
        members, requested_ids
    ).items():
        if isinstance(value, (bytes, bytearray)):
            try:
                text = 解密QQ阅读章节数据(
                    bytes(value),
                    name,
                    allow_refresh=False,
                    解密材料=解密材料,
                )
            except Exception as exc:
                logger.debug(f"QQ阅读参考正文解密失败：错误={type(exc).__name__}")
                text = None
            value = text if text else "章节解密失败"
        elif not isinstance(value, str):
            value = str(value)
        current = chapter_map.get(chapter_id)
        if current is None or current == "章节解密失败":
            chapter_map[chapter_id] = value
    business_failures = _解析QQ阅读正文章节业务失败(members, requested_ids)
    result: list[Any] = []
    for chapter_id in requested_ids:
        value = chapter_map.get(chapter_id, "章节响应缺失")
        if _QQ阅读正文项失败原因(value) and chapter_id in business_failures:
            value = _QQ阅读正文响应错误(
                "接口业务失败", code=business_failures[chapter_id]
            )
        result.append(value)
    decrypt_failed = sum(1 for value in chapter_map.values() if value == "章节解密失败")
    return result, len(chapter_map), decrypt_failed


def QQ阅读失败章节窗口(chapter_numbers: list[int]) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    for chapter_number in sorted(set(chapter_numbers)):
        if not windows:
            windows.append((chapter_number, chapter_number))
            continue
        start, end = windows[-1]
        if (
            chapter_number == end + 1
            and chapter_number - start < QQ阅读失败章节重试窗口
        ):
            windows[-1] = (start, chapter_number)
        else:
            windows.append((chapter_number, chapter_number))
    return windows


# === published TEB/eqct ===
TEA_KEY_STR = "*#_!U@!#.)xDK02L"
API_AUTH = "https://bookcommon.reader.qq.com/auth"


def tea_key_ints(device: str, tea_key: str = TEA_KEY_STR) -> list[int]:
    dig = hashlib.md5((device + tea_key).encode("utf-8")).digest()
    return list(struct.unpack("<iiii", dig))


def tea_key_default(tea_key: str = TEA_KEY_STR) -> list[int]:
    b = tea_key.encode("utf-8")
    if len(b) < 16:
        b = b.ljust(16, b"\0")
    return list(struct.unpack("<iiii", b[:16]))


def tea_decrypt_block(block: bytes, key_ints, rounds: int = 16) -> bytes:
    v0, v1 = struct.unpack("<ii", block)
    k0, k1, k2, k3 = [_i32(x) for x in key_ints]
    summ = _i32(rounds * (-1640531527))
    for _ in range(rounds):
        v1 = _i32(
            v1
            - _i32(
                _i32(_i32(v0 << 4) + k2) ^ _i32(v0 + summ) ^ _i32(_i32(v0 >> 5) + k3)
            )
        )
        v0 = _i32(
            v0
            - _i32(
                _i32(_i32(v1 << 4) + k0) ^ _i32(v1 + summ) ^ _i32(_i32(v1 >> 5) + k1)
            )
        )
        summ = _i32(summ - (-1640531527))
    return struct.pack("<ii", v0, v1)


def tea_decrypt_bytes(data: bytes, key_ints) -> bytes:
    padn = len(data) % 8
    total = len(data) + (8 - padn if padn else 0)
    buf = bytearray(total)
    buf[: len(data)] = data
    for i in range(0, total, 8):
        buf[i : i + 8] = tea_decrypt_block(bytes(buf[i : i + 8]), key_ints)
    return bytes(buf[: len(data)])


def tea_decrypt_head128(data: bytes, key_ints=None) -> bytes:
    if key_ints is None:
        key_ints = tea_key_default()
    n = min(128, len(data))
    head = bytearray(data[:n])
    if len(head) % 8:
        head += b"\0" * (8 - (len(head) % 8))
    out = bytearray(len(head))
    for off in range(0, len(head), 8):
        out[off : off + 8] = tea_decrypt_block(bytes(head[off : off + 8]), key_ints)
    return bytes(out[:n]) + data[n:]


def strip_epu_trailer(data: bytes) -> bytes:
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        return data
    comment_len = struct.unpack_from("<H", data, eocd + 20)[0]
    return data[: eocd + 22 + comment_len]


_CRCTAB = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xEDB88320 if (_c & 1) else (_c >> 1)
    _CRCTAB.append(_c)


def _crc32_byte(crc: int, b: int) -> int:
    return (_CRCTAB[(crc ^ (b & 0xFF)) & 0xFF] ^ (crc >> 8)) & 0xFFFFFFFF


class ZipCrypto:
    def __init__(self, pwd: bytes):
        self.k = [305419896, 591751049, 878082192]
        for value in pwd:
            self.update(value)

    def update(self, b: int) -> None:
        self.k[0] = _crc32_byte(self.k[0], b)
        self.k[1] = (self.k[1] + (self.k[0] & 0xFF)) & 0xFFFFFFFF
        self.k[1] = (self.k[1] * 134775813 + 1) & 0xFFFFFFFF
        self.k[2] = _crc32_byte(self.k[2], (self.k[1] >> 24) & 0xFF)

    def dec_byte(self) -> int:
        t = (self.k[2] | 2) & 0xFFFFFFFF
        return ((t * (t ^ 1)) >> 8) & 0xFF

    def decrypt(self, data: bytes) -> bytes:
        out = bytearray(len(data))
        for index, value in enumerate(data):
            plain = value ^ self.dec_byte()
            self.update(plain)
            out[index] = plain
        return bytes(out)


def extract_zip_entries(zdata: bytes, pwd: bytes) -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(zdata)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            header_offset = entry.header_offset
            if header_offset < 0 or header_offset + 30 > len(zdata):
                raise zipfile.BadZipFile("invalid local header offset")
            header = struct.unpack_from("<4s2B4HL2L2H", zdata, header_offset)
            if header[0] != b"PK\x03\x04":
                raise zipfile.BadZipFile("invalid local header signature")
            data_offset = header_offset + 30 + header[10] + header[11]
            data_end = data_offset + entry.compress_size
            if data_end > len(zdata):
                raise zipfile.BadZipFile("truncated ZIP entry")
            payload = zdata[data_offset:data_end]
            if entry.flag_bits & 1:
                if not pwd:
                    raise RuntimeError("ZIP password missing")
                if len(payload) < 12:
                    raise zipfile.BadZipFile("encrypted ZIP entry is too short")
                # QQ阅读的加密头校验字节不总符合标准；校验解密后的 CRC。
                payload = ZipCrypto(pwd).decrypt(payload)[12:]
            if entry.compress_type == zipfile.ZIP_STORED:
                plain = payload
            elif entry.compress_type == zipfile.ZIP_DEFLATED:
                plain = zlib.decompress(payload, -15)
            else:
                raise NotImplementedError("unsupported ZIP compression")
            if len(plain) != entry.file_size:
                raise zipfile.BadZipFile("ZIP entry size mismatch")
            if zlib.crc32(plain) & 0xFFFFFFFF != entry.CRC:
                raise zipfile.BadZipFile("ZIP entry CRC mismatch")
            entries.append((entry.filename, plain))
    return entries


def extract_eqct(eqct: bytes, pwd: bytes) -> list[tuple[str, bytes]]:
    if len(eqct) < 128:
        raise ValueError("TEA head decrypt failed: QTEB resource too short")
    decrypted = tea_decrypt_head128(eqct)
    if len(decrypted) >= 168:
        decrypted = decrypted[:-40]
    start = decrypted.find(b"PK\x03\x04")
    if start < 0:
        raise ValueError(f"TEA head decrypt failed head={decrypted[:8].hex()}")
    zdata = strip_epu_trailer(decrypted[start:])
    return extract_zip_entries(zdata, pwd)


def xhtml_to_text(data: bytes) -> str:
    text = data.decode("utf-8", "replace")
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", "", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = html.unescape(text).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _规范出版书资源路径(path: str) -> str:
    segments: list[str] = []
    for segment in str(path or "").replace("\\", "/").split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    return "/".join(segments)


def _查找出版书资源(
    resources: dict[str, tuple[str, bytes]],
    target: str,
) -> tuple[str, bytes] | None:
    normalized_target = _规范出版书资源路径(target)
    if normalized_target in resources:
        return resources[normalized_target]
    for name, resource in resources.items():
        if name.endswith(f"/{normalized_target}") or normalized_target.endswith(
            f"/{name}"
        ):
            return resource
    return None


def _获取出版书OPF顺序(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    resources = {
        _规范出版书资源路径(name): (name, data)
        for name, data in files
        if _规范出版书资源路径(name)
    }
    container = next(
        (
            resource
            for name, resource in resources.items()
            if name.lower() == "meta-inf/container.xml"
        ),
        None,
    )
    if container is None:
        return []
    try:
        container_root = ET.fromstring(container[1])
        rootfile = next(
            (
                element.attrib.get("full-path", "")
                for element in container_root.iter()
                if element.tag.rsplit("}", 1)[-1].lower() == "rootfile"
            ),
            "",
        )
        opf_resource = _查找出版书资源(resources, rootfile)
        if opf_resource is None:
            return []
        opf_path = _规范出版书资源路径(rootfile)
        opf_root = ET.fromstring(opf_resource[1])
    except (ET.ParseError, ValueError, TypeError):
        return []

    manifest: dict[str, str] = {}
    spine_ids: list[str] = []
    for element in opf_root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag == "item":
            item_id = str(element.attrib.get("id") or "").strip()
            href = str(element.attrib.get("href") or "").strip()
            if item_id and href:
                parent = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
                manifest[item_id] = _规范出版书资源路径(f"{parent}/{href}")
        elif tag == "itemref":
            item_id = str(element.attrib.get("idref") or "").strip()
            if item_id:
                spine_ids.append(item_id)

    ordered: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for item_id in spine_ids:
        resource = _查找出版书资源(resources, manifest.get(item_id, ""))
        if resource is None:
            continue
        normalized = _规范出版书资源路径(resource[0])
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(resource)
    return ordered


def 合并参考出版书正文(files: list[tuple[str, bytes]]) -> str:
    ordered = _获取出版书OPF顺序(files)
    if not ordered:
        ordered = sorted(files, key=lambda item: _规范出版书资源路径(item[0]).lower())
    texts: list[str] = []
    for name, data in ordered:
        lower = _规范出版书资源路径(name).lower()
        if lower.endswith((".xhtml", ".html", ".htm")):
            text = xhtml_to_text(data)
        elif lower.endswith(".txt"):
            text = data.decode("utf-8", "replace").strip()
        else:
            continue
        if text:
            texts.append(text)
    return "\n\n".join(texts)


def _parse_teb_info_blob(blob: bytes) -> list[dict]:
    if not blob:
        return []
    if blob[:1] == b"{":
        obj = json.loads(blob.decode("utf-8", "replace"))
        raise RuntimeError(f"TEB error: {obj}")
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
        raw = tf.extractfile(tf.getmember("info.txt")).read()
    info = json.loads(raw.decode("utf-8"))
    if isinstance(info, list):
        return [x for x in info if isinstance(x, dict)]
    if isinstance(info, dict):
        return [info]
    return []


# === AstrBot adapter ===

QQ阅读详情地址 = "https://commontgw.reader.qq.com/book/queryBookInfo"
QQ阅读目录地址 = "https://newminerva-tgw.reader.qq.com/ChapBatAuthWithPD"
QQ阅读搜索地址 = "https://newzxsearch.reader.qq.com/v7_5_1/search"
QQ阅读第三方正文地址 = "http://154.12.91.167:7000/content"
# 每批固定 25 章，避免第三方服务对大范围请求截断；整本按连续区间分段并发完成。
QQ阅读第三方正文批量章节数 = 25
QQ阅读第三方正文最大动态并发数 = 16
QQ阅读进度日志分段数 = 4
QQ阅读链接正则 = re.compile(r"https?://[^\s'\"<>，。]+", re.I)
QQ阅读允许域名 = ("reader.qq.com", "book.qq.com")
QQ阅读KOL短链路径正则 = re.compile(r"^/kol-rec/[A-Za-z0-9_-]{6,128}/?$", re.I)
QQ阅读KOL短链书籍编号正则 = re.compile(
    r"(?:\bbookData|\"bookData\")\s*:\s*\{[^{}]{0,2048}?"
    r"(?:\bbid|\"bid\")\s*:\s*[\"']?(\d+)",
    re.I,
)
QQ阅读登录态命名空间 = "qq_reader_auth"
QQ阅读登录态状态键 = "login_state"
_QQ阅读账号状态锁 = globals().get("_QQ阅读账号状态锁") or threading.RLock()
小说缓存目录 = 文件缓存工具.小说缓存目录
文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。"
    "如喜欢本书，请支持正版。"
)
下载失败提示 = "下载失败"
文件发送失败提示 = "文件发送失败，请稍后再试"
章节单独付费提示 = "没有可下载的免费章节"


def _是QQ阅读域名(hostname: str) -> bool:
    host = str(hostname or "").lower().strip(".")
    return any(
        host == domain or host.endswith(f".{domain}") for domain in QQ阅读允许域名
    )


def 提取QQ阅读链接(文本: Any) -> str | None:
    文本值 = html.unescape(str(文本 or "")).replace("\\/", "/")
    for match in QQ阅读链接正则.finditer(文本值):
        link = match.group(0).rstrip(")]}>，。；;！!")
        try:
            if _是QQ阅读域名(urlsplit(link).hostname or ""):
                return link
        except ValueError:
            continue
    return None


def _读取QQ阅读字段(对象: Any, 字段名: str) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def _遍历QQ阅读卡片数据(根对象: Any) -> Iterator[str]:
    """只遍历消息原始数据和卡片常见嵌套字段，避免把对象 repr 当作消息文本。"""
    待处理: list[tuple[Any, int]] = [(根对象, 0)]
    已访问: set[int] = set()
    处理数量 = 0
    while 待处理 and 处理数量 < 2048:
        当前, 深度 = 待处理.pop()
        if 当前 is None or 深度 > 8:
            continue
        if isinstance(当前, (dict, list, tuple)) or not isinstance(
            当前, (str, bytes, int, float, bool)
        ):
            对象编号 = id(当前)
            if 对象编号 in 已访问:
                continue
            已访问.add(对象编号)
        处理数量 += 1

        if isinstance(当前, str):
            yield 当前
            文本 = 当前.strip()
            if 文本[:1] in {"{", "["}:
                try:
                    待处理.append((json.loads(文本), 深度 + 1))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
            continue
        if isinstance(当前, bytes):
            continue
        if isinstance(当前, dict):
            待处理.extend((值, 深度 + 1) for 值 in 当前.values())
            continue
        if isinstance(当前, (list, tuple)):
            待处理.extend((值, 深度 + 1) for 值 in 当前)
            continue

        for 字段名 in (
            "raw_data",
            "msg_elements",
            "raw_message",
            "message",
            "data",
            "payload",
            "event",
            "content",
            "extra",
        ):
            值 = _读取QQ阅读字段(当前, 字段名)
            if 值 is not None:
                待处理.append((值, 深度 + 1))


def 提取QQ阅读事件链接(event: Any) -> str | None:
    候选对象 = [
        event,
        _读取QQ阅读字段(event, "message_obj"),
        _读取QQ阅读字段(event, "raw_message"),
        _读取QQ阅读字段(event, "message"),
    ]
    for 对象 in 候选对象:
        if 对象 is None:
            continue
        for 值 in _遍历QQ阅读卡片数据(对象):
            link = 提取QQ阅读链接(值)
            if link is not None:
                return link
    return None


def 识别QQ阅读Cookie文本(文本: Any) -> bool:
    raw = str(文本 or "")
    if re.search(r"\byw(?:guid|key)\b", raw, re.I):
        return True
    # QQ 阅读 Android 原始请求使用 uid/usid 命名。仅同时出现两项时接收，
    # 避免把普通消息里的单个 uid 当作登录态。
    return bool(
        re.search(r"(?:^|[;\r\n])\s*uid\s*[:=]", raw, re.I)
        and re.search(r"(?:^|[;\r\n])\s*usid\s*[:=]", raw, re.I)
    )


def _从CookieJSON提取(data: Any, result: dict[str, str]) -> None:
    if isinstance(data, list):
        for item in data:
            _从CookieJSON提取(item, result)
        return
    if not isinstance(data, dict):
        return
    aliases = {
        "ywguid": "ywguid",
        "ywkey": "ywkey",
        "uid": "ywguid",
        "usid": "ywkey",
    }
    name = str(data.get("name") or "").strip().lower()
    canonical_name = aliases.get(name)
    if canonical_name and data.get("value") is not None:
        result[canonical_name] = str(data["value"]).strip()
    for key, value in data.items():
        lowered = str(key).strip().lower()
        canonical_name = aliases.get(lowered)
        if canonical_name and isinstance(value, (str, int)):
            result[canonical_name] = str(value).strip()
        elif isinstance(value, (dict, list)):
            _从CookieJSON提取(value, result)


def 解析QQ阅读Cookie(文本: Any) -> dict[str, str] | None:
    raw = str(文本 or "").strip()
    if not raw:
        return None
    result: dict[str, str] = {}
    try:
        _从CookieJSON提取(json.loads(raw), result)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    for line in raw.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 7 and parts[5].strip().lower() in {"ywguid", "ywkey"}:
            result[parts[5].strip().lower()] = parts[6].strip()
    for name, canonical_name in (
        ("ywguid", "ywguid"),
        ("ywkey", "ywkey"),
        ("uid", "ywguid"),
        ("usid", "ywkey"),
    ):
        match = re.search(
            rf"(?:^|[;\s'\"`]){name}\s*[:=]\s*([^;\s'\"`]+)",
            raw,
            re.I,
        )
        if match:
            result[canonical_name] = match.group(1).strip()
    ywguid = result.get("ywguid", "")
    ywkey = result.get("ywkey", "")
    if not re.fullmatch(r"\d{6,32}", ywguid):
        return None
    if not re.fullmatch(r"[^\s;,\"']{6,256}", ywkey):
        return None
    return {"ywguid": ywguid, "ywkey": ywkey}


def _是QQ阅读通用分享链接(来源: Any) -> bool:
    link = 提取QQ阅读链接(来源)
    if not link:
        return False
    try:
        parsed = urlsplit(link)
        return (
            parsed.scheme == "https"
            and (parsed.hostname or "").lower() == "ih5.reader.qq.com"
            and parsed.path.rstrip("/").lower() == "/h5/share/bookshare"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


def 提取QQ阅读分享书名(文本: Any, 来源: Any) -> str:
    """只关联同段官方分享文案里的书名和当前通用链接。"""
    if not isinstance(文本, str) or not _是QQ阅读通用分享链接(来源):
        return ""
    link = 提取QQ阅读链接(来源)
    text = html.unescape(文本).replace("\\/", "/")
    标题集: set[str] = set()
    for match in re.finditer(
        r"我正在用\s*QQ阅读\s*看一本书\s*《([^《》\r\n]{1,120})》"
        r"\s*[，,]\s*觉得不错\s*[，,]\s*与大家一起分享[。.!！]?\s*"
        r"(https?://[^\s<>\"']+)",
        text,
        re.I,
    ):
        if 提取QQ阅读链接(match.group(2)) != link:
            continue
        title = match.group(1).strip()
        if title and all(ord(char) >= 32 and ord(char) != 127 for char in title):
            标题集.add(title)
    return next(iter(标题集)) if len(标题集) == 1 else ""


def _清理QQ阅读搜索文本(文本: Any) -> str:
    """去除官方搜索响应里的 em 高亮标签，保留书名标点和副标题。"""
    return re.sub(r"</?em\s*>", "", html.unescape(str(文本 or "")), flags=re.I).strip()


def _规范QQ阅读书名(文本: Any) -> str:
    return "".join(unicodedata.normalize("NFKC", _清理QQ阅读搜索文本(文本)).split())


async def 按QQ阅读分享书名解析编号(标题: str) -> str:
    """完整书名匹配且唯一时才恢复缺失的编号，不采用相似结果。"""
    标准书名 = _规范QQ阅读书名(标题)
    if not 标准书名:
        return ""
    try:
        结果 = await asyncio.wait_for(搜索小说(标题, 需要数量=30), timeout=30)
    except Exception as exc:
        logger.warning("QQ阅读分享书名补全失败：错误类型=%s", type(exc).__name__)
        return ""
    候选编号 = {
        str(项.get("book_id") or "")
        for 项 in 结果
        if isinstance(项, dict)
        and str(项.get("book_id") or "").isdigit()
        and _规范QQ阅读书名(项.get("title")) == 标准书名
    }
    return next(iter(候选编号)) if len(候选编号) == 1 else ""


def 解析书籍编号(来源: Any) -> str:
    link = 提取QQ阅读链接(来源) or str(来源 or "").strip()
    try:
        parsed = urlsplit(link)
        query = parse_qs(parsed.query)
        for key in ("bid", "bookid", "bookId", "book_id"):
            for value in query.get(key, []):
                if str(value).isdigit():
                    return str(value)
        path = parsed.path
    except ValueError:
        path = link
    for pattern in (
        r"/book-detail/(\d+)(?:/|$)",
        r"/book/(\d+)(?:\.html)?(?:/|$)",
        r"/(\d+)(?:\.html)?(?:/|$)",
    ):
        match = re.search(pattern, path, re.I)
        if match:
            return match.group(1)
    return ""


async def 解析QQ阅读分享页书籍编号(
    来源: Any,
    session: aiohttp.ClientSession,
) -> str:
    link = 提取QQ阅读链接(来源)
    if not link:
        return ""
    try:
        parsed = urlsplit(link)
    except ValueError:
        return ""
    if (
        (parsed.hostname or "").lower() != "book.qq.com"
        or not QQ阅读KOL短链路径正则.fullmatch(parsed.path)
    ):
        return ""

    page_url = link
    page_source = ""
    for _ in range(4):
        async with session.get(page_url, allow_redirects=False) as response:
            if response.status in {301, 302, 303, 307, 308}:
                location = str(response.headers.get("Location") or "").strip()
                if not location:
                    raise RuntimeError("QQ阅读分享页重定向缺少目标地址")
                next_url = urljoin(page_url, location)
                next_parsed = urlsplit(next_url)
                if (
                    next_parsed.scheme != "https"
                    or not _是QQ阅读域名(next_parsed.hostname or "")
                ):
                    raise RuntimeError("QQ阅读分享页跳转地址无效")
                page_url = next_url
                continue
            response.raise_for_status()
            page_source = await response.text()
            break
    else:
        raise RuntimeError("QQ阅读分享页跳转次数过多")

    match = QQ阅读KOL短链书籍编号正则.search(page_source)
    return str(match.group(1)) if match else ""


def 初始化参考核心() -> ConfigManager:
    load_config_once()
    return ConfigManager.get_instance()


def _应用QQ阅读登录态(登录态: dict[str, str]) -> None:
    """兼容旧调用；只更新调用方已绑定的账号上下文。"""
    config = _QQ阅读配置上下文.get()
    if config is not None:
        config.uid = 登录态["ywguid"]
        config.usid = 登录态["ywkey"]


def _解析QQ阅读账号项(数据: Any) -> dict[str, Any] | None:
    if not isinstance(数据, dict):
        return None
    凭据 = 解析QQ阅读Cookie(json.dumps({
        "ywguid": 数据.get("ywguid") or 数据.get("uid") or "",
        "ywkey": 数据.get("ywkey") or 数据.get("usid") or "",
    }))
    if not 凭据:
        return None
    账号ID = "qr_" + hashlib.sha256(凭据["ywguid"].encode("ascii")).hexdigest()[:20]
    资料 = 数据.get("profile") if isinstance(数据.get("profile"), dict) else 数据
    vip = 资料.get("vip") if isinstance(资料.get("vip"), dict) else {}
    return {
        "id": 账号ID,
        **凭据,
        "enabled": 数据.get("enabled") is not False,
        "nickname": str(资料.get("nickname") or "")[:120],
        "avatar_url": str(资料.get("avatar_url") or "")[:2048],
        "phone": str(资料.get("phone") or "")[:32],
        "updated_at": max(0, _安全整数(数据.get("updated_at"), 0)),
        "profile_updated_at": max(0, _安全整数(数据.get("profile_updated_at"), 0)),
        "vip": {
            "available": vip.get("available") is True,
            "is_vip": vip.get("is_vip") is True,
            "vip_type": str(vip.get("vip_type") or "")[:80],
            "vip_expire_at": max(0, _安全整数(vip.get("vip_expire_at"), 0)),
            "vip_expire_text": str(vip.get("vip_expire_text") or "")[:80],
            "checked_at": max(0, _安全整数(vip.get("checked_at"), 0)),
        },
    }


def _读取QQ阅读账号状态(配置: Any) -> dict[str, Any]:
    raw = 读取运行状态值(配置, QQ阅读登录态命名空间, QQ阅读登录态状态键, "")
    if not raw:
        return {"version": 2, "selected_id": "", "accounts": []}
    try:
        数据 = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("QQ阅读账号状态无效") from exc
    if not isinstance(数据, dict):
        raise ValueError("QQ阅读账号状态无效")
    原项 = 数据.get("accounts") if "accounts" in 数据 else [数据]
    if not isinstance(原项, list):
        raise ValueError("QQ阅读账号列表无效")
    账号项: dict[str, dict[str, Any]] = {}
    for 项 in 原项:
        已解析 = _解析QQ阅读账号项(项)
        if 已解析:
            账号项[已解析["id"]] = 已解析
    选中ID = str(数据.get("selected_id") or "")
    if not (选中ID in 账号项 and 账号项[选中ID]["enabled"]):
        选中ID = next((项["id"] for 项 in 账号项.values() if 项["enabled"]), "")
    return {"version": 2, "selected_id": 选中ID, "accounts": list(账号项.values())}


def _写入QQ阅读账号状态(配置: Any, 状态: dict[str, Any]) -> None:
    if not 已配置运行状态数据库(配置):
        raise ValueError("数据库未配置")
    写入运行状态值(
        配置, QQ阅读登录态命名空间, QQ阅读登录态状态键,
        json.dumps(状态, ensure_ascii=True, separators=(",", ":")),
    )


def _QQ阅读账号摘要(状态: dict[str, Any]) -> dict[str, Any]:
    列表 = []
    for 账号 in 状态["accounts"]:
        资料 = {键: 值 for 键, 值 in 账号.items() if 键 != "ywkey"}
        资料["vip"] = dict(账号["vip"])
        资料["selected"] = 账号["id"] == 状态["selected_id"]
        if not 资料["nickname"]:
            资料["nickname"] = "书友_" + 账号["ywguid"][-6:]
        if not 资料["avatar_url"]:
            资料["avatar_url"] = (
                "https://shp.qpic.cn/qqreader_f/0/" + 账号["ywguid"] + "/136"
            )
        列表.append(资料)
    return {"configured": bool(状态["selected_id"]),
            "selected_id": 状态["selected_id"], "accounts": 列表}


def 读取QQ阅读账号列表(配置: Any) -> dict[str, Any]:
    with _QQ阅读账号状态锁:
        return _QQ阅读账号摘要(_读取QQ阅读账号状态(配置))


def 读取QQ阅读账号凭据(配置: Any, 账号ID: str = "") -> dict[str, Any] | None:
    with _QQ阅读账号状态锁:
        状态 = _读取QQ阅读账号状态(配置)
        目标 = str(账号ID or 状态["selected_id"])
        for 项 in 状态["accounts"]:
            if 项["id"] == 目标:
                return {"id": 项["id"], "ywguid": 项["ywguid"], "ywkey": 项["ywkey"]}
    return None


def 保存QQ阅读账号(
    配置: Any, 登录态: dict[str, Any], 账号ID: str = "", 设为当前: bool = True,
) -> dict[str, Any]:
    凭据 = _解析QQ阅读账号项(登录态)
    if not 凭据:
        raise ValueError("QQ阅读登录态格式无效")
    with _QQ阅读账号状态锁:
        状态 = _读取QQ阅读账号状态(配置)
        if 账号ID and 账号ID != 凭据["id"]:
            raise ValueError("账号身份不匹配")
        原值 = next((项 for 项 in 状态["accounts"] if 项["id"] == 凭据["id"]), None)
        if 原值:
            # 换票据后保留已有资料，但下次刷新重新核对官方会员状态。
            原值.update({"ywkey": 凭据["ywkey"], "enabled": True,
                         "updated_at": int(time.time())})
            for 键 in ("nickname", "avatar_url", "phone"):
                if 凭据[键]:
                    原值[键] = 凭据[键]
        else:
            凭据["updated_at"] = int(time.time())
            状态["accounts"].append(凭据)
        if 设为当前 or not 状态["selected_id"]:
            状态["selected_id"] = 凭据["id"]
        _写入QQ阅读账号状态(配置, 状态)
        return _QQ阅读账号摘要(状态)


def 设置QQ阅读账号启用(配置: Any, 账号ID: str, 启用: bool) -> dict[str, Any]:
    if not isinstance(启用, bool):
        raise ValueError("账号开关参数无效")
    with _QQ阅读账号状态锁:
        状态 = _读取QQ阅读账号状态(配置)
        账号 = next((项 for 项 in 状态["accounts"] if 项["id"] == 账号ID), None)
        if 账号 is None:
            raise ValueError("QQ阅读账号不存在")
        账号["enabled"] = 启用
        if not 启用 and 状态["selected_id"] == 账号ID:
            状态["selected_id"] = next((项["id"] for 项 in 状态["accounts"] if 项["enabled"]), "")
        elif 启用 and not 状态["selected_id"]:
            状态["selected_id"] = 账号ID
        _写入QQ阅读账号状态(配置, 状态)
        return _QQ阅读账号摘要(状态)


def 切换QQ阅读账号(配置: Any, 账号ID: str) -> dict[str, Any]:
    with _QQ阅读账号状态锁:
        状态 = _读取QQ阅读账号状态(配置)
        if not any(项["id"] == 账号ID and 项["enabled"] for 项 in 状态["accounts"]):
            raise ValueError("请选择已启用的QQ阅读账号")
        状态["selected_id"] = 账号ID
        _写入QQ阅读账号状态(配置, 状态)
        return _QQ阅读账号摘要(状态)


def 删除QQ阅读账号(配置: Any, 账号ID: str) -> dict[str, Any]:
    with _QQ阅读账号状态锁:
        状态 = _读取QQ阅读账号状态(配置)
        if not any(项["id"] == 账号ID for 项 in 状态["accounts"]):
            raise ValueError("QQ阅读账号不存在")
        状态["accounts"] = [项 for 项 in 状态["accounts"] if 项["id"] != 账号ID]
        if 状态["selected_id"] == 账号ID:
            状态["selected_id"] = next((项["id"] for 项 in 状态["accounts"] if 项["enabled"]), "")
        _写入QQ阅读账号状态(配置, 状态)
        return _QQ阅读账号摘要(状态)


def _合并QQ阅读账号资料(
    配置: Any, 凭据: dict[str, Any], 资料: dict[str, Any],
) -> dict[str, Any]:
    with _QQ阅读账号状态锁:
        状态 = _读取QQ阅读账号状态(配置)
        账号 = next((项 for 项 in 状态["accounts"] if 项["id"] == 凭据["id"]), None)
        # 刷新期间删除、重登或改票据时，迟到资料不新增账号也不覆盖新资料。
        if 账号 is None or 账号["ywkey"] != 凭据["ywkey"]:
            return _QQ阅读账号摘要(状态)
        for 键 in ("nickname", "avatar_url", "phone"):
            值 = str(资料.get(键) or "")
            if 值:
                账号[键] = 值[:2048 if 键 == "avatar_url" else 120]
        if isinstance(资料.get("vip"), dict):
            账号["vip"] = dict(资料["vip"])
        账号["profile_updated_at"] = int(time.time())
        _写入QQ阅读账号状态(配置, 状态)
        return _QQ阅读账号摘要(状态)


async def 刷新QQ阅读账号资料(配置: Any, 账号ID: str = "") -> dict[str, Any]:
    凭据 = await asyncio.to_thread(读取QQ阅读账号凭据, 配置, 账号ID)
    if not 凭据:
        raise ValueError("QQ阅读账号不存在")
    with QQ阅读账号上下文(凭据):
        async with 创建QQ阅读HTTP会话(concurrency=2) as session:
            资料 = await 查询QQ阅读账号资料(session)
    if not 资料.get("available"):
        raise ValueError("QQ阅读账号资料暂未获取")
    return await asyncio.to_thread(_合并QQ阅读账号资料, 配置, 凭据, 资料)


def _读取QQ阅读登录态(配置: Any) -> dict[str, str] | None:
    凭据 = 读取QQ阅读账号凭据(配置)
    return {"ywguid": 凭据["ywguid"], "ywkey": 凭据["ywkey"]} if 凭据 else None


def _保存QQ阅读登录态(配置: Any, 登录态: dict[str, Any]) -> None:
    保存QQ阅读账号(配置, 登录态)


async def 加载保存的QQ阅读登录态(配置: Any) -> bool:
    await asyncio.to_thread(初始化参考核心)
    if not 已配置运行状态数据库(配置):
        return False
    try:
        登录态 = await asyncio.to_thread(_读取QQ阅读登录态, 配置)
    except Exception as exc:
        logger.warning(f"QQ阅读登录态读取失败：错误={type(exc).__name__}")
        return False
    if not 登录态:
        return False
    _应用QQ阅读登录态(登录态)
    return True


async def 处理QQ阅读Cookie指令(
    event: Any,
    命令文本: str,
    配置: Any = None,
) -> str | None:
    if not 识别QQ阅读Cookie文本(命令文本):
        return None
    if not 是群文件清理管理员(event, 配置):
        return ""
    登录态 = 解析QQ阅读Cookie(命令文本)
    if 登录态 is None:
        return "QQ阅读Cookie无效，请同时提供有效的ywguid/ywkey或uid/usid"
    if not 已配置运行状态数据库(配置):
        return "数据库未配置，QQ阅读Cookie未保存"
    try:
        await asyncio.to_thread(_保存QQ阅读登录态, 配置, 登录态)
    except Exception as exc:
        logger.warning(f"QQ阅读Cookie保存失败：错误={type(exc).__name__}")
        return "QQ阅读Cookie保存失败，请稍后再试"
    return "QQ阅读账号已保存并设为当前账号"


def _遍历详情对象(data: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    stack = [data]
    seen: set[int] = set()
    while stack:
        item = stack.pop(0)
        if isinstance(item, dict):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            result.append(item)
            stack.extend(
                value for value in item.values() if isinstance(value, (dict, list))
            )
        elif isinstance(item, list):
            stack.extend(item)
    return result


def _读取详情字段(objects: list[dict[str, Any]], *names: str, default: Any = "") -> Any:
    for item in objects:
        for name in names:
            value = item.get(name)
            if value not in (None, ""):
                return value
    return default


def _安全整数(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError, OverflowError):
        return default


def _是真值(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _详情支持VIP免费(objects: list[dict[str, Any]]) -> bool:
    vip_free = _读取详情字段(
        objects,
        "vipFree",
        "vip_free",
        "isVipFree",
        "is_vip_free",
        default=False,
    )
    if _是真值(vip_free):
        return True
    message = str(
        _读取详情字段(
            objects,
            "vipFreeMsg",
            "vip_free_msg",
            "vipTips",
            "vip_tips",
            "vipdisc",
            "vipDisc",
            default="",
        )
        or ""
    ).strip()
    lowered = message.lower()
    has_vip_marker = "vip" in lowered or "会员" in message or "包月" in message
    has_free_marker = "免费" in message or "专享" in message or "开通" in message
    if has_vip_marker and has_free_marker:
        return True

    need_open_vip = _读取详情字段(
        objects,
        "needOpenVip",
        "need_open_vip",
        default=False,
    )
    return _是真值(need_open_vip) and has_vip_marker


def _规范状态(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if text in {"完结", "完本"} or "完结" in text or lowered in {"1", "true", "yes"}:
        return "完结"
    if text in {"连载"} or "连载" in text or lowered in {"0", "false", "no"}:
        return "连载"
    return "连载"


def 解析参考书籍详情(data: Any, book_id: str) -> dict[str, Any]:
    if (
        isinstance(data, dict)
        and "retCode" in data
        and _安全整数(data.get("retCode"), 0) != 0
    ):
        raise RuntimeError("书籍详情不可用")
    objects = _遍历详情对象(data)
    status = _规范状态(
        _读取详情字段(
            objects,
            "isfinished",
            "isFinished",
            "finished",
            "finishstate",
            "status",
        )
    )
    chapters = _读取详情字段(
        objects,
        "totalChapters",
        "chapterNum",
        "chapters",
        "totalChapter",
        "chapter_count",
        default=0,
    )
    max_free_chapter = _读取详情字段(
        objects,
        "maxfreechapter",
        "maxFreeChapter",
        "max_free_chapter",
        default=0,
    )
    vip_state = _读取详情字段(
        objects,
        "isVip",
        "is_vip",
        "vipStatus",
        "vip_status",
        default=False,
    )
    free_value = _读取详情字段(objects, "free", default=None)
    free = None
    if free_value not in (None, ""):
        parsed_free = _安全整数(free_value, default=-1)
        if parsed_free >= 0:
            free = parsed_free
    return {
        "title": str(
            _读取详情字段(
                objects, "title", "bookName", "book_name", default=f"QQ阅读{book_id}"
            )
            or f"QQ阅读{book_id}"
        ).strip(),
        "author": str(
            _读取详情字段(
                objects, "author", "authorName", "author_name", default="未知"
            )
            or "未知"
        ).strip(),
        "status": status,
        "words_num": str(
            _读取详情字段(
                objects,
                "wordscount",
                "wordCount",
                "words",
                "allwords",
                "totalWords",
                "word_count",
                default="",
            )
            or ""
        ).strip(),
        "chapters": _安全整数(chapters),
        "total_chapters": _安全整数(chapters),
        "max_free_chapter": _安全整数(max_free_chapter),
        "is_vip": _是真值(vip_state),
        "free": free,
        "vip_free": _详情支持VIP免费(objects),
        "intro": str(
            _读取详情字段(
                objects, "intro", "desc", "summary", "description", default=""
            )
            or ""
        ).strip(),
    }


def 解析QQ阅读搜索结果(data: Any) -> list[dict[str, Any]]:
    """把 QQ 阅读 App 搜索卡片归一为找书可用字段。"""
    if not isinstance(data, dict):
        return []
    cards = data.get("cardlist") or data.get("cardList") or []
    if not isinstance(cards, list):
        return []
    result: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        info = card.get("info") if isinstance(card.get("info"), dict) else {}
        book_id = str(
            info.get("bid") or card.get("bid") or card.get("id") or ""
        ).strip()
        title = _清理QQ阅读搜索文本(
            info.get("title") or info.get("bookName") or card.get("title") or ""
        )
        if not book_id.isdigit() or not title:
            continue
        result.append(
            {
                "platform": "QQ阅读",
                "book_id": book_id,
                "title": title,
                "author": _清理QQ阅读搜索文本(
                    info.get("author") or card.get("author") or "未知"
                )
                or "未知",
                "url": f"https://book.qq.com/book-detail/{book_id}",
                "score": card.get("book_score") or info.get("score") or 0,
                "word_count": info.get("allwords") or card.get("allwords") or 0,
                "read_count": 0,
            }
        )
    return result


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    """使用 QQ 阅读 App 搜索接口获取找书候选。"""
    keyword = str(关键词 or "").strip()
    if not keyword:
        return []
    size = max(1, min(int(需要数量 or 20), 30))
    async with 创建QQ阅读HTTP会话(concurrency=2) as session:
        await 确保QQ阅读密钥池(session)
        async with session.get(
            QQ阅读搜索地址,
            params={"key": keyword, "start": 0, "size": size},
            headers=await 异步构造QQ阅读鉴权请求头(int(time.time() * 1000)),
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
    return 解析QQ阅读搜索结果(data)[:size]


async def 获取参考书籍详情(
    book_id: str,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    if session is None:
        async with 创建QQ阅读HTTP会话(concurrency=2) as local_session:
            return await 获取参考书籍详情(book_id, local_session)
    await 确保QQ阅读密钥池(session)
    async with session.get(
        QQ阅读详情地址,
        params={"bid": book_id, "types": "1,2,3,4,5"},
        headers=await 异步构造QQ阅读鉴权请求头(int(time.time() * 1000)),
    ) as response:
        response.raise_for_status()
        data = await response.json(content_type=None)
    return 解析参考书籍详情(data, book_id)


def 解析参考目录包(package: bytes, book_id: str) -> list[dict[str, Any]]:
    members = tar_decrypt(package)
    candidates: list[tuple[str, bytes]] = []
    for name, data in members.items():
        if name == "code" or not isinstance(data, (bytes, bytearray)):
            continue
        candidates.append((str(name), bytes(data)))
    if not candidates:
        return []
    candidates.sort(
        key=lambda item: (
            item[0] == f"{book_id}_ALL_s",
            item[0].endswith("_ALL_s"),
            len(item[1]),
        ),
        reverse=True,
    )
    text = candidates[0][1].decode("utf-8", "replace")
    rows: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        parts = line.split(",")
        cid = parts[0].strip() if parts else ""
        if not cid.isdigit():
            continue
        if len(parts) >= 15:
            title = ",".join(parts[1:-13]).strip()
        else:
            title = parts[1].strip() if len(parts) > 1 else ""
        metadata = parts[-13:] if len(parts) >= 15 else []
        chapter_fee = (
            max(_安全整数(metadata[1]), _安全整数(metadata[3]))
            if len(metadata) == 13
            else 0
        )
        rows.append(
            {
                "cid": cid,
                "title": title or f"第{cid}章",
                "chapter_fee": chapter_fee,
            }
        )
    rows.sort(key=lambda row: int(row["cid"]))
    return [
        {
            "cid": row["cid"],
            "index": index,
            "title": row["title"],
            "chapter_fee": row["chapter_fee"],
        }
        for index, row in enumerate(rows, start=1)
    ]


def 获取QQ阅读书籍付费类型(
    details: dict[str, Any], catalog: list[dict[str, Any]]
) -> str:
    """按目录费用和详情标记区分免费、VIP 与单章付费书籍。"""
    total = max(
        _安全整数(details.get("total_chapters")),
        _安全整数(details.get("chapters")),
        len(catalog),
    )
    max_free = _安全整数(details.get("max_free_chapter"))
    has_free_limit = max_free > 0 and max_free < total
    has_paid_chapter = any(
        _安全整数(item.get("chapter_fee")) > 0 for item in catalog
    )
    # 详情的 free 是 QQ 阅读 App 的书籍级分类，应优先于目录中的
    # chapter_fee。VIP 章节同样会带章节价格，不能因此把 VIP 书误判为
    # 单章付费；只有 free=0 且目录明确存在付费/免费上限时才是单章付费。
    free_type = _安全整数(details.get("free"), default=-1)
    if free_type == 1:
        return "free"
    if free_type == 2:
        return "vip"
    if free_type == 0 and (has_paid_chapter or has_free_limit):
        return "single"
    if has_paid_chapter:
        return "single"
    if _是真值(details.get("vip_free")):
        return "vip"
    if has_free_limit:
        return "single"
    return "free"


def 是章节单独付费书籍(details: dict[str, Any], catalog: list[dict[str, Any]]) -> bool:
    return 获取QQ阅读书籍付费类型(details, catalog) == "single"


def 获取QQ阅读可下载目录(
    details: dict[str, Any],
    catalog: list[dict[str, Any]],
    账号有VIP: bool = False,
) -> list[dict[str, Any]]:
    """免费书取全量，账号 VIP 取 VIP 书全量，单章付费始终只取免费章。"""
    带原始序号目录 = [
        {**dict(item), "_qq_source_index": position}
        for position, item in enumerate(catalog, start=1)
    ]
    付费类型 = 获取QQ阅读书籍付费类型(details, catalog)
    if 付费类型 == "free" or (
        付费类型 == "vip" and bool(账号有VIP)
    ):
        return 带原始序号目录
    max_free = _安全整数(details.get("max_free_chapter"))
    total = max(
        _安全整数(details.get("total_chapters")),
        _安全整数(details.get("chapters")),
        len(catalog),
    )
    has_free_limit = max_free > 0 and max_free < total
    free_catalog = [
        dict(item)
        for position, item in enumerate(带原始序号目录, start=1)
        if _安全整数(item.get("chapter_fee")) <= 0
        and (not has_free_limit or position <= max_free)
    ]
    for index, item in enumerate(free_catalog, start=1):
        item["index"] = index
    return free_catalog


def _获取QQ阅读带原始序号目录(
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """保留第三方正文接口使用的原始目录位置。"""
    return [
        {**dict(item), "_qq_source_index": position}
        for position, item in enumerate(catalog, start=1)
    ]


def _QQ阅读第三方正文范围(
    catalog: list[dict[str, Any]],
) -> list[tuple[int, int, list[dict[str, Any]]]]:
    """按原目录序号拆分连续区间，避免过滤章节后正文错位。"""
    indexed: list[tuple[int, dict[str, Any]]] = []
    for position, item in enumerate(catalog, start=1):
        source_index = _安全整数(item.get("_qq_source_index"), position)
        if source_index > 0:
            indexed.append((source_index, item))
    indexed.sort(key=lambda entry: entry[0])

    ranges: list[tuple[int, int, list[dict[str, Any]]]] = []
    start = 0
    end = 0
    items: list[dict[str, Any]] = []
    for source_index, item in indexed:
        if not items or source_index == end + 1:
            if not items:
                start = source_index
            end = source_index
            items.append(item)
            continue
        ranges.append((start, end, items))
        start = end = source_index
        items = [item]
    if items:
        ranges.append((start, end, items))
    return ranges


async def 下载QQ阅读第三方正文(
    book_id: str,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """非会员从第三方正文服务分段获取完整可下载目录。"""
    if not catalog:
        return []

    tasks: list[tuple[int, int, list[dict[str, Any]]]] = []
    for range_start, _range_end, range_items in _QQ阅读第三方正文范围(catalog):
        for offset in range(0, len(range_items), QQ阅读第三方正文批量章节数):
            batch_items = range_items[
                offset : offset + QQ阅读第三方正文批量章节数
            ]
            if batch_items:
                tasks.append(
                    (
                        range_start + offset,
                        range_start + offset + len(batch_items) - 1,
                        batch_items,
                    )
                )
    if not tasks:
        return []

    concurrency = max(
        1,
        min(QQ阅读第三方正文最大动态并发数, len(tasks)),
    )
    semaphore = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=45, sock_connect=10, sock_read=45)
    contents_by_source_index: dict[int, str] = {}

    async def fetch_range(
        client: aiohttp.ClientSession,
        range_start: int,
        range_end: int,
        range_items: list[dict[str, Any]],
    ) -> None:
        async with semaphore:
            async with client.get(
                QQ阅读第三方正文地址,
                params={"bookid": str(book_id), "s": range_start, "e": range_end},
                headers={"Accept": "application/json", "User-Agent": UA},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)

        if not isinstance(payload, dict):
            raise RuntimeError("第三方正文响应格式无效")
        result_code = payload.get("code")
        if result_code not in (None, "") and _安全整数(result_code, -1) != 0:
            raise RuntimeError("第三方正文接口业务失败")
        chapter_contents = payload.get("data")
        if not isinstance(chapter_contents, list) or len(chapter_contents) != len(
            range_items
        ):
            logger.warning(
                "QQ阅读第三方正文响应不完整：书籍编号=%s，请求范围=%s-%s，"
                "返回章节=%s，预期章节=%s，错误分类=%s",
                book_id,
                range_start,
                range_end,
                len(chapter_contents) if isinstance(chapter_contents, list) else 0,
                len(range_items),
                "章节范围不可用"
                if isinstance(chapter_contents, list)
                else "响应格式无效",
            )
            raise RuntimeError("第三方正文章节数量不完整")

        for offset, chapter_content in enumerate(chapter_contents):
            if isinstance(chapter_content, dict):
                chapter_content = (
                    chapter_content.get("content")
                    or chapter_content.get("text")
                    or chapter_content.get("body")
                    or ""
                )
            text = str(chapter_content or "").strip()
            if not text:
                raise RuntimeError("第三方正文返回空章节")
            contents_by_source_index[range_start + offset] = text

    connector = aiohttp.TCPConnector(
        limit=concurrency,
        limit_per_host=concurrency,
        ttl_dns_cache=300,
        keepalive_timeout=30,
    )
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        trust_env=True,
    ) as client:
        await asyncio.gather(
            *(fetch_range(client, start, end, items) for start, end, items in tasks)
        )

    chapters: list[dict[str, Any]] = []
    for position, item in enumerate(catalog, start=1):
        source_index = _安全整数(item.get("_qq_source_index"), position)
        text = contents_by_source_index.get(source_index, "")
        if not text:
            raise RuntimeError("第三方正文缺少章节")
        chapters.append({**item, "content": text})
    return chapters


async def 获取参考书籍目录(
    book_id: str,
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, Any]]:
    if session is None:
        async with 创建QQ阅读HTTP会话(concurrency=2) as local_session:
            return await 获取参考书籍目录(book_id, local_session)
    await 确保QQ阅读密钥池(session)
    params = {
        "bookId": book_id,
        "type": "0",
        "tafauth": "1",
        "scids": "0",
        "text_type": "0",
        "useindex": "1",
    }
    async with session.get(
        QQ阅读目录地址,
        params=params,
        headers=await 异步构造QQ阅读鉴权请求头(
            int(time.time() * 1000),
            _构造QQ阅读请求地址(QQ阅读目录地址, params),
        ),
    ) as response:
        response.raise_for_status()
        package = await response.read()
    return await _异步QQ阅读CPU函数(解析参考目录包, package, book_id)


async def 获取参考兼容目录(
    book_id: str,
    chapter_count: int,
    session: aiohttp.ClientSession | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    total = max(0, int(chapter_count or 0))
    catalog: list[dict[str, Any]] = []
    try:
        catalog = await 获取参考书籍目录(book_id, session)
    except aiohttp.ClientResponseError as exc:
        if exc.status != 400:
            raise
    if catalog or total <= 0:
        return catalog, False

    fallback = await 获取参考出版书目录(book_id, total, session)
    return fallback, bool(fallback)


def _出版书资源地址(item: dict[str, Any]) -> str:
    for key in (
        "ctebchaptercosurl",
        "chaptercosurl",
        "epubPureUrl",
        "epubResourceUrl",
    ):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def 解析参考出版书目录(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        cid = str(
            item.get("chapter_id") or item.get("cid") or item.get("scid") or ""
        ).strip()
        if not cid.isdigit():
            continue
        resource_url = _出版书资源地址(item)
        if not resource_url:
            continue
        title = str(
            item.get("chapter_title") or item.get("title") or f"第{cid}章"
        ).strip()
        candidate = {
            "cid": cid,
            "title": title or f"第{cid}章",
            "resource_url": resource_url,
            "published": True,
        }
        current = selected.get(cid)
        if current is None:
            selected[cid] = candidate
            continue
        current_url = str(current.get("resource_url") or "")
        if "epubPure" in resource_url and "epubPure" not in current_url:
            selected[cid] = candidate
    rows = sorted(selected.values(), key=lambda row: int(row["cid"]))
    return [
        {
            "cid": row["cid"],
            "index": index,
            "title": row["title"],
            "resource_url": row["resource_url"],
            "published": True,
        }
        for index, row in enumerate(rows, start=1)
    ]


async def 获取参考出版书目录(
    book_id: str,
    chapter_count: int,
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, Any]]:
    total = max(0, int(chapter_count or 0))
    if total <= 0:
        return []
    if session is None:
        concurrency = max(1, min(QQ阅读批量最大动态并发数, (total + 199) // 200))
        async with 创建QQ阅读HTTP会话(concurrency=concurrency) as local_session:
            return await 获取参考出版书目录(book_id, total, local_session)
    await 确保QQ阅读密钥池(session)
    config = ConfigManager.get_instance()
    chapter_ids = [str(index) for index in range(1, total + 1)]
    batches = [chapter_ids[start : start + 200] for start in range(0, total, 200)]
    semaphore = asyncio.Semaphore(max(1, min(QQ阅读批量最大动态并发数, len(batches))))

    async def 请求目录批次(batch: list[str]) -> list[dict[str, Any]]:
        params = {
            "bookId": book_id,
            "type": "0",
            "tafauth": "1",
            "cidType": "1",
            "restype": "4",
            "epubFlag": "1",
            "scids": ",".join(batch),
            "scene": "0",
            "adState": "1",
            "fuid": config.fuid,
            "noclick": "1",
        }
        headers = await 异步构造QQ阅读鉴权请求头(
            int(time.time() * 1000),
            _构造QQ阅读请求地址(QQ阅读目录地址, params),
        )
        headers["text_type"] = "1"
        async with semaphore:
            async with session.get(
                QQ阅读目录地址,
                params=params,
                headers=headers,
            ) as response:
                response.raise_for_status()
                package = await response.read()
        return await _异步QQ阅读CPU函数(_parse_teb_info_blob, package)

    all_items: list[dict[str, Any]] = []
    for items in await asyncio.gather(*(请求目录批次(batch) for batch in batches)):
        all_items.extend(items)
    catalog = 解析参考出版书目录(all_items)
    if len(catalog) != total:
        raise RuntimeError("章节不完整")
    return catalog


async def 获取参考出版书密码(
    book_id: str,
    session: aiohttp.ClientSession,
) -> bytes:
    config = ConfigManager.get_instance()
    params = {
        "bookid": book_id,
        "authInfo": config.qrsn[:16],
        "onlytrial": "1",
        "onlycteb": "1",
    }
    # /auth 使用独立的 App 登录包格式；混入网关签名会改变响应封装。
    headers = {
        "User-Agent": UA,
        "Cookie": f"ywguid={config.uid}; ywkey={config.usid};",
        "ywguid": config.uid,
        "ywkey": config.usid,
        "Accept": "*/*",
    }
    async with session.get(
        API_AUTH,
        params=params,
        headers=headers,
    ) as response:
        response.raise_for_status()
        encrypted = await response.read()
    plain = await _异步QQ阅读CPU函数(
        tea_decrypt_bytes, encrypted, tea_key_ints(config.uid)
    )
    payload = json.loads(plain.split(b"\x00", 1)[0].decode("utf-8"))
    password = str(payload.get("pwd") or "").encode("utf-8")
    if not password:
        raise RuntimeError("出版书授权失败")
    return password


def 解析参考出版书章节(package: bytes, password: bytes) -> str:
    files = extract_eqct(package, password)
    if not files:
        raise RuntimeError("出版书资源解包为空")
    text = 合并参考出版书正文(files).strip()
    if not text:
        图片扩展名 = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
        存在图片正文 = any(
            name.lower().endswith((".xhtml", ".html", ".htm"))
            and re.search(rb"<img\b[^>]*\bsrc\s*=", data, re.IGNORECASE)
            for name, data in files
        ) and any(name.lower().endswith(图片扩展名) for name, _ in files)
        if 存在图片正文:
            raise RuntimeError("出版书章节仅包含图片")
        raise RuntimeError("出版书正文为空")
    return text


def _出版书章节失败分类(exc: Exception) -> str:
    if isinstance(exc, aiohttp.ClientResponseError):
        return f"http_{exc.status}"
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, aiohttp.ClientError):
        return "network_error"
    if isinstance(exc, zipfile.BadZipFile):
        return "bad_zip"
    if isinstance(exc, zlib.error):
        return "deflate_error"
    if isinstance(exc, NotImplementedError):
        return "unsupported_compression"
    if isinstance(exc, RuntimeError):
        if str(exc) == "出版书资源解包为空":
            return "empty_archive"
        if str(exc) == "出版书章节仅包含图片":
            return "image_only"
        if str(exc) == "出版书章节正文只有标题":
            return "title_only"
        if str(exc) == "出版书正文为空":
            return "empty_text"
        if "password" in str(exc).lower():
            return "zip_password_error"
        return "runtime_error"
    if isinstance(exc, (ValueError, struct.error, EOFError)):
        return "invalid_container"
    return type(exc).__name__


async def 下载参考出版书正文(
    book_id: str,
    catalog: list[dict[str, Any]],
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, Any]]:
    if not catalog:
        return []
    if session is None:
        concurrency = max(1, min(QQ阅读出版书最大动态并发数, len(catalog)))
        async with 创建QQ阅读HTTP会话(concurrency=concurrency) as local_session:
            return await 下载参考出版书正文(book_id, catalog, local_session)

    password = await 获取参考出版书密码(book_id, session)
    total = len(catalog)
    concurrency = max(1, min(QQ阅读出版书最大动态并发数, total))
    request_semaphore = asyncio.Semaphore(concurrency)
    decrypt_semaphore = asyncio.Semaphore(max(1, min(QQ阅读解密最大动态并发数, total)))
    failure_types: dict[int, str] = {}
    skippable_failure_types = {"image_only", "title_only"}
    logger.info(
        f"QQ阅读章节进度：书籍编号={book_id}, 进度=0/{total}, 百分比=0%, "
        f"并发数={concurrency}"
    )

    async def 下载章节(index: int, item: dict[str, Any]) -> tuple[int, str | None]:
        resource_url = str(item.get("resource_url") or "").strip()
        if not resource_url:
            failure_types[index] = "missing_resource_url"
            return index, None
        for attempt in range(1, 4):
            try:
                async with request_semaphore:
                    async with session.get(
                        resource_url, headers={"User-Agent": UA}
                    ) as response:
                        response.raise_for_status()
                        package = await response.read()
                async with decrypt_semaphore:
                    text = await _异步QQ阅读CPU函数(
                        解析参考出版书章节, package, password
                    )
                if not 去除章节正文重复标题(item.get("title"), text):
                    raise RuntimeError("出版书章节正文只有标题")
                return index, text
            except Exception as exc:
                failure_type = _出版书章节失败分类(exc)
                if attempt >= 3 or failure_type in {
                    "empty_archive",
                    "empty_text",
                    "image_only",
                    "title_only",
                }:
                    failure_types[index] = failure_type
                    logger.debug(
                        f"QQ阅读出版书章节请求失败：书籍编号={book_id}, 序号={index + 1}, "
                        f"尝试次数={attempt}, 分类={failure_types[index]}"
                    )
                    break
                await asyncio.sleep(0.3 * attempt)
        return index, None

    results: dict[int, str] = {}
    completed = 0
    last_segment = 0
    for task in asyncio.as_completed(
        [下载章节(index, item) for index, item in enumerate(catalog)]
    ):
        index, text = await task
        if text:
            results[index] = text
        completed += 1
        skipped = sum(
            1
            for failure_type in failure_types.values()
            if failure_type in skippable_failure_types
        )
        segment = (
            QQ阅读进度日志分段数
            if completed >= total
            else int(completed * QQ阅读进度日志分段数 / max(1, total))
        )
        if segment > last_segment or completed >= total:
            last_segment = segment
            success = len(results)
            percent = int(completed * 100 / max(1, total))
            logger.info(
                f"QQ阅读章节进度：书籍编号={book_id}, 进度={completed}/{total}, "
                f"百分比={percent}%, 成功={success}, 跳过={skipped}, "
                f"失败={max(0, completed - success - skipped)}"
            )
    missing_indices = [index for index in range(total) if index not in results]
    skipped_indices = [
        index
        for index in missing_indices
        if failure_types.get(index) in skippable_failure_types
    ]
    failed_indices = [index for index in missing_indices if index not in skipped_indices]
    if skipped_indices:
        skipped_preview = ",".join(str(index + 1) for index in skipped_indices[:10])
        if len(skipped_indices) > 10:
            skipped_preview += ",..."
        logger.info(
            f"QQ阅读出版书无可读正文章节已跳过：书籍编号={book_id}, "
            f"序号={skipped_preview}, 数量={len(skipped_indices)}"
        )
    if failed_indices:
        reason_counts: dict[str, int] = {}
        for index in failed_indices:
            reason = failure_types.get(index, "unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        missing_preview = ",".join(
            str(index + 1) for index in failed_indices[:10]
        )
        if len(failed_indices) > 10:
            missing_preview += ",..."
        reason_summary = ",".join(
            f"{reason}:{count}" for reason, count in sorted(reason_counts.items())
        )
        logger.warning(
            f"QQ阅读出版书正文缺失：书籍编号={book_id}, "
            f"缺失序号={missing_preview}, 数量={len(failed_indices)}, "
            f"失败分类={reason_summary}"
        )
        raise RuntimeError("章节不完整")
    chapters = [
        {**item, "content": results[index]}
        for index, item in enumerate(catalog)
        if index in results
    ]
    if not chapters:
        raise RuntimeError("出版书全部章节均无可读正文")
    return chapters


async def 异步获取QQ阅读正文批次(
    session: aiohttp.ClientSession,
    book_id: str,
    chapter_ids: list[str],
    解密信号量: asyncio.Semaphore,
    *,
    请求信号量: asyncio.Semaphore | None = None,
    解密材料: tuple[bytes, bytes, bytes] | None = None,
) -> tuple[list[Any], int, int]:
    config = ConfigManager.get_instance()
    params = {
        "bookId": str(book_id),
        "type": "2",
        "scids": 构造QQ阅读正文章节参数(chapter_ids),
        "fuid": config.fuid,
    }
    headers = await 异步构造QQ阅读鉴权请求头(
        int(time.time() * 1000),
        _构造QQ阅读请求地址(QQ阅读目录地址, params),
    )
    request_started = time.perf_counter()
    response_status = 0
    if 请求信号量 is None:
        请求上下文 = session.get(QQ阅读目录地址, params=params, headers=headers)
        async with 请求上下文 as response:
            response.raise_for_status()
            package = await response.read()
            response_status = response.status
            _检查QQ阅读正文响应(package, response_status)
    else:
        async with 请求信号量:
            async with session.get(
                QQ阅读目录地址, params=params, headers=headers
            ) as response:
                response.raise_for_status()
                package = await response.read()
                response_status = response.status
                _检查QQ阅读正文响应(package, response_status)
    request_elapsed = time.perf_counter() - request_started
    decrypt_started = time.perf_counter()
    try:
        async with 解密信号量:
            result = await _异步QQ阅读CPU函数(
                解析QQ阅读正文批次带统计,
                package,
                chapter_ids,
                解密材料,
            )
    except _QQ阅读正文响应错误 as exc:
        raise _QQ阅读正文响应错误(
            exc.category,
            http_status=exc.http_status or response_status,
            code=exc.code,
        ) from None
    for item in result[0]:
        if isinstance(item, _QQ阅读正文响应错误) and not item.http_status:
            item.http_status = response_status
    decrypt_elapsed = time.perf_counter() - decrypt_started
    chapter_span = (
        f"{chapter_ids[0]}-{chapter_ids[-1]}" if chapter_ids else ""
    )
    logger.debug(
        f"QQ阅读批次耗时：章节范围={chapter_span}, 章节数={len(chapter_ids)}, "
        f"响应字节={len(package)}, 请求={request_elapsed:.3f}s, "
        f"解包解密={decrypt_elapsed:.3f}s"
    )
    return result


async def 下载参考正文(
    book_id: str,
    catalog: list[dict[str, Any]],
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, Any]]:
    if not catalog:
        return []
    if session is None:
        batch_count = (len(catalog) + QQ阅读批量章节数 - 1) // QQ阅读批量章节数
        concurrency = 计算QQ阅读批量并发数(batch_count)
        async with 创建QQ阅读HTTP会话(concurrency=concurrency) as local_session:
            return await 下载参考正文(book_id, catalog, local_session)
    初始化参考核心()
    await 确保QQ阅读密钥池(session)
    total = len(catalog)
    last_segment = 0
    last_completed = 0
    last_success = -1
    batch_count = (total + QQ阅读批量章节数 - 1) // QQ阅读批量章节数
    concurrency = 计算QQ阅读批量并发数(batch_count)
    logger.info(
        f"QQ阅读章节进度：书籍编号={book_id}, 进度=0/{total}, 百分比=0%, "
        f"批次数={batch_count}, 批量章节数={QQ阅读批量章节数}, 并发数={concurrency}, "
        f"最大并发数={QQ阅读批量最大动态并发数}"
    )

    def 合并批次(
        first: int,
        last: int,
        part: Any,
        results: list[Any],
        batch_failure: dict[str, Any] | None,
    ) -> int:
        recovered = 0
        for offset in range(last - first + 1):
            target_index = first + offset - 1
            if target_index < 0 or target_index >= len(results):
                continue
            if not _QQ阅读正文项失败原因(results[target_index]):
                continue
            if batch_failure is not None:
                failure_reasons[target_index] = dict(batch_failure)
                continue
            if not isinstance(part, list) or offset >= len(part):
                failure_reasons[target_index] = {"category": "响应缺失"}
                continue
            item = part[offset]
            reason = _QQ阅读正文项失败原因(item)
            if reason:
                failure_reasons[target_index] = {"category": reason}
                if isinstance(item, _QQ阅读正文响应错误):
                    failure_reasons[target_index].update(
                        {"http_status": item.http_status, "code": item.code}
                    )
                continue
            results[target_index] = item
            failure_reasons[target_index] = None
            recovered += 1
        return recovered

    def 汇报进度(completed: int, success: int) -> None:
        nonlocal last_segment, last_completed, last_success
        completed = min(max(0, int(completed)), total)
        success = min(max(0, int(success)), completed)
        segment = (
            QQ阅读进度日志分段数
            if completed >= total
            else int(completed * QQ阅读进度日志分段数 / max(1, total))
        )
        if segment <= last_segment and completed < total:
            return
        if (
            completed >= total
            and completed == last_completed
            and success == last_success
        ):
            return
        last_segment = max(last_segment, segment)
        last_completed = completed
        last_success = success
        percent = int(completed * 100 / max(1, total))
        logger.info(
            f"QQ阅读章节进度：书籍编号={book_id}, 进度={completed}/{total}, "
            f"百分比={percent}%, 成功={success}, 失败={completed - success}"
        )

    ranges = [
        (start, min(start + QQ阅读批量章节数 - 1, total))
        for start in range(1, total + 1, QQ阅读批量章节数)
    ]
    results: list[Any] = [None] * total
    failure_reasons: list[dict[str, Any] | None] = [None] * total
    completed = 0
    success = 0
    请求信号量 = asyncio.Semaphore(concurrency)
    decrypt_concurrency = max(1, min(QQ阅读解密最大动态并发数, total))
    解密信号量 = asyncio.Semaphore(decrypt_concurrency)
    解密材料: tuple[bytes, bytes, bytes] | None = None
    try:
        解密材料 = ConfigManager.get_instance().获取解密材料()
    except Exception:
        logger.debug("QQ阅读正文解密材料准备失败")

    def 新建请求统计() -> dict[str, int]:
        return {
            "batches": 0,
            "response_items": 0,
            "valid_items": 0,
            "response_missing": 0,
            "decrypt_failed": 0,
            "http_failed": 0,
            "other_failed": 0,
            "timeout_failed": 0,
            "invalid_response": 0,
        }

    def 合并请求统计(target: dict[str, int], source: dict[str, int]) -> None:
        for key in target:
            target[key] += int(source.get(key, 0) or 0)

    def 格式化失败范围(numbers: list[int]) -> str:
        return ",".join(
            f"{start}-{end}" if start != end else str(start)
            for start, end in QQ阅读失败章节窗口(numbers)
        )

    async def 请求批次(
        first: int,
        last: int,
    ) -> tuple[int, int, list[Any] | None, dict[str, int], dict[str, Any] | None]:
        expected = last - first + 1
        stats = 新建请求统计()
        stats["batches"] = 1
        try:
            chapter_ids = 获取QQ阅读正文章节ID列表(catalog, first, last)
            part = await 异步获取QQ阅读正文批次(
                session,
                book_id,
                chapter_ids,
                解密信号量,
                请求信号量=请求信号量,
                解密材料=解密材料,
            )
            if isinstance(part, tuple) and len(part) == 3:
                part, response_items, decrypt_failed = part
                stats["response_items"] = int(response_items or 0)
                stats["decrypt_failed"] = int(decrypt_failed or 0)
            else:
                stats["response_items"] = len(part) if isinstance(part, list) else 0
            stats["valid_items"] = (
                sum(
                    1
                    for item in part[:expected]
                    if not _QQ阅读正文项失败原因(item)
                )
                if isinstance(part, list)
                else 0
            )
            stats["response_missing"] = max(
                0,
                expected - stats["response_items"],
            )
            return first, last, part, stats, None
        except asyncio.TimeoutError:
            stats["timeout_failed"] = 1
            return first, last, None, stats, {"category": "超时"}
        except aiohttp.ClientError as exc:
            stats["http_failed"] = 1
            status = getattr(exc, "status", 0)
            status = status if isinstance(status, int) and 100 <= status <= 599 else 0
            logger.debug(
                f"QQ阅读批量正文请求失败：书籍编号={book_id}, 范围={first}-{last}, "
                f"阶段=请求, HTTP状态={status or 'none'}, 错误={type(exc).__name__}"
            )
            return first, last, None, stats, {"category": "请求失败", "http_status": status}
        except _QQ阅读正文响应错误 as exc:
            stats["invalid_response"] = 1
            return first, last, None, stats, {
                "category": exc.category,
                "http_status": exc.http_status,
                "code": exc.code,
            }
        except Exception as exc:
            stats["other_failed"] = 1
            logger.debug(
                f"QQ阅读批量正文请求失败：书籍编号={book_id}, 范围={first}-{last}, "
                f"错误={type(exc).__name__}"
            )
            return first, last, None, stats, {"category": "响应处理失败"}

    initial_stats = 新建请求统计()
    for task in asyncio.as_completed([请求批次(a, b) for a, b in ranges]):
        first, last, part, stats, batch_failure = await task
        expected = last - first + 1
        success += 合并批次(first, last, part, results, batch_failure)
        合并请求统计(initial_stats, stats)
        completed += expected
        if completed < total:
            汇报进度(completed, success)

    logger.debug(
        f"QQ阅读正文首轮汇总：书籍编号={book_id}, 批次数={initial_stats['batches']}, "
        f"响应章节数={initial_stats['response_items']}/{total}, "
        f"有效章节数={initial_stats['valid_items']}, "
        f"响应缺失={initial_stats['response_missing']}, "
        f"解密失败={initial_stats['decrypt_failed']}, "
        f"请求失败={initial_stats['http_failed']}, "
        f"其他失败={initial_stats['other_failed']}, "
        f"超时={initial_stats['timeout_failed']}, "
        f"响应包无效={initial_stats['invalid_response']}"
    )

    for round_index in range(1, QQ阅读失败章节重试轮数 + 1):
        missing = [
            index + 1
            for index, item in enumerate(results)
            if _QQ阅读正文项失败原因(item)
        ]
        if not missing:
            break
        if round_index == 1:
            refreshed = await 确保QQ阅读密钥池(session, force=True)
            try:
                解密材料 = ConfigManager.get_instance().获取解密材料()
            except Exception:
                解密材料 = None
            logger.debug(
                f"QQ阅读正文密钥池刷新：书籍编号={book_id}, 成功={int(bool(refreshed))}"
            )
        retry_ranges = QQ阅读失败章节窗口(missing)
        retry_concurrency = 计算QQ阅读批量并发数(len(retry_ranges))
        logger.debug(
            f"QQ阅读失败章节重试：书籍编号={book_id}, 轮次={round_index}/{QQ阅读失败章节重试轮数}, "
            f"缺失={len(missing)}, 范围={格式化失败范围(missing)}, "
            f"窗口数={len(retry_ranges)}, 并发数={retry_concurrency}"
        )
        recovered = 0
        retry_semaphore = asyncio.Semaphore(retry_concurrency)

        async def 重试批次(
            first: int,
            last: int,
        ) -> tuple[int, int, list[Any] | None, dict[str, int], dict[str, Any] | None]:
            async with retry_semaphore:
                return await 请求批次(first, last)

        retry_stats = 新建请求统计()
        for task in asyncio.as_completed([重试批次(a, b) for a, b in retry_ranges]):
            first, last, part, stats, batch_failure = await task
            recovered += 合并批次(first, last, part, results, batch_failure)
            合并请求统计(retry_stats, stats)
        success = sum(1 for item in results if not _QQ阅读正文项失败原因(item))
        logger.debug(
            f"QQ阅读失败章节重试结果：书籍编号={book_id}, 轮次={round_index}/{QQ阅读失败章节重试轮数}, "
            f"恢复={recovered}, 仍缺失={total - success}, "
            f"响应章节数={retry_stats['response_items']}, "
            f"有效章节数={retry_stats['valid_items']}, "
            f"响应缺失={retry_stats['response_missing']}, "
            f"解密失败={retry_stats['decrypt_failed']}, "
            f"请求失败={retry_stats['http_failed']}, "
            f"其他失败={retry_stats['other_failed']}, "
            f"超时={retry_stats['timeout_failed']}, "
            f"响应包无效={retry_stats['invalid_response']}"
        )
        if success >= total or recovered <= 0:
            break
        if round_index < QQ阅读失败章节重试轮数:
            await asyncio.sleep(0.2 * round_index)

    success = sum(1 for item in results if not _QQ阅读正文项失败原因(item))
    汇报进度(total, success)
    chapters: list[dict[str, Any]] = []
    缺失章节号: list[int] = []
    缺失分类: dict[str, int] = {}
    失败HTTP状态: set[int] = set()
    失败业务码: set[str] = set()
    for 序号, (catalog_item, content) in enumerate(zip(catalog, results), start=1):
        reason = _QQ阅读正文项失败原因(content)
        if reason:
            缺失章节号.append(序号)
            failure = failure_reasons[序号 - 1] or {"category": reason}
            category = str(failure.get("category") or reason)
            缺失分类[category] = 缺失分类.get(category, 0) + 1
            if failure.get("http_status"):
                失败HTTP状态.add(int(failure["http_status"]))
            if failure.get("code"):
                失败业务码.add(str(failure["code"]))
            continue
        text = (
            content.decode("utf-8", "replace").strip()
            if isinstance(content, bytes)
            else str(content or "").strip()
        )
        chapters.append({**catalog_item, "content": text})
    if 缺失章节号:
        statuses = ",".join(str(status) for status in sorted(失败HTTP状态)) or "none"
        codes = ",".join(sorted(失败业务码)) or "none"
        logger.warning(
            f"QQ阅读正文缺失：书籍编号={book_id}, 缺失章节号={格式化失败范围(缺失章节号)}, "
            f"数量={len(缺失章节号)}, 分类={缺失分类}, "
            f"HTTP状态={statuses}, 业务码={codes}"
        )
        raise RuntimeError("章节不完整")
    return chapters


def 清理文件名(value: Any) -> str:
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(value or "").strip())
    return text.strip(" .") or "未知"


def 格式化字数(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "未知"
    normalized = re.sub(r"[\s,，]", "", text)
    if normalized.endswith("字"):
        normalized = normalized[:-1]
    number = _安全整数(normalized, -1)
    if number < 0:
        return text
    if number >= 10000:
        formatted = f"{number / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}万字"
    return f"{number}字"


def 生成小说文件名(book_id: str, details: dict[str, Any]) -> str:
    status = "完结" if "完" in str(details.get("status") or "") else "连载"
    title = 清理文件名(details.get("title") or f"QQ阅读{book_id}")
    author = 清理文件名(details.get("author") or "未知")
    return f"[{status}]书名：{title} 作者：{author}.txt"


def 生成小说文件内容(
    book_id: str,
    details: dict[str, Any],
    catalog: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
) -> tuple[str, bytes]:
    filename = 生成小说文件名(book_id, details)
    lines = [
        文件声明,
        "",
        f"名称：{details.get('title') or f'QQ阅读{book_id}'}",
        f"作者：{details.get('author') or '未知'}",
        f"状态：{details.get('status') or '连载'}",
        f"字数：{格式化字数(details.get('words_num'))}",
        f"书籍ID：{book_id}",
        f"章节数：{len(catalog)}",
        "",
    ]
    intro = str(details.get("intro") or "").strip()
    if intro:
        lines.extend(["简介：", intro, ""])
    for index, chapter in enumerate(chapters, start=1):
        title = str(chapter.get("title") or f"第{index}章").strip()
        content = 去除章节正文重复标题(title, chapter.get("content"))
        lines.extend([title, "", content, ""])
    text = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n")
    return filename, text.replace("\n", "\r\n").encode("utf-8")


def 格式化下载提示(details: dict[str, Any], catalog_count: int) -> str:
    return "\n".join(
        [
            f"书名：{details.get('title') or '未知'}",
            f"作者：{details.get('author') or '未知'}",
            f"状态：{details.get('status') or '连载'}",
            f"章节：{catalog_count} 章",
            f"字数：{格式化字数(details.get('words_num'))}",
            "",
            "正在下载中请稍等.....",
        ]
    )


def 生成不冲突缓存路径(filename: str) -> Path:
    小说缓存目录.mkdir(parents=True, exist_ok=True)
    safe_name = Path(清理文件名(filename)).name
    if not safe_name.lower().endswith(".txt"):
        safe_name = f"{safe_name}.txt"
    candidate = 小说缓存目录 / safe_name
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = 小说缓存目录 / f"{Path(safe_name).stem}_{index}.txt"
        if not candidate.exists():
            return candidate
    raise RuntimeError("下载缓存同名文件过多")


def 写入下载缓存文件(filename: str, content: bytes) -> Path:
    path = 生成不冲突缓存路径(filename)
    path.write_bytes(content)
    文件缓存工具.标记小说缓存正在使用(path)
    return path


def 删除小说缓存文件(path: Any) -> None:
    if not path:
        return
    文件缓存工具.删除小说缓存文件(path)


async def 准备发送文本文件(
    event: Any,
    filename: str,
    content: bytes,
    config: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    cache_path = 写入下载缓存文件(filename, content)
    if 小说网盘 is None:
        删除小说缓存文件(cache_path)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "小说网盘模块未加载",
        }
    try:
        upload = await 小说网盘.上传小说并获取分享链接(config, cache_path, filename)
        if not upload.get("success"):
            删除小说缓存文件(cache_path)
            return {
                "sent": False,
                "fallback_text": "",
                "source_cache_path": None,
                "error": str(upload.get("error") or "小说网盘上传失败"),
            }
        completed = await 小说网盘.发送小说下载完成链接(
            event,
            书名,
            作者,
            str(upload.get("share_url") or ""),
        )
        if completed.get("sent"):
            return {
                "sent": True,
                "fallback_text": "",
                "source_cache_path": cache_path,
                "error": "",
            }
        fallback_text = str(completed.get("fallback_text") or "")
        if fallback_text:
            return {
                "sent": False,
                "fallback_text": fallback_text,
                "source_cache_path": cache_path,
                "error": "",
            }
        删除小说缓存文件(cache_path)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "完成消息发送失败",
        }
    except Exception as exc:
        删除小说缓存文件(cache_path)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": type(exc).__name__,
        }


def 启动百度后台上传并清理源文件(config: Any, source_path: Any, filename: str) -> None:
    if not source_path:
        return

    async def upload_and_cleanup() -> None:
        try:
            if 百度网盘 is not None:
                result = await 百度网盘.后台上传小说文件(config, source_path, filename)
                if result.get("enabled") and not (
                    result.get("success") or result.get("skipped")
                ):
                    logger.warning(
                        f"QQ阅读百度网盘后台上传失败：文件={filename}, 错误=UploadFailed"
                    )
        except Exception as exc:
            logger.warning(
                f"QQ阅读百度网盘后台上传异常：文件={filename}, 错误={type(exc).__name__}"
            )
        finally:
            删除小说缓存文件(source_path)

    try:
        asyncio.create_task(upload_and_cleanup())
    except RuntimeError:
        删除小说缓存文件(source_path)


def 获取QQ阅读回复流(
    event: Any,
    命令文本: str,
    配置: Any = None,
) -> AsyncIterator[Any] | None:
    link = 提取QQ阅读链接(命令文本) or 提取QQ阅读事件链接(event)
    if link is None:
        return None
    return 生成下载回复流(event, link, 配置, 分享文本=命令文本)


async def 生成下载回复流(
    event: Any,
    来源: str,
    配置: Any = None,
    *,
    分享文本: str = "",
) -> AsyncIterator[Any]:
    """一次下载固定一个启用账号；后续切换和停用只影响新任务。"""
    try:
        登录态 = await asyncio.to_thread(_读取QQ阅读登录态, 配置)
    except Exception as exc:
        logger.warning("QQ阅读下载账号读取失败：错误类型=%s", type(exc).__name__)
        yield 下载失败提示
        return
    with QQ阅读账号上下文(登录态) as 下载配置:
        pass
    回复流 = _生成固定账号QQ阅读下载回复流(
        event, 来源, 配置, 分享文本=分享文本,
    )
    try:
        while True:
            token = _QQ阅读配置上下文.set(下载配置)
            try:
                try:
                    回复 = await anext(回复流)
                except StopAsyncIteration:
                    break
            finally:
                _QQ阅读配置上下文.reset(token)
            yield 回复
    finally:
        token = _QQ阅读配置上下文.set(下载配置)
        try:
            await 回复流.aclose()
        finally:
            _QQ阅读配置上下文.reset(token)


async def _生成固定账号QQ阅读下载回复流(
    event: Any,
    来源: str,
    配置: Any = None,
    *,
    分享文本: str = "",
) -> AsyncIterator[Any]:
    book_id = ""
    stage = "link"
    try:
        async with 创建QQ阅读HTTP会话(
            concurrency=max(
                QQ阅读批量最大动态并发数,
                QQ阅读出版书最大动态并发数,
            )
        ) as session:
            book_id = 解析书籍编号(来源) or await 解析QQ阅读分享页书籍编号(
                来源, session
            )
            if not book_id:
                分享书名 = 提取QQ阅读分享书名(分享文本 or 来源, 来源)
                if 分享书名:
                    book_id = await 按QQ阅读分享书名解析编号(分享书名)
            if not book_id:
                logger.warning("QQ阅读分享链接解析失败：错误分类=book_id_missing")
                yield 下载失败提示
                return

            stage = "details"
            try:
                details = await 获取参考书籍详情(book_id, session)
            except Exception as exc:
                logger.debug(f"QQ阅读参考详情获取失败：错误={type(exc).__name__}")
                details = {
                    "title": f"QQ阅读{book_id}",
                    "author": "未知",
                    "status": "连载",
                    "words_num": "",
                    "chapters": 0,
                    "free": None,
                    "intro": "",
                }

            stage = "account"
            account_vip = await 查询QQ阅读账号VIP状态(session)
            账号有VIP = bool(
                account_vip.get("available") and account_vip.get("is_vip")
            )
            VIP判断来源 = "账号接口" if account_vip.get("available") else "未验证"

            stage = "catalog"
            catalog, published = await 获取参考兼容目录(
                book_id,
                _安全整数(details.get("chapters")),
                session,
            )
            if not catalog:
                raise RuntimeError("目录为空")
            原始目录数 = len(catalog)
            付费类型 = 获取QQ阅读书籍付费类型(details, catalog)
            使用第三方正文 = not 账号有VIP and 付费类型 in {"free", "vip"}
            if 使用第三方正文:
                # 第三方接口的 s/e 使用原目录位置，不能使用筛选后重排的 index。
                catalog = _获取QQ阅读带原始序号目录(catalog)
            else:
                catalog = 获取QQ阅读可下载目录(details, catalog, 账号有VIP)
            if not catalog:
                yield 章节单独付费提示
                return
            details["chapters"] = len(catalog)
            正文来源 = "第三方正文接口" if 使用第三方正文 else "官方账号接口"
            logger.info(
                f"QQ阅读开始下载：书籍编号={book_id}, 书名={details.get('title')}, "
                f"作者={details.get('author')}, 章节数={len(catalog)}, "
                f"原始章节数={原始目录数}, 付费类型={付费类型}, "
                f"账号VIP={'是' if 账号有VIP else '否'}, "
                f"VIP判断={VIP判断来源}, "
                f"正文来源={正文来源}, "
                f"书籍类型={'published' if published else 'novel'}"
            )
            yield 格式化下载提示(details, len(catalog))

            stage = "content"
            if 使用第三方正文:
                chapters = await 下载QQ阅读第三方正文(book_id, catalog)
            else:
                chapters = (
                    await 下载参考出版书正文(book_id, catalog, session)
                    if published
                    else await 下载参考正文(book_id, catalog, session)
                )
                if published:
                    catalog = chapters
                    details["chapters"] = len(chapters)
        filename, content = 生成小说文件内容(book_id, details, catalog, chapters)
        logger.info(
            f"QQ阅读章节下载完成：书籍编号={book_id}, 书名={details.get('title')}, "
            f"成功={len(chapters)}, 总数={len(catalog)}, 文件大小={len(content)}"
        )

        stage = "upload"
        result = await 准备发送文本文件(
            event,
            filename,
            content,
            配置,
            书名=details.get("title"),
            作者=details.get("author"),
        )
        source_path = result.get("source_cache_path")
        if result.get("sent"):
            启动百度后台上传并清理源文件(配置, source_path, filename)
            return
        fallback_text = str(result.get("fallback_text") or "")
        if fallback_text:
            try:
                yield fallback_text
            finally:
                启动百度后台上传并清理源文件(配置, source_path, filename)
            return
        yield 文件发送失败提示
    except Exception as exc:
        logger.warning(
            f"QQ阅读参考下载失败：书籍编号={book_id}, 阶段={stage}, 错误={type(exc).__name__}"
        )
        yield 下载失败提示




class QQ阅读扫码登录客户端:
    """复用 QQ阅读当前 QQConnect 登录链；每个实例持有独立 Cookie 会话。"""

    _允许主机 = frozenset({
        "login.book.qq.com", "book.qq.com", "passport.yuewen.com",
        "ptlogin.yuewen.com", "ptlogin.qidian.com", "passport.qidian.com",
        "graph.qq.com", "xui.ptlogin2.qq.com", "ssl.ptlogin2.qq.com",
        "ptlogin2.qq.com", "ui.ptlogin2.qq.com",
    })
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._closed = False
        self._expires_at = 0.0
        self._oauth: dict[str, str] = {}
        self._graph_url = ""
        self._oauth_openapi = "#"
        self._xlogin_url = ""
        self._pt: dict[str, str] = {}
        self.status = "created"
        self.诊断阶段 = "created"
        self.HTTP状态: int | None = None
        self.轮询状态: str | None = None
        self.业务码: str | None = None

    def _设置诊断阶段(self, 阶段: str) -> None:
        self.诊断阶段 = 阶段
        self.HTTP状态 = None
        self.业务码 = None

    def _记录业务码(self, value: Any) -> None:
        if type(value) is int and -10**12 < value < 10**12:
            value = str(value)
        self.业务码 = value if type(value) is str and re.fullmatch(r"-?[0-9]{1,12}", value) else None

    @staticmethod
    def _提取授权选项(text: str) -> str:
        from html.parser import HTMLParser

        class 授权选项解析器(HTMLParser):
            def __init__(self) -> None:
                super().__init__(convert_charrefs=True)
                self.values: list[str] = []

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                fields = dict(attrs)
                if tag != "input" or fields.get("name") != "api_choose":
                    return
                if "checked" not in fields and "disabled" not in fields:
                    return
                value = fields.get("value")
                if value is None or not re.fullmatch(r"[0-9]{1,12}", value):
                    raise RuntimeError("qqreader_qr_provider_fields_missing")
                self.values.append(value)

        parser = 授权选项解析器()
        parser.feed(text)
        parser.close()
        return "_".join(parser.values) or "#"

    @classmethod
    def _校验地址(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https" or parsed.hostname not in cls._允许主机
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
            ):
                raise ValueError
        except (TypeError, ValueError):
            raise RuntimeError("qqreader_qr_redirect_invalid") from None
        return value

    async def _请求(
        self, method: str, url: str, *, data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[str, bytes, list[tuple[str, bytes]]]:
        if self._closed or self._session is None:
            raise RuntimeError("qqreader_qr_closed")
        frames: list[tuple[str, bytes]] = []
        for _ in range(10):
            self._校验地址(url)
            self.HTTP状态 = None
            async with self._session.request(
                method, url, data=data, headers=headers, allow_redirects=False,
            ) as response:
                self.HTTP状态 = response.status
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    size += len(chunk)
                    if size > 1024 * 1024:
                        raise RuntimeError("qqreader_qr_response_large")
                    chunks.append(chunk)
                body = b"".join(chunks)
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location", "")
                    if not location or (method != "GET" and response.status in {307, 308}):
                        raise RuntimeError("qqreader_qr_redirect_invalid")
                    frames.append((str(response.url), body))
                    url = self._校验地址(urljoin(str(response.url), location))
                    method, data, headers = "GET", None, None
                    continue
                if response.status != 200:
                    raise RuntimeError("qqreader_qr_http_error")
                frames.append((str(response.url), body))
                return str(response.url), body, frames
        raise RuntimeError("qqreader_qr_redirect_limit")

    def _读取Cookie(self, name: str, url: str) -> str:
        if self._session is None:
            return ""
        from yarl import URL

        cookie = self._session.cookie_jar.filter_cookies(URL(url)).get(name)
        return cookie.value if cookie else ""

    @staticmethod
    def _解析回调(text: str) -> list[str]:
        import ast

        match = re.fullmatch(r"\s*ptuiCB\((.{0,16384})\)\s*;?\s*", text, re.S)
        if not match:
            raise RuntimeError("qqreader_qr_callback_invalid")
        try:
            values = ast.literal_eval("(" + match.group(1) + ",)")
        except (SyntaxError, ValueError, TypeError, RecursionError):
            raise RuntimeError("qqreader_qr_callback_invalid") from None
        if not isinstance(values, tuple) or not 5 <= len(values) <= 10 or not all(
            isinstance(value, str) for value in values
        ):
            raise RuntimeError("qqreader_qr_callback_invalid")
        return list(values)

    @staticmethod
    def _提取页面数据(text: str) -> dict[str, Any] | None:
        match = re.search(r"\bvar\s+data\s*=\s*(\{)", text)
        if not match:
            return None
        try:
            data, _ = json.JSONDecoder().raw_decode(text[match.start(1):])
        except (ValueError, TypeError, RecursionError):
            return None
        return data if isinstance(data, dict) else None

    async def 获取登录二维码(self) -> bytes:
        if self._closed or self._session is not None:
            raise RuntimeError("qqreader_qr_session_started")
        self._session = aiohttp.ClientSession(
            headers={"User-Agent": self._UA},
            timeout=aiohttp.ClientTimeout(total=20, sock_connect=8, sock_read=15),
            connector=aiohttp.TCPConnector(limit=2, ttl_dns_cache=300),
            cookie_jar=aiohttp.CookieJar(),
        )
        try:
            login_params = {
                "appId": "1450000219", "areaId": "10", "tab": "qq",
                "returnurl": "https://book.qq.com/loginSuccess", "popup": "1",
                "ticket": "1", "target": "iframe", "version": "1.0",
                "unionshow": "00001",
            }
            self._设置诊断阶段("login_page")
            _, body, _ = await self._请求(
                "GET", "https://login.book.qq.com/login.html?" + urlencode(login_params),
            )
            page = body.decode("utf-8", "replace")
            button = re.search(
                r'href-value="([^"]{1,8192})"\s+id="qqLoginButton"', page,
            )
            if not button:
                raise RuntimeError("qqreader_qr_entry_missing")
            entry = self._校验地址(html.unescape(button.group(1)))
            if urlsplit(entry).hostname != "ptlogin.yuewen.com" or urlsplit(entry).path != "/login/qqconnectlogin":
                raise RuntimeError("qqreader_qr_entry_invalid")
            self._设置诊断阶段("qq_entry")
            self._graph_url, body, _ = await self._请求("GET", entry)
            self.诊断阶段 = "oauth_page"
            graph = urlsplit(self._graph_url)
            if graph.hostname != "graph.qq.com" or graph.path != "/oauth2.0/show":
                raise RuntimeError("qqreader_qr_oauth_entry_invalid")
            self._oauth = {key: value[-1] for key, value in parse_qs(graph.query).items() if value}
            if self._oauth.get("client_id") != "101481755" or self._oauth.get("response_type") != "code":
                raise RuntimeError("qqreader_qr_oauth_app_invalid")
            redirect = self._校验地址(self._oauth.get("redirect_uri", ""))
            if urlsplit(redirect).hostname != "ptlogin.qidian.com" or urlsplit(redirect).path != "/login/qqconnectcallback":
                raise RuntimeError("qqreader_qr_oauth_callback_invalid")
            graph_text = body.decode("utf-8", "replace")
            if not re.search(r"xlogin\?appid=716027609&daid=383", graph_text):
                raise RuntimeError("qqreader_qr_provider_changed")
            self._oauth_openapi = self._提取授权选项(graph_text)
            params = {
                "appid": "716027609", "daid": "383", "style": "33",
                "login_text": "登录", "hide_title_bar": "1", "hide_border": "1",
                "target": "self", "s_url": "https://graph.qq.com/oauth2.0/login_jump",
                "pt_3rd_aid": self._oauth["client_id"], "theme": "2",
            }
            self._设置诊断阶段("ptlogin_page")
            self._xlogin_url, body, _ = await self._请求(
                "GET", "https://xui.ptlogin2.qq.com/cgi-bin/xlogin?" + urlencode(params),
            )
            pt_page = body.decode("utf-8", "replace")
            version = re.search(r'ptui_version:encodeURIComponent\("(\d{4,32})"\)', pt_page)
            style = re.search(r'style:encodeURIComponent\("(\d{1,3})"\)', pt_page)
            if not version or not style or not self._读取Cookie("pt_login_sig", self._xlogin_url):
                raise RuntimeError("qqreader_qr_provider_fields_missing")
            self._pt = {"version": version.group(1), "style": style.group(1)}
            qr_params = {
                "appid": "716027609", "e": "2", "l": "M", "s": "3",
                "d": "72", "v": "4", "t": str(secrets.randbelow(10**15) / 10**15),
                "daid": "383", "pt_3rd_aid": self._oauth["client_id"],
                "u1": "https://graph.qq.com/oauth2.0/login_jump",
            }
            self._设置诊断阶段("qr_image")
            _, image, _ = await self._请求(
                "GET", "https://xui.ptlogin2.qq.com/ssl/ptqrshow?" + urlencode(qr_params),
                headers={"Referer": self._xlogin_url},
            )
            if not image.startswith(b"\x89PNG\r\n\x1a\n") or not self._读取Cookie(
                "qrsig", "https://xui.ptlogin2.qq.com/ssl/ptqrlogin",
            ):
                raise RuntimeError("qqreader_qr_image_invalid")
            self.status = "waiting"
            self._expires_at = time.monotonic() + 300
            return image
        except BaseException:
            await self.关闭()
            raise

    async def _交换阅读登录态(self, jump_url: str) -> dict[str, str]:
        self.status = "authorizing"
        self._设置诊断阶段("login_jump")
        _, _, frames = await self._请求("GET", self._校验地址(jump_url))
        skey = self._读取Cookie("p_skey", "https://graph.qq.com/")
        if not skey:
            raise RuntimeError("qqreader_qr_oauth_cookie_missing")
        token = 5381
        for char in skey:
            token = (token * 33 + ord(char)) & 0x7FFFFFFF
        data = {key: self._oauth.get(key, "") for key in (
            "response_type", "client_id", "redirect_uri", "scope", "state", "switch",
        )}
        data.update({
            "from_ptlogin": "1", "src": "1", "update_auth": "1", "openapi": self._oauth_openapi,
            "g_tk": str(token), "auth_time": str(int(time.time() * 1000)),
            "ui": secrets.token_hex(16).upper(),
        })
        # 授权 POST 只提交一次；错误及取消均不自动重放。
        self._设置诊断阶段("oauth_authorize")
        final_url, body, more = await self._请求(
            "POST", "https://graph.qq.com/oauth2.0/authorize", data=data,
            headers={"Referer": self._graph_url, "Origin": "https://graph.qq.com"},
        )
        frames.extend(more)
        if urlsplit(final_url).hostname == "graph.qq.com":
            text = body.decode("utf-8", "replace")
            code = re.search(r'"ret"\s*:\s*"?(-?[0-9]{1,12})"?(?=\s*[,}])', text)
            self._记录业务码(code.group(1) if code else None)
            match = re.search(r'"callback"\s*:\s*("(?:[^"\\]|\\.){1,16384}")', text)
            if not match:
                raise RuntimeError("qqreader_qr_oauth_authorize_failed")
            callback = json.loads(match.group(1))
            if urlsplit(self._校验地址(callback)).hostname != "ptlogin.qidian.com":
                raise RuntimeError("qqreader_qr_oauth_callback_invalid")
            self._设置诊断阶段("reader_callback")
            final_url, body, more = await self._请求("GET", callback)
            frames.extend(more)
        guid, key, ticket = "", "", ""
        landing = ""
        for frame_url, frame_body in frames:
            parsed_url = urlsplit(frame_url)
            if parsed_url.hostname == "book.qq.com" and parsed_url.path == "/loginSuccess":
                query = parse_qs(parsed_url.query)
                guid = (query.get("ywguid") or [guid])[-1]
                ticket = (query.get("ticket") or [ticket])[-1]
                landing = frame_url
            if parsed_url.hostname not in {"ptlogin.qidian.com", "ptlogin.yuewen.com", "passport.yuewen.com", "passport.qidian.com"}:
                continue
            page_data = self._提取页面数据(frame_body.decode("utf-8", "replace"))
            if not page_data:
                continue
            self.诊断阶段 = "reader_callback"
            callback_data = page_data.get("callbackData")
            self._记录业务码(callback_data.get("code") if isinstance(callback_data, dict) else None)
            if not isinstance(callback_data, dict) or str(callback_data.get("code")) != "0":
                raise RuntimeError("qqreader_qr_reader_callback_failed")
            details = callback_data.get("data")
            if not isinstance(details, dict):
                raise RuntimeError("qqreader_qr_reader_callback_invalid")
            guid = str(details.get("ywGuid") or guid)
            key = str(details.get("ywKey") or key)
            ticket = str(details.get("ticket") or ticket)
            redirect = details.get("302url") or callback_data.get("302url")
            if redirect and not key:
                redirect = self._校验地址(str(redirect))
                _, _, extra = await self._请求("GET", redirect)
                for target_url, _ in extra:
                    target = urlsplit(target_url)
                    if target.hostname == "book.qq.com" and target.path == "/loginSuccess":
                        query = parse_qs(target.query)
                        guid = (query.get("ywguid") or [guid])[-1]
                        ticket = (query.get("ticket") or [ticket])[-1]
                        landing = target_url
        if not key and guid and ticket:
            self._设置诊断阶段("ticket_exchange")
            _, body, _ = await self._请求(
                "GET", "https://book.qq.com/api/authen/getKeyByTicket",
                headers={"ywguid": guid, "ywTicket": ticket, "Referer": landing or "https://book.qq.com/loginSuccess"},
            )
            try:
                result = json.loads(body)
            except (ValueError, TypeError):
                raise RuntimeError("qqreader_qr_ticket_invalid") from None
            self._记录业务码(result.get("code") if isinstance(result, dict) else None)
            if not isinstance(result, dict) or str(result.get("code")) != "0" or not isinstance(result.get("data"), dict):
                raise RuntimeError("qqreader_qr_ticket_failed")
            key = str(result["data"].get("ywkey") or "")
        self.诊断阶段 = "credentials"
        if not re.fullmatch(r"[1-9]\d{5,31}", guid) or not re.fullmatch(
            r"[^\s;,\"']{6,256}", key
        ) or any(ord(char) < 33 or ord(char) == 127 for char in key):
            raise RuntimeError("qqreader_qr_reader_credentials_missing")
        self.status = "confirmed"
        self.诊断阶段 = "confirmed"
        return {"ywguid": guid, "ywkey": key}

    async def 等待登录并获取登录态(self, timeout: float = 300, interval: float = 2) -> dict[str, str]:
        if self.status != "waiting" or self._session is None or self._closed:
            raise RuntimeError("qqreader_qr_not_started")
        deadline = min(self._expires_at, time.monotonic() + max(1, min(float(timeout), 300)))
        qrsig = self._读取Cookie("qrsig", "https://xui.ptlogin2.qq.com/ssl/ptqrlogin")
        token = 0
        for char in qrsig:
            token = (token * 33 + ord(char)) & 0x7FFFFFFF
        try:
            while not self._closed and time.monotonic() < deadline:
                params = {
                    "u1": "https://graph.qq.com/oauth2.0/login_jump", "ptqrtoken": str(token),
                    "ptredirect": "0", "h": "1", "t": "1", "g": "1", "from_ui": "1",
                    "ptlang": "2052", "action": "0-0-" + str(int(time.time() * 1000)),
                    "js_ver": self._pt["version"], "js_type": "1",
                    "login_sig": self._读取Cookie("pt_login_sig", self._xlogin_url),
                    "pt_uistyle": self._pt["style"], "aid": "716027609", "daid": "383",
                    "pt_3rd_aid": self._oauth["client_id"],
                }
                self._设置诊断阶段("poll")
                _, body, _ = await self._请求(
                    "GET", "https://xui.ptlogin2.qq.com/ssl/ptqrlogin?" + urlencode(params),
                    headers={"Referer": self._xlogin_url},
                )
                result = self._解析回调(body.decode("utf-8", "replace"))
                self.轮询状态 = result[0] if re.fullmatch(r"-?[0-9]{1,12}", result[0]) else None
                if result[0] == "0":
                    return await self._交换阅读登录态(result[2])
                if result[0] == "65":
                    self.status = "expired"
                    raise TimeoutError("qqreader_qr_expired")
                if result[0] == "67":
                    self.status = "scanned"
                elif result[0] == "66":
                    self.status = "waiting"
                else:
                    self.status = "failed"
                    raise RuntimeError("qqreader_qr_authorization_required")
                await asyncio.sleep(max(2, min(float(interval), 10)))
            self.status = "expired"
            raise TimeoutError("qqreader_qr_expired")
        finally:
            await self.关闭()

    async def 关闭(self) -> None:
        self._closed = True
        if self._session is not None:
            self._session.cookie_jar.clear()
            await self._session.close()
            self._session = None
        self._oauth.clear()
        self._oauth_openapi = "#"
        self._pt.clear()



class QQ阅读手机号登录客户端:
    """当前官网手机号登录；Cookie 和两阶段 sessionKey 只保留于本实例。"""

    _回调 = "mantouReaderSms"
    _官网地址 = "https://login.book.qq.com/login.html"
    _接口地址 = "https://ptlogin.yuewen.com"

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._closed = False
        self._phone = ""
        self._challenge_key = ""
        self._sms_key = ""
        self._captcha_app_id = ""
        self._config: dict[str, Any] = {}
        self._deadline = 0.0
        self._lock = asyncio.Lock()
        self.status = "created"

    def _检查有效(self) -> None:
        if self._closed or self._session is None:
            raise RuntimeError("qqreader_sms_closed")
        if self._deadline and time.monotonic() >= self._deadline:
            self.status = "expired"
            self._challenge_key = self._sms_key = ""
            raise TimeoutError("qqreader_sms_expired")

    async def _读取(self, url: str) -> bytes:
        self._检查有效()
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in {
            "login.book.qq.com", "ptlogin.yuewen.com", "book.qq.com",
            "ywloginstatic.yuewen.com",
        } or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise RuntimeError("qqreader_sms_address_invalid")
        assert self._session is not None
        async with self._session.get(
            url, allow_redirects=False,
            headers={"Referer": self._官网地址},
        ) as response:
            if response.status != 200:
                raise RuntimeError("qqreader_sms_http_error")
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.content.iter_chunked(64 * 1024):
                size += len(chunk)
                if size > 1024 * 1024:
                    raise RuntimeError("qqreader_sms_response_large")
                chunks.append(chunk)
        self._检查有效()
        return b"".join(chunks)

    async def _初始化(self) -> None:
        params = {
            "appId": "1450000219", "areaId": "10", "tab": "phone",
            "returnurl": "https://book.qq.com/loginSuccess", "popup": "1",
            "ticket": "1", "target": "iframe", "version": "1.0",
            "unionshow": "00001",
        }
        page = (await self._读取(self._官网地址 + "?" + urlencode(params))).decode("utf-8", "replace")
        match = re.search(r"\bLoginV1\.init\(\s*(\{)", page)
        if not match:
            raise RuntimeError("qqreader_sms_config_missing")
        try:
            config, _ = json.JSONDecoder().raw_decode(page[match.start(1):])
        except (ValueError, TypeError, RecursionError):
            raise RuntimeError("qqreader_sms_config_invalid") from None
        if not isinstance(config, dict) or (
            str(config.get("appId")) != "1450000219"
            or str(config.get("areaId")) != "10"
            or config.get("baseUrl") != self._接口地址
            or config.get("returnUrl") != "https://book.qq.com/loginSuccess"
            or not _是真值(config.get("usePhone"))
        ):
            raise RuntimeError("qqreader_sms_provider_changed")
        script = re.search(
            r'<script\b[^>]*\bsrc=["\']((?:https:)?//ywloginstatic\.yuewen\.com/js4/login\.js(?:\?[^"\']*)?)["\']',
            page, re.I,
        )
        if not script:
            raise RuntimeError("qqreader_sms_script_missing")
        script_url = html.unescape(script.group(1))
        if script_url.startswith("//"):
            script_url = "https:" + script_url
        javascript = (await self._读取(script_url)).decode("utf-8", "replace")
        captcha = re.search(r'\bcaptchaAppId\s*:\s*["\'](\d{6,14})["\']', javascript)
        if not captcha or not all(re.search(pattern, javascript) for pattern in (
            r'["\']phoneSendMsg["\']\s*:\s*["\']/userSdk/sendmsgnew["\']',
            r'["\']phoneCodeLogin["\']\s*:\s*["\']/userSdk/phonecodelogin["\']',
        )):
            raise RuntimeError("qqreader_sms_script_changed")
        self._config = config
        self._captcha_app_id = captcha.group(1)

    def _基础参数(self) -> dict[str, str]:
        config = self._config
        return {
            "appId": "1450000219", "areaId": "10",
            "source": str(config.get("source") or ""),
            "returnurl": "https://book.qq.com/loginSuccess",
            "version": str(config.get("version") or "1.0"),
            "imei": str(config.get("imei") or ""),
            "qimei": str(config.get("qimei") or ""),
            "target": str(config.get("target") or "iframe"),
            "ticket": str(config.get("ticket") or "1"),
            "autotime": str(config.get("autoTime") or "14"),
            "jumpdm": str(config.get("jumpdm") or ""),
            "ajaxdm": str(config.get("ajaxdm") or "yuewen"),
            "auto": str(config.get("autoLoginFlag") or "0"),
            "sdkversion": str(config.get("sdkversion") or ""),
            "format": "jsonp", "method": self._回调,
        }

    async def _请求JSONP(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        if endpoint not in {"sendmsgnew", "phonecodelogin"}:
            raise RuntimeError("qqreader_sms_endpoint_invalid")
        payload = (await self._读取(
            self._接口地址 + "/userSdk/" + endpoint + "?" + urlencode(params)
        )).decode("utf-8", "strict")
        wrapper = re.fullmatch(r"\s*" + re.escape(self._回调) + r"\((.*)\)\s*;?\s*", payload, re.S)
        try:
            data = json.loads(wrapper.group(1) if wrapper else payload)
        except (ValueError, TypeError, RecursionError):
            raise RuntimeError("qqreader_sms_json_invalid") from None
        if not isinstance(data, dict) or str(data.get("code")) != "0":
            if isinstance(data, dict) and str(data.get("code")) in {"-11003", "-10092"}:
                self.status = "expired"
                self._challenge_key = self._sms_key = ""
            raise ValueError("qqreader_sms_request_rejected")
        result = data.get("data")
        if not isinstance(result, dict):
            raise RuntimeError("qqreader_sms_data_invalid")
        return result

    def _处理发送结果(self, result: dict[str, Any]) -> dict[str, Any]:
        key = result.get("sessionKey")
        if not isinstance(key, str) or not 1 <= len(key) <= 8192 or any(ord(ch) < 32 for ch in key):
            raise RuntimeError("qqreader_sms_session_missing")
        action = str(result.get("nextAction"))
        self._sms_key = ""
        if action == "0":
            self._challenge_key = ""
            self._sms_key = key
            self.status = "sent"
            self._deadline = time.monotonic() + 300
            return {"challenge_required": False, "sent": True}
        if action == "11":
            script = str(result.get("imgSrc") or "")
            if "TCaptcha.js" not in script:
                raise RuntimeError("qqreader_sms_challenge_changed")
            self._challenge_key = key
            self.status = "challenge"
            return {"challenge_required": True, "sent": False,
                    "captcha_app_id": self._captcha_app_id}
        raise RuntimeError("qqreader_sms_challenge_unrecognized")

    async def 预请求(self, 手机号: str) -> dict[str, Any]:
        phone = str(手机号 or "").strip()
        if not re.fullmatch(r"1\d{10}", phone):
            raise ValueError("qqreader_sms_phone_invalid")
        async with self._lock:
            if self._closed or self._session is not None:
                raise RuntimeError("qqreader_sms_already_started")
            self._phone = phone
            self._deadline = time.monotonic() + 300
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": QQ阅读扫码登录客户端._UA},
                timeout=aiohttp.ClientTimeout(total=15, sock_connect=5, sock_read=10),
                connector=aiohttp.TCPConnector(limit=2, ttl_dns_cache=300),
                cookie_jar=aiohttp.CookieJar(),
            )
            try:
                await self._初始化()
                params = self._基础参数()
                params.update({"phoneIsAbroad": "0", "auto": "",
                               "inputUserId": "+86" + phone, "sessionKey": "",
                               "type": "1", "validateCode": "", "needRegister": "0"})
                return self._处理发送结果(await self._请求JSONP("sendmsgnew", params))
            except BaseException:
                await self.关闭()
                raise

    async def 确认发送(self, ticket: str, randstr: str) -> dict[str, Any]:
        async with self._lock:
            self._检查有效()
            if self.status != "challenge" or not self._challenge_key:
                raise RuntimeError("qqreader_sms_challenge_required")
            values = (ticket, randstr)
            if any(not isinstance(value, str) or not 1 <= len(value) <= 8192
                   or any(ord(ch) < 33 or ord(ch) == 127 or ch == ";" for ch in value)
                   for value in values):
                raise ValueError("qqreader_sms_challenge_invalid")
            params = self._基础参数()
            params.update({"phoneIsAbroad": "0", "mobilePhone": self._phone,
                           "inputUserId": "+86" + self._phone,
                           "sessionKey": self._challenge_key, "type": "1",
                           "validateCode": randstr + ";" + ticket, "needRegister": "0"})
            return self._处理发送结果(await self._请求JSONP("sendmsgnew", params))

    async def 验证登录(self, 验证码: str) -> dict[str, str]:
        code = str(验证码 or "").strip()
        if not re.fullmatch(r"\d{4,8}", code):
            raise ValueError("qqreader_sms_code_invalid")
        async with self._lock:
            self._检查有效()
            if self.status != "sent" or not self._sms_key:
                raise RuntimeError("qqreader_sms_not_sent")
            params = self._基础参数()
            params.update({"inputUserId": self._phone, "sessionKey": self._sms_key,
                           "validateCode": code})
            result = await self._请求JSONP("phonecodelogin", params)
            login = 解析QQ阅读Cookie(json.dumps({
                "ywguid": result.get("ywGuid"), "ywkey": result.get("ywKey"),
            }))
            if not login:
                raise RuntimeError("qqreader_sms_credentials_missing")
            self.status = "confirmed"
            await self.关闭()
            return login

    async def 关闭(self) -> None:
        self._closed = True
        self._phone = self._challenge_key = self._sms_key = ""
        self._config.clear()
        if self._session is not None:
            self._session.cookie_jar.clear()
            await self._session.close()
            self._session = None
