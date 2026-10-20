"""帮助网页服务入口。

该模块只负责网页服务生命周期、路由注册和模板选择；配置读取、鉴权与
API 处理在 :mod:`帮助网页后端`，页面资源在独立的页面模块中维护。
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys
from typing import Any

from aiohttp import web

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)

_载入前已有页面模块 = set(sys.modules)

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
    if _页面模块.__name__ in _载入前已有页面模块:
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
        ("get", "/tutorial-images/{filename}", 后端._处理教程图片),
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
        ("post", "/api/pan-accounts/{platform}/scan", 后端._处理夸克网页扫码开始),
        ("get", "/api/pan-accounts/{platform}/scan/{scan_id}", 后端._处理夸克网页扫码状态),
        ("delete", "/api/pan-accounts/{platform}/scan/{scan_id}", 后端._处理夸克网页扫码取消),
        ("delete", "/api/pan-accounts/{platform}", 后端._处理网盘账号删除),
        ("post", "/api/pan-accounts/{platform}/enable", 后端._处理网盘账号开关),
        ("post", "/api/pan-accounts/{platform}/default", 后端._处理网盘账号默认),
        ("post", "/api/pan-account-selection", 后端._处理网盘账号选择),
        ("get", "/api/qq-reader-auth", 后端._处理QQ阅读登录态),
        ("post", "/api/qq-reader-auth", 后端._处理QQ阅读登录态保存),
        ("delete", "/api/qq-reader-auth", 后端._处理QQ阅读登录态删除),
        ("post", "/api/qq-reader-auth/select", 后端._处理QQ阅读账号选择),
        ("post", "/api/qq-reader-auth/enable", 后端._处理QQ阅读账号启用),
        ("post", "/api/qq-reader-auth/refresh", 后端._处理QQ阅读账号刷新),
        ("post", "/api/qq-reader-auth/credential", 后端._处理QQ阅读账号凭据),
        ("post", "/api/qq-reader-auth/scan", 后端._处理QQ阅读网页扫码开始),
        ("get", "/api/qq-reader-auth/scan", 后端._处理QQ阅读网页扫码状态),
        ("delete", "/api/qq-reader-auth/scan", 后端._处理QQ阅读网页扫码取消),
        ("post", "/api/message/chats", 后端._处理消息聊天列表),
        ("post", "/api/message/history", 后端._处理消息历史),
        ("post", "/api/message/user-profile/refresh", 后端._处理私聊资料刷新),
        ("get", "/api/message/media", 后端._处理消息媒体),
        ("get", "/api/message/lanzou-image", 后端._处理蓝奏云归档图片),
        ("get", "/api/message/markdown-media/{token}", 后端._处理临时Markdown媒体),
        ("get", "/api/message/local-media/{filename}", 后端._处理本地发送媒体),
        ("get", "/api/message/layout", 后端._处理消息布局),
        ("post", "/api/message/layout", 后端._处理消息布局),
        ("get", "/api/message/ws", 后端._处理消息WebSocket),
        ("get", "/api/message/events", 后端._处理消息事件),
        ("post", "/api/message/send", 后端._处理消息发送),
        ("post", "/api/message/recall", 后端._处理消息撤回),
        ("post", "/api/message/group-member/mute", 后端._处理消息禁言),
        ("post", "/api/message/group-member/unmute", 后端._处理消息解除禁言),
        ("post", "/api/message/group-member/mutes", 后端._处理消息禁言状态),
        ("post", "/api/message/group-roles", 后端._处理群角色),
        ("post", "/api/message/pin", 后端._处理消息置顶),
        ("post", "/api/message/read", 后端._处理消息已读),
        ("post", "/api/message/remarks", 后端._处理群备注),
        ("post", "/api/message/group-info/refresh", 后端._处理群信息刷新),
        ("post", "/api/message/group-settings", 后端._处理群设置),
        ("post", "/api/message/group-members", 后端._处理群成员列表),
        ("post", "/api/message/group-member/info", 后端._处理群成员信息),
        ("post", "/api/message/group-members/remove", 后端._处理群成员批量移除),
        ("post", "/api/message/group-blacklist", 后端._处理群黑名单查询),
        ("post", "/api/message/group-blacklist/update", 后端._处理群黑名单操作),
        ("post", "/api/message/group-ad", 后端._处理群广告开关),
        ("post", "/api/message/group-pan", 后端._处理群网盘选择),
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


async def _恢复控制台会话(服务: 帮助网页服务, 配置: Any) -> None:
    try:
        配置快照 = 后端.获取控制台会话配置快照(配置)
        快照 = await 后端._控制台线程执行(后端._读取持久化控制台会话, 配置快照)
        if 后端.当前帮助网页服务 is not 服务 or 后端.当前帮助网页配置 is not 配置:
            return
        if 后端.获取控制台认证指纹(配置快照) != 后端.获取控制台认证指纹(配置):
            return
        for 会话值, (到期时间, 用户名) in 快照.items():
            if 会话值 in 后端.控制台会话恢复排除:
                continue
            后端.控制台会话.setdefault(会话值, 到期时间)
            后端.控制台会话身份.setdefault(会话值, 用户名)
            后端.控制台会话最后持久化.setdefault(会话值, 0.0)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.debug("帮助控制台会话后台恢复失败：错误类型=%s", type(exc).__name__)


async def _刷新公开地址(服务: 帮助网页服务, 配置: Any) -> None:
    try:
        地址 = await 后端._控制台线程执行(后端._计算帮助网页地址, 配置)
        if 后端.当前帮助网页服务 is 服务 and 后端.当前帮助网页配置 is 配置 and 地址:
            服务.public_url = 后端._构造控制台访问地址(地址, 配置)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.debug("帮助控制台访问地址后台更新失败：错误类型=%s", type(exc).__name__)


@web.middleware
async def _等待控制台会话恢复(request: web.Request, handler: Any) -> web.StreamResponse:
    会话值 = str(request.cookies.get(后端.控制台会话Cookie名) or "").strip()
    任务 = 后端.控制台会话恢复任务
    if 会话值 and 会话值 not in 后端.控制台会话 and 任务 is not None and not 任务.done():
        await asyncio.shield(任务)
    return await handler(request)


async def 启动帮助网页服务(配置: Any = None) -> 帮助网页服务 | None:
    """先启动监听；数据库会话和公网地址在后台恢复。"""
    await 停止帮助网页服务(后端.当前帮助网页服务, 保留会话=True)
    后端.当前帮助网页服务 = None
    后端.网页服务启动状态 = False
    后端.当前帮助网页配置 = 配置
    后端.同步控制台会话认证(配置)
    基础地址 = 后端._计算帮助网页启动地址(配置)
    public_url = 后端._构造控制台访问地址(基础地址, 配置)
    host, port = 后端._读取监听配置(配置)
    app = web.Application(
        client_max_size=300 * 1024 * 1024,
        middlewares=[_等待控制台会话恢复, _压缩控制台响应],
    )
    _注册路由(app)
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=2.0)
    try:
        await runner.setup()
        await web.TCPSite(runner, host, port).start()
    except Exception as exc:
        await runner.cleanup()
        logger.warning("帮助控制台启动失败：错误类型=%s", type(exc).__name__)
        return None
    服务 = 后端.当前帮助网页服务 = 帮助网页服务(runner, public_url, host, port)
    后端.网页服务启动状态 = True
    后端._安排控制台后台任务(后端._清理本地发送媒体同步)
    后端.控制台会话恢复任务 = asyncio.create_task(_恢复控制台会话(服务, 配置), name="控制台会话恢复")
    for 任务 in (后端.控制台会话恢复任务, asyncio.create_task(_刷新公开地址(服务, 配置), name="控制台公开地址")):
        后端.控制台后台任务.add(任务)
        任务.add_done_callback(后端.控制台后台任务.discard)
    logger.info("帮助控制台已启动：监听地址=%s, 监听端口=%s, 访问地址=%s", host, port, 基础地址)
    return 服务


async def 停止帮助网页服务(服务: 帮助网页服务 | None, *, 保留会话: bool = False) -> None:
    try:
        await 后端._取消全部夸克网页扫码()
        await 后端._取消全部QQ阅读网页扫码()
        await 后端.停止实时连接()
        if 服务 is not None:
            await 服务.runner.cleanup()
    except Exception as exc:
        logger.warning("帮助控制台停止失败：错误类型=%s", type(exc).__name__)
    finally:
        try:
            await 后端.关闭媒体代理会话()
        except Exception as exc:
            logger.debug("帮助控制台媒体代理会话关闭失败：错误类型=%s", type(exc).__name__)
        后端.清空临时Markdown媒体()
        后端.关闭控制台执行器()
        后端.控制台会话恢复任务 = None
        if 后端.当前帮助网页服务 is 服务:
            后端.当前帮助网页服务 = None
            后端.网页服务启动状态 = None
            后端.当前帮助网页配置 = None
            if not 保留会话:
                后端.控制台会话.clear()
                后端.控制台会话身份.clear()
                后端.控制台会话最后持久化.clear()


__all__ = ["获取帮助网页地址", "启动帮助网页服务", "停止帮助网页服务"]
