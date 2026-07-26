from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from 功能文件.管理功能.基础功能 import 用户激活
from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 读取字段, 获取发送者QQ
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取布尔运行状态值, 读取运行状态值


模块加载时间 = time.time()
上次进程CPU采样: tuple[float, float] | None = (time.monotonic(), time.process_time())
上次系统CPU采样: tuple[int, int] | None = None
小说功能状态命名空间 = "novel_feature_switch"
小说默认状态 = {"番茄": True, "七猫": True, "书旗": True, "QQ阅读": True}
付费开关状态命名空间 = "paid_access"


def 处理状态指令(event: Any, 命令文本: str, 配置: Any, 插件版本: str = "") -> str | None:
    if str(命令文本 or "").strip() != "状态":
        return None
    if not 是群文件清理管理员(event, 配置):
        return "没有权限查看状态"
    return 生成状态回复(event, 配置, 插件版本)


def 生成状态回复(event: Any, 配置: Any, 插件版本: str = "") -> str:
    功能状态 = 读取小说功能状态(配置)
    数据库状态 = 读取数据库配置状态(配置)
    UC状态 = 读取UC网盘状态(配置)
    百度状态 = 读取百度网盘状态(配置)
    群文件Cookie状态 = 读取群文件Cookie状态(event, 配置)

    return "\n".join(
        [
            "系统状态",
            "",
            "系统信息",
            f"插件版本：v{str(插件版本 or '').lstrip('v') or '未知'}",
            f"系统时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"运行系统：{platform.platform()}",
            f"Python：{platform.python_version()}",
            f"CPU核心：{os.cpu_count() or '未知'}",
            f"运行内存：{格式化运行内存()}",
            f"运行CPU：{格式化运行CPU()}",
            f"系统内存：{格式化系统内存()}",
            f"系统CPU：{格式化系统CPU()}",
            f"磁盘剩余：{格式化磁盘信息()}",
            f"系统运行：{格式化系统运行时间()}",
            f"插件运行：{格式化时长(int(time.time() - 模块加载时间))}",
            "",
            "功能状态",
            f"番茄小说：{格式化开关(bool(功能状态.get('番茄', True)))}",
            f"七猫小说：{格式化开关(bool(功能状态.get('七猫', True)))}",
            f"书旗小说：{格式化开关(bool(功能状态.get('书旗', True)))}",
            f"QQ阅读：{格式化开关(bool(功能状态.get('QQ阅读', True)))}",
            f"收费模式：已全部免费",
            f"数据库：{数据库状态}",
            f"群cookie：{群文件Cookie状态}",
            f"UC网盘：{UC状态}",
            f"百度网盘：{百度状态}",
        ]
    )


def 读取全局收费状态(配置: Any) -> str:
    def 读取状态() -> str:
        文本 = 读取运行状态值(配置, 付费开关状态命名空间, "global", "").strip().lower()
        if 文本 in {"on", "1", "true", "yes", "开启"}:
            return "开启（强制全部收费）"
        if 文本 in {"off", "0", "false", "no", "关闭"}:
            return "关闭（全部免费）"
        return "按群聊/私聊独立开关"

    return 安全读取("全局收费", 读取状态, "按群聊/私聊独立开关")


def 读取当前群收费状态(event: Any, 配置: Any) -> str:
    群号 = 用户激活.获取群号(event)
    if not 群号:
        return "非群聊"
    return 格式化开关(
        安全读取("当前群收费", lambda: 读取布尔运行状态值(配置, 付费开关状态命名空间, f"group:{群号}", True), True)
    )


def 读取私聊收费状态(配置: Any) -> str:
    def 读取状态() -> bool:
        return 读取布尔运行状态值(
            配置,
            付费开关状态命名空间,
            "private",
            True,
        )

    return 格式化开关(安全读取("私聊收费", 读取状态, True))


def 读取群文件Cookie状态(event: Any, 配置: Any) -> str:
    def 读取状态() -> str:
        from 功能文件.管理功能.群聊功能 import 网页群文件
        发送者 = 获取发送者QQ(event)
        return 网页群文件.获取Cookie状态摘要(发送者, 配置)

    return 安全读取("群文件Cookie", 读取状态, "读取失败")


def 读取数据库配置状态(配置: Any) -> str:
    try:
        数据库配置 = 用户激活.获取数据库配置(配置)
    except Exception:
        return "未配置"
    return "已配置" if 数据库配置 else "未配置"


def 读取UC网盘状态(配置: Any) -> str:
    Cookie = 清理带前缀Cookie(读取配置字段(配置, "uc_pan_cookie", ("uc_pan_settings", "UC网盘设置", "basic_settings", "基础配置")), "UC网盘#")
    return 格式化开关(bool(Cookie))


def 读取百度网盘状态(配置: Any) -> str:
    Cookie = 清理带前缀Cookie(读取配置字段(配置, "baidu_pan_cookie", ("baidu_pan_settings", "百度网盘设置", "basic_settings", "基础配置")), "百度网盘#")
    上传状态 = str(读取配置字段(配置, "baidu_pan_upload_status", ("baidu_pan_settings", "百度网盘设置", "basic_settings", "基础配置")) or "").strip()
    if 上传状态 not in ("完结", "连载", "全部"):
        上传状态 = "完结"
    return f"{格式化开关(bool(Cookie))}，上传：{上传状态}"


def 读取小说功能状态(配置: Any) -> dict[str, bool]:
    状态 = dict(小说默认状态)
    for 功能名, 默认值 in 小说默认状态.items():
        状态[功能名] = 安全读取(
            f"{功能名}功能状态",
            lambda 名称=功能名, 默认=默认值: 读取布尔运行状态值(配置, 小说功能状态命名空间, 名称, 默认),
            默认值,
        )
    return 状态


def 读取配置字段(配置: Any, 字段名: str, 分类列表: tuple[str, ...] = ("basic_settings", "基础配置")) -> Any:
    if 配置 is None:
        return None
    配置字典 = 获取配置字典(配置)
    if 配置字典 is not None and 配置字典 is not 配置:
        值 = 读取配置字段(配置字典, 字段名, 分类列表)
        if 值 is not None:
            return 值
    值 = 读取字段(配置, 字段名)
    if 值 is not None:
        return 值
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            值 = 获取方法(字段名)
            if 值 is not None:
                return 值
        except Exception:
            pass
    for 分类名 in 分类列表:
        分类 = 读取字段(配置, 分类名)
        if 分类 is None and callable(获取方法):
            try:
                分类 = 获取方法(分类名)
            except Exception:
                分类 = None
        if isinstance(分类, dict) and 字段名 in 分类:
            return 分类.get(字段名)
        值 = 读取字段(分类, 字段名)
        if 值 is not None:
            return 值
    return None


def 获取配置字典(配置: Any) -> dict[str, Any] | None:
    if isinstance(配置, dict):
        return 配置
    获取方法 = getattr(配置, "get_config", None)
    if callable(获取方法):
        try:
            数据 = 获取方法()
            if isinstance(数据, dict):
                return 数据
        except Exception:
            pass
    for 字段名 in ("data", "obj"):
        数据 = getattr(配置, 字段名, None)
        if isinstance(数据, dict):
            return 数据
    return None


def 清理带前缀Cookie(值: Any, 前缀: str) -> str:
    文本 = str(值 or "").strip()
    if 文本.startswith(前缀):
        文本 = 文本.split("#", 1)[1].strip()
    return 文本


def 安全读取(名称: str, 函数: Callable[[], Any], 默认值: Any) -> Any:
    try:
        return 函数()
    except Exception:
        return 默认值


def 格式化开关(是否开启: bool) -> str:
    return "开启" if 是否开启 else "关闭"


def 格式化磁盘信息() -> str:
    try:
        用量 = shutil.disk_usage(Path(__file__).resolve().anchor or Path.cwd())
    except Exception:
        try:
            用量 = shutil.disk_usage(Path.cwd())
        except Exception:
            return "未知"
    return f"{格式化字节(用量.free)} / {格式化字节(用量.total)}"


def 格式化运行内存() -> str:
    字节数 = 读取当前进程内存()
    if 字节数 is None:
        return "未知"
    return 格式化字节(字节数)


def 格式化运行CPU() -> str:
    global 上次进程CPU采样

    当前时间 = time.monotonic()
    当前CPU时间 = time.process_time()
    累计文本 = f"累计{当前CPU时间:.2f}秒"
    if 上次进程CPU采样 is None:
        上次进程CPU采样 = (当前时间, 当前CPU时间)
        return f"采样中（{累计文本}）"

    上次时间, 上次CPU时间 = 上次进程CPU采样
    上次进程CPU采样 = (当前时间, 当前CPU时间)
    间隔 = 当前时间 - 上次时间
    if 间隔 <= 0:
        return f"采样中（{累计文本}）"
    核心数 = max(1, os.cpu_count() or 1)
    百分比 = max(0.0, (当前CPU时间 - 上次CPU时间) / 间隔 / 核心数 * 100)
    return f"{百分比:.1f}%（{累计文本}）"


def 格式化系统内存() -> str:
    内存 = 读取系统内存()
    if 内存 is None:
        return "未知"
    已用, 总计 = 内存
    return f"{格式化字节(已用)} / {格式化字节(总计)}"


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
        with open("/proc/uptime", "r", encoding="utf-8") as 文件:
            内容 = 文件.read().strip().split()
        if 内容:
            return float(内容[0])
    except Exception:
        return None
    return None


def 读取Windows系统运行秒数() -> float | None:
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        毫秒 = kernel32.GetTickCount64()
        if 毫秒 >= 0:
            return float(毫秒) / 1000
    except Exception:
        return None
    return None


def 读取当前进程内存() -> int | None:
    系统名 = platform.system().lower()
    if 系统名 == "windows":
        return 读取Windows进程内存()
    if 系统名 == "linux":
        return 读取Linux进程内存()
    return 读取Resource进程内存()


def 读取Linux进程内存() -> int | None:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as 文件:
            for 行 in 文件:
                if 行.startswith("VmRSS:"):
                    项目 = 行.split()
                    if len(项目) >= 2:
                        return int(项目[1]) * 1024
    except Exception:
        return None
    return None


def 读取Windows进程内存() -> int | None:
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        计数器 = PROCESS_MEMORY_COUNTERS()
        计数器.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        句柄 = kernel32.GetCurrentProcess()
        成功 = psapi.GetProcessMemoryInfo(句柄, ctypes.byref(计数器), 计数器.cb)
        if 成功:
            return int(计数器.WorkingSetSize)
    except Exception:
        return None
    return None


def 读取Resource进程内存() -> int | None:
    try:
        import resource

        最大常驻 = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if 最大常驻 <= 0:
            return None
        if platform.system().lower() == "darwin":
            return 最大常驻
        return 最大常驻 * 1024
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
        with open("/proc/meminfo", "r", encoding="utf-8") as 文件:
            for 行 in 文件:
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
        with open("/proc/stat", "r", encoding="utf-8") as 文件:
            第一行 = 文件.readline()
        项目 = 第一行.split()
        if not 项目 or 项目[0] != "cpu":
            return None
        数值 = [int(值) for 值 in 项目[1:]]
        if len(数值) < 4:
            return None
        空闲 = 数值[3] + (数值[4] if len(数值) > 4 else 0)
        总计 = sum(数值)
        return 空闲, 总计
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
        if not kernel32.GetSystemTimes(ctypes.byref(空闲), ctypes.byref(内核), ctypes.byref(用户)):
            return None

        def 转整数(值: FILETIME) -> int:
            return (int(值.dwHighDateTime) << 32) + int(值.dwLowDateTime)

        空闲值 = 转整数(空闲)
        总计值 = 转整数(内核) + 转整数(用户)
        return 空闲值, 总计值
    except Exception:
        return None


def 格式化字节(字节数: int) -> str:
    数值 = float(字节数)
    for 单位 in ("B", "KB", "MB", "GB", "TB"):
        if 数值 < 1024 or 单位 == "TB":
            return f"{数值:.1f}{单位}"
        数值 /= 1024
    return f"{字节数}B"


def 格式化时长(秒数: int) -> str:
    秒数 = max(0, int(秒数))
    天, 余数 = divmod(秒数, 86400)
    小时, 余数 = divmod(余数, 3600)
    分钟, 秒 = divmod(余数, 60)
    项目 = []
    if 天:
        项目.append(f"{天}天")
    if 小时:
        项目.append(f"{小时}小时")
    if 分钟:
        项目.append(f"{分钟}分钟")
    if not 项目:
        项目.append(f"{秒}秒")
    return "".join(项目)


上次系统CPU采样 = 读取系统CPU计数器()
