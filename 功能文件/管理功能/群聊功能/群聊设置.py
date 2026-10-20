"""QQ 官方群设置：按 AppID/群隔离，分页读取和一次性批量写入。"""

import asyncio
import copy
import re
import time
from collections import deque
from datetime import datetime

import aiohttp
from astrbot.api import logger
from 功能文件.管理功能.基础功能 import 消息记录
from 功能文件.管理功能.群聊功能 import 群管功能


_标识格式 = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_AppID格式 = re.compile(r"[0-9]{4,32}\Z")
_读取缓存 = globals().get("_读取缓存", {})
_频率记录 = globals().get("_频率记录", {})
_群写入锁 = globals().get("_群写入锁", {})
_读取锁 = globals().get("_读取锁", {})
_缓存代次 = globals().get("_缓存代次", {})
_缓存上限 = 1024
_频率上限 = {"members": 60, "member": 30, "remove": 30, "blacklist": 30, "blacklist_op": 60}
_踢人事件记录 = globals().get("_踢人事件记录", {})
_踢人事件有效期秒 = 600
_踢人事件记录上限 = 4096


def _错误(reason, message, status=409, code=None):
    结果 = {"ok": False, "reason": reason, "error": message, "message": message, "http_status": status}
    if type(code) is int:
        结果["code"] = code
    return 结果


def _标识有效(值):
    return isinstance(值, str) and bool(_标识格式.fullmatch(值))


def _批量有效(值):
    return isinstance(值, list) and 1 <= len(值) <= 20 and all(_标识有效(x) for x in 值) and len(set(值)) == len(值)


def _游标有效(值):
    return (isinstance(值, str) and len(值) <= 2048
            and not any(ord(x) < 32 or 127 <= ord(x) <= 159 for x in 值))


def _回收读取锁():
    if len(_读取锁) > _缓存上限 * 2:
        for 锁键, 锁 in list(_读取锁.items()):
            # release() 到等待方恢复之间锁暂时未上锁，不能移走仍有等待方的锁。
            if not 锁.locked() and not getattr(锁, "_waiters", None):
                _读取锁.pop(锁键, None)


def _取字段(对象, 字段):
    return 对象.get(字段) if isinstance(对象, dict) else getattr(对象, 字段, None)


def _通道(chat_id, appid, 上下文=None):
    if not _标识有效(chat_id) or not isinstance(appid, str):
        return None, _错误("invalid_scope", "群标识或机器人参数无效", 400)
    已知 = (消息记录.消息缓存.get(chat_id) or {}).get("appid")
    appid = appid or (已知 if isinstance(已知, str) else "")
    if not _AppID格式.fullmatch(appid):
        return None, _错误("appid_missing", "请刷新群资料后重试", 400)
    if 已知 and str(已知) != appid:
        return None, _错误("appid_mismatch", "群聊与机器人不匹配", 400)
    平台 = 消息记录.获取QQ官方平台(上下文=上下文, appid=appid)
    if 平台 is None or not 消息记录._是QQ官方平台(平台):
        return None, _错误("platform_missing", "QQ 官方机器人尚未就绪")
    通道 = 消息记录.获取HTTP通道(平台)
    if 通道 is None:
        return None, _错误("http_missing", "QQ 官方机器人尚未就绪")
    http = 通道[1]
    # 获取QQ官方平台旧版有首平台回退，认证 Token 的 AppID 必须精确匹配。
    token = getattr(http, "_token", None)
    if str(getattr(token, "app_id", "")) != appid:
        return None, _错误("appid_mismatch", "群聊与机器人不匹配", 400)
    if getattr(http, "is_sandbox", False):
        return None, _错误("sandbox", "请使用正式环境的 QQ 官方机器人")
    return (appid, http), None


def _事件通道(event):
    """群指令直接使用收到该事件的官方认证通道，不借用其它平台 Token。"""
    if not 群管功能.是QQ官方机器人(event):
        return None, _错误("platform_missing", "QQ 官方机器人尚未就绪")
    chat_id = 群管功能.获取群号(event)
    if not _标识有效(chat_id):
        return None, _错误("invalid_scope", "群标识无效", 400)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段 in ("group_openid", "group_id"):
            标识 = _取字段(对象, 字段)
            if isinstance(标识, str) and 标识 and 标识 != chat_id:
                return None, _错误("invalid_scope", "群聊目标不匹配", 400)
    bot = getattr(event, "bot", None)
    http = getattr(getattr(bot, "api", None), "_http", None)
    if http is None:
        return None, _错误("http_missing", "QQ 官方机器人尚未就绪")
    appid = str(getattr(getattr(http, "_token", None), "app_id", ""))
    if not _AppID格式.fullmatch(appid):
        return None, _错误("appid_missing", "机器人认证状态不完整", 400)
    if getattr(http, "is_sandbox", False):
        return None, _错误("sandbox", "请使用正式环境的 QQ 官方机器人")
    return (chat_id, appid, http), None


def _受控失败(chat_id, appid, stage, status=None, code=None, error_type="response"):
    if code in {11253, 11254, 40012010}:
        结果 = _错误("api_permission", "机器人尚未开通此群管理接口", 403, code)
    elif code == 11282:
        结果 = _错误("group_permission", "该群尚未授予机器人所需管理权限", 403, code)
    elif code == 11243 or status == 401:
        结果 = _错误("auth_expired", "机器人登录状态暂时失效，请稍后重试", 502, code)
    elif status == 429:
        结果 = _错误("rate_limited", "操作过于频繁，请稍后重试", 429, code)
    else:
        结果 = _错误("upstream_error", "群管理请求失败，请稍后再试", 502, code)
    logger.warning("QQ官方群设置请求失败：stage=%s, group_id=%s, appid=%s, http_status=%s, code=%s, error_type=%s, reason=%s",
                   stage, chat_id, appid, status or "none", code if code is not None else "none", error_type, 结果["reason"])
    return 结果


def _整数错误码(响应):
    for 字段 in ("err_code", "code"):
        值 = 响应.get(字段)
        if 值 not in (None, "", 0, "0"):
            try:
                return int(值)
            except (TypeError, ValueError):
                return -1
    return None


async def _请求(chat_id, appid, http, stage, method, path, *, params=None, body=None):
    记录 = _频率记录.setdefault((appid, stage), deque())
    现在 = time.monotonic()
    while 记录 and 现在 - 记录[0] >= 60:
        记录.popleft()
    if len(记录) >= _频率上限[stage]:
        return _错误("rate_limited", "操作过于频繁，请稍后重试", 429)
    记录.append(现在)
    请求已提交 = False
    try:
        # 复用 SDK 的刷新认证与会话，但避开 request() 对 ConnectionReset 的 POST 重放。
        await http.check_session()
        请求头 = dict(getattr(http, "_headers", {}) or {})
        if (str(getattr(getattr(http, "_token", None), "app_id", "")) != appid
                or not str(请求头.get("Authorization", "")).startswith("QQBot ")):
            return _错误("auth_mismatch", "机器人认证状态不匹配", 409)
        参数 = {"headers": 请求头, "timeout": aiohttp.ClientTimeout(total=20), "allow_redirects": False}
        if params:
            参数["params"] = params
        if body is not None:
            参数["json"] = body
        请求已提交 = True
        async with http._session.request(method, "https://api.bot.qq.com" + path, **参数) as 响应:
            状态 = 响应.status
            数据 = await 响应.json(content_type=None)
        if not isinstance(数据, dict):
            结果 = _受控失败(chat_id, appid, stage, 状态, error_type="invalid_response")
            if stage == "remove" and 200 <= 状态 < 300:
                return _错误("remove_unconfirmed", "成员移除结果未确认，请刷新成员列表", 502)
            return 结果
        业务码 = _整数错误码(数据)
        if not 200 <= 状态 < 300 or 业务码 is not None:
            if 消息记录._响应表示群机器人已移除(数据):
                消息记录._设置群机器人状态(chat_id, "removed", appid, 持久化=True)
            return _受控失败(chat_id, appid, stage, 状态, 业务码)
        return {"ok": True, "data": 数据}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        结果 = _受控失败(chat_id, appid, stage, error_type=type(exc).__name__)
        if stage == "remove" and 请求已提交:
            return _错误("remove_unconfirmed", "成员移除结果未确认，请刷新成员列表", 502)
        return 结果


def _日期(值):
    if not isinstance(值, str) or len(值) > 64:
        return ""
    try:
        datetime.fromisoformat(值.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return 值


def _成员(数据, chat_id, appid, 黑名单=False):
    if not isinstance(数据, dict) or not _标识有效(数据.get("member_openid")):
        return None
    if 数据.get("username") is not None and not isinstance(数据.get("username"), str):
        return None
    if not 黑名单 and (not isinstance(数据.get("member_role"), str)
                     or 数据["member_role"] not in {"member", "owner", "admin"}):
        return None
    标识 = 数据["member_openid"]
    昵称 = 消息记录._有效用户昵称(数据.get("username"), 标识)[:128]
    空白 = not 昵称 and 消息记录._明确空白昵称(数据.get("username"))
    # 列表 API 没有头像字段；只复用同 AppID 群资料及官方作用域头像地址。
    资料 = (消息记录.成员资料缓存.get(chat_id) or {}).get(标识) or {}
    头像 = 资料.get("avatar") if isinstance(资料, dict) else ""
    if not isinstance(头像, str) or not re.match(r"https?://", 头像) or len(头像) > 2048:
        头像 = "https://q.qlogo.cn/qqapp/%s/%s/0" % (appid, 标识)
    结果 = {"member_openid": 标识, "username": 昵称, "nickname": 昵称,
            "nickname_blank": bool(空白), "bot": 数据.get("bot") is True,
            "union_openid": 数据.get("union_openid") if _标识有效(数据.get("union_openid")) else "", "avatar": 头像}
    if 黑名单:
        结果["banned_at"] = _日期(数据.get("banned_at"))
    else:
        结果.update(member_role=数据["member_role"], joined_at=_日期(数据.get("joined_at")))
    return 结果


def _清缓存(appid, chat_id):
    范围 = (appid, chat_id)
    _缓存代次[范围] = _缓存代次.get(范围, 0) + 1
    for key in list(_读取缓存):
        if key[:2] == (appid, chat_id):
            _读取缓存.pop(key, None)


async def _分页读取(chat_id, appid, stage, path, 字段, cursor, limit, force, 上下文):
    if not _游标有效(cursor) or type(force) is not bool:
        return _错误("invalid_page", "分页参数无效", 400)
    通道, 错误 = _通道(chat_id, appid, 上下文)
    if 错误:
        return 错误
    appid, http = 通道
    key = (appid, chat_id, stage, cursor, limit)
    async with _读取锁.setdefault(key, asyncio.Lock()):
        缓存 = _读取缓存.get(key)
        if not force and 缓存 and time.monotonic() - 缓存[0] < (30 if 缓存[1].get("ok") else 15):
            return {**copy.deepcopy(缓存[1]), "cached": True}
        参数 = {"cursor": cursor} if cursor else {}
        if limit:
            参数["limit"] = limit
        代次 = _缓存代次.get((appid, chat_id), 0)
        结果 = await _请求(chat_id, appid, http, stage, "GET", path, params=参数)
        if _缓存代次.get((appid, chat_id), 0) != 代次:
            return _错误("stale_read", "群资料已更新，请刷新重试", 409)
        if 结果["ok"]:
            数据 = 结果["data"]
            列表 = 数据.get(字段)
            下页 = 数据.get("next_cursor")
            if (not isinstance(列表, list) or len(列表) > (30 if stage == "members" else limit)
                    or not _游标有效(下页) or (下页 and 下页 == cursor)):
                结果 = _错误("invalid_response", "群管理分页响应不完整", 502)
            else:
                成员 = [_成员(x, chat_id, appid, stage == "blacklist") for x in 列表]
                if (any(x is None for x in 成员)
                        or len({x["member_openid"] for x in 成员 if x is not None}) != len(成员)):
                    结果 = _错误("invalid_response", "群管理成员响应不完整", 502)
                else:
                    结果 = {"ok": True, 字段: 成员, "next_cursor": 下页, "has_more": bool(下页), "cached": False}
        while len(_读取缓存) >= _缓存上限:
            _读取缓存.pop(next(iter(_读取缓存)))
        _读取缓存[key] = (time.monotonic(), copy.deepcopy(结果))
        _回收读取锁()
        return 结果


async def 获取群设置(chat_id, appid="", 上下文=None):
    通道, 错误 = _通道(chat_id, appid, 上下文)
    if 错误:
        return 错误
    def 读取本地():
        配置 = 消息记录.当前插件配置
        可保存 = 群管功能.群广告开关可持久化(配置)
        群信息 = 消息记录.获取缓存的群信息(chat_id)
        if 群信息.get("appid") not in (None, "", 通道[0]):
            return _错误("appid_mismatch", "群聊与机器人不匹配", 400)
        群简介 = 群信息.get("group_finger_memo")
        群分类 = 群信息.get("group_class_text")
        群标签 = 群信息.get("group_tags")
        return {"ok": True, "can_manage": True, "available": True, "editable": True,
                "remark": 消息记录.获取群备注(chat_id), "group_qq": 消息记录.获取群QQ号(chat_id),
                "group_name": 消息记录._有效用户昵称(群信息.get("group_name") or 群信息.get("name")),
                "group_finger_memo": 群简介 if isinstance(群简介, str) else "",
                "group_class_text": 群分类 if isinstance(群分类, str) else "",
                "group_tags": [标签 for 标签 in 群标签 if isinstance(标签, str)] if isinstance(群标签, list) else [],
                "member_num": 群信息.get("member_num", 0), "is_admin": 消息记录.群机器人是否管理员(chat_id),
                "ad_enabled": 群管功能.读取群广告开关(配置, chat_id), "ad_editable": 可保存,
                "remark_editable": 可保存, "local_settings_editable": 可保存, "message": ""}
    return await asyncio.get_running_loop().run_in_executor(None, 读取本地)


async def 获取群成员列表(chat_id, appid="", cursor="", force=False, 上下文=None):
    return await _分页读取(chat_id, appid, "members", "/v2/groups/%s/members" % chat_id, "members", cursor, 0, force, 上下文)


async def 获取群成员信息(chat_id, appid="", member_openid="", force=False, 上下文=None):
    if not _标识有效(member_openid) or type(force) is not bool:
        return _错误("invalid_member", "成员参数无效", 400)
    通道, 错误 = _通道(chat_id, appid, 上下文)
    if 错误:
        return 错误
    appid, http = 通道
    key = (appid, chat_id, "member", member_openid, 0)
    async with _读取锁.setdefault(key, asyncio.Lock()):
        缓存 = _读取缓存.get(key)
        if not force and 缓存 and time.monotonic() - 缓存[0] < (30 if 缓存[1].get("ok") else 15):
            return {**copy.deepcopy(缓存[1]), "cached": True}
        代次 = _缓存代次.get((appid, chat_id), 0)
        结果 = await _请求(chat_id, appid, http, "member", "GET", "/v2/groups/%s/members/%s" % (chat_id, member_openid))
        if _缓存代次.get((appid, chat_id), 0) != 代次:
            return _错误("stale_read", "群资料已更新，请刷新重试", 409)
        if 结果["ok"]:
            成员 = _成员(结果["data"], chat_id, appid)
            结果 = {"ok": True, "member": 成员, "cached": False} if 成员 and 成员["member_openid"] == member_openid else _错误("invalid_response", "群成员详情响应不完整", 502)
        while len(_读取缓存) >= _缓存上限:
            _读取缓存.pop(next(iter(_读取缓存)))
        _读取缓存[key] = (time.monotonic(), copy.deepcopy(结果))
        _回收读取锁()
        return 结果


async def 获取群黑名单(chat_id, appid="", cursor="", limit=20, force=False, 上下文=None):
    if type(limit) is not int or not 1 <= limit <= 100:
        return _错误("invalid_limit", "黑名单分页参数无效", 400)
    return await _分页读取(chat_id, appid, "blacklist", "/v2/groups/%s/member_blacklist" % chat_id, "users", cursor, limit, force, 上下文)


def _失败成员(数据, 字段, 目标):
    列表 = 数据.get(字段)
    if not isinstance(列表, list) or any(not _标识有效(x) or x not in 目标 for x in 列表):
        return None
    return list(dict.fromkeys(列表))


async def 批量移除群成员(chat_id, appid="", member_openids=None, add_to_member_blacklist=False, 上下文=None):
    if not _批量有效(member_openids) or type(add_to_member_blacklist) is not bool:
        return _错误("invalid_batch", "单次请选择 1 至 20 个不同成员", 400)
    通道, 错误 = _通道(chat_id, appid, 上下文)
    if 错误:
        return 错误
    appid, http = 通道
    return await _执行批量移除(chat_id, appid, http, member_openids, add_to_member_blacklist)


async def 批量移除事件群成员(event, member_openids=None):
    if not _批量有效(member_openids):
        return _错误("invalid_batch", "单次请选择 1 至 20 个不同成员", 400)
    通道, 错误 = _事件通道(event)
    if 错误:
        return 错误
    chat_id, appid, http = 通道
    消息编号 = 群管功能.获取当前消息编号(event)
    if (not isinstance(消息编号, str) or not 消息编号 or len(消息编号) > 2048
            or any(ord(x) < 32 or 127 <= ord(x) <= 159 for x in 消息编号)):
        return _错误("message_id_missing", "当前消息标识无效", 400)
    现在 = time.monotonic()
    for 键, 时间 in list(_踢人事件记录.items()):
        if 现在 - 时间 >= _踢人事件有效期秒:
            _踢人事件记录.pop(键, None)
    键 = (appid, chat_id, 消息编号)
    if 键 in _踢人事件记录:
        return _错误("duplicate_event", "此条指令已处理", 409)
    if len(_踢人事件记录) >= _踢人事件记录上限:
        return _错误("rate_limited", "操作过于频繁，请稍后重试", 429)
    # 在第一次 await 前领取；成功、超时与取消均保留，避免双事件重放 POST。
    _踢人事件记录[键] = 现在
    return await _执行批量移除(chat_id, appid, http, member_openids, False)


async def _执行批量移除(chat_id, appid, http, member_openids, add_to_member_blacklist):
    async with _群写入锁.setdefault((appid, chat_id), asyncio.Lock()):
        try:
            结果 = await _请求(chat_id, appid, http, "remove", "POST", "/v2/groups/%s/batch_remove_members" % chat_id,
                           body={"member_openids": list(member_openids), "add_to_member_blacklist": add_to_member_blacklist})
        finally:
            # 超时或热重载取消后也失效旧列表，不重放操作或宣称成功。
            _清缓存(appid, chat_id)
        if not 结果["ok"]:
            return 结果
        数据 = 结果["data"]
        失败 = _失败成员(数据, "add_to_member_blacklist_fail_openids", member_openids)
        if 数据.get("remove_members_result") != "success" or 失败 is None:
            return _错误("remove_unconfirmed", "成员移除结果未确认，请刷新成员列表", 502)
        消息记录.标记群信息待刷新(chat_id)
        return {"ok": True, "partial": bool(失败), "member_openids": list(member_openids), "removed_openids": list(member_openids),
                "add_to_member_blacklist_fail_openids": 失败, "message": "成员已移除，部分成员加入黑名单失败" if 失败 else "成员已移除"}


async def 操作群黑名单(chat_id, appid="", op="", member_openids=None, 上下文=None):
    if not isinstance(op, str) or op not in {"add", "del"} or not _批量有效(member_openids):
        return _错误("invalid_operation", "黑名单操作参数无效，单次最多 20 人", 400)
    通道, 错误 = _通道(chat_id, appid, 上下文)
    if 错误:
        return 错误
    appid, http = 通道
    async with _群写入锁.setdefault((appid, chat_id), asyncio.Lock()):
        try:
            结果 = await _请求(chat_id, appid, http, "blacklist_op", "POST", "/v2/groups/%s/member_blacklist" % chat_id,
                           body={"op": op, "member_openids": list(member_openids)})
        finally:
            _清缓存(appid, chat_id)
        if not 结果["ok"]:
            return 结果
        失败 = _失败成员(结果["data"], "fail_openids", member_openids)
        if 失败 is None:
            return _错误("operation_unconfirmed", "黑名单操作结果未确认，请刷新黑名单", 502)
        成功 = [x for x in member_openids if x not in 失败]
        return {"ok": bool(成功), "partial": bool(失败) and bool(成功), "op": op, "member_openids": list(member_openids),
                "success_openids": 成功, "fail_openids": 失败, "http_status": 409 if not 成功 else 200,
                "message": "黑名单已更新，部分成员操作失败" if 成功 and 失败 else "黑名单已更新" if 成功 else "黑名单操作失败",
                "error": "黑名单操作失败" if not 成功 else ""}
