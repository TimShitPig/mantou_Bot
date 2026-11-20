"""Sáng Tác Việt App 协议。只处理同源请求和字段解析，不写入账号或文件。"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import ssl
import time
import unicodedata
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlencode

import aiohttp
from yarl import URL

BASE = "https://sangtacviet.app"
_DOMAIN = "sangtacviet.app"
_LEGACY_BASE = "https://sangtacviet.com"
_COOKIE_DOMAINS = frozenset({_DOMAIN, "sangtacviet.com"})
UA = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "x-stv-transport": "app",
    "x-requested-with": "com.sangtacviet.mobilereader",
    "Referer": BASE + "/app.v2.php",
    "Accept": "*/*",
    "Accept-Language": "vi-VN,vi;q=0.9",
}
_PATHS = {
    "/", "/index.php", "/mobile/userinfo.php", "/mobile/jsonify.php",
    "/mobile/bookinfo.php", "/io/searchtp/searchBooks", "/user/0/",
    "/io/grantcontext/context", "/io/user/online", "/io/userinfo/getuseritems",
}
_CONNECTION_POOLS = globals().get("_CONNECTION_POOLS") or {}
_ACCOUNT_QUERY_TIMEOUTS = (30.0, 60.0)
_ACCOUNT_QUERY_RETRY_DELAY = 0.5
_CHAPTER_DOWNLOAD_GATES = globals().get("_CHAPTER_DOWNLOAD_GATES") or {}
STV_DOWNLOAD_CONCURRENCY = 100
_CHAPTER_DOWNLOAD_ATTEMPTS = 3
_CHAPTER_DOWNLOAD_MAX_WAIT = 60.0
_CHAPTER_DOWNLOAD_BUDGET = 120.0
_CHAPTER_KEY_PATH = "/io/grantcontext/context"
_CHAPTER_READ_PATH = "/"


def _acquire_connector() -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    pool = _CONNECTION_POOLS.get(loop)
    if pool is None or pool["connector"].closed or pool["connector"].limit != STV_DOWNLOAD_CONCURRENCY:
        if pool is not None and not pool["connector"].closed and pool["users"] == 0:
            loop.create_task(_close_idle_connector(pool))
        pool = {"loop": loop, "connector": aiohttp.TCPConnector(
            limit=STV_DOWNLOAD_CONCURRENCY, limit_per_host=STV_DOWNLOAD_CONCURRENCY,
            ttl_dns_cache=300, keepalive_timeout=30,
        ), "users": 0, "idle": None}
        _CONNECTION_POOLS[loop] = pool
    if pool["idle"] is not None:
        pool["idle"].cancel()
        pool["idle"] = None
    pool["users"] += 1
    return pool


def _release_connector(pool: dict[str, Any]) -> None:
    pool["users"] -= 1
    if pool["users"] == 0 and not pool["loop"].is_closed():
        pool["idle"] = pool["loop"].call_later(
            30, lambda: pool["loop"].create_task(_close_idle_connector(pool)),
        )


async def _close_idle_connector(expected: dict[str, Any] | None = None) -> None:
    loop = asyncio.get_running_loop()
    pool = expected if expected is not None else _CONNECTION_POOLS.get(loop)
    if pool is not None and pool["users"] == 0:
        if _CONNECTION_POOLS.get(loop) is pool:
            _CONNECTION_POOLS.pop(loop, None)
        if pool["idle"] is not None:
            pool["idle"].cancel()
        await pool["connector"].close()


class STVError(RuntimeError):
    def __init__(self, category: str, http_status: int | None = None, code: Any = None,
                 *, retry_after: float | None = None):
        self.category = category
        self.http_status = http_status
        value = str(code) if isinstance(code, (str, int)) and not isinstance(code, bool) else ""
        self.code = value if re.fullmatch(r"-?\d{1,12}", value) else None
        self.retry_after = retry_after
        super().__init__(category)


def _retry_after_seconds(value: Any, server_date: Any = None) -> float | None:
    if not isinstance(value, str) or len(value) > 128:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]+", value):
        return float(value)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is not None:
            target = parsed.timestamp()
            delay = max(0.0, target - time.time())
            if isinstance(server_date, str) and len(server_date) <= 128:
                try:
                    date = parsedate_to_datetime(server_date)
                    if date.tzinfo is not None:
                        delay = max(delay, target - date.timestamp())
                except (ValueError, TypeError, OverflowError):
                    pass
            return delay
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def _identity(host: Any, bookid: Any) -> tuple[str, str]:
    host, bookid = str(host or "").strip(), str(bookid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", host) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", bookid):
        raise STVError("invalid_input")
    return host, bookid


def _item_id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise STVError("invalid_input")
    value = str(value).strip()
    if not value or len(value) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise STVError("invalid_input")
    return value


def _html_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</(?:p|div)\s*>", "\n\n", value)
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _js_eval(source: str, expression: str | None, data: dict[str, Any] | None = None) -> str:
    """独立无宿主绑定的 JS 环境；网络、文件和 Python 回调均不可用。"""
    try:
        import quickjs
    except ImportError as exc:
        raise STVError("js_runtime_missing") from exc
    try:
        program = POLYFILL + "\n" + MOCK_ENV.replace("__UA__", json.dumps(UA))
        if data is not None:
            program += "\nvar x=" + json.dumps(data, ensure_ascii=True) + ";"
        if expression is None:
            # App 读取 eval 的返回值；当前脚本也可能通过 reader 的 getter 提供密钥。
            program += (
                "\nvar __keyResult = eval(" + json.dumps(source, ensure_ascii=True) + ");\n"
                "typeof __keyResult === 'undefined' && typeof __registered.chapterkey === 'function'"
                " ? __registered.chapterkey.call(app.reader) : __keyResult;"
            )
        else:
            program += "\n" + source + "\n" + expression
        # Windows 由 quickjs-ng 提供相同 API，避免旧 MiniRacer 在实测脚本中耗满时限。
        context = quickjs.Context()
        context.set_memory_limit(96 * 1024 * 1024)
        context.set_max_stack_size(2 * 1024 * 1024)
        context.set_time_limit(5)
        result = context.eval(program)
        if not isinstance(result, str):
            raise STVError("invalid_response")
        return result
    except STVError:
        raise
    except Exception as exc:
        raise STVError("js_decode_failed") from exc


async def _run_js(source: str, expression: str | None, data: dict[str, Any] | None = None) -> str:
    async def execute() -> tuple[bool, Any]:
        try:
            return True, await asyncio.to_thread(_js_eval, source, expression, data)
        except Exception as exc:
            return False, exc

    # 在线程协程内收集异常，避免 Python 3.14 shield 的取消回调提前记录异常栈。
    worker = asyncio.create_task(execute())
    try:
        success, result = await asyncio.shield(worker)
    except asyncio.CancelledError:
        # JS 本身有 5 秒上限；退出会话前回收线程，避免取消后悬挂执行。
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
        raise
    if not success:
        raise result
    return result


class STVClient:
    """一次会话保存一个账号的 Cookie；正文 key 与 readcontextid 始终成对使用。"""

    def __init__(self, cookies: list[dict[str, Any]] | None = None, uid: str = "",
                 *, chapter_download: bool = False):
        if uid and not re.fullmatch(r"[1-9]\d*", str(uid)):
            raise STVError("invalid_input")
        self.uid = str(uid)
        self._initial_cookies = list(cookies or [])
        self.session: aiohttp.ClientSession | None = None
        self._connection_pool: dict[str, Any] | None = None
        self._reading_lock = asyncio.Lock()
        self._key_target: tuple[str, str] | None = None
        self._key = ""
        self._key_context = ""
        self._reward_offer: tuple[str, float] | None = None
        self.mutation_guard = None
        self._chapter_download = chapter_download

    async def __aenter__(self) -> STVClient:
        jar = aiohttp.CookieJar()
        for item in self._initial_cookies:
            if not isinstance(item, dict):
                raise STVError("invalid_cookie")
            name, value = item.get("name"), item.get("value")
            domain = str(item.get("domain") or "sangtacviet.com").lstrip(".")
            path = str(item.get("path") or "/")
            if (
                not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", name)
                or not isinstance(value, str) or len(value) > 16384
                or any(ord(c) < 32 or ord(c) == 127 for c in value)
                or domain not in _COOKIE_DOMAINS or not path.startswith("/") or len(path) > 300
                or name in {"readcontextid", "transmode", "foreignlang"}
            ):
                raise STVError("invalid_cookie")
            cookie = SimpleCookie()
            cookie[name] = value
            # 官方 App 在已确认的域名间携带同一登录态；旧会话仅定向迁至当前网关。
            cookie[name]["domain"] = _DOMAIN
            cookie[name]["path"] = path
            cookie[name]["secure"] = bool(item.get("secure", True))
            if item.get("expires"):
                cookie[name]["expires"] = str(item["expires"])
            jar.update_cookies(cookie, response_url=URL(BASE + path))
        jar.update_cookies({"mac_tt": "true", "transmode": "chinese", "foreignlang": "vi"}, response_url=URL(BASE))
        self._connection_pool = _acquire_connector()
        try:
            self.session = aiohttp.ClientSession(
                headers=HEADERS, cookie_jar=jar,
                connector=self._connection_pool["connector"], connector_owner=False,
                timeout=aiohttp.ClientTimeout(total=60, sock_connect=15, sock_read=45),
            )
        except BaseException:
            _release_connector(self._connection_pool)
            self._connection_pool = None
            raise
        if hasattr(self.session, "_retry_connection"):
            self.session._retry_connection = False
        return self

    async def __aexit__(self, *args: Any) -> None:
        try:
            if self.session is not None:
                await self.session.close()
        finally:
            self.session = None
            self._clear_reading_key()
            if self._connection_pool is not None:
                _release_connector(self._connection_pool)
                self._connection_pool = None

    def _session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            raise STVError("session_closed")
        return self.session

    def _has_access(self) -> bool:
        value = self._session().cookie_jar.filter_cookies(URL(BASE)).get("access")
        return bool(value and len(value.value) >= 32)

    def export_cookies(self) -> list[dict[str, Any]]:
        return [
            {"name": value.key, "value": value.value, "domain": value["domain"] or _DOMAIN,
             "path": value["path"] or "/", "secure": bool(value["secure"]), "expires": value["expires"]}
            for value in self._session().cookie_jar
            if value["domain"].lstrip(".") == _DOMAIN
            and value.key not in {"readcontextid", "transmode", "foreignlang"}
        ]

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None, *, limit: int = 16 * 1024 * 1024,
        mutation: bool = False, account: bool = False,
    ) -> tuple[str, dict[str, str]]:
        chapter_read = path == _CHAPTER_KEY_PATH or (
            path in {_CHAPTER_READ_PATH, "/index.php"} and (params or {}).get("sajax") == "readchapter"
        )
        if not (self._chapter_download and method == "GET" and chapter_read and not mutation and not account):
            return await self._request_once(method, path, params, data, limit=limit, mutation=mutation, account=account)
        loop = asyncio.get_running_loop()
        gate = _CHAPTER_DOWNLOAD_GATES.setdefault(
            loop, {"cooldown_until": 0.0},
        )
        # 热重载可保留旧串行门的冷却截止时间，但不再保留主动请求间隔。
        if "semaphore" not in gate:
            gate["semaphore"] = asyncio.Semaphore(STV_DOWNLOAD_CONCURRENCY)
        deadline = time.monotonic() + _CHAPTER_DOWNLOAD_BUDGET
        last_error = None
        try:
            async with asyncio.timeout(_CHAPTER_DOWNLOAD_BUDGET):
                for attempt in range(1, _CHAPTER_DOWNLOAD_ATTEMPTS + 1):
                    async with gate["semaphore"]:
                        while True:
                            now = time.monotonic()
                            delay = max(0.0, gate["cooldown_until"] - now)
                            if delay > _CHAPTER_DOWNLOAD_MAX_WAIT or now + delay >= deadline:
                                raise last_error or STVError("rate_limited")
                            if not delay:
                                break
                            await asyncio.sleep(delay)
                        try:
                            return await self._request_once(method, path, params, data, limit=limit)
                        except STVError as exc:
                            if exc.category != "rate_limited" or exc.http_status != 429:
                                raise
                            last_error = exc
                            delay = exc.retry_after if exc.retry_after is not None else 5.0 * 2 ** (attempt - 1)
                            gate["cooldown_until"] = max(gate["cooldown_until"], time.monotonic() + delay)
                            if attempt == _CHAPTER_DOWNLOAD_ATTEMPTS or delay > _CHAPTER_DOWNLOAD_MAX_WAIT:
                                raise
        except asyncio.TimeoutError:
            raise last_error or STVError("timeout") from None
        raise last_error or STVError("rate_limited")

    async def _request_once(
        self, method: str, path: str, params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None, *, limit: int = 16 * 1024 * 1024,
        mutation: bool = False, account: bool = False,
    ) -> tuple[str, dict[str, str]]:
        if path not in _PATHS or method not in {"GET", "POST"}:
            raise STVError("invalid_endpoint")
        query = urlencode(params or {})
        url = URL(BASE + path + ("?" + query if query else ""), encoded=True)
        headers = {"Origin": BASE, "Content-Type": "application/x-www-form-urlencoded"} if method == "POST" else {}
        if query:
            canonical = "".join(part + "&" for part in sorted(query.replace("?", "").split("&")))
            headers["X-STV-Sign"] = hashlib.md5((canonical + "erogh982^%*%^*").encode()).hexdigest()
        if mutation and self.mutation_guard is not None and self.mutation_guard() is False:
            raise PermissionError("STV管理权限已失效")
        try:
            async with self._session().request(
                method, url, data=data, headers=headers, allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=30 if account else 60, sock_connect=15, sock_read=30 if account else 45),
            ) as response:
                if response.status in {401, 403} and account:
                    raise STVError("credential_invalid" if response.status == 401 else "verification_required", response.status)
                if response.status != 200:
                    category = "operation_unconfirmed" if mutation else (
                        "verification_required" if 300 <= response.status < 400 else
                        "rate_limited" if response.status == 429 else "http_error"
                    )
                    raise STVError(
                        category, response.status,
                        retry_after=_retry_after_seconds(
                            response.headers.get("Retry-After"), response.headers.get("Date"),
                        ) if response.status == 429 else None,
                    )
                raw = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    if len(raw) + len(chunk) > limit:
                        raise STVError("operation_unconfirmed" if mutation else "response_too_large", 200)
                    raw.extend(chunk)
                body = raw.decode("utf-8-sig", "strict")
                if account and (body.strip().lower() == "captcha" or body.lstrip().lower().startswith(("<!doctype", "<html"))):
                    raise STVError("verification_required", 200)
                return body, dict(response.headers)
        except STVError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, UnicodeError) as exc:
            category = "operation_unconfirmed" if mutation else "timeout" if isinstance(exc, asyncio.TimeoutError) else "network_error"
            raise STVError(category) from exc

    @staticmethod
    def _json(body: str, *, mutation: bool = False, prefix: bool = False) -> dict[str, Any]:
        try:
            if prefix and not body.lstrip().startswith("{"):
                start = body.find("{")
                if start >= 0:
                    body = body[start:]
            value = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise STVError("operation_unconfirmed" if mutation else "invalid_response", 200) from exc
        if not isinstance(value, dict):
            raise STVError("operation_unconfirmed" if mutation else "invalid_response", 200)
        return value

    @staticmethod
    def _code(data: dict[str, Any], expected: str, *, account: bool = False) -> None:
        code = str(data.get("code"))
        if code != expected:
            raise STVError("credential_invalid" if account or code in {"2", "12"} else "business_error", 200, data.get("code"))

    async def search(self, keyword: str, page: int = 0) -> list[dict[str, Any]]:
        if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 500 or isinstance(page, bool) or not isinstance(page, int) or page < 0:
            raise STVError("invalid_input")
        body, _ = await self._request("GET", "/io/searchtp/searchBooks", {
            "method": "search", "minc": 0, "category": "", "findinname": keyword,
            "find": "", "sort": "", "host": "", "tag": "", "step": "", "p": page,
        })
        data = self._json(body)
        self._code(data, "100")
        if not isinstance(data.get("list"), list) or any(not isinstance(item, dict) for item in data["list"]):
            raise STVError("invalid_response", 200)
        return data["list"]

    async def recommended(self) -> list[dict[str, str]]:
        body, _ = await self._request("GET", "/io/searchtp/searchBooks", {
            "method": "search", "find": "", "findinname": "", "category": "", "host": "",
            "minc": 50, "sort": "auto", "step": 5, "tag": "", "p": 0,
        })
        data = self._json(body)
        if data.get("message") or data.get("text") or not isinstance(data.get("list"), list):
            raise STVError("invalid_response", 200)
        books, known = [], set()
        for item in data["list"]:
            if not isinstance(item, dict):
                continue
            try:
                host, bookid = _identity(item.get("host"), item.get("id"))
            except STVError:
                continue
            if (host, bookid) not in known:
                known.add((host, bookid))
                books.append({"host": host, "id": bookid, "name": str(item.get("name") or item.get("tname") or item.get("hname") or bookid)})
        if not books:
            raise STVError("empty_response", 200)
        return books

    async def detail(self, host: str, bookid: str) -> dict[str, Any]:
        host, bookid = _identity(host, bookid)
        body, _ = await self._request("GET", "/mobile/bookinfo.php", {"host": host, "hid": bookid})
        data = self._json(body)
        if str(data.get("code")) == "101":
            raise STVError("book_unavailable", 200, data.get("code"))
        self._code(data, "100")
        if not isinstance(data.get("book"), dict):
            raise STVError("invalid_response", 200)
        return data["book"]

    async def catalog(self, host: str, bookid: str) -> list[dict[str, str]]:
        host, bookid = _identity(host, bookid)
        body, _ = await self._request("GET", "/index.php", {"ngmar": "chapterlist", "h": host, "bookid": bookid, "sajax": "getchapterlist"})
        data = self._json(body)
        self._code(data, "1")
        if data.get("enckey"):
            if not isinstance(data["enckey"], str) or len(data["enckey"]) > 2 * 1024 * 1024:
                raise STVError("invalid_response", 200)
            decoded = await _run_js("eval(atob(x.enckey));", "JSON.stringify(x)", data)
            data = self._json(decoded)
        raw = data.get("oridata") or data.get("data") or ""
        if not isinstance(raw, str):
            raise STVError("invalid_response", 200)
        result, known = [], set()
        for entry in raw.strip().split("-//-"):
            if not entry.strip():
                continue
            fields = entry.strip().split("-/-")
            if len(fields) < 3 or not fields[1].strip() or fields[1].strip() in known:
                raise STVError("invalid_response", 200)
            cid = _item_id(fields[1])
            known.add(cid)
            result.append({"cid": cid, "title": fields[2].strip()})
        if not result:
            raise STVError("catalog_empty", 200)
        return list(reversed(result)) if host == "uukanshu" else result

    def _clear_reading_key(self) -> None:
        self._key, self._key_target, self._key_context = "", None, ""

    def _reading_context(self) -> str:
        cookie = self._session().cookie_jar.filter_cookies(URL(BASE)).get("readcontextid")
        return cookie.value if cookie is not None else ""

    async def _chapter_key(self, host: str, bookid: str) -> str:
        # 取密钥可能同时更新 readcontextid，旧密钥不能再与新上下文配对。
        self._clear_reading_key()
        body, _ = await self._request("GET", _CHAPTER_KEY_PATH, {"hostid": host, "bookid": bookid}, limit=2 * 1024 * 1024)
        context = self._reading_context()
        script = body.lstrip()
        if not context or not script or script.startswith("<"):
            raise STVError("invalid_response", 200)
        key = await _run_js(body, None)
        if (not key or len(key) > 16384 or key.strip() != key or key in {"undefined", "null"}
                or re.search(r"[\x00-\x1f\x7f-\x9f]", key) or self._reading_context() != context):
            raise STVError("invalid_response", 200)
        self._key, self._key_target, self._key_context = key, (host, bookid), context
        return key

    async def _chapter_raw(self, host: str, bookid: str, cid: str) -> dict[str, Any]:
        if (self._key_target != (host, bookid) or not self._key
                or not self._key_context or self._key_context != self._reading_context()):
            self._clear_reading_key()
            raise STVError("invalid_response")
        # App 原生阅读直接提交绝对 URL，根路径不会被通用请求层改写。
        body, _ = await self._request("GET", _CHAPTER_READ_PATH, {"sajax": "readchapter", "h": host, "bookid": bookid, "c": cid, "key": self._key})
        return self._json(body, prefix=True)

    def _chapter_code(self, data: dict[str, Any]) -> None:
        code = str(data.get("code"))
        if code == "0":
            return
        category = (
            "credential_invalid" if code in {"2", "12"} and self.uid else
            "login_required" if code in {"2", "12"} else
            "paid_chapter" if code == "13" else
            "verification_required" if code in {"7", "15", "18", "19", "21"} else
            "business_error"
        )
        raise STVError(category, 200, data.get("code"))

    async def chapter(self, host: str, bookid: str, cid: str, *, reward_reading: bool = False) -> dict[str, Any]:
        host, bookid = _identity(host, bookid)
        cid = _item_id(cid)
        async with self._reading_lock:
            jar = self._session().cookie_jar
            origin = URL(BASE)
            saved_mode = jar.filter_cookies(origin).get("transmode")
            old_mode = saved_mode.value if saved_mode is not None else "chinese"
            try:
                # App 默认 vp 对应 name；下载仅在中文提取失败时尝试原文模式。
                modes = ("name",) if reward_reading else ("name", "chinese")
                refreshed = False
                for mode in modes:
                    jar.update_cookies({"transmode": mode}, response_url=origin)
                    if self._key_target != (host, bookid) or not self._key:
                        await self._chapter_key(host, bookid)
                    data = await self._chapter_raw(host, bookid, cid)
                    if not refreshed and str(data.get("code")) in {"10001", "10002"}:
                        refreshed = True
                        await self._chapter_key(host, bookid)
                        data = await self._chapter_raw(host, bookid, cid)
                    self._chapter_code(data)
                    try:
                        content = html_to_chinese_text(data.get("data") or "")
                    except (ValueError, TypeError) as exc:
                        if mode == modes[-1]:
                            raise STVError("chinese_body_missing", 200) from exc
                        continue
                    if not content.strip():
                        raise STVError("chapter_empty", 200)
                    return {"title": str(data.get("chaptername") or ""), "content": content,
                            "reward_token_count": len(re.findall(r"<i(?:\s|>)", data.get("data") or "", re.IGNORECASE))}
            finally:
                jar.update_cookies({"transmode": old_mode}, response_url=origin)


    async def chapter_batch(self, host: str, bookid: str, chapter_ids: list[str]) -> list[dict[str, Any] | None]:
        """同一会话最多100路读取；切模式或刷新密钥前等待本批请求全部结束。"""
        host, bookid = _identity(host, bookid)
        if not self._chapter_download or not 0 < len(chapter_ids) <= STV_DOWNLOAD_CONCURRENCY:
            raise STVError("invalid_input")
        chapter_ids = [_item_id(cid) for cid in chapter_ids]

        async def fetch(indices: list[int]) -> list[dict[str, Any]]:
            tasks = [asyncio.create_task(self._chapter_raw(host, bookid, chapter_ids[index])) for index in indices]
            try:
                return await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        async with self._reading_lock:
            jar = self._session().cookie_jar
            origin = URL(BASE)
            saved_mode = jar.filter_cookies(origin).get("transmode")
            old_mode = saved_mode.value if saved_mode is not None else "chinese"
            results: list[dict[str, Any] | None] = [None] * len(chapter_ids)
            pending = list(range(len(chapter_ids)))
            refreshed: set[int] = set()
            try:
                for mode in ("name", "chinese"):
                    jar.update_cookies({"transmode": mode}, response_url=origin)
                    if self._key_target != (host, bookid) or not self._key:
                        await self._chapter_key(host, bookid)
                    data = await fetch(pending)
                    renew = [offset for offset, item in enumerate(data)
                             if pending[offset] not in refreshed and str(item.get("code")) in {"10001", "10002"}]
                    if renew:
                        await self._chapter_key(host, bookid)
                        indices = [pending[offset] for offset in renew]
                        refreshed.update(indices)
                        for offset, item in zip(renew, await fetch(indices)):
                            data[offset] = item
                    fallback = []
                    for index, item in zip(pending, data):
                        try:
                            self._chapter_code(item)
                        except STVError as exc:
                            if exc.category in {"login_required", "paid_chapter", "content_unavailable"}:
                                continue
                            raise
                        try:
                            content = html_to_chinese_text(item.get("data") or "")
                        except (ValueError, TypeError) as exc:
                            if mode == "chinese":
                                raise STVError("chinese_body_missing", 200) from exc
                            fallback.append(index)
                            continue
                        if not content.strip():
                            raise STVError("chapter_empty", 200)
                        results[index] = {"title": str(item.get("chaptername") or ""), "content": content,
                                          "reward_token_count": len(re.findall(r"<i(?:\s|>)", item.get("data") or "", re.IGNORECASE))}
                    if not fallback:
                        break
                    pending = fallback
                return results
            finally:
                jar.update_cookies({"transmode": old_mode}, response_url=origin)


    def _clear_account(self) -> None:
        self._session().cookie_jar.clear(lambda cookie: cookie.key in {"access", "useri2", "readcontextid"})
        self._clear_reading_key()
        self.uid, self._reward_offer = "", None

    async def account_info(self) -> dict[str, Any]:
        if not self._has_access():
            raise STVError("credential_invalid")
        body, _ = await self._request("POST", "/mobile/userinfo.php", data="", limit=1024 * 1024, account=True)
        info = self._json(body)
        code = str(info.get("code"))
        if code in {"101", "2", "12", "401"}:
            raise STVError("credential_invalid", 200, info.get("code"))
        if code != "400":
            raise STVError("business_error" if isinstance(info.get("code"), (str, int)) else "invalid_response", 200, info.get("code"))
        uid = str(info.get("id") or "")
        if not re.fullmatch(r"[1-9]\d*", uid) or not self._has_access() or (self.uid and self.uid != uid):
            raise STVError("credential_invalid", 200)
        self.uid = uid
        return info

    @staticmethod
    def _credentials(username: str, password: str) -> None:
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password or len(username) > 500 or len(password) > 1000:
            raise STVError("invalid_input")

    async def login(self, username: str, password: str) -> dict[str, Any]:
        self._credentials(username, password)
        self._clear_account()
        body, _ = await self._request("POST", "/index.php", {"ajax": "login"}, {"username": username, "psw": password}, mutation=True, account=True, limit=1024 * 1024)
        if body.strip() != "success" or not self._has_access():
            raise STVError("credential_invalid", 200)
        return await self.account_info()

    async def register(self, username: str, password: str, repeat_password: str) -> dict[str, Any]:
        self._credentials(username, password)
        if password != repeat_password:
            raise STVError("password_mismatch")
        self._clear_account()
        body, _ = await self._request("POST", "/index.php", {"ajax": "register"}, {"username": username, "psw": password, "repsw": repeat_password}, mutation=True, account=True, limit=1024 * 1024)
        if body.strip() != "success":
            raise STVError("registration_rejected", 200)
        result: dict[str, Any] = {"registered": True, "logged_in": False, "info": None}
        if self._has_access():
            try:
                info = await self.account_info()
            except STVError:
                return result
            result.update(logged_in=True, info=info)
        return result

    async def heartbeat(self) -> dict[str, Any]:
        if not self.uid:
            await self.account_info()
        if not self._has_access():
            raise STVError("credential_invalid")
        await self._request("POST", "/index.php", {"ngmar": "onl2", "u": self.uid}, {"sajax": "online"}, account=True, limit=1024 * 1024)
        return await self.account_info()

    async def reward_status(self) -> bool:
        if not self.uid:
            await self.account_info()
        if not self._has_access():
            raise STVError("credential_invalid")
        self._reward_offer = None
        body, headers = await self._request("POST", "/io/user/online", {"ngmar": "ol2", "u": self.uid}, {"sajax": "online", "ngmar": "ol"}, account=True, limit=1024 * 1024)
        if "Bạn chưa đăng nhập" in body:
            raise STVError("credential_invalid", 200)
        available = next((value for key, value in headers.items() if key.lower() == "x-col"), "") == "1"
        if available:
            self._reward_offer = (self.uid, time.monotonic())
        return available

    def _reward_json(self, body: str) -> dict[str, Any]:
        data = self._json(body, mutation=True)
        reason = data.get("err")
        if (str(data.get("code")) != "1" and isinstance(reason, str)
                and unicodedata.normalize("NFC", reason).strip().casefold() in {
                    "bạn chưa đăng nhập", "bạn chưa đăng nhập!",
                }):
            raise STVError("reward_login_required", 200, data.get("code"))
        return data

    async def collect_reward(self, cid: str) -> dict[str, Any]:
        cid = _item_id(cid)
        offer, self._reward_offer = self._reward_offer, None
        if not self._has_access() or not self.uid:
            raise STVError("credential_invalid")
        if not offer or offer[0] != self.uid or not 0 <= time.monotonic() - offer[1] <= 300:
            raise STVError("reward_unavailable")
        body, _ = await self._request("POST", "/index.php", {"ngmar": "collect"}, {"sajax": "collect"}, mutation=True, account=True, limit=1024 * 1024)
        item = self._reward_json(body)
        if not all(key in item for key in ("name", "info", "level", "type")) or not isinstance(item["name"], str) or not item["name"].strip() or not isinstance(item["info"], str):
            raise STVError("operation_unconfirmed", 200)
        form = {"ajax": "fcollect", "c": cid}
        if str(item["type"]) in {"3", "4"}:
            name, info = _html_text(item["name"]), _html_text(item["info"])
            if len(name) > 80:
                raise STVError("operation_unconfirmed", 200)
            form.update(newname=name, newinfo=info)
        body, _ = await self._request("POST", "/index.php", {"ngmar": "fcl"}, form, mutation=True, account=True, limit=1024 * 1024)
        result = self._reward_json(body)
        code = result.get("code")
        if (not isinstance(code, (str, int)) or isinstance(code, bool)
                or not re.fullmatch(r"-?[0-9]{1,12}", str(code))):
            raise STVError("operation_unconfirmed", 200)
        collected = str(code) == "1"
        category = ""
        if not collected:
            reason = result.get("err")
            reason = unicodedata.normalize("NFC", reason).strip().casefold() if isinstance(reason, str) else ""
            category = {
                "cơ duyên của ngươi đã bay mất, thật xui xẻo.": "reward_expired",
                "không nhặt được gì": "reward_not_found",
            }.get(reason, "reward_rejected")
        outcome = {"collected": collected, "cid": cid, "item": item, "result": result, "category": category}
        if collected:
            # 预览不代表入包；只在 fcollect 明确成功后记录服务端实际物品资料。
            name = "".join(" " if unicodedata.category(char).startswith("C") else char
                           for char in _html_text(item["name"]))
            name = _inventory_name_text(name)
            reward = {"name": name if len(name) <= 80 else "名称暂未翻译"}
            level = item.get("level")
            if isinstance(level, (str, int)) and not isinstance(level, bool) and re.fullmatch(r"[0-9]{1,12}", str(level)):
                reward["level"] = int(level)
            # 已核实 collect 只返回 name/info/level/type，没有数量；不得猜成一个。
            outcome["reward"] = reward
        return outcome

    async def cultivation(self) -> dict[str, Any]:
        try:
            body, _ = await self._account_query("/user/0/", account=False, limit=2 * 1024 * 1024)
        except STVError as exc:
            if exc.http_status in {401, 403}:
                failure = STVError("credential_invalid" if exc.http_status == 401 else "verification_required", exc.http_status)
                for field in ("request_stage", "attempts", "timeout_kind"):
                    if hasattr(exc, field):
                        setattr(failure, field, getattr(exc, field))
                raise failure from exc
            raise
        if not self._has_access():
            raise STVError("credential_invalid")
        try:
            return _parse_cultivation_profile(body, self.uid)
        except ValueError as exc:
            raise STVError("invalid_response", 200) from exc

    async def breakthrough(self) -> dict[str, Any]:
        before = await self.cultivation()
        if not before["breakthrough_available"]:
            raise STVError("breakthrough_unavailable")
        body, _ = await self._request("POST", "/index.php", {"ngmar": "dotphavo"}, {"ajax": "dotphavothan"}, mutation=True, account=True, limit=1024 * 1024)
        result: dict[str, Any] = {"success": body.strip() == "success", "before": before, "after": None, "refresh_error": None}
        try:
            result["after"] = await self.cultivation()
        except STVError:
            result["refresh_error"] = "refresh_failed"
        return result

    async def inventory(self) -> dict[str, Any]:
        # App getinv 会把官网已有物品返回为空，使用官网同账号的库存和激活列表。
        if not self._has_access():
            raise STVError("credential_invalid")
        checked = None
        if not self.uid:
            checked = await self.account_info()
        uid = self.uid
        if not re.fullmatch(r"[1-9]\d*", uid):
            raise STVError("credential_invalid")
        tasks = [
            asyncio.create_task(self._request("POST", "/io/userinfo/getuseritems", {"uid": uid}, "", account=True, limit=2 * 1024 * 1024)),
            asyncio.create_task(self._request("POST", "/index.php", {"ngmar": "getactiv"}, {"ajax": "getactivateditem"}, account=True, limit=2 * 1024 * 1024)),
        ]
        if checked is None:
            tasks.append(asyncio.create_task(self.account_info()))
        try:
            responses = await asyncio.gather(*tasks)
            identity = checked if checked is not None else responses[2]
            if str(identity.get("id") or "") != uid or self.uid != uid or not self._has_access():
                raise STVError("credential_invalid", 200)
            return {"list": _parse_inventory_fragment(responses[0][0]),
                    "act": _parse_inventory_fragment(responses[1][0], active=True)}
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _account_query(self, path: str, params: dict[str, Any] | None = None,
                             **kwargs: Any) -> tuple[str, dict[str, str]]:
        """仅修为查询的身份与资料各恢复一次；成功子请求不重复，总预算不增加。"""
        if path != "/user/0/" or params or kwargs.get("mutation"):
            raise STVError("invalid_endpoint")
        fixed_uid = self.uid

        def validate() -> None:
            self._session()
            if not self._has_access() or self.uid != fixed_uid:
                raise STVError("credential_invalid")
            if self.mutation_guard is not None and self.mutation_guard() is False:
                raise PermissionError("STV管理权限已失效")

        async def identity() -> dict[str, Any]:
            nonlocal fixed_uid
            info = await self.account_info()
            uid = str(info.get("id") or "")
            if not re.fullmatch(r"[1-9]\d*", uid) or self.uid != uid or (fixed_uid and fixed_uid != uid):
                raise STVError("credential_invalid", 200)
            fixed_uid = uid
            return info

        def causes(exc: Exception) -> list[BaseException]:
            chain = []
            while exc is not None and all(exc is not item for item in chain) and len(chain) < 16:
                chain.append(exc)
                exc = exc.__cause__
            return chain

        def retryable(exc: Exception) -> bool:
            chain = causes(exc)
            if any(isinstance(item, (ssl.SSLError, aiohttp.ClientSSLError, aiohttp.ServerFingerprintMismatch,
                                     UnicodeError, aiohttp.InvalidURL)) for item in chain):
                return False
            if isinstance(exc, STVError) and (
                exc.category not in {"timeout", "network_error"} or exc.http_status is not None or exc.code is not None
            ):
                return False
            return any(isinstance(item, (asyncio.TimeoutError, aiohttp.ClientConnectionError,
                                          aiohttp.ClientPayloadError)) for item in chain)

        def timeout_kind(exc: Exception) -> str:
            chain = causes(exc)
            if any(isinstance(item, getattr(aiohttp, "ConnectionTimeoutError", ())) for item in chain):
                return "connection_timeout"
            if any(isinstance(item, getattr(aiohttp, "SocketTimeoutError", ())) for item in chain):
                return "read_timeout"
            return "total_timeout" if any(isinstance(item, asyncio.TimeoutError) for item in chain) else "none"

        async def read(operation: Any, stage: str, budget: float) -> Any:
            attempts = 1
            kind = "none"
            total = asyncio.timeout(budget)
            try:
                async with total:
                    for attempts in (1, 2):
                        remaining = max(0.0, total.when() - asyncio.get_running_loop().time())
                        attempt = asyncio.timeout(min(budget / 2, remaining) if attempts == 1 else remaining)
                        try:
                            async with attempt:
                                validate()
                                result = await operation()
                                validate()
                                return result
                        except asyncio.TimeoutError as exc:
                            failure = STVError("timeout")
                            failure.__cause__ = exc
                            kind = "attempt_timeout" if attempt.expired() else timeout_kind(exc)
                        except Exception as exc:
                            failure = exc
                            kind = timeout_kind(exc)
                        if attempts == 2 or not retryable(failure):
                            raise failure
                        # 等待、排队及两次请求均在同一个原始总预算中；取消直接传播。
                        await asyncio.sleep(_ACCOUNT_QUERY_RETRY_DELAY)
            except asyncio.TimeoutError as exc:
                failure = STVError("timeout")
                failure.__cause__ = exc
                kind = "total_timeout" if total.expired() else timeout_kind(exc)
            except Exception as exc:
                failure = exc
            else:
                raise RuntimeError("STV只读查询未返回结果")
            failure.request_stage = stage
            failure.attempts = attempts
            failure.timeout_kind = kind
            raise failure

        tasks = [asyncio.create_task(read(identity, "account_info", _ACCOUNT_QUERY_TIMEOUTS[0])),
                 asyncio.create_task(read(lambda: self._request("GET", path, params, **kwargs),
                                          "cultivation_page", _ACCOUNT_QUERY_TIMEOUTS[1]))]
        try:
            _, result = await asyncio.gather(*tasks)
            validate()
            return result
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    @staticmethod
    def _find_item(data: dict[str, Any], item_id: str) -> tuple[dict[str, Any], bool]:
        found = []
        for field in ("list", "act"):
            matches = [item for item in data[field] if item.get("i") is not None and str(item["i"]).strip() == item_id]
            if len(matches) > 1:
                raise STVError("ambiguous_item")
            found.extend((item, field == "act") for item in matches)
        if not found:
            raise STVError("item_unavailable")
        return next((pair for pair in found if pair[1]), found[0])

    async def inventory_item(self, item_id: str) -> dict[str, Any]:
        item_id = _item_id(item_id)
        return self._find_item(await self.inventory(), item_id)[0]

    async def use_item(self, item_id: str) -> dict[str, Any]:
        item_id = _item_id(item_id)
        item, active = self._find_item(await self.inventory(), item_id)
        if active or str(item.get("ac", "")).lower() in {"1", "true"}:
            raise STVError("item_active")
        kind = str(item.get("t", ""))
        if kind not in {"1", "2", "3", "4", "5"}:
            raise STVError("unsupported_item")
        marker = "item" if kind == "5" else "useitem"
        form = {"ajax": "item", "sub": "useitem", "itemid": item_id} if kind == "5" else {"ajax": "useitem", "itemid": item_id}
        body, _ = await self._request("POST", "/index.php", {"ngmar": marker}, form, mutation=True, account=True, limit=1024 * 1024)
        if body.strip() != "success":
            raise STVError("operation_unconfirmed", 200)
        return {"used": True, "item_id": item_id, "type": kind}


POLYFILL = r"""
var __B64A='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
var btoa=function(input){
  var output=''; var i=0; input=String(input);
  while(i<input.length){
    var c1=input.charCodeAt(i++) & 0xff;
    var c2=input.charCodeAt(i++); var c3=input.charCodeAt(i++);
    var e1=c1>>2;
    var e2=((c1&3)<<4)|((isNaN(c2)?0:c2)>>4);
    var e3=isNaN(c2)?64:(((c2&15)<<2)|((isNaN(c3)?0:c3)>>6));
    var e4=isNaN(c3)?64:(c3&63);
    output+=__B64A[e1]+__B64A[e2]+__B64A[e3]+__B64A[e4];
  }
  return output;
};
var atob=function(input){
  var output=''; var i=0; var bs=0; var acc=0;
  input=String(input).replace(/[^A-Za-z0-9\+\/=]/g,'');
  for(i=0;i<input.length;i++){
    var ch=input[i]; if(ch==='='){ break; }
    acc=(acc<<6)|__B64A.indexOf(ch); bs+=6;
    if(bs>=8){ bs-=8; output+=String.fromCharCode((acc>>bs)&0xff); }
  }
  return output;
};
"""


MOCK_ENV = r"""
var navigator  = { userAgent: __UA__, platform: "Linux armv8l" };
var document   = { cookie: "mac_tt=true", addEventListener: function(){},
                   createElement: function(){ return {style:{}}; } };
var location   = { href: "https://sangtacviet.app/app.v2.php", hostname: "sangtacviet.app" };
var Capacitor  = { isNativePlatform: function(){ return true; },
                   getPlatformId: function(){ return "android"; }, Plugins: {} };
var __registered = {};
var reader = { __defineGetter__: function(name, fn){ __registered[String(name)] = fn; } };
var app = { reader: reader };
var window = { navigator: navigator, document: document, location: location,
               Capacitor: Capacitor, app: app };
"""


class _ChineseBodyParser(HTMLParser):
    """读取 App 词条的中文 t 属性，不使用越南语可见词面。"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.stack = []
        self.tokens = 0

    def handle_starttag(self, tag, attrs):
        suppressed = bool(self.stack and self.stack[-1][1])
        values = dict(attrs)
        if not suppressed and tag == "i":
            source = values.get("t")
            if not isinstance(source, str) or not source.strip():
                raise ValueError("接口词条缺少中文 t 属性，未使用越南语替代正文")
            self.output.append(source)
            self.tokens += 1
            suppressed = True
        elif tag in ("script", "style"):
            suppressed = True
        elif not suppressed and tag == "br":
            self.output.append("\n")
        if tag not in ("br", "hr", "img", "input", "meta", "link", "wbr", "source", "area", "base", "embed", "param", "track", "col"):
            self.stack.append((tag, suppressed))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                suppressed = self.stack[index][1]
                del self.stack[index:]
                if not suppressed and tag in ("p", "div", "section", "article"):
                    self.output.append("\n\n")
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            return
        # App 注入的缓存提示不是小说正文。
        if data.strip() == "@Bạn đang đọc bản lưu trong hệ thống":
            return
        self.output.append(data)


def html_to_chinese_text(html):
    """从 App 返回的中文正文或 i[t] 词条提取中文，不经机器翻译。"""
    parser = _ChineseBodyParser()
    parser.feed(html)
    parser.close()
    text = "".join(parser.output)
    if not re.search(r"[\u3400-\u9fff\U00020000-\U0003134f]", text):
        raise ValueError("接口未返回可提取的中文正文，未将越南语当作中文保存")
    if re.search(r"[\u00c0-\u024f\u1e00-\u1eff]", text):
        raise ValueError("接口正文仍含未还原的越南语片段，未保存不完整中文")
    if parser.tokens:
        # 服务端在越南语词条间插入空格；保留换行和 ASCII 词内空格。
        han = r"\u3400-\u9fff\U00020000-\U0003134f"
        text = re.sub(r"(?<=[" + han + r"])[ \t]+(?=\S)", "", text)
        text = re.sub(r"(?<=\S)[ \t]+(?=[" + han + r"])", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class _CultivationNode:
    def __init__(self, tag="", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.parts = []

    def walk(self):
        yield self
        for part in self.parts:
            if isinstance(part, _CultivationNode):
                yield from part.walk()

    def has_class(self, name):
        return name in (self.attrs.get("class") or "").split()

    def text(self, direct=False):
        return " ".join(" ".join(part if isinstance(part, str) else
            ("" if direct else part.text()) for part in self.parts).split())


class _CultivationParser(HTMLParser):
    """只读取官方账号卡片的DOM结构，不执行页面脚本。"""
    _void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _CultivationNode()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _CultivationNode(tag, attrs, self.stack[-1])
        self.stack[-1].parts.append(node)
        if tag not in self._void:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if not any(node.tag in ("script", "style", "template") for node in self.stack):
            self.stack[-1].parts.append(data)


def _inventory_chinese_text(value: str) -> bool:
    # 中文自定义内容允许 S/SSR、HP 等短大写缩写，不将普通外语句子当成中文。
    han = r"[\u3400-\u9fff\U00020000-\U0003134f]"
    if not re.search(han, value) or re.search(r"[A-Z]{1,4}\s+[A-Z]{1,4}", value):
        return False
    text = re.sub(r"(?<![A-Za-z])[A-Z]{1,4}(?![A-Za-z])", "", value)
    return all(not unicodedata.category(char).startswith("L") or bool(re.fullmatch(han, char)) for char in text)


def _inventory_name_text(value: str) -> str:
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if _inventory_chinese_text(text):
        return text
    # 仅匹配实际名称；不根据 tag 用类别名称冒充物品名称。
    return {
        "mảnh vụn linh thạch": "灵石碎片", "thiên vận đan": "天运丹",
        "hạ phẩm thiên vận đan": "下品天运丹", "thượng phẩm tụ khí đan": "上品聚气丹",
        "hạ phẩm tẩy tủy đan": "下品洗髓丹", "trung phẩm tẩy tủy đan": "中品洗髓丹",
        "công kích bí kỹ": "攻击秘技",
        "linh thạch": "灵石", "đan dược": "丹药", "công pháp": "功法", "võ kỹ": "武技",
    }.get(text.casefold(), "名称暂未翻译")


def _inventory_description_text(value: str) -> str:
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if not text or _inventory_chinese_text(text):
        return text
    # 对照官方 ItemTool 的完整说明模板；数字、百分号来自响应，不用 b/l 重算。
    number = r"([0-9]+(?:[.,][0-9]+)*(?:[eE][+-]?[0-9]+)?)"
    templates = (
        (rf"Linh thạch sinh sản trong tự nhiên, hấp thu có thể tăng cường {number} tu vi\.?",
         "天然形成的灵石，吸收后可增加{0}点修为。"),
        (rf"Tẩy Tủy Đan, loại đan được thường nhe thấy, sử dụng bồi bổ {number} căn cơ\. Khi căn cơ vượt mức lịch luyện sẽ không nhận thêm căn cơ\.",
         "洗髓丹，一种常见丹药，使用后补充{0}点根基。根基超过历练上限时不再增加。"),
        (rf"Loại đan dược trong truyền thuyết, có thể tăng may mắn cho người sử dụng\. Tăng {number} vận khí\.?",
         "传说中的丹药，可提升使用者的运气。增加{0}点气运。"),
        (rf"Tụ Khí Đan là nhất bình thường đan được, chứa bàng bạc linh khí, sử dụng tăng {number} tu vi\.?",
         "聚气丹是一种普通丹药，蕴含充沛灵气，使用后增加{0}点修为。"),
        (rf"Công pháp trong lúc hữu tình nhặt được\. Tăng {number}\s*% tốc độ tu luyện và {number}\s*% toàn thuộc tính\.?",
         "偶然拾得的功法。修炼速度提高{0}%，全属性提高{1}%。"),
        (rf"Trong lúc lịch luyện (@[^\s@<>]{{1,128}}) đã ngộ ra môn bí kỹ này, uy lực vô cùng cường đại\. Tăng {number}\s*% lực tay cùng tốc độ\.?",
         "{0}在历练中领悟了这门秘技，威力极为强大。臂力和速度提高{1}%。"),
        (rf"Hấp thu tăng {number} tu vi\.?", "吸收后增加{0}点修为。"),
        (rf"(?:Sử dụng )?Tăng {number} tu vi\.?", "使用后增加{0}点修为。"),
        (rf"Sử dụng tăng {number}\s*% tốc độ hấp thu linh khí, hiệu lực trong {number} giờ, hiệu lực tối đa {number} viên cùng lúc\.?",
         "使用后灵气吸收速度增加{0}%，持续{1}小时，最多同时生效{2}颗。"),
        (rf"Sử dụng tăng {number}\s*% tốc độ hấp thu linh khí, hiệu lực trong {number} giờ, dùng chồng sẽ không có hiệu quả\.?",
         "使用后灵气吸收速度增加{0}%，持续{1}小时，重复使用不叠加效果。"),
        (rf"Sử dụng bồi bổ {number}\s*(%)? điểm căn cơ\.?", "使用后补充{0}{1}根基。"),
        (rf"(?:Sử dụng )?Tăng {number} (?:điểm )?vận khí\.?", "使用后增加{0}点气运。"),
        (r"Sử dụng lập tức thoát khỏi (?:trạng thái )?trọng thương\.?", "使用后立即脱离重伤状态。"),
        (rf"Tu luyện gia tăng {number}\s*% tốc độ tu luyện và toàn bộ thuộc tính\.?",
         "修炼后提升{0}%修炼速度及全部属性。"),
    )
    for pattern, translated in templates:
        match = re.fullmatch(pattern, text, re.IGNORECASE)
        if match:
            values = list(match.groups())
            # 官网的新旧根基说明分别有百分号和点数，按实际返回单位保留。
            if translated == "使用后补充{0}{1}根基。":
                values[1] = values[1] or "点"
            return translated.format(*values)
    attributes = {
        "lực tay": "臂力", "lực tay và tốc độ": "臂力和速度", "tinh thần lực": "精神力",
        "lực phòng ngự": "防御力", "tốc độ": "速度", "thực lực": "实力",
        "huyết khí": "血气", "huyết khí và phòng ngự": "血气和防御",
    }
    for source, translated in attributes.items():
        match = re.fullmatch(rf"Tu luyện gia tăng {number}\s*% {re.escape(source)}\.?", text, re.IGNORECASE)
        if match:
            return f"修炼后提升{match[1]}%{translated}。"
    return "说明暂未翻译"


def _inventory_info_text(name: str, info: _CultivationNode, item_level: int | None) -> str:
    text = " ".join(unicodedata.normalize("NFC", info.text()).split())
    heading = " ".join(unicodedata.normalize("NFC", name).split())
    level_line = r"(?:Cấp|等级)\s*[:：]\s*([0-9]{1,12})(?:\s+|$)"
    title = next((part for part in info.parts if not isinstance(part, str) or part.strip()), None)
    if isinstance(title, _CultivationNode) and title.tag == "b":
        display_title = unicodedata.normalize("NFC", title.text())
        # 自定义 itn 可能不同于官网加粗标题；后接等级才能确认是标题。
        if text.startswith(display_title + " ") and re.match(level_line, text[len(display_title):].lstrip(), re.IGNORECASE):
            heading = display_title
    pieces = []
    if text == heading or text.startswith(heading + " "):
        text = text[len(heading):].strip()
    level = re.match(level_line, text, re.IGNORECASE)
    if level:
        if int(level[1]) != item_level:
            pieces.append("等级：" + level[1])
        text = text[level.end():]
    description = _inventory_description_text(text)
    if description:
        pieces.append(description)
    return " ".join(pieces)


_INVENTORY_ICON_PATHS = frozenset({
    "/linhthach.jpg", "/danduoc.jpg", "/congphap.jpg", "/vuky.jpg",
    "/asset/hoa.jpg", "/asset/thuy.jpg", "/asset/kim.jpg", "/asset/moc.jpg", "/asset/tho.jpg",
    "/asset/phong.jpg", "/asset/loi.jpg", "/asset/quang.jpg", "/asset/bang.jpg", "/asset/am.jpg",
    "/game/asset/item/thon-thien-ma-cong-than-quyen.png", "/game/asset/item/thu-hon-dan.png",
})


def _inventory_icon_url(value: Any) -> str:
    """只返回已核实且可访问的官方物品图片，拒绝任意 URL 或查询参数。"""
    if not isinstance(value, str):
        return ""
    path = value
    for origin in (BASE, _LEGACY_BASE):
        if value.startswith(origin + "/"):
            path = value[len(origin):]
            break
    # 保留已保存的官方图标和分组身份，只切换协议请求网关。
    return _LEGACY_BASE + path if path in _INVENTORY_ICON_PATHS else ""


def _inventory_icon(attrs: dict[str, str], kind: str, level: int | None) -> str:
    # 官网 main.css 与用户页的物品图标级联；不执行 HTML 中的样式或脚本。
    backgrounds = [part.strip() for part in str(attrs.get("style") or "").split(";")
                   if re.match(r"\s*background(?:-image)?\s*:", part, re.IGNORECASE)]
    if backgrounds:
        match = re.fullmatch(r"background(?:-image)?\s*:\s*url\(\s*['\"]?([^'\"()\s]+)['\"]?\s*\)",
                             backgrounds[-1], re.IGNORECASE)
        return _inventory_icon_url(match[1]) if match else ""
    if kind == "3" and level == 50:
        return _inventory_icon_url("/game/asset/item/thon-thien-ma-cong-than-quyen.png")
    if attrs.get("b") == "3000000":
        return _inventory_icon_url("/game/asset/item/thu-hon-dan.png")
    if attrs.get("b") == "10000":
        # 官方此项图片目前返回 404，不用其他物品图片代替。
        return ""
    effects = {"19": "hoa", "20": "thuy", "21": "kim", "22": "moc", "23": "tho",
               "24": "phong", "25": "loi", "26": "quang", "27": "bang", "28": "am"}
    if attrs.get("e") in effects:
        return _inventory_icon_url("/asset/" + effects[attrs["e"]] + ".jpg")
    return _inventory_icon_url({"1": "/linhthach.jpg", "2": "/danduoc.jpg",
                                "3": "/congphap.jpg", "4": "/vuky.jpg"}.get(kind))


def _parse_inventory_fragment(body: str, *, active: bool = False) -> list[dict[str, Any]]:
    """解析官网库存片段；HTML 的 n 是数量，不沿用 App JSON 的名称含义。"""
    if not body.strip():
        return []
    if body.strip().lower() == "captcha" or re.match(r"\s*(?:<!doctype|<html)", body, re.IGNORECASE):
        raise STVError("verification_required", 200)
    parser = _CultivationParser()
    parser.feed(body)
    parser.close()
    items = [node for node in parser.root.walk() if node.has_class("item")]
    if not items or len(parser.stack) != 1:
        raise STVError("invalid_response", 200)
    result = []
    seen = set()
    for item in items:
        parent = item.parent
        while parent is not None:
            if parent.tag in {"script", "style", "template"} or parent.has_class("item"):
                raise STVError("invalid_response", 200)
            parent = parent.parent
        try:
            item_id = _item_id(item.attrs.get("i"))
        except STVError:
            raise STVError("invalid_response", 200) from None
        if item_id in seen:
            raise STVError("ambiguous_item", 200)
        seen.add(item_id)
        kind = (item.attrs.get("tag") or "").strip()
        active_value = (item.attrs.get("ac", "true" if active else "") or "").strip().lower()
        info_nodes = [node for node in item.walk() if node.has_class("iinfo")]
        if not re.fullmatch(r"[1-9]\d*", kind) or active_value not in {"0", "1", "false", "true"} or len(info_nodes) != 1:
            raise STVError("invalid_response", 200)
        info = info_nodes[0]
        name = (item.attrs.get("itn") or "").strip()
        if not name:
            title = next((part for part in info.parts if not isinstance(part, str) or part.strip()), None)
            name = title.text() if isinstance(title, _CultivationNode) and title.tag == "b" else ""
        if not name or not info.text():
            raise STVError("invalid_response", 200)
        row = {"i": item_id, "t": kind, "ac": active or active_value in {"1", "true"},
               "name": _inventory_name_text(name),
               # 官网按每个原始实例计一件，仅多件合并后生成 n；缺少 n 不是未知数量。
               "count": 1}
        for attribute, field in (("l", "level"), ("n", "count")):
            if attribute in item.attrs:
                value = (item.attrs[attribute] or "").strip()
                if (not re.fullmatch(r"[0-9]{1,12}", value)
                        or (attribute == "n" and int(value) <= 0)):
                    raise STVError("invalid_response", 200)
                row[field] = int(value)
                if attribute == "l":
                    row["l"] = value
        row["info"] = _inventory_info_text(name, info, row.get("level"))
        row["icon"] = _inventory_icon(item.attrs, kind, row.get("level"))
        # 使用原字段分组；两个未翻译名称或不同效果不能因显示占位相同而合并。
        normalize = lambda text: " ".join(unicodedata.normalize("NFC", text or "").split())
        identity = [normalize(name), normalize(info.text()), kind, item.attrs.get("e"),
                    item.attrs.get("l"), item.attrs.get("b"), row["ac"], row["icon"]]
        # 官网功法/武技保留独立实例，升级与消耗仍必须使用原实例 ID。
        if kind in {"3", "4"}:
            identity.append(item_id)
        row["group_key"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False,
                                                   separators=(",", ":")).encode("utf-8")).hexdigest()
        result.append(row)
    return result


def _cultivation_number(value):
    value = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError("官方修为字段不是有效数值：" + value[:60])
    return float(value) if "." in value else int(value)


def _cultivation_realm_text(value: str) -> str:
    # 官方个人页已核实词条及新手说明第5节的明确汉越境界；未知名称不套用。
    realms = {
        "huyền đạo": "玄道", "phong vương": "封王", "thông thần": "通神",
        "võ đồ": "武徒", "võ sư": "武师", "võ tông": "武宗",
        "võ vương": "武王", "võ hoàng": "武皇", "võ đế": "武帝", "võ thánh": "武圣",
        "võ thần": "武神", "tiêu dao": "逍遥", "vô cực": "无极", "thái thượng": "太上",
    }
    ranks = {"nhất": "一", "nhị": "二", "tam": "三", "tứ": "四", "ngũ": "五",
             "lục": "六", "thất": "七", "bát": "八", "cửu": "九"}
    phases = {"sơ kỳ": "初期", "trung kỳ": "中期", "hậu kỳ": "后期", "viên mãn": "圆满"}
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if re.fullmatch(r"[\u3400-\u9fff0-9\s]+", text) and re.search(r"[\u3400-\u9fff]", text):
        return text
    normalized = text.casefold()
    if normalized in realms:
        return realms[normalized]
    for source, translated in realms.items():
        if not normalized.startswith(source + " "):
            continue
        suffix = normalized[len(source) + 1:]
        if suffix in phases:
            return translated + phases[suffix]
        match = re.fullmatch(r"(nhất|nhị|tam|tứ|ngũ|lục|thất|bát|cửu|[1-9]) trọng", suffix)
        if match:
            rank = ranks.get(match[1]) or "一二三四五六七八九"[int(match[1]) - 1]
            return translated + rank + "重"
    return "暂未识别境界"


def _cultivation_status_text(value: str) -> str:
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if re.fullmatch(r"[\u3400-\u9fff\s]+", text):
        return text
    return {"đang lịch luyện": "正在历练", "đang tu luyện": "正在修炼"}.get(text.casefold(), "暂未识别状态")


def _parse_cultivation_profile(html, user_id):
    parser = _CultivationParser()
    parser.feed(html)
    parser.close()

    def one(nodes, predicate, label):
        matches = [node for node in nodes if predicate(node)]
        if len(matches) != 1:
            raise ValueError("官方个人页缺少唯一的" + label + "，未使用其他字段替代")
        return matches[0]

    page = one(parser.root.walk(), lambda n: n.attrs.get("id") == "userpage", "账号卡片")
    identity = one(page.walk(), lambda n: n.attrs.get("id") == "dsname", "账号身份")
    if identity.attrs.get("usid") != str(user_id):
        raise STVError("credential_invalid")
    user_text = one(page.walk(), lambda n: n.has_class("user-info-text"), "境界区域")
    realm = user_text.text(direct=True)
    if not realm:
        raise ValueError("官方个人页未返回境界，未使用称号代替")
    speed_node = one(user_text.walk(), lambda n: n.has_class("user-culti-speed"), "修炼速度")
    status = one(user_text.walk(), lambda n: n.has_class("user-status-text"), "修炼状态").text()
    speed_match = re.search(r"\+?(\d+(?:\.\d+)?)\s+tu vi/phút", speed_node.text())
    if speed_match is None or not status or not (speed_node.attrs.get("title") or "").strip():
        raise ValueError("官方个人页未返回有效修炼速度或状态")
    stats = one(page.walk(), lambda n: n.has_class("user-stat"), "修为属性区域")
    extended = one(stats.walk(), lambda n: n.has_class("extended-stat"), "详细修为区域")

    def progress(label):
        box = one(extended.walk(), lambda n: n.has_class("stat-box") and any(
            child.has_class("stat-title") and child.text() == label for child in n.walk()), label)
        return one(box.walk(), lambda n: n.has_class("progress-bar"), label + "进度")

    cultivation = progress("Tu vi")
    current, minimum, next_value = (_cultivation_number(cultivation.attrs.get(key, "")) for key in
                                    ("aria-valuenow", "aria-valuemin", "aria-valuemax"))
    if minimum > next_value or current < minimum:
        raise ValueError("官方修为进度范围异常")
    foundation = progress("Căn cơ")
    foundation_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", foundation.text())
    if foundation_match is None:
        raise ValueError("官方根基进度格式异常")
    foundation_current, foundation_max = map(_cultivation_number, foundation_match.groups())
    rows = {}
    attributes = {}
    for node in stats.walk():
        if not node.has_class("stat-row"):
            continue
        spans = [part for part in node.parts if isinstance(part, _CultivationNode) and part.tag == "span"]
        if len(spans) == 2:
            label, value = spans[0].text(), spans[1].text()
            if label in rows:
                raise ValueError("官方个人页存在重复属性：" + label)
            rows[label] = value
            if any(parent is node for parent in extended.walk()):
                attributes[label] = value

    def count(label, unit):
        match = re.fullmatch(r"(\d+)\s+" + unit, rows.get(label, ""))
        if match is None:
            raise ValueError("官方个人页未返回有效" + label)
        return int(match[1])

    def enabled(node):
        while node is not None:
            style = re.sub(r"\s+", "", node.attrs.get("style", "")).lower()
            if (node.tag in ("script", "style", "template") or "disabled" in node.attrs
                    or "hidden" in node.attrs or node.attrs.get("aria-disabled") == "true"
                    or node.attrs.get("aria-hidden") == "true" or "display:none" in style
                    or "visibility:hidden" in style):
                return False
            node = node.parent
        return True

    available = any(enabled(node) and re.fullmatch(
        r"\s*(?:return\s+)?UserTool\.showBreakThongThan\(\s*(?:this)?\s*\)\s*;?\s*",
        node.attrs.get("onclick") or "") for node in page.walk())
    speed_per_minute = _cultivation_number(speed_match[1])
    speed_display = str(speed_per_minute).removesuffix(".0")
    return {"user_id": str(user_id), "realm": _cultivation_realm_text(realm),
            "cultivation": {"current": current, "minimum": minimum, "next": next_value, "text": cultivation.text()},
            "foundation": {"current": foundation_current, "maximum": foundation_max, "text": foundation.text()},
            "speed": {"per_minute": speed_per_minute, "text": f"每分钟 +{speed_display} 修为",
                      "basis": speed_node.attrs.get("title", "")},
            "status": _cultivation_status_text(status), "training_minutes": count("Đã tu luyện", "phút"),
            "read_chapters": count("Đã đọc", "chương"), "attributes": attributes,
            "breakthrough_available": available}
