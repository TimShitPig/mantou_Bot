from __future__ import annotations

import asyncio
import importlib
import logging
import sys
import types
import unittest
from types import SimpleNamespace


def 安装测试依赖() -> None:
    astrbot模块 = types.ModuleType("astrbot")
    astrbot接口模块 = types.ModuleType("astrbot.api")
    astrbot接口模块.logger = logging.getLogger("全量消息测试")
    astrbot模块.api = astrbot接口模块
    sys.modules["astrbot"] = astrbot模块
    sys.modules["astrbot.api"] = astrbot接口模块

    class 测试路由:
        def __init__(self, 方法: str, 路径: str, **参数) -> None:
            self.method = 方法
            self.path = 路径.format(**参数)

    botpy模块 = types.ModuleType("botpy")
    botpyHTTP模块 = types.ModuleType("botpy.http")
    botpyHTTP模块.Route = 测试路由
    botpy模块.http = botpyHTTP模块
    sys.modules["botpy"] = botpy模块
    sys.modules["botpy.http"] = botpyHTTP模块


class 全量消息测试(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        安装测试依赖()
        sys.modules.pop("功能文件.管理功能.群聊功能.全量消息", None)
        cls.模块 = importlib.import_module("功能文件.管理功能.群聊功能.全量消息")

    def test_官方群状态将全部消息映射为已开启(self) -> None:
        状态 = self.模块.解析官方群机器人状态(
            {
                "recv_msg_setting": "all",
                "allow_proactive_msg": True,
                "member_openid": "member_openid_123",
            }
        )

        self.assertEqual(状态["全量消息"], "已开启")
        self.assertEqual(状态["主动发言"], "已开启")
        self.assertIn("群内全部消息：已开启", self.模块.格式化官方群机器人状态(状态))

    def test_MD提及使用成员OpenID格式(self) -> None:
        self.assertEqual(
            self.模块.生成QQ官方MD提及("member_openid_123"),
            "<@member_openid_123>",
        )

    async def test_通过官方群状态接口查询开关(self) -> None:
        class 测试HTTP:
            async def request(self, 路由):
                self.路由 = 路由
                return {
                    "recv_msg_setting": "only_mention",
                    "allow_proactive_msg": False,
                }

        HTTP = 测试HTTP()
        事件 = SimpleNamespace(bot=SimpleNamespace(api=SimpleNamespace(_http=HTTP)))

        状态 = await self.模块.查询官方群机器人状态(事件, "GROUP_OPENID")

        self.assertEqual(HTTP.路由.method, "GET")
        self.assertEqual(HTTP.路由.path, "/v2/groups/GROUP_OPENID/bot_state")
        self.assertEqual(状态["全量消息"], "未开启")
        self.assertEqual(状态["主动发言"], "未开启")
