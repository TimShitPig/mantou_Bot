from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from astrbot.api import logger
from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.群聊功能.群列表工具 import 获取机器人所在群号列表


清理群文件命令 = {"清理群文件", "群文件清理"}
清理全部群文件命令 = {"清理全部群文件"}
群文件清理诊断最大长度 = 80000
群文件删除并发数 = 200
群文件ID失效重试次数 = 1


async def 处理群文件清理(event: Any, 命令文本: str, 配置: Any) -> str | None:
    if 命令文本 not in 清理群文件命令 and 命令文本 not in 清理全部群文件命令:
        return None

    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用群文件清理"

    if 命令文本 in 清理全部群文件命令:
        return await 处理全部群文件清理(event)

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

    if not await 机器人是群管理员(bot, 群号, event):
        logger.info(f"群文件清理跳过非管理群：group_id={群号}")
        return None

    await 发送清理开始提示(event, "正在清理群文件")

    try:
        删除成功, 删除失败 = await 清理指定群文件(bot, 群号)
        return f"群文件清理完成：成功 {删除成功} 个，失败 {删除失败} 个"
    except Exception as exc:
        logger.warning(f"群文件清理失败：group_id={群号}, error={exc}")
        return f"群文件清理失败：{exc}"


async def 处理全部群文件清理(event: Any) -> str:
    bot = getattr(event, "bot", None)
    if bot is None:
        记录群文件清理事件诊断(event, None, "", "缺少 bot 实例")
        return "全部群文件清理失败：当前事件缺少 bot 实例"

    if not 支持群文件动作接口(bot):
        记录群文件清理事件诊断(event, bot, "", "缺少 api.call_action")
        return "全部群文件清理失败：当前适配器没有群文件接口，已输出群文件清理事件诊断"

    try:
        群号列表 = await 获取机器人所在群号列表(bot)
    except Exception as exc:
        logger.warning(f"全部群文件清理获取群列表失败：error={exc}")
        return f"全部群文件清理失败：{exc}"

    await 发送清理开始提示(event, "正在清理群文件（全部）")

    群成功 = 0
    群失败 = 0
    文件成功 = 0
    文件失败 = 0
    失败群: list[tuple[str, Exception]] = []

    for 群号 in 群号列表:
        if not await 机器人是群管理员(bot, 群号, event):
            logger.info(f"全部群文件清理跳过非管理群：group_id={群号}")
            continue
        try:
            本群文件成功, 本群文件失败 = await 清理指定群文件(bot, 群号)
            群成功 += 1
            文件成功 += 本群文件成功
            文件失败 += 本群文件失败
            logger.info(f"全部群文件清理完成单群：group_id={群号}, success={本群文件成功}, failed={本群文件失败}")
        except Exception as exc:
            群失败 += 1
            失败群.append((群号, exc))
            logger.warning(f"全部群文件清理失败单群：group_id={群号}, error={exc}")

    行列表 = [f"全部群文件清理完成：群成功 {群成功} 个，群失败 {群失败} 个", f"文件成功 {文件成功} 个，文件失败 {文件失败} 个"]
    if 失败群:
        行列表.append("失败群：" + "；".join(f"{群号}：{错误}" for 群号, 错误 in 失败群))
    return "\n".join(行列表)


async def 清理指定群文件(bot: Any, 群号: Any) -> tuple[int, int]:
    删除成功 = 0
    删除失败 = 0
    已失败文件: set[str] = set()

    while True:
        文件列表 = await 获取全部群文件(bot, 群号)
        待删文件 = [文件 for 文件 in 文件列表 if 获取文件稳定键(文件) not in 已失败文件]
        if not 待删文件:
            break

        待删批次 = 待删文件[:群文件删除并发数]
        logger.info(
            f"群文件清理开始并发删除：group_id={群号}, batch={len(待删批次)}, "
            f"remaining={len(待删文件)}, concurrency={群文件删除并发数}"
        )
        本轮结果 = await asyncio.gather(
            *(删除单个群文件并处理失效ID(bot, 群号, 文件) for 文件 in 待删批次)
        )
        for 结果 in 本轮结果:
            文件 = 结果["文件"]
            if 结果["成功"]:
                if 结果.get("跳过"):
                    logger.info(f"群文件清理跳过失效记录：group_id={群号}, file={文件}, reason={结果.get('说明', '')}")
                else:
                    删除成功 += 1
                continue

            删除失败 += 1
            已失败文件.add(获取文件稳定键(文件))
            logger.warning(f"群文件删除失败：group_id={群号}, file={文件}, error={结果['错误']}")

    return 删除成功, 删除失败


async def 删除单个群文件并处理失效ID(bot: Any, 群号: Any, 文件: dict[str, Any]) -> dict[str, Any]:
    当前文件 = 文件
    最后错误: Exception | None = None

    for 重试轮次 in range(0, 群文件ID失效重试次数 + 1):
        try:
            await 删除群文件记录(bot, 群号, 当前文件)
            return {"文件": 当前文件, "成功": True, "跳过": False, "错误": None}
        except Exception as exc:
            最后错误 = exc
            if not 是文件ID无效错误(exc):
                return {"文件": 当前文件, "成功": False, "错误": exc}
            if 重试轮次 >= 群文件ID失效重试次数:
                break

            try:
                await asyncio.sleep(min(0.5 * (重试轮次 + 1), 2.0))
                新文件列表 = await 获取全部群文件(bot, 群号)
            except Exception as refresh_exc:
                return {"文件": 当前文件, "成功": False, "错误": refresh_exc}

            新文件 = 查找同一个群文件(文件, 新文件列表)
            if 新文件 is None:
                return {
                    "文件": 当前文件,
                    "成功": True,
                    "跳过": True,
                    "错误": None,
                    "说明": f"文件ID失效且第 {重试轮次 + 1} 次重新扫描后文件已不存在",
                }

            logger.info(
                "群文件ID失效后使用重新扫描记录重试删除："
                f"group_id={群号}, file_name={文件.get('file_name')}, retry={重试轮次 + 1}, "
                f"old_file_id={当前文件.get('file_id')}, new_file_id={新文件.get('file_id')}, "
                f"busid={新文件.get('busid')}"
            )
            当前文件 = 新文件

    return {"文件": 当前文件, "成功": False, "错误": 最后错误}


async def 删除群文件记录(bot: Any, 群号: Any, 文件: dict[str, Any]) -> None:
    try:
        await 删除群文件(bot, 群号, 文件["file_id"], 文件.get("busid"))
    except Exception as exc:
        if 文件.get("busid") is None or not 是文件ID无效错误(exc):
            raise
        logger.info(
            "群文件删除携带busid失败，尝试不带busid重试："
            f"group_id={群号}, file_name={文件.get('file_name')}, file_id={文件.get('file_id')}, busid={文件.get('busid')}"
        )
        await 删除群文件(bot, 群号, 文件["file_id"], None)


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


async def 发送清理开始提示(event: Any, 文本: str) -> None:
    try:
        发送方法 = getattr(event, "send", None)
        if not callable(发送方法):
            return
        结果对象 = 文本
        plain_result = getattr(event, "plain_result", None)
        if callable(plain_result):
            结果对象 = plain_result(文本)
        结果 = 发送方法(结果对象)
        if asyncio.iscoroutine(结果) or hasattr(结果, "__await__"):
            await 结果
    except Exception as exc:
        logger.warning(f"群文件清理开始提示发送失败：error={exc}")


async def 机器人是群管理员(bot: Any, 群号: Any, event: Any = None) -> bool:
    机器人QQ = 获取机器人QQ(bot, event)
    if not 机器人QQ:
        机器人QQ = await 从登录信息获取机器人QQ(bot)
    if not 机器人QQ:
        logger.info(f"群文件清理跳过非管理群：group_id={群号}, reason=缺少机器人QQ，无法确认机器人是QQ群管理员")
        return False
    try:
        响应 = await 调用动作(bot, "get_group_member_info", group_id=int(群号), user_id=int(机器人QQ), no_cache=True)
    except Exception as exc:
        logger.info(f"群文件清理跳过非管理群：group_id={群号}, bot_qq={机器人QQ}, error={exc}")
        return False

    数据 = 响应.get("data") if isinstance(响应, dict) and "data" in 响应 else 响应
    角色 = 数据.get("role") if isinstance(数据, dict) else None
    return 是群管理角色(角色)


async def 从登录信息获取机器人QQ(bot: Any) -> str:
    try:
        响应 = await 调用动作(bot, "get_login_info")
    except Exception as exc:
        logger.info(f"群文件清理获取机器人登录信息失败：error={exc}")
        return ""
    return 提取数字QQ(响应)


def 获取机器人QQ(bot: Any, event: Any = None) -> str:
    消息对象 = getattr(event, "message_obj", None) if event is not None else None
    候选对象 = [
        event,
        消息对象,
        bot,
        getattr(bot, "api", None),
        getattr(bot, "account", None),
        getattr(bot, "client", None),
        getattr(bot, "adapter", None),
    ]
    for 对象 in 候选对象:
        QQ = 提取数字QQ(对象)
        if QQ:
            return QQ
    return ""


def 提取数字QQ(对象: Any) -> str:
    if 对象 is None:
        return ""
    if isinstance(对象, (str, int)):
        文本 = str(对象 or "").strip()
        return 文本 if re.fullmatch(r"[1-9]\d{4,11}", 文本) else ""
    if isinstance(对象, dict):
        数据 = 对象.get("data") if isinstance(对象.get("data"), dict) else None
        if 数据:
            QQ = 提取数字QQ(数据)
            if QQ:
                return QQ
    for 字段名 in ("self_id", "bot_id", "robot_id", "uin", "qq", "user_id"):
        值 = 读取字段(对象, 字段名)
        文本 = str(值 or "").strip()
        if re.fullmatch(r"[1-9]\d{4,11}", 文本):
            return 文本
    return ""


def 是群管理角色(角色: Any) -> bool:
    return str(角色 or "").strip().lower() in {"owner", "admin"}


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


def 获取文件稳定键(文件: dict[str, Any]) -> str:
    return "|".join(
        [
            str(文件.get("file_name") or ""),
            str(获取群文件大小(文件) or ""),
            str(文件.get("uploader") or ""),
            str(文件.get("busid") or ""),
        ]
    )


def 是文件ID无效错误(exc: Exception) -> bool:
    文本列表 = [str(exc)]
    for 字段名 in ("retcode", "message", "wording", "status"):
        值 = getattr(exc, 字段名, None)
        if 值 is not None:
            if 字段名 == "retcode" and str(值) == "1200":
                return True
            文本列表.append(str(值))
    文本 = " ".join(文本列表)
    return "Invalid file_id" in 文本 or "retcode=1200" in 文本


def 查找同一个群文件(原文件: dict[str, Any], 文件列表: list[dict[str, Any]]) -> dict[str, Any] | None:
    原键 = 获取文件去重键(原文件)
    for 文件 in 文件列表:
        if 原键 and 获取文件去重键(文件) == 原键:
            return 文件

    for 文件 in 文件列表:
        if 是同一个群文件(原文件, 文件):
            return 文件
    return None


def 是同一个群文件(原文件: dict[str, Any], 新文件: dict[str, Any]) -> bool:
    if 原文件.get("file_name") != 新文件.get("file_name"):
        return False

    for 字段名 in ("busid", "uploader"):
        原值 = 原文件.get(字段名)
        新值 = 新文件.get(字段名)
        if 原值 is not None and 新值 is not None and str(原值) != str(新值):
            return False

    原大小 = 获取群文件大小(原文件)
    新大小 = 获取群文件大小(新文件)
    if 原大小 is not None and 新大小 is not None and 原大小 != 新大小:
        return False

    return True


def 获取群文件大小(文件: dict[str, Any]) -> int | None:
    for 字段名 in ("size", "file_size"):
        值 = 文件.get(字段名)
        if 值 is None:
            continue
        try:
            return int(值)
        except (TypeError, ValueError):
            continue
    return None


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
