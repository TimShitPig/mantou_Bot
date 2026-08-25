from __future__ import annotations

import asyncio
import copy
import hmac
import inspect
import ipaddress
import json
import logging
import re
import secrets
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiohttp import web

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)

默认监听地址 = "0.0.0.0"
默认监听端口 = 8090
控制台版本 = "5.45.2"
默认控制台用户名 = "admin"
默认控制台密码 = ""
控制台会话Cookie名 = "mantou_console_session"
控制台会话有效期 = 12 * 60 * 60


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
    "baidu_pan_upload_status": {
        "category": "baidu_pan_settings",
        "label": "百度后台备份状态",
        "kind": "select",
        "secret": False,
        "options": ["完结", "连载", "全部"],
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
    return callable(getattr(配置, "save_config", None))


async def _持久化插件配置() -> None:
    配置 = 当前帮助网页配置
    保存方法 = getattr(配置, "save_config", None)
    if not callable(保存方法):
        raise RuntimeError("插件配置没有持久化接口")
    结果 = 保存方法()
    if inspect.isawaitable(结果):
        await 结果


def _读取插件配置摘要() -> dict[str, Any]:
    配置 = 当前帮助网页配置
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
    if 定义.get("secret"):
        文本 = str(值 or "").strip()
        if not 文本:
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
    if 字段名 == "baidu_pan_upload_status" and 文本 not in {"完结", "连载", "全部"}:
        raise ValueError("百度备份状态无效")
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


def _清理控制台会话() -> None:
    截止时间 = time.time()
    for 会话值, 到期时间 in list(控制台会话.items()):
        if 到期时间 <= 截止时间:
            控制台会话.pop(会话值, None)
            控制台会话身份.pop(会话值, None)


def _取得请求会话(request: web.Request) -> str:
    _清理控制台会话()
    return str(request.cookies.get(控制台会话Cookie名) or "").strip()


def _请求已授权(request: web.Request) -> bool:
    会话值 = _取得请求会话(request)
    到期时间 = 控制台会话.get(会话值)
    if not 会话值 or 到期时间 is None or 到期时间 <= time.time():
        控制台会话.pop(会话值, None)
        return False
    控制台会话[会话值] = time.time() + 控制台会话有效期
    return True


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
    控制台会话[会话值] = time.time() + 控制台会话有效期
    控制台会话身份[会话值] = 配置用户名
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
    响应 = web.json_response({"ok": True})
    响应.del_cookie(控制台会话Cookie名, path="/")
    return 响应


def _读取控制台数据(登录用户名: str = "") -> dict[str, Any]:
    from 功能文件.管理功能.基础功能 import 状态功能
    from 功能文件.管理功能.基础功能.运行状态数据库 import (
        已配置运行状态数据库,
        检查运行状态数据库,
    )
    from 功能文件.管理功能.网盘功能 import UC网盘, 夸克网盘, 百度网盘, 网盘Cookie, 小说网盘
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
    状态 = 小说功能开关.读取小说功能状态(配置)
    平台列表 = [
        {
            "key": 功能名,
            "name": 小说功能开关.功能显示名.get(功能名, 功能名),
            "enabled": bool(状态.get(功能名, True)),
        }
        for 功能名 in 小说功能开关.默认状态
    ]
    网盘定义 = (
        ("UC", "UC网盘", UC网盘.UC网盘是否启用, UC网盘.读取UC上传目录),
        ("夸克", "夸克网盘", 夸克网盘.夸克网盘是否启用, 夸克网盘.读取夸克上传目录),
        ("百度", "百度网盘", 百度网盘.百度网盘是否启用, 百度网盘.读取百度上传目录),
    )
    网盘列表 = []
    当前网盘 = 小说网盘.获取当前主网盘(配置)
    for 标识, 名称, 是否启用, 读取目录 in 网盘定义:
        try:
            已配置 = bool(是否启用(配置))
            账号数量 = 网盘Cookie.获取网盘账号数量(配置, 标识)
            账号摘要 = 网盘Cookie.获取网盘账号摘要(配置, 标识)
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
                "active": 标识 == 当前网盘,
                "selected_account": int(
                    网盘Cookie.获取当前网盘账号序号(配置, 标识)
                ),
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
            "global_enabled": 小说功能开关.小说总开关是否开启(配置),
            "test_mode": 小说功能开关.管理员测试模式是否开启(配置),
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
        数据 = await asyncio.to_thread(
            _读取控制台数据, _读取当前控制台身份(request)
        )
        return web.json_response(数据, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台数据读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "控制台数据暂时不可用")


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
        await asyncio.to_thread(_写入)
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

    def _写入() -> None:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值

        写入运行状态值(当前帮助网页配置, "novel_share_pan", "active", 网盘名)

    try:
        await asyncio.to_thread(_写入)
        return web.json_response({"ok": True})
    except Exception as exc:
        logger.warning("帮助控制台主网盘切换失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "主网盘保存失败，请检查数据库配置")


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
    try:
        配置字典 = _读取插件配置字典(当前帮助网页配置)
        原配置快照 = copy.deepcopy(配置字典) if isinstance(配置字典, dict) else None
        待更新: list[tuple[str, dict[str, Any], Any]] = []
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
        # 先完整校验，再一次性写入，避免同一请求中后续字段失败时留下半套配置。
        for 字段名, 定义, 值 in 待更新:
            _设置插件配置值(
                当前帮助网页配置,
                str(定义["category"]),
                字段名,
                值,
            )
            已更新.append(字段名)
        if 已更新 and _插件配置可持久化(当前帮助网页配置):
            await _持久化插件配置()
        elif 已更新 and not isinstance(当前帮助网页配置, dict):
            raise RuntimeError("插件配置没有持久化接口")
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
        logger.warning("帮助控制台插件配置保存失败：错误类型=%s", type(exc).__name__)
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
        摘要 = await asyncio.to_thread(
            网盘Cookie.获取网盘账号摘要, 当前帮助网页配置, 平台
        )
        当前序号 = await asyncio.to_thread(
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
        序号 = await asyncio.to_thread(
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

        成功, _ = await asyncio.to_thread(
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

        成功, _ = await asyncio.to_thread(
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
        await asyncio.to_thread(QQ阅读._保存QQ阅读登录态, 当前帮助网页配置, 登录态)
        await asyncio.to_thread(QQ阅读._应用QQ阅读登录态, 登录态)
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
        每页 = int((数据 or {}).get("page_size") or 50)
    except (TypeError, ValueError):
        每页 = 50
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await asyncio.to_thread(
            消息记录.获取聊天列表, 过滤, 搜索, 页码, 每页
        )
        try:
            asyncio.create_task(消息记录.刷新待处理群信息())
        except Exception:
            pass
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
        limit = int((数据 or {}).get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    if not 会话标识 or len(会话标识) > 200:
        return _控制台错误(400, "会话参数无效")
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        结果 = await asyncio.to_thread(
            消息记录.获取消息历史, 会话标识, 类型, before_date, limit
        )
        try:
            asyncio.create_task(消息记录.刷新待处理群信息())
        except Exception:
            pass
        return web.json_response({"ok": True, **结果}, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台消息历史读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "消息历史暂时不可用")


async def _处理消息发送(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    数据 = await _读取请求JSON(request)
    if not 数据:
        return _控制台错误(400, "请求参数无效")
    会话标识 = str(数据.get("chat_id") or "").strip()
    会话类型 = str(数据.get("chat_type") or "")
    消息类型 = str(数据.get("msg_type") or "text")
    内容 = str(数据.get("content") or "")
    if not 会话标识 or len(会话标识) > 200:
        return _控制台错误(400, "会话参数无效")
    try:
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
             图片路径=str(数据.get("image") or ""),
             图片数据=str(数据.get("image_data") or ""),
             媒体路径=str(数据.get("media") or ""),
             媒体URL=str(数据.get("media_url") or ""),
             媒体文件类型=int(数据.get("media_file_type") or 1),
            ARK模板ID=str(数据.get("ark_template_id") or ""),
            ARK字段=数据.get("ark_fields") if isinstance(数据.get("ark_fields"), dict) else None,
            ARK列表=str(数据.get("ark_list") or ""),
            卡片字段=数据.get("card") if isinstance(数据.get("card"), dict) else None,
        )
        if not 结果.get("ok"):
            return _控制台错误(409, str(结果.get("message") or "发送失败"))
        return web.json_response({"ok": True, **结果})
    except Exception as exc:
        logger.warning("帮助控制台消息发送失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "发送失败，请稍后再试")


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

        结果 = await 消息记录.撤回消息(会话标识, 消息ID, str((数据 or {}).get("appid") or ""))
        if not 结果.get("ok"):
            return _控制台错误(409, str(结果.get("message") or "撤回失败"))
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
            await asyncio.to_thread(消息记录.删除群备注, 会话标识)
            return web.json_response({"ok": True, "message": "备注已删除"})
        备注 = str((数据 or {}).get("remark") or "").strip()
        群QQ = str((数据 or {}).get("group_qq") or "").strip()
        await asyncio.to_thread(消息记录.保存群备注, 会话标识, 备注, 群QQ)
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

        结果 = await 消息记录.刷新群信息(会话标识, str((数据 or {}).get("appid") or ""))
        if 结果 is None:
            return _控制台错误(409, "群信息刷新失败")
        return web.json_response({"ok": True, **结果})
    except Exception as exc:
        logger.warning("帮助控制台群信息刷新失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(409, "群信息刷新失败")



def _渲染控制台页面() -> str:
    return _网页头部 + _网页主体 + _网页脚本


_网页头部 = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f8f8ff">
  <title>馒头控制台</title>
  <style>
    :root { color-scheme: light; --ink:#24243a; --muted:#7d8096; --soft:#a8abc0; --line:#e8e9f2; --bg:#f7f8fd; --panel:#fff; --primary:#6b63f5; --primary-dark:#574eea; --primary-soft:#f0efff; --mint:#e9fbf3; --mint-ink:#319e6b; --peach:#fff3ed; --peach-ink:#d77755; --yellow:#fff9e5; --yellow-ink:#bd8a23; --pink:#fff0f7; --pink-ink:#c66791; --shadow:0 10px 30px rgba(60,57,112,.06); }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.55 Inter,"PingFang SC","Microsoft YaHei",ui-sans-serif,system-ui,sans-serif; overflow-x:hidden; }
    button,input { font:inherit; }
    button { cursor:pointer; }
    .shell { min-height:100vh; display:grid; grid-template-columns:252px minmax(0,1fr); grid-template-rows:64px minmax(0,1fr); grid-template-areas:"top top" "side main"; }
    .topbar { grid-area:top; display:flex; align-items:center; justify-content:space-between; gap:20px; padding:0 30px; background:#fff; border-bottom:1px solid var(--line); }
    .brand { display:flex; align-items:center; gap:10px; min-width:0; }
    .brand-mark { width:34px; height:34px; display:grid; place-items:center; border-radius:11px; background:var(--primary-soft); color:var(--primary); font-size:16px; font-weight:800; }
    .brand strong { font-size:16px; letter-spacing:.1px; }
    .version-badge { display:inline-flex; margin-left:7px; padding:3px 8px; border-radius:999px; background:#f3f3f8; color:var(--muted); font-size:11px; font-weight:650; }
    .top-actions { display:flex; align-items:center; gap:16px; }
    .status-dot { display:inline-flex; align-items:center; gap:7px; color:var(--mint-ink); font-size:12px; font-weight:650; }
    .status-dot::before { content:""; width:7px; height:7px; border-radius:50%; background:#4dbb82; box-shadow:0 0 0 4px var(--mint); }
    .admin-menu { position:relative; }
    .admin-chip { display:inline-flex; align-items:center; gap:8px; min-height:36px; padding:4px 8px 4px 5px; border:1px solid transparent; border-radius:9px; background:transparent; color:var(--ink); font-size:13px; font-weight:650; transition:background .18s ease,border-color .18s ease; }
    .admin-chip:hover,.admin-chip[aria-expanded="true"] { border-color:#e5e3f7; background:#fbfaff; }
    .admin-avatar { width:28px; height:28px; display:grid; place-items:center; border-radius:50%; background:#f0efff; color:var(--primary); font-size:12px; font-weight:800; }
    #admin-name { max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .admin-chevron { color:var(--soft); font-size:13px; }
    .admin-popover { position:absolute; z-index:5; top:calc(100% + 8px); right:0; width:220px; padding:13px 14px; border:1px solid var(--line); border-radius:10px; background:#fff; box-shadow:0 12px 30px rgba(60,57,112,.12); }
    .admin-popover[hidden] { display:none; }
    .admin-popover strong { display:block; font-size:13px; }
    .admin-popover small { display:block; margin-top:5px; color:var(--muted); font-size:11px; line-height:1.45; }
    .popover-logout { display:block; width:100%; margin-top:10px; padding:7px 10px; border:1px solid var(--line); border-radius:7px; background:#fff; color:var(--danger,#d64545); font-size:12px; cursor:pointer; text-align:center; }
    .popover-logout:hover { background:#fdf2f2; border-color:#e8b8b8; }
    .sidebar { grid-area:side; min-width:0; background:#fff; border-right:1px solid var(--line); padding:24px 14px 18px; display:flex; flex-direction:column; gap:24px; }
    .profile { display:grid; justify-items:center; gap:7px; padding:4px 0 8px; }
    .bot-avatar { position:relative; width:72px; height:72px; overflow:hidden; border:5px solid #f3f2ff; border-radius:50%; background:#e9eaff; box-shadow:0 5px 14px rgba(92,87,210,.12); }
    .bot-avatar::before { content:""; position:absolute; width:62px; height:58px; left:0; top:5px; border-radius:50% 50% 42% 42%; background:#a2a5f7; }
    .bot-avatar::after { content:"✦"; position:absolute; right:7px; top:4px; color:#fff; font-size:13px; }
    .avatar-face { position:absolute; left:16px; top:27px; z-index:1; color:#4f50a8; font-size:23px; letter-spacing:5px; }
    .profile strong { font-size:14px; }
    .online { display:inline-flex; align-items:center; gap:5px; color:var(--mint-ink); font-size:12px; }
    .online::before { content:""; width:6px; height:6px; border-radius:50%; background:#4dbb82; }
    .nav-label { margin:0 10px 8px; color:#afb1c1; font-size:10px; font-weight:800; letter-spacing:1px; text-transform:uppercase; }
    .nav { display:grid; gap:5px; }
    .nav a { display:flex; align-items:center; gap:11px; padding:11px 12px; border-radius:9px; color:#55586d; text-decoration:none; transition:background .18s ease,color .18s ease,transform .18s ease,box-shadow .18s ease; }
    .nav a:hover { transform:translateX(3px); }
    .nav a:hover,.nav a.active,.nav a[aria-current="true"] { background:var(--primary-soft); color:var(--primary-dark); }
    .nav-icon { width:18px; color:#777a90; text-align:center; font-size:16px; }
    .nav a.active .nav-icon,.nav a[aria-current="true"] .nav-icon { color:var(--primary); }
    .nav a:focus-visible,.refresh:focus-visible,.switch:focus-visible,.pan-select:focus-visible { outline:3px solid #c9c6ff; outline-offset:2px; }
    .sidebar-foot { margin-top:auto; padding:14px 13px; border:1px solid #ebeaf4; border-radius:11px; background:#fbfbff; color:var(--muted); font-size:11px; }
    .sidebar-foot strong { display:block; margin-bottom:5px; color:var(--ink); font-size:13px; }
    .sidebar-foot .spark { color:var(--primary); font-size:16px; }
    .main { grid-area:main; min-width:0; background:var(--bg); }
    .content { width:min(1500px,calc(100% - 50px)); margin:0 auto; padding:34px 0 60px; }
    .page-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; }
    .page-kicker { margin:0 0 4px; color:var(--primary); font-size:12px; font-weight:750; }
    .page-heading h1 { margin:0; font-size:25px; letter-spacing:-.2px; }
    .page-heading p { margin:5px 0 0; color:var(--muted); font-size:13px; }
    .notice { display:none; margin:18px 0; padding:13px 15px; border:1px solid #f1df9b; border-radius:10px; background:var(--yellow); color:#8b681c; }
    .notice.show { display:block; }
    .primary-button { display:inline-flex; align-items:center; gap:7px; min-height:38px; border:0; border-radius:9px; padding:0 15px; background:var(--primary); color:#fff; font-size:12px; font-weight:700; box-shadow:0 6px 16px rgba(107,99,245,.18); }
    .primary-button:hover { background:var(--primary-dark); }
    .button-icon { font-size:15px; line-height:1; }
    .metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; margin:27px 0 30px; }
    .metric { min-height:104px; padding:17px 18px; background:var(--panel); border:1px solid var(--line); border-radius:11px; box-shadow:var(--shadow); }
    .metric:nth-child(1) { background:#fbfaff; }
    .metric:nth-child(2) { background:#fbfffd; }
    .metric:nth-child(3) { background:#fffdfa; }
    .metric:nth-child(4) { background:#fffafd; }
    .metric-label { color:var(--muted); font-size:12px; }
    .metric-value { margin-top:11px; color:var(--ink); font-size:22px; font-weight:750; }
    .metric-meta { margin-top:4px; color:var(--muted); font-size:11px; }
    .section { margin-top:28px; scroll-margin-top:82px; }
    .section-head { display:flex; align-items:flex-end; justify-content:space-between; gap:15px; margin-bottom:11px; }
    .section-head h2 { margin:0; font-size:17px; }
    .section-head p { margin:3px 0 0; color:var(--muted); font-size:12px; }
    .section-link { color:var(--primary); font-size:12px; font-weight:650; text-decoration:none; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:11px; box-shadow:var(--shadow); overflow:hidden; }
    .global-bar { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:16px 19px; border-bottom:1px solid var(--line); background:#fcfbff; }
    .global-actions { display:flex; align-items:center; gap:18px; flex:0 0 auto; }
    .test-mode { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; white-space:nowrap; }
    .global-copy strong { display:block; font-size:14px; }
    .global-copy span { display:block; margin-top:2px; color:var(--muted); font-size:12px; }
    .switch { position:relative; width:42px; height:24px; flex:0 0 auto; border:0; border-radius:999px; background:#d7d8e4; transition:background .18s ease; }
    .switch span { position:absolute; top:3px; left:3px; width:18px; height:18px; border-radius:50%; background:#fff; box-shadow:0 1px 3px #0002; transition:transform .18s ease; }
    .switch.on { background:var(--primary); }
    .switch.on span { transform:translateX(18px); }
    .switch:disabled { cursor:not-allowed; opacity:.45; }
    .novel-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); }
    .novel-item { display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:73px; padding:15px 18px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); }
    .novel-item:nth-child(3n) { border-right:0; }
    .novel-item:nth-last-child(-n+3) { border-bottom:0; }
    .novel-name { display:flex; align-items:center; gap:10px; min-width:0; }
    .novel-badge { width:29px; height:29px; display:grid; place-items:center; border-radius:9px; background:var(--primary-soft); color:var(--primary); font-size:12px; font-weight:800; }
    .novel-item:nth-child(3n+2) .novel-badge { background:var(--mint); color:var(--mint-ink); }
    .novel-item:nth-child(3n) .novel-badge { background:var(--peach); color:var(--peach-ink); }
    .novel-name strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .novel-name small { display:block; margin-top:2px; color:var(--muted); font-size:11px; }
    .pan-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:13px; }
    .pan-card { padding:18px; border:1px solid var(--line); border-radius:11px; background:var(--panel); box-shadow:var(--shadow); }
    .pan-card.active { border-color:#c4c0ff; box-shadow:0 0 0 2px #eeecff inset, var(--shadow); }
    .pan-top { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }
    .pan-title { display:flex; align-items:center; gap:9px; }
    .pan-logo { width:31px; height:31px; display:grid; place-items:center; border-radius:9px; background:var(--primary-soft); color:var(--primary); font-weight:800; }
    .pan-title strong { font-size:14px; }
    .tag { display:inline-flex; padding:3px 7px; border-radius:999px; font-size:10px; font-weight:700; }
    .tag.active { background:var(--primary-soft); color:var(--primary-dark); }
    .tag.ok { background:var(--mint); color:var(--mint-ink); }
    .tag.off { background:#f2f4f7; color:#667085; }
    .pan-meta { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:20px 0 14px; }
    .pan-meta span { display:block; color:var(--muted); font-size:11px; }
    .pan-meta strong { display:block; margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .account-list { display:grid; gap:6px; margin:0 0 14px; }
    .account-row { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 9px; border:1px solid #eef0f3; border-radius:6px; background:#fbfcfe; color:var(--muted); font-size:11px; }
    .account-row strong { color:var(--ink); font-size:12px; font-weight:650; }
    .account-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pan-select { width:100%; min-height:40px; border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink); padding:8px 10px; }
    .pan-select:disabled { color:#98a2b3; cursor:not-allowed; }
    .runtime-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }
    .runtime-item { padding:14px 15px; border:1px solid var(--line); border-radius:10px; background:var(--panel); box-shadow:var(--shadow); }
    .runtime-item span { display:block; color:var(--muted); font-size:11px; }
    .runtime-item strong { display:block; margin-top:7px; font-size:14px; }
    .config-list { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); }
    .config-item { padding:15px 18px; border-right:1px solid var(--line); }
    .config-item:last-child { border-right:0; }
    .config-item span { display:block; color:var(--muted); font-size:11px; }
    .config-item strong { display:block; margin-top:5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .toast { position:fixed; right:22px; bottom:22px; z-index:10; transform:translateY(12px); opacity:0; pointer-events:none; padding:11px 14px; border-radius:9px; background:#353250; color:#fff; box-shadow:0 8px 25px rgba(48,45,90,.22); transition:opacity .2s,transform .2s; }
    .toast.show { transform:translateY(0); opacity:1; }
    .empty { padding:30px; color:var(--muted); text-align:center; }
    @media (max-width:1050px) { .metrics { grid-template-columns:repeat(2,1fr); } .runtime-grid { grid-template-columns:repeat(3,1fr); } .config-list { grid-template-columns:repeat(2,1fr); } .config-item { border-right:1px solid var(--line); border-bottom:1px solid var(--line); } .config-item:nth-child(2n) { border-right:0; } .config-item:nth-last-child(-n+2) { border-bottom:0; } }
     @media (max-width:760px) { .shell { display:block; } .topbar { min-height:62px; padding:12px 15px; } .brand strong { font-size:14px; } .top-actions { gap:8px; } .admin-chip { font-size:12px; } .status-dot { display:none; } .sidebar { padding:10px 12px 8px; border-right:0; border-bottom:1px solid var(--line); gap:10px; } .profile { display:flex; align-items:center; justify-content:flex-start; gap:9px; padding:0 2px; } .bot-avatar { width:38px; height:38px; border-width:3px; } .bot-avatar::before { width:34px; height:32px; top:2px; } .avatar-face { left:8px; top:12px; font-size:12px; letter-spacing:2px; } .bot-avatar::after { right:2px; top:1px; font-size:8px; } .profile strong { font-size:13px; } .online { margin-left:-3px; } .nav-label,.sidebar-foot { display:none; } .nav { display:flex; gap:4px; overflow-x:auto; scrollbar-width:none; } .nav::-webkit-scrollbar { display:none; } .nav a { flex:0 0 auto; padding:8px 10px; } .content { width:calc(100% - 28px); padding:23px 0 40px; } .page-heading h1 { font-size:21px; } .page-heading p { font-size:12px; } .primary-button { min-height:34px; padding:0 11px; } .metrics,.pan-grid { grid-template-columns:1fr; } .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .novel-item:nth-child(3n) { border-right:1px solid var(--line); } .novel-item:nth-child(2n) { border-right:0; } .novel-item:nth-last-child(-n+3),.novel-item:last-child,.novel-item:nth-last-child(2) { border-bottom:1px solid var(--line); } .global-bar { align-items:flex-start; } .global-actions { gap:10px; } .test-mode span { max-width:68px; white-space:normal; line-height:1.2; } .runtime-grid { grid-template-columns:repeat(2,1fr); } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { padding:13px; border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
     /* Screenshot-inspired configuration workspace. The data/API contract stays unchanged. */
     .shell { grid-template-columns:248px minmax(0,1fr); grid-template-rows:62px minmax(0,1fr); }
     .topbar { padding:0 30px; }
     .brand-mark { width:36px; height:36px; border-radius:50%; background:#e9e9ff; color:#5d58d8; border:3px solid #f5f4ff; font-size:13px; }
     .brand strong { font-size:17px; }
     .sidebar { padding:28px 18px 18px; gap:25px; }
     .profile { gap:8px; padding-bottom:13px; }
     .bot-avatar { width:76px; height:76px; }
     .nav-label { margin:0 12px 8px; font-size:11px; letter-spacing:0; text-transform:none; color:#a0a2b5; }
     .nav { gap:4px; }
     .nav a { min-height:40px; padding:10px 12px; border-radius:8px; font-size:13px; }
     .nav-icon { width:19px; font-size:15px; }
     .sidebar-foot { border-radius:8px; background:#f5f6fb; padding:15px 13px; line-height:1.65; }
     .main { background:#f7f8fc; }
     .content { width:min(1300px,calc(100% - 44px)); padding:38px 0 65px; }
     .page-kicker { display:none; }
     .page-heading h1 { font-size:24px; letter-spacing:0; }
     .page-heading p { margin-top:6px; font-size:13px; }
     .primary-button { min-height:40px; border-radius:7px; padding:0 17px; }
     .notice { margin:14px 0 0; border-radius:7px; }
     .metrics { display:none; }
     .workspace-grid { display:grid; grid-template-columns:minmax(0,1.62fr) minmax(310px,.96fr); align-items:start; gap:16px; margin-top:17px; }
     .workspace-left,.workspace-right { display:grid; gap:16px; align-content:start; min-width:0; }
     .console-card { margin:0; padding:21px 21px 20px; background:#fff; border:1px solid var(--line); border-radius:8px; box-shadow:0 5px 18px rgba(55,59,103,.045); scroll-margin-top:80px; }
     .console-card h2 { margin:0; font-size:15px; }
     .card-subtitle { margin:4px 0 18px; color:var(--muted); font-size:12px; }
     .profile-fields { display:grid; gap:0; }
     .profile-field { display:grid; grid-template-columns:112px minmax(0,1fr); align-items:center; gap:16px; min-height:58px; border-bottom:1px solid #f0f1f5; }
     .profile-field:last-child { border-bottom:0; }
     .profile-field > span { color:#55586d; font-size:13px; }
     .readonly-value { min-height:38px; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 11px; border:1px solid #e4e6ee; border-radius:7px; color:var(--ink); background:#fff; }
     .readonly-value small { color:#a1a4b4; font-size:11px; }
     .avatar-inline { display:flex; align-items:center; gap:10px; }
     .avatar-inline .bot-avatar { width:43px; height:43px; border-width:3px; }
     .avatar-inline .bot-avatar::before { width:37px; height:35px; top:3px; }
     .avatar-inline .avatar-face { left:9px; top:14px; font-size:13px; letter-spacing:2px; }
     .avatar-inline .bot-avatar::after { right:3px; top:1px; font-size:9px; }
     .avatar-inline small { color:var(--muted); font-size:11px; }
     .state-line { display:flex; align-items:center; gap:10px; }
     .state-line .online { font-size:12px; }
     .connection-fields { display:grid; gap:12px; }
     .connection-row { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:12px 0; border-bottom:1px solid #f0f1f5; }
     .connection-row:last-child { border-bottom:0; padding-bottom:0; }
     .connection-row:first-child { padding-top:0; }
     .connection-row > span { color:#55586d; font-size:12px; }
     .connection-row strong { max-width:66%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink); font-size:12px; font-weight:600; text-align:right; }
     .module-card { padding:21px 0 0; overflow:hidden; }
     .module-card h2,.module-card .card-subtitle { margin-left:21px; margin-right:21px; }
     .module-card .global-bar { padding:14px 21px; border-top:1px solid #f0f1f5; background:#fcfbff; }
     .module-card .novel-grid { grid-template-columns:1fr; }
     .module-card .novel-item { min-height:51px; padding:10px 21px; border-right:0; }
     .module-card .novel-item:nth-last-child(-n+3) { border-bottom:1px solid var(--line); }
     .module-card .novel-item:last-child { border-bottom:0; }
     .module-card .novel-badge { width:26px; height:26px; border-radius:7px; }
     .module-card .novel-name strong { font-size:12px; }
     .module-card .novel-name small { font-size:10px; }
     .module-card .switch { transform:scale(.88); transform-origin:right center; }
     .status-card { padding-bottom:13px; }
     .status-card .status-list { display:grid; gap:0; margin-top:10px; }
     .status-item { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:9px 0; border-bottom:1px solid #f0f1f5; font-size:12px; }
     .status-item:last-child { border-bottom:0; }
     .status-item span { color:#65687b; }
     .status-item strong { color:var(--ink); font-weight:600; text-align:right; }
     .status-item strong.good { color:var(--mint-ink); }
     .test-card { padding-bottom:17px; }
     .test-bubble { display:flex; align-items:flex-start; gap:9px; margin-top:14px; }
     .test-mini-avatar { width:28px; height:28px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:#e9e9ff; color:#5c58d8; font-size:11px; font-weight:800; }
     .test-bubble p { margin:0; padding:9px 11px; border-radius:5px 10px 10px 10px; background:#f0f1f7; color:#65687b; font-size:11px; line-height:1.55; }
     .test-hint { margin:13px 0 0; color:#a0a2b5; font-size:11px; }
     .pan-section { margin-top:16px; }
     .pan-section .section-head { margin:0 0 10px; }
     .pan-tabs { display:flex; gap:8px; margin:0 24px 16px; padding:4px; border:1px solid #e8e8f4; border-radius:9px; background:#fafaff; }
     .pan-tab { flex:1 1 0; min-width:0; min-height:38px; padding:0 14px; border:0; border-radius:7px; background:transparent; color:#777992; font-size:12px; font-weight:700; white-space:nowrap; transition:color .18s ease,background .18s ease,box-shadow .18s ease; }
     .pan-tab:hover { color:var(--primary-dark); background:#f2f1ff; }
     .pan-tab.active { color:var(--primary-dark); background:#fff; box-shadow:0 2px 8px rgba(72,68,146,.1); }
     .pan-tab:focus-visible { outline:2px solid #aaa0e7; outline-offset:2px; }
     .pan-grid { grid-template-columns:1fr; }
     .pan-card[hidden] { display:none !important; }
     .pan-console { padding:22px 0 24px; overflow:visible; }
     .pan-console > h2,.pan-console > .card-subtitle { margin-left:24px; margin-right:24px; }
     .pan-console .pan-note { margin-left:24px; margin-right:24px; }
     .pan-console .pan-grid { padding:0 24px; }
     .pan-console .pan-card { min-width:0; padding:20px; transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease; }
     .pan-console .pan-card:hover { transform:translateY(-2px); }
     .runtime-grid { display:none; }
     .config-list { grid-template-columns:repeat(2,minmax(0,1fr)); border-radius:7px; box-shadow:none; }
     .config-item { min-height:64px; padding:13px 15px; border-bottom:1px solid var(--line); }
     .config-item:nth-child(2n) { border-right:0; }
     .config-item:nth-last-child(-n+2) { border-bottom:0; }
     .config-section { margin-top:16px; }
     .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
     @media (max-width:1050px) { .workspace-grid { grid-template-columns:minmax(0,1.35fr) minmax(280px,.9fr); } .pan-grid { grid-template-columns:1fr; } }
     @media (max-width:760px) { .pan-console { padding-top:18px; } .pan-console > h2,.pan-console > .card-subtitle,.pan-console .pan-note { margin-left:17px; margin-right:17px; } .pan-console .pan-tabs { margin-left:17px; margin-right:17px; gap:6px; overflow-x:auto; scrollbar-width:none; } .pan-console .pan-tabs::-webkit-scrollbar { display:none; } .pan-console .pan-tab { flex:0 0 auto; min-width:92px; padding:0 12px; } .pan-console .pan-grid { padding:0 17px; } }
     @media (max-width:760px) { .content { width:calc(100% - 28px); padding:23px 0 40px; } .workspace-grid { grid-template-columns:1fr; } .workspace-right { order:-1; } .module-card .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .module-card .novel-item { border-right:1px solid var(--line); } .module-card .novel-item:nth-child(2n) { border-right:0; } .module-card .novel-item:nth-last-child(-n+2) { border-bottom:0; } .profile-field { grid-template-columns:92px minmax(0,1fr); gap:10px; } .connection-row strong { max-width:58%; } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
     .page-view[hidden] { display:none !important; }
     .page-view { min-width:0; scroll-margin-top:82px; }
     .heading-actions { display:flex; align-items:center; gap:12px; }
     .updated-label { color:var(--muted); font-size:11px; white-space:nowrap; }
     .summary-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; margin-top:18px; }
     .summary-card { min-height:168px; display:flex; flex-direction:column; align-items:flex-start; padding:17px 18px; background:#fff; border:1px solid var(--line); border-radius:8px; box-shadow:0 5px 18px rgba(55,59,103,.045); }
     .summary-card > span { color:var(--muted); font-size:12px; }
     .summary-card > strong { margin-top:12px; color:var(--ink); font-size:21px; }
     .summary-card > small { min-height:18px; margin-top:4px; color:var(--muted); font-size:11px; }
     .text-button { display:block; margin-top:auto; padding:0; color:var(--primary); font-size:12px; font-weight:700; text-align:left; }
     .text-button:hover { color:var(--primary-dark); }
     .page-grid { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(280px,.9fr); gap:16px; margin-top:16px; }
     .page-grid .console-card { min-width:0; }
     .page-view-head { margin-top:18px; margin-bottom:0; }
     .shortcut-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
     .shortcut-card { min-height:94px; display:grid; grid-template-columns:30px minmax(0,1fr); grid-template-rows:auto auto; column-gap:10px; align-items:center; padding:13px; border:1px solid #e8e9f2; border-radius:7px; background:#fff; color:var(--ink); text-align:left; }
     .shortcut-card:hover { border-color:#c9c6ff; background:#fbfaff; }
     .shortcut-icon { grid-row:1 / span 2; width:30px; height:30px; display:grid; place-items:center; border-radius:8px; background:var(--primary-soft); color:var(--primary); font-size:14px; }
     .shortcut-card strong { font-size:12px; }
     .shortcut-card small { color:var(--muted); font-size:10px; line-height:1.45; }
     .compact-status { margin-top:8px; }
     .outline-button { min-height:36px; padding:0 16px; border:1px solid #c9c6ff; border-radius:7px; background:#fff; color:var(--primary-dark); font-size:12px; font-weight:700; }
     .outline-button:hover { background:var(--primary-soft); }
     .standalone-card { margin-top:18px; }
     .standalone-card > h2 { font-size:18px; }
     .module-heading { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:18px 0 10px; }
     .module-heading h3 { margin:0; font-size:13px; }
     .module-heading span { color:var(--muted); font-size:11px; }
     .pan-note { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:16px 0; padding:13px 15px; border:1px solid #e9e8f7; border-radius:7px; background:#fbfaff; }
     .pan-note span { color:var(--muted); font-size:12px; }
     .pan-note strong { color:var(--primary-dark); font-size:13px; }
     .runtime-page-grid { display:grid !important; grid-template-columns:repeat(5,minmax(0,1fr)); margin-top:18px; }
     .runtime-detail { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:16px; }
     .runtime-detail .status-item { padding:13px; border:1px solid var(--line); border-radius:7px; background:#fbfcff; }
     .safe-list,.settings-list { display:grid; gap:0; }
     .safe-list > div,.settings-row { display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:50px; border-bottom:1px solid #f0f1f5; font-size:12px; }
     .safe-list > div:last-child,.settings-row:last-child { border-bottom:0; }
     .safe-list span,.settings-row span { color:#65687b; }
     .safe-list strong,.settings-row strong { color:var(--ink); font-weight:600; text-align:right; }
     .settings-row strong { max-width:65%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
     .config-editor { display:grid; gap:18px; }
     .config-group { padding:16px; border:1px solid #eef0f5; border-radius:8px; background:#fcfcff; }
     .config-group h3 { margin:0 0 13px; font-size:13px; }
     .config-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px 15px; }
     .config-field { display:grid; gap:6px; min-width:0; }
     .config-field.full { grid-column:1 / -1; }
     .config-field label { color:#65687b; font-size:11px; font-weight:700; }
     .config-field input,.config-field textarea,.config-field select,.account-add input,.group-account input { width:100%; min-height:39px; padding:8px 10px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); outline:none; }
     .config-field textarea { min-height:74px; resize:vertical; }
     .config-field input:focus,.config-field textarea:focus,.config-field select:focus,.account-add input:focus,.group-account input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
     .config-field small,.secret-hint,.config-message,.qq-auth-message { color:var(--muted); font-size:10px; line-height:1.55; }
     .config-actions { display:flex; align-items:center; gap:12px; }
     .config-actions .primary-button { min-height:38px; }
     .config-message.ok,.qq-auth-message.ok { color:var(--mint-ink); }
     .config-message.error,.qq-auth-message.error { color:#c06478; }
     .account-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:12px; }
     .account-add { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:7px; margin-top:13px; }
     .account-add .outline-button,.group-account .outline-button { min-height:39px; padding:0 11px; }
     .account-row { min-width:0; }
     .account-row button { flex:0 0 auto; border:0; background:transparent; color:#c06478; font-size:11px; }
     .account-row button:hover { color:#a94761; }
     .pan-directory { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:7px; margin:0 0 12px; }
     .pan-directory input { min-width:0; min-height:36px; padding:7px 9px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); outline:none; }
     .pan-directory input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
     .pan-directory .outline-button { min-height:36px; padding:0 10px; }
     .pan-security-note { margin:0 0 12px; padding:8px 9px; border-radius:6px; background:#fafaff; color:var(--muted); font-size:10px; line-height:1.5; }
     .group-account { display:grid; grid-template-columns:minmax(0,1fr) 74px auto; gap:7px; margin-top:9px; }
     .group-account input { min-width:0; }
     .group-account select { min-height:39px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); }
     .qq-auth-form { display:grid; gap:11px; max-width:500px; }
     .qq-auth-row { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
     .qq-auth-row input { min-height:39px; padding:8px 10px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); }
     .qq-auth-actions { display:flex; align-items:center; gap:9px; }
     .settings-hint { margin-top:15px; padding:12px 13px; border-radius:7px; background:#f7f7fd; color:var(--muted); font-size:11px; line-height:1.6; }
     .help-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-top:16px; }
     .help-card h3 { margin:0; font-size:14px; }
     .help-card > p { margin:4px 0 15px; color:var(--muted); font-size:11px; }
     .command-list { display:flex; flex-wrap:wrap; gap:7px; }
     .command-list span { display:inline-flex; min-height:28px; align-items:center; padding:0 9px; border:1px solid #e8e8f1; border-radius:6px; background:#fbfbfe; color:#55586d; font-size:11px; }
     @media (max-width:1050px) { .summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .runtime-page-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
      @keyframes page-enter { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
      @keyframes card-enter { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
      @keyframes switch-feedback { 0% { transform:scale(1); } 45% { transform:scale(1.08); } 100% { transform:scale(1); } }
      .page-view:not([hidden]) { animation:page-enter .32s cubic-bezier(.22,.8,.35,1) both; }
      .page-view:not([hidden]) .console-card,.page-view:not([hidden]) .summary-card,.page-view:not([hidden]) .shortcut-card,.page-view:not([hidden]) .pan-card,.page-view:not([hidden]) .runtime-item { animation:card-enter .34s cubic-bezier(.22,.8,.35,1) both; }
      .page-view:not([hidden]) .console-card:nth-child(2),.page-view:not([hidden]) .summary-card:nth-child(2),.page-view:not([hidden]) .shortcut-card:nth-child(2),.page-view:not([hidden]) .pan-card:nth-child(2),.page-view:not([hidden]) .runtime-item:nth-child(2) { animation-delay:.045s; }
      .page-view:not([hidden]) .console-card:nth-child(3),.page-view:not([hidden]) .summary-card:nth-child(3),.page-view:not([hidden]) .shortcut-card:nth-child(3),.page-view:not([hidden]) .pan-card:nth-child(3),.page-view:not([hidden]) .runtime-item:nth-child(3) { animation-delay:.09s; }
      .page-view:not([hidden]) .console-card:nth-child(4),.page-view:not([hidden]) .summary-card:nth-child(4),.page-view:not([hidden]) .shortcut-card:nth-child(4),.page-view:not([hidden]) .pan-card:nth-child(4),.page-view:not([hidden]) .runtime-item:nth-child(4) { animation-delay:.135s; }
      .summary-card,.shortcut-card,.pan-card,.runtime-item { transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease; }
      .summary-card:hover,.shortcut-card:hover,.pan-card:hover,.runtime-item:hover { transform:translateY(-2px); }
      .shortcut-card { cursor:default; }
      .switch:active { animation:switch-feedback .22s ease both; }
     /* Novel controls use an unframed workspace with compact, real controls. */
     .novel-console { margin-top:18px; padding:4px 0 0; }
     .novel-console-head { display:flex; align-items:flex-start; justify-content:space-between; gap:22px; margin-bottom:20px; }
     .novel-console-head h2 { margin:4px 0 0; font-size:23px; letter-spacing:0; }
     .novel-console-head .card-subtitle { margin:7px 0 0; max-width:520px; }
     .novel-overline,.novel-panel-kicker,.novel-platform-overline { color:#9295aa; font-size:10px; font-weight:800; letter-spacing:1.3px; }
     .novel-state-pill { display:inline-flex; align-items:center; gap:8px; min-height:34px; padding:0 12px; border:1px solid #dbe8df; border-radius:999px; background:#f4fbf7; color:#318260; white-space:nowrap; }
     .novel-state-pill.is-off { border-color:#e3e4eb; background:#fafafd; color:#838697; }
     .novel-state-dot { width:7px; height:7px; border-radius:50%; background:#4eb781; box-shadow:0 0 0 4px #e3f6eb; }
     .novel-state-pill.is-off .novel-state-dot { background:#a7a9b6; box-shadow:0 0 0 4px #eff0f4; }
     .novel-state-pill strong { font-size:11px; font-weight:750; }
     .novel-control-grid { display:grid; grid-template-columns:minmax(0,1.42fr) minmax(280px,.92fr); gap:12px; }
     .novel-master-panel,.novel-test-panel { min-height:178px; padding:20px; border:1px solid var(--line); border-radius:10px; background:#fff; box-shadow:0 5px 18px rgba(55,59,103,.045); }
     .novel-master-panel { border-color:#dedcff; background:#fbfaff; }
     .novel-test-panel { border-color:#f0ded4; background:#fffaf7; }
     .novel-panel-kicker { display:flex; align-items:center; gap:8px; color:#716cbf; letter-spacing:.7px; }
     .novel-test-panel .novel-panel-kicker { color:#bf7961; }
     .novel-panel-icon { width:25px; height:25px; display:grid; place-items:center; border-radius:7px; background:#ecebff; color:#605bd2; font-size:12px; letter-spacing:0; }
     .novel-test-panel .novel-panel-icon { background:#ffebe2; color:#c5755b; }
     .novel-master-copy h3,.novel-test-panel h3 { margin:19px 0 4px; font-size:17px; }
     .novel-master-copy p,.novel-test-panel p { max-width:410px; margin:0; color:#777a8e; font-size:12px; line-height:1.65; }
     .novel-master-actions,.novel-test-actions { display:flex; align-items:flex-end; justify-content:space-between; gap:15px; margin-top:18px; }
     .novel-master-state { display:grid; gap:2px; }
     .novel-master-state strong { color:var(--ink); font-size:12px; }
     .novel-master-state span,.novel-test-note { color:#9698aa; font-size:11px; }
     .novel-console .novel-master-panel .switch { width:50px; height:28px; }
     .novel-console .novel-master-panel .switch span { width:22px; height:22px; }
     .novel-console .novel-master-panel .switch.on span { transform:translateX(22px); }
     .novel-test-actions { align-items:center; margin-top:20px; }
     .novel-test-actions .switch { transform:scale(.95); transform-origin:right center; }
     .novel-platform-head { display:flex; align-items:flex-end; justify-content:space-between; gap:18px; margin:29px 0 12px; }
     .novel-platform-head h3 { margin:4px 0 0; font-size:15px; }
     .novel-platform-count { color:#76798d; font-size:11px; }
     .novel-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
     .novel-item { display:flex; align-items:center; justify-content:space-between; gap:14px; min-height:78px; padding:14px 16px; border:1px solid #e8e9f1; border-radius:9px; background:#fff; box-shadow:none; transition:border-color .2s ease,background .2s ease,transform .2s ease,box-shadow .2s ease; }
     .novel-item:hover { border-color:#cfcdf3; background:#fdfdff; transform:translateY(-2px); box-shadow:0 7px 18px rgba(55,59,103,.06); }
     .novel-item.is-enabled { border-color:#d8e9df; }
     .novel-item.is-disabled { background:#fcfcfd; }
     .novel-item-main { display:flex; align-items:center; gap:11px; min-width:0; }
     .novel-badge { width:34px; height:34px; flex:0 0 auto; display:grid; place-items:center; border-radius:10px; background:#efeeff; color:#625dd4; font-size:12px; font-weight:800; }
     .novel-item:nth-child(3n+2) .novel-badge { background:#e8f8ef; color:#35936a; }
     .novel-item:nth-child(3n) .novel-badge { background:#fff0e9; color:#ca7b5f; }
     .novel-item-copy { min-width:0; }
     .novel-item-title { display:flex; align-items:center; gap:8px; min-width:0; }
     .novel-item-title strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
     .novel-item-copy small { display:block; margin-top:4px; color:#999bab; font-size:10px; }
     .novel-item-status { flex:0 0 auto; color:#9a9cad; font-size:10px; }
     .novel-item.is-enabled .novel-item-status { color:#35936a; }
     .novel-item .switch { transform:scale(.9); transform-origin:right center; }
     .novel-item .switch:focus-visible,.novel-master-panel .switch:focus-visible,.novel-test-panel .switch:focus-visible { outline:3px solid #c9c6ff; outline-offset:3px; }
     @media (max-width:900px) { .novel-control-grid { grid-template-columns:1fr; } }
     @media (max-width:760px) { .novel-console { margin-top:15px; padding-top:0; } .novel-console-head { display:block; } .novel-state-pill { margin-top:14px; } .novel-master-panel,.novel-test-panel { min-height:0; padding:17px; } .novel-master-copy h3,.novel-test-panel h3 { margin-top:15px; } .novel-platform-head { align-items:flex-start; margin-top:24px; } .novel-platform-head { display:block; } .novel-platform-count { display:block; margin-top:6px; } .novel-grid { grid-template-columns:1fr; } .novel-item { min-height:72px; padding:13px 14px; } }
      @media (max-width:760px) { #admin-name { max-width:88px; } .admin-popover { right:-2px; width:205px; } }
      @media (prefers-reduced-motion: reduce) {
        *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:.01ms !important; }
      }
     @media (max-width:760px) { .heading-actions { gap:7px; } .updated-label { display:none; } .summary-grid,.page-grid,.runtime-detail,.help-grid { grid-template-columns:1fr; } .shortcut-grid { grid-template-columns:1fr; } .runtime-page-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .standalone-card { margin-top:15px; } .safe-list > div,.settings-row { min-height:56px; } .config-fields,.qq-auth-row { grid-template-columns:1fr; } .group-account { grid-template-columns:minmax(0,1fr) 70px; } .group-account .outline-button { grid-column:1 / -1; } }
   </style>
</head>
"""

_网页主体 = """
<body>
  <div class="shell">
    <header class="topbar">
        <div class="brand"><div class="brand-mark">馒</div><div><strong>QQ机器人后台</strong><span class="version-badge" id="console-version">v5.45.2</span></div></div>
      <div class="top-actions"><span class="status-dot">服务在线</span><div class="admin-menu"><button class="admin-chip" id="admin-chip" type="button" aria-expanded="false" aria-controls="admin-popover"><span class="admin-avatar" id="admin-avatar">管</span><span id="admin-name">管理员</span><span class="admin-chevron">⌄</span></button><div class="admin-popover" id="admin-popover" hidden><strong id="admin-popover-name">管理员</strong><small id="admin-popover-role">控制台管理员 · 当前会话</small><small id="admin-popover-scope">插件管理员白名单：读取中</small><button class="popover-logout" id="popover-logout" type="button" hidden>退出登录</button></div></div></div>
    </header>
    <aside class="sidebar">
      <div class="profile"><div class="bot-avatar"><span class="avatar-face">•ᴗ•</span></div><strong>馒头助手</strong><span class="online">在线</span></div>
      <div><div class="nav-label">工作台</div><nav class="nav" aria-label="控制台导航">
        <a href="?view=dashboard" data-view="dashboard"><span class="nav-icon">⌂</span>控制台</a>
        <a href="?view=bot" data-view="bot"><span class="nav-icon">⚙</span>机器人配置</a>
        <a href="?view=novels" data-view="novels"><span class="nav-icon">☷</span>小说功能</a>
        <a href="?view=pans" data-view="pans"><span class="nav-icon">▣</span>网盘配置</a>
        <a href="?view=messages" data-view="messages"><span class="nav-icon">✉</span>消息记录</a>
        <a href="?view=runtime" data-view="runtime"><span class="nav-icon">◒</span>运行状态</a>
        <a href="?view=help" data-view="help"><span class="nav-icon">?</span>帮助指令</a>
        <a href="?view=settings" data-view="settings"><span class="nav-icon">⚙</span>系统设置</a>
      </nav></div>
      <div class="sidebar-foot"><span class="spark">✦</span><strong>只显示真实功能</strong><span>未接入后端的数据入口不会伪装成可用按钮。</span></div>
    </aside>
    <main class="main">
      <div class="content">
        <div class="page-heading"><div><p id="page-eyebrow" class="page-kicker">馒头Bot / 管理台</p><h1 id="page-title">控制台</h1><p id="page-subtitle">查看机器人和小说服务的实时状态</p></div><div class="heading-actions"><span id="updated" class="updated-label">--</span></div></div>
        <div id="notice" class="notice"></div>
        <section id="page-dashboard" class="page-view" data-page="dashboard">
          <div class="section-head page-view-head"><div><h2>服务总览</h2><p>快速查看当前功能状态；页面切换请使用左侧导航。</p></div></div>
          <div class="summary-grid">
            <article class="summary-card"><span>小说总开关</span><strong id="metric-global">--</strong><small id="metric-global-meta">加载中</small><span class="text-button">管理小说功能</span></article>
            <article class="summary-card"><span>当前分享网盘</span><strong id="metric-pan">--</strong><small id="metric-pan-meta">加载中</small><span class="text-button">管理网盘</span></article>
            <article class="summary-card"><span>数据库状态</span><strong id="metric-db">--</strong><small id="metric-db-meta">加载中</small><span class="text-button">查看连接配置</span></article>
            <article class="summary-card"><span>插件版本</span><strong id="metric-version">--</strong><small id="metric-version-meta">馒头Bot</small><span class="text-button">查看运行状态</span></article>
          </div>
          <div class="page-grid dashboard-grid"><article class="console-card"><h2>快捷入口</h2><p class="card-subtitle">各项功能均有独立页面，请从左侧导航打开。</p><div class="shortcut-grid"><article class="shortcut-card"><span class="shortcut-icon">⚙</span><strong>机器人配置</strong><small>查看安全摘要与监听配置</small></article><article class="shortcut-card"><span class="shortcut-icon">☷</span><strong>小说功能</strong><small>开关平台和管理员测试模式</small></article><article class="shortcut-card"><span class="shortcut-icon">▣</span><strong>网盘配置</strong><small>选择主分享网盘和查看账号摘要</small></article><article class="shortcut-card"><span class="shortcut-icon">◒</span><strong>运行状态</strong><small>查看服务器实时指标</small></article></div></article><article class="console-card"><h2>当前状态</h2><p class="card-subtitle">最近一次读取：<span id="dashboard-updated">--</span></p><div class="status-list compact-status"><div class="status-item"><span>CPU 占用</span><strong id="dashboard-cpu">--</strong></div><div class="status-item"><span>物理内存</span><strong id="dashboard-memory">--</strong></div><div class="status-item"><span>系统运行时间</span><strong id="dashboard-runtime">--</strong></div></div></article></div>
        </section>

        <section id="page-bot" class="page-view" data-page="bot" hidden>
          <div class="workspace-grid"><div class="workspace-left"><article id="overview" class="console-card"><h2>基本信息</h2><p class="card-subtitle">当前插件的安全摘要和运行身份</p><div class="profile-fields"><div class="profile-field"><span>机器人名称</span><div class="readonly-value"><strong>馒头助手</strong><small>管理台</small></div></div><div class="profile-field"><span>机器人 QQ 号</span><div class="readonly-value"><strong>由适配器提供</strong><small>页面不读取账号信息</small></div></div><div class="profile-field"><span>机器人头像</span><div class="avatar-inline"><div class="bot-avatar"><span class="avatar-face">•ᴗ•</span></div><small>馒头Bot 二次元助手</small></div></div><div class="profile-field"><span>机器人简介</span><div class="readonly-value"><strong>小说下载、网盘分享与群聊管理</strong></div></div><div class="profile-field"><span>运行状态</span><div class="state-line"><span class="online">在线运行</span></div></div></div></article><article id="config" class="console-card"><h2>机器人配置</h2><p class="card-subtitle">管理员白名单和帮助网页账号；敏感字段只写入，不在网页回显。</p><div id="basic-config-editor" class="config-editor"><div class="empty">正在读取配置...</div></div></article><article class="console-card"><h2>QQ阅读登录态</h2><p class="card-subtitle">只保存 ywguid 和 ywkey，不显示原值。</p><div id="qq-auth-editor"><div class="empty">正在读取登录态...</div></div></article></div><div class="workspace-right"><article class="console-card"><h2>安全说明</h2><p class="card-subtitle">页面只展示后端允许的摘要。</p><div class="safe-list"><div><span>登录凭据</span><strong>不返回原文</strong></div><div><span>数据库地址</span><strong>只写不读</strong></div><div><span>网盘 Cookie</span><strong>只写不回显</strong></div><div><span>会话 Cookie</span><strong>仅 HttpOnly 保存</strong></div></div></article></div></div>
        </section>

        <section id="page-novels" class="page-view" data-page="novels" hidden><article id="novels" class="novel-console standalone-card">
          <header class="novel-console-head"><div><span class="novel-overline">NOVEL CONTROL</span><h2>小说功能</h2><p class="card-subtitle">集中管理小说入口和平台状态，下载逻辑保持不变。</p></div><div id="novel-state-pill" class="novel-state-pill"><span class="novel-state-dot"></span><strong>读取中</strong></div></header>
          <div class="novel-control-grid">
            <section class="novel-master-panel"><div class="novel-panel-kicker"><span class="novel-panel-icon">全</span><span>GLOBAL ACCESS</span></div><div class="novel-master-copy"><h3>全部小说功能</h3><p>控制下载、找书和翻页的总入口。关闭后所有平台都会暂停响应。</p></div><div class="novel-master-actions"><div class="novel-master-state"><strong id="novel-master-label">读取中</strong><span id="novel-platform-summary">正在读取平台状态</span></div><button id="global-switch" class="switch" type="button" aria-label="切换全局小说功能"><span></span></button></div></section>
            <section class="novel-test-panel"><div class="novel-panel-kicker"><span class="novel-panel-icon">测</span><span>ADMIN MODE</span></div><h3>管理员测试模式</h3><p>只影响管理员测试，不会绕过普通用户的平台开关。</p><div class="novel-test-actions"><span id="novel-test-label" class="novel-test-note">状态读取中</span><button id="test-switch" class="switch" type="button" aria-label="切换管理员测试模式"><span></span></button></div></section>
          </div>
          <div class="novel-platform-head"><div><span class="novel-platform-overline">PLATFORMS</span><h3>平台开关</h3></div><span id="novel-enabled-count" class="novel-platform-count">-- / -- 已开启</span></div>
          <div id="novel-grid" class="novel-grid"><div class="empty">正在读取小说平台...</div></div>
        </article></section>

        <section id="page-pans" class="page-view" data-page="pans" hidden><article id="pans" class="pan-console console-card standalone-card"><h2>网盘配置</h2><p class="card-subtitle">选择一个网盘页面进行管理，左侧导航负责页面切换；Cookie 只写入，不在网页回显。</p><div class="pan-note"><span>当前主分享网盘</span><strong id="pan-active-label">--</strong></div><div class="pan-tabs" role="tablist" aria-label="网盘配置页面"><button id="pan-tab-UC" class="pan-tab" type="button" role="tab" data-pan-tab="UC" aria-controls="pan-card-UC" aria-selected="false">UC网盘</button><button id="pan-tab-夸克" class="pan-tab" type="button" role="tab" data-pan-tab="夸克" aria-controls="pan-card-夸克" aria-selected="false">夸克网盘</button><button id="pan-tab-百度" class="pan-tab" type="button" role="tab" data-pan-tab="百度" aria-controls="pan-card-百度" aria-selected="false">百度网盘</button></div><div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态...</div></div></article></section>

        <section id="page-runtime" class="page-view" data-page="runtime" hidden><article class="console-card standalone-card"><h2>运行状态</h2><p class="card-subtitle">这些数据来自服务器当前运行状态。</p><div class="runtime-grid runtime-page-grid"><div class="runtime-item"><span>CPU占用</span><strong id="runtime-cpu">--</strong></div><div class="runtime-item"><span>物理内存</span><strong id="runtime-memory">--</strong></div><div class="runtime-item"><span>磁盘空间</span><strong id="runtime-disk">--</strong></div><div class="runtime-item"><span>系统运行时间</span><strong id="runtime-runtime">--</strong></div><div class="runtime-item"><span>操作系统</span><strong id="runtime-os">--</strong></div></div><div class="runtime-detail"><div class="status-item"><span>数据库</span><strong id="runtime-db">--</strong></div><div class="status-item"><span>当前网盘</span><strong id="runtime-pan">--</strong></div><div class="status-item"><span>插件版本</span><strong id="runtime-version">--</strong></div></div></article></section>

        <section id="page-help" class="page-view" data-page="help" hidden><div class="section-head page-view-head"><div><h2>帮助指令</h2><p>这里列出机器人当前支持的聊天指令；网页不代替群聊执行指令。</p></div></div><div class="help-grid"><article class="console-card help-card"><h3>管理与状态</h3><p>需要管理员权限的指令。</p><div class="command-list"><span>帮助</span><span>状态</span><span>小说</span><span>开小说 / 关小说</span><span>开测试 / 关测试</span><span>网盘状态</span><span>换UC / 换夸克 / 换百度</span><span>夸克登录</span></div></article><article class="console-card help-card"><h3>小说入口</h3><p>在群聊或私聊发送链接即可识别。</p><div class="command-list"><span>找关键词</span><span>找书 关键词</span><span>找作者 关键词</span><span>上一页 / 下一页</span><span>小说平台分享链接</span><span>小说分享卡片</span></div></article><article class="console-card help-card"><h3>群聊管理</h3><p>由插件管理员和群身份规则共同决定。</p><div class="command-list"><span>禁言 @成员</span><span>禁 @成员 1</span><span>解 @成员</span><span>数字撤回</span><span>卡片撤回</span><span>合并转发撤回</span></div></article></div></section>
        <section id="page-settings" class="page-view" data-page="settings" hidden><article id="settings" class="console-card standalone-card"><h2>系统设置</h2><p class="card-subtitle">数据库连接和网页服务设置可直接保存；监听端口等变更需要重载插件。</p><div id="settings-editor" class="config-editor"><div class="empty">正在读取设置...</div></div></article></section>

        <section id="page-messages" class="page-view" data-page="messages" hidden>
          <style>
            .msg-shell { display:grid; grid-template-columns:330px minmax(0,1fr); min-height:calc(100vh - 130px); align-items:stretch; background:#fff; border:1px solid #e8e9ec; border-radius:10px; overflow:hidden; }
            .msg-panel { display:flex; flex-direction:column; min-width:0; min-height:0; background:#fff; }
            .chat-list-panel { border-right:1px solid #e8e9ec; background:#fafafa; }
            .msg-list-head { display:flex; flex-direction:column; gap:8px; padding:10px 12px 8px; border-bottom:1px solid #e8e9ec; background:#fff; }
            .msg-filter { display:flex; gap:2px; padding:2px; background:#f2f3f5; border-radius:8px; }
            .msg-filter button { flex:1 1 0; min-width:0; min-height:26px; padding:0 4px; border:0; border-radius:6px; background:transparent; color:#666; font-size:11px; font-weight:600; cursor:pointer; }
            .msg-filter button.active { background:#fff; color:#12b7f5; box-shadow:0 1px 3px rgba(0,0,0,.08); }
            .msg-search { display:flex; gap:6px; }
            .msg-search input { flex:1 1 0; min-width:0; height:30px; padding:0 10px; border:1px solid transparent; border-radius:15px; background:#f2f3f5; color:#333; font-size:12px; outline:none; transition:all .15s ease; }
            .msg-search input:focus { border-color:#12b7f5; background:#fff; }
            .msg-search button { height:30px; padding:0 12px; border:0; border-radius:15px; background:#12b7f5; color:#fff; font-size:11px; font-weight:700; cursor:pointer; }
            .msg-chats { flex:1 1 0; min-height:0; overflow-y:auto; padding:4px 6px; }
            .msg-chat { display:flex; gap:10px; width:100%; min-height:56px; padding:8px 10px; border:0; border-radius:8px; background:transparent; text-align:left; cursor:pointer; transition:background .12s ease; }
            .msg-chat:hover { background:#ececee; }
            .msg-chat.active { background:#dbeafd; }
            .msg-chat-avatar { position:relative; width:40px; height:40px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:#cfe3fb; color:#3a7bd5; font-size:14px; font-weight:800; overflow:hidden; }
            .msg-chat-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-chat-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:14px; font-weight:800; color:#3a7bd5; }
            .msg-chat-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-chat-main { flex:1 1 0; min-width:0; align-self:center; }
            .msg-chat-top { display:flex; align-items:center; gap:6px; }
            .msg-chat-top strong { font-size:13px; font-weight:600; color:#222; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-top small { margin-left:auto; flex:0 0 auto; color:#999; font-size:10px; }
            .msg-chat-sub { margin-top:3px; color:#999; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-type { display:none; }
            .msg-chat-meta { display:none; }
            .msg-empty { padding:26px 14px; color:#aaa; font-size:12px; text-align:center; }
            .msg-work { display:flex; flex-direction:column; min-width:0; min-height:0; background:#f5f6f7; }
            .msg-head { display:flex; align-items:center; gap:10px; padding:10px 16px; background:#fff; border-bottom:1px solid #e8e9ec; }
            .msg-head-name { font-size:15px; font-weight:650; color:#222; }
            .msg-head-sub { margin-top:2px; color:#999; font-size:11px; }
            .msg-head-actions { margin-left:auto; display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
            .msg-btn { min-height:28px; padding:0 10px; border:1px solid #dcdfe6; border-radius:6px; background:#fff; color:#666; font-size:11px; font-weight:600; cursor:pointer; transition:all .16s ease; }
            .msg-btn:hover { border-color:#12b7f5; color:#12b7f5; }
            .msg-btn.primary { border-color:#12b7f5; background:#12b7f5; color:#fff; }
            .msg-btn.primary:hover { background:#0ea5e0; }
            .msg-body { flex:1 1 0; min-height:0; overflow-y:auto; padding:18px 16px 10px; background:#f5f6f7; }
            .msg-day { margin:10px 0; color:#aaa; font-size:10px; text-align:center; }
            .msg-row { display:flex; gap:9px; margin-bottom:14px; }
            .msg-row.self { flex-direction:row-reverse; }
            .msg-avatar { position:relative; width:36px; height:36px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:#cfe3fb; color:#3a7bd5; font-size:12px; font-weight:800; overflow:hidden; }
            .msg-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:12px; font-weight:800; color:#3a7bd5; }
            .msg-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-bubble-wrap { max-width:min(70%,560px); min-width:0; }
            .msg-row.self .msg-bubble-wrap { display:flex; flex-direction:column; align-items:flex-end; }
            .msg-bubble-name { margin-bottom:3px; color:#999; font-size:10px; padding-left:2px; }
            .msg-row.self .msg-bubble-name { padding-left:0; padding-right:2px; }
            .msg-bubble { padding:8px 12px; border-radius:3px 10px 10px 10px; background:#fff; color:#333; font-size:13px; line-height:1.6; word-break:break-word; white-space:pre-wrap; box-shadow:0 1px 2px rgba(0,0,0,.05); }
            .msg-row.self .msg-bubble { border-radius:10px 3px 10px 10px; background:#12b7f5; color:#fff; }
            .msg-row.self .msg-bubble .msg-bubble-quote { color:#dff1fd; }
            .msg-bubble.recalled { color:#bbb; font-style:italic; background:#eee; }
            .msg-bubble-quote { margin:-2px 0 6px; padding:5px 8px; border-left:3px solid #8ec5f2; border-radius:4px; background:#f2f8ff; color:#888; font-size:11px; }
            .msg-row.self .msg-bubble-quote { background:rgba(255,255,255,.22); border-left-color:#fff; }
            .msg-media { margin-top:7px; }
            .msg-media img { max-width:210px; max-height:210px; border-radius:8px; display:block; }
            .msg-meta { margin-top:3px; color:#b0b0b0; font-size:9px; padding-left:2px; }
            .msg-row.self .msg-meta { text-align:right; padding-left:0; padding-right:2px; }
            .msg-tags { display:inline-flex; gap:4px; margin-left:6px; vertical-align:middle; }
            .msg-tag { display:inline-block; padding:0 5px; border-radius:4px; font-size:9px; line-height:15px; font-weight:700; }
            .msg-tag.bot { background:#ffeef5; color:#c66791; }
            .msg-tag.role { background:#eef3ff; color:#5b7bd5; }
            .msg-tag.self { background:#e9fbf3; color:#319e6b; }
            .msg-tag.recalled { background:#f2f2f5; color:#9a9cb0; }
            .msg-actions { display:flex; gap:5px; margin-top:5px; }
            .msg-row.self .msg-actions { justify-content:flex-end; }
            .msg-action { padding:0 7px; min-height:22px; border:0; border-radius:5px; background:#e4e7ec; color:#888; font-size:10px; cursor:pointer; }
            .msg-action:hover { background:#d2e9fb; color:#12b7f5; }
            .msg-load-older { display:block; margin:0 auto 12px; padding:5px 12px; border:1px solid #dcdfe6; border-radius:6px; background:#fff; color:#999; font-size:11px; cursor:pointer; }
            .msg-composer { display:flex; flex-direction:column; gap:8px; padding:10px 14px 12px; background:#fff; border-top:1px solid #e8e9ec; }
            .msg-composer-tabs { display:flex; gap:5px; flex-wrap:wrap; }
            .msg-composer-tabs button { min-height:26px; padding:0 10px; border:1px solid #e0e1e5; border-radius:6px; background:#fff; color:#999; font-size:11px; font-weight:600; cursor:pointer; }
            .msg-composer-tabs button.active { border-color:#12b7f5; color:#12b7f5; background:#e8f6fe; }
            .msg-composer-mode { display:flex; gap:5px; flex-wrap:wrap; align-items:center; }
            .msg-composer-mode select { height:28px; padding:0 8px; border:1px solid #e0e1e5; border-radius:6px; background:#fff; color:#333; font-size:11px; }
            .msg-composer-mode input { height:28px; min-width:120px; padding:0 8px; border:1px solid #e0e1e5; border-radius:6px; background:#fbfbff; color:#333; font-size:11px; outline:none; }
            .msg-textarea { min-height:64px; max-height:150px; padding:9px 11px; border:0; border-radius:6px; background:#f2f3f5; color:#333; font-size:12px; line-height:1.55; resize:vertical; outline:none; transition:all .15s ease; }
            .msg-textarea:focus { background:#fff; box-shadow:inset 0 0 0 1px #12b7f5; }
            .msg-extra { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; }
            .msg-extra input { height:28px; min-width:0; padding:0 8px; border:1px solid #e0e1e5; border-radius:6px; background:#fbfbff; color:#333; font-size:11px; outline:none; }
            .msg-send-row { display:flex; align-items:center; gap:10px; justify-content:flex-end; }
            .msg-send-row .msg-btn.primary { min-height:32px; padding:0 24px; }
            .msg-quote-preview { display:flex; align-items:center; gap:8px; padding:6px 9px; border:1px solid #e2ddf5; border-radius:8px; background:#f8f7ff; color:#999; font-size:11px; }
        .msg-img-preview { display:flex; align-items:center; gap:8px; margin:6px 0; padding:6px 8px; background:#f7f8fa; border:1px solid #e8e9ec; border-radius:8px; }
        .msg-img-preview img { width:48px; height:48px; object-fit:cover; border-radius:6px; border:1px solid #dcdde0; }
        .msg-img-preview span { flex:1; font-size:12px; color:#4a4d54; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .msg-img-preview .msg-action { background:none; border:none; color:#e64340; cursor:pointer; font-size:12px; padding:2px 6px; }
            .msg-quote-preview b { color:#333; }
            .msg-raw-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-raw-modal[hidden] { display:none; }
            .msg-raw-box { width:min(720px,100%); max-height:78vh; display:flex; flex-direction:column; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-raw-head { display:flex; align-items:center; justify-content:space-between; padding:12px 15px; border-bottom:1px solid #e8e9ec; }
            .msg-raw-head strong { font-size:13px; color:#222; }
            .msg-raw-head button { border:0; background:transparent; color:#999; font-size:16px; cursor:pointer; }
            .msg-raw-content { flex:1 1 0; min-height:0; overflow:auto; padding:13px 15px; white-space:pre-wrap; word-break:break-all; color:#333; font:12px/1.6 Consolas,Monaco,monospace; }
            .msg-mute-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-mute-modal[hidden] { display:none; }
            .msg-mute-box { width:min(400px,100%); background:#fff; border-radius:12px; padding:16px; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-mute-box h3 { margin:0 0 12px; font-size:14px; color:#222; }
            .msg-mute-presets { display:flex; gap:7px; flex-wrap:wrap; margin-bottom:12px; }
            .msg-mute-presets button { min-height:30px; padding:0 12px; border:1px solid #e0e1e5; border-radius:8px; background:#fff; color:#666; font-size:11px; cursor:pointer; }
            .msg-mute-presets button.active { border-color:#12b7f5; color:#12b7f5; background:#e8f6fe; }
            .msg-mute-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:12px; }
            .msg-remark-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-remark-modal[hidden] { display:none; }
            .msg-remark-box { width:min(380px,100%); background:#fff; border-radius:12px; padding:16px; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-remark-box h3 { margin:0 0 12px; font-size:14px; color:#222; }
            /* ===== QQ PC 风格覆盖 ===== */
            .msg-shell { grid-template-columns:340px minmax(0,1fr); border:1px solid #e1e5ea; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
            .chat-list-panel { background:#f7f8fa; }
            .msg-list-head { padding:10px 12px; background:#f7f8fa; border-bottom:1px solid #e5e8ec; }
            .msg-filter button.active { color:#12b7f5; }
            .msg-chats { padding:4px 6px; }
            .msg-chat { min-height:52px; padding:6px 8px; border-radius:6px; }
            .msg-chat:hover { background:#eceef1; }
            .msg-chat.active { background:#d5ebfb; }
            .msg-chat-avatar { width:38px; height:38px; }
            .msg-chat-top strong { font-size:12.5px; }
            .msg-chat-sub { font-size:11px; margin-top:1px; }
            .msg-work { background:#f5f6f7; }
            .msg-head { padding:8px 14px; background:#fff; }
            .msg-body { padding:14px 20px 8px; background:#f5f6f7; }
            .msg-day { margin:8px 0; color:#b6bcc4; font-size:10px; }
            .msg-row { gap:10px; margin-bottom:12px; align-items:flex-start; }
            .msg-avatar { width:38px; height:38px; }
            .msg-bubble-wrap { max-width:min(62%,560px); }
            .msg-bubble { padding:9px 12px; border-radius:4px 12px 12px 12px; background:#fff; font-size:13px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
            .msg-row.self .msg-bubble { border-radius:12px 4px 12px 12px; background:#95ec69; color:#000; }
            .msg-row.self .msg-bubble .msg-bubble-quote { color:rgba(0,0,0,.55); }
            .msg-meta { color:#b6bcc4; font-size:9px; }
            .msg-bubble-name { font-size:10px; }
            .msg-composer { padding:8px 14px 10px; background:#fff; border-top:1px solid #e5e8ec; }
            .msg-textarea { background:#f7f8fa; border-radius:4px; }
            .msg-textarea:focus { background:#fff; box-shadow:inset 0 0 0 1px #12b7f5; }
            .msg-send-row .msg-btn.primary { background:#12b7f5; border-color:#12b7f5; }

            /* 右键菜单 */
            .msg-ctx { position:fixed; z-index:120; min-width:150px; padding:4px; background:#fff; border:1px solid #e1e5ea; border-radius:8px; box-shadow:0 6px 20px rgba(0,0,0,.14); user-select:none; }
            .msg-ctx[hidden] { display:none; }
            .msg-ctx-item { display:flex; align-items:center; gap:8px; width:100%; padding:7px 10px; border:0; border-radius:5px; background:transparent; color:#333; font-size:12px; text-align:left; cursor:pointer; }
            .msg-ctx-item:hover { background:#f0f7ff; color:#12b7f5; }
            .msg-ctx-item.danger:hover { background:#fff1f0; color:#e64340; }
            .msg-ctx-sep { height:1px; margin:4px 8px; background:#eee; }

            /* 多选模式 */
            .msg-multi-bar { display:flex; align-items:center; gap:10px; padding:6px 14px; background:#e8f6fe; border-bottom:1px solid #cfe8fb; font-size:12px; color:#12b7f5; }
            .msg-multi-bar[hidden] { display:none; }
            .msg-row.multi-mode { cursor:pointer; }
            .msg-row.multi-mode .msg-avatar, .msg-row.multi-mode .msg-bubble { opacity:.85; }
            .msg-row.multi-mode.selected .msg-bubble { outline:2px solid #12b7f5; outline-offset:2px; }
            .msg-pos { position:relative; display:inline-flex; flex:0 0 auto; }
            .msg-multi-check { display:none; }
            .msg-row.multi-mode .msg-multi-check { display:grid; position:absolute; left:-16px; top:50%; transform:translateY(-50%); width:18px; height:18px; border-radius:50%; border:2px solid #c3ccd4; background:#fff; display:grid; place-items:center; font-size:11px; color:#fff; }
            .msg-row.multi-mode.selected .msg-multi-check { border-color:#12b7f5; background:#12b7f5; }
            .msg-row.self.multi-mode .msg-multi-check { left:auto; right:-16px; }
            .msg-row.multi-mode.no-multi { opacity:.55; }
            .msg-row.multi-mode.no-multi .msg-multi-check { display:none; }
            .msg-row.multi-mode .msg-multi-check::after { content:'✓'; }
            .msg-pos { position:relative; }
            @media (max-width:900px) { .msg-shell { grid-template-columns:1fr; } .msg-panel.chat-list-panel { min-height:280px; max-height:38vh; } .msg-bubble-wrap { max-width:88%; } .msg-extra { grid-template-columns:1fr; } }
          </style>
          <div class="msg-shell">
            <div class="msg-panel chat-list-panel">
              <div class="msg-list-head">
                <div class="msg-filter" id="msg-filter" role="tablist" aria-label="消息过滤">
                  <button type="button" data-msg-filter="all" class="active">全量</button>
                  <button type="button" data-msg-filter="remark">备注</button>
                  <button type="button" data-msg-filter="group">群聊</button>
                  <button type="button" data-msg-filter="user">私聊</button>
                </div>
                <div class="msg-search">
                  <input id="msg-search-input" type="text" placeholder="搜索群名或 openid" aria-label="搜索会话">
                  <button id="msg-search-btn" type="button">搜索</button>
                </div>
              </div>
              <div class="msg-chats" id="msg-chats"><div class="msg-empty">正在加载会话...</div></div>
            </div>
            <div class="msg-panel msg-work">
              <div class="msg-head">
                <div style="min-width:0">
                  <div class="msg-head-name" id="msg-head-name">选择一个会话</div>
                  <div class="msg-head-sub" id="msg-head-sub">左侧列表选择群聊或私聊查看消息</div>
                  <span class="msg-admin-tag" id="msg-admin-tag" hidden>· 机器人是管理员</span>
                </div>
                <div class="msg-head-actions">
                  <button class="msg-btn" id="msg-refresh-info" type="button" hidden>刷新群信息</button>
                  <button class="msg-btn" id="msg-remark" type="button" hidden>群备注</button>
                  <button class="msg-btn" id="msg-reload" type="button">刷新</button>
                </div>
              </div>
              <div class="msg-multi-bar" id="msg-multi-bar" hidden><span id="msg-multi-count">已选 0 条</span><button class="msg-btn primary" id="msg-multi-recall" type="button">撤回选中</button><button class="msg-btn" id="msg-multi-cancel" type="button">取消</button></div>
              <div class="msg-body" id="msg-body"><div class="msg-empty">从左侧选择会话开始查看</div></div>
              <div class="msg-composer" id="msg-composer" hidden>
                <div class="msg-composer-tabs" id="msg-composer-tabs">
                  <button type="button" data-msg-type="text" class="active">文本</button>
                  <button type="button" data-msg-type="markdown">Markdown</button>
                  <button type="button" data-msg-type="media">媒体</button>
                  <button type="button" data-msg-type="ark">ARK模板</button>
                  <button type="button" data-msg-type="card">图文卡片</button>
                </div>
                <div class="msg-composer-mode">
                  <select id="msg-send-mode" aria-label="发送方式">
                    <option value="default">默认（全量群主动/其他被动）</option>
                    <option value="passive">被动（msg_id）</option>
                    <option value="active">主动</option>
                    <option value="custom_msg_id">自定义 msg_id</option>
                    <option value="custom_event_id">自定义事件 ID</option>
                  </select>
                  <input id="msg-custom-id" type="text" placeholder="自定义 msg_id / 事件 ID" hidden>
                </div>
                <div class="msg-extra" id="msg-extra" hidden></div>
                <textarea id="msg-textarea" class="msg-textarea" placeholder="输入消息内容...（回车发送，Ctrl+Enter 换行）" aria-label="消息内容"></textarea>
                <div class="msg-quote-preview" id="msg-quote-preview" hidden><b>引用：</b><span id="msg-quote-text"></span><button class="msg-action" id="msg-quote-clear" type="button">取消引用</button></div>
                <div class="msg-img-preview" id="msg-img-preview" hidden><img id="msg-img-thumb" alt="待发送图片"><span id="msg-img-name">图片</span><button class="msg-action" id="msg-img-clear" type="button">移除</button></div>
                <div class="msg-send-row">
                  <span id="msg-send-status" style="color:var(--muted);font-size:11px"></span>
                  <button class="msg-btn primary" id="msg-send" type="button">发送</button>
                </div>
              </div>
            </div>
          </div>
          <div class="msg-ctx" id="msg-ctx" hidden></div>
          <div class="msg-raw-modal" id="msg-raw-modal" hidden><div class="msg-raw-box"><div class="msg-raw-head"><strong>消息原始数据</strong><button id="msg-raw-close" type="button">×</button></div><div class="msg-raw-content" id="msg-raw-content"></div></div></div>
          <div class="msg-remark-modal" id="msg-remark-modal" hidden><div class="msg-remark-box"><h3>群备注</h3><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">备注名（显示在会话列表）</label><input id="msg-remark-name" type="text" placeholder="输入群备注名" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px;margin-bottom:10px"><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">群号（用于显示群头像，可留空）</label><input id="msg-remark-qq" type="text" placeholder="输入群号" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-remark-delete" type="button" style="color:#e64340;border-color:#f5c2c1;margin-right:auto">删除备注</button><button class="msg-btn" id="msg-remark-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-remark-save" type="button">保存</button></div></div></div>
          <div class="msg-mute-modal" id="msg-mute-modal" hidden><div class="msg-mute-box"><h3 id="msg-mute-title">禁言成员</h3><div class="msg-mute-presets" id="msg-mute-presets"><button type="button" data-mute-min="10">10分钟</button><button type="button" data-mute-min="30" class="active">30分钟</button><button type="button" data-mute-min="60">1小时</button><button type="button" data-mute-min="1440">1天</button></div><input id="msg-mute-custom" type="number" min="1" max="43200" placeholder="自定义分钟" style="width:100%;height:32px;padding:0 9px;border:1px solid var(--line);border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-mute-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-mute-confirm" type="button">确认禁言</button></div></div></div>
        </section>
      </div>
    </main>
  </div>
  <div id="toast" class="toast" role="status"></div>
"""

_网页脚本 = """
  <script>
    (() => {
      const initialParams = new URLSearchParams(location.search);
      if (initialParams.has('token')) { initialParams.delete('token'); const cleanQuery = initialParams.toString(); history.replaceState({}, '', `${location.pathname}${cleanQuery ? `?${cleanQuery}` : ''}${location.hash}`); }
      const $ = (id) => document.getElementById(id);
      const esc = (value) => String(value ?? '').replace(/[&<>\"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[char]));
      const views = {
        dashboard: ['控制台', '查看机器人和小说服务的实时状态'],
        bot: ['机器人配置', '查看安全摘要、监听地址和访问策略'],
        novels: ['小说功能', '管理全局开关、测试模式和平台开关'],
        pans: ['网盘配置', '管理主分享网盘和账号安全摘要'],
        runtime: ['运行状态', '查看服务器、数据库和插件实时指标'],
        help: ['帮助指令', '查看机器人当前支持的聊天指令'],
         settings: ['系统设置', '直接修改插件配置、网盘目录和数据库连接'],
        messages: ['消息记录', '查看群聊和私聊消息，回复、发送和撤回消息'],
      };
      let snapshot = null;
      let activePanTab = null;
      let toastTimer = null;
      const showNotice = (message) => { const node = $('notice'); node.textContent = message; node.classList.toggle('show', Boolean(message)); };
      const toast = (message) => { const node = $('toast'); node.textContent = message; node.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('show'), 2200); };
      const api = async (path, options = {}) => {
        const response = await fetch(`/api/${path}`, { cache:'no-store', credentials:'same-origin', headers:{'Content-Type':'application/json'}, ...options });
        const data = await response.json().catch(() => ({ok:false,error:'服务器返回格式错误'}));
        if (!response.ok || !data.ok) { const error = new Error(data.error || '请求失败'); error.status = response.status; throw error; }
        return data;
      };
      const viewFromUrl = () => { const current = new URLSearchParams(location.search).get('view'); return views[current] ? current : 'dashboard'; };
      const setView = (view, push = true) => {
        const next = views[view] ? view : 'dashboard';
        if (push) { const nextParams = new URLSearchParams(location.search); nextParams.set('view', next); history.pushState({view:next}, '', `${location.pathname}?${nextParams.toString()}`); }
        const meta = views[next];
        $('page-title').textContent = meta[0]; $('page-subtitle').textContent = meta[1];
        document.querySelectorAll('[data-page]').forEach((node) => { node.hidden = node.dataset.page !== next; });
        document.querySelectorAll('.sidebar [data-view]').forEach((node) => { const active = node.dataset.view === next; node.classList.toggle('active', active); node.setAttribute('aria-current', active ? 'page' : 'false'); });
        if (next === 'dashboard') $('page-eyebrow').textContent = '馒头Bot / 管理台'; else $('page-eyebrow').textContent = '馒头Bot / 功能页面';
        if (next === 'messages') { loadMsgChats(); if (msgState.chatId) loadMsgHistory(); }
        window.scrollTo({top:0, behavior:'auto'});
      };
      const switchHtml = (key, enabled, editable, label) => `<button class="switch ${enabled ? 'on' : ''}" data-switch="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(label)}" aria-pressed="${enabled}"><span></span></button>`;
      const platformGlyph = (name) => ({'番茄':'番','七猫':'猫','书旗':'旗','QQ阅读':'阅','QQ浏览器':'浏','得间':'得','点众':'众','盐言':'盐','塔读':'塔','百度':'度','小米':'米','晋江':'晋','宜搜':'搜','米读':'读','猫眼':'眼','酷我':'酷','酷匠':'匠','连城':'城','菠萝包':'菠'}[name] || String(name || '书').slice(0, 1));
      const categoryOrder = ['basic_settings', 'help_web_settings', 'uc_pan_settings', 'quark_pan_settings', 'baidu_pan_settings', 'database_settings'];
      const safeFieldValue = (field) => {
        if (field.kind === 'admin_list') return Array.isArray(field.value) ? field.value.join('\\n') : '';
        return field.secret ? '' : String(field.value ?? '');
      };
      const renderConfigEditor = (targetId, fields, editable, filter) => {
        const node = $(targetId);
        if (!node) return;
        const selected = (fields || []).filter((field) => !filter || filter(field));
        const groups = [];
        categoryOrder.forEach((category) => {
          const groupFields = selected.filter((field) => field.category === category);
          if (groupFields.length) groups.push([category, groupFields]);
        });
        selected.filter((field) => !categoryOrder.includes(field.category)).forEach((field) => {
          let group = groups.find((item) => item[0] === field.category);
          if (!group) { group = [field.category, []]; groups.push(group); }
          group[1].push(field);
        });
        if (!groups.length) { node.innerHTML = '<div class="empty">暂无可编辑配置</div>'; return; }
        node.innerHTML = groups.map(([category, groupFields]) => `<section class="config-group" data-config-category="${esc(category)}"><h3>${esc(groupFields[0].category_name || category)}</h3><div class="config-fields">${groupFields.map((field) => {
          const inputId = `cfg-${field.key}`;
          const label = esc(field.label || field.key);
          const hint = field.secret ? (field.configured ? '已配置，留空表示不修改' : '敏感值只写入，不在页面回显') : '';
          if (field.kind === 'admin_list') return `<div class="config-field full"><label for="${inputId}">${label}</label><textarea id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'} placeholder="每行一个 QQ 号">${esc(safeFieldValue(field))}</textarea><small>${hint || '共 ' + esc(field.count || 0) + ' 个管理员'}</small></div>`;
          if (field.kind === 'select') return `<div class="config-field"><label for="${inputId}">${label}</label><select id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'}>${(field.options || []).map((option) => `<option value="${esc(option)}" ${String(option) === String(field.value ?? '') ? 'selected' : ''}>${esc(option)}</option>`).join('')}</select><small>${hint}</small></div>`;
          const type = field.secret ? 'password' : (field.kind === 'number' ? 'number' : 'text');
          return `<div class="config-field"><label for="${inputId}">${label}</label><input id="${inputId}" type="${type}" data-config-field="${esc(field.key)}" value="${esc(safeFieldValue(field))}" ${editable ? '' : 'disabled'} placeholder="${esc(field.secret ? '留空不修改' : '')}"><small>${hint}</small></div>`;
        }).join('')}</div></section>`).join('') + `<div class="config-actions"><button class="primary-button" type="button" data-config-save ${editable ? '' : 'disabled'}>保存配置</button><span class="config-message" data-config-message></span></div>`;
        node.querySelector('[data-config-save]')?.addEventListener('click', () => saveConfig(node));
      };
       const saveConfig = async (editor) => {
        const fields = {};
        editor.querySelectorAll('[data-config-field]').forEach((input) => {
          const value = input.tagName === 'TEXTAREA' ? input.value : input.value;
          if (input.type === 'password' && !value.trim()) return;
           if (input.dataset.configField === 'group_file_cleanup_admin_qq') {
             fields[input.dataset.configField] = value.split(/[\\s,，]+/).filter(Boolean);
          } else fields[input.dataset.configField] = value;
        });
        const message = editor.querySelector('[data-config-message]');
        try { const result = await api('config', {method:'POST', body:JSON.stringify({fields})}); if (message) { message.textContent = result.message || '配置已保存'; message.className = 'config-message ok'; } toast(result.message || '配置已保存'); await load(); }
         catch (error) { if (error.status === 401) showAuthError(error); if (message) { message.textContent = error.message; message.className = 'config-message error'; } else toast(error.message); }
      };
      const panAccountRows = (item, editable) => (item.account_summary || []).map((account) => `<div class="account-row"><div><strong>账号${esc(account.index)}</strong><span>${esc(account.name || '未命名账号')} · ${esc(account.phone || '未获取')}</span></div><button type="button" data-pan-delete="${esc(item.key)}" data-index="${esc(account.index)}" ${editable ? '' : 'disabled'}>删除</button></div>`).join('');
       const renderPanCard = (item, pansEditable, configEditable) => { const directoryField = ({UC:'uc_pan_upload_dir','夸克':'quark_pan_upload_dir','百度':'baidu_pan_upload_dir'})[item.key] || ''; return `<article id="pan-card-${esc(item.key)}" class="pan-card ${item.active ? 'active' : ''}" data-pan-card="${esc(item.key)}" role="tabpanel" aria-labelledby="pan-tab-${esc(item.key)}"><div class="pan-top"><div class="pan-title"><div class="pan-logo">${esc(item.key.slice(0,1))}</div><strong>${esc(item.name)}</strong></div><div>${item.active ? '<span class="tag active">当前主网盘</span>' : ''}</div></div><div class="pan-meta"><div><span>配置状态</span><strong>${item.configured ? '<span class="tag ok">已配置</span>' : '<span class="tag off">未配置</span>'}</strong></div><div><span>账号数量</span><strong>${esc(item.accounts)} 个</strong></div><div><span>上传目录</span><strong title="${esc(item.directory)}">${esc(item.directory || '默认目录')}</strong></div><div><span>群账号选择</span><strong>默认账号${esc(item.selected_account || 1)}</strong></div></div><div class="pan-security-note">登录态：${item.configured ? '已保存（Cookie 不回显）' : '未配置'}${item.key === '夸克' ? ' · 可刷新账号资料' : ''}</div><div class="pan-directory"><input type="text" data-pan-dir="${esc(item.key)}" data-pan-dir-field="${esc(directoryField)}" value="${esc(item.directory || '')}" placeholder="/小说机器人" ${configEditable ? '' : 'disabled'}><button class="outline-button" type="button" data-pan-dir-save="${esc(item.key)}" ${configEditable ? '' : 'disabled'}>保存目录</button></div><div class="account-list">${panAccountRows(item, pansEditable) || '<div class="empty">暂无账号</div>'}</div><div class="account-add"><input type="password" data-pan-cookie="${esc(item.key)}" placeholder="粘贴 ${esc(item.name)} Cookie（只写入）" ${pansEditable ? '' : 'disabled'}><button class="outline-button" type="button" data-pan-add="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>添加账号</button></div><div class="account-actions"><button class="outline-button" type="button" data-pan-refresh="${esc(item.key)}" ${pansEditable && item.key === '夸克' ? '' : 'disabled'}>刷新资料</button><select class="pan-select" data-pan="${esc(item.key)}" ${pansEditable ? '' : 'disabled'} aria-label="选择${esc(item.name)}"><option value="">${item.active ? '当前使用中' : '设为主分享网盘'}</option><option value="${esc(item.key)}">切换到${esc(item.name)}</option></select></div><div class="group-account"><input type="text" data-pan-group="${esc(item.key)}" placeholder="QQ群号（用于选择账号）" ${pansEditable ? '' : 'disabled'}><select data-pan-group-index="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>${(item.account_summary || []).map((account) => `<option value="${esc(account.index)}" ${Number(account.index) === Number(item.selected_account || 1) ? 'selected' : ''}>账号${esc(account.index)}</option>`).join('') || '<option value="1">账号1</option>'}</select><button class="outline-button" type="button" data-pan-group-save="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>保存群选择</button></div></article>`; };
       const applyPanTab = (key) => { const cards = document.querySelectorAll('[data-pan-card]'); const tabs = document.querySelectorAll('[data-pan-tab]'); const available = Array.from(cards).map((node) => node.dataset.panCard); const selected = available.includes(key) ? key : (available[0] || ''); activePanTab = selected || null; try { if (selected) sessionStorage.setItem('mantou-pan-tab', selected); } catch (_) {} tabs.forEach((node) => { const isActive = node.dataset.panTab === selected; node.classList.toggle('active', isActive); node.setAttribute('aria-selected', String(isActive)); node.tabIndex = isActive ? 0 : -1; }); cards.forEach((node) => { const isActive = node.dataset.panCard === selected; node.hidden = !isActive; node.setAttribute('aria-hidden', String(!isActive)); }); };
       const choosePanTab = (key) => { applyPanTab(key); };
      const render = (data) => {
        snapshot = data;
        const auth = data.auth || {}; const novels = data.novels || {}; const pans = data.pans || {}; const server = data.server || {}; const database = data.database || {};
        const adminName = String(auth.username || '管理员');
        if ($('admin-name')) $('admin-name').textContent = adminName;
        if ($('admin-popover-name')) $('admin-popover-name').textContent = adminName;
        if ($('admin-avatar')) $('admin-avatar').textContent = adminName.slice(0, 1) || '管';
        if ($('admin-popover-role')) $('admin-popover-role').textContent = `${auth.role || '控制台管理员'} · 当前会话`;
        if ($('admin-popover-scope')) $('admin-popover-scope').textContent = `插件管理员白名单：${Number(auth.admin_count || 0)} 个`;
        $('metric-global').textContent = novels.global_enabled ? '已开启' : '已关闭'; $('metric-global-meta').textContent = novels.test_mode ? '测试模式已开启' : '测试模式未开启';
        $('metric-pan').textContent = pans.active || '--'; const activePan = (pans.items || []).find((item) => item.active); $('metric-pan-meta').textContent = activePan ? `${activePan.accounts} 个账号 · ${activePan.configured ? '已配置' : '未配置'}` : '未选择';
        $('metric-db').textContent = database.status || '--'; $('metric-db-meta').textContent = database.configured ? '状态可持久化' : '未配置数据库'; $('metric-version').textContent = `v${data.version || '--'}`; $('console-version').textContent = `v${data.version || '--'}`;
        $('dashboard-cpu').textContent = server.cpu || '--'; $('dashboard-memory').textContent = server.memory || '--'; $('dashboard-runtime').textContent = server.runtime || '--'; $('dashboard-updated').textContent = '刚刚';
        [['global-switch', '__global__', novels.global_enabled, '切换全局小说功能'], ['test-switch', '__test__', novels.test_mode, '切换管理员测试模式']].forEach(([id, key, enabled, label]) => { const node = $(id); node.className = `switch ${enabled ? 'on' : ''}`; node.dataset.switch = key; node.dataset.enabled = String(Boolean(enabled)); node.disabled = !novels.editable; node.setAttribute('aria-label', label); node.setAttribute('aria-pressed', String(Boolean(enabled))); });
        const platforms = novels.platforms || [];
        const enabledCount = platforms.filter((item) => item.enabled).length;
        const totalCount = platforms.length;
        const novelState = $('novel-state-pill');
        if (novelState) { novelState.classList.toggle('is-off', !novels.global_enabled); novelState.querySelector('strong').textContent = novels.global_enabled ? '入口已开启' : '入口已关闭'; }
        if ($('novel-master-label')) $('novel-master-label').textContent = novels.global_enabled ? '下载入口已开启' : '下载入口已关闭';
        if ($('novel-platform-summary')) $('novel-platform-summary').textContent = `已开启 ${enabledCount} 个平台`;
        if ($('novel-enabled-count')) $('novel-enabled-count').textContent = `${enabledCount} / ${totalCount} 已开启`;
        if ($('novel-test-label')) $('novel-test-label').textContent = novels.test_mode ? '测试模式已开启' : '测试模式未开启';
        $('novel-grid').innerHTML = platforms.map((item) => `<div class="novel-item ${item.enabled ? 'is-enabled' : 'is-disabled'}"><div class="novel-item-main"><div class="novel-badge">${esc(platformGlyph(item.name))}</div><div class="novel-item-copy"><div class="novel-item-title"><strong>${esc(item.name)}</strong><span class="novel-item-status">${item.enabled ? '已开启' : '已关闭'}</span></div><small>${item.enabled ? '允许识别链接并进入下载流程' : '当前不会响应此平台链接'}</small></div></div>${switchHtml(item.key, item.enabled, novels.editable, `切换${item.name}`)}</div>`).join('') || '<div class="empty">没有可用小说平台</div>';
        $('pan-active-label').textContent = pans.active || '--';
        $('pan-grid').innerHTML = (pans.items || []).map((item) => renderPanCard(item, pans.editable, pans.config_editable)).join('') || '<div class="empty">没有网盘数据</div>';
        let preferredPanTab = activePanTab; if (!preferredPanTab) { try { preferredPanTab = sessionStorage.getItem('mantou-pan-tab'); } catch (_) {} } applyPanTab(preferredPanTab || pans.active || 'UC');
        $('runtime-cpu').textContent = server.cpu || '--'; $('runtime-memory').textContent = server.memory || '--'; $('runtime-disk').textContent = server.disk || '--'; $('runtime-runtime').textContent = server.runtime || '--'; $('runtime-os').textContent = server.os || '--'; $('runtime-db').textContent = database.status || '--'; $('runtime-pan').textContent = pans.active || '--'; $('runtime-version').textContent = `v${data.version || '--'}`;
        const configList = $('config-list'); if (configList) configList.innerHTML = `<div class="config-item"><span>监听地址</span><strong>${esc(server.listen || '--')}</strong></div><div class="config-item"><span>访问地址</span><strong title="${esc(server.address)}">${esc(server.address || '--')}</strong></div><div class="config-item"><span>域名模式</span><strong>${data.config && data.config.custom_domain ? '自定义域名' : '自动服务器 IP'}</strong></div><div class="config-item"><span>登录方式</span><strong>${esc(data.config && data.config.auth_mode || '账号密码会话')}</strong></div>`;
        const configFields = data.config && data.config.fields || [];
        renderConfigEditor('basic-config-editor', configFields, Boolean(data.config && data.config.editable), (field) => ['basic_settings', 'help_web_settings'].includes(field.category));
        renderConfigEditor('settings-editor', configFields, Boolean(data.config && data.config.editable), (field) => ['database_settings', 'uc_pan_settings', 'quark_pan_settings', 'baidu_pan_settings'].includes(field.category));
        renderQQAuthEditor(data.qq_reader || {});
        $('updated').textContent = '刚刚更新';
        document.querySelectorAll('[data-switch]').forEach((node) => node.addEventListener('click', () => changeNovel(node)));
        document.querySelectorAll('[data-pan]').forEach((node) => node.addEventListener('change', () => { const value = node.value; node.value = ''; if (value) changePan(value, node); }));
        document.querySelectorAll('[data-pan-add]').forEach((node) => node.addEventListener('click', () => addPanAccount(node.dataset.panAdd)));
        document.querySelectorAll('[data-pan-delete]').forEach((node) => node.addEventListener('click', () => deletePanAccount(node.dataset.panDelete, node.dataset.index)));
        document.querySelectorAll('[data-pan-refresh]').forEach((node) => node.addEventListener('click', () => refreshPanAccounts(node.dataset.panRefresh, node)));
        document.querySelectorAll('[data-pan-group-save]').forEach((node) => node.addEventListener('click', () => savePanGroup(node.dataset.panGroupSave)));
        document.querySelectorAll('[data-pan-dir-save]').forEach((node) => node.addEventListener('click', () => savePanDirectory(node.dataset.panDirSave, node)));
        document.querySelectorAll('[data-pan-tab]').forEach((node) => { node.addEventListener('click', () => choosePanTab(node.dataset.panTab)); node.addEventListener('keydown', (event) => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const tabs = Array.from(document.querySelectorAll('[data-pan-tab]')); const index = tabs.indexOf(node); const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length]; next?.focus(); choosePanTab(next?.dataset.panTab); } }); });
      };
      const renderQQAuthEditor = (auth) => {
        const node = $('qq-auth-editor'); if (!node) return;
        node.innerHTML = `<div class="qq-auth-form"><div class="qq-auth-row"><input type="text" id="qq-ywguid" placeholder="ywguid" autocomplete="off"><input type="password" id="qq-ywkey" placeholder="ywkey" autocomplete="off"></div><div class="qq-auth-actions"><button class="primary-button" type="button" id="qq-auth-save">保存登录态</button><button class="outline-button" type="button" id="qq-auth-delete" ${auth.configured ? '' : 'disabled'}>清除登录态</button><span class="qq-auth-message">${auth.configured ? `已配置${auth.updated_at ? ` · ${new Date(auth.updated_at * 1000).toLocaleString()}` : ''}` : '未配置'}</span></div></div>`;
        $('qq-auth-save').addEventListener('click', saveQQAuth); $('qq-auth-delete').addEventListener('click', deleteQQAuth);
      };
       const addPanAccount = async (platform) => { const input = document.querySelector(`[data-pan-cookie="${CSS.escape(platform)}"]`); const button = document.querySelector(`[data-pan-add="${CSS.escape(platform)}"]`); const cookie = input?.value.trim(); if (!cookie) return toast('请先粘贴 Cookie'); if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}`, {method:'POST', body:JSON.stringify({cookie})}); if (input) input.value = ''; toast(`${platform}账号已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const deletePanAccount = async (platform, index, button) => { if (!confirm(`确定删除${platform}账号${index}吗？`)) return; if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}`, {method:'DELETE', body:JSON.stringify({index:Number(index)})}); toast('账号已删除'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const refreshPanAccounts = async (platform, button) => { if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}?refresh=1`); toast('账号资料已刷新'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const savePanDirectory = async (platform, button) => { const input = document.querySelector(`[data-pan-dir="${CSS.escape(platform)}"]`); const field = input?.dataset.panDirField; const value = input?.value.trim(); if (!field || !value) return toast('请输入上传目录'); if (button) button.disabled = true; try { const result = await api('config', {method:'POST', body:JSON.stringify({fields:{[field]:value}})}); toast(result.message || `${platform}上传目录已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const savePanGroup = async (platform) => { const group = document.querySelector(`[data-pan-group="${CSS.escape(platform)}"]`)?.value.trim(); const select = document.querySelector(`[data-pan-group-index="${CSS.escape(platform)}"]`); if (!group) return toast('请输入QQ群号'); if (!/^\\d+$/.test(group)) return toast('QQ群号格式无效'); try { await api('pan-account-selection', {method:'POST', body:JSON.stringify({platform, index:Number(select?.value || 1), group_id:group})}); toast('群账号选择已保存'); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const saveQQAuth = async () => { const ywguid = $('qq-ywguid')?.value.trim(); const ywkey = $('qq-ywkey')?.value.trim(); if (!ywguid || !ywkey) return toast('请填写 ywguid 和 ywkey'); const button = $('qq-auth-save'); if (button) button.disabled = true; try { await api('qq-reader-auth', {method:'POST', body:JSON.stringify({ywguid, ywkey})}); if ($('qq-ywguid')) $('qq-ywguid').value = ''; if ($('qq-ywkey')) $('qq-ywkey').value = ''; toast('QQ阅读登录态已保存'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const deleteQQAuth = async () => { if (!confirm('确定清除 QQ阅读登录态吗？')) return; const button = $('qq-auth-delete'); if (button) button.disabled = true; try { await api('qq-reader-auth', {method:'DELETE'}); toast('QQ阅读登录态已清除'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
      const showAuthError = (error) => { if (error.status === 401) { location.reload(); return; } if ($('popover-logout')) $('popover-logout').hidden = true; showNotice(error.status === 503 ? '登录服务尚未启用，请联系管理员。' : '控制台数据暂时不可用，请稍后重试。'); };
      const adminChip = $('admin-chip'); const adminPopover = $('admin-popover');
      adminChip?.addEventListener('click', (event) => { event.stopPropagation(); const expanded = adminChip.getAttribute('aria-expanded') === 'true'; adminChip.setAttribute('aria-expanded', String(!expanded)); if (adminPopover) adminPopover.hidden = expanded; });
      document.addEventListener('click', () => { if (adminChip?.getAttribute('aria-expanded') === 'true') { adminChip.setAttribute('aria-expanded', 'false'); if (adminPopover) adminPopover.hidden = true; } });
      const changeNovel = async (node) => { if (!snapshot || !snapshot.novels.editable) return toast('数据库未配置，开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { await api('novel-switch', {method:'POST', body:JSON.stringify({key:node.dataset.switch, enabled})}); toast('小说开关已更新'); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const changePan = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘选择不能保存'); if (node) node.disabled = true; try { await api('pan-switch', {method:'POST', body:JSON.stringify({key})}); toast('主分享网盘已更新'); await load(); } catch (error) { if (node) node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const load = async () => { try { render(await api('dashboard')); if ($('popover-logout')) $('popover-logout').hidden = false; setView(viewFromUrl(), false); } catch (error) { showAuthError(error); } };
      $('popover-logout').addEventListener('click', async () => { try { await api('logout', {method:'POST'}); } finally { location.reload(); } });
      document.querySelectorAll('.sidebar [data-view]').forEach((node) => node.addEventListener('click', (event) => { event.preventDefault(); setView(node.dataset.view); }));
      window.addEventListener('popstate', () => setView(viewFromUrl(), false));

      // ---------- 消息记录页 ----------
      const msgState = { filter:'all', search:'', page:1, chatId:'', chatType:'group', messages:[], quote:null, mute:{member:'',name:''}, sendType:'text', sendMode:'default', muteMinutes:30, timer:null, lastRolesAt:0, lastRolesChatId:'', botIsAdmin:false, profiles:{}, pastedImage:null, sending:false, multi:false, selected:new Set(), ctxMsg:null, ctxUser:null };
      const msgComposerTabs = [['text','文本'],['markdown','Markdown'],['media','媒体'],['ark','ARK模板'],['card','图文卡片']];
      const msgFilterLabels = { all:'全量', remark:'备注', group:'群聊', user:'私聊' };
      const avatarUrl = (openid, type, appid) => {
        if (!openid) return '';
        if (type === 'group') { const qq = window.msgGroupQQ?.[openid] || ''; return qq ? `https://p.qlogo.cn/gh/${qq}/${qq}/100/` : ''; }
        const aid = appid || window.msgAppid || '';
        return aid ? `https://q.qlogo.cn/qqapp/${aid}/${openid}/0` : '';
      };
      const avatarImg = (url, letter) => `<img src="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.closest('.msg-chat-avatar, .msg-avatar').classList.add('avatar-fallback'); this.remove();">`;
      const avatarHtml = (url, letter) => {
        if (!url) return esc(String(letter || '?').slice(0, 1));
        return `<span class="avatar-letter">${esc(String(letter || '?').slice(0, 1))}</span>` + avatarImg(url, letter);
      };
      const msgTypeName = (m) => {
        const c = String(m.content || '');
        if (c.startsWith('[媒体]')) return '媒体';
        if (c.startsWith('[ARK卡片]')) return 'ARK';
        if (c.startsWith('[图文卡片]')) return '卡片';
        return '文本';
      };
      const fmtChatTime = (ts) => {
        const s = String(ts || '').trim();
        if (!s) return '';
        const d = new Date(s.replace('T', ' ').replace(/-/g, '/'));
        if (isNaN(d.getTime())) return s.slice(5, 16);
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const sameDay = d.toDateString() === now.toDateString();
        const yest = new Date(now); yest.setDate(now.getDate() - 1);
        if (sameDay) return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
        if (d.toDateString() === yest.toDateString()) return '昨天';
        if (d.getFullYear() === now.getFullYear()) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      };
      const renderMsgChats = (data) => {
        const node = $('msg-chats'); const chats = data.chats || [];
        window.msgGroupQQ = {}; (chats||[]).forEach((chat) => { if (chat.group_qq) window.msgGroupQQ[chat.chat_id] = chat.group_qq; });
        if (!chats.length) { node.innerHTML = '<div class="msg-empty">暂无消息会话，机器人收到消息后会出现在这里</div>'; return; }
        node.innerHTML = chats.map((chat) => {
          const av = avatarUrl(chat.chat_id, chat.chat_type, chat.appid);
          if (chat.appid) window.msgAppid = chat.appid;
          const typeTag = chat.chat_type === 'user' ? '<span class="msg-chat-type">私聊</span>' : '<span class="msg-chat-type">群聊</span>';
          return `<button type="button" class="msg-chat ${msgState.chatId === chat.chat_id ? 'active' : ''}" data-msg-chat="${esc(chat.chat_id)}" data-msg-type="${esc(chat.chat_type)}">
            <span class="msg-chat-avatar">${avatarHtml(av, chat.nickname || '群')}</span>
            <span class="msg-chat-main"><span class="msg-chat-top"><strong>${esc(chat.nickname || chat.chat_id)}</strong>${typeTag}<small>${esc(fmtChatTime(chat.last_time))}</small></span>
            <span class="msg-chat-sub">${esc(String(chat.last_content || '（无文本内容）').replace(/<@([A-Za-z0-9_-]{5,128})>/g, (all, oid) => '@' + oid.slice(0, 6) + '…'))}</span>
            <span class="msg-chat-meta">${chat.chat_type === 'group' ? `群消息 ${chat.msg_count} 条` : `私聊消息 ${chat.msg_count} 条`}${chat.remark ? ' · 已备注' : ''}</span></span>
          </button>`;
        }).join('');
        node.querySelectorAll('[data-msg-chat]').forEach((el) => el.addEventListener('click', () => { if (msgState.multi) exitMultiMode(); msgState.chatId = el.dataset.msgChat; msgState.chatType = el.dataset.msgType; loadMsgHistory(); renderMsgChats({chats}); }));
      };
      const loadMsgChats = async () => {
        try { const data = await api('message/chats', {method:'POST', body:JSON.stringify({filter:msgState.filter, search:msgState.search, page:msgState.page, page_size:50})}); renderMsgChats(data); }
        catch (error) { if (error.status === 401) showAuthError(error); else $('msg-chats').innerHTML = `<div class="msg-empty">${esc(error.message)}</div>`; }
      };
      const fmtDayLabel = (ts) => {
        const s = String(ts || '').trim();
        if (!s) return '';
        const d = new Date(s.replace('T', ' ').replace(/-/g, '/'));
        if (isNaN(d.getTime())) return s.slice(0, 10);
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        if (d.toDateString() === now.toDateString()) return '今天';
        const yest = new Date(now); yest.setDate(now.getDate() - 1);
        if (d.toDateString() === yest.toDateString()) return '昨天';
        if (d.getFullYear() === now.getFullYear()) return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
        return s.slice(0, 10);
      };
      const fmtMsgTime = (ts) => {
        const s = String(ts || '').trim();
        if (!s) return '';
        const d = new Date(s.replace('T', ' ').replace(/-/g, '/'));
        if (isNaN(d.getTime())) return s.slice(11, 16);
        const pad = (n) => String(n).padStart(2, '0');
        return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
      };
      const updateMsgAdminTag = () => {
        const el = $('msg-admin-tag');
        if (!el) return;
        el.hidden = !(msgState.chatType === 'group' && msgState.botIsAdmin);
      };
      const updateMsgHead = (data) => {
        $('msg-head-name').textContent = data.chat_name || '未命名会话';
        const gInfo = data.group_info || {};
        const gNum = Number(gInfo.member_num || 0);
        $('msg-head-sub').textContent = msgState.chatType === 'group'
          ? `群聊 · ${esc(msgState.chatId)}${gNum > 0 ? ` · 群成员 ${gNum} 人` : ''}`
          : `私聊 · ${esc(msgState.chatId)}`;
      };
      const showMsgCtx = (x, y, items) => {
        const ctx = $('msg-ctx');
        ctx.innerHTML = items.map((it) => it.sep ? '<div class="msg-ctx-sep"></div>' : `<button class="msg-ctx-item${it.danger ? ' danger' : ''}" type="button">${esc(it.label)}</button>`).join('');
        ctx.hidden = false;
        const pad = 8;
        const rect = ctx.getBoundingClientRect();
        const left = Math.min(x, window.innerWidth - rect.width - pad);
        const top = Math.min(y, window.innerHeight - rect.height - pad);
        ctx.style.left = left + 'px';
        ctx.style.top = top + 'px';
        ctx.querySelectorAll('.msg-ctx-item').forEach((btn, idx) => {
          const item = items.filter((it) => !it.sep)[idx];
          btn.addEventListener('click', () => { hideMsgCtx(); if (item && item.action) item.action(); });
        });
      };
      const hideMsgCtx = () => { $('msg-ctx').hidden = true; $('msg-ctx').innerHTML = ''; };
      document.addEventListener('click', (e) => { if (!$('msg-ctx').contains(e.target)) hideMsgCtx(); });
      document.addEventListener('contextmenu', (e) => { if (!$('msg-ctx').contains(e.target)) hideMsgCtx(); });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideMsgCtx(); });
      const atMember = (uid, nick) => {
        if (!uid) return;
        // QQ 官方群聊提及只支持 Markdown 消息，自动切换到 Markdown 类型
        if (msgState.sendType !== 'markdown' && msgState.sendType !== 'text') { toast('请先切换到文本或 Markdown 类型再 @ 成员'); return; }
        if (msgState.sendType !== 'markdown') {
          msgState.sendType = 'markdown';
          $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x.dataset.msgType === 'markdown'));
          renderMsgExtra();
        }
        const ta = $('msg-textarea');
        ta.focus();
        const mention = `<@${uid}> `;
        const start = ta.selectionStart ?? ta.value.length;
        ta.value = ta.value.slice(0, start) + mention + ta.value.slice(ta.selectionEnd ?? start);
        ta.selectionStart = ta.selectionEnd = start + mention.length;
        ta.dispatchEvent(new Event('input'));
        toast(`已插入 @${nick || uid}（将以 Markdown 发送）`);
      };
      const copyMsgText = async (text) => {
        try { await navigator.clipboard.writeText(text); toast('已复制'); }
        catch (error) { toast('复制失败：' + error.message); }
      };
      const enterMultiMode = () => {
        msgState.multi = true; msgState.selected.clear();
        $('msg-multi-bar').hidden = false;
        $('msg-multi-count').textContent = '已选 0 条';
        $('msg-body').classList.add('multi-mode');
        $('msg-body').querySelectorAll('.msg-row').forEach((row) => row.classList.add('multi-mode'));
      };
      const exitMultiMode = () => {
        msgState.multi = false; msgState.selected.clear();
        $('msg-multi-bar').hidden = true;
        $('msg-body').classList.remove('multi-mode');
        $('msg-body').querySelectorAll('.msg-row').forEach((row) => { row.classList.remove('multi-mode'); row.classList.remove('selected'); });
      };
      const recallSelected = async () => {
        const ids = [...msgState.selected];
        if (!ids.length) return toast('请先选择要撤回的消息');
        if (!confirm(`确定撤回选中的 ${ids.length} 条消息吗？发送超过 2 分钟的消息不可撤回。`)) return;
        let okCount = 0; let failCount = 0;
        for (const id of ids) {
          try { await api('message/recall', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, message_id:id})}); okCount++; }
          catch (error) { failCount++; }
        }
        toast(`撤回完成：成功 ${okCount} 条${failCount ? `，失败 ${failCount} 条` : ''}`);
        exitMultiMode(); loadMsgHistory();
      };
      const renderMsgMessages = (data) => {
        const body = $('msg-body'); const msgs = data.messages || [];
        window.msgAppid = data.messages?.[0]?.appid || window.msgAppid || '';
        updateMsgHead(data);
        updateMsgAdminTag();
        $('msg-refresh-info').hidden = msgState.chatType !== 'group';
        $('msg-remark').hidden = msgState.chatType !== 'group';
        if (!msgs.length) { body.innerHTML = '<div class="msg-empty">暂无消息记录</div>'; return; }
        let lastDay = ''; let html = '';
        if (data.has_more) html += '<button class="msg-load-older" id="msg-load-older" type="button">加载更早消息</button>';
        msgs.forEach((m) => {
          const day = String(m.timestamp||'').slice(0,10);
          if (day !== lastDay && day) { html += `<div class="msg-day">${esc(fmtDayLabel(m.timestamp))}</div>`; lastDay = day; }
          const isSelf = Boolean(m.is_self);
          const recalled = Boolean(m.recalled);
          const profiles = data.member_profiles || {};
          msgState.profiles = profiles;
          const profile = profiles[m.user_id] || {};
          const av = isSelf ? '' : avatarUrl(m.user_id, 'user', data.messages?.[0]?.appid || window.msgAppid);
          const tags = [];
          if (isSelf) tags.push('<span class="msg-tag self">我</span>');
          if (m.source === 'web_panel') tags.push('<span class="msg-tag">网页</span>');
          if (recalled) tags.push('<span class="msg-tag recalled">已撤回</span>');
          const roleMap = {owner:'群主', admin:'管理', member:'群员'};
          const roleTag = roleMap[profile.role] || roleMap[String(m.raw_message||'').match(/member_role[^,]*?['\"]([a-z]+)['\"]/)?.[1] || ''];
          if (!isSelf && roleTag) tags.push(`<span class="msg-tag role">${roleTag}</span>`);
          const renderText = (text) => {
            let out = String(text || '');
            out = out.replace(/<@([A-Za-z0-9_-]{5,128})>/g, (all, oid) => {
              const nm = profiles[oid]?.nickname || '';
              return nm ? `@${nm}` : all;
            });
            return out;
          };
          const ref = (data.references || {})[m.reference_id];
          // 撤回后隐藏引用与媒体，只显示已撤回
          const quote = !recalled && m.reference_id ? (ref ? `<div class="msg-bubble-quote"><b>${esc(ref.nickname || '')}</b>：${esc(ref.content || '')}</div>` : `<div class="msg-bubble-quote">引用消息 ${esc(m.reference_id)}</div>`) : '';
          const media = !recalled && m.media && m.media.src ? (m.media.type === '图片' ? `<div class="msg-media"><img src="${esc(m.media.src)}" alt="图片" loading="lazy" referrerpolicy="no-referrer"></div>` : `<div class="msg-media"><span class="msg-tag">[${esc(m.media.type)}]</span> <span style="word-break:break-all;font-size:11px;color:#999">${esc(m.media.src)}</span></div>`) : '';
          const content = recalled ? '（消息已撤回）' : renderText(m.content || '（空消息）');
          // 权限：撤回自己发的消息总是可以；撤回他人消息需要机器人为管理员；禁言需要机器人为管理员且对方非群主/管理员
          const canRecall = Boolean(m.message_id) && !recalled && (isSelf || msgState.botIsAdmin);
          const canMute = !isSelf && msgState.chatType === 'group' && Boolean(m.user_id) && msgState.botIsAdmin && profile.role !== 'owner' && profile.role !== 'admin';
          const actions = [];
          if (canRecall) actions.push(`<button class="msg-action" data-msg-recall="${esc(m.message_id)}" type="button">撤回</button>`);
          if (!isSelf && msgState.chatType === 'group' && m.user_id) actions.push(`<button class="msg-action" data-msg-quote="${esc(m.message_id)}" data-msg-user="${esc(m.user_id)}" data-msg-name="${esc(m.nickname||'')}" type="button">引用</button>`);
          if (canMute) actions.push(`<button class="msg-action" data-msg-mute="${esc(m.user_id)}" data-msg-mute-name="${esc(m.nickname||'')}" type="button">禁言</button>`);
          if (m.raw_message) actions.push(`<button class="msg-action" data-msg-raw="${msgState.chatId}_${m.id}" type="button">原始数据</button>`);
          window._msgRaw = window._msgRaw || {}; window._msgRaw[`${msgState.chatId}_${m.id}`] = m.raw_message;
          const isSelected = msgState.selected.has(m.message_id);
          const multiEnabled = canRecall;
          html += `<div class="msg-row ${isSelf ? 'self' : ''}${msgState.multi ? ' multi-mode' : ''}${isSelected ? ' selected' : ''}${multiEnabled ? '' : ' no-multi'}" data-msg-mid="${esc(m.message_id)}" data-msg-uid="${esc(m.user_id)}" data-msg-nick="${esc(m.nickname||'')}" data-msg-self="${isSelf ? '1' : ''}" data-msg-recalled="${recalled ? '1' : ''}" data-msg-content="${esc(m.content || '')}">
            <span class="msg-pos">
              <span class="msg-multi-check"></span>
              <span class="msg-avatar">${avatarHtml(av, m.nickname || '?')}</span>
            </span>
            <div class="msg-bubble-wrap"><div class="msg-bubble-name">${esc(m.nickname||'')}${tags.length ? `<span class="msg-tags">${tags.join('')}</span>` : ''}</div>
              <div class="msg-bubble ${recalled ? 'recalled' : ''}">${quote}${esc(content)}${media}</div>
              <div class="msg-meta">${esc(fmtMsgTime(m.timestamp))}${m.message_id ? ` · ${esc(m.message_id.slice(0,18))}…` : ''}</div>
              ${actions.length ? `<div class="msg-actions">${actions.join('')}</div>` : ''}
            </div></div>`;
        });
        body.innerHTML = html;
        body.scrollTop = body.scrollHeight;
        body.querySelector('#msg-load-older')?.addEventListener('click', () => loadMsgHistory(true));
        body.querySelectorAll('[data-msg-recall]').forEach((el) => el.addEventListener('click', () => recallMessage(el.dataset.msgRecall)));
        body.querySelectorAll('[data-msg-quote]').forEach((el) => el.addEventListener('click', () => { msgState.quote = {id:el.dataset.msgQuote, text:el.dataset.msgName || '引用消息'}; $('msg-quote-preview').hidden = false; $('msg-quote-text').textContent = `${el.dataset.msgName} · 引用`; }));
        body.querySelectorAll('[data-msg-mute]').forEach((el) => el.addEventListener('click', () => { msgState.mute = {member:el.dataset.msgMute, name:el.dataset.msgMuteName}; $('msg-mute-title').textContent = `禁言 ${el.dataset.msgMuteName || el.dataset.msgMute}`; $('msg-mute-modal').hidden = false; }));
        body.querySelectorAll('[data-msg-raw]').forEach((el) => el.addEventListener('click', () => { $('msg-raw-content').textContent = window._msgRaw?.[el.dataset.msgRaw] || '无原始数据'; $('msg-raw-modal').hidden = false; }));
        body.querySelectorAll('.msg-row').forEach((row) => {
          row.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const mid = row.dataset.msgMid;
            const uid = row.dataset.msgUid;
            const nick = row.dataset.msgNick;
            const isSelf = row.dataset.msgSelf === '1';
            const recalled = row.dataset.msgRecalled === '1';
            const content = row.dataset.msgContent || '';
            if (msgState.multi) {
              toggleMsgSelect(row, mid);
              return;
            }
            const profile = (msgState.profiles || {})[uid] || {};
            const canMuteRow = !isSelf && msgState.chatType === 'group' && uid && msgState.botIsAdmin && profile.role !== 'owner' && profile.role !== 'admin';
            const canRecallRow = Boolean(mid) && !recalled && (isSelf || msgState.botIsAdmin);
            const items = [];
            if (!isSelf && msgState.chatType === 'group' && uid) items.push({label:'@' + (nick || 'TA'), action:() => atMember(uid, nick)});
            if (canMuteRow) items.push({label:'禁言', action:() => { msgState.mute = {member:uid, name:nick}; $('msg-mute-title').textContent = `禁言 ${nick || uid}`; $('msg-mute-modal').hidden = false; }});
            if (items.length && !isSelf) items.push({sep:true});
            if (!isSelf && msgState.chatType === 'group' && mid) items.push({label:'引用', action:() => { msgState.quote = {id:mid, text:nick || '引用消息'}; $('msg-quote-preview').hidden = false; $('msg-quote-text').textContent = `${nick} · 引用`; }});
            if (content) items.push({label:'复制', action:() => copyMsgText(content)});
            if (canRecallRow) items.push({label:'撤回', danger:true, action:() => recallMessage(mid)});
            if (mid) items.push({sep:true});
            items.push({label:'多选', action:() => { enterMultiMode(); if (canRecallRow) toggleMsgSelect(row, mid); }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
          row.addEventListener('click', (e) => {
            if (msgState.multi && !e.target.closest('button')) {
              const canSel = Boolean(row.dataset.msgMid) && !(row.dataset.msgRecalled === '1') && (row.dataset.msgSelf === '1' || msgState.botIsAdmin);
              if (canSel) toggleMsgSelect(row, row.dataset.msgMid);
            }
          });
          row.querySelector('.msg-avatar')?.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const uid = row.dataset.msgUid;
            const nick = row.dataset.msgNick;
            const isSelf = row.dataset.msgSelf === '1';
            if (msgState.multi) return;
            const profileA = (msgState.profiles || {})[uid] || {};
            const canMuteAv = !isSelf && msgState.chatType === 'group' && uid && msgState.botIsAdmin && profileA.role !== 'owner' && profileA.role !== 'admin';
            const items = [];
            if (!isSelf && msgState.chatType === 'group' && uid) items.push({label:'@' + (nick || 'TA'), action:() => atMember(uid, nick)});
            if (canMuteAv) items.push({label:'禁言', action:() => { msgState.mute = {member:uid, name:nick}; $('msg-mute-title').textContent = `禁言 ${nick || uid}`; $('msg-mute-modal').hidden = false; }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
        });
      };
      const toggleMsgSelect = (row, mid) => {
        if (!mid) return;
        if (msgState.selected.has(mid)) { msgState.selected.delete(mid); row.classList.remove('selected'); }
        else { msgState.selected.add(mid); row.classList.add('selected'); }
        $('msg-multi-count').textContent = `已选 ${msgState.selected.size} 条`;
      };
      const loadMsgHistory = async (older = false, quiet = false) => {
        if (!msgState.chatId) return;
        $('msg-composer').hidden = false;
        try {
          const before = older ? (msgState.messages[0]?.timestamp || '') : '';
          const data = await api('message/history', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, chat_type:msgState.chatType, before_date:before, limit:120})});
          const incoming = data.messages || [];
          if (quiet && !older) {
            updateMsgHead(data);
            const prevLast = msgState.messages[msgState.messages.length - 1]?.message_id || '';
            const newLast = incoming[incoming.length - 1]?.message_id || '';
            if (prevLast === newLast && incoming.length === msgState.messages.length) { return; }
          }
          msgState.messages = older ? [...incoming, ...msgState.messages] : incoming;
          renderMsgMessages({...data, messages: msgState.messages});
          loadGroupRoles(true);
        } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); }
      };
      const loadGroupRoles = async (throttled = false) => {
        if (msgState.chatType !== 'group' || !msgState.chatId) return;
        const now = Date.now();
        if (throttled && msgState.lastRolesChatId === msgState.chatId && msgState.lastRolesAt && now - msgState.lastRolesAt < 60000) return;
        msgState.lastRolesAt = now; msgState.lastRolesChatId = msgState.chatId;
        try { const data = await api('message/group-roles', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId})}); msgState.botIsAdmin = Boolean(data.bot_is_admin); updateMsgAdminTag(); }
        catch (error) { msgState.botIsAdmin = false; updateMsgAdminTag(); }
      };
      const recallMessage = async (messageId) => {
        if (!confirm('确定撤回这条消息吗？发送超过 2 分钟的消息不可撤回。')) return;
        try { await api('message/recall', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, message_id:messageId})}); toast('撤回成功'); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const refreshGroupInfo = async () => {
        if (!msgState.chatId) return;
        try { const data = await api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId})}); toast(data.group_name ? `群信息已刷新：${data.group_name}${data.member_num ? `（成员 ${data.member_num} 人）` : ''}` : (data.member_num ? `群信息已刷新：成员 ${data.member_num} 人` : '群信息已刷新')); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const showRemarkDialog = async () => {
        if (!msgState.chatId) return;
        let data = {}; try { data = await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, action:'get'})}); } catch (error) { data = {}; }
        $('msg-remark-name').value = data.remark || '';
        $('msg-remark-qq').value = data.group_qq || '';
        $('msg-remark-modal').hidden = false;
      };
      const saveRemark = async () => {
        const remark = $('msg-remark-name').value.trim();
        const groupQQ = $('msg-remark-qq').value.trim();
        try { await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, remark, group_qq:groupQQ})}); toast('备注已保存'); $('msg-remark-modal').hidden = true; loadMsgChats(); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const deleteRemark = async () => {
        if (!confirm('确定删除该会话的备注和群号吗？')) return;
        try { await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, action:'delete'})}); toast('备注已删除'); $('msg-remark-modal').hidden = true; loadMsgChats(); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const sendMessage = async () => {
        if (msgState.sending) return;
        const content = $('msg-textarea').value.trim();
        const customId = $('msg-custom-id').value.trim();
        const payload = { chat_id:msgState.chatId, chat_type:msgState.chatType, msg_type:msgState.sendType, content, send_mode:msgState.sendMode, custom_id:customId, quote_message_id:msgState.quote?.id || '' };
        if (msgState.sendType === 'media') {
          payload.media_file_type = Number($('msg-media-type')?.value || 1);
          payload.media = $('msg-media-path')?.value.trim() || '';
          payload.media_url = $('msg-media-url')?.value.trim() || '';
          if (!payload.media && !payload.media_url && !msgState.pastedImage) return toast('请填写媒体文件路径或 URL');
        }
        if (msgState.pastedImage) { payload.image_data = msgState.pastedImage; }
        if (msgState.sendType === 'ark') {
          payload.ark_template_id = $('msg-ark-template')?.value || '24';
          const fields = {};
          document.querySelectorAll('#msg-extra [data-ark-field]').forEach((el) => { const v = el.value.trim(); if (v) fields[el.dataset.arkField] = v; });
          payload.ark_fields = fields;
          payload.ark_list = $('msg-ark-list')?.value.trim() || '';
        }
        if (msgState.sendType === 'card') {
          payload.card = { title: $('msg-card-title')?.value.trim() || '', description: $('msg-card-desc')?.value.trim() || '', pic_url: $('msg-card-pic')?.value.trim() || '', url: $('msg-card-url')?.value.trim() || '' };
          if (!payload.card.title) return toast('请填写卡片标题');
        }
        if (!content && !msgState.pastedImage && !['media','ark','card'].includes(msgState.sendType)) return toast('请输入消息内容');
        msgState.sending = true;
        const btn = $('msg-send'); btn.disabled = true; $('msg-send-status').textContent = '发送中...';
        try { const result = await api('message/send', {method:'POST', body:JSON.stringify(payload)}); toast('发送成功'); $('msg-textarea').value = ''; msgState.quote = null; msgState.pastedImage = null; $('msg-quote-preview').hidden = true; $('msg-img-preview').hidden = true; $('msg-img-thumb').removeAttribute('src'); loadMsgHistory(); }
        catch (error) { toast(error.message); }
        finally { btn.disabled = false; $('msg-send-status').textContent = ''; msgState.sending = false; }
      };
      const renderMsgExtra = () => {
        const extra = $('msg-extra'); const type = msgState.sendType;
        if (type === 'media') { extra.hidden = false; extra.innerHTML = `<input id="msg-media-type" type="number" min="1" max="4" value="1" title="1图片 2视频 3语音 4文件"><input id="msg-media-path" type="text" placeholder="本地文件路径（服务器）"><input id="msg-media-url" type="text" placeholder="或媒体 URL"><input type="text" placeholder="媒体说明（可选，显示在消息中）" id="msg-media-text">`; }
        else if (type === 'ark') { extra.hidden = false; extra.innerHTML = `<select id="msg-ark-template"><option value="23">23 链接列表</option><option value="24" selected>24 文本卡片</option><option value="37">37 大图卡片</option></select><input data-ark-field="#DESC#" type="text" placeholder="#DESC# 描述"><input data-ark-field="#PROMPT#" type="text" placeholder="#PROMPT# 提示"><input data-ark-field="#TITLE#" type="text" placeholder="#TITLE# 标题"><input data-ark-field="#METADESC#" type="text" placeholder="#METADESC# 元描述"><input data-ark-field="#IMG#" type="text" placeholder="#IMG# 图片URL"><input data-ark-field="#LINK#" type="text" placeholder="#LINK# 跳转链接"><input data-ark-field="#SUBTITLE#" type="text" placeholder="#SUBTITLE# 副标题"><textarea id="msg-ark-list" class="msg-textarea" style="min-height:52px" placeholder="23 模板列表：每行 描述|链接"></textarea>`; }
        else if (type === 'card') { extra.hidden = false; extra.innerHTML = `<input id="msg-card-title" type="text" placeholder="卡片标题"><input id="msg-card-desc" type="text" placeholder="卡片描述"><input id="msg-card-pic" type="text" placeholder="图片 URL"><input id="msg-card-url" type="text" placeholder="跳转 URL">`; }
        else { extra.hidden = true; extra.innerHTML = ''; }
      };
      $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((el) => el.addEventListener('click', () => { $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((x) => x.classList.toggle('active', x === el)); msgState.filter = el.dataset.msgFilter; msgState.page = 1; loadMsgChats(); }));
      $('msg-search-btn').addEventListener('click', () => { msgState.search = $('msg-search-input').value.trim(); msgState.page = 1; loadMsgChats(); });
      $('msg-search-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') { msgState.search = e.target.value.trim(); msgState.page = 1; loadMsgChats(); } });
      $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((el) => el.addEventListener('click', () => { $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x === el)); msgState.sendType = el.dataset.msgType; renderMsgExtra(); }));
      $('msg-send-mode').addEventListener('change', (e) => { msgState.sendMode = e.target.value; $('msg-custom-id').hidden = !(msgState.sendMode === 'custom_msg_id' || msgState.sendMode === 'custom_event_id'); });
      $('msg-send').addEventListener('click', sendMessage);
      $('msg-textarea').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing && e.keyCode !== 229) {
          e.preventDefault();
          sendMessage();
        }
      });
      $('msg-textarea').addEventListener('paste', (e) => {
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (const item of items) {
          if (item.type && item.type.indexOf('image/') === 0) {
            const file = item.getAsFile();
            if (!file) continue;
            const reader = new FileReader();
            reader.onload = () => {
              msgState.pastedImage = reader.result;
              $('msg-img-thumb').src = reader.result;
              $('msg-img-preview').hidden = false;
              toast('已粘贴图片，可继续输入文字后发送');
            };
            reader.readAsDataURL(file);
            e.preventDefault();
            return;
          }
        }
      });
      $('msg-img-clear').addEventListener('click', () => { msgState.pastedImage = null; $('msg-img-preview').hidden = true; $('msg-img-thumb').removeAttribute('src'); });
      $('msg-reload').addEventListener('click', () => { loadMsgChats(); if (msgState.chatId) loadMsgHistory(); });
      $('msg-multi-recall').addEventListener('click', recallSelected);
      $('msg-multi-cancel').addEventListener('click', () => { exitMultiMode(); });
      $('msg-refresh-info').addEventListener('click', refreshGroupInfo);
      $('msg-remark').addEventListener('click', showRemarkDialog);
      $('msg-quote-clear').addEventListener('click', () => { msgState.quote = null; $('msg-quote-preview').hidden = true; });
      $('msg-raw-close').addEventListener('click', () => { $('msg-raw-modal').hidden = true; });
      $('msg-raw-modal').addEventListener('click', (e) => { if (e.target === $('msg-raw-modal')) $('msg-raw-modal').hidden = true; });
      $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((el) => el.addEventListener('click', () => { $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((x) => x.classList.toggle('active', x === el)); msgState.muteMinutes = Number(el.dataset.muteMin); $('msg-mute-custom').value = ''; }));
      $('msg-mute-custom').addEventListener('input', (e) => { const v = Number(e.target.value); if (v >= 1) msgState.muteMinutes = v; });
      $('msg-mute-cancel').addEventListener('click', () => { $('msg-mute-modal').hidden = true; });
      $('msg-remark-cancel').addEventListener('click', () => { $('msg-remark-modal').hidden = true; });
      $('msg-remark-save').addEventListener('click', saveRemark);
      $('msg-remark-delete').addEventListener('click', deleteRemark);
      $('msg-mute-confirm').addEventListener('click', async () => { if (!msgState.mute.member) return; try { await api('message/group-member/mute', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, member_openid:msgState.mute.member, minutes:msgState.muteMinutes})}); toast('禁言成功'); $('msg-mute-modal').hidden = true; } catch (error) { toast(error.message); } });
      msgState.timer = setInterval(() => { const active = !document.querySelector('#page-messages')?.hidden; if (active) { loadMsgChats(); if (msgState.chatId) loadMsgHistory(false, true); } }, 10000);

      setView(viewFromUrl(), false); load();
    })();
  </script>
</body>
</html>
"""


def _渲染登录页面() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f7f8fd">
  <title>馒头助手</title>
  <style>
    :root { color-scheme:light; --ink:#292741; --muted:#7d8096; --line:#e8e9f2; --bg:#f7f8fd; --panel:#fff; --primary:#6b63f5; --primary-dark:#574eea; --primary-soft:#f0efff; --mint:#e9fbf3; --mint-ink:#319e6b; }
    * { box-sizing:border-box; }
    html,body { min-height:100%; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.55 Inter,"PingFang SC","Microsoft YaHei",ui-sans-serif,system-ui,sans-serif; }
    button,input { font:inherit; }
    button { cursor:pointer; }
    .login-page { min-height:100vh; display:grid; place-items:center; padding:24px; }
    .login-shell { width:min(850px,100%); display:grid; grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr); overflow:hidden; border:1px solid var(--line); border-radius:18px; background:var(--panel); box-shadow:0 18px 48px rgba(60,57,112,.08); animation:login-rise .42s cubic-bezier(.22,.8,.35,1) both; }
    .login-welcome { display:flex; flex-direction:column; justify-content:center; min-height:510px; padding:54px 50px; background:#fbfaff; border-right:1px solid var(--line); }
    .login-brand { display:flex; align-items:center; gap:11px; }
    .login-brand-mark { width:38px; height:38px; display:grid; place-items:center; border:3px solid #f5f4ff; border-radius:50%; background:#e9e9ff; color:#5d58d8; font-size:14px; font-weight:800; }
    .login-brand strong { display:block; font-size:16px; }
    .login-brand small { display:block; margin-top:1px; color:var(--muted); font-size:11px; }
    .login-illustration { position:relative; width:176px; height:176px; display:grid; place-items:center; margin:42px auto 27px; }
    .login-illustration::before { content:""; position:absolute; inset:13px; border:1px solid #e6e4ff; border-radius:50%; }
    .login-avatar { position:relative; width:112px; height:112px; overflow:hidden; border:7px solid #f0efff; border-radius:50%; background:#e9eaff; box-shadow:0 10px 22px rgba(92,87,210,.14); animation:login-float 3.4s ease-in-out infinite; }
    .login-avatar::before { content:""; position:absolute; width:96px; height:91px; left:0; top:7px; border-radius:50% 50% 43% 43%; background:#a2a5f7; }
    .login-avatar::after { content:"✦"; position:absolute; right:9px; top:5px; color:#fff; font-size:17px; }
    .login-avatar-face { position:absolute; left:22px; top:43px; z-index:1; color:#4f50a8; font-size:30px; letter-spacing:7px; }
    .login-star { position:absolute; color:#b4b0ff; font-size:18px; animation:login-twinkle 2.4s ease-in-out infinite; }
    .login-star.one { left:13px; top:34px; }
    .login-star.two { right:12px; bottom:31px; animation-delay:.8s; }
    .login-welcome h1 { margin:0; text-align:center; font-size:25px; letter-spacing:.2px; }
    .login-welcome p { max-width:290px; margin:8px auto 0; color:var(--muted); font-size:12px; line-height:1.8; text-align:center; }
    .login-panel { display:flex; flex-direction:column; justify-content:center; padding:54px 50px; }
    .login-panel h2 { margin:0; font-size:20px; }
    .login-panel > p { margin:7px 0 25px; color:var(--muted); font-size:12px; }
    .login-form { display:grid; gap:15px; }
    .login-form label { display:grid; gap:6px; color:#5f5d72; font-size:12px; font-weight:700; }
    .login-form input { width:100%; min-height:43px; padding:9px 12px; border:1px solid #dddceb; border-radius:8px; background:#fff; color:var(--ink); outline:none; transition:border-color .18s ease,box-shadow .18s ease; }
    .login-form input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
    .login-button { display:flex; align-items:center; justify-content:center; gap:8px; min-height:43px; margin-top:5px; border:0; border-radius:8px; background:var(--primary); color:#fff; font-size:13px; font-weight:750; box-shadow:0 7px 17px rgba(107,99,245,.2); transition:background .18s ease,transform .18s ease; }
    .login-button:hover { background:var(--primary-dark); transform:translateY(-1px); }
    .login-button:disabled { cursor:wait; opacity:.65; transform:none; }
    .login-message { min-height:20px; margin:16px 0 0; color:#c06478; font-size:12px; line-height:1.6; }
    .login-message:empty { margin-top:8px; }
    .login-note { display:flex; align-items:center; gap:6px; margin-top:28px; color:#9b9db0; font-size:11px; }
    .login-note::before { content:""; width:7px; height:7px; border-radius:50%; background:#4dbb82; box-shadow:0 0 0 4px var(--mint); }
    @keyframes login-rise { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
    @keyframes login-float { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-5px); } }
    @keyframes login-twinkle { 0%,100% { opacity:.45; transform:scale(.9); } 50% { opacity:1; transform:scale(1.08); } }
    @media (max-width:680px) { .login-page { padding:15px; } .login-shell { grid-template-columns:1fr; max-width:430px; } .login-welcome { min-height:0; padding:31px 26px 27px; border-right:0; border-bottom:1px solid var(--line); } .login-illustration { width:130px; height:130px; margin:24px auto 18px; } .login-illustration::before { inset:8px; } .login-avatar { width:82px; height:82px; border-width:5px; } .login-avatar::before { width:72px; height:69px; top:4px; } .login-avatar-face { left:16px; top:31px; font-size:22px; letter-spacing:4px; } .login-avatar::after { right:5px; top:2px; font-size:12px; } .login-star { font-size:14px; } .login-welcome h1 { font-size:21px; } .login-panel { padding:31px 26px 34px; } }
    @media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; transition-duration:.01ms !important; } }
  </style>
</head>
<body class="login-page">
  <main class="login-shell">
    <section class="login-welcome" aria-labelledby="login-title">
      <div class="login-brand"><span class="login-brand-mark">馒</span><div><strong>馒头助手</strong><small>QQ 机器人</small></div></div>
      <div class="login-illustration" aria-hidden="true"><span class="login-star one">✦</span><div class="login-avatar"><span class="login-avatar-face">•ᴗ•</span></div><span class="login-star two">✦</span></div>
      <h1 id="login-title">欢迎回来</h1>
      <p>验证管理身份后继续使用馒头助手。</p>
    </section>
    <section class="login-panel" aria-labelledby="login-heading">
      <h2 id="login-heading">身份验证</h2>
      <p>请输入登录信息。</p>
      <form id="login-form" class="login-form">
        <label for="login-username">账号<input id="login-username" name="username" autocomplete="username" required></label>
        <label for="login-password">密码<input id="login-password" name="password" type="password" autocomplete="current-password" required></label>
        <button class="login-button" type="submit"><span>进入</span><span aria-hidden="true">→</span></button>
      </form>
      <p id="login-message" class="login-message" role="alert" aria-live="polite"></p>
      <div class="login-note">登录状态仅保存在当前浏览器会话中</div>
    </section>
  </main>
  <script>
    (() => {
      const form = document.getElementById('login-form');
      const username = document.getElementById('login-username');
      const password = document.getElementById('login-password');
      const button = form.querySelector('button[type="submit"]');
      const message = document.getElementById('login-message');
      const setMessage = (value) => { message.textContent = value; };
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        button.disabled = true;
        setMessage('');
        try {
          const response = await fetch('/api/login', { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:username.value.trim(), password:password.value}) });
          const data = await response.json().catch(() => ({ok:false}));
          if (!response.ok || !data.ok) { const error = new Error(); error.status = response.status; throw error; }
          password.value = '';
          location.replace(location.pathname + '?view=dashboard');
        } catch (error) {
          setMessage(error.status === 401 ? '账号或密码不正确。' : error.status === 503 ? '登录服务暂未启用，请联系管理员。' : '暂时无法登录，请稍后再试。');
        } finally {
          button.disabled = false;
        }
      });
      username.focus();
    })();
  </script>
</body>
</html>
"""


async def _处理帮助网页(request: web.Request) -> web.Response:
    页面 = _渲染控制台页面() if _请求已授权(request) else _渲染登录页面()
    return web.Response(
        text=页面,
        content_type="text/html",
        charset="utf-8",
        headers={"Cache-Control": "no-store"},
    )


async def 启动帮助网页服务(配置: Any = None) -> 帮助网页服务 | None:
    global 当前帮助网页服务, 网页服务启动状态, 当前帮助网页配置
    await 停止帮助网页服务(当前帮助网页服务)
    当前帮助网页服务 = None
    网页服务启动状态 = False
    当前帮助网页配置 = 配置
    控制台会话.clear()
    控制台会话身份.clear()

    基础地址 = _计算帮助网页地址(配置)
    public_url = _构造控制台访问地址(基础地址, 配置)
    host, port = _读取监听配置(配置)
    app = web.Application()
    app.router.add_get("/", _处理帮助网页)
    app.router.add_post("/api/login", _处理控制台登录)
    app.router.add_post("/api/logout", _处理控制台退出)
    app.router.add_get("/api/dashboard", _处理控制台数据)
    app.router.add_post("/api/novel-switch", _处理小说开关)
    app.router.add_post("/api/pan-switch", _处理网盘切换)
    app.router.add_get("/api/config", _处理插件配置数据)
    app.router.add_post("/api/config", _处理插件配置写入)
    app.router.add_get("/api/pan-accounts/{platform}", _处理网盘账号列表)
    app.router.add_post("/api/pan-accounts/{platform}", _处理网盘账号新增)
    app.router.add_delete("/api/pan-accounts/{platform}", _处理网盘账号删除)
    app.router.add_post("/api/pan-account-selection", _处理网盘账号选择)
    app.router.add_get("/api/qq-reader-auth", _处理QQ阅读登录态)
    app.router.add_post("/api/qq-reader-auth", _处理QQ阅读登录态保存)
    app.router.add_delete("/api/qq-reader-auth", _处理QQ阅读登录态删除)
    app.router.add_post("/api/message/chats", _处理消息聊天列表)
    app.router.add_post("/api/message/history", _处理消息历史)
    app.router.add_post("/api/message/send", _处理消息发送)
    app.router.add_post("/api/message/recall", _处理消息撤回)
    app.router.add_post("/api/message/group-member/mute", _处理消息禁言)
    app.router.add_post("/api/message/group-roles", _处理群角色)
    app.router.add_post("/api/message/remarks", _处理群备注)
    app.router.add_post("/api/message/group-info/refresh", _处理群信息刷新)
    app.router.add_get("/{tail:.*}", _处理帮助网页)
    runner = web.AppRunner(app, access_log=None)
    try:
        await runner.setup()
        await web.TCPSite(runner, host, port).start()
    except Exception as exc:
        await runner.cleanup()
        logger.warning("帮助控制台启动失败：错误类型=%s", type(exc).__name__)
        return None

    当前帮助网页服务 = 帮助网页服务(runner, public_url, host, port)
    网页服务启动状态 = True
    logger.info(
        "帮助控制台已启动：监听地址=%s, 监听端口=%s, 访问地址=%s",
        host,
        port,
        基础地址,
    )
    return 当前帮助网页服务


async def 停止帮助网页服务(服务: 帮助网页服务 | None) -> None:
    global 当前帮助网页服务, 网页服务启动状态, 当前帮助网页配置
    if 服务 is None:
        return
    try:
        await 服务.runner.cleanup()
    except Exception as exc:
        logger.warning("帮助控制台停止失败：错误类型=%s", type(exc).__name__)
    finally:
        if 当前帮助网页服务 is 服务:
            当前帮助网页服务 = None
            网页服务启动状态 = None
            当前帮助网页配置 = None
            控制台会话.clear()
            控制台会话身份.clear()
