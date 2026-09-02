from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


帮助回调前缀 = "帮助回调:"
欢迎回调前缀 = "欢迎回调:"
群成员加入事件标记 = "mantou_group_member_add"
群成员事件意图位 = 1 << 24
群机器人退出事件意图位 = 1 << 25
群成员加入桥版本 = 8
QQ官方语音Silk补丁版本 = 1
欢迎诊断事件名 = {"group_member_add", "group_add_robot", "group_del_robot"}
当前插件上下文: Any = None
平台同步任务: asyncio.Task | None = None
平台同步已完成 = False


def _读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名, 默认值)
    return getattr(对象, 字段名, 默认值)


def _获取平台实例列表(上下文: Any) -> list[Any]:
    平台管理器 = _读取字段(上下文, "platform_manager") if 上下文 is not None else None
    平台列表 = _读取字段(平台管理器, "platform_insts", None)
    if isinstance(平台列表, (list, tuple)):
        return list(平台列表)
    获取实例 = getattr(平台管理器, "get_insts", None)
    if not callable(获取实例):
        return []
    try:
        平台列表 = 获取实例()
    except Exception:
        return []
    return list(平台列表) if isinstance(平台列表, (list, tuple)) else []


def _是QQ官方平台(平台实例: Any) -> bool:
    try:
        元信息 = 平台实例.meta()
        名称 = str(_读取字段(元信息, "name") or "").strip().casefold()
        标识 = str(_读取字段(元信息, "id") or "").strip().casefold()
        配置 = _读取字段(平台实例, "config")
        类型 = str(_读取字段(配置, "type") or "").strip().casefold()
        return (
            名称 == "qq_official"
            or 标识 == "qq_official"
            or 类型 == "qq_official"
            or "qq 机器人官方" in 名称
        )
    except Exception:
        return False


def _已加载QQ官方平台(上下文: Any) -> bool:
    return any(_是QQ官方平台(平台实例) for 平台实例 in _获取平台实例列表(上下文))


def 安装QQ官方语音Silk兼容补丁() -> bool:
    """兼容 QQ 语音的 0x03 前缀 Tencent SILK 数据。"""
    try:
        from astrbot.core.utils import media_utils, tencent_record_helper
    except Exception as 异常:
        logger.warning("QQ官方语音兼容补丁加载失败：error_type=%s", type(异常).__name__)
        return False

    if getattr(media_utils, "_mantou_qq_silk_patch_version", 0) == QQ官方语音Silk补丁版本:
        return True
    原始音频魔数探测 = getattr(media_utils, "_mantou_原始音频魔数探测", None)
    if not callable(原始音频魔数探测):
        原始音频魔数探测 = getattr(media_utils, "_get_audio_magic_type", None)
    原始腾讯Silk解码 = getattr(tencent_record_helper, "_mantou_原始腾讯Silk解码", None)
    if not callable(原始腾讯Silk解码):
        原始腾讯Silk解码 = getattr(tencent_record_helper, "tencent_silk_to_wav", None)
    if not callable(原始音频魔数探测) or not callable(原始腾讯Silk解码):
        logger.warning("QQ官方语音兼容补丁安装失败：媒体工具接口不可用")
        return False

    setattr(media_utils, "_mantou_原始音频魔数探测", 原始音频魔数探测)
    setattr(tencent_record_helper, "_mantou_原始腾讯Silk解码", 原始腾讯Silk解码)

    def 新音频魔数探测(音频路径: str) -> str:
        try:
            with open(音频路径, "rb") as 文件:
                头部 = 文件.read(12)
            if 头部.startswith(b"\x03#!SILK_V3"):
                return "silk"
        except OSError:
            pass
        return 原始音频魔数探测(音频路径)

    async def 新腾讯Silk到Wav(Silk路径: str, 输出路径: str) -> str:
        def 读取Silk数据() -> bytes:
            with open(Silk路径, "rb") as 文件:
                return 文件.read()

        try:
            数据 = await asyncio.to_thread(读取Silk数据)
        except OSError:
            return await 原始腾讯Silk解码(Silk路径, 输出路径)
        if not 数据.startswith(b"\x03#!SILK_V3"):
            return await 原始腾讯Silk解码(Silk路径, 输出路径)

        def 解码并写入() -> str:
            from io import BytesIO
            import wave

            import pysilk

            输出 = BytesIO()
            pysilk.decode(BytesIO(数据[1:]), 输出, 24000)
            输出.seek(0)
            with wave.open(输出路径, "wb") as WAV文件:
                WAV文件.setnchannels(1)
                WAV文件.setsampwidth(2)
                WAV文件.setframerate(24000)
                WAV文件.writeframes(输出.read())
            return str(输出路径)

        return await asyncio.to_thread(解码并写入)

    media_utils._get_audio_magic_type = 新音频魔数探测
    media_utils.tencent_silk_to_wav = 新腾讯Silk到Wav
    tencent_record_helper.tencent_silk_to_wav = 新腾讯Silk到Wav
    media_utils._mantou_qq_silk_patch_version = QQ官方语音Silk补丁版本
    logger.info("QQ官方语音兼容补丁已安装：支持 0x03 Tencent SILK")
    return True


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
        _读取字段(交互, "group_member_openid") or _读取字段(交互, "user_openid") or ""
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


def _群成员加入意图已启用(意图: Any, 客户端: Any) -> bool:
    for 值 in (_读取字段(意图, "value"), _读取字段(客户端, "intents")):
        try:
            if int(值) & 群成员事件意图位:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _启用群成员加入意图(意图: Any, 客户端: Any) -> tuple[bool, int | None, int | None]:
    """确保登录前后的客户端都带上官方 GROUP_MEMBER_EVENT。"""
    原意图值 = _读取字段(意图, "value")
    if 原意图值 is None:
        原意图值 = _读取字段(客户端, "intents")
    try:
        原值 = int(原意图值 or 0)
    except (TypeError, ValueError):
        return False, None, None
    目标值 = 原值 | 群成员事件意图位
    try:
        if 意图 is not None:
            意图.value = 目标值
        if 客户端 is not None:
            客户端.intents = 目标值
    except (AttributeError, TypeError, ValueError):
        return False, 原值, None
    return True, 原值, 目标值


def _启用群机器人退出意图(意图: Any, 客户端: Any) -> tuple[bool, int | None, int | None]:
    """确保登录前后的客户端带上官方 GROUP_AND_C2C_EVENT。"""
    原意图值 = _读取字段(意图, "value")
    if 原意图值 is None:
        原意图值 = _读取字段(客户端, "intents")
    try:
        原值 = int(原意图值 or 0)
    except (TypeError, ValueError):
        return False, None, None
    目标值 = 原值 | 群机器人退出事件意图位
    try:
        if 意图 is not None:
            意图.value = 目标值
        if 客户端 is not None:
            客户端.intents = 目标值
    except (AttributeError, TypeError, ValueError):
        return False, 原值, None
    return True, 原值, 目标值


def _解析器表包含(容器: Any, 解析器名称: str) -> bool:
    for 字段名 in ("parsers", "parser", "_parsers", "_parser"):
        解析器表 = _读取字段(容器, 字段名)
        if isinstance(解析器表, dict) and callable(解析器表.get(解析器名称)):
            return True
    return False


def _记录群成员加入诊断(
    阶段: str,
    适配器模块: Any,
    平台实例: Any = None,
    客户端: Any = None,
) -> None:
    """只记录订阅和解析器状态，不记录事件原文或账号凭据。"""
    if 客户端 is None and 平台实例 is not None:
        客户端 = _读取字段(平台实例, "client")
    意图 = _读取字段(平台实例, "intents") if 平台实例 is not None else None
    连接 = _读取字段(客户端, "_connection")
    连接状态 = _读取字段(连接, "state")
    连接状态类 = _读取字段(适配器模块, "ConnectionState")
    客户端类 = _读取字段(适配器模块, "botClient")
    try:
        意图值 = _读取字段(意图, "value")
        客户端意图值 = _读取字段(客户端, "intents")
        意图值文本 = str(int(意图值)) if 意图值 is not None else "None"
        客户端意图文本 = str(int(客户端意图值)) if 客户端意图值 is not None else "None"
    except (TypeError, ValueError):
        意图值文本 = "invalid"
        客户端意图文本 = "invalid"
    logger.info(
        "QQ官方群欢迎诊断：stage=%s, group_member_event=%s, intent_value=%s, "
        "client_intents=%s, connection=%s, parser_class=%s, "
        "parser_state=%s, parser_connection=%s, member_callback=%s, "
        "robot_callback=%s",
        阶段,
        _群成员加入意图已启用(意图, 客户端) if 意图 is not None else False,
        意图值文本,
        客户端意图文本,
        连接 is not None,
        callable(getattr(连接状态类, "parse_group_member_add", None)),
        _解析器表包含(连接状态, "group_member_add"),
        _解析器表包含(连接, "group_member_add"),
        callable(getattr(客户端类, "on_group_member_add", None)),
        callable(getattr(客户端类, "on_group_add_robot", None)),
    )


def _事件字段状态(原始事件: Any) -> str:
    事件数据 = _提取群成员加入数据(原始事件)
    return (
        f"has_group={bool(事件数据.get('group_openid'))}, "
        f"has_member={bool(事件数据.get('member_openid'))}, "
        f"has_operator={bool(事件数据.get('op_member_openid'))}, "
        f"has_user={bool(事件数据.get('user_openid'))}, "
        f"has_timestamp={bool(事件数据.get('timestamp'))}"
    )


def _写入群聊事件解析器(容器: Any, 解析器名称: str, 解析器: Any) -> bool:
    已写入 = False
    for 字段名 in ("parsers", "parser", "_parsers", "_parser"):
        解析器表 = _读取字段(容器, 字段名)
        if isinstance(解析器表, dict):
            解析器表[解析器名称] = 解析器
            已写入 = True
    return 已写入


def _注册群成员加入解析器(适配器模块: Any, 客户端: Any = None) -> bool:
    """补齐旧版 qq-botpy 未内置的官方群聊事件解析器。"""
    连接状态类 = _读取字段(适配器模块, "ConnectionState")
    if 连接状态类 is None:
        try:
            from botpy.connection import ConnectionState as 连接状态类  # type: ignore
        except Exception as 异常:
            logger.warning(f"QQ官方群成员加入解析器加载失败：error={异常}")
            return False

    def 安装解析器(解析器名称: str) -> None:
        方法名 = "parse_" + 解析器名称
        if callable(getattr(连接状态类, 方法名, None)):
            return

        def 解析官方群聊事件(self: Any, 负载: Any) -> None:
            外层数据 = 负载 if isinstance(负载, dict) else {}
            事件数据 = 外层数据.get("d", {})
            if not isinstance(事件数据, dict):
                事件数据 = {}
            已整理数据 = dict(事件数据)
            事件编号 = 外层数据.get("id")
            if 事件编号 is not None:
                已整理数据["_mantou_event_id"] = 事件编号
            logger.info(
                "QQ官方群欢迎诊断：stage=parser_dispatch, event=%s, %s",
                解析器名称,
                _事件字段状态(已整理数据),
            )
            self._dispatch(解析器名称, 已整理数据)

        setattr(连接状态类, 方法名, 解析官方群聊事件)

    # QQ 官方文档中的事件名，分别覆盖普通成员加入和机器人被加入群聊。
    安装解析器("group_member_add")
    安装解析器("group_add_robot")
    安装解析器("group_del_robot")

    if 客户端 is None:
        return True

    连接容器 = _读取字段(客户端, "_connection")
    if 连接容器 is None:
        return True

    连接状态 = _读取字段(连接容器, "state")
    已同步 = False
    for 解析器名称 in ("group_member_add", "group_add_robot", "group_del_robot"):
        解析器 = getattr(连接状态, "parse_" + 解析器名称, None)
        if not callable(解析器):
            解析器 = getattr(连接容器, "parse_" + 解析器名称, None)
        if not callable(解析器):
            continue
        已同步 = _写入群聊事件解析器(连接容器, 解析器名称, 解析器) or 已同步
        已同步 = _写入群聊事件解析器(连接状态, 解析器名称, 解析器) or 已同步
    return 已同步


def _开启群成员加入事件(平台实例: Any, 适配器模块: Any) -> bool:
    """同步 GROUP_MEMBER_ADD 解析器，并记录网关订阅是否实际开启。"""
    意图 = _读取字段(平台实例, "intents")
    客户端 = _读取字段(平台实例, "client")
    if 意图 is None or 客户端 is None:
        return False
    try:
        解析器已注册 = _注册群成员加入解析器(适配器模块, 客户端)
        try:
            平台意图值 = int(_读取字段(意图, "value") or 0)
        except (TypeError, ValueError):
            平台意图值 = 0
        if not (平台意图值 & 群成员事件意图位):
            已启用, 原意图值, 新意图值 = _启用群成员加入意图(意图, 客户端)
            意图已开启 = 已启用
            logger.info(
                "QQ官方群欢迎诊断：stage=intent_enable, success=%s, before=%s, after=%s, "
                "restart_required=%s",
                意图已开启,
                原意图值 if 原意图值 is not None else "None",
                新意图值 if 新意图值 is not None else "None",
                _读取字段(客户端, "_connection") is not None,
            )
        else:
            意图已开启 = _群成员加入意图已启用(意图, 客户端)
        try:
            当前意图值 = int(_读取字段(意图, "value") or _读取字段(客户端, "intents") or 0)
        except (TypeError, ValueError):
            当前意图值 = 0
        if not (当前意图值 & 群机器人退出事件意图位):
            退出意图已开启, _, _ = _启用群机器人退出意图(意图, 客户端)
        else:
            退出意图已开启 = True
        _记录群成员加入诊断(
            "listener_sync",
            适配器模块,
            平台实例,
            客户端,
        )
        logger.info(
            "QQ官方群成员欢迎监听状态：group_member_event=%s, group_del_robot_event=%s, parser_registered=%s, connected=%s",
            意图已开启,
            退出意图已开启,
            解析器已注册,
            _读取字段(客户端, "_connection") is not None,
        )
        if not 意图已开启 or not 退出意图已开启:
            logger.warning(
                "QQ官方群成员事件未完整订阅：请启用群成员与群机器人退出事件接收后重启适配器"
            )
        return 意图已开启 and 退出意图已开启 and 解析器已注册
    except Exception as 异常:
        logger.warning(
            "QQ官方群成员加入事件同步失败：error_type=%s",
            type(异常).__name__,
        )
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
    for 字段名 in (
        "timestamp",
        "group_openid",
        "member_openid",
        "op_member_openid",
        "user_openid",
        "_mantou_event_id",
    ):
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
    logger.info(
        "QQ官方群欢迎诊断：stage=delivery, event_type=%s, %s",
        "GROUP_MEMBER_ADD" if 事件数据.get("member_openid") else "GROUP_ADD_ROBOT",
        _事件字段状态(原始事件),
    )
    群号 = str(事件数据.get("group_openid") or "").strip()
    成员 = str(
        事件数据.get("member_openid") or 事件数据.get("op_member_openid") or ""
    ).strip()
    用户 = str(事件数据.get("user_openid") or "").strip()
    if not 群号 or not 成员:
        logger.warning(
            "QQ官方群成员加入事件缺少必要标识：has_group=%s, has_member=%s",
            bool(群号),
            bool(成员),
        )
        return

    if 用户:
        try:
            from 功能文件.管理功能.群聊功能.群列表工具 import 记录官方群成员映射

            记录官方群成员映射(群号, 用户, 成员)
        except Exception as 异常:
            logger.debug(
                "QQ官方群成员映射记录跳过：error_type=%s",
                type(异常).__name__,
            )

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
    内部事件 = 平台.create_event(解析结果)
    from 功能文件.管理功能.群聊功能 import 群成员事件

    发送成功 = await 群成员事件.发送群成员加入欢迎(内部事件, 成员)
    logger.info(
        "QQ官方群欢迎诊断：stage=send_result, sent=%s, has_group=%s, has_member=%s",
        bool(发送成功),
        bool(群号),
        bool(成员),
    )
    if not 发送成功:
        raise RuntimeError("欢迎消息发送失败")
    logger.info("QQ官方群成员欢迎消息已发送：group_openid=%s", 群号)


def _安装登录后解析器同步(客户端类: Any, 适配器模块: Any) -> None:
    if getattr(客户端类, "_mantou_群成员登录同步已安装", False):
        return
    原登录方法 = getattr(客户端类, "_bot_login", None)
    if not callable(原登录方法):
        logger.warning("QQ官方群欢迎诊断：stage=login_hook, installed=False")
        return

    async def 新登录方法(self: Any, *参数: Any, **关键字: Any) -> Any:
        try:
            平台 = _读取字段(self, "platform")
            _启用群成员加入意图(_读取字段(平台, "intents"), self)
            结果 = 原登录方法(self, *参数, **关键字)
            if inspect.isawaitable(结果):
                结果 = await 结果
        except Exception as 异常:
            logger.warning(
                "QQ官方群欢迎诊断：stage=login, success=False, error_type=%s",
                type(异常).__name__,
            )
            raise
        _注册群成员加入解析器(适配器模块, self)
        _记录群成员加入诊断(
            "post_login",
            适配器模块,
            _读取字段(self, "platform"),
            self,
        )
        return 结果

    客户端类._bot_login = 新登录方法
    客户端类._mantou_群成员登录同步已安装 = True


def _安装网关鉴权订阅(适配器模块: Any) -> None:
    """在每条新 WebSocket 会话发送 IDENTIFY 前校正群成员事件订阅位。"""
    网关类 = _读取字段(适配器模块, "ManagedBotWebSocket")
    if 网关类 is None:
        网关类 = _读取字段(适配器模块, "BotWebSocket")
    if 网关类 is None:
        logger.warning("QQ官方群欢迎诊断：stage=ws_identify_hook, installed=False")
        return
    if getattr(网关类, "_mantou_群成员鉴权订阅已安装", False):
        return
    原鉴权方法 = getattr(网关类, "ws_identify", None)
    if not callable(原鉴权方法):
        logger.warning("QQ官方群欢迎诊断：stage=ws_identify_hook, installed=False")
        return

    async def 新鉴权方法(self: Any, *参数: Any, **关键字: Any) -> Any:
        会话 = _读取字段(self, "_session")
        原意图值 = _读取字段(会话, "intent") if isinstance(会话, dict) else None
        try:
            原值 = int(原意图值 or 0)
        except (TypeError, ValueError):
            原值 = 0
        新值 = 原值 | 群成员事件意图位
        if isinstance(会话, dict):
            会话["intent"] = 新值
        logger.info(
            "QQ官方群欢迎诊断：stage=ws_identify, group_member_event=%s, intent=%s",
            bool(新值 & 群成员事件意图位),
            新值,
        )
        结果 = 原鉴权方法(self, *参数, **关键字)
        if inspect.isawaitable(结果):
            return await 结果
        return 结果

    网关类.ws_identify = 新鉴权方法
    网关类._mantou_群成员鉴权订阅已安装 = True
    logger.info("QQ官方群欢迎诊断：stage=ws_identify_hook, installed=True")


def _安装网关接收诊断(适配器模块: Any) -> None:
    """记录事件是否到达 WebSocket 及其 parser 命中状态。"""
    网关类 = _读取字段(适配器模块, "ManagedBotWebSocket")
    if 网关类 is None:
        网关类 = _读取字段(适配器模块, "BotWebSocket")
    if 网关类 is None:
        logger.warning("QQ官方群欢迎诊断：stage=ws_receive_hook, installed=False")
        return
    if getattr(网关类, "_mantou_群成员网关接收诊断已安装", False):
        return
    原接收方法 = getattr(网关类, "on_message", None)
    if not callable(原接收方法):
        logger.warning("QQ官方群欢迎诊断：stage=ws_receive_hook, installed=False")
        return

    async def 新接收方法(self: Any, websocket: Any, message: Any) -> Any:
        事件名 = ""
        try:
            文本 = message
            if isinstance(文本, (bytes, bytearray)):
                文本 = 文本.decode("utf-8", errors="ignore")
            负载 = json.loads(文本) if isinstance(文本, str) else {}
            事件名 = str(负载.get("t") or "").strip().lower()
            if 事件名 in 欢迎诊断事件名:
                连接 = _读取字段(self, "_connection")
                解析器表 = _读取字段(self, "_parser", {})
                会话 = _读取字段(self, "_session", {})
                意图值 = _读取字段(会话, "intent")
                try:
                    群成员事件已订阅 = bool(int(意图值) & 群成员事件意图位)
                except (TypeError, ValueError):
                    群成员事件已订阅 = False
                logger.info(
                    "QQ官方群欢迎诊断：stage=ws_receive, event=%s, parser=%s, "
                    "group_member_event=%s, connection_parser=%s, intent=%s",
                    事件名,
                    isinstance(解析器表, dict) and callable(解析器表.get(事件名)),
                    群成员事件已订阅,
                    isinstance(_读取字段(连接, "parser"), dict),
                    意图值 if 意图值 is not None else "None",
                )
        except Exception:
            pass
        return await 原接收方法(self, websocket, message)

    网关类.on_message = 新接收方法
    网关类._mantou_群成员网关接收诊断已安装 = True
    logger.info("QQ官方群欢迎诊断：stage=ws_receive_hook, installed=True")


def _安装网关分发诊断(客户端类: Any) -> None:
    if getattr(客户端类, "_mantou_群成员网关诊断已安装", False):
        return
    原分发方法 = getattr(客户端类, "ws_dispatch", None)
    if not callable(原分发方法):
        logger.warning("QQ官方群欢迎诊断：stage=ws_dispatch_hook, installed=False")
        return

    def 新分发方法(self: Any, 事件名: Any, *参数: Any, **关键字: Any) -> Any:
        规范事件名 = str(事件名 or "").strip().lower()
        if 规范事件名 in {"group_member_add", "group_add_robot"}:
            连接 = _读取字段(self, "_connection")
            负载 = 参数[0] if 参数 else None
            logger.info(
                "QQ官方群欢迎诊断：stage=ws_dispatch, event=%s, parser=%s, %s",
                规范事件名,
                _解析器表包含(连接, 规范事件名),
                _事件字段状态(负载),
            )
        return 原分发方法(self, 事件名, *参数, **关键字)

    客户端类.ws_dispatch = 新分发方法
    客户端类._mantou_群成员网关诊断已安装 = True


def _移除旧群成员欢迎回调(客户端类: Any, 适配器类: Any) -> None:
    """热重载时清除旧版本注入的新人欢迎回调。"""
    已移除 = False
    for 回调名称 in ("on_group_member_add", "on_group_add_robot"):
        回调 = getattr(客户端类, 回调名称, None)
        if getattr(回调, "__module__", "") != __name__:
            continue
        try:
            delattr(客户端类, 回调名称)
            已移除 = True
        except AttributeError:
            pass
    if getattr(适配器类, "_mantou_群成员加入已安装", False):
        try:
            delattr(适配器类, "_mantou_群成员加入已安装")
            已移除 = True
        except AttributeError:
            pass
    if getattr(适配器类, "_mantou_群成员加入桥版本", 0):
        try:
            delattr(适配器类, "_mantou_群成员加入桥版本")
            已移除 = True
        except AttributeError:
            pass
    if 已移除:
        logger.info("QQ官方旧版新人欢迎回调已移除")


def 安装QQ官方帮助交互(上下文: Any = None) -> bool:
    """为 QQ 官方 WebSocket 适配器补齐原生帮助交互。

    QQ 官方 `action.type=1` 通过 `INTERACTION_CREATE` 投递；AstrBot 默认适配器
    与旧版 qq-botpy 的回调需要在此转入现有插件消息流水线。
    """
    global 当前插件上下文
    if 上下文 is not None:
        当前插件上下文 = 上下文
    try:
        from astrbot.core.platform.sources.qqofficial import (
            qqofficial_platform_adapter as 适配器模块,
        )
    except Exception as 异常:
        logger.warning("QQ官方帮助回调桥加载失败：error_type=%s", type(异常).__name__)
        return False

    安装QQ官方语音Silk兼容补丁()

    适配器类 = getattr(适配器模块, "QQOfficialPlatformAdapter", None)
    客户端类 = getattr(适配器模块, "botClient", None)
    if 适配器类 is None or 客户端类 is None:
        logger.warning("QQ官方帮助回调桥加载失败：适配器类或客户端类不存在")
        return False

    _移除旧群成员欢迎回调(客户端类, 适配器类)
    if not getattr(适配器类, "_mantou_帮助互动已安装", False):
        原互动回调 = getattr(客户端类, "on_interaction_create", None)

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

        客户端类.on_interaction_create = 新互动回调
        适配器类._mantou_帮助互动已安装 = True
        logger.info("QQ官方帮助回调桥已安装：已订阅 INTERACTION 事件")

    if getattr(适配器类, "_mantou_群成员加入桥版本", 0) != 群成员加入桥版本:
        原成员加入回调 = getattr(客户端类, "on_group_member_add", None)
        原机器人入群回调 = getattr(客户端类, "on_group_add_robot", None)
        原机器人退群回调 = getattr(客户端类, "on_group_del_robot", None)
        if getattr(原成员加入回调, "__module__", "") == __name__:
            原成员加入回调 = None
        if getattr(原机器人入群回调, "__module__", "") == __name__:
            原机器人入群回调 = None
        if getattr(原机器人退群回调, "__module__", "") == __name__:
            原机器人退群回调 = None

        async def 新成员加入回调(self: Any, 原始事件: Any) -> Any:
            logger.info(
                "QQ官方群欢迎诊断：stage=callback_enter, event=GROUP_MEMBER_ADD, %s",
                _事件字段状态(原始事件),
            )
            try:
                await _投递群成员加入事件(self, 原始事件, 适配器模块)
            except Exception as 异常:
                logger.warning(
                    "QQ官方群成员加入事件投递失败：error_type=%s",
                    type(异常).__name__,
                )
            if callable(原成员加入回调):
                结果 = 原成员加入回调(self, 原始事件)
                if inspect.isawaitable(结果):
                    return await 结果
                return 结果
            return None

        async def 新机器人入群回调(self: Any, 原始事件: Any) -> Any:
            logger.info(
                "QQ官方群欢迎诊断：stage=callback_enter, event=GROUP_ADD_ROBOT, %s",
                _事件字段状态(原始事件),
            )
            try:
                from 功能文件.管理功能.基础功能 import 消息记录

                事件数据 = _提取群成员加入数据(原始事件)
                群号 = str(事件数据.get("group_openid") or "").strip()
                if 群号:
                    appid = str(
                        _读取字段(self, "appid")
                        or _读取字段(_读取字段(self, "platform"), "appid")
                        or ""
                    ).strip()
                    消息记录.标记群机器人已加入(群号, appid)
                await _投递群成员加入事件(self, 原始事件, 适配器模块)
            except Exception as 异常:
                logger.warning(
                    "QQ官方机器人入群欢迎投递失败：error_type=%s",
                    type(异常).__name__,
                )
            if callable(原机器人入群回调):
                结果 = 原机器人入群回调(self, 原始事件)
                if inspect.isawaitable(结果):
                    return await 结果
                return 结果
            return None

        async def 新机器人退群回调(self: Any, 原始事件: Any) -> Any:
            logger.info(
                "QQ官方群成员状态：stage=callback_enter, event=GROUP_DEL_ROBOT, %s",
                _事件字段状态(原始事件),
            )
            try:
                from 功能文件.管理功能.基础功能 import 消息记录

                事件数据 = _提取群成员加入数据(原始事件)
                群号 = str(事件数据.get("group_openid") or "").strip()
                if 群号:
                    appid = str(
                        _读取字段(self, "appid")
                        or _读取字段(_读取字段(self, "platform"), "appid")
                        or ""
                    ).strip()
                    消息记录.标记群机器人已移除(群号, appid)
            except Exception as 异常:
                logger.warning(
                    "QQ官方群机器人退出状态记录失败：error_type=%s",
                    type(异常).__name__,
                )
            if callable(原机器人退群回调):
                结果 = 原机器人退群回调(self, 原始事件)
                if inspect.isawaitable(结果):
                    return await 结果
                return 结果
            return None

        客户端类.on_group_member_add = 新成员加入回调
        客户端类.on_group_add_robot = 新机器人入群回调
        客户端类.on_group_del_robot = 新机器人退群回调
        适配器类._mantou_群成员加入已安装 = True
        适配器类._mantou_群成员加入桥版本 = 群成员加入桥版本
        logger.info("QQ官方群成员加入桥已安装：已接入 GROUP_MEMBER_ADD")

    已启用帮助数量 = 0
    已启用成员加入数量 = 0
    找到官方适配器 = False
    for 平台实例 in _获取平台实例列表(上下文):
        try:
            if not _是QQ官方平台(平台实例):
                continue
            找到官方适配器 = True
            if _开启互动事件(平台实例):
                已启用帮助数量 += 1
            if _开启群成员加入事件(平台实例, 适配器模块):
                已启用成员加入数量 += 1
        except Exception as 异常:
            logger.warning(
                "QQ官方帮助桥诊断：stage=platform_sync, success=False, error_type=%s",
                type(异常).__name__,
            )
            continue
    global 平台同步已完成
    平台同步已完成 = 找到官方适配器
    if 上下文 is not None and not 找到官方适配器:
        logger.warning("QQ官方帮助桥诊断：stage=platform_sync, qq_official_found=False")
    if 已启用帮助数量 or 已启用成员加入数量:
        logger.info(
            "QQ官方群事件桥已同步运行中适配器："
            f"interaction={已启用帮助数量}, "
            f"group_member_add={已启用成员加入数量}",
        )
    if 上下文 is not None and not 找到官方适配器:
        _安排平台加载后同步(上下文)
    return True


async def _等待QQ官方平台加载(上下文: Any) -> None:
    """兼容未触发 OnPlatformLoadedEvent 的运行时，等待官方平台实例出现后同步帮助桥。"""
    try:
        for _ in range(360):
            if 平台同步已完成:
                return
            if _已加载QQ官方平台(上下文):
                logger.info(
                    "QQ官方帮助桥诊断：stage=platform_poll, qq_official_found=True",
                )
                安装QQ官方帮助交互(上下文)
                return
            await asyncio.sleep(0.5)
        logger.debug(
            "QQ官方帮助桥诊断：stage=platform_poll, qq_official_found=False",
        )
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        logger.warning(
            "QQ官方帮助桥诊断：stage=platform_poll, success=False, error_type=%s",
            type(异常).__name__,
        )


def _安排平台加载后同步(上下文: Any) -> None:
    global 平台同步任务
    if 平台同步已完成 or 上下文 is None:
        return
    if 平台同步任务 is not None and not 平台同步任务.done():
        return
    try:
        事件循环 = asyncio.get_running_loop()
    except RuntimeError:
        平台同步任务 = None
        return
    平台同步任务 = 事件循环.create_task(_等待QQ官方平台加载(上下文))


async def QQ官方平台加载后同步(上下文: Any) -> None:
    """由插件主模块接收平台生命周期事件，避免子模块 handler 无法归属插件。"""
    logger.info("QQ官方帮助桥诊断：stage=platform_loaded_hook, begin=True")
    安装QQ官方帮助交互(上下文)
