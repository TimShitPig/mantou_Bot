"""疯读小说 App：游客会话、原生连续多章和异步连接复用。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
from http.cookies import SimpleCookie
import json
from pathlib import Path
import re
import time
from typing import Any, AsyncIterator
import urllib.parse
import uuid

import aiohttp
from yarl import URL

try:
    from astrbot.api import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)
try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except ImportError:
    小说网盘 = None
from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具

from 功能文件.管理功能.小说功能.功能.平台隔离执行 import 创建平台同步调用, 创建平台缓存调用

_平台同步调用 = 创建平台同步调用('疯读')
_平台缓存调用 = 创建平台缓存调用('疯读', 文件缓存工具.删除小说缓存文件)
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题, 格式化小说字数

疯读基础地址 = "https://fiction.fengduxiaoshuo.com"
疯读激活地址 = "https://ws2.fengduxiaoshuo.com/auth/activate"
疯读每批章节数 = 100
疯读并发数 = 8
疯读目录每页数量 = 3000
疯读响应大小上限 = 16 * 1024 * 1024
疯读链接正则 = re.compile(r"https?://(?:[a-z0-9-]+\.)*fengduxiaoshuo\.com(?::\d+)?(?:/[^\s<>\"']*)?", re.I)
疯读文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
# 游客会话只保留于内存；不读取来源项目的会话或生成设备/账号文件。
疯读游客状态: dict[str, Any] = globals().get("疯读游客状态") or {}
疯读接口路径 = {
    "/doReader/search/result", "/doReader/api/book",
    "/doReader/api/book/chapters", "/doReader/api/get_content_by_chapterId",
}


class _疯读请求错误(RuntimeError):
    def __init__(self, category: str, *, http_status: int | None = None, code: int | None = None):
        super().__init__(category)
        self.category = category
        self.http_status = http_status
        self.code = code


class _疯读搜索结果(list[dict[str, Any]]):
    """保留已取得的候选，并让聚合层识别后续页失败。"""

    incomplete = False


def _整数(value: Any) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    return None


def _文本(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def _签名(path: str, parameters: dict[str, Any]) -> str:
    values = {key: str(value) for key, value in parameters.items()}
    keys = sorted(values, key=lambda value: value.encode("utf-16-be", "surrogatepass"))
    canonical = "GET&" + path + "&" + "&".join(key + "=" + values[key] for key in keys) + "&json=&"
    utf16 = canonical.encode("utf-16-be", "surrogatepass")
    modified = bytearray()
    for offset in range(0, len(utf16), 2):
        unit = (utf16[offset] << 8) | utf16[offset + 1]
        if 1 <= unit <= 0x7f:
            modified.append(unit)
        elif unit <= 0x7ff:
            modified.extend((0xc0 | (unit >> 6), 0x80 | (unit & 0x3f)))
        else:
            modified.extend((0xe0 | (unit >> 12), 0x80 | ((unit >> 6) & 0x3f), 0x80 | (unit & 0x3f)))
    digest = hashlib.md5(modified + b"B1w2OjLnERw6fXfl").hexdigest()
    return (base64.b64encode(digest.encode("ascii")).decode("ascii").rstrip("=") + "\n")[:-2]


def _激活参数(identifier: str, now_ms: int | None = None) -> dict[str, Any]:
    app_name, version, channel = "com.cootek.crazyreader.android", "1236", "01001P"
    os_version, device_info = "15", "2201123C"
    seconds = (time.time_ns() // 1_000_000 if now_ms is None else now_ms) // 1000
    values = (app_name, identifier, os_version, device_info, "", str(seconds))
    salts = (3761, 459310051, 131, 207806543, 961128419, 2302987)
    text = "".join((value if i % 2 == 0 else value[::-1]) + str(salts[i]) for i, value in enumerate(values))
    product = 1
    for char in hashlib.md5(text.encode("utf-8")).hexdigest():
        product = product * ord(char) % 1000000007
    digest = hashlib.md5((app_name + version + channel + identifier).encode("utf-8")).hexdigest()
    return {
        "app_name": app_name, "app_version": version, "activate_type": "new",
        "os_name": "android", "os_version": os_version, "device_info": device_info,
        "channel_code": channel, "identifier": identifier,
        "random_uuid": "-".join((digest[:8], digest[8:12], digest[12:16], digest[16:20], digest[20:])),
        "timestamp": int(str(seconds) + f"{product % 1000:03d}"),
    }


def 创建疯读HTTP会话() -> aiohttp.ClientSession:
    session = aiohttp.ClientSession(
        headers={"User-Agent": "okhttp/3.12.11", "Accept": "application/json", "Accept-Encoding": "gzip"},
        connector=aiohttp.TCPConnector(limit=疯读并发数, limit_per_host=疯读并发数, ttl_dns_cache=300),
        timeout=aiohttp.ClientTimeout(total=45, sock_connect=10, sock_read=30),
        cookie_jar=aiohttp.DummyCookieJar(),
    )
    if hasattr(session, "_retry_connection"):
        session._retry_connection = False
    return session


async def _读取JSON(response: Any) -> dict[str, Any]:
    if response.status != 200:
        raise _疯读请求错误("rate_limited" if response.status == 429 else "http_error", http_status=response.status)
    raw = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        if len(raw) + len(chunk) > 疯读响应大小上限:
            raise _疯读请求错误("response_too_large", http_status=200)
        raw.extend(chunk)
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _疯读请求错误("invalid_response", http_status=200) from exc
    if not isinstance(data, dict):
        raise _疯读请求错误("invalid_response", http_status=200)
    return data


async def _获取游客token(session: aiohttp.ClientSession, invalid_token: str = "") -> str:
    loop = asyncio.get_running_loop()
    if 疯读游客状态.get("loop") is not loop:
        疯读游客状态.update(loop=loop, lock=asyncio.Lock())
    async with 疯读游客状态["lock"]:
        token = 疯读游客状态.get("token")
        if isinstance(token, str) and token and token != invalid_token:
            return token
        if token == invalid_token:
            疯读游客状态.pop("token", None)
        identifier = 疯读游客状态.setdefault("identifier", uuid.uuid4().hex[:16])
        payload = json.dumps(_激活参数(identifier), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            async with session.post(疯读激活地址, data=payload, headers={"Content-Type": "application/json; charset=utf-8"}, allow_redirects=False) as response:
                data = await _读取JSON(response)
                code = _整数(data.get("error_code"))
                if code != 0:
                    raise _疯读请求错误("activation_failed", http_status=200, code=code)
                cookies = SimpleCookie()
                for item in response.headers.getall("Set-Cookie", []):
                    cookies.load(item)
                token = cookies["auth_token"].value if "auth_token" in cookies else ""
                if not token:
                    raise _疯读请求错误("activation_token_missing", http_status=200)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise _疯读请求错误("timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error") from exc
        疯读游客状态["token"] = token
        return token


async def _请求(session: aiohttp.ClientSession, path: str, parameters: dict[str, Any]) -> dict[str, Any]:
    if path not in 疯读接口路径:
        raise _疯读请求错误("invalid_endpoint")
    token = await _获取游客token(session)
    refreshed = False
    last: _疯读请求错误 | None = None
    attempt = 0
    while attempt < 3:
        values = {"_token": token, **parameters, "_sv": "v1", "_ts": str(int(time.time()))}
        values["_sign"] = _签名(path, values)
        url = URL(疯读基础地址 + path + "?" + urllib.parse.urlencode(values), encoded=True)
        try:
            async with session.get(url, allow_redirects=False) as response:
                envelope = await _读取JSON(response)
            code = _整数(envelope.get("result_code"))
            if code == 4003 and not refreshed:
                token = await _获取游客token(session, token)
                refreshed = True
                continue
            if code != 2000:
                raise _疯读请求错误("credential_invalid" if code == 4003 else "business_error", http_status=200, code=code)
            result = envelope.get("result")
            if not isinstance(result, dict):
                raise _疯读请求错误("invalid_response", http_status=200)
            return result
        except _疯读请求错误 as exc:
            if exc.category != "http_error" or exc.http_status not in {408, 500, 502, 503, 504}:
                raise
            last = exc
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            last = _疯读请求错误("timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error")
        attempt += 1
        if attempt < 3:
            await asyncio.sleep(0.25 * attempt)
    raise last or _疯读请求错误("request_failed")


def 构造疯读链接(book_id: Any) -> str:
    return f"{疯读基础地址}/doReader/api/book?book_id={book_id}"


def _展开来源(value: str) -> str:
    text = html.unescape(value).replace("\\/", "/")
    for _ in range(2):
        decoded = html.unescape(urllib.parse.unquote(text)).replace("\\/", "/")
        if decoded == text:
            break
        text = decoded
    return text


def 提取疯读书籍编号(source: Any) -> str:
    if not isinstance(source, str):
        return ""
    text = _展开来源(source.strip())
    if re.fullmatch(r"[1-9][0-9]*", text):
        return text
    try:
        parts = urllib.parse.urlsplit(text)
        host = (parts.hostname or "").lower()
        if parts.scheme not in {"http", "https"} or not (host == "fengduxiaoshuo.com" or host.endswith(".fengduxiaoshuo.com")):
            return ""
        query = urllib.parse.parse_qs(parts.query)
        for key in ("book_id", "bookId", "bookid", "id"):
            if len(query.get(key, [])) == 1 and re.fullmatch(r"[1-9][0-9]*", query[key][0]):
                return query[key][0]
        match = re.fullmatch(r"/(?:book|bookinfo|bookInfo|detail|reader)/(\d+)/?", parts.path)
        return match.group(1) if match and int(match.group(1)) > 0 else ""
    except (ValueError, TypeError):
        return ""


def _收集来源(value: Any, output: list[str], seen: set[int], depth: int = 0) -> None:
    if value is None or depth > 6:
        return
    if isinstance(value, str):
        output.append(value)
        return
    if isinstance(value, (int, float, bool, bytes)) or id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, dict):
        children = value.values()
    elif isinstance(value, (list, tuple)):
        children = value
    else:
        children = [getattr(value, field, None) for field in ("message_str", "message", "raw_message", "text", "content", "data")]
    for child in children:
        _收集来源(child, output, seen, depth + 1)


def 获取疯读小说回复流(event: Any, command: str, config: Any = None) -> AsyncIterator[Any] | None:
    match = re.fullmatch(r"疯读(?:小说)?\s+([1-9][0-9]*)", str(command or "").strip())
    if match:
        return 生成疯读下载回复流(event, match.group(1), config)
    values: list[str] = []
    _收集来源(command, values, set())
    _收集来源(event, values, set())
    for value in values:
        for found in 疯读链接正则.finditer(_展开来源(value)):
            source = found.group(0).rstrip("'\"，。；;]}>）)")
            if 提取疯读书籍编号(source):
                return 生成疯读下载回复流(event, source, config)
    return None


def _解析书籍(info: Any, book_id: str = "") -> dict[str, Any]:
    if not isinstance(info, dict):
        raise _疯读请求错误("invalid_detail")
    number = _整数(info.get("bookId"))
    title = _文本(info.get("bookTitle"))
    if number is None or number <= 0 or (book_id and str(number) != book_id) or not title:
        raise _疯读请求错误("invalid_detail")
    if _整数(info.get("bookType")) != 1 or _整数(info.get("is_audio_book")) not in {None, 0}:
        raise _疯读请求错误("unsupported_book_type")
    finished = _整数(info.get("bookIsFinished"))
    count = next((value for key in ("book_words_num_orig", "book_words_num") if (value := _整数(info.get(key))) is not None and value > 0), 0)
    return {
        "book_id": str(number), "title": title, "author": _文本(info.get("bookAuthor")) or "未知",
        "intro": _文本(info.get("bookDesc")), "status": {0: "连载", 1: "完结"}.get(finished, "未知"),
        "word_count": count, "url": 构造疯读链接(number),
    }


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    limit = max(1, min(30, int(需要数量 or 20)))
    books = _疯读搜索结果()
    seen: set[str] = set()
    async with 创建疯读HTTP会话() as session:
        for page in range(1, 4):
            try:
                token = await _获取游客token(session)
                data = await _请求(session, "/doReader/search/result", {
                    "key_words": keyword, "page_num": page, "api_version": "v10",
                    "nid": hashlib.md5((token + str(time.time_ns() // 1_000_000)).encode("utf-8")).hexdigest(),
                    "extra": '{"book_type":1}',
                })
                sections = data.get("sections")
                if not isinstance(sections, list):
                    raise _疯读请求错误("invalid_search")
                page_books = []
                for section in sections:
                    if not isinstance(section, dict):
                        raise _疯读请求错误("invalid_search")
                    if section.get("type") != "search":
                        continue
                    rows = section.get("books")
                    if not isinstance(rows, list):
                        raise _疯读请求错误("invalid_search")
                    for row in rows:
                        if not isinstance(row, dict):
                            raise _疯读请求错误("invalid_search")
                        if _整数(row.get("bookType")) != 1 or _整数(row.get("is_audio_book")) not in {None, 0}:
                            continue
                        page_books.append(_解析书籍(row))
            except _疯读请求错误:
                if not books:
                    raise
                books.incomplete = True
                return books
            added = 0
            for book in page_books:
                if book["book_id"] not in seen:
                    seen.add(book["book_id"])
                    books.append(book)
                    added += 1
                if len(books) >= limit:
                    return books
            if not added:
                break
    return books


async def 获取疯读详情(session: aiohttp.ClientSession, book_id: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    data = await _请求(session, "/doReader/api/book", {"book_id": book_id, "need_chapters": 0, "version": "v2"})
    detail = _解析书籍(data.get("book"), book_id)
    chapters: list[dict[str, str]] = []
    total: int | None = None
    seen: set[str] = set()
    page = 1
    while total is None or len(chapters) < total:
        catalog = await _请求(session, "/doReader/api/book/chapters", {"book_id": book_id, "page": page, "count": 疯读目录每页数量, "api_version": "v3"})
        current_total = _整数(catalog.get("total"))
        if current_total is None or current_total < 0 or (total is not None and total != current_total):
            raise _疯读请求错误("invalid_catalog_total")
        total = current_total
        rows = catalog.get("chapters")
        if not isinstance(rows, list) or (not rows and total):
            raise _疯读请求错误("incomplete_catalog")
        for row in rows:
            if not isinstance(row, dict):
                raise _疯读请求错误("invalid_catalog")
            number = _整数(row.get("chapterId"))
            title = _文本(row.get("chapterTitle"))
            if number is None or number <= 0 or str(number) in seen or not title or _整数(row.get("bookId")) != int(book_id):
                raise _疯读请求错误("invalid_catalog")
            seen.add(str(number))
            chapters.append({"id": str(number), "title": title})
        if len(chapters) > total:
            raise _疯读请求错误("invalid_catalog_total")
        page += 1
    if not chapters:
        raise _疯读请求错误("catalog_empty")
    return detail, chapters


def _划分章节批次(chapters: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    for chapter in chapters:
        if not batches or len(batches[-1]) >= 疯读每批章节数 or int(chapter["id"]) != int(batches[-1][-1]["id"]) + 1:
            batches.append([])
        batches[-1].append(chapter)
    return batches


async def _下载批次(session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]) -> list[str]:
    data = await _请求(session, "/doReader/api/get_content_by_chapterId", {"bookId": book_id, "chapterId": chapters[0]["id"], "chapterCount": len(chapters)})
    rows = data.get("content")
    if not isinstance(rows, list) or len(rows) != len(chapters):
        raise _疯读请求错误("incomplete_content")
    bodies = []
    for entry, row in zip(chapters, rows):
        if not isinstance(row, dict) or _整数(row.get("chapterId")) != int(entry["id"]) or _整数(row.get("bookId")) != int(book_id):
            raise _疯读请求错误("chapter_identity_mismatch")
        body = row.get("chapterContent")
        if not isinstance(body, str) or not body.strip():
            raise _疯读请求错误("empty_content")
        bodies.append(body)
    return bodies


async def 下载疯读正文(session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]) -> list[str]:
    batches = _划分章节批次(chapters)
    sem = asyncio.Semaphore(疯读并发数)
    logger.info("疯读小说章节进度：书籍编号=%s, 进度=0/%s, 百分比=0%%, 每批章节数=%s, 并发数=%s, HTTP会话复用=开启", book_id, len(chapters), 疯读每批章节数, 疯读并发数)

    async def one(index: int, batch: list[dict[str, str]]) -> tuple[int, list[str]]:
        async with sem:
            return index, await _下载批次(session, book_id, batch)

    tasks = [asyncio.create_task(one(index, batch)) for index, batch in enumerate(batches)]
    results: list[list[str] | None] = [None] * len(batches)
    done, threshold = 0, max(1, (len(chapters) + 3) // 4)
    next_log = threshold
    try:
        for task in asyncio.as_completed(tasks):
            index, bodies = await task
            results[index] = bodies
            done += len(bodies)
            if done >= next_log or done == len(chapters):
                logger.info("疯读小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 每批章节数=%s, 并发数=%s, HTTP会话复用=开启", book_id, done, len(chapters), int(done * 100 / len(chapters)), done, 疯读每批章节数, 疯读并发数)
                while next_log <= done:
                    next_log += threshold
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    if any(value is None for value in results):
        raise _疯读请求错误("incomplete_content")
    return [body for batch in results if batch is not None for body in batch]


def 格式化疯读下载提示(detail: dict[str, Any], count: int) -> str:
    return "\n".join([f"书名：{detail['title']}", f"作者：{detail['author']}", f"状态：{detail['status']}", f"章节：{count} 章", f"字数：{格式化小说字数(detail.get('word_count'))}", "", "正在下载中请稍等....."])


def _文件名(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", value).strip(" .")[:80] or "疯读小说"


def 生成疯读文件(book_id: str, detail: dict[str, Any], chapters: list[dict[str, str]], contents: list[str]) -> tuple[str, bytes]:
    if len(chapters) != len(contents) or not contents or any(not body.strip() for body in contents):
        raise _疯读请求错误("incomplete_content")
    title, author, status = detail["title"], detail["author"], detail["status"]
    lines = [疯读文件声明, "", f"名称：{title}", f"作者：{author}", f"状态：{status}", f"字数：{格式化小说字数(detail.get('word_count'))}", f"书籍ID：{book_id}", f"章节数：{len(chapters)}", ""]
    if detail.get("intro"):
        lines.extend(["简介：", detail["intro"], ""])
    for chapter, body in zip(chapters, contents):
        lines.extend([chapter["title"], "", 去除章节正文重复标题(chapter["title"], body), ""])
    text = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    return f"[{status}]书名：{_文件名(title)} 作者：{_文件名(author)}.txt", text.encode("utf-8")


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
    raise _疯读请求错误("cache_name_conflict")


async def _发送(event: Any, filename: str, content: bytes, config: Any, detail: dict[str, Any]) -> dict[str, Any]:
    path = await _平台缓存调用(_写入缓存,filename, content)
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
            文件缓存工具.解除小说缓存占用(path)
        else:
            文件缓存工具.删除小说缓存文件(path)


async def 生成疯读下载回复流(event: Any, source: str, config: Any = None) -> AsyncIterator[Any]:
    book_id = 提取疯读书籍编号(source)
    if not book_id:
        yield "下载失败 请重试"
        return
    stage = "metadata"
    try:
        async with 创建疯读HTTP会话() as session:
            detail, chapters = await 获取疯读详情(session, book_id)
            logger.info("疯读小说开始下载：书籍编号=%s, 书名=%s, 作者=%s, 章节数=%s", book_id, detail["title"], detail["author"], len(chapters))
            yield 格式化疯读下载提示(detail, len(chapters))
            stage = "chapters"
            bodies = await 下载疯读正文(session, book_id, chapters)
        filename, content = await _平台同步调用(生成疯读文件,book_id, detail, chapters, bodies)
        logger.info("疯读小说章节下载完成：书籍编号=%s, 成功=%s, 总数=%s, 文件大小=%s", book_id, len(bodies), len(chapters), len(content))
        stage = "upload_send"
        result = await _发送(event, filename, content, config, detail)
        if result.get("sent"):
            return
        if result.get("fallback_text"):
            yield str(result["fallback_text"])
            return
        logger.warning("疯读小说文件发送失败：stage=upload_send, book_id=%s, reason=upload_or_delivery_failed", book_id)
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning("疯读小说处理失败：stage=%s, book_id=%s, error_type=%s, category=%s, http_status=%s, code=%s", stage, book_id, type(exc).__name__, getattr(exc, "category", "unknown"), getattr(exc, "http_status", None), getattr(exc, "code", None))
        yield "文件发送失败，请稍后再试" if stage == "upload_send" else "下载失败 请重试"
