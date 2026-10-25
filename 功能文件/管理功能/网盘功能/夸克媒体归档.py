"""聊天附件原字节归档到夸克默认账号；网页通过受保护的同源接口读取。"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import ipaddress
import re
import socket
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlencode, urljoin, urlsplit

import aiohttp

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from .媒体归档工具 import (
    _媒体种类, _媒体项目列表, _原附件后缀, 识别媒体类型, 解析媒体范围,
)

媒体最大字节数 = 100 * 1024 * 1024
归档目录 = "/QQ聊天媒体"
直链复用秒 = 300
下载请求头 = {"User-Agent": "Mozilla/5.0", "Referer": "https://pan.quark.cn/"}
图片归档待恢复: dict[tuple[str, str], dict[str, Any]] = globals().get("图片归档待恢复", {})
图片归档任务: set[asyncio.Task[Any]] = globals().get("图片归档任务", set())
图片归档接收开启 = False
_唤醒: asyncio.TimerHandle | None = globals().get("_唤醒")
_上传并发 = globals().get("_上传并发", asyncio.Semaphore(2))


class 媒体归档错误(RuntimeError):
    def __init__(self, 阶段: str, 状态码: int = 0):
        super().__init__(阶段)
        self.阶段 = 阶段
        self.状态码 = 状态码


def _配置快照(配置: Any) -> dict[str, Any]:
    from 功能文件.管理功能.基础功能.消息记录存储 import 获取数据库配置快照
    # 普通字典交给线程，避免复制 AstrBotConfig 内部锁。
    数据库 = 获取数据库配置快照(配置)
    return {"database_settings": dict(数据库["database_settings"]),
            "quark_pan_settings": dict(配置.get("quark_pan_settings", {}) or {})}


def _账号资料(配置: Any) -> list[dict[str, Any]]:
    from . import 网盘Cookie
    return 网盘Cookie._读取保存的网盘账号记录(配置, "夸克")


def _账号标识(账号: dict[str, Any]) -> str:
    from . import 网盘Cookie
    身份 = str(账号.get("identity") or 网盘Cookie._获取网盘Cookie身份键("夸克", 账号.get("cookie")) or "")
    if not 身份:
        raise 媒体归档错误("account_identity_missing")
    return hashlib.sha256(身份.encode("utf-8")).hexdigest()


def _读取默认账号(配置: Any) -> dict[str, str]:
    from . import 网盘Cookie
    # 直接读取默认序号，不经过小说任务的账号 ContextVar 或群选择。
    序号 = 网盘Cookie.获取默认网盘账号序号(配置, "夸克")
    账号列表 = _账号资料(配置)
    if not 1 <= 序号 <= len(账号列表):
        raise 媒体归档错误("default_account_missing")
    账号 = 账号列表[序号 - 1]
    if not 账号.get("enabled", True) or not 账号.get("cookie"):
        raise 媒体归档错误("default_account_disabled")
    return {"account_id": _账号标识(账号), "cookie": str(账号["cookie"])}


def _读取绑定账号(配置: Any, 账号ID: str) -> str:
    for 账号 in _账号资料(配置):
        try:
            匹配 = _账号标识(账号) == 账号ID
        except 媒体归档错误:
            continue
        if 匹配 and 账号.get("cookie"):
            return str(账号["cookie"])
    raise 媒体归档错误("archive_account_missing")


async def _校验下载地址(地址: str, *, 夸克: bool = False) -> str:
    if not isinstance(地址, str) or len(地址) > 8192 or re.search(r"[\x00-\x20\x7f]", 地址):
        raise 媒体归档错误("url_invalid")
    try:
        解析 = urlsplit(地址)
        主机 = (解析.hostname or "").lower().rstrip(".")
        有效 = 解析.scheme.lower() == "https" and 主机 and 解析.username is None and 解析.password is None and 解析.port in (None, 443)
    except ValueError:
        raise 媒体归档错误("url_invalid") from None
    if not 有效 or 解析.fragment or 夸克 and not (主机 == "quark.cn" or 主机.endswith(".quark.cn")):
        raise 媒体归档错误("url_invalid")
    try:
        地址列表 = [ipaddress.ip_address(主机)]
    except ValueError:
        try:
            地址列表 = [ipaddress.ip_address(x[4][0]) for x in await asyncio.get_running_loop().getaddrinfo(主机, 443, type=socket.SOCK_STREAM)]
        except (OSError, ValueError) as exc:
            raise 媒体归档错误("dns_failed") from exc
    if not 地址列表 or any(not x.is_global for x in 地址列表):
        raise 媒体归档错误("host_not_public")
    return 地址


async def _请求原字节(会话: aiohttp.ClientSession, 地址: str, *, 范围: str = "", Cookie: str = "") -> aiohttp.ClientResponse:
    for _ in range(5):
        地址 = await _校验下载地址(地址, 夸克=bool(Cookie))
        请求头 = dict(下载请求头)
        if Cookie:
            请求头["Cookie"] = Cookie
        if 范围:
            请求头["Range"] = 范围
        响应 = await 会话.get(地址, headers=请求头, allow_redirects=False)
        if 响应.status not in {301, 302, 303, 307, 308}:
            return 响应
        位置 = 响应.headers.get("Location", "")
        响应.release()
        if not 位置:
            raise 媒体归档错误("redirect_invalid")
        地址 = urljoin(地址, 位置)
    raise 媒体归档错误("redirect_limit")


def _新建会话() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, connect=20, sock_read=90),
                                 cookie_jar=aiohttp.DummyCookieJar(), trust_env=True)


async def _下载QQ媒体(地址: str, 路径: Path, 种类: str) -> tuple[str, int]:
    from 功能文件.页面功能 import 帮助网页后端
    if not 帮助网页后端._允许媒体地址(地址):
        raise 媒体归档错误("source_url_invalid")
    async with _新建会话() as 会话:
        响应 = await _请求原字节(会话, 地址)
        try:
            if 响应.status != 200:
                raise 媒体归档错误("source_status", 响应.status)
            if 响应.content_length is not None and 响应.content_length > 媒体最大字节数:
                raise 媒体归档错误("source_too_large")
            总数 = 0
            前缀 = bytearray()
            with 路径.open("wb") as 文件:
                async for 块 in 响应.content.iter_chunked(64 * 1024):
                    总数 += len(块)
                    if 总数 > 媒体最大字节数:
                        raise 媒体归档错误("source_too_large")
                    if len(前缀) < 128:
                        前缀.extend(块[:128 - len(前缀)])
                    写任务 = asyncio.create_task(asyncio.to_thread(文件.write, 块))
                    try:
                        await asyncio.shield(写任务)
                    except asyncio.CancelledError:
                        await 写任务
                        raise
            MIME = 识别媒体类型(bytes(前缀), 响应.headers.get("Content-Type"), 预期种类=种类)
            if not 总数 or not MIME or 响应.content_length is not None and 总数 != 响应.content_length:
                raise 媒体归档错误("source_not_media")
            return MIME, 总数
        finally:
            响应.release()


def _日期目录(记录: dict[str, Any]) -> str:
    try:
        原值 = 记录.get("ts") or 记录.get("time") or 记录.get("timestamp") or 0
        try:
            数值 = float(原值)
            日期 = datetime.fromtimestamp(数值) if 数值 > 0 else datetime.now()
        except ValueError:
            日期 = datetime.fromisoformat(str(原值).replace("Z", "+00:00")).astimezone()
    except (ValueError, TypeError, OverflowError, OSError):
        日期 = datetime.now()
    return f"{归档目录}/{日期.year}年{日期.month}月{日期.day}日"


async def _归档单项(参数: dict[str, Any], 索引: int, 项目: dict[str, Any], 进度: dict[str, Any]) -> dict[str, Any]:
    async with _上传并发:
        return await _执行归档单项(参数, 索引, 项目, 进度)


async def _执行归档单项(参数: dict[str, Any], 索引: int, 项目: dict[str, Any], 进度: dict[str, Any]) -> dict[str, Any]:
    from . import 夸克网盘
    from 功能文件.管理功能.基础功能 import 文件缓存
    if isinstance(进度.get("archive"), dict):
        return dict(进度["archive"])
    if 进度.get("upload_submitted") and not 进度.get("file_id"):
        raise 媒体归档错误("upload_result_unconfirmed")
    路径 = None
    try:
        账号 = 参数.get("account")
        if not 账号:
            账号 = await asyncio.to_thread(_读取默认账号, 参数["config"])
            参数["account"] = 账号
        elif not 进度.get("file_id"):
            # 凭据更新沿用原账号身份，默认账号变化不迁移已经绑定的任务。
            Cookie = await asyncio.to_thread(_读取绑定账号, 参数["config"], 账号["account_id"])
            账号 = 参数["account"] = {"account_id": 账号["account_id"], "cookie": Cookie}
        if not 进度.get("file_id"):
            路径 = 文件缓存.创建临时缓存文件("mantou-quark-media-", ".tmp")
            文件缓存.标记临时缓存正在使用(路径)
            地址 = str(项目.get("src") or 项目.get("url") or 项目.get("download_url") or "")
            MIME, 大小 = await _下载QQ媒体(地址, 路径, _媒体种类(项目))
            原名 = str(项目.get("name") or 项目.get("filename") or "")
            唯一键 = f"{参数['record'].get('_session')}:{参数['record'].get('message_id')}:{索引}"
            文件名 = hashlib.sha256(唯一键.encode()).hexdigest() + _原附件后缀(项目, MIME)
            进度.update(content_type=MIME, size=大小, filename=文件名, original_name=原名 or 文件名,
                      media_kind=_媒体种类(项目), account_id=账号["account_id"])
            async with 夸克网盘.夸克网盘客户端(账号["cookie"]) as 客户端:
                async with 夸克网盘.获取夸克账号操作锁(账号["cookie"]):
                    进度["parent_id"] = await 客户端.确保目录路径(_日期目录(参数["record"]))
                    # 从提交开始至取得文件 ID 期间保持不确定状态，取消与断流不重放。
                    进度["upload_submitted"] = True
                    进度["file_id"] = await 客户端.上传文件(路径, 进度["parent_id"], 文件名)
                    if not 进度["file_id"]:
                        raise 媒体归档错误("upload_id_missing")
        字段 = ("file_id", "account_id", "parent_id", "content_type", "size", "filename", "original_name", "media_kind")
        归档 = {k: 进度[k] for k in 字段}
        进度["archive"] = 归档
        return dict(归档)
    finally:
        if 路径 is not None:
            try:
                路径.unlink(missing_ok=True)
            finally:
                文件缓存.解除临时缓存占用(路径)


def _已有归档(媒体: dict[str, Any], 索引: int) -> bool:
    return isinstance((媒体.get("_quark_archives") or {}).get(str(索引)), dict) or isinstance(
        (媒体.get("_lanzou_archives") or {}).get(str(索引)), dict) or 索引 == 0 and isinstance(媒体.get("_lanzou_archive"), dict)


def _旧项目可完成(进度: dict[str, Any]) -> bool:
    远端 = 进度.get("remote_task")
    return bool(进度.get("archive") or 进度.get("file_id") or
                isinstance(远端, asyncio.Task) and
                (not 远端.done() or not 远端.cancelled() and 远端.exception() is None))


def _释放未提交旧项(进度: dict[str, Any]) -> None:
    旧 = 进度.get("_legacy")
    if isinstance(旧, dict) and not 旧.get("upload_submitted") and not _旧项目可完成(旧):
        # 旧下载/明确拒绝已结束且未提交，可以改走夸克；未知提交继续保护。
        进度.pop("_legacy", None)
        进度.pop("remote_task", None)


async def _完成旧归档(参数: dict[str, Any], 进度: dict[str, Any]) -> dict[str, Any]:
    旧进度 = 进度["_legacy"]
    if isinstance(旧进度.get("archive"), dict):
        return dict(旧进度["archive"])
    远端 = 旧进度.get("remote_task")
    if isinstance(远端, asyncio.Task) and (not 远端.done() or not 远端.cancelled() and 远端.exception() is None):
        try:
            归档 = await asyncio.shield(远端)
            if isinstance(归档, dict):
                旧进度["archive"] = 归档
                return dict(归档)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
    if not 旧进度.get("file_id"):
        raise 媒体归档错误("legacy_upload_unconfirmed")
    # 仅续接已确认的旧文件分享，绝不调用旧上传入口或补交上传。
    旧模块 = 参数["legacy_module"]
    Cookie, UID = 旧模块._解析Cookie(旧模块._配置值(参数["legacy_config"]))
    if 旧进度.get("uid") not in (None, UID):
        raise 媒体归档错误("legacy_account_changed")
    async with _上传并发:
        return await 旧模块._上传并取得归档资料(Cookie, UID, 旧进度, None)


def _可运行(参数: dict[str, Any]) -> bool:
    媒体 = 参数["record"].get("media") or {}
    for 索引, _ in _媒体项目列表(媒体):
        项 = 参数.get("progress", {}).get(索引, {})
        _释放未提交旧项(项)
        if _已有归档(媒体, 索引):
            continue
        if "_legacy" in 项:
            if _旧项目可完成(项["_legacy"]):
                return True
            continue
        远端 = 项.get("remote_task")
        if 项.get("upload_submitted") and not 项.get("file_id") and (not isinstance(远端, asyncio.Task) or 远端.done()):
            continue
        if 项.get("file_id") or int(项.get("source_failures", 0)) < 3:
            return True
    return False


async def _处理记录(键: tuple[str, str], 参数: dict[str, Any]) -> None:
    from 功能文件.管理功能.基础功能 import 消息记录
    try:
        if not 消息记录.消息数据库已配置():
            参数["retry_at"] = asyncio.get_running_loop().time() + 300
            return
        for 索引, 项目 in _媒体项目列表(参数["record"].get("media")):
            if _已有归档(参数["record"]["media"], 索引):
                continue
            进度 = 参数.setdefault("progress", {}).setdefault(索引, {})
            _释放未提交旧项(进度)
            if "_legacy" in 进度 and not _旧项目可完成(进度["_legacy"]):
                continue
            if int(进度.get("source_failures", 0)) >= 3 and not 进度.get("file_id"):
                continue
            try:
                远端 = 进度.get("remote_task")
                if not isinstance(远端, asyncio.Task) or 远端.done() and (远端.cancelled() or 远端.exception() is not None):
                    远端 = asyncio.create_task(_完成旧归档(参数, 进度) if "_legacy" in 进度 else _归档单项(参数, 索引, 项目, 进度))
                    进度["remote_task"] = 远端
                    远端.add_done_callback(_读取任务结果)
                归档 = await asyncio.shield(远端)
                提供方 = "lanzou" if "_legacy" in 进度 else "quark"
                if not 消息记录.更新消息媒体归档(键[0], 键[1], 归档, 原记录=参数["record"], 媒体索引=索引, provider=提供方):
                    raise 媒体归档错误("message_persist_rejected")
                参数["record"]["media"].setdefault("_lanzou_archives" if 提供方 == "lanzou" else "_quark_archives", {})[str(索引)] = 归档
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not 进度.get("upload_submitted") and getattr(exc, "阶段", "").startswith("source_"):
                    进度["source_failures"] = int(进度.get("source_failures", 0)) + 1
                logger.warning("夸克媒体归档失败：媒体序号=%s，种类=%s，阶段=%s，错误类型=%s，状态=%s",
                               索引 + 1, _媒体种类(项目), getattr(exc, "阶段", "archive"), type(exc).__name__, getattr(exc, "状态码", 0) or "none")
        if all(_已有归档(参数["record"]["media"], i) for i, _ in _媒体项目列表(参数["record"].get("media"))):
            图片归档待恢复.pop(键, None)
        else:
            参数["retry_at"] = asyncio.get_running_loop().time() + 300
    finally:
        参数.pop("task", None)


def _读取任务结果(任务: asyncio.Task[Any]) -> None:
    if not 任务.cancelled():
        任务.exception()


def _完成(任务: asyncio.Task[Any]) -> None:
    图片归档任务.discard(任务)
    _读取任务结果(任务)
    _排空队列()


def _排空队列() -> None:
    global _唤醒
    if _唤醒 is not None:
        _唤醒.cancel()
        _唤醒 = None
    if not 图片归档接收开启:
        return
    循环 = asyncio.get_running_loop()
    最早 = None
    for 键, 参数 in list(图片归档待恢复.items()):
        if not _可运行(参数) or isinstance(参数.get("task"), asyncio.Task):
            continue
        截止 = float(参数.get("retry_at") or 0)
        if 截止 > 循环.time():
            最早 = 截止 if 最早 is None else min(最早, 截止)
            continue
        if len(图片归档任务) >= 2:
            break
        任务 = asyncio.create_task(_处理记录(键, 参数))
        参数["task"] = 任务
        图片归档任务.add(任务)
        任务.add_done_callback(_完成)
    if 最早 is not None and len(图片归档任务) < 2:
        _唤醒 = 循环.call_at(最早, _排空队列)


def 安排归档消息图片(配置: Any, 记录: dict[str, Any]) -> bool:
    from 功能文件.管理功能.基础功能 import 消息记录
    if not 图片归档接收开启 or not 消息记录.消息数据库已配置() or not _媒体项目列表(记录.get("media")):
        return False
    键 = (str(记录.get("_session") or ""), str(记录.get("message_id") or ""))
    if not all(键):
        return False
    参数 = 图片归档待恢复.setdefault(键, {"record": copy.deepcopy(记录), "config": _配置快照(配置)})
    旧列表 = dict(_媒体项目列表(参数["record"].get("media")))
    参数["record"]["media"] = 消息记录._合并媒体记录(参数["record"]["media"], 记录["media"])
    for i, 项 in _媒体项目列表(参数["record"]["media"]):
        if 项.get("src") != (旧列表.get(i) or {}).get("src"):
            参数.get("progress", {}).get(i, {}).pop("source_failures", None)
    _排空队列()
    return True


def 启动图片归档任务(配置: Any = None) -> None:
    global 图片归档接收开启
    图片归档接收开启 = True
    # 逐项接管；旧上传未知状态留在原索引，安全兄弟项改走夸克。
    旧模块 = sys.modules.get("功能文件.管理功能.网盘功能.蓝奏云图片归档")
    for 旧参数 in list(getattr(旧模块, "图片归档待恢复", {}).values()):
        if 旧参数.get("_quark_handoff"):
            continue
        记录 = 旧参数["record"]
        键 = (str(记录.get("_session") or ""), str(记录.get("message_id") or ""))
        if not 安排归档消息图片(配置 or 旧参数.get("config"), 记录):
            continue
        参数 = 图片归档待恢复[键]
        进度 = 旧参数.get("progress", {})
        if any(k in 进度 for k in ("uid", "remote_task", "archive", "file_id", "upload_submitted")):
            进度 = {0: 进度}
        参数["legacy_module"] = 旧模块
        参数["legacy_config"] = 旧参数.get("config")
        for 索引, 项 in 进度.items():
            if isinstance(项, dict) and (项.get("upload_submitted") or _旧项目可完成(项)):
                参数.setdefault("progress", {})[int(索引)] = {"_legacy": 项}
        # 原队列保留未知提交资料，但明确消费接管，后续重载不重新上传。
        旧参数["_quark_handoff"] = True
    for 参数 in 图片归档待恢复.values():
        if 配置 is not None:
            参数["config"] = _配置快照(配置)
    _排空队列()


async def 停止图片归档任务() -> None:
    global 图片归档接收开启, _唤醒
    图片归档接收开启 = False
    if _唤醒 is not None:
        _唤醒.cancel()
        _唤醒 = None
    任务 = list(图片归档任务)
    for 项 in 任务:
        项.cancel()
    if 任务:
        await asyncio.gather(*任务, return_exceptions=True)
    图片归档任务.clear()


def 构造网页媒体字段(媒体: Any, 会话标识: str, 类型: str, 消息ID: str) -> dict[str, Any] | None:
    if not isinstance(媒体, dict):
        return None
    结果 = copy.deepcopy(媒体)
    夸克 = 结果.pop("_quark_archives", {})
    蓝奏 = 结果.pop("_lanzou_archives", {})
    夸克 = 夸克 if isinstance(夸克, dict) else {}
    蓝奏 = 蓝奏 if isinstance(蓝奏, dict) else {}
    旧 = 结果.pop("_lanzou_archive", None)
    if isinstance(旧, dict):
        蓝奏.setdefault("0", 旧)
    for 索引, 项 in _媒体项目列表(结果, 可下载=False):
        归档 = 夸克.get(str(索引)) or 蓝奏.get(str(索引))
        if not isinstance(归档, dict):
            continue
        路由 = "quark-media" if str(索引) in 夸克 else "lanzou-image"
        项.update(src="/api/message/" + 路由 + "?" + urlencode({"chat_id": 会话标识, "chat_type": 类型,
                    "message_id": 消息ID, "media_index": 索引}), archived=True,
                 content_type=str(归档.get("content_type") or ""), size=int(归档.get("size") or 0))
        for k in ("url", "download_url", "_quark_archives", "_lanzou_archives", "_lanzou_archive"):
            项.pop(k, None)
        if 索引 == 0:
            for k in ("src", "archived", "content_type", "size"):
                结果[k] = 项[k]
            结果.pop("url", None)
            结果.pop("download_url", None)
    return 结果


@asynccontextmanager
async def 打开归档媒体(配置: Any, 归档: dict[str, Any], *, 范围: str = "", 保存直链: Any = None) -> AsyncIterator[aiohttp.ClientResponse]:
    from .夸克网盘 import 夸克网盘客户端
    Cookie = await asyncio.to_thread(_读取绑定账号, _配置快照(配置), str(归档.get("account_id") or ""))
    try:
        年龄 = time.time() - float(归档.get("direct_url_cached_at") or 0)
    except (ValueError, TypeError):
        年龄 = -1
    缓存 = str(归档.get("direct_url") or "") if 0 <= 年龄 < 直链复用秒 else ""
    async with _新建会话() as 会话:
        响应 = None
        获取时间 = 0.0
        if 缓存:
            try:
                响应 = await _请求原字节(会话, 缓存, 范围=范围, Cookie=Cookie)
                if 响应.status not in {200, 206}:
                    响应.release()
                    响应 = None
            except asyncio.CancelledError:
                raise
            except Exception:
                响应 = None
        if 响应 is None:
            async with 夸克网盘客户端(Cookie) as 客户端:
                地址 = await 客户端.获取文件下载地址(str(归档.get("file_id") or ""))
                Cookie = 客户端.cookie
            获取时间 = time.time()
            响应 = await _请求原字节(会话, 地址, 范围=范围, Cookie=Cookie)
        else:
            地址 = 缓存
        try:
            if 响应.status not in {200, 206}:
                raise 媒体归档错误("download_status", 响应.status)
            yield 响应
        finally:
            响应.release()
        if 获取时间 and callable(保存直链):
            try:
                await 保存直链(地址, 获取时间)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("夸克媒体直链缓存未更新：错误类型=%s", type(exc).__name__)


async def 读取归档媒体块(上游: aiohttp.ClientResponse, 归档: dict[str, Any], 起点: int, 终点: int) -> AsyncIterator[bytes]:
    余量 = 终点 - 起点 + 1
    跳过 = 起点
    if 上游.status == 206:
        范围 = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", 上游.headers.get("Content-Range", ""))
        if not 范围 or tuple(map(int, 范围.groups())) != (起点, 终点, int(归档["size"])):
            raise 媒体归档错误("archive_range_mismatch", 206)
        跳过 = 0
    async for 块 in 上游.content.iter_chunked(64 * 1024):
        if 跳过:
            长度 = min(跳过, len(块))
            跳过 -= 长度
            块 = 块[长度:]
        块 = 块[:余量]
        if 块:
            余量 -= len(块)
            yield 块
        if not 余量:
            return
    raise 媒体归档错误("archive_truncated")
