from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


群管功能 = importlib.import_module("功能文件.管理功能.群聊功能.群管功能")


class QQ官方机器人权限测试(unittest.TestCase):
    def test_解析官方机器人群角色(self) -> None:
        self.assertEqual(
            群管功能.提取QQ官方机器人群角色({"member_role": "admin"}),
            "admin",
        )
        self.assertEqual(
            群管功能.提取QQ官方机器人群角色({"data": {"member_role": "member"}}),
            "member",
        )

    def test_请求官方机器人状态接口(self) -> None:
        路由调用 = []

        class 假路由:
            def __init__(self, method, path, **kwargs):
                self.method = method
                self.path = path
                self.kwargs = kwargs

        class 假HTTP:
            async def request(self, route):
                路由调用.append(route)
                return {"member_role": "admin"}

        假BotPy = types.ModuleType("botpy")
        假BotPyHTTP = types.ModuleType("botpy.http")
        假BotPyHTTP.Route = 假路由
        假BotPy.http = 假BotPyHTTP
        bot = SimpleNamespace(api=SimpleNamespace(_http=假HTTP()))

        with patch.dict(
            sys.modules,
            {"botpy": 假BotPy, "botpy.http": 假BotPyHTTP},
        ):
            角色 = asyncio.run(
                群管功能.获取QQ官方机器人群角色(bot, "GROUP_OPENID")
            )

        self.assertEqual(角色, "admin")
        self.assertEqual(路由调用[0].method, "GET")
        self.assertEqual(路由调用[0].path, "/v2/groups/{group_openid}/bot_state")
        self.assertEqual(路由调用[0].kwargs["group_openid"], "GROUP_OPENID")

    def test_权限查询异常按无权限处理(self) -> None:
        with patch.object(
            群管功能,
            "获取QQ官方机器人群角色",
            new=AsyncMock(side_effect=RuntimeError("api error")),
        ):
            结果 = asyncio.run(
                群管功能.QQ官方机器人具备群管权限(
                    object(),
                    "ERROR_GROUP",
                )
            )

        self.assertFalse(结果)

    def test_官方机器人不是管理员时禁言静默跳过(self) -> None:
        event = SimpleNamespace(bot=object())
        with patch.object(群管功能, "解析单用户禁言参数", return_value={
            "targets": ["member-openid"],
            "operation": "add",
            "seconds": 86400,
        }), patch.object(群管功能, "是群文件清理管理员", return_value=True), patch.object(
            群管功能, "获取群号", return_value="GROUP_OPENID"
        ), patch.object(
            群管功能,
            "QQ官方机器人具备群管权限",
            new=AsyncMock(return_value=False),
        ), patch.object(
            群管功能,
            "使用_set_group_ban禁言",
            new=AsyncMock(),
        ) as 禁言:
            回复 = asyncio.run(群管功能.处理群禁言(event, "禁 @成员", None))

        self.assertIsNone(回复)
        禁言.assert_not_awaited()

    def test_官方机器人不是管理员时撤回静默跳过(self) -> None:
        event = SimpleNamespace(bot=object())
        with patch.object(群管功能, "是否需要撤回消息", return_value=True), patch.object(
            群管功能,
            "是否发送者为QQ群主或管理员",
            new=AsyncMock(return_value=False),
        ), patch.object(
            群管功能, "获取群号", return_value="GROUP_OPENID"
        ), patch.object(
            群管功能,
            "QQ官方机器人具备群管权限",
            new=AsyncMock(return_value=False),
        ), patch.object(
            群管功能,
            "尝试撤回当前消息",
            new=AsyncMock(return_value=True),
        ) as 撤回:
            结果 = asyncio.run(群管功能.处理数字撤回(event, None))

        self.assertFalse(结果)
        撤回.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
