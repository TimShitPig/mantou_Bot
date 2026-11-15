"""西瓜免费小说 1.0.9.264 App 协议与共享会话异步下载。"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import hmac
import html
import json
import re
import secrets
import struct
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp
from Crypto.Cipher import AES, ARC4
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Util.Padding import pad, unpad
from yarl import URL

try:
    from astrbot.api import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)
try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None
from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

西瓜基础地址 = "https://xgmf.zuanqianyi.com"
西瓜重试次数 = 3
西瓜正文请求间隔 = 0.5
西瓜响应大小上限 = 4 * 1024 * 1024
西瓜文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
_AES密钥 = b"dzkjgfyxgshylgzm"
_AES向量 = b"apiupdownedcrypt"
# 以下是该 App 公开客户端中的协议常量，不含设备、游客或登录凭据。
_签名证书摘要 = '8cfaaedef7a7e24a716732ff5428958f'
_HMAC密钥 = b'wj3imab73kwceuf51lf01ORHe2cmo8X0YrZwF4p2uv3WEfmqxrT2oIBwRFRNErXW20UKal15ZTDdxPKU43puZFqcuXkvrQmadhp1wn6YPEDO4WRgInp8NNNQo4uNsWF1CELOzx7yPOS4pQbhTRWB4qRm0a4ENIegN0SH7K2STbsyaCuWh7m7s3rTpb5dK3CcDdsT35vo0xNbPZI2dJmKoIeKk9p3YhBLNWp9WoZqn9Qihpvn4nvgJzVSacgy2MTo'
_RSA私钥编码 = 'MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCKeaOFPXGp7N80uoPzQ8Ncz9fyPM8fvKj52szC4bSFWuS66ZZdo/vHFj4zLahQ2slL/begQfGSC4elaaX1wpFgEbyucYyulDOcHz0O5vvQDtySpnEu4b3AX2JfhQKtEJdK1pwDgzV+uLi0T2wBua7NADyiVL9J1KiVrywDKN+pclgVy2+sqK1wKWWKMha2HS/NlqfmNyxCdvnTuE6D20lIsPUmrkE2ZwkrlqivHTI4gWh6ONqjtPSd76lhgBV2svO9D7aMRz96BcV4XVqYdBXzbArOmd/rfXFWty6spGqqCBcHX79QUwarNVWrK7cprPZMatx3Y4N5pIait/F9c3jBAgMBAAECggEBAIfJmdDJHNF9Zq8lCskcNNGpOl/ew1iivqwro0ii3Us7gznKXtm6OOXT6PB0oC2RLX1n8Y2jvIfy6HQK8mPZBIdJPVVuIX778tPwSgZ3+IvgVukzb5+CW3jtz+BM5P/iWglYAyrqmiWGbBDcJNRYSZHa3ppsMhvq/dmyKZ17kj9sVRaJXauejkbhiIYKpOFXdYnPGQEU1sMjYNfSzo7h3OtfunFuPuQ+TCTHUetkJHy2cMy3bYsl/diRmvM+dqOJit+uFDVAxxg/j4LDu1q4yHhQofJ8/kpQNRYDOT1xi/vKPf+XoLwHns9fw/Azv1JCg76kc0uMIA5EzXyCIME0VHUCgYEA8cwQk/heAb8OiUgSc1YRE7ztGFYMBZ838LVUboIX38h4EeCBlsrlNhQoXEbuXh+x1kVKElURwLA8BJoXJMyQfAvi8QWkfTPWGm0b7V0KMdCWW9oM00nU5iVyFWkk2mAn+/j8uvVqlUVEDtWFgQZ/QefPS25jzuDfyuZ1fe4Yp2sCgYEAkpvoZ6ECt46Tn2t+4EuE2aSegd8CvzGwGHZeBIt6utfWO6bLr5vHS529qb3dKL41019P9oiRR/SSTLZSsVOsAytv1JMEPeoDY3Fxh/GULODkLq2NnapskQP11XlDt7xjazeJsxS8s2KP6yeA63dxOZ3iv4C0nCgIJ7gSCe+dp4MCgYBsbhNdF7qoU9Ij8+L6P7VGwakdCbE4cC74zYgASmyEWPSnJ6NVSMVC3AVBZDmOke4A5W+TCvz8CMvRUHxiby23wujRJrOdxboUfatRZTCmKCDVLdIkie5kCpS/TzhMiWRE1WIYQOe76qTbdhr5Qj2dA2PtMqKlaihRZ8l2YGhD4wKBgQCHJ8WzqyJ3F7CN2iqIGfaqMfGSZoYAvozJsG1yISeOkiXErjq+dIzg79WGYys8QUYby5VLAJF2VUh+AeLv6OP9tBCPVs0lStO+3Dk+iv3/9X9GbObN/+vAMHd0Siucecbpc7S07Bwd/3IP5kYaTO2LoTsFMmDOSLVj8HRoxoZ/gwKBgQCXjMPO9bnv03JYQ3EzJbM1UuokRu0iXRaZ3BzRj3jHBKELrsKBDXNdaJLUJyqDQJE18lJJRQC+JciNA5kFuzdLjwfu4GHIHFXQSBuNdz8BKXPltxjBObhr9ycNeLXWIQnZo0iGQiHc/+6aC88cw4gGZtuW+gWRa7QxTtgTNWrbgw=='
_RSA私钥 = RSA.import_key(base64.b64decode(_RSA私钥编码))
_固定查询 = "appId=100398183&country=CN&lang=zh_CN&ver=10009264&appVer=1.0.9.264&timestamp="
_西瓜指令正则 = re.compile(r"^西瓜免费小说(?:下载)?[\s:：]+([0-9]{5,20})\s*$")

# UTDID 的密钥解码及校验布局与原 App 注册实现一致，密码运算复用 PyCryptodome。
_UTDID密钥 = ARC4.new(
    b"QrMgt8GGYI6T52ZY5AnhtxkLzb8egpFn3j5JELI8H6wtACbUnZ5cc3aYTsTRbmk"
    b"AkRJeYbtx92LPBWm7nBO9UIl7y5i5MQNmUZNf5QENurR5tGyo7yJ2G0MBjWvy6i"
    b"AtlAbacKP0SwOUeUWx5dsBdyhxa7Id1APtybSdDgicBDuNjI0mlZFUzZSS9dmN8l"
    b"BD0WTVOMz0pRZbR3cysomRXOO1ghqjJdTcyDIxzpNAEszN8RMGjrzyU7Hjbmwi6YNK"
).decrypt(bytes(value & 255 for value in (
    69, 114, 116, -33, 125, -54, -31, 86, -11, 11, -78, -96, -17, -99,
    64, 23, -95, -126, -82, -64, 113, 116, -16, -103, 49, -30, 9, -39,
    33, -80, -68, -78, -117, 53, 30, -122, 64, -104, 74, -49, 106, 85,
    -38, -93,
)))


def _UTDID哈希(value: str) -> int:
    raw = value.encode("utf-16-be", "surrogatepass")
    result = 0
    for offset in range(0, len(raw), 2):
        result = (31 * result + int.from_bytes(raw[offset:offset + 2], "big")) & 0xFFFFFFFF
    return result


def _UTDID校验(prefix: bytes) -> bytes:
    digest = hmac.new(_UTDID密钥, prefix, hashlib.sha1).digest()
    return struct.pack(">I", _UTDID哈希(base64.b64encode(digest).decode("ascii")))


def _生成UTDID(android_id: str) -> str:
    prefix = (struct.pack(">II", int(time.time()) & 0xFFFFFFFF, secrets.randbits(32))
              + b"\x03\x00" + struct.pack(">I", _UTDID哈希(android_id)))
    return base64.b64encode(prefix + _UTDID校验(prefix)).decode("ascii")


def _有效UTDID(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 24:
        return False
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError:
        return False
    return (len(raw) == 18 and raw[8:10] == b"\x03\x00"
            and hmac.compare_digest(raw[14:], _UTDID校验(raw[:14])))


def _新建设备参数() -> dict[str, str]:
    android_id = secrets.token_hex(8)
    return {
        "utdid": _生成UTDID(android_id), "oaid": str(uuid.uuid4()),
        "sex": "0", "channelCode": "wb1001925", "domain": "2", "p": "35",
        "brand": "Xiaomi", "model": "2201123C", "ver": "10009264",
        "appVer": "1.0.9.264", "osVer": "android35", "androidId": android_id,
        "rtype": "2", "deviceType": "-1", "pname": "com.dzmf.zmfxsdq",
    }


# 已注册设备只保留在内存并跨热重载复用，不读取或生成 profile/设备文件。
if "_游客状态" not in globals():
    _游客状态: dict[str, Any] = {
        "param": _新建设备参数(), "loop": None, "lock": None, "cpu": None,
        "failed_until": 0.0, "invalid_param": None, "device_generation": 0,
    }


class _西瓜请求错误(RuntimeError):
    def __init__(self, category: str, *, http_status: int | None = None, code: int | None = None):
        super().__init__(category)
        self.category = category
        self.http_status = http_status
        self.code = code


def _整数(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    return None


def _书号(value: Any) -> str:
    text = str(value or "") if not isinstance(value, bool) else ""
    return text if re.fullmatch(r"[0-9]{5,20}", text) else ""


def _文本(value: Any) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", html.unescape(
        re.sub(r"<[^>]+>", "", str(value or ""))
    )).strip()


def _状态(value: Any) -> str:
    return {0: "连载", 1: "完结"}.get(_整数(value), "未知")


def _JSON(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _加密(value: str) -> str:
    return AES.new(_AES密钥, AES.MODE_CBC, _AES向量).encrypt(pad(value.encode("utf-8"), 16)).hex()


def _解密(value: bytes) -> dict[str, Any]:
    try:
        cipher = bytes.fromhex(value.decode("ascii").strip())
        plain = unpad(AES.new(_AES密钥, AES.MODE_CBC, _AES向量).decrypt(cipher), 16)
        result = json.loads(plain.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("invalid_root")
        return result
    except (ValueError, UnicodeError) as exc:
        raise _西瓜请求错误("invalid_response", http_status=200) from exc


def _初始化同步器() -> None:
    loop = asyncio.get_running_loop()
    if _游客状态.get("loop") is not loop:
        _游客状态.update(loop=loop, lock=asyncio.Lock(), cpu=asyncio.Semaphore(4), chapter_lock=asyncio.Lock())
    elif "chapter_lock" not in _游客状态:
        _游客状态["chapter_lock"] = asyncio.Lock()
    _游客状态.setdefault("chapter_next_at", 0.0)
    _游客状态.setdefault("invalid_param", None)
    _游客状态.setdefault("device_generation", 0)
    # 旧版拒绝冷却只标记旧设备失效，新版首次使用立即注册替换。
    if _游客状态.pop("chapter_restricted_until", 0.0) > time.monotonic():
        _游客状态["invalid_param"] = _游客状态["param"]


def _同步签名(value: str, sign_type: int) -> str:
    raw = (value + _签名证书摘要).encode("utf-8")
    if sign_type == 1:
        signature = hmac.new(_HMAC密钥, raw, hashlib.sha256).digest()
    elif sign_type == 2:
        signature = pkcs1_15.new(_RSA私钥).sign(SHA256.new(raw))
    else:
        raise _西瓜请求错误("invalid_signature_type")
    return base64.b64encode(signature).decode("ascii")


async def _签名(value: str, sign_type: int) -> str:
    if sign_type == 1:
        return _同步签名(value, sign_type)
    _初始化同步器()
    async with _游客状态["cpu"]:
        return await asyncio.to_thread(_同步签名, value, sign_type)


def 创建西瓜HTTP会话(concurrency: int = 500) -> aiohttp.ClientSession:
    # 正文最多 500 路异步并发，连接池使用相同上限。
    session = aiohttp.ClientSession(
        headers={"User-Agent": "okhttp/4.9.2", "Accept": "application/json"},
        timeout=aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20),
        connector=aiohttp.TCPConnector(limit=max(0, int(concurrency)),
                                       limit_per_host=max(0, int(concurrency)), ttl_dns_cache=300),
        cookie_jar=aiohttp.DummyCookieJar(), trust_env=True,
    )
    if hasattr(session, "_retry_connection"):
        session._retry_connection = False
    return session


async def _读取(response: aiohttp.ClientResponse) -> bytes:
    if response.status != 200:
        raise _西瓜请求错误("rate_limited" if response.status == 429 else "http_error",
                           http_status=response.status)
    raw = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        if len(raw) + len(chunk) > 西瓜响应大小上限:
            raise _西瓜请求错误("response_too_large", http_status=200)
        raw.extend(chunk)
    return bytes(raw)


async def _请求(session: aiohttp.ClientSession, call_no: str, body: dict[str, Any],
              sign_type: int = 1, *, deadline: float | None = None) -> dict[str, Any]:
    if call_no not in {"1141", "1110", "111", "1153"}:
        raise _西瓜请求错误("invalid_endpoint")
    _初始化同步器()
    if call_no == "1153":
        # 同一设备的阅读请求仍共享串行节奏，CDN 章节工作协程不受影响。
        async with _游客状态["chapter_lock"]:
            return await _设备请求(session, call_no, body, sign_type, deadline=deadline)
    return await _设备请求(session, call_no, body, sign_type, deadline=deadline)


async def _设备请求(session: aiohttp.ClientSession, call_no: str, body: dict[str, Any],
                 sign_type: int, *, deadline: float | None) -> dict[str, Any]:
    params = await _确保游客(session, deadline=deadline)
    try:
        return await _执行请求(session, call_no, body, sign_type, params=params, deadline=deadline)
    except _西瓜请求错误 as exc:
        if exc.category != "access_restricted" or exc.code != 8:
            raise
    # 明确的业务拒绝才更换设备；迟到的旧设备拒绝复用已完成的新注册。
    params = await _确保游客(session, rejected=params, deadline=deadline)
    try:
        return await _执行请求(session, call_no, body, sign_type, params=params, deadline=deadline)
    except _西瓜请求错误 as exc:
        if exc.category == "access_restricted" and exc.code == 8:
            async with _游客状态["lock"]:
                if _游客状态["param"] is params:
                    _游客状态["invalid_param"] = params
                    _游客状态["failed_until"] = time.monotonic() + 60
        # 每次业务请求最多换设备重试一次，持续拒绝不循环注册。
        raise


async def _执行请求(session: aiohttp.ClientSession, call_no: str, body: dict[str, Any],
                sign_type: int, *, params: dict[str, Any], deadline: float | None = None) -> dict[str, Any]:
    last: _西瓜请求错误 | None = None
    # f0 会初始化游客，断流后结果不明时不自动重复提交。
    attempts = 1 if call_no == "1121" else 西瓜重试次数
    for attempt in range(attempts):
        if call_no == "1153":
            delay = max(0.0, _游客状态["chapter_next_at"] - time.monotonic())
            if deadline is not None and time.monotonic() + delay >= deadline:
                raise last or _西瓜请求错误("timeout")
            if delay:
                await asyncio.sleep(delay)
        options: dict[str, Any] = {}
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise last or _西瓜请求错误("timeout")
            options["timeout"] = aiohttp.ClientTimeout(total=min(4, remaining), sock_connect=min(4, remaining))
        query = _固定查询 + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        plaintext = _JSON(body)
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "param": _加密(_JSON(params)),
            "signType": str(sign_type), "sign": await _签名(query + plaintext, sign_type),
        }
        try:
            if call_no == "1153":
                _游客状态["chapter_next_at"] = time.monotonic() + 西瓜正文请求间隔
            async with session.post(URL(西瓜基础地址 + "/glory/free/" + call_no + "?" + query, encoded=True),
                                    data=("start_" + _加密(plaintext)).encode("ascii"), headers=headers,
                                    allow_redirects=False, **options) as response:
                result = _解密(await _读取(response))
            code = _整数(result.get("retCode"))
            if code is None:
                raise _西瓜请求错误("invalid_response", http_status=200)
            if code != 0:
                if code == 8:
                    raise _西瓜请求错误("access_restricted", http_status=200, code=code)
                raise _西瓜请求错误("business_error", http_status=200, code=code)
            return result
        except _西瓜请求错误 as exc:
            if exc.category != "http_error" or exc.http_status not in {408, 500, 502, 503, 504}:
                raise
            last = exc
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            last = _西瓜请求错误("timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error")
        if attempt + 1 < attempts:
            delay = 0.2 * (attempt + 1)
            if deadline is not None and time.monotonic() + delay >= deadline:
                raise last
            await asyncio.sleep(delay)
    raise last or _西瓜请求错误("network_error")


async def _确保游客(session: aiohttp.ClientSession, *, rejected: dict[str, Any] | None = None,
                deadline: float | None = None) -> dict[str, Any]:
    _初始化同步器()
    lock = _游客状态["lock"]
    if deadline is None:
        await lock.acquire()
    else:
        try:
            await asyncio.wait_for(lock.acquire(), max(0.0, deadline - time.monotonic()))
        except asyncio.TimeoutError:
            raise _西瓜请求错误("timeout") from None
    try:
        current = _游客状态["param"]
        if rejected is current:
            _游客状态["invalid_param"] = current
        if (_书号(current.get("uid")) and _有效UTDID(current.get("utdid"))
                and _游客状态["invalid_param"] is not current):
            return current
        if time.monotonic() < _游客状态["failed_until"]:
            if _游客状态["invalid_param"] is current:
                raise _西瓜请求错误("access_restricted", code=8)
            raise _西瓜请求错误("guest_cooldown")
        params = _新建设备参数()
        body = {"f": "f0", "rCode": 10009264, "domain": 2,
                "brand": params["brand"], "model": params["model"],
                "attributionId": "|" + params["oaid"], "utdid": params["utdid"],
                "channelCode": params["channelCode"]}
        try:
            # 候选设备与 f0 请求体一致；1121 结果不明时不自动重复注册。
            response = await _执行请求(session, "1121", body, 2, params=params, deadline=deadline)
            data = response.get("data")
            info = data.get("f0") if isinstance(data, dict) else None
            uid = _书号(info.get("userId")) if isinstance(info, dict) else ""
            if not uid or uid == _书号(current.get("uid")):
                raise _西瓜请求错误("invalid_guest")
            params["uid"] = uid
            if isinstance(info.get("channelCode"), str) and info["channelCode"]:
                params["channelCode"] = info["channelCode"]
        except BaseException:
            _游客状态["failed_until"] = time.monotonic() + 60
            raise
        # 注册成功后原子发布；旧请求始终使用自己的参数快照。
        _游客状态.update(param=params, invalid_param=None, failed_until=0.0,
                     device_generation=_游客状态["device_generation"] + 1)
        logger.info("西瓜免费小说设备注册完成：stage=device_register, reason=%s, generation=%s",
                    "access_restricted" if rejected is not None else "initialize",
                    _游客状态["device_generation"])
        return params
    finally:
        lock.release()


def 构造西瓜链接(book_id: Any) -> str:
    # 仅供找书选中及在途任务恢复，不作为聊天书号下载指令。
    return "西瓜免费小说 " + _书号(book_id)


def 解析西瓜书籍编号(source: Any) -> str:
    if not isinstance(source, str):
        return ""
    match = _西瓜指令正则.fullmatch(source.strip())
    return match.group(1) if match else ""


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    maximum = max(1, min(30, int(需要数量 or 20)))
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    deadline = time.monotonic() + 10
    async with 创建西瓜HTTP会话(4) as session:
        for page in range(1, (maximum + 14) // 15 + 1):
            response = await _请求(session, "1141", {"keyword": keyword, "index": page,
                                   "size": 15, "searchType": "4"}, deadline=deadline)
            data = response.get("data")
            if not isinstance(data, dict):
                raise _西瓜请求错误("invalid_search")
            total = _整数(data.get("totalCount"))
            rows = data.get("searchList")
            # App 将缺失/null 列表作为空页；保留前页结果，不把终页当作请求失败。
            if rows is None:
                rows = []
            if not isinstance(rows, list):
                raise _西瓜请求错误("invalid_search")
            valid_rows = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                book_id = _书号(row.get("bookId"))
                title = _文本(row.get("bookName"))
                if not book_id or not title:
                    continue
                valid_rows += 1
                if book_id in seen:
                    continue
                seen.add(book_id)
                results.append({"book_id": book_id, "title": title,
                                "author": _文本(row.get("author")) or "未知",
                                "url": 构造西瓜链接(book_id), "intro": _文本(row.get("introduction")),
                                "status": _状态(row.get("status")), "word_count": row.get("totalWordSize") or 0,
                                "_search_status": {"status": row.get("status")}, "score": 0, "heat": 0})
            # 有结果数却无首屏列表，或整页全部无效，仍是协议异常而非正常没书。
            if (rows and not valid_rows) or (not rows and not results and total is not None and total > 0):
                raise _西瓜请求错误("invalid_search")
            if len(results) >= maximum or len(rows) < 15 or (total is not None and len(seen) >= total):
                break
    return results[:maximum]


async def 获取西瓜详情(session: aiohttp.ClientSession, book_id: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    response = await _请求(session, "1110", {"bookId": book_id})
    data = response.get("data")
    book = data.get("book") if isinstance(data, dict) else None
    if not isinstance(book, dict) or _书号(book.get("bookId")) != book_id or not _文本(book.get("bookName")):
        raise _西瓜请求错误("invalid_detail")
    expected = _整数(book.get("totalChapterNum"))
    if expected is None or expected <= 0:
        raise _西瓜请求错误("invalid_catalog_count")
    chapters: list[dict[str, str]] = []
    seen: set[str] = set()
    anchor = ""
    for page in range(10000):
        response = await _请求(session, "111", {"bookId": book_id, "chapterId": anchor,
                               "chapterOffset": "50" if page == 0 else "51", "chapterEndId": "",
                               "needBlockList": "1" if page == 0 else ""})
        node = response.get("data")
        if not isinstance(node, dict) or ("bookId" in node and _书号(node["bookId"]) != book_id):
            raise _西瓜请求错误("invalid_catalog")
        ids, names = node.get("chapterIdList"), node.get("chapterNameList")
        if not isinstance(ids, list) or not isinstance(names, list) or len(ids) != len(names):
            raise _西瓜请求错误("invalid_catalog")
        added = 0
        for cid, name in zip(ids, names):
            chapter_id, title = _书号(cid), _文本(name)
            if not chapter_id or not title:
                raise _西瓜请求错误("invalid_catalog")
            if chapter_id not in seen:
                seen.add(chapter_id)
                chapters.append({"id": chapter_id, "title": title})
                added += 1
        if len(chapters) > expected:
            raise _西瓜请求错误("incomplete_catalog")
        if not added:
            break
        anchor = chapters[-1]["id"]
    if len(chapters) != expected:
        raise _西瓜请求错误("incomplete_catalog")
    return {"title": _文本(book["bookName"]), "author": _文本(book.get("author")) or "未知",
            "intro": _文本(book.get("introduction")), "status": _状态(book.get("status")),
            "word_count": _文本(book.get("totalWordSize")) or "未知"}, chapters


async def _正文元数据(session: aiohttp.ClientSession, book_id: str, batch: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    ids = [chapter["id"] for chapter in batch]
    response = await _请求(session, "1153", {"bookId": book_id, "chapterIds": ids,
                           "autoPay": "1", "keepShowAd": 1}, 2)
    data = response.get("data")
    rows = data.get("chapterInfo") if isinstance(data, dict) else None
    if not isinstance(rows, list) or ("bookId" in data and _书号(data["bookId"]) != book_id):
        raise _西瓜请求错误("invalid_chapter")
    received: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = _书号(row.get("chapterId")) if isinstance(row, dict) else ""
        if cid not in ids or cid in received or ("bookId" in row and _书号(row["bookId"]) != book_id):
            raise _西瓜请求错误("invalid_chapter")
        if _整数(row.get("chapterStatus")) != 1:
            raise _西瓜请求错误("chapter_unavailable")
        received[cid] = row
    if set(received) != set(ids):
        raise _西瓜请求错误("missing_chapter")
    return received


def _正文地址(value: Any) -> URL:
    try:
        if not isinstance(value, str):
            raise ValueError("invalid_url")
        url = URL(value, encoded=True)
        if url.scheme not in {"https", "http"} or not url.host or url.user or url.password:
            raise ValueError("invalid_url")
        return url
    except (ValueError, TypeError):
        raise _西瓜请求错误("invalid_content_url") from None


async def _读取正文(session: aiohttp.ClientSession, url: URL) -> bytes:
    for redirects in range(5):
        async with session.get(url, allow_redirects=False) as response:
            if response.status not in {301, 302, 303, 307, 308}:
                return await _读取(response)
            location = response.headers.get("Location")
            if redirects == 4 or not location:
                raise _西瓜请求错误("invalid_content_redirect", http_status=response.status)
            # 仅跟随 App 返回的正文地址；共享会话不保存 Cookie，GET 不带 param/sign。
            url = _正文地址(str(url.join(URL(location, encoded=True))))
    raise _西瓜请求错误("invalid_content_redirect")


async def _下载正文(session: aiohttp.ClientSession, chapter: dict[str, Any]) -> str:
    urls = chapter.get("cdnUrls")
    if not isinstance(urls, list) or not urls:
        raise _西瓜请求错误("missing_content_url")
    last: _西瓜请求错误 | None = None
    for value in urls:
        url = _正文地址(value)
        for attempt in range(西瓜重试次数):
            try:
                raw = await _读取正文(session, url)
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeError as exc:
                    raise _西瓜请求错误("invalid_content") from exc
                if not text.strip() or text.lstrip().lower().startswith(("<!doctype html", "<html")):
                    raise _西瓜请求错误("empty_content" if not text.strip() else "invalid_content")
                return text
            except _西瓜请求错误 as exc:
                if exc.http_status in {401, 403, 429}:
                    raise
                last = exc
                if exc.category != "http_error" or exc.http_status not in {408, 500, 502, 503, 504}:
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                last = _西瓜请求错误("timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error")
            if attempt + 1 < 西瓜重试次数:
                await asyncio.sleep(0.2 * (attempt + 1))
    raise last or _西瓜请求错误("network_error")


async def 下载西瓜正文(session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]) -> list[str]:
    if not chapters:
        raise _西瓜请求错误("empty_catalog")
    # 一次提交完整目录，校验全部阅读状态后再并发下载正文。
    received = await _正文元数据(session, book_id, chapters)
    worker_count = min(500, len(chapters))
    queue: asyncio.Queue[tuple[int, dict[str, Any]] | None] = asyncio.Queue(maxsize=worker_count * 2)
    results = [""] * len(chapters)
    done = 0
    next_log = max(1, (len(chapters) + 3) // 4)
    logger.info("西瓜免费小说章节进度：书籍编号=%s, 进度=0/%s, 百分比=0%%, 并发数=%s, HTTP会话复用=开启",
                book_id, len(chapters), worker_count)

    async def produce() -> None:
        # 获取地址与逐章下载独立，最多使用 500 个正文工作协程。
        for index, chapter in enumerate(chapters):
            await queue.put((index, received[chapter["id"]]))
        for _ in range(worker_count):
            await queue.put(None)

    async def worker() -> None:
        nonlocal done, next_log
        while (item := await queue.get()) is not None:
            index, chapter = item
            results[index] = await _下载正文(session, chapter)
            done += 1
            if done >= next_log or done == len(chapters):
                logger.info("西瓜免费小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 并发数=%s, HTTP会话复用=开启",
                            book_id, done, len(chapters), int(done * 100 / len(chapters)), done, worker_count)
                next_log += max(1, (len(chapters) + 3) // 4)

    tasks = [asyncio.create_task(produce())] + [asyncio.create_task(worker()) for _ in range(worker_count)]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    if not all(results):
        raise _西瓜请求错误("incomplete_content")
    return results


def _文件名(value: Any) -> str:
    return re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "未知")).strip(" .")[:80] or "西瓜免费小说"


def 格式化西瓜下载提示(detail: dict[str, Any], count: int) -> str:
    return "\n".join([f"书名：{detail.get('title') or '未知'}", f"作者：{detail.get('author') or '未知'}",
                      f"状态：{detail.get('status') or '未知'}", f"章节：{count} 章",
                      f"字数：{detail.get('word_count') or '未知'}", "", "正在下载中请稍等....."])


def 生成西瓜文件(book_id: str, detail: dict[str, Any], chapters: list[dict[str, str]], contents: list[str]) -> tuple[str, bytes]:
    if len(chapters) != len(contents) or not contents or not all(contents):
        raise _西瓜请求错误("incomplete_content")
    title, author = str(detail.get("title") or "未知"), str(detail.get("author") or "未知")
    status = str(detail.get("status") or "未知")
    lines = [西瓜文件声明, "", f"名称：{title}", f"作者：{author}", f"状态：{status}",
             f"字数：{detail.get('word_count') or '未知'}", f"书籍ID：{book_id}", f"章节数：{len(chapters)}", ""]
    if detail.get("intro"):
        lines.extend(["简介：", str(detail["intro"]), ""])
    for chapter, content in zip(chapters, contents):
        lines.extend([chapter["title"], "", 去除章节正文重复标题(chapter["title"], content), ""])
    filename = f"[{status}]书名：{_文件名(title)} 作者：{_文件名(author)}.txt"
    text = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n")
    return filename, text.replace("\n", "\r\n").encode("utf-8")


def _写入缓存(filename: str, content: bytes) -> Path:
    directory = 文件缓存工具.小说缓存目录
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = directory / (Path(filename).name if index == 0 else f"{Path(filename).stem}_{index}.txt")
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            continue
        文件缓存工具.标记小说缓存正在使用(path)
        return path
    raise _西瓜请求错误("cache_name_conflict")


async def _发送(event: Any, filename: str, content: bytes, config: Any, detail: dict[str, Any]) -> dict[str, Any]:
    path = _写入缓存(filename, content)
    cancelled = False
    try:
        if 小说网盘 is None:
            return {"sent": False}
        uploaded = await 小说网盘.上传小说并获取分享链接(config, path, filename)
        if not uploaded.get("success"):
            return {"sent": False}
        return await 小说网盘.发送小说下载结果(event, detail["title"], detail["author"], uploaded)
    except asyncio.CancelledError:
        cancelled = True
        raise
    finally:
        if cancelled:
            # 统一网盘已登记任务输入；账号读取或发送期间重载仍需复用该 TXT。
            文件缓存工具.解除小说缓存占用(path)
        else:
            文件缓存工具.删除小说缓存文件(path)


async def 生成西瓜下载回复流(event: Any, source: str, config: Any = None) -> AsyncIterator[Any]:
    book_id = 解析西瓜书籍编号(source)
    if not book_id:
        yield "下载失败 请重试"
        return
    stage = "metadata"
    try:
        async with 创建西瓜HTTP会话() as session:
            detail, chapters = await 获取西瓜详情(session, book_id)
            logger.info("西瓜免费小说开始下载：书籍编号=%s, 书名=%s, 作者=%s, 章节数=%s",
                        book_id, detail["title"], detail["author"], len(chapters))
            yield 格式化西瓜下载提示(detail, len(chapters))
            stage = "chapters"
            contents = await 下载西瓜正文(session, book_id, chapters)
        filename, content = 生成西瓜文件(book_id, detail, chapters, contents)
        logger.info("西瓜免费小说章节下载完成：书籍编号=%s, 成功=%s, 总数=%s, 文件大小=%s",
                    book_id, len(contents), len(chapters), len(content))
        stage = "upload_send"
        result = await _发送(event, filename, content, config, detail)
        if result.get("sent"):
            return
        if result.get("fallback_text"):
            yield str(result["fallback_text"])
            return
        logger.warning("西瓜免费小说文件发送失败：stage=upload_send, book_id=%s, reason=upload_or_delivery_failed", book_id)
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning("西瓜免费小说处理失败：stage=%s, book_id=%s, error_type=%s, category=%s, http_status=%s, code=%s",
                       stage, book_id, type(exc).__name__, getattr(exc, "category", "unknown"),
                       getattr(exc, "http_status", None), getattr(exc, "code", None))
        yield "文件发送失败，请稍后再试" if stage == "upload_send" else "下载失败 请重试"
