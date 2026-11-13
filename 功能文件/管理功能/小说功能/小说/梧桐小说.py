"""梧桐协议客户端与下载入口，复用疯狂追书的基础调度和文件流程。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import re
import secrets
from typing import Any, AsyncIterator, Mapping
from urllib.parse import quote_plus

from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad, unpad

try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger(__name__)

from 功能文件.管理功能.小说功能.小说 import 番茄小说, 疯狂追书小说

AsyncFkzsClient = 疯狂追书小说.AsyncFkzsClient
WutongError = 疯狂追书小说.FkzsError

APP_PKG = "com.ushaqi.zhuishushenqi.ninenine"
SIGN_KEY = "83jR_DYJWSfONkqpPkOVVu4HTfe-8_CeM5wI"
API_HOST = "https://fiction.52leho.com"
OPENAPI_HOST = "https://bookopenapi.zhuishushenqi.com"
_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _java_urlencode(value: str) -> str:
    return quote_plus(value, safe="*").replace("~", "%7E")


def encrypt_app_params(params: Mapping[str, Any]) -> str:
    encoded = [
        f"{key}={_java_urlencode(_java_urlencode(str(value)))}"
        for key, value in sorted(params.items())
        if key and value is not None and str(value)
    ]
    seed = secrets.choice(_ALPHABET)
    key = SIGN_KEY[:36 - ord(seed) % 10].encode("ascii")
    iv_source = base64.urlsafe_b64encode(hashlib.md5(key).digest()[:8]).decode("ascii")
    cipher = DES.new(key[:8], DES.MODE_CBC, iv=iv_source[:8].encode("ascii"))
    encrypted = cipher.encrypt(pad("&".join(encoded).encode("utf-8"), DES.block_size))
    tail = "".join(secrets.choice(_ALPHABET) for _ in range((ord(seed) % 10) % 3))
    return seed + iv_source + base64.urlsafe_b64encode(encrypted).decode("ascii") + tail


def decrypt_app_response(raw: bytes | str) -> Any:
    try:
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        text = text.strip()
        if not text:
            raise WutongError("empty_response", retryable=True)
        if text.startswith(("{", "[")):
            return json.loads(text)
        encoded = text.encode("ascii")
        encoded += b"=" * (-len(encoded) % 4)
        ciphertext = base64.b64decode(encoded, validate=True)
        cipher = AES.new(SIGN_KEY[:16].encode("ascii"), AES.MODE_ECB)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")
        return json.loads(plaintext)
    except (ValueError, TypeError, AttributeError, UnicodeError, binascii.Error):
        raise WutongError("invalid_app_response") from None


class AsyncWutongClient(AsyncFkzsClient):
    """每个客户端持有梧桐身份；不会修改其他平台的会话或全局参数。"""

    app_pkg = APP_PKG
    app_name = ""
    app_version = "1.5.4"
    version_code = "26101616"
    platform_name = "梧桐"
    worker_prefix = "mantou-wutong"
    device_defaults = {
        "device_brand": "Xiaomi",
        "device_model": "MI 8",
        "inner_version": "0",
        "os_version": "QKQ1.190828.002",
        "os_api": "33",
        "resolution": "1080x2340",
    }
    encrypt_params = staticmethod(encrypt_app_params)
    decrypt_response = staticmethod(decrypt_app_response)

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("api_host", API_HOST)
        kwargs.setdefault("openapi_host", OPENAPI_HOST)
        super().__init__(**kwargs)
        self.common["uuid"] = self.common["android_id"]

    def _app_form(self, params: Mapping[str, Any], encrypted: str) -> dict[str, str]:
        return {**{key: str(value) for key, value in params.items()}, "p": encrypted}

    @staticmethod
    def _encode_chapter_link(link: str) -> str:
        return _java_urlencode(link)

    @staticmethod
    def _chapter_link_md5(link: str, encoded: str) -> str:
        return hashlib.md5(encoded.encode("utf-8")).hexdigest()

_下载命令正则 = re.compile(r"梧桐(?:小说)?[\s：:]+([0-9a-f]{24})", re.I)
提取梧桐书籍编号 = 疯狂追书小说.提取疯狂追书书籍编号
生成梧桐小说文件内容 = 疯狂追书小说.生成疯狂追书小说文件内容


def 提取梧桐来源(event: Any, 命令文本: Any = "") -> str | None:
    消息文本 = event.get("message_str") if isinstance(event, Mapping) else getattr(event, "message_str", "")
    for 文本 in (命令文本, 消息文本):
        if isinstance(文本, str):
            匹配 = _下载命令正则.fullmatch(文本.strip())
            if 匹配:
                return 匹配.group(1).lower()
    return None


def 规范化梧桐书籍信息(书籍编号: str, 详情: Mapping[str, Any]) -> dict[str, Any]:
    信息 = 疯狂追书小说.规范化疯狂追书书籍信息(书籍编号, 详情)
    if not 番茄小说.清理番茄网页文本(详情.get("title")):
        信息["title"] = f"梧桐小说{书籍编号}"
    return 信息


def 生成梧桐下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    return 疯狂追书小说.生成疯狂追书下载回复流(
        event, 来源, 配置, 客户端类=AsyncWutongClient,
        平台名="梧桐", 书籍信息规范化=规范化梧桐书籍信息,
    )


def 获取梧桐小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取梧桐来源(event, 命令文本)
    return 生成梧桐下载回复流(event, 来源, 配置) if 来源 else None


async def 搜索梧桐小说(关键词: str, 数量上限: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        上限 = max(1, min(int(数量上限), 30))
        async with AsyncWutongClient(concurrency=2) as client:
            搜索 = await client.search(关键词, page=1, page_size=上限)
        return [
            {"status": 书.get("status"), "platform": "梧桐", "book_id": str(书["book_id"]),
             "title": 书["title"], "author": 书.get("author") or "未知", "url": "",
             "word_count": 书.get("word_count"), "chapter_count": 书.get("chapter_count"),
             "intro": 书.get("intro") or "", "score": 书.get("score"), "heat": 书.get("read_num")}
            for 书 in 搜索.get("items", [])[:上限]
            if 提取梧桐书籍编号(书.get("book_id")) and 书.get("title")
        ]
    except Exception as exc:
        logger.debug("梧桐小说搜索失败：error_type=%s", type(exc).__name__)
        return []
