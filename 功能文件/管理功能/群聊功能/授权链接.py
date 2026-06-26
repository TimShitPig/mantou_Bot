from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from astrbot.api import logger
from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 是QQ官方机器人
from 功能文件.管理功能.基础功能.帮助功能 import (
    发送Markdown键盘消息,
    生成返回按钮,
)


授权命令 = {"授权"}
授权链接触发项名称 = "授权链接"
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
群号字段列表 = ("groupCode", "group_code", "group_id", "group", "group_uin")
机器人QQ字段列表 = ("self_id", "bot_id", "robot_id", "botUin", "bot_uin", "uin", "qq", "user_id")
机器人UID字段列表 = ("botUid", "bot_uid", "robot_uid", "self_uid")
授权诊断最大长度 = 8000


async def 处理授权链接(event: Any, 命令文本: str, 上下文: Any = None, 配置: Any = None) -> str | None:
    授权参数 = 提取授权命令参数(命令文本)
    if 授权参数 is None:
        return None

    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用授权链接"

    记录授权事件诊断(event)

    手动群号, 手动机器人QQ = 授权参数
    群号 = 手动群号 or await 获取群号(event)
    if not 群号:
        提示 = "授权链接生成失败：没有获取到数字QQ群号，请在目标群里发送\u201c授权\u201d"
        if 是QQ官方机器人(event):
            return await 发送授权MD消息(event, 提示)
        return 提示

    机器人QQ = 手动机器人QQ or await 获取机器人QQ(event, 上下文)
    if not 机器人QQ:
        提示 = "授权链接生成失败：没有获取到机器人QQ号，当前适配器没有返回 botUin"
        if 是QQ官方机器人(event):
            return await 发送授权MD消息(event, 提示)
        return 提示

    机器人UID = await 获取机器人UID(event, 机器人QQ)
    if not 机器人UID:
        提示 = f"授权链接生成失败：没有获取到机器人UID，当前适配器不支持 getUidFromUin({机器人QQ})"
        if 是QQ官方机器人(event):
            return await 发送授权MD消息(event, 提示)
        return 提示

    链接 = 生成授权链接(群号, 机器人QQ, 机器人UID)
    logger.info(f"授权链接已生成：groupCode={群号}, botUin={机器人QQ}, botUid={机器人UID}")
    纯文本 = "\n".join([
        "授权链接：",
        链接,
        "",
        "请群主使用安卓/鸿蒙 QQ 9.2.90 及以上打开，iOS 暂不支持。",
    ])
    if 是QQ官方机器人(event):
        md文本 = "\n".join([
            "## 🔗 授权群聊\n",
            f"**群号：** {群号}",
            f"**机器人QQ：** {机器人QQ}",
            "",
            "请群主使用安卓/鸿蒙 QQ 9.2.90 及以上点击下方按钮授权，iOS 暂不支持。",
        ])
        授权按钮 = 生成链接按钮("🌐 点击授权", 链接, "已打开授权页")
        返回按钮 = 生成返回按钮(自动发送=True)
        键盘 = {"rows": [{"buttons": [授权按钮]}, {"buttons": [返回按钮]}]}
        if await 发送Markdown键盘消息(event, md文本, 键盘):
            return ""
    return 纯文本


async def 发送授权MD消息(event: Any, 文本: str) -> str:
    """发送带返回按钮的MD消息，用于错误提示。"""
    md文本 = f"## 🔗 授权群聊\n\n{文本}"
    返回按钮 = 生成返回按钮(自动发送=True)
    键盘 = {"rows": [{"buttons": [返回按钮]}]}
    if await 发送Markdown键盘消息(event, md文本, 键盘):
        return ""
    return 文本


def 生成链接按钮(标签: str, 跳转链接: str, 点击后标签: str = "") -> dict[str, Any]:
    return {
        "id": f"link_{跳转链接}",
        "render_data": {"label": 标签, "visited_label": 点击后标签 or 标签},
        "action": {
            "type": 0,
            "permission": {"type": 2},
            "data": 跳转链接,
            "unsupport_tips": "请手动复制链接到浏览器打开",
        },
    }


def 提取授权命令参数(命令文本: str) -> tuple[str, str] | None:
    文本 = str(命令文本 or "").strip()
    if 文本 in 授权命令:
        return "", ""
    匹配 = re.fullmatch(r"授权\s+([1-9]\d{4,11})(?:\s+([1-9]\d{4,11}))?", 文本)
    if not 匹配:
        return None
    return 匹配.group(1), 匹配.group(2) or ""


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

    for 对象 in 获取事件候选对象(event):
        群号 = 提取数字字段(对象, 群号字段列表)
        if 群号:
            return 群号
    return ""


async def 获取机器人QQ(event: Any, 上下文: Any = None) -> str:
    bot = getattr(event, "bot", None)
    上下文机器人QQ = 提取数字字段(上下文, ("robot_id", "self_id", "bot_id", "botUin", "uin", "qq"))
    if 上下文机器人QQ:
        return 上下文机器人QQ

    接口返回QQ = await 从接口获取机器人QQ(bot)
    if 接口返回QQ:
        return 接口返回QQ

    候选对象 = (*获取事件候选对象(event), bot, getattr(bot, "api", None), 上下文)
    for 对象 in 候选对象:
        机器人QQ = 提取数字字段(对象, 机器人QQ字段列表)
        if 机器人QQ:
            return 机器人QQ
    return ""


async def 从接口获取机器人QQ(bot: Any) -> str:
    响应 = await 调用机器人动作(bot, "get_login_info")
    return 提取首个数字(响应, ("user_id", "self_id", "bot_id", "robot_id", "uin", "qq"))


async def 获取机器人UID(event: Any, 机器人QQ: str) -> str:
    bot = getattr(event, "bot", None)
    本地UID = 提取本地机器人UID(event, bot, 机器人QQ)
    if 本地UID:
        return 本地UID

    for 动作名 in 取UID动作名列表:
        for 参数 in 构造UID参数候选(机器人QQ):
            响应 = await 调用机器人动作(bot, 动作名, **参数)
            机器人UID = 提取UID(响应, 机器人QQ)
            if 机器人UID:
                return 机器人UID
            if 响应 not in (None, ""):
                logger.info(f"授权链接UID转换响应未识别：action={动作名}, params={参数}, response={诊断文本(响应, 2000)}")
    return ""


def 提取本地机器人UID(event: Any, bot: Any, 机器人QQ: str = "") -> str:
    for 对象 in (*获取事件候选对象(event), bot, getattr(bot, "api", None)):
        UID = 提取UID字段(对象, 机器人UID字段列表, 排除QQ=机器人QQ)
        if UID:
            return UID
    return ""


def 构造UID参数候选(机器人QQ: str) -> list[dict[str, Any]]:
    数字QQ = int(机器人QQ) if str(机器人QQ).isdigit() else 机器人QQ
    return [
        {"uin": 数字QQ},
        {"uin": str(机器人QQ)},
        {"uins": [数字QQ]},
        {"uin_list": [数字QQ]},
        {"user_id": 数字QQ},
        {"user_id": str(机器人QQ)},
        {"qq": 数字QQ},
        {"qq": str(机器人QQ)},
        {"botUin": 数字QQ},
        {"botUin": str(机器人QQ)},
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


def 提取UID(值: Any, 排除QQ: str = "") -> str:
    if isinstance(值, str):
        return 规范化UID(值, 排除QQ)
    if isinstance(值, dict):
        for 字段名 in ("botUid", "bot_uid", "uid", "user_uid", "uin_uid"):
            UID = 规范化UID(值.get(字段名), 排除QQ)
            if UID:
                return UID
        for 字段名 in ("data", "result", "ret", "response"):
            UID = 提取UID(值.get(字段名), 排除QQ)
            if UID:
                return UID
        for 子项 in 值.values():
            UID = 提取UID(子项, 排除QQ)
            if UID:
                return UID
    if isinstance(值, list):
        for 子项 in 值:
            UID = 提取UID(子项, 排除QQ)
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


def 提取数字字段(值: Any, 字段列表: tuple[str, ...], 已见: set[int] | None = None) -> str:
    if 已见 is None:
        已见 = set()
    if 值 is None or callable(值):
        return ""
    对象编号 = id(值)
    if 对象编号 in 已见:
        return ""
    已见.add(对象编号)

    if isinstance(值, dict):
        for 字段名 in 字段列表:
            数字 = 规范化数字(值.get(字段名))
            if 数字:
                return 数字
        for 子项 in 值.values():
            数字 = 提取数字字段(子项, 字段列表, 已见)
            if 数字:
                return 数字
        return ""

    if isinstance(值, (list, tuple, set)):
        for 子项 in 值:
            数字 = 提取数字字段(子项, 字段列表, 已见)
            if 数字:
                return 数字
        return ""

    if isinstance(值, str):
        for 文本 in 生成文本变体(值):
            JSON对象 = 解析JSON对象(文本)
            if JSON对象 is not None:
                数字 = 提取数字字段(JSON对象, 字段列表, 已见)
                if 数字:
                    return 数字
        return ""

    for 字段名 in 字段列表:
        数字 = 规范化数字(读取字段(值, 字段名))
        if 数字:
            return 数字

    if hasattr(值, "__dict__"):
        return 提取数字字段(vars(值), 字段列表, 已见)
    return ""


def 提取UID字段(值: Any, 字段列表: tuple[str, ...], 已见: set[int] | None = None, 排除QQ: str = "") -> str:
    if 已见 is None:
        已见 = set()
    if 值 is None or callable(值):
        return ""
    对象编号 = id(值)
    if 对象编号 in 已见:
        return ""
    已见.add(对象编号)

    if isinstance(值, dict):
        for 字段名 in 字段列表:
            UID = 规范化UID(值.get(字段名), 排除QQ)
            if UID:
                return UID
        for 子项 in 值.values():
            UID = 提取UID字段(子项, 字段列表, 已见, 排除QQ)
            if UID:
                return UID
        return ""

    if isinstance(值, (list, tuple, set)):
        for 子项 in 值:
            UID = 提取UID字段(子项, 字段列表, 已见, 排除QQ)
            if UID:
                return UID
        return ""

    if isinstance(值, str):
        for 文本 in 生成文本变体(值):
            JSON对象 = 解析JSON对象(文本)
            if JSON对象 is not None:
                UID = 提取UID字段(JSON对象, 字段列表, 已见, 排除QQ)
                if UID:
                    return UID
        return ""

    for 字段名 in 字段列表:
        UID = 规范化UID(读取字段(值, 字段名), 排除QQ)
        if UID:
            return UID

    if hasattr(值, "__dict__"):
        return 提取UID字段(vars(值), 字段列表, 已见, 排除QQ)
    return ""


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 获取事件候选对象(event: Any) -> tuple[Any, ...]:
    消息对象 = getattr(event, "message_obj", None)
    return (
        event,
        消息对象,
        读取字段(event, "message_str"),
        读取字段(event, "raw_message"),
        读取字段(event, "message"),
        读取字段(消息对象, "message_str"),
        读取字段(消息对象, "raw_message"),
        读取字段(消息对象, "message"),
    )


def 生成文本变体(文本: str) -> list[str]:
    原文 = str(文本 or "").replace("\\/", "/")
    变体列表 = [原文]
    for _ in range(3):
        解码文本 = urllib.parse.unquote(变体列表[-1])
        if 解码文本 == 变体列表[-1]:
            break
        变体列表.append(解码文本)
    return 变体列表


def 解析JSON对象(文本: str) -> Any:
    文本 = str(文本 or "").strip()
    if not 文本:
        return None
    解码器 = json.JSONDecoder()
    起点列表 = [0] if 文本.startswith(("{", "[")) else []
    起点列表.extend(位置 for 位置, 字符 in enumerate(文本) if 字符 in "{[")
    for 起点 in dict.fromkeys(起点列表):
        try:
            对象, _ = 解码器.raw_decode(文本[起点:])
            return 对象
        except Exception:
            continue
    return None


def 记录授权事件诊断(event: Any) -> None:
    try:
        诊断数据 = {
            "event_type": type(event).__name__,
            "event": 诊断序列化对象(event),
            "message_obj": 诊断序列化对象(getattr(event, "message_obj", None)),
        }
        文本 = json.dumps(诊断数据, ensure_ascii=False, default=str)
        logger.info(f"授权链接事件诊断：{限制文本长度(文本, 授权诊断最大长度)}")
    except Exception as exc:
        logger.warning(f"授权链接事件诊断失败：error={exc}")


def 诊断文本(值: Any, 最大长度: int = 2000) -> str:
    try:
        文本 = json.dumps(诊断序列化对象(值), ensure_ascii=False, default=str)
    except Exception:
        文本 = str(值)
    return 限制文本长度(文本, 最大长度)


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
    if len(文本) > 最大长度:
        return 文本[:最大长度] + "..."
    return 文本


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


def 规范化UID(值: Any, 排除QQ: str = "") -> str:
    if 值 is None or callable(值):
        return ""
    文本 = str(值).strip()
    if not 文本:
        return ""
    if 排除QQ and 文本 == str(排除QQ):
        return ""
    return 文本 if 文本.startswith("u_") or len(文本) >= 8 else ""
