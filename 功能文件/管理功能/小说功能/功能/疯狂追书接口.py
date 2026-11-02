"""疯狂追书 App 接口：异步会话复用、库解密与有界动态章节下载。"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import os
import re
import secrets
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping

import aiohttp
from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad, unpad
from yarl import URL

try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger(__name__)


APP_PKG = "com.dt.fkzs"
APP_NAME = "com_dt_fkzs"
APP_VERSION = "1.4.5"
VERSION_CODE = "37"
CHANNEL = "c1001"
API_HOST = "https://fiction.52leho.com"
OPENAPI_HOST = "http://bookopenapi.zhuishushenqi.com"
MAX_CONCURRENCY = 400
FALLBACK_DERIVE_BASE = "4d60FY1OI-cT8A6ZQKqaWA2zGMlV8fSV7zQI"
OPENAPI_SIGN_SECRET = "BrdUENn5R8gveVcwhZG52qNnrQ4UMNFP"
CHAPTER_GCM_KEY = b"QLRkftCsAGRBrKEhyhsySPjh2sVE8uhb"
CHAPTER_GCM_AAD = b"T8L9VvMjzkKqGNFTSc2nmHL5WxHZRx7q"
APP_HEADERS = {"device-platform": "android", "User-Agent": "android", "app_pkg": APP_PKG}
_ID_RE = re.compile(r"[a-f0-9]{24}")
_CHAPTER_ID_RE = re.compile(r"/chapter/([a-f0-9]{24})(?=[/?#]|$)")
_PLACEHOLDER_MARKERS = (
    "本章为VIP", "本章为付费", "该章节为VIP", "该章为付费", "VIP章节",
    "付费章节", "订阅章节", "需要购买", "购买后可阅读", "订阅后可阅读",
    "开通VIP", "开通会员", "请先登录", "登录后阅读", "暂无正文", "内容不存在",
)


class FkzsError(RuntimeError):
    """固定错误分类；不保存响应原文、请求地址或认证资料。"""

    def __init__(
        self, reason: str, *, code: int | None = None, status: int | None = None,
        retryable: bool = False, retry_after: float = 0, missing_count: int = 0,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        self.missing_count = missing_count


def _id(value: Any) -> str:
    text = str(value or "").strip()
    if not _ID_RE.fullmatch(text):
        raise FkzsError("invalid_id")
    return text


def _numeric_code(value: Any) -> int | None:
    if not isinstance(value, bool) and re.fullmatch(r"-?\d{1,12}", str(value)):
        return int(value)
    return None


def _count(value: Any) -> int:
    number = _numeric_code(value)
    return max(0, number or 0)


def _decode_b64(value: str) -> bytes:
    try:
        text = value.strip().encode("ascii")
        text += b"=" * (-len(text) % 4)
        return base64.b64decode(text, altchars=b"-_", validate=True)
    except (AttributeError, UnicodeEncodeError, binascii.Error, ValueError):
        raise FkzsError("invalid_base64") from None


def encrypt_app_params(params: Mapping[str, Any]) -> str:
    """DES-CBC/PKCS5 请求体；与 App 的固定 a 派生分支一致。"""
    pieces = [
        f"{key}={urllib.parse.quote_plus(str(params[key]))}"
        for key in sorted(params)
        if key and params[key] is not None and str(params[key])
    ]
    key = FALLBACK_DERIVE_BASE[:-7].encode("ascii")
    salt = base64.urlsafe_b64encode(hashlib.md5(key).digest()[:8]).decode("ascii")
    cipher = DES.new(key[:8], DES.MODE_CBC, iv=salt[:8].encode("ascii"))
    ciphertext = cipher.encrypt(pad("&".join(pieces).encode("utf-8"), DES.block_size))
    return "a" + salt + base64.urlsafe_b64encode(ciphertext).decode("ascii") + secrets.choice(
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )


def decrypt_app_response(raw: bytes | str) -> Any:
    """明文 JSON 或 AES-ECB/PKCS7 JSON，使用 PyCryptodome 解密。"""
    try:
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        text = text.strip()
        if not text:
            raise FkzsError("empty_response", retryable=True)
        try:
            return json.loads(text)
        except ValueError:
            pass
        encrypted = _decode_b64(text)
        cipher = AES.new(FALLBACK_DERIVE_BASE[:16].encode("ascii"), AES.MODE_ECB)
        plain = unpad(cipher.decrypt(encrypted), AES.block_size).decode("utf-8")
        return json.loads(plain)
    except (ValueError, UnicodeError, TypeError):
        raise FkzsError("invalid_app_response") from None


def openapi_sign(params: Mapping[str, Any]) -> str:
    text = OPENAPI_SIGN_SECRET + "".join(
        key + str(params[key]) for key in sorted(params) if params[key] not in (None, "")
    )
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def decrypt_chapter_content(encoded: str) -> str:
    """AES-GCM 必须验证认证标签；验证后还原 App 正文字节变换。"""
    raw = _decode_b64(encoded)
    if len(raw) < 28:
        raise FkzsError("invalid_chapter_cipher")
    try:
        cipher = AES.new(CHAPTER_GCM_KEY, AES.MODE_GCM, nonce=raw[:12])
        cipher.update(CHAPTER_GCM_AAD)
        plain = cipher.decrypt_and_verify(raw[12:-16], raw[-16:])
        masks = bytes(
            ((key << 2) ^ (CHAPTER_GCM_KEY[(index + 1) % 32] >> 2)) & 255
            for index, key in enumerate(CHAPTER_GCM_KEY)
        )
        text = bytes(
            (((value << 5) | (value >> 3)) & 255) ^ masks[index & 31]
            for index, value in enumerate(plain)
        ).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise FkzsError("chapter_decrypt_failed") from None
    compact = re.sub(r"\s+", "", text)
    if not compact:
        raise FkzsError("empty_content", retryable=True)
    if len(compact) <= 500 and any(marker in compact for marker in _PLACEHOLDER_MARKERS):
        raise FkzsError("chapter_unavailable")
    return text


def normalize_book(data: Mapping[str, Any], requested_id: str | None = None) -> dict[str, Any]:
    book_id = _id(data.get("book_id") or data.get("_id"))
    if requested_id is not None and book_id != _id(requested_id):
        raise FkzsError("book_mismatch")
    toc_id = data.get("tocId") or data.get("toc_id")
    serial = data.get("isSerial", data.get("is_serial"))
    title = str(data.get("title") or data.get("book_name") or "").strip()
    if not title:
        raise FkzsError("missing_book_title")
    return {
        "book_id": book_id, "toc_id": _id(toc_id) if toc_id else "", "title": title,
        "author": str(data.get("author") or ""),
        "status": "连载" if serial is True else "完结" if serial is False else "未知",
        "word_count": _count(data.get("wordCount", data.get("word_count"))),
        "chapter_count": _count(data.get("chaptersCount", data.get("chapter_count"))),
        "intro": str(data.get("longIntro") or data.get("long_intro") or data.get("shortIntro") or data.get("short_intro") or ""),
        "cover": str(data.get("cover") or ""),
        "category": str(data.get("majorCate") or data.get("major_cate") or data.get("category") or ""),
        "score": (data.get("rating") or {}).get("score") if isinstance(data.get("rating"), Mapping) else data.get("book_score"),
        "read_num": data.get("read_num"),
    }


def _verify_identity(data: Mapping[str, Any], book_id: str, chapter_id: str | None = None, toc_id: str | None = None) -> None:
    for keys, expected in (
        (("book_id", "bookId"), book_id),
        (("chapter_id", "chapterId", "_id") if chapter_id else (), chapter_id),
        (("toc_id", "tocId"), toc_id),
    ):
        if expected:
            for key in keys:
                if key in data and data[key] not in (None, "") and str(data[key]) != expected:
                    raise FkzsError("chapter_mismatch" if chapter_id else "catalog_mismatch")


def normalize_catalog(data: Mapping[str, Any], book_id: str, toc_id: str) -> list[dict[str, Any]]:
    book_id, toc_id = _id(book_id), _id(toc_id)
    _verify_identity(data, book_id, toc_id=toc_id)
    rows = data.get("chapters")
    if not isinstance(rows, list) or not rows:
        raise FkzsError("empty_catalog")
    expected = _count(data.get("chaptersCount", data.get("chapters_count")))
    if expected and expected != len(rows):
        raise FkzsError("incomplete_catalog", missing_count=max(0, expected - len(rows)))
    seen: set[str] = set()
    catalog = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise FkzsError("invalid_catalog")
        _verify_identity(row, book_id, toc_id=toc_id)
        link = row.get("link") or row.get("url")
        if not isinstance(link, str) or len(link) > 8192 or any(ord(c) < 32 for c in link):
            raise FkzsError("invalid_chapter_link")
        match = _CHAPTER_ID_RE.search(link)
        if not match:
            raise FkzsError("invalid_chapter_link")
        chapter_id = _id(match.group(1))
        _verify_identity(row, book_id, chapter_id, toc_id)
        if chapter_id in seen:
            raise FkzsError("duplicate_chapter")
        seen.add(chapter_id)
        catalog.append({
            "book_id": book_id, "toc_id": toc_id, "chapter_id": chapter_id,
            "index": index, "title": str(row.get("title") or row.get("name") or f"第{index}章"),
            "link": link, "locked": bool(row.get("isVip") or row.get("is_vip") or row.get("isLock")),
        })
    return catalog


def _trusted_url(value: str, *, origin: bool = False) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        host = (parsed.hostname or "").lower()
        trusted = any(host == base or host.endswith("." + base) for base in ("52leho.com", "zhuishushenqi.com"))
        if (
            parsed.scheme not in {"http", "https"} or not trusted
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 80, 443) or parsed.fragment
            or (origin and (parsed.path not in ("", "/") or parsed.query))
        ):
            raise ValueError
        return value.rstrip("/") if origin else value
    except (TypeError, ValueError):
        raise FkzsError("invalid_endpoint") from None


class AsyncFkzsClient:
    """一个任务复用一个连接池；设备和登录态仅保留在当前内存。"""

    def __init__(
        self, *, concurrency: int = MAX_CONCURRENCY, api_host: str = API_HOST,
        openapi_host: str = OPENAPI_HOST,
    ) -> None:
        self.concurrency = max(1, min(MAX_CONCURRENCY, int(concurrency)))
        self.current_concurrency = self.concurrency
        self.api_host = _trusted_url(api_host, origin=True)
        self.openapi_host = _trusted_url(openapi_host, origin=True)
        self.session: aiohttp.ClientSession | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._cpu_slots = asyncio.Semaphore(min(32, max(2, os.cpu_count() or 2)))
        self._device_lock = asyncio.Lock()
        self._token_lock = asyncio.Lock()
        self._device_ready = False
        self._device_failure: tuple[float, FkzsError] | None = None
        self._token = ""
        self._token_failure: tuple[float, FkzsError] | None = None
        self._workers: set[asyncio.Task[Any]] = set()
        self._active = 0
        self.common = {
            "app_name": APP_NAME, "app_pkg": APP_PKG, "app_version": APP_VERSION,
            "version_code": VERSION_CODE, "device_id": "", "app_device_id": "", "sm_device_id": "",
            "channel": CHANNEL, "device_brand": "vivo", "device_model": "V2023A", "inner_version": "",
            "uid": "", "uuid": secrets.token_hex(16), "oaid": "", "imei": "", "android_id": secrets.token_hex(8),
            "language": "zh-CN", "os_version": "RP1A.200720.012", "os_api": "30", "dpi": "2.75",
            "carrier": "", "resolution": "1080x2400", "device_platform": "android", "device_type": "android",
            "access": "wifi", "is_debug": "0",
        }
        self.stats = {key: 0 for key in ("requests", "retries", "http_429", "http_5xx", "network_errors", "peak_concurrency")}
        self.concurrency_history: list[dict[str, Any]] = []

    async def __aenter__(self) -> AsyncFkzsClient:
        if self.session is not None:
            raise FkzsError("session_already_open")
        self._executor = ThreadPoolExecutor(max_workers=min(32, max(2, os.cpu_count() or 2)), thread_name_prefix="mantou-fkzs-crypto")
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=self.concurrency, limit_per_host=self.concurrency, ttl_dns_cache=300, keepalive_timeout=30),
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
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self._token = ""
        self._token_failure = None

    async def _cpu(self, function: Any, *args: Any) -> Any:
        if self._executor is None:
            raise FkzsError("session_not_open")
        async with self._cpu_slots:
            return await asyncio.get_running_loop().run_in_executor(self._executor, function, *args)

    async def _http(self, method: str, url: str | URL, *, limit: int = 4 * 1024 * 1024, **kwargs: Any) -> bytes:
        if self.session is None:
            raise FkzsError("session_not_open")
        self.stats["requests"] += 1
        self._active += 1
        self.stats["peak_concurrency"] = max(self.stats["peak_concurrency"], self._active)
        try:
            async with self.session.request(method, url, allow_redirects=False, **kwargs) as response:
                status = response.status
                if status != 200:
                    self.stats["http_429"] += int(status == 429)
                    self.stats["http_5xx"] += int(500 <= status <= 599)
                    try:
                        delay = min(30.0, max(0.0, float(response.headers.get("Retry-After", "0"))))
                    except (ValueError, TypeError):
                        delay = 0.0
                    raise FkzsError("http_error", status=status, retryable=status == 429 or 500 <= status <= 599, retry_after=delay)
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > limit:
                        raise FkzsError("response_too_large")
                return bytes(body)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self.stats["network_errors"] += 1
            raise FkzsError("network_error", retryable=True) from None
        finally:
            self._active -= 1

    async def _app(self, path: str, business: Mapping[str, Any] | None = None, *, attempts: int = 3) -> dict[str, Any]:
        for attempt in range(max(1, attempts)):
            try:
                params = {**self.common, "request_time": str(int(time.time())), **(business or {})}
                encrypted = await self._cpu(encrypt_app_params, params)
                raw = await self._http("POST", self.api_host + path,
                    headers={**APP_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                    data={"app_pkg": APP_PKG, "p": encrypted}, limit=32 * 1024 * 1024)
                payload = await self._cpu(decrypt_app_response, raw)
                if not isinstance(payload, dict):
                    raise FkzsError("invalid_app_response")
                if payload.get("code") not in (0, "0", None):
                    raise FkzsError("app_business_error", code=_numeric_code(payload.get("code")))
                return payload
            except FkzsError as error:
                if not error.retryable or attempt + 1 >= attempts:
                    raise
                self.stats["retries"] += 1
                await asyncio.sleep(max(error.retry_after, 0.5 * 2**attempt))
        raise FkzsError("request_failed")

    async def ensure_device(self) -> None:
        if self._device_ready:
            return
        async with self._device_lock:
            if self._device_ready:
                return
            if self._device_failure and time.monotonic() < self._device_failure[0]:
                raise self._device_failure[1]
            try:
                data = (await self._app("/v1/device/init")).get("data")
                if not isinstance(data, dict) or not data.get("uid") or not data.get("device_id"):
                    raise FkzsError("invalid_device_response")
            except FkzsError as error:
                self._device_failure = (time.monotonic() + max(1, error.retry_after), error)
                raise
            self.common.update(uid=str(data["uid"]), device_id=str(data["device_id"]), app_device_id=str(data["device_id"]))
            self._device_ready = True
            self._device_failure = None

    @property
    def sdk_device_id(self) -> str:
        return base64.b64encode(self.common["android_id"].encode("utf-8")).decode("ascii")

    async def _login(self, old_token: str | None = None) -> str:
        await self.ensure_device()
        async with self._token_lock:
            if self._token and (old_token is None or self._token != old_token):
                return self._token
            if self._token_failure and time.monotonic() < self._token_failure[0]:
                raise self._token_failure[1]
            params = {"userId": str(self.common["uid"] or self.common["uuid"]), "appFlag": APP_PKG, "version": "1"}
            params["sign"] = openapi_sign(params)
            try:
                raw = await self._http("GET", self.openapi_host + "/interc/public/login", params=params, headers={"x-device-id": self.sdk_device_id})
                payload = await self._cpu(_json_object, raw)
                data = payload.get("data")
                token = data.get("token") if isinstance(data, dict) else None
                if payload.get("ok") is not True or not isinstance(token, str) or not token:
                    raise FkzsError("login_failed", code=_numeric_code(payload.get("code")))
            except FkzsError as error:
                self._token_failure = (time.monotonic() + max(1, error.retry_after), error)
                raise
            self._token = token
            self._token_failure = None
            return token

    async def get_book(self, book_id: Any) -> dict[str, Any]:
        book_id = _id(book_id)
        await self.ensure_device()
        data = (await self._app("/v1/book/info", {"book_id": book_id})).get("data")
        book = data.get("book_info") if isinstance(data, dict) else None
        if not isinstance(book, dict):
            raise FkzsError("missing_book")
        return normalize_book(book, book_id)

    async def search(self, keyword: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        keyword = str(keyword or "").strip()
        if not keyword:
            raise FkzsError("empty_keyword")
        page, page_size = max(1, int(page)), max(1, min(50, int(page_size)))
        await self.ensure_device()
        data = (await self._app("/v1/book/mall/search/book", {"search_word": keyword, "page": page, "page_size": page_size})).get("data")
        if not isinstance(data, list):
            raise FkzsError("invalid_search")
        items = [normalize_book(row) for row in data if isinstance(row, Mapping)]
        semaphore = asyncio.Semaphore(2)

        async def enrich(item: dict[str, Any]) -> None:
            if item["author"]:
                return
            async with semaphore:
                try:
                    detail = await self.get_book(item["book_id"])
                except FkzsError:
                    return
                item.update(detail)

        await asyncio.gather(*(enrich(item) for item in items))
        return {"items": items, "page": page, "page_size": page_size, "has_more": len(items) >= page_size}

    async def get_catalog(self, book_id: Any, toc_id: Any = None) -> list[dict[str, Any]]:
        book_id = _id(book_id)
        await self.ensure_device()
        detail = await self.get_book(book_id) if not toc_id else None
        toc_id = _id(toc_id or (detail or {}).get("toc_id"))
        data = (await self._app("/v1/book/toc", {"book_id": book_id, "toc_id": toc_id, "toc_size": 99999999})).get("data")
        if not isinstance(data, dict):
            raise FkzsError("invalid_catalog")
        expected = _count(data.get("chaptersCount", data.get("chapters_count")))
        if not expected and detail:
            expected = detail["chapter_count"]
        rows = data.get("chapters")
        if expected and isinstance(rows, list) and len(rows) < expected:
            cache = (await self._app("/v1/book/chapter", {"book_id": book_id, "toc_id": toc_id})).get("data")
            url = cache.get("chapter_url") if isinstance(cache, dict) else None
            if not isinstance(url, str):
                raise FkzsError("incomplete_catalog", missing_count=expected - len(rows))
            raw = await self._http("GET", _trusted_url(url), headers={"User-Agent": "android"}, limit=32 * 1024 * 1024)
            full = await self._cpu(_json_object, raw)
            if not isinstance(full.get("chapters"), list):
                raise FkzsError("invalid_catalog")
            data = full
        data = dict(data)
        if expected:
            data["chaptersCount"] = max(expected, _count(data.get("chaptersCount", data.get("chapters_count"))))
        return await self._cpu(normalize_catalog, data, book_id, toc_id)

    async def _chapter_once(self, book_id: str, chapter_id: str, meta: Mapping[str, Any]) -> dict[str, Any]:
        _verify_identity(meta, book_id, chapter_id)
        link = meta.get("link")
        if not isinstance(link, str) or len(link) > 8192 or any(ord(char) < 32 for char in link):
            raise FkzsError("invalid_chapter_link")
        match = _CHAPTER_ID_RE.search(link)
        if not match or match.group(1) != chapter_id:
            raise FkzsError("chapter_mismatch")
        params = {"appFlag": APP_PKG, "linkMd5": hashlib.md5(link.encode("utf-8")).hexdigest(), "version": "1"}
        params["sign"] = openapi_sign(params)
        url = URL(self.openapi_host + "/interc/chapter/" + urllib.parse.quote(link, safe="") + "?" + urllib.parse.urlencode(params), encoded=True)
        token = await self._login()
        for token_attempt in range(2):
            raw = await self._http("GET", url, headers={"x-token": token, "x-device-id": self.sdk_device_id}, limit=2 * 1024 * 1024)
            payload = await self._cpu(_json_object, raw)
            if payload.get("ok") is True:
                break
            if payload.get("code") == "TOKEN_INVALID" and token_attempt == 0:
                token = await self._login(token)
                continue
            raise FkzsError("token_invalid" if payload.get("code") == "TOKEN_INVALID" else "chapter_business_error", code=_numeric_code(payload.get("code")))
        chapter = payload.get("chapter")
        if not isinstance(chapter, dict):
            raise FkzsError("missing_chapter", retryable=True)
        _verify_identity(chapter, book_id, chapter_id, meta.get("toc_id"))
        if chapter.get("link") not in (None, "", link):
            raise FkzsError("chapter_mismatch")
        encrypted = chapter.get("cpContent") or chapter.get("chapterContent")
        if not isinstance(encrypted, str) or not encrypted:
            raise FkzsError("empty_content", retryable=True)
        text = await self._cpu(decrypt_chapter_content, encrypted)
        return {"book_id": book_id, "chapter_id": chapter_id, "toc_id": meta.get("toc_id", ""),
                "index": meta.get("index"), "title": str(chapter.get("title") or meta.get("title") or ""), "text": text, "link": link}

    async def get_chapter(self, book_id: Any, chapter_id: Any, *, meta: dict[str, Any] | None = None, attempts: int = 3) -> dict[str, Any]:
        book_id, chapter_id = _id(book_id), _id(chapter_id)
        if meta is None:
            catalog = await self.get_catalog(book_id)
            meta = next((row for row in catalog if row["chapter_id"] == chapter_id), None)
            if meta is None:
                raise FkzsError("chapter_not_found")
        attempts = max(1, min(3, int(attempts)))
        for attempt in range(attempts):
            try:
                return await self._chapter_once(book_id, chapter_id, meta)
            except FkzsError as error:
                if not error.retryable or attempt + 1 >= attempts:
                    raise
                self.stats["retries"] += 1
                await asyncio.sleep(max(error.retry_after, 0.5 * 2**attempt))
        raise FkzsError("request_failed")

    async def download_all(self, book_id: Any, catalog: list[dict[str, Any]], *, toc_id: Any = None) -> list[dict[str, Any]]:
        book_id = _id(book_id)
        if not catalog:
            raise FkzsError("empty_catalog")
        chapter_ids = [_id(meta.get("chapter_id")) for meta in catalog]
        if len(set(chapter_ids)) != len(chapter_ids):
            raise FkzsError("duplicate_chapter")
        for meta in catalog:
            _verify_identity(meta, book_id, _id(meta.get("chapter_id")), _id(toc_id) if toc_id else None)
        await self._login()
        total = len(catalog)
        ceiling = min(self.concurrency, total)
        self.current_concurrency = ceiling
        pending = list(catalog)
        results: dict[str, dict[str, Any]] = {}
        next_progress = 25
        logger.info(f"疯狂追书下载进度：章节=0/{total}, 并发={ceiling}")
        for attempt in range(3):
            retry: list[dict[str, Any]] = []
            retry_delay = 0.5 * 2**attempt
            for start in range(0, len(pending), MAX_CONCURRENCY):
                batch = pending[start:start + MAX_CONCURRENCY]
                queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
                for meta in batch:
                    queue.put_nowait(meta)
                before = dict(self.stats)
                failures = 0

                async def worker() -> None:
                    nonlocal failures, next_progress, retry_delay
                    while True:
                        try:
                            meta = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return
                        chapter_id = meta["chapter_id"]
                        try:
                            results[chapter_id] = await self.get_chapter(book_id, chapter_id, meta=meta, attempts=1)
                            percent = len(results) * 100 // total
                            if percent >= next_progress and next_progress < 100:
                                logger.info(f"疯狂追书下载进度：章节={len(results)}/{total}, 并发={self.current_concurrency}")
                                next_progress = (percent // 25 + 1) * 25
                        except FkzsError as error:
                            failures += 1
                            if error.retryable and attempt < 2:
                                retry.append(meta)
                                retry_delay = max(retry_delay, error.retry_after)
                            logger.debug(f"疯狂追书章节请求失败：原因={error.reason}, HTTP={error.status}, code={error.code}")
                        finally:
                            queue.task_done()

                workers = {asyncio.create_task(worker(), name="mantou-fkzs-chapter") for _ in range(min(self.current_concurrency, len(batch)))}
                self._workers.update(workers)
                try:
                    await asyncio.gather(*workers)
                finally:
                    for task in workers:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*workers, return_exceptions=True)
                    self._workers.difference_update(workers)
                old = self.current_concurrency
                congested = any(self.stats[key] > before[key] for key in ("http_429", "http_5xx")) or failures / len(batch) >= 0.1
                if congested:
                    self.current_concurrency = max(1, old // 2)
                elif not failures:
                    self.current_concurrency = min(ceiling, old + max(1, ceiling // 8))
                if old != self.current_concurrency:
                    self.concurrency_history.append({"from": old, "to": self.current_concurrency, "reason": "congested" if congested else "recovered"})
            pending = retry
            if not pending:
                break
            self.stats["retries"] += len(pending)
            await asyncio.sleep(retry_delay)
        if len(results) != total:
            raise FkzsError("incomplete_book", missing_count=total - len(results))
        logger.info(f"疯狂追书下载进度：章节={total}/{total}, 已完成")
        return [results[chapter_id] for chapter_id in chapter_ids]


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise FkzsError("invalid_json") from None
    if not isinstance(payload, dict):
        raise FkzsError("invalid_response")
    return payload
