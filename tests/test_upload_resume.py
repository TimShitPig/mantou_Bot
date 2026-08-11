import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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
event_module = types.ModuleType("astrbot.api.event")
event_module.MessageChain = object
sys.modules.setdefault("astrbot.api.event", event_module)
components_module = types.ModuleType("astrbot.api.message_components")
components_module.Image = object
components_module.Plain = object
sys.modules.setdefault("astrbot.api.message_components", components_module)


from 功能文件.管理功能.网盘功能 import 小说网盘
from 功能文件.管理功能.小说功能.功能 import 下载缓存清理


class _失败网盘:
    async def 上传小说并获取分享链接(self, _配置, _路径, _文件名):
        return {
            "enabled": True,
            "success": False,
            "share_url": "",
            "error": "临时网络错误",
        }


class _成功网盘:
    async def 上传小说并获取分享链接(self, _配置, _路径, _文件名):
        return {
            "enabled": True,
            "success": True,
            "share_url": "https://example.invalid/share",
            "error": "",
        }


class 网盘上传断点续传测试(unittest.IsolatedAsyncioTestCase):
    async def test_主网盘失败时保留可续传任务(self):
        with tempfile.TemporaryDirectory() as 临时目录:
            缓存路径 = Path(临时目录) / "测试书.txt"
            缓存路径.write_text("正文", encoding="utf-8")
            失败网盘 = _失败网盘()

            with patch.object(小说网盘, "获取当前主网盘", return_value="夸克"), \
                patch.object(小说网盘, "主网盘是否启用", return_value=True), \
                patch.dict(小说网盘.网盘模块映射, {"夸克": 失败网盘}, clear=False):
                结果 = await 小说网盘.上传小说并获取分享链接(
                    {}, 缓存路径, 缓存路径.name
                )

            self.assertFalse(结果["success"])
            self.assertTrue(下载缓存清理.上传任务待续传(缓存路径))
            self.assertTrue(缓存路径.exists())

    async def test_重载后自动恢复待上传任务(self):
        with tempfile.TemporaryDirectory() as 临时目录:
            缓存目录 = Path(临时目录)
            缓存路径 = 缓存目录 / "测试书.txt"
            缓存路径.write_text("正文", encoding="utf-8")
            下载缓存清理.登记上传任务(缓存路径, 缓存路径.name, "夸克网盘")
            成功网盘 = _成功网盘()

            with patch.object(下载缓存清理, "下载缓存目录", 缓存目录), \
                patch.object(小说网盘, "获取当前主网盘", return_value="夸克"), \
                patch.object(小说网盘, "主网盘是否启用", return_value=True), \
                patch.dict(小说网盘.网盘模块映射, {"夸克": 成功网盘}, clear=False):
                恢复数量 = await 小说网盘.恢复待续传上传任务({})

            self.assertEqual(恢复数量, 1)
            self.assertFalse(缓存路径.exists())
            self.assertFalse(下载缓存清理.上传任务待续传(缓存路径))


if __name__ == "__main__":
    unittest.main()
