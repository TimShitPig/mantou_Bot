"""酷匠小说独立异步下载模块。"""
from __future__ import annotations

import asyncio
import base64
import gzip
import html
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

try:
    from Crypto.Cipher import AES
except Exception:
    AES = None
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

酷匠基础地址 = "https://app.kujiang.com/v1/book"
酷匠域名 = {"kujiang.com", "www.kujiang.com", "app.kujiang.com"}
酷匠链接正则 = re.compile(r"https?://(?:[^\s/<>\"']*\.)?kujiang\.com[^\s<>\"']*", re.I)
酷匠并发数 = 80
酷匠重试次数 = 3
酷匠缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
酷匠声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
酷匠目录请求头 = {"auth-code": "dc67efdd82941586e69207b3374037b2", "app": "com.dpx.kujiang", "platform": "android", "device-uuid": "5dd1f054b2f013b9", "version": "3.9.7", "channel": "XIAOMI", "User-Agent": "KuJiang/3.9.7", "Accept": "application/json"}
酷匠正文请求头 = {"auth-code": "440590fab1b828085ab67fdc9fc40cbb", "app": "com.dpx.kujiang", "platform": "android", "device-uuid": "A589D18F6E1F84A2", "version": "3.9.14", "channel": "QQ", "User-Agent": "KuJiang/3.9.14(Android;P40;7.1.2)", "Accept": "application/json"}


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


def 提取酷匠来源(event: Any, command: Any) -> str | None:
    values: list[str] = []
    _收集(command, values, set())
    _收集(event, values, set())
    for value in values:
        match = 酷匠链接正则.search(urllib.parse.unquote(value))
        if match:
            return match.group(0).rstrip("'\"，。；;]}>）)")
    for value in values:
        if "酷匠" not in value and "kujiang" not in value.lower():
            continue
        match = re.search(r"(?:book[_-]?id|bookId|novelId|book)\D{0,8}(\d+)", value, re.I)
        if match:
            return 构造酷匠链接(match.group(1))
    return None


def 解析酷匠书籍编号(source: str) -> str:
    text = urllib.parse.unquote(str(source or ""))
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(text).query)
        for key in ("book", "book_id", "bookId", "id"):
            if query.get(key) and str(query[key][0]).isdigit():
                return str(query[key][0])
    except Exception:
        pass
    match = re.search(r"(?:book|novel|detail)[^0-9]{0,15}(\d+)", text, re.I)
    return match.group(1) if match else ""


def 构造酷匠链接(book_id: Any) -> str:
    return f"https://app.kujiang.com/book/{book_id}"


def 创建酷匠HTTP会话(concurrency: int = 酷匠并发数) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    connector = aiohttp.TCPConnector(limit=max(1, int(concurrency)), limit_per_host=max(1, int(concurrency)), ttl_dns_cache=300)
    return aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=timeout, connector=connector)


async def _请求(session: aiohttp.ClientSession, path: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(酷匠重试次数):
        try:
            async with session.get(酷匠基础地址 + path, params=params, headers=headers) as response:
                response.raise_for_status()
                data = json.loads((await response.read()).decode("utf-8-sig", "replace"))
            return data if isinstance(data, dict) else {}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < 酷匠重试次数:
                await asyncio.sleep(0.2 * (attempt + 1))
    raise RuntimeError("酷匠接口请求失败") from last


def _成功(data: Any) -> bool:
    return isinstance(data, dict) and str((data.get("header") or {}).get("result")) == "0"


async def 获取酷匠详情(session: aiohttp.ClientSession, book_id: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    detail = await _请求(session, f"/get_book_infos", params={"book": book_id, "subsite": "m", "from": "search"})
    if not _成功(detail):
        return {}, []
    info = (detail.get("body") or {}).get("bookinfo") if isinstance(detail.get("body"), dict) else {}
    info = info if isinstance(info, dict) else {}
    catalog = await _请求(session, "/catalog", params={"book": book_id, "auth_code": "dc67efdd82941586e69207b3374037b2", "sort": "asc"}, headers=酷匠目录请求头)
    chapters: list[dict[str, str]] = []
    volumes = (catalog.get("body") or {}).get("catalog") if isinstance(catalog.get("body"), dict) else []
    for volume in volumes if isinstance(volumes, list) else []:
        if not isinstance(volume, dict):
            continue
        chapters.extend(
            {"id": str(chapter.get("chapter")), "title": _文本(chapter.get("v_chapter") or "章节")}
            for chapter in (volume.get("chapters") if isinstance(volume.get("chapters"), list) else [])
            if isinstance(chapter, dict) and str(chapter.get("chapter") or "")
        )
    detail_info = {"title": _文本(info.get("v_book")), "author": _文本(info.get("penname") or "未知"), "intro": _文本(info.get("intro")), "status": "完结" if str(info.get("status") or "").lower() in {"1", "finish", "完结"} else "连载", "word_count": info.get("public_size") or info.get("word_count") or 0}
    return detail_info, chapters


def _解密正文(value: str) -> str:
    if AES is None or len(value) <= 28:
        return ""
    try:
        encrypted = base64.b64decode(value[28:])
        decrypted = AES.new(b"KujiangApp747605", AES.MODE_CBC, b"5efd3f6060e20330").decrypt(encrypted)
        # PKCS7 padding is removed by the library-compatible path.
        padding = decrypted[-1]
        if 0 < padding <= 16 and decrypted.endswith(bytes([padding]) * padding):
            decrypted = decrypted[:-padding]
        packed = base64.b64decode(decrypted)
        return gzip.decompress(packed).decode("utf-8", "replace")
    except Exception:
        return ""


async def _下载章节(session: aiohttp.ClientSession, book_id: str, chapter: dict[str, str], sem: asyncio.Semaphore) -> str:
    async with sem:
        for attempt in range(酷匠重试次数):
            try:
                data = await _请求(session, "/read", params={"book": book_id, "chapter": chapter["id"]}, headers=酷匠正文请求头)
                node = (data.get("body") or {}) if isinstance(data.get("body"), dict) else {}
                content = _解密正文(str(node.get("content") or ""))
                if content:
                    return _文本(content).strip()
                raise RuntimeError("正文为空或解密失败")
            except Exception as exc:
                logger.debug("酷匠小说章节获取失败：章节=%s, 错误类型=%s", chapter.get("id"), type(exc).__name__)
                if attempt + 1 < 酷匠重试次数:
                    await asyncio.sleep(0.2 * (attempt + 1))
    return ""


async def 下载酷匠正文(session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]) -> list[str]:
    results = [""] * len(chapters)
    sem = asyncio.Semaphore(max(1, min(酷匠并发数, len(chapters) or 1)))
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
                logger.info("酷匠小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s, 并发数=%s, 会话复用=开启, 解密方式=库", book_id, done, len(chapters), int(done * 100 / max(1, len(chapters))), success, done - success, 酷匠并发数)
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
    return re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "未知")).strip(" .")[:80] or "酷匠小说"


def 生成酷匠文件(book_id: str, detail: dict[str, Any], chapters: list[dict[str, str]], contents: list[str]) -> tuple[str, bytes]:
    status = str(detail.get("status") or "连载")
    title, author = str(detail.get("title") or f"酷匠小说{book_id}"), str(detail.get("author") or "未知")
    lines = [酷匠声明, "", f"名称：{title}", f"作者：{author}", f"状态：{status}", f"字数：{_字数(detail.get('word_count'))}", f"书籍ID：{book_id}", f"章节数：{len(chapters)}", ""]
    if detail.get("intro"):
        lines.extend(["简介：", str(detail["intro"]), ""])
    for chapter, content in zip(chapters, contents):
        heading = chapter.get("title") or "章节"
        lines.extend([heading, "", 去除章节正文重复标题(heading, content), ""])
    filename = f"[{status}]书名：{_文件名(title)} 作者：{_文件名(author)}.txt"
    text = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n")
    return filename, text.replace("\n", "\r\n").encode("utf-8")


def _缓存(filename: str, content: bytes) -> Path:
    酷匠缓存目录.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = 酷匠缓存目录 / (Path(filename).name if index == 0 else f"{Path(filename).stem}_{index}.txt")
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
        logger.warning("酷匠小说文件发送失败：错误类型=%s", type(exc).__name__)
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
            logger.warning("酷匠小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            小说缓存工具.删除下载缓存文件(path)
    try:
        asyncio.create_task(task())
    except RuntimeError:
        小说缓存工具.删除下载缓存文件(path)


async def 生成酷匠下载回复流(event: Any, source: str, config: Any = None) -> AsyncIterator[Any]:
    book_id = 解析酷匠书籍编号(source)
    if not book_id:
        yield "下载失败"
        return
    try:
        async with 创建酷匠HTTP会话() as session:
            detail, chapters = await 获取酷匠详情(session, book_id)
            if not detail or not chapters:
                yield "下载失败"
                return
            logger.info("酷匠小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s, 会话复用=开启, 解密方式=库", book_id, len(chapters), 酷匠并发数)
            yield f"书名：{detail.get('title') or '未知'}\n作者：{detail.get('author') or '未知'}\n状态：{detail.get('status') or '连载'}\n章节：{len(chapters)} 章\n字数：{_字数(detail.get('word_count'))}\n\n正在下载中请稍等....."
            contents = await 下载酷匠正文(session, book_id, chapters)
        if any(not content for content in contents):
            logger.warning("酷匠小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s", book_id, sum(bool(x) for x in contents), len(chapters))
            yield "下载失败"
            return
        filename, content = 生成酷匠文件(book_id, detail, chapters, contents)
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
        logger.warning("酷匠小说下载失败：错误类型=%s", type(exc).__name__)
        yield "下载失败"


def 获取酷匠小说回复流(event: Any, command: str, config: Any = None) -> AsyncIterator[Any] | None:
    source = 提取酷匠来源(event, command)
    return 生成酷匠下载回复流(event, source, config) if source else None


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    try:
        async with 创建酷匠HTTP会话(4) as session:
            data = await _请求(session, "/search", params={"keyword": keyword})
        rows = data.get("body") if isinstance(data.get("body"), list) else []
        result = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            book_id, title = str(item.get("book") or ""), _文本(item.get("v_book"))
            if not book_id or not title:
                continue
            result.append({"book_id": book_id, "title": title, "author": _文本(item.get("penname") or "未知"), "url": 构造酷匠链接(book_id), "intro": _文本(item.get("intro")), "score": 0, "heat": 0, "word_count": item.get("public_size") or 0})
        return result[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as exc:
        logger.debug("酷匠小说搜索失败：错误类型=%s", type(exc).__name__)
        return []
