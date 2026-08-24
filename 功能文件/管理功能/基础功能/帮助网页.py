from __future__ import annotations

import asyncio
import hmac
import ipaddress
import logging
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
控制台版本 = "5.41.1"
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
    控制台会话.pop(_取得请求会话(request), None)
    响应 = web.json_response({"ok": True})
    响应.del_cookie(控制台会话Cookie名, path="/")
    return 响应


def _读取控制台数据() -> dict[str, Any]:
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
            }
        )

    host, port = _读取监听配置(配置)
    return {
        "ok": True,
        "version": 控制台版本,
        "updated_at": int(time.time()),
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
        },
    }


async def _处理控制台数据(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "请先登录控制台")
    try:
        数据 = await asyncio.to_thread(_读取控制台数据)
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
    .shell { min-height:100vh; display:grid; grid-template-columns:224px minmax(0,1fr); grid-template-rows:64px minmax(0,1fr); grid-template-areas:"top top" "side main"; }
    .topbar { grid-area:top; display:flex; align-items:center; justify-content:space-between; gap:20px; padding:0 30px; background:#fff; border-bottom:1px solid var(--line); }
    .brand { display:flex; align-items:center; gap:10px; min-width:0; }
    .brand-mark { width:34px; height:34px; display:grid; place-items:center; border-radius:11px; background:var(--primary-soft); color:var(--primary); font-size:16px; font-weight:800; }
    .brand strong { font-size:16px; letter-spacing:.1px; }
    .version-badge { display:inline-flex; margin-left:7px; padding:3px 8px; border-radius:999px; background:#f3f3f8; color:var(--muted); font-size:11px; font-weight:650; }
    .top-actions { display:flex; align-items:center; gap:16px; }
    .status-dot { display:inline-flex; align-items:center; gap:7px; color:var(--mint-ink); font-size:12px; font-weight:650; }
    .status-dot::before { content:""; width:7px; height:7px; border-radius:50%; background:#4dbb82; box-shadow:0 0 0 4px var(--mint); }
    .admin-chip { display:flex; align-items:center; gap:8px; color:var(--ink); font-size:13px; font-weight:650; }
    .admin-avatar { width:28px; height:28px; display:grid; place-items:center; border-radius:50%; background:#f0efff; color:var(--primary); font-size:12px; font-weight:800; }
    .admin-chevron { color:var(--soft); font-size:13px; }
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
    .content { width:min(1180px,calc(100% - 70px)); margin:0 auto; padding:34px 0 60px; }
    .page-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; }
    .page-kicker { margin:0 0 4px; color:var(--primary); font-size:12px; font-weight:750; }
    .page-heading h1 { margin:0; font-size:25px; letter-spacing:-.2px; }
    .page-heading p { margin:5px 0 0; color:var(--muted); font-size:13px; }
    .page-tabs { display:flex; gap:26px; margin-top:25px; padding:0 2px; border-bottom:1px solid var(--line); }
    .page-tabs span { position:relative; padding:0 0 12px; color:#65687b; font-size:13px; cursor:default; user-select:none; }
    .page-tabs span.active { color:var(--primary-dark); font-weight:700; }
    .page-tabs span.active::after { content:""; position:absolute; left:0; right:0; bottom:-1px; height:2px; border-radius:2px; background:var(--primary); }
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
     @media (max-width:760px) { .shell { display:block; } .topbar { min-height:62px; padding:12px 15px; } .brand strong { font-size:14px; } .top-actions { gap:8px; } .admin-chip { font-size:12px; } .status-dot { display:none; } .sidebar { padding:10px 12px 8px; border-right:0; border-bottom:1px solid var(--line); gap:10px; } .profile { display:flex; align-items:center; justify-content:flex-start; gap:9px; padding:0 2px; } .bot-avatar { width:38px; height:38px; border-width:3px; } .bot-avatar::before { width:34px; height:32px; top:2px; } .avatar-face { left:8px; top:12px; font-size:12px; letter-spacing:2px; } .bot-avatar::after { right:2px; top:1px; font-size:8px; } .profile strong { font-size:13px; } .online { margin-left:-3px; } .nav-label,.sidebar-foot { display:none; } .nav { display:flex; gap:4px; overflow-x:auto; scrollbar-width:none; } .nav::-webkit-scrollbar { display:none; } .nav a { flex:0 0 auto; padding:8px 10px; } .content { width:calc(100% - 28px); padding:23px 0 40px; } .page-heading h1 { font-size:21px; } .page-heading p { font-size:12px; } .primary-button { min-height:34px; padding:0 11px; } .page-tabs { gap:20px; margin-top:20px; overflow-x:auto; scrollbar-width:none; } .page-tabs::-webkit-scrollbar { display:none; } .page-tabs span { flex:0 0 auto; } .metrics,.pan-grid { grid-template-columns:1fr; } .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .novel-item:nth-child(3n) { border-right:1px solid var(--line); } .novel-item:nth-child(2n) { border-right:0; } .novel-item:nth-last-child(-n+3),.novel-item:last-child,.novel-item:nth-last-child(2) { border-bottom:1px solid var(--line); } .global-bar { align-items:flex-start; } .global-actions { gap:10px; } .test-mode span { max-width:68px; white-space:normal; line-height:1.2; } .runtime-grid { grid-template-columns:repeat(2,1fr); } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { padding:13px; border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
     /* Screenshot-inspired configuration workspace. The data/API contract stays unchanged. */
     .shell { grid-template-columns:222px minmax(0,1fr); grid-template-rows:62px minmax(0,1fr); }
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
     .content { width:min(1040px,calc(100% - 64px)); padding:38px 0 65px; }
     .page-kicker { display:none; }
     .page-heading h1 { font-size:24px; letter-spacing:0; }
     .page-heading p { margin-top:6px; font-size:13px; }
     .primary-button { min-height:40px; border-radius:7px; padding:0 17px; }
     .page-tabs { gap:0; margin-top:26px; padding:0 7px; border:1px solid var(--line); border-radius:8px; background:#fff; box-shadow:0 4px 14px rgba(58,60,104,.035); }
     .page-tabs span { padding:15px 18px 13px; font-size:13px; }
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
     .pan-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
     .runtime-grid { display:none; }
     .config-list { grid-template-columns:repeat(2,minmax(0,1fr)); border-radius:7px; box-shadow:none; }
     .config-item { min-height:64px; padding:13px 15px; border-bottom:1px solid var(--line); }
     .config-item:nth-child(2n) { border-right:0; }
     .config-item:nth-last-child(-n+2) { border-bottom:0; }
     .config-section { margin-top:16px; }
     .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
     @media (max-width:1050px) { .workspace-grid { grid-template-columns:minmax(0,1.35fr) minmax(280px,.9fr); } .pan-grid { grid-template-columns:1fr; } }
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
      @media (prefers-reduced-motion: reduce) {
        *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:.01ms !important; }
      }
      @media (max-width:760px) { .heading-actions { gap:7px; } .updated-label { display:none; } .summary-grid,.page-grid,.runtime-detail,.help-grid { grid-template-columns:1fr; } .shortcut-grid { grid-template-columns:1fr; } .runtime-page-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .standalone-card { margin-top:15px; } .safe-list > div,.settings-row { min-height:56px; } }
   </style>
</head>
"""

_网页主体 = """
<body>
  <div class="shell">
    <header class="topbar">
        <div class="brand"><div class="brand-mark">馒</div><div><strong>QQ机器人后台</strong><span class="version-badge" id="console-version">v5.41.1</span></div></div>
      <div class="top-actions"><span class="status-dot">服务在线</span><div class="admin-chip"><span class="admin-avatar">管</span><span>管理员</span><span class="admin-chevron">⌄</span></div></div>
    </header>
    <aside class="sidebar">
      <div class="profile"><div class="bot-avatar"><span class="avatar-face">•ᴗ•</span></div><strong>馒头助手</strong><span class="online">在线</span></div>
      <div><div class="nav-label">工作台</div><nav class="nav" aria-label="控制台导航">
        <a href="?view=dashboard" data-view="dashboard"><span class="nav-icon">⌂</span>控制台</a>
        <a href="?view=bot" data-view="bot"><span class="nav-icon">⚙</span>机器人配置</a>
        <a href="?view=novels" data-view="novels"><span class="nav-icon">☷</span>小说功能</a>
        <a href="?view=pans" data-view="pans"><span class="nav-icon">▣</span>网盘配置</a>
        <a href="?view=runtime" data-view="runtime"><span class="nav-icon">◒</span>运行状态</a>
        <a href="?view=help" data-view="help"><span class="nav-icon">?</span>帮助指令</a>
        <a href="?view=settings" data-view="settings"><span class="nav-icon">⚙</span>系统设置</a>
      </nav></div>
      <div class="sidebar-foot"><span class="spark">✦</span><strong>只显示真实功能</strong><span>未接入后端的数据入口不会伪装成可用按钮。</span></div>
    </aside>
    <main class="main">
      <div class="content">
        <div class="page-heading"><div><p id="page-eyebrow" class="page-kicker">馒头Bot / 管理台</p><h1 id="page-title">控制台</h1><p id="page-subtitle">查看机器人和小说服务的实时状态</p></div><div class="heading-actions"><span id="updated" class="updated-label">--</span><button class="outline-button" id="logout" type="button" hidden>退出登录</button><button class="primary-button" id="refresh" type="button"><span class="button-icon">↻</span>刷新状态</button></div></div>
        <nav class="page-tabs" aria-label="当前页面分区"><span class="page-tab" data-tab="bot">基本信息</span><span class="page-tab" data-tab="novels">小说功能</span><span class="page-tab" data-tab="pans">网盘配置</span><span class="page-tab" data-tab="runtime">运行状态</span><span class="page-tab" data-tab="settings">系统设置</span></nav>
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
          <div class="workspace-grid"><div class="workspace-left"><article id="overview" class="console-card"><h2>基本信息</h2><p class="card-subtitle">当前插件的安全摘要和运行身份</p><div class="profile-fields"><div class="profile-field"><span>机器人名称</span><div class="readonly-value"><strong>馒头助手</strong><small>管理台</small></div></div><div class="profile-field"><span>机器人 QQ 号</span><div class="readonly-value"><strong>由适配器提供</strong><small>页面不读取账号信息</small></div></div><div class="profile-field"><span>机器人头像</span><div class="avatar-inline"><div class="bot-avatar"><span class="avatar-face">•ᴗ•</span></div><small>馒头Bot 二次元助手</small></div></div><div class="profile-field"><span>机器人简介</span><div class="readonly-value"><strong>小说下载、网盘分享与群聊管理</strong></div></div><div class="profile-field"><span>运行状态</span><div class="state-line"><span class="online">在线运行</span></div></div></div></article><article id="config" class="console-card"><h2>连接配置</h2><p class="card-subtitle">网页监听和数据持久化状态</p><div id="config-list" class="panel config-list"><div class="empty">正在读取配置...</div></div></article></div><div class="workspace-right"><article class="console-card"><h2>安全说明</h2><p class="card-subtitle">页面只展示后端允许的摘要。</p><div class="safe-list"><div><span>登录凭据</span><strong>不返回原文</strong></div><div><span>数据库地址</span><strong>不返回</strong></div><div><span>会话 Cookie</span><strong>仅 HttpOnly 保存</strong></div><div><span>写入方式</span><strong>仅调用已授权接口</strong></div></div></article></div></div>
        </section>

        <section id="page-novels" class="page-view" data-page="novels" hidden><article id="novels" class="console-card module-card standalone-card"><h2>小说功能</h2><p class="card-subtitle">这里的开关会写入运行状态数据库，关闭后对应平台不会进入下载流程。</p><div class="global-bar"><div class="global-copy"><strong>全部小说功能</strong><span>控制下载、找书和翻页总入口</span></div><button id="global-switch" class="switch" type="button" aria-label="切换全局小说功能"><span></span></button></div><div class="test-mode global-bar"><div class="global-copy"><strong>管理员测试模式</strong><span>仅管理员可用，不改变普通用户的关闭限制</span></div><button id="test-switch" class="switch" type="button" aria-label="切换管理员测试模式"><span></span></button></div><div class="module-heading"><h3>平台开关</h3><span>逐个平台控制</span></div><div id="novel-grid" class="novel-grid"><div class="empty">正在读取小说平台...</div></div></article></section>

        <section id="page-pans" class="page-view" data-page="pans" hidden><article id="pans" class="console-card standalone-card"><h2>网盘配置</h2><p class="card-subtitle">主分享网盘会用于所有小说完成消息。切换后立即保存。</p><div class="pan-note"><span>当前主分享网盘</span><strong id="pan-active-label">--</strong></div><div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态...</div></div></article></section>

        <section id="page-runtime" class="page-view" data-page="runtime" hidden><article class="console-card standalone-card"><h2>运行状态</h2><p class="card-subtitle">这些数据来自服务器当前运行状态。</p><div class="runtime-grid runtime-page-grid"><div class="runtime-item"><span>CPU占用</span><strong id="runtime-cpu">--</strong></div><div class="runtime-item"><span>物理内存</span><strong id="runtime-memory">--</strong></div><div class="runtime-item"><span>磁盘空间</span><strong id="runtime-disk">--</strong></div><div class="runtime-item"><span>系统运行时间</span><strong id="runtime-runtime">--</strong></div><div class="runtime-item"><span>操作系统</span><strong id="runtime-os">--</strong></div></div><div class="runtime-detail"><div class="status-item"><span>数据库</span><strong id="runtime-db">--</strong></div><div class="status-item"><span>当前网盘</span><strong id="runtime-pan">--</strong></div><div class="status-item"><span>插件版本</span><strong id="runtime-version">--</strong></div></div></article></section>

        <section id="page-help" class="page-view" data-page="help" hidden><div class="section-head page-view-head"><div><h2>帮助指令</h2><p>这里列出机器人当前支持的聊天指令；网页不代替群聊执行指令。</p></div></div><div class="help-grid"><article class="console-card help-card"><h3>管理与状态</h3><p>需要管理员权限的指令。</p><div class="command-list"><span>帮助</span><span>状态</span><span>小说</span><span>开小说 / 关小说</span><span>开测试 / 关测试</span><span>网盘状态</span><span>换UC / 换夸克 / 换百度</span><span>夸克登录</span></div></article><article class="console-card help-card"><h3>小说入口</h3><p>在群聊或私聊发送链接即可识别。</p><div class="command-list"><span>找关键词</span><span>找书 关键词</span><span>找作者 关键词</span><span>上一页 / 下一页</span><span>小说平台分享链接</span><span>小说分享卡片</span></div></article><article class="console-card help-card"><h3>群聊管理</h3><p>由插件管理员和群身份规则共同决定。</p><div class="command-list"><span>禁言 @成员</span><span>禁 @成员 1</span><span>解 @成员</span><span>数字撤回</span><span>卡片撤回</span><span>合并转发撤回</span></div></article></div></section>
        <section id="page-settings" class="page-view" data-page="settings" hidden><article id="settings" class="console-card standalone-card"><h2>系统设置</h2><p class="card-subtitle">当前网页服务的监听和访问策略。配置修改请在 AstrBot 插件配置中完成。</p><div id="settings-list" class="settings-list"><div class="empty">正在读取设置...</div></div></article></section>
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
        settings: ['系统设置', '查看网页服务设置；修改请回到 AstrBot 配置'],
      };
      let snapshot = null;
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
        document.querySelectorAll('.page-tabs [data-tab]').forEach((node) => node.classList.toggle('active', node.dataset.tab === next));
        if (next === 'dashboard') $('page-eyebrow').textContent = '馒头Bot / 管理台'; else $('page-eyebrow').textContent = '馒头Bot / 功能页面';
        window.scrollTo({top:0, behavior:'auto'});
      };
      const switchHtml = (key, enabled, editable, label) => `<button class="switch ${enabled ? 'on' : ''}" data-switch="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(label)}" aria-pressed="${enabled}"><span></span></button>`;
      const render = (data) => {
        snapshot = data;
        const novels = data.novels || {}; const pans = data.pans || {}; const server = data.server || {}; const database = data.database || {};
        $('metric-global').textContent = novels.global_enabled ? '已开启' : '已关闭'; $('metric-global-meta').textContent = novels.test_mode ? '测试模式已开启' : '测试模式未开启';
        $('metric-pan').textContent = pans.active || '--'; const activePan = (pans.items || []).find((item) => item.active); $('metric-pan-meta').textContent = activePan ? `${activePan.accounts} 个账号 · ${activePan.configured ? '已配置' : '未配置'}` : '未选择';
        $('metric-db').textContent = database.status || '--'; $('metric-db-meta').textContent = database.configured ? '状态可持久化' : '未配置数据库'; $('metric-version').textContent = `v${data.version || '--'}`; $('console-version').textContent = `v${data.version || '--'}`;
        $('dashboard-cpu').textContent = server.cpu || '--'; $('dashboard-memory').textContent = server.memory || '--'; $('dashboard-runtime').textContent = server.runtime || '--'; $('dashboard-updated').textContent = '刚刚';
        [['global-switch', '__global__', novels.global_enabled, '切换全局小说功能'], ['test-switch', '__test__', novels.test_mode, '切换管理员测试模式']].forEach(([id, key, enabled, label]) => { const node = $(id); node.className = `switch ${enabled ? 'on' : ''}`; node.dataset.switch = key; node.dataset.enabled = String(Boolean(enabled)); node.disabled = !novels.editable; node.setAttribute('aria-label', label); node.setAttribute('aria-pressed', String(Boolean(enabled))); });
        $('novel-grid').innerHTML = (novels.platforms || []).map((item) => `<div class="novel-item"><div class="novel-name"><div class="novel-badge">书</div><div><strong>${esc(item.name)}</strong><small>${item.enabled ? '当前可用' : '已停用'}</small></div></div>${switchHtml(item.key, item.enabled, novels.editable, `切换${item.name}`)}</div>`).join('') || '<div class="empty">没有可用小说平台</div>';
        $('pan-active-label').textContent = pans.active || '--';
        $('pan-grid').innerHTML = (pans.items || []).map((item) => { const accounts = (item.account_summary || []).map((account) => `<div class="account-row"><strong>账号${esc(account.index)}</strong><span>${esc(account.name)} · ${esc(account.phone)}</span></div>`).join(''); return `<article class="pan-card ${item.active ? 'active' : ''}"><div class="pan-top"><div class="pan-title"><div class="pan-logo">${esc(item.key.slice(0,1))}</div><strong>${esc(item.name)}</strong></div><div>${item.active ? '<span class="tag active">当前主网盘</span>' : ''}</div></div><div class="pan-meta"><div><span>配置状态</span><strong>${item.configured ? '<span class="tag ok">已配置</span>' : '<span class="tag off">未配置</span>'}</strong></div><div><span>账号数量</span><strong>${esc(item.accounts)} 个</strong></div><div><span>上传目录</span><strong title="${esc(item.directory)}">${esc(item.directory || '默认目录')}</strong></div><div><span>账号策略</span><strong>按群独立选择</strong></div></div>${accounts ? `<div class="account-list">${accounts}</div>` : ''}<select class="pan-select" data-pan="${esc(item.key)}" ${pans.editable ? '' : 'disabled'} aria-label="选择${esc(item.name)}"><option value="">${item.active ? '当前使用中' : '设为主分享网盘'}</option><option value="${esc(item.key)}">切换到${esc(item.name)}</option></select></article>`; }).join('') || '<div class="empty">没有网盘数据</div>';
        $('runtime-cpu').textContent = server.cpu || '--'; $('runtime-memory').textContent = server.memory || '--'; $('runtime-disk').textContent = server.disk || '--'; $('runtime-runtime').textContent = server.runtime || '--'; $('runtime-os').textContent = server.os || '--'; $('runtime-db').textContent = database.status || '--'; $('runtime-pan').textContent = pans.active || '--'; $('runtime-version').textContent = `v${data.version || '--'}`;
        $('config-list').innerHTML = `<div class="config-item"><span>监听地址</span><strong>${esc(server.listen || '--')}</strong></div><div class="config-item"><span>访问地址</span><strong title="${esc(server.address)}">${esc(server.address || '--')}</strong></div><div class="config-item"><span>域名模式</span><strong>${data.config && data.config.custom_domain ? '自定义域名' : '自动服务器 IP'}</strong></div><div class="config-item"><span>登录方式</span><strong>${esc(data.config && data.config.auth_mode || '账号密码会话')}</strong></div>`;
        $('settings-list').innerHTML = `<div class="settings-row"><span>监听主机</span><strong>${esc(data.config && data.config.help_web_host || '--')}</strong></div><div class="settings-row"><span>监听端口</span><strong>${esc(data.config && data.config.help_web_port || '--')}</strong></div><div class="settings-row"><span>公开访问地址</span><strong>${esc(server.address || '--')}</strong></div><div class="settings-row"><span>登录方式</span><strong>${esc(data.config && data.config.auth_mode || '--')}</strong></div><div class="settings-hint">账号和密码请在 AstrBot 插件配置的“帮助网页设置”中修改，保存后重载插件；网页不会返回密码原文。</div>`;
        $('updated').textContent = '刚刚更新';
        document.querySelectorAll('[data-switch]').forEach((node) => node.addEventListener('click', () => changeNovel(node)));
        document.querySelectorAll('[data-pan]').forEach((node) => node.addEventListener('change', () => { const value = node.value; node.value = ''; if (value) changePan(value, node); }));
      };
      const showAuthError = (error) => { if (error.status === 401) { location.reload(); return; } $('logout').hidden = true; $('refresh').hidden = true; showNotice(error.status === 503 ? '登录服务尚未启用，请联系管理员。' : '控制台数据暂时不可用，请稍后重试。'); };
      const changeNovel = async (node) => { if (!snapshot || !snapshot.novels.editable) return toast('数据库未配置，开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { await api('novel-switch', {method:'POST', body:JSON.stringify({key:node.dataset.switch, enabled})}); toast('小说开关已更新'); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const changePan = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘选择不能保存'); if (node) node.disabled = true; try { await api('pan-switch', {method:'POST', body:JSON.stringify({key})}); toast('主分享网盘已更新'); await load(); } catch (error) { if (node) node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const load = async () => { try { render(await api('dashboard')); $('logout').hidden = false; $('refresh').hidden = false; setView(viewFromUrl(), false); } catch (error) { showAuthError(error); } };
      $('logout').addEventListener('click', async () => { try { await api('logout', {method:'POST'}); } finally { location.reload(); } });
      document.querySelectorAll('.sidebar [data-view]').forEach((node) => node.addEventListener('click', (event) => { event.preventDefault(); setView(node.dataset.view); }));
      window.addEventListener('popstate', () => setView(viewFromUrl(), false));
      $('refresh').addEventListener('click', load); setView(viewFromUrl(), false); load();
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
