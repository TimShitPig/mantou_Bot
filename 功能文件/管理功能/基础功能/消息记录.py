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

try:
    from 功能文件.管理功能.基础功能 import 消息记录存储

    _消息存储 = 消息记录存储
except Exception as 导入异常:
    _消息存储 = None
    logger.warning("消息记录存储模块加载失败：错误类型=%s", type(导入异常).__name__)

消息记录版本 = 1
最大会话数 = 200
每会话最大消息数 = 500
总消息上限 = 10000
当前插件上下文: Any = globals().get("当前插件上下文")
消息缓存: dict[str, dict[str, Any]] = globals().get("消息缓存") or {}
群信息缓存: dict[str, dict[str, Any]] = globals().get("群信息缓存") or {}
群信息待刷新: set[str] = globals().get("群信息待刷新") or set()
成员资料缓存: dict[str, dict[str, dict[str, Any]]] = globals().get("成员资料缓存") or {}
发送序号 = globals().get("发送序号") or 0
_挂钩已安装 = globals().get("_挂钩已安装", False)
_发送挂钩已安装 = globals().get("_发送挂钩已安装", False)

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

        if len(文本) >= 19 and 文本[4] == "-" and 文本[10] in ("T", " "):
            核心 = 文本[:19]
            格式 = "%Y-%m-%dT%H:%M:%S" if 文本[10] == "T" else "%Y-%m-%d %H:%M:%S"
            解析 = _日期类.strptime(核心, 格式)
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
            "unread": 0,
        }
    return 消息缓存[会话标识]


def _序列化原始消息(消息: Any, 最长: int = 0) -> str:
    try:
        文本 = str(消息 or "")
    except Exception:
        return ""
    if 最长 > 0 and len(文本) > 最长:
        return 文本[:最长] + "...[已截断]"
    return 文本


_表情标签规则 = re.compile(r'<faceType=\d+,faceId="([^"]*)"(?:,ext="([^"]*)")?>')
_表情JSON规则 = re.compile(r'"text"\s*:\s*"([^"]*)"')


def _解码表情文本(标签: str) -> str:
    """把 QQ 官方表情标签解码成可读文本，如 [？]。"""
    try:
        import base64
        import json as _json

        匹配 = _表情标签规则.search(标签)
        if not 匹配:
            return 标签
        表情ID = 匹配.group(1) or ""
        编码 = 匹配.group(2) or ""
        文本 = ""
        if 编码:
            try:
                原文 = base64.b64decode(编码).decode("utf-8", errors="ignore")
                try:
                    数据 = _json.loads(原文)
                    文本 = str(数据.get("text") or "")
                except Exception:
                    文本 = _表情JSON规则.search(原文).group(1) if _表情JSON规则.search(原文) else ""
            except Exception:
                pass
        if not 文本 or not 文本.strip():
            return f"[表情{表情ID}]" if 表情ID else "[表情]"
        return f"{文本}"
    except Exception:
        return 标签


def _提取消息文本(内容: Any) -> str:
    return _表情标签规则.sub(lambda 匹配: _解码表情文本(匹配.group(0)), str(内容 or "").strip())


_REFIDX规则 = re.compile(r"(?:^|[?&])msg_idx=([^&]+)")


def _提取REFIDX(消息: Any) -> str:
    """从消息 message_scene.ext 提取 REFIDX（QQ 官方引用消息专用标识）。"""
    try:
        场景 = _读取字段(消息, "message_scene") or {}
        if isinstance(场景, str):
            try:
                import json as _json

                场景 = _json.loads(场景)
            except Exception:
                场景 = {}
        扩展 = 场景.get("ext") if isinstance(场景, dict) else None
        if isinstance(扩展, str):
            扩展 = [扩展]
        if not isinstance(扩展, list):
            return ""
        for 项 in 扩展:
            if not isinstance(项, str):
                continue
            匹配 = _REFIDX规则.search(项)
            if 匹配:
                try:
                    from urllib.parse import unquote

                    return unquote(匹配.group(1))
                except Exception:
                    return 匹配.group(1)
    except Exception:
        pass
    return ""


def _提取附件媒体(消息: Any) -> dict[str, str] | None:
    """从 QQ 官方消息 attachments 提取图片/语音/视频/文件媒体信息。"""
    try:
        附件列表 = _读取字段(消息, "attachments")
        if not isinstance(附件列表, list) or not 附件列表:
            return None
        for 附件 in 附件列表:
            类型 = str(_读取字段(附件, "content_type") or "").lower()
            地址 = str(_读取字段(附件, "url") or "").strip()
            if not 地址:
                continue
            if 类型.startswith("image/"):
                return {"type": "图片", "src": 地址, "text": ""}
            if 类型.startswith("video/"):
                return {"type": "视频", "src": 地址, "text": ""}
            if 类型.startswith("audio/"):
                return {"type": "语音", "src": 地址, "text": ""}
            return {"type": "文件", "src": 地址, "text": ""}
    except Exception:
        pass
    return None


def _提取媒体字段(内容: str, 消息: Any = None) -> dict[str, str] | None:
    """提取媒体信息：优先附件图片，其次消息原文占位或 QQ 富媒体图片链接。"""
    附件媒体 = _提取附件媒体(消息)
    if 附件媒体:
        return 附件媒体
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
    """从 QQ 官方消息提取昵称（botpy 修补后 author 已带 username）。"""
    作者 = _读取字段(消息, "author") or {}
    for 字段 in ("username", "member_name", "nickname", "user_name", "name"):
        昵称 = str(_读取字段(作者, 字段) or "").strip()
        if 昵称:
            return 昵称
    for 字段 in ("username", "member_name", "nickname", "dear_remark", "user_name", "name"):
        昵称 = str(_读取字段(消息, 字段) or "").strip()
        if 昵称:
            return 昵称
    return ""


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


_后台补查任务: list[Any] = []
_用户详情接口不可用 = False


def _昵称需要补查(会话标识: str, 会话: dict[str, Any] | None) -> bool:
    """私聊会话昵称缺失（空/未知/openid）时需要补查。"""
    if not 会话:
        return False
    昵称 = str(会话.get("last_nickname") or "").strip()
    if not 昵称 or "未知" in 昵称:
        return True
    if 会话标识 and 昵称 == 会话标识:
        return True
    return False


def _私聊兜底昵称(会话标识: str) -> str:
    """私聊昵称无法从 QQ 官方事件/接口获取时，用 Elaina 同款可读兜底名。"""
    try:
        标识 = str(会话标识 or "").strip()
        if not 标识:
            return "未知用户"
        if len(标识) > 6:
            return "用户" + 标识[-6:]
        return "用户" + 标识
    except Exception:
        return "未知用户"


def _保存本地昵称(会话标识: str, 昵称: str) -> None:
    """把补查到的昵称持久化到本地缓存，重启后仍可显示。"""
    if not 会话标识 or not 昵称:
        return
    try:
        数据 = _读取本地缓存文件()
        昵称表 = 数据.setdefault("nicknames", {})
        if str(昵称表.get(会话标识) or "") != 昵称:
            昵称表[会话标识] = 昵称
            _写入本地缓存文件(数据)
    except Exception as exc:
        logger.warning("私聊昵称持久化失败：错误类型=%s", type(exc).__name__)


async def _补查用户昵称(会话标识: str, 用户标识: str, appid: str = "") -> None:
    """私聊昵称消息事件不含，尝试调用 QQ 官方用户详情接口补查并回写缓存。

    QQ 官方开放平台目前未提供该接口（路径不存在返回 404），
    首次失败后标记接口不可用，避免每次收到私聊消息都重复请求。
    """
    global _用户详情接口不可用
    if not 用户标识 or _用户详情接口不可用:
        return
    try:
        from botpy.http import Route

        平台实例 = 获取QQ官方平台()
        通道 = 获取HTTP通道(平台实例)
        if 通道 is None:
            return
        _api, _http = 通道
        结果 = await _http.request(Route("GET", "/v2/users/{openid}", openid=用户标识))
        数据 = 结果 if isinstance(结果, dict) else (getattr(结果, "data", None) or {})
        昵称 = str(_读取字段(数据, "username") or "").strip()
        if not 昵称:
            return
        会话 = 消息缓存.get(str(会话标识 or "").strip())
        if 会话:
            if _昵称需要补查(会话标识, 会话):
                会话["last_nickname"] = 昵称
            资料 = 成员资料缓存.setdefault(str(会话标识 or "").strip(), {})
            旧资料 = 资料.get(用户标识) or {}
            if not str(旧资料.get("nickname") or "").strip():
                旧资料["nickname"] = 昵称
                资料[用户标识] = 旧资料
        _保存本地昵称(会话标识, 昵称)
    except Exception as exc:
        名称 = type(exc).__name__
        if 名称 in ("NotFoundError", "Not Found", "NotFound"):
            _用户详情接口不可用 = True
            logger.info("QQ 官方未提供用户详情接口，私聊昵称改用兜底显示")
        else:
            logger.warning("私聊昵称补查失败：错误类型=%s", 名称)


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
        自身REFIDX = _提取REFIDX(消息)
        _记录成员资料(会话标识, 成员标识, 昵称, 是机器人, 角色)
        会话 = _取得会话缓存(会话标识, 类型, appid)
        if 类型 == "group" and 会话标识 not in 群信息缓存:
            标记群信息待刷新(会话标识)
        发送序号 += 1
        记录: dict[str, Any] = {
            "id": 发送序号,
            "message_id": 消息ID,
            "user_id": 成员标识,
            "_session": 会话标识,
            "appid": str(appid or 会话.get("appid") or ""),
            "nickname": 昵称 or (_私聊兜底昵称(会话标识) if 类型 == "user" else "未知用户"),
            "content": 内容,
            "timestamp": _格式化时间戳(时间戳),
            "is_self": bool(is_self),
            "source": 源,
            "raw_message": _序列化原始消息(_读取字段(消息, "raw_data") or 消息),
            "recalled": False,
            "media": _提取媒体字段(内容, 消息),
            "reference_id": 引用ID or "",
            "refidx": 自身REFIDX or "",
            "chat_type": 类型,
            "ts": _转数字时间戳(时间戳) or int(time.time()),
        }
        会话["messages"].append(记录)
        if not is_self and not 是机器人:
            会话["unread"] = int(会话.get("unread") or 0) + 1
        if _消息存储 is not None:
            try:
                _消息存储.写入消息(记录)
            except Exception as 存储异常:
                logger.debug("消息记录入库失败：错误类型=%s", type(存储异常).__name__)
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
    if _消息存储 is not None:
        try:
            _消息存储.裁剪总消息(总消息上限 * 2)
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
            "chat_type": 类型,
            "ts": int(time.time()),
        }
        会话["messages"].append(记录)
        if _消息存储 is not None:
            try:
                _消息存储.写入消息(记录)
            except Exception as 存储异常:
                logger.debug("消息记录入库失败：错误类型=%s", type(存储异常).__name__)
        if len(会话["messages"]) > 每会话最大消息数:
            会话["messages"] = 会话["messages"][-每会话最大消息数:]
        if 内容:
            会话["last_content"] = 内容
            会话["last_nickname"] = "我"
        会话["last_ts"] = int(time.time())
        会话["unread"] = 0
        _裁剪总缓存()
        return 记录
    except Exception as exc:
        logger.warning("消息记录发送缓存写入失败：错误类型=%s", type(exc).__name__)
        return None


def 设置会话已读(会话标识: str) -> bool:
    """打开会话时清零未读数。"""
    try:
        会话 = 消息缓存.get(str(会话标识 or "").strip())
        if not 会话:
            return False
        会话["unread"] = 0
        return True
    except Exception:
        return False


def 标记撤回(会话标识: str, 消息ID: str) -> bool:
    会话 = 消息缓存.get(str(会话标识 or "").strip())
    找到 = False
    if 会话:
        for 记录 in 会话.get("messages", []):
            if 记录.get("message_id") == 消息ID:
                记录["recalled"] = True
                找到 = True
                break
    if _消息存储 is not None:
        try:
            _消息存储.标记消息撤回(会话标识, 消息ID)
        except Exception:
            pass
    return 找到


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


def 获取本地最近消息ID(会话标识: str) -> str:
    """从进程内消息缓存找最近一条收到的消息 ID 作为被动发送 msg_id 兜底。"""
    try:
        会话 = 消息缓存.get(会话标识) or {}
        消息列表 = 会话.get("messages") or []
        for 记录 in reversed(消息列表):
            if bool(记录.get("is_self")):
                continue
            消息ID = str(记录.get("message_id") or "").strip()
            if 消息ID:
                return 消息ID
    except Exception:
        pass
    return ""


def 获取本地最近消息时效(会话标识: str) -> float:
    """返回最近一条收到的消息的时间戳（秒），无消息时返回 0。"""
    try:
        会话 = 消息缓存.get(会话标识) or {}
        消息列表 = 会话.get("messages") or []
        for 记录 in reversed(消息列表):
            if bool(记录.get("is_self")):
                continue
            消息ID = str(记录.get("message_id") or "").strip()
            if 消息ID:
                return int(_转数字时间戳(记录.get("timestamp")) or 0)
    except Exception:
        pass
    return 0


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


def 删除群备注(会话标识: str) -> None:
    """删除某个会话的全部备注与群号信息。"""
    数据 = _读取本地缓存文件()
    备注表 = 数据.get("remarks") or {}
    if 会话标识 in 备注表:
        del 备注表[会话标识]
        数据["remarks"] = 备注表
        _写入本地缓存文件(数据)


def 设置会话置顶(会话标识: str, 置顶: bool) -> bool:
    """置顶或取消置顶会话，置顶顺序持久化到本地缓存。"""
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return False
    数据 = _读取本地缓存文件()
    置顶列表 = [str(x) for x in (数据.get("pinned") or []) if str(x or "").strip()]
    已置顶 = 会话标识 in 置顶列表
    if 置顶 and not 已置顶:
        置顶列表.insert(0, 会话标识)
        数据["pinned"] = 置顶列表
        _写入本地缓存文件(数据)
    elif not 置顶 and 已置顶:
        置顶列表 = [x for x in 置顶列表 if x != 会话标识]
        数据["pinned"] = 置顶列表
        _写入本地缓存文件(数据)
    return True


_本地缓存内存: dict[str, Any] | None = None
_本地缓存时间: float = 0.0


def _读取本地缓存文件(强制刷新: bool = False) -> dict[str, Any]:
    """读取置顶/备注/昵称元数据：优先 MySQL，未配置数据库时仅内存缓存。"""
    global _本地缓存内存, _本地缓存时间
    now = time.time()
    if not 强制刷新 and _本地缓存内存 is not None and now - _本地缓存时间 < 5.0:
        return _本地缓存内存
    try:
        if _消息存储 is not None:
            元数据 = _消息存储.读取全部元数据()
            if 元数据:
                _本地缓存内存 = 元数据
                _本地缓存时间 = now
                return 元数据
    except Exception as exc:
        logger.debug("消息记录 MySQL 元数据读取失败：错误类型=%s", type(exc).__name__)
    return dict(_本地缓存内存 or {})


def _写入本地缓存文件(数据: dict[str, Any]) -> None:
    """写入置顶/备注/昵称元数据：仅 MySQL（不产生任何本地文件）。"""
    global _本地缓存内存, _本地缓存时间
    _本地缓存内存 = 数据
    _本地缓存时间 = time.time()
    if _消息存储 is None:
        return
    for 键, 值 in (数据 or {}).items():
        try:
            _消息存储.写入元数据(键, 值)
        except Exception as 存储异常:
            logger.debug("消息记录元数据入库失败：错误类型=%s", type(存储异常).__name__)


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
    if 最近昵称:
        return 最近昵称
    if str(会话.get("chat_type") or "") == "user":
        本地昵称 = str((_读取本地缓存文件().get("nicknames") or {}).get(会话标识) or "")
        if 本地昵称:
            return 本地昵称
        return _私聊兜底昵称(会话标识)
    return 会话标识


async def 补查缺失私聊昵称(聊天项列表: list[dict[str, Any]]) -> int:
    """对昵称缺失的私聊会话逐个补查昵称（历史会话补查入口）。"""
    补查数 = 0
    if not 聊天项列表:
        return 0
    try:
        for 聊天 in 聊天项列表:
            if str(聊天.get("chat_type") or "") != "user":
                continue
            会话标识 = str(聊天.get("chat_id") or "").strip()
            if not 会话标识:
                continue
            会话 = 消息缓存.get(会话标识)
            if not _昵称需要补查(会话标识, 会话):
                continue
            本地昵称 = str((_读取本地缓存文件().get("nicknames") or {}).get(会话标识) or "")
            if 本地昵称:
                if 会话:
                    会话["last_nickname"] = 本地昵称
                continue
            兜底 = _私聊兜底昵称(会话标识)
            if 会话 and (not str(会话.get("last_nickname") or "").strip() or "未知" in str(会话.get("last_nickname") or "")):
                会话["last_nickname"] = 兜底
            补查数 += 1
    except Exception as exc:
        logger.warning("私聊昵称批量补查失败：错误类型=%s", type(exc).__name__)
    return 补查数


def _补齐数据库会话到内存() -> None:
    """把 MySQL 中持久化的会话补回内存，保证置顶/备注会话重启后仍显示。"""
    if _消息存储 is None:
        return
    try:
        已加载 = False
        for 会话标识 in _消息存储.读取全部会话标识():
            会话标识 = str(会话标识 or "").strip()
            if not 会话标识 or 会话标识 in 消息缓存:
                continue
            消息列表 = _消息存储.读取会话消息(会话标识, 每会话最大消息数)
            if not 消息列表:
                continue
            类型 = str(消息列表[-1].get("chat_type") or "group")
            会话 = _取得会话缓存(会话标识, 类型, str(消息列表[-1].get("appid") or ""))
            会话["messages"] = 消息列表
            最后 = 消息列表[-1]
            会话["last_content"] = str(最后.get("content") or "")
            会话["last_nickname"] = str(最后.get("nickname") or "")
            会话["last_ts"] = int(最后.get("ts") or 0)
            已加载 = True
        if 已加载:
            logger.debug("消息记录会话已从数据库补回内存")
    except Exception as exc:
        logger.debug("消息记录数据库会话补回失败：错误类型=%s", type(exc).__name__)


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
    本地数据 = _读取本地缓存文件()
    本地备注表 = (本地数据.get("remarks") or {})
    _补齐数据库会话到内存()
    for 会话标识, 会话 in 消息缓存.items():
        类型 = str(会话.get("chat_type") or "group")
        if 过滤 == "group" and 类型 != "group":
            continue
        if 过滤 == "user" and 类型 != "user":
            continue
        会话备注 = 本地备注表.get(会话标识) or {}
        备注 = str(会话备注.get("remark") or "")
        if 过滤 == "remark" and not 备注:
            continue
        if 类型 == "group":
            缓存群信息 = 群信息缓存.get(会话标识)
            if not 缓存群信息 or int(time.time()) - int(缓存群信息.get("updated_at") or 0) > 300:
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
                "group_qq": str(会话备注.get("group_qq") or ""),
                "last_content": _表情标签规则.sub(lambda 匹配: _解码表情文本(匹配.group(0)), str(最后消息.get("content") or 会话.get("last_content") or "")),
                "last_time": str(最后消息.get("timestamp") or _格式化时间戳(会话.get("last_ts"))),
                "last_ts": int(会话.get("last_ts") or 0),
                "msg_count": len(消息列表),
                "unread": int(会话.get("unread") or 0),
                "remark": 备注,
                "in_group": True,
                "group_name": str(群信息缓存.get(会话标识, {}).get("group_name") or ""),
            }
        )
    置顶列表 = [str(x) for x in (本地数据.get("pinned") or []) if str(x or "").strip()]
    置顶顺序 = {会话: idx for idx, 会话 in enumerate(置顶列表)}
    for 聊天 in 聊天列表:
        聊天["pinned"] = str(聊天.get("chat_id") or "") in 置顶顺序
    # 置顶会话整体排前，组内按最新消息时间倒序；未置顶按最新消息时间倒序（同 QQ）
    聊天列表.sort(
        key=lambda x: (
            0 if str(x.get("chat_id") or "") in 置顶顺序 else 1,
            -(x.get("last_ts") or 0),
            str(x.get("chat_id") or ""),
        )
    )
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
    for 历史项 in 返回消息:
        if isinstance(历史项, dict) and 历史项.get("raw_message"):
            历史项["raw_message"] = _序列化原始消息(历史项.get("raw_message"), 3000)
        if isinstance(历史项, dict) and 历史项.get("content"):
            历史项["content"] = _表情标签规则.sub(lambda 匹配: _解码表情文本(匹配.group(0)), str(历史项.get("content") or ""))
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
    文件字节: bytes | None = None,
) -> str:
    """上传媒体到群/私聊，返回 file_info。"""
    from botpy.http import Route

    payload: dict[str, Any] = {"file_type": 文件类型, "srv_send_msg": False}
    地址 = str(文件路径 or "").strip()
    远程 = str(文件URL or "").strip()
    if 文件字节:
        payload["file_data"] = base64.b64encode(文件字节).decode("utf-8")
    elif 地址 and Path(地址).is_file():
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
    图片数据: str = "",
    媒体路径: str = "",
    媒体URL: str = "",
    媒体文件类型: int = 1,
    媒体文本: str = "",
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
    最近消息ID = 消息ID or 获取最近消息ID(平台实例, 会话标识) or 获取本地最近消息ID(会话标识)
    场景 = 获取会话场景(平台实例, 会话标识)
    # QQ 官方被动消息 msg_id 2 分钟时效：优先用近期收到的消息 ID 被动发送
    本地最近时间 = 获取本地最近消息时效(会话标识)
    近期消息ID = ""
    if 本地最近时间 and int(time.time()) - 本地最近时间 <= 100:
        近期消息ID = 获取本地最近消息ID(会话标识)
    if 发送方式 == "active":
        被动ID = ""
    elif 发送方式 == "custom_msg_id":
        被动ID = 自定义ID
    elif 发送方式 == "custom_event_id":
        被动ID = ""
    elif 发送方式 == "passive":
        被动ID = 近期消息ID or ""
    else:
        # 默认：仅用 2 分钟时效内的近期 msg_id 被动发送；无近期消息时尝试主动推送（全量群可用）
        被动ID = 近期消息ID or ""
    if 类型 == "group" and 发送方式 == "default" and not 被动ID:
        return {"ok": False, "message": "发送失败：该群最近没有收到新消息，无法主动发送。请先在群里发一条消息后 2 分钟内重试，或确认该群已开启全量消息接收。"}
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
        引用目标 = 引用消息ID
        # QQ 官方引用需优先使用被引用消息自身的 REFIDX，找不到时回退完整消息 ID
        for 会话记录 in 消息缓存.values():
            目标 = next((x for x in (会话记录.get("messages") or []) if str(x.get("message_id") or "") == 引用消息ID), None)
            if 目标 and 目标.get("refidx"):
                引用目标 = str(目标.get("refidx"))
                break
        消息体["message_reference"] = {"message_id": 引用目标, "ignore_get_message_error": True}

    图片字节: bytes | None = None
    if 图片数据:
        图片数据 = str(图片数据 or "").strip()
        try:
            if 图片数据.startswith("data:") and "," in 图片数据:
                图片数据 = 图片数据.split(",", 1)[1]
            图片字节 = base64.b64decode(图片数据)
        except Exception:
            return {"ok": False, "message": "图片数据无效"}

    # QQ 官方富媒体消息与文本不能混在同一条：图片和文字分两条发送（先图片后文字）
    if 图片字节 is not None:
        file_info = await _上传媒体(
            _http,
            会话标识,
            会话类型 or "group",
            文件类型=1,
            文件字节=图片字节,
        )
        if not file_info:
            return {"ok": False, "message": "图片上传失败"}
        消息体["msg_type"] = 7
        消息体.pop("content", None)
        消息体["media"] = {"file_info": file_info}

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
        # 媒体说明文本单独补发（QQ 官方不支持图文/媒体混排）
        if str(媒体文本 or "").strip() and not 内容:
            内容 = str(媒体文本 or "").strip()
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
        # 图片/媒体+文字：QQ 官方不支持图文混排，先发媒体，再补发一条文本消息
        if 消息体.get("msg_type") == 7 and 内容:
            文本消息体 = {
                "msg_type": 0,
                "content": 内容,
                "msg_seq": random.randint(1, 10000),
            }
            if 被动ID:
                文本消息体["msg_id"] = 被动ID
            if 事件ID:
                文本消息体["event_id"] = 事件ID
            try:
                文本结果 = await _http.request(route, json=文本消息体)
                文本ID = ""
                if isinstance(文本结果, dict):
                    文本ID = str(文本结果.get("id") or "")
                记录发送消息(会话标识, 会话类型 or "group", 内容, appid, 消息ID=文本ID, 引用ID=引用消息ID)
            except Exception as 文本异常:
                logger.warning("消息记录图片附带文本发送失败：错误类型=%s", type(文本异常).__name__)
    except Exception as exc:
        import traceback as _traceback

        logger.warning(
            "消息记录发送失败：错误类型=%s，错误详情=%s",
            type(exc).__name__,
            str(exc)[:400],
        )
        错误文本 = str(exc)
        if 被动ID and any(词 in 错误文本 for 词 in ("过期", "expired", "msg_id")):
            # msg_id 已过期：去掉后重试一次主动推送（全量消息群可成功）
            消息体.pop("msg_id", None)
            try:
                结果 = await _http.request(route, json=消息体)
            except Exception as 重试异常:
                错误文本 = str(重试异常)
                logger.warning("消息记录主动重试失败：错误类型=%s，错误详情=%s", type(重试异常).__name__, 错误文本[:400])
            else:
                if isinstance(结果, dict) and 结果.get("id"):
                    响应ID = str(结果.get("id") or "")
                    展示内容 = 内容
                    if 消息体.get("msg_type") == 7 and 图片字节 is not None:
                        展示内容 = "[图片]" if not 内容 else "[图片] " + 内容
                    if 类型 == "media":
                        展示内容 = "[媒体]"
                    elif 类型 == "ark":
                        展示内容 = "[ARK卡片] " + 展示内容
                    elif 类型 == "card":
                        展示内容 = "[图文卡片] " + 展示内容
                    记录 = 记录发送消息(会话标识, 会话类型 or "group", 展示内容 or "（空消息）", appid, 消息ID=响应ID, 引用ID=引用消息ID)
                    return {"ok": True, "message_id": 响应ID, "message": 记录}
                错误文本 = "重试后仍失败"
        if 类型 == "user" and not 被动ID:
            return {"ok": False, "message": "私聊发送失败：该用户不在互动窗口内，请先在 QQ 中与该机器人互动一次"}
        if any(词 in 错误文本 for 词 in ("过期", "expired", "msg_id已过期", "msg_id 已过期")):
            return {"ok": False, "message": "发送失败：被动消息ID已过期，请先在目标会话发一条新消息后 2 分钟内重试"}
        if any(词 in 错误文本 for 词 in ("403", "Forbidden", "没有权限", "not allowed", "not_admin", "no permission")):
            return {"ok": False, "message": "发送失败：机器人没有该会话的发送权限"}
        if any(词 in 错误文本 for 词 in ("404", "Not Found", "不存在", "invalid", "无效")):
            return {"ok": False, "message": "发送失败：会话或目标不存在，请刷新会话列表重试"}
        if "timeout" in 错误文本.lower() or "timed out" in 错误文本.lower():
            return {"ok": False, "message": "发送失败：请求超时，请稍后重试"}
        _traceback.print_exc()
        return {"ok": False, "message": "发送失败，请稍后再试"}

    响应ID = ""
    if isinstance(结果, dict):
        响应ID = str(结果.get("id") or "")
    elif 结果 is not None:
        响应ID = str(getattr(结果, "id", None) or "")
    展示内容 = 内容
    if 消息体.get("msg_type") == 7 and 图片字节 is not None:
        展示内容 = "[图片]" if not 内容 else "[图片] " + 内容
    if 类型 == "media":
        展示内容 = "[媒体]"
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
        提示 = "禁言失败，请稍后再试"
        原文 = str(getattr(exc, "resp", "") or exc)
        if "not admin" in 原文 or "没有权限" in 原文 or "权限" in 原文:
            提示 = "机器人不是该群管理员，无法执行禁言"
        elif "不存在" in 原文 or "无效" in 原文:
            提示 = "群或成员不存在，无法禁言"
        logger.warning("消息记录禁言失败：错误类型=%s", type(exc).__name__)
        return {"ok": False, "message": 提示}


# ---------------------------------------------------------------------------
# botpy 昵称修补
# ---------------------------------------------------------------------------

_昵称修补已安装 = globals().get("_昵称修补已安装", False)


def _修补botpy昵称() -> bool:
    """botpy 解析 QQ 官方事件时丢弃了 author.username，这里包装构造器补回。

    QQ 官方 C2C/群聊事件原始 JSON 的 author 带 username（用户昵称），但
    botpy 1.2.1 的 C2CMessage._User / GroupMessage._User 只解析 openid。
    在事件构造后把 username 动态补到 author 对象上，下游即可读取。
    """
    global _昵称修补已安装
    if _昵称修补已安装:
        return True
    try:
        import botpy.message as _botpy消息模块
    except Exception:
        return False
    for 类名 in ("C2CMessage", "GroupMessage"):
        消息类 = getattr(_botpy消息模块, 类名, None)
        if 消息类 is None:
            continue
        原初始化 = getattr(消息类, "__init__", None)
        if 原初始化 is None or getattr(原初始化, "__module__", "") == __name__:
            continue

        def 新初始化(self: Any, *参数: Any, _原=原初始化, **关键字: Any) -> None:
            _原(self, *参数, **关键字)
            try:
                作者 = getattr(self, "author", None)
                if 作者 is None or getattr(作者, "username", None):
                    return
                数据 = None
                for 项 in 参数:
                    if isinstance(项, dict) and 项.get("author") is not None:
                        数据 = 项
                        break
                if 数据 is None:
                    数据 = 关键字.get("data")
                if not isinstance(数据, dict):
                    return
                作者数据 = 数据.get("author") or {}
                if not isinstance(作者数据, dict):
                    return
                昵称 = str(作者数据.get("username") or "").strip()
                if 昵称:
                    作者.username = 昵称
            except Exception:
                pass

        消息类.__init__ = 新初始化  # type: ignore[method-assign]
    _昵称修补已安装 = True
    return True


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
                _安装消息发送挂钩()
                appid = str(_读取字段(_读取字段(self, "platform"), "appid") or "")
                记录 = 记录收到消息(消息, _类型, appid)
                if _类型 == "user" and 记录:
                    用户标识 = str(记录.get("user_id") or "").strip()
                    会话标识 = str(记录.get("_session") or "").strip()
                    if 用户标识 and 会话标识:
                        try:
                            try:
                                _后台补查任务.append(asyncio.create_task(_补查用户昵称(会话标识, 用户标识, appid)))
                            except RuntimeError:
                                _后台补查任务.append(asyncio.get_event_loop().create_task(_补查用户昵称(会话标识, 用户标识, appid)))
                        except Exception:
                            pass
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


def _链提取文本(消息链: Any) -> str:
    """从 AstrBot MessageChain 提取展示文本（纯文本 + 媒体占位）。"""
    try:
        段们 = getattr(消息链, "segments", None) or []
        文本 = ""
        for 段 in 段们:
            类型 = str(getattr(段, "type", "") or "")
            数据 = getattr(段, "data", None)
            if 类型 == "Plain":
                if isinstance(数据, dict):
                    文本 += str(数据.get("text") or "")
                else:
                    文本 += str(数据 or "")
            elif 类型 == "Image":
                文本 += "[图片] "
            elif 类型 == "File":
                文本 += "[文件] "
            elif 类型 == "Video":
                文本 += "[视频] "
            elif 类型 == "Record":
                文本 += "[语音] "
            elif 类型 == "Markdown":
                if isinstance(数据, dict):
                    文本 += str(数据.get("content") or "")
                else:
                    文本 += str(数据 or "")
        return 文本.strip()
    except Exception:
        return ""


def _会话标识兜底(session: Any) -> str:
    """从 AstrBot MessageSession 提取会话标识，优先匹配缓存中已存在的键。"""
    try:
        候选 = [
            str(getattr(session, "session_id", "") or "").strip(),
            str(getattr(session, "group_id", "") or "").strip(),
            str(getattr(session, "user_id", "") or "").strip(),
            str(getattr(session, "target_id", "") or "").strip(),
            str(getattr(session, "openid", "") or "").strip(),
            str(getattr(session, "sender_id", "") or "").strip(),
        ]
        for 键 in 候选:
            if 键 and 键 in 消息缓存:
                return 键
        for 键 in 候选:
            if 键:
                return 键
    except Exception:
        pass
    return ""


def _包装事件发送(发送方法: Any) -> Any:
    """包装 QQ 官方事件层的发送入口（_post_send）。

    AstrBot 调度器对插件回复调用 event.send()/send_streaming()，最终都汇入
    QQOfficialMessageEvent._post_send()；这里在真正发送前把机器人消息写入缓存。
    """
    if 发送方法 is None or getattr(发送方法, "__module__", "") == __name__:
        return None

    async def 新发送(self: Any, stream: Any = None, **关键字: Any) -> Any:
        try:
            缓冲 = getattr(self, "send_buffer", None)
            if 缓冲 is not None:
                会话标识 = str(getattr(getattr(self, "session", None), "session_id", "") or "").strip()
                消息类型 = getattr(getattr(self, "session", None), "message_type", None)
                类型 = "group" if "GROUP" in str(消息类型).upper() else "user"
                appid = ""
                try:
                    appid = str(getattr(getattr(self, "platform_meta", None), "id", "") or "")
                except Exception:
                    pass
                内容 = _链提取文本(缓冲)
                if 会话标识 and 内容:
                    记录发送消息(会话标识, 类型, 内容, appid)
        except Exception as exc:
            logger.warning("消息记录事件发送挂钩失败：错误类型=%s", type(exc).__name__)
        结果 = 发送方法(self, stream, **关键字)
        if asyncio.iscoroutine(结果):
            return await 结果
        return 结果

    return 新发送


def _包装发送方法(发送方法: Any) -> Any:
    """生成包装后的发送方法：调用前把机器人发送的消息写入缓存。"""
    if 发送方法 is None or getattr(发送方法, "__module__", "") == __name__:
        return None

    async def 新发送(self: Any, session: Any, message_chain: Any) -> Any:
        try:
            appid = str(getattr(self, "appid", "") or "")
            会话标识 = _会话标识兜底(session)
            消息类型 = str(getattr(session, "message_type", "") or "")
            类型 = "group" if "GROUP" in 消息类型.upper() else "user"
            内容 = _链提取文本(message_chain)
            if 会话标识 and 内容:
                记录发送消息(会话标识, 类型, 内容, appid)
        except Exception as exc:
            logger.warning("消息记录发送挂钩失败：错误类型=%s", type(exc).__name__)
        结果 = 发送方法(self, session, message_chain)
        if asyncio.iscoroutine(结果):
            return await 结果
        return 结果

    return 新发送


def _安装消息发送挂钩() -> bool:
    """包装平台发送入口，把机器人发送的消息写入缓存。

    双保险：优先包装 QQ 官方适配器类，再包装 AstrBot 平台基类，避免
    适配器版本差异导致漏记。
    """
    global _发送挂钩已安装
    if _发送挂钩已安装:
        return True
    已包装 = 0
    try:
        from astrbot.core.platform.sources.qqofficial import (
            qqofficial_message_event as 事件模块,
            qqofficial_platform_adapter as 适配器模块,
        )

        适配器类 = getattr(适配器模块, "QQOfficialPlatformAdapter", None)
        if 适配器类 is not None:
            原发送 = getattr(适配器类, "send_by_session", None)
            新发送 = _包装发送方法(原发送)
            if 新发送 is not None:
                setattr(适配器类, "send_by_session", 新发送)
                已包装 += 1
        事件类 = getattr(事件模块, "QQOfficialMessageEvent", None)
        if 事件类 is not None:
            原发送 = getattr(事件类, "_post_send", None)
            新发送 = _包装事件发送(原发送)
            if 新发送 is not None:
                setattr(事件类, "_post_send", 新发送)
                已包装 += 1
    except Exception as 异常:
        logger.warning("消息记录发送挂钩（适配器/事件）加载失败：错误类型=%s", type(异常).__name__)
    try:
        from astrbot.core.platform.platform import Platform as 平台基类

        原基类发送 = getattr(平台基类, "send_by_session", None)
        新基类发送 = _包装发送方法(原基类发送)
        if 新基类发送 is not None:
            setattr(平台基类, "send_by_session", 新基类发送)
            已包装 += 1
    except Exception as 异常:
        logger.warning("消息记录发送挂钩（基类）加载失败：错误类型=%s", type(异常).__name__)
    if 已包装 == 0:
        return False
    _发送挂钩已安装 = True
    logger.info("消息记录发送挂钩已安装：机器人发送消息已接入缓存（%d 处）", 已包装)
    return True


def 安装消息记录(上下文: Any = None) -> bool:
    global 当前插件上下文
    if 上下文 is not None:
        当前插件上下文 = 上下文
    try:
        if _消息存储 is not None:
            try:
                _消息存储.设置数据库配置(getattr(上下文, "config", None))
                _消息存储.初始化数据库()
                _从数据库恢复()
            except Exception as 恢复异常:
                logger.warning("消息记录数据库恢复失败：错误类型=%s", type(恢复异常).__name__)
        _修补botpy昵称()
        _安装消息事件挂钩()
        _安装消息发送挂钩()
        return True
    except Exception as exc:
        logger.warning("消息记录安装失败：错误类型=%s", type(exc).__name__)
        return False


def _从数据库恢复() -> None:
    """启动/重载时从 MySQL 恢复会话与最近消息，置顶/备注/昵称随元数据恢复。"""
    if _消息存储 is None:
        return
    元数据 = {}
    try:
        元数据 = _消息存储.读取全部元数据() or {}
    except Exception as exc:
        logger.debug("消息记录元数据恢复失败：错误类型=%s", type(exc).__name__)
    if 元数据:
        global _本地缓存内存, _本地缓存时间
        _本地缓存内存 = 元数据
        _本地缓存时间 = time.time()
    会话标识列表 = _消息存储.读取全部会话标识()
    置顶列表 = [str(x) for x in (元数据.get("pinned") or []) if str(x or "").strip()]
    恢复数 = 0
    最大序号 = 0
    # 置顶/备注/昵称里出现的会话即使没有消息也要恢复，保证置顶会话不丢
    元数据会话: set[str] = set()
    for 键 in ("pinned", "remarks", "nicknames"):
        值 = 元数据.get(键)
        if isinstance(值, dict):
            for 会话 in 值:
                元数据会话.add(str(会话 or "").strip())
        elif isinstance(值, list):
            for 会话 in 值:
                元数据会话.add(str(会话 or "").strip())
    for 会话标识 in set(会话标识列表) | 元数据会话:
        会话标识 = str(会话标识 or "").strip()
        if not 会话标识 or 会话标识 in 消息缓存:
            continue
        消息列表 = []
        try:
            消息列表 = _消息存储.读取会话消息(会话标识, 每会话最大消息数) or []
        except Exception as exc:
            logger.debug("消息记录会话恢复失败：错误类型=%s", type(exc).__name__)
        类型 = "group"
        appid = ""
        if 消息列表:
            类型 = str(消息列表[-1].get("chat_type") or "group")
            appid = str(消息列表[-1].get("appid") or "")
        elif isinstance(元数据.get("remarks") or {}, dict):
            备注表 = 元数据.get("remarks") or {}
            if 会话标识 in 备注表:
                类型 = "group"
        会话 = _取得会话缓存(会话标识, 类型, appid)
        if 消息列表:
            会话["messages"] = 消息列表
            最后 = 消息列表[-1]
            会话["last_content"] = str(最后.get("content") or "")
            会话["last_nickname"] = str(最后.get("nickname") or "")
            会话["last_ts"] = int(最后.get("ts") or 0)
            for 记录 in 消息列表:
                最大序号 = max(最大序号, int(记录.get("id") or 0))
            恢复数 += 1
        elif 会话标识 in 置顶列表:
            # 无消息但被置顶的会话：保留占位以便显示置顶
            恢复数 += 1
    global 发送序号
    if 最大序号 > 发送序号:
        发送序号 = 最大序号
    if 恢复数:
        logger.info("消息记录数据库恢复会话：数量=%s", 恢复数)
