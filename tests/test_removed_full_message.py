from __future__ import annotations

from pathlib import Path
import unittest


仓库根目录 = Path(__file__).resolve().parents[1]


class 全量消息删除测试(unittest.TestCase):
    def test_主流程不再加载全量消息功能(self) -> None:
        主模块源码 = (仓库根目录 / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("全量消息功能", 主模块源码)

    def test_全量消息模块已删除(self) -> None:
        self.assertFalse(
            (仓库根目录 / "功能文件/管理功能/群聊功能/全量消息.py").exists()
        )


if __name__ == "__main__":
    unittest.main()
