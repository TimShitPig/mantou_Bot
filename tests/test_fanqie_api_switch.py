from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def 安装astrbot桩() -> None:
    logger = types.SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
    )
    message_components = types.SimpleNamespace(File=lambda **kwargs: kwargs)
    api模块 = types.ModuleType("astrbot.api")
    api模块.logger = logger
    api模块.message_components = message_components
    astrbot模块 = types.ModuleType("astrbot")
    astrbot模块.api = api模块
    sys.modules.setdefault("astrbot", astrbot模块)
    sys.modules.setdefault("astrbot.api", api模块)


class 假事件:
    group_id = "456"

    def get_sender_id(self) -> str:
        return "123"


class 假响应:
    status = 200

    def __init__(self, 数据: dict):
        self.数据 = 数据

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self) -> str:
        return json.dumps(self.数据, ensure_ascii=False)


class 假会话:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def get(self, 地址: str, **kwargs):
        参数 = dict(kwargs.get("params") or {})
        self.calls.append((urlparse(地址).path, 参数))
        路径 = urlparse(地址).path
        if 路径 == "/api/detail":
            return 假响应(
                {
                    "code": 200,
                    "data": {
                        "code": 0,
                        "data": {
                            "book_id": 参数["book_id"],
                            "book_name": "测试书",
                            "author": "测试作者",
                            "creation_status": "0",
                            "word_number": "12345",
                            "serial_count": "1",
                            "abstract": "测试简介",
                        },
                    },
                }
            )
        if 路径 == "/api/book":
            return 假响应(
                {
                    "code": 200,
                    "data": {
                        "code": 0,
                        "data": {
                            "chapterListWithVolume": [
                                [
                                    {
                                        "itemId": "chapter-1",
                                        "title": "第一章",
                                        "realChapterOrder": "1",
                                    }
                                ]
                            ],
                            "allItemIds": ["chapter-1"],
                        },
                    },
                }
            )
        if 路径 == "/api/content":
            return 假响应(
                {
                    "code": 200,
                    "data": {
                        "chapters": [
                            {
                                "item_id": "chapter-1",
                                "title": "第一章",
                                "content": "第一段\n\n第二段",
                            }
                        ]
                    },
                }
            )
        raise AssertionError(f"unexpected path: {路径}")


class 番茄API切换测试(unittest.TestCase):
    def setUp(self) -> None:
        安装astrbot桩()
        self.模块 = importlib.import_module("功能文件.API功能.OIAPI.番茄小说")
        self.模块.待选择API会话.clear()
        self.状态: dict[tuple[str, str], str] = {}
        self.模块.读取运行状态值 = lambda 配置, 命名空间, 状态键, 默认值="": self.状态.get((命名空间, 状态键), 默认值)

        def 写入状态(配置, 命名空间, 状态键, 状态值):
            self.状态[(命名空间, 状态键)] = str(状态值)

        self.模块.写入运行状态值 = 写入状态
        self.配置 = {"group_file_cleanup_admin_qq": ["123"]}
        self.事件 = 假事件()

    def test_查看api列出番茄api并允许数字4切换(self):
        菜单 = self.模块.处理番茄小说API指令(self.事件, "查看API", self.配置)

        self.assertIn("4. 番茄API", 菜单)
        self.assertIn("1、2、3 或 4", 菜单)

        回复 = self.模块.处理番茄小说API指令(self.事件, "4", self.配置)

        self.assertEqual("番茄小说API已切换为：番茄API", 回复)
        self.assertEqual("番茄API", self.状态[("fanqie_api", "current_api")])
        self.assertEqual("番茄API", self.模块.规范化番茄小说接口("4"))

    def test_番茄api别名可直接切换(self):
        回复 = self.模块.处理番茄小说API指令(self.事件, "番茄api", self.配置)

        self.assertEqual("番茄小说API已切换为：番茄API", 回复)
        self.assertEqual("番茄API", self.状态[("fanqie_api", "current_api")])


class 番茄独立API模块测试(unittest.TestCase):
    def setUp(self) -> None:
        安装astrbot桩()
        self.模块 = importlib.import_module("功能文件.API功能.番茄API.番茄小说")

    def test_独立模块用详情目录和批量内容接口生成统一结果(self):
        async def 场景():
            会话 = 假会话()
            准备结果 = await self.模块.准备番茄小说(会话, "7461615503505640473")
            self.assertTrue(准备结果["success"])
            self.assertEqual("测试书", 准备结果["book_info"]["title"])
            self.assertEqual("测试作者", 准备结果["book_info"]["author"])
            self.assertEqual(1, 准备结果["book_info"]["chapter_count"])
            self.assertEqual("chapter-1", 准备结果["chapters"][0]["id"])

            章节结果 = await self.模块.下载全部章节(会话, "7461615503505640473", 准备结果["chapters"])

            self.assertEqual("第一段\n\n第二段", 章节结果[0]["content"])
            self.assertTrue(章节结果[0]["success"])
            self.assertIn(("/api/detail", {"book_id": "7461615503505640473"}), 会话.calls)
            self.assertIn(("/api/book", {"book_id": "7461615503505640473"}), 会话.calls)
            self.assertIn(
                (
                    "/api/content",
                    {"tab": "批量", "item_ids": "chapter-1", "book_id": "7461615503505640473"},
                ),
                会话.calls,
            )

        asyncio.run(场景())


if __name__ == "__main__":
    unittest.main()
