from __future__ import annotations

import asyncio
import copy
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
import tempfile
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, TCPConnector, web

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)

默认监听地址 = "0.0.0.0"
默认监听端口 = 8090
控制台版本 = "6.1.14"
默认控制台用户名 = "admin"
默认控制台密码 = ""
控制台会话Cookie名 = "mantou_console_session"
控制台会话有效期 = 30 * 24 * 60 * 60
控制台会话命名空间 = "console_session"
消息布局命名空间 = "msg_console_layout"
消息布局默认值 = {
    "list_width": 340,
    "composer_height": 132,
    "list_collapsed": False,
    "composer_collapsed": False,
}
媒体代理最大字节数 = 256 * 1024 * 1024
媒体代理超时秒 = 30
媒体代理主机后缀 = (
    "multimedia.nt.qq.com.cn",
    "qqbot.ugcimg.cn",
    "gchat.qpic.cn",
    "qpic.cn",
    "qq.com.cn",
    "qq.com",
)


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
_控制台执行器: ThreadPoolExecutor | None = globals().get("_控制台执行器")
_控制台执行器锁 = globals().get("_控制台执行器锁") or threading.Lock()
控制台执行器最大并发数 = 4
消息列表缓存秒数 = 3.0
消息列表缓存最大条目 = 64
消息列表缓存: dict[tuple[str, str, int, int], tuple[float, dict[str, Any]]] = globals().get("消息列表缓存") or {}
消息列表缓存锁: dict[tuple[str, str, int, int], asyncio.Lock] = globals().get("消息列表缓存锁") or {}
消息列表后台刷新: set[tuple[str, str, int, int]] = globals().get("消息列表后台刷新") or set()
消息列表缓存版本 = int(globals().get("消息列表缓存版本", 0) or 0)
实时连接任务: set[asyncio.Task[Any]] = globals().get("实时连接任务") or set()
_媒体代理会话: ClientSession | None = globals().get("_媒体代理会话")


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
    调用 = partial(函数, *参数, **关键字参数)
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
            trust_env=False,
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


def 清理消息列表缓存() -> None:
    """清除网页会话列表缓存，写入/已读/置顶后立即读取最新状态。"""
    global 消息列表缓存版本
    消息列表缓存版本 += 1
    消息列表缓存.clear()


def _写入消息列表缓存(
    缓存键: tuple[str, str, int, int], 结果: dict[str, Any], 缓存版本: int
) -> None:
    if 缓存版本 != 消息列表缓存版本:
        return
    if 缓存键 not in 消息列表缓存 and len(消息列表缓存) >= 消息列表缓存最大条目:
        最旧键 = min(消息列表缓存, key=lambda key: 消息列表缓存[key][0])
        消息列表缓存.pop(最旧键, None)
    消息列表缓存[缓存键] = (time.monotonic(), copy.deepcopy(结果))


async def _构建消息列表(
    过滤: str, 搜索: str, 页码: int, 每页: int
) -> dict[str, Any]:
    from 功能文件.管理功能.基础功能 import 消息记录

    结果 = await _控制台线程执行(
        消息记录.获取聊天列表, 过滤, 搜索, 页码, 每页
    )
    try:
        # 昵称补查只更新内存兜底值；列表聚合已使用同一份缓存。
        await 消息记录.补查缺失私聊昵称(结果.get("chats") or [])
    except Exception:
        pass
    return 结果


async def _后台刷新消息列表(
    缓存键: tuple[str, str, int, int], 过滤: str, 搜索: str, 页码: int, 每页: int,
    缓存版本: int,
) -> None:
    try:
        结果 = await _构建消息列表(过滤, 搜索, 页码, 每页)
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
    "uc_pan_cookie": {
        "category": "uc_pan_settings",
        "label": "UC 网盘 Cookie",
        "kind": "secret",
        "secret": True,
    },
    "uc_pan_upload_dir": {
        "category": "uc_pan_settings",
        "label": "UC 上传目录",
        "kind": "text",
        "secret": False,
    },
    "quark_pan_cookie": {
        "category": "quark_pan_settings",
        "label": "夸克网盘 Cookie",
        "kind": "secret",
        "secret": True,
    },
    "quark_pan_upload_dir": {
        "category": "quark_pan_settings",
        "label": "夸克上传目录",
        "kind": "text",
        "secret": False,
    },
    "baidu_pan_cookie": {
        "category": "baidu_pan_settings",
        "label": "百度网盘 Cookie",
        "kind": "secret",
        "secret": True,
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
        "kind": "secret",
        "secret": True,
    },
    "database_port": {
        "category": "database_settings",
        "label": "数据库端口",
        "kind": "secret",
        "secret": True,
    },
    "database_user": {
        "category": "database_settings",
        "label": "数据库用户名/名称",
        "kind": "secret",
        "secret": True,
    },
    "database_password": {
        "category": "database_settings",
        "label": "数据库密码",
        "kind": "secret",
        "secret": True,
    },
}

配置字段分类显示名 = {
    "basic_settings": "权限设置",
    "help_web_settings": "帮助网页",
    "uc_pan_settings": "UC 网盘",
    "quark_pan_settings": "夸克网盘",
    "baidu_pan_settings": "百度网盘",
    "database_settings": "数据库",
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
    配置 = 当前帮助网页配置
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
    配置 = 当前帮助网页配置
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
            [] if 定义["kind"] == "admin_list" else "",
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
        }
        if 定义.get("options"):
            项目["options"] = list(定义["options"])
        if 定义["kind"] == "admin_list":
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
    }


def _校验插件配置字段(字段名: str, 值: Any) -> Any:
    定义 = 插件配置字段定义.get(字段名)
    if not 定义:
        raise ValueError("配置字段不支持")
    kind = 定义["kind"]
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
        if 字段名 == "database_port" and (
            not 文本.isdigit() or not 1 <= int(文本) <= 65535
        ):
            raise ValueError("数据库端口无效")
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


def _数据库会话可用() -> bool:
    """当前帮助网页配置已配置运行状态数据库时才能持久化会话。"""
    if 当前帮助网页配置 is None:
        return False
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 已配置运行状态数据库
        return bool(已配置运行状态数据库(当前帮助网页配置))
    except Exception:
        return False


def _解析持久会话文本(文本: str) -> tuple[float | None, str]:
    """解析持久会话值：到期时间戳|用户名；格式异常返回 (None, 管理员)。"""
    if not 文本:
        return None, "管理员"
    try:
        到期部分, _, 用户名 = str(文本).rpartition("|")
        return float(到期部分), 用户名 or "管理员"
    except Exception:
        return None, "管理员"


def _读取持久化控制台会话(会话值: str) -> tuple[float, str] | None:
    """从 MySQL 恢复会话；返回 (到期时间, 用户名)；无有效会话返回 None。"""
    if not 会话值 or not _数据库会话可用():
        return None
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态值
        文本 = 读取运行状态值(当前帮助网页配置, 控制台会话命名空间, 会话值, "")
        到期时间, 用户名 = _解析持久会话文本(文本)
        if 到期时间 is None:
            return None
        return 到期时间, 用户名
    except Exception as exc:
        logger.debug("帮助控制台读取持久会话失败：错误类型=%s", type(exc).__name__)
        return None


def _写入持久化控制台会话(会话值: str, 到期时间: float, 用户名: str) -> None:
    if not 会话值 or not _数据库会话可用():
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值
        写入运行状态值(
            当前帮助网页配置,
            控制台会话命名空间,
            会话值,
            f"{到期时间:.0f}|{用户名}",
        )
    except Exception as exc:
        logger.debug("帮助控制台写入持久会话失败：错误类型=%s", type(exc).__name__)


def _删除持久化控制台会话(会话值: str) -> None:
    if not 会话值 or not _数据库会话可用():
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 删除运行状态值
        删除运行状态值(当前帮助网页配置, 控制台会话命名空间, 会话值)
    except Exception as exc:
        logger.debug("帮助控制台删除持久会话失败：错误类型=%s", type(exc).__name__)


def _加载持久化控制台会话() -> None:
    """启动服务时把数据库中的有效会话恢复到内存，避免重载后同设备重新登录。"""
    if not _数据库会话可用():
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态命名空间
        记录 = 读取运行状态命名空间(当前帮助网页配置, 控制台会话命名空间)
        现在 = time.time()
        for 会话值, 文本 in 记录.items():
            到期时间, 用户名 = _解析持久会话文本(文本)
            if 到期时间 is None or 到期时间 <= 现在:
                _删除持久化控制台会话(会话值)
                continue
            控制台会话[会话值] = 到期时间
            控制台会话身份[会话值] = 用户名
    except Exception as exc:
        logger.debug("帮助控制台加载持久会话失败：错误类型=%s", type(exc).__name__)


def _清理控制台会话() -> None:
    截止时间 = time.time()
    for 会话值, 到期时间 in list(控制台会话.items()):
        if 到期时间 <= 截止时间:
            控制台会话.pop(会话值, None)
            控制台会话身份.pop(会话值, None)
            _删除持久化控制台会话(会话值)


def _取得请求会话(request: web.Request) -> str:
    _清理控制台会话()
    return str(request.cookies.get(控制台会话Cookie名) or "").strip()


def _请求已授权(request: web.Request) -> bool:
    会话值 = _取得请求会话(request)
    if not 会话值:
        return False
    到期时间 = 控制台会话.get(会话值)
    需要回写持久会话 = False
    if 到期时间 is None:
        # 内存未命中（如插件重载后）：尝试从 MySQL 恢复持久会话
        持久会话 = _读取持久化控制台会话(会话值)
        if 持久会话 is not None:
            到期时间, 用户名 = 持久会话
            控制台会话[会话值] = 到期时间
            控制台会话身份[会话值] = 用户名
            需要回写持久会话 = True
    if 到期时间 is None or 到期时间 <= time.time():
        控制台会话.pop(会话值, None)
        控制台会话身份.pop(会话值, None)
        return False
    新到期时间 = time.time() + 控制台会话有效期
    控制台会话[会话值] = 新到期时间
    if 需要回写持久会话:
        # 恢复会话时同步滑动续期到 MySQL，保证长期使用不因插件重载掉线
        _写入持久化控制台会话(会话值, 新到期时间, 控制台会话身份.get(会话值, "管理员"))
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


async def _读取请求JSON(request: web.Request) -> dict[str, Any] | None:
    try:
        数据 = await request.json()
    except Exception:
        return None
    return 数据 if isinstance(数据, dict) else None


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
                fd, 路径文本 = tempfile.mkstemp(prefix='mantou-web-', suffix=后缀)
                临时路径 = Path(路径文本)
                已读 = 0
                try:
                    with os.fdopen(fd, 'wb') as 文件句柄:
                        while True:
                            数据块 = await 部分.read_chunk(size=1024 * 1024)
                            if not 数据块:
                                break
                            已读 += len(数据块)
                            if 已读 > 媒体代理最大字节数:
                                raise ValueError('媒体文件过大')
                            文件句柄.write(数据块)
                except Exception:
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
        return 数据, 临时路径
    except Exception:
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
    文件名 = _媒体文件名(request.query.get("name"))
    try:
        超时 = ClientTimeout(total=媒体代理超时秒, connect=10, sock_read=媒体代理超时秒)
        客户端 = await 获取媒体代理会话()
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
                最终地址 = str(getattr(上游, "url", 地址) or 地址)
                if not _允许媒体地址(最终地址):
                    return web.Response(status=502, text="媒体地址不可用")
                if 上游.status not in {200, 206}:
                    return web.Response(status=404, text="媒体暂时不可用")
                try:
                    内容长度 = int(上游.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    内容长度 = 0
                if 内容长度 > 媒体代理最大字节数:
                    return web.Response(status=413, text="媒体文件过大")

                前缀 = await 上游.content.read(64 * 1024)
                类型 = _识别媒体类型(
                    上游.headers.get("Content-Type"), 前缀, 最终地址, 模式
                )
                if 模式 == "image" and not 类型.startswith("image/"):
                    return web.Response(status=415, text="不是可预览的图片")
                响应头 = {
                    "Cache-Control": "private, max-age=120",
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
                await 响应.prepare(request)
                已发送 = 0
                if 前缀:
                    已发送 = len(前缀)
                    if 已发送 > 媒体代理最大字节数:
                        await 响应.write_eof()
                        return 响应
                    await 响应.write(前缀)
                async for 数据块 in 上游.content.iter_chunked(64 * 1024):
                    if 已发送 + len(数据块) > 媒体代理最大字节数:
                        logger.warning(
                            "帮助控制台媒体代理达到大小上限：模式=%s，大小上限=%d",
                            模式,
                            媒体代理最大字节数,
                        )
                        break
                    await 响应.write(数据块)
                    已发送 += len(数据块)
                await 响应.write_eof()
                return 响应
    except asyncio.CancelledError:
        raise
    except (ClientError, asyncio.TimeoutError, TimeoutError, OSError, ValueError) as exc:
        logger.warning(
            "帮助控制台媒体代理失败：模式=%s，错误类型=%s",
            模式,
            type(exc).__name__,
        )
        return web.Response(status=502, text="媒体暂时不可用")


本地发送媒体有效期秒 = 3 * 24 * 60 * 60
本地发送媒体扩展名 = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".silk", ".dat"})


def _默认本地发送媒体目录() -> Path:
    """使用 AstrBot 数据目录保存发送媒体，避免写入插件代码目录。"""
    try:
        插件根目录 = Path(__file__).resolve().parents[2]
        if 插件根目录.parent.name.lower() == "plugins":
            return 插件根目录.parent.parent / "mantou_bot_media"
    except (OSError, IndexError):
        pass
    return Path(tempfile.gettempdir()) / "mantou_bot_media"


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
    截止时间 = float(现在 if 现在 is not None else time.time()) - 本地发送媒体有效期秒
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
    if not isinstance(数据, bytes) or not 数据 or len(数据) > 媒体代理最大字节数:
        return ""
    try:
        _清理本地发送媒体同步()
        扩展名 = Path(str(文件名 or "")).suffix.lower()
        if 扩展名 not in 本地发送媒体扩展名:
            扩展名 = mimetypes.guess_extension(str(内容类型 or "").split(";", 1)[0]) or ".dat"
        if 扩展名 == ".jpe":
            扩展名 = ".jpg"
        目标 = 本地发送媒体目录 / f"{hashlib.md5(数据).hexdigest()}{扩展名}"
        本地发送媒体目录.mkdir(parents=True, exist_ok=True)
        if not 目标.is_file():
            临时 = 目标.with_name(f".{目标.name}.{secrets.token_hex(4)}.tmp")
            try:
                临时.write_bytes(数据)
                临时.replace(目标)
            finally:
                临时.unlink(missing_ok=True)
        return f"/api/message/local-media/{目标.name}"
    except (OSError, TypeError, ValueError):
        return ""


async def 保存本地发送媒体(
    数据: bytes,
    文件名: str = "",
    内容类型: str = "application/octet-stream",
) -> str:
    """按内容 MD5 保存发送媒体，返回控制台同源地址。"""
    if not isinstance(数据, (bytes, bytearray)) or not 数据:
        return ""
    return await _控制台线程执行(
        _保存本地发送媒体同步,
        bytes(数据),
        str(文件名 or ""),
        str(内容类型 or "application/octet-stream"),
    )


async def _处理本地发送媒体(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return web.Response(status=401, text="请先登录控制台")
    路径 = _本地发送媒体路径(request.match_info.get("filename"))
    if 路径 is None or not 路径.is_file():
        return web.Response(status=404, text="媒体暂时不可用")
    try:
        _清理本地发送媒体同步()
        if not 路径.is_file():
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
    配置用户名, 配置密码 = _读取控制台账号(当前帮助网页配置)
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
    _写入持久化控制台会话(会话值, 到期时间, 配置用户名)
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
    控制台会话.pop(会话值, None)
    控制台会话身份.pop(会话值, None)
    _删除持久化控制台会话(会话值)
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

    配置 = 当前帮助网页配置
    数据库已配置 = 已配置运行状态数据库(配置)
    数据库状态 = 检查运行状态数据库(配置)
    QQ登录态摘要: dict[str, Any] = {"configured": False}
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        原值 = QQ阅读._读取QQ阅读登录态(配置)
        原始状态 = QQ阅读.读取运行状态值(
            配置,
            QQ阅读.QQ阅读登录态命名空间,
            QQ阅读.QQ阅读登录态状态键,
            "",
        )
        更新时间 = 0
        if 原始状态:
            try:
                更新时间 = int((json.loads(原始状态) or {}).get("updated_at") or 0)
            except (TypeError, ValueError, json.JSONDecodeError):
                更新时间 = 0
        QQ登录态摘要 = {"configured": bool(原值), "updated_at": 更新时间}
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
        except Exception:
            已配置, 账号数量, 账号摘要, 目录 = False, 0, [], ""
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
                # 账号选择按群隔离；控制台没有当前群上下文，默认展示账号1。
                "selected_account": 1,
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
        "database": {"configured": 数据库已配置, "status": 数据库状态},
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

        状态 = 读取运行状态命名空间(当前帮助网页配置, 消息布局命名空间)
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
            当前帮助网页配置,
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
    """返回 QQ 官方机器人公开资料；失败时返回空资料让页面使用默认头像。"""
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        资料 = await 消息记录.获取机器人资料()
        return web.json_response(
            {"ok": True, "profile": 资料 if isinstance(资料, dict) else {}},
            headers={"Cache-Control": "private, max-age=300"},
        )
    except Exception as exc:
        logger.debug("帮助控制台机器人资料读取失败：错误类型=%s", type(exc).__name__)
        return web.json_response(
            {"ok": True, "profile": {}},
            headers={"Cache-Control": "private, max-age=60"},
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
                当前帮助网页配置,
                小说功能开关.状态命名空间,
                小说功能开关.小说总开关状态键,
                enabled,
            )
        elif 功能名 == "__test__":
            写入布尔运行状态值(
                当前帮助网页配置,
                小说功能开关.状态命名空间,
                小说功能开关.管理员测试模式状态键,
                enabled,
            )
        elif 功能名 in 小说功能开关.默认状态:
            小说功能开关.写入小说功能状态(当前帮助网页配置, 功能名, enabled)
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
    数据 = await _读取请求JSON(request)
    网盘名 = str((数据 or {}).get("key") or "").strip()
    if 网盘名 not in {"UC", "夸克", "百度"}:
        return _控制台错误(400, "网盘参数无效")
    try:
        from 功能文件.管理功能.网盘功能 import 网盘状态

        网盘已开启 = await _控制台线程执行(
            网盘状态.网盘开关是否开启,
            当前帮助网页配置,
            网盘名,
        )
        if not 网盘已开启:
            return _控制台错误(409, "该网盘已关闭，请先开启")
    except Exception as exc:
        logger.warning(
            "帮助控制台主网盘开关读取失败：平台=%s，错误类型=%s",
            网盘名,
            type(exc).__name__,
        )
        return _控制台错误(409, "网盘状态暂时不可用")

    def _写入() -> None:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值

        写入运行状态值(当前帮助网页配置, "novel_share_pan", "active", 网盘名)

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
            当前帮助网页配置,
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


async def _处理插件配置写入(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    字段数据 = (数据 or {}).get("fields")
    if not isinstance(字段数据, dict) or not 字段数据:
        return _控制台错误(400, "配置参数无效")
    if 当前帮助网页配置 is None:
        return _控制台错误(503, "插件配置不可用")
    配置字典: dict[str, Any] | None = None
    原配置快照: dict[str, Any] | None = None
    阶段 = "读取配置"
    try:
        配置字典 = _读取插件配置字典(当前帮助网页配置)
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
            if 定义.get("secret") and not str(原值 or "").strip():
                continue
            值 = _校验插件配置字段(字段名, 原值)
            待更新.append((字段名, 定义, 值))
        已更新 = []
        阶段 = "写入配置"
        # 先完整校验，再一次性写入，避免同一请求中后续字段失败时留下半套配置。
        for 字段名, 定义, 值 in 待更新:
            _设置插件配置值(
                当前帮助网页配置,
                str(定义["category"]),
                字段名,
                值,
            )
            已更新.append(字段名)
        阶段 = "持久化配置"
        if 已更新 and _插件配置可持久化(当前帮助网页配置):
            await _持久化插件配置()
        elif 已更新 and not isinstance(当前帮助网页配置, dict):
            raise RuntimeError("插件配置没有持久化接口")
        if "group_file_cleanup_admin_qq" in 已更新:
            阶段 = "同步管理员白名单"
            from 功能文件.管理功能.基础功能 import 权限工具

            权限工具.同步管理员白名单(当前帮助网页配置, 强制=True)
        return web.json_response(
            {
                "ok": True,
                "updated": 已更新,
                "restart_required": bool(已更新),
                "message": "配置已保存，监听地址、登录账号和网盘目录等变更需重载插件生效",
            }
        )
    except ValueError:
        return _控制台错误(400, "配置参数无效")
    except Exception as exc:
        if isinstance(配置字典, dict) and isinstance(原配置快照, dict):
            配置字典.clear()
            配置字典.update(原配置快照)
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

        if 平台 == "夸克" and request.query.get("refresh") == "1":
            await 网盘Cookie._刷新夸克账号资料(当前帮助网页配置)
        摘要 = await _控制台线程执行(
            网盘Cookie.获取网盘账号摘要, 当前帮助网页配置, 平台
        )
        当前序号 = await _控制台线程执行(
            网盘Cookie.获取当前网盘账号序号, 当前帮助网页配置, 平台
        )
        return web.json_response(
            {"ok": True, "platform": 平台, "selected_account": 当前序号, "accounts": 摘要},
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
        名称 = 手机号 = ""
        if 平台 == "夸克":
            名称, 手机号 = await 网盘Cookie._获取夸克账号资料(解析结果[1])
        序号 = await _控制台线程执行(
            网盘Cookie._保存网盘Cookie,
            当前帮助网页配置,
            平台,
            解析结果[1],
            名称=名称,
            手机号=手机号,
        )
        return web.json_response(
            {"ok": True, "index": 序号, "message": f"{平台}账号已保存"}
        )
    except Exception as exc:
        logger.warning("帮助控制台网盘账号保存失败：平台=%s, 错误类型=%s", 平台, type(exc).__name__)
        return _控制台错误(409, "网盘账号保存失败，请检查数据库配置")


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
            网盘Cookie._删除网盘账号, 当前帮助网页配置, 平台, 序号
        )
        if not 成功:
            return _控制台错误(409, "账号不能删除，请检查账号序号和数据库配置")
        return web.json_response({"ok": True, "message": "账号已删除"})
    except Exception as exc:
        logger.warning("帮助控制台网盘账号删除失败：平台=%s, 错误类型=%s", 平台, type(exc).__name__)
        return _控制台错误(409, "网盘账号删除失败")


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
            当前帮助网页配置,
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


async def _处理QQ阅读登录态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        原值 = QQ阅读._读取QQ阅读登录态(当前帮助网页配置)
        原始状态 = QQ阅读.读取运行状态值(
            当前帮助网页配置,
            QQ阅读.QQ阅读登录态命名空间,
            QQ阅读.QQ阅读登录态状态键,
            "",
        )
        更新时间 = 0
        try:
            更新时间 = int((json.loads(原始状态) or {}).get("updated_at") or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return web.json_response(
            {"ok": True, "configured": bool(原值), "updated_at": 更新时间}
        )
    except Exception as exc:
        logger.warning("帮助控制台 QQ阅读状态读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "QQ阅读状态读取失败")


async def _处理QQ阅读登录态保存(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    文本 = str((数据 or {}).get("cookie") or "").strip()
    if not 文本:
        文本 = f"ywguid: {(数据 or {}).get('ywguid') or ''}\nywkey: {(数据 or {}).get('ywkey') or ''}"
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        登录态 = QQ阅读.解析QQ阅读Cookie(文本)
        if not 登录态:
            return _控制台错误(400, "QQ阅读登录态格式无效")
        if not QQ阅读.已配置运行状态数据库(当前帮助网页配置):
            return _控制台错误(409, "数据库未配置，登录态未保存")
        await _控制台线程执行(QQ阅读._保存QQ阅读登录态, 当前帮助网页配置, 登录态)
        await _控制台线程执行(QQ阅读._应用QQ阅读登录态, 登录态)
        return web.json_response({"ok": True, "message": "QQ阅读登录态已保存"})
    except Exception as exc:
        logger.warning("帮助控制台 QQ阅读登录态保存失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "QQ阅读登录态保存失败")


async def _处理QQ阅读登录态删除(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    try:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读

        if not QQ阅读.已配置运行状态数据库(当前帮助网页配置):
            return _控制台错误(409, "数据库未配置，登录态未删除")
        QQ阅读.写入运行状态值(
            当前帮助网页配置,
            QQ阅读.QQ阅读登录态命名空间,
            QQ阅读.QQ阅读登录态状态键,
            "",
        )
        return web.json_response({"ok": True, "message": "QQ阅读登录态已清除"})
    except Exception as exc:
        logger.warning("帮助控制台 QQ阅读登录态删除失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "QQ阅读登录态清除失败")



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
    页码 = max(1, 页码)
    缓存键 = (过滤, 搜索, 页码, 每页)
    当前时间 = time.monotonic()
    缓存项 = 消息列表缓存.get(缓存键)
    if 缓存项:
        缓存时间, 缓存结果 = 缓存项
        if 当前时间 - 缓存时间 >= 消息列表缓存秒数 and 缓存键 not in 消息列表后台刷新:
            消息列表后台刷新.add(缓存键)
            asyncio.create_task(_后台刷新消息列表(缓存键, 过滤, 搜索, 页码, 每页, 消息列表缓存版本))
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
                结果 = await _构建消息列表(过滤, 搜索, 页码, 每页)
                _写入消息列表缓存(缓存键, 结果, 缓存版本)
        return web.json_response({"ok": True, **结果}, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台消息列表读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "消息列表暂时不可用")


async def _处理消息历史(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    类型 = str((数据 or {}).get("chat_type") or "group")
    before_date = str((数据 or {}).get("before_date") or "")
    try:
        before_id = max(0, int((数据 or {}).get("before_id") or 0))
    except (TypeError, ValueError):
        before_id = 0
    try:
        limit = int((数据 or {}).get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    if not 会话标识 or len(会话标识) > 200:
        return _控制台错误(400, "会话参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await _控制台线程执行(
            消息记录.获取消息历史, 会话标识, 类型, before_date, limit, before_id
        )
        try:
            消息记录.安排待处理群信息刷新()
        except Exception:
            pass
        try:
            if 类型 == "user":
                await 消息记录.补查缺失私聊昵称([
                    {"chat_id": 会话标识, "chat_type": "user", "appid": str((数据 or {}).get("appid") or "")}
                ])
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





async def _处理消息禁言状态(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    类型 = str((数据 or {}).get("chat_type") or "group").strip().lower()
    appid = str((数据 or {}).get("appid") or "").strip()
    强制 = (数据 or {}).get("force") is True or str(
        (数据 or {}).get("force") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not 会话标识 or 类型 != "group":
        return _控制台错误(400, "群聊参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        状态 = await 消息记录.查询群禁言状态(会话标识, appid, 强制=强制)
        return web.json_response(
            {"ok": True, **状态},
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        logger.warning(
            "帮助控制台群禁言状态读取失败：错误类型=%s",
            type(exc).__name__,
        )
        return web.json_response(
            {
                "ok": True,
                "available": False,
                "members": [],
                "global_rule": {},
                "checked_at": int(time.time()),
            },
            headers={"Cache-Control": "no-store"},
        )


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
    if not 会话标识:
        return _控制台错误(400, "参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        if not await _控制台线程执行(消息记录.设置会话置顶, 会话标识, 置顶):
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
    if not 会话标识:
        return _控制台错误(400, "参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        消息记录.设置会话已读(会话标识)
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
    if not 会话标识:
        return _控制台错误(400, "会话参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await 消息记录.获取群角色(会话标识, str((数据 or {}).get("appid") or ""))
        return web.json_response({"ok": True, **结果}, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台群角色读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "群角色暂时不可用")


async def _处理群备注(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    会话标识 = str((数据 or {}).get("chat_id") or "").strip()
    if not 会话标识:
        return _控制台错误(400, "会话参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        if (数据 or {}).get("action") == "get":
            结果 = {
                "remark": 消息记录.获取群备注(会话标识),
                "group_qq": 消息记录.获取群QQ号(会话标识),
            }
            return web.json_response({"ok": True, **结果})
        if (数据 or {}).get("action") == "delete":
            if not await _控制台线程执行(消息记录.删除群备注, 会话标识):
                return _控制台错误(409, "备注删除失败")
            清理消息列表缓存()
            return web.json_response({"ok": True, "message": "备注已删除"})
        备注 = str((数据 or {}).get("remark") or "").strip()
        群QQ = str((数据 or {}).get("group_qq") or "").strip()
        if not await _控制台线程执行(消息记录.保存群备注, 会话标识, 备注, 群QQ):
            return _控制台错误(409, "备注保存失败")
        清理消息列表缓存()
        return web.json_response({"ok": True, "message": "备注已保存"})
    except Exception as exc:
        logger.warning("帮助控制台群备注保存失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "备注保存失败")


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
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    数据 = 数据 if isinstance(数据, dict) else {}
    会话标识 = str(数据.get("chat_id") or "").strip()
    会话类型 = str(数据.get("chat_type") or "group").strip().lower()
    if not 会话标识 or len(会话标识) > 200 or 会话类型 != "group":
        return _控制台错误(400, "只支持 QQ 官方群会话")
    try:
        from 功能文件.管理功能.群聊功能 import 群管功能

        if str(数据.get("action") or "get").strip().lower() == "get":
            开启 = await _控制台线程执行(
                群管功能.读取群广告开关,
                当前帮助网页配置,
                会话标识,
            )
            return web.json_response(
                {
                    "ok": True,
                    "enabled": bool(开启),
                    "editable": bool(群管功能.群广告开关可持久化(当前帮助网页配置)),
                    "platform": "qq_official",
                },
                headers={"Cache-Control": "no-store"},
            )

        原始状态 = 数据.get("enabled")
        if not isinstance(原始状态, bool):
            return _控制台错误(400, "广告开关参数无效")
        if not 群管功能.群广告开关可持久化(当前帮助网页配置):
            return _控制台错误(409, "数据库未配置，广告开关无法保存")
        成功 = await _控制台线程执行(
            群管功能.写入群广告开关,
            当前帮助网页配置,
            会话标识,
            原始状态,
        )
        if not 成功:
            return _控制台错误(409, "广告开关保存失败，请稍后再试")
        return web.json_response(
            {
                "ok": True,
                "enabled": bool(原始状态),
                "editable": True,
                "platform": "qq_official",
            },
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        logger.warning("帮助控制台群广告开关失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "广告开关暂时不可用")
