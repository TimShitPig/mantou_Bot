from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
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

from 功能文件.管理功能.权限工具 import 是群文件清理管理员, 获取发送者QQ


未激活提示 = "请查看群公告查看激活方法"
默认激活天数 = 30
最长激活天数 = 3650
下载缓存目录 = Path(__file__).resolve().parents[1] / "下载缓存"
默认本地激活文件 = 下载缓存目录 / "用户激活.json"
用户操作命令规则 = re.compile(r"^(?:用户)?(?:激活|重置)(?:\d+)?(?:\s+\S+){0,3}$")
用户操作命令开头 = ("激活", "用户激活", "重置", "用户重置")
数字规则 = re.compile(r"\d+")
用户编号规则 = re.compile(r"^[A-Za-z0-9_-]{5,64}$")
数据库表名规则 = re.compile(r"^[A-Za-z0-9_]{1,64}$")
需激活文本命令 = {"随机英文单词", "随机一言", "疯狂星期四", "古诗词名句"}


async def 处理用户激活(event: Any, 命令文本: str, 配置: Any, context: Any = None) -> str | None:
    激活参数 = 解析激活命令(event, 命令文本, context)
    if 激活参数 is None:
        return None
    记录用户激活诊断(event, 命令文本, 激活参数, context)
    if not 是群文件清理管理员(event, 配置):
        return "没有权限使用用户激活"

    操作 = 激活参数.get("action") or "激活"
    目标用户 = 激活参数.get("target_user_id") or ""
    if not 目标用户:
        动作名 = "重置" if 操作 == "重置" else "激活"
        return f"用户{动作名}失败：请 @ 要{动作名}的用户"

    群号 = 获取群号(event)
    if not 群号:
        动作名 = "重置" if 操作 == "重置" else "激活"
        return f"用户{动作名}失败：只能在群聊中{动作名}用户"

    if 操作 == "重置":
        try:
            await 删除激活记录(配置, 群号, 目标用户)
        except Exception as exc:
            logger.warning(f"用户激活重置失败：group_id={群号}, user_id={目标用户}, error={exc}")
            return f"用户重置失败：{exc}"
        return f"已取消用户激活：{目标用户}"

    天数 = 安全整数(激活参数.get("days"), 默认激活天数)
    if 天数 <= 0:
        return "用户激活失败：激活天数必须是正整数"
    if 天数 > 最长激活天数:
        return f"用户激活失败：激活天数不能超过 {最长激活天数} 天"

    到期时间 = int(time.time()) + 天数 * 86400
    try:
        await 写入激活记录(配置, 群号, 目标用户, 到期时间)
    except Exception as exc:
        logger.warning(f"用户激活写入失败：group_id={群号}, user_id={目标用户}, error={exc}")
        return f"用户激活失败：{exc}"

    return "\n".join(
        [
            f"已激活用户：{目标用户}",
            f"有效期：{天数} 天",
            f"到期时间：{格式化时间戳(到期时间)}",
        ]
    )


async def 获取未激活拦截回复(event: Any, 配置: Any) -> str | None:
    if await 用户可使用功能(event, 配置):
        return None
    return 未激活提示


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


def 解析激活命令(event: Any, 命令文本: str, context: Any = None) -> dict[str, Any] | None:
    文本 = 提取激活命令文本(event, 命令文本)
    if not 文本 or not 用户操作命令规则.fullmatch(文本):
        return None

    操作 = 提取用户操作(文本)
    if not 操作:
        return None

    At用户列表 = 获取At用户列表(event)
    数字列表 = [int(匹配.group(0)) for 匹配 in 数字规则.finditer(文本)]
    目标用户, 天数 = 从命令文本提取用户和天数(文本)

    被艾特用户 = 提取被艾特用户QQ(event, At用户列表, context)
    if 被艾特用户:
        return {"action": 操作, "target_user_id": 被艾特用户, "days": 数字列表[0] if 数字列表 else 天数}
    if 目标用户:
        return {"action": 操作, "target_user_id": 目标用户, "days": 天数}
    if At用户列表:
        return {"action": 操作, "target_user_id": At用户列表[0], "days": 数字列表[0] if 数字列表 else 天数}

    return {"action": 操作, "target_user_id": 目标用户, "days": 天数}


def 提取用户操作(文本: str) -> str:
    头部 = str(文本 or "").split(maxsplit=1)[0]
    if 头部.startswith("用户激活") or 头部.startswith("激活"):
        return "激活"
    if 头部.startswith("用户重置") or 头部.startswith("重置"):
        return "重置"
    return ""


def 从命令文本提取用户和天数(文本: str) -> tuple[str, int]:
    项目列表 = 文本.split()
    if len(项目列表) < 2:
        return "", 默认激活天数

    目标用户 = str(项目列表[1]).strip()
    if not 用户编号规则.fullmatch(目标用户):
        return "", 默认激活天数

    天数 = 默认激活天数
    if len(项目列表) >= 3:
        天数 = 安全整数(项目列表[2], 默认激活天数)
    return 目标用户, 天数


def 提取被艾特用户QQ(event: Any, At用户列表: list[str] | None = None, context: Any = None) -> str:
    用户列表 = At用户列表 or 获取At用户列表(event)
    if not 用户列表:
        return ""
    忽略用户 = 获取应忽略At用户(event, context)
    for 用户 in 用户列表:
        if 用户 not in 忽略用户:
            return 用户
    return ""


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


def 清理激活命令文本(文本: Any) -> str:
    结果 = str(文本 or "")
    结果 = re.sub(r"\[CQ:reply,[^\]]*\]", "", 结果, flags=re.IGNORECASE)
    结果 = re.sub(r"\[CQ:at,[^\]]*\]", "", 结果, flags=re.IGNORECASE)
    结果 = re.sub(r"\[At:[^\]]+\]", "", 结果, flags=re.IGNORECASE)
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


async def 读取激活到期时间(配置: Any, 群号: str, 用户编号: str) -> int:
    if 使用数据库存储(配置):
        return await asyncio.to_thread(读取数据库激活到期时间, 配置, 群号, 用户编号)
    return 读取本地激活到期时间(配置, 群号, 用户编号)


async def 写入激活记录(配置: Any, 群号: str, 用户编号: str, 到期时间: int) -> None:
    if 使用数据库存储(配置):
        await asyncio.to_thread(写入数据库激活记录, 配置, 群号, 用户编号, 到期时间)
        return
    写入本地激活记录(配置, 群号, 用户编号, 到期时间)


async def 删除激活记录(配置: Any, 群号: str, 用户编号: str) -> None:
    if 使用数据库存储(配置):
        await asyncio.to_thread(删除数据库激活记录, 配置, 群号, 用户编号)
        return
    删除本地激活记录(配置, 群号, 用户编号)


def 读取本地激活到期时间(配置: Any, 群号: str, 用户编号: str) -> int:
    数据 = 读取本地激活数据(配置)
    记录 = 数据.get(激活记录键(群号, 用户编号))
    if not isinstance(记录, dict):
        return 0
    到期时间 = 安全整数(记录.get("expires_at"), 0)
    if 到期时间 < int(time.time()):
        return 0
    return 到期时间


def 写入本地激活记录(配置: Any, 群号: str, 用户编号: str, 到期时间: int) -> None:
    路径 = 获取本地激活文件路径(配置)
    路径.parent.mkdir(parents=True, exist_ok=True)
    数据 = 读取本地激活数据(配置)
    数据[激活记录键(群号, 用户编号)] = {
        "group_id": str(群号),
        "user_id": str(用户编号),
        "expires_at": int(到期时间),
        "updated_at": int(time.time()),
    }
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2), encoding="utf-8")


def 删除本地激活记录(配置: Any, 群号: str, 用户编号: str) -> None:
    路径 = 获取本地激活文件路径(配置)
    if not 路径.exists():
        return
    数据 = 读取本地激活数据(配置)
    数据.pop(激活记录键(群号, 用户编号), None)
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2), encoding="utf-8")


def 读取本地激活数据(配置: Any) -> dict[str, Any]:
    路径 = 获取本地激活文件路径(配置)
    if not 路径.exists():
        return {}
    try:
        数据 = json.loads(路径.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"用户激活本地记录读取失败：file={路径}, error={exc}")
        return {}
    return 数据 if isinstance(数据, dict) else {}


def 获取本地激活文件路径(配置: Any) -> Path:
    配置路径 = str(读取配置字段(配置, "user_activation_local_file") or "").strip()
    if 配置路径:
        return Path(配置路径)
    return 默认本地激活文件


def 读取数据库激活到期时间(配置: Any, 群号: str, 用户编号: str) -> int:
    数据库配置 = 获取数据库配置(配置)
    with 打开数据库连接(数据库配置) as 连接:
        确保数据库表(连接, 数据库配置["table"])
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT expires_at FROM `{数据库配置['table']}` WHERE group_id=%s AND user_id=%s LIMIT 1",
                (str(群号), str(用户编号)),
            )
            记录 = 游标.fetchone()
    if not 记录:
        return 0
    到期时间 = 安全整数(记录[0], 0)
    return 到期时间 if 到期时间 >= int(time.time()) else 0


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


def 获取数据库配置(配置: Any) -> dict[str, Any]:
    表名 = str(读取配置字段(配置, "user_activation_database_table") or "mantou_user_activation").strip()
    if not 数据库表名规则.fullmatch(表名):
        raise RuntimeError("用户激活数据库表名只能包含字母、数字和下划线")

    数据库配置 = {
        "host": str(读取配置字段(配置, "user_activation_database_host") or "").strip(),
        "port": 安全整数(读取配置字段(配置, "user_activation_database_port"), 3306),
        "user": str(读取配置字段(配置, "user_activation_database_user") or "").strip(),
        "password": str(读取配置字段(配置, "user_activation_database_password") or ""),
        "database": str(读取配置字段(配置, "user_activation_database_name") or "").strip(),
        "table": 表名,
    }
    缺少字段 = [键 for 键 in ("host", "user", "database") if not 数据库配置[键]]
    if 缺少字段:
        raise RuntimeError(f"用户激活数据库配置不完整：缺少 {', '.join(缺少字段)}")
    return 数据库配置


def 使用数据库存储(配置: Any) -> bool:
    值 = 读取配置字段(配置, "user_activation_database_enabled")
    return str(值 or "").strip().lower() in {"1", "true", "yes", "on", "启用", "开启"}


def 激活记录键(群号: str, 用户编号: str) -> str:
    return f"{群号}:{用户编号}"


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "group_id") or 读取字段(对象, "group")
        if isinstance(值, dict):
            值 = 值.get("group_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 读取配置字段(配置: Any, 字段名: str) -> Any:
    if 配置 is None:
        return None
    if isinstance(配置, dict):
        return 配置.get(字段名)
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
