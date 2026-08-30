"""米读小说独立异步下载模块。"""

from __future__ import annotations

import asyncio
import html
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)
try:
    from 功能文件.管理功能.网盘功能 import 小说网盘, 百度网盘
except Exception:
    百度网盘 = 小说网盘 = None
from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

米读API = "https://api.midureader.com"
米读CDN = "https://book.midureader.com"
米读域名 = {
    "midureader.com",
    "www.midureader.com",
    "api.midureader.com",
    "book.midureader.com",
}
米读链接正则 = re.compile(
    r"https?://(?:[^\s/<>\"']*\.)?midureader\.com[^\s<>\"']*", re.I
)
米读并发数 = 80
米读重试次数 = 3
米读缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
米读声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


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


def 提取米读来源(event: Any, command: Any) -> str | None:
    values: list[str] = []
    _收集(command, values, set())
    _收集(event, values, set())
    for value in values:
        match = 米读链接正则.search(urllib.parse.unquote(value))
        if match:
            return match.group(0).rstrip("'\"，。；;]}>）)")
    for value in values:
        if "米读" in value or "midureader" in value.lower():
            match = re.search(
                r"(?:book[_-]?id|bookId|novelId)\D{0,8}([A-Za-z0-9_-]{8,128})",
                value,
                re.I,
            )
            if match:
                return 构造米读链接(match.group(1))
    return None


def 解析米读书籍编号(source: str) -> str:
    text = urllib.parse.unquote(str(source or ""))
    try:
        parsed = urllib.parse.urlsplit(text)
        query = urllib.parse.parse_qs(parsed.query)
        for key in ("book_id", "bookId", "id"):
            if query.get(key):
                value = str(query[key][0])
                if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
                    return value
    except Exception:
        pass
    match = re.search(
        r"(?:book|detail|fiction)[^A-Za-z0-9_-]{0,10}([A-Za-z0-9_-]{8,128})", text, re.I
    )
    return match.group(1) if match else ""


def 构造米读链接(book_id: Any) -> str:
    return f"https://book.midureader.com/book/{urllib.parse.quote(str(book_id or ''))}"


def 创建米读HTTP会话(concurrency: int = 米读并发数) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    connector = aiohttp.TCPConnector(
        limit=max(1, int(concurrency)),
        limit_per_host=max(1, int(concurrency)),
        ttl_dns_cache=300,
    )
    return aiohttp.ClientSession(
        headers={
            "User-Agent": "okhttp/3.12.1",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=timeout,
        connector=connector,
    )


async def _请求(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
    json_response: bool = True,
) -> Any:
    last: Exception | None = None
    for attempt in range(米读重试次数):
        try:
            async with session.request(method, url, data=data) as response:
                response.raise_for_status()
                body = await response.read()
            if not json_response:
                return body
            return json.loads(body.decode("utf-8-sig", "replace"))
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < 米读重试次数:
                await asyncio.sleep(0.2 * (attempt + 1))
    raise RuntimeError("米读接口请求失败") from last


def _成功(data: Any) -> bool:
    return isinstance(data, dict) and str(data.get("code", "0")) in {"0", "200"}


async def 获取米读详情(
    session: aiohttp.ClientSession, book_id: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    detail_data = await _请求(
        session,
        "POST",
        f"{米读API}/fiction/book/getDetail",
        data={"app": "midu", "book_id": book_id, "source": "midu", "token": ""},
    )
    if not _成功(detail_data):
        return {}, []
    raw = detail_data.get("data") if isinstance(detail_data.get("data"), dict) else {}
    catalog_raw = await _请求(
        session,
        "GET",
        f"{米读CDN}/book/chapter_list/100/{urllib.parse.quote(book_id)}.txt",
        json_response=False,
    )
    try:
        catalog_data = json.loads(
            catalog_raw.decode("utf-8-sig", "replace").lstrip("\ufeff")
        )
    except Exception:
        catalog_data = []
    chapters: list[dict[str, str]] = []
    if isinstance(catalog_data, list):
        for item in catalog_data:
            if not isinstance(item, dict):
                continue
            chapter_id = str(item.get("chapterId") or "")
            md5 = str(item.get("content_md5") or "")
            if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", chapter_id) and re.fullmatch(
                r"[A-Fa-f0-9]{16,128}", md5
            ):
                chapters.append(
                    {
                        "id": f"{chapter_id}/{md5}",
                        "title": _文本(item.get("title") or f"第{len(chapters) + 1}章"),
                    }
                )
    detail = {
        "title": _文本(raw.get("title") or raw.get("bookName")),
        "author": _文本(raw.get("author") or "未知"),
        "intro": _文本(raw.get("description")),
        "status": "完结"
        if str(raw.get("status") or "").lower() in {"1", "finish", "完结"}
        else "连载",
        "word_count": raw.get("wordCount") or raw.get("words") or 0,
    }
    return detail, chapters


async def _下载章节(
    session: aiohttp.ClientSession,
    book_id: str,
    chapter: dict[str, str],
    sem: asyncio.Semaphore,
) -> str:
    chapter_id, md5 = chapter["id"].split("/", 1)
    url = f"{米读CDN}/book/chapter/segment/master/{urllib.parse.quote(book_id)}/{urllib.parse.quote(chapter_id)}/{urllib.parse.quote(md5)}.txt"
    async with sem:
        for attempt in range(米读重试次数):
            try:
                data = await _请求(session, "GET", url)
                values = (
                    data.get("data")
                    if isinstance(data, dict) and isinstance(data.get("data"), list)
                    else data
                )
                lines = []
                if isinstance(values, list):
                    lines.extend(
                        _文本(item.get("content"))
                        for item in values
                        if isinstance(item, dict) and "content" in item
                    )
                content = "\n".join(item for item in lines if item).strip()
                if content:
                    return content
                raise RuntimeError("正文为空")
            except Exception as exc:
                logger.debug(
                    "米读小说章节获取失败：章节=%s, 错误类型=%s",
                    chapter.get("id"),
                    type(exc).__name__,
                )
                if attempt + 1 < 米读重试次数:
                    await asyncio.sleep(0.2 * (attempt + 1))
    return ""


async def 下载米读正文(
    session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]
) -> list[str]:
    results = [""] * len(chapters)
    sem = asyncio.Semaphore(max(1, min(米读并发数, len(chapters) or 1)))
    done = 0
    next_log = max(1, len(chapters) // 10)
    lock = asyncio.Lock()

    async def one(index: int, chapter: dict[str, str]) -> None:
        nonlocal done, next_log
        results[index] = await _下载章节(session, book_id, chapter, sem)
        async with lock:
            done += 1
            if done >= next_log or done == len(chapters):
                success = sum(bool(item) for item in results)
                logger.info(
                    "米读小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s, 并发数=%s, 会话复用=开启, 解密方式=无需解密",
                    book_id,
                    done,
                    len(chapters),
                    int(done * 100 / max(1, len(chapters))),
                    success,
                    done - success,
                    米读并发数,
                )
                next_log += max(1, len(chapters) // 10)

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
        or "米读小说"
    )


def 生成米读文件(
    book_id: str,
    detail: dict[str, Any],
    chapters: list[dict[str, str]],
    contents: list[str],
) -> tuple[str, bytes]:
    status = str(detail.get("status") or "连载")
    title, author = (
        str(detail.get("title") or f"米读小说{book_id}"),
        str(detail.get("author") or "未知"),
    )
    lines = [
        米读声明,
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
    米读缓存目录.mkdir(parents=True, exist_ok=True)
    path = 米读缓存目录 / Path(filename).name
    for index in range(1000):
        candidate = (
            path if index == 0 else 米读缓存目录 / f"{Path(filename).stem}_{index}.txt"
        )
        if not candidate.exists():
            candidate.write_bytes(content)
            小说缓存工具.标记下载缓存正在使用(candidate)
            return candidate
    raise RuntimeError("缓存文件名冲突")


async def _发送(
    event: Any, filename: str, content: bytes, config: Any, title: str, author: str
) -> dict[str, Any]:
    path = _缓存(filename, content)
    if 小说网盘 is None:
        小说缓存工具.删除下载缓存文件(path)
        return {"sent": False, "source_cache_path": None}
    try:
        uploaded = await 小说网盘.上传小说并获取分享链接(config, path, filename)
        if not uploaded.get("success"):
            小说缓存工具.删除下载缓存文件(path)
            return {"sent": False, "source_cache_path": None}
        sent = await 小说网盘.发送小说下载完成链接(
            event, title, author, str(uploaded.get("share_url") or "")
        )
        return {
            "sent": bool(sent.get("sent")),
            "fallback_text": str(sent.get("fallback_text") or ""),
            "source_cache_path": path,
        }
    except Exception as exc:
        logger.warning("米读小说文件发送失败：错误类型=%s", type(exc).__name__)
        小说缓存工具.删除下载缓存文件(path)
        return {"sent": False, "source_cache_path": None}


def _后台(config: Any, path: Any, filename: str) -> None:
    if not path:
        return

    async def task() -> None:
        try:
            if 百度网盘 is not None:
                await 百度网盘.后台上传小说文件(config, path, filename)
        except Exception as exc:
            logger.warning("米读小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            小说缓存工具.删除下载缓存文件(path)

    try:
        asyncio.create_task(task())
    except RuntimeError:
        小说缓存工具.删除下载缓存文件(path)


async def 生成米读下载回复流(
    event: Any, source: str, config: Any = None
) -> AsyncIterator[Any]:
    book_id = 解析米读书籍编号(source)
    if not book_id:
        yield "下载失败 请重试"
        return
    try:
        async with 创建米读HTTP会话() as session:
            detail, chapters = await 获取米读详情(session, book_id)
            if not detail or not chapters:
                yield "下载失败 请重试"
                return
            logger.info(
                "米读小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s, 会话复用=开启, 解密方式=无需解密",
                book_id,
                len(chapters),
                米读并发数,
            )
            yield f"书名：{detail.get('title') or '未知'}\n作者：{detail.get('author') or '未知'}\n状态：{detail.get('status') or '连载'}\n章节：{len(chapters)} 章\n字数：{_字数(detail.get('word_count'))}\n\n正在下载中请稍等....."
            contents = await 下载米读正文(session, book_id, chapters)
        if any(not content for content in contents):
            logger.warning(
                "米读小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s",
                book_id,
                sum(bool(x) for x in contents),
                len(chapters),
            )
            yield "下载失败 请重试"
            return
        filename, content = 生成米读文件(book_id, detail, chapters, contents)
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
        logger.warning("米读小说下载失败：错误类型=%s", type(exc).__name__)
        yield "下载失败 请重试"


def 获取米读小说回复流(
    event: Any, command: str, config: Any = None
) -> AsyncIterator[Any] | None:
    source = 提取米读来源(event, command)
    return 生成米读下载回复流(event, source, config) if source else None


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    try:
        async with 创建米读HTTP会话(4) as session:
            data = await _请求(
                session,
                "POST",
                f"{米读API}/fiction/search/searchV2",
                data={"app": "midu", "keyword": keyword, "page": 0},
            )
        rows = (
            data.get("data")
            if isinstance(data, dict) and isinstance(data.get("data"), list)
            else []
        )
        result = []
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get("bookData"), dict):
                continue
            book = item["bookData"]
            book_id = str(book.get("book_id") or book.get("bookId") or "")
            title = _文本(book.get("title") or book.get("bookName"))
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", book_id) or not title:
                continue
            result.append(
                {
                    "book_id": book_id,
                    "title": title,
                    "author": _文本(
                        item.get("emAuthor") or book.get("author") or "未知"
                    ),
                    "url": 构造米读链接(book_id),
                    "intro": _文本(book.get("description")),
                    "score": 0,
                    "heat": 0,
                }
            )
        return result[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as exc:
        logger.debug("米读小说搜索失败：错误类型=%s", type(exc).__name__)
        return []
