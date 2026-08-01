from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


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
    小说功能.下载缓存清理 = types.SimpleNamespace(
        标记下载缓存正在使用=lambda *args, **kwargs: None,
        解除下载缓存占用=lambda *args, **kwargs: None,
    )

    spec = importlib.util.spec_from_file_location("qq_reader_reference_test_module", QQ_READER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


QQ阅读 = _load_qq_reader_module()


def _catalog_tar(book_id: str, text: str) -> bytes:
    payload = text.encode("utf-8")
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        info = tarfile.TarInfo(f"{book_id}_ALL_s")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


class QQ阅读参考适配测试(unittest.IsolatedAsyncioTestCase):
    def test_旧登录和旧下载实现已移除(self):
        self.assertFalse(hasattr(QQ阅读, "处理QQ阅读登录指令"))
        self.assertFalse(hasattr(QQ阅读, "解析QQ阅读Cookie"))
        self.assertFalse(hasattr(QQ阅读, "下载全书批量"))

    def test_使用参考项目固定身份且不落地密钥池(self):
        self.assertEqual(
            QQ阅读.CONFIG,
            {
                "loginType": "50",
                "c_platform": "android",
                "c_version": "qqreader_8.3.3.0888_android",
                "channel": "10005136",
                "qrsn": "0022ece0af3ed4d0052148e33e8bce20ab31a706cf9af04b",
                "usid": "ywIWoPGBmOeI",
                "uid": "855131499808",
                "fuid": "89306811035542cd868d49def7d3857d",
            },
        )
        self.assertTrue(hasattr(QQ阅读, "Fetcher"))
        self.assertFalse(hasattr(QQ阅读, "KEYPOOL_CACHE"))

    def test_识别分享链接中的书籍编号(self):
        source = "https://ih5.reader.qq.com/h5/share/bookShare?site=1&bid=304890"

        self.assertEqual(QQ阅读.解析书籍编号(source), "304890")
        self.assertEqual(QQ阅读.提取QQ阅读链接(f"分享：{source}"), source)

    def test_目录包解析为有序章节(self):
        package = _catalog_tar("304890", "1001,第一章\n1002,第二章\n")

        catalog = QQ阅读.解析参考目录包(package, "304890")

        self.assertEqual(
            catalog,
            [
                {"cid": "1001", "index": 1, "title": "第一章"},
                {"cid": "1002", "index": 2, "title": "第二章"},
            ],
        )

    def test_出版书目录同时识别_cteb_和_epub_资源(self):
        catalog = QQ阅读.解析参考出版书目录(
            [
                {
                    "chapter_id": "1",
                    "chapter_title": "第一章",
                    "ctebchaptercosurl": "https://TARGET/1.eqct",
                },
                {
                    "chapter_id": "2",
                    "chapter_title": "第二章",
                    "epubResourceUrl": "https://TARGET/2-resource.eqct",
                    "epubPureUrl": "https://TARGET/2-pure.eqct",
                },
            ]
        )

        self.assertEqual(
            catalog,
            [
                {
                    "cid": "1",
                    "index": 1,
                    "title": "第一章",
                    "resource_url": "https://TARGET/1.eqct",
                    "published": True,
                },
                {
                    "cid": "2",
                    "index": 2,
                    "title": "第二章",
                    "resource_url": "https://TARGET/2-pure.eqct",
                    "published": True,
                },
            ],
        )

    def test_txt格式与其他小说一致并使用_crlf(self):
        details = {
            "title": "测试书",
            "author": "测试作者",
            "status": "完结",
            "words_num": "12345",
            "intro": "测试简介",
        }
        catalog = [
            {"cid": "1", "index": 1, "title": "第一章"},
            {"cid": "2", "index": 2, "title": "第二章"},
        ]
        chapters = [
            {**catalog[0], "content": "正文一\n第二段"},
            {**catalog[1], "content": "正文二"},
        ]

        filename, content = QQ阅读.生成小说文件内容("42", details, catalog, chapters)
        text = content.decode("utf-8")

        self.assertEqual(filename, "[完结]书名：测试书 作者：测试作者.txt")
        self.assertIn("名称：测试书\r\n作者：测试作者", text)
        self.assertIn("第一章\r\n\r\n正文一\r\n第二段", text)
        self.assertIn("第二章\r\n\r\n正文二", text)
        self.assertNotIn("\n", text.replace("\r\n", ""))

    async def test_整本正文只调用参考_fetcher_范围下载(self):
        catalog = [
            {"cid": "1", "index": 1, "title": "第一章"},
            {"cid": "2", "index": 2, "title": "第二章"},
        ]
        close = Mock()
        fetcher = types.SimpleNamespace(
            get_chapter=lambda book_id, start, end: ["正文一", "正文二"],
            _session=types.SimpleNamespace(close=close),
        )

        with patch.object(QQ阅读, "初始化参考核心") as initialize:
            with patch.object(QQ阅读, "Fetcher", return_value=fetcher) as fetcher_class:
                chapters = await QQ阅读.下载参考正文("42", catalog)

        initialize.assert_called_once()
        fetcher_class.assert_called_once()
        self.assertEqual([item["content"] for item in chapters], ["正文一", "正文二"])
        close.assert_called_once()

    async def test_参考_fetcher_缺章时停止合成(self):
        catalog = [
            {"cid": "1", "index": 1, "title": "第一章"},
            {"cid": "2", "index": 2, "title": "第二章"},
        ]
        close = Mock()
        fetcher = types.SimpleNamespace(
            get_chapter=lambda book_id, start, end: ["正文一"],
            _session=types.SimpleNamespace(close=close),
        )

        with patch.object(QQ阅读, "初始化参考核心"):
            with patch.object(QQ阅读, "Fetcher", return_value=fetcher):
                with self.assertRaisesRegex(RuntimeError, "章节不完整"):
                    await QQ阅读.下载参考正文("42", catalog)

        close.assert_called_once()

    async def test_参考_fetcher_瞬时缺章时整段重试(self):
        catalog = [
            {"cid": "1", "index": 1, "title": "第一章"},
            {"cid": "2", "index": 2, "title": "第二章"},
        ]
        responses = iter([["正文一", "章节解密失败"], ["正文一", "正文二"]])
        close = Mock()
        fetcher = types.SimpleNamespace(
            get_chapter=lambda *args: next(responses),
            _session=types.SimpleNamespace(close=close),
        )

        with patch.object(QQ阅读, "初始化参考核心"):
            with patch.object(QQ阅读, "Fetcher", return_value=fetcher):
                with patch.object(QQ阅读.asyncio, "sleep", AsyncMock()):
                    chapters = await QQ阅读.下载参考正文("42", catalog)

        self.assertEqual([item["content"] for item in chapters], ["正文一", "正文二"])
        close.assert_called_once()

    async def test_下载流使用参考正文并交给统一网盘发送(self):
        details = {
            "title": "测试书",
            "author": "测试作者",
            "status": "完结",
            "words_num": "12345",
            "intro": "",
        }
        catalog = [{"cid": "1", "index": 1, "title": "第一章"}]
        chapters = [{**catalog[0], "content": "正文一"}]
        send_result = {
            "sent": True,
            "fallback_text": "",
            "source_cache_path": "TARGET.txt",
            "error": "",
        }

        with patch.object(QQ阅读, "获取参考书籍详情", AsyncMock(return_value=details)):
            with patch.object(QQ阅读, "获取参考书籍目录", AsyncMock(return_value=catalog)):
                with patch.object(QQ阅读, "下载参考正文", AsyncMock(return_value=chapters)):
                    with patch.object(
                        QQ阅读,
                        "准备发送文本文件",
                        AsyncMock(return_value=send_result),
                    ) as sender:
                        with patch.object(QQ阅读, "启动百度后台上传并清理源文件") as backup:
                            output = [
                                item
                                async for item in QQ阅读.生成下载回复流(
                                    object(),
                                    "https://ih5.reader.qq.com/h5/share/bookShare?bid=42",
                                    {},
                                )
                            ]

        self.assertEqual(len(output), 1)
        self.assertIn("书名：测试书", output[0])
        self.assertIn("正在下载中请稍等.....", output[0])
        sender.assert_awaited_once()
        self.assertIn(b"\r\n", sender.await_args.args[2])
        backup.assert_called_once_with({}, "TARGET.txt", "[完结]书名：测试书 作者：测试作者.txt")

    async def test_site4_下载流改走参考出版书资源(self):
        details = {
            "title": "出版测试书",
            "author": "测试作者",
            "status": "完结",
            "words_num": "1000",
            "chapters": 1,
            "intro": "",
        }
        catalog = [
            {
                "cid": "1",
                "index": 1,
                "title": "第一章",
                "resource_url": "https://TARGET/1.eqct",
                "published": True,
            }
        ]
        chapters = [{**catalog[0], "content": "出版正文"}]
        send_result = {
            "sent": True,
            "fallback_text": "",
            "source_cache_path": "TARGET.txt",
            "error": "",
        }

        with patch.object(QQ阅读, "获取参考书籍详情", AsyncMock(return_value=details)):
            with patch.object(QQ阅读, "获取参考出版书目录", AsyncMock(return_value=catalog)) as get_catalog:
                with patch.object(QQ阅读, "下载参考出版书正文", AsyncMock(return_value=chapters)) as download:
                    with patch.object(QQ阅读, "获取参考书籍目录", AsyncMock()) as regular_catalog:
                        with patch.object(QQ阅读, "下载参考正文", AsyncMock()) as regular_download:
                            with patch.object(
                                QQ阅读,
                                "准备发送文本文件",
                                AsyncMock(return_value=send_result),
                            ):
                                with patch.object(QQ阅读, "启动百度后台上传并清理源文件"):
                                    output = [
                                        item
                                        async for item in QQ阅读.生成下载回复流(
                                            object(),
                                            "https://ih5.reader.qq.com/h5/share/bookShare?bid=42&site=4",
                                            {},
                                        )
                                    ]

        self.assertEqual(len(output), 1)
        get_catalog.assert_awaited_once_with("42", 1)
        download.assert_awaited_once_with("42", catalog)
        regular_catalog.assert_not_awaited()
        regular_download.assert_not_awaited()

    def test_非QQ阅读消息不创建下载流(self):
        self.assertIsNone(QQ阅读.获取QQ阅读回复流(object(), "普通消息", {}))
        self.assertIsNotNone(
            QQ阅读.获取QQ阅读回复流(
                object(),
                "https://book.qq.com/book-detail/304890",
                {},
            )
        )

    def test_参考_fetcher_单窗口瞬时失败会重试(self):
        fetcher = object.__new__(QQ阅读.Fetcher)
        responses = iter([["章节解密失败"], ["正文"]])

        with patch.object(fetcher, "_get_chapter", side_effect=lambda *args: next(responses)) as request:
            with patch.object(QQ阅读.time, "sleep"):
                result = fetcher.get_chapter("42", "1", "1")

        self.assertEqual(result, ["正文"])
        self.assertEqual(request.call_count, 2)

    def test_主分发和依赖不再保留旧登录入口(self):
        main_text = (ROOT / "main.py").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

        self.assertNotIn("处理QQ阅读登录指令", main_text)
        self.assertIn("requests", requirements)


if __name__ == "__main__":
    unittest.main()
