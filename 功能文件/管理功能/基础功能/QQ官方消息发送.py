"""保留 QQ 发送响应的受控数字错误，不重放提交结果未知的消息。"""
from __future__ import annotations

import ast
import asyncio
import json
import math
import re
from typing import Any
from urllib.parse import urlsplit

import aiohttp


_响应字节上限 = 16 * 1024
_响应读取秒数 = 10.0
_错误字段 = {
    "http_status": ("status", "status_code", "http_status"),
    "code": ("code", "ret_code", "error_code"),
    "err_code": ("err_code", "business_code"),
}


def _数字(值: Any) -> int | None:
    if isinstance(值, bool) or not isinstance(值, (int, str)):
        return None
    文本 = str(值).strip()
    return int(文本) if re.fullmatch(r"-?[0-9]{1,10}", 文本) else None


class QQ消息发送错误(RuntimeError):
    def __init__(self, status: Any = None, code: Any = None, err_code: Any = None, *, reason: str = "http_error"):
        self.status = _数字(status)
        if self.status is not None and not 100 <= self.status <= 599:
            self.status = None
        self.code, self.err_code = _数字(code), _数字(err_code)
        self.reason = reason if reason in {
            "http_error", "business_error", "invalid_json", "invalid_response",
            "response_too_large", "auth_mismatch", "invalid_route", "invalid_reply",
            "timeout", "network",
        } else "http_error"
        super().__init__("QQ消息发送失败（" + self.reason + "）")


def 提取QQ消息错误字段(异常: Any) -> dict[str, int | None]:
    """只从明确属性或完整有界字典读取数字，不扫描异常文字中的编号。"""
    结果: dict[str, int | None] = {键: None for 键 in _错误字段}
    for 键, 别名 in _错误字段.items():
        for 名称 in 别名:
            值 = _数字(getattr(异常, 名称, None))
            if 值 is not None:
                结果[键] = 值
                break
    for 原始 in (*getattr(异常, "args", ()), getattr(异常, "msgs", None)):
        if isinstance(原始, str):
            if len(原始) > _响应字节上限:
                continue
            原始 = 原始.strip()
            if not (原始.startswith("{") and 原始.endswith("}")):
                continue
            try:
                原始 = json.loads(原始)
            except (ValueError, RecursionError):
                try:
                    原始 = ast.literal_eval(原始)
                except (ValueError, SyntaxError, MemoryError, RecursionError):
                    continue
        if not isinstance(原始, dict):
            continue
        for 键, 别名 in _错误字段.items():
            if 结果[键] is not None:
                continue
            for 名称 in 别名:
                值 = _数字(原始.get(名称))
                if 值 is not None:
                    结果[键] = 值
                    break
    状态 = 结果["http_status"]
    if 状态 is not None and not 100 <= 状态 <= 599:
        结果["http_status"] = None
    return 结果


def 主动消息权限被拒绝(异常: Any) -> bool:
    字段 = 提取QQ消息错误字段(异常)
    return 40034105 in (字段["code"], 字段["err_code"])


def 被动回复已过期(异常: Any) -> bool:
    字段 = 提取QQ消息错误字段(异常)
    if any(字段[键] not in (None, 0) for 键 in ("code", "err_code")):
        return 40034005 in (字段["code"], 字段["err_code"])
    # 兼容只保留 message 的旧 SDK，仅接受明确 msg_id 过期描述。
    文本 = str(getattr(异常, "msgs", None) or 异常).strip().lower()
    return len(文本) <= 1024 and any(字 in 文本 for 字 in ("过期", "expired")) and any(
        字 in 文本 for 字 in ("msg_id", "msgid", "消息id", "消息 id")
    )


def QQ消息错误分类(异常: Any) -> str:
    字段 = 提取QQ消息错误字段(异常)
    状态 = 字段["http_status"]
    业务码 = {字段["code"], 字段["err_code"]}
    if 状态 == 429 or 40034100 in 业务码:
        return "rate_limit"
    for 码, 分类 in (
        (40034105, "permissions_denied"), (40034127, "markdown_permission_denied"),
        (40034005, "reply_expired"), (40034006, "content_violation"),
        (40034024, "invalid_msg_id"), (40034025, "invalid_event_id"),
        (40034026, "event_expired"), (40034027, "unsupported_event"),
        (40034128, "reply_limit"),
    ):
        if 码 in 业务码:
            return 分类
    if 状态 == 401 or 100016 in 业务码 or 11243 in 业务码:
        return "credential_invalid"
    if 状态 == 403:
        return "access_denied"
    if 状态 is not None and 状态 >= 500:
        return "server_error"
    if isinstance(异常, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(异常, (aiohttp.ClientError, OSError)):
        return "network"
    if isinstance(异常, QQ消息发送错误) and 异常.reason not in {"http_error", "business_error"}:
        return 异常.reason
    return "request_failed"


async def 提交QQ消息(http: Any, route: Any, payload: dict[str, Any], appid: str) -> dict[str, Any]:
    """复用 SDK 的认证与会话，仅提交一次固定官方群/私聊消息 POST。"""
    if (getattr(route, "method", "") != "POST" or getattr(route, "path", "") not in {
        "/v2/groups/{group_openid}/messages", "/v2/users/{openid}/messages"
    }):
        raise QQ消息发送错误(reason="invalid_route")
    if payload.get("msg_id") and payload.get("event_id"):
        raise QQ消息发送错误(reason="invalid_reply")
    if str(getattr(getattr(http, "_token", None), "app_id", "")) != appid:
        raise QQ消息发送错误(reason="auth_mismatch")
    route.is_sandbox = bool(getattr(http, "is_sandbox", False))
    地址 = urlsplit(route.url)
    if (地址.scheme != "https" or 地址.netloc not in {
        "api.sgroup.qq.com", "sandbox.api.sgroup.qq.com", "api.bot.qq.com"
    } or 地址.query or 地址.fragment or not re.fullmatch(
        r"/v2/(?:groups|users)/[A-Za-z0-9_-]{5,128}/messages", 地址.path
    )):
        raise QQ消息发送错误(reason="invalid_route")
    await http.check_session()
    令牌 = getattr(http, "_token", None)
    会话 = getattr(http, "_session", None)
    请求头 = dict(getattr(http, "_headers", None) or {})
    访问令牌 = getattr(令牌, "access_token", None)
    if (not re.fullmatch(r"[0-9]{4,32}", appid)
        or str(getattr(令牌, "app_id", "")) != appid
        or str(请求头.get("X-Union-Appid", "")) != appid
        or not isinstance(访问令牌, str) or not 访问令牌
        or 请求头.get("Authorization") != "QQBot " + 访问令牌
        or 会话 is None or getattr(会话, "closed", True)):
        raise QQ消息发送错误(reason="auth_mismatch")
    超时 = float(getattr(http, "timeout", 30))
    if not math.isfinite(超时) or 超时 <= 0:
        超时 = 30.0
    async with 会话.request(
        method="POST", url=route.url, json=payload, headers=请求头,
        timeout=aiohttp.ClientTimeout(total=超时), allow_redirects=False,
    ) as 响应:
        状态 = 响应.status

        async def 读取() -> bytes:
            内容 = bytearray()
            async for 块 in 响应.content.iter_chunked(4096):
                内容.extend(块)
                if len(内容) > _响应字节上限:
                    raise QQ消息发送错误(状态, reason="response_too_large")
            return bytes(内容)

        try:
            内容 = await asyncio.wait_for(读取(), timeout=_响应读取秒数)
        except asyncio.TimeoutError:
            raise QQ消息发送错误(状态, reason="timeout") from None
        except (aiohttp.ClientError, OSError):
            raise QQ消息发送错误(状态, reason="network") from None
        try:
            结果 = json.loads(内容)
        except (ValueError, UnicodeError, RecursionError):
            raise QQ消息发送错误(状态, reason="invalid_json") from None
        if not isinstance(结果, dict):
            raise QQ消息发送错误(状态, reason="invalid_response")
        错误 = QQ消息发送错误(状态, 结果.get("code"), 结果.get("err_code"))
        if not 200 <= 状态 < 300:
            raise 错误
        if any(原值 not in (None, "", 0, "0") or isinstance(原值, bool)
               for 原值 in (结果.get("code"), 结果.get("err_code"))):
            raise QQ消息发送错误(状态, 错误.code, 错误.err_code, reason="business_error")
        消息ID = 结果.get("id")
        if not isinstance(消息ID, str) or not 消息ID.strip() or len(消息ID) > 512:
            raise QQ消息发送错误(状态, reason="invalid_response")
        return 结果
