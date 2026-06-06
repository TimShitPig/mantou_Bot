from __future__ import annotations

import inspect
import re
from typing import Any


数字群号规则 = re.compile(r"[1-9]\d{4,11}")


async def 获取机器人所在群号列表(bot: Any) -> list[str]:
    响应 = await 调用群列表接口(bot)
    群号列表 = 提取群号列表(响应)
    if not 群号列表:
        raise RuntimeError("没有获取到机器人所在的数字群号")
    return 群号列表


async def 调用群列表接口(bot: Any) -> Any:
    群列表方法 = getattr(bot, "get_group_list", None)
    if callable(群列表方法):
        return await 等待可能异步结果(群列表方法())

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        return await 等待可能异步结果(调用动作("get_group_list"))

    raise RuntimeError("当前 bot 没有 get_group_list 群列表接口")


async def 等待可能异步结果(结果: Any) -> Any:
    if inspect.isawaitable(结果):
        return await 结果
    return 结果


def 提取群号列表(响应: Any) -> list[str]:
    数据 = 响应.get("data") if isinstance(响应, dict) and "data" in 响应 else 响应
    候选列表: list[Any]
    if isinstance(数据, dict):
        候选列表 = 数据.get("groups") or 数据.get("group_list") or 数据.get("list") or []
    elif isinstance(数据, list):
        候选列表 = 数据
    else:
        候选列表 = []

    结果: list[str] = []
    已见: set[str] = set()
    for 候选 in 候选列表:
        群号 = 提取单个群号(候选)
        if not 群号 or 群号 in 已见:
            continue
        已见.add(群号)
        结果.append(群号)
    return 结果


def 提取单个群号(值: Any) -> str:
    if isinstance(值, dict):
        值 = 值.get("group_id") or 值.get("group") or 值.get("id")
    文本 = str(值 or "").strip()
    return 文本 if 数字群号规则.fullmatch(文本) else ""
