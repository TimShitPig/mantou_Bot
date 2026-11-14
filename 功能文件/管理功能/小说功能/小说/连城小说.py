"""连城读书独立异步下载模块。"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import html
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp
from yarl import URL

try:
    from Crypto.Cipher import DES
    from Crypto.Util.Padding import unpad
except ImportError:
    DES = None

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)
try:
    from 功能文件.管理功能.网盘功能 import 小说网盘, 百度网盘
except Exception:
    百度网盘 = 小说网盘 = None
from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

连城基础地址 = "http://a.lc1001.com"
连城域名 = {"lc1001.com", "www.lc1001.com", "h5.lc1001.com"}
连城链接正则 = re.compile(r"https?://(?:[^\s/<>\"']*\.)?lc1001\.com[^\s<>\"']*", re.I)
连城并发数 = 200
连城重试次数 = 3
连城响应大小上限 = 4 * 1024 * 1024
连城接口 = {
    "/app/query/keybooks": ("POST", "POST", ("consumerKey", "pn", "timestamp", "uID")),
    "/app/info/bookindex": ("GET", "GET", ("bID", "consumerKey", "lmID", "timestamp", "uID")),
    "/app/info/bookcata": ("GET", "GET", ("bID", "consumerKey", "isUpdate", "timestamp", "uID")),
    "/app/book/pubchapter": ("POST", "GET", ("bID", "cID", "consumerKey", "timestamp", "uID")),
}
连城缓存目录 = 文件缓存工具.小说缓存目录
连城声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
连城请求头 = {
    "User-Agent": "okhttp/4.9.1",
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
}


class _连城请求错误(RuntimeError):
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


def _签名(method: str, url: str, parameters: str) -> str:
    def encode(value: str) -> str:
        return urllib.parse.quote_plus(value, safe="*").replace("~", "%7E")

    value = method + encode(url) + encode(parameters) + "XKrqBSeeEwgDy2pT"
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _文本(value: Any) -> str:
    return re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
        "",
        html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))),
    ).strip()


def _收集(value: Any, output: list[str], seen: set[int], depth: int = 0) -> None:
    if value is None or depth > 7:
        return
    if isinstance(value, str):
        output.append(value)
        return
    if isinstance(value, dict):
        try:
            output.append(json.dumps(value, ensure_ascii=False, default=str))
        except Exception:
            pass
        for child in value.values():
            _收集(child, output, seen, depth + 1)
        return
    if isinstance(value, (list, tuple, set)):
        for child in value:
            _收集(child, output, seen, depth + 1)
        return
    if id(value) in seen:
        return
    seen.add(id(value))
    for field in ("message_str", "message", "raw_message", "text", "content", "data"):
        try:
            _收集(getattr(value, field, None), output, seen, depth + 1)
        except Exception:
            pass


def 提取连城来源(event: Any, command: Any) -> str | None:
    values: list[str] = []
    _收集(command, values, set())
    _收集(event, values, set())
    for value in values:
        match = 连城链接正则.search(urllib.parse.unquote(value))
        if match:
            return match.group(0).rstrip("'\"，。；;]}>）)")
    for value in values:
        if "连城" not in value and "lc1001" not in value.lower():
            continue
        match = re.search(r"(?:bid|book[_-]?id|bookId)\D{0,8}(\d{5,})", value, re.I)
        if match:
            return 构造连城链接(match.group(1))
    return None


def 解析连城书籍编号(source: str) -> str:
    text = urllib.parse.unquote(str(source or ""))
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(text).query)
        for key in ("bID", "bid", "book_id", "bookId", "id"):
            if query.get(key) and str(query[key][0]).isdigit():
                return str(query[key][0])
    except Exception:
        pass
    match = re.search(r"(?:book|detail|reader)[^0-9]{0,15}(\d{5,})", text, re.I)
    return match.group(1) if match else ""


def 构造连城链接(book_id: Any) -> str:
    return f"https://h5.lc1001.com/book/{book_id}"


def 创建连城HTTP会话(concurrency: int = 连城并发数) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    connector = aiohttp.TCPConnector(
        limit=max(1, int(concurrency)),
        limit_per_host=max(1, int(concurrency)),
        ttl_dns_cache=300,
    )
    session = aiohttp.ClientSession(
        headers=连城请求头, timeout=timeout, connector=connector
    )
    if hasattr(session, "_retry_connection"):
        session._retry_connection = False
    return session


async def _请求(
    session: aiohttp.ClientSession, path: str, data: dict[str, Any]
) -> dict[str, Any]:
    if path not in 连城接口:
        raise _连城请求错误("invalid_endpoint")
    method, signature_method, fields = 连城接口[path]
    last: _连城请求错误 | None = None
    for attempt in range(连城重试次数):
        values = {
            **{key: str(value) for key, value in data.items()},
            "consumerKey": "LCREAD_ANDROID",
            "timestamp": str(int(time.time() * 1000)),
            "uID": "0",
        }
        parameters = "".join(key + "=" + values[key] for key in fields)
        values["sign"] = _签名(signature_method, 连城基础地址 + path, parameters)
        url = URL(连城基础地址 + path + "?" + urllib.parse.urlencode(values), encoded=True)
        try:
            async with session.request(
                method, url, data=b"" if method == "POST" else None,
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise _连城请求错误(
                        "rate_limited" if response.status == 429 else "http_error",
                        http_status=response.status,
                    )
                raw = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    if len(raw) + len(chunk) > 连城响应大小上限:
                        raise _连城请求错误("response_too_large", http_status=200)
                    raw.extend(chunk)
                try:
                    value = json.loads(raw.decode("utf-8-sig"))
                except (json.JSONDecodeError, UnicodeError) as exc:
                    raise _连城请求错误("invalid_response", http_status=200) from exc
            code = _整数(value.get("RETCODE")) if isinstance(value, dict) else None
            if code is None:
                raise _连城请求错误("invalid_response", http_status=200)
            if code != 200:
                raise _连城请求错误("business_error", http_status=200, code=code)
            return value
        except _连城请求错误 as exc:
            if exc.category != "http_error" or exc.http_status not in {408, 500, 502, 503, 504}:
                raise
            last = exc
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            last = _连城请求错误(
                "timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error"
            )
        if attempt + 1 < 连城重试次数:
            await asyncio.sleep(0.2 * (attempt + 1))
    raise last or _连城请求错误("network_error")


async def 获取连城详情(
    session: aiohttp.ClientSession, book_id: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    detail = await _请求(session, "/app/info/bookindex", {"bID": book_id, "lmID": "1000"})
    info = detail.get("DATA")
    if (
        not isinstance(info, dict)
        or str(info.get("BID")) != str(book_id)
        or not _文本(info.get("BNAME"))
    ):
        raise _连城请求错误("invalid_detail")
    catalog = await _请求(
        session, "/app/info/bookcata", {"bID": book_id, "isUpdate": "0"}
    )
    body = catalog.get("DATA")
    volumes = body.get("BOOKCATA") if isinstance(body, dict) else None
    if not isinstance(volumes, list):
        raise _连城请求错误("invalid_catalog")
    chapters: list[dict[str, str]] = []
    seen: set[str] = set()
    for volume in volumes:
        if not isinstance(volume, dict) or not isinstance(volume.get("CHAPTERS"), list):
            raise _连城请求错误("invalid_catalog")
        for chapter in volume["CHAPTERS"]:
            chapter_id = str(chapter.get("CID") or "") if isinstance(chapter, dict) else ""
            if not chapter_id.isascii() or not chapter_id.isdigit() or chapter_id in seen:
                raise _连城请求错误("invalid_catalog")
            seen.add(chapter_id)
            # 游客只取目录明确标注的公开章；遍历所有卷，保留后部免费番外。
            if _整数(chapter.get("ISVC")) != 0:
                continue
            title = _文本(chapter.get("CNAME"))
            if not title:
                raise _连城请求错误("invalid_catalog")
            chapters.append({"id": chapter_id, "title": title})
    detail_info = {
        "title": _文本(info.get("BNAME")),
        "author": _文本(info.get("ANAME") or "未知"),
        "intro": _文本(info.get("CONTENT")),
        "status": "完结"
        if str(info.get("STATE") or "").lower() in {"1", "finish", "完结"}
        else "连载",
        "word_count": info.get("WORDNUM") or 0,
    }
    return detail_info, chapters


def _解密正文(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise _连城请求错误("invalid_content")
    if DES is None:
        raise _连城请求错误("crypto_unavailable")
    try:
        encrypted = base64.b64decode("".join(value.split()), validate=True)
        if not encrypted or len(encrypted) % DES.block_size:
            raise ValueError("invalid_cipher")
        decrypted = DES.new(
            b"1701019k", DES.MODE_CBC, bytes.fromhex("0102030405060708")
        ).decrypt(encrypted)
        return unpad(decrypted, DES.block_size).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeError) as exc:
        raise _连城请求错误("decrypt_error") from exc


async def _下载章节(
    session: aiohttp.ClientSession,
    book_id: str,
    chapter: dict[str, str],
    sem: asyncio.Semaphore,
) -> str:
    async with sem:
        try:
            data = await _请求(
                session, "/app/book/pubchapter",
                {"bID": book_id, "cID": chapter["id"], "token": "0",
                 "mType": "XIAOMI-2201123C", "PACKINGCHANNEL": "PCALL"},
            )
            node = data.get("DATA")
            if (
                not isinstance(node, dict)
                or str(node.get("BID")) != str(book_id)
                or _文本(node.get("CNAME")) != chapter["title"]
                or ("CID" in node and str(node["CID"]) != chapter["id"])
                or _整数(node.get("ISVC")) != 0
            ):
                raise _连城请求错误("invalid_chapter")
            content = _解密正文(node.get("CTXT"))
            content = _文本(re.sub(r"<br\s*/?>", "\n", content, flags=re.I))
            if not content:
                raise _连城请求错误("empty_content")
            return content
        except Exception as exc:
            logger.debug(
                "连城小说章节获取失败：章节=%s, 错误类型=%s, category=%s, http_status=%s, code=%s",
                chapter.get("id"), type(exc).__name__, getattr(exc, "category", "unknown"),
                getattr(exc, "http_status", None), getattr(exc, "code", None),
            )
    return ""


async def 下载连城正文(
    session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]
) -> list[str]:
    results = [""] * len(chapters)
    sem = asyncio.Semaphore(max(1, min(连城并发数, len(chapters) or 1)))
    done = 0
    next_log = max(1, (len(chapters) + 3) // 4)
    lock = asyncio.Lock()

    async def one(index: int, chapter: dict[str, str]) -> None:
        nonlocal done, next_log
        results[index] = await _下载章节(session, book_id, chapter, sem)
        async with lock:
            done += 1
            if done >= next_log or done == len(chapters):
                success = sum(bool(item) for item in results)
                logger.info(
                    "连城小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s, 并发数=%s, 会话复用=开启, 解密方式=DES",
                    book_id,
                    done,
                    len(chapters),
                    int(done * 100 / max(1, len(chapters))),
                    success,
                    done - success,
                    连城并发数,
                )
                next_log += max(1, (len(chapters) + 3) // 4)

    await asyncio.gather(*(one(i, chapter) for i, chapter in enumerate(chapters)))
    return results


def _字数(value: Any) -> str:
    try:
        number = int(str(value or "").replace(",", ""))
        return f"{number:,}字" if number > 0 else "未知"
    except Exception:
        return "未知"


def _文件名(value: Any) -> str:
    return (
        re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "未知")).strip(" .")[:80]
        or "连城小说"
    )


def 生成连城文件(
    book_id: str,
    detail: dict[str, Any],
    chapters: list[dict[str, str]],
    contents: list[str],
) -> tuple[str, bytes]:
    status = str(detail.get("status") or "连载")
    title, author = (
        str(detail.get("title") or f"连城小说{book_id}"),
        str(detail.get("author") or "未知"),
    )
    lines = [
        连城声明,
        "",
        f"名称：{title}",
        f"作者：{author}",
        f"状态：{status}",
        f"字数：{_字数(detail.get('word_count'))}",
        f"书籍ID：{book_id}",
        f"章节数：{len(chapters)}",
        "",
    ]
    if detail.get("intro"):
        lines.extend(["简介：", str(detail["intro"]), ""])
    for chapter, content in zip(chapters, contents):
        heading = chapter.get("title") or "章节"
        lines.extend([heading, "", 去除章节正文重复标题(heading, content), ""])
    filename = f"[{status}]书名：{_文件名(title)} 作者：{_文件名(author)}.txt"
    text = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n")
    return filename, text.replace("\n", "\r\n").encode("utf-8")


def _缓存(filename: str, content: bytes) -> Path:
    连城缓存目录.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = 连城缓存目录 / (
            Path(filename).name if index == 0 else f"{Path(filename).stem}_{index}.txt"
        )
        if not path.exists():
            path.write_bytes(content)
            文件缓存工具.标记小说缓存正在使用(path)
            return path
    raise RuntimeError("缓存文件名冲突")


async def _发送(
    event: Any, filename: str, content: bytes, config: Any, title: str, author: str
) -> dict[str, Any]:
    path = _缓存(filename, content)
    if 小说网盘 is None:
        文件缓存工具.删除小说缓存文件(path)
        return {"sent": False, "source_cache_path": None}
    try:
        uploaded = await 小说网盘.上传小说并获取分享链接(config, path, filename)
        if not uploaded.get("success"):
            文件缓存工具.删除小说缓存文件(path)
            return {"sent": False, "source_cache_path": None}
        sent = await 小说网盘.发送小说下载结果(
            event, title, author, uploaded
        )
        return {
            "sent": bool(sent.get("sent")),
            "fallback_text": str(sent.get("fallback_text") or ""),
            "source_cache_path": path,
        }
    except Exception as exc:
        logger.warning("连城小说文件发送失败：错误类型=%s", type(exc).__name__)
        文件缓存工具.删除小说缓存文件(path)
        return {"sent": False, "source_cache_path": None}


def _后台(config: Any, path: Any, filename: str) -> None:
    if not path:
        return

    async def task() -> None:
        try:
            if 百度网盘 is not None:
                await 百度网盘.后台上传小说文件(config, path, filename)
        except Exception as exc:
            logger.warning("连城小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            文件缓存工具.删除小说缓存文件(path)

    try:
        asyncio.create_task(task())
    except RuntimeError:
        文件缓存工具.删除小说缓存文件(path)


async def 生成连城下载回复流(
    event: Any, source: str, config: Any = None
) -> AsyncIterator[Any]:
    book_id = 解析连城书籍编号(source)
    if not book_id:
        yield "下载失败 请重试"
        return
    try:
        async with 创建连城HTTP会话() as session:
            detail, chapters = await 获取连城详情(session, book_id)
            if not detail or not chapters:
                yield "下载失败 请重试"
                return
            logger.info(
                "连城小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s, 会话复用=开启, 解密方式=DES",
                book_id,
                len(chapters),
                连城并发数,
            )
            yield f"书名：{detail.get('title') or '未知'}\n作者：{detail.get('author') or '未知'}\n状态：{detail.get('status') or '连载'}\n章节：{len(chapters)} 章\n字数：{_字数(detail.get('word_count'))}\n\n正在下载中请稍等....."
            contents = await 下载连城正文(session, book_id, chapters)
        if any(not content for content in contents):
            logger.warning(
                "连城小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s",
                book_id,
                sum(bool(x) for x in contents),
                len(chapters),
            )
            yield "下载失败 请重试"
            return
        filename, content = 生成连城文件(book_id, detail, chapters, contents)
        result = await _发送(
            event,
            filename,
            content,
            config,
            str(detail.get("title") or "未知"),
            str(detail.get("author") or "未知"),
        )
        path = result.get("source_cache_path")
        if result.get("sent"):
            _后台(config, path, filename)
        elif result.get("fallback_text"):
            yield result["fallback_text"]
            _后台(config, path, filename)
        else:
            yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(
            "连城小说下载失败：错误类型=%s, category=%s, http_status=%s, code=%s",
            type(exc).__name__, getattr(exc, "category", "unknown"),
            getattr(exc, "http_status", None), getattr(exc, "code", None),
        )
        yield "下载失败 请重试"


def 获取连城小说回复流(
    event: Any, command: str, config: Any = None
) -> AsyncIterator[Any] | None:
    source = 提取连城来源(event, command)
    return 生成连城下载回复流(event, source, config) if source else None


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    async with 创建连城HTTP会话(4) as session:
        data = await _请求(
            session, "/app/query/keybooks", {"deviceID": "", "kw": keyword, "pn": "0"}
        )
    body = data.get("DATA")
    rows = body.get("KEYLIST") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise _连城请求错误("invalid_search")
    result = []
    for item in rows:
        if not isinstance(item, dict):
            raise _连城请求错误("invalid_search")
        book_id, title = str(item.get("KEYID") or ""), _文本(item.get("KEYNAME"))
        if not book_id.isascii() or not book_id.isdigit() or not title:
            raise _连城请求错误("invalid_search")
        result.append(
            {
                "_search_status": {key: item[key] for key in ("STATE",) if key in item},
                "book_id": book_id,
                "title": title,
                "author": _文本(item.get("AUTHORNAME") or "未知"),
                "url": 构造连城链接(book_id),
                "intro": _文本(item.get("CONTENT")),
                "score": 0,
                "heat": 0,
                "word_count": item.get("WORDNUM") or 0,
            }
        )
    return result[: max(1, min(30, int(需要数量 or 20)))]
