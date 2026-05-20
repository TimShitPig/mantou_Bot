from pathlib import Path
import re
import sys
from typing import Any

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

插件目录 = Path(__file__).resolve().parent
if str(插件目录) not in sys.path:
    sys.path.insert(0, str(插件目录))

from 功能文件.oiapi.古诗词名句 import 获取古诗词名句回复
from 功能文件.oiapi.疯狂星期四 import 获取疯狂星期四回复
from 功能文件.oiapi.随机一言 import 获取随机一言回复
from 功能文件.oiapi.随机英文单词 import 获取随机英文单词回复
import 功能文件.管理功能.数字撤回 as 数字撤回功能


链接规则 = re.compile(r"https?://|https?%3A%2F%2F|\b\w+\.\w+/", re.IGNORECASE)
群名片规则 = re.compile(r"\[CQ:contact,[^\]]*(?:type=group|type=qq_group)[^\]]*\]")
卡片消息规则 = re.compile(r"\[ComponentType\.Json\]|\[CQ:json,", re.IGNORECASE)


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", "1.5.13")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        pass

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        命令文本 = 获取命令文本(event)

        if 命令文本 == "随机英文单词":
            回复内容 = await 获取随机英文单词回复()
        elif 命令文本 == "随机一言":
            回复内容 = await 获取随机一言回复()
        elif 命令文本 == "疯狂星期四":
            回复内容 = await 获取疯狂星期四回复()
        elif 命令文本 == "古诗词名句":
            回复内容 = await 获取古诗词名句回复()
        else:
            消息文本 = 获取消息文本兼容(event)
            if 是否群名片消息兼容(event) or (
                not 是否链接消息(命令文本)
                and not 是否链接消息(消息文本)
                and 数字撤回功能.是否需要撤回数字消息(消息文本)
            ):
                await 数字撤回功能.尝试撤回当前消息(event)
                event.stop_event()
            return

        yield event.plain_result(回复内容)
        event.stop_event()

    async def terminate(self):
        pass


def 获取消息文本兼容(event: AstrMessageEvent) -> str:
    获取消息文本 = getattr(数字撤回功能, "获取消息文本", None)
    if callable(获取消息文本):
        return 获取消息文本(event)
    return str(getattr(event, "message_str", "") or "").strip()


def 获取命令文本(event: AstrMessageEvent) -> str:
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


def 是否群名片消息兼容(event: AstrMessageEvent) -> bool:
    是否群名片消息 = getattr(数字撤回功能, "是否群名片消息", None)
    if callable(是否群名片消息):
        return 是否群名片消息(event)

    for 文本 in 获取原始文本候选(event):
        if 群名片规则.search(文本) or 卡片消息规则.search(文本):
            return True

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (消息对象, event):
        消息 = 读取字段(对象, "message")
        if 包含群名片消息段(消息):
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


def 清理命令文本(文本: str) -> str:
    文本 = re.sub(r"\[CQ:reply,[^\]]*\]", "", str(文本 or ""))
    文本 = re.sub(r"\[CQ:at,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[At:[^\]]+\]", "", 文本)
    return 文本.strip()


def 是否链接消息(文本: str) -> bool:
    return bool(链接规则.search(str(文本 or "")))
