"""网盘远端小说文件的时间与文件名判断工具。"""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any


def 读取远端文件名(项目: Any) -> str:
    if not isinstance(项目, dict):
        return ""
    for 字段名 in (
        "file_name",
        "fileName",
        "server_filename",
        "name",
        "filename",
    ):
        值 = 项目.get(字段名)
        if 值 not in (None, ""):
            return str(值).strip()
    return ""


def 是小说TXT(项目: Any) -> bool:
    """只清理机器人生成的 TXT，避免误删网盘目录里的其他类型文件。"""
    文件名 = 读取远端文件名(项目)
    return bool(文件名 and 文件名.lower().endswith(".txt"))


def _转远端时间戳(值: Any) -> float:
    if isinstance(值, datetime):
        try:
            return float(值.timestamp())
        except (OverflowError, OSError, ValueError):
            return 0.0
    if isinstance(值, date):
        try:
            return float(datetime.combine(值, datetime.min.time()).timestamp())
        except (OverflowError, OSError, ValueError):
            return 0.0
    if isinstance(值, (int, float)):
        数值 = float(值)
    else:
        文本 = str(值 or "").strip()
        if not 文本:
            return 0.0
        if re.fullmatch(r"\d+(?:\.\d+)?", 文本):
            数值 = float(文本)
        else:
            try:
                标准文本 = 文本.replace("Z", "+00:00")
                解析 = datetime.fromisoformat(标准文本)
                return float(解析.timestamp())
            except (TypeError, ValueError, OverflowError, OSError):
                return 0.0
    if 数值 > 10_000_000_000:
        数值 /= 1000.0
    if 数值 < 946_684_800 or 数值 > 4_102_444_800:
        return 0.0
    return 数值


def 读取远端文件时间戳(项目: Any) -> float:
    if not isinstance(项目, dict):
        return 0.0
    for 字段名 in (
        "updated_at",
        "update_time",
        "modified_at",
        "mtime",
        "server_mtime",
        "local_mtime",
        "created_at",
        "create_time",
    ):
        值 = 项目.get(字段名)
        时间戳 = _转远端时间戳(值)
        if 时间戳 > 0:
            return 时间戳
    return 0.0


def 是早于当天的小说(项目: Any, 当前日期: date | None = None) -> bool:
    if not 是小说TXT(项目):
        return False
    时间戳 = 读取远端文件时间戳(项目)
    if 时间戳 <= 0:
        return False
    日期 = 当前日期 or datetime.now().astimezone().date()
    try:
        文件日期 = datetime.fromtimestamp(时间戳).date()
    except (OverflowError, OSError, ValueError):
        return False
    return 文件日期 < 日期
