"""网盘远端小说文件的时间与文件名判断工具。"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import hashlib
import re
from typing import Any
import weakref


_目录创建锁表 = globals().get("_目录创建锁表")
if not isinstance(_目录创建锁表, weakref.WeakValueDictionary):
    _目录创建锁表 = weakref.WeakValueDictionary()


def 获取目录创建锁(cookie: str, 父目录ID: str, 目录名: str) -> asyncio.Lock:
    稳定Cookie = sorted(
        片段.strip()
        for 片段 in str(cookie or "").split(";")
        if 片段.strip()
        and 片段.split("=", 1)[0].strip().lower() not in {"__puus", "ctoken"}
    )
    锁键 = hashlib.sha256(
        (";".join(稳定Cookie) + "\0" + str(父目录ID) + "\0" + 目录名).encode("utf-8")
    ).hexdigest()
    锁 = _目录创建锁表.get(锁键)
    if 锁 is None:
        锁 = asyncio.Lock()
        _目录创建锁表[锁键] = 锁
    return 锁


def 生成每日上传目录(总目录: str, 当前日期: date | None = None) -> str:
    日期 = 当前日期 or datetime.now().astimezone().date()
    日期名 = f"{日期.year}年{日期.month}月{日期.day}日"
    根目录 = str(总目录 or "/小说机器人").strip().replace("\\", "/").rstrip("/")
    return f"{根目录}/{日期名}"


def 读取日期目录日期(目录名: str) -> date | None:
    匹配 = re.fullmatch(r"([0-9]{4})年([1-9][0-9]?)月([1-9][0-9]?)日", 目录名)
    if not 匹配:
        return None
    try:
        return date(*(int(部分) for 部分 in 匹配.groups()))
    except ValueError:
        return None


def 是远端文件夹(项目: Any) -> bool:
    if not isinstance(项目, dict):
        return False
    for 字段 in ("dir", "is_dir", "isdir"):
        if 字段 in 项目:
            值 = 项目[字段]
            return 值.strip().lower() in {"1", "true", "yes"} if isinstance(值, str) else bool(值)
    return False


def 读取远端项目ID(项目: Any) -> str:
    if not isinstance(项目, dict):
        return ""
    for 字段 in ("fid", "file_id", "fileId", "id", "path"):
        值 = 项目.get(字段)
        if 值 not in (None, ""):
            return str(值)
    return ""


async def 清理日期目录小说(
    客户端: Any, 总目录: str, 当前日期: date | None = None
) -> int:
    """保留今天/昨天，清理旧 TXT 后仅删除已确认空的过期日期子目录。"""
    日期 = 当前日期 or datetime.now().astimezone().date()
    截止日期 = 日期 - timedelta(days=2)
    根目录ID = await 客户端.确保目录路径(总目录)
    根目录项目 = await 客户端.列出目录全部项目(根目录ID)

    async def 清理文件(目录ID: str, 项目列表: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        待删除 = list(dict.fromkeys(
            读取远端项目ID(项目)
            for 项目 in 项目列表
            if not 是远端文件夹(项目)
            and 是应清理的小说(项目, 日期, 保留天数=2)
            and 读取远端项目ID(项目)
        ))
        if not 待删除:
            return 0, 项目列表
        await 客户端.删除文件ID列表(待删除)
        # 删除可能由远端异步执行；只重查，不重复提交删除或递归删除目录。
        for 尝试 in range(4):
            剩余项目 = await 客户端.列出目录全部项目(目录ID)
            剩余ID = {读取远端项目ID(项目) for 项目 in 剩余项目}
            if not 剩余ID.intersection(待删除):
                return len(待删除), 剩余项目
            if 尝试 < 3:
                await asyncio.sleep(0.25 * (尝试 + 1))
        raise RuntimeError("网盘过期小说删除尚未完成，保留日期目录")

    删除数量, _ = await 清理文件(根目录ID, 根目录项目)
    for 项目 in 根目录项目:
        if not 是远端文件夹(项目):
            continue
        目录日期 = 读取日期目录日期(读取远端文件名(项目))
        目录ID = 读取远端项目ID(项目)
        if 目录日期 is None or 目录日期 > 截止日期 or not 目录ID or 目录ID == 根目录ID:
            continue
        目录项目 = await 客户端.列出目录全部项目(目录ID)
        已删除, _ = await 清理文件(目录ID, 目录项目)
        删除数量 += 已删除
        # 再读一次完整目录，混入其他文件、未知时间 TXT 或子目录时保留。
        if not await 客户端.列出目录全部项目(目录ID):
            await 客户端.删除文件ID列表([目录ID])
    return 删除数量


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


def 是应清理的小说(
    项目: Any,
    当前日期: date | None = None,
    保留天数: int = 2,
) -> bool:
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
    try:
        保留天数 = max(0, int(保留天数))
    except (TypeError, ValueError):
        保留天数 = 2
    return 文件日期 <= 日期 - timedelta(days=保留天数)


def 是早于当天的小说(项目: Any, 当前日期: date | None = None) -> bool:
    """兼容旧调用：判断文件是否早于当天。"""
    return 是应清理的小说(项目, 当前日期, 保留天数=0)
