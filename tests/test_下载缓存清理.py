import importlib.util
import tempfile
import unittest
from pathlib import Path


def 加载下载缓存清理模块():
    路径 = Path(__file__).resolve().parents[1] / "功能文件" / "管理功能" / "小说功能" / "下载缓存清理.py"
    if not 路径.is_file():
        return None
    规格 = importlib.util.spec_from_file_location("测试下载缓存清理模块", 路径)
    模块 = importlib.util.module_from_spec(规格)
    assert 规格 and 规格.loader
    规格.loader.exec_module(模块)
    return 模块


class 下载缓存清理测试(unittest.TestCase):
    def test_清理残留小说文本并保留非小说文件(self):
        模块 = 加载下载缓存清理模块()
        with tempfile.TemporaryDirectory() as 临时目录:
            缓存目录 = Path(临时目录)
            小说 = 缓存目录 / "[完结]书名：测试 作者：测试.txt"
            非小说 = 缓存目录 / "保留.md"
            小说.write_text("正文", encoding="utf-8")
            非小说.write_text("说明", encoding="utf-8")

            已清理 = 模块.清理残留下载缓存(缓存目录) if 模块 else None

            self.assertEqual(1, 已清理)
            self.assertFalse(小说.exists())
            self.assertTrue(非小说.exists())

    def test_插件初始化会清理残留缓存(self):
        main源码 = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

        self.assertIn("小说缓存清理.清理残留下载缓存()", main源码)


if __name__ == "__main__":
    unittest.main()
