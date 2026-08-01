from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from astrbot.api import logger

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    已配置运行状态数据库,
    读取运行状态值,
    写入运行状态值,
)


网盘Cookie命名空间 = "novel_pan_auth"
平台状态键 = {"UC": "uc", "夸克": "quark", "百度": "baidu"}
平台显示名 = {"UC": "UC网盘", "夸克": "夸克网盘", "百度": "百度网盘"}
平台前缀模式 = re.compile(
    r"^\s*(UC|夸克|百度)(?:网盘)?(?:\s*Cookie)?\s*[:：#]\s*",
    re.I,
)
Cookie名称模式 = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _规范化平台名称(平台: Any) -> str:
    文本 = str(平台 or "").strip()
    if 文本.lower() == "uc":
        return "UC"
    if 文本 in ("夸克", "百度"):
        return 文本
    return ""


def _规范化Cookie名称(名称: Any) -> str:
    文本 = str(名称 or "").strip().strip("*`'\"")
    文本 = 文本.replace("\\_", "_").replace("\\-", "-")
    return 文本 if Cookie名称模式.fullmatch(文本) else ""


def _写入Cookie字段(字段: dict[str, tuple[str, str]], 名称: Any, 值: Any) -> None:
    Cookie名称 = _规范化Cookie名称(名称)
    Cookie值 = str(值 if 值 is not None else "").strip().strip("'\"`")
    if not Cookie名称 or not Cookie值:
        return
    字段[Cookie名称.lower()] = (Cookie名称, Cookie值)


def _从CookieJSON提取(数据: Any, 字段: dict[str, tuple[str, str]], 域名: set[str]) -> None:
    if isinstance(数据, list):
        for 项目 in 数据:
            _从CookieJSON提取(项目, 字段, 域名)
        return
    if not isinstance(数据, dict):
        return
    名称 = 数据.get("name")
    值 = 数据.get("value")
    if 名称 is not None and 值 is not None:
        _写入Cookie字段(字段, 名称, 值)
    当前域名 = str(数据.get("domain") or 数据.get("host") or "").strip().lower()
    if 当前域名:
        域名.add(当前域名.lstrip("."))
    for 键, 项目值 in 数据.items():
        规范键 = _规范化Cookie名称(键)
        if 规范键 and isinstance(项目值, (str, int, float)):
            if 规范键.lower() in {
                "bduss",
                "stoken",
                "b-user-id",
                "__puus",
                "__uid",
                "ctoken",
                "udrive_transfer_sess",
            }:
                _写入Cookie字段(字段, 规范键, 项目值)
        elif isinstance(项目值, (dict, list)):
            _从CookieJSON提取(项目值, 字段, 域名)


def _提取Cookie候选文本(原文: str) -> list[str]:
    候选: list[str] = []
    for 模式 in (
        re.compile(r"(?:-H|--header)\s*(['\"])Cookie\s*:\s*(.*?)\1", re.I | re.S),
        re.compile(r"(?:-b|--cookie)\s*(['\"])(.*?)\1", re.I | re.S),
    ):
        候选.extend(匹配.group(2).strip() for 匹配 in 模式.finditer(原文) if 匹配.group(2).strip())
    for 行 in 原文.splitlines():
        匹配 = re.match(r"^\s*Cookie\s*:\s*(.+)$", 行, re.I)
        if 匹配:
            候选.append(匹配.group(1).strip())
    return 候选 or [原文]


def _提取Cookie字段(文本: Any) -> tuple[dict[str, tuple[str, str]], set[str], str, str]:
    原文 = str(文本 or "").strip()
    指定平台 = ""
    前缀匹配 = 平台前缀模式.match(原文)
    if 前缀匹配:
        指定平台 = _规范化平台名称(前缀匹配.group(1))
        原文 = 原文[前缀匹配.end():].strip()

    字段: dict[str, tuple[str, str]] = {}
    域名: set[str] = set()
    try:
        JSON数据 = json.loads(原文)
    except (TypeError, ValueError, json.JSONDecodeError):
        JSON数据 = None
    if JSON数据 is not None:
        _从CookieJSON提取(JSON数据, 字段, 域名)

    for 行 in 原文.splitlines():
        处理行 = 行.strip()
        if 处理行.startswith("#HttpOnly_"):
            处理行 = 处理行[len("#HttpOnly_"):]
        elif 处理行.startswith("#"):
            continue
        分段 = 处理行.split("\t")
        if len(分段) >= 7:
            域名.add(str(分段[0]).strip().lower().lstrip("."))
            _写入Cookie字段(字段, 分段[5], 分段[6])

    if not 字段:
        for 候选 in _提取Cookie候选文本(原文):
            for 片段 in re.split(r";\s*|\r?\n", 候选):
                片段 = 片段.strip().strip("'\"`")
                if not 片段 or "=" not in 片段:
                    continue
                名称, 值 = 片段.split("=", 1)
                _写入Cookie字段(字段, 名称, 值)
    return 字段, 域名, 指定平台, 原文


def _识别平台(
    字段: dict[str, tuple[str, str]],
    域名: set[str],
    指定平台: str,
    原文: str,
) -> str:
    if 指定平台:
        return 指定平台
    名称集合 = set(字段)
    域名文本 = " ".join(域名)
    原文小写 = 原文.lower()
    if {"bduss", "stoken"}.issubset(名称集合) or "baidu.com" in 域名文本:
        return "百度"
    if (
        "udrive_transfer_sess" in 名称集合
        or any(名称.startswith("_up_28a_") for 名称 in 名称集合)
        or "drive.uc.cn" in 原文小写
        or "uc.cn" in 域名文本
    ):
        return "UC"
    if (
        {"b-user-id", "__puus"}.issubset(名称集合)
        or {"ctoken", "__puus"}.issubset(名称集合)
        or "quark.cn" in 域名文本
        or "pan.quark.cn" in 原文小写
        or "drive-pc.quark.cn" in 原文小写
    ):
        return "夸克"
    return ""


def _Cookie字段完整(平台: str, 字段: dict[str, tuple[str, str]]) -> bool:
    名称集合 = set(字段)
    if 平台 == "UC":
        return "udrive_transfer_sess" in 名称集合 and bool(
            {"ctoken", "__puus", "__uid"} & 名称集合
        )
    if 平台 == "夸克":
        return "__puus" in 名称集合 and bool({"b-user-id", "__uid"} & 名称集合)
    if 平台 == "百度":
        return {"bduss", "stoken"}.issubset(名称集合)
    return False


def _序列化Cookie字段(字段: dict[str, tuple[str, str]]) -> str:
    return "; ".join(f"{名称}={值}" for 名称, 值 in 字段.values())


def 解析网盘Cookie(文本: Any) -> tuple[str, str] | None:
    字段, 域名, 指定平台, 原文 = _提取Cookie字段(文本)
    平台 = _识别平台(字段, 域名, 指定平台, 原文)
    if not 平台:
        return None
    if not _Cookie字段完整(平台, 字段):
        return 平台, ""
    return 平台, _序列化Cookie字段(字段)


def _保存网盘Cookie(配置: Any, 平台: str, Cookie: str) -> None:
    payload = json.dumps(
        {"provider": 平台, "cookie": Cookie, "updated_at": int(time.time())},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    写入运行状态值(配置, 网盘Cookie命名空间, 平台状态键[平台], payload)


def _读取保存的网盘Cookie(配置: Any, 平台: str) -> str:
    原始值 = 读取运行状态值(配置, 网盘Cookie命名空间, 平台状态键[平台], "")
    if not 原始值:
        return ""
    try:
        数据 = json.loads(原始值)
    except (TypeError, ValueError, json.JSONDecodeError):
        数据 = None
    Cookie = str(数据.get("cookie") or "").strip() if isinstance(数据, dict) else str(原始值).strip()
    解析结果 = 解析网盘Cookie(f"{平台} Cookie: {Cookie}")
    if not 解析结果 or 解析结果[0] != 平台:
        return ""
    return 解析结果[1]


def 读取网盘Cookie(配置: Any, 平台: str, 配置Cookie: Any = "") -> str:
    规范平台 = _规范化平台名称(平台)
    if 规范平台 and 已配置运行状态数据库(配置):
        try:
            保存Cookie = _读取保存的网盘Cookie(配置, 规范平台)
            if 保存Cookie:
                return 保存Cookie
        except Exception as 异常:
            logger.warning(f"{平台显示名[规范平台]}Cookie读取失败：error={type(异常).__name__}")
    配置原值 = str(配置Cookie or "").strip()
    if 规范平台 and 配置原值:
        解析结果 = 解析网盘Cookie(f"{规范平台} Cookie: {配置原值}")
        if 解析结果 and 解析结果[1]:
            return 解析结果[1]
    return 配置原值


def 持久化刷新后的网盘Cookie(
    配置: Any,
    平台: str,
    原Cookie: Any,
    新Cookie: Any,
) -> None:
    规范平台 = _规范化平台名称(平台)
    原值 = str(原Cookie or "").strip()
    新值 = str(新Cookie or "").strip()
    if not 规范平台 or not 新值 or 新值 == 原值 or not 已配置运行状态数据库(配置):
        return
    try:
        当前保存值 = _读取保存的网盘Cookie(配置, 规范平台)
        if not 当前保存值 or 当前保存值 != 原值:
            return
        解析结果 = 解析网盘Cookie(f"{规范平台} Cookie: {新值}")
        if not 解析结果 or not 解析结果[1]:
            return
        _保存网盘Cookie(配置, 规范平台, 解析结果[1])
    except Exception as 异常:
        logger.warning(f"{平台显示名[规范平台]}Cookie刷新保存失败：error={type(异常).__name__}")


async def 处理网盘Cookie指令(event: Any, 命令文本: str, 配置: Any = None) -> str | None:
    解析结果 = 解析网盘Cookie(命令文本)
    if 解析结果 is None:
        return None
    平台, Cookie = 解析结果
    if not 是群文件清理管理员(event, 配置):
        return ""
    显示名 = 平台显示名[平台]
    if not Cookie:
        return f"{显示名}Cookie无效，请提供完整浏览器Cookie"
    if not 已配置运行状态数据库(配置):
        return f"数据库未配置，{显示名}Cookie未保存"
    try:
        await asyncio.to_thread(_保存网盘Cookie, 配置, 平台, Cookie)
    except Exception as 异常:
        logger.warning(f"{显示名}Cookie保存失败：error={type(异常).__name__}")
        return f"{显示名}Cookie保存失败，请稍后再试"
    return f"{显示名}Cookie已保存并覆盖原登录态"
