from __future__ import annotations

import asyncio
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
import base64
import hashlib
import json
import random
import struct
import time
import zlib
import aiohttp
import gmpy2
from Crypto.Util.strxor import strxor
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from astrbot.api import logger

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception as exc:
    小说网盘 = None
    logger.warning(f"小说网盘模块加载失败：error={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={exc}")

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
得间单章最大并发数 = 500
得间单章重试次数 = 3
得间解密最大动态并发数 = 200
得间解密执行器 = ThreadPoolExecutor(
    max_workers=得间解密最大动态并发数,
    thread_name_prefix="dejian-decrypt",
)


# ===== 得间协议与解密（原 _得间源码） =====

BASE = "https://dj.palmestore.com"
PACKAGE = "com.chaozh.iReader.dj"
APP_UA = (
    "Mozilla/5.0 (Linux; Android 9; Pixel 4 Build/PQ3B.190801.002; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120 Mobile Safari/537.36"
)

APP_DIR = Path(__file__).resolve().parent

EMBEDDED_KEY_PK8_B64 = (
    "MIICdQIBADANBgkqhkiG9w0BAQEFAASCAl8wggJbAgEAAoGBAMXGjyS3p+3AVnlBJe5VQ6tC9inh8tVBve4r+yBjC5HQD6th2n3tSyuNVYaNRAFSEq+OENwnwwhjbYUnjLWb+qZscB43K1+4/WlKdvfgwQVXm0ZQ2+jMBf+165UBEEuuWT2WqXeKkkUqPQta5lrt4eFfbo53JcOO4D5fDSGQS5bZAgMBAAECgYAor4I/AXEQXeLsKtTMxMmY77uIPi0gZdfWqUGOFhIJOw4eKZEzGp++I+MWPPVieCnT55vcTmm2zg13uP0fVykmukWqZszG/ZNpPKYleOqnZOqQj7O3au8Ywz18F/pqD++PsUzxRVeXxSOOwmjQ0D2Pe/9yutz62pyiFGAzDsaI6QJBAMn8DeBT3AtcWuONdiHL3yC4NkGJDdyBbMOaWyvrcvUUZr13uS9mZO6pLTN6v9tkmPUdvYxcPTJ9wdGR7NcNPDsCQQD6qluGI2VAlz4s5UoDnelFKrwDPeiruE3I6wsrasK6h37DsAE6OrQgx2dm4yH7ntJHUlJCZ5ay1EBNfEexgQv7AkA1r2vUwxVKY7q4nqHWa8SbgrrRAmePw0qwVreC3erJHyoLk+XBpnqPQKIF+8tAueU5yTTXOLD/WZOJazrDEf5/AkBpwG+Ggu5Xtrcbd8ynA/sDHElf0MGVmNbwOgFnWs42pa1cX6fU6ilOXvIH3TFcF6A9SMS9kThpz9QlHJaek4P7AkAavQillA/wnrha9GsK5UFmzmwNfkjLLW4psAUsXOsqFXWMoxTd0xWuSbuVOzERpbFMBl1VoZQmD9BLSVOTNe+v"
)

DEFAULT_SESSION: Dict[str, str] = {
    "p3": "25272056",
}

TOKEN_KEY_BASE0 = bytes.fromhex("5a0b1252b41e6bf509dd542a66d25a47")
TOKEN_KEY_BASE1 = bytes.fromhex("16a7f4c45ec7a517d82f84e753fc5ecd")
NATIVE_AES_SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cfd0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdbe0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9ee1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16"
)
NATIVE_AES_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)
NATIVE_RSA_N = int(
    "bd95ed3c46e9cc7e5174db00493f54c9fcd307a689260aeac7c9ca1fb635b45083d54dce90b00a4d98f8baa508edb4aa14efce8d6cbf73f6c0bb9fddf522699a"
    "e0106c19bfc2bd84147d1d20ecafd4796d01b4d7f8d785f58408aa0fc91c30be2198c14a45bb7714ae2bd03bc571d4d5e7dbf8e24b60a48e936076ec1e1216d1",
    16,
)
NATIVE_RSA_E = 65537
IV_XOR_CONST = 0xC83C4ED0


def p7_encrypt(s: str) -> str:
    out = ["__"]
    repl = {1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1, 0: 0}
    for ch in s or "":
        if "0" <= ch <= "9":
            out.append(str((repl[ord(ch) - 48] * 3) % 10))
        else:
            out.append(ch)
    return "".join(out)


def load_session() -> Dict[str, str]:
    data = DEFAULT_SESSION.copy()
    # 生成 8 位随机数字作为 usr
    data["usr"] = str(random.randint(10000000, 99999999))
    # 补全必要的派生字段（这些是算法必须的，不补会出错）
    if not data.get("p7"):
        data["p7"] = p7_encrypt("1234567890abcdef")
    if not data.get("p31"):
        data["p31"] = data["p7"]
    if not data.get("p30"):
        data["p30"] = "__"
    if not data.get("devId"):
        data["devId"] = data.get("p7", "")
    return data


def sorted_param_str(params: Dict[str, Any]) -> str:
    parts = []
    for k in sorted(str(x) for x in params.keys() if str(x)):
        v = params.get(k, "")
        if v is None or str(v) == "":
            continue
        parts.append(f"{k}={v}")
    return "&".join(parts)


_SIGN_KEY = None


def app_sign(sorted_s: str) -> str:
    global _SIGN_KEY
    if _SIGN_KEY is None:
        raw = base64.b64decode(EMBEDDED_KEY_PK8_B64)
        _SIGN_KEY = serialization.load_der_private_key(raw, password=None)
    sig = _SIGN_KEY.sign(sorted_s.encode("utf-8"), padding.PKCS1v15(), hashes.SHA1())
    return base64.b64encode(sig).decode("ascii")


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        m = re.search(r"\d+", str(v or ""))
        return int(m.group(0)) if m else default


def extract_token_b64(auth: Any, chapter_id: int) -> str:
    if not isinstance(auth, dict):
        raise RuntimeError("auth error")
    body = auth.get("body")
    if not isinstance(body, dict):
        raise RuntimeError("no auth body")
    key = f"chapter_{chapter_id}"
    node = body.get(key)
    if isinstance(node, dict) and node.get("token"):
        return str(node["token"])
    if body.get("token"):
        return str(body["token"])
    for value in body.values():
        if isinstance(value, dict) and value.get("token"):
            return str(value["token"])
    raise RuntimeError("no token")


def _rol3(x: int) -> int:
    return (((x << 3) & 0xff) | (x >> 5)) & 0xff


ZHANGYUE_CTR_POST_XOR = bytes((~_rol3(value)) & 0xff for value in range(256))


def _gf_xtime(a: int) -> int:
    return (((a << 1) & 0xff) ^ (0x1b if a & 0x80 else 0)) & 0xff


def _gf_mul(a: int, b: int) -> int:
    out = 0
    while b:
        if b & 1:
            out ^= a
        a = _gf_xtime(a)
        b >>= 1
    return out & 0xff


def _ror32(v: int, n: int) -> int:
    return ((v >> n) | ((v & ((1 << n) - 1)) << (32 - n))) & 0xffffffff


def _native_t_tables() -> Tuple[List[int], List[int], List[int], List[int]]:
    t0 = [(_gf_mul(s, 3) << 24) | (_gf_mul(s, 10) << 16) | (s << 8) | _gf_mul(s, 9) for s in NATIVE_AES_SBOX]
    return t0, [_ror32(v, 8) for v in t0], [_ror32(v, 16) for v in t0], [_ror32(v, 24) for v in t0]


_NATIVE_T = _native_t_tables()


@lru_cache(maxsize=512)
def _native_key_schedule(key: bytes) -> Tuple[int, ...]:
    if len(key) != 16:
        raise ValueError("bad key")
    words = [int.from_bytes(key[i:i + 4], "big") for i in range(0, 16, 4)]
    for rcon in NATIVE_AES_RCON:
        t = words[-1]
        rot = ((t << 8) & 0xffffffff) | (t >> 24)
        sub = 0
        for shift in (24, 16, 8, 0):
            sub |= NATIVE_AES_SBOX[(rot >> shift) & 0xff] << shift
        sub ^= rcon << 24
        words.append(words[-4] ^ sub)
        words.append(words[-4] ^ words[-1])
        words.append(words[-4] ^ words[-1])
        words.append(words[-4] ^ words[-1])
    return tuple(x & 0xffffffff for x in words)


def _native_block(round_keys: Tuple[int, ...], block16: bytes) -> bytes:
    if len(block16) != 16:
        raise ValueError("bad block")
    t0, t1, t2, t3 = _NATIVE_T
    s0 = round_keys[0] ^ int.from_bytes(block16[0:4], "big")
    s1 = round_keys[1] ^ int.from_bytes(block16[4:8], "big")
    s2 = round_keys[2] ^ int.from_bytes(block16[8:12], "big")
    s3 = round_keys[3] ^ int.from_bytes(block16[12:16], "big")
    for r in range(1, 10):
        n0 = t0[s0 >> 24] ^ t1[(s1 >> 16) & 0xff] ^ t2[(s2 >> 8) & 0xff] ^ t3[s3 & 0xff] ^ round_keys[4 * r]
        n1 = t0[s1 >> 24] ^ t1[(s2 >> 16) & 0xff] ^ t2[(s3 >> 8) & 0xff] ^ t3[s0 & 0xff] ^ round_keys[4 * r + 1]
        n2 = t0[s2 >> 24] ^ t1[(s3 >> 16) & 0xff] ^ t2[(s0 >> 8) & 0xff] ^ t3[s1 & 0xff] ^ round_keys[4 * r + 2]
        n3 = t0[s3 >> 24] ^ t1[(s0 >> 16) & 0xff] ^ t2[(s1 >> 8) & 0xff] ^ t3[s2 & 0xff] ^ round_keys[4 * r + 3]
        s0, s1, s2, s3 = n0 & 0xffffffff, n1 & 0xffffffff, n2 & 0xffffffff, n3 & 0xffffffff
    out = bytearray(16)
    final = round_keys[40:44]
    selectors = (
        (s0 >> 24, 24, 0), ((s1 >> 16) & 0xff, 16, 0), ((s2 >> 8) & 0xff, 8, 0), (s3 & 0xff, 0, 0),
        (s1 >> 24, 24, 1), ((s2 >> 16) & 0xff, 16, 1), ((s3 >> 8) & 0xff, 8, 1), (s0 & 0xff, 0, 1),
        (s2 >> 24, 24, 2), ((s3 >> 16) & 0xff, 16, 2), ((s0 >> 8) & 0xff, 8, 2), (s1 & 0xff, 0, 2),
        (s3 >> 24, 24, 3), ((s0 >> 16) & 0xff, 16, 3), ((s1 >> 8) & 0xff, 8, 3), (s2 & 0xff, 0, 3),
    )
    for i, (src, shift, key_index) in enumerate(selectors):
        out[i] = NATIVE_AES_SBOX[src & 0xff] ^ ((final[key_index] >> shift) & 0xff)
    return bytes(out)


def zhangyue_native_ctr(data: bytes, key: bytes, iv: bytes) -> bytes:
    if len(key) != 16 or len(iv) != 16:
        raise ValueError("bad ctr args")
    if not data:
        return b""
    counter = bytearray(iv)
    key_stream = bytearray(len(data))
    round_keys = _native_key_schedule(key)
    for off in range(0, len(data), 16):
        end = min(off + 16, len(data))
        key_stream[off:end] = _native_block(round_keys, bytes(counter))[:end - off]
        for idx in (13, 12, 11, 10):
            counter[idx] = (counter[idx] + 1) & 0xff
            if counter[idx]:
                break
    return strxor(data, key_stream).translate(ZHANGYUE_CTR_POST_XOR)


def native_rsa_unwrap(cipher: bytes) -> bytes:
    if len(cipher) != 128:
        raise ValueError("bad token length")
    m = int(gmpy2.powmod(int.from_bytes(cipher, "big"), NATIVE_RSA_E, NATIVE_RSA_N)).to_bytes(128, "big")
    if not m.startswith(b"\x00\x01"):
        raise ValueError("bad token padding")
    sep = m.find(b"\x00", 2)
    if sep < 0:
        raise ValueError("bad token sep")
    return m[sep + 1:]


def _token_first_layer_key(seed4: bytes) -> bytes:
    return bytes((TOKEN_KEY_BASE0[i] + TOKEN_KEY_BASE1[i] + seed4[i & 3]) & 0xff for i in range(16))


def unwrap_dejian_token(raw: bytes) -> bytes:
    if len(raw) < 12:
        raise ValueError("bad raw token")
    struct_len = int.from_bytes(raw[:4], "little")
    if struct_len <= 0 or struct_len > 0x400:
        raise ValueError("bad token header")
    key = _token_first_layer_key(raw[4:8])
    body = zhangyue_native_ctr(raw[8:], key, bytes((~key[(i + 5) & 15]) & 0xff for i in range(16)))
    return raw[:8] + body


def derive_stage1_key(raw_token: bytes, usr: str, dev: str) -> bytes:
    token = unwrap_dejian_token(raw_token)
    if len(token) < 0x4c:
        raise ValueError("token too short")
    iv = bytes.fromhex("000001018b0000000000000000000000")
    slot0 = token[0x0c:0x1c]
    check = token[0x2c:0x3c]
    key = zhangyue_native_ctr(slot0, hashlib.md5(usr.encode("utf-8")).digest(), iv)
    if hashlib.md5(key).digest() != check:
        raise ValueError("token check failed")
    return key


def iv_from_stage1(key16: bytes) -> bytes:
    iv = bytearray()
    for i in range(0, 16, 4):
        d = struct.unpack_from("<I", key16, i)[0] ^ IV_XOR_CONST
        iv += struct.pack("<I", d)
    return bytes(iv)


def parse_zip_stored(data: bytes):
    off = 0
    while off + 30 <= len(data) and data[off:off + 4] == b"PK\x03\x04":
        _sig, _ver, flag, method, _mt, _md, _crc, csize, _usize, nlen, xlen = struct.unpack_from("<IHHHHHIIIHH", data, off)
        name = data[off + 30: off + 30 + nlen].decode("utf-8", "replace")
        data_off = off + 30 + nlen + xlen
        payload = data[data_off: data_off + csize]
        yield name, method, payload
        off = data_off + csize
        if flag & 8:
            off += 16 if data[off:off + 4] == b"PK\x07\x08" else 12


def decrypt_payload(payload: bytes, key: bytes) -> bytes:
    dec = zhangyue_native_ctr(payload, key, iv_from_stage1(key))
    last_err: Optional[Exception] = None
    for skip in range(8):
        try:
            return zlib.decompress(dec[skip:], -15)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"inflate failed: {last_err}")


def strip_zy_header(raw: bytes) -> bytes:
    if raw.startswith(b"<?xml") or raw.startswith(b"<"):
        return raw
    idx = raw.find(b"<?xml")
    if 0 < idx <= 16:
        return raw[idx:]
    return raw


def html_to_text(html: str) -> str:
    # 删除 class="text-title-1" 的 h1 标签
    html = re.sub(r'<h1[^>]*class="text-title-1"[^>]*>.*?</h1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    t = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</p\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    
    # 合并连续换行为一个
    t = re.sub(r'\n{2,}', '\n', t)
    
    for a, b in [("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'")]:
        t = t.replace(a, b)
    t = t.replace("\r", "")
    t = t.strip()
    return t


def decrypt_epub_text(epub_data: bytes, key: bytes) -> str:
    text = ""
    for name, method, payload in parse_zip_stored(epub_data):
        if name == "mimetype" or name.endswith("encryption.xml"):
            continue
        body = strip_zy_header(decrypt_payload(payload, key))
        if name.endswith((".xhtml", ".html")):
            text = html_to_text(body.decode("utf-8", "replace"))
    if not text:
        raise RuntimeError("no text")
    return text


def 创建得间HTTP会话(并发数: int) -> aiohttp.ClientSession:
    并发数 = max(1, int(并发数 or 1))
    connector = aiohttp.TCPConnector(
        limit=并发数,
        limit_per_host=并发数,
        keepalive_timeout=30,
        ttl_dns_cache=300,
    )
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=120)
    return aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={"User-Agent": APP_UA, "Accept": "application/json,text/plain,*/*"},
    )


async def 异步请求得间JSON(
    HTTP会话: aiohttp.ClientSession,
    方法: str,
    地址: str,
    *,
    参数: Optional[Dict[str, Any]] = None,
    表单: Optional[Dict[str, Any]] = None,
    请求信号量: Optional[asyncio.Semaphore] = None,
    超时秒数: int = 20,
) -> Any:
    超时 = aiohttp.ClientTimeout(total=max(1, int(超时秒数 or 20)))

    async def 请求() -> bytes:
        async with HTTP会话.request(
            方法,
            地址,
            params=参数,
            data=表单,
            timeout=超时,
        ) as 响应:
            响应.raise_for_status()
            return await 响应.read()

    if 请求信号量 is None:
        原始响应 = await 请求()
    else:
        async with 请求信号量:
            原始响应 = await 请求()
    if not 原始响应:
        return {}
    try:
        return json.loads(原始响应.decode("utf-8-sig", "replace"))
    except json.JSONDecodeError as 异常:
        raise RuntimeError("得间接口响应不是JSON") from 异常


async def 异步下载得间字节(
    HTTP会话: aiohttp.ClientSession,
    地址: str,
    请求信号量: Optional[asyncio.Semaphore] = None,
) -> bytes:
    超时 = aiohttp.ClientTimeout(total=120)

    async def 请求() -> bytes:
        async with HTTP会话.get(地址, timeout=超时) as 响应:
            响应.raise_for_status()
            return await 响应.read()

    if 请求信号量 is None:
        return await 请求()
    async with 请求信号量:
        return await 请求()


class 得间单章异步客户端:
    """参考得间.py 的 DejianClient，仅将 requests 会话替换为共享 aiohttp 会话。"""

    def __init__(
        self,
        HTTP会话: aiohttp.ClientSession,
        请求信号量: asyncio.Semaphore,
        批量清单: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.HTTP会话 = HTTP会话
        self.请求信号量 = 请求信号量
        self.会话参数 = load_session()
        self._批量清单 = dict(批量清单 or {})
        self._批量清单锁 = asyncio.Lock()

    def 账号参数(self) -> Dict[str, str]:
        参数: Dict[str, str] = {}
        for 键 in ("zyeid", "usr", "rgt", "p1"):
            值 = self.会话参数.get(键, "")
            if 值 or 键 in ("usr", "rgt", "p1"):
                参数[键] = 值
        if self.会话参数.get("usr"):
            参数["ku"] = self.会话参数["usr"]
        return 参数

    def 设备参数(self) -> Dict[str, str]:
        键列表 = (
            "pc", "p2", "p3", "p4", "p5", "p7", "p9", "p12", "p16",
            "p21", "p22", "p25", "p26", "p28", "p29", "p30", "p31",
            "p33", "p34", "firm", "d1",
        )
        return {键: self.会话参数.get(键, "") for 键 in 键列表 if 键 in self.会话参数}

    def 附加参数(self, 参数: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        结果: Dict[str, Any] = {}
        结果.update(self.账号参数())
        结果.update(self.设备参数())
        if 参数:
            结果.update(参数)
        return 结果

    def 签名参数(self, 参数: Dict[str, Any]) -> Dict[str, Any]:
        结果 = dict(参数)
        结果["timestamp"] = str(int(time.time() * 1000))
        结果["sign"] = app_sign(sorted_param_str(结果))
        return 结果

    async def 获取JSON(
        self,
        路径或地址: str,
        参数: Optional[Dict[str, Any]] = None,
        *,
        需要公共参数: bool = True,
    ) -> Any:
        地址 = 路径或地址 if 路径或地址.startswith("http") else f"{BASE}{路径或地址}"
        查询参数 = self.附加参数(参数) if 需要公共参数 else dict(参数 or {})
        return await 异步请求得间JSON(
            self.HTTP会话,
            "GET",
            地址,
            参数=查询参数,
            请求信号量=self.请求信号量,
        )

    async def 提交JSON(self, 路径或地址: str, 表单: Dict[str, Any]) -> Any:
        地址 = 路径或地址 if 路径或地址.startswith("http") else f"{BASE}{路径或地址}"
        return await 异步请求得间JSON(
            self.HTTP会话,
            "POST",
            地址,
            参数=self.附加参数({}),
            表单=表单,
            请求信号量=self.请求信号量,
        )

    async def 下载(self, 地址: str) -> bytes:
        return await 异步下载得间字节(self.HTTP会话, 地址, self.请求信号量)

    async def 获取批量下载清单(self, 书籍编号: str) -> Dict[str, Any]:
        if self._批量清单.get("downUrl"):
            return self._批量清单
        async with self._批量清单锁:
            if self._批量清单.get("downUrl"):
                return self._批量清单
            信息 = await self.获取JSON(
                "/zybook3/u/p/api.php",
                {"Act": "batchDownloadChapteres", "bid": str(书籍编号)},
            )
            正文 = 信息.get("body") if isinstance(信息, dict) else None
            地址 = str(正文.get("downUrl") or "").strip() if isinstance(正文, dict) else ""
            if not 地址:
                raise RuntimeError("no downUrl")
            self._批量清单 = {
                "bookId": str(书籍编号),
                "downUrl": 地址,
                "maxChapId": _to_int(正文.get("maxChapId")),
                "downloadCount": _to_int(正文.get("downloadCount")),
            }
            return self._批量清单

    async def 安全章节列表(
        self,
        书籍编号: str,
        start: int = 1,
        end: int = 0,
        limit: int = 0,
    ) -> List[Dict[str, Any]]:
        基础地址 = str((await self.获取批量下载清单(书籍编号))["downUrl"])
        结果: List[Dict[str, Any]] = []
        当前章节 = max(1, int(start or 1))
        结束章节 = int(end or 0)
        最大数量 = int(limit or 0)
        while True:
            分隔符 = "&" if "?" in 基础地址 else "?"
            地址 = f"{基础地址}{分隔符}{urllib.parse.urlencode({'startChapID': 当前章节})}"
            信息 = await self.获取JSON(地址, 需要公共参数=False)
            正文 = 信息.get("body") if isinstance(信息, dict) else None
            if not isinstance(正文, dict):
                break
            章节列表 = 正文.get("downInfo") or []
            if not isinstance(章节列表, list):
                break
            已增加 = 0
            for 项 in 章节列表:
                if not isinstance(项, dict):
                    continue
                章节编号 = _to_int(项.get("chapterId"))
                if not 章节编号 or (结束章节 > 0 and 章节编号 > 结束章节):
                    continue
                结果.append(项)
                已增加 += 1
                if 最大数量 > 0 and len(结果) >= 最大数量:
                    return 结果
            if 正文.get("end") or not 章节列表 or 已增加 == 0:
                break
            最后章节 = _to_int((章节列表[-1] or {}).get("chapterId"))
            if 最后章节 <= 0:
                break
            当前章节 = 最后章节 + 1
            if 结束章节 > 0 and 当前章节 > 结束章节:
                break
        return 结果

    async def 查找章节(self, 书籍编号: str, 章节编号: int) -> Dict[str, Any]:
        章节编号 = int(章节编号)
        for start, end, limit in (
            (max(1, 章节编号 - 3), 章节编号 + 3, 50),
            (章节编号, 章节编号 + 10, 20),
            (1, 章节编号, 0),
        ):
            for 项 in await self.安全章节列表(书籍编号, start=start, end=end, limit=limit):
                if _to_int(项.get("chapterId")) == 章节编号:
                    return 项
        raise RuntimeError("chapter not found")

    async def 单章授权(self, 书籍编号: str, 章节编号: int) -> Any:
        表单 = self.签名参数(
            {
                "bookId": str(书籍编号),
                "chapterId": str(int(章节编号)),
                "devId": self.会话参数.get("devId", ""),
                "usrName": self.会话参数.get("usr", ""),
            }
        )
        表单.update({"type": "0", "fid": "72"})
        return await self.提交JSON("/dj_drm/djdrm/getAuthChapter", 表单)


def 解密得间单章正文(正文数据: bytes, 授权令牌: str, 用户名: str, 设备号: str) -> str:
    原始令牌 = native_rsa_unwrap(base64.b64decode(授权令牌))
    密钥 = derive_stage1_key(原始令牌, 用户名, 设备号)
    return decrypt_epub_text(正文数据, 密钥).strip()


async def 异步下载得间单章正文(
    HTTP会话: aiohttp.ClientSession,
    书籍编号: str,
    章节编号: int,
    请求信号量: asyncio.Semaphore,
    解密信号量: asyncio.Semaphore,
    客户端: Optional[得间单章异步客户端] = None,
) -> str:
    """与参考 get_chapter_text 相同的单章顺序，网络请求改为共享异步会话。"""
    for 重试轮次 in range(1, 得间单章重试次数 + 1):
        当前客户端 = 客户端 or 得间单章异步客户端(HTTP会话, 请求信号量)
        try:
            用户名 = str(当前客户端.会话参数.get("usr") or "")
            设备号 = str(当前客户端.会话参数.get("devId") or "")
            if not 用户名 or not 设备号:
                raise RuntimeError("bad session")
            章节项 = await 当前客户端.查找章节(书籍编号, 章节编号)
            正文地址 = str(
                章节项.get("url") or 章节项.get("downUrl") or 章节项.get("downloadUrl") or ""
            ).strip()
            if not 正文地址:
                raise RuntimeError("no chapter url")
            授权结果 = await 当前客户端.单章授权(书籍编号, 章节编号)
            授权令牌 = extract_token_b64(授权结果, 章节编号)
            正文数据 = await 当前客户端.下载(正文地址)
            async with 解密信号量:
                return await asyncio.get_running_loop().run_in_executor(
                    得间解密执行器,
                    解密得间单章正文,
                    正文数据,
                    授权令牌,
                    用户名,
                    设备号,
                )
        except Exception as 异常:
            logger.debug(
                f"得间单章下载重试：book_id={书籍编号}, chapter_id={章节编号}, "
                f"round={重试轮次}, error={type(异常).__name__}"
            )
            if 重试轮次 < 得间单章重试次数:
                await asyncio.sleep(0.05 * 重试轮次)
    return ""






def generate_search_usr(length: int = 6) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def 解析得间搜索数据(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict) or data.get("code", -1) != 0:
        return {"success": True, "count": 0, "results": [], "raw": data}

    body = data.get("body") or {}
    book = body.get("book") if isinstance(body, dict) else {}
    datas = (book or {}).get("datas") if isinstance(book, dict) else []
    if not isinstance(datas, list):
        datas = []

    results: List[Dict[str, Any]] = []
    for item in datas:
        if not isinstance(item, dict):
            continue
        info = item.get("data_info") or {}
        if not isinstance(info, dict) or not info:
            continue

        raw_name = str(info.get("bookName") or info.get("displayBookName") or "")
        title = raw_name.strip("《》")
        title = re.sub(r"^《|》$", "", raw_name)
        if not title:
            title = raw_name

        complete_state = info.get("completeState") or "N"
        status = "已完结" if complete_state == "Y" else "连载中"
        tag_list = info.get("tagList") or []
        if not isinstance(tag_list, list):
            tag_list = []

        kind_parts = ["得间"]
        if tag_list:
            kind_parts.extend(str(x) for x in tag_list if x)
        kind_parts.append(status)

        results.append(
            {
                "title": title,
                "author": str(info.get("bookAuthor") or ""),
                "abstract": str(info.get("bookDescription") or ""),
                "cover_url": str(info.get("picUrl") or ""),
                "book_id": str(info.get("bookId") or ""),
                "source": "得间",
                "kind": ",".join(kind_parts),
                "word_count": "",
                "last_chapter": f"得间_{status}",
            }
        )

    return {"success": True, "count": len(results), "results": results}


async def 异步搜索得间书籍(
    HTTP会话: aiohttp.ClientSession,
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    current_page = max(1, int(page or 1))
    data = await 异步请求得间JSON(
        HTTP会话,
        "GET",
        f"{BASE}/zybk/api/search/freeapp/book",
        参数={
            "word": query,
            "type": "book,listen",
            "pageSize": page_size,
            "currentPage": current_page,
            "usr": generate_search_usr(),
            "p2": "124013",
            "p3": "17418056",
        },
    )
    return 解析得间搜索数据(data)


def 解析得间书籍详情(data: Any, bid: str) -> Dict[str, Any]:
    if not isinstance(data, dict) or data.get("code", -1) != 0:
        return {"success": False, "detail": {}, "raw": data}

    body = data.get("body") or {}
    info = body.get("bookInfo") if isinstance(body, dict) else {}
    if not isinstance(info, dict):
        info = {}

    complete_state = info.get("completeState") or "N"
    status = "已完结" if complete_state == "Y" else "连载中"
    cats = info.get("categorys") or []
    if not isinstance(cats, list):
        cats = []
    cat_names = []
    for c in cats:
        if isinstance(c, dict) and c.get("name"):
            cat_names.append(str(c["name"]))

    price = info.get("priceInfo") or {}
    if not isinstance(price, dict):
        price = {}

    detail = {
        "book_id": str(info.get("bookId") or bid),
        "title": str(info.get("bookName") or ""),
        "author": str(info.get("author") or ""),
        "abstract": str(info.get("desc") or ""),
        "cover_url": str(info.get("picUrl") or ""),
        "word_count": str(info.get("wordCount") or info.get("wordNum") or ""),
        "status": status,
        "category": ",".join(cat_names),
        "from_source": str(info.get("fromSource") or ""),
        "is_free": bool(price.get("isFree")),
        "last_chapter_time": str(info.get("lastChapterTime") or ""),
        "raw_book_info": info,
    }
    return {"success": True, "detail": detail, "raw": data}


async def 异步获取得间书籍详情(
    HTTP会话: aiohttp.ClientSession,
    bid: str,
) -> Dict[str, Any]:
    data = await 异步请求得间JSON(
        HTTP会话,
        "GET",
        f"{BASE}/zybk/api/detail/index",
        参数={"p3": "17111111", "p2": "1", "p4": "1", "bid": str(bid)},
    )
    return 解析得间书籍详情(data, bid)


async def 异步获取得间批量下载清单(
    HTTP会话: aiohttp.ClientSession,
    bid: str,
) -> Dict[str, Any]:
    """下载前读取实际可访问章节范围，避免把购买章节当作网络失败反复重试。"""
    try:
        客户端 = 得间单章异步客户端(HTTP会话, asyncio.Semaphore(2))
        return await 客户端.获取批量下载清单(bid)
    except Exception as 异常:
        logger.debug(
            f"得间可下载章节范围获取失败：book_id={bid}, "
            f"error={type(异常).__name__}"
        )
        return {}


def 解析得间章节目录(xml_text: str) -> Dict[str, Any]:
    if not xml_text or "<cp>" not in xml_text:
        return {"success": False, "count": 0, "chapters": [], "raw": xml_text}

    total_record = 0
    m_total = re.search(r"<totalRecord>(\d+)</totalRecord>", xml_text)
    if m_total:
        total_record = int(m_total.group(1))

    chapters: List[Dict[str, Any]] = []
    for m in re.finditer(
        r"<cp>\s*<id>(\d+)</id>\s*<cs>(\d+)</cs>\s*<wc>(\d+)</wc>.*?<cn>(.*?)</cn>",
        xml_text,
        flags=re.S,
    ):
        chapters.append(
            {
                "chapter_id": int(m.group(1)),
                "cs": int(m.group(2)),
                "word_count": int(m.group(3)),
                "title": re.sub(r"\s+", " ", m.group(4)).strip(),
            }
        )

    if not chapters:
        ids = re.findall(r"<cp>\s*<id>(\d+)</id>", xml_text)
        titles = re.findall(r"<cn>(.*?)</cn>", xml_text)
        for i, cid in enumerate(ids):
            chapters.append(
                {
                    "chapter_id": int(cid),
                    "cs": 0,
                    "word_count": 0,
                    "title": titles[i].strip() if i < len(titles) else "",
                }
            )

    return {
        "success": True,
        "count": len(chapters),
        "total_record": total_record or len(chapters),
        "chapters": chapters,
        "raw": xml_text,
    }


async def 异步获取得间章节目录(
    HTTP会话: aiohttp.ClientSession,
    bid: str,
) -> Dict[str, Any]:
    async with HTTP会话.get(
        f"{BASE}/zybook/u/p/api.php",
        params={"Act": "getChapterListVersion", "p4": "501656", "bid": str(bid)},
        timeout=aiohttp.ClientTimeout(total=20),
    ) as response:
        response.raise_for_status()
        xml_text = await response.text(encoding="utf-8", errors="replace")
    return 解析得间章节目录(xml_text)


# ===== 业务封装 =====

进度日志分段数 = 10
得间域名正则 = re.compile(r"palmestore\.com|zhangyue\.com|ireader\.com|dejian", re.I)
链接正则 = re.compile(r"https?://[^\s'\"<>]+", re.I)
书籍编号正则 = re.compile(r"(?:bid|book[_-]?id|bookId)=(\d{5,})", re.I)
路径编号正则 = re.compile(r"/(?:book|detail|books?)/(\d{5,})", re.I)


def 计算得间单章并发数(章节总数: int) -> int:
    return max(1, min(得间单章最大并发数, int(章节总数 or 0)))


def 得间存在未购买章节(目录: list[dict[str, Any]], 批量清单: Dict[str, Any]) -> bool:
    """根据 App 清单判断整本是否含当前会话不可访问的章节。"""
    if not 批量清单 or not 目录:
        return False
    总章节数 = len(目录)
    可下载章节数 = _to_int(批量清单.get("downloadCount"))
    最大可下载章节号 = _to_int(批量清单.get("maxChapId"))
    目录章节号 = [
        _to_int(章节.get("id") or 章节.get("chapter_id"))
        for 章节 in 目录
    ]
    有效章节号 = [章节号 for 章节号 in 目录章节号 if 章节号 > 0]
    if 可下载章节数 > 0 and 可下载章节数 < 总章节数:
        return True
    if 最大可下载章节号 > 0 and 有效章节号:
        return 最大可下载章节号 < max(有效章节号)
    return False


def 获取得间小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取直接得间来源(命令文本) or 提取事件得间来源(event)
    if 来源 is None:
        return None
    return 生成下载回复流(event, 来源, 配置)


async def 生成下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取书籍编号(来源)
    if not 书籍编号:
        yield "下载失败"
        return
    try:
        async with 创建得间HTTP会话(2) as HTTP会话:
            详情包, 目录包, 批量清单 = await asyncio.gather(
                异步获取得间书籍详情(HTTP会话, 书籍编号),
                异步获取得间章节目录(HTTP会话, 书籍编号),
                异步获取得间批量下载清单(HTTP会话, 书籍编号),
            )
        if not 详情包.get("success"):
            logger.warning(f"得间小说详情失败：book_id={书籍编号}")
            yield "下载失败"
            return
        详情 = 详情包.get("detail") or {}
        目录 = 目录包.get("chapters") or []
        if not 目录:
            logger.warning(f"得间小说目录失败：book_id={书籍编号}")
            yield "下载失败"
            return

        if 得间存在未购买章节(目录, 批量清单):
            可下载章节数 = _to_int(批量清单.get("downloadCount"))
            logger.warning(
                f"得间小说包含未购买章节：book_id={书籍编号}, "
                f"available={可下载章节数}, total={len(目录)}"
            )
            yield "该书包含未购买章节，暂不支持下载"
            return

        书名 = str(详情.get("title") or "未知")
        作者 = str(详情.get("author") or "未知")
        状态 = "完结" if "完结" in str(详情.get("status") or "") else "连载"
        字数 = 格式化字数(详情.get("word_count"))
        logger.info(f"得间小说开始下载：book_id={书籍编号}, title={书名}, author={作者}, chapters={len(目录)}")
        yield "\n".join([
            f"书名：{书名}",
            f"作者：{作者}",
            f"状态：{状态}",
            f"章节：{len(目录)} 章",
            f"字数：{字数}",
            "",
            "正在下载中请稍等.....",
        ])

        章节结果 = await 下载全部章节(书籍编号, 目录, 批量清单=批量清单)
        成功 = [x for x in 章节结果 if x.get("content")]
        if len(成功) != len(目录):
            logger.warning(
                f"得间小说下载失败：book_id={书籍编号}, success={len(成功)}, total={len(目录)}"
            )
            yield "下载失败"
            return

        文件名, 文件内容 = 生成小说文件(书籍编号, 书名, 作者, 状态, 字数, 章节结果)
        发送结果 = await 准备发送文本文件(event, 文件名, 文件内容, 配置, 书名=书名, 作者=作者)
        if 发送结果.get("sent"):
            启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        降级 = str(发送结果.get("fallback_text") or "")
        if 降级:
            try:
                yield 降级
            finally:
                启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        logger.warning(f"得间小说完成消息发送失败：book_id={书籍编号}, error={发送结果.get('error')}")
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(f"得间小说下载失败：source={来源}, error={exc}")
        yield "下载失败"


async def 下载全部章节(
    书籍编号: str,
    目录: list[dict[str, Any]],
    *,
    批量清单: Optional[Dict[str, Any]] = None,
) -> list[dict[str, str]]:
    总数 = len(目录)
    结果: list[dict[str, str] | None] = [None] * 总数
    章节下标表: Dict[int, List[int]] = {}
    无效章节下标: List[int] = []
    for 下标, 章节 in enumerate(目录):
        章节编号 = _to_int(章节.get("id") or 章节.get("chapter_id"))
        if 章节编号 > 0:
            章节下标表.setdefault(章节编号, []).append(下标)
        else:
            无效章节下标.append(下标)
    if not 章节下标表:
        return []

    实际正文并发数 = 计算得间单章并发数(len(章节下标表))
    解密并发数 = max(1, min(实际正文并发数, 得间解密最大动态并发数))
    完成 = len(无效章节下标)
    成功 = 0
    上次日志百分比 = 0
    进度锁 = asyncio.Lock()
    请求信号量 = asyncio.Semaphore(实际正文并发数)
    解密信号量 = asyncio.Semaphore(解密并发数)
    async with 创建得间HTTP会话(实际正文并发数) as HTTP会话:
        客户端 = 得间单章异步客户端(HTTP会话, 请求信号量, 批量清单)
        logger.info(
            f"得间小说章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%, "
            f"mode=single_chapter, concurrency={实际正文并发数}, "
            f"max_concurrency={得间单章最大并发数}, session_reuse=on, "
            f"decrypt_concurrency={解密并发数}, retries={得间单章重试次数}"
        )

        async def 下载一章(章节编号: int, 下标列表: List[int]) -> None:
            nonlocal 完成, 成功, 上次日志百分比
            正文 = (
                await 异步下载得间单章正文(
                    HTTP会话,
                    书籍编号,
                    章节编号,
                    请求信号量,
                    解密信号量,
                    客户端,
                )
            ).strip()
            for 下标 in 下标列表:
                章 = 目录[下标]
                标题 = str(章.get("title") or 章.get("cn") or f"第{章节编号}章")
                结果[下标] = {"title": 标题, "content": 正文, "id": str(章节编号)}
            async with 进度锁:
                完成 += len(下标列表)
                if 正文:
                    成功 += len(下标列表)
                当前百分比 = int(完成 * 100 / max(总数, 1))
                if 完成 == 总数 or 当前百分比 >= min(100, 上次日志百分比 + 进度日志分段数):
                    logger.info(
                        f"得间小说章节进度：book_id={书籍编号}, progress={完成}/{总数}, "
                        f"percent={当前百分比}%, success={成功}, failed={完成 - 成功}"
                    )
                    上次日志百分比 = 当前百分比

        await asyncio.gather(
            *(下载一章(章节编号, 下标列表) for 章节编号, 下标列表 in 章节下标表.items())
        )
    输出: list[dict[str, str]] = []
    for 下标, 章 in enumerate(目录):
        已下载 = 结果[下标]
        if 已下载 is None:
            章节编号 = _to_int(章.get("id") or 章.get("chapter_id"))
            已下载 = {
                "title": str(章.get("title") or 章.get("cn") or f"第{章节编号}章"),
                "content": "",
                "id": str(章节编号),
            }
        输出.append(已下载)
    logger.info(
        f"得间小说章节下载完成：book_id={书籍编号}, success={成功}, total={总数}, "
        f"mode=single_chapter, concurrency={实际正文并发数}, "
        f"max_concurrency={得间单章最大并发数}, session_reuse=on, "
        f"decrypt_concurrency={解密并发数}, retries={得间单章重试次数}"
    )
    return 输出


def 生成小说文件(书籍编号: str, 书名: str, 作者: str, 状态: str, 字数: str, 章节结果: list[dict[str, str]]) -> tuple[str, bytes]:
    文件名 = f"[{状态}]书名：{清理文件名(书名)} 作者：{清理文件名(作者)}.txt"
    行 = [文件声明, "", f"名称：{书名}", f"作者：{作者}", f"状态：{状态}", f"字数：{字数}", f"书籍ID：{书籍编号}", f"章节数：{len(章节结果)}", ""]
    for 章 in 章节结果:
        if not 章.get("content"):
            continue
        标题 = str(章.get("title") or "章节")
        正文 = 去除章节正文重复标题(标题, 章.get("content"))
        行.extend([标题, "", 正文, ""])
    return 文件名, "\n".join(行).encode("utf-8")


async def 准备发送文本文件(event: Any, 文件名: str, 文件内容: bytes, 配置: Any = None, *, 书名: Any = "", 作者: Any = "") -> dict[str, Any]:
    缓存路径 = 写入缓存(文件名, 文件内容)
    if 小说网盘 is None:
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "小说网盘模块未加载"}
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not 网盘结果.get("success"):
            删除缓存(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(网盘结果.get("error") or "小说网盘未启用")}
        完成结果 = await 小说网盘.发送小说下载完成链接(event, 书名, 作者, str(网盘结果.get("share_url") or ""))
        if 完成结果.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 缓存路径, "error": str(完成结果.get("error") or "")}
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(完成结果.get("error") or "完成消息发送失败")}
    except Exception as exc:
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(exc)}


def 启动百度后台上传并清理(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    async def _任务() -> None:
        try:
            if 百度网盘 is not None and 源缓存路径:
                await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
        except Exception as exc:
            logger.warning(f"得间小说百度后台上传异常：file={文件名}, error={exc}")
        finally:
            删除缓存(源缓存路径)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_任务())
    except Exception:
        删除缓存(源缓存路径)


def 写入缓存(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 下载缓存目录 / 文件名
    序号 = 1
    while 路径.exists():
        路径 = 下载缓存目录 / f"{Path(文件名).stem}_{序号}.txt"
        序号 += 1
    路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(路径)
    return 路径


def 删除缓存(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    小说缓存工具.删除下载缓存文件(缓存路径)


def 提取直接得间来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or "")
    if not 得间域名正则.search(文本):
        return None
    m = 链接正则.search(文本)
    return m.group(0) if m else 文本.strip() or None


def 提取事件得间来源(event: Any) -> str | None:
    for 字段 in ("message_str", "message", "raw_message"):
        值 = getattr(event, 字段, None)
        if 值 is None:
            continue
        来源 = 提取直接得间来源(str(值))
        if 来源:
            return 来源
    return None


def 提取书籍编号(来源: str) -> str:
    文本 = str(来源 or "")
    for 正则 in (书籍编号正则, 路径编号正则):
        m = 正则.search(文本)
        if m:
            return m.group(1)
    m = re.search(r"(\d{6,})", 文本)
    return m.group(1) if m else ""


def 格式化字数(字数: Any) -> str:
    文本 = str(字数 or "").strip()
    if not 文本:
        return "未知"
    数字文本 = re.sub(r"[\s,，]", "", 文本)
    if 数字文本.endswith("字"):
        数字文本 = 数字文本[:-1]
    if 数字文本.isdigit():
        n = int(数字文本)
        return f"{round(n/10000, 1)}万字" if n >= 10000 else f"{n}字"
    return 文本


def 清理文件名(文件名: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", str(文件名 or "")).strip() or "未知"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    try:
        async with 创建得间HTTP会话(2) as HTTP会话:
            数据 = await 异步搜索得间书籍(HTTP会话, 关键词, 1, max(需要数量, 20))
    except Exception as exc:
        logger.warning(f"得间搜索失败：keyword={关键词}, error={exc}")
        return []
    结果 = []
    for item in 数据.get("results") or []:
        book_id = str(item.get("book_id") or "").strip()
        if not book_id:
            continue
        结果.append({
            "title": item.get("title") or "未知",
            "author": item.get("author") or "未知",
            "book_id": book_id,
            "platform": "得间",
            "url": f"https://dj.palmestore.com/zybk/api/detail/index?bid={book_id}",
            "heat": 0,
            "score": 0,
        })
        if len(结果) >= 需要数量:
            break
    return 结果
