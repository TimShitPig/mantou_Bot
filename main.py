from pathlib import Path
import importlib
import sys

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

插件目录 = Path(__file__).resolve().parent
if str(插件目录) not in sys.path:
    sys.path.insert(0, str(插件目录))

def 加载功能模块(模块路径: str):
    return importlib.reload(importlib.import_module(模块路径))


importlib.invalidate_caches()
权限工具 = 加载功能模块("功能文件.管理功能.基础功能.权限工具")
消息工具 = 加载功能模块("功能文件.管理功能.基础功能.消息工具")
帮助功能 = 加载功能模块("功能文件.管理功能.基础功能.帮助功能")
QQ官方交互桥 = 加载功能模块("功能文件.管理功能.基础功能.QQ官方交互桥")
状态功能 = 加载功能模块("功能文件.管理功能.基础功能.状态功能")
UC网盘功能 = 加载功能模块("功能文件.管理功能.网盘功能.UC网盘")
百度网盘功能 = 加载功能模块("功能文件.管理功能.网盘功能.百度网盘")
QQ阅读功能 = 加载功能模块("功能文件.管理功能.小说功能.QQ阅读")
群列表工具 = 加载功能模块("功能文件.管理功能.群聊功能.群列表工具")
群管功能 = 加载功能模块("功能文件.管理功能.群聊功能.群管功能")
网页群文件功能 = 加载功能模块("功能文件.管理功能.群聊功能.网页群文件")
七猫小说功能 = 加载功能模块("功能文件.管理功能.小说功能.七猫小说")
书旗小说功能 = 加载功能模块("功能文件.管理功能.小说功能.书旗小说")
番茄小说功能 = 加载功能模块("功能文件.管理功能.小说功能.番茄小说")
授权链接功能 = 加载功能模块("功能文件.管理功能.群聊功能.授权链接")
小说功能开关 = 加载功能模块("功能文件.管理功能.小说功能.小说功能开关")
找书功能 = 加载功能模块("功能文件.管理功能.小说功能.找书")
QQ官方交互桥.安装QQ官方帮助交互()
获取命令文本 = getattr(消息工具, "获取命令文本")
插件版本 = "4.0.0"


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", 插件版本)
class MyPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.context = context
        self.config = config

    async def initialize(self):
        QQ官方交互桥.安装QQ官方帮助交互(self.context)
        网页群文件功能.启动Cookie自动保活(self.config)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        命令文本 = 获取命令文本(event)
        回复内容 = None

        async def _输出找书结果(找书结果):
            if 找书结果 is None:
                return
            if isinstance(找书结果, str):
                yield event.plain_result(找书结果)
                return
            if isinstance(找书结果, dict):
                md文本 = str(找书结果.get("md") or "")
                键盘 = 找书结果.get("keyboard")
                纯文本 = str(找书结果.get("text") or md文本)
                if md文本 and 权限工具.是QQ官方机器人(event):
                    发送成功 = await 帮助功能.发送Markdown键盘消息(event, md文本, 键盘)
                    if not 发送成功:
                        yield event.plain_result(纯文本)
                else:
                    yield event.plain_result(纯文本)
                return
            async for 找书回复内容 in 找书结果:
                if isinstance(找书回复内容, str):
                    yield event.plain_result(找书回复内容)
                else:
                    yield 找书回复内容

        帮助回调 = 帮助功能.解析帮助回调命令(命令文本)
        if 帮助回调 is not None:
            回调类型, 回调命令 = 帮助回调
            logger.info(f"QQ官方帮助回调分发：type={回调类型}, command={回调命令}")
            if 回调类型 == "菜单":
                md文本, 键盘 = 帮助功能.处理帮助指令MD带键盘(event, 回调命令, self.config)
                if md文本 is not None:
                    if 权限工具.是QQ官方机器人(event):
                        发送成功 = await 帮助功能.发送Markdown键盘消息(event, md文本, 键盘)
                        if not 发送成功:
                            yield event.plain_result(md文本)
                    else:
                        yield event.plain_result(md文本)
                event.stop_event()
                return
            命令文本 = 回调命令

        # 找书优先：搜索/翻页/选N 下载（兼容 Markdown 文字指令链和手动发送）
        找书下载 = 找书功能.获取找书下载回复流(event, 命令文本, self.config)
        if 找书下载 is not None:
            async for 片段 in _输出找书结果(找书下载):
                yield 片段
            event.stop_event()
            return

        找书回复 = await 找书功能.处理找书指令(event, 命令文本, self.config)
        if 找书回复 is not None:
            async for 片段 in _输出找书结果(找书回复):
                yield 片段
            event.stop_event()
            return

        是广告消息 = (
            群管功能.是否闪传消息(event)
            or 群管功能.是否群名片消息(event)
            or 群管功能.是否合并转发消息(event)
        )

        if 是广告消息:
            if await 群管功能.处理数字撤回(event, self.config):
                event.stop_event()
                return

        登录回复 = await QQ阅读功能.处理QQ阅读登录指令(event, 命令文本, self.config)
        if 登录回复 is not None:
            回复内容 = 登录回复
        if 回复内容 is None:
            回复内容 = 小说功能开关.处理小说功能开关指令(event, 命令文本, self.config)
        if 回复内容 is None:
            回复内容 = 状态功能.处理状态指令(event, 命令文本, self.config, 插件版本)
        if 回复内容 is None:
            if 网页群文件功能.需要优先处理返回(event):
                回复内容 = await 网页群文件功能.处理网页群文件清理(event, 命令文本, self.config)
            if 回复内容 is None:
                if 权限工具.是QQ官方机器人(event):
                    md文本, 键盘 = 帮助功能.处理帮助指令MD带键盘(event, 命令文本, self.config)
                    if md文本 is not None:
                        发送成功 = await 帮助功能.发送Markdown键盘消息(event, md文本, 键盘)
                        if not 发送成功:
                            yield event.plain_result(md文本)
                        event.stop_event()
                        return
                回复内容 = 帮助功能.处理帮助指令(event, 命令文本, self.config)
        if 回复内容 is None:
            回复内容 = await 网页群文件功能.处理网页群文件清理(event, 命令文本, self.config)
        if 回复内容 is None:
            回复内容 = await 授权链接功能.处理授权链接(event, 命令文本, self.context, self.config)

        if 回复内容 is None:
            回复内容 = await 群管功能.处理群禁言(event, 命令文本, self.config)

        if 回复内容 is None:
            if await 群管功能.处理数字撤回(event, self.config):
                event.stop_event()
                return

            书旗回复流 = 书旗小说功能.获取书旗小说回复流(event, 命令文本, self.config)
            if 书旗回复流 is not None:
                if not 小说功能开关.小说功能是否开启("书旗", self.config):
                    yield event.plain_result(小说功能开关.获取小说功能关闭回复("书旗"))
                    event.stop_event()
                    return
                async for 书旗回复内容 in 书旗回复流:
                    if isinstance(书旗回复内容, str):
                        yield event.plain_result(书旗回复内容)
                    else:
                        yield 书旗回复内容
                event.stop_event()
                return

            七猫回复流 = 七猫小说功能.获取七猫小说回复流(event, 命令文本, self.config)
            if 七猫回复流 is not None:
                if not 小说功能开关.小说功能是否开启("七猫", self.config):
                    yield event.plain_result(小说功能开关.获取小说功能关闭回复("七猫"))
                    event.stop_event()
                    return
                async for 七猫回复内容 in 七猫回复流:
                    if isinstance(七猫回复内容, str):
                        yield event.plain_result(七猫回复内容)
                    else:
                        yield 七猫回复内容
                event.stop_event()
                return

            QQ阅读回复流 = QQ阅读功能.获取QQ阅读回复流(event, 命令文本, self.config)
            if QQ阅读回复流 is not None:
                if not 小说功能开关.小说功能是否开启("QQ阅读", self.config):
                    yield event.plain_result(小说功能开关.获取小说功能关闭回复("QQ阅读"))
                    event.stop_event()
                    return
                async for QQ阅读回复内容 in QQ阅读回复流:
                    if isinstance(QQ阅读回复内容, str):
                        yield event.plain_result(QQ阅读回复内容)
                    else:
                        yield QQ阅读回复内容
                event.stop_event()
                return

            番茄回复流 = 番茄小说功能.获取番茄小说回复流(event, 命令文本, self.config)
            if 番茄回复流 is not None:
                logger.info("番茄小说分发：使用本地下载链路")
                if not 小说功能开关.小说功能是否开启("番茄", self.config):
                    yield event.plain_result(小说功能开关.获取小说功能关闭回复("番茄"))
                    event.stop_event()
                    return
                async for 番茄回复内容 in 番茄回复流:
                    if isinstance(番茄回复内容, str):
                        yield event.plain_result(番茄回复内容)
                    else:
                        yield 番茄回复内容
                event.stop_event()
                return

        if not 回复内容:
            # 空字符串表示 markdown 已自行发送（如群文件清理按钮交互），跳过 plain_result 避免空消息链警告
            return

        yield event.plain_result(回复内容)
        event.stop_event()

    async def terminate(self):
        pass
