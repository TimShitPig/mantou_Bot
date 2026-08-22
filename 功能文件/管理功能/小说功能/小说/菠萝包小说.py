"""菠萝包小说独立异步详情、目录和正文下载链路。"""

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

菠萝包搜索地址 = "https://m.sfacg.com/API/HTML5.ashx"
菠萝包API地址 = "https://minipapi.sfacg.com/pas/mpapi"
菠萝包域名 = {"sfacg.com", "www.sfacg.com", "m.sfacg.com", "minipapi.sfacg.com"}
菠萝包链接正则 = re.compile(
    r"https?://(?:[^\s/<>\"']*\.)?(?:sfacg\.com)[^\s<>\"']*",
    re.IGNORECASE,
)
菠萝包并发数 = 80
菠萝包重试次数 = 3
菠萝包缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
菠萝包声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
)
菠萝包请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "sf-minip-info": "minip_novel/1.0.70(android;10)/wxmp",
    "authorization": "Basic YW5kcm9pZHVzZXI6MWEjJDUxLXl0Njk7KkFjdkBxeHE=",
}


def _文本(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return re.sub(
        r"\n{3,}", "\n\n", text.replace("\r\n", "\n").replace("\r", "\n")
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
    ident = id(value)
    if ident in seen:
        return
    seen.add(ident)
    for field in ("message_str", "message", "raw_message", "text", "content", "data"):
        try:
            _收集(getattr(value, field, None), output, seen, depth + 1)
        except Exception:
            pass


def 提取菠萝包来源(event: Any, command: Any) -> str | None:
    values: list[str] = []
    _收集(command, values, set())
    _收集(event, values, set())
    for value in values:
        match = 菠萝包链接正则.search(urllib.parse.unquote(value))
        if match:
            return match.group(0).rstrip("'\"，。；;]}>）)")
    for value in values:
        if "sfacg" not in value.lower() and "菠萝包" not in value:
            continue
        match = re.search(
            r"(?:novel[_-]?id|book[_-]?id|novelid|bookid|novel)\D{0,8}(\d{4,})",
            value,
            re.I,
        )
        if match:
            return 构造菠萝包链接(match.group(1))
    return None


def 解析菠萝包书籍编号(source: str) -> str:
    text = urllib.parse.unquote(str(source or ""))
    try:
        parsed = urllib.parse.urlsplit(text)
        host = (parsed.hostname or "").lower()
        if host and host not in 菠萝包域名:
            return ""
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        for key in ("novelid", "novel_id", "bookid", "book_id", "id"):
            for value in query.get(key, []):
                if re.fullmatch(r"\d{4,}", str(value)):
                    return str(value)
        match = re.search(
            r"(?:novel|book|detail|read|/b/)[^0-9]{0,20}(\d{4,})", parsed.path, re.I
        )
        if match:
            return match.group(1)
    except Exception:
        pass
    match = re.search(
        r"(?:novel[_-]?id|book[_-]?id|novel|book)\D{0,8}(\d{4,})", text, re.I
    )
    return match.group(1) if match else ""


def 构造菠萝包链接(book_id: Any) -> str:
    return f"https://m.sfacg.com/Novel/{str(book_id).strip()}/"


def 创建菠萝包HTTP会话(concurrency: int = 菠萝包并发数) -> aiohttp.ClientSession:
    concurrency = max(1, int(concurrency or 1))
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    connector = aiohttp.TCPConnector(
        limit=concurrency, limit_per_host=concurrency, ttl_dns_cache=300
    )
    return aiohttp.ClientSession(
        headers=菠萝包请求头, timeout=timeout, connector=connector
    )


async def _请求(
    session: aiohttp.ClientSession, url: str, *, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(菠萝包重试次数):
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
            return data if isinstance(data, dict) else {}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < 菠萝包重试次数:
                await asyncio.sleep(0.2 * (attempt + 1))
    raise RuntimeError("菠萝包接口请求失败") from last


def _接口成功(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    status = data.get("status")
    if isinstance(status, dict):
        return str(status.get("httpCode") or status.get("code") or "") == "200"
    return data.get("Status") in (200, "200")


async def 获取菠萝包目录(
    session: aiohttp.ClientSession, book_id: str
) -> list[dict[str, str]]:
    data = await _请求(
        session, f"{菠萝包API地址}/novels/{urllib.parse.quote(book_id)}/dirs"
    )
    if not _接口成功(data):
        return []
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    chapters: list[dict[str, str]] = []
    for volume in (
        payload.get("volumeList") if isinstance(payload.get("volumeList"), list) else []
    ):
        if not isinstance(volume, dict):
            continue
        for chapter in (
            volume.get("chapterList")
            if isinstance(volume.get("chapterList"), list)
            else []
        ):
            if not isinstance(chapter, dict):
                continue
            chapter_id = str(chapter.get("chapId") or "").strip()
            title = _文本(chapter.get("title") or "章节")
            if chapter_id and title:
                chapters.append({"id": chapter_id, "title": title})
    return chapters


async def 获取菠萝包详情(
    session: aiohttp.ClientSession, book_id: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    expand = "latestchapter,chapterCount,typeName,intro,fav,ticket,pointCount,tags,sysTags,signlevel,discount,discountExpireDate,totalNeedFireMoney,originTotalNeedFireMoney"
    data = await _请求(
        session,
        f"{菠萝包API地址}/novels/{urllib.parse.quote(book_id)}",
        params={"expand": expand},
    )
    if not _接口成功(data):
        return {}, []
    info = data.get("data") if isinstance(data.get("data"), dict) else {}
    title = _文本(info.get("novelName"))
    if not title:
        return {}, []
    chapters = await 获取菠萝包目录(session, book_id)
    expand_info = info.get("expand") if isinstance(info.get("expand"), dict) else {}
    status_value = info.get("novelStatus") or info.get("status") or info.get("state")
    status = (
        "完结"
        if str(status_value).lower() in {"1", "2", "finish", "finished", "完结"}
        else "连载"
    )
    return {
        "title": title,
        "author": _文本(info.get("authorName") or "未知"),
        "intro": _文本(expand_info.get("intro") or info.get("intro")),
        "status": status,
        "word_count": info.get("charCount") or info.get("wordCount") or info.get("words") or 0,
    }, chapters


async def _下载章节(
    session: aiohttp.ClientSession, chapter: dict[str, str], sem: asyncio.Semaphore
) -> str:
    async with sem:
        for attempt in range(菠萝包重试次数):
            try:
                data = await _请求(
                    session,
                    f"{菠萝包API地址}/Chaps/{urllib.parse.quote(chapter['id'])}",
                    params={
                        "expand": "content,needFireMoney,originNeedFireMoney,tsukkomi",
                        "autoOrder": "false",
                    },
                )
                if not _接口成功(data):
                    raise RuntimeError("正文业务失败")
                node = data.get("data") if isinstance(data.get("data"), dict) else {}
                expand = (
                    node.get("expand") if isinstance(node.get("expand"), dict) else {}
                )
                content = _文本(expand.get("content") or node.get("content"))
                if content:
                    return content
                raise RuntimeError("正文为空")
            except Exception as exc:
                logger.debug(
                    "菠萝包小说章节获取失败：章节=%s, 错误类型=%s",
                    chapter.get("id"),
                    type(exc).__name__,
                )
                if attempt + 1 < 菠萝包重试次数:
                    await asyncio.sleep(0.2 * (attempt + 1))
    return ""


async def 下载菠萝包正文(
    session: aiohttp.ClientSession, chapters: list[dict[str, str]]
) -> list[str]:
    results = [""] * len(chapters)
    sem = asyncio.Semaphore(max(1, min(菠萝包并发数, len(chapters) or 1)))
    done = 0
    next_log = max(1, len(chapters) // 10)
    lock = asyncio.Lock()

    async def one(index: int, chapter: dict[str, str]) -> None:
        nonlocal done, next_log
        results[index] = await _下载章节(session, chapter, sem)
        async with lock:
            done += 1
            if done >= next_log or done == len(chapters):
                success = sum(bool(item) for item in results)
                logger.info(
                    "菠萝包小说章节进度：进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s, 并发数=%s, 会话复用=开启, 解密方式=无需解密",
                    done,
                    len(chapters),
                    int(done * 100 / max(1, len(chapters))),
                    success,
                    done - success,
                    菠萝包并发数,
                )
                next_log += max(1, len(chapters) // 10)

    await asyncio.gather(
        *(one(index, chapter) for index, chapter in enumerate(chapters))
    )
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
        or "菠萝包小说"
    )


def 生成菠萝包文件(
    book_id: str,
    detail: dict[str, Any],
    chapters: list[dict[str, str]],
    contents: list[str],
) -> tuple[str, bytes]:
    status = str(detail.get("status") or "连载")
    title = str(detail.get("title") or f"菠萝包小说{book_id}")
    author = str(detail.get("author") or "未知")
    lines = [
        菠萝包声明,
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
    菠萝包缓存目录.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = 菠萝包缓存目录 / (
            Path(filename).name if index == 0 else f"{Path(filename).stem}_{index}.txt"
        )
        if not path.exists():
            path.write_bytes(content)
            小说缓存工具.标记下载缓存正在使用(path)
            return path
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
        logger.warning("菠萝包小说文件发送失败：错误类型=%s", type(exc).__name__)
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
            logger.warning(
                "菠萝包小说百度后台备份异常：错误类型=%s", type(exc).__name__
            )
        finally:
            小说缓存工具.删除下载缓存文件(path)

    try:
        asyncio.create_task(task())
    except RuntimeError:
        小说缓存工具.删除下载缓存文件(path)


async def 生成菠萝包下载回复流(
    event: Any, source: str, config: Any = None
) -> AsyncIterator[Any]:
    book_id = 解析菠萝包书籍编号(source)
    if not book_id:
        yield "下载失败"
        return
    try:
        async with 创建菠萝包HTTP会话() as session:
            detail, chapters = await 获取菠萝包详情(session, book_id)
            if not detail or not chapters:
                yield "下载失败"
                return
            logger.info(
                "菠萝包小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s, 会话复用=开启, 解密方式=无需解密",
                book_id,
                len(chapters),
                菠萝包并发数,
            )
            yield f"书名：{detail.get('title') or '未知'}\n作者：{detail.get('author') or '未知'}\n状态：{detail.get('status') or '连载'}\n章节：{len(chapters)} 章\n字数：{_字数(detail.get('word_count'))}\n\n正在下载中请稍等....."
            contents = await 下载菠萝包正文(session, chapters)
        if any(not content for content in contents):
            logger.warning(
                "菠萝包小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s",
                book_id,
                sum(bool(x) for x in contents),
                len(chapters),
            )
            yield "下载失败"
            return
        filename, content = 生成菠萝包文件(book_id, detail, chapters, contents)
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
        logger.warning("菠萝包小说下载失败：错误类型=%s", type(exc).__name__)
        yield "下载失败"


def 获取菠萝包小说回复流(
    event: Any, command: str, config: Any = None
) -> AsyncIterator[Any] | None:
    source = 提取菠萝包来源(event, command)
    return 生成菠萝包下载回复流(event, source, config) if source else None


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    try:
        async with 创建菠萝包HTTP会话(4) as session:
            data = await _请求(
                session,
                菠萝包搜索地址,
                params={"op": "search", "keyword": keyword, "page": 1},
            )
        if data.get("Status") not in (200, "200"):
            return []
        rows = data.get("Novels") if isinstance(data.get("Novels"), list) else []
        result = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            book_id = str(item.get("NovelID") or "").strip()
            title = _文本(item.get("NovelName"))
            if not book_id.isdigit() or not title:
                continue
            result.append(
                {
                    "book_id": book_id,
                    "title": title,
                    "author": _文本(item.get("AuthorName") or "未知"),
                    "url": 构造菠萝包链接(book_id),
                    "intro": _文本(item.get("TypeName")),
                    "score": 0,
                    "heat": 0,
                    "word_count": 0,
                }
            )
        return result[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as exc:
        logger.debug("菠萝包小说搜索失败：错误类型=%s", type(exc).__name__)
        return []
