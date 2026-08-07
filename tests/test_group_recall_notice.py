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


if __name__ == "__main__":
    unittest.main()
