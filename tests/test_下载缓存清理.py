from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def 加载下载缓存清理模块():
    源文件 = (
        Path(__file__).resolve().parents[1]
        / "功能文件"
        / "管理功能"
        / "小说功能"
        / "功能"
        / "下载缓存清理.py"
    )
    规格 = importlib.util.spec_from_file_location("下载缓存清理测试模块", 源文件)
    assert 规格 is not None and 规格.loader is not None
    模块 = importlib.util.module_from_spec(规格)
    规格.loader.exec_module(模块)
    return 模块


class 下载缓存清理测试(unittest.TestCase):
    def setUp(self) -> None:
        self.模块 = 加载下载缓存清理模块()
        self.临时目录 = tempfile.TemporaryDirectory()
        self.缓存目录 = Path(self.临时目录.name)
        self.缓存文件 = self.缓存目录 / "下载中的小说.txt"
        self.缓存文件.write_text("正文", encoding="utf-8")

    def tearDown(self) -> None:
        self.临时目录.cleanup()

    def test_重载清理不删除正在上传的缓存文件(self) -> None:
        self.模块.标记下载缓存正在使用(self.缓存文件)

        已清理 = self.模块.清理残留下载缓存(self.缓存目录)

        self.assertEqual(已清理, 0)
        self.assertTrue(self.缓存文件.exists())

    def test_解除占用后重载清理删除残留文件(self) -> None:
        self.模块.标记下载缓存正在使用(self.缓存文件)
        self.模块.解除下载缓存占用(self.缓存文件)

        已清理 = self.模块.清理残留下载缓存(self.缓存目录)

        self.assertEqual(已清理, 1)
        self.assertFalse(self.缓存文件.exists())
