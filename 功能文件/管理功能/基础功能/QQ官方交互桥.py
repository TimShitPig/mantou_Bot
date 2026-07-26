from __future__ import annotations

import inspect
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


帮助回调前缀 = "帮助回调:"


def _读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名, 默认值)
    return getattr(对象, 字段名, 默认值)


def _提取按钮数据(交互: Any) -> str:
    数据 = _读取字段(交互, "data")
    已解析 = _读取字段(数据, "resolved")
    值 = _读取字段(已解析, "button_data")
    if 值 is None:
        值 = _读取字段(数据, "button_data")
    return str(值 or "").strip()


def _是否帮助回调(数据: str) -> bool:
    数据 = str(数据 or "").strip()
    return 数据.startswith(帮助回调前缀) and len(数据) > len(帮助回调前缀)


def _获取最近可回复消息ID(平台: Any, 会话标识: str) -> str | None:
    """互动 ID 不是消息 ID；群聊仅复用当前会话最近的真实消息 ID。"""
    缓存 = _读取字段(平台, "_session_last_message_id", {})
    if not isinstance(缓存, dict):
        return None
    消息ID = str(缓存.get(会话标识) or "").strip()
    return 消息ID or None


async def _回应交互(客户端: Any, 交互: Any, 状态码: int = 0) -> None:
    交互编号 = str(_读取字段(交互, "id") or "").strip()
    if not 交互编号:
        return
    接口 = _读取字段(交互, "_api") or _读取字段(客户端, "api")
    方法 = getattr(接口, "on_interaction_result", None)
    if not callable(方法):
        return
    try:
        结果 = 方法(交互编号, int(状态码))
        if inspect.isawaitable(结果):
            await 结果
    except Exception as 异常:
        logger.warning(f"QQ官方帮助回调回应失败：id={交互编号}, error={异常}")


async def _投递帮助回调(客户端: Any, 交互: Any, 数据: str, 适配器模块: Any) -> None:
    """把原生回调包装成 AstrBot 内部消息，交由 main 的帮助回调分发处理。"""
    平台 = _读取字段(客户端, "platform")
    if 平台 is None:
        raise RuntimeError("未找到QQ官方平台实例")

    群号 = str(_读取字段(交互, "group_openid") or "").strip()
    用户 = str(
        _读取字段(交互, "group_member_openid")
        or _读取字段(交互, "user_openid")
        or ""
    ).strip()
    if not 用户:
        raise RuntimeError("互动事件缺少用户标识")

    交互编号 = str(_读取字段(交互, "id") or _读取字段(交互, "event_id") or "").strip()
    原始数据: dict[str, Any] = {
        "id": 交互编号,
        "content": 数据,
        "attachments": [],
        "mantou_help_callback": True,
        "interaction_id": 交互编号,
        "interaction": {
            "id": 交互编号,
            "data": {"resolved": {"button_data": 数据}},
        },
    }
    事件编号 = _读取字段(交互, "event_id")
    消息类型 = _读取字段(适配器模块, "MessageType")

    if 群号:
        原始数据["group_openid"] = 群号
        原始数据["author"] = {"member_openid": 用户, "username": ""}
        消息类 = _读取字段(适配器模块, "PatchedGroupMessage")
        if 消息类 is None:
            from botpy.message import GroupMessage as 消息类  # type: ignore

        原始消息 = 消息类(客户端.api, 事件编号, 原始数据)
        解析结果 = await 平台._parse_from_qqofficial(
            原始消息,
            消息类型.GROUP_MESSAGE,
            force_group_mention=True,
        )
        解析结果.session_id = 群号
        解析结果.message_id = _获取最近可回复消息ID(平台, 群号)
        记录场景 = getattr(平台, "remember_session_scene", None)
        if callable(记录场景):
            记录场景(群号, "group")
    else:
        原始数据["author"] = {"user_openid": 用户, "username": ""}
        消息类 = _读取字段(适配器模块, "PatchedC2CMessage")
        if 消息类 is None:
            from botpy.message import C2CMessage as 消息类  # type: ignore

        原始消息 = 消息类(客户端.api, 事件编号, 原始数据)
        解析结果 = await 平台._parse_from_qqofficial(
            原始消息,
            消息类型.FRIEND_MESSAGE,
        )
        解析结果.session_id = 用户
        # 私聊主动发送不使用 interaction_id 作为 msg_id，避免无效或越权重试。
        解析结果.message_id = None
        记录场景 = getattr(平台, "remember_session_scene", None)
        if callable(记录场景):
            记录场景(用户, "friend")

    平台.commit_event(平台.create_event(解析结果))


def _开启互动事件(平台实例: Any) -> bool:
    意图 = _读取字段(平台实例, "intents")
    客户端 = _读取字段(平台实例, "client")
    if 意图 is None or 客户端 is None:
        return False
    try:
        意图.interaction = True
        客户端.intents = int(_读取字段(意图, "value", _读取字段(客户端, "intents", 0)))
        return True
    except Exception as 异常:
        logger.warning(f"QQ官方帮助回调订阅启用失败：error={异常}")
        return False


def 安装QQ官方帮助交互(上下文: Any = None) -> bool:
    """为 QQ 官方 WebSocket 适配器补齐帮助菜单原生回调。

    QQ 官方 `action.type=1` 通过 `INTERACTION_CREATE` 投递；AstrBot 默认适配器
    不会把该事件转换为普通消息，因此在此订阅并转入现有插件消息流水线。
    """
    try:
        from astrbot.core.platform.sources.qqofficial import qqofficial_platform_adapter as 适配器模块
    except Exception as 异常:
        logger.debug(f"QQ官方帮助回调桥未加载：error={异常}")
        return False

    适配器类 = getattr(适配器模块, "QQOfficialPlatformAdapter", None)
    客户端类 = getattr(适配器模块, "botClient", None)
    if 适配器类 is None or 客户端类 is None:
        return False

    if not getattr(适配器类, "_mantou_帮助互动已安装", False):
        原初始化 = 适配器类.__init__
        原互动回调 = getattr(客户端类, "on_interaction_create", None)

        def 新初始化(self: Any, *参数: Any, **关键字: Any) -> None:
            原初始化(self, *参数, **关键字)
            _开启互动事件(self)

        async def 新互动回调(self: Any, 交互: Any) -> Any:
            数据 = _提取按钮数据(交互)
            if not _是否帮助回调(数据):
                if callable(原互动回调):
                    结果 = 原互动回调(self, 交互)
                    if inspect.isawaitable(结果):
                        return await 结果
                    return 结果
                return None

            await _回应交互(self, 交互, 0)
            try:
                await _投递帮助回调(self, 交互, 数据, 适配器模块)
                logger.info(f"QQ官方帮助回调已投递：data={数据}")
            except Exception as 异常:
                logger.warning(f"QQ官方帮助回调投递失败：data={数据}, error={异常}")
            return None

        适配器类.__init__ = 新初始化
        客户端类.on_interaction_create = 新互动回调
        适配器类._mantou_帮助互动已安装 = True
        logger.info("QQ官方帮助回调桥已安装：已订阅 INTERACTION 事件")

    已启用数量 = 0
    平台管理器 = _读取字段(上下文, "platform_manager") if 上下文 is not None else None
    平台列表 = _读取字段(平台管理器, "platform_insts", []) or []
    for 平台实例 in 平台列表:
        try:
            元信息 = 平台实例.meta()
            名称 = str(_读取字段(元信息, "name") or "")
            标识 = str(_读取字段(元信息, "id") or "")
            if "QQ 机器人官方" not in 名称 and "qq_official" not in 标识:
                continue
            if _开启互动事件(平台实例):
                已启用数量 += 1
        except Exception:
            continue
    if 已启用数量:
        logger.info(f"QQ官方帮助回调桥已同步运行中适配器：count={已启用数量}")
    return True
