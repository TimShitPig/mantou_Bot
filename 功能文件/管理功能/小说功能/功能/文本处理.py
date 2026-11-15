"""小说正文写入 TXT 前的通用文本处理。"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def 去除章节正文重复标题(标题: object, 正文: object) -> str:
    """删除正文首行中与章节标题完全相同的重复标题。"""
    文本 = str(正文 or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    标题文本 = str(标题 or "").strip()
    if not 文本 or not 标题文本:
        return 文本

    行列表 = 文本.split("\n")
    首行 = 行列表[0].strip().lstrip("\ufeff")
    if _标题比较值(首行) != _标题比较值(标题文本):
        return 文本
    return "\n".join(行列表[1:]).lstrip("\n").strip()


def _标题比较值(文本: str) -> str:
    return re.sub(r"\s+", "", str(文本 or "")).strip()


def 格式化小说字数(值: object) -> str:
    """转换显示单位，调用方继续保留平台返回的精确字数。"""
    if 值 is None or isinstance(值, bool):
        return "未知"
    文本 = re.sub(r"[\s,，]", "", str(值))
    带单位 = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(万|亿)字?", 文本)
    if 带单位:
        return (文本 if 文本.endswith("字") else f"{文本}字") if Decimal(带单位[1]) > 0 else "未知"
    数字文本 = 文本[:-1] if 文本.endswith("字") else 文本
    if not re.fullmatch(r"[0-9]+(?:\.0+)?", 数字文本):
        return "未知"
    try:
        数字 = int(Decimal(数字文本))
        if 数字 >= 10000:
            万字 = f"{Decimal(数字) / 10000:.2f}".rstrip("0").rstrip(".")
            return f"{万字}万字"
        return f"{数字:,}字" if 数字 > 0 else "未知"
    except (InvalidOperation, ValueError, OverflowError):
        return "未知"
