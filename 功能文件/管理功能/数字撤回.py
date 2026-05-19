from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent


数字撤回规则 = re.compile(r"^\d{9,12}$")


def 是否需要撤回数字消息(消息文本: str) -> bool:
    return bool(数字撤回规则.fullmatch(str(消息文本 or "").strip()))


async def 尝试撤回当前消息(event: AstrMessageEvent) -> bool:
    消息编号 = 获取当前消息编号(event)
    if not 消息编号:
        logger.warning("数字撤回失败：当前事件缺少 message_id")
        return False

    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"数字撤回失败：当前事件缺少 bot 实例，message_id={消息编号}")
        return False

    for 撤回函数 in (使用_delete_msg撤回, 使用_call_api撤回, 使用_call_action撤回):
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
    if 消息对象 is None:
        return None
    if isinstance(消息对象, dict):
        return 消息对象.get("message_id") or 消息对象.get("id")
    return getattr(消息对象, "message_id", None) or getattr(消息对象, "id", None)


async def 使用_delete_msg撤回(bot: Any, 消息编号: Any) -> bool:
    撤回方法 = getattr(bot, "delete_msg", None)
    if not callable(撤回方法):
        return False
    await 撤回方法(message_id=消息编号)
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
