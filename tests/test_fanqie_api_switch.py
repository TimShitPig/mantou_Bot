from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


class FakeUserActivation:
    def __init__(self):
        self.saved: list[tuple[str, str, str]] = []

    async def 读取运行状态(self, namespace: str, key: str) -> str:
        return ""

    async def 保存运行状态(self, namespace: str, key: str, value: str) -> None:
        self.saved.append((namespace, key, value))


class FakeEvent:
    def __init__(self, sender_id: str, text: str):
        self.sender_id = sender_id
        self.message_str = text
        self.group_id = "10001"
        self.is_admin_or_owner = False

    def get_sender_id(self) -> str:
        return self.sender_id


def load_fanqie_module(fake_user_activation: FakeUserActivation):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "功能文件" / "API功能" / "OIAPI" / "番茄小说.py"
    module_name = "fanqie_api_switch_test_module"

    fake_astrbot = types.ModuleType("astrbot")
    fake_astrbot_api = types.ModuleType("astrbot.api")
    fake_astrbot_api.logger = FakeLogger()
    sys.modules["astrbot"] = fake_astrbot
    sys.modules["astrbot.api"] = fake_astrbot_api

    fake_main = types.ModuleType("main")
    fake_main.析API番茄小说模块 = types.SimpleNamespace()
    fake_main.崩溃API番茄小说模块 = types.SimpleNamespace()
    fake_main.用户激活功能 = fake_user_activation
    fake_main.小说功能开关 = types.SimpleNamespace()
    fake_main.UC网盘功能 = types.SimpleNamespace()
    fake_main.百度网盘功能 = types.SimpleNamespace()
    fake_main.自建API番茄小说模块 = types.SimpleNamespace()
    sys.modules["main"] = fake_main

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载番茄小说模块")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FanqieApiSwitchTest(unittest.TestCase):
    def test_configured_cleanup_admin_can_switch_to_self_api(self):
        fake_user_activation = FakeUserActivation()
        module = load_fanqie_module(fake_user_activation)
        event = FakeEvent("123456", "自建api")
        config = {"basic_settings": {"group_file_cleanup_admin_qq": ["123456"]}}

        reply = asyncio.run(module.处理番茄小说API指令(event, "自建api", config))

        self.assertEqual(reply, "已切换到：自建API")
        self.assertEqual(fake_user_activation.saved, [("fq_api_choice", "api", "4")])

    def test_non_cleanup_admin_cannot_switch_to_self_api(self):
        fake_user_activation = FakeUserActivation()
        module = load_fanqie_module(fake_user_activation)
        event = FakeEvent("999999", "自建api")
        config = {"basic_settings": {"group_file_cleanup_admin_qq": ["123456"]}}

        reply = asyncio.run(module.处理番茄小说API指令(event, "自建api", config))

        self.assertIsNone(reply)
        self.assertEqual(fake_user_activation.saved, [])


if __name__ == "__main__":
    unittest.main()
