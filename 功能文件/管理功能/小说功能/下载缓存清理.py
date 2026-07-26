from __future__ import annotations

from pathlib import Path
from typing import Any


下载缓存目录 = Path(__file__).resolve().parents[2] / "下载缓存"


def 清理残留下载缓存(缓存目录: str | Path | None = None) -> int:
    """删除下载缓存目录中上次运行遗留的小说 txt 文件。"""
    目录 = Path(缓存目录) if 缓存目录 is not None else 下载缓存目录
    if not 目录.is_dir():
        return 0
    已清理 = 0
    for 路径 in 目录.glob("*.txt"):
        if not 路径.is_file():
            continue
        try:
            路径.unlink()
            已清理 += 1
        except OSError:
            continue
    return 已清理
