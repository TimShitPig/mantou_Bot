"""小说下载后台任务调度。

每次识别到一本小说都创建一个独立任务。这里不设置全局队列、平台队列或
共享信号量，避免一本文本下载占用消息事件后让后续小说排队。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from astrbot.api import logger

_运行中的小说任务: set[asyncio.Task[Any]] = set()


async def _发送回复内容(
    event: Any,
    内容: Any,
    帮助功能: Any,
    权限工具: Any,
) -> None:
    """把回复流项目直接发送到原会话。"""
    if not 权限工具.是QQ官方机器人(event):
        return
    if isinstance(内容, str):
        try:
            await 帮助功能.发送QQ官方提及Markdown(event, 内容)
        except Exception as 异常:
            logger.debug(
                "小说下载后台发送QQ官方Markdown失败：错误类型=%s",
                type(异常).__name__,
            )
        return

    # MessageEventResult 继承 MessageChain，保留对象本身以避免丢失 QQ 官方按钮等消息段。
    await event.send(内容)


async def _消费小说回复流(
    event: Any,
    回复流: AsyncIterator[Any],
    帮助功能: Any,
    权限工具: Any,
) -> None:
    from 功能文件.管理功能.网盘功能 import 小说网盘

    事件令牌 = 小说网盘.设置当前网盘事件(event)
    try:
        async for 内容 in 回复流:
            try:
                await _发送回复内容(event, 内容, 帮助功能, 权限工具)
            except asyncio.CancelledError:
                raise
            except Exception as 异常:
                # 发送出口的临时失败不应中止正文下载和后续清理。
                logger.warning(
                    "小说下载后台发送回复失败：错误类型=%s",
                    type(异常).__name__,
                )
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        logger.warning(
            "小说下载后台任务异常：错误类型=%s",
            type(异常).__name__,
        )
    finally:
        小说网盘.清除当前网盘事件(事件令牌)


def _任务完成(task: asyncio.Task[Any]) -> None:
    _运行中的小说任务.discard(task)
    if task.cancelled():
        return
    try:
        task.exception()
    except Exception as 异常:
        logger.warning(
            "小说下载后台任务回收异常：错误类型=%s",
            type(异常).__name__,
        )


def 启动小说回复流任务(
    event: Any,
    回复流: AsyncIterator[Any],
    帮助功能: Any,
    权限工具: Any,
) -> asyncio.Task[Any]:
    """立即启动一本小说的独立下载任务，不进入任何全局排队。"""
    task = asyncio.create_task(
        _消费小说回复流(event, 回复流, 帮助功能, 权限工具),
        name="小说下载",
    )
    _运行中的小说任务.add(task)
    task.add_done_callback(_任务完成)
    return task


async def 停止小说下载任务() -> None:
    """插件重载/停止时取消并等待所有仍在运行的小说任务。"""
    任务列表 = list(_运行中的小说任务)
    if not 任务列表:
        return
    for task in 任务列表:
        task.cancel()
    await asyncio.gather(*任务列表, return_exceptions=True)
    _运行中的小说任务.difference_update(任务列表)


def 获取运行中的小说任务数() -> int:
    """返回当前后台小说任务数，供受控诊断使用。"""
    return len(_运行中的小说任务)
