from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import hmac
import html
import json
import re
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

import aiohttp

from typing import List, Sequence

# ===== embedded Tadu pure-Python crypto and content decoder =====

def pkcs7_pad(data: bytes, block_size: int) -> bytes:
    n = block_size - (len(data) % block_size)
    return data + bytes([n]) * n


# ---------------------------------------------------------------------------
# AES-128 ECB encryption
# ---------------------------------------------------------------------------

def _xtime(x: int) -> int:
    x <<= 1
    return (x ^ 0x11B) & 0xFF if x & 0x100 else x & 0xFF


def _gmul(a: int, b: int) -> int:
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        a = _xtime(a)
        b >>= 1
    return p & 0xFF


def _gf_pow(a: int, n: int) -> int:
    r = 1
    while n:
        if n & 1:
            r = _gmul(r, a)
        a = _gmul(a, a)
        n >>= 1
    return r


def _rot8(x: int, n: int) -> int:
    return ((x << n) | (x >> (8 - n))) & 0xFF


def _make_sbox() -> List[int]:
    box: List[int] = []
    for x in range(256):
        inv = 0 if x == 0 else _gf_pow(x, 254)
        box.append((inv ^ _rot8(inv, 1) ^ _rot8(inv, 2) ^ _rot8(inv, 3) ^ _rot8(inv, 4) ^ 0x63) & 0xFF)
    return box


AES_SBOX = _make_sbox()
AES_RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _aes_key_expand(key: bytes) -> List[List[int]]:
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    words: List[List[int]] = [list(key[i:i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        temp = words[i - 1][:]
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [AES_SBOX[b] for b in temp]
            temp[0] ^= AES_RCON[i // 4]
        words.append([words[i - 4][j] ^ temp[j] for j in range(4)])
    return [sum(words[i:i + 4], []) for i in range(0, 44, 4)]


def _aes_shift_rows(s: List[int]) -> None:
    old = s[:]
    for r in range(4):
        for c in range(4):
            s[r + 4 * c] = old[r + 4 * ((c + r) % 4)]


def _aes_mix_columns(s: List[int]) -> None:
    for c in range(4):
        i = 4 * c
        a0, a1, a2, a3 = s[i], s[i + 1], s[i + 2], s[i + 3]
        s[i] = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
        s[i + 1] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
        s[i + 2] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
        s[i + 3] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)


def aes128_encrypt_block(block: bytes, key: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError("AES block must be 16 bytes")
    rks = _aes_key_expand(key)
    s = list(block)
    for i in range(16):
        s[i] ^= rks[0][i]
    for rnd in range(1, 10):
        for i in range(16):
            s[i] = AES_SBOX[s[i]]
        _aes_shift_rows(s)
        _aes_mix_columns(s)
        for i in range(16):
            s[i] ^= rks[rnd][i]
    for i in range(16):
        s[i] = AES_SBOX[s[i]]
    _aes_shift_rows(s)
    for i in range(16):
        s[i] ^= rks[10][i]
    return bytes(s)


def aes128_ecb_pkcs7_encrypt(data: bytes, key: bytes) -> bytes:
    data = pkcs7_pad(data, 16)
    return b"".join(aes128_encrypt_block(data[i:i + 16], key) for i in range(0, len(data), 16))


# ---------------------------------------------------------------------------
# DES ECB encryption
# ---------------------------------------------------------------------------

DES_IP = [
    58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4,
    62, 54, 46, 38, 30, 22, 14, 6, 64, 56, 48, 40, 32, 24, 16, 8,
    57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
    61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7,
]
DES_FP = [
    40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31,
    38, 6, 46, 14, 54, 22, 62, 30, 37, 5, 45, 13, 53, 21, 61, 29,
    36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
    34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25,
]
DES_E = [
    32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9,
    8, 9, 10, 11, 12, 13, 12, 13, 14, 15, 16, 17,
    16, 17, 18, 19, 20, 21, 20, 21, 22, 23, 24, 25,
    24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1,
]
DES_P = [
    16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10,
    2, 8, 24, 14, 32, 27, 3, 9, 19, 13, 30, 6, 22, 11, 4, 25,
]
DES_PC1 = [
    57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18,
    10, 2, 59, 51, 43, 35, 27, 19, 11, 3, 60, 52, 44, 36,
    63, 55, 47, 39, 31, 23, 15, 7, 62, 54, 46, 38, 30, 22,
    14, 6, 61, 53, 45, 37, 29, 21, 13, 5, 28, 20, 12, 4,
]
DES_PC2 = [
    14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10,
    23, 19, 12, 4, 26, 8, 16, 7, 27, 20, 13, 2,
    41, 52, 31, 37, 47, 55, 30, 40, 51, 45, 33, 48,
    44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32,
]
DES_SHIFTS = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]
DES_SBOX = [
    [[14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7],[0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8],[4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0],[15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13]],
    [[15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10],[3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5],[0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15],[13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9]],
    [[10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8],[13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1],[13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7],[1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12]],
    [[7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15],[13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9],[10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4],[3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14]],
    [[2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9],[14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6],[4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14],[11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3]],
    [[12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11],[10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8],[9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6],[4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13]],
    [[4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1],[13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6],[1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2],[6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12]],
    [[13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7],[1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2],[7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8],[2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11]],
]


def _bits(data: bytes) -> List[int]:
    return [(b >> i) & 1 for b in data for i in range(7, -1, -1)]


def _unbits(bits: Sequence[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        v = 0
        for bit in bits[i:i + 8]:
            v = (v << 1) | (bit & 1)
        out.append(v)
    return bytes(out)


def _perm(bits: Sequence[int], table: Sequence[int]) -> List[int]:
    return [bits[i - 1] for i in table]


def _rot(bits: List[int], n: int) -> List[int]:
    return bits[n:] + bits[:n]


def _des_subkeys(key: bytes) -> List[List[int]]:
    if len(key) != 8:
        raise ValueError("DES key must be 8 bytes")
    k = _perm(_bits(key), DES_PC1)
    c, d = k[:28], k[28:]
    out: List[List[int]] = []
    for sh in DES_SHIFTS:
        c = _rot(c, sh); d = _rot(d, sh)
        out.append(_perm(c + d, DES_PC2))
    return out


def _des_f(r: Sequence[int], subkey: Sequence[int]) -> List[int]:
    x = [a ^ b for a, b in zip(_perm(r, DES_E), subkey)]
    s_out: List[int] = []
    for i in range(8):
        c = x[i * 6:(i + 1) * 6]
        row = (c[0] << 1) | c[5]
        col = (c[1] << 3) | (c[2] << 2) | (c[3] << 1) | c[4]
        v = DES_SBOX[i][row][col]
        s_out.extend([(v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1])
    return _perm(s_out, DES_P)


def des_encrypt_block(block: bytes, key: bytes) -> bytes:
    if len(block) != 8:
        raise ValueError("DES block must be 8 bytes")
    l_r = _perm(_bits(block), DES_IP)
    l, r = l_r[:32], l_r[32:]
    for sk in _des_subkeys(key):
        l, r = r, [a ^ b for a, b in zip(l, _des_f(r, sk))]
    return _unbits(_perm(r + l, DES_FP))


def des_ecb_pkcs7_encrypt(data: bytes, key: bytes) -> bytes:
    data = pkcs7_pad(data, 8)
    return b"".join(des_encrypt_block(data[i:i + 8], key) for i in range(0, len(data), 8))


def selftest_crypto() -> bool:
    aes = aes128_encrypt_block(bytes.fromhex("6bc1bee22e409f96e93d7e117393172a"), bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")).hex()
    des = des_encrypt_block(bytes.fromhex("0123456789abcdef"), bytes.fromhex("133457799bbcdff1")).hex()
    return aes == "3ad77bb40d7a3660a89ecaf32466ef97" and des == "85e813540f0ab405"


def 解密_tadu正文(data: bytes) -> str:
    """使用内嵌纯 Python 库解析 TDZ 容器并还原 UTF-16LE 正文。"""
    raw = bytes(data or b"")
    if raw[:4] == b"tadu":
        import gzip

        if len(raw) < 32:
            raise ValueError("TDZ 容器头不完整")
        meta_len = int.from_bytes(raw[8:16], "little")
        pos = 16 + meta_len
        if pos + 16 > len(raw):
            raise ValueError("TDZ 容器索引不完整")
        offset = int.from_bytes(raw[pos:pos + 8], "little")
        length = int.from_bytes(raw[pos + 8:pos + 16], "little")
        if offset <= 0 or length <= 0 or offset + length > len(raw):
            raise ValueError("TDZ 容器正文范围无效")
        raw = gzip.decompress(raw[offset:offset + length])
    elif raw.startswith(b"\x1f\x8b"):
        import gzip

        raw = gzip.decompress(raw)
    return raw.decode("utf-16le", errors="ignore").replace("\ufeff", " ").replace("\r", "\n").strip()



try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception as exc:
    小说网盘 = None
    logger.warning("塔读小说网盘模块加载失败：错误类型=%s", type(exc).__name__)

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning("塔读小说百度网盘模块加载失败：错误类型=%s", type(exc).__name__)

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题


下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"

塔读API = "http://reader.tadu.com"
塔读下载并发上限 = 400
塔读目录并发上限 = 400
塔读解密并发上限 = 400
塔读重试次数 = 3
进度日志分段数 = 10

APP_VERSION = "6.11.02.800019"
VERSION_CODE = 1321
ANDROID_RELEASE = "10"
ANDROID_SDK_INT = 29
SCREEN_SIZE = "1080*1920"
DEVICE_TYPE = "Pixel 4"
DEVICE_MAKE = "Google"
PACKAGE_NAME = "zhuishu"
USER_AGENT = "Mozilla/5.0 (Linux; Android 10; Pixel 4 Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36"
TDCN_SECRET = "UYHMKJ%$#&21918djduw^&*()_+^$%kjdsk28dkdj236^"
TDCN_DES_KEY = b"LAP^%O$8"
BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
OAUTH_SECRET_1 = "cd2yj5352pu927mrsn5kmut0saloniy"
OAUTH_HMAC_KEY = b"1a8154132fg4a784fad101661z1854181ac1qed7"

塔读域名规则 = re.compile(r"(?:^|[./])tadu\.com(?:$|[/:?])|塔读", re.IGNORECASE)
非塔读小说域名规则 = re.compile(
    r"(?:^|[./])(?:fanqienovel|changdunovel|fqnovel|novelfm)\.com(?:$|[/:?])",
    re.IGNORECASE,
)
链接规则 = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
书籍编号规则 = re.compile(r"(?:bookId|book_id|bookid|bid)=(\d{4,})", re.IGNORECASE)
路径编号规则 = re.compile(r"/(?:book|read|reader|detail)/([0-9]{4,})(?:[./?]|$)", re.IGNORECASE)

塔读解密执行器 = ThreadPoolExecutor(
    max_workers=塔读解密并发上限,
    thread_name_prefix="tadu-decrypt",
)


@dataclass
class 塔读会话状态:
    sessionid: str = ""
    token: str = ""
    refresh_token: str = ""
    expire: Any = None
    early_time: Any = None
    expire_time: Any = None


_塔读会话 = 塔读会话状态()
_塔读会话锁 = asyncio.Lock()


def _当前毫秒() -> int:
    return int(time.time() * 1000)


def _md5_hex(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.md5(raw).hexdigest()


def _base62_encode(number: int, length: int = 16) -> str:
    out: list[str] = []
    while True:
        if number <= 61:
            out.append(BASE62[number])
            break
        out.append(BASE62[number % 62])
        number //= 62
    return "".join(reversed(out)).rjust(length, "0")


def _aes_b64(text: str, key_text: str) -> str:

    return base64.b64encode(
        aes128_ecb_pkcs7_encrypt(text.encode("utf-8"), key_text.encode("utf-8"))
    ).decode("ascii")


def _des_hex(text: str) -> str:

    return des_ecb_pkcs7_encrypt(text.encode("utf-8"), TDCN_DES_KEY).hex().upper()


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _紧凑JSON(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _构造Bearer(sessionid: str = "", ts: int | None = None) -> str:
    current = int(ts if ts is not None else _当前毫秒())
    aes_key = _base62_encode(current, 16)
    issuer = f"tadu:app:android:{aes_key}"
    jti = _md5_hex(
        f"{_aes_b64(OAUTH_SECRET_1, aes_key)}:"
        f"{_aes_b64(issuer, aes_key)}:"
        f"{_aes_b64(str(current), aes_key).lower()}"
    )
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "sdk": _aes_b64(str(ANDROID_SDK_INT), aes_key),
        "sessionid": _aes_b64(sessionid or "", aes_key),
        "clientTime": current,
        "iss": issuer,
        "iat": current // 1000,
        "jti": jti,
    }
    signing = (
        _base64url(_紧凑JSON(header))
        + "."
        + _base64url(_紧凑JSON(claims))
    ).encode("ascii")
    signature = hmac.new(OAUTH_HMAC_KEY, signing, hashlib.sha256).digest()
    jwt = signing.decode("ascii") + "." + _base64url(signature)
    return base64.b64encode(jwt.encode("utf-8")).decode("ascii")


def _参数值串(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""
    values: list[str] = []
    for key in sorted(params.keys(), key=lambda item: str(item).lower()):
        value = params.get(key)
        if value is None:
            values.append("")
        elif isinstance(value, (list, tuple)):
            values.append("".join("" if item is None else str(item) for item in value))
        else:
            values.append(str(value))
    return "".join(values)


def _构造Tdcn(params: Mapping[str, Any] | None, rn: str) -> str:
    sdk = urllib.parse.quote_plus(ANDROID_RELEASE, safe="")
    device_type = urllib.parse.quote_plus(DEVICE_TYPE, safe="")
    raw = (
        _参数值串(params)
        + TDCN_SECRET
        + rn
        + ""
        + APP_VERSION
        + ""
        + ""
        + sdk
        + SCREEN_SIZE
        + device_type
        + ""
        + ""
    )
    return _des_hex(_md5_hex(raw))


def _构造XClient(params: Mapping[str, Any] | None = None) -> str:
    rn = "".join(str(uuid.uuid4().int % 10) for _ in range(10))
    tdcn = _构造Tdcn(params, rn)
    fields = [
        ("sdk", urllib.parse.quote_plus(ANDROID_RELEASE, safe="")),
        ("sdkVersion", str(ANDROID_SDK_INT)),
        ("screenSize", SCREEN_SIZE),
        ("type", urllib.parse.quote_plus(DEVICE_TYPE, safe="")),
        ("imei", ""),
        ("imsi", ""),
        ("version", APP_VERSION),
        ("versionCode", str(VERSION_CODE)),
        ("rootPath", ""),
        ("rn", rn),
        ("tdcn", tdcn),
        ("android_id_new", ""),
        ("localTime", str(_当前毫秒())),
        ("shuZiId", ""),
        ("tdUUID", str(uuid.uuid4())),
        ("oaid", ""),
        ("isGuestMode", "0"),
        ("readLike", "0"),
        ("tagIds", ""),
        ("make", DEVICE_MAKE),
        ("package_name", PACKAGE_NAME),
    ]
    return ";".join(f"{key}={value}" for key, value in fields) + ";"


def _接口成功(response: Mapping[str, Any]) -> bool:
    try:
        return int(response.get("code", -1)) == 100
    except Exception:
        return False


def _数据对象(response: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(response, Mapping):
        return {}
    data = response.get("data")
    if isinstance(data, Mapping):
        return data
    return {}


def _绝对地址(domain: str, url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return str(domain or "").rstrip("/") + "/" + value.lstrip("/")


def _提取列表(data: Mapping[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, Mapping):
            nested = _提取列表(value, ("books", "bookList", "chapters", "chapterList", "list", "records"))
            if nested:
                return nested
    return []


def _格式化字数(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "未知"
    number_text = re.sub(r"[\s,，]", "", text)
    if number_text.endswith("字"):
        number_text = number_text[:-1]
    if number_text.replace(".", "", 1).isdigit():
        try:
            number = int(float(number_text))
        except Exception:
            return text
        return f"{round(number / 10000, 1)}万字" if number >= 10000 else f"{number}字"
    return text


def _清理文件名(value: Any) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(value or "")).strip()
    return text[:120] or "未知"


def _清理正文(text: Any) -> str:
    value = html.unescape(str(text or "")).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t\u3000]+", " ", value)
    return value.strip()


def 提取塔读正文(data: bytes) -> str:
    return _清理正文(解密_tadu正文(data))


def 计算塔读章节并发数(章节数: int) -> int:
    return max(1, min(塔读下载并发上限, int(章节数 or 0)))


def 解析塔读搜索书籍(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    data = _数据对象(response)
    rows = _提取列表(data, ("books", "bookList", "list", "result", "searchBookList"))
    result: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        book = item.get("bookInfo") if isinstance(item.get("bookInfo"), Mapping) else item
        book_id = str(book.get("bookId") or book.get("id") or book.get("docId") or "").strip()
        if not book_id:
            continue
        title = str(book.get("bookName") or book.get("title") or book.get("name") or "未知").strip()
        author = str(book.get("authorName") or book.get("author") or "未知").strip()
        result.append({
            "title": title or "未知",
            "author": author or "未知",
            "book_id": book_id,
            "platform": "塔读",
            "url": f"https://reader.tadu.com/book/{book_id}",
            "heat": book.get("readCount") or book.get("heat") or 0,
            "score": book.get("score") or 0,
            "word_count": book.get("wordCount") or book.get("words") or book.get("wordNum") or "",
        })
    return result


def 解析塔读批量章节(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    data = _数据对象(response)
    domain = str(data.get("domain") or "")
    rows = _提取列表(data, ("chapters", "chapterList", "list"))
    result: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, Mapping):
            continue
        chapter_id = str(item.get("chapterId") or item.get("chapter_id") or item.get("id") or "").strip()
        chapter_num = item.get("chapterNum") or item.get("chapterNumber") or item.get("num") or index
        try:
            chapter_num = int(chapter_num)
        except Exception:
            chapter_num = index
        title = str(item.get("chapterName") or item.get("chapterTitle") or item.get("title") or item.get("name") or f"第{chapter_num}章").strip()
        url = _绝对地址(
            str(item.get("domain") or domain),
            str(item.get("downloadUrl") or item.get("chapterUrl") or item.get("chapterDownloadUrl") or item.get("url") or ""),
        )
        result.append({
            "chapter_id": chapter_id,
            "chapter_num": chapter_num,
            "title": title or f"第{chapter_num}章",
            "url": url,
        })
    return result


def 提取塔读直接来源(text: str) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    match = 链接规则.search(value)
    if match:
        link = match.group(0)
        if 非塔读小说域名规则.search(link) or not 塔读域名规则.search(link):
            return None
        return link
    if not 塔读域名规则.search(value) and not 书籍编号规则.search(value):
        return None
    return value


def 提取塔读书籍编号(source: str) -> str:
    value = str(source or "")
    for pattern in (书籍编号规则, 路径编号规则):
        match = pattern.search(value)
        if match:
            return match.group(1)
    if 塔读域名规则.search(value):
        match = re.search(r"(?<!\d)(\d{5,})(?!\d)", value)
        if match:
            return match.group(1)
    return ""


def _事件来源(event: Any) -> str | None:
    for field in ("message_str", "message", "raw_message"):
        value = getattr(event, field, None)
        if value is None:
            continue
        source = 提取塔读直接来源(str(value))
        if source:
            return source
    return None


def 创建塔读HTTP会话() -> aiohttp.ClientSession:
    connector = aiohttp.TCPConnector(
        limit=塔读下载并发上限,
        limit_per_host=塔读下载并发上限,
        ttl_dns_cache=300,
        keepalive_timeout=30,
        force_close=False,
    )
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=60)
    return aiohttp.ClientSession(timeout=timeout, connector=connector)


def _塔读请求头(sign_params: Mapping[str, Any] | None = None, content_type: str = "") -> dict[str, str]:
    state = _塔读会话
    headers = {
        "User-Agent": USER_AGENT,
        "X-Client": _构造XClient(sign_params),
        "COOKIE": (
            f"sessionid={state.sessionid};token={state.token};"
            f"refreshToken={state.refresh_token};bearer={_构造Bearer(state.sessionid)}"
        ),
        "token": state.token,
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


async def _请求塔读接口(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    form: Mapping[str, Any] | None = None,
    ensure_session: bool = True,
) -> dict[str, Any]:
    if ensure_session:
        await 确保塔读会话(session)
    method = method.upper()
    sign_params = params if method == "GET" else form
    url = path if path.startswith("http") else 塔读API.rstrip("/") + "/" + path.lstrip("/")
    headers = _塔读请求头(sign_params, "application/x-www-form-urlencoded" if method == "POST" else "")
    async with session.request(method, url, params=params if method == "GET" else None, data=form if method == "POST" else None, headers=headers) as response:
        response.raise_for_status()
        payload = await response.json(content_type=None)
    if not isinstance(payload, dict):
        raise RuntimeError("塔读接口响应格式异常")
    return payload


def _更新塔读会话(data: Mapping[str, Any]) -> None:
    """吸收注册/续期响应，仅把游客登录态保存在当前进程内。"""
    _塔读会话.sessionid = str(data.get("sessionId") or data.get("sessionid") or _塔读会话.sessionid or "")
    _塔读会话.token = str(data.get("token") or _塔读会话.token or "")
    _塔读会话.refresh_token = str(
        data.get("refreshToken") or data.get("refresh_token") or _塔读会话.refresh_token or ""
    )
    if data.get("expire") not in (None, ""):
        _塔读会话.expire = data.get("expire")
    if data.get("earlyTime") not in (None, ""):
        _塔读会话.early_time = data.get("earlyTime")
    if data.get("expireTime") not in (None, ""):
        _塔读会话.expire_time = data.get("expireTime")
    try:
        expire_seconds = int(data.get("expire") or 0)
    except (TypeError, ValueError):
        expire_seconds = 0
    if expire_seconds > 0:
        _塔读会话.expire_time = _当前毫秒() + expire_seconds * 1000


def _塔读会话需要续期() -> bool:
    if not _塔读会话.sessionid or not _塔读会话.token:
        return False
    try:
        expire_time = int(_塔读会话.expire_time)
    except (TypeError, ValueError):
        # 旧进程内状态没有有效期时，先走 token/get，失败再重新注册。
        return True
    try:
        early_time = max(0, int(_塔读会话.early_time or 0))
    except (TypeError, ValueError):
        early_time = 0
    return _当前毫秒() >= expire_time - early_time * 1000


def _应用塔读Token响应(response: Mapping[str, Any] | None) -> bool:
    if not isinstance(response, Mapping) or not _接口成功(response):
        return False
    data = response.get("data")
    if not isinstance(data, Mapping):
        data = response
    token = data.get("token")
    if not token:
        return False
    _更新塔读会话(data)
    return True


async def _注册塔读会话(session: aiohttp.ClientSession) -> None:
    response = await _请求塔读接口(
        session,
        "POST",
        "/user/api/register",
        form={"readType": 0},
        ensure_session=False,
    )
    data = _数据对象(response)
    if not _接口成功(response) or not data:
        raise RuntimeError("塔读游客会话初始化失败")
    _更新塔读会话(data)
    if not _塔读会话.sessionid or not _塔读会话.token:
        raise RuntimeError("塔读游客会话字段不完整")


async def 确保塔读会话(session: aiohttp.ClientSession) -> None:
    if _塔读会话.sessionid and _塔读会话.token and not _塔读会话需要续期():
        return
    async with _塔读会话锁:
        if _塔读会话.sessionid and _塔读会话.token and not _塔读会话需要续期():
            return
        if not _塔读会话.sessionid or not _塔读会话.token:
            await _注册塔读会话(session)
            return
        try:
            response = await _请求塔读接口(
                session,
                "GET",
                "/user/api/token/get",
                ensure_session=False,
            )
            if _应用塔读Token响应(response):
                return
        except Exception as exc:
            logger.debug("塔读游客Token续期失败：阶段=refresh, 错误类型=%s", type(exc).__name__)
        await _注册塔读会话(session)


async def _获取详情(session: aiohttp.ClientSession, book_id: str) -> dict[str, Any]:
    response = await _请求塔读接口(session, "GET", "/book/info/titlePage", params={"bookId": book_id})
    data = _数据对象(response)
    for key in ("bookInfo", "bookDetail", "book", "info"):
        value = data.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return dict(data)


async def _获取单章地址(session: aiohttp.ClientSession, book_id: str, chapter: Mapping[str, Any]) -> str:
    response = await _请求塔读接口(
        session,
        "GET",
        "/book/chapter/getChapterTdz",
        params={
            "book_id": book_id,
            "chapter_num": chapter.get("chapter_num") or 0,
            "chapter_id": chapter.get("chapter_id") or "",
        },
    )
    data = _数据对象(response)
    chapter_info = data.get("chapterInfo") if isinstance(data.get("chapterInfo"), Mapping) else data
    return _绝对地址(
        str(chapter_info.get("domain") or data.get("domain") or ""),
        str(chapter_info.get("chapterUrl") or chapter_info.get("chapterDownloadUrl") or chapter_info.get("url") or ""),
    )


async def _获取目录(session: aiohttp.ClientSession, book_id: str) -> list[dict[str, Any]]:
    batch_response = await _请求塔读接口(
        session,
        "GET",
        "/book/batchdownload/listNew",
        params={"book_id": book_id},
    )
    chapters = 解析塔读批量章节(batch_response)
    if not chapters:
        catalog_response = await _请求塔读接口(
            session,
            "GET",
            "/book/directory/list",
            params={"bookId": book_id, "sort": "asc"},
        )
        data = _数据对象(catalog_response)
        rows = _提取列表(data, ("chapters", "chapterList", "list"))
        chapters = 解析塔读批量章节({"data": {"chapters": rows}})
    if not chapters:
        return []

    missing = [chapter for chapter in chapters if not chapter.get("url")]
    if missing:
        sem = asyncio.Semaphore(min(塔读目录并发上限, max(1, len(missing))))

        async def fill(chapter: dict[str, Any]) -> None:
            async with sem:
                chapter["url"] = await _获取单章地址(session, book_id, chapter)

        await asyncio.gather(*(fill(chapter) for chapter in missing))
    return chapters


async def _下载章节字节(session: aiohttp.ClientSession, url: str) -> bytes:
    value = str(url or "")
    if value.startswith("https://media") and ".tadu.com/" in value:
        value = "http://" + value[len("https://"):]
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "keep-alive"}
    async with session.get(value, headers=headers) as response:
        response.raise_for_status()
        return await response.read()


async def _下载全部章节(
    session: aiohttp.ClientSession,
    book_id: str,
    chapters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    total = len(chapters)
    concurrency = 计算塔读章节并发数(total)
    request_sem = asyncio.Semaphore(concurrency)
    decrypt_sem = asyncio.Semaphore(min(塔读解密并发上限, concurrency))
    results: list[dict[str, Any] | None] = [None] * total
    progress_lock = asyncio.Lock()
    completed = 0
    success = 0
    last_percent = 0
    logger.info(
        "塔读小说章节进度：书籍编号=%s, 进度=0/%s, 百分比=0%%, "
        "模式=批量地址, 并发数=%s, 最大并发数=%s, 会话复用=开启, "
        "解密方式=库, 解密并发数=%s, 重试次数=%s",
        book_id,
        total,
        concurrency,
        塔读下载并发上限,
        min(塔读解密并发上限, concurrency),
        塔读重试次数,
    )

    async def download_one(index: int, chapter: dict[str, Any]) -> None:
        nonlocal completed, success, last_percent
        title = str(chapter.get("title") or f"第{index + 1}章")
        url = str(chapter.get("url") or "")
        content = ""
        for attempt in range(1, 塔读重试次数 + 1):
            try:
                if not url:
                    raise RuntimeError("章节地址为空")
                async with request_sem:
                    raw = await _下载章节字节(session, url)
                async with decrypt_sem:
                    loop = asyncio.get_running_loop()
                    content = await loop.run_in_executor(塔读解密执行器, 提取塔读正文, raw)
                if not content:
                    raise RuntimeError("章节正文为空")
                break
            except Exception as exc:
                logger.debug(
                    "塔读单章失败：书籍编号=%s, 序号=%s, 轮次=%s, 错误类型=%s",
                    book_id,
                    index + 1,
                    attempt,
                    type(exc).__name__,
                )
                if attempt < 塔读重试次数:
                    await asyncio.sleep(min(0.5 * attempt, 1.5))
        results[index] = {"title": title, "content": content, "id": str(chapter.get("chapter_id") or "")}
        async with progress_lock:
            completed += 1
            if content:
                success += 1
            percent = int(completed * 100 / max(total, 1))
            if completed == total or percent >= min(100, last_percent + 进度日志分段数):
                logger.info(
                    "塔读小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s",
                    book_id,
                    completed,
                    total,
                    percent,
                    success,
                    completed - success,
                )
                last_percent = percent

    await asyncio.gather(*(download_one(index, chapter) for index, chapter in enumerate(chapters)))
    return [
        item or {
            "title": str(chapter.get("title") or f"第{index + 1}章"),
            "content": "",
            "id": str(chapter.get("chapter_id") or ""),
        }
        for index, (item, chapter) in enumerate(zip(results, chapters))
    ]


def _详情字段(detail: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = detail.get(key)
        if value not in (None, ""):
            return value
    return ""


def 解析塔读书籍详情(detail: Mapping[str, Any] | None) -> dict[str, str]:
    """统一解析塔读 titlePage 返回的书名、作者、状态和真实字数。"""
    data = detail if isinstance(detail, Mapping) else {}
    title = str(_详情字段(data, "bookName", "bookTitle", "title", "name") or "未知")
    author = str(_详情字段(data, "bookAuthor", "authorName", "author", "writer") or "未知")
    status_text = str(_详情字段(data, "status", "serialStatus", "bookStatus") or "")
    is_end = str(_详情字段(data, "isEnd", "isFinished", "finish") or "").lower()
    status = "完结" if "完" in status_text or is_end in {"1", "true", "yes"} else "连载"
    word_count = _格式化字数(_详情字段(
        data,
        "bookTotalSize",
        "wordCount",
        "bookWordCount",
        "wordNum",
        "totalWordCount",
        "totalWords",
        "words",
    ))
    return {
        "title": title,
        "author": author,
        "status": status,
        "word_count": word_count,
    }


def _生成小说文件(book_id: str, title: str, author: str, status: str, word_count: str, chapters: list[dict[str, Any]]) -> tuple[str, bytes]:
    file_name = f"[{status}]书名：{_清理文件名(title)} 作者：{_清理文件名(author)}.txt"
    lines = [
        文件声明,
        "",
        f"名称：{title}",
        f"作者：{author}",
        f"状态：{status}",
        f"字数：{word_count}",
        f"书籍ID：{book_id}",
        f"章节数：{len(chapters)}",
        "",
    ]
    for chapter in chapters:
        content = str(chapter.get("content") or "").strip()
        if not content:
            continue
        chapter_title = str(chapter.get("title") or "章节")
        content = 去除章节正文重复标题(chapter_title, content)
        lines.extend([chapter_title, "", content, ""])
    return file_name, "\n".join(lines).encode("utf-8")


def _写入缓存(file_name: str, content: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    path = 下载缓存目录 / file_name
    index = 1
    while path.exists():
        path = 下载缓存目录 / f"{Path(file_name).stem}_{index}.txt"
        index += 1
    path.write_bytes(content)
    小说缓存工具.标记下载缓存正在使用(path)
    return path


def _删除缓存(path: Any) -> None:
    if not path:
        return
    小说缓存工具.删除下载缓存文件(path)


async def _准备发送文本文件(event: Any, file_name: str, content: bytes, config: Any, *, title: str, author: str) -> dict[str, Any]:
    cache_path = _写入缓存(file_name, content)
    if 小说网盘 is None:
        _删除缓存(cache_path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "网盘模块未加载"}
    try:
        upload = await 小说网盘.上传小说并获取分享链接(config, cache_path, file_name)
        if not upload.get("success"):
            _删除缓存(cache_path)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "上传失败"}
        sent = await 小说网盘.发送小说下载完成链接(event, title, author, str(upload.get("share_url") or ""))
        if sent.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": cache_path, "error": ""}
        fallback = str(sent.get("fallback_text") or "")
        if fallback:
            return {"sent": False, "fallback_text": fallback, "source_cache_path": cache_path, "error": ""}
        _删除缓存(cache_path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "完成消息发送失败"}
    except Exception as exc:
        logger.warning("塔读小说网盘处理失败：文件=%s, 错误类型=%s", file_name, type(exc).__name__)
        _删除缓存(cache_path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "网盘处理失败"}


def _启动百度后台上传并清理(config: Any, cache_path: Any, file_name: str) -> None:
    async def task() -> None:
        try:
            if 百度网盘 is not None and cache_path:
                await 百度网盘.后台上传小说文件(config, cache_path, file_name)
        except Exception as exc:
            logger.warning("塔读小说百度后台上传异常：文件=%s, 错误类型=%s", file_name, type(exc).__name__)
        finally:
            _删除缓存(cache_path)

    try:
        asyncio.get_running_loop().create_task(task())
    except Exception:
        _删除缓存(cache_path)


def 获取塔读小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    source = 提取塔读直接来源(命令文本) or _事件来源(event)
    if source is None:
        return None
    return 生成塔读下载回复流(event, source, 配置)


async def 生成塔读下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    book_id = 提取塔读书籍编号(来源)
    if not book_id:
        yield "下载失败"
        return
    try:
        async with 创建塔读HTTP会话() as session:
            await 确保塔读会话(session)
            detail, chapters = await asyncio.gather(
                _获取详情(session, book_id),
                _获取目录(session, book_id),
            )
            if not chapters or not all(chapter.get("url") for chapter in chapters):
                logger.warning("塔读小说目录不完整：书籍编号=%s, 章节数=%s", book_id, len(chapters))
                yield "下载失败"
                return
            详情 = 解析塔读书籍详情(detail)
            title = 详情["title"]
            author = 详情["author"]
            status = 详情["status"]
            word_count = 详情["word_count"]
            concurrency = 计算塔读章节并发数(len(chapters))
            logger.info(
                "塔读小说开始下载：书籍编号=%s, 书名=%s, 作者=%s, 章节数=%s, "
                "目录并发数=%s, 正文并发数=%s, 会话复用=开启, 解密方式=库",
                book_id,
                title,
                author,
                len(chapters),
                塔读目录并发上限,
                concurrency,
            )
            yield "\n".join([
                f"书名：{title}",
                f"作者：{author}",
                f"状态：{status}",
                f"章节：{len(chapters)} 章",
                f"字数：{word_count}",
                "",
                "正在下载中请稍等.....",
            ])
            chapter_results = await _下载全部章节(session, book_id, chapters)

        success = [chapter for chapter in chapter_results if chapter.get("content")]
        if len(success) != len(chapters):
            logger.warning("塔读小说下载失败：书籍编号=%s, 成功=%s, 总数=%s", book_id, len(success), len(chapters))
            yield "下载失败"
            return
        file_name, content = _生成小说文件(book_id, title, author, status, word_count, chapter_results)
        send_result = await _准备发送文本文件(event, file_name, content, 配置, title=title, author=author)
        if send_result.get("sent"):
            _启动百度后台上传并清理(配置, send_result.get("source_cache_path"), file_name)
            return
        fallback = str(send_result.get("fallback_text") or "")
        if fallback:
            try:
                yield fallback
            finally:
                _启动百度后台上传并清理(配置, send_result.get("source_cache_path"), file_name)
            return
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning("塔读小说下载失败：书籍编号=%s, 错误类型=%s", book_id, type(exc).__name__)
        yield "下载失败"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    try:
        async with 创建塔读HTTP会话() as session:
            response = await _请求塔读接口(
                session,
                "GET",
                "/book/search/result",
                params={
                    "searchcontent": str(关键词),
                    "page": 1,
                    "type": 1,
                    "docId": "",
                    "readLike": "0",
                    "searchType": 0,
                    "searchFrom": 0,
                    "wordMinNum": 0,
                    "wordMaxNum": 0,
                },
            )
        return 解析塔读搜索书籍(response)[: max(1, int(需要数量 or 1))]
    except Exception as exc:
        logger.warning("塔读小说搜索失败：关键词=%s, 错误类型=%s", 关键词, type(exc).__name__)
        return []


def 关闭塔读资源() -> None:
    global 塔读解密执行器
    try:
        塔读解密执行器.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
