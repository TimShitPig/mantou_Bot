from pathlib import Path
import re
import sys

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


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", "1.6.5")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        pass

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        消息文本 = 清理消息文本(event)

        if await 处理数字撤回兼容(event, 消息文本):
            event.stop_event()
            return

        if 消息文本 == "随机英文单词":
            回复内容 = await 获取随机英文单词回复()
        elif 消息文本 == "随机一言":
            回复内容 = await 获取随机一言回复()
        elif 消息文本 == "疯狂星期四":
            回复内容 = await 获取疯狂星期四回复()
        elif 消息文本 == "古诗词名句":
            回复内容 = await 获取古诗词名句回复()
        else:
            return

        yield event.plain_result(回复内容)
        event.stop_event()

    async def terminate(self):
        pass


async def 处理数字撤回兼容(event: AstrMessageEvent, 消息文本: str) -> bool:
    处理数字撤回 = getattr(数字撤回功能, "处理数字撤回", None)
    if callable(处理数字撤回):
        return await 处理数字撤回(event, 消息文本)

    是否需要撤回数字消息 = getattr(数字撤回功能, "是否需要撤回数字消息", None)
    尝试撤回当前消息 = getattr(数字撤回功能, "尝试撤回当前消息", None)
    if not callable(是否需要撤回数字消息) or not callable(尝试撤回当前消息):
        return False

    if not 是否需要撤回数字消息(消息文本):
        return False

    await 尝试撤回当前消息(event)
    return True


def 清理消息文本(event: AstrMessageEvent) -> str:
    候选文本 = [清理文本片段(文本) for 文本 in 获取消息文本候选(event)]
    候选文本 = [文本 for 文本 in 候选文本 if 文本]

    for 文本 in 候选文本:
        if 数字撤回功能.是否需要撤回数字消息(文本):
            return 文本

    for 文本 in 候选文本:
        if 文本 in ("随机英文单词", "随机一言", "疯狂星期四", "古诗词名句"):
            return 文本

    return 候选文本[0] if 候选文本 else ""


def 获取消息文本候选(event: AstrMessageEvent) -> list:
    消息对象 = getattr(event, "message_obj", None)
    return [
        读取字段(消息对象, "raw_message"),
        读取字段(event, "raw_message"),
        读取字段(消息对象, "message_str"),
        读取字段(event, "message_str"),
        读取字段(消息对象, "message"),
        读取字段(event, "message"),
    ]


def 清理文本片段(文本) -> str:
    文本 = str(文本 or "")
    文本 = re.sub(r"\[CQ:reply,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[CQ:at,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[At:[^\]]+\]", "", 文本)
    文本 = 文本.replace("@", "").replace("＠", "")
    return 文本.strip()


def 读取字段(对象, 字段名: str):
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
