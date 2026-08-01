from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock


ROOT = Path(__file__).resolve().parents[1]
UC_PATH = ROOT / "功能文件" / "管理功能" / "网盘功能" / "UC网盘.py"


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


def _load_uc_module():
    astrbot = _package("astrbot")
    astrbot_api = types.ModuleType("astrbot.api")
    astrbot_api.logger = _Logger()
    astrbot.api = astrbot_api
    sys.modules["astrbot.api"] = astrbot_api

    spec = importlib.util.spec_from_file_location("uc_completion_link_test_module", UC_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


UC网盘 = _load_uc_module()


class UC小说完成链接测试(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _package("功能文件")
        _package("功能文件.管理功能")
        _package("功能文件.管理功能.基础功能")

    def _安装QQ官方发送桩(self, *发送结果: bool) -> AsyncMock:
        权限工具 = types.ModuleType("功能文件.管理功能.基础功能.权限工具")
        权限工具.是QQ官方机器人 = lambda event: True
        sys.modules[权限工具.__name__] = 权限工具

        发送函数 = AsyncMock(side_effect=发送结果)
        帮助功能 = types.ModuleType("功能文件.管理功能.基础功能.帮助功能")
        帮助功能.发送Markdown键盘消息 = 发送函数
        sys.modules[帮助功能.__name__] = 帮助功能
        return 发送函数

    def test_文字链接只接受_http_并转义_markdown_url(self):
        self.assertEqual(UC网盘.构造小说下载完成文字链接("javascript:alert(1)"), "")
        self.assertEqual(
            UC网盘.构造小说下载完成文字链接("https://example.com/a b_(1)"),
            "[点击此文字打开](https://example.com/a%20b_%281%29)",
        )

    async def test_QQ官方按钮后紧跟纯文字链接(self):
        发送函数 = self._安装QQ官方发送桩(True, True)
        链接 = "https://example.com/share?id=42"

        结果 = await UC网盘.发送小说下载完成链接(object(), "测试书", "测试作者", 链接)

        self.assertTrue(结果["sent"])
        self.assertEqual(发送函数.await_count, 2)
        首条参数 = 发送函数.await_args_list[0].args
        self.assertIn("宝宝你的", 首条参数[1])
        self.assertEqual(首条参数[2]["rows"][0]["buttons"][0]["action"]["data"], 链接)
        第二条参数 = 发送函数.await_args_list[1].args
        self.assertEqual(第二条参数[1], f"[点击此文字打开]({链接})")
        self.assertIsNone(第二条参数[2])

    async def test_备用文字链接失败不误报已发送按钮(self):
        发送函数 = self._安装QQ官方发送桩(True, False)

        结果 = await UC网盘.发送小说下载完成链接(
            object(),
            "测试书",
            "测试作者",
            "https://example.com/share",
        )

        self.assertTrue(结果["sent"])
        self.assertEqual(发送函数.await_count, 2)


if __name__ == "__main__":
    unittest.main()
