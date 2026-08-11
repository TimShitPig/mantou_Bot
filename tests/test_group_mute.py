import asyncio
import sys
import types
import unittest
from unittest.mock import patch
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


class 群禁言测试(unittest.TestCase):
    def test_解析QQ官方单用户禁言(self):
        event = types.SimpleNamespace(
            get_platform_name=lambda: "qq_official",
            message_obj={
                "message": [
                    {"type": "text", "data": {"text": "禁言 10分钟"}},
                    {"type": "at", "data": {"member_openid": "MemberOpenID_01"}},
                ]
            },
        )

        参数 = 群管功能.解析单用户禁言参数(event, "禁言 10分钟")

        self.assertEqual(参数["targets"], ["MemberOpenID_01"])
        self.assertEqual(参数["seconds"], 600)
        self.assertEqual(参数["operation"], "add")

    def test_解析解除禁言(self):
        event = types.SimpleNamespace(
            message_obj={
                "message": [
                    {"type": "text", "data": {"text": "解除禁言"}},
                    {"type": "at", "data": {"member_openid": "MemberOpenID_01"}},
                ]
            }
        )

        参数 = 群管功能.解析单用户禁言参数(event, "解除禁言")

        self.assertEqual(参数["targets"], ["MemberOpenID_01"])
        self.assertEqual(参数["operation"], "del")
        self.assertIsNone(参数["seconds"])

    def test_解析禁和禁言默认七天(self):
        for 命令 in ("禁", "禁言"):
            event = types.SimpleNamespace(
                message_obj={
                    "message": [
                        {"type": "text", "data": {"text": 命令}},
                        {"type": "at", "data": {"member_openid": "MemberOpenID_01"}},
                    ]
                }
            )
            参数 = 群管功能.解析单用户禁言参数(event, 命令)
            self.assertEqual(参数["targets"], ["MemberOpenID_01"])
            self.assertEqual(参数["seconds"], 7 * 86400)
            self.assertEqual(参数["operation"], "add")

    def test_解析禁无单位数字按天计算(self):
        event = types.SimpleNamespace(
            message_obj={
                "message": [
                    {"type": "text", "data": {"text": "禁 1"}},
                    {"type": "at", "data": {"member_openid": "MemberOpenID_01"}},
                ]
            }
        )
        参数 = 群管功能.解析单用户禁言参数(event, "禁 1")
        self.assertEqual(参数["seconds"], 86400)

    def test_解析禁后直接跟数字按天计算(self):
        event = types.SimpleNamespace(
            message_obj={
                "message": [
                    {"type": "text", "data": {"text": "禁30"}},
                    {"type": "at", "data": {"member_openid": "MemberOpenID_01"}},
                ]
            }
        )
        参数 = 群管功能.解析单用户禁言参数(event, "禁30")
        self.assertEqual(参数["targets"], ["MemberOpenID_01"])
        self.assertEqual(参数["seconds"], 30 * 86400)
        self.assertEqual(参数["operation"], "add")

    def test_解析解和解禁都为解除(self):
        for 命令 in ("解", "解禁"):
            event = types.SimpleNamespace(
                message_obj={
                    "message": [
                        {"type": "text", "data": {"text": 命令}},
                        {"type": "at", "data": {"member_openid": "MemberOpenID_01"}},
                    ]
                }
            )
            参数 = 群管功能.解析单用户禁言参数(event, 命令)
            self.assertEqual(参数["targets"], ["MemberOpenID_01"])
            self.assertEqual(参数["operation"], "del")
            self.assertIsNone(参数["seconds"])

    def test_官方禁言请求体(self):
        body = 群管功能.构造QQ官方成员禁言请求体(
            ["MemberOpenID_01"],
            "add",
            "2026-08-11T12:00:00+08:00",
        )

        self.assertEqual(
            body,
            {
                "members": [
                    {
                        "op": "add",
                        "member_openid": "MemberOpenID_01",
                        "mute_expire_at": "2026-08-11T12:00:00+08:00",
                    }
                ]
            },
        )

    def test_OneBot单用户禁言调用set_group_ban(self):
        calls = []

        async def set_group_ban(**kwargs):
            calls.append(kwargs)

        bot = types.SimpleNamespace(set_group_ban=set_group_ban)

        asyncio.run(群管功能.使用_set_group_ban禁言(bot, "123456789", "987654321", 600))

        self.assertEqual(
            calls,
            [{"group_id": 123456789, "user_id": 987654321, "duration": 600}],
        )

    def test_QQ官方单用户禁言走restrict_chat_setting(self):
        requests = []

        class Route:
            def __init__(self, method, path, **params):
                self.method = method
                self.path = path
                self.params = params

        class HttpClient:
            async def request(self, route, **kwargs):
                requests.append((route, kwargs))
                return None

        botpy = types.ModuleType("botpy")
        botpy_http = types.ModuleType("botpy.http")
        botpy_http.Route = Route
        botpy.http = botpy_http
        bot = types.SimpleNamespace(api=types.SimpleNamespace(_http=HttpClient()))

        with patch.dict(sys.modules, {"botpy": botpy, "botpy.http": botpy_http}):
            asyncio.run(
                群管功能.使用_set_group_ban禁言(
                    bot,
                    "GroupOpenID_01",
                    "MemberOpenID_01",
                    600,
                )
            )

        self.assertEqual(len(requests), 1)
        route, kwargs = requests[0]
        self.assertEqual(route.method, "POST")
        self.assertEqual(route.path, "/v2/groups/{group_openid}/restrict_chat_setting")
        self.assertEqual(route.params, {"group_openid": "GroupOpenID_01"})
        self.assertEqual(kwargs["json"]["members"][0]["op"], "add")
        self.assertEqual(kwargs["json"]["members"][0]["member_openid"], "MemberOpenID_01")
        self.assertTrue(kwargs["json"]["members"][0]["mute_expire_at"].endswith("+08:00"))

    def test_全体禁言入口已移除(self):
        self.assertFalse(hasattr(群管功能, "禁言命令集合"))
        self.assertFalse(hasattr(群管功能, "使用_set_group_whole_ban禁言"))

    def test_禁言成功回复会提及被禁言成员(self):
        self.assertEqual(
            群管功能.构造成员禁言成功回复(
                types.SimpleNamespace(get_platform_name=lambda: "qq_official"),
                ["MemberOpenID_01"],
            ),
            "<@MemberOpenID_01> 你已经被禁言，请联系群主说明情况",
        )
        self.assertEqual(
            群管功能.构造成员禁言成功回复(
                types.SimpleNamespace(get_platform_name=lambda: "onebot"),
                ["987654321"],
            ),
            "[CQ:at,qq=987654321] 你已经被禁言，请联系群主说明情况",
        )

    def test_广告撤回禁言时长按次数递增并封顶(self):
        self.assertEqual(
            [群管功能.计算广告撤回禁言秒数(次数) for 次数 in range(1, 7)],
            [180, 600, 1800, 86400, 30 * 86400, 30 * 86400],
        )

    def test_撤回广告提醒提及QQ官方发送者(self):
        event = types.SimpleNamespace(
            get_platform_name=lambda: "qq_official",
            message_obj={"author": {"member_openid": "MemberOpenID_01"}},
        )
        self.assertEqual(
            群管功能.获取撤回发送者标识(event),
            "MemberOpenID_01",
        )
        self.assertEqual(
            群管功能.构造撤回广告提醒(event),
            "<@MemberOpenID_01> 请勿再发送此类消息",
        )

    def test_撤回广告自动禁言调用OneBot时长(self):
        calls = []

        async def set_group_ban(**kwargs):
            calls.append(kwargs)

        event = types.SimpleNamespace(
            message_obj={
                "group_id": "123456789",
                "sender": {"user_id": "987654321"},
            },
            bot=types.SimpleNamespace(set_group_ban=set_group_ban),
        )
        self.assertTrue(asyncio.run(群管功能.尝试广告撤回禁言(event, 180, 1)))
        self.assertEqual(
            calls,
            [{"group_id": 123456789, "user_id": 987654321, "duration": 180}],
        )


if __name__ == "__main__":
    unittest.main()
