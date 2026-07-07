from __future__ import annotations

import importlib
import time
from typing import Any


运行状态数据库表名 = "mantou_runtime_state"


def 读取运行状态值(配置: Any, 命名空间: str, 状态键: str, 默认值: str = "") -> str:
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    with 打开数据库连接(数据库配置) as 连接:
        确保运行状态数据库表(连接, 表名)
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT state_value
                FROM `{表名}`
                WHERE namespace=%s AND state_key=%s
                LIMIT 1
                """,
                (str(命名空间), str(状态键)),
            )
            记录 = 游标.fetchone()
    if not 记录:
        return 默认值
    return str(记录[0] if 记录[0] is not None else 默认值)


def 写入运行状态值(配置: Any, 命名空间: str, 状态键: str, 状态值: Any) -> None:
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    当前时间 = int(time.time())
    with 打开数据库连接(数据库配置) as 连接:
        确保运行状态数据库表(连接, 表名)
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                INSERT INTO `{表名}` (namespace, state_key, state_value, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE state_value=VALUES(state_value), updated_at=VALUES(updated_at)
                """,
                (str(命名空间), str(状态键), str(状态值), 当前时间),
            )
        连接.commit()


def 读取运行状态命名空间(配置: Any, 命名空间: str) -> dict[str, str]:
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    with 打开数据库连接(数据库配置) as 连接:
        确保运行状态数据库表(连接, 表名)
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT state_key, state_value
                FROM `{表名}`
                WHERE namespace=%s
                """,
                (str(命名空间),),
            )
            记录列表 = 游标.fetchall()
    return {
        str(记录[0]): str(记录[1] if 记录[1] is not None else "")
        for 记录 in 记录列表
    }


def 读取布尔运行状态值(配置: Any, 命名空间: str, 状态键: str, 默认值: bool = True) -> bool:
    默认文本 = "1" if 默认值 else "0"
    文本 = 读取运行状态值(配置, 命名空间, 状态键, 默认文本).strip().lower()
    if 文本 in {"1", "true", "yes", "on", "开启"}:
        return True
    if 文本 in {"0", "false", "no", "off", "关闭"}:
        return False
    return bool(默认值)


def 写入布尔运行状态值(配置: Any, 命名空间: str, 状态键: str, 状态值: bool) -> None:
    写入运行状态值(配置, 命名空间, 状态键, "1" if 状态值 else "0")


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
    return 获取用户激活模块().获取数据库配置(配置)


def 打开数据库连接(数据库配置: dict[str, Any]) -> Any:
    return 获取用户激活模块().打开数据库连接(数据库配置)


def 获取用户激活模块() -> Any:
    return importlib.import_module("功能文件.管理功能.基础功能.用户激活")
