"""Sáng Tác Việt 小说、独立账号和可关闭的在线/奖励任务。"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import html
import json
import math
from pathlib import Path
import random
import re
import time
from typing import Any, AsyncIterator, Callable
from urllib.parse import parse_qs, unquote, urlsplit
import uuid

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from .STV协议 import STVClient, STVError, STV_DOWNLOAD_CONCURRENCY, _close_idle_connector
from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    已配置运行状态数据库, 读取运行状态值, 写入运行状态值, 获取数据库配置, 数据库连接错误,
    比较并更新运行状态值, 批量读取运行状态值,
)
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题, 格式化小说字数

_锁表 = globals().get("_锁表") or {}
_任务表 = globals().get("_任务表") or {}
_资料任务表 = globals().get("_资料任务表") or {}
_资料快照 = globals().get("_资料快照") or {}
_运行状态 = globals().get("_运行状态") or {}
_阅读记录 = globals().get("_阅读记录") or {}
_待写阅读记录 = globals().get("_待写阅读记录") or {}
_阅读写入任务 = globals().get("_阅读写入任务") or {}
_阅读事件 = frozenset({
    "online", "online_state", "online_started", "online_retry_wait", "online_stopped", "heartbeat",
    "reading_book", "reading_detail", "reading_catalog", "reading_chapter", "reading_completed",
    "reward_status", "reward_collect", "reward_collected", "reward_not_collected", "reward_unavailable",
})
_奖励事件 = frozenset({"reward_status", "reward_collect", "reward_collected", "reward_not_collected", "reward_unavailable"})
_阅读错误分类 = frozenset({
    "unknown", "timeout", "network_error", "session_closed", "credential_invalid", "verification_required",
    "access_denied", "operation_unconfirmed", "business_error", "invalid_response", "empty_response",
    "response_too_large", "invalid_cookie", "empty_recommendations", "empty_catalog", "empty_content",
    "catalog_empty", "chapter_empty", "chinese_body_missing", "js_runtime_missing", "js_decode_failed",
    "reward_unavailable", "database_error", "reward_expired", "reward_not_found", "reward_rejected", "reward_login_required",
})
_服务运行 = globals().get("_服务运行", True)
_命名空间 = "stv_auth"
_状态键 = "account"
_阅读状态键 = "reading_runtime"
_资料状态键 = "account_panel"
_随机 = random.SystemRandom()
_声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


class _STV账号状态错误(ValueError):
    def __init__(self, category: str):
        提示 = {"invalid_scope": "请选择有效机器人", "account_state_invalid": "STV账号状态无效",
              "account_identity_invalid": "STV账号身份无效"}
        self.category = category if category in 提示 else "account_state_invalid"
        super().__init__(提示[self.category])


def _空状态() -> dict[str, Any]:
    return {"uid": "", "username": "", "cookies": [], "revision": "",
            "auth_status": "unknown", "online_enabled": False, "rewards_enabled": False,
            "last_event": "", "last_time": 0}


def _作用域(配置: Any) -> str:
    appid = 获取当前机器人AppID(配置)
    if not re.fullmatch(r"[0-9]{4,32}", str(appid or "")):
        raise _STV账号状态错误("invalid_scope")
    return appid


def _任务键(配置: Any) -> str:
    values = json.dumps(获取数据库配置(配置) if 已配置运行状态数据库(配置) else {}, sort_keys=True, default=str)
    return _作用域(配置) + ":" + hashlib.sha256(values.encode()).hexdigest()


def _锁(配置: Any, *, 调度: bool = False) -> asyncio.Lock:
    key = _作用域(配置) + ":scheduler" if 调度 else _任务键(配置)
    loop = asyncio.get_running_loop()
    if key not in _锁表 or _锁表[key][0] is not loop:
        _锁表[key] = (loop, asyncio.Lock())
    return _锁表[key][1]


def _读取(配置: Any) -> dict[str, Any]:
    _作用域(配置)
    if not 已配置运行状态数据库(配置):
        return _空状态()
    raw = 读取运行状态值(配置, _命名空间, _状态键, "")
    if not raw:
        return _空状态()
    try:
        state = json.loads(raw)
    except (TypeError, ValueError):
        raise _STV账号状态错误("account_state_invalid") from None
    if not isinstance(state, dict) or not isinstance(state.get("cookies"), list):
        raise _STV账号状态错误("account_state_invalid")
    if state.get("uid") and not re.fullmatch(r"[1-9][0-9]{0,31}", str(state["uid"])):
        raise _STV账号状态错误("account_identity_invalid")
    result = {**_空状态(), **{key: state[key] for key in _空状态() if key in state}}
    for field in ("online_enabled", "rewards_enabled"):
        result[field] = result[field] is True
    return result


async def _读状态(配置: Any) -> dict[str, Any]:
    state = await asyncio.to_thread(_读取, 配置)
    await _加载阅读记录(配置, state)
    return state


def _校验(检查: Callable[[], bool] | None) -> None:
    if 检查 is not None and not 检查():
        raise PermissionError("账号操作会话已结束")


async def _写状态(配置: Any, state: dict[str, Any], 检查: Callable[[], bool] | None = None) -> None:
    def write() -> None:
        _校验(检查)
        if not 已配置运行状态数据库(配置):
            raise ValueError("请先配置数据库")
        写入运行状态值(配置, _命名空间, _状态键, json.dumps(state, ensure_ascii=True, separators=(",", ":")))

    # 写线程结束前不释放账号锁，取消与重新登录不会交叉覆盖状态。
    task = asyncio.create_task(asyncio.to_thread(write))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        if not task.cancelled():
            task.exception()
        raise


def _阅读记录键(配置: Any, state: dict[str, Any]) -> tuple[str, str, str]:
    return _任务键(配置), str(state.get("uid") or ""), str(state.get("revision") or "")


def _规范阅读活动(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("event"), str) or value["event"] not in _阅读事件:
        return {}
    stamp = value.get("time")
    if type(stamp) is not int or not 0 < stamp < 10**12:
        return {}
    success = value.get("success")
    category = value.get("category")
    result = {"event": value["event"], "time": stamp,
              "success": success if type(success) is bool else None,
              "category": category if isinstance(category, str) and category in _阅读错误分类 else ""}
    if result["event"] == "reward_collected" and result["success"] is True:
        reward = _奖励日志摘要({"collected": True, "reward": value.get("reward")}).get("reward")
        if reward:
            result["reward"] = reward
    return result


def _规范阅读进度(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    due = value.get("next_read_at")
    if type(due) not in (int, float) or not 0 < due < 10**12 or not math.isfinite(due):
        return {}

    def identity(row: Any, count: int) -> bool:
        return (isinstance(row, (list, tuple)) and len(row) == count
                and isinstance(row[0], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", row[0])
                and isinstance(row[1], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", row[1])
                and (count == 2 or (isinstance(row[2], str) and 0 < len(row[2]) <= 200
                                    and not any(ord(c) < 32 or ord(c) == 127 for c in row[2]))))

    book = value.get("last_book")
    recent = value.get("recent")
    return {"next_read_at": due, "last_book": list(book) if identity(book, 2) else None,
            "recent": [list(row) for row in recent[-256:] if identity(row, 3)] if isinstance(recent, list) else []}


async def _加载阅读记录(配置: Any, state: dict[str, Any]) -> None:
    if not state.get("uid") or not 已配置运行状态数据库(配置):
        return
    key = _阅读记录键(配置, state)
    if _阅读记录.get(key, {}).get("loaded"):
        return
    lock_key = key[0] + ":reading_load"
    loop = asyncio.get_running_loop()
    if lock_key not in _锁表 or _锁表[lock_key][0] is not loop:
        _锁表[lock_key] = (loop, asyncio.Lock())
    async with _锁表[lock_key][1]:
        if _阅读记录.get(key, {}).get("loaded"):
            return
        try:
            raw = await asyncio.to_thread(读取运行状态值, 配置, _命名空间, _阅读状态键, "")
        except Exception as exc:
            logger.warning("STV阅读记录读取失败：error_type=%s", type(exc).__name__)
            # 未取得持久进度时交给原任务退避，不能空状态起步再覆盖旧记录。
            raise
        try:
            saved = json.loads(raw) if raw and len(raw) <= 256 * 1024 else {}
        except (TypeError, ValueError):
            saved = {}
        if (not isinstance(saved, dict) or saved.get("schema_version") != 1
                or saved.get("uid") != state["uid"] or saved.get("revision") != state["revision"]):
            saved = {}
        bucket = _阅读记录.get(key, {})
        memory = _规范阅读活动(bucket.get("reading"))
        stored = _规范阅读活动(saved.get("reading"))
        reading = memory if memory.get("time", 0) >= stored.get("time", 0) else stored
        old_logs = bucket.get("reward_logs")
        disk_logs = saved.get("reward_logs")
        old_logs = [_规范阅读活动(row) for row in old_logs[-100:]] if isinstance(old_logs, list) else []
        disk_logs = [_规范阅读活动(row) for row in disk_logs[-100:]] if isinstance(disk_logs, list) else []
        old_logs = [row for row in old_logs if row.get("event") in _奖励事件 and row.get("success") is not None]
        disk_logs = [row for row in disk_logs if row.get("event") in _奖励事件 and row.get("success") is not None]
        if "new_logs" in bucket:
            new_logs = [_规范阅读活动(row) for row in bucket["new_logs"][-100:]]
            logs = (disk_logs + [row for row in new_logs if row.get("event") in _奖励事件 and row.get("success") is not None])[-100:]
        else:
            logs = old_logs if old_logs and (not disk_logs or old_logs[-1]["time"] >= disk_logs[-1]["time"]) else disk_logs
        progress = _规范阅读进度(bucket.get("progress")) or _规范阅读进度(saved.get("progress"))
        # 热重载可能保留旧模块的内存桶；成功读库后立即迁入持久状态，
        # 即使挂时长已关闭且之后没有新事件，也不能在进程重启时丢失日志。
        migrate_memory = bool(bucket.get("reading") or bucket.get("reward_logs")
                              or bucket.get("progress") or bucket.get("new_logs"))
        while key not in _阅读记录 and len(_阅读记录) >= 128:
            _阅读记录.pop(next(iter(_阅读记录)))
        merged = {"reading": reading, "reward_logs": logs, "progress": progress, "loaded": True}
        _阅读记录[key] = merged
        if migrate_memory:
            _排队阅读记录(配置, state, merged)


def _写阅读记录同步(配置: Any, snapshot: dict[str, Any]) -> bool:
    snapshot = copy.deepcopy(snapshot)
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    # 运行状态列为 MySQL TEXT；保留全部100条受控日志，超预算时仅裁掉最早章节索引。
    recent = snapshot.get("progress", {}).get("recent", [])
    while len(payload.encode("utf-8")) > 60 * 1024 and recent:
        recent.pop(0)
        payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    for _ in range(3):
        account = 读取运行状态值(配置, _命名空间, _状态键, "")
        try:
            current = json.loads(account) if account else {}
        except (TypeError, ValueError):
            return True
        # 记录不能覆盖换号/退出后的状态，且账号本身始终由原账号路径维护。
        if (not isinstance(current, dict) or current.get("uid", "") != snapshot["uid"]
                or current.get("revision", "") != snapshot["revision"]):
            return True
        old = 读取运行状态值(配置, _命名空间, _阅读状态键, "")
        expected = {_状态键: account or None, _阅读状态键: old or None}
        values = {_阅读状态键: payload} if snapshot["uid"] else {}
        if 比较并更新运行状态值(配置, _命名空间, expected, values,
                              删除=None if snapshot["uid"] else [_阅读状态键]):
            return True
    return False


async def _等待阅读写入(task: Any) -> Any:
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # 不留下取消后仍可能写库的线程；等它结束后继续传播取消。
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not task.cancelled():
            task.exception()
        raise


async def _执行阅读写入(scope: str) -> None:
    try:
        while (pending := _待写阅读记录.get(scope)) is not None:
            config, snapshot = pending
            task = asyncio.create_task(asyncio.to_thread(_写阅读记录同步, config, snapshot))
            written = await _等待阅读写入(task)
            if not written:
                logger.warning("STV阅读记录保存暂缓：reason=state_changed")
                return
            if _待写阅读记录.get(scope) is pending:
                _待写阅读记录.pop(scope, None)
    except Exception as exc:
        logger.warning("STV阅读记录保存失败：error_type=%s", type(exc).__name__)
    finally:
        if _阅读写入任务.get(scope) is asyncio.current_task():
            _阅读写入任务.pop(scope, None)


def _启动阅读写入(scope: str) -> None:
    task = _阅读写入任务.get(scope)
    if scope in _待写阅读记录 and (task is None or task.done()):
        _阅读写入任务[scope] = asyncio.create_task(_执行阅读写入(scope), name="STV阅读记录保存")


def _排队阅读记录(配置: Any, state: dict[str, Any], bucket: dict[str, Any], *, 清空: bool = False) -> None:
    if not 已配置运行状态数据库(配置) or (not 清空 and not bucket.get("loaded")):
        return
    config = copy.deepcopy(dict(配置))
    config["__mantou_bot_appid__"] = _作用域(配置)
    snapshot = {"schema_version": 1, "uid": str(state.get("uid") or ""),
                "revision": str(state.get("revision") or ""),
                "reading": _规范阅读活动(bucket.get("reading")),
                "reward_logs": copy.deepcopy(bucket.get("reward_logs", [])[-100:]),
                "progress": _规范阅读进度(bucket.get("progress"))}
    scope = _任务键(配置)
    _待写阅读记录[scope] = (config, snapshot)
    _启动阅读写入(scope)


async def _冲刷阅读记录(配置: Any = None) -> None:
    scopes = [_任务键(配置)] if 配置 is not None else list(set(_待写阅读记录) | set(_阅读写入任务))
    for scope in scopes:
        _启动阅读写入(scope)
    tasks = [_阅读写入任务[scope] for scope in scopes if scope in _阅读写入任务]
    if tasks:
        await _等待阅读写入(asyncio.gather(*tasks, return_exceptions=True))


async def _清理阅读记录(配置: Any, state: dict[str, Any]) -> None:
    scope = _任务键(配置)
    for key in list(_阅读记录):
        if key[0] == scope:
            _阅读记录.pop(key, None)
    _排队阅读记录(配置, state, {}, 清空=True)
    await _冲刷阅读记录(配置)


def _空资料() -> dict[str, Any]:
    return {"profile": None, "inventory": None, "profile_updated_at": 0, "inventory_updated_at": 0}


def _资料分片数(raw: str) -> int:
    try:
        meta = json.loads(raw) if raw else {}
        count = meta.get("parts", 0)
        return count if type(count) is int and 0 <= count <= 512 else 0
    except (ValueError, TypeError, AttributeError):
        return 0


def _资料批读(配置: Any, keys: list[str]) -> dict[str, str]:
    values = 批量读取运行状态值(配置, tuple((_命名空间, key) for key in keys))
    return {key: values[(_命名空间, key)] for key in keys if (_命名空间, key) in values}


def _解读资料(values: dict[str, str], state: dict[str, Any]) -> dict[str, Any]:
    try:
        raw = values.get(_资料状态键, "")
        meta = json.loads(raw) if raw else {}
        if (meta.get("schema_version") != 1 or meta.get("uid") != state["uid"]
                or meta.get("revision") != state["revision"]):
            return _空资料()
        count = _资料分片数(raw)
        if not count:
            return _空资料()
        payload = "".join(values[f"{_资料状态键}:{i}"] for i in range(count))
        if hashlib.sha256(payload.encode()).hexdigest() != meta.get("sha256"):
            return _空资料()
        data = json.loads(payload)
        result = _空资料()
        for field in ("profile", "inventory"):
            value = data.get(field)
            stamp = data.get(field + "_updated_at")
            if not isinstance(value, dict) or type(stamp) is not int or not 0 < stamp < 10**12:
                continue
            if field == "profile" and str(value.get("user_id")) != state["uid"]:
                continue
            if field == "inventory" and not all(isinstance(value.get(name), list) for name in ("list", "act")):
                continue
            result[field] = _安全资料(value)
            result[field + "_updated_at"] = stamp
        return result
    except (ValueError, TypeError, KeyError, AttributeError):
        return _空资料()


def _读取资料同步(配置: Any, state: dict[str, Any]) -> dict[str, Any]:
    for _ in range(3):
        raw = 读取运行状态值(配置, _命名空间, _资料状态键, "")
        keys = [_状态键, _资料状态键, *[f"{_资料状态键}:{i}" for i in range(_资料分片数(raw))]]
        values = _资料批读(配置, keys)
        if values.get(_资料状态键, "") != raw:
            continue
        try:
            account = json.loads(values.get(_状态键, "{}"))
        except (ValueError, TypeError):
            return _空资料()
        if account.get("uid") != state["uid"] or account.get("revision") != state["revision"]:
            return _空资料()
        return _解读资料(values, state)
    raise STVError("snapshot_changed")


async def _加载资料快照(配置: Any, state: dict[str, Any]) -> None:
    if not state.get("uid") or not 已配置运行状态数据库(配置):
        return
    key = _阅读记录键(配置, state)
    if key in _资料快照:
        return
    data = await asyncio.to_thread(_读取资料同步, 配置, state)
    # 并发摘要不能覆盖刚完成的刷新；身份由键和数据库二次核验隔离。
    if key not in _资料快照:
        while len(_资料快照) >= 128:
            _资料快照.pop(next(iter(_资料快照)))
        _资料快照[key] = data


def _写资料同步(配置: Any, state: dict[str, Any], updates: dict[str, Any], 清空: bool = False,
                期望资料: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for _ in range(3):
        raw = 读取运行状态值(配置, _命名空间, _资料状态键, "")
        old_count = _资料分片数(raw)
        keys = [_状态键, _资料状态键, *[f"{_资料状态键}:{i}" for i in range(old_count)]]
        values = _资料批读(配置, keys)
        if values.get(_资料状态键, "") != raw:
            continue
        try:
            account = json.loads(values.get(_状态键, "{}"))
        except (ValueError, TypeError):
            return None
        if (account.get("uid", "") != state["uid"] or account.get("revision", "") != state["revision"]
                or (not 清空 and account.get("cookies") != state["cookies"])
                or (not 清空 and account.get("auth_status") == "invalid")):
            return None
        expected = {key: values.get(key) for key in keys}
        if 清空:
            if 比较并更新运行状态值(配置, _命名空间, expected, {}, 删除=keys[1:]):
                return _空资料()
            continue
        result = _解读资料(values, state)
        accepted = copy.deepcopy(updates)
        if 期望资料 is not None:
            # 查询期间突破等操作已保存新资料时，旧查询不得把同字段写回旧值。
            for field in ("profile", "inventory"):
                stamp = field + "_updated_at"
                if (field in accepted and (result.get(field) != 期望资料.get(field)
                                          or result.get(stamp) != 期望资料.get(stamp))):
                    accepted.pop(field, None)
                    accepted.pop(stamp, None)
        if not accepted:
            return result
        result.update(accepted)
        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        # MySQL TEXT 按 UTF-8 字节限额；分片与索引在同一事务提交，不截断库存。
        parts = [payload[i:i + 12000] for i in range(0, len(payload), 12000)]
        if len(parts) > 512:
            raise STVError("response_too_large")
        extra = [f"{_资料状态键}:{i}" for i in range(old_count, len(parts))]
        extra_values = _资料批读(配置, extra) if extra else {}
        expected.update({key: extra_values.get(key) for key in extra})
        meta = {"schema_version": 1, "uid": state["uid"], "revision": state["revision"],
                "parts": len(parts), "sha256": hashlib.sha256(payload.encode()).hexdigest()}
        writes = {_资料状态键: json.dumps(meta, separators=(",", ":"))}
        writes.update({f"{_资料状态键}:{i}": part for i, part in enumerate(parts)})
        removed = [f"{_资料状态键}:{i}" for i in range(len(parts), old_count)]
        if 比较并更新运行状态值(配置, _命名空间, expected, writes, 删除=removed):
            return result
    raise STVError("snapshot_changed")


async def _保存资料(配置: Any, state: dict[str, Any], updates: dict[str, Any], *, 清空: bool = False,
                  期望资料: dict[str, Any] | None = None) -> None:
    task = asyncio.create_task(asyncio.to_thread(_写资料同步, 配置, copy.deepcopy(state), updates, 清空, 期望资料))
    result = await _等待阅读写入(task)
    if result is None:
        raise STVError("snapshot_changed")
    if 清空:
        for key in list(_资料快照):
            if key[0] == _任务键(配置):
                _资料快照.pop(key, None)
    elif state.get("uid"):
        _资料快照[_阅读记录键(配置, state)] = result


def _资料锁(配置: Any) -> asyncio.Lock:
    key = _任务键(配置) + ":details"
    loop = asyncio.get_running_loop()
    if key not in _锁表 or _锁表[key][0] is not loop:
        _锁表[key] = (loop, asyncio.Lock())
    return _锁表[key][1]


async def _刷新资料(配置: Any, fields: tuple[str, ...] = ("profile", "inventory"), *,
                  检查: Callable[[], bool] | None = None, 后台: bool = False,
                  预期身份: tuple[str, str] | None = None) -> dict[str, Any]:
    async with _资料锁(配置):
        _校验(检查)
        async with _锁(配置):
            state = await _读状态(配置)
            if 预期身份 is not None and (state["uid"], state["revision"]) != 预期身份:
                raise STVError("snapshot_changed")
            if not state["uid"] or not state["cookies"] or state["auth_status"] == "invalid":
                raise STVError("credential_invalid")
        if 后台 and not _服务运行:
            return {}
        await _加载资料快照(配置, state)
        expected_details = copy.deepcopy(_资料快照.get(_阅读记录键(配置, state), _空资料()))
        methods = {"profile": "cultivation", "inventory": "inventory"}
        async with STVClient(cookies=state["cookies"], uid=state["uid"]) as client:
            tasks = [asyncio.create_task(getattr(client, methods[field])()) for field in fields]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                updated_cookies = client.export_cookies()
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
        _校验(检查)
        async with _锁(配置):
            latest = await _读状态(配置)
            if (latest["uid"] != state["uid"] or latest["revision"] != state["revision"]
                    or latest["cookies"] != state["cookies"] or (后台 and not _服务运行)):
                raise STVError("snapshot_changed")
            updates = {}
            errors = []
            for field, result in zip(fields, results):
                if isinstance(result, BaseException):
                    if not isinstance(result, Exception):
                        raise result
                    errors.append(result)
                    logger.warning("STV资料同步失败：stage=%s, error_type=%s, category=%s",
                                   field, type(result).__name__, getattr(result, "category", "unknown"))
                    if getattr(result, "category", "") == "credential_invalid":
                        await _失效(配置, latest, result)
                        raise result
                else:
                    updates[field] = _安全资料(result)
                    updates[field + "_updated_at"] = int(time.time())
            if updates:
                if latest["cookies"] != updated_cookies:
                    latest.update(cookies=updated_cookies, auth_status="valid")
                    await _写状态(配置, latest, 检查)
                await _保存资料(配置, latest, updates, 期望资料=expected_details)
            if errors and not 后台:
                raise errors[0]
            return _摘要(配置, latest)


async def _资料后台任务(配置: Any, revision: str | None) -> None:
    uid = None
    try:
        while _服务运行:
            started = time.monotonic()
            try:
                state = await _读状态(配置)
                if (not state["uid"] or not state["cookies"] or state["auth_status"] == "invalid"
                        or (revision is not None and revision != state["revision"])
                        or (uid is not None and uid != state["uid"])):
                    return
                uid, revision = state["uid"], state["revision"]
                await _加载资料快照(配置, state)
                await _刷新资料(配置, 后台=True, 预期身份=(uid, revision))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("STV资料同步失败：stage=refresh, error_type=%s, category=%s",
                               type(exc).__name__, getattr(exc, "category", "unknown"))
            await asyncio.sleep(max(1, 60 - (time.monotonic() - started)))
    finally:
        key = _任务键(配置)
        if _资料任务表.get(key) is asyncio.current_task():
            _资料任务表.pop(key, None)


def _奖励日志摘要(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    summary: dict[str, Any] = {}
    category = result.get("category")
    if result.get("collected") is False and isinstance(category, str) and category in {
        "reward_expired", "reward_not_found", "reward_rejected",
    }:
        summary["category"] = category
    code = (result.get("result") or {}).get("code") if isinstance(result.get("result"), dict) else None
    if type(code) is int or type(code) is str:
        value = str(code)
        if re.fullmatch(r"-?[0-9]{1,12}", value):
            summary["code"] = value
    reward = result.get("reward")
    if result.get("collected") is True and isinstance(reward, dict):
        name = reward.get("name")
        if (isinstance(name, str) and 0 < len(name) <= 80
                and not any(ord(char) < 32 or ord(char) == 127 for char in name)):
            from .STV协议 import _inventory_chinese_text
            if _inventory_chinese_text(name):
                item = {"name": name}
                for field in ("level", "count"):
                    value = reward.get(field)
                    if type(value) is int and 0 <= value <= 999999999999 and (field != "count" or value > 0):
                        item[field] = value
                summary["reward"] = item
    return summary


def _记录阅读活动(配置: Any, state: dict[str, Any], event: str, *,
                    success: bool | None = None, exc: Exception | None = None,
                    奖励结果: dict[str, Any] | None = None) -> None:
    if event not in _阅读事件 or not state.get("uid"):
        return
    category = ""
    if exc is not None:
        if isinstance(exc, 数据库连接错误):
            category = "database_error"
        elif isinstance(exc, TimeoutError):
            category = "timeout"
        elif isinstance(exc, ConnectionError):
            category = "network_error"
        else:
            raw = getattr(exc, "category", "unknown")
            category = raw if isinstance(raw, str) and raw in _阅读错误分类 else "unknown"
        success = False
    key = _阅读记录键(配置, state)
    if key not in _阅读记录:
        # 长期进程的历史账号记录也有上限，不把账号身份放进返回内容。
        while len(_阅读记录) >= 128:
            _阅读记录.pop(next(iter(_阅读记录)))
        _阅读记录[key] = {"reading": {}, "reward_logs": [], "new_logs": []}
    reward = _奖励日志摘要(奖励结果)
    if exc is None and event == "reward_not_collected" and success is False:
        category = reward.get("category", "")
    record = {"event": event, "time": int(time.time()), "success": success, "category": category}
    if event == "reward_collected" and success is True and "reward" in reward:
        record["reward"] = reward["reward"]
    bucket = _阅读记录[key]
    bucket["reading"] = record
    if event in _奖励事件 and success is not None:
        bucket["reward_logs"] = [*bucket["reward_logs"], record][-100:]
        if not bucket.get("loaded"):
            bucket["new_logs"] = [*bucket.get("new_logs", []), record][-100:]
    _排队阅读记录(配置, state, bucket)


def _阅读摘要(配置: Any, state: dict[str, Any]) -> dict[str, Any]:
    bucket = _阅读记录.get(_阅读记录键(配置, state), {})
    return {
        "reading": copy.deepcopy(bucket.get("reading") or {"event": "", "time": 0, "success": None, "category": ""}),
        "reward_logs": copy.deepcopy(bucket.get("reward_logs", [])),
    }


def _日志(配置: Any, state: dict[str, Any], event: str, exc: Exception | None = None, *,
          记录活动: bool = True, 奖励结果: dict[str, Any] | None = None) -> None:
    if 记录活动:
        _记录阅读活动(配置, state, event, success=exc is None and event != "reward_not_collected",
                  exc=exc, 奖励结果=奖励结果)
    now = int(time.time())
    _运行状态[_任务键(配置)] = {"last_event": event, "last_time": now}
    if exc is None:
        message = "STV账号任务：appid=%s, uid=%s, event=%s"
        values = [_作用域(配置), state.get("uid") or "none", event]
        if event in {"reward_collected", "reward_not_collected"}:
            result = _奖励日志摘要(奖励结果)
            if event == "reward_not_collected":
                message += ", category=%s, code=%s"
                values.extend((result.get("category", "unknown"), result.get("code", "none")))
            elif "reward" in result:
                message += ", 领取物品=%s"
                values.append(result["reward"]["name"])
                for field, label in (("level", "等级"), ("count", "数量")):
                    if field in result["reward"]:
                        message += ", " + label + "=%s"
                        values.append(result["reward"][field])
        logger.info(message, *values)
    elif getattr(exc, "category", "") == "breakthrough_unavailable":
        logger.info("STV账号任务未提交：appid=%s, uid=%s, stage=%s, reason=breakthrough_unavailable",
                    _作用域(配置), state.get("uid") or "none", event)
    else:
        message = "STV账号任务失败：appid=%s, uid=%s, stage=%s, error_type=%s, category=%s, http_status=%s, code=%s"
        values = [_作用域(配置), state.get("uid") or "none", event, type(exc).__name__,
                  exc.reason if isinstance(exc, 数据库连接错误) else getattr(exc, "category", "unknown"),
                  getattr(exc, "http_status", None),
                  exc.mysql_code if isinstance(exc, 数据库连接错误) else getattr(exc, "code", None)]
        if event == "cultivation":
            stage = getattr(exc, "request_stage", "unknown")
            stage = stage if isinstance(stage, str) and stage in {"account_info", "cultivation_page"} else "unknown"
            attempts = getattr(exc, "attempts", None)
            attempts = attempts if type(attempts) is int and attempts in {1, 2} else "none"
            kind = getattr(exc, "timeout_kind", "none")
            kind = kind if isinstance(kind, str) and kind in {
                "connection_timeout", "read_timeout", "total_timeout", "attempt_timeout", "none",
            } else "unknown"
            message += ", request_stage=%s, attempts=%s, timeout_kind=%s"
            values.extend((stage, attempts, kind))
        logger.warning(message, *values)


def _摘要(配置: Any, state: dict[str, Any]) -> dict[str, Any]:
    task = _任务表.get(_任务键(配置))
    return {key: state[key] for key in ("uid", "username", "auth_status", "online_enabled", "rewards_enabled", "last_event", "last_time")} | {
        "logged_in": bool(state["uid"] and state["cookies"] and state["auth_status"] != "invalid"),
        "running": bool(state["online_enabled"] and state["auth_status"] != "invalid" and task and not task.done()),
        **_运行状态.get(_任务键(配置), {}),
        **_阅读摘要(配置, state),
        "details": copy.deepcopy(_资料快照.get(_阅读记录键(配置, state), _空资料())),
    }


async def 读取STV账号摘要(配置: Any) -> dict[str, Any]:
    # 只读取已持久化的整行快照，不等待后台网络或消耗操作持有的账号锁。
    state = await _读状态(配置)
    await _加载资料快照(配置, state)
    return _摘要(配置, state)


async def _失效(配置: Any, state: dict[str, Any], exc: Exception) -> None:
    if getattr(exc, "category", "") == "credential_invalid":
        state.update(auth_status="invalid", online_enabled=False, rewards_enabled=False,
                     last_event="credential_invalid", last_time=int(time.time()))
        await _写状态(配置, state)


async def 登录STV账号(配置: Any, username: str, password: str, *, 注册: bool = False,
                     重复密码: str = "", 提交前校验: Callable[[], bool] | None = None) -> dict[str, Any]:
    async with _锁(配置):
        _校验(提交前校验)
        if not 已配置运行状态数据库(配置):
            raise ValueError("请先配置数据库")
        old = await _读状态(配置)
        _校验(提交前校验)
        stage = "register" if 注册 else "login"
        try:
            async with STVClient() as client:
                client.mutation_guard = 提交前校验
                if 注册:
                    registered = await client.register(username, password, 重复密码)
                    if not registered.get("logged_in"):
                        _日志(配置, old, "registered_login_required")
                        return {**_摘要(配置, old), "registered": True, "registration_logged_in": False}
                    info = registered["info"]
                else:
                    info = await client.login(username, password)
                _校验(提交前校验)
                state = {**_空状态(), "uid": str(info["id"]), "username": username.strip(),
                         "cookies": client.export_cookies(), "revision": uuid.uuid4().hex,
                         "auth_status": "valid", "last_event": stage, "last_time": int(time.time())}
                await _写状态(配置, state, 提交前校验)
                await _清理阅读记录(配置, state)
                await _保存资料(配置, state, {}, 清空=True)
                _日志(配置, state, stage)
        except Exception as exc:
            _日志(配置, old, stage, exc)
            raise
    await _同步任务(配置)
    return {**await 读取STV账号摘要(配置), **({"registered": True, "registration_logged_in": True} if 注册 else {})}


async def 删除STV账号(配置: Any, *, 提交前校验: Callable[[], bool] | None = None) -> dict[str, Any]:
    _校验(提交前校验)
    await _取消作用域任务(配置)
    async with _锁(配置):
        state = await _读状态(配置)
        await _写状态(配置, _空状态(), 提交前校验)
        await _清理阅读记录(配置, _空状态())
        await _保存资料(配置, _空状态(), {}, 清空=True)
        _日志(配置, state, "logout")
    await _同步任务(配置)
    return await 读取STV账号摘要(配置)


async def 设置STV开关(配置: Any, 名称: str, 启用: bool, *,
                    提交前校验: Callable[[], bool] | None = None) -> dict[str, Any]:
    if 名称 not in {"online", "rewards"} or type(启用) is not bool:
        raise ValueError("开关参数无效")
    _校验(提交前校验)
    if not 启用:
        await _取消作用域任务(配置)
    async with _锁(配置):
        state = await _读状态(配置)
        if 启用 and (not state["uid"] or not state["cookies"] or state["auth_status"] == "invalid"):
            raise ValueError("请先登录STV账号")
        state[名称 + "_enabled"] = 启用
        await _写状态(配置, state, 提交前校验)
        _日志(配置, state, 名称 + ("_enabled" if 启用 else "_disabled"))
    await _同步任务(配置)
    return await 读取STV账号摘要(配置)


def _安全资料(value: Any) -> Any:
    """账号面板只返回业务展示字段，不透传远程原始对象。"""
    if isinstance(value, dict):
        allowed = {"user_id", "username", "realm", "cultivation", "foundation", "speed", "status", "training_minutes",
                   "read_chapters", "attributes", "breakthrough_available", "current", "maximum", "minimum", "next",
                   "per_minute", "basis", "text", "max", "min", "value",
                   "success", "used", "item_id", "type", "before", "after", "refresh_error", "list", "act",
                   "name", "info", "level", "i", "n", "t", "ac", "l", "d", "id", "title", "amount", "count", "group_key"}
        result = {key: _安全资料(item) for key, item in value.items() if key in allowed}
        if "icon" in value:
            from .STV协议 import _inventory_icon_url
            result["icon"] = _inventory_icon_url(value["icon"])
        if isinstance(value.get("attributes"), dict):
            result["attributes"] = {_文本(key)[:80]: _安全资料(item)
                                    for key, item in list(value["attributes"].items())[:100]}
        return result
    if isinstance(value, list):
        return [_安全资料(item) for item in value]
    if isinstance(value, str):
        text = html.unescape(re.sub(r"<[^>]*>", "", value))
        return re.sub(r"https?://\S+", "", text)[:4000]
    if value is None or type(value) in (int, float, bool):
        return value
    return None


async def 执行STV账号操作(配置: Any, 操作: str, 物品ID: str = "", *,
                        提交前校验: Callable[[], bool] | None = None,
                        附带摘要: bool = False) -> dict[str, Any]:
    methods = {"refresh": "account_info", "cultivation": "cultivation", "breakthrough": "breakthrough",
               "inventory": "inventory", "item": "inventory_item", "use": "use_item"}
    if 操作 not in methods:
        raise ValueError("账号操作无效")
    if 操作 in {"cultivation", "inventory"}:
        field = "profile" if 操作 == "cultivation" else "inventory"
        summary = await _刷新资料(配置, (field,), 检查=提交前校验)
        result = summary["details"][field]
        return {"summary": summary, "result": result} if 附带摘要 else result
    async with _锁(配置):
        _校验(提交前校验)
        state = await _读状态(配置)
        _校验(提交前校验)
        if not state["uid"] or not state["cookies"] or state["auth_status"] == "invalid":
            raise ValueError("请先登录STV账号")
        try:
            async with STVClient(cookies=state["cookies"], uid=state["uid"]) as client:
                client.mutation_guard = 提交前校验
                method = getattr(client, methods[操作])
                result = await method(物品ID) if 操作 in {"item", "use"} else await method()
                _校验(提交前校验)
                state.update(cookies=client.export_cookies(), auth_status="valid",
                             last_event=操作, last_time=int(time.time()))
                await _写状态(配置, state, 提交前校验)
                _日志(配置, state, 操作)
                if 操作 == "breakthrough" and isinstance(result.get("after"), dict):
                    await _保存资料(配置, state, {"profile": _安全资料(result["after"]),
                                                "profile_updated_at": int(time.time())})
                await _加载资料快照(配置, state)
                summary = _摘要(配置, state)
                result = summary if 操作 == "refresh" else _安全资料(result)
                return {"summary": summary, "result": result} if 附带摘要 else result
        except Exception as exc:
            await _失效(配置, state, exc)
            _日志(配置, state, 操作, exc)
            raise


async def _同步任务(配置: Any) -> None:
    async with _锁(配置, 调度=True):
        await _替换任务(配置)


async def _替换任务(配置: Any) -> None:
    key = _任务键(配置)
    old_tasks = []
    for table in (_任务表, _资料任务表):
        for old_key in list(table):
            if old_key.startswith(_作用域(配置) + ":") and old_key != key:
                old_tasks.append(table.pop(old_key))
    for task in old_tasks:
        if task is not asyncio.current_task() and not task.done():
            task.cancel()
    if old_tasks:
        await asyncio.gather(*old_tasks, return_exceptions=True)
    if not _服务运行:
        return
    async with _锁(配置):
        try:
            state = await _读状态(配置)
        except Exception as exc:
            if not _可恢复后台错误(exc):
                raise
            state = None
    identity = (state["uid"], state["revision"]) if state else None
    snapshot = copy.deepcopy(dict(配置))
    snapshot["__mantou_bot_appid__"] = _作用域(配置)
    logged_in = state is None or bool(state["uid"] and state["cookies"] and state["auth_status"] != "invalid")
    for table, enabled, worker, name in (
        (_任务表, logged_in and (state is None or state["online_enabled"]), _后台任务, "STV在线任务:"),
        (_资料任务表, logged_in, _资料后台任务, "STV资料同步:"),
    ):
        task = table.get(key)
        if (enabled and task and not task.done() and
                (state is None or getattr(task, "_stv_identity", None) == identity)):
            continue
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if _服务运行 and enabled:
            task = asyncio.create_task(worker(snapshot, state["revision"] if state else None),
                                       name=name + _作用域(配置))
            task._stv_identity = identity
            table[key] = task
        elif table.get(key) is task:
            table.pop(key, None)


async def _取消作用域任务(配置: Any) -> None:
    async with _锁(配置, 调度=True):
        key = _任务键(配置)
        task = _任务表.pop(key, None)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def 启动STV后台任务(配置: Any = None) -> None:
    global _服务运行
    _服务运行 = True
    # 先恢复服务生命周期；无配置时不借用调用方的机器人作用域。
    if 配置 is None:
        return
    # 生命周期尚未枚举到机器人时没有账号作用域，不能恢复任务或借用其他机器人。
    if not 获取当前机器人AppID(配置):
        return
    await _同步任务(配置)


async def 停止STV后台任务() -> None:
    global _服务运行
    _服务运行 = False
    tasks = list(_任务表.values()) + list(_资料任务表.values())
    _任务表.clear()
    _资料任务表.clear()
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await _冲刷阅读记录()
    await _close_idle_connector()


def _可恢复后台错误(exc: Exception) -> bool:
    if isinstance(exc, 数据库连接错误):
        return exc.reason in {"dns", "timeout", "network", "server_busy"} or exc.mysql_code in {2006, 2013}
    return isinstance(exc, (TimeoutError, ConnectionError)) or (
        isinstance(exc, STVError) and exc.category in {"timeout", "network_error", "session_closed"}
    )


async def _后台任务(配置: Any, revision: str | None) -> None:
    state = _空状态()
    uid = None
    failures = 0
    try:
        while _服务运行:
            entered = False
            try:
                state = await _读状态(配置)
                if (not _服务运行 or not state["online_enabled"] or not state["uid"] or not state["cookies"]
                        or state["auth_status"] == "invalid"
                        or (revision is not None and state["revision"] != revision)
                        or (uid is not None and state["uid"] != uid)):
                    return
                revision, uid = state["revision"], state["uid"]
                entered = True
                failure = await _执行在线任务(配置, revision, uid)
                if failure is None:
                    return
                failed_state, exc = failure
                if failed_state["revision"] == revision and failed_state["uid"] == uid:
                    state = failed_state
                raise exc
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not entered:
                    _日志(配置, state, "online_state", exc)
                if _可恢复后台错误(exc):
                    failures += 1
                    _日志(配置, state, "online_retry_wait")
                    await asyncio.sleep(min(5 * 2 ** min(failures - 1, 6), 300))
                    # 每次恢复都重新校验固定账号代次、身份和最新开关；不保存旧会话奖励。
                    continue
                # 无法恢复时同步关闭当前账号的挂时长，避免开关亮着但任务已消失。
                while _服务运行:
                    try:
                        async with _锁(配置):
                            latest = await _读状态(配置)
                            if (_服务运行 and revision is not None and latest["revision"] == revision
                                    and latest["uid"] == uid and latest["online_enabled"]):
                                if latest["cookies"] != state["cookies"]:
                                    break
                                latest.update(online_enabled=False, last_event="online_error", last_time=int(time.time()))
                                await _写状态(配置, latest)
                        return
                    except Exception as update_exc:
                        _日志(配置, state, "online_state", update_exc)
                        if not _可恢复后台错误(update_exc):
                            return
                        # 只恢复关闭状态的读写，不因同步失败重跑在线或领奖操作。
                        failures += 1
                        await asyncio.sleep(min(5 * 2 ** min(failures - 1, 6), 300))
    except asyncio.CancelledError:
        _日志(配置, state, "online_stopped")
        raise
    finally:
        key = _任务键(配置)
        if _任务表.get(key) is asyncio.current_task():
            _任务表.pop(key, None)


async def _执行在线任务(配置: Any, revision: str, uid: str) -> tuple[dict[str, Any], Exception] | None:
    state = _空状态()
    stage = "online"
    reward_pending = False
    reward_result = None
    reward_details = None
    try:
        state = await _读状态(配置)

        def current(row: dict[str, Any]) -> bool:
            return (_服务运行 and row["revision"] == revision and row["uid"] == uid
                    and row["online_enabled"] and row["auth_status"] != "invalid")

        progress = _规范阅读进度(_阅读记录.get(_阅读记录键(配置, state), {}).get("progress"))
        heartbeat_due = time.monotonic()
        reading_due = heartbeat_due + max(0, min(300, progress.get("next_read_at", 0) - time.time()))
        reward_due = float("inf")
        reward_cid = ""
        reward_needs_clear = False
        recent: list[tuple[str, str, str]] = [tuple(row) for row in progress.get("recent", [])]
        last_book = tuple(progress["last_book"]) if progress.get("last_book") else None
        reading_stage = "book"
        chapter: dict[str, Any] = {}
        failures = 0
        if not current(state):
            return
        _日志(配置, state, "online_started")
        while True:
            async with _锁(配置):
                state = await _读状态(配置)
                if not current(state):
                    return
                cookies = copy.deepcopy(state["cookies"])
            async with STVClient(cookies=cookies, uid=uid) as client:
                # 前台刷新可能更新 Cookie；旧会话不能覆盖它或据其失败误标失效。
                # 发生变化时关闭旧会话，按最新持久快照重建，奖励通知不跨会话复用。
                reward_cid = ""
                reward_due = float("inf")
                reward_attempted = False
                while True:
                    async with _锁(配置):
                        state = await _读状态(配置)
                        if not current(state):
                            return
                        if state["cookies"] != cookies:
                            break
                    now = time.monotonic()
                    try:
                        if now >= heartbeat_due:
                            stage = "heartbeat"
                            _记录阅读活动(配置, state, stage)
                            await client.heartbeat()
                            heartbeat_due = time.monotonic() + 120
                            async with _锁(配置):
                                state = await _读状态(配置)
                                if not current(state):
                                    return
                                if state["cookies"] != cookies:
                                    break
                                cookies = client.export_cookies()
                                state.update(cookies=cookies, auth_status="valid")
                                await _写状态(配置, state)
                                _日志(配置, state, "heartbeat")
                        if reward_cid and state["rewards_enabled"] and now >= reward_due:
                            stage = "reward_status"
                            _记录阅读活动(配置, state, stage)
                            final_check = now >= reading_due
                            reward_due = float("inf") if final_check else reading_due
                            offered = await client.reward_status()
                            async with _锁(配置):
                                state = await _读状态(配置)
                                if not current(state):
                                    return
                                if state["cookies"] != cookies:
                                    break
                                if not offered:
                                    reward_needs_clear = False
                                if offered and not reward_needs_clear and state["rewards_enabled"]:
                                    stage = "reward_collect"
                                    reward_result = None
                                    reward_details = None
                                    # 消耗仍串行；领取前持久关闭，取消或未知结果不重放。
                                    state["rewards_enabled"] = False
                                    await _写状态(配置, state)
                                    _记录阅读活动(配置, state, stage)
                                    reward_pending, reward_result = True, None
                                    reward_attempted = True
                                    reward_details = await client.collect_reward(reward_cid)
                                    reward_result = reward_details.get("collected") is True
                                    # 无通知 ID；拒绝后的连续可领标记不可当作新通知。
                                    reward_needs_clear = not reward_result
                                    # 领奖结果已经明确，后续状态保存失败也不能改写成领取失败。
                                    _日志(配置, state, "reward_collected" if reward_result else "reward_not_collected",
                                        奖励结果=reward_details)
                                    reward_pending = False
                                    await _冲刷阅读记录(配置)
                                    reward_cid = ""
                                    state["rewards_enabled"] = True
                                    await _写状态(配置, state)
                                elif final_check:
                                    reward_cid = ""
                                    if not offered and state["rewards_enabled"]:
                                        _日志(配置, state, "reward_unavailable")
                        if now >= reading_due:
                            stage = "reading_" + reading_stage
                            _记录阅读活动(配置, state, stage)
                            reading_due = time.monotonic() + 2
                            if reading_stage == "book":
                                reward_cid = ""
                                books = await client.recommended()
                                choices = [row for row in books if (str(row["host"]), str(row["id"])) != last_book]
                                if not choices:
                                    choices = books
                                if not choices:
                                    raise STVError("empty_recommendations")
                                book = _随机.choice(choices)
                            elif reading_stage == "detail":
                                await client.detail(*last_book)
                            elif reading_stage == "catalog":
                                catalog = await client.catalog(*last_book)
                                choices = [row for row in catalog if (*last_book, str(row["cid"])) not in recent]
                                if not choices:
                                    raise STVError("empty_catalog")
                                next_chapter = _随机.choice(choices)
                            else:
                                body = await client.chapter(*last_book, str(chapter["cid"]), reward_reading=True)
                                chars = len(re.sub(r"\s", "", body["content"]))
                                if not chars:
                                    raise STVError("empty_content")
                            # 只接受仍属于当前账号/开关的结果；网络期间不占账号锁。
                            async with _锁(配置):
                                state = await _读状态(配置)
                                if not current(state):
                                    return
                                if state["cookies"] != cookies:
                                    break
                                if reading_stage == "book":
                                    last_book = (str(book["host"]), str(book["id"]))
                                    reading_stage = "detail"
                                elif reading_stage == "detail":
                                    reading_stage = "catalog"
                                elif reading_stage == "catalog":
                                    chapter = next_chapter
                                    reading_stage = "chapter"
                                else:
                                    recent = [*recent, (*last_book, str(chapter["cid"]))][-256:]
                                    delay = _随机.randint(180, 300)
                                    chapter_ready_at = time.monotonic()
                                    reading_due = chapter_ready_at + delay
                                    _阅读记录[_阅读记录键(配置, state)]["progress"] = {
                                        "next_read_at": time.time() + delay,
                                        "last_book": list(last_book), "recent": [list(row) for row in recent],
                                    }
                                    if body.get("reward_token_count", 0) >= 400 and state["rewards_enabled"]:
                                        reward_cid = str(chapter["cid"])
                                        reward_attempted = False
                                        reward_due = chapter_ready_at + 60
                                    reading_stage = "book"
                                    _日志(配置, state, "reading_completed")
                                    await _冲刷阅读记录(配置)
                        failures = 0
                    except Exception as exc:
                        async with _锁(配置):
                            state = await _读状态(配置)
                            if not current(state):
                                return
                            if state["cookies"] != cookies:
                                break
                            if stage == "reward_collect" and reward_result is not None:
                                _日志(配置, state, stage, exc, 记录活动=False)
                            else:
                                _日志(配置, state, stage, exc)
                            reward_pending = False
                            if getattr(exc, "category", "") == "credential_invalid":
                                await _失效(配置, state, exc)
                                return
                            if stage == "reward_collect":
                                # 拒绝、异常和未确认结果需管理员核实后再开启。
                                state["rewards_enabled"] = False
                                await _写状态(配置, state)
                                reward_cid = ""
                            if getattr(exc, "category", "") in {"verification_required", "access_denied"}:
                                state["online_enabled"] = False
                                await _写状态(配置, state)
                                return
                        failures += 1
                        delay = min(120 * 2 ** min(failures - 1, 3), 600)
                        if stage == "heartbeat":
                            heartbeat_due = time.monotonic() + delay
                        elif stage not in {"reward_status", "reward_collect"}:
                            reading_due = time.monotonic() + delay
                            reading_stage = "book"
                    deadlines = [heartbeat_due, reading_due]
                    if reward_cid and state["rewards_enabled"]:
                        deadlines.append(reward_due)
                    await asyncio.sleep(max(0.1, min(deadlines) - time.monotonic()))
                if reward_cid and not reward_attempted and state["rewards_enabled"]:
                    logger.info("STV奖励未提交：appid=%s, uid=%s, reason=session_changed_before_submit",
                                _作用域(配置), uid)
    except asyncio.CancelledError:
        if reward_pending:
            if reward_result is None:
                _日志(配置, state, "reward_collect", STVError("operation_unconfirmed"))
            else:
                _日志(配置, state, "reward_collected" if reward_result else "reward_not_collected",
                    奖励结果=reward_details)
        raise
    except Exception as exc:
        if stage == "reward_collect" and reward_result is not None:
            _日志(配置, state, stage, exc, 记录活动=False)
        else:
            _日志(配置, state, stage, exc)
        return state, exc


def 提取STV书籍编号(source: Any) -> str:
    if not isinstance(source, str):
        return ""
    text = html.unescape(source).replace("\\/", "/").strip()
    for _ in range(2):
        text = unquote(text)
    if re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", text):
        return text
    try:
        parts = urlsplit(text)
        if parts.scheme not in {"http", "https"} or (parts.hostname or "").lower() not in {"sangtacviet.com", "www.sangtacviet.com"}:
            return ""
        query = parse_qs(parts.query)
        host = (query.get("host") or query.get("h") or [""])[0]
        book_id = (query.get("bookid") or query.get("hid") or [""])[0]
        # 官方书籍页面 /truyen/<host>/<语言>/<bookid>/。
        path = re.fullmatch(r"/truyen/([A-Za-z0-9_-]+)/[A-Za-z0-9_-]+/([A-Za-z0-9_-]+)(?:/.*)?", parts.path)
        if path:
            host, book_id = path.groups()
        result = str(host) + "/" + str(book_id)
        return result if re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", result) else ""
    except ValueError:
        return ""


def 构造STV链接(book_id: str) -> str:
    identity = 提取STV书籍编号(book_id)
    if not identity:
        return ""
    host, number = identity.split("/", 1)
    return f"https://sangtacviet.com/truyen/{host}/1/{number}/"


def 获取STV书源名称(identity: Any) -> str:
    """只显示官方书源标识已核实的中文站名，不根据未知标识猜测。"""
    book_id = 提取STV书籍编号(identity)
    host = book_id.partition("/")[0] if book_id else ""
    names = {
        "qidian": "起点中文网", "idejian": "得间小说", "qimao": "七猫小说",
        "fanqie": "番茄小说", "jjwxc": "晋江文学城", "sfacg": "菠萝包轻小说",
        "kujiang": "酷匠网", "tadu": "塔读小说", "zongheng": "纵横中文网",
        "69shuorg": "69书吧", "acqq": "腾讯动漫", "ciweimao": "刺猬猫阅读",
        "faloo": "飞卢小说网", "linovel": "轻之文库", "kanman": "看漫网",
        "ptwxz": "飘天文学", "quanben5": "全本小说网", "biquge5200": "新笔趣阁5200",
    }
    return names.get(host, "未知书源")


def _文本(value: Any) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", "", html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))).strip()


def _元数据(row: dict[str, Any], identity: str) -> dict[str, Any]:
    status_value = row.get("status")
    status_raw = _文本(status_value).casefold()
    status = "完结" if status_raw in {"hoàn thành", "hoàn tất", "已完结", "完结", "completed"} else (
        "连载" if status_raw in {"còn tiếp", "đang ra", "连载", "连载中", "ongoing"} else
        "暂停" if status_raw == "tạm ngưng" else "未知")
    if isinstance(status_value, (int, str)) and not isinstance(status_value, bool):
        status = {"0": "未知", "1": "连载", "2": "暂停", "3": "完结"}.get(str(status_value).strip(), status)
    count = row.get("word_count")
    if isinstance(count, bool) or not re.fullmatch(r"[1-9][0-9]*", str(count or "")):
        count = 0
    return {"book_id": identity, "title": _文本(row.get("name") or row.get("hname") or row.get("tname")),
            "author": _文本(row.get("author")) or "未知", "status": status,
            "word_count": int(count), "intro": _文本(row.get("info")), "url": 构造STV链接(identity)}


async def 搜索STV小说(keyword: str, limit: int = 20) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    known: set[str] = set()
    async with STVClient() as client:
        for page in range(min(3, max(1, (limit + 9) // 10))):
            rows = await client.search(keyword, page=page)
            for row in rows:
                identity = 提取STV书籍编号(str(row.get("host") or "") + "/" + str(row.get("id") or ""))
                if not identity or identity in known or str(row.get("host") or "") == "cocomanga":
                    continue
                metadata = _元数据(row, identity)
                if metadata["title"]:
                    result.append(metadata)
                    known.add(identity)
            if not rows or len(result) >= limit:
                break
    return result[:limit]


def 获取STV小说回复流(event: Any, command: str, config: Any = None) -> AsyncIterator[Any] | None:
    text = str(command or "").strip()
    match = re.fullmatch(r"STV(?:小说)?\s+([A-Za-z0-9_-]+/[A-Za-z0-9_-]+)", text, re.I)
    if match:
        return 生成STV下载回复流(event, match.group(1), config)
    sources: list[str] = []
    _收集来源(command, sources, set())
    _收集来源(event, sources, set())
    for value in sources:
        for found in re.finditer(r"https?://(?:www\.)?sangtacviet\.com/[^\s<>\"']+", html.unescape(value).replace("\\/", "/"), re.I):
            source = found.group(0).rstrip("，。；;]}>）)")
            if 提取STV书籍编号(source):
                return 生成STV下载回复流(event, source, config)
    return None


def _收集来源(value: Any, result: list[str], seen: set[int], depth: int = 0) -> None:
    if depth > 7 or value is None:
        return
    if isinstance(value, str):
        result.append(value)
        return
    if id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, dict):
        for name in ("url", "jump_url", "qqdocurl", "content", "data", "raw_message", "message", "message_obj", "json"):
            _收集来源(value.get(name), result, seen, depth + 1)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _收集来源(item, result, seen, depth + 1)
    else:
        for name in ("message_str", "raw_message", "message_obj", "message", "data", "url", "content"):
            _收集来源(getattr(value, name, None), result, seen, depth + 1)


def _写缓存(filename: str, content: bytes) -> Path:
    directory = 文件缓存工具.小说缓存目录
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        path = directory / (filename if index == 0 else f"{Path(filename).stem}_{index}.txt")
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            continue
        文件缓存工具.标记小说缓存正在使用(path)
        return path
    raise STVError("cache_name_conflict")


async def _发送(event: Any, filename: str, content: bytes, config: Any, detail: dict[str, Any]) -> dict[str, Any]:
    from 功能文件.管理功能.网盘功能 import 小说网盘

    path = _写缓存(filename, content)
    cancelled = False
    try:
        result = await 小说网盘.上传小说并获取分享链接(config, path, filename)
        if not result.get("success"):
            return {"sent": False}
        return await 小说网盘.发送小说下载结果(event, detail["title"], detail["author"], result)
    except asyncio.CancelledError:
        cancelled = True
        raise
    finally:
        if cancelled:
            文件缓存工具.解除小说缓存占用(path)
        else:
            文件缓存工具.删除小说缓存文件(path)


async def 生成STV下载回复流(event: Any, source: str, config: Any = None) -> AsyncIterator[Any]:
    identity = 提取STV书籍编号(source)
    if not identity:
        yield "下载失败 请重试"
        return
    stage = "metadata"
    state = _空状态()
    try:
        state = await _读状态(config) if 获取当前机器人AppID(config) else _空状态()
        if state["auth_status"] == "invalid":
            state = _空状态()
        host, number = identity.split("/", 1)
        async with STVClient(cookies=state["cookies"], uid=state["uid"], chapter_download=True) as client:
            detail = _元数据(await client.detail(host, number), identity)
            if not detail["title"]:
                raise STVError("invalid_detail")
            chapters = await client.catalog(host, number)
            if not chapters:
                raise STVError("empty_catalog")
            logger.info("STV小说开始下载：书籍编号=%s, 章节数=%s, 并发数=%s",
                        identity, len(chapters), min(STV_DOWNLOAD_CONCURRENCY, len(chapters)))
            yield "\n".join([f"书名：{detail['title']}", f"作者：{detail['author']}", f"状态：{detail['status']}",
                              f"章节：{len(chapters)} 章", f"字数：{格式化小说字数(detail['word_count'])}", "", "正在下载中请稍等....."])
            stage = "chapters"
            contents = []
            selected = []
            failures = 0
            # 每批100章复用同一会话和密钥，批内并发；结果仍按原目录顺序合并。
            for offset in range(0, len(chapters), STV_DOWNLOAD_CONCURRENCY):
                batch = chapters[offset:offset + STV_DOWNLOAD_CONCURRENCY]
                bodies = await client.chapter_batch(host, number, [str(chapter["cid"]) for chapter in batch])
                for chapter, body in zip(batch, bodies):
                    if body is None:
                        failures += 1
                        continue
                    selected.append(chapter)
                    contents.append(body["content"])
            if not contents:
                raise STVError("empty_content")
        if failures:
            logger.warning("STV小说章节下载汇总：book_id=%s, success=%s, skipped=%s, category=unavailable_chapters", identity, len(contents), failures)
        lines = [_声明, "", f"名称：{detail['title']}", f"作者：{detail['author']}", f"状态：{detail['status']}",
                 f"字数：{格式化小说字数(detail['word_count'])}", f"书籍ID：{identity}", f"章节数：{len(selected)}", ""]
        if detail["intro"]:
            lines.extend(["简介：", detail["intro"], ""])
        for chapter, body in zip(selected, contents):
            lines.extend([chapter["title"], "", 去除章节正文重复标题(chapter["title"], body), ""])
        safe = lambda value: re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", value).strip(" .")[:80] or "STV小说"
        filename = f"[{detail['status']}]书名：{safe(detail['title'])} 作者：{safe(detail['author'])}.txt"
        content = "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n").encode("utf-8")
        logger.info("STV小说章节下载完成：书籍编号=%s, 成功=%s, 总数=%s, 文件大小=%s", identity, len(contents), len(chapters), len(content))
        stage = "upload_send"
        result = await _发送(event, filename, content, config, detail)
        if result.get("sent"):
            return
        if result.get("fallback_text"):
            yield str(result["fallback_text"])
            return
        raise STVError("upload_or_delivery_failed")
    except Exception as exc:
        if getattr(exc, "category", "") == "credential_invalid" and state["uid"]:
            async with _锁(config):
                current = await _读状态(config)
                if current["revision"] == state["revision"]:
                    await _失效(config, current, exc)
        logger.warning("STV小说处理失败：stage=%s, book_id=%s, error_type=%s, category=%s, http_status=%s, code=%s",
                       stage, identity, type(exc).__name__, getattr(exc, "category", "unknown"),
                       getattr(exc, "http_status", None), getattr(exc, "code", None))
        if stage == "upload_send":
            yield "文件发送失败，请稍后再试"
        elif getattr(exc, "category", "") == "rate_limited":
            yield "请求较多，请稍后再试"
        else:
            yield "下载失败 请重试"
