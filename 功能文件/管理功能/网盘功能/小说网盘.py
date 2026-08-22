from __future__ import annotations

from pathlib import Path
from typing import Any

from astrbot.api import logger

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值, 读取运行状态值
from 功能文件.管理功能.小说功能.功能 import 下载缓存清理
from 功能文件.管理功能.网盘功能 import UC网盘, 夸克网盘, 百度网盘, 网盘Cookie

状态命名空间 = "novel_share_pan"
状态键 = "active"
默认主网盘 = "UC"
网盘模块映射 = {"UC": UC网盘, "夸克": 夸克网盘, "百度": 百度网盘}
网盘显示名 = {"UC": "UC网盘", "夸克": "夸克网盘", "百度": "百度网盘"}
切换命令 = {
    "换UC": "UC",
    "换uc": "UC",
    "换Uc": "UC",
    "换uC": "UC",
    "换夸克": "夸克",
    "换百度": "百度",
}
状态命令 = {"网盘", "网盘状态", "当前网盘"}


async def 处理网盘Cookie指令(event: Any, 命令文本: str, 配置: Any) -> Any | None:
    return await 网盘Cookie.处理网盘Cookie指令(event, 命令文本, 配置)


async def 停止网盘后台任务() -> None:
    await 网盘Cookie.停止全部夸克扫码登录任务()


def 处理网盘切换指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if 文本 not in 切换命令 and 文本 not in 状态命令:
        return None
    if not 是群文件清理管理员(event, 配置):
        return None
    if 文本 in 状态命令:
        当前网盘 = 获取当前主网盘(配置)
        状态列表 = [f"当前小说网盘：{网盘显示名[当前网盘]}"]
        for 网盘名称 in ("UC", "夸克", "百度"):
            配置状态 = "已配置" if 主网盘是否启用(网盘名称, 配置) else "未配置"
            状态列表.append(f"{网盘显示名[网盘名称]}：{配置状态}")
        return "\n".join(状态列表)
    目标网盘 = 切换命令[文本]
    try:
        写入运行状态值(配置, 状态命名空间, 状态键, 目标网盘)
    except Exception as 异常:
        logger.warning(f"小说主网盘切换写入数据库失败：target={目标网盘}, error={异常}")
        return "网盘切换失败，请稍后再试"
    return f"已切换到{网盘显示名[目标网盘]}"


def 获取当前主网盘(配置: Any = None) -> str:
    try:
        当前网盘 = 读取运行状态值(配置, 状态命名空间, 状态键, 默认主网盘).strip()
    except Exception as 异常:
        logger.warning(f"小说主网盘读取数据库失败：error={异常}")
        return 默认主网盘
    return 当前网盘 if 当前网盘 in 网盘模块映射 else 默认主网盘


def 主网盘是否启用(网盘名称: str, 配置: Any) -> bool:
    if 网盘名称 == "UC":
        return UC网盘.UC网盘是否启用(配置)
    if 网盘名称 == "夸克":
        return 夸克网盘.夸克网盘是否启用(配置)
    if 网盘名称 == "百度":
        return 百度网盘.百度网盘是否启用(配置)
    return False


async def 上传小说并获取分享链接(
    配置: Any,
    源缓存路径: str | Path,
    文件名: str,
    *,
    _指定网盘: str | None = None,
) -> dict[str, Any]:
    当前网盘 = _指定网盘 if _指定网盘 in 网盘模块映射 else 获取当前主网盘(配置)
    网盘模块 = 网盘模块映射[当前网盘]
    if not 主网盘是否启用(当前网盘, 配置):
        return {
            "enabled": False,
            "success": False,
            "share_url": "",
            "provider": 网盘显示名[当前网盘],
            "error": "当前网盘未配置",
        }
    源路径 = Path(源缓存路径)
    if not 源路径.is_file():
        return {
            "enabled": True,
            "success": False,
            "share_url": "",
            "provider": 网盘显示名[当前网盘],
            "error": "本地文件不存在",
        }
    下载缓存清理.登记上传任务(源路径, 文件名, 网盘显示名[当前网盘])
    try:
        结果 = await 网盘模块.上传小说并获取分享链接(配置, 源路径, 文件名)
    except Exception as 异常:
        下载缓存清理.更新上传任务(
            源路径,
            "primary_pending",
            last_error=str(异常),
            retry_count=int(
                (下载缓存清理.读取上传任务(源路径) or {}).get("retry_count") or 0
            )
            + 1,
        )
        return {
            "enabled": True,
            "success": False,
            "share_url": "",
            "provider": 网盘显示名[当前网盘],
            "error": str(异常),
        }
    if not isinstance(结果, dict):
        下载缓存清理.更新上传任务(
            源路径,
            "primary_pending",
            last_error="网盘返回格式错误",
            retry_count=int(
                (下载缓存清理.读取上传任务(源路径) or {}).get("retry_count") or 0
            )
            + 1,
        )
        return {
            "enabled": True,
            "success": False,
            "share_url": "",
            "provider": 网盘显示名[当前网盘],
            "error": "网盘返回格式错误",
        }
    结果 = dict(结果)
    if 结果.get("success"):
        下载缓存清理.更新上传任务(
            源路径,
            "primary_done",
            share_url=str(结果.get("share_url") or ""),
            last_error="",
        )
    else:
        旧任务 = 下载缓存清理.读取上传任务(源路径) or {}
        下载缓存清理.更新上传任务(
            源路径,
            "primary_pending",
            last_error=str(结果.get("error") or "上传失败"),
            retry_count=int(旧任务.get("retry_count") or 0) + 1,
        )
    结果["provider"] = 网盘显示名[当前网盘]
    return 结果


async def 恢复待续传上传任务(配置: Any) -> int:
    """插件重载后恢复 TXT 上传；没有原会话时只恢复网盘任务并清理缓存。"""
    任务列表 = 下载缓存清理.获取待续传上传任务()
    已处理 = 0
    for 任务 in 任务列表:
        路径 = Path(str(任务.get("cache_path") or ""))
        文件名 = str(任务.get("file_name") or 路径.name)
        if not 路径.is_file():
            continue
        状态 = str(任务.get("state") or "primary_pending")
        if 状态 == "primary_pending" and 下载缓存清理.下载缓存正在使用(路径):
            continue
        if 状态 == "primary_pending":
            任务网盘 = next(
                (
                    键
                    for 键, 显示名 in 网盘显示名.items()
                    if str(任务.get("provider") or "") == 显示名
                ),
                None,
            )
            try:
                结果 = await 上传小说并获取分享链接(
                    配置,
                    路径,
                    文件名,
                    _指定网盘=任务网盘,
                )
            except Exception as 异常:
                logger.warning(f"重载恢复小说上传失败：file={文件名}, error={异常}")
                continue
            if not 结果.get("success"):
                continue
            已处理 += 1
        if not await _恢复百度后台上传(配置, 路径, 文件名):
            下载缓存清理.更新上传任务(
                路径,
                "backup_pending",
                last_error="百度网盘后台备份未完成",
            )
            continue
        if 下载缓存清理.删除下载缓存文件(路径):
            logger.info(f"重载恢复小说上传完成：file={文件名}")
    return 已处理


async def _恢复百度后台上传(配置: Any, 路径: Path, 文件名: str) -> bool:
    if 百度网盘 is None:
        return True
    try:
        结果 = await 百度网盘.后台上传小说文件(配置, 路径, 文件名)
    except Exception as 异常:
        logger.warning(f"重载恢复百度后台上传异常：file={文件名}, error={异常}")
        return False
    if not isinstance(结果, dict):
        return False
    return bool(结果.get("success") or 结果.get("skipped") or not 结果.get("enabled"))


async def 发送小说下载完成链接(
    event: Any, 书名: Any, 作者: Any, 分享链接: str
) -> dict[str, Any]:
    return await UC网盘.发送小说下载完成链接(event, 书名, 作者, 分享链接)


def 小说分享网盘是否启用(配置: Any) -> bool:
    return 主网盘是否启用(获取当前主网盘(配置), 配置)
