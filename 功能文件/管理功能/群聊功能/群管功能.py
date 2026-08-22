from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from astrbot.api.event import AstrMessageEvent
except Exception:
    AstrMessageEvent = Any

try:
    from astrbot.api import message_components as Comp
except Exception:
    Comp = None

from 功能文件.管理功能.基础功能.权限工具 import (
    是QQ官方机器人,
    是群文件清理管理员,
)
from 功能文件.管理功能.群聊功能.群列表工具 import (
    删除官方群成员映射,
    获取官方群成员标识,
    获取官方群用户标识,
    获取机器人所在群号列表,
    记录官方群成员映射,
    记录机器人所在群号,
)

数字撤回规则 = re.compile(r"(?<!\d)\d{9,12}(?!\d)")
链接规则 = re.compile(
    r"https?://|https?%3A%2F%2F|qb://|qb%3A%2F%2F|\b\w+\.\w+/", re.IGNORECASE
)
白名单域名规则 = re.compile(
    r"changdunovel\.com|fanqienovel\.com|fqnovel\.com|novelfm\.com|qimao\.com|app-share\.wtzw\.com|shuqi\.com|shuqireader\.com|reader\.qq\.com|book\.qq\.com|bookshelf\.html5\.qq\.com|novel\.html5\.qq\.com|qbnovel\.qq\.com|qb(?::|%3A)(?:/|%2F){2}ext(?:/|%2F)novelreader|palmestore\.com|zhangyue\.com|ireader\.com|dianzhong\.com|mr\.baidu\.com|boxnovel\.baidu\.com|novel\.baidu\.com|reader\.browser\.miui\.com|reader\.miui\.com|novel\.browser\.miui\.com|dushu\.xiaomi\.com|ieasou\.com|easou\.com|midureader\.com|sfacg\.com|kuwo\.cn|kuwo\.com|kujiang\.com|lc1001\.com|jjwxc\.net|jjwxc\.com|soia\.zhihu\.com|story\.zhihu\.com",
    re.IGNORECASE,
)
QQ阅读小程序白名单规则 = re.compile(
    r"(?:微信小程序|小程序).{0,2000}(?:source|来源)\s*[:：=]\s*[\"']?QQ阅读"
    r"|(?:source|来源)\s*[:：=]\s*[\"']?QQ阅读.{0,2000}(?:微信小程序|小程序)",
    re.IGNORECASE | re.DOTALL,
)
群名片规则 = re.compile(r"\[CQ:contact,[^\]]*(?:type=group|type=qq_group)[^\]]*\]")
卡片消息规则 = re.compile(
    r"ComponentType\.(?:Json|Share|Contact)|\[CQ:(?:json|contact),|\[卡片消息\]|暂不能查看该消息内容",
    re.IGNORECASE,
)
At消息规则 = re.compile(
    r"\[CQ:at,[^\]]*\]|\[At:[^\]]+\]|<@!?[A-Za-z0-9_-]{5,64}>|ComponentType\.At",
    re.IGNORECASE,
)
合并转发规则 = re.compile(
    r"ComponentType\.(?:Forward|Node|Nodes)|\[CQ:(?:forward|node),|群聊的聊天记录|查看\d+条转发消息|\[合并转发消息\]",
    re.IGNORECASE,
)
闪传消息规则 = re.compile(
    r"QQ闪传|该消息类型暂不支持查看|\[闪传(?:消息)?\]", re.IGNORECASE
)
数字ID规则 = re.compile(r"[1-9]\d{4,11}")
用户编号规则 = re.compile(r"^[A-Za-z0-9_-]{5,64}$")
管理员QQ规则 = re.compile(r"^\d{5,12}$")
数字撤回踢出阈值 = 3
最近消息撤回数量 = 8
最近消息撤回拉取数量 = 100
踢人消息撤回数量 = 50
踢人消息撤回拉取数量 = 100
广告撤回禁言时长表 = (3 * 60, 10 * 60, 30 * 60, 86400, 30 * 86400)
数字撤回触发次数: dict[str, int] = {}
数字撤回处理锁: asyncio.Lock | None = None
数字撤回处理中: set[str] = set()
数字撤回完成时间: dict[str, float] = {}
数字撤回去重缓存秒数 = 120.0
群管功能模块版本 = "1.25.1"
踢出命令集合 = {"踢", "踢了", "踢人"}
QQ群管理角色集合 = {"owner", "admin", "群主", "管理员"}
QQ官方机器人权限缓存秒数 = 30.0
QQ官方机器人权限缓存: dict[tuple[int, str], tuple[float, bool]] = {}
QQ官方机器人权限锁: asyncio.Lock | None = None
单用户禁言前缀 = ("解除禁言", "解禁", "解", "禁言用户", "单独禁言", "禁言", "禁")
单用户禁言默认秒数 = 7 * 86400
单用户禁言时长规则 = re.compile(
    r"(?<!\d)(\d{1,8})\s*(秒钟|秒|分钟|分|小时|时|天|s|m|h|d)?(?!\w)",
    re.IGNORECASE,
)


async def 处理用户踢出(event: AstrMessageEvent, 命令文本: str, 配置: Any) -> str | None:
    return None


async def 处理群禁言(event: AstrMessageEvent, 命令文本: str, 配置: Any) -> str | None:
    单用户参数 = 解析单用户禁言参数(event, 命令文本)
    if 单用户参数 is not None:
        if not 是群文件清理管理员(event, 配置):
            return None

        群号 = 获取群号(event)
        目标列表 = list(单用户参数.get("targets") or [])
        if not 群号:
            return "成员禁言失败：只能在群聊中使用"
        if not 目标列表:
            return "成员禁言失败：请@要操作的成员"

        bot = getattr(event, "bot", None)
        if bot is None:
            return "成员禁言失败，请稍后再试"
        if not await QQ官方机器人具备群管权限(bot, 群号):
            logger.info("群禁言跳过：QQ官方机器人不是群管理员，group_id=%s", 群号)
            return None

        操作 = str(单用户参数.get("operation") or "add")
        秒数 = 单用户参数.get("seconds")
        成功数量 = 0
        for 用户 in 目标列表:
            try:
                # QQ 官方群只能从当前 @ 消息拿到目标成员 OpenID；官方没有
                # 通用的“查询指定成员是否在群内”接口。当前命令既然能解析
                # 出有效的群内 @，直接交给官方禁言接口处理，避免把接口不
                # 支持误判成“成员不在群内”，导致“解”无法执行。
                if str(群号).strip().isdigit() and not await 检查群成员存在(
                    bot, 群号, 用户
                ):
                    logger.info(
                        "群禁言跳过：目标成员不在群内，group_id=%s, user_id=%s",
                        群号,
                        用户,
                    )
                    continue
                await 使用_set_group_ban禁言(
                    bot,
                    群号,
                    用户,
                    int(秒数 or 0),
                    操作,
                )
                成功数量 += 1
                await 同步成员禁言到其它群(
                    bot,
                    群号,
                    用户,
                    int(秒数 or 0),
                    操作,
                )
            except Exception as exc:
                logger.warning(
                    "成员禁言失败：group_id=%s, user_id=%s, operation=%s, error_type=%s",
                    群号,
                    用户,
                    操作,
                    type(exc).__name__,
                )

        if 操作 == "del":
            return None
        if 成功数量 != len(目标列表):
            return "成员禁言失败，请稍后再试"
        return 构造成员禁言成功回复(event, 目标列表)


def 踢人功能是否开启(配置: Any = None) -> bool:
    return False


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


def 获取群禁言候选文本(event: AstrMessageEvent, 命令文本: str) -> list[str]:
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
    return 候选列表


def 解析单用户禁言参数(event: AstrMessageEvent, 命令文本: str) -> dict[str, Any] | None:
    """解析「禁言/禁 @成员 [时长]」和「解除禁言/解 @成员」。"""
    for 候选 in 获取群禁言候选文本(event, 命令文本):
        文本 = 清理踢出命令文本(候选)
        if not 文本:
            continue

        命令前缀 = next(
            (
                前缀
                for 前缀 in sorted(单用户禁言前缀, key=len, reverse=True)
                if (
                    文本 == 前缀
                    or 文本.startswith(前缀 + " ")
                    or (
                        文本.startswith(前缀)
                        and len(文本) > len(前缀)
                        and 文本[len(前缀)].isdigit()
                    )
                )
            ),
            None,
        )
        if 命令前缀 is None:
            continue

        操作 = "del" if 命令前缀 in {"解除禁言", "解禁", "解"} else "add"
        参数文本 = 文本[len(命令前缀) :].strip()
        秒数: int | None = None
        if 操作 != "del":
            匹配 = 单用户禁言时长规则.search(参数文本)
            if 匹配:
                数值 = int(匹配.group(1))
                单位 = (匹配.group(2) or "天").lower()
                倍数 = {
                    "秒钟": 1,
                    "秒": 1,
                    "s": 1,
                    "分钟": 60,
                    "分": 60,
                    "m": 60,
                    "小时": 3600,
                    "时": 3600,
                    "h": 3600,
                    "天": 86400,
                    "d": 86400,
                }.get(单位, 60)
                秒数 = max(1, 数值 * 倍数)
            else:
                秒数 = 单用户禁言默认秒数

        return {
            "targets": 提取被艾特用户QQ列表(event),
            "seconds": 秒数,
            "operation": 操作,
            "command": 命令前缀,
        }

    return None


def 构造成员禁言成功回复(event: AstrMessageEvent, 用户列表: list[str]) -> str:
    """禁言成功后提及被禁言成员，避免只回复操作者。"""
    行列表: list[str] = []
    for 用户 in 去重保序(用户列表):
        if 是QQ官方机器人(event):
            提及 = f"<@{用户}>"
        else:
            提及 = f"[CQ:at,qq={用户}]"
        行列表.append(f"{提及} 你已经被禁言，请联系群主说明情况")
    return "\n".join(行列表)


def 格式化批量踢出结果(
    成功用户: list[str],
    失败用户: list[tuple[str, Exception]],
    撤回数量记录: dict[str, int] | None = None,
) -> str:
    行列表 = [f"用户踢出完成：成功 {len(成功用户)} 个，失败 {len(失败用户)} 个"]
    if 成功用户:
        行列表.append(f"已踢出用户：{格式化用户列表(成功用户)}")
    if 撤回数量记录:
        行列表.append(
            "已撤回消息："
            + "；".join(f"{用户} {撤回数量记录.get(用户, 0)} 条" for 用户 in 成功用户)
        )
    if 失败用户:
        行列表.append(
            "失败用户：" + "；".join(f"{用户}：{错误}" for 用户, 错误 in 失败用户)
        )
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
                or 读取字段(消息.get("data"), "member_openid")
                or 读取字段(消息.get("data"), "user_openid")
                or 读取字段(消息.get("data"), "openid")
            )
            if 用户:
                结果.append(用户)
        for 子值 in 消息.values():
            结果.extend(从消息段提取At用户列表(子值))
        return 结果
    if Comp is not None:
        try:
            if isinstance(消息, Comp.At):
                用户 = 规范化用户编号(
                    getattr(消息, "qq", "")
                    or getattr(消息, "member_openid", "")
                    or getattr(消息, "user_openid", "")
                    or getattr(消息, "openid", "")
                )
                return [用户] if 用户 else []
        except Exception:
            pass
    if 是否At类型值(读取字段(消息, "type")):
        用户 = 规范化用户编号(
            读取字段(消息, "qq")
            or 读取字段(消息, "user_id")
            or 读取字段(消息, "member_openid")
            or 读取字段(消息, "user_openid")
            or 读取字段(消息, "openid")
            or 读取字段(读取字段(消息, "data"), "qq")
            or 读取字段(读取字段(消息, "data"), "user_id")
            or 读取字段(读取字段(消息, "data"), "member_openid")
            or 读取字段(读取字段(消息, "data"), "user_openid")
            or 读取字段(读取字段(消息, "data"), "openid")
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
    for 匹配 in re.finditer(r"<@!?([A-Za-z0-9_-]{5,64})>", 原文):
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
    结果 = re.sub(r"<@!?[A-Za-z0-9_-]{5,64}>", "", 结果)
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
    return 文本 if 用户编号规则.fullmatch(文本) else ""


async def 处理数字撤回(event: AstrMessageEvent, 配置: Any = None) -> bool:
    消息文本 = 获取消息文本(event)
    if not 是否需要撤回消息(event, 消息文本):
        logger.debug("撤回检查跳过")
        return False
    去重键 = await 开始数字撤回去重(event)
    if 去重键 == "":
        logger.info(
            "数字撤回去重跳过：消息正在处理或已处理，group_id=%s, message_id=%s",
            获取群号(event),
            获取当前消息编号(event),
        )
        return False

    撤回成功 = False
    try:
        if await 是否发送者为QQ群主或管理员(event):
            logger.info(
                "数字撤回跳过：QQ群主/管理员消息不撤回，"
                f"group_id={获取群号(event)}, user_id={获取发送者QQ(event)}"
            )
            return False
        bot = getattr(event, "bot", None)
        群号 = 获取群号(event)
        if bot is None or not await QQ官方机器人具备群管权限(bot, 群号):
            logger.info("撤回跳过：QQ官方机器人不是群管理员，group_id=%s", 群号)
            return False
        卡片类型 = 获取卡片撤回类型(event)
        if 卡片类型:
            logger.debug(f"卡片撤回规则命中：类型={卡片类型}")
        撤回成功 = await 尝试撤回当前消息(event)
        if 撤回成功:
            await 尝试撤回触发用户最近消息(event)
            触发次数 = await 记录撤回触发并尝试踢出(event, 配置)
            if 触发次数:
                禁言秒数 = 计算广告撤回禁言秒数(触发次数)
                禁言成功 = await 尝试广告撤回禁言(event, 禁言秒数, 触发次数)
                if 禁言成功:
                    await 发送撤回广告提醒(event)
        return 撤回成功
    finally:
        await 结束数字撤回去重(去重键, 撤回成功)


async def 开始数字撤回去重(event: AstrMessageEvent) -> str | None:
    消息编号 = str(获取当前消息编号(event) or "").strip()
    if not 消息编号:
        return None
    群号 = str(获取群号(event) or "").strip()
    去重键 = f"{群号}:{消息编号}"

    global 数字撤回处理锁
    if 数字撤回处理锁 is None:
        数字撤回处理锁 = asyncio.Lock()
    当前时间 = time.monotonic()
    async with 数字撤回处理锁:
        for 键, 时间戳 in list(数字撤回完成时间.items()):
            if 当前时间 - 时间戳 >= 数字撤回去重缓存秒数:
                数字撤回完成时间.pop(键, None)
        if 去重键 in 数字撤回处理中 or 去重键 in 数字撤回完成时间:
            return ""
        数字撤回处理中.add(去重键)
    return 去重键


async def 结束数字撤回去重(去重键: str | None, 成功: bool) -> None:
    if not 去重键:
        return
    global 数字撤回处理锁
    if 数字撤回处理锁 is None:
        数字撤回处理锁 = asyncio.Lock()
    async with 数字撤回处理锁:
        数字撤回处理中.discard(去重键)
        if 成功:
            数字撤回完成时间[去重键] = time.monotonic()


def 计算广告撤回禁言秒数(触发次数: int) -> int:
    """按同一成员跨群累计的撤回次数递增禁言时长，超过第五次保持 30 天。"""
    次数 = max(1, int(触发次数 or 1))
    return 广告撤回禁言时长表[min(次数, len(广告撤回禁言时长表)) - 1]


def 获取撤回发送者标识(event: AstrMessageEvent) -> str:
    """读取 OneBot user_id 或 QQ 官方 author.member_openid。"""
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("sender", "author", "member", "user"):
            发送者 = 读取字段(对象, 字段名)
            for 标识字段 in (
                "member_openid",
                "user_openid",
                "openid",
                "user_id",
                "qq",
                "id",
            ):
                标识 = 规范化用户编号(读取字段(发送者, 标识字段))
                if 标识:
                    return 标识
        for 标识字段 in (
            "member_openid",
            "user_openid",
            "openid",
            "sender_id",
            "user_id",
            "qq",
        ):
            标识 = 规范化用户编号(读取字段(对象, 标识字段))
            if 标识:
                return 标识
    return ""


def 获取撤回发送者统一标识(event: AstrMessageEvent) -> str:
    """读取可跨 QQ 官方群复用的 user_openid，OneBot 场景返回 QQ 号。"""
    官方 = 是QQ官方机器人(event)
    消息对象 = getattr(event, "message_obj", None)
    对象列表 = (event, 消息对象)
    if 官方:
        标识字段 = ("user_openid", "openid")
    else:
        标识字段 = ("user_id", "qq", "openid")
    for 对象 in 对象列表:
        if 对象 is None:
            continue
        for 字段名 in ("sender", "author", "member", "user"):
            发送者 = 读取字段(对象, 字段名)
            for 标识字段名 in 标识字段:
                标识 = 规范化用户编号(读取字段(发送者, 标识字段名))
                if 标识:
                    return 标识
        for 标识字段名 in 标识字段:
            标识 = 规范化用户编号(读取字段(对象, 标识字段名))
            if 标识:
                return 标识
    return ""


def 记录当前群成员映射(event: AstrMessageEvent, 群号: str) -> None:
    """从当前官方群消息记录 user_openid 与本群 member_openid。"""
    群号文本 = str(群号 or "").strip()
    if not 群号文本 or 是数字ID(群号文本):
        return
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        候选对象 = [对象] + [
            读取字段(对象, 字段名) for 字段名 in ("sender", "author", "member", "user")
        ]
        for 候选 in 候选对象:
            if 候选 is None:
                continue
            成员 = 规范化用户编号(读取字段(候选, "member_openid"))
            用户 = 规范化用户编号(
                读取字段(候选, "user_openid") or 读取字段(候选, "openid")
            )
            if 成员 and 用户:
                记录官方群成员映射(群号文本, 用户, 成员)
                break
        for 字段名 in ("message", "components", "content", "raw_message"):
            记录消息段成员映射(读取字段(对象, 字段名), 群号文本)


def 记录消息段成员映射(消息: Any, 群号: str) -> None:
    if 消息 is None or not 群号:
        return
    if isinstance(消息, (list, tuple, set)):
        for 消息段 in 消息:
            记录消息段成员映射(消息段, 群号)
        return
    if isinstance(消息, dict):
        数据 = 消息.get("data") if isinstance(消息.get("data"), dict) else 消息
        成员 = 规范化用户编号(数据.get("member_openid"))
        用户 = 规范化用户编号(数据.get("user_openid") or 数据.get("openid"))
        if 成员 and 用户:
            记录官方群成员映射(群号, 用户, 成员)
        for 子值 in 消息.values():
            if isinstance(子值, (dict, list, tuple, set)):
                记录消息段成员映射(子值, 群号)
        return
    成员 = 规范化用户编号(getattr(消息, "member_openid", None))
    用户 = 规范化用户编号(
        getattr(消息, "user_openid", None) or getattr(消息, "openid", None)
    )
    if 成员 and 用户:
        记录官方群成员映射(群号, 用户, 成员)


async def 尝试广告撤回禁言(event: AstrMessageEvent, 秒数: int, 触发次数: int) -> bool:
    群号 = 获取群号(event)
    用户标识 = 获取撤回发送者标识(event)
    跨群用户标识 = 获取撤回发送者统一标识(event)
    bot = getattr(event, "bot", None)
    if not 群号 or not 用户标识 or bot is None:
        logger.warning(
            "广告撤回自动禁言跳过：缺少群或成员标识，count=%s",
            触发次数,
        )
        return False
    try:
        await 使用_set_group_ban禁言(bot, 群号, 用户标识, 秒数, "add")
        同步成功数, 同步失败数 = await 同步成员禁言到其它群(
            bot,
            群号,
            用户标识,
            秒数,
            "add",
            跨群用户标识=跨群用户标识,
        )
        logger.info(
            "广告撤回自动禁言成功：group_id=%s, user_id=%s, count=%s, seconds=%s, "
            "cross_group_success=%s, cross_group_failed=%s",
            群号,
            用户标识,
            触发次数,
            秒数,
            同步成功数,
            同步失败数,
        )
        return True
    except Exception as exc:
        logger.warning(
            "广告撤回自动禁言失败：group_id=%s, user_id=%s, count=%s, error_type=%s",
            群号,
            用户标识,
            触发次数,
            type(exc).__name__,
        )
        return False


def 获取撤回发送者提及(event: AstrMessageEvent) -> str:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("sender", "author", "member", "user"):
            发送者 = 读取字段(对象, 字段名)
            for 标识字段 in ("member_openid", "user_openid", "openid", "user_id", "id"):
                标识 = str(读取字段(发送者, 标识字段) or "").strip()
                if 标识:
                    if 是QQ官方机器人(event):
                        return (
                            f"<@{标识}>"
                            if not 标识.isdigit() and 用户编号规则.fullmatch(标识)
                            else "发送者"
                        )
                    return (
                        f"[CQ:at,qq={标识}]"
                        if 管理员QQ规则.fullmatch(标识)
                        else "发送者"
                    )
        for 字段名 in (
            "member_openid",
            "user_openid",
            "openid",
            "sender_id",
            "user_id",
        ):
            标识 = str(读取字段(对象, 字段名) or "").strip()
            if 标识:
                if 是QQ官方机器人(event):
                    return (
                        f"<@{标识}>"
                        if not 标识.isdigit() and 用户编号规则.fullmatch(标识)
                        else "发送者"
                    )
                return (
                    f"[CQ:at,qq={标识}]" if 管理员QQ规则.fullmatch(标识) else "发送者"
                )
    return "发送者"


def 构造撤回广告提醒(event: AstrMessageEvent) -> str:
    return f"{获取撤回发送者提及(event)}\n请勿发送此类消息\n如果是小说请联系群主"


async def 发送撤回广告提醒(event: AstrMessageEvent) -> bool:
    文本 = 构造撤回广告提醒(event)
    try:
        if 是QQ官方机器人(event):
            from 功能文件.管理功能.基础功能 import 帮助功能

            return bool(
                await 帮助功能.发送Markdown键盘消息(
                    event,
                    文本,
                    None,
                    主动发送=True,
                    自动提及=False,
                )
            )
        发送方法 = getattr(event, "send", None)
        if not callable(发送方法):
            return False
        发送结果 = 发送方法(event.plain_result(文本))
        await 等待可能异步结果(发送结果)
        return True
    except Exception as exc:
        logger.warning(
            "广告撤回提醒发送失败：error_type=%s",
            type(exc).__name__,
        )
        return False


async def 是否发送者为QQ群主或管理员(event: AstrMessageEvent) -> bool:
    事件角色 = 提取事件发送者群角色(event)

    群号 = 获取群号(event)
    用户QQ = 获取发送者QQ(event)
    if not 群号 or not 用户QQ:
        结果 = 是QQ群管理角色(事件角色)
        logger.info(
            f"群管理身份检查: 群号={群号}, 用户QQ={用户QQ}, 事件角色={事件角色!r}, 结果={结果}(缺少群号或用户QQ)"
        )
        return 结果

    bot = getattr(event, "bot", None)
    if bot is None:
        结果 = 是QQ群管理角色(事件角色)
        logger.info(
            f"群管理身份检查: 群号={群号}, 用户QQ={用户QQ}, 事件角色={事件角色!r}, 结果={结果}(缺少bot)"
        )
        return 结果

    try:
        群号值 = int(群号)
        用户QQ值 = int(用户QQ)
        响应 = await 调用机器人动作(
            bot,
            "get_group_member_info",
            group_id=群号值,
            user_id=用户QQ值,
            no_cache=True,
        )
    except (ValueError, TypeError):
        try:
            响应 = await 调用机器人动作(
                bot,
                "get_group_member_info",
                group_openid=群号,
                user_openid=用户QQ,
                no_cache=True,
            )
        except Exception as exc:
            结果 = 是QQ群管理角色(事件角色)
            logger.info(
                f"群管理身份检查: 群号={群号}, 用户QQ={用户QQ}, 事件角色={事件角色!r}, 结果={结果}(openid查询异常: {exc})"
            )
            return 结果
    except Exception as exc:
        结果 = 是QQ群管理角色(事件角色)
        logger.info(
            f"群管理身份检查: 群号={群号}, 用户QQ={用户QQ}, 事件角色={事件角色!r}, 结果={结果}(数字ID查询异常: {exc})"
        )
        return 结果

    数据 = 响应.get("data") if isinstance(响应, dict) and "data" in 响应 else 响应
    if isinstance(数据, dict):
        角色 = 数据.get("role")
        结果 = 是QQ群管理角色(角色)
        logger.info(
            f"群管理身份检查: 群号={群号}, 用户QQ={用户QQ}, 事件角色={事件角色!r}, API角色={角色!r}, 结果={结果}"
        )
        return 结果
    结果 = 是QQ群管理角色(事件角色)
    logger.info(
        f"群管理身份检查: 群号={群号}, 用户QQ={用户QQ}, 事件角色={事件角色!r}, 结果={结果}(API返回非dict)"
    )
    return 结果


def 提取事件发送者群角色(event: AstrMessageEvent) -> str:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        角色 = 提取对象发送者角色(对象)
        if 角色:
            return 角色
    return ""


def 提取对象发送者角色(对象: Any) -> str:
    if 对象 is None:
        return ""
    for 字段名 in ("author",):
        子对象 = 读取字段(对象, 字段名)
        角色 = 读取首个字段(子对象, ("member_role", "role", "sender_role", "user_role"))
        if 角色:
            return str(角色).strip()

    for 字段名 in ("raw_message", "raw", "payload", "data", "event"):
        原始对象 = 读取字段(对象, 字段名)
        角色 = 提取原始数据发送者角色(原始对象)
        if 角色:
            return 角色

    for 字段名 in ("sender", "member", "user"):
        子对象 = 读取字段(对象, 字段名)
        角色 = 读取首个字段(子对象, ("member_role", "role", "sender_role", "user_role"))
        if 角色:
            return str(角色).strip()

    直接角色 = 读取首个字段(对象, ("member_role", "role", "sender_role", "user_role"))
    if 直接角色:
        return str(直接角色).strip()
    return ""


def 提取原始数据发送者角色(原始对象: Any) -> str:
    if 原始对象 is None:
        return ""
    if isinstance(原始对象, str):
        文本 = 原始对象.strip()
        if not (文本.startswith("{") and "role" in 文本):
            return ""
        try:
            原始对象 = json.loads(文本)
        except Exception:
            return ""
    if not isinstance(原始对象, dict):
        return ""
    for 字段名 in ("author", "d", "data", "event"):
        子对象 = 原始对象.get(字段名)
        角色 = 提取原始数据发送者角色(子对象)
        if 角色:
            return 角色
    for 字段名 in ("sender", "member", "user"):
        子对象 = 原始对象.get(字段名)
        角色 = 提取原始数据发送者角色(子对象)
        if 角色:
            return 角色
    直接角色 = 读取首个字段(
        原始对象, ("member_role", "role", "sender_role", "user_role")
    )
    if 直接角色:
        return str(直接角色).strip()
    return ""


def 读取首个字段(对象: Any, 字段列表: tuple[str, ...]) -> Any:
    for 字段名 in 字段列表:
        值 = 读取字段(对象, 字段名)
        if 值 not in (None, ""):
            return 值
    return None


def 是QQ群管理角色(角色: Any) -> bool:
    return str(角色 or "").strip().lower() in QQ群管理角色集合


def 提取QQ官方机器人群角色(响应: Any) -> str:
    """提取 QQ 官方 bot_state 返回的 member_role。"""
    数据 = 响应
    if isinstance(响应, dict) and "data" in 响应:
        数据 = 响应.get("data")
    if isinstance(数据, dict):
        角色 = 数据.get("member_role") or 数据.get("role")
    else:
        角色 = getattr(数据, "member_role", None) or getattr(数据, "role", None)
    return str(角色 or "").strip().lower()


async def 获取QQ官方机器人群角色(bot: Any, 群号: str) -> str:
    """请求 QQ 官方群 bot_state；非官方数字群不走该接口。"""
    群号文本 = str(群号 or "").strip()
    if not 群号文本 or 群号文本.isdigit():
        return ""
    api = getattr(bot, "api", None)
    http客户端 = getattr(api, "_http", None) if api else None
    if http客户端 is None:
        raise RuntimeError("当前 bot 没有 QQ 官方 HTTP 客户端")

    from botpy.http import Route

    路由 = Route(
        "GET",
        "/v2/groups/{group_openid}/bot_state",
        group_openid=群号文本,
    )
    响应 = await http客户端.request(路由)
    角色 = 提取QQ官方机器人群角色(响应)
    if not 角色:
        raise RuntimeError("QQ 官方 bot_state 未返回 member_role")
    return 角色


async def QQ官方机器人具备群管权限(
    bot: Any,
    群号: str,
    *,
    未缓存时允许: bool = False,
) -> bool:
    """只有 QQ 官方机器人为群主/管理员时才允许撤回和禁言。"""
    群号文本 = str(群号 or "").strip()
    if not 群号文本 or 群号文本.isdigit():
        return True

    global QQ官方机器人权限锁
    if QQ官方机器人权限锁 is None:
        QQ官方机器人权限锁 = asyncio.Lock()

    缓存键 = (id(bot), 群号文本)
    当前时间 = time.monotonic()
    缓存 = QQ官方机器人权限缓存.get(缓存键)
    if 缓存 and 当前时间 - 缓存[0] < QQ官方机器人权限缓存秒数:
        return 缓存[1]
    if 未缓存时允许:
        return True

    async with QQ官方机器人权限锁:
        当前时间 = time.monotonic()
        缓存 = QQ官方机器人权限缓存.get(缓存键)
        if 缓存 and 当前时间 - 缓存[0] < QQ官方机器人权限缓存秒数:
            return 缓存[1]
        try:
            角色 = await 获取QQ官方机器人群角色(bot, 群号文本)
            允许 = 角色 in {"owner", "admin"}
        except Exception as exc:
            允许 = False
            logger.debug(
                "QQ官方机器人群权限获取失败：group_id=%s, error_type=%s",
                群号文本,
                type(exc).__name__,
            )
            角色 = "unknown"
        QQ官方机器人权限缓存[缓存键] = (time.monotonic(), 允许)
        if not 允许:
            logger.debug(
                "QQ官方机器人群管权限不足：group_id=%s, member_role=%s",
                群号文本,
                角色,
            )
        return 允许


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
    当前文本 = 文本
    for _ in range(3):
        if 链接规则.search(当前文本):
            return False
        解码文本 = unquote(当前文本)
        if 解码文本 == 当前文本:
            break
        当前文本 = 解码文本
    return bool(数字撤回规则.search(文本))


def 是否白名单消息(event: AstrMessageEvent, 消息文本: str = "") -> bool:
    if 包含QQ阅读小程序白名单(消息文本):
        return True
    if 包含白名单域名(消息文本):
        return True
    for 文本 in 获取原始文本候选(event):
        if 包含QQ阅读小程序白名单(文本):
            return True
        if 包含白名单域名(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含QQ阅读小程序白名单(消息):
            return True
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


def 是否At消息(event: AstrMessageEvent) -> bool:
    for 文本 in 获取原始文本候选(event):
        去除At机器人文本 = re.sub(r"\[At:qq_official\]", "", 文本)
        if At消息规则.search(去除At机器人文本):
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
        return 是否合并转发消息段(值) or any(
            包含合并转发标记(子值) for 子值 in 值.values()
        )
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
    当前文本 = str(值).replace("\\/", "/")
    for _ in range(3):
        if 白名单域名规则.search(当前文本):
            return True
        解码文本 = unquote(当前文本)
        if 解码文本 == 当前文本:
            break
        当前文本 = 解码文本
    数据 = 读取字段(值, "data")
    return 数据 is not None and 数据 is not 值 and 包含白名单域名(数据)


def 包含QQ阅读小程序白名单(值: Any) -> bool:
    """放行来源明确为 QQ 阅读的小程序/卡片分享，避免误伤正常书籍分享。"""
    if 值 is None:
        return False
    if isinstance(值, (list, tuple, set)):
        return any(包含QQ阅读小程序白名单(子值) for 子值 in 值)
    if isinstance(值, dict):
        小写字段 = {str(键).lower(): 子值 for 键, 子值 in 值.items()}
        来源值 = next(
            (
                小写字段.get(键)
                for 键 in ("source", "来源", "source_name", "app_source", "provider")
                if 小写字段.get(键) is not None
            ),
            None,
        )
        来源文本 = re.sub(r"\s+", "", str(来源值 or "")).strip("\"'")
        if 来源文本 == "QQ阅读":
            卡片字段文本 = " ".join(
                str(小写字段.get(键) or "")
                for 键 in (
                    "type",
                    "tag",
                    "title",
                    "summary",
                    "description",
                    "content",
                    "name",
                    "app_name",
                    "appname",
                )
            ).lower()
            if (
                "小程序" in 卡片字段文本
                or "miniapp" in 卡片字段文本
                or "wechat" in 卡片字段文本
                or str(小写字段.get("type") or "").lower() in {"json", "share"}
            ):
                return True
        return any(包含QQ阅读小程序白名单(子值) for 子值 in 值.values())
    return bool(QQ阅读小程序白名单规则.search(str(值)))


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
        if 文本 in ("forward", "node", "nodes") or 文本.endswith(
            (".forward", ".node", ".nodes")
        ):
            return True
        if any(
            标记 in 文本
            for 标记 in (
                "componenttype.forward",
                "componenttype.node",
                "componenttype.nodes",
            )
        ):
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
    候选文本: list[str] = []
    事件文本 = 清理可见文本(str(getattr(event, "message_str", "") or ""))
    if 事件文本:
        候选文本.append(事件文本)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message", "content"):
            文本 = 转成文本(读取字段(对象, 字段名))
            if 文本 and 文本 not in 候选文本:
                候选文本.append(文本)

    for 文本 in 候选文本:
        if 是否需要撤回数字消息(文本):
            return 文本
    return 候选文本[0] if 候选文本 else ""


async def 尝试撤回当前消息(event: AstrMessageEvent) -> bool:
    if 是否At消息(event):
        logger.info("数字撤回跳过：普通@消息不撤回（@机器人除外）")
        return False

    消息编号 = 获取当前消息编号(event)
    群号 = 获取群号(event)
    if not 消息编号:
        logger.warning("数字撤回失败：当前事件缺少 message_id")
        return False

    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(f"数字撤回失败：当前事件缺少 bot 实例，message_id={消息编号}")
        return False

    logger.info(
        f"尝试撤回: message_id={消息编号}, group_id={群号}, 是官方机器人={是QQ官方机器人(event)}, bot类型={type(bot).__name__}"
    )

    try:
        await 使用_delete_msg撤回(bot, 消息编号, 群号)
        logger.info(f"数字撤回成功：message_id={消息编号}")
        return True
    except Exception as exc:
        logger.warning(f"数字撤回失败：message_id={消息编号}, error={exc}")
        return False


async def 尝试撤回触发用户最近消息(event: AstrMessageEvent) -> int:
    群号 = 获取群号(event)
    用户QQ = 获取发送者QQ(event)
    if not 群号 or not 用户QQ:
        logger.info(
            f"最近消息撤回跳过：缺少群号或用户QQ，group_id={群号}, user_id={用户QQ}"
        )
        return 0
    当前消息编号 = str(获取当前消息编号(event) or "")
    return await 尝试撤回指定用户最近消息(
        event,
        群号,
        用户QQ,
        排除消息编号=当前消息编号,
        拉取数量=最近消息撤回拉取数量,
        撤回数量=最近消息撤回数量,
        日志名称="最近消息撤回",
    )


async def 尝试撤回指定用户最近消息(
    event: AstrMessageEvent,
    群号: str,
    用户QQ: str,
    排除消息编号: str = "",
    拉取数量: int = 最近消息撤回拉取数量,
    撤回数量: int = 最近消息撤回数量,
    日志名称: str = "最近消息撤回",
) -> int:
    if not 群号 or not 用户QQ:
        logger.info(
            f"{日志名称}跳过：缺少群号或用户QQ，group_id={群号}, user_id={用户QQ}"
        )
        return 0
    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(
            f"{日志名称}失败：当前事件缺少 bot 实例，group_id={群号}, user_id={用户QQ}"
        )
        return 0
    if not await QQ官方机器人具备群管权限(bot, 群号):
        logger.info("%s跳过：QQ官方机器人不是群管理员，group_id=%s", 日志名称, 群号)
        return 0

    try:
        历史消息 = await 获取群历史消息(bot, 群号, 拉取数量)
    except Exception as exc:
        logger.warning(
            f"{日志名称}获取历史失败：group_id={群号}, user_id={用户QQ}, error={exc}"
        )
        return 0

    目标消息 = 筛选用户最近消息(历史消息, 用户QQ, 排除消息编号, 撤回数量)
    成功数量 = 0
    for 消息 in 目标消息:
        消息编号 = 消息.get("message_id") if isinstance(消息, dict) else None
        if not 消息编号:
            continue
        try:
            await 使用_delete_msg撤回(bot, 消息编号, 群号)
            成功数量 += 1
            logger.info(
                f"{日志名称}成功：group_id={群号}, user_id={用户QQ}, message_id={消息编号}"
            )
        except Exception as exc:
            logger.warning(
                f"{日志名称}失败：group_id={群号}, user_id={用户QQ}, message_id={消息编号}, error={exc}"
            )
    return 成功数量


async def 获取群历史消息(bot: Any, 群号: str, 数量: int) -> list[dict[str, Any]]:
    try:
        群号值 = int(群号)
        响应 = await 调用机器人动作(
            bot, "get_group_msg_history", group_id=群号值, count=int(数量)
        )
    except (ValueError, TypeError):
        try:
            响应 = await 调用机器人动作(
                bot, "get_group_msg_history", group_openid=群号, count=int(数量)
            )
        except Exception:
            try:
                响应 = await 调用机器人动作(
                    bot, "get_group_msg_history", channel_id=群号, count=int(数量)
                )
            except Exception:
                响应 = None
    if isinstance(响应, dict):
        数据 = 响应.get("data") if "data" in 响应 else 响应
        if isinstance(数据, dict):
            消息列表 = 数据.get("messages") or 数据.get("message") or []
        else:
            消息列表 = 响应.get("messages") or []
    else:
        消息列表 = []
    return [消息 for 消息 in 消息列表 if isinstance(消息, dict)]


def 筛选用户最近消息(
    历史消息: list[dict[str, Any]],
    用户QQ: str,
    排除消息编号: str = "",
    数量: int = 最近消息撤回数量,
) -> list[dict[str, Any]]:
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


async def 记录撤回触发并尝试踢出(event: AstrMessageEvent, 配置: Any = None) -> int:
    群号 = 获取群号(event)
    用户QQ = 获取撤回发送者统一标识(event) or 获取撤回发送者标识(event)
    if not 群号 or not 用户QQ:
        logger.info("数字撤回计数跳过：缺少群或成员标识")
        return 0

    计数键 = 用户QQ
    当前次数 = 数字撤回触发次数.get(计数键, 0) + 1
    数字撤回触发次数[计数键] = 当前次数
    logger.info(
        "数字撤回模块触发计数：group_id=%s, user_id=%s, count=%s",
        群号,
        用户QQ,
        当前次数,
    )
    return 当前次数


async def 尝试踢出成员(
    event: AstrMessageEvent, 群号: str, 用户QQ: str, 配置: Any = None
) -> bool:
    bot = getattr(event, "bot", None)
    if bot is None:
        logger.warning(
            f"数字撤回踢出失败：当前事件缺少 bot 实例，group_id={群号}, user_id={用户QQ}"
        )
        return False

    try:
        await 尝试网页或适配器踢出(event, bot, 群号, 用户QQ, 配置)
        logger.info(
            f"数字撤回触发 {数字撤回踢出阈值} 次，已踢出成员：group_id={群号}, user_id={用户QQ}"
        )
        await 尝试踢出其它群同一成员(bot, 群号, 用户QQ)
        return True
    except Exception as exc:
        logger.warning(
            f"数字撤回踢出失败：group_id={群号}, user_id={用户QQ}, error={exc}"
        )
        return False


async def 尝试网页或适配器踢出(
    event: AstrMessageEvent, bot: Any, 群号: str, 用户QQ: str, 配置: Any = None
) -> None:
    await 使用_set_group_kick踢出(bot, 群号, 用户QQ)


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
            logger.warning(
                f"跨群踢出失败：group_id={群号}, user_id={用户QQ}, error={exc}"
            )


async def 同步成员禁言到其它群(
    bot: Any,
    当前群号: str,
    用户QQ: str,
    秒数: int,
    操作: str,
    跨群用户标识: str = "",
) -> tuple[int, int]:
    """把当前群的成员禁言/解禁同步到机器人所在的其它群。"""
    try:
        群号列表 = await 获取机器人所在群号列表(bot)
    except Exception as exc:
        logger.warning(
            "跨群禁言获取群列表失败：user_id=%s, error_type=%s",
            用户QQ,
            type(exc).__name__,
        )
        return 0, 0

    其它群列表 = 去重保序(
        [
            str(群号).strip()
            for 群号 in 群号列表
            if str(群号).strip() and str(群号).strip() != str(当前群号).strip()
        ]
    )
    if not 其它群列表:
        return 0, 0

    稳定用户标识 = 规范化用户编号(跨群用户标识)
    if not 稳定用户标识 and not 是数字ID(当前群号):
        稳定用户标识 = 获取官方群用户标识(当前群号, 用户QQ)

    信号量 = asyncio.Semaphore(8)

    async def 同步单群(群号: str) -> tuple[int, int]:
        async with 信号量:
            try:
                目标用户标识 = 用户QQ
                if 是数字ID(群号):
                    if not await 检查群成员存在(bot, 群号, 用户QQ):
                        return 0, 0
                else:
                    if not 稳定用户标识:
                        return 0, 0
                    目标用户标识 = 获取官方群成员标识(群号, 稳定用户标识)
                    if not 目标用户标识:
                        return 0, 0

                if not await QQ官方机器人具备群管权限(
                    bot,
                    群号,
                    未缓存时允许=False,
                ):
                    return 0, 0
                await 使用_set_group_ban禁言(bot, 群号, 目标用户标识, 秒数, 操作)
                logger.info(
                    "跨群禁言成功：group_id=%s, user_id=%s, operation=%s",
                    群号,
                    目标用户标识,
                    操作,
                )
                return 1, 0
            except Exception as exc:
                if not 是数字ID(群号):
                    删除官方群成员映射(群号, 稳定用户标识)
                logger.debug(
                    "跨群禁言请求未完成：group_id=%s, operation=%s, error_type=%s",
                    群号,
                    操作,
                    type(exc).__name__,
                )
                return 0, 1

    结果 = await asyncio.gather(*(同步单群(群号) for 群号 in 其它群列表))
    return sum(项目[0] for 项目 in 结果), sum(项目[1] for 项目 in 结果)


async def 检查群成员存在(bot: Any, 群号: str, 用户QQ: str) -> bool:
    是否数字 = True
    try:
        群号值 = int(群号)
        用户QQ值 = int(用户QQ)
    except (ValueError, TypeError):
        是否数字 = False
        群号值 = 群号
        用户QQ值 = 用户QQ

    try:
        if 是否数字:
            try:
                响应 = await 调用机器人动作(
                    bot,
                    "get_group_member_info",
                    group_id=群号值,
                    user_id=用户QQ值,
                    no_cache=True,
                )
                if 响应:
                    数据 = (
                        响应.get("data")
                        if isinstance(响应, dict) and "data" in 响应
                        else 响应
                    )
                    if isinstance(数据, dict):
                        返回用户 = (
                            数据.get("user_id")
                            or 数据.get("qq")
                            or 数据.get("id")
                            or 数据.get("user_openid")
                            or 数据.get("member_openid")
                        )
                        if 返回用户 is not None and str(返回用户).strip() == str(
                            用户QQ
                        ):
                            return True
            except Exception:
                pass
        try:
            响应 = await 调用机器人动作(
                bot,
                "get_group_member_info",
                group_openid=群号值,
                user_openid=用户QQ值,
                no_cache=True,
            )
            if 响应:
                数据 = (
                    响应.get("data")
                    if isinstance(响应, dict) and "data" in 响应
                    else 响应
                )
                if isinstance(数据, dict):
                    返回用户 = (
                        数据.get("user_id")
                        or 数据.get("qq")
                        or 数据.get("id")
                        or 数据.get("user_openid")
                        or 数据.get("member_openid")
                    )
                    if 返回用户 is not None and str(返回用户).strip() == str(用户QQ):
                        return True
        except Exception:
            pass
    except Exception:
        return False
    return False


async def 尝试踢出指定成员(
    event: AstrMessageEvent, 群号: str, 用户QQ: str, 配置: Any = None
) -> None:
    bot = getattr(event, "bot", None)
    if bot is None:
        raise RuntimeError("当前事件缺少 bot 实例")
    await 尝试网页或适配器踢出(event, bot, 群号, 用户QQ, 配置)
    await 尝试踢出其它群同一成员(bot, 群号, 用户QQ)


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
    方法 = getattr(event, "get_group_id", None)
    if callable(方法):
        try:
            值 = 方法()
        except Exception:
            值 = None
        if inspect.isawaitable(值):
            if inspect.iscoroutine(值):
                try:
                    值.close()
                except Exception:
                    pass
            值 = None
        if 值:
            群号 = 提取安全群号(值)
            if 群号:
                记录机器人所在群号(群号)
                记录当前群成员映射(event, 群号)
                return 群号

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = (
            读取字段(对象, "group_openid")
            or 读取字段(对象, "group_id")
            or 读取字段(对象, "group")
        )
        if isinstance(值, dict):
            值 = 值.get("group_openid") or 值.get("group_id") or 值.get("id")
        群号 = 提取安全群号(值)
        if 群号:
            记录机器人所在群号(群号)
            记录当前群成员映射(event, 群号)
            return 群号
    return ""


def 提取安全群号(值: Any) -> str:
    if inspect.isawaitable(值):
        if inspect.iscoroutine(值):
            try:
                值.close()
            except Exception:
                pass
        return ""
    if callable(值):
        return ""
    文本 = str(值 or "").strip()
    if (
        not 文本
        or "coroutine object" in 文本.lower()
        or "generator object" in 文本.lower()
    ):
        return ""
    if re.search(r"<[^>]+ object at 0x[0-9a-f]+>", 文本, re.IGNORECASE):
        return ""
    return 文本


def 获取发送者QQ(event: AstrMessageEvent) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = (
            读取字段(对象, "sender_id")
            or 读取字段(对象, "user_id")
            or 读取字段(对象, "sender")
        )
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
    文本 = re.sub(r"<@!?[A-Za-z0-9_-]{5,64}>", "", 文本)
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


async def 使用_delete_msg撤回(bot: Any, 消息编号: Any, 群号: str = "") -> bool:
    try:
        from astrbot.api import logger as _logger
    except Exception:
        import logging

        _logger = logging.getLogger(__name__)

    api = getattr(bot, "api", None)

    撤回方法 = getattr(bot, "delete_msg", None)
    if callable(撤回方法):
        try:
            响应 = await 撤回方法(message_id=消息编号)
            if 撤回响应成功(响应):
                return True
        except Exception:
            pass
        if 群号:
            try:
                响应 = await 撤回方法(message_id=消息编号, channel_id=群号)
                if 撤回响应成功(响应):
                    return True
            except Exception:
                pass
            try:
                响应 = await 撤回方法(message_id=消息编号, group_openid=群号)
                if 撤回响应成功(响应):
                    return True
            except Exception:
                pass
            try:
                响应 = await 撤回方法(message_id=消息编号, openid=群号)
                if 撤回响应成功(响应):
                    return True
            except Exception:
                pass

    调用动作 = (
        getattr(getattr(api, "call_action", None), "__call__", None) if api else None
    )
    if callable(调用动作):
        try:
            响应 = await 调用动作("delete_msg", message_id=消息编号)
            if 撤回响应成功(响应):
                return True
        except Exception:
            pass
        if 群号:
            try:
                响应 = await 调用动作(
                    "delete_msg", message_id=消息编号, channel_id=群号
                )
                if 撤回响应成功(响应):
                    return True
            except Exception:
                pass
            try:
                响应 = await 调用动作(
                    "delete_msg", message_id=消息编号, group_openid=群号
                )
                if 撤回响应成功(响应):
                    return True
            except Exception:
                pass
            try:
                响应 = await 调用动作("delete_msg", message_id=消息编号, openid=群号)
                if 撤回响应成功(响应):
                    return True
            except Exception:
                pass

    for 方法名 in (
        "recall_msg",
        "delete_message",
        "recall_message",
        "msg_recall",
        "message_recall",
    ):
        方法 = getattr(bot, 方法名, None)
        if callable(方法):
            try:
                响应 = await 方法(message_id=消息编号)
                if 撤回响应成功(响应):
                    return True
            except Exception:
                pass
            if 群号:
                try:
                    响应 = await 方法(message_id=消息编号, channel_id=群号)
                    if 撤回响应成功(响应):
                        return True
                except Exception:
                    pass
                try:
                    响应 = await 方法(message_id=消息编号, group_openid=群号)
                    if 撤回响应成功(响应):
                        return True
                except Exception:
                    pass

    if api is not None:
        for 方法名 in (
            "recall_msg",
            "delete_message",
            "recall_message",
            "msg_recall",
            "message_recall",
            "delete_msg",
        ):
            方法 = getattr(api, 方法名, None)
            if callable(方法):
                try:
                    响应 = await 方法(message_id=消息编号)
                    if 撤回响应成功(响应):
                        return True
                except Exception:
                    pass
                if 群号:
                    try:
                        响应 = await 方法(channel_id=群号, message_id=消息编号)
                        if 撤回响应成功(响应):
                            return True
                    except Exception:
                        pass
                    try:
                        响应 = await 方法(message_id=消息编号, channel_id=群号)
                        if 撤回响应成功(响应):
                            return True
                    except Exception:
                        pass
                    try:
                        响应 = await 方法(群号, 消息编号)
                        if 撤回响应成功(响应):
                            return True
                    except Exception:
                        pass

    if api is not None and 群号:
        _http = getattr(api, "_http", None)
        if _http is not None:
            _logger.info(
                f"撤回: 尝试通过 api._http 底层HTTP客户端撤回群消息, _http类型={type(_http).__name__}"
            )
            try:
                import botpy.http as _botpy_http

                Route = _botpy_http.Route
            except Exception:
                Route = None
            if Route is not None:
                try:
                    route = Route("DELETE", f"/v2/groups/{群号}/messages/{消息编号}")
                    响应 = await _http.request(route)
                    if 撤回响应成功(响应):
                        _logger.info("撤回成功: 已收到确认响应")
                        return True
                except Exception as e:
                    _logger.info(
                        f"撤回: _http.request(Route) 异常: {type(e).__name__}: {e}"
                    )
            else:
                _logger.info("撤回: 无法导入 botpy.http.Route，跳过底层HTTP撤回")

    raise RuntimeError("当前 bot 没有可用的撤回接口")


def 撤回响应成功(响应: Any) -> bool:
    """只把明确成功或无返回值的撤回响应视为成功。"""
    if 响应 is None:
        return True
    if isinstance(响应, bool):
        return 响应
    if isinstance(响应, dict):
        状态 = str(响应.get("status") or "").strip().lower()
        if 状态 in {"failed", "failure", "error", "async"}:
            return False

        返回码 = 响应.get("retcode")
        if 返回码 is not None:
            try:
                return int(返回码) == 0
            except (TypeError, ValueError):
                return False

        成功字段 = 响应.get("success")
        if isinstance(成功字段, bool):
            return 成功字段
        if "code" in 响应:
            try:
                return int(响应.get("code")) == 0
            except (TypeError, ValueError):
                return False
        return 状态 in {"", "ok", "success"}
    return 响应 is not False


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
    是否数字 = True
    try:
        群号值 = int(群号)
        用户QQ值 = int(用户QQ)
    except (ValueError, TypeError):
        是否数字 = False
        群号值 = 群号
        用户QQ值 = 用户QQ

    踢出方法 = getattr(bot, "set_group_kick", None)
    if callable(踢出方法):
        if 是否数字:
            try:
                await 踢出方法(
                    group_id=群号值, user_id=用户QQ值, reject_add_request=False
                )
                return True
            except Exception:
                pass
        try:
            await 踢出方法(
                group_openid=群号值, user_openid=用户QQ值, reject_add_request=False
            )
            return True
        except Exception:
            pass
        if 是否数字:
            raise RuntimeError("set_group_kick 踢出失败")
        raise RuntimeError("set_group_kick 踢出失败，可能不支持 openid 参数")

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        if 是否数字:
            try:
                await 调用动作(
                    "set_group_kick",
                    group_id=群号值,
                    user_id=用户QQ值,
                    reject_add_request=False,
                )
                return True
            except Exception:
                pass
        try:
            await 调用动作(
                "set_group_kick",
                group_openid=群号值,
                user_openid=用户QQ值,
                reject_add_request=False,
            )
            return True
        except Exception:
            pass
        if 是否数字:
            raise RuntimeError("set_group_kick 踢出失败")
        raise RuntimeError("set_group_kick 踢出失败，可能不支持 openid 参数")

    raise RuntimeError("当前 bot 没有 set_group_kick 踢出接口")


def 构造QQ官方成员禁言请求体(
    用户列表: list[str],
    操作: str,
    禁言到期时间: str | None = None,
) -> dict[str, Any]:
    if 操作 not in {"add", "update", "del"}:
        raise ValueError("不支持的成员禁言操作")

    成员列表: list[dict[str, str]] = []
    for 用户 in 去重保序([规范化用户编号(项目) for 项目 in 用户列表]):
        if not 用户:
            continue
        成员: dict[str, str] = {"op": 操作, "member_openid": 用户}
        if 操作 in {"add", "update"} and 禁言到期时间:
            成员["mute_expire_at"] = 禁言到期时间
        成员列表.append(成员)
    return {"members": 成员列表}


def 生成QQ官方禁言到期时间(秒数: int) -> str:
    北京时区 = timezone(timedelta(hours=8))
    到期时间 = datetime.now(北京时区) + timedelta(seconds=max(1, int(秒数)))
    return 到期时间.isoformat(timespec="seconds")


def 官方禁言响应成功(响应: Any) -> bool:
    if 响应 is None:
        return True
    if isinstance(响应, bool):
        return 响应
    if isinstance(响应, dict):
        状态 = str(响应.get("status") or "").strip().lower()
        if 状态 in {"failed", "failure", "error"}:
            return False
        for 字段名 in ("retcode", "code", "errcode"):
            if 字段名 in 响应 and 响应.get(字段名) not in (None, ""):
                try:
                    return int(响应.get(字段名)) == 0
                except (TypeError, ValueError):
                    return False
        return True
    return 响应 is not False


async def 使用QQ官方成员禁言接口(
    bot: Any,
    群OpenID: str,
    用户OpenID: str,
    秒数: int,
    操作: str,
) -> bool:
    api = getattr(bot, "api", None)
    http客户端 = getattr(api, "_http", None) if api else None
    if http客户端 is None:
        raise RuntimeError("当前 bot 没有 QQ 官方 HTTP 客户端")

    from botpy.http import Route

    到期时间 = None if 操作 == "del" else 生成QQ官方禁言到期时间(秒数)
    请求体 = 构造QQ官方成员禁言请求体([用户OpenID], 操作, 到期时间)
    路由 = Route(
        "POST",
        "/v2/groups/{group_openid}/restrict_chat_setting",
        group_openid=群OpenID,
    )
    响应 = await http客户端.request(路由, json=请求体)
    if not 官方禁言响应成功(响应):
        raise RuntimeError("QQ 官方成员禁言接口返回失败")
    return True


async def 使用_set_group_ban禁言(
    bot: Any,
    群号: str,
    用户QQ: str,
    秒数: int,
    操作: str = "add",
) -> bool:
    """兼容 OneBot set_group_ban 与 QQ 官方成员禁言接口。"""
    群号文本 = str(群号 or "").strip()
    用户文本 = str(用户QQ or "").strip()
    是否数字 = bool(
        管理员QQ规则.fullmatch(群号文本) and 管理员QQ规则.fullmatch(用户文本)
    )

    if not 是否数字:
        return await 使用QQ官方成员禁言接口(
            bot,
            群号文本,
            用户文本,
            秒数,
            操作,
        )

    群号值: Any = int(群号文本) if 是否数字 else 群号文本
    用户值: Any = int(用户文本) if 是否数字 else 用户文本
    时长 = 0 if 操作 == "del" else max(1, int(秒数))

    禁言方法 = getattr(bot, "set_group_ban", None)
    if callable(禁言方法):
        if 是否数字:
            await 等待可能异步结果(
                禁言方法(group_id=群号值, user_id=用户值, duration=时长)
            )
            return True
        await 等待可能异步结果(
            禁言方法(group_openid=群号值, user_openid=用户值, duration=时长)
        )
        return True

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        if 是否数字:
            await 等待可能异步结果(
                调用动作(
                    "set_group_ban",
                    group_id=群号值,
                    user_id=用户值,
                    duration=时长,
                )
            )
            return True
        await 等待可能异步结果(
            调用动作(
                "set_group_ban",
                group_openid=群号值,
                user_openid=用户值,
                duration=时长,
            )
        )
        return True

    raise RuntimeError("当前 bot 没有成员禁言接口")


def 安全整数(值: Any, 默认值: int = 0) -> int:
    if 值 in (None, "") or isinstance(值, bool):
        return 默认值
    try:
        return int(str(值).strip())
    except Exception:
        return 默认值
