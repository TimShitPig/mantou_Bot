from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent


数字撤回规则 = re.compile(r"^\d{9,12}$")
历史撤回数量 = 20
历史拉取数量 = 80


def 是否需要撤回数字消息(消息文本: str) -> bool:
    return bool(数字撤回规则.fullmatch(str(消息文本 or "").strip()))


async def 处理数字撤回(event: AstrMessageEvent, 消息文本: str) -> bool:
    if not 是否需要撤回数字消息(消息文本):
        return False

    当前消息编号 = 获取当前消息编号(event)
    当前用户编号 = 获取当前用户编号(event)
    bot = getattr(event, "bot", None)

    if bot is None:
        logger.warning("数字撤回失败：当前事件缺少 bot 实例")
        return True

    if not 当前消息编号:
        logger.warning("数字撤回警告：当前事件缺少 message_id，将只尝试撤回历史消息")

    历史消息 = await 获取当前会话历史消息(event, bot)
    待撤回编号 = 提取该用户历史消息编号(历史消息, 当前用户编号, 当前消息编号)

    撤回成功数 = 0
    for 消息编号 in 待撤回编号:
        if await 尝试撤回消息(bot, 消息编号):
            撤回成功数 += 1

    if 当前消息编号 and 当前消息编号 not in 待撤回编号:
        if await 尝试撤回消息(bot, 当前消息编号):
            撤回成功数 += 1

    logger.info(
        f"数字撤回完成：user_id={当前用户编号 or '未知'}, "
        f"history_count={len(待撤回编号)}, success_count={撤回成功数}"
    )
    return True


async def 获取当前会话历史消息(event: AstrMessageEvent, bot: Any) -> list[dict[str, Any]]:
    群号 = 获取当前群号(event)
    用户编号 = 获取当前用户编号(event)

    if 群号:
        响应 = await 调用动作(bot, "get_group_msg_history", group_id=群号, count=历史拉取数量)
    elif 用户编号:
        响应 = await 调用动作(bot, "get_friend_msg_history", user_id=用户编号, count=历史拉取数量)
    else:
        logger.warning("数字撤回无法获取历史：缺少 group_id/user_id")
        return []

    return 解析历史消息列表(响应)


async def 调用动作(bot: Any, 动作名: str, **参数: Any) -> Any:
    调用方式 = []
    if hasattr(bot, "api") and callable(getattr(bot.api, "call_action", None)):
        调用方式.append(lambda: bot.api.call_action(动作名, **参数))
    if callable(getattr(bot, "call_api", None)):
        调用方式.append(lambda: bot.call_api(动作名, **参数))
    if callable(getattr(bot, "call_action", None)):
        调用方式.append(lambda: bot.call_action(动作名, **参数))

    for 调用 in 调用方式:
        try:
            return await 调用()
        except Exception as exc:
            logger.warning(f"数字撤回调用 {动作名} 失败：{exc}")
    return None


def 解析历史消息列表(响应: Any) -> list[dict[str, Any]]:
    if isinstance(响应, list):
        return [消息 for 消息 in 响应 if isinstance(消息, dict)]
    if not isinstance(响应, dict):
        return []

    for 字段名 in ("messages", "message", "data"):
        值 = 响应.get(字段名)
        if isinstance(值, list):
            return [消息 for 消息 in 值 if isinstance(消息, dict)]
        if isinstance(值, dict):
            嵌套消息 = 解析历史消息列表(值)
            if 嵌套消息:
                return 嵌套消息
    return []


def 提取该用户历史消息编号(
    历史消息: list[dict[str, Any]], 当前用户编号: Any, 当前消息编号: Any
) -> list[Any]:
    当前用户 = 规范编号(当前用户编号)
    当前消息 = 规范编号(当前消息编号)
    结果: list[Any] = []
    已见: set[str] = set()

    for 消息 in reversed(历史消息):
        消息编号 = 消息.get("message_id") or 消息.get("id")
        消息编号文本 = 规范编号(消息编号)
        if not 消息编号文本 or 消息编号文本 == 当前消息 or 消息编号文本 in 已见:
            continue

        发送者编号 = 获取历史消息用户编号(消息)
        if 当前用户 and 发送者编号 and 发送者编号 != 当前用户:
            continue

        已见.add(消息编号文本)
        结果.append(消息编号)
        if len(结果) >= 历史撤回数量:
            break

    return 结果


def 获取历史消息用户编号(消息: dict[str, Any]) -> str:
    发送者 = 消息.get("sender")
    if isinstance(发送者, dict):
        for 字段名 in ("user_id", "id", "uin", "uid"):
            编号 = 规范编号(发送者.get(字段名))
            if 编号:
                return 编号

    for 字段名 in ("user_id", "sender_id", "sender", "uid"):
        编号 = 规范编号(消息.get(字段名))
        if 编号:
            return 编号
    return ""


async def 尝试撤回消息(bot: Any, 消息编号: Any) -> bool:
    if not 消息编号:
        return False

    for 撤回函数 in (使用_delete_msg撤回, 使用_api_call_action撤回, 使用_call_api撤回, 使用_call_action撤回):
        try:
            if await 撤回函数(bot, 消息编号):
                logger.info(f"数字撤回成功：message_id={消息编号}")
                return True
        except Exception as exc:
            logger.warning(f"数字撤回尝试失败：message_id={消息编号}, error={exc}")
    return False


async def 尝试撤回当前消息(event: AstrMessageEvent) -> bool:
    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning("数字撤回失败：当前事件缺少 bot 实例")
        return False
    return await 尝试撤回消息(bot, 获取当前消息编号(event))


def 获取当前消息编号(event: AstrMessageEvent) -> Any:
    消息对象 = getattr(event, "message_obj", None)
    if 消息对象 is None:
        return None
    if isinstance(消息对象, dict):
        return 消息对象.get("message_id") or 消息对象.get("id")
    return getattr(消息对象, "message_id", None) or getattr(消息对象, "id", None)


def 获取当前用户编号(event: AstrMessageEvent) -> Any:
    try:
        用户编号 = event.get_sender_id()
        if 用户编号:
            return 用户编号
    except Exception:
        pass

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("user_id", "sender_id", "sender", "openid", "user_openid"):
            值 = 读取字段(对象, 字段名)
            if 值:
                return 值
    return None


def 获取当前群号(event: AstrMessageEvent) -> Any:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("group_id", "groupId"):
            值 = 读取字段(对象, 字段名)
            if 值:
                return 值
    return None


def 读取字段(对象: Any, 字段名: str) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 规范编号(编号: Any) -> str:
    if 编号 is None:
        return ""
    return str(编号).strip()


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
