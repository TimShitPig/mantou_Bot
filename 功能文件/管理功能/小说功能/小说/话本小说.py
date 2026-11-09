"""话本小说分享链接、异步下载和统一 TXT/网盘出口。"""

from __future__ import annotations

import asyncio
import html
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

import aiohttp

try:
    from astrbot.api import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.小说 import 番茄小说
from 功能文件.管理功能.网盘功能 import 小说网盘

API_BASE = "https://api.ihuaben.com"
MAX_CONCURRENCY = 400
_IMAGE_RE = re.compile(r"\[img:([^\]]+)\]", re.IGNORECASE)
_SERIAL_STATES = {
    "SERIALIZE": "连载中",
    "SERIALIZING": "连载中",
    "COMPLETE": "已完结",
    "COMPLETES": "已完结",
}


class HuabenError(RuntimeError):
    """仅保存固定分类与数字码，不携带服务端原文或请求凭据。"""

    def __init__(
        self,
        reason: str,
        *,
        code: int | None = None,
        status: int | None = None,
        retryable: bool = False,
        retry_after: float = 0,
        missing_count: int = 0,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        self.missing_count = missing_count


def _positive_id(value: Any) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"[1-9]\d{0,17}", text):
        raise HuabenError("invalid_id")
    return text


def _cover_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "undefined":
        return ""
    if text.startswith(("https://", "http://")):
        return text
    return "https://piccn.ihuaben.com/" + text.lstrip("/")


def normalize_book(data: dict[str, Any]) -> dict[str, Any]:
    book_id = _positive_id(data.get("bookId"))
    state = str(data.get("serialState") or "")
    return {
        "book_id": book_id,
        "book_name": str(data.get("bookName") or ""),
        "author_name": str(data.get("authorName") or ""),
        "serial_state": state,
        "serial_state_text": _SERIAL_STATES.get(state, "未知"),
        "word_count": data.get("wordCount"),
        "chapter_count": data.get("chapterCount"),
        "intro": str(data.get("bookIntroduction") or ""),
        "cover_url": _cover_url(data.get("coverUrl")),
        "book_url": f"https://www.ihuaben.com/book/{book_id}.html",
        "category_name": str(data.get("bookCategoryName") or ""),
    }


class AsyncHuabenClient:
    """一次下载共用一个 aiohttp 会话；工作任务按章节量创建，最高 400 路。"""

    def __init__(self, *, concurrency: int = MAX_CONCURRENCY) -> None:
        self.concurrency = max(1, min(MAX_CONCURRENCY, int(concurrency)))
        self.current_concurrency = self.concurrency
        self.session: aiohttp.ClientSession | None = None
        self._workers: set[asyncio.Task[Any]] = set()
        self._device_id = str(uuid.uuid4())
        self._android_id = uuid.uuid4().hex[:16]
        self._active = 0
        self.stats = {
            "requests": 0,
            "retries": 0,
            "http_429": 0,
            "http_5xx": 0,
            "code2": 0,
            "code3": 0,
            "network_errors": 0,
            "peak_concurrency": 0,
        }
        self.concurrency_history: list[dict[str, Any]] = []

    async def __aenter__(self) -> AsyncHuabenClient:
        if self.session is not None:
            raise HuabenError("session_already_open")
        connector = aiohttp.TCPConnector(
            limit=self.concurrency,
            limit_per_host=self.concurrency,
            keepalive_timeout=30,
            ttl_dns_cache=300,
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60, sock_connect=15, sock_read=45),
            cookie_jar=aiohttp.DummyCookieJar(),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        workers = tuple(self._workers)
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        if self.session is not None:
            await self.session.close()
            self.session = None

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36 - HuabenApp"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://wwwapp.ihuaben.com/",
            "plantype": "ANDROID",
            "version": "7.6.1",
            "packageid": "com.huabenapp",
            "umengchannel": "official",
            "device-brand": "google",
            "device-model": "Pixel 7",
            "access-token": "",
            "device-id": self._device_id,
            "deviceid": self._android_id,
            "timestamp": str(time.time_ns() // 1_000_000),
        }

    async def _request_once(
        self, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        if self.session is None:
            raise HuabenError("session_not_open")
        self.stats["requests"] += 1
        self._active += 1
        self.stats["peak_concurrency"] = max(
            self.stats["peak_concurrency"], self._active
        )
        try:
            async with self.session.get(
                url, params=params, headers=self._headers(), allow_redirects=False
            ) as response:
                status = response.status
                retry_header = response.headers.get("Retry-After", "")
                try:
                    retry_after = min(30.0, max(0.0, float(retry_header)))
                except ValueError:
                    retry_after = 0.0
                if status != 200:
                    self.stats["http_429"] += int(status == 429)
                    self.stats["http_5xx"] += int(status >= 500)
                    raise HuabenError(
                        "http_error",
                        status=status,
                        retryable=status == 429 or 500 <= status <= 599,
                        retry_after=retry_after,
                    )
                # Content 是 JSON 明文；aiohttp 使用库自动还原 HTTP 压缩传输。
                raw = await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self.stats["network_errors"] += 1
            raise HuabenError("network_error", retryable=True) from None
        finally:
            self._active -= 1
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise HuabenError("invalid_json") from None
        if not isinstance(payload, dict):
            raise HuabenError("invalid_response")
        raw_code = payload.get("code")
        if isinstance(raw_code, bool) or not re.fullmatch(r"-?\d+", str(raw_code)):
            raise HuabenError("invalid_code")
        code = int(raw_code)
        if code:
            self.stats["code2"] += int(code == 2)
            self.stats["code3"] += int(code == 3)
            raise HuabenError(
                {1: "not_found", 2: "server_busy", 3: "verification_required", 4: "token_invalid"}.get(
                    code, "business_error"
                ),
                code=code,
                retryable=code in (2, 3),
            )
        if "data" not in payload:
            raise HuabenError("missing_data")
        return payload["data"]

    async def _request_json(
        self, url: str, params: dict[str, Any] | None = None, *, attempts: int = 3
    ) -> Any:
        for attempt in range(attempts):
            try:
                return await self._request_once(url, params)
            except HuabenError as error:
                if not error.retryable or attempt + 1 >= attempts:
                    raise
                self.stats["retries"] += 1
                await asyncio.sleep(max(error.retry_after, 0.5 * (2**attempt)))
        raise HuabenError("request_failed")

    async def search(
        self, keyword: str, page: int = 1, page_size: int = 30
    ) -> dict[str, Any]:
        keyword = str(keyword or "").strip()
        if not keyword:
            raise HuabenError("empty_keyword")
        page, page_size = max(1, int(page)), max(1, min(50, int(page_size)))
        data = await self._request_json(
            f"{API_BASE}/book-search/search/appHomeSearch",
            {
                "keyWord": keyword,
                "page": page,
                "pageSize": page_size,
                "bookSearchIndex": "BOOK",
                "source": "markPlaza",
            },
        )
        if not isinstance(data, dict) or (
            data.get("books") is not None and not isinstance(data.get("books"), list)
        ):
            raise HuabenError("invalid_search")
        items = [normalize_book(item) for item in data.get("books") or [] if isinstance(item, dict)]
        return {"items": items, "page": page, "page_size": page_size, "count": len(items)}

    async def get_book(self, book_id: Any) -> dict[str, Any]:
        book_id = _positive_id(book_id)
        data = await self._request_json(f"{API_BASE}/book/read/book", {"bookId": book_id})
        if not isinstance(data, dict) or str(data.get("bookId")) != book_id:
            raise HuabenError("book_mismatch")
        return normalize_book(data)

    async def get_catalog(self, book_id: Any) -> list[dict[str, Any]]:
        book_id = _positive_id(book_id)
        data = await self._request_json(
            f"{API_BASE}/book/read/volume/v2/{book_id}/{time.time_ns() // 1_000_000}"
        )
        if not isinstance(data, dict) or not isinstance(data.get("volumeList"), list):
            raise HuabenError("invalid_catalog")
        # App 阅读页按返回卷序展开 chapterList；旧平铺接口会漏掉彩蛋和番外。
        items: list[dict[str, Any]] = []
        for volume in data["volumeList"]:
            if not isinstance(volume, dict) or not isinstance(volume.get("chapterList"), list):
                raise HuabenError("invalid_catalog")
            items.extend(volume["chapterList"])
        if not items:
            raise HuabenError("empty_catalog")
        chapters: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(items, 1):
            if not isinstance(item, dict):
                raise HuabenError("invalid_catalog")
            chapter_id = _positive_id(item.get("chapterId"))
            if chapter_id in seen or str(item.get("bookId", book_id)) != book_id:
                raise HuabenError("catalog_mismatch")
            seen.add(chapter_id)
            chapters.append(
                {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "index": index,
                    "title": str(item.get("title") or f"第{index}章"),
                    "chapter_type": str(item.get("chapterType") or ""),
                }
            )
        return chapters

    async def get_chapter(
        self,
        book_id: Any,
        chapter_id: Any,
        *,
        meta: dict[str, Any] | None = None,
        attempts: int = 3,
    ) -> dict[str, Any]:
        book_id, chapter_id = _positive_id(book_id), _positive_id(chapter_id)
        meta = meta or {}
        if str(meta.get("chapter_type") or "").upper() in {"PAID", "MEMBER", "VIP"}:
            raise HuabenError("chapter_locked")
        data = await self._request_json(
            f"{API_BASE}/book/read/chapter/content/{book_id}/{chapter_id}/{time.time_ns() // 1_000_000}",
            attempts=attempts,
        )
        if not isinstance(data, dict):
            raise HuabenError("missing_chapter", retryable=True)
        if str(data.get("bookId", book_id)) != book_id or str(
            data.get("chapterId", chapter_id)
        ) != chapter_id:
            raise HuabenError("chapter_mismatch")
        if data.get("chapterLocked") is True or data.get("unlocked") is False:
            raise HuabenError("chapter_locked")
        content = data.get("content")
        if not isinstance(content, str) or not content.strip():
            raise HuabenError("empty_content", retryable=True)
        text = _IMAGE_RE.sub("", content).strip()
        images = [_cover_url(path) for path in _IMAGE_RE.findall(content)]
        return {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "index": meta.get("index"),
            "title": str(data.get("title") or meta.get("title") or ""),
            "text": content,
            "content_text": text,
            "images": images,
            "word_count": data.get("wordCount"),
        }

    async def download_all(
        self, book_id: Any, catalog: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        book_id = _positive_id(book_id)
        if not catalog:
            raise HuabenError("empty_catalog")
        total = len(catalog)
        ceiling = min(self.concurrency, total)
        self.current_concurrency = ceiling
        results: dict[str, dict[str, Any]] = {}
        pending = list(catalog)
        next_progress = 25
        logger.info(f"话本小说下载进度：书籍编号={book_id}, 章节=0/{total}, 并发={ceiling}")

        def adjust_concurrency(batch_count: int, batch_failures: int, before: dict[str, int]) -> None:
            old = self.current_concurrency
            congested = any(
                self.stats[key] > before[key] for key in ("http_429", "http_5xx", "code3")
            ) or batch_failures / max(1, batch_count) >= 0.1
            if congested:
                self.current_concurrency = max(1, old // 2)
            elif not batch_failures:
                self.current_concurrency = min(ceiling, old + max(1, ceiling // 8))
            if old != self.current_concurrency:
                self.concurrency_history.append(
                    {"from": old, "to": self.current_concurrency, "reason": "congested" if congested else "recovered"}
                )
                logger.debug(f"话本小说动态并发：{old}->{self.current_concurrency}")

        for attempt in range(3):
            retry: list[dict[str, Any]] = []
            retry_delay = 0.5 * (2**attempt)
            for start in range(0, len(pending), MAX_CONCURRENCY):
                batch = pending[start : start + MAX_CONCURRENCY]
                queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
                for meta in batch:
                    queue.put_nowait(meta)
                before = dict(self.stats)
                failed_in_batch = 0

                async def worker() -> None:
                    nonlocal failed_in_batch, retry_delay, next_progress
                    while True:
                        try:
                            meta = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return
                        chapter_id = _positive_id(meta.get("chapter_id"))
                        try:
                            chapter = await self.get_chapter(
                                book_id, chapter_id, meta=meta, attempts=1
                            )
                            results[chapter_id] = chapter
                            percent = len(results) * 100 // total
                            if percent >= next_progress and next_progress < 100:
                                logger.info(
                                    f"话本小说下载进度：书籍编号={book_id}, 章节={len(results)}/{total}, "
                                    f"并发={self.current_concurrency}"
                                )
                                next_progress = (percent // 25 + 1) * 25
                        except HuabenError as error:
                            failed_in_batch += 1
                            if error.retryable and attempt < 2:
                                retry.append(meta)
                                retry_delay = max(retry_delay, error.retry_after)
                            logger.debug(
                                f"话本小说章节请求失败：章节编号={chapter_id}, 原因={error.reason}, "
                                f"HTTP={error.status}, code={error.code}"
                            )
                        finally:
                            queue.task_done()

                workers = {
                    asyncio.create_task(worker(), name="mantou-huaben-chapter")
                    for _ in range(min(self.current_concurrency, len(batch)))
                }
                self._workers.update(workers)
                try:
                    await asyncio.gather(*workers)
                finally:
                    for task in workers:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*workers, return_exceptions=True)
                    self._workers.difference_update(workers)
                adjust_concurrency(len(batch), failed_in_batch, before)
            pending = retry
            if not pending:
                break
            self.stats["retries"] += len(pending)
            await asyncio.sleep(retry_delay)
        if len(results) != total:
            raise HuabenError("incomplete_book", missing_count=total - len(results))
        logger.info(f"话本小说下载进度：书籍编号={book_id}, 章节={total}/{total}, 已完成")
        return [results[_positive_id(meta["chapter_id"])] for meta in catalog]

话本小说缓存目录 = 文件缓存工具.小说缓存目录
话本下载失败提示 = "下载失败 请重试"
话本文件发送失败提示 = "文件发送失败，请稍后再试"
_链接正则 = re.compile(r"https?://[^\s<>\"']+", re.I)


def 提取话本书籍编号(来源: Any) -> str:
    文本 = html.unescape(str(来源 or "")).replace("\\/", "/").strip()
    try:
        地址 = urlsplit(文本)
        主机 = (地址.hostname or "").lower().rstrip(".")
        if (
            地址.scheme not in {"http", "https"}
            or 地址.username
            or 地址.password
            or not (主机 == "ihuaben.com" or 主机.endswith(".ihuaben.com"))
        ):
            return ""
        匹配 = re.fullmatch(r"/(?:book|list)/(\d{1,15})(?:\.html)?/?", 地址.path, re.I)
        if 匹配:
            return 匹配.group(1)
        查询 = parse_qs(地址.query)
        for 字段 in ("bookId", "bookid", "book_id"):
            候选 = 查询.get(字段, [])
            if len(候选) == 1 and re.fullmatch(r"\d{1,15}", 候选[0]):
                return 候选[0]
    except ValueError:
        pass
    return ""


def _字段(对象: Any, 名称: str) -> Any:
    return 对象.get(名称) if isinstance(对象, Mapping) else getattr(对象, 名称, None)


def _当前输入文本(event: Any, 命令文本: Any) -> list[str]:
    """仅检查本条文字和分享卡片，跳过引用、作者和提及资料。"""
    文本 = [值 for 值 in (命令文本, _字段(event, "message_str")) if isinstance(值, str)]
    队列 = [(event, 0, False)]
    已见: set[int] = set()
    排除 = {"author", "sender", "user", "member", "mentions", "reply", "quote",
            "message_reference", "msg_elements", "quoted_message", "reference"}
    while 队列 and len(已见) < 256:
        当前, 深度, 卡片 = 队列.pop(0)
        if 当前 is None or 深度 > 8 or id(当前) in 已见:
            continue
        已见.add(id(当前))
        if isinstance(当前, str):
            try:
                当前 = json.loads(当前)
            except (ValueError, TypeError):
                if 卡片:
                    文本.append(当前)
                continue
        if isinstance(当前, (list, tuple)):
            队列.extend((子项, 深度 + 1, 卡片) for 子项 in 当前[:128])
            continue
        类型 = _字段(当前, "type")
        类型 = str(getattr(类型, "value", 类型) or "").lower().removeprefix("componenttype.")
        if 类型 in {"reply", "at", "atall", "forward", "node", "nodes"}:
            continue
        if 类型 in {"json", "ark"}:
            队列.append((_字段(当前, "data"), 深度 + 1, True))
            continue
        if 卡片 and isinstance(当前, Mapping):
            队列.extend((值, 深度 + 1, True) for 键, 值 in 当前.items()
                        if str(键).lower() not in 排除 and isinstance(值, (str, dict, list)))
            continue
        for 名称 in ("content", "text"):
            值 = _字段(当前, 名称)
            if isinstance(值, str):
                文本.append(值)
        for 名称 in ("message_obj", "raw_message", "message", "raw_data", "d", "data", "ark"):
            队列.append((_字段(当前, 名称), 深度 + 1, 名称 == "ark"))
    return 文本


def 提取话本来源(event: Any, 命令文本: Any = "") -> str | None:
    for 文本 in _当前输入文本(event, 命令文本):
        for _ in range(3):
            文本 = html.unescape(文本).replace("\\/", "/")
            for 匹配 in _链接正则.finditer(文本):
                链接 = 匹配.group().rstrip("，。；;）)]}>\\")
                if 提取话本书籍编号(链接):
                    return 链接
            文本 = unquote(文本)
    return None


def 规范化话本书籍信息(书籍编号: str, 详情: Mapping[str, Any]) -> dict[str, Any]:
    字数 = 详情.get("word_count")
    if isinstance(字数, bool) or not isinstance(字数, (int, str)) or not re.fullmatch(r"\d+", str(字数)):
        字数文本 = "未知"
    else:
        数字 = int(字数)
        if 数字 >= 10000:
            万字 = f"{数字 / 10000:.2f}".rstrip("0").rstrip(".")
            字数文本 = f"{万字}万字"
        else:
            字数文本 = f"{数字}字" if 数字 > 0 else "未知"
    状态 = str(详情.get("serial_state_text") or "")
    return {
        "title": str(详情.get("book_name") or f"话本小说{书籍编号}"),
        "author": str(详情.get("author_name") or "未知"),
        "status": "完结" if 状态 in {"完结", "已完结", "完本"} else "连载",
        "word_count": 字数文本,
        "intro": str(详情.get("intro") or "").strip(),
    }


def 生成话本小说文件内容(
    书籍编号: str, 书籍信息: dict[str, Any],
    目录: list[dict[str, Any]], 章节结果: list[dict[str, Any]],
) -> tuple[str, bytes]:
    """先确认全量成功，再直接复用番茄的文件名、声明、头部和编码。"""
    if not 目录 or len(目录) != len(章节结果):
        raise HuabenError("incomplete_chapters")
    输出 = []
    for 序号, (章节, 结果) in enumerate(zip(目录, 章节结果), 1):
        if (
            str(章节.get("chapter_id")) != str(结果.get("chapter_id"))
            or str(结果.get("book_id")) != str(书籍编号)
            or not str(结果.get("text") or "").strip()
        ):
            raise HuabenError("invalid_chapter")
        标题 = 结果.get("title") or 章节.get("title") or f"第{序号}章"
        if not 番茄小说.去除章节正文重复标题(标题, 结果["text"]).strip():
            raise HuabenError("empty_chapter")
        输出.append({"index": 序号, "title": 标题, "content": 结果["text"], "success": True})
    return 番茄小说.生成番茄小说文件内容(书籍编号, 书籍信息, 目录, 输出)


def 写入话本下载缓存文件(文件名: str, 内容: bytes) -> Path:
    话本小说缓存目录.mkdir(parents=True, exist_ok=True)
    安全名称 = Path(番茄小说.清理番茄文件名(文件名)).name
    if not 安全名称.lower().endswith(".txt"):
        安全名称 += ".txt"
    路径 = 话本小说缓存目录 / 安全名称
    for 序号 in range(1000):
        候选 = 路径 if 序号 == 0 else 路径.with_name(f"{路径.stem}_{序号}{路径.suffix}")
        try:
            文件 = 候选.open("xb")
        except FileExistsError:
            continue
        try:
            with 文件:
                文件.write(内容)
            文件缓存工具.标记小说缓存正在使用(候选)
            return 候选
        except BaseException:
            文件缓存工具.删除小说缓存文件(候选)
            raise
    raise RuntimeError("cache_name_conflict")


async def _写入缓存(文件名: str, 内容: bytes) -> Path:
    任务 = asyncio.create_task(asyncio.to_thread(写入话本下载缓存文件, 文件名, 内容))
    try:
        return await asyncio.shield(任务)
    except asyncio.CancelledError:
        # 等待正在写入的文件完成并释放，避免取消后留下无人持有的占用标记。
        try:
            路径 = await 任务
            文件缓存工具.删除小说缓存文件(路径)
        finally:
            raise


async def 生成话本下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取话本书籍编号(来源)
    if not 书籍编号:
        yield 话本下载失败提示
        return
    阶段 = "metadata"
    路径: Path | None = None
    try:
        async with AsyncHuabenClient(concurrency=400) as client:
            结果 = await asyncio.gather(client.get_book(书籍编号), client.get_catalog(书籍编号),
                                       return_exceptions=True)
            for 项 in 结果:
                if isinstance(项, BaseException):
                    raise 项
            详情, 目录 = 结果
            if not 目录:
                raise HuabenError("empty_catalog")
            声明数 = 详情.get("chapter_count")
            if isinstance(声明数, int) and not isinstance(声明数, bool) and 声明数 > 0 and 声明数 != len(目录):
                raise HuabenError("incomplete_catalog")
            书籍信息 = 规范化话本书籍信息(书籍编号, 详情)
            yield 番茄小说.格式化番茄下载提示(书籍信息, len(目录))
            阶段 = "chapters"
            章节结果 = await client.download_all(书籍编号, 目录)
        阶段 = "txt"
        文件名, 内容 = await asyncio.to_thread(生成话本小说文件内容, 书籍编号, 书籍信息, 目录, 章节结果)
        路径 = await _写入缓存(文件名, 内容)
        阶段 = "upload"
        上传 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传.get("success"):
            yield 话本文件发送失败提示
            return
        阶段 = "share"
        发送 = await 小说网盘.发送小说下载结果(event, 书籍信息["title"], 书籍信息["author"],
                                                 上传)
        if not 发送.get("sent"):
            yield str(发送.get("fallback_text") or 话本文件发送失败提示)
    except Exception as exc:
        logger.warning("话本小说处理失败：stage=%s, book_id=%s, error_type=%s, reason=%s, code=%s, http_status=%s",
                       阶段, 书籍编号, type(exc).__name__,
                       exc.reason if isinstance(exc, HuabenError) else "operation_failed",
                       exc.code if isinstance(exc, HuabenError) else None,
                       exc.status if isinstance(exc, HuabenError) else None)
        yield 话本文件发送失败提示 if 阶段 in {"upload", "share"} else 话本下载失败提示
    finally:
        # 统一清理函数会保留等待续传的上传任务，不另开后台备份。
        if 路径 is not None:
            文件缓存工具.删除小说缓存文件(路径)


def 获取话本小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取话本来源(event, 命令文本)
    return 生成话本下载回复流(event, 来源, 配置) if 来源 else None


async def 搜索话本小说(关键词: str, 数量上限: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        上限 = max(1, min(int(数量上限), 30))
        async with AsyncHuabenClient(concurrency=2) as client:
            搜索 = await client.search(关键词, page=1, page_size=上限)
        return [{"platform": "话本", "book_id": str(书["book_id"]),
                 "title": 书["book_name"], "author": 书.get("author_name") or "未知",
                 "url": f"https://www.ihuaben.com/book/{书['book_id']}.html",
                 "word_count": 书.get("word_count"), "chapter_count": 书.get("chapter_count"),
                 "intro": 书.get("intro") or ""}
                for 书 in 搜索.get("items", [])[:上限]
                if str(书.get("book_id") or "").isdigit() and 书.get("book_name")]
    except Exception as exc:
        logger.debug("话本小说搜索失败：error_type=%s", type(exc).__name__)
        return []
