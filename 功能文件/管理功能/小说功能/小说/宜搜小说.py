"""宜搜小说独立异步下载模块。"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

try:
    from Crypto.Cipher import DES
    from Crypto.Util.Padding import unpad
except Exception:
    DES = None
    unpad = None

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

宜搜基础地址 = "https://api.ieasou.com"
宜搜签名密钥 = "EaSoU0517+PuBlIsHkEy-JRKKOWTUNZCNTWY-"
宜搜解密密钥 = b"EaSoUcNt"
宜搜解密向量 = b"EaSoUcNt"
宜搜允许域名 = {"ieasou.com", "www.ieasou.com", "api.ieasou.com", "easou.com"}
宜搜链接正则 = re.compile(
    r"https?://(?:[^\s/<>\"']*\.)?(?:ieasou\.com|easou\.com)[^\s<>\"']*", re.I
)
宜搜缓存目录 = 小说缓存工具.下载缓存目录
宜搜并发数 = 50
宜搜重试次数 = 3
宜搜声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


def _文本(value: Any) -> str:
    return re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", html.unescape(str(value or ""))
    ).strip()


def _候选(value: Any, out: list[str], seen: set[int], depth: int = 0) -> None:
    if value is None or depth > 7:
        return
    if isinstance(value, str):
        out.append(value)
        return
    if isinstance(value, dict):
        try:
            out.append(json.dumps(value, ensure_ascii=False, default=str))
        except Exception:
            pass
        for item in value.values():
            _候选(item, out, seen, depth + 1)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _候选(item, out, seen, depth + 1)
        return
    ident = id(value)
    if ident in seen:
        return
    seen.add(ident)
    for field in ("message_str", "message", "raw_message", "text", "content", "data"):
        try:
            _候选(getattr(value, field, None), out, seen, depth + 1)
        except Exception:
            pass


def 提取宜搜来源(event: Any, command: Any) -> str | None:
    values: list[str] = []
    _候选(command, values, set())
    _候选(event, values, set())
    for value in values:
        for text in (value, urllib.parse.unquote(value)):
            match = 宜搜链接正则.search(text)
            if match:
                return match.group(0).rstrip("'\"，。；;]}>）)")
    for value in values:
        if (
            "宜搜" not in value
            and "ieasou" not in value.lower()
            and "easou" not in value.lower()
        ):
            continue
        nid = re.search(
            r"(?:nid|book[_-]?id|bookId|novelId)\D{0,8}(\d{3,})", value, re.I
        )
        gid = re.search(r"(?:gid|genre[_-]?id|categoryId)\D{0,8}(\d{1,})", value, re.I)
        if nid and gid:
            return 构造宜搜链接(f"{nid.group(1)}_{gid.group(1)}")
    return None


def 解析宜搜书籍编号(source: str) -> str:
    text = urllib.parse.unquote(str(source or ""))
    match = re.search(
        r"(?:book|novel|detail)[^0-9]{0,20}(\d{3,})[_/-](\d{1,})", text, re.I
    )
    if match:
        return f"{match.group(1)}_{match.group(2)}"
    match = re.search(r"(\d{3,})_(\d{1,})", text)
    return f"{match.group(1)}_{match.group(2)}" if match else ""


def 构造宜搜链接(book_id: Any) -> str:
    return f"https://www.ieasou.com/book/{book_id}"


def _时间参数() -> str:
    import time

    return str(int(time.time() * 1000))


def _公共参数(timestamp: str) -> dict[str, str]:
    return {
        "ac": "999",
        "appType": "0",
        "appid": "10001",
        "appverion": "508500",
        "bidType": "0",
        "birt": "1706674841000",
        "ch": "blf1298_10928_001",
        "chType": "6",
        "cid": "eef_easou_book",
        "dzh": "1",
        "gender": "1",
        "instId": timestamp,
        "instime": timestamp,
        "os": "android",
        "pr": "-1.0",
        "ptype": "5",
        "pushid": "7b4aaf1210a5bdbac3cea26d5030a419",
        "recSw": "1",
        "rtype": "2",
        "scp": "0",
        "session_id": "153F4EEE16F56A43FD63ZD21B866413ED9BE044EFB876A115C62DBED82EE4C824D",
        "showj": "1",
        "tm": "0",
        "udid": "3d3ec742930b635fc4c61f0575dbc4d2939edbe2",
        "userInitPay": "3",
        "utype": "0",
        "vm": "5.8.5",
    }


def _签名地址(path: str, params: dict[str, Any]) -> str:
    items = [
        (str(key), str(value))
        for key, value in params.items()
        if key != "snk" and value not in (None, "")
    ]
    items.sort()
    sign = (
        hashlib.md5(
            (
                "&".join(f"{key}={value}" for key, value in items)
                + "&key="
                + 宜搜签名密钥
            ).encode()
        )
        .hexdigest()
        .upper()
    )
    query = dict(params)
    query["snk"] = sign
    return 宜搜基础地址 + path + "?" + urllib.parse.urlencode(query)


def 创建宜搜HTTP会话(concurrency: int = 宜搜并发数) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    connector = aiohttp.TCPConnector(
        limit=max(1, int(concurrency)),
        limit_per_host=max(1, int(concurrency)),
        ttl_dns_cache=300,
    )
    return aiohttp.ClientSession(
        headers={"User-Agent": "esbook android 5.8.5", "Accept": "application/json"},
        timeout=timeout,
        connector=connector,
    )


async def _请求(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(宜搜重试次数):
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                raw = await response.read()
            for body in (raw, bytes(byte ^ 0xFF for byte in raw)):
                try:
                    data = json.loads(body.decode("utf-8-sig", "replace"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    continue
            return {}
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last = exc
            if attempt + 1 < 宜搜重试次数:
                await asyncio.sleep(0.2 * (attempt + 1))
    raise RuntimeError("宜搜接口请求失败") from last


def _成功(data: Any) -> bool:
    return isinstance(data, dict) and (
        "success" not in data or data.get("success") in (True, 1, "1", "true")
    )


def _编号(book_id: Any) -> tuple[str, str] | None:
    match = re.fullmatch(r"(\d+)_(\d+)", str(book_id or "").strip())
    return (match.group(1), match.group(2)) if match else None


def _取章节(data: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pools: list[Any] = [data.get("chapters")]
    pools.extend(
        item.get("chapters")
        for item in data.get("volumes", [])
        if isinstance(item, dict)
    )
    seen: set[str] = set()
    for pool in pools:
        if not isinstance(pool, list):
            continue
        for item in pool:
            if not isinstance(item, dict):
                continue
            number = str(item.get("sort") or item.get("sequence") or "").strip()
            if not number.isdigit() or number in seen:
                continue
            seen.add(number)
            rows.append(
                {
                    "id": number,
                    "title": _文本(
                        item.get("chapter_name") or item.get("name") or f"第{number}章"
                    ),
                }
            )
    rows.sort(key=lambda item: int(item["id"]))
    return rows


async def 获取宜搜详情(
    session: aiohttp.ClientSession, book_id: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    parts = _编号(book_id)
    if not parts:
        return {}, []
    nid, gid = parts
    detail_params = _公共参数(_时间参数())
    detail_params.update(
        {
            "ad": "0",
            "gid": gid,
            "nid": nid,
            "sort": "1",
            "size": "50",
            "returnType": "010",
            "gsort": "1",
        }
    )
    detail_data = await _请求(
        session, _签名地址("/api/bookapp/bookSummary.m", detail_params)
    )
    if not _成功(detail_data):
        return {}, []
    info = (
        detail_data.get("coverInfo")
        if isinstance(detail_data.get("coverInfo"), dict)
        else {}
    )
    chapters: list[dict[str, str]] = []
    seen: set[str] = set()
    page_size = 1000
    offset = 1
    expected = 0
    try:
        expected = int(info.get("chapterCount") or info.get("last_sort") or 0)
    except (TypeError, ValueError):
        expected = 0
    while offset <= 200000:
        page_params = _公共参数(_时间参数())
        page_params.update(
            {
                "ad": "0",
                "gid": gid,
                "nid": nid,
                "sort": str(offset),
                "size": str(page_size),
                "returnType": "100",
                "gsort": "1",
            }
        )
        data = await _请求(
            session, _签名地址("/api/bookapp/bookSummary.m", page_params)
        )
        if not _成功(data):
            break
        page_chapters = _取章节(data)
        new_count = 0
        for chapter in page_chapters:
            chapter_id = chapter.get("id") or ""
            if chapter_id and chapter_id not in seen:
                seen.add(chapter_id)
                chapters.append(chapter)
                new_count += 1
        if (
            bool(data.get("lastPage"))
            or len(page_chapters) < page_size
            or new_count == 0
        ):
            break
        if expected and len(chapters) >= expected:
            break
        offset += page_size
    chapters.sort(key=lambda item: int(item["id"]))
    status_value = str(info.get("status") or "").lower()
    status = (
        "完结"
        if status_value in {"1", "2", "finish", "finished", "完本", "完结"}
        else "连载"
    )
    return (
        {
            "title": _文本(info.get("name")),
            "author": _文本(info.get("author") or "未知"),
            "intro": _文本(info.get("desc")),
            "status": status,
            "word_count": info.get("wordCount") or info.get("words") or 0,
        },
        chapters,
    )


async def _下载章节(
    session: aiohttp.ClientSession,
    book_id: str,
    chapter: dict[str, str],
    sem: asyncio.Semaphore,
) -> str:
    parts = _编号(book_id)
    if not parts:
        return ""
    nid, gid = parts
    async with sem:
        for attempt in range(宜搜重试次数):
            try:
                params = _公共参数(_时间参数())
                params.update(
                    {
                        "a": "1",
                        "autoBuy": "0",
                        "gid": gid,
                        "nid": nid,
                        "sort": chapter["id"],
                        "gsort": "0",
                        "sgsort": "0",
                        "sequence": "1",
                    }
                )
                data = await _请求(
                    session, _签名地址("/api/bookapp/chargeChapter.m", params)
                )
                value = data.get("content") or (data.get("data") or {}).get("content")
                if (
                    not isinstance(value, str)
                    or not re.fullmatch(r"[0-9A-Fa-f]+", value)
                    or len(value) % 2
                ):
                    raise RuntimeError("正文响应为空")
                if DES is None or unpad is None:
                    raise RuntimeError("解密库不可用")
                plain = unpad(
                    DES.new(宜搜解密密钥, DES.MODE_CBC, 宜搜解密向量).decrypt(
                        bytes.fromhex(value)
                    ),
                    DES.block_size,
                ).decode("utf-8", "replace")
                plain = _文本(plain).strip()
                if plain:
                    return plain
            except Exception as exc:
                logger.debug(
                    "宜搜小说章节获取失败：章节=%s, 错误类型=%s",
                    chapter.get("id"),
                    type(exc).__name__,
                )
                if attempt + 1 < 宜搜重试次数:
                    await asyncio.sleep(0.2 * (attempt + 1))
    return ""


async def 下载宜搜正文(
    session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]
) -> list[str]:
    results = [""] * len(chapters)
    sem = asyncio.Semaphore(max(1, min(宜搜并发数, len(chapters) or 1)))
    done = 0
    next_log = max(1, len(chapters) // 10)
    lock = asyncio.Lock()

    async def one(index: int, chapter: dict[str, str]) -> None:
        nonlocal done, next_log
        results[index] = await _下载章节(session, book_id, chapter, sem)
        async with lock:
            done += 1
            if done >= next_log or done == len(chapters):
                logger.info(
                    "宜搜小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s, 并发数=%s, 会话复用=开启, 解密方式=库",
                    book_id,
                    done,
                    len(chapters),
                    int(done * 100 / max(1, len(chapters))),
                    sum(bool(x) for x in results),
                    done - sum(bool(x) for x in results),
                    sem._value,
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
        or "宜搜小说"
    )


def 生成宜搜文件(
    book_id: str,
    detail: dict[str, Any],
    chapters: list[dict[str, str]],
    contents: list[str],
) -> tuple[str, bytes]:
    status = str(detail.get("status") or "连载")
    title = str(detail.get("title") or f"宜搜小说{book_id}")
    author = str(detail.get("author") or "未知")
    lines = [
        宜搜声明,
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
    return filename, "\r\n".join("\n".join(lines).splitlines()).replace(
        "\n", "\r\n"
    ).encode("utf-8")


def _写入缓存(filename: str, content: bytes) -> Path:
    宜搜缓存目录.mkdir(parents=True, exist_ok=True)
    path = 宜搜缓存目录 / Path(filename).name
    for index in range(1, 1000):
        if not path.exists():
            path.write_bytes(content)
            小说缓存工具.标记下载缓存正在使用(path)
            return path
        path = 宜搜缓存目录 / f"{Path(filename).stem}_{index}.txt"
    raise RuntimeError("缓存文件名冲突")


async def _发送(
    event: Any, filename: str, content: bytes, config: Any, title: str, author: str
) -> dict[str, Any]:
    path = _写入缓存(filename, content)
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
        logger.warning("宜搜小说文件发送失败：错误类型=%s", type(exc).__name__)
        小说缓存工具.删除下载缓存文件(path)
        return {"sent": False, "source_cache_path": None}


def _后台备份(config: Any, path: Any, filename: str) -> None:
    if not path:
        return

    async def task() -> None:
        try:
            if 百度网盘 is not None:
                await 百度网盘.后台上传小说文件(config, path, filename)
        except Exception as exc:
            logger.warning("宜搜小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            小说缓存工具.删除下载缓存文件(path)

    try:
        asyncio.create_task(task())
    except RuntimeError:
        小说缓存工具.删除下载缓存文件(path)


async def 生成宜搜下载回复流(
    event: Any, source: str, config: Any = None
) -> AsyncIterator[Any]:
    book_id = 解析宜搜书籍编号(source)
    if not book_id:
        yield "下载失败 请重试"
        return
    try:
        async with 创建宜搜HTTP会话() as session:
            detail, chapters = await 获取宜搜详情(session, book_id)
            if not detail or not chapters:
                yield "下载失败 请重试"
                return
            logger.info(
                "宜搜小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s, 会话复用=开启, 解密方式=库",
                book_id,
                len(chapters),
                宜搜并发数,
            )
            yield f"书名：{detail.get('title') or '未知'}\n作者：{detail.get('author') or '未知'}\n状态：{detail.get('status') or '连载'}\n章节：{len(chapters)} 章\n字数：{_字数(detail.get('word_count'))}\n\n正在下载中请稍等....."
            contents = await 下载宜搜正文(session, book_id, chapters)
        if len(contents) != len(chapters) or any(not content for content in contents):
            logger.warning(
                "宜搜小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s",
                book_id,
                sum(bool(x) for x in contents),
                len(chapters),
            )
            yield "下载失败 请重试"
            return
        filename, content = 生成宜搜文件(book_id, detail, chapters, contents)
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
            _后台备份(config, path, filename)
            return
        if result.get("fallback_text"):
            yield result["fallback_text"]
            _后台备份(config, path, filename)
            return
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning("宜搜小说下载失败：错误类型=%s", type(exc).__name__)
        yield "下载失败 请重试"


def 获取宜搜小说回复流(
    event: Any, command: str, config: Any = None
) -> AsyncIterator[Any] | None:
    source = 提取宜搜来源(event, command)
    return 生成宜搜下载回复流(event, source, config) if source else None


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    try:
        params = _公共参数(_时间参数())
        params.update(
            {
                "word": keyword,
                "type": "0",
                "page_id": "1",
                "count": str(min(100, max(1, int(需要数量 or 20)))),
                "sort_type": "0",
                "subclass": "0",
                "datasource": "0",
                "catalog": "0",
                "bookStatus": "0",
            }
        )
        async with 创建宜搜HTTP会话(4) as session:
            data = await _请求(session, _签名地址("/api/bookapp/searchdzh.m", params))
        rows = (
            data.get("all_book_items")
            if isinstance(data.get("all_book_items"), list)
            else []
        )
        result = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            nid, gid = str(item.get("nid") or ""), str(item.get("gid") or "")
            title = _文本(item.get("name"))
            if not nid.isdigit() or not gid.isdigit() or not title:
                continue
            book_id = f"{nid}_{gid}"
            result.append(
                {
                    "book_id": book_id,
                    "title": title,
                    "author": _文本(item.get("author") or "未知"),
                    "url": 构造宜搜链接(book_id),
                    "intro": _文本(item.get("desc")),
                    "score": item.get("score") or 0,
                    "heat": item.get("readCount") or 0,
                    "word_count": item.get("wordCount") or item.get("words") or 0,
                }
            )
        return result[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as exc:
        logger.debug("宜搜小说搜索失败：错误类型=%s", type(exc).__name__)
        return []
