"""话本 App 公开接口：连接复用、明文解析与有界动态章节下载。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any

import aiohttp

try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger(__name__)


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
            "version": "7.5.0",
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
            f"{API_BASE}/book/read/chapter/{book_id}/{time.time_ns() // 1_000_000}"
        )
        if not isinstance(data, list) or not data:
            raise HuabenError("empty_catalog")
        chapters: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(data, 1):
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
