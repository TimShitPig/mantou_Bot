from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from 功能文件.管理功能.权限工具 import 是群文件清理管理员


下载缓存目录 = Path(__file__).resolve().parents[1] / "下载缓存"
功能开关状态文件 = 下载缓存目录 / "小说功能开关.json"
默认状态 = {"番茄": True, "七猫": True}
功能显示名 = {"番茄": "番茄小说", "七猫": "七猫小说"}
开关命令配置 = {
    "开启番茄": ("番茄", True),
    "关闭番茄": ("番茄", False),
    "开启七猫": ("七猫", True),
    "关闭七猫": ("七猫", False),
}


def 处理小说功能开关指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if 文本 not in 开关命令配置:
        return None
    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用小说功能开关"

    功能名, 是否开启 = 开关命令配置[文本]
    写入小说功能状态(功能名, 是否开启)
    状态文本 = "开启" if 是否开启 else "关闭"
    return f"{功能显示名[功能名]}已{状态文本}"


def 小说功能是否开启(功能名: str) -> bool:
    状态 = 读取小说功能状态()
    return bool(状态.get(功能名, True))


def 获取小说功能关闭回复(功能名: str) -> str:
    return f"{功能显示名.get(功能名, 功能名)}功能已关闭"


def 写入小说功能状态(功能名: str, 是否开启: bool) -> None:
    状态 = 读取小说功能状态()
    状态[功能名] = bool(是否开启)
    功能开关状态文件.parent.mkdir(parents=True, exist_ok=True)
    功能开关状态文件.write_text(json.dumps(状态, ensure_ascii=False, indent=2), encoding="utf-8")


def 读取小说功能状态() -> dict[str, bool]:
    状态 = dict(默认状态)
    if not 功能开关状态文件.exists():
        return 状态
    try:
        数据 = json.loads(功能开关状态文件.read_text(encoding="utf-8"))
    except Exception:
        return 状态
    if not isinstance(数据, dict):
        return 状态
    for 功能名 in 默认状态:
        if 功能名 in 数据:
            状态[功能名] = bool(数据[功能名])
    return 状态
