from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import secrets
import socket
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import quote, urlencode, urljoin, urlsplit

from aiohttp import ClientResponse, ClientSession, ClientTimeout, FormData
from yarl import URL

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


蓝奏云网盘主机 = "https://pc.woozooo.com"
图片归档目录名 = "QQ聊天图片"
蓝奏云分享域名 = frozenset(
    {
        "lanzou.com",
        "lanzouo.com",
        "lanzouw.com",
        "lanzoui.com",
        "lanzoux.com",
        "lanzous.com",
        "woozooo.com",
    }
)
图片最大字节数 = 100 * 1024 * 1024
网页最大字节数 = 1024 * 1024
最大跳转次数 = 4
蓝奏云Cookie字段 = frozenset({"phpdisk_info", "ylogin"})
蓝奏云UserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
图片归档并发限制 = asyncio.Semaphore(2)
图片归档进行中: set[tuple[str, str]] = globals().get("图片归档进行中") or set()
图片归档已完成: set[tuple[str, str]] = globals().get("图片归档已完成") or set()
图片归档失败冷却: dict[tuple[str, str], float] = globals().get("图片归档失败冷却") or {}
图片归档任务: set[asyncio.Task[Any]] = globals().get("图片归档任务") or set()
图片归档排队中: set[tuple[str, str]] = globals().get("图片归档排队中") or set()
图片归档接收开启 = bool(globals().get("图片归档接收开启", True))
图片归档最大任务数 = 128


class 蓝奏云请求错误(RuntimeError):
    def __init__(
        self,
        阶段: str,
        状态码: int = 0,
        业务码: Any = None,
        主机: str = "",
    ):
        super().__init__(阶段)
        self.阶段 = 阶段
        self.状态码 = int(状态码 or 0)
        try:
            self.业务码 = int(业务码) if 业务码 is not None else None
        except (TypeError, ValueError):
            self.业务码 = None
        self.主机 = str(主机 or "")[:253]


def _配置值(配置: Any) -> str:
    候选列表 = [配置]
    for 属性名 in ("data", "obj"):
        值 = getattr(配置, 属性名, None)
        if 值 is not None:
            候选列表.append(值)
    获取配置 = getattr(配置, "get_config", None)
    if callable(获取配置):
        try:
            候选列表.append(获取配置())
        except Exception:
            pass
    for 候选 in 候选列表:
        if isinstance(候选, dict):
            分类 = 候选.get("lanzou_pan_settings")
            if isinstance(分类, dict):
                return str(分类.get("lanzou_pan_cookie") or "").strip()
            return str(候选.get("lanzou_pan_cookie") or "").strip()
    return str(getattr(配置, "lanzou_pan_cookie", "") or "").strip()


def _解析Cookie(原文: Any) -> tuple[dict[str, str], str]:
    文本 = str(原文 or "").strip()
    if 文本[:7].lower() == "cookie:":
        文本 = 文本.split(":", 1)[1].strip()
    Cookie: dict[str, str] = {}
    for 片段 in 文本.split(";"):
        if "=" not in 片段:
            continue
        名称, 值 = 片段.split("=", 1)
        名称 = 名称.strip()
        值 = 值.strip()
        if 名称 and 值:
            Cookie[名称] = 值
    if not 蓝奏云Cookie字段.issubset(Cookie):
        raise 蓝奏云请求错误("cookie_invalid")
    return Cookie, Cookie["ylogin"]


def _新建会话(Cookie: dict[str, str] | None = None) -> ClientSession:
    from aiohttp import CookieJar

    会话 = ClientSession(
        headers={
            "User-Agent": 蓝奏云UserAgent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        },
        cookie_jar=CookieJar(unsafe=True),
        timeout=ClientTimeout(total=None, connect=20, sock_read=90),
        trust_env=True,
    )
    if Cookie:
        会话.cookie_jar.update_cookies(
            Cookie, response_url=URL(蓝奏云网盘主机 + "/")
        )
    return 会话


async def _确保公网HTTPS地址(地址: str, *, 限制蓝奏域名: bool = False) -> str:
    文本 = str(地址 or "").strip()
    if len(文本) > 8192:
        raise 蓝奏云请求错误("url_invalid")
    解析 = urlsplit(文本)
    主机 = str(解析.hostname or "").rstrip(".").lower()
    if (
        解析.scheme.lower() != "https"
        or not 主机
        or 解析.username
        or 解析.password
        or (解析.port not in (None, 443))
    ):
        raise 蓝奏云请求错误("url_invalid")
    if 限制蓝奏域名 and not any(
        主机 == 根域 or 主机.endswith(f".{根域}") for 根域 in 蓝奏云分享域名
    ):
        raise 蓝奏云请求错误("share_host_invalid", 主机=主机)
    try:
        地址列表 = [ipaddress.ip_address(主机)]
    except ValueError:
        try:
            解析结果 = await asyncio.get_running_loop().getaddrinfo(
                主机, 443, type=socket.SOCK_STREAM
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise 蓝奏云请求错误("dns_failed") from exc
        地址列表 = []
        for 结果 in 解析结果:
            try:
                地址列表.append(ipaddress.ip_address(结果[4][0]))
            except (ValueError, TypeError, IndexError):
                continue
    if not 地址列表 or any(not 地址.is_global for 地址 in 地址列表):
        raise 蓝奏云请求错误("host_not_public")
    return 文本


async def _请求跟随跳转(
    会话: ClientSession,
    地址: str,
    *,
    referer: str = "",
    限制蓝奏域名: bool = False,
) -> ClientResponse:
    当前地址 = 地址
    for 次数 in range(最大跳转次数 + 1):
        当前地址 = await _确保公网HTTPS地址(
            当前地址, 限制蓝奏域名=限制蓝奏域名 and 次数 == 0
        )
        try:
            响应 = await 会话.get(
                当前地址,
                allow_redirects=False,
                headers={"Referer": referer} if referer else None,
            )
        except Exception as exc:
            raise 蓝奏云请求错误("get_failed") from exc
        if 响应.status not in {301, 302, 303, 307, 308}:
            return 响应
        跳转地址 = 响应.headers.get("Location")
        响应.release()
        if not 跳转地址 or 次数 >= 最大跳转次数:
            raise 蓝奏云请求错误("redirect_invalid", 响应.status)
        当前地址 = urljoin(当前地址, 跳转地址)
    raise 蓝奏云请求错误("redirect_limit")


async def _读取网页文本(
    会话: ClientSession,
    地址: str,
    *,
    referer: str = "",
    限制蓝奏域名: bool = False,
) -> str:
    响应 = await _请求跟随跳转(
        会话, 地址, referer=referer, 限制蓝奏域名=限制蓝奏域名
    )
    try:
        if 响应.status != 200:
            raise 蓝奏云请求错误("page_status", 响应.status)
        内容 = await 响应.content.read(网页最大字节数 + 1)
        if len(内容) > 网页最大字节数:
            raise 蓝奏云请求错误("page_too_large", 响应.status)
        编码 = 响应.charset or "utf-8"
        return 内容.decode(编码, errors="replace")
    finally:
        响应.release()


async def _提交表单JSON(
    会话: ClientSession,
    地址: str,
    字段: dict[str, Any],
    *,
    referer: str = "",
) -> dict[str, Any]:
    try:
        async with 会话.post(
            地址,
            data={名称: str(值) for 名称, 值 in 字段.items()},
            headers={"Referer": referer} if referer else None,
            allow_redirects=False,
        ) as 响应:
            if 响应.status != 200:
                raise 蓝奏云请求错误("post_status", 响应.status)
            内容 = await 响应.content.read(网页最大字节数 + 1)
            if len(内容) > 网页最大字节数:
                raise 蓝奏云请求错误("response_too_large", 响应.status)
            try:
                结果 = json.loads(内容.decode(响应.charset or "utf-8", errors="replace"))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise 蓝奏云请求错误("response_not_json", 响应.status) from exc
            if not isinstance(结果, dict):
                raise 蓝奏云请求错误("response_shape", 响应.status)
            return 结果
    except 蓝奏云请求错误:
        raise
    except Exception as exc:
        raise 蓝奏云请求错误("post_failed") from exc


def _成功(结果: dict[str, Any]) -> bool:
    return str(结果.get("zt") or "").strip() == "1"


def _目录项(结果: dict[str, Any]) -> list[dict[str, Any]]:
    值 = 结果.get("text")
    if not isinstance(值, list):
        return []
    return [项目 for 项目 in 值 if isinstance(项目, dict)]


async def _列出目录(
    会话: ClientSession, UID: str, 父目录ID: Any
) -> list[dict[str, Any]]:
    结果 = await _提交表单JSON(
        会话,
        f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}",
        {"task": 47, "folder_id": 父目录ID},
        referer=f"{蓝奏云网盘主机}/mydisk.php",
    )
    if not isinstance(结果.get("text"), list):
        raise 蓝奏云请求错误("directory_list", 业务码=结果.get("zt"))
    return _目录项(结果)


async def _确保归档目录(会话: ClientSession, UID: str, 月份目录: str) -> int:
    根目录 = await _列出目录(会话, UID, -1)
    根ID = next(
        (
            str(项目.get("fol_id"))
            for 项目 in 根目录
            if str(项目.get("name") or "").strip() == 图片归档目录名
            and str(项目.get("fol_id") or "").isdigit()
        ),
        "",
    )
    if not 根ID:
        创建结果 = await _提交表单JSON(
            会话,
            f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}",
            {
                "task": 2,
                "parent_id": -1,
                "folder_name": 图片归档目录名,
                "folder_description": "QQ 聊天图片归档",
            },
            referer=f"{蓝奏云网盘主机}/mydisk.php",
        )
        if not _成功(创建结果):
            raise 蓝奏云请求错误("directory_create")
        根目录 = await _列出目录(会话, UID, -1)
        根ID = next(
            (
                str(项目.get("fol_id"))
                for 项目 in 根目录
                if str(项目.get("name") or "").strip() == 图片归档目录名
                and str(项目.get("fol_id") or "").isdigit()
            ),
            "",
        )
    if not 根ID:
        raise 蓝奏云请求错误("directory_missing")

    月份列表 = await _列出目录(会话, UID, 根ID)
    月份ID = next(
        (
            str(项目.get("fol_id"))
            for 项目 in 月份列表
            if str(项目.get("name") or "").strip() == 月份目录
            and str(项目.get("fol_id") or "").isdigit()
        ),
        "",
    )
    if not 月份ID:
        创建结果 = await _提交表单JSON(
            会话,
            f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}",
            {
                "task": 2,
                "parent_id": 根ID,
                "folder_name": 月份目录,
                "folder_description": "",
            },
            referer=f"{蓝奏云网盘主机}/mydisk.php",
        )
        if not _成功(创建结果):
            raise 蓝奏云请求错误("directory_create")
        月份列表 = await _列出目录(会话, UID, 根ID)
        月份ID = next(
            (
                str(项目.get("fol_id"))
                for 项目 in 月份列表
                if str(项目.get("name") or "").strip() == 月份目录
                and str(项目.get("fol_id") or "").isdigit()
            ),
            "",
        )
    if not 月份ID:
        raise 蓝奏云请求错误("directory_missing")
    return int(月份ID)


async def _下载QQ图片(地址: str, 路径: Path) -> tuple[str, int]:
    from 功能文件.页面功能 import 帮助网页后端

    if not 帮助网页后端._允许媒体地址(地址):
        raise 蓝奏云请求错误("source_url_invalid")
    async with _新建会话() as 会话:
        响应 = await _请求跟随跳转(会话, 地址)
        try:
            if 响应.status not in (200, 206):
                raise 蓝奏云请求错误("source_status", 响应.status)
            try:
                长度 = int(响应.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                长度 = 0
            if 长度 > 图片最大字节数:
                raise 蓝奏云请求错误("source_too_large", 响应.status)
            已读 = 0
            前缀 = bytearray()
            with 路径.open("wb") as 文件:
                async for 数据块 in 响应.content.iter_chunked(64 * 1024):
                    已读 += len(数据块)
                    if 已读 > 图片最大字节数:
                        raise 蓝奏云请求错误("source_too_large", 响应.status)
                    if len(前缀) < 64:
                        前缀.extend(数据块[: 64 - len(前缀)])
                    文件.write(数据块)
            内容类型 = 识别图片类型(bytes(前缀), 响应.headers.get("Content-Type"))
            if not 内容类型:
                raise 蓝奏云请求错误("source_not_image", 响应.status)
            return 内容类型, 已读
        finally:
            响应.release()


def 识别图片类型(前缀: bytes, 响应类型: Any = "") -> str:
    if 前缀.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if 前缀.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if 前缀.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(前缀) >= 12 and 前缀[:4] == b"RIFF" and 前缀[8:12] == b"WEBP":
        return "image/webp"
    if 前缀.startswith(b"BM"):
        return "image/bmp"
    if len(前缀) >= 12 and 前缀[4:8] == b"ftyp" and b"avif" in 前缀[8:32]:
        return "image/avif"
    类型 = str(响应类型 or "").split(";", 1)[0].strip().lower()
    if 类型 in {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/avif"}:
        return 类型
    return ""


def _图片扩展名(内容类型: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/avif": ".avif",
    }.get(内容类型, ".img")


async def _上传图片(
    会话: ClientSession,
    UID: str,
    目录ID: int,
    文件路径: Path,
    文件名: str,
    内容类型: str,
    大小: int,
) -> str:
    日期 = datetime.now().strftime("%a %b %d %Y %H:%M:%S GMT+0800 (中国标准时间)")
    表单 = FormData()
    for 名称, 值 in (
        ("task", "1"),
        ("vie", "2"),
        ("ve", "2"),
        ("id", "WU_FILE_0"),
        ("name", 文件名),
        ("type", 内容类型),
        ("lastModifiedDate", 日期),
        ("size", str(大小)),
        ("folder_id_bb_n", str(目录ID)),
    ):
        表单.add_field(名称, 值)
    with 文件路径.open("rb") as 文件句柄:
        表单.add_field(
            "upload_file",
            文件句柄,
            filename=文件名,
            content_type=内容类型,
        )
        try:
            async with 会话.post(
                f"{蓝奏云网盘主机}/html5up.php",
                data=表单,
                headers={
                    "Origin": 蓝奏云网盘主机,
                    "Referer": f"{蓝奏云网盘主机}/mydisk.php?item=files&action=index&u={quote(UID)}",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                },
                allow_redirects=False,
            ) as 响应:
                if 响应.status != 200:
                    raise 蓝奏云请求错误("upload_status", 响应.status)
                内容 = await 响应.content.read(网页最大字节数 + 1)
                if len(内容) > 网页最大字节数:
                    raise 蓝奏云请求错误("upload_response_too_large", 响应.status)
                try:
                    结果 = json.loads(内容.decode(响应.charset or "utf-8", errors="replace"))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise 蓝奏云请求错误("upload_response_not_json", 响应.status) from exc
                if not isinstance(结果, dict) or not _成功(结果):
                    raise 蓝奏云请求错误("upload_rejected", 响应.status)
                文本 = 结果.get("text")
                文件记录 = 文本[0] if isinstance(文本, list) and 文本 else 文本
                文件ID = 文件记录.get("id") if isinstance(文件记录, dict) else None
                if not str(文件ID or "").isdigit():
                    raise 蓝奏云请求错误("upload_id_missing", 响应.status)
                return str(文件ID)
        except 蓝奏云请求错误:
            raise
        except Exception as exc:
            raise 蓝奏云请求错误("upload_failed") from exc


async def _取得分享信息(
    会话: ClientSession, UID: str, 文件ID: str, 提取码: str
) -> dict[str, str]:
    API = f"{蓝奏云网盘主机}/doupload.php?{urlencode({'uid': UID})}"
    设置结果 = await _提交表单JSON(
        会话,
        API,
        {"task": 23, "file_id": 文件ID, "shows": 1, "shownames": 提取码},
        referer=f"{蓝奏云网盘主机}/mydisk.php",
    )
    分享结果 = await _提交表单JSON(
        会话,
        API,
        {"task": 22, "file_id": 文件ID},
        referer=f"{蓝奏云网盘主机}/mydisk.php",
    )
    信息 = 分享结果.get("info")
    if not isinstance(信息, dict):
        raise 蓝奏云请求错误("share_response")
    分享码 = str(信息.get("pwd") or "").strip()
    if not 分享码 and _成功(设置结果):
        分享码 = 提取码
    if not 分享码:
        raise 蓝奏云请求错误("share_password_missing")
    分享地址 = str(信息.get("url") or "").strip()
    if not 分享地址:
        主站 = str(信息.get("is_newd") or "").strip().rstrip("/")
        分享ID = str(信息.get("f_id") or "").strip()
        if not 主站 or not 分享ID:
            raise 蓝奏云请求错误("share_link_missing")
        分享地址 = f"{主站}/{quote(分享ID, safe='')}"
    分享地址 = await _确保公网HTTPS地址(分享地址, 限制蓝奏域名=True)
    return {"share_url": 分享地址, "password": 分享码, "file_id": 文件ID}


async def _取得直接下载地址(
    会话: ClientSession, 分享地址: str, 提取码: str
) -> str:
    分享HTML = await _读取网页文本(
        会话, 分享地址, 限制蓝奏域名=True
    )
    if "文件取消" in 分享HTML or "文件不存在" in 分享HTML:
        raise 蓝奏云请求错误("share_missing")
    分享解析 = urlsplit(分享地址)
    Ajax地址 = f"{分享解析.scheme}://{分享解析.netloc}/ajaxm.php"
    if re.search(r'id=["\'](?:pwdload|passwddiv)["\']', 分享HTML, re.IGNORECASE):
        匹配 = re.search(r"sign=([\w-]+)&", 分享HTML)
        if not 匹配:
            raise 蓝奏云请求错误("password_sign_missing")
        Ajax字段 = {"action": "downprocess", "sign": 匹配.group(1), "p": 提取码}
        Referer = 分享地址
    else:
        匹配 = re.search(r'<iframe[^>]+src=["\']([^"\']+)', 分享HTML, re.IGNORECASE)
        if not 匹配:
            raise 蓝奏云请求错误("download_frame_missing")
        下载页地址 = urljoin(分享地址, 匹配.group(1))
        下载页HTML = await _读取网页文本(
            会话, 下载页地址, referer=分享地址, 限制蓝奏域名=True
        )
        if "验证码" in 下载页HTML or "网络异常" in 下载页HTML:
            raise 蓝奏云请求错误("download_challenge")
        Sign = re.search(r"['\"]sign['\"]\s*:\s*['\"]([^'\"]+)", 下载页HTML)
        if not Sign:
            Sign = re.search(r"\bvar\s+sign\s*=\s*['\"]([^'\"]+)", 下载页HTML)
        if not Sign:
            raise 蓝奏云请求错误("download_sign_missing")
        Ajax字段 = {"action": "downprocess", "sign": Sign.group(1), "ves": 1}
        Referer = 下载页地址
    Ajax结果 = await _提交表单JSON(
        会话, Ajax地址, Ajax字段, referer=Referer
    )
    if not _成功(Ajax结果):
        raise 蓝奏云请求错误("download_link_rejected")
    下载主机 = str(Ajax结果.get("dom") or "").strip().rstrip("/")
    下载标识 = str(Ajax结果.get("url") or "").strip()
    if not 下载主机 or not 下载标识:
        raise 蓝奏云请求错误("download_link_missing")
    下载地址 = f"{下载主机}/file/{quote(下载标识, safe='')}"
    return await _确保公网HTTPS地址(下载地址)


@asynccontextmanager
async def 打开归档图片(
    分享地址: str, 提取码: str
) -> AsyncIterator[ClientResponse]:
    async with _新建会话() as 会话:
        直接地址 = await _取得直接下载地址(会话, 分享地址, 提取码)
        响应 = await _请求跟随跳转(会话, 直接地址, referer=分享地址)
        try:
            if 响应.status != 200:
                raise 蓝奏云请求错误("download_status", 响应.status)
            yield 响应
        finally:
            响应.release()


async def _执行图片归档(配置: Any, 记录: dict[str, Any]) -> dict[str, Any]:
    Cookie, UID = _解析Cookie(_配置值(配置))
    地址 = str((记录.get("media") or {}).get("src") or "").strip()
    if not 地址:
        raise 蓝奏云请求错误("source_missing")
    from 功能文件.管理功能.基础功能 import 文件缓存

    临时路径 = Path(文件缓存.创建临时缓存文件("lanzou-image-", ".tmp"))
    try:
        内容类型, 大小 = await _下载QQ图片(地址, 临时路径)
        媒体 = 记录.get("media") or {}
        标识 = hashlib.sha256(
            f"{记录.get('_session') or ''}:{记录.get('message_id') or ''}".encode(
                "utf-8", errors="ignore"
            )
        ).hexdigest()[:24]
        文件名 = f"msg_{标识}{_图片扩展名(内容类型)}"
        时间戳 = int(记录.get("ts") or 0)
        月份 = datetime.fromtimestamp(时间戳).strftime("%Y-%m") if 时间戳 > 0 else datetime.now().strftime("%Y-%m")
        async with _新建会话(Cookie) as 会话:
            登录结果 = await _列出目录(会话, UID, -1)
            del 登录结果
            目录ID = await _确保归档目录(会话, UID, 月份)
            文件ID = await _上传图片(
                会话, UID, 目录ID, 临时路径, 文件名, 内容类型, 大小
            )
            提取码 = f"{secrets.randbelow(10_000):04d}"
            分享 = await _取得分享信息(会话, UID, 文件ID, 提取码)
        return {
            "share_url": 分享["share_url"],
            "password": 分享["password"],
            "file_id": 分享["file_id"],
            "content_type": 内容类型,
            "size": 大小,
            "filename": 文件名,
        }
    finally:
        临时路径.unlink(missing_ok=True)


async def 归档消息图片(配置: Any, 记录: dict[str, Any]) -> None:
    global 图片归档失败冷却
    媒体 = 记录.get("media")
    if not isinstance(媒体, dict) or str(媒体.get("type") or "").lower() not in {"图片", "image", "img"}:
        return
    if not _配置值(配置):
        return
    会话标识 = str(记录.get("_session") or "").strip()
    消息ID = str(记录.get("message_id") or "").strip()
    if not 会话标识 or not 消息ID or 媒体.get("_lanzou_archive"):
        return
    键 = (会话标识, 消息ID)
    if 键 in 图片归档已完成 or 键 in 图片归档进行中:
        return
    if float(图片归档失败冷却.get(键) or 0) > asyncio.get_running_loop().time():
        return
    图片归档进行中.add(键)
    阶段 = "download"
    try:
        from 功能文件.管理功能.基础功能 import 消息记录

        if not 消息记录.消息数据库已配置():
            return
        async with 图片归档并发限制:
            归档资料 = await _执行图片归档(配置, 记录)
            阶段 = "persist"
            if not 消息记录.更新消息媒体归档(
                会话标识, 消息ID, 归档资料, 原记录=记录
            ):
                raise 蓝奏云请求错误("message_not_found")
            图片归档已完成.add(键)
            if len(图片归档已完成) > 10000:
                图片归档已完成.clear()
                图片归档已完成.add(键)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        当前时间 = asyncio.get_running_loop().time()
        图片归档失败冷却[键] = 当前时间 + 300
        if len(图片归档失败冷却) > 10000:
            图片归档失败冷却 = {
                冷却键: 到期时间
                for 冷却键, 到期时间 in 图片归档失败冷却.items()
                if 到期时间 > 当前时间
            }
            if len(图片归档失败冷却) > 10000:
                图片归档失败冷却.clear()
                图片归档失败冷却[键] = 当前时间 + 300
        logger.warning(
            "蓝奏云图片归档失败：阶段=%s，错误类型=%s，状态=%s，业务码=%s，主机=%s",
            getattr(exc, "阶段", 阶段),
            type(exc).__name__,
            getattr(exc, "状态码", 0) or "none",
            getattr(exc, "业务码", None) if getattr(exc, "业务码", None) is not None else "none",
            getattr(exc, "主机", "") or "none",
        )
    finally:
        图片归档进行中.discard(键)
        图片归档排队中.discard(键)


def 安排归档消息图片(配置: Any, 记录: dict[str, Any]) -> bool:
    if not 图片归档接收开启 or not _配置值(配置):
        return False
    媒体 = 记录.get("media")
    if not isinstance(媒体, dict) or str(媒体.get("type") or "").lower() not in {
        "图片", "image", "img"
    }:
        return False
    会话标识 = str(记录.get("_session") or "").strip()
    消息ID = str(记录.get("message_id") or "").strip()
    if not 会话标识 or not 消息ID or 媒体.get("_lanzou_archive"):
        return False
    键 = (会话标识, 消息ID)
    if 键 in 图片归档已完成 or 键 in 图片归档进行中 or 键 in 图片归档排队中:
        return False
    if len(图片归档任务) >= 图片归档最大任务数:
        logger.warning("蓝奏云图片归档队列已满：上限=%s", 图片归档最大任务数)
        return False
    图片归档排队中.add(键)
    try:
        任务 = asyncio.get_running_loop().create_task(归档消息图片(配置, dict(记录)))
    except RuntimeError:
        图片归档排队中.discard(键)
        return False
    图片归档任务.add(任务)
    任务.add_done_callback(图片归档任务.discard)
    return True


def 启动图片归档任务() -> None:
    global 图片归档接收开启
    图片归档接收开启 = True


async def 停止图片归档任务() -> None:
    global 图片归档接收开启
    图片归档接收开启 = False
    任务列表 = [任务 for 任务 in 图片归档任务 if not 任务.done()]
    for 任务 in 任务列表:
        任务.cancel()
    if 任务列表:
        await asyncio.gather(*任务列表, return_exceptions=True)
    图片归档任务.clear()
    图片归档排队中.clear()
    图片归档进行中.clear()


def 构造网页媒体字段(
    媒体: Any, 会话标识: str, 类型: str, 消息ID: str
) -> dict[str, Any] | None:
    if not isinstance(媒体, dict):
        return None
    结果 = dict(媒体)
    归档 = 结果.pop("_lanzou_archive", None)
    if not isinstance(归档, dict):
        return 结果
    try:
        大小 = max(0, int(归档.get("size") or 0))
    except (TypeError, ValueError):
        大小 = 0
    结果["src"] = 构造消息图片代理地址(会话标识, 类型, 消息ID)
    结果["archived"] = True
    结果["content_type"] = str(归档.get("content_type") or "image/jpeg")
    结果["size"] = 大小
    return 结果


def 构造消息图片代理地址(
    会话标识: str, 类型: str, 消息ID: str
) -> str:
    查询 = urlencode(
        {
            "chat_id": str(会话标识 or ""),
            "chat_type": str(类型 or "group"),
            "message_id": str(消息ID or ""),
        }
    )
    return f"/api/message/lanzou-image?{查询}"


__all__ = [
    "安排归档消息图片",
    "构造消息图片代理地址",
    "构造网页媒体字段",
    "识别图片类型",
    "归档消息图片",
    "打开归档图片",
    "启动图片归档任务",
    "停止图片归档任务",
]
