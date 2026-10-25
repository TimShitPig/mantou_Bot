from __future__ import annotations

import asyncio
import copy
import hashlib
import ipaddress
import json
import re
import secrets
import socket
import struct
import time
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import quote, urlencode, urljoin, urlsplit

from aiohttp import ClientResponse, ClientSession, ClientTimeout, FormData
from yarl import URL

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


蓝奏云网盘主机 = "https://pc.woozooo.com"
图片归档目录名 = "QQ聊天图片"  # 保留原目录名称，兼容已有归档
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
蓝奏云Cookie字段 = frozenset({"phpdisk_info", "ylogin"})
蓝奏云UserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
图片归档并发限制 = globals().get("图片归档并发限制", asyncio.Semaphore(2))
图片归档进行中: set[tuple[str, str]] = globals().get("图片归档进行中", set())
图片归档失败冷却: dict[tuple[str, str], float] = globals().get("图片归档失败冷却", {})
图片归档任务: set[asyncio.Task[Any]] = globals().get("图片归档任务", set())
图片归档排队中: set[tuple[str, str]] = globals().get("图片归档排队中", set())
图片归档接收开启 = bool(globals().get("图片归档接收开启", True))
图片归档最大任务数 = 2
图片归档唤醒句柄: asyncio.TimerHandle | None = globals().get("图片归档唤醒句柄")
图片归档调度代次 = int(globals().get("图片归档调度代次", 0))
# 仅保留当前进程的参数与远端结果；附件字节只使用上传临时文件。
图片归档待恢复: dict[tuple[str, str], dict[str, Any]] = globals().get("图片归档待恢复", {})
媒体远端并发限制 = globals().get("媒体远端并发限制", asyncio.Semaphore(2))
归档目录锁 = globals().get("归档目录锁", asyncio.Lock())
# 内部退避策略，不代表蓝奏云公布的固定限额；跨同进程热重载保留。
蓝奏云上传最小间隔秒 = 15
蓝奏云频率冷却秒 = 300
蓝奏云频率最大冷却秒 = 1800
蓝奏云上传锁 = globals().get("蓝奏云上传锁", asyncio.Lock())
蓝奏云上传下次允许: dict[str, float] = globals().get("蓝奏云上传下次允许", {})
蓝奏云上传频率拒绝次数: dict[str, int] = globals().get("蓝奏云上传频率拒绝次数", {})


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


def _上传业务错误(结果: Any, 状态码: int) -> 蓝奏云请求错误:
    if not isinstance(结果, dict):
        return 蓝奏云请求错误("upload_response_shape", 状态码, 原因="upload_response_invalid")
    业务值 = 结果.get("zt")
    业务码 = int(业务值) if (
        type(业务值) is int or isinstance(业务值, str) and re.fullmatch(r"-?[0-9]{1,6}", 业务值.strip())
    ) else None
    文本 = 结果.get("text")
    项目 = 文本 if isinstance(文本, list) else [文本]
    含文件ID = any(
        isinstance(项, dict) and any(项.get(字段) not in (None, "") for 字段 in ("id", "file_id"))
        for 项 in [结果, *项目]
    )
    # 只处理服务器实测的明确频率拒绝；其它业务码或矛盾响应不推断上传结果。
    提示 = 结果.get("info")
    频率拒绝 = 业务码 == 0 and not 含文件ID and isinstance(提示, str) and "上传频率过快" in 提示
    return 蓝奏云请求错误(
        "upload_rejected", 状态码, 业务码,
        原因="upload_rate_limited" if 频率拒绝 else "", 明确拒绝=频率拒绝,
    )


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


def _配置值(配置: Any) -> str:
    候选列表 = [配置]
    for 属性名 in ("data", "obj"):
        值 = getattr(配置, 属性名, None)
        if 值 is not None:
            候选列表.append(值)
    获取配置 = getattr(配置, "get_config", None)
    if callable(获取配置):
        try:
            候选列表.append(获取配置())
        except Exception:
            pass
    for 候选 in 候选列表:
        if isinstance(候选, dict):
            分类 = 候选.get("lanzou_pan_settings")
            if isinstance(分类, dict):
                return str(分类.get("lanzou_pan_cookie") or "").strip()
            return str(候选.get("lanzou_pan_cookie") or "").strip()
    return str(getattr(配置, "lanzou_pan_cookie", "") or "").strip()


def _解析Cookie(原文: Any) -> tuple[dict[str, str], str]:
    文本 = str(原文 or "").strip()
    if 文本[:7].lower() == "cookie:":
        文本 = 文本.split(":", 1)[1].strip()
    Cookie: dict[str, str] = {}
    for 片段 in 文本.split(";"):
        if "=" not in 片段:
            continue
        名称, 值 = 片段.split("=", 1)
        名称 = 名称.strip()
        值 = 值.strip()
        if 名称 and 值:
            Cookie[名称] = 值
    if not 蓝奏云Cookie字段.issubset(Cookie):
        raise 蓝奏云请求错误("cookie_invalid")
    return Cookie, Cookie["ylogin"]


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


def _目录项(结果: dict[str, Any]) -> list[dict[str, Any]]:
    值 = 结果.get("text")
    if not isinstance(值, list):
        return []
    return [项目 for 项目 in 值 if isinstance(项目, dict)]


async def _列出目录(
    会话: ClientSession, UID: str, 父目录ID: Any
) -> list[dict[str, Any]]:
    结果 = await _提交表单JSON(
        会话,
        f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}",
        {"task": 47, "folder_id": 父目录ID},
        referer=f"{蓝奏云网盘主机}/mydisk.php",
    )
    if not isinstance(结果.get("text"), list):
        raise 蓝奏云请求错误("directory_list", 业务码=结果.get("zt"))
    return _目录项(结果)


async def _确保归档目录(会话: ClientSession, UID: str, 日期目录: str) -> int:
    根目录 = await _列出目录(会话, UID, -1)
    根ID = next(
        (
            str(项目.get("fol_id"))
            for 项目 in 根目录
            if str(项目.get("name") or "").strip() == 图片归档目录名
            and str(项目.get("fol_id") or "").isdigit()
        ),
        "",
    )
    if not 根ID:
        创建结果 = await _提交表单JSON(
            会话,
            f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}",
            {
                "task": 2,
                "parent_id": -1,
                "folder_name": 图片归档目录名,
                "folder_description": "QQ 聊天图片归档",
            },
            referer=f"{蓝奏云网盘主机}/mydisk.php",
        )
        if not _成功(创建结果):
            raise 蓝奏云请求错误("directory_create")
        根目录 = await _列出目录(会话, UID, -1)
        根ID = next(
            (
                str(项目.get("fol_id"))
                for 项目 in 根目录
                if str(项目.get("name") or "").strip() == 图片归档目录名
                and str(项目.get("fol_id") or "").isdigit()
            ),
            "",
        )
    if not 根ID:
        raise 蓝奏云请求错误("directory_missing")

    日期列表 = await _列出目录(会话, UID, 根ID)
    日期ID = next(
        (
            str(项目.get("fol_id"))
            for 项目 in 日期列表
            if str(项目.get("name") or "").strip() == 日期目录
            and str(项目.get("fol_id") or "").isdigit()
        ),
        "",
    )
    if not 日期ID:
        创建结果 = await _提交表单JSON(
            会话,
            f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}",
            {
                "task": 2,
                "parent_id": 根ID,
                "folder_name": 日期目录,
                "folder_description": "",
            },
            referer=f"{蓝奏云网盘主机}/mydisk.php",
        )
        if not _成功(创建结果):
            raise 蓝奏云请求错误("directory_create")
        日期列表 = await _列出目录(会话, UID, 根ID)
        日期ID = next(
            (
                str(项目.get("fol_id"))
                for 项目 in 日期列表
                if str(项目.get("name") or "").strip() == 日期目录
                and str(项目.get("fol_id") or "").isdigit()
            ),
            "",
        )
    if not 日期ID:
        raise 蓝奏云请求错误("directory_missing")
    return int(日期ID)


def _媒体种类(项目: dict[str, Any]) -> str:
    类型 = str(项目.get("type") or 项目.get("media_type") or "").lower()
    MIME = str(项目.get("content_type") or "").lower()
    if 类型 in {"图片", "image", "img"} or MIME.startswith("image/"):
        return "image"
    if 类型 in {"视频", "video"} or MIME.startswith("video/"):
        return "video"
    if 类型 in {"语音", "音频", "audio", "voice"} or MIME.startswith("audio/"):
        return "audio"
    if 类型 in {"文件", "file", "document"} or 项目.get("src") or 项目.get("url") or 项目.get("download_url"):
        return "file"
    return ""


def _媒体项目列表(媒体: Any, *, 可下载: bool = True) -> list[tuple[int, dict[str, Any]]]:
    if not isinstance(媒体, dict):
        return []
    项目列表 = 媒体.get("items")
    if not isinstance(项目列表, list) or not 项目列表:
        项目列表 = [媒体]
    return [(索引, 项目) for 索引, 项目 in enumerate(项目列表)
            if isinstance(项目, dict) and _媒体种类(项目)
            and (not 可下载 or str(项目.get("src") or 项目.get("url") or 项目.get("download_url") or "").startswith(("http://", "https://")))]


def 识别图片类型(前缀: bytes, 响应类型: Any = "") -> str:
    if 前缀.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if 前缀.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if 前缀.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(前缀) >= 12 and 前缀[:4] == b"RIFF" and 前缀[8:12] == b"WEBP":
        return "image/webp"
    if 前缀.startswith(b"BM"):
        return "image/bmp"
    if 前缀.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if 前缀.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"
    if len(前缀) >= 12 and 前缀[4:8] == b"ftyp":
        if any(标识 in 前缀[8:64] for 标识 in (b"avif", b"avis")):
            return "image/avif"
        if any(标识 in 前缀[8:64] for 标识 in (b"heic", b"heix", b"heif", b"mif1")):
            return "image/heif"
    return ""


def 识别媒体类型(前缀: bytes, 响应类型: Any = "", *, 预期种类: str = "") -> str:
    if 前缀 and 预期种类 == "file":
        return "application/octet-stream"
    图片类型 = 识别图片类型(前缀)
    if 图片类型:
        return 图片类型 if 预期种类 not in {"video", "audio"} else ""
    视频类型 = ""
    if len(前缀) >= 12 and 前缀[4:8] == b"ftyp":
        if 预期种类 == "audio" or b"M4A " in 前缀[8:64]:
            return "audio/mp4" if 预期种类 not in {"image", "video"} else ""
        视频类型 = "video/quicktime" if 前缀[8:12] == b"qt  " else "video/mp4"
    elif 前缀.startswith(b"\x1aE\xdf\xa3"):
        视频类型 = "video/webm" if b"webm" in 前缀.lower() else "video/x-matroska"
    elif 前缀.startswith(b"RIFF") and 前缀[8:12] == b"AVI ":
        视频类型 = "video/x-msvideo"
    elif 前缀.startswith(b"FLV"):
        视频类型 = "video/x-flv"
    elif 前缀.startswith(b"OggS") and b"theora" in 前缀.lower():
        视频类型 = "video/ogg"
    elif 前缀.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3")):
        视频类型 = "video/mpeg"
    if 视频类型:
        return 视频类型 if 预期种类 not in {"image", "audio"} else ""
    音频类型 = ""
    if 前缀.startswith(b"RIFF") and 前缀[8:12] == b"WAVE":
        音频类型 = "audio/wav"
    elif 前缀.startswith(b"ID3") or (len(前缀) >= 2 and 前缀[0] == 0xff and 前缀[1] & 0xe0 == 0xe0):
        音频类型 = "audio/mpeg"
    elif 前缀.startswith(b"fLaC"):
        音频类型 = "audio/flac"
    elif 前缀.startswith((b"#!AMR", b"#!AMR-WB")):
        音频类型 = "audio/amr"
    elif 前缀.startswith((b"#!SILK", b"\x02#!SILK")):
        音频类型 = "audio/silk"
    elif 前缀.startswith(b"OggS"):
        音频类型 = "audio/ogg"
    if 音频类型:
        return 音频类型 if 预期种类 not in {"image", "video"} else ""
    # QQ 新格式未覆盖文件头时，只接受已声明的媒体 MIME，排除错误 HTML/JSON。
    类型 = str(响应类型 or "").split(";", 1)[0].strip().lower()
    if 类型 == "image/svg+xml" and (b"<svg" in 前缀.lower() or 前缀.lstrip().startswith(b"<?xml")) and 预期种类 != "video":
        return 类型
    if 前缀 and not 前缀.lstrip().startswith((b"<", b"{", b"[")) and re.fullmatch(r"(?:image|video|audio)/[a-z0-9.+-]+", 类型):
        return 类型 if not 预期种类 or 类型.startswith(预期种类 + "/") else ""
    if 前缀 and 预期种类 in {"image", "audio", "video"} and not 前缀.lstrip().startswith((b"<", b"{", b"[")):
        return 预期种类 + "/x-unknown"
    return ""


def _图片扩展名(内容类型: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
            "image/webp": ".webp", "image/bmp": ".bmp", "image/avif": ".avif",
            "image/heif": ".heif", "image/tiff": ".tiff", "image/x-icon": ".ico", "image/svg+xml": ".svg",
            "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm",
            "video/x-matroska": ".mkv", "video/x-msvideo": ".avi", "video/x-flv": ".flv",
            "video/ogg": ".ogv", "video/mpeg": ".mpeg", "audio/wav": ".wav",
            "audio/mpeg": ".mp3", "audio/flac": ".flac", "audio/ogg": ".ogg",
            "audio/amr": ".amr", "audio/silk": ".silk"}.get(内容类型, ".bin")


def _原附件后缀(项目: dict[str, Any], 内容类型: str) -> str:
    # 不以 .jpg 白名单限制归档；未知后缀装在真实 ZIP 内，原字节不变。
    名称 = str(项目.get("name") or 项目.get("filename") or "")
    if not 名称:
        名称 = urlsplit(str(项目.get("src") or 项目.get("url") or "")).path.rsplit("/", 1)[-1]
    后缀 = Path(名称).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{1,16}", 后缀):
        return 后缀
    return _图片扩展名(内容类型)


async def _下载QQ媒体(地址: str, 路径: Path, 预期种类: str) -> tuple[str, int]:
    from 功能文件.页面功能 import 帮助网页后端

    if not 帮助网页后端._允许媒体地址(地址):
        raise 蓝奏云请求错误("source_url_invalid")
    async with _新建会话() as 会话:
        响应 = await _请求跟随跳转(会话, 地址)
        try:
            if 响应.status != 200:
                raise 蓝奏云请求错误("source_status", 响应.status)
            if 响应.content_length is not None and 响应.content_length > 图片最大字节数:
                raise 蓝奏云请求错误("source_too_large", 响应.status)
            已读 = 0
            前缀 = bytearray()
            with 路径.open("wb") as 文件:
                async for 数据块 in 响应.content.iter_chunked(64 * 1024):
                    已读 += len(数据块)
                    if 已读 > 图片最大字节数:
                        raise 蓝奏云请求错误("source_too_large", 响应.status)
                    if len(前缀) < 128:
                        前缀.extend(数据块[:128 - len(前缀)])
                    写任务 = asyncio.create_task(asyncio.to_thread(文件.write, 数据块))
                    try:
                        await asyncio.shield(写任务)
                    except asyncio.CancelledError:
                        await 写任务
                        raise
            内容类型 = 识别媒体类型(bytes(前缀), 响应.headers.get("Content-Type"), 预期种类=预期种类)
            if not 内容类型 or not 已读:
                raise 蓝奏云请求错误("source_not_media", 响应.status)
            return 内容类型, 已读
        finally:
            响应.release()


def _打包原始媒体(源路径: Path, 归档路径: Path, 文件名: str) -> dict[str, Any]:
    # 实际 ZIP_STORED 容器，不伪装后缀，不转码；网页可直接按偏移流式取原字节。
    with zipfile.ZipFile(归档路径, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as 容器:
        容器.write(源路径, arcname=文件名)
        信息 = 容器.getinfo(文件名)
    归档大小 = 归档路径.stat().st_size
    if 归档大小 > 图片最大字节数:
        raise 蓝奏云请求错误("archive_too_large")
    with 归档路径.open("rb") as 文件:
        头 = 文件.read(30)
    if len(头) != 30 or 头[:4] != b"PK\x03\x04":
        raise 蓝奏云请求错误("archive_header_invalid")
    名称长度, 扩展长度 = struct.unpack_from("<HH", 头, 26)
    return {"container": "zip-stored", "offset": 30 + 名称长度 + 扩展长度,
            "archive_size": 归档大小, "crc32": 信息.CRC}


async def _上传图片(
    会话: ClientSession,
    UID: str,
    目录ID: int,
    文件路径: Path,
    文件名: str,
    内容类型: str,
    大小: int,
) -> str:
    日期 = datetime.now().strftime("%a %b %d %Y %H:%M:%S GMT+0800 (中国标准时间)")
    表单 = FormData()
    for 名称, 值 in (
        ("task", "1"),
        ("vie", "2"),
        ("ve", "2"),
        ("id", "WU_FILE_0"),
        ("name", 文件名),
        ("type", 内容类型),
        ("lastModifiedDate", 日期),
        ("size", str(大小)),
        ("folder_id_bb_n", str(目录ID)),
    ):
        表单.add_field(名称, 值)
    with 文件路径.open("rb") as 文件句柄:
        表单.add_field(
            "upload_file",
            文件句柄,
            filename=文件名,
            content_type=内容类型,
        )
        try:
            async with 会话.post(
                f"{蓝奏云网盘主机}/html5up.php",
                data=表单,
                headers={
                    "Origin": 蓝奏云网盘主机,
                    "Referer": f"{蓝奏云网盘主机}/mydisk.php?item=files&action=index&u={quote(UID)}",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                },
                allow_redirects=False,
            ) as 响应:
                if 响应.status != 200:
                    raise 蓝奏云请求错误("upload_status", 响应.status)
                内容 = await _读取有界响应内容(响应, "upload_response_too_large")
                try:
                    结果 = json.loads(内容.decode(响应.charset or "utf-8", errors="replace"))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise 蓝奏云请求错误("upload_response_not_json", 响应.status) from exc
                if not isinstance(结果, dict) or not _成功(结果):
                    raise _上传业务错误(结果, 响应.status)
                文本 = 结果.get("text")
                文件记录 = 文本[0] if isinstance(文本, list) and 文本 else 文本
                文件ID = 文件记录.get("id") if isinstance(文件记录, dict) else None
                if not str(文件ID or "").isdigit():
                    raise 蓝奏云请求错误("upload_id_missing", 响应.status)
                return str(文件ID)
        except 蓝奏云请求错误:
            raise
        except Exception as exc:
            raise 蓝奏云请求错误("upload_failed") from exc


async def _取得分享信息(
    会话: ClientSession, UID: str, 文件ID: str, 提取码: str
) -> dict[str, str]:
    API = f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}"
    设置结果 = await _提交表单JSON(
        会话,
        API,
        {"task": 23, "file_id": 文件ID, "shows": 1, "shownames": 提取码},
        referer=f"{蓝奏云网盘主机}/mydisk.php",
    )
    分享结果 = await _提交表单JSON(
        会话,
        API,
        {"task": 22, "file_id": 文件ID},
        referer=f"{蓝奏云网盘主机}/mydisk.php",
    )
    信息 = 分享结果.get("info")
    if not isinstance(信息, dict):
        raise 蓝奏云请求错误("share_response")
    分享码 = str(信息.get("pwd") or "").strip()
    if not 分享码 and _成功(设置结果):
        分享码 = 提取码
    if not 分享码:
        raise 蓝奏云请求错误("share_password_missing")
    分享地址 = str(信息.get("url") or "").strip()
    if not 分享地址:
        主站 = str(信息.get("is_newd") or "").strip().rstrip("/")
        分享ID = str(信息.get("f_id") or "").strip()
        if not 主站 or not 分享ID:
            raise 蓝奏云请求错误("share_link_missing")
        分享地址 = f"{主站}/{quote(分享ID, safe='')}"
    分享地址 = await _确保公网HTTPS地址(分享地址, 限制蓝奏域名=True)
    return {"share_url": 分享地址, "password": 分享码, "file_id": 文件ID}


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


def 解析媒体范围(范围: str, 大小: int) -> tuple[int, int, bool]:
    if 大小 <= 0:
        raise ValueError("media_size_invalid")
    if not 范围:
        return 0, 大小 - 1, False
    匹配 = re.fullmatch(r"bytes=(\d*)-(\d*)", 范围.strip())
    if not 匹配 or not any(匹配.groups()):
        raise ValueError("range_invalid")
    首, 尾 = 匹配.groups()
    if not 首:
        长度 = int(尾)
        if 长度 <= 0:
            raise ValueError("range_invalid")
        return max(0, 大小 - 长度), 大小 - 1, True
    起点 = int(首)
    终点 = min(大小 - 1, int(尾)) if 尾 else 大小 - 1
    if 起点 >= 大小 or 终点 < 起点:
        raise ValueError("range_invalid")
    return 起点, 终点, True


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


def _删除归档临时文件(路径: Path) -> None:
    from 功能文件.管理功能.基础功能 import 文件缓存

    try:
        路径.unlink(missing_ok=True)
    finally:
        文件缓存.解除临时缓存占用(路径)


async def _上传并取得归档资料(
    Cookie: dict[str, str], UID: str, 进度: dict[str, Any], 临时路径: Path | None,
) -> dict[str, Any]:
    try:
        async with _新建会话(Cookie) as 会话:
            文件ID = str(进度.get("file_id") or "")
            if not 文件ID:
                if 临时路径 is None:
                    raise 蓝奏云请求错误("source_missing")
                async with 归档目录锁:
                    目录ID = await _确保归档目录(会话, UID, str(进度.get("directory") or 进度.get("month") or _归档日期目录名()))
                async with 蓝奏云上传锁:
                    当前时间 = asyncio.get_running_loop().time()
                    截止 = 蓝奏云上传下次允许.get(UID, 0)
                    if 截止 > 当前时间:
                        进度["upload_retry_at"] = 截止
                        raise 蓝奏云请求错误("upload_cooldown", 原因="upload_cooldown")
                    蓝奏云上传下次允许[UID] = 当前时间 + 蓝奏云上传最小间隔秒
                    进度.pop("upload_retry_at", None)
                    进度["upload_submitted"] = True
                    try:
                        文件ID = await _上传图片(
                            会话, UID, 目录ID, 临时路径,
                            str(进度["filename"]) + (".zip" if 进度.get("container") == "zip-stored" else ""),
                            "application/zip" if 进度.get("container") == "zip-stored" else str(进度["content_type"]),
                            int(进度.get("archive_size") or 进度["size"]),
                        )
                    except 蓝奏云请求错误 as 异常:
                        if 异常.明确拒绝:
                            进度.pop("upload_submitted", None)
                            次数 = min(蓝奏云上传频率拒绝次数.get(UID, 0) + 1, 4)
                            蓝奏云上传频率拒绝次数[UID] = 次数
                            等待 = min(蓝奏云频率最大冷却秒, 蓝奏云频率冷却秒 * 2 ** (次数 - 1))
                            截止 = asyncio.get_running_loop().time() + 等待
                            蓝奏云上传下次允许[UID] = 截止
                            进度["upload_retry_at"] = 截止
                        raise
                    进度["file_id"] = 文件ID
                    蓝奏云上传频率拒绝次数.pop(UID, None)
            if 临时路径 is not None:
                _删除归档临时文件(临时路径)
                临时路径 = None
            提取码 = 进度.setdefault("password", f"{secrets.randbelow(10_000):04d}")
            分享 = await _取得分享信息(会话, UID, 文件ID, str(提取码))
        归档资料 = {"share_url": 分享["share_url"], "password": 分享["password"], "file_id": 分享["file_id"],
                    "content_type": 进度["content_type"], "size": 进度["size"], "filename": 进度["filename"]}
        for 字段 in ("container", "offset", "archive_size", "crc32", "media_kind", "original_name"):
            if 字段 in 进度:
                归档资料[字段] = 进度[字段]
        进度["archive"] = 归档资料
        return 归档资料
    finally:
        if 临时路径 is not None:
            _删除归档临时文件(临时路径)


def _归档日期目录名(时间戳: Any = None) -> str:
    try:
        数值 = float(时间戳)
        日期 = datetime.fromtimestamp(数值) if 数值 > 0 else datetime.now()
    except (TypeError, ValueError, OverflowError, OSError):
        日期 = datetime.now()
    return f"{日期.year}年{日期.month}月{日期.day}日"


async def _归档单项远端(Cookie: dict[str, str], UID: str, 记录: dict[str, Any], 索引: int, 进度: dict[str, Any]) -> dict[str, Any]:
    from 功能文件.管理功能.基础功能 import 文件缓存

    async with 媒体远端并发限制:
        原路径: Path | None = None
        包路径: Path | None = None
        try:
            if not 进度.get("file_id"):
                项目 = dict(_媒体项目列表(记录.get("media"))).get(索引)
                if not isinstance(项目, dict):
                    raise 蓝奏云请求错误("source_missing")
                地址 = str(项目.get("src") or 项目.get("url") or 项目.get("download_url") or "").strip()
                if 进度.get("uid") not in (None, UID):
                    raise 蓝奏云请求错误("account_changed")
                原路径 = Path(文件缓存.创建临时缓存文件("lanzou-media-", ".tmp"))
                文件缓存.标记临时缓存正在使用(原路径)
                内容类型, 大小 = await _下载QQ媒体(地址, 原路径, _媒体种类(项目))
                标识 = hashlib.sha256(f"{记录['_session']}:{记录['message_id']}:{索引}".encode()).hexdigest()[:24]
                日期目录 = _归档日期目录名(记录.get("ts"))
                进度.update({"content_type": 内容类型, "size": 大小, "filename": f"msg_{标识}{_原附件后缀(项目, 内容类型)}",
                            "media_kind": _媒体种类(项目), "original_name": str(项目.get("name") or 项目.get("filename") or "")[:160],
                            "directory": 日期目录})
                包路径 = Path(文件缓存.创建临时缓存文件("lanzou-media-", ".zip"))
                文件缓存.标记临时缓存正在使用(包路径)
                打包任务 = asyncio.create_task(asyncio.to_thread(_打包原始媒体, 原路径, 包路径, 进度["filename"]))
                try:
                    进度.update(await asyncio.shield(打包任务))
                except asyncio.CancelledError:
                    # 线程完成后才能删除它正在读写的文件。
                    await 打包任务
                    raise
                _删除归档临时文件(原路径)
                原路径 = None
            上传路径 = 包路径
            包路径 = None
            return await _上传并取得归档资料(Cookie, UID, 进度, 上传路径)
        finally:
            for 路径 in (原路径, 包路径):
                if 路径 is not None:
                    _删除归档临时文件(路径)


def _读取远端归档任务结果(任务: asyncio.Task[Any]) -> None:
    if not 任务.cancelled():
        任务.exception()


def _项目归档资料(媒体: dict[str, Any], 索引: int) -> dict[str, Any] | None:
    列表 = 媒体.get("_lanzou_archives")
    归档 = 列表.get(str(索引)) if isinstance(列表, dict) else None
    if not isinstance(归档, dict) and 索引 == 0:
        归档 = 媒体.get("_lanzou_archive")
    return 归档 if isinstance(归档, dict) else None


async def _执行图片归档(配置: Any, 记录: dict[str, Any], 媒体索引: int = 0) -> dict[str, Any]:
    Cookie, UID = _解析Cookie(_配置值(配置))
    键 = (str(记录.get("_session") or "").strip(), str(记录.get("message_id") or "").strip())
    参数 = 图片归档待恢复.setdefault(键, {"config": 配置, "record": copy.deepcopy(记录)})
    所有进度 = 参数.setdefault("progress", {})
    # 接管上一版同进程尚未结束的第一张图片上传，不重新 POST。
    if any(字段 in 所有进度 for 字段 in ("uid", "remote_task", "archive", "file_id")):
        所有进度 = 参数["progress"] = {0: 所有进度}
    进度 = 所有进度.setdefault(媒体索引, {})
    if 进度.get("upload_submitted") and not 进度.get("file_id"):
        远端 = 进度.get("remote_task")
        if 远端 is None or 远端.done():
            raise 蓝奏云请求错误("upload_result_unconfirmed")
    if isinstance(进度.get("archive"), dict):
        return dict(进度["archive"])
    远端任务 = 进度.get("remote_task")
    if isinstance(远端任务, asyncio.Task):
        if not 远端任务.done() or (not 远端任务.cancelled() and 远端任务.exception() is None):
            return await asyncio.shield(远端任务)
        进度.pop("remote_task", None)
    if 进度.get("uid") not in (None, UID):
        raise 蓝奏云请求错误("account_changed")
    进度["uid"] = UID
    if not 进度.get("file_id"):
        截止 = max(蓝奏云上传下次允许.get(UID, 0), float(进度.get("upload_retry_at") or 0))
        if 截止 > asyncio.get_running_loop().time():
            进度["upload_retry_at"] = 截止
            raise 蓝奏云请求错误("upload_cooldown", 原因="upload_cooldown")
    远端任务 = asyncio.create_task(_归档单项远端(Cookie, UID, 记录, 媒体索引, 进度))
    进度["remote_task"] = 远端任务
    远端任务.add_done_callback(_读取远端归档任务结果)
    return await asyncio.shield(远端任务)


def _归档逐项进度(参数: dict[str, Any]) -> dict[int, dict[str, Any]]:
    进度 = 参数.setdefault("progress", {})
    if any(字段 in 进度 for 字段 in ("uid", "remote_task", "archive", "file_id", "upload_submitted")):
        进度 = 参数["progress"] = {0: 进度}
    return 进度


def _归档项目可恢复(进度: dict[str, Any]) -> bool:
    if 进度.get("file_id") or isinstance(进度.get("archive"), dict):
        return True
    远端 = 进度.get("remote_task")
    if isinstance(远端, asyncio.Task) and not 远端.done():
        return True
    # POST 已经发出但没有确认文件 ID，保留标记，禁止重新上传。
    if 进度.get("upload_submitted"):
        return False
    return int(进度.get("source_failures", 0)) < 3


def _归档参数可恢复(参数: dict[str, Any]) -> bool:
    媒体 = 参数["record"].get("media") or {}
    进度 = _归档逐项进度(参数)
    return any(
        not _项目归档资料(媒体, 索引)
        and _归档项目可恢复(进度.get(索引, {}))
        for 索引, _ in _媒体项目列表(媒体)
    )


def _归档参数上传截止(参数: dict[str, Any]) -> float:
    """取未完成项目最早的可运行时刻；已确认文件和在途任务不受上传冷却阻挡。"""
    try:
        _, UID = _解析Cookie(_配置值(参数.get("config")))
    except 蓝奏云请求错误:
        return 0
    媒体 = 参数["record"].get("media") or {}
    进度表 = _归档逐项进度(参数)
    截止列表 = []
    for 索引, _ in _媒体项目列表(媒体):
        项 = 进度表.get(索引, {})
        if _项目归档资料(媒体, 索引) or not _归档项目可恢复(项):
            continue
        远端 = 项.get("remote_task")
        if 项.get("file_id") or isinstance(远端, asyncio.Task) and not 远端.done():
            return 0
        截止列表.append(max(蓝奏云上传下次允许.get(UID, 0), float(项.get("upload_retry_at") or 0)))
    return min(截止列表, default=0)


def _归档存在未确认上传(参数: dict[str, Any]) -> bool:
    return any(
        项.get("upload_submitted") and not 项.get("file_id")
        for 项 in _归档逐项进度(参数).values()
        if isinstance(项, dict)
    )


async def 归档消息图片(配置: Any, 记录: dict[str, Any]) -> None:
    if not _配置值(配置) or not _媒体项目列表(记录.get("media")):
        return
    键 = (str(记录.get("_session") or "").strip(), str(记录.get("message_id") or "").strip())
    if not all(键) or 键 in 图片归档进行中:
        return
    参数 = 图片归档待恢复.setdefault(键, {"config": 配置, "record": copy.deepcopy(记录)})
    记录 = 参数["record"]
    图片归档进行中.add(键)
    中断 = False
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        if not 消息记录.消息数据库已配置():
            return
        已处理: set[int] = set()
        async with 图片归档并发限制:
            while True:
                下一项 = next(((i, 项目) for i, 项目 in _媒体项目列表(记录.get("media")) if i not in 已处理), None)
                if 下一项 is None:
                    break
                索引, 项目 = 下一项
                已处理.add(索引)
                if _项目归档资料(记录["media"], 索引):
                    continue
                进度 = _归档逐项进度(参数).setdefault(索引, {})
                if not _归档项目可恢复(进度):
                    continue
                try:
                    归档资料 = await _执行图片归档(配置, 记录, 索引)
                    for 尝试 in range(3):
                        if 消息记录.更新消息媒体归档(键[0], 键[1], 归档资料, 原记录=记录, 媒体索引=索引):
                            break
                        await asyncio.sleep(0.5 * (尝试 + 1))
                    else:
                        raise 蓝奏云请求错误("message_persist_rejected")
                    记录["media"].setdefault("_lanzou_archives", {})[str(索引)] = dict(归档资料)
                    (参数.get("progress") or {}).pop(索引, None)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if not 进度.get("file_id") and not 进度.get("upload_submitted") and getattr(exc, "原因", "") not in {"upload_rate_limited", "upload_cooldown"}:
                        进度["source_failures"] = int(进度.get("source_failures", 0)) + 1
                    # 单项失败不阻止本条消息其余图片/视频。
                    业务码 = getattr(exc, "业务码", None)
                    等待 = max(0, int(float(进度.get("upload_retry_at") or 0) - asyncio.get_running_loop().time()))
                    日志 = logger.debug if getattr(exc, "原因", "") == "upload_cooldown" else logger.warning
                    日志("蓝奏云媒体归档失败：媒体序号=%s，种类=%s，阶段=%s，错误类型=%s，状态=%s，业务码=%s，原因=%s，等待秒=%s", 索引 + 1, _媒体种类(项目), getattr(exc, "阶段", "upload"), type(exc).__name__, getattr(exc, "状态码", 0) or "none", 业务码 if 业务码 is not None else "none", getattr(exc, "原因", "") or "none", 等待)
    except asyncio.CancelledError:
        中断 = True
        raise
    finally:
        图片归档进行中.discard(键)
        图片归档排队中.discard(键)
        完成 = all(_项目归档资料(记录["media"], i) for i, _ in _媒体项目列表(记录.get("media")))
        if 完成:
            图片归档待恢复.pop(键, None)
            图片归档失败冷却.pop(键, None)
        elif not 中断:
            当前时间 = asyncio.get_running_loop().time()
            上传截止 = _归档参数上传截止(参数)
            图片归档失败冷却[键] = 上传截止 if 上传截止 > 当前时间 else 当前时间 + 300
            if len(图片归档失败冷却) > 10000:
                过期键 = [k for k, v in 图片归档失败冷却.items() if v <= 当前时间]
                for k in 过期键:
                    图片归档失败冷却.pop(k, None)
                if len(图片归档失败冷却) > 10000:
                    图片归档失败冷却.pop(next(iter(图片归档失败冷却)), None)
            # 等待字典只保存元数据；已提交未知结果必须跨重复回显和热重载保留。
            # 前置失败仍由外层三次预算决定释放，已确认文件 ID 只重试分享/持久化。


def _归档等待任务完成(任务: asyncio.Task[Any], 键: tuple[str, str], 参数: dict[str, Any]) -> None:
    图片归档任务.discard(任务)
    if 参数.get("task") is 任务:
        参数.pop("task", None)
        图片归档排队中.discard(键)
        图片归档进行中.discard(键)
    _读取远端归档任务结果(任务)
    if 图片归档接收开启:
        _排空图片归档队列()


async def _归档有限重试(键: tuple[str, str], 参数: dict[str, Any]) -> None:
    for 次数 in range(3):
        if 次数:
            await asyncio.sleep(次数 * 2)
        图片归档失败冷却.pop(键, None)
        try:
            await 归档消息图片(参数["config"], 参数["record"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            图片归档失败冷却[键] = asyncio.get_running_loop().time() + 300
            logger.warning("蓝奏云媒体归档调度失败：错误类型=%s", type(exc).__name__)
            return
        if 键 not in 图片归档待恢复:
            return
        if not _归档参数可恢复(参数):
            图片归档失败冷却.pop(键, None)
            if not _归档存在未确认上传(参数):
                图片归档待恢复.pop(键, None)
            return
        上传截止 = _归档参数上传截止(参数)
        if 上传截止 > asyncio.get_running_loop().time():
            图片归档失败冷却[键] = 上传截止
            return
    # 三次后释放等待 Task；已确认的文件 ID 由唯一冷却句柄再次唤醒。
    图片归档失败冷却[键] = asyncio.get_running_loop().time() + 300


def _启动待恢复图片(键: tuple[str, str], 参数: dict[str, Any]) -> bool:
    if not 图片归档接收开启 or not _归档参数可恢复(参数):
        return False
    当前任务 = 参数.get("task")
    if isinstance(当前任务, asyncio.Task) and not 当前任务.done():
        return False
    if 键 in 图片归档进行中 or 键 in 图片归档排队中 or not _配置值(参数.get("config")):
        return False
    if len(图片归档任务) >= 图片归档最大任务数:
        return False
    if max(图片归档失败冷却.get(键, 0), _归档参数上传截止(参数)) > asyncio.get_running_loop().time():
        return False
    图片归档排队中.add(键)
    try:
        任务 = asyncio.create_task(_归档有限重试(键, 参数))
    except RuntimeError:
        图片归档排队中.discard(键)
        return False
    参数["task"] = 任务
    图片归档任务.add(任务)
    任务.add_done_callback(lambda 完成任务: _归档等待任务完成(完成任务, 键, 参数))
    return True


def _取消图片归档唤醒() -> None:
    global 图片归档唤醒句柄
    if 图片归档唤醒句柄 is not None:
        图片归档唤醒句柄.cancel()
        图片归档唤醒句柄 = None


def _排空图片归档队列() -> None:
    global 图片归档唤醒句柄
    if not 图片归档接收开启:
        return
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return
    _取消图片归档唤醒()
    图片归档任务.difference_update(任务 for 任务 in list(图片归档任务) if 任务.done())
    if len(图片归档任务) >= 图片归档最大任务数:
        # 满额时由完成回调继续排空，不在每次入队时重复扫描全部元数据。
        return
    当前时间 = 循环.time()
    下次唤醒: float | None = None
    for 键, 参数 in list(图片归档待恢复.items()):
        当前任务 = 参数.get("task")
        if isinstance(当前任务, asyncio.Task) and not 当前任务.done():
            continue
        if not _配置值(参数.get("config")) or not _归档参数可恢复(参数):
            continue
        截止 = max(图片归档失败冷却.get(键, 0), _归档参数上传截止(参数))
        if 截止 > 当前时间:
            下次唤醒 = 截止 if 下次唤醒 is None else min(下次唤醒, 截止)
            continue
        if len(图片归档任务) < 图片归档最大任务数:
            _启动待恢复图片(键, 参数)
        if len(图片归档任务) >= 图片归档最大任务数:
            break
    if 下次唤醒 is not None and len(图片归档任务) < 图片归档最大任务数:
        代次 = 图片归档调度代次

        def 到期唤醒() -> None:
            global 图片归档唤醒句柄
            if 图片归档唤醒句柄 is not 句柄 or 图片归档调度代次 != 代次:
                return
            图片归档唤醒句柄 = None
            if 图片归档接收开启:
                _排空图片归档队列()

        句柄 = 循环.call_at(下次唤醒, 到期唤醒)
        图片归档唤醒句柄 = 句柄


def 安排归档消息图片(配置: Any, 记录: dict[str, Any]) -> bool:
    from 功能文件.管理功能.基础功能 import 消息记录

    if not 图片归档接收开启 or not _配置值(配置) or not 消息记录.消息数据库已配置():
        return False
    媒体 = 记录.get("media")
    项目 = _媒体项目列表(媒体)
    if not 项目 or all(_项目归档资料(媒体, i) for i, _ in 项目):
        return False
    键 = (str(记录.get("_session") or "").strip(), str(记录.get("message_id") or "").strip())
    if not all(键):
        return False
    # 高峰期只排消息元数据，不提前下载附件或为每条消息创建等待 Task。
    参数 = 图片归档待恢复.setdefault(键, {"config": 配置, "record": copy.deepcopy(记录)})
    参数["config"] = 配置
    参数["record"]["media"] = 消息记录._合并媒体记录(参数["record"]["media"], 媒体)
    _排空图片归档队列()
    return True


def 启动图片归档任务(配置: Any = None) -> None:
    global 图片归档接收开启, 图片归档调度代次
    _取消图片归档唤醒()
    图片归档调度代次 += 1
    图片归档接收开启 = True
    for 键, 参数 in list(图片归档待恢复.items()):
        if 配置 is not None:
            参数["config"] = 配置
    _排空图片归档队列()


async def 停止图片归档任务() -> None:
    global 图片归档接收开启, 图片归档调度代次
    图片归档接收开启 = False
    图片归档调度代次 += 1
    _取消图片归档唤醒()
    任务列表 = [任务 for 任务 in 图片归档任务 if not 任务.done()]
    for 任务 in 任务列表:
        任务.cancel()
    if 任务列表:
        await asyncio.gather(*任务列表, return_exceptions=True)
    图片归档任务.clear()
    图片归档排队中.clear()
    图片归档进行中.clear()


def 构造网页媒体字段(媒体: Any, 会话标识: str, 类型: str, 消息ID: str) -> dict[str, Any] | None:
    if not isinstance(媒体, dict):
        return None
    结果 = copy.deepcopy(媒体)
    归档列表 = 结果.pop("_lanzou_archives", {})
    旧归档 = 结果.pop("_lanzou_archive", None)
    if not isinstance(归档列表, dict):
        归档列表 = {}
    if isinstance(旧归档, dict):
        归档列表.setdefault("0", 旧归档)
    for 索引, 项目 in _媒体项目列表(结果, 可下载=False):
        归档 = 归档列表.get(str(索引))
        if not isinstance(归档, dict):
            continue
        项目.update({"src": 构造消息图片代理地址(会话标识, 类型, 消息ID, 索引), "archived": True,
                    "content_type": str(归档.get("content_type") or ""), "size": int(归档.get("size") or 0)})
        for 字段 in ("url", "download_url", "_lanzou_archive", "_lanzou_archives"):
            项目.pop(字段, None)
        if 索引 == 0:
            for 字段 in ("src", "archived", "content_type", "size"):
                结果[字段] = 项目[字段]
            结果.pop("url", None)
            结果.pop("download_url", None)
    return 结果


def 构造消息图片代理地址(会话标识: str, 类型: str, 消息ID: str, 媒体索引: int = 0) -> str:
    return "/api/message/lanzou-image?" + urlencode({"chat_id": str(会话标识 or ""), "chat_type": str(类型 or "group"),
                                                     "message_id": str(消息ID or ""), "media_index": 媒体索引})


__all__ = ["安排归档消息图片", "构造消息图片代理地址", "构造网页媒体字段", "识别图片类型", "识别媒体类型",
           "归档消息图片", "打开归档图片", "启动图片归档任务", "停止图片归档任务"]
