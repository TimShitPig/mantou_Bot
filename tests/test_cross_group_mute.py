from __future__ import annotations

import asyncio
import importlib
import unittest
from unittest.mock import patch


群管功能 = importlib.import_module("功能文件.管理功能.群聊功能.群管功能")
群列表工具 = importlib.import_module("功能文件.管理功能.群聊功能.群列表工具")


class 跨群禁言测试(unittest.TestCase):
    def test_提取QQ官方群openid列表(self) -> None:
        self.assertEqual(
            群列表工具.提取群号列表(
                {"data": [{"group_openid": "group-a"}, {"group_openid": "group-b"}]}
            ),
            ["group-a", "group-b"],
        )

    def test_同步到其它群并跳过当前群(self) -> None:
        bot = object()
        禁言调用: list[tuple[str, str, int, str]] = []

        async def 获取群列表(_bot):
            return ["10001", "10002", "10003"]

        async def 检查成员(_bot, 群号, 用户):
            return 群号 != "10003"

        async def 执行禁言(_bot, 群号, 用户, 秒数, 操作):
            禁言调用.append((群号, 用户, 秒数, 操作))

        with patch.object(群管功能, "获取机器人所在群号列表", new=获取群列表), patch.object(
            群管功能, "检查群成员存在", new=检查成员
        ), patch.object(群管功能, "使用_set_group_ban禁言", new=执行禁言):
            成功数, 失败数 = asyncio.run(
                群管功能.同步成员禁言到其它群(
                    bot,
                    "10001",
                    "12345",
                    86400,
                    "add",
                )
            )

        self.assertEqual((成功数, 失败数), (1, 0))
        self.assertEqual(禁言调用, [("10002", "12345", 86400, "add")])

    def test_跨群解禁跳过当前群(self) -> None:
        bot = object()
        禁言调用: list[str] = []

        async def 获取群列表(_bot):
            return ["group-a", "group-b"]

        async def 执行禁言(_bot, 群号, 用户, 秒数, 操作):
            禁言调用.append(群号)

        with patch.object(
            群管功能,
            "获取机器人所在群号列表",
            new=获取群列表,
        ), patch.object(群管功能, "使用_set_group_ban禁言", new=执行禁言):
            成功数, 失败数 = asyncio.run(
                群管功能.同步成员禁言到其它群(
                    bot,
                    "group-a",
                    "member-1",
                    0,
                    "del",
                )
            )

        self.assertEqual((成功数, 失败数), (1, 0))
        self.assertEqual(禁言调用, ["group-b"])


if __name__ == "__main__":
    unittest.main()
