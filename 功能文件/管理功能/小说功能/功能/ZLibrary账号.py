"""管理员触发的 API 自动注册；账号仅存 MySQL，不参与公开下载器。"""
from __future__ import annotations

import asyncio
import datetime as dt
import html
import json
import logging
import re
import secrets
import time
import uuid
from typing import Any
from urllib.parse import quote

import aiohttp
from 功能文件.管理功能.基础功能 import 权限工具, 运行状态数据库

logger = logging.getLogger(__name__)
账号命名空间 = "zlibrary_accounts"
_任务: set[asyncio.Task] = globals().get("_任务", set())
_最近启动 = globals().get("_最近启动", 0.0)


class 注册错误(RuntimeError):
    def __init__(self, 阶段: str, 状态: str, http状态: int = 0):
        self.阶段, self.状态, self.http状态 = 阶段, 状态, http状态
        super().__init__(f"{阶段}:{状态}:{http状态}")


async def _请求(session, 方法, url, 阶段, **参数):
    # 拒绝跳转，防止向其他站点转发邮箱 Key、Token 或注册凭据。
    async with session.request(方法, url, allow_redirects=False, **参数) as response:
        raw = bytearray()
        async for block in response.content.iter_chunked(65536):
            raw.extend(block)
            if len(raw) > 2 * 1024 * 1024:
                raise 注册错误(阶段, "response_too_large", response.status)
        if not 200 <= response.status < 300:
            raise 注册错误(阶段, "http_error", response.status)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise 注册错误(阶段, "invalid_json", response.status) from exc
        if not isinstance(data, dict) or any(data.get(k) for k in ("error", "errors", "_error")):
            raise 注册错误(阶段, "business_error", response.status)
        return data


def _验证码(message: dict, address: str) -> str | None:
    recipients = message.get("to")
    if not isinstance(recipients, list) or not any(
        isinstance(item, dict) and str(item.get("address", "")).lower() == address.lower()
        for item in recipients
    ):
        return None
    sender = message.get("from")
    sender = sender.get("address", "") if isinstance(sender, dict) else ""
    domain = str(sender).rsplit("@", 1)[-1].lower()
    if not any(domain == d or domain.endswith("." + d) for d in ("libb.la", "z-lib.fm", "1lib.sk")):
        return None
    subject = str(message.get("subject", ""))
    if not re.search(r"verification|verify|confirmation|confirm|sign.?up|registration|验证码|验证|注册", subject, re.I):
        return None
    code = message.get("verificationCode")
    if isinstance(code, str) and re.fullmatch(r"[0-9]{4}", code):
        return code
    parts = [str(message.get(k) or "")[:256000] for k in ("subject", "intro", "text")]
    body = message.get("html")
    if isinstance(body, str):
        parts.append(body[:256000])
    elif isinstance(body, list):
        parts.extend(v[:256000] for v in body if isinstance(v, str))
    text = html.unescape(" ".join(parts))
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text)
    keyword = r"(?:verification|verify|confirmation|confirm|security|one[\s-]?time|otp|验证码|校验码|確認碼|确认码|驗證碼)"
    match = re.search(
        rf"{keyword}[^0-9]{{0,80}}(?<![0-9])([0-9]{{4}})(?![0-9])|(?<![0-9])([0-9]{{4}})(?![0-9])[^0-9]{{0,80}}{keyword}",
        text, re.I,
    )
    return (match.group(1) or match.group(2)) if match else None


def _业务回复(payload: dict, 阶段: str) -> dict:
    response = payload.get("response")
    if not isinstance(response, dict) or not response:
        raise 注册错误(阶段, "unconfirmed")
    if any(response.get(k) for k in ("validationError", "error", "errors", "_error")):
        raise 注册错误(阶段, "business_error")
    return response


def _重定向成功(response: dict, login: bool = False) -> bool:
    field = "priorityRedirectUrl" if login else "forceRedirection"
    return bool(
        (isinstance(response.get(field), str) and response[field])
        or (isinstance(response.get("regularDomains"), (list, dict)) and response["regularDomains"]
            and isinstance(response.get("params"), str) and response["params"])
    )


async def 自动创建账号(api_key: str, 保存账号, rx: str = "215", *,
                 邮箱地址: str = "https://maliapi.215.im/v1",
                 站点地址: str = "https://libb.la", 等待秒数: float = 120,
                 轮询间隔: float = 5) -> str:
    """保存账号为异步回调；测试可注入本地端点，生产端点由代码固定。"""
    if not api_key.startswith("AC-") or not rx.strip():
        raise 注册错误("config", "invalid_config")
    attempt = uuid.uuid4().hex
    password = secrets.token_urlsafe(15)  # 20 位，不使用邮箱作密码。
    name = "Reader" + secrets.token_hex(4)
    timeout = aiohttp.ClientTimeout(total=25, connect=10)
    mail_headers = {"Accept": "application/json", "User-Agent": "YYDSMailClient/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=mail_headers,
                                   cookie_jar=aiohttp.DummyCookieJar()) as mail:
        created = await _请求(mail, "POST", 邮箱地址 + "/accounts", "mail_create",
                            headers={"X-API-Key": api_key, "Idempotency-Key": attempt},
                            json={"localPart": "m" + secrets.token_hex(8)})
        data = created.get("data")
        if created.get("success") is not True or not isinstance(data, dict):
            raise 注册错误("mail_create", "unconfirmed")
        address, token, mailbox_id = data.get("address"), data.get("token"), data.get("id")
        if not isinstance(address, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", address):
            raise 注册错误("mail_create", "invalid_address")
        if not isinstance(token, str) or not token or not isinstance(mailbox_id, str) or not mailbox_id:
            raise 注册错误("mail_create", "missing_mailbox")
        mail_auth = {"Authorization": "Bearer " + token}
        fields = {"email": address, "password": password, "name": name, "rx": rx,
                  "action": "registration", "redirectUrl": ""}
        headers = {"Accept": "application/json", "Origin": 站点地址,
                   "Referer": 站点地址 + "/registration", "X-Requested-With": "XMLHttpRequest"}
        account = {"email": address, "password": password, "name": name,
                   "status": "pending", "created_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        # 注册前保存凭据；即使保存/登录后续出错，也不会丢失已创建的账号。
        await 保存账号(attempt, dict(account))
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as site:
            form = aiohttp.FormData()
            for key, value in fields.items():
                form.add_field(key, value, content_type="text/plain")
            since = dt.datetime.now(dt.timezone.utc)
            sent = await _请求(site, "POST", 站点地址 + "/papi/user/verification/send-code", "send_code", data=form)
            if sent.get("success") not in (1, True):
                raise 注册错误("send_code", "unconfirmed")
            code = None
            checked = set()
            # 整段轮询受硬超时约束，包括详情请求和 sleep。
            try:
                async with asyncio.timeout(等待秒数):
                    while code is None:
                        inbox = await _请求(mail, "GET", 邮箱地址 + "/inboxes/" + quote(mailbox_id, safe="") + "/messages", "mail_read",
                                          headers=mail_auth, params={"since": since.isoformat(), "seen": "false", "limit": "200"})
                        messages = inbox.get("data", {}).get("messages") if isinstance(inbox.get("data"), dict) else None
                        if inbox.get("success") is not True or not isinstance(messages, list):
                            raise 注册错误("mail_read", "unconfirmed")
                        for summary in messages:
                            if not isinstance(summary, dict):
                                continue
                            ident = summary.get("id")
                            if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", ident) or ident in checked:
                                continue
                            detailed = await _请求(mail, "GET", 邮箱地址 + "/messages/" + quote(ident, safe=""), "mail_read",
                                                 headers=mail_auth, params={"address": address})
                            message = detailed.get("data")
                            if detailed.get("success") is not True or not isinstance(message, dict):
                                raise 注册错误("mail_read", "unconfirmed")
                            try:
                                stamp = dt.datetime.fromisoformat(str(message.get("createdAt") or summary.get("createdAt") or "").replace("Z", "+00:00"))
                            except ValueError:
                                continue
                            if stamp.tzinfo is None or stamp < since:
                                checked.add(ident)
                                continue
                            code = _验证码(message, address)
                            if code:
                                break
                        if code is None:
                            await asyncio.sleep(轮询间隔)
            except TimeoutError as exc:
                raise 注册错误("mail_read", "code_timeout") from exc
            response = _业务回复(await _请求(site, "POST", 站点地址 + "/rpc.php", "registration",
                data={**fields, "verifyCode": code, "isModal": "true", "gg_json_mode": "1"}), "registration")
            if not _重定向成功(response):
                raise 注册错误("registration", "unconfirmed")
            account["status"] = "registered"
            await 保存账号(attempt, dict(account))
        # 独立 CookieJar，避免把注册会话的 Cookie 误认为登录返回结果。
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as login:
            response = _业务回复(await _请求(login, "POST", 站点地址 + "/rpc.php", "login", data={
                "email": address, "password": password, "action": "login", "site_mode": "books",
                "isSingleLogin": "1", "isModal": "true", "redirectUrl": "", "gg_json_mode": "1",
            }), "login")
            cookies = login.cookie_jar.filter_cookies(aiohttp.client_reqrep.URL(站点地址))
            if not _重定向成功(response, True) or not all(cookies.get(k) and cookies[k].value for k in ("remix_userid", "remix_userkey")):
                raise 注册错误("login", "unconfirmed")
        account["status"] = "logged_in"
        await 保存账号(attempt, dict(account))
    return attempt


async def _注册并保存(配置):
    分类 = 运行状态数据库.读取配置字段(配置, "zlibrary_account_settings") or 配置
    key = str(运行状态数据库.读取配置字段(分类, "zlibrary_mail_api_key") or "").strip()
    rx = str(运行状态数据库.读取配置字段(分类, "zlibrary_registration_rx") or "215").strip()
    if not key:
        return "请先配置邮箱 API Key"
    if await asyncio.to_thread(运行状态数据库.检查运行状态数据库, 配置) != "正常":
        return "请先配置并连接数据库"

    async def 保存(标识, 数据):
        await asyncio.to_thread(运行状态数据库.写入运行状态值, 配置, 账号命名空间, 标识,
                               json.dumps(数据, ensure_ascii=False))

    try:
        await 自动创建账号(key, 保存, rx)
    except 注册错误 as exc:
        logger.warning("ZLibrary创建账号失败：阶段=%s 状态=%s HTTP=%s", exc.阶段, exc.状态, exc.http状态)
        return "账号创建流程未完成，请稍后再试"
    except Exception as exc:
        logger.warning("ZLibrary创建账号失败：类型=%s", type(exc).__name__)
        return "账号创建流程未完成，请稍后再试"
    return "账号注册成功，登录返回成功，账号已保存到数据库"


async def _回复流(配置):
    global _最近启动
    if _任务 or time.monotonic() - _最近启动 < 60:
        yield "账号创建处理中，请稍后再试"
        return
    _最近启动 = time.monotonic()
    task = asyncio.create_task(_注册并保存(配置))
    _任务.add(task)
    try:
        yield "正在自动获取邮箱并创建账号，请稍等"
        yield await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        _任务.discard(task)


async def _静默():
    if False:
        yield ""


def 获取ZLibrary账号回复流(event: Any, 命令文本: str, 配置: Any):
    if str(命令文本).strip().lower() not in {"注册zlibrary", "创建zlibrary账号"}:
        return None
    if not 权限工具.是QQ官方机器人(event) or not 权限工具.是群文件清理管理员(event, 配置):
        return _静默()
    return _回复流(配置)


async def 停止ZLibrary账号任务():
    tasks = list(_任务)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _任务.clear()
