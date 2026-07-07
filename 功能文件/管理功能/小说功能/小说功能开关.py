from __future__ import annotations

from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取布尔运行状态值, 写入布尔运行状态值


默认状态 = {"番茄": True, "七猫": True, "书旗": True}
功能显示名 = {"番茄": "番茄小说", "七猫": "七猫小说", "书旗": "书旗小说"}
开关命令配置 = {
    "开启番茄": ("番茄", True),
    "关闭番茄": ("番茄", False),
    "开启七猫": ("七猫", True),
    "关闭七猫": ("七猫", False),
    "开启书旗": ("书旗", True),
    "关闭书旗": ("书旗", False),
}
状态命名空间 = "novel_feature_switch"


def 处理小说功能开关指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if 文本 not in 开关命令配置:
        return None
    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用小说功能开关"

    功能名, 是否开启 = 开关命令配置[文本]
    try:
        写入小说功能状态(配置, 功能名, 是否开启)
    except Exception as exc:
        logger.warning(f"小说功能开关写入数据库失败：feature={功能名}, enabled={是否开启}, error={exc}")
        return f"{功能显示名[功能名]}开关失败：{exc}"
    状态文本 = "开启" if 是否开启 else "关闭"
    return f"{功能显示名[功能名]}已{状态文本}"


def 小说功能是否开启(功能名: str, 配置: Any = None) -> bool:
    状态 = 读取小说功能状态(配置)
    return bool(状态.get(功能名, True))


def 获取小说功能关闭回复(功能名: str) -> str:
    return f"{功能显示名.get(功能名, 功能名)}功能已关闭"


def 写入小说功能状态(配置: Any, 功能名: str, 是否开启: bool) -> None:
    if 功能名 not in 默认状态:
        raise RuntimeError(f"未知小说功能：{功能名}")
    写入布尔运行状态值(配置, 状态命名空间, 功能名, bool(是否开启))


def 读取小说功能状态(配置: Any = None) -> dict[str, bool]:
    状态 = dict(默认状态)
    if 配置 is None:
        return 状态
    for 功能名, 默认值 in 默认状态.items():
        try:
            状态[功能名] = 读取布尔运行状态值(配置, 状态命名空间, 功能名, 默认值)
        except Exception as exc:
            logger.warning(f"小说功能开关读取数据库失败：feature={功能名}, error={exc}")
            状态[功能名] = 默认值
    return 状态
