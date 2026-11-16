"""Sáng Tác Việt 小说、独立账号和可关闭的在线/奖励任务。"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import html
import json
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

from .STV协议 import STVClient, STVError, _close_idle_connector
from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    已配置运行状态数据库, 读取运行状态值, 写入运行状态值, 获取数据库配置, 数据库连接错误,
)
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题, 格式化小说字数

_锁表 = globals().get("_锁表") or {}
_任务表 = globals().get("_任务表") or {}
_运行状态 = globals().get("_运行状态") or {}
_阅读记录 = globals().get("_阅读记录") or {}
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
    "reward_unavailable", "database_error",
})
_服务运行 = globals().get("_服务运行", True)
_命名空间 = "stv_auth"
_状态键 = "account"
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
    return await asyncio.to_thread(_读取, 配置)


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


def _清理阅读记录(配置: Any) -> None:
    scope = _任务键(配置)
    for key in list(_阅读记录):
        if key[0] == scope:
            _阅读记录.pop(key, None)


def _记录阅读活动(配置: Any, state: dict[str, Any], event: str, *,
                    success: bool | None = None, exc: Exception | None = None) -> None:
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
        _阅读记录[key] = {"reading": {}, "reward_logs": []}
    record = {"event": event, "time": int(time.time()), "success": success, "category": category}
    bucket = _阅读记录[key]
    bucket["reading"] = record
    if event in _奖励事件 and success is not None:
        bucket["reward_logs"] = [*bucket["reward_logs"], record][-100:]


def _阅读摘要(配置: Any, state: dict[str, Any]) -> dict[str, Any]:
    bucket = _阅读记录.get(_阅读记录键(配置, state), {})
    return {
        "reading": dict(bucket.get("reading") or {"event": "", "time": 0, "success": None, "category": ""}),
        "reward_logs": [dict(row) for row in bucket.get("reward_logs", [])],
    }


def _日志(配置: Any, state: dict[str, Any], event: str, exc: Exception | None = None, *, 记录活动: bool = True) -> None:
    if 记录活动:
        _记录阅读活动(配置, state, event, success=exc is None and event != "reward_not_collected", exc=exc)
    now = int(time.time())
    _运行状态[_任务键(配置)] = {"last_event": event, "last_time": now}
    if exc is None:
        logger.info("STV账号任务：appid=%s, uid=%s, event=%s", _作用域(配置), state.get("uid") or "none", event)
    elif getattr(exc, "category", "") == "breakthrough_unavailable":
        logger.info("STV账号任务未提交：appid=%s, uid=%s, stage=%s, reason=breakthrough_unavailable",
                    _作用域(配置), state.get("uid") or "none", event)
    else:
        logger.warning("STV账号任务失败：appid=%s, uid=%s, stage=%s, error_type=%s, category=%s, http_status=%s, code=%s",
                       _作用域(配置), state.get("uid") or "none", event, type(exc).__name__,
                       exc.reason if isinstance(exc, 数据库连接错误) else getattr(exc, "category", "unknown"),
                       getattr(exc, "http_status", None),
                       exc.mysql_code if isinstance(exc, 数据库连接错误) else getattr(exc, "code", None))


def _摘要(配置: Any, state: dict[str, Any]) -> dict[str, Any]:
    task = _任务表.get(_任务键(配置))
    return {key: state[key] for key in ("uid", "username", "auth_status", "online_enabled", "rewards_enabled", "last_event", "last_time")} | {
        "logged_in": bool(state["uid"] and state["cookies"] and state["auth_status"] != "invalid"),
        "running": bool(state["online_enabled"] and state["auth_status"] != "invalid" and task and not task.done()),
        **_运行状态.get(_任务键(配置), {}),
        **_阅读摘要(配置, state),
    }


async def 读取STV账号摘要(配置: Any) -> dict[str, Any]:
    # 只读取已持久化的整行快照，不等待后台网络或消耗操作持有的账号锁。
    return _摘要(配置, await _读状态(配置))


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
                _清理阅读记录(配置)
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
        _清理阅读记录(配置)
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
                   "name", "info", "level", "i", "n", "t", "ac", "l", "d", "id", "title", "amount", "count"}
        result = {key: _安全资料(item) for key, item in value.items() if key in allowed}
        if isinstance(value.get("attributes"), dict):
            result["attributes"] = {_文本(key)[:80]: _安全资料(item)
                                    for key, item in list(value["attributes"].items())[:100]}
        return result
    if isinstance(value, list):
        return [_安全资料(item) for item in value[:1000]]
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
    tasks = [_任务表.pop(old_key) for old_key in list(_任务表)
             if old_key.startswith(_作用域(配置) + ":")]
    for task in tasks:
        if task is not asyncio.current_task() and not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    if not _服务运行:
        return
    async with _锁(配置):
        try:
            state = await _读状态(配置)
        except Exception as exc:
            if not _可恢复后台错误(exc):
                raise
            # 启动时的瞬时读库失败也交给同一任务恢复，不能只留下已开启的配置。
            state = None
        if _服务运行 and (state is None or (
            state["online_enabled"] and state["uid"] and state["cookies"] and state["auth_status"] != "invalid"
        )):
            snapshot = copy.deepcopy(dict(配置))
            snapshot["__mantou_bot_appid__"] = _作用域(配置)
            task = asyncio.create_task(_后台任务(snapshot, state["revision"] if state else None), name="STV在线任务:" + _作用域(配置))
            _任务表[key] = task


async def _取消作用域任务(配置: Any) -> None:
    async with _锁(配置, 调度=True):
        key = _任务键(配置)
        task = _任务表.pop(key, None)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def 启动STV后台任务(配置: Any) -> None:
    global _服务运行
    _服务运行 = True
    # 生命周期尚未枚举到机器人时没有账号作用域，不能恢复任务或借用其他机器人。
    if not 获取当前机器人AppID(配置):
        return
    await _同步任务(配置)


async def 停止STV后台任务() -> None:
    global _服务运行
    _服务运行 = False
    tasks = list(_任务表.values())
    _任务表.clear()
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
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
    try:
        state = await _读状态(配置)

        def current(row: dict[str, Any]) -> bool:
            return (_服务运行 and row["revision"] == revision and row["uid"] == uid
                    and row["online_enabled"] and row["auth_status"] != "invalid")

        heartbeat_due = reading_due = time.monotonic()
        reward_due = float("inf")
        reward_cid = ""
        recent: list[tuple[str, str, str]] = []
        last_book = None
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
                            reward_due = time.monotonic() + 300
                            offered = await client.reward_status()
                            async with _锁(配置):
                                state = await _读状态(配置)
                                if not current(state):
                                    return
                                if state["cookies"] != cookies:
                                    break
                                if offered and state["rewards_enabled"]:
                                    stage = "reward_collect"
                                    reward_result = None
                                    # 消耗仍串行；领取前持久关闭，取消或未知结果不重放。
                                    state["rewards_enabled"] = False
                                    await _写状态(配置, state)
                                    _记录阅读活动(配置, state, stage)
                                    reward_pending, reward_result = True, None
                                    result = await client.collect_reward(reward_cid)
                                    reward_result = bool(result.get("collected"))
                                    # 领奖结果已经明确，后续状态保存失败也不能改写成领取失败。
                                    _日志(配置, state, "reward_collected" if reward_result else "reward_not_collected")
                                    reward_pending = False
                                    reward_cid = ""
                                    state["rewards_enabled"] = True
                                    await _写状态(配置, state)
                                elif not offered:
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
                                body = await client.chapter(*last_book, str(chapter["cid"]))
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
                                    recent = [*recent, (*last_book, str(chapter["cid"]))][-256:]
                                    reading_stage = "chapter"
                                else:
                                    reading_due = time.monotonic() + _随机.randint(180, 300)
                                    if body.get("reward_token_count", 0) >= 400 and state["rewards_enabled"]:
                                        reward_cid = str(chapter["cid"])
                                        reward_due = time.monotonic() + 15
                                    reading_stage = "book"
                                    _日志(配置, state, "reading_completed")
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
                        else:
                            reading_due = time.monotonic() + delay
                            reading_stage = "book"
                    deadlines = [heartbeat_due, reading_due]
                    if reward_cid and state["rewards_enabled"]:
                        deadlines.append(reward_due)
                    await asyncio.sleep(max(0.1, min(deadlines) - time.monotonic()))
    except asyncio.CancelledError:
        if reward_pending:
            if reward_result is None:
                _日志(配置, state, "reward_collect", STVError("operation_unconfirmed"))
            else:
                _日志(配置, state, "reward_collected" if reward_result else "reward_not_collected")
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


def _文本(value: Any) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", "", html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))).strip()


def _元数据(row: dict[str, Any], identity: str) -> dict[str, Any]:
    status_raw = _文本(row.get("status")).casefold()
    status = "完结" if status_raw in {"hoàn thành", "hoàn tất", "已完结", "完结", "completed"} else (
        "连载" if status_raw in {"còn tiếp", "đang ra", "连载", "连载中", "ongoing"} else "未知")
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
        async with STVClient(cookies=state["cookies"], uid=state["uid"]) as client:
            detail = _元数据(await client.detail(host, number), identity)
            if not detail["title"]:
                raise STVError("invalid_detail")
            chapters = await client.catalog(host, number)
            if not chapters:
                raise STVError("empty_catalog")
            logger.info("STV小说开始下载：书籍编号=%s, 章节数=%s", identity, len(chapters))
            yield "\n".join([f"书名：{detail['title']}", f"作者：{detail['author']}", f"状态：{detail['status']}",
                              f"章节：{len(chapters)} 章", f"字数：{格式化小说字数(detail['word_count'])}", "", "正在下载中请稍等....."])
            stage = "chapters"
            contents = []
            selected = []
            failures = 0
            # 同本书的 key/readcontextid 绑定同一会话；不并发替换上下文。
            for chapter in chapters:
                try:
                    body = await client.chapter(host, number, str(chapter["cid"]))
                except STVError as exc:
                    if exc.category in {"login_required", "paid_chapter", "content_unavailable"}:
                        failures += 1
                        continue
                    raise
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
        yield "文件发送失败，请稍后再试" if stage == "upload_send" else "下载失败 请重试"
