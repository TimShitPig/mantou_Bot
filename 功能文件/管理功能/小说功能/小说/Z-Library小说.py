"""Z-Library 搜索、账号创建与公开书籍下载。"""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import json
import posixpath
import re
import secrets
import time
import uuid
import zipfile
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import quote, unquote, urljoin, urlsplit
from xml.etree import ElementTree

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
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题


ZLibrary允许域名 = {
    "z-library.sk",
    "zh.z-library.sk",
}
ZLibrary链接正则 = re.compile(
    r"https?://(?:zh\.)?z-library\.sk/book/[^\s<>\"']+", re.IGNORECASE
)
ZLibrary请求超时秒数 = 35
ZLibrary详情最大字节数 = 4 * 1024 * 1024
ZLibrary文件最大字节数 = 120 * 1024 * 1024
ZLibrary压缩后最大展开字节数 = 256 * 1024 * 1024
ZLibrary搜索结果最大字节数 = 4 * 1024 * 1024
ZLibrary搜索登录URL = "https://z-library.sk/rpc.php"
ZLibrary搜索域名 = "https://z-library.sk"
ZLibrary邮箱API地址 = "https://maliapi.215.im/v1"
ZLibrary注册站点地址 = "https://libb.la"
ZLibrary搜索锁: asyncio.Lock = globals().get("ZLibrary搜索锁", asyncio.Lock())
ZLibrary账号命名空间 = "zlibrary_accounts"
ZLibrary注册任务集合: set[asyncio.Task] = globals().get("ZLibrary注册任务集合", set())
ZLibrary最近注册启动 = globals().get("ZLibrary最近注册启动", 0.0)
ZLibrary文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。"
    "如喜欢本书，请支持正版。"
)
ZLibrary下载失败提示 = "下载失败 请重试"
ZLibrary文件发送失败提示 = "文件发送失败，请稍后再试"


class _ZLibrary站点错误(RuntimeError):
    pass


class _ZLibrary正文HTML解析器(HTMLParser):
    """把常见 EPUB XHTML 或网页正文转成段落文本。"""

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


class _ZLibrary注册错误(RuntimeError):
    def __init__(self, 阶段: str, 状态: str, http状态: int = 0):
        self.阶段, self.状态, self.http状态 = 阶段, 状态, http状态
        super().__init__(f"{阶段}:{状态}:{http状态}")


async def _请求ZLibrary注册接口(session, 方法, 地址, 阶段, **参数):
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


def _提取ZLibrary验证码(邮件: dict, 地址: str) -> str | None:
    收件人列表 = 邮件.get("to")
    if not isinstance(收件人列表, list) or not any(
        isinstance(收件人, dict)
        and str(收件人.get("address", "")).lower() == 地址.lower()
        for 收件人 in 收件人列表
    ):
        return None
    发件人 = 邮件.get("from")
    发件地址 = 发件人.get("address", "") if isinstance(发件人, dict) else ""
    发件域名 = str(发件地址).rsplit("@", 1)[-1].lower()
    if not any(
        发件域名 == 域名 or 发件域名.endswith("." + 域名)
        for 域名 in ("libb.la", "z-lib.fm", "1lib.sk")
    ):
        return None
    主题 = str(邮件.get("subject", ""))
    if not re.search(
        r"verification|verify|confirmation|confirm|sign.?up|registration|验证码|验证|注册",
        主题,
        re.I,
    ):
        return None
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
    return (匹配.group(1) or 匹配.group(2)) if 匹配 else None


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
        async with aiohttp.ClientSession(timeout=超时, headers=站点请求头) as 站点会话:
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
                            try:
                                时间戳 = dt.datetime.fromisoformat(
                                    str(邮件.get("createdAt") or 邮件摘要.get("createdAt") or "").replace("Z", "+00:00")
                                )
                            except ValueError:
                                已检查邮件.add(邮件ID)
                                continue
                            if 时间戳.tzinfo is None or 时间戳 < 开始时间:
                                已检查邮件.add(邮件ID)
                                continue
                            验证码 = _提取ZLibrary验证码(邮件, 邮箱)
                            if 验证码:
                                break
                            已检查邮件.add(邮件ID)
                        if 验证码 is None:
                            await asyncio.sleep(轮询间隔)
            except TimeoutError as exc:
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
        async with aiohttp.ClientSession(timeout=超时, headers=站点请求头) as 登录会话:
            登录数据 = await _请求ZLibrary注册接口(
                登录会话,
                "POST",
                站点地址 + "/rpc.php",
                "login",
                data={
                    "email": 邮箱,
                    "password": 密码,
                    "action": "login",
                    "site_mode": "books",
                    "isSingleLogin": "1",
                    "isModal": "true",
                    "redirectUrl": "",
                    "gg_json_mode": "1",
                },
            )
            登录回复 = _检查ZLibrary业务回复(登录数据, "login")
            cookies = 登录会话.cookie_jar.filter_cookies(aiohttp.client_reqrep.URL(站点地址))
            if not _ZLibrary跳转已确认(登录回复, True) or not all(
                cookies.get(字段) and cookies[字段].value
                for 字段 in ("remix_userid", "remix_userkey")
            ):
                raise _ZLibrary注册错误("login", "unconfirmed")
        账号["status"] = "logged_in"
        await 保存账号(尝试ID, dict(账号))
    return 尝试ID


async def _注册并保存ZLibrary账号(配置: Any) -> str:
    分类 = 运行状态数据库.读取配置字段(配置, "zlibrary_account_settings") or 配置
    api_key = str(运行状态数据库.读取配置字段(分类, "zlibrary_mail_api_key") or "").strip()
    rx = str(运行状态数据库.读取配置字段(分类, "zlibrary_registration_rx") or "215").strip()
    if not api_key:
        return "请先配置邮箱 API Key"
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 配置) != "正常":
        return "请先配置并连接数据库"

    async def 保存(标识: str, 数据: dict[str, Any]) -> None:
        await asyncio.to_thread(
            运行状态数据库.写入运行状态值,
            配置,
            ZLibrary账号命名空间,
            标识,
            json.dumps(数据, ensure_ascii=False),
        )

    try:
        await 自动创建ZLibrary账号(api_key, 保存, rx)
    except _ZLibrary注册错误 as exc:
        logger.warning(
            "ZLibrary创建账号失败：阶段=%s 状态=%s HTTP=%s",
            exc.阶段,
            exc.状态,
            exc.http状态,
        )
        return "账号创建流程未完成，请稍后再试"
    except Exception as exc:
        logger.warning("ZLibrary创建账号失败：类型=%s", type(exc).__name__)
        return "账号创建流程未完成，请稍后再试"
    return "账号注册成功，登录返回成功，账号已保存到数据库"


async def 获取ZLibrary搜索账号(配置: Any) -> dict[str, str] | None:
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 配置) != "正常":
        return None
    try:
        状态列表 = await asyncio.to_thread(
            运行状态数据库.读取运行状态命名空间,
            配置,
            ZLibrary账号命名空间,
        )
    except Exception as exc:
        logger.warning("ZLibrary搜索账号读取失败：错误类型=%s", type(exc).__name__)
        return None
    账号候选 = []
    for 原始值 in 状态列表.values():
        try:
            账号 = json.loads(原始值)
        except (TypeError, ValueError):
            continue
        if not isinstance(账号, dict) or 账号.get("status") != "logged_in":
            continue
        邮箱, 密码 = 账号.get("email"), 账号.get("password")
        if not isinstance(邮箱, str) or not 邮箱 or not isinstance(密码, str) or not 密码:
            continue
        账号候选.append((str(账号.get("created_at") or ""), 邮箱, 密码))
    if not 账号候选:
        return None
    _, 邮箱, 密码 = max(账号候选, key=lambda 项: 项[0])
    return {"email": 邮箱, "password": 密码}


async def _ZLibrary注册回复流(配置: Any):
    global ZLibrary最近注册启动
    if ZLibrary注册任务集合 or time.monotonic() - ZLibrary最近注册启动 < 60:
        yield "账号创建处理中，请稍后再试"
        return
    ZLibrary最近注册启动 = time.monotonic()
    任务 = asyncio.create_task(_注册并保存ZLibrary账号(配置))
    ZLibrary注册任务集合.add(任务)
    try:
        yield "正在自动获取邮箱并创建账号，请稍等"
        yield await 任务
    finally:
        if not 任务.done():
            任务.cancel()
        await asyncio.gather(任务, return_exceptions=True)
        ZLibrary注册任务集合.discard(任务)


async def _ZLibrary静默回复流():
    if False:
        yield ""


def 获取ZLibrary账号回复流(event: Any, 命令文本: str, 配置: Any):
    if str(命令文本).strip().lower() not in {"注册zlibrary", "创建zlibrary账号"}:
        return None
    if not 权限工具.是QQ官方机器人(event) or not 权限工具.是群文件清理管理员(event, 配置):
        return _ZLibrary静默回复流()
    return _ZLibrary注册回复流(配置)


async def 停止ZLibrary账号任务() -> None:
    任务列表 = list(ZLibrary注册任务集合)
    for 任务 in 任务列表:
        任务.cancel()
    await asyncio.gather(*任务列表, return_exceptions=True)
    ZLibrary注册任务集合.clear()


class _ZLibrary搜索结果解析器(HTMLParser):
    """解析上游搜索页中的 z-bookcard 书籍卡片。"""

    _空标签 = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.深度 = 0
        self.结果区深度: int | None = None
        self.当前卡片: dict[str, str] | None = None
        self.捕获字段: tuple[str, int, list[str]] | None = None
        self.卡片列表: list[dict[str, str]] = []

    @staticmethod
    def _读取属性(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {键.lower(): str(值 or "") for 键, 值 in attrs if 键}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        属性 = self._读取属性(attrs)
        if tag == "div" and 属性.get("id") == "searchResultBox":
            self.结果区深度 = self.深度
        elif tag == "z-bookcard" and self.结果区深度 is not None:
            self.当前卡片 = {
                "book_id": 属性.get("id", "").strip(),
                "href": 属性.get("href", "").strip(),
                "title": "",
                "authors": "",
            }
        elif self.当前卡片 is not None and tag == "div" and 属性.get("slot") in {"title", "author"}:
            self.捕获字段 = (属性["slot"], self.深度 + 1, [])
        if tag not in self._空标签:
            self.深度 += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self._空标签:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.捕获字段 is not None:
            self.捕获字段[2].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.捕获字段 is not None and self.深度 == self.捕获字段[1]:
            字段名, _深度, 文本片段 = self.捕获字段
            if self.当前卡片 is not None:
                self.当前卡片["title" if 字段名 == "title" else "authors"] = " ".join(文本片段)
            self.捕获字段 = None
        if tag == "z-bookcard" and self.当前卡片 is not None:
            self.卡片列表.append(self.当前卡片)
            self.当前卡片 = None
        if tag == "div" and self.结果区深度 == self.深度 - 1:
            self.结果区深度 = None
        if tag not in self._空标签:
            self.深度 = max(0, self.深度 - 1)


def _解析ZLibrary搜索结果(原始HTML: str, 需要数量: int) -> list[dict[str, Any]]:
    解析器 = _ZLibrary搜索结果解析器()
    解析器.feed(原始HTML)
    结果: list[dict[str, Any]] = []
    for 卡片 in 解析器.卡片列表:
        地址 = urljoin(ZLibrary搜索域名 + "/", html.unescape(卡片.get("href", "")))
        if not _是ZLibrary链接(地址):
            continue
        路径 = [段 for 段 in urlsplit(地址).path.split("/") if 段]
        编号 = str(卡片.get("book_id") or (路径[1] if len(路径) >= 2 else "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", 编号):
            continue
        书名 = re.sub(r"\s+", " ", html.unescape(卡片.get("title", ""))).strip()
        作者 = re.sub(r"\s+", " ", html.unescape(卡片.get("authors", ""))).strip()
        if not 书名:
            continue
        作者 = ", ".join(作者.split(";")) if 作者 else "未知"
        结果.append({
            "platform": "ZLibrary",
            "book_id": 编号,
            "title": 书名,
            "author": 作者,
            "url": 地址,
            "heat": 0,
            "score": 0,
            "read_count": 0,
            "word_count": 0,
        })
        if len(结果) >= max(1, min(int(需要数量 or 15), 50)):
            break
    return 结果


async def 搜索ZLibrary(
    关键词: str, *, 需要数量: int = 15, 配置: Any = None
) -> list[dict[str, Any]]:
    """通过已验证账号调用上游 search(q,count) 对应的书籍搜索页。"""
    查询 = str(关键词 or "").strip()
    if not 查询:
        return []
    async with ZLibrary搜索锁:
        账号 = await 获取ZLibrary搜索账号(配置)
        if not 账号:
            return []
        timeout = aiohttp.ClientTimeout(total=10, connect=5, sock_connect=5, sock_read=8)
        headers = {
            "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
            "Origin": ZLibrary搜索域名,
            "Referer": ZLibrary搜索域名 + "/",
        }
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            cookie_jar=aiohttp.CookieJar(unsafe=True),
            trust_env=False,
        ) as session:
            表单 = {
                "isModal": "true",
                "email": str(账号.get("email") or ""),
                "password": str(账号.get("password") or ""),
                "site_mode": "books",
                "action": "login",
                "isSingleLogin": "1",
                "redirectUrl": "",
                "gg_json_mode": "1",
            }
            try:
                async with session.post(
                    ZLibrary搜索登录URL, data=表单, allow_redirects=False
                ) as response:
                    if response.status != 200:
                        logger.debug("ZLibrary搜索登录失败：HTTP=%s", response.status)
                        return []
                    原始 = await response.content.read(1024 * 1024 + 1)
                    if len(原始) > 1024 * 1024:
                        return []
                    回复 = json.loads(原始.decode("utf-8"))
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, UnicodeError) as exc:
                logger.debug("ZLibrary搜索登录异常：错误类型=%s", type(exc).__name__)
                return []
            登录回复 = 回复.get("response") if isinstance(回复, dict) else None
            if not isinstance(登录回复, dict) or 登录回复.get("validationError"):
                logger.debug("ZLibrary搜索登录未确认")
                return []
            Cookies = {cookie.key: cookie.value for cookie in session.cookie_jar}
            认证字段 = {"remix_userid", "remix_userkey"}
            if not 认证字段.issubset(Cookies) or not all(Cookies.get(name) for name in 认证字段):
                logger.debug("ZLibrary搜索登录缺少认证Cookie")
                return []
            搜索地址 = ZLibrary搜索域名 + "/s/" + quote(查询, safe="")
            try:
                async with session.get(
                    搜索地址,
                    params={"page": "1"},
                    headers={"Cookie": "; ".join(f"{key}={value}" for key, value in Cookies.items())},
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        logger.debug("ZLibrary搜索失败：HTTP=%s", response.status)
                        return []
                    原始 = await response.content.read(ZLibrary搜索结果最大字节数 + 1)
                    if len(原始) > ZLibrary搜索结果最大字节数:
                        return []
                    return _解析ZLibrary搜索结果(
                        原始.decode("utf-8", "replace"), 需要数量
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.debug("ZLibrary搜索异常：错误类型=%s", type(exc).__name__)
                return []


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


def _解析HTML字段(原始: str) -> dict[str, Any]:
    if "diamwall" in 原始.lower() or "verifying your browser" in 原始.lower():
        raise _ZLibrary站点错误("Z-Library站点验证未通过")

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
    return {
        "title": 标题,
        "author": ", ".join(作者列表) or "未知",
        "download_url": 下载链接,
        "file_type": 详情文件类型,
    }


async def _请求详情(session: aiohttp.ClientSession, 来源: str) -> dict[str, Any]:
    try:
        async with session.get(来源, headers=_请求头(来源)) as response:
            if response.status in {403, 429, 503, 513}:
                raise _ZLibrary站点错误("Z-Library站点暂时不可访问")
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            原始 = await response.content.read(ZLibrary详情最大字节数 + 1)
            if len(原始) > ZLibrary详情最大字节数:
                raise _ZLibrary站点错误("Z-Library详情响应过大")
            最终来源 = str(response.url)
    except _ZLibrary站点错误:
        raise
    except Exception as exc:
        raise RuntimeError("Z-Library详情请求失败") from exc
    详情 = _解析HTML字段(原始.decode("utf-8", "replace"))
    if not _是ZLibrary链接(最终来源):
        raise _ZLibrary站点错误("Z-Library详情发生非站点跳转")
    书籍编号, 哈希 = 解析ZLibrary书籍编号(来源)
    详情["book_id"] = 书籍编号
    详情["hash"] = 哈希
    详情["detail_url"] = 最终来源
    if not 详情.get("title") or not 详情.get("download_url"):
        raise _ZLibrary站点错误("Z-Library详情缺少下载信息")
    详情["download_url"] = urljoin(最终来源, str(详情["download_url"]))
    return 详情


def _请求头(来源: str = "") -> dict[str, str]:
    地址 = urlsplit(来源)
    return {
        "Accept": "text/html,application/xhtml+xml,application/epub+zip,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Referer": f"{地址.scheme}://{地址.netloc}/" if 地址.netloc else "https://zh.z-library.sk/",
    }


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
                前缀 = 路径.read_bytes()[:4096].lower()
                if b"login" in 前缀 or b"diamwall" in 前缀 or b"verification" in 前缀:
                    raise _ZLibrary站点错误("Z-Library下载需要公开可用的文件地址")
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


def _读取EPUB正文(路径: Path) -> str:
    with zipfile.ZipFile(路径) as 压缩包:
        if sum(项目.file_size for 项目 in 压缩包.infolist()) > ZLibrary压缩后最大展开字节数:
            raise RuntimeError("EPUB解压后过大")
        opf路径 = ""
        try:
            容器 = ElementTree.fromstring(压缩包.read("META-INF/container.xml"))
            for 节点 in 容器.iter():
                if 节点.tag.rsplit("}", 1)[-1] == "rootfile":
                    opf路径 = str(节点.attrib.get("full-path") or "")
                    if opf路径:
                        break
        except Exception:
            pass
        if not opf路径:
            opf候选 = [项目 for 项目 in 压缩包.namelist() if 项目.lower().endswith(".opf")]
            opf路径 = opf候选[0] if opf候选 else ""
        if not opf路径:
            raise RuntimeError("EPUB缺少目录文件")
        opf = ElementTree.fromstring(压缩包.read(opf路径))
        清单: dict[str, str] = {}
        for 节点 in opf.iter():
            if 节点.tag.rsplit("}", 1)[-1] == "item":
                标识 = str(节点.attrib.get("id") or "")
                href = str(节点.attrib.get("href") or "")
                类型 = str(节点.attrib.get("media-type") or "").lower()
                if 标识 and href and ("html" in 类型 or href.lower().endswith((".xhtml", ".html", ".htm"))):
                    清单[标识] = posixpath.normpath(posixpath.join(posixpath.dirname(opf路径), href))
        正文路径: list[str] = []
        for 节点 in opf.iter():
            if 节点.tag.rsplit("}", 1)[-1] == "itemref":
                路径 = 清单.get(str(节点.attrib.get("idref") or ""))
                if 路径:
                    正文路径.append(路径)
        if not 正文路径:
            正文路径 = list(清单.values())
        片段 = [_清理正文(_解码文本(压缩包.read(路径))) for 路径 in 正文路径 if 路径 in 压缩包.namelist()]
    return "\n\n".join(项目 for 项目 in 片段 if 项目).strip()


def _读取FB2正文(路径: Path) -> str:
    return _读取FB2内容(路径.read_bytes())


def _读取FB2内容(原始: bytes) -> str:
    根节点 = ElementTree.fromstring(原始)
    片段: list[str] = []
    for 节点 in 根节点.iter():
        标签 = 节点.tag.rsplit("}", 1)[-1]
        if 标签 in {"title", "p", "subtitle", "text-author", "epigraph"}:
            文本 = _清理正文("".join(节点.itertext()))
            if 文本:
                片段.append(文本)
    return "\n\n".join(片段).strip()


def _读取PDF正文(路径: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("PDF解析库不可用") from exc
    读取器 = PdfReader(str(路径))
    return "\n\n".join(
        文本.strip()
        for 页面 in 读取器.pages
        for 文本 in [页面.extract_text() or ""]
        if 文本.strip()
    ).strip()


def _转换为正文(路径: Path, 文件名: str) -> str:
    后缀 = Path(文件名 or 路径.name).suffix.lower() or 路径.suffix.lower()
    with 路径.open("rb") as 文件:
        文件头 = 文件.read(5)
    if 后缀 == ".pdf" or 文件头 == b"%PDF-":
        return _读取PDF正文(路径)
    if zipfile.is_zipfile(路径):
        with zipfile.ZipFile(路径) as 压缩包:
            if sum(项目.file_size for 项目 in 压缩包.infolist()) > ZLibrary压缩后最大展开字节数:
                raise RuntimeError("电子书解压后过大")
            FB2路径 = next(
                (项目 for 项目 in 压缩包.namelist() if 项目.lower().endswith(".fb2")),
                None,
            )
            if FB2路径:
                return _读取FB2内容(压缩包.read(FB2路径))
        return _读取EPUB正文(路径)
    if 后缀 == ".fb2":
        return _读取FB2正文(路径)
    if 后缀 == ".pdf":
        return _读取PDF正文(路径)
    return _清理正文(_解码文本(路径.read_bytes()))


def _生成文件内容(详情: dict[str, Any], 正文: str) -> tuple[str, bytes]:
    标题 = _清理文件名(详情.get("title") or "Z-Library小说")
    作者 = _清理文件名(详情.get("author") or "未知")
    正文 = 去除章节正文重复标题(标题, 正文)
    if len(正文.strip()) < 2:
        raise RuntimeError("Z-Library正文为空")
    行列表 = [
        ZLibrary文件声明,
        "",
        f"书名：{标题}",
        f"作者：{作者}",
        "状态：电子书文件",
        "章节数：整本文件",
        "",
        标题,
        "",
        正文.strip(),
        "",
    ]
    文本 = "\n".join(行列表).replace("\r\n", "\n").replace("\r", "\n")
    return f"[完结]书名：{标题} 作者：{作者}.txt", 文本.replace("\n", "\r\n").encode("utf-8")


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
        trust_env=True,
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
        async with _创建ZLibrary会话() as session:
            阶段 = "detail"
            详情 = await _请求详情(session, 来源)
            logger.info(
                "Z-Library小说开始下载：书名=%s, 作者=%s, 下载文件=1",
                详情.get("title") or "未知",
                详情.get("author") or "未知",
            )
            yield 格式化ZLibrary下载提示(详情)
            阶段 = "download"
            临时路径, 原文件名 = await _下载原文件(session, 详情, 来源)
            阶段 = "convert"
            正文 = await asyncio.to_thread(_转换为正文, 临时路径, 原文件名)
            if len(re.sub(r"\s+", "", 正文)) < 2:
                raise RuntimeError("Z-Library正文为空")
            文件名, 内容 = await asyncio.to_thread(_生成文件内容, 详情, 正文)
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
            "Z-Library小说下载失败：阶段=%s, 错误类型=%s",
            阶段,
            type(exc).__name__,
        )
        yield ZLibrary下载失败提示
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
