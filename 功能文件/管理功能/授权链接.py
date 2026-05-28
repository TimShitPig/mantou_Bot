from __future__ import annotations

import json
import urllib.parse
from typing import Any

from astrbot.api import logger


AUTH_COMMANDS = {"\u6388\u6743"}
PAGE_NAME = "ai_group_service_agreement_pop_page"
TRANSFER_URL = "https://club.vip.qq.com/transfer?open_kuikly_info="
UID_ACTIONS = (
    "getUidFromUin",
    "get_uid_from_uin",
    "get_uid_by_uin",
    "get_uid",
    "_get_uid",
    "get_uin2uid",
    "getUin2Uid",
)


async def handle_authorization_link(event: Any, command_text: str, context: Any = None, config: Any = None) -> str | None:
    if str(command_text or "").strip() not in AUTH_COMMANDS:
        return None

    group_code = get_group_code(event)
    if not group_code:
        return "\u6388\u6743\u94fe\u63a5\u751f\u6210\u5931\u8d25\uff1a\u6ca1\u6709\u83b7\u53d6\u5230\u6570\u5b57QQ\u7fa4\u53f7\uff0c\u8bf7\u5728\u76ee\u6807\u7fa4\u91cc\u53d1\u9001\u201c\u6388\u6743\u201d"

    bot_uin = await get_bot_uin(event, context)
    if not bot_uin:
        return "\u6388\u6743\u94fe\u63a5\u751f\u6210\u5931\u8d25\uff1a\u6ca1\u6709\u83b7\u53d6\u5230\u673a\u5668\u4ebaQQ\u53f7\uff0c\u5f53\u524d\u9002\u914d\u5668\u6ca1\u6709\u8fd4\u56de botUin"

    bot_uid = await get_bot_uid(event, bot_uin)
    if not bot_uid:
        return f"\u6388\u6743\u94fe\u63a5\u751f\u6210\u5931\u8d25\uff1a\u6ca1\u6709\u83b7\u53d6\u5230\u673a\u5668\u4ebaUID\uff0c\u5f53\u524d\u9002\u914d\u5668\u4e0d\u652f\u6301 getUidFromUin({bot_uin})"

    link = build_authorization_link(group_code, bot_uin, bot_uid)
    logger.info(f"authorization link generated: groupCode={group_code}, botUin={bot_uin}, botUid={bot_uid}")
    return "\n".join([
        "\u6388\u6743\u94fe\u63a5\uff1a",
        link,
        "",
        "\u8bf7\u7fa4\u4e3b\u4f7f\u7528\u5b89\u5353/\u9e3f\u8499 QQ 9.2.90 \u53ca\u4ee5\u4e0a\u6253\u5f00\uff0ciOS \u6682\u4e0d\u652f\u6301\u3002",
    ])


def build_authorization_link(group_code: str, bot_uin: str, bot_uid: str) -> str:
    payload = {
        "page_name": PAGE_NAME,
        "groupCode": int(group_code),
        "botUin": int(bot_uin),
        "botUid": str(bot_uid),
        "screen": 1,
    }
    json_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return TRANSFER_URL + urllib.parse.quote(json_text, safe="")


def get_group_code(event: Any) -> str:
    for method_name in ("get_group_id", "get_group"):
        method = getattr(event, method_name, None)
        if callable(method):
            group_code = normalize_digits(method())
            if group_code:
                return group_code

    message_obj = getattr(event, "message_obj", None)
    raw_message = read_field(message_obj, "raw_message")
    for obj in (event, message_obj, raw_message):
        value = read_first_field(obj, ("groupCode", "group_code", "group_id", "group", "group_uin"))
        group_code = normalize_digits(value)
        if group_code:
            return group_code
    return ""


async def get_bot_uin(event: Any, context: Any = None) -> str:
    bot = getattr(event, "bot", None)
    api_value = await get_bot_uin_from_api(bot)
    if api_value:
        return api_value

    message_obj = getattr(event, "message_obj", None)
    raw_message = read_field(message_obj, "raw_message")
    candidates = (event, message_obj, raw_message, bot, getattr(bot, "api", None), context)
    for obj in candidates:
        value = read_first_field(obj, ("self_id", "bot_id", "robot_id", "botUin", "bot_uin", "uin", "qq", "user_id"))
        bot_uin = normalize_digits(value)
        if bot_uin:
            return bot_uin
    return ""


async def get_bot_uin_from_api(bot: Any) -> str:
    response = await call_bot_action(bot, "get_login_info")
    return extract_first_digits(response, ("user_id", "self_id", "bot_id", "robot_id", "uin", "qq"))


async def get_bot_uid(event: Any, bot_uin: str) -> str:
    bot = getattr(event, "bot", None)
    local_uid = extract_local_bot_uid(event, bot)
    if local_uid:
        return local_uid

    for action_name in UID_ACTIONS:
        for params in build_uid_param_candidates(bot_uin):
            response = await call_bot_action(bot, action_name, **params)
            bot_uid = extract_uid(response)
            if bot_uid:
                return bot_uid
    return ""


def extract_local_bot_uid(event: Any, bot: Any) -> str:
    message_obj = getattr(event, "message_obj", None)
    raw_message = read_field(message_obj, "raw_message")
    for obj in (event, message_obj, raw_message, bot, getattr(bot, "api", None)):
        value = read_first_field(obj, ("botUid", "bot_uid", "robot_uid", "self_uid"))
        uid = normalize_uid(value)
        if uid:
            return uid
    return ""


def build_uid_param_candidates(bot_uin: str) -> list[dict[str, Any]]:
    number = int(bot_uin) if str(bot_uin).isdigit() else bot_uin
    return [
        {"uin": number},
        {"uin": str(bot_uin)},
        {"user_id": number},
        {"qq": number},
        {"botUin": number},
    ]


async def call_bot_action(bot: Any, action_name: str, **params: Any) -> Any:
    if bot is None:
        return None

    api = getattr(bot, "api", None)
    call_action = getattr(api, "call_action", None)
    if callable(call_action):
        try:
            return await call_action(action_name, **params)
        except Exception as exc:
            logger.debug(f"authorization action failed: action={action_name}, params={params}, error={exc}")

    for obj in (bot, api):
        method = getattr(obj, action_name, None)
        if not callable(method):
            continue
        try:
            return await maybe_await(method(**params))
        except TypeError:
            try:
                first_arg = next(iter(params.values())) if params else None
                return await maybe_await(method(first_arg) if first_arg is not None else method())
            except Exception as exc:
                logger.debug(f"authorization method failed: method={action_name}, params={params}, error={exc}")
        except Exception as exc:
            logger.debug(f"authorization method failed: method={action_name}, params={params}, error={exc}")
    return None


async def maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def extract_uid(value: Any) -> str:
    if isinstance(value, str):
        return normalize_uid(value)
    if isinstance(value, dict):
        for field in ("botUid", "bot_uid", "uid", "user_uid", "uin_uid"):
            uid = normalize_uid(value.get(field))
            if uid:
                return uid
        for field in ("data", "result", "ret", "response"):
            uid = extract_uid(value.get(field))
            if uid:
                return uid
        for child in value.values():
            if isinstance(child, (dict, list)):
                uid = extract_uid(child)
                if uid:
                    return uid
    if isinstance(value, list):
        for item in value:
            uid = extract_uid(item)
            if uid:
                return uid
    return ""


def extract_first_digits(value: Any, fields: tuple[str, ...]) -> str:
    if isinstance(value, dict):
        for field in fields:
            digits = normalize_digits(value.get(field))
            if digits:
                return digits
        for field in ("data", "result", "ret", "response"):
            digits = extract_first_digits(value.get(field), fields)
            if digits:
                return digits
    return normalize_digits(value)


def read_first_field(obj: Any, fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = read_field(obj, field)
        if value not in (None, ""):
            return value
    return None


def read_field(obj: Any, field: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


def normalize_digits(value: Any) -> str:
    if isinstance(value, dict):
        for field in ("group_id", "groupCode", "user_id", "self_id", "uin", "qq", "id"):
            result = normalize_digits(value.get(field))
            if result:
                return result
        return ""
    if value is None or callable(value):
        return ""
    text = str(value).strip()
    return text if text.isdigit() else ""


def normalize_uid(value: Any) -> str:
    if value is None or callable(value):
        return ""
    text = str(value).strip()
    if not text or text.isdigit():
        return ""
    return text if text.startswith("u_") or len(text) >= 8 else ""


globals()["\u5904\u7406\u6388\u6743\u94fe\u63a5"] = handle_authorization_link
globals()["\u751f\u6210\u6388\u6743\u94fe\u63a5"] = build_authorization_link

