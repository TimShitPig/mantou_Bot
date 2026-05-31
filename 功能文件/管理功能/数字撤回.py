from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent


数字撤回规则 = re.compile(r"(?<!\d)\d{9,12}(?!\d)")
链接规则 = re.compile(r"https?://|https?%3A%2F%2F|\b\w+\.\w+/", re.IGNORECASE)
白名单域名规则 = re.compile(r"changdunovel\.com|fanqienovel\.com|fqnovel\.com|novelfm\.com|qimao\.com|app-share\.wtzw\.com", re.IGNORECASE)
群名片规则 = re.compile(r"\[CQ:contact,[^\]]*(?:type=group|type=qq_group)[^\]]*\]")
卡片消息规则 = re.compile(r"ComponentType\.(?:Json|Share|Contact)|\[CQ:(?:json|contact),", re.IGNORECASE)
At消息规则 = re.compile(r"\[CQ:at,[^\]]*\]|\[At:[^\]]+\]|ComponentType\.At", re.IGNORECASE)
合并转发规则 = re.compile(
    r"ComponentType\.(?:Forward|Node|Nodes)|\[CQ:(?:forward|node),|群聊的聊天记录|查看\d+条转发消息",
    re.IGNORECASE,
)
闪传消息规则 = re.compile(r"QQ闪传|该消息类型暂不支持查看", re.IGNORECASE)
数字ID规则 = re.compile(r"[1-9]\d{4,11}")
数字撤回踢出阈值 = 3
数字撤回触发次数: dict[str, int] = {}
数字撤回模块版本 = "1.9.1"


async def 处理数字撤回(event: AstrMessageEvent) -> bool:
    消息文本 = 获取消息文本(event)
    卡片类型 = 获取卡片撤回类型(event)
    if 卡片类型:
        记录卡片诊断日志(event, 消息文本, 卡片类型)
    if not 是否需要撤回消息(event, 消息文本):
        return False
    撤回成功 = await 尝试撤回当前消息(event)
    if 撤回成功:
        await 记录撤回触发并尝试踢出(event)
    return 撤回成功


def 是否需要撤回消息(event: AstrMessageEvent, 消息文本: str = "") -> bool:
    if 是否白名单消息(event, 消息文本):
        return False
    if 是否At消息(event):
        return False
    return (
        是否群名片消息(event)
        or 是否合并转发消息(event)
        or 是否闪传消息(event)
        or 是否需要撤回数字消息(消息文本)
    )


def 是否需要撤回数字消息(消息文本: str) -> bool:
    文本 = str(消息文本 or "").strip()
    if 链接规则.search(文本):
        return False
    return bool(数字撤回规则.search(文本))


def 是否白名单消息(event: AstrMessageEvent, 消息文本: str = "") -> bool:
    if 白名单域名规则.search(str(消息文本 or "")):
        return True
    for 文本 in 获取原始文本候选(event):
        if 白名单域名规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含白名单域名(消息):
            return True
    return False


def 是否群名片消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if 群名片规则.search(文本) or 卡片消息规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含群名片消息段(消息) or 包含卡片标记(消息):
            return True
    return False


def 是否合并转发消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if 合并转发规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含合并转发消息段(消息) or 包含合并转发标记(消息):
            return True
    return False


def 是否闪传消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if 闪传消息规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含闪传标记(消息):
            return True
    return False


def 获取卡片撤回类型(event: AstrMessageEvent) -> str:
    if 是否群名片消息(event):
        return "群名片/JSON卡片"
    if 是否合并转发消息(event):
        return "合并转发"
    if 是否闪传消息(event):
        return "QQ闪传"
    return ""


def 记录卡片诊断日志(event: AstrMessageEvent, 消息文本: str, 卡片类型: str) -> None:
    消息对象 = getattr(event, "message_obj", None)
    logger.info(
        "卡片诊断："
        f"类型={卡片类型}, "
        f"message_id={获取当前消息编号(event)}, "
        f"message_str={限制长度(getattr(event, 'message_str', ''))}, "
        f"raw_message={限制长度(getattr(event, 'raw_message', ''))}, "
        f"提取文本={限制长度(消息文本)}, "
        f"event_message={描述值(读取字段(event, 'message'))}, "
        f"message_obj_message={描述值(读取字段(消息对象, 'message'))}"
    )


def 是否At消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if At消息规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含At消息段(消息) or 包含At对象标记(消息):
            return True
    return False


def 获取原始文本候选(event: AstrMessageEvent) -> list[str]:
    消息对象 = getattr(event, "message_obj", None)
    结果: list[str] = []
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, str) and 值:
                结果.append(值)
    return 结果


def 包含群名片消息段(消息: Any) -> bool:
    if isinstance(消息, list):
        return any(是否群名片消息段(消息段) for 消息段 in 消息)
    return 是否群名片消息段(消息)


def 包含At消息段(消息: Any) -> bool:
    if isinstance(消息, list):
        return any(是否At消息段(消息段) for 消息段 in 消息)
    return 是否At消息段(消息)


def 包含合并转发消息段(消息: Any) -> bool:
    if isinstance(消息, list):
        return any(是否合并转发消息段(消息段) for 消息段 in 消息)
    return 是否合并转发消息段(消息)


def 是否At消息段(消息段: Any) -> bool:
    if isinstance(消息段, dict):
        return 是否At类型值(消息段.get("type"))
    return 是否At类型值(读取字段(消息段, "type"))


def 是否合并转发消息段(消息段: Any) -> bool:
    if isinstance(消息段, dict):
        return 是否合并转发类型值(消息段.get("type"))
    return 是否合并转发类型值(读取字段(消息段, "type"))


def 包含At对象标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含At对象标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return 是否At消息段(值) or any(包含At对象标记(子值) for 子值 in 值.values())
    return bool(At消息规则.search(str(值)))


def 包含合并转发标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含合并转发标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return 是否合并转发消息段(值) or any(包含合并转发标记(子值) for 子值 in 值.values())
    return bool(合并转发规则.search(str(值)))


def 包含闪传标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含闪传标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return any(包含闪传标记(子值) for 子值 in 值.values())
    return bool(闪传消息规则.search(str(值)))


def 包含白名单域名(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含白名单域名(子值) for 子值 in 值)
    if isinstance(值, dict):
        return any(包含白名单域名(子值) for 子值 in 值.values())
    return bool(白名单域名规则.search(str(值)))


def 是否At类型值(值: Any) -> bool:
    for 候选 in (值, 读取字段(值, "value"), 读取字段(值, "name")):
        if 候选 is None:
            continue
        文本 = str(候选).strip().lower()
        if 文本 == "at" or 文本.endswith(".at") or "componenttype.at" in 文本:
            return True
    return False


def 是否合并转发类型值(值: Any) -> bool:
    for 候选 in (值, 读取字段(值, "value"), 读取字段(值, "name")):
        if 候选 is None:
            continue
        文本 = str(候选).strip().lower()
        if 文本 in ("forward", "node", "nodes") or 文本.endswith((".forward", ".node", ".nodes")):
            return True
        if any(标记 in 文本 for 标记 in ("componenttype.forward", "componenttype.node", "componenttype.nodes")):
            return True
    return False


def 是否群名片消息段(消息段: Any) -> bool:
    if not isinstance(消息段, dict):
        return False
    if 消息段.get("type") == "json":
        return True
    if 消息段.get("type") != "contact":
        return False
    数据 = 消息段.get("data")
    if not isinstance(数据, dict):
        return False
    return str(数据.get("type") or "").lower() in ("group", "qq_group")


def 包含卡片标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, list):
        return any(包含卡片标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return any(包含卡片标记(子值) for 子值 in 值.values())
    return bool(卡片消息规则.search(str(值)))


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
    if 是否At消息(event):
        logger.info("数字撤回跳过：普通@消息不撤回")
        return False

    消息编号 = 获取当前消息编号(event)
    if not 消息编号:
        logger.warning("数字撤回失败：当前事件缺少 message_id")
        return False

    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"数字撤回失败：当前事件缺少 bot 实例，message_id={消息编号}")
        return False

    try:
        await 使用_delete_msg撤回(bot, 消息编号)
        logger.info(f"数字撤回成功：message_id={消息编号}")
        return True
    except Exception as exc:
        logger.warning(f"数字撤回失败：message_id={消息编号}, error={exc}")
        return False


async def 记录撤回触发并尝试踢出(event: AstrMessageEvent) -> None:
    群号 = 获取群号(event)
    用户QQ = 获取发送者QQ(event)
    if not 是数字ID(群号) or not 是数字ID(用户QQ):
        logger.info(f"数字撤回踢出跳过：缺少数字群号或用户QQ，group_id={群号}, user_id={用户QQ}")
        return

    计数键 = f"{群号}:{用户QQ}"
    当前次数 = 数字撤回触发次数.get(计数键, 0) + 1
    数字撤回触发次数[计数键] = 当前次数
    logger.info(f"数字撤回模块触发计数：group_id={群号}, user_id={用户QQ}, count={当前次数}/{数字撤回踢出阈值}")
    if 当前次数 < 数字撤回踢出阈值:
        return

    if await 尝试踢出成员(event, 群号, 用户QQ):
        数字撤回触发次数.pop(计数键, None)


async def 尝试踢出成员(event: AstrMessageEvent, 群号: str, 用户QQ: str) -> bool:
    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"数字撤回踢出失败：当前事件缺少 bot 实例，group_id={群号}, user_id={用户QQ}")
        return False

    try:
        await 使用_set_group_kick踢出(bot, 群号, 用户QQ)
        logger.info(f"数字撤回触发 {数字撤回踢出阈值} 次，已踢出成员：group_id={群号}, user_id={用户QQ}")
        return True
    except Exception as exc:
        logger.warning(f"数字撤回踢出失败：group_id={群号}, user_id={用户QQ}, error={exc}")
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


def 获取群号(event: AstrMessageEvent) -> str:
    for 方法名 in ("get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "group_id") or 读取字段(对象, "group")
        if isinstance(值, dict):
            值 = 值.get("group_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 获取发送者QQ(event: AstrMessageEvent) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "sender_id") or 读取字段(对象, "user_id") or 读取字段(对象, "sender")
        if isinstance(值, dict):
            值 = 值.get("user_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 是数字ID(值: Any) -> bool:
    return bool(数字ID规则.fullmatch(str(值 or "").strip()))


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


def 限制长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    if len(文本) > 最大长度:
        return 文本[:最大长度] + "..."
    return 文本


def 描述值(值: Any) -> str:
    if 值 is None:
        return "None"
    if isinstance(值, list):
        return "[" + ", ".join(描述消息段(消息段) for 消息段 in 值) + "]"
    return 描述消息段(值)


def 描述消息段(消息段: Any) -> str:
    if isinstance(消息段, dict):
        return 限制长度(
            {
                "class": type(消息段).__name__,
                "type": 消息段.get("type"),
                "data": 消息段.get("data"),
                "str": str(消息段),
            }
        )
    return 限制长度(
        {
            "class": type(消息段).__name__,
            "type": 读取字段(消息段, "type"),
            "data": 读取字段(消息段, "data"),
            "value": 读取字段(消息段, "value"),
            "name": 读取字段(消息段, "name"),
            "str": str(消息段),
        }
    )


async def 使用_delete_msg撤回(bot: Any, 消息编号: Any) -> bool:
    撤回方法 = getattr(bot, "delete_msg", None)
    if not callable(撤回方法):
        raise RuntimeError("当前 bot 没有 delete_msg 撤回接口")
    await 撤回方法(message_id=消息编号)
    return True


async def 使用_set_group_kick踢出(bot: Any, 群号: str, 用户QQ: str) -> bool:
    群号值 = int(群号)
    用户QQ值 = int(用户QQ)
    踢出方法 = getattr(bot, "set_group_kick", None)
    if callable(踢出方法):
        await 踢出方法(group_id=群号值, user_id=用户QQ值, reject_add_request=False)
        return True

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        await 调用动作("set_group_kick", group_id=群号值, user_id=用户QQ值, reject_add_request=False)
        return True

    raise RuntimeError("当前 bot 没有 set_group_kick 踢出接口")
