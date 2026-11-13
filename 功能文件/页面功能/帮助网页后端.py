from __future__ import annotations

import asyncio
import base64
import copy
import contextvars
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import hmac
import inspect
import ipaddress
import mimetypes
import json
import logging
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from 功能文件.管理功能.基础功能.机器人作用域 import (
    获取机器人配置, 获取当前机器人AppID, 绑定机器人作用域,
    规范化机器人AppID, 机器人独立配置分类, 机器人独立帮助字段,
)

import aiohttp
from aiohttp import ClientError, ClientSession, ClientTimeout, TCPConnector, web

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)

默认监听地址 = "0.0.0.0"
默认监听端口 = 8090
# 由已加载插件的生命周期在网页监听前注入，不单独维护版本常量。
控制台版本 = ""
默认控制台用户名 = "admin"
默认控制台密码 = ""
控制台会话Cookie名 = "mantou_console_session"
控制台会话有效期 = 30 * 24 * 60 * 60
控制台会话命名空间 = "console_session"
消息布局命名空间 = "msg_console_layout"
消息布局默认值 = {
    "list_width": 273,
    "composer_height": 173,
    "list_collapsed": False,
    "composer_collapsed": False,
}
媒体代理最大字节数 = 256 * 1024 * 1024
媒体代理超时秒 = 30
媒体代理连接超时秒 = 10
媒体代理读取超时秒 = 60
媒体代理主机后缀 = (
    "multimedia.nt.qq.com.cn",
    "qqbot.ugcimg.cn",
    "gchat.qpic.cn",
    "qpic.cn",
    "qlogo.cn",
    "qq.com.cn",
    "qq.com",
)
媒体代理失败缓存有效期秒 = 5 * 60
媒体代理失败缓存上限 = 4096
媒体代理失败缓存: dict[str, float] = globals().get("媒体代理失败缓存") or {}
媒体代理失败缓存锁 = globals().get("媒体代理失败缓存锁") or threading.Lock()
@dataclass
class 帮助网页服务:
    runner: web.AppRunner
    public_url: str
    host: str
    port: int


# importlib.reload 会复用原模块字典；保留旧引用，确保重载时可以清理旧端口和会话。
当前帮助网页服务: 帮助网页服务 | None = globals().get("当前帮助网页服务")
自动公开地址缓存: str | None = globals().get("自动公开地址缓存")
网页服务启动状态: bool | None = globals().get("网页服务启动状态")
当前帮助网页配置: Any = globals().get("当前帮助网页配置")
控制台会话: dict[str, float] = globals().get("控制台会话") or {}
控制台会话身份: dict[str, str] = globals().get("控制台会话身份") or {}
控制台会话最后持久化: dict[str, float] = globals().get("控制台会话最后持久化") or {}
控制台会话恢复排除: set[str] = globals().get("控制台会话恢复排除") or set()
控制台会话恢复任务: asyncio.Task[Any] | None = globals().get("控制台会话恢复任务")
控制台会话认证指纹: str = globals().get("控制台会话认证指纹", "")
_控制台会话存储锁 = globals().get("_控制台会话存储锁") or threading.RLock()
_机器人配置请求锁: dict[tuple[int, str], dict[str, Any]] = globals().get("_机器人配置请求锁") or {}
_聊天清理确认会话: dict[str, dict[str, Any]] = globals().get("_聊天清理确认会话") or {}
_聊天清理执行任务: set[asyncio.Task[Any]] = globals().get("_聊天清理执行任务") or set()
控制台后台任务: set[asyncio.Task[Any]] = globals().get("控制台后台任务") or set()
夸克网页扫码会话: dict[str, dict[str, Any]] = globals().get("夸克网页扫码会话") or {}
夸克扫码启动代次: dict[str, str] = globals().get("夸克扫码启动代次") or {}
扫码所有者会话: dict[str, str] = globals().get("扫码所有者会话") or {}
QQ阅读网页扫码会话: dict[str, dict[str, Any]] = globals().get("QQ阅读网页扫码会话") or {}
QQ阅读扫码启动代次: dict[str, str] = globals().get("QQ阅读扫码启动代次") or {}
晋江网页扫码会话: dict[str, dict[str, Any]] = globals().get("晋江网页扫码会话") or {}
晋江扫码启动代次: dict[str, str] = globals().get("晋江扫码启动代次") or {}
QQ阅读网页短信会话: dict[str, dict[str, Any]] = globals().get("QQ阅读网页短信会话") or {}
QQ阅读短信启动代次: dict[str, str] = globals().get("QQ阅读短信启动代次") or {}
_控制台执行器: ThreadPoolExecutor | None = globals().get("_控制台执行器")
_控制台执行器锁 = globals().get("_控制台执行器锁") or threading.Lock()
控制台执行器最大并发数 = 4
消息列表缓存秒数 = 3.0
消息列表缓存最大条目 = 64
消息列表缓存: dict[tuple[str, str, int, int, str | None], tuple[float, dict[str, Any]]] = globals().get("消息列表缓存") or {}
消息列表缓存锁: dict[tuple[str, str, int, int, str | None], asyncio.Lock] = globals().get("消息列表缓存锁") or {}
消息列表后台刷新: set[tuple[str, str, int, int, str | None]] = globals().get("消息列表后台刷新") or set()
def _清理旧消息列表昵称任务() -> None:
    """停用旧版补名任务，等旧协程及完成回调退出后移除兼容引用。"""
    模块状态 = globals()
    旧任务表 = 模块状态.get("消息列表昵称回填任务")
    if not isinstance(旧任务表, dict):
        return
    旧任务 = [任务 for 任务 in 旧任务表.values() if isinstance(任务, asyncio.Task)]
    旧任务表.clear()

    def 移除旧引用() -> None:
        if any(not 任务.done() for 任务 in 旧任务):
            return
        if 模块状态.get("消息列表昵称回填任务") is 旧任务表:
            模块状态.pop("消息列表昵称回填任务", None)
        模块状态.pop("_后台回填消息列表昵称", None)
        模块状态.pop("_安排消息列表昵称回填", None)

    def 已结束(任务: asyncio.Task[Any]) -> None:
        # 旧回调仍按全局名称访问任务表；让它们先完成，下一轮再删引用。
        循环 = 任务.get_loop()
        if not 循环.is_closed():
            循环.call_soon(移除旧引用)

    if not 旧任务:
        移除旧引用()
        return
    for 任务 in 旧任务:
        控制台后台任务.add(任务)
        任务.add_done_callback(控制台后台任务.discard)
        if 任务.done():
            已结束(任务)
        else:
            任务.add_done_callback(已结束)
            任务.cancel()


_清理旧消息列表昵称任务()
消息列表缓存版本 = int(globals().get("消息列表缓存版本", 0) or 0) + 1
消息历史查询任务: dict[tuple[Any, ...], asyncio.Task[Any]] = (
    globals().get("消息历史查询任务") or {}
)
实时连接任务: set[asyncio.Task[Any]] = globals().get("实时连接任务") or set()
_媒体代理会话: ClientSession | None = globals().get("_媒体代理会话")
群状态刷新任务: dict[tuple[str, str, str], asyncio.Task[Any]] = globals().get("群状态刷新任务") or {}
群状态刷新失败冷却: dict[tuple[str, str, str], float] = globals().get("群状态刷新失败冷却") or {}
_群状态刷新并发: asyncio.Semaphore | None = None



def _当前作用域配置() -> Any:
    return 获取机器人配置(当前帮助网页配置)


def _扫码所有者(会话值: str) -> str:
    所有者 = hashlib.sha256((会话值 + "\x1f" + 获取当前机器人AppID()).encode("utf-8")).hexdigest()
    扫码所有者会话[所有者] = 会话值
    return 所有者


def _待取消扫码所有者(会话值: str) -> set[str]:
    if 获取当前机器人AppID():
        return {_扫码所有者(会话值)}
    return {键 for 键, 值 in 扫码所有者会话.items() if 值 == 会话值}


@web.middleware
async def 机器人作用域中间件(request: web.Request, handler: Any) -> web.StreamResponse:
    """每次请求固定机器人身份，选择页面及登录不继承其他页面的身份。"""
    路径 = request.path
    if 路径 in {"/api/zlibrary-accounts/manage", "/api/zlibrary-accounts/import"}:
        request = request.clone(client_max_size=128 * 1024)
    if not 路径.startswith("/api/") or 路径 in {"/api/login", "/api/logout", "/api/bot-profile"}:
        with 绑定机器人作用域(""):
            return await handler(request)
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    媒体读取 = 路径 in {"/api/message/media", "/api/message/lanzou-image", "/api/message/quark-media"} or 路径.startswith("/api/message/local-media/")
    appid = 规范化机器人AppID(request.query.get("appid"))
    if not appid:
        if 媒体读取 and not request.query.get("appid"):
            with 绑定机器人作用域(""):
                return await handler(request)
        return _控制台错误(400, "请先选择机器人")
    from 功能文件.管理功能.基础功能 import 消息记录
    if appid not in 消息记录.获取已配置机器人AppID列表():
        return _控制台错误(409, "机器人配置已变更，请重新选择")
    if request.content_type == "application/json" and request.can_read_body:
        try:
            数据 = await request.json()
        except (ValueError, UnicodeDecodeError):
            return _控制台错误(400, "请求参数无效")
        if isinstance(数据, dict) and "appid" in 数据 and str(数据["appid"] or "").strip() != appid:
            return _控制台错误(400, "机器人参数不一致")
    request["机器人AppID"] = appid
    with 绑定机器人作用域(appid):
        响应 = await handler(request)
    if isinstance(响应, web.Response) and 响应.content_type == "application/json" and 响应.body:
        try:
            内容 = json.loads(响应.body)
            if isinstance(内容, dict):
                内容.setdefault("appid", appid)
                响应.body = json.dumps(内容, ensure_ascii=False).encode("utf-8")
        except (ValueError, UnicodeDecodeError):
            pass
    return 响应


def _获取控制台执行器() -> ThreadPoolExecutor:
    """为网页数据库读写提供独立线程池，避免下载任务占满默认执行器。"""
    global _控制台执行器
    with _控制台执行器锁:
        if _控制台执行器 is None or getattr(_控制台执行器, "_shutdown", False):
            _控制台执行器 = ThreadPoolExecutor(
                max_workers=控制台执行器最大并发数,
                thread_name_prefix="mantou-console",
            )
        return _控制台执行器


async def _控制台线程执行(函数: Any, *参数: Any, **关键字参数: Any) -> Any:
    """把可能阻塞的控制台操作移出事件循环和下载默认线程池。"""
    loop = asyncio.get_running_loop()
    调用 = partial(contextvars.copy_context().run, 函数, *参数, **关键字参数)
    return await loop.run_in_executor(_获取控制台执行器(), 调用)


def 关闭控制台执行器() -> None:
    """停止网页服务时释放独立执行器，重载后重新建立。"""
    global _控制台执行器
    with _控制台执行器锁:
        执行器 = _控制台执行器
        _控制台执行器 = None
    if 执行器 is not None:
        执行器.shutdown(wait=False, cancel_futures=True)


async def 获取媒体代理会话() -> ClientSession:
    """复用媒体代理连接，避免每张图片重复建立 TCP/TLS 会话。"""
    global _媒体代理会话
    if _媒体代理会话 is None or _媒体代理会话.closed:
        _媒体代理会话 = ClientSession(
            connector=TCPConnector(
                limit=32,
                limit_per_host=8,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            ),
            trust_env=True,
        )
    return _媒体代理会话


async def 关闭媒体代理会话() -> None:
    global _媒体代理会话
    会话 = _媒体代理会话
    _媒体代理会话 = None
    if 会话 is not None and not 会话.closed:
        await 会话.close()


async def 停止实时连接() -> None:
    """在插件重载前主动关闭 SSE/WebSocket，避免 runner.cleanup 等待长连接超时。"""
    当前任务 = asyncio.current_task()
    待取消 = [
        任务
        for 任务 in list(实时连接任务)
        if 任务 is not 当前任务 and not 任务.done()
    ]
    for 任务 in 待取消:
        任务.cancel()
    if 待取消:
        await asyncio.gather(*待取消, return_exceptions=True)
        for 任务 in 待取消:
            实时连接任务.discard(任务)
    待取消后台 = [
        任务
        for 任务 in list(控制台后台任务)
        if 任务 is not 当前任务 and not 任务.done()
    ]
    for 任务 in 待取消后台:
        任务.cancel()
    if 待取消后台:
        await asyncio.gather(*待取消后台, return_exceptions=True)
        for 任务 in 待取消后台:
            控制台后台任务.discard(任务)


def 清理消息列表缓存() -> None:
    """清除网页会话列表缓存，写入/已读/置顶后立即读取最新状态。"""
    global 消息列表缓存版本
    消息列表缓存版本 += 1
    消息列表缓存.clear()
    _清理消息列表缓存锁()


def _清理消息列表缓存锁() -> None:
    """回收已失效请求的空闲锁，避免不同搜索条件长期累积。"""
    有效缓存键 = set(消息列表缓存)
    for 缓存键, 锁 in list(消息列表缓存锁.items()):
        if 缓存键 in 有效缓存键 or 缓存键 in 消息列表后台刷新:
            continue
        try:
            被占用 = bool(锁.locked())
        except Exception:
            被占用 = False
        if not 被占用:
            消息列表缓存锁.pop(缓存键, None)


def _写入消息列表缓存(
    缓存键: tuple[str, str, int, int, str | None], 结果: dict[str, Any], 缓存版本: int
) -> None:
    if 缓存版本 != 消息列表缓存版本:
        return
    if 缓存键 not in 消息列表缓存 and len(消息列表缓存) >= 消息列表缓存最大条目:
        最旧键 = min(消息列表缓存, key=lambda key: 消息列表缓存[key][0])
        消息列表缓存.pop(最旧键, None)
    消息列表缓存[缓存键] = (time.monotonic(), copy.deepcopy(结果))
    _清理消息列表缓存锁()


async def _构建消息列表(
    过滤: str, 搜索: str, 页码: int, 每页: int, appid: str | None = None
) -> dict[str, Any]:
    from 功能文件.管理功能.基础功能 import 消息记录

    结果 = await _控制台线程执行(
        消息记录.获取聊天列表, 过滤, 搜索, 页码, 每页, appid
    )
    return 结果


async def _后台刷新消息列表(
    缓存键: tuple[str, str, int, int, str | None], 过滤: str, 搜索: str, 页码: int, 每页: int,
    缓存版本: int, appid: str | None = None,
) -> None:
    try:
        结果 = await _构建消息列表(过滤, 搜索, 页码, 每页, appid)
        _写入消息列表缓存(缓存键, 结果, 缓存版本)
    except Exception as exc:
        logger.debug("帮助控制台消息列表后台刷新失败：错误类型=%s", type(exc).__name__)
    finally:
        消息列表后台刷新.discard(缓存键)

插件配置字段定义: dict[str, dict[str, Any]] = {
    "group_file_cleanup_admin_qq": {
        "category": "basic_settings",
        "label": "插件管理员白名单",
        "kind": "admin_list",
        "secret": False,
    },
    "qq_reader_api_enabled": {
        "category": "qq_reader_api_settings", "label": "开启 QQ 阅读开放接口",
        "kind": "boolean", "secret": False, "default": False,
        "hint": "服务共用，复用帮助网页端口；只需 API Key，无需 AppID。",
    },
    "qq_reader_api_keys": {
        "category": "qq_reader_api_settings", "label": "QQ 阅读 API Keys",
        "kind": "api_keys", "secret": True,
        "hint": "每行一个 Key。填写后保存将替换全部 Key；留空不修改。可随机生成并追加，或单独撤销。",
    },
    "welcome_tutorial_image_width": {
        "category": "help_web_settings",
        "label": "使用教程图片宽度（像素）",
        "kind": "number",
        "secret": False,
        "default": 480,
    },
    "help_web_domain": {
        "category": "help_web_settings",
        "label": "帮助网页外网地址",
        "kind": "text",
        "secret": False,
    },
    "help_web_host": {
        "category": "help_web_settings",
        "label": "帮助网页监听地址",
        "kind": "text",
        "secret": False,
    },
    "help_web_port": {
        "category": "help_web_settings",
        "label": "帮助网页监听端口",
        "kind": "number",
        "secret": False,
    },
    "help_web_admin_username": {
        "category": "help_web_settings",
        "label": "帮助网页登录账号",
        "kind": "text",
        "secret": False,
    },
    "help_web_admin_password": {
        "category": "help_web_settings",
        "label": "帮助网页登录密码",
        "kind": "secret",
        "secret": True,
    },
    "zlibrary_mail_api_key": {
        "category": "zlibrary_account_settings",
        "label": "ZLibrary 邮箱 API Key",
        "kind": "secret",
        "secret": True,
        "placeholder": "输入 AC- 开头的邮箱 API Key",
        "hint": "只写入、不回显；留空保持原值。保存后可发送“测试账号”，已有账号继续复用。",
    },
    "zlibrary_registration_rx": {
        "category": "zlibrary_account_settings",
        "label": "ZLibrary 注册表单 rx",
        "kind": "text", "secret": False, "default": "215",
        "hint": "默认 215，仅在远端注册表单变更时调整。",
    },
    "uc_pan_upload_dir": {
        "category": "uc_pan_settings",
        "label": "UC 上传目录",
        "kind": "text",
        "secret": False,
    },
    "quark_pan_upload_dir": {
        "category": "quark_pan_settings",
        "label": "夸克上传目录",
        "kind": "text",
        "secret": False,
    },
    "baidu_pan_upload_dir": {
        "category": "baidu_pan_settings",
        "label": "百度上传目录",
        "kind": "text",
        "secret": False,
    },
    "database_host": {
        "category": "database_settings",
        "label": "数据库地址",
        "kind": "text",
        "secret": False,
        "hint": "支持 IP、域名或带端口的 MySQL 地址。修改后重载插件生效。",
    },
    "database_port": {
        "category": "database_settings",
        "label": "数据库端口",
        "kind": "number",
        "secret": False,
        "default": "3306",
        "hint": "留空使用地址内端口，地址未带端口时使用 3306；有效范围 1 至 65535。",
    },
    "database_user": {
        "category": "database_settings",
        "label": "数据库用户名",
        "kind": "text",
        "secret": False,
        "hint": "MySQL 登录用户名。",
    },
    "database_name": {
        "category": "database_settings",
        "label": "数据库名",
        "kind": "text",
        "secret": False,
        "hint": "留空时使用数据库用户名作为数据库名。",
        "placeholder": "留空时与用户名相同",
    },
    "database_password": {
        "category": "database_settings",
        "label": "数据库密码",
        "kind": "secret",
        "secret": True,
        "hint": "密码仅写入、不回显；已配置时留空表示不修改。",
    },
    "database_ssl_mode": {
        "category": "database_settings", "label": "数据库加密连接", "kind": "select",
        "secret": False, "default": "preferred",
        "options": [
            {"value": "preferred", "label": "自动协商"},
            {"value": "required", "label": "必须加密"},
            {"value": "verify_identity", "label": "验证证书与主机名"},
            {"value": "disabled", "label": "关闭 TLS"},
        ],
        "hint": "公网数据库可选择必须加密；验证证书时地址须与证书匹配。",
    },
    "database_ssl_ca": {
        "category": "database_settings", "label": "数据库 CA 证书", "kind": "text",
        "secret": False, "default": "",
        "hint": "可选，填写 AstrBot 所在服务器可读取的 CA 证书文件；留空使用系统证书。",
    },
    "database_connect_timeout": {
        "category": "database_settings", "label": "数据库连接超时（秒）", "kind": "number",
        "secret": False, "default": "10", "hint": "有效范围 1 至 60 秒。",
    },
}

配置字段分类显示名 = {
    "qq_reader_api_settings": "QQ 阅读开放接口",
    "zlibrary_account_settings": "ZLibrary 账号注册",
    "basic_settings": "权限设置",
    "help_web_settings": "帮助网页",
    "uc_pan_settings": "UC 网盘",
    "quark_pan_settings": "夸克网盘",
    "baidu_pan_settings": "百度网盘",
    "database_settings": "数据库连接",
}


def _读取帮助网页字段(配置: Any, 字段名: str) -> Any:
    if 配置 is None:
        return None
    if isinstance(配置, dict):
        if 字段名 in 配置:
            return 配置.get(字段名)
        分类 = 配置.get("help_web_settings") or 配置.get("帮助网页设置")
        if isinstance(分类, dict) and 字段名 in 分类:
            return 分类.get(字段名)
        for 包装字段 in ("data", "obj"):
            数据 = 配置.get(包装字段)
            if isinstance(数据, dict) and 数据 is not 配置:
                值 = _读取帮助网页字段(数据, 字段名)
                if 值 is not None:
                    return 值
        return None
    for 属性名 in ("data", "obj"):
        数据 = getattr(配置, 属性名, None)
        if isinstance(数据, dict) and 数据 is not 配置:
            值 = _读取帮助网页字段(数据, 字段名)
            if 值 is not None:
                return 值
    获取配置方法 = getattr(配置, "get_config", None)
    if callable(获取配置方法):
        try:
            值 = _读取帮助网页字段(获取配置方法(), 字段名)
            if 值 is not None:
                return 值
        except Exception:
            pass
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            值 = 获取方法(字段名)
            if 值 is not None:
                return 值
            分类 = 获取方法("help_web_settings")
            if isinstance(分类, dict):
                return 分类.get(字段名)
        except Exception:
            pass
    值 = getattr(配置, 字段名, None)
    if 值 is not None:
        return 值
    分类 = getattr(配置, "help_web_settings", None)
    return getattr(分类, 字段名, None) if 分类 is not None else None


def _读取插件配置字典(配置: Any) -> dict[str, Any] | None:
    if isinstance(配置, dict):
        return 配置
    for 属性名 in ("data", "obj"):
        数据 = getattr(配置, 属性名, None)
        if isinstance(数据, dict):
            return 数据
    获取配置方法 = getattr(配置, "get_config", None)
    if callable(获取配置方法):
        try:
            数据 = 获取配置方法()
            if isinstance(数据, dict):
                return 数据
        except Exception:
            pass
    return None


def _复制插件配置值(值: Any) -> Any:
    """只复制插件配置支持的 JSON 值，避开 AstrBot 配置对象内部锁。"""
    if isinstance(值, dict):
        return {键: _复制插件配置值(项目) for 键, 项目 in 值.items()}
    if isinstance(值, list):
        return [_复制插件配置值(项目) for 项目 in 值]
    if isinstance(值, tuple):
        return tuple(_复制插件配置值(项目) for 项目 in 值)
    if isinstance(值, set):
        return {_复制插件配置值(项目) for 项目 in 值}
    if 值 is None or isinstance(值, (str, int, float, bool)):
        return 值
    try:
        return copy.deepcopy(值)
    except (TypeError, ValueError):
        return str(值)


def _读取插件配置值(配置: Any, 分类名: str, 字段名: str, 默认值: Any = None) -> Any:
    数据 = _读取插件配置字典(配置)
    if isinstance(数据, dict):
        分类 = 数据.get(分类名)
        if isinstance(分类, dict) and 字段名 in 分类:
            return 分类.get(字段名)
        if 字段名 in 数据:
            return 数据.get(字段名)
    值 = getattr(配置, 字段名, None)
    return 默认值 if 值 is None else 值


def _设置插件配置值(配置: Any, 分类名: str, 字段名: str, 值: Any) -> None:
    设置作用域字段 = getattr(配置, "设置配置字段", None)
    if callable(设置作用域字段):
        设置作用域字段(分类名, 字段名, 值)
        return
    数据 = _读取插件配置字典(配置)
    if not isinstance(数据, dict):
        raise RuntimeError("插件配置对象不可写入")
    分类 = 数据.get(分类名)
    if not isinstance(分类, dict):
        分类 = {}
        数据[分类名] = 分类
    分类[字段名] = 值


def _插件配置可持久化(配置: Any) -> bool:
    return callable(getattr(配置, "save_config_async", None)) or callable(
        getattr(配置, "save_config", None)
    )


async def _持久化插件配置() -> None:
    配置 = _当前作用域配置()
    异步保存方法 = getattr(配置, "save_config_async", None)
    if callable(异步保存方法):
        结果 = 异步保存方法()
        if inspect.isawaitable(结果):
            await 结果
        return
    保存方法 = getattr(配置, "save_config", None)
    if not callable(保存方法):
        raise RuntimeError("插件配置没有持久化接口")
    try:
        签名 = inspect.signature(保存方法)
        必填参数 = [
            参数
            for 参数名, 参数 in 签名.parameters.items()
            if 参数名 != "self"
            and 参数.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            and 参数.default is inspect.Parameter.empty
        ]
    except (TypeError, ValueError):
        必填参数 = []
    if 必填参数:
        配置字典 = _读取插件配置字典(配置)
        结果 = 保存方法(dict(配置字典 or {}))
    else:
        结果 = 保存方法()
    if inspect.isawaitable(结果):
        await 结果


def _读取插件配置摘要() -> dict[str, Any]:
    配置 = _当前作用域配置()
    try:
        from 功能文件.管理功能.基础功能 import 权限工具

        权限工具.同步管理员白名单(配置)
    except Exception as exc:
        logger.debug("帮助控制台管理员白名单同步失败：错误类型=%s", type(exc).__name__)
    字段列表: list[dict[str, Any]] = []
    for 字段名, 定义 in 插件配置字段定义.items():
        原值 = _读取插件配置值(
            配置,
            str(定义["category"]),
            字段名,
            定义.get("default", [] if 定义["kind"] == "admin_list" else ""),
        )
        项目: dict[str, Any] = {
            "key": 字段名,
            "category": 定义["category"],
            "category_name": 配置字段分类显示名.get(
                str(定义["category"]), str(定义["category"])
            ),
            "label": 定义["label"],
            "kind": 定义["kind"],
            "secret": bool(定义.get("secret")),
            "configured": bool(原值),
            "scope": "bot" if (定义["category"] in 机器人独立配置分类 or (定义["category"] == "help_web_settings" and 字段名 in 机器人独立帮助字段)) else "shared",
        }
        if 定义.get("hint"):
            项目["hint"] = str(定义["hint"])
        if 定义.get("placeholder"):
            项目["placeholder"] = str(定义["placeholder"])
        if 定义.get("options"):
            项目["options"] = list(定义["options"])
        if 定义["kind"] == "api_keys":
            from 功能文件.页面功能 import QQ阅读开放接口
            项目["keys"] = QQ阅读开放接口.读取接口密钥摘要(配置)
            项目["count"] = len(项目["keys"])
            项目["configured"] = bool(项目["keys"])
        elif 定义["kind"] == "admin_list":
            值列表 = 原值 if isinstance(原值, list) else str(原值 or "").split(",")
            值列表 = [str(值).strip() for 值 in 值列表 if str(值).strip()]
            项目["count"] = len(值列表)
            # 管理员标识不是密钥，网页需要能编辑它；其它敏感字段仍只返回摘要。
            项目["value"] = 值列表
        elif 定义["kind"] == "boolean":
            文本值 = str(原值 or "").strip().lower()
            项目["value"] = (
                原值
                if isinstance(原值, bool)
                else 文本值 in {"1", "true", "yes", "on", "enabled", "开启", "开"}
            )
        elif not 定义.get("secret"):
            项目["value"] = (
                list(原值) if isinstance(原值, list) else str(原值 or "")
            )
        else:
            # 敏感值只返回是否已配置。Cookie、密码、数据库凭据和密钥
            # 即使脱敏后也不应进入网页响应。
            项目["configured"] = bool(原值)
        字段列表.append(项目)
    return {
        "editable": _插件配置可持久化(配置) or isinstance(配置, dict),
        "restart_required": True,
        "fields": 字段列表,
        "appid": 获取当前机器人AppID(配置),
    }


def _校验插件配置字段(字段名: str, 值: Any) -> Any:
    定义 = 插件配置字段定义.get(字段名)
    if not 定义:
        raise ValueError("配置字段不支持")
    kind = 定义["kind"]
    if kind == "api_keys":
        from 功能文件.页面功能 import QQ阅读开放接口
        return QQ阅读开放接口.规范接口密钥列表(值)
    if kind == "select":
        文本 = str(值 or "").strip()
        允许值 = {str(项.get("value")) if isinstance(项, dict) else str(项) for 项 in 定义.get("options", [])}
        if 文本 not in 允许值:
            raise ValueError("配置选项无效")
        return 文本
    if kind == "boolean":
        if isinstance(值, bool):
            return 值
        文本 = str(值 or "").strip().lower()
        if 文本 in {"1", "true", "yes", "on", "enabled", "开启", "开"}:
            return True
        if 文本 in {"0", "false", "no", "off", "disabled", "关闭", "关"}:
            return False
        raise ValueError("布尔配置值无效")
    if 定义.get("secret"):
        文本 = str(值 or "").strip()
        if not 文本 and not 定义.get("allow_empty"):
            raise ValueError("敏感字段不能为空")
        if len(文本) > 20000:
            raise ValueError("配置值过长")
        if 字段名 == "zlibrary_mail_api_key" and not re.fullmatch(r"AC-[A-Za-z0-9_-]{1,256}", 文本):
            raise ValueError("邮箱 API Key 格式无效")
        return 文本
    if kind == "admin_list":
        原列表 = 值 if isinstance(值, list) else re.split(r"[,，\n\r\s]+", str(值 or ""))
        结果 = []
        for 项 in 原列表:
            文本 = str(项 or "").strip()
            if 文本 and 文本 not in 结果:
                if len(文本) > 128:
                    raise ValueError("管理员标识过长")
                结果.append(文本)
        if len(结果) > 200:
            raise ValueError("管理员白名单过多")
        return 结果
    文本 = str(值 or "").strip()
    if len(文本) > 500:
        raise ValueError("配置值过长")
    if 字段名 == "welcome_tutorial_image_width":
        if not 文本.isdigit() or not 160 <= int(文本) <= 1080:
            raise ValueError("教程图片宽度应为 160 至 1080 像素")
        return int(文本)
    if 字段名 == "database_port":
        if not 文本:
            return ""
        if not 文本.isdigit() or not 1 <= int(文本) <= 65535:
            raise ValueError("数据库端口无效")
        return 文本
    if 字段名 == "database_connect_timeout":
        if not 文本.isdigit() or not 1 <= int(文本) <= 60:
            raise ValueError("数据库连接超时应为 1 至 60 秒")
        return int(文本)
    if 字段名 == "database_ssl_ca" and any(ord(字符) < 32 for 字符 in 文本):
        raise ValueError("数据库证书路径无效")
    if 字段名 == "database_name":
        if len(文本) > 64 or any(ord(字符) < 32 or ord(字符) == 127 or 字符 in "`\\" for 字符 in 文本):
            raise ValueError("数据库名无效")
        return 文本
    if 字段名 == "help_web_port":
        if not 文本.isdigit() or not 1 <= int(文本) <= 65535:
            raise ValueError("帮助网页端口无效")
        return 文本
    if 字段名 == "help_web_domain":
        if not 文本:
            return ""
        地址 = _规范化公开地址(文本)
        if not 地址:
            raise ValueError("帮助网页地址无效")
        return 地址
    if 字段名.endswith("_upload_dir") and 文本 and not 文本.startswith("/"):
        raise ValueError("上传目录必须以 / 开头")
    return 文本


def _规范化公开地址(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"http://{raw}"
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    try:
        if not parsed.hostname:
            return ""
        parsed.port
    except ValueError:
        return ""
    hostname = str(parsed.hostname).strip().lower().rstrip(".")
    if hostname != "localhost" and "." not in hostname:
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            return ""
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))


def _获取服务器IPv4() -> str:
    """先获取公网 IPv4，再回退到默认出站网卡地址。"""
    try:
        from urllib.request import Request, urlopen

        for 地址服务 in (
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://ip.sb",
            "https://icanhazip.com",
        ):
            try:
                请求 = Request(地址服务, headers={"User-Agent": "mantou-console/1.0"})
                with urlopen(请求, timeout=2) as 响应:
                    文本 = 响应.read(64).decode("ascii", "ignore").strip()
                解析地址 = ipaddress.ip_address(文本)
                if (
                    解析地址.version == 4
                    and not 解析地址.is_loopback
                    and not 解析地址.is_unspecified
                    and not 解析地址.is_link_local
                ):
                    return 文本
            except (OSError, ValueError):
                continue
    except Exception:
        pass

    候选地址: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            候选地址.append(str(sock.getsockname()[0]))
    except OSError:
        pass

    for 主机名 in (socket.gethostname(), socket.getfqdn()):
        try:
            for 地址 in socket.gethostbyname_ex(主机名)[2]:
                候选地址.append(str(地址))
        except OSError:
            continue

    for 地址 in 候选地址:
        try:
            解析地址 = ipaddress.ip_address(地址)
        except ValueError:
            continue
        if 解析地址.version == 4 and not (
            解析地址.is_loopback
            or 解析地址.is_unspecified
            or 解析地址.is_link_local
        ):
            return 地址
    return "127.0.0.1"


def _读取监听配置(配置: Any) -> tuple[str, int]:
    host = str(_读取帮助网页字段(配置, "help_web_host") or 默认监听地址).strip()
    if not host:
        host = 默认监听地址
    try:
        port = int(_读取帮助网页字段(配置, "help_web_port") or 默认监听端口)
    except (TypeError, ValueError):
        port = 默认监听端口
    return host, max(1, min(65535, port))


def _获取自动公开地址(配置: Any = None) -> str:
    global 自动公开地址缓存
    主机, 端口 = _读取监听配置(配置)
    主机文本 = 主机.strip().lower().rstrip(".")
    if 主机文本 in {"localhost", "127.0.0.1"}:
        公开主机 = "127.0.0.1"
    elif 主机文本 not in {"", "0.0.0.0", "::"}:
        try:
            公开主机 = str(ipaddress.ip_address(主机文本))
        except ValueError:
            公开主机 = _获取服务器IPv4()
    else:
        if not 自动公开地址缓存:
            自动公开地址缓存 = _获取服务器IPv4()
        公开主机 = 自动公开地址缓存
    return _规范化公开地址(f"http://{公开主机}:{端口}")


def _计算帮助网页启动地址(配置: Any = None) -> str:
    """先使用已知地址启动监听，公网查询随后在后台完成。"""
    手动地址 = _规范化公开地址(_读取帮助网页字段(配置, "help_web_domain"))
    if 手动地址:
        return 手动地址
    主机, 端口 = _读取监听配置(配置)
    公开主机 = 主机
    if 主机 in {"", "0.0.0.0", "::"}:
        公开主机 = 自动公开地址缓存 or "127.0.0.1"
        if not 自动公开地址缓存:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect(("8.8.8.8", 80))
                    公开主机 = str(sock.getsockname()[0])
            except OSError:
                pass
    return _规范化公开地址(f"http://{公开主机}:{端口}")


def _计算帮助网页地址(配置: Any = None) -> str:
    手动地址 = _规范化公开地址(_读取帮助网页字段(配置, "help_web_domain"))
    return 手动地址 or _获取自动公开地址(配置)


def _读取控制台账号(配置: Any = None) -> tuple[str, str]:
    用户名 = str(
        _读取帮助网页字段(配置, "help_web_admin_username") or 默认控制台用户名
    ).strip()
    密码 = str(
        _读取帮助网页字段(配置, "help_web_admin_password") or 默认控制台密码
    )
    return 用户名, 密码


def _构造控制台访问地址(基础地址: str, 配置: Any = None) -> str:
    del 配置
    return 基础地址 or ""


def 获取帮助网页地址(配置: Any = None) -> str:
    """返回不携带登录凭据的控制台地址；登录在网页内完成。"""
    if 当前帮助网页服务 is not None:
        return 当前帮助网页服务.public_url
    if 网页服务启动状态 is False:
        return ""
    return _构造控制台访问地址(_计算帮助网页地址(配置), 配置)


async def _处理教程图片(request: web.Request) -> web.StreamResponse:
    """仅公开随插件发布的四张教程配图，不读取聊天媒体或缓存。"""
    from 功能文件.管理功能.群聊功能.群成员事件 import 教程图片规格

    文件名 = request.match_info.get("filename", "")
    if 文件名 not in {规格[0] for 规格 in 教程图片规格}:
        raise web.HTTPNotFound()
    目录 = Path(__file__).with_name("教程图片").resolve()
    路径 = (目录 / 文件名).resolve()
    if 路径.parent != 目录 or not 路径.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(路径, headers={
        "Cache-Control": "public, max-age=86400",
        "X-Content-Type-Options": "nosniff",
    })


def _数据库会话可用(配置: Any = None) -> bool:
    """_当前作用域配置()已配置运行状态数据库时才能持久化会话。"""
    数据库配置 = 配置 if 配置 is not None else _当前作用域配置()
    if 数据库配置 is None:
        return False
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 已配置运行状态数据库
        return bool(已配置运行状态数据库(数据库配置))
    except Exception:
        return False


def 获取控制台会话配置快照(配置: Any = None) -> dict[str, Any]:
    """在线程派发前固定认证及连接输入，不引用后续会变更的配置对象。"""
    from 功能文件.管理功能.基础功能.运行状态数据库 import 读取数据库配置值, 获取数据库配置

    来源 = 配置 if 配置 is not None else _当前作用域配置()
    用户名, 密码 = _读取控制台账号(来源)
    数据库配置 = {
        字段: 读取数据库配置值(来源, 字段, 旧字段)
        for 字段, 旧字段 in (
            ("database_host", "user_activation_database_host"),
            ("database_port", "user_activation_database_port"),
            ("database_user", "user_activation_database_user"),
            ("database_password", "user_activation_database_password"),
            ("database_name", "user_activation_database_name"),
            ("database_ssl_mode", ""),
            ("database_ssl_ca", ""),
            ("database_connect_timeout", ""),
        )
    }
    for 字段 in ("database_host", "database_user", "database_name"):
        数据库配置[字段] = str(数据库配置[字段] or "").strip()
    数据库配置["database_name"] = 数据库配置["database_name"] or 数据库配置["database_user"]
    数据库配置["database_password"] = str(数据库配置["database_password"] or "")
    数据库配置["database_ssl_mode"] = 数据库配置["database_ssl_mode"] or "preferred"
    数据库配置["database_ssl_ca"] = 数据库配置["database_ssl_ca"] or ""
    数据库配置["database_connect_timeout"] = 数据库配置["database_connect_timeout"] if 数据库配置["database_connect_timeout"] is not None else 10
    try:
        规范配置 = 获取数据库配置({"database_settings": 数据库配置})
        for 字段, 键 in (("database_host", "host"), ("database_port", "port"),
                         ("database_ssl_mode", "ssl_mode"), ("database_ssl_ca", "ssl_ca"),
                         ("database_connect_timeout", "connect_timeout")):
            数据库配置[字段] = 规范配置[键]
    except (ValueError, RuntimeError):
        # 配置尚未填写完整时仍须能登录并编辑；保留原值参与认证指纹。
        pass
    return {
        "help_web_settings": {"help_web_admin_username": 用户名, "help_web_admin_password": 密码},
        "database_settings": 数据库配置,
        "__mantou_bot_appid__": 获取当前机器人AppID(来源),
    }


def 获取控制台认证指纹(配置: Any) -> str:
    快照 = 获取控制台会话配置快照(配置)
    快照.pop("__mantou_bot_appid__", None)
    文本 = json.dumps(快照, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(文本.encode("utf-8")).hexdigest()


def 同步控制台会话认证(配置: Any) -> bool:
    """仅相同凭据及数据库的热重载保留登录；签名从不返回网页或日志。"""
    global 控制台会话认证指纹
    新指纹 = 获取控制台认证指纹(配置)
    一致 = bool(控制台会话认证指纹) and hmac.compare_digest(控制台会话认证指纹, 新指纹)
    if not 一致:
        QQ阅读扫码启动代次.clear()
        晋江扫码启动代次.clear()
        QQ阅读短信启动代次.clear()
        try:
            asyncio.get_running_loop().create_task(_取消全部QQ阅读网页扫码())
            asyncio.get_running_loop().create_task(_取消全部晋江网页扫码())
            asyncio.get_running_loop().create_task(_取消全部QQ阅读网页短信())
        except RuntimeError:
            pass
        控制台会话.clear()
        控制台会话身份.clear()
        控制台会话最后持久化.clear()
        控制台会话恢复排除.clear()
    控制台会话认证指纹 = 新指纹
    return 一致


def _解析持久会话文本(文本: str) -> tuple[float | None, str, str]:
    """只恢复新格式签名会话，旧记录不在冷启动时自动沿用。"""
    try:
        值 = json.loads(文本)
        if not isinstance(值, dict) or 值.get("version") != 2:
            return None, "管理员", ""
        return float(值["expires_at"]), str(值["username"]), str(值["auth"])
    except (TypeError, ValueError, KeyError):
        return None, "管理员", ""


def _写入持久化控制台会话(会话值: str, 到期时间: float, 用户名: str, 配置: Any) -> None:
    if not 会话值 or not _数据库会话可用(配置):
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值
        指纹 = 获取控制台认证指纹(配置)
        with _控制台会话存储锁:
            if 会话值 in 控制台会话恢复排除 or not hmac.compare_digest(指纹, 控制台会话认证指纹):
                return
            写入运行状态值(
                配置, 控制台会话命名空间, 会话值,
                json.dumps({"version": 2, "expires_at": 到期时间, "username": 用户名, "auth": 指纹},
                           ensure_ascii=False, separators=(",", ":")),
            )
    except Exception as exc:
        logger.debug("帮助控制台写入持久会话失败：错误类型=%s", type(exc).__name__)


def _删除持久化控制台会话(会话值: str, 配置: Any) -> None:
    if not 会话值 or not _数据库会话可用(配置):
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 删除运行状态值
        with _控制台会话存储锁:
            删除运行状态值(配置, 控制台会话命名空间, 会话值)
    except Exception as exc:
        logger.debug("帮助控制台删除持久会话失败：错误类型=%s", type(exc).__name__)


def _读取持久化控制台会话(配置: Any) -> dict[str, tuple[float, str]]:
    """线程中只读取快照，合并和退出排除在事件循环中执行。"""
    数据库配置 = 配置
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态命名空间, 已配置运行状态数据库
        if not 已配置运行状态数据库(数据库配置):
            return {}
        记录 = 读取运行状态命名空间(数据库配置, 控制台会话命名空间)
        预期指纹 = 获取控制台认证指纹(数据库配置)
        现在 = time.time()
        结果 = {}
        for 会话值, 文本 in 记录.items():
            到期时间, 用户名, 指纹 = _解析持久会话文本(文本)
            if 到期时间 is not None and 到期时间 > 现在 and hmac.compare_digest(指纹, 预期指纹):
                结果[会话值] = (到期时间, 用户名)
        return 结果
    except Exception as exc:
        logger.debug("帮助控制台加载持久会话失败：错误类型=%s", type(exc).__name__)
        return {}


def _清理控制台会话() -> None:
    截止时间 = time.time()
    for scan_id, 扫码状态 in list(夸克网页扫码会话.items()):
        if (
            扫码状态.get("status") in {"success", "expired", "cancelled", "error"}
            and 截止时间 - float(扫码状态.get("updated_at") or 0) > 300
        ):
            夸克网页扫码会话.pop(scan_id, None)
    for scan_id, 状态 in list(QQ阅读网页扫码会话.items()):
        if 状态.get("status") in {"success", "expired", "cancelled", "error"} and 截止时间 - float(状态.get("updated_at") or 0) > 300:
            QQ阅读网页扫码会话.pop(scan_id, None)
    for 所有者, 状态 in list(QQ阅读网页短信会话.items()):
        if 状态.get("expires_at", 0) <= 截止时间:
            try:
                asyncio.get_running_loop().create_task(_移除QQ阅读网页短信会话(所有者, 状态))
            except RuntimeError:
                pass
    for scan_id, 状态 in list(晋江网页扫码会话.items()):
        if 状态.get("status") in {"success", "expired", "cancelled", "error"} and 截止时间 - float(状态.get("updated_at") or 0) > 300:
            晋江网页扫码会话.pop(scan_id, None)
    for 会话值, 到期时间 in list(控制台会话.items()):
        if 到期时间 <= 截止时间:
            控制台会话恢复排除.add(会话值)
            控制台会话.pop(会话值, None)
            控制台会话身份.pop(会话值, None)
            控制台会话最后持久化.pop(会话值, None)
            _安排控制台后台任务(_删除持久化控制台会话, 会话值, 获取控制台会话配置快照())
            try:
                asyncio.get_running_loop().create_task(
                    _取消夸克网页扫码所有者(会话值)
                )
                asyncio.get_running_loop().create_task(_取消QQ阅读网页扫码所有者(会话值))
                asyncio.get_running_loop().create_task(_取消晋江网页扫码所有者(会话值))
                asyncio.get_running_loop().create_task(_取消QQ阅读网页短信所有者(会话值))
            except RuntimeError:
                pass


def _安排控制台后台任务(函数: Any, *参数: Any) -> None:
    """把会话清理/续期写入移出请求事件循环，不让数据库连接阻塞网页响应。"""
    try:
        任务 = asyncio.create_task(_控制台线程执行(函数, *参数))
    except RuntimeError:
        return
    控制台后台任务.add(任务)
    任务.add_done_callback(控制台后台任务.discard)


def _取得请求会话(request: web.Request) -> str:
    _清理控制台会话()
    return str(request.cookies.get(控制台会话Cookie名) or "").strip()


def _请求已授权(request: web.Request) -> bool:
    if not 控制台会话认证指纹 or not hmac.compare_digest(
        控制台会话认证指纹, 获取控制台认证指纹(_当前作用域配置())
    ):
        同步控制台会话认证(_当前作用域配置())
        return False
    会话值 = _取得请求会话(request)
    if not 会话值:
        return False
    到期时间 = 控制台会话.get(会话值)
    # 持久会话在服务启动阶段一次性恢复；请求路径不再同步访问 MySQL。
    # 这样消息列表和媒体请求不会被数据库连接/查询拖住事件循环。
    if 到期时间 is None or 到期时间 <= time.time():
        控制台会话.pop(会话值, None)
        控制台会话身份.pop(会话值, None)
        控制台会话最后持久化.pop(会话值, None)
        return False
    新到期时间 = time.time() + 控制台会话有效期
    控制台会话[会话值] = 新到期时间
    # 滑动续期仍保留，但最多每小时后台写一次，避免每个 API 请求都触发数据库写入。
    现在 = time.time()
    if 现在 - 控制台会话最后持久化.get(会话值, 0.0) >= 3600:
        控制台会话最后持久化[会话值] = 现在
        _安排控制台后台任务(
            _写入持久化控制台会话,
            会话值,
            新到期时间,
            控制台会话身份.get(会话值, "管理员"),
            获取控制台会话配置快照(),
        )
    return True


def _请求来自同源(request: web.Request) -> bool:
    """WebSocket 只接受当前控制台页面发起的同源连接。"""
    来源 = str(request.headers.get("Origin") or "").strip()
    主机头 = str(request.headers.get("Host") or "").strip()
    if not 来源 or not 主机头:
        return False
    try:
        来源地址 = urlsplit(来源)
        请求地址 = urlsplit(f"//{主机头}")
        代理协议 = str(request.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip().lower()
        请求协议 = 代理协议 or str(request.scheme or "http").lower()
        if 来源地址.scheme.lower() not in {"http", "https"} or 来源地址.scheme.lower() != 请求协议:
            return False
        if str(来源地址.hostname or "").rstrip(".").lower() != str(请求地址.hostname or "").rstrip(".").lower():
            return False
        来源端口 = 来源地址.port or (443 if 来源地址.scheme.lower() == "https" else 80)
        请求端口 = 请求地址.port or (443 if 请求协议 == "https" else 80)
        return 来源端口 == 请求端口
    except (TypeError, ValueError):
        return False


def _读取当前控制台身份(request: web.Request) -> str:
    """返回当前会话的登录账号；身份摘要可以展示，密码和会话值不出接口。"""
    return 控制台会话身份.get(_取得请求会话(request), "管理员") or "管理员"


def _控制台错误(状态码: int, 文本: str) -> web.Response:
    return web.json_response({"ok": False, "error": 文本}, status=状态码)


async def _处理数据库连接测试(request: web.Request) -> web.Response:
    """测试当前表单，不保存配置，也不创建数据库或表。"""
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _请求来自同源(request):
        return _控制台错误(403, "请求来源无效")
    数据 = await _读取请求JSON(request)
    字段 = (数据 or {}).get("fields")
    if not isinstance(字段, dict) or not 字段 or any(
        名 not in 插件配置字段定义 or 插件配置字段定义[名]["category"] != "database_settings"
        for 名 in 字段
    ):
        return _控制台错误(400, "数据库测试参数无效")
    快照 = 获取控制台会话配置快照()
    try:
        for 名, 值 in 字段.items():
            if 名 == "database_password" and (值 is None or 值 == ""):
                continue
            快照["database_settings"][名] = _校验插件配置字段(名, 值)
    except (ValueError, TypeError):
        return _控制台错误(400, "数据库测试参数无效")
    认证 = 控制台会话认证指纹
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 测试运行状态数据库连接
        结果 = await _控制台线程执行(测试运行状态数据库连接, 快照)
        if not _请求已授权(request) or 认证 != 控制台会话认证指纹:
            return _控制台错误(401, "登录状态已更新，请重新登录")
        return web.json_response({
            "ok": True, "connected": bool(结果["ok"]),
            **{名: 结果[名] for 名 in ("status", "reason", "message", "mysql_code", "version", "tls")},
        }, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台数据库测试失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(502, "数据库测试暂时未完成，请稍后重试")


def _清理聊天确认令牌() -> None:
    现在 = time.monotonic()
    for 令牌, 项 in list(_聊天清理确认会话.items()):
        if 项["expires"] <= 现在 or 项["auth"] != 控制台会话认证指纹:
            _聊天清理确认会话.pop(令牌, None)
    while len(_聊天清理确认会话) >= 128:
        _聊天清理确认会话.pop(next(iter(_聊天清理确认会话)))


async def _读取聊天清理请求(request: web.Request) -> tuple[dict[str, Any] | None, web.Response | None]:
    if not _请求已授权(request):
        return None, _控制台错误(401, "请先登录控制台")
    if not _请求来自同源(request):
        return None, _控制台错误(403, "请求来源无效")
    数据 = await _读取请求JSON(request)
    appid = 获取当前机器人AppID()
    if not isinstance(数据, dict) or not appid or 数据.get("appid") != appid:
        return None, _控制台错误(400, "机器人参数无效")
    return 数据, None


async def _处理聊天清理预览(request: web.Request) -> web.Response:
    数据, 错误 = await _读取聊天清理请求(request)
    if 错误 is not None:
        return 错误
    范围 = 数据.get("scope")
    if not isinstance(范围, str) or 范围 not in {"chat", "bot"} or (范围 == "chat" and (
        not isinstance(数据.get("chat_type"), str) or 数据.get("chat_type") not in {"group", "user"}
        or not isinstance(数据.get("chat_id"), str)
        or not 0 < len(数据["chat_id"].strip()) <= 128
        or any(ord(字) < 32 or ord(字) == 127 for 字 in 数据["chat_id"])
    )):
        return _控制台错误(400, "请选择要清理的聊天记录")
    appid, 认证 = 获取当前机器人AppID(), 控制台会话认证指纹
    所有者 = hashlib.sha256(_取得请求会话(request).encode()).hexdigest()
    try:
        from 功能文件.管理功能.基础功能 import 消息记录
        结果 = await 消息记录.准备清理聊天记录(
            appid, 数据.get("chat_type", "") if 范围 == "chat" else "",
            数据.get("chat_id", "").strip() if 范围 == "chat" else "", 范围,
        )
        if not _请求已授权(request) or 认证 != 控制台会话认证指纹:
            return _控制台错误(401, "登录状态已更新，请重新登录")
        if not 结果.get("ok"):
            return _控制台错误(409, "读取聊天记录失败，请稍后重试")
        _清理聊天确认令牌()
        for 键, 项 in list(_聊天清理确认会话.items()):
            if 项["owner"] == 所有者 and 项["appid"] == appid:
                _聊天清理确认会话.pop(键, None)
        令牌 = secrets.token_urlsafe(32)
        _聊天清理确认会话[令牌] = {"owner": 所有者, "appid": appid, "auth": 认证,
            "expires": time.monotonic() + 120, "preview": 结果}
        return web.json_response({"ok": True, "clear_token": 令牌, "expires_at": time.time() + 120,
            "matched_count": int(结果["count"]),
            **{名: 结果[名] for 名 in ("appid", "scope", "chat_id", "chat_type")},
            "boundary": {名: 结果["boundary"][名] for 名 in ("cutoff_id", "origin", "cutoff_order")},
        }, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台聊天清理预览失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "读取聊天记录失败，请稍后重试")


async def _完成聊天记录清理(预览: dict[str, Any]) -> dict[str, Any]:
    from 功能文件.管理功能.基础功能 import 消息记录
    结果 = await 消息记录.执行清理聊天记录(预览)
    if 结果.get("ok"):
        清理消息列表缓存()
    return 结果


def _聊天清理执行结束(任务: asyncio.Task[Any]) -> None:
    _聊天清理执行任务.discard(任务)
    if not 任务.cancelled() and 任务.exception() is not None:
        logger.warning("帮助控制台聊天清理后台失败：错误类型=%s", type(任务.exception()).__name__)


async def _处理聊天记录清理(request: web.Request) -> web.Response:
    数据, 错误 = await _读取聊天清理请求(request)
    if 错误 is not None:
        return 错误
    _清理聊天确认令牌()
    令牌 = 数据.get("clear_token")
    if not isinstance(令牌, str) or len(令牌) > 128:
        return _控制台错误(400, "清理确认已失效，请重新操作")
    项 = _聊天清理确认会话.get(令牌)
    所有者 = hashlib.sha256(_取得请求会话(request).encode()).hexdigest()
    if not 项 or 项["owner"] != 所有者 or 项["appid"] != 获取当前机器人AppID():
        return _控制台错误(409, "清理确认已失效，请重新操作")
    # 先消费再提交，断线或重复请求不得重放删除；业务任务完成事务及内存同步后退出。
    _聊天清理确认会话.pop(令牌, None)
    任务 = asyncio.create_task(_完成聊天记录清理(项["preview"]))
    _聊天清理执行任务.add(任务)
    任务.add_done_callback(_聊天清理执行结束)
    try:
        结果 = await asyncio.shield(任务)
        if not 结果.get("ok"):
            return _控制台错误(409, "清理未完成，请刷新后重试")
        return web.json_response({名: 结果[名] for 名 in (
            "ok", "appid", "scope", "chat_type", "chat_id", "deleted_count", "database_deleted_count",
            "memory_deleted_count", "remaining_count", "cutoff_id", "origin", "cutoff_order",
        )}, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台聊天清理失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "清理未完成，请刷新后重试")


async def _读取请求JSON(request: web.Request) -> dict[str, Any] | None:
    try:
        数据 = await request.json()
    except Exception:
        return None
    if not isinstance(数据, dict):
        return None
    appid = str(request.get("机器人AppID") or "")
    if appid:
        if "appid" in 数据 and str(数据["appid"] or "").strip() != appid:
            raise web.HTTPBadRequest(text="机器人参数不一致")
        数据 = {**数据, "appid": appid}
    return 数据


async def _读取消息发送请求(request: web.Request) -> tuple[dict[str, Any] | None, Path | None]:
    """读取 JSON 或 multipart 消息请求；大文件落临时文件，避免 Base64 内存膨胀。"""
    if not str(request.content_type or '').lower().startswith('multipart/'):
        return await _读取请求JSON(request), None
    数据: dict[str, Any] = {}
    临时路径: Path | None = None
    try:
        读取器 = await request.multipart()
        async for 部分 in 读取器:
            名称 = str(部分.name or '').strip()
            if not 名称:
                continue
            文件名 = str(部分.filename or '').strip()
            if 文件名:
                if 临时路径 is not None:
                    while await 部分.read_chunk(size=1024 * 1024):
                        pass
                    continue
                后缀 = re.sub(r'[^A-Za-z0-9.]', '', Path(文件名).suffix.lower())[:12]
                from 功能文件.管理功能.基础功能 import 文件缓存

                临时路径 = 文件缓存.创建临时缓存文件("mantou-web-", 后缀)
                已读 = 0
                try:
                    with 临时路径.open('wb') as 文件句柄:
                        while True:
                            数据块 = await 部分.read_chunk(size=1024 * 1024)
                            if not 数据块:
                                break
                            已读 += len(数据块)
                            if 已读 > (10 * 1024 * 1024 if 名称 == 'image_file' else 媒体代理最大字节数):
                                raise ValueError('媒体文件过大')
                            文件句柄.write(数据块)
                except (Exception, asyncio.CancelledError):
                    临时路径.unlink(missing_ok=True)
                    临时路径 = None
                    raise
                if 名称 == 'image_file':
                    数据['image'] = str(临时路径)
                    数据['image_name'] = 文件名[:160]
                else:
                    数据['media'] = str(临时路径)
                    数据['media_name'] = 文件名[:160]
                continue
            数据[名称] = await 部分.text()
        for 名称 in ('card', 'ark_fields'):
            值 = 数据.get(名称)
            if isinstance(值, str) and 值.strip().startswith(('{', '[')):
                try:
                    数据[名称] = json.loads(值)
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
        appid = str(request.get("机器人AppID") or "")
        if appid and "appid" in 数据 and str(数据["appid"] or "").strip() != appid:
            raise web.HTTPBadRequest(text="机器人参数不一致")
        if appid:
            数据["appid"] = appid
        return 数据, 临时路径
    except (Exception, asyncio.CancelledError):
        if 临时路径 is not None:
            临时路径.unlink(missing_ok=True)
        raise


def _允许媒体地址(地址: Any) -> bool:
    """只允许 QQ 媒体域名进入代理，避免把控制台变成开放 URL 转发器。"""
    try:
        解析 = urlsplit(str(地址 or "").strip())
        主机 = str(解析.hostname or "").rstrip(".").lower()
        if 解析.scheme.lower() not in {"http", "https"} or not 主机:
            return False
        if 解析.username or 解析.password:
            return False
        try:
            IP地址 = ipaddress.ip_address(主机)
            if not IP地址.is_global:
                return False
        except ValueError:
            pass
        return any(
            主机 == 后缀 or 主机.endswith("." + 后缀)
            for 后缀 in 媒体代理主机后缀
        )
    except (TypeError, ValueError):
        return False


def _媒体文件名(值: Any) -> str:
    """过滤响应头中的文件名，避免控制字符或路径穿透。"""
    文本 = unquote(str(值 or "").strip())
    文本 = re.sub(r"[\x00-\x1f\x7f\\/:*?\"<>|]+", "_", 文本).strip(" .")
    return 文本[:160] or "附件文件"


def _识别媒体类型(响应类型: Any, 前缀: bytes, 地址: str, 模式: str) -> str:
    """QQ 下载接口偶尔返回 octet-stream，按文件头补出浏览器需要的图片 MIME。"""
    类型 = str(响应类型 or "").split(";", 1)[0].strip().lower()
    if 类型 and 类型 != "application/octet-stream":
        return 类型
    if 前缀.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if 前缀.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if 前缀.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(前缀) >= 12 and 前缀[:4] == b"RIFF" and 前缀[8:12] == b"WEBP":
        return "image/webp"
    if 前缀.lstrip().startswith(b"<svg") or b"<svg" in 前缀[:512].lower():
        return "image/svg+xml"
    if 模式 == "image":
        类型 = mimetypes.guess_type(urlsplit(地址).path)[0] or ""
        if 类型.startswith("image/"):
            return 类型
    return 类型 or "application/octet-stream"


def _媒体代理缓存键(地址: str) -> str:
    """只在内存中保存地址摘要，避免失败缓存长期保留带签名 URL。"""
    return hashlib.sha256(str(地址 or "").encode("utf-8", errors="ignore")).hexdigest()


def _媒体代理失败缓存命中(缓存键: str) -> bool:
    if not 缓存键:
        return False
    当前时间 = time.monotonic()
    with 媒体代理失败缓存锁:
        for 键, 截止时间 in list(媒体代理失败缓存.items()):
            if float(截止时间 or 0) <= 当前时间:
                媒体代理失败缓存.pop(键, None)
        return float(媒体代理失败缓存.get(缓存键) or 0) > 当前时间


def _记录媒体代理失败(缓存键: str) -> None:
    if not 缓存键:
        return
    当前时间 = time.monotonic()
    with 媒体代理失败缓存锁:
        媒体代理失败缓存[缓存键] = 当前时间 + 媒体代理失败缓存有效期秒
        if len(媒体代理失败缓存) > 媒体代理失败缓存上限:
            最旧键 = min(
                媒体代理失败缓存,
                key=lambda 键: float(媒体代理失败缓存.get(键) or 0),
            )
            媒体代理失败缓存.pop(最旧键, None)


def _清除媒体代理失败(缓存键: str) -> None:
    if not 缓存键:
        return
    with 媒体代理失败缓存锁:
        媒体代理失败缓存.pop(缓存键, None)


async def _媒体上游地址已过期(上游: Any) -> bool:
    """仅识别 QQ 明确返回的附件签名过期，不能把临时 4xx 锁成过期。"""
    try:
        if int(getattr(上游, "status", 0) or 0) != 400:
            return False
        内容 = await 上游.content.read(16 * 1024)
        负载 = json.loads(内容.decode("utf-8", errors="ignore"))
        if not isinstance(负载, dict):
            return False
        错误码 = 负载.get("retcode", 负载.get("code"))
        return str(错误码 or "").strip() == "-5503007"
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return False


def _媒体代理失败响应(模式: str, *, 已过期: bool = False) -> web.Response:
    """保留真实失败状态，使网页可对临时代理失败执行一次直连回退。"""
    return web.Response(
        status=404 if 已过期 else 502,
        text="媒体已过期" if 已过期 else "媒体暂时不可用",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Mantou-Media-Error": "expired" if 已过期 else "temporary",
        },
    )


def _媒体代理请求超时(模式: str) -> ClientTimeout:
    return ClientTimeout(
        total=None if 模式 == "file" else 媒体代理超时秒,
        # connect 包含连接池等待；实际新建连接仍单独限制为十秒。
        connect=媒体代理超时秒,
        sock_connect=媒体代理连接超时秒,
        sock_read=媒体代理读取超时秒,
    )


async def _处理消息媒体(request: web.Request) -> web.StreamResponse:
    """在同源会话中转发 QQ 附件，解决签名 URL 的跨域和响应类型问题。"""
    if not _请求已授权(request):
        return web.Response(status=401, text="请先登录控制台")
    地址 = str(request.query.get("src") or "").strip()
    if len(地址) > 8192 or not _允许媒体地址(地址):
        return web.Response(status=400, text="媒体地址无效")
    模式 = str(request.query.get("mode") or "image").strip().lower()
    if 模式 not in {"image", "file"}:
        模式 = "file"
    缓存键 = _媒体代理缓存键(地址)
    if _媒体代理失败缓存命中(缓存键):
        return _媒体代理失败响应(模式, 已过期=True)
    文件名 = _媒体文件名(request.query.get("name"))
    阶段 = "session"
    已发送 = 0
    上游状态: int | None = None
    响应: web.StreamResponse | None = None
    try:
        超时 = _媒体代理请求超时(模式)
        客户端 = await 获取媒体代理会话()
        阶段 = "upstream_request"
        async with 客户端.get(
            地址,
            allow_redirects=True,
            max_redirects=3,
            timeout=超时,
            headers={
                "Accept": "image/*,application/octet-stream,*/*",
                "User-Agent": "MantouBot/console-media",
            },
        ) as 上游:
                上游状态 = int(getattr(上游, "status", 0) or 0)
                最终地址 = str(getattr(上游, "url", 地址) or 地址)
                if not _允许媒体地址(最终地址):
                    return web.Response(status=502, text="媒体地址不可用")
                if 上游.status not in {200, 206}:
                    # QQ 附件仅在明确返回 -5503007 时才不可恢复；429、403 和
                    # CDN 短暂 4xx 都让前端立即尝试一次原地址，不能进入五分钟负缓存。
                    if await _媒体上游地址已过期(上游):
                        _记录媒体代理失败(缓存键)
                        return _媒体代理失败响应(模式, 已过期=True)
                    return _媒体代理失败响应(模式)
                _清除媒体代理失败(缓存键)
                try:
                    内容长度 = int(上游.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    内容长度 = 0
                if 内容长度 > 媒体代理最大字节数:
                    return web.Response(status=413, text="媒体文件过大")

                阶段 = "read_prefix"
                前缀 = await 上游.content.read(64 * 1024)
                类型 = _识别媒体类型(
                    上游.headers.get("Content-Type"), 前缀, 最终地址, 模式
                )
                if 模式 == "image" and not 类型.startswith("image/"):
                    return web.Response(status=415, text="不是可预览的图片")
                响应头 = {
                    # 只由登录用户自己的浏览器缓存；服务器不保存收到的图片字节。
                    # 保留已成功展示的 QQ 图片，避免同一带签名地址过期后再次请求变占位。
                    "Cache-Control": "private, max-age=86400, stale-if-error=604800",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Type": 类型,
                }
                if 内容长度 > 0:
                    响应头["Content-Length"] = str(内容长度)
                if 模式 == "image":
                    响应头["Content-Disposition"] = "inline"
                else:
                    响应头["Content-Disposition"] = (
                        "attachment; filename*=UTF-8''" + quote(文件名, safe="")
                    )
                响应 = web.StreamResponse(status=上游.status, headers=响应头)
                阶段 = "prepare_response"
                await 响应.prepare(request)
                if 前缀:
                    if len(前缀) > 媒体代理最大字节数:
                        阶段 = "response_eof"
                        await 响应.write_eof()
                        阶段 = "upstream_release"
                        return 响应
                    阶段 = "response_write"
                    await 响应.write(前缀)
                    已发送 += len(前缀)
                阶段 = "upstream_read"
                async for 数据块 in 上游.content.iter_chunked(64 * 1024):
                    if 已发送 + len(数据块) > 媒体代理最大字节数:
                        logger.warning(
                            "帮助控制台媒体代理达到大小上限：模式=%s，大小上限=%d",
                            模式,
                            媒体代理最大字节数,
                        )
                        break
                    阶段 = "response_write"
                    await 响应.write(数据块)
                    已发送 += len(数据块)
                    阶段 = "upstream_read"
                阶段 = "response_eof"
                await 响应.write_eof()
                阶段 = "upstream_release"
                return 响应
    except asyncio.CancelledError:
        raise
    except (ClientError, asyncio.TimeoutError, TimeoutError, OSError, ValueError) as exc:
        # 异步读取与响应写入会抛出同类连接错误，必须在实际 I/O 边界区分方向。
        客户端断开 = 阶段 in {"prepare_response", "response_write", "response_eof"} and isinstance(exc, ConnectionError)
        if 客户端断开:
            logger.debug(
                "帮助控制台媒体请求被客户端中断：模式=%s，阶段=%s，错误类型=%s，上游状态=%s，已发送字节=%d",
                模式, 阶段, type(exc).__name__,
                上游状态 if 上游状态 is not None else "none", 已发送,
            )
        else:
            logger.warning(
                "帮助控制台媒体代理失败：模式=%s，阶段=%s，错误类型=%s，上游状态=%s，已发送字节=%d",
                模式, 阶段, type(exc).__name__,
                上游状态 if 上游状态 is not None else "none", 已发送,
            )
        if 响应 is not None and (响应.prepared or 客户端断开):
            响应.force_close()
            传输 = request.transport
            if 传输 is not None:
                传输.close()
            return 响应
        return _媒体代理失败响应(模式)


async def _处理蓝奏云归档图片(request: web.Request) -> web.StreamResponse:
    return await _处理云盘归档媒体(request, "lanzou")


async def _处理夸克归档媒体(request: web.Request) -> web.StreamResponse:
    return await _处理云盘归档媒体(request, "quark")


async def _处理云盘归档媒体(request: web.Request, provider: str) -> web.StreamResponse:
    if not _请求已授权(request):
        return web.Response(status=401, text="请先登录控制台")
    会话标识 = str(request.query.get("chat_id") or "").strip()
    类型 = str(request.query.get("chat_type") or "group").strip().lower()
    消息ID = str(request.query.get("message_id") or "").strip()
    appid = str(request.query.get("appid") or "").strip()
    if appid and not re.fullmatch(r"[0-9]{4,32}", appid):
        return web.Response(status=400, text="媒体记录参数无效")
    try:
        媒体索引 = int(request.query.get("media_index") or 0)
    except (TypeError, ValueError):
        return web.Response(status=400, text="媒体记录参数无效")
    if not 会话标识 or len(会话标识) > 200 or 类型 not in {"group", "user"} or not 消息ID or len(消息ID) > 512 or not 0 <= 媒体索引 < 10000:
        return web.Response(status=400, text="媒体记录参数无效")
    响应: web.StreamResponse | None = None
    阶段 = "archive_lookup"
    上游状态: int | None = None
    已发送 = 0
    try:
        import zlib
        from 功能文件.管理功能.基础功能 import 消息记录, 消息记录存储
        from 功能文件.管理功能.网盘功能 import 夸克媒体归档, 旧蓝奏云归档读取

        归档模块 = 夸克媒体归档 if provider == "quark" else 旧蓝奏云归档读取
        账号配置快照 = 夸克媒体归档._配置快照(_当前作用域配置())

        数据库快照 = 消息记录存储.获取数据库配置快照(_当前作用域配置())
        归档 = await _控制台线程执行(
            消息记录存储.执行数据库配置快照操作, 数据库快照,
            partial(消息记录存储.读取消息媒体归档, provider=provider, appid=appid), 会话标识, 消息ID, 类型, 媒体索引,
        )
        if not isinstance(归档, dict):
            return web.Response(status=404, text="媒体归档不存在")
        阶段 = "archive_metadata"
        大小 = int(归档.get("size") or 0)
        偏移 = 0 if provider == "quark" else 旧蓝奏云归档读取._归档偏移(归档)
        try:
            起点, 终点, 分段 = 归档模块.解析媒体范围(request.headers.get("Range", ""), 大小)
        except ValueError:
            return web.Response(status=416, headers={"Content-Range": f"bytes */{大小}"})
        # ZIP_STORED 精确映射原文件偏移；若上游忽略 Range，则有界跳过容器头。
        远端范围 = f"bytes={偏移 + 起点}-{偏移 + 终点}" if 偏移 or 分段 else ""
        已完整读取 = False

        async def 保存直链(直链: str, 获取时间: float) -> None:
            if not 已完整读取:
                return
            参数 = (会话标识, 消息ID, 类型, 媒体索引, 归档, 直链, 获取时间)
            成功 = await _控制台线程执行(
                消息记录存储.执行数据库配置快照操作, 数据库快照,
                partial(消息记录.更新消息媒体直链, provider=provider, appid=appid), *参数,
            )
            if 成功 and 数据库快照 == 消息记录存储.获取数据库配置快照(_当前作用域配置()):
                消息记录.更新缓存消息媒体直链(*参数, provider=provider, appid=appid)

        阶段 = "archive_open"
        读取上下文 = (
            夸克媒体归档.打开归档媒体(账号配置快照, 归档, 范围=远端范围, 保存直链=保存直链)
            if provider == "quark" else 旧蓝奏云归档读取.打开归档图片(
                str(归档.get("share_url") or ""), str(归档.get("password") or ""),
                范围=远端范围, 归档资料=归档, 保存直链=保存直链,
            )
        )
        async with 读取上下文 as 上游:
            上游状态 = 上游.status
            阶段 = "upstream_read"
            块流 = 归档模块.读取归档媒体块(上游, 归档, 起点, 终点)
            前块 = await anext(块流)
            阶段 = "media_type"
            MIME = str(归档.get("content_type") or "").split(";", 1)[0].lower()
            文件归档 = 归档.get("media_kind") == "file" or MIME == "application/octet-stream"
            if not 文件归档 and not re.fullmatch(r"(?:image|video|audio)/[a-z0-9.+-]+", MIME):
                return web.Response(status=415, text="归档内容类型无效")
            if 起点 == 0 and not 文件归档 and not 归档模块.识别媒体类型(前块[:128], MIME):
                return web.Response(status=415, text="归档内容不是媒体")
            响应头 = {"Content-Type": MIME, "Content-Length": str(终点 - 起点 + 1),
                      "Content-Disposition": ("attachment; filename*=UTF-8''" + quote(_媒体文件名(归档.get("original_name") or 归档.get("filename")), safe="")) if 文件归档 else "inline", "Cache-Control": "private, max-age=3600",
                      "X-Content-Type-Options": "nosniff", "Accept-Ranges": "bytes",
                      "Content-Security-Policy": "sandbox; default-src 'none'"}
            if 分段:
                响应头["Content-Range"] = f"bytes {起点}-{终点}/{大小}"
            响应 = web.StreamResponse(status=206 if 分段 else 200, headers=响应头)
            阶段 = "response_prepare"
            await 响应.prepare(request)
            校验 = zlib.crc32(前块)
            阶段 = "response_write"
            await 响应.write(前块)
            已发送 += len(前块)
            阶段 = "upstream_read"
            async for 块 in 块流:
                校验 = zlib.crc32(块, 校验)
                阶段 = "response_write"
                await 响应.write(块)
                已发送 += len(块)
                阶段 = "upstream_read"
            阶段 = "crc"
            if not 分段 and 归档.get("container") == "zip-stored" and 校验 & 0xffffffff != int(归档.get("crc32", -1)):
                raise ValueError("archive_crc_mismatch")
            阶段 = "response_eof"
            await 响应.write_eof()
            # Content-Length 响应的空 EOF 不一定触碰套接字，补查客户端连接。
            传输 = request.transport
            if 传输 is None or 传输.is_closing():
                raise ConnectionResetError("media_client_disconnected")
            阶段 = "complete"
            已完整读取 = True
            return 响应
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # 仅响应写入边界的连接异常表示下游断开；同类上游异常仍需告警。
        客户端断开 = 阶段 in {"response_prepare", "response_write", "response_eof"} and isinstance(exc, ConnectionError)
        if 客户端断开:
            logger.debug("帮助控制台云盘媒体请求被客户端中断：媒体序号=%s，阶段=%s，错误类型=%s，已发送字节=%d", 媒体索引 + 1, 阶段, type(exc).__name__, 已发送)
        else:
            logger.warning("帮助控制台云盘媒体读取失败：媒体序号=%s，阶段=%s，原因=%s，错误类型=%s，状态=%s，已发送字节=%d", 媒体索引 + 1, 阶段, getattr(exc, "阶段", "none"), type(exc).__name__, getattr(exc, "状态码", 0) or 上游状态 or "none", 已发送)
        if 响应 is not None and (响应.prepared or 客户端断开):
            响应.force_close()
            if request.transport is not None:
                request.transport.close()
            return 响应
        return web.Response(status=502, text="媒体归档暂时不可用")


本地发送媒体有效期秒 = 3 * 24 * 60 * 60
本地发送媒体清理间隔秒 = 5 * 60
本地发送媒体上次清理时间 = float(globals().get("本地发送媒体上次清理时间", 0.0) or 0.0)
本地发送媒体扩展名 = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".silk", ".dat"})


def _默认本地发送媒体目录() -> Path:
    """返回统一文件缓存下的媒体分类目录。"""
    from 功能文件.管理功能.基础功能 import 文件缓存

    return 文件缓存.媒体缓存目录


本地发送媒体目录 = _默认本地发送媒体目录()


def _本地发送媒体路径(文件名: Any) -> Path | None:
    名称 = str(文件名 or "").strip()
    if not re.fullmatch(r"[0-9a-f]{32}\.[A-Za-z0-9]{1,8}", 名称, re.IGNORECASE):
        return None
    路径 = (本地发送媒体目录 / 名称).resolve()
    根目录 = 本地发送媒体目录.resolve()
    if 路径.parent != 根目录:
        return None
    return 路径


def _清理本地发送媒体同步(现在: float | None = None) -> None:
    global 本地发送媒体上次清理时间
    是否强制 = 现在 is not None
    当前时间 = float(现在 if 现在 is not None else time.time())
    if not 是否强制 and 当前时间 - 本地发送媒体上次清理时间 < 本地发送媒体清理间隔秒:
        return
    本地发送媒体上次清理时间 = 当前时间
    截止时间 = 当前时间 - 本地发送媒体有效期秒
    try:
        if not 本地发送媒体目录.is_dir():
            return
        for 路径 in 本地发送媒体目录.iterdir():
            if not 路径.is_file() or 路径.suffix.lower() not in 本地发送媒体扩展名:
                continue
            try:
                if 路径.stat().st_mtime < 截止时间:
                    路径.unlink(missing_ok=True)
            except OSError:
                continue
    except OSError:
        return


def _保存本地发送媒体同步(数据: bytes, 文件名: str, 内容类型: str) -> str:
    """旧接口兼容占位；新发送媒体不再写入服务器硬盘。"""
    return ""


async def 保存本地发送媒体(
    数据: bytes,
    文件名: str = "",
    内容类型: str = "application/octet-stream",
) -> str:
    """兼容旧调用方；实际媒体副本由浏览器 Cache API 保存。"""
    return ""


async def _处理本地发送媒体(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return web.Response(status=401, text="请先登录控制台")
    路径 = _本地发送媒体路径(request.match_info.get("filename"))
    if 路径 is None or not 路径.is_file():
        return web.Response(status=404, text="媒体暂时不可用")
    try:
        # 清理只做后台维护；当前文件用 mtime 单点校验，避免 GET 等待目录扫描。
        _安排控制台后台任务(_清理本地发送媒体同步)
        if not 路径.is_file() or 路径.stat().st_mtime < time.time() - 本地发送媒体有效期秒:
            return web.Response(status=404, text="媒体暂时不可用")
        类型 = mimetypes.guess_type(路径.name)[0] or "application/octet-stream"
        return web.FileResponse(
            路径,
            headers={
                "Cache-Control": "private, max-age=120",
                "Content-Type": 类型,
                "X-Content-Type-Options": "nosniff",
            },
        )
    except OSError:
        return web.Response(status=404, text="媒体暂时不可用")


async def _处理控制台登录(request: web.Request) -> web.Response:
    数据 = await _读取请求JSON(request)
    用户名 = str((数据 or {}).get("username") or "").strip()
    密码 = str((数据 or {}).get("password") or "")
    配置快照 = 获取控制台会话配置快照()
    请求指纹 = 获取控制台认证指纹(配置快照)
    配置用户名, 配置密码 = _读取控制台账号(配置快照)
    if not 配置用户名 or not 配置密码:
        return _控制台错误(503, "登录服务尚未配置")
    if not (
        hmac.compare_digest(用户名, 配置用户名)
        and hmac.compare_digest(密码, 配置密码)
    ):
        return _控制台错误(401, "账号或密码错误")

    _清理控制台会话()
    会话值 = secrets.token_urlsafe(32)
    到期时间 = time.time() + 控制台会话有效期
    控制台会话[会话值] = 到期时间
    控制台会话身份[会话值] = 配置用户名
    await _控制台线程执行(
        _写入持久化控制台会话,
        会话值,
        到期时间,
        配置用户名,
        配置快照,
    )
    if 会话值 in 控制台会话恢复排除 or not hmac.compare_digest(请求指纹, 控制台会话认证指纹):
        控制台会话.pop(会话值, None)
        控制台会话身份.pop(会话值, None)
        控制台会话最后持久化.pop(会话值, None)
        return _控制台错误(409, "登录状态已更新，请重新登录")
    控制台会话最后持久化[会话值] = time.time()
    响应 = web.json_response({"ok": True})
    响应.set_cookie(
        控制台会话Cookie名,
        会话值,
        max_age=控制台会话有效期,
        httponly=True,
        samesite="Lax",
        secure=request.secure,
        path="/",
    )
    return 响应


async def _处理控制台退出(request: web.Request) -> web.Response:
    会话值 = _取得请求会话(request)
    配置快照 = 获取控制台会话配置快照()
    if 会话值:
        控制台会话恢复排除.add(会话值)
    控制台会话.pop(会话值, None)
    控制台会话身份.pop(会话值, None)
    控制台会话最后持久化.pop(会话值, None)
    await _取消夸克网页扫码所有者(会话值)
    await _取消QQ阅读网页扫码所有者(会话值)
    await _取消晋江网页扫码所有者(会话值)
    await _取消QQ阅读网页短信所有者(会话值)
    await _控制台线程执行(_删除持久化控制台会话, 会话值, 配置快照)
    响应 = web.json_response({"ok": True})
    响应.del_cookie(控制台会话Cookie名, path="/")
    return 响应


def _读取控制台数据(登录用户名: str = "") -> dict[str, Any]:
    from 功能文件.管理功能.基础功能 import 状态功能
    from 功能文件.管理功能.基础功能.运行状态数据库 import (
        已配置运行状态数据库,
        检查运行状态数据库,
    )
    from 功能文件.管理功能.网盘功能 import (
        UC网盘,
        夸克网盘,
        百度网盘,
        网盘Cookie,
        网盘状态,
        小说网盘,
    )
    from 功能文件.管理功能.小说功能.功能 import 小说功能开关

    配置 = _当前作用域配置()
    数据库已配置 = 已配置运行状态数据库(配置)
    数据库状态 = 检查运行状态数据库(配置)
    数据库展示配置 = 获取控制台会话配置快照(配置)["database_settings"]
    QQ登录态摘要: dict[str, Any] = {"configured": False}
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        QQ登录态摘要 = {"editable": 数据库已配置, **QQ阅读.读取QQ阅读账号列表(配置)}
    except Exception as exc:
        logger.warning("帮助控制台 QQ阅读状态读取失败：错误类型=%s", type(exc).__name__)
    小说控制台状态 = 小说功能开关.读取小说功能控制台状态(配置)
    状态 = 小说控制台状态["platforms"]
    平台列表 = [
        {
            "key": 功能名,
            "name": 小说功能开关.功能显示名.get(功能名, 功能名),
            "enabled": bool(状态.get(功能名, True)),
        }
        for 功能名 in 小说功能开关.默认状态
    ]
    网盘定义 = (
        ("UC", "UC网盘", UC网盘.读取UC上传目录),
        ("夸克", "夸克网盘", 夸克网盘.读取夸克上传目录),
        ("百度", "百度网盘", 百度网盘.读取百度上传目录),
    )
    try:
        网盘账号摘要批量 = 网盘Cookie.获取网盘账号摘要批量(配置)
    except Exception as exc:
        logger.warning("帮助控制台网盘账号批量读取失败：错误类型=%s", type(exc).__name__)
        网盘账号摘要批量 = {}
    网盘列表 = []
    当前网盘 = 小说网盘.获取当前主网盘(配置)
    网盘启用状态 = 网盘状态.读取网盘开关批量(配置)
    for 标识, 名称, 读取目录 in 网盘定义:
        try:
            账号摘要 = list(网盘账号摘要批量.get(标识) or [])
            账号数量 = len(账号摘要)
            已配置 = bool(账号摘要)
            目录 = str(读取目录(配置) or "")
            默认账号 = 网盘Cookie.获取默认网盘账号序号(配置, 标识)
        except Exception:
            已配置, 账号数量, 账号摘要, 目录, 默认账号 = False, 0, [], "", 0
        网盘列表.append(
            {
                "key": 标识,
                "name": 名称,
                "configured": 已配置,
                "accounts": int(账号数量),
                "account_summary": 账号摘要,
                "directory": 目录,
                "enabled": bool(网盘启用状态.get(标识, True)),
                "active": 标识 == 当前网盘,
                "default_account": int(默认账号 or 0),
                "selected_account": int(默认账号 or 0),
            }
        )

    host, port = _读取监听配置(配置)
    配置摘要 = _读取插件配置摘要()
    管理员字段 = next(
        (
            字段
            for 字段 in 配置摘要.get("fields", [])
            if 字段.get("key") == "group_file_cleanup_admin_qq"
        ),
        {},
    )
    return {
        "ok": True,
        "version": 控制台版本,
        "updated_at": int(time.time()),
        "auth": {
            "username": str(登录用户名 or "管理员"),
            "role": "控制台管理员",
            "admin_count": int(管理员字段.get("count") or 0),
        },
        "database": {
            "configured": 数据库已配置,
            "status": 数据库状态,
            "address": str(数据库展示配置.get("database_host") or ""),
            "port": str(数据库展示配置.get("database_port") or ""),
            "username": str(数据库展示配置.get("database_user") or ""),
            "name": str(数据库展示配置.get("database_name") or ""),
            "password_configured": bool(数据库展示配置.get("database_password")),
        },
        "novels": {
            "global_enabled": bool(小说控制台状态["global_enabled"]),
            "test_mode": bool(小说控制台状态["test_mode"]),
            "editable": 数据库已配置,
            "platforms": 平台列表,
        },
        "pans": {
            "active": 当前网盘,
            "editable": 数据库已配置,
            "config_editable": bool(配置摘要.get("editable")),
            "items": 网盘列表,
        },
        "server": {
            "listen": f"{host}:{port}",
            "address": _计算帮助网页地址(配置),
            "runtime": 状态功能.格式化系统运行时间(),
            "cpu": 状态功能.格式化系统CPU(),
            "memory": 状态功能.格式化系统内存(),
            "disk": 状态功能.格式化磁盘信息(),
            "os": 状态功能.获取操作系统名称(),
        },
        "config": {
            "help_web_host": host,
            "help_web_port": port,
            "custom_domain": bool(_规范化公开地址(_读取帮助网页字段(配置, "help_web_domain"))),
            "auth_mode": "账号密码 + 会话 Cookie",
            **配置摘要,
        },
        "qq_reader": QQ登录态摘要,
    }


async def _处理控制台数据(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    try:
        数据 = await _控制台线程执行(
            _读取控制台数据, _读取当前控制台身份(request)
        )
        return web.json_response(数据, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台数据读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "控制台数据暂时不可用")


def _解析消息布局布尔值(值: Any, 默认值: bool = False) -> bool:
    if isinstance(值, bool):
        return 值
    if isinstance(值, (int, float)):
        return bool(值)
    文本 = str(值 or "").strip().lower()
    if 文本 in {"1", "true", "yes", "on", "开启"}:
        return True
    if 文本 in {"0", "false", "no", "off", "关闭"}:
        return False
    return 默认值


def _规范化消息布局(布局: Any = None) -> dict[str, Any]:
    来源 = 布局 if isinstance(布局, dict) else {}
    try:
        列表宽度 = int(来源.get("list_width", 消息布局默认值["list_width"]))
    except (TypeError, ValueError):
        列表宽度 = int(消息布局默认值["list_width"])
    try:
        输入高度 = int(
            来源.get("composer_height", 消息布局默认值["composer_height"])
        )
    except (TypeError, ValueError):
        输入高度 = int(消息布局默认值["composer_height"])
    return {
        "list_width": max(220, min(680, 列表宽度)),
        "composer_height": max(96, min(420, 输入高度)),
        "list_collapsed": _解析消息布局布尔值(
            来源.get("list_collapsed"), bool(消息布局默认值["list_collapsed"])
        ),
        "composer_collapsed": _解析消息布局布尔值(
            来源.get("composer_collapsed"),
            bool(消息布局默认值["composer_collapsed"]),
        ),
    }


def _读取消息布局() -> dict[str, Any]:
    默认布局 = _规范化消息布局(消息布局默认值)
    if not _数据库会话可用():
        return 默认布局
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态命名空间

        状态 = 读取运行状态命名空间(_当前作用域配置(), 消息布局命名空间)
        return _规范化消息布局({**默认布局, **状态})
    except Exception as exc:
        logger.debug("帮助控制台消息布局读取失败：错误类型=%s", type(exc).__name__)
        return 默认布局


async def _处理消息布局(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if request.method.upper() == "GET":
        return web.json_response(
            {
                "ok": True,
                "layout": await _控制台线程执行(_读取消息布局),
                "persisted": _数据库会话可用(),
            },
            headers={"Cache-Control": "no-store"},
        )
    数据 = await _读取请求JSON(request)
    if not isinstance(数据, dict):
        return _控制台错误(400, "布局参数无效")
    允许字段 = {
        "list_width",
        "composer_height",
        "list_collapsed",
        "composer_collapsed",
    }
    更新 = {键: 数据[键] for 键 in 允许字段 if 键 in 数据}
    if not 更新:
        return _控制台错误(400, "布局参数无效")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，布局无法保存")

    def _写入布局() -> dict[str, Any]:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 批量写入运行状态值

        当前布局 = _读取消息布局()
        合并布局 = _规范化消息布局({**当前布局, **更新})
        批量写入运行状态值(
            _当前作用域配置(),
            消息布局命名空间,
            {键: 合并布局[键] for 键 in 允许字段},
        )
        return 合并布局

    try:
        布局 = await _控制台线程执行(_写入布局)
        return web.json_response(
            {"ok": True, "layout": 布局, "persisted": True},
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        logger.warning("帮助控制台消息布局保存失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "布局保存失败，请稍后重试")


async def _处理机器人资料(request: web.Request) -> web.Response:
    """返回全部 QQ 官方机器人公开资料，兼容单资料读取。"""
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    目标AppID = str(request.query.get("appid") or "").strip()
    if 目标AppID and not re.fullmatch(r"[0-9]{4,32}", 目标AppID):
        return _控制台错误(400, "机器人参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        资料列表 = await 消息记录.获取机器人资料列表()
        字段 = ("appid", "platform_id", "id", "username", "avatar", "status", "profile_status")
        资料列表 = [
            {键: str(资料.get(键) or "") for 键 in 字段}
            for 资料 in 资料列表 if isinstance(资料, dict)
        ]
        try:
            统计列表 = await 消息记录.获取机器人消息统计([项["appid"] for 项 in 资料列表])
            if not isinstance(统计列表, dict):
                统计列表 = {}
        except Exception as 统计异常:
            logger.debug("帮助控制台机器人统计读取失败：错误类型=%s", type(统计异常).__name__)
            统计列表 = {}
        for 项 in 资料列表:
            项["stats"] = 统计列表.get(项["appid"], {
                "group_count": None, "user_count": None, "status": "unavailable",
            })
        资料 = next((项 for 项 in 资料列表 if 项.get("appid") == 目标AppID), {}) if 目标AppID else next(iter(资料列表), {})
        return web.json_response(
            {"ok": True, "profile": 资料, "profiles": 资料列表,
             "version": 控制台版本, "auth": {"username": _读取当前控制台身份(request)}},
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        logger.debug("帮助控制台机器人资料读取失败：错误类型=%s", type(exc).__name__)
        return web.json_response(
            {"ok": True, "profile": {}, "profiles": [], "version": 控制台版本},
            headers={"Cache-Control": "no-store"},
        )


async def _处理小说开关(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    if 数据 is None or not isinstance(数据.get("enabled"), bool):
        return _控制台错误(400, "请求参数无效")
    功能名 = str(数据.get("key") or "").strip()
    enabled = bool(数据["enabled"])

    def _写入() -> None:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 写入布尔运行状态值
        from 功能文件.管理功能.小说功能.功能 import 小说功能开关

        if 功能名 == "__global__":
            写入布尔运行状态值(
                _当前作用域配置(),
                小说功能开关.状态命名空间,
                小说功能开关.小说总开关状态键,
                enabled,
            )
        elif 功能名 == "__test__":
            写入布尔运行状态值(
                _当前作用域配置(),
                小说功能开关.状态命名空间,
                小说功能开关.管理员测试模式状态键,
                enabled,
            )
        elif 功能名 in 小说功能开关.默认状态:
            小说功能开关.写入小说功能状态(_当前作用域配置(), 功能名, enabled)
        else:
            raise ValueError("unknown feature")

    try:
        await _控制台线程执行(_写入)
        return web.json_response({"ok": True})
    except Exception as exc:
        logger.warning("帮助控制台小说开关写入失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "小说开关保存失败，请检查数据库配置")


async def _处理网盘切换(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，默认网盘不能保存")
    数据 = await _读取请求JSON(request)
    网盘名 = str((数据 or {}).get("key") or "").strip()
    if 网盘名 not in {"UC", "夸克", "百度"}:
        return _控制台错误(400, "网盘参数无效")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie, 网盘状态

        网盘已开启 = await _控制台线程执行(
            网盘状态.网盘开关是否开启,
            _当前作用域配置(),
            网盘名,
        )
        if not 网盘已开启:
            return _控制台错误(409, "该网盘已关闭，请先开启")
        可用账号 = await _控制台线程执行(
            网盘Cookie.获取启用网盘账号列表,
            _当前作用域配置(),
            网盘名,
        )
        if not 可用账号:
            return _控制台错误(409, "该网盘没有启用的账号")
    except Exception as exc:
        logger.warning(
            "帮助控制台主网盘开关读取失败：平台=%s，错误类型=%s",
            网盘名,
            type(exc).__name__,
        )
        return _控制台错误(409, "网盘状态暂时不可用")

    def _写入() -> None:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值

        写入运行状态值(_当前作用域配置(), "novel_share_pan", "active", 网盘名)

    try:
        await _控制台线程执行(_写入)
        return web.json_response({"ok": True})
    except Exception as exc:
        logger.warning("帮助控制台主网盘切换失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "主网盘保存失败，请检查数据库配置")


async def _处理网盘开关(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    if 数据 is None or not isinstance(数据.get("enabled"), bool):
        return _控制台错误(400, "请求参数无效")
    网盘名 = str(数据.get("key") or "").strip()
    if 网盘名 not in {"UC", "夸克", "百度"}:
        return _控制台错误(400, "网盘参数无效")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，网盘开关不能保存")
    启用 = bool(数据["enabled"])
    try:
        from 功能文件.管理功能.网盘功能 import 网盘状态

        await _控制台线程执行(
            网盘状态.写入网盘开关,
            _当前作用域配置(),
            网盘名,
            启用,
        )
        return web.json_response(
            {"ok": True, "enabled": 启用, "message": "网盘开关已更新"}
        )
    except Exception as exc:
        logger.warning("帮助控制台网盘开关写入失败：平台=%s，错误类型=%s", 网盘名, type(exc).__name__)
        return _控制台错误(409, "网盘开关保存失败，请检查数据库配置")


def _规范化网盘平台(平台: Any) -> str:
    文本 = str(平台 or "").strip()
    return {"uc": "UC", "UC": "UC", "夸": "夸克", "夸克": "夸克", "百度": "百度"}.get(
        文本, ""
    )


async def _处理插件配置数据(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    return web.json_response(
        {"ok": True, **_读取插件配置摘要()},
        headers={"Cache-Control": "no-store"},
    )


async def _串行写入插件配置(request: web.Request, 处理函数: Any) -> web.Response:
    配置 = _当前作用域配置()
    # API Keys 为服务共用；所有控制台配置写入共享同一锁，跨机器人也不能丢更新。
    键 = (id(getattr(配置, "基础配置", 配置)), "shared_config")
    项 = _机器人配置请求锁.setdefault(键, {"lock": asyncio.Lock(), "users": 0})
    项["users"] += 1
    try:
        async with 项["lock"]:
            return await 处理函数(request)
    finally:
        项["users"] -= 1
        if 项["users"] == 0 and _机器人配置请求锁.get(键) is 项:
            _机器人配置请求锁.pop(键, None)


async def _处理插件配置写入(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    return await _串行写入插件配置(request, _处理当前机器人配置写入)


async def _处理QQ阅读API密钥(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    return await _串行写入插件配置(request, _修改QQ阅读API密钥)


async def _修改QQ阅读API密钥(request: web.Request) -> web.Response:
    from 功能文件.页面功能 import QQ阅读开放接口
    数据 = await _读取请求JSON(request)
    if not isinstance(数据, dict) or 数据.get("action") not in ("generate", "delete"):
        return _控制台错误(400, "密钥操作无效")
    配置 = _当前作用域配置()
    if 配置 is None:
        return _控制台错误(503, "插件配置不可用")
    分类名 = "qq_reader_api_settings"
    字典 = _读取插件配置字典(配置)
    if not isinstance(字典, dict):
        return _控制台错误(503, "插件配置不可用")
    旧分类 = copy.deepcopy(字典.get(分类名))
    keys = QQ阅读开放接口.读取接口密钥(配置)
    新密钥 = ""
    if 数据["action"] == "generate":
        新密钥 = secrets.token_urlsafe(32)
        while 新密钥 in keys:
            新密钥 = secrets.token_urlsafe(32)
        keys.append(新密钥)
    else:
        标识 = 数据.get("id")
        if not isinstance(标识, str) or not re.fullmatch(r"[a-f0-9]{16}", 标识):
            return _控制台错误(400, "密钥标识无效")
        摘要 = QQ阅读开放接口.读取接口密钥摘要(配置)
        匹配 = [key for key, 项 in zip(keys, 摘要) if hmac.compare_digest(项["id"], 标识)]
        if len(匹配) != 1:
            return _控制台错误(404, "密钥不存在")
        keys.remove(匹配[0])
    try:
        _设置插件配置值(配置, 分类名, "qq_reader_api_keys", keys)
        _设置插件配置值(配置, 分类名, "qq_reader_api_key", "")
        if _插件配置可持久化(配置):
            await _持久化插件配置()
        elif not isinstance(配置, dict):
            raise RuntimeError("插件配置不可保存")
    except BaseException as exc:
        if 旧分类 is None:
            字典.pop(分类名, None)
        else:
            字典[分类名] = 旧分类
        清除 = getattr(配置, "清除待保存字段", None)
        if callable(清除):
            清除()
        if isinstance(exc, asyncio.CancelledError):
            raise
        if not isinstance(exc, Exception):
            raise
        logger.warning("QQ阅读API密钥保存失败：error_type=%s", type(exc).__name__)
        return _控制台错误(409, "密钥保存失败，请稍后重试")
    响应 = {"ok": True, "keys": QQ阅读开放接口.读取接口密钥摘要(配置),
            "message": "新 Key 已添加，请立即复制保存，仅显示本次" if 新密钥 else "Key 已撤销"}
    if 新密钥:
        响应["key"] = 新密钥
    return web.json_response(响应, headers={"Cache-Control": "no-store"})


async def _处理当前机器人配置写入(request: web.Request) -> web.Response:
    数据 = await _读取请求JSON(request)
    字段数据 = (数据 or {}).get("fields")
    if not isinstance(字段数据, dict) or not 字段数据:
        return _控制台错误(400, "配置参数无效")
    if _当前作用域配置() is None:
        return _控制台错误(503, "插件配置不可用")
    配置字典: dict[str, Any] | None = None
    原配置快照: dict[str, Any] | None = None
    阶段 = "读取配置"
    try:
        配置字典 = _读取插件配置字典(_当前作用域配置())
        原认证指纹 = 获取控制台认证指纹(_当前作用域配置())
        阶段 = "创建配置快照"
        原配置快照 = (
            _复制插件配置值(配置字典)
            if isinstance(配置字典, dict)
            else None
        )
        待更新: list[tuple[str, dict[str, Any], Any]] = []
        阶段 = "校验配置"
        for 字段名, 原值 in 字段数据.items():
            字段名 = str(字段名 or "").strip()
            定义 = 插件配置字段定义.get(字段名)
            if not 定义:
                raise ValueError("配置字段不支持")
            if 定义.get("secret") and (原值 is None or isinstance(原值, str) and not 原值.strip()):
                continue
            值 = _校验插件配置字段(字段名, 原值)
            待更新.append((字段名, 定义, 值))
        已更新 = []
        阶段 = "写入配置"
        # 先完整校验，再一次性写入，避免同一请求中后续字段失败时留下半套配置。
        for 字段名, 定义, 值 in 待更新:
            _设置插件配置值(
                _当前作用域配置(),
                str(定义["category"]),
                字段名,
                值,
            )
            if 字段名 == "qq_reader_api_keys":
                _设置插件配置值(_当前作用域配置(), "qq_reader_api_settings", "qq_reader_api_key", "")
            已更新.append(字段名)
        阶段 = "持久化配置"
        if 已更新 and _插件配置可持久化(_当前作用域配置()):
            await _持久化插件配置()
        elif 已更新 and not isinstance(_当前作用域配置(), dict):
            raise RuntimeError("插件配置没有持久化接口")
        if "group_file_cleanup_admin_qq" in 已更新:
            阶段 = "同步管理员白名单"
            from 功能文件.管理功能.基础功能 import 权限工具

            权限工具.同步管理员白名单(_当前作用域配置(), 强制=True)
        return web.json_response(
            {
                "ok": True,
                "updated": 已更新,
                "restart_required": any(
                    插件配置字段定义[键]["category"] not in 机器人独立配置分类
                    and not (插件配置字段定义[键]["category"] == "help_web_settings" and 键 in 机器人独立帮助字段)
                    for 键 in 已更新
                ),
                "auth_changed": not hmac.compare_digest(
                    原认证指纹,
                    获取控制台认证指纹(_当前作用域配置()),
                ),
                "message": "配置已保存；共用数据库连接、监听地址和登录账号等变更需重载插件生效",
            }
        )
    except ValueError:
        return _控制台错误(400, "配置参数无效")
    except asyncio.CancelledError:
        if isinstance(配置字典, dict) and isinstance(原配置快照, dict):
            配置字典.clear()
            配置字典.update(原配置快照)
        清除 = getattr(配置字典, "清除待保存字段", None)
        if callable(清除):
            清除()
        raise
    except Exception as exc:
        if isinstance(配置字典, dict) and isinstance(原配置快照, dict):
            配置字典.clear()
            配置字典.update(原配置快照)
        清除 = getattr(配置字典, "清除待保存字段", None)
        if callable(清除):
            清除()
        logger.warning(
            "帮助控制台插件配置保存失败：阶段=%s，错误类型=%s",
            阶段,
            type(exc).__name__,
        )
        return _控制台错误(409, "配置保存失败，请稍后重试")


async def _处理网盘账号列表(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    平台 = _规范化网盘平台(request.match_info.get("platform"))
    if not 平台:
        return _控制台错误(400, "网盘参数无效")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        if 平台 == "夸克":
            await 网盘Cookie._刷新夸克账号资料(
                _当前作用域配置(),
                强制=request.query.get("refresh") == "1",
            )
        摘要 = await _控制台线程执行(
            网盘Cookie.获取网盘账号摘要, _当前作用域配置(), 平台
        )
        当前序号 = await _控制台线程执行(
            网盘Cookie.获取当前网盘账号序号, _当前作用域配置(), 平台
        )
        return web.json_response(
            {
                "ok": True,
                "platform": 平台,
                "selected_account": 当前序号,
                "default_account": 当前序号,
                "accounts": 摘要,
            },
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        logger.warning("帮助控制台网盘账号读取失败：平台=%s, 错误类型=%s", 平台, type(exc).__name__)
        return _控制台错误(500, "网盘账号读取失败")


async def _处理网盘账号新增(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    平台 = _规范化网盘平台(request.match_info.get("platform"))
    数据 = await _读取请求JSON(request)
    Cookie文本 = str((数据 or {}).get("cookie") or "").strip()
    if not 平台 or not Cookie文本:
        return _控制台错误(400, "网盘账号参数无效")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        解析结果 = 网盘Cookie.解析网盘Cookie(f"{平台} Cookie: {Cookie文本}")
        if not 解析结果 or 解析结果[0] != 平台 or not 解析结果[1]:
            return _控制台错误(400, "网盘账号格式无效")
        资料保存参数: dict[str, Any] = {}
        if 平台 == "夸克":
            账号资料 = await 网盘Cookie._获取夸克账号资料(
                解析结果[1]
            )
            资料保存参数 = 网盘Cookie._夸克账号资料保存参数(账号资料)
        序号 = await _控制台线程执行(
            网盘Cookie._保存网盘Cookie,
            状态["config"],
            平台,
            解析结果[1],
            **资料保存参数,
        )
        return web.json_response(
            {"ok": True, "index": 序号, "message": f"{平台}账号已保存"}
        )
    except Exception as exc:
        logger.warning("帮助控制台网盘账号保存失败：平台=%s, 错误类型=%s", 平台, type(exc).__name__)
        return _控制台错误(409, "网盘账号保存失败，请检查数据库配置")


def _夸克网页扫码状态文案(状态: str) -> str:
    return {
        "waiting": "请使用夸克 App 扫描二维码，二维码有效期为 5 分钟。",
        "saving": "扫码成功，正在读取账号资料并保存。",
        "success": "夸克账号已添加。",
        "expired": "二维码已过期，请重新获取。",
        "cancelled": "扫码已取消。",
        "error": "扫码失败，请重新获取二维码。",
    }.get(状态, "扫码状态暂不可用。")


def _夸克扫码仍有效(状态: dict[str, Any]) -> bool:
    return (
        夸克扫码启动代次.get(状态.get("owner")) == 状态.get("generation")
        and 控制台会话.get(状态.get("session"), 0) > time.time()
        and hmac.compare_digest(获取控制台认证指纹(状态.get("config")), 控制台会话认证指纹)
    )


def _保存夸克扫码账号(状态: dict[str, Any], Cookie: str, 资料: dict[str, Any]) -> int:
    if not _夸克扫码仍有效(状态):
        return 0
    from 功能文件.管理功能.网盘功能 import 网盘Cookie
    return 网盘Cookie._保存网盘Cookie(状态["config"], "夸克", Cookie, **资料)


async def _运行夸克网页扫码(scan_id: str) -> None:
    状态 = 夸克网页扫码会话.get(scan_id)
    if not 状态:
        return
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        Cookie = await 状态["client"].等待登录并获取Cookie(
            状态["token"], timeout=300, interval=2
        )
        if not _夸克扫码仍有效(状态):
            状态["status"] = "cancelled"
            return
        状态["status"] = "saving"
        状态["updated_at"] = time.time()
        账号资料 = await 网盘Cookie._获取夸克账号资料(Cookie)
        资料保存参数 = 网盘Cookie._夸克账号资料保存参数(账号资料)
        序号 = await _控制台线程执行(
            _保存夸克扫码账号,
            状态,
            Cookie,
            资料保存参数,
        )
        if not 序号:
            状态["status"] = "cancelled"
            return
        状态["status"] = "success"
        状态["index"] = int(序号)
        状态["updated_at"] = time.time()
    except asyncio.CancelledError:
        状态["status"] = "cancelled"
        状态["updated_at"] = time.time()
        raise
    except TimeoutError:
        状态["status"] = "expired"
        状态["updated_at"] = time.time()
    except Exception as exc:
        阶段 = str(getattr(exc, "阶段", "save" if 状态.get("status") == "saving" else "poll"))
        logger.warning(
            "帮助控制台夸克扫码失败：阶段=%s，错误类型=%s",
            阶段,
            type(exc).__name__,
        )
        状态["status"] = "error"
        状态["updated_at"] = time.time()
    finally:
        状态.pop("token", None)
        try:
            await 状态["client"].关闭()
        except Exception as exc:
            logger.debug("帮助控制台夸克扫码会话关闭失败：错误类型=%s", type(exc).__name__)


async def _移除夸克网页扫码会话(
    scan_id: str, 所有者: str | None = None
) -> bool:
    状态 = 夸克网页扫码会话.get(scan_id)
    if not 状态 or (所有者 is not None and 状态.get("owner") != 所有者):
        return False
    if 夸克扫码启动代次.get(状态.get("owner")) == 状态.get("generation"):
        夸克扫码启动代次.pop(状态.get("owner"), None)
    任务 = 状态.get("task")
    if isinstance(任务, asyncio.Task) and not 任务.done():
        任务.cancel()
        await asyncio.gather(任务, return_exceptions=True)
    try:
        await 状态["client"].关闭()
    except Exception as exc:
        logger.debug("帮助控制台夸克扫码会话关闭失败：错误类型=%s", type(exc).__name__)
    夸克网页扫码会话.pop(scan_id, None)
    return True


async def _取消夸克网页扫码所有者(所有者: str) -> None:
    if not 所有者:
        return
    所有者摘要集合 = _待取消扫码所有者(所有者)
    for 摘要 in 所有者摘要集合:
        夸克扫码启动代次.pop(摘要, None)
    for scan_id, 状态 in list(夸克网页扫码会话.items()):
        if 状态.get("owner") in 所有者摘要集合:
            await _移除夸克网页扫码会话(scan_id, 状态.get("owner"))


async def _取消全部夸克网页扫码() -> None:
    夸克扫码启动代次.clear()
    for scan_id in list(夸克网页扫码会话):
        await _移除夸克网页扫码会话(scan_id)


async def _处理夸克网页扫码开始(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if _规范化网盘平台(request.match_info.get("platform")) != "夸克":
        return _控制台错误(400, "网盘参数无效")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，扫码账号不能保存")

    会话值 = _取得请求会话(request)
    await _取消夸克网页扫码所有者(会话值)
    所有者 = _扫码所有者(会话值)
    代次 = secrets.token_urlsafe(16)
    夸克扫码启动代次[所有者] = 代次
    from 功能文件.管理功能.网盘功能 import 网盘Cookie

    客户端 = 网盘Cookie.夸克扫码登录客户端()
    try:
        Token, 登录地址 = await 客户端.获取登录二维码()
        图片字节 = await asyncio.to_thread(
            网盘Cookie.生成夸克登录二维码, 登录地址
        )
    except Exception as exc:
        阶段 = str(getattr(exc, "阶段", "qr"))
        logger.warning(
            "帮助控制台夸克二维码获取失败：阶段=%s，错误类型=%s",
            阶段,
            type(exc).__name__,
        )
        try:
            await 客户端.关闭()
        except Exception as close_exc:
            logger.debug("帮助控制台夸克扫码会话关闭失败：错误类型=%s", type(close_exc).__name__)
        return _控制台错误(502, "夸克二维码获取失败，请稍后重试")

    if 夸克扫码启动代次.get(所有者) != 代次 or 控制台会话.get(会话值, 0) <= time.time():
        await 客户端.关闭()
        return _控制台错误(409, "扫码会话已结束")
    scan_id = secrets.token_urlsafe(24)
    状态: dict[str, Any] = {
        "owner": 所有者,
        "session": 会话值,
        "appid": 获取当前机器人AppID(),
        "config": 获取控制台会话配置快照(),
        "generation": 代次,
        "client": 客户端,
        "token": Token,
        "status": "waiting",
        "updated_at": time.time(),
        "index": 0,
    }
    夸克网页扫码会话[scan_id] = 状态
    状态["task"] = asyncio.create_task(_运行夸克网页扫码(scan_id))
    图片编码 = base64.b64encode(图片字节).decode("ascii")
    return web.json_response(
        {
            "ok": True,
            "scan_id": scan_id,
            "qr_image": f"data:image/png;base64,{图片编码}",
            "status": "waiting",
            "message": _夸克网页扫码状态文案("waiting"),
            "expires_in": 300,
        },
        headers={"Cache-Control": "no-store"},
    )


async def _处理夸克网页扫码状态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if _规范化网盘平台(request.match_info.get("platform")) != "夸克":
        return _控制台错误(400, "网盘参数无效")
    scan_id = str(request.match_info.get("scan_id") or "").strip()
    状态 = 夸克网页扫码会话.get(scan_id)
    所有者 = _扫码所有者(_取得请求会话(request))
    if not 状态 or 状态.get("owner") != 所有者:
        return _控制台错误(404, "扫码会话已结束，请重新获取二维码")
    当前状态 = str(状态.get("status") or "error")
    if 当前状态 in {"success", "expired", "cancelled", "error"}:
        if time.time() - float(状态.get("updated_at") or 0) > 300:
            await _移除夸克网页扫码会话(scan_id, 状态.get("owner"))
            return _控制台错误(404, "扫码会话已结束，请重新获取二维码")
    return web.json_response(
        {
            "ok": True,
            "status": 当前状态,
            "message": _夸克网页扫码状态文案(当前状态),
            "index": int(状态.get("index") or 0),
        },
        headers={"Cache-Control": "no-store"},
    )


async def _处理夸克网页扫码取消(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if _规范化网盘平台(request.match_info.get("platform")) != "夸克":
        return _控制台错误(400, "网盘参数无效")
    scan_id = str(request.match_info.get("scan_id") or "").strip()
    if not scan_id:
        await _取消夸克网页扫码所有者(_取得请求会话(request))
        return web.json_response({"ok": True, "message": "扫码会话已结束"})
    所有者 = _扫码所有者(_取得请求会话(request))
    await _移除夸克网页扫码会话(scan_id, 所有者)
    return web.json_response({"ok": True, "message": "扫码会话已结束"})


async def _处理网盘账号删除(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    平台 = _规范化网盘平台(request.match_info.get("platform"))
    数据 = await _读取请求JSON(request)
    try:
        序号 = int((数据 or {}).get("index"))
    except (TypeError, ValueError):
        序号 = 0
    if not 平台 or 序号 < 1:
        return _控制台错误(400, "账号序号无效")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        成功, _ = await _控制台线程执行(
            网盘Cookie._删除网盘账号, _当前作用域配置(), 平台, 序号
        )
        if not 成功:
            return _控制台错误(409, "账号不能删除，请检查账号序号和数据库配置")
        return web.json_response({"ok": True, "message": "账号已删除"})
    except Exception as exc:
        logger.warning("帮助控制台网盘账号删除失败：平台=%s, 错误类型=%s", 平台, type(exc).__name__)
        return _控制台错误(409, "网盘账号删除失败")


async def _处理网盘账号开关(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    平台 = _规范化网盘平台(request.match_info.get("platform"))
    数据 = await _读取请求JSON(request)
    try:
        序号 = int((数据 or {}).get("index"))
    except (TypeError, ValueError):
        序号 = 0
    启用 = (数据 or {}).get("enabled")
    if not 平台 or 序号 < 1 or not isinstance(启用, bool):
        return _控制台错误(400, "网盘账号参数无效")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        成功, _ = await _控制台线程执行(
            网盘Cookie._设置网盘账号启用,
            _当前作用域配置(),
            平台,
            序号,
            启用,
        )
        if not 成功:
            return _控制台错误(409, "账号状态保存失败，请检查账号和数据库配置")
        return web.json_response(
            {
                "ok": True,
                "enabled": 启用,
                "message": f"{平台}账号{序号}{'已启用' if 启用 else '已停用'}",
            }
        )
    except Exception as exc:
        logger.warning(
            "帮助控制台网盘账号开关失败：平台=%s，错误类型=%s",
            平台,
            type(exc).__name__,
        )
        return _控制台错误(409, "账号状态保存失败，请检查数据库配置")


async def _处理网盘账号默认(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    平台 = _规范化网盘平台(request.match_info.get("platform"))
    数据 = await _读取请求JSON(request)
    try:
        序号 = int((数据 or {}).get("index"))
    except (TypeError, ValueError):
        序号 = 0
    if not 平台 or 序号 < 1:
        return _控制台错误(400, "网盘账号参数无效")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，默认账号不能保存")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        成功, _ = await _控制台线程执行(
            网盘Cookie.设置默认网盘账号序号,
            _当前作用域配置(),
            平台,
            序号,
        )
        if not 成功:
            return _控制台错误(409, "默认账号设置失败，请检查账号状态和数据库配置")
        return web.json_response(
            {
                "ok": True,
                "default_account": 序号,
                "message": f"{平台}默认账号已更新",
            }
        )
    except Exception as exc:
        logger.warning(
            "帮助控制台网盘默认账号写入失败：平台=%s，错误类型=%s",
            平台,
            type(exc).__name__,
        )
        return _控制台错误(409, "默认账号保存失败，请检查数据库配置")


async def _处理网盘账号选择(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    平台 = _规范化网盘平台((数据 or {}).get("platform"))
    群标识 = str((数据 or {}).get("group_id") or "").strip()
    try:
        序号 = int((数据 or {}).get("index"))
    except (TypeError, ValueError):
        序号 = 0
    if not 平台 or not 群标识 or len(群标识) > 128 or 序号 < 1:
        return _控制台错误(400, "群账号参数无效")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        成功, _ = await _控制台线程执行(
            网盘Cookie.设置网盘账号序号按群标识,
            _当前作用域配置(),
            平台,
            序号,
            群标识,
        )
        if not 成功:
            return _控制台错误(409, "群账号选择失败，请检查账号和数据库配置")
        return web.json_response({"ok": True, "message": "群账号选择已保存"})
    except Exception as exc:
        logger.warning("帮助控制台群账号选择失败：平台=%s, 错误类型=%s", 平台, type(exc).__name__)
        return _控制台错误(409, "群账号选择失败")


def _构建群网盘选择数据(配置: Any, 群标识: str) -> dict[str, Any]:
    from 功能文件.管理功能.网盘功能 import 网盘Cookie

    return {"ok": True, "editable": _数据库会话可用(), **网盘Cookie.获取群网盘选择摘要(配置, 群标识)}


async def _处理群网盘选择(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    群标识 = str((数据 or {}).get("chat_id") or "").strip()
    操作 = str((数据 or {}).get("action") or "get").strip().lower()
    if not 群标识 or len(群标识) > 128:
        return _控制台错误(400, "群标识无效")
    if 操作 == "get":
        try:
            结果 = await _控制台线程执行(
                _构建群网盘选择数据,
                _当前作用域配置(),
                群标识,
            )
            return web.json_response(结果, headers={"Cache-Control": "no-store"})
        except Exception as exc:
            logger.warning(
                "帮助控制台群网盘选择读取失败：错误类型=%s",
                type(exc).__name__,
            )
            return _控制台错误(500, "群网盘选择读取失败")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，群网盘选择不能保存")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘Cookie

        if 操作 == "reset":
            成功, _ = await _控制台线程执行(
                网盘Cookie.清除群网盘账号选择,
                _当前作用域配置(),
                群标识,
            )
            if not 成功:
                return _控制台错误(409, "群网盘选择清除失败")
            return web.json_response({"ok": True, "message": "已恢复全局默认网盘"})
        if 操作 == "file":
            成功, _ = await _控制台线程执行(网盘Cookie.设置群小说文件直发, _当前作用域配置(), 群标识)
            if not 成功:
                return _控制台错误(409, "群文件直发设置失败")
            return web.json_response({"ok": True, "message": "本群已关闭网盘，小说将直接发送文件"})
        if 操作 != "set":
            return _控制台错误(400, "群网盘操作无效")
        平台 = _规范化网盘平台((数据 or {}).get("platform"))
        try:
            序号 = int((数据 or {}).get("index"))
        except (TypeError, ValueError):
            序号 = 0
        if not 平台 or 序号 < 1:
            return _控制台错误(400, "群网盘账号参数无效")
        成功, _ = await _控制台线程执行(
            网盘Cookie.设置群网盘账号选择,
            _当前作用域配置(),
            平台,
            序号,
            群标识,
        )
        if not 成功:
            return _控制台错误(409, "群网盘选择失败，请检查账号状态")
        return web.json_response({"ok": True, "message": "本群网盘账号已更新"})
    except Exception as exc:
        logger.warning(
            "帮助控制台群网盘选择写入失败：错误类型=%s",
            type(exc).__name__,
        )
        return _控制台错误(409, "群网盘选择保存失败")


async def _处理ZLibrary账号资料(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    try:
        import importlib

        模块 = importlib.import_module("功能文件.管理功能.小说功能.小说.Z-Library小说")
        if request.path == "/api/zlibrary-accounts":
            摘要 = await 模块.获取ZLibrary账号列表(_当前作用域配置())
        else:
            摘要 = await 模块.获取ZLibrary账号摘要(_当前作用域配置(), 刷新=request.method == "POST", 账号标识=request.query.get("account_id", ""))
        if not _请求已授权(request):
            return _控制台错误(401, "请重新登录控制台")
        return web.json_response({"ok": True, **摘要}, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    except Exception as exc:
        logger.warning("帮助控制台 ZLibrary账号资料读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(502, "账号资料暂不可用，请稍后刷新")


async def _处理ZLibrary账号管理(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，账号未保存")
    数据 = await _读取请求JSON(request)
    if not 数据:
        return _控制台错误(400, "账号参数无效")
    try:
        import importlib
        模块 = importlib.import_module("功能文件.管理功能.小说功能.小说.Z-Library小说")
        函数 = 模块.导入ZLibrary账号 if request.path.endswith("/import") else 模块.管理ZLibrary账号
        摘要 = await 函数(获取控制台会话配置快照(), 数据, lambda: _请求已授权(request))
        if not _请求已授权(request):
            return _控制台错误(401, "请重新登录控制台")
        return web.json_response({"ok": True, **摘要}, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    except PermissionError:
        return _控制台错误(401, "请重新登录控制台")
    except ValueError as exc:
        # 此业务层 ValueError 只含固定短提示，不含上游响应或凭据。
        允许 = {"账号操作参数无效", "请选择一个账号", "分组或备注过长", "账号已变化或尚未完成注册，请刷新", "请先启用账号", "账号额度未确认或已耗尽，暂不能切换", "账号已变化，请刷新后重试", "每次导入 1～50 个账号", "账号格式无效", "邮箱或密码格式无效", "导入内容包含重复邮箱"}
        return _控制台错误(409, str(exc) if str(exc) in 允许 else "账号参数无效")
    except Exception as exc:
        logger.warning("帮助控制台 ZLibrary账号操作失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(502, "账号操作失败，请刷新列表确认后重试")


def _QQ阅读JSON(数据: dict[str, Any]) -> web.Response:
    return web.json_response(数据, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


async def _处理QQ阅读登录态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        摘要 = await _控制台线程执行(QQ阅读.读取QQ阅读账号列表, _当前作用域配置())
        return _QQ阅读JSON({"ok": True, "editable": _数据库会话可用(), **摘要})
    except Exception as exc:
        logger.warning("帮助控制台 QQ阅读账号读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "QQ阅读账号读取失败")


async def _处理QQ阅读登录态保存(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，账号未保存")
    数据 = await _读取请求JSON(request)
    if not 数据:
        return _控制台错误(400, "账号参数无效")
    文本 = str(数据.get("cookie") or "").strip()
    if not 文本:
        文本 = json.dumps({"ywguid": 数据.get("ywguid"), "ywkey": 数据.get("ywkey")})
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        登录态 = QQ阅读.解析QQ阅读Cookie(文本)
        if not 登录态:
            return _控制台错误(400, "QQ阅读登录态格式无效")
        配置 = 获取控制台会话配置快照()
        摘要 = await _控制台线程执行(
            QQ阅读.保存QQ阅读账号, 配置, 登录态, str(数据.get("account_id") or "")
        )
        try:
            摘要 = await asyncio.wait_for(QQ阅读.刷新QQ阅读账号资料(配置, 摘要["selected_id"]), timeout=20)
        except Exception as exc:
            logger.debug("QQ阅读新账号资料暂未更新：错误类型=%s", type(exc).__name__)
        return _QQ阅读JSON({"ok": True, "message": "QQ阅读账号已保存并设为当前账号", **摘要})
    except ValueError:
        return _控制台错误(400, "账号格式或账号身份无效")
    except Exception as exc:
        logger.warning("帮助控制台 QQ阅读账号保存失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "QQ阅读账号保存失败")


async def _QQ阅读账号操作(request: web.Request, 操作: str) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，账号操作未保存")
    数据 = await _读取请求JSON(request)
    账号ID = str((数据 or {}).get("account_id") or "").strip()
    if not 账号ID or len(账号ID) > 80:
        return _控制台错误(400, "请选择QQ阅读账号")
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        配置 = 获取控制台会话配置快照()
        if 操作 == "credential":
            凭据 = await _控制台线程执行(QQ阅读.读取QQ阅读账号凭据, 配置, 账号ID)
            if not 凭据:
                return _控制台错误(404, "QQ阅读账号不存在")
            return _QQ阅读JSON({"ok": True, "ywguid": 凭据["ywguid"], "ywkey": 凭据["ywkey"]})
        if 操作 == "refresh":
            摘要 = await asyncio.wait_for(QQ阅读.刷新QQ阅读账号资料(配置, 账号ID), timeout=25)
        elif 操作 == "enable":
            if not isinstance(数据.get("enabled"), bool):
                return _控制台错误(400, "账号开关参数无效")
            摘要 = await _控制台线程执行(QQ阅读.设置QQ阅读账号启用, 配置, 账号ID, 数据["enabled"])
        else:
            函数 = QQ阅读.删除QQ阅读账号 if 操作 == "delete" else QQ阅读.切换QQ阅读账号
            摘要 = await _控制台线程执行(函数, 配置, 账号ID)
        return _QQ阅读JSON({"ok": True, **摘要})
    except ValueError:
        return _控制台错误(409, "QQ阅读账号状态已变化或资料暂未获取，请刷新后重试")
    except Exception as exc:
        logger.warning("帮助控制台 QQ阅读账号操作失败：阶段=%s，错误类型=%s", 操作, type(exc).__name__)
        return _控制台错误(502 if 操作 == "refresh" else 409, "QQ阅读账号操作失败，请稍后重试")


async def _处理QQ阅读登录态删除(request: web.Request) -> web.Response:
    return await _QQ阅读账号操作(request, "delete")


async def _处理QQ阅读账号选择(request: web.Request) -> web.Response:
    return await _QQ阅读账号操作(request, "select")


async def _处理QQ阅读账号启用(request: web.Request) -> web.Response:
    return await _QQ阅读账号操作(request, "enable")


async def _处理QQ阅读账号刷新(request: web.Request) -> web.Response:
    return await _QQ阅读账号操作(request, "refresh")


async def _处理QQ阅读账号凭据(request: web.Request) -> web.Response:
    return await _QQ阅读账号操作(request, "credential")


def _QQ阅读短信仍有效(状态: dict[str, Any]) -> bool:
    return (
        not 状态.get("cancelled")
        and QQ阅读网页短信会话.get(状态["owner"]) is 状态
        and QQ阅读短信启动代次.get(状态["owner"]) == 状态["generation"]
        and 状态.get("expires_at", 0) > time.time()
        and 控制台会话.get(状态["session"], 0) > time.time()
        and hmac.compare_digest(状态["auth"], 控制台会话认证指纹)
        and hmac.compare_digest(状态["auth"], 获取控制台认证指纹(_当前作用域配置()))
    )


async def _移除QQ阅读网页短信会话(所有者: str, 预期: dict[str, Any] | None = None) -> None:
    状态 = QQ阅读网页短信会话.get(所有者)
    if not 状态 or (预期 is not None and 状态 is not 预期):
        return
    状态["cancelled"] = True
    QQ阅读网页短信会话.pop(所有者, None)
    if QQ阅读短信启动代次.get(所有者) == 状态["generation"]:
        QQ阅读短信启动代次.pop(所有者, None)
    try:
        await 状态["client"].关闭()
    except Exception as exc:
        logger.debug("QQ阅读短信会话关闭失败：错误类型=%s", type(exc).__name__)


async def _取消QQ阅读网页短信所有者(会话值: str) -> None:
    if 会话值:
        for 所有者 in _待取消扫码所有者(会话值):
            QQ阅读短信启动代次.pop(所有者, None)
            await _移除QQ阅读网页短信会话(所有者)


async def _取消全部QQ阅读网页短信() -> None:
    QQ阅读短信启动代次.clear()
    for 所有者 in list(QQ阅读网页短信会话):
        await _移除QQ阅读网页短信会话(所有者)


async def _处理QQ阅读短信预请求(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，账号未保存")
    数据 = await _读取请求JSON(request)
    手机号 = str((数据 or {}).get("phone") or "").strip()
    if not re.fullmatch(r"1[0-9]{10}", 手机号):
        return _控制台错误(400, "请输入有效的11位手机号")
    会话值 = _取得请求会话(request)
    所有者 = _扫码所有者(会话值)
    原状态 = QQ阅读网页短信会话.get(所有者)
    if 原状态 and _QQ阅读短信仍有效(原状态):
        if 原状态.get("busy"):
            return _控制台错误(409, "登录请求处理中，请稍候")
        if time.time() - 原状态.get("sent_at", 0) < 60:
            return _控制台错误(429, "验证码已发送，请稍后再试")
    代次 = secrets.token_urlsafe(16)
    QQ阅读短信启动代次[所有者] = 代次
    认证 = 控制台会话认证指纹
    配置 = 获取控制台会话配置快照()
    await _移除QQ阅读网页短信会话(所有者)
    if (QQ阅读短信启动代次.get(所有者) != 代次 or 控制台会话.get(会话值, 0) <= time.time()
            or not hmac.compare_digest(认证, 控制台会话认证指纹)):
        return _控制台错误(409, "登录会话已更新，请重新获取验证码")
    from 功能文件.管理功能.小说功能.小说 import QQ阅读

    状态 = {"owner": 所有者, "session": 会话值, "appid": 获取当前机器人AppID(), "auth": 认证, "generation": 代次,
            "config": 配置, "phone": 手机号,
            "expires_at": time.time() + 600, "busy": True, "sent_at": 0,
            "client": QQ阅读.QQ阅读手机号登录客户端()}
    QQ阅读网页短信会话[所有者] = 状态
    try:
        if not _QQ阅读短信仍有效(状态):
            return _控制台错误(409, "登录会话已更新，请重新获取验证码")
        结果 = await 状态["client"].预请求(手机号)
        if not _QQ阅读短信仍有效(状态):
            return _控制台错误(409, "登录会话已更新，请重新获取验证码")
        已发送 = 结果.get("sent") is True
        需要验证 = 结果.get("challenge_required") is True
        if 已发送:
            状态["sent_at"] = time.time()
        if not 已发送 and not 需要验证:
            raise RuntimeError("qqreader_sms_send_unconfirmed")
        return _QQ阅读JSON({"ok": True, "sent": 已发送, "challenge_required": 需要验证,
            "captcha_app_id": str(结果.get("captcha_app_id") or "") if 需要验证 else "",
            "message": "请完成安全验证" if 需要验证 else "验证码已发送"})
    except Exception as exc:
        logger.warning("QQ阅读短信预请求失败：错误类型=%s", type(exc).__name__)
        await _移除QQ阅读网页短信会话(所有者, 状态)
        return _控制台错误(502, "验证码请求失败，请稍后重试")
    finally:
        状态["busy"] = False


def _保存QQ阅读短信账号(状态: dict[str, Any], 登录态: dict[str, Any]) -> dict[str, Any] | None:
    # 在线程队列实际取得执行权时再校验，取消后的排队结果不写账号库。
    if not _QQ阅读短信仍有效(状态):
        return None
    from 功能文件.管理功能.小说功能.小说 import QQ阅读

    return QQ阅读.保存QQ阅读账号(状态["config"], 登录态)


async def _QQ阅读短信操作(request: web.Request, 操作: str) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    会话值 = _取得请求会话(request)
    所有者 = _扫码所有者(会话值)
    if 操作 == "cancel":
        await _取消QQ阅读网页短信所有者(会话值)
        return _QQ阅读JSON({"ok": True})
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，账号未保存")
    数据 = await _读取请求JSON(request)
    状态 = QQ阅读网页短信会话.get(所有者)
    if not 状态 or not _QQ阅读短信仍有效(状态):
        return _控制台错误(409, "请重新获取验证码")
    if str((数据 or {}).get("phone") or "").strip() != 状态["phone"]:
        return _控制台错误(400, "手机号已变化，请重新获取验证码")
    if 状态.get("busy"):
        return _控制台错误(409, "登录请求处理中，请稍候")
    if 操作 == "confirm":
        ticket = str((数据 or {}).get("ticket") or "").strip()
        randstr = str((数据 or {}).get("randstr") or "").strip()
        if not ticket or len(ticket) > 8192 or not randstr or len(randstr) > 512:
            return _控制台错误(400, "请完成安全验证")
        if time.time() - 状态.get("sent_at", 0) < 60:
            return _控制台错误(429, "验证码已发送，请稍后再试")
    else:
        code = str((数据 or {}).get("code") or "").strip()
        if not re.fullmatch(r"[0-9]{4,8}", code):
            return _控制台错误(400, "请输入有效的短信验证码")
        if not 状态.get("sent_at"):
            return _控制台错误(409, "请先获取验证码")
    状态["busy"] = True
    try:
        if 操作 == "confirm":
            结果 = await 状态["client"].确认发送(ticket, randstr)
            if not _QQ阅读短信仍有效(状态):
                return _控制台错误(409, "登录会话已更新，请重新获取验证码")
            已发送 = 结果.get("sent") is True
            需要验证 = 结果.get("challenge_required") is True
            if not 已发送 and not 需要验证:
                raise RuntimeError("qqreader_sms_send_unconfirmed")
            if 已发送:
                状态["sent_at"] = time.time()
            return _QQ阅读JSON({"ok": True, "sent": 已发送, "challenge_required": 需要验证,
                "captcha_app_id": str(结果.get("captcha_app_id") or "") if 需要验证 else "",
                "message": "请重新完成安全验证" if 需要验证 else "验证码已发送"})
        登录态 = await 状态["client"].验证登录(code)
        if not _QQ阅读短信仍有效(状态):
            return _控制台错误(409, "登录会话已更新，请重新获取验证码")
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        摘要 = await _控制台线程执行(_保存QQ阅读短信账号, 状态, 登录态)
        if 摘要 is None:
            return _控制台错误(409, "登录会话已更新，请重新获取验证码")
        try:
            摘要 = await asyncio.wait_for(QQ阅读.刷新QQ阅读账号资料(状态["config"], 摘要["selected_id"]), timeout=20)
        except Exception as exc:
            logger.debug("QQ阅读手机号账号资料暂未更新：错误类型=%s", type(exc).__name__)
        await _移除QQ阅读网页短信会话(所有者, 状态)
        return _QQ阅读JSON({"ok": True, "message": "账号已添加并设为当前账号", **摘要})
    except Exception as exc:
        logger.warning("QQ阅读短信操作失败：阶段=%s，错误类型=%s", 操作, type(exc).__name__)
        return _控制台错误(502, "验证码校验或登录失败，请检查后重试")
    finally:
        状态["busy"] = False


async def _处理QQ阅读短信确认下发(request: web.Request) -> web.Response:
    return await _QQ阅读短信操作(request, "confirm")


async def _处理QQ阅读短信登录(request: web.Request) -> web.Response:
    return await _QQ阅读短信操作(request, "login")


async def _处理QQ阅读短信取消(request: web.Request) -> web.Response:
    return await _QQ阅读短信操作(request, "cancel")


async def _移除QQ阅读网页扫码会话(scan_id: str, 所有者: str | None = None) -> bool:
    状态 = QQ阅读网页扫码会话.get(scan_id)
    if not 状态 or (所有者 is not None and 状态.get("owner") != 所有者):
        return False
    状态["cancelled"] = True
    if QQ阅读扫码启动代次.get(状态["owner"]) == 状态["generation"]:
        QQ阅读扫码启动代次.pop(状态["owner"], None)
    任务 = 状态.get("task")
    if isinstance(任务, asyncio.Task) and not 任务.done():
        任务.cancel()
        await asyncio.gather(任务, return_exceptions=True)
    try:
        await 状态["client"].关闭()
    except Exception as exc:
        logger.debug("QQ阅读扫码会话关闭失败：错误类型=%s", type(exc).__name__)
    QQ阅读网页扫码会话.pop(scan_id, None)
    return True


async def _取消QQ阅读网页扫码所有者(会话值: str, *, 取消启动: bool = True) -> None:
    if not 会话值:
        return
    所有者集合 = _待取消扫码所有者(会话值)
    if 取消启动:
        for 所有者 in 所有者集合:
            QQ阅读扫码启动代次.pop(所有者, None)
    for scan_id, 状态 in list(QQ阅读网页扫码会话.items()):
        if 状态.get("owner") in 所有者集合:
            await _移除QQ阅读网页扫码会话(scan_id, 状态.get("owner"))


async def _取消全部QQ阅读网页扫码() -> None:
    QQ阅读扫码启动代次.clear()
    for scan_id in list(QQ阅读网页扫码会话):
        await _移除QQ阅读网页扫码会话(scan_id)


def _QQ阅读扫码仍有效(状态: dict[str, Any]) -> bool:
    return (
        not 状态.get("cancelled")
        and 控制台会话.get(状态["session"], 0) > time.time()
        and hmac.compare_digest(状态["auth"], 控制台会话认证指纹)
        and hmac.compare_digest(状态["auth"], 获取控制台认证指纹(_当前作用域配置()))
        and QQ阅读扫码启动代次.get(状态["owner"]) == 状态["generation"]
    )


def _QQ阅读扫码响应(scan_id: str, 状态: dict[str, Any]) -> dict[str, Any]:
    当前状态 = str(状态.get("status") or "waiting")
    if 当前状态 == "waiting" and getattr(状态["client"], "status", "") == "scanned":
        当前状态 = "scanned"
    文案 = {
        "waiting": "请使用手机QQ扫码并确认登录QQ阅读。",
        "scanned": "二维码已扫描，请在手机QQ确认登录。",
        "saving": "登录成功，正在保存账号。",
        "success": "QQ阅读账号已添加并设为当前账号。",
        "expired": "二维码已过期，请重新获取。",
        "cancelled": "扫码已取消。",
        "error": "扫码登录失败，请重新获取二维码。",
    }
    return {"ok": True, "scan_id": scan_id, "status": 当前状态,
            "account_id": str(状态.get("account_id") or ""),
            "expires_in": max(0, int(状态["expires_at"] - time.time())),
            "message": 文案.get(当前状态, "请重新获取二维码。")}


def _记录QQ阅读扫码失败(客户端: Any, exc: BaseException, 阶段: str) -> None:
    """只记录固定阶段、已知错误标识和数字状态，不输出异常或远端原文。"""
    允许原因 = {
        "qqreader_qr_redirect_invalid", "qqreader_qr_closed", "qqreader_qr_response_large",
        "qqreader_qr_http_error", "qqreader_qr_redirect_limit", "qqreader_qr_callback_invalid",
        "qqreader_qr_session_started", "qqreader_qr_entry_missing", "qqreader_qr_entry_invalid",
        "qqreader_qr_oauth_entry_invalid", "qqreader_qr_oauth_app_invalid",
        "qqreader_qr_oauth_callback_invalid", "qqreader_qr_provider_changed",
        "qqreader_qr_provider_fields_missing", "qqreader_qr_image_invalid",
        "qqreader_qr_oauth_cookie_missing", "qqreader_qr_oauth_authorize_failed",
        "qqreader_qr_reader_callback_failed", "qqreader_qr_reader_callback_invalid",
        "qqreader_qr_ticket_invalid", "qqreader_qr_ticket_failed",
        "qqreader_qr_reader_credentials_missing", "qqreader_qr_not_started",
        "qqreader_qr_authorization_required",
    }
    原因 = "unexpected_error"
    if isinstance(exc, RuntimeError) and len(exc.args) == 1:
        候选原因 = exc.args[0]
        if type(候选原因) is str and 候选原因 in 允许原因:
            原因 = 候选原因
    if 阶段 not in {"qr_start", "wait_login", "save_account", "refresh_profile"}:
        阶段 = "unknown"
    客户端阶段 = getattr(客户端, "诊断阶段", "unknown")
    if type(客户端阶段) is not str or 客户端阶段 not in {
        "created", "login_page", "qq_entry", "oauth_page", "ptlogin_page", "qr_image",
        "poll", "login_jump", "oauth_authorize", "reader_callback", "ticket_exchange",
        "credentials", "confirmed", "closed",
    }:
        客户端阶段 = "unknown"
    HTTP状态 = getattr(客户端, "HTTP状态", None)
    if type(HTTP状态) is not int or not 100 <= HTTP状态 <= 599:
        HTTP状态 = "none"
    状态码 = []
    for 字段 in ("轮询状态", "业务码"):
        值 = getattr(客户端, 字段, None)
        if type(值) is int and -10**12 < 值 < 10**12:
            值 = str(值)
        状态码.append(值 if type(值) is str and re.fullmatch(r"-?[0-9]{1,12}", 值) else "none")
    跳转主机 = getattr(客户端, "跳转主机", None)
    if type(跳转主机) is not str or 跳转主机 not in {
        "login.book.qq.com", "book.qq.com", "passport.yuewen.com", "ptlogin.yuewen.com",
        "ptlogin.qidian.com", "passport.qidian.com", "graph.qq.com", "xui.ptlogin2.qq.com",
        "ssl.ptlogin2.qq.com", "ptlogin2.qq.com", "ui.ptlogin2.qq.com", "ssl.ptlogin2.graph.qq.com",
    }:
        跳转主机 = "unknown"
    跳转协议 = getattr(客户端, "跳转协议", None)
    if type(跳转协议) is not str or 跳转协议 not in {"https", "http"}:
        跳转协议 = "unknown"
    日志 = logger.debug if 阶段 == "refresh_profile" else logger.warning
    日志(
        "帮助控制台 QQ阅读扫码失败：阶段=%s，客户端阶段=%s，原因=%s，HTTP状态=%s，轮询码=%s，业务码=%s，跳转主机=%s，跳转协议=%s，错误类型=%s",
        阶段, 客户端阶段, 原因, HTTP状态, *状态码, 跳转主机, 跳转协议, type(exc).__name__,
    )


async def _运行QQ阅读网页扫码(scan_id: str) -> None:
    状态 = QQ阅读网页扫码会话[scan_id]
    阶段 = "wait_login"
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        登录态 = await 状态["client"].等待登录并获取登录态(timeout=300, interval=2)
        if not _QQ阅读扫码仍有效(状态):
            状态["status"] = "cancelled"
            return
        状态["status"] = "saving"
        状态["updated_at"] = time.time()
        阶段 = "save_account"
        摘要 = await _控制台线程执行(QQ阅读.保存QQ阅读账号, 状态["config"], 登录态)
        状态["account_id"] = 摘要["selected_id"]
        阶段 = "refresh_profile"
        try:
            await asyncio.wait_for(QQ阅读.刷新QQ阅读账号资料(状态["config"], 摘要["selected_id"]), timeout=20)
        except Exception as exc:
            _记录QQ阅读扫码失败(状态["client"], exc, 阶段)
        状态["status"] = "success"
    except asyncio.CancelledError:
        状态["status"] = "cancelled"
        raise
    except TimeoutError:
        状态["status"] = "expired"
    except Exception as exc:
        状态["status"] = "error"
        _记录QQ阅读扫码失败(状态["client"], exc, 阶段)
    finally:
        状态["updated_at"] = time.time()
        try:
            await 状态["client"].关闭()
        except Exception as exc:
            logger.debug("QQ阅读扫码会话关闭失败：错误类型=%s", type(exc).__name__)


async def _处理QQ阅读网页扫码开始(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，扫码账号未保存")
    from 功能文件.管理功能.小说功能.小说 import QQ阅读

    会话值 = _取得请求会话(request)
    所有者 = _扫码所有者(会话值)
    代次 = secrets.token_urlsafe(16)
    QQ阅读扫码启动代次[所有者] = 代次
    await _取消QQ阅读网页扫码所有者(会话值, 取消启动=False)
    状态: dict[str, Any] = {
        "owner": 所有者, "session": 会话值, "appid": 获取当前机器人AppID(), "generation": 代次,
        "auth": 控制台会话认证指纹, "config": 获取控制台会话配置快照(),
        "client": QQ阅读.QQ阅读扫码登录客户端(), "status": "waiting",
        "updated_at": time.time(), "expires_at": time.time() + 300,
    }
    客户端 = 状态["client"]
    已登记 = False
    try:
        if not _QQ阅读扫码仍有效(状态):
            return _控制台错误(409, "扫码会话已更新")
        图片 = await 客户端.获取登录二维码()
        if not _QQ阅读扫码仍有效(状态):
            return _控制台错误(409, "扫码会话已更新")
        scan_id = secrets.token_urlsafe(24)
        QQ阅读网页扫码会话[scan_id] = 状态
        状态["task"] = asyncio.create_task(_运行QQ阅读网页扫码(scan_id))
        已登记 = True
        return _QQ阅读JSON({**_QQ阅读扫码响应(scan_id, 状态),
            "qr_image": "data:image/png;base64," + base64.b64encode(图片).decode("ascii")})
    except Exception as exc:
        _记录QQ阅读扫码失败(客户端, exc, "qr_start")
        return _控制台错误(502, "QQ阅读二维码获取失败，请稍后重试")
    finally:
        if not 已登记:
            try:
                await 客户端.关闭()
            except Exception:
                pass


async def _处理QQ阅读网页扫码状态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    scan_id = str(request.query.get("scan_id") or "")
    状态 = QQ阅读网页扫码会话.get(scan_id)
    所有者 = _扫码所有者(_取得请求会话(request))
    if not 状态 or 状态.get("owner") != 所有者:
        return _控制台错误(404, "扫码会话已结束，请重新获取二维码")
    if not _QQ阅读扫码仍有效(状态):
        await _移除QQ阅读网页扫码会话(scan_id, 所有者)
        return _控制台错误(404, "扫码会话已结束，请重新获取二维码")
    return _QQ阅读JSON(_QQ阅读扫码响应(scan_id, 状态))


async def _处理QQ阅读网页扫码取消(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    scan_id = str((数据 or {}).get("scan_id") or "")
    会话值 = _取得请求会话(request)
    所有者 = _扫码所有者(会话值)
    if not scan_id:
        await _取消QQ阅读网页扫码所有者(会话值)
    else:
        await _移除QQ阅读网页扫码会话(scan_id, 所有者)
    return _QQ阅读JSON({"ok": True, "message": "扫码会话已结束"})


def _晋江JSON(数据: dict[str, Any]) -> web.Response:
    return web.json_response(数据, headers={
        "Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer",
    })


def _晋江操作上下文(request: web.Request) -> dict[str, Any]:
    return {
        "session": _取得请求会话(request), "auth": 控制台会话认证指纹,
        "appid": 获取当前机器人AppID(), "config": 获取控制台会话配置快照(),
    }


def _晋江操作仍有效(状态: dict[str, Any]) -> bool:
    return (
        bool(状态.get("appid")) and not 状态.get("cancelled")
        and 控制台会话.get(状态["session"], 0) > time.time()
        and 状态["appid"] == 获取当前机器人AppID(状态["config"])
        and hmac.compare_digest(状态["auth"], 控制台会话认证指纹)
        and hmac.compare_digest(状态["auth"], 获取控制台认证指纹(_当前作用域配置()))
    )


async def _晋江受保护写入(函数: Any, *参数: Any, **关键字参数: Any) -> Any:
    """取消时等已接受的写库结束；存储层在锁内及提交前检查授权代次。"""
    async def 执行写入() -> tuple[bool, Any]:
        try:
            return True, await _控制台线程执行(函数, *参数, **关键字参数)
        except Exception as exc:
            # 被取消的 shield 在部分 Python 版本会打印内部异常；统一由请求层受控处理。
            return False, exc

    任务 = asyncio.create_task(执行写入())
    try:
        成功, 结果 = await asyncio.shield(任务)
    except asyncio.CancelledError:
        # 注销、替换扫码和停止服务可能同时取消同一个任务，重复取消也不得遗留写线程。
        while not 任务.done():
            try:
                await asyncio.shield(任务)
            except asyncio.CancelledError:
                continue
        raise
    if not 成功:
        raise 结果
    return 结果


async def _刷新晋江网页账号资料(状态: dict[str, Any], 账号ID: str) -> dict[str, Any]:
    from 功能文件.管理功能.小说功能.功能 import 晋江账号
    from 功能文件.管理功能.小说功能.小说 import 晋江小说

    凭据 = await _控制台线程执行(晋江账号.读取晋江账号凭据, 状态["config"], 账号ID)
    if not 凭据 or not _晋江操作仍有效(状态):
        raise PermissionError("账号状态已变化")
    资料 = await asyncio.wait_for(晋江小说.查询晋江账号资料(凭据), timeout=25)
    if not _晋江操作仍有效(状态):
        raise PermissionError("会话已结束")
    await _晋江受保护写入(
        晋江账号.合并晋江账号资料, 状态["config"], 凭据, 资料,
        提交前校验=lambda: _晋江操作仍有效(状态),
    )
    return await _控制台线程执行(晋江账号.读取晋江账号列表, 状态["config"])


async def _处理晋江登录态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    状态 = _晋江操作上下文(request)
    try:
        from 功能文件.管理功能.小说功能.功能 import 晋江账号

        摘要 = await _控制台线程执行(晋江账号.读取晋江账号列表, 状态["config"])
        if not _晋江操作仍有效(状态):
            return _控制台错误(401, "请重新登录控制台")
        return _晋江JSON({"ok": True, "editable": _数据库会话可用(状态["config"]), **摘要})
    except Exception as exc:
        logger.warning("帮助控制台 晋江账号读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "晋江账号读取失败")


async def _处理晋江登录态保存(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，账号未保存")
    数据 = await _读取请求JSON(request)
    if not 数据 or not isinstance(数据.get("select", True), bool):
        return _控制台错误(400, "账号参数无效")
    if not isinstance(数据.get("token"), str) or not isinstance(数据.get("readerId"), (str, int)) or isinstance(数据.get("readerId"), bool):
        return _控制台错误(400, "晋江登录态格式无效")
    状态 = _晋江操作上下文(request)
    try:
        from 功能文件.管理功能.小说功能.功能 import 晋江账号

        摘要 = await _晋江受保护写入(
            晋江账号.保存晋江账号, 状态["config"],
            {"token": 数据["token"], "readerId": 数据["readerId"]},
            str(数据.get("account_id") or ""), 数据.get("select", True),
            提交前校验=lambda: _晋江操作仍有效(状态),
        )
        if not _晋江操作仍有效(状态):
            return _控制台错误(401, "请重新登录控制台")
        return _晋江JSON({"ok": True, "editable": True, "message": "晋江账号已保存", **摘要})
    except PermissionError:
        return _控制台错误(401, "请重新登录控制台")
    except ValueError:
        return _控制台错误(400, "晋江账号格式或身份无效")
    except Exception as exc:
        logger.warning("帮助控制台 晋江账号保存失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "晋江账号保存失败")


async def _晋江账号操作(request: web.Request, 操作: str) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，账号操作未保存")
    数据 = await _读取请求JSON(request)
    账号ID = str((数据 or {}).get("account_id") or "").strip()
    if not 账号ID or len(账号ID) > 80:
        return _控制台错误(400, "请选择晋江账号")
    状态 = _晋江操作上下文(request)
    try:
        from 功能文件.管理功能.小说功能.功能 import 晋江账号

        if 操作 == "refresh":
            摘要 = await _刷新晋江网页账号资料(状态, 账号ID)
        elif 操作 == "enable":
            if not isinstance(数据.get("enabled"), bool):
                return _控制台错误(400, "账号开关参数无效")
            摘要 = await _晋江受保护写入(
                晋江账号.设置晋江账号启用, 状态["config"], 账号ID, 数据["enabled"],
                提交前校验=lambda: _晋江操作仍有效(状态),
            )
        else:
            函数 = 晋江账号.删除晋江账号 if 操作 == "delete" else 晋江账号.切换晋江账号
            摘要 = await _晋江受保护写入(
                函数, 状态["config"], 账号ID, 提交前校验=lambda: _晋江操作仍有效(状态),
            )
        if not _晋江操作仍有效(状态):
            return _控制台错误(401, "请重新登录控制台")
        return _晋江JSON({"ok": True, "editable": True, **摘要})
    except PermissionError:
        return _控制台错误(401, "请重新登录控制台")
    except ValueError:
        return _控制台错误(409, "晋江账号状态已变化，请刷新后重试")
    except Exception as exc:
        logger.warning("帮助控制台 晋江账号操作失败：阶段=%s，错误类型=%s", 操作, type(exc).__name__)
        return _控制台错误(502 if 操作 == "refresh" else 409, "晋江账号操作失败，请稍后重试")


async def _处理晋江登录态删除(request: web.Request) -> web.Response:
    return await _晋江账号操作(request, "delete")


async def _处理晋江账号选择(request: web.Request) -> web.Response:
    return await _晋江账号操作(request, "select")


async def _处理晋江账号启用(request: web.Request) -> web.Response:
    return await _晋江账号操作(request, "enable")


async def _处理晋江账号刷新(request: web.Request) -> web.Response:
    return await _晋江账号操作(request, "refresh")


def _晋江扫码仍有效(状态: dict[str, Any]) -> bool:
    return _晋江操作仍有效(状态) and 晋江扫码启动代次.get(状态["owner"]) == 状态["generation"]


async def _移除晋江网页扫码会话(scan_id: str, 所有者: str | None = None) -> bool:
    状态 = 晋江网页扫码会话.get(scan_id)
    if not 状态 or (所有者 is not None and 状态.get("owner") != 所有者):
        return False
    状态["cancelled"] = True
    if 晋江扫码启动代次.get(状态["owner"]) == 状态["generation"]:
        晋江扫码启动代次.pop(状态["owner"], None)
    任务 = 状态.get("task")
    if isinstance(任务, asyncio.Task) and not 任务.done():
        任务.cancel()
        await asyncio.gather(任务, return_exceptions=True)
    try:
        await 状态["client"].close()
    except Exception as exc:
        logger.debug("晋江扫码会话关闭失败：错误类型=%s", type(exc).__name__)
    if 晋江网页扫码会话.get(scan_id) is 状态:
        晋江网页扫码会话.pop(scan_id, None)
    return True


async def _取消晋江网页扫码所有者(会话值: str, *, 取消启动: bool = True) -> None:
    if not 会话值:
        return
    所有者集合 = _待取消扫码所有者(会话值)
    if 取消启动:
        for 所有者 in 所有者集合:
            晋江扫码启动代次.pop(所有者, None)
    for scan_id, 状态 in list(晋江网页扫码会话.items()):
        if 状态.get("owner") in 所有者集合:
            await _移除晋江网页扫码会话(scan_id, 状态.get("owner"))


async def _取消全部晋江网页扫码() -> None:
    晋江扫码启动代次.clear()
    for scan_id in list(晋江网页扫码会话):
        await _移除晋江网页扫码会话(scan_id)


def _晋江扫码响应(scan_id: str, 状态: dict[str, Any]) -> dict[str, Any]:
    当前状态 = str(状态.get("status") or "waiting")
    文案 = {
        "waiting": "请使用晋江小说阅读App扫码并确认登录。",
        "saving": "登录成功，正在保存账号。", "success": "晋江账号已添加并设为当前账号。",
        "expired": "二维码已过期，请重新获取。", "cancelled": "扫码已取消。",
        "error": "扫码登录失败，请重新获取二维码。",
    }
    return {
        "ok": True, "scan_id": scan_id, "status": 当前状态,
        "account_id": str(状态.get("account_id") or ""),
        "expires_at": 状态["expires_at"],
        "expires_in": max(0, int(状态["expires_at"] - time.time())),
        "message": 文案.get(当前状态, 文案["error"]),
    }


def _记录晋江扫码失败(exc: BaseException, 阶段: str) -> None:
    if 阶段 not in {"qr_start", "wait_login", "save_account", "refresh_profile"}:
        阶段 = "unknown"
    logger.warning("帮助控制台 晋江扫码失败：阶段=%s，错误类型=%s", 阶段, type(exc).__name__)


def _记录晋江扫码状态错误(结果: dict[str, Any]) -> None:
    允许原因 = {
        "timeout", "network_error", "http_error", "response_too_large", "invalid_encoding",
        "invalid_envelope", "invalid_envelope_json", "invalid_response", "decrypt_failed",
        "response_too_deep", "invalid_encrypt_fields", "unsupported_encryption",
        "missing_encrypt_field", "business_error", "unknown_login_state",
    }
    原因 = 结果.get("reason")
    if type(原因) is not str or 原因 not in 允许原因:
        原因 = "unknown_login_state"
    业务码 = 结果.get("code")
    if type(业务码) is int:
        业务码 = str(业务码)
    if type(业务码) is not str or not re.fullmatch(r"-?[0-9]{1,12}", 业务码):
        业务码 = "none"
    logger.warning("帮助控制台 晋江扫码失败：阶段=wait_login，原因=%s，业务码=%s", 原因, 业务码)


async def _运行晋江网页扫码(scan_id: str) -> None:
    状态 = 晋江网页扫码会话[scan_id]
    阶段 = "wait_login"
    try:
        from 功能文件.管理功能.小说功能.功能 import 晋江账号

        while _晋江扫码仍有效(状态):
            if 状态["expires_at"] <= time.time():
                状态["status"] = "expired"
                return
            结果 = await 状态["client"].poll()
            if not _晋江扫码仍有效(状态):
                状态["status"] = "cancelled"
                return
            当前状态 = 结果.get("status")
            if 当前状态 == "waiting":
                await asyncio.sleep(2)
                continue
            if 当前状态 != "success":
                状态["status"] = "expired" if 当前状态 == "expired" else "error"
                if 当前状态 != "expired":
                    _记录晋江扫码状态错误(结果)
                return
            登录态 = 结果.get("credentials")
            if not isinstance(登录态, dict):
                状态["status"] = "error"
                return
            状态["status"] = "saving"
            状态["updated_at"] = time.time()
            阶段 = "save_account"
            try:
                摘要 = await _晋江受保护写入(
                    晋江账号.保存晋江账号, 状态["config"], 登录态,
                    提交前校验=lambda: _晋江扫码仍有效(状态),
                )
            finally:
                登录态.clear()
            if not _晋江扫码仍有效(状态):
                状态["status"] = "cancelled"
                return
            状态["account_id"] = str(摘要.get("selected_id") or "")
            状态["status"] = "success"
            return
        状态["status"] = "cancelled"
    except asyncio.CancelledError:
        状态["status"] = "cancelled"
        raise
    except PermissionError:
        状态["status"] = "cancelled"
    except TimeoutError:
        状态["status"] = "expired"
    except Exception as exc:
        状态["status"] = "error"
        _记录晋江扫码失败(exc, 阶段)
    finally:
        状态["updated_at"] = time.time()
        try:
            await 状态["client"].close()
        except Exception as exc:
            logger.debug("晋江扫码会话关闭失败：错误类型=%s", type(exc).__name__)


async def _处理晋江网页扫码开始(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    if not _数据库会话可用():
        return _控制台错误(409, "数据库未配置，扫码账号未保存")
    from 功能文件.管理功能.小说功能.小说 import 晋江小说

    状态 = _晋江操作上下文(request)
    所有者 = _扫码所有者(状态["session"])
    代次 = secrets.token_urlsafe(16)
    晋江扫码启动代次[所有者] = 代次
    await _取消晋江网页扫码所有者(状态["session"], 取消启动=False)
    状态.update({
        "owner": 所有者, "generation": 代次, "client": 晋江小说.晋江扫码登录客户端(),
        "status": "waiting", "updated_at": time.time(), "expires_at": time.time() + 60,
    })
    已登记 = False
    try:
        if not _晋江扫码仍有效(状态):
            return _控制台错误(409, "扫码会话已更新")
        结果 = await asyncio.wait_for(状态["client"].start(), timeout=30)
        if not _晋江扫码仍有效(状态):
            return _控制台错误(409, "扫码会话已更新")
        图片 = 结果.get("qr_image")
        if not isinstance(图片, str) or not re.fullmatch(r"data:image/png;base64,[A-Za-z0-9+/=]{1,1048576}", 图片):
            return _控制台错误(502, "晋江二维码获取失败，请稍后重试")
        状态["expires_at"] = min(time.time() + 60, float(结果.get("expires_at") or time.time() + 60))
        scan_id = secrets.token_urlsafe(24)
        晋江网页扫码会话[scan_id] = 状态
        状态["task"] = asyncio.create_task(_运行晋江网页扫码(scan_id))
        已登记 = True
        return _晋江JSON({**_晋江扫码响应(scan_id, 状态), "qr_image": 图片})
    except Exception as exc:
        _记录晋江扫码失败(exc, "qr_start")
        return _控制台错误(502, "晋江二维码获取失败，请稍后重试")
    finally:
        if not 已登记:
            try:
                await 状态["client"].close()
            except Exception:
                pass


async def _处理晋江网页扫码状态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    scan_id = str(request.query.get("scan_id") or "")
    状态 = 晋江网页扫码会话.get(scan_id)
    所有者 = _扫码所有者(_取得请求会话(request))
    if not 状态 or 状态.get("owner") != 所有者:
        return _控制台错误(404, "扫码会话已结束，请重新获取二维码")
    if not _晋江扫码仍有效(状态):
        await _移除晋江网页扫码会话(scan_id, 所有者)
        return _控制台错误(404, "扫码会话已结束，请重新获取二维码")
    return _晋江JSON(_晋江扫码响应(scan_id, 状态))


async def _处理晋江网页扫码取消(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    scan_id = str((数据 or {}).get("scan_id") or "")
    会话值 = _取得请求会话(request)
    所有者 = _扫码所有者(会话值)
    if scan_id:
        await _移除晋江网页扫码会话(scan_id, 所有者)
    else:
        await _取消晋江网页扫码所有者(会话值)
    return _晋江JSON({"ok": True, "message": "扫码会话已结束"})


async def _处理消息聊天列表(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    过滤 = str((数据 or {}).get("filter") or "all")
    搜索 = str((数据 or {}).get("search") or "")
    try:
        页码 = int((数据 or {}).get("page") or 1)
    except (TypeError, ValueError):
        页码 = 1
    try:
        原始每页 = int((数据 or {}).get("page_size", 50))
        每页 = 0 if 原始每页 <= 0 else min(100, 原始每页)
    except (TypeError, ValueError):
        每页 = 50
    appid = str((数据 or {}).get("appid") or "").strip() if "appid" in (数据 or {}) else None
    if appid is not None and appid and not re.fullmatch(r"[0-9]{4,32}", appid):
        return _控制台错误(400, "会话参数无效")
    页码 = max(1, 页码)
    缓存键 = (过滤, 搜索, 页码, 每页, appid)
    当前时间 = time.monotonic()
    缓存项 = 消息列表缓存.get(缓存键)
    if 缓存项:
        缓存时间, 缓存结果 = 缓存项
        if 当前时间 - 缓存时间 >= 消息列表缓存秒数 and 缓存键 not in 消息列表后台刷新:
            消息列表后台刷新.add(缓存键)
            asyncio.create_task(_后台刷新消息列表(缓存键, 过滤, 搜索, 页码, 每页, 消息列表缓存版本, appid))
        return web.json_response(
            {"ok": True, **缓存结果},
            headers={"Cache-Control": "no-store"},
        )
    try:
        锁 = 消息列表缓存锁.setdefault(缓存键, asyncio.Lock())
        async with 锁:
            缓存项 = 消息列表缓存.get(缓存键)
            if 缓存项:
                结果 = 缓存项[1]
            else:
                缓存版本 = 消息列表缓存版本
                结果 = await _构建消息列表(过滤, 搜索, 页码, 每页, appid)
                _写入消息列表缓存(缓存键, 结果, 缓存版本)
        return web.json_response({"ok": True, **结果}, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台消息列表读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "消息列表暂时不可用")
    finally:
        _清理消息列表缓存锁()


async def _合并查询消息历史(
    会话标识: str, 类型: str, before_date: str, limit: int, before_id: int,
    appid: str = "", 引用标识: str = "", after_id: int = 0, 历史窗口: bool = False,
) -> dict[str, Any] | None:
    """相同历史请求共享正在执行的查询，完成后立即释放，不缓存历史结果。"""
    from 功能文件.管理功能.基础功能 import 消息记录

    # 网页发送/撤回等写操作会推进版本，新请求不能加入写操作前的查询。
    键 = (会话标识, 类型, before_date, limit, before_id, appid, 引用标识, after_id, 历史窗口, 消息列表缓存版本)
    任务 = 消息历史查询任务.get(键)
    if 任务 is None or 任务.done():
        查询 = (
            _控制台线程执行(消息记录.获取引用定位历史, 会话标识, 类型, appid, limit, 引用标识, before_id, after_id)
            if 历史窗口 else
            _控制台线程执行(消息记录.获取消息历史, 会话标识, 类型, before_date, limit, before_id, appid)
        )
        任务 = asyncio.create_task(
            查询,
            name="控制台历史查询",
        )
        消息历史查询任务[键] = 任务
        控制台后台任务.add(任务)

        def 查询结束(已完成: asyncio.Task[Any]) -> None:
            if 消息历史查询任务.get(键) is 已完成:
                消息历史查询任务.pop(键, None)
            控制台后台任务.discard(已完成)
            # 所有网页请求取消后仍要取走异常，避免留下无人接收的任务异常。
            if not 已完成.cancelled():
                已完成.exception()

        任务.add_done_callback(查询结束)
    # 切换群聊取消某个 HTTP 请求时，其他正在等待的标签页继续使用同一查询。
    return await asyncio.shield(任务)


async def _处理消息历史(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    类型 = str((数据 or {}).get("chat_type") or "group")
    before_date = str((数据 or {}).get("before_date") or "")
    appid = str((数据 or {}).get("appid") or "").strip()
    引用标识 = str((数据 or {}).get("locate_reference_id") or "").strip()
    历史窗口 = bool(引用标识 or (数据 or {}).get("history_window") is True)
    try:
        before_id = max(0, int((数据 or {}).get("before_id") or 0))
    except (TypeError, ValueError):
        before_id = 0
    try:
        after_id = max(0, int((数据 or {}).get("after_id") or 0))
    except (TypeError, ValueError):
        return _控制台错误(400, "会话参数无效")
    try:
        limit = max(1, min(100, int((数据 or {}).get("limit") or 100)))
    except (TypeError, ValueError):
        limit = 100
    if not 会话标识 or len(会话标识) > 200 or 类型 not in {"group", "user"} or (appid and not re.fullmatch(r"[0-9]{4,32}", appid)):
        return _控制台错误(400, "会话参数无效")
    if (
        历史窗口 and (
            类型 not in {"group", "user"} or len(appid) > 64 or len(引用标识) > 512
            or any(ord(字符) < 32 or 127 <= ord(字符) <= 159 for 字符 in 引用标识)
            or (before_id and after_id) or (引用标识 and (before_id or after_id))
            or (not 引用标识 and not before_id and not after_id)
        )
    ) or (after_id and not 历史窗口):
        return _控制台错误(400, "会话参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await _合并查询消息历史(
            会话标识, 类型, before_date, limit, before_id, appid, 引用标识, after_id, 历史窗口
        )
        if 结果 is None:
            return _控制台错误(404, "原消息未保存或已删除")
        try:
            from 功能文件.管理功能.网盘功能 import 夸克媒体归档

            for 消息项 in 结果.get("messages") or []:
                if not isinstance(消息项, dict):
                    continue
                消息项["media"] = 夸克媒体归档.构造网页媒体字段(
                    消息项.get("media"),
                    会话标识,
                    类型,
                    str(消息项.get("message_id") or ""),
                    appid=str(消息项.get("appid") or ""),
                )
                消息项["media"] = 消息记录.清理网页媒体内部字段(消息项["media"])
        except Exception as exc:
            logger.debug("帮助控制台历史图片代理地址生成失败：错误类型=%s", type(exc).__name__)
            for 消息项 in 结果.get("messages") or []:
                if isinstance(消息项, dict) and isinstance(消息项.get("media"), dict):
                    消息项["media"] = 消息记录.清理网页媒体内部字段(消息项["media"])
        try:
            消息记录.安排待处理群信息刷新()
        except Exception:
            pass
        return web.json_response({"ok": True, **结果}, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台消息历史读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "消息历史暂时不可用")


async def _处理消息事件(request: web.Request) -> web.StreamResponse:
    """向消息记录页推送实时事件，避免等待固定轮询周期。"""
    if not _请求已授权(request):
        return web.Response(status=401, text="Unauthorized")
    当前任务: asyncio.Task[Any] | None = None
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        队列 = 消息记录.订阅消息事件()
        if 队列 is None:
            return web.Response(status=503, text="Event stream unavailable")
        响应 = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-store",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        当前任务 = asyncio.current_task()
        if 当前任务 is not None:
            实时连接任务.add(当前任务)
        await 响应.prepare(request)
        await 响应.write(b'data: {"type":"ready","data":{}}\n\n')
        try:
            while True:
                try:
                    事件 = await asyncio.wait_for(队列.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    await 响应.write(b": keepalive\n\n")
                    continue
                if not _实时事件属于机器人(事件, 获取当前机器人AppID()):
                    continue
                文本 = json.dumps(事件, ensure_ascii=False, separators=(",", ":"), default=str)
                await 响应.write(f"data: {文本}\n\n".encode("utf-8"))
        except asyncio.CancelledError:
            raise
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:
            logger.debug("帮助控制台消息事件连接结束：错误类型=%s", type(exc).__name__)
        finally:
            消息记录.取消消息事件订阅(队列)
            if 当前任务 is not None:
                实时连接任务.discard(当前任务)
        return 响应
    except asyncio.CancelledError:
        if 当前任务 is not None:
            实时连接任务.discard(当前任务)
        raise
    except Exception as exc:
        if 当前任务 is not None:
            实时连接任务.discard(当前任务)
        logger.debug("帮助控制台消息事件启动失败：错误类型=%s", type(exc).__name__)
        return web.Response(status=503, text="Event stream unavailable")


def _实时事件属于机器人(事件: Any, appid: str) -> bool:
    数据 = 事件.get("data") if isinstance(事件, dict) else None
    return bool(appid) and isinstance(数据, dict) and str(数据.get("appid") or "").strip() == appid


async def _处理消息WebSocket(request: web.Request) -> web.StreamResponse:
    """消息记录实时主通道；浏览器断线时由前端降级到 SSE。"""
    if not _请求已授权(request):
        return web.Response(status=401, text="Unauthorized")
    if not _请求来自同源(request):
        return web.Response(status=403, text="Forbidden")
    当前任务: asyncio.Task[Any] | None = None
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        队列 = 消息记录.订阅消息事件()
        if 队列 is None:
            return web.Response(status=503, text="WebSocket unavailable")
        响应 = web.WebSocketResponse(heartbeat=30.0, compress=False)
        当前任务 = asyncio.current_task()
        if 当前任务 is not None:
            实时连接任务.add(当前任务)
        接收任务: asyncio.Task[Any] | None = None
        事件任务: asyncio.Task[Any] | None = None
        try:
            await 响应.prepare(request)
            await 响应.send_json({"type": "ready", "data": {}}, dumps=lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str))
            接收任务 = asyncio.create_task(响应.receive())
            事件任务 = asyncio.create_task(队列.get())
            while not 响应.closed:
                完成任务, _ = await asyncio.wait(
                    {接收任务, 事件任务},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if 接收任务 in 完成任务:
                    消息 = 接收任务.result()
                    if 消息.type in {web.WSMsgType.CLOSE, web.WSMsgType.CLOSED, web.WSMsgType.ERROR}:
                        break
                    接收任务 = asyncio.create_task(响应.receive())
                if 事件任务 in 完成任务:
                    事件 = 事件任务.result()
                    if _实时事件属于机器人(事件, 获取当前机器人AppID()):
                        await 响应.send_json(事件, dumps=lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str))
                    事件任务 = asyncio.create_task(队列.get())
        except asyncio.CancelledError:
            raise
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:
            logger.debug("帮助控制台消息 WebSocket 连接结束：错误类型=%s", type(exc).__name__)
        finally:
            待取消任务 = []
            for 任务 in (接收任务, 事件任务):
                if 任务 is not None and not 任务.done():
                    任务.cancel()
                    待取消任务.append(任务)
            if 待取消任务:
                await asyncio.gather(*待取消任务, return_exceptions=True)
            消息记录.取消消息事件订阅(队列)
            if not 响应.closed:
                await 响应.close()
            if 当前任务 is not None:
                实时连接任务.discard(当前任务)
        return 响应
    except asyncio.CancelledError:
        if 当前任务 is not None:
            实时连接任务.discard(当前任务)
        raise
    except Exception as exc:
        if 当前任务 is not None:
            实时连接任务.discard(当前任务)
        logger.debug("帮助控制台消息 WebSocket 启动失败：错误类型=%s", type(exc).__name__)
        return web.Response(status=503, text="WebSocket unavailable")


async def _处理消息发送(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    临时媒体路径: Path | None = None
    try:
        数据, 临时媒体路径 = await _读取消息发送请求(request)
        if not 数据:
            return _控制台错误(400, "请求参数无效")
        会话标识 = str(数据.get("chat_id") or "").strip()
        会话类型 = str(数据.get("chat_type") or "")
        消息类型 = str(数据.get("msg_type") or "text")
        内容 = str(数据.get("content") or "")
        if not 会话标识 or len(会话标识) > 200:
            return _控制台错误(400, "会话参数无效")
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await 消息记录.发送消息(
            会话标识,
            消息类型,
            内容,
            str(数据.get("appid") or ""),
            会话类型=会话类型,
            消息ID=str(数据.get("msg_id") or ""),
            发送方式=str(数据.get("send_mode") or "default"),
             自定义ID=str(数据.get("custom_id") or ""),
             引用消息ID=str(数据.get("quote_message_id") or 数据.get("message_reference_id") or ""),
             引用消息REFIDX=str(数据.get("quote_message_refidx") or ""),
             图片路径=str(数据.get("image") or ""),
             图片文件名=str(数据.get("image_name") or ""),
             图片数据=str(数据.get("image_data") or ""),
             图片URL=str(数据.get("image_url") or ""),
             图片前文本=str(数据.get("image_before") or ""),
             图片后文本=str(数据.get("image_after") or ""),
             图片占位标记=str(数据.get("image_marker") or "\ufffc"),
             媒体路径=str(数据.get("media") or ""),
             媒体URL=str(数据.get("media_url") or ""),
             媒体数据=str(数据.get("media_data") or ""),
             媒体文件名=str(数据.get("media_name") or ""),
             媒体内容类型=str(数据.get("media_mime") or ""),
             媒体文本=str(数据.get("media_text") or ""),
             媒体文件类型=int(数据.get("media_file_type") or 1),
             浏览器媒体键=str(数据.get("browser_media_key") or ""),
            ARK模板ID=str(数据.get("ark_template_id") or ""),
            ARK字段=数据.get("ark_fields") if isinstance(数据.get("ark_fields"), dict) else None,
            ARK列表=str(数据.get("ark_list") or ""),
            卡片字段=数据.get("card") if isinstance(数据.get("card"), dict) else None,
        )
        if not 结果.get("ok"):
            return _控制台错误(409, str(结果.get("message") or "发送失败"))
        清理消息列表缓存()
        return web.json_response({"ok": True, **结果})
    except Exception as exc:
        logger.warning("帮助控制台消息发送失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "发送失败，请稍后再试")
    finally:
        if 临时媒体路径 is not None:
            try:
                临时媒体路径.unlink(missing_ok=True)
            except OSError:
                logger.debug("帮助控制台临时媒体清理失败：错误类型=OSError")


async def _处理消息撤回(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    消息ID = str((数据 or {}).get("message_id") or "").strip()
    if not 会话标识 or not 消息ID:
        return _控制台错误(400, "参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await 消息记录.撤回消息(
            会话标识,
            消息ID,
            str((数据 or {}).get("appid") or ""),
            str((数据 or {}).get("chat_type") or ""),
        )
        if not 结果.get("ok"):
            return _控制台错误(409, str(结果.get("message") or "撤回失败"))
        清理消息列表缓存()
        return web.json_response({"ok": True, "message": "撤回成功"})
    except Exception as exc:
        logger.warning("帮助控制台消息撤回失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "撤回失败，请稍后再试")


async def _处理消息禁言(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    成员标识 = str((数据 or {}).get("member_openid") or "").strip()
    try:
        分钟数 = int((数据 or {}).get("minutes") or 30)
    except (TypeError, ValueError):
        分钟数 = 30
    if not 会话标识 or not 成员标识:
        return _控制台错误(400, "参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await 消息记录.禁言群成员(会话标识, 成员标识, 分钟数, str((数据 or {}).get("appid") or ""))
        if not 结果.get("ok"):
            return _控制台错误(409, str(结果.get("message") or "禁言失败"))
        return web.json_response({"ok": True, "message": "禁言成功"})
    except Exception as exc:
        logger.warning("帮助控制台消息禁言失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "禁言失败，请稍后再试")






def _读取网页群状态快照(
    类型: str, 会话标识: str, appid: str = "", 强制: bool = False,
) -> dict[str, Any]:
    """状态读取不等待官方接口；未取得资料时明确返回 pending。"""
    from 功能文件.管理功能.基础功能 import 消息记录

    会话标识, appid = 消息记录._网页群状态作用域(会话标识, appid)
    if not 消息记录.群会话允许查询资料(会话标识, appid):
        for 清理键 in (("roles", appid, 会话标识), ("mutes", appid, 会话标识)):
            旧任务 = 群状态刷新任务.pop(清理键, None)
            if 旧任务 is not None and not 旧任务.done():
                旧任务.cancel()
            群状态刷新失败冷却.pop(清理键, None)
        状态 = {
            "chat_id": 会话标识, "chat_type": "group", "appid": appid,
            "available": False, "has_data": False, "cached": False,
            "pending": False, "stale": False, "refreshing": False,
            "status": "unavailable", "next_refresh_at": 0, "retry_after_ms": 1000,
        }
        if 类型 == "mutes":
            return {**消息记录._复制群禁言状态(None), **状态}
        return {
            "roles": {}, "bot_is_admin": None, "bot_in_group": None, "bot_role": "",
            "membership_status": "unknown", "membership_checked_at": 0,
            "membership_revision": 0, "allow_proactive_msg": None, "recv_msg_setting": "",
            **状态,
        }

    读取 = 消息记录.获取网页群禁言快照 if 类型 == "mutes" else 消息记录.获取网页群角色快照
    状态, 需要刷新 = 读取(会话标识, appid)
    键 = (类型, str(状态["appid"]), str(状态["chat_id"]))
    现有任务 = 群状态刷新任务.get(键)
    if 现有任务 is not None and 现有任务.done():
        群状态刷新任务.pop(键, None)
        现有任务 = None
    当前时间 = time.monotonic()
    for 冷却键, 截止 in tuple(群状态刷新失败冷却.items()):
        if 截止 <= 当前时间:
            群状态刷新失败冷却.pop(冷却键, None)
    冷却中 = 群状态刷新失败冷却.get(键, 0.0) > 当前时间
    if (需要刷新 or 强制) and 现有任务 is None and (强制 or not 冷却中):
        global _群状态刷新并发
        if _群状态刷新并发 is None:
            _群状态刷新并发 = asyncio.Semaphore(2)
        并发 = _群状态刷新并发

        async def 刷新() -> None:
            def 仍可刷新() -> bool:
                return (
                    群状态刷新任务.get(键) is asyncio.current_task()
                    and 消息记录.群会话允许查询资料(键[2], 键[1])
                )

            try:
                async with 并发:
                    if not 仍可刷新():
                        return
                    async with asyncio.timeout(15):
                        if 类型 == "mutes":
                            刷新结果 = await 消息记录.查询群禁言状态(键[2], 键[1], 强制=强制)
                        else:
                            刷新结果 = await 消息记录.获取群角色(键[2], 键[1], 强制=True)
                        if not 仍可刷新():
                            return
                        # 角色层会保留旧资料并吞掉受控接口失败，不能只靠异常判断刷新成功。
                        # 禁言写入淘汰了较早 GET 时，应让下一次读取补查，不能进入失败冷却。
                        _, 仍需刷新 = 读取(键[2], 键[1])
                        已被写入淘汰 = isinstance(刷新结果, dict) and 刷新结果.get("invalidated") is True
                        if 仍需刷新 and not 已被写入淘汰:
                            群状态刷新失败冷却[键] = time.monotonic() + 30
                        else:
                            群状态刷新失败冷却.pop(键, None)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not 仍可刷新():
                    return
                群状态刷新失败冷却[键] = time.monotonic() + 30
                logger.debug("帮助控制台群状态后台刷新失败：类型=%s，错误类型=%s", 类型, type(exc).__name__)

        现有任务 = asyncio.create_task(刷新(), name="控制台群状态刷新")
        群状态刷新任务[键] = 现有任务
        控制台后台任务.add(现有任务)

        def 结束(任务: asyncio.Task[Any]) -> None:
            if 群状态刷新任务.get(键) is 任务:
                群状态刷新任务.pop(键, None)
            控制台后台任务.discard(任务)
            if not 任务.cancelled():
                任务.exception()

        现有任务.add_done_callback(结束)
    状态["refreshing"] = 现有任务 is not None and not 现有任务.done()
    冷却剩余 = max(0.0, 群状态刷新失败冷却.get(键, 0.0) - time.monotonic())
    状态["retry_after_ms"] = 1000
    if 冷却剩余 and 需要刷新 and not 状态["refreshing"]:
        状态["pending"] = False
        状态["status"] = "stale" if 状态.get("has_data") else "unavailable"
        状态["next_refresh_at"] = time.time() + 冷却剩余
        状态["retry_after_ms"] = max(1000, int(冷却剩余 * 1000))
    if 类型 == "mutes":
        # 仅返回归一化后的规则、成员及快照元数据，不透传 SDK 或缓存中的额外字段。
        归一化 = 消息记录._复制群禁言状态(状态, cached=bool(状态.get("cached")))
        for 字段 in ("chat_id", "chat_type", "appid", "available", "has_data", "pending", "stale", "refreshing", "status", "retry_after_ms"):
            if 字段 in 状态:
                归一化[字段] = 状态[字段]
        return 归一化
    return 状态


async def _处理消息禁言状态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    类型 = str((数据 or {}).get("chat_type") or "group").strip().lower()
    appid = str((数据 or {}).get("appid") or "").strip()
    强制 = (数据 or {}).get("force") is True
    if not 会话标识 or len(会话标识) > 200 or 类型 != "group":
        return _控制台错误(400, "群聊参数无效")
    try:
        状态 = _读取网页群状态快照("mutes", 会话标识, appid, 强制)
        return web.json_response({"ok": True, **状态}, headers={"Cache-Control": "no-store"})
    except ValueError:
        return _控制台错误(400, "群聊与机器人不匹配，请刷新资料")
    except Exception as exc:
        logger.warning("帮助控制台群禁言快照读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(503, "群状态暂时不可用，请稍后重试")


async def _处理消息解除禁言(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    成员标识 = str((数据 or {}).get("member_openid") or "").strip()
    appid = str((数据 or {}).get("appid") or "").strip()
    if not 会话标识 or not 成员标识:
        return _控制台错误(400, "参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await 消息记录.解除群成员禁言(会话标识, 成员标识, appid)
        if not 结果.get("ok"):
            return _控制台错误(409, str(结果.get("message") or "解除禁言失败"))
        return web.json_response({"ok": True, "message": "解除禁言成功"})
    except Exception as exc:
        logger.warning("帮助控制台解除禁言失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "解除禁言失败，请稍后重试")


async def _处理消息置顶(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    原始置顶 = (数据 or {}).get("pinned")
    if isinstance(原始置顶, bool):
        置顶 = 原始置顶
    elif isinstance(原始置顶, (int, float)):
        置顶 = bool(原始置顶)
    else:
        置顶 = str(原始置顶 or "").strip().lower() in {"1", "true", "yes", "on", "置顶"}
    类型 = str((数据 or {}).get("chat_type") or "group").strip()
    appid = str((数据 or {}).get("appid") or "").strip()
    if not 会话标识 or 类型 not in {"group", "user"} or (appid and not re.fullmatch(r"[0-9]{4,32}", appid)):
        return _控制台错误(400, "参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        if not await _控制台线程执行(消息记录.设置会话置顶, 会话标识, 置顶, 类型, appid):
            return _控制台错误(409, "数据库未保存，会话置顶未生效")
        清理消息列表缓存()
        return web.json_response(
            {"ok": True, "pinned": 置顶, "message": "已置顶" if 置顶 else "已取消置顶"}
        )
    except Exception as exc:
        logger.warning("帮助控制台会话置顶失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "置顶操作失败，请稍后再试")


async def _处理消息已读(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    类型 = str((数据 or {}).get("chat_type") or "group").strip()
    appid = str((数据 or {}).get("appid") or "").strip()
    if not 会话标识 or 类型 not in {"group", "user"} or (appid and not re.fullmatch(r"[0-9]{4,32}", appid)):
        return _控制台错误(400, "参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        消息记录.设置会话已读(会话标识, 类型, appid)
        # 已读值已进入消息记录后台队列；不要让浏览器等待 MySQL 提交，
        # 否则每次打开群聊都会被数据库往返阻塞数百毫秒。
        清理消息列表缓存()
        return web.json_response({"ok": True})
    except Exception as exc:
        logger.warning("帮助控制台会话已读失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "操作失败，请稍后再试")


async def _处理群角色(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    if not 会话标识 or len(会话标识) > 200:
        return _控制台错误(400, "会话参数无效")
    try:
        状态 = _读取网页群状态快照("roles", 会话标识, str((数据 or {}).get("appid") or "").strip())
        return web.json_response({"ok": True, **状态}, headers={"Cache-Control": "no-store"})
    except ValueError:
        return _控制台错误(400, "群聊与机器人不匹配，请刷新资料")
    except Exception as exc:
        logger.warning("帮助控制台群角色快照读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(503, "群角色暂时不可用，请稍后重试")


def _群设置响应(结果: dict[str, Any], 状态码: int = 200) -> web.Response:
    return web.json_response(结果, status=状态码, headers={"Cache-Control": "no-store"})


def _群设置错误(状态码: int, 文本: str) -> web.Response:
    return _群设置响应({"ok": False, "error": 文本}, 状态码)


def _群设置请求范围(数据: dict[str, Any]) -> dict[str, str]:
    return {"chat_id": 数据["chat_id"], "chat_type": "group", "appid": 数据["appid"]}


_群设置标识格式 = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_群设置AppID格式 = re.compile(r"[0-9]{4,32}\Z")


async def _读取群设置请求(
    request: web.Request, 要求已知: bool = False,
) -> tuple[dict[str, Any] | None, web.Response | None]:
    """所有群设置入口共享鉴权、同源和显式群作用域校验。"""
    if not _请求已授权(request):
        return None, _群设置错误(401, "请先登录控制台")
    if not _请求来自同源(request):
        return None, _群设置错误(403, "请求来源无效")
    数据 = await _读取请求JSON(request)
    if 数据 is None:
        return None, _群设置错误(400, "请求参数无效")
    群标识 = 数据.get("chat_id")
    appid = 数据.get("appid", "")
    if (
        数据.get("chat_type") != "group"
        or not isinstance(群标识, str)
        or not _群设置标识格式.fullmatch(群标识)
        or not isinstance(appid, str)
        or (appid and not _群设置AppID格式.fullmatch(appid))
    ):
        return None, _群设置错误(400, "群聊参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        已知会话 = 消息记录._读取作用域会话缓存(群标识, "group", appid)
    except Exception as exc:
        logger.warning("帮助控制台群设置范围检查失败：错误类型=%s", type(exc).__name__)
        return None, _群设置错误(502, "群资料暂时不可用，请稍后重试")
    if 已知会话:
        if not isinstance(已知会话, dict) or 已知会话.get("chat_type") != "group":
            return None, _群设置错误(400, "只支持已知群聊")
        已知AppID = 已知会话.get("appid")
        if not isinstance(已知AppID, str) or not _群设置AppID格式.fullmatch(已知AppID):
            return None, _群设置错误(400, "请刷新群资料后重试")
        if appid and appid != 已知AppID:
            return None, _群设置错误(400, "群聊与机器人不匹配")
        appid = 已知AppID
    elif 要求已知 or not appid:
        return None, _群设置错误(400, "请先打开已有群聊并刷新资料")
    数据 = {**数据, "chat_id": 群标识, "appid": appid}
    return 数据, None


def _群设置成员参数有效(标识: Any) -> bool:
    return isinstance(标识, str) and bool(_群设置标识格式.fullmatch(标识))


def _群设置批量成员有效(成员列表: Any) -> bool:
    return (
        isinstance(成员列表, list)
        and 0 < len(成员列表) <= 20
        and all(_群设置成员参数有效(成员) for 成员 in 成员列表)
        and len(set(成员列表)) == len(成员列表)
    )


async def _调用群设置业务(
    数据: dict[str, Any], 函数名: str, 失败提示: str, **参数: Any
) -> web.Response:
    try:
        from 功能文件.管理功能.群聊功能 import 群聊设置

        结果 = await getattr(群聊设置, 函数名)(数据["chat_id"], appid=数据["appid"], **参数)
        if not isinstance(结果, dict):
            return _群设置响应({"ok": False, "error": 失败提示, **_群设置请求范围(数据)}, 502)
        if 函数名 == "批量移除群成员" and (结果.get("ok") is True or 结果.get("partial") is True):
            清理消息列表缓存()
        if 结果.get("ok") is not True:
            原始状态 = 结果.get("http_status")
            状态码 = 原始状态 if type(原始状态) is int and 400 <= 原始状态 <= 599 else 409
            原因 = 结果.get("reason")
            受控提示 = {
                "api_permission": "机器人尚未开通此群管理接口",
                "group_permission": "该群尚未授予机器人所需管理权限",
                "auth_expired": "机器人登录状态暂时失效，请稍后重试",
                "rate_limited": "操作过于频繁，请稍后重试",
                "invalid_response": "群管理响应不完整",
                "remove_unconfirmed": "成员移除结果未确认，请刷新成员列表",
                "operation_unconfirmed": "黑名单操作结果未确认，请刷新黑名单",
            }.get(原因, 失败提示) if isinstance(原因, str) else 失败提示
            错误码 = 结果.get("code")
            logger.warning(
                "帮助控制台群设置操作失败：阶段=%s，群标识=%s，appid=%s，HTTP状态=%s，业务码=%s",
                函数名, 数据["chat_id"], 数据["appid"], 状态码,
                错误码 if type(错误码) is int else "none",
            )
            return _群设置响应(
                {**结果, "ok": False, "error": 受控提示, "message": 受控提示, **_群设置请求范围(数据)},
                状态码,
            )
        return _群设置响应({**结果, **_群设置请求范围(数据)})
    except Exception as exc:
        logger.warning(
            "帮助控制台群设置操作失败：阶段=%s，群标识=%s，appid=%s，错误类型=%s",
            函数名, 数据["chat_id"], 数据["appid"], type(exc).__name__,
        )
        return _群设置响应({"ok": False, "error": 失败提示, **_群设置请求范围(数据)}, 502)


async def _处理群设置(request: web.Request) -> web.Response:
    数据, 错误 = await _读取群设置请求(request)
    if 错误 is not None:
        return 错误
    return await _调用群设置业务(数据, "获取群设置", "群设置读取失败，请稍后再试")


async def _处理群成员列表(request: web.Request) -> web.Response:
    数据, 错误 = await _读取群设置请求(request)
    if 错误 is not None:
        return 错误
    游标 = 数据.get("cursor", "")
    强制刷新 = 数据.get("force", False)
    if not isinstance(游标, str) or len(游标) > 2048 or not isinstance(强制刷新, bool):
        return _群设置错误(400, "成员分页参数无效")
    return await _调用群设置业务(
        数据, "获取群成员列表", "群成员列表读取失败，请稍后再试", cursor=游标, force=强制刷新,
    )


async def _处理群成员信息(request: web.Request) -> web.Response:
    数据, 错误 = await _读取群设置请求(request)
    if 错误 is not None:
        return 错误
    成员标识 = 数据.get("member_openid")
    强制刷新 = 数据.get("force", False)
    if not _群设置成员参数有效(成员标识) or not isinstance(强制刷新, bool):
        return _群设置错误(400, "成员参数无效")
    return await _调用群设置业务(
        数据, "获取群成员信息", "群成员信息读取失败，请稍后再试", member_openid=成员标识.strip(), force=强制刷新,
    )


async def _处理群成员批量移除(request: web.Request) -> web.Response:
    数据, 错误 = await _读取群设置请求(request)
    if 错误 is not None:
        return 错误
    成员列表 = 数据.get("member_openids")
    同时拉黑 = 数据.get("add_to_member_blacklist", False)
    if not _群设置批量成员有效(成员列表) or not isinstance(同时拉黑, bool):
        return _群设置错误(400, "成员移除参数无效，单次最多选择 20 人")
    return await _调用群设置业务(
        数据, "批量移除群成员", "群成员移除失败，请稍后再试",
        member_openids=[成员.strip() for 成员 in 成员列表], add_to_member_blacklist=同时拉黑,
    )


async def _处理群黑名单查询(request: web.Request) -> web.Response:
    数据, 错误 = await _读取群设置请求(request)
    if 错误 is not None:
        return 错误
    游标 = 数据.get("cursor", "")
    条数 = 数据.get("limit", 20)
    强制刷新 = 数据.get("force", False)
    if (
        not isinstance(游标, str) or len(游标) > 2048
        or type(条数) is not int or not 1 <= 条数 <= 100
        or not isinstance(强制刷新, bool)
    ):
        return _群设置错误(400, "黑名单分页参数无效")
    return await _调用群设置业务(
        数据, "获取群黑名单", "群黑名单读取失败，请稍后再试", cursor=游标, limit=条数, force=强制刷新,
    )


async def _处理群黑名单操作(request: web.Request) -> web.Response:
    数据, 错误 = await _读取群设置请求(request)
    if 错误 is not None:
        return 错误
    成员列表 = 数据.get("member_openids")
    操作 = 数据.get("op")
    if not _群设置批量成员有效(成员列表) or not isinstance(操作, str) or 操作 not in {"add", "del"}:
        return _群设置错误(400, "黑名单操作参数无效，单次最多选择 20 人")
    return await _调用群设置业务(
        数据, "操作群黑名单", "群黑名单操作失败，请稍后再试",
        member_openids=[成员.strip() for 成员 in 成员列表], op=操作,
    )


async def _处理群备注(request: web.Request) -> web.Response:
    数据, 错误 = await _读取群设置请求(request, 要求已知=True)
    if 错误 is not None:
        return 错误
    会话标识 = 数据["chat_id"]
    操作 = 数据.get("action", "set")
    if not isinstance(操作, str) or 操作 not in {"get", "set", "delete"}:
        return _群设置错误(400, "备注操作参数无效")
    if 操作 == "set" and (
        not isinstance(数据.get("remark", ""), str)
        or len(数据.get("remark", "")) > 200
        or not isinstance(数据.get("group_qq", ""), str)
        or len(数据.get("group_qq", "")) > 32
    ):
        return _群设置错误(400, "备注参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        if 操作 == "get":
            结果 = {
                "remark": 消息记录.获取群备注(会话标识, 数据["appid"]),
                "group_qq": 消息记录.获取群QQ号(会话标识, 数据["appid"]),
            }
            return _群设置响应({"ok": True, **结果, **_群设置请求范围(数据)})
        if 操作 == "delete":
            if not await _控制台线程执行(消息记录.删除群备注, 会话标识, 数据["appid"]):
                return _群设置错误(409, "备注删除失败")
            清理消息列表缓存()
            return _群设置响应({"ok": True, "message": "备注已删除", **_群设置请求范围(数据)})
        备注 = 数据.get("remark", "").strip()
        群QQ = 数据.get("group_qq", "").strip()
        if not await _控制台线程执行(消息记录.保存群备注, 会话标识, 备注, 群QQ, 数据["appid"]):
            return _群设置错误(409, "备注保存失败")
        清理消息列表缓存()
        return _群设置响应({"ok": True, "message": "备注已保存", **_群设置请求范围(数据)})
    except Exception as exc:
        logger.warning("帮助控制台群备注保存失败：错误类型=%s", type(exc).__name__)
        return _群设置错误(409, "备注保存失败")


async def _处理私聊资料刷新(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    标识 = str((数据 or {}).get("chat_id") or "").strip()
    类型 = str((数据 or {}).get("chat_type") or "user").strip()
    if not 标识 or len(标识) > 128 or 类型 != "user":
        return _控制台错误(400, "私聊参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await 消息记录.刷新私聊资料(标识, str((数据 or {}).get("appid") or ""))
        清理消息列表缓存()
        return web.json_response({"ok": True, **结果}, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台私聊资料刷新失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "私聊资料刷新失败")


async def _处理群信息刷新(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    if not 会话标识:
        return _控制台错误(400, "会话参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        # 网页按钮表示管理员明确要求更新，忽略 24 小时缓存和失败冷却。
        结果 = await 消息记录.刷新群信息(
            会话标识,
            str((数据 or {}).get("appid") or ""),
            强制=True,
        )
        if 结果 is None:
            return _控制台错误(409, "群信息刷新失败")
        清理消息列表缓存()
        return web.json_response({"ok": True, **结果})
    except Exception as exc:
        logger.warning("帮助控制台群信息刷新失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "群信息刷新失败")


async def _处理群广告开关(request: web.Request) -> web.Response:
    """读取或修改单个 QQ 官方群的广告拦截状态。"""
    数据, 错误 = await _读取群设置请求(request, 要求已知=True)
    if 错误 is not None:
        return 错误
    会话标识 = 数据["chat_id"]
    操作 = 数据.get("action", "get")
    if not isinstance(操作, str) or 操作 not in {"get", "set"}:
        return _群设置错误(400, "广告开关操作参数无效")
    try:
        from 功能文件.管理功能.群聊功能 import 群管功能

        if 操作 == "get":
            开启 = await _控制台线程执行(
                群管功能.读取群广告开关,
                _当前作用域配置(),
                会话标识,
            )
            return web.json_response(
                {
                    "ok": True,
                    "enabled": bool(开启),
                    "editable": bool(群管功能.群广告开关可持久化(_当前作用域配置())),
                    "platform": "qq_official",
                    **_群设置请求范围(数据),
                },
                headers={"Cache-Control": "no-store"},
            )

        原始状态 = 数据.get("enabled")
        if not isinstance(原始状态, bool):
            return _群设置错误(400, "广告开关参数无效")
        if not 群管功能.群广告开关可持久化(_当前作用域配置()):
            return _群设置错误(409, "数据库未配置，广告开关保存失败")
        成功 = await _控制台线程执行(
            群管功能.写入群广告开关,
            _当前作用域配置(),
            会话标识,
            原始状态,
        )
        if not 成功:
            return _群设置错误(409, "广告开关保存失败，请稍后再试")
        return web.json_response(
            {
                "ok": True,
                "enabled": bool(原始状态),
                "editable": True,
                "platform": "qq_official",
                **_群设置请求范围(数据),
            },
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        logger.warning("帮助控制台群广告开关失败：错误类型=%s", type(exc).__name__)
        return _群设置错误(409, "广告开关暂时不可用")
