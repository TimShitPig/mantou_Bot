from __future__ import annotations

import asyncio
import json
import math
import re
import secrets
import string
import time
from datetime import datetime
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from astrbot.api import message_components as Comp
except Exception:
    Comp = None

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 获取发送者QQ, 获取群文件清理管理员QQ列表
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取布尔运行状态值, 写入布尔运行状态值, 读取运行状态值, 写入运行状态值


未激活提示 = "请查看群公告查看激活方法"
下载提示标记 = "正在下载中请稍等"
默认激活天数 = 30
最长激活天数 = 3650
用户激活数据库表名 = "mantou_user_activation"
用户激活卡密数据库表名 = "mantou_user_activation_cards"
用户免费额度数据库表名 = "mantou_user_free_quota"
运行状态数据库表名 = "mantou_runtime_state"
免费额度配置项 = "user_activation_daily_free_quota"
基础配置分类名 = "basic_settings"
数据库配置分类名 = "database_settings"
卡密同步配置分类名 = "card_key_sync_settings"
卡密同步已使用配置项 = "card_key_sync_used_cards"
卡密同步未使用配置项 = "card_key_sync_unused_cards"
卡密同步状态命名空间 = "card_key_sync"
卡密同步快照状态键 = "snapshot_v1"
卡密同步配置创建者 = "config_sync"
付费开关状态命名空间 = "paid_access"
全局付费开关命令配置 = {
    "开启付费": True,
    "开启收费": True,
    "关闭付费": False,
    "关闭收费": False,
}
群聊付费开关命令配置 = {
    "开启群聊付费": True,
    "开启群聊收费": True,
    "关闭群聊付费": False,
    "关闭群聊收费": False,
}
私聊付费开关命令配置 = {
    "开启私聊付费": True,
    "开启私聊收费": True,
    "关闭私聊付费": False,
    "关闭私聊收费": False,
}
配置字段分类映射 = {
    "group_file_cleanup_admin_qq": (基础配置分类名, "基础配置"),
    "番茄小说key": (基础配置分类名, "基础配置"),
    "user_activation_daily_free_quota": (基础配置分类名, "基础配置"),
    "user_activation_database_host": (数据库配置分类名, "数据库配置"),
    "user_activation_database_port": (数据库配置分类名, "数据库配置"),
    "user_activation_database_user": (数据库配置分类名, "数据库配置"),
    "user_activation_database_password": (数据库配置分类名, "数据库配置"),
    "user_activation_database_name": (数据库配置分类名, "数据库配置"),
    卡密同步已使用配置项: (卡密同步配置分类名, "卡密同步查看"),
    卡密同步未使用配置项: (卡密同步配置分类名, "卡密同步查看"),
}
配置字段默认值 = {
    "group_file_cleanup_admin_qq": [],
    "番茄小说key": "",
    "user_activation_daily_free_quota": "0",
    "user_activation_database_host": "",
    "user_activation_database_port": "3306",
    "user_activation_database_user": "",
    "user_activation_database_password": "",
}
用户操作命令规则 = re.compile(
    r"^(?:(?:用户)?(?:激活增加|激活减少|激活|重置|增加|减少)(?:\d+)?|(?:用户)?查询时间|(?:用户)?查询)(?:\s+\S+){0,20}$"
)
用户操作命令开头 = (
    "激活增加",
    "用户激活增加",
    "增加",
    "用户增加",
    "激活减少",
    "用户激活减少",
    "减少",
    "用户减少",
    "激活",
    "用户激活",
    "重置",
    "用户重置",
    "查询",
    "用户查询",
    "查询时间",
    "用户查询时间",
)
用户列表命令 = {"查询用户"}
用户列表下一页命令 = {"下一页", "下"}
用户列表上一页命令 = {"上一页", "上"}
用户列表翻页命令 = 用户列表下一页命令 | 用户列表上一页命令
生成卡密命令规则 = re.compile(r"^生成卡密(?:\s+(\d+))?$")
查询卡密命令规则 = re.compile(r"^查询卡密(?:\s+\S+){0,20}$")
复制卡密命令规则 = re.compile(r"^复制(?:\s*(\d+)\s*天?)?$")
查询卡密菜单命令 = "查询卡密"
卡密查询选择命令 = {"1": "used", "2": "unused"}
卡密查询返回命令 = {"0"}
卡密规则 = re.compile(r"^(?=.*[A-Z])[A-Z0-9]{12}$")
卡密候选规则 = re.compile(r"(?=([A-Z0-9]{12}))")
卡密字符集 = "".join(字符 for 字符 in string.ascii_uppercase + string.digits if 字符 not in {"0", "1", "I", "O"})
数字规则 = re.compile(r"\d+")
用户编号规则 = re.compile(r"^[A-Za-z0-9_-]{5,64}$")
需激活文本命令 = {"随机英文单词", "随机一言", "疯狂星期四", "古诗词名句"}
用户列表每页数量 = 10
卡密列表每页数量 = 5
卡密生成最大数量 = 200
列表分隔线 = "--------------------"
用户列表翻页状态: dict[str, dict[str, Any]] = {}
卡密查询翻页状态: dict[str, dict[str, Any]] = {}
卡密查询选择状态: dict[str, dict[str, Any]] = {}
免费额度状态锁 = asyncio.Lock()
免费额度最近放行: dict[str, dict[str, int | str]] = {}


async def 处理用户激活(event: Any, 命令文本: str, 配置: Any, context: Any = None) -> str | None:
    try:
        卡密回复 = await 处理卡密功能(event, 命令文本, 配置, context)
        if 卡密回复 is not None:
            return 卡密回复
    except Exception as exc:
        logger.warning(f"处理卡密功能异常：error={exc}")

    try:
        付费开关回复 = 处理付费开关指令(event, 命令文本, 配置)
        if 付费开关回复 is not None:
            return 付费开关回复
    except Exception as exc:
        logger.warning(f"处理付费开关指令异常：error={exc}")

    列表命令 = 提取用户列表命令文本(event, 命令文本)
    if 列表命令 in 用户列表命令 or 列表命令 in 用户列表翻页命令:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限查询激活用户"
        return await 处理查询用户列表(event, 配置, 翻页方向=获取翻页方向(列表命令))

    激活参数 = 解析激活命令(event, 命令文本, context)
    if 激活参数 is None:
        return None
    记录用户激活诊断(event, 命令文本, 激活参数, context)
    操作 = 激活参数.get("action") or "激活"
    if 操作 == "查询":
        return await 处理查询时间(event, 激活参数, 配置)

    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用用户激活"

    目标用户列表 = 获取目标用户列表(激活参数)
    if not 目标用户列表:
        动作名 = 获取用户操作显示名(操作)
        return f"用户{动作名}失败：请 @ 要{动作名}的用户"

    群号 = 获取群号(event)
    if not 群号:
        动作名 = 获取用户操作显示名(操作)
        return f"用户{动作名}失败：只能在群聊中{动作名}用户"

    if 操作 == "重置":
        成功用户: list[str] = []
        失败用户: list[tuple[str, Exception]] = []
        for 目标用户 in 目标用户列表:
            try:
                await 删除激活记录(配置, 群号, 目标用户)
                成功用户.append(目标用户)
            except Exception as exc:
                失败用户.append((目标用户, exc))
                logger.warning(f"用户激活重置失败：group_id={群号}, user_id={目标用户}, error={exc}")
        if len(目标用户列表) == 1:
            if 成功用户:
                return f"已取消用户激活：{成功用户[0]}"
            return f"用户重置失败：{失败用户[0][1]}"
        return 格式化批量重置结果(成功用户, 失败用户)

    if 操作 in {"增加", "减少"}:
        天数 = 安全整数(激活参数.get("days"), 默认激活天数)
        if 天数 <= 0:
            return "用户激活调整失败：天数必须是正整数"
        if 天数 > 最长激活天数:
            return f"用户激活调整失败：调整天数不能超过 {最长激活天数} 天"
        return await 处理激活时间调整(event, 配置, 群号, 目标用户列表, 操作, 天数)

    天数 = 安全整数(激活参数.get("days"), 默认激活天数)
    if 天数 <= 0:
        return "用户激活失败：激活天数必须是正整数"
    if 天数 > 最长激活天数:
        return f"用户激活失败：激活天数不能超过 {最长激活天数} 天"

    到期时间 = int(time.time()) + 天数 * 86400
    成功用户: list[str] = []
    已激活用户: list[dict[str, Any]] = []
    失败用户: list[tuple[str, Exception]] = []
    for 目标用户 in 目标用户列表:
        try:
            原记录 = await 读取激活记录(配置, 群号, 目标用户)
            if 原记录:
                已激活用户.append({"user_id": 目标用户, **原记录})
                continue
            await 写入激活记录(配置, 群号, 目标用户, 到期时间)
            成功用户.append(目标用户)
        except Exception as exc:
            失败用户.append((目标用户, exc))
            logger.warning(f"用户激活写入失败：group_id={群号}, user_id={目标用户}, error={exc}")

    if len(目标用户列表) == 1:
        if 成功用户:
            return "\n".join(
                [
                    f"已激活用户：{成功用户[0]}",
                    f"有效期：{天数} 天",
                    f"到期时间：{格式化时间戳(到期时间)}",
                ]
            )
        if 已激活用户:
            return 格式化单用户已激活回复(已激活用户[0])
        return f"用户激活失败：{失败用户[0][1]}"

    return 格式化批量激活结果(成功用户, 已激活用户, 失败用户, 天数, 到期时间)


def 用户激活回复需要同步卡密配置(回复内容: Any) -> bool:
    文本 = str(回复内容 or "")
    return any(标记 in 文本 for 标记 in ("已生成卡密", "卡密激活成功", "卡密无效或已使用"))


async def 同步卡密配置视图(配置: Any) -> bool:
    配置字典 = 获取配置字典(配置)
    if 配置字典 is None:
        return False
    try:
        记录列表 = await asyncio.to_thread(同步数据库卡密到配置, 配置字典)
    except RuntimeError as exc:
        文本 = str(exc)
        if "用户激活数据库配置不完整" not in 文本 and "缺少 pymysql" not in 文本:
            logger.warning(f"卡密配置同步失败：error={exc}")
        return False
    except Exception as exc:
        logger.warning(f"卡密配置同步失败：error={exc}")
        return False
    return bool(记录列表)


def 迁移旧版配置分类(配置: Any) -> bool:
    配置字典 = 获取配置字典(配置)
    if 配置字典 is None:
        return False

    已变更 = False
    for 字段名, 默认值 in 配置字段默认值.items():
        if 字段名 not in 配置字典:
            continue
        旧值 = 配置字典.get(字段名)
        if 配置值等同默认(旧值, 默认值):
            continue
        分类名 = 配置字段分类映射.get(字段名, (基础配置分类名,))[0]
        分类 = 配置字典.get(分类名)
        if not isinstance(分类, dict):
            分类 = {}
            配置字典[分类名] = 分类
        当前值 = 分类.get(字段名)
        if 字段名 in 分类 and not 配置值等同默认(当前值, 默认值):
            continue
        分类[字段名] = 旧值
        已变更 = True
    return 已变更


def 配置值等同默认(值: Any, 默认值: Any) -> bool:
    if isinstance(默认值, list):
        return not 值
    return str(值 if 值 is not None else "").strip() == str(默认值).strip()


async def 处理查询时间(event: Any, 激活参数: dict[str, Any], 配置: Any) -> str:
    发送者 = 获取发送者QQ(event)
    目标用户列表 = 获取目标用户列表(激活参数)
    if not 目标用户列表 and 发送者:
        目标用户列表 = [发送者]
    if not 目标用户列表:
        return "用户查询失败：没有获取到用户QQ"

    if any(目标用户 != 发送者 for 目标用户 in 目标用户列表) and not 是群文件清理管理员(event, 配置):
        return "没有权限查询其他用户激活时间"

    群号 = 获取群号(event) or "private"
    结果列表 = [await 获取单用户查询时间回复(配置, 群号, 目标用户) for 目标用户 in 目标用户列表]
    return "\n\n".join(结果列表)


async def 获取单用户查询时间回复(配置: Any, 群号: str, 目标用户: str) -> str:
    if 目标用户 in 获取群文件清理管理员QQ列表(配置):
        return "\n".join([f"用户：{目标用户}", "状态：管理员，无需激活"])

    try:
        激活记录 = await 读取激活查询详情(配置, 群号, 目标用户)
    except Exception as exc:
        logger.warning(f"用户激活查询失败：group_id={群号}, user_id={目标用户}, error={exc}")
        return f"用户查询失败：{exc}"

    if not 激活记录 or 安全整数(激活记录.get("expires_at"), 0) <= 0:
        return "\n".join([f"用户：{目标用户}", "状态：未激活"])

    return 格式化单用户查询回复(目标用户, 激活记录)


async def 处理激活时间调整(
    event: Any,
    配置: Any,
    群号: str,
    目标用户列表: list[str],
    操作: str,
    天数: int,
) -> str:
    成功用户: list[dict[str, Any]] = []
    过期用户: list[str] = []
    失败用户: list[tuple[str, Exception]] = []
    调整秒数 = 天数 * 86400
    当前时间 = int(time.time())

    for 目标用户 in 目标用户列表:
        try:
            激活记录 = await 读取激活记录(配置, 群号, 目标用户)
            if not 激活记录:
                raise RuntimeError("用户未激活，无法调整时间")
            原到期时间 = 安全整数(激活记录.get("expires_at"), 0)
            新到期时间 = 原到期时间 + 调整秒数 if 操作 == "增加" else 原到期时间 - 调整秒数
            if 新到期时间 <= 当前时间:
                await 删除激活记录(配置, 群号, 目标用户)
                过期用户.append(目标用户)
                continue
            await 写入激活记录(配置, 群号, 目标用户, 新到期时间)
            成功用户.append({"user_id": 目标用户, "expires_at": 新到期时间})
        except Exception as exc:
            失败用户.append((目标用户, exc))
            logger.warning(f"用户激活时间调整失败：action={操作}, group_id={群号}, user_id={目标用户}, error={exc}")

    if len(目标用户列表) == 1:
        if 成功用户:
            目标用户 = 成功用户[0]["user_id"]
            动作文本 = "增加" if 操作 == "增加" else "减少"
            return "\n".join(
                [
                    f"已{动作文本}用户激活时间：{目标用户}",
                    f"调整天数：{天数} 天",
                    f"到期时间：{格式化时间戳(成功用户[0]['expires_at'])}",
                ]
            )
        if 过期用户:
            return f"已减少用户激活时间：{过期用户[0]}\n调整后已到期，已取消激活"
        return f"用户激活调整失败：{失败用户[0][1]}"

    return 格式化批量调整结果(操作, 成功用户, 过期用户, 失败用户, 天数)


async def 处理查询用户列表(event: Any, 配置: Any, 下一页: bool = False, 翻页方向: int = 0) -> str:
    群号 = 获取群号(event)
    if not 群号:
        return "查询用户失败：只能在群聊中使用"

    if 下一页 and 翻页方向 == 0:
        翻页方向 = 1
    状态键 = 获取用户列表翻页状态键(event, 群号)
    if 翻页方向 == 0:
        卡密查询翻页状态.pop(状态键, None)
        卡密查询选择状态.pop(状态键, None)
    if 翻页方向 != 0 and 状态键 not in 用户列表翻页状态:
        return "没有可翻页的查询用户结果，请先发送“查询用户”"

    页码 = 安全整数(用户列表翻页状态.get(状态键, {}).get("page"), 1) + 翻页方向 if 翻页方向 else 1
    用户列表 = await 列出激活用户记录(配置, 群号)
    if not 用户列表:
        用户列表翻页状态.pop(状态键, None)
        return "当前群没有已激活用户"

    总页数 = max(1, (len(用户列表) + 用户列表每页数量 - 1) // 用户列表每页数量)
    边界提示 = ""
    if 页码 < 1:
        页码 = 1
        边界提示 = "已经是第一页"
    elif 页码 > 总页数:
        页码 = 总页数
        边界提示 = "已经是最后一页"
    用户列表翻页状态[状态键] = {"page": 页码}
    return 格式化激活用户列表(用户列表, 页码, 总页数, 边界提示)


async def 处理卡密功能(event: Any, 命令文本: str, 配置: Any, context: Any = None) -> str | None:
    卡密文本 = 提取卡密命令文本(event, 命令文本)

    if 卡密文本 in 卡密查询选择命令 or 卡密文本 in 卡密查询返回命令:
        群号 = 获取群号(event) or "private"
        状态键 = 获取用户列表翻页状态键(event, 群号)
        if 状态键 not in 卡密查询选择状态:
            return None
        if not 是群文件清理管理员(event, 配置):
            return "没有权限查询卡密"
        return await 处理查询卡密菜单选择(event, 卡密文本, 配置, context)

    if 卡密文本 in 用户列表翻页命令:
        群号 = 获取群号(event) or "private"
        状态键 = 获取用户列表翻页状态键(event, 群号)
        if 状态键 not in 卡密查询翻页状态:
            return None
        if not 是群文件清理管理员(event, 配置):
            return "没有权限查询卡密"
        return await 处理查询卡密(event, 卡密文本, 配置, context, 翻页方向=获取翻页方向(卡密文本))

    if 复制卡密命令规则.fullmatch(卡密文本):
        群号 = 获取群号(event) or "private"
        状态键 = 获取用户列表翻页状态键(event, 群号)
        if 状态键 not in 卡密查询翻页状态:
            return None
        if not 是群文件清理管理员(event, 配置):
            return "没有权限查询卡密"
        return await 处理复制卡密(event, 卡密文本, 配置)

    if 卡密文本.startswith("生成卡密"):
        if not 是群文件清理管理员(event, 配置):
            return "没有权限生成卡密"
        return await 处理生成卡密(event, 卡密文本, 配置)

    if 卡密文本.startswith("查询卡密"):
        if not 是群文件清理管理员(event, 配置):
            return "没有权限查询卡密"
        if 卡密文本 == 查询卡密菜单命令:
            return 打开查询卡密菜单(event)
        return await 处理查询卡密(event, 卡密文本, 配置, context)

    卡密候选列表 = 提取卡密候选列表(卡密文本 or 命令文本)
    if 卡密候选列表:
        return await 处理使用卡密候选列表(event, 配置, 卡密候选列表)
    return None


async def 处理生成卡密(event: Any, 命令文本: str, 配置: Any) -> str:
    匹配 = 生成卡密命令规则.fullmatch(命令文本)
    if not 匹配:
        return "卡密生成失败：格式为“生成卡密”或“生成卡密 数量”"

    数量 = 安全整数(匹配.group(1), 1)
    if 数量 <= 0:
        return "卡密生成失败：数量必须是正整数"
    if 数量 > 卡密生成最大数量:
        return f"卡密生成失败：一次最多生成 {卡密生成最大数量} 个"

    群号 = 获取群号(event) or "private"
    创建者 = 获取发送者QQ(event)
    if not 创建者:
        return "卡密生成失败：没有获取到管理员QQ"

    try:
        卡密列表 = await 生成并保存卡密列表(配置, 群号, 创建者, 数量, 默认激活天数)
    except Exception as exc:
        logger.warning(f"卡密生成失败：group_id={群号}, count={数量}, error={exc}")
        return f"卡密生成失败：{exc}"

    return "\n".join(
        [
            f"已生成卡密：{len(卡密列表)} 个",
            f"有效期：{默认激活天数} 天",
            *卡密列表,
        ]
    )


def 打开查询卡密菜单(event: Any) -> str:
    群号 = 获取群号(event) or "private"
    状态键 = 获取用户列表翻页状态键(event, 群号)
    用户列表翻页状态.pop(状态键, None)
    卡密查询翻页状态.pop(状态键, None)
    卡密查询选择状态[状态键] = {"created_at": int(time.time())}
    return "\n".join(
        [
            "查询卡密",
            "1. 已使用",
            "2. 未使用",
            "0. 返回上一步",
        ]
    )


async def 处理查询卡密菜单选择(event: Any, 命令文本: str, 配置: Any, context: Any = None) -> str:
    群号 = 获取群号(event) or "private"
    状态键 = 获取用户列表翻页状态键(event, 群号)
    if 命令文本 in 卡密查询返回命令:
        卡密查询选择状态.pop(状态键, None)
        卡密查询翻页状态.pop(状态键, None)
        return "已返回上一步"

    状态 = 卡密查询选择命令.get(命令文本)
    if not 状态:
        return 打开查询卡密菜单(event)
    卡密查询选择状态.pop(状态键, None)
    查询文本 = "查询卡密 使用" if 状态 == "used" else "查询卡密 没使用"
    return await 处理查询卡密(event, 查询文本, 配置, context)


async def 处理使用卡密(event: Any, 配置: Any, 卡密: str) -> str | None:
    return await 处理使用卡密候选列表(event, 配置, [卡密])


async def 处理使用卡密候选列表(event: Any, 配置: Any, 卡密候选列表: list[str]) -> str | None:
    用户编号 = 获取发送者QQ(event)
    if not 用户编号:
        return "卡密激活失败：没有获取到用户QQ"

    群号 = 获取群号(event) or "private"
    卡密候选列表 = 去重保序([规范化卡密(卡密) for 卡密 in 卡密候选列表 if 规范化卡密(卡密)])
    if not 卡密候选列表:
        return None
    try:
        卡密候选列表 = await asyncio.to_thread(筛选存在数据库卡密列表, 配置, 群号, 卡密候选列表)
    except Exception as exc:
        logger.warning(f"卡密存在性检查失败：group_id={群号}, user_id={用户编号}, error={exc}")
        return f"卡密激活失败：{exc}"
    if not 卡密候选列表:
        return None

    if 是群文件清理管理员(event, 配置):
        return "管理员无需激活，不消耗卡密"

    最后异常: Exception | None = None
    已收到数据库响应 = False
    for 卡密 in 卡密候选列表:
        try:
            结果 = await asyncio.to_thread(使用数据库卡密激活, 配置, 群号, 用户编号, 卡密)
        except Exception as exc:
            最后异常 = exc
            logger.warning(f"卡密激活失败：group_id={群号}, user_id={用户编号}, card={卡密}, error={exc}")
            continue

        已收到数据库响应 = True
        状态 = 结果.get("status")
        if 状态 == "already":
            return 格式化单用户已激活回复({"user_id": 用户编号, **结果.get("record", {})})
        if 状态 == "used":
            return "\n".join(
                [
                    "卡密激活成功",
                    f"有效期：{安全整数(结果.get('days'), 默认激活天数)} 天",
                    f"到期时间：{格式化时间戳(安全整数(结果.get('expires_at'), 0))}",
                ]
            )

    if 最后异常 is not None and (len(卡密候选列表) == 1 or not 已收到数据库响应):
        return f"卡密激活失败：{最后异常}"
    return "卡密无效或已使用"


async def 处理查询卡密(
    event: Any,
    命令文本: str,
    配置: Any,
    context: Any = None,
    下一页: bool = False,
    翻页方向: int = 0,
) -> str:
    群号 = 获取群号(event) or "private"
    状态键 = 获取用户列表翻页状态键(event, 群号)

    if 下一页 and 翻页方向 == 0:
        翻页方向 = 1
    if 翻页方向 != 0:
        状态 = 卡密查询翻页状态.get(状态键)
        if not 状态:
            return "没有可翻页的卡密查询结果，请先发送“查询卡密”"
        页码 = 安全整数(状态.get("page"), 1) + 翻页方向
        查询参数 = 状态.get("query") if isinstance(状态.get("query"), dict) else {}
    else:
        查询参数 = 解析查询卡密命令(event, 命令文本, context)
        if 查询参数 is None:
            return "卡密查询失败：格式为“查询卡密”“查询卡密 已使用”“查询卡密 未使用”“查询卡密 QQ号”或“查询卡密 卡密”"
        页码 = 1
        用户列表翻页状态.pop(状态键, None)
        卡密查询选择状态.pop(状态键, None)

    try:
        卡密列表 = await 列出卡密记录(配置, 群号, 查询参数)
    except Exception as exc:
        logger.warning(f"卡密查询失败：group_id={群号}, query={查询参数}, error={exc}")
        return f"卡密查询失败：{exc}"

    if not 卡密列表:
        卡密查询翻页状态.pop(状态键, None)
        return "没有符合条件的卡密"

    总页数 = max(1, (len(卡密列表) + 卡密列表每页数量 - 1) // 卡密列表每页数量)
    边界提示 = ""
    if 页码 < 1:
        页码 = 1
        边界提示 = "已经是第一页"
    elif 页码 > 总页数:
        页码 = 总页数
        边界提示 = "已经是最后一页"
    卡密查询翻页状态[状态键] = {"page": 页码, "query": 查询参数}
    return 格式化卡密列表(卡密列表, 查询参数, 页码, 总页数, 边界提示)


async def 处理复制卡密(event: Any, 命令文本: str, 配置: Any) -> str:
    群号 = 获取群号(event) or "private"
    状态键 = 获取用户列表翻页状态键(event, 群号)
    状态 = 卡密查询翻页状态.get(状态键)
    if not 状态:
        return "没有可复制的卡密查询结果，请先发送“查询卡密”"
    查询参数 = 状态.get("query") if isinstance(状态.get("query"), dict) else {}
    匹配 = 复制卡密命令规则.fullmatch(str(命令文本 or "").strip())
    天数筛选 = 安全整数(匹配.group(1), 0) if 匹配 and 匹配.group(1) else 0

    try:
        卡密列表 = await 列出卡密记录(配置, 群号, 查询参数)
    except Exception as exc:
        logger.warning(f"卡密复制失败：group_id={群号}, query={查询参数}, days={天数筛选}, error={exc}")
        return f"卡密复制失败：{exc}"
    if 天数筛选 > 0:
        卡密列表 = [记录 for 记录 in 卡密列表 if 安全整数(记录.get("days"), 默认激活天数) == 天数筛选]
    if not 卡密列表:
        return "没有符合条件的卡密"
    return 格式化复制卡密列表(卡密列表, 天数筛选)


def 获取目标用户列表(激活参数: dict[str, Any]) -> list[str]:
    目标用户列表 = 激活参数.get("target_user_ids")
    if isinstance(目标用户列表, list):
        return 去重保序([str(用户).strip() for 用户 in 目标用户列表 if str(用户).strip()])

    目标用户 = str(激活参数.get("target_user_id") or "").strip()
    return [目标用户] if 目标用户 else []


def 获取用户操作显示名(操作: str) -> str:
    return {"增加": "激活增加", "减少": "激活减少", "重置": "重置"}.get(操作, "激活")


def 格式化批量激活结果(
    成功用户: list[str],
    已激活用户: list[dict[str, Any]],
    失败用户: list[tuple[str, Exception]],
    天数: int,
    到期时间: int,
) -> str:
    行列表 = [
        f"用户激活完成：成功 {len(成功用户)} 个，已激活 {len(已激活用户)} 个，失败 {len(失败用户)} 个"
    ]
    if 成功用户:
        行列表.extend(
            [
                f"已激活用户：{格式化用户列表(成功用户)}",
                f"有效期：{天数} 天",
                f"到期时间：{格式化时间戳(到期时间)}",
            ]
        )
    if 已激活用户:
        行列表.append(f"已激活用户（未重复激活）：{格式化用户列表([str(记录['user_id']) for 记录 in 已激活用户])}")
    if 失败用户:
        行列表.append("失败用户：" + "；".join(f"{用户}：{错误}" for 用户, 错误 in 失败用户))
    return "\n".join(行列表)


def 格式化单用户已激活回复(激活记录: dict[str, Any]) -> str:
    到期时间 = 安全整数(激活记录.get("expires_at"), 0)
    return "\n".join(
        [
            f"用户已激活：{激活记录.get('user_id')}",
            "不会重复激活",
            f"到期时间：{格式化时间戳(到期时间)}",
        ]
    )


def 格式化单用户查询回复(目标用户: str, 激活记录: dict[str, Any]) -> str:
    激活时间 = 安全整数(激活记录.get("updated_at"), 0)
    到期时间 = 安全整数(激活记录.get("expires_at"), 0)
    激活天数 = 安全整数(激活记录.get("days"), 0)
    剩余秒数 = max(0, 到期时间 - int(time.time()))
    卡密号 = str(激活记录.get("card_key") or "").strip() or "未知"
    return "\n".join(
        [
            f"QQ号：{目标用户}",
            f"卡密号：{卡密号}",
            f"激活天数：{激活天数 if 激活天数 > 0 else '未知'} 天",
            f"剩余时间：{格式化剩余时间(剩余秒数)}",
            f"激活时间：{格式化时间戳(激活时间) if 激活时间 > 0 else '未知'}",
            f"结束时间：{格式化时间戳(到期时间)}",
        ]
    )


def 格式化批量调整结果(
    操作: str,
    成功用户: list[dict[str, Any]],
    过期用户: list[str],
    失败用户: list[tuple[str, Exception]],
    天数: int,
) -> str:
    动作文本 = "增加" if 操作 == "增加" else "减少"
    行列表 = [f"用户激活时间{动作文本}完成：成功 {len(成功用户)} 个，到期取消 {len(过期用户)} 个，失败 {len(失败用户)} 个"]
    if 成功用户:
        行列表.append(f"已{动作文本}用户：{格式化用户列表([str(记录['user_id']) for 记录 in 成功用户])}")
        行列表.append(f"调整天数：{天数} 天")
    if 过期用户:
        行列表.append(f"已到期并取消激活：{格式化用户列表(过期用户)}")
    if 失败用户:
        行列表.append("失败用户：" + "；".join(f"{用户}：{错误}" for 用户, 错误 in 失败用户))
    return "\n".join(行列表)


def 格式化批量重置结果(成功用户: list[str], 失败用户: list[tuple[str, Exception]]) -> str:
    行列表 = [f"用户重置完成：成功 {len(成功用户)} 个，失败 {len(失败用户)} 个"]
    if 成功用户:
        行列表.append(f"已取消用户激活：{格式化用户列表(成功用户)}")
    if 失败用户:
        行列表.append("失败用户：" + "；".join(f"{用户}：{错误}" for 用户, 错误 in 失败用户))
    return "\n".join(行列表)


def 格式化用户列表(用户列表: list[str]) -> str:
    return "、".join(用户列表)


def 获取用户列表翻页状态键(event: Any, 群号: str) -> str:
    return f"{群号}:{获取发送者QQ(event)}"


def 获取翻页方向(命令文本: str) -> int:
    文本 = str(命令文本 or "").strip()
    if 文本 in 用户列表下一页命令:
        return 1
    if 文本 in 用户列表上一页命令:
        return -1
    return 0


async def 列出激活用户记录(配置: Any, 群号: str) -> list[dict[str, int | str]]:
    return await asyncio.to_thread(列出数据库激活用户记录, 配置, 群号)


def 格式化激活用户列表(用户列表: list[dict[str, Any]], 页码: int, 总页数: int, 边界提示: str | bool = "") -> str:
    当前时间 = int(time.time())
    用户列表 = sorted(
        用户列表,
        key=lambda 记录: (
            安全整数(记录.get("expires_at"), 0),
            str(记录.get("user_id") or ""),
        ),
    )
    开始 = (页码 - 1) * 用户列表每页数量
    当前页用户 = 用户列表[开始 : 开始 + 用户列表每页数量]
    行列表 = [f"已激活用户列表：第 {页码} / {总页数} 页，共 {len(用户列表)} 个"]
    用户块: list[str] = []
    for 序号, 记录 in enumerate(当前页用户, start=开始 + 1):
        到期时间 = 安全整数(记录.get("expires_at"), 0)
        卡密号 = str(记录.get("card_key") or "").strip() or "未知"
        剩余秒数 = max(0, 到期时间 - 当前时间)
        用户块.append("\n".join([
            f"{序号}. QQ：{记录.get('user_id')}",
            f"卡密：{卡密号}",
            f"剩余时间：{格式化剩余时间(剩余秒数)}",
        ]))
    if 用户块:
        行列表.append(f"\n{列表分隔线}\n".join(用户块))
    if 页码 < 总页数:
        行列表.append("发送“下一页”或“下”查看更多")
    if isinstance(边界提示, str) and 边界提示:
        行列表.append(边界提示)
    elif 边界提示 is True:
        行列表.append("已经是最后一页")
    return "\n".join(行列表)


def 格式化卡密列表(
    卡密列表: list[dict[str, Any]],
    查询参数: dict[str, Any],
    页码: int,
    总页数: int,
    边界提示: str | bool = "",
) -> str:
    开始 = (页码 - 1) * 卡密列表每页数量
    当前页卡密 = 卡密列表[开始 : 开始 + 卡密列表每页数量]
    状态 = 查询参数.get("status")
    标题 = "已使用卡密列表" if 状态 == "used" else "未使用卡密列表" if 状态 == "unused" else "卡密列表"
    行列表 = [f"{标题}：第 {页码} / {总页数} 页，共 {len(卡密列表)} 个"]
    卡密块: list[str] = []
    for 记录 in 当前页卡密:
        使用者 = str(记录.get("used_by") or "").strip()
        天数 = 安全整数(记录.get("days"), 默认激活天数)
        使用状态 = 使用者 if 使用者 else "未使用"
        卡密块.append("\n".join([str(记录.get("card_key") or ""), f"{使用状态}----{天数}天"]))
    if 卡密块:
        行列表.append(f"\n{列表分隔线}\n".join(卡密块))
    if 页码 < 总页数:
        行列表.append("发送“下一页”或“下”查看更多")
    if isinstance(边界提示, str) and 边界提示:
        行列表.append(边界提示)
    elif 边界提示 is True:
        行列表.append("已经是最后一页")
    return "\n".join(行列表)


def 格式化复制卡密列表(卡密列表: list[dict[str, Any]], 天数筛选: int = 0) -> str:
    if 天数筛选 > 0:
        有效期文本 = f"{天数筛选} 天"
    else:
        天数集合 = {安全整数(记录.get("days"), 默认激活天数) for 记录 in 卡密列表}
        有效期文本 = f"{next(iter(天数集合))} 天" if len(天数集合) == 1 else "全部"
    return "\n".join(
        [
            f"已复制卡密：{len(卡密列表)} 个",
            f"有效期：{有效期文本}",
            *[str(记录.get("card_key") or "").strip() for 记录 in 卡密列表 if str(记录.get("card_key") or "").strip()],
        ]
    )


def 解析查询卡密命令(event: Any, 命令文本: str, context: Any = None) -> dict[str, Any] | None:
    if not 查询卡密命令规则.fullmatch(命令文本):
        return None

    项目列表 = str(命令文本 or "").split()[1:]
    状态 = "unused"
    卡密 = ""
    用户列表: list[str] = []
    for 项目 in 项目列表:
        项目文本 = str(项目 or "").strip()
        if not 项目文本:
            continue
        if 项目文本 in {"已使用", "使用", "已用", "已使用的", "使用的", "已用的", "已使用卡密", "使用的卡密"}:
            状态 = "used"
            continue
        if 项目文本 in {"未使用", "没使用", "未用", "未使用的", "没使用的", "未用的", "未使用卡密", "没使用的卡密"}:
            状态 = "unused"
            continue
        规范卡密 = 规范化卡密(项目文本)
        if 规范卡密:
            卡密 = 规范卡密
            continue
        用户 = 规范化用户编号(项目文本)
        if 用户:
            用户列表.append(用户)

    At用户列表 = 提取被艾特用户QQ列表(event, 获取At用户列表(event), context)
    if At用户列表:
        用户列表 = At用户列表

    return {
        "status": 状态,
        "card_key": 卡密,
        "user_ids": 去重保序(用户列表),
    }


async def 获取未激活拦截回复(event: Any, 配置: Any) -> str | None:
    if not 付费模式是否开启(event, 配置):
        return None
    if await 用户可使用功能(event, 配置):
        return None
    if await 尝试消耗每日免费额度(event, 配置):
        return None
    return await 获取免费额度用尽拦截回复(event, 配置)


async def 用户可使用功能(event: Any, 配置: Any) -> bool:
    if 是群文件清理管理员(event, 配置):
        return True

    用户编号 = 获取发送者QQ(event)
    if not 用户编号:
        return False
    群号 = 获取群号(event) or "private"

    try:
        到期时间 = await 读取激活到期时间(配置, 群号, 用户编号)
    except Exception as exc:
        logger.warning(f"用户激活读取失败：group_id={群号}, user_id={用户编号}, error={exc}")
        return False
    return 到期时间 >= int(time.time())


async def 尝试消耗每日免费额度(event: Any, 配置: Any) -> bool:
    每日限额 = 获取每日免费额度(配置)
    if 每日限额 <= 0:
        return False

    用户编号 = 获取发送者QQ(event)
    if not 用户编号:
        return False
    群号 = 获取群号(event) or "private"

    try:
        async with 免费额度状态锁:
            已使用 = await asyncio.to_thread(消耗每日免费额度记录, 配置, 群号, 用户编号, 每日限额)
    except Exception as exc:
        logger.warning(f"用户免费额度消耗失败：group_id={群号}, user_id={用户编号}, error={exc}")
        return False
    if 已使用 <= 0:
        return False

    免费额度最近放行[获取免费额度记录键(群号, 用户编号)] = {
        "date": 获取免费额度日期(),
        "quota": 每日限额,
        "used": 已使用,
        "timestamp": int(time.time()),
    }
    logger.debug(f"用户免费额度放行：group_id={群号}, user_id={用户编号}, daily_quota={每日限额}, used={已使用}")
    return True


async def 获取免费额度用尽拦截回复(event: Any, 配置: Any) -> str:
    每日限额 = 获取每日免费额度(配置)
    if 每日限额 <= 0:
        return 未激活提示

    用户编号 = 获取发送者QQ(event)
    if not 用户编号:
        return 未激活提示
    群号 = 获取群号(event) or "private"

    try:
        async with 免费额度状态锁:
            已使用 = await asyncio.to_thread(读取每日免费额度已使用, 配置, 群号, 用户编号)
    except Exception as exc:
        logger.warning(f"用户免费额度读取失败：group_id={群号}, user_id={用户编号}, error={exc}")
        return 未激活提示
    if 已使用 >= 每日限额:
        return 格式化免费额度用尽提示(每日限额)
    return 未激活提示


async def 获取下载免费额度提示(event: Any, 配置: Any) -> str:
    if not 付费模式是否开启(event, 配置):
        return ""
    每日限额 = 获取每日免费额度(配置)
    if 每日限额 <= 0:
        return ""

    用户编号 = 获取发送者QQ(event)
    if not 用户编号:
        return ""
    群号 = 获取群号(event) or "private"
    记录 = 免费额度最近放行.get(获取免费额度记录键(群号, 用户编号)) or {}
    if str(记录.get("date") or "") != 获取免费额度日期():
        return ""
    if 安全整数(记录.get("quota"), 0) != 每日限额:
        return ""
    if int(time.time()) - 安全整数(记录.get("timestamp"), 0) > 300:
        return ""

    已使用 = 安全整数(记录.get("used"), 0)
    if 已使用 <= 0:
        return ""
    剩余 = max(0, 每日限额 - 已使用)
    return 格式化下载免费额度提示(剩余)


def 附加下载免费额度提示(回复内容: str, 免费额度提示: str) -> str:
    if not 免费额度提示 or 下载提示标记 not in str(回复内容 or ""):
        return 回复内容
    if 免费额度提示 in 回复内容:
        return 回复内容
    return f"{str(回复内容).rstrip()}\n{免费额度提示}"


def 处理付费开关指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if 文本 not in 全局付费开关命令配置 and 文本 not in 群聊付费开关命令配置 and 文本 not in 私聊付费开关命令配置:
        return None
    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用付费开关"

    数据库可用 = True
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 获取数据库配置 as 获取运行状态数据库配置
        获取运行状态数据库配置(配置)
    except Exception:
        数据库可用 = False

    if 文本 in 全局付费开关命令配置:
        是否开启 = 全局付费开关命令配置[文本]
        状态键 = 获取全局付费开关状态键()
        if not 数据库可用:
            if 是否开启:
                return "全局收费模式开启失败：数据库未配置，请先在插件配置中填写数据库信息"
            return "全局收费模式关闭失败：数据库未配置，请先在插件配置中填写数据库信息"
        try:
            写入运行状态值(配置, 付费开关状态命名空间, 状态键, "on" if 是否开启 else "off")
        except Exception as exc:
            logger.warning(f"全局付费开关写入数据库失败：enabled={是否开启}, error={exc}")
            return f"全局付费开关失败：{exc}"
        if 是否开启:
            return "已开启全局收费模式，群聊和私聊未激活用户均需激活或使用每日免费额度"
        return "已关闭全局收费模式，群聊和私聊未激活用户均可无限制使用"

    if 文本 in 私聊付费开关命令配置:
        是否开启 = 私聊付费开关命令配置[文本]
        状态键 = 获取私聊付费开关状态键()
        if not 数据库可用:
            if 是否开启:
                return "私聊收费模式开启失败：数据库未配置，请先在插件配置中填写数据库信息"
            return "私聊收费模式关闭失败：数据库未配置，请先在插件配置中填写数据库信息"
        try:
            写入布尔运行状态值(配置, 付费开关状态命名空间, 状态键, 是否开启)
        except Exception as exc:
            logger.warning(f"私聊付费开关写入数据库失败：enabled={是否开启}, error={exc}")
            return f"私聊付费开关失败：{exc}"
        if 是否开启:
            return "已开启私聊收费模式，私聊未激活用户需激活或使用每日免费额度"
        return "已关闭私聊收费模式，私聊未激活用户可无限制使用"

    群号 = 获取群号(event)
    if not 群号:
        return "付费开关失败：只能在群聊中使用"

    是否开启 = 群聊付费开关命令配置[文本]
    状态键 = 获取付费开关状态键(群号)
    if not 数据库可用:
        if 是否开启:
            return "本群付费模式开启失败：数据库未配置，请先在插件配置中填写数据库信息"
        return "本群付费模式关闭失败：数据库未配置，请先在插件配置中填写数据库信息"
    try:
        写入布尔运行状态值(配置, 付费开关状态命名空间, 状态键, 是否开启)
    except Exception as exc:
        logger.warning(f"付费开关写入数据库失败：group_id={群号}, enabled={是否开启}, error={exc}")
        return f"付费开关失败：{exc}"
    if 是否开启:
        return "已开启本群付费模式，未激活用户需激活或使用每日免费额度"
    return "已关闭本群付费模式，未激活用户可无限制使用"


def 付费模式是否开启(event: Any, 配置: Any) -> bool:
    全局模式 = 获取全局付费模式(配置)
    if 全局模式 == "on":
        return True

    群号 = 获取群号(event)
    适配器 = ""
    try:
        from 功能文件.管理功能.基础功能.权限工具 import 获取适配器名称 as _获取适配器
        适配器 = _获取适配器(event)
    except Exception:
        pass

    if not 群号:
        try:
            私聊开关文本 = 读取运行状态值(配置, 付费开关状态命名空间, 获取私聊付费开关状态键(), "").strip().lower()
            if 私聊开关文本:
                私聊付费 = 私聊开关文本 in {"1", "true", "yes", "on", "开启"}
                logger.debug(f"付费开关诊断(私聊): 适配器={适配器}, 群号为空, 私聊付费已设置, 私聊付费={私聊付费}")
                return 私聊付费
            logger.debug(f"付费开关诊断(私聊): 适配器={适配器}, 群号为空, 私聊付费未设置, 全局={全局模式}")
            return 全局模式 != "off"
        except RuntimeError:
            logger.info("私聊付费开关读取跳过：数据库未配置，默认开启收费模式")
            return True
        except Exception as exc:
            logger.warning(f"私聊付费开关读取数据库失败：error={exc}")
            return True

    try:
        群聊开关文本 = 读取运行状态值(配置, 付费开关状态命名空间, 获取付费开关状态键(群号), "").strip().lower()
        if 群聊开关文本:
            群聊付费 = 群聊开关文本 in {"1", "true", "yes", "on", "开启"}
            logger.debug(f"付费开关诊断(群聊): 适配器={适配器}, 群号={群号}, 群聊付费已设置, 付费={群聊付费}")
            return 群聊付费
        logger.debug(f"付费开关诊断(群聊): 适配器={适配器}, 群号={群号}, 群聊付费未设置, 全局={全局模式}")
        return 全局模式 != "off"
    except RuntimeError:
        logger.info(f"付费开关读取跳过：数据库未配置，默认开启收费模式，group_id={群号}")
        return True
    except Exception as exc:
        logger.warning(f"付费开关读取数据库失败：group_id={群号}, error={exc}")
        return True


def 获取全局付费模式(配置: Any) -> str:
    try:
        文本 = 读取运行状态值(配置, 付费开关状态命名空间, 获取全局付费开关状态键(), "").strip().lower()
    except RuntimeError:
        logger.info("全局付费开关读取跳过：数据库未配置，默认使用群聊/私聊独立收费模式")
        return ""
    except Exception as exc:
        logger.warning(f"全局付费开关读取数据库失败：error={exc}")
        return ""
    if 文本 in {"on", "1", "true", "yes", "开启"}:
        return "on"
    if 文本 in {"off", "0", "false", "no", "关闭"}:
        return "off"
    return ""


def 获取全局付费开关状态键() -> str:
    return "global"


def 获取付费开关状态键(群号: str) -> str:
    return f"group:{str(群号).strip()}"


def 获取私聊付费开关状态键() -> str:
    return "private"


def 获取每日免费额度(配置: Any) -> int:
    return max(0, 安全整数(读取配置字段(配置, 免费额度配置项), 0))


def 消耗每日免费额度记录(配置: Any, 群号: str, 用户编号: str, 每日限额: int) -> int:
    return 消耗数据库每日免费额度记录(配置, 用户编号, 每日限额)


def 读取每日免费额度已使用(配置: Any, 群号: str, 用户编号: str) -> int:
    return 读取数据库每日免费额度已使用(配置, 用户编号)


def 获取免费额度记录键(群号: str, 用户编号: str) -> str:
    return str(用户编号)


def 格式化下载免费额度提示(剩余本数: int) -> str:
    if 剩余本数 <= 0:
        return "这是你今天的最后一本了\n可以购买VIP进行无限下载"
    return f"今日免费剩余：{剩余本数} 本"


def 格式化免费额度用尽提示(每日限额: int) -> str:
    return "\n".join(
        [
            f"您今日的{每日限额}本免费次数已经下载完了哦",
            "如果要再下载可以购买VIP请看群公告",
            "或者等第二天继续免费下载",
        ]
    )


def 获取免费额度日期() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def 是需激活文本命令(命令文本: str) -> bool:
    return str(命令文本 or "").strip() in 需激活文本命令


def 提取激活命令文本(event: Any, 命令文本: str) -> str:
    候选列表: list[str] = []
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("message", "components", "content"):
            文本 = 从消息段提取非At文本(读取字段(对象, 字段名))
            if 文本:
                候选列表.append(文本)
    候选列表.append(str(命令文本 or ""))
    候选列表.extend(获取原始文本候选(event))

    for 候选 in 候选列表:
        文本 = 清理激活命令文本(候选)
        if 文本 and 文本.startswith(用户操作命令开头):
            return 文本
    return ""


def 提取用户列表命令文本(event: Any, 命令文本: str) -> str:
    候选列表: list[str] = [str(命令文本 or "")]
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("message", "components", "content"):
            文本 = 从消息段提取非At文本(读取字段(对象, 字段名))
            if 文本:
                候选列表.append(文本)
    候选列表.extend(获取原始文本候选(event))

    for 候选 in 候选列表:
        文本 = 清理激活命令文本(候选)
        if 文本 in 用户列表命令 or 文本 in 用户列表翻页命令:
            return 文本
    return ""


def 提取卡密命令文本(event: Any, 命令文本: str) -> str:
    指令候选列表: list[str] = [str(命令文本 or "")]
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("message", "components", "content"):
            文本 = 从消息段提取非At文本(读取字段(对象, 字段名))
            if 文本:
                指令候选列表.append(文本)
    指令候选列表.extend(获取原始文本候选(event))

    for 候选 in 指令候选列表:
        文本 = 清理激活命令文本(候选)
        if (
            文本 in 卡密查询选择命令
            or 文本 in 卡密查询返回命令
            or
            文本 in 用户列表翻页命令
            or 文本.startswith("生成卡密")
            or 文本.startswith("查询卡密")
            or 复制卡密命令规则.fullmatch(文本)
        ):
            return 文本

    for 候选 in 获取卡密可见文本候选(event, 命令文本):
        文本 = 清理激活命令文本(候选)
        if 提取卡密候选列表(文本):
            return 文本
    return ""


def 解析激活命令(event: Any, 命令文本: str, context: Any = None) -> dict[str, Any] | None:
    文本 = 提取激活命令文本(event, 命令文本)
    if not 文本 or not 用户操作命令规则.fullmatch(文本):
        return None

    操作 = 提取用户操作(文本)
    if not 操作:
        return None

    At用户列表 = 获取At用户列表(event)
    手动用户列表, 天数 = 从命令文本提取用户列表和天数(文本, 操作)

    被艾特用户列表 = 提取被艾特用户QQ列表(event, At用户列表, context)
    if 被艾特用户列表:
        return 构造用户操作参数(操作, 被艾特用户列表, 天数)
    if 手动用户列表:
        return 构造用户操作参数(操作, 手动用户列表, 天数)

    return 构造用户操作参数(操作, [], 天数)


def 构造用户操作参数(操作: str, 用户列表: list[str], 天数: int) -> dict[str, Any]:
    用户列表 = 去重保序([用户 for 用户 in 用户列表 if 用户])
    return {
        "action": 操作,
        "target_user_id": 用户列表[0] if 用户列表 else "",
        "target_user_ids": 用户列表,
        "days": 天数,
    }


def 提取用户操作(文本: str) -> str:
    头部 = str(文本 or "").split(maxsplit=1)[0]
    if 头部.startswith("用户激活增加") or 头部.startswith("激活增加") or 头部.startswith("用户增加") or 头部.startswith("增加"):
        return "增加"
    if 头部.startswith("用户激活减少") or 头部.startswith("激活减少") or 头部.startswith("用户减少") or 头部.startswith("减少"):
        return "减少"
    if 头部.startswith("用户重置") or 头部.startswith("重置"):
        return "重置"
    if 头部.startswith("用户查询时间") or 头部.startswith("查询时间") or 头部.startswith("用户查询") or 头部.startswith("查询"):
        return "查询"
    if 头部.startswith("用户激活") or 头部.startswith("激活"):
        return "激活"
    return ""


def 从命令文本提取用户和天数(文本: str) -> tuple[str, int]:
    用户列表, 天数 = 从命令文本提取用户列表和天数(文本, 提取用户操作(文本))
    return (用户列表[0] if 用户列表 else "", 天数)


def 从命令文本提取用户列表和天数(文本: str, 操作: str) -> tuple[list[str], int]:
    项目列表 = 文本.split()
    if len(项目列表) < 2:
        return [], 从命令头提取天数(文本)

    用户列表: list[str] = []
    天数 = 从命令头提取天数(文本)
    for 项目 in 项目列表[1:]:
        项目 = str(项目).strip()
        if 用户编号规则.fullmatch(项目):
            用户列表.append(项目)
            continue
        if 操作 in {"激活", "增加", "减少"} and 数字规则.fullmatch(项目):
            天数 = 安全整数(项目, 天数)
    return 去重保序(用户列表), 天数


def 从命令头提取天数(文本: str) -> int:
    头部 = str(文本 or "").split(maxsplit=1)[0]
    匹配 = re.search(r"(?:用户)?(?:激活增加|激活减少|激活|增加|减少)(\d+)$", 头部)
    if 匹配:
        return 安全整数(匹配.group(1), 默认激活天数)
    return 默认激活天数


def 提取被艾特用户QQ(event: Any, At用户列表: list[str] | None = None, context: Any = None) -> str:
    用户列表 = 提取被艾特用户QQ列表(event, At用户列表, context)
    return 用户列表[0] if 用户列表 else ""


def 提取被艾特用户QQ列表(event: Any, At用户列表: list[str] | None = None, context: Any = None) -> list[str]:
    用户列表 = At用户列表 or 获取At用户列表(event)
    if not 用户列表:
        return []
    忽略用户 = 获取应忽略At用户(event, context)
    结果: list[str] = []
    for 用户 in 用户列表:
        if 用户 in 忽略用户:
            continue
        结果.append(用户)
    return 去重保序(结果)


def 获取At用户列表(event: Any) -> list[str]:
    结果: list[str] = []
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("message", "components", "content"):
            结果.extend(从消息段提取At用户列表(读取字段(对象, 字段名)))
        for 字段名 in ("message_str", "raw_message"):
            结果.extend(从文本提取At用户列表(读取字段(对象, 字段名)))
    return 去重保序(结果)


def 从消息段提取At用户列表(消息: Any) -> list[str]:
    if 消息 is None:
        return []
    if isinstance(消息, (list, tuple, set)):
        结果: list[str] = []
        for 消息段 in 消息:
            结果.extend(从消息段提取At用户列表(消息段))
        return 结果
    if isinstance(消息, dict):
        结果: list[str] = []
        if 是At类型值(消息.get("type")):
            用户 = 规范化用户编号(消息.get("qq") or 读取字段(消息.get("data"), "qq") or 读取字段(消息.get("data"), "user_id"))
            if 用户:
                结果.append(用户)
        for 子值 in 消息.values():
            结果.extend(从消息段提取At用户列表(子值))
        return 结果
    if Comp is not None:
        try:
            if isinstance(消息, Comp.At):
                用户 = 规范化用户编号(getattr(消息, "qq", ""))
                return [用户] if 用户 else []
        except Exception:
            pass
    if 是At类型值(读取字段(消息, "type")):
        用户 = 规范化用户编号(
            读取字段(消息, "qq")
            or 读取字段(消息, "user_id")
            or 读取字段(读取字段(消息, "data"), "qq")
            or 读取字段(读取字段(消息, "data"), "user_id")
        )
        return [用户] if 用户 else []
    return []


def 从消息段提取非At文本(消息: Any) -> str:
    if 消息 is None:
        return ""
    if isinstance(消息, str):
        return 消息
    if isinstance(消息, (list, tuple, set)):
        return "".join(从消息段提取非At文本(消息段) for 消息段 in 消息)
    if isinstance(消息, dict):
        if 是At类型值(消息.get("type")):
            return ""
        消息类型 = str(消息.get("type") or "").strip().lower()
        if 消息类型 in {"text", "plain"}:
            数据 = 消息.get("data")
            if isinstance(数据, dict):
                return str(数据.get("text") or 数据.get("content") or "")
            return str(消息.get("text") or 消息.get("content") or "")
        return ""
    if Comp is not None:
        try:
            if isinstance(消息, Comp.At):
                return ""
        except Exception:
            pass

    消息类型 = str(读取字段(消息, "type") or "")
    if 是At类型值(消息类型):
        return ""
    消息类型小写 = 消息类型.lower()
    if 消息类型小写 in {"text", "plain"} or 消息类型小写.endswith((".plain", ".text")):
        return str(读取字段(消息, "text") or 读取字段(消息, "content") or "")
    return ""


def 获取卡密可见文本候选(event: Any, 命令文本: str) -> list[str]:
    候选列表: list[str] = []
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("message", "components", "content"):
            文本 = 从消息段提取非At文本(读取字段(对象, 字段名))
            if 文本:
                候选列表.append(文本)
    if not 候选列表 and 是否可按命令文本识别卡密(event):
        命令文本 = str(命令文本 or "").strip()
        if 命令文本:
            候选列表.append(命令文本)
    return 候选列表


def 是否可按命令文本识别卡密(event: Any) -> bool:
    消息对象 = getattr(event, "message_obj", None)
    找到消息字段 = False
    for 对象 in (event, 消息对象):
        for 字段名 in ("message", "components", "content"):
            消息 = 读取字段(对象, 字段名)
            if 消息 is None:
                continue
            找到消息字段 = True
            if not 是否纯文本消息段集合(消息):
                return False
    return not 找到消息字段


def 是否纯文本消息段集合(消息: Any) -> bool:
    if 消息 is None:
        return True
    if isinstance(消息, str):
        return True
    if isinstance(消息, (list, tuple, set)):
        return all(是否纯文本消息段集合(消息段) for 消息段 in 消息)
    if isinstance(消息, dict):
        消息类型 = str(消息.get("type") or "").strip().lower()
        return 消息类型 in {"text", "plain"} or 是At类型值(消息.get("type"))
    消息类型 = str(读取字段(消息, "type") or "")
    if 是At类型值(消息类型):
        return True
    消息类型小写 = 消息类型.lower()
    return 消息类型小写 in {"text", "plain"} or 消息类型小写.endswith((".plain", ".text"))


def 清理激活命令文本(文本: Any) -> str:
    结果 = str(文本 or "")
    结果 = re.sub(r"\[CQ:reply,[^\]]*\]", "", 结果, flags=re.IGNORECASE)
    结果 = re.sub(r"\[CQ:at,[^\]]*\]", "", 结果, flags=re.IGNORECASE)
    结果 = re.sub(r"\[At:[^\]]+\]", "", 结果, flags=re.IGNORECASE)
    结果 = re.sub(r"<@!?[A-Za-z0-9_-]{5,64}>", "", 结果)
    结果 = 结果.replace("＠", "@").strip()
    while 结果.startswith("@"):
        新结果 = re.sub(r"^@[^\s]+\s*", "", 结果, count=1)
        if 新结果 == 结果:
            break
        结果 = 新结果.strip()
    结果 = re.sub(r"\s+", " ", 结果).strip()
    return 结果


def 从文本提取At用户列表(文本: Any) -> list[str]:
    原文 = str(文本 or "")
    if not 原文:
        return []
    结果: list[str] = []
    for 匹配 in re.finditer(r"\[At:([^\]]+)\]", 原文, re.IGNORECASE):
        用户 = 规范化用户编号(匹配.group(1))
        if 用户:
            结果.append(用户)
    for 匹配 in re.finditer(r"\[CQ:at,[^\]]*qq=([^,\]]+)", 原文, re.IGNORECASE):
        用户 = 规范化用户编号(匹配.group(1))
        if 用户:
            结果.append(用户)
    for 匹配 in re.finditer(r"<@!?([A-Za-z0-9_-]{5,64})>", 原文):
        用户 = 规范化用户编号(匹配.group(1))
        if 用户:
            结果.append(用户)
    for 匹配 in re.finditer(r"@[^\s()]{1,80}\(([A-Za-z0-9_-]{5,64})\)", 原文):
        用户 = 规范化用户编号(匹配.group(1))
        if 用户:
            结果.append(用户)
    return 结果


def 去重保序(列表: list[str]) -> list[str]:
    结果: list[str] = []
    已见: set[str] = set()
    for 项目 in 列表:
        if 项目 in 已见:
            continue
        已见.add(项目)
        结果.append(项目)
    return 结果


def 获取原始文本候选(event: Any) -> list[str]:
    消息对象 = getattr(event, "message_obj", None)
    结果: list[str] = []
    for 对象 in (event, 消息对象):
        for 字段名 in ("raw_message", "message_str"):
            值 = 读取字段(对象, 字段名)
            if 值:
                结果.append(str(值))
    return 结果


def 记录用户激活诊断(event: Any, 命令文本: str, 激活参数: dict[str, Any], context: Any = None) -> None:
    try:
        logger.info(
            "用户激活诊断："
            f"command={限制长度(命令文本, 120)}, "
            f"sender={获取发送者QQ(event)}, "
            f"action={激活参数.get('action')}, "
            f"target={激活参数.get('target_user_id')}, "
            f"targets={激活参数.get('target_user_ids')}, "
            f"days={激活参数.get('days')}, "
            f"at_users={获取At用户列表(event)}, "
            f"ignored_at={list(获取应忽略At用户(event, context))}, "
            f"is_wake={bool(读取字段(event, 'is_wake'))}, "
            f"is_at_or_wake_command={bool(读取字段(event, 'is_at_or_wake_command'))}, "
            f"message_str={限制长度(读取字段(event, 'message_str'), 300)}, "
            f"raw_message={限制长度(读取字段(event, 'raw_message'), 300)}"
        )
    except Exception as exc:
        logger.warning(f"用户激活诊断失败：error={exc}")


def 获取应忽略At用户(event: Any, context: Any = None) -> set[str]:
    结果: set[str] = set()
    消息对象 = getattr(event, "message_obj", None)
    bot = getattr(event, "bot", None)
    for 对象 in (event, 消息对象, bot, context):
        if 对象 is None:
            continue
        for 字段名 in ("self_id", "bot_id", "robot_id", "uin", "qq"):
            值 = 规范化用户编号(读取字段(对象, 字段名))
            if 值:
                结果.add(值)
    return 结果


def 规范化用户编号(值: Any) -> str:
    文本 = str(值 or "").strip()
    if not 文本 or 文本.lower() in {"all", "qq_official"}:
        return ""
    return 文本 if 用户编号规则.fullmatch(文本) else ""


def 是At类型值(值: Any) -> bool:
    for 候选 in (值, 读取字段(值, "value"), 读取字段(值, "name")):
        if 候选 is None:
            continue
        文本 = str(候选).strip().lower()
        if 文本 == "at" or 文本.endswith(".at") or "componenttype.at" in 文本:
            return True
    return False


def 规范化卡密(值: Any) -> str:
    文本 = str(值 or "").strip().upper()
    return 文本 if 卡密规则.fullmatch(文本) else ""


def 提取卡密候选列表(值: Any) -> list[str]:
    文本 = str(值 or "").upper()
    候选列表 = [匹配.group(1) for 匹配 in 卡密候选规则.finditer(文本)]
    return 去重保序([候选 for 候选 in 候选列表 if 卡密规则.fullmatch(候选)])


def 生成单个卡密() -> str:
    while True:
        卡密 = "".join(secrets.choice(卡密字符集) for _ in range(12))
        if 卡密规则.fullmatch(卡密):
            return 卡密


async def 生成并保存卡密列表(配置: Any, 群号: str, 创建者: str, 数量: int, 天数: int) -> list[str]:
    return await asyncio.to_thread(生成数据库卡密列表, 配置, 群号, 创建者, 数量, 天数)


async def 列出卡密记录(配置: Any, 群号: str, 查询参数: dict[str, Any]) -> list[dict[str, Any]]:
    return await asyncio.to_thread(列出数据库卡密记录, 配置, 群号, 查询参数)


def 规范化卡密记录(记录: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_key": str(记录.get("card_key") or "").strip(),
        "group_id": str(记录.get("group_id") or "").strip(),
        "days": 安全整数(记录.get("days"), 默认激活天数),
        "created_at": 安全整数(记录.get("created_at"), 0),
        "created_by": str(记录.get("created_by") or "").strip(),
        "used_at": 安全整数(记录.get("used_at"), 0),
        "used_by": str(记录.get("used_by") or "").strip(),
    }


async def 读取激活到期时间(配置: Any, 群号: str, 用户编号: str) -> int:
    记录 = await 读取激活记录(配置, 群号, 用户编号)
    return 安全整数(记录.get("expires_at") if 记录 else 0, 0)


async def 读取激活记录(配置: Any, 群号: str, 用户编号: str) -> dict[str, int]:
    return await asyncio.to_thread(读取数据库激活记录, 配置, 群号, 用户编号)


async def 读取激活查询详情(配置: Any, 群号: str, 用户编号: str) -> dict[str, Any]:
    return await asyncio.to_thread(读取数据库激活查询详情, 配置, 群号, 用户编号)


async def 写入激活记录(配置: Any, 群号: str, 用户编号: str, 到期时间: int) -> None:
    await asyncio.to_thread(写入数据库激活记录, 配置, 群号, 用户编号, 到期时间)


async def 删除激活记录(配置: Any, 群号: str, 用户编号: str) -> None:
    await asyncio.to_thread(删除数据库激活记录, 配置, 群号, 用户编号)


def 读取数据库激活记录(配置: Any, 群号: str, 用户编号: str) -> dict[str, int]:
    数据库配置 = 获取数据库配置(配置)
    with 打开数据库连接(数据库配置) as 连接:
        确保数据库表(连接, 数据库配置["table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT expires_at, updated_at FROM `{数据库配置['table']}` WHERE group_id=%s AND user_id=%s LIMIT 1",
                (str(群号), str(用户编号)),
            )
            记录 = 游标.fetchone()
    if not 记录:
        return {}
    到期时间 = 安全整数(记录[0], 0)
    if 到期时间 < int(time.time()):
        return {}
    return {
        "expires_at": 到期时间,
        "updated_at": 安全整数(记录[1] if len(记录) > 1 else 0, 0),
    }


def 读取数据库激活查询详情(配置: Any, 群号: str, 用户编号: str) -> dict[str, Any]:
    数据库配置 = 获取数据库配置(配置)
    当前时间 = int(time.time())
    with 打开数据库连接(数据库配置) as 连接:
        确保数据库表(连接, 数据库配置["table"])
        确保卡密数据库表(连接, 数据库配置["card_table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT expires_at, updated_at
                FROM `{数据库配置['table']}`
                WHERE group_id=%s AND user_id=%s
                LIMIT 1
                """,
                (str(群号), str(用户编号)),
            )
            激活记录 = 游标.fetchone()
            if not 激活记录:
                return {}

            到期时间 = 安全整数(激活记录[0], 0)
            if 到期时间 < 当前时间:
                return {}

            激活时间 = 安全整数(激活记录[1] if len(激活记录) > 1 else 0, 0)
            游标.execute(
                f"""
                SELECT card_key, days, used_at
                FROM `{数据库配置['card_table']}`
                WHERE group_id=%s AND used_by=%s
                ORDER BY used_at DESC, created_at DESC
                LIMIT 1
                """,
                (str(群号), str(用户编号)),
            )
            卡密记录 = 游标.fetchone()

    卡密号 = str(卡密记录[0]).strip() if 卡密记录 else ""
    卡密天数 = 安全整数(卡密记录[1], 0) if 卡密记录 else 0
    卡密使用时间 = 安全整数(卡密记录[2], 0) if 卡密记录 else 0
    if 卡密使用时间 > 0:
        激活时间 = 卡密使用时间
    if 卡密天数 <= 0 and 激活时间 > 0 and 到期时间 > 激活时间:
        卡密天数 = max(1, math.ceil((到期时间 - 激活时间) / 86400))
    return {
        "expires_at": 到期时间,
        "updated_at": 激活时间,
        "card_key": 卡密号,
        "days": 卡密天数,
    }


def 写入数据库激活记录(配置: Any, 群号: str, 用户编号: str, 到期时间: int) -> None:
    数据库配置 = 获取数据库配置(配置)
    with 打开数据库连接(数据库配置) as 连接:
        确保数据库表(连接, 数据库配置["table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                INSERT INTO `{数据库配置['table']}` (group_id, user_id, expires_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE expires_at=VALUES(expires_at), updated_at=VALUES(updated_at)
                """,
                (str(群号), str(用户编号), int(到期时间), int(time.time())),
            )
        连接.commit()


def 删除数据库激活记录(配置: Any, 群号: str, 用户编号: str) -> None:
    数据库配置 = 获取数据库配置(配置)
    with 打开数据库连接(数据库配置) as 连接:
        确保数据库表(连接, 数据库配置["table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"DELETE FROM `{数据库配置['table']}` WHERE group_id=%s AND user_id=%s",
                (str(群号), str(用户编号)),
            )
        连接.commit()


def 列出数据库激活用户记录(配置: Any, 群号: str) -> list[dict[str, int | str]]:
    数据库配置 = 获取数据库配置(配置)
    当前时间 = int(time.time())
    with 打开数据库连接(数据库配置) as 连接:
        确保数据库表(连接, 数据库配置["table"])
        确保卡密数据库表(连接, 数据库配置["card_table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT a.user_id,
                       a.expires_at,
                       a.updated_at,
                       (
                           SELECT c.card_key
                           FROM `{数据库配置['card_table']}` c
                           WHERE c.group_id = a.group_id
                             AND c.used_by = a.user_id
                           ORDER BY c.used_at DESC, c.created_at DESC, c.card_key ASC
                           LIMIT 1
                       ) AS card_key
                FROM `{数据库配置['table']}` a
                WHERE a.group_id=%s AND a.expires_at >= %s
                ORDER BY a.expires_at ASC, a.user_id ASC
                """,
                (str(群号), 当前时间),
            )
            记录列表 = 游标.fetchall()
    return [
        {
            "user_id": str(记录[0]),
            "expires_at": 安全整数(记录[1], 0),
            "updated_at": 安全整数(记录[2] if len(记录) > 2 else 0, 0),
            "card_key": str(记录[3] if len(记录) > 3 and 记录[3] else "").strip(),
        }
        for 记录 in 记录列表
    ]


def 生成数据库卡密列表(配置: Any, 群号: str, 创建者: str, 数量: int, 天数: int) -> list[str]:
    数据库配置 = 获取数据库配置(配置)
    当前时间 = int(time.time())
    结果: list[str] = []
    尝试次数 = 0
    with 打开数据库连接(数据库配置) as 连接:
        确保卡密数据库表(连接, 数据库配置["card_table"])
        with 连接.cursor() as 游标:
            while len(结果) < 数量 and 尝试次数 < 数量 * 100:
                尝试次数 += 1
                卡密 = 生成单个卡密()
                游标.execute(
                    f"""
                    INSERT IGNORE INTO `{数据库配置['card_table']}`
                    (card_key, group_id, days, created_at, created_by, used_at, used_by)
                    VALUES (%s, %s, %s, %s, %s, 0, '')
                    """,
                    (卡密, str(群号), int(天数), 当前时间, str(创建者)),
                )
                if 游标.rowcount:
                    结果.append(卡密)
        if len(结果) < 数量:
            连接.rollback()
            raise RuntimeError("卡密生成失败，请重试")
        连接.commit()
    return 结果


def 筛选存在数据库卡密列表(配置: Any, 群号: str, 卡密列表: list[str]) -> list[str]:
    卡密列表 = 去重保序([规范化卡密(卡密) for 卡密 in 卡密列表 if 规范化卡密(卡密)])
    if not 卡密列表:
        return []
    数据库配置 = 获取数据库配置(配置)
    with 打开数据库连接(数据库配置) as 连接:
        确保卡密数据库表(连接, 数据库配置["card_table"])
        with 连接.cursor() as 游标:
            占位符 = ", ".join(["%s"] * len(卡密列表))
            游标.execute(
                f"""
                SELECT card_key
                FROM `{数据库配置['card_table']}`
                WHERE group_id=%s AND card_key IN ({占位符})
                """,
                tuple([str(群号), *卡密列表]),
            )
            记录列表 = 游标.fetchall()
    存在集合 = {str(记录[0] or "").strip() for 记录 in 记录列表 if str(记录[0] or "").strip()}
    return [卡密 for 卡密 in 卡密列表 if 卡密 in 存在集合]


def 使用数据库卡密激活(配置: Any, 群号: str, 用户编号: str, 卡密: str) -> dict[str, Any]:
    数据库配置 = 获取数据库配置(配置)
    当前时间 = int(time.time())
    with 打开数据库连接(数据库配置) as 连接:
        确保数据库表(连接, 数据库配置["table"])
        确保卡密数据库表(连接, 数据库配置["card_table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT days, used_at, used_by
                FROM `{数据库配置['card_table']}`
                WHERE card_key=%s AND group_id=%s
                LIMIT 1
                FOR UPDATE
                """,
                (卡密, str(群号)),
            )
            卡密记录 = 游标.fetchone()
            if not 卡密记录:
                连接.rollback()
                return {"status": "invalid"}
            if 安全整数(卡密记录[1], 0) > 0 or str(卡密记录[2] if len(卡密记录) > 2 else "").strip():
                连接.rollback()
                return {"status": "invalid"}

            游标.execute(
                f"""
                SELECT expires_at, updated_at
                FROM `{数据库配置['table']}`
                WHERE group_id=%s AND user_id=%s
                LIMIT 1
                FOR UPDATE
                """,
                (str(群号), str(用户编号)),
            )
            激活记录 = 游标.fetchone()
            if 激活记录 and 安全整数(激活记录[0], 0) >= 当前时间:
                连接.rollback()
                return {
                    "status": "already",
                    "record": {
                        "expires_at": 安全整数(激活记录[0], 0),
                        "updated_at": 安全整数(激活记录[1] if len(激活记录) > 1 else 0, 0),
                    },
                }

            天数 = 安全整数(卡密记录[0], 默认激活天数)
            到期时间 = 当前时间 + 天数 * 86400
            游标.execute(
                f"""
                INSERT INTO `{数据库配置['table']}` (group_id, user_id, expires_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE expires_at=VALUES(expires_at), updated_at=VALUES(updated_at)
                """,
                (str(群号), str(用户编号), 到期时间, 当前时间),
            )
            游标.execute(
                f"""
                UPDATE `{数据库配置['card_table']}`
                SET used_at=%s, used_by=%s
                WHERE card_key=%s AND group_id=%s
                """,
                (当前时间, str(用户编号), 卡密, str(群号)),
            )
        连接.commit()
    return {"status": "used", "days": 天数, "expires_at": 到期时间}


def 列出数据库卡密记录(配置: Any, 群号: str, 查询参数: dict[str, Any]) -> list[dict[str, Any]]:
    数据库配置 = 获取数据库配置(配置)
    条件列表 = ["group_id=%s"]
    参数列表: list[Any] = [str(群号)]
    状态 = 查询参数.get("status")
    指定卡密 = str(查询参数.get("card_key") or "").strip()
    用户列表 = [str(用户).strip() for 用户 in 查询参数.get("user_ids", []) if str(用户).strip()]
    if 状态 == "used":
        条件列表.append("used_at > 0")
    elif 状态 == "unused":
        条件列表.append("used_at = 0")
    if 指定卡密:
        条件列表.append("card_key=%s")
        参数列表.append(指定卡密)
    if 用户列表:
        占位符 = ", ".join(["%s"] * len(用户列表))
        条件列表.append(f"used_by IN ({占位符})")
        参数列表.extend(用户列表)

    with 打开数据库连接(数据库配置) as 连接:
        确保卡密数据库表(连接, 数据库配置["card_table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT card_key, group_id, days, created_at, created_by, used_at, used_by
                FROM `{数据库配置['card_table']}`
                WHERE {' AND '.join(条件列表)}
                ORDER BY CASE WHEN used_at = 0 THEN 1 ELSE 0 END ASC,
                         IF(used_at = 0, created_at, used_at) DESC,
                         card_key ASC
                """,
                tuple(参数列表),
            )
            记录列表 = 游标.fetchall()
    return [
        规范化卡密记录(
            {
                "card_key": 记录[0],
                "group_id": 记录[1],
                "days": 记录[2],
                "created_at": 记录[3],
                "created_by": 记录[4],
                "used_at": 记录[5],
                "used_by": 记录[6],
            }
        )
        for 记录 in 记录列表
    ]


def 同步数据库卡密到配置(配置: Any) -> bool:
    数据库配置 = 获取数据库配置(配置)
    配置卡密记录 = 读取配置卡密记录映射(配置)
    当前时间 = int(time.time())

    with 打开数据库连接(数据库配置) as 连接:
        确保卡密数据库表(连接, 数据库配置["card_table"])
        确保运行状态数据库表(连接, 数据库配置["runtime_state_table"])
        快照 = 读取卡密同步快照(连接, 数据库配置["runtime_state_table"])
        数据库记录映射 = 转换卡密记录映射(查询全部数据库卡密记录(连接, 数据库配置["card_table"]))

        待删除卡密列表 = 获取配置删除卡密列表(配置卡密记录, 数据库记录映射, 快照)
        if 待删除卡密列表:
            删除数据库卡密记录列表(连接, 数据库配置["card_table"], 待删除卡密列表)
            for 卡密 in 待删除卡密列表:
                数据库记录映射.pop(卡密, None)

        待写入记录列表 = 获取配置新增或修改卡密列表(配置卡密记录, 数据库记录映射, 快照, bool(快照), 当前时间)
        if 待写入记录列表:
            写入或更新数据库卡密记录列表(连接, 数据库配置["card_table"], 待写入记录列表)

        记录列表 = 查询全部数据库卡密记录(连接, 数据库配置["card_table"])
        写入卡密同步快照(连接, 数据库配置["runtime_state_table"], 生成卡密同步快照(记录列表))

    已使用列表: list[str] = []
    未使用列表: list[str] = []
    for 记录 in 记录列表:
        规范记录 = 规范化卡密记录(记录)
        卡密 = str(规范记录.get("card_key") or "").strip()
        if not 卡密:
            continue
        if str(规范记录.get("used_by") or "").strip() or 安全整数(规范记录.get("used_at"), 0) > 0:
            已使用列表.append(格式化配置已使用卡密(规范记录))
        else:
            未使用列表.append(格式化配置未使用卡密(规范记录))

    已变更 = False
    已变更 = 设置配置字段(配置, 卡密同步已使用配置项, 已使用列表) or 已变更
    已变更 = 设置配置字段(配置, 卡密同步未使用配置项, 未使用列表) or 已变更
    if 待删除卡密列表 or 待写入记录列表:
        已变更 = True
    return 已变更


def 获取配置删除卡密列表(
    配置卡密记录: dict[str, dict[str, Any]],
    数据库记录映射: dict[str, dict[str, Any]],
    快照: dict[str, dict[str, Any]],
) -> list[str]:
    结果: list[str] = []
    for 卡密 in 快照:
        if 卡密 in 配置卡密记录:
            continue
        if 卡密 in 数据库记录映射:
            结果.append(卡密)
    return sorted(结果)


def 获取配置新增或修改卡密列表(
    配置卡密记录: dict[str, dict[str, Any]],
    数据库记录映射: dict[str, dict[str, Any]],
    快照: dict[str, dict[str, Any]],
    已有快照: bool,
    当前时间: int,
) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = []
    for 卡密, 配置记录 in 配置卡密记录.items():
        配置签名 = 获取卡密同步签名(配置记录)
        快照签名 = 快照.get(卡密)
        if 快照签名 is not None:
            if 配置签名 != 快照签名:
                结果.append(准备配置卡密写入记录(配置记录, 当前时间))
            continue

        if 卡密 not in 数据库记录映射:
            结果.append(准备配置卡密写入记录(配置记录, 当前时间))
            continue

        if 已有快照 and 配置签名 != 获取卡密同步签名(数据库记录映射[卡密]):
            结果.append(准备配置卡密写入记录(配置记录, 当前时间))
    return 结果


def 准备配置卡密写入记录(记录: dict[str, Any], 当前时间: int) -> dict[str, Any]:
    规范记录 = 规范化卡密记录(记录)
    已使用 = bool(str(规范记录.get("used_by") or "").strip() or 安全整数(规范记录.get("used_at"), 0) > 0)
    return {
        "card_key": str(规范记录.get("card_key") or "").strip(),
        "group_id": str(规范记录.get("group_id") or "").strip() or "private",
        "days": 安全整数(规范记录.get("days"), 默认激活天数),
        "created_at": 安全整数(规范记录.get("created_at"), 0) or 当前时间,
        "created_by": str(规范记录.get("created_by") or "").strip() or 卡密同步配置创建者,
        "used_at": (安全整数(规范记录.get("used_at"), 0) or 当前时间) if 已使用 else 0,
        "used_by": str(规范记录.get("used_by") or "").strip() if 已使用 else "",
    }


def 读取配置卡密记录映射(配置: Any) -> dict[str, dict[str, Any]]:
    结果: dict[str, dict[str, Any]] = {}
    for 字段名, 默认状态 in ((卡密同步已使用配置项, "used"), (卡密同步未使用配置项, "unused")):
        值 = 读取配置字段(配置, 字段名)
        if isinstance(值, str):
            值 = [值]
        if not isinstance(值, list):
            continue
        for 项目 in 值:
            记录 = 解析配置卡密记录(项目, 默认状态)
            卡密 = str(记录.get("card_key") or "").strip()
            if 卡密:
                结果[卡密] = 记录
    return 结果


def 解析配置卡密记录(项目: Any, 默认状态: str) -> dict[str, Any]:
    文本 = str(项目 or "").strip()
    if not 文本:
        return {}
    字段列表 = [字段.strip() for 字段 in 文本.split("#")]
    卡密 = 规范化卡密(字段列表[0] if 字段列表 else "")
    if not 卡密:
        候选列表 = 提取卡密候选列表(文本)
        卡密 = 候选列表[0] if 候选列表 else ""
    if not 卡密:
        return {}

    状态文本 = "#".join(字段列表).lower()
    已使用 = 默认状态 == "used" or "已使用" in 状态文本 or "used" in 状态文本
    群号 = 字段列表[1] if len(字段列表) > 1 and 字段列表[1] else "private"
    用户 = ""
    if 已使用 and len(字段列表) > 2 and not 是配置卡密天数字段(字段列表[2]) and "使用" not in 字段列表[2]:
        用户 = 字段列表[2].strip()
    天数 = 提取配置卡密天数(字段列表)
    return {
        "card_key": 卡密,
        "group_id": 群号,
        "days": 天数,
        "created_at": 0,
        "created_by": 卡密同步配置创建者,
        "used_at": 1 if 已使用 else 0,
        "used_by": 用户 if 已使用 else "",
    }


def 是配置卡密天数字段(文本: Any) -> bool:
    return bool(re.fullmatch(r"\d+\s*天?", str(文本 or "").strip()))


def 提取配置卡密天数(字段列表: list[str]) -> int:
    for 字段 in 字段列表:
        匹配 = re.fullmatch(r"(\d+)\s*天", str(字段 or "").strip())
        if 匹配:
            return max(1, 安全整数(匹配.group(1), 默认激活天数))
    for 字段 in reversed(字段列表[2:]):
        文本 = str(字段 or "").strip()
        if 文本.isdigit():
            数值 = 安全整数(文本, 默认激活天数)
            if 0 < 数值 <= 最长激活天数:
                return 数值
    return 默认激活天数


def 转换卡密记录映射(记录列表: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    结果: dict[str, dict[str, Any]] = {}
    for 记录 in 记录列表:
        规范记录 = 规范化卡密记录(记录)
        卡密 = str(规范记录.get("card_key") or "").strip()
        if 卡密:
            结果[卡密] = 规范记录
    return 结果


def 生成卡密同步快照(记录列表: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {卡密: 获取卡密同步签名(记录) for 卡密, 记录 in 转换卡密记录映射(记录列表).items()}


def 获取卡密同步签名(记录: dict[str, Any]) -> dict[str, Any]:
    规范记录 = 规范化卡密记录(记录)
    已使用 = bool(str(规范记录.get("used_by") or "").strip() or 安全整数(规范记录.get("used_at"), 0) > 0)
    return {
        "card_key": str(规范记录.get("card_key") or "").strip(),
        "group_id": str(规范记录.get("group_id") or "").strip(),
        "days": 安全整数(规范记录.get("days"), 默认激活天数),
        "status": "used" if 已使用 else "unused",
        "used_by": str(规范记录.get("used_by") or "").strip() if 已使用 else "",
    }


def 读取卡密同步快照(连接: Any, 表名: str) -> dict[str, dict[str, Any]]:
    with 连接.cursor() as 游标:
        游标.execute(
            f"""
            SELECT state_value
            FROM `{表名}`
            WHERE namespace=%s AND state_key=%s
            LIMIT 1
            """,
            (卡密同步状态命名空间, 卡密同步快照状态键),
        )
        记录 = 游标.fetchone()
    if not 记录:
        return {}
    try:
        数据 = json.loads(str(记录[0] or "{}"))
    except Exception:
        return {}
    if not isinstance(数据, dict):
        return {}
    结果: dict[str, dict[str, Any]] = {}
    for 卡密, 签名 in 数据.items():
        标准卡密 = 规范化卡密(卡密)
        if 标准卡密 and isinstance(签名, dict):
            结果[标准卡密] = 获取卡密同步签名({"card_key": 标准卡密, **签名})
    return 结果


def 写入卡密同步快照(连接: Any, 表名: str, 快照: dict[str, dict[str, Any]]) -> None:
    with 连接.cursor() as 游标:
        游标.execute(
            f"""
            INSERT INTO `{表名}` (namespace, state_key, state_value, updated_at)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE state_value=VALUES(state_value), updated_at=VALUES(updated_at)
            """,
            (
                卡密同步状态命名空间,
                卡密同步快照状态键,
                json.dumps(快照, ensure_ascii=False, sort_keys=True),
                int(time.time()),
            ),
        )
    连接.commit()


def 写入或更新数据库卡密记录列表(连接: Any, 表名: str, 记录列表: list[dict[str, Any]]) -> None:
    if not 记录列表:
        return
    with 连接.cursor() as 游标:
        for 记录 in 记录列表:
            规范记录 = 准备配置卡密写入记录(记录, int(time.time()))
            if not 规范记录["card_key"]:
                continue
            游标.execute(
                f"""
                INSERT INTO `{表名}` (card_key, group_id, days, created_at, created_by, used_at, used_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    group_id=VALUES(group_id),
                    days=VALUES(days),
                    used_at=VALUES(used_at),
                    used_by=VALUES(used_by)
                """,
                (
                    规范记录["card_key"],
                    规范记录["group_id"],
                    规范记录["days"],
                    规范记录["created_at"],
                    规范记录["created_by"],
                    规范记录["used_at"],
                    规范记录["used_by"],
                ),
            )
    连接.commit()


def 删除数据库卡密记录列表(连接: Any, 表名: str, 卡密列表: list[str]) -> None:
    卡密列表 = 去重保序([规范化卡密(卡密) for 卡密 in 卡密列表 if 规范化卡密(卡密)])
    if not 卡密列表:
        return
    with 连接.cursor() as 游标:
        for 开始 in range(0, len(卡密列表), 200):
            当前批次 = 卡密列表[开始 : 开始 + 200]
            占位符 = ", ".join(["%s"] * len(当前批次))
            游标.execute(f"DELETE FROM `{表名}` WHERE card_key IN ({占位符})", tuple(当前批次))
    连接.commit()


def 查询全部数据库卡密记录(连接: Any, 表名: str) -> list[dict[str, Any]]:
    with 连接.cursor() as 游标:
        游标.execute(
            f"""
            SELECT card_key, group_id, days, created_at, created_by, used_at, used_by
            FROM `{表名}`
            ORDER BY CASE WHEN used_at = 0 THEN 1 ELSE 0 END ASC,
                     IF(used_at = 0, created_at, used_at) DESC,
                     group_id ASC,
                     card_key ASC
            """
        )
        记录列表 = 游标.fetchall()
    return [
        {
            "card_key": 记录[0],
            "group_id": 记录[1],
            "days": 记录[2],
            "created_at": 记录[3],
            "created_by": 记录[4],
            "used_at": 记录[5],
            "used_by": 记录[6],
        }
        for 记录 in 记录列表
    ]

def 消耗数据库每日免费额度记录(配置: Any, 用户编号: str, 每日限额: int) -> int:
    数据库配置 = 获取数据库配置(配置)
    今日 = 获取免费额度日期()
    当前时间 = int(time.time())
    with 打开数据库连接(数据库配置) as 连接:
        确保免费额度数据库表(连接, 数据库配置["free_quota_table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT used_count
                FROM `{数据库配置['free_quota_table']}`
                WHERE usage_date=%s AND user_id=%s
                LIMIT 1
                FOR UPDATE
                """,
                (今日, str(用户编号)),
            )
            记录 = 游标.fetchone()
            已使用 = 安全整数(记录[0], 0) if 记录 else 0
            if 已使用 >= 每日限额:
                连接.rollback()
                return 0
            新次数 = 已使用 + 1
            游标.execute(
                f"""
                INSERT INTO `{数据库配置['free_quota_table']}` (usage_date, user_id, used_count, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE used_count=VALUES(used_count), updated_at=VALUES(updated_at)
                """,
                (今日, str(用户编号), 新次数, 当前时间),
            )
        连接.commit()
    return 新次数


def 读取数据库每日免费额度已使用(配置: Any, 用户编号: str) -> int:
    数据库配置 = 获取数据库配置(配置)
    with 打开数据库连接(数据库配置) as 连接:
        确保免费额度数据库表(连接, 数据库配置["free_quota_table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT used_count
                FROM `{数据库配置['free_quota_table']}`
                WHERE usage_date=%s AND user_id=%s
                LIMIT 1
                """,
                (获取免费额度日期(), str(用户编号)),
            )
            记录 = 游标.fetchone()
    return 安全整数(记录[0], 0) if 记录 else 0


def 格式化配置已使用卡密(记录: dict[str, Any]) -> str:
    卡密 = str(记录.get("card_key") or "").strip()
    群号 = str(记录.get("group_id") or "").strip()
    用户 = str(记录.get("used_by") or "").strip() or "未知QQ"
    天数 = 安全整数(记录.get("days"), 默认激活天数)
    return f"{卡密}#{群号}#{用户}#{天数}天#已使用"


def 格式化配置未使用卡密(记录: dict[str, Any]) -> str:
    卡密 = str(记录.get("card_key") or "").strip()
    群号 = str(记录.get("group_id") or "").strip()
    天数 = 安全整数(记录.get("days"), 默认激活天数)
    return f"{卡密}#{群号}#{天数}天#未使用"


def 打开数据库连接(数据库配置: dict[str, Any]) -> Any:
    try:
        import pymysql
    except Exception as exc:
        raise RuntimeError("缺少 pymysql 依赖，请先安装 requirements.txt") from exc
    return pymysql.connect(
        host=数据库配置["host"],
        port=数据库配置["port"],
        user=数据库配置["user"],
        password=数据库配置["password"],
        database=数据库配置["database"],
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


def 确保数据库表(连接: Any, 表名: str) -> None:
    with 连接.cursor() as 游标:
        游标.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{表名}` (
                group_id VARCHAR(64) NOT NULL,
                user_id VARCHAR(64) NOT NULL,
                expires_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                PRIMARY KEY (group_id, user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    连接.commit()


def 确保卡密数据库表(连接: Any, 表名: str) -> None:
    with 连接.cursor() as 游标:
        游标.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{表名}` (
                card_key VARCHAR(32) NOT NULL,
                group_id VARCHAR(64) NOT NULL,
                days INT NOT NULL,
                created_at BIGINT NOT NULL,
                created_by VARCHAR(64) NOT NULL,
                used_at BIGINT NOT NULL DEFAULT 0,
                used_by VARCHAR(64) NOT NULL DEFAULT '',
                PRIMARY KEY (card_key),
                KEY idx_group_used (group_id, used_at),
                KEY idx_group_used_by (group_id, used_by)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    连接.commit()


def 确保免费额度数据库表(连接: Any, 表名: str) -> None:
    with 连接.cursor() as 游标:
        游标.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{表名}` (
                usage_date VARCHAR(16) NOT NULL,
                user_id VARCHAR(64) NOT NULL,
                used_count INT NOT NULL DEFAULT 0,
                updated_at BIGINT NOT NULL,
                PRIMARY KEY (usage_date, user_id),
                KEY idx_user_date (user_id, usage_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    连接.commit()


def 确保运行状态数据库表(连接: Any, 表名: str) -> None:
    with 连接.cursor() as 游标:
        游标.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{表名}` (
                namespace VARCHAR(64) NOT NULL,
                state_key VARCHAR(128) NOT NULL,
                state_value TEXT NOT NULL,
                updated_at BIGINT NOT NULL,
                PRIMARY KEY (namespace, state_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    连接.commit()


def 获取数据库配置(配置: Any) -> dict[str, Any]:
    用户名 = str(读取配置字段(配置, "user_activation_database_user") or "").strip()
    数据库名 = str(读取配置字段(配置, "user_activation_database_name") or 用户名).strip()
    数据库配置 = {
        "host": str(读取配置字段(配置, "user_activation_database_host") or "").strip(),
        "port": 安全整数(读取配置字段(配置, "user_activation_database_port"), 3306),
        "user": 用户名,
        "password": str(读取配置字段(配置, "user_activation_database_password") or ""),
        "database": 数据库名,
        "table": 用户激活数据库表名,
        "card_table": 用户激活卡密数据库表名,
        "free_quota_table": 用户免费额度数据库表名,
        "runtime_state_table": 运行状态数据库表名,
    }
    缺少字段 = [键 for 键 in ("host", "user", "database") if not 数据库配置[键]]
    if 缺少字段:
        raise RuntimeError(f"用户激活数据库配置不完整：缺少 {', '.join(缺少字段)}")
    return 数据库配置


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group", "get_group_openid"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                结果 = str(值)
                logger.debug(f"获取群号诊断: 方法={方法名}, 返回值={结果}")
                return 结果

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "group_openid") or 读取字段(对象, "group_id") or 读取字段(对象, "group")
        if isinstance(值, dict):
            值 = 值.get("group_openid") or 值.get("group_id") or 值.get("id")
        if 值:
            结果 = str(值)
            logger.debug(f"获取群号诊断: 对象字段, 返回值={结果}")
            return 结果
    logger.debug(f"获取群号诊断: 未找到群号, 返回空字符串")
    return ""


def 读取配置字段(配置: Any, 字段名: str) -> Any:
    if 配置 is None:
        return None
    配置字典 = 获取配置字典(配置)
    if 配置字典 is not None and 配置字典 is not 配置:
        值 = 读取配置字段(配置字典, 字段名)
        if 值 is not None:
            return 值

    值 = 读取字段(配置, 字段名)
    if 值 is None:
        值 = 读取旧版配置字段(配置, 字段名)
    if 值 is not None:
        return 值
    for 分类名 in 配置字段分类映射.get(字段名, ()):
        分类 = 读取字段(配置, 分类名)
        if 分类 is None:
            分类 = 读取旧版配置字段(配置, 分类名)
        if isinstance(分类, dict):
            值 = 分类.get(字段名)
            if 值 is not None:
                return 值
        elif 分类 is not None:
            值 = 读取字段(分类, 字段名)
            if 值 is None:
                值 = 读取旧版配置字段(分类, 字段名)
            if 值 is not None:
                return 值
    return None


def 设置配置字段(配置: Any, 字段名: str, 值: Any) -> bool:
    配置字典 = 获取配置字典(配置)
    if 配置字典 is None:
        return False
    分类名 = 配置字段分类映射.get(字段名, (基础配置分类名,))[0]
    分类 = 配置字典.get(分类名)
    if not isinstance(分类, dict):
        分类 = {}
        配置字典[分类名] = 分类
    if 分类.get(字段名) == 值:
        return False
    分类[字段名] = 值
    return True


def 获取配置字典(配置: Any) -> dict[str, Any] | None:
    if 配置 is None:
        return None
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


def 读取旧版配置字段(配置: Any, 字段名: str) -> Any:
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            return 获取方法(字段名)
        except Exception:
            pass
    return getattr(配置, 字段名, None)


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 安全整数(值: Any, 默认值: int = 0) -> int:
    if 值 in (None, "") or isinstance(值, bool):
        return 默认值
    try:
        return int(str(值).strip())
    except Exception:
        return 默认值


def 限制长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."


def 格式化时间戳(时间戳: int) -> str:
    return datetime.fromtimestamp(int(时间戳)).strftime("%Y-%m-%d %H:%M:%S")


def 格式化日期(时间戳: int) -> str:
    if int(时间戳) <= 0:
        return "未知"
    return datetime.fromtimestamp(int(时间戳)).strftime("%Y-%m-%d")


def 格式化剩余时间(秒数: int) -> str:
    秒数 = max(0, int(秒数))
    天数, 余数 = divmod(秒数, 86400)
    小时, 余数 = divmod(余数, 3600)
    分钟, _ = divmod(余数, 60)
    结果: list[str] = []
    if 天数:
        结果.append(f"{天数} 天")
    if 小时:
        结果.append(f"{小时} 小时")
    if 分钟 or not 结果:
        结果.append(f"{分钟} 分钟")
    return " ".join(结果)