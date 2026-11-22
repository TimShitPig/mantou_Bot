from __future__ import annotations

import html
import json
import re
from collections import deque
from itertools import islice
from typing import Any
from urllib.parse import unquote, urlsplit


本地系统消息来源 = ("group_member_join", "group_member_leave", "group_members_removed", "friend_add", "friend_del")
本地系统消息编号前缀 = ("group-event:", "friend-event:")


def 是本地系统消息(消息编号: Any, 来源: Any = "") -> bool:
    """入群/退群及好友通知仅用于本地展示，没有可撤回的官方消息 ID。"""
    return (str(来源 or "").strip() in 本地系统消息来源
            or str(消息编号 or "").strip().startswith(本地系统消息编号前缀))


def 获取命令文本(event: Any) -> str:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            文本 = 转成命令文本(读取字段(对象, 字段名))
            if 文本:
                return 文本
    return ""


def 读取字段(对象: Any, 字段名: str) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 转成命令文本(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, str):
        return 清理命令文本(值)
    if isinstance(值, list):
        return 清理命令文本("".join(转消息段文本(消息段) for 消息段 in 值))
    if isinstance(值, dict):
        return 清理命令文本(转消息段文本(值))
    return ""


def 转消息段文本(消息段: Any) -> str:
    if not isinstance(消息段, dict) or 消息段.get("type") != "text":
        return ""
    数据 = 消息段.get("data")
    if isinstance(数据, dict):
        return str(数据.get("text") or "")
    return ""


def 清理命令文本(文本: str) -> str:
    文本 = str(文本 or "")
    文本 = re.sub(r"\[At:[^\]]+\]", "", 文本)
    文本 = re.sub(r"<@!?[A-Za-z0-9_-]{5,64}>", "", 文本)
    return 文本.strip()



_书耽链接候选 = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_书耽详情路径 = re.compile(r"/book/book_detail/([1-9][0-9]{0,19})/?")
_跳过卡片分支 = {
    "author", "sender", "user", "member", "mentions", "reply", "quote",
    "quoted", "quotedmessage", "reference", "messagereference", "msgelements",
    "message", "rawmessage", "forward", "node", "nodes", "ref",
}


def 提取书耽详情书号(event: Any, 命令文本: Any = "") -> str:
    """只读当前消息的文本和分享卡片，返回书耽详情页的书号。"""
    待检查 = deque([(命令文本, 0, "text"), (event, 0, "message")])
    已检查 = set()
    while 待检查 and len(已检查) < 256:
        值, 深度, 类型 = 待检查.popleft()
        if 值 is None or 深度 > 10 or (id(值), 类型) in 已检查:
            continue
        已检查.add((id(值), 类型))
        if isinstance(值, str):
            if not 值 or len(值) > 65536:
                continue
            if 类型 != "text" and 值.lstrip().startswith(("{", "[")):
                try:
                    结构 = json.loads(值)
                except (ValueError, RecursionError):
                    continue
                待检查.append((结构, 深度 + 1, 类型))
                continue
            文本 = 值
            for _ in range(3):
                文本 = html.unescape(文本).replace("\\/", "/")
                for 匹配 in _书耽链接候选.finditer(文本):
                    链接 = 匹配.group().rstrip("，。；！？、;）)]}\x60")
                    try:
                        地址 = urlsplit(链接)
                    except ValueError:
                        continue
                    if 地址.netloc.lower() not in {"www.shubl.com", "shubl.com"}:
                        continue
                    路径 = _书耽详情路径.fullmatch(地址.path)
                    if 路径:
                        return 路径[1]
                解码 = unquote(文本)
                if 解码 == 文本:
                    break
                文本 = 解码
            continue
        if isinstance(值, (list, tuple)):
            待检查.extend((项, 深度 + 1, 类型) for 项 in 值[:128])
            continue
        if 类型 == "card" and isinstance(值, dict):
            待检查.extend(
                (项, 深度 + 1, "card") for 键, 项 in islice(值.items(), 128)
                if str(键).lower().replace("_", "").replace("-", "") not in _跳过卡片分支
                and isinstance(项, (str, dict, list))
            )
            continue
        段类型 = 读取字段(值, "type")
        段类型 = str(getattr(段类型, "value", 段类型) or "").lower().removeprefix("componenttype.")
        if 段类型 in {"reply", "at", "atall", "forward", "node", "nodes"}:
            continue
        if 段类型 in {"ark", "json", "share"} or 类型 == "card":
            模式字段 = (("data", "card"), ("url", "text"), ("kv", "card"), ("obj", "card"), ("obj_kv", "card"), ("value", "text"))
        elif 段类型 in {"plain", "text"}:
            模式字段 = (("text", "text"), ("data", "message"))
        else:
            模式字段 = (("message_str", "text"), ("content", "text"), ("text", "text"),
                         ("message_obj", "message"), ("message", "message"), ("raw_message", "message"),
                         ("ark", "card"))
        待检查.extend((读取字段(值, 字段), 深度 + 1, 模式) for 字段, 模式 in 模式字段)
    return ""
