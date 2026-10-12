"""插件的快速启动、后台维护及热重载任务交接。"""

from __future__ import annotations

import asyncio
import importlib
import time
from typing import Any

from astrbot.api import logger

from . import QQ官方交互桥, 文件缓存, 权限工具, 消息记录
from 功能文件.页面功能 import 帮助网页
from 功能文件.管理功能.网盘功能 import 小说网盘, 蓝奏云图片归档
from 功能文件.管理功能.小说功能.功能 import 小说下载任务, 小说功能开关
from 功能文件.管理功能.小说功能.小说 import QQ阅读, 得间小说, 塔读小说

_ZLibrary = importlib.import_module("功能文件.管理功能.小说功能.小说.Z-Library小说")
_缓存准备任务: asyncio.Task[Any] | None = globals().get("_缓存准备任务")
_当前句柄: dict[str, Any] | None = globals().get("_当前句柄")


def _准备缓存同步() -> dict[str, Any]:
    文件缓存.初始化文件缓存目录()
    return {
        "migrated": 文件缓存.迁移旧文件缓存(),
        "temporary": 文件缓存.清理过期临时文件缓存(),
        "remaining": 文件缓存.清理残留小说缓存(),
        "expired": 文件缓存.清理过期小说缓存(),
    }


async def _准备缓存() -> dict[str, Any]:
    global _缓存准备任务
    循环 = asyncio.get_running_loop()
    if (
        _缓存准备任务 is None
        or _缓存准备任务.done()
        or _缓存准备任务.get_loop() is not 循环
    ):
        _缓存准备任务 = 循环.create_task(
            asyncio.to_thread(_准备缓存同步), name="插件缓存准备"
        )
    # 取消维护任务不会中断磁盘扫描；下一轮重载接管同一准备任务。
    return await asyncio.shield(_缓存准备任务)


def _记录每日缓存清理(数量: int) -> None:
    if 数量:
        logger.info("每日零点清理过期小说缓存：数量=%s", 数量)


async def _后台恢复(句柄: dict[str, Any]) -> None:
    开始 = time.monotonic()
    try:
        结果 = await _准备缓存()
        if 句柄["stopped"]:
            return
        logger.info(
            "插件缓存准备完成：残留=%s，过期=%s，临时=%s，用时=%.3f秒",
            结果["remaining"], 结果["expired"], 结果["temporary"],
            time.monotonic() - 开始,
        )
        if any(结果["migrated"].values()):
            logger.info("插件旧缓存迁移完成：数量=%s", sum(结果["migrated"].values()))
        句柄["cache_daily"] = 文件缓存.启动每日文件缓存任务(
            清理完成回调=_记录每日缓存清理
        )
        小说网盘.启动每日网盘远端清理任务(句柄["config"])
        数量 = 小说下载任务.恢复中断小说任务(帮助功能=句柄["help"], 权限工具=权限工具, 配置=句柄["config"])
        # 调度器先重新占用自己的 TXT，全局扫描只接管没有原会话的遗留任务。
        小说网盘.启动恢复待续传上传任务(句柄["config"])
        logger.info("插件重载任务恢复已启动：小说=%s，用时=%.3f秒", 数量, time.monotonic() - 开始)
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        logger.warning("插件后台恢复失败：stage=cache_resume, error_type=%s", type(异常).__name__)


async def _同步账号状态(配置: Any) -> None:
    async def _白名单() -> None:
        try:
            await asyncio.to_thread(权限工具.同步管理员白名单, 配置, 强制=True)
        except Exception as 异常:
            logger.warning("插件后台状态同步失败：stage=admins, error_type=%s", type(异常).__name__)

    async def _阅读() -> None:
        try:
            await QQ阅读.加载保存的QQ阅读登录态(配置)
        except Exception as 异常:
            logger.warning("插件后台状态同步失败：stage=reader, error_type=%s", type(异常).__name__)

    await asyncio.gather(_白名单(), _阅读())


async def 启动插件(上下文: Any, 配置: Any, 版本: str, 源码目录: Any) -> dict[str, Any]:
    global _当前句柄
    if _当前句柄 and not _当前句柄["stopped"]:
        if _当前句柄["context"] is 上下文 and _当前句柄["config"] is 配置:
            return _当前句柄
        await 停止插件(_当前句柄)
    from . import 帮助功能

    开始 = time.monotonic()
    句柄 = {"context": 上下文, "config": 配置, "stopped": False,
          "help": 帮助功能, "web": None, "cache_daily": None, "background": []}
    _当前句柄 = 句柄
    QQ官方交互桥.安装QQ官方帮助交互(上下文)
    消息记录.安装消息记录(上下文, 配置)
    文件缓存.重置进程上传占用()
    小说下载任务.保护中断小说缓存()
    蓝奏云图片归档.启动图片归档任务(配置)
    try:
        句柄["web"] = await 帮助网页.启动帮助网页服务(配置)
        句柄["background"] = [
            asyncio.create_task(_后台恢复(句柄), name="插件后台恢复"),
            asyncio.create_task(_同步账号状态(配置), name="插件账号状态同步"),
        ]
    except BaseException:
        await 停止插件(句柄)
        raise
    logger.info("馒头bot基础服务已启动：版本=%s, 源码目录=%s, 用时=%.3f秒", 版本, 源码目录, time.monotonic() - 开始)
    return 句柄


async def 停止插件(句柄: dict[str, Any] | None) -> None:
    global _当前句柄
    if not 句柄 or 句柄.get("stopped"):
        return
    句柄["stopped"] = True
    开始 = time.monotonic()
    for 任务 in 句柄["background"]:
        任务.cancel()
    if 句柄["background"]:
        await asyncio.gather(*句柄["background"], return_exceptions=True)

    async def _停止(阶段: str, 调用: Any, *参数: Any, **关键字: Any) -> None:
        try:
            await 调用(*参数, **关键字)
        except Exception as 异常:
            logger.warning("插件停止步骤失败：stage=%s, error_type=%s", 阶段, type(异常).__name__)

    await _停止("novels", 小说下载任务.停止小说下载任务, 保留待恢复=True)
    await _停止("pan", 小说网盘.停止网盘后台任务)
    await _停止("accounts", _ZLibrary.停止ZLibrary账号任务)
    await _停止("images", 蓝奏云图片归档.停止图片归档任务)
    await _停止("web", 帮助网页.停止帮助网页服务, 句柄["web"], 保留会话=True)
    await _停止("cache_daily", 文件缓存.停止每日文件缓存任务, 句柄["cache_daily"])
    await _停止("messages", 消息记录.停止消息记录, 超时=2.0)
    for 阶段, 关闭 in (
        ("switches", 小说功能开关.关闭小说功能状态执行器),
        ("reader", QQ阅读.关闭QQ阅读签名执行器),
        ("dejian", 得间小说.关闭得间资源),
        ("tadu", 塔读小说.关闭塔读资源),
    ):
        try:
            关闭()
        except Exception as 异常:
            logger.warning("插件资源关闭失败：stage=%s, error_type=%s", 阶段, type(异常).__name__)
    if _当前句柄 is 句柄:
        _当前句柄 = None
    logger.info("馒头bot重载交接完成：用时=%.3f秒", time.monotonic() - 开始)
