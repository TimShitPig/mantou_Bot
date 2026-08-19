"""猫眼/掌阅小说独立异步下载模块。"""
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
    from 功能文件.管理功能.网盘功能 import 百度网盘, 小说网盘
except Exception:
    百度网盘 = 小说网盘 = None
from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

猫眼搜索地址 = "https://ah2.zhangyue.com/zybook3/u/p/api.php"
猫眼详情地址 = "https://ah2.zhangyue.com/zybk/api/detail/index"
猫眼目录地址 = "https://cpt.zhangyue.com/zybook/u/p/api.php"
猫眼正文地址 = "https://m.zhangyue.com/nextchapter"
猫眼公共参数 = {"pc": "10", "p1": "275000", "p2": "275000", "p3": "17410354", "p4": "501654", "p25": "74103", "p29": "zya9cec4", "p33": "com.syhzx.htsw", "usr": "", "rgt": "0"}
猫眼域名 = {"zhangyue.com", "www.zhangyue.com", "ireader.com", "m.ireader.com"}
猫眼链接正则 = re.compile(r"https?://(?:[^\s/<>\"']*\.)?(?:zhangyue\.com|ireader\.com)[^\s<>\"']*", re.I)
猫眼并发数 = 80
猫眼重试次数 = 3
猫眼缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
猫眼声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


def _文本(value: Any) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", html.unescape(re.sub(r"<[^>]+>", "", str(value or "")))).strip()


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


def 提取猫眼来源(event: Any, command: Any) -> str | None:
    values: list[str] = []
    _收集(command, values, set())
    _收集(event, values, set())
    for value in values:
        match = 猫眼链接正则.search(urllib.parse.unquote(value))
        if match:
            return match.group(0).rstrip("'\"，。；;]}>）)")
    for value in values:
        if "猫眼" not in value and "zhangyue" not in value.lower() and "ireader" not in value.lower():
            continue
        match = re.search(r"(?:bid|book[_-]?id|bookId)\D{0,8}(\d{4,})", value, re.I)
        if match:
            return 构造猫眼链接(match.group(1))
    return None


def 解析猫眼书籍编号(source: str) -> str:
    text = urllib.parse.unquote(str(source or ""))
    try:
        parsed = urllib.parse.urlsplit(text)
        query = urllib.parse.parse_qs(parsed.query)
        for key in ("bid", "book_id", "bookId", "id"):
            if query.get(key) and str(query[key][0]).isdigit():
                return str(query[key][0])
    except Exception:
        pass
    match = re.search(r"(?:book|detail|reader)[^0-9]{0,15}(\d{4,})", text, re.I)
    return match.group(1) if match else ""


def 构造猫眼链接(book_id: Any) -> str:
    return f"https://m.zhangyue.com/book/{book_id}"


def 创建猫眼HTTP会话(concurrency: int = 猫眼并发数) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    connector = aiohttp.TCPConnector(limit=max(1, int(concurrency)), limit_per_host=max(1, int(concurrency)), ttl_dns_cache=300)
    return aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 MaoyanReader/2.4.0", "Accept": "application/json, text/plain, */*"}, timeout=timeout, connector=connector)


async def _请求(session: aiohttp.ClientSession, url: str, *, params: dict[str, Any] | None = None, accept: str = "application/json") -> tuple[bytes, dict[str, Any] | None]:
    last: Exception | None = None
    merged = dict(猫眼公共参数)
    if params:
        merged.update(params)
    for attempt in range(猫眼重试次数):
        try:
            async with session.get(url, params=merged, headers={"Accept": accept}) as response:
                response.raise_for_status()
                body = await response.read()
            if "xml" in accept:
                return body, None
            try:
                data = json.loads(body.decode("utf-8-sig", "replace"))
            except Exception:
                data = None
            return body, data if isinstance(data, dict) else None
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last = exc
            if attempt + 1 < 猫眼重试次数:
                await asyncio.sleep(0.2 * (attempt + 1))
    raise RuntimeError("猫眼接口请求失败") from last


def _章节XML(body: bytes) -> list[dict[str, str]]:
    text = body.decode("utf-8", "replace")
    result: list[dict[str, str]] = []
    for chunk in re.findall(r"<cp\b[^>]*>(.*?)</cp>", text, re.I | re.S):
        def value(name: str) -> str:
            match = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", chunk, re.I | re.S)
            return _文本(html.unescape(match.group(1))) if match else ""
        chapter_id = value("id")
        title = value("cn")
        if chapter_id.isdigit() and title:
            result.append({"id": chapter_id, "title": title})
    return result


async def 获取猫眼详情(session: aiohttp.ClientSession, book_id: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    _, detail = await _请求(session, 猫眼详情地址, params={"bid": book_id, "source": "read"})
    if not isinstance(detail, dict) or str(detail.get("code", "0")) not in {"0", "200"}:
        return {}, []
    body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
    info = body.get("bookInfo") if isinstance(body.get("bookInfo"), dict) else {}
    raw, _ = await _请求(session, 猫眼目录地址, params={"Act": "getChapterListVersion", "dt": "xml", "bid": book_id, "sid": "1", "vs": "0"}, accept="application/xml, text/xml, */*")
    chapters = _章节XML(raw)
    result = {"title": _文本(info.get("bookName")), "author": _文本(info.get("author") or "未知"), "intro": _文本(info.get("desc")), "status": "完结" if str(info.get("status") or "").lower() in {"1", "finish", "完结"} else "连载", "word_count": info.get("wordCount") or 0}
    return result, chapters


def _正文文本(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<!--.*?-->|<(script|style|noscript)\b[^>]*>.*?</\1>", "", text, flags=re.I | re.S)
    text = re.sub(r"<\/?(?:br|p|div|h[1-6]|li|section|article|blockquote|tr|td)[^>]*>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [re.sub(r"[ \t\f\v]+", " ", item).strip() for item in re.split(r"\n+", text.replace("\r", "\n"))]
    return "\n".join(item for item in lines if item).strip()


async def _下载章节(session: aiohttp.ClientSession, book_id: str, chapter: dict[str, str], sem: asyncio.Semaphore) -> str:
    async with sem:
        for attempt in range(猫眼重试次数):
            try:
                _, data = await _请求(session, f"{猫眼正文地址}/{urllib.parse.quote(book_id)}/{urllib.parse.quote(chapter['id'])}")
                if not isinstance(data, dict) or str(data.get("code", "0")) not in {"0", "200"}:
                    raise RuntimeError("正文业务失败")
                content = _正文文本(data.get("html"))
                if content:
                    return content
                raise RuntimeError("正文为空")
            except Exception as exc:
                logger.debug("猫眼小说章节获取失败：章节=%s, 错误类型=%s", chapter.get("id"), type(exc).__name__)
                if attempt + 1 < 猫眼重试次数:
                    await asyncio.sleep(0.2 * (attempt + 1))
    return ""


async def 下载猫眼正文(session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]) -> list[str]:
    results = [""] * len(chapters)
    sem = asyncio.Semaphore(max(1, min(猫眼并发数, len(chapters) or 1)))
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
                logger.info("猫眼小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s, 并发数=%s, 会话复用=开启, 解密方式=无需解密", book_id, done, len(chapters), int(done * 100 / max(1, len(chapters))), success, done - success, 猫眼并发数)
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
    return re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "未知")).strip(" .")[:80] or "猫眼小说"


def 生成猫眼文件(book_id: str, detail: dict[str, Any], chapters: list[dict[str, str]], contents: list[str]) -> tuple[str, bytes]:
    status = str(detail.get("status") or "连载")
    title, author = str(detail.get("title") or f"猫眼小说{book_id}"), str(detail.get("author") or "未知")
    lines = [猫眼声明, "", f"名称：{title}", f"作者：{author}", f"状态：{status}", f"字数：{_字数(detail.get('word_count'))}", f"书籍ID：{book_id}", f"章节数：{len(chapters)}", ""]
    if detail.get("intro"):
        lines.extend(["简介：", str(detail["intro"]), ""])
    for chapter, content in zip(chapters, contents):
        heading = chapter.get("title") or "章节"
        lines.extend([heading, "", 去除章节正文重复标题(heading, content), ""])
    filename = f"[{status}]书名：{_文件名(title)} 作者：{_文件名(author)}.txt"
    text = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n")
    return filename, text.replace("\n", "\r\n").encode("utf-8")


def _缓存(filename: str, content: bytes) -> Path:
    猫眼缓存目录.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = 猫眼缓存目录 / (Path(filename).name if index == 0 else f"{Path(filename).stem}_{index}.txt")
        if not path.exists():
            path.write_bytes(content)
            小说缓存工具.标记下载缓存正在使用(path)
            return path
    raise RuntimeError("缓存文件名冲突")


async def _发送(event: Any, filename: str, content: bytes, config: Any, title: str, author: str) -> dict[str, Any]:
    path = _缓存(filename, content)
    if 小说网盘 is None:
        小说缓存工具.删除下载缓存文件(path)
        return {"sent": False, "source_cache_path": None}
    try:
        uploaded = await 小说网盘.上传小说并获取分享链接(config, path, filename)
        if not uploaded.get("success"):
            小说缓存工具.删除下载缓存文件(path)
            return {"sent": False, "source_cache_path": None}
        sent = await 小说网盘.发送小说下载完成链接(event, title, author, str(uploaded.get("share_url") or ""))
        return {"sent": bool(sent.get("sent")), "fallback_text": str(sent.get("fallback_text") or ""), "source_cache_path": path}
    except Exception as exc:
        logger.warning("猫眼小说文件发送失败：错误类型=%s", type(exc).__name__)
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
            logger.warning("猫眼小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            小说缓存工具.删除下载缓存文件(path)
    try:
        asyncio.create_task(task())
    except RuntimeError:
        小说缓存工具.删除下载缓存文件(path)


async def 生成猫眼下载回复流(event: Any, source: str, config: Any = None) -> AsyncIterator[Any]:
    book_id = 解析猫眼书籍编号(source)
    if not book_id:
        yield "下载失败"
        return
    try:
        async with 创建猫眼HTTP会话() as session:
            detail, chapters = await 获取猫眼详情(session, book_id)
            if not detail or not chapters:
                yield "下载失败"
                return
            logger.info("猫眼小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s, 会话复用=开启, 解密方式=无需解密", book_id, len(chapters), 猫眼并发数)
            yield f"书名：{detail.get('title') or '未知'}\n作者：{detail.get('author') or '未知'}\n状态：{detail.get('status') or '连载'}\n章节：{len(chapters)} 章\n字数：{_字数(detail.get('word_count'))}\n\n正在下载中请稍等....."
            contents = await 下载猫眼正文(session, book_id, chapters)
        if any(not content for content in contents):
            logger.warning("猫眼小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s", book_id, sum(bool(x) for x in contents), len(chapters))
            yield "下载失败"
            return
        filename, content = 生成猫眼文件(book_id, detail, chapters, contents)
        result = await _发送(event, filename, content, config, str(detail.get("title") or "未知"), str(detail.get("author") or "未知"))
        path = result.get("source_cache_path")
        if result.get("sent"):
            _后台(config, path, filename)
        elif result.get("fallback_text"):
            yield result["fallback_text"]
            _后台(config, path, filename)
        else:
            yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning("猫眼小说下载失败：错误类型=%s", type(exc).__name__)
        yield "下载失败"


def 获取猫眼小说回复流(event: Any, command: str, config: Any = None) -> AsyncIterator[Any] | None:
    source = 提取猫眼来源(event, command)
    return 生成猫眼下载回复流(event, source, config) if source else None


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    try:
        params = {"Act": "searchMultiple", "keyWord": keyword, "type": "book", "pageSize": min(50, max(1, int(需要数量 or 20))), "currentPage": 1, "filterAuthor": 1, "suggestType": 0}
        async with 创建猫眼HTTP会话(4) as session:
            _, data = await _请求(session, 猫眼搜索地址, params=params)
        rows = (((data or {}).get("body") or {}).get("book") or {}).get("datas") if isinstance(data, dict) else []
        result = []
        for item in rows if isinstance(rows, list) else []:
            if not isinstance(item, dict):
                continue
            info = item.get("data_info") if isinstance(item.get("data_info"), dict) else {}
            book_id, title = str(info.get("bookId") or ""), _文本(info.get("displayBookName") or info.get("bookName"))
            if not book_id.isdigit() or not title:
                continue
            result.append({"book_id": book_id, "title": title.replace("《", "").replace("》", ""), "author": _文本(info.get("bookAuthor") or "未知"), "url": 构造猫眼链接(book_id), "intro": _文本(info.get("bookDescription")), "score": 0, "heat": 0})
        return result[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as exc:
        logger.debug("猫眼小说搜索失败：错误类型=%s", type(exc).__name__)
        return []
