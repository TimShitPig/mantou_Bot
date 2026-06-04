from __future__ import annotations

from typing import Any


def 是群文件清理管理员(event: Any, 配置: Any) -> bool:
    发送者 = 获取发送者QQ(event)
    管理员列表 = 获取群文件清理管理员QQ列表(配置)
    return bool(发送者 and 发送者 in 管理员列表)


def 获取群文件清理管理员QQ列表(配置: Any) -> set[str]:
    if not 配置:
        return set()
    值 = 读取配置字段(配置, "group_file_cleanup_admin_qq") or []
    if isinstance(值, str):
        值 = [值]
    if not isinstance(值, list):
        return set()
    return {str(项目).strip() for 项目 in 值 if str(项目).strip()}


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
