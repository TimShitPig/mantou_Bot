"""
网页接口版群文件清理（pan.qun.qq.com）

通过 QQ 群文件网页接口批量删除群文件，需要管理员手动登录 QQ 网页拿 Cookie。
v2.0.0 起统一承担群文件清理职责，删除适配器扩展接口版 群文件清理.py。

指令（仅群文件清理管理员白名单 QQ 可用）：
- 登录群文件：返回 QQ 登录链接，引导用户去浏览器登录拿 Cookie
- 群文件登录cookie <cookie>：保存当前管理员的群文件 Cookie，31 天有效
- 清理群文件 / 群文件清理：列出「添加群聊」里的目标群，发送编号清理对应群（120 秒内有效，发送 0 取消）
- 清理全部群文件：用网页接口清理「添加群聊」里添加的全部目标群
- 添加群聊 群号 [群号...]：添加一个或多个群号到待清理列表
- 删除群聊 群号 [群号...]：从待清理列表移除群号
- 查看群聊：列出当前已添加的待清理目标群（含备注）
- 删除群聊：进入删除模式，点群号按钮直接删除
- 关闭删除群聊：退出删除模式，回到普通查看列表
- 更改备注：列出群号按钮选择要修改备注的群
- 更改备注 群号：进入备注等待（60 秒），下条消息作为该群备注保存
- 取消备注：取消备注等待
"""
from __future__ import annotations

import asyncio
import json
import re
import time
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

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 是QQ官方机器人, 获取发送者QQ
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态值, 写入运行状态值
from 功能文件.管理功能.基础功能.帮助功能 import 发送Markdown键盘消息, 生成按钮, 按钮分行


# ---------- 配置 ----------

登录群文件命令 = "登录群文件"
群文件登录cookie规则 = re.compile(r"^群文件登录\s*cookie\s+(.+)$", re.IGNORECASE)

清理群文件命令 = {"清理群文件", "群文件清理"}
清理全部群文件命令 = {"清理全部群文件"}

COOKIE有效期秒数 = 31 * 24 * 3600
列表每页数量 = 50
每批删除数量 = 20
删除最大重试次数 = 3
请求超时秒数 = 30
清理选择等待秒数 = 120

# Cookie 存 MySQL mantou_runtime_state：namespace=web_group_file_cookie，state_key=管理员QQ
COOKIE命名空间 = "web_group_file_cookie"

# 清理群文件选择等待状态：key=会话标识，value=(过期时间戳, 群号列表)
清理等待状态: dict[str, tuple[float, list[str]]] = {}

文件列表接口 = "https://pan.qun.qq.com/cgi-bin/group_file/get_file_list"
删除文件接口 = "https://pan.qun.qq.com/cgi-bin/group_file/delete_file"
登录链接 = (
    "https://ui.ptlogin2.qq.com/cgi-bin/login?style=9&appid=1600001573"
    "&s_url=https://qun.qq.com/#/login&daid=761&hide_close_icon=0"
)

# 群聊管理
待清理群命名空间 = "cleanup_groups"
待清理群状态键 = "group_list"
数字群号规则 = re.compile(r"[1-9]\d{4,11}")
添加群聊规则 = re.compile(r"^添加群聊\s+(.+)$")
删除群聊规则 = re.compile(r"^删除群聊\s+(.+)$")
查看群聊命令 = "查看群聊"
进入删除模式命令 = "删除群聊"
退出删除模式命令 = "关闭删除群聊"
返回上一步命令 = "返回上一步"
更改备注命令 = "更改备注"
取消备注命令 = "取消备注"
更改备注规则 = re.compile(r"^更改备注\s+(\d{5,12})$")
备注等待秒数 = 60
备注状态键前缀 = "remark:"
按钮每行数 = 2
按钮最大行数 = 5
删除模式等待秒数 = 300

# 备注等待状态：key=会话标识，value=(过期时间戳, 群号)
备注等待状态: dict[str, tuple[float, str]] = {}

# 删除模式状态：key=会话标识，value=过期时间戳；进入删除模式后按钮发「返回上一步」退出
删除模式状态: dict[str, float] = {}


# ---------- 删除模式状态管理 ----------


def 进入删除模式(event: Any) -> None:
    删除模式状态[获取会话标识(event)] = time.time() + 删除模式等待秒数


def 退出删除模式(event: Any) -> None:
    删除模式状态.pop(获取会话标识(event), None)


def 处于删除模式(event: Any) -> bool:
    标识 = 获取会话标识(event)
    过期时间 = 删除模式状态.get(标识)
    if 过期时间 is None:
        return False
    if 过期时间 <= time.time():
        删除模式状态.pop(标识, None)
        return False
    return True


def 处于清理等待状态(event: Any) -> bool:
    标识 = 获取会话标识(event)
    状态 = 清理等待状态.get(标识)
    if 状态 is None:
        return False
    过期时间, _ = 状态
    if 过期时间 <= time.time():
        清理等待状态.pop(标识, None)
        return False
    return True


def 需要优先处理返回(event: Any) -> bool:
    """删除模式或清理等待状态下，返回上一步需要由本模块优先处理，避免被帮助功能拦截。"""
    return 处于删除模式(event) or 处于清理等待状态(event)


async def 处理删除模式返回(event: Any, 文本: str, 配置: Any) -> str | None:
    """删除模式下收到「返回上一步」：退出删除模式并回到查看群聊列表。"""
    if 文本 != 返回上一步命令 or not 处于删除模式(event):
        return None
    退出删除模式(event)
    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用群聊管理"
    return await 显示群列表查看(event, 配置)


# ---------- 入口分发 ----------


async def 处理网页群文件清理(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None

    try:
        return await _处理网页群文件清理内部(event, 文本, 配置)
    except Exception as exc:
        logger.warning(f"[网页群文件诊断] 命令={文本!r} 异常={type(exc).__name__}: {exc}", exc_info=True)
        return f"网页群文件处理异常：{type(exc).__name__}: {exc}"


async def _处理网页群文件清理内部(event: Any, 文本: str, 配置: Any) -> str | None:
    logger.info(f"[网页群文件诊断] 收到命令 文本={文本!r} 是管理员={是群文件清理管理员(event, 配置)}")
    删除模式回复 = await 处理删除模式返回(event, 文本, 配置)
    if 删除模式回复 is not None:
        return 删除模式回复

    选择回复 = await 处理清理选择回复(event, 文本, 配置)
    if 选择回复 is not None:
        return 选择回复

    备注回复 = await 处理备注等待回复(event, 文本, 配置)
    if 备注回复 is not None:
        return 备注回复

    群聊管理回复 = await 处理群聊管理指令(event, 文本, 配置)
    if 群聊管理回复 is not None:
        return 群聊管理回复

    if 文本 == 登录群文件命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用网页群文件清理"
        return 生成登录提示()

    cookie匹配 = 群文件登录cookie规则.fullmatch(文本)
    if cookie匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用网页群文件清理"
        return await 保存用户Cookie(event, cookie匹配.group(1).strip(), 配置)

    if 文本 in 清理群文件命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群文件清理"
        return await 列出待清理群供选择(event, 配置)

    if 文本 in 清理全部群文件命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群文件清理"
        return await 清理全部已添加群(event, 配置)

    return None


async def 处理清理选择回复(event: Any, 文本: str, 配置: Any) -> str | None:
    标识 = 获取会话标识(event)
    状态 = 清理等待状态.get(标识)
    if 状态 is None:
        return None
    过期时间, 群号列表 = 状态
    if 过期时间 <= time.time():
        清理等待状态.pop(标识, None)
        # 状态过期：数字或返回上一步返回提示，避免落到帮助菜单误进其他功能（如全员禁言详情）
        if 文本.isdigit() or 文本 == 返回上一步命令:
            return "清理群文件选择已过期，请重新发送「清理群文件」"
        return None

    logger.info(f"[网页群文件诊断] 清理选择回复 文本={文本!r} 标识={标识!r} 群号列表={群号列表}")

    if 文本 == "0" or 文本 == 返回上一步命令:
        清理等待状态.pop(标识, None)
        return "已取消清理群文件选择"

    if not 是群文件清理管理员(event, 配置):
        清理等待状态.pop(标识, None)
        return "没有权限使用群文件清理"

    目标群号 = None
    # 先匹配编号（1,2,3...）
    if 文本.isdigit():
        序号 = int(文本)
        if 1 <= 序号 <= len(群号列表):
            目标群号 = 群号列表[序号 - 1]
    # 再匹配群号或备注（按钮可能发送的是按钮文字而非编号）
    if 目标群号 is None:
        for 群号 in 群号列表:
            if 文本 == 群号 or 文本 == 读取群备注(配置, 群号):
                目标群号 = 群号
                break

    if 目标群号 is None:
        if 文本.isdigit():
            return f"编号无效，请发送 1-{len(群号列表)} 的数字，或发送 0 取消"
        return None

    清理结果 = await 清空指定群文件(event, 目标群号, 配置)
    # 清理成功后保持清理等待状态，允许连续清理多个群；发送「0」或「返回上一步」才退出
    剩余群号列表 = 读取待清理群列表(配置)
    if not 剩余群号列表:
        清理等待状态.pop(标识, None)
        return f"已选择群 {目标群号}，开始清理\n{清理结果}\n已清理完所有待清理群"
    # 刷新等待状态的群号列表和过期时间，避免连续清理中途过期
    清理等待状态[标识] = (time.time() + 清理选择等待秒数, 剩余群号列表)
    return f"已选择群 {目标群号}，开始清理\n{清理结果}\n\n可继续发送编号清理其他群，或发送「返回上一步」结束"


async def 列出待清理群供选择(event: Any, 配置: Any) -> str:
    群号列表 = 读取待清理群列表(配置)
    if not 群号列表:
        return "还没有添加待清理群，请先发送「添加群聊 群号」添加目标群"

    写入清理等待状态(event, 群号列表)
    if 是QQ官方机器人(event):
        md = 格式化清理选择markdown(群号列表)
        群按钮 = [
            生成按钮(str(序号), 生成群号按钮标签(群号, 配置), 自动发送=True, data为标签=False)
            for 序号, 群号 in enumerate(群号列表, start=1)
        ]
        取消按钮 = 生成按钮(返回上一步命令, "返回上一步", 自动发送=True, data为标签=True)
        行 = 按钮分行(群按钮, 每行最多=按钮每行数)
        行.append({"buttons": [取消按钮]})
        键盘 = {"rows": 行} if len(行) <= 按钮最大行数 else None
        if await 发送Markdown键盘消息(event, md, 键盘):
            return ""
    行列表 = [f"请发送编号清理对应群（{清理选择等待秒数} 秒内有效）："]
    for 序号, 群号 in enumerate(群号列表, start=1):
        行列表.append(f"{序号}. {群号}")
    行列表.append("发送 0 取消")
    return "\n".join(行列表)


def 格式化清理选择markdown(群号列表: list[str]) -> str:
    行列表 = [f"**选择要清理的群**", f"点击群号按钮清理对应群（{清理选择等待秒数} 秒内有效）："]
    for 序号, 群号 in enumerate(群号列表, start=1):
        行列表.append(f"{序号}. {群号}")
    return "\n".join(行列表)


def 获取会话标识(event: Any) -> str:
    发送者 = 获取发送者QQ(event) or ""
    群号 = 获取群号(event)
    if 群号:
        return f"group:{群号}:{发送者}"
    return f"private:{发送者}"


def 写入清理等待状态(event: Any, 群号列表: list[str]) -> None:
    清理等待状态[获取会话标识(event)] = (time.time() + 清理选择等待秒数, 群号列表)


def 生成登录提示() -> str:
    return (
        "请在浏览器打开以下链接登录 QQ：\n"
        f"{登录链接}\n"
        "授权完后复制浏览器 Cookie，发送：\n"
        "群文件登录cookie 你的cookie"
    )


# ---------- 群聊管理（待清理目标群列表） ----------


async def 处理群聊管理指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None

    if 文本 in (查看群聊命令, 退出删除模式命令):
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        退出删除模式(event)
        return await 显示群列表查看(event, 配置)

    if 文本 == 进入删除模式命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        进入删除模式(event)
        return await 显示群列表删除模式(event, 配置, 前缀文本="")

    添加匹配 = 添加群聊规则.fullmatch(文本)
    if 添加匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        return await 添加群聊(event, 配置, 添加匹配.group(1))

    删除匹配 = 删除群聊规则.fullmatch(文本)
    if 删除匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        删除结果 = 删除群聊(配置, 删除匹配.group(1))
        return await 显示删除结果带刷新(event, 配置, 删除结果)

    if 文本 == 更改备注命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        return await 显示更改备注选群(event, 配置)

    更改备注匹配 = 更改备注规则.fullmatch(文本)
    if 更改备注匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        return await 进入备注等待(event, 配置, 更改备注匹配.group(1))

    if 文本 == 取消备注命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        return "当前没有进行中的备注修改"

    return None


async def 显示群列表查看(event: Any, 配置: Any, 前缀文本: str = "") -> str:
    """查看群聊：QQ 官方发 markdown + 删除/更改备注/返回上一步按钮；普通机器人纯文本。"""
    群号列表 = 读取待清理群列表(配置)
    if not 群号列表:
        if 前缀文本:
            return 前缀文本 + "\n当前没有添加待清理群，请发送「添加群聊 群号」添加"
        return "当前没有添加待清理群，请发送「添加群聊 群号」添加"
    if 是QQ官方机器人(event):
        标题 = (前缀文本 + "\n\n" if 前缀文本 else "") + "待清理群列表"
        md = 格式化群列表markdown(群号列表, 配置, 标题)
        删除按钮 = 生成按钮(进入删除模式命令, "删除群聊", 自动发送=True, data为标签=False)
        更改备注按钮 = 生成按钮(更改备注命令, "更改备注", 自动发送=True, data为标签=False)
        返回按钮 = 生成按钮("返回上一步", "返回上一步", 自动发送=True, data为标签=True)
        键盘 = {"rows": [{"buttons": [删除按钮, 更改备注按钮]}, {"buttons": [返回按钮]}]}
        if await 发送Markdown键盘消息(event, md, 键盘):
            return ""
    尾部前缀 = 前缀文本 + "\n" if 前缀文本 else ""
    return 尾部前缀 + 格式化待清理群列表文本(群号列表, 配置, "发送「删除群聊」可逐个删除")


async def 显示群列表删除模式(event: Any, 配置: Any, 前缀文本: str) -> str:
    """删除模式：QQ 官方发群按钮 + 返回按钮；普通机器人纯文本编号列表。"""
    群号列表 = 读取待清理群列表(配置)
    if not 群号列表:
        if 前缀文本:
            return 前缀文本 + "\n已没有待清理群了"
        return "当前没有待清理群，请先发送「添加群聊 群号」添加"
    if 是QQ官方机器人(event):
        md = 格式化群列表markdown(群号列表, 配置, "点击群号删除" if not 前缀文本 else 前缀文本)
        群按钮 = [
            生成按钮(f"{进入删除模式命令} {群号}", 生成群号按钮标签(群号, 配置), 自动发送=True, data为标签=False)
            for 群号 in 群号列表
        ]
        返回按钮 = 生成按钮(返回上一步命令, "返回上一步", 自动发送=True, data为标签=True)
        行 = 按钮分行(群按钮, 每行最多=按钮每行数)
        行.append({"buttons": [返回按钮]})
        键盘 = {"rows": 行} if len(行) <= 按钮最大行数 else None
        if await 发送Markdown键盘消息(event, md, 键盘):
            return ""
    return 格式化待清理群列表文本(群号列表, 配置, "发送「删除群聊 群号」删除，发送「关闭删除群聊」退出")


async def 显示删除结果带刷新(event: Any, 配置: Any, 删除结果文本: str) -> str:
    """删除群号后：QQ 官方刷新剩余群按钮列表（保持删除模式）；普通机器人纯文本。"""
    进入删除模式(event)
    if 是QQ官方机器人(event):
        群号列表 = 读取待清理群列表(配置)
        md = 删除结果文本
        键盘 = None
        if 群号列表:
            md += "\n\n剩余待清理群，点击删除："
            for 行文本 in 格式化群列表行(群号列表, 配置):
                md += f"\n{行文本}"
            群按钮 = [
                生成按钮(f"{进入删除模式命令} {群号}", 生成群号按钮标签(群号, 配置), 自动发送=True, data为标签=False)
                for 群号 in 群号列表
            ]
            返回按钮 = 生成按钮(返回上一步命令, "返回上一步", 自动发送=True, data为标签=True)
            行 = 按钮分行(群按钮, 每行最多=按钮每行数)
            行.append({"buttons": [返回按钮]})
            键盘 = {"rows": 行} if len(行) <= 按钮最大行数 else None
        if await 发送Markdown键盘消息(event, md, 键盘):
            return ""
    return 删除结果文本 + "\n" + 格式化待清理群列表(配置)


async def 显示更改备注选群(event: Any, 配置: Any) -> str:
    """更改备注选群：QQ 官方发群按钮 + 返回按钮；普通机器人纯文本。"""
    群号列表 = 读取待清理群列表(配置)
    if not 群号列表:
        return "还没有添加待清理群，请先发送「添加群聊 群号」添加目标群"
    if 是QQ官方机器人(event):
        md = 格式化群列表markdown(群号列表, 配置, "选择要修改备注的群")
        群按钮 = [
            生成按钮(f"{更改备注命令} {群号}", 生成群号按钮标签(群号, 配置), 自动发送=True, data为标签=False)
            for 群号 in 群号列表
        ]
        返回按钮 = 生成按钮(查看群聊命令, "返回上一步", 自动发送=True, data为标签=False)
        行 = 按钮分行(群按钮, 每行最多=按钮每行数)
        行.append({"buttons": [返回按钮]})
        键盘 = {"rows": 行} if len(行) <= 按钮最大行数 else None
        if await 发送Markdown键盘消息(event, md, 键盘):
            return ""
    return 格式化待清理群列表文本(群号列表, 配置, "发送「更改备注 群号」修改备注")


async def 进入备注等待(event: Any, 配置: Any, 群号: str) -> str:
    """进入备注等待状态：60 秒内下条消息作为备注。"""
    群号列表 = 读取待清理群列表(配置)
    if 群号 not in 群号列表:
        return f"群 {群号} 不在待清理列表中"
    当前备注 = 读取群备注(配置, 群号)
    标识 = 获取会话标识(event)
    备注等待状态[标识] = (time.time() + 备注等待秒数, 群号)
    logger.info(f"[网页群文件诊断] 进入备注等待 标识={标识!r} 群号={群号!r} 当前备注={当前备注!r}")
    提示 = f"请在 {备注等待秒数} 秒内发送群 {群号} 的新备注"
    if 当前备注:
        提示 += f"\n当前备注：{当前备注}"
    提示 += "\n发送「取消备注」取消"
    if 是QQ官方机器人(event):
        取消按钮 = 生成按钮(取消备注命令, "取消备注", 自动发送=True, data为标签=False)
        键盘 = {"rows": [{"buttons": [取消按钮]}]}
        if await 发送Markdown键盘消息(event, 提示, 键盘):
            return ""
    return 提示


async def 处理备注等待回复(event: Any, 文本: str, 配置: Any) -> str | None:
    """命中备注等待状态时：取消备注命令取消，否则下条消息作为备注保存。"""
    标识 = 获取会话标识(event)
    状态 = 备注等待状态.get(标识)
    logger.info(f"[网页群文件诊断] 处理备注回复 文本={文本!r} 标识={标识!r} 状态={'有' if 状态 else '无'}")
    if 状态 is None:
        return None
    过期时间, 群号 = 状态
    if 过期时间 <= time.time():
        备注等待状态.pop(标识, None)
        return None

    if 文本 == 取消备注命令:
        备注等待状态.pop(标识, None)
        return "已取消修改备注"

    if not 是群文件清理管理员(event, 配置):
        备注等待状态.pop(标识, None)
        return "没有权限修改备注"

    备注 = 文本.strip()
    try:
        写入群备注(配置, 群号, 备注)
    except Exception as exc:
        备注等待状态.pop(标识, None)
        logger.warning(f"群备注写入失败：group={群号}, error={exc}")
        return f"备注保存失败：{exc}"
    备注等待状态.pop(标识, None)
    return await 显示群列表查看(event, 配置, 前缀文本=f"已保存群 {群号} 的备注：{备注}")


def 读取待清理群列表(配置: Any) -> list[str]:
    文本 = 读取运行状态值(配置, 待清理群命名空间, 待清理群状态键, "")
    if not 文本:
        return []
    try:
        数据 = json.loads(文本)
    except Exception:
        return []
    if not isinstance(数据, list):
        return []
    结果: list[str] = []
    已见: set[str] = set()
    for 群号 in 数据:
        文本群号 = str(群号).strip()
        if not 文本群号 or 文本群号 in 已见:
            continue
        已见.add(文本群号)
        结果.append(文本群号)
    return 结果


def 写入待清理群列表(配置: Any, 群号列表: list[str]) -> None:
    写入运行状态值(配置, 待清理群命名空间, 待清理群状态键, json.dumps(群号列表, ensure_ascii=False))


async def 添加群聊(event: Any, 配置: Any, 参数文本: str) -> str:
    解析群号 = 解析群号参数(参数文本)
    if not 解析群号:
        return "请提供要添加的群号，例如：添加群聊 123456789"

    当前列表 = 读取待清理群列表(配置)
    已见 = set(当前列表)
    新增 = [群号 for 群号 in 解析群号 if 群号 not in 已见]
    已存在 = [群号 for 群号 in 解析群号 if 群号 in 已见]

    if 新增:
        当前列表.extend(新增)
        try:
            写入待清理群列表(配置, 当前列表)
        except Exception as exc:
            logger.warning(f"添加群聊写入失败：error={exc}")
            return f"添加群聊失败：{exc}"

    行列表 = []
    if 新增:
        行列表.append("已添加：" + "、".join(新增))
    if 已存在:
        行列表.append("已存在跳过：" + "、".join(已存在))
    行列表.append(f"当前共 {len(当前列表)} 个待清理群")
    return await 显示群列表查看(event, 配置, 前缀文本="\n".join(行列表))


def 删除群聊(配置: Any, 参数文本: str) -> str:
    解析群号 = 解析群号参数(参数文本)
    if not 解析群号:
        return "请提供要删除的群号，例如：删除群聊 123456789"

    当前列表 = 读取待清理群列表(配置)
    当前集合 = set(当前列表)
    待删集合 = set(解析群号)
    新列表 = [群号 for 群号 in 当前列表 if 群号 not in 待删集合]
    已删除 = [群号 for 群号 in 解析群号 if 群号 in 当前集合]
    不存在 = [群号 for 群号 in 解析群号 if 群号 not in 当前集合]

    if 新列表 != 当前列表:
        try:
            写入待清理群列表(配置, 新列表)
            for 群号 in 已删除:
                try:
                    写入群备注(配置, 群号, "")
                except Exception:
                    pass
        except Exception as exc:
            logger.warning(f"删除群聊写入失败：error={exc}")
            return f"删除群聊失败：{exc}"

    行列表 = []
    if 已删除:
        行列表.append("已删除：" + "、".join(已删除))
    if 不存在:
        行列表.append("列表中没有：" + "、".join(不存在))
    行列表.append(f"当前共 {len(新列表)} 个待清理群")
    return "\n".join(行列表)


def 格式化待清理群列表(配置: Any) -> str:
    当前列表 = 读取待清理群列表(配置)
    if not 当前列表:
        return "当前没有添加待清理群，请发送「添加群聊 群号」添加"
    return 格式化待清理群列表文本(当前列表, 配置, "发送「删除群聊 群号」可移除")


def 格式化待清理群列表文本(群号列表: list[str], 配置: Any, 尾部提示: str) -> str:
    行列表 = [f"当前共 {len(群号列表)} 个待清理群："]
    for 行文本 in 格式化群列表行(群号列表, 配置):
        行列表.append(行文本)
    if 尾部提示:
        行列表.append(f"\n{尾部提示}")
    return "\n".join(行列表)


def 格式化群列表markdown(群号列表: list[str], 配置: Any, 标题: str) -> str:
    行列表 = [f"**{标题}**", f"共 {len(群号列表)} 个待清理群："]
    for 行文本 in 格式化群列表行(群号列表, 配置):
        行列表.append(行文本)
    return "\n".join(行列表)


def 格式化群列表行(群号列表: list[str], 配置: Any) -> list[str]:
    结果: list[str] = []
    for 序号, 群号 in enumerate(群号列表, start=1):
        备注 = 读取群备注(配置, 群号)
        if 备注:
            结果.append(f"{序号}. {群号}（{备注}）")
        else:
            结果.append(f"{序号}. {群号}")
    return 结果


def 读取群备注(配置: Any, 群号: str) -> str:
    return str(读取运行状态值(配置, 待清理群命名空间, f"{备注状态键前缀}{群号}", "") or "")


def 写入群备注(配置: Any, 群号: str, 备注: str) -> None:
    写入运行状态值(配置, 待清理群命名空间, f"{备注状态键前缀}{群号}", 备注)


def 生成群号按钮标签(群号: str, 配置: Any, 最大长度: int = 12) -> str:
    """生成群号按钮标签：有备注直接显示备注（超长截断加省略号），无备注显示群号。"""
    备注 = 读取群备注(配置, 群号)
    if not 备注:
        return 群号
    if len(备注) > 最大长度:
        备注 = 备注[:最大长度] + "…"
    return 备注


def 解析群号参数(参数文本: str) -> list[str]:
    候选 = 参数文本.replace(",", " ").replace("、", " ").split()
    结果: list[str] = []
    已见: set[str] = set()
    for 候选项 in 候选:
        文本 = 候选项.strip()
        if not 文本 or not 数字群号规则.fullmatch(文本):
            continue
        if 文本 in 已见:
            continue
        已见.add(文本)
        结果.append(文本)
    return 结果


# ---------- Cookie 管理 ----------


async def 保存用户Cookie(event: Any, cookie文本: str, 配置: Any) -> str:
    if "skey=" not in cookie文本:
        return "Cookie 无效，缺少 skey 字段"

    用户QQ = 获取发送者QQ(event)
    if not 用户QQ:
        return "没有获取到管理员QQ，无法保存 Cookie"

    过期时间 = int(time.time()) + COOKIE有效期秒数
    状态值 = json.dumps({"cookie": cookie文本, "expire": 过期时间}, ensure_ascii=False)
    try:
        写入运行状态值(配置, COOKIE命名空间, 用户QQ, 状态值)
    except Exception as exc:
        logger.warning(f"网页群文件 Cookie 写入数据库失败：user_id={用户QQ}, error={exc}")
        return f"Cookie 保存失败：{exc}"
    logger.info(f"网页群文件 Cookie 已更新：user_id={用户QQ}")
    return f"Cookie 已保存，{COOKIE有效期秒数 // 86400} 天内有效"


def 读取用户Cookie(用户QQ: str, 配置: Any) -> str | None:
    状态值 = 读取运行状态值(配置, COOKIE命名空间, 用户QQ, "")
    if not 状态值:
        return None
    try:
        信息 = json.loads(状态值)
    except Exception:
        return None
    if not isinstance(信息, dict):
        return None
    if 安全整数(信息.get("expire"), 0) <= int(time.time()):
        try:
            写入运行状态值(配置, COOKIE命名空间, 用户QQ, "")
        except Exception:
            pass
        return None
    cookie文本 = str(信息.get("cookie") or "").strip()
    return cookie文本 or None


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


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group", "get_group_openid"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            # AstrMessageEvent 的 get_group 等可能是 async 方法，同步调用返回协程对象
            # 协程对象 str() 会变成 <coroutine object ... at 0x...>，污染会话标识
            if asyncio.iscoroutine(值):
                # 避免未 await 的协程被 GC 时打印 warning，主动 close
                值.close()
                continue
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("group_openid", "group_id", "group"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("group_openid") or 值.get("group_id") or 值.get("id")
            if 值:
                return str(值)
    return ""


async def 发送清理开始提示(event: Any, 文本: str) -> None:
    try:
        发送方法 = getattr(event, "send", None)
        if not callable(发送方法):
            return
        结果对象 = 文本
        plain_result = getattr(event, "plain_result", None)
        if callable(plain_result):
            结果对象 = plain_result(文本)
        结果 = 发送方法(结果对象)
        if asyncio.iscoroutine(结果) or hasattr(结果, "__await__"):
            await 结果
    except Exception as exc:
        logger.warning(f"群文件清理开始提示发送失败：error={exc}")


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


async def 执行网页清理(
    session: Any,
    群号: str,
    cookie文本: str,
) -> tuple[int, int, str | None]:
    """核心清理，返回 (成功文件数, 失败文件数, 错误信息或None)。"""
    skey = 提取skey(cookie文本)
    if not skey:
        return 0, 0, "Cookie 缺少 skey，请重新发送「登录群文件」重新登录"

    bkn = 计算bkn(skey)
    logger.info(f"[网页群文件] 开始清理 群号={群号} bkn={bkn}")

    全部文件 = await 拉取全部文件(session, 群号, bkn, cookie文本)
    if 全部文件 is None:
        return 0, 0, "Cookie 已失效或接口错误，请重新发送「登录群文件」重新登录"
    if not 全部文件:
        return 0, 0, None

    总数 = len(全部文件)
    批次列表 = [全部文件[开始:开始 + 每批删除数量] for 开始 in range(0, 总数, 每批删除数量)]
    logger.info(
        f"[网页群文件] 群 {群号} 共 {总数} 个文件 分 {len(批次列表)} 批删除（每批 {每批删除数量} 个）"
    )

    结果列表 = await asyncio.gather(
        *(删除文件批次(session, 群号, cookie文本, 批次) for 批次 in 批次列表)
    )
    成功批次数 = sum(1 for 结果 in 结果列表 if 结果)
    成功文件数 = sum(
        len(批次列表[序号])
        for 序号, 结果 in enumerate(结果列表)
        if 结果
    )
    logger.info(
        f"[网页群文件] 群 {群号} 删除完成 成功 {成功批次数}/{len(批次列表)} 批"
    )
    return 成功文件数, 总数 - 成功文件数, None


async def 清空指定群文件(event: Any, 群号: str, 配置: Any) -> str:
    用户QQ = 获取发送者QQ(event)
    if not 用户QQ:
        return "没有获取到管理员QQ"

    cookie文本 = 读取用户Cookie(用户QQ, 配置)
    if not cookie文本:
        return "你还没有登录群文件，请先发送「登录群文件」获取登录链接"

    if aiohttp is None:
        return "缺少 aiohttp 依赖，无法清理群文件"

    async with aiohttp.ClientSession() as session:
        成功, 失败, 错误 = await 执行网页清理(session, 群号, cookie文本)

    if 错误:
        return 错误
    if 成功 == 0 and 失败 == 0:
        return f"清理完成（群 {群号} 没有群文件）"
    return (
        f"清理完成，群 {群号} 共处理 {成功 + 失败} 个文件，"
        f"成功 {成功} 个，失败 {失败} 个"
    )


async def 清理全部已添加群(event: Any, 配置: Any) -> str:
    用户QQ = 获取发送者QQ(event)
    if not 用户QQ:
        return "没有获取到管理员QQ"

    cookie文本 = 读取用户Cookie(用户QQ, 配置)
    if not cookie文本:
        return "你还没有登录群文件，请先发送「登录群文件」获取登录链接"

    群号列表 = 读取待清理群列表(配置)
    if not 群号列表:
        return "还没有添加待清理群，请先发送「添加群聊 群号」添加目标群后再使用清理全部群文件"

    if aiohttp is None:
        return "缺少 aiohttp 依赖，无法清理群文件"

    await 发送清理开始提示(event, "正在清理群文件（全部）")

    成功群 = 0
    失败群 = 0
    文件成功 = 0
    文件失败 = 0
    失败详情: list[str] = []

    async with aiohttp.ClientSession() as session:
        for 群号 in 群号列表:
            try:
                成功, 失败, 错误 = await 执行网页清理(session, 群号, cookie文本)
                if 错误:
                    失败群 += 1
                    失败详情.append(f"{群号}：{错误}")
                    logger.warning(f"[网页群文件] 全部清理单群失败：group_id={群号}, error={错误}")
                else:
                    成功群 += 1
                    文件成功 += 成功
                    文件失败 += 失败
                    logger.info(
                        f"[网页群文件] 全部清理单群完成：group_id={群号}, success={成功}, failed={失败}"
                    )
            except Exception as exc:
                失败群 += 1
                失败详情.append(f"{群号}：{exc}")
                logger.warning(f"[网页群文件] 全部清理单群异常：group_id={群号}, error={exc}")

    行列表 = [
        f"全部群文件清理完成：群成功 {成功群} 个，群失败 {失败群} 个",
        f"文件成功 {文件成功} 个，文件失败 {文件失败} 个",
    ]
    if 失败详情:
        行列表.append("失败群：" + "；".join(失败详情))
    return "\n".join(行列表)
