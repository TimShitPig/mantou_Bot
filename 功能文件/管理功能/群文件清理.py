from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from astrbot.api import logger


清理群文件命令 = {"清理群文件", "群文件清理"}
群文件清理诊断最大长度 = 8000
群文件删除并发数 = 20


async def 处理群文件清理(event: Any, 命令文本: str, 配置: Any) -> str | None:
    if 命令文本 not in 清理群文件命令:
        return None

    发送者 = 获取发送者QQ(event)
    管理员列表 = 获取管理员QQ列表(配置)
    if not 发送者 or 发送者 not in 管理员列表:
        return "没有权限使用群文件清理"

    群号 = 获取群号(event)
    if not 群号:
        记录群文件清理事件诊断(event, None, 群号, "缺少群号")
        return "群文件清理只能在群聊中使用"

    bot = getattr(event, "bot", None)
    if bot is None:
        记录群文件清理事件诊断(event, None, 群号, "缺少 bot 实例")
        return "群文件清理失败：当前事件缺少 bot 实例"

    if not 是数字群号(群号):
        记录群文件清理事件诊断(event, bot, 群号, "群号不是数字QQ群号")
        return "群文件清理失败：当前适配器返回的不是数字QQ群号，qq_official 的 group_openid 不能用于 OneBot 群文件接口"

    if not 支持群文件动作接口(bot):
        记录群文件清理事件诊断(event, bot, 群号, "缺少 api.call_action")
        return "群文件清理失败：当前适配器没有群文件接口，已输出群文件清理事件诊断"

    try:
        删除成功 = 0
        删除失败 = 0
        已失败文件: set[str] = set()

        while True:
            文件列表 = await 获取全部群文件(bot, 群号)
            待删文件 = [文件 for 文件 in 文件列表 if 获取文件去重键(文件) not in 已失败文件]
            if not 待删文件:
                break

            logger.info(
                f"群文件清理开始并发删除：group_id={群号}, count={len(待删文件)}, concurrency={群文件删除并发数}"
            )
            本轮结果 = await 并发删除群文件列表(bot, 群号, 待删文件)
            本轮成功 = sum(1 for 结果 in 本轮结果 if 结果["成功"])
            for 结果 in 本轮结果:
                文件 = 结果["文件"]
                if 结果["成功"]:
                    删除成功 += 1
                    continue
                删除失败 += 1
                已失败文件.add(获取文件去重键(文件))
                logger.warning(f"群文件删除失败：group_id={群号}, file={文件}, error={结果['错误']}")

            if 本轮成功 == 0:
                break

        return f"群文件清理完成：成功 {删除成功} 个，失败 {删除失败} 个"
    except Exception as exc:
        logger.warning(f"群文件清理失败：group_id={群号}, error={exc}")
        return f"群文件清理失败：{exc}"


async def 并发删除群文件列表(bot: Any, 群号: Any, 文件列表: list[dict[str, Any]]) -> list[dict[str, Any]]:
    信号量 = asyncio.Semaphore(群文件删除并发数)

    async def 删除单个文件(文件: dict[str, Any]) -> dict[str, Any]:
        async with 信号量:
            try:
                await 删除群文件(bot, 群号, 文件["file_id"], 文件.get("busid"))
                return {"文件": 文件, "成功": True, "错误": None}
            except Exception as exc:
                return {"文件": 文件, "成功": False, "错误": exc}

    return await asyncio.gather(*(删除单个文件(文件) for 文件 in 文件列表))


async def 获取全部群文件(bot: Any, 群号: Any) -> list[dict[str, Any]]:
    根目录 = await 调用动作(bot, "get_group_root_files", group_id=群号)
    文件列表 = 提取文件列表(根目录)
    待处理文件夹 = 提取文件夹列表(根目录)
    已处理文件夹: set[str] = set()

    while 待处理文件夹:
        文件夹 = 待处理文件夹.pop(0)
        文件夹编号 = 文件夹.get("folder_id") or 文件夹.get("id")
        if not 文件夹编号 or str(文件夹编号) in 已处理文件夹:
            continue
        已处理文件夹.add(str(文件夹编号))
        文件夹内容 = await 调用动作(bot, "get_group_files_by_folder", group_id=群号, folder_id=文件夹编号)
        文件列表.extend(提取文件列表(文件夹内容))
        待处理文件夹.extend(提取文件夹列表(文件夹内容))
    return 去重文件列表(文件列表)


async def 删除群文件(bot: Any, 群号: Any, 文件编号: Any, busid: Any = None) -> None:
    参数 = {"group_id": 群号, "file_id": 文件编号}
    if busid is not None:
        参数["busid"] = busid
    await 调用动作(bot, "delete_group_file", **参数)


async def 调用动作(bot: Any, 动作: str, **参数: Any) -> Any:
    api = getattr(bot, "api", None)
    调用方法 = getattr(api, "call_action", None)
    if not callable(调用方法):
        raise RuntimeError("当前 bot 没有 api.call_action 接口")
    return await 调用方法(动作, **参数)


def 支持群文件动作接口(bot: Any) -> bool:
    api = getattr(bot, "api", None)
    return callable(getattr(api, "call_action", None))


def 提取文件列表(响应: Any) -> list[dict[str, Any]]:
    数据 = 响应.get("data") if isinstance(响应, dict) and isinstance(响应.get("data"), dict) else 响应
    if not isinstance(数据, dict):
        return []
    文件列表 = 数据.get("files") or []
    return [文件 for 文件 in 文件列表 if isinstance(文件, dict)]


def 提取文件夹列表(响应: Any) -> list[dict[str, Any]]:
    数据 = 响应.get("data") if isinstance(响应, dict) and isinstance(响应.get("data"), dict) else 响应
    if not isinstance(数据, dict):
        return []
    文件夹列表 = 数据.get("folders") or []
    return [文件夹 for 文件夹 in 文件夹列表 if isinstance(文件夹, dict)]


def 去重文件列表(文件列表: list[dict[str, Any]]) -> list[dict[str, Any]]:
    结果 = []
    已见文件: set[str] = set()
    for 文件 in 文件列表:
        去重键 = 获取文件去重键(文件)
        if not 去重键:
            continue
        if 去重键 in 已见文件:
            continue
        已见文件.add(去重键)
        结果.append(文件)
    return 结果


def 获取文件去重键(文件: dict[str, Any]) -> str:
    文件编号 = 文件.get("file_id")
    if not 文件编号:
        return ""
    return f"{文件编号}:{文件.get('busid', '')}"


def 获取管理员QQ列表(配置: Any) -> set[str]:
    if not 配置:
        return set()
    值 = 读取字段(配置, "group_file_cleanup_admin_qq") or []
    if isinstance(值, str):
        值 = [值]
    if not isinstance(值, list):
        return set()
    return {str(项目).strip() for 项目 in 值 if str(项目).strip()}


def 获取发送者QQ(event: Any) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("sender_id", "user_id", "sender"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("user_id") or 值.get("id")
            if 值:
                return str(值)
    return ""


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("group_id", "group"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("group_id") or 值.get("id")
            if 值:
                return str(值)
    return ""


def 是数字群号(值: Any) -> bool:
    return bool(re.fullmatch(r"[1-9]\d{4,11}", str(值 or "").strip()))


def 记录群文件清理事件诊断(event: Any, bot: Any, 群号: str, 原因: str) -> None:
    try:
        api = getattr(bot, "api", None)
        诊断数据 = {
            "reason": 原因,
            "event_type": type(event).__name__,
            "group_id": 群号,
            "group_id_is_numeric": 是数字群号(群号),
            "bot_type": type(bot).__name__ if bot is not None else "",
            "api_type": type(api).__name__ if api is not None else "",
            "has_call_action": callable(getattr(api, "call_action", None)),
            "expected_actions": ["get_group_root_files", "get_group_files_by_folder", "delete_group_file"],
            "event": 诊断序列化对象(event),
            "message_obj": 诊断序列化对象(getattr(event, "message_obj", None)),
        }
        文本 = json.dumps(诊断数据, ensure_ascii=False, default=str)
        logger.info(f"群文件清理事件诊断：{限制文本长度(文本, 群文件清理诊断最大长度)}")
    except Exception as exc:
        logger.warning(f"群文件清理事件诊断失败：error={exc}")


def 诊断序列化对象(值: Any, 深度: int = 0, 已见: set[int] | None = None) -> Any:
    if 已见 is None:
        已见 = set()
    if 值 is None or isinstance(值, (str, int, float, bool)):
        return 限制文本长度(值, 1000) if isinstance(值, str) else 值
    if callable(值):
        return f"<callable {getattr(值, '__name__', type(值).__name__)}>"
    对象编号 = id(值)
    if 对象编号 in 已见:
        return "<循环引用>"
    已见.add(对象编号)
    if 深度 >= 4:
        return 限制文本长度(str(值), 1000)

    if isinstance(值, dict):
        结果 = {}
        for 键, 子项 in list(值.items())[:80]:
            if str(键).startswith("_") or str(键) in {"bot", "api", "context"}:
                continue
            结果[str(键)] = 诊断序列化对象(子项, 深度 + 1, 已见)
        return 结果
    if isinstance(值, (list, tuple, set)):
        return [诊断序列化对象(子项, 深度 + 1, 已见) for 子项 in list(值)[:80]]
    if hasattr(值, "__dict__"):
        结果 = {"__class__": type(值).__name__}
        for 键, 子项 in vars(值).items():
            if str(键).startswith("_") or str(键) in {"bot", "api", "context"}:
                continue
            结果[str(键)] = 诊断序列化对象(子项, 深度 + 1, 已见)
        return 结果
    return 限制文本长度(str(值), 1000)


def 限制文本长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
