from __future__ import annotations

import asyncio
import ast
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import html
import json
import os
import random
import re
import threading
import time
from datetime import datetime as _日期类
from datetime import timedelta as _时间差
from datetime import timezone as _时区类
from pathlib import Path
from typing import Any
from urllib.parse import quote as _网址编码
from urllib.parse import urlsplit as _解析网址

try:
    from aiohttp import ClientSession, ClientTimeout
except Exception:
    ClientSession = None
    ClientTimeout = None

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
# 群基本信息接口限制为 30 QPM；后台按群串行请求，每个群至少一小时更新一次。
群信息刷新间隔秒 = 60 * 60
群信息限流冷却秒 = 30 * 60
群信息默认失败冷却秒 = 60 * 60
群信息请求间隔秒 = 3.0
群信息人工最短间隔秒 = 60
群信息轮询检查间隔秒 = 60.0
群机器人状态命名空间 = "qq_group_membership"
# 官方 bot_state 限制为 30 QPM；半小时复核一次，避免已退出群长期显示为正常。
群机器人状态缓存有效期秒 = 30 * 60
未读状态命名空间 = "msg_console_unread"
当前插件上下文: Any = globals().get("当前插件上下文")
当前插件配置: Any = globals().get("当前插件配置")
自己发送消息ID: dict[str, float] = globals().get("自己发送消息ID") or {}
消息缓存: dict[str, dict[str, Any]] = globals().get("消息缓存") or {}
群信息缓存: dict[str, dict[str, Any]] = globals().get("群信息缓存") or {}
群机器人状态缓存: dict[str, dict[str, Any]] = globals().get("群机器人状态缓存") or {}
群禁言状态缓存: dict[tuple[str, str], dict[str, Any]] = globals().get("群禁言状态缓存") or {}
群禁言状态缓存有效期秒 = 30
群禁言状态失败冷却秒 = 60
_群禁言状态请求锁 = globals().get("_群禁言状态请求锁") or asyncio.Lock()
已撤回消息待同步: dict[tuple[str, str], float] = globals().get("已撤回消息待同步") or {}
群信息待刷新: set[str] = globals().get("群信息待刷新") or set()
_群信息刷新锁 = globals().get("_群信息刷新锁") or asyncio.Lock()
_群信息刷新任务: asyncio.Task[Any] | None = globals().get("_群信息刷新任务")
_群信息轮询任务: asyncio.Task[Any] | None = globals().get("_群信息轮询任务")
_数据库写入锁 = globals().get("_数据库写入锁") or asyncio.Lock()
_元数据写入锁 = globals().get("_元数据写入锁") or threading.RLock()
_后台写入任务: set[asyncio.Task[Any]] = globals().get("_后台写入任务") or set()
_消息记录执行器: ThreadPoolExecutor | None = globals().get("_消息记录执行器")
_消息记录执行器锁 = threading.Lock()
_未读待写: dict[str, int] = globals().get("_未读待写") or {}
_消息持久化队列上限 = 50000
_消息持久化批量大小 = 200
_消息持久化聚合秒数 = 0.05
_消息持久化最大重试次数 = 3
_消息持久化重试等待秒 = 0.5
_消息持久化队列: asyncio.Queue[tuple[str, Any]] = (
    globals().get("_消息持久化队列") or asyncio.Queue(maxsize=_消息持久化队列上限)
)
_消息持久化任务: asyncio.Task[Any] | None = globals().get("_消息持久化任务")
_消息持久化接收入队 = globals().get("_消息持久化接收入队", True)
_消息持久化溢出数 = int(globals().get("_消息持久化溢出数", 0) or 0)
机器人资料缓存: dict[str, tuple[float, dict[str, str]]] = globals().get("机器人资料缓存") or {}
机器人资料缓存秒数 = 6 * 60 * 60
_数据库裁剪进行中 = globals().get("_数据库裁剪进行中", False)
_上次数据库裁剪排队时间 = float(globals().get("_上次数据库裁剪排队时间", 0.0) or 0.0)
_数据库裁剪最短间隔 = 300.0
_消息缓存总数缓存 = int(globals().get("_消息缓存总数缓存", 0) or 0)
_消息缓存总数检查时间 = float(globals().get("_消息缓存总数检查时间", 0.0) or 0.0)
_消息缓存总数检查间隔 = 0.5
_消息数据库配置缓存: bool | None = globals().get("_消息数据库配置缓存")
_消息数据库配置缓存时间 = float(
    globals().get("_消息数据库配置缓存时间", 0.0) or 0.0
)
_消息数据库配置缓存间隔 = 2.0
_消息接收队列上限 = 4096
_消息接收队列: asyncio.Queue[tuple[Any, Any, str]] = (
    globals().get("_消息接收队列") or asyncio.Queue(maxsize=_消息接收队列上限)
)
_消息接收任务: asyncio.Task[Any] | None = globals().get("_消息接收任务")
_消息接收入队 = globals().get("_消息接收入队", True)
_消息接收溢出数 = int(globals().get("_消息接收溢出数", 0) or 0)
_昵称补查队列上限 = 1024
_昵称补查工作数 = 2
_昵称补查队列: asyncio.Queue[tuple[str, str, str]] = (
    globals().get("_昵称补查队列") or asyncio.Queue(maxsize=_昵称补查队列上限)
)
_昵称补查任务: list[asyncio.Task[Any]] = list(globals().get("_昵称补查任务") or [])
_昵称补查等待中: set[tuple[str, str]] = globals().get("_昵称补查等待中") or set()
_昵称补查接收入队 = globals().get("_昵称补查接收入队", True)
_昵称补查溢出数 = int(globals().get("_昵称补查溢出数", 0) or 0)
_消息事件订阅: dict[asyncio.Queue[Any], asyncio.AbstractEventLoop] = globals().get("_消息事件订阅") or {}
_消息事件队列上限 = 512
成员资料缓存: dict[str, dict[str, dict[str, Any]]] = globals().get("成员资料缓存") or {}
成员资料每会话上限 = 2000
发送序号 = globals().get("发送序号") or 0
_挂钩已安装 = globals().get("_挂钩已安装", False)
_消息事件挂钩版本 = int(globals().get("_消息事件挂钩版本", 0) or 0)
_消息撤回事件挂钩版本 = int(globals().get("_消息撤回事件挂钩版本", 0) or 0)
_发送挂钩已安装 = globals().get("_发送挂钩已安装", False)
主动消息权限缓存: dict[str, tuple[str, float]] = globals().get("主动消息权限缓存") or {}
主动消息权限缓存有效期秒 = 30 * 60

_OPENID规则 = re.compile(r"^[A-Za-z0-9_-]{5,128}$")
_提及规则 = re.compile(r"<@!?([A-Za-z0-9_-]{5,128})>")
_媒体占位规则 = re.compile(
    r"\[(图片|语音|视频|文件|媒体|media)]\s*((?:https?:)?//[^\s<>]+)",
    re.IGNORECASE,
)
_QQ图片域名 = re.compile(
    r"(?:https?://)?[^>\s]*(?:multimedia\.nt\.qq\.com\.cn|qqbot\.ugcimg\.cn|gchat\.qpic\.cn)[^>\s]*"
)
_显示时区 = _时区类(_时间差(hours=8))


def _读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名, 默认值)
    return getattr(对象, 字段名, 默认值)


def _主动消息权限键(会话标识: str, 会话类型: str = "") -> str:
    类型 = "user" if str(会话类型 or "").strip().lower() == "user" else "group"
    return f"{类型}:{str(会话标识 or '').strip()}"


def 记录主动消息权限(会话标识: str, 会话类型: str, 允许: bool) -> None:
    """记录最近一次主动消息结果，避免反复请求已确认无权限的会话。"""
    键 = _主动消息权限键(会话标识, 会话类型)
    if 键.endswith(":"):
        return
    主动消息权限缓存[键] = ("allowed" if 允许 else "denied", time.time())


def 主动消息是否允许(会话标识: str, 会话类型: str) -> bool | None:
    """返回已知主动消息权限；未知时返回 None。

    群状态接口返回的权限优先于发送结果缓存，避免在已明确禁止主动推送
    时仍尝试调用发送接口。实际查询由异步 ``查询群主动消息权限`` 完成。
    """
    if str(会话类型 or "").strip().lower() == "group":
        读取状态 = globals().get("_读取群机器人状态")
        if callable(读取状态):
            try:
                状态 = 读取状态(会话标识)
            except Exception:
                状态 = {}
            if isinstance(状态, dict):
                if str(状态.get("status") or "").strip().lower() == "removed":
                    return False
                明确权限 = 状态.get("allow_proactive_msg")
                if isinstance(明确权限, bool):
                    return 明确权限
    键 = _主动消息权限键(会话标识, 会话类型)
    项 = 主动消息权限缓存.get(键)
    if not 项:
        return None
    状态, 时间戳 = 项
    if time.time() - float(时间戳 or 0) >= 主动消息权限缓存有效期秒:
        主动消息权限缓存.pop(键, None)
        return None
    return 状态 == "allowed"


def 清除主动消息权限(会话标识: str, 会话类型: str = "") -> None:
    """收到新消息后清除旧的拒绝结果，允许下一次重新探测。"""
    主动消息权限缓存.pop(_主动消息权限键(会话标识, 会话类型), None)


def 主动消息无权限(异常: Any) -> bool:
    """识别 QQ 官方发送接口返回的主动消息权限错误。"""
    文本 = str(异常 or "").lower()
    return any(
        关键词 in 文本
        for 关键词 in (
            "主动消息失败",
            "主动发送失败",
            "主动消息无权限",
            "主动发送无权限",
            "40034105",
            "no permission",
            "not allowed",
        )
    )


def 被动消息ID已过期(异常: Any) -> bool:
    """只识别官方明确的被动消息 ID 失效，避免未知错误触发重复重发。"""
    文本 = str(异常 or "").lower()
    return (
        (
            any(关键词 in 文本 for 关键词 in ("过期", "expired", "timeout"))
            and any(
                关键词 in 文本
                for 关键词 in ("msg_id", "msgid", "消息id", "消息 id")
            )
        )
        or any(关键词 in 文本 for 关键词 in ("40034005", "40034006", "msg_id已过期"))
    )


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
            日期值 = 时间戳
            if getattr(日期值, "tzinfo", None) is None:
                日期值 = 日期值.replace(tzinfo=_显示时区)
            return int(日期值.timestamp())
        except Exception:
            return None
    文本 = str(时间戳).strip()
    if not 文本:
        return None
    try:
        if len(文本) >= 10 and 文本[4] == "-" and 文本[7] == "-":
            解析 = _日期类.fromisoformat(文本.replace("Z", "+00:00"))
            if 解析.tzinfo is None:
                # 数据库存储的无时区文本统一视为控制台显示时区，而不是服务器系统时区。
                解析 = 解析.replace(tzinfo=_显示时区)
            return int(解析.timestamp())
    except (ValueError, TypeError, OverflowError):
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
        return _日期类.fromtimestamp(数值, _显示时区).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OverflowError, OSError):
        return ""


def _提取发送响应字段(响应: Any, *字段名: str) -> Any:
    """兼容 qq-botpy 的对象、字典及嵌套 data 响应。"""
    候选 = [响应]
    if isinstance(响应, dict):
        候选.append(响应.get("data"))
    else:
        候选.append(getattr(响应, "data", None))
    for 对象 in 候选:
        if 对象 is None:
            continue
        for 名称 in 字段名:
            值 = 对象.get(名称) if isinstance(对象, dict) else getattr(对象, 名称, None)
            if 值 not in (None, ""):
                return 值
    return None


def _提取发送响应消息ID(响应: Any) -> str:
    return str(_提取发送响应字段(响应, "id", "message_id") or "").strip()


def _提取发送响应时间(响应: Any) -> int | None:
    return _转数字时间戳(
        _提取发送响应字段(响应, "timestamp", "time", "created_at")
    )


def _提取发送响应REFIDX(响应: Any) -> str:
    """读取 QQ 官方发送响应中的 ext_info.ref_idx，用于引用机器人消息。"""
    扩展 = _提取发送响应字段(响应, "ext_info")
    return str(_读取字段(扩展, "ref_idx") or _读取字段(扩展, "refidx") or "").strip()


def _提取原始消息时间(原始消息: Any) -> Any:
    """从历史消息的 JSON/字典文本取出 QQ 官方原始 timestamp。"""
    数据 = 原始消息
    if isinstance(数据, str):
        文本 = 数据.strip()
        if not 文本:
            return None
        for 解析器 in (json.loads, ast.literal_eval):
            try:
                候选 = 解析器(文本)
                if isinstance(候选, dict):
                    数据 = 候选
                    break
            except Exception:
                continue
        # 会话列表只读取原始消息尾部摘要；摘要不是完整 JSON 时，
        # 直接从 timestamp/time/created_at 字段提取值，继续修正旧记录时区。
        if isinstance(数据, str):
            匹配 = re.search(
                r"(?:['\"])?(?:timestamp|time|created_at)(?:['\"])?\s*:\s*"
                r"(?:['\"]([^'\"]+)['\"]|([^,}\s]+))",
                文本,
                re.IGNORECASE,
            )
            if 匹配:
                return 匹配.group(1) or 匹配.group(2)
    if not isinstance(数据, dict):
        return None
    for 字段 in ("timestamp", "time", "created_at"):
        值 = 数据.get(字段)
        if 值 not in (None, ""):
            return 值
    return None


def _规范化历史消息(记录: dict[str, Any]) -> dict[str, Any]:
    """修复旧记录的时区和来源标记，保证历史排序与新消息一致。"""
    if isinstance(记录, dict):
        记录["message_id"] = _规范消息ID(记录.get("message_id"))
    来源 = str(记录.get("source") or "")
    if 来源.startswith("bot_") or 来源 == "web_panel":
        记录["is_self"] = True
        if not str(记录.get("nickname") or "").strip():
            记录["nickname"] = "机器人" if 来源.startswith("bot_") else "我"
    原始消息 = _解析消息结构(记录.get("raw_message"))
    _更新消息提及资料(记录, 原始消息 or 记录.get("raw_message"))
    会话标识 = str(记录.get("_session") or "").strip()
    作者标识 = str(记录.get("user_id") or "").strip()
    作者昵称 = str(记录.get("nickname") or "").strip()
    作者头像 = _提取成员头像(原始消息 or 记录.get("raw_message")) or str(
        记录.get("avatar") or ""
    ).strip()
    if 作者头像:
        记录["avatar"] = 作者头像
    if (
        会话标识
        and 作者标识
        and (
            (作者昵称 and 作者昵称 not in {"未知用户", "未知"})
            or bool(作者头像)
        )
    ):
        _记录成员资料(
            会话标识,
            作者标识,
            作者昵称,
            bool(记录.get("is_self")),
            头像=作者头像,
        )
    原始时间 = _转数字时间戳(_提取原始消息时间(记录.get("raw_message")))
    try:
        记录时间 = int(记录.get("ts") or 0)
    except (TypeError, ValueError):
        记录时间 = 0
    标准时间 = 原始时间 or 记录时间 or _转数字时间戳(记录.get("timestamp"))
    if 标准时间:
        记录["ts"] = 标准时间
        记录["timestamp"] = _格式化时间戳(标准时间)
    现有媒体 = 记录.get("media")
    现有地址 = (
        str(现有媒体.get("src") or "").strip()
        if isinstance(现有媒体, dict)
        else ""
    )
    if not 现有地址:
        补充媒体 = _提取媒体字段(str(记录.get("content") or ""), 原始消息)
        if 补充媒体:
            if isinstance(现有媒体, dict):
                合并媒体 = dict(现有媒体)
                合并媒体.update({k: v for k, v in 补充媒体.items() if v not in (None, "")})
                记录["media"] = 合并媒体
            else:
                记录["media"] = 补充媒体
    return 记录


def _规范化聊天摘要(记录: dict[str, Any]) -> dict[str, Any]:
    """只归一化会话列表摘要的时间和来源，不解析完整媒体/正文。"""
    if not isinstance(记录, dict):
        return {}
    来源 = str(记录.get("source") or "")
    if 来源.startswith("bot_") or 来源 == "web_panel":
        记录["is_self"] = True
        if not str(记录.get("nickname") or "").strip():
            记录["nickname"] = "机器人" if 来源.startswith("bot_") else "我"
    原始消息 = _解析消息结构(记录.get("raw_message"))
    _更新消息提及资料(记录, 原始消息 or 记录.get("raw_message"))
    会话标识 = str(记录.get("_session") or "").strip()
    作者标识 = str(记录.get("user_id") or "").strip()
    作者昵称 = str(记录.get("nickname") or "").strip()
    作者头像 = _提取成员头像(原始消息 or 记录.get("raw_message")) or str(
        记录.get("avatar") or ""
    ).strip()
    if 作者头像:
        记录["avatar"] = 作者头像
    if (
        会话标识
        and 作者标识
        and (
            (作者昵称 and 作者昵称 not in {"未知用户", "未知"})
            or bool(作者头像)
        )
    ):
        _记录成员资料(
            会话标识,
            作者标识,
            作者昵称,
            bool(记录.get("is_self")),
            头像=作者头像,
        )
    原始时间 = _转数字时间戳(_提取原始消息时间(记录.get("raw_message")))
    try:
        记录时间 = int(记录.get("ts") or 0)
    except (TypeError, ValueError):
        记录时间 = 0
    标准时间 = 原始时间 or 记录时间 or _转数字时间戳(记录.get("timestamp"))
    if 标准时间:
        记录["ts"] = 标准时间
        记录["timestamp"] = _格式化时间戳(标准时间)
    return 记录


def _历史消息排序键(记录: dict[str, Any]) -> tuple[int, int, str]:
    # 调用方在排序前已经完成规范化；这里仅取排序字段，避免每次比较都重复解析 raw_message。
    try:
        消息序号 = int(记录.get("id") or 0)
    except (TypeError, ValueError):
        消息序号 = 0
    return int(记录.get("ts") or 0), 消息序号, _规范消息ID(记录.get("message_id"))


def _规范消息ID(值: Any) -> str:
    """统一消息 ID 的空白表示，兼容旧记录和不同适配器字段。"""
    return str(值 or "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "").strip()


def _提取消息ID(消息: Any) -> str:
    """从官方消息对象及其原始负载读取同一条消息的 ID。"""
    待检查 = [消息]
    for 字段 in ("raw_data", "data", "payload"):
        值 = _读取字段(消息, 字段)
        if 值 not in (None, ""):
            待检查.append(值)
    for 对象 in 待检查:
        结构 = _解析消息结构(对象)
        if 结构 is not None:
            对象 = 结构
        for 字段 in ("id", "message_id", "messageId"):
            值 = _规范消息ID(_读取字段(对象, 字段))
            if 值:
                return 值
    return ""


def _消息去重键(记录: dict[str, Any]) -> tuple[str, ...]:
    """返回消息主键及官方原始事件键，避免双回调造成重复显示。"""
    if not isinstance(记录, dict):
        return ()
    键: list[str] = []
    消息ID = _规范消息ID(记录.get("message_id"))
    if 消息ID:
        键.append(f"id:{消息ID}")
    # 同一网关负载在全量/At 两条回调路径中可能携带不同的适配器字段，
    # 但 raw_message 完全一致；只对官方接收事件使用该高置信度键。
    if str(记录.get("source") or "").strip().lower() == "qq_official":
        原始 = str(记录.get("raw_message") or "").strip()
        if 原始:
            try:
                摘要 = hashlib.sha1(原始.encode("utf-8", errors="ignore")).hexdigest()
            except Exception:
                摘要 = 原始[:512]
            键.append(f"raw:{摘要}")
    return tuple(键)


def _消息记录重复(已有记录: dict[str, Any], 新记录: dict[str, Any]) -> bool:
    旧键 = set(_消息去重键(已有记录))
    新键 = set(_消息去重键(新记录))
    return bool(旧键 and 新键 and 旧键.intersection(新键))


def _整数时间戳(值: Any) -> int:
    """读取记录时间，异常值统一按 0 处理。"""
    try:
        return int(值 or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _消息媒体指纹(媒体: Any) -> str:
    if not isinstance(媒体, dict) or not 媒体:
        return ""
    try:
        return json.dumps(媒体, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        return str(媒体)


def _查找机器人回显记录(
    会话: dict[str, Any],
    消息ID: str,
    内容: str,
    时间戳: Any,
) -> dict[str, Any] | None:
    """补齐发送响应缺少消息 ID 时的官方回显，避免再显示一条机器人消息。

    只有最近几秒内、内容完全相同且原记录确实来自机器人发送入口时才合并，
    普通成员消息不会因为文本相同而被吞掉。
    """
    if not str(内容 or "").strip():
        return None
    当前时间 = _整数时间戳(时间戳) or int(time.time())
    for 记录 in reversed(会话.get("messages") or []):
        if not isinstance(记录, dict) or not 记录.get("is_self"):
            continue
        来源 = str(记录.get("source") or "").strip().lower()
        if not (来源.startswith("bot_") or 来源 == "web_panel"):
            continue
        旧ID = _规范消息ID(记录.get("message_id"))
        if 消息ID and 旧ID and 消息ID != 旧ID:
            continue
        if str(记录.get("content") or "").strip() != str(内容 or "").strip():
            continue
        if abs(当前时间 - _整数时间戳(记录.get("ts"))) > 8:
            continue
        return 记录
    return None


def _查找重复机器人发送(
    会话: dict[str, Any],
    类型: str,
    内容: str,
    媒体: dict[str, Any] | None,
    时间戳: int,
    来源: str,
    消息ID: str = "",
) -> dict[str, Any] | None:
    """合并事件发送/会话发送挂钩的无 ID 重复记账。"""
    来源 = str(来源 or "").strip().lower()
    if not (来源.startswith("bot_") or 来源 == "web_panel"):
        return None
    新媒体指纹 = _消息媒体指纹(媒体)
    for 记录 in reversed(会话.get("messages") or []):
        if not isinstance(记录, dict) or not 记录.get("is_self"):
            continue
        旧来源 = str(记录.get("source") or "").strip().lower()
        if not (旧来源.startswith("bot_") or 旧来源 == "web_panel") or 旧来源 == 来源:
            continue
        旧ID = _规范消息ID(记录.get("message_id"))
        if 消息ID and 旧ID and 消息ID != 旧ID:
            continue
        if str(记录.get("chat_type") or 类型).strip().lower() != str(类型 or "").strip().lower():
            continue
        if str(记录.get("content") or "").strip() != str(内容 or "").strip():
            continue
        if _消息媒体指纹(记录.get("media")) != 新媒体指纹:
            continue
        if abs(int(时间戳 or 0) - _整数时间戳(记录.get("ts"))) > 5:
            continue
        return 记录
    return None


def _合并重复消息(已有记录: dict[str, Any], 新记录: dict[str, Any]) -> dict[str, Any]:
    """合并同一 message_id 的重复事件，保留较完整的消息资料。"""
    if not isinstance(已有记录, dict) or not isinstance(新记录, dict):
        return 已有记录
    新消息ID = _规范消息ID(新记录.get("message_id"))
    旧消息ID = _规范消息ID(已有记录.get("message_id"))
    if 旧消息ID:
        已有记录["message_id"] = 旧消息ID
    elif 新消息ID:
        已有记录["message_id"] = 新消息ID
    for 字段 in (
        "user_id", "nickname", "content", "timestamp", "source", "raw_message",
        "reference_id", "refidx", "avatar", "chat_type", "appid",
    ):
        新值 = 新记录.get(字段)
        if 新值 not in (None, "") and 已有记录.get(字段) in (None, ""):
            已有记录[字段] = 新值
    旧媒体 = 已有记录.get("media")
    新媒体 = 新记录.get("media")
    if isinstance(新媒体, dict) and 新媒体:
        if not isinstance(旧媒体, dict) or not 旧媒体.get("src"):
            已有记录["media"] = dict(新媒体)
        else:
            for 字段 in (
                "text", "name", "content_type", "size", "width", "height",
                "before_text", "after_text",
            ):
                if 新媒体.get(字段) not in (None, "") and not 旧媒体.get(字段):
                    旧媒体[字段] = 新媒体[字段]
    已有记录["is_self"] = bool(已有记录.get("is_self") or 新记录.get("is_self"))
    已有记录["recalled"] = bool(已有记录.get("recalled") or 新记录.get("recalled"))
    try:
        已有记录["ts"] = max(int(已有记录.get("ts") or 0), int(新记录.get("ts") or 0))
    except (TypeError, ValueError):
        pass
    return 已有记录


def _去重消息列表(消息列表: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """按消息 ID 或同一官方原始事件去重，兼容修复前已经落库的重复记录。"""
    结果: list[dict[str, Any]] = []
    索引: dict[str, int] = {}
    for 消息 in 消息列表 or []:
        if not isinstance(消息, dict):
            continue
        去重键 = _消息去重键(消息)
        if not 去重键:
            结果.append(消息)
            continue
        已有位置 = next((索引.get(键) for 键 in 去重键 if 键 in 索引), None)
        if 已有位置 is None:
            for 键 in 去重键:
                索引[键] = len(结果)
            结果.append(消息)
        else:
            _合并重复消息(结果[已有位置], 消息)
            for 键 in 去重键:
                索引[键] = 已有位置
    return 结果


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
            # 启动时只恢复会话骨架；完整历史在打开会话或滚动到顶部时按页读取。
            "msg_count": 0,
            "last_ts": 0,
            "last_content": "",
            "last_nickname": "",
            # 接收事件不能在 AstrBot 事件循环中同步查询 MySQL；启动恢复时
            # 会一次性载入持久化未读数，新会话则从当前事件开始累计。
            "unread": max(0, int(_未读待写.get(会话标识, 0) or 0)),
        }
    return 消息缓存[会话标识]


def _读取持久化未读数(会话标识: str) -> int:
    """从 MySQL 读取会话未读数，未配置数据库或异常时返回 0。"""
    if not 会话标识:
        return 0
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import (
            已配置运行状态数据库,
            读取运行状态值,
        )

        if not 已配置运行状态数据库(当前插件配置):
            return 0
        文本 = 读取运行状态值(
            当前插件配置, 未读状态命名空间, str(会话标识), "0"
        )
        return max(0, int(文本 or 0))
    except Exception as 异常:
        logger.debug("消息记录未读数读取失败：错误类型=%s", type(异常).__name__)
        return 0


def _读取全部持久化未读数() -> dict[str, int]:
    """一次性读取全部会话未读数，避免聊天列表聚合时逐会话查库。"""
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import (
            已配置运行状态数据库,
            读取运行状态命名空间,
        )

        if not 已配置运行状态数据库(当前插件配置):
            return {}
        原始 = 读取运行状态命名空间(当前插件配置, 未读状态命名空间) or {}
        结果 = {
            str(会话): max(0, int(值 or 0))
            for 会话, 值 in 原始.items()
            if str(会话 or "").strip()
        }
        # 同一进程内最新状态可能仍在写库队列中，优先使用待写值，避免旧值回显。
        结果.update({str(会话): max(0, int(值 or 0)) for 会话, 值 in _未读待写.items()})
        return 结果
    except Exception as 异常:
        logger.debug("消息记录未读数批量读取失败：错误类型=%s", type(异常).__name__)
        return {}


def _获取消息记录执行器() -> ThreadPoolExecutor:
    """为消息记录数据库操作提供独立线程池，避免占用小说下载线程。"""
    global _消息记录执行器
    with _消息记录执行器锁:
        if _消息记录执行器 is None or getattr(_消息记录执行器, "_shutdown", False):
            _消息记录执行器 = ThreadPoolExecutor(
                max_workers=max(2, min(4, (os.cpu_count() or 4) // 2 or 2)),
                thread_name_prefix="mantou-message-db",
            )
        return _消息记录执行器


async def _异步执行消息记录同步(操作: Any, *参数: Any) -> Any:
    """在线程池执行可能阻塞的消息记录数据库操作。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _获取消息记录执行器(),
        partial(操作, *参数),
    )


def 关闭消息记录执行器() -> None:
    """停止消息记录专用线程池，供插件重载时释放资源。"""
    global _消息记录执行器
    with _消息记录执行器锁:
        执行器 = _消息记录执行器
        _消息记录执行器 = None
    if 执行器 is not None:
        执行器.shutdown(wait=False, cancel_futures=True)


def _消息数据库已配置() -> bool:
    """只判断消息记录是否需要落库，未配置数据库时不启动持久化队列。"""
    global _消息数据库配置缓存, _消息数据库配置缓存时间
    if _消息存储 is None:
        return False
    当前时间 = time.monotonic()
    if (
        _消息数据库配置缓存 is not None
        and 当前时间 - _消息数据库配置缓存时间 < _消息数据库配置缓存间隔
    ):
        return _消息数据库配置缓存
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 已配置运行状态数据库

        _消息数据库配置缓存 = bool(已配置运行状态数据库(当前插件配置))
    except Exception:
        _消息数据库配置缓存 = False
    _消息数据库配置缓存时间 = 当前时间
    return _消息数据库配置缓存


def _后台执行同步(操作: Any, *参数: Any) -> asyncio.Task[Any] | None:
    """把可能阻塞的数据库操作移出 AstrBot 事件循环并登记，便于重载前等待。"""
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        try:
            操作(*参数)
        except Exception as 异常:
            logger.debug("消息记录后台数据库操作失败：错误类型=%s", type(异常).__name__)
        return None

    async def _执行() -> Any:
        try:
            # 所有后台写库共用一个锁，避免并发 INSERT 按完成先后乱序。
            async with _数据库写入锁:
                return await _异步执行消息记录同步(操作, *参数)
        except Exception as 异常:
            logger.debug("消息记录后台数据库操作失败：错误类型=%s", type(异常).__name__)
            return None

    任务 = 循环.create_task(_执行())
    _后台写入任务.add(任务)
    任务.add_done_callback(_后台写入任务.discard)
    return 任务


def _执行消息持久化批次(项目列表: list[tuple[str, Any]]) -> bool:
    """在线程中批量落库；同一会话的未读值只写本批最后一次状态。"""
    消息列表: list[dict[str, Any]] = []
    未读表: dict[str, int] = {}
    for 类型, 数据 in 项目列表:
        if 类型 == "message" and isinstance(数据, dict):
            消息列表.append(数据)
        elif 类型 == "unread" and isinstance(数据, tuple) and len(数据) == 2:
            会话标识, 未读数 = 数据
            未读表[str(会话标识)] = max(0, int(未读数 or 0))

    成功 = True
    if 消息列表:
        if _消息存储 is None:
            成功 = False
        else:
            try:
                批量写入 = getattr(_消息存储, "批量写入消息", None)
                if callable(批量写入):
                    if 批量写入(消息列表) is False:
                        成功 = False
                else:
                    for 记录 in 消息列表:
                        if _消息存储.写入消息(记录) is False:
                            成功 = False
            except Exception as 异常:
                logger.debug("消息记录消息批量持久化失败：错误类型=%s", type(异常).__name__)
                成功 = False

    if not 未读表:
        return 成功
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        if not 运行状态数据库.已配置运行状态数据库(当前插件配置):
            return 成功
        批量写入 = getattr(运行状态数据库, "批量写入运行状态值", None)
        if callable(批量写入):
            批量写入(
                当前插件配置,
                未读状态命名空间,
                未读表,
            )
            return 成功
        写入运行状态值 = 运行状态数据库.写入运行状态值
        for 会话标识, 未读数 in 未读表.items():
            写入运行状态值(当前插件配置, 未读状态命名空间, 会话标识, 未读数)
    except Exception as 异常:
        logger.debug("消息记录未读数批量持久化失败：错误类型=%s", type(异常).__name__)
        成功 = False
    return 成功


def _准备消息持久化队列() -> asyncio.Queue[tuple[str, Any]]:
    """确保队列属于当前事件循环；仅在旧循环已结束且队列为空时重建。"""
    global _消息持久化队列
    try:
        当前循环 = asyncio.get_running_loop()
    except RuntimeError:
        return _消息持久化队列
    队列循环 = getattr(_消息持久化队列, "_loop", None)
    任务运行中 = _消息持久化任务 is not None and not _消息持久化任务.done()
    if 队列循环 not in (None, 当前循环) and _消息持久化队列.empty() and not 任务运行中:
        _消息持久化队列 = asyncio.Queue(maxsize=_消息持久化队列上限)
    return _消息持久化队列


async def _消息持久化工作() -> None:
    """固定单消费者按时间窗聚合消息，避免每条消息创建一个后台任务。"""
    global _消息持久化任务
    队列 = _准备消息持久化队列()
    try:
        while True:
            首项 = await 队列.get()
            批次 = [首项]
            截止时间 = asyncio.get_running_loop().time() + _消息持久化聚合秒数
            while len(批次) < _消息持久化批量大小:
                try:
                    批次.append(队列.get_nowait())
                    continue
                except asyncio.QueueEmpty:
                    剩余时间 = 截止时间 - asyncio.get_running_loop().time()
                    if 剩余时间 <= 0:
                        break
                try:
                    批次.append(await asyncio.wait_for(队列.get(), timeout=剩余时间))
                except TimeoutError:
                    break
            # 消息和未读状态分开重试。未读状态失败时不重复 INSERT 已提交的
            # 无 message_id 消息，避免网络抖动造成历史记录再次出现。
            try:
                for 项目类型 in ("message", "unread"):
                    子批次 = [项目 for 项目 in 批次 if 项目[0] == 项目类型]
                    if not 子批次:
                        continue
                    写入成功 = False
                    最后错误类型 = ""
                    for 重试次数 in range(_消息持久化最大重试次数):
                        try:
                            async with _数据库写入锁:
                                结果 = await _异步执行消息记录同步(
                                    _执行消息持久化批次,
                                    子批次,
                                )
                            写入成功 = 结果 is not False
                        except asyncio.CancelledError:
                            raise
                        except Exception as 异常:
                            最后错误类型 = type(异常).__name__
                        if 写入成功:
                            break
                        if 重试次数 + 1 < _消息持久化最大重试次数:
                            await asyncio.sleep(_消息持久化重试等待秒 * (重试次数 + 1))
                    if not 写入成功:
                        logger.warning(
                            "消息记录后台批量写入失败：类型=%s，数量=%d，重试次数=%d，错误类型=%s",
                            项目类型,
                            len(子批次),
                            _消息持久化最大重试次数,
                            最后错误类型 or "写入返回失败",
                        )
            finally:
                for _ in 批次:
                    队列.task_done()
    except asyncio.CancelledError:
        raise
    finally:
        当前任务 = asyncio.current_task()
        if _消息持久化任务 is 当前任务:
            _消息持久化任务 = None


def _启动消息持久化任务() -> asyncio.Task[Any] | None:
    global _消息持久化任务
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return None
    if _消息持久化任务 is None or _消息持久化任务.done():
        _准备消息持久化队列()
        _消息持久化任务 = 循环.create_task(_消息持久化工作())
    return _消息持久化任务


def _排队消息持久化(类型: str, 数据: Any) -> bool:
    """非阻塞投递持久化项目；队列上限与 ElainaBot 日志队列一致。"""
    global _消息持久化溢出数
    if not _消息持久化接收入队:
        return False
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            _执行消息持久化批次([(类型, 数据)])
            return True
        except Exception as 异常:
            logger.debug("消息记录同步持久化失败：错误类型=%s", type(异常).__name__)
            return False
    队列 = _准备消息持久化队列()
    try:
        队列.put_nowait((类型, 数据))
    except asyncio.QueueFull:
        _消息持久化溢出数 += 1
        if _消息持久化溢出数 == 1 or _消息持久化溢出数 % 1000 == 0:
            logger.warning(
                "消息记录持久化队列已满：上限=%d，累计未入队=%d",
                _消息持久化队列上限,
                _消息持久化溢出数,
            )
        return False
    _启动消息持久化任务()
    return True


async def 等待消息记录写入(超时: float = 10.0) -> bool:
    """等待当前已排队的消息/未读/元数据写入，供网页操作和插件停机调用。"""
    截止时间 = asyncio.get_running_loop().time() + max(0.1, float(超时))
    队列 = _准备消息持久化队列()
    if not 队列.empty():
        _启动消息持久化任务()
    try:
        剩余时间 = max(0.01, 截止时间 - asyncio.get_running_loop().time())
        await asyncio.wait_for(队列.join(), timeout=剩余时间)
    except TimeoutError:
        logger.warning("消息记录持久化队列未在限定时间内冲刷：剩余=%d", 队列.qsize())
        return False
    except Exception as 异常:
        logger.warning("消息记录持久化队列等待失败：错误类型=%s", type(异常).__name__)
        return False
    任务列表 = [任务 for 任务 in list(_后台写入任务) if not 任务.done()]
    if not 任务列表:
        return True
    try:
        剩余时间 = max(0.01, 截止时间 - asyncio.get_running_loop().time())
        _, 未完成 = await asyncio.wait(任务列表, timeout=剩余时间)
        if 未完成:
            logger.warning("消息记录后台写入未在限定时间内完成：剩余=%d", len(未完成))
            return False
        return True
    except Exception as 异常:
        logger.warning("消息记录后台写入等待失败：错误类型=%s", type(异常).__name__)
        return False


async def 停止消息记录() -> bool:
    """插件重载/退出前按接收、昵称、持久化顺序冲刷，避免最后消息丢失。"""
    global _消息接收入队, _昵称补查接收入队, _消息持久化接收入队
    global _消息接收任务, _消息持久化任务, _昵称补查任务, _群信息刷新任务
    global _群信息轮询任务
    群信息轮询任务 = _群信息轮询任务
    _群信息轮询任务 = None
    if 群信息轮询任务 is not None and not 群信息轮询任务.done():
        群信息轮询任务.cancel()
        await asyncio.gather(群信息轮询任务, return_exceptions=True)
    群信息任务 = _群信息刷新任务
    _群信息刷新任务 = None
    if 群信息任务 is not None and not 群信息任务.done():
        群信息任务.cancel()
        await asyncio.gather(群信息任务, return_exceptions=True)
    _消息接收入队 = False
    截止时间 = asyncio.get_running_loop().time() + 15.0
    接收队列 = _准备消息接收队列()
    接收冲刷 = True
    try:
        剩余 = max(0.01, 截止时间 - asyncio.get_running_loop().time())
        await asyncio.wait_for(接收队列.join(), timeout=剩余)
    except Exception as 异常:
        接收冲刷 = False
        logger.warning("消息记录接收队列未在限定时间内冲刷：错误类型=%s，剩余=%d", type(异常).__name__, 接收队列.qsize())
    接收任务 = _消息接收任务
    _消息接收任务 = None
    if 接收任务 is not None and not 接收任务.done():
        接收任务.cancel()
        await asyncio.gather(接收任务, return_exceptions=True)

    _昵称补查接收入队 = False
    昵称队列 = _准备昵称补查队列()
    昵称冲刷 = True
    try:
        剩余 = max(0.01, 截止时间 - asyncio.get_running_loop().time())
        await asyncio.wait_for(昵称队列.join(), timeout=剩余)
    except Exception as 异常:
        昵称冲刷 = False
        logger.warning("私聊昵称补查队列未在限定时间内冲刷：错误类型=%s，剩余=%d", type(异常).__name__, 昵称队列.qsize())
    昵称任务列表 = [任务 for 任务 in _昵称补查任务 if not 任务.done()]
    _昵称补查任务 = []
    for 任务 in 昵称任务列表:
        任务.cancel()
    if 昵称任务列表:
        await asyncio.gather(*昵称任务列表, return_exceptions=True)

    _消息持久化接收入队 = False
    剩余 = max(0.01, 截止时间 - asyncio.get_running_loop().time())
    已冲刷 = 接收冲刷 and 昵称冲刷 and await 等待消息记录写入(剩余)
    任务 = _消息持久化任务
    _消息持久化任务 = None
    if 任务 is not None and not 任务.done():
        任务.cancel()
        await asyncio.gather(任务, return_exceptions=True)
    关闭消息记录执行器()
    return 已冲刷


def _持久化未读数(会话标识: str, 未读数: int) -> None:
    """异步写入未读数，避免 MySQL 往返阻塞消息事件循环。"""
    if not 会话标识 or not _消息数据库已配置():
        return
    会话标识 = str(会话标识)
    try:
        _未读待写[会话标识] = max(0, int(未读数))
    except (TypeError, ValueError):
        _未读待写[会话标识] = 0
    _排队消息持久化("unread", (会话标识, _未读待写[会话标识]))


def 订阅消息事件() -> asyncio.Queue[Any] | None:
    """注册网页实时消息订阅；队列有界，慢客户端只丢弃最旧事件。"""
    try:
        循环 = asyncio.get_running_loop()
        队列: asyncio.Queue[Any] = asyncio.Queue(maxsize=_消息事件队列上限)
        _消息事件订阅[队列] = 循环
        return 队列
    except RuntimeError:
        return None


def 取消消息事件订阅(队列: asyncio.Queue[Any] | None) -> None:
    if 队列 is not None:
        _消息事件订阅.pop(队列, None)


def _获取消息相关成员资料(
    会话标识: str,
    消息列表: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, dict[str, Any]]:
    """只复制当前消息页涉及的成员资料，避免把整群资料推到浏览器。"""
    全部资料 = 成员资料缓存.get(str(会话标识 or "").strip()) or {}
    相关标识: set[str] = set()
    for 消息 in 消息列表 or ():
        if not isinstance(消息, dict):
            continue
        作者标识 = str(消息.get("user_id") or "").strip()
        if 作者标识:
            相关标识.add(作者标识)
        相关标识.update(_提及规则.findall(str(消息.get("content") or "")))
    return {
        标识: copy.deepcopy(全部资料[标识])
        for 标识 in 相关标识
        if isinstance(全部资料.get(标识), dict)
    }


def _消息事件载荷(记录: dict[str, Any], 会话: dict[str, Any]) -> dict[str, Any]:
    """构造控制台实时事件，避免把内部会话键和未处理对象直接推到网页。"""
    字段 = (
        "id", "message_id", "user_id", "nickname", "content", "timestamp",
        "is_self", "source", "recalled", "media", "reference_id", "refidx",
        "avatar", "chat_type", "ts", "appid",
    )
    消息 = {字段名: 记录.get(字段名) for 字段名 in 字段}
    会话标识 = str(记录.get("_session") or "")
    成员资料 = _获取消息相关成员资料(会话标识, [记录])
    return {
        "chat_id": 会话标识,
        "chat_type": str(记录.get("chat_type") or 会话.get("chat_type") or "group"),
        "appid": str(记录.get("appid") or 会话.get("appid") or ""),
        "msg_count": max(
            int(会话.get("msg_count") or 0),
            len(会话.get("messages") or []),
        ),
        "unread": max(0, int(会话.get("unread") or 0)),
        "last_content": _替换提及名称(会话.get("last_content") or "", 会话标识),
        "last_nickname": str(会话.get("last_nickname") or ""),
        "last_ts": int(会话.get("last_ts") or 0),
        **_聊天群成员状态(会话标识, str(记录.get("chat_type") or 会话.get("chat_type") or "group")),
        "member_profiles": 成员资料,
        "message": 消息,
    }


def _推送消息事件(记录: dict[str, Any], 会话: dict[str, Any]) -> None:
    """把已进入内存的消息放入网页队列，不等待网络或数据库。"""
    if not _消息事件订阅:
        return
    载荷 = {"type": "message", "data": _消息事件载荷(记录, 会话)}

    def 投递(队列: asyncio.Queue[Any]) -> None:
        try:
            队列.put_nowait(载荷)
        except asyncio.QueueFull:
            try:
                队列.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                队列.put_nowait(载荷)
            except asyncio.QueueFull:
                pass

    try:
        当前循环 = asyncio.get_running_loop()
    except RuntimeError:
        当前循环 = None
    for 队列, 循环 in list(_消息事件订阅.items()):
        if 当前循环 is 循环:
            投递(队列)
        elif 循环.is_closed():
            _消息事件订阅.pop(队列, None)
        else:
            try:
                循环.call_soon_threadsafe(投递, 队列)
            except RuntimeError:
                _消息事件订阅.pop(队列, None)


def _推送群状态事件(会话标识: str, 状态: str) -> None:
    """把群成员状态变化实时推送到网页，避免等待下一次列表轮询。"""
    if not _消息事件订阅:
        return
    载荷 = {
        "type": "group_status",
        "data": {
            "chat_id": str(会话标识 or "").strip(),
            "membership_status": str(状态 or "unknown").strip().lower(),
        },
    }

    def 投递(队列: asyncio.Queue[Any]) -> None:
        try:
            队列.put_nowait(载荷)
        except asyncio.QueueFull:
            try:
                队列.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                队列.put_nowait(载荷)
            except asyncio.QueueFull:
                pass

    try:
        当前循环 = asyncio.get_running_loop()
    except RuntimeError:
        当前循环 = None
    for 队列, 循环 in list(_消息事件订阅.items()):
        if 当前循环 is 循环:
            投递(队列)
        elif 循环.is_closed():
            _消息事件订阅.pop(队列, None)
        else:
            try:
                循环.call_soon_threadsafe(投递, 队列)
            except RuntimeError:
                _消息事件订阅.pop(队列, None)


def _序列化原始消息(消息: Any, 最长: int = 0) -> str:
    """保存官方事件负载，而不是只保存 botpy 对象的精简 ``repr``。

    qq-botpy 的 ``GroupMessage.__repr__`` 不包含 ``author``，而头像等
    非标准扩展字段只存在于适配器保存的 ``raw_data`` 中。优先序列化
    结构化负载，历史分页才能继续解析头像和昵称。
    """
    负载 = 消息
    if not isinstance(负载, (dict, list, tuple)):
        for 字段 in ("raw_data", "data", "payload"):
            值 = _读取字段(消息, 字段)
            if isinstance(值, (dict, list, tuple)):
                负载 = 值
                break
    if isinstance(负载, (dict, list, tuple)):
        try:
            文本 = json.dumps(负载, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            try:
                文本 = str(负载 or "")
            except Exception:
                return ""
    else:
        文本 = ""
        for 方法名 in ("model_dump", "dict"):
            方法 = getattr(负载, 方法名, None)
            if not callable(方法):
                continue
            try:
                结构 = 方法()
                if isinstance(结构, (dict, list, tuple)):
                    文本 = json.dumps(
                        结构,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    break
            except Exception:
                continue
        if not 文本:
            try:
                文本 = str(负载 or "")
            except Exception:
                return ""
    if 最长 > 0 and len(文本) > 最长:
        return 文本[:最长] + "...[已截断]"
    return 文本


def _解析消息结构(对象: Any) -> Any:
    """把 QQ 原始消息、raw_data 或附件对象转为可读取的结构。"""
    if isinstance(对象, (dict, list, tuple)):
        return 对象
    if isinstance(对象, bytes):
        try:
            对象 = 对象.decode("utf-8", errors="ignore")
        except Exception:
            return None
    for 方法名 in ("model_dump", "dict"):
        方法 = getattr(对象, 方法名, None)
        if callable(方法):
            try:
                结果 = 方法()
                if isinstance(结果, (dict, list, tuple)):
                    return 结果
            except Exception:
                pass
    if not isinstance(对象, str):
        return None
    文本 = 对象.strip()
    if not 文本:
        return None
    for 解析器 in (json.loads, ast.literal_eval):
        try:
            结果 = 解析器(文本)
            if isinstance(结果, (dict, list, tuple)):
                return 结果
        except Exception:
            continue
    return None


def _提取消息提及资料(消息: Any) -> dict[str, str]:
    """从 botpy 对象、字典和兼容消息段中提取被提及成员昵称。"""
    if 消息 is None:
        return {}
    结果: dict[str, str] = {}
    待检查: list[tuple[Any, str]] = [(消息, "")]
    已检查: set[int] = set()
    提及字段 = ("mentions", "mention", "at_users", "at_list")
    容器字段 = ("data", "message", "raw_data", "event", "payload")
    标识字段 = ("member_openid", "user_openid", "openid", "user_id", "id")
    名称字段 = ("username", "member_name", "nickname", "user_name", "name", "display_name")

    def 加入子项(值: Any, 标识提示: str = "") -> None:
        if 值 in (None, ""):
            return
        if isinstance(值, dict):
            if any(字段 in 值 for 字段 in (*标识字段, *名称字段)):
                待检查.append((值, 标识提示))
                return
            for 键, 子值 in 值.items():
                键文本 = str(键 or "").strip()
                待检查.append((子值, 键文本 if _OPENID规则.fullmatch(键文本) else 标识提示))
            return
        if isinstance(值, (list, tuple, set)):
            待检查.extend((子值, 标识提示) for 子值 in 值)
            return
        待检查.append((值, 标识提示))

    while 待检查:
        当前, 标识提示 = 待检查.pop()
        结构 = _解析消息结构(当前)
        当前 = 结构 if 结构 is not None else 当前
        if isinstance(当前, (dict, list, tuple)):
            对象键 = id(当前)
            if 对象键 in 已检查:
                continue
            已检查.add(对象键)
        if isinstance(当前, (list, tuple, set)):
            待检查.extend((子项, 标识提示) for 子项 in 当前)
            continue
        标识 = 标识提示
        名称 = ""
        if isinstance(当前, dict):
            for 字段 in 标识字段:
                值 = 当前.get(字段)
                if 值 not in (None, ""):
                    标识 = str(值).strip()
                    break
            for 字段 in 名称字段:
                值 = 当前.get(字段)
                if 值 not in (None, ""):
                    名称 = str(值).strip()
                    break
            for 字段 in 提及字段:
                加入子项(当前.get(字段))
            for 字段 in 容器字段:
                if 字段 in 当前:
                    加入子项(当前.get(字段))
        elif not isinstance(当前, (str, bytes, int, float, bool)):
            for 字段 in 标识字段:
                值 = _读取字段(当前, 字段)
                if 值 not in (None, ""):
                    标识 = str(值).strip()
                    break
            for 字段 in 名称字段:
                值 = _读取字段(当前, 字段)
                if 值 not in (None, ""):
                    名称 = str(值).strip()
                    break
            for 字段 in 提及字段:
                加入子项(_读取字段(当前, 字段))
            for 字段 in 容器字段:
                值 = _读取字段(当前, 字段)
                if 值 not in (None, ""):
                    加入子项(值)
        elif 标识提示 and _OPENID规则.fullmatch(标识提示):
            名称 = str(当前).strip()
        if 标识 and _OPENID规则.fullmatch(标识) and 名称 and 名称 != 标识:
            结果[标识] = 名称
    return 结果


def _更新消息提及资料(记录: dict[str, Any], 消息: Any = None) -> None:
    """把消息里的被提及成员资料并入当前会话缓存，供正文和列表预览显示。"""
    if not isinstance(记录, dict):
        return
    会话标识 = str(记录.get("_session") or "").strip()
    if not 会话标识:
        return
    原始 = 消息 if 消息 is not None else 记录.get("raw_message")
    资料 = _提取消息提及资料(原始)
    if not 资料:
        return
    会话资料 = 成员资料缓存.setdefault(会话标识, {})
    for 成员标识, 昵称 in 资料.items():
        if 成员标识 not in 会话资料:
            while len(会话资料) >= 成员资料每会话上限:
                try:
                    会话资料.pop(next(iter(会话资料)))
                except (StopIteration, RuntimeError):
                    break
        当前 = 会话资料.setdefault(成员标识, {})
        当前["nickname"] = 昵称
        当前.setdefault("is_bot", False)
        当前.setdefault("role", "")


def _替换提及名称(文本: Any, 会话标识: str) -> str:
    """把会话预览中的 `<@openid>` 替换为已缓存的成员名称。"""
    原文 = str(文本 or "")
    资料表 = 成员资料缓存.get(str(会话标识 or "").strip()) or {}
    if not 资料表 or "<@" not in 原文:
        return 原文
    def 取昵称(成员标识: str) -> str:
        资料 = 资料表.get(成员标识)
        if isinstance(资料, dict):
            return str(资料.get("nickname") or 资料.get("username") or "").strip()
        return str(资料 or "").strip()
    return _提及规则.sub(
        lambda 匹配: "@" + (取昵称(匹配.group(1)) or 匹配.group(0)),
        原文,
    )


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


def _提取附件列表(消息: Any) -> list[Any]:
    """兼容 botpy 对象、字典和 raw_data 嵌套结构中的 attachments。"""
    if 消息 is None:
        return []
    来源: list[Any] = []
    待检查: list[Any] = [消息]
    已检查: set[int] = set()
    for _ in range(2):
        下一层: list[Any] = []
        for 当前 in 待检查:
            结构 = _解析消息结构(当前)
            当前 = 结构 if 结构 is not None else 当前
            标识 = id(当前)
            if 标识 in 已检查:
                continue
            已检查.add(标识)
            来源.append(当前)
            for 字段 in ("raw_data", "data", "payload", "event", "message"):
                嵌套 = _读取字段(当前, 字段)
                if 嵌套 not in (None, ""):
                    解析结果 = _解析消息结构(嵌套)
                    下一层.append(解析结果 if 解析结果 is not None else 嵌套)
        待检查 = 下一层
        if not 待检查:
            break
    附件列表: list[Any] = []
    for 当前 in 来源:
        for 字段 in ("attachments", "attachment", "files"):
            值 = _读取字段(当前, 字段)
            if 值 in (None, ""):
                continue
            解析结果 = _解析消息结构(值)
            值 = 解析结果 if 解析结果 is not None else 值
            if isinstance(值, (list, tuple)):
                附件列表.extend(值)
            elif isinstance(值, dict) and not any(
                键 in 值 for 键 in ("url", "download_url", "file_url", "src", "content_type")
            ):
                附件列表.extend(值.values())
            else:
                附件列表.append(值)
    return 附件列表


def _读取附件字段(附件: Any, *字段名: str) -> Any:
    for 字段 in 字段名:
        值 = _读取字段(附件, 字段)
        if 值 not in (None, ""):
            return 值
    return None


def _清理媒体地址(地址: Any) -> str:
    return html.unescape(str(地址 or "").strip()).strip("<>[](){}，。；;、")


def _提取附件媒体(消息: Any) -> dict[str, Any] | None:
    """从 QQ 官方消息 attachments 提取图片/语音/视频/文件及元数据。"""
    try:
        for 原附件 in _提取附件列表(消息):
            附件 = _解析消息结构(原附件) or 原附件
            类型值 = str(
                _读取附件字段(附件, "content_type", "mime_type", "type") or ""
            ).strip().lower()
            地址 = _清理媒体地址(
                _读取附件字段(附件, "url", "download_url", "file_url", "src")
                or (_读取附件字段(附件, "voice_wav_url") if "voice" in 类型值 else "")
            )
            if not 地址:
                continue
            if 类型值.startswith("image") or 类型值 in ("img", "图片"):
                媒体类型 = "图片"
            elif 类型值.startswith("video") or 类型值 in ("视频",):
                媒体类型 = "视频"
            elif 类型值.startswith("audio") or 类型值.startswith("voice") or 类型值 in ("语音",):
                媒体类型 = "语音"
            else:
                媒体类型 = "文件"
            媒体: dict[str, Any] = {"type": 媒体类型, "src": 地址, "text": ""}
            名称 = _读取附件字段(附件, "filename", "file_name", "name")
            if 名称 not in (None, ""):
                媒体["name"] = str(名称).strip()
            内容类型 = _读取附件字段(附件, "content_type", "mime_type")
            if 内容类型 not in (None, ""):
                媒体["content_type"] = str(内容类型).strip()
            for 字段 in ("size", "width", "height"):
                值 = _读取附件字段(附件, 字段)
                if 值 not in (None, ""):
                    媒体[字段] = 值
            return 媒体
    except Exception:
        pass
    return None


def _提取媒体字段(内容: str, 消息: Any = None) -> dict[str, Any] | None:
    """提取媒体信息：优先附件，其次带 URL 的消息占位或 QQ 富媒体链接。"""
    附件媒体 = _提取附件媒体(消息)
    if 附件媒体:
        return 附件媒体
    if not 内容:
        return None
    匹配 = _媒体占位规则.search(内容)
    if 匹配:
        类型 = 匹配.group(1)
        地址 = _清理媒体地址(匹配.group(2))
        文本 = (内容[: 匹配.start()] + 内容[匹配.end() :]).strip()
        return {"type": 类型, "src": 地址, "text": 文本}
    匹配 = _QQ图片域名.search(内容)
    if 匹配:
        地址 = _清理媒体地址(匹配.group(0))
        文本 = (内容[: 匹配.start()] + 内容[匹配.end() :]).strip()
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
    成员 = _读取字段(消息, "member")
    for 字段 in ("nick", "nickname", "member_name", "username", "name"):
        昵称 = str(_读取字段(成员, 字段) or "").strip()
        if 昵称:
            return 昵称
    return ""


def _提取成员头像(消息: Any) -> str:
    """读取官方事件扩展中的头像地址，不调用其他适配器接口。

    标准官方群事件不保证头像字段；新旧 AstrBot/botpy 版本可能把它
    放在 ``author``、``member``、``user`` 或 ``raw_data.d`` 中，且别名
    可能是 ``avatar_url``。限定遍历深度和字段，避免把整个消息对象
    转字符串，也避免误把正文中的 URL 当成头像。
    """
    待检查: list[tuple[Any, int]] = [(消息, 0)]
    已检查: set[int] = set()
    嵌套字段 = (
        "raw_data",
        "data",
        "payload",
        "event",
        "message",
        "d",
        "author",
        "member",
        "user",
        "profile",
    )
    头像字段 = ("avatar", "avatar_url", "avatarUrl", "icon")

    def 取地址(值: Any) -> str:
        if isinstance(值, dict):
            值 = (
                值.get("url")
                or 值.get("src")
                or 值.get("href")
                or 值.get("value")
            )
        地址 = str(值 or "").strip()
        if 地址.startswith("//"):
            地址 = "https:" + 地址
        return 地址 if 地址.startswith(("https://", "http://")) else ""

    while 待检查:
        当前, 深度 = 待检查.pop()
        if 当前 in (None, "") or 深度 > 5:
            continue
        if isinstance(当前, (dict, list, tuple, set)):
            对象键 = id(当前)
            if 对象键 in 已检查:
                continue
            已检查.add(对象键)
        for 字段 in 头像字段:
            地址 = 取地址(_读取字段(当前, 字段))
            if 地址:
                return 地址
        结构 = _解析消息结构(当前)
        if 结构 is not None and 结构 is not 当前:
            待检查.append((结构, 深度))
            continue
        if isinstance(当前, dict):
            for 字段 in 嵌套字段:
                值 = 当前.get(字段)
                if 值 not in (None, ""):
                    待检查.append((值, 深度 + 1))
        elif isinstance(当前, (list, tuple, set)):
            待检查.extend((值, 深度 + 1) for 值 in 当前)
        else:
            for 字段 in 嵌套字段:
                值 = _读取字段(当前, 字段)
                if 值 not in (None, ""):
                    待检查.append((值, 深度 + 1))
    return ""


def _记录成员资料(
    会话标识: str,
    成员标识: str,
    昵称: str,
    是机器人: bool = False,
    角色: str = "",
    头像: str = "",
) -> None:
    if not 成员标识:
        return
    会话资料 = 成员资料缓存.setdefault(会话标识, {})
    if 成员标识 not in 会话资料:
        while len(会话资料) >= 成员资料每会话上限:
            try:
                会话资料.pop(next(iter(会话资料)))
            except (StopIteration, RuntimeError):
                break
        会话资料[成员标识] = {
            "nickname": 昵称 or "",
            "is_bot": bool(是机器人),
            "role": str(角色 or ""),
            "avatar": str(头像 or "").strip(),
        }
    else:
        if 昵称:
            会话资料[成员标识]["nickname"] = 昵称
        会话资料[成员标识]["is_bot"] = bool(是机器人)
        if 角色:
            会话资料[成员标识]["role"] = str(角色 or "")
        if 头像:
            会话资料[成员标识]["avatar"] = str(头像).strip()


def _裁剪成员资料缓存() -> None:
    """热重载后也限制旧模块遗留的成员资料数量。"""
    for 资料表 in 成员资料缓存.values():
        if not isinstance(资料表, dict):
            continue
        while len(资料表) > 成员资料每会话上限:
            try:
                资料表.pop(next(iter(资料表)))
            except (StopIteration, RuntimeError):
                break


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
        with _元数据写入锁:
            数据 = copy.deepcopy(_读取本地缓存文件(强制刷新=True))
            昵称表 = 数据.setdefault("nicknames", {})
            if str(昵称表.get(会话标识) or "") != 昵称:
                昵称表[会话标识] = 昵称
                _持久化元数据字段("nicknames", 昵称表, 数据)
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

        平台实例 = 获取QQ官方平台(appid=appid)
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
        await _异步执行消息记录同步(_保存本地昵称, 会话标识, 昵称)
    except Exception as exc:
        名称 = type(exc).__name__
        if 名称 in ("NotFoundError", "Not Found", "NotFound"):
            _用户详情接口不可用 = True
            logger.info("QQ 官方未提供用户详情接口，私聊昵称改用兜底显示")
        else:
            logger.warning("私聊昵称补查失败：错误类型=%s", 名称)


def _准备昵称补查队列() -> asyncio.Queue[tuple[str, str, str]]:
    """热重载切换事件循环后，在旧队列已经清空时重建队列。"""
    global _昵称补查队列
    try:
        当前循环 = asyncio.get_running_loop()
    except RuntimeError:
        return _昵称补查队列
    队列循环 = getattr(_昵称补查队列, "_loop", None)
    有效任务 = any(not 任务.done() for 任务 in _昵称补查任务)
    if 队列循环 not in (None, 当前循环) and _昵称补查队列.empty() and not 有效任务:
        _昵称补查队列 = asyncio.Queue(maxsize=_昵称补查队列上限)
    return _昵称补查队列


async def _昵称补查工作() -> None:
    队列 = _准备昵称补查队列()
    while True:
        会话标识, 用户标识, appid = await 队列.get()
        try:
            await _补查用户昵称(会话标识, 用户标识, appid)
        except asyncio.CancelledError:
            raise
        except Exception as 异常:
            logger.warning("私聊昵称补查任务失败：错误类型=%s", type(异常).__name__)
        finally:
            _昵称补查等待中.discard((会话标识, 用户标识))
            队列.task_done()


def _启动昵称补查任务() -> None:
    global _昵称补查任务
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return
    _准备昵称补查队列()
    当前循环任务 = [
        任务
        for 任务 in _昵称补查任务
        if not 任务.done() and getattr(任务, "get_loop", lambda: None)() is 循环
    ]
    while len(当前循环任务) < _昵称补查工作数:
        当前循环任务.append(循环.create_task(_昵称补查工作()))
    _昵称补查任务 = 当前循环任务


def _排队昵称补查(会话标识: str, 用户标识: str, appid: str = "") -> bool:
    """同一私聊用户同时最多存在一个补查项目，避免消息洪峰生成无限任务。"""
    global _昵称补查溢出数
    if not _昵称补查接收入队 or _用户详情接口不可用:
        return False
    会话标识 = str(会话标识 or "").strip()
    用户标识 = str(用户标识 or "").strip()
    if not 会话标识 or not 用户标识:
        return False
    键 = (会话标识, 用户标识)
    if 键 in _昵称补查等待中:
        return True
    队列 = _准备昵称补查队列()
    _昵称补查等待中.add(键)
    try:
        队列.put_nowait((会话标识, 用户标识, str(appid or "")))
    except asyncio.QueueFull:
        _昵称补查等待中.discard(键)
        _昵称补查溢出数 += 1
        if _昵称补查溢出数 == 1 or _昵称补查溢出数 % 100 == 0:
            logger.warning(
                "私聊昵称补查队列已满：上限=%d，累计未入队=%d",
                _昵称补查队列上限,
                _昵称补查溢出数,
            )
        return False
    _启动昵称补查任务()
    return True


def 记录收到消息(
    消息: Any,
    类型: str,
    appid: str = "",
    *,
    is_self: bool = False,
    源: str = "qq_official",
) -> dict[str, Any] | None:
    """把一条 QQ 官方消息写入进程内缓存。"""
    global 发送序号, _消息缓存总数缓存
    try:
        会话标识 = ""
        消息ID = _提取消息ID(消息)
        回显自己 = bool(消息ID) and 消息ID in 自己发送消息ID
        is_self = bool(is_self) or 回显自己
        回显记录: dict[str, Any] | None = None
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
        if not is_self and 类型 in {"group", "user"}:
            # 部分发送入口拿不到响应 ID，官方回显仍会再次经过消息事件。
            # 只在短时间窗口内把它并入已记录的机器人消息，避免重复展示。
            回显记录 = _查找机器人回显记录(
                消息缓存.get(会话标识) or {},
                消息ID,
                内容,
                时间戳,
            )
            if 回显记录 is not None:
                is_self = True
                if 消息ID and not _规范消息ID(回显记录.get("message_id")):
                    回显记录["message_id"] = 消息ID
                if 消息ID:
                    自己发送消息ID[消息ID] = time.time()
        if not is_self:
            清除主动消息权限(会话标识, 类型)
        引用ID = ""
        消息引用 = _读取字段(消息, "message_reference")
        if 消息引用:
            引用ID = str(_读取字段(消息引用, "message_id") or "").strip()
        自身REFIDX = _提取REFIDX(消息)
        作者头像 = _提取成员头像(消息)
        _记录成员资料(
            会话标识,
            成员标识,
            昵称,
            是机器人,
            角色,
            作者头像,
        )
        会话 = _取得会话缓存(会话标识, 类型, appid)
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
            "avatar": 作者头像,
            "raw_message": _序列化原始消息(_读取字段(消息, "raw_data") or 消息),
            "recalled": False,
            "media": _提取媒体字段(内容, 消息),
            "reference_id": 引用ID or "",
            "refidx": 自身REFIDX or "",
            "chat_type": 类型,
            "ts": _转数字时间戳(时间戳) or int(time.time()),
        }
        撤回键 = (会话标识, 消息ID)
        待同步时间 = 已撤回消息待同步.get(撤回键)
        if 待同步时间 is not None:
            if time.time() - float(待同步时间 or 0) < 10 * 60:
                记录["recalled"] = True
            已撤回消息待同步.pop(撤回键, None)
        _更新消息提及资料(记录, 消息)
        已有记录 = next(
            (
                x for x in reversed(会话["messages"] or [])
                if (
                    (消息ID and _规范消息ID(x.get("message_id")) == 消息ID)
                    or (回显记录 is not None and x is 回显记录)
                    or _消息记录重复(x, 记录)
                )
            ),
            None,
        )
        新增记录 = 已有记录 is None
        if 新增记录:
            会话["messages"].append(记录)
            _消息缓存总数缓存 += 1
            会话["msg_count"] = max(
                int(会话.get("msg_count") or 0),
                len(会话["messages"]),
            )
            # 每条首次收到的消息都计入未读数，包括机器人和管理员本人发送的消息；
            # 重复 message_id 会走下方合并分支，不会重复累计。
            会话["unread"] = int(会话.get("unread") or 0) + 1
            _持久化未读数(会话标识, 会话["unread"])
        else:
            # QQ 官方可能同时投递 at/group 两种回调；同一 message_id 只保留一条。
            记录 = _合并重复消息(已有记录, 记录)
        if _消息数据库已配置() and 新增记录:
            try:
                _排队消息持久化("message", dict(记录))
            except Exception as 存储异常:
                logger.debug("消息记录入库失败：错误类型=%s", type(存储异常).__name__)
        if len(会话["messages"]) > 每会话最大消息数:
            旧数量 = len(会话["messages"])
            会话["messages"] = 会话["messages"][-每会话最大消息数:]
            _消息缓存总数缓存 = max(
                0,
                _消息缓存总数缓存 - (旧数量 - len(会话["messages"])),
            )
        新时间戳 = _转数字时间戳(时间戳) or int(time.time())
        # 摘要按时间维护，纯媒体/空文本消息也要覆盖上一条预览；
        # 旧消息回补时不能把较新的摘要倒退。
        try:
            当前摘要时间 = int(会话.get("last_ts") or 0)
        except (TypeError, ValueError):
            当前摘要时间 = 0
        摘要记录 = 记录 if isinstance(记录, dict) else {}
        if 新时间戳 >= 当前摘要时间:
            会话["last_content"] = str(摘要记录.get("content") or "")
            会话["last_nickname"] = str(摘要记录.get("nickname") or 昵称 or "")
            会话["last_message_id"] = str(摘要记录.get("message_id") or 消息ID or "")
        会话["last_ts"] = max(int(会话.get("last_ts") or 0), 新时间戳)
        # 先通知网页再等待数据库线程；这一步必须保持在事件循环内轻量完成。
        if 新增记录:
            _推送消息事件(记录, 会话)
        _裁剪总缓存()
        return 记录
    except Exception as exc:
        logger.warning("消息记录缓存写入失败：错误类型=%s", type(exc).__name__)
        return None


def _准备消息接收队列() -> asyncio.Queue[tuple[Any, Any, str]]:
    """热重载切换事件循环后，在旧队列已经清空时重建队列。"""
    global _消息接收队列
    try:
        当前循环 = asyncio.get_running_loop()
    except RuntimeError:
        return _消息接收队列
    队列循环 = getattr(_消息接收队列, "_loop", None)
    任务运行中 = _消息接收任务 is not None and not _消息接收任务.done()
    if 队列循环 not in (None, 当前循环) and _消息接收队列.empty() and not 任务运行中:
        _消息接收队列 = asyncio.Queue(maxsize=_消息接收队列上限)
    return _消息接收队列


async def _消息接收工作() -> None:
    """单 worker 按 QQ 官方到达顺序更新缓存，接收回调不执行解析和写库。"""
    global _消息接收任务
    队列 = _准备消息接收队列()
    try:
        while True:
            客户端, 消息, 类型 = await 队列.get()
            try:
                appid = str(_读取字段(_读取字段(客户端, "platform"), "appid") or "")
                记录 = 记录收到消息(消息, 类型, appid)
                if 类型 == "group" and 记录:
                    会话标识 = str(记录.get("_session") or "").strip()
                    if 会话标识 and 获取群机器人状态(会话标识) != "active":
                        _设置群机器人状态(会话标识, "active", appid, 持久化=True)
                if 类型 == "user" and 记录:
                    用户标识 = str(记录.get("user_id") or "").strip()
                    会话标识 = str(记录.get("_session") or "").strip()
                    if _昵称需要补查(会话标识, 消息缓存.get(会话标识)):
                        _排队昵称补查(会话标识, 用户标识, appid)
            except asyncio.CancelledError:
                raise
            except Exception as 异常:
                logger.warning("消息记录接收队列处理失败：错误类型=%s", type(异常).__name__)
            finally:
                队列.task_done()
    except asyncio.CancelledError:
        raise
    finally:
        当前任务 = asyncio.current_task()
        if _消息接收任务 is 当前任务:
            _消息接收任务 = None


def _启动消息接收任务() -> asyncio.Task[Any] | None:
    global _消息接收任务
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return None
    if (
        _消息接收任务 is None
        or _消息接收任务.done()
        or getattr(_消息接收任务, "get_loop", lambda: None)() is not 循环
    ):
        _准备消息接收队列()
        _消息接收任务 = 循环.create_task(_消息接收工作())
    return _消息接收任务


def _排队收到消息(客户端: Any, 消息: Any, 类型: str) -> bool:
    """QQ 官方接收回调只做一次有界队列非阻塞投递。"""
    global _消息接收溢出数
    if not _消息接收入队:
        return False
    队列 = _准备消息接收队列()
    try:
        队列.put_nowait((客户端, 消息, 类型))
    except asyncio.QueueFull:
        _消息接收溢出数 += 1
        if _消息接收溢出数 == 1 or _消息接收溢出数 % 100 == 0:
            logger.warning(
                "消息记录接收队列已满：上限=%d，累计未入队=%d",
                _消息接收队列上限,
                _消息接收溢出数,
            )
        return False
    _启动消息接收任务()
    return True


def _裁剪总缓存() -> None:
    global _数据库裁剪进行中, _上次数据库裁剪排队时间
    global _消息缓存总数缓存, _消息缓存总数检查时间
    当前时间 = time.monotonic()
    需要重新统计 = (
        _消息缓存总数缓存 <= 0
        or 当前时间 - _消息缓存总数检查时间 >= _消息缓存总数检查间隔
    )
    if not 需要重新统计 and _消息缓存总数缓存 <= 总消息上限:
        return
    if 需要重新统计:
        _消息缓存总数检查时间 = 当前时间
        总数 = sum(len(会话.get("messages", [])) for 会话 in 消息缓存.values())
        _消息缓存总数缓存 = 总数
    else:
        # 追加和单会话裁剪都会维护计数；超限时直接使用增量值，
        # 避免消息洪峰期间每条消息都重新遍历全部会话。
        总数 = _消息缓存总数缓存
    if 总数 <= 总消息上限:
        return
    try:
        会话列表 = sorted(
            消息缓存.values(),
            key=lambda s: (s.get("last_ts") or 0, s.get("appid") or ""),
        )
        目标会话数 = max(1, len(会话列表))
        目标保留数量 = max(
            1,
            min(每会话最大消息数 // 2, 总消息上限 // 目标会话数),
        )
        for 会话 in 会话列表:
            if 总数 <= 总消息上限:
                break
            消息列表 = 会话.get("messages") or []
            保留数量 = 目标保留数量
            旧数量 = len(消息列表)
            if 旧数量 <= 保留数量:
                continue
            会话["messages"] = 消息列表[-保留数量:]
            总数 -= 旧数量 - len(会话["messages"])
        _消息缓存总数缓存 = max(0, 总数)
    except Exception:
        _消息缓存总数缓存 = max(0, 总数)
    if _消息数据库已配置():
        try:
            当前时间 = time.monotonic()
            if _数据库裁剪进行中 or 当前时间 - _上次数据库裁剪排队时间 < _数据库裁剪最短间隔:
                return
            _数据库裁剪进行中 = True
            _上次数据库裁剪排队时间 = 当前时间
            任务 = _后台执行同步(_消息存储.裁剪总消息, 总消息上限 * 2)
            if 任务 is None:
                _数据库裁剪进行中 = False
            else:
                def _裁剪完成(_任务: asyncio.Task[Any]) -> None:
                    global _数据库裁剪进行中
                    _数据库裁剪进行中 = False

                任务.add_done_callback(_裁剪完成)
        except Exception:
            _数据库裁剪进行中 = False
            pass


def 记录发送消息(
    会话标识: str,
    类型: str,
    内容: str,
    appid: str = "",
    *,
    消息ID: str = "",
    自身REFIDX: str = "",
    引用ID: str = "",
    媒体: dict[str, Any] | None = None,
    发送者昵称: str = "",
    发送者头像: str = "",
    来源: str = "",
    发送时间: Any = None,
) -> dict[str, Any] | None:
    """把机器人发送的消息写入缓存，并按一条新消息累计未读数。"""
    global 发送序号, _消息缓存总数缓存
    try:
        消息ID = _规范消息ID(消息ID)
        会话 = _取得会话缓存(会话标识, 类型, appid)
        成功时间戳 = _转数字时间戳(发送时间) or int(time.time())
        来源值 = str(来源 or "web_panel").strip() or "web_panel"
        媒体值 = 媒体 or _提取媒体字段(内容)
        头像值 = str(发送者头像 or "").strip()
        if not 头像值 and 来源值.startswith("bot_"):
            机器人缓存项 = 机器人资料缓存.get(str(appid or "default").strip() or "default")
            if isinstance(机器人缓存项, tuple) and len(机器人缓存项) > 1:
                机器人资料 = 机器人缓存项[1]
                if isinstance(机器人资料, dict):
                    头像值 = str(
                        机器人资料.get("avatar")
                        or 机器人资料.get("avatar_url")
                        or ""
                    ).strip()
        # event._post_send、send_by_session 和网页直发可能分别捕获同一
        # 次发送。响应没有消息 ID 时，以来源、内容和短时间窗口合并交叉记账。
        重复发送记录 = _查找重复机器人发送(
            会话,
            类型,
            内容,
            媒体值,
            成功时间戳,
            来源值,
            消息ID,
        )
        if 重复发送记录 is not None:
            _合并重复消息(
                重复发送记录,
                {
                    "message_id": 消息ID,
                    "content": 内容,
                    "media": 媒体值,
                    "avatar": 头像值,
                    "refidx": 自身REFIDX or "",
                    "reference_id": 引用ID or "",
                    "is_self": True,
                    "source": 来源值,
                    "chat_type": 类型,
                    "appid": str(appid or ""),
                    "ts": 成功时间戳,
                },
            )
            if 消息ID:
                自己发送消息ID[消息ID] = time.time()
            return 重复发送记录
        if 消息ID:
            已有记录 = next(
                (
                    x for x in reversed(会话["messages"] or [])
                    if _规范消息ID(x.get("message_id")) == 消息ID
                ),
                None,
            )
            if 已有记录 is not None:
                _合并重复消息(
                    已有记录,
                    {
                        "message_id": str(消息ID),
                        "content": 内容,
                        "media": 媒体 or _提取媒体字段(内容),
                        "avatar": 头像值,
                        "refidx": 自身REFIDX or "",
                        "reference_id": 引用ID or "",
                        "is_self": True,
                        "source": 来源值,
                        "chat_type": 类型,
                        "appid": str(appid or ""),
                        "ts": 成功时间戳,
                    },
                )
                try:
                    当前摘要时间 = int(会话.get("last_ts") or 0)
                except (TypeError, ValueError):
                    当前摘要时间 = 0
                if 成功时间戳 >= 当前摘要时间:
                    会话["last_content"] = str(已有记录.get("content") or "")
                    会话["last_nickname"] = str(已有记录.get("nickname") or 发送者昵称 or "我")
                    会话["last_message_id"] = str(已有记录.get("message_id") or 消息ID or "")
                会话["last_ts"] = max(int(会话.get("last_ts") or 0), 成功时间戳)
                自己发送消息ID[str(消息ID)] = time.time()
                return 已有记录
        发送序号 += 1
        记录: dict[str, Any] = {
            "id": 发送序号,
            "_session": str(会话标识 or ""),
            "message_id": 消息ID,
            "refidx": str(自身REFIDX or "").strip(),
            "user_id": "",
            "appid": str(appid or 会话.get("appid") or ""),
            "nickname": 发送者昵称 or "我",
            "content": 内容,
            "timestamp": _格式化时间戳(成功时间戳),
            "is_self": True,
            "source": 来源值,
            "avatar": 头像值,
            "raw_message": "",
            "recalled": False,
            "media": 媒体值,
            "reference_id": 引用ID or "",
            "chat_type": 类型,
            "ts": 成功时间戳,
        }
        会话["messages"].append(记录)
        _消息缓存总数缓存 += 1
        会话["msg_count"] = max(
            int(会话.get("msg_count") or 0),
            len(会话["messages"]),
        )
        # 网页/机器人主动发送同样是一条新消息，保持未读红点按消息数累计。
        会话["unread"] = int(会话.get("unread") or 0) + 1
        _持久化未读数(会话标识, 会话["unread"])
        if 来源.startswith("bot_"):
            logger.debug(
                "消息记录已捕获机器人发送：会话类型=%s，来源=%s，消息ID=%s，文本长度=%d",
                类型,
                来源,
                str(消息ID or "")[:80],
                len(str(内容 or "")),
            )
        if 消息ID:
            自己发送消息ID[str(消息ID)] = time.time()
            try:
                if len(自己发送消息ID) > 500:
                    for 键 in [k for k, v in 自己发送消息ID.items() if time.time() - v > 300]:
                        自己发送消息ID.pop(键, None)
            except Exception:
                pass
        if _消息数据库已配置():
            try:
                _排队消息持久化("message", dict(记录))
            except Exception as 存储异常:
                logger.debug("消息记录入库失败：错误类型=%s", type(存储异常).__name__)
        if len(会话["messages"]) > 每会话最大消息数:
            旧数量 = len(会话["messages"])
            会话["messages"] = 会话["messages"][-每会话最大消息数:]
            _消息缓存总数缓存 = max(
                0,
                _消息缓存总数缓存 - (旧数量 - len(会话["messages"])),
            )
        try:
            当前摘要时间 = int(会话.get("last_ts") or 0)
        except (TypeError, ValueError):
            当前摘要时间 = 0
        if 成功时间戳 >= 当前摘要时间:
            会话["last_content"] = str(内容 or "")
            会话["last_nickname"] = 发送者昵称 or "我"
            会话["last_message_id"] = str(消息ID or "")
        会话["last_ts"] = max(int(会话.get("last_ts") or 0), 成功时间戳)
        # 机器人发送回复也属于一条新消息；只有设置会话已读才会清零红点。
        _推送消息事件(记录, 会话)
        _裁剪总缓存()
        return 记录
    except Exception as exc:
        logger.warning("消息记录发送缓存写入失败：错误类型=%s", type(exc).__name__)
        return None


def 设置会话已读(会话标识: str) -> bool:
    """打开会话时清零未读数（内存与 MySQL 同步清）。"""
    try:
        会话标识 = str(会话标识 or "").strip()
        会话 = 消息缓存.get(会话标识)
        if 会话:
            会话["unread"] = 0
        _持久化未读数(会话标识, 0)
        return True
    except Exception:
        return False


def 标记撤回(会话标识: str, 消息ID: str) -> bool:
    会话标识 = str(会话标识 or "").strip()
    消息ID = str(消息ID or "").strip()
    if not 会话标识 or not 消息ID:
        return False
    当前时间 = time.time()
    for 键, 时间戳 in list(已撤回消息待同步.items()):
        if 当前时间 - float(时间戳 or 0) >= 10 * 60:
            已撤回消息待同步.pop(键, None)
    会话 = 消息缓存.get(会话标识)
    找到 = False
    已更新记录: list[dict[str, Any]] = []
    if 会话:
        for 记录 in 会话.get("messages", []):
            if str(记录.get("message_id") or "").strip() == 消息ID:
                记录["recalled"] = True
                找到 = True
                已更新记录.append(记录)
    存储已标记 = False
    if _消息存储 is not None:
        try:
            存储已标记 = bool(_消息存储.标记消息撤回(会话标识, 消息ID))
        except Exception:
            存储已标记 = False
    if not 找到 and not 存储已标记:
        已撤回消息待同步[(会话标识, 消息ID)] = 当前时间
    if 已更新记录 and 会话:
        for 记录 in 已更新记录:
            _推送消息事件(记录, 会话)
    return 找到 or 存储已标记


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


def 获取QQ官方平台(上下文: Any = None, appid: str = "") -> Any | None:
    上下文 = 上下文 if 上下文 is not None else 当前插件上下文
    目标AppID = str(appid or "").strip()
    首个官方平台 = None
    for 平台实例 in _读取平台实例列表(上下文):
        try:
            if not _是QQ官方平台(平台实例):
                continue
            if 首个官方平台 is None:
                首个官方平台 = 平台实例
            if not 目标AppID:
                return 平台实例
            配置 = _读取字段(平台实例, "config")
            元信息 = 平台实例.meta()
            候选AppID = (
                _读取字段(平台实例, "appid"),
                _读取字段(平台实例, "app_id"),
                _读取字段(配置, "appid"),
                _读取字段(配置, "app_id"),
                _读取字段(元信息, "appid"),
                _读取字段(元信息, "app_id"),
            )
            if any(str(值 or "").strip() == 目标AppID for 值 in 候选AppID):
                return 平台实例
        except Exception:
            continue
    # 单机器人或旧版本平台对象未暴露 AppID 时保持兼容；多机器人时优先精确匹配。
    return 首个官方平台


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


async def 获取机器人资料(appid: str = "") -> dict[str, str]:
    """按 QQ 官方 /users/@me 接口读取并缓存机器人名称、头像和 ID。"""
    缓存键 = str(appid or "default").strip() or "default"
    当前时间 = time.time()
    已缓存 = 机器人资料缓存.get(缓存键)
    if 已缓存 and 当前时间 - float(已缓存[0] or 0) < 机器人资料缓存秒数:
        return dict(已缓存[1])
    平台实例 = 获取QQ官方平台(appid=appid)
    通道 = 获取HTTP通道(平台实例)
    if 通道 is None:
        return {}
    _, _http = 通道
    try:
        from botpy.http import Route

        响应 = await _http.request(Route("GET", "/users/@me"))
        资料 = {
            "id": str(_提取发送响应字段(响应, "id") or "").strip(),
            "username": str(_提取发送响应字段(响应, "username", "name") or "").strip(),
            "avatar": str(_提取发送响应字段(响应, "avatar", "avatar_url") or "").strip(),
        }
        if not 资料["username"] and not 资料["avatar"]:
            机器人资料缓存[缓存键] = (当前时间, {})
            return {}
        机器人资料缓存[缓存键] = (当前时间, dict(资料))
        return 资料
    except Exception as 异常:
        logger.debug("QQ官方机器人资料读取失败：错误类型=%s", type(异常).__name__)
        return {}


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


def 保存群备注(会话标识: str, 备注: str = "", 群QQ: str = "") -> bool:
    with _元数据写入锁:
        数据 = copy.deepcopy(_读取本地缓存文件(强制刷新=True))
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
        return _持久化元数据字段("remarks", 备注表, 数据)


def 删除群备注(会话标识: str) -> bool:
    """删除某个会话的全部备注与群号信息。"""
    with _元数据写入锁:
        数据 = copy.deepcopy(_读取本地缓存文件(强制刷新=True))
        备注表 = 数据.get("remarks") or {}
        if 会话标识 in 备注表:
            del 备注表[会话标识]
            return _持久化元数据字段("remarks", 备注表, 数据)
        return True


def 设置会话置顶(会话标识: str, 置顶: bool) -> bool:
    """置顶或取消置顶会话，置顶顺序持久化到元数据存储。"""
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return False
    with _元数据写入锁:
        # 置顶操作强制读取数据库最新列表，避免网页多开或并发操作使用旧缓存。
        数据 = copy.deepcopy(_读取本地缓存文件(强制刷新=True))
        置顶列表 = [str(x) for x in (数据.get("pinned") or []) if str(x or "").strip()]
        已置顶 = 会话标识 in 置顶列表
        if 置顶 and not 已置顶:
            置顶列表.insert(0, 会话标识)
            return _持久化元数据字段("pinned", 置顶列表, 数据)
        if not 置顶 and 已置顶:
            置顶列表 = [x for x in 置顶列表 if x != 会话标识]
            return _持久化元数据字段("pinned", 置顶列表, 数据)
        return True


_本地缓存内存: dict[str, Any] | None = None
_本地缓存时间: float = 0.0


def _读取本地缓存文件(强制刷新: bool = False) -> dict[str, Any]:
    """读取置顶/备注/昵称元数据：优先 MySQL，未配置数据库时仅内存缓存。"""
    global _本地缓存内存, _本地缓存时间
    with _元数据写入锁:
        now = time.time()
        if not 强制刷新 and _本地缓存内存 is not None and now - _本地缓存时间 < 5.0:
            return copy.deepcopy(_本地缓存内存)
        try:
            if _消息存储 is not None:
                元数据 = _消息存储.读取全部元数据()
                # 空元数据也是有效结果，必须更新时间戳，否则每次会话
                # 显示名计算都会重新建立数据库连接。
                _本地缓存内存 = copy.deepcopy(元数据 or {})
                _本地缓存时间 = now
                return copy.deepcopy(_本地缓存内存)
        except Exception as exc:
            logger.debug("消息记录 MySQL 元数据读取失败：错误类型=%s", type(exc).__name__)
            # 失败结果短暂缓存，避免同一请求内的会话循环触发 N+1 重试。
            _本地缓存时间 = now
        return copy.deepcopy(_本地缓存内存 or {})


def _持久化元数据字段(字段名: str, 值: Any, 当前数据: dict[str, Any] | None = None) -> bool:
    """只提交一个元数据字段，避免置顶、备注和昵称并发操作互相覆盖。"""
    global _本地缓存内存, _本地缓存时间
    if _消息存储 is None:
        数据 = copy.deepcopy(当前数据 or _本地缓存内存 or {})
        数据[字段名] = copy.deepcopy(值)
        _本地缓存内存 = 数据
        _本地缓存时间 = time.time()
        return False
    try:
        if not _消息存储.写入元数据(字段名, 值):
            return False
    except Exception as 存储异常:
        logger.debug("消息记录元数据入库失败：字段=%s，错误类型=%s", 字段名, type(存储异常).__name__)
        return False
    数据 = copy.deepcopy(当前数据 or _本地缓存内存 or {})
    数据[字段名] = copy.deepcopy(值)
    _本地缓存内存 = 数据
    _本地缓存时间 = time.time()
    return True


def 标记群信息待刷新(会话标识: str) -> None:
    会话标识 = str(会话标识 or "").strip()
    if 会话标识:
        群信息待刷新.add(会话标识)


def _解析群机器人状态值(值: Any) -> dict[str, Any]:
    if isinstance(值, dict):
        原始 = 值
    else:
        文本 = str(值 or "").strip()
        try:
            原始 = json.loads(文本) if 文本.startswith("{") else {"status": 文本}
        except (TypeError, ValueError, json.JSONDecodeError):
            原始 = {"status": 文本}
    状态 = str(原始.get("status") or "unknown").strip().lower()
    if 状态 not in {"active", "removed", "unknown"}:
        状态 = "unknown"
    try:
        检查时间 = int(原始.get("checked_at") or 0)
    except (TypeError, ValueError):
        检查时间 = 0
    允许主动消息 = 原始.get("allow_proactive_msg")
    if isinstance(允许主动消息, str):
        文本 = 允许主动消息.strip().lower()
        if 文本 in {"true", "1", "yes", "on", "开启"}:
            允许主动消息 = True
        elif 文本 in {"false", "0", "no", "off", "关闭"}:
            允许主动消息 = False
        else:
            允许主动消息 = None
    elif not isinstance(允许主动消息, bool):
        允许主动消息 = None
    return {
        "status": 状态,
        "checked_at": max(0, 检查时间),
        "appid": str(原始.get("appid") or "").strip(),
        "member_role": str(原始.get("member_role") or "").strip().lower(),
        "allow_proactive_msg": 允许主动消息,
        "recv_msg_setting": str(原始.get("recv_msg_setting") or "").strip().lower(),
    }


def _读取群机器人状态(会话标识: str) -> dict[str, Any]:
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return {
            "status": "unknown",
            "checked_at": 0,
            "appid": "",
            "member_role": "",
            "allow_proactive_msg": None,
            "recv_msg_setting": "",
        }
    状态 = 群机器人状态缓存.get(会话标识)
    if isinstance(状态, dict):
        return _解析群机器人状态值(状态)
    信息 = 群信息缓存.get(会话标识) or {}
    if 信息.get("membership_status"):
        return _解析群机器人状态值(
            {
                "status": 信息.get("membership_status"),
                "checked_at": 信息.get("membership_checked_at") or 信息.get("updated_at") or 0,
                "appid": 信息.get("appid") or "",
                "member_role": 信息.get("member_role") or "",
                "allow_proactive_msg": 信息.get("allow_proactive_msg"),
                "recv_msg_setting": 信息.get("recv_msg_setting") or "",
            }
        )
    return {
        "status": "unknown",
        "checked_at": 0,
        "appid": "",
        "member_role": "",
        "allow_proactive_msg": None,
        "recv_msg_setting": "",
    }


def 获取群机器人状态(会话标识: str) -> str:
    return str(_读取群机器人状态(会话标识).get("status") or "unknown")


def 群机器人是否在群(会话标识: str) -> bool:
    return 获取群机器人状态(会话标识) != "removed"


def _设置群机器人状态(
    会话标识: str,
    状态: str,
    appid: str = "",
    成员角色: str = "",
    允许主动消息: bool | None = None,
    接收消息设置: str = "",
    *,
    持久化: bool = True,
) -> dict[str, Any]:
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return {
            "status": "unknown",
            "checked_at": 0,
            "appid": "",
            "member_role": "",
            "allow_proactive_msg": None,
            "recv_msg_setting": "",
        }
    状态 = str(状态 or "unknown").strip().lower()
    if 状态 not in {"active", "removed", "unknown"}:
        状态 = "unknown"
    旧状态 = str((群机器人状态缓存.get(会话标识) or {}).get("status") or "unknown")
    记录 = {
        "status": 状态,
        "checked_at": int(time.time()),
        "appid": str(appid or "").strip(),
        "member_role": str(成员角色 or "").strip().lower(),
        "allow_proactive_msg": (
            允许主动消息
            if isinstance(允许主动消息, bool)
            else (群机器人状态缓存.get(会话标识) or {}).get("allow_proactive_msg")
        ),
        "recv_msg_setting": str(
            接收消息设置
            or (群机器人状态缓存.get(会话标识) or {}).get("recv_msg_setting")
            or ""
        ).strip().lower(),
    }
    群机器人状态缓存[会话标识] = 记录
    信息 = 群信息缓存.setdefault(会话标识, {"group_openid": 会话标识})
    信息["membership_status"] = 状态
    信息["membership_checked_at"] = 记录["checked_at"]
    if 记录["appid"]:
        信息["appid"] = 记录["appid"]
    if 记录["member_role"]:
        信息["member_role"] = 记录["member_role"]
    if isinstance(记录.get("allow_proactive_msg"), bool):
        信息["allow_proactive_msg"] = 记录["allow_proactive_msg"]
    if 记录.get("recv_msg_setting"):
        信息["recv_msg_setting"] = 记录["recv_msg_setting"]
    if 记录["member_role"] in {"owner", "admin"}:
        信息["is_admin"] = True
    elif 状态 == "removed":
        信息["is_admin"] = False
    if 状态 != 旧状态:
        _推送群状态事件(会话标识, 状态)
    if 持久化 and _消息数据库已配置():
        try:
            from 功能文件.管理功能.基础功能 import 运行状态数据库

            值 = json.dumps(记录, ensure_ascii=False, separators=(",", ":"))
            _后台执行同步(
                运行状态数据库.写入运行状态值,
                当前插件配置,
                群机器人状态命名空间,
                会话标识,
                值,
            )
        except Exception as 异常:
            logger.debug("消息记录群成员状态持久化排队失败：错误类型=%s", type(异常).__name__)
    return 记录


def 标记群机器人已移除(会话标识: str, appid: str = "") -> dict[str, Any]:
    """处理官方 GROUP_DEL_ROBOT 事件，立即把群标记为已移除并持久化。"""
    return _设置群机器人状态(会话标识, "removed", appid, 持久化=True)


def 标记群机器人已加入(会话标识: str, appid: str = "") -> dict[str, Any]:
    """处理官方 GROUP_ADD_ROBOT 事件，恢复群的可用状态并持久化。"""
    return _设置群机器人状态(会话标识, "active", appid, 持久化=True)


def _恢复群机器人状态() -> None:
    if not _消息数据库已配置():
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态命名空间

        状态表 = 读取运行状态命名空间(当前插件配置, 群机器人状态命名空间) or {}
        for 会话标识, 值 in 状态表.items():
            会话标识 = str(会话标识 or "").strip()
            if not 会话标识:
                continue
            记录 = _解析群机器人状态值(值)
            群机器人状态缓存[会话标识] = 记录
            信息 = 群信息缓存.setdefault(会话标识, {"group_openid": 会话标识})
            信息["membership_status"] = 记录["status"]
            信息["membership_checked_at"] = 记录["checked_at"]
            if 记录["appid"]:
                信息["appid"] = 记录["appid"]
            if 记录["member_role"]:
                信息["member_role"] = 记录["member_role"]
            if isinstance(记录.get("allow_proactive_msg"), bool):
                信息["allow_proactive_msg"] = 记录["allow_proactive_msg"]
            if 记录.get("recv_msg_setting"):
                信息["recv_msg_setting"] = 记录["recv_msg_setting"]
            if 记录["status"] == "removed":
                信息["is_admin"] = False
    except Exception as 异常:
        logger.debug("消息记录群成员状态恢复失败：错误类型=%s", type(异常).__name__)


def _群机器人状态需检查(会话标识: str, 强制: bool = False) -> bool:
    if 强制:
        return True
    记录 = _读取群机器人状态(会话标识)
    if 记录["status"] == "unknown":
        return True
    if 记录["status"] == "active" and not 记录.get("member_role"):
        return True
    return int(time.time()) - int(记录.get("checked_at") or 0) >= 群机器人状态缓存有效期秒


def _异常表示群机器人已移除(异常: Exception) -> bool:
    异常类型 = type(异常).__name__.strip().lower()
    if "notfound" in 异常类型 or "not_found" in 异常类型:
        return True
    for 字段名 in ("status", "status_code", "code", "http_status"):
        try:
            if int(getattr(异常, 字段名)) == 404:
                return True
        except (AttributeError, TypeError, ValueError):
            continue
    try:
        文本 = str(异常).lower()
    except Exception:
        文本 = ""
    if any(词 in 文本 for 词 in ("rate limit", "rate_limit", "限流", "频率", "timeout", "timed out")):
        return False
    return any(
        词 in 文本
        for 词 in (
            "404",
            "not found",
            "不存在",
            "不在群",
            "未加入群",
            "非群成员",
            "不是群成员",
        )
    )


def _响应表示群机器人已移除(响应: Any) -> bool:
    """识别官方接口返回的群不存在/机器人不在群错误，不误判权限错误。"""
    if not isinstance(响应, dict):
        return False
    for 字段名 in ("status", "status_code", "http_status", "code"):
        try:
            if int(响应.get(字段名)) == 404:
                return True
        except (TypeError, ValueError):
            continue
    try:
        文本 = json.dumps(响应, ensure_ascii=False, separators=(",", ":")).lower()
    except Exception:
        文本 = str(响应).lower()
    if any(词 in 文本 for 词 in ("rate limit", "rate_limit", "限流", "频率", "timeout", "timed out", "11253")):
        return False
    return any(
        词 in 文本
        for 词 in (
            "404",
            "not found",
            "不存在",
            "不在群",
            "未加入群",
            "非群成员",
            "不是群成员",
        )
    )


def _群信息异常摘要(异常: Exception) -> dict[str, str]:
    """提取群资料请求的受控诊断字段，避免日志只剩 ServerError。"""
    类型 = type(异常).__name__
    原文 = getattr(异常, "msgs", None) or str(异常)
    文本 = re.sub(r"\s+", " ", str(原文 or "")).strip()
    文本 = re.sub(r"https?://\S+", "<url>", 文本, flags=re.IGNORECASE)[:200]
    小写 = 文本.lower()
    if _异常表示群机器人已移除(异常):
        分类 = "not_member"
    elif any(词 in 小写 for 词 in ("rate limit", "rate_limit", "限流", "频率", "限制")):
        分类 = "rate_limit"
    elif any(词 in 小写 for 词 in ("timeout", "timed out", "超时")):
        分类 = "timeout"
    elif any(词 in 小写 for 词 in ("connection", "connect", "网络", "socket")):
        分类 = "network"
    else:
        分类 = "unknown"

    def _字段值(*名称: str) -> str:
        for 名称项 in 名称:
            try:
                值 = getattr(异常, 名称项, None)
            except Exception:
                值 = None
            if 值 not in (None, ""):
                return str(值).strip()
        return ""

    http_status = _字段值("status", "status_code", "http_status")
    code = _字段值("code", "ret_code", "error_code")
    err_code = _字段值("err_code", "errno", "business_code")
    if not http_status:
        匹配 = re.search(r"(?:HTTP|错误代码|status)[：:= ]+(\d{3})", 文本, re.IGNORECASE)
        http_status = 匹配.group(1) if 匹配 else ""
    if not code:
        匹配 = re.search(r"(?:^|[\s,])code[：:= ]*(-?\d+)", 文本, re.IGNORECASE)
        code = 匹配.group(1) if 匹配 else ""
    if not err_code:
        匹配 = re.search(r"(?:err_code|error_code|errno)[：:= ]*(-?\d+)", 文本, re.IGNORECASE)
        err_code = 匹配.group(1) if 匹配 else ""
    return {
        "error_type": 类型,
        "category": 分类,
        "http_status": http_status,
        "code": code,
        "err_code": err_code,
        "detail": 文本 or "(empty)",
    }


def _构造已移除群摘要(
    会话标识: str, 已有: dict[str, Any] | None = None, appid: str = ""
) -> dict[str, Any]:
    """保留原群会话信息，只把机器人成员状态更新为已移除。"""
    会话标识 = str(会话标识 or "").strip()
    摘要 = dict(已有 or {})
    摘要.setdefault("group_openid", 会话标识)
    摘要["membership_status"] = "removed"
    摘要["membership_checked_at"] = int(time.time())
    if str(appid or "").strip():
        摘要.setdefault("appid", str(appid).strip())
    摘要["is_admin"] = False
    群信息缓存[会话标识] = 摘要
    return 摘要


async def _查询群机器人状态(
    会话标识: str, appid: str = "", 强制: bool = False
) -> dict[str, Any]:
    会话标识 = str(会话标识 or "").strip()
    现有 = _读取群机器人状态(会话标识)
    if not 会话标识 or not _群机器人状态需检查(会话标识, 强制):
        return 现有
    appid = _获取群信息appid(会话标识, appid) if "_获取群信息appid" in globals() else str(appid or "")
    通道 = 获取HTTP通道(获取QQ官方平台(appid=appid))
    if 通道 is None:
        return 现有
    _, _http = 通道
    try:
        from botpy.http import Route

        响应 = await _http.request(
            Route(
                "GET",
                "/v2/groups/{group_openid}/bot_state",
                group_openid=会话标识,
            )
        )
        if not isinstance(响应, dict):
            raise RuntimeError("群机器人状态响应无效")
        if _响应表示群机器人已移除(响应):
            return _设置群机器人状态(会话标识, "removed", appid, 持久化=True)
        错误码 = 响应.get("code")
        if 错误码 not in (None, 0, "", "0"):
            if str(错误码) in {"404", "40400", "10004"}:
                return _设置群机器人状态(会话标识, "removed", appid, 持久化=True)
            return 现有
        成员OpenID = str(响应.get("member_openid") or "").strip()
        if not 成员OpenID:
            raise RuntimeError("群机器人状态缺少成员标识")
        角色 = str(响应.get("member_role") or "member").strip().lower()
        允许主动消息 = 响应.get("allow_proactive_msg")
        if isinstance(允许主动消息, str):
            允许主动消息文本 = 允许主动消息.strip().lower()
            if 允许主动消息文本 in {"true", "1", "yes", "on", "开启"}:
                允许主动消息 = True
            elif 允许主动消息文本 in {"false", "0", "no", "off", "关闭"}:
                允许主动消息 = False
            else:
                允许主动消息 = None
        elif not isinstance(允许主动消息, bool):
            允许主动消息 = None
        记录 = _设置群机器人状态(
            会话标识,
            "active",
            appid,
            角色,
            允许主动消息,
            str(响应.get("recv_msg_setting") or ""),
            持久化=True,
        )
        return 记录
    except Exception as 异常:
        if _异常表示群机器人已移除(异常):
            详情 = _群信息异常摘要(异常)
            logger.info(
                "消息记录群机器人状态：stage=bot_state, group_id=%s, appid=%s, "
                "status=removed, category=%s, http_status=%s, code=%s, err_code=%s, detail=%s",
                会话标识,
                appid,
                详情["category"],
                详情["http_status"] or "unknown",
                详情["code"] or "unknown",
                详情["err_code"] or "unknown",
                详情["detail"],
            )
            return _设置群机器人状态(会话标识, "removed", appid, 持久化=True)
        详情 = _群信息异常摘要(异常)
        logger.warning(
            "消息记录群机器人状态查询失败：stage=bot_state, group_id=%s, appid=%s, "
            "error_type=%s, category=%s, http_status=%s, code=%s, err_code=%s, detail=%s",
            会话标识,
            appid,
            详情["error_type"],
            详情["category"],
            详情["http_status"] or "unknown",
            详情["code"] or "unknown",
            详情["err_code"] or "unknown",
            详情["detail"],
        )
        return 现有


async def 查询群主动消息权限(会话标识: str, appid: str = "") -> bool | None:
    """查询 QQ 官方群内主动消息权限，并复用长期群状态缓存。

    返回 ``True`` 表示允许主动推送，``False`` 表示明确禁止或机器人已
    被移出群，``None`` 表示当前无法从官方状态或缓存确认。私聊没有对应
    的群状态接口，因此只返回已有的发送结果缓存。
    """
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return None
    if not str(appid or "").strip():
        appid = str((_读取群机器人状态(会话标识) or {}).get("appid") or "").strip()
    状态 = await _查询群机器人状态(会话标识, appid)
    if str(状态.get("status") or "").strip().lower() == "removed":
        记录主动消息权限(会话标识, "group", False)
        return False
    权限 = 状态.get("allow_proactive_msg")
    if isinstance(权限, bool):
        记录主动消息权限(会话标识, "group", 权限)
        return 权限
    return 主动消息是否允许(会话标识, "group")


def _获取群信息appid(会话标识: str, appid: str = "") -> str:
    """优先使用调用方提供的 AppID，否则从当前会话恢复。"""
    appid = str(appid or "").strip()
    if appid:
        return appid
    会话 = 消息缓存.get(str(会话标识 or "").strip()) or {}
    return str(会话.get("appid") or "").strip()


def _复制群禁言状态(状态: dict[str, Any], *, cached: bool = False) -> dict[str, Any]:
    结果 = copy.deepcopy(状态 if isinstance(状态, dict) else {})
    结果.setdefault("available", False)
    结果.setdefault("members", [])
    结果.setdefault("global_rule", {})
    结果["cached"] = bool(cached)
    return 结果


async def 查询群禁言状态(
    会话标识: str,
    appid: str = "",
    强制: bool = False,
) -> dict[str, Any]:
    """按 QQ 官方接口读取当前群的成员禁言状态并短时缓存。"""
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return {"available": False, "members": [], "global_rule": {}, "checked_at": 0}
    appid = _获取群信息appid(会话标识, appid)
    缓存键 = (appid, 会话标识)
    现在 = time.time()
    现有 = 群禁言状态缓存.get(缓存键)
    if (
        not 强制
        and isinstance(现有, dict)
        and float(现有.get("next_refresh_at") or 0) > 现在
    ):
        return _复制群禁言状态(现有, cached=True)

    async with _群禁言状态请求锁:
        现在 = time.time()
        现有 = 群禁言状态缓存.get(缓存键)
        if (
            not 强制
            and isinstance(现有, dict)
            and float(现有.get("next_refresh_at") or 0) > 现在
        ):
            return _复制群禁言状态(现有, cached=True)
        try:
            from botpy.http import Route

            平台 = 获取QQ官方平台(appid=appid)
            通道 = 获取HTTP通道(平台)
            if 通道 is None:
                raise RuntimeError("QQ官方HTTP通道未加载")
            _, _http = 通道
            响应 = await _http.request(
                Route(
                    "GET",
                    "/v2/groups/{group_openid}/restrict_chat_setting",
                    group_openid=会话标识,
                )
            )
            if not isinstance(响应, dict):
                raise RuntimeError("禁言状态响应格式无效")
            错误码 = 响应.get("code")
            if 错误码 not in (None, 0, "", "0"):
                raise RuntimeError(f"禁言状态业务错误：code={错误码}")
            成员列表: list[dict[str, Any]] = []
            for 成员 in 响应.get("members") or []:
                if not isinstance(成员, dict):
                    continue
                成员标识 = str(
                    成员.get("member_openid") or 成员.get("union_openid") or ""
                ).strip()
                if not 成员标识:
                    continue
                到期文本 = str(成员.get("mute_expire_at") or "").strip()
                到期时间 = _转数字时间戳(到期文本) or 0
                if 到期时间 and 到期时间 <= 现在:
                    continue
                成员列表.append(
                    {
                        "member_openid": 成员标识,
                        "username": str(成员.get("username") or "").strip(),
                        "mute_expire_at": 到期文本,
                        "mute_expire_ts": int(到期时间) if 到期时间 else 0,
                    }
                )
            全员规则 = 响应.get("global_rule")
            if not isinstance(全员规则, dict):
                全员规则 = {}
            状态 = {
                "available": True,
                "members": 成员列表,
                "global_rule": {
                    "mode": str(全员规则.get("mode") or "none").strip(),
                },
                "checked_at": int(现在),
                "next_refresh_at": 现在 + 群禁言状态缓存有效期秒,
            }
            群禁言状态缓存[缓存键] = 状态
            return _复制群禁言状态(状态)
        except Exception as 异常:
            logger.warning(
                "消息记录群禁言状态查询失败：stage=restrict_chat_setting, "
                "group_id=%s, appid=%s, error_type=%s, cooldown=%s",
                会话标识,
                appid,
                type(异常).__name__,
                群禁言状态失败冷却秒,
            )
            失败状态 = dict(现有) if isinstance(现有, dict) else {}
            失败状态.update(
                {
                    "available": False,
                    "checked_at": int(现在),
                    "next_refresh_at": 现在 + 群禁言状态失败冷却秒,
                }
            )
            失败状态.setdefault("members", [])
            失败状态.setdefault("global_rule", {})
            群禁言状态缓存[缓存键] = 失败状态
            return _复制群禁言状态(失败状态, cached=bool(现有))


def _群信息需要刷新(信息: dict[str, Any] | None) -> bool:
    """判断群资料是否需要后台更新；失败冷却期间保留旧资料。"""
    信息 = 信息 if isinstance(信息, dict) else {}
    现在 = int(time.time())
    try:
        下次刷新 = int(信息.get("next_refresh_at") or 0)
    except (TypeError, ValueError):
        下次刷新 = 0
    if 下次刷新 > 现在:
        return False
    try:
        更新时间 = int(信息.get("updated_at") or 0)
    except (TypeError, ValueError):
        更新时间 = 0
    return 更新时间 <= 0 or 现在 - 更新时间 >= 群信息刷新间隔秒


async def 刷新待处理群信息() -> int:
    """批量刷新待处理群信息，返回成功数量（加锁防并发，逐个带间隔避免限流）。"""
    if not 群信息待刷新:
        return 0
    async with _群信息刷新锁:
        if not 群信息待刷新:
            return 0
        批次 = list(群信息待刷新)[:10]
        群信息待刷新.clear()
        成功数 = 0
        for 会话标识 in 批次:
            try:
                结果 = await 刷新群信息(会话标识)
                if 结果:
                    成功数 += 1
            except Exception as exc:
                logger.warning("消息记录群信息后台刷新失败：错误类型=%s", type(exc).__name__)
            # 官方接口限制为 30 QPM，后台刷新保持更低的请求速率。
            await asyncio.sleep(群信息请求间隔秒)
    return 成功数


def 安排待处理群信息刷新() -> None:
    """为待刷新群资料复用单个后台任务，避免网页轮询重复排队。"""
    global _群信息刷新任务
    if not 群信息待刷新:
        return
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return
    if (
        _群信息刷新任务 is not None
        and not _群信息刷新任务.done()
        and getattr(_群信息刷新任务, "get_loop", lambda: None)() is 循环
    ):
        return
    _群信息刷新任务 = 循环.create_task(刷新待处理群信息())


def _获取群信息轮询候选() -> list[str]:
    """收集已知官方群，跳过已确认退出的群，保持轮询只覆盖已有会话。"""
    候选: set[str] = set()
    for 会话标识, 信息 in 群信息缓存.items():
        会话标识 = str(会话标识 or "").strip()
        if not isinstance(信息, dict):
            continue
        信息字典 = 信息
        if not 会话标识 or str(信息字典.get("membership_status") or "").lower() == "removed":
            continue
        候选.add(会话标识)
    for 会话标识, 会话 in 消息缓存.items():
        会话标识 = str(会话标识 or "").strip()
        if not isinstance(会话, dict):
            continue
        会话字典 = 会话
        if not 会话标识 or str(会话字典.get("chat_type") or "group") != "group":
            continue
        if 获取群机器人状态(会话标识) == "removed":
            continue
        候选.add(会话标识)
    return list(候选)


async def _群信息轮询工作() -> None:
    """低频轮询群基本信息，实际请求复用待刷新队列的串行限流。"""
    global _群信息轮询任务
    try:
        while True:
            await asyncio.sleep(群信息轮询检查间隔秒)
            try:
                for 会话标识 in _获取群信息轮询候选():
                    if _群信息需要刷新(群信息缓存.get(会话标识)):
                        标记群信息待刷新(会话标识)
                安排待处理群信息刷新()
            except Exception as 异常:
                logger.debug("消息记录群信息轮询检查失败：错误类型=%s", type(异常).__name__)
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        logger.debug("消息记录群信息轮询任务停止：错误类型=%s", type(异常).__name__)
    finally:
        当前任务 = asyncio.current_task()
        if _群信息轮询任务 is 当前任务:
            _群信息轮询任务 = None


def _启动群信息轮询任务() -> asyncio.Task[Any] | None:
    """启动单个群资料轮询任务，热重载时避免重复创建。"""
    global _群信息轮询任务
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return None
    if (
        _群信息轮询任务 is None
        or _群信息轮询任务.done()
        or getattr(_群信息轮询任务, "get_loop", lambda: None)() is not 循环
    ):
        _群信息轮询任务 = 循环.create_task(_群信息轮询工作())
    return _群信息轮询任务


def _群信息冷却秒数(异常: Exception) -> int:
    """按错误类型返回冷却秒数，避免失败时持续触碰官方群信息接口。"""
    try:
        文本 = str(异常)
    except Exception:
        文本 = ""
    if "注销" in 文本 or "不存在" in 文本:
        return 86400
    if "频率" in 文本 or "限流" in 文本 or "限制" in 文本:
        return 群信息限流冷却秒
    return 群信息默认失败冷却秒


async def 刷新群信息(
    会话标识: str, appid: str = "", 强制: bool = False
) -> dict[str, Any] | None:
    """按需调用 QQ 官方群资料接口；成功结果写入数据库长期保存。"""
    if not 会话标识:
        return None
    已有 = 群信息缓存.get(会话标识) or {}
    if not 强制 and not _群信息需要刷新(已有):
        return None
    if 强制:
        try:
            上次请求 = int(已有.get("last_request_at") or 0)
        except (TypeError, ValueError):
            上次请求 = 0
        现在 = int(time.time())
        if 上次请求 and 现在 - 上次请求 < 群信息人工最短间隔秒:
            logger.info(
                "消息记录群信息刷新被频率保护：group_id=%s, cooldown=%s",
                会话标识,
                群信息人工最短间隔秒 - (现在 - 上次请求),
            )
            return None
        已有 = dict(已有)
        已有["last_request_at"] = 现在
        群信息缓存[会话标识] = 已有
    appid = _获取群信息appid(会话标识, appid)
    成员状态 = await _查询群机器人状态(会话标识, appid, 强制=强制)
    if 成员状态.get("status") == "removed":
        return _构造已移除群摘要(会话标识, 已有, appid)
    通道 = 获取HTTP通道(获取QQ官方平台(appid=appid))
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
        错误码 = 结果.get("code") if isinstance(结果, dict) else None
        有群资料字段 = isinstance(结果, dict) and any(
            字段 in 结果
            for 字段 in (
                "group_openid",
                "group_name",
                "group_finger_memo",
                "group_class_text",
                "group_tags",
                "group_member_num",
            )
        )
        if (
            not isinstance(结果, dict)
            or not 有群资料字段
            or 错误码 not in (None, 0, "0", "")
        ):
            if _响应表示群机器人已移除(结果):
                _设置群机器人状态(会话标识, "removed", appid, 持久化=True)
                return _构造已移除群摘要(会话标识, 已有, appid)
            失败缓存 = dict(已有)
            失败缓存.setdefault("group_openid", 会话标识)
            # 非成功业务响应也进入长冷却，防止权限/接口异常时每次打开会话都重试。
            失败缓存["next_refresh_at"] = int(time.time()) + 群信息默认失败冷却秒
            群信息缓存[会话标识] = 失败缓存
            返回字段 = (
                ",".join(sorted(str(字段) for 字段 in 结果.keys()))
                if isinstance(结果, dict)
                else ""
            )
            logger.warning(
                "消息记录群信息响应无效：stage=group_info_response, group_id=%s, appid=%s, "
                "response_type=%s, code=%s, fields=%s, cooldown=%s",
                会话标识,
                appid,
                type(结果).__name__,
                str(错误码 or "unknown"),
                返回字段 or "none",
                群信息默认失败冷却秒,
            )
            return None
        标签 = 结果.get("group_tags") if "group_tags" in 结果 else 已有.get("group_tags")
        if not isinstance(标签, (list, tuple)):
            标签 = [] if 标签 in (None, "") else [标签]
        标签 = [str(值).strip() for 值 in 标签 if str(值 or "").strip()]
        原始成员数 = (
            结果.get("group_member_num")
            if "group_member_num" in 结果
            else 已有.get("member_num")
        )
        try:
            成员数 = max(0, int(原始成员数 or 0))
        except (TypeError, ValueError):
            try:
                成员数 = max(0, int(已有.get("member_num") or 0))
            except (TypeError, ValueError):
                成员数 = 0
        群名 = 结果.get("group_name") if "group_name" in 结果 else 已有.get("group_name")
        群备注 = (
            结果.get("group_finger_memo")
            if "group_finger_memo" in 结果
            else 已有.get("group_finger_memo")
        )
        群分类 = (
            结果.get("group_class_text")
            if "group_class_text" in 结果
            else 已有.get("group_class_text")
        )
        机器人是否管理员 = str(成员状态.get("member_role") or "") in ("owner", "admin")
        摘要 = {
            "group_openid": str(结果.get("group_openid") or 会话标识),
            "appid": appid,
            "group_name": str(群名 or ""),
            "group_finger_memo": str(群备注 or ""),
            "group_class_text": str(群分类 or ""),
            "group_tags": 标签,
            "member_num": 成员数,
            "is_admin": 机器人是否管理员,
            "membership_status": str(成员状态.get("status") or "unknown"),
            "membership_checked_at": int(成员状态.get("checked_at") or time.time()),
            "updated_at": int(time.time()),
            "last_request_at": int(已有.get("last_request_at") or 0),
        }
        群信息缓存[会话标识] = 摘要
        if _消息存储 is not None:
            try:
                写入群信息 = getattr(_消息存储, "写入群信息", None)
                if callable(写入群信息):
                    await _异步执行消息记录同步(写入群信息, 摘要, appid)
            except Exception as 存储异常:
                logger.debug(
                    "消息记录群资料持久化失败：错误类型=%s",
                    type(存储异常).__name__,
                )
        return 摘要
    except Exception as exc:
        if _异常表示群机器人已移除(exc):
            详情 = _群信息异常摘要(exc)
            logger.info(
                "消息记录群信息：stage=group_info, group_id=%s, appid=%s, "
                "status=removed, category=%s, http_status=%s, code=%s, err_code=%s, detail=%s",
                会话标识,
                appid,
                详情["category"],
                详情["http_status"] or "unknown",
                详情["code"] or "unknown",
                详情["err_code"] or "unknown",
                详情["detail"],
            )
            _设置群机器人状态(会话标识, "removed", appid, 持久化=True)
            return _构造已移除群摘要(会话标识, 已有, appid)
        冷却秒数 = _群信息冷却秒数(exc)
        失败缓存 = dict(已有)
        失败缓存.setdefault("group_openid", 会话标识)
        失败缓存["next_refresh_at"] = int(time.time()) + 冷却秒数
        群信息缓存[会话标识] = 失败缓存
        详情 = _群信息异常摘要(exc)
        logger.warning(
            "消息记录群信息刷新失败：stage=group_info, group_id=%s, appid=%s, "
            "error_type=%s, category=%s, http_status=%s, code=%s, err_code=%s, detail=%s, cooldown=%s",
            会话标识,
            appid,
            详情["error_type"],
            详情["category"],
            详情["http_status"] or "unknown",
            详情["code"] or "unknown",
            详情["err_code"] or "unknown",
            详情["detail"],
            冷却秒数,
        )
        return None


def 群机器人是否管理员(会话标识: str) -> bool:
    """检查机器人在该群是否具备管理员权限。"""
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return False
    群信息 = 群信息缓存.get(会话标识) or {}
    if "is_admin" in 群信息:
        return bool(群信息.get("is_admin"))
    try:
        from 功能文件.管理功能.群聊功能 import 群管功能
        for (_, gid), (_, 允许) in getattr(群管功能, "QQ官方机器人权限缓存", {}).items():
            if str(gid).strip() == 会话标识:
                return bool(允许)
    except Exception:
        pass
    return False


def 获取缓存的群信息(会话标识: str) -> dict[str, Any]:
    信息 = 群信息缓存.get(会话标识) or {}
    会话 = 消息缓存.get(会话标识) or {}
    返回 = dict(信息)
    返回.pop("next_refresh_at", None)
    返回.setdefault("group_openid", 会话标识)
    返回.setdefault("group_name", 获取群备注(会话标识) or "")
    返回.setdefault("group_finger_memo", "")
    返回.setdefault("group_class_text", "")
    返回.setdefault("group_tags", [])
    返回.setdefault("member_num", 0)
    成员状态 = _读取群机器人状态(会话标识)
    返回.setdefault("membership_status", str(成员状态.get("status") or "unknown"))
    返回.setdefault("membership_checked_at", int(成员状态.get("checked_at") or 0))
    if isinstance(成员状态.get("allow_proactive_msg"), bool):
        返回.setdefault("allow_proactive_msg", 成员状态["allow_proactive_msg"])
    else:
        返回.setdefault("allow_proactive_msg", None)
    返回.setdefault("recv_msg_setting", str(成员状态.get("recv_msg_setting") or ""))
    返回["in_group"] = 返回.get("membership_status") != "removed"
    return 返回


# ---------------------------------------------------------------------------
# 聊天列表与历史
# ---------------------------------------------------------------------------

def _聊天显示名(
    会话标识: str,
    会话: dict[str, Any],
    备注表: dict[str, Any] | None = None,
) -> str:
    if 备注表 is None:
        备注表 = (_读取本地缓存文件().get("remarks") or {})
    if not isinstance(备注表, dict):
        备注表 = {}
    备注项 = 备注表.get(会话标识) or {}
    备注 = str(备注项.get("remark") or "")
    if 备注:
        return 备注
    信息 = 群信息缓存.get(会话标识) or {}
    群名 = str(信息.get("group_name") or "")
    if 群名:
        return 群名
    最近昵称 = str(会话.get("last_nickname") or "")
    # 群会话不把机器人和网页发送昵称当作群名退路，避免群名被"机器人"/"我"污染
    if 最近昵称 and ((str(会话.get("chat_type") or "") == "user") or 最近昵称 not in ("机器人", "我")):
        return 最近昵称
    if str(会话.get("chat_type") or "") == "user":
        本地昵称 = str((_读取本地缓存文件().get("nicknames") or {}).get(会话标识) or "")
        if 本地昵称:
            return 本地昵称
        return _私聊兜底昵称(会话标识)
    return 会话标识


def _聊天群成员状态(会话标识: str, 类型: str) -> dict[str, Any]:
    if str(类型 or "") != "group":
        return {"in_group": True, "membership_status": "active", "membership_checked_at": 0}
    状态 = _读取群机器人状态(会话标识)
    return {
        "in_group": 状态.get("status") != "removed",
        "membership_status": str(状态.get("status") or "unknown"),
        "membership_checked_at": int(状态.get("checked_at") or 0),
    }


def _聊天已移除(聊天: dict[str, Any]) -> bool:
    """返回会话是否已确认机器人被移出群聊。"""
    if str(聊天.get("chat_type") or "group") != "group":
        return False
    状态 = str(聊天.get("membership_status") or "").strip().lower()
    不在群 = 聊天.get("in_group") is False or str(聊天.get("in_group") or "").strip().lower() == "false"
    return 状态 == "removed" or 不在群


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
                聊天["nickname"] = 本地昵称
                continue
            兜底 = _私聊兜底昵称(会话标识)
            if 会话 and (not str(会话.get("last_nickname") or "").strip() or "未知" in str(会话.get("last_nickname") or "")):
                会话["last_nickname"] = 兜底
            聊天["nickname"] = 兜底
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
        持久化未读表 = _读取全部持久化未读数()
        for 会话标识 in _消息存储.读取全部会话标识():
            会话标识 = str(会话标识 or "").strip()
            if not 会话标识 or 会话标识 in 消息缓存:
                continue
            消息列表 = [_规范化历史消息(x) for x in (_消息存储.读取会话消息(会话标识, 每会话最大消息数) or [])]
            消息列表.sort(key=_历史消息排序键)
            if not 消息列表:
                continue
            类型 = str(消息列表[-1].get("chat_type") or "group")
            会话 = _取得会话缓存(会话标识, 类型, str(消息列表[-1].get("appid") or ""))
            if 会话标识 not in _未读待写 and 会话标识 in 持久化未读表:
                会话["unread"] = max(0, int(持久化未读表.get(会话标识) or 0))
            会话["messages"] = 消息列表
            最后 = 消息列表[-1]
            会话["last_content"] = _替换提及名称(最后.get("content") or "", 会话标识)
            会话["last_nickname"] = str(最后.get("nickname") or "")
            会话["last_ts"] = max(int(会话.get("last_ts") or 0), int(最后.get("ts") or 0))
            已加载 = True
        if 已加载:
            logger.debug("消息记录会话已从数据库补回内存")
    except Exception as exc:
        logger.debug("消息记录数据库会话补回失败：错误类型=%s", type(exc).__name__)


def _数据库聚合聊天项(
    过滤: str, 搜索: str, 本地数据: dict[str, Any], 置顶顺序: dict[str, int]
) -> list[dict[str, Any]] | None:
    """对齐 ElainaBot：单次 MySQL GROUP BY 聚合所有会话，返回聊天列表项；不可用时返回 None。

    等价于 ElainaBot 的 _aggregate_chats_sync（SQLite GROUP BY group_id + 前 200 会话
    按 id 批量补查 last_content），这里用 MySQL 的 聚合聊天列表 + 批量读取最后消息 实现。
    """
    if _消息存储 is None:
        return None
    try:
        # 控制台群列表使用全部模式；消息历史仍由单独接口按 100 条分页。
        骨架 = _消息存储.聚合聊天列表(0)
        # 被移除的群可能没有任何消息行，单靠消息表聚合会把它们漏掉。
        # 启动恢复已经把群资料放入内存，列表刷新优先使用缓存，避免每次
        # 打开消息页再建立一次数据库连接；缓存为空时保留持久化兜底。
        群信息项: dict[str, dict[str, Any]] = {}
        for 群标识, 信息 in 群信息缓存.items():
            群标识 = str(群标识 or "").strip()
            if not 群标识 or not isinstance(信息, dict):
                continue
            群信息项[群标识] = dict(信息)
        if not 群信息项:
            读取群信息 = getattr(_消息存储, "读取全部群信息", None)
            持久化群信息 = 读取群信息() if callable(读取群信息) else []
            for 信息 in 持久化群信息 or []:
                if not isinstance(信息, dict):
                    continue
                群标识 = str(信息.get("group_openid") or "").strip()
                if 群标识:
                    群信息项[群标识] = dict(信息)
        if not 骨架 and not 群信息项:
            return None
        最后id列表 = [int(项.get("last_id") or 0) for 项 in 骨架 if int(项.get("last_id") or 0)]
        # 会话列表只需最后消息的预览和元数据，不把卡片原文/媒体字段整批读回。
        if 最后id列表:
            # 热重载期间可能暂时仍持有旧版存储模块，保留完整读取作为兼容退路。
            读取摘要 = getattr(_消息存储, "批量读取最后消息摘要", None)
            if not callable(读取摘要):
                读取摘要 = getattr(_消息存储, "批量读取最后消息", None)
            if not callable(读取摘要):
                raise AttributeError("消息存储缺少最后消息读取方法")
            最后消息表 = 读取摘要(最后id列表)
        else:
            最后消息表 = {}
        本地备注表 = (本地数据.get("remarks") or {})
        持久化未读表 = _读取全部持久化未读数()
        聊天项: list[dict[str, Any]] = []
        已有会话标识: set[str] = set()
        for 项 in 骨架:
            会话标识 = str(项.get("会话标识") or "")
            if not 会话标识:
                continue
            已有会话标识.add(会话标识)
            最后记录 = 最后消息表.get(int(项.get("last_id") or 0)) or {}
            _规范化聊天摘要(最后记录)
            类型 = str(最后记录.get("chat_type") or "group")
            if 过滤 == "group" and 类型 != "group":
                continue
            if 过滤 == "user" and 类型 != "user":
                continue
            会话备注 = 本地备注表.get(会话标识) or {}
            备注 = str(会话备注.get("remark") or "")
            if 过滤 == "remark" and not 备注:
                continue
            内存会话 = 消息缓存.get(会话标识) or {}
            内存消息列表 = 内存会话.get("messages") or []
            内存最后时间 = int(内存会话.get("last_ts") or 0)
            数据库最后时间 = max(
                int(项.get("last_ts") or 0),
                int(最后记录.get("ts") or 0),
            )
            if 内存最后时间 >= 数据库最后时间 and (内存最后时间 or 内存会话.get("last_content")):
                # 接收路径已经维护会话摘要，列表请求无需遍历和规范化整段内存消息。
                内存最后记录 = 内存消息列表[-1] if 内存消息列表 else {}
                最后记录 = {
                    "chat_type": str(内存会话.get("chat_type") or 类型),
                    "nickname": str(内存会话.get("last_nickname") or ""),
                    "appid": str(内存会话.get("appid") or ""),
                    "content": str(内存会话.get("last_content") or ""),
                    "avatar": str(
                        (
                            内存最后记录.get("avatar")
                            if isinstance(内存最后记录, dict)
                            else ""
                        )
                        or 最后记录.get("avatar")
                        or ""
                    ).strip(),
                    "timestamp": _格式化时间戳(内存最后时间),
                    "ts": 内存最后时间,
                }
                类型 = str(最后记录.get("chat_type") or 类型)
            轻量会话 = {
                "chat_type": 类型,
                "last_nickname": str(最后记录.get("nickname") or 内存会话.get("last_nickname") or ""),
                "appid": str(最后记录.get("appid") or 内存会话.get("appid") or ""),
            }
            显示名 = _聊天显示名(会话标识, 轻量会话, 本地备注表)
            if 搜索 and 搜索 not in 显示名 and 搜索 not in 会话标识:
                continue
            last_ts = int(最后记录.get("ts") or 项.get("last_ts") or 0)
            if 会话标识 in 消息缓存:
                # 待写值代表当前事件循环的最新状态；没有待写值时，
                # 合并内存与持久化值，避免重启或多标签页时红点回退。
                if 会话标识 in _未读待写:
                    当前未读数 = _未读待写[会话标识]
                elif 会话标识 in 持久化未读表:
                    当前未读数 = max(
                        int(内存会话.get("unread") or 0),
                        int(持久化未读表.get(会话标识) or 0),
                    )
                else:
                    当前未读数 = int(内存会话.get("unread") or 0)
            elif 会话标识 in _未读待写:
                当前未读数 = _未读待写[会话标识]
            elif 会话标识 in 持久化未读表:
                当前未读数 = 持久化未读表[会话标识]
            else:
                当前未读数 = int(内存会话.get("unread") or 0)
            聊天项.append(
                {
                    "chat_id": 会话标识,
                    "chat_type": 类型,
                    "appid": str(最后记录.get("appid") or 内存会话.get("appid") or ""),
                    "nickname": 显示名,
                    "avatar": str(最后记录.get("avatar") or "").strip(),
                    "group_qq": str(会话备注.get("group_qq") or ""),
                    "last_content": _替换提及名称(
                        _表情标签规则.sub(
                            lambda 匹配: _解码表情文本(匹配.group(0)),
                            str(最后记录.get("content") or ""),
                        ),
                        会话标识,
                    ),
                    "last_time": _格式化时间戳(last_ts) or str(最后记录.get("timestamp") or ""),
                    "last_ts": last_ts,
                    "msg_count": max(
                        int(项.get("msg_count") or 0),
                        int(内存会话.get("msg_count") or 0),
                        len(内存消息列表),
                    ),
                    "unread": max(0, int(当前未读数 or 0)),
                    "remark": 备注,
                    **_聊天群成员状态(会话标识, 类型),
                    "is_admin": bool(群机器人是否管理员(会话标识)) if 类型 == "group" else False,
                    "group_name": str(群信息缓存.get(会话标识, {}).get("group_name") or ""),
                }
            )
        # 没有消息记录的群也要进入列表，尤其是已被移除且需要长期保留提示的群。
        for 信息 in 群信息项.values():
            会话标识 = str(信息.get("group_openid") or "").strip()
            if not 会话标识 or 会话标识 in 已有会话标识:
                continue
            已有会话标识.add(会话标识)
            会话备注 = 本地备注表.get(会话标识) or {}
            备注 = str(会话备注.get("remark") or "")
            if 过滤 == "remark" and not 备注:
                continue
            群名 = str(信息.get("group_name") or "").strip()
            轻量会话 = {
                "chat_type": "group",
                "last_nickname": 群名,
                "appid": str(信息.get("appid") or ""),
            }
            显示名 = _聊天显示名(会话标识, 轻量会话, 本地备注表)
            if 搜索 and 搜索 not in 显示名 and 搜索 not in 会话标识:
                continue
            当前未读数 = _未读待写.get(
                会话标识,
                int(持久化未读表.get(会话标识) or 0),
            )
            聊天项.append(
                {
                    "chat_id": 会话标识,
                    "chat_type": "group",
                    "appid": str(信息.get("appid") or ""),
                    "nickname": 显示名,
                    "group_qq": str(会话备注.get("group_qq") or ""),
                    "last_content": "",
                    "last_time": "",
                    "last_ts": 0,
                    "msg_count": 0,
                    "unread": max(0, int(当前未读数 or 0)),
                    "remark": 备注,
                    **_聊天群成员状态(会话标识, "group"),
                    "is_admin": bool(群机器人是否管理员(会话标识)),
                    "group_name": 群名,
                }
            )
        # 数据库写入线程尚未提交时，GROUP BY 不会包含刚收到的新会话。
        # 追加内存会话即可让 SSE 触发的列表刷新立即看到消息和红点。
        for 会话标识, 内存会话 in list(消息缓存.items()):
            会话标识 = str(会话标识 or "").strip()
            if not 会话标识 or 会话标识 in 已有会话标识:
                continue
            类型 = str(内存会话.get("chat_type") or "group")
            if 过滤 == "group" and 类型 != "group":
                continue
            if 过滤 == "user" and 类型 != "user":
                continue
            会话备注 = 本地备注表.get(会话标识) or {}
            备注 = str(会话备注.get("remark") or "")
            if 过滤 == "remark" and not 备注:
                continue
            显示名 = _聊天显示名(会话标识, 内存会话, 本地备注表)
            if 搜索 and 搜索 not in 显示名 and 搜索 not in 会话标识:
                continue
            消息列表 = 内存会话.get("messages") or []
            最后记录 = 消息列表[-1] if 消息列表 else {}
            最后内容 = str(内存会话.get("last_content") or 最后记录.get("content") or "")
            最后时间 = int(内存会话.get("last_ts") or 最后记录.get("ts") or 0)
            当前未读数 = _未读待写.get(会话标识, int(内存会话.get("unread") or 0))
            聊天项.append(
                {
                    "chat_id": 会话标识,
                    "chat_type": 类型,
                    "appid": str(内存会话.get("appid") or 最后记录.get("appid") or ""),
                    "nickname": 显示名,
                    "avatar": str(最后记录.get("avatar") or "").strip(),
                    "group_qq": str(会话备注.get("group_qq") or ""),
                    "last_content": _替换提及名称(
                        _表情标签规则.sub(lambda 匹配: _解码表情文本(匹配.group(0)), 最后内容),
                        会话标识,
                    ),
                    "last_time": _格式化时间戳(最后时间) or str(最后记录.get("timestamp") or ""),
                    "last_ts": 最后时间,
                    "msg_count": max(int(内存会话.get("msg_count") or 0), len(消息列表)),
                    "unread": max(0, int(当前未读数 or 0)),
                    "remark": 备注,
                    **_聊天群成员状态(会话标识, 类型),
                    "is_admin": bool(群机器人是否管理员(会话标识)) if 类型 == "group" else False,
                    "group_name": str(群信息缓存.get(会话标识, {}).get("group_name") or ""),
                }
            )
        for 聊天 in 聊天项:
            聊天["pinned"] = str(聊天.get("chat_id") or "") in 置顶顺序
        return 聊天项
    except Exception as exc:
        logger.debug("消息记录数据库聊天聚合失败，回退内存：错误类型=%s", type(exc).__name__)
        return None


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
        原始每页 = int(每页)
        每页 = 0 if 原始每页 <= 0 else min(100, 原始每页)
    except (TypeError, ValueError):
        页码, 每页 = 1, 50
    本地数据 = _读取本地缓存文件()
    本地备注表 = (本地数据.get("remarks") or {})
    置顶列表 = [str(x) for x in (本地数据.get("pinned") or []) if str(x or "").strip()]
    置顶顺序 = {会话: idx for idx, 会话 in enumerate(置顶列表)}
    # 对齐 ElainaBot：数据库 GROUP BY 聚合优先，不可用时回退内存缓存
    聊天列表: list[dict[str, Any]] | None = _数据库聚合聊天项(过滤, 搜索, 本地数据, 置顶顺序)
    if 聊天列表 is None:
        聊天列表 = []
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
            显示名 = _聊天显示名(会话标识, 会话, 本地备注表)
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
                    "avatar": str(最后消息.get("avatar") or "").strip(),
                    "group_qq": str(会话备注.get("group_qq") or ""),
                    "last_content": _替换提及名称(
                        _表情标签规则.sub(
                            lambda 匹配: _解码表情文本(匹配.group(0)),
                            str(最后消息.get("content") or 会话.get("last_content") or ""),
                        ),
                        会话标识,
                    ),
                    "last_time": str(最后消息.get("timestamp") or _格式化时间戳(会话.get("last_ts"))),
                    "last_ts": int(会话.get("last_ts") or 0),
                    "msg_count": max(int(会话.get("msg_count") or 0), len(消息列表)),
                    "unread": int(会话.get("unread") or 0),
                    "remark": 备注,
                    **_聊天群成员状态(会话标识, 类型),
                    "is_admin": bool(群机器人是否管理员(会话标识)) if 类型 == "group" else False,
                    "group_name": str(群信息缓存.get(会话标识, {}).get("group_name") or ""),
                }
            )
        for 聊天 in 聊天列表:
            聊天["pinned"] = str(聊天.get("chat_id") or "") in 置顶顺序
    # 已移除群聊始终放在列表底部；正常会话中手动置顶仍在最前，
    # 未读数只显示红点，不改变已读会话的位置。
    聊天列表.sort(
        key=lambda x: (
            1 if _聊天已移除(x) else 0,
            0 if str(x.get("chat_id") or "") in 置顶顺序 else 1,
            -(x.get("last_ts") or 0),
            str(x.get("chat_id") or ""),
        )
    )
    总数 = len(聊天列表)
    if 每页 <= 0:
        返回聊天 = 聊天列表
    else:
        开始 = (页码 - 1) * 每页
        返回聊天 = 聊天列表[开始 : 开始 + 每页]
    return {
        "chats": 返回聊天,
        "total": 总数,
        "page": 页码,
        "page_size": 每页,
    }


def _数据库历史消息(
    会话标识: str, 类型: str, before_date: str, limit: int, before_id: int = 0,
) -> dict[str, Any] | None:
    """对齐 ElainaBot：从 MySQL 分页读取会话历史；不可用时返回 None 由调用方回退内存。

    等价于 ElainaBot 的 _query_chat_messages_sync（按 id 倒序分页）。
    优先使用 before_id，避免历史记录中的旧时区文本影响分页。
    """
    if _消息存储 is None:
        return None
    try:
        before_ts = 0 if before_id else int(_转数字时间戳(before_date) or 0)
        行列表 = _消息存储.分页读取历史(
            会话标识,
            before_id=max(0, int(before_id or 0)),
            上限=limit,
            before_ts=before_ts,
            返回额外=True,
        )
        if not 行列表:
            return None
        数据库有更多 = len(行列表) > limit
        if 数据库有更多:
            # 查询多取一条只用于判断分页，不把探测行返回给网页。
            行列表 = 行列表[:limit]
        原始会话消息: list[dict[str, Any]] = [
            _规范化历史消息(x) for x in reversed(行列表)
        ]
        原始数量 = len(原始会话消息)
        会话消息: list[dict[str, Any]] = _去重消息列表(原始会话消息)
        会话消息.sort(key=_历史消息排序键)
        返回消息 = 会话消息[-limit:]
        # 消息先写入内存再异步落库；数据库查询可能早于写入线程完成，
        # 因此把本进程尚未出现在本页的接收/发送记录一起合并，避免实时消息延迟。
        内存会话 = 消息缓存.get(会话标识) or {}
        内存消息记录 = [
            _规范化历史消息(消息项) for 消息项 in (内存会话.get("messages") or [])
        ]
        已有记录键 = {
            (
                _规范消息ID(消息项.get("message_id")),
                str(消息项.get("content") or ""),
                int(消息项.get("ts") or 0),
            )
            for 消息项 in 返回消息
        }
        for 消息项 in 内存消息记录:
            if before_id and int(消息项.get("id") or 0) >= before_id:
                continue
            if not before_id and before_date and int(消息项.get("ts") or 0) >= int(_转数字时间戳(before_date) or 0):
                continue
            记录键 = (
                _规范消息ID(消息项.get("message_id")),
                str(消息项.get("content") or ""),
                int(消息项.get("ts") or 0),
            )
            if 记录键 not in 已有记录键:
                返回消息.append(消息项)
                已有记录键.add(记录键)
        返回消息 = _去重消息列表(返回消息)
        返回消息.sort(key=_历史消息排序键)
        返回消息 = 返回消息[-limit:]
        最后消息 = 返回消息[-1] if 返回消息 else {}
        消息索引 = {_规范消息ID(m.get("message_id")): m for m in 返回消息 if _规范消息ID(m.get("message_id"))}
        引用映射: dict[str, dict[str, str]] = {}
        for 消息记录项 in 返回消息:
            引用ID = str(消息记录项.get("reference_id") or "").strip()
            if not 引用ID or 引用ID in 引用映射:
                continue
            被引用 = 消息索引.get(引用ID)
            if 被引用:
                引用映射[引用ID] = {
                    "nickname": str(被引用.get("nickname") or ""),
                    "content": _替换提及名称(被引用.get("content") or "", 会话标识),
                    "timestamp": str(被引用.get("timestamp") or ""),
                }
        for 历史项 in 返回消息:
            if isinstance(历史项, dict) and 历史项.get("raw_message"):
                历史项["raw_message"] = _序列化原始消息(历史项.get("raw_message"), 3000)
            if isinstance(历史项, dict) and 历史项.get("content"):
                历史项["content"] = _表情标签规则.sub(lambda 匹配: _解码表情文本(匹配.group(0)), str(历史项.get("content") or ""))
        内存会话 = 消息缓存.get(会话标识) or {}
        轻量会话 = {
            "chat_type": 类型,
            "last_nickname": str(最后消息.get("nickname") or 内存会话.get("last_nickname") or ""),
            "appid": str(最后消息.get("appid") or ""),
        }
        return {
            "messages": 返回消息,
            "last_msg_id": str(最后消息.get("message_id") or ""),
            "oldest_date": str(会话消息[0].get("timestamp") or "") if 会话消息 else "",
            "has_more": 数据库有更多,
            "chat_name": _聊天显示名(会话标识, 轻量会话),
            "group_info": 获取缓存的群信息(会话标识),
            "is_admin": bool(群机器人是否管理员(会话标识)) if 类型 == "group" else False,
            "member_profiles": _获取消息相关成员资料(会话标识, 返回消息),
            "references": 引用映射,
        }
    except Exception as exc:
        logger.debug("消息记录数据库历史读取失败，回退内存：错误类型=%s", type(exc).__name__)
        return None


def 获取消息历史(
    会话标识: str,
    类型: str = "group",
    before_date: str = "",
    limit: int = 100,
    before_id: int = 0,
) -> dict[str, Any]:
    会话标识 = str(会话标识 or "").strip()
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        limit = 100
    if 类型 == "group" and _群信息需要刷新(群信息缓存.get(会话标识)):
        # 历史请求只负责排队一次后台资料刷新，响应仍先返回消息内容。
        # 会话列表不会触发官方群接口，避免刷新页面反复消耗 30 QPM 配额。
        标记群信息待刷新(会话标识)
    # 对齐 ElainaBot：MySQL 分页查询优先，不可用时回退内存缓存
    if 类型 in ("group", "user"):
        数据库结果 = _数据库历史消息(会话标识, 类型, before_date, limit, before_id)
        if 数据库结果 is not None:
            return 数据库结果
    会话 = 消息缓存.get(会话标识)
    if not 会话:
        return {
            "messages": [],
            "last_msg_id": "",
            "oldest_date": "",
            "has_more": False,
            "chat_name": "",
            "group_info": 获取缓存的群信息(会话标识),
            "is_admin": bool(群机器人是否管理员(会话标识)) if 类型 == "group" else False,
        }
    消息列表 = 会话.get("messages") or []
    会话消息: list[dict[str, Any]] = _去重消息列表(
        [_规范化历史消息(m) for m in 消息列表]
    )
    会话消息.sort(key=_历史消息排序键)
    try:
        before_id = max(0, int(before_id or 0))
    except (TypeError, ValueError):
        before_id = 0
    if before_id:
        会话消息 = [m for m in 会话消息 if int(m.get("id") or 0) < before_id]
    elif before_date:
        before_date = str(before_date or "").strip()
        before_ts = int(_转数字时间戳(before_date) or 0)
        if before_ts:
            会话消息 = [m for m in 会话消息 if int(m.get("ts") or 0) < before_ts]
    原始数量 = len(会话消息)
    返回消息 = 会话消息[-limit:]
    最后消息 = 会话消息[-1] if 会话消息 else {}
    引用映射: dict[str, dict[str, str]] = {}
    消息索引 = {_规范消息ID(m.get("message_id")): m for m in 会话消息 if _规范消息ID(m.get("message_id"))}
    for 消息记录项 in 返回消息:
        引用ID = str(消息记录项.get("reference_id") or "").strip()
        if not 引用ID or 引用ID in 引用映射:
            continue
        被引用 = 消息索引.get(引用ID)
        if 被引用:
            引用映射[引用ID] = {
                "nickname": str(被引用.get("nickname") or ""),
                "content": _替换提及名称(被引用.get("content") or "", 会话标识),
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
        "has_more": 原始数量 > limit or (bool(before_id) and 原始数量 >= limit),
        "chat_name": _聊天显示名(会话标识, 会话),
        "group_info": 获取缓存的群信息(会话标识),
        "is_admin": bool(群机器人是否管理员(会话标识)) if 类型 == "group" else False,
        "member_profiles": _获取消息相关成员资料(会话标识, 返回消息),
        "references": 引用映射,
    }


async def 获取群角色(会话标识: str, appid: str = "") -> dict[str, Any]:
    """查询机器人在群状态与成员角色缓存，返回 (成员角色表, 机器人是否管理员)。"""
    状态 = await _查询群机器人状态(会话标识, appid)
    机器人角色 = str(状态.get("member_role") or "")
    机器人是否管理员 = (
        状态.get("status") != "removed"
        and 机器人角色 in ("owner", "admin")
    )
    if 会话标识:
        信息 = 群信息缓存.setdefault(会话标识, {"group_openid": 会话标识})
        信息["is_admin"] = 机器人是否管理员
    成员表: dict[str, dict[str, Any]] = {}
    for 成员标识, 资料 in (成员资料缓存.get(会话标识) or {}).items():
        成员表[成员标识] = {
            "nickname": 资料.get("nickname") or "",
            "is_bot": bool(资料.get("is_bot") or False),
            "role": "",
        }
    return {
        "roles": 成员表,
        "bot_is_admin": 机器人是否管理员,
        "bot_role": 机器人角色,
        "bot_in_group": 状态.get("status") != "removed",
        "membership_status": str(状态.get("status") or "unknown"),
        "membership_checked_at": int(状态.get("checked_at") or 0),
        "allow_proactive_msg": 状态.get("allow_proactive_msg"),
        "recv_msg_setting": str(状态.get("recv_msg_setting") or ""),
    }


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
    文件名: str = "",
) -> str:
    """按 QQ 官方富媒体协议上传并返回 file_info。"""
    from botpy.http import Route

    try:
        文件类型 = int(文件类型 or 4)
    except (TypeError, ValueError):
        文件类型 = 4
    if 文件类型 not in {1, 2, 3, 4}:
        文件类型 = 4
    地址 = str(文件路径 or "").strip()
    远程 = str(文件URL or "").strip()
    默认文件名 = {1: "image.png", 2: "video.mp4", 3: "audio.silk", 4: "attachment.bin"}[文件类型]
    文件名 = str(文件名 or "").strip()
    if 地址:
        文件名 = Path(地址).name
    文件名 = re.sub(r"[\x00-\x1f\x7f\\/]", "_", 文件名)[:160].strip() or 默认文件名

    if 文件字节 is None and 地址 and Path(地址).is_file():
        try:
            with open(地址, "rb") as 文件句柄:
                文件字节 = 文件句柄.read()
        except OSError:
            return ""
    if 文件字节 is not None:
        if len(文件字节) <= 0 or len(文件字节) > 200 * 1024 * 1024:
            return ""
        return await _上传媒体分片(
            _http,
            会话标识,
            类型,
            文件类型,
            文件名,
            文件字节,
        )
    if not (远程.startswith("http://") or 远程.startswith("https://")):
        return ""
    payload: dict[str, Any] = {
        "file_type": 文件类型,
        "url": 远程,
        "file_name": 文件名,
        "srv_send_msg": False,
    }
    if 类型 == "user":
        route = Route("POST", "/v2/users/{openid}/files", openid=会话标识)
    else:
        route = Route(
            "POST",
            "/v2/groups/{group_openid}/files",
            group_openid=会话标识,
        )
    结果 = await _http.request(route, json=payload)
    if isinstance(结果, dict):
        return str(结果.get("file_info") or "")
    return ""


async def _上传媒体分片(
    _http: Any,
    会话标识: str,
    类型: str,
    文件类型: int,
    文件名: str,
    文件字节: bytes,
) -> str:
    """执行官方 upload_prepare、分片 PUT、part_finish 和合并流程。"""
    if ClientSession is None or ClientTimeout is None:
        return ""
    from botpy.http import Route

    文件大小 = len(文件字节)
    文件MD5 = hashlib.md5(文件字节).hexdigest()
    文件SHA1 = hashlib.sha1(文件字节).hexdigest()
    前十MBMD5 = hashlib.md5(文件字节[:10002432]).hexdigest()
    if 类型 == "user":
        预上传路由 = Route("POST", "/v2/users/{user_id}/upload_prepare", user_id=会话标识)
        分片完成路由模板 = "/v2/users/{user_id}/upload_part_finish"
        合并路由 = Route("POST", "/v2/users/{openid}/files", openid=会话标识)
        路由参数名 = "user_id"
    else:
        预上传路由 = Route("POST", "/v2/groups/{group_id}/upload_prepare", group_id=会话标识)
        分片完成路由模板 = "/v2/groups/{group_id}/upload_part_finish"
        合并路由 = Route("POST", "/v2/groups/{group_openid}/files", group_openid=会话标识)
        路由参数名 = "group_id"
    预上传 = await _http.request(
        预上传路由,
        json={
            "file_type": 文件类型,
            "file_size": str(文件大小),
            "file_name": 文件名,
            "md5": 文件MD5,
            "sha1": 文件SHA1,
            "md5_10m": 前十MBMD5,
        },
    )
    if not isinstance(预上传, dict):
        return ""
    上传ID = str(预上传.get("upload_id") or "").strip()
    分片列表 = 预上传.get("parts")
    try:
        默认分片大小 = max(1, int(预上传.get("block_size") or 5 * 1024 * 1024))
    except (TypeError, ValueError):
        默认分片大小 = 5 * 1024 * 1024
    if not 上传ID or not isinstance(分片列表, list) or not 分片列表:
        return ""
    配置 = 预上传.get("upload_config") if isinstance(预上传.get("upload_config"), dict) else {}
    try:
        并发数 = max(1, min(4, int(配置.get("concurrency") or 1)))
    except (TypeError, ValueError):
        并发数 = 1

    async def 上传一个分片(客户端: Any, 分片: dict[str, Any]) -> None:
        if not isinstance(分片, dict):
            raise RuntimeError("分片参数无效")
        try:
            分片序号 = int(分片.get("index"))
        except (TypeError, ValueError):
            raise RuntimeError("分片序号无效")
        预签名地址 = str(分片.get("presigned_url") or 分片.get("url") or "").strip()
        try:
            分片大小 = max(1, int(分片.get("block_size") or 默认分片大小))
        except (TypeError, ValueError):
            分片大小 = 默认分片大小
        起点 = 分片序号 * 默认分片大小
        数据 = 文件字节[起点 : min(文件大小, 起点 + 分片大小)]
        if not 预签名地址 or not 数据:
            raise RuntimeError("分片数据无效")
        分片MD5 = hashlib.md5(数据).hexdigest()
        for 次数 in range(3):
            try:
                async with 客户端.put(预签名地址, data=数据) as 响应:
                    if not 200 <= 响应.status < 300:
                        raise RuntimeError(f"分片上传 HTTP {响应.status}")
                await _http.request(
                    Route(
                        "POST",
                        分片完成路由模板,
                        **{路由参数名: 会话标识},
                    ),
                    json={
                        "upload_id": 上传ID,
                        "part_index": 分片序号,
                        "block_size": str(len(数据)),
                        "md5": 分片MD5,
                    },
                )
                return
            except Exception:
                if 次数 >= 2:
                    raise
                await asyncio.sleep(1 + 次数)

    信号量 = asyncio.Semaphore(并发数)

    async def 限制上传(客户端: Any, 分片: dict[str, Any]) -> None:
        async with 信号量:
            await 上传一个分片(客户端, 分片)

    async with ClientSession(
        timeout=ClientTimeout(total=300, connect=20, sock_read=300),
        trust_env=False,
    ) as 客户端:
        await asyncio.gather(*(限制上传(客户端, 分片) for 分片 in 分片列表))
    合并 = await _http.request(
        合并路由,
        json={
            "file_type": 文件类型,
            "file_name": 文件名,
            "upload_id": 上传ID,
            "srv_send_msg": False,
        },
    )
    if isinstance(合并, dict):
        return str(合并.get("file_info") or "")
    return ""


def _规范化公网图片地址(地址: Any) -> str:
    """Markdown 图片只接受可由 QQ 官方下载的 HTTP(S) 地址。"""
    文本 = str(地址 or "").strip()
    try:
        解析结果 = _解析网址(文本)
    except ValueError:
        return ""
    if 解析结果.scheme.lower() not in {"http", "https"} or not 解析结果.netloc:
        return ""
    return 文本


def _构造Markdown图文内容(
    内容: Any,
    图片地址: Any,
    图片前文本: Any = "",
    图片后文本: Any = "",
    图片占位标记: Any = "\ufffc",
) -> str:
    """按 QQ 官方 Markdown 图片语法拼接一条图文消息。"""
    文本 = str(内容 or "").strip()
    地址 = _规范化公网图片地址(图片地址)
    前文本 = str(图片前文本 or "").strip()
    后文本 = str(图片后文本 or "").strip()
    占位标记 = str(图片占位标记 or "\ufffc")
    if 文本 and 地址 and 占位标记 and 占位标记 in 文本:
        编码地址 = _网址编码(地址, safe=":/?#[]@!$&'*+,;=%~._-")
        图片标记 = f"![图片 #640px #480px]({编码地址})"
        return (f"\n\n{图片标记}\n\n").join(文本.split(占位标记)).strip()
    if (前文本 or 后文本) and 地址:
        编码地址 = _网址编码(地址, safe=":/?#[]@!$&'*+,;=%~._-")
        图片标记 = f"![图片 #640px #480px]({编码地址})"
        return "\n\n".join(值 for 值 in (前文本, 图片标记, 后文本) if 值)
    if not 文本 or not 地址:
        return ""
    编码地址 = _网址编码(地址, safe=":/?#[]@!$&'*+,;=%~._-")
    return f"{文本}\n\n![图片 #640px #480px]({编码地址})"


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
    引用消息REFIDX: str = "",
    图片路径: str = "",
    图片文件名: str = "",
    图片数据: str = "",
    图片URL: str = "",
    图片前文本: str = "",
    图片后文本: str = "",
    图片占位标记: str = "\ufffc",
    媒体路径: str = "",
    媒体URL: str = "",
    媒体数据: str = "",
    媒体文件名: str = "",
    媒体内容类型: str = "",
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
    会话类型 = str(
        会话类型
        or (消息缓存.get(会话标识, {}) or {}).get("chat_type")
        or "group"
    ).strip().lower()
    权限会话类型 = 会话类型
    平台实例 = 获取QQ官方平台(appid=appid)
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
    事件ID = 自定义ID if 发送方式 == "custom_event_id" else ""
    实际使用主动消息 = not 被动ID and not 事件ID
    if 实际使用主动消息:
        if 权限会话类型 == "group":
            查询权限 = await 查询群主动消息权限(会话标识, appid)
            if 查询权限 is not True:
                return {"ok": False, "message": "发送失败：主动消息权限未开启"}
        elif 主动消息是否允许(会话标识, 权限会话类型) is False:
            return {"ok": False, "message": "发送失败：主动消息权限未开启"}
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
        引用目标 = str(引用消息REFIDX or "").strip() or 引用消息ID
        # QQ 官方引用需优先使用被引用消息自身的 REFIDX，找不到时回退完整消息 ID
        if not 引用消息REFIDX:
            for 会话记录 in 消息缓存.values():
                目标 = next((x for x in (会话记录.get("messages") or []) if str(x.get("message_id") or "") == 引用消息ID), None)
                if 目标 and 目标.get("refidx"):
                    引用目标 = str(目标.get("refidx"))
                    break
        消息体["message_reference"] = {"message_id": 引用目标, "ignore_get_message_error": True}

    图片公开地址 = _规范化公网图片地址(图片URL)
    图片前文本 = str(图片前文本 or "").strip()
    图片后文本 = str(图片后文本 or "").strip()
    图片文件名 = str(图片文件名 or "").strip()
    图片字节: bytes | None = None
    if 图片路径:
        图片路径值 = Path(str(图片路径).strip())
        try:
            文件大小 = 图片路径值.stat().st_size
        except OSError:
            return {"ok": False, "message": "图片数据无效"}
        if 文件大小 <= 0 or 文件大小 > 200 * 1024 * 1024:
            return {"ok": False, "message": "图片数据无效"}
        try:
            图片字节 = 图片路径值.read_bytes()
        except OSError:
            return {"ok": False, "message": "图片数据无效"}
        图片文件名 = 图片文件名 or 图片路径值.name or "image.png"
    if not 图片文件名:
        图片文件名 = "image.png"
    if 图片数据:
        图片数据 = str(图片数据 or "").strip()
        try:
            图片类型匹配 = re.match(r"^data:image/(png|jpe?g|gif|webp|bmp);base64,", 图片数据, re.IGNORECASE)
            if 图片类型匹配:
                扩展名 = 图片类型匹配.group(1).lower()
                图片文件名 = "image.jpg" if 扩展名 in {"jpg", "jpeg"} else f"image.{扩展名}"
            if 图片数据.startswith("data:") and "," in 图片数据:
                图片数据 = 图片数据.split(",", 1)[1]
            图片字节 = base64.b64decode(图片数据)
        except Exception:
            return {"ok": False, "message": "图片数据无效"}

    媒体字节: bytes | None = None
    if 媒体数据:
        媒体原始数据 = str(媒体数据 or "").strip()
        try:
            if 媒体原始数据.startswith("data:") and "," in 媒体原始数据:
                媒体原始数据 = 媒体原始数据.split(",", 1)[1]
            媒体字节 = base64.b64decode(媒体原始数据, validate=True)
        except Exception:
            return {"ok": False, "message": "媒体数据无效"}
        if len(媒体字节) <= 0 or len(媒体字节) > 200 * 1024 * 1024:
            return {"ok": False, "message": "媒体文件过大"}

    图片占位标记 = str(图片占位标记 or "\ufffc")

    图片记录地址 = 图片公开地址
    媒体记录地址 = str(媒体URL or "").strip()

    async def _保存本地发送媒体记录() -> None:
        """仅为发送的字节媒体保留本地副本，收到的附件仍只保存官方 URL。"""
        nonlocal 图片记录地址, 媒体记录地址
        数据: bytes | None = None
        文件名 = ""
        内容类型 = "application/octet-stream"
        if 图片字节 is not None and not 图片记录地址:
            数据 = 图片字节
            文件名 = 图片文件名
            内容类型 = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
            }.get(Path(图片文件名).suffix.lower(), "image/png")
        elif 媒体字节 is not None and not 媒体记录地址:
            数据 = 媒体字节
            文件名 = 媒体文件名 or "attachment.bin"
            try:
                媒体类型编号 = int(媒体文件类型 or 4)
            except (TypeError, ValueError):
                媒体类型编号 = 4
            内容类型 = 媒体内容类型 or {
                2: "video/mp4",
                3: "audio/silk",
                4: "application/octet-stream",
            }.get(媒体类型编号, "application/octet-stream")
        if not 数据:
            return
        try:
            from 功能文件.页面功能 import 帮助网页后端

            地址 = await 帮助网页后端.保存本地发送媒体(
                数据,
                文件名,
                内容类型,
            )
        except asyncio.CancelledError:
            raise
        except Exception as 异常:
            logger.debug("消息发送媒体本地副本保存失败：错误类型=%s", type(异常).__name__)
            return
        if not 地址:
            return
        if 图片字节 is not None and not 图片记录地址:
            图片记录地址 = 地址
        elif 媒体字节 is not None and not 媒体记录地址:
            媒体记录地址 = 地址

    def _图片媒体记录() -> dict[str, Any]:
        展示文本 = str(内容 or "").replace(图片占位标记, "").strip()
        前文本 = 图片前文本
        后文本 = 图片后文本
        if 图片占位标记 and 图片占位标记 in str(内容 or ""):
            前文本, 后文本 = str(内容 or "").split(图片占位标记, 1)
            前文本 = 前文本.strip()
            后文本 = 后文本.strip()
        媒体记录: dict[str, Any] = {
            "type": "图片",
            "src": 图片记录地址,
            "text": 展示文本,
        }
        if 前文本 or 后文本:
            媒体记录["before_text"] = 前文本
            媒体记录["after_text"] = 后文本
        return 媒体记录

    def _普通媒体记录() -> dict[str, Any]:
        try:
            类型编号 = int(媒体文件类型 or 4)
        except (TypeError, ValueError):
            类型编号 = 4
        类型名称 = {2: "视频", 3: "语音", 4: "文件"}.get(类型编号, "文件")
        媒体地址 = str(媒体记录地址 or "").strip()
        if not (
            媒体地址.startswith(("http://", "https://"))
            or 媒体地址.startswith("/api/message/local-media/")
        ):
            媒体地址 = ""
        return {
            "type": 类型名称,
            "src": 媒体地址,
            "name": str(媒体文件名 or "").strip(),
            "content_type": str(媒体内容类型 or "").strip(),
            "text": str(内容 or "").replace(图片占位标记, "").strip(),
        }

    # 有公网地址时使用 Markdown；本地字节媒体直接走官方富媒体消息。
    图文内容 = (
        _构造Markdown图文内容(
            内容,
            图片公开地址,
            图片前文本,
            图片后文本,
            图片占位标记,
        )
        if 类型 in ("text", "markdown")
        else ""
    )
    if 图文内容:
        消息体["msg_type"] = 2
        消息体.pop("content", None)
        消息体["markdown"] = {
            "content": 图文内容,
            "force_verify_image_resource": True,
        }
    else:
        # 没有公网图片地址时，下面改用官方富媒体消息。
        if (图片字节 is not None or 图片公开地址) and 类型 == "markdown":
            类型 = "text"
    if not 图文内容 and (图片字节 is not None or 图片公开地址):
        file_info = await _上传媒体(
            _http,
            会话标识,
            会话类型 or "group",
            文件URL=图片公开地址,
            文件类型=1,
            文件字节=图片字节,
            文件名=图片文件名,
        )
        if not file_info:
            return {"ok": False, "message": "图片上传失败"}
        消息体["msg_type"] = 7
        # QQ 官方 msg_type=7 只接受 media.file_info；文字只能通过 Markdown
        # 图文消息发送，不能把 content 混入富媒体请求体。
        消息体.pop("content", None)
        消息体["media"] = {"file_info": file_info}

    if not 图文内容 and 类型 == "markdown":
        消息体["msg_type"] = 2
        消息体.pop("content", None)
        消息体["markdown"] = {"content": 内容}
    elif 类型 == "media":
        file_info = ""
        if 媒体路径 or 媒体URL or 媒体字节 is not None:
            file_info = await _上传媒体(
                _http,
                会话标识,
                会话类型 or "group",
                媒体路径,
                媒体URL,
                int(媒体文件类型 or 1),
                媒体字节,
                媒体文件名,
            )
        if not file_info:
            return {"ok": False, "message": "媒体上传失败"}
        消息体["msg_type"] = 7
        消息体.pop("content", None)
        消息体["media"] = {"file_info": file_info}
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
        if 实际使用主动消息:
            记录主动消息权限(会话标识, 权限会话类型, True)
    except Exception as exc:
        if 实际使用主动消息 and 主动消息无权限(exc):
            记录主动消息权限(会话标识, 权限会话类型, False)
        logger.warning(
            "消息记录发送失败：错误类型=%s，错误详情=%s",
            type(exc).__name__,
            str(exc)[:400],
        )
        错误文本 = str(exc)
        if 被动ID and 被动消息ID已过期(exc):
            # msg_id 已过期：去掉后重试一次主动推送（全量消息群可成功）
            消息体.pop("msg_id", None)
            if 主动消息是否允许(会话标识, 权限会话类型) is False:
                return {"ok": False, "message": "发送失败：主动消息权限未开启"}
            try:
                结果 = await _http.request(route, json=消息体)
                记录主动消息权限(会话标识, 权限会话类型, True)
            except Exception as 重试异常:
                if 主动消息无权限(重试异常):
                    记录主动消息权限(会话标识, 权限会话类型, False)
                错误文本 = str(重试异常)
                logger.warning("消息记录主动重试失败：错误类型=%s，错误详情=%s", type(重试异常).__name__, 错误文本[:400])
            else:
                if isinstance(结果, dict) and 结果.get("id"):
                    响应ID = str(结果.get("id") or "")
                    await _保存本地发送媒体记录()
                    展示内容 = str(内容 or "").replace(图片占位标记, "").strip() if 图文内容 else 内容
                    if 消息体.get("msg_type") == 7 and (图片字节 is not None or 图片公开地址):
                        清理文本 = str(内容 or "").replace(图片占位标记, "").strip()
                        展示内容 = "[图片]" if not 清理文本 else "[图片] " + 清理文本
                    if 类型 == "media":
                        展示内容 = f"[{_普通媒体记录().get('type') or '文件'}]"
                    elif 类型 == "ark":
                        展示内容 = "[ARK卡片] " + 展示内容
                    elif 类型 == "card":
                        展示内容 = "[图文卡片] " + 展示内容
                    媒体记录 = None
                    if 图文内容:
                        媒体记录 = _图片媒体记录()
                    elif 消息体.get("msg_type") == 7 and (图片字节 is not None or 图片公开地址):
                        媒体记录 = _图片媒体记录()
                    elif 类型 == "media":
                        媒体记录 = _普通媒体记录()
                    记录 = 记录发送消息(
                        会话标识,
                        会话类型 or "group",
                        展示内容 or "（空消息）",
                        appid,
                        消息ID=响应ID,
                        自身REFIDX=_提取发送响应REFIDX(结果),
                        引用ID=引用消息ID,
                        媒体=媒体记录,
                        发送时间=_提取发送响应时间(结果),
                    )
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
        return {"ok": False, "message": "发送失败，请稍后再试"}

    响应ID = ""
    if isinstance(结果, dict):
        响应ID = str(结果.get("id") or "")
    elif 结果 is not None:
        响应ID = str(getattr(结果, "id", None) or "")
    await _保存本地发送媒体记录()
    展示内容 = str(内容 or "").replace(图片占位标记, "").strip() if 图文内容 else 内容
    if 消息体.get("msg_type") == 7 and (图片字节 is not None or 图片公开地址):
        清理文本 = str(内容 or "").replace(图片占位标记, "").strip()
        展示内容 = "[图片]" if not 清理文本 else "[图片] " + 清理文本
    if 类型 == "media":
        展示内容 = f"[{_普通媒体记录().get('type') or '文件'}]"
    elif 类型 == "ark":
        展示内容 = "[ARK卡片] " + 展示内容
    elif 类型 == "card":
        展示内容 = "[图文卡片] " + 展示内容
    媒体记录 = None
    if 图文内容:
        媒体记录 = _图片媒体记录()
    elif 消息体.get("msg_type") == 7 and (图片字节 is not None or 图片公开地址):
        媒体记录 = _图片媒体记录()
    elif 类型 == "media":
        媒体记录 = _普通媒体记录()
    记录 = 记录发送消息(
        会话标识,
        会话类型 or "group",
        展示内容 or "（空消息）",
        appid,
        消息ID=响应ID,
        自身REFIDX=_提取发送响应REFIDX(结果),
        引用ID=引用消息ID,
        媒体=媒体记录,
        发送时间=_提取发送响应时间(结果),
    )
    return {"ok": True, "message_id": 响应ID, "message": 记录}


async def 撤回消息(
    会话标识: str, 消息ID: str, appid: str = "", 类型: str = ""
) -> dict[str, Any]:
    会话标识 = str(会话标识 or "").strip()
    消息ID = str(消息ID or "").strip()
    if not 会话标识 or not 消息ID:
        return {"ok": False, "message": "参数无效"}
    通道 = 获取HTTP通道(获取QQ官方平台(appid=appid))
    if 通道 is None:
        return {"ok": False, "message": "QQ官方平台未加载"}
    _, _http = 通道
    try:
        from botpy.http import Route

        会话类型 = str(
            类型
            or (消息缓存.get(会话标识, {}) or {}).get("chat_type")
            or "group"
        ).strip().lower()
        if 会话类型 == "user":
            route = Route(
                "DELETE",
                "/v2/users/{user_openid}/messages/{message_id}",
                user_openid=会话标识,
                message_id=消息ID,
            )
        else:
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
    通道 = 获取HTTP通道(获取QQ官方平台(appid=appid))
    if 通道 is None:
        return {"ok": False, "message": "QQ官方平台未加载"}
    _, _http = 通道
    try:
        from botpy.http import Route

        from datetime import datetime, timedelta, timezone

        到期 = datetime.now(timezone(timedelta(hours=8))) + timedelta(minutes=分钟数)
        到期文本 = 到期.isoformat(timespec="seconds")
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
        for 缓存键 in list(群禁言状态缓存):
            if 缓存键[1] == 会话标识:
                群禁言状态缓存.pop(缓存键, None)
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


async def 解除群成员禁言(
    会话标识: str,
    成员标识: str,
    appid: str = "",
) -> dict[str, Any]:
    """通过 QQ 官方接口解除当前群成员禁言。"""
    会话标识 = str(会话标识 or "").strip()
    成员标识 = str(成员标识 or "").strip()
    if not 会话标识 or not 成员标识:
        return {"ok": False, "message": "参数无效"}
    通道 = 获取HTTP通道(获取QQ官方平台(appid=appid))
    if 通道 is None:
        return {"ok": False, "message": "QQ官方平台未加载"}
    _, _http = 通道
    try:
        from botpy.http import Route

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
                        "op": "del",
                        "member_openid": 成员标识,
                    }
                ]
            },
        )
        for 缓存键 in list(群禁言状态缓存):
            if 缓存键[1] == 会话标识:
                群禁言状态缓存.pop(缓存键, None)
        return {"ok": True, "message": "解除禁言成功"}
    except Exception as exc:
        提示 = "解除禁言失败，请稍后再试"
        原文 = str(getattr(exc, "resp", "") or exc)
        if "not admin" in 原文 or "没有权限" in 原文 or "权限" in 原文:
            提示 = "机器人不是该群管理员，无法解除禁言"
        elif "不存在" in 原文 or "无效" in 原文:
            提示 = "群或成员不存在，无法解除禁言"
        logger.warning("消息记录解除禁言失败：错误类型=%s", type(exc).__name__)
        return {"ok": False, "message": 提示}


# ---------------------------------------------------------------------------
# botpy 昵称修补
# ---------------------------------------------------------------------------

_昵称修补已安装 = globals().get("_昵称修补已安装", False)


def _修补botpy昵称() -> bool:
    """补回 botpy 丢弃的 author 昵称及官方事件扩展头像字段。

    QQ 官方 C2C/群聊事件原始 JSON 的 author 带 username（用户昵称），但
    部分 botpy 版本的 C2CMessage._User / GroupMessage._User 只解析 openid。
    在事件构造后把 username 和可能存在的 avatar 动态补到 author 对象上，
    下游即可读取；标准事件没有头像字段时仍保持为空。
    """
    global _昵称修补已安装
    if _昵称修补已安装:
        return True
    try:
        import botpy.message as _botpy消息模块
    except Exception:
        return False
    消息模块列表 = [_botpy消息模块]
    try:
        from astrbot.core.platform.sources.qqofficial import (
            qqofficial_platform_adapter as _官方适配器模块,
        )

        消息模块列表.append(_官方适配器模块)
    except Exception:
        pass
    消息类列表: list[type[Any]] = []
    已处理类型: set[type[Any]] = set()
    for 消息模块 in 消息模块列表:
        for 类名 in (
            "C2CMessage",
            "GroupMessage",
            "PatchedC2CMessage",
            "PatchedGroupMessage",
            "PatchedDirectMessage",
        ):
            消息类 = getattr(消息模块, 类名, None)
            if not isinstance(消息类, type) or 消息类 in 已处理类型:
                continue
            已处理类型.add(消息类)
            消息类列表.append(消息类)
    for 消息类 in 消息类列表:
        if 消息类 is None:
            continue
        原初始化 = getattr(消息类, "__init__", None)
        if 原初始化 is None or getattr(原初始化, "__module__", "") == __name__:
            continue

        def 新初始化(self: Any, *参数: Any, _原=原初始化, **关键字: Any) -> None:
            _原(self, *参数, **关键字)
            try:
                数据 = None
                for 项 in 参数:
                    if isinstance(项, dict) and 项.get("author") is not None:
                        数据 = 项
                        break
                if 数据 is None:
                    数据 = 关键字.get("data")
                if not isinstance(数据, dict):
                    return
                作者 = getattr(self, "author", None)
                作者数据 = 数据.get("author") or {}
                成员数据 = 数据.get("member") or {}
                资料对象列表 = [
                    项
                    for 项 in (
                        作者数据,
                        成员数据,
                        成员数据.get("user") if isinstance(成员数据, dict) else None,
                    )
                    if isinstance(项, dict)
                ]
                if isinstance(作者数据, dict):
                    昵称 = str(作者数据.get("username") or "").strip()
                    if 昵称 and 作者 is not None:
                        作者.username = 昵称
                if 作者 is not None:
                    for 资料 in 资料对象列表:
                        for 字段 in ("avatar", "avatar_url", "avatarUrl", "icon"):
                            头像 = 资料.get(字段)
                            if 头像 not in (None, ""):
                                try:
                                    setattr(作者, 字段, str(头像).strip())
                                except Exception:
                                    pass
                原始提及 = 数据.get("mentions") or []
                已解析提及 = getattr(self, "mentions", None) or []
                if isinstance(原始提及, dict):
                    原始提及 = list(原始提及.values())
                for 原始成员, 解析成员 in zip(原始提及, 已解析提及):
                    if not isinstance(原始成员, dict):
                        continue
                    标识 = str(
                        原始成员.get("member_openid")
                        or 原始成员.get("user_openid")
                        or 原始成员.get("openid")
                        or 原始成员.get("id")
                        or ""
                    ).strip()
                    if 标识:
                        for 字段 in ("member_openid", "user_openid", "openid", "id"):
                            try:
                                if not getattr(解析成员, 字段, None):
                                    setattr(解析成员, 字段, 标识)
                            except Exception:
                                pass
                    提及昵称 = str(
                        原始成员.get("username")
                        or 原始成员.get("member_name")
                        or 原始成员.get("nickname")
                        or 原始成员.get("name")
                        or ""
                    ).strip()
                    if 提及昵称:
                        try:
                            解析成员.username = 提及昵称
                        except Exception:
                            pass
            except Exception:
                pass

        消息类.__init__ = 新初始化  # type: ignore[method-assign]
    _昵称修补已安装 = True
    return True


# ---------------------------------------------------------------------------
# 事件挂钩
# ---------------------------------------------------------------------------

_撤回事件名称 = {
    "message_delete",
    "message_recall",
    "group_message_delete",
    "group_message_recall",
    "group_message_recalled",
    "c2c_message_delete",
    "c2c_message_recall",
    "direct_message_delete",
    "direct_message_recall",
    "public_message_delete",
}


def _查找消息会话(消息ID: str) -> tuple[str, str] | None:
    """按消息 ID 在本地缓存中反查会话，兼容撤回事件缺少会话字段。"""
    目标ID = str(消息ID or "").strip()
    if not 目标ID:
        return None
    for 会话标识, 会话 in list(消息缓存.items()):
        if not isinstance(会话, dict):
            continue
        for 记录 in 会话.get("messages") or []:
            if isinstance(记录, dict) and str(记录.get("message_id") or "").strip() == 目标ID:
                return str(会话标识), str(记录.get("chat_type") or 会话.get("chat_type") or "group")
    return None


def _提取撤回事件目标(
    事件名: Any, 参数: tuple[Any, ...], 关键字: dict[str, Any]
) -> list[tuple[str, str, str]]:
    """从可能的 QQ 网关撤回负载提取会话、消息 ID 和会话类型。"""
    名称 = str(事件名 or "").strip().lower().replace("-", "_")
    默认类型 = "user" if any(值 in 名称 for 值 in ("c2c", "direct")) else "group"
    结果: list[tuple[str, str, str]] = []
    已见: set[tuple[str, str, str]] = set()

    def 加入(会话标识: Any, 消息ID: Any, 类型: str) -> None:
        会话值 = str(会话标识 or "").strip()
        消息值 = str(消息ID or "").strip()
        类型值 = "user" if 类型 == "user" else "group"
        if not 消息值:
            return
        if not 会话值:
            反查 = _查找消息会话(消息值)
            if 反查:
                会话值, 类型值 = 反查
        if not 会话值:
            return
        项 = (会话值, 消息值, 类型值)
        if 项 not in 已见:
            已见.add(项)
            结果.append(项)

    def 遍历(对象: Any, 类型: str, 会话标识: str = "", 深度: int = 0, 消息上下文: bool = False) -> None:
        if 对象 is None or 深度 > 7:
            return
        if isinstance(对象, dict):
            当前会话 = str(
                对象.get("group_openid")
                or 对象.get("group_id")
                or 对象.get("user_openid")
                or 对象.get("user_id")
                or 会话标识
                or ""
            ).strip()
            当前类型 = "user" if any(
                对象.get(字段) not in (None, "")
                for 字段 in ("user_openid", "user_id")
            ) else 类型
            消息值 = 对象.get("message_id") or 对象.get("msg_id") or 对象.get("messageId")
            if not 消息值 and 消息上下文:
                消息值 = 对象.get("id")
            if 消息值:
                加入(当前会话, 消息值, 当前类型)
            for 字段, 子对象 in 对象.items():
                if 字段 in {"group_openid", "group_id", "user_openid", "user_id", "message_id", "msg_id", "messageId"}:
                    continue
                遍历(
                    子对象,
                    当前类型,
                    当前会话,
                    深度 + 1,
                    消息上下文 or 字段 in {"message", "deleted_message", "deleted", "data"},
                )
            return
        if isinstance(对象, (list, tuple, set)):
            for 子对象 in 对象:
                遍历(子对象, 类型, 会话标识, 深度 + 1, 消息上下文)
            return
        if isinstance(对象, (str, bytes, int, float, bool)):
            return
        当前会话 = str(
            _读取字段(对象, "group_openid")
            or _读取字段(对象, "group_id")
            or _读取字段(对象, "user_openid")
            or _读取字段(对象, "user_id")
            or 会话标识
            or ""
        ).strip()
        当前类型 = "user" if _读取字段(对象, "user_openid") or _读取字段(对象, "user_id") else 类型
        消息值 = (
            _读取字段(对象, "message_id")
            or _读取字段(对象, "msg_id")
            or _读取字段(对象, "messageId")
            or (_读取字段(对象, "id") if 消息上下文 else "")
        )
        if 消息值:
            加入(当前会话, 消息值, 当前类型)
        for 字段 in ("message", "deleted_message", "deleted", "data", "payload", "raw_data"):
            子对象 = _读取字段(对象, 字段)
            if 子对象 not in (None, ""):
                遍历(子对象, 当前类型, 当前会话, 深度 + 1, 消息上下文 or 字段 in {"message", "deleted_message", "deleted", "data"})

    for 对象 in (*参数, *关键字.values()):
        遍历(对象, 默认类型)
    return 结果


def _处理撤回网关事件(事件名: Any, 参数: tuple[Any, ...], 关键字: dict[str, Any]) -> int:
    目标列表 = _提取撤回事件目标(事件名, 参数, 关键字)
    for 会话标识, 消息ID, _类型 in 目标列表:
        标记撤回(会话标识, 消息ID)
    if 目标列表:
        logger.debug(
            "消息记录撤回事件已同步：事件=%s，数量=%d",
            str(事件名 or "").strip().lower(),
            len(目标列表),
        )
    return len(目标列表)


def _安装消息撤回事件挂钩(客户端类: Any) -> bool:
    """兼容 QQ 网关可能下发的消息删除/撤回事件。"""
    global _消息撤回事件挂钩版本
    原分发方法 = getattr(客户端类, "ws_dispatch", None)
    if not callable(原分发方法):
        return False
    if getattr(原分发方法, "__mantou_recall_hook_version__", 0) >= 1:
        _消息撤回事件挂钩版本 = max(_消息撤回事件挂钩版本, 1)
        return True

    def 新分发方法(self: Any, 事件名: Any, *参数: Any, **关键字: Any) -> Any:
        名称 = str(事件名 or "").strip().lower().replace("-", "_")
        if 名称 in _撤回事件名称:
            try:
                _处理撤回网关事件(名称, 参数, 关键字)
            except Exception as 异常:
                logger.debug("消息记录撤回事件处理失败：错误类型=%s", type(异常).__name__)
        return 原分发方法(self, 事件名, *参数, **关键字)

    setattr(新分发方法, "__mantou_recall_hook_version__", 1)
    客户端类.ws_dispatch = 新分发方法
    _消息撤回事件挂钩版本 = 1
    logger.info("消息记录撤回事件挂钩已安装：已兼容网关删除/撤回事件")
    return True


def _安装消息事件挂钩() -> bool:
    """为 QQ 官方 botClient 包装消息事件回调，把收到的消息写入缓存。"""
    global _挂钩已安装, _消息事件挂钩版本
    if _挂钩已安装 and _消息事件挂钩版本 >= 3 and _消息撤回事件挂钩版本 >= 1:
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
    _安装消息撤回事件挂钩(客户端类)

    事件表 = (
        ("on_group_at_message_create", "group"),
        ("on_group_message_create", "group"),
        ("on_c2c_message_create", "user"),
        ("on_direct_message_create", "user"),
        ("on_group_del_robot", "group_removed"),
    )
    for 事件名, 类型 in 事件表:
        原回调 = getattr(客户端类, 事件名, None)
        if 原回调 is None or getattr(原回调, "__module__", "") == __name__:
            continue

        async def 新回调(self: Any, 消息: Any, _原=原回调, _类型=类型) -> Any:
            try:
                _安装消息发送挂钩()
                # botpy 的事件回调位于网关接收热路径，只做一次非阻塞入队。
                # 解析、缓存、未读计数、昵称补查和数据库写入由独立 worker 顺序处理。
                if _类型 == "group_removed":
                    群号 = _提取群机器人退出群号(消息)
                    if 群号:
                        标记群机器人已移除(群号, _平台实例appid(self))
                else:
                    _排队收到消息(self, 消息, _类型)
            except Exception as exc:
                logger.warning("消息记录事件入队失败：错误类型=%s", type(exc).__name__)
            结果 = _原(self, 消息)
            if asyncio.iscoroutine(结果):
                return await 结果
            return 结果

        setattr(客户端类, 事件名, 新回调)
    _挂钩已安装 = True
    _消息事件挂钩版本 = 3
    logger.info("消息记录事件挂钩已安装：group/user 消息已接入缓存")
    return True


def _链提取文本(消息链: Any) -> str:
    """从 AstrBot MessageChain 提取展示文本（纯文本 + 媒体占位）。

    兼容新版 MessageChain.chain（pydantic 组件对象，文本在 text/content 字段，无 data 属性）
    与旧版 segments（type/data 字典）两种形态，组件类型大小写不敏感。
    """
    try:
        段们 = getattr(消息链, "chain", None) or getattr(消息链, "segments", None) or []
        文本 = ""
        for 段 in 段们:
            if isinstance(段, dict):
                类型 = str(段.get("type") or "").strip().lower()
                数据 = 段.get("data") or {}
                内容 = _链段取文本(类型, 数据)
            else:
                类型 = str(getattr(段, "type", "") or "").strip().lower()
                数据 = getattr(段, "data", None)
                内容 = _链段取文本(类型, 数据 if isinstance(数据, dict) else None, 段)
            if 内容:
                文本 += 内容
            elif 类型 in ("image", "img", "图片"):
                文本 += (" " if 文本 and not 文本.endswith(" ") else "") + "[图片] "
            elif 类型 in ("file", "files", "文件"):
                文本 += (" " if 文本 and not 文本.endswith(" ") else "") + "[文件] "
            elif 类型 in ("video", "视频"):
                文本 += (" " if 文本 and not 文本.endswith(" ") else "") + "[视频] "
            elif 类型 in ("record", "recordmusic", "语音"):
                文本 += (" " if 文本 and not 文本.endswith(" ") else "") + "[语音] "
        return 文本.strip()
    except Exception:
        return ""


def _链段取文本(类型: str, 数据: dict[str, Any] | None, 段: Any = None) -> str:
    """取消息链单个段的展示文本（Plain 取 text，Markdown 取 content，兼容新旧形态）。"""
    if 类型 in ("plain", "text"):
        if 数据:
            return str(数据.get("text") or "")
        return str(getattr(段, "text", "") or "")
    if 类型 == "markdown":
        if 数据:
            return str(数据.get("content") or "")
        return str(getattr(段, "content", "") or "")
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
    """包装 QQ 官方事件发送入口，只在平台成功返回后记录消息和时间。"""
    if 发送方法 is None or getattr(发送方法, "__mantou_record_after_send__", False):
        return None

    async def 新发送(self: Any, stream: Any = None, **关键字: Any) -> Any:
        会话标识 = ""
        类型 = "user"
        appid = ""
        内容 = ""
        try:
            缓冲 = getattr(self, "send_buffer", None)
            if 缓冲 is not None:
                会话 = getattr(self, "session", None)
                会话标识 = _会话标识兜底(会话)
                消息类型 = getattr(会话, "message_type", None)
                类型 = "group" if "GROUP" in str(消息类型).upper() else "user"
                try:
                    appid = str(getattr(getattr(self, "platform_meta", None), "id", "") or "")
                except Exception:
                    pass
                内容 = _链提取文本(缓冲)
        except Exception as exc:
            logger.debug("消息记录事件发送参数提取失败：错误类型=%s", type(exc).__name__)
        结果 = 发送方法(self, stream, **关键字)
        if asyncio.iscoroutine(结果):
            结果 = await 结果
        try:
            原始消息 = getattr(self, "message_obj", None)
            原始消息ID = str(
                getattr(原始消息, "message_id", None)
                or getattr(原始消息, "id", None)
                or ""
            ).strip()
            if 会话标识 and 内容 and (结果 is not None or 原始消息ID):
                记录发送消息(
                    会话标识,
                    类型,
                    内容,
                    appid,
                    消息ID=_提取发送响应消息ID(结果),
                    自身REFIDX=_提取发送响应REFIDX(结果),
                    发送者昵称="机器人",
                    来源="bot_event",
                    发送时间=_提取发送响应时间(结果),
                )
        except Exception as exc:
            logger.warning("消息记录事件发送成功后记录失败：错误类型=%s", type(exc).__name__)
        return 结果

    setattr(新发送, "__mantou_record_after_send__", True)
    return 新发送


def _包装发送方法(发送方法: Any) -> Any:
    """包装主动会话发送，只在适配器确认发送成功后记录。"""
    if 发送方法 is None or getattr(发送方法, "__mantou_record_after_send__", False):
        return None

    async def 新发送(self: Any, session: Any, message_chain: Any) -> Any:
        appid = ""
        会话标识 = ""
        类型 = "user"
        内容 = ""
        发送前消息ID = ""
        try:
            appid = str(getattr(self, "appid", "") or "")
            会话标识 = _会话标识兜底(session)
            消息类型 = str(getattr(session, "message_type", "") or "")
            类型 = "group" if "GROUP" in 消息类型.upper() else "user"
            内容 = _链提取文本(message_chain)
            发送前消息ID = str((getattr(self, "_session_last_message_id", {}) or {}).get(会话标识) or "")
        except Exception as exc:
            logger.debug("消息记录主动发送参数提取失败：错误类型=%s", type(exc).__name__)
        结果 = 发送方法(self, session, message_chain)
        if asyncio.iscoroutine(结果):
            结果 = await 结果
        try:
            发送后消息ID = str((getattr(self, "_session_last_message_id", {}) or {}).get(会话标识) or "")
            响应消息ID = _提取发送响应消息ID(结果)
            if 响应消息ID and 响应消息ID == 发送前消息ID:
                响应消息ID = ""
            消息ID = 响应消息ID or (
                发送后消息ID
                if 发送后消息ID and 发送后消息ID != 发送前消息ID
                else ""
            )
            # send_by_session 按官方适配器约定返回 None。群聊没有旧消息 ID 时，
            # 适配器可能实际跳过发送，因此只允许已有会话或明确开启主动发送的群
            # 在无 ID 时落一条记录；私聊发送成功返回后始终保留本地记录。
            允许无ID记录 = (
                类型 == "user"
                or bool(发送前消息ID)
                or bool(getattr(self, "_allow_group_proactive_send", False))
            )
            if 会话标识 and 内容 and (消息ID or 允许无ID记录):
                记录发送消息(
                    会话标识,
                    类型,
                    内容,
                    appid,
                    消息ID=消息ID,
                    自身REFIDX=_提取发送响应REFIDX(结果),
                    发送者昵称="机器人",
                    来源="bot_session",
                )
        except Exception as exc:
            logger.warning("消息记录主动发送成功后记录失败：错误类型=%s", type(exc).__name__)
        return 结果

    setattr(新发送, "__mantou_record_after_send__", True)
    return 新发送


def _安装消息发送挂钩() -> bool:
    """包装平台发送入口，把机器人发送的消息写入缓存。

    事件回复和主动会话发送分别包装一次；不再包装 Platform 基类，避免
    QQOfficialPlatformAdapter 调用基类收尾时把同一条消息重复记录。
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
    if 已包装 == 0:
        return False
    _发送挂钩已安装 = True
    logger.info("消息记录发送挂钩已安装：机器人发送消息已接入缓存（%d 处）", 已包装)
    return True


def _提取群机器人退出群号(事件: Any) -> str:
    候选对象 = [
        事件,
        _读取字段(事件, "raw_data"),
        _读取字段(事件, "data"),
        _读取字段(事件, "__dict__"),
    ]
    for 对象 in 候选对象:
        if not isinstance(对象, dict):
            continue
        数据 = 对象.get("d") if isinstance(对象.get("d"), dict) else 对象
        群号 = str(
            数据.get("group_openid")
            or 数据.get("group_id")
            or ""
        ).strip()
        if 群号:
            return 群号
    for 字段名 in ("group_openid", "group_id"):
        群号 = str(_读取字段(事件, 字段名) or "").strip()
        if 群号:
            return 群号
    return ""


def _平台实例appid(客户端: Any) -> str:
    for 对象 in (客户端, _读取字段(客户端, "platform"), _读取字段(客户端, "config")):
        for 字段名 in ("appid", "app_id", "id"):
            值 = str(_读取字段(对象, 字段名) or "").strip()
            if 值:
                return 值
    return ""


def 安装消息记录(上下文: Any = None, 配置: Any = None) -> bool:
    global 当前插件上下文, _消息接收入队, _昵称补查接收入队, _消息持久化接收入队
    global _消息数据库配置缓存, _消息数据库配置缓存时间
    _消息接收入队 = True
    _昵称补查接收入队 = True
    _消息持久化接收入队 = True
    _消息数据库配置缓存 = None
    _消息数据库配置缓存时间 = 0.0
    # 热重载不沿用旧版本遗留的群资料待刷新队列；队列由打开会话和后台轮询产生。
    群信息待刷新.clear()
    _裁剪成员资料缓存()
    if 上下文 is not None:
        当前插件上下文 = 上下文
    try:
        if _消息存储 is not None:
            try:
                插件配置 = 配置 if 配置 is not None else getattr(上下文, "config", None)
                global 当前插件配置
                当前插件配置 = 插件配置
                _消息存储.设置数据库配置(插件配置)
                _消息存储.初始化数据库()
                _从数据库恢复()
            except Exception as 恢复异常:
                logger.warning("消息记录数据库恢复失败：错误类型=%s", type(恢复异常).__name__)
        _修补botpy昵称()
        _安装消息事件挂钩()
        _安装消息发送挂钩()
        _启动群信息轮询任务()
        return True
    except Exception as exc:
        logger.warning("消息记录安装失败：错误类型=%s", type(exc).__name__)
        return False


def _从数据库恢复() -> None:
    """启动/重载时只从 MySQL 恢复会话摘要，历史消息在打开会话时分页读取。"""
    _恢复群机器人状态()
    # 热重载会保留旧模块的内存缓存，无论是否配置数据库都先清掉旧重复。
    for 会话 in 消息缓存.values():
        if isinstance(会话, dict):
            会话["messages"] = _去重消息列表(会话.get("messages") or [])
    if _消息存储 is None:
        return
    try:
        读取群信息 = getattr(_消息存储, "读取全部群信息", None)
        持久化群信息 = 读取群信息() if callable(读取群信息) else []
        恢复群数 = 0
        for 原始信息 in 持久化群信息 or []:
            if not isinstance(原始信息, dict):
                continue
            会话标识 = str(原始信息.get("group_openid") or "").strip()
            if not 会话标识:
                continue
            try:
                成员数 = max(0, int(原始信息.get("member_num") or 0))
            except (TypeError, ValueError):
                成员数 = 0
            标签 = 原始信息.get("group_tags")
            if not isinstance(标签, list):
                标签 = [] if 标签 in (None, "") else [标签]
            资料 = {
                "group_openid": 会话标识,
                "appid": str(原始信息.get("appid") or ""),
                "group_name": str(原始信息.get("group_name") or ""),
                "group_finger_memo": str(原始信息.get("group_finger_memo") or ""),
                "group_class_text": str(原始信息.get("group_class_text") or ""),
                "group_tags": [str(值).strip() for 值 in 标签 if str(值 or "").strip()],
                "member_num": 成员数,
                "is_admin": bool(原始信息.get("is_admin")),
                "updated_at": int(原始信息.get("updated_at") or 0),
            }
            成员状态 = _读取群机器人状态(会话标识)
            资料["membership_status"] = str(成员状态.get("status") or "unknown")
            资料["membership_checked_at"] = int(成员状态.get("checked_at") or 0)
            资料["member_role"] = str(成员状态.get("member_role") or "")
            现有 = 群信息缓存.get(会话标识) or {}
            try:
                资料时间 = int(资料.get("updated_at") or 0)
            except (TypeError, ValueError):
                资料时间 = 0
            try:
                现有时间 = int(现有.get("updated_at") or 0)
            except (TypeError, ValueError):
                现有时间 = 0
            try:
                现有成员数 = int(现有.get("member_num") or 0)
            except (TypeError, ValueError):
                现有成员数 = 0
            现有有资料 = bool(
                str(现有.get("group_name") or "").strip()
                or str(现有.get("group_finger_memo") or "").strip()
                or str(现有.get("group_class_text") or "").strip()
                or 现有.get("group_tags")
                or 现有成员数 > 0
                or bool(现有.get("is_admin"))
            )
            if not 现有 or not 现有有资料 or 资料时间 >= 现有时间:
                群信息缓存[会话标识] = 资料
                恢复群数 += 1
        if 恢复群数:
            logger.info("消息记录数据库恢复群资料：数量=%s", 恢复群数)
    except Exception as exc:
        logger.debug("消息记录群资料恢复失败：错误类型=%s", type(exc).__name__)
    元数据 = {}
    try:
        元数据 = _消息存储.读取全部元数据() or {}
    except Exception as exc:
        logger.debug("消息记录元数据恢复失败：错误类型=%s", type(exc).__name__)
    if 元数据:
        global _本地缓存内存, _本地缓存时间
        _本地缓存内存 = 元数据
        _本地缓存时间 = time.time()
    持久化未读表 = _读取全部持久化未读数()
    # 热重载会保留模块级缓存；只同步未读值，不重复读取整段历史。
    for 已有会话标识, 已有会话 in 消息缓存.items():
        if 已有会话标识 in _未读待写:
            已有会话["unread"] = _未读待写[已有会话标识]
        elif 已有会话标识 in 持久化未读表:
            已有会话["unread"] = max(
                int(已有会话.get("unread") or 0),
                int(持久化未读表.get(已有会话标识) or 0),
            )
    置顶列表 = [str(x) for x in (元数据.get("pinned") or []) if str(x or "").strip()]
    # 只恢复会话骨架和最后一条摘要；历史消息在打开会话时由分页接口读取。
    会话骨架: list[dict[str, Any]] = []
    try:
        聚合聊天列表 = getattr(_消息存储, "聚合聊天列表", None)
        if callable(聚合聊天列表):
            会话骨架 = 聚合聊天列表(500) or []
    except Exception as exc:
        logger.debug("消息记录会话摘要恢复失败：错误类型=%s", type(exc).__name__)
    摘要表: dict[int, dict[str, Any]] = {}
    try:
        摘要读取 = getattr(_消息存储, "批量读取最后消息摘要", None)
        摘要ID = [int(项.get("last_id") or 0) for 项 in 会话骨架 if int(项.get("last_id") or 0)]
        if callable(摘要读取) and 摘要ID:
            摘要表 = 摘要读取(摘要ID) or {}
    except Exception as exc:
        logger.debug("消息记录最后摘要恢复失败：错误类型=%s", type(exc).__name__)
    恢复数 = 0
    最大序号 = 0
    已恢复会话: set[str] = set()
    for 项 in 会话骨架:
        会话标识 = str(项.get("会话标识") or "").strip()
        if not 会话标识:
            continue
        已恢复会话.add(会话标识)
        最后ID = int(项.get("last_id") or 0)
        最后 = dict(摘要表.get(最后ID) or {})
        _规范化聊天摘要(最后)
        类型 = str(最后.get("chat_type") or "group")
        appid = str(最后.get("appid") or "")
        会话 = _取得会话缓存(会话标识, 类型, appid)
        会话["msg_count"] = max(
            int(会话.get("msg_count") or 0),
            int(项.get("msg_count") or 0),
        )
        if 会话标识 not in _未读待写 and 会话标识 in 持久化未读表:
            会话["unread"] = max(0, int(持久化未读表.get(会话标识) or 0))
        摘要时间 = int(最后.get("ts") or 项.get("last_ts") or 0)
        if 摘要时间 >= int(会话.get("last_ts") or 0):
            会话["last_content"] = _替换提及名称(最后.get("content") or "", 会话标识)
            会话["last_nickname"] = str(最后.get("nickname") or "")
            会话["last_message_id"] = str(最后.get("message_id") or "")
            会话["last_ts"] = 摘要时间
        最大序号 = max(最大序号, 最后ID)
        恢复数 += 1
    # 置顶/备注/昵称中的会话即使没有消息也保留占位，但不触发历史读取。
    元数据会话: set[str] = set()
    for 键 in ("pinned", "remarks", "nicknames"):
        值 = 元数据.get(键)
        if isinstance(值, dict):
            元数据会话.update(str(会话 or "").strip() for 会话 in 值)
        elif isinstance(值, list):
            元数据会话.update(str(会话 or "").strip() for 会话 in 值)
    for 会话标识 in 元数据会话 - 已恢复会话:
        会话标识 = str(会话标识 or "").strip()
        if not 会话标识 or 会话标识 in 消息缓存:
            continue
        会话 = _取得会话缓存(会话标识, "group", "")
        if 会话标识 not in _未读待写 and 会话标识 in 持久化未读表:
            会话["unread"] = max(0, int(持久化未读表.get(会话标识) or 0))
        if 会话标识 in 置顶列表 or 会话标识 in 元数据会话:
            恢复数 += 1
    global 发送序号
    if 最大序号 > 发送序号:
        发送序号 = 最大序号
    if 恢复数:
        logger.info("消息记录数据库恢复会话摘要：数量=%s，历史消息按会话分页加载", 恢复数)
