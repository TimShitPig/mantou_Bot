from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from 功能文件.管理功能.基础功能 import 用户激活
from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 读取字段
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取布尔运行状态值, 读取运行状态值


模块加载时间 = time.time()
番茄API状态命名空间 = "fanqie_api"
番茄API状态键 = "current_api"
小说功能状态命名空间 = "novel_feature_switch"
小说默认状态 = {"番茄": True, "七猫": True}
付费开关状态命名空间 = "paid_access"
默认上传目录 = "/小说机器人"


def 处理状态指令(event: Any, 命令文本: str, 配置: Any, 插件版本: str = "") -> str | None:
    if str(命令文本 or "").strip() != "状态":
        return None
    if not 是群文件清理管理员(event, 配置):
        return "没有权限查看状态"
    return 生成状态回复(event, 配置, 插件版本)


def 生成状态回复(event: Any, 配置: Any, 插件版本: str = "") -> str:
    功能状态 = 读取小说功能状态(配置)
    当前API = 读取当前番茄API(配置)
    当前群收费 = 读取当前群收费状态(event, 配置)
    私聊收费 = 读取私聊收费状态(配置)
    每日免费额度 = 安全读取("每日免费额度", lambda: 用户激活.获取每日免费额度(配置), 0)
    数据库状态 = 读取数据库配置状态(配置)
    UC状态 = 读取UC网盘状态(配置)
    百度状态 = 读取百度网盘状态(配置)

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
            f"磁盘剩余：{格式化磁盘信息()}",
            f"插件运行：{格式化时长(int(time.time() - 模块加载时间))}",
            "",
            "功能状态",
            f"番茄小说：{格式化开关(bool(功能状态.get('番茄', True)))}",
            f"七猫小说：{格式化开关(bool(功能状态.get('七猫', True)))}",
            f"当前番茄API：{当前API}",
            f"当前群收费：{当前群收费}",
            f"私聊收费：{私聊收费}",
            f"每日免费额度：{每日免费额度} 次",
            f"番茄OIAPI key：{格式化已配置(bool(str(读取配置字段(配置, '番茄小说key') or '').strip()))}",
            f"数据库：{数据库状态}",
            f"UC网盘：{UC状态}",
            f"百度网盘：{百度状态}",
        ]
    )


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


def 读取数据库配置状态(配置: Any) -> str:
    try:
        数据库配置 = 用户激活.获取数据库配置(配置)
    except Exception:
        return "未配置"
    主机 = 数据库配置.get("host") or "未知"
    数据库名 = 数据库配置.get("database") or "未知"
    return f"已配置（{主机}/{数据库名}）"


def 读取UC网盘状态(配置: Any) -> str:
    Cookie = 清理带前缀Cookie(读取配置字段(配置, "uc_pan_cookie", ("uc_pan_settings", "UC网盘设置", "basic_settings", "基础配置")), "UC网盘#")
    目录 = str(读取配置字段(配置, "uc_pan_upload_dir", ("uc_pan_settings", "UC网盘设置", "basic_settings", "基础配置")) or "").strip() or 默认上传目录
    return f"{格式化开关(bool(Cookie))}，目录：{目录}"


def 读取百度网盘状态(配置: Any) -> str:
    Cookie = 清理带前缀Cookie(读取配置字段(配置, "baidu_pan_cookie", ("baidu_pan_settings", "百度网盘设置", "basic_settings", "基础配置")), "百度网盘#")
    目录 = str(读取配置字段(配置, "baidu_pan_upload_dir", ("baidu_pan_settings", "百度网盘设置", "basic_settings", "基础配置")) or "").strip() or 默认上传目录
    上传状态 = str(读取配置字段(配置, "baidu_pan_upload_status", ("baidu_pan_settings", "百度网盘设置", "basic_settings", "基础配置")) or "").strip()
    if 上传状态 not in ("完结", "连载", "全部"):
        上传状态 = "完结"
    return f"{格式化开关(bool(Cookie))}，目录：{目录}，上传：{上传状态}"


def 读取小说功能状态(配置: Any) -> dict[str, bool]:
    状态 = dict(小说默认状态)
    for 功能名, 默认值 in 小说默认状态.items():
        状态[功能名] = 安全读取(
            f"{功能名}功能状态",
            lambda 名称=功能名, 默认=默认值: 读取布尔运行状态值(配置, 小说功能状态命名空间, 名称, 默认),
            默认值,
        )
    return 状态


def 读取当前番茄API(配置: Any) -> str:
    当前接口 = 安全读取(
        "当前番茄API",
        lambda: 读取运行状态值(配置, 番茄API状态命名空间, 番茄API状态键, "OIAPI"),
        "OIAPI",
    )
    return 规范化番茄API(当前接口)


def 规范化番茄API(值: Any) -> str:
    文本 = str(值 or "").strip().lower()
    if 文本 in ("崩溃api", "崩溃", "bengkuiapi", "bengkui", "crashapi", "crash", "3"):
        return "崩溃API"
    if 文本 in ("析api", "xiapi", "xapi", "析", "xi", "2"):
        return "析API"
    return "OIAPI"


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


def 格式化已配置(是否配置: bool) -> str:
    return "已配置" if 是否配置 else "未配置"


def 格式化磁盘信息() -> str:
    try:
        用量 = shutil.disk_usage(Path(__file__).resolve().anchor or Path.cwd())
    except Exception:
        try:
            用量 = shutil.disk_usage(Path.cwd())
        except Exception:
            return "未知"
    return f"{格式化字节(用量.free)} / {格式化字节(用量.total)}"


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
