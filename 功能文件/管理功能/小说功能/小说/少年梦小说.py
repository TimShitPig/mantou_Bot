"""少年梦 App：公开找书与目录、当前账号草稿正文、200 路异步会话复用。"""

from __future__ import annotations

import asyncio
import errno as errno_codes
import hashlib
import html
import json
import os
from pathlib import Path
import re
import socket
import ssl
from typing import Any, AsyncIterator
from urllib.parse import parse_qs, unquote, urlsplit

import aiohttp

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID
from 功能文件.管理功能.小说功能.功能.平台隔离执行 import 创建平台同步调用, 创建平台缓存调用
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题, 格式化小说字数

少年梦基础地址 = "https://api.shaoniandream.com"
少年梦并发数 = 200
少年梦响应大小上限 = 16 * 1024 * 1024
少年梦签名KEY = '87ac02d392a8d3566fe7748c8de00af3'
少年梦签名SECRET = '57dcuidu8aa8062bfe8042ea65310669'
少年梦接口路径 = {
    "/Login/login",
    "/Booklibrary/index", "/Booklibrary/bookdetail", "/Booklibrary/readdir",
    "/Author/managerbooks", "/Author/tmpchapter", "/Author/getOneChapter",
}
少年梦链接正则 = re.compile(r"https?://(?:[a-z0-9-]+\.)*shaoniandream\.com(?:/[^\s<>\"']*)?", re.I)
少年梦文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
_平台同步调用 = 创建平台同步调用("少年梦")
_平台缓存调用 = 创建平台缓存调用("少年梦", 文件缓存工具.删除小说缓存文件)
_并发状态: dict[str, Any] = globals().get("_并发状态") or {}
_少年梦正文恢复总时限 = 120.0
_少年梦正文恢复退避 = (0.5, 1.0)
_少年梦正文最多尝试 = 3


class 少年梦请求错误(RuntimeError):
    def __init__(self, category: str, *, http_status: int | None = None, code: int | None = None,
                 network_type: str = "", request_stage: str = "", errno: int | None = None,
                 retryable: bool = False, attempt: int = 1):
        super().__init__(category)
        self.category, self.http_status, self.code = category, http_status, code
        self.network_type, self.request_stage = network_type, request_stage
        self.errno, self.retryable, self.attempt = errno, retryable, attempt


def _分类网络异常(exc: BaseException, *, request_stage: str, http_status: int | None = None) -> 少年梦请求错误:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and len(chain) < 6 and all(current is not item for item in chain):
        chain.append(current)
        current = current.__cause__
    names = {type(item).__name__ for item in chain}
    os_error = next((item for item in chain if isinstance(item, OSError) and type(item.errno) is int), None)
    number = os_error.errno if os_error is not None else None
    transient_errno = {errno_codes.ECONNRESET, errno_codes.ECONNABORTED, errno_codes.ECONNREFUSED,
                       errno_codes.ETIMEDOUT, errno_codes.EPIPE, errno_codes.ENETRESET,
                       errno_codes.EHOSTUNREACH, errno_codes.ENETUNREACH}
    category, retryable = "network_other", False
    if any(isinstance(item, (aiohttp.ClientConnectorCertificateError, ssl.SSLCertVerificationError)) for item in chain):
        category = "certificate_error"
    elif any(isinstance(item, (aiohttp.ClientSSLError, ssl.SSLError, aiohttp.ServerFingerprintMismatch)) for item in chain):
        category = "tls_error"
    elif any(isinstance(item, socket.gaierror) for item in chain):
        category = "dns_error"
        retryable = number == socket.EAI_AGAIN
    elif isinstance(exc, asyncio.TimeoutError):
        category = ("connect_timeout" if "ConnectionTimeoutError" in names else
                    "read_timeout" if "SocketTimeoutError" in names else
                    "server_timeout" if isinstance(exc, aiohttp.ServerTimeoutError) else "total_timeout")
        retryable = True
    elif isinstance(exc, aiohttp.ClientPayloadError):
        # 上游提前 EOF 与坏压缩/非法 chunk 使用同一异常外壳，只恢复已确认的中断。
        incomplete = any(type(item).__name__ == "ContentLengthError" or (
            type(item).__name__ == "TransferEncodingError" and
            getattr(item, "message", None) == "Not enough data to satisfy transfer length header."
        ) for item in chain[1:])
        category, retryable = ("payload_incomplete", True) if incomplete else ("payload_error", False)
        if number in transient_errno:
            category, retryable = "connection_reset", True
    elif isinstance(exc, aiohttp.ServerDisconnectedError):
        category, retryable = "server_disconnected", True
    elif number in transient_errno:
        category, retryable = "connection_reset", True
    elif isinstance(exc, aiohttp.ClientConnectorError):
        category = "connection_failed"
    elif isinstance(exc, aiohttp.ClientConnectionError):
        category, retryable = "connection_closed", True
    known_types = {"ClientConnectorCertificateError", "SSLCertVerificationError", "ClientConnectorSSLError",
                   "ClientSSLError", "SSLError", "ServerFingerprintMismatch", "ClientConnectorDNSError",
                   "ClientConnectorError", "ClientOSError", "ConnectionTimeoutError", "SocketTimeoutError",
                   "ServerTimeoutError", "TimeoutError", "ServerDisconnectedError", "ClientPayloadError",
                   "ClientConnectionError", "ServerConnectionError", "ConnectionResetError", "ConnectionAbortedError",
                   "ConnectionRefusedError", "BrokenPipeError", "OSError", "gaierror"}
    network_type = type(exc).__name__ if type(exc).__name__ in known_types else "OtherNetworkError"
    return 少年梦请求错误(category, http_status=http_status, network_type=network_type,
                          request_stage=request_stage, errno=number, retryable=retryable)


class _搜索结果(list):
    incomplete = False


def _整数(value: Any) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,18}", value):
        return int(value)
    return None


def _文本(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def _签名(parameters: dict[str, Any]) -> dict[str, Any]:
    fields = dict(parameters, isDevice="Android", regDevice="2")
    canonical = "".join(f"{key}={fields[key]}&" for key in sorted(fields) if fields[key] is not None and key not in {"sign", "key", "secrect"})
    canonical += f"key={少年梦签名KEY}&secrect={少年梦签名SECRET}"
    return dict(fields, sign=hashlib.md5(canonical.encode("utf-8")).hexdigest().upper())


def 创建少年梦HTTP会话() -> aiohttp.ClientSession:
    session = aiohttp.ClientSession(
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "okhttp/4.11.0", "version": "v4", "appversion": "1.5.7", "devicebrand": "Xiaomi", "appplatform": "shaoniandream"},
        connector=aiohttp.TCPConnector(limit=少年梦并发数, limit_per_host=少年梦并发数, ttl_dns_cache=300),
        timeout=aiohttp.ClientTimeout(total=45, sock_connect=10, sock_read=30),
        cookie_jar=aiohttp.DummyCookieJar(),
    )
    if hasattr(session, "_retry_connection"):
        session._retry_connection = False
    return session


async def _请求(session: aiohttp.ClientSession, path: str, fields: dict[str, Any], *, token: str = "") -> Any:
    if path not in 少年梦接口路径 or (token and not path.startswith("/Author/")):
        raise 少年梦请求错误("invalid_endpoint")
    loop = asyncio.get_running_loop()
    if _并发状态.get("loop") is not loop:
        _并发状态.update(loop=loop, semaphore=asyncio.Semaphore(少年梦并发数))
    request_stage, http_status = "queue", None
    try:
        async with _并发状态["semaphore"]:
            request_stage = "request"
            async with session.post(少年梦基础地址 + path, data=json.dumps(_签名(fields), ensure_ascii=False, separators=(",", ":")).encode("utf-8"), headers={"logintoken": token} if token else None, allow_redirects=False) as response:
                http_status = response.status
                if response.status != 200:
                    raise 少年梦请求错误("rate_limited" if response.status == 429 else "http_error", http_status=response.status)
                request_stage = "read"
                raw = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    if len(raw) + len(chunk) > 少年梦响应大小上限:
                        raise 少年梦请求错误("response_too_large", http_status=200)
                    raw.extend(chunk)
                request_stage = "parse"
                try:
                    result = json.loads(raw.decode("utf-8-sig"))
                except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
                    raise 少年梦请求错误("invalid_response", http_status=200) from exc
                if not isinstance(result, dict):
                    raise 少年梦请求错误("invalid_response", http_status=200)
                code = _整数(result.get("status"))
                if code != 1 or (path == "/Login/login" and type(result.get("status")) is not int):
                    raise 少年梦请求错误("business_error", http_status=200, code=code)
                if "data" not in result:
                    raise 少年梦请求错误("invalid_response", http_status=200)
                return result["data"]
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        raise _分类网络异常(exc, request_stage=request_stage, http_status=http_status) from None


async def _请求少年梦草稿正文(session: aiohttp.ClientSession, fields: dict[str, Any], token: str) -> Any:
    # 只重读原章节，不重放登录、草稿选择或其他接口；预算包含队列、请求与退避。
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _少年梦正文恢复总时限
    for attempt in range(1, _少年梦正文最多尝试 + 1):
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise 少年梦请求错误("total_timeout", network_type="TimeoutError", request_stage="budget", attempt=attempt)
        try:
            return await asyncio.wait_for(_请求(session, "/Author/getOneChapter", fields, token=token), timeout=remaining)
        except asyncio.TimeoutError:
            raise 少年梦请求错误("total_timeout", network_type="TimeoutError", request_stage="budget", attempt=attempt) from None
        except 少年梦请求错误 as exc:
            exc.attempt = attempt
            if not exc.retryable or attempt == _少年梦正文最多尝试:
                raise
            delay = _少年梦正文恢复退避[attempt - 1]
            if deadline - loop.time() <= delay:
                raise 少年梦请求错误("total_timeout", network_type="TimeoutError", request_stage="budget", attempt=attempt) from None
            logger.warning("少年梦正文瞬时请求恢复：stage=%s, attempt=%s, category=%s, network_type=%s, errno=%s, http_status=%s",
                           exc.request_stage, attempt, exc.category, exc.network_type, exc.errno, exc.http_status)
            await asyncio.sleep(delay)


def 读取少年梦账号(config: Any) -> tuple[int, str]:
    # 只能使用当前机器人的快照，不能借用顶层配置或其他机器人账号。
    appid = 获取当前机器人AppID(config)
    if not appid or not isinstance(config, dict):
        raise 少年梦请求错误("account_missing")
    if config.get("__mantou_bot_appid__") == appid:
        settings = config.get("shaoniandream_settings")
    else:
        profiles = config.get("bot_profiles")
        profile = profiles.get(appid) if isinstance(profiles, dict) else None
        settings = profile.get("shaoniandream_settings") if isinstance(profile, dict) else None
    value = settings.get("shaoniandream_session") if isinstance(settings, dict) else None
    return _解析少年梦会话(value)


def _解析少年梦会话(value: Any) -> tuple[int, str]:
    if not isinstance(value, str) or not value.strip() or len(value) > 20000:
        raise 少年梦请求错误("account_missing")
    try:
        data = json.loads(value)
    except (ValueError, RecursionError) as exc:
        raise 少年梦请求错误("invalid_account") from exc
    if isinstance(data, dict) and "response" in data:
        data = data["response"]
    if isinstance(data, dict) and "data" in data:
        if type(data.get("status")) is not int or data["status"] != 1:
            raise 少年梦请求错误("invalid_account")
        data = data["data"]
    if not isinstance(data, dict) or type(data.get("id")) is not int or data["id"] <= 0:
        raise 少年梦请求错误("invalid_account")
    token = data.get("logintoken")
    if not isinstance(token, str) or not token.strip() or len(token) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in token):
        raise 少年梦请求错误("invalid_account")
    return data["id"], token


async def 登录少年梦账号(phone: str, password: str) -> str:
    """提交一次官方登录，仅返回可保存的最小会话，密码不落盘。"""
    if not isinstance(phone, str) or re.fullmatch(r"[0-9]{11}", phone) is None:
        raise 少年梦请求错误("invalid_login_input")
    if not isinstance(password, str) or not password or len(password) > 1024:
        raise 少年梦请求错误("invalid_login_input")
    async with 创建少年梦HTTP会话() as session:
        data = await _请求(session, "/Login/login", {"phone": phone, "password": password})
    # 登录响应只允许用户对象，不能把其他嵌套响应当作成功账号。
    if not isinstance(data, dict):
        raise 少年梦请求错误("invalid_account")
    value = json.dumps({"id": data.get("id"), "logintoken": data.get("logintoken")}, ensure_ascii=False, separators=(",", ":"))
    _解析少年梦会话(value)
    return value


async def 自动获取少年梦草稿BookID(session: aiohttp.ClientSession, account: tuple[int, str]) -> int:
    user_id, token = account
    seen: set[int] = set()
    for page in range(1, 101):
        rows = await _请求(session, "/Author/managerbooks", {"UserID": user_id, "page": page, "count": 50}, token=token)
        if not isinstance(rows, list):
            raise 少年梦请求错误("invalid_author_books")
        if not rows:
            break
        for row in rows:
            book_id = _整数(row.get("id")) if isinstance(row, dict) else None
            if book_id is None or book_id <= 0 or book_id in seen:
                raise 少年梦请求错误("invalid_author_books")
            seen.add(book_id)
            drafts = await _请求(session, "/Author/tmpchapter", {"UserID": user_id, "BookID": book_id}, token=token)
            if not isinstance(drafts, list):
                raise 少年梦请求错误("invalid_drafts")
            for draft in drafts:
                if not isinstance(draft, dict) or _整数(draft.get("BookID")) != book_id or (_整数(draft.get("id")) or 0) <= 0:
                    raise 少年梦请求错误("invalid_drafts")
            if drafts:
                return book_id
        if len(rows) < 50:
            break
    raise 少年梦请求错误("draft_book_missing")


def 构造少年梦链接(book_id: Any) -> str:
    return f"https://h5.shaoniandream.com/pages/bookdetail/detail?bookid={book_id}"


def _展开来源(value: str) -> str:
    text = html.unescape(value).replace("\\/", "/")
    for _ in range(2):
        decoded = html.unescape(unquote(text)).replace("\\/", "/")
        if decoded == text:
            break
        text = decoded
    return text


def _解析下载目标(source: Any) -> dict[str, str] | None:
    if not isinstance(source, str):
        return None
    text = _展开来源(source.strip())
    match = re.fullmatch(r"(?:少年梦(?:小说)?\s*)?([1-9][0-9]{0,17})(?:\s+([1-9][0-9]{0,17}))?", text)
    if match:
        return {"book_id": match[1], "chapter_id": match[2] or ""}
    for found in 少年梦链接正则.finditer(text):
        try:
            parsed = urlsplit(found.group(0).rstrip("'\"，。；;]}>）)"))
            host = (parsed.hostname or "").lower()
            if parsed.username or parsed.password or parsed.port not in {None, 80, 443} or not (host == "shaoniandream.com" or host.endswith(".shaoniandream.com")):
                continue
            query = parse_qs(parsed.query)
            bids = [v for k, values in query.items() if k.lower() in {"bookid", "book_id"} for v in values]
            cids = [v for k, values in query.items() if k.lower() in {"chapterid", "chapter_id"} for v in values]
            if len(bids) == 1 and len(cids) <= 1 and re.fullmatch(r"[1-9][0-9]{0,17}", bids[0]) and (not cids or re.fullmatch(r"[1-9][0-9]{0,17}", cids[0])):
                return {"book_id": bids[0], "chapter_id": cids[0] if cids else ""}
        except ValueError:
            continue
    return None


async def 提取少年梦下载目标(source: Any) -> dict[str, str] | None:
    return _解析下载目标(source)


def 提取少年梦书籍编号(source: Any) -> str:
    target = _解析下载目标(source)
    return target["book_id"] if target else ""


def _收集来源(value: Any, results: list[str], visited: set[int], depth: int = 0) -> None:
    if value is None or depth > 6:
        return
    if isinstance(value, str):
        results.append(value)
        return
    if id(value) in visited:
        return
    visited.add(id(value))
    if isinstance(value, dict):
        for key in ("url", "jumpUrl", "jump_url", "desc", "text", "content", "data", "meta", "detail_1", "news", "raw_message", "message"):
            if key in value:
                _收集来源(value[key], results, visited, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _收集来源(item, results, visited, depth + 1)
    else:
        for name in ("message_str", "raw_message", "message_obj", "message", "data", "text", "url"):
            _收集来源(getattr(value, name, None), results, visited, depth + 1)


def 获取少年梦小说回复流(event: Any, source: str, config: Any = None) -> AsyncIterator[Any] | None:
    if isinstance(source, str) and re.fullmatch(r"少年梦(?:小说)?\s*[1-9][0-9]{0,17}(?:\s+[1-9][0-9]{0,17})?", source.strip()):
        return 生成少年梦下载回复流(event, source, config)
    values: list[str] = []
    _收集来源(source, values, set())
    _收集来源(event, values, set())
    for value in values:
        if 少年梦链接正则.search(_展开来源(value)) and _解析下载目标(value):
            return 生成少年梦下载回复流(event, value, config)
    return None


def _解析书籍(row: Any, expected_id: str = "", *, search: bool = False) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise 少年梦请求错误("invalid_detail")
    book_id = _整数(row.get("BooksID" if search else "id"))
    title = _文本(row.get("title"))
    if not book_id or book_id < 0 or not title or (expected_id and str(book_id) != expected_id):
        raise 少年梦请求错误("book_identity_mismatch")
    author_obj = row.get("AuthorObj")
    author = row.get("penName") if search else author_obj.get("penName") if isinstance(author_obj, dict) else None
    word_count = row.get("FontCount")
    if not isinstance(word_count, (str, int)) or isinstance(word_count, bool):
        word_count = None
    return {"book_id": str(book_id), "title": title, "author": _文本(author) or "未知", "intro": _文本(row.get("jianjie")), "status": {1: "连载", 2: "完结"}.get(_整数(row.get("serialState")), "未知"), "word_count": word_count, "url": 构造少年梦链接(book_id)}


async def 搜索少年梦小说(keyword: str, limit: int = 30, config: Any = None) -> list[dict[str, Any]]:
    if not isinstance(keyword, str) or not keyword.strip():
        return []
    limit = max(1, min(30, int(limit)))
    books = _搜索结果()

    async def search() -> None:
        seen: set[str] = set()
        async with 创建少年梦HTTP会话() as session:
            for page in range(1, 3):
                rows = await _请求(session, "/Booklibrary/index", {"keywords": keyword.strip(), "page": page, "count": 20})
                if not isinstance(rows, list):
                    raise 少年梦请求错误("invalid_search")
                for row in rows:
                    book = _解析书籍(row, search=True)
                    if book["book_id"] not in seen:
                        seen.add(book["book_id"])
                        books.append(book)
                    if len(books) >= limit:
                        return
                if len(rows) < 20:
                    return
    try:
        await asyncio.wait_for(search(), timeout=10)
    except (少年梦请求错误, asyncio.TimeoutError):
        if not books:
            raise
        books.incomplete = True
    return books


async def 获取少年梦详情(session: aiohttp.ClientSession, book_id: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    detail = _解析书籍(await _请求(session, "/Booklibrary/bookdetail", {"BookID": int(book_id), "UserID": -1}), book_id)
    data = await _请求(session, "/Booklibrary/readdir", {"BookID": int(book_id), "UserID": -1})
    if not isinstance(data, dict) or _整数(data.get("id")) != int(book_id) or _文本(data.get("title")) != detail["title"]:
        raise 少年梦请求错误("book_identity_mismatch")
    volumes = data.get("chapterList")
    if not isinstance(volumes, list):
        raise 少年梦请求错误("invalid_catalog")
    chapters: list[dict[str, str]] = []
    seen: set[int] = set()
    for volume in volumes:
        if not isinstance(volume, dict) or _整数(volume.get("BookID")) != int(book_id) or not isinstance(volume.get("chapterList"), list):
            raise 少年梦请求错误("invalid_catalog")
        for row in volume["chapterList"]:
            chapter_id = _整数(row.get("id")) if isinstance(row, dict) else None
            title = _文本(row.get("title")) if isinstance(row, dict) else ""
            if not chapter_id or chapter_id < 0 or chapter_id in seen or not title:
                raise 少年梦请求错误("invalid_catalog")
            seen.add(chapter_id)
            chapters.append({"id": str(chapter_id), "title": title})
    total = _整数(data.get("chapterCount"))
    if total is not None and total != len(chapters):
        raise 少年梦请求错误("incomplete_catalog")
    if not chapters:
        raise 少年梦请求错误("catalog_empty")
    return detail, chapters


async def 获取少年梦草稿正文(session: aiohttp.ClientSession, account: tuple[int, str], draft_book_id: int, chapter_id: str, *, expected_book_id: str = "") -> tuple[str, str]:
    user_id, token = account
    data = await _请求少年梦草稿正文(session, {"UserID": user_id, "BookID": draft_book_id, "ChapterID": int(chapter_id)}, token)
    row = data.get("ChapterObj") if isinstance(data, dict) else None
    if not isinstance(row, dict) or _整数(row.get("id")) != int(chapter_id) or (expected_book_id and _整数(row.get("BookID")) != int(expected_book_id)):
        raise 少年梦请求错误("chapter_identity_mismatch")
    body = row.get("theContent")
    title = _文本(row.get("title"))
    if not isinstance(body, str) or not body.strip() or not title:
        raise 少年梦请求错误("empty_content")
    return title, body


async def 下载少年梦正文(session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]], account: tuple[int, str], draft_book_id: int) -> list[str]:
    # 固定工人数，完成一章立即补位；结果写回原目录位置。
    contents = [""] * len(chapters)
    jobs = iter(enumerate(chapters))
    done, next_log = 0, max(1, (len(chapters) + 3) // 4)
    step = next_log
    logger.info("少年梦小说章节进度：进度=0/%s, 并发数=%s, HTTP会话复用=开启", len(chapters), min(少年梦并发数, len(chapters)))

    async def worker() -> None:
        nonlocal done, next_log
        for index, chapter in jobs:
            title, body = await 获取少年梦草稿正文(session, account, draft_book_id, chapter["id"], expected_book_id=book_id)
            if title != chapter["title"]:
                raise 少年梦请求错误("chapter_title_mismatch")
            contents[index] = body
            done += 1
            if done >= next_log or done == len(chapters):
                logger.info("少年梦小说章节进度：进度=%s/%s, 百分比=%s%%, HTTP会话复用=开启", done, len(chapters), int(done * 100 / len(chapters)))
                next_log += step
    tasks = [asyncio.create_task(worker()) for _ in range(min(少年梦并发数, len(chapters)))]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return contents


def 格式化少年梦下载提示(detail: dict[str, Any], count: int) -> str:
    return "\n".join(["宝宝你的", "", f"书名：{detail['title']}", f"作者：{detail['author']}", f"状态：{detail['status']}", f"章节：{count}", f"字数：{格式化小说字数(detail.get('word_count'))}", "", "正在下载中请稍等....."])


def 生成少年梦文件(book_id: str, detail: dict[str, Any], chapters: list[dict[str, str]], contents: list[str]) -> tuple[str, bytes]:
    if len(chapters) != len(contents) or not contents or any(not body.strip() for body in contents):
        raise 少年梦请求错误("incomplete_content")
    lines = [少年梦文件声明, "", f"名称：{detail['title']}", f"作者：{detail['author']}", f"状态：{detail['status']}", f"字数：{格式化小说字数(detail.get('word_count'))}", f"书籍ID：{book_id}", f"章节数：{len(chapters)}", ""]
    if detail.get("intro"):
        lines.extend(["简介：", detail["intro"], ""])
    for chapter, body in zip(chapters, contents):
        lines.extend([chapter["title"], "", 去除章节正文重复标题(chapter["title"], body), ""])
    def filename(value: str) -> str:
        return re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", value).strip(" .")[:80] or "未知"
    text = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    return f"[{detail['status']}]书名：{filename(detail['title'])} 作者：{filename(detail['author'])}.txt", text.encode("utf-8")


def _写入缓存(filename: str, content: bytes) -> Path:
    directory = 文件缓存工具.小说缓存目录
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = directory / (Path(filename).name if index == 0 else f"{Path(filename).stem}_{index}.txt")
        try:
            文件缓存工具.独占写入小说缓存(path, content)
        except 文件缓存工具.小说缓存文件已存在:
            continue
        try:
            文件缓存工具.标记小说缓存正在使用(path)
        except BaseException:
            path.unlink(missing_ok=True)
            文件缓存工具.解除小说缓存占用(path)
            marker = 文件缓存工具.获取小说缓存占用标记路径(path)
            marker.with_name(f"{marker.name}.{os.getpid()}.tmp").unlink(missing_ok=True)
            raise
        return path
    raise 少年梦请求错误("cache_name_conflict")


async def _发送(event: Any, filename: str, content: bytes, config: Any, detail: dict[str, Any]) -> dict[str, Any]:
    from 功能文件.管理功能.网盘功能 import 小说网盘
    path = await _平台缓存调用(_写入缓存, filename, content)
    cancelled = False
    try:
        uploaded = await 小说网盘.上传小说并获取分享链接(config, path, filename)
        if not uploaded.get("success"):
            return {"sent": False}
        return await 小说网盘.发送小说下载结果(event, detail["title"], detail["author"], uploaded)
    except asyncio.CancelledError:
        cancelled = True
        raise
    finally:
        if cancelled:
            文件缓存工具.解除小说缓存占用(path)
        else:
            文件缓存工具.删除小说缓存文件(path)


async def 生成少年梦下载回复流(event: Any, source: str, config: Any = None) -> AsyncIterator[Any]:
    target = _解析下载目标(source)
    if not target:
        yield "下载失败 请重试"
        return
    book_id, chapter_id = target["book_id"], target["chapter_id"]
    stage = "account"
    try:
        account = 读取少年梦账号(config)
        async with 创建少年梦HTTP会话() as session:
            stage = "draft_book"
            draft_book_id = await 自动获取少年梦草稿BookID(session, account)
            stage = "metadata"
            if chapter_id:
                # 手动章节直接请求，不要求出现在草稿列表或公开目录中。
                detail = _解析书籍(await _请求(session, "/Booklibrary/bookdetail", {"BookID": int(book_id), "UserID": -1}), book_id)
                stage = "chapters"
                title, body = await 获取少年梦草稿正文(session, account, draft_book_id, chapter_id, expected_book_id=book_id)
                chapters, bodies = [{"id": chapter_id, "title": title}], [body]
                yield 格式化少年梦下载提示(detail, 1)
            else:
                detail, chapters = await 获取少年梦详情(session, book_id)
                yield 格式化少年梦下载提示(detail, len(chapters))
                stage = "chapters"
                bodies = await 下载少年梦正文(session, book_id, chapters, account, draft_book_id)
        filename, content = await _平台同步调用(生成少年梦文件, book_id, detail, chapters, bodies)
        stage = "upload_send"
        result = await _发送(event, filename, content, config, detail)
        if result.get("sent"):
            return
        yield str(result["fallback_text"]) if result.get("fallback_text") else "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning("少年梦小说处理失败：stage=%s, error_type=%s, category=%s, network_type=%s, request_stage=%s, attempt=%s, errno=%s, http_status=%s, code=%s", stage, type(exc).__name__, getattr(exc, "category", "unknown"), getattr(exc, "network_type", ""), getattr(exc, "request_stage", ""), getattr(exc, "attempt", 1), getattr(exc, "errno", None), getattr(exc, "http_status", None), getattr(exc, "code", None))
        yield "文件发送失败，请稍后再试" if stage == "upload_send" else "下载失败 请重试"
