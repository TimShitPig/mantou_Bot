"""仅向同源、已登录的管理页面返回明确允许查看的已保存字段。"""

from __future__ import annotations

import hmac
import json

from aiohttp import web

from . import 帮助网页后端 as 后端


密码显示请求上限 = 16 * 1024
_允许显示字段 = frozenset({"help_web_admin_password", "database_password", "zlibrary_mail_api_key"})


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
    if 请求.content_type != "application/json":
        return _错误(400, "密码查看参数无效")
    if 请求.content_length is not None and 请求.content_length > 密码显示请求上限:
        return _错误(413, "密码查看请求过大")
    try:
        正文 = await 请求.read()
        if len(正文) > 密码显示请求上限:
            return _错误(413, "密码查看请求过大")
        数据 = json.loads(正文.decode("utf-8"))
        if not isinstance(数据, dict) or set(数据) != {"field"}:
            return _错误(400, "密码查看参数无效")
        字段 = 数据["field"]
        if not isinstance(字段, str) or 字段 not in _允许显示字段:
            return _错误(400, "密码查看参数无效")
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
