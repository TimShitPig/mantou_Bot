from __future__ import annotations

import inspect
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


帮助回调前缀 = "帮助回调:"
欢迎回调前缀 = "欢迎回调:"
群成员加入事件标记 = "mantou_group_member_add"


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


def _是否欢迎回调(数据: str) -> bool:
    数据 = str(数据 or "").strip()
    return 数据.startswith(欢迎回调前缀) and len(数据) > len(欢迎回调前缀)


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


def _注册群成员加入解析器(适配器模块: Any, 客户端: Any = None) -> bool:
    """补齐旧版 qq-botpy 未内置的 GROUP_MEMBER_ADD 网关解析器。"""
    连接状态类 = _读取字段(适配器模块, "ConnectionState")
    if 连接状态类 is None:
        try:
            from botpy.connection import ConnectionState as 连接状态类  # type: ignore
        except Exception as 异常:
            logger.warning(f"QQ官方群成员加入解析器加载失败：error={异常}")
            return False

    if not callable(getattr(连接状态类, "parse_group_member_add", None)):
        def 解析群成员加入(self: Any, 负载: Any) -> None:
            外层数据 = 负载 if isinstance(负载, dict) else {}
            事件数据 = 外层数据.get("d", {})
            if not isinstance(事件数据, dict):
                事件数据 = {}
            已整理数据 = dict(事件数据)
            事件编号 = 外层数据.get("id")
            if 事件编号 is not None:
                已整理数据["_mantou_event_id"] = 事件编号
            self._dispatch("group_member_add", 已整理数据)

        setattr(连接状态类, "parse_group_member_add", 解析群成员加入)

    if 客户端 is None:
        return True

    已同步 = False
    连接容器 = _读取字段(客户端, "_connection")
    候选连接 = (连接容器, _读取字段(连接容器, "state"))
    for 连接状态 in 候选连接:
        解析器表 = _读取字段(连接状态, "parsers")
        解析器 = getattr(连接状态, "parse_group_member_add", None)
        if isinstance(解析器表, dict) and callable(解析器):
            解析器表["group_member_add"] = 解析器
            已同步 = True
    return 已同步 or 连接容器 is None


def _开启群成员加入事件(平台实例: Any, 适配器模块: Any) -> bool:
    """同步已启用的官方群消息订阅与 GROUP_MEMBER_ADD 解析器。"""
    意图 = _读取字段(平台实例, "intents")
    客户端 = _读取字段(平台实例, "client")
    if 意图 is None or 客户端 is None:
        return False
    try:
        # GROUP_MEMBER_ADD 与官方群消息共用 GROUP_AND_C2C_EVENT Intent。
        # 未开启群消息接收的适配器保持原配置，不由插件代为改变平台订阅范围。
        if not bool(_读取字段(意图, "public_messages", False)):
            return False
        return _注册群成员加入解析器(适配器模块, 客户端)
    except Exception as 异常:
        logger.warning(f"QQ官方群成员加入事件同步失败：error={异常}")
        return False


def _提取群成员加入数据(原始事件: Any) -> dict[str, Any]:
    候选数据: list[dict[str, Any]] = []
    if isinstance(原始事件, dict):
        候选数据.append(原始事件)
    else:
        for 字段名 in ("raw_data", "data", "payload", "event"):
            值 = _读取字段(原始事件, 字段名)
            if isinstance(值, dict):
                候选数据.append(值)
        属性字典 = _读取字段(原始事件, "__dict__")
        if isinstance(属性字典, dict):
            候选数据.append(属性字典)

    展开数据: list[dict[str, Any]] = []
    for 数据 in 候选数据:
        展开数据.append(数据)
        内层数据 = 数据.get("d")
        if isinstance(内层数据, dict):
            展开数据.append(内层数据)

    结果: dict[str, Any] = {}
    for 字段名 in ("timestamp", "group_openid", "member_openid", "user_openid", "_mantou_event_id"):
        for 数据 in 展开数据:
            值 = 数据.get(字段名)
            if 值 is not None and str(值).strip():
                结果[字段名] = 值
                break
        if 字段名 not in 结果:
            值 = _读取字段(原始事件, 字段名)
            if 值 is not None and str(值).strip():
                结果[字段名] = 值
    return 结果


async def _投递群成员加入事件(客户端: Any, 原始事件: Any, 适配器模块: Any) -> None:
    """将官方成员加入事件包装为内部事件，避免混入普通消息解析。"""
    平台 = _读取字段(客户端, "platform")
    if 平台 is None:
        raise RuntimeError("未找到QQ官方平台实例")

    事件数据 = _提取群成员加入数据(原始事件)
    群号 = str(事件数据.get("group_openid") or "").strip()
    成员 = str(事件数据.get("member_openid") or "").strip()
    用户 = str(事件数据.get("user_openid") or "").strip()
    if not 群号 or not 成员:
        logger.warning(
            "QQ官方群成员加入事件缺少必要标识：has_group=%s, has_member=%s",
            bool(群号),
            bool(成员),
        )
        return

    时间戳 = str(事件数据.get("timestamp") or "")
    事件编号 = str(事件数据.get("_mantou_event_id") or "").strip()
    消息编号 = 事件编号 or f"group-member-add:{时间戳}:{成员}"
    原始数据: dict[str, Any] = {
        "id": 消息编号,
        "content": "",
        "attachments": [],
        "group_openid": 群号,
        "author": {
            "member_openid": 成员,
            "user_openid": 用户,
            "username": "",
        },
        群成员加入事件标记: True,
        "group_member_add": {
            "timestamp": 事件数据.get("timestamp"),
            "group_openid": 群号,
            "member_openid": 成员,
            "user_openid": 用户,
        },
    }
    消息类 = _读取字段(适配器模块, "PatchedGroupMessage")
    if 消息类 is None:
        from botpy.message import GroupMessage as 消息类  # type: ignore

    消息类型 = _读取字段(适配器模块, "MessageType")
    原始消息 = 消息类(客户端.api, 消息编号, 原始数据)
    解析结果 = await 平台._parse_from_qqofficial(
        原始消息,
        消息类型.GROUP_MESSAGE,
    )
    解析结果.group_id = 群号
    解析结果.session_id = 群号
    解析结果.message_id = None
    记录场景 = getattr(平台, "remember_session_scene", None)
    if callable(记录场景):
        记录场景(群号, "group")
    平台.commit_event(平台.create_event(解析结果))


def 安装QQ官方帮助交互(上下文: Any = None) -> bool:
    """为 QQ 官方 WebSocket 适配器补齐原生交互和群成员加入事件。

    QQ 官方 `action.type=1` 通过 `INTERACTION_CREATE` 投递；AstrBot 默认适配器
    与旧版 qq-botpy 都不会完整转发该事件和 `GROUP_MEMBER_ADD`，因此在此转入
    现有插件消息流水线。
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

    _注册群成员加入解析器(适配器模块)

    if not getattr(适配器类, "_mantou_帮助互动已安装", False):
        原初始化 = 适配器类.__init__
        原互动回调 = getattr(客户端类, "on_interaction_create", None)

        def 新初始化(self: Any, *参数: Any, **关键字: Any) -> None:
            原初始化(self, *参数, **关键字)
            _开启互动事件(self)

        async def 新互动回调(self: Any, 交互: Any) -> Any:
            数据 = _提取按钮数据(交互)
            if not (_是否帮助回调(数据) or _是否欢迎回调(数据)):
                if callable(原互动回调):
                    结果 = 原互动回调(self, 交互)
                    if inspect.isawaitable(结果):
                        return await 结果
                    return 结果
                return None

            await _回应交互(self, 交互, 0)
            try:
                await _投递帮助回调(self, 交互, 数据, 适配器模块)
                logger.info(f"QQ官方互动回调已投递：data={数据}")
            except Exception as 异常:
                logger.warning(f"QQ官方互动回调投递失败：data={数据}, error={异常}")
            return None

        适配器类.__init__ = 新初始化
        客户端类.on_interaction_create = 新互动回调
        适配器类._mantou_帮助互动已安装 = True
        logger.info("QQ官方帮助回调桥已安装：已订阅 INTERACTION 事件")

    if not getattr(适配器类, "_mantou_群成员加入已安装", False):
        原初始化 = 适配器类.__init__
        原成员加入回调 = getattr(客户端类, "on_group_member_add", None)

        def 新成员加入初始化(self: Any, *参数: Any, **关键字: Any) -> None:
            _注册群成员加入解析器(适配器模块)
            原初始化(self, *参数, **关键字)
            _开启群成员加入事件(self, 适配器模块)

        async def 新成员加入回调(self: Any, 原始事件: Any) -> Any:
            try:
                await _投递群成员加入事件(self, 原始事件, 适配器模块)
            except Exception as 异常:
                logger.warning(f"QQ官方群成员加入事件投递失败：error={异常}")
            if callable(原成员加入回调):
                结果 = 原成员加入回调(self, 原始事件)
                if inspect.isawaitable(结果):
                    return await 结果
                return 结果
            return None

        适配器类.__init__ = 新成员加入初始化
        客户端类.on_group_member_add = 新成员加入回调
        适配器类._mantou_群成员加入已安装 = True
        logger.info("QQ官方群成员加入桥已安装：已接入 GROUP_MEMBER_ADD")

    已启用帮助数量 = 0
    已启用成员加入数量 = 0
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
                已启用帮助数量 += 1
            if _开启群成员加入事件(平台实例, 适配器模块):
                已启用成员加入数量 += 1
        except Exception:
            continue
    if 已启用帮助数量 or 已启用成员加入数量:
        logger.info(
            "QQ官方群事件桥已同步运行中适配器："
            f"interaction={已启用帮助数量}, group_member_add={已启用成员加入数量}",
        )
    return True
