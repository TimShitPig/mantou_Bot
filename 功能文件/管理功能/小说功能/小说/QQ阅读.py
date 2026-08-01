# -*- coding: utf-8 -*-
"""QQ阅读参考核心及 AstrBot 下载适配。

依赖: requests, pycryptodome
账号配置: 文件内 CONFIG 字典（仅鉴权必要字段）
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import html
import hashlib
import io
import json
import re
import secrets
import ssl
import struct
import tarfile
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, AsyncIterator, BinaryIO, Callable, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from astrbot.api import logger

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    已配置运行状态数据库,
    读取运行状态值,
    写入运行状态值,
)

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception:
    百度网盘 = None

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具

from Crypto.Cipher import AES, DES
from Crypto.Util import Counter
from Crypto.Util.Padding import unpad

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# === decrypt ===
"""Pure-Python QQRead chapter decrypt (libfock algorithm recovery).

Wire format:
  enc = header_cipher(256) || body_cipher
  body = header_plain[128:256] || enc[256:]

Key schedule:
  knva = AES-128-CBC(key=c9ajudte0zb21ksg, iv=58jb6v2lzcspwymg).decrypt(embedded_ct)
  master = SHA256(fuid || knva)
  header / keypool = AES-256-CBC(master, iv=master[:16])
  token_index = int(mode_digit_string) % len(tokens)
  content_key = SHA256(token_ascii || fuid || stt)

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
    "8f400c5fcec88186569c7c407e35d289"
    "5495f9025321cd94976e786a65f18550"
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
      key = "c9ajudte0zb21ksg", iv = "58jb6v2lzcspwymg", AES-128-CBC, PKCS7.
    """
    if len(ciphertext) % 16:
        raise ValueError("knva ciphertext length must be multiple of 16")
    pt = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(ciphertext)
    return unpad(pt, 16)


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= 16 and data.endswith(bytes([pad]) * pad):
        return data[:-pad]
    if data.endswith(b"\r"):
        return data.rstrip(b"\r")
    return data


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


def decrypt_keypool(keypool: bytes, master: bytes) -> list[str]:
    if len(keypool) % 16:
        raise ValueError("keypool length must be multiple of 16")
    pt = AES.new(master, AES.MODE_CBC, iv=master[:16]).decrypt(keypool)
    pt = _pkcs7_unpad(pt)
    s = pt.decode("ascii", "replace").strip().strip("\r")
    return [p for p in s.split(",") if p]


def decrypt_header(enc: bytes, master: bytes) -> bytes:
    if len(enc) < 256:
        raise ValueError("chapter too short")
    return AES.new(master, AES.MODE_CBC, iv=master[:16]).decrypt(enc[:256])


def content_key(token_ascii: str | bytes, fuid: str | bytes, stt: str | bytes) -> bytes:
    if isinstance(token_ascii, str):
        token_ascii = token_ascii.encode("ascii")
    if isinstance(fuid, str):
        fuid = fuid.encode("utf-8")
    if isinstance(stt, str):
        stt = stt.encode("utf-8")
    return hashlib.sha256(token_ascii + fuid + stt).digest()


def _gunzip_loose(data: bytes) -> bytes:
    if data[:2] != b"\x1f\x8b":
        raise ValueError("not gzip")
    dco = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = dco.decompress(data)
        out += dco.flush()
        return out
    except zlib.error:
        for cut in range(len(data), max(len(data) - 64, 16), -1):
            try:
                return gzip.decompress(data[:cut])
            except Exception:
                continue
        raise


def _body(enc: bytes, header_plain: bytes) -> bytes:
    inline_body = header_plain[128:256]
    if not any(inline_body):
        return enc[256:]
    return inline_body + enc[256:]


def _aes_cbc(data: bytes, key32: bytes) -> bytes:
    if len(data) % 16:
        raise ValueError(f"AES block len {len(data)}")
    return AES.new(key32, AES.MODE_CBC, iv=key32[:16]).decrypt(data)


def _des_cbc(data: bytes, key32: bytes) -> bytes:
    if len(data) % 8:
        raise ValueError(f"DES block len {len(data)}")
    return DES.new(key32[:8], DES.MODE_CBC, iv=key32[:8]).decrypt(data)


def _aes_ctr(data: bytes, key32: bytes, initial_value: int = 2) -> bytes:
    ctr = Counter.new(
        32,
        prefix=key32[:12],
        initial_value=initial_value,
        little_endian=False,
    )
    return AES.new(key32, AES.MODE_CTR, counter=ctr).decrypt(data)


def _unpad8(data: bytes) -> bytes:
    return unpad(data, 8)


def _unpad16(data: bytes) -> bytes:
    return unpad(data, 16)


def mode_string_from_header(header: bytes) -> str:
    mode = header[:16].split(b"\x00", 1)[0]
    digits = bytes(b for b in mode if 48 <= b <= 57)
    if not digits:
        raise ValueError(f"no mode digits in {mode!r}")
    return digits.decode("ascii")


def mode_id_from_header(header: bytes) -> int:
    """Native compares atoi(mode_str[:8])."""
    digits = mode_string_from_header(header)
    if len(digits) < 8:
        return int(digits)
    return int(digits[:8])


def token_index_from_header(header: bytes, token_count: int) -> int:
    """token_index = int(full_mode_digit_string) % token_count.

    Verified on samples c1-c15 (20-token pools):
      3193288111 % 20 = 11
      3134442310 % 20 = 10
      349410281  % 20 = 1
      9485912317 % 20 = 17
    """
    if token_count <= 0:
        raise ValueError("empty keypool tokens")
    return int(mode_string_from_header(header)) % token_count


def decrypt_mode_aes_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_cbc(_aes_cbc(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_des_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_cbc(_des_cbc(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_ctr_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _des_cbc(_aes_ctr(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_aes_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_unpad16(_aes_cbc(body, key32)), key32)
    return _gunzip_loose(mid)


def decrypt_mode_des_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_unpad8(_des_cbc(body, key32)), key32)
    return _gunzip_loose(mid)


def decrypt_mode_aes_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _des_cbc(_aes_cbc(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_ctr_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_aes_ctr(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_des_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _unpad8(_des_cbc(_unpad8(_des_cbc(body, key32)), key32))
    return _gunzip_loose(mid)


def decrypt_mode_ctr_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _unpad16(_aes_cbc(_aes_ctr(body, key32), key32))
    return _gunzip_loose(mid)


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


def select_token(tokens: list[str], index: int = 11) -> str:
    if not tokens:
        raise ValueError("empty keypool tokens")
    if index < 0 or index >= len(tokens):
        return tokens[-1]
    return tokens[index]


def decrypt_chapter(
    enc: bytes,
    stt: str | bytes,
    fuid: str | bytes,
    keypool: bytes,
    knva: bytes | None = None,
    token_index: Optional[int] = None,
) -> str:
    if knva is None:
        knva = derive_knva()
    master = master_key(fuid, knva)
    tokens = decrypt_keypool(keypool, master)
    header = decrypt_header(enc, master)
    mid = mode_id_from_header(header)
    handler = _MODE_HANDLERS.get(mid)
    if handler is None:
        mode = header[:16].split(b"\x00", 1)[0]
        raise NotImplementedError(f"mode id {mid} ({mode!r}) not supported")

    if token_index is None:
        token_index = token_index_from_header(header, len(tokens))

    last_err: Optional[Exception] = None
    order = [token_index] + [i for i in range(len(tokens)) if i != token_index]
    for ti in order:
        try:
            key32 = content_key(select_token(tokens, ti), fuid, stt)
            raw = handler(enc, key32, header)
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"decrypt failed for mode id {mid}: {last_err}")


def try_decrypt_chapter(
    enc: bytes,
    stt: str | bytes,
    fuid: str | bytes,
    keypool: bytes,
    knva: bytes | None = None,
) -> Optional[str]:
    try:
        return decrypt_chapter(enc, stt, fuid, keypool, knva)
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
    608135816, -2052912941, 320440878, 57701188, -1542899678, 698298832, 137296536, -330404727, 1160258022, 953160567, -1101764913, 887688300,
    -1062458953, -914599715, 1065670069, -1253635817, -1843997223, -1988494565
]

S_INIT = [
    -785314906, -1730169428, 805139163, -803545161, -1193168915, 1780907670, -1166241723, -248741991, 614570311, -1282315017, 134345442, -2054226922,
    1667834072, 1901547113, -1537671517, -191677058, 227898511, 1921955416, 1904987480, -2112533778, 2069144605, -1034266187, -1674521287, 720527379,
    -976113629, 677414384, -901678824, -1193592593, -1904616272, 1614419982, 1822297739, -1340175810, -686458943, -1120842969, 2024746970, 1432378464,
    -430627341, -1437226092, 1464375394, 1676153920, 1439316330, 715854006, -1261675468, 289532110, -1588296017, 2087905683, -1276242927, 1668267050,
    732546397, 1947742710, -832815594, -1685613794, -1344882125, 1814351708, 2050118529, 680887927, 999245976, 1800124847, -994056165, 1713906067,
    1641548236, -81679983, 1216130144, 1575780402, -276538019, -377129551, -601480446, -345695352, 596196993, -745100091, 258830323, -2081144263,
    772490370, -1534844924, 1774776394, -1642095778, 566650946, -152474470, 1728879713, -1412200208, 1783734482, -665571480, -1777359064, -1420741725,
    1861159788, 326777828, -1170476976, 2130389656, -1578015459, 967770486, 1724537150, -2109534584, -1930525159, 1164943284, 2105845187, 998989502,
    -529566248, -2050940813, 1075463327, 1455516326, 1322494562, 910128902, 469688178, 1117454909, 936433444, -804646328, -619713837, 1240580251,
    122909385, -2137449605, 634681816, -152510729, -469872614, -1233564613, -1754472259, 79693498, -1045868618, 1084186820, 1583128258, 426386531,
    1761308591, 1047286709, 322548459, 995290223, 1845252383, -1691314900, -863943356, -1352745719, -1092366332, -567063811, 1712269319, 422464435,
    -1060394921, 1170764815, -771006663, -1177289765, 1434042557, 442511882, -694091578, 1076654713, 1738483198, -81812532, -1901729288, -617471240,
    1014306527, -43947243, 793779912, -1392160085, 842905082, -48003232, 1395751752, 1040244610, -1638115397, -898659168, 445077038, -552113701,
    -717051658, 679411651, -1402522938, -1940957837, 1767581616, -1144366904, -503340195, -1192226400, 284835224, -48135240, 1258075500, 768725851,
    -1705778055, -1225243291, -762426948, 1274779536, -505548070, -1530167757, 1660621633, -823867672, -283063590, 913787905, -797008130, 737222580,
    -1780753843, -1366257256, -357724559, 1804850592, -795946544, -1345903136, -1908647121, -1904896841, -1879645445, -233690268, -2004305902, -1878134756,
    1336762016, 1754252060, -774901359, -1280786003, 791618072, -1106372745, -361419266, -1962795103, -442446833, -1250986776, 413987798, -829824359,
    -1264037920, -49028937, 2093235073, -760370983, 375366246, -2137688315, -1815317740, 555357303, -424861595, 2008414854, -950779147, -73583153,
    -338841844, 2067696032, -700376109, -1373733303, 2428461, 544322398, 577241275, 1471733935, 610547355, -267798242, 1432588573, 1507829418,
    2025931657, -648391809, 545086370, 48609733, -2094660746, 1653985193, 298326376, 1316178497, -1287180854, 2064951626, 458293330, -1705826027,
    -703637697, -1130641692, 727753846, -2115603456, 146436021, 1461446943, -224990101, 705550613, -1235000031, -407242314, -13368018, -981117340,
    1404054877, -1449160799, 146425753, 1854211946, 1266315497, -1246549692, -613086930, -1004984797, -1385257296, 1235738493, -1662099272, -1880247706,
    -324367247, 1771706367, 1449415276, -1028546847, 422970021, 1963543593, -1604775104, -468174274, 1062508698, 1531092325, 1804592342, -1711849514,
    -1580033017, -269995787, 1294809318, -265986623, 1289560198, -2072974554, 1669523910, 35572830, 157838143, 1052438473, 1016535060, 1802137761,
    1753167236, 1386275462, -1214491899, -1437595849, 1040679964, 2145300060, -1904392980, 1461121720, -1338320329, -263189491, -266592508, 33600511,
    -1374882534, 1018524850, 629373528, -603381315, -779021319, 2091462646, -1808644237, 586499841, 988145025, 935516892, -927631820, -1695294041,
    -1455136442, 265290510, -322386114, -1535828415, -499593831, 1005194799, 847297441, 406762289, 1314163512, 1332590856, 1866599683, -167115585,
    750260880, 613907577, 1450815602, -1129346641, -560302305, -644675568, -1282691566, -590397650, 1427272223, 778793252, 1343938022, -1618686585,
    2052605720, 1946737175, -1130390852, -380928628, -327488454, -612033030, 1661551462, -1000029230, -283371449, 840292616, -582796489, 616741398,
    312560963, 711312465, 1351876610, 322626781, 1910503582, 271666773, -2119403562, 1594956187, 70604529, -677132437, 1007753275, 1495573769,
    -225450259, -1745748998, -1631928532, 504708206, -2031925904, -353800271, -2045878774, 1514023603, 1998579484, 1312622330, 694541497, -1712906993,
    -2143385130, 1382467621, 776784248, -1676627094, -971698502, -1797068168, -1510196141, 503983604, -218673497, 907881277, 423175695, 432175456,
    1378068232, -149744970, -340918674, -356311194, -474200683, -1501837181, -1317062703, 26017576, -1020076561, -1100195163, 1700274565, 1756076034,
    -288447217, -617638597, 720338349, 1533947780, 354530856, 688349552, -321042571, 1637815568, 332179504, -345916010, 53804574, -1442618417,
    -1250730864, 1282449977, -711025141, -877994476, -288586052, 1617046695, -1666491221, -1292663698, 1686838959, 431878346, -1608291911, 1700445008,
    1080580658, 1009431731, 832498133, -1071531785, -1688990951, -2023776103, -1778935426, 1648197032, -130578278, -1746719369, 300782431, 375919233,
    238389289, -941219882, -1763778655, 2019080857, 1475708069, 455242339, -1685863425, 448939670, -843904277, 1395535956, -1881585436, 1841049896,
    1491858159, 885456874, -30872223, -293847949, 1565136089, -396052509, 1108368660, 540939232, 1173283510, -1549095958, -613658859, -87339056,
    -951913406, -278217803, 1699691293, 1103962373, -669091426, -2038084153, -464828566, 1031889488, -815619598, 1535977030, -58162272, -1043876189,
    2132092099, 1774941330, 1199868427, 1452454533, 157007616, -1390851939, 342012276, 595725824, 1480756522, 206960106, 497939518, 591360097,
    863170706, -1919713727, -698356495, 1814182875, 2094937945, -873565088, 1082520231, -831049106, -1509457788, 435703966, -386934699, 1641649973,
    -1452693590, -989067582, 1510255612, -2146710820, -1639679442, -1018874748, -36346107, 236887753, -613164077, 274041037, 1734335097, -479771840,
    -976997275, 1899903192, 1026095262, -244449504, 356393447, -1884275382, -421290197, -612127241, -381855128, -1803468553, -162781668, -1805047500,
    1091903735, 1979897079, -1124832466, -727580568, -737663887, 857797738, 1136121015, 1342202287, 507115054, -1759230650, 337727348, -1081374656,
    1301675037, -1766485585, 1895095763, 1721773893, -1078195732, 62756741, 2142006736, 835421444, -1762973773, 1442658625, -635090970, -1412822374,
    676362277, 1392781812, 170690266, -373920261, 1759253602, -683120384, 1745797284, 664899054, 1329594018, -393761396, -1249058810, 2062866102,
    -1429332356, -751345684, -830954599, 1080764994, 553557557, -638351943, -298199125, 991055499, 499776247, 1265440854, 648242737, -354183246,
    980351604, -581221582, 1749149687, -898096901, -83167922, -654396521, 1161844396, -1169648345, 1431517754, 545492359, -26498633, -795437749,
    1437099964, -1592419752, -861329053, -1713251533, -1507177898, 1060185593, 1593081372, -1876348548, -34019326, 69676912, -2135222948, 86519011,
    -1782508216, -456757982, 1220612927, -955283748, 133810670, 1090789135, 1078426020, 1569222167, 845107691, -711212847, -222510705, 1091646820,
    628848692, 1613405280, -537335645, 526609435, 236106946, 48312990, -1352249391, -892239595, 1797494240, 859738849, 992217954, -289490654,
    -2051890674, -424014439, -562951028, 765654824, -804095931, -1783130883, 1685915746, -405998096, 1414112111, -2021832454, -1013056217, -214004450,
    172450625, -1724973196, 980381355, -185008841, -1475158944, -1578377736, -1726226100, -613520627, -964995824, 1835478071, 660984891, -590288892,
    -248967737, -872349789, -1254551662, 1762651403, 1719377915, -824476260, -1601057013, -652910941, -1156370552, 1364962596, 2073328063, 1983633131,
    926494387, -871278215, -2144935273, -198299347, 1749200295, -966120645, 309677260, 2016342300, 1779581495, -1215147545, 111262694, 1274766160,
    443224088, 298511866, 1025883608, -488520759, 1145181785, 168956806, -653464466, -710153686, 1689216846, -628709281, -1094719096, 1692713982,
    -1648590761, -252198778, 1618508792, 1610833997, -771914938, -164094032, 2001055236, -684262196, -2092799181, -266425487, -1333771897, 1006657119,
    2006996926, -1108824540, 1430667929, -1084739999, 1314452623, -220332638, -193663176, -2021016126, 1399257539, -927756684, -1267338667, 1190975929,
    2062231137, -1960976508, -2073424263, -1856006686, 1181637006, 548689776, -1932175983, -922558900, -1190417183, -1149106736, 296247880, 1970579870,
    -1216407114, -525738999, 1714227617, -1003338189, -396747006, 166772364, 1251581989, 493813264, 448347421, 195405023, -1584991729, 677966185,
    -591930749, 1463355134, -1578971493, 1338867538, 1343315457, -1492745222, -1610435132, 233230375, -1694987225, 2000651841, -1017099258, 1638401717,
    -266896856, -1057650976, 6314154, 819756386, 300326615, 590932579, 1405279636, -1027467724, -1144263082, -1866680610, -335774303, -833020554,
    1862657033, 1266418056, 963775037, 2089974820, -2031914401, 1917689273, 448879540, -744572676, -313240200, 150775221, -667058989, 1303187396,
    508620638, -1318983944, -1568336679, 1817252668, 1876281319, 1457606340, 908771278, -574175177, -677760460, -1838972398, 1729034894, 1080033504,
    976866871, -738527793, -1413318857, 1522871579, 1555064734, 1336096578, -746444992, -1715692610, -720269667, -1089506539, -701686658, -956251013,
    -1215554709, 564236357, -1301368386, 1781952180, 1464380207, -1131123079, -962365742, 1699332808, 1393555694, 1183702653, -713881059, 1288719814,
    691649499, -1447410096, -1399511320, -1101077756, -1577396752, 1781354906, 1676643554, -1702433246, -1064713544, 1126444790, -1524759638, -1661808476,
    -2084544070, -1679201715, -1880812208, -1167828010, 673620729, -1489356063, 1269405062, -279616791, -953159725, -145557542, 1057255273, 2012875353,
    -2132498155, -2018474495, -1693849939, 993977747, -376373926, -1640704105, 753973209, 36408145, -1764381638, 25011837, -774947114, 2088578344,
    530523599, -1376601957, 1524020338, 1518925132, -534139791, -535190042, 1202760957, -309069157, -388774771, 674977740, -120232407, 2031300136,
    2019492241, -311074731, -141160892, -472686964, 352677332, -1997247046, 60907813, 90501309, -1007968747, 1016092578, -1759044884, -1455814870,
    457141659, 509813237, -174299397, 652014361, 1966332200, -1319764491, 55981186, -1967506245, 676427537, -1039476232, -1412673177, -861040033,
    1307055953, 942726286, 933058658, -1826555503, -361066302, -79791154, 1361170020, 2001714738, -1464409218, -1020707514, 1222529897, 1679025792,
    -1565652976, -580013532, 1770335741, 151462246, -1281735158, 1682292957, 1483529935, 471910574, 1539241949, 458788160, -858652289, 1807016891,
    -576558466, 978976581, 1043663428, -1129001515, 1927990952, -94075717, -1922690386, -1086558393, -761535389, 1412390302, -1362987237, -162634896,
    1947078029, -413461673, -126740879, -1353482915, 1077988104, 1320477388, 886195818, 18198404, -508558296, -1785185763, 112762804, -831610808,
    1866414978, 891333506, 18488651, 661792760, 1628790961, -409780260, -1153795797, 876946877, -1601685023, 1372485963, 791857591, -1608533303,
    -534984578, -1127755274, -822013501, -1578587449, 445679433, -732971622, -790962485, -720709064, 54117162, -963561881, -1913048708, -525259953,
    -140617289, 1140177722, -220915201, 668550556, -1080614356, 367459370, 261225585, -1684794075, -85617823, -826893077, -1029151655, 314222801,
    -1228863650, -486184436, 282218597, -888953790, -521376242, 379116347, 1285071038, 846784868, -1625320142, -523005217, -744475605, -1989021154,
    453669953, 1268987020, -977374944, -1015663912, -550133875, -1684459730, -435458233, 266596637, -447948204, 517658769, -832407089, -851542417,
    370717030, -47440635, -2070949179, -151313767, -182193321, -1506642397, -1817692879, 1456262402, -1393524382, 1517677493, 1846949527, -1999473716,
    -560569710, -2118563376, 1280348187, 1908823572, -423180355, 846861322, 1172426758, -1007518822, -911584259, 1655181056, -1155153950, 901632758,
    1897031941, -1308360158, -1228157060, -847864789, 1393639104, 373351379, 950779232, 625454576, -1170726756, -146354570, 2007998917, 544563296,
    -2050228658, -1964470824, 2058025392, 1291430526, 424198748, 50039436, 29584100, -689184263, -1865090967, -1503863136, 1057563949, -1039604065,
    -1219600078, -831004069, 1469046755, 985887462
]

CIHAI_INIT = [
    1332899944, 1700884034, 1701343084, 1684370003, 1668446532, 1869963892
]

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


def expand_with_salt_and_key(P: List[int], S: List[int], salt: bytes, key: bytes) -> None:
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


def magic_search_final(password_bytes: bytes, salt_bytes: bytes, rounds_log2: int, cihai_init: List[int]) -> bytes:
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
    salt_b64 = salt_str[i2 + 3 : i2 + 25]
    if len(salt_b64) != 22:
        raise ValueError("Bad bcrypt-like salt length")
    pwd_bytes = password.encode("utf-8")
    if c_rev >= "a":
        pwd_bytes = password.encode("utf-8") + b"\x00"
    salt_bytes = magic_b64_decode(salt_b64, 16)
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
        logger.debug(f"QQ阅读参考 tar 解析失败：error={type(e).__name__}")
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
    "fuid": "89306811035542cd868d49def7d3857d"
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

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConfigManager()
            return cls._instance

    def _knva_bytes(self) -> bytes:
        return derive_knva()

    def _cache_valid(self, pool_b64: str) -> bool:
        if not pool_b64 or not self.fuid:
            return False
        try:
            raw = base64.b64decode(pool_b64)
            tokens = decrypt_keypool(raw, master_key(self.fuid, self._knva_bytes()))
            return bool(tokens)
        except Exception:
            return False

    def _load_key_pool_cache(self) -> Optional[str]:
        return self.key_pool

    def _save_key_pool_cache(self, pool_b64: str) -> None:
        self.key_pool = pool_b64

    def fetch_key_pool(self) -> bool:
        if not self.fuid:
            logger.debug("QQ阅读参考核心未配置 fuid")
            return False
        url = f"https://newminerva-tgw.reader.qq.com/sk?fuid={self.fuid}"
        try:
            with make_session() as sess:
                resp = sess.get(url, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            pool = str(data.get("pool", "") or "").strip()
            if not pool:
                logger.debug("QQ阅读参考核心密钥池响应为空")
                return False
            if not self._cache_valid(pool):
                logger.debug("QQ阅读参考核心密钥池校验失败")
                return False
            self.key_pool = pool
            self._save_key_pool_cache(pool)
            return True
        except Exception as e:
            logger.debug(f"QQ阅读参考核心密钥池获取失败：error={type(e).__name__}")
            return False

    def set_key_pool(self, force: bool = False) -> None:
        if not self.fuid:
            logger.debug("QQ阅读参考核心未配置 fuid")
            return
        if not force:
            cached = self._load_key_pool_cache()
            if cached and self._cache_valid(cached):
                self.key_pool = cached
                return
        if self.fetch_key_pool():
            return
        cached = self._load_key_pool_cache()
        self.key_pool = cached or self.key_pool or ""

    def refresh_key_pool(self) -> bool:
        return self.fetch_key_pool()

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
            self.fuid = str(m["fuid"])
        self.set_key_pool()


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
QQ阅读批量章节数 = 500
QQ阅读批量最大动态并发数 = 5
QQ阅读失败章节重试窗口 = 31
QQ阅读失败章节重试轮数 = 3


class _SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    s.verify = False
    s.mount("https://", _SSLAdapter())
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    return s


class Fetcher:
    def __init__(self) -> None:
        self._session = make_session()

    def extract_mid_number(self, s: str) -> int:
        a = s.find("_")
        b = s.find("_", a + 1)
        return int(s[a + 1 : b])

    def _cfg(self) -> ConfigManager:
        return ConfigManager.get_instance()

    def _pwd(self, timestamp_ms: int) -> str:
        c = self._cfg()
        return (
            f"{c.login_type}|||{c.c_version}|{c.c_platform}|{c.channel}|"
            f"{c.qrsn}|{c.qrsn}||||0|{timestamp_ms}|{SIGN_TAIL}"
        )

    def _auth_headers(self, timestamp_ms: int) -> Dict[str, str]:
        c = self._cfg()
        pwd = self._pwd(timestamp_ms)
        csigs_val = search(sha256_hex(pwd), generate_salt())
        return {
            "User-Agent": UA,
            "loginType": c.login_type,
            "c_platform": c.c_platform,
            "c_version": c.c_version,
            "channel": c.channel,
            "qrsn": c.qrsn,
            "usid": c.usid,
            "uid": c.uid,
            "youngerMode": "0",
            "qrsn_new": c.qrsn,
            "ttime": str(timestamp_ms),
            "csigs": csigs_val,
        }

    @staticmethod
    def _chapter_valid(item: Any) -> bool:
        text = str(item or "").strip()
        return bool(text) and text != "章节解密失败"

    @staticmethod
    def _failed_chapter_windows(chapter_numbers: list[int]) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        for chapter_number in sorted(set(chapter_numbers)):
            if not windows:
                windows.append((chapter_number, chapter_number))
                continue
            start, end = windows[-1]
            if chapter_number == end + 1 and chapter_number - start < QQ阅读失败章节重试窗口:
                windows[-1] = (start, chapter_number)
            else:
                windows.append((chapter_number, chapter_number))
        return windows

    def get_chapter(
        self,
        book_id: str,
        start_chapter: str,
        end_chapter: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[List[Any]]:
        def report_progress(completed: int, success: int) -> None:
            if progress_callback is None:
                return
            try:
                progress_callback(completed, success)
            except Exception:
                pass

        try:
            s = abs(int(start_chapter))
            e = abs(int(end_chapter or start_chapter))
        except (TypeError, ValueError):
            return None
        if s > e:
            e = s
        total = e - s + 1
        batch_size = QQ阅读批量章节数
        results: List[Any] = [None] * total
        ranges: list[tuple[int, int]] = []
        batch_start = s
        while batch_start <= e:
            be = min(batch_start + batch_size - 1, e)
            ranges.append((batch_start, be))
            batch_start += batch_size

        def merge_result(first: int, last: int, part: Any) -> int:
            if not isinstance(part, list):
                return 0
            recovered = 0
            expected = last - first + 1
            for offset, item in enumerate(part[:expected]):
                chapter_number = first + offset
                target_index = chapter_number - s
                if not self._chapter_valid(item) or self._chapter_valid(results[target_index]):
                    continue
                results[target_index] = item
                recovered += 1
            return recovered

        concurrency = max(1, min(QQ阅读批量最大动态并发数, len(ranges)))
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_map = {
                pool.submit(self._get_chapter, book_id, str(a), str(b)): (a, b)
                for a, b in ranges
            }
            completed = 0
            success = 0
            for fut in as_completed(future_map):
                a, b = future_map[fut]
                expected = b - a + 1
                try:
                    success += merge_result(a, b, fut.result())
                except Exception:
                    pass
                completed += expected
                report_progress(min(completed, total), min(success, total))

        for round_index in range(1, QQ阅读失败章节重试轮数 + 1):
            missing = [s + index for index, item in enumerate(results) if not self._chapter_valid(item)]
            if not missing:
                break
            retry_windows = self._failed_chapter_windows(missing)
            retry_concurrency = max(1, min(QQ阅读批量最大动态并发数, len(retry_windows)))
            logger.debug(
                f"QQ阅读失败章节重试：book_id={book_id}, round={round_index}/{QQ阅读失败章节重试轮数}, "
                f"missing={len(missing)}, windows={len(retry_windows)}, concurrency={retry_concurrency}"
            )
            recovered = 0
            with ThreadPoolExecutor(max_workers=retry_concurrency) as pool:
                future_map = {
                    pool.submit(self._get_chapter, book_id, str(a), str(b)): (a, b)
                    for a, b in retry_windows
                }
                for fut in as_completed(future_map):
                    a, b = future_map[fut]
                    try:
                        recovered += merge_result(a, b, fut.result())
                    except Exception:
                        pass
            success = sum(1 for item in results if self._chapter_valid(item))
            report_progress(total, success)
            logger.debug(
                f"QQ阅读失败章节重试结果：book_id={book_id}, round={round_index}/{QQ阅读失败章节重试轮数}, "
                f"recovered={recovered}, still_missing={total - success}"
            )
            if success >= total:
                break
            if recovered <= 0:
                break
            if round_index < QQ阅读失败章节重试轮数:
                time.sleep(0.2 * round_index)
        return results if any(self._chapter_valid(item) for item in results) else None

    def _decrypt_bytes(self, data: bytes, stt: str | bytes, allow_refresh: bool = True) -> Optional[str]:
        c = self._cfg()
        knva = c._knva_bytes()

        def _try() -> Optional[str]:
            if not c.key_pool:
                return None
            try:
                kp = base64.b64decode(c.key_pool)
            except Exception:
                return None
            return try_decrypt_chapter(data, stt, c.fuid, kp, knva)

        text = _try()
        if text is not None:
            return text
        if allow_refresh and c.refresh_key_pool():
            return _try()
        return None

    def _get_chapter(self, book_id: str, start_chapter: str, end_chapter: Optional[str]) -> Optional[List[Any]]:
        try:
            if end_chapter is not None:
                s = abs(int(start_chapter))
                e2 = abs(int(end_chapter))
                if s > e2:
                    end_chapter = start_chapter
                    e2 = s
                if e2 - s > 10000:
                    return None
            else:
                s = abs(int(start_chapter))
                e2 = s
                end_chapter = start_chapter
        except Exception as e:
            logger.debug(f"QQ阅读参考正文范围无效：error={type(e).__name__}")
            return None

        ts = int(time.time() * 1000)
        c = self._cfg()
        url = (
            f"https://newminerva-tgw.reader.qq.com/ChapBatAuthWithPD"
            f"?bookId={book_id}&type=2&scids={start_chapter}-{end_chapter}&fuid={c.fuid}"
        )
        headers = self._auth_headers(ts)
        try:
            r = self._session.get(url, headers=headers, timeout=60)
            m = tar_decrypt(r.content)
            remove_keys = []
            for key, value in list(m.items()):
                try:
                    if key in ("code", "info.txt"):
                        remove_keys.append(key)
                        continue
                    if not isinstance(value, (bytes, bytearray)):
                        # already text / other
                        if not isinstance(value, str):
                            m[key] = str(value)
                        continue
                    content = None
                    try:
                        content = self._decrypt_bytes(bytes(value), key, allow_refresh=True)
                    except Exception as e_pure:
                        logger.debug(
                            f"QQ阅读参考正文解密失败：error={type(e_pure).__name__}"
                        )
                    m[key] = content if content else "章节解密失败"
                except Exception as e4:
                    logger.debug(
                        f"QQ阅读参考正文成员处理失败：error={type(e4).__name__}"
                    )
                    m[key] = "章节解密失败"
            for k in remove_keys:
                m.pop(k, None)
            chapter_map: Dict[int, Any] = {}
            for key, value in m.items():
                try:
                    chapter_number = self.extract_mid_number(key)
                except (TypeError, ValueError):
                    continue
                if s <= chapter_number <= e2:
                    current = chapter_map.get(chapter_number)
                    if current is None or current == "章节解密失败":
                        chapter_map[chapter_number] = value
            if not chapter_map:
                return None
            return [
                chapter_map.get(chapter_number, "章节解密失败")
                for chapter_number in range(s, e2 + 1)
            ]
        except Exception as e5:
            logger.debug(f"QQ阅读参考正文请求失败：error={type(e5).__name__}")
            return None



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
        v1 = _i32(v1 - _i32(_i32(_i32(v0 << 4) + k2) ^ _i32(v0 + summ) ^ _i32(_i32(v0 >> 5) + k3)))
        v0 = _i32(v0 - _i32(_i32(_i32(v1 << 4) + k0) ^ _i32(v1 + summ) ^ _i32(_i32(v1 >> 5) + k1)))
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


def extract_zip_entries_manual(zdata: bytes, pwd: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    pos = 0
    while pos + 30 <= len(zdata):
        sig = struct.unpack_from("<I", zdata, pos)[0]
        if sig in (0x02014B50, 0x06054B50):
            break
        if sig != 0x04034B50:
            break
        _ver, flag, method, _t, _d, _crc, csize, _usize, nlen, xlen = struct.unpack_from(
            "<HHHHHIIIHH", zdata, pos + 4
        )
        name = zdata[pos + 30 : pos + 30 + nlen]
        data_off = pos + 30 + nlen + xlen
        payload = zdata[data_off : data_off + csize]
        pos = data_off + csize
        if flag & 0x8 and pos + 16 <= len(zdata) and zdata[pos : pos + 4] == b"PK\x07\x08":
            pos += 16
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
    zdata = strip_epu_trailer(tea_decrypt_head128(eqct))
    if zdata[:2] != b"PK":
        raise ValueError(f"TEA head decrypt failed head={zdata[:8].hex()}")
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


def pick_best_entry(files: list[tuple[str, bytes]]) -> tuple[str, bytes]:
    scored = []
    for name, data in files:
        lower = name.lower().replace("\\", "/")
        score = len(data)
        if lower.endswith((".xhtml", ".html", ".htm", ".txt")):
            score += 5_000_000
        if "/text/" in lower:
            score += 1_000_000
        if "cover" in lower:
            score -= 2_000_000
        if lower.endswith((".jpg", ".png", ".css", ".ncx", ".opf", ".ttf")):
            score -= 4_000_000
        scored.append((score, name, data))
    scored.sort(reverse=True)
    return scored[0][1], scored[0][2]


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
QQ阅读进度日志分段数 = 10
QQ阅读链接正则 = re.compile(r"https?://[^\s'\"<>，。]+", re.I)
QQ阅读允许域名 = ("reader.qq.com", "book.qq.com", "novel.html5.qq.com")
QQ阅读登录态命名空间 = "qq_reader_auth"
QQ阅读登录态状态键 = "login_state"
下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。"
    "如喜欢本书，请支持正版。"
)
下载失败提示 = "下载失败"
文件发送失败提示 = "文件发送失败，请稍后再试"


def _是QQ阅读域名(hostname: str) -> bool:
    host = str(hostname or "").lower().strip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in QQ阅读允许域名)


def 提取QQ阅读链接(文本: Any) -> str | None:
    for match in QQ阅读链接正则.finditer(str(文本 or "")):
        link = match.group(0).rstrip(")]}>，。；;！!")
        try:
            if _是QQ阅读域名(urlsplit(link).hostname or ""):
                return link
        except ValueError:
            continue
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
        logger.warning(f"QQ阅读登录态读取失败：error={type(exc).__name__}")
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
        logger.warning(f"QQ阅读Cookie保存失败：error={type(exc).__name__}")
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
            stack.extend(value for value in item.values() if isinstance(value, (dict, list)))
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


def _规范状态(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if text in {"完结", "完本"} or "完结" in text or lowered in {"1", "true", "yes"}:
        return "完结"
    if text in {"连载"} or "连载" in text or lowered in {"0", "false", "no"}:
        return "连载"
    return "连载"


def 解析参考书籍详情(data: Any, book_id: str) -> dict[str, Any]:
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
    return {
        "title": str(
            _读取详情字段(objects, "title", "bookName", "book_name", default=f"QQ阅读{book_id}")
            or f"QQ阅读{book_id}"
        ).strip(),
        "author": str(
            _读取详情字段(objects, "author", "authorName", "author_name", default="未知")
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
        "intro": str(
            _读取详情字段(objects, "intro", "desc", "summary", "description", default="")
            or ""
        ).strip(),
    }


def _请求参考书籍详情(book_id: str) -> dict[str, Any]:
    初始化参考核心()
    fetcher = Fetcher()
    try:
        response = fetcher._session.get(
            QQ阅读详情地址,
            params={"bid": book_id, "types": "1,2,3,4,5"},
            headers=fetcher._auth_headers(int(time.time() * 1000)),
            timeout=30,
        )
        response.raise_for_status()
        return 解析参考书籍详情(response.json(), book_id)
    finally:
        fetcher._session.close()


async def 获取参考书籍详情(book_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(_请求参考书籍详情, book_id)


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
        rows.append({"cid": cid, "title": title or f"第{cid}章"})
    rows.sort(key=lambda row: int(row["cid"]))
    return [
        {"cid": row["cid"], "index": index, "title": row["title"]}
        for index, row in enumerate(rows, start=1)
    ]


def _请求参考书籍目录(book_id: str) -> list[dict[str, Any]]:
    初始化参考核心()
    fetcher = Fetcher()
    try:
        response = fetcher._session.get(
            QQ阅读目录地址,
            params={
                "bookId": book_id,
                "type": "0",
                "tafauth": "1",
                "scids": "0",
                "text_type": "0",
                "useindex": "1",
            },
            headers=fetcher._auth_headers(int(time.time() * 1000)),
            timeout=60,
        )
        response.raise_for_status()
        return 解析参考目录包(response.content, book_id)
    finally:
        fetcher._session.close()


async def 获取参考书籍目录(book_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_请求参考书籍目录, book_id)


async def 获取参考兼容目录(
    book_id: str,
    chapter_count: int,
) -> tuple[list[dict[str, Any]], bool]:
    total = max(0, int(chapter_count or 0))
    catalog: list[dict[str, Any]] = []
    try:
        catalog = await 获取参考书籍目录(book_id)
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        if getattr(response, "status_code", None) != 400:
            raise
    if catalog or total <= 0:
        return catalog, False

    fallback = await 获取参考出版书目录(book_id, total)
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
        cid = str(item.get("chapter_id") or item.get("cid") or item.get("scid") or "").strip()
        if not cid.isdigit():
            continue
        resource_url = _出版书资源地址(item)
        if not resource_url:
            continue
        title = str(item.get("chapter_title") or item.get("title") or f"第{cid}章").strip()
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


def _请求参考出版书目录(book_id: str, chapter_count: int) -> list[dict[str, Any]]:
    total = max(0, int(chapter_count or 0))
    if total <= 0:
        return []
    初始化参考核心()
    fetcher = Fetcher()
    try:
        all_items: list[dict[str, Any]] = []
        chapter_ids = [str(index) for index in range(1, total + 1)]
        for start in range(0, len(chapter_ids), 200):
            batch = chapter_ids[start : start + 200]
            headers = fetcher._auth_headers(int(time.time() * 1000))
            headers["text_type"] = "1"
            response = fetcher._session.get(
                QQ阅读目录地址,
                params={
                    "bookId": book_id,
                    "type": "0",
                    "tafauth": "1",
                    "cidType": "1",
                    "restype": "4",
                    "epubFlag": "1",
                    "scids": ",".join(batch),
                    "scene": "0",
                    "adState": "1",
                    "fuid": ConfigManager.get_instance().fuid,
                    "noclick": "1",
                },
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            all_items.extend(_parse_teb_info_blob(response.content))
        catalog = 解析参考出版书目录(all_items)
        if len(catalog) != total:
            raise RuntimeError("章节不完整")
        return catalog
    finally:
        fetcher._session.close()


async def 获取参考出版书目录(book_id: str, chapter_count: int) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_请求参考出版书目录, book_id, chapter_count)


def _获取参考出版书密码(book_id: str) -> bytes:
    config = ConfigManager.get_instance()
    fetcher = Fetcher()
    try:
        response = fetcher._session.get(
            API_AUTH,
            params={"bookid": book_id, "authInfo": config.qrsn, "onlytrial": "1"},
            headers={
                "User-Agent": UA,
                "Cookie": f"ywguid={config.uid}; ywkey={config.usid};",
                "ywguid": config.uid,
                "ywkey": config.usid,
                "Accept": "*/*",
            },
            timeout=20,
        )
        response.raise_for_status()
        plain = tea_decrypt_bytes(response.content, tea_key_ints(config.uid))
        payload = json.loads(plain.split(b"\x00", 1)[0].decode("utf-8"))
        password = str(payload.get("pwd") or "").encode("utf-8")
        if not password:
            raise RuntimeError("出版书授权失败")
        return password
    finally:
        fetcher._session.close()


def _下载参考出版书章节(item: dict[str, Any], password: bytes) -> str:
    resource_url = str(item.get("resource_url") or "").strip()
    if not resource_url:
        raise RuntimeError("出版书资源为空")
    latest_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with make_session() as session:
                response = session.get(resource_url, headers={"User-Agent": UA}, timeout=30)
                response.raise_for_status()
                files = extract_eqct(response.content, password)
            if not files:
                raise RuntimeError("出版书资源解包为空")
            name, data = pick_best_entry(files)
            lowered = name.lower()
            if lowered.endswith((".xhtml", ".html", ".htm")):
                text = xhtml_to_text(data)
            elif lowered.endswith(".txt"):
                text = data.decode("utf-8", "replace")
            else:
                raise RuntimeError("出版书正文资源缺失")
            text = text.strip()
            if not text:
                raise RuntimeError("出版书正文为空")
            return text
        except Exception as exc:
            latest_error = exc
            if attempt < 3:
                time.sleep(0.3 * attempt)
    raise RuntimeError("出版书章节下载失败") from latest_error


def _下载参考出版书正文同步(
    book_id: str,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    total = len(catalog)
    completed = 0
    success = 0
    last_segment = 0
    logger.info(f"QQ阅读章节进度：book_id={book_id}, progress=0/{total}, percent=0%")
    password = _获取参考出版书密码(book_id)
    results: dict[int, str] = {}
    failures: list[int] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_下载参考出版书章节, item, password): index
            for index, item in enumerate(catalog)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
                success += 1
            except Exception:
                failures.append(index)
            completed += 1
            segment = (
                QQ阅读进度日志分段数
                if completed >= total
                else int(completed * QQ阅读进度日志分段数 / max(1, total))
            )
            if segment > last_segment or completed >= total:
                last_segment = segment
                percent = int(completed * 100 / max(1, total))
                logger.info(
                    f"QQ阅读章节进度：book_id={book_id}, progress={completed}/{total}, "
                    f"percent={percent}%, success={success}, failed={completed - success}"
                )
    if failures or len(results) != len(catalog):
        raise RuntimeError("章节不完整")
    return [
        {**item, "content": results[index]}
        for index, item in enumerate(catalog)
    ]


async def 下载参考出版书正文(
    book_id: str,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not catalog:
        return []
    await asyncio.to_thread(初始化参考核心)
    return await asyncio.to_thread(_下载参考出版书正文同步, book_id, catalog)


async def 下载参考正文(book_id: str, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not catalog:
        return []
    await asyncio.to_thread(初始化参考核心)
    fetcher = Fetcher()
    total = len(catalog)
    last_segment = 0
    last_completed = 0
    last_success = -1
    batch_count = (total + QQ阅读批量章节数 - 1) // QQ阅读批量章节数
    concurrency = max(1, min(QQ阅读批量最大动态并发数, batch_count))
    logger.info(
        f"QQ阅读章节进度：book_id={book_id}, progress=0/{total}, percent=0%, "
        f"batches={batch_count}, batch_size={QQ阅读批量章节数}, concurrency={concurrency}"
    )

    def report_progress(completed: int, success: int) -> None:
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
        if completed >= total and completed == last_completed and success == last_success:
            return
        last_segment = max(last_segment, segment)
        last_completed = completed
        last_success = success
        percent = int(completed * 100 / max(1, total))
        logger.info(
            f"QQ阅读章节进度：book_id={book_id}, progress={completed}/{total}, "
            f"percent={percent}%, success={success}, failed={completed - success}"
        )

    try:
        raw_chapters = await asyncio.to_thread(
            fetcher.get_chapter,
            book_id,
            "1",
            str(total),
            report_progress,
        )
        if isinstance(raw_chapters, list) and len(raw_chapters) == total:
            chapters: list[dict[str, Any]] = []
            for catalog_item, content in zip(catalog, raw_chapters):
                if isinstance(content, bytes):
                    text = content.decode("utf-8", "replace").strip()
                else:
                    text = str(content or "").strip()
                if not text or text == "章节解密失败":
                    chapters = []
                    break
                chapters.append({**catalog_item, "content": text})
            if len(chapters) == total:
                return chapters
        raise RuntimeError("章节不完整")
    finally:
        fetcher._session.close()


def 清理文件名(value: Any) -> str:
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(value or "").strip())
    return text.strip(" .") or "未知"


def 格式化字数(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "未知"
    if "字" in text:
        return text
    number = _安全整数(text, -1)
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
        content = str(chapter.get("content") or "").strip()
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
    try:
        Path(path).unlink(missing_ok=True)
    finally:
        小说缓存工具.解除下载缓存占用(path)


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
                if result.get("enabled") and not (result.get("success") or result.get("skipped")):
                    logger.warning(
                        f"QQ阅读百度网盘后台上传失败：file={filename}, error=UploadFailed"
                    )
        except Exception as exc:
            logger.warning(
                f"QQ阅读百度网盘后台上传异常：file={filename}, error={type(exc).__name__}"
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
    link = 提取QQ阅读链接(命令文本)
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
        try:
            details = await 获取参考书籍详情(book_id)
        except Exception as exc:
            logger.debug(f"QQ阅读参考详情获取失败：error={type(exc).__name__}")
            details = {
                "title": f"QQ阅读{book_id}",
                "author": "未知",
                "status": "连载",
                "words_num": "",
                "chapters": 0,
                "intro": "",
            }

        stage = "catalog"
        catalog, published = await 获取参考兼容目录(
            book_id,
            _安全整数(details.get("chapters")),
        )
        if not catalog:
            raise RuntimeError("目录为空")
        details["chapters"] = len(catalog)
        logger.info(
            f"QQ阅读开始下载：book_id={book_id}, title={details.get('title')}, "
            f"author={details.get('author')}, chapters={len(catalog)}, "
            f"book_type={'published' if published else 'novel'}"
        )
        yield 格式化下载提示(details, len(catalog))

        stage = "content"
        chapters = (
            await 下载参考出版书正文(book_id, catalog)
            if published
            else await 下载参考正文(book_id, catalog)
        )
        filename, content = 生成小说文件内容(book_id, details, catalog, chapters)
        logger.info(
            f"QQ阅读章节下载完成：book_id={book_id}, title={details.get('title')}, "
            f"success={len(chapters)}, total={len(catalog)}, file_size={len(content)}"
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
            f"QQ阅读参考下载失败：book_id={book_id}, stage={stage}, error={type(exc).__name__}"
        )
        yield 下载失败提示
