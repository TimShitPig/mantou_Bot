import importlib.util
import sys
import types
import unittest
from pathlib import Path


def 加载QQ阅读模块():
    日志 = types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)
    astrbot = types.ModuleType("astrbot")
    astrbot_api = types.ModuleType("astrbot.api")
    astrbot_api.logger = 日志
    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = astrbot_api

    权限工具 = types.ModuleType("功能文件.管理功能.基础功能.权限工具")
    权限工具.是群文件清理管理员 = lambda *args, **kwargs: True
    sys.modules[权限工具.__name__] = 权限工具
    运行状态 = types.ModuleType("功能文件.管理功能.基础功能.运行状态数据库")
    运行状态.读取运行状态值 = lambda *args, **kwargs: ""
    运行状态.写入运行状态值 = lambda *args, **kwargs: None
    sys.modules[运行状态.__name__] = 运行状态
    网盘功能 = types.ModuleType("功能文件.管理功能.网盘功能")
    网盘功能.UC网盘 = None
    网盘功能.百度网盘 = None
    sys.modules[网盘功能.__name__] = 网盘功能

    路径 = Path(__file__).resolve().parents[1] / "功能文件" / "管理功能" / "小说功能" / "QQ阅读.py"
    规格 = importlib.util.spec_from_file_location("测试QQ阅读模块", 路径)
    模块 = importlib.util.module_from_spec(规格)
    assert 规格 and 规格.loader
    sys.modules[规格.name] = 模块
    规格.loader.exec_module(模块)
    return 模块


class QQ阅读Cookie识别测试(unittest.TestCase):
    def test_直接发送有效登录Cookie会被识别(self):
        模块 = 加载QQ阅读模块()

        self.assertTrue(模块.是QQ阅读Cookie文本("ywguid=123456; ywkey=abcdef; qrsn=test;"))

    def test_普通聊天内容不会被识别为Cookie(self):
        模块 = 加载QQ阅读模块()

        self.assertFalse(模块.是QQ阅读Cookie文本("今天读 QQ 阅读了吗？"))

    def test_CookieEditor_JSON会被识别(self):
        模块 = 加载QQ阅读模块()
        Cookie = '[{"domain": ".reader.qq.com", "name": "ywguid", "value": "123"}, {"domain": ".reader.qq.com", "name": "ywkey", "value": "abc"}]'

        self.assertTrue(模块.是QQ阅读Cookie文本(Cookie))

    def test_Netscape_HttpOnly_Cookie会被识别(self):
        模块 = 加载QQ阅读模块()
        Cookie = (
            "#HttpOnly_.reader.qq.com\tTRUE\t/\tFALSE\t0\tywguid\t123\n"
            "#HttpOnly_.reader.qq.com\tTRUE\t/\tFALSE\t0\tywkey\tabc"
        )

        self.assertTrue(模块.是QQ阅读Cookie文本(Cookie))

    def test_直接发送Cookie会保存登录态(self):
        模块 = 加载QQ阅读模块()
        已保存 = {}
        模块.是群文件清理管理员 = lambda *args, **kwargs: True
        模块.写入QQ阅读登录态 = lambda 配置, 登录态: 已保存.update(登录态)

        回复 = __import__("asyncio").run(
            模块.处理QQ阅读登录指令(object(), "ywguid=123456; ywkey=abcdef;", object())
        )

        self.assertEqual("QQ阅读Cookie已保存", 回复)
        self.assertEqual("123456", 已保存["ywguid"])
        self.assertEqual("abcdef", 已保存["ywkey"])


if __name__ == "__main__":
    unittest.main()
