from __future__ import annotations

import asyncio
import base64
import json
import random
import re
import time
from pathlib import Path
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

消息记录版本 = 1
最大会话数 = 200
每会话最大消息数 = 500
总消息上限 = 10000
缓存目录名 = "下载缓存"
备注缓存文件名 = "消息记录缓存.json"

当前插件上下文: Any = globals().get("当前插件上下文")
消息缓存: dict[str, dict[str, Any]] = globals().get("消息缓存") or {}
群信息缓存: dict[str, dict[str, Any]] = globals().get("群信息缓存") or {}
群信息待刷新: set[str] = globals().get("群信息待刷新") or set()
成员资料缓存: dict[str, dict[str, dict[str, Any]]] = globals().get("成员资料缓存") or {}
发送序号 = globals().get("发送序号") or 0
_挂钩已安装 = globals().get("_挂钩已安装", False)

_OPENID规则 = re.compile(r"^[A-Za-z0-9_-]{5,128}$")
_媒体占位规则 = re.compile(r"\[(图片|语音|视频|文件|媒体|media)]([^\s]+)")
_QQ图片域名 = re.compile(
    r"(?:https?://)?[^>\s]*(?:multimedia\.nt\.qq\.com\.cn|qqbot\.ugcimg\.cn|gchat\.qpic\.cn)[^>\s]*"
)


def _读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名, 默认值)
    return getattr(对象, 字段名, 默认值)


def _转数字时间戳(时间戳: Any) -> int | None:
    """把数字秒、ISO 字符串或 datetime 统一转成秒级数字时间戳。"""
    if 时间戳 is None or 时间戳 == "":
        return None
    if isinstance(时间戳, (int, float)):
        try:
            数值 = int(时间戳)
        except (TypeError, ValueError, OverflowError):
            return None
        if 数值 <= 0:
            return None
        if 数值 > 10**12:
            数值 //= 1000
        return 数值
    if hasattr(时间戳, "timestamp"):
        try:
            return int(时间戳.timestamp())
        except Exception:
            return None
    文本 = str(时间戳).strip()
    if not 文本:
        return None
    try:
        from datetime import datetime as _日期类

        if len(文本) >= 19 and 文本[4] == "-" and 文本[10] == "T":
            核心 = 文本[:19]
            解析 = _日期类.strptime(核心, "%Y-%m-%dT%H:%M:%S")
            return int(解析.timestamp())
    except (ValueError, TypeError):
        pass
    try:
        数值 = int(float(文本))
        if 数值 > 0:
            return 数值
    except (TypeError, ValueError):
        pass
    return None


def _格式化时间戳(时间戳: Any) -> str:
    数值 = _转数字时间戳(时间戳)
    if 数值 is None:
        return ""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(数值))
    except (ValueError, OverflowError, OSError):
        return ""


def _规范会话标识(会话: str, 类型: str) -> str:
    """会话统一使用 openid 作为会话标识。"""
    return str(会话 or "").strip()


def _取得会话缓存(会话标识: str, 类型: str, appid: str = "") -> dict[str, Any]:
    会话标识 = _规范会话标识(会话标识, 类型)
    if 会话标识 not in 消息缓存:
        if len(消息缓存) >= 最大会话数:
            # 淘汰最久未活跃的会话
            try:
                最旧会话 = min(
                    消息缓存,
                    key=lambda k: (
                        消息缓存[k].get("last_ts") or 0,
                        k,
                    ),
                )
                消息缓存.pop(最旧会话, None)
            except Exception:
                pass
        消息缓存[会话标识] = {
            "chat_type": 类型,
            "appid": str(appid or ""),
            "messages": [],
            "last_ts": 0,
            "last_content": "",
            "last_nickname": "",
        }
    return 消息缓存[会话标识]


def _序列化原始消息(消息: Any) -> str:
    try:
        return str(消息 or "")
    except Exception:
        return ""


def _提取消息文本(内容: Any) -> str:
    return str(内容 or "").strip()


def _提取媒体字段(内容: str) -> dict[str, str] | None:
    """从消息原文提取媒体占位或 QQ 富媒体图片链接。"""
    if not 内容:
        return None
    匹配 = _媒体占位规则.search(内容)
    if 匹配:
        类型 = 匹配.group(1)
        地址 = 匹配.group(2)
        文本 = 内容.replace(匹配.group(0), "").strip()
        return {"type": 类型, "src": 地址, "text": 文本}
    匹配 = _QQ图片域名.search(内容)
    if 匹配:
        地址 = 匹配.group(0).strip("<>")
        文本 = 内容.replace(匹配.group(0), "").strip()
        return {"type": "图片", "src": 地址, "text": 文本}
    return None


def _提取成员标识(消息: Any, 类型: str) -> str:
    """从 QQ 官方消息对象提取成员 openid。"""
    作者 = _读取字段(消息, "author")
    if 类型 == "user":
        标识 = _读取字段(作者, "user_openid") or _读取字段(作者, "id")
    else:
        标识 = _读取字段(作者, "member_openid") or _读取字段(作者, "id")
    return str(标识 or "").strip()


def _提取成员昵称(消息: Any) -> str:
    作者 = _读取字段(消息, "author")
    return str(_读取字段(作者, "username") or "").strip()


def _记录成员资料(
    会话标识: str,
    成员标识: str,
    昵称: str,
    是机器人: bool = False,
    角色: str = "",
) -> None:
    if not 成员标识:
        return
    会话资料 = 成员资料缓存.setdefault(会话标识, {})
    if 成员标识 not in 会话资料:
        会话资料[成员标识] = {"nickname": 昵称 or "", "is_bot": bool(是机器人), "role": str(角色 or "")}
    else:
        if 昵称:
            会话资料[成员标识]["nickname"] = 昵称
        会话资料[成员标识]["is_bot"] = bool(是机器人)
        if 角色:
            会话资料[成员标识]["role"] = str(角色 or "")


def 记录收到消息(
    消息: Any,
    类型: str,
    appid: str = "",
    *,
    is_self: bool = False,
    源: str = "qq_official",
) -> dict[str, Any] | None:
    """把一条 QQ 官方消息写入进程内缓存。"""
    global 发送序号
    try:
        会话标识 = ""
        消息ID = str(_读取字段(消息, "id") or "").strip()
        内容 = _提取消息文本(_读取字段(消息, "content"))
        if 类型 == "user":
            会话标识 = _提取成员标识(消息, "user")
            成员标识 = 会话标识
        else:
            会话标识 = str(_读取字段(消息, "group_openid") or "").strip()
            成员标识 = _提取成员标识(消息, "group")
        if not 会话标识:
            return None
        昵称 = _提取成员昵称(消息)
        作者 = _读取字段(消息, "author")
        是机器人 = bool(_读取字段(作者, "bot") or False)
        角色 = str(_读取字段(作者, "member_role") or "").strip()
        时间戳 = _读取字段(消息, "timestamp") or int(time.time())
        引用ID = ""
        消息引用 = _读取字段(消息, "message_reference")
        if 消息引用:
            引用ID = str(_读取字段(消息引用, "message_id") or "").strip()
        _记录成员资料(会话标识, 成员标识, 昵称, 是机器人, 角色)
        会话 = _取得会话缓存(会话标识, 类型, appid)
        if 类型 == "group" and 会话标识 not in 群信息缓存:
            标记群信息待刷新(会话标识)
        发送序号 += 1
        记录: dict[str, Any] = {
            "id": 发送序号,
            "message_id": 消息ID,
            "user_id": 成员标识,
            "appid": str(appid or 会话.get("appid") or ""),
            "nickname": 昵称 or "未知用户",
            "content": 内容,
            "timestamp": _格式化时间戳(时间戳),
            "is_self": bool(is_self),
            "source": 源,
            "raw_message": _序列化原始消息(_读取字段(消息, "raw_data") or 消息),
            "recalled": False,
            "media": _提取媒体字段(内容),
            "reference_id": 引用ID or "",
        }
        会话["messages"].append(记录)
        if len(会话["messages"]) > 每会话最大消息数:
            会话["messages"] = 会话["messages"][-每会话最大消息数:]
        if 内容:
            会话["last_content"] = 内容
            会话["last_nickname"] = 昵称
        会话["last_ts"] = _转数字时间戳(时间戳) or int(time.time())
        _裁剪总缓存()
        return 记录
    except Exception as exc:
        logger.warning("消息记录缓存写入失败：错误类型=%s", type(exc).__name__)
        return None


def _裁剪总缓存() -> None:
    总数 = sum(len(会话.get("messages", [])) for 会话 in 消息缓存.values())
    if 总数 <= 总消息上限:
        return
    try:
        会话列表 = sorted(
            消息缓存.values(),
            key=lambda s: (s.get("last_ts") or 0, s.get("appid") or ""),
        )
        for 会话 in 会话列表:
            if 总数 <= 总消息上限:
                break
            会话["messages"] = 会话["messages"][-(每会话最大消息数 // 2):]
            总数 = sum(len(s.get("messages", [])) for s in 消息缓存.values())
    except Exception:
        pass


def 记录发送消息(
    会话标识: str,
    类型: str,
    内容: str,
    appid: str = "",
    *,
    消息ID: str = "",
    引用ID: str = "",
) -> dict[str, Any] | None:
    """把网页发送成功的消息写入缓存，标记为机器人自己发送。"""
    global 发送序号
    try:
        会话 = _取得会话缓存(会话标识, 类型, appid)
        发送序号 += 1
        记录: dict[str, Any] = {
            "id": 发送序号,
            "message_id": 消息ID,
            "user_id": "",
            "appid": str(appid or ""),
            "nickname": "我",
            "content": 内容,
            "timestamp": _格式化时间戳(int(time.time())),
            "is_self": True,
            "source": "web_panel",
            "raw_message": "",
            "recalled": False,
            "media": _提取媒体字段(内容),
            "reference_id": 引用ID or "",
        }
        会话["messages"].append(记录)
        if len(会话["messages"]) > 每会话最大消息数:
            会话["messages"] = 会话["messages"][-每会话最大消息数:]
        if 内容:
            会话["last_content"] = 内容
            会话["last_nickname"] = "我"
        会话["last_ts"] = int(time.time())
        _裁剪总缓存()
        return 记录
    except Exception as exc:
        logger.warning("消息记录发送缓存写入失败：错误类型=%s", type(exc).__name__)
        return None


def 标记撤回(会话标识: str, 消息ID: str) -> bool:
    会话 = 消息缓存.get(str(会话标识 or "").strip())
    if not 会话:
        return False
    for 记录 in 会话.get("messages", []):
        if 记录.get("message_id") == 消息ID:
            记录["recalled"] = True
            return True
    return False


def _读取平台实例列表(上下文: Any) -> list[Any]:
    平台管理器 = _读取字段(上下文, "platform_manager") if 上下文 is not None else None
    平台列表 = _读取字段(平台管理器, "platform_insts", None)
    if isinstance(平台列表, (list, tuple)):
        return list(平台列表)
    获取实例 = getattr(平台管理器, "get_insts", None)
    if not callable(获取实例):
        return []
    try:
        平台列表 = 获取实例()
    except Exception:
        return []
    return list(平台列表) if isinstance(平台列表, (list, tuple)) else []


def _是QQ官方平台(平台实例: Any) -> bool:
    try:
        元信息 = 平台实例.meta()
        名称 = str(_读取字段(元信息, "name") or "").strip().casefold()
        标识 = str(_读取字段(元信息, "id") or "").strip().casefold()
        配置 = _读取字段(平台实例, "config")
        类型 = str(_读取字段(配置, "type") or "").strip().casefold()
        return (
            名称 == "qq_official"
            or 标识 == "qq_official"
            or 类型 == "qq_official"
            or "qq 机器人官方" in 名称
        )
    except Exception:
        return False


def 获取QQ官方平台(上下文: Any = None) -> Any | None:
    上下文 = 上下文 if 上下文 is not None else 当前插件上下文
    for 平台实例 in _读取平台实例列表(上下文):
        try:
            if _是QQ官方平台(平台实例):
                return 平台实例
        except Exception:
            continue
    return None


def 获取HTTP通道(平台实例: Any = None) -> tuple[Any, Any] | None:
    """返回 (bot_api, http)，用于直接调用 QQ 官方 REST 接口。"""
    平台实例 = 平台实例 or 获取QQ官方平台()
    if 平台实例 is None:
        return None
    客户端 = _读取字段(平台实例, "client")
    api = _读取字段(客户端, "api")
    _http = _读取字段(api, "_http")
    if _http is None:
        return None
    return api, _http


def 获取最近消息ID(平台实例: Any, 会话标识: str) -> str:
    if 平台实例 is None:
        return ""
    缓存 = _读取字段(平台实例, "_session_last_message_id", {})
    if not isinstance(缓存, dict):
        return ""
    return str(缓存.get(会话标识) or "").strip()


def 获取会话场景(平台实例: Any, 会话标识: str) -> str:
    if 平台实例 is None:
        return ""
    缓存 = _读取字段(平台实例, "_session_scene", {})
    if not isinstance(缓存, dict):
        return ""
    return str(缓存.get(会话标识) or "").strip()


# ---------------------------------------------------------------------------
# 群信息与备注
# ---------------------------------------------------------------------------

def 获取群备注(会话标识: str) -> str:
    数据 = _读取本地缓存文件()
    return str((数据.get("remarks") or {}).get(会话标识, {}).get("remark") or "")


def 获取群QQ号(会话标识: str) -> str:
    数据 = _读取本地缓存文件()
    return str((数据.get("remarks") or {}).get(会话标识, {}).get("group_qq") or "")


def 保存群备注(会话标识: str, 备注: str = "", 群QQ: str = "") -> None:
    数据 = _读取本地缓存文件()
    备注表 = 数据.setdefault("remarks", {})
    现有 = 备注表.setdefault(会话标识, {})
    if 备注:
        现有["remark"] = 备注
    else:
        现有.pop("remark", None)
    if 群QQ:
        现有["group_qq"] = 群QQ
    elif 群QQ == "":
        现有.pop("group_qq", None)
    备注表[会话标识] = 现有
    _写入本地缓存文件(数据)


def _缓存文件路径() -> Path:
    try:
        模块目录 = Path(__file__).resolve().parent
        return 模块目录.parent.parent / 缓存目录名 / 备注缓存文件名
    except Exception:
        return Path(".") / 备注缓存文件名


def _读取本地缓存文件() -> dict[str, Any]:
    try:
        路径 = _缓存文件路径()
        if 路径.exists():
            with open(路径, "r", encoding="utf-8") as f:
                数据 = json.load(f)
            if isinstance(数据, dict):
                return 数据
    except Exception as exc:
        logger.warning("消息记录本地缓存读取失败：错误类型=%s", type(exc).__name__)
    return {}


def _写入本地缓存文件(数据: dict[str, Any]) -> None:
    try:
        路径 = _缓存文件路径()
        路径.parent.mkdir(parents=True, exist_ok=True)
        临时 = 路径.with_suffix(".tmp")
        with open(临时, "w", encoding="utf-8") as f:
            json.dump(数据, f, ensure_ascii=False, indent=1)
        临时.replace(路径)
    except Exception as exc:
        logger.warning("消息记录本地缓存写入失败：错误类型=%s", type(exc).__name__)


def 标记群信息待刷新(会话标识: str) -> None:
    会话标识 = str(会话标识 or "").strip()
    if 会话标识:
        群信息待刷新.add(会话标识)


async def 刷新待处理群信息() -> int:
    """批量刷新待处理群信息，返回成功数量。"""
    if not 群信息待刷新:
        return 0
    批次 = list(群信息待刷新)[:20]
    群信息待刷新.clear()
    成功数 = 0
    for 会话标识 in 批次:
        try:
            结果 = await 刷新群信息(会话标识)
            if 结果:
                成功数 += 1
        except Exception as exc:
            logger.warning("消息记录群信息后台刷新失败：错误类型=%s", type(exc).__name__)
    return 成功数


async def 刷新群信息(会话标识: str, appid: str = "") -> dict[str, Any] | None:
    """调用 QQ 官方接口刷新群基本信息。"""
    通道 = 获取HTTP通道()
    if 通道 is None:
        return None
    _, _http = 通道
    try:
        from botpy.http import Route

        route = Route(
            "GET",
            "/v2/groups/{group_openid}/info",
            group_openid=会话标识,
        )
        结果 = await _http.request(route)
        if not isinstance(结果, dict):
            return None
        摘要 = {
            "group_openid": str(结果.get("group_openid") or 会话标识),
            "group_name": str(结果.get("group_name") or ""),
            "member_num": int(结果.get("group_member_num") or 0),
            "updated_at": int(time.time()),
        }
        群信息缓存[会话标识] = 摘要
        return 摘要
    except Exception as exc:
        logger.warning("消息记录群信息刷新失败：错误类型=%s", type(exc).__name__)
        return None


def 获取缓存的群信息(会话标识: str) -> dict[str, Any]:
    信息 = 群信息缓存.get(会话标识) or {}
    会话 = 消息缓存.get(会话标识) or {}
    返回 = dict(信息)
    返回.setdefault("group_openid", 会话标识)
    返回.setdefault("group_name", 获取群备注(会话标识) or "")
    返回.setdefault("member_num", 0)
    return 返回


# ---------------------------------------------------------------------------
# 聊天列表与历史
# ---------------------------------------------------------------------------

def _聊天显示名(会话标识: str, 会话: dict[str, Any]) -> str:
    备注 = 获取群备注(会话标识)
    if 备注:
        return 备注
    信息 = 群信息缓存.get(会话标识) or {}
    群名 = str(信息.get("group_name") or "")
    if 群名:
        return 群名
    最近昵称 = str(会话.get("last_nickname") or "")
    return 最近昵称 or 会话标识


def 获取聊天列表(
    过滤: str = "all",
    搜索: str = "",
    页码: int = 1,
    每页: int = 50,
) -> dict[str, Any]:
    过滤 = str(过滤 or "all").strip()
    搜索 = str(搜索 or "").strip()
    try:
        页码 = max(1, int(页码))
        每页 = max(1, min(100, int(每页)))
    except (TypeError, ValueError):
        页码, 每页 = 1, 50
    聊天列表: list[dict[str, Any]] = []
    for 会话标识, 会话 in 消息缓存.items():
        类型 = str(会话.get("chat_type") or "group")
        if 过滤 == "group" and 类型 != "group":
            continue
        if 过滤 == "user" and 类型 != "user":
            continue
        if 过滤 == "remark":
            备注 = 获取群备注(会话标识)
            if not 备注:
                continue
        if 类型 == "group" and not 群信息缓存.get(会话标识):
            标记群信息待刷新(会话标识)
        显示名 = _聊天显示名(会话标识, 会话)
        if 搜索 and 搜索 not in 显示名 and 搜索 not in 会话标识:
            continue
        消息列表 = 会话.get("messages") or []
        最后消息 = 消息列表[-1] if 消息列表 else {}
        聊天列表.append(
            {
                "chat_id": 会话标识,
                "chat_type": 类型,
                "appid": str(会话.get("appid") or ""),
                "nickname": 显示名,
                "group_qq": 获取群QQ号(会话标识),
                "last_content": str(最后消息.get("content") or 会话.get("last_content") or ""),
                "last_time": str(最后消息.get("timestamp") or _格式化时间戳(会话.get("last_ts"))),
                "msg_count": len(消息列表),
                "remark": 获取群备注(会话标识),
                "in_group": True,
                "group_name": str(群信息缓存.get(会话标识, {}).get("group_name") or ""),
            }
        )
    聊天列表.sort(key=lambda x: (x.get("last_time") or "", x.get("chat_id") or ""), reverse=True)
    总数 = len(聊天列表)
    开始 = (页码 - 1) * 每页
    return {
        "chats": 聊天列表[开始 : 开始 + 每页],
        "total": 总数,
        "page": 页码,
        "page_size": 每页,
    }


def 获取消息历史(
    会话标识: str,
    类型: str = "group",
    before_date: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    会话 = 消息缓存.get(str(会话标识 or "").strip())
    if not 会话:
        return {
            "messages": [],
            "last_msg_id": "",
            "oldest_date": "",
            "has_more": False,
            "chat_name": "",
            "group_info": 获取缓存的群信息(会话标识),
        }
    try:
        limit = max(1, min(200, int(limit)))
    except (TypeError, ValueError):
        limit = 100
    消息列表 = 会话.get("messages") or []
    会话消息: list[dict[str, Any]] = list(消息列表)
    if before_date:
        before_date = str(before_date or "").strip()
        if before_date:
            会话消息 = [m for m in 会话消息 if str(m.get("timestamp") or "") < before_date]
    原始数量 = len(会话消息)
    返回消息 = 会话消息[-limit:]
    最后消息 = 会话消息[-1] if 会话消息 else {}
    引用映射: dict[str, dict[str, str]] = {}
    消息索引 = {str(m.get("message_id") or ""): m for m in 消息列表}
    for 消息记录项 in 返回消息:
        引用ID = str(消息记录项.get("reference_id") or "").strip()
        if not 引用ID or 引用ID in 引用映射:
            continue
        被引用 = 消息索引.get(引用ID)
        if 被引用:
            引用映射[引用ID] = {
                "nickname": str(被引用.get("nickname") or ""),
                "content": str(被引用.get("content") or ""),
                "timestamp": str(被引用.get("timestamp") or ""),
            }
    return {
        "messages": 返回消息,
        "last_msg_id": str(最后消息.get("message_id") or ""),
        "oldest_date": str(会话消息[0].get("timestamp") or "") if 会话消息 else "",
        "has_more": 原始数量 > limit,
        "chat_name": _聊天显示名(会话标识, 会话),
        "group_info": 获取缓存的群信息(会话标识),
        "member_profiles": 成员资料缓存.get(会话标识, {}),
        "references": 引用映射,
    }


async def 获取群角色(会话标识: str, appid: str = "") -> dict[str, Any]:
    """查询机器人在群状态与成员角色缓存，返回 (成员角色表, 机器人是否管理员)。"""
    平台实例 = 获取QQ官方平台()
    机器人角色 = ""
    机器人是否管理员 = False
    通道 = 获取HTTP通道(平台实例)
    if 通道 is not None:
        try:
            _, _http = 通道
            from botpy.http import Route

            route = Route(
                "GET",
                "/v2/groups/{group_openid}/bot_state",
                group_openid=会话标识,
            )
            结果 = await _http.request(route)
            if isinstance(结果, dict):
                机器人角色 = str(结果.get("member_role") or "")
                机器人是否管理员 = 机器人角色 in ("owner", "admin")
        except Exception as exc:
            logger.warning("消息记录群角色查询失败：错误类型=%s", type(exc).__name__)
    成员表: dict[str, dict[str, Any]] = {}
    for 成员标识, 资料 in (成员资料缓存.get(会话标识) or {}).items():
        成员表[成员标识] = {
            "nickname": 资料.get("nickname") or "",
            "is_bot": bool(资料.get("is_bot") or False),
            "role": "",
        }
    return {"roles": 成员表, "bot_is_admin": 机器人是否管理员, "bot_role": 机器人角色}


# ---------------------------------------------------------------------------
# 发送消息
# ---------------------------------------------------------------------------

def _规范化发送方式(方式: str) -> str:
    方式 = str(方式 or "default").strip()
    if 方式 in ("default", "passive", "active", "custom_msg_id", "custom_event_id"):
        return 方式
    return "default"


def _规范化消息类型(类型: str) -> str:
    类型 = str(类型 or "text").strip()
    if 类型 in ("text", "markdown", "media", "ark", "card"):
        return 类型
    return "text"


def _构造ARK数据(模板ID: str, 字段: dict[str, Any], 列表行: str) -> list[dict[str, Any]]:
    模板ID = str(模板ID or "24").strip()
    kv: list[dict[str, Any]] = []
    if 模板ID == "24":
        for 键 in ("#DESC#", "#PROMPT#", "#TITLE#", "#METADESC#", "#IMG#", "#LINK#", "#SUBTITLE#"):
            值 = str((字段 or {}).get(键) or "").strip()
            if 值:
                kv.append({"key": 键, "value": 值})
    elif 模板ID == "37":
        for 键 in ("#PROMPT#", "#METATITLE#", "#METASUBTITLE#", "#METACOVER#", "#METAURL#"):
            值 = str((字段 or {}).get(键) or "").strip()
            if 值:
                kv.append({"key": 键, "value": 值})
    else:  # 23 链接列表
        描述 = str((字段 or {}).get("#DESC#") or "").strip()
        提示 = str((字段 or {}).get("#PROMPT#") or "").strip()
        if 描述:
            kv.append({"key": "#DESC#", "value": 描述})
        if 提示:
            kv.append({"key": "#PROMPT#", "value": 提示})
        列表: list[dict[str, Any]] = []
        for 行 in str(列表行 or "").splitlines():
            行 = 行.strip()
            if not 行:
                continue
            部分 = 行.split("|", 1)
            if len(部分) == 2 and 部分[0].strip() and 部分[1].strip():
                列表.append(
                    {
                        "obj_kv": [
                            {"key": "desc", "value": 部分[0].strip()},
                            {"key": "link", "value": 部分[1].strip()},
                        ]
                    }
                )
        if 列表:
            kv.append({"key": "#LIST#", "obj": 列表})
    return kv


async def _上传媒体(
    _http: Any,
    会话标识: str,
    类型: str,
    文件路径: str = "",
    文件URL: str = "",
    文件类型: int = 1,
) -> str:
    """上传媒体到群/私聊，返回 file_info。"""
    from botpy.http import Route

    payload: dict[str, Any] = {"file_type": 文件类型, "srv_send_msg": False}
    地址 = str(文件路径 or "").strip()
    远程 = str(文件URL or "").strip()
    if 地址 and Path(地址).is_file():
        with open(地址, "rb") as f:
            payload["file_data"] = base64.b64encode(f.read()).decode("utf-8")
    elif 远程.startswith("http://") or 远程.startswith("https://"):
        payload["url"] = 远程
    else:
        return ""
    if 类型 == "user":
        payload["openid"] = 会话标识
        route = Route("POST", "/v2/users/{openid}/files", openid=会话标识)
    else:
        payload["group_openid"] = 会话标识
        route = Route(
            "POST",
            "/v2/groups/{group_openid}/files",
            group_openid=会话标识,
        )
    结果 = await _http.request(route, json=payload)
    if isinstance(结果, dict):
        return str(结果.get("file_info") or "")
    return ""


async def 发送消息(
    会话标识: str,
    类型: str,
    内容: str,
    appid: str = "",
    *,
    会话类型: str = "",
    消息ID: str = "",
    发送方式: str = "default",
    自定义ID: str = "",
    引用消息ID: str = "",
    图片路径: str = "",
    媒体路径: str = "",
    媒体URL: str = "",
    媒体文件类型: int = 1,
    ARK模板ID: str = "",
    ARK字段: dict[str, Any] | None = None,
    ARK列表: str = "",
    卡片字段: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """发送一条 QQ 官方消息，返回 {ok, message_id, message}。"""
    会话标识 = str(会话标识 or "").strip()
    类型 = _规范化消息类型(类型)
    发送方式 = _规范化发送方式(发送方式)
    内容 = str(内容 or "").strip()
    平台实例 = 获取QQ官方平台()
    通道 = 获取HTTP通道(平台实例)
    if 通道 is None:
        return {"ok": False, "message": "QQ官方平台未加载"}
    api, _http = 通道
    最近消息ID = 消息ID or 获取最近消息ID(平台实例, 会话标识)
    场景 = 获取会话场景(平台实例, 会话标识)
    if 发送方式 == "active":
        被动ID = ""
    elif 发送方式 == "custom_msg_id":
        被动ID = 自定义ID
    elif 发送方式 == "custom_event_id":
        被动ID = ""
    elif 发送方式 == "passive":
        被动ID = 最近消息ID
    else:
        # 默认：群聊全量消息可主动，其他被动
        被动ID = "" if (类型 == "group" and 场景 == "group" and 最近消息ID) else 最近消息ID
    事件ID = 自定义ID if 发送方式 == "custom_event_id" else ""
    消息体: dict[str, Any] = {
        "msg_type": 0,
        "content": 内容,
        "msg_seq": random.randint(1, 10000),
    }
    if 被动ID:
        消息体["msg_id"] = 被动ID
    if 事件ID:
        消息体["event_id"] = 事件ID
    if 引用消息ID:
        消息体["message_reference"] = {"message_id": 引用消息ID}

    if 类型 == "markdown":
        消息体["msg_type"] = 2
        消息体.pop("content", None)
        消息体["markdown"] = {"content": 内容}
    elif 类型 == "media":
        file_info = ""
        if 媒体路径 or 媒体URL:
            file_info = await _上传媒体(
                _http,
                会话标识,
                会话类型 or "group",
                媒体路径,
                媒体URL,
                int(媒体文件类型 or 1),
            )
        if not file_info:
            return {"ok": False, "message": "媒体上传失败"}
        消息体["msg_type"] = 7
        消息体.pop("content", None)
        消息体["media"] = {"file_info": file_info}
        if 内容:
            消息体["content"] = 内容
    elif 类型 == "ark":
        kv = _构造ARK数据(ARK模板ID, ARK字段 or {}, ARK列表)
        if not kv:
            return {"ok": False, "message": "请至少填写一个 ARK 字段"}
        消息体["msg_type"] = 3
        消息体.pop("content", None)
        消息体["ark"] = {"template_id": int(str(ARK模板ID or "24").strip() or 24), "kv": kv}
    elif 类型 == "card":
        卡片 = 卡片字段 or {}
        标题 = str(卡片.get("title") or "").strip()
        if not 标题:
            return {"ok": False, "message": "请填写卡片标题"}
        消息体["msg_type"] = 4
        消息体.pop("content", None)
        embed: dict[str, Any] = {
            "title": 标题,
            "desc": str(卡片.get("description") or "").strip(),
            "prompt": str(卡片.get("description") or "").strip(),
        }
        if str(卡片.get("pic_url") or "").strip():
            embed["image"] = str(卡片.get("pic_url") or "").strip()
        if str(卡片.get("url") or "").strip():
            embed["url"] = str(卡片.get("url") or "").strip()
        消息体["embed"] = embed

    if not 会话类型:
        会话缓存 = 消息缓存.get(会话标识) or {}
        会话类型 = str(会话缓存.get("chat_type") or "group")
    try:
        from botpy.http import Route

        if 会话类型 == "user":
            route = Route("POST", "/v2/users/{openid}/messages", openid=会话标识)
        else:
            route = Route(
                "POST",
                "/v2/groups/{group_openid}/messages",
                group_openid=会话标识,
            )
        结果 = await _http.request(route, json=消息体)
    except Exception as exc:
        logger.warning("消息记录发送失败：错误类型=%s", type(exc).__name__)
        return {"ok": False, "message": "发送失败，请稍后再试"}

    响应ID = ""
    if isinstance(结果, dict):
        响应ID = str(结果.get("id") or "")
    elif 结果 is not None:
        响应ID = str(getattr(结果, "id", None) or "")
    展示内容 = 内容
    if 类型 == "media":
        展示内容 = f"[媒体] {展示内容}"
    elif 类型 == "ark":
        展示内容 = "[ARK卡片] " + 展示内容
    elif 类型 == "card":
        展示内容 = "[图文卡片] " + 展示内容
    记录 = 记录发送消息(
        会话标识,
        会话类型 or "group",
        展示内容 or "（空消息）",
        appid,
        消息ID=响应ID,
        引用ID=引用消息ID,
    )
    return {"ok": True, "message_id": 响应ID, "message": 记录}


async def 撤回消息(会话标识: str, 消息ID: str, appid: str = "") -> dict[str, Any]:
    会话标识 = str(会话标识 or "").strip()
    消息ID = str(消息ID or "").strip()
    if not 会话标识 or not 消息ID:
        return {"ok": False, "message": "参数无效"}
    通道 = 获取HTTP通道()
    if 通道 is None:
        return {"ok": False, "message": "QQ官方平台未加载"}
    _, _http = 通道
    try:
        from botpy.http import Route

        route = Route(
            "DELETE",
            "/v2/groups/{group_openid}/messages/{message_id}",
            group_openid=会话标识,
            message_id=消息ID,
        )
        await _http.request(route)
        标记撤回(会话标识, 消息ID)
        return {"ok": True, "message": "撤回成功"}
    except Exception as exc:
        logger.warning("消息记录撤回失败：错误类型=%s", type(exc).__name__)
        return {"ok": False, "message": "撤回失败，请稍后再试"}


async def 禁言群成员(
    会话标识: str,
    成员标识: str,
    分钟数: int,
    appid: str = "",
) -> dict[str, Any]:
    会话标识 = str(会话标识 or "").strip()
    成员标识 = str(成员标识 or "").strip()
    try:
        分钟数 = max(1, min(43200, int(分钟数)))
    except (TypeError, ValueError):
        分钟数 = 30
    if not 会话标识 or not 成员标识:
        return {"ok": False, "message": "参数无效"}
    通道 = 获取HTTP通道()
    if 通道 is None:
        return {"ok": False, "message": "QQ官方平台未加载"}
    _, _http = 通道
    try:
        from botpy.http import Route

        from datetime import datetime, timedelta, timezone

        到期 = datetime.now(timezone.utc) + timedelta(minutes=分钟数)
        到期文本 = 到期.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        route = Route(
            "POST",
            "/v2/groups/{group_openid}/restrict_chat_setting",
            group_openid=会话标识,
        )
        await _http.request(
            route,
            json={
                "members": [
                    {
                        "op": "add",
                        "member_openid": 成员标识,
                        "mute_expire_at": 到期文本,
                    }
                ]
            },
        )
        return {"ok": True, "message": "禁言成功"}
    except Exception as exc:
        logger.warning("消息记录禁言失败：错误类型=%s", type(exc).__name__)
        return {"ok": False, "message": "禁言失败，请稍后再试"}


# ---------------------------------------------------------------------------
# 事件挂钩
# ---------------------------------------------------------------------------

def _安装消息事件挂钩() -> bool:
    """为 QQ 官方 botClient 包装消息事件回调，把收到的消息写入缓存。"""
    global _挂钩已安装
    if _挂钩已安装:
        return True
    try:
        from astrbot.core.platform.sources.qqofficial import (
            qqofficial_platform_adapter as 适配器模块,
        )
    except Exception as 异常:
        logger.warning("消息记录挂钩加载失败：错误类型=%s", type(异常).__name__)
        return False
    客户端类 = getattr(适配器模块, "botClient", None)
    if 客户端类 is None:
        return False

    事件表 = (
        ("on_group_at_message_create", "group"),
        ("on_group_message_create", "group"),
        ("on_c2c_message_create", "user"),
        ("on_direct_message_create", "user"),
    )
    for 事件名, 类型 in 事件表:
        原回调 = getattr(客户端类, 事件名, None)
        if 原回调 is None or getattr(原回调, "__module__", "") == __name__:
            continue

        async def 新回调(self: Any, 消息: Any, _原=原回调, _类型=类型) -> Any:
            try:
                appid = str(_读取字段(_读取字段(self, "platform"), "appid") or "")
                记录收到消息(消息, _类型, appid)
            except Exception as exc:
                logger.warning("消息记录事件缓存失败：错误类型=%s", type(exc).__name__)
            结果 = _原(self, 消息)
            if asyncio.iscoroutine(结果):
                return await 结果
            return 结果

        setattr(客户端类, 事件名, 新回调)
    _挂钩已安装 = True
    logger.info("消息记录事件挂钩已安装：group/user 消息已接入缓存")
    return True


def 安装消息记录(上下文: Any = None) -> bool:
    global 当前插件上下文
    if 上下文 is not None:
        当前插件上下文 = 上下文
    try:
        return _安装消息事件挂钩()
    except Exception as exc:
        logger.warning("消息记录安装失败：错误类型=%s", type(exc).__name__)
        return False
