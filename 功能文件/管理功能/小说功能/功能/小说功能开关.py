from __future__ import annotations

import re
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取布尔运行状态值, 写入布尔运行状态值


默认状态 = {"番茄": True, "七猫": True, "书旗": True, "QQ阅读": True, "QQ浏览器": True, "得间": True, "点众": True, "知乎": True, "塔读": True}
功能显示名 = {"番茄": "番茄小说", "七猫": "七猫小说", "书旗": "书旗小说", "QQ阅读": "QQ阅读", "QQ浏览器": "QQ浏览器小说", "得间": "得间小说", "点众": "点众小说", "知乎": "知乎", "塔读": "塔读小说"}
开关命令配置 = {
    "开启番茄": ("番茄", True),
    "关闭番茄": ("番茄", False),
    "开启七猫": ("七猫", True),
    "关闭七猫": ("七猫", False),
    "开启书旗": ("书旗", True),
    "关闭书旗": ("书旗", False),
    "开启QQ阅读": ("QQ阅读", True),
    "关闭QQ阅读": ("QQ阅读", False),
    "开启得间": ("得间", True),
    "关闭得间": ("得间", False),
    "开启点众": ("点众", True),
    "关闭点众": ("点众", False),
    "开启知乎": ("知乎", True),
    "关闭知乎": ("知乎", False),
    "开启塔读": ("塔读", True),
    "关闭塔读": ("塔读", False),
}
开关命令配置.update(
    {
        f"{前缀}{功能名}": (功能名, 是否开启)
        for 功能名 in 默认状态
        for 前缀, 是否开启 in (("开", True), ("关", False))
    }
)
小说状态命令 = {"小说", "小说列表"}
测试模式命令配置 = {
    "开测试": True,
    "开启测试": True,
    "关测试": False,
    "关闭测试": False,
}
状态命名空间 = "novel_feature_switch"
管理员测试模式状态键 = "管理员测试模式"


def 处理小说功能开关指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    文本 = re.sub(r"(?i)qq(?=阅读)", "QQ", 文本)
    if 文本 not in 开关命令配置 and 文本 not in 小说状态命令 and 文本 not in 测试模式命令配置:
        return None
    if not 是群文件清理管理员(event, 配置):
        return None

    if 文本 in 小说状态命令:
        return 格式化小说功能状态(读取小说功能状态(配置))
    if 文本 in 测试模式命令配置:
        是否开启 = 测试模式命令配置[文本]
        try:
            写入布尔运行状态值(配置, 状态命名空间, 管理员测试模式状态键, 是否开启)
        except Exception as exc:
            logger.warning(f"管理员测试模式写入数据库失败：enabled={是否开启}, error={exc}")
            return "测试模式切换失败，请稍后再试"
        状态文本 = "开启" if 是否开启 else "关闭"
        return f"管理员测试模式已{状态文本}"

    功能名, 是否开启 = 开关命令配置[文本]
    try:
        写入小说功能状态(配置, 功能名, 是否开启)
    except Exception as exc:
        logger.warning(f"小说功能开关写入数据库失败：feature={功能名}, enabled={是否开启}, error={exc}")
        return f"{功能显示名[功能名]}开关失败，请稍后再试"
    状态文本 = "开启" if 是否开启 else "关闭"
    return f"{功能显示名[功能名]}已{状态文本}"


def 小说功能是否开启(功能名: str, 配置: Any = None) -> bool:
    状态 = 读取小说功能状态(配置)
    return bool(状态.get(功能名, True))


def 管理员测试模式是否开启(配置: Any = None) -> bool:
    try:
        return 读取布尔运行状态值(配置, 状态命名空间, 管理员测试模式状态键, False)
    except Exception as exc:
        logger.warning(f"管理员测试模式读取数据库失败：error={exc}")
        return False


def 当前事件可使用小说功能(event: Any, 功能名: str, 配置: Any = None) -> bool:
    if 小说功能是否开启(功能名, 配置):
        return True
    return bool(
        是群文件清理管理员(event, 配置)
        and 管理员测试模式是否开启(配置)
    )


def 获取小说功能关闭回复(功能名: str) -> str:
    return f"{功能显示名.get(功能名, 功能名)}功能已关闭"


def 格式化小说功能状态(状态: dict[str, bool]) -> str:
    行列表 = ["📚 本群小说功能列表"]
    for 功能名 in 默认状态:
        状态文本 = "已开启" if 状态.get(功能名, True) else "已关闭"
        行列表.append(f"{功能显示名[功能名]}：{状态文本}")
    return "\n".join(行列表)


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
