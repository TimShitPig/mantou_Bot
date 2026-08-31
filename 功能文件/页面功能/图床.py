"""聊天媒体图床上传适配。

默认使用 0x0.st 的匿名 multipart 接口；管理员可以在插件配置中替换为
兼容 ``file`` 字段和 URL 返回值的自建图床。媒体上传失败时由调用方决定
是否提示用户，模块本身不把远端响应原文返回给聊天或网页。
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
from pathlib import Path
from typing import Any, AsyncIterable
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, FormData
from aiohttp.payload import AsyncIterablePayload

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)


默认图床上传地址 = "https://0x0.st"
图床请求超时秒 = 60
图床最大上传字节数 = 200 * 1024 * 1024
图床最大响应字节数 = 64 * 1024
图床返回地址规则 = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _配置字典(配置: Any) -> dict[str, Any]:
    if isinstance(配置, dict):
        return 配置
    for 属性名 in ("data", "obj"):
        数据 = getattr(配置, 属性名, None)
        if isinstance(数据, dict):
            return 数据
    获取配置 = getattr(配置, "get_config", None)
    if callable(获取配置):
        try:
            数据 = 获取配置()
            if isinstance(数据, dict):
                return 数据
        except Exception:
            pass
    return {}


def _配置值(配置: Any, 字段名: str, 默认值: Any = None) -> Any:
    数据 = _配置字典(配置)
    分类 = 数据.get("image_host_settings") or 数据.get("图片图床设置")
    if isinstance(分类, dict) and 字段名 in 分类:
        return 分类.get(字段名)
    if 字段名 in 数据:
        return 数据.get(字段名)
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            值 = 获取方法(字段名)
            if 值 is not None:
                return 值
            if isinstance(分类, dict):
                return 分类.get(字段名, 默认值)
        except Exception:
            pass
    值 = getattr(配置, 字段名, None)
    return 默认值 if 值 is None else 值


def 读取图床设置(配置: Any = None) -> tuple[bool, str, str]:
    上传地址 = str(
        _配置值(配置, "image_host_upload_url", 默认图床上传地址)
        or 默认图床上传地址
    ).strip()
    Token = str(_配置值(配置, "image_host_token", "") or "").strip()
    return True, 上传地址, Token


def 图床是否开启(配置: Any = None) -> bool:
    开启, 上传地址, _ = 读取图床设置(配置)
    try:
        解析 = urlsplit(上传地址)
        return 开启 and 解析.scheme.lower() in {"http", "https"} and bool(解析.netloc)
    except ValueError:
        return False


def _规范化文件名(文件名: Any, 内容类型: Any = "") -> str:
    名称 = re.sub(r"[\x00-\x1f\x7f\\/:*?\"<>|]+", "_", str(文件名 or "").strip())
    名称 = 名称.strip(" .")[:160]
    if 名称:
        return 名称
    类型 = str(内容类型 or "").lower()
    扩展名 = ".jpg" if "jpeg" in 类型 else ".webp" if "webp" in 类型 else ".png"
    return f"image{扩展名}"


def _允许图床地址(地址: Any) -> bool:
    try:
        解析 = urlsplit(str(地址 or "").strip())
        主机 = str(解析.hostname or "").rstrip(".").lower()
        if 解析.scheme.lower() not in {"http", "https"} or not 主机:
            return False
        if 解析.username or 解析.password:
            return False
        try:
            IP地址 = ipaddress.ip_address(主机)
            if not IP地址.is_global:
                return False
        except ValueError:
            pass
        return True
    except (TypeError, ValueError):
        return False


def _图床请求头(Token: str) -> dict[str, str]:
    头 = {"User-Agent": "MantouBot/image-host", "Accept": "application/json,text/plain,*/*"}
    if Token:
        头["Authorization"] = f"Bearer {Token}"
    return 头


def _追加图床字段(表单: FormData, 上传地址: str) -> None:
    try:
        主机 = str(urlsplit(上传地址).hostname or "").lower().rstrip(".")
    except ValueError:
        主机 = ""
    if 主机 == "0x0.st" or 主机.endswith(".0x0.st"):
        表单.add_field("secret", "1")


def _提取返回地址(数据: Any) -> str:
    if isinstance(数据, dict):
        for 键 in ("url", "src", "link", "image_url", "download_url"):
            地址 = _提取返回地址(数据.get(键))
            if 地址:
                return 地址
        for 值 in 数据.values():
            地址 = _提取返回地址(值)
            if 地址:
                return 地址
        return ""
    if isinstance(数据, (list, tuple)):
        for 值 in 数据:
            地址 = _提取返回地址(值)
            if 地址:
                return 地址
        return ""
    文本 = str(数据 or "").strip()
    if not 文本:
        return ""
    匹配 = 图床返回地址规则.search(文本)
    if not 匹配:
        return ""
    return 匹配.group(0).rstrip(".,);]}")


async def _发送图床表单(
    上传地址: str, 表单: FormData, Token: str
) -> str:
    try:
        超时 = ClientTimeout(total=图床请求超时秒, connect=15, sock_read=图床请求超时秒)
        async with ClientSession(timeout=超时, trust_env=False) as 客户端:
            async with 客户端.post(
                上传地址,
                data=表单,
                headers=_图床请求头(Token),
                allow_redirects=True,
                max_redirects=2,
            ) as 响应:
                内容 = await 响应.content.read(图床最大响应字节数)
                if not 200 <= 响应.status < 300:
                    logger.debug("图床上传失败：阶段=响应，状态=%s", int(响应.status))
                    return ""
                文本 = 内容.decode("utf-8", errors="replace").strip()
                try:
                    数据: Any = json.loads(文本)
                except (TypeError, ValueError, json.JSONDecodeError):
                    数据 = 文本
                地址 = _提取返回地址(数据)
                return 地址 if _允许图床地址(地址) else ""
    except asyncio.CancelledError:
        raise
    except (ClientError, asyncio.TimeoutError, TimeoutError, OSError, ValueError) as 异常:
        logger.debug("图床上传失败：阶段=请求，错误类型=%s", type(异常).__name__)
        return ""


async def 上传媒体字节(
    图片字节: bytes,
    文件名: str = "image.png",
    内容类型: str = "image/png",
    配置: Any = None,
) -> str:
    开启, 上传地址, Token = 读取图床设置(配置)
    if not 开启 or not _允许图床地址(上传地址):
        return ""
    if not isinstance(图片字节, (bytes, bytearray)):
        return ""
    数据 = bytes(图片字节)
    if not 数据 or len(数据) > 图床最大上传字节数:
        return ""
    表单 = FormData()
    表单.add_field(
        "file",
        数据,
        filename=_规范化文件名(文件名, 内容类型),
        content_type=str(内容类型 or "image/png").split(";", 1)[0],
    )
    _追加图床字段(表单, 上传地址)
    return await _发送图床表单(上传地址, 表单, Token)


async def 上传媒体URL(
    图片地址: str,
    文件名: str = "image.png",
    内容类型: str = "image/png",
    配置: Any = None,
) -> str:
    开启, 上传地址, Token = 读取图床设置(配置)
    if not 开启 or not _允许图床地址(上传地址) or not _允许图床地址(图片地址):
        return ""
    表单 = FormData()
    表单.add_field("url", str(图片地址).strip(), content_type="text/plain")
    表单.add_field("file_name", _规范化文件名(文件名, 内容类型))
    _追加图床字段(表单, 上传地址)
    return await _发送图床表单(上传地址, 表单, Token)


async def 上传媒体流(
    图片流: AsyncIterable[bytes],
    文件名: str = "image.png",
    内容类型: str = "image/png",
    配置: Any = None,
) -> str:
    """把上游响应流直接转发到图床，过程中不创建本地图片文件。"""
    开启, 上传地址, Token = 读取图床设置(配置)
    if not 开启 or not _允许图床地址(上传地址):
        return ""
    已读取 = 0

    async def _受限流() -> AsyncIterable[bytes]:
        nonlocal 已读取
        async for 数据块 in 图片流:
            if not 数据块:
                continue
            已读取 += len(数据块)
            if 已读取 > 图床最大上传字节数:
                raise ValueError("图床上传文件过大")
            yield 数据块

    表单 = FormData()
    表单.add_field(
        "file",
        AsyncIterablePayload(
            _受限流(),
            content_type=str(内容类型 or "image/png").split(";", 1)[0],
        ),
        filename=_规范化文件名(文件名, 内容类型),
    )
    _追加图床字段(表单, 上传地址)
    return await _发送图床表单(上传地址, 表单, Token)


async def 上传媒体文件(
    文件路径: str | Path,
    文件名: str = "attachment.bin",
    内容类型: str = "application/octet-stream",
    配置: Any = None,
) -> str:
    """以受限分块读取服务器文件并上传，避免复制完整文件到内存。"""
    路径 = Path(文件路径)
    try:
        if not 路径.is_file() or 路径.stat().st_size <= 0:
            return ""
        if 路径.stat().st_size > 图床最大上传字节数:
            return ""
    except OSError:
        return ""

    async def _文件流() -> AsyncIterable[bytes]:
        try:
            with 路径.open("rb") as 文件:
                while True:
                    数据块 = await asyncio.to_thread(文件.read, 64 * 1024)
                    if not 数据块:
                        break
                    yield 数据块
        except OSError:
            return

    return await 上传媒体流(_文件流(), 文件名 or 路径.name, 内容类型, 配置)


async def 上传图片字节(
    图片字节: bytes,
    文件名: str = "image.png",
    内容类型: str = "image/png",
    配置: Any = None,
) -> str:
    """兼容旧调用；图片和其它媒体统一走同一上传流程。"""
    return await 上传媒体字节(图片字节, 文件名, 内容类型, 配置)


async def 上传图片URL(
    图片地址: str,
    文件名: str = "image.png",
    内容类型: str = "image/png",
    配置: Any = None,
) -> str:
    """兼容旧调用；图片和其它媒体统一走同一上传流程。"""
    return await 上传媒体URL(图片地址, 文件名, 内容类型, 配置)


async def 上传图片流(
    图片流: AsyncIterable[bytes],
    文件名: str = "image.png",
    内容类型: str = "image/png",
    配置: Any = None,
) -> str:
    """兼容旧调用；图片和其它媒体统一走同一上传流程。"""
    return await 上传媒体流(图片流, 文件名, 内容类型, 配置)
