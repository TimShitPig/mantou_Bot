from __future__ import annotations

import inspect
import re
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from astrbot.api.event import AstrMessageEvent
except Exception:
    AstrMessageEvent = Any

from 功能文件.管理功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.群列表工具 import 获取机器人所在群号列表


数字撤回规则 = re.compile(r"(?<!\d)\d{9,12}(?!\d)")
链接规则 = re.compile(r"https?://|https?%3A%2F%2F|\b\w+\.\w+/", re.IGNORECASE)
白名单域名规则 = re.compile(r"changdunovel\.com|fanqienovel\.com|fqnovel\.com|novelfm\.com|qimao\.com|app-share\.wtzw\.com", re.IGNORECASE)
群名片规则 = re.compile(r"\[CQ:contact,[^\]]*(?:type=group|type=qq_group)[^\]]*\]")
卡片消息规则 = re.compile(r"ComponentType\.(?:Json|Share|Contact)|\[CQ:(?:json|contact),", re.IGNORECASE)
At消息规则 = re.compile(r"\[CQ:at,[^\]]*\]|\[At:[^\]]+\]|ComponentType\.At", re.IGNORECASE)
合并转发规则 = re.compile(
    r"ComponentType\.(?:Forward|Node|Nodes)|\[CQ:(?:forward|node),|群聊的聊天记录|查看\d+条转发消息",
    re.IGNORECASE,
)
闪传消息规则 = re.compile(r"QQ闪传|该消息类型暂不支持查看", re.IGNORECASE)
数字ID规则 = re.compile(r"[1-9]\d{4,11}")
数字撤回踢出阈值 = 3
最近消息撤回数量 = 5
最近消息撤回拉取数量 = 30
数字撤回触发次数: dict[str, int] = {}
群管功能模块版本 = "1.18.0"
踢出命令集合 = {"踢", "踢了"}
禁言命令配置 = {
    "开启禁言": {"全部群": False, "启用": True, "操作": "开启"},
    "关闭禁言": {"全部群": False, "启用": False, "操作": "关闭"},
    "开启全部禁言": {"全部群": True, "启用": True, "操作": "开启"},
    "关闭全部禁言": {"全部群": True, "启用": False, "操作": "关闭"},
}
禁言命令集合 = set(禁言命令配置)


async def 处理用户踢出(event: AstrMessageEvent, 命令文本: str, 配置: Any) -> str | None:
    目标用户列表 = 解析踢出目标用户列表(event, 命令文本)
    if 目标用户列表 is None:
        return None

    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用用户踢出"

    if not 目标用户列表:
        return "用户踢出失败：请 @ 要踢出的用户"

    群号 = 获取群号(event)
    if not 群号:
        return "用户踢出失败：只能在群聊中使用"
    if not 是数字ID(群号) or any(not 是数字ID(目标用户) for 目标用户 in 目标用户列表):
        return "用户踢出失败：当前适配器没有返回数字群号或用户QQ"

    成功用户: list[str] = []
    失败用户: list[tuple[str, Exception]] = []
    for 目标用户 in 目标用户列表:
        try:
            await 尝试踢出指定成员(event, 群号, 目标用户)
            成功用户.append(目标用户)
            logger.info(f"用户踢出成功：group_id={群号}, user_id={目标用户}")
        except Exception as exc:
            失败用户.append((目标用户, exc))
            logger.warning(f"用户踢出失败：group_id={群号}, user_id={目标用户}, error={exc}")

    if len(目标用户列表) == 1:
        if 成功用户:
            return f"已踢出用户：{成功用户[0]}"
        return f"用户踢出失败：{失败用户[0][1]}"

    return 格式化批量踢出结果(成功用户, 失败用户)


async def 处理群禁言(event: AstrMessageEvent, 命令文本: str, 配置: Any) -> str | None:
    命令 = 提取群禁言命令文本(event, 命令文本)
    if 命令 not in 禁言命令集合:
        return None

    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用群禁言"

    命令配置 = 禁言命令配置[命令]
    启用 = bool(命令配置["启用"])
    操作 = str(命令配置["操作"])

    if 命令配置["全部群"]:
        return await 处理全部群禁言(event, 启用, 操作)

    群号 = 获取群号(event)
    if not 群号:
        return "群禁言失败：只能在群聊中使用"
    if not 是数字ID(群号):
        return "群禁言失败：当前适配器没有返回数字群号"

    try:
        await 尝试设置全员禁言(event, 群号, 启用)
        logger.info(f"群禁言{操作}成功：group_id={群号}")
        return f"已{操作}全员禁言"
    except Exception as exc:
        logger.warning(f"群禁言{操作}失败：group_id={群号}, error={exc}")
        return f"群禁言失败：{exc}"


async def 处理全部群禁言(event: AstrMessageEvent, 启用: bool, 操作: str) -> str:
    bot = getattr(event, "bot", None)
    if bot is None:
        return "全部群禁言失败：当前事件缺少 bot 实例"

    try:
        群号列表 = await 获取机器人所在群号列表(bot)
    except Exception as exc:
        logger.warning(f"全部群禁言获取群列表失败：error={exc}")
        return f"全部群禁言失败：{exc}"

    成功群: list[str] = []
    失败群: list[tuple[str, Exception]] = []
    for 群号 in 群号列表:
        try:
            await 使用_set_group_whole_ban禁言(bot, 群号, 启用)
            成功群.append(群号)
            logger.info(f"全部群禁言{操作}成功：group_id={群号}")
        except Exception as exc:
            失败群.append((群号, exc))
            logger.warning(f"全部群禁言{操作}失败：group_id={群号}, error={exc}")

    return 格式化全部群禁言结果(成功群, 失败群, 操作)


def 格式化全部群禁言结果(成功群: list[str], 失败群: list[tuple[str, Exception]], 操作: str) -> str:
    行列表 = [f"全部群禁言{操作}完成：成功 {len(成功群)} 个，失败 {len(失败群)} 个"]
    if 失败群:
        行列表.append("失败群：" + "；".join(f"{群号}：{错误}" for 群号, 错误 in 失败群))
    return "\n".join(行列表)


def 解析踢出目标用户列表(event: AstrMessageEvent, 命令文本: str) -> list[str] | None:
    命令 = 提取踢出命令文本(event, 命令文本)
    if 命令 not in 踢出命令集合:
        return None
    return 提取被艾特用户QQ列表(event)


def 解析踢出目标用户(event: AstrMessageEvent, 命令文本: str) -> str | None:
    目标用户列表 = 解析踢出目标用户列表(event, 命令文本)
    if 目标用户列表 is None:
        return None
    return 目标用户列表[0] if 目标用户列表 else ""


def 提取群禁言命令文本(event: AstrMessageEvent, 命令文本: str) -> str:
    候选列表: list[str] = []
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message", "components", "content"):
            文本 = 从消息段提取非At文本(读取字段(对象, 字段名))
            if 文本:
                候选列表.append(文本)
    候选列表.append(str(命令文本 or ""))
    候选列表.extend(获取原始文本候选(event))

    for 候选 in 候选列表:
        文本 = 清理踢出命令文本(候选)
        if 文本 in 禁言命令集合:
            return 文本
    return ""


def 格式化批量踢出结果(成功用户: list[str], 失败用户: list[tuple[str, Exception]]) -> str:
    行列表 = [f"用户踢出完成：成功 {len(成功用户)} 个，失败 {len(失败用户)} 个"]
    if 成功用户:
        行列表.append(f"已踢出用户：{格式化用户列表(成功用户)}")
    if 失败用户:
        行列表.append("失败用户：" + "；".join(f"{用户}：{错误}" for 用户, 错误 in 失败用户))
    return "\n".join(行列表)


def 提取踢出命令文本(event: AstrMessageEvent, 命令文本: str) -> str:
    候选列表: list[str] = []
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message", "components", "content"):
            文本 = 从消息段提取非At文本(读取字段(对象, 字段名))
            if 文本:
                候选列表.append(文本)
    候选列表.append(str(命令文本 or ""))
    候选列表.extend(获取原始文本候选(event))

    for 候选 in 候选列表:
        文本 = 清理踢出命令文本(候选)
        if 文本 in 踢出命令集合:
            return 文本
    return ""


def 提取被艾特用户QQ(event: AstrMessageEvent) -> str:
    用户列表 = 提取被艾特用户QQ列表(event)
    return 用户列表[0] if 用户列表 else ""


def 提取被艾特用户QQ列表(event: AstrMessageEvent) -> list[str]:
    忽略用户 = 获取应忽略At用户(event)
    结果: list[str] = []
    for 用户 in 获取At用户列表(event):
        if 用户 in 忽略用户:
            continue
        结果.append(用户)
    return 去重保序(结果)


def 获取应忽略At用户(event: AstrMessageEvent) -> set[str]:
    结果: set[str] = set()
    消息对象 = getattr(event, "message_obj", None)
    bot = getattr(event, "bot", None)
    for 对象 in (event, 消息对象, bot):
        if 对象 is None:
            continue
        for 字段名 in ("self_id", "bot_id", "robot_id", "uin", "qq"):
            用户 = 规范化用户编号(读取字段(对象, 字段名))
            if 用户:
                结果.add(用户)
    return 结果


def 获取At用户列表(event: AstrMessageEvent) -> list[str]:
    结果: list[str] = []
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message", "components", "content"):
            结果.extend(从消息段提取At用户列表(读取字段(对象, 字段名)))
        for 字段名 in ("message_str", "raw_message"):
            结果.extend(从文本提取At用户列表(读取字段(对象, 字段名)))
    return 去重保序(结果)


def 从消息段提取At用户列表(消息: Any) -> list[str]:
    if 消息 is None:
        return []
    if isinstance(消息, (list, tuple, set)):
        结果: list[str] = []
        for 消息段 in 消息:
            结果.extend(从消息段提取At用户列表(消息段))
        return 结果
    if isinstance(消息, dict):
        结果: list[str] = []
        if 是否At类型值(消息.get("type")):
            用户 = 规范化用户编号(
                消息.get("qq")
                or 读取字段(消息.get("data"), "qq")
                or 读取字段(消息.get("data"), "user_id")
            )
            if 用户:
                结果.append(用户)
        for 子值 in 消息.values():
            结果.extend(从消息段提取At用户列表(子值))
        return 结果
    if 是否At类型值(读取字段(消息, "type")):
        用户 = 规范化用户编号(
            读取字段(消息, "qq")
            or 读取字段(消息, "user_id")
            or 读取字段(读取字段(消息, "data"), "qq")
            or 读取字段(读取字段(消息, "data"), "user_id")
        )
        return [用户] if 用户 else []
    return []


def 从消息段提取非At文本(消息: Any) -> str:
    if 消息 is None:
        return ""
    if isinstance(消息, str):
        return 消息
    if isinstance(消息, (list, tuple, set)):
        return "".join(从消息段提取非At文本(消息段) for 消息段 in 消息)
    if isinstance(消息, dict):
        if 是否At类型值(消息.get("type")):
            return ""
        消息类型 = str(消息.get("type") or "").strip().lower()
        if 消息类型 in {"text", "plain"}:
            数据 = 消息.get("data")
            if isinstance(数据, dict):
                return str(数据.get("text") or 数据.get("content") or "")
            return str(消息.get("text") or 消息.get("content") or "")
        return ""

    消息类型 = str(读取字段(消息, "type") or "")
    if 是否At类型值(消息类型):
        return ""
    消息类型小写 = 消息类型.lower()
    if 消息类型小写 in {"text", "plain"} or 消息类型小写.endswith((".plain", ".text")):
        return str(读取字段(消息, "text") or 读取字段(消息, "content") or "")
    return ""


def 从文本提取At用户列表(文本: Any) -> list[str]:
    原文 = str(文本 or "")
    if not 原文:
        return []
    结果: list[str] = []
    for 匹配 in re.finditer(r"\[At:([^\]]+)\]", 原文, re.IGNORECASE):
        用户 = 规范化用户编号(匹配.group(1))
        if 用户:
            结果.append(用户)
    for 匹配 in re.finditer(r"\[CQ:at,[^\]]*qq=([^,\]]+)", 原文, re.IGNORECASE):
        用户 = 规范化用户编号(匹配.group(1))
        if 用户:
            结果.append(用户)
    for 匹配 in re.finditer(r"@[^\s()]{1,80}\(([A-Za-z0-9_-]{5,64})\)", 原文):
        用户 = 规范化用户编号(匹配.group(1))
        if 用户:
            结果.append(用户)
    return 结果


def 清理踢出命令文本(文本: Any) -> str:
    结果 = str(文本 or "")
    结果 = re.sub(r"\[CQ:reply,[^\]]*\]", "", 结果, flags=re.IGNORECASE)
    结果 = re.sub(r"\[CQ:at,[^\]]*\]", "", 结果, flags=re.IGNORECASE)
    结果 = re.sub(r"\[At:[^\]]+\]", "", 结果, flags=re.IGNORECASE)
    结果 = 结果.replace("＠", "@").strip()
    while 结果.startswith("@"):
        新结果 = re.sub(r"^@[^\s]+\s*", "", 结果, count=1)
        if 新结果 == 结果:
            break
        结果 = 新结果.strip()
    结果 = re.sub(r"\s+", " ", 结果).strip()
    return 结果


def 去重保序(列表: list[str]) -> list[str]:
    结果: list[str] = []
    已见: set[str] = set()
    for 项目 in 列表:
        if 项目 in 已见:
            continue
        已见.add(项目)
        结果.append(项目)
    return 结果


def 格式化用户列表(用户列表: list[str]) -> str:
    return "、".join(用户列表)


def 规范化用户编号(值: Any) -> str:
    文本 = str(值 or "").strip()
    if not 文本 or 文本.lower() in {"all", "qq_official"}:
        return ""
    return 文本 if 数字ID规则.fullmatch(文本) else ""


async def 处理数字撤回(event: AstrMessageEvent) -> bool:
    消息文本 = 获取消息文本(event)
    卡片类型 = 获取卡片撤回类型(event)
    if 卡片类型:
        记录卡片诊断日志(event, 消息文本, 卡片类型)
    if not 是否需要撤回消息(event, 消息文本):
        return False
    撤回成功 = await 尝试撤回当前消息(event)
    if 撤回成功:
        await 尝试撤回触发用户最近消息(event)
        await 记录撤回触发并尝试踢出(event)
    return 撤回成功


def 是否需要撤回消息(event: AstrMessageEvent, 消息文本: str = "") -> bool:
    if 是否白名单消息(event, 消息文本):
        return False
    if 是否At消息(event):
        return False
    return (
        是否群名片消息(event)
        or 是否合并转发消息(event)
        or 是否闪传消息(event)
        or 是否需要撤回数字消息(消息文本)
    )


def 是否需要撤回数字消息(消息文本: str) -> bool:
    文本 = str(消息文本 or "").strip()
    if 链接规则.search(文本):
        return False
    return bool(数字撤回规则.search(文本))


def 是否白名单消息(event: AstrMessageEvent, 消息文本: str = "") -> bool:
    if 白名单域名规则.search(str(消息文本 or "")):
        return True
    for 文本 in 获取原始文本候选(event):
        if 白名单域名规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含白名单域名(消息):
            return True
    return False


def 是否群名片消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if 群名片规则.search(文本) or 卡片消息规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含群名片消息段(消息) or 包含卡片标记(消息):
            return True
    return False


def 是否合并转发消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if 合并转发规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含合并转发消息段(消息) or 包含合并转发标记(消息):
            return True
    return False


def 是否闪传消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if 闪传消息规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含闪传标记(消息):
            return True
    return False


def 获取卡片撤回类型(event: AstrMessageEvent) -> str:
    if 是否群名片消息(event):
        return "群名片/JSON卡片"
    if 是否合并转发消息(event):
        return "合并转发"
    if 是否闪传消息(event):
        return "QQ闪传"
    return ""


def 记录卡片诊断日志(event: AstrMessageEvent, 消息文本: str, 卡片类型: str) -> None:
    消息对象 = getattr(event, "message_obj", None)
    logger.info(
        "卡片诊断："
        f"类型={卡片类型}, "
        f"message_id={获取当前消息编号(event)}, "
        f"message_str={限制长度(getattr(event, 'message_str', ''))}, "
        f"raw_message={限制长度(getattr(event, 'raw_message', ''))}, "
        f"提取文本={限制长度(消息文本)}, "
        f"event_message={描述值(读取字段(event, 'message'))}, "
        f"message_obj_message={描述值(读取字段(消息对象, 'message'))}"
    )


def 是否At消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        if At消息规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含At消息段(消息) or 包含At对象标记(消息):
            return True
    return False


def 获取原始文本候选(event: AstrMessageEvent) -> list[str]:
    消息对象 = getattr(event, "message_obj", None)
    结果: list[str] = []
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, str) and 值:
                结果.append(值)
    return 结果


def 包含群名片消息段(消息: Any) -> bool:
    if isinstance(消息, list):
        return any(是否群名片消息段(消息段) for 消息段 in 消息)
    return 是否群名片消息段(消息)


def 包含At消息段(消息: Any) -> bool:
    if isinstance(消息, list):
        return any(是否At消息段(消息段) for 消息段 in 消息)
    return 是否At消息段(消息)


def 包含合并转发消息段(消息: Any) -> bool:
    if isinstance(消息, list):
        return any(是否合并转发消息段(消息段) for 消息段 in 消息)
    return 是否合并转发消息段(消息)


def 是否At消息段(消息段: Any) -> bool:
    if isinstance(消息段, dict):
        return 是否At类型值(消息段.get("type"))
    return 是否At类型值(读取字段(消息段, "type"))


def 是否合并转发消息段(消息段: Any) -> bool:
    if isinstance(消息段, dict):
        return 是否合并转发类型值(消息段.get("type"))
    return 是否合并转发类型值(读取字段(消息段, "type"))


def 包含At对象标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含At对象标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return 是否At消息段(值) or any(包含At对象标记(子值) for 子值 in 值.values())
    return bool(At消息规则.search(str(值)))


def 包含合并转发标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含合并转发标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return 是否合并转发消息段(值) or any(包含合并转发标记(子值) for 子值 in 值.values())
    return bool(合并转发规则.search(str(值)))


def 包含闪传标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含闪传标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return any(包含闪传标记(子值) for 子值 in 值.values())
    return bool(闪传消息规则.search(str(值)))


def 包含白名单域名(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含白名单域名(子值) for 子值 in 值)
    if isinstance(值, dict):
        return any(包含白名单域名(子值) for 子值 in 值.values())
    return bool(白名单域名规则.search(str(值)))


def 是否At类型值(值: Any) -> bool:
    for 候选 in (值, 读取字段(值, "value"), 读取字段(值, "name")):
        if 候选 is None:
            continue
        文本 = str(候选).strip().lower()
        if 文本 == "at" or 文本.endswith(".at") or "componenttype.at" in 文本:
            return True
    return False


def 是否合并转发类型值(值: Any) -> bool:
    for 候选 in (值, 读取字段(值, "value"), 读取字段(值, "name")):
        if 候选 is None:
            continue
        文本 = str(候选).strip().lower()
        if 文本 in ("forward", "node", "nodes") or 文本.endswith((".forward", ".node", ".nodes")):
            return True
        if any(标记 in 文本 for 标记 in ("componenttype.forward", "componenttype.node", "componenttype.nodes")):
            return True
    return False


def 是否群名片消息段(消息段: Any) -> bool:
    if not isinstance(消息段, dict):
        return False
    if 消息段.get("type") == "json":
        return True
    if 消息段.get("type") != "contact":
        return False
    数据 = 消息段.get("data")
    if not isinstance(数据, dict):
        return False
    return str(数据.get("type") or "").lower() in ("group", "qq_group")


def 包含卡片标记(值: Any) -> bool:
    if 值 is None:
        return False
    if isinstance(值, list):
        return any(包含卡片标记(子值) for 子值 in 值)
    if isinstance(值, dict):
        return any(包含卡片标记(子值) for 子值 in 值.values())
    return bool(卡片消息规则.search(str(值)))


def 获取消息文本(event: AstrMessageEvent) -> str:
    事件文本 = 清理可见文本(str(getattr(event, "message_str", "") or ""))
    if 事件文本:
        return 事件文本

    消息对象 = getattr(event, "message_obj", None)
    候选文本 = []
    for 对象 in (消息对象,):
        if 对象 is None:
            continue
        for 字段名 in ("message",):
            文本 = 转成文本(读取字段(对象, 字段名))
            if 文本:
                候选文本.append(文本)

    for 文本 in 候选文本:
        if 是否需要撤回数字消息(文本):
            return 文本
    return 候选文本[0] if 候选文本 else ""


async def 尝试撤回当前消息(event: AstrMessageEvent) -> bool:
    if 是否At消息(event):
        logger.info("数字撤回跳过：普通@消息不撤回")
        return False

    消息编号 = 获取当前消息编号(event)
    if not 消息编号:
        logger.warning("数字撤回失败：当前事件缺少 message_id")
        return False

    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"数字撤回失败：当前事件缺少 bot 实例，message_id={消息编号}")
        return False

    try:
        await 使用_delete_msg撤回(bot, 消息编号)
        logger.info(f"数字撤回成功：message_id={消息编号}")
        return True
    except Exception as exc:
        logger.warning(f"数字撤回失败：message_id={消息编号}, error={exc}")
        return False


async def 尝试撤回触发用户最近消息(event: AstrMessageEvent) -> int:
    群号 = 获取群号(event)
    用户QQ = 获取发送者QQ(event)
    if not 是数字ID(群号) or not 是数字ID(用户QQ):
        logger.info(f"最近消息撤回跳过：缺少数字群号或用户QQ，group_id={群号}, user_id={用户QQ}")
        return 0

    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"最近消息撤回失败：当前事件缺少 bot 实例，group_id={群号}, user_id={用户QQ}")
        return 0

    try:
        历史消息 = await 获取群历史消息(bot, 群号, 最近消息撤回拉取数量)
    except Exception as exc:
        logger.warning(f"最近消息撤回获取历史失败：group_id={群号}, user_id={用户QQ}, error={exc}")
        return 0

    当前消息编号 = str(获取当前消息编号(event) or "")
    目标消息 = 筛选用户最近消息(历史消息, 用户QQ, 当前消息编号, 最近消息撤回数量)
    成功数量 = 0
    for 消息 in 目标消息:
        消息编号 = 消息.get("message_id") if isinstance(消息, dict) else None
        if not 消息编号:
            continue
        try:
            await 使用_delete_msg撤回(bot, 消息编号)
            成功数量 += 1
            logger.info(f"最近消息撤回成功：group_id={群号}, user_id={用户QQ}, message_id={消息编号}")
        except Exception as exc:
            logger.warning(f"最近消息撤回失败：group_id={群号}, user_id={用户QQ}, message_id={消息编号}, error={exc}")
    return 成功数量


async def 获取群历史消息(bot: Any, 群号: str, 数量: int) -> list[dict[str, Any]]:
    响应 = await 调用机器人动作(bot, "get_group_msg_history", group_id=int(群号), count=int(数量))
    if isinstance(响应, dict):
        数据 = 响应.get("data") if "data" in 响应 else 响应
        if isinstance(数据, dict):
            消息列表 = 数据.get("messages") or 数据.get("message") or []
        else:
            消息列表 = 响应.get("messages") or []
    else:
        消息列表 = []
    return [消息 for 消息 in 消息列表 if isinstance(消息, dict)]


def 筛选用户最近消息(历史消息: list[dict[str, Any]], 用户QQ: str, 排除消息编号: str = "", 数量: int = 最近消息撤回数量) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = []
    for 消息 in 历史消息:
        发送者 = 消息.get("sender") if isinstance(消息, dict) else None
        发送者QQ = ""
        if isinstance(发送者, dict):
            发送者QQ = str(发送者.get("user_id") or "").strip()
        if 发送者QQ != str(用户QQ):
            continue
        消息编号 = str(消息.get("message_id") or "").strip()
        if 排除消息编号 and 消息编号 == 排除消息编号:
            continue
        结果.append(消息)
    结果.sort(key=lambda 项目: 安全整数(项目.get("time"), 0), reverse=True)
    return 结果[: max(0, int(数量))]


async def 记录撤回触发并尝试踢出(event: AstrMessageEvent) -> None:
    群号 = 获取群号(event)
    用户QQ = 获取发送者QQ(event)
    if not 是数字ID(群号) or not 是数字ID(用户QQ):
        logger.info(f"数字撤回踢出跳过：缺少数字群号或用户QQ，group_id={群号}, user_id={用户QQ}")
        return

    计数键 = f"{群号}:{用户QQ}"
    当前次数 = 数字撤回触发次数.get(计数键, 0) + 1
    数字撤回触发次数[计数键] = 当前次数
    logger.info(f"数字撤回模块触发计数：group_id={群号}, user_id={用户QQ}, count={当前次数}/{数字撤回踢出阈值}")
    if 当前次数 < 数字撤回踢出阈值:
        return

    if await 尝试踢出成员(event, 群号, 用户QQ):
        数字撤回触发次数.pop(计数键, None)


async def 尝试踢出成员(event: AstrMessageEvent, 群号: str, 用户QQ: str) -> bool:
    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"数字撤回踢出失败：当前事件缺少 bot 实例，group_id={群号}, user_id={用户QQ}")
        return False

    try:
        await 使用_set_group_kick踢出(bot, 群号, 用户QQ)
        logger.info(f"数字撤回触发 {数字撤回踢出阈值} 次，已踢出成员：group_id={群号}, user_id={用户QQ}")
        await 尝试踢出其它群同一成员(bot, 群号, 用户QQ)
        return True
    except Exception as exc:
        logger.warning(f"数字撤回踢出失败：group_id={群号}, user_id={用户QQ}, error={exc}")
        return False


async def 尝试踢出其它群同一成员(bot: Any, 当前群号: str, 用户QQ: str) -> None:
    try:
        群号列表 = await 获取机器人所在群号列表(bot)
    except Exception as exc:
        logger.warning(f"跨群踢出获取群列表失败：user_id={用户QQ}, error={exc}")
        return

    for 群号 in 群号列表:
        群号 = str(群号)
        if 群号 == str(当前群号) or not 是数字ID(群号):
            continue
        try:
            if not await 检查群成员存在(bot, 群号, 用户QQ):
                continue
            await 使用_set_group_kick踢出(bot, 群号, 用户QQ)
            logger.info(f"跨群踢出成功：group_id={群号}, user_id={用户QQ}")
        except Exception as exc:
            logger.warning(f"跨群踢出失败：group_id={群号}, user_id={用户QQ}, error={exc}")


async def 检查群成员存在(bot: Any, 群号: str, 用户QQ: str) -> bool:
    try:
        响应 = await 调用机器人动作(bot, "get_group_member_info", group_id=int(群号), user_id=int(用户QQ), no_cache=True)
    except Exception:
        return False
    if not 响应:
        return False
    数据 = 响应.get("data") if isinstance(响应, dict) and "data" in 响应 else 响应
    if isinstance(数据, dict):
        返回用户 = 数据.get("user_id") or 数据.get("qq") or 数据.get("id")
        return str(返回用户 or 用户QQ).strip() == str(用户QQ)
    return True


async def 尝试踢出指定成员(event: AstrMessageEvent, 群号: str, 用户QQ: str) -> None:
    bot = getattr(event, "bot", None)
    if bot is None:
        raise RuntimeError("当前事件缺少 bot 实例")
    await 使用_set_group_kick踢出(bot, 群号, 用户QQ)


async def 尝试设置全员禁言(event: AstrMessageEvent, 群号: str, 启用: bool) -> None:
    bot = getattr(event, "bot", None)
    if bot is None:
        raise RuntimeError("当前事件缺少 bot 实例")
    await 使用_set_group_whole_ban禁言(bot, 群号, 启用)


def 获取当前消息编号(event: AstrMessageEvent) -> Any:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        if 对象 is None:
            continue
        if isinstance(对象, dict):
            消息编号 = 对象.get("message_id") or 对象.get("id")
        else:
            消息编号 = getattr(对象, "message_id", None) or getattr(对象, "id", None)
        if 消息编号:
            return 消息编号
    return None


def 获取群号(event: AstrMessageEvent) -> str:
    for 方法名 in ("get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "group_id") or 读取字段(对象, "group")
        if isinstance(值, dict):
            值 = 值.get("group_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 获取发送者QQ(event: AstrMessageEvent) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "sender_id") or 读取字段(对象, "user_id") or 读取字段(对象, "sender")
        if isinstance(值, dict):
            值 = 值.get("user_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 是数字ID(值: Any) -> bool:
    return bool(数字ID规则.fullmatch(str(值 or "").strip()))


def 读取字段(对象: Any, 字段名: str) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 转成文本(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, str):
        return 清理可见文本(值)
    if isinstance(值, list):
        return 清理可见文本("".join(转消息段文本(消息段) for 消息段 in 值))
    if isinstance(值, dict):
        return 清理可见文本(转消息段文本(值))
    return ""


def 清理可见文本(文本: str) -> str:
    文本 = re.sub(r"\[CQ:reply,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[CQ:at,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[At:[^\]]+\]", "", 文本)
    return 文本.strip()


def 转消息段文本(消息段: Any) -> str:
    if not isinstance(消息段, dict):
        return ""
    if 消息段.get("type") != "text":
        return ""
    数据 = 消息段.get("data")
    if isinstance(数据, dict):
        return str(数据.get("text") or "")
    return ""


def 限制长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    if len(文本) > 最大长度:
        return 文本[:最大长度] + "..."
    return 文本


def 描述值(值: Any) -> str:
    if 值 is None:
        return "None"
    if isinstance(值, list):
        return "[" + ", ".join(描述消息段(消息段) for 消息段 in 值) + "]"
    return 描述消息段(值)


def 描述消息段(消息段: Any) -> str:
    if isinstance(消息段, dict):
        return 限制长度(
            {
                "class": type(消息段).__name__,
                "type": 消息段.get("type"),
                "data": 消息段.get("data"),
                "str": str(消息段),
            }
        )
    return 限制长度(
        {
            "class": type(消息段).__name__,
            "type": 读取字段(消息段, "type"),
            "data": 读取字段(消息段, "data"),
            "value": 读取字段(消息段, "value"),
            "name": 读取字段(消息段, "name"),
            "str": str(消息段),
        }
    )


async def 使用_delete_msg撤回(bot: Any, 消息编号: Any) -> bool:
    撤回方法 = getattr(bot, "delete_msg", None)
    if not callable(撤回方法):
        raise RuntimeError("当前 bot 没有 delete_msg 撤回接口")
    await 撤回方法(message_id=消息编号)
    return True


async def 调用机器人动作(bot: Any, 动作名: str, **参数: Any) -> Any:
    动作方法 = getattr(bot, 动作名, None)
    if callable(动作方法):
        return await 等待可能异步结果(动作方法(**参数))

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        return await 等待可能异步结果(调用动作(动作名, **参数))

    raise RuntimeError(f"当前 bot 没有 {动作名} 接口")


async def 等待可能异步结果(结果: Any) -> Any:
    if inspect.isawaitable(结果):
        return await 结果
    return 结果


async def 使用_set_group_kick踢出(bot: Any, 群号: str, 用户QQ: str) -> bool:
    群号值 = int(群号)
    用户QQ值 = int(用户QQ)
    踢出方法 = getattr(bot, "set_group_kick", None)
    if callable(踢出方法):
        await 踢出方法(group_id=群号值, user_id=用户QQ值, reject_add_request=False)
        return True

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        await 调用动作("set_group_kick", group_id=群号值, user_id=用户QQ值, reject_add_request=False)
        return True

    raise RuntimeError("当前 bot 没有 set_group_kick 踢出接口")


async def 使用_set_group_whole_ban禁言(bot: Any, 群号: str, 启用: bool = True) -> bool:
    群号值 = int(群号)
    禁言方法 = getattr(bot, "set_group_whole_ban", None)
    if callable(禁言方法):
        await 禁言方法(group_id=群号值, enable=启用)
        return True

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        await 调用动作("set_group_whole_ban", group_id=群号值, enable=启用)
        return True

    raise RuntimeError("当前 bot 没有 set_group_whole_ban 全员禁言接口")


def 安全整数(值: Any, 默认值: int = 0) -> int:
    if 值 in (None, "") or isinstance(值, bool):
        return 默认值
    try:
        return int(str(值).strip())
    except Exception:
        return 默认值
