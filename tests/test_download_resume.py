import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


from 功能文件.管理功能.小说功能.功能 import 下载缓存清理


class 下载缓存断点续传测试(unittest.TestCase):
    def test_重载不会删除已登记上传任务的缓存(self):
        with tempfile.TemporaryDirectory() as 临时目录:
            缓存目录 = Path(临时目录)
            缓存路径 = 缓存目录 / "测试书.txt"
            缓存路径.write_text("正文", encoding="utf-8")
            标记路径 = 下载缓存清理.标记下载缓存正在使用(缓存路径)
            标记路径.write_text(
                json.dumps({"pid": os.getpid() + 100000, "created_at": 1}),
                encoding="utf-8",
            )

            with patch.object(下载缓存清理, "下载缓存目录", 缓存目录):
                下载缓存清理.登记上传任务(缓存路径, "测试书.txt", "夸克网盘")
                清理数量 = 下载缓存清理.清理残留下载缓存()

            self.assertEqual(清理数量, 0)
            self.assertTrue(缓存路径.exists())
            self.assertTrue(下载缓存清理.上传任务待续传(缓存路径))

    def test_完成上传任务后才允许清理任务记录(self):
        with tempfile.TemporaryDirectory() as 临时目录:
            缓存目录 = Path(临时目录)
            缓存路径 = 缓存目录 / "测试书.txt"
            缓存路径.write_text("正文", encoding="utf-8")

            with patch.object(下载缓存清理, "下载缓存目录", 缓存目录):
                任务路径 = 下载缓存清理.登记上传任务(缓存路径, "测试书.txt", "夸克网盘")
                self.assertTrue(任务路径.exists())
                下载缓存清理.完成上传任务(缓存路径)
                self.assertFalse(任务路径.exists())
                self.assertFalse(下载缓存清理.上传任务待续传(缓存路径))

    def test_待续传任务阻止删除缓存文件(self):
        with tempfile.TemporaryDirectory() as 临时目录:
            缓存目录 = Path(临时目录)
            缓存路径 = 缓存目录 / "测试书.txt"
            缓存路径.write_text("正文", encoding="utf-8")

            with patch.object(下载缓存清理, "下载缓存目录", 缓存目录):
                下载缓存清理.登记上传任务(缓存路径, "测试书.txt", "夸克网盘")
                self.assertFalse(下载缓存清理.删除下载缓存文件(缓存路径))
                self.assertTrue(缓存路径.exists())


if __name__ == "__main__":
    unittest.main()
