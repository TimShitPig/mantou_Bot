import sys
import types
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
api = types.ModuleType("astrbot.api")
api.logger = types.SimpleNamespace(
    debug=lambda *args, **kwargs: None,
    info=lambda *args, **kwargs: None,
    warning=lambda *args, **kwargs: None,
)
astrbot = types.ModuleType("astrbot")
astrbot.api = api
sys.modules.setdefault("astrbot", astrbot)
sys.modules.setdefault("astrbot.api", api)

from 功能文件.管理功能.小说功能.小说 import QQ阅读


class QQ阅读章节请求测试(unittest.TestCase):
    def test_批次使用目录真实章节id而不是过滤后序号(self):
        catalog = [
            {"cid": "1"},
            {"cid": "17"},
            {"cid": "717"},
        ]

        self.assertEqual(
            QQ阅读.获取QQ阅读正文章节ID列表(catalog, 1, 3),
            ["1", "17", "717"],
        )

    def test_非连续章节id使用逗号请求(self):
        self.assertEqual(
            QQ阅读.构造QQ阅读正文章节参数(["1", "17", "717"]),
            "1,17,717",
        )


if __name__ == "__main__":
    unittest.main()
