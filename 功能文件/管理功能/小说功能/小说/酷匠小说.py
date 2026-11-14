"""酷匠小说独立异步下载模块。"""

from __future__ import annotations

import asyncio
import base64
import binascii
import gzip
import html
import json
import re
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except Exception:
    AES = None
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

酷匠基础地址 = "https://app.kujiang.com/v1/book"
酷匠域名 = {"kujiang.com", "www.kujiang.com", "app.kujiang.com"}
酷匠链接正则 = re.compile(r"https?://(?:[^\s/<>\"']*\.)?kujiang\.com[^\s<>\"']*", re.I)
酷匠并发数 = 80
酷匠重试次数 = 3
酷匠缓存目录 = 文件缓存工具.小说缓存目录
酷匠声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
酷匠应用版本 = "3.9.69"
酷匠响应大小上限 = 4 * 1024 * 1024


class _酷匠请求错误(RuntimeError):
    def __init__(
        self, category: str, *, http_status: int | None = None, code: int | None = None
    ) -> None:
        super().__init__(category)
        self.category = category
        self.http_status = http_status
        self.code = code


def _业务码(data: dict[str, Any]) -> int | None:
    header = data.get("header")
    value = header.get("result") if isinstance(header, dict) else None
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,10}", value):
        return int(value)
    return None


def _状态(info: dict[str, Any]) -> str:
    # App 详情使用 fullflag；status/show_status 不是创作状态。
    value = info.get("fullflag")
    if isinstance(value, bool):
        return "未知"
    return {"1": "完结", "0": "连载"}.get(str(value), "未知")


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
        match = re.search(
            r"(?:book[_-]?id|bookId|novelId|book)\D{0,8}(\d+)", value, re.I
        )
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
    connector = aiohttp.TCPConnector(
        limit=max(1, int(concurrency)),
        limit_per_host=max(1, int(concurrency)),
        ttl_dns_cache=300,
    )
    android_id = uuid.uuid4().hex[:16]
    return aiohttp.ClientSession(
        headers={
            "app": "com.dpx.kujiang", "platform": "android",
            "version": 酷匠应用版本, "auth-code": "", "channel": "KUJIANG",
            "device-uuid": "uid" + base64.b64encode(android_id.encode()).decode("ascii"),
            "User-Agent": f"KuJiang/{酷匠应用版本}(Android;23113RKC6C;15)",
            "Accept": "application/json",
        },
        timeout=timeout,
        connector=connector,
    )


async def _请求(
    session: aiohttp.ClientSession,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    last: _酷匠请求错误 | None = None
    for attempt in range(酷匠重试次数):
        try:
            async with session.get(
                酷匠基础地址 + path, params=params, headers=headers, allow_redirects=False
            ) as response:
                if response.status != 200:
                    raise _酷匠请求错误(
                        "rate_limited" if response.status == 429 else "http_error",
                        http_status=response.status,
                    )
                raw = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    if len(raw) + len(chunk) > 酷匠响应大小上限:
                        raise _酷匠请求错误("response_too_large", http_status=200)
                    raw.extend(chunk)
                try:
                    data = json.loads(raw.decode("utf-8-sig"))
                except (json.JSONDecodeError, UnicodeError) as exc:
                    raise _酷匠请求错误("invalid_response", http_status=200) from exc
            if not isinstance(data, dict) or _业务码(data) is None:
                raise _酷匠请求错误("invalid_response", http_status=200)
            return data
        except _酷匠请求错误 as exc:
            if exc.category != "http_error" or exc.http_status not in {408, 500, 502, 503, 504}:
                raise
            last = exc
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            last = _酷匠请求错误(
                "timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error"
            )
        if attempt + 1 < 酷匠重试次数:
            await asyncio.sleep(0.2 * (attempt + 1))
    raise last or _酷匠请求错误("network_error")


def _成功(data: Any) -> bool:
    return isinstance(data, dict) and _业务码(data) == 0


async def 获取酷匠详情(
    session: aiohttp.ClientSession, book_id: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    detail = await _请求(
        session, "/get_book_infos", params={"book": book_id, "subsite": "m"}
    )
    if not _成功(detail):
        raise _酷匠请求错误("business_error", code=_业务码(detail))
    body = detail.get("body")
    info = body.get("bookinfo") if isinstance(body, dict) else None
    if (
        not isinstance(info, dict)
        or str(info.get("book")) != str(book_id)
        or not _文本(info.get("v_book"))
    ):
        raise _酷匠请求错误("invalid_detail")
    catalog = await _请求(
        session, "/catalog", params={"book": book_id, "auth_code": "", "sort": "asc"}
    )
    if not _成功(catalog):
        raise _酷匠请求错误("business_error", code=_业务码(catalog))
    body = catalog.get("body")
    volumes = body.get("catalog") if isinstance(body, dict) else None
    if not isinstance(volumes, list):
        raise _酷匠请求错误("invalid_catalog")
    chapters: list[dict[str, str]] = []
    seen: set[str] = set()
    for volume in volumes:
        if not isinstance(volume, dict) or not isinstance(volume.get("chapters"), list):
            raise _酷匠请求错误("invalid_catalog")
        for chapter in volume["chapters"]:
            chapter_id = str(chapter.get("chapter") or "") if isinstance(chapter, dict) else ""
            if not chapter_id.isascii() or not chapter_id.isdigit() or chapter_id in seen:
                raise _酷匠请求错误("invalid_catalog")
            seen.add(chapter_id)
            chapters.append({"id": chapter_id, "title": _文本(chapter.get("v_chapter") or "章节")})
    detail_info = {
        "title": _文本(info.get("v_book")),
        "author": _文本(info.get("penname") or "未知"),
        "intro": _文本(info.get("intro")),
        "status": _状态(info),
        "word_count": info.get("public_size") or info.get("word_count") or 0,
    }
    return detail_info, chapters


def _解密正文(value: str) -> str:
    if not isinstance(value, str):
        raise _酷匠请求错误("invalid_content")
    if "a2o@" not in value:
        return value
    if AES is None:
        raise _酷匠请求错误("crypto_unavailable")
    try:
        iv_text, cipher_text = value.split("a2o@", 1)
        iv = base64.b64decode("".join(iv_text.split()), validate=True)
        encrypted = base64.b64decode("".join(cipher_text.split()), validate=True)
        if len(iv) != AES.block_size or not encrypted or len(encrypted) % AES.block_size:
            raise ValueError("invalid_cipher")
        decrypted = unpad(AES.new(b"KujiangApp747605", AES.MODE_CBC, iv).decrypt(encrypted), AES.block_size)
        packed = base64.b64decode("".join(decrypted.decode("utf-8").split()), validate=True)
        return gzip.decompress(packed).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeError, OSError, EOFError) as exc:
        raise _酷匠请求错误("decrypt_error") from exc


async def _下载章节(
    session: aiohttp.ClientSession,
    book_id: str,
    chapter: dict[str, str],
    sem: asyncio.Semaphore,
) -> str:
    async with sem:
        try:
            data = await _请求(
                session, "/cache_chapter", params={"book": book_id, "chapter": chapter["id"]}
            )
            # 缓存正文只有 result=2 表示完整内容；订阅及预览状态不得作为成功正文。
            if _业务码(data) != 2:
                raise _酷匠请求错误("chapter_unavailable", code=_业务码(data))
            node = data.get("body")
            if not isinstance(node, dict) or str(node.get("chapter")) != chapter["id"]:
                raise _酷匠请求错误("chapter_mismatch")
            content = _文本(_解密正文(node.get("content")))
            if not content:
                raise _酷匠请求错误("empty_content")
            return content
        except Exception as exc:
            logger.debug(
                "酷匠小说章节获取失败：章节=%s, 错误类型=%s, category=%s, http_status=%s, code=%s",
                chapter.get("id"), type(exc).__name__,
                getattr(exc, "category", "unknown"), getattr(exc, "http_status", None),
                getattr(exc, "code", None),
            )
    return ""


async def 下载酷匠正文(
    session: aiohttp.ClientSession, book_id: str, chapters: list[dict[str, str]]
) -> list[str]:
    results = [""] * len(chapters)
    sem = asyncio.Semaphore(max(1, min(酷匠并发数, len(chapters) or 1)))
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
                    "酷匠小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s, 并发数=%s, 会话复用=开启, 解密方式=库",
                    book_id,
                    done,
                    len(chapters),
                    int(done * 100 / max(1, len(chapters))),
                    success,
                    done - success,
                    酷匠并发数,
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
        or "酷匠小说"
    )


def 生成酷匠文件(
    book_id: str,
    detail: dict[str, Any],
    chapters: list[dict[str, str]],
    contents: list[str],
) -> tuple[str, bytes]:
    status = str(detail.get("status") or "连载")
    title, author = (
        str(detail.get("title") or f"酷匠小说{book_id}"),
        str(detail.get("author") or "未知"),
    )
    lines = [
        酷匠声明,
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
    酷匠缓存目录.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = 酷匠缓存目录 / (
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
        logger.warning("酷匠小说文件发送失败：错误类型=%s", type(exc).__name__)
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
            logger.warning("酷匠小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            文件缓存工具.删除小说缓存文件(path)

    try:
        asyncio.create_task(task())
    except RuntimeError:
        文件缓存工具.删除小说缓存文件(path)


async def 生成酷匠下载回复流(
    event: Any, source: str, config: Any = None
) -> AsyncIterator[Any]:
    book_id = 解析酷匠书籍编号(source)
    if not book_id:
        yield "下载失败 请重试"
        return
    try:
        async with 创建酷匠HTTP会话() as session:
            detail, chapters = await 获取酷匠详情(session, book_id)
            if not detail or not chapters:
                yield "下载失败 请重试"
                return
            logger.info(
                "酷匠小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s, 会话复用=开启, 解密方式=库",
                book_id,
                len(chapters),
                酷匠并发数,
            )
            yield f"书名：{detail.get('title') or '未知'}\n作者：{detail.get('author') or '未知'}\n状态：{detail.get('status') or '连载'}\n章节：{len(chapters)} 章\n字数：{_字数(detail.get('word_count'))}\n\n正在下载中请稍等....."
            contents = await 下载酷匠正文(session, book_id, chapters)
        if any(not content for content in contents):
            logger.warning(
                "酷匠小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s",
                book_id,
                sum(bool(x) for x in contents),
                len(chapters),
            )
            yield "下载失败 请重试"
            return
        filename, content = 生成酷匠文件(book_id, detail, chapters, contents)
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
            "酷匠小说下载失败：错误类型=%s, category=%s, http_status=%s, code=%s",
            type(exc).__name__, getattr(exc, "category", "unknown"),
            getattr(exc, "http_status", None), getattr(exc, "code", None),
        )
        yield "下载失败 请重试"


def 获取酷匠小说回复流(
    event: Any, command: str, config: Any = None
) -> AsyncIterator[Any] | None:
    source = 提取酷匠来源(event, command)
    return 生成酷匠下载回复流(event, source, config) if source else None


async def 搜索小说(keyword: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    try:
        async with 创建酷匠HTTP会话(4) as session:
            data = await _请求(session, "/search202107", params={"keyword": keyword})
        if not _成功(data):
            raise _酷匠请求错误("business_error", code=_业务码(data))
        body = data.get("body")
        rows = body.get("list") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            raise _酷匠请求错误("invalid_search")
        result = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            book_id, title = str(item.get("book") or ""), _文本(item.get("v_book"))
            if not book_id.isascii() or not book_id.isdigit() or not title:
                continue
            result.append(
                {
                    "status": _状态(item),
                    "book_id": book_id,
                    "title": title,
                    "author": _文本(item.get("penname") or "未知"),
                    "url": 构造酷匠链接(book_id),
                    "intro": _文本(item.get("intro")),
                    "score": 0,
                    "heat": 0,
                    "word_count": item.get("public_size") or 0,
                }
            )
        return result[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as exc:
        logger.debug(
            "酷匠小说搜索失败：错误类型=%s, category=%s, http_status=%s, code=%s",
            type(exc).__name__, getattr(exc, "category", "unknown"),
            getattr(exc, "http_status", None), getattr(exc, "code", None),
        )
        raise
