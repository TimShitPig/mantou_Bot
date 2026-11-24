"""按有界范围读取已保存的图床文件，避免图床一次回源全部视频分片。"""
from __future__ import annotations

import asyncio
import re
import weakref
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, DummyCookieJar, web


_单次范围 = 4 * 1024 * 1024
_读取上限 = 800 * 1024 * 1024
_下载额度 = globals().get("_下载额度")
if _下载额度 is None:
    _下载额度 = weakref.WeakKeyDictionary()


def 是图床文件地址(值: Any) -> bool:
    if not isinstance(值, str) or not 值 or len(值) > 8192:
        return False
    if any(字符.isspace() or ord(字符) < 32 or ord(字符) == 127 for 字符 in 值):
        return False
    try:
        地址 = urlsplit(值)
        路径 = unquote(地址.path)
        return (地址.scheme == "https" and 地址.hostname == "mantou-imgbed.pages.dev"
                and 地址.port in (None, 443) and 地址.username is None and 地址.password is None
                and 地址.path.startswith("/file/") and len(地址.path) > 6
                and not 地址.query and not 地址.fragment and "\\" not in 路径
                and not any(段 in {".", ".."} for 段 in 路径.split("/"))
                and not any(ord(字符) < 32 or ord(字符) == 127 for 字符 in 路径))
    except ValueError:
        return False


def _范围(头: str, 大小: int) -> tuple[int, int, bool]:
    if not 头:
        return 0, 大小 - 1, False
    if len(头) > 128:
        raise ValueError("range")
    匹配 = re.fullmatch(r"bytes=(\d*)-(\d*)", 头.strip())
    if not 匹配 or not any(匹配.groups()):
        raise ValueError("range")
    首, 尾 = 匹配.groups()
    if not 首:
        长度 = int(尾)
        if 长度 <= 0:
            raise ValueError("range")
        return max(0, 大小 - 长度), 大小 - 1, True
    起点 = int(首)
    终点 = min(int(尾), 大小 - 1) if 尾 else 大小 - 1
    if not 0 <= 起点 <= 终点 < 大小:
        raise ValueError("range")
    return 起点, 终点, True


async def _探测大小(客户端, 地址: str) -> tuple[int, str]:
    """HEAD 无长度时只读一字节范围；忽略范围的小文件有界读取至 EOF。"""
    async with 客户端.get(
        地址, headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"}, allow_redirects=False,
    ) as 上游:
        if 上游.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("upstream_encoding")
        类型 = str(上游.headers.get("Content-Type") or "application/octet-stream")
        长度头 = 上游.headers.get("Content-Length")
        if 上游.status == 206:
            匹配 = re.fullmatch(r"bytes 0-0/([1-9][0-9]{0,11})", 上游.headers.get("Content-Range", ""))
            if not 匹配 or (长度头 is not None and 长度头 != "1"):
                raise ValueError("upstream_range")
            if len(await 上游.content.read(2)) != 1 or await 上游.content.read(1):
                raise ValueError("upstream_length")
            return int(匹配[1]), 类型
        if 上游.status != 200:
            raise ValueError("upstream_status")
        小文件上限 = 16 * 1024 * 1024
        if 长度头 is not None:
            if not re.fullmatch(r"[0-9]+", 长度头) or not 0 < int(长度头) <= 小文件上限:
                raise ValueError("upstream_length")
            return int(长度头), 类型
        大小 = 0
        while True:
            数据 = await 上游.content.read(min(64 * 1024, 小文件上限 - 大小 + 1))
            if not 数据:
                return 大小, 类型
            大小 += len(数据)
            if 大小 > 小文件上限:
                raise ValueError("upstream_size")


async def 处理图床媒体(request: web.Request, 地址: str, 模式: str, 文件名: str) -> web.StreamResponse:
    """由已鉴权的媒体入口调用；上传 Token 永不进入下载会话。"""
    if not 是图床文件地址(地址):
        return web.Response(status=400, text="媒体地址无效")
    头列表 = request.headers.getall("Range", [])
    if len(头列表) > 1:
        return web.Response(status=416, text="媒体范围无效")
    额度 = _下载额度.get(asyncio.get_running_loop())
    if 额度 is None:
        额度 = asyncio.Semaphore(8)
        _下载额度[asyncio.get_running_loop()] = 额度
    响应 = None
    try:
        async with 额度, ClientSession(
            timeout=ClientTimeout(total=None, connect=20, sock_read=90),
            cookie_jar=DummyCookieJar(), trust_env=False, auto_decompress=False,
        ) as 客户端:
            if hasattr(客户端, "_retry_connection"):
                客户端._retry_connection = False
            async with 客户端.head(地址, headers={"Accept-Encoding": "identity"}, allow_redirects=False) as 上游:
                if 上游.status != 200:
                    return web.Response(status=502, text="媒体暂时不可用")
                长度头 = 上游.headers.get("Content-Length")
                大小 = int(长度头) if 长度头 is not None else None
                原内容类型 = 上游.headers.get("Content-Type")
            if 大小 is None:
                大小, 探测类型 = await _探测大小(客户端, 地址)
                原内容类型 = 原内容类型 or 探测类型
            内容类型 = str(原内容类型 or "application/octet-stream").split(";", 1)[0].lower()
            if not 0 < 大小 <= _读取上限:
                return web.Response(status=413 if 大小 > _读取上限 else 502, text="媒体文件不可用")
            if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", 内容类型):
                内容类型 = "application/octet-stream"
            if 模式 in {"image", "avatar"} and not 内容类型.startswith("image/"):
                return web.Response(status=415, text="不是可预览的图片")
            try:
                起点, 终点, 分段 = _范围(头列表[0] if 头列表 else "", 大小)
            except ValueError:
                return web.Response(status=416, headers={"Content-Range": f"bytes */{大小}"})
            响应头 = {
                "Content-Type": 内容类型, "Content-Length": str(终点 - 起点 + 1), "Accept-Ranges": "bytes",
                "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400",
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "Content-Disposition": "inline" if 模式 in {"image", "avatar"} else "attachment; filename*=UTF-8''" + quote(文件名, safe=""),
            }
            if 分段:
                响应头["Content-Range"] = f"bytes {起点}-{终点}/{大小}"
            if request.method == "HEAD":
                return web.Response(status=206 if 分段 else 200, headers=响应头)
            位置 = 起点
            while 位置 <= 终点:
                本段终点 = min(位置 + _单次范围 - 1, 终点)
                async with 客户端.get(
                    地址, headers={"Range": f"bytes={位置}-{本段终点}", "Accept-Encoding": "identity"}, allow_redirects=False,
                ) as 上游:
                    if 上游.headers.get("Content-Encoding", "identity").lower() != "identity":
                        raise ValueError("upstream_encoding")
                    if 上游.status == 206:
                        if 上游.headers.get("Content-Range") != f"bytes {位置}-{本段终点}/{大小}":
                            raise ValueError("upstream_range")
                        跳过 = 0
                    elif 上游.status == 200 and 大小 <= 16 * 1024 * 1024:
                        # 小文件源忽略 Range 时有界跳过原文件前缀；大文件必须逐段读取。
                        跳过 = 位置
                    else:
                        raise ValueError("upstream_status")
                    上游长度 = 上游.headers.get("Content-Length")
                    if 上游长度 is not None:
                        预期长度 = 本段终点 - 位置 + 1 if 上游.status == 206 else 大小
                        if not re.fullmatch(r"[0-9]+", 上游长度) or int(上游长度) != 预期长度:
                            raise ValueError("upstream_length")
                    while 跳过:
                        数据 = await 上游.content.read(min(64 * 1024, 跳过))
                        if not 数据:
                            raise ValueError("upstream_short")
                        跳过 -= len(数据)
                    剩余 = 本段终点 - 位置 + 1
                    while 剩余:
                        数据 = await 上游.content.read(min(64 * 1024, 剩余))
                        if not 数据:
                            raise ValueError("upstream_short")
                        if 响应 is None:
                            响应 = web.StreamResponse(status=206 if 分段 else 200, headers=响应头)
                            await 响应.prepare(request)
                        await 响应.write(数据)
                        剩余 -= len(数据)
                    if 上游.status == 206 and await 上游.content.read(1):
                        raise ValueError("upstream_length")
                位置 = 本段终点 + 1
            await 响应.write_eof()
            return 响应
    except asyncio.CancelledError:
        if 响应 is not None:
            响应.force_close()
            传输 = request.transport
            if 传输 is not None:
                传输.close()
        raise
    except (ClientError, TimeoutError, OSError, TypeError, ValueError):
        if 响应 is not None:
            响应.force_close()
            传输 = request.transport
            if 传输 is not None:
                传输.close()
            return 响应
        return web.Response(status=502, text="媒体暂时不可用", headers={"Cache-Control": "no-store"})
