"""
群聊管理 - 维护待清理群文件的目标群列表

通过 MySQL 运行状态表 mantou_runtime_state 存储管理员手动添加的群号列表，
供「清理全部群文件」使用。与适配器扩展接口版的 群文件清理.py 联动。

指令（仅群文件清理管理员白名单 QQ 可用）：
- 添加群聊 <群号> [群号...]：添加一个或多个群号到待清理列表
- 删除群聊 <群号> [群号...]：从待清理列表移除群号
- 查看群聊：列出当前已添加的待清理目标群
"""
from __future__ import annotations

import json
import re
from typing import Any

from astrbot.api import logger

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态值, 写入运行状态值


待清理群命名空间 = "cleanup_groups"
待清理群状态键 = "group_list"
数字群号规则 = re.compile(r"[1-9]\d{4,11}")

添加群聊规则 = re.compile(r"^添加群聊\s+(.+)$")
删除群聊规则 = re.compile(r"^删除群聊\s+(.+)$")
查看群聊命令 = "查看群聊"


async def 处理群聊管理指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None

    if 文本 == 查看群聊命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        return 格式化待清理群列表(配置)

    添加匹配 = 添加群聊规则.fullmatch(文本)
    if 添加匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        return 添加群聊(配置, 添加匹配.group(1))

    删除匹配 = 删除群聊规则.fullmatch(文本)
    if 删除匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用群聊管理"
        return 删除群聊(配置, 删除匹配.group(1))

    return None


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


def 添加群聊(配置: Any, 参数文本: str) -> str:
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
    return "\n".join(行列表)


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
    行列表 = [f"当前共 {len(当前列表)} 个待清理群："]
    for 序号, 群号 in enumerate(当前列表, start=1):
        行列表.append(f"{序号}. {群号}")
    行列表.append("\n发送「删除群聊 群号」可移除")
    return "\n".join(行列表)


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
