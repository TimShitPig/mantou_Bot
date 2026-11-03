"""梧桐 App 协议：复用追书异步下载器，隔离应用身份和加密参数。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
from typing import Any, Mapping
from urllib.parse import quote_plus

from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad, unpad

from 功能文件.管理功能.小说功能.功能.疯狂追书接口 import (
    AsyncFkzsClient,
    FkzsError as WutongError,
)

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
