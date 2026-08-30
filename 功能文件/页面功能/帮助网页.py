"""帮助网页服务入口。

该模块只负责网页服务生命周期、路由注册和模板选择；配置读取、鉴权与
API 处理在 :mod:`帮助网页后端`，页面资源在独立的页面模块中维护。
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from aiohttp import web

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)

from . import 帮助网页后端 as 后端
from . import 帮助网页页面 as 页面
from . import 登录页面
from . import 登录页面脚本, 登录页面样式, 帮助网页脚本, 帮助网页样式

# AstrBot 重载主模块时显式刷新页面依赖，避免继续使用旧的 HTML/CSS/JS。
for _页面模块 in (
    帮助网页样式,
    帮助网页脚本,
    登录页面样式,
    登录页面脚本,
    页面,
    后端,
):
    importlib.reload(_页面模块)

帮助网页服务 = 后端.帮助网页服务


def 获取帮助网页地址(配置: Any = None) -> str:
    """返回帮助菜单使用的网页地址。"""

    return 后端.获取帮助网页地址(配置)


async def _处理帮助网页(request: web.Request) -> web.Response:
    页面内容 = (
        页面.渲染控制台页面()
        if 后端._请求已授权(request)
        else 登录页面.渲染登录页面()
    )
    return web.Response(
        text=页面内容,
        content_type="text/html",
        charset="utf-8",
        headers={"Cache-Control": "no-store"},
    )


def _注册路由(app: web.Application) -> None:
    路由 = (
        ("get", "/", _处理帮助网页),
        ("post", "/api/login", 后端._处理控制台登录),
        ("post", "/api/logout", 后端._处理控制台退出),
        ("get", "/api/dashboard", 后端._处理控制台数据),
        ("get", "/api/bot-profile", 后端._处理机器人资料),
        ("post", "/api/novel-switch", 后端._处理小说开关),
        ("post", "/api/pan-switch", 后端._处理网盘切换),
        ("post", "/api/pan-enable", 后端._处理网盘开关),
        ("get", "/api/config", 后端._处理插件配置数据),
        ("post", "/api/config", 后端._处理插件配置写入),
        ("get", "/api/pan-accounts/{platform}", 后端._处理网盘账号列表),
        ("post", "/api/pan-accounts/{platform}", 后端._处理网盘账号新增),
        ("delete", "/api/pan-accounts/{platform}", 后端._处理网盘账号删除),
        ("post", "/api/pan-account-selection", 后端._处理网盘账号选择),
        ("get", "/api/qq-reader-auth", 后端._处理QQ阅读登录态),
        ("post", "/api/qq-reader-auth", 后端._处理QQ阅读登录态保存),
        ("delete", "/api/qq-reader-auth", 后端._处理QQ阅读登录态删除),
        ("post", "/api/message/chats", 后端._处理消息聊天列表),
        ("post", "/api/message/history", 后端._处理消息历史),
        ("get", "/api/message/media", 后端._处理消息媒体),
        ("get", "/api/message/markdown-image/{token}", 后端._处理临时Markdown图片),
        ("get", "/api/message/layout", 后端._处理消息布局),
        ("post", "/api/message/layout", 后端._处理消息布局),
        ("get", "/api/message/ws", 后端._处理消息WebSocket),
        ("get", "/api/message/events", 后端._处理消息事件),
        ("post", "/api/message/send", 后端._处理消息发送),
        ("post", "/api/message/recall", 后端._处理消息撤回),
        ("post", "/api/message/group-member/mute", 后端._处理消息禁言),
        ("post", "/api/message/group-roles", 后端._处理群角色),
        ("post", "/api/message/pin", 后端._处理消息置顶),
        ("post", "/api/message/read", 后端._处理消息已读),
        ("post", "/api/message/remarks", 后端._处理群备注),
        ("post", "/api/message/group-info/refresh", 后端._处理群信息刷新),
        ("post", "/api/message/group-ad", 后端._处理群广告开关),
        ("get", "/{tail:.*}", _处理帮助网页),
    )
    for 方法, 路径, 处理器 in 路由:
        getattr(app.router, f"add_{方法}")(路径, 处理器)


@web.middleware
async def _压缩控制台响应(request: web.Request, handler: Any) -> web.StreamResponse:
    """压缩控制台 HTML/JSON，实时事件流和 WebSocket 保持原样。"""
    响应 = await handler(request)
    if not isinstance(响应, web.Response):
        return 响应
    if 响应.headers.get("Content-Encoding"):
        return 响应
    if 响应.content_type not in {"text/html", "application/json"}:
        return 响应
    正文 = getattr(响应, "body", None)
    if not 正文 or len(正文) < 1024:
        return 响应
    try:
        响应.enable_compression()
    except Exception as exc:
        logger.debug("帮助控制台响应压缩跳过：错误类型=%s", type(exc).__name__)
    return 响应


async def 启动帮助网页服务(配置: Any = None) -> 帮助网页服务 | None:
    """启动帮助网页并返回可供插件生命周期保存的服务句柄。"""

    await 停止帮助网页服务(后端.当前帮助网页服务)
    后端.当前帮助网页服务 = None
    后端.网页服务启动状态 = False
    后端.当前帮助网页配置 = 配置
    后端.控制台会话.clear()
    后端.控制台会话身份.clear()
    后端._加载持久化控制台会话()

    基础地址 = 后端._计算帮助网页地址(配置)
    public_url = 后端._构造控制台访问地址(基础地址, 配置)
    host, port = 后端._读取监听配置(配置)
    app = web.Application(middlewares=[_压缩控制台响应])
    _注册路由(app)
    runner = web.AppRunner(app, access_log=None)
    try:
        await runner.setup()
        await web.TCPSite(runner, host, port).start()
    except Exception as exc:
        await runner.cleanup()
        logger.warning("帮助控制台启动失败：错误类型=%s", type(exc).__name__)
        return None

    后端.当前帮助网页服务 = 帮助网页服务(runner, public_url, host, port)
    后端.网页服务启动状态 = True
    logger.info(
        "帮助控制台已启动：监听地址=%s, 监听端口=%s, 访问地址=%s",
        host,
        port,
        基础地址,
    )
    return 后端.当前帮助网页服务


async def 停止帮助网页服务(服务: 帮助网页服务 | None) -> None:
    """停止网页服务并清理内存会话。"""

    try:
        if 服务 is not None:
            await 服务.runner.cleanup()
    except Exception as exc:
        logger.warning("帮助控制台停止失败：错误类型=%s", type(exc).__name__)
    finally:
        后端.关闭控制台执行器()
        if 后端.当前帮助网页服务 is 服务:
            后端.当前帮助网页服务 = None
            后端.网页服务启动状态 = None
            后端.当前帮助网页配置 = None
            后端.控制台会话.clear()
            后端.控制台会话身份.clear()


__all__ = ["获取帮助网页地址", "启动帮助网页服务", "停止帮助网页服务"]
