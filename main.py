from pathlib import Path
import importlib
import sys

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

插件目录 = Path(__file__).resolve().parent
if str(插件目录) not in sys.path:
    sys.path.insert(0, str(插件目录))

def 加载功能模块(模块路径: str):
    return importlib.reload(importlib.import_module(模块路径))


importlib.invalidate_caches()
古诗词名句模块 = 加载功能模块("功能文件.oiapi.古诗词名句")
疯狂星期四模块 = 加载功能模块("功能文件.oiapi.疯狂星期四")
随机一言模块 = 加载功能模块("功能文件.oiapi.随机一言")
随机英文单词模块 = 加载功能模块("功能文件.oiapi.随机英文单词")
数字撤回功能 = 加载功能模块("功能文件.管理功能.数字撤回")
消息工具 = 加载功能模块("功能文件.管理功能.消息工具")

获取古诗词名句回复 = getattr(古诗词名句模块, "获取古诗词名句回复")
获取疯狂星期四回复 = getattr(疯狂星期四模块, "获取疯狂星期四回复")
获取随机一言回复 = getattr(随机一言模块, "获取随机一言回复")
获取随机英文单词回复 = getattr(随机英文单词模块, "获取随机英文单词回复")
获取命令文本 = getattr(消息工具, "获取命令文本")
插件版本 = "1.5.29"


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", 插件版本)
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        pass

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        命令文本 = 获取命令文本(event)
        回复内容 = None

        if 命令文本 == "随机英文单词":
            回复内容 = await 获取随机英文单词回复()
        elif 命令文本 == "随机一言":
            回复内容 = await 获取随机一言回复()
        elif 命令文本 == "疯狂星期四":
            回复内容 = await 获取疯狂星期四回复()
        elif 命令文本 == "古诗词名句":
            回复内容 = await 获取古诗词名句回复()

        if 回复内容 is None:
            if await 数字撤回功能.处理数字撤回(event):
                event.stop_event()
            return

        yield event.plain_result(回复内容)
        event.stop_event()

    async def terminate(self):
        pass
