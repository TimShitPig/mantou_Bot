from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 检查运行状态数据库

上次系统CPU采样: tuple[int, int] | None = None
框架版本缓存: str | None = None


def 处理状态指令(
    event: Any, 命令文本: str, 配置: Any, 插件版本: str = ""
) -> str | None:
    if str(命令文本 or "").strip() != "状态":
        return None
    if not 是群文件清理管理员(event, 配置):
        return None
    return 生成状态回复(event, 配置, 插件版本)


def 生成状态回复(event: Any, 配置: Any, 插件版本: str = "") -> str:
    del event, 插件版本
    数据库状态 = 检查运行状态数据库(配置)
    return "\n\n".join(
        [
            f"系统位数：{获取系统位数()}",
            f"CPU占用：{格式化系统CPU()}",
            f"物理内存：{格式化系统内存()}",
            f"磁盘空间：{格式化磁盘信息()}",
            f"系统进程：{格式化系统进程数()}",
            f"操作系统：{获取操作系统名称()}",
            f"框架版本：{获取框架版本()}",
            f"数据库：{数据库状态}",
            f"运行时间：{格式化系统运行时间()}",
            f"当前时间：{datetime.now().strftime('%Y年%m月%d日%H时%M分%S秒')}",
        ]
    )


def 获取系统位数() -> str:
    架构 = f"{platform.architecture()[0]} {platform.machine()}"
    if "64" in 架构:
        return "64位"
    if "32" in 架构:
        return "32位"
    return "未知"


def 获取操作系统名称() -> str:
    if platform.system().lower() == "linux":
        try:
            for 行 in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
                if not 行.startswith("PRETTY_NAME="):
                    continue
                名称 = 行.split("=", 1)[1].strip().strip('"')
                if 名称:
                    return 名称
        except Exception:
            pass
    return platform.platform() or "未知"


def 获取框架版本() -> str:
    global 框架版本缓存

    if 框架版本缓存 is not None:
        return 框架版本缓存

    for 环境变量 in ("ASTRBOT_GIT_SHA", "ASTRBOT_VERSION", "GIT_COMMIT"):
        值 = str(os.environ.get(环境变量) or "").strip()
        if 值:
            框架版本缓存 = 值[:40]
            return 框架版本缓存

    try:
        import astrbot
    except Exception:
        框架版本缓存 = "未知"
        return 框架版本缓存

    模块路径 = getattr(astrbot, "__file__", None)
    if 模块路径:
        try:
            起始目录 = Path(模块路径).resolve().parent
            已检查目录: set[Path] = set()
            for 目录 in (起始目录, *起始目录.parents):
                if 目录 in 已检查目录:
                    continue
                已检查目录.add(目录)
                短提交 = 读取Git短提交(目录)
                if 短提交:
                    框架版本缓存 = 短提交
                    return 框架版本缓存
        except Exception:
            pass

    for 字段名 in ("__version__", "VERSION", "version"):
        值 = str(getattr(astrbot, 字段名, "") or "").strip()
        if 值:
            框架版本缓存 = 值
            return 框架版本缓存

    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            值 = str(version("astrbot") or "").strip()
        except PackageNotFoundError:
            值 = ""
        if 值:
            框架版本缓存 = 值
            return 框架版本缓存
    except Exception:
        pass

    框架版本缓存 = "未知"
    return 框架版本缓存


def 读取Git短提交(目录: Path) -> str | None:
    if not (目录 / ".git").exists():
        return None
    try:
        结果 = subprocess.run(
            ["git", "-C", str(目录), "rev-parse", "--short=8", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            timeout=1,
        )
    except Exception:
        return None
    短提交 = 结果.stdout.strip()
    return 短提交 if 结果.returncode == 0 and 短提交 else None


def 格式化磁盘信息() -> str:
    try:
        根目录 = Path(__file__).resolve().anchor or Path.cwd()
        用量 = shutil.disk_usage(根目录)
    except Exception:
        try:
            用量 = shutil.disk_usage(Path.cwd())
        except Exception:
            return "未知"
    return f"{格式化容量(用量.used)}/{格式化容量(用量.total)}"


def 格式化系统内存() -> str:
    内存 = 读取系统内存()
    if 内存 is None:
        return "未知"
    已用, 总计 = 内存
    return f"{格式化容量(已用)}/{格式化容量(总计)}"


def 格式化系统CPU() -> str:
    global 上次系统CPU采样

    当前采样 = 读取系统CPU计数器()
    if 当前采样 is None:
        return "未知"
    if 上次系统CPU采样 is None:
        上次系统CPU采样 = 当前采样
        return "0.0%"
    上次空闲, 上次总计 = 上次系统CPU采样
    当前空闲, 当前总计 = 当前采样
    上次系统CPU采样 = 当前采样
    总增量 = 当前总计 - 上次总计
    空闲增量 = 当前空闲 - 上次空闲
    if 总增量 <= 0:
        return "0.0%"
    百分比 = max(0.0, min(100.0, (1 - 空闲增量 / 总增量) * 100))
    return f"{百分比:.1f}%"


def 格式化系统进程数() -> str:
    数量 = 读取系统进程数()
    return f"{数量}个" if 数量 is not None else "未知"


def 读取系统进程数() -> int | None:
    系统名 = platform.system().lower()
    if 系统名 == "linux":
        try:
            return sum(1 for 名称 in os.listdir("/proc") if 名称.isdigit())
        except Exception:
            return None
    if 系统名 == "windows":
        try:
            结果 = subprocess.run(
                ["tasklist", "/NH", "/FO", "CSV"],
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
            )
            if 结果.returncode == 0:
                return sum(
                    1 for 行 in 结果.stdout.splitlines() if 行.lstrip().startswith('"')
                )
        except Exception:
            return None
    return None


def 格式化系统运行时间() -> str:
    秒数 = 读取系统运行秒数()
    if 秒数 is None:
        return "未知"
    return 格式化时长(int(秒数))


def 读取系统运行秒数() -> float | None:
    系统名 = platform.system().lower()
    if 系统名 == "windows":
        return 读取Windows系统运行秒数()
    if 系统名 == "linux":
        return 读取Linux系统运行秒数()
    return None


def 读取Linux系统运行秒数() -> float | None:
    try:
        内容 = Path("/proc/uptime").read_text(encoding="utf-8").strip().split()
        return float(内容[0]) if 内容 else None
    except Exception:
        return None


def 读取Windows系统运行秒数() -> float | None:
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        毫秒 = kernel32.GetTickCount64()
        return float(毫秒) / 1000 if 毫秒 >= 0 else None
    except Exception:
        return None


def 读取系统内存() -> tuple[int, int] | None:
    系统名 = platform.system().lower()
    if 系统名 == "windows":
        return 读取Windows系统内存()
    if 系统名 == "linux":
        return 读取Linux系统内存()
    return None


def 读取Linux系统内存() -> tuple[int, int] | None:
    try:
        数据: dict[str, int] = {}
        for 行 in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ":" not in 行:
                continue
            键, 值 = 行.split(":", 1)
            项目 = 值.split()
            if 项目:
                数据[键] = int(项目[0]) * 1024
        总计 = 数据.get("MemTotal")
        可用 = 数据.get("MemAvailable")
        if 总计 and 可用 is not None:
            return max(0, 总计 - 可用), 总计
    except Exception:
        return None
    return None


def 读取Windows系统内存() -> tuple[int, int] | None:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        状态 = MEMORYSTATUSEX()
        状态.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(状态)):
            总计 = int(状态.ullTotalPhys)
            可用 = int(状态.ullAvailPhys)
            return max(0, 总计 - 可用), 总计
    except Exception:
        return None
    return None


def 读取系统CPU计数器() -> tuple[int, int] | None:
    系统名 = platform.system().lower()
    if 系统名 == "windows":
        return 读取Windows系统CPU计数器()
    if 系统名 == "linux":
        return 读取Linux系统CPU计数器()
    return None


def 读取Linux系统CPU计数器() -> tuple[int, int] | None:
    try:
        第一行 = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
        项目 = 第一行.split()
        if not 项目 or 项目[0] != "cpu":
            return None
        数值 = [int(值) for 值 in 项目[1:]]
        if len(数值) < 4:
            return None
        空闲 = 数值[3] + (数值[4] if len(数值) > 4 else 0)
        return 空闲, sum(数值)
    except Exception:
        return None


def 读取Windows系统CPU计数器() -> tuple[int, int] | None:
    try:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD),
            ]

        空闲 = FILETIME()
        内核 = FILETIME()
        用户 = FILETIME()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetSystemTimes.argtypes = [
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        kernel32.GetSystemTimes.restype = wintypes.BOOL
        if not kernel32.GetSystemTimes(
            ctypes.byref(空闲), ctypes.byref(内核), ctypes.byref(用户)
        ):
            return None

        def 转整数(值: FILETIME) -> int:
            return (int(值.dwHighDateTime) << 32) + int(值.dwLowDateTime)

        空闲值 = 转整数(空闲)
        总计值 = 转整数(内核) + 转整数(用户)
        return 空闲值, 总计值
    except Exception:
        return None


def 格式化容量(字节数: int) -> str:
    数值 = max(0, int(字节数)) / (1024**3)
    if 数值 >= 1:
        return f"{数值:.1f}G"
    数值 *= 1024
    return f"{数值:.1f}M"


def 格式化时长(秒数: int) -> str:
    秒数 = max(0, int(秒数))
    天, 余数 = divmod(秒数, 86400)
    小时, 余数 = divmod(余数, 3600)
    分钟, 秒 = divmod(余数, 60)
    项目 = []
    if 天:
        项目.append(f"{天}天")
    if 小时 or 项目:
        项目.append(f"{小时}小时")
    if 分钟 or 项目:
        项目.append(f"{分钟}分")
    项目.append(f"{秒}秒")
    return "".join(项目)


上次系统CPU采样 = 读取系统CPU计数器()
