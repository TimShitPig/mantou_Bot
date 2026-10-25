"""仅用于读取已经保存的蓝奏云历史归档；不提供上传或账号配置。"""
from __future__ import annotations

from .媒体归档工具 import 识别媒体类型, 解析媒体范围


import asyncio
import ipaddress
import json
import re
import socket
import time
from contextlib import asynccontextmanager
from html.parser import HTMLParser
from typing import Any, AsyncIterator
from urllib.parse import quote, urlencode, urljoin, urlsplit
from aiohttp import ClientResponse, ClientSession, ClientTimeout
from yarl import URL
try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


蓝奏云网盘主机 = "https://pc.woozooo.com"


蓝奏云分享域名 = frozenset(
    {
        "lanzou.com",
        "lanzouo.com",
        "lanzouw.com",
        "lanzoui.com",
        "lanzoux.com",
        "lanzous.com",
        "lanzn.com",
        "woozooo.com",
    }
)


图片最大字节数 = 100 * 1024 * 1024


网页最大字节数 = 1024 * 1024


最大跳转次数 = 4


归档直链复用秒 = 300


最大分享页结构重试次数 = 1


分享页结构重试间隔秒 = 0.25


蓝奏云UserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class 蓝奏云请求错误(RuntimeError):
    def __init__(
        self,
        阶段: str,
        状态码: int = 0,
        业务码: Any = None,
        主机: str = "",
        *, 原因: str = "", 明确拒绝: bool = False,
    ):
        super().__init__(阶段)
        self.阶段 = 阶段
        self.状态码 = int(状态码 or 0)
        try:
            self.业务码 = int(业务码) if 业务码 is not None else None
        except (TypeError, ValueError):
            self.业务码 = None
        self.主机 = str(主机 or "")[:253]
        self.原因 = 原因 if 原因 in {"upload_rate_limited", "upload_cooldown", "upload_response_invalid"} else ""
        self.明确拒绝 = bool(明确拒绝)


class _ESAScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self._script_parts: list[str] = []
        self._capture_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attributes = dict(attrs)
        类型 = str(attributes.get("type") or "").strip().lower()
        self._capture_script = not attributes.get("src") and 类型 in {
            "", "text/javascript", "application/javascript", "text/ecmascript", "application/ecmascript"
        }
        self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_script:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script":
            return
        if self._capture_script:
            self.scripts.append("".join(self._script_parts))
        self._capture_script = False
        self._script_parts = []


def _新建会话(Cookie: dict[str, str] | None = None) -> ClientSession:
    from aiohttp import CookieJar

    会话 = ClientSession(
        headers={
            "User-Agent": 蓝奏云UserAgent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        },
        cookie_jar=CookieJar(unsafe=True),
        timeout=ClientTimeout(total=None, connect=20, sock_read=90),
        trust_env=True,
    )
    if Cookie:
        会话.cookie_jar.update_cookies(
            Cookie, response_url=URL(蓝奏云网盘主机 + "/")
        )
    return 会话


def _浏览器页面请求头() -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }


async def _读取有界响应内容(
    响应: ClientResponse, 超限阶段: str = "response_too_large"
) -> bytes:
    # StreamReader.read(n) 可能只返回当前网络分块，必须继续读取直到 EOF。
    内容 = bytearray()
    while True:
        块 = await 响应.content.read(min(64 * 1024, 网页最大字节数 + 1 - len(内容)))
        if not 块:
            return bytes(内容)
        内容.extend(块)
        if len(内容) > 网页最大字节数:
            raise 蓝奏云请求错误(超限阶段, 响应.status)


def _提取ESA脚本(页面HTML: str) -> list[str]:
    解析器 = _ESAScriptParser()
    try:
        解析器.feed(页面HTML)
        解析器.close()
    except Exception as exc:
        raise 蓝奏云请求错误("esa_html_parse_failed") from exc
    脚本列表 = [脚本 for 脚本 in 解析器.scripts if 脚本.strip()]
    # 某些响应直接返回 JS；只接受 Cookie 标记，HTML 正文不作为脚本执行。
    if not 脚本列表 and not re.search(r"<(?:!doctype|html|head|body|script)\b", 页面HTML, re.IGNORECASE):
        if "acw_sc__v2" in 页面HTML:
            脚本列表 = [页面HTML]
    return 脚本列表


def _解析标准ESA参数(脚本列表: list[str]) -> str:
    # 与公开 LanZouCloud-API 的 calc_acw_sc__v2 协议一致，仅匹配已知参数。
    掩码 = "3000176000856006061501533003690027800375"
    参数 = []
    for 脚本 in 脚本列表:
        if "acw_sc__v2" not in 脚本:
            continue
        参数.extend(值 for _, 值 in re.findall(r"\barg1\s*=\s*(['\"])([^'\"]*)\1", 脚本))
    if len(参数) != 1 or not re.fullmatch(r"[0-9a-fA-F]{40}", 参数[0]):
        return ""
    置换 = (15, 35, 29, 24, 33, 16, 1, 38, 10, 9, 19, 31, 40, 27, 22, 23,
            25, 13, 6, 11, 39, 18, 20, 8, 14, 21, 32, 26, 2, 30, 7, 4, 17, 5,
            3, 28, 34, 37, 12, 36)
    数据 = bytes.fromhex("".join(参数[0][位置 - 1] for 位置 in 置换))
    return bytes(左 ^ 右 for 左, 右 in zip(数据, bytes.fromhex(掩码))).hex()


def _含ESA挑战(页面HTML: str) -> bool:
    脚本列表 = _提取ESA脚本(页面HTML)
    if _解析标准ESA参数(脚本列表):
        return True
    return any(
        "acw_sc__v2" in 脚本 and (
            re.search(r"\barg1\s*=", 脚本)
            or re.search(r"\bdocument\s*(?:\.\s*cookie|\[\s*['\"]cookie['\"]\s*\])\s*=", 脚本)
        )
        for 脚本 in 脚本列表
    )


def _执行ESA挑战脚本(
    会话: ClientSession, 页面地址: str, 页面HTML: str, *, 优先直接解析: bool = True
) -> bool:
    if len(页面HTML.encode("utf-8", errors="ignore")) > 网页最大字节数:
        raise 蓝奏云请求错误("esa_page_too_large")
    脚本列表 = _提取ESA脚本(页面HTML)
    if not 脚本列表:
        raise 蓝奏云请求错误("esa_script_missing")
    if len(脚本列表) > 12:
        raise 蓝奏云请求错误("esa_script_count")
    if sum(len(脚本.encode("utf-8", errors="ignore")) for 脚本 in 脚本列表) > 256 * 1024:
        raise 蓝奏云请求错误("esa_script_too_large")
    标准Cookie = _解析标准ESA参数(脚本列表) if 优先直接解析 else ""
    if 标准Cookie:
        会话.cookie_jar.update_cookies(
            {"acw_sc__v2": 标准Cookie}, response_url=URL(页面地址)
        )
        return True
    try:
        import quickjs
    except ImportError as exc:
        raise 蓝奏云请求错误("esa_runtime_unavailable") from exc

    页面URL = URL(页面地址)
    初始Cookie = {
        名称: 项目.value
        for 名称, 项目 in 会话.cookie_jar.filter_cookies(页面URL).items()
    }
    上下文 = quickjs.Context()
    上下文.set_memory_limit(8 * 1024 * 1024)
    上下文.set_time_limit(2.0)
    引导脚本 = (
        "var __cookieMap=new Map(Object.entries("
        + json.dumps(初始Cookie, ensure_ascii=True)
        + "));var __cookieWrites=new Map();var document={};"
        "Object.defineProperty(document,'cookie',{get:function(){return "
        "Array.from(__cookieMap,function(x){return x[0]+'='+x[1]}).join('; ')},"
        "set:function(v){var p=String(v).split(';',1)[0],i=p.indexOf('=');"
        "if(i>0){var k=p.slice(0,i).trim(),v=p.slice(i+1).trim();"
        "__cookieMap.set(k,v);__cookieWrites.set(k,v)}}});"
        "var location={href:"
        + json.dumps(页面地址, ensure_ascii=True)
        + ",reload:function(){}};document.location=location;document.URL="
        + json.dumps(页面地址, ensure_ascii=True)
        + ";document.documentURI=document.URL;var navigator={userAgent:"
        + json.dumps(蓝奏云UserAgent, ensure_ascii=True)
        + ",language:'zh-CN',platform:'Win32'};"
        "var window={document:document,location:location,navigator:navigator};"
        "var self=window,top=window,parent=window;"
        "var setTimeout=function(f){if(typeof f==='function')f();return 1};"
        "var clearTimeout=function(){};"
    )
    try:
        上下文.eval(引导脚本)
        for 脚本 in 脚本列表:
            上下文.eval(脚本)
        Cookie原文 = str(上下文.eval("Array.from(__cookieWrites,function(x){return x[0]+'='+x[1]}).join('; ')") or "")
    except Exception as exc:
        raise 蓝奏云请求错误("esa_script_failed") from exc

    更新Cookie: dict[str, str] = {}
    for 片段 in Cookie原文.split(";"):
        名称, 分隔符, 值 = 片段.strip().partition("=")
        if 分隔符 and 名称 and 值:
            更新Cookie[名称] = 值
    挑战Cookie = 更新Cookie.get("acw_sc__v2", "")
    if not 挑战Cookie or len(挑战Cookie) > 1024:
        raise 蓝奏云请求错误("esa_cookie_missing")
    try:
        会话.cookie_jar.update_cookies(更新Cookie, response_url=页面URL)
    except Exception as exc:
        raise 蓝奏云请求错误("esa_cookie_rejected") from exc
    return False


def _是ESA响应(响应: ClientResponse) -> bool:
    # ESA 服务器同样返回普通文件，200/206 二进制流不得被预读或释放。
    类型 = str(响应.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    return 响应.status == 200 and 类型 in {
        "text/html", "application/xhtml+xml", "text/javascript", "application/javascript"
    }


async def _确保公网HTTPS地址(地址: str, *, 限制蓝奏域名: bool = False) -> str:
    文本 = str(地址 or "").strip()
    if len(文本) > 8192:
        raise 蓝奏云请求错误("url_invalid")
    解析 = urlsplit(文本)
    主机 = str(解析.hostname or "").rstrip(".").lower()
    if (
        解析.scheme.lower() != "https"
        or not 主机
        or 解析.username
        or 解析.password
        or (解析.port not in (None, 443))
    ):
        raise 蓝奏云请求错误("url_invalid")
    if 限制蓝奏域名 and not any(
        主机 == 根域 or 主机.endswith(f".{根域}") for 根域 in 蓝奏云分享域名
    ):
        raise 蓝奏云请求错误("share_host_invalid", 主机=主机)
    try:
        地址列表 = [ipaddress.ip_address(主机)]
    except ValueError:
        try:
            解析结果 = await asyncio.get_running_loop().getaddrinfo(
                主机, 443, type=socket.SOCK_STREAM
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise 蓝奏云请求错误("dns_failed") from exc
        地址列表 = []
        for 结果 in 解析结果:
            try:
                地址列表.append(ipaddress.ip_address(结果[4][0]))
            except (ValueError, TypeError, IndexError):
                continue
    if not 地址列表 or any(not 地址.is_global for 地址 in 地址列表):
        raise 蓝奏云请求错误("host_not_public")
    return 文本


async def _请求跟随跳转(
    会话: ClientSession,
    地址: str,
    *,
    referer: str = "",
    限制蓝奏域名: bool = False,
    请求头: dict[str, str] | None = None,
) -> ClientResponse:
    当前地址 = 地址
    for 次数 in range(最大跳转次数 + 1):
        当前地址 = await _确保公网HTTPS地址(
            当前地址, 限制蓝奏域名=限制蓝奏域名 and 次数 == 0
        )
        try:
            当前请求头 = dict(请求头 or {})
            if referer:
                当前请求头["Referer"] = referer
            响应 = await 会话.get(
                当前地址,
                allow_redirects=False,
                headers=当前请求头 or None,
            )
        except Exception as exc:
            raise 蓝奏云请求错误("get_failed") from exc
        if 响应.status not in {301, 302, 303, 307, 308}:
            return 响应
        跳转地址 = 响应.headers.get("Location")
        响应.release()
        if not 跳转地址 or 次数 >= 最大跳转次数:
            raise 蓝奏云请求错误("redirect_invalid", 响应.status)
        当前地址 = urljoin(当前地址, 跳转地址)
    raise 蓝奏云请求错误("redirect_limit")


async def _请求处理ESA挑战(
    会话: ClientSession,
    地址: str,
    *,
    referer: str = "",
    限制蓝奏域名: bool = False,
    请求头: dict[str, str] | None = None,
) -> ClientResponse:
    上次直接解析 = False
    for 次数 in range(3):
        响应 = await _请求跟随跳转(
            会话, 地址, referer=referer,
            限制蓝奏域名=限制蓝奏域名, 请求头=请求头,
        )
        if not _是ESA响应(响应):
            return 响应
        try:
            页面内容 = await _读取有界响应内容(响应, "esa_page_too_large")
            页面HTML = 页面内容.decode("utf-8", errors="replace")
            if not _含ESA挑战(页面HTML):
                raise 蓝奏云请求错误("download_not_file", 响应.status)
            if 次数 and not 上次直接解析:
                raise 蓝奏云请求错误("esa_challenge_retry", 响应.status)
            # 标准参数优先直接解析；仍返回挑战时只兼容执行一次未知变体。
            上次直接解析 = _执行ESA挑战脚本(
                会话, str(响应.url), 页面HTML, 优先直接解析=次数 == 0
            )
        finally:
            响应.release()
    raise 蓝奏云请求错误("esa_challenge_retry")


async def _读取网页文本(
    会话: ClientSession,
    地址: str,
    *,
    referer: str = "",
    限制蓝奏域名: bool = False,
) -> str:
    上次直接解析 = False
    for 次数 in range(3):
        响应 = await _请求跟随跳转(
            会话, 地址, referer=referer,
            限制蓝奏域名=限制蓝奏域名, 请求头=_浏览器页面请求头(),
        )
        try:
            内容 = await _读取有界响应内容(响应, "page_too_large")
            if 响应.status != 200:
                raise 蓝奏云请求错误("page_status", 响应.status)
            页面HTML = 内容.decode(响应.charset or "utf-8", errors="replace")
            if not (_是ESA响应(响应) and _含ESA挑战(页面HTML)):
                return 页面HTML
            if 次数 and not 上次直接解析:
                raise 蓝奏云请求错误("esa_challenge_retry", 响应.status)
            上次直接解析 = _执行ESA挑战脚本(
                会话, str(响应.url), 页面HTML, 优先直接解析=次数 == 0
            )
        finally:
            响应.release()
    raise 蓝奏云请求错误("esa_challenge_retry")


async def _提交表单JSON(
    会话: ClientSession,
    地址: str,
    字段: dict[str, Any],
    *,
    referer: str = "",
    请求头: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        当前请求头 = dict(请求头 or {})
        if referer:
            当前请求头["Referer"] = referer
        async with 会话.post(
            地址,
            data={名称: str(值) for 名称, 值 in 字段.items()},
            headers=当前请求头 or None,
            allow_redirects=False,
        ) as 响应:
            if 响应.status != 200:
                raise 蓝奏云请求错误("post_status", 响应.status)
            内容 = await _读取有界响应内容(响应)
            try:
                结果 = json.loads(内容.decode(响应.charset or "utf-8", errors="replace"))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise 蓝奏云请求错误("response_not_json", 响应.status) from exc
            if not isinstance(结果, dict):
                raise 蓝奏云请求错误("response_shape", 响应.status)
            return 结果
    except 蓝奏云请求错误:
        raise
    except Exception as exc:
        raise 蓝奏云请求错误("post_failed") from exc


def _成功(结果: dict[str, Any]) -> bool:
    return str(结果.get("zt") or "").strip() == "1"


async def _取得直接下载地址(
    会话: ClientSession,
    分享地址: str,
    提取码: str,
    分享页重试次数: int = 0,
) -> str:
    分享HTML = await _读取网页文本(
        会话, 分享地址, 限制蓝奏域名=True
    )
    if "文件取消" in 分享HTML or "文件不存在" in 分享HTML:
        raise 蓝奏云请求错误("share_missing")
    分享解析 = urlsplit(分享地址)
    新版下载接口 = False
    新版Sign = re.search(
        r"\bvar\s+isngis\s*=\s*['\"]([^'\"]+)['\"]",
        分享HTML,
        re.IGNORECASE,
    )
    新版Ajax = re.search(
        r"\burl\s*:\s*['\"](https://apifile\.woozooo\.com/ajaxfile\.php\?file=[0-9]+)['\"]",
        分享HTML,
        re.IGNORECASE,
    )
    if 新版Sign and 新版Ajax:
        Ajax地址 = await _确保公网HTTPS地址(新版Ajax.group(1))
        if urlsplit(Ajax地址).hostname != "apifile.woozooo.com":
            raise 蓝奏云请求错误("download_api_host_invalid")
        Kd匹配 = re.search(r"\bvar\s+kdns\s*=\s*([0-9]+)", 分享HTML)
        if not Kd匹配:
            raise 蓝奏云请求错误("download_kd_missing")
        Ajax字段 = {
            "action": "downprocess",
            "sign": 新版Sign.group(1),
            "kd": Kd匹配.group(1),
            "p": 提取码,
        }
        Referer = 分享地址
        Ajax请求头 = {
            "Origin": f"{分享解析.scheme}://{分享解析.netloc}",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        新版下载接口 = True
    elif re.search(r'id=["\'](?:pwdload|passwddiv)["\']', 分享HTML, re.IGNORECASE):
        匹配 = re.search(r"sign=([\w-]+)&", 分享HTML)
        if not 匹配:
            raise 蓝奏云请求错误("password_sign_missing")
        Ajax地址 = f"{分享解析.scheme}://{分享解析.netloc}/ajaxm.php"
        Ajax字段 = {"action": "downprocess", "sign": 匹配.group(1), "p": 提取码}
        Referer = 分享地址
    else:
        匹配 = re.search(r'<iframe[^>]+src=["\']([^"\']+)', 分享HTML, re.IGNORECASE)
        if not 匹配:
            if 分享页重试次数 < 最大分享页结构重试次数:
                await asyncio.sleep(分享页结构重试间隔秒)
                return await _取得直接下载地址(
                    会话,
                    分享地址,
                    提取码,
                    分享页重试次数 + 1,
                )
            raise 蓝奏云请求错误("password_page_unrecognized")
        下载页地址 = urljoin(分享地址, 匹配.group(1))
        下载页HTML = await _读取网页文本(
            会话, 下载页地址, referer=分享地址, 限制蓝奏域名=True
        )
        if "验证码" in 下载页HTML or "网络异常" in 下载页HTML:
            raise 蓝奏云请求错误("download_challenge")
        Sign = re.search(r"['\"]sign['\"]\s*:\s*['\"]([^'\"]+)['\"]", 下载页HTML)
        if not Sign:
            Sign = re.search(r"\bvar\s+sign\s*=\s*['\"]([^'\"]+)['\"]", 下载页HTML)
        if not Sign:
            raise 蓝奏云请求错误("download_sign_missing")
        Ajax地址 = f"{分享解析.scheme}://{分享解析.netloc}/ajaxm.php"
        Ajax字段 = {"action": "downprocess", "sign": Sign.group(1), "ves": 1}
        Referer = 下载页地址
    Ajax结果 = await _提交表单JSON(
        会话,
        Ajax地址,
        Ajax字段,
        referer=Referer,
        请求头=Ajax请求头 if 新版下载接口 else None,
    )
    if not _成功(Ajax结果):
        raise 蓝奏云请求错误("download_link_rejected")
    下载主机 = str(Ajax结果.get("dom") or "").strip().rstrip("/")
    下载标识 = str(Ajax结果.get("url") or "").strip()
    if not 下载主机 or not 下载标识:
        raise 蓝奏云请求错误("download_link_missing")
    if "://" not in 下载主机:
        下载主机 = f"https://{下载主机.lstrip('/')}"
    下载主机解析 = urlsplit(下载主机)
    if (
        下载主机解析.scheme.lower() != "https"
        or not 下载主机解析.hostname
        or 下载主机解析.username
        or 下载主机解析.password
        or 下载主机解析.port not in (None, 443)
        or 下载主机解析.path not in ("", "/")
        or 下载主机解析.query
        or 下载主机解析.fragment
    ):
        raise 蓝奏云请求错误("download_host_invalid")
    if 新版下载接口:
        下载主机名 = str(下载主机解析.hostname or "").lower().rstrip(".")
        if not (下载主机名 == "lanrar.com" or 下载主机名.endswith(".lanrar.com")):
            raise 蓝奏云请求错误("download_host_invalid", 主机=下载主机名)
    下载地址 = f"{下载主机}/file/{下载标识 if 新版下载接口 else quote(下载标识, safe='')}"
    return await _确保公网HTTPS地址(下载地址)


def _可复用归档直链(归档资料: Any, 分享地址: str, 提取码: str) -> str:
    if not isinstance(归档资料, dict):
        return ""
    if 归档资料.get("share_url") != 分享地址 or 归档资料.get("password") != 提取码:
        return ""
    try:
        已过秒数 = time.time() - float(归档资料.get("direct_url_cached_at") or 0)
    except (TypeError, ValueError, OverflowError):
        return ""
    if not 0 <= 已过秒数 < 归档直链复用秒:
        return ""
    return str(归档资料.get("direct_url") or "").strip()


@asynccontextmanager
async def 打开归档图片(
    分享地址: str, 提取码: str, *, 范围: str = "",
    归档资料: dict[str, Any] | None = None,
    保存直链: Any = None,
) -> AsyncIterator[ClientResponse]:
    async with _新建会话() as 会话:
        下载请求头 = _浏览器页面请求头()
        下载请求头["Sec-Fetch-Site"] = "cross-site"
        if 范围:
            下载请求头["Range"] = 范围
        直接地址 = _可复用归档直链(归档资料, 分享地址, 提取码)
        响应 = None
        获取时间 = 0.0
        if 直接地址:
            try:
                # 所有缓存地址仍走公网 HTTPS 校验；失效时只在发送字节前重取一次。
                响应 = await _请求处理ESA挑战(
                    会话, 直接地址, referer=分享地址, 请求头=下载请求头,
                )
                if 响应.status not in {200, 206}:
                    响应.release()
                    响应 = None
            except asyncio.CancelledError:
                raise
            except Exception:
                响应 = None
        if 响应 is None:
            直接地址 = await _取得直接下载地址(会话, 分享地址, 提取码)
            获取时间 = time.time()
            响应 = await _请求处理ESA挑战(
                会话, 直接地址, referer=分享地址, 请求头=下载请求头,
            )
        try:
            if 响应.status not in {200, 206}:
                raise 蓝奏云请求错误("download_status", 响应.status)
            yield 响应
        finally:
            响应.release()
        # 消费者正常退出意味着 Range/原字节校验已完成；失败及取消不保存新地址。
        if 获取时间 and callable(保存直链):
            try:
                await 保存直链(直接地址, 获取时间)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("蓝奏云媒体直链保存失败：错误类型=%s", type(exc).__name__)


def _归档偏移(归档: dict[str, Any]) -> int:
    大小 = int(归档.get("size") or 0)
    if not 0 < 大小 <= 图片最大字节数:
        raise 蓝奏云请求错误("archive_size_invalid")
    if 归档.get("container") != "zip-stored":
        return 0
    偏移 = int(归档.get("offset") or 0)
    包大小 = int(归档.get("archive_size") or 0)
    if 偏移 < 30 or not 偏移 + 大小 <= 包大小 <= 图片最大字节数:
        raise 蓝奏云请求错误("archive_container_invalid")
    return 偏移


async def 读取归档媒体块(上游: ClientResponse, 归档: dict[str, Any], 起点: int, 终点: int) -> AsyncIterator[bytes]:
    偏移 = _归档偏移(归档)
    跳过 = 偏移 + 起点
    余量 = 终点 - 起点 + 1
    if 上游.status == 206:
        范围 = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", 上游.headers.get("Content-Range", ""))
        总量 = int(归档.get("archive_size") or 归档["size"])
        if not 范围 or tuple(map(int, 范围.groups())) != (偏移 + 起点, 偏移 + 终点, 总量):
            raise 蓝奏云请求错误("archive_range_mismatch", 206)
        跳过 = 0
    async for 块 in 上游.content.iter_chunked(64 * 1024):
        if 跳过:
            数量 = min(跳过, len(块))
            跳过 -= 数量
            块 = 块[数量:]
        if not 块:
            continue
        块 = 块[:余量]
        余量 -= len(块)
        if 块:
            yield 块
        if not 余量:
            return
    raise 蓝奏云请求错误("archive_truncated")


