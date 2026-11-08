"""仅向同源、已登录的管理页面返回明确允许查看的已保存字段。"""

from __future__ import annotations

import hmac
import json
import re
from collections.abc import Callable

from aiohttp import web

from . import 帮助网页后端 as 后端


密码显示请求上限 = 16 * 1024
_允许显示字段 = frozenset({"help_web_admin_password", "database_password", "zlibrary_mail_api_key"})
_网盘凭据引用格式 = re.compile(r"[0-9a-f]{64}")


def _响应(状态: int, 数据: dict, **附加头: str) -> web.Response:
    return web.json_response(
        数据,
        status=状态,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", **附加头},
    )


def _错误(状态: int, 文本: str, **附加头: str) -> web.Response:
    return _响应(状态, {"ok": False, "error": 文本}, **附加头)


async def 处理保存密码(请求: web.Request) -> web.Response:
    if 请求.method != "POST":
        return _错误(405, "只允许 POST 请求", Allow="POST")
    if not 后端._请求已授权(请求):
        return _错误(401, "请重新登录控制台")
    if (
        len(请求.headers.getall("Origin", [])) != 1
        or len(请求.headers.getall("Host", [])) != 1
        or not 后端._请求来自同源(请求)
    ):
        return _错误(403, "请从当前控制台页面查看已保存密码")
    会话 = 后端._取得请求会话(请求)
    认证指纹 = 后端.控制台会话认证指纹

    def 会话仍有效() -> bool:
        return (
            后端._请求已授权(请求)
            and hmac.compare_digest(认证指纹, 后端.控制台会话认证指纹)
            and hmac.compare_digest(会话, 后端._取得请求会话(请求))
        )

    if 请求.content_type != "application/json":
        return _错误(400, "密码查看参数无效")
    if 请求.content_length is not None and 请求.content_length > 密码显示请求上限:
        return _错误(413, "密码查看请求过大")
    try:
        正文 = await 请求.read()
        if len(正文) > 密码显示请求上限:
            return _错误(413, "密码查看请求过大")
        数据 = json.loads(正文.decode("utf-8"))
        if not isinstance(数据, dict) or not isinstance(数据.get("field"), str):
            return _错误(400, "密码查看参数无效")
    except web.HTTPRequestEntityTooLarge:
        return _错误(413, "密码查看请求过大")
    except (UnicodeError, ValueError, RecursionError):
        return _错误(400, "密码查看参数无效")

    if not 会话仍有效():
        return _错误(401, "请重新登录控制台")
    字段 = 数据["field"]
    if 字段 == "pan_cookie":
        return await _处理网盘Cookie(数据, 会话仍有效)
    if set(数据) != {"field"} or 字段 not in _允许显示字段:
        return _错误(400, "密码查看参数无效")
    配置 = 后端._当前作用域配置()
    if 字段 == "help_web_admin_password":
        值 = str(后端._读取帮助网页字段(配置, 字段) or "")
    elif 字段 == "database_password":
        值 = 后端.获取控制台会话配置快照(配置)["database_settings"]["database_password"]
    else:
        值 = str(后端._读取插件配置值(配置, "zlibrary_account_settings", 字段, "") or "")
    if not 值:
        return _错误(404, "没有已保存的值")
    return _响应(200, {"ok": True, "value": 值})


async def _处理网盘Cookie(数据: dict, 会话仍有效: Callable[[], bool]) -> web.Response:
    from 功能文件.管理功能.网盘功能 import 网盘Cookie

    平台 = 数据.get("platform")
    序号 = 数据.get("index")
    凭据引用 = 数据.get("credential_ref")
    if (
        set(数据) != {"field", "platform", "index", "credential_ref"}
        or not isinstance(平台, str)
        or 平台 not in 网盘Cookie.平台状态键
        or type(序号) is not int
        or 序号 < 1
        or not isinstance(凭据引用, str)
        or not _网盘凭据引用格式.fullmatch(凭据引用)
    ):
        return _错误(400, "网盘 Cookie 查看参数无效")
    try:
        Cookie = await 后端._控制台线程执行(
            网盘Cookie.读取指定网盘账号Cookie, 后端._当前作用域配置(), 平台, 序号, 凭据引用
        )
    except Exception:
        return _错误(503, "暂时无法读取网盘 Cookie，请稍后重试")
    if not 会话仍有效():
        return _错误(401, "请重新登录控制台")
    if not Cookie:
        return _错误(404, "网盘账号已变更，请刷新页面后重试")
    return _响应(200, {"ok": True, "value": Cookie})
