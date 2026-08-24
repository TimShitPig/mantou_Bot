from __future__ import annotations

import html
import ipaddress
import logging
import socket
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


@dataclass
class 帮助网页服务:
    runner: web.AppRunner
    public_url: str
    host: str
    port: int


# importlib.reload 会复用原模块字典；保留旧引用，确保重载时可以清理旧端口。
当前帮助网页服务: 帮助网页服务 | None = globals().get("当前帮助网页服务")
自动公开地址缓存: str | None = globals().get("自动公开地址缓存")
网页服务启动状态: bool | None = globals().get("网页服务启动状态")


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
                请求 = Request(地址服务, headers={"User-Agent": "mantou-help-web/1.0"})
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


def 获取帮助网页地址(配置: Any = None) -> str:
    """返回已启动服务地址；服务启动前返回自动候选地址供初始化使用。"""
    if 当前帮助网页服务 is not None:
        return 当前帮助网页服务.public_url
    if 网页服务启动状态 is False:
        return ""
    return _计算帮助网页地址(配置)


def _读取监听配置(配置: Any) -> tuple[str, int]:
    host = str(_读取帮助网页字段(配置, "help_web_host") or 默认监听地址).strip()
    if not host:
        host = 默认监听地址
    try:
        port = int(_读取帮助网页字段(配置, "help_web_port") or 默认监听端口)
    except (TypeError, ValueError):
        port = 默认监听端口
    return host, max(1, min(65535, port))


def _渲染帮助条目(大类序号: int, 小类序号: int, 触发序号: int, 触发项: dict[str, Any]) -> str:
    名称 = html.escape(str(触发项.get("名称") or "帮助项"))
    触发 = html.escape(str(触发项.get("触发") or ""))
    详情 = html.escape(str(触发项.get("详情") or ""))
    搜索值 = html.escape(f"{名称} {触发} {详情}", quote=True)
    项目编号 = f"item-{大类序号}-{小类序号}-{触发序号}"
    return (
        f'<article class="help-item" id="{项目编号}" data-search="{搜索值}">'
        f"<h3>{名称}</h3>"
        f'<p class="trigger"><span>触发</span>{触发}</p>'
        f'<p class="description">{详情}</p>'
        "</article>"
    )


def _渲染帮助页面() -> str:
    # 延迟导入，避免 main.py 重载帮助功能和网页模块时产生循环导入。
    from 功能文件.管理功能.基础功能.帮助功能 import 帮助大类

    导航: list[str] = []
    分组内容: list[str] = []
    for 大类序号, 大类 in enumerate(帮助大类):
        大类名称 = str(大类.get("名称") or f"分类{大类序号 + 1}")
        大类锚点 = f"category-{大类序号}"
        导航.append(f'<a href="#{大类锚点}">{html.escape(大类名称)}</a>')
        小类内容: list[str] = []
        for 小类序号, 小类 in enumerate(大类.get("小类") or []):
            小类名称 = html.escape(str(小类.get("名称") or "功能"))
            条目内容 = "".join(
                _渲染帮助条目(大类序号, 小类序号, 触发序号, 触发项)
                for 触发序号, 触发项 in enumerate(小类.get("触发项") or [])
                if isinstance(触发项, dict)
            )
            if 条目内容:
                小类内容.append(
                    f'<section class="subgroup"><h2>{小类名称}</h2>{条目内容}</section>'
                )
        if 小类内容:
            分组内容.append(
                f'<section class="category" id="{大类锚点}">'
                f"<h1>{html.escape(大类名称)}</h1>{''.join(小类内容)}</section>"
            )

    return _网页头部 + "".join(导航) + _网页导航尾部 + "".join(分组内容) + _网页尾部


_网页头部 = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="馒头bot功能帮助">
  <title>馒头bot帮助</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #52606d;
      --line: #d9e2ec;
      --paper: #ffffff;
      --page: #f5f7fa;
      --navy: #102a43;
      --teal: #0f766e;
      --amber: #b45309;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background: var(--page);
      color: var(--ink);
      font: 16px/1.65 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    a { color: inherit; }
    .topbar {
      background: var(--navy);
      color: #fff;
      padding: 28px max(20px, calc((100vw - 1180px) / 2));
    }
    .topbar h1 { margin: 0; font-size: 2.2rem; letter-spacing: 0; }
    .topbar p { margin: 6px 0 0; color: #d9e2ec; }
    .layout {
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      gap: 28px;
      width: min(1180px, calc(100% - 40px));
      margin: 28px auto 48px;
      align-items: start;
    }
    .sidebar {
      position: sticky;
      top: 20px;
      display: grid;
      gap: 8px;
      padding: 16px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .sidebar strong { color: var(--navy); margin-bottom: 4px; }
    .sidebar a { padding: 7px 8px; color: var(--muted); text-decoration: none; border-radius: 5px; }
    .sidebar a:hover, .sidebar a:focus-visible { background: #e6fffa; color: var(--teal); }
    .content { min-width: 0; }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .toolbar {
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      gap: 12px;
      align-items: center;
      margin-bottom: 24px;
      padding: 12px 0;
      background: var(--page);
    }
    .toolbar input {
      width: 100%;
      min-height: 44px;
      padding: 9px 13px;
      border: 1px solid #bcccdc;
      border-radius: 6px;
      background: var(--paper);
      color: var(--ink);
      font: inherit;
    }
    .toolbar input:focus { outline: 3px solid #b2f5ea; border-color: var(--teal); }
    .category { scroll-margin-top: 72px; margin-bottom: 34px; }
    .category > h1 { margin: 0 0 15px; color: var(--navy); font-size: 1.55rem; }
    .subgroup { margin: 0 0 24px; }
    .subgroup h2 {
      margin: 0 0 10px;
      padding-bottom: 7px;
      border-bottom: 2px solid var(--line);
      color: var(--teal);
      font-size: 1.08rem;
    }
    .help-item {
      margin: 10px 0;
      padding: 15px 17px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--amber);
      border-radius: 7px;
      background: var(--paper);
    }
    .help-item[hidden] { display: none; }
    .help-item h3 { margin: 0 0 5px; font-size: 1rem; }
    .help-item p { margin: 4px 0 0; }
    .trigger { color: var(--navy); font-weight: 600; white-space: pre-wrap; overflow-wrap: anywhere; }
    .trigger span {
      display: inline-block;
      margin-right: 8px;
      padding: 1px 6px;
      border-radius: 4px;
      background: #fff3c4;
      color: #7b341e;
      font-size: .78rem;
      font-weight: 700;
    }
    .description { color: var(--muted); white-space: pre-wrap; overflow-wrap: anywhere; }
    .empty { padding: 22px; color: var(--muted); text-align: center; }
    @media (max-width: 720px) {
      .topbar { padding: 22px 18px; }
      .topbar h1 { font-size: 1.75rem; }
      .layout { display: block; width: min(100% - 24px, 680px); margin-top: 12px; }
      .sidebar { position: static; display: flex; gap: 6px; overflow-x: auto; margin-bottom: 10px; padding: 8px; }
      .sidebar strong { display: none; }
      .sidebar a { flex: 0 0 auto; white-space: nowrap; }
      .toolbar { padding: 8px 0; }
      .help-item { padding: 13px 14px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <h1>馒头bot帮助</h1>
    <p>按分类查看管理、小说、网盘和群聊功能。</p>
  </header>
  <div class="layout">
    <nav class="sidebar" aria-label="帮助分类"><strong>分类</strong>
"""

_网页导航尾部 = """
    </nav>
    <main class="content">
      <div class="toolbar">
        <label for="help-search" class="sr-only">搜索帮助</label>
        <input id="help-search" type="search" placeholder="搜索功能、触发词或说明" autocomplete="off">
      </div>
"""

_网页尾部 = """
    </main>
  </div>
  <script>
    (() => {
      const input = document.querySelector('#help-search');
      const items = [...document.querySelectorAll('.help-item')];
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = '没有匹配的帮助内容';
      document.querySelector('.content').appendChild(empty);
      const update = () => {
        const query = input.value.trim().toLocaleLowerCase();
        let visible = 0;
        items.forEach((item) => {
          const matched = !query || item.dataset.search.toLocaleLowerCase().includes(query);
          item.hidden = !matched;
          if (matched) visible += 1;
        });
        empty.hidden = visible !== 0;
      };
      input.addEventListener('input', update);
      update();
    })();
  </script>
</body>
</html>
"""


async def _处理帮助网页(request: web.Request) -> web.Response:
    del request
    try:
        return web.Response(
            text=_渲染帮助页面(),
            content_type="text/html",
            charset="utf-8",
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        logger.warning("帮助网页渲染失败：错误类型=%s", type(exc).__name__)
        return web.Response(
            text="帮助网页暂时不可用",
            status=500,
            content_type="text",
            charset="utf-8",
        )


async def 启动帮助网页服务(配置: Any = None) -> 帮助网页服务 | None:
    global 当前帮助网页服务, 网页服务启动状态
    await 停止帮助网页服务(当前帮助网页服务)
    当前帮助网页服务 = None
    网页服务启动状态 = False

    public_url = _计算帮助网页地址(配置)

    host, port = _读取监听配置(配置)
    app = web.Application()
    app.router.add_get("/", _处理帮助网页)
    app.router.add_get("/{tail:.*}", _处理帮助网页)
    runner = web.AppRunner(app, access_log=None)
    try:
        await runner.setup()
        await web.TCPSite(runner, host, port).start()
    except Exception as exc:
        await runner.cleanup()
        logger.warning("帮助网页启动失败：错误类型=%s", type(exc).__name__)
        return None

    当前帮助网页服务 = 帮助网页服务(runner, public_url, host, port)
    网页服务启动状态 = True
    logger.info("帮助网页已启动：监听地址=%s, 监听端口=%s, 访问地址=%s", host, port, public_url)
    return 当前帮助网页服务


async def 停止帮助网页服务(服务: 帮助网页服务 | None) -> None:
    global 当前帮助网页服务, 网页服务启动状态
    if 服务 is None:
        return
    try:
        await 服务.runner.cleanup()
    except Exception as exc:
        logger.warning("帮助网页停止失败：错误类型=%s", type(exc).__name__)
    finally:
        if 当前帮助网页服务 is 服务:
            当前帮助网页服务 = None
            网页服务启动状态 = None
