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
from urllib.parse import quote, urlsplit, urlunsplit

from aiohttp import web

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)

默认监听地址 = "0.0.0.0"
默认监听端口 = 8090
控制台版本 = "5.39.0"


@dataclass
class 帮助网页服务:
    runner: web.AppRunner
    public_url: str
    host: str
    port: int


# importlib.reload 会复用原模块字典；保留旧引用，确保重载时可以清理旧端口和令牌。
当前帮助网页服务: 帮助网页服务 | None = globals().get("当前帮助网页服务")
自动公开地址缓存: str | None = globals().get("自动公开地址缓存")
网页服务启动状态: bool | None = globals().get("网页服务启动状态")
当前帮助网页配置: Any = globals().get("当前帮助网页配置")
控制台访问令牌: str = globals().get("控制台访问令牌") or secrets.token_urlsafe(24)


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


def _读取控制台令牌(配置: Any = None) -> str:
    配置令牌 = str(_读取帮助网页字段(配置, "help_web_admin_token") or "").strip()
    return 配置令牌 or 控制台访问令牌


def _构造控制台访问地址(基础地址: str, 配置: Any = None) -> str:
    if not 基础地址:
        return ""
    令牌 = _读取控制台令牌(配置)
    try:
        parsed = urlsplit(基础地址)
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                f"token={quote(令牌, safe='')}",
                "",
            )
        )
    except ValueError:
        return 基础地址


def 获取帮助网页地址(配置: Any = None) -> str:
    """返回带控制台令牌的访问地址；服务启动失败时不暴露失效链接。"""
    if 当前帮助网页服务 is not None:
        return 当前帮助网页服务.public_url
    if 网页服务启动状态 is False:
        return ""
    return _构造控制台访问地址(_计算帮助网页地址(配置), 配置)


def _取得请求令牌(request: web.Request) -> str:
    令牌 = str(request.query.get("token") or "").strip()
    if 令牌:
        return 令牌
    令牌 = str(request.headers.get("X-Mantou-Token") or "").strip()
    if 令牌:
        return 令牌
    授权 = str(request.headers.get("Authorization") or "")
    return 授权[7:].strip() if 授权.lower().startswith("bearer ") else ""


def _请求已授权(request: web.Request) -> bool:
    期望令牌 = _读取控制台令牌(当前帮助网页配置)
    实际令牌 = _取得请求令牌(request)
    return bool(期望令牌 and 实际令牌 and hmac.compare_digest(实际令牌, 期望令牌))


def _控制台错误(状态码: int, 文本: str) -> web.Response:
    return web.json_response({"ok": False, "error": 文本}, status=状态码)


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
            "token_mode": "自定义令牌" if _读取帮助网页字段(配置, "help_web_admin_token") else "自动令牌",
        },
    }


async def _处理控制台数据(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "访问令牌无效")
    try:
        数据 = await asyncio.to_thread(_读取控制台数据)
        return web.json_response(数据, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        logger.warning("帮助控制台数据读取失败：错误类型=%s", type(exc).__name__)
        return _控制台错误(500, "控制台数据暂时不可用")


async def _读取请求JSON(request: web.Request) -> dict[str, Any] | None:
    try:
        数据 = await request.json()
    except Exception:
        return None
    return 数据 if isinstance(数据, dict) else None


async def _处理小说开关(request: web.Request) -> web.Response:
    if not _请求已授权(request):
        return _控制台错误(401, "访问令牌无效")
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
        return _控制台错误(401, "访问令牌无效")
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
  <meta name="theme-color" content="#101828">
  <title>馒头控制台</title>
  <style>
    :root { color-scheme: light; --ink:#172033; --muted:#667085; --line:#e5e7eb; --bg:#f5f7fb; --panel:#fff; --nav:#101828; --nav-2:#182230; --blue:#2563eb; --blue-soft:#eff6ff; --green:#16a34a; --green-soft:#ecfdf3; --red:#dc2626; --amber-soft:#fffbeb; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; overflow-x:hidden; }
    button,input { font:inherit; }
    button { cursor:pointer; }
    .shell { min-height:100vh; display:grid; grid-template-columns:248px minmax(0,1fr); }
    .sidebar { background:var(--nav); color:#d0d5dd; padding:24px 16px; display:flex; flex-direction:column; gap:26px; }
    .brand { display:flex; align-items:center; gap:11px; padding:0 10px; color:#fff; }
    .brand-mark { width:34px; height:34px; display:grid; place-items:center; border-radius:10px; background:#2563eb; color:#fff; font-weight:800; }
    .brand strong { display:block; font-size:15px; }
    .brand small { display:block; margin-top:2px; color:#98a2b3; font-size:11px; }
    .nav-label { margin:0 10px 8px; color:#667085; font-size:10px; font-weight:800; letter-spacing:1.2px; text-transform:uppercase; }
    .nav { display:grid; gap:4px; }
    .nav a { display:flex; align-items:center; gap:10px; padding:10px 11px; border-radius:7px; color:#98a2b3; text-decoration:none; }
    .nav a:hover,.nav a.active,.nav a[aria-current="true"] { background:var(--nav-2); color:#fff; }
    .nav-icon { width:18px; color:#98a2b3; text-align:center; font-size:16px; }
    .nav a:focus-visible,.refresh:focus-visible,.switch:focus-visible,.pan-select:focus-visible { outline:3px solid #93c5fd; outline-offset:2px; }
    .sidebar-foot { margin-top:auto; padding:13px 12px; border:1px solid #293546; border-radius:8px; color:#98a2b3; font-size:12px; }
    .sidebar-foot strong { display:block; margin-bottom:3px; color:#e4e7ec; font-size:13px; }
    .main { min-width:0; }
    .topbar { height:72px; display:flex; align-items:center; justify-content:space-between; padding:0 34px; background:#fff; border-bottom:1px solid var(--line); }
    .topbar h1 { margin:0; font-size:20px; }
    .topbar p { margin:3px 0 0; color:var(--muted); font-size:12px; }
    .top-actions { display:flex; align-items:center; gap:12px; }
    .status-dot { display:inline-flex; align-items:center; gap:7px; padding:7px 10px; border:1px solid #d1fadf; border-radius:999px; background:var(--green-soft); color:#15803d; font-size:12px; font-weight:700; }
    .status-dot::before { content:""; width:7px; height:7px; border-radius:50%; background:#22c55e; }
    .refresh { border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--muted); padding:7px 11px; }
    .refresh:hover { border-color:#98a2b3; color:var(--ink); }
    .content { width:min(1380px,calc(100% - 68px)); margin:0 auto; padding:28px 0 50px; }
    .notice { display:none; margin-bottom:18px; padding:14px 16px; border:1px solid #fedf89; border-radius:8px; background:var(--amber-soft); color:#92400e; }
    .notice.show { display:block; }
    .metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-bottom:28px; }
    .metric { min-height:118px; padding:18px; background:var(--panel); border:1px solid var(--line); border-radius:8px; }
    .metric-label { color:var(--muted); font-size:12px; }
    .metric-value { margin-top:13px; color:var(--ink); font-size:25px; font-weight:750; }
    .metric-meta { margin-top:5px; color:var(--muted); font-size:12px; }
    .section { margin-top:30px; scroll-margin-top:86px; }
    .section-head { display:flex; align-items:flex-end; justify-content:space-between; margin-bottom:12px; }
    .section-head h2 { margin:0; font-size:16px; }
    .section-head p { margin:3px 0 0; color:var(--muted); font-size:12px; }
    .section-link { color:var(--blue); font-size:12px; text-decoration:none; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
    .global-bar { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:15px 18px; border-bottom:1px solid var(--line); background:#fbfcfe; }
    .global-actions { display:flex; align-items:center; gap:18px; flex:0 0 auto; }
    .test-mode { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; white-space:nowrap; }
    .global-copy strong { display:block; font-size:14px; }
    .global-copy span { display:block; margin-top:2px; color:var(--muted); font-size:12px; }
    .switch { position:relative; width:42px; height:24px; flex:0 0 auto; border:0; border-radius:999px; background:#d0d5dd; transition:background .18s ease; }
    .switch span { position:absolute; top:3px; left:3px; width:18px; height:18px; border-radius:50%; background:#fff; box-shadow:0 1px 3px #0002; transition:transform .18s ease; }
    .switch.on { background:var(--blue); }
    .switch.on span { transform:translateX(18px); }
    .switch:disabled { cursor:not-allowed; opacity:.45; }
    .novel-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); }
    .novel-item { display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:72px; padding:15px 18px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); }
    .novel-item:nth-child(3n) { border-right:0; }
    .novel-item:nth-last-child(-n+3) { border-bottom:0; }
    .novel-name { display:flex; align-items:center; gap:10px; min-width:0; }
    .novel-badge { width:28px; height:28px; display:grid; place-items:center; border-radius:7px; background:var(--blue-soft); color:var(--blue); font-size:12px; font-weight:800; }
    .novel-name strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .novel-name small { display:block; margin-top:2px; color:var(--muted); font-size:11px; }
    .pan-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
    .pan-card { padding:18px; border:1px solid var(--line); border-radius:8px; background:var(--panel); }
    .pan-card.active { border-color:#93c5fd; box-shadow:0 0 0 1px #bfdbfe inset; }
    .pan-top { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }
    .pan-title { display:flex; align-items:center; gap:9px; }
    .pan-logo { width:30px; height:30px; display:grid; place-items:center; border-radius:7px; background:#f2f4f7; color:#344054; font-weight:800; }
    .pan-title strong { font-size:14px; }
    .tag { display:inline-flex; padding:3px 7px; border-radius:999px; font-size:10px; font-weight:700; }
    .tag.active { background:var(--blue-soft); color:var(--blue); }
    .tag.ok { background:var(--green-soft); color:#15803d; }
    .tag.off { background:#f2f4f7; color:#667085; }
    .pan-meta { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:20px 0 14px; }
    .pan-meta span { display:block; color:var(--muted); font-size:11px; }
    .pan-meta strong { display:block; margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .account-list { display:grid; gap:6px; margin:0 0 14px; }
    .account-row { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 9px; border:1px solid #eef0f3; border-radius:6px; background:#fbfcfe; color:var(--muted); font-size:11px; }
    .account-row strong { color:var(--ink); font-size:12px; font-weight:650; }
    .account-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pan-select { width:100%; min-height:40px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--ink); padding:8px 10px; }
    .pan-select:disabled { color:#98a2b3; cursor:not-allowed; }
    .runtime-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }
    .runtime-item { padding:14px 15px; border:1px solid var(--line); border-radius:8px; background:var(--panel); }
    .runtime-item span { display:block; color:var(--muted); font-size:11px; }
    .runtime-item strong { display:block; margin-top:7px; font-size:14px; }
    .config-list { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); }
    .config-item { padding:15px 18px; border-right:1px solid var(--line); }
    .config-item:last-child { border-right:0; }
    .config-item span { display:block; color:var(--muted); font-size:11px; }
    .config-item strong { display:block; margin-top:5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .toast { position:fixed; right:22px; bottom:22px; z-index:10; transform:translateY(12px); opacity:0; pointer-events:none; padding:11px 14px; border-radius:7px; background:#172033; color:#fff; box-shadow:0 8px 25px #1018282b; transition:opacity .2s,transform .2s; }
    .toast.show { transform:translateY(0); opacity:1; }
    .empty { padding:30px; color:var(--muted); text-align:center; }
    @media (max-width:1050px) { .metrics { grid-template-columns:repeat(2,1fr); } .runtime-grid { grid-template-columns:repeat(3,1fr); } .config-list { grid-template-columns:repeat(2,1fr); } .config-item { border-right:1px solid var(--line); border-bottom:1px solid var(--line); } .config-item:nth-child(2n) { border-right:0; } .config-item:nth-last-child(-n+2) { border-bottom:0; } }
    @media (max-width:760px) { .shell { display:block; } .sidebar { padding:14px 12px 10px; gap:12px; } .brand { padding:0 6px; } .nav-label,.sidebar-foot { display:none; } .nav { display:flex; gap:4px; overflow-x:auto; scrollbar-width:none; } .nav::-webkit-scrollbar { display:none; } .nav a { flex:0 0 auto; padding:8px 10px; } .topbar { height:auto; min-height:68px; padding:14px 16px; } .topbar h1 { font-size:18px; } .status-dot { display:none; } .content { width:calc(100% - 28px); padding-top:20px; } .metrics,.pan-grid { grid-template-columns:1fr; } .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .novel-item:nth-child(3n) { border-right:1px solid var(--line); } .novel-item:nth-child(2n) { border-right:0; } .novel-item:nth-last-child(-n+3),.novel-item:last-child,.novel-item:nth-last-child(2) { border-bottom:1px solid var(--line); } .runtime-grid { grid-template-columns:repeat(2,1fr); } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { padding:13px; border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
  </style>
</head>
"""

_网页主体 = """
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">馒</div><div><strong>馒头控制台</strong><small>小说机器人管理中心</small></div></div>
      <div><div class="nav-label">Workspace</div><nav class="nav" aria-label="控制台导航"><a class="active" aria-current="true" data-nav="overview" href="#overview"><span class="nav-icon">▦</span>总览</a><a data-nav="novels" href="#novels"><span class="nav-icon">▤</span>小说功能</a><a data-nav="pans" href="#pans"><span class="nav-icon">◈</span>网盘配置</a><a data-nav="runtime" href="#runtime"><span class="nav-icon">◒</span>运行状态</a></nav></div>
      <div class="sidebar-foot"><strong>管理员控制台</strong><span>配置状态仅展示安全摘要，敏感凭据不会显示。</span></div>
    </aside>
    <main class="main">
      <header class="topbar"><div><h1>控制台</h1><p>集中管理小说平台、分享网盘和运行状态</p></div><div class="top-actions"><span class="status-dot">服务在线</span><button class="refresh" id="refresh" type="button">↻ 刷新</button></div></header>
      <div class="content">
        <div id="notice" class="notice"></div>
        <section id="overview" class="metrics"><div class="metric"><div class="metric-label">小说总开关</div><div id="metric-global" class="metric-value">--</div><div id="metric-global-meta" class="metric-meta">加载中</div></div><div class="metric"><div class="metric-label">当前分享网盘</div><div id="metric-pan" class="metric-value">--</div><div id="metric-pan-meta" class="metric-meta">加载中</div></div><div class="metric"><div class="metric-label">数据库</div><div id="metric-db" class="metric-value">--</div><div id="metric-db-meta" class="metric-meta">加载中</div></div><div class="metric"><div class="metric-label">插件版本</div><div id="metric-version" class="metric-value">--</div><div id="metric-version-meta" class="metric-meta">馒头 bot</div></div></section>
        <section id="novels" class="section"><div class="section-head"><div><h2>小说功能</h2><p>单独控制每个平台，关闭后不影响其他平台。</p></div><a class="section-link" href="#novels">管理开关</a></div><div class="panel"><div class="global-bar"><div class="global-copy"><strong>全局小说功能</strong><span>关闭后所有小说下载、找书和翻页入口都会暂停。</span></div><div class="global-actions"><div class="test-mode"><span>管理员测试模式</span><button id="test-switch" class="switch" type="button" aria-label="切换管理员测试模式"><span></span></button></div><button id="global-switch" class="switch" type="button" aria-label="切换全局小说功能"><span></span></button></div></div><div id="novel-grid" class="novel-grid"><div class="empty">正在读取小说平台...</div></div></div></section>
        <section id="pans" class="section"><div class="section-head"><div><h2>网盘配置</h2><p>选择小说完成后的主分享网盘，账号数量和上传目录仅显示摘要。</p></div><a class="section-link" href="#pans">查看配置</a></div><div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态...</div></div></section>
        <section id="runtime" class="section"><div class="section-head"><div><h2>运行状态</h2><p>服务器和插件的实时摘要。</p></div><span id="updated" class="section-link">--</span></div><div class="runtime-grid"><div class="runtime-item"><span>CPU占用</span><strong id="runtime-cpu">--</strong></div><div class="runtime-item"><span>物理内存</span><strong id="runtime-memory">--</strong></div><div class="runtime-item"><span>磁盘空间</span><strong id="runtime-disk">--</strong></div><div class="runtime-item"><span>系统运行时间</span><strong id="runtime-runtime">--</strong></div><div class="runtime-item"><span>操作系统</span><strong id="runtime-os">--</strong></div></div></section>
        <section class="section"><div class="section-head"><div><h2>当前配置</h2><p>网页监听和控制台访问策略。</p></div></div><div id="config-list" class="panel config-list"><div class="empty">正在读取配置...</div></div></section>
      </div>
    </main>
  </div>
  <div id="toast" class="toast" role="status"></div>
"""

_网页脚本 = """
  <script>
    (() => {
      const token = new URLSearchParams(location.search).get('token') || '';
      const $ = (id) => document.getElementById(id);
      const esc = (value) => String(value ?? '').replace(/[&<>\"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[char]));
      let snapshot = null;
      let toastTimer = null;
      const showNotice = (message) => { const node = $('notice'); node.textContent = message; node.classList.toggle('show', Boolean(message)); };
      const toast = (message) => { const node = $('toast'); node.textContent = message; node.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('show'), 2200); };
      const api = async (path, options = {}) => {
        const query = `?token=${encodeURIComponent(token)}`;
        const response = await fetch(`/api/${path}${query}`, { cache:'no-store', headers:{'Content-Type':'application/json'}, ...options });
        const data = await response.json().catch(() => ({ok:false,error:'服务器返回格式错误'}));
        if (!response.ok || !data.ok) throw new Error(data.error || '请求失败');
        return data;
      };
      const switchHtml = (key, enabled, editable, label) => `<button class="switch ${enabled ? 'on' : ''}" data-switch="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(label)}" aria-pressed="${enabled}"><span></span></button>`;
      const render = (data) => {
        snapshot = data;
        const novels = data.novels || {};
        const pans = data.pans || {};
        const server = data.server || {};
        const database = data.database || {};
        $('metric-global').textContent = novels.global_enabled ? '已开启' : '已关闭';
        $('metric-global-meta').textContent = novels.test_mode ? '测试模式已开启' : '测试模式未开启';
        $('metric-pan').textContent = pans.active || '--';
        const activePan = (pans.items || []).find((item) => item.active);
        $('metric-pan-meta').textContent = activePan ? `${activePan.accounts} 个账号 · ${activePan.configured ? '已配置' : '未配置'}` : '未选择';
        $('metric-db').textContent = database.status || '--';
        $('metric-db-meta').textContent = database.configured ? '状态可持久化' : '未配置数据库';
        $('metric-version').textContent = `v${data.version || '--'}`;
        [['global-switch', '__global__', novels.global_enabled, '切换全局小说功能'], ['test-switch', '__test__', novels.test_mode, '切换管理员测试模式']].forEach(([id, key, enabled, label]) => {
          const node = $(id);
          node.className = `switch ${enabled ? 'on' : ''}`;
          node.dataset.switch = key;
          node.dataset.enabled = String(Boolean(enabled));
          node.disabled = !novels.editable;
          node.setAttribute('aria-label', label);
          node.setAttribute('aria-pressed', String(Boolean(enabled)));
        });
        $('novel-grid').innerHTML = (novels.platforms || []).map((item) => `<div class="novel-item"><div class="novel-name"><div class="novel-badge">书</div><div><strong>${esc(item.name)}</strong><small>${item.enabled ? '当前可用' : '已停用'}</small></div></div>${switchHtml(item.key, item.enabled, novels.editable, `切换${item.name}`)}</div>`).join('') || '<div class="empty">没有可用小说平台</div>';
        $('pan-grid').innerHTML = (pans.items || []).map((item) => { const accounts = (item.account_summary || []).map((account) => `<div class="account-row"><strong>账号${esc(account.index)}</strong><span>${esc(account.name)} · ${esc(account.phone)}</span></div>`).join(''); return `<article class="pan-card ${item.active ? 'active' : ''}"><div class="pan-top"><div class="pan-title"><div class="pan-logo">${esc(item.key.slice(0,1))}</div><strong>${esc(item.name)}</strong></div><div>${item.active ? '<span class="tag active">当前主网盘</span>' : ''}</div></div><div class="pan-meta"><div><span>配置状态</span><strong>${item.configured ? '<span class="tag ok">已配置</span>' : '<span class="tag off">未配置</span>'}</strong></div><div><span>账号数量</span><strong>${esc(item.accounts)} 个</strong></div><div><span>上传目录</span><strong title="${esc(item.directory)}">${esc(item.directory || '默认目录')}</strong></div><div><span>账号策略</span><strong>按群独立选择</strong></div></div>${accounts ? `<div class="account-list">${accounts}</div>` : ''}<select class="pan-select" data-pan="${esc(item.key)}" ${pans.editable ? '' : 'disabled'} aria-label="选择${esc(item.name)}"><option value="">${item.active ? '当前使用中' : '设为主分享网盘'}</option><option value="${esc(item.key)}">切换到${esc(item.name)}</option></select></article>`; }).join('') || '<div class="empty">没有网盘数据</div>';
        $('runtime-cpu').textContent = server.cpu || '--'; $('runtime-memory').textContent = server.memory || '--'; $('runtime-disk').textContent = server.disk || '--'; $('runtime-runtime').textContent = server.runtime || '--'; $('runtime-os').textContent = server.os || '--';
        $('config-list').innerHTML = `<div class="config-item"><span>监听地址</span><strong>${esc(server.listen || '--')}</strong></div><div class="config-item"><span>访问地址</span><strong title="${esc(server.address)}">${esc(server.address || '--')}</strong></div><div class="config-item"><span>域名模式</span><strong>${data.config && data.config.custom_domain ? '自定义域名' : '自动服务器 IP'}</strong></div><div class="config-item"><span>访问令牌</span><strong>${esc(data.config && data.config.token_mode || '自动令牌')}</strong></div>`;
        $('updated').textContent = '刚刚更新';
        showNotice(!token ? '当前页面没有访问令牌，请从聊天中的“打开网页版帮助”按钮进入控制台。' : '');
        document.querySelectorAll('[data-switch]').forEach((node) => node.addEventListener('click', () => changeNovel(node)));
        document.querySelectorAll('[data-pan]').forEach((node) => node.addEventListener('change', () => { const value = node.value; node.value = ''; if (value) changePan(value, node); }));
      };
      const changeNovel = async (node) => { if (!snapshot || !snapshot.novels.editable) return toast('数据库未配置，开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { await api('novel-switch', {method:'POST', body:JSON.stringify({key:node.dataset.switch, enabled})}); toast('小说开关已更新'); await load(); } catch (error) { node.disabled = false; toast(error.message); } };
      const changePan = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘选择不能保存'); if (node) node.disabled = true; try { await api('pan-switch', {method:'POST', body:JSON.stringify({key})}); toast('主分享网盘已更新'); await load(); } catch (error) { if (node) node.disabled = false; toast(error.message); } };
      const load = async () => { try { render(await api('dashboard')); } catch (error) { showNotice(error.message); } };
      const navLinks = [...document.querySelectorAll('[data-nav]')];
      const updateNav = () => {
        let current = 'overview';
        navLinks.forEach((link) => {
          const section = $(link.dataset.nav);
          if (section && section.getBoundingClientRect().top <= 120) current = link.dataset.nav;
        });
        navLinks.forEach((link) => {
          const active = link.dataset.nav === current;
          link.classList.toggle('active', active);
          link.setAttribute('aria-current', active ? 'true' : 'false');
        });
      };
      window.addEventListener('scroll', updateNav, {passive:true});
      navLinks.forEach((link) => link.addEventListener('click', () => setTimeout(updateNav, 0)));
      $('refresh').addEventListener('click', load); load(); updateNav();
    })();
  </script>
</body>
</html>
"""


async def _处理帮助网页(request: web.Request) -> web.Response:
    del request
    return web.Response(
        text=_渲染控制台页面(),
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

    基础地址 = _计算帮助网页地址(配置)
    public_url = _构造控制台访问地址(基础地址, 配置)
    host, port = _读取监听配置(配置)
    app = web.Application()
    app.router.add_get("/", _处理帮助网页)
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
