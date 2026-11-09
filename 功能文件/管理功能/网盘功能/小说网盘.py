from __future__ import annotations

import asyncio
import secrets

import aiohttp
from urllib.parse import quote
from datetime import date, datetime
import json
import re
from pathlib import Path
from typing import Any

from astrbot.api import logger

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值, 读取运行状态值
from 功能文件.管理功能.基础功能 import 文件缓存, 机器人作用域
from 功能文件.管理功能.网盘功能 import UC网盘, 夸克网盘, 百度网盘, 网盘Cookie
from 功能文件.管理功能.网盘功能 import 网盘状态

状态命名空间 = "novel_share_pan"
状态键 = "active"
默认主网盘 = "UC"
网盘模块映射 = {"UC": UC网盘, "夸克": 夸克网盘, "百度": 百度网盘}
网盘顺序 = ("UC", "夸克", "百度")
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
账号选择前缀 = {
    "UC": "UC",
    "uc": "UC",
    "夸": "夸克",
    "夸克": "夸克",
    "百": "百度",
    "百度": "百度",
}
网盘远端清理任务: asyncio.Task[Any] | None = globals().get("网盘远端清理任务")
恢复上传任务句柄: asyncio.Task[Any] | None = globals().get("恢复上传任务句柄")


def 设置当前网盘事件(event: Any) -> Any:
    return 网盘Cookie.设置当前网盘事件(event)


def 清除当前网盘事件(令牌: Any) -> None:
    网盘Cookie.清除当前网盘事件(令牌)


async def 处理网盘Cookie指令(event: Any, 命令文本: str, 配置: Any) -> Any | None:
    return await 网盘Cookie.处理网盘Cookie指令(event, 命令文本, 配置)


async def 停止网盘后台任务() -> None:
    await 停止恢复待续传上传任务()
    await 停止每日网盘远端清理任务()
    await 网盘Cookie.停止全部夸克扫码登录任务()


async def 停止恢复待续传上传任务() -> None:
    """停止上一轮重载恢复，避免同一缓存被多个协程重复处理。"""
    global 恢复上传任务句柄
    当前任务 = asyncio.current_task()
    待停止任务: list[asyncio.Task[Any]] = []
    任务 = 恢复上传任务句柄
    if 任务 is not None and not 任务.done() and 任务 is not 当前任务:
        待停止任务.append(任务)
    # v6.1.70 之前的恢复任务没有保存句柄；热重载时按其限定名清理，
    # 避免旧协程与新单实例恢复任务同时处理同一个缓存文件。
    for 候选任务 in asyncio.all_tasks():
        if 候选任务 is 当前任务 or 候选任务.done() or 候选任务 in 待停止任务:
            continue
        try:
            协程名称 = str(候选任务.get_coro().__qualname__ or "")
        except Exception:
            协程名称 = ""
        if "initialize.<locals>._恢复小说上传任务" in 协程名称:
            待停止任务.append(候选任务)
    恢复上传任务句柄 = None
    if not 待停止任务:
        return
    for 待停止 in 待停止任务:
        待停止.cancel()
    try:
        当前循环 = asyncio.get_running_loop()
    except RuntimeError:
        当前循环 = None
    if 当前循环 is not None:
        await asyncio.gather(*待停止任务, return_exceptions=True)


async def 清理网盘过期小说文件(
    配置: Any, 当前日期: date | None = None
) -> dict[str, int]:
    """遍历各机器人的独立账号；共用同一账号/目录时只检查一次。"""
    配置列表 = ([配置] if 机器人作用域.获取当前机器人AppID(配置)
              else 机器人作用域.枚举机器人配置(配置))
    已检查账号: set[tuple[str, str, str]] = set()
    合计: dict[str, int] = {}
    for 当前配置 in 配置列表 or [配置]:
        with 机器人作用域.绑定机器人作用域(机器人作用域.获取当前机器人AppID(当前配置)):
            统计 = await _清理当前机器人网盘过期小说(当前配置, 当前日期, 已检查账号)
        for 平台, 数量 in 统计.items():
            合计[平台] = 合计.get(平台, 0) + 数量
    return 合计


async def _清理当前机器人网盘过期小说(
    配置: Any, 当前日期: date | None,
    已检查账号: set[tuple[str, str, str]],
) -> dict[str, int]:
    """清理各账号过期 TXT 及已清空的日期目录，保留今天和昨天。"""
    日期 = 当前日期 or datetime.now().astimezone().date()
    客户端映射 = {
        "UC": (UC网盘.UC网盘客户端, UC网盘.读取UC上传目录),
        "夸克": (夸克网盘.夸克网盘客户端, 夸克网盘.读取夸克上传目录),
        "百度": (百度网盘.百度网盘客户端, 百度网盘.读取百度上传目录),
    }
    统计: dict[str, int] = {}
    for 平台 in 网盘顺序:
        if not 网盘状态.网盘开关是否开启(配置, 平台):
            continue
        账号列表 = 网盘Cookie.获取启用网盘账号列表(配置, 平台)
        if not 账号列表:
            continue
        客户端类, 读取目录 = 客户端映射[平台]
        删除数量 = 0
        for 序号, Cookie in 账号列表:
            目录 = 读取目录(配置)
            账号键 = (平台, Cookie, 目录)
            if 账号键 in 已检查账号:
                continue
            已检查账号.add(账号键)
            try:
                async with 客户端类(Cookie) as 客户端:
                    删除数量 += await 客户端.清理早于当天小说(
                        目录, 日期
                    )
            except asyncio.CancelledError:
                raise
            except Exception as 异常:
                logger.warning(
                    "网盘远端旧小说清理失败：平台=%s，账号=%d，错误类型=%s",
                    平台,
                    序号,
                    type(异常).__name__,
                )
        if 删除数量:
            统计[平台] = 删除数量
    return 统计


async def 每日网盘远端清理任务(配置: Any) -> None:
    """按服务器本地时间每天零点清理网盘旧小说。"""
    while True:
        await asyncio.sleep(文件缓存.计算下次本地零点等待秒数())
        try:
            统计 = await 清理网盘过期小说文件(配置)
            总数 = sum(统计.values())
            if 总数:
                logger.info(
                    "每日零点网盘旧小说清理完成：数量=%d，平台=%s",
                    总数,
                    ",".join(f"{平台}:{数量}" for 平台, 数量 in 统计.items()),
                )
        except asyncio.CancelledError:
            raise
        except Exception as 异常:
            logger.warning(
                "每日零点网盘旧小说清理失败：错误类型=%s",
                type(异常).__name__,
            )


def 启动每日网盘远端清理任务(配置: Any) -> asyncio.Task[Any] | None:
    global 网盘远端清理任务
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return None
    if (
        网盘远端清理任务 is not None
        and not 网盘远端清理任务.done()
        and getattr(网盘远端清理任务, "get_loop", lambda: None)() is 循环
    ):
        return 网盘远端清理任务
    网盘远端清理任务 = 循环.create_task(
        每日网盘远端清理任务(配置),
        name="网盘每日旧小说清理",
    )
    return 网盘远端清理任务


async def 停止每日网盘远端清理任务() -> None:
    global 网盘远端清理任务
    任务 = 网盘远端清理任务
    网盘远端清理任务 = None
    if 任务 is None or 任务.done():
        return
    任务.cancel()
    await asyncio.gather(任务, return_exceptions=True)


def 处理网盘切换指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    设置当前网盘事件(event)
    账号匹配 = re.fullmatch(
        r"(?:换\s*)?(UC|uc|夸|夸克|百|百度)\s*换\s*([1-9]\d*)", 文本
    )
    if (
        账号匹配 is None
        and 文本 not in 切换命令
        and 文本 not in 状态命令
        and 文本 not in {"关网盘", "关闭网盘", "开网盘", "开启网盘"}
    ):
        return None
    if not 是群文件清理管理员(event, 配置):
        return None
    if 文本 in {"关网盘", "关闭网盘", "开网盘", "开启网盘"}:
        群标识 = 网盘Cookie.获取网盘群标识(event)
        if not 群标识:
            return "请在群聊中使用此指令"
        关闭 = 文本 in {"关网盘", "关闭网盘"}
        函数 = 网盘Cookie.设置群小说文件直发 if 关闭 else 网盘Cookie.清除群网盘账号选择
        成功, 错误 = 函数(配置, 群标识)
        return ("本群已关闭网盘，小说将直接发送文件" if 关闭 else "本群已恢复默认网盘") if 成功 else 错误
    if 账号匹配 is not None:
        平台 = 账号选择前缀[账号匹配.group(1)]
        序号 = int(账号匹配.group(2))
        成功, 错误 = 网盘Cookie.设置网盘账号序号(
            配置, 平台, 序号, event
        )
        if not 成功:
            return 错误
        return f"当前群已切换到{网盘显示名[平台]}账号{序号}"
    if 文本 in 状态命令:
        当前网盘 = 获取当前主网盘(配置)
        群选择 = 网盘Cookie.获取群网盘账号选择(配置)
        状态列表 = [f"当前小说网盘：{网盘显示名[当前网盘]}"]
        if 群选择 and 群选择.get("mode") == "file":
            状态列表.insert(0, "本群网盘已关闭：直接发送文件")
        for 网盘名称 in ("UC", "夸克", "百度"):
            if not 网盘状态.网盘开关是否开启(配置, 网盘名称):
                配置状态 = "已关闭"
            else:
                配置状态 = "已配置" if 主网盘是否启用(网盘名称, 配置) else "未配置"
            账号数量 = 网盘Cookie.获取网盘账号数量(配置, 网盘名称)
            当前账号 = 网盘Cookie.获取当前网盘账号序号(
                配置, 网盘名称, event
            )
            状态列表.append(
                f"{网盘显示名[网盘名称]}：{配置状态}，账号{账号数量}个，当前第{当前账号}个"
            )
        return "\n".join(状态列表)
    目标网盘 = 切换命令[文本]
    if not 网盘状态.网盘开关是否开启(配置, 目标网盘):
        return f"{网盘显示名[目标网盘]}已关闭，请先开启"
    if not 网盘Cookie.获取启用网盘账号列表(配置, 目标网盘):
        return f"{网盘显示名[目标网盘]}没有启用账号，请先启用一个账号"
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


def _序列化分享链接(分享列表: list[dict[str, str]]) -> str:
    """兼容旧调用方：单网盘返回 URL，多网盘返回可解析的 JSON。"""
    if len(分享列表) == 1:
        return 分享列表[0]["url"]
    return json.dumps(分享列表, ensure_ascii=False, separators=(",", ":"))


async def _上传单个平台(
    配置: Any,
    源路径: Path,
    文件名: str,
    平台: str,
    账号序号: int,
) -> dict[str, str | bool]:
    模块 = 网盘模块映射[平台]
    logger.debug("小说网盘并发上传开始：platform=%s", 平台)
    覆盖令牌 = 网盘Cookie.设置网盘账号覆盖(平台, 账号序号)
    try:
        结果 = await 模块.上传小说并获取分享链接(配置, 源路径, 文件名)
    except Exception as 异常:
        return {
            "platform": 平台,
            "provider": 网盘显示名[平台],
            "success": False,
            "url": "",
            "error": str(异常),
        }
    finally:
        网盘Cookie.清除网盘账号覆盖(覆盖令牌)
    if not isinstance(结果, dict):
        return {
            "platform": 平台,
            "provider": 网盘显示名[平台],
            "success": False,
            "url": "",
            "error": "网盘返回格式错误",
        }
    链接 = str(结果.get("share_url") or "").strip()
    if not 结果.get("success") or not 链接:
        return {
            "platform": 平台,
            "provider": 网盘显示名[平台],
            "success": False,
            "url": "",
            "error": str(结果.get("error") or "上传失败"),
        }
    return {
        "platform": 平台,
        "provider": 网盘显示名[平台],
        "success": True,
        "url": 链接,
        "error": "",
    }


async def _并发上传平台列表(
    配置: Any,
    源路径: Path,
    文件名: str,
    目标平台列表: list[str],
    账号索引: dict[str, int] | None,
) -> list[dict[str, str | bool]]:
    """一次创建所有上传任务，确保各网盘从同一批调度中并行开始。"""
    任务列表 = [
        asyncio.create_task(
            _上传单个平台(
                配置,
                源路径,
                文件名,
                平台,
                int((账号索引 or {}).get(平台, 1) or 1),
            ),
            name=f"小说网盘上传-{平台}",
        )
        for 平台 in 目标平台列表
    ]
    if not 任务列表:
        return []
    logger.debug(
        "小说网盘并发上传调度完成：platforms=%s",
        ",".join(目标平台列表),
    )
    return list(await asyncio.gather(*任务列表))


async def _上传小说并获取分享链接内部(
    配置: Any,
    源缓存路径: str | Path,
    文件名: str,
    *,
    _指定网盘: str | None = None,
    _账号索引: dict[str, int] | None = None,
) -> dict[str, Any]:
    源路径 = Path(源缓存路径)
    if not 源路径.is_file():
        return {
            "enabled": True,
            "success": False,
            "share_url": "",
            "share_links": [],
            "provider": "小说网盘",
            "error": "本地文件不存在",
        }
    if _指定网盘 in 网盘模块映射:
        目标平台列表 = [str(_指定网盘)] if 主网盘是否启用(str(_指定网盘), 配置) else []
    else:
        目标平台列表 = [
            平台 for 平台 in 网盘顺序 if 主网盘是否启用(平台, 配置)
        ]
    if not 目标平台列表:
        return {
            "enabled": False,
            "success": False,
            "share_url": "",
            "share_links": [],
            "provider": 网盘显示名.get(_指定网盘 or 获取当前主网盘(配置), "小说网盘"),
            "error": "没有已开启且已配置的网盘",
        }
    文件缓存.登记上传任务(
        源路径,
        文件名,
        网盘显示名[目标平台列表[0]],
        账号索引=_账号索引,
        待处理平台=目标平台列表,
        appid=机器人作用域.获取当前机器人AppID(配置),
    )
    结果列表 = await _并发上传平台列表(
        配置,
        源路径,
        文件名,
        目标平台列表,
        _账号索引,
    )
    分享列表 = [
        {
            "platform": str(结果.get("platform") or ""),
            "provider": str(结果.get("provider") or ""),
            "url": str(结果.get("url") or ""),
        }
        for 结果 in 结果列表
        if 结果.get("success") and str(结果.get("url") or "").strip()
    ]
    成功平台 = [str(结果.get("platform") or "") for 结果 in 结果列表 if 结果.get("success")]
    失败平台 = [str(结果.get("platform") or "") for 结果 in 结果列表 if not 结果.get("success")]
    if 分享列表:
        分享链接 = _序列化分享链接(分享列表)
        文件缓存.更新上传任务(
            源路径,
            "primary_done" if not 失败平台 else "primary_pending",
            share_url=分享链接,
            last_error="",
            pending_platforms=失败平台,
            completed_platforms=成功平台,
        )
        return {
            "enabled": True,
            "success": True,
            "share_url": 分享链接,
            "share_links": 分享列表,
            "providers": [项目["provider"] for 项目 in 分享列表],
            "provider": "、".join(项目["provider"] for 项目 in 分享列表),
            "error": "",
        }
    错误列表 = [str(结果.get("error") or "上传失败") for 结果 in 结果列表]
    旧任务 = 文件缓存.读取上传任务(源路径) or {}
    文件缓存.更新上传任务(
        源路径,
        "primary_pending",
        last_error="；".join(错误列表),
        retry_count=int(旧任务.get("retry_count") or 0) + 1,
    )
    return {
        "enabled": True,
        "success": False,
        "share_url": "",
        "share_links": [],
        "provider": "、".join(网盘显示名[平台] for 平台 in 目标平台列表),
        "error": 错误列表[0] if 错误列表 else "上传失败",
    }


def _获取当前群上传网盘(配置: Any) -> tuple[str, int]:
    群标识 = 网盘Cookie.获取网盘群标识()
    群选择 = 网盘Cookie.获取群网盘账号选择(配置, 群标识)
    if 群选择 and 群选择.get("mode") == "file":
        return "file", 0
    可用账号 = {
        平台: {
            序号
            for 序号, _ in 网盘Cookie.获取启用网盘账号列表(配置, 平台)
        }
        for 平台 in 网盘顺序
        if 网盘状态.网盘开关是否开启(配置, 平台)
    }
    可用账号 = {平台: 序号集合 for 平台, 序号集合 in 可用账号.items() if 序号集合}

    if 群选择:
        平台 = str(群选择.get("platform") or "")
        try:
            序号 = int(群选择.get("index") or 0)
        except (TypeError, ValueError):
            序号 = 0
        if 平台 in 可用账号 and 序号 in 可用账号[平台]:
            return 平台, 序号

    平台 = 获取当前主网盘(配置)
    if 平台 not in 可用账号:
        平台 = next((名称 for 名称 in 网盘顺序 if 名称 in 可用账号), 平台)
    序号 = 网盘Cookie.获取当前网盘账号序号按群标识(
        配置, 平台, 群标识
    )
    if 平台 in 可用账号 and 序号 not in 可用账号[平台]:
        序号 = min(可用账号[平台])
    return 平台, max(1, int(序号 or 1))


async def 上传小说并获取分享链接(
    配置: Any,
    源缓存路径: str | Path,
    文件名: str,
    *,
    _指定网盘: str | None = None,
    _账号序号: int | None = None,
    _账号索引: dict[str, int] | None = None,
) -> dict[str, Any]:
    from 功能文件.管理功能.小说功能.功能 import 小说下载任务

    # TXT 已生成即登记，账号读取等待期间重载也能复用源文件。
    小说下载任务.登记当前小说上传(配置, 源缓存路径, 文件名, _指定网盘, _账号索引)
    if _指定网盘 not in {*网盘模块映射, "file"}:
        _指定网盘, 默认账号序号 = await asyncio.to_thread(
            _获取当前群上传网盘, 配置
        )
        if _账号序号 is None:
            _账号序号 = 默认账号序号
    if _指定网盘 == "file":
        小说下载任务.登记当前小说上传(配置, 源缓存路径, 文件名, "file", {})
        路径 = Path(源缓存路径)
        if not 路径.is_file():
            return {"success": False, "error": "文件不存在"}
        # 待发送文件同样受清理保护；全局续传不得把它转成网盘上传。
        文件缓存.登记上传任务(路径, 文件名, "直接文件", 待处理平台=[],
                     appid=机器人作用域.获取当前机器人AppID(配置))
        文件缓存.更新上传任务(路径, "primary_pending", delivery_mode="file")
        return {"success": True, "delivery_mode": "file", "path": str(路径),
                "filename": 文件名, "provider": "直接文件", "share_url": ""}
    if _账号索引 is None:
        if _账号序号 is None:
            _账号序号 = await asyncio.to_thread(
                网盘Cookie.获取当前网盘账号序号,
                配置,
                str(_指定网盘),
            )
        _账号索引 = {str(_指定网盘): max(1, int(_账号序号 or 1))}
    else:
        _账号索引 = {
            平台: max(1, int(序号))
            for 平台, 序号 in _账号索引.items()
            if 平台 in 网盘模块映射 and str(序号).lstrip("+").isdigit()
        }
    if _指定网盘 in 网盘模块映射:
        try:
            _账号索引[str(_指定网盘)] = max(
                1, int(_账号序号 or _账号索引.get(str(_指定网盘), 1))
            )
        except (TypeError, ValueError):
            _账号索引[str(_指定网盘)] = 1
    小说下载任务.登记当前小说上传(配置, 源缓存路径, 文件名, _指定网盘, _账号索引)
    return await _上传小说并获取分享链接内部(
        配置,
        源缓存路径,
        文件名,
        _指定网盘=_指定网盘,
        _账号索引=_账号索引,
    )


async def 恢复待续传上传任务(配置: Any) -> int:
    """插件重载后恢复 TXT 上传；没有原会话时只恢复网盘任务并清理缓存。"""
    任务列表 = 文件缓存.获取待续传上传任务()
    已处理 = 0
    for 任务 in 任务列表:
        路径 = Path(str(任务.get("cache_path") or ""))
        文件名 = str(任务.get("file_name") or 路径.name)
        if not 路径.is_file():
            continue
        状态 = str(任务.get("state") or "primary_pending")
        if 任务.get("delivery_mode") == "file":
            # 同进程任务由调度器提前保护；进程重启后的孤立文件只清理，不猜测会话。
            if not 文件缓存.小说缓存正在使用(路径):
                文件缓存.更新上传任务(路径, "primary_done")
                文件缓存.删除小说缓存文件(路径)
            continue
        if 文件缓存.小说缓存正在使用(路径):
            continue
        appid = str(任务.get("bot_appid") or "").strip()
        if appid:
            任务配置 = 机器人作用域.获取机器人配置(配置, appid)
        else:
            配置列表 = 机器人作用域.枚举机器人配置(配置)
            if len(配置列表) > 1:
                logger.warning("小说上传续传等待：reason=legacy_bot_identity_missing")
                continue
            任务配置 = 配置列表[0] if 配置列表 else 配置
        if 状态 == "primary_pending":
            任务平台 = 任务.get("pending_platforms")
            if isinstance(任务平台, list):
                待处理平台 = [
                    str(平台).strip()
                    for 平台 in 任务平台
                    if str(平台 or "").strip() in 网盘模块映射
                ]
            else:
                任务网盘 = next(
                    (
                        键
                        for 键, 显示名 in 网盘显示名.items()
                        if str(任务.get("provider") or "") == 显示名
                    ),
                    None,
                )
                待处理平台 = [任务网盘] if 任务网盘 else [
                    平台 for 平台 in 网盘顺序 if 主网盘是否启用(平台, 任务配置)
                ]
            if not 待处理平台:
                文件缓存.更新上传任务(路径, "primary_done", last_error="")
                if 文件缓存.删除小说缓存文件(路径):
                    logger.info(f"重载恢复小说上传完成：file={文件名}")
                continue
            账号索引 = 任务.get("account_indices")
            if not isinstance(账号索引, dict):
                账号索引 = {}
            try:
                with 机器人作用域.绑定机器人作用域(机器人作用域.获取当前机器人AppID(任务配置)):
                    结果列表 = await _并发上传平台列表(
                        任务配置,
                        路径,
                        文件名,
                        待处理平台,
                        账号索引,
                    )
            except Exception as 异常:
                logger.warning(f"重载恢复小说上传失败：file={文件名}, error={异常}")
                continue
            成功平台 = [
                str(结果.get("platform") or "")
                for 结果 in 结果列表
                if 结果.get("success")
            ]
            失败平台 = [
                str(结果.get("platform") or "")
                for 结果 in 结果列表
                if not 结果.get("success")
            ]
            if 失败平台:
                文件缓存.更新上传任务(
                    路径,
                    "primary_pending",
                    pending_platforms=失败平台,
                    completed_platforms=成功平台,
                    last_error="上传失败",
                )
                continue
            已处理 += 1
            文件缓存.更新上传任务(
                路径,
                "primary_done",
                pending_platforms=[],
                completed_platforms=成功平台,
                last_error="",
            )
        elif 状态 == "backup_pending":
            # 旧版本可能留下“百度后台备份”状态；新流程不再做后台备份，直接结束任务。
            文件缓存.更新上传任务(路径, "primary_done", last_error="")
        if 文件缓存.删除小说缓存文件(路径):
            logger.info(f"重载恢复小说上传完成：file={文件名}")
    return 已处理


def 启动恢复待续传上传任务(配置: Any) -> asyncio.Task[Any] | None:
    """启动单实例的重载恢复任务，重复初始化时复用现有任务。"""
    global 恢复上传任务句柄
    try:
        循环 = asyncio.get_running_loop()
    except RuntimeError:
        return None
    现有任务 = 恢复上传任务句柄
    if (
        现有任务 is not None
        and not 现有任务.done()
        and getattr(现有任务, "get_loop", lambda: None)() is 循环
    ):
        return 现有任务
    if 现有任务 is not None and not 现有任务.done():
        现有任务.cancel()

    async def _恢复工作() -> None:
        try:
            恢复数量 = await 恢复待续传上传任务(配置)
            if 恢复数量:
                logger.info("插件重载恢复小说上传任务：数量=%s", 恢复数量)
        except asyncio.CancelledError:
            raise
        except Exception as 异常:
            logger.warning(
                "插件重载恢复小说上传任务异常：错误类型=%s", type(异常).__name__
            )

    恢复上传任务句柄 = 循环.create_task(
        _恢复工作(),
        name="小说网盘重载恢复",
    )
    return 恢复上传任务句柄


async def _直接发送小说文件(event: Any, 交付结果: dict[str, Any]) -> dict[str, Any]:
    """复用官方适配器文件上传，单次提交消息并校验实际响应；不回退网盘。"""
    from 功能文件.管理功能.基础功能.权限工具 import 是QQ官方机器人
    from 功能文件.管理功能.基础功能 import 消息记录
    from 功能文件.管理功能.小说功能.功能 import 小说下载任务

    路径 = Path(交付结果["path"])
    阶段 = "init"
    状态码 = None
    业务码 = None
    try:
        if not 是QQ官方机器人(event):
            raise ValueError("unsupported_platform")
        群 = 网盘Cookie.获取网盘群标识(event)
        appid = 机器人作用域.获取事件机器人AppID(event)
        http = getattr(getattr(getattr(event, "bot", None), "api", None), "_http", None)
        def 身份有效() -> bool:
            return bool(群 and appid and http is not None
                        and str(getattr(getattr(http, "_token", None), "app_id", "")) == appid
                        and 机器人作用域.获取当前机器人AppID() == appid)
        if not 身份有效() or not callable(getattr(event, "upload_group_and_c2c_media", None)):
            raise ValueError("identity_or_uploader_missing")
        文件名 = Path(交付结果["filename"]).name
        大小 = (await asyncio.to_thread(路径.stat)).st_size
        阶段 = "upload"
        媒体 = await event.upload_group_and_c2c_media(
            str(路径.absolute()), 4, file_name=文件名, group_openid=群,
        )
        if not isinstance(媒体, dict) or not isinstance(媒体.get("file_info"), str) or not 媒体["file_info"]:
            raise ValueError("upload_unconfirmed")
        await http.check_session()
        if not 身份有效():
            raise ValueError("identity_changed")
        消息体 = {"msg_type": 7, "media": {"file_info": 媒体["file_info"]},
               "msg_seq": secrets.randbelow(10000) + 1}
        消息ID = str(getattr(getattr(event, "message_obj", None), "message_id", "") or "")
        if 消息ID:
            消息体["msg_id"] = 消息ID
        阶段 = "send"
        # 网络异常或未知结果也不自动重放已经提交的文件消息。
        小说下载任务.标记当前小说文件已提交()
        主机 = "sandbox.api.sgroup.qq.com" if getattr(http, "is_sandbox", False) else "api.bot.qq.com"
        async with http._session.post(
            f"https://{主机}/v2/groups/{quote(群, safe='')}/messages",
            json=消息体, headers=dict(getattr(http, "_headers", {}) or {}),
            allow_redirects=False, timeout=aiohttp.ClientTimeout(total=60),
        ) as 响应:
            状态码 = 响应.status
            数据 = bytearray()
            async for 块 in 响应.content.iter_chunked(16384):
                数据.extend(块)
                if len(数据) > 65536:
                    raise ValueError("response_too_large")
            返回 = json.loads(数据)
            if not isinstance(返回, dict):
                raise ValueError("invalid_response")
            码字段 = [返回[键] for 键 in ("code", "err_code") if 键 in 返回]
            业务码 = next((int(值) for 值 in 码字段 if type(值) in (int, str)
                        and re.fullmatch(r"-?[0-9]{1,12}", str(值))), None)
            码有效 = all(type(值) in (int, str) and 值 in (0, "0") for 值 in 码字段)
            if not 200 <= 状态码 < 300 or not 码有效 or not isinstance(返回.get("id"), str) or not 返回["id"]:
                raise ValueError("send_unconfirmed")
        # 确认先于记账；记账异常不能使文件再次发送。
        小说下载任务.标记当前小说完成通知()
        try:
            消息记录.记录发送消息(群, "group", "[文件] " + 文件名, appid,
                消息ID=返回["id"], 来源="bot_novel_file",
                媒体={"type": "文件", "src": "", "name": 文件名,
                    "size": 大小, "content_type": "text/plain"})
        except Exception as 异常:
            logger.warning("小说文件发送记账失败：error_type=%s", type(异常).__name__)
        return {"sent": True, "fallback_text": "", "error": ""}
    except Exception as 异常:
        logger.warning("小说文件直发失败：stage=%s, http_status=%s, code=%s, error_type=%s",
                       阶段, 状态码, 业务码, type(异常).__name__)
        return {"sent": False, "fallback_text": "", "error": "文件发送失败，请稍后再试"}
    finally:
        try:
            文件缓存.更新上传任务(路径, "primary_done")
            文件缓存.删除小说缓存文件(路径)
        except OSError as 异常:
            logger.warning("小说直发缓存清理失败：error_type=%s", type(异常).__name__)


async def 发送小说下载结果(
    event: Any, 书名: Any, 作者: Any, 交付结果: dict[str, Any]
) -> dict[str, Any]:
    from 功能文件.管理功能.小说功能.功能 import 小说下载任务

    async def _发送并确认() -> dict[str, Any]:
        if 交付结果.get("delivery_mode") == "file":
            结果 = await _直接发送小说文件(event, 交付结果)
        else:
            结果 = await UC网盘.发送小说下载完成链接(event, 书名, 作者, 交付结果.get("share_url", ""))
        if 结果.get("sent"):
            小说下载任务.标记当前小说完成通知(str(书名 or ""), str(作者 or ""))
        return 结果

    # 提交中的发送由重载任务接管确认，不阻塞停止，也不重复发送。
    任务 = asyncio.create_task(_发送并确认(), name="小说完成通知")
    已登记 = 小说下载任务.登记当前小说发送任务(任务)
    try:
        return await asyncio.shield(任务)
    except asyncio.CancelledError:
        if not 已登记:
            await asyncio.shield(任务)
        raise


def 小说分享网盘是否启用(配置: Any) -> bool:
    return any(主网盘是否启用(平台, 配置) for 平台 in 网盘顺序)
