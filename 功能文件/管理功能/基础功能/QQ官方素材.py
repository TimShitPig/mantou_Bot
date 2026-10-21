"""QQ 官方 Markdown 图片素材预上传，不保存图片或临时票据。"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
from typing import Any
from urllib.parse import quote, urlsplit

import aiohttp
from PIL import Image


图片大小上限 = 10 * 1024 * 1024
_响应上限 = 1024 * 1024
_图片类型 = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "WEBP": "image/webp"}


class QQ素材错误(RuntimeError):
    def __init__(self, stage: str, status: int | None = None, code: int | None = None):
        super().__init__(stage)
        self.stage, self.status, self.code = stage, status, code


def 读取图片资料(数据: bytes) -> dict[str, Any]:
    """只读取格式和尺寸，原字节直接上传，保留动画与画质。"""
    if not 数据 or len(数据) > 图片大小上限:
        raise QQ素材错误("image_size")
    try:
        with Image.open(io.BytesIO(数据)) as 图片:
            格式 = str(图片.format or "").upper()
            宽, 高 = 图片.size
    except Exception:
        raise QQ素材错误("image_format") from None
    if 格式 not in _图片类型 or 宽 <= 0 or 高 <= 0:
        raise QQ素材错误("image_format")
    后缀 = "jpg" if 格式 == "JPEG" else 格式.lower()
    return {"content_type": _图片类型[格式], "file_name": "image." + 后缀, "width": 宽, "height": 高}


async def _读取响应(响应: Any, 阶段: str) -> dict[str, Any]:
    数据 = bytearray()
    async for 块 in 响应.content.iter_chunked(65536):
        数据.extend(块)
        if len(数据) > _响应上限:
            raise QQ素材错误(阶段 + "_response_size", 响应.status)
    try:
        结果 = json.loads(数据)
    except (ValueError, UnicodeError):
        raise QQ素材错误(阶段 + "_response", 响应.status) from None
    if not isinstance(结果, dict):
        raise QQ素材错误(阶段 + "_response", 响应.status)
    业务码 = None
    for 键 in ("code", "err_code"):
        if 结果.get(键) not in (None, 0, "0", ""):
            try:
                业务码 = int(结果[键])
            except (TypeError, ValueError):
                业务码 = -1
            break
    if not 200 <= 响应.status < 300 or 业务码 is not None:
        raise QQ素材错误(阶段, 响应.status, 业务码)
    return 结果


async def _请求素材(http: Any, appid: str, 阶段: str, 请求体: dict[str, Any] | None, *, 路径: str = "", 方法: str = "POST") -> dict[str, Any]:
    # request() 的连接重置重试可能重放 POST；这里只提交一次。
    await http.check_session()
    请求头 = dict(getattr(http, "_headers", {}) or {})
    认证AppID = str(getattr(getattr(http, "_token", None), "app_id", "") or "")
    if not appid or 认证AppID != appid or not str(请求头.get("Authorization", "")).startswith("QQBot "):
        raise QQ素材错误("auth_mismatch")
    if getattr(http, "is_sandbox", False):
        raise QQ素材错误("sandbox")
    async with http._session.request(
        方法, "https://api.bot.qq.com/v2/media-images/" + (路径 or 阶段),
        json=请求体, headers=请求头, allow_redirects=False,
        timeout=aiohttp.ClientTimeout(total=10 if 方法 == "DELETE" else 30),
    ) as 响应:
        return await _读取响应(响应, 阶段)


async def 上传Markdown图片(http: Any, appid: str, 数据: bytes) -> dict[str, Any]:
    """申请素材、原字节 PUT、确认素材；引用仅供本次发送使用。"""
    资料 = await asyncio.to_thread(读取图片资料, 数据)
    MD5 = hashlib.md5(数据).hexdigest()
    准备 = await _请求素材(http, appid, "prepare", {
        "file_name": 资料["file_name"], "file_size": len(数据),
        "content_type": 资料["content_type"], "md5": MD5,
        "sha1": hashlib.sha1(数据).hexdigest(),
    })
    上传ID = str(准备.get("upload_id") or "")
    地址 = str(准备.get("presigned_url") or "")
    try:
        解析 = urlsplit(地址)
        有效地址 = (解析.scheme == "https"
                and bool(re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.myqcloud\.com", 解析.hostname or "")) and not 解析.username
                and not 解析.password and 解析.port in (None, 443) and not 解析.fragment)
    except ValueError:
        有效地址 = False
    if not 上传ID or not 有效地址:
        raise QQ素材错误("prepare_fields")
    # 独立会话不携带 SDK Authorization/Cookie，不跟随预签名地址重定向。
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=90, connect=15), trust_env=False,
        cookie_jar=aiohttp.DummyCookieJar(),
    ) as 客户端:
        async with 客户端.put(地址, data=数据, headers={"Content-Type": 资料["content_type"]}, allow_redirects=False) as 响应:
            if not 200 <= 响应.status < 300:
                raise QQ素材错误("upload", 响应.status)
            ETag = str(响应.headers.get("ETag") or "").strip('"').lower()
            if ETag and ETag != MD5:
                raise QQ素材错误("upload_etag", 响应.status)
    完成 = await _请求素材(http, appid, "complete", {"upload_id": 上传ID, "md5": MD5})
    引用 = str(完成.get("url") or "")
    图片ID = str(完成.get("image_id") or "")
    if (not re.fullmatch(r"qqbot-media://image/v1/[A-Za-z0-9._~%+=/-]+", 引用)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", 图片ID)):
        raise QQ素材错误("complete_fields")
    return {"url": 引用, "image_id": 图片ID, "width": 资料["width"], "height": 资料["height"]}


async def 删除已发送素材(http: Any, appid: str, 图片ID: str) -> None:
    """发送成功已转存后仅释放本次素材，已发送消息不受影响。"""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", str(图片ID or "")):
        raise QQ素材错误("delete_fields")
    await _请求素材(http, appid, "delete", None, 路径=quote(图片ID, safe="") + "/delete", 方法="DELETE")
