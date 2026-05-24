from __future__ import annotations
from typing import Any

from astrbot.api import logger


清理群文件命令 = {"清理群文件", "群文件清理"}


async def 处理群文件清理(event: Any, 命令文本: str, 配置: Any) -> str | None:
    if 命令文本 not in 清理群文件命令:
        return None

    发送者 = 获取发送者QQ(event)
    管理员列表 = 获取管理员QQ列表(配置)
    if not 发送者 or 发送者 not in 管理员列表:
        return "没有权限使用群文件清理。"

    群号 = 获取群号(event)
    if not 群号:
        return "群文件清理只能在群聊中使用。"

    bot = getattr(event, "bot", None)
    if bot is None:
        return "群文件清理失败：当前事件缺少 bot 实例。"

    try:
        文件列表 = await 获取全部群文件(bot, 群号)
        删除成功 = 0
        删除失败 = 0
        for 文件 in 文件列表:
            try:
                await 删除群文件(bot, 群号, 文件["file_id"], 文件.get("busid"))
                删除成功 += 1
            except Exception as exc:
                删除失败 += 1
                logger.warning(f"群文件删除失败：group_id={群号}, file={文件}, error={exc}")

        return f"群文件清理完成：成功 {删除成功} 个，失败 {删除失败} 个"
    except Exception as exc:
        logger.warning(f"群文件清理失败：group_id={群号}, error={exc}")
        return f"群文件清理失败：{exc}"


async def 获取全部群文件(bot: Any, 群号: Any) -> list[dict[str, Any]]:
    根目录 = await 调用动作(bot, "get_group_root_files", group_id=群号)
    文件列表 = 提取文件列表(根目录)
    文件夹列表 = 提取文件夹列表(根目录)

    for 文件夹 in 文件夹列表:
        文件夹编号 = 文件夹.get("folder_id") or 文件夹.get("id")
        if not 文件夹编号:
            continue
        文件夹内容 = await 调用动作(bot, "get_group_files_by_folder", group_id=群号, folder_id=文件夹编号)
        文件列表.extend(提取文件列表(文件夹内容))
    return [文件 for 文件 in 文件列表 if 文件.get("file_id")]


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


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
