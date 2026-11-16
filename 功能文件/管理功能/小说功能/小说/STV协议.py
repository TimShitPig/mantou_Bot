"""Sáng Tác Việt App 协议。只处理同源请求和字段解析，不写入账号或文件。"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import time
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlencode

import aiohttp
from yarl import URL

BASE = "https://sangtacviet.com"
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
    "/io/grantcontext/context", "/io/user/online",
}
_CONNECTION_POOLS = globals().get("_CONNECTION_POOLS") or {}


def _acquire_connector() -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    pool = _CONNECTION_POOLS.get(loop)
    if pool is None or pool["connector"].closed:
        pool = {"loop": loop, "connector": aiohttp.TCPConnector(
            limit=8, limit_per_host=8, ttl_dns_cache=300, keepalive_timeout=30,
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
    pool = _CONNECTION_POOLS.get(loop)
    if pool is not None and (expected is None or pool is expected) and pool["users"] == 0:
        _CONNECTION_POOLS.pop(loop, None)
        if pool["idle"] is not None:
            pool["idle"].cancel()
        await pool["connector"].close()


class STVError(RuntimeError):
    def __init__(self, category: str, http_status: int | None = None, code: Any = None):
        self.category = category
        self.http_status = http_status
        value = str(code) if isinstance(code, (str, int)) and not isinstance(code, bool) else ""
        self.code = value if re.fullmatch(r"-?\d{1,12}", value) else None
        super().__init__(category)


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


def _js_eval(source: str, expression: str, data: dict[str, Any] | None = None) -> str:
    """独立无宿主绑定的 JS 环境；网络、文件和 Python 回调均不可用。"""
    try:
        import quickjs
    except ImportError:
        quickjs = None
    try:
        program = POLYFILL + "\n" + MOCK_ENV.replace("__UA__", json.dumps(UA))
        if data is not None:
            program += "\nvar x=" + json.dumps(data, ensure_ascii=True) + ";"
        program += "\n" + source + "\n" + expression
        if quickjs is not None:
            context = quickjs.Context()
            context.set_memory_limit(96 * 1024 * 1024)
            context.set_max_stack_size(2 * 1024 * 1024)
            context.set_time_limit(5)
            result = context.eval(program)
        else:
            try:
                from py_mini_racer import py_mini_racer
            except ImportError as exc:
                raise STVError("js_runtime_missing") from exc
            context = py_mini_racer.MiniRacer()
            result = context.eval(program, timeout=5000, max_memory=96 * 1024 * 1024)
        if not isinstance(result, str):
            raise STVError("invalid_response")
        return result
    except STVError:
        raise
    except Exception as exc:
        raise STVError("js_decode_failed") from exc


async def _run_js(source: str, expression: str, data: dict[str, Any] | None = None) -> str:
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

    def __init__(self, cookies: list[dict[str, Any]] | None = None, uid: str = ""):
        if uid and not re.fullmatch(r"[1-9]\d*", str(uid)):
            raise STVError("invalid_input")
        self.uid = str(uid)
        self._initial_cookies = list(cookies or [])
        self.session: aiohttp.ClientSession | None = None
        self._connection_pool: dict[str, Any] | None = None
        self._reading_lock = asyncio.Lock()
        self._key_target: tuple[str, str] | None = None
        self._key = ""
        self._reward_offer: tuple[str, float] | None = None
        self.mutation_guard = None

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
                or domain != "sangtacviet.com" or not path.startswith("/") or len(path) > 300
                or name in {"readcontextid", "transmode", "foreignlang"}
            ):
                raise STVError("invalid_cookie")
            cookie = SimpleCookie()
            cookie[name] = value
            cookie[name]["domain"] = domain
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
            {"name": value.key, "value": value.value, "domain": value["domain"] or "sangtacviet.com",
             "path": value["path"] or "/", "secure": bool(value["secure"]), "expires": value["expires"]}
            for value in self._session().cookie_jar
            if value["domain"].lstrip(".") == "sangtacviet.com"
            and value.key not in {"readcontextid", "transmode", "foreignlang"}
        ]

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None, *, limit: int = 16 * 1024 * 1024,
        mutation: bool = False, account: bool = False,
    ) -> tuple[str, dict[str, str]]:
        if path not in _PATHS or method not in {"GET", "POST"}:
            raise STVError("invalid_endpoint")
        query = urlencode(params or {})
        url = URL(BASE + path + ("?" + query if query else ""), encoded=True)
        headers = {"Origin": BASE} if method == "POST" else {}
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
                    raise STVError(category, response.status)
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

    async def _chapter_key(self, host: str, bookid: str) -> str:
        body, _ = await self._request("GET", "/io/grantcontext/context", {"hostid": host, "bookid": bookid}, limit=2 * 1024 * 1024)
        if len(body) < 1000:
            raise STVError("invalid_response", 200)
        key = await _run_js(body, "String(__registered.chapterkey.call(app.reader))")
        if not key or len(key) > 16384 or key in {"undefined", "null"}:
            raise STVError("invalid_response", 200)
        self._key, self._key_target = key, (host, bookid)
        return key

    async def _chapter_raw(self, host: str, bookid: str, cid: str) -> dict[str, Any]:
        body, _ = await self._request("GET", "/index.php", {"sajax": "readchapter", "h": host, "bookid": bookid, "c": cid, "key": self._key})
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

    async def chapter(self, host: str, bookid: str, cid: str) -> dict[str, Any]:
        host, bookid = _identity(host, bookid)
        cid = _item_id(cid)
        async with self._reading_lock:
            if self._key_target != (host, bookid) or not self._key:
                await self._chapter_key(host, bookid)
            data = await self._chapter_raw(host, bookid, cid)
            if str(data.get("code")) == "10002":
                await self._chapter_key(host, bookid)
                data = await self._chapter_raw(host, bookid, cid)
            self._chapter_code(data)
            try:
                content = html_to_chinese_text(data.get("data") or "")
            except (ValueError, TypeError):
                jar = self._session().cookie_jar
                jar.update_cookies({"transmode": "name"}, response_url=URL(BASE))
                try:
                    data = await self._chapter_raw(host, bookid, cid)
                finally:
                    jar.update_cookies({"transmode": "chinese"}, response_url=URL(BASE))
                self._chapter_code(data)
                try:
                    content = html_to_chinese_text(data.get("data") or "")
                except (ValueError, TypeError) as exc:
                    raise STVError("chinese_body_missing", 200) from exc
            if not content.strip():
                raise STVError("chapter_empty", 200)
            return {"title": str(data.get("chaptername") or ""), "content": content,
                    "reward_token_count": len(re.findall(r"<i(?:\s|>)", data.get("data") or "", re.IGNORECASE))}

    def _clear_account(self) -> None:
        self._session().cookie_jar.clear(lambda cookie: cookie.key in {"access", "useri2", "readcontextid"})
        self.uid, self._key, self._key_target, self._reward_offer = "", "", None, None

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
        body, _ = await self._request("POST", "/", {"ajax": "login"}, {"username": username, "psw": password}, mutation=True, account=True, limit=1024 * 1024)
        if body.strip() != "success" or not self._has_access():
            raise STVError("credential_invalid", 200)
        return await self.account_info()

    async def register(self, username: str, password: str, repeat_password: str) -> dict[str, Any]:
        self._credentials(username, password)
        if password != repeat_password:
            raise STVError("password_mismatch")
        self._clear_account()
        body, _ = await self._request("POST", "/", {"ajax": "register"}, {"username": username, "psw": password, "repsw": repeat_password}, mutation=True, account=True, limit=1024 * 1024)
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

    async def collect_reward(self, cid: str) -> dict[str, Any]:
        cid = _item_id(cid)
        offer, self._reward_offer = self._reward_offer, None
        if not self._has_access() or not self.uid:
            raise STVError("credential_invalid")
        if not offer or offer[0] != self.uid or not 0 <= time.monotonic() - offer[1] <= 300:
            raise STVError("reward_unavailable")
        body, _ = await self._request("POST", "/index.php", {"ngmar": "collect"}, {"sajax": "collect"}, mutation=True, account=True, limit=1024 * 1024)
        item = self._json(body, mutation=True)
        if not all(key in item for key in ("name", "info", "level", "type")) or not isinstance(item["name"], str) or not item["name"].strip() or not isinstance(item["info"], str):
            raise STVError("operation_unconfirmed", 200)
        form = {"ajax": "fcollect", "c": cid}
        if str(item["type"]) in {"3", "4"}:
            name, info = _html_text(item["name"]), _html_text(item["info"])
            if len(name) > 80:
                raise STVError("operation_unconfirmed", 200)
            form.update(newname=name, newinfo=info)
        body, _ = await self._request("POST", "/index.php", {"ngmar": "fcl"}, form, mutation=True, account=True, limit=1024 * 1024)
        result = self._json(body, mutation=True)
        if not isinstance(result.get("code"), (str, int)) or isinstance(result.get("code"), bool):
            raise STVError("operation_unconfirmed", 200)
        return {"collected": str(result["code"]) == "1", "cid": cid, "item": item, "result": result}

    async def cultivation(self) -> dict[str, Any]:
        try:
            body, _ = await self._account_query("/user/0/", account=False, limit=2 * 1024 * 1024)
        except STVError as exc:
            if exc.http_status == 401:
                raise STVError("credential_invalid", 401) from exc
            if exc.http_status == 403:
                raise STVError("verification_required", 403) from exc
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
        body, _ = await self._account_query("/mobile/jsonify.php", {"ajax": "getinv"}, account=True)
        data = self._json(body)
        self._code(data, "100")
        if any(not isinstance(data.get(field), list) or any(not isinstance(item, dict) for item in data[field]) for field in ("list", "act")):
            raise STVError("invalid_response", 200)
        if not self._has_access():
            raise STVError("credential_invalid", 200)
        return data

    async def _account_query(self, path: str, params: dict[str, Any] | None = None,
                             **kwargs: Any) -> tuple[str, dict[str, str]]:
        """独立的身份与资料读取并行；两者均成功才返回，不缓存身份或数据。"""
        if not self._has_access():
            raise STVError("credential_invalid")
        tasks = [asyncio.create_task(self.account_info()),
                 asyncio.create_task(self._request("GET", path, params, **kwargs))]
        try:
            _, result = await asyncio.gather(*tasks)
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
var location   = { href: "https://sangtacviet.com/app.v2.php", hostname: "sangtacviet.com" };
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


def _cultivation_number(value):
    value = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError("官方修为字段不是有效数值：" + value[:60])
    return float(value) if "." in value else int(value)


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
    return {"user_id": str(user_id), "realm": realm,
            "cultivation": {"current": current, "minimum": minimum, "next": next_value, "text": cultivation.text()},
            "foundation": {"current": foundation_current, "maximum": foundation_max, "text": foundation.text()},
            "speed": {"per_minute": _cultivation_number(speed_match[1]), "text": speed_node.text(),
                      "basis": speed_node.attrs.get("title", "")},
            "status": status, "training_minutes": count("Đã tu luyện", "phút"),
            "read_chapters": count("Đã đọc", "chương"), "attributes": attributes,
            "breakthrough_available": available}
