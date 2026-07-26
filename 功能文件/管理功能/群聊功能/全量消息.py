from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger
from 功能文件.管理功能.基础功能.帮助功能 import 发送Markdown键盘消息, 生成返回按钮
from 功能文件.管理功能.基础功能.权限工具 import 是QQ官方机器人, 是群文件清理管理员, 读取字段


全量消息状态命令 = {"全量消息", "全量消息状态", "查看全量消息", "群消息状态"}
群OpenID字段 = ("group_openid", "groupOpenid")
成员OpenID字段 = ("member_openid", "user_openid", "openid", "id")
OpenID规则 = re.compile(r"^[A-Za-z0-9_-]{5,128}$")


async def 处理全量消息(event: Any, 命令文本: str, 上下文: Any = None, 配置: Any = None) -> str | None:
    if str(命令文本 or "").strip() not in 全量消息状态命令:
        return None
    if not 是群文件清理管理员(event, 配置):
        return None

    群OpenID = await 获取群OpenID(event)
    状态 = await 查询官方群机器人状态(event, 群OpenID)
    return await 发送全量消息状态(event, 状态)


async def 查询官方群机器人状态(event: Any, 群OpenID: str) -> dict[str, Any]:
    """按 QQ 官方群机器人状态接口查询当前群的消息接收设置。"""
    if not 群OpenID:
        logger.info("全量消息状态查询跳过：当前事件没有 group_openid")
        return 状态不可查询()

    bot = getattr(event, "bot", None)
    api = getattr(bot, "api", None) if bot else None
    HTTP客户端 = getattr(api, "_http", None) if api else None
    if HTTP客户端 is None:
        logger.info("全量消息状态查询跳过：当前事件没有 QQ 官方 HTTP 客户端")
        return 状态不可查询()

    try:
        from botpy.http import Route

        路由 = Route("GET", "/v2/groups/{group_openid}/bot_state", group_openid=群OpenID)
        响应 = await HTTP客户端.request(路由)
        状态 = 解析官方群机器人状态(响应)
        logger.info(
            "全量消息状态查询成功："
            f"group_openid={群OpenID}, recv_msg_setting={状态['recv_msg_setting']}, "
            f"allow_proactive_msg={状态['allow_proactive_msg']}"
        )
        return 状态
    except Exception as 异常:
        logger.warning(
            f"全量消息状态查询失败：group_openid={群OpenID}, "
            f"error={type(异常).__name__}: {异常}"
        )
        return 状态不可查询()


def 解析官方群机器人状态(响应: Any) -> dict[str, Any]:
    数据 = 响应.get("data") if isinstance(响应, dict) and isinstance(响应.get("data"), dict) else 响应
    if not isinstance(数据, dict):
        return 状态不可查询()

    接收模式 = str(数据.get("recv_msg_setting") or "").strip().lower()
    if 接收模式 not in {"all", "only_mention", "mention_and_context"}:
        return 状态不可查询()

    主动发言 = bool(数据.get("allow_proactive_msg"))
    return {
        "可查询": True,
        "recv_msg_setting": 接收模式,
        "allow_proactive_msg": 主动发言,
        "全量消息": "已开启" if 接收模式 == "all" else "未开启",
        "主动发言": "已开启" if 主动发言 else "未开启",
    }


def 状态不可查询() -> dict[str, Any]:
    return {
        "可查询": False,
        "recv_msg_setting": "",
        "allow_proactive_msg": False,
        "全量消息": "状态暂不可查询",
        "主动发言": "状态暂不可查询",
    }


def 格式化官方群机器人状态(状态: dict[str, Any]) -> str:
    行 = [
        f"群内全部消息：{状态.get('全量消息') or '状态暂不可查询'}",
        f"机器人主动在群聊内发言：{状态.get('主动发言') or '状态暂不可查询'}",
    ]
    接收模式 = str(状态.get("recv_msg_setting") or "")
    模式说明 = {
        "all": "当前范围：群内全部消息",
        "only_mention": "当前范围：仅 @机器人",
        "mention_and_context": "当前范围：@机器人和上下文",
    }.get(接收模式)
    if 模式说明:
        行.append(模式说明)
    return "\n".join(行)


async def 发送全量消息状态(event: Any, 状态: dict[str, Any]) -> str:
    状态文本 = 格式化官方群机器人状态(状态)
    if not 是QQ官方机器人(event):
        return 状态文本

    提及 = 生成QQ官方MD提及(获取成员OpenID(event))
    md行 = [提及] if 提及 else []
    md行.extend(["## 群消息设置", "", 状态文本])
    if not 状态.get("可查询"):
        md行.extend(["", "官方群状态接口暂不可用，请在机器人资料页查看群消息设置。"])
    键盘 = {"rows": [{"buttons": [生成返回按钮(自动发送=True)]}]}
    if await 发送Markdown键盘消息(event, "\n".join(md行), 键盘):
        return ""
    return 状态文本


def 生成QQ官方MD提及(成员OpenID: Any) -> str:
    OpenID = str(成员OpenID or "").strip()
    return f"<@{OpenID}>" if OpenID规则.fullmatch(OpenID) else ""


async def 获取群OpenID(event: Any) -> str:
    for 对象 in (getattr(event, "message_obj", None), event):
        OpenID = 提取OpenID字段(对象, 群OpenID字段)
        if OpenID:
            return OpenID
    for 方法名 in ("get_group_openid", "get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if not callable(方法):
            continue
        try:
            值 = 方法()
            if hasattr(值, "__await__"):
                值 = await 值
            OpenID = str(值 or "").strip()
            if OpenID and not OpenID.isdigit():
                return OpenID
        except Exception:
            continue
    return ""


def 获取成员OpenID(event: Any) -> str:
    for 对象 in (getattr(event, "message_obj", None), event):
        发送者 = 读取字段(对象, "author") or 读取字段(对象, "sender")
        OpenID = 提取OpenID字段(发送者, 成员OpenID字段)
        if OpenID:
            return OpenID
        OpenID = 提取OpenID字段(对象, 成员OpenID字段)
        if OpenID:
            return OpenID
    return ""


def 提取OpenID字段(对象: Any, 字段列表: tuple[str, ...]) -> str:
    if isinstance(对象, dict):
        for 字段 in 字段列表:
            值 = str(对象.get(字段) or "").strip()
            if 值:
                return 值
    elif 对象 is not None:
        for 字段 in 字段列表:
            值 = str(读取字段(对象, 字段) or "").strip()
            if 值:
                return 值
    return ""
