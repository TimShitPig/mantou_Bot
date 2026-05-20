from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent


数字撤回规则 = re.compile(r"(?<!\d)\d{9,12}(?!\d)")
链接规则 = re.compile(r"https?://|https?%3A%2F%2F|\b\w+\.\w+/", re.IGNORECASE)


def 是否需要撤回数字消息(消息文本: str) -> bool:
    文本 = str(消息文本 or "").strip()
    if 链接规则.search(文本):
        return False
    return bool(数字撤回规则.search(文本))


def 获取消息文本(event: AstrMessageEvent) -> str:
    事件文本 = 清理可见文本(str(getattr(event, "message_str", "") or ""))
    if 事件文本:
        return 事件文本

    消息对象 = getattr(event, "message_obj", None)
    候选文本 = []
    for 对象 in (消息对象,):
        if 对象 is None:
            continue
        for 字段名 in ("message",):
            文本 = 转成文本(读取字段(对象, 字段名))
            if 文本:
                候选文本.append(文本)

    for 文本 in 候选文本:
        if 是否需要撤回数字消息(文本):
            return 文本
    return 候选文本[0] if 候选文本 else ""


async def 尝试撤回当前消息(event: AstrMessageEvent) -> bool:
    消息编号 = 获取当前消息编号(event)
    if not 消息编号:
        logger.warning("数字撤回失败：当前事件缺少 message_id")
        return False

    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"数字撤回失败：当前事件缺少 bot 实例，message_id={消息编号}")
        return False

    for 撤回函数 in (使用_delete_msg撤回, 使用_api_call_action撤回, 使用_call_api撤回, 使用_call_action撤回):
        try:
            if await 撤回函数(bot, 消息编号):
                logger.info(f"数字撤回成功：message_id={消息编号}")
                return True
        except Exception as exc:
            logger.warning(f"数字撤回尝试失败：message_id={消息编号}, error={exc}")

    logger.warning(f"数字撤回失败：没有可用的撤回接口，message_id={消息编号}")
    return False


def 获取当前消息编号(event: AstrMessageEvent) -> Any:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        if 对象 is None:
            continue
        if isinstance(对象, dict):
            消息编号 = 对象.get("message_id") or 对象.get("id")
        else:
            消息编号 = getattr(对象, "message_id", None) or getattr(对象, "id", None)
        if 消息编号:
            return 消息编号
    return None


def 读取字段(对象: Any, 字段名: str) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 转成文本(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, str):
        return 清理可见文本(值)
    if isinstance(值, list):
        return 清理可见文本("".join(转消息段文本(消息段) for 消息段 in 值))
    if isinstance(值, dict):
        return 清理可见文本(转消息段文本(值))
    return ""


def 清理可见文本(文本: str) -> str:
    文本 = re.sub(r"\[CQ:reply,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[CQ:at,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[At:[^\]]+\]", "", 文本)
    return 文本.strip()


def 转消息段文本(消息段: Any) -> str:
    if not isinstance(消息段, dict):
        return ""
    if 消息段.get("type") != "text":
        return ""
    数据 = 消息段.get("data")
    if isinstance(数据, dict):
        return str(数据.get("text") or "")
    return ""


async def 使用_delete_msg撤回(bot: Any, 消息编号: Any) -> bool:
    撤回方法 = getattr(bot, "delete_msg", None)
    if not callable(撤回方法):
        return False
    await 撤回方法(message_id=消息编号)
    return True


async def 使用_api_call_action撤回(bot: Any, 消息编号: Any) -> bool:
    api = getattr(bot, "api", None)
    调用方法 = getattr(api, "call_action", None)
    if not callable(调用方法):
        return False
    await 调用方法("delete_msg", message_id=消息编号)
    return True


async def 使用_call_api撤回(bot: Any, 消息编号: Any) -> bool:
    调用方法 = getattr(bot, "call_api", None)
    if not callable(调用方法):
        return False
    await 调用方法("delete_msg", message_id=消息编号)
    return True


async def 使用_call_action撤回(bot: Any, 消息编号: Any) -> bool:
    调用方法 = getattr(bot, "call_action", None)
    if not callable(调用方法):
        return False
    await 调用方法("delete_msg", message_id=消息编号)
    return True
