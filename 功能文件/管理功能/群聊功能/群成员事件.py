from __future__ import annotations

from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


群成员加入事件标记 = "mantou_group_member_add"


def _读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名, 默认值)
    return getattr(对象, 字段名, 默认值)


def _提取群成员加入数据(event: Any) -> dict[str, Any] | None:
    候选对象 = (
        event,
        _读取字段(event, "message_obj"),
        _读取字段(event, "message"),
    )
    for 候选对象项 in 候选对象:
        原始消息 = _读取字段(候选对象项, "raw_message")
        原始数据 = _读取字段(原始消息, "raw_data")
        if not isinstance(原始数据, dict):
            continue
        if 原始数据.get(群成员加入事件标记) is not True:
            continue
        事件数据 = 原始数据.get("group_member_add")
        return dict(事件数据) if isinstance(事件数据, dict) else {}
    return None


async def 处理群成员加入事件(event: Any) -> bool:
    """消费 QQ 官方 GROUP_MEMBER_ADD 内部事件，保留后续群聊功能的扩展入口。"""
    事件数据 = _提取群成员加入数据(event)
    if 事件数据 is None:
        return False

    群号 = str(事件数据.get("group_openid") or "").strip()
    成员 = str(事件数据.get("member_openid") or "").strip()
    有跨应用用户标识 = bool(str(事件数据.get("user_openid") or "").strip())
    if not 群号 or not 成员:
        logger.warning(
            "QQ官方群成员加入事件无效：has_group=%s, has_member=%s",
            bool(群号),
            bool(成员),
        )
        return True

    logger.info(
        "QQ官方群成员加入：group_openid=%s, member_openid=%s, has_user_openid=%s",
        群号,
        成员,
        有跨应用用户标识,
    )
    return True
