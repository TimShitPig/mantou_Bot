from __future__ import annotations

import asyncio
import importlib.util
import struct
import sys
import types
import unittest
import zlib
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
QQ_READER_PATH = ROOT / "功能文件" / "管理功能" / "小说功能" / "小说" / "QQ阅读.py"


class _Logger:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


def _package(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


def _load_qq_reader_module():
    astrbot = _package("astrbot")
    astrbot_api = types.ModuleType("astrbot.api")
    astrbot_api.logger = _Logger()
    astrbot.api = astrbot_api
    sys.modules["astrbot.api"] = astrbot_api

    _package("功能文件")
    _package("功能文件.管理功能")
    _package("功能文件.管理功能.基础功能")
    权限工具 = types.ModuleType("功能文件.管理功能.基础功能.权限工具")
    权限工具.是群文件清理管理员 = lambda *args, **kwargs: False
    sys.modules[权限工具.__name__] = 权限工具
    运行状态数据库 = types.ModuleType("功能文件.管理功能.基础功能.运行状态数据库")
    运行状态数据库.读取运行状态值 = lambda *args, **kwargs: ""
    运行状态数据库.写入运行状态值 = lambda *args, **kwargs: None
    sys.modules[运行状态数据库.__name__] = 运行状态数据库

    网盘功能 = _package("功能文件.管理功能.网盘功能")
    网盘功能.UC网盘 = None
    网盘功能.百度网盘 = None
    _package("功能文件.管理功能.小说功能")
    小说功能 = _package("功能文件.管理功能.小说功能.功能")
    小说功能.下载缓存清理 = types.SimpleNamespace()

    spec = importlib.util.spec_from_file_location("qq_reader_publication_test_module", QQ_READER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


QQ阅读 = _load_qq_reader_module()


def _zipcrypto_encrypt(data: bytes, password: bytes) -> bytes:
    crypto = QQ阅读.出版书ZipCrypto(password)
    encrypted = bytearray()
    for value in data:
        encrypted.append(value ^ crypto.解密字节())
        crypto.更新(value)
    return bytes(encrypted)


def _encrypted_stored_zip_entry(name: str, content: bytes, password: bytes) -> bytes:
    name_bytes = name.encode("utf-8")
    crc = zlib.crc32(content) & 0xFFFFFFFF
    encryption_header = b"zip-header!" + bytes([(crc >> 24) & 0xFF])
    payload = _zipcrypto_encrypt(encryption_header + content, password)
    local_header = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        20,
        0x1,
        0,
        0,
        0,
        crc,
        len(payload),
        len(content),
        len(name_bytes),
        0,
    )
    return local_header + name_bytes + payload


class QQ阅读出版书测试(unittest.IsolatedAsyncioTestCase):
    def test_浏览器_cookie_会识别_yw_登录字段(self):
        登录态 = QQ阅读.解析QQ阅读Cookie("tracking=1; ywguid=account-id; ywkey=account-key")

        self.assertEqual(登录态["ywguid"], "account-id")
        self.assertEqual(登录态["ywkey"], "account-key")
        self.assertTrue(QQ阅读.有效QQ阅读登录态(登录态))

    def test_正确密码可以解包加密存储条目(self):
        archive = _encrypted_stored_zip_entry("OPS/chapter.xhtml", "正文可以正常读取".encode("utf-8"), b"right-password")

        entries = QQ阅读.解包出版书Zip条目(archive, b"right-password")

        self.assertEqual(entries, [("OPS/chapter.xhtml", "正文可以正常读取".encode("utf-8"))])

    def test_错误密码不能被当成出版书正文(self):
        archive = _encrypted_stored_zip_entry("OPS/chapter.xhtml", "正文可以正常读取".encode("utf-8"), b"right-password")

        with self.assertRaisesRegex(ValueError, "密码校验失败"):
            QQ阅读.解包出版书Zip条目(archive, b"wrong-password")

    def test_二进制乱码不能被选为出版书正文(self):
        with self.assertRaisesRegex(ValueError, "正文校验失败"):
            QQ阅读.选择出版书正文条目([("OPS/chapter.xhtml", b"\x00\x01\x02\x03" * 16)])

    async def test_出版书资源始终使用_app_签名请求头(self):
        captured: dict[str, object] = {}

        async def fake_http_get_bytes(session, url, headers, timeout=60):
            captured["headers"] = dict(headers)
            return b"resource", 200

        with patch.object(QQ阅读, "构建App请求头", return_value={"User-Agent": "app", "uid": "app-id"}) as app_headers:
            with patch.object(QQ阅读, "http_get_bytes", side_effect=fake_http_get_bytes):
                result = await QQ阅读.请求出版书章节包(
                    object(),
                    "book-id",
                    "1,2",
                    {"ywguid": "browser-id", "ywkey": "browser-key", "Cookie": "ywguid=browser-id; ywkey=browser-key;"},
                )

        self.assertEqual(result, b"resource")
        app_headers.assert_called_once()
        headers = captured["headers"]
        self.assertEqual(headers["uid"], "app-id")
        self.assertNotIn("Cookie", headers)
        self.assertEqual(headers["text_type"], "1")

    async def test_批量正文忽略浏览器登录态并固定使用_app_签名(self):
        captured: dict[str, object] = {}

        async def fake_http_get_bytes(session, url, headers, timeout=60):
            captured["url"] = url
            captured["headers"] = dict(headers)
            return b"chapter-package", 200

        browser_login = {
            "ywguid": "browser-id",
            "ywkey": "browser-key",
            "Cookie": "ywguid=browser-id; ywkey=browser-key;",
            "fuid": "browser-fuid",
        }
        app_headers = {"User-Agent": "app", "uid": "app-id"}
        with patch.object(QQ阅读, "构建App请求头", return_value=app_headers) as build_headers:
            with patch.object(QQ阅读, "http_get_bytes", side_effect=fake_http_get_bytes):
                result = await QQ阅读.请求批量包(
                    object(),
                    "book-id",
                    "1-31",
                    登录态=browser_login,
                )

        self.assertEqual(result, b"chapter-package")
        build_headers.assert_called_once()
        headers = captured["headers"]
        self.assertEqual(headers, app_headers)
        self.assertNotIn("Cookie", headers)
        query = parse_qs(urlparse(str(captured["url"])).query)
        self.assertEqual(query["type"], ["2"])
        self.assertEqual(query["scids"], ["1-31"])
        self.assertEqual(query["fuid"], [QQ阅读.默认App请求身份["fuid"]])
        self.assertNotIn("text_type", query)

    async def test_目录包使用_app_签名请求头(self):
        captured: dict[str, object] = {}

        async def fake_http_get_bytes(session, url, headers, timeout=60):
            captured["headers"] = dict(headers)
            return b"catalog-package", 200

        app_headers = {"User-Agent": "app", "uid": "app-id"}
        with patch.object(QQ阅读, "构建App请求头", return_value=app_headers) as build_headers:
            with patch.object(QQ阅读, "http_get_bytes", side_effect=fake_http_get_bytes):
                result = await QQ阅读.请求目录包(object(), "book-id")

        self.assertEqual(result, b"catalog-package")
        build_headers.assert_called_once()
        self.assertEqual(captured["headers"], app_headers)

    async def test_书籍详情忽略浏览器_cookie_并使用_app_签名(self):
        captured: dict[str, object] = {}

        async def fake_http_get_json(session, url, headers, timeout=30):
            captured["headers"] = dict(headers)
            return {"title": "book"}

        browser_login = {
            "ywguid": "browser-id",
            "ywkey": "browser-key",
            "Cookie": "ywguid=browser-id; ywkey=browser-key;",
        }
        app_headers = {"User-Agent": "app", "uid": "app-id"}
        with patch.object(QQ阅读, "构建App请求头", return_value=app_headers) as build_headers:
            with patch.object(QQ阅读, "http_get_json", side_effect=fake_http_get_json):
                result = await QQ阅读.请求书籍信息(object(), "book-id", browser_login)

        self.assertEqual(result, {"title": "book"})
        build_headers.assert_called_once()
        self.assertEqual(captured["headers"], app_headers)
        self.assertNotIn("Cookie", captured["headers"])

    async def test_动态密钥池固定使用_app_fuid(self):
        captured: dict[str, object] = {}

        async def fake_http_get_json(session, url, headers, timeout=30):
            captured["url"] = url
            captured["headers"] = dict(headers)
            return {"pool": "cG9vbA=="}

        QQ阅读.内存密钥池缓存.clear()
        with patch.object(QQ阅读, "http_get_json", side_effect=fake_http_get_json):
            with patch.object(QQ阅读, "decrypt_keypool", return_value=["token"]) as decrypt_pool:
                result = await QQ阅读.请求动态密钥池(object(), {"fuid": "browser-fuid"})

        self.assertEqual(result, "cG9vbA==")
        query = parse_qs(urlparse(str(captured["url"])).query)
        self.assertEqual(query["fuid"], [QQ阅读.默认App请求身份["fuid"]])
        self.assertNotIn("Cookie", captured["headers"])
        self.assertEqual(decrypt_pool.call_args.args[1], QQ阅读.master_key(QQ阅读.默认App请求身份["fuid"]))

    def test_浏览器登录态不能覆盖_app_加密身份(self):
        下载态 = QQ阅读.组装本地下载态(
            {
                "ywguid": "browser-id",
                "ywkey": "browser-key",
                "fuid": "browser-fuid",
            }
        )

        self.assertEqual(下载态["fuid"], QQ阅读.默认App请求身份["fuid"])

    def test_章节解密始终使用_app_加密身份(self):
        with patch.object(QQ阅读, "解密章节密文", return_value=(b"chapter", "ok")) as decrypt:
            text, note = QQ阅读.解密章节(
                b"cipher",
                "book-id",
                "chapter-id",
                {"fuid": "browser-fuid", "keypool_b64": "a2V5cG9vbA=="},
            )

        self.assertEqual((text, note), ("chapter", "ok"))
        self.assertEqual(decrypt.call_args.kwargs["fuid"], QQ阅读.默认App请求身份["fuid"])

    async def test_五百章业务批次按三十一章_app_窗口请求(self):
        requests: list[str] = []
        目录 = [
            {"cid": str(index), "id": str(index), "index": index, "title": f"第{index}章"}
            for index in range(1, 501)
        ]

        async def fake_request(session, bid, scids, **kwargs):
            requests.append(scids)
            return scids.encode("ascii")

        def fake_parse(blob):
            start_text, end_text = blob.decode("ascii").split("-", 1)
            return [
                QQ阅读.Tar成员(f"book-id_{index}_s", len(b"chapter"), b"chapter")
                for index in range(int(start_text), int(end_text) + 1)
            ]

        with patch.object(QQ阅读, "请求批量包", side_effect=fake_request):
            with patch.object(QQ阅读, "解析tar", side_effect=fake_parse):
                result = await QQ阅读.下载全书批量(object(), "book-id", 目录, {})

        expected = [
            f"{start}-{min(start + QQ阅读.App章节窗口上限 - 1, 500)}"
            for start in range(1, 501, QQ阅读.App章节窗口上限)
        ]
        self.assertEqual(requests, expected)
        self.assertEqual(len(result.章节), 500)
        self.assertTrue(all(chapter["success"] for chapter in result.章节))

    async def test_多业务批次的_app_请求并发不超过四(self):
        active = 0
        peak = 0
        目录 = [
            {"cid": str(index), "id": str(index), "index": index, "title": f"第{index}章"}
            for index in range(1, 2501)
        ]

        async def fake_request(session, bid, scids, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.001)
            active -= 1
            return scids.encode("ascii")

        def fake_parse(blob):
            start_text, end_text = blob.decode("ascii").split("-", 1)
            return [
                QQ阅读.Tar成员(f"book-id_{index}_s", len(b"chapter"), b"chapter")
                for index in range(int(start_text), int(end_text) + 1)
            ]

        with patch.object(QQ阅读, "请求批量包", side_effect=fake_request):
            with patch.object(QQ阅读, "解析tar", side_effect=fake_parse):
                result = await QQ阅读.下载全书批量(object(), "book-id", 目录, {})

        self.assertEqual(peak, QQ阅读.批量并发上限)
        self.assertEqual(len(result.章节), 2500)
        self.assertTrue(all(chapter["success"] for chapter in result.章节))


if __name__ == "__main__":
    unittest.main()
