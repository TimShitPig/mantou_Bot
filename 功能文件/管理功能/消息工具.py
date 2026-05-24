from __future__ import annotations

import re
from typing import Any


def 获取命令文本(event: Any) -> str:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            文本 = 转成命令文本(读取字段(对象, 字段名))
            if 文本:
                return 文本
    return ""


def 读取字段(对象: Any, 字段名: str) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 转成命令文本(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, str):
        return 清理命令文本(值)
    if isinstance(值, list):
        return 清理命令文本("".join(转消息段文本(消息段) for 消息段 in 值))
    if isinstance(值, dict):
        return 清理命令文本(转消息段文本(值))
    return ""


def 转消息段文本(消息段: Any) -> str:
    if not isinstance(消息段, dict) or 消息段.get("type") != "text":
        return ""
    数据 = 消息段.get("data")
    if isinstance(数据, dict):
        return str(数据.get("text") or "")
    return ""


def 清理命令文本(文本: str) -> str:
    文本 = re.sub(r"\[CQ:reply,[^\]]*\]", "", str(文本 or ""))
    文本 = re.sub(r"\[CQ:at,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[At:[^\]]+\]", "", 文本)
    return 文本.strip()
