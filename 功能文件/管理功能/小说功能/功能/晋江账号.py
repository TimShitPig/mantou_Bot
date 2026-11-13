"""晋江账号的机器人作用域存储；凭据只在内部下载与登录流程使用。"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from typing import Any, Callable

from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    已配置运行状态数据库,
    读取运行状态值,
    写入运行状态值,
)

_账号锁 = globals().get("_账号锁") or threading.RLock()
命名空间 = "jinjiang_auth"
状态键 = "login_state"


def _身份(数据: Any) -> dict[str, str]:
    if not isinstance(数据, dict):
        raise ValueError("晋江账号格式无效")
    reader_id = 数据.get("readerId")
    token = 数据.get("token")
    if isinstance(reader_id, bool) or not isinstance(reader_id, (str, int)):
        raise ValueError("晋江账号编号无效")
    reader_id = str(reader_id)
    if not re.fullmatch(r"[0-9]{1,32}", reader_id) or int(reader_id) <= 0:
        raise ValueError("晋江账号编号无效")
    reader_id = str(int(reader_id))
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= 8192
        or any(c == ":" or c.isspace() or ord(c) < 33 or ord(c) > 126 for c in token)
    ):
        raise ValueError("晋江账号凭据无效")
    return {"readerId": reader_id, "token": token}


def _账号ID(reader_id: str) -> str:
    return "jj_" + hashlib.sha256(reader_id.encode("ascii")).hexdigest()[:20]


def _指纹(数据: dict[str, Any]) -> str:
    return hashlib.sha256(
        (数据["readerId"] + "\x1f" + 数据["token"]).encode()
    ).hexdigest()


def _要求作用域(配置: Any) -> None:
    if not re.fullmatch(r"[0-9]+", str(获取当前机器人AppID(配置) or "")):
        raise ValueError("请选择有效机器人")


def _读取(配置: Any) -> dict[str, Any]:
    _要求作用域(配置)
    raw = 读取运行状态值(配置, 命名空间, 状态键, "")
    if not raw:
        return {"version": 1, "selected_id": "", "accounts": []}
    try:
        state = json.loads(raw)
        if not isinstance(state, dict) or not isinstance(state.get("accounts"), list):
            raise ValueError
        rows = {}
        for item in state["accounts"]:
            identity = _身份(item)
            account_id = _账号ID(identity["readerId"])
            rows[account_id] = {
                "id": account_id,
                **identity,
                "nickname": str(item.get("nickname") or "")[:120],
                "enabled": item.get("enabled") is not False,
                "auth_status": item.get("auth_status")
                if item.get("auth_status") in {"valid", "invalid"}
                else "unknown",
                "auth_checked_at": max(0, int(item.get("auth_checked_at") or 0)),
                "updated_at": max(0, int(item.get("updated_at") or 0)),
                "profile_updated_at": max(0, int(item.get("profile_updated_at") or 0)),
                "credential_revision": max(
                    0, int(item.get("credential_revision") or 0)
                ),
            }
        selected = str(state.get("selected_id") or "")
        if not any(
            item["id"] == selected and item["enabled"] for item in rows.values()
        ):
            selected = ""
        return {"version": 1, "selected_id": selected, "accounts": list(rows.values())}
    except (TypeError, ValueError, OverflowError):
        raise ValueError("晋江账号状态无效") from None


def _写入(配置: Any, state: dict[str, Any]) -> None:
    _要求作用域(配置)
    if not 已配置运行状态数据库(配置):
        raise ValueError("数据库未配置")
    写入运行状态值(
        配置,
        命名空间,
        状态键,
        json.dumps(state, ensure_ascii=True, separators=(",", ":")),
    )


def _摘要(state: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "readerId",
        "nickname",
        "enabled",
        "auth_status",
        "auth_checked_at",
        "updated_at",
        "profile_updated_at",
    )
    rows = []
    for account in state["accounts"]:
        row = {key: account[key] for key in fields}
        row["nickname"] = row["nickname"] or "晋江书友_" + row["readerId"][-6:]
        row["selected"] = account["id"] == state["selected_id"]
        rows.append(row)
    return {
        "configured": any(
            item["selected"] and item["auth_status"] != "invalid" for item in rows
        ),
        "selected_id": state["selected_id"],
        "accounts": rows,
    }


def 读取晋江账号列表(配置: Any) -> dict[str, Any]:
    with _账号锁:
        return _摘要(_读取(配置))


def 读取晋江账号凭据(配置: Any, 账号ID: str = "") -> dict[str, Any] | None:
    _要求作用域(配置)
    if not 已配置运行状态数据库(配置):
        return None
    with _账号锁:
        state = _读取(配置)
        target = str(账号ID or state["selected_id"])
        for account in state["accounts"]:
            if account["id"] == target:
                if not 账号ID and (
                    not account["enabled"] or account["auth_status"] == "invalid"
                ):
                    return None
                return {
                    key: account[key]
                    for key in (
                        "id",
                        "readerId",
                        "token",
                        "credential_revision",
                        "auth_checked_at",
                    )
                } | {"credential_fingerprint": _指纹(account)}
    return None


def 保存晋江账号(
    配置: Any,
    登录态: dict[str, Any],
    账号ID: str = "",
    设为当前: bool = True,
    *,
    提交前校验: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    identity = _身份(登录态)
    account_id = _账号ID(identity["readerId"])
    if 账号ID and 账号ID != account_id:
        raise ValueError("晋江账号身份不匹配")
    with _账号锁:
        if 提交前校验 is not None and not 提交前校验():
            raise PermissionError("扫码会话已结束")
        state = _读取(配置)
        account = next(
            (item for item in state["accounts"] if item["id"] == account_id), None
        )
        if account is None:
            account = {"id": account_id, "nickname": "", "profile_updated_at": 0}
            state["accounts"].append(account)
        account.update(
            identity,
            enabled=True,
            auth_status="unknown",
            auth_checked_at=time.time_ns(),
            updated_at=int(time.time()),
            credential_revision=time.time_ns(),
        )
        nickname = (
            登录态.get("nickname") or 登录态.get("name") or 登录态.get("readerName")
        )
        if isinstance(nickname, str) and nickname.strip():
            account["nickname"] = nickname.strip()[:120]
        if 设为当前 or not state["selected_id"]:
            state["selected_id"] = account_id
        if 提交前校验 is not None and not 提交前校验():
            raise PermissionError("扫码会话已结束")
        _写入(配置, state)
        return _摘要(state)


def _变更账号(
    配置: Any,
    账号ID: str,
    action: str,
    enabled: bool = True,
    *,
    提交前校验: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    with _账号锁:
        if 提交前校验 is not None and not 提交前校验():
            raise PermissionError("账号会话已结束")
        state = _读取(配置)
        account = next(
            (item for item in state["accounts"] if item["id"] == 账号ID), None
        )
        if account is None:
            raise ValueError("晋江账号不存在")
        if action == "delete":
            state["accounts"] = [
                item for item in state["accounts"] if item["id"] != 账号ID
            ]
        elif action == "enable":
            if not isinstance(enabled, bool):
                raise ValueError("账号开关参数无效")
            account["enabled"] = enabled
        elif action == "select":
            if not account["enabled"]:
                raise ValueError("请选择已启用的晋江账号")
            state["selected_id"] = 账号ID
        if not any(
            item["id"] == state["selected_id"] and item["enabled"]
            for item in state["accounts"]
        ):
            state["selected_id"] = next(
                (item["id"] for item in state["accounts"] if item["enabled"]), ""
            )
        if 提交前校验 is not None and not 提交前校验():
            raise PermissionError("账号会话已结束")
        _写入(配置, state)
        return _摘要(state)


def 删除晋江账号(
    配置: Any, 账号ID: str, *, 提交前校验: Callable[[], bool] | None = None
) -> dict[str, Any]:
    return _变更账号(配置, 账号ID, "delete", 提交前校验=提交前校验)


def 切换晋江账号(
    配置: Any, 账号ID: str, *, 提交前校验: Callable[[], bool] | None = None
) -> dict[str, Any]:
    return _变更账号(配置, 账号ID, "select", 提交前校验=提交前校验)


def 设置晋江账号启用(
    配置: Any, 账号ID: str, 启用: bool, *, 提交前校验: Callable[[], bool] | None = None
) -> dict[str, Any]:
    return _变更账号(配置, 账号ID, "enable", 启用, 提交前校验=提交前校验)


def 合并晋江账号资料(
    配置: Any,
    凭据: dict[str, Any],
    资料: dict[str, Any],
    *,
    提交前校验: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    with _账号锁:
        if 提交前校验 is not None and not 提交前校验():
            raise PermissionError("账号会话已结束")
        state = _读取(配置)
        account = next(
            (item for item in state["accounts"] if item["id"] == 凭据.get("id")), None
        )
        if (
            account is None
            or _指纹(account) != 凭据.get("credential_fingerprint")
            or account["credential_revision"] != 凭据.get("credential_revision")
            or account["auth_checked_at"] != 凭据.get("auth_checked_at")
        ):
            return _摘要(state)
        status = 资料.get("auth_status")
        # 网络或未知响应不覆盖已知身份；仅协议层明确有效/失效才落库。
        if status in {"valid", "invalid"}:
            account["auth_status"] = status
            account["auth_checked_at"] = time.time_ns()
            account["profile_updated_at"] = int(time.time())
            nickname = 资料.get("nickname")
            if isinstance(nickname, str) and nickname.strip():
                account["nickname"] = nickname.strip()[:120]
            if 提交前校验 is not None and not 提交前校验():
                raise PermissionError("账号会话已结束")
            _写入(配置, state)
        return _摘要(state)
