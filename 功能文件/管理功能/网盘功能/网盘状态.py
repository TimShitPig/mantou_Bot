"""网盘运行开关。

开关属于运行状态而不是插件配置：默认开启，管理员可以在控制台按平台
独立停用；停用后该平台不会参与主分享或百度后台备份。
"""

from __future__ import annotations

from typing import Any

from astrbot.api import logger


状态命名空间 = "novel_pan_enabled"
平台状态键 = {"UC": "uc", "夸克": "quark", "百度": "baidu"}
默认状态 = {平台: True for 平台 in 平台状态键}


def 规范化网盘平台(平台: Any) -> str:
    文本 = str(平台 or "").strip()
    return {
        "uc": "UC",
        "UC": "UC",
        "夸": "夸克",
        "夸克": "夸克",
        "百度": "百度",
    }.get(文本, "")


def _解析布尔值(值: Any, 默认值: bool = True) -> bool:
    文本 = "" if 值 is None else str(值).strip().lower()
    if 文本 in {"1", "true", "yes", "on", "开启"}:
        return True
    if 文本 in {"0", "false", "no", "off", "关闭"}:
        return False
    return bool(默认值)


def 读取网盘开关(配置: Any, 平台: Any) -> bool:
    规范平台 = 规范化网盘平台(平台)
    if not 规范平台:
        return False
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        return 运行状态数据库.读取布尔运行状态值(
            配置,
            状态命名空间,
            平台状态键[规范平台],
            默认状态[规范平台],
        )
    except Exception as exc:
        logger.debug("网盘运行开关读取失败：平台=%s，错误类型=%s", 规范平台, type(exc).__name__)
        return 默认状态[规范平台]


def 读取网盘开关批量(
    配置: Any, 平台列表: tuple[str, ...] = ("UC", "夸克", "百度")
) -> dict[str, bool]:
    规范平台列表: list[str] = []
    for 平台 in 平台列表:
        规范平台 = 规范化网盘平台(平台)
        if 规范平台 and 规范平台 not in 规范平台列表:
            规范平台列表.append(规范平台)
    if not 规范平台列表:
        return {}

    状态字典: dict[str, str] = {}
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        if 运行状态数据库.已配置运行状态数据库(配置):
            状态字典 = 运行状态数据库.读取运行状态命名空间(配置, 状态命名空间)
    except Exception as exc:
        logger.warning("网盘运行开关批量读取失败：错误类型=%s", type(exc).__name__)

    return {
        平台: _解析布尔值(
            状态字典.get(平台状态键[平台]),
            默认状态[平台],
        )
        for 平台 in 规范平台列表
    }


def 写入网盘开关(配置: Any, 平台: Any, 启用: bool) -> None:
    规范平台 = 规范化网盘平台(平台)
    if not 规范平台:
        raise ValueError("网盘平台无效")
    if not isinstance(启用, bool):
        raise ValueError("网盘开关参数无效")
    from 功能文件.管理功能.基础功能 import 运行状态数据库

    运行状态数据库.写入布尔运行状态值(
        配置,
        状态命名空间,
        平台状态键[规范平台],
        启用,
    )


def 网盘开关是否开启(配置: Any, 平台: Any) -> bool:
    return 读取网盘开关(配置, 平台)
