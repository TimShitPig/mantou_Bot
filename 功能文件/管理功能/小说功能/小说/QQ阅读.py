# -*- coding: utf-8 -*-
"""QQ阅读参考核心及 AstrBot 下载适配。

依赖: aiohttp, pycryptodome, bcrypt
账号配置: 文件内 CONFIG 字典（仅鉴权必要字段）
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
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
import xml.etree.ElementTree as ET
import zlib
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
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

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

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
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
    "usid": "ywIWoPGBmOeI",
    "uid": "855131499808",
    "fuid": "89306811035542cd868d49def7d3857d",
}

_固定配置已加载 = False
_固定配置加载锁 = threading.Lock()


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
        ConfigManager.get_instance().apply(CONFIG)
        _固定配置已加载 = True


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
    return await loop.run_in_executor(_获取QQ阅读解密执行器(), 函数, *参数)


async def 异步构造QQ阅读鉴权请求头(
    timestamp_ms: int,
    request_url: str | None = None,
) -> Dict[str, str]:
    """把 csigs/网关签名移出事件循环，避免阻塞网页和消息事件。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _获取QQ阅读签名执行器(),
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
        for candidate in _QQ阅读章节文件候选键(str(name)):
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
    members = tar_decrypt(package)
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
    result = [
        chapter_map.get(chapter_id, "章节解密失败") for chapter_id in requested_ids
    ]
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
        for x in pwd:
            self.update(x)

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
        for i, c in enumerate(data):
            p = c ^ self.dec_byte()
            self.update(p)
            out[i] = p
        return bytes(out)


def _查找下一个ZIP标记(data: bytes, start: int) -> int:
    positions = [
        data.find(signature, start)
        for signature in (b"PK\x03\x04", b"PK\x01\x02", b"PK\x05\x06")
    ]
    valid = [position for position in positions if position >= 0]
    return min(valid) if valid else -1


def extract_zip_entries_manual(zdata: bytes, pwd: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    pos = 0
    while pos + 30 <= len(zdata):
        sig = struct.unpack_from("<I", zdata, pos)[0]
        if sig in (0x02014B50, 0x06054B50):
            break
        if sig != 0x04034B50:
            break
        _ver, flag, method, _t, _d, _crc, csize, _usize, nlen, xlen = (
            struct.unpack_from("<HHHHHIIIHH", zdata, pos + 4)
        )
        name = zdata[pos + 30 : pos + 30 + nlen]
        data_off = pos + 30 + nlen + xlen
        if data_off > len(zdata):
            break
        data_end = data_off + csize
        if csize == 0 or data_end > len(zdata):
            next_pos = _查找下一个ZIP标记(zdata, data_off)
            if next_pos < data_off:
                break
            data_end = next_pos
        payload = zdata[data_off:data_end]
        pos = data_end
        if csize and flag & 0x8:
            if zdata[pos : pos + 4] == b"PK\x07\x08":
                pos += 16
            elif pos + 12 <= len(zdata):
                pos += 12
        name_s = name.decode("utf-8", "replace")
        if flag & 1:
            if len(payload) < 12:
                raise ValueError(f"encrypted entry too short: {name_s}")
            body = ZipCrypto(pwd).decrypt(payload)[12:]
        else:
            body = payload
        if method == 0:
            plain = body
        elif method == 8:
            plain = zlib.decompress(body, -15)
        else:
            raise ValueError(f"unsupported method {method}")
        out.append((name_s, plain))
    if not out:
        raise ValueError("no local zip entries")
    return out


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
    return extract_zip_entries_manual(zdata, pwd)


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
QQ阅读免费正文地址 = "http://154.12.91.167:7000/content"
QQ阅读免费正文批量章节数 = 200
QQ阅读免费正文最大动态并发数 = 16
QQ阅读进度日志分段数 = 10
QQ阅读链接正则 = re.compile(r"https?://[^\s'\"<>，。]+", re.I)
QQ阅读允许域名 = ("reader.qq.com", "book.qq.com")
QQ阅读登录态命名空间 = "qq_reader_auth"
QQ阅读登录态状态键 = "login_state"
下载缓存目录 = 小说缓存工具.下载缓存目录
文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。"
    "如喜欢本书，请支持正版。"
)
下载失败提示 = "下载失败 请重试"
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
    return bool(re.search(r"\byw(?:guid|key)\b", str(文本 or ""), re.I))


def _从CookieJSON提取(data: Any, result: dict[str, str]) -> None:
    if isinstance(data, list):
        for item in data:
            _从CookieJSON提取(item, result)
        return
    if not isinstance(data, dict):
        return
    name = str(data.get("name") or "").strip().lower()
    if name in {"ywguid", "ywkey"} and data.get("value") is not None:
        result[name] = str(data["value"]).strip()
    for key, value in data.items():
        lowered = str(key).strip().lower()
        if lowered in {"ywguid", "ywkey"} and isinstance(value, (str, int)):
            result[lowered] = str(value).strip()
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
    for name in ("ywguid", "ywkey"):
        match = re.search(
            rf"(?:^|[;\s'\"`]){name}\s*[:=]\s*([^;\s'\"`]+)",
            raw,
            re.I,
        )
        if match:
            result[name] = match.group(1).strip()
    ywguid = result.get("ywguid", "")
    ywkey = result.get("ywkey", "")
    if not re.fullmatch(r"\d{6,32}", ywguid):
        return None
    if not re.fullmatch(r"[^\s;,\"']{6,256}", ywkey):
        return None
    return {"ywguid": ywguid, "ywkey": ywkey}


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


def 初始化参考核心() -> ConfigManager:
    load_config_once()
    return ConfigManager.get_instance()


def _应用QQ阅读登录态(登录态: dict[str, str]) -> None:
    config = 初始化参考核心()
    config.uid = 登录态["ywguid"]
    config.usid = 登录态["ywkey"]


def _读取QQ阅读登录态(配置: Any) -> dict[str, str] | None:
    raw = 读取运行状态值(配置, QQ阅读登录态命名空间, QQ阅读登录态状态键, "")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return 解析QQ阅读Cookie(
        f"ywguid={data.get('ywguid') or data.get('uid') or ''};"
        f"ywkey={data.get('ywkey') or data.get('usid') or ''};"
    )


def _保存QQ阅读登录态(配置: Any, 登录态: dict[str, str]) -> None:
    payload = json.dumps(
        {
            "ywguid": 登录态["ywguid"],
            "ywkey": 登录态["ywkey"],
            "updated_at": int(time.time()),
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    写入运行状态值(配置, QQ阅读登录态命名空间, QQ阅读登录态状态键, payload)


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
    await asyncio.to_thread(_应用QQ阅读登录态, 登录态)
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
        return "QQ阅读Cookie无效，请同时提供有效的ywguid和ywkey"
    if not 已配置运行状态数据库(配置):
        return "数据库未配置，QQ阅读Cookie未保存"
    try:
        await asyncio.to_thread(_保存QQ阅读登录态, 配置, 登录态)
        await asyncio.to_thread(_应用QQ阅读登录态, 登录态)
    except Exception as exc:
        logger.warning(f"QQ阅读Cookie保存失败：错误={type(exc).__name__}")
        return "QQ阅读Cookie保存失败，请稍后再试"
    return "QQ阅读Cookie已保存并覆盖原登录态"


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
    except (TypeError, ValueError):
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
        title = str(
            info.get("title") or info.get("bookName") or card.get("title") or ""
        ).strip()
        if not book_id.isdigit() or not title:
            continue
        result.append(
            {
                "platform": "QQ阅读",
                "book_id": book_id,
                "title": title,
                "author": str(
                    info.get("author") or card.get("author") or "未知"
                ).strip()
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
    if not has_paid_chapter and not has_free_limit:
        return "free"
    if _是真值(details.get("vip_free")):
        return "vip"
    return "single"


def 是章节单独付费书籍(details: dict[str, Any], catalog: list[dict[str, Any]]) -> bool:
    return 获取QQ阅读书籍付费类型(details, catalog) == "single"


def 获取QQ阅读可下载目录(
    details: dict[str, Any], catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """免费书取全量，VIP 账号只对 VIP 书取全量，单章付费始终只取免费章。"""
    def 带原始序号() -> list[dict[str, Any]]:
        结果: list[dict[str, Any]] = []
        for 位置, 项目 in enumerate(catalog, start=1):
            复制 = dict(项目)
            复制.setdefault("_qq_source_index", 位置)
            结果.append(复制)
        return 结果

    付费类型 = 获取QQ阅读书籍付费类型(details, catalog)
    if 付费类型 == "free" or (
        付费类型 == "vip" and _是真值(details.get("is_vip"))
    ):
        return 带原始序号()
    max_free = _安全整数(details.get("max_free_chapter"))
    total = max(
        _安全整数(details.get("total_chapters")),
        _安全整数(details.get("chapters")),
        len(catalog),
    )
    has_free_limit = max_free > 0 and max_free < total
    free_catalog = [
        {**dict(item), "_qq_source_index": position}
        for position, item in enumerate(catalog, start=1)
        if _安全整数(item.get("chapter_fee")) <= 0
        and (not has_free_limit or position <= max_free)
    ]
    for index, item in enumerate(free_catalog, start=1):
        item["index"] = index
    return free_catalog


def _QQ阅读免费正文范围(
    catalog: list[dict[str, Any]],
) -> list[tuple[int, int, list[dict[str, Any]]]]:
    """按原目录序号拆分免费章节，避免过滤付费章后错位。"""
    带序号: list[tuple[int, dict[str, Any]]] = []
    for 位置, 项目 in enumerate(catalog, start=1):
        try:
            原始序号 = int(项目.get("_qq_source_index") or 位置)
        except (TypeError, ValueError):
            原始序号 = 位置
        if 原始序号 > 0:
            带序号.append((原始序号, 项目))
    带序号.sort(key=lambda 项目: 项目[0])
    结果: list[tuple[int, int, list[dict[str, Any]]]] = []
    当前开始 = 0
    当前结束 = 0
    当前项目: list[dict[str, Any]] = []
    for 原始序号, 项目 in 带序号:
        if not 当前项目 or 原始序号 == 当前结束 + 1:
            if not 当前项目:
                当前开始 = 原始序号
            当前结束 = 原始序号
            当前项目.append(项目)
            continue
        结果.append((当前开始, 当前结束, 当前项目))
        当前开始 = 当前结束 = 原始序号
        当前项目 = [项目]
    if 当前项目:
        结果.append((当前开始, 当前结束, 当前项目))
    return 结果


async def 下载QQ阅读免费正文API(
    book_id: str, catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """非 VIP 账号从免费明文接口按原目录序号获取正文。"""
    if not catalog:
        return []
    范围任务: list[tuple[int, int, list[dict[str, Any]]]] = []
    for 开始, 结束, 项目 in _QQ阅读免费正文范围(catalog):
        for 偏移 in range(0, len(项目), QQ阅读免费正文批量章节数):
            分段 = 项目[偏移 : 偏移 + QQ阅读免费正文批量章节数]
            if 分段:
                范围任务.append(
                    (
                        开始 + 偏移,
                        开始 + 偏移 + len(分段) - 1,
                        分段,
                    )
                )
    if not 范围任务:
        return []
    并发数 = max(
        1,
        min(QQ阅读免费正文最大动态并发数, len(范围任务)),
    )
    信号量 = asyncio.Semaphore(并发数)
    超时 = aiohttp.ClientTimeout(total=45, sock_connect=10, sock_read=45)
    结果按序号: dict[int, str] = {}
    完成数 = 0

    async def 请求范围(
        客户端: aiohttp.ClientSession,
        开始: int,
        结束: int,
        项目: list[dict[str, Any]],
    ) -> None:
        nonlocal 完成数
        async with 信号量:
            async with 客户端.get(
                QQ阅读免费正文地址,
                params={"bookid": str(book_id), "s": 开始, "e": 结束},
                headers={"Accept": "application/json", "User-Agent": UA},
            ) as 响应:
                响应.raise_for_status()
                数据 = await 响应.json(content_type=None)
        if not isinstance(数据, dict) or _安全整数(数据.get("code"), -1) != 0:
            raise RuntimeError("免费正文接口业务失败")
        正文列表 = 数据.get("data")
        if not isinstance(正文列表, list) or len(正文列表) != len(项目):
            raise RuntimeError("免费正文接口章节数量不完整")
        for 偏移, 正文 in enumerate(正文列表):
            if isinstance(正文, dict):
                正文 = (
                    正文.get("content")
                    or 正文.get("text")
                    or 正文.get("body")
                    or ""
                )
            文本 = str(正文 or "").strip()
            if not 文本:
                raise RuntimeError("免费正文接口返回空正文")
            结果按序号[开始 + 偏移] = 文本
        完成数 += len(项目)
        logger.debug(
            f"QQ阅读免费正文接口进度：书籍编号={book_id}, "
            f"进度={完成数}/{len(catalog)}, 并发数={并发数}"
        )

    async with aiohttp.ClientSession(timeout=超时, trust_env=False) as 客户端:
        await asyncio.gather(
            *(请求范围(客户端, 开始, 结束, 项目) for 开始, 结束, 项目 in 范围任务)
        )
    章节结果: list[dict[str, Any]] = []
    for 项目 in catalog:
        try:
            原始序号 = int(项目.get("_qq_source_index") or 项目.get("index") or 0)
        except (TypeError, ValueError):
            原始序号 = 0
        正文 = 结果按序号.get(原始序号, "")
        if not 正文:
            raise RuntimeError("免费正文接口缺少章节")
        章节结果.append({**项目, "content": 正文})
    return 章节结果


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
        raise RuntimeError("出版书正文为空")
    return text


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
    logger.info(
        f"QQ阅读章节进度：书籍编号={book_id}, 进度=0/{total}, 百分比=0%, "
        f"并发数={concurrency}"
    )

    async def 下载章节(index: int, item: dict[str, Any]) -> tuple[int, str | None]:
        resource_url = str(item.get("resource_url") or "").strip()
        if not resource_url:
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
                return index, text
            except Exception as exc:
                if attempt >= 3:
                    logger.debug(
                        f"QQ阅读出版书章节请求失败：书籍编号={book_id}, 序号={index + 1}, "
                        f"错误={type(exc).__name__}"
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
                f"百分比={percent}%, 成功={success}, 失败={completed - success}"
            )
    if len(results) != total:
        raise RuntimeError("章节不完整")
    return [{**item, "content": results[index]} for index, item in enumerate(catalog)]


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
    if 请求信号量 is None:
        请求上下文 = session.get(QQ阅读目录地址, params=params, headers=headers)
        async with 请求上下文 as response:
            response.raise_for_status()
            package = await response.read()
    else:
        async with 请求信号量:
            async with session.get(
                QQ阅读目录地址, params=params, headers=headers
            ) as response:
                response.raise_for_status()
                package = await response.read()
    request_elapsed = time.perf_counter() - request_started
    decrypt_started = time.perf_counter()
    async with 解密信号量:
        result = await _异步QQ阅读CPU函数(
            解析QQ阅读正文批次带统计,
            package,
            chapter_ids,
            解密材料,
        )
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

    def 合并批次(first: int, last: int, part: Any, results: list[Any]) -> int:
        if not isinstance(part, list):
            return 0
        recovered = 0
        expected = last - first + 1
        for offset, item in enumerate(part[:expected]):
            target_index = first + offset - 1
            if target_index < 0 or target_index >= len(results):
                continue
            if item in (None, "", "章节解密失败") or results[target_index] not in (
                None,
                "",
                "章节解密失败",
            ):
                continue
            results[target_index] = item
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
    ) -> tuple[int, int, list[Any] | None, dict[str, int]]:
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
                    if item not in (None, "", "章节解密失败")
                )
                if isinstance(part, list)
                else 0
            )
            stats["response_missing"] = max(
                0,
                expected - stats["response_items"] - stats["decrypt_failed"],
            )
            return first, last, part, stats
        except (aiohttp.ClientError, asyncio.TimeoutError):
            stats["http_failed"] = 1
            logger.debug(
                f"QQ阅读批量正文请求失败：书籍编号={book_id}, 范围={first}-{last}, "
                "阶段=请求"
            )
            return first, last, None, stats
        except Exception as exc:
            stats["other_failed"] = 1
            logger.debug(
                f"QQ阅读批量正文请求失败：书籍编号={book_id}, 范围={first}-{last}, "
                f"错误={type(exc).__name__}"
            )
            return first, last, None, stats

    initial_stats = 新建请求统计()
    for task in asyncio.as_completed([请求批次(a, b) for a, b in ranges]):
        first, last, part, stats = await task
        expected = last - first + 1
        success += 合并批次(first, last, part, results)
        合并请求统计(initial_stats, stats)
        completed += expected
        汇报进度(completed, success)

    logger.debug(
        f"QQ阅读正文首轮汇总：书籍编号={book_id}, 批次数={initial_stats['batches']}, "
        f"响应章节数={initial_stats['response_items']}/{total}, "
        f"有效章节数={initial_stats['valid_items']}, "
        f"响应缺失={initial_stats['response_missing']}, "
        f"解密失败={initial_stats['decrypt_failed']}, "
        f"请求失败={initial_stats['http_failed']}, "
        f"其他失败={initial_stats['other_failed']}"
    )

    for round_index in range(1, QQ阅读失败章节重试轮数 + 1):
        missing = [
            index + 1
            for index, item in enumerate(results)
            if item in (None, "", "章节解密失败")
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
        ) -> tuple[int, int, list[Any] | None, dict[str, int]]:
            async with retry_semaphore:
                return await 请求批次(first, last)

        retry_stats = 新建请求统计()
        for task in asyncio.as_completed([重试批次(a, b) for a, b in retry_ranges]):
            first, last, part, stats = await task
            recovered += 合并批次(first, last, part, results)
            合并请求统计(retry_stats, stats)
        success = sum(1 for item in results if item not in (None, "", "章节解密失败"))
        汇报进度(total, success)
        logger.debug(
            f"QQ阅读失败章节重试结果：书籍编号={book_id}, 轮次={round_index}/{QQ阅读失败章节重试轮数}, "
            f"恢复={recovered}, 仍缺失={total - success}, "
            f"响应章节数={retry_stats['response_items']}, "
            f"有效章节数={retry_stats['valid_items']}, "
            f"响应缺失={retry_stats['response_missing']}, "
            f"解密失败={retry_stats['decrypt_failed']}, "
            f"请求失败={retry_stats['http_failed']}, "
            f"其他失败={retry_stats['other_failed']}"
        )
        if success >= total or recovered <= 0:
            break
        if round_index < QQ阅读失败章节重试轮数:
            await asyncio.sleep(0.2 * round_index)

    chapters: list[dict[str, Any]] = []
    缺失章节号: list[int] = []
    缺失分类: dict[str, int] = {}
    for 序号, (catalog_item, content) in enumerate(zip(catalog, results), start=1):
        text = (
            content.decode("utf-8", "replace").strip()
            if isinstance(content, bytes)
            else str(content or "").strip()
        )
        if not text or text == "章节解密失败":
            缺失章节号.append(序号)
            if text == "章节解密失败":
                缺失分类["解密失败"] = 缺失分类.get("解密失败", 0) + 1
            else:
                缺失分类["空正文"] = 缺失分类.get("空正文", 0) + 1
            continue
        chapters.append({**catalog_item, "content": text})
    if 缺失章节号:
        logger.warning(
            f"QQ阅读正文缺失：书籍编号={book_id}, 缺失章节号={格式化失败范围(缺失章节号)}, "
            f"数量={len(缺失章节号)}, 分类={缺失分类}"
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
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    safe_name = Path(清理文件名(filename)).name
    if not safe_name.lower().endswith(".txt"):
        safe_name = f"{safe_name}.txt"
    candidate = 下载缓存目录 / safe_name
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = 下载缓存目录 / f"{Path(safe_name).stem}_{index}.txt"
        if not candidate.exists():
            return candidate
    raise RuntimeError("下载缓存同名文件过多")


def 写入下载缓存文件(filename: str, content: bytes) -> Path:
    path = 生成不冲突缓存路径(filename)
    path.write_bytes(content)
    小说缓存工具.标记下载缓存正在使用(path)
    return path


def 删除下载缓存文件(path: Any) -> None:
    if not path:
        return
    小说缓存工具.删除下载缓存文件(path)


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
        删除下载缓存文件(cache_path)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "小说网盘模块未加载",
        }
    try:
        upload = await 小说网盘.上传小说并获取分享链接(config, cache_path, filename)
        if not upload.get("success"):
            删除下载缓存文件(cache_path)
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
        删除下载缓存文件(cache_path)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "完成消息发送失败",
        }
    except Exception as exc:
        删除下载缓存文件(cache_path)
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
            删除下载缓存文件(source_path)

    try:
        asyncio.create_task(upload_and_cleanup())
    except RuntimeError:
        删除下载缓存文件(source_path)


def 获取QQ阅读回复流(
    event: Any,
    命令文本: str,
    配置: Any = None,
) -> AsyncIterator[Any] | None:
    link = 提取QQ阅读链接(命令文本) or 提取QQ阅读事件链接(event)
    if link is None:
        return None
    return 生成下载回复流(event, link, 配置)


async def 生成下载回复流(
    event: Any,
    来源: str,
    配置: Any = None,
) -> AsyncIterator[Any]:
    book_id = 解析书籍编号(来源)
    if not book_id:
        yield 下载失败提示
        return

    await 加载保存的QQ阅读登录态(配置)

    stage = "details"
    try:
        async with 创建QQ阅读HTTP会话(
            concurrency=max(
                QQ阅读批量最大动态并发数,
                QQ阅读出版书最大动态并发数,
            )
        ) as session:
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
            账号有VIP = _是真值(details.get("is_vip"))
            if 账号有VIP:
                catalog = 获取QQ阅读可下载目录(details, catalog)
            else:
                # 非 VIP 账号的第三方明文接口按原始目录取整本，不能套用 QQ
                # 阅读账号的 max_free_chapter 限制；接口自身负责返回可用正文。
                catalog = [
                    {
                        **dict(项目),
                        "_qq_source_index": int(
                            项目.get("_qq_source_index") or 位置
                        ),
                    }
                    for 位置, 项目 in enumerate(catalog, start=1)
                ]
            if not catalog:
                yield 章节单独付费提示
                return
            details["chapters"] = len(catalog)
            正文来源 = "官方账号接口" if 账号有VIP else "免费明文接口"
            logger.info(
                f"QQ阅读开始下载：书籍编号={book_id}, 书名={details.get('title')}, "
                f"作者={details.get('author')}, 章节数={len(catalog)}, "
                f"原始章节数={原始目录数}, 付费类型={付费类型}, "
                f"书籍类型={'published' if published else 'novel'}, "
                f"账号VIP={'是' if 账号有VIP else '否'}, 正文来源={正文来源}"
            )
            yield 格式化下载提示(details, len(catalog))

            stage = "content"
            if not 账号有VIP:
                logger.debug(
                    f"QQ阅读正文来源：书籍编号={book_id}, 账号VIP=否, 来源=免费正文接口"
                )
                chapters = await 下载QQ阅读免费正文API(book_id, catalog)
            else:
                logger.debug(
                    f"QQ阅读正文来源：书籍编号={book_id}, 账号VIP=是, 来源=账号正文接口"
                )
                chapters = (
                    await 下载参考出版书正文(book_id, catalog, session)
                    if published
                    else await 下载参考正文(book_id, catalog, session)
                )
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
