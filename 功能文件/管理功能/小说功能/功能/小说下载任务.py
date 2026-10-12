"""小说后台任务调度与同进程插件热重载恢复。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextvars import ContextVar
import importlib
import inspect
from pathlib import Path
import re
from typing import Any

from astrbot.api import logger

# reload 复用模块字典：保留输入和状态，不把关闭的生成器当作可续传任务。
_运行中的小说任务: set[asyncio.Task[Any]] = globals().get("_运行中的小说任务", set())
_小说任务记录: dict[tuple[Any, ...], dict[str, Any]] = globals().get("_小说任务记录", {})
_已结束小说任务: dict[tuple[Any, ...], asyncio.Task[Any]] = globals().get("_已结束小说任务", {})
_当前小说任务: ContextVar[Any] = globals().get(
    "_当前小说任务", ContextVar("mantou_novel_task", default=None)
)
_接受小说任务 = True


def _捕获回复流工厂(回复流: Any) -> dict[str, Any] | None:
    """捕获本项目顶层生成器的已绑定输入，找书使用解析后的书籍输入。"""
    if not inspect.isasyncgen(回复流):
        return None
    帧, 代码 = 回复流.ag_frame, 回复流.ag_code
    if 帧 is None or "<locals>" in getattr(代码, "co_qualname", 代码.co_name):
        return None
    工厂 = 帧.f_globals.get(代码.co_name)
    if not inspect.isasyncgenfunction(工厂) or 工厂.__code__ is not 代码:
        return None
    参数, 关键字 = [], {}
    for 名称, 项 in inspect.signature(工厂).parameters.items():
        if 名称 not in 帧.f_locals:
            return None
        值 = 帧.f_locals[名称]
        if 名称 == "找书候选" and isinstance(值, dict):
            值 = dict(值)
        if 项.kind == inspect.Parameter.POSITIONAL_ONLY:
            参数.append(值)
        elif 项.kind == inspect.Parameter.VAR_POSITIONAL:
            参数.extend(值)
        elif 项.kind == inspect.Parameter.VAR_KEYWORD:
            关键字.update(值)
        else:
            关键字[名称] = 值
    return {"module": 工厂.__module__, "name": 工厂.__name__,
            "args": tuple(参数), "kwargs": 关键字}


def _获取任务键(event: Any, 工厂: dict[str, Any] | None) -> tuple[Any, ...]:
    消息标识 = None
    获取标识 = getattr(event, "get_message_id", None)
    if callable(获取标识):
        try:
            消息标识 = 获取标识()
        except Exception:
            pass
    if not 消息标识:
        消息标识 = getattr(getattr(event, "message_obj", None), "message_id", None)
    if not 消息标识:
        消息标识 = getattr(event, "message_id", None)
    return (str(getattr(event, "unified_msg_origin", "")),
            str(消息标识) if 消息标识 else id(event),
            str((工厂 or {}).get("module") or ""),
            str((工厂 or {}).get("name") or ""))


async def _关闭回复流(回复流: Any) -> None:
    关闭 = getattr(回复流, "aclose", None)
    if callable(关闭):
        try:
            await 关闭()
        except Exception as 异常:
            logger.debug("小说回复流清理失败：错误类型=%s", type(异常).__name__)


async def _发送回复内容(event: Any, 内容: Any, 帮助功能: Any, 权限工具: Any) -> bool:
    if not 权限工具.是QQ官方机器人(event):
        return False
    if isinstance(内容, str):
        try:
            return bool(await 帮助功能.发送QQ官方提及Markdown(event, 内容))
        except Exception as 异常:
            logger.debug("小说下载后台发送QQ官方Markdown失败：错误类型=%s", type(异常).__name__)
            return False
    # MessageEventResult 继承 MessageChain，保留按钮和其他官方消息段。
    await event.send(内容)
    return True


def _记录书籍提示(记录: dict[str, Any], 内容: Any) -> None:
    if not isinstance(内容, str):
        return
    for 字段, 目标 in (("书名", "title"), ("作者", "author")):
        匹配 = re.search(rf"(?:^|\n){字段}[：:]\s*([^\n]+)", 内容)
        if 匹配:
            记录[目标] = 匹配.group(1).strip()


def 登记当前小说上传(
    配置: Any, 源缓存路径: str | Path, 文件名: str,
    指定网盘: str | None = None, 账号索引: dict[str, int] | None = None,
) -> None:
    """统一网盘入口上传前登记 TXT，重载复用文件及原账号。"""
    记录 = _当前小说任务.get()
    if not isinstance(记录, dict):
        return
    记录["upload"] = {
        "config": 配置, "path": str(Path(源缓存路径).absolute()),
        "filename": str(文件名), "platform": 指定网盘,
        "account_indices": dict(账号索引 or {}),
    }
    if not 记录.get("title"):
        匹配 = re.search(r"书名[：:](.+?) 作者[：:](.+)\.txt$", str(文件名))
        if 匹配:
            记录["title"], 记录["author"] = 匹配.groups()


def 标记当前小说完成通知(书名: Any = "", 作者: Any = "") -> None:
    """官方发送确认成功后调用，已经通知的任务不在重载后重发。"""
    记录 = _当前小说任务.get()
    if isinstance(记录, dict):
        记录["notified"] = True
        if 书名:
            记录["title"] = str(书名)
        if 作者:
            记录["author"] = str(作者)


def _读取小说发送结果(任务: asyncio.Task[Any]) -> None:
    if not 任务.cancelled():
        try:
            任务.exception()
        except Exception as 异常:
            logger.debug("小说发送任务回收失败：错误类型=%s", type(异常).__name__)


def 登记当前小说发送任务(任务: asyncio.Task[Any]) -> bool:
    """提交中的官方发送跨热重载保留，由恢复任务等待结果而非再次提交。"""
    记录 = _当前小说任务.get()
    if not isinstance(记录, dict):
        return False
    记录.setdefault("pending_sends", []).append(任务)
    任务.add_done_callback(_读取小说发送结果)
    return True


async def _接管小说发送任务(记录: dict[str, Any]) -> None:
    for 任务 in list(记录.get("pending_sends") or []):
        try:
            await asyncio.shield(任务)
        except asyncio.CancelledError:
            if not 任务.cancelled():
                raise
        except Exception as 异常:
            logger.debug("小说重载发送结果失败：错误类型=%s", type(异常).__name__)
        finally:
            if 任务.done() and 任务 in 记录.get("pending_sends", []):
                记录["pending_sends"].remove(任务)


async def _恢复小说上传(记录: dict[str, Any], 帮助功能: Any, 权限工具: Any) -> None:
    from 功能文件.管理功能.基础功能 import 文件缓存
    from 功能文件.管理功能.网盘功能 import 小说网盘

    上传 = 记录["upload"]
    路径 = Path(上传["path"])
    文件缓存.标记小说缓存正在使用(路径)
    try:
        旧任务 = 文件缓存.读取上传任务(路径) or {}
        分享链接 = str(旧任务.get("share_url") or "")
        if str(旧任务.get("state") or "") != "primary_done" or not 分享链接:
            结果 = await 小说网盘.上传小说并获取分享链接(
                上传["config"], 路径, 上传["filename"],
                _指定网盘=上传.get("platform"),
                _账号索引=上传.get("account_indices"),
            )
            if not 结果.get("success"):
                await _发送回复内容(记录["event"], "文件发送失败，请稍后再试", 帮助功能, 权限工具)
                return
            分享链接 = str(结果.get("share_url") or "")
        if not 记录.get("notified"):
            结果 = await 小说网盘.发送小说下载完成链接(
                记录["event"], 记录.get("title") or "未知",
                记录.get("author") or "未知", 分享链接,
            )
            if 结果.get("sent"):
                标记当前小说完成通知()
            else:
                await _发送回复内容(记录["event"], "文件发送失败，请稍后再试", 帮助功能, 权限工具)
    finally:
        if 记录.get("cancel_requested") and not 记录.get("notified"):
            文件缓存.解除小说缓存占用(路径)
        else:
            文件缓存.删除小说缓存文件(路径)


async def _创建恢复回复流(记录: dict[str, Any]) -> Any:
    显式工厂 = 记录.get("factory_callable")
    if callable(显式工厂):
        回复流 = 显式工厂()
        return await 回复流 if inspect.isawaitable(回复流) else 回复流
    工厂 = 记录.get("factory")
    if not 工厂:
        raise RuntimeError("reply_factory_missing")
    模块 = importlib.import_module(工厂["module"])
    return getattr(模块, 工厂["name"])(*工厂["args"], **工厂["kwargs"])


async def _消费小说回复流(
    event: Any, 回复流: AsyncIterator[Any] | None,
    帮助功能: Any, 权限工具: Any, 记录: dict[str, Any],
) -> None:
    from 功能文件.管理功能.网盘功能 import 小说网盘

    记录.pop("initial_stream", None)
    事件令牌 = 小说网盘.设置当前网盘事件(event)
    任务令牌 = _当前小说任务.set(记录)
    try:
        if 回复流 is None:
            await _接管小说发送任务(记录)
            if 记录.get("notified"):
                return
        if 回复流 is None and 记录.get("upload") and Path(记录["upload"]["path"]).is_file():
            await _恢复小说上传(记录, 帮助功能, 权限工具)
            return
        if 回复流 is None:
            回复流 = await _创建恢复回复流(记录)
        async for 内容 in 回复流:
            _记录书籍提示(记录, 内容)
            if isinstance(内容, str) and 内容 in 记录["sent_text"]:
                continue
            try:
                async def _发送并登记(本次内容: Any = 内容) -> bool:
                    已发送 = await _发送回复内容(event, 本次内容, 帮助功能, 权限工具)
                    if 已发送 and isinstance(本次内容, str):
                        记录["sent_text"].add(本次内容)
                    return 已发送

                发送任务 = asyncio.create_task(_发送并登记(), name="小说提示发送")
                登记当前小说发送任务(发送任务)
                try:
                    await asyncio.shield(发送任务)
                finally:
                    if 发送任务.done() and 发送任务 in 记录.get("pending_sends", []):
                        记录["pending_sends"].remove(发送任务)
            except asyncio.CancelledError:
                raise
            except Exception as 异常:
                logger.warning("小说下载后台发送回复失败：错误类型=%s", type(异常).__name__)
    except asyncio.CancelledError:
        if 记录.get("cancel_requested") and not 记录.get("notified"):
            if 记录.get("factory") or 记录.get("factory_callable") or 记录.get("upload"):
                记录["state"] = "suspended"
        raise
    except Exception as 异常:
        logger.warning("小说下载后台任务异常：错误类型=%s", type(异常).__name__)
    finally:
        if 回复流 is not None:
            await _关闭回复流(回复流)
        _当前小说任务.reset(任务令牌)
        小说网盘.清除当前网盘事件(事件令牌)
        if 记录.get("state") != "suspended":
            if _小说任务记录.get(记录["key"]) is 记录:
                _小说任务记录.pop(记录["key"], None)
            当前任务 = asyncio.current_task()
            if 当前任务 is not None:
                _已结束小说任务[记录["key"]] = 当前任务
                while len(_已结束小说任务) > 512:
                    _已结束小说任务.pop(next(iter(_已结束小说任务)))


def _任务完成(task: asyncio.Task[Any]) -> None:
    _运行中的小说任务.discard(task)
    if not task.cancelled():
        try:
            task.exception()
        except Exception as 异常:
            logger.warning("小说下载后台任务回收异常：错误类型=%s", type(异常).__name__)


def _启动记录任务(
    记录: dict[str, Any], 回复流: Any, 帮助功能: Any, 权限工具: Any,
) -> asyncio.Task[Any]:
    记录["state"], 记录["cancel_requested"] = "running", False
    记录["initial_stream"] = 回复流
    task = asyncio.create_task(
        _消费小说回复流(记录["event"], 回复流, 帮助功能, 权限工具, 记录),
        name="小说下载恢复" if 回复流 is None else "小说下载",
    )
    记录["task"] = 记录["last_task"] = task
    _运行中的小说任务.add(task)
    task.add_done_callback(_任务完成)
    return task


def 启动小说回复流任务(
    event: Any, 回复流: AsyncIterator[Any], 帮助功能: Any, 权限工具: Any,
    *, 回复流工厂: Callable[[], Any] | None = None,
) -> asyncio.Task[Any]:
    """立即启动独立下载，同一消息重复分发时复用现有任务。"""
    工厂 = _捕获回复流工厂(回复流)
    键 = _获取任务键(event, 工厂)
    已结束任务 = _已结束小说任务.get(键)
    if 已结束任务 is not None:
        asyncio.create_task(_关闭回复流(回复流))
        return 已结束任务
    旧记录 = _小说任务记录.get(键)
    if 旧记录 is not None and 旧记录.get("task") is not None:
        asyncio.create_task(_关闭回复流(回复流))
        return 旧记录["task"]
    if 旧记录 is not None:
        清理任务 = asyncio.create_task(_关闭回复流(回复流))
        if not _接受小说任务:
            return 清理任务
        return _启动记录任务(旧记录, None, 帮助功能, 权限工具)
    if 旧记录 is None:
        记录 = {"key": 键, "event": event, "factory": 工厂,
                "factory_callable": 回复流工厂, "sent_text": set(),
                "notified": False, "state": "running", "cancel_requested": False}
        _小说任务记录[键] = 记录
    if not _接受小说任务:
        记录["cancel_requested"], 记录["state"], 记录["task"] = True, "suspended", None
        if not 工厂 and not 回复流工厂:
            _小说任务记录.pop(键, None)
        return asyncio.create_task(_关闭回复流(回复流))
    return _启动记录任务(记录, 回复流, 帮助功能, 权限工具)


async def 停止小说下载任务(*, 保留待恢复: bool = True) -> None:
    """等待取消完成，热重载只保留同进程可重建的任务输入。"""
    global _接受小说任务
    _接受小说任务 = False
    任务列表 = list(_运行中的小说任务)
    for 记录 in list(_小说任务记录.values()):
        if 记录.get("task") in 任务列表:
            记录["cancel_requested"] = 保留待恢复
    for task in 任务列表:
        task.cancel()
    await asyncio.gather(*任务列表, return_exceptions=True)
    _运行中的小说任务.difference_update(任务列表)
    # 尚未首次调度的协程没有运行 finally，也要关闭输入生成器并保留工厂。
    for 键, 记录 in list(_小说任务记录.items()):
        task = 记录.get("task")
        if task not in 任务列表:
            continue
        await _关闭回复流(记录.pop("initial_stream", None))
        if 保留待恢复 and task.cancelled() and not 记录.get("notified") and (
            记录.get("factory") or 记录.get("factory_callable") or 记录.get("upload")
        ):
            记录["state"], 记录["task"] = "suspended", None
        elif 记录.get("state") != "suspended" or not 保留待恢复:
            _小说任务记录.pop(键, None)
    if not 保留待恢复:
        _小说任务记录.clear()
        _已结束小说任务.clear()


def 保护中断小说缓存() -> int:
    """启动清理/迁移前保护同进程中断任务的 TXT；此时不执行下载。"""
    from 功能文件.管理功能.基础功能 import 文件缓存

    已保护 = 0
    for 记录 in _小说任务记录.values():
        if 记录.get("notified") or not 记录.get("upload"):
            continue
        路径 = Path(记录["upload"]["path"])
        if 路径.is_file():
            文件缓存.标记小说缓存正在使用(路径)
            已保护 += 1
    return 已保护


def 恢复中断小说任务(帮助功能: Any, 权限工具: Any, 配置: Any = None) -> int:
    """所有平台模块加载后调用，先登记 TXT 占用再启动原会话任务。"""
    global _接受小说任务

    _接受小说任务 = True
    保护中断小说缓存()
    已恢复 = 0
    for 记录 in list(_小说任务记录.values()):
        if 记录.get("state") != "suspended":
            continue
        if 记录.get("notified"):
            from 功能文件.管理功能.基础功能 import 文件缓存

            if 记录.get("upload"):
                文件缓存.删除小说缓存文件(记录["upload"]["path"])
            _小说任务记录.pop(记录["key"], None)
            最后任务 = 记录.get("last_task")
            if 最后任务 is not None:
                _已结束小说任务[记录["key"]] = 最后任务
                while len(_已结束小说任务) > 512:
                    _已结束小说任务.pop(next(iter(_已结束小说任务)))
            continue
        if 配置 is not None:
            工厂 = 记录.get("factory") or {}
            for 名称 in ("配置", "config"):
                if 名称 in 工厂.get("kwargs", {}):
                    工厂["kwargs"][名称] = 配置
            if 记录.get("upload"):
                记录["upload"]["config"] = 配置
        _启动记录任务(记录, None, 帮助功能, 权限工具)
        已恢复 += 1
    if 已恢复:
        logger.info("插件重载恢复原会话小说任务：数量=%s", 已恢复)
    return 已恢复


def 获取运行中的小说任务数() -> int:
    return len(_运行中的小说任务)


def 获取待恢复小说任务数() -> int:
    return sum(记录.get("state") == "suspended" for 记录 in _小说任务记录.values())
