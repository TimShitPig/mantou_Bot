from __future__ import annotations

import inspect
import re
import time
from typing import Any


数字群号规则 = re.compile(r"[1-9]\d{4,11}")
已知机器人群号集合: set[str] = set()
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


def 记录机器人所在群号(群号: Any) -> None:
    """记录当前进程见过的群号，供没有群列表接口的官方适配器跨群操作使用。"""
    文本 = _安全群号文本(群号)
    if 文本:
        已知机器人群号集合.add(文本)


def 获取已知机器人群号列表() -> list[str]:
    return sorted(已知机器人群号集合)


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


async def 获取机器人所在群号列表(bot: Any) -> list[str]:
    try:
        响应 = await 调用群列表接口(bot)
        群号列表 = 提取群号列表(响应)
        if 群号列表:
            已知机器人群号集合.update(群号列表)
            return 群号列表
    except Exception:
        pass
    群号列表 = 获取已知机器人群号列表()
    if not 群号列表:
        raise RuntimeError("没有获取到机器人所在的群号")
    return 群号列表


async def 调用群列表接口(bot: Any) -> Any:
    群列表方法 = getattr(bot, "get_group_list", None)
    if callable(群列表方法):
        return await 等待可能异步结果(群列表方法())

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        return await 等待可能异步结果(调用动作("get_group_list"))

    raise RuntimeError("当前 bot 没有 get_group_list 群列表接口")


async def 等待可能异步结果(结果: Any) -> Any:
    if inspect.isawaitable(结果):
        return await 结果
    return 结果


def 提取群号列表(响应: Any) -> list[str]:
    数据 = 响应.get("data") if isinstance(响应, dict) and "data" in 响应 else 响应
    候选列表: list[Any]
    if isinstance(数据, dict):
        候选列表 = 数据.get("groups") or 数据.get("group_list") or 数据.get("list") or []
    elif isinstance(数据, list):
        候选列表 = 数据
    else:
        候选列表 = []

    结果: list[str] = []
    已见: set[str] = set()
    for 候选 in 候选列表:
        群号 = 提取单个群号(候选)
        if not 群号 or 群号 in 已见:
            continue
        已见.add(群号)
        结果.append(群号)
    return 结果


def 提取单个群号(值: Any) -> str:
    if isinstance(值, dict):
        值 = (
            值.get("group_id")
            or 值.get("group_openid")
            or 值.get("groupOpenid")
            or 值.get("group")
            or 值.get("id")
        )
    文本 = _安全群号文本(值)
    if not 文本:
        return ""
    if 数字群号规则.fullmatch(文本):
        return 文本
    # QQ 官方机器人返回 group_openid，非数字群号也接受
    return 文本
