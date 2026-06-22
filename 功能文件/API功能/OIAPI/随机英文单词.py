from __future__ import annotations

from typing import Any

import aiohttp


接口地址 = "https://oiapi.net/api/RandEnglishDict"


async def 获取随机英文单词回复() -> str:
    try:
        数据 = await 请求随机英文单词()
        return 格式化随机英文单词(数据)
    except Exception:
        return "获取随机英文单词失败，请稍后再试。"


async def 请求随机英文单词() -> dict[str, Any]:
    超时设置 = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=超时设置) as 会话:
        async with 会话.get(接口地址) as 响应:
            响应.raise_for_status()
            数据 = await 响应.json(content_type=None)
            if not isinstance(数据, dict):
                raise ValueError("接口返回格式不是对象")
            return 数据


def 格式化随机英文单词(响应数据: dict[str, Any]) -> str:
    单词数据 = 响应数据.get("data")
    if not isinstance(单词数据, dict):
        raise ValueError("缺少单词数据")

    单词 = 获取文本字段(单词数据, "content")
    翻译 = 获取文本字段(单词数据, "trans")
    例句, 译文 = 获取第一条例句(单词数据)

    return "\n".join(
        [
            f"单词：{单词}",
            f"翻译：{翻译}",
            f"例句：{例句}",
            f"译文：{译文}",
        ]
    )


def 获取文本字段(数据: dict[str, Any], 字段名: str) -> str:
    字段值 = 数据.get(字段名)
    if not isinstance(字段值, str) or not 字段值.strip():
        raise ValueError(f"缺少字段：{字段名}")
    return 字段值.strip()


def 获取第一条例句(单词数据: dict[str, Any]) -> tuple[str, str]:
    例句列表 = 单词数据.get("sentences")
    if not isinstance(例句列表, list) or not 例句列表:
        raise ValueError("缺少例句")

    第一条例句 = 例句列表[0]
    if not isinstance(第一条例句, dict):
        raise ValueError("例句格式错误")

    return 获取文本字段(第一条例句, "sContent"), 获取文本字段(第一条例句, "sCn")
