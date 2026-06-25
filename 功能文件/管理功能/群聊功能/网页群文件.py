"""
网页接口版群文件清理（pan.qun.qq.com）

通过 QQ 群文件网页接口批量删除群文件，需要管理员手动登录 QQ 网页拿 Cookie。
与适配器扩展接口版的 群文件清理.py 相互独立，指令不冲突。

指令（仅群文件清理管理员白名单 QQ 可用）：
- 登录群文件：返回 QQ 登录链接，引导用户去浏览器登录拿 Cookie
- 群文件登录cookie <cookie>：保存当前管理员的群文件 Cookie，31 天有效
- 清空群文件 <群号>：清空指定群的所有根目录文件
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 获取发送者QQ


# ---------- 配置 ----------

插件目录 = Path(__file__).resolve().parent.parent.parent.parent
状态目录 = 插件目录 / "功能文件" / "下载缓存"
COOKIE文件路径 = 状态目录 / "网页群文件Cookie.json"

登录群文件命令 = "登录群文件"
群文件登录cookie规则 = re.compile(r"^群文件登录\s*cookie\s+(.+)$", re.IGNORECASE)
清空群文件规则 = re.compile(r"^清空群文件\s+(\d+)$")

COOKIE有效期秒数 = 31 * 24 * 3600
列表每页数量 = 50
每批删除数量 = 20
删除最大重试次数 = 3
请求超时秒数 = 30

文件列表接口 = "https://pan.qun.qq.com/cgi-bin/group_file/get_file_list"
删除文件接口 = "https://pan.qun.qq.com/cgi-bin/group_file/delete_file"
登录链接 = (
    "https://ui.ptlogin2.qq.com/cgi-bin/login?style=9&appid=1600001573"
    "&s_url=https://qun.qq.com/#/login&daid=761&hide_close_icon=0"
)


# ---------- 入口分发 ----------


async def 处理网页群文件清理(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None

    if 文本 == 登录群文件命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用网页群文件清理"
        return 生成登录提示()

    cookie匹配 = 群文件登录cookie规则.fullmatch(文本)
    if cookie匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用网页群文件清理"
        return await 保存用户Cookie(event, cookie匹配.group(1).strip())

    清空匹配 = 清空群文件规则.fullmatch(文本)
    if 清空匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用网页群文件清理"
        return await 清空指定群文件(event, 清空匹配.group(1), 配置)

    return None


def 生成登录提示() -> str:
    return (
        "请在浏览器打开以下链接登录 QQ：\n"
        f"{登录链接}\n"
        "授权完后复制浏览器 Cookie，发送：\n"
        "群文件登录cookie 你的cookie"
    )


# ---------- Cookie 管理 ----------


async def 保存用户Cookie(event: Any, cookie文本: str) -> str:
    if "skey=" not in cookie文本:
        return "Cookie 无效，缺少 skey 字段"

    用户QQ = 获取发送者QQ(event)
    if not 用户QQ:
        return "没有获取到管理员QQ，无法保存 Cookie"

    cookies = 读取Cookie文件()
    cookies[用户QQ] = {
        "cookie": cookie文本,
        "expire": int(time.time()) + COOKIE有效期秒数,
    }
    写入Cookie文件(cookies)
    logger.info(f"网页群文件 Cookie 已更新：user_id={用户QQ}")
    return f"Cookie 已保存，{COOKIE有效期秒数 // 86400} 天内有效"


def 读取用户Cookie(用户QQ: str) -> str | None:
    cookies = 读取Cookie文件()
    信息 = cookies.get(用户QQ)
    if not 信息:
        return None
    if 安全整数(信息.get("expire"), 0) <= int(time.time()):
        return None
    return str(信息.get("cookie") or "").strip() or None


def 读取Cookie文件() -> dict[str, dict[str, Any]]:
    if not COOKIE文件路径.exists():
        return {}
    try:
        数据 = json.loads(COOKIE文件路径.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(数据, dict):
        return {}
    当前时间 = int(time.time())
    有效数据 = {
        str(用户QQ): 信息
        for 用户QQ, 信息 in 数据.items()
        if isinstance(信息, dict) and 安全整数(信息.get("expire"), 0) > 当前时间
    }
    if len(有效数据) != len(数据):
        写入Cookie文件(有效数据)
    return 有效数据


def 写入Cookie文件(cookies: dict[str, dict[str, Any]]) -> None:
    状态目录.mkdir(parents=True, exist_ok=True)
    COOKIE文件路径.write_text(
        json.dumps(cookies, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------- 工具 ----------


def 安全整数(值: Any, 默认值: int = 0) -> int:
    try:
        结果 = int(值)
    except (TypeError, ValueError):
        return 默认值
    return 结果 if 结果 >= 0 else 默认值


def 提取skey(cookie文本: str) -> str | None:
    匹配 = re.search(r"skey=([^;]+)", cookie文本)
    return 匹配.group(1) if 匹配 else None


def 计算bkn(skey: str) -> int:
    哈希值 = 5381
    for 字符 in skey:
        哈希值 += (哈希值 << 5) + ord(字符)
    return 哈希值 & 0x7FFFFFFF


async def 安全解析JSON(响应文本: str) -> dict | None:
    try:
        结果 = json.loads(响应文本)
        return 结果 if isinstance(结果, dict) else None
    except Exception:
        return None


# ---------- API ----------


async def 拉取文件列表(
    session: Any,
    群号: str,
    bkn: int,
    cookie文本: str,
    起始位置: int,
    数量: int = 列表每页数量,
) -> dict | None:
    请求地址 = (
        f"{文件列表接口}?gc={群号}&bkn={bkn}"
        f"&folder_id=/&start_index={起始位置}&cnt={数量}"
        f"&filter_code=0&show_onlinedoc_folder=1&src=qpan"
    )
    请求头 = {"Cookie": cookie文本}
    logger.info(f"[网页群文件] 请求文件列表：start={起始位置}, cnt={数量}")
    try:
        async with session.get(请求地址, headers=请求头, timeout=aiohttp.ClientTimeout(total=请求超时秒数)) as resp:
            if resp.status != 200:
                logger.warning(f"[网页群文件] 文件列表 HTTP {resp.status}")
                return None
            响应文本 = await resp.text()
            数据 = await 安全解析JSON(响应文本)
            if not 数据:
                logger.warning(f"[网页群文件] 文件列表非JSON响应：{响应文本[:200]}")
                return None
            if 安全整数(数据.get("ec"), -1) != 0:
                logger.warning(
                    f"[网页群文件] 文件列表接口错误 ec={数据.get('ec')} em={数据.get('em', '')}"
                )
                return None
            logger.info(
                f"[网页群文件] 文件列表获取成功 total={数据.get('total_cnt', 0)} 本页={len(数据.get('file_list', []))}"
            )
            return 数据
    except Exception as 异常:
        logger.warning(f"[网页群文件] 请求文件列表异常：{异常}")
        return None


async def 拉取全部文件(
    session: Any,
    群号: str,
    bkn: int,
    cookie文本: str,
) -> list[dict] | None:
    首页 = await 拉取文件列表(session, 群号, bkn, cookie文本, 0)
    if not 首页:
        return None
    总数 = 安全整数(首页.get("total_cnt"), 0)
    全部文件 = list(首页.get("file_list", []))
    if 总数 <= 列表每页数量:
        return 全部文件
    任务列表 = []
    for 页码 in range(1, (总数 + 列表每页数量 - 1) // 列表每页数量):
        任务列表.append(拉取文件列表(session, 群号, bkn, cookie文本, 页码 * 列表每页数量))
    结果列表 = await asyncio.gather(*任务列表)
    for 结果 in 结果列表:
        if 结果 and 安全整数(结果.get("ec"), -1) == 0:
            全部文件.extend(结果.get("file_list", []))
    return 全部文件


async def 删除文件批次(
    session: Any,
    群号: str,
    cookie文本: str,
    批次文件: list[dict],
    最大重试: int = 删除最大重试次数,
) -> bool:
    删除列表 = [
        {
            "gc": int(群号),
            "app_id": 4,
            "bus_id": 文件.get("bus_id"),
            "file_id": 文件.get("id"),
            "parent_folder_id": 文件.get("parent_id", "/"),
        }
        for 文件 in 批次文件
        if 文件.get("id") is not None
    ]
    if not 删除列表:
        return True

    请求头 = {"Cookie": cookie文本}
    for 尝试次数 in range(1, 最大重试 + 1):
        skey = 提取skey(cookie文本)
        if not skey:
            logger.warning("[网页群文件] Cookie 缺少 skey，无法计算 bkn")
            return False
        bkn = 计算bkn(skey)
        表单数据 = {
            "gc": 群号,
            "bkn": str(bkn),
            "file_list": json.dumps({"file_list": 删除列表}),
        }
        try:
            async with session.post(
                删除文件接口,
                data=表单数据,
                headers=请求头,
                timeout=aiohttp.ClientTimeout(total=请求超时秒数),
            ) as resp:
                响应文本 = await resp.text()
                if resp.status == 200:
                    数据 = await 安全解析JSON(响应文本)
                    if 数据 and 安全整数(数据.get("ec"), -1) == 0:
                        logger.info(f"[网页群文件] 删除成功 批次大小={len(批次文件)}")
                        return True
                    logger.warning(
                        f"[网页群文件] 删除接口错误 ec={数据.get('ec') if 数据 else '?'} 尝试 {尝试次数}/{最大重试}"
                    )
                elif resp.status == 500:
                    logger.warning(f"[网页群文件] 服务器500错误 尝试 {尝试次数}/{最大重试}")
                else:
                    logger.warning(
                        f"[网页群文件] 删除 HTTP {resp.status} 尝试 {尝试次数}/{最大重试}"
                    )
        except Exception as 异常:
            logger.warning(f"[网页群文件] 删除请求异常：{异常} 尝试 {尝试次数}/{最大重试}")

    logger.warning(
        f"[网页群文件] 删除失败 已重试 {最大重试} 次 批次大小={len(批次文件)}"
    )
    return False


# ---------- 清理主流程 ----------


async def 清空指定群文件(event: Any, 群号: str, 配置: Any) -> str:
    用户QQ = 获取发送者QQ(event)
    if not 用户QQ:
        return "没有获取到管理员QQ"

    cookie文本 = 读取用户Cookie(用户QQ)
    if not cookie文本:
        return "你还没有登录群文件，请先发送「登录群文件」获取登录链接"

    skey = 提取skey(cookie文本)
    if not skey:
        return "Cookie 缺少 skey，请重新发送「登录群文件」重新登录"

    if aiohttp is None:
        return "缺少 aiohttp 依赖，无法清理群文件"

    bkn = 计算bkn(skey)
    logger.info(f"[网页群文件] 开始清理 群号={群号} bkn={bkn}")

    async with aiohttp.ClientSession() as session:
        全部文件 = await 拉取全部文件(session, 群号, bkn, cookie文本)
        if 全部文件 is None:
            return "Cookie 已失效或接口错误，请重新发送「登录群文件」重新登录"
        if not 全部文件:
            return f"清理完成（群 {群号} 没有群文件）"

        总数 = len(全部文件)
        批次列表 = [全部文件[开始:开始 + 每批删除数量] for 开始 in range(0, 总数, 每批删除数量)]
        logger.info(
            f"[网页群文件] 群 {群号} 共 {总数} 个文件 分 {len(批次列表)} 批删除（每批 {每批删除数量} 个）"
        )

        任务列表 = [
            删除文件批次(session, 群号, cookie文本, 批次) for 批次 in 批次列表
        ]
        结果列表 = await asyncio.gather(*任务列表)
        成功批次数 = sum(1 for 结果 in 结果列表 if 结果)
        成功文件数 = sum(
            len(批次列表[序号])
            for 序号, 结果 in enumerate(结果列表)
            if 结果
        )
        logger.info(
            f"[网页群文件] 群 {群号} 删除完成 成功 {成功批次数}/{len(批次列表)} 批"
        )

    return (
        f"清理完成，群 {群号} 共处理 {总数} 个文件，"
        f"成功 {成功文件数} 个，失败 {总数 - 成功文件数} 个"
    )
