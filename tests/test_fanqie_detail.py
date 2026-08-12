from __future__ import annotations

import asyncio
import importlib
import unittest
from unittest.mock import AsyncMock, patch


番茄小说 = importlib.import_module("功能文件.管理功能.小说功能.小说.番茄小说")


class 假响应:
    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


class 假客户端:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls = 0

    async def request(self, method: str, url: str, **kwargs):
        self.calls += 1
        return 假响应(self.responses.pop(0))


class 番茄详情测试(unittest.TestCase):
    def test_业务失败后会重试并返回真实详情(self) -> None:
        client = 假客户端(
            [
                {"code": 4004, "data": {}},
                {"code": 0, "data": {"book_name": "真实书名", "author": "真实作者"}},
            ]
        )

        详情 = asyncio.run(
            番茄小说.异步获取番茄书籍详情(client, "7280731566056148003")
        )

        self.assertEqual(详情["book_name"], "真实书名")
        self.assertEqual(详情["author"], "真实作者")
        self.assertEqual(client.calls, 2)

    def test_连续空详情会失败而不是返回占位详情(self) -> None:
        client = 假客户端([{"code": 4004, "data": {}}] * 4)

        with self.assertRaises(RuntimeError):
            asyncio.run(
                番茄小说.异步获取番茄书籍详情(client, "7280731566056148003")
            )

        self.assertGreaterEqual(client.calls, 3)

    def test_非字典详情数据不会被当成成功(self) -> None:
        client = 假客户端([{"code": 0, "data": []}] * 4)

        with self.assertRaises(RuntimeError):
            asyncio.run(
                番茄小说.异步获取番茄书籍详情(client, "7280731566056148003")
            )

    def test_准备阶段详情失败不会继续生成占位书名(self) -> None:
        with patch.object(
            番茄小说,
            "异步解析番茄目录",
            new=AsyncMock(return_value=["7474835508535774233"]),
        ), patch.object(
            番茄小说,
            "异步获取番茄书籍详情",
            new=AsyncMock(side_effect=RuntimeError("detail failed")),
        ), patch.object(
            番茄小说,
            "异步读取番茄目录元数据",
            new=AsyncMock(return_value={}),
        ):
            with self.assertRaises(RuntimeError):
                asyncio.run(
                    番茄小说.异步准备番茄下载数据(
                        object(), "7280731566056148003"
                    )
                )


if __name__ == "__main__":
    unittest.main()
