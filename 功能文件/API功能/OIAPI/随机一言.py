from __future__ import annotations

from typing import Any

import aiohttp


接口地址 = "https://oiapi.net/api/AWord"


async def 获取随机一言回复() -> str:
    try:
        数据 = await 请求随机一言()
        return 格式化随机一言(数据)
    except Exception:
        return "获取随机一言失败，请稍后再试。"


async def 请求随机一言() -> dict[str, Any]:
    超时设置 = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=超时设置) as 会话:
        async with 会话.get(接口地址) as 响应:
            响应.raise_for_status()
            数据 = await 响应.json(content_type=None)
            if not isinstance(数据, dict):
                raise ValueError("接口返回格式不是对象")
            return 数据


def 格式化随机一言(响应数据: dict[str, Any]) -> str:
    一言数据 = 响应数据.get("data")
    if not isinstance(一言数据, dict):
        raise ValueError("缺少一言数据")

    内容 = 获取文本字段(一言数据, "content")
    出处 = 获取文本字段(一言数据, "from")
    时间 = 获取文本字段(一言数据, "time")

    return "\n".join(
        [
            f"一言：{内容}",
            f"出处：{出处}",
            f"时间：{时间}",
        ]
    )


def 获取文本字段(数据: dict[str, Any], 字段名: str) -> str:
    字段值 = 数据.get(字段名)
    if not isinstance(字段值, str) or not 字段值.strip():
        raise ValueError(f"缺少字段：{字段名}")
    return 字段值.strip()
