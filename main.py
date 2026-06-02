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
古诗词名句模块 = 加载功能模块("功能文件.API功能.OIAPI.古诗词名句")
疯狂星期四模块 = 加载功能模块("功能文件.API功能.OIAPI.疯狂星期四")
随机一言模块 = 加载功能模块("功能文件.API功能.OIAPI.随机一言")
随机英文单词模块 = 加载功能模块("功能文件.API功能.OIAPI.随机英文单词")
权限工具 = 加载功能模块("功能文件.管理功能.权限工具")
析API番茄小说模块 = 加载功能模块("功能文件.API功能.析API.番茄小说")
番茄小说模块 = 加载功能模块("功能文件.API功能.OIAPI.番茄小说")
群管功能 = 加载功能模块("功能文件.管理功能.群管功能")
消息工具 = 加载功能模块("功能文件.管理功能.消息工具")
群文件清理功能 = 加载功能模块("功能文件.管理功能.群文件清理")
七猫小说功能 = 加载功能模块("功能文件.管理功能.七猫小说")
授权链接功能 = 加载功能模块("功能文件.管理功能.授权链接")
用户激活功能 = 加载功能模块("功能文件.管理功能.用户激活")
帮助功能 = 加载功能模块("功能文件.管理功能.帮助功能")

获取古诗词名句回复 = getattr(古诗词名句模块, "获取古诗词名句回复")
获取疯狂星期四回复 = getattr(疯狂星期四模块, "获取疯狂星期四回复")
获取随机一言回复 = getattr(随机一言模块, "获取随机一言回复")
获取随机英文单词回复 = getattr(随机英文单词模块, "获取随机英文单词回复")
获取命令文本 = getattr(消息工具, "获取命令文本")
插件版本 = "1.18.0"


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", 插件版本)
class MyPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config

    async def initialize(self):
        pass

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        命令文本 = 获取命令文本(event)
        回复内容 = None

        激活回复 = await 用户激活功能.处理用户激活(event, 命令文本, self.config, self.context)
        if 激活回复 is not None:
            yield event.plain_result(激活回复)
            event.stop_event()
            return

        if 用户激活功能.是需激活文本命令(命令文本):
            激活拦截 = await 用户激活功能.获取未激活拦截回复(event, self.config)
            if 激活拦截 is not None:
                回复内容 = 激活拦截
            elif 命令文本 == "随机英文单词":
                回复内容 = await 获取随机英文单词回复()
            elif 命令文本 == "随机一言":
                回复内容 = await 获取随机一言回复()
            elif 命令文本 == "疯狂星期四":
                回复内容 = await 获取疯狂星期四回复()
            elif 命令文本 == "古诗词名句":
                回复内容 = await 获取古诗词名句回复()
        else:
            回复内容 = 番茄小说模块.处理番茄小说API指令(event, 命令文本, self.config)
            if 回复内容 is None:
                回复内容 = 帮助功能.处理帮助指令(event, 命令文本, self.config)
            if 回复内容 is None:
                回复内容 = await 群文件清理功能.处理群文件清理(event, 命令文本, self.config)
            if 回复内容 is None:
                回复内容 = await 授权链接功能.处理授权链接(event, 命令文本, self.context, self.config)

            if 回复内容 is None:
                回复内容 = await 群管功能.处理用户踢出(event, 命令文本, self.config)

            if 回复内容 is None:
                if await 群管功能.处理数字撤回(event):
                    event.stop_event()
                    return

                七猫回复流 = 七猫小说功能.获取七猫小说回复流(event, 命令文本)
                if 七猫回复流 is not None:
                    激活拦截 = await 用户激活功能.获取未激活拦截回复(event, self.config)
                    if 激活拦截 is not None:
                        yield event.plain_result(激活拦截)
                        event.stop_event()
                        return
                    async for 七猫回复内容 in 七猫回复流:
                        if isinstance(七猫回复内容, str):
                            yield event.plain_result(七猫回复内容)
                        else:
                            yield 七猫回复内容
                    event.stop_event()
                    return

                番茄回复流 = 番茄小说模块.获取番茄小说回复流(event, 命令文本, self.config)
                if 番茄回复流 is not None:
                    激活拦截 = await 用户激活功能.获取未激活拦截回复(event, self.config)
                    if 激活拦截 is not None:
                        yield event.plain_result(激活拦截)
                        event.stop_event()
                        return
                    async for 番茄回复内容 in 番茄回复流:
                        if isinstance(番茄回复内容, str):
                            yield event.plain_result(番茄回复内容)
                        else:
                            yield 番茄回复内容
                    event.stop_event()
                    return

        if 回复内容 is None:
            return

        yield event.plain_result(回复内容)
        event.stop_event()

    async def terminate(self):
        pass
