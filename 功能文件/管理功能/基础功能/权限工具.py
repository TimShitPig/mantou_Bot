from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    logger = logging.getLogger(__name__)


管理员白名单命名空间 = "admin_whitelist"
管理员白名单状态键 = "group_file_cleanup_admin_qq"
管理员白名单配置快照键 = "config_snapshot"
管理员白名单同步间隔秒 = 5.0
_管理员白名单缓存: dict[int, tuple[float, list[str]]] = {}
_管理员白名单同步锁 = threading.RLock()


def 是群文件清理管理员(event: Any, 配置: Any) -> bool:
    发送者 = 获取发送者QQ(event)
    管理员列表 = 获取群文件清理管理员QQ列表(配置)
    return bool(发送者 and 发送者 in 管理员列表)


def 获取群文件清理管理员QQ列表(配置: Any) -> set[str]:
    return set(同步管理员白名单(配置))


def _规范化管理员白名单(值: Any) -> list[str]:
    if isinstance(值, str):
        文本 = 值.strip()
        if 文本.startswith("["):
            try:
                值 = json.loads(文本)
            except (TypeError, ValueError, json.JSONDecodeError):
                值 = 文本
        if isinstance(值, str):
            值 = [项目 for 项目 in re.split(r"[,，\n\r\s]+", 值) if 项目]
    if not isinstance(值, (list, tuple, set)):
        return []
    结果: list[str] = []
    for 项目 in 值:
        文本 = str(项目 or "").strip()
        if 文本 and 文本 not in 结果:
            结果.append(文本)
    return 结果


def _读取管理员配置白名单(配置: Any) -> list[str]:
    if not 配置:
        return []
    return _规范化管理员白名单(
        读取配置字段(配置, "group_file_cleanup_admin_qq") or []
    )


def _读取数据库白名单状态(配置: Any) -> tuple[bool, str, str]:
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        if not 运行状态数据库.已配置运行状态数据库(配置):
            return False, "", ""
        当前值 = 运行状态数据库.读取运行状态值(
            配置, 管理员白名单命名空间, 管理员白名单状态键, ""
        )
        快照值 = 运行状态数据库.读取运行状态值(
            配置, 管理员白名单命名空间, 管理员白名单配置快照键, ""
        )
        return True, str(当前值 or ""), str(快照值 or "")
    except Exception as 异常:
        logger.debug(
            "管理员白名单数据库读取失败：错误类型=%s",
            type(异常).__name__,
        )
        return False, "", ""


def _写入数据库白名单状态(配置: Any, 白名单: list[str]) -> bool:
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        if not 运行状态数据库.已配置运行状态数据库(配置):
            return False
        值 = json.dumps(白名单, ensure_ascii=False, separators=(",", ":"))
        批量写入 = getattr(运行状态数据库, "批量写入运行状态值", None)
        if callable(批量写入):
            批量写入(
                配置,
                管理员白名单命名空间,
                {
                    管理员白名单状态键: 值,
                    管理员白名单配置快照键: 值,
                },
            )
        else:
            运行状态数据库.写入运行状态值(
                配置, 管理员白名单命名空间, 管理员白名单状态键, 值
            )
            运行状态数据库.写入运行状态值(
                配置, 管理员白名单命名空间, 管理员白名单配置快照键, 值
            )
        return True
    except Exception as 异常:
        logger.debug(
            "管理员白名单数据库写入失败：错误类型=%s",
            type(异常).__name__,
        )
        return False


def _写入AstrBot配置白名单(配置: Any, 白名单: list[str]) -> bool:
    数据 = 获取配置字典(配置)
    if isinstance(数据, dict):
        for 分类名 in ("basic_settings", "基础配置"):
            分类 = 数据.get(分类名)
            if isinstance(分类, dict):
                分类["group_file_cleanup_admin_qq"] = list(白名单)
                return True
        if "group_file_cleanup_admin_qq" in 数据:
            数据["group_file_cleanup_admin_qq"] = list(白名单)
            return True
        基础配置 = 数据.setdefault("basic_settings", {})
        if isinstance(基础配置, dict):
            基础配置["group_file_cleanup_admin_qq"] = list(白名单)
            return True
    try:
        setattr(配置, "group_file_cleanup_admin_qq", list(白名单))
        return True
    except Exception:
        return False


def _持久化AstrBot配置(配置: Any) -> None:
    保存方法 = getattr(配置, "save_config", None)
    if not callable(保存方法):
        return
    try:
        保存方法()
    except Exception as 异常:
        logger.debug(
            "管理员白名单 AstrBot 配置写入失败：错误类型=%s",
            type(异常).__name__,
        )


def 同步管理员白名单(配置: Any, 强制: bool = False) -> list[str]:
    """在 AstrBot 配置与 MySQL 之间双向同步管理员白名单。

    ``config_snapshot`` 记录上次同步的配置值，用于区分“配置刚被修改”与
    “数据库被外部修改”。数据库可用时优先保留外部数据库变更，配置发生
    变化时则把新配置写入数据库；两边最终保持同一份列表。
    """
    if not 配置:
        return []
    配置键 = id(配置)
    现在 = time.monotonic()
    with _管理员白名单同步锁:
        缓存 = _管理员白名单缓存.get(配置键)
        if (
            not 强制
            and 缓存 is not None
            and 现在 - 缓存[0] < 管理员白名单同步间隔秒
        ):
            return list(缓存[1])

        配置白名单 = _读取管理员配置白名单(配置)
        数据库已配置, 数据库文本, 快照文本 = _读取数据库白名单状态(配置)
        if not 数据库已配置:
            _管理员白名单缓存[配置键] = (现在, list(配置白名单))
            return 配置白名单

        数据库有值 = bool(数据库文本.strip())
        快照有值 = bool(快照文本.strip())
        数据库白名单 = _规范化管理员白名单(数据库文本) if 数据库有值 else []
        上次配置白名单 = _规范化管理员白名单(快照文本) if 快照有值 else []

        if 快照有值 and 配置白名单 != 上次配置白名单:
            # AstrBot 配置在上次同步后发生变化，配置值作为本次更新源。
            最终白名单 = 配置白名单
        elif 数据库有值:
            # 配置未变化时，数据库可能被网页、运维脚本或其他实例修改。
            最终白名单 = 数据库白名单
        elif 配置白名单:
            # 首次启用数据库同步时迁移现有 AstrBot 配置。
            最终白名单 = 配置白名单
        else:
            最终白名单 = []

        配置已变化 = 最终白名单 != 配置白名单
        数据库值 = json.dumps(最终白名单, ensure_ascii=False, separators=(",", ":"))
        数据库需写入 = 数据库文本 != 数据库值 or 快照文本 != 数据库值
        if 配置已变化 and _写入AstrBot配置白名单(配置, 最终白名单):
            _持久化AstrBot配置(配置)
        if 数据库需写入:
            _写入数据库白名单状态(配置, 最终白名单)
        _管理员白名单缓存[配置键] = (现在, list(最终白名单))
        return list(最终白名单)


def 读取配置字段(配置: Any, 字段名: str) -> Any:
    配置字典 = 获取配置字典(配置)
    if 配置字典 is not None and 配置字典 is not 配置:
        值 = 读取配置字段(配置字典, 字段名)
        if 值 is not None:
            return 值

    值 = 读取字段(配置, 字段名)
    if 值 is None:
        值 = 读取旧版配置字段(配置, 字段名)
    if 值 is not None:
        return 值
    for 分类名 in ("basic_settings", "基础配置"):
        分类 = 读取字段(配置, 分类名)
        if 分类 is None:
            分类 = 读取旧版配置字段(配置, 分类名)
        if isinstance(分类, dict):
            值 = 分类.get(字段名)
            if 值 is not None:
                return 值
        elif 分类 is not None:
            值 = 读取字段(分类, 字段名)
            if 值 is None:
                值 = 读取旧版配置字段(分类, 字段名)
            if 值 is not None:
                return 值
    return None


def 获取配置字典(配置: Any) -> dict[str, Any] | None:
    if isinstance(配置, dict):
        return 配置
    获取方法 = getattr(配置, "get_config", None)
    if callable(获取方法):
        try:
            数据 = 获取方法()
            if isinstance(数据, dict):
                return 数据
        except Exception:
            pass
    for 字段名 in ("data", "obj"):
        数据 = getattr(配置, 字段名, None)
        if isinstance(数据, dict):
            return 数据
    return None


def 读取旧版配置字段(配置: Any, 字段名: str) -> Any:
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            return 获取方法(字段名)
        except Exception:
            pass
    return getattr(配置, 字段名, None)


def 获取发送者QQ(event: Any) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("sender_id", "user_id", "sender"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("user_id") or 值.get("id")
            if 值:
                return str(值)
    return ""


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 获取适配器名称(event: Any) -> str:
    for 方法名 in ("get_platform_name", "get_adapter_name"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            try:
                return str(方法()).strip().lower()
            except Exception:
                pass

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        platform_meta = 读取字段(对象, "platform_meta")
        if platform_meta:
            for 字段名 in ("name", "id", "platform", "adapter_name", "platform_name"):
                值 = 读取字段(platform_meta, 字段名)
                if 值:
                    return str(值).strip().lower()
            if isinstance(platform_meta, dict):
                for 字段名 in (
                    "name",
                    "id",
                    "platform",
                    "adapter_name",
                    "platform_name",
                ):
                    值 = platform_meta.get(字段名)
                    if 值:
                        return str(值).strip().lower()

    bot = getattr(event, "bot", None)
    if bot is not None:
        for 字段名 in ("platform", "adapter_name", "adapter"):
            值 = 读取字段(bot, 字段名)
            if 值:
                    return str(值).strip().lower()
        for 字段名 in ("platform_name", "platform_type"):
            值 = 读取字段(bot, 字段名)
            if 值:
                    return str(值).strip().lower()

    return ""


def 是QQ官方机器人(event: Any) -> bool:
    适配器 = re.sub(r"[-\s]+", "_", 获取适配器名称(event))
    if not 适配器:
        return False
    return 适配器 == "qq_official" or 适配器 == "qqofficial"

