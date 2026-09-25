from __future__ import annotations

import asyncio
import filecmp
import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any

日志 = logging.getLogger(__name__)
插件根目录 = Path(__file__).resolve().parents[3]
文件缓存目录 = 插件根目录 / "功能文件" / "文件缓存"
旧本地小说缓存目录 = 插件根目录 / "功能文件" / "下载缓存"
旧媒体缓存目录列表: tuple[Path, ...] = ()
旧临时缓存目录列表: tuple[Path, ...] = ()
if 插件根目录.parent.name.lower() == "plugins":
    # AstrBot 重装会替换插件目录，所有运行文件都放在稳定的数据目录。
    _AstrBot数据目录 = 插件根目录.parent.parent
    文件缓存目录 = _AstrBot数据目录 / "mantou_bot_file_cache"
    _旧稳定小说缓存目录 = _AstrBot数据目录 / "mantou_bot_download_cache"
    旧媒体缓存目录列表 = (
        _AstrBot数据目录 / "mantou_bot_media",
        Path(tempfile.gettempdir()) / "mantou_bot_media",
    )
    旧临时缓存目录列表 = (
        Path(tempfile.gettempdir()) / "mantou_bot_media",
        Path(tempfile.gettempdir()),
    )
else:
    _旧稳定小说缓存目录 = 旧本地小说缓存目录
    旧媒体缓存目录列表 = (Path(tempfile.gettempdir()) / "mantou_bot_media",)
    旧临时缓存目录列表 = (Path(tempfile.gettempdir()),)

小说缓存目录 = 文件缓存目录 / "小说缓存"
媒体缓存目录 = 文件缓存目录 / "媒体缓存"
临时缓存目录 = 文件缓存目录 / "临时缓存"
消息记录缓存目录 = 文件缓存目录 / "消息记录缓存"
其他缓存目录 = 文件缓存目录 / "其他缓存"


def 初始化文件缓存目录() -> None:
    for 目录 in (
        文件缓存目录,
        小说缓存目录,
        媒体缓存目录,
        临时缓存目录,
        消息记录缓存目录,
        其他缓存目录,
    ):
        目录.mkdir(parents=True, exist_ok=True)


def 创建临时缓存文件(前缀: str = "mantou-", 后缀: str = "") -> Path:
    临时缓存目录.mkdir(parents=True, exist_ok=True)
    文件描述符, 路径文本 = tempfile.mkstemp(
        prefix=str(前缀 or "mantou-"), suffix=str(后缀 or ""), dir=临时缓存目录
    )
    os.close(文件描述符)
    return Path(路径文本)


def 获取小说缓存目录列表() -> tuple[Path, ...]:
    """返回小说缓存目录与旧路径，兼容迁移过程中的上传续传任务。"""
    结果: list[Path] = [小说缓存目录]
    for 目录 in (_旧稳定小说缓存目录, 旧本地小说缓存目录):
        if 目录 not in 结果:
            结果.append(目录)
    return tuple(结果)
上传占用标记后缀 = ".uploading"
上传任务目录名 = ".upload_jobs"
上传任务状态 = {"primary_pending", "primary_done", "backup_pending"}
媒体缓存扩展名 = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".silk", ".dat"}
)
_进程活动缓存路径: set[str] = globals().get("_进程活动缓存路径") or set()


def 获取小说缓存占用标记路径(缓存路径: str | Path) -> Path:
    路径 = Path(缓存路径)
    return 路径.with_name(f"{路径.name}{上传占用标记后缀}")


def 获取上传任务目录(缓存目录: str | Path | None = None) -> Path:
    目录 = Path(缓存目录) if 缓存目录 is not None else 小说缓存目录
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


def 删除小说缓存文件(缓存路径: str | Path | None) -> bool:
    """删除缓存；主上传失败时保留文件并释放本次尝试的活动占用。"""
    if not 缓存路径:
        return False
    路径 = Path(缓存路径)
    任务 = 读取上传任务(路径)
    状态 = str(任务.get("state") or "") if 任务 else ""
    if 状态 in {"primary_pending", "backup_pending"}:
        # 失败任务由 .upload_jobs 持久化保护；释放当前尝试的占用，
        # 使同一进程中的重试/重载恢复任务不再被自己的 PID 永久跳过。
        解除小说缓存占用(路径)
        return False
    try:
        路径.unlink(missing_ok=True)
        完成上传任务(路径)
        解除小说缓存占用(路径)
        return True
    except OSError:
        return False


def 获取待续传上传任务(缓存目录: str | Path | None = None) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = []
    目录列表 = (
        (Path(缓存目录),)
        if 缓存目录 is not None
        else 获取小说缓存目录列表()
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


def 标记小说缓存正在使用(缓存路径: str | Path) -> Path:
    """标记小说缓存正被上传任务使用，避免插件重载时误删。"""
    路径 = Path(缓存路径)
    标记路径 = 获取小说缓存占用标记路径(路径)
    标记路径.parent.mkdir(parents=True, exist_ok=True)
    内容 = json.dumps(
        {"pid": os.getpid(), "created_at": int(time.time())},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    临时路径 = 标记路径.with_name(f"{标记路径.name}.{os.getpid()}.tmp")
    临时路径.write_text(内容, encoding="utf-8")
    临时路径.replace(标记路径)
    _进程活动缓存路径.add(str(路径.absolute()))
    return 标记路径


def 解除小说缓存占用(缓存路径: str | Path | None) -> None:
    if not 缓存路径:
        return
    路径 = Path(缓存路径)
    _进程活动缓存路径.discard(str(路径.absolute()))
    获取小说缓存占用标记路径(路径).unlink(missing_ok=True)


def 重置进程上传占用() -> None:
    """旧插件任务已停止后重置活动集合，保留任务文件用于续传。"""
    _进程活动缓存路径.clear()


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


def 小说缓存正在使用(缓存路径: str | Path) -> bool:
    路径 = Path(缓存路径)
    if str(路径.absolute()) in _进程活动缓存路径:
        return True
    标记路径 = 获取小说缓存占用标记路径(缓存路径)
    if not 标记路径.is_file():
        return False
    try:
        数据 = json.loads(标记路径.read_text(encoding="utf-8"))
        进程号 = int(数据.get("pid") or 0) if isinstance(数据, dict) else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    # 当前进程的旧标记可能来自插件重载前的失败任务；只有本次模块
    # 生命周期重新登记过的路径才算活动，避免阻塞续传恢复。
    if 进程号 == os.getpid():
        return False
    return _进程仍在运行(进程号)


def _占用标记仍由进程持有(缓存路径: Path) -> bool:
    标记路径 = 获取小说缓存占用标记路径(缓存路径)
    if not 标记路径.is_file():
        return False
    try:
        数据 = json.loads(标记路径.read_text(encoding="utf-8"))
        进程号 = int(数据.get("pid") or 0) if isinstance(数据, dict) else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    return _进程仍在运行(进程号)


def _无冲突缓存路径(目录: Path, 源路径: Path) -> Path:
    目录.mkdir(parents=True, exist_ok=True)
    目标 = 目录 / 源路径.name
    if not 目标.exists():
        return 目标
    for 序号 in range(1, 1000):
        候选 = 目录 / f"{源路径.stem}_迁移{序号}{源路径.suffix}"
        if not 候选.exists():
            return 候选
    raise RuntimeError("缓存目录中同名文件过多")


def _移动或合并重复缓存文件(源路径: Path, 目标目录: Path) -> bool:
    目标目录.mkdir(parents=True, exist_ok=True)
    同名目标 = 目标目录 / 源路径.name
    try:
        if 源路径.resolve() == 同名目标.resolve():
            return False
    except OSError:
        pass
    if 同名目标.is_file():
        try:
            if filecmp.cmp(源路径, 同名目标, shallow=False):
                源路径.unlink(missing_ok=True)
                return True
        except OSError:
            pass
    目标路径 = _无冲突缓存路径(目标目录, 源路径)
    shutil.move(str(源路径), str(目标路径))
    return True


def 迁移旧文件缓存() -> dict[str, int]:
    """把旧下载缓存、媒体副本、临时文件和状态文件移入分类目录。"""
    初始化文件缓存目录()
    结果 = {"novel": 0, "media": 0, "temporary": 0, "message": 0, "other": 0}

    for 旧目录 in 获取小说缓存目录列表()[1:]:
        if not 旧目录.is_dir():
            continue
        for 旧文件 in 旧目录.glob("*.txt"):
            if not 旧文件.is_file() or _占用标记仍由进程持有(旧文件):
                continue
            if 小说缓存正在使用(旧文件):
                continue
            旧任务路径 = 获取上传任务路径(旧文件)
            旧任务: dict[str, Any] | None = None
            if 旧任务路径.is_file():
                try:
                    数据 = json.loads(旧任务路径.read_text(encoding="utf-8"))
                    旧任务 = 数据 if isinstance(数据, dict) else None
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    旧任务 = None
            目标 = _无冲突缓存路径(小说缓存目录, 旧文件)
            try:
                shutil.move(str(旧文件), str(目标))
                if 旧任务 is not None:
                    旧任务["cache_path"] = str(目标.absolute())
                    _原子写入JSON(获取上传任务路径(目标), 旧任务)
                旧任务路径.unlink(missing_ok=True)
                获取小说缓存占用标记路径(旧文件).unlink(missing_ok=True)
                结果["novel"] += 1
            except OSError as 异常:
                日志.warning(
                    "文件缓存迁移失败：类型=小说缓存, 错误类型=%s",
                    type(异常).__name__,
                )

    已看过媒体目录: set[Path] = set()
    for 旧目录 in 旧媒体缓存目录列表:
        try:
            规范旧目录 = 旧目录.resolve()
        except OSError:
            规范旧目录 = 旧目录
        if 规范旧目录 in 已看过媒体目录 or not 旧目录.is_dir():
            continue
        已看过媒体目录.add(规范旧目录)
        for 旧文件 in 旧目录.iterdir():
            if not 旧文件.is_file():
                continue
            try:
                if _移动或合并重复缓存文件(旧文件, 媒体缓存目录):
                    结果["media"] += 1
            except (OSError, RuntimeError) as 异常:
                日志.warning(
                    "文件缓存迁移失败：类型=媒体缓存, 错误类型=%s",
                    type(异常).__name__,
                )

    临时源目录: set[Path] = set()
    for 旧目录 in 旧临时缓存目录列表:
        try:
            规范旧目录 = 旧目录.resolve()
        except OSError:
            规范旧目录 = 旧目录
        if 规范旧目录 in 临时源目录 or not 旧目录.is_dir():
            continue
        临时源目录.add(规范旧目录)
        for 旧文件 in 旧目录.glob("mantou-web-*"):
            if not 旧文件.is_file():
                continue
            try:
                if time.time() - 旧文件.stat().st_mtime < 600:
                    continue
                _移动或合并重复缓存文件(旧文件, 临时缓存目录)
                结果["temporary"] += 1
            except (OSError, RuntimeError) as 异常:
                日志.warning(
                    "文件缓存迁移失败：类型=临时文件, 错误类型=%s",
                    type(异常).__name__,
                )

    已看过旧缓存目录: set[Path] = set()
    for 旧目录 in 获取小说缓存目录列表()[1:]:
        try:
            规范旧目录 = 旧目录.resolve()
        except OSError:
            规范旧目录 = 旧目录
        if 规范旧目录 in 已看过旧缓存目录 or not 旧目录.is_dir():
            continue
        已看过旧缓存目录.add(规范旧目录)
        for 旧文件 in 旧目录.iterdir():
            if (
                not 旧文件.is_file()
                or 旧文件.suffix.lower() == ".txt"
                or 旧文件.name.endswith(上传占用标记后缀)
                or 旧文件.suffix.lower() == ".gitignore"
            ):
                continue
            if 旧文件.suffix.lower() == ".tmp":
                目标目录 = 临时缓存目录
                类型 = "temporary"
            elif 旧文件.name.casefold() == "消息记录缓存.json".casefold():
                目标目录 = 消息记录缓存目录
                类型 = "message"
            elif 旧文件.suffix.lower() in 媒体缓存扩展名:
                目标目录 = 媒体缓存目录
                类型 = "media"
            else:
                目标目录 = 其他缓存目录
                类型 = "other"
            try:
                if _移动或合并重复缓存文件(旧文件, 目标目录):
                    结果[类型] += 1
            except (OSError, RuntimeError) as 异常:
                日志.warning(
                    "文件缓存迁移失败：类型=%s，错误类型=%s",
                    类型,
                    type(异常).__name__,
                )
    return 结果


def 清理过期临时文件缓存(保留秒数: int = 24 * 60 * 60) -> int:
    """清理重载或进程中断遗留的临时上传/转码文件。"""
    if not 临时缓存目录.is_dir():
        return 0
    截止时间 = time.time() - max(60, int(保留秒数 or 0))
    已清理 = 0
    for 路径 in 临时缓存目录.iterdir():
        if not 路径.is_file():
            continue
        try:
            if 路径.stat().st_mtime >= 截止时间:
                continue
            路径.unlink(missing_ok=True)
            已清理 += 1
        except OSError:
            continue
    return 已清理


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
        if not 缓存路径.exists() and not 小说缓存正在使用(缓存路径):
            try:
                标记路径.unlink(missing_ok=True)
            except OSError:
                continue


def 清理残留小说缓存(缓存目录: str | Path | None = None) -> int:
    """删除上次运行遗留的小说 TXT，跳过当前仍在上传的缓存。"""
    已清理 = 0
    目录列表 = (
        (Path(缓存目录),)
        if 缓存目录 is not None
        else 获取小说缓存目录列表()
    )
    for 目录 in 目录列表:
        if not 目录.is_dir():
            continue
        for 路径 in 目录.glob("*.txt"):
            if not 路径.is_file():
                continue
            if 上传任务待续传(路径) or 小说缓存正在使用(路径):
                continue
            if 删除小说缓存文件(路径):
                已清理 += 1
        _清理孤立占用标记(目录)
    return 已清理


def 清理过期小说缓存(
    缓存目录: str | Path | None = None,
    当前日期: date | datetime | None = None,
) -> int:
    """删除本地日期早于前一天的小说 TXT，保留今天和昨天。"""
    日期边界 = _转换为本地日期(当前日期) - timedelta(days=1)
    已清理 = 0
    目录列表 = (
        (Path(缓存目录),)
        if 缓存目录 is not None
        else 获取小说缓存目录列表()
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
            if 上传任务待续传(路径) or 小说缓存正在使用(路径):
                continue
            if not 删除小说缓存文件(路径):
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


async def 每日文件缓存任务(
    缓存目录: str | Path | None = None,
    清理完成回调: Any = None,
) -> None:
    """持续等待本地每日零点并清理前一日及更早的小说 TXT。"""
    while True:
        await asyncio.sleep(计算下次本地零点等待秒数())
        try:
            已清理 = 清理过期小说缓存(缓存目录)
            if 清理完成回调 is not None:
                清理完成回调(已清理)
        except asyncio.CancelledError:
            raise
        except Exception as 异常:
            日志.warning(
                "每日零点清理小说缓存异常：错误类型=%s",
                type(异常).__name__,
            )
            continue


def 启动每日文件缓存任务(
    缓存目录: str | Path | None = None,
    清理完成回调: Any = None,
) -> asyncio.Task[Any]:
    return asyncio.create_task(
        每日文件缓存任务(缓存目录, 清理完成回调),
        name="小说缓存每日清理",
    )


async def 停止每日文件缓存任务(任务: asyncio.Task[Any] | None) -> None:
    if 任务 is None or 任务.done():
        return
    任务.cancel()
    await asyncio.gather(任务, return_exceptions=True)
