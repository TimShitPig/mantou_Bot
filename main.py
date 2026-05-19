from pathlib import Path
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


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", "1.4.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        pass

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        消息文本 = event.message_str.strip()

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
