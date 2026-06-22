from __future__ import annotations

from typing import Any

import aiohttp


接口地址 = "https://oiapi.net/api/KFC"


async def 获取疯狂星期四回复() -> str:
    try:
        数据 = await 请求疯狂星期四()
        return 格式化疯狂星期四(数据)
    except Exception:
        return "获取疯狂星期四文案失败，请稍后再试。"


async def 请求疯狂星期四() -> dict[str, Any]:
    超时设置 = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=超时设置) as 会话:
        async with 会话.get(接口地址) as 响应:
            响应.raise_for_status()
            数据 = await 响应.json(content_type=None)
            if not isinstance(数据, dict):
                raise ValueError("接口返回格式不是对象")
            return 数据


def 格式化疯狂星期四(响应数据: dict[str, Any]) -> str:
    文案 = 响应数据.get("message")
    if not isinstance(文案, str) or not 文案.strip():
        raise ValueError("缺少疯狂星期四文案")
    return 文案.strip()
