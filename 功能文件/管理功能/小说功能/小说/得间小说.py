from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
import base64
import hashlib
import json
import random
import struct
import time
import urllib.parse
import zlib
import requests
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from astrbot.api import logger

try:
    from 功能文件.管理功能.网盘功能 import UC网盘
except Exception as exc:
    UC网盘 = None
    logger.warning(f"UC网盘模块加载失败：error={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={exc}")

下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
章节并发数 = 8

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

# 极简会话：只保留固定参数 p3，usr 由 load_session 动态生成
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
        _SIGN_KEY = RSA.import_key(raw)
    sig = pkcs1_15.new(_SIGN_KEY).sign(SHA1.new(sorted_s.encode("utf-8")))
    return base64.b64encode(sig).decode("ascii")


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        m = re.search(r"\d+", str(v or ""))
        return int(m.group(0)) if m else default


class DejianClient:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = load_session()
        self.s = requests.Session()
        self.s.verify = False
        requests.packages.urllib3.disable_warnings()
        self.s.headers.update({"User-Agent": APP_UA, "Accept": "application/json,text/plain,*/*"})

    def account_params(self) -> Dict[str, str]:
        p: Dict[str, str] = {}
        for k in ("zyeid", "usr", "rgt", "p1"):
            v = self.session.get(k, "")
            if v or k in ("usr", "rgt", "p1"):
                p[k] = v
        if self.session.get("usr"):
            p["ku"] = self.session["usr"]
        return p

    def device_params(self) -> Dict[str, str]:
        keys = [
            "pc", "p2", "p3", "p4", "p5", "p7", "p9", "p12", "p16",
            "p21", "p22", "p25", "p26", "p28", "p29", "p30", "p31",
            "p33", "p34", "firm", "d1",
        ]
        return {k: self.session.get(k, "") for k in keys if k in self.session}

    def append_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        out.update(self.account_params())
        out.update(self.device_params())
        if params:
            out.update(params)
        return out

    def sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(params)
        params["timestamp"] = str(int(time.time() * 1000))
        params["sign"] = app_sign(sorted_param_str(params))
        return params

    def get(self, path_or_url: str, params: Optional[Dict[str, Any]] = None, need_common: bool = True) -> Any:
        url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
        p = self.append_params(params) if need_common else dict(params or {})
        r = self.s.get(url, params=p, timeout=self.timeout)
        r.raise_for_status()
        return r.json() if r.content else {}

    def post(self, path_or_url: str, data: Dict[str, Any], need_common_url: bool = True) -> Any:
        url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
        params = self.append_params({}) if need_common_url else {}
        r = self.s.post(url, params=params, data=data, timeout=self.timeout)
        r.raise_for_status()
        return r.json() if r.content else {}

    def batch_download_manifest(self, bid: str) -> Dict[str, Any]:
        info = self.get("/zybook3/u/p/api.php", {"Act": "batchDownloadChapteres", "bid": str(bid)}, need_common=True)
        body = info.get("body") if isinstance(info, dict) else None
        if not isinstance(body, dict) or not body.get("downUrl"):
            raise RuntimeError("no downUrl")
        return {
            "bookId": str(bid),
            "downUrl": str(body.get("downUrl") or ""),
            "maxChapId": _to_int(body.get("maxChapId")),
            "downloadCount": _to_int(body.get("downloadCount")),
        }

    def drm_auth_chapter(self, bid: str, chapter_id: int) -> Any:
        body = {
            "bookId": str(bid),
            "chapterId": str(chapter_id),
            "devId": self.session.get("devId", ""),
            "usrName": self.session.get("usr", ""),
        }
        signed = self.sign_params(body)
        signed.update({"type": "0", "fid": "72"})
        return self.post("/dj_drm/djdrm/getAuthChapter", signed, need_common_url=True)

    def download(self, url: str) -> bytes:
        r = self.s.get(url, timeout=120)
        r.raise_for_status()
        return r.content


def chap_list_safe(client: DejianClient, bid: str, start: int = 1, end: int = 0, limit: int = 0) -> List[Dict[str, Any]]:
    base_url = client.batch_download_manifest(bid)["downUrl"]
    rows: List[Dict[str, Any]] = []
    cur = max(1, int(start or 1))
    end = int(end or 0)
    limit = int(limit or 0)
    while True:
        sep = "&" if "?" in base_url else "?"
        r = client.s.get(base_url + sep + urllib.parse.urlencode({"startChapID": cur}), timeout=client.timeout)
        r.raise_for_status()
        j = r.json() if r.content else {}
        body = j.get("body") if isinstance(j, dict) else None
        if not isinstance(body, dict):
            break
        items = body.get("downInfo") or []
        if not isinstance(items, list):
            break
        added = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            cid = int(it.get("chapterId") or 0)
            if not cid or (end > 0 and cid > end):
                continue
            rows.append(it)
            added += 1
            if limit > 0 and len(rows) >= limit:
                return rows
        if body.get("end") or not items or added == 0:
            break
        last_cid = int((items[-1] or {}).get("chapterId") or 0)
        if last_cid <= 0:
            break
        cur = last_cid + 1
        if end > 0 and cur > end:
            break
    return rows


def find_chapter_item(client: DejianClient, bid: str, chapter_id: int) -> Dict[str, Any]:
    chapter_id = int(chapter_id)
    for start, end, limit in (
        (max(1, chapter_id - 3), chapter_id + 3, 50),
        (chapter_id, chapter_id + 10, 20),
        (1, chapter_id, 0),
    ):
        for it in chap_list_safe(client, bid, start=start, end=end, limit=limit):
            if int(it.get("chapterId") or 0) == chapter_id:
                return it
    raise RuntimeError("chapter not found")


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
    for v in body.values():
        if isinstance(v, dict) and v.get("token"):
            return str(v["token"])
    raise RuntimeError("no token")


def _rol3(x: int) -> int:
    return (((x << 3) & 0xff) | (x >> 5)) & 0xff


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


def _native_key_schedule(key: bytes) -> List[int]:
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
    return [x & 0xffffffff for x in words]


def _native_block(key: bytes, block16: bytes) -> bytes:
    if len(block16) != 16:
        raise ValueError("bad block")
    rk = _native_key_schedule(key)
    t0, t1, t2, t3 = _NATIVE_T
    s0 = rk[0] ^ int.from_bytes(block16[0:4], "big")
    s1 = rk[1] ^ int.from_bytes(block16[4:8], "big")
    s2 = rk[2] ^ int.from_bytes(block16[8:12], "big")
    s3 = rk[3] ^ int.from_bytes(block16[12:16], "big")
    for r in range(1, 10):
        n0 = t0[s0 >> 24] ^ t1[(s1 >> 16) & 0xff] ^ t2[(s2 >> 8) & 0xff] ^ t3[s3 & 0xff] ^ rk[4 * r]
        n1 = t0[s1 >> 24] ^ t1[(s2 >> 16) & 0xff] ^ t2[(s3 >> 8) & 0xff] ^ t3[s0 & 0xff] ^ rk[4 * r + 1]
        n2 = t0[s2 >> 24] ^ t1[(s3 >> 16) & 0xff] ^ t2[(s0 >> 8) & 0xff] ^ t3[s1 & 0xff] ^ rk[4 * r + 2]
        n3 = t0[s3 >> 24] ^ t1[(s0 >> 16) & 0xff] ^ t2[(s1 >> 8) & 0xff] ^ t3[s2 & 0xff] ^ rk[4 * r + 3]
        s0, s1, s2, s3 = n0 & 0xffffffff, n1 & 0xffffffff, n2 & 0xffffffff, n3 & 0xffffffff
    out = bytearray(16)
    final = rk[40:44]
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
    counter = bytearray(iv)
    out = bytearray()
    for off in range(0, len(data), 16):
        ks = _native_block(key, bytes(counter))
        for c, k in zip(data[off:off + 16], ks):
            out.append((~_rol3(c ^ k)) & 0xff)
        for idx in (13, 12, 11, 10):
            counter[idx] = (counter[idx] + 1) & 0xff
            if counter[idx]:
                break
    return bytes(out)


def native_rsa_unwrap(cipher: bytes) -> bytes:
    if len(cipher) != 128:
        raise ValueError("bad token length")
    m = pow(int.from_bytes(cipher, "big"), NATIVE_RSA_E, NATIVE_RSA_N).to_bytes(128, "big")
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


def get_chapter_text(bid: str, chapter_id: int) -> str:
    client = DejianClient()
    sess = client.session
    usr = str(sess.get("usr") or "")
    dev = str(sess.get("devId") or "")
    if not usr or not dev:
        raise RuntimeError("bad session")

    item = find_chapter_item(client, bid, chapter_id)
    url = item.get("url") or item.get("downUrl") or item.get("downloadUrl") or ""
    if not url:
        raise RuntimeError("no chapter url")

    auth = client.drm_auth_chapter(bid, chapter_id)
    raw_token = native_rsa_unwrap(base64.b64decode(extract_token_b64(auth, chapter_id)))
    stage1 = derive_stage1_key(raw_token, usr, dev)
    return decrypt_epub_text(client.download(str(url)), stage1)






def generate_search_usr(length: int = 6) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def _http_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    r = requests.get(
        url,
        params=params,
        headers={"User-Agent": APP_UA, "Accept": "application/json,text/plain,*/*"},
        timeout=20,
        verify=False,
    )
    r.raise_for_status()
    if not r.content:
        return {}
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def _http_get_text(url: str, params: Optional[Dict[str, Any]] = None) -> str:
    r = requests.get(
        url,
        params=params,
        headers={"User-Agent": APP_UA, "Accept": "application/json,text/plain,*/*"},
        timeout=20,
        verify=False,
    )
    r.raise_for_status()
    return r.text or ""


def search_books(query: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """Test search against freeapp/book API."""
    current_page = max(1, int(page or 1))
    params = {
        "word": query,
        "type": "book,listen",
        "pageSize": page_size,
        "currentPage": current_page,
        "usr": generate_search_usr(),
        "p2": "124013",
        "p3": "17418056",
    }
    data = _http_get_json(f"{BASE}/zybk/api/search/freeapp/book", params)

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


def get_book_detail(bid: str) -> Dict[str, Any]:
    """Book detail: /zybk/api/detail/index"""
    params = {
        "p3": "17111111",
        "p2": "1",
        "p4": "1",
        "bid": str(bid),
    }
    data = _http_get_json(f"{BASE}/zybk/api/detail/index", params)
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


def get_chapter_catalog(bid: str) -> Dict[str, Any]:
    """Chapter catalog: /zybook/u/p/api.php?Act=getChapterListVersion"""
    params = {
        "Act": "getChapterListVersion",
        "p4": "501656",
        "bid": str(bid),
    }
    xml_text = _http_get_text(f"{BASE}/zybook/u/p/api.php", params)
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

# ===== 业务封装 =====

进度日志分段数 = 10
得间域名正则 = re.compile(r"palmestore\.com|zhangyue\.com|ireader\.com|dejian", re.I)
链接正则 = re.compile(r"https?://[^\s'\"<>]+", re.I)
书籍编号正则 = re.compile(r"(?:bid|book[_-]?id|bookId)=(\d{5,})", re.I)
路径编号正则 = re.compile(r"/(?:book|detail|books?)/(\d{5,})", re.I)


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
        详情包 = await asyncio.to_thread(get_book_detail, 书籍编号)
        if not 详情包.get("success"):
            logger.warning(f"得间小说详情失败：book_id={书籍编号}")
            yield "下载失败"
            return
        详情 = 详情包.get("detail") or {}
        目录包 = await asyncio.to_thread(get_chapter_catalog, 书籍编号)
        目录 = 目录包.get("chapters") or []
        if not 目录:
            logger.warning(f"得间小说目录失败：book_id={书籍编号}")
            yield "下载失败"
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

        章节结果 = await 下载全部章节(书籍编号, 目录)
        成功 = [x for x in 章节结果 if x.get("content")]
        if not 成功:
            logger.warning(f"得间小说下载失败：book_id={书籍编号}, success=0, total={len(目录)}")
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


async def 下载全部章节(书籍编号: str, 目录: list[dict[str, Any]]) -> list[dict[str, str]]:
    总数 = len(目录)
    结果: list[dict[str, str] | None] = [None] * 总数
    信号量 = asyncio.Semaphore(章节并发数)
    完成 = 0
    成功 = 0

    async def 拉一章(下标: int, 章: dict[str, Any]) -> None:
        nonlocal 完成, 成功
        cid = int(章.get("id") or 章.get("chapter_id") or 0)
        标题 = str(章.get("title") or 章.get("cn") or f"第{cid}章")
        正文 = ""
        async with 信号量:
            if cid > 0:
                try:
                    正文 = await asyncio.to_thread(get_chapter_text, 书籍编号, cid)
                except Exception as exc:
                    logger.warning(f"得间章节下载失败：book_id={书籍编号}, chapter_id={cid}, error={exc}")
                    正文 = ""
        结果[下标] = {"title": 标题, "content": str(正文 or "").strip(), "id": str(cid)}
        完成 += 1
        if 正文:
            成功 += 1
        if 完成 == 1 or 完成 == 总数 or 完成 % max(1, 总数 // 进度日志分段数) == 0:
            logger.info(
                f"得间小说章节进度：book_id={书籍编号}, progress={完成}/{总数}, "
                f"percent={int(完成 * 100 / max(总数, 1))}%, success={成功}, failed={完成 - 成功}"
            )

    await asyncio.gather(*(拉一章(i, 章) for i, 章 in enumerate(目录)))
    return [x for x in 结果 if x is not None]


def 生成小说文件(书籍编号: str, 书名: str, 作者: str, 状态: str, 字数: str, 章节结果: list[dict[str, str]]) -> tuple[str, bytes]:
    文件名 = f"[{状态}]书名：{清理文件名(书名)} 作者：{清理文件名(作者)}.txt"
    行 = [文件声明, "", f"名称：{书名}", f"作者：{作者}", f"状态：{状态}", f"字数：{字数}", f"书籍ID：{书籍编号}", f"章节数：{len(章节结果)}", ""]
    for 章 in 章节结果:
        if not 章.get("content"):
            continue
        行.extend([章.get("title") or "章节", "", 章["content"], ""])
    return 文件名, "\n".join(行).encode("utf-8")


async def 准备发送文本文件(event: Any, 文件名: str, 文件内容: bytes, 配置: Any = None, *, 书名: Any = "", 作者: Any = "") -> dict[str, Any]:
    缓存路径 = 写入缓存(文件名, 文件内容)
    if UC网盘 is None:
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "UC网盘模块未加载"}
    try:
        UC结果 = await UC网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not UC结果.get("success"):
            删除缓存(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(UC结果.get("error") or "UC网盘未启用")}
        完成结果 = await UC网盘.发送小说下载完成链接(event, 书名, 作者, str(UC结果.get("share_url") or ""))
        if 完成结果:
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        return {"sent": False, "fallback_text": "", "source_cache_path": 缓存路径, "error": "完成消息发送失败"}
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
    return 路径


def 删除缓存(缓存路径: Any) -> None:
    try:
        if 缓存路径:
            Path(缓存路径).unlink(missing_ok=True)
    except Exception:
        pass


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
    if "字" in 文本:
        return 文本
    if 文本.isdigit():
        n = int(文本)
        return f"{round(n/10000, 1)}万字" if n >= 10000 else f"{n}字"
    return 文本


def 清理文件名(文件名: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", str(文件名 or "")).strip() or "未知"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    try:
        数据 = await asyncio.to_thread(search_books, 关键词, 1, max(需要数量, 20))
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
