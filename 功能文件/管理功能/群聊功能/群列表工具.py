from __future__ import annotations

import inspect
import re
import time
from typing import Any

官方群成员映射: dict[str, dict[str, tuple[str, float]]] = {}
官方群成员反向映射: dict[str, dict[str, tuple[str, float]]] = {}
官方群成员映射有效期秒数 = 24 * 60 * 60


def _关闭未等待对象(值: Any) -> None:
    if inspect.iscoroutine(值):
        try:
            值.close()
        except Exception:
            pass


def _安全群号文本(值: Any) -> str:
    if inspect.isawaitable(值):
        _关闭未等待对象(值)
        return ""
    if callable(值):
        return ""
    文本 = str(值 or "").strip()
    if not 文本:
        return ""
    if "coroutine object" in 文本.lower() or "generator object" in 文本.lower():
        return ""
    if re.search(r"<[^>]+ object at 0x[0-9a-f]+>", 文本, re.IGNORECASE):
        return ""
    return 文本


def 记录官方群成员映射(群号: Any, 用户标识: Any, 成员标识: Any) -> None:
    """记录 QQ 官方群内稳定 user_openid 与本群 member_openid 的对应关系。"""
    群号文本 = _安全群号文本(群号)
    用户文本 = _安全群号文本(用户标识)
    成员文本 = _安全群号文本(成员标识)
    if not 群号文本 or not 用户文本 or not 成员文本:
        return
    当前时间 = time.monotonic()
    官方群成员映射.setdefault(群号文本, {})[用户文本] = (成员文本, 当前时间)
    官方群成员反向映射.setdefault(群号文本, {})[成员文本] = (用户文本, 当前时间)


def 获取官方群成员标识(群号: Any, 用户标识: Any) -> str:
    群号文本 = _安全群号文本(群号)
    用户文本 = _安全群号文本(用户标识)
    if not 群号文本 or not 用户文本:
        return ""
    记录 = 官方群成员映射.get(群号文本, {}).get(用户文本)
    if not 记录:
        return ""
    成员文本, 时间戳 = 记录
    if time.monotonic() - 时间戳 >= 官方群成员映射有效期秒数:
        官方群成员映射.get(群号文本, {}).pop(用户文本, None)
        官方群成员反向映射.get(群号文本, {}).pop(成员文本, None)
        return ""
    return 成员文本


def 获取官方群用户标识(群号: Any, 成员标识: Any) -> str:
    群号文本 = _安全群号文本(群号)
    成员文本 = _安全群号文本(成员标识)
    if not 群号文本 or not 成员文本:
        return ""
    记录 = 官方群成员反向映射.get(群号文本, {}).get(成员文本)
    if not 记录:
        return ""
    用户文本, 时间戳 = 记录
    if time.monotonic() - 时间戳 >= 官方群成员映射有效期秒数:
        官方群成员反向映射.get(群号文本, {}).pop(成员文本, None)
        官方群成员映射.get(群号文本, {}).pop(用户文本, None)
        return ""
    return 用户文本


def 删除官方群成员映射(群号: Any, 用户标识: Any = "", 成员标识: Any = "") -> None:
    群号文本 = _安全群号文本(群号)
    用户文本 = _安全群号文本(用户标识)
    成员文本 = _安全群号文本(成员标识)
    if not 群号文本:
        return
    if 用户文本:
        旧记录 = 官方群成员映射.get(群号文本, {}).pop(用户文本, None)
        if 旧记录 and not 成员文本:
            成员文本 = 旧记录[0]
    if 成员文本:
        旧记录 = 官方群成员反向映射.get(群号文本, {}).pop(成员文本, None)
        if 旧记录 and not 用户文本:
            用户文本 = 旧记录[0]
    if 用户文本:
        官方群成员映射.get(群号文本, {}).pop(用户文本, None)
    if 成员文本:
        官方群成员反向映射.get(群号文本, {}).pop(成员文本, None)
