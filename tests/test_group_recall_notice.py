import sys
import types
import unittest
import asyncio
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

from 功能文件.管理功能.群聊功能 import 群管功能


class 撤回通知提及测试(unittest.TestCase):
    def test_官方群使用发送者_member_openid(self):
        event = types.SimpleNamespace(
            get_platform_name=lambda: "qq_official",
            message_obj={
                "author": {
                    "member_openid": "MemberOpenID_01",
                    "username": "发送者",
                }
            },
        )

        self.assertEqual(
            群管功能.获取撤回发送者提及(event),
            "<@MemberOpenID_01>",
        )

    def test_onebot使用发送者QQ(self):
        event = types.SimpleNamespace(
            get_platform_name=lambda: "aiocqhttp",
            message_obj={"sender": {"user_id": "123456789"}},
        )

        self.assertEqual(
            群管功能.获取撤回发送者提及(event),
            "[CQ:at,qq=123456789]",
        )

    def test_同群并发撤回通知只发送一条(self):
        群管功能.撤回通知最近发送时间.clear()
        发送次数 = 0

        async def 场景():
            nonlocal 发送次数

            async def 发送(_结果):
                nonlocal 发送次数
                发送次数 += 1
                await asyncio.sleep(0)

            event = types.SimpleNamespace(
                get_group_id=lambda: "group-01",
                get_platform_name=lambda: "aiocqhttp",
                get_sender_id=lambda: "123456789",
                plain_result=lambda text: text,
                send=发送,
                message_obj={"sender": {"user_id": "123456789", "nickname": "发送者"}},
            )
            tasks = [
                asyncio.create_task(群管功能.发送撤回通知(event, None, "违规消息")),
                asyncio.create_task(群管功能.发送撤回通知(event, None, "违规消息")),
            ]
            await asyncio.gather(*tasks)

        asyncio.run(场景())
        self.assertEqual(发送次数, 1)


if __name__ == "__main__":
    unittest.main()
