"""从本地原图取得 QQ Markdown 素材引用；仅缓存素材元数据，不保存认证票据。"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import io
import json
import re
import time
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from PIL import Image


图片大小上限 = 10 * 1024 * 1024
_响应上限 = 1024 * 1024
_图片类型 = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "WEBP": "image/webp"}
_素材缓存 = globals().get("_素材缓存") or {}
_素材上传任务 = globals().get("_素材上传任务") or {}
_结果未知素材 = globals().get("_结果未知素材") or {}


class QQ素材错误(RuntimeError):
    def __init__(self, stage: str, status: int | None = None, code: int | None = None, *, unknown: bool = False):
        super().__init__(stage)
        self.stage = stage
        self.status = status if type(status) is int else None
        self.code = code if type(code) is int else None
        self.unknown = unknown


def _校验认证(http: Any, appid: str) -> None:
    当前 = str(getattr(getattr(http, "_token", None), "app_id", "") or "").strip()
    if not re.fullmatch(r"[0-9]{4,32}", appid) or 当前 != appid:
        raise QQ素材错误("auth_mismatch")
    if getattr(http, "is_sandbox", False):
        raise QQ素材错误("sandbox")


def 读取图片资料(数据: bytes) -> dict[str, Any]:
    """校验格式和可解码性，不转码或改动原字节。"""
    if not isinstance(数据, bytes) or not 数据 or len(数据) > 图片大小上限:
        raise QQ素材错误("image_size")
    try:
        with Image.open(io.BytesIO(数据)) as 图片:
            格式 = str(图片.format or "").upper()
            宽, 高 = 图片.size
            图片.verify()
        with Image.open(io.BytesIO(数据)) as 图片:
            图片.load()
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
            raise QQ素材错误(阶段 + "_response_size", 响应.status, unknown=True)
    try:
        结果 = json.loads(数据)
    except (ValueError, UnicodeError):
        raise QQ素材错误(阶段 + "_response", 响应.status, unknown=True) from None
    if not isinstance(结果, dict):
        raise QQ素材错误(阶段 + "_response", 响应.status, unknown=True)
    业务码 = None
    for 键 in ("code", "err_code"):
        值 = 结果.get(键)
        if 值 in (None, 0, "0", "") and not isinstance(值, bool):
            continue
        if type(值) is int:
            业务码 = 值
        elif isinstance(值, str) and re.fullmatch(r"-?[0-9]{1,10}", 值):
            业务码 = int(值)
        else:
            raise QQ素材错误(阶段 + "_response", 响应.status, unknown=True)
        break
    if not 200 <= 响应.status < 300 or 业务码 is not None:
        raise QQ素材错误(阶段, 响应.status, 业务码, unknown=响应.status >= 500)
    return 结果


async def _请求素材(http: Any, appid: str, 阶段: str, 请求体: dict[str, Any]) -> dict[str, Any]:
    if 阶段 not in {"prepare", "complete"}:
        raise QQ素材错误("invalid_operation")
    _校验认证(http, appid)
    await http.check_session()
    _校验认证(http, appid)
    请求头 = dict(getattr(http, "_headers", {}) or {})
    访问令牌 = getattr(getattr(http, "_token", None), "access_token", None)
    if (not isinstance(访问令牌, str) or not 访问令牌
            or 请求头.get("Authorization") != "QQBot " + 访问令牌
            or str(请求头.get("X-Union-Appid", "")) != appid):
        raise QQ素材错误("auth_mismatch")
    # SDK request() 可能包含连接重试；素材 POST 只提交一次。
    try:
        async with http._session.request(
            "POST", "https://api.bot.qq.com/v2/media-images/" + 阶段,
            json=请求体, headers=请求头, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=30),
        ) as 响应:
            return await _读取响应(响应, 阶段)
    except asyncio.CancelledError:
        raise
    except QQ素材错误:
        raise
    except Exception:
        raise QQ素材错误(阶段 + "_unknown", unknown=True) from None


async def 上传Markdown图片(http: Any, appid: str, 数据: bytes) -> dict[str, Any]:
    """申请、原字节 PUT、确认各提交一次；预签名地址只进入无认证的独立会话。"""
    _校验认证(http, appid)
    资料 = await asyncio.to_thread(读取图片资料, 数据)
    MD5 = hashlib.md5(数据).hexdigest()
    准备 = await _请求素材(http, appid, "prepare", {
        "file_name": 资料["file_name"], "file_size": len(数据), "content_type": 资料["content_type"],
        "md5": MD5, "sha1": hashlib.sha1(数据).hexdigest(),
    })
    上传ID = str(准备.get("upload_id") or "")
    地址 = str(准备.get("presigned_url") or "")
    try:
        解析 = urlsplit(地址)
        有效 = (解析.scheme == "https" and bool(re.fullmatch(
            r"[a-z0-9][a-z0-9-]*-[0-9]+\.cos\.[a-z0-9-]+\.myqcloud\.com", 解析.hostname or ""))
            and 解析.username is None and 解析.password is None and 解析.port in (None, 443) and not 解析.fragment)
    except ValueError:
        有效 = False
    if not 上传ID or not 有效:
        raise QQ素材错误("prepare_fields", unknown=True)
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=90, connect=15), trust_env=False,
            cookie_jar=aiohttp.DummyCookieJar(),
        ) as 客户端:
            if hasattr(客户端, "_retry_connection"):
                客户端._retry_connection = False
            async with 客户端.put(地址, data=数据, headers={"Content-Type": 资料["content_type"]}, allow_redirects=False) as 响应:
                if not 200 <= 响应.status < 300:
                    raise QQ素材错误("upload", 响应.status)
                ETag = str(响应.headers.get("ETag") or "").strip('"').lower()
                if ETag and ETag != MD5:
                    raise QQ素材错误("upload_etag", 响应.status)
    except asyncio.CancelledError:
        raise
    except QQ素材错误:
        raise
    except Exception:
        raise QQ素材错误("upload_unknown", unknown=True) from None
    完成 = await _请求素材(http, appid, "complete", {"upload_id": 上传ID, "md5": MD5})
    引用, 图片ID, 有效期 = 完成.get("url"), 完成.get("image_id"), 完成.get("ttl")
    if (not isinstance(引用, str) or not re.fullmatch(r"qqbot-media://image/v1/[A-Za-z0-9._~%+=/-]+", 引用)
            or not isinstance(图片ID, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", 图片ID)
            or type(有效期) is not int or not 0 < 有效期 <= 7776000):
        raise QQ素材错误("complete_fields", unknown=True)
    return {"url": 引用, "image_id": 图片ID, "width": 资料["width"], "height": 资料["height"], "ttl": 有效期}


async def 获取Markdown图片(http: Any, appid: str, 数据: bytes) -> dict[str, Any]:
    """按认证 AppID 和原图摘要单飞；取消等待者也等待本次上传收尾，不重传未知结果。"""
    _校验认证(http, appid)
    键 = appid, hashlib.sha256(数据).hexdigest()
    已存 = _素材缓存.get(键)
    if isinstance(已存, dict) and float(已存.get("cache_until") or 0) > time.time():
        return copy.deepcopy(已存)
    未知 = _结果未知素材.get(键)
    if isinstance(未知, dict):
        raise QQ素材错误(未知["stage"], 未知.get("status"), 未知.get("code"), unknown=True)
    任务 = _素材上传任务.get(键)
    if 任务 is None:
        async def 单次上传() -> dict[str, Any]:
            try:
                结果 = await 上传Markdown图片(http, appid, 数据)
                # complete.ttl 是官方滑动窗口；本地只保守使用这次确认时的截止，不伪造 expires_at。
                有效期 = 结果["ttl"]
                结果["cache_until"] = time.time() + 有效期 - min(60, max(1, 有效期 // 10))
                _素材缓存[键] = copy.deepcopy(结果)
                return 结果
            except asyncio.CancelledError:
                _结果未知素材[键] = {"stage": "cancelled_unknown"}
                raise
            except QQ素材错误 as 异常:
                if 异常.unknown:
                    _结果未知素材[键] = {"stage": 异常.stage, "status": 异常.status, "code": 异常.code}
                raise
            finally:
                if _素材上传任务.get(键) is asyncio.current_task():
                    _素材上传任务.pop(键, None)
        任务 = asyncio.create_task(单次上传(), name="QQ教程本地素材上传")
        _素材上传任务[键] = 任务
    try:
        return copy.deepcopy(await asyncio.shield(任务))
    except asyncio.CancelledError:
        while not 任务.done():
            try:
                await asyncio.shield(任务)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not 任务.cancelled():
            任务.exception()
        raise
