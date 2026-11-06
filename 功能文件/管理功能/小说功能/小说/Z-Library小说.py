"""Z-Library 搜索、账号创建与公开书籍下载。"""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import hashlib
import json
import re
import secrets
import time
import uuid
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import quote, unquote, urljoin, urlsplit

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.基础功能 import 权限工具, 运行状态数据库
from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID


ZLibrary允许域名 = {
    "z-library.sk",
    "zh.z-library.sk",
    "libb.la",
    "zh.libb.la",
    "zh.zlib.bz",
    "zlib.bz",
}
ZLibrary链接正则 = re.compile(
    r"https?://(?:(?:zh\.)?z-library\.sk|(?:zh\.)?libb\.la|(?:zh\.)?zlib\.bz)/book/[^\s<>\"']+",
    re.IGNORECASE,
)
ZLibrary请求超时秒数 = 35
ZLibrary详情最大字节数 = 4 * 1024 * 1024
ZLibrary文件最大字节数 = 120 * 1024 * 1024
ZLibrary转换响应最大字节数 = 2 * 1024 * 1024
ZLibrary转换等待秒数 = 300
ZLibrary转换轮询间隔秒数 = 10
ZLibrary搜索域名 = "https://zlib.bz"
ZLibrary邮箱API地址 = "https://maliapi.215.im/v1"
ZLibrary注册站点地址 = "https://zlib.bz"
ZLibrary账号命名空间 = "zlibrary_accounts"
ZLibrary注册任务集合: set[asyncio.Task] = globals().get("ZLibrary注册任务集合", set())
ZLibrary自动注册任务: dict[str, asyncio.Task] = globals().get("ZLibrary自动注册任务", {})
ZLibrary注册失败冷却: dict[str, float] = globals().get("ZLibrary注册失败冷却", {})
ZLibrary账号资料缓存: dict[str, dict[str, Any]] = globals().get("ZLibrary账号资料缓存", {})
# 切换已验证直连入口时丢弃旧失败冷却，不沿用旧域名的网络故障。
if globals().get("ZLibrary资料请求入口") != ZLibrary搜索域名:
    ZLibrary账号资料缓存 = {键: 项 for 键, 项 in ZLibrary账号资料缓存.items() if not 项.get("failed")}
ZLibrary资料请求入口 = ZLibrary搜索域名
ZLibrary账号资料任务: dict[str, asyncio.Task] = globals().get("ZLibrary账号资料任务", {})
ZLibrary活动注册记录: set[tuple[str, str]] = globals().get("ZLibrary活动注册记录", set())
ZLibrary账号资料并发 = globals().get("ZLibrary账号资料并发") or asyncio.Semaphore(2)
ZLibrary额度重查冷却: dict[str, float] = globals().get("ZLibrary额度重查冷却", {})
ZLibrary额度恢复检查间隔 = 300
ZLibrary账号管理锁: dict[str, asyncio.Lock] = globals().get("ZLibrary账号管理锁", {})
_ZLibrary账号停止 = False
ZLibrary下载失败提示 = "下载失败 请重试"
ZLibrary文件发送失败提示 = "文件发送失败，请稍后再试"


class _ZLibrary站点错误(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        诊断原因: str = "site_error",
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.诊断原因 = 诊断原因
        self.http_status = http_status


class _ZLibrary正文HTML解析器(HTMLParser):
    """清理详情页与搜索结果里的 HTML 文本片段。"""

    _块元素 = {
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "li",
        "p",
        "section",
        "tr",
    }
    _跳过元素 = {"head", "script", "style", "svg", "nav", "aside"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.片段: list[str] = []
        self.跳过深度 = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        小写标签 = tag.lower()
        if 小写标签 in self._跳过元素:
            self.跳过深度 += 1
            return
        if not self.跳过深度 and 小写标签 in self._块元素:
            self.片段.append("\n")

    def handle_endtag(self, tag: str) -> None:
        小写标签 = tag.lower()
        if 小写标签 in self._跳过元素 and self.跳过深度:
            self.跳过深度 -= 1
            return
        if not self.跳过深度 and 小写标签 in self._块元素:
            self.片段.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.跳过深度:
            self.片段.append(data)


def _清理正文(值: Any) -> str:
    if 值 is None:
        return ""
    文本 = html.unescape(str(值)).replace("\r\n", "\n").replace("\r", "\n")
    if "<" in 文本 and ">" in 文本:
        解析器 = _ZLibrary正文HTML解析器()
        try:
            解析器.feed(文本)
            文本 = "".join(解析器.片段)
        except Exception:
            文本 = re.sub(r"<[^>]+>", "", 文本)
    行列表: list[str] = []
    for 行 in 文本.split("\n"):
        行 = re.sub(r"[ \t\u3000]+", " ", 行).strip()
        if 行列表 and not 行 and not 行列表[-1]:
            continue
        if 行:
            行列表.append(行)
        elif 行列表:
            行列表.append("")
    while 行列表 and not 行列表[-1]:
        行列表.pop()
    return "\n".join(行列表).strip()


def _遍历文本候选(值: Any, 结果: list[str], 已见: set[int], 深度: int = 0) -> None:
    if 值 is None or 深度 > 7:
        return
    if isinstance(值, str):
        结果.append(值)
        return
    if isinstance(值, dict):
        for 子值 in 值.values():
            _遍历文本候选(子值, 结果, 已见, 深度 + 1)
        return
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            _遍历文本候选(子值, 结果, 已见, 深度 + 1)
        return
    标识 = id(值)
    if 标识 in 已见:
        return
    已见.add(标识)
    for 字段名 in (
        "message_str",
        "raw_message",
        "message",
        "raw_data",
        "data",
        "content",
        "text",
    ):
        try:
            _遍历文本候选(getattr(值, 字段名, None), 结果, 已见, 深度 + 1)
        except Exception:
            continue


def 提取ZLibrary来源(event: Any, 命令文本: Any) -> str | None:
    候选: list[str] = []
    _遍历文本候选(命令文本, 候选, set())
    _遍历文本候选(event, 候选, set())
    for 文本 in 候选:
        文本 = html.unescape(str(文本)).replace("\\/", "/")
        for 匹配 in ZLibrary链接正则.finditer(文本):
            链接 = 匹配.group(0).rstrip("`)]}>，。；;！!）")
            if _是ZLibrary链接(链接):
                return 链接
        try:
            解码文本 = unquote(文本)
        except Exception:
            解码文本 = 文本
        for 匹配 in ZLibrary链接正则.finditer(解码文本):
            链接 = 匹配.group(0).rstrip("`)]}>，。；;！!）")
            if _是ZLibrary链接(链接):
                return 链接
    return None


def _是ZLibrary链接(值: str) -> bool:
    try:
        地址 = urlsplit(str(值).strip())
    except ValueError:
        return False
    主机 = (地址.hostname or "").lower().strip(".")
    路径 = [项目 for 项目 in (地址.path or "").split("/") if 项目]
    return 主机 in ZLibrary允许域名 and len(路径) >= 2 and 路径[0].lower() == "book"


def _是ZLibrary站点HTTPS地址(值: str) -> bool:
    try:
        地址 = urlsplit(str(值).strip())
    except ValueError:
        return False
    return 地址.scheme.lower() == "https" and (地址.hostname or "").lower().strip(".") in ZLibrary允许域名


class _ZLibrary注册错误(RuntimeError):
    def __init__(self, 阶段: str, 状态: str, http状态: int = 0):
        self.阶段, self.状态, self.http状态 = 阶段, 状态, http状态
        super().__init__(f"{阶段}:{状态}:{http状态}")


async def _请求ZLibrary注册接口(session, 方法, 地址, 阶段, **参数):
    try:
        async with session.request(方法, 地址, allow_redirects=False, **参数) as response:
            原始 = bytearray()
            async for 数据块 in response.content.iter_chunked(65536):
                原始.extend(数据块)
                if len(原始) > 2 * 1024 * 1024:
                    raise _ZLibrary注册错误(阶段, "response_too_large", response.status)
            if not 200 <= response.status < 300:
                raise _ZLibrary注册错误(阶段, "http_error", response.status)
            try:
                数据 = json.loads(原始)
            except (ValueError, UnicodeError) as exc:
                raise _ZLibrary注册错误(阶段, "invalid_json", response.status) from exc
            if not isinstance(数据, dict) or any(数据.get(字段) for 字段 in ("error", "errors", "_error")):
                raise _ZLibrary注册错误(阶段, "business_error", response.status)
            return 数据
    except _ZLibrary注册错误:
        raise
    except (aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError) as exc:
        raise _ZLibrary注册错误(阶段, "tls_error") from exc
    except aiohttp.ClientConnectorDNSError as exc:
        raise _ZLibrary注册错误(阶段, "dns_error") from exc
    except (aiohttp.ClientConnectionError, TimeoutError) as exc:
        状态 = "connection_timeout" if isinstance(exc, aiohttp.ConnectionTimeoutError) else "network_timeout" if isinstance(exc, TimeoutError) else "connection_error"
        raise _ZLibrary注册错误(阶段, 状态) from exc


async def _登录ZLibraryEAPI(session: aiohttp.ClientSession, 账号: dict[str, str]) -> dict[str, Any]:
    """按用户提供的 EAPI 校验账号，只把认证 Cookie 留在本次会话。"""
    数据 = await _请求ZLibrary注册接口(
        session, "POST", ZLibrary搜索域名 + "/eapi/user/login", "login",
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        data={"email": 账号["email"], "password": 账号["password"]},
    )
    用户 = 数据.get("user")
    if 数据.get("success") != 1 or not isinstance(用户, dict):
        raise _ZLibrary注册错误("login", "unconfirmed")
    用户编号 = str(用户.get("id") or "")
    密钥 = str(用户.get("remix_userkey") or "")
    if not re.fullmatch(r"[0-9]{1,30}", 用户编号) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", 密钥):
        raise _ZLibrary注册错误("login", "missing_session")
    session.cookie_jar.update_cookies(
        {"remix_userid": 用户编号, "remix_userkey": 密钥},
        response_url=aiohttp.client_reqrep.URL(ZLibrary搜索域名),
    )
    return 用户


def _提取ZLibrary验证码(
    邮件: dict, 地址: str, *, 诊断: dict[str, int] | None = None,
) -> str | None:
    def 拒绝(原因: str) -> None:
        if 诊断 is not None:
            诊断[原因] = 诊断.get(原因, 0) + 1

    收件人列表 = 邮件.get("to")
    if not isinstance(收件人列表, list) or not any(
        isinstance(收件人, dict)
        and str(收件人.get("address", "")).lower() == 地址.lower()
        for 收件人 in 收件人列表
    ):
        return 拒绝("recipient_mismatch")
    验证码 = 邮件.get("verificationCode")
    if isinstance(验证码, str) and re.fullmatch(r"[0-9]{4}", 验证码):
        return 验证码
    片段 = [str(邮件.get(字段) or "")[:256000] for 字段 in ("subject", "intro", "text")]
    正文 = 邮件.get("html")
    if isinstance(正文, str):
        片段.append(正文[:256000])
    elif isinstance(正文, list):
        片段.extend(项目[:256000] for 项目 in 正文 if isinstance(项目, str))
    文本 = html.unescape(" ".join(片段))
    文本 = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", 文本)
    文本 = re.sub(r"(?s)<[^>]*>", " ", 文本)
    文本 = re.sub(r"\s+", " ", 文本)
    验证词 = r"(?:verification|verify|confirmation|confirm|security|one[\s-]?time|otp|验证码|校验码|確認碼|确认码|驗證碼)"
    匹配 = re.search(
        rf"{验证词}[^0-9]{{0,80}}(?<![0-9])([0-9]{{4}})(?![0-9])|(?<![0-9])([0-9]{{4}})(?![0-9])[^0-9]{{0,80}}{验证词}",
        文本,
        re.I,
    )
    return (匹配.group(1) or 匹配.group(2)) if 匹配 else 拒绝("code_missing")


def _检查ZLibrary业务回复(数据: dict, 阶段: str) -> dict:
    回复 = 数据.get("response")
    if not isinstance(回复, dict) or not 回复:
        raise _ZLibrary注册错误(阶段, "unconfirmed")
    if any(回复.get(字段) for 字段 in ("validationError", "error", "errors", "_error")):
        raise _ZLibrary注册错误(阶段, "business_error")
    return 回复


def _ZLibrary跳转已确认(回复: dict, 登录: bool = False) -> bool:
    字段 = "priorityRedirectUrl" if 登录 else "forceRedirection"
    return bool(
        (isinstance(回复.get(字段), str) and 回复[字段])
        or (
            isinstance(回复.get("regularDomains"), (list, dict))
            and 回复["regularDomains"]
            and isinstance(回复.get("params"), str)
            and 回复["params"]
        )
    )


async def 自动创建ZLibrary账号(
    api_key: str,
    保存账号,
    rx: str = "215",
    *,
    邮箱地址: str = ZLibrary邮箱API地址,
    站点地址: str = ZLibrary注册站点地址,
    等待秒数: float = 120,
    轮询间隔: float = 5,
) -> str:
    """通过邮箱 API 收码注册，并用独立会话确认登录。"""
    if not api_key.startswith("AC-") or not rx.strip():
        raise _ZLibrary注册错误("config", "invalid_config")
    尝试ID = uuid.uuid4().hex
    密码 = secrets.token_urlsafe(15)
    名称 = "Reader" + secrets.token_hex(4)
    超时 = aiohttp.ClientTimeout(total=25, connect=10)
    邮箱请求头 = {"Accept": "application/json", "User-Agent": "YYDSMailClient/1.0"}
    async with aiohttp.ClientSession(
        timeout=超时,
        headers=邮箱请求头,
        cookie_jar=aiohttp.DummyCookieJar(),
        trust_env=False,
    ) as 邮箱会话:
        创建结果 = await _请求ZLibrary注册接口(
            邮箱会话,
            "POST",
            邮箱地址 + "/accounts",
            "mail_create",
            headers={"X-API-Key": api_key, "Idempotency-Key": 尝试ID},
            json={"localPart": "m" + secrets.token_hex(8)},
        )
        邮箱数据 = 创建结果.get("data")
        if 创建结果.get("success") is not True or not isinstance(邮箱数据, dict):
            raise _ZLibrary注册错误("mail_create", "unconfirmed")
        邮箱 = 邮箱数据.get("address")
        邮箱令牌 = 邮箱数据.get("token")
        邮箱ID = 邮箱数据.get("id")
        if not isinstance(邮箱, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", 邮箱):
            raise _ZLibrary注册错误("mail_create", "invalid_address")
        if not isinstance(邮箱令牌, str) or not 邮箱令牌 or not isinstance(邮箱ID, str) or not 邮箱ID:
            raise _ZLibrary注册错误("mail_create", "missing_mailbox")
        邮箱鉴权头 = {"Authorization": "Bearer " + 邮箱令牌}
        表单 = {
            "email": 邮箱,
            "password": 密码,
            "name": 名称,
            "rx": rx,
            "action": "registration",
            "redirectUrl": "",
        }
        站点请求头 = {
            "Accept": "application/json",
            "Origin": 站点地址,
            "Referer": 站点地址 + "/registration",
            "X-Requested-With": "XMLHttpRequest",
        }
        账号 = {
            "email": 邮箱,
            "password": 密码,
            "name": 名称,
            "status": "pending",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        await 保存账号(尝试ID, dict(账号))
        async with aiohttp.ClientSession(timeout=超时, headers=站点请求头, trust_env=False) as 站点会话:
            发码表单 = aiohttp.FormData()
            for 字段, 值 in 表单.items():
                发码表单.add_field(字段, 值, content_type="text/plain")
            开始时间 = dt.datetime.now(dt.timezone.utc)
            发码结果 = await _请求ZLibrary注册接口(
                站点会话,
                "POST",
                站点地址 + "/papi/user/verification/send-code",
                "send_code",
                data=发码表单,
            )
            if 发码结果.get("success") not in (1, True):
                raise _ZLibrary注册错误("send_code", "unconfirmed")
            验证码 = None
            已检查邮件: set[str] = set()
            邮箱诊断: dict[str, int] = {}
            轮询次数 = 0
            非空轮询次数 = 0
            邮件详情次数 = 0
            try:
                async with asyncio.timeout(等待秒数):
                    while 验证码 is None:
                        收件箱 = await _请求ZLibrary注册接口(
                            邮箱会话,
                            "GET",
                            邮箱地址 + "/inboxes/" + quote(邮箱ID, safe="") + "/messages",
                            "mail_read",
                            headers=邮箱鉴权头,
                            params={"since": 开始时间.isoformat(), "seen": "false", "limit": "200"},
                        )
                        邮件列表 = (
                            收件箱.get("data", {}).get("messages")
                            if isinstance(收件箱.get("data"), dict)
                            else None
                        )
                        if 收件箱.get("success") is not True or not isinstance(邮件列表, list):
                            raise _ZLibrary注册错误("mail_read", "unconfirmed")
                        轮询次数 += 1
                        非空轮询次数 += int(bool(邮件列表))
                        for 邮件摘要 in 邮件列表:
                            if not isinstance(邮件摘要, dict):
                                continue
                            邮件ID = 邮件摘要.get("id")
                            if (
                                not isinstance(邮件ID, str)
                                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", 邮件ID)
                                or 邮件ID in 已检查邮件
                            ):
                                continue
                            邮件详情 = await _请求ZLibrary注册接口(
                                邮箱会话,
                                "GET",
                                邮箱地址 + "/messages/" + quote(邮件ID, safe=""),
                                "mail_read",
                                headers=邮箱鉴权头,
                                params={"address": 邮箱},
                            )
                            邮件 = 邮件详情.get("data")
                            if 邮件详情.get("success") is not True or not isinstance(邮件, dict):
                                raise _ZLibrary注册错误("mail_read", "unconfirmed")
                            邮件详情次数 += 1
                            try:
                                时间戳 = dt.datetime.fromisoformat(
                                    str(邮件.get("createdAt") or 邮件摘要.get("createdAt") or "").replace("Z", "+00:00")
                                )
                            except ValueError:
                                邮箱诊断["timestamp_invalid"] = 邮箱诊断.get("timestamp_invalid", 0) + 1
                                已检查邮件.add(邮件ID)
                                continue
                            if 时间戳.tzinfo is None or 时间戳 < 开始时间:
                                原因 = "timezone_missing" if 时间戳.tzinfo is None else "before_request"
                                邮箱诊断[原因] = 邮箱诊断.get(原因, 0) + 1
                                已检查邮件.add(邮件ID)
                                continue
                            验证码 = _提取ZLibrary验证码(邮件, 邮箱, 诊断=邮箱诊断)
                            if 验证码:
                                break
                            已检查邮件.add(邮件ID)
                        if 验证码 is None:
                            await asyncio.sleep(轮询间隔)
            except TimeoutError as exc:
                logger.warning(
                    "ZLibrary验证码等待超时：polls=%s, nonempty_polls=%s, details=%s, rejected=%s",
                    轮询次数, 非空轮询次数, 邮件详情次数,
                    json.dumps(邮箱诊断, sort_keys=True),
                )
                raise _ZLibrary注册错误("mail_read", "code_timeout") from exc
            注册数据 = await _请求ZLibrary注册接口(
                站点会话,
                "POST",
                站点地址 + "/rpc.php",
                "registration",
                data={
                    **表单,
                    "verifyCode": 验证码,
                    "isModal": "true",
                    "gg_json_mode": "1",
                },
            )
            注册回复 = _检查ZLibrary业务回复(注册数据, "registration")
            if not _ZLibrary跳转已确认(注册回复):
                raise _ZLibrary注册错误("registration", "unconfirmed")
            账号["status"] = "registered"
            await 保存账号(尝试ID, dict(账号))
        async with aiohttp.ClientSession(timeout=超时, trust_env=False) as 登录会话:
            await _登录ZLibraryEAPI(登录会话, 账号)
        账号["status"] = "logged_in"
        await 保存账号(尝试ID, dict(账号))
    return 尝试ID


async def _等待ZLibrary状态写入(函数, *参数):
    # 线程写入开始后必须等到结果，再清理；避免取消后的迟到 INSERT 复活失败记录。
    任务 = asyncio.create_task(asyncio.to_thread(函数, *参数))
    try:
        return await asyncio.shield(任务)
    except asyncio.CancelledError:
        await 任务
        raise


async def _清理ZLibrary未完成记录(配置: Any) -> None:
    """仅清理已结束的 pending/registered；成功账号与在途任务不动。"""
    作用域, 快照 = _ZLibrary注册配置快照(配置)
    状态 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
    for 标识, 账号 in _解析ZLibrary账号记录(状态):
        if 账号.get("status") not in {"pending", "registered"} or (作用域, 标识) in ZLibrary活动注册记录:
            continue
        await _等待ZLibrary状态写入(运行状态数据库.比较并更新运行状态值, 快照, ZLibrary账号命名空间,
                            {标识: 状态[标识]}, {}, [标识])


async def _注册并保存ZLibrary账号(配置: Any) -> dict[str, str] | None:
    作用域, 配置 = _ZLibrary注册配置快照(配置)
    分类 = 运行状态数据库.读取配置字段(配置, "zlibrary_account_settings") or 配置
    api_key = str(运行状态数据库.读取配置字段(分类, "zlibrary_mail_api_key") or "").strip()
    rx = str(运行状态数据库.读取配置字段(分类, "zlibrary_registration_rx") or "215").strip()
    if not api_key:
        return None
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 配置) != "正常":
        return None
    本次账号 = None
    本次记录 = {}
    async def 保存(标识: str, 数据: dict[str, Any]) -> None:
        nonlocal 本次账号
        原始 = json.dumps(数据, ensure_ascii=False)
        本次记录[标识] = 原始
        ZLibrary活动注册记录.add((作用域, 标识))
        await _等待ZLibrary状态写入(运行状态数据库.写入运行状态值, 配置, ZLibrary账号命名空间, 标识, 原始)
        if 数据.get("status") == "logged_in":
            本次账号 = {"email": 数据["email"], "password": 数据["password"]}
    try:
        await 自动创建ZLibrary账号(api_key, 保存, rx)
    except _ZLibrary注册错误 as exc:
        logger.warning("ZLibrary创建账号失败：阶段=%s 状态=%s HTTP=%s", exc.阶段, exc.状态, exc.http状态)
        return None
    except Exception as exc:
        logger.warning("ZLibrary创建账号失败：类型=%s", type(exc).__name__)
        return None
    finally:
        try:
            if 本次记录:
                当前 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 配置, ZLibrary账号命名空间)
                for 标识, 原始 in 本次记录.items():
                    原账号 = json.loads(原始)
                    try:
                        未完成 = json.loads(当前.get(标识, "null"))
                    except (ValueError, TypeError):
                        continue
                    if (isinstance(未完成, dict) and 未完成.get("status") in {"pending", "registered"}
                            and all(未完成.get(k) == 原账号.get(k) for k in ("email", "password"))):
                        await _等待ZLibrary状态写入(运行状态数据库.比较并更新运行状态值, 配置, ZLibrary账号命名空间,
                                                {标识: 当前[标识]}, {}, [标识])
        except Exception as exc:
            logger.warning("ZLibrary失败注册记录清理失败：错误类型=%s", type(exc).__name__)
        finally:
            for 标识 in 本次记录:
                ZLibrary活动注册记录.discard((作用域, 标识))
    return 本次账号


async def 获取ZLibrary搜索账号(配置: Any, *, 自动注册: bool = True) -> dict[str, str] | None:
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 配置) != "正常":
        return None
    try:
        await _清理ZLibrary未完成记录(配置)
        状态列表 = await asyncio.to_thread(
            运行状态数据库.读取运行状态命名空间,
            配置,
            ZLibrary账号命名空间,
        )
    except Exception as exc:
        logger.warning("ZLibrary搜索账号读取失败：错误类型=%s", type(exc).__name__)
        return None
    记录 = _解析ZLibrary账号记录(状态列表)
    已验证 = [项 for 项 in 记录 if 项[1].get("status") == "logged_in"]
    if not 已验证:
        return await _确保ZLibrary自动账号(配置) if 自动注册 else None
    作用域, _ = _ZLibrary注册配置快照(配置)
    额度状态 = _解析ZLibrary额度状态(状态列表)
    管理状态 = _解析ZLibrary管理状态(状态列表)
    for 标识, 账号 in sorted(已验证, key=lambda 项: (_ZLibrary账号资料键(作用域, *项) == 管理状态["preferred"], _ZLibrary账号排序键(项)), reverse=True):
        键 = _ZLibrary账号资料键(作用域, 标识, 账号)
        if 管理状态["accounts"].get(键, {}).get("enabled") is False:
            continue
        额度 = 额度状态.get(键, {})
        if 额度.get("status") == "quota_paused":
            if not _ZLibrary额度可重查(键, 额度):
                continue
            ZLibrary额度重查冷却[键] = time.monotonic() + ZLibrary额度恢复检查间隔
            结果 = await 获取ZLibrary账号摘要(配置, 刷新=True, 账号标识=键)
            剩余 = 结果.get("profile", {}).get("downloads_remaining")
            if not isinstance(剩余, int) or 剩余 <= 0:
                continue
        return {"email": 账号["email"], "password": 账号["password"]}
    # 已有账号全部暂停时，保留等待恢复；不得退到自动注册。
    return None


def _解析ZLibrary账号记录(状态列表: dict[str, str]) -> list[tuple[str, dict[str, Any]]]:
    记录 = []
    for 标识, 原始值 in 状态列表.items():
        try:
            账号 = json.loads(原始值)
        except (TypeError, ValueError):
            continue
        if not isinstance(账号, dict):
            continue
        邮箱, 密码 = 账号.get("email"), 账号.get("password")
        if not isinstance(邮箱, str) or not 邮箱 or not isinstance(密码, str) or not 密码:
            continue
        记录.append((标识, 账号))
    return 记录


def _解析ZLibrary管理状态(状态: dict[str, str]) -> dict[str, Any]:
    结果: dict[str, Any] = {"accounts": {}, "preferred": ""}
    for 键, 原始 in 状态.items():
        if 键 != "__selection__" and not re.fullmatch(r"__meta_[a-f0-9]{64}", 键):
            continue
        try:
            值 = json.loads(原始)
        except (ValueError, TypeError):
            continue
        if not isinstance(值, dict):
            continue
        if 键 == "__selection__":
            首选 = str(值.get("preferred") or "")
            结果["preferred"] = 首选 if re.fullmatch(r"[a-f0-9]{64}", 首选) else ""
        else:
            结果["accounts"][键[7:]] = {
                "enabled": 值.get("enabled") is not False,
                "group": str(值.get("group") or "")[:40],
                "note": str(值.get("note") or "")[:200],
            }
    return 结果


def _ZLibrary账号排序键(项):
    return str(项[1].get("created_at") or ""), 项[1]["email"], 项[1]["password"]


def _选取ZLibrary当前账号(记录: list[tuple[str, dict[str, Any]]], 作用域: str = "", 额度状态: dict | None = None, 管理状态: dict | None = None):
    管理状态 = 管理状态 or {"accounts": {}, "preferred": ""}
    候选 = [项 for 项 in 记录 if 项[1].get("status") == "logged_in"
            and (额度状态 or {}).get(_ZLibrary账号资料键(作用域, *项), {}).get("status") != "quota_paused"
            and 管理状态["accounts"].get(_ZLibrary账号资料键(作用域, *项), {}).get("enabled") is not False]
    return max(候选, key=lambda 项: (_ZLibrary账号资料键(作用域, *项) == 管理状态["preferred"], _ZLibrary账号排序键(项))) if 候选 else None


def _解析ZLibrary额度状态(状态列表: dict[str, str]) -> dict[str, dict[str, Any]]:
    结果 = {}
    for 键, 原始 in 状态列表.items():
        if not re.fullmatch(r"__quota_[a-f0-9]{64}", 键):
            continue
        try:
            值 = json.loads(原始)
        except (ValueError, TypeError):
            continue
        if isinstance(值, dict) and 值.get("status") in {"quota_paused", "quota_active"}:
            结果[键[8:]] = 值
    return 结果


def _ZLibrary额度可重查(键: str, 额度: dict[str, Any]) -> bool:
    检查 = _ZLibrary资料整数(额度.get("checked_at")) or 0
    今日 = dt.datetime.now().astimezone().date()
    检查日期 = dt.datetime.fromtimestamp(检查).astimezone().date()
    return (time.monotonic() >= ZLibrary额度重查冷却.get(键, 0)
            and (time.time() - 检查 >= ZLibrary额度恢复检查间隔 or 今日 != 检查日期))


async def _保存ZLibrary额度状态(配置: Any, 键: str, 资料: dict[str, Any]) -> None:
    剩余 = 资料.get("downloads_remaining")
    if not isinstance(剩余, int) or isinstance(剩余, bool):
        return
    # 独立状态键，绝不覆盖账号凭据、注册状态或删除耗尽账号。
    状态 = {"status": "quota_paused" if 剩余 == 0 else "quota_active",
            "remaining": 剩余, "checked_at": int(time.time())}
    await asyncio.to_thread(运行状态数据库.写入运行状态值, 配置, ZLibrary账号命名空间,
                            "__quota_" + 键, json.dumps(状态))
    if 剩余 > 0:
        ZLibrary额度重查冷却.pop(键, None)


async def 获取ZLibrary下载账号(配置: Any) -> dict[str, str]:
    # 每次下载前取得官方额度，不以本地日期推断已经恢复。
    作用域, 快照 = _ZLibrary注册配置快照(配置)
    初始状态 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
    检查上限 = max(1, sum(账号.get("status") == "logged_in" for _, 账号 in _解析ZLibrary账号记录(初始状态)))
    for _ in range(检查上限):
        账号 = await 获取ZLibrary搜索账号(快照)
        if not 账号:
            raise _ZLibrary站点错误("账号额度暂不可用", 诊断原因="quota_paused")
        状态 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
        项 = next((项 for 项 in _解析ZLibrary账号记录(状态) if 项[1].get("status") == "logged_in"
                  and 项[1]["email"] == 账号["email"] and 项[1]["password"] == 账号["password"]), None)
        if 项 is None:
            raise _ZLibrary站点错误("账号已变化", 诊断原因="account_changed")
        键 = _ZLibrary账号资料键(作用域, *项)
        结果 = await 获取ZLibrary账号摘要(快照, 刷新=True, 账号标识=键)
        资料 = 结果.get("profile", {})
        剩余 = 资料.get("downloads_remaining")
        if 资料.get("available") is not True or not isinstance(剩余, int):
            raise _ZLibrary站点错误("账号额度未确认", 诊断原因="quota_unknown")
        if 结果.get("account", {}).get("enabled") is False:
            continue
        if 剩余 > 0:
            return 账号
        # 精确零额度已持久化暂停，下一轮只检查其他已有账号。
    raise _ZLibrary站点错误("账号额度暂不可用", 诊断原因="quota_paused")


async def _刷新ZLibrary下载后额度(配置: Any, 账号: dict[str, str]) -> None:
    try:
        作用域, 快照 = _ZLibrary注册配置快照(配置)
        状态 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
        项 = next((项 for 项 in _解析ZLibrary账号记录(状态) if 项[1].get("email") == 账号["email"] and 项[1].get("password") == 账号["password"]), None)
        if 项:
            await 获取ZLibrary账号摘要(快照, 刷新=True, 账号标识=_ZLibrary账号资料键(作用域, *项))
    except Exception as exc:
        logger.warning("ZLibrary下载后额度查询失败：错误类型=%s", type(exc).__name__)


def _ZLibrary资料整数(值: Any) -> int | None:
    if isinstance(值, bool) or not re.fullmatch(r"[0-9]{1,10}", str(值)):
        return None
    return int(值)


def _ZLibrary资料布尔(值: Any) -> bool | None:
    if 值 in (True, 1, "1"):
        return True
    if 值 in (False, 0, "0"):
        return False
    return None


def _投影ZLibrary账号资料(用户: dict[str, Any]) -> dict[str, Any]:
    已用 = _ZLibrary资料整数(用户.get("downloads_today"))
    上限 = _ZLibrary资料整数(用户.get("downloads_limit"))
    return {
        "available": True, "checked_at": int(time.time()),
        "name": str(用户.get("name") or "")[:120],
        "downloads_today": 已用, "downloads_limit": 上限,
        "downloads_remaining": max(0, 上限 - 已用) if 已用 is not None and 上限 is not None else None,
        "is_vip": _ZLibrary资料布尔(用户.get("isPremium")),
        "email_confirmed": _ZLibrary资料布尔(用户.get("confirmed")),
        # 实测 profile 未提供权限清单；不能由 VIP 或额度猜测管理员等权限。
        "permissions": None,
    }


def _ZLibrary账号资料键(作用域: str, 标识: str, 账号: dict[str, Any]) -> str:
    凭据摘要 = hashlib.sha256((账号["email"] + "\x00" + 账号["password"]).encode()).hexdigest()
    return hashlib.sha256((作用域 + "\x00" + 标识 + "\x00" + 凭据摘要).encode()).hexdigest()


def _ZLibrary账号安全摘要(作用域: str, 标识: str, 账号: dict[str, Any], 当前标识: str, 额度状态: dict | None = None, 管理状态: dict | None = None) -> dict[str, Any]:
    管理状态 = 管理状态 or {"accounts": {}, "preferred": ""}
    键 = _ZLibrary账号资料键(作用域, 标识, 账号)
    缓存 = ZLibrary账号资料缓存.get(键)
    return {
        "id": 键, "name": str(账号.get("name") or "")[:120],
        "email": 账号["email"],
        "enabled": 管理状态["accounts"].get(键, {}).get("enabled") is not False,
        "group": 管理状态["accounts"].get(键, {}).get("group", ""),
        "note": 管理状态["accounts"].get(键, {}).get("note", ""),
        "is_preferred": 键 == 管理状态["preferred"],
        "created_at": str(账号.get("created_at") or "")[:80],
        "is_current": 标识 == 当前标识,
        "quota_paused": (额度状态 or {}).get(键, {}).get("status") == "quota_paused",
        "status": "logged_in" if 账号.get("status") == "logged_in" else "pending",
        "profile": dict(缓存["profile"]) if 缓存 and 缓存["expires"] > time.monotonic() else None,
    }


async def 获取ZLibrary账号列表(配置: Any) -> dict[str, Any]:
    """读取本机器人账号表；额度独立按行补查，列表不等待远端。"""
    作用域, 快照 = _ZLibrary注册配置快照(配置)
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 快照) != "正常":
        return {"accounts": [], "message": "数据库未连接，无法读取账号"}
    await _清理ZLibrary未完成记录(快照)
    状态 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
    记录 = [项 for 项 in _解析ZLibrary账号记录(状态) if 项[1].get("status") == "logged_in"]
    额度状态 = _解析ZLibrary额度状态(状态)
    管理状态 = _解析ZLibrary管理状态(状态)
    当前 = _选取ZLibrary当前账号(记录, 作用域, 额度状态, 管理状态)
    当前标识 = 当前[0] if 当前 else ""
    记录.sort(key=lambda 项: str(项[1].get("created_at") or ""), reverse=True)
    return {"accounts": [_ZLibrary账号安全摘要(作用域, 标识, 账号, 当前标识, 额度状态, 管理状态) for 标识, 账号 in 记录],
            "groups": sorted({管理状态["accounts"].get(_ZLibrary账号资料键(作用域, *项), {}).get("group", "") for 项 in 记录} - {""}),
            "preferred_account_id": 管理状态["preferred"]}


async def _读取ZLibrary账号资料(账号: dict[str, Any]) -> dict[str, Any]:
    """同一账号重连一次；登录已给完整资料时不再追加冗余 GET。"""
    async with _创建ZLibrary会话() as session:
        for 尝试 in range(2):
            try:
                登录用户 = await _登录ZLibraryEAPI(session, 账号)
                break
            except _ZLibrary注册错误 as exc:
                # 只重试尚未建立连接的登录；认证、业务、TLS 和已发送的未知结果不重放。
                可重试 = isinstance(exc.__cause__, (aiohttp.ClientConnectorError, aiohttp.ConnectionTimeoutError))
                if 尝试 or exc.状态 in {"tls_error", "http_error", "business_error", "unconfirmed"} or not 可重试:
                    raise
                await asyncio.sleep(0.5)
        if 登录用户.get("email") and str(登录用户["email"]).casefold() != 账号["email"].casefold():
            raise _ZLibrary注册错误("login", "identity_unconfirmed")
        完整字段 = ("downloads_today", "downloads_limit", "isPremium", "confirmed")
        登录资料 = _投影ZLibrary账号资料(登录用户)
        if all(k in 登录用户 for k in 完整字段) and 登录资料["downloads_remaining"] is not None:
            return 登录资料
        for 尝试 in range(2):
            try:
                数据 = await _请求ZLibrary注册接口(session, "GET", ZLibrary搜索域名 + "/eapi/user/profile", "profile")
                break
            except _ZLibrary注册错误 as exc:
                if 尝试 or exc.状态 not in {"connection_timeout", "network_timeout", "connection_error", "dns_error"}:
                    raise
                await asyncio.sleep(0.5)
        用户 = 数据.get("user")
        if (数据.get("success") != 1 or not isinstance(用户, dict)
                or str(用户.get("id")) != str(登录用户.get("id"))
                or (用户.get("email") and str(用户["email"]).casefold() != 账号["email"].casefold())):
            raise _ZLibrary注册错误("profile", "identity_unconfirmed")
        return _投影ZLibrary账号资料(用户)


async def 获取ZLibrary账号摘要(配置: Any, *, 刷新: bool = False, 账号标识: str = "") -> dict[str, Any]:
    """仅查询当前机器人已有账号，绝不触发注册；只返回白名单资料。"""
    作用域, 快照 = _ZLibrary注册配置快照(配置)
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 快照) != "正常":
        return {"configured": False, "message": "数据库未连接，无法读取账号"}
    状态列表 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
    记录 = _解析ZLibrary账号记录(状态列表)
    额度状态 = _解析ZLibrary额度状态(状态列表)
    管理状态 = _解析ZLibrary管理状态(状态列表)
    当前 = _选取ZLibrary当前账号(记录, 作用域, 额度状态, 管理状态)
    if 账号标识:
        if not re.fullmatch(r"[a-f0-9]{64}", 账号标识):
            return {"configured": False, "message": "账号不存在，请刷新列表"}
        当前 = next((项 for 项 in 记录 if _ZLibrary账号资料键(作用域, *项) == 账号标识 and 项[1].get("status") == "logged_in"), None)
    摘要: dict[str, Any] = {
        "configured": 当前 is not None,
        "saved_accounts": sum(账号.get("status") == "logged_in" for _, 账号 in 记录),
        "pending_accounts": sum(账号.get("status") in {"pending", "registered"} for _, 账号 in 记录),
    }
    if 当前 is None:
        return {**摘要, "message": "暂无已验证账号，可发送“测试账号”注册并保存"}
    标识, 账号 = 当前
    邮箱 = 账号["email"]
    键 = _ZLibrary账号资料键(作用域, 标识, 账号)
    当前可用 = _选取ZLibrary当前账号(记录, 作用域, 额度状态, 管理状态)
    摘要["current_account_id"] = _ZLibrary账号资料键(作用域, *当前可用) if 当前可用 else ""
    摘要["account"] = _ZLibrary账号安全摘要(作用域, 标识, 账号, (当前可用 or ("",))[0], 额度状态, 管理状态)
    摘要["account"].pop("profile", None)
    缓存 = ZLibrary账号资料缓存.get(键)
    if 缓存 and 缓存["expires"] > time.monotonic() and (not 刷新 or 缓存["failed"]):
        return {**摘要, "profile": dict(缓存["profile"])}
    if _ZLibrary账号停止:
        return {**摘要, "message": "账号资料服务正在重载"}
    任务 = ZLibrary账号资料任务.get(键)
    if 任务 is None or 任务.done():
        async def 查询():
            # 排队时间不计入网络时限，避免第三个及以后账号尚未开始就超时。
            async with ZLibrary账号资料并发:
                旧缓存 = ZLibrary账号资料缓存.get(键) or {}
                旧资料 = 旧缓存.get("last_success") or (旧缓存.get("profile") if not 旧缓存.get("failed") else None)
                try:
                    async with asyncio.timeout(65):
                        资料 = await _读取ZLibrary账号资料(账号)
                    await _保存ZLibrary额度状态(快照, 键, 资料)
                    失败 = False
                except Exception as exc:
                    阶段 = getattr(exc, "阶段", "profile")
                    分类 = getattr(exc, "状态", "network_timeout" if isinstance(exc, TimeoutError) else "unknown")
                    允许分类 = {"connection_timeout", "network_timeout", "connection_error", "dns_error", "tls_error", "http_error", "identity_unconfirmed", "business_error", "unconfirmed"}
                    分类 = 分类 if 分类 in 允许分类 else "unknown"
                    logger.warning("ZLibrary账号资料查询失败：阶段=%s 状态=%s HTTP=%s 错误类型=%s",
                                   阶段, 分类, getattr(exc, "http状态", 0), type(exc).__name__)
                    提示 = "连接超时，请稍后刷新" if 分类 in {"connection_timeout", "network_timeout"} else "连接失败，请稍后刷新" if 分类 in {"connection_error", "dns_error"} else "账号资料查询失败，请稍后刷新"
                    资料 = {**(旧资料 or {}), "available": False, "message": 提示, "failure_category": 分类,
                            "failure_stage": 阶段, "last_attempt_at": int(time.time()), "stale": bool(旧资料)}
                    失败 = True
                for 旧键, 项 in list(ZLibrary账号资料缓存.items()):
                    if 项["expires"] <= time.monotonic() and time.monotonic() - 项["expires"] > 3600:
                        ZLibrary账号资料缓存.pop(旧键, None)
                ZLibrary账号资料缓存[键] = {"expires": time.monotonic() + 60, "failed": 失败, "profile": 资料,
                                            "last_success": dict(旧资料) if 失败 and 旧资料 else None if 失败 else dict(资料)}
                return 资料
        任务 = asyncio.create_task(查询())
        ZLibrary账号资料任务[键] = 任务
        ZLibrary注册任务集合.add(任务)
        def 收尾(已完成):
            ZLibrary注册任务集合.discard(已完成)
            if ZLibrary账号资料任务.get(键) is 已完成:
                ZLibrary账号资料任务.pop(键, None)
            if not 已完成.cancelled():
                已完成.exception()
        任务.add_done_callback(收尾)
    资料 = await asyncio.shield(任务)
    # 查询期间若新注册、更换或删除当前账号，旧资料不得拼到新账号上。
    新状态 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
    新记录 = _解析ZLibrary账号记录(新状态)
    仍有效 = next((项 for 项 in 新记录 if 项[0] == 标识), None) == 当前 if 账号标识 else _选取ZLibrary当前账号(新记录, 作用域, 额度状态, _解析ZLibrary管理状态(新状态)) == 当前
    if not 仍有效:
        return {"configured": False, "message": "当前账号已变化，请刷新"}
    新额度 = _解析ZLibrary额度状态(新状态)
    新管理 = _解析ZLibrary管理状态(新状态)
    当前可用 = _选取ZLibrary当前账号(新记录, 作用域, 新额度, 新管理)
    摘要["current_account_id"] = _ZLibrary账号资料键(作用域, *当前可用) if 当前可用 else ""
    摘要["account"]["is_current"] = bool(当前可用 and 当前可用[0] == 标识)
    摘要["account"].update(_ZLibrary账号安全摘要(作用域, 标识, 账号, (当前可用 or ("",))[0], 新额度, 新管理))
    摘要["account"].pop("profile", None)
    return {**摘要, "profile": dict(资料)}


async def 管理ZLibrary账号(配置: Any, 数据: dict[str, Any], 授权检查=lambda: True) -> dict[str, Any]:
    """仅操作本机器人已有账号；原值比较防止迟到请求覆盖新凭据。"""
    作用域, 快照 = _ZLibrary注册配置快照(配置)
    操作 = 数据.get("action")
    编号 = 数据.get("ids")
    if (操作 not in {"enable", "disable", "group", "edit", "select", "delete"}
            or not isinstance(编号, list) or not 1 <= len(编号) <= 100
            or any(not isinstance(x, str) or not re.fullmatch(r"[a-f0-9]{64}", x) for x in 编号)):
        raise ValueError("账号操作参数无效")
    编号 = list(dict.fromkeys(编号))
    if 操作 in {"select", "edit"} and len(编号) != 1:
        raise ValueError("请选择一个账号")
    分组, 备注 = 数据.get("group", ""), 数据.get("note", "")
    if not isinstance(分组, str) or len(分组) > 40 or not isinstance(备注, str) or len(备注) > 200:
        raise ValueError("分组或备注过长")
    async with ZLibrary账号管理锁.setdefault(作用域, asyncio.Lock()):
        状态 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
        记录 = {_ZLibrary账号资料键(作用域, *项): 项 for 项 in _解析ZLibrary账号记录(状态)}
        if any(x not in 记录 or 记录[x][1].get("status") != "logged_in" for x in 编号):
            raise ValueError("账号已变化或尚未完成注册，请刷新")
        管理 = _解析ZLibrary管理状态(状态)
        if 操作 == "select":
            if 管理["accounts"].get(编号[0], {}).get("enabled") is False:
                raise ValueError("请先启用账号")
            摘要 = await 获取ZLibrary账号摘要(快照, 刷新=True, 账号标识=编号[0])
            资料 = 摘要.get("profile", {})
            if not 资料.get("available") or not isinstance(资料.get("downloads_remaining"), int) or 资料["downloads_remaining"] <= 0:
                raise ValueError("账号额度未确认或已耗尽，暂不能切换")
        期望, 写入, 删除 = {}, {}, []
        for 键 in 编号:
            原键, _ = 记录[键]
            期望[原键] = 状态[原键]
            元键 = "__meta_" + 键
            期望[元键] = 状态.get(元键)
            元 = dict(管理["accounts"].get(键, {"enabled": True, "group": "", "note": ""}))
            if 操作 == "delete":
                删除.append(原键)
                for 附键 in (元键, "__quota_" + 键):
                    期望[附键] = 状态.get(附键)
                    删除.append(附键)
            elif 操作 in {"enable", "disable", "group", "edit"}:
                if 操作 in {"enable", "disable"}: 元["enabled"] = 操作 == "enable"
                if 操作 in {"group", "edit"}: 元["group"] = 分组.strip()
                if 操作 == "edit": 元["note"] = 备注.strip()
                写入[元键] = json.dumps(元, ensure_ascii=False)
        if 操作 == "select" or (操作 == "delete" and 管理["preferred"] in 编号):
            期望["__selection__"] = 状态.get("__selection__")
            写入["__selection__"] = json.dumps({"preferred": 编号[0] if 操作 == "select" else ""})
        if not 授权检查():
            raise PermissionError("登录已失效")
        成功 = await asyncio.to_thread(运行状态数据库.比较并更新运行状态值, 快照, ZLibrary账号命名空间, 期望, 写入, 删除)
        if not 成功:
            raise ValueError("账号已变化，请刷新后重试")
        for 键 in 编号:
            if 操作 == "delete": ZLibrary账号资料缓存.pop(键, None)
    return {"message": "账号操作已保存", **await 获取ZLibrary账号列表(快照)}


async def 导入ZLibrary账号(配置: Any, 数据: dict[str, Any], 授权检查=lambda: True) -> dict[str, Any]:
    """验证现有邮箱账号后保存；不创建远端账号，不返回凭据。"""
    作用域, 快照 = _ZLibrary注册配置快照(配置)
    输入 = 数据.get("accounts")
    if not isinstance(输入, list) or not 1 <= len(输入) <= 50:
        raise ValueError("每次导入 1～50 个账号")
    账号集 = []
    已见 = set()
    for 项 in 输入:
        if not isinstance(项, dict): raise ValueError("账号格式无效")
        邮箱, 密码 = 项.get("email"), 项.get("password")
        if (not isinstance(邮箱, str) or not re.fullmatch(r"[^\s@]{1,100}@[^\s@]{1,150}", 邮箱.strip())
                or not isinstance(密码, str) or not 1 <= len(密码) <= 512):
            raise ValueError("邮箱或密码格式无效")
        邮箱 = 邮箱.strip().casefold()
        if 邮箱 in 已见: raise ValueError("导入内容包含重复邮箱")
        已见.add(邮箱)
        账号集.append({"email": 邮箱, "password": 密码})
    结果 = []
    async with ZLibrary账号管理锁.setdefault(作用域, asyncio.Lock()):
        初始 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
        async def 验证(账号):
            try:
                async with asyncio.timeout(45), ZLibrary账号资料并发:
                    async with _创建ZLibrary会话() as session:
                        登录 = await _登录ZLibraryEAPI(session, 账号)
                        响应 = await _请求ZLibrary注册接口(session, "GET", ZLibrary搜索域名 + "/eapi/user/profile", "profile")
                用户 = 响应.get("user")
                if (响应.get("success") != 1 or not isinstance(用户, dict) or str(用户.get("id")) != str(登录.get("id"))
                        or not 用户.get("email") or str(用户["email"]).casefold() != 账号["email"]):
                    return None
                return _投影ZLibrary账号资料(用户)
            except Exception as exc:
                logger.warning("ZLibrary导入验证失败：HTTP=%s 错误类型=%s", getattr(exc, "http状态", 0), type(exc).__name__)
                return None
        资料集 = await asyncio.gather(*(验证(x) for x in 账号集))
        for 账号, 资料 in zip(账号集, 资料集):
            行结果 = {"email": 账号["email"], "success": False}
            if 资料 is None:
                结果.append({**行结果, "message": "登录或资料验证失败"}); continue
            if not 授权检查(): raise PermissionError("登录已失效")
            当前 = await asyncio.to_thread(运行状态数据库.读取运行状态命名空间, 快照, ZLibrary账号命名空间)
            旧 = [x for x in _解析ZLibrary账号记录(初始) if x[1]["email"].casefold() == 账号["email"]]
            新 = [x for x in _解析ZLibrary账号记录(当前) if x[1]["email"].casefold() == 账号["email"]]
            if len(旧) > 1 or 新 != 旧 or (旧 and 旧[0][1].get("status") != "logged_in"):
                结果.append({**行结果, "message": "账号已变化或正在注册，请刷新"}); continue
            标识 = 旧[0][0] if 旧 else "import_" + hashlib.sha256(账号["email"].encode()).hexdigest()
            新账号 = {**账号, "name": 资料.get("name", ""), "status": "logged_in",
                      "created_at": 旧[0][1].get("created_at", "") if 旧 else dt.datetime.now(dt.timezone.utc).isoformat()}
            新键 = _ZLibrary账号资料键(作用域, 标识, 新账号)
            期望 = {标识: 初始.get(标识)}
            写入 = {标识: json.dumps(新账号, ensure_ascii=False)}
            删除 = []
            if 旧:
                旧键 = _ZLibrary账号资料键(作用域, *旧[0])
                if 旧键 != 新键:
                    元键 = "__meta_" + 旧键
                    新元键 = "__meta_" + 新键
                    期望.update({元键: 当前.get(元键), 新元键: 当前.get(新元键), "__selection__": 当前.get("__selection__")})
                    写入[新元键] = 当前.get(元键) or json.dumps({"enabled": True})
                    删除.append(元键)
                    if _解析ZLibrary管理状态(当前)["preferred"] == 旧键:
                        写入["__selection__"] = json.dumps({"preferred": 新键})
            if not 授权检查(): raise PermissionError("登录已失效")
            成功 = await asyncio.to_thread(运行状态数据库.比较并更新运行状态值, 快照, ZLibrary账号命名空间, 期望, 写入, 删除)
            if 成功:
                await _保存ZLibrary额度状态(快照, 新键, 资料)
                ZLibrary账号资料缓存[新键] = {"expires": time.monotonic() + 60, "failed": False, "profile": 资料}
            结果.append({**行结果, "success": 成功, "message": "已更新" if 成功 and 旧 else "已导入" if 成功 else "账号已变化，请刷新"})
    return {"results": 结果, "message": f"导入成功 {sum(x['success'] for x in 结果)} / {len(结果)}", **await 获取ZLibrary账号列表(快照)}


def _ZLibrary注册配置快照(配置: Any) -> tuple[str, dict[str, Any]]:
    数据库 = 运行状态数据库.获取数据库配置(配置)
    分类 = 运行状态数据库.读取配置字段(配置, "zlibrary_account_settings") or 配置
    快照 = {
        "database_settings": {
            ("database_name" if 键 == "database" else "database_" + 键): 值
            for 键, 值 in 数据库.items() if 键 != "runtime_state_table"
        },
        "zlibrary_account_settings": {
            "zlibrary_mail_api_key": str(运行状态数据库.读取配置字段(分类, "zlibrary_mail_api_key") or ""),
            "zlibrary_registration_rx": str(运行状态数据库.读取配置字段(分类, "zlibrary_registration_rx") or "215"),
        },
        "__mantou_bot_appid__": 获取当前机器人AppID(配置),
    }
    if not 快照["__mantou_bot_appid__"]:
        raise _ZLibrary注册错误("account", "app_scope")
    作用域 = hashlib.sha256(json.dumps({"database": 快照["database_settings"], "appid": 快照["__mantou_bot_appid__"]}, sort_keys=True).encode()).hexdigest()
    return 作用域, 快照


async def _准备ZLibrary自动账号(
    配置: dict[str, Any], *, 手动测试: bool = False,
) -> dict[str, str] | None:
    async with asyncio.timeout(240):
        if 手动测试:
            return await _注册并保存ZLibrary账号(配置)
        # 并发等待者可能已由前一流程完成注册；创建前再查一次。
        已有 = await 获取ZLibrary搜索账号(配置, 自动注册=False)
        if 已有:
            return 已有
        状态列表 = await asyncio.to_thread(
            运行状态数据库.读取运行状态命名空间, 配置, ZLibrary账号命名空间,
        )
        if any(账号.get("status") == "logged_in" for _, 账号 in _解析ZLibrary账号记录(状态列表)):
            return None
        return await _注册并保存ZLibrary账号(配置)


async def _确保ZLibrary自动账号(配置: Any, *, 手动测试: bool = False) -> dict[str, str] | None:
    if _ZLibrary账号停止:
        return None
    try:
        作用域, 快照 = _ZLibrary注册配置快照(配置)
    except Exception as exc:
        logger.warning("ZLibrary账号配置未就绪：错误类型=%s", type(exc).__name__)
        return None
    if 手动测试:
        # 每次明确指令独立注册；自动任务仍按机器人/数据库合并及冷却。
        作用域 += ":test:" + uuid.uuid4().hex
    任务 = ZLibrary自动注册任务.get(作用域)
    if 任务 is None or 任务.done():
        if ZLibrary注册失败冷却.get(作用域, 0.0) > time.monotonic():
            return None
        async def 执行():
            try:
                账号 = await _准备ZLibrary自动账号(快照, 手动测试=手动测试)
                if not 账号:
                    ZLibrary注册失败冷却[作用域] = time.monotonic() + 60
                return 账号
            except Exception as exc:
                ZLibrary注册失败冷却[作用域] = time.monotonic() + 60
                logger.warning(
                    "ZLibrary自动账号准备失败：阶段=%s 状态=%s HTTP=%s 错误类型=%s",
                    getattr(exc, "阶段", "account"), getattr(exc, "状态", "unconfirmed"),
                    getattr(exc, "http状态", 0), type(exc).__name__,
                )
                return None
        任务 = asyncio.create_task(执行())
        ZLibrary自动注册任务[作用域] = 任务
        ZLibrary注册任务集合.add(任务)
        def 收尾(已完成):
            ZLibrary注册任务集合.discard(已完成)
            if ZLibrary自动注册任务.get(作用域) is 已完成:
                ZLibrary自动注册任务.pop(作用域, None)
            if not 已完成.cancelled():
                已完成.exception()
        任务.add_done_callback(收尾)
    # 单个搜索取消不会丢掉已提交的注册；插件停止统一回收。
    return await asyncio.shield(任务)


async def _ZLibrary注册回复流(配置: Any, *, 手动测试: bool = False):
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 配置) != "正常":
        yield "数据库未连接，请先配置并连接数据库后重试"
        return
    yield "正在注册新账号并验证登录，请稍等" if 手动测试 else "正在准备账号，已有账号将直接复用，请稍等"
    账号 = None if 手动测试 else await 获取ZLibrary搜索账号(配置, 自动注册=False)
    if not 账号:
        账号 = await _确保ZLibrary自动账号(配置, 手动测试=手动测试)
    if 账号:
        yield "新账号注册及登录验证成功，已自动保存到数据库" if 手动测试 else "账号已就绪，已保存账号会持续复用"
        return
    分类 = 运行状态数据库.读取配置字段(配置, "zlibrary_account_settings") or 配置
    api_key = str(运行状态数据库.读取配置字段(分类, "zlibrary_mail_api_key") or "").strip()
    if not api_key:
        yield "未配置邮箱 API Key，请在插件配置中填写后重试"
    elif not api_key.startswith("AC-"):
        yield "邮箱 API Key 格式不正确，请检查插件配置后重试"
    else:
        yield "账号准备未完成，请稍后重试"


async def _ZLibrary静默回复流():
    if False:
        yield ""


def 获取ZLibrary账号回复流(event: Any, 命令文本: str, 配置: Any):
    if str(命令文本).strip().lower() not in {"注册zlibrary", "创建zlibrary账号", "测试账号"}:
        return None
    if not 权限工具.是QQ官方机器人(event) or not 权限工具.是群文件清理管理员(event, 配置):
        return _ZLibrary静默回复流()
    return _ZLibrary注册回复流(配置, 手动测试=str(命令文本).strip() == "测试账号")


async def 停止ZLibrary账号任务() -> None:
    global _ZLibrary账号停止
    _ZLibrary账号停止 = True
    任务列表 = list(ZLibrary注册任务集合)
    for 任务 in 任务列表:
        任务.cancel()
    await asyncio.gather(*任务列表, return_exceptions=True)
    ZLibrary注册任务集合.clear()
    ZLibrary自动注册任务.clear()
    ZLibrary账号资料任务.clear()


def _解析ZLibraryEAPI搜索结果(数据: dict[str, Any], 需要数量: int) -> list[dict[str, Any]]:
    if 数据.get("success") != 1 or not isinstance(数据.get("books"), list):
        raise _ZLibrary注册错误("search", "unconfirmed")
    结果 = []
    for 书籍 in 数据["books"]:
        if not isinstance(书籍, dict):
            continue
        编号, 哈希 = str(书籍.get("id") or ""), str(书籍.get("hash") or "")
        标题 = _清理正文(书籍.get("title"))
        if not re.fullmatch(r"[0-9]{1,30}", 编号) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", 哈希) or not 标题:
            continue
        结果.append({
            "platform": "ZLibrary", "book_id": 编号, "title": 标题,
            "author": _清理正文(书籍.get("author")) or "未知",
            "url": f"{ZLibrary搜索域名}/book/{编号}/{哈希}",
        })
        if len(结果) >= 需要数量:
            break
    return 结果


async def 搜索ZLibrary(
    关键词: str, *, 需要数量: int = 15, 配置: Any = None
) -> list[dict[str, Any]]:
    查询 = str(关键词 or "").strip()
    if not 查询:
        return []
    账号 = await 获取ZLibrary搜索账号(配置)
    if not 账号:
        return []
    async with _创建ZLibrary会话() as session:
        await _登录ZLibraryEAPI(session, 账号)
        数据 = await _请求ZLibrary注册接口(
            session, "POST", ZLibrary搜索域名 + "/eapi/book/search", "search",
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            data={"message": 查询, "page": 1, "limit": max(1, min(int(需要数量), 50))},
        )
        return _解析ZLibraryEAPI搜索结果(数据, max(1, min(int(需要数量), 50)))


def 解析ZLibrary书籍编号(来源: str) -> tuple[str, str]:
    try:
        路径 = [项目 for 项目 in urlsplit(来源).path.split("/") if 项目]
    except ValueError:
        return "", ""
    if len(路径) < 2 or 路径[0].lower() != "book":
        return "", ""
    书籍编号 = unquote(路径[1]).strip()
    哈希 = unquote(路径[2]).strip() if len(路径) >= 3 else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", 书籍编号):
        return "", ""
    return 书籍编号, 哈希


def _响应文件名(headers: Any, 默认值: str = "book.bin") -> str:
    内容处置 = str(headers.get("Content-Disposition") or "")
    if 内容处置:
        try:
            消息 = Message()
            消息["Content-Disposition"] = 内容处置
            文件名 = 消息.get_filename()
            if 文件名:
                return unquote(str(文件名).strip())
        except Exception:
            pass
    return 默认值


def _清理文件名(值: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|]+", "_", str(值 or "").strip())
    return 文本[:90] or "Z-Library小说"


class _ZLibrary详情链接解析器(HTMLParser):
    """读取详情页公开的格式下载与转换链接。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.链接列表: list[dict[str, str]] = []
        self._当前链接: dict[str, Any] | None = None

    def _完成当前链接(self) -> None:
        if self._当前链接 is None:
            return
        项目 = self._当前链接
        项目["text"] = " ".join(项目.pop("text_parts")).strip()
        self.链接列表.append(项目)
        self._当前链接 = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in {"a", "button"}:
            return
        self._完成当前链接()
        属性 = {键.lower(): str(值 or "") for 键, 值 in attrs if 键}
        href = 属性.get("href") or 属性.get("data-href") or 属性.get("data-url")
        if not href:
            return
        self._当前链接 = {
            "tag": tag,
            "href": html.unescape(href.strip()),
            "format": 属性.get("data-format") or 属性.get("data-type") or "",
            "label": 属性.get("aria-label") or 属性.get("title") or "",
            "text_parts": [],
        }

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self._当前链接 is not None:
            self._完成当前链接()

    def handle_data(self, data: str) -> None:
        if self._当前链接 is not None:
            self._当前链接["text_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._当前链接 is not None and tag.lower() == self._当前链接.get("tag"):
            self._完成当前链接()


def _提取官方TXT转换链接(原始HTML: str) -> str:
    解析器 = _ZLibrary详情链接解析器()
    解析器.feed(原始HTML)
    解析器.close()
    解析器._完成当前链接()
    for 链接 in 解析器.链接列表:
        href = 链接.get("href", "")
        try:
            地址 = urlsplit(href)
            主机 = (地址.hostname or "").lower().strip(".")
        except ValueError:
            continue
        if 地址.scheme and 地址.scheme.lower() not in {"http", "https"}:
            continue
        if 主机 and 主机 not in ZLibrary允许域名:
            continue
        标签 = re.sub(r"\s+", " ", _清理正文(链接.get("text") or 链接.get("label"))).strip().lower()
        格式 = re.sub(r"[^a-z0-9]", "", 链接.get("format", "").lower())
        路径 = 地址.path.lower()
        查询 = 地址.query.lower()
        if (
            re.search(r"(?<![a-z])txt(?![a-z])", 标签)
            or 格式 in {"txt", "text", "plaintext"}
            or 路径.endswith(".txt")
            or re.search(r"(?:^|&)(?:format|type|extension)=txt(?:&|$)", 查询)
        ):
            return href
    return ""


def _解析HTML字段(原始: str) -> dict[str, Any]:
    小写原始 = 原始.lower()
    if any(
        标记 in 小写原始
        for 标记 in ("diamwall", "verifying your browser", "checking your browser")
    ):
        raise _ZLibrary站点错误(
            "Z-Library站点验证未通过", 诊断原因="anti_bot_page"
        )

    def 匹配文本(选择器属性: str) -> str:
        标签选择器 = (
            选择器属性
            if 选择器属性.startswith("<")
            else rf"<[^>]*{选择器属性}"
        )
        匹配 = re.search(
            rf"{标签选择器}[^>]*>([\s\S]*?)</[^>]+>",
            原始,
            re.I,
        )
        return _清理正文(匹配.group(1)) if 匹配 else ""

    标题 = 匹配文本(r"<h1\b[^>]*itemprop\s*=\s*['\"]name['\"]")
    if not 标题:
        元数据 = re.search(
            r"<meta\b[^>]*(?:itemprop\s*=\s*['\"]name['\"]|"
            r"property\s*=\s*['\"]og:title['\"])[^>]*"
            r"content\s*=\s*['\"]([^'\"]+)['\"]",
            原始,
            re.I,
        )
        if 元数据:
            标题 = _清理正文(元数据.group(1))
    if not 标题:
        标题 = 匹配文本(r"<h1\b")
    作者列表 = [
        _清理正文(匹配.group(1))
        for 匹配 in re.finditer(
            r"<a[^>]*itemprop\s*=\s*['\"]author['\"][^>]*>([\s\S]*?)</a>",
            原始,
            re.I,
        )
    ]
    作者列表 = list(dict.fromkeys(项目 for 项目 in 作者列表 if 项目))
    详情文件类型 = ""
    文件类型匹配 = re.search(
        r"(?:property__file|itemprop\s*=\s*['\"]encodingFormat['\"])[^>]*>"
        r"([\s\S]{0,200})",
        原始,
        re.I,
    )
    if 文件类型匹配:
        详情文件类型 = _清理正文(文件类型匹配.group(1))
    数字书籍编号匹配 = re.search(
        r"<[^>]+\bid\s*=\s*['\"]([0-9]{4,12})['\"][^>]*>",
        原始,
        re.I,
    )
    if not 数字书籍编号匹配:
        数字书籍编号匹配 = re.search(
            r"\bdata-book-id\s*=\s*['\"]([0-9]{4,12})['\"]",
            原始,
            re.I,
        )
    数字书籍编号 = 数字书籍编号匹配.group(1) if 数字书籍编号匹配 else ""
    TXT转换可用 = bool(
        re.search(
            r"\bdata-convertation-available\s*=\s*['\"]?1['\"]?",
            原始,
            re.I,
        )
        and re.search(r"\bdata-convert_to\s*=\s*['\"]txt['\"]", 原始, re.I)
    )
    下载链接 = ""
    for 匹配 in re.finditer(
        r"<(?:a|button)[^>]+(?:href|data-href|data-url)\s*=\s*['\"]([^'\"]+)['\"][^>]*>",
        原始,
        re.I,
    ):
        候选 = html.unescape(匹配.group(1))
        if "/dl/" in 候选 or "/download" in 候选 or "download" in 候选.lower():
            下载链接 = 候选
            break
    if not 下载链接:
        匹配 = re.search(r"['\"]([^'\"]*/dl/[^'\"]+)['\"]", 原始, re.I)
        if 匹配:
            下载链接 = html.unescape(匹配.group(1))
    TXT转换链接 = _提取官方TXT转换链接(原始)
    return {
        "title": 标题,
        "author": ", ".join(作者列表) or "未知",
        "download_url": 下载链接,
        "txt_conversion_url": TXT转换链接,
        "txt_conversion_available": TXT转换可用,
        "book_id": 数字书籍编号,
        "file_type": 详情文件类型,
    }


async def _请求详情(session: aiohttp.ClientSession, 来源: str) -> dict[str, Any]:
    try:
        async with session.get(来源, headers=_请求头(来源)) as response:
            if response.status in {403, 429, 503, 513}:
                响应提示 = (
                    await response.content.read(64 * 1024)
                ).decode("utf-8", "replace").lower()
                是浏览器校验 = any(
                    标记 in 响应提示
                    for 标记 in (
                        "diamwall",
                        "verifying your browser",
                        "checking your browser",
                    )
                )
                raise _ZLibrary站点错误(
                    "Z-Library站点暂时不可访问",
                    诊断原因="anti_bot_page" if 是浏览器校验 else "http_blocked",
                    http_status=response.status,
                )
            if response.status >= 400:
                raise _ZLibrary站点错误(
                    "Z-Library详情请求HTTP失败",
                    诊断原因="http_error",
                    http_status=response.status,
                )
            原始 = await response.content.read(ZLibrary详情最大字节数 + 1)
            if len(原始) > ZLibrary详情最大字节数:
                raise _ZLibrary站点错误(
                    "Z-Library详情响应过大", 诊断原因="response_too_large"
                )
            最终来源 = str(response.url)
    except _ZLibrary站点错误:
        raise
    except asyncio.TimeoutError as exc:
        raise _ZLibrary站点错误(
            "Z-Library详情请求超时", 诊断原因="request_timeout"
        ) from exc
    except aiohttp.ClientError as exc:
        raise _ZLibrary站点错误(
            "Z-Library详情连接失败", 诊断原因="transport_error"
        ) from exc
    except Exception as exc:
        raise RuntimeError("Z-Library详情请求失败") from exc
    详情 = _解析HTML字段(原始.decode("utf-8", "replace"))
    if not _是ZLibrary链接(最终来源):
        raise _ZLibrary站点错误(
            "Z-Library详情发生非站点跳转", 诊断原因="redirect_outside_site"
        )
    书籍编号, 哈希 = 解析ZLibrary书籍编号(来源)
    if not 详情.get("book_id") and re.fullmatch(r"[0-9]{4,12}", 书籍编号):
        详情["book_id"] = 书籍编号
    详情["book_slug"] = 书籍编号
    详情["hash"] = 哈希
    详情["detail_url"] = 最终来源
    可用官方转换 = bool(
        详情.get("txt_conversion_available")
        and re.fullmatch(r"[0-9]{4,12}", str(详情.get("book_id") or ""))
    )
    if not 详情.get("title"):
        raise _ZLibrary站点错误(
            "Z-Library详情缺少标题", 诊断原因="detail_title_missing"
        )
    if not (
        详情.get("download_url") or 详情.get("txt_conversion_url") or 可用官方转换
    ):
        raise _ZLibrary站点错误(
            "Z-Library详情缺少下载信息", 诊断原因="detail_download_markers_missing"
        )
    原始下载链接 = (
        urljoin(最终来源, str(详情["download_url"]))
        if 详情.get("download_url")
        else ""
    )
    TXT转换链接 = str(详情.get("txt_conversion_url") or "").strip()
    if TXT转换链接:
        官方TXT链接 = urljoin(最终来源, TXT转换链接)
        if not _是ZLibrary站点HTTPS地址(官方TXT链接):
            raise _ZLibrary站点错误(
                "Z-Library官方TXT转换地址无效",
                诊断原因="invalid_txt_conversion_url",
            )
        详情["download_url"] = 官方TXT链接
        详情["download_mode"] = "direct_txt"
    else:
        原始格式 = re.sub(r"[^a-z0-9]", "", str(详情.get("file_type") or "").lower())
        原始路径 = urlsplit(原始下载链接).path.lower() if 原始下载链接 else ""
        if "txt" in 原始格式 or 原始路径.endswith(".txt"):
            详情["download_mode"] = "direct_txt"
            详情["download_url"] = 原始下载链接
        elif 可用官方转换:
            详情["download_mode"] = "api_conversion"
            详情["download_url"] = ""
        else:
            raise _ZLibrary站点错误(
                "Z-Library详情没有官方TXT转换方式",
                诊断原因="official_txt_conversion_unavailable",
            )
    return 详情


async def _请求详情含认证重试(
    session: aiohttp.ClientSession, 来源: str, 配置: Any
) -> dict[str, Any]:
    if urlsplit(来源).hostname in {"zlib.bz", "zh.zlib.bz"}:
        账号 = getattr(session, "_mantou_zlibrary_download_account", None) or await 获取ZLibrary下载账号(配置)
        session._mantou_zlibrary_download_account = 账号
        if not 账号:
            raise _ZLibrary站点错误("Z-Library缺少可用账号")
        await _登录ZLibraryEAPI(session, 账号)
        编号, 哈希 = 解析ZLibrary书籍编号(来源)
        if not re.fullmatch(r"[0-9]{1,30}", 编号) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", 哈希):
            raise _ZLibrary站点错误("Z-Library书籍编号无效")
        数据 = await _请求ZLibrary注册接口(
            session, "GET", f"{ZLibrary搜索域名}/eapi/book/{编号}/{哈希}", "detail",
        )
        书籍 = 数据.get("book")
        if 数据.get("success") != 1 or not isinstance(书籍, dict) or str(书籍.get("id")) != 编号:
            raise _ZLibrary站点错误("Z-Library书籍详情未确认")
        下载地址 = urljoin(ZLibrary搜索域名, str(书籍.get("dl") or ""))
        if (not 书籍.get("dl") or urlsplit(下载地址).netloc.lower() != urlsplit(ZLibrary搜索域名).netloc
                or urlsplit(下载地址).scheme != "https"):
            raise _ZLibrary站点错误("Z-Library下载地址无效")
        if str(书籍.get("extension") or "").lower() != "txt":
            raise _ZLibrary站点错误("Z-Library当前书籍没有官方TXT")
        return {
            "book_id": 编号, "hash": 哈希,
            "title": _清理正文(书籍.get("title")) or "Z-Library小说",
            "author": _清理正文(书籍.get("author")) or "未知",
            "file_type": "txt", "download_mode": "direct_txt",
            "download_url": 下载地址, "detail_url": 来源,
        }
    try:
        return await _请求详情(session, 来源)
    except _ZLibrary站点错误 as exc:
        if exc.诊断原因 != "anti_bot_page" or exc.http_status != 503:
            raise
        账号 = getattr(session, "_mantou_zlibrary_download_account", None) or await 获取ZLibrary下载账号(配置)
        session._mantou_zlibrary_download_account = 账号
        if not 账号:
            raise
        await _登录ZLibrary转换账号(session, 来源, 账号)
        return await _请求详情(session, 来源)


def _请求头(来源: str = "") -> dict[str, str]:
    地址 = urlsplit(来源)
    return {
        "Accept": "text/html,application/xhtml+xml,application/epub+zip,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Referer": f"{地址.scheme}://{地址.netloc}/" if 地址.netloc else "https://zh.z-library.sk/",
    }


async def _登录ZLibrary转换账号(
    session: aiohttp.ClientSession, 详情页地址: str, 账号: dict[str, str]
) -> str:
    地址 = urlsplit(详情页地址)
    站点地址 = f"{地址.scheme}://{地址.netloc}"
    if not _是ZLibrary站点HTTPS地址(站点地址):
        raise _ZLibrary站点错误("Z-Library登录站点地址无效")
    if 地址.hostname in {"zlib.bz", "zh.zlib.bz"}:
        await _登录ZLibraryEAPI(session, 账号)
        return 站点地址
    现有Cookie = session.cookie_jar.filter_cookies(aiohttp.client_reqrep.URL(站点地址))
    if all(
        现有Cookie.get(字段) and 现有Cookie[字段].value
        for 字段 in ("remix_userid", "remix_userkey")
    ):
        return 站点地址
    登录数据 = await _请求ZLibrary注册接口(
        session,
        "POST",
        站点地址 + "/rpc.php",
        "login",
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Origin": 站点地址,
            "Referer": 详情页地址,
            "X-Requested-With": "XMLHttpRequest",
        },
        data={
            "isModal": "true",
            "email": str(账号.get("email") or ""),
            "password": str(账号.get("password") or ""),
            "site_mode": "books",
            "action": "login",
            "isSingleLogin": "1",
            "redirectUrl": "",
            "gg_json_mode": "1",
        },
    )
    _检查ZLibrary业务回复(登录数据, "login")
    cookies = session.cookie_jar.filter_cookies(aiohttp.client_reqrep.URL(站点地址))
    if not all(
        cookies.get(字段) and cookies[字段].value
        for 字段 in ("remix_userid", "remix_userkey")
    ):
        raise _ZLibrary站点错误("Z-Library登录未取得有效会话")
    return 站点地址


async def _请求ZLibrary转换JSON(
    session: aiohttp.ClientSession,
    方法: str,
    地址: str,
    详情页地址: str,
) -> dict[str, Any]:
    try:
        async with session.request(
            方法,
            地址,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Origin": f"{urlsplit(详情页地址).scheme}://{urlsplit(详情页地址).netloc}",
                "Referer": 详情页地址,
                "X-Requested-With": "XMLHttpRequest",
            },
            allow_redirects=False,
        ) as response:
            if response.status in {401, 403}:
                raise _ZLibrary站点错误("Z-Library官方TXT转换未通过登录验证")
            if response.status >= 400:
                raise _ZLibrary站点错误("Z-Library官方TXT转换请求失败")
            原始 = await response.content.read(ZLibrary转换响应最大字节数 + 1)
            if len(原始) > ZLibrary转换响应最大字节数:
                raise _ZLibrary站点错误("Z-Library官方TXT转换响应过大")
    except _ZLibrary站点错误:
        raise
    except Exception as exc:
        raise _ZLibrary站点错误("Z-Library官方TXT转换请求失败") from exc
    try:
        数据 = json.loads(原始.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise _ZLibrary站点错误("Z-Library官方TXT转换响应无效") from exc
    if not isinstance(数据, dict):
        raise _ZLibrary站点错误("Z-Library官方TXT转换响应无效")
    return 数据


def _官方转换下载地址(数据: Any, 详情页地址: str) -> str:
    if not isinstance(数据, dict):
        return ""
    候选 = str(数据.get("downloadUrl") or "").strip()
    if not 候选:
        return ""
    地址 = urljoin(详情页地址, 候选)
    if not _是ZLibrary站点HTTPS地址(地址):
        raise _ZLibrary站点错误("Z-Library官方TXT转换下载地址无效")
    return 地址


async def _请求官方TXT转换(
    session: aiohttp.ClientSession, 详情: dict[str, Any], 来源: str, 配置: Any
) -> str:
    书籍编号 = str(详情.get("book_id") or "")
    详情页地址 = str(详情.get("detail_url") or 来源)
    if not re.fullmatch(r"[0-9]{4,12}", 书籍编号):
        raise _ZLibrary站点错误("Z-Library官方TXT转换缺少书籍编号")
    账号 = getattr(session, "_mantou_zlibrary_download_account", None) or await 获取ZLibrary下载账号(配置)
    session._mantou_zlibrary_download_account = 账号
    if not 账号:
        raise _ZLibrary站点错误("Z-Library官方TXT转换缺少已登录账号")
    站点地址 = await _登录ZLibrary转换账号(session, 详情页地址, 账号)
    转换地址 = f"{站点地址}/papi/book/{书籍编号}/file-conversion/txt"
    创建结果 = await _请求ZLibrary转换JSON(
        session, "POST", 转换地址, 详情页地址
    )
    if 创建结果.get("error"):
        raise _ZLibrary站点错误("Z-Library官方TXT转换任务创建失败")
    即时结果 = 创建结果.get("response")
    下载地址 = _官方转换下载地址(即时结果, 详情页地址)
    if 下载地址:
        return 下载地址
    任务编号 = str(
        创建结果.get("jobId")
        or (即时结果.get("jobId") if isinstance(即时结果, dict) else "")
        or ""
    )
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", 任务编号):
        raise _ZLibrary站点错误("Z-Library官方TXT转换未返回任务编号")
    状态地址 = f"{站点地址}/papi/book/{书籍编号}/file-conversion/jobs"
    截止时间 = time.monotonic() + ZLibrary转换等待秒数
    await asyncio.sleep(min(5, ZLibrary转换等待秒数))
    while time.monotonic() < 截止时间:
        状态结果 = await _请求ZLibrary转换JSON(
            session, "GET", 状态地址, 详情页地址
        )
        状态主体 = 状态结果.get("response")
        if not isinstance(状态主体, dict) or "jobs" not in 状态主体:
            状态主体 = 状态结果
        任务列表 = 状态主体.get("jobs") if isinstance(状态主体, dict) else None
        if not isinstance(任务列表, list):
            raise _ZLibrary站点错误("Z-Library官方TXT转换状态无效")
        for 任务 in 任务列表:
            if not isinstance(任务, dict) or str(任务.get("jobId") or "") != 任务编号:
                continue
            状态 = str(任务.get("status") or "").lower()
            if 状态 == "ok":
                下载地址 = _官方转换下载地址(任务, 详情页地址)
                if not 下载地址:
                    raise _ZLibrary站点错误("Z-Library官方TXT转换未返回下载地址")
                return 下载地址
            if 状态 in {"error", "failed", "failure", "cancelled"}:
                raise _ZLibrary站点错误("Z-Library官方TXT转换任务失败")
            break
        await asyncio.sleep(
            min(ZLibrary转换轮询间隔秒数, max(0, 截止时间 - time.monotonic()))
        )
    raise _ZLibrary站点错误("Z-Library官方TXT转换等待超时")


async def _下载原文件(
    session: aiohttp.ClientSession, 详情: dict[str, Any], 来源: str
) -> tuple[Path, str]:
    下载地址 = str(详情.get("download_url") or "")
    if not 下载地址:
        raise _ZLibrary站点错误("Z-Library下载地址为空")
    try:
        下载URL = urlsplit(下载地址)
    except ValueError as exc:
        raise _ZLibrary站点错误("Z-Library下载地址无效") from exc
    if 下载URL.scheme.lower() not in {"http", "https"} or not 下载URL.hostname:
        raise _ZLibrary站点错误("Z-Library下载地址无效")
    扩展名 = Path(urlsplit(下载地址).path).suffix.lower() or ".bin"
    路径 = await asyncio.to_thread(
        文件缓存工具.创建临时缓存文件, "zlibrary-", 扩展名
    )
    try:
        async with session.get(下载地址, headers=_请求头(来源), allow_redirects=True) as response:
            if response.status in {403, 429, 503, 513}:
                raise _ZLibrary站点错误("Z-Library文件暂时不可下载")
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            内容类型 = str(response.headers.get("Content-Type") or "").lower()
            文件名 = _响应文件名(response.headers, f"book{扩展名}")
            if Path(文件名).suffix.lower() not in {
                ".epub", ".fb2", ".pdf", ".txt", ".html", ".htm", ".xhtml"
            }:
                后缀 = {
                    "application/epub+zip": ".epub",
                    "application/pdf": ".pdf",
                    "text/plain": ".txt",
                    "text/html": ".html",
                    "application/xhtml+xml": ".xhtml",
                }.get(内容类型.split(";", 1)[0].strip())
                if 后缀:
                    文件名 = f"book{后缀}"
            内容媒体类型 = 内容类型.split(";", 1)[0].strip()
            if 内容媒体类型 in {
                "text/html",
                "application/xhtml+xml",
                "application/pdf",
                "application/epub+zip",
                "application/json",
                "application/problem+json",
                "application/xml",
                "text/xml",
            }:
                raise _ZLibrary站点错误("Z-Library官方TXT转换未返回TXT")
            if Path(文件名).suffix.lower() != ".txt":
                if 内容媒体类型 != "text/plain":
                    raise _ZLibrary站点错误("Z-Library官方TXT转换未返回TXT")
                文件名 = f"{Path(文件名).stem or 'book'}.txt"
            总长度 = response.headers.get("Content-Length")
            if 总长度 and int(总长度) > ZLibrary文件最大字节数:
                raise _ZLibrary站点错误("Z-Library文件过大")
            已写入 = 0
            with 路径.open("wb") as 文件:
                async for 块 in response.content.iter_chunked(256 * 1024):
                    已写入 += len(块)
                    if 已写入 > ZLibrary文件最大字节数:
                        raise _ZLibrary站点错误("Z-Library文件过大")
                    文件.write(块)
            if 内容类型.startswith("text/html"):
                raise _ZLibrary站点错误("Z-Library下载未返回可用TXT")
            return 路径, 文件名
    except Exception:
        await asyncio.to_thread(路径.unlink, True)
        raise


def _解码文本(原始: bytes) -> str:
    for 编码 in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            文本 = 原始.decode(编码)
            if 文本.count("\ufffd") < max(2, len(文本) // 100):
                return 文本
        except UnicodeDecodeError:
            continue
    return 原始.decode("utf-8", "replace")


def _读取官方TXT(路径: Path) -> str:
    原始 = 路径.read_bytes()
    if 原始.startswith((b"PK\x03\x04", b"%PDF-")):
        raise _ZLibrary站点错误("Z-Library官方转换返回了非TXT文件")
    正文 = _解码文本(原始).replace("\r\n", "\n").replace("\r", "\n")
    开头 = re.sub(r"\s+", "", 正文[:512]).lower()
    if 开头.startswith(("<!doctypehtml", "<html", "<head", "<body")):
        raise _ZLibrary站点错误("Z-Library官方转换未返回TXT正文")
    if len(正文.strip()) < 2:
        raise _ZLibrary站点错误("Z-Library官方TXT正文为空")
    return 正文.strip()


def _生成输出文件名(详情: dict[str, Any]) -> str:
    标题 = _清理文件名(详情.get("title") or "Z-Library小说")
    作者 = _清理文件名(详情.get("author") or "未知")
    return f"[完结]书名：{标题} 作者：{作者}.txt"


def _写入小说缓存(文件名: str, 内容: bytes) -> Path:
    目录 = 文件缓存工具.小说缓存目录
    目录.mkdir(parents=True, exist_ok=True)
    基础名 = Path(_清理文件名(文件名)).name
    if not 基础名.lower().endswith(".txt"):
        基础名 += ".txt"
    路径 = 目录 / 基础名
    for 序号 in range(1000):
        候选 = 路径 if 序号 == 0 else 目录 / f"{路径.stem}_{序号}{路径.suffix}"
        if not 候选.exists():
            候选.write_bytes(内容)
            文件缓存工具.标记小说缓存正在使用(候选)
            return 候选
    raise RuntimeError("小说缓存文件过多")


async def _发送小说文件(
    event: Any,
    文件名: str,
    内容: bytes,
    配置: Any,
    书名: str,
    作者: str,
) -> dict[str, Any]:
    路径 = await asyncio.to_thread(_写入小说缓存, 文件名, 内容)
    if 小说网盘 is None:
        await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
        return {"sent": False, "fallback_text": "", "path": None}
    try:
        上传 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传.get("success"):
            await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
            return {"sent": False, "fallback_text": "", "path": None}
        完成 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(上传.get("share_url") or "")
        )
        if 完成.get("sent"):
            await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
            return {"sent": True, "fallback_text": "", "path": None}
        return {
            "sent": False,
            "fallback_text": str(完成.get("fallback_text") or ""),
            "path": 路径,
        }
    except Exception:
        await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
        raise


def _创建ZLibrary会话() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=ZLibrary请求超时秒数, sock_connect=10, sock_read=25),
        connector=aiohttp.TCPConnector(limit=4, limit_per_host=4, ttl_dns_cache=300),
        trust_env=False,
        cookie_jar=aiohttp.CookieJar(unsafe=False),
    )


def 格式化ZLibrary下载提示(详情: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"书名：{详情.get('title') or '未知'}",
            f"作者：{详情.get('author') or '未知'}",
            "状态：电子书文件",
            "章节：整本",
            "",
            "正在下载中请稍等.....",
        ]
    )


async def 生成ZLibrary下载回复流(
    event: Any, 来源: str, 配置: Any = None
) -> AsyncIterator[str]:
    临时路径: Path | None = None
    阶段 = "create_session"
    try:
        阶段 = "account"
        绑定账号 = await 获取ZLibrary下载账号(配置)
        async with _创建ZLibrary会话() as session:
            session._mantou_zlibrary_download_account = 绑定账号
            阶段 = "detail"
            详情 = await _请求详情含认证重试(session, 来源, 配置)
            logger.info(
                "Z-Library小说开始下载：书名=%s, 作者=%s, 下载文件=1",
                详情.get("title") or "未知",
                详情.get("author") or "未知",
            )
            yield 格式化ZLibrary下载提示(详情)
            if 详情.get("download_mode") == "api_conversion":
                阶段 = "official_txt_conversion"
                详情["download_url"] = await _请求官方TXT转换(
                    session, 详情, 来源, 配置
                )
            阶段 = "download"
            临时路径, 原文件名 = await _下载原文件(session, 详情, 来源)
            await _刷新ZLibrary下载后额度(配置, 绑定账号)
            阶段 = "official_txt"
            if Path(原文件名).suffix.lower() != ".txt":
                raise _ZLibrary站点错误("Z-Library官方转换没有生成TXT")
            正文 = await asyncio.to_thread(_读取官方TXT, 临时路径)
            内容 = await asyncio.to_thread(临时路径.read_bytes)
            文件名 = _生成输出文件名(详情)
            字数 = len(re.sub(r"\s+", "", 正文))
            logger.info(
                "Z-Library小说下载完成：书名=%s, 文件数=1, 字数=%s, 文件大小=%s",
                详情.get("title") or "未知",
                字数,
                len(内容),
            )
            阶段 = "share"
            发送结果 = await _发送小说文件(
                event,
                文件名,
                内容,
                配置,
                str(详情.get("title") or "未知"),
                str(详情.get("author") or "未知"),
            )
            if 发送结果.get("sent"):
                return
            路径 = 发送结果.get("path")
            if 路径:
                await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
            降级文本 = str(发送结果.get("fallback_text") or "")
            if 降级文本:
                yield 降级文本
                return
            yield ZLibrary文件发送失败提示
    except Exception as exc:
        logger.warning(
            "Z-Library小说下载失败：阶段=%s, 错误类型=%s, 原因=%s, HTTP状态=%s, 底层错误类型=%s",
            阶段,
            type(exc).__name__,
            getattr(exc, "诊断原因", None) or getattr(exc, "状态", "unclassified"),
            getattr(exc, "http_status", None)
            or getattr(exc, "http状态", None)
            or "none",
            type(exc.__cause__).__name__ if exc.__cause__ else "none",
        )
        yield "账号额度暂不可用，请等待恢复后重试" if getattr(exc, "诊断原因", "") == "quota_paused" else ZLibrary下载失败提示
    finally:
        if 临时路径 is not None:
            await asyncio.to_thread(临时路径.unlink, True)


def 获取ZLibrary小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[str] | None:
    来源 = 提取ZLibrary来源(event, 命令文本)
    if not 来源:
        return None
    return 生成ZLibrary下载回复流(event, 来源, 配置)
