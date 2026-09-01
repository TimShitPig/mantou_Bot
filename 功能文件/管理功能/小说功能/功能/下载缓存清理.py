from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any

日志 = logging.getLogger(__name__)
下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
插件根目录 = Path(__file__).resolve().parents[4]
旧下载缓存目录 = 插件根目录 / "功能文件" / "下载缓存"
if 插件根目录.parent.name.lower() == "plugins":
    # AstrBot 重装插件会替换插件目录，上传中的 TXT 必须放在稳定的数据目录。
    下载缓存目录 = 插件根目录.parent.parent / "mantou_bot_download_cache"


def 获取下载缓存目录列表() -> tuple[Path, ...]:
    """返回当前缓存目录和旧目录，兼容重装前遗留的续传任务。"""
    if 旧下载缓存目录 == 下载缓存目录:
        return (下载缓存目录,)
    return (下载缓存目录, 旧下载缓存目录)
上传占用标记后缀 = ".uploading"
上传任务目录名 = ".upload_jobs"
上传任务状态 = {"primary_pending", "primary_done", "backup_pending"}


def 获取下载缓存占用标记路径(缓存路径: str | Path) -> Path:
    路径 = Path(缓存路径)
    return 路径.with_name(f"{路径.name}{上传占用标记后缀}")


def 获取上传任务目录(缓存目录: str | Path | None = None) -> Path:
    目录 = Path(缓存目录) if 缓存目录 is not None else 下载缓存目录
    return 目录 / 上传任务目录名


def 获取上传任务路径(缓存路径: str | Path) -> Path:
    路径 = Path(缓存路径)
    标识 = str(路径.absolute()).encode("utf-8", errors="replace")
    文件名 = hashlib.sha256(标识).hexdigest() + ".json"
    return 获取上传任务目录(路径.parent) / 文件名


def _原子写入JSON(路径: Path, 数据: dict[str, Any]) -> None:
    路径.parent.mkdir(parents=True, exist_ok=True)
    临时路径 = 路径.with_name(f"{路径.name}.{os.getpid()}.tmp")
    临时路径.write_text(
        json.dumps(数据, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    临时路径.replace(路径)


def 读取上传任务(缓存路径: str | Path) -> dict[str, Any] | None:
    任务路径 = 获取上传任务路径(缓存路径)
    if not 任务路径.is_file():
        return None
    try:
        数据 = json.loads(任务路径.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return 数据 if isinstance(数据, dict) else None


def 登记上传任务(
    缓存路径: str | Path,
    文件名: str,
    网盘名称: str = "",
    *,
    账号索引: dict[str, int] | None = None,
    待处理平台: list[str] | tuple[str, ...] | None = None,
) -> Path:
    路径 = Path(缓存路径)
    任务路径 = 获取上传任务路径(路径)
    旧任务 = 读取上传任务(路径) or {}
    当前时间 = int(time.time())
    数据 = {
        "version": 1,
        "cache_path": str(路径.absolute()),
        "file_name": str(文件名 or 路径.name),
        "provider": str(网盘名称 or 旧任务.get("provider") or ""),
        "state": str(旧任务.get("state") or "primary_pending"),
        "created_at": int(旧任务.get("created_at") or 当前时间),
        "updated_at": 当前时间,
        "retry_count": int(旧任务.get("retry_count") or 0),
        "last_error": str(旧任务.get("last_error") or ""),
    }
    if isinstance(待处理平台, (list, tuple)):
        数据["pending_platforms"] = [
            str(平台).strip()
            for 平台 in 待处理平台
            if str(平台 or "").strip()
        ]
    elif isinstance(旧任务.get("pending_platforms"), list):
        数据["pending_platforms"] = [
            str(平台).strip()
            for 平台 in 旧任务["pending_platforms"]
            if str(平台 or "").strip()
        ]
    if isinstance(旧任务.get("completed_platforms"), list):
        数据["completed_platforms"] = [
            str(平台).strip()
            for 平台 in 旧任务["completed_platforms"]
            if str(平台 or "").strip()
        ]
    if isinstance(账号索引, dict):
        数据["account_indices"] = {
            str(平台): max(1, int(序号))
            for 平台, 序号 in 账号索引.items()
            if str(平台) and str(序号).lstrip("+").isdigit()
        }
    elif isinstance(旧任务.get("account_indices"), dict):
        数据["account_indices"] = dict(旧任务["account_indices"])
    if 数据["state"] not in 上传任务状态:
        数据["state"] = "primary_pending"
    _原子写入JSON(任务路径, 数据)
    return 任务路径


def 更新上传任务(
    缓存路径: str | Path, 状态: str | None = None, **字段: Any
) -> Path | None:
    任务路径 = 获取上传任务路径(缓存路径)
    数据 = 读取上传任务(缓存路径)
    if 数据 is None:
        return None
    if 状态 is not None:
        数据["state"] = str(状态)
    数据.update(字段)
    数据["updated_at"] = int(time.time())
    _原子写入JSON(任务路径, 数据)
    return 任务路径


def 上传任务待续传(缓存路径: str | Path) -> bool:
    数据 = 读取上传任务(缓存路径)
    return bool(数据 and str(数据.get("state") or "") in 上传任务状态)


def 完成上传任务(缓存路径: str | Path) -> None:
    获取上传任务路径(缓存路径).unlink(missing_ok=True)


def 删除下载缓存文件(缓存路径: str | Path | None) -> bool:
    """删除缓存；主上传尚未成功时保留文件，等待下次重载恢复。"""
    if not 缓存路径:
        return False
    路径 = Path(缓存路径)
    任务 = 读取上传任务(路径)
    状态 = str(任务.get("state") or "") if 任务 else ""
    if 状态 in {"primary_pending", "backup_pending"}:
        return False
    try:
        路径.unlink(missing_ok=True)
        完成上传任务(路径)
        解除下载缓存占用(路径)
        return True
    except OSError:
        return False


def 获取待续传上传任务(缓存目录: str | Path | None = None) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = []
    目录列表 = (
        (Path(缓存目录),)
        if 缓存目录 is not None
        else 获取下载缓存目录列表()
    )
    for 当前目录 in 目录列表:
        任务目录 = 获取上传任务目录(当前目录)
        if not 任务目录.is_dir():
            continue
        for 任务路径 in sorted(任务目录.glob("*.json")):
            try:
                数据 = json.loads(任务路径.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if (
                not isinstance(数据, dict)
                or str(数据.get("state") or "") not in 上传任务状态
            ):
                continue
            缓存路径 = Path(str(数据.get("cache_path") or ""))
            if 缓存路径.is_file():
                结果.append(数据)
            else:
                任务路径.unlink(missing_ok=True)
    return 结果


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


def _转换为本地日期(值: date | datetime | None = None) -> date:
    if isinstance(值, datetime):
        return 值.date()
    if isinstance(值, date):
        return 值
    return datetime.now().date()


def _获取文件本地日期(路径: Path) -> date | None:
    try:
        return datetime.fromtimestamp(路径.stat().st_mtime).date()
    except OSError:
        return None


def _清理孤立占用标记(目录: Path) -> None:
    for 标记路径 in 目录.glob(f"*.txt{上传占用标记后缀}"):
        缓存路径 = 标记路径.with_name(标记路径.name.removesuffix(上传占用标记后缀))
        if not 缓存路径.exists() and not 下载缓存正在使用(缓存路径):
            try:
                标记路径.unlink(missing_ok=True)
            except OSError:
                continue


def 清理残留下载缓存(缓存目录: str | Path | None = None) -> int:
    """删除上次运行遗留的小说 TXT，跳过当前仍在上传的缓存。"""
    已清理 = 0
    目录列表 = (
        (Path(缓存目录),)
        if 缓存目录 is not None
        else 获取下载缓存目录列表()
    )
    for 目录 in 目录列表:
        if not 目录.is_dir():
            continue
        for 路径 in 目录.glob("*.txt"):
            if not 路径.is_file():
                continue
            if 上传任务待续传(路径) or 下载缓存正在使用(路径):
                continue
            if 删除下载缓存文件(路径):
                已清理 += 1
        _清理孤立占用标记(目录)
    return 已清理


def 清理过期下载缓存(
    缓存目录: str | Path | None = None,
    当前日期: date | datetime | None = None,
) -> int:
    """删除本地日期早于前一天的小说 TXT，保留今天和昨天。"""
    日期边界 = _转换为本地日期(当前日期) - timedelta(days=1)
    已清理 = 0
    目录列表 = (
        (Path(缓存目录),)
        if 缓存目录 is not None
        else 获取下载缓存目录列表()
    )
    for 目录 in 目录列表:
        if not 目录.is_dir():
            continue
        for 路径 in 目录.glob("*.txt"):
            if not 路径.is_file():
                continue
            文件日期 = _获取文件本地日期(路径)
            if 文件日期 is None or 文件日期 >= 日期边界:
                continue
            if 上传任务待续传(路径) or 下载缓存正在使用(路径):
                continue
            if not 删除下载缓存文件(路径):
                continue
            已清理 += 1
        _清理孤立占用标记(目录)
    return 已清理


def 计算下次本地零点等待秒数(现在: datetime | None = None) -> float:
    """计算距离下一次本地零点的秒数，兼容测试传入的时间。"""
    当前时间 = 现在 or datetime.now().astimezone()
    if 当前时间.tzinfo is None:
        当前时间 = 当前时间.astimezone()
    下一天 = 当前时间.date() + timedelta(days=1)
    下次零点 = datetime.combine(
        下一天,
        datetime_time.min,
        tzinfo=当前时间.tzinfo,
    )
    return max((下次零点 - 当前时间).total_seconds(), 0.1)


async def 每日下载缓存清理任务(
    缓存目录: str | Path | None = None,
    清理完成回调: Any = None,
) -> None:
    """持续等待本地每日零点并清理前一日及更早的小说 TXT。"""
    while True:
        await asyncio.sleep(计算下次本地零点等待秒数())
        try:
            已清理 = 清理过期下载缓存(缓存目录)
            if 清理完成回调 is not None:
                清理完成回调(已清理)
        except asyncio.CancelledError:
            raise
        except Exception as 异常:
            日志.warning(
                "每日零点清理小说下载缓存异常：错误类型=%s",
                type(异常).__name__,
            )
            continue


def 启动每日下载缓存清理任务(
    缓存目录: str | Path | None = None,
    清理完成回调: Any = None,
) -> asyncio.Task[Any]:
    return asyncio.create_task(
        每日下载缓存清理任务(缓存目录, 清理完成回调),
        name="小说缓存每日清理",
    )


async def 停止每日下载缓存清理任务(任务: asyncio.Task[Any] | None) -> None:
    if 任务 is None or 任务.done():
        return
    任务.cancel()
    await asyncio.gather(任务, return_exceptions=True)
