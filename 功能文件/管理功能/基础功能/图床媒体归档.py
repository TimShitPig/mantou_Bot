"""把消息附件逐项保存到自建图床；原 QQ 地址和附件索引保持不变。"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import ipaddress
import json
import logging
import math
import os
import re
import shutil
import socket
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit
from uuid import uuid4

import aiohttp

try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger(__name__)


_QQ主机后缀 = ("qq.com", "qq.com.cn", "qpic.cn", "qlogo.cn")
_图床主机 = "mantou-imgbed.pages.dev"
_进度字段 = frozenset({
    "stage", "operation", "submitted", "confirmed", "upload_id", "next_chunk", "total_chunks",
    "folder", "size", "sha256", "original_name", "content_type", "media_kind", "token_fingerprint", "started_at",
    "result_url", "uploaded_at",
})
_待归档 = globals().get("_待归档")
if not isinstance(_待归档, dict):
    _待归档 = {}
_归档任务 = globals().get("_归档任务")
if not isinstance(_归档任务, set):
    _归档任务 = set()
_接收开启 = False
_停止中 = False
_唤醒 = globals().get("_唤醒")
_当前配置 = globals().get("_当前配置")
_登记任务 = globals().get("_登记任务")
if not isinstance(_登记任务, set):
    _登记任务 = set()
# 热重载时清除旧版本保存的并发额度，不让旧信号量继续约束新任务。
globals().pop("_登记额度", None)
globals().pop("最大并发数", None)
_恢复任务 = globals().get("_恢复任务")
_存储操作白名单 = frozenset({"read", "update", "restore", "readiness"})
_存储阶段白名单 = frozenset({"config", "connect", "query", "decode", "state_unavailable"})
_存储分类白名单 = frozenset({
    "configuration", "dependency", "dns", "timeout", "network", "tls", "tls_required",
    "tls_unavailable", "authentication", "host_denied", "permission", "database_missing",
    "auth_plugin", "server_busy", "unknown", "schema", "invalid_data", "unavailable",
    "initialization_pending", "initialization_failed", "database_changed",
})
_存储错误类型白名单 = frozenset({
    "RuntimeError", "ValueError", "TypeError", "OperationalError", "ProgrammingError",
    "InterfaceError", "InternalError", "DataError", "IntegrityError", "TimeoutError",
    "OSError", "ConnectionError", "DatabaseError", "Error", "UnicodeDecodeError",
    "JSONDecodeError", "数据库连接错误",
})


def _存储错误字段(异常: BaseException, 操作: str = "") -> dict[str, Any]:
    """只保留受控分类和数字码，不提取异常正文、SQL或连接配置。"""
    原操作 = getattr(异常, "operation", 操作)
    原阶段 = getattr(异常, "storage_stage", None) or getattr(异常, "stage", "")
    分类 = getattr(异常, "category", "unknown")
    错误码 = getattr(异常, "mysql_code", None)
    根类型 = getattr(异常, "source_error_type", None) or type(异常).__name__
    return {
        "operation": 原操作 if type(原操作) is str and 原操作 in _存储操作白名单 else 操作 if 操作 in _存储操作白名单 else "",
        "storage_stage": 原阶段 if type(原阶段) is str and 原阶段 in _存储阶段白名单 else "unknown",
        "category": 分类 if type(分类) is str and 分类 in _存储分类白名单 else "unknown",
        "mysql_code": 错误码 if type(错误码) is int and 0 < 错误码 < 100000 else None,
        "source_error_type": 根类型 if type(根类型) is str and 根类型 in _存储错误类型白名单 else "Error",
    }


class 图床归档错误(RuntimeError):
    def __init__(self, stage: str, status: int | None = None, *, operation: str = "",
                 storage_stage: str = "", category: str = "unknown", mysql_code: int | None = None,
                 source_error_type: str = ""):
        super().__init__(stage)
        self.stage, self.status = stage, status
        self.operation, self.storage_stage = operation, storage_stage
        self.category, self.mysql_code, self.source_error_type = category, mysql_code, source_error_type


class _公网解析器(aiohttp.abc.AbstractResolver):
    """校验实际连接所用的 DNS 结果，不能依赖另一次预先解析。"""
    def __init__(self):
        self._resolver = aiohttp.DefaultResolver()

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET):
        结果 = await self._resolver.resolve(host, port, family=family)
        try:
            if not 结果 or any(not ipaddress.ip_address(项["host"]).is_global for 项 in 结果):
                raise 图床归档错误("source_host_not_public")
        except (KeyError, ValueError, TypeError):
            raise 图床归档错误("source_host_not_public") from None
        return 结果

    async def close(self):
        await self._resolver.close()


def _种类(项目: dict[str, Any]) -> str:
    for 字段 in ("media_kind", "type", "media_type"):
        类型 = str(项目.get(字段) or "").strip().lower()
        if 类型 in {"图片", "image", "img"}:
            return "image"
        if 类型 in {"视频", "video"}:
            return "video"
        if 类型 in {"音频", "语音", "audio", "voice", "record", "recordmusic"}:
            return "audio"
        if 类型 in {"文件", "file", "document", "files"}:
            return "file"
    MIME = str(项目.get("content_type") or 项目.get("mime_type") or "").lower()
    for 前缀, 类型 in (("image/", "image"), ("video/", "video"), ("audio/", "audio")):
        if MIME.startswith(前缀):
            return 类型
    return "file"


def _附件列表(媒体: Any) -> list[tuple[int, dict[str, Any]]]:
    if not isinstance(媒体, dict):
        return []
    项目 = 媒体.get("items")
    项目 = 项目 if isinstance(项目, list) and 项目 else [媒体]
    return [(索引, 值) for 索引, 值 in enumerate(项目) if isinstance(值, dict)]


def _源地址(项目: dict[str, Any]) -> str:
    return str(项目.get("src") or 项目.get("url") or 项目.get("download_url") or "").strip()


def _图床地址(值: Any) -> str:
    if not isinstance(值, str) or not 值 or len(值) > 8192:
        return ""
    if any(字符.isspace() or ord(字符) < 32 or 127 <= ord(字符) <= 159 for 字符 in 值):
        return ""
    try:
        地址 = urlsplit(值)
        解码路径 = unquote(地址.path)
        if (地址.scheme == "https" and 地址.hostname == _图床主机 and 地址.port in (None, 443)
                and 地址.username is None and 地址.password is None and 地址.path.startswith("/file/")
                and len(地址.path) > 6 and not 地址.query and not 地址.fragment and "\\" not in 解码路径
                and not any(段 in {".", ".."} for 段 in 解码路径.split("/"))
                and not any(ord(字符) < 32 or ord(字符) == 127 for 字符 in 解码路径)):
            return 值
    except ValueError:
        pass
    return ""


def 构造网页媒体字段(媒体: Any) -> Any:
    """只新增保存状态和已确认外链，不改变原地址、顺序或图文索引。"""
    if not isinstance(媒体, dict):
        return 媒体
    结果 = copy.deepcopy(媒体)
    归档列表 = 结果.get("_imgbed_archives")
    归档列表 = 归档列表 if isinstance(归档列表, dict) else {}
    for 索引, 项目 in _附件列表(结果):
        项目.pop("imgbed_url", None)
        项目.pop("imgbed_status", None)
        归档 = 归档列表.get(str(索引))
        if not isinstance(归档, dict):
            continue
        状态 = str(归档.get("status") or "")
        状态 = {"saved": "stored", "pending": "queued", "saving": "uploading"}.get(状态, 状态)
        if 状态 in {"queued", "pending", "downloaded", "waiting_token", "waiting_source", "downloading", "uploading", "saving", "unknown", "failed", "saved", "stored"}:
            项目["imgbed_status"] = 状态
        地址 = _图床地址(归档.get("url"))
        if 状态 in {"stored", "saved"} and 地址:
            项目["imgbed_url"] = 地址
        elif 状态 in {"stored", "saved"}:
            项目["imgbed_status"] = "failed"
    if isinstance(结果.get("items"), list) and 结果["items"] and isinstance(结果["items"][0], dict):
        for 字段 in ("imgbed_url", "imgbed_status"):
            结果.pop(字段, None)
            if 字段 in 结果["items"][0]:
                结果[字段] = 结果["items"][0][字段]
    return 结果


def _配置快照(配置: Any, appid: str) -> tuple[dict[str, Any], str]:
    from . import 消息记录存储, 机器人作用域
    配置 = 机器人作用域.获取机器人配置(配置, appid)
    快照 = 消息记录存储.获取数据库配置快照(配置)
    键 = hashlib.sha256(json.dumps(快照, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return 快照, 键


def _配置令牌(参数: dict[str, Any]) -> str:
    from . import 机器人作用域
    配置 = 机器人作用域.获取机器人配置(参数["config_source"], 参数["appid"])
    基础 = 配置.get("basic_settings", {}) if isinstance(配置, dict) else {}
    return 基础.get("image_host_token", "") if isinstance(基础, dict) else ""


def _任务键(记录: dict[str, Any], 数据库键: str, 索引: int) -> tuple[Any, ...] | None:
    appid = str(记录.get("appid") or "")
    类型 = str(记录.get("chat_type") or "")
    会话 = str(记录.get("_session") or "")
    消息ID = str(记录.get("message_id") or "")
    历史源 = str(记录.get("history_origin") or "")
    历史序号 = 记录.get("history_order")
    if (not re.fullmatch(r"[0-9]{4,32}", appid) or 类型 not in {"group", "user"}
            or not 会话 or len(会话) > 200 or len(消息ID) > 512):
        return None
    if 历史源 and isinstance(历史序号, int) and not isinstance(历史序号, bool) and 历史序号 > 0:
        身份 = ("history", 历史源, 历史序号)
    elif 消息ID:
        身份 = ("message", 消息ID)
    else:
        return None
    return 数据库键, appid, 类型, 会话, *身份, 索引


def _每项参数(值: Any, 索引: int) -> dict[str, Any] | None:
    if not isinstance(值, dict):
        return None
    if "path" in 值 or "data" in 值 or "url" in 值 or "too_large" in 值:
        return dict(值) if 索引 == 0 else None
    单项 = 值.get(索引, 值.get(str(索引)))
    return dict(单项) if isinstance(单项, dict) else None


def _安全缓存路径(值: Any) -> Path | None:
    from . import 文件缓存
    if not isinstance(值, (str, Path)) or not str(值):
        return None
    try:
        路径 = Path(值).resolve()
        if 路径.is_relative_to(文件缓存.临时缓存目录.resolve()) and 路径 != 文件缓存.临时缓存目录.resolve():
            return 路径
    except (OSError, RuntimeError, ValueError):
        pass
    return None


def 安排归档消息媒体(配置: Any, 记录: Any, 本地来源: Any = None, 已上传结果: Any = None) -> bool:
    """同步入口只接管元数据和已准备好的缓存副本，不复制或读取媒体正文。"""
    if _停止中 or not isinstance(记录, dict) or not _附件列表(记录.get("media")):
        return False
    try:
        asyncio.get_running_loop()
        快照, 数据库键 = _配置快照(配置, str(记录.get("appid") or ""))
    except Exception:
        return False
    接受 = False
    原归档列表 = 记录["media"].get("_imgbed_archives") or {}
    for 索引, 项目 in _附件列表(记录["media"]):
        键 = _任务键(记录, 数据库键, 索引)
        if 键 is None:
            continue
        本地 = _每项参数(本地来源, 索引)
        已上传 = _每项参数(已上传结果, 索引)
        原归档 = 原归档列表.get(str(索引)) if isinstance(原归档列表, dict) else None
        if isinstance(原归档, dict) and 原归档.get("status") in {"stored", "saved"} and _图床地址(原归档.get("url")):
            _释放本地描述(本地)
            接受 = True
            continue
        保存字段 = ("_session", "chat_type", "appid", "message_id", "history_origin", "history_order", "id", "ts", "timestamp", "source", "is_self", "media")
        精简记录 = {字段: copy.deepcopy(记录[字段]) for 字段 in 保存字段 if 字段 in 记录}
        参数 = _待归档.get(键)
        if 参数 is None:
            参数 = {"record": 精简记录, "item": copy.deepcopy(项目), "index": 索引,
                    "appid": str(记录["appid"]), "database_snapshot": 快照, "database_key": 数据库键,
                    "config_source": 配置, "archive": copy.deepcopy(原归档), "retry_at": 0.0}
            _待归档[键] = 参数
        else:
            旧地址 = _源地址(参数["item"])
            参数["record"], 参数["item"] = 精简记录, copy.deepcopy(项目)
            参数["config_source"] = 配置
            if 旧地址 != _源地址(项目) and not _提交未知(参数.get("archive")):
                参数.pop("terminal", None)
                参数.pop("source_failures", None)
                参数["retry_at"] = 0.0
        if 本地 is not None:
            if not isinstance(参数.get("local"), dict):
                参数["local"] = 本地
            elif 参数["local"].get("path") != 本地.get("path"):
                _释放本地描述(本地)
            if not _提交未知(参数.get("archive")):
                参数.pop("terminal", None)
                参数["retry_at"] = 0.0
        if 已上传 is not None and _图床地址(已上传.get("url")):
            参数["confirmed_result"] = 已上传
            参数.pop("terminal", None)
            参数["retry_at"] = 0.0
        if not 参数.get("task") and not 参数.get("register_task"):
            参数["registered"] = False
        接受 = True
    _排空队列()
    return 接受


def _释放本地描述(描述: Any) -> None:
    from . import 文件缓存
    if not isinstance(描述, dict) or 描述.get("owned") is not True:
        return
    路径 = _安全缓存路径(描述.get("path"))
    if 路径 is not None:
        try:
            路径.unlink(missing_ok=True)
        except OSError:
            return
        文件缓存.解除临时缓存占用(路径)


def _提交未知(归档: Any) -> bool:
    if not isinstance(归档, dict):
        return False
    进度 = 归档.get("progress")
    return 归档.get("status") == "unknown" or isinstance(进度, dict) and 进度.get("submitted") is True and 进度.get("confirmed") is not True


def _旧大小拒绝可恢复(归档: Any) -> bool:
    """只恢复旧客户端在任何上传提交之前作出的大小拒绝。"""
    if (not isinstance(归档, dict) or 归档.get("status") != "failed"
            or 归档.get("error_stage") not in {"source_too_large", "file_size", "image_size"}
            or _提交未知(归档) or _图床地址(归档.get("url"))):
        return False
    进度 = 归档.get("progress")
    if 进度 is None or isinstance(进度, dict) and not 进度:
        return True
    return (isinstance(进度, dict) and 进度.get("submitted") is False and 进度.get("confirmed") is True
            and 进度.get("operation", "prepare") == "prepare" and 进度.get("stage", "ready") == "ready"
            and type(进度.get("next_chunk", 0)) is int and 进度.get("next_chunk", 0) == 0 and not 进度.get("upload_id"))


def _解除旧大小拒绝(参数: dict[str, Any]) -> bool:
    当前 = 参数.get("archive")
    if _提交未知(当前) or isinstance(当前, dict) and 当前.get("error_stage") == "source_expired":
        return False
    if isinstance(当前, dict):
        if 当前.get("status") in {"stored", "saved"} or 当前.get("url"):
            return False
        进度 = 当前.get("progress")
        if 进度 is not None and not (isinstance(进度, dict) and not 进度):
            if (not isinstance(进度, dict) or 进度.get("submitted") is not False or 进度.get("confirmed") is not True
                    or 进度.get("operation", "prepare") != "prepare" or 进度.get("next_chunk", 0) != 0 or 进度.get("upload_id")):
                return False
    待保存 = 参数.get("pending_state")
    if not _旧大小拒绝可恢复(当前) and not _旧大小拒绝可恢复(待保存):
        return False
    参数.pop("terminal", None)
    参数.pop("source_failures", None)
    参数.pop("last_error", None)
    参数["retry_at"] = 0.0
    if _旧大小拒绝可恢复(待保存):
        参数.pop("pending_state", None)
    return True


def _旧大小拒绝仍需保护(归档: Any) -> bool:
    return (isinstance(归档, dict) and 归档.get("status") == "failed"
            and 归档.get("error_stage") in {"source_too_large", "file_size", "image_size"}
            and not _旧大小拒绝可恢复(归档))


def _本地来源去旧大小标记(参数: dict[str, Any]) -> None:
    本地 = 参数.get("local")
    if not isinstance(本地, dict) or 本地.get("too_large") is not True:
        return
    if 本地.get("path") or isinstance(本地.get("data"), (bytes, bytearray, memoryview)):
        本地 = dict(本地)
        本地.pop("too_large", None)
        参数["local"] = 本地
    else:
        # 旧版只保留了超限标记，原件不可伪造；有远端附件地址时交给下载流程。
        参数.pop("local", None)


def _清理进度(进度: Any) -> dict[str, Any]:
    if not isinstance(进度, dict):
        return {}
    结果 = {键: copy.deepcopy(进度[键]) for 键 in _进度字段 if 键 in 进度}
    if "result_url" in 结果 and not _图床地址(结果["result_url"]):
        raise 图床归档错误("progress_invalid")
    return 结果


def _已完成进度结果(进度: Any) -> dict[str, Any] | None:
    if (not isinstance(进度, dict) or 进度.get("stage") != "completed"
            or 进度.get("submitted") is not False or 进度.get("confirmed") is not True
            or not _图床地址(进度.get("result_url"))):
        return None
    时间 = 进度.get("uploaded_at")
    if type(时间) not in (int, float) or not math.isfinite(时间) or 时间 <= 0:
        return None
    字段 = ("size", "sha256", "content_type", "original_name", "media_kind", "uploaded_at")
    return {键: copy.deepcopy(进度[键]) for 键 in 字段 if 键 in 进度} | {"url": 进度["result_url"]}


def _记录参数(参数: dict[str, Any]) -> tuple[Any, ...]:
    记录 = 参数["record"]
    return (str(记录.get("_session") or ""), str(记录.get("message_id") or ""),
            str(记录.get("chat_type") or ""), 参数["index"])


def _作用域参数(参数: dict[str, Any]) -> dict[str, Any]:
    记录 = 参数["record"]
    return {"appid": 参数["appid"], "history_origin": str(记录.get("history_origin") or ""),
            "history_order": 记录.get("history_order", 0), "数据库快照": 参数["database_snapshot"]}


async def _读取状态(参数: dict[str, Any]) -> dict[str, Any] | None:
    from . import 消息记录
    try:
        结果 = await 消息记录.读取消息图床归档(*_记录参数(参数), **_作用域参数(参数))
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        raise 图床归档错误("state_unavailable", **_存储错误字段(异常, "read")) from None
    return copy.deepcopy(结果) if isinstance(结果, dict) else None


async def _保存状态(参数: dict[str, Any], 新归档: dict[str, Any]) -> None:
    from . import 消息记录
    原归档 = 参数.get("archive")
    try:
        状态 = await 消息记录.更新消息图床归档(
            *_记录参数(参数), 原归档, 新归档, 原记录=参数["record"],
            expected_source=_源地址(参数["item"]), **_作用域参数(参数),
        )
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        raise 图床归档错误("state_unavailable", **_存储错误字段(异常, "update")) from None
    if 状态 == "updated":
        参数["archive"] = copy.deepcopy(新归档)
        参数["record"].setdefault("media", {}).setdefault("_imgbed_archives", {})[str(参数["index"])] = copy.deepcopy(新归档)
        return
    if 状态 == "missing":
        已清理 = getattr(消息记录, "_聊天记录已清理", None)
        if callable(已清理) and 已清理(参数["record"]):
            参数["gone"] = True
            raise 图床归档错误("message_missing")
        raise 图床归档错误("message_waiting")
    if 状态 == "conflict":
        参数["archive"] = await _读取状态(参数)
        raise 图床归档错误("state_conflict")
    raise 图床归档错误("state_unavailable")


def _新状态(参数: dict[str, Any], 状态: str, **字段: Any) -> dict[str, Any]:
    已有 = 参数.get("archive")
    结果 = copy.deepcopy(已有) if isinstance(已有, dict) else {}
    结果.update(status=状态, media_kind=_种类(参数["item"]),
              source_fingerprint=hashlib.sha256(_源地址(参数["item"]).encode()).hexdigest(), **字段)
    if 状态 in {"queued", "downloading", "downloaded", "uploading", "stored"} and "error_stage" not in 字段:
        结果.pop("error_stage", None)
    return 结果


async def _校验下载地址(值: str, *, 允许公网: bool = False) -> str:
    if not isinstance(值, str) or not 值 or len(值) > 8192 or re.search(r"[\x00-\x20\x7f\\]", 值):
        raise 图床归档错误("source_url_invalid")
    try:
        地址 = urlsplit(值)
        主机 = str(地址.hostname or "").lower()
        可信 = 主机 in {_图床主机, "qqbot.ugcimg.cn"} or any(主机 == 后缀 or 主机.endswith("." + 后缀) for 后缀 in _QQ主机后缀)
        if (地址.scheme != "https" or not (可信 or 允许公网 is True) or 地址.username is not None or 地址.password is not None
                or 地址.port not in (None, 443) or 地址.fragment):
            raise 图床归档错误("source_url_invalid")
        if 主机 == _图床主机 and not _图床地址(值):
            raise 图床归档错误("source_url_invalid")
        try:
            字面地址 = ipaddress.ip_address(主机)
        except ValueError:
            字面地址 = None
        if 字面地址 is not None and not 字面地址.is_global:
            raise 图床归档错误("source_host_not_public")
    except 图床归档错误:
        raise
    except (OSError, ValueError, asyncio.TimeoutError):
        raise 图床归档错误("source_dns_failed") from None
    return 值


async def _源已过期(响应: Any) -> bool:
    if 响应.status != 400:
        return False
    async def 读取() -> bytes | None:
        内容 = bytearray()
        while True:
            块 = await 响应.content.read(min(4096, 16385 - len(内容)))
            if not 块:
                return bytes(内容)
            内容.extend(块)
            if len(内容) > 16384:
                return None
    try:
        内容 = await asyncio.wait_for(读取(), timeout=10)
        结果 = json.loads(内容.decode("utf-8")) if 内容 is not None else None
        码 = 结果.get("retcode", 结果.get("code")) if isinstance(结果, dict) else None
        return type(码) is int and 码 == -5503007 or isinstance(码, str) and 码 == "-5503007"
    except asyncio.CancelledError:
        raise
    except (aiohttp.ClientError, OSError, UnicodeError, ValueError, asyncio.TimeoutError):
        return False


async def _写文件块(文件: Any, 块: Any) -> None:
    写入 = asyncio.create_task(asyncio.to_thread(文件.write, 块))
    try:
        await asyncio.shield(写入)
    except asyncio.CancelledError:
        await 写入
        raise


async def _接管缓存文件(参数: dict[str, Any], 路径: Path) -> Path:
    """待确认文件放入专属子目录，普通临时缓存清理不删除这些原件。"""
    from . import 文件缓存
    保存目录 = 文件缓存.临时缓存目录 / "图床待保存"
    await asyncio.to_thread(保存目录.mkdir, parents=True, exist_ok=True)
    if 路径.parent.resolve() == 保存目录.resolve():
        文件缓存.标记临时缓存正在使用(路径)
        return 路径
    后缀 = 路径.suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,12}", 路径.suffix) else ".bin"
    目标 = 保存目录 / (uuid4().hex + 后缀)
    移动 = asyncio.create_task(asyncio.to_thread(os.replace, 路径, 目标))
    已取消 = False
    try:
        await asyncio.shield(移动)
    except asyncio.CancelledError:
        await 移动
        已取消 = True
    参数.setdefault("local", {}).update(path=str(目标), owned=True)
    文件缓存.标记临时缓存正在使用(目标)
    文件缓存.解除临时缓存占用(路径)
    if 已取消:
        raise asyncio.CancelledError
    return 目标


async def _下载来源(地址: str, 路径: Path, *, 允许公网: bool = False) -> tuple[int, str]:
    try:
        return await _下载已验证来源(地址, 路径, 允许公网=允许公网)
    except asyncio.CancelledError:
        raise
    except 图床归档错误:
        raise
    except aiohttp.ClientSSLError:
        raise 图床归档错误("source_tls_error") from None
    except (aiohttp.ClientError, OSError, asyncio.TimeoutError):
        raise 图床归档错误("source_request") from None


async def _下载已验证来源(地址: str, 路径: Path, *, 允许公网: bool = False) -> tuple[int, str]:
    解析器 = _公网解析器()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, connect=20, sock_read=90),
                                         connector=aiohttp.TCPConnector(limit=0, resolver=解析器, use_dns_cache=False),
                                         cookie_jar=aiohttp.DummyCookieJar(), trust_env=False) as 会话:
            return await _下载会话来源(会话, 地址, 路径, 允许公网=允许公网)
    finally:
        await 解析器.close()


async def _下载会话来源(会话: Any, 地址: str, 路径: Path, *, 允许公网: bool = False) -> tuple[int, str]:
    for 跳转 in range(5):
        地址 = await _校验下载地址(地址, 允许公网=允许公网)
        响应 = await 会话.get(地址, allow_redirects=False, headers={"User-Agent": "Mozilla/5.0"})
        try:
            if 响应.status in {301, 302, 303, 307, 308}:
                位置 = 响应.headers.get("Location", "")
                if not 位置 or 跳转 == 4:
                    raise 图床归档错误("source_redirect_invalid")
                地址 = urljoin(地址, 位置)
                continue
            if 响应.status != 200:
                过期 = await _源已过期(响应)
                raise 图床归档错误("source_expired" if 过期 else "source_http", 响应.status)
            总长度 = 响应.content_length
            已读 = 0
            with 路径.open("wb") as 文件:
                async for 块 in 响应.content.iter_chunked(65536):
                    已读 += len(块)
                    await _写文件块(文件, 块)
            if 已读 <= 0 or 总长度 is not None and 已读 != 总长度:
                raise 图床归档错误("source_incomplete", 响应.status)
            return 已读, str(响应.headers.get("Content-Type") or "application/octet-stream").split(";", 1)[0]
        finally:
            响应.release()
    raise 图床归档错误("source_redirect_invalid")


async def _准备本地文件(参数: dict[str, Any]) -> Path:
    from . import 文件缓存
    _本地来源去旧大小标记(参数)
    已有 = 参数.get("archive")
    本地 = 参数.get("local")
    if isinstance(本地, dict) and 本地.get("complete") is False:
        if 本地.get("remote") is True:
            本地 = None
        else:
            raise 图床归档错误("source_incomplete")
    if not isinstance(本地, dict) and isinstance(已有, dict) and 已有.get("local_complete") is True:
        路径 = _安全缓存路径(已有.get("local_path"))
        if 路径 is not None and await asyncio.to_thread(路径.is_file):
            本地 = 参数["local"] = {"path": str(路径), "owned": True}
    if isinstance(本地, dict):
        原路径 = Path(本地["path"]) if 本地.get("path") else None
        if 原路径 is not None:
            大小 = (await asyncio.to_thread(原路径.stat)).st_size
            if 大小 <= 0:
                raise 图床归档错误("source_data_invalid")
            安全路径 = _安全缓存路径(原路径)
            if 本地.get("owned") is True and 安全路径 is not None and 本地.get("complete", True):
                文件缓存.标记临时缓存正在使用(安全路径)
                return await _接管缓存文件(参数, 安全路径)
        else:
            数据 = 本地.get("data")
            if not isinstance(数据, (bytes, bytearray, memoryview)) or not 数据:
                raise 图床归档错误("source_data_invalid")
        新路径 = 文件缓存.创建临时缓存文件("mantou-imgbed-media-", ".bin")
        文件缓存.标记临时缓存正在使用(新路径)
        参数["local"] = {**本地, "path": str(新路径), "owned": True, "complete": False}
        参数["local"].pop("data", None)
        if 原路径 is not None:
            复制 = asyncio.create_task(asyncio.to_thread(shutil.copyfile, 原路径, 新路径))
            try:
                await asyncio.shield(复制)
            except asyncio.CancelledError:
                await 复制
                raise
        else:
            with 新路径.open("wb") as 文件:
                视图 = memoryview(数据)
                for 起点 in range(0, len(视图), 65536):
                    await _写文件块(文件, 视图[起点:起点 + 65536])
        参数["local"]["complete"] = True
        return await _接管缓存文件(参数, 新路径)
    地址 = _源地址(参数["item"])
    if not 地址.startswith("https://"):
        raise 图床归档错误("source_waiting")
    路径 = _安全缓存路径(已有.get("local_path")) if isinstance(已有, dict) else None
    if 路径 is None:
        路径 = 文件缓存.创建临时缓存文件("mantou-imgbed-media-", ".bin")
    文件缓存.标记临时缓存正在使用(路径)
    参数["local"] = {"path": str(路径), "owned": True, "complete": False, "remote": True}
    路径 = await _接管缓存文件(参数, 路径)
    await _保存状态(参数, _新状态(参数, "downloading", local_path=str(路径), local_complete=False))
    参数["source_attempt"] = 地址
    大小, MIME = await _下载来源(地址, 路径, 允许公网=参数["record"].get("is_self") is True)
    参数["local_complete"] = True
    参数["local"]["complete"] = True
    await _保存状态(参数, _新状态(参数, "downloaded", local_path=str(路径), local_complete=True, size=大小, content_type=MIME))
    return 路径


async def _执行归档(参数: dict[str, Any]) -> None:
    from . import 自建图床
    已存 = await _读取状态(参数)
    if isinstance(已存, dict):
        参数["archive"] = 已存
    归档 = 参数.get("archive")
    已解除大小拒绝 = _解除旧大小拒绝(参数)
    if _旧大小拒绝可恢复(参数.get("pending_state")) and not 已解除大小拒绝 and isinstance(归档, dict):
        # 较新的已提交/已确认状态优先于旧大小失败回填，不回退其进度。
        参数.pop("pending_state", None)
        if 参数.get("terminal") and not 参数.get("confirmed_result"):
            if 归档.get("status") in {"stored", "saved"} and _图床地址(归档.get("url")):
                参数["done"] = True
            return
    if isinstance(参数.get("pending_state"), dict):
        await _保存状态(参数, 参数["pending_state"])
        参数.pop("pending_state", None)
        if 参数.get("terminal"):
            return
        归档 = 参数.get("archive")
    已完成 = _已完成进度结果(归档.get("progress")) if isinstance(归档, dict) else None
    if 已完成:
        参数["confirmed_result"] = 已完成
    if isinstance(归档, dict) and 归档.get("status") in {"stored", "saved"} and _图床地址(归档.get("url")):
        参数["done"] = True
        return
    if _提交未知(归档) and not 参数.get("confirmed_result"):
        参数["terminal"] = True
        return
    if _旧大小拒绝仍需保护(归档) and not 参数.get("confirmed_result"):
        参数["terminal"] = True
        return
    if (isinstance(归档, dict) and 归档.get("error_stage") == "source_expired"
            and 归档.get("source_fingerprint") == hashlib.sha256(_源地址(参数["item"]).encode()).hexdigest()
            and not 参数.get("confirmed_result") and not 参数.get("local")):
        参数["terminal"] = True
        return
    if not 参数.get("confirmed_result"):
        Token = _配置令牌(参数)
        if not isinstance(Token, str) or not Token:
            raise 图床归档错误("not_configured")
        路径 = await _准备本地文件(参数)
        本地 = 参数.get("local") or {}
        项目 = 参数["item"]
        原名 = str(本地.get("original_name") or 本地.get("name") or 项目.get("name") or 项目.get("filename") or "file.bin")
        await _保存状态(参数, _新状态(参数, "downloaded", local_path=str(路径), local_complete=True))
        async def 提交前(进度: Any = None) -> None:
            旧进度 = (参数.get("archive") or {}).get("progress")
            值 = {**(旧进度 if isinstance(旧进度, dict) else {}), **(进度 if isinstance(进度, dict) else {})}
            干净进度 = _清理进度(值)
            干净进度.update(submitted=True, confirmed=False)
            await _保存状态(参数, _新状态(参数, "uploading", progress=干净进度, local_path=str(路径), local_complete=True))
        async def 保存进度(进度: Any) -> None:
            if not isinstance(进度, dict):
                raise 图床归档错误("progress_invalid")
            干净进度 = _清理进度(进度)
            await _保存状态(参数, _新状态(参数, "uploading", progress=干净进度, local_path=str(路径), local_complete=True))
        当前进度 = 归档.get("progress") if isinstance(归档, dict) else None
        结果 = await 自建图床.上传文件(
            路径, Token, 文件名=原名, 媒体种类=_种类({**项目, **本地}),
            提交前=提交前, 进度回调=保存进度, 进度=copy.deepcopy(当前进度) if isinstance(当前进度, dict) else None,
        )
        if not isinstance(结果, dict) or not _图床地址(结果.get("url")):
            raise 图床归档错误("upload_result_invalid")
        参数["confirmed_result"] = 结果
    结果 = 参数["confirmed_result"]
    字段 = ("url", "size", "sha256", "content_type", "original_name", "media_kind", "uploaded_at")
    新归档 = {键: copy.deepcopy(结果[键]) for 键 in 字段 if 键 in 结果}
    新归档.update(status="stored", media_kind=结果.get("media_kind") or _种类(参数["item"]))
    if not _图床地址(新归档.get("url")):
        raise 图床归档错误("upload_result_invalid")
    await _保存状态(参数, 新归档)
    参数["done"] = True


async def _处理任务(键: tuple[Any, ...], 参数: dict[str, Any]) -> None:
    from . import 机器人作用域
    try:
        _, 当前数据库键 = _配置快照(参数["config_source"], 参数["appid"])
        if 当前数据库键 != 参数["database_key"]:
            参数["terminal"] = True
            return
        with 机器人作用域.绑定机器人作用域(参数["appid"]):
            await _执行归档(参数)
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        阶段 = getattr(异常, "stage", "archive")
        归档 = 参数.get("archive")
        if (str(阶段).startswith("source_") and 参数.get("source_attempt")
                and 参数["source_attempt"] != _源地址(参数["item"]) and not _提交未知(归档)):
            参数.pop("terminal", None)
            参数.pop("source_failures", None)
            参数["retry_at"] = 0.0
            return
        已确认进度 = None
        try:
            错误进度 = _清理进度(getattr(异常, "progress", None))
            if 错误进度:
                已完成 = _已完成进度结果(错误进度)
                if 已完成:
                    参数["confirmed_result"] = 已完成
                if 错误进度.get("submitted") is False and 错误进度.get("confirmed") is True:
                    已确认进度 = 错误进度
        except 图床归档错误:
            pass
        if 已确认进度 is not None:
            参数["pending_state"] = _新状态(参数, "saving" if 参数.get("confirmed_result") else "uploading", progress=已确认进度)
            参数.pop("terminal", None)
            try:
                await _保存状态(参数, 参数["pending_state"])
                参数.pop("pending_state", None)
            except 图床归档错误:
                pass
        elif _提交未知(归档) and not 参数.get("confirmed_result"):
            参数["terminal"] = True
        elif 阶段 == "source_waiting":
            参数["terminal"] = True
        elif 阶段 in {"source_expired", "source_url_invalid", "source_host_not_public", "source_tls_error"}:
            参数["terminal"] = True
        elif str(阶段).startswith("source_"):
            参数["source_failures"] = int(参数.get("source_failures", 0)) + 1
            参数["terminal"] = 参数["source_failures"] >= 3
        elif 阶段 not in {"state_unavailable", "state_conflict", "message_missing", "message_waiting", "not_configured"}:
            参数["terminal"] = True
        if 已确认进度 is None and 阶段 not in {"state_unavailable", "state_conflict", "message_missing", "message_waiting"}:
            状态 = "unknown" if _提交未知(归档) else ("waiting_token" if 阶段 == "not_configured" else "waiting_source" if 阶段 == "source_waiting" else "failed")
            参数["pending_state"] = _新状态(参数, 状态, error_stage=str(阶段))
            try:
                await _保存状态(参数, 参数["pending_state"])
                参数.pop("pending_state", None)
            except 图床归档错误:
                参数["retry_at"] = asyncio.get_running_loop().time() + 30.0
        if not 参数.get("terminal"):
            参数["retry_at"] = asyncio.get_running_loop().time() + 30.0
        if 参数.get("last_error") != 阶段:
            详情 = _存储错误字段(异常)
            logger.warning(
                "自建图床媒体保存失败：阶段=%s，数据库操作=%s，数据库阶段=%s，分类=%s，MySQL错误码=%s，根错误类型=%s，媒体序号=%s，HTTP状态=%s，错误类型=%s",
                阶段, 详情["operation"] or "none", 详情["storage_stage"], 详情["category"],
                详情["mysql_code"] if 详情["mysql_code"] is not None else "none", 详情["source_error_type"],
                参数["index"], getattr(异常, "status", None) or "none", type(异常).__name__,
            )
            参数["last_error"] = 阶段
    finally:
        if 参数.get("done") or 参数.get("gone"):
            _释放本地描述(参数.get("local"))
            _待归档.pop(键, None)
        参数.pop("task", None)


def _任务完成(任务: asyncio.Task[Any]) -> None:
    _归档任务.discard(任务)
    if not 任务.cancelled():
        任务.exception()
    _排空队列()


async def _登记单项(键: tuple[Any, ...], 参数: dict[str, Any]) -> None:
    """先独立落待保存状态；大文件不阻塞后续元数据登记。"""
    from . import 机器人作用域
    try:
        with 机器人作用域.绑定机器人作用域(参数["appid"]):
            已有 = await _读取状态(参数)
            if isinstance(已有, dict):
                参数["archive"] = 已有
            归档 = 参数.get("archive")
            _解除旧大小拒绝(参数)
            已完成 = _已完成进度结果(归档.get("progress")) if isinstance(归档, dict) else None
            if 已完成:
                参数["confirmed_result"] = 已完成
            if isinstance(归档, dict) and 归档.get("status") in {"saved", "stored"} and _图床地址(归档.get("url")):
                参数["done"] = True
                return
            if 参数.get("confirmed_result"):
                # 完成进度恢复后仍需接管已完整的专属原件，保存成功时才能释放。
                # 显式传入的本地描述保留其 owned 属性，不接管用户原路径。
                if (isinstance(归档, dict) and 归档.get("local_complete") is True
                        and not isinstance(参数.get("local"), dict)):
                    from . import 文件缓存
                    路径 = _安全缓存路径(归档.get("local_path"))
                    专属目录 = (文件缓存.临时缓存目录 / "图床待保存").resolve()
                    if (路径 is not None and 路径.parent == 专属目录
                            and await asyncio.to_thread(路径.is_file)):
                        文件缓存.标记临时缓存正在使用(路径)
                        参数["local"] = {"path": str(路径), "owned": True, "complete": True}
                参数["registered"] = True
                return
            if isinstance(归档, dict):
                路径 = _安全缓存路径(归档.get("local_path"))
                if 路径 is not None and await asyncio.to_thread(路径.is_file):
                    from . import 文件缓存
                    文件缓存.标记临时缓存正在使用(路径)
                    参数.setdefault("local", {"path": str(路径), "owned": True,
                                               "complete": 归档.get("local_complete") is True,
                                               "remote": 归档.get("local_complete") is not True})
            if _提交未知(归档) and not 参数.get("confirmed_result"):
                参数["terminal"] = True
                参数["registered"] = True
                return
            if _旧大小拒绝仍需保护(归档):
                参数["terminal"] = True
                参数["registered"] = True
                return
            if (isinstance(归档, dict) and 归档.get("error_stage") == "source_expired"
                    and 归档.get("source_fingerprint") == hashlib.sha256(_源地址(参数["item"]).encode()).hexdigest()
                    and not 参数.get("confirmed_result") and not (参数.get("local") or {}).get("complete")):
                参数["terminal"] = True
                参数["registered"] = True
                return
            字段 = {}
            _本地来源去旧大小标记(参数)
            if isinstance(参数.get("local"), dict) and 参数["local"].get("complete", True):
                路径 = await _准备本地文件(参数)
                字段.update(local_path=str(路径), local_complete=True)
            状态 = "queued" if _源地址(参数["item"]).startswith("https://") or 参数.get("local") or 参数.get("confirmed_result") else "waiting_source"
            await _保存状态(参数, _新状态(参数, 状态, **字段))
            参数["registered"] = True
            if 状态 == "waiting_source":
                参数["terminal"] = True
    except asyncio.CancelledError:
        raise
    except Exception as 异常:
        if 参数.get("gone"):
            return
        参数["retry_at"] = asyncio.get_running_loop().time() + 30.0
        阶段 = getattr(异常, "stage", "state_unavailable")
        if 参数.get("last_error") != 阶段:
            详情 = _存储错误字段(异常)
            logger.warning(
                "自建图床待保存登记失败：阶段=%s，数据库操作=%s，数据库阶段=%s，分类=%s，MySQL错误码=%s，根错误类型=%s，媒体序号=%s，错误类型=%s",
                阶段, 详情["operation"] or "none", 详情["storage_stage"], 详情["category"],
                详情["mysql_code"] if 详情["mysql_code"] is not None else "none",
                详情["source_error_type"], 参数["index"], type(异常).__name__,
            )
            参数["last_error"] = 阶段
    finally:
        if 参数.get("done") or 参数.get("gone"):
            _释放本地描述(参数.get("local"))
            _待归档.pop(键, None)
        参数.pop("register_task", None)


def _登记完成(任务: asyncio.Task[Any]) -> None:
    _登记任务.discard(任务)
    if not 任务.cancelled():
        任务.exception()
    _排空队列()


def _排空队列() -> None:
    global _唤醒
    if _唤醒 is not None:
        _唤醒.cancel()
        _唤醒 = None
    if not _接收开启 or _停止中:
        return
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return
    最早 = None
    for 键, 参数 in list(_待归档.items()):
        if 参数.get("terminal") and not 参数.get("pending_state") or isinstance(参数.get("task"), asyncio.Task) or isinstance(参数.get("register_task"), asyncio.Task):
            continue
        截止 = float(参数.get("retry_at") or 0)
        if 截止 > 循环.time():
            最早 = 截止 if 最早 is None else min(最早, 截止)
            continue
        if not 参数.get("registered"):
            任务 = asyncio.create_task(_登记单项(键, 参数), name="自建图床待保存登记")
            参数["register_task"] = 任务
            _登记任务.add(任务)
            任务.add_done_callback(_登记完成)
            continue
        任务 = asyncio.create_task(_处理任务(键, 参数), name="自建图床媒体保存")
        参数["task"] = 任务
        _归档任务.add(任务)
        任务.add_done_callback(_任务完成)
    if 最早 is not None:
        _唤醒 = 循环.call_at(最早, _排空队列)


def 启动媒体归档任务(配置: Any) -> None:
    global _接收开启, _停止中, _当前配置, _恢复任务
    _当前配置 = 配置
    _停止中 = False
    _接收开启 = True
    for 参数 in _待归档.values():
        _解除旧大小拒绝(参数)
        if 参数.get("last_error") in {"not_configured", "state_unavailable", "state_conflict", "message_waiting"} and not _提交未知(参数.get("archive")):
            参数.pop("terminal", None)
            参数["retry_at"] = 0.0
    _排空队列()
    if _恢复任务 is None or _恢复任务.done():
        _恢复任务 = asyncio.create_task(_恢复待处理任务(配置), name="自建图床任务恢复")


async def _恢复待处理任务(配置: Any) -> None:
    from . import 消息记录, 消息记录存储
    已扫描 = set()
    for 会话表 in (getattr(消息记录, "作用域消息缓存", {}), getattr(消息记录, "消息缓存", {})):
        for 会话 in list(会话表.values()) if isinstance(会话表, dict) else []:
            if not isinstance(会话, dict):
                continue
            for 记录 in list(会话.get("messages") or []):
                if not _接收开启 or _停止中:
                    return
                if not isinstance(记录, dict) or id(记录) in 已扫描:
                    continue
                已扫描.add(id(记录))
                归档 = (记录.get("media") or {}).get("_imgbed_archives") if isinstance(记录.get("media"), dict) else None
                if isinstance(归档, dict) and 归档:
                    安排归档消息媒体(配置, 记录)
    快照 = 消息记录存储.获取数据库配置快照(配置)
    游标 = 0
    while _接收开启 and not _停止中:
        try:
            批次 = await 消息记录.列出待处理图床消息(after_id=游标, limit=200, 数据库快照=快照)
            if not isinstance(批次, dict):
                raise 图床归档错误("state_unavailable")
            for 记录 in 批次.get("records") or []:
                if not _接收开启 or _停止中:
                    return
                if isinstance(记录, dict):
                    安排归档消息媒体(配置, 记录)
            if not 批次.get("has_more"):
                return
            下一个 = 批次.get("next_id")
            if not isinstance(下一个, int) or isinstance(下一个, bool) or 下一个 <= 游标:
                raise 图床归档错误("state_cursor_invalid")
            游标 = 下一个
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception as 异常:
            详情 = _存储错误字段(异常, "restore")
            logger.warning(
                "自建图床任务恢复失败：阶段=state_restore，数据库操作=%s，数据库阶段=%s，分类=%s，MySQL错误码=%s，根错误类型=%s，错误类型=%s",
                详情["operation"], 详情["storage_stage"], 详情["category"],
                详情["mysql_code"] if 详情["mysql_code"] is not None else "none",
                详情["source_error_type"], type(异常).__name__,
            )
            await asyncio.sleep(30)


async def 停止媒体归档任务() -> None:
    global _接收开启, _停止中, _唤醒
    _接收开启 = False
    _停止中 = True
    if _唤醒 is not None:
        _唤醒.cancel()
        _唤醒 = None
    任务列表 = list(_归档任务 | _登记任务)
    if isinstance(_恢复任务, asyncio.Task) and not _恢复任务.done():
        任务列表.append(_恢复任务)
    for 任务 in 任务列表:
        任务.cancel()
    if 任务列表:
        await asyncio.gather(*任务列表, return_exceptions=True)
    _归档任务.clear()
    _登记任务.clear()
