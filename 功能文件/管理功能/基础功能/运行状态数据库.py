from __future__ import annotations

import time
from typing import Any

运行状态数据库表名 = "mantou_runtime_state"
数据库配置分类名 = "database_settings"


def 读取运行状态值(配置: Any, 命名空间: str, 状态键: str, 默认值: str = "") -> str:
    if not 已配置运行状态数据库(配置):
        return 默认值
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
    if not 已配置运行状态数据库(配置):
        return {}
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
        str(记录[0]): str(记录[1] if 记录[1] is not None else "") for 记录 in 记录列表
    }


def 读取布尔运行状态值(
    配置: Any, 命名空间: str, 状态键: str, 默认值: bool = True
) -> bool:
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
    """读取通用运行状态数据库配置，并兼容历史配置字段。"""
    用户名 = str(
        读取数据库配置值(配置, "database_user", "user_activation_database_user") or ""
    ).strip()
    数据库名 = str(
        读取数据库配置值(配置, "database_name", "user_activation_database_name")
        or 用户名
    ).strip()
    数据库配置 = {
        "host": str(
            读取数据库配置值(配置, "database_host", "user_activation_database_host")
            or ""
        ).strip(),
        "port": 安全整数(
            读取数据库配置值(配置, "database_port", "user_activation_database_port"),
            3306,
        ),
        "user": 用户名,
        "password": str(
            读取数据库配置值(
                配置, "database_password", "user_activation_database_password"
            )
            or ""
        ),
        "database": 数据库名,
        "runtime_state_table": 运行状态数据库表名,
    }
    缺少字段 = [字段 for 字段 in ("host", "user", "database") if not 数据库配置[字段]]
    if 缺少字段:
        raise RuntimeError(f"数据库配置不完整：缺少 {', '.join(缺少字段)}")
    return 数据库配置


def 已配置运行状态数据库(配置: Any) -> bool:
    """只判断配置是否完整；未配置时读取状态不应尝试连接 MySQL。"""
    用户名 = str(
        读取数据库配置值(配置, "database_user", "user_activation_database_user") or ""
    ).strip()
    数据库名 = str(
        读取数据库配置值(配置, "database_name", "user_activation_database_name")
        or 用户名
    ).strip()
    主机 = str(
        读取数据库配置值(配置, "database_host", "user_activation_database_host") or ""
    ).strip()
    return bool(主机 and 用户名 and 数据库名)


def 检查运行状态数据库(配置: Any) -> str:
    """按需执行一次数据库连通性检查，不返回连接参数或异常原文。"""
    if not 已配置运行状态数据库(配置):
        return "未配置"
    try:
        数据库配置 = 获取数据库配置(配置)
        with 打开数据库连接(数据库配置) as 连接:
            with 连接.cursor() as 游标:
                游标.execute("SELECT 1")
                游标.fetchone()
        return "正常"
    except Exception:
        return "异常"


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


def 读取数据库配置值(配置: Any, *字段列表: str) -> Any:
    for 字段名 in 字段列表:
        值 = 读取配置字段(配置, 字段名)
        if 值 is None:
            continue
        if isinstance(值, str) and not 值.strip():
            continue
        return 值
    return None


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

    for 分类名 in (数据库配置分类名, "数据库配置"):
        分类 = 读取字段(配置, 分类名)
        if 分类 is None:
            分类 = 读取旧版配置字段(配置, 分类名)
        if 分类 is None:
            continue
        值 = 读取字段(分类, 字段名)
        if 值 is None:
            值 = 读取旧版配置字段(分类, 字段名)
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


def 读取字段(对象: Any, 字段名: str) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 读取旧版配置字段(配置: Any, 字段名: str) -> Any:
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            return 获取方法(字段名)
        except Exception:
            pass
    return None


def 安全整数(值: Any, 默认值: int) -> int:
    try:
        return int(str(值).strip())
    except (TypeError, ValueError):
        return 默认值
