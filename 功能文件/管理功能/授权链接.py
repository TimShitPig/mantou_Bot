from __future__ import annotations

import json
import urllib.parse
from typing import Any

from astrbot.api import logger


授权命令 = {"授权"}
页面名 = "ai_group_service_agreement_pop_page"
跳转地址 = "https://club.vip.qq.com/transfer?open_kuikly_info="
取UID动作名列表 = (
    "getUidFromUin",
    "get_uid_from_uin",
    "get_uid_by_uin",
    "get_uid",
    "_get_uid",
    "get_uin2uid",
    "getUin2Uid",
)


async def 处理授权链接(event: Any, 命令文本: str, 上下文: Any = None, 配置: Any = None) -> str | None:
    if str(命令文本 or "").strip() not in 授权命令:
        return None

    群号 = await 获取群号(event)
    if not 群号:
        return "授权链接生成失败：没有获取到数字QQ群号，请在目标群里发送“授权”"

    机器人QQ = await 获取机器人QQ(event, 上下文)
    if not 机器人QQ:
        return "授权链接生成失败：没有获取到机器人QQ号，当前适配器没有返回 botUin"

    机器人UID = await 获取机器人UID(event, 机器人QQ)
    if not 机器人UID:
        return f"授权链接生成失败：没有获取到机器人UID，当前适配器不支持 getUidFromUin({机器人QQ})"

    链接 = 生成授权链接(群号, 机器人QQ, 机器人UID)
    logger.info(f"授权链接已生成：groupCode={群号}, botUin={机器人QQ}, botUid={机器人UID}")
    return "\n".join([
        "授权链接：",
        链接,
        "",
        "请群主使用安卓/鸿蒙 QQ 9.2.90 及以上打开，iOS 暂不支持。",
    ])


def 生成授权链接(群号: str, 机器人QQ: str, 机器人UID: str) -> str:
    参数 = {
        "page_name": 页面名,
        "groupCode": int(群号),
        "botUin": int(机器人QQ),
        "botUid": str(机器人UID),
        "screen": 1,
    }
    参数文本 = json.dumps(参数, ensure_ascii=False, separators=(",", ":"))
    return 跳转地址 + urllib.parse.quote(参数文本, safe="")


async def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            群号 = 规范化数字(await 等待结果(方法()))
            if 群号:
                return 群号

    消息对象 = getattr(event, "message_obj", None)
    原始消息 = 读取字段(消息对象, "raw_message")
    for 对象 in (event, 消息对象, 原始消息):
        值 = 读取首个字段(对象, ("groupCode", "group_code", "group_id", "group", "group_uin"))
        群号 = 规范化数字(值)
        if 群号:
            return 群号
    return ""


async def 获取机器人QQ(event: Any, 上下文: Any = None) -> str:
    bot = getattr(event, "bot", None)
    接口返回QQ = await 从接口获取机器人QQ(bot)
    if 接口返回QQ:
        return 接口返回QQ

    消息对象 = getattr(event, "message_obj", None)
    原始消息 = 读取字段(消息对象, "raw_message")
    候选对象 = (event, 消息对象, 原始消息, bot, getattr(bot, "api", None), 上下文)
    for 对象 in 候选对象:
        值 = 读取首个字段(对象, ("self_id", "bot_id", "robot_id", "botUin", "bot_uin", "uin", "qq", "user_id"))
        机器人QQ = 规范化数字(值)
        if 机器人QQ:
            return 机器人QQ
    return ""


async def 从接口获取机器人QQ(bot: Any) -> str:
    响应 = await 调用机器人动作(bot, "get_login_info")
    return 提取首个数字(响应, ("user_id", "self_id", "bot_id", "robot_id", "uin", "qq"))


async def 获取机器人UID(event: Any, 机器人QQ: str) -> str:
    bot = getattr(event, "bot", None)
    本地UID = 提取本地机器人UID(event, bot)
    if 本地UID:
        return 本地UID

    for 动作名 in 取UID动作名列表:
        for 参数 in 构造UID参数候选(机器人QQ):
            响应 = await 调用机器人动作(bot, 动作名, **参数)
            机器人UID = 提取UID(响应)
            if 机器人UID:
                return 机器人UID
    return ""


def 提取本地机器人UID(event: Any, bot: Any) -> str:
    消息对象 = getattr(event, "message_obj", None)
    原始消息 = 读取字段(消息对象, "raw_message")
    for 对象 in (event, 消息对象, 原始消息, bot, getattr(bot, "api", None)):
        值 = 读取首个字段(对象, ("botUid", "bot_uid", "robot_uid", "self_uid"))
        UID = 规范化UID(值)
        if UID:
            return UID
    return ""


def 构造UID参数候选(机器人QQ: str) -> list[dict[str, Any]]:
    数字QQ = int(机器人QQ) if str(机器人QQ).isdigit() else 机器人QQ
    return [
        {"uin": 数字QQ},
        {"uin": str(机器人QQ)},
        {"user_id": 数字QQ},
        {"qq": 数字QQ},
        {"botUin": 数字QQ},
    ]


async def 调用机器人动作(bot: Any, 动作名: str, **参数: Any) -> Any:
    if bot is None:
        return None

    api = getattr(bot, "api", None)
    调用动作 = getattr(api, "call_action", None)
    if callable(调用动作):
        try:
            return await 调用动作(动作名, **参数)
        except Exception as exc:
            logger.debug(f"授权链接动作调用失败：action={动作名}, params={参数}, error={exc}")

    for 对象 in (bot, api):
        方法 = getattr(对象, 动作名, None)
        if not callable(方法):
            continue
        try:
            return await 等待结果(方法(**参数))
        except TypeError:
            try:
                首个参数 = next(iter(参数.values())) if 参数 else None
                调用结果 = 方法(首个参数) if 首个参数 is not None else 方法()
                return await 等待结果(调用结果)
            except Exception as exc:
                logger.debug(f"授权链接方法调用失败：method={动作名}, params={参数}, error={exc}")
        except Exception as exc:
            logger.debug(f"授权链接方法调用失败：method={动作名}, params={参数}, error={exc}")
    return None


async def 等待结果(值: Any) -> Any:
    if hasattr(值, "__await__"):
        return await 值
    return 值


def 提取UID(值: Any) -> str:
    if isinstance(值, str):
        return 规范化UID(值)
    if isinstance(值, dict):
        for 字段名 in ("botUid", "bot_uid", "uid", "user_uid", "uin_uid"):
            UID = 规范化UID(值.get(字段名))
            if UID:
                return UID
        for 字段名 in ("data", "result", "ret", "response"):
            UID = 提取UID(值.get(字段名))
            if UID:
                return UID
        for 子项 in 值.values():
            if isinstance(子项, (dict, list)):
                UID = 提取UID(子项)
                if UID:
                    return UID
    if isinstance(值, list):
        for 子项 in 值:
            UID = 提取UID(子项)
            if UID:
                return UID
    return ""


def 提取首个数字(值: Any, 字段列表: tuple[str, ...]) -> str:
    if isinstance(值, dict):
        for 字段名 in 字段列表:
            数字 = 规范化数字(值.get(字段名))
            if 数字:
                return 数字
        for 字段名 in ("data", "result", "ret", "response"):
            数字 = 提取首个数字(值.get(字段名), 字段列表)
            if 数字:
                return 数字
    return 规范化数字(值)


def 读取首个字段(对象: Any, 字段列表: tuple[str, ...]) -> Any:
    for 字段名 in 字段列表:
        值 = 读取字段(对象, 字段名)
        if 值 not in (None, ""):
            return 值
    return None


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 规范化数字(值: Any) -> str:
    if isinstance(值, dict):
        for 字段名 in ("group_id", "groupCode", "user_id", "self_id", "uin", "qq", "id"):
            结果 = 规范化数字(值.get(字段名))
            if 结果:
                return 结果
        return ""
    if 值 is None or callable(值):
        return ""
    文本 = str(值).strip()
    return 文本 if 文本.isdigit() else ""


def 规范化UID(值: Any) -> str:
    if 值 is None or callable(值):
        return ""
    文本 = str(值).strip()
    if not 文本 or 文本.isdigit():
        return ""
    return 文本 if 文本.startswith("u_") or len(文本) >= 8 else ""
