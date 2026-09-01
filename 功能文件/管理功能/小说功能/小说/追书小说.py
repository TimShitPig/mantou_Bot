from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception as exc:
    小说网盘 = None
    logger.warning("小说网盘模块加载失败：错误=%s", type(exc).__name__)

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning("百度网盘模块加载失败：错误=%s", type(exc).__name__)

from 功能文件.管理功能.基础功能.权限工具 import 读取字段
from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except Exception:
    AES = None
    unpad = None


追书应用名称 = "追书神器免费版"
追书包名 = "com.ushaqi.zhuishushenqi.adfree"
追书渠道 = "zhuishuFree"
追书应用标识 = "F1d36851BC0e5943042b261dFcFEd0e5"
追书第三方令牌密钥 = b"5fFf6D94079904826ab080B8179E9376"
追书H5密钥AAD = b"4e894B20a07c80331d1AC8A7e1b6c140"
追书H5密钥 = b"5fA05147846fb1528af053B770292C03"
追书搜索主机 = (
    "http://b.zhuishushenqi.com",
    "http://b01.zhuishushenqi.com",
    "http://b02.zhuishushenqi.com",
)
追书接口主机 = "https://api.zhuishushenqi.com"
追书书籍接口主机 = (
    "https://bookapi01.zhuishushenqi.com",
    "https://bookapi02.zhuishushenqi.com",
    "https://bookapi03.zhuishushenqi.com",
    "https://bookapi04.zhuishushenqi.com",
    "https://bookapi05.zhuishushenqi.com",
)
追书默认章节主机 = (
    "https://chapter3.zhuishushenqi.com",
    "https://chapterup3.zhuishushenqi.com",
    "https://chapter2.zhuishushenqi.com",
)
追书设备标识 = base64.b64encode(
    hashlib.sha256(b"mantou-bot-zhuishu-device").digest()[:16]
).decode("ascii")
追书用户标识 = hashlib.md5(追书设备标识.encode("ascii")).hexdigest()[:24]
追书用户代理 = (
    "ZhuiShuShenQi/3.45.95 (Android 9; Samsung Marlin / Samsung SM-N9760; "
    "China Mobile GSM)[preload=false;locale=zh_CN;clientidbase=]"
)
追书来源标记正则 = re.compile(
    r"(?:https?://(?:[A-Za-z0-9-]+\.)?(?:zhuishushenqi|zhuishuvip)\.com"
    r"(?::\d+)?(?:[/?:#]|$)|zssq(?:free)?://)",
    re.I,
)
追书正文最大动态并发数 = 400
追书正文最大尝试次数 = 3
追书解密并发数 = max(4, min(32, (os.cpu_count() or 4) * 2))
下载缓存目录 = 小说缓存工具.下载缓存目录
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
正文降级提示 = (
    "请安装最新版追书",
    "版权到期",
    "不再提供在线阅读",
    "该书已下架",
    "暂无阅读内容",
)
_游客令牌缓存 = ""
_游客令牌时间 = 0.0


class ZhuishuError(RuntimeError):
    pass


@dataclass
class 追书章节:
    index: int
    chapter_id: str
    name: str
    link: str
    order: int
    raw: dict[str, Any]


@dataclass
class 追书书籍:
    book_id: str
    book_name: str
    author_name: str
    chapter_num: int
    word_count: int
    intro: str
    status_text: str
    chapters: list[追书章节]
    raw_info: dict[str, Any]
    raw_toc: dict[str, Any]


def _需要AES() -> None:
    if AES is None or unpad is None:
        raise ZhuishuError("缺少 pycryptodome 依赖")


def _安全文件名(value: Any, default: str = "追书小说") -> str:
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "")).strip(" .")
    return (text or default)[:100]


def _清理文本(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def _取字段(obj: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(obj, dict):
        return default
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return default


def _安全整数(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        return int(float(str(value).replace(",", "").replace("，", "")))
    except Exception:
        return default


def _转布尔(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y", "是", "开启"}:
        return True
    if text in {"0", "false", "no", "off", "n", "否", "关闭"}:
        return False
    return default


def _补齐Base64(value: Any) -> str:
    text = str(value or "").strip()
    return text + "=" * ((4 - len(text) % 4) % 4)


def _解码Base64(value: Any) -> bytes:
    text = _补齐Base64(value)
    try:
        return base64.b64decode(text, altchars=b"-_", validate=False)
    except Exception as exc:
        raise ZhuishuError("追书密文编码异常") from exc


def _第三方令牌() -> str:
    _需要AES()
    nonce = os.urandom(12)
    cipher = AES.new(追书第三方令牌密钥, AES.MODE_GCM, nonce=nonce)
    cipher.update(追书应用标识.encode("ascii"))
    plain = json.dumps(
        {"time": int(time.time() * 1000)}, separators=(",", ":")
    ).encode("utf-8")
    encrypted, tag = cipher.encrypt_and_digest(plain)
    return 追书应用标识 + ":" + (nonce + encrypted + tag).hex()


def _请求头(*, 需要令牌: bool = False, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": 追书用户代理,
        "X-User-Agent": 追书用户代理,
        "x-app-name": 追书渠道,
        "X-Channel": "FTencent",
        "X-Uid": 追书用户标识,
        "X-Device-Id": 追书设备标识,
        "B-Zssq": 追书设备标识,
        "x-android-id": 追书设备标识,
        "weskitType": "free",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip",
    }
    if 需要令牌:
        headers["third-token"] = _第三方令牌()
    if extra:
        headers.update(extra)
    return headers


async def _请求JSON(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: Any = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> Any:
    try:
        async with session.request(
            method.upper(),
            url,
            params=params or None,
            data=data,
            headers=headers,
            allow_redirects=True,
        ) as response:
            body = await response.read()
            if response.status >= 400:
                raise ZhuishuError(f"HTTP {response.status}")
            if not body:
                raise ZhuishuError("空响应")
            try:
                result = json.loads(body.decode("utf-8", errors="replace"))
            except Exception as exc:
                raise ZhuishuError("响应不是 JSON") from exc
            if isinstance(result, dict) and result.get("errors"):
                raise ZhuishuError("接口返回错误")
            return result
    except asyncio.CancelledError:
        raise
    except ZhuishuError:
        raise
    except Exception as exc:
        raise ZhuishuError("网络请求异常") from exc


async def _登录游客账号(session: aiohttp.ClientSession) -> str:
    """按追书免费版的游客登录流程换取短期会话令牌。"""
    数据: Any = None
    最后错误: Exception | None = None
    for 尝试次数 in range(1, 4):
        try:
            数据 = await _请求JSON(
                session,
                f"{追书接口主机}/user/login",
                method="POST",
                data={
                    "platform_code": "tourist",
                    "platform_uid": 追书设备标识,
                    "platform_token": 追书设备标识,
                    "version": "3.45.95",
                    "packageName": 追书包名,
                    "promoterId": "",
                    "channelName": "FTencent",
                },
                headers=_请求头(
                    需要令牌=True,
                    extra={"Content-Type": "application/x-www-form-urlencoded"},
                ),
            )
            break
        except Exception as exc:
            最后错误 = exc
            if 尝试次数 < 3:
                await asyncio.sleep(0.25 * 尝试次数)
    if 数据 is None and 最后错误 is not None:
        raise ZhuishuError("游客会话获取失败") from 最后错误
    token = str(数据.get("token") or "") if isinstance(数据, dict) else ""
    if not token or not _转布尔(数据.get("ok") if isinstance(数据, dict) else False):
        raise ZhuishuError("游客会话获取失败")
    return token


async def _获取游客令牌(session: aiohttp.ClientSession, *, 强制刷新: bool = False) -> str:
    global _游客令牌缓存, _游客令牌时间
    现在 = time.monotonic()
    if (
        not 强制刷新
        and _游客令牌缓存
        and 现在 - _游客令牌时间 < 900
    ):
        return _游客令牌缓存
    token = await _登录游客账号(session)
    _游客令牌缓存 = token
    _游客令牌时间 = 现在
    return token


def _标准化列表(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("books", "data", "list", "tocs", "toc", "sources"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            nested = _标准化列表(value)
            if nested:
                return nested
    return []


async def 搜索小说(
    session: aiohttp.ClientSession,
    关键词: str,
    *,
    需要数量: int = 20,
) -> list[dict[str, Any]]:
    参数 = {
        "model.query": str(关键词 or "").strip(),
        "model.contentType2": "1",
        "model.packageName": 追书包名,
        "token": "",
        "userid": "",
        "dflag": "",
        "dfsign": "",
        "channel": 追书渠道,
    }
    最后错误: Exception | None = None
    for host in 追书搜索主机:
        try:
            数据 = await _请求JSON(
                session,
                f"{host}/books/fuzzy-search",
                params=参数,
                headers=_请求头(),
            )
            书籍列表 = _标准化列表(数据)
            return [书籍 for 书籍 in 书籍列表 if isinstance(书籍, dict)][:
                max(1, int(需要数量 or 20))
            ]
        except Exception as exc:
            最后错误 = exc
    if 最后错误:
        raise ZhuishuError("搜索失败") from 最后错误
    return []


async def 获取书籍详情(
    session: aiohttp.ClientSession,
    书籍编号: str,
) -> dict[str, Any]:
    for host in (追书接口主机, *追书书籍接口主机):
        try:
            数据 = await _请求JSON(
                session,
                f"{host}/book/{书籍编号}",
                headers=_请求头(),
            )
            if isinstance(数据, dict) and (
                数据.get("_id") or 数据.get("id") or 数据.get("title")
            ):
                return 数据
        except Exception:
            continue
    for host in 追书书籍接口主机:
        try:
            数据 = await _请求JSON(
                session,
                f"{host}/book/crypto/{书籍编号}",
                params={
                    "timestamp": int(time.time() * 1000),
                    "token": "",
                    "useNewCat": "true",
                    "packageName": 追书包名,
                },
                headers=_请求头(需要令牌=True),
            )
            if isinstance(数据, dict):
                return 数据
        except Exception:
            continue
    raise ZhuishuError("详情获取失败")


async def _选择目录编号(
    session: aiohttp.ClientSession,
    书籍编号: str,
) -> str:
    for host in 追书书籍接口主机:
        try:
            数据 = await _请求JSON(
                session,
                f"{host}/btoc/crypto",
                params={
                    "book": 书籍编号,
                    "view": "summary",
                    "platform": "android",
                    "token": "",
                },
                headers=_请求头(需要令牌=True),
            )
            for item in _标准化列表(数据):
                if isinstance(item, dict):
                    编号 = _取字段(item, "_id", "id", "tocId", "toc_id")
                    if 编号:
                        return str(编号)
        except Exception:
            continue
    for endpoint in ("atoc", "ctoc"):
        try:
            数据 = await _请求JSON(
                session,
                f"{追书接口主机}/{endpoint}",
                params={"book": 书籍编号, "view": "summary", "platform": "android"},
                headers=_请求头(),
            )
            for item in _标准化列表(数据):
                if isinstance(item, dict):
                    编号 = _取字段(item, "_id", "id", "tocId", "toc_id")
                    if 编号:
                        return str(编号)
        except Exception:
            continue
    return ""


async def 获取目录(
    session: aiohttp.ClientSession,
    书籍编号: str,
) -> dict[str, Any]:
    目录编号 = await _选择目录编号(session, 书籍编号)
    候选 = []
    if 目录编号:
        for host in 追书书籍接口主机:
            候选.append(
                (
                    f"{host}/dtoc/crypto/{书籍编号}/{目录编号}",
                    {"view": "chapters", "platform": "android", "token": ""},
                    _请求头(需要令牌=True),
                )
            )
        for endpoint in ("atoc", "ctoc"):
            候选.append(
                (
                    f"{追书接口主机}/{endpoint}/{目录编号}",
                    {"view": "chapters", "platform": "android"},
                    _请求头(),
                )
            )
    # 部分公开书源只接受 /dtoc/{toc_id}，作为兼容回退。
    for host in 追书书籍接口主机:
        for identifier in (目录编号, 书籍编号):
            if not identifier:
                continue
            候选.append(
                (
                    f"{host}/dtoc/{identifier}",
                    {
                        "view": "chapters",
                        "platform": "android",
                        "token": "",
                        "packageName": 追书包名,
                    },
                    _请求头(需要令牌=True),
                )
            )
    for url, params, headers in 候选:
        try:
            数据 = await _请求JSON(session, url, params=params, headers=headers)
            if not isinstance(数据, dict):
                continue
            if isinstance(数据.get("data"), dict) and 数据["data"].get("chapters"):
                数据 = dict(数据["data"])
            if 数据.get("chapters"):
                if 目录编号:
                    数据.setdefault("_id", 目录编号)
                return 数据
        except Exception:
            continue
    raise ZhuishuError("目录获取失败")


def _转换章节(目录: dict[str, Any]) -> list[追书章节]:
    原始列表 = 目录.get("chapters") or []
    章节列表: list[追书章节] = []
    for index, item in enumerate(原始列表, 1):
        if not isinstance(item, dict):
            continue
        order = _安全整数(_取字段(item, "order", "seqId", "Order"), index) or index
        chapter_id = str(_取字段(item, "id", "_id", "chapterId", default="") or "")
        link = str(_取字段(item, "link", "url", default="") or "")
        name = _清理文本(_取字段(item, "title", "name", default=f"第{index}章"))
        if not chapter_id or not link:
            continue
        章节列表.append(
            追书章节(
                index=index,
                chapter_id=chapter_id,
                name=name or f"第{index}章",
                link=link,
                order=order,
                raw=dict(item),
            )
        )
    return 章节列表


def _解密H5章节密钥(value: Any) -> bytes:
    """解开逐章 key 接口返回的 key 字段；noEncrypt 字段直接使用。"""
    _需要AES()
    raw = _解码Base64(value)
    if len(raw) <= 12 + 16:
        raise ZhuishuError("章节密钥长度异常")
    nonce, payload = raw[:12], raw[12:]
    cipher = AES.new(追书H5密钥, AES.MODE_GCM, nonce=nonce)
    cipher.update(追书H5密钥AAD)
    plain = cipher.decrypt_and_verify(payload[:-16], payload[-16:])
    key = _解码Base64(plain.decode("utf-8"))
    if len(key) not in (16, 24, 32):
        raise ZhuishuError("章节密钥不可用")
    return key


def _解析单章密钥(data: Any, order: int) -> bytes:
    if not isinstance(data, dict) or not _转布尔(data.get("ok"), False):
        message = str(_取字段(data, "message", "msg", "code", default="") or "")
        if "TOKEN_INVALID" in message.upper():
            raise ZhuishuError("游客会话失效")
        raise ZhuishuError("章节密钥接口异常")
    items = data.get("data")
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise ZhuishuError("章节密钥为空")
    item = next(
        (
            candidate
            for candidate in items
            if isinstance(candidate, dict)
            and _安全整数(candidate.get("order"), order) == order
        ),
        next((candidate for candidate in items if isinstance(candidate, dict)), None),
    )
    if not isinstance(item, dict):
        raise ZhuishuError("章节密钥为空")
    no_encrypt = item.get("noEncrypt")
    if no_encrypt:
        key = _解码Base64(no_encrypt)
    elif item.get("key"):
        key = _解密H5章节密钥(item["key"])
    else:
        raise ZhuishuError("章节密钥为空")
    if len(key) not in (16, 24, 32):
        raise ZhuishuError("章节密钥不可用")
    return key


async def _获取单章密钥(
    session: aiohttp.ClientSession,
    book_id: str,
    order: int,
    token: str,
    解密执行器: ThreadPoolExecutor | None = None,
) -> bytes:
    参数 = {
        "token": token,
        "orderType": "ad",
        "version": "v2",
        "appName": "androidMaster",
        "productLine": "1",
        "leftOrders": "",
    }
    最后错误: Exception | None = None
    for host in 追书书籍接口主机:
        try:
            数据 = await _请求JSON(
                session,
                f"{host}/book/crypto/{book_id}/chapters/{order}/key",
                params=参数,
                headers=_请求头(需要令牌=True),
            )
            if 解密执行器 is None:
                return _解析单章密钥(数据, order)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                解密执行器,
                _解析单章密钥,
                数据,
                order,
            )
        except Exception as exc:
            最后错误 = exc
            if isinstance(exc, ZhuishuError) and "游客会话失效" in str(exc):
                break
    raise ZhuishuError("章节密钥获取失败") from 最后错误


def _章节内容对象(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    for key in ("chapter", "data"):
        if isinstance(data.get(key), dict):
            return data[key]
    return data


def _正文是降级提示(text: Any) -> bool:
    value = _清理文本(text)
    return any(marker in value for marker in 正文降级提示)


def _提取密文(data: Any) -> tuple[str, str]:
    chapter = _章节内容对象(data)
    cp = _取字段(chapter, "cpContent", "content", default="")
    if cp:
        return "cipher", str(cp)
    images = _取字段(chapter, "images", default="")
    if images:
        return "cipher", str(images)
    body = _取字段(chapter, "body", "text", default="")
    return "plain", str(body or "")


async def _请求章节数据(
    session: aiohttp.ClientSession,
    章节: 追书章节,
    目录: dict[str, Any],
) -> dict[str, Any]:
    hosts: list[str] = []
    for key in ("chapterHost", "chapterHosts", "chapter_host"):
        value = 目录.get(key)
        if isinstance(value, list):
            hosts.extend(str(item).rstrip("/") for item in value if item)
        elif isinstance(value, str) and value.strip():
            hosts.append(value.rstrip("/"))
    for host in 追书默认章节主机:
        if host not in hosts:
            hosts.append(host)
    encoded_link = urllib.parse.quote(章节.link, safe="")
    章节路径 = "picture2" if "picture.zhuishushenqi.com" in 章节.link else "chapter2"
    最后错误: Exception | None = None
    for host in hosts:
        try:
            data = await _请求JSON(
                session,
                f"{host}/{章节路径}/{encoded_link}",
                headers=_请求头(),
            )
            kind, content = _提取密文(data)
            if kind == "cipher" and content:
                return data
            if content and not _正文是降级提示(content):
                return data
            raise ZhuishuError("章节返回降级提示")
        except Exception as exc:
            最后错误 = exc
    raise ZhuishuError("章节请求失败") from 最后错误


def _解密正文同步(cipher_text: str, key: bytes) -> str:
    _需要AES()
    raw = _解码Base64(cipher_text)
    if len(raw) <= 16 or len(raw[16:]) % 16:
        raise ZhuishuError("正文密文长度异常")
    候选 = ((raw[:16], raw[16:]), (b"\0" * 16, raw))
    for iv, encrypted in 候选:
        try:
            plain = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(encrypted)
            plain = unpad(plain, AES.block_size)
            text = plain.decode("utf-8")
            text = _清理文本(text)
            if text and not _正文是降级提示(text):
                return text
        except Exception:
            continue
    raise ZhuishuError("正文解密失败")


async def _下载章节一轮(
    session: aiohttp.ClientSession,
    书籍: 追书书籍,
    目录: dict[str, Any],
    章节列表: list[追书章节],
    游客令牌: str,
    并发数: int,
    解密执行器: ThreadPoolExecutor,
    进度回调: Any,
) -> list[tuple[int, str, str]]:
    信号量 = asyncio.Semaphore(max(1, 并发数))

    async def 下载一章(章节: 追书章节) -> tuple[int, str, str]:
        async with 信号量:
            try:
                key_result, body_result = await asyncio.gather(
                    _获取单章密钥(
                        session,
                        书籍.book_id,
                        章节.order,
                        游客令牌,
                        解密执行器,
                    ),
                    _请求章节数据(session, 章节, 目录),
                    return_exceptions=True,
                )
                if isinstance(key_result, Exception):
                    raise key_result
                if isinstance(body_result, Exception):
                    raise body_result
                kind, value = _提取密文(body_result)
                if not value:
                    raise ZhuishuError("章节正文为空")
                if kind == "plain":
                    text = _清理文本(value)
                    if not text or _正文是降级提示(text):
                        raise ZhuishuError("章节正文不可用")
                else:
                    loop = asyncio.get_running_loop()
                    text = await loop.run_in_executor(
                        解密执行器,
                        _解密正文同步,
                        value,
                        key_result,
                    )
                await 进度回调(True)
                return 章节.index, text, ""
            except Exception as exc:
                await 进度回调(False)
                return 章节.index, "", type(exc).__name__

    return list(
        await asyncio.gather(*(下载一章(章节) for 章节 in 章节列表))
    )


async def 下载全部章节(
    session: aiohttp.ClientSession,
    书籍: 追书书籍,
    目录: dict[str, Any],
    游客令牌: str,
) -> list[dict[str, str]]:
    总数 = len(书籍.chapters)
    if not 总数:
        raise ZhuishuError("没有可下载的章节")

    结果: dict[int, str] = {}
    已完成 = 0
    成功数 = 0
    下次进度 = 25
    进度锁 = asyncio.Lock()
    解密执行器 = ThreadPoolExecutor(
        max_workers=min(追书解密并发数, max(1, 总数)),
        thread_name_prefix="zhuishu-decode",
    )

    logger.info(
        "追书小说章节进度：书籍编号=%s, 进度=0/%s, 百分比=0%%, "
        "章节数=%s, 动态并发上限=%s, 解密并发数=%s",
        书籍.book_id,
        总数,
        总数,
        min(追书正文最大动态并发数, 总数),
        min(追书解密并发数, 总数),
    )

    async def 记录进度(成功: bool) -> None:
        nonlocal 已完成, 成功数, 下次进度
        async with 进度锁:
            已完成 += 1
            if 成功:
                成功数 += 1
            百分比 = 已完成 * 100 // 总数
            if 百分比 < 下次进度 and 已完成 != 总数:
                return
            logger.info(
                "追书小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s",
                书籍.book_id,
                已完成,
                总数,
                百分比,
                成功数,
                已完成 - 成功数,
            )
            while 下次进度 <= 百分比:
                下次进度 += 25

    待处理 = list(书籍.chapters)
    try:
        for 尝试次数 in range(1, 追书正文最大尝试次数 + 1):
            if not 待处理:
                break
            本轮结果 = await _下载章节一轮(
                session,
                书籍,
                目录,
                待处理,
                游客令牌,
                min(
                    追书正文最大动态并发数,
                    max(1, len(待处理)),
                ),
                解密执行器,
                记录进度 if 尝试次数 == 1 else (lambda _ok: asyncio.sleep(0)),
            )
            下轮: list[追书章节] = []
            for index, text, error_type in 本轮结果:
                if text:
                    结果[index] = text
                else:
                    章节 = next((item for item in 待处理 if item.index == index), None)
                    if 章节 is not None:
                        下轮.append(章节)
                    logger.debug(
                        "追书章节下载失败：书籍编号=%s, 章节序号=%s, 轮次=%s/%s, 错误类型=%s",
                        书籍.book_id,
                        index,
                        尝试次数,
                        追书正文最大尝试次数,
                        error_type,
                    )
            待处理 = 下轮
            if 待处理 and 尝试次数 < 追书正文最大尝试次数:
                await asyncio.sleep(min(1.0, 0.25 * 尝试次数))
    finally:
        解密执行器.shutdown(wait=False, cancel_futures=True)

    if 待处理 or len(结果) != 总数:
        raise ZhuishuError(f"章节正文不完整：success={len(结果)}, total={总数}")
    return [
        {"id": 章节.chapter_id, "title": 章节.name, "content": 结果[章节.index]}
        for 章节 in 书籍.chapters
    ]


async def _获取书籍(
    session: aiohttp.ClientSession,
    book_id: str,
) -> tuple[追书书籍, dict[str, Any]]:
    详情 = await 获取书籍详情(session, book_id)
    目录 = await 获取目录(session, book_id)
    章节 = _转换章节(目录)
    if not 章节:
        raise ZhuishuError("目录为空")
    声明章节数 = _安全整数(
        _取字段(目录, "chaptersCount", "chapterCount", "chapter_num"),
        0,
    )
    if 声明章节数 and 声明章节数 != len(章节):
        raise ZhuishuError("目录不完整")
    真实书籍编号 = str(_取字段(目录, "book", "bookId", default=book_id) or book_id)
    书名 = _清理文本(
        _取字段(详情, "title", "name", "book_name", default=f"{追书应用名称}{book_id}")
    )
    作者 = _清理文本(_取字段(详情, "author", "originalAuthor", default="未知")) or "未知"
    完结 = _转布尔(_取字段(详情, "isSerial", "is_serial"), default=False) is False
    状态 = "完结" if 完结 else "连载"
    书籍 = 追书书籍(
        book_id=真实书籍编号,
        book_name=书名 or str(book_id),
        author_name=作者,
        chapter_num=len(章节),
        word_count=_安全整数(_取字段(详情, "wordCount", "word_count", "words"), 0),
        intro=_清理文本(_取字段(详情, "longIntro", "shortIntro", "intro", "description", default="")),
        status_text=状态,
        chapters=章节,
        raw_info=详情,
        raw_toc=目录,
    )
    return 书籍, 目录


def 获取追书小说回复流(
    event: Any,
    命令文本: str,
    配置: Any = None,
) -> AsyncIterator[str] | None:
    链接 = 提取直接追书链接(命令文本) or 提取事件追书链接(event)
    if not 链接:
        return None
    return 生成下载回复流(event, 链接, 配置)


async def 生成下载回复流(
    event: Any,
    链接: str,
    配置: Any = None,
) -> AsyncIterator[str]:
    if AES is None or unpad is None:
        logger.warning("追书小说下载失败：缺少 pycryptodome 依赖")
        yield "下载失败 请重试"
        return
    try:
        书籍编号 = 提取追书书籍编号(链接)
        if not 书籍编号:
            raise ZhuishuError("没有识别到书籍编号")
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=60)
        connector = aiohttp.TCPConnector(
            limit=追书正文最大动态并发数,
            limit_per_host=追书正文最大动态并发数,
            ttl_dns_cache=300,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            书籍, 目录 = await _获取书籍(session, 书籍编号)
            logger.info(
                "追书小说开始下载：书籍编号=%s, 书名=%s, 作者=%s, "
                "公开章节=%s, 目录章节=%s, 模式=游客免费密钥+逐章正文",
                书籍.book_id,
                书籍.book_name,
                书籍.author_name,
                len(书籍.chapters),
                len(目录.get("chapters") or []),
            )
            yield 格式化下载提示(书籍)
            游客令牌 = await _获取游客令牌(session)
            logger.info(
                "追书小说游客会话已建立：书籍编号=%s, 章节数=%s",
                书籍.book_id,
                len(书籍.chapters),
            )
            章节内容 = await 下载全部章节(session, 书籍, 目录, 游客令牌)
            文件名, 文件内容 = 生成小说文件内容(书籍, 章节内容)
            logger.info(
                "追书小说章节下载完成：书籍编号=%s, 成功=%s, 文件大小=%s",
                书籍.book_id,
                len(章节内容),
                len(文件内容),
            )

        发送结果 = await 准备发送文本文件给当前会话(
            event,
            文件名,
            文件内容,
            配置,
            书名=书籍.book_name,
            作者=书籍.author_name,
        )
        if 发送结果.get("sent"):
            启动百度后台上传并清理源文件(
                配置, 发送结果.get("source_cache_path"), 文件名
            )
            return
        降级文本 = str(发送结果.get("fallback_text") or "")
        if 降级文本:
            try:
                yield 降级文本
            finally:
                启动百度后台上传并清理源文件(
                    配置, 发送结果.get("source_cache_path"), 文件名
                )
            return
        logger.warning(
            "追书小说完成消息发送失败：书籍编号=%s, 错误类型=%s",
            书籍编号,
            type(发送结果.get("error")).__name__,
        )
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(
            "追书小说下载失败：书籍编号=%s, 错误类型=%s",
            提取追书书籍编号(链接) or "unknown",
            type(exc).__name__,
        )
        yield "下载失败 请重试"


def 生成小说文件内容(
    书籍: 追书书籍,
    章节内容: list[dict[str, str]],
) -> tuple[str, bytes]:
    内容: list[str] = [
        文件声明,
        "",
        f"名称：{书籍.book_name}",
        f"作者：{书籍.author_name or '未知'}",
        f"状态：{书籍.status_text}",
        f"字数：{格式化字数(书籍.word_count)}",
        f"书籍ID：{书籍.book_id}",
        f"章节数：{len(书籍.chapters)}",
        "",
    ]
    if 书籍.intro:
        内容.extend(["简介：", 书籍.intro, ""])
    for item in 章节内容:
        title = str(item.get("title") or "")
        text = 去除章节正文重复标题(title, item.get("content"))
        内容.extend([title, "", text, ""])
    return 生成小说文件名(书籍), "\r\n".join(内容).encode("utf-8")


def 生成小说文件名(书籍: 追书书籍) -> str:
    return (
        f"[{书籍.status_text}]书名：{_安全文件名(书籍.book_name)} "
        f"作者：{_安全文件名(书籍.author_name, '未知')}.txt"
    )


def 格式化下载提示(书籍: 追书书籍) -> str:
    return "\n".join(
        [
            f"书名：{书籍.book_name or '未知'}",
            f"作者：{书籍.author_name or '未知'}",
            f"状态：{书籍.status_text}",
            f"章节：{len(书籍.chapters)} 章",
            f"字数：{格式化字数(书籍.word_count)}",
            "",
            "正在下载中请稍等.....",
        ]
    )


def 格式化字数(value: Any) -> str:
    number = _安全整数(value, 0)
    if number <= 0:
        return "未知"
    if number >= 10000:
        return f"{number / 10000:.1f}".rstrip("0").rstrip(".") + "万字"
    return f"{number}字"


async def 准备发送文本文件给当前会话(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    logger.info("追书小说准备上传：文件=%s, 大小=%s", 文件名, len(文件内容))
    缓存路径 = 写入下载缓存文件(文件名, 文件内容)
    if 小说网盘 is None:
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "网盘模块未加载"}
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not 网盘结果.get("success"):
            logger.warning("追书小说主网盘上传失败：文件=%s", 文件名)
            删除下载缓存文件(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "上传失败"}
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(网盘结果.get("share_url") or "")
        )
        if 完成结果.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 缓存路径, "error": ""}
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "完成消息发送失败"}
    except Exception as exc:
        logger.warning("追书小说主网盘上传或完成消息发送失败：文件=%s, 错误类型=%s", 文件名, type(exc).__name__)
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": type(exc).__name__}


def 启动百度后台上传并清理源文件(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    if not 源缓存路径:
        return

    async def 执行() -> None:
        try:
            if 百度网盘 is not None:
                结果 = await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
                if 结果.get("success"):
                    logger.info("追书小说百度网盘后台上传成功：文件=%s", 文件名)
                elif 结果.get("enabled"):
                    logger.warning("追书小说百度网盘后台上传失败：文件=%s", 文件名)
        except Exception as exc:
            logger.warning("追书小说百度网盘后台上传异常：文件=%s, 错误类型=%s", 文件名, type(exc).__name__)
        finally:
            删除下载缓存文件(源缓存路径)

    try:
        asyncio.create_task(执行())
    except RuntimeError:
        删除下载缓存文件(源缓存路径)


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(缓存路径)
    return 缓存路径


def 删除下载缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    if not 小说缓存工具.删除下载缓存文件(缓存路径):
        logger.debug("追书小说下载缓存仍在等待续传")
        return
    logger.info("追书小说下载缓存文件已删除")


def 生成不冲突缓存路径(文件名: str) -> Path:
    安全名称 = Path(_安全文件名(文件名)).name or "追书小说.txt"
    if not 安全名称.lower().endswith(".txt"):
        安全名称 += ".txt"
    路径 = 下载缓存目录 / 安全名称
    if not 路径.exists():
        return 路径
    for number in range(1, 1000):
        候选 = 下载缓存目录 / f"{路径.stem}_{number}{路径.suffix}"
        if not 候选.exists():
            return 候选
    raise ZhuishuError("下载缓存文件名冲突")


def 提取直接追书链接(文本: Any) -> str:
    if 文本 is None:
        return ""
    value = str(文本).strip()
    return 提取追书链接(value)


def 提取事件追书链接(event: Any) -> str:
    候选 = [event, getattr(event, "message_obj", None)]
    for obj in 候选:
        if obj is None:
            continue
        for field in ("message_str", "raw_message", "message", "text"):
            link = 提取追书链接(读取字段(obj, field))
            if link:
                return link
    return ""


def 提取追书链接(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        for child in value:
            link = 提取追书链接(child)
            if link:
                return link
        return ""
    if isinstance(value, dict):
        for child in value.values():
            link = 提取追书链接(child)
            if link:
                return link
        return ""
    text = str(value)
    patterns = (
        r"https?://(?:(?:m|www|h5|book)\.)?zhuishushenqi\.com/(?:books?|detail)/[0-9a-f]{16,32}(?:[^\s'\"<>，。]*)",
        r"https?://(?:(?:m|www|h5|book)\.)?zhuishuvip\.com/(?:books?|detail)/[0-9a-f]{16,32}(?:[^\s'\"<>，。]*)",
        r"zssq(?:free)?://(?:books?|detail)/[0-9a-f]{16,32}(?:[^\s'\"<>，。]*)",
        r"zssq(?:free)?://openDeepLink[^\s'\"<>，。]*?(?:param|bookId|book_id)=?[=:]([0-9a-f]{16,32})[^\s'\"<>，。]*",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).rstrip(".,!?！？;；)")
    # 查询参数兜底仅适用于明确带有追书域名/协议的消息，避免抢走番茄长读等同样使用 book_id 的链接。
    if 追书来源标记正则.search(text) and re.search(
        r"(?:bookId|book_id|book|bid)=", text, flags=re.IGNORECASE
    ):
        book_id = 提取追书书籍编号(text)
        if book_id:
            return 构造追书链接(book_id)
    return ""


def 提取追书书籍编号(文本: Any) -> str:
    value = str(文本 or "").strip()
    if not 追书来源标记正则.search(value):
        return ""
    patterns = (
        r"/(?:books?|detail)/([0-9a-f]{16,32})(?:[/?#]|$)",
        r"[?&](?:bookId|book_id|bid|id)=([0-9a-f]{16,32})(?:[&#]|$)",
        r"(?:param|bookId|book_id)=([0-9a-f]{16,32})(?:[&#/?]|$)",
        r"(?:^|[^0-9a-f])([0-9a-f]{24})(?:$|[^0-9a-f])",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def 构造追书链接(书籍编号: str) -> str:
    return f"https://m.zhuishushenqi.com/books/{书籍编号}?shareFrom=app"
