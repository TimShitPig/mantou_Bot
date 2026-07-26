from __future__ import annotations

import json
import os
import time
from pathlib import Path


下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
上传占用标记后缀 = ".uploading"


def 获取下载缓存占用标记路径(缓存路径: str | Path) -> Path:
    路径 = Path(缓存路径)
    return 路径.with_name(f"{路径.name}{上传占用标记后缀}")


def 标记下载缓存正在使用(缓存路径: str | Path) -> Path:
    """标记下载缓存正被上传任务使用，避免插件重载时误删。"""
    路径 = Path(缓存路径)
    标记路径 = 获取下载缓存占用标记路径(路径)
    标记路径.parent.mkdir(parents=True, exist_ok=True)
    内容 = json.dumps(
        {"pid": os.getpid(), "created_at": int(time.time())},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    临时路径 = 标记路径.with_name(f"{标记路径.name}.{os.getpid()}.tmp")
    临时路径.write_text(内容, encoding="utf-8")
    临时路径.replace(标记路径)
    return 标记路径


def 解除下载缓存占用(缓存路径: str | Path | None) -> None:
    if not 缓存路径:
        return
    获取下载缓存占用标记路径(缓存路径).unlink(missing_ok=True)


def _进程仍在运行(进程号: int) -> bool:
    if 进程号 <= 0:
        return False
    if 进程号 == os.getpid():
        return True
    try:
        os.kill(进程号, 0)
    except OSError:
        return False
    return True


def 下载缓存正在使用(缓存路径: str | Path) -> bool:
    标记路径 = 获取下载缓存占用标记路径(缓存路径)
    if not 标记路径.is_file():
        return False
    try:
        数据 = json.loads(标记路径.read_text(encoding="utf-8"))
        进程号 = int(数据.get("pid") or 0) if isinstance(数据, dict) else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    return _进程仍在运行(进程号)


def 清理残留下载缓存(缓存目录: str | Path | None = None) -> int:
    """删除上次运行遗留的小说 TXT，跳过当前仍在上传的缓存。"""
    目录 = Path(缓存目录) if 缓存目录 is not None else 下载缓存目录
    if not 目录.is_dir():
        return 0
    已清理 = 0
    for 路径 in 目录.glob("*.txt"):
        if not 路径.is_file():
            continue
        标记路径 = 获取下载缓存占用标记路径(路径)
        if 下载缓存正在使用(路径):
            continue
        try:
            路径.unlink()
            标记路径.unlink(missing_ok=True)
            已清理 += 1
        except OSError:
            continue
    for 标记路径 in 目录.glob(f"*.txt{上传占用标记后缀}"):
        缓存路径 = 标记路径.with_name(标记路径.name.removesuffix(上传占用标记后缀))
        if not 缓存路径.exists() and not 下载缓存正在使用(缓存路径):
            标记路径.unlink(missing_ok=True)
    return 已清理
