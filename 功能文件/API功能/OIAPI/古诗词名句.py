from __future__ import annotations

from typing import Any

import aiohttp


接口地址 = "https://oiapi.net/api/Sentences"


async def 获取古诗词名句回复() -> str:
    try:
        数据 = await 请求古诗词名句()
        return 格式化古诗词名句(数据)
    except Exception:
        return "获取古诗词名句失败，请稍后再试。"


async def 请求古诗词名句() -> dict[str, Any]:
    超时设置 = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=超时设置) as 会话:
        async with 会话.get(接口地址) as 响应:
            响应.raise_for_status()
            数据 = await 响应.json(content_type=None)
            if not isinstance(数据, dict):
                raise ValueError("接口返回格式不是对象")
            return 数据


def 格式化古诗词名句(响应数据: dict[str, Any]) -> str:
    名句数据 = 响应数据.get("data")
    if not isinstance(名句数据, dict):
        raise ValueError("缺少古诗词名句数据")

    内容 = 获取文本字段(名句数据, "content")
    作者 = 获取文本字段(名句数据, "author")
    作品 = 获取文本字段(名句数据, "works")

    return "\n".join(
        [
            f"名句：{内容}",
            f"作者：{作者}",
            f"作品：{作品}",
        ]
    )


def 获取文本字段(数据: dict[str, Any], 字段名: str) -> str:
    字段值 = 数据.get(字段名)
    if not isinstance(字段值, str) or not 字段值.strip():
        raise ValueError(f"缺少字段：{字段名}")
    return 字段值.strip()
