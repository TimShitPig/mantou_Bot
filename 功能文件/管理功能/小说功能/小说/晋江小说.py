"""晋江 Android App 协议、账号扫码与异步小说下载。

沿用 App 520 的章节签名、动态报文和字段解密；无账号使用游客且只选免费章。
登录身份仅用于确认已有读取权限，不调用购买接口。TXT 与发送仍复用统一缓存、网盘和机器人作用域。
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import html
import io
import json
import re
import time
import weakref
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception:
    百度网盘 = None

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

晋江详情地址 = "https://android.jjwxc.net/androidapi/novelbasicinfo"
晋江目录地址 = "https://android.jjwxc.net/androidapi/chapterList"
晋江正文地址 = "https://android.jjwxc.net/androidapi/chapterContent"
晋江搜索地址 = "https://android.jjwxc.net/androidapi/search"
晋江扫码创建地址 = "https://app.jjwxc.org/app.jjwxc/android/reading/Login/scanCodeLogin"
晋江扫码查询地址 = "https://app.jjwxc.org/app.jjwxc/android/reading/Login/checkJjreaderLogin"
晋江资料地址 = "https://app.jjwxc.org/userSettingAndroid/getSetting"
晋江App版本 = 520
晋江正文密钥 = b"KW8Dvm2N"
晋江正文向量 = b"1ae2c94b"
晋江响应字节上限 = 32 * 1024 * 1024
晋江请求最小间隔 = 0.5
晋江域名集合 = {"jjwxc.net", "jjwxc.com"}
晋江请求并发上限 = 2
晋江搜索数量上限 = 30
晋江请求重试次数 = 3
晋江进度日志最多条数 = 5
晋江小说缓存目录 = 文件缓存工具.小说缓存目录
晋江文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
)
晋江下载失败提示 = "下载失败 请重试"
晋江没有可下载章节提示 = "没有可下载章节"
晋江章节未发布提示 = "该书暂未发布章节"
晋江仅文案提示 = "该书目前仅公开文案，正文尚未发布"
晋江全文存稿状态文案 = "1058:作者大大全文存稿中，只开启了文案让大家先睹为快，还请继续关注哦~~~"
晋江文件发送失败提示 = "文件发送失败，请稍后再试"
晋江请求头 = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15; 2201123C) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Version/4.0 Chrome/130.0.0.0 Mobile Safari/537.36/"
        "JINJIANG-Android/520(2201123C;android 15;Scale/3.0)"
    ),
    "Accept": "application/json",
    "Referer": "https://android.jjwxc.net/?v=520",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}
晋江链接正则 = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_晋江会话节流: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


class 晋江请求错误(RuntimeError):
    """只携带固定分类及数字业务码，不保留上游正文或认证参数。"""

    def __init__(self, reason: str, *, code: Any = None, http_status: int | None = None):
        self.reason = reason
        self.code = _晋江数字码(code)
        self.http_status = http_status
        super().__init__(reason)


def _晋江数字码(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (str, int)) and re.fullmatch(r"[0-9]{1,6}", str(value)):
        return str(value)
    return None


def 加密晋江内容(text: str, key: bytes = 晋江正文密钥, iv: bytes = 晋江正文向量) -> str:
    if not isinstance(text, str):
        raise 晋江请求错误("invalid_plaintext")
    return base64.b64encode(DES.new(key, DES.MODE_CBC, iv).encrypt(pad(text.encode("utf-8"), 8))).decode("ascii")


def 解密晋江内容(text: str, key: bytes = 晋江正文密钥, iv: bytes = 晋江正文向量) -> str:
    try:
        if not isinstance(text, str):
            raise ValueError
        raw = base64.b64decode("".join(text.split()), validate=True)
        return unpad(DES.new(key, DES.MODE_CBC, iv).decrypt(raw), 8).decode("utf-8")
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise 晋江请求错误("decrypt_failed") from None


def 生成晋江章节签名(书籍编号: str, 章节编号: str, token: str = "", *, 时间戳: int | None = None) -> str:
    if not re.fullmatch(r"[0-9]{1,12}", str(书籍编号)) or int(书籍编号) <= 0:
        raise 晋江请求错误("invalid_book_id")
    if not re.fullmatch(r"[0-9]{1,12}", str(章节编号)) or int(章节编号) <= 0:
        raise 晋江请求错误("invalid_chapter_id")
    if not isinstance(token, str) or len(token) > 8192 or any(c == ":" or not 33 <= ord(c) <= 126 for c in token):
        raise 晋江请求错误("invalid_credentials")
    stamp = int(time.time() * 1000) if 时间戳 is None else int(时间戳)
    return 加密晋江内容(f"{stamp}:{token}:{int(书籍编号)}:{int(章节编号)}")


def 解码晋江响应(raw: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise 晋江请求错误("invalid_encoding") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        lower = {k.lower(): v for k, v in headers.items()}
        accesskey, keystring = lower.get("accesskey", ""), lower.get("keystring", "")
        text = text.strip()
        if not accesskey or not keystring or len(text) <= 12:
            raise 晋江请求错误("invalid_envelope") from None
        total = sum(map(ord, accesskey))
        start = total % len(keystring)
        fragment = keystring[start:start + total // 65]
        if ord(accesskey[-1]) & 1:
            encrypted, salt = text[:-12], text[-12:]
        else:
            salt, encrypted = text[:12], text[12:]
        key = hashlib.md5((fragment + salt).encode()).hexdigest()[:8].encode()
        iv = hashlib.md5(salt.encode()).hexdigest()[:8].encode()
        try:
            data = json.loads(解密晋江内容(encrypted, key, iv))
        except json.JSONDecodeError:
            raise 晋江请求错误("invalid_envelope_json") from None
    if not isinstance(data, dict):
        raise 晋江请求错误("invalid_response")
    return _解码晋江字段(data)


def _解码晋江字段(data: Any, 深度: int = 0) -> Any:
    if 深度 > 64:
        raise 晋江请求错误("response_too_deep")
    if isinstance(data, list):
        return [_解码晋江字段(item, 深度 + 1) for item in data]
    if not isinstance(data, dict):
        return data
    result = {key: _解码晋江字段(value, 深度 + 1) for key, value in data.items()}
    fields = data.get("encryptField") or []
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except json.JSONDecodeError:
            fields = [field.strip() for field in fields.split(",") if field.strip()]
    if not isinstance(fields, list) or any(not isinstance(field, str) for field in fields):
        raise 晋江请求错误("invalid_encrypt_fields")
    if fields and data.get("encryptType", "jj") != "jj":
        raise 晋江请求错误("unsupported_encryption")
    for field in fields:
        if field not in data or not isinstance(data[field], str):
            raise 晋江请求错误("missing_encrypt_field")
        result[field] = 解密晋江内容(data[field]) if data[field] else ""
    if fields:
        result["encryptField"] = []
    return result


class _晋江章节未发布(RuntimeError):
    """目录接口返回尚未发布章节或尚未通过审核的业务状态。"""

    def __init__(self, 业务码: str, *, 仅文案: bool = False) -> None:
        self.业务码 = 业务码
        self.仅文案 = 仅文案
        super().__init__("chapters_unpublished")


def 创建晋江HTTP会话(并发数: int = 晋江请求并发上限) -> aiohttp.ClientSession:
    """创建下载期间复用的异步连接池。"""
    并发数 = max(1, min(int(并发数 or 1), 晋江请求并发上限))
    connector = aiohttp.TCPConnector(
        limit=并发数,
        limit_per_host=并发数,
        ttl_dns_cache=300,
        keepalive_timeout=30,
    )
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    return aiohttp.ClientSession(
        headers=晋江请求头,
        timeout=timeout,
        connector=connector,
        cookie_jar=aiohttp.DummyCookieJar(),
    )


def _清理来源(值: Any) -> str:
    return (
        html.unescape(str(值 or ""))
        .replace("\\/", "/")
        .strip()
        .rstrip("\"'`，。；;]}>）)")
    )


def _文本候选(值: Any, 结果: list[str], 已见: set[int], 深度: int = 0) -> None:
    if 值 is None or 深度 > 8:
        return
    if isinstance(值, str):
        if 值.strip():
            结果.append(值)
        return
    if isinstance(值, Mapping):
        for 子值 in 值.values():
            _文本候选(子值, 结果, 已见, 深度 + 1)
        return
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            _文本候选(子值, 结果, 已见, 深度 + 1)
        return
    标识 = id(值)
    if 标识 in 已见:
        return
    已见.add(标识)
    for 字段 in (
        "message_str",
        "raw_message",
        "message",
        "message_obj",
        "text",
        "content",
        "data",
        "jump_url",
        "url",
    ):
        try:
            _文本候选(getattr(值, 字段, None), 结果, 已见, 深度 + 1)
        except Exception:
            continue


def _是晋江链接(链接: str) -> bool:
    try:
        主机 = (urlparse(链接).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return any(主机 == 域名 or 主机.endswith(f".{域名}") for 域名 in 晋江域名集合)


def 提取晋江来源(event: Any, 命令文本: Any = "") -> str | None:
    候选: list[str] = []
    _文本候选(命令文本, 候选, set())
    _文本候选(event, 候选, set())
    for 文本 in 候选:
        当前文本 = 文本
        for _ in range(2):
            当前文本 = unquote(当前文本)
        当前文本 = 当前文本.replace("\\/", "/")
        for 匹配 in 晋江链接正则.finditer(当前文本):
            链接 = _清理来源(匹配.group(0))
            if _是晋江链接(链接):
                return 链接
    return None


def 提取晋江书籍编号(来源: Any) -> str:
    文本 = _清理来源(来源)
    try:
        解析 = urlparse(文本)
    except ValueError:
        return ""
    if not _是晋江链接(文本):
        return ""
    查询 = parse_qs(解析.query, keep_blank_values=True)
    for 值 in 查询.get("novelid", []) + 查询.get("novelId", []):
        if re.fullmatch(r"\d{1,12}", str(值 or "")):
            return str(值)
    匹配 = re.search(
        r"/(?:book2|book|novel)/(\d{1,12})(?:[/?#]|$)", 解析.path, re.IGNORECASE
    )
    if 匹配:
        return 匹配.group(1)
    return ""


async def 请求晋江JSON(
    session: aiohttp.ClientSession,
    地址: str,
    参数: Mapping[str, Any] | Callable[[], Mapping[str, Any]],
    *,
    重试次数: int = 晋江请求重试次数,
    方法: str = "GET",
    原始正文: bytes | None = None,
    额外请求头: Mapping[str, str] | None = None,
    允许业务错误: bool = False,
    超时: float = 90,
) -> dict[str, Any]:
    # 固定官方端点，不把认证参数送往重定向地址或调用方提供的主机。
    if 地址 not in {
        晋江详情地址, 晋江目录地址, 晋江正文地址, 晋江搜索地址,
        晋江扫码创建地址, 晋江扫码查询地址, 晋江资料地址,
    } or 方法 not in {"GET", "POST"}:
        raise 晋江请求错误("invalid_endpoint")
    if 原始正文 is not None and (方法 != "POST" or not isinstance(原始正文, bytes)):
        raise 晋江请求错误("invalid_request_body")
    次数上限 = max(1, int(重试次数 or 1))
    节流 = _晋江会话节流.setdefault(session, {"lock": asyncio.Lock(), "last": 0.0})
    for 次数 in range(次数上限):
        try:
            async with 节流["lock"]:
                delay = 晋江请求最小间隔 - (time.monotonic() - 节流["last"])
                if delay > 0:
                    await asyncio.sleep(delay)
                节流["last"] = time.monotonic()
            当前参数 = dict(参数() if callable(参数) else 参数)
            当前参数.setdefault("versionCode", 晋江App版本)
            options: dict[str, Any] = {
                "allow_redirects": False,
                "headers": dict(额外请求头 or {}),
                "timeout": aiohttp.ClientTimeout(total=max(0.1, 超时), sock_connect=min(15, max(0.1, 超时))),
            }
            if 方法 == "GET":
                options["params"] = 当前参数
            else:
                options["data"] = 原始正文 if 原始正文 is not None else 当前参数
            async with session.request(方法, 地址, **options) as response:
                if response.status != 200:
                    retry_after = response.headers.get("Retry-After", "")
                    backoff = int(retry_after) if retry_after.isdigit() else 0
                    error = 晋江请求错误("http_error", http_status=response.status)
                    if response.status in {408, 429, 500, 502, 503, 504} and 次数 + 1 < 次数上限 and backoff <= 60:
                        await asyncio.sleep(max(2 ** 次数, backoff))
                        continue
                    raise error
                chunks = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    chunks.extend(chunk)
                    if len(chunks) > 晋江响应字节上限:
                        raise 晋江请求错误("response_too_large")
                data = 解码晋江响应(bytes(chunks), response.headers)
            if "code" in data and not 允许业务错误:
                code = _晋江数字码(data["code"])
                if code not in {"0", "200", "2000"}:
                    # 仅明确正文权限文案可跳过VIP，不把超时、签名失败等当作未订阅。
                    message = data.get("message") or data.get("msg")
                    denied = 地址 == 晋江正文地址 and code is not None and isinstance(message, str) and re.search(
                        r"未购买|尚未购买|请先购买|请购买|购买后(?:才能|可)|未订阅|尚未订阅|请先订阅|请订阅|订阅后(?:才能|可)|该章节为VIP章节", message,
                    ) is not None
                    raise 晋江请求错误("chapter_access_denied" if denied else "business_error", code=code)
            return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if 次数 + 1 >= 次数上限:
                reason = "timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error"
                raise 晋江请求错误(reason) from None
            await asyncio.sleep(2 ** 次数)
    raise 晋江请求错误("request_failed")


def _解析晋江登录身份(data: Any) -> dict[str, str] | None:
    if not isinstance(data, Mapping):
        return None
    if "code" in data and _晋江数字码(data["code"]) not in {"0", "200", "2000"}:
        return None
    nested = data.get("data")
    account = nested if isinstance(nested, Mapping) and nested.get("token") else data
    token = account.get("token")
    reader_id = account.get("readerId", account.get("readerid"))
    if (
        isinstance(reader_id, bool) or not isinstance(reader_id, (str, int))
        or not re.fullmatch(r"[0-9]{1,32}", str(reader_id)) or int(reader_id) <= 0
        or not isinstance(token, str) or not token or len(token) > 8192
        or any(c == ":" or not 33 <= ord(c) <= 126 for c in token)
        or account.get("error") or account.get("errors")
    ):
        return None
    return {"token": token, "readerId": str(int(reader_id))}


class 晋江扫码登录客户端:
    """每个后台登录会话独立持有票据；不启动网页、浏览器或本地监听。"""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._ticket: dict[str, str] | None = None
        self._expires = 0.0
        self._deadline = 0.0
        self._last_poll = 0.0
        self._lock = asyncio.Lock()
        self._closed = False

    async def start(self) -> dict[str, Any]:
        async with self._lock:
            if self._closed or self._session is not None:
                raise 晋江请求错误("qr_session_closed")
            self._session = 创建晋江HTTP会话(1)
            try:
                data = await 请求晋江JSON(
                    self._session, 晋江扫码创建地址, {}, 重试次数=1,
                    额外请求头={"source": "android", "versiontype": "reading", "versionCode": str(晋江App版本)},
                    允许业务错误=True, 超时=25,
                )
                ticket = data.get("data")
                if _晋江数字码(data.get("code")) != "200" or not isinstance(ticket, dict):
                    raise 晋江请求错误("qr_create_failed", code=data.get("code"))
                selected = {field: ticket.get(field) for field in ("jjreader_key", "device_key")}
                if any(not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9]{32}", value) is None for value in selected.values()):
                    raise 晋江请求错误("invalid_qr_ticket")
                self._ticket = selected
                url = "https://www.jjwxc.net?action=scanCode&jjreader_key=" + selected["jjreader_key"] + "&device_key=" + selected["device_key"]
                import qrcode
                image = qrcode.make(url)
                with io.BytesIO() as output:
                    image.save(output, format="PNG")
                    qr_image = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
                self._expires = time.time() + 60
                self._deadline = time.monotonic() + 60
                return {"status": "waiting", "qr_image": qr_image, "expires_in": 60, "expires_at": self._expires}
            except BaseException:
                await self._close_unlocked()
                raise

    async def poll(self) -> dict[str, Any]:
        async with self._lock:
            if self._closed or self._session is None or self._ticket is None:
                return {"status": "expired", "reason": "qr_session_closed", "code": None}
            if time.monotonic() >= self._deadline:
                await self._close_unlocked()
                return {"status": "expired", "reason": "qr_timeout", "code": None}
            if time.monotonic() - self._last_poll < 2:
                return {"status": "waiting", "reason": "waiting", "code": "100"}
            self._last_poll = time.monotonic()
            params = {"versionCode": str(晋江App版本), **self._ticket}
            try:
                data = await 请求晋江JSON(
                    self._session, 晋江扫码查询地址, params, 方法="POST", 重试次数=1,
                    原始正文=加密晋江内容(json.dumps(params, separators=(",", ":"))).encode("ascii"),
                    额外请求头={"source": "android", "versiontype": "reading", "versionCode": str(晋江App版本), "Content-Type": "text/plain;charset=utf-8"},
                    允许业务错误=True, 超时=min(25, max(0.1, self._deadline - time.monotonic())),
                )
            except 晋江请求错误 as exc:
                return {"status": "error", "reason": exc.reason, "code": exc.code}
            if time.monotonic() >= self._deadline:
                await self._close_unlocked()
                return {"status": "expired", "reason": "qr_timeout", "code": None}
            code = _晋江数字码(data.get("code"))
            if code == "100" and type(data.get("data")) is list and not data["data"]:
                return {"status": "waiting", "reason": "waiting", "code": code}
            credentials = _解析晋江登录身份(data) if code == "200" else None
            if credentials is not None:
                await self._close_unlocked()
                return {"status": "success", "reason": "authenticated", "code": code, "credentials": credentials}
            await self._close_unlocked()
            return {"status": "error", "reason": "unknown_login_state", "code": code}

    async def _close_unlocked(self) -> None:
        self._closed = True
        self._ticket = None
        session, self._session = self._session, None
        if session is not None:
            await session.close()

    async def close(self) -> None:
        async with self._lock:
            await self._close_unlocked()


async def 查询晋江账号资料(凭据: Mapping[str, Any]) -> dict[str, Any]:
    """只读原生设置接口；正文需要登录的 1004 不用于推断账号失效。"""
    identity = _解析晋江登录身份(凭据)
    if identity is None:
        return {"status": "unknown", "auth_status": "unknown", "reason": "invalid_credentials", "code": None}
    try:
        async with 创建晋江HTTP会话(1) as session:
            data = await 请求晋江JSON(
                session, 晋江资料地址, {"sign": 加密晋江内容(identity["token"])},
                重试次数=1, 允许业务错误=True, 超时=25,
            )
    except 晋江请求错误 as exc:
        return {"status": "unknown", "auth_status": "unknown", "reason": exc.reason, "code": exc.code}
    code = _晋江数字码(data.get("code"))
    if code == "1004":
        return {"status": "invalid", "auth_status": "invalid", "reason": "credential_invalid", "code": code, "readerId": identity["readerId"]}
    nested = data.get("data")
    if code in {"0", "200", "2000"} and isinstance(nested, dict) and not data.get("error") and not data.get("errors"):
        returned_id = nested.get("readerId", nested.get("readerid"))
        if not isinstance(returned_id, bool) and isinstance(returned_id, (str, int)) and re.fullmatch(r"[0-9]{1,32}", str(returned_id)) and int(returned_id) > 0:
            if str(int(returned_id)) != identity["readerId"]:
                return {"status": "unknown", "auth_status": "unknown", "reason": "identity_mismatch", "code": code}
            return {"status": "valid", "auth_status": "valid", "reason": "authenticated", "code": code, "readerId": identity["readerId"]}
    return {"status": "unknown", "auth_status": "unknown", "reason": "unverified_profile_response", "code": code, "readerId": identity["readerId"]}


def _安全整数(值: Any, 默认值: int = 0) -> int:
    try:
        return int(float(str(值).strip()))
    except (TypeError, ValueError):
        return 默认值


def 格式化晋江字数(值: Any, 格式化值: Any = "") -> str:
    原始 = str(格式化值 or 值 or "").strip()
    if not 原始:
        return "未知"
    if "万" in 原始:
        return 原始 if 原始.endswith("字") else f"{原始}字"
    数字文本 = re.sub(r"[\s,，]", "", str(值 or 原始))
    if 数字文本.isdigit():
        数字 = int(数字文本)
        return f"{数字}字" if 数字 < 10000 else f"{数字 / 10000:.1f}万字"
    return 原始 if 原始.endswith("字") else f"{原始}字"


def _清理正文(值: Any) -> str:
    文本 = html.unescape(str(值 or "")).replace("\r\n", "\n").replace("\r", "\n")
    文本 = re.sub(r"(?i)<br\s*/?>", "\n", 文本)
    文本 = re.sub(r"(?s)<[^>]+>", "", 文本)
    文本 = re.sub(r"\n{3,}", "\n\n", 文本)
    return 文本.strip()


async def 获取晋江详情(
    session: aiohttp.ClientSession,
    书籍编号: str,
) -> dict[str, Any]:
    data = await 请求晋江JSON(session, 晋江详情地址, {"novelId": 书籍编号})
    if str(data.get("novelId") or "").strip() != str(书籍编号):
        raise RuntimeError("晋江详情不可用")
    step = _安全整数(data.get("novelStep"), 1)
    章节数字段 = str(data.get("novelChapterCount", "")).strip()
    章节数 = int(章节数字段) if re.fullmatch(r"[0-9]{1,9}", 章节数字段) else -1
    return {
        "title": str(data.get("novelName") or f"晋江小说{书籍编号}").strip(),
        "author": str(data.get("authorName") or "未知").strip(),
        "status": "完结" if step == 2 else "连载",
        "word_count": 格式化晋江字数(
            data.get("novelSize"), data.get("novelsizeformat")
        ),
        "chapter_count": 章节数,
        "intro": _清理正文(data.get("novelIntro") or data.get("novelIntroShort")),
    }


def _章节可下载(章节: Mapping[str, Any], 凭据: Mapping[str, Any] | None = None) -> bool:
    """游客只选明确免费章；登录后的付费候选仍须由正文响应确认权限。"""
    if str(章节.get("islock", "0")).strip() != "0":
        return False
    # 不把限免文案、价格或小数截断结果当成游客读取权限。
    vip = _晋江数字码(章节.get("isvip"))
    if vip == "0":
        return True
    token = (凭据 or {}).get("token")
    return vip is not None and isinstance(token, str) and bool(token.strip())


async def 获取晋江目录(
    session: aiohttp.ClientSession,
    书籍编号: str,
    凭据: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    参数: dict[str, Any] = {"novelId": 书籍编号, "more": "0", "whole": "1"}
    if 凭据 and 凭据.get("token"):
        参数["token"] = 凭据["token"]
    data = await 请求晋江JSON(
        session,
        晋江目录地址,
        参数,
        允许业务错误=True,
    )
    业务码 = str(data.get("code") or "").strip()
    rows = data.get("chapterlist")
    if 业务码 in {"1058", "1068"}:
        # 详情中的章数可能包含作者存稿。只有目录明确返回已核实的
        # “全文存稿、仅开文案”状态且没有目录时，才能确认未公开正文。
        仅文案 = (
            业务码 == "1058"
            and data.get("message") == 晋江全文存稿状态文案
            and (rows is None or isinstance(rows, list) and not rows)
        )
        raise _晋江章节未发布(业务码, 仅文案=仅文案)
    if 业务码 and 业务码 not in {"0", "200", "2000"}:
        raise 晋江请求错误("business_error", code=data.get("code"))
    if not isinstance(rows, list):
        raise 晋江请求错误("invalid_catalog")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, Mapping):
            raise 晋江请求错误("invalid_catalog_entry")
        if _安全整数(item.get("chaptertype"), 0) == 1:
            continue  # App 卷名占位不是正文，章节编号可以不连续。
        chapter_id = str(item.get("chapterid") or item.get("chapterId") or "").strip()
        if not re.fullmatch(r"[0-9]{1,12}", chapter_id) or int(chapter_id) <= 0 or chapter_id in seen:
            raise 晋江请求错误("invalid_catalog_entry")
        seen.add(chapter_id)
        result.append(
            {
                "id": chapter_id,
                "title": str(
                    item.get("chaptername") or item.get("chapterName") or f"第{index}章"
                ).strip(),
                "isvip": item.get("isvip"),
                "islock": item.get("islock"),
                "point": item.get("point"),
                "pointfreevip": item.get("pointfreevip"),
                "available": _章节可下载(item, 凭据),
                "index": index,
            }
        )
    return result


async def 获取晋江正文(
    session: aiohttp.ClientSession,
    书籍编号: str,
    章节编号: str,
    凭据: Mapping[str, Any] | None = None,
) -> str:
    token = str((凭据 or {}).get("token") or "")
    data = await 请求晋江JSON(
        session,
        晋江正文地址,
        lambda: {"readState": "downloadtext", "sign": 生成晋江章节签名(书籍编号, 章节编号, token)},
    )
    if str(data.get("chapterId")) != str(章节编号):
        raise 晋江请求错误("chapter_identity_mismatch")
    content = _清理正文(data.get("content"))
    if not content:
        raise RuntimeError("晋江正文为空")
    return content


async def 下载晋江正文(
    session: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
    凭据: Mapping[str, Any] | None = None,
    配置: Any = None,
) -> list[dict[str, Any]]:
    # 正文入口再次按任务身份筛选，不信任调用方缓存的 available 标记。
    目录 = [chapter for chapter in 目录 if _章节可下载(chapter, 凭据)]
    total = len(目录)
    if not total:
        return []
    concurrency = min(晋江请求并发上限, total)
    request_sem = asyncio.Semaphore(concurrency)
    results: list[dict[str, Any] | None] = [None] * total
    progress_lock = asyncio.Lock()
    completed = 0
    success = 0
    skipped = 0
    errors: list[Exception] = []
    需要核实身份 = False
    # 总进度日志（含 0% 起始行）最多 5 条，短篇不再按章节逐条刷屏。
    进度日志间隔 = max(
        1,
        (total + 晋江进度日志最多条数 - 2)
        // max(1, 晋江进度日志最多条数 - 1),
    )
    next_log = 进度日志间隔
    logger.info(
        "晋江小说章节进度：书籍编号=%s, 进度=0/%s, 百分比=0%%, "
        "可下载章节并发数=%s, 会话复用=开启, 重试次数=%s",
        书籍编号,
        total,
        concurrency,
        晋江请求重试次数,
    )

    async def 下载一章(index: int, chapter: dict[str, Any]) -> None:
        nonlocal completed, success, skipped, next_log, 需要核实身份
        content = ""
        无权限 = False
        try:
            async with request_sem:
                content = await 获取晋江正文(session, 书籍编号, str(chapter["id"]), 凭据)
        except Exception as exc:
            需要核实身份 = 需要核实身份 or getattr(exc, "code", None) == "1004"
            # 目录可能尚未同步免费转付费；明确权限拒绝以正文响应为准。
            无权限 = getattr(exc, "reason", None) == "chapter_access_denied"
            if not 无权限:
                errors.append(exc)
            logger.debug(
                "晋江小说单章请求失败：书籍编号=%s, 序号=%s, 错误类型=%s, 原因=%s, 业务码=%s",
                书籍编号,
                index + 1,
                type(exc).__name__,
                getattr(exc, "reason", "chapter_failed"),
                getattr(exc, "code", None),
            )
        results[index] = {
            "id": str(chapter["id"]),
            "title": str(chapter.get("title") or f"第{index + 1}章"),
            "content": content,
            "success": bool(content),
            "skipped": 无权限,
        }
        async with progress_lock:
            completed += 1
            success += int(bool(content))
            skipped += int(无权限)
            if completed >= next_log or completed == total:
                percent = int(completed * 100 / max(1, total))
                logger.info(
                    "晋江小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 无权限跳过=%s, 失败=%s",
                    书籍编号,
                    completed,
                    total,
                    percent,
                    success,
                    skipped,
                    completed - success - skipped,
                )
                while next_log <= completed:
                    next_log += 进度日志间隔

    await asyncio.gather(
        *(下载一章(index, chapter) for index, chapter in enumerate(目录))
    )
    if 需要核实身份 and 凭据 and 配置 is not None:
        # 1004 在章节接口也表示无权限；必须另行调用只读身份接口再决定是否失效。
        from 功能文件.管理功能.小说功能.功能.晋江账号 import 合并晋江账号资料

        资料 = await 查询晋江账号资料(凭据)
        await asyncio.to_thread(合并晋江账号资料, 配置, dict(凭据), 资料)
    output = [item for item in results if item is not None and item.get("success")]
    if any(item is None for item in results) or errors:
        first = errors[0] if errors else None
        raise 晋江请求错误("chapter_incomplete", code=getattr(first, "code", None), http_status=getattr(first, "http_status", None))
    logger.info(
        "晋江小说章节下载完成：书籍编号=%s, 成功=%s, 无权限跳过=%s, 总数=%s",
        书籍编号,
        len(output),
        skipped,
        total,
    )
    return output


def _清理文件名(值: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(值 or "")).strip(" .")
    return 文本[:80] or "晋江小说"


def 生成晋江小说文件内容(
    书籍编号: str,
    详情: dict[str, Any],
    目录: list[dict[str, Any]],
    章节结果: list[dict[str, Any]],
) -> tuple[str, bytes]:
    状态 = str(详情.get("status") or "连载")
    书名 = str(详情.get("title") or f"晋江小说{书籍编号}")
    作者 = str(详情.get("author") or "未知")
    文件名 = f"[{状态}]书名：{_清理文件名(书名)} 作者：{_清理文件名(作者)}.txt"
    行列表 = [
        晋江文件声明,
        "",
        f"名称：{书名}",
        f"作者：{作者}",
        f"状态：{状态}",
        f"字数：{详情.get('word_count') or '未知'}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(目录)}",
        "",
    ]
    总目录章数 = _安全整数(详情.get("catalog_chapter_count"), len(目录))
    if 总目录章数 > len(目录):
        行列表.extend([
            f"目录共 {总目录章数} 章，本文件已取得 {len(目录)} 章正文。",
            f"另有 {总目录章数 - len(目录)} 章锁定或当前身份无读取权限，未收入本文件。",
            "",
        ])
    简介 = str(详情.get("intro") or "").strip()
    if 简介:
        行列表.extend(["简介：", 简介, ""])
    for chapter in 章节结果:
        title = str(chapter.get("title") or "章节")
        content = 去除章节正文重复标题(title, chapter.get("content"))
        if not str(content or "").strip():
            raise RuntimeError("晋江小说正文为空")
        行列表.extend([title, "", str(content).strip(), ""])
    text = "\n".join(行列表).replace("\r\n", "\n").replace("\r", "\n")
    return 文件名, text.replace("\n", "\r\n").encode("utf-8")


def 写入晋江下载缓存文件(文件名: str, 内容: bytes) -> Path:
    晋江小说缓存目录.mkdir(parents=True, exist_ok=True)
    path = 晋江小说缓存目录 / Path(_清理文件名(文件名)).name
    if path.exists():
        for index in range(1, 1000):
            candidate = 晋江小说缓存目录 / f"{path.stem}_{index}{path.suffix}"
            if not candidate.exists():
                path = candidate
                break
    path.write_bytes(内容)
    文件缓存工具.标记小说缓存正在使用(path)
    return path


def 删除晋江缓存文件(path: Any) -> None:
    if path:
        文件缓存工具.删除小说缓存文件(path)


async def 准备发送晋江文本文件(
    event: Any,
    文件名: str,
    内容: bytes,
    配置: Any,
    *,
    书名: str,
    作者: str,
) -> dict[str, Any]:
    path = 写入晋江下载缓存文件(文件名, 内容)
    if 小说网盘 is None:
        删除晋江缓存文件(path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    try:
        upload = await 小说网盘.上传小说并获取分享链接(配置, path, 文件名)
        if not upload.get("success"):
            删除晋江缓存文件(path)
            return {"sent": False, "fallback_text": "", "source_cache_path": None}
        sent = await 小说网盘.发送小说下载结果(
            event, 书名, 作者, upload
        )
        if sent.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": path}
        fallback = str(sent.get("fallback_text") or "")
        if fallback:
            return {"sent": False, "fallback_text": fallback, "source_cache_path": path}
        删除晋江缓存文件(path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    except Exception as exc:
        logger.warning("晋江小说文件发送失败：错误类型=%s", type(exc).__name__)
        删除晋江缓存文件(path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}


def 启动晋江百度后台上传并清理源文件(配置: Any, path: Any, 文件名: str) -> None:
    if not path:
        return

    async def 任务() -> None:
        备份完成 = True
        try:
            if 百度网盘 is not None:
                result = await 百度网盘.后台上传小说文件(配置, path, 文件名)
                if not isinstance(result, dict) or (
                    result.get("enabled")
                    and not (result.get("success") or result.get("skipped"))
                ):
                    备份完成 = False
                    logger.warning("晋江小说百度后台备份失败：文件=%s", 文件名)
        except Exception as exc:
            备份完成 = False
            logger.warning("晋江小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            if not 备份完成:
                文件缓存工具.更新上传任务(
                    path, "backup_pending", last_error="百度网盘后台备份未完成"
                )
            else:
                文件缓存工具.更新上传任务(path, "primary_done", last_error="")
            删除晋江缓存文件(path)

    try:
        asyncio.create_task(任务())
    except RuntimeError:
        删除晋江缓存文件(path)


async def 生成晋江下载回复流(
    event: Any,
    来源: str,
    配置: Any = None,
) -> AsyncIterator[Any]:
    书籍编号 = 提取晋江书籍编号(来源)
    if not 书籍编号:
        yield 晋江下载失败提示
        return
    stage = "详情目录"
    try:
        # 在任务开始时按当前机器人作用域取一次，后续切换账号不改变在途签名身份。
        from 功能文件.管理功能.小说功能.功能.晋江账号 import 读取晋江账号凭据
        from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID

        appid = str(获取当前机器人AppID(配置) or "")
        当前凭据 = await asyncio.to_thread(读取晋江账号凭据, 配置) if re.fullmatch(r"[0-9]+", appid) else None
        凭据 = dict(当前凭据) if isinstance(当前凭据, Mapping) else None
        async with 创建晋江HTTP会话() as session:
            详情, 全部目录 = await asyncio.gather(
                获取晋江详情(session, 书籍编号),
                获取晋江目录(session, 书籍编号, 凭据),
                return_exceptions=True,
            )
            # 等待两项都结束后再离开会话，先保留真实的详情错误或取消。
            if isinstance(详情, BaseException):
                stage = "详情"
                raise 详情
            stage = "目录"
            if isinstance(全部目录, _晋江章节未发布):
                if 全部目录.仅文案:
                    logger.info(
                        "晋江小说正文尚未公开：书籍编号=%s, 阶段=目录, 业务码=%s, "
                        "原因=manuscript_only, 详情章节=%s",
                        书籍编号,
                        全部目录.业务码,
                        详情.get("chapter_count"),
                    )
                    yield 晋江仅文案提示
                    return
                if 详情.get("chapter_count") != 0:
                    raise RuntimeError("晋江目录状态与详情不一致")
                logger.info(
                    "晋江小说暂未发布章节：书籍编号=%s, 阶段=目录, 业务码=%s",
                    书籍编号,
                    全部目录.业务码,
                )
                yield 晋江章节未发布提示
                return
            if isinstance(全部目录, BaseException):
                raise 全部目录
            可下载目录 = [item for item in 全部目录 if item.get("available")]
            if not 全部目录:
                raise RuntimeError("晋江目录为空")
            if not 可下载目录:
                logger.info(
                    "晋江小说没有可下载章节：书籍编号=%s, 总章节=%s",
                    书籍编号,
                    len(全部目录),
                )
                yield 晋江没有可下载章节提示
                return
            免费章节数 = sum(_晋江数字码(item.get("isvip")) == "0" for item in 可下载目录)
            logger.info(
                "晋江小说开始下载：书籍编号=%s, 书名=%s, 作者=%s, "
                "身份=%s, 总章节=%s, 免费章节=%s, 付费权限待确认=%s",
                书籍编号,
                详情.get("title"),
                详情.get("author"),
                "登录账号" if 凭据 else "游客",
                len(全部目录),
                免费章节数,
                len(可下载目录) - 免费章节数,
            )
            章节提示 = (
                f"章节：免费 {免费章节数} 章，付费章节仅下载已解锁部分"
                if 凭据 else f"章节：{免费章节数} 章（免费）"
            )
            yield "\n".join(
                [
                    f"书名：{详情.get('title') or '未知'}",
                    f"作者：{详情.get('author') or '未知'}",
                    f"状态：{详情.get('status') or '连载'}",
                    章节提示,
                    f"字数：{详情.get('word_count') or '未知'}",
                    "",
                    "正在下载中请稍等.....",
                ]
            )
            stage = "正文"
            章节结果 = await 下载晋江正文(session, 书籍编号, 可下载目录, 凭据, 配置)
            if not 章节结果:
                yield 晋江没有可下载章节提示
                return
            已读取 = {item["id"] for item in 章节结果}
            可下载目录 = [item for item in 可下载目录 if item["id"] in 已读取]
            详情["catalog_chapter_count"] = len(全部目录)
        文件名, 内容 = 生成晋江小说文件内容(书籍编号, 详情, 可下载目录, 章节结果)
        发送结果 = await 准备发送晋江文本文件(
            event,
            文件名,
            内容,
            配置,
            书名=str(详情.get("title") or "未知"),
            作者=str(详情.get("author") or "未知"),
        )
        path = 发送结果.get("source_cache_path")
        if 发送结果.get("sent"):
            启动晋江百度后台上传并清理源文件(配置, path, 文件名)
            return
        fallback = str(发送结果.get("fallback_text") or "")
        if fallback:
            try:
                yield fallback
            finally:
                启动晋江百度后台上传并清理源文件(配置, path, 文件名)
            return
        yield 晋江文件发送失败提示
    except Exception as exc:
        logger.warning(
            "晋江小说下载失败：书籍编号=%s, 阶段=%s, 错误类型=%s, 原因=%s, 业务码=%s, HTTP=%s",
            书籍编号,
            stage,
            type(exc).__name__,
            getattr(exc, "reason", "download_failed"),
            getattr(exc, "code", None),
            getattr(exc, "http_status", None),
        )
        yield 晋江下载失败提示


def 获取晋江小说回复流(
    event: Any,
    命令文本: str,
    配置: Any = None,
) -> AsyncIterator[Any] | None:
    来源 = 提取晋江来源(event, 命令文本)
    if 来源 is None:
        return None
    return 生成晋江下载回复流(event, 来源, 配置)


def 解析晋江搜索结果(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: Any = data.get("items")
    if not isinstance(rows, list):
        nested = data.get("data")
        rows = nested.get("items") if isinstance(nested, Mapping) else []
    result: list[dict[str, Any]] = []
    for item in rows if isinstance(rows, list) else []:
        if not isinstance(item, Mapping):
            continue
        book_id = str(
            item.get("novelid") or item.get("novelId") or item.get("book_id") or ""
        ).strip()
        title = str(
            item.get("novelname") or item.get("novelName") or item.get("title") or ""
        ).strip()
        if not book_id.isdigit() or not title:
            continue
        result.append(
            {
                "platform": "晋江",
                "book_id": book_id,
                "title": title,
                "author": str(
                    item.get("authorname")
                    or item.get("authorName")
                    or item.get("author")
                    or "未知"
                ).strip()
                or "未知",
                "url": f"https://www.jjwxc.net/onebook.php?novelid={book_id}",
                "word_count": item.get("novelsize") or item.get("novelSize") or 0,
                "heat": item.get("novelbefavoritedcount") or item.get("heat") or 0,
                "score": item.get("novelScore") or item.get("score") or 0,
            }
        )
    return result


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        async with 创建晋江HTTP会话(2) as session:
            data = await 请求晋江JSON(
                session,
                晋江搜索地址,
                {
                    "keyword": 关键词,
                    "type": "1",
                    "page": "1",
                    "searchType": "1",
                },
                允许业务错误=True,
            )
        code = _晋江数字码(data.get("code"))
        if code == "1055":
            return []
        if "code" in data and code not in {"0", "200", "2000"}:
            raise 晋江请求错误("business_error", code=code)
        return 解析晋江搜索结果(data)[
            : max(1, min(int(需要数量 or 20), 晋江搜索数量上限))
        ]
    except Exception as exc:
        logger.debug("晋江小说搜索失败：错误类型=%s", type(exc).__name__)
        return []


生成下载回复流 = 生成晋江下载回复流
