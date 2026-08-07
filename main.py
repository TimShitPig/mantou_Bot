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
运行状态数据库 = 加载功能模块("功能文件.管理功能.基础功能.运行状态数据库")
状态功能 = 加载功能模块("功能文件.管理功能.基础功能.状态功能")
网盘Cookie功能 = 加载功能模块("功能文件.管理功能.网盘功能.网盘Cookie")
UC网盘功能 = 加载功能模块("功能文件.管理功能.网盘功能.UC网盘")
夸克网盘功能 = 加载功能模块("功能文件.管理功能.网盘功能.夸克网盘")
百度网盘功能 = 加载功能模块("功能文件.管理功能.网盘功能.百度网盘")
小说网盘功能 = 加载功能模块("功能文件.管理功能.网盘功能.小说网盘")
QQ阅读功能 = 加载功能模块("功能文件.管理功能.小说功能.小说.QQ阅读")
群列表工具 = 加载功能模块("功能文件.管理功能.群聊功能.群列表工具")
群管功能 = 加载功能模块("功能文件.管理功能.群聊功能.群管功能")
网页群文件功能 = 加载功能模块("功能文件.管理功能.群聊功能.网页群文件")
七猫小说功能 = 加载功能模块("功能文件.管理功能.小说功能.小说.七猫小说")
书旗小说功能 = 加载功能模块("功能文件.管理功能.小说功能.小说.书旗小说")
番茄小说功能 = 加载功能模块("功能文件.管理功能.小说功能.小说.番茄小说")
得间小说功能 = 加载功能模块("功能文件.管理功能.小说功能.小说.得间小说")
点众小说功能 = 加载功能模块("功能文件.管理功能.小说功能.小说.点众小说")
小说缓存清理 = 加载功能模块("功能文件.管理功能.小说功能.功能.下载缓存清理")
全量消息功能 = 加载功能模块("功能文件.管理功能.群聊功能.全量消息")
小说功能开关 = 加载功能模块("功能文件.管理功能.小说功能.功能.小说功能开关")
找书功能 = 加载功能模块("功能文件.管理功能.小说功能.功能.找书")
QQ官方交互桥.安装QQ官方帮助交互()
获取命令文本 = getattr(消息工具, "获取命令文本")
插件版本 = "5.10.21"


@register("馒头bot", "馒头", "适用于 AstrBot 的馒头bot插件。", 插件版本)
class MyPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.context = context
        self.config = config

    async def initialize(self):
        QQ官方交互桥.安装QQ官方帮助交互(self.context)
        logger.info("馒头bot加载完成：version=%s, source=%s", 插件版本, 插件目录)
        已清理缓存数 = 小说缓存清理.清理残留下载缓存()
        if 已清理缓存数:
            logger.info(f"插件重载清理小说下载缓存：count={已清理缓存数}")

    @filter.on_platform_loaded()
    async def _QQ官方平台加载后同步(self):
        await QQ官方交互桥.QQ官方平台加载后同步(self.context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        命令文本 = 获取命令文本(event)
        回复内容 = None

        async def _输出文本回复(文本):
            """QQ 官方群聊统一使用 Markdown 并提及发起人，其他适配器保持原回复。"""
            if 权限工具.是QQ官方机器人(event):
                if await 帮助功能.发送QQ官方提及Markdown(event, str(文本)):
                    return
            yield event.plain_result(文本)

        async def _输出回复流(回复流):
            async for 流回复内容 in 回复流:
                if isinstance(流回复内容, str):
                    async for 输出内容 in _输出文本回复(流回复内容):
                        yield 输出内容
                else:
                    yield 流回复内容

        async def _输出找书结果(找书结果):
            if 找书结果 is None:
                return
            if isinstance(找书结果, str):
                async for 输出内容 in _输出文本回复(找书结果):
                    yield 输出内容
                return
            if isinstance(找书结果, dict):
                md文本 = str(找书结果.get("md") or "")
                键盘 = 找书结果.get("keyboard")
                纯文本 = str(找书结果.get("text") or md文本)
                if md文本 and 权限工具.是QQ官方机器人(event):
                    发送成功 = await 帮助功能.发送Markdown键盘消息(event, md文本, 键盘)
                    if not 发送成功:
                        async for 输出内容 in _输出文本回复(纯文本):
                            yield 输出内容
                else:
                    async for 输出内容 in _输出文本回复(纯文本):
                        yield 输出内容
                return
            async for 找书回复内容 in 找书结果:
                if isinstance(找书回复内容, str):
                    async for 输出内容 in _输出文本回复(找书回复内容):
                        yield 输出内容
                else:
                    yield 找书回复内容

        网盘Cookie回复 = await 小说网盘功能.处理网盘Cookie指令(
            event,
            命令文本,
            self.config,
        )
        if 网盘Cookie回复 is not None:
            if isinstance(网盘Cookie回复, str) and 网盘Cookie回复:
                async for 输出内容 in _输出文本回复(网盘Cookie回复):
                    yield 输出内容
            elif not isinstance(网盘Cookie回复, str):
                yield 网盘Cookie回复
            event.stop_event()
            return

        QQ阅读Cookie回复 = await QQ阅读功能.处理QQ阅读Cookie指令(
            event,
            命令文本,
            self.config,
        )
        if QQ阅读Cookie回复 is not None:
            if QQ阅读Cookie回复:
                async for 输出内容 in _输出文本回复(QQ阅读Cookie回复):
                    yield 输出内容
            event.stop_event()
            return

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
                            async for 输出内容 in _输出文本回复(md文本):
                                yield 输出内容
                    else:
                        async for 输出内容 in _输出文本回复(md文本):
                            yield 输出内容
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

        回复内容 = 小说功能开关.处理小说功能开关指令(event, 命令文本, self.config)
        if 回复内容 is None:
            回复内容 = 小说网盘功能.处理网盘切换指令(event, 命令文本, self.config)
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
                            async for 输出内容 in _输出文本回复(md文本):
                                yield 输出内容
                        event.stop_event()
                        return
                回复内容 = 帮助功能.处理帮助指令(event, 命令文本, self.config)
        if 回复内容 is None:
            回复内容 = await 网页群文件功能.处理网页群文件清理(event, 命令文本, self.config)
        if 回复内容 is None:
            回复内容 = await 全量消息功能.处理全量消息(event, 命令文本, self.context, self.config)

        if 回复内容 is None:
            回复内容 = await 群管功能.处理群禁言(event, 命令文本, self.config)

        if 回复内容 is None:
            if await 群管功能.处理数字撤回(event, self.config):
                event.stop_event()
                return

            书旗回复流 = 书旗小说功能.获取书旗小说回复流(event, 命令文本, self.config)
            if 书旗回复流 is not None:
                if not 小说功能开关.当前事件可使用小说功能(event, "书旗", self.config):
                    async for 输出内容 in _输出文本回复(小说功能开关.获取小说功能关闭回复("书旗")):
                        yield 输出内容
                    event.stop_event()
                    return
                async for 输出内容 in _输出回复流(书旗回复流):
                    yield 输出内容
                event.stop_event()
                return

            七猫回复流 = 七猫小说功能.获取七猫小说回复流(event, 命令文本, self.config)
            if 七猫回复流 is not None:
                if not 小说功能开关.当前事件可使用小说功能(event, "七猫", self.config):
                    async for 输出内容 in _输出文本回复(小说功能开关.获取小说功能关闭回复("七猫")):
                        yield 输出内容
                    event.stop_event()
                    return
                async for 输出内容 in _输出回复流(七猫回复流):
                    yield 输出内容
                event.stop_event()
                return

            QQ阅读回复流 = QQ阅读功能.获取QQ阅读回复流(event, 命令文本, self.config)
            if QQ阅读回复流 is not None:
                if not 小说功能开关.当前事件可使用小说功能(event, "QQ阅读", self.config):
                    async for 输出内容 in _输出文本回复(小说功能开关.获取小说功能关闭回复("QQ阅读")):
                        yield 输出内容
                    event.stop_event()
                    return
                async for 输出内容 in _输出回复流(QQ阅读回复流):
                    yield 输出内容
                event.stop_event()
                return

            得间回复流 = 得间小说功能.获取得间小说回复流(event, 命令文本, self.config)
            if 得间回复流 is not None:
                if not 小说功能开关.当前事件可使用小说功能(event, "得间", self.config):
                    async for 输出内容 in _输出文本回复(小说功能开关.获取小说功能关闭回复("得间")):
                        yield 输出内容
                    event.stop_event()
                    return
                async for 输出内容 in _输出回复流(得间回复流):
                    yield 输出内容
                event.stop_event()
                return

            点众回复流 = 点众小说功能.获取点众小说回复流(event, 命令文本, self.config)
            if 点众回复流 is not None:
                if not 小说功能开关.当前事件可使用小说功能(event, "点众", self.config):
                    async for 输出内容 in _输出文本回复(小说功能开关.获取小说功能关闭回复("点众")):
                        yield 输出内容
                    event.stop_event()
                    return
                async for 输出内容 in _输出回复流(点众回复流):
                    yield 输出内容
                event.stop_event()
                return

            番茄回复流 = 番茄小说功能.获取番茄小说回复流(event, 命令文本, self.config)
            if 番茄回复流 is not None:
                logger.debug("番茄小说分发：使用本地下载链路")
                if not 小说功能开关.当前事件可使用小说功能(event, "番茄", self.config):
                    async for 输出内容 in _输出文本回复(小说功能开关.获取小说功能关闭回复("番茄")):
                        yield 输出内容
                    event.stop_event()
                    return
                async for 输出内容 in _输出回复流(番茄回复流):
                    yield 输出内容
                event.stop_event()
                return

        if not 回复内容:
            # 空字符串表示 markdown 已自行发送（如群文件清理按钮交互），跳过 plain_result 避免空消息链警告
            return

        async for 输出内容 in _输出文本回复(回复内容):
            yield 输出内容
        event.stop_event()

    async def terminate(self):
        await 小说网盘功能.停止网盘后台任务()
