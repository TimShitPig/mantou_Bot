"""已保存控制台密码的按需显示。"""

from __future__ import annotations

from collections import deque
import hmac
import ipaddress
import json
import math
import time
from urllib.parse import urlsplit

from aiohttp import web

from . import 帮助网页后端 as 后端


密码显示请求上限 = 16 * 1024
_允许显示字段 = frozenset({"help_web_admin_password", "database_password"})
_尝试次数 = 6
_尝试窗口秒 = 60
_尝试时间: deque[float] = globals().get("_尝试时间") or deque(maxlen=_尝试次数)
_代理头 = ("Forwarded", "X-Forwarded-For", "X-Forwarded-Proto", "X-Forwarded-Host", "X-Real-IP", "Via")


def _响应(状态: int, 数据: dict, **附加头: str) -> web.Response:
    return web.json_response(
        数据,
        status=状态,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", **附加头},
    )


def _错误(状态: int, 文本: str, **附加头: str) -> web.Response:
    return _响应(状态, {"ok": False, "error": 文本}, **附加头)


def _是回环IP(主机: str) -> bool:
    try:
        地址 = ipaddress.ip_address(主机)
    except ValueError:
        return False
    if isinstance(地址, ipaddress.IPv6Address) and 地址.ipv4_mapped is not None:
        地址 = 地址.ipv4_mapped
    return 地址.is_loopback


def _安全同源请求(请求: web.Request) -> bool:
    """只信任当前连接的 TLS 或不经 HTTP 代理的回环连接。"""
    来源头 = 请求.headers.getall("Origin", [])
    主机头 = 请求.headers.getall("Host", [])
    传输 = 请求.transport
    if len(来源头) != 1 or len(主机头) != 1 or 传输 is None:
        return False
    try:
        来源 = urlsplit(来源头[0])
        主机 = urlsplit("//" + 主机头[0])
        if any(
            地址.username is not None or 地址.password is not None or 地址.path
            or 地址.query or 地址.fragment
            for 地址 in (来源, 主机)
        ):
            return False
        if not 来源.hostname or 来源.hostname != 主机.hostname:
            return False
        使用TLS = 传输.get_extra_info("ssl_object") is not None
        协议, 默认端口 = ("https", 443) if 使用TLS else ("http", 80)
        来源端口 = 默认端口 if 来源.port is None else 来源.port
        请求端口 = 默认端口 if 主机.port is None else 主机.port
        if 来源.scheme != 协议 or not 来源端口 or 来源端口 != 请求端口:
            return False
    except ValueError:
        return False
    if 使用TLS:
        return True
    对端 = 传输.get_extra_info("peername")
    return bool(
        isinstance(对端, tuple)
        and 对端
        and _是回环IP(str(对端[0]))
        and (来源.hostname == "localhost" or _是回环IP(来源.hostname))
        and not any(头 in 请求.headers for 头 in _代理头)
    )


def _登记验证尝试() -> int:
    """共享固定窗口，返回冷却秒数；不记录会话、客户端或密码。"""
    现在 = time.monotonic()
    while _尝试时间 and 现在 - _尝试时间[0] >= _尝试窗口秒:
        _尝试时间.popleft()
    if len(_尝试时间) >= _尝试次数:
        return max(1, math.ceil(_尝试窗口秒 - (现在 - _尝试时间[0])))
    _尝试时间.append(现在)
    return 0


async def 处理保存密码(请求: web.Request) -> web.Response:
    """重新验证管理员密码，再读取明确允许显示的一个已保存字段。"""
    if 请求.method != "POST":
        return _错误(405, "只允许 POST 请求", Allow="POST")
    if not 后端._请求已授权(请求):
        return _错误(401, "请重新登录控制台")
    if not _安全同源请求(请求):
        return _错误(403, "请通过服务器本机或支持直接 TLS 的控制台连接查看已保存密码")
    会话 = 后端._取得请求会话(请求)
    认证指纹 = 后端.控制台会话认证指纹
    if 请求.content_type != "application/json":
        return _错误(400, "密码查看参数无效")
    if 请求.content_length is not None and 请求.content_length > 密码显示请求上限:
        return _错误(413, "密码查看请求过大")
    try:
        正文 = await 请求.read()
        if len(正文) > 密码显示请求上限:
            return _错误(413, "密码查看请求过大")
        数据 = json.loads(正文.decode("utf-8"))
        if not isinstance(数据, dict) or set(数据) != {"field", "password"}:
            return _错误(400, "密码查看参数无效")
        字段, 密码 = 数据["field"], 数据["password"]
        if not isinstance(字段, str) or 字段 not in _允许显示字段 or not isinstance(密码, str) or not 密码:
            return _错误(400, "密码查看参数无效")
        提交密码 = 密码.encode("utf-8")
    except web.HTTPRequestEntityTooLarge:
        return _错误(413, "密码查看请求过大")
    except (UnicodeError, ValueError, RecursionError):
        return _错误(400, "密码查看参数无效")

    if (
        not 后端._请求已授权(请求)
        or not hmac.compare_digest(认证指纹, 后端.控制台会话认证指纹)
        or not hmac.compare_digest(会话, 后端._取得请求会话(请求))
    ):
        return _错误(401, "请重新登录控制台")
    冷却 = _登记验证尝试()
    if 冷却:
        return _错误(429, "操作过于频繁，请稍后重试", **{"Retry-After": str(冷却)})
    配置 = 后端._当前作用域配置()
    _, 当前密码 = 后端._读取控制台账号(配置)
    if not 当前密码 or not hmac.compare_digest(提交密码, 当前密码.encode("utf-8")):
        return _错误(403, "管理员密码验证失败")
    if 字段 == "help_web_admin_password":
        值 = str(后端._读取帮助网页字段(配置, 字段) or "")
    else:
        值 = 后端.获取控制台会话配置快照(配置)["database_settings"]["database_password"]
    if not 值:
        return _错误(404, "没有已保存的密码")
    return _响应(200, {"ok": True, "value": 值})
