from __future__ import annotations

import asyncio
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能.权限工具 import (
    获取发送者QQ,
    获取群文件清理管理员QQ列表,
    是群文件清理管理员,
)
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    写入布尔运行状态值,
    读取运行状态命名空间,
)

默认状态 = {
    "番茄": True,
    "七猫": True,
    "书旗": True,
    "追书": True,
    "QQ阅读": True,
    "QQ浏览器": True,
    "得间": True,
    "点众": True,
    "盐言": True,
    "塔读": True,
    "百度": True,
    "小米": True,
    "宜搜": True,
    "米读": True,
    "猫眼": True,
    "酷我": True,
    "酷匠": True,
    "连城": True,
    "菠萝包": True,
    "晋江": True,
}
功能显示名 = {
    "番茄": "番茄小说",
    "七猫": "七猫小说",
    "书旗": "书旗小说",
    "追书": "追书小说",
    "QQ阅读": "QQ阅读",
    "QQ浏览器": "QQ浏览器小说",
    "得间": "得间小说",
    "点众": "点众小说",
    "盐言": "盐言小说",
    "塔读": "塔读小说",
    "百度": "百度小说",
    "小米": "小米小说",
    "宜搜": "宜搜小说",
    "米读": "米读小说",
    "猫眼": "猫眼小说",
    "酷我": "酷我小说",
    "酷匠": "酷匠小说",
    "连城": "连城小说",
    "菠萝包": "菠萝包小说",
    "晋江": "晋江小说",
}
开关命令配置 = {
    "开启番茄": ("番茄", True),
    "关闭番茄": ("番茄", False),
    "开启七猫": ("七猫", True),
    "关闭七猫": ("七猫", False),
    "开启书旗": ("书旗", True),
    "关闭书旗": ("书旗", False),
    "开启追书小说": ("追书", True),
    "关闭追书小说": ("追书", False),
    "开追书小说": ("追书", True),
    "关追书小说": ("追书", False),
    "开启QQ阅读": ("QQ阅读", True),
    "关闭QQ阅读": ("QQ阅读", False),
    "开启得间": ("得间", True),
    "关闭得间": ("得间", False),
    "开启点众": ("点众", True),
    "关闭点众": ("点众", False),
    "开启盐言": ("盐言", True),
    "关闭盐言": ("盐言", False),
    "开启塔读": ("塔读", True),
    "关闭塔读": ("塔读", False),
    "开启百度": ("百度", True),
    "关闭百度": ("百度", False),
    "开启百度小说": ("百度", True),
    "关闭百度小说": ("百度", False),
    "开百度小说": ("百度", True),
    "关百度小说": ("百度", False),
    "开启小米": ("小米", True),
    "关闭小米": ("小米", False),
    "开启小米小说": ("小米", True),
    "关闭小米小说": ("小米", False),
    "开小米小说": ("小米", True),
    "关小米小说": ("小米", False),
}
开关命令配置.update(
    {
        f"{前缀}{功能名}": (功能名, 是否开启)
        for 功能名 in 默认状态
        for 前缀, 是否开启 in (
            ("开", True),
            ("开启", True),
            ("关", False),
            ("关闭", False),
        )
    }
)
小说状态命令 = {"小说", "小说列表"}
小说总开关命令配置 = {
    "开小说": True,
    "开启小说": True,
    "关小说": False,
    "关闭小说": False,
}
测试模式命令配置 = {
    "开测试": True,
    "开启测试": True,
    "关测试": False,
    "关闭测试": False,
}
状态命名空间 = "novel_feature_switch"
小说总开关状态键 = "全部小说"
管理员测试模式状态键 = "管理员测试模式"
小说功能状态缓存秒数 = 2.0
_小说功能状态缓存: dict[int, tuple[float, dict[str, Any]]] = {}
_小说功能状态缓存锁 = threading.RLock()
_小说功能状态执行器: ThreadPoolExecutor | None = globals().get("_小说功能状态执行器")
_小说功能状态执行器锁 = threading.RLock()


def _复制小说功能状态(状态: dict[str, Any]) -> dict[str, Any]:
    return {
        "global_enabled": bool(状态.get("global_enabled", True)),
        "test_mode": bool(状态.get("test_mode", False)),
        "platforms": dict(状态.get("platforms") or 默认状态),
    }


def _清除小说功能状态缓存(配置: Any = None) -> None:
    with _小说功能状态缓存锁:
        if 配置 is None:
            _小说功能状态缓存.clear()
        else:
            _小说功能状态缓存.pop(id(配置), None)


def _获取小说功能状态执行器() -> ThreadPoolExecutor:
    global _小说功能状态执行器
    with _小说功能状态执行器锁:
        if _小说功能状态执行器 is None or getattr(_小说功能状态执行器, "_shutdown", False):
            _小说功能状态执行器 = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="mantou-novel-state",
            )
        return _小说功能状态执行器


def 关闭小说功能状态执行器() -> None:
    """插件停止时释放开关查询线程，避免热重载遗留工作线程。"""
    global _小说功能状态执行器
    with _小说功能状态执行器锁:
        执行器 = _小说功能状态执行器
        _小说功能状态执行器 = None
    if 执行器 is not None:
        执行器.shutdown(wait=False, cancel_futures=True)


async def _异步执行小说功能状态查询(函数: Any, *参数: Any) -> Any:
    """把数据库状态读取移出事件循环，避免等待 MySQL 时拖慢正文下载任务。"""
    循环 = asyncio.get_running_loop()
    return await 循环.run_in_executor(
        _获取小说功能状态执行器(),
        partial(函数, *参数),
    )


async def _异步是小说测试管理员(event: Any, 配置: Any) -> bool:
    """先在事件循环读取发送者，再在线程中读取可能涉及 MySQL 的白名单。"""
    发送者 = 获取发送者QQ(event)
    if not 发送者:
        return False
    try:
        管理员列表 = await _异步执行小说功能状态查询(
            获取群文件清理管理员QQ列表,
            配置,
        )
    except Exception as 异常:
        logger.debug("小说测试模式管理员读取失败：错误类型=%s", type(异常).__name__)
        return False
    return str(发送者) in set(管理员列表 or ())


def 处理小说功能开关指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    文本 = re.sub(r"(?i)qq(?=阅读)", "QQ", 文本)
    if (
        文本 not in 开关命令配置
        and 文本 not in 小说状态命令
        and 文本 not in 小说总开关命令配置
        and 文本 not in 测试模式命令配置
    ):
        return None
    if not 是群文件清理管理员(event, 配置):
        return None

    if 文本 in 小说状态命令:
        return 格式化小说功能状态(读取小说功能状态(配置), 小说总开关是否开启(配置))
    if 文本 in 小说总开关命令配置:
        是否开启 = 小说总开关命令配置[文本]
        try:
            写入布尔运行状态值(配置, 状态命名空间, 小说总开关状态键, 是否开启)
            _清除小说功能状态缓存(配置)
        except Exception as exc:
            logger.warning(
                f"全局小说功能开关写入数据库失败：是否开启={是否开启}, 错误={type(exc).__name__}"
            )
            return "小说功能开关失败，请稍后再试"
        状态文本 = "开启" if 是否开启 else "关闭"
        return f"全局小说功能已{状态文本}"
    if 文本 in 测试模式命令配置:
        是否开启 = 测试模式命令配置[文本]
        try:
            写入布尔运行状态值(配置, 状态命名空间, 管理员测试模式状态键, 是否开启)
            _清除小说功能状态缓存(配置)
        except Exception as exc:
            logger.warning(
                f"管理员测试模式写入数据库失败：是否开启={是否开启}, 错误={type(exc).__name__}"
            )
            return "测试模式切换失败，请稍后再试"
        状态文本 = "开启" if 是否开启 else "关闭"
        return f"管理员测试模式已{状态文本}"

    功能名, 是否开启 = 开关命令配置[文本]
    try:
        写入小说功能状态(配置, 功能名, 是否开启)
    except Exception as exc:
        logger.warning(
            f"小说功能开关写入数据库失败：功能={功能名}, 是否开启={是否开启}, 错误={type(exc).__name__}"
        )
        return f"{功能显示名[功能名]}开关失败，请稍后再试"
    状态文本 = "开启" if 是否开启 else "关闭"
    return f"{功能显示名[功能名]}已{状态文本}"


def 小说功能是否开启(功能名: str, 配置: Any = None) -> bool:
    return bool(读取小说功能控制台状态(配置)["platforms"].get(功能名, True))


def 小说总开关是否开启(配置: Any = None) -> bool:
    return bool(读取小说功能控制台状态(配置)["global_enabled"])


def 管理员测试模式是否开启(配置: Any = None) -> bool:
    return bool(读取小说功能控制台状态(配置)["test_mode"])


def 当前事件可使用小说功能(event: Any, 功能名: str, 配置: Any = None) -> bool:
    if not 小说总开关是否开启(配置):
        return False
    if 小说功能是否开启(功能名, 配置):
        return True
    return bool(是群文件清理管理员(event, 配置) and 管理员测试模式是否开启(配置))


async def 异步当前事件可使用小说功能(
    event: Any, 功能名: str, 配置: Any = None
) -> bool:
    状态 = await _异步执行小说功能状态查询(读取小说功能控制台状态, 配置)
    if not isinstance(状态, dict):
        状态 = {}
    if not bool(状态.get("global_enabled", True)):
        return False
    平台状态 = 状态.get("platforms") if isinstance(状态, dict) else {}
    if bool((平台状态 or {}).get(功能名, 默认状态.get(功能名, True))):
        return True
    return bool(状态.get("test_mode")) and await _异步是小说测试管理员(event, 配置)


async def 异步小说总开关是否开启(配置: Any = None) -> bool:
    return bool(
        await _异步执行小说功能状态查询(小说总开关是否开启, 配置)
    )


def 获取当前事件可用小说平台(event: Any, 配置: Any = None) -> set[str]:
    """返回当前事件可以使用的小说平台，供找书搜索一次性筛选。"""
    状态 = 读取小说功能控制台状态(配置)
    if not bool(状态.get("global_enabled")):
        return set()
    平台状态 = 状态.get("platforms")
    if not isinstance(平台状态, dict):
        平台状态 = {}
    # 管理员测试模式沿用单平台下载的既有例外：仅插件管理员可测试关闭平台。
    if bool(状态.get("test_mode")) and 是群文件清理管理员(event, 配置):
        return set(默认状态)
    return {
        功能名
        for 功能名, 默认值 in 默认状态.items()
        if bool(平台状态.get(功能名, 默认值))
    }


async def 异步获取当前事件可用小说平台(
    event: Any, 配置: Any = None
) -> set[str]:
    状态 = await _异步执行小说功能状态查询(读取小说功能控制台状态, 配置)
    if not isinstance(状态, dict):
        状态 = {}
    if not bool(状态.get("global_enabled", True)):
        return set()
    if bool(状态.get("test_mode")) and await _异步是小说测试管理员(event, 配置):
        return set(默认状态)
    平台状态 = 状态.get("platforms") if isinstance(状态, dict) else {}
    return {
        功能名
        for 功能名, 默认值 in 默认状态.items()
        if bool((平台状态 or {}).get(功能名, 默认值))
    }


def 获取小说功能关闭回复(功能名: str, 配置: Any = None) -> str:
    if not 小说总开关是否开启(配置):
        return "小说功能已关闭"
    return f"{功能显示名.get(功能名, 功能名)}功能已关闭"


def 格式化小说功能状态(状态: dict[str, bool], 总开关是否开启: bool) -> str:
    总开关状态文本 = "已开启" if 总开关是否开启 else "已关闭"
    行列表 = [f"📚 全局小说功能：{总开关状态文本}"]
    for 功能名 in 默认状态:
        状态文本 = "已开启" if 状态.get(功能名, True) else "已关闭"
        行列表.append(f"{功能显示名[功能名]}：{状态文本}")
    return "\n".join(行列表)


def 写入小说功能状态(配置: Any, 功能名: str, 是否开启: bool) -> None:
    if 功能名 not in 默认状态:
        raise RuntimeError(f"未知小说功能：{功能名}")
    写入布尔运行状态值(配置, 状态命名空间, 功能名, bool(是否开启))
    _清除小说功能状态缓存(配置)


def _运行状态转布尔(值: Any, 默认值: bool) -> bool:
    文本 = str(值 if 值 is not None else ("1" if 默认值 else "0")).strip().lower()
    if 文本 in {"1", "true", "yes", "on", "开启"}:
        return True
    if 文本 in {"0", "false", "no", "off", "关闭"}:
        return False
    return bool(默认值)


def 读取小说功能控制台状态(配置: Any = None) -> dict[str, Any]:
    """一次读取控制台所需的全局、测试模式和全部平台开关。"""
    结果: dict[str, Any] = {
        "global_enabled": True,
        "test_mode": False,
        "platforms": dict(默认状态),
    }
    if 配置 is None:
        return 结果
    配置键 = id(配置)
    当前时间 = time.monotonic()
    with _小说功能状态缓存锁:
        缓存 = _小说功能状态缓存.get(配置键)
        if 缓存 is not None and 当前时间 - 缓存[0] < 小说功能状态缓存秒数:
            return _复制小说功能状态(缓存[1])
    try:
        状态 = 读取运行状态命名空间(配置, 状态命名空间)
    except Exception as exc:
        logger.warning(
            f"小说功能开关批量读取数据库失败：错误={type(exc).__name__}"
        )
        with _小说功能状态缓存锁:
            _小说功能状态缓存[配置键] = (time.monotonic(), _复制小说功能状态(结果))
        return _复制小说功能状态(结果)
    if not isinstance(状态, dict):
        logger.warning("小说功能开关批量读取数据库返回格式异常：错误类型=TypeError")
        with _小说功能状态缓存锁:
            _小说功能状态缓存[配置键] = (time.monotonic(), _复制小说功能状态(结果))
        return _复制小说功能状态(结果)
    结果["global_enabled"] = _运行状态转布尔(
        状态.get(小说总开关状态键), True
    )
    结果["test_mode"] = _运行状态转布尔(
        状态.get(管理员测试模式状态键), False
    )
    平台状态 = 结果["platforms"]
    for 功能名, 默认值 in 默认状态.items():
        平台状态[功能名] = _运行状态转布尔(状态.get(功能名), 默认值)
    with _小说功能状态缓存锁:
        _小说功能状态缓存[配置键] = (time.monotonic(), _复制小说功能状态(结果))
    return _复制小说功能状态(结果)


def 读取小说功能状态(配置: Any = None) -> dict[str, bool]:
    return dict(读取小说功能控制台状态(配置)["platforms"])
