from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Callable, Coroutine
import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

插件目录 = Path(__file__).resolve().parent
功能目录 = 插件目录 / "功能文件" / "oiapi"


功能函数 = Callable[[], Coroutine[Any, Any, str]]


def 加载功能函数(文件名: str, 函数名: str) -> 功能函数:
    模块路径 = 功能目录 / 文件名
    模块名 = f"mantou_bot_{模块路径.stem}"
    模块规格 = spec_from_file_location(模块名, 模块路径)
    if 模块规格 is None or 模块规格.loader is None:
        raise ImportError(f"无法加载功能文件：{模块路径}")

    模块 = module_from_spec(模块规格)
    模块规格.loader.exec_module(模块)
    return getattr(模块, 函数名)


def 清理消息文本(event: AstrMessageEvent) -> str:
    文本 = str(getattr(event, "message_str", "") or "")
    文本 = re.sub(r"\[CQ:reply,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[CQ:at,[^\]]*\]", "", 文本)
    文本 = re.sub(r"\[At:[^\]]+\]", "", 文本)
    文本 = 文本.replace("@", "").replace("＠", "")
    return 文本.strip()


获取古诗词名句回复 = 加载功能函数("古诗词名句.py", "获取古诗词名句回复")
获取疯狂星期四回复 = 加载功能函数("疯狂星期四.py", "获取疯狂星期四回复")
获取随机一言回复 = 加载功能函数("随机一言.py", "获取随机一言回复")
获取随机英文单词回复 = 加载功能函数("随机英文单词.py", "获取随机英文单词回复")


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", "1.4.3")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        pass

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        原始文本 = str(getattr(event, "message_str", "") or "")
        消息文本 = 清理消息文本(event)
        logger.info(f"馒头bot收到原始文本：{原始文本}")
        logger.info(f"馒头bot清理后文本：{消息文本}")

        if 消息文本 == "随机英文单词":
            功能名 = "随机英文单词"
            回复内容 = await 获取随机英文单词回复()
        elif 消息文本 == "随机一言":
            功能名 = "随机一言"
            回复内容 = await 获取随机一言回复()
        elif 消息文本 == "疯狂星期四":
            功能名 = "疯狂星期四"
            回复内容 = await 获取疯狂星期四回复()
        elif 消息文本 == "古诗词名句":
            功能名 = "古诗词名句"
            回复内容 = await 获取古诗词名句回复()
        else:
            return

        logger.info(f"馒头bot命中功能：{功能名}")
        logger.info(f"馒头bot准备回复内容：{回复内容}")
        yield event.plain_result(回复内容)
        event.stop_event()

    async def terminate(self):
        pass
