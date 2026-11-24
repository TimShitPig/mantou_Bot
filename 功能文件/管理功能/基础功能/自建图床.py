"""自建图床原字节上传；凭据由当前机器人的受保护配置传入。"""
from __future__ import annotations

import asyncio
import io
import json
import weakref
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from PIL import Image


图床地址 = "https://mantou-imgbed.pages.dev"
图片大小上限 = 10 * 1024 * 1024
_响应上限 = 64 * 1024
_图片类型 = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "WEBP": "image/webp"}
_上传额度 = globals().get("_上传额度")
if _上传额度 is None:
    _上传额度 = weakref.WeakKeyDictionary()


class 图床错误(RuntimeError):
    def __init__(self, stage: str, status: int | None = None):
        super().__init__(stage)
        self.stage, self.status = stage, status


def 读取图片资料(数据: bytes) -> dict[str, Any]:
    """只读取格式与尺寸，保留动画和原始图片字节。"""
    if not isinstance(数据, bytes) or not 数据 or len(数据) > 图片大小上限:
        raise 图床错误("image_size")
    try:
        with Image.open(io.BytesIO(数据)) as 图片:
            格式 = str(图片.format or "").upper()
            宽, 高 = 图片.size
    except Exception:
        raise 图床错误("image_format") from None
    if 格式 not in _图片类型 or 宽 <= 0 or 高 <= 0:
        raise 图床错误("image_format")
    后缀 = "jpg" if 格式 == "JPEG" else 格式.lower()
    return {"content_type": _图片类型[格式], "file_name": "image." + 后缀, "width": 宽, "height": 高}


def _规范图片地址(值: Any) -> str:
    if not isinstance(值, str) or not 值 or len(值) > 4096:
        raise 图床错误("response_url")
    if any(字符.isspace() or ord(字符) < 32 or ord(字符) == 127 for 字符 in 值):
        raise 图床错误("response_url")
    if 值.startswith("/file/"):
        值 = 图床地址 + 值
    try:
        地址 = urlsplit(值)
        有效 = (
            地址.scheme == "https" and 地址.hostname == "mantou-imgbed.pages.dev"
            and 地址.port in (None, 443) and 地址.username is None and 地址.password is None
            and 地址.path.startswith("/file/") and len(地址.path) > len("/file/")
            and not 地址.query and not 地址.fragment and "\\" not in 地址.path
        )
    except ValueError:
        有效 = False
    if not 有效:
        raise 图床错误("response_url")
    return 值


async def _读取上传结果(响应: Any) -> str:
    if 响应.status != 200:
        raise 图床错误("upload", 响应.status)
    原文 = bytearray()
    async for 块 in 响应.content.iter_chunked(16384):
        原文.extend(块)
        if len(原文) > _响应上限:
            raise 图床错误("response_size", 响应.status)
    try:
        结果 = json.loads(原文)
    except (ValueError, UnicodeError):
        raise 图床错误("response_json", 响应.status) from None
    if isinstance(结果, list) and len(结果) == 1:
        结果 = 结果[0]
    if not isinstance(结果, dict):
        raise 图床错误("response_fields", 响应.status)
    return _规范图片地址(结果.get("src"))


async def 上传图片(数据: bytes, 上传密码: str) -> dict[str, Any]:
    """每次只提交一次 POST，不切换渠道，不重放失败或取消的上传。"""
    if not isinstance(上传密码, str) or not 上传密码:
        raise 图床错误("not_configured")
    if len(上传密码) > 256 or any(字符.isspace() or ord(字符) < 32 or 127 <= ord(字符) <= 159 for 字符 in 上传密码):
        raise 图床错误("invalid_config")
    资料 = await asyncio.to_thread(读取图片资料, 数据)
    循环 = asyncio.get_running_loop()
    额度 = _上传额度.get(循环)
    if 额度 is None:
        额度 = asyncio.Semaphore(8)
        _上传额度[循环] = 额度

    async def 提交() -> str:
        async with 额度:
            表单 = aiohttp.FormData()
            表单.add_field("file", 数据, filename=资料["file_name"], content_type=资料["content_type"])
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=75, connect=15),
                cookie_jar=aiohttp.DummyCookieJar(), trust_env=False,
            ) as 客户端:
                if hasattr(客户端, "_retry_connection"):
                    客户端._retry_connection = False
                async with 客户端.post(
                    图床地址 + "/upload", data=表单,
                    headers={"authCode": 上传密码}, allow_redirects=False,
                    params={"uploadChannel": "telegram", "channelName": "自建图床",
                            "serverCompress": "false", "autoRetry": "false",
                            "returnFormat": "full", "responseFormat": "object",
                            "uploadFolder": "mantou-bot/images"},
                ) as 响应:
                    return await _读取上传结果(响应)

    try:
        地址 = await asyncio.wait_for(提交(), timeout=90)
    except asyncio.CancelledError:
        raise
    except (asyncio.TimeoutError, TimeoutError):
        raise 图床错误("timeout") from None
    except aiohttp.ClientError:
        raise 图床错误("request") from None
    return {"url": 地址, "width": 资料["width"], "height": 资料["height"]}
