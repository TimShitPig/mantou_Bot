"""自建图床原字节上传；Token 只在当前请求的 Bearer 头中使用。"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import math
import mimetypes
import os
import re
import stat
import time
import weakref
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import aiohttp
from PIL import Image


图床地址 = "https://mantou-imgbed.pages.dev"
上传分片大小 = 16 * 1024 * 1024
_响应上限 = 64 * 1024
_图片类型 = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "WEBP": "image/webp"}
_媒体目录 = {"image": "图片", "file": "文件", "audio": "音频", "video": "视频"}
_上传额度 = globals().get("_上传额度")
if _上传额度 is None:
    _上传额度 = weakref.WeakKeyDictionary()


class 图床错误(RuntimeError):
    def __init__(
        self, stage: str, status: int | None = None, *, submitted: bool = False,
        operation: str = "prepare", progress: dict[str, Any] | None = None,
    ):
        super().__init__(stage)
        self.stage, self.status = stage, status
        self.submitted, self.operation = bool(submitted), operation
        self.progress = dict(progress or {})


def 读取图片资料(数据: bytes) -> dict[str, Any]:
    """只读取格式与尺寸，保留动画和原始图片字节。"""
    if not isinstance(数据, bytes) or not 数据:
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
        路径 = unquote(地址.path)
        有效 = (
            地址.scheme == "https" and 地址.hostname == "mantou-imgbed.pages.dev"
            and 地址.port in (None, 443) and 地址.username is None and 地址.password is None
            and 地址.path.startswith("/file/") and len(地址.path) > len("/file/")
            and not 地址.query and not 地址.fragment and "\\" not in 路径
            and not any(字符 in (".", "..") for 字符 in 路径.split("/"))
            and not any(ord(字符) < 32 or ord(字符) == 127 for 字符 in 路径)
        )
    except ValueError:
        有效 = False
    if not 有效:
        raise 图床错误("response_url")
    return 值


async def _在线程执行(函数, *参数):
    """取消时先等有界文件读完，防止工作线程使用已关闭的文件句柄。"""
    任务 = asyncio.create_task(asyncio.to_thread(函数, *参数))
    try:
        return await asyncio.shield(任务)
    except asyncio.CancelledError:
        while not 任务.done():
            try:
                await asyncio.shield(任务)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if 任务.done() and not 任务.cancelled():
            任务.exception()
        raise


def _文件状态(文件) -> tuple[int, int, int, int] | None:
    try:
        状态 = os.fstat(文件.fileno())
    except (AttributeError, io.UnsupportedOperation):
        return None
    if not stat.S_ISREG(状态.st_mode):
        raise 图床错误("file_type")
    return 状态.st_dev, 状态.st_ino, 状态.st_size, 状态.st_mtime_ns


def _文件摘要(文件) -> tuple[int, str, tuple[int, int, int, int] | None]:
    初始状态 = _文件状态(文件)
    if 初始状态 is not None and 初始状态[2] <= 0:
        raise 图床错误("file_size")
    摘要 = hashlib.sha256()
    大小 = 0
    文件.seek(0)
    while 块 := 文件.read(1024 * 1024):
        大小 += len(块)
        摘要.update(块)
    if 大小 <= 0:
        raise 图床错误("file_size")
    if _文件状态(文件) != 初始状态:
        raise 图床错误("file_changed")
    return 大小, 摘要.hexdigest(), 初始状态


def _读取文件块(文件, 偏移: int, 长度: int, 初始状态) -> bytes:
    if _文件状态(文件) != 初始状态:
        raise 图床错误("file_changed")
    文件.seek(偏移)
    块 = 文件.read(长度)
    if len(块) != 长度 or _文件状态(文件) != 初始状态:
        raise 图床错误("file_changed")
    return 块


def _校验Token(上传Token: str) -> None:
    if not isinstance(上传Token, str) or not 上传Token:
        raise 图床错误("not_configured")
    if len(上传Token) > 4096 or any(not 33 <= ord(字符) <= 126 for 字符 in 上传Token):
        raise 图床错误("invalid_config")


def _规范文件名(文件名: Any) -> str:
    if not isinstance(文件名, str):
        raise 图床错误("file_name")
    名称 = 文件名.replace("\\", "/").rsplit("/", 1)[-1]
    try:
        名称字节数 = len(名称.encode("utf-8"))
    except UnicodeError:
        raise 图床错误("file_name") from None
    if not 名称 or 名称 in (".", "..") or 名称字节数 > 384 or any(
        ord(字符) < 32 or 127 <= ord(字符) <= 159 for 字符 in 名称
    ):
        raise 图床错误("file_name")
    return 名称


def _准备进度(旧进度, 资料: dict[str, Any], 上传Token: str) -> dict[str, Any]:
    绑定 = {
        **资料, "total_chunks": (资料["size"] + 上传分片大小 - 1) // 上传分片大小,
        "token_fingerprint": hashlib.sha256(上传Token.encode("utf-8")).hexdigest(),
    }
    if 旧进度 is not None and not isinstance(旧进度, dict):
        raise 图床错误("progress_mismatch")
    if not 旧进度:
        日期 = datetime.now()
        return {
            **绑定, "stage": "ready", "operation": "prepare", "submitted": False, "confirmed": True,
            "upload_id": "", "next_chunk": 0, "started_at": time.time(),
            "folder": f"聊天媒体/{日期.year}年{日期.month}月{日期.day}日/{_媒体目录[资料['media_kind']]}",
        }
    if any(旧进度.get(键) != 值 for 键, 值 in 绑定.items()):
        raise 图床错误("progress_mismatch")
    下一片 = 旧进度.get("next_chunk")
    上传编号 = 旧进度.get("upload_id")
    目录 = 旧进度.get("folder")
    开始时间 = 旧进度.get("started_at")
    if (
        type(下一片) is not int or not 0 <= 下一片 <= 绑定["total_chunks"]
        or not isinstance(上传编号, str) or len(上传编号) > 100
        or not isinstance(目录, str)
        or not re.fullmatch(r"聊天媒体/\d{4}年\d{1,2}月\d{1,2}日/" + _媒体目录[资料["media_kind"]], 目录)
        or type(开始时间) not in (int, float) or not math.isfinite(开始时间) or 开始时间 <= 0
    ):
        raise 图床错误("progress_mismatch")
    受控进度 = {**绑定, **{键: 旧进度[键] for 键 in (
        "stage", "operation", "submitted", "confirmed", "upload_id", "next_chunk", "started_at",
        "folder", "result_url", "uploaded_at",
    ) if 键 in 旧进度}}
    if 旧进度.get("operation") not in ("prepare", "single", "init", "chunk", "merge"):
        raise 图床错误("progress_mismatch")
    if 旧进度.get("stage") not in (
        "ready", "initialized", "uploading", "completed", "single_submitted", "init_submitted",
        "chunk_submitted", "merge_submitted",
    ):
        raise 图床错误("progress_mismatch")
    if 旧进度["stage"] != "completed":
        受控进度.pop("result_url", None)
        受控进度.pop("uploaded_at", None)
    if 旧进度.get("submitted") is not False or 旧进度.get("confirmed") is not True:
        raise 图床错误("submission_unknown", submitted=True, operation=旧进度["operation"], progress=受控进度)
    if 旧进度.get("stage") == "completed":
        _规范图片地址(旧进度.get("result_url"))
        if (
            下一片 != 绑定["total_chunks"] or type(旧进度.get("uploaded_at")) not in (int, float)
            or not math.isfinite(旧进度["uploaded_at"]) or 旧进度["uploaded_at"] <= 0
        ):
            raise 图床错误("progress_mismatch")
    elif 上传编号:
        if 绑定["total_chunks"] <= 1 or not re.fullmatch(r"upload_[0-9]+_[a-z0-9]+", 上传编号):
            raise 图床错误("progress_mismatch")
        if 旧进度.get("stage") not in ("initialized", "uploading"):
            raise 图床错误("progress_mismatch")
    elif 旧进度.get("stage") != "ready" or 下一片:
        raise 图床错误("progress_mismatch")
    # 只接收本客户端的受控字段；凭据和调用方私有字段不进入回调或错误。
    return 受控进度


async def _回调(函数, 状态: dict[str, Any], *, 已提交: bool, 操作: str) -> None:
    if 函数 is None:
        return
    try:
        await 函数(dict(状态))
    except asyncio.CancelledError:
        raise
    except Exception:
        raise 图床错误("progress", submitted=已提交, operation=操作, progress=状态) from None


async def _读取响应(响应) -> Any:
    if 响应.status != 200:
        raise 图床错误("upload", 响应.status)
    原文 = bytearray()
    async for 块 in 响应.content.iter_chunked(16384):
        原文.extend(块)
        if len(原文) > _响应上限:
            raise 图床错误("response_size", 响应.status)
    try:
        return json.loads(原文.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise 图床错误("response_json", 响应.status) from None


def _结果地址(结果) -> str:
    if isinstance(结果, list) and len(结果) == 1:
        结果 = 结果[0]
    if not isinstance(结果, dict):
        raise 图床错误("response_fields", 200)
    return _规范图片地址(结果.get("src"))


async def _请求(客户端, 上传Token, 参数, 表单, 状态, 操作, 提交前, 进度回调, 确认):
    待确认 = {**状态, "stage": 操作 + "_submitted", "operation": 操作, "submitted": True, "confirmed": False}
    try:
        await _回调(提交前, 待确认, 已提交=False, 操作=操作)
    except 图床错误 as 错误:
        错误.progress = dict(状态)
        raise
    # 一旦进入 POST，无论断连、取消还是响应解析失败，调用方必须保留待确认标记。
    try:
        async with 客户端.post(
            图床地址 + "/upload", params=参数, data=表单,
            headers={"Authorization": "Bearer " + 上传Token}, allow_redirects=False,
        ) as 响应:
            结果 = await _读取响应(响应)
        新状态 = 确认(结果, 待确认)
    except asyncio.CancelledError:
        raise
    except 图床错误 as 错误:
        raise 图床错误(
            错误.stage, 错误.status if 错误.status is not None else 200,
            submitted=True, operation=操作, progress=待确认,
        ) from None
    except (asyncio.TimeoutError, TimeoutError):
        raise 图床错误("timeout", submitted=True, operation=操作, progress=待确认) from None
    except aiohttp.ClientError:
        raise 图床错误("request", submitted=True, operation=操作, progress=待确认) from None
    except (OSError, ValueError, TypeError):
        raise 图床错误("request", submitted=True, operation=操作, progress=待确认) from None
    await _回调(进度回调, 新状态, 已提交=True, 操作=操作)
    return 新状态


def _表单(字段: dict[str, Any], 块: bytes | None = None, 文件名="", 类型=""):
    表单 = aiohttp.FormData(quote_fields=False)
    for 键, 值 in 字段.items():
        表单.add_field(键, str(值))
    if 块 is not None:
        表单.add_field("file", 块, filename=文件名, content_type=类型)
    return 表单


def _上传结果(状态):
    return {
        键: 状态[键] for 键 in (
            "size", "sha256", "content_type", "original_name", "media_kind", "uploaded_at",
        )
    } | {"url": _规范图片地址(状态["result_url"])}


async def _上传源(打开源, 上传Token, 名称, 种类, 类型, 提交前=None, 进度回调=None, 进度=None):
    _校验Token(上传Token)
    名称 = _规范文件名(名称)
    if not isinstance(种类, str) or 种类 not in _媒体目录:
        raise 图床错误("media_kind")
    循环 = asyncio.get_running_loop()
    额度 = _上传额度.get(循环)
    if 额度 is None:
        额度 = asyncio.Semaphore(8)
        _上传额度[循环] = 额度
    async with 额度:
        try:
            with 打开源() as 文件:
                大小, 摘要, 初始状态 = await _在线程执行(_文件摘要, 文件)
                状态 = _准备进度(进度, {
                    "size": 大小, "sha256": 摘要, "original_name": 名称,
                    "content_type": 类型, "media_kind": 种类,
                }, 上传Token)
                if 状态["stage"] == "completed":
                    return _上传结果(状态)
                参数 = {
                    "uploadChannel": "telegram", "channelName": "自建图床",
                    "serverCompress": "false", "autoRetry": "false", "uploadNameType": "default",
                    "returnFormat": "full", "responseFormat": "object", "uploadFolder": 状态["folder"],
                }

                def 确认完成(结果, 待确认):
                    return {
                        **待确认, "stage": "completed", "submitted": False, "confirmed": True,
                        "next_chunk": 待确认["total_chunks"], "result_url": _结果地址(结果),
                        "uploaded_at": time.time(),
                    }

                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=240, connect=15, sock_read=210),
                    cookie_jar=aiohttp.DummyCookieJar(), trust_env=False,
                ) as 客户端:
                    if hasattr(客户端, "_retry_connection"):
                        客户端._retry_connection = False
                    if 大小 <= 上传分片大小:
                        块 = await _在线程执行(_读取文件块, 文件, 0, 大小, 初始状态)
                        状态 = await _请求(
                            客户端, 上传Token, 参数, _表单({}, 块, 名称, 类型), 状态, "single",
                            提交前, 进度回调, 确认完成,
                        )
                    else:
                        字段 = {"originalFileName": 名称, "originalFileType": 类型, "totalChunks": 状态["total_chunks"]}
                        if not 状态["upload_id"]:
                            def 确认初始化(结果, 待确认):
                                if not isinstance(结果, dict) or 结果.get("success") is not True:
                                    raise 图床错误("response_fields", 200)
                                编号 = 结果.get("uploadId")
                                if not isinstance(编号, str) or len(编号) > 100 or not re.fullmatch(r"upload_[0-9]+_[a-z0-9]+", 编号):
                                    raise 图床错误("response_fields", 200)
                                return {**待确认, "stage": "initialized", "submitted": False, "confirmed": True, "upload_id": 编号}
                            状态 = await _请求(
                                客户端, 上传Token, {**参数, "initChunked": "true"}, _表单(字段),
                                状态, "init", 提交前, 进度回调, 确认初始化,
                            )
                        for 序号 in range(状态["next_chunk"], 状态["total_chunks"]):
                            偏移 = 序号 * 上传分片大小
                            块 = await _在线程执行(_读取文件块, 文件, 偏移, min(上传分片大小, 大小 - 偏移), 初始状态)
                            def 确认分片(结果, 待确认, 当前序号=序号):
                                if (
                                    not isinstance(结果, dict) or 结果.get("success") is not True
                                    or 结果.get("uploadId") != 待确认["upload_id"]
                                    or type(结果.get("chunkIndex")) is not int or 结果["chunkIndex"] != 当前序号
                                ):
                                    raise 图床错误("response_fields", 200)
                                return {**待确认, "stage": "uploading", "submitted": False, "confirmed": True, "next_chunk": 当前序号 + 1}
                            状态 = await _请求(
                                客户端, 上传Token, {**参数, "chunked": "true"},
                                _表单({**字段, "uploadId": 状态["upload_id"], "chunkIndex": 序号}, 块, 名称, "application/octet-stream"),
                                状态, "chunk", 提交前, 进度回调, 确认分片,
                            )
                        # 上游 Telegram 分片内部仍有固定重试；客户端不追加重试或重发未知提交。
                        状态 = await _请求(
                            客户端, 上传Token, {**参数, "chunked": "true", "merge": "true"},
                            _表单({**字段, "uploadId": 状态["upload_id"]}), 状态, "merge",
                            提交前, 进度回调, 确认完成,
                        )
                return _上传结果(状态)
        except asyncio.CancelledError:
            raise
        except 图床错误:
            raise
        except (OSError, ValueError, TypeError):
            raise 图床错误("file_read") from None


async def 上传文件(
    路径, 上传Token: str, *, 文件名: str = "", 媒体种类: str = "file",
    提交前=None, 进度回调=None, 进度=None,
) -> dict[str, Any]:
    """分片有界读取；只从已确认的下一片继续，不自动重放提交。"""
    try:
        文件路径 = Path(路径)
        名称 = 文件名 or 文件路径.name
    except (TypeError, ValueError):
        raise 图床错误("file_path") from None
    名称 = _规范文件名(名称)
    类型 = mimetypes.guess_type(名称)[0] or "application/octet-stream"
    return await _上传源(
        lambda: 文件路径.open("rb"), 上传Token, 名称, 媒体种类, 类型,
        提交前=提交前, 进度回调=进度回调, 进度=进度,
    )


async def 上传图片(数据: bytes, 上传Token: str) -> dict[str, Any]:
    """网页图片兼容入口；保留实际尺寸、动画和原字节，使用中文图片目录。"""
    _校验Token(上传Token)
    资料 = await _在线程执行(读取图片资料, 数据)
    结果 = await _上传源(
        lambda: io.BytesIO(数据), 上传Token, 资料["file_name"], "image", 资料["content_type"],
    )
    return {**结果, "width": 资料["width"], "height": 资料["height"]}


def _读取图片文件资料(路径: Path) -> dict[str, Any]:
    """只读文件头的格式与尺寸，不展开像素或整份读取图片。"""
    try:
        with Image.open(路径) as 图片:
            格式 = str(图片.format or "").upper()
            宽, 高 = 图片.size
    except Exception:
        raise 图床错误("image_format") from None
    if 格式 not in _图片类型 or 宽 <= 0 or 高 <= 0:
        raise 图床错误("image_format")
    return {"content_type": _图片类型[格式], "width": 宽, "height": 高}


async def 上传图片文件(路径, 上传Token: str, *, 文件名: str = "") -> dict[str, Any]:
    """图片文件入口保留原字节，以固定大小分片上传并附上实际尺寸。"""
    _校验Token(上传Token)
    try:
        文件路径 = Path(路径)
    except (TypeError, ValueError):
        raise 图床错误("file_path") from None
    名称 = _规范文件名(文件名 or 文件路径.name)
    资料 = await _在线程执行(_读取图片文件资料, 文件路径)
    结果 = await _上传源(
        lambda: 文件路径.open("rb"), 上传Token, 名称, "image", 资料["content_type"],
    )
    return {**结果, "width": 资料["width"], "height": 资料["height"]}
