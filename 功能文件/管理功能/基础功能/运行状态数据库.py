from __future__ import annotations

import time
import threading
import hashlib
import json
import ipaddress
import re
import socket
import ssl
from typing import Any
from urllib.parse import urlsplit
from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID

运行状态数据库表名 = "mantou_runtime_state"
数据库配置分类名 = "database_settings"
_运行状态表结构版本 = 1
_已确保运行状态表: set[tuple[int, str]] = globals().get("_已确保运行状态表", set())
_运行状态表锁 = globals().get("_运行状态表锁") or threading.Lock()
机器人业务状态命名空间 = frozenset({
    "admin_whitelist", "novel_pan_auth", "novel_pan_account_selection",
    "novel_pan_enabled", "novel_share_pan", "qq_reader_auth",
    "zlibrary_accounts", "novel_feature_switch", "msg_console_layout", "group_ad_protection",
})
_机器人状态快照缓存 = globals().get("_机器人状态快照缓存") or set()
_机器人状态快照锁 = globals().get("_机器人状态快照锁") or threading.RLock()
_机器人快照标记 = "__bot_scope_v1__"


def _机器人状态命名空间(配置: Any, 命名空间: str) -> str:
    原始 = str(命名空间)
    appid = 获取当前机器人AppID(配置)
    if not appid or 原始 not in 机器人业务状态命名空间:
        return 原始
    新空间 = "bot_" + hashlib.sha256(f"{appid}\x1f{原始}".encode()).hexdigest()[:56]
    if not 已配置运行状态数据库(配置):
        return 新空间
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    缓存键 = (*_配置缓存键(数据库配置, 表名), 新空间)
    if 缓存键 in _机器人状态快照缓存:
        return 新空间
    with _机器人状态快照锁:
        if 缓存键 in _机器人状态快照缓存:
            return 新空间
        with 打开数据库连接(数据库配置) as 连接:
            _确保运行状态表一次(连接, 数据库配置, 表名)
            with 连接.cursor() as 游标:
                游标.execute(f"SELECT state_value FROM `{表名}` WHERE namespace=%s AND state_key=%s LIMIT 1", (新空间, _机器人快照标记))
                if 游标.fetchone() is None:
                    # 首次为每个机器人复制一次旧状态；后续不再跟随全局值。
                    # INSERT IGNORE 保留已确认的独立值，并发初始化也不覆盖。
                    游标.execute(
                        f"INSERT IGNORE INTO `{表名}` (namespace,state_key,state_value,updated_at) "
                        f"SELECT %s,state_key,state_value,updated_at FROM `{表名}` WHERE namespace=%s",
                        (新空间, 原始),
                    )
                    游标.execute(
                        f"INSERT IGNORE INTO `{表名}` (namespace,state_key,state_value,updated_at) VALUES (%s,%s,%s,%s)",
                        (新空间, _机器人快照标记, "1", int(time.time())),
                    )
            连接.commit()
        _机器人状态快照缓存.add(缓存键)
    return 新空间


def _配置缓存键(数据库配置: dict[str, Any], 表名: str) -> tuple[int, str]:
    # 密码等配置只参与不可逆指纹；热重载保留成功结果，换连接配置或结构版本重新检查。
    配置文本 = json.dumps({**数据库配置, "runtime_state_table": str(表名 or "")},
                        sort_keys=True, ensure_ascii=False, default=str)
    return _运行状态表结构版本, hashlib.sha256(配置文本.encode("utf-8")).hexdigest()


def _确保运行状态表一次(连接: Any, 数据库配置: dict[str, Any], 表名: str) -> None:
    """进程内缓存建表结果，避免每次状态读写都执行 DDL 和提交。"""
    键 = _配置缓存键(数据库配置, 表名)
    if 键 in _已确保运行状态表:
        return
    with _运行状态表锁:
        if 键 in _已确保运行状态表:
            return
        确保运行状态数据库表(连接, 表名)
        _已确保运行状态表.add(键)


def 读取运行状态值(配置: Any, 命名空间: str, 状态键: str, 默认值: str = "") -> str:
    if not 已配置运行状态数据库(配置):
        return 默认值
    命名空间 = _机器人状态命名空间(配置, 命名空间)
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    with 打开数据库连接(数据库配置) as 连接:
        _确保运行状态表一次(连接, 数据库配置, 表名)
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



def 批量读取运行状态值(
    配置: Any, 查询项: tuple[tuple[str, str], ...],
) -> dict[tuple[str, str], str]:
    """单次查询读取跨命名空间的指定键，不缓存值、不载入无关群状态。"""
    if not 查询项 or not 已配置运行状态数据库(配置):
        return {}
    原查询键 = list(dict.fromkeys((str(空间), str(键)) for 空间, 键 in 查询项))
    查询映射 = {(_机器人状态命名空间(配置, 空间), 键): (空间, 键) for 空间, 键 in 原查询键}
    查询键 = list(查询映射)
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    占位 = ",".join("(%s,%s)" for _ in 查询键)
    参数 = tuple(值 for 项 in 查询键 for 值 in 项)
    with 打开数据库连接(数据库配置) as 连接:
        _确保运行状态表一次(连接, 数据库配置, 表名)
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT namespace, state_key, state_value FROM `{表名}` "
                f"WHERE (namespace, state_key) IN ({占位})",
                参数,
            )
            记录列表 = 游标.fetchall()
    return {
        查询映射[(str(记录[0]), str(记录[1]))]: str(记录[2] if 记录[2] is not None else "")
        for 记录 in 记录列表
    }

def 写入运行状态值(配置: Any, 命名空间: str, 状态键: str, 状态值: Any) -> None:
    命名空间 = _机器人状态命名空间(配置, 命名空间)
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    当前时间 = int(time.time())
    with 打开数据库连接(数据库配置) as 连接:
        _确保运行状态表一次(连接, 数据库配置, 表名)
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


def 批量写入运行状态值(
    配置: Any,
    命名空间: str,
    状态值: dict[str, Any],
) -> None:
    """用单连接单事务写入同一命名空间的多条运行状态。"""
    if not 状态值 or not 已配置运行状态数据库(配置):
        return
    命名空间 = _机器人状态命名空间(配置, 命名空间)
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    当前时间 = int(time.time())
    记录列表 = [
        (str(命名空间), str(状态键), str(状态值项), 当前时间)
        for 状态键, 状态值项 in 状态值.items()
    ]
    if not 记录列表:
        return
    with 打开数据库连接(数据库配置) as 连接:
        _确保运行状态表一次(连接, 数据库配置, 表名)
        with 连接.cursor() as 游标:
            游标.executemany(
                f"""
                INSERT INTO `{表名}` (namespace, state_key, state_value, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE state_value=VALUES(state_value), updated_at=VALUES(updated_at)
                """,
                记录列表,
            )
        连接.commit()


def 读取运行状态命名空间(配置: Any, 命名空间: str) -> dict[str, str]:
    if not 已配置运行状态数据库(配置):
        return {}
    命名空间 = _机器人状态命名空间(配置, 命名空间)
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    with 打开数据库连接(数据库配置) as 连接:
        _确保运行状态表一次(连接, 数据库配置, 表名)
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
        if str(记录[0]) != _机器人快照标记
    }


def 删除运行状态值(配置: Any, 命名空间: str, 状态键: str) -> None:
    """按命名空间+键删除一条运行状态；用于控制台持久会话等场景。"""
    命名空间 = _机器人状态命名空间(配置, 命名空间)
    数据库配置 = 获取数据库配置(配置)
    表名 = 数据库配置.get("runtime_state_table") or 运行状态数据库表名
    with 打开数据库连接(数据库配置) as 连接:
        _确保运行状态表一次(连接, 数据库配置, 表名)
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                DELETE FROM `{表名}`
                WHERE namespace=%s AND state_key=%s
                """,
                (str(命名空间), str(状态键)),
            )
        连接.commit()


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
        or ""
    ).strip() or 用户名
    主机, 端口 = _规范化数据库地址(
        读取数据库配置值(配置, "database_host", "user_activation_database_host"),
        读取数据库配置值(配置, "database_port", "user_activation_database_port"),
    )
    加密模式 = str(读取数据库配置值(配置, "database_ssl_mode") or "preferred").strip().lower()
    if 加密模式 not in {"preferred", "required", "verify_identity", "disabled"}:
        raise 数据库连接错误("configuration")
    超时原值 = 读取数据库配置值(配置, "database_connect_timeout")
    try:
        连接超时 = int(str(超时原值).strip()) if 超时原值 is not None else 10
    except (TypeError, ValueError):
        raise 数据库连接错误("configuration") from None
    if not 1 <= 连接超时 <= 60:
        raise 数据库连接错误("configuration")
    数据库配置 = {
        "host": 主机,
        "port": 端口,
        "user": 用户名,
        "password": str(
            读取数据库配置值(
                配置, "database_password", "user_activation_database_password"
            )
            or ""
        ),
        "database": 数据库名,
        "runtime_state_table": 运行状态数据库表名,
        "ssl_mode": 加密模式,
        "ssl_ca": str(读取数据库配置值(配置, "database_ssl_ca") or "").strip(),
        "connect_timeout": 连接超时,
    }
    缺少字段 = [字段 for 字段 in ("host", "user", "database") if not 数据库配置[字段]]
    if 缺少字段:
        raise 数据库连接错误("configuration")
    return 数据库配置


def 已配置运行状态数据库(配置: Any) -> bool:
    """只判断配置是否完整（库名缺省用用户名）；未配置时读取状态不应尝试连接 MySQL。"""
    用户名 = str(
        读取数据库配置值(配置, "database_user", "user_activation_database_user") or ""
    ).strip()
    主机 = str(
        读取数据库配置值(配置, "database_host", "user_activation_database_host") or ""
    ).strip()
    return bool(主机 and 用户名)


def 检查运行状态数据库(配置: Any) -> str:
    """按需执行一次数据库连通性检查，不返回连接参数或异常原文。"""
    return str(测试运行状态数据库连接(配置)["status"])


数据库连接提示 = {
    "configuration": "数据库配置无效，请检查地址格式、端口、加密模式和超时",
    "dependency": "数据库驱动或认证依赖缺失，请更新插件依赖",
    "dns": "数据库域名解析失败，请检查地址与服务器 DNS",
    "timeout": "数据库连接超时，请检查公网端口、安全组与防火墙",
    "network": "数据库网络连接失败，请检查监听地址、端口和访问规则",
    "tls": "数据库加密连接失败，请检查 TLS 模式与证书",
    "tls_required": "数据库要求加密连接，请启用 TLS",
    "tls_unavailable": "目标数据库未提供 TLS，请检查服务端加密配置",
    "authentication": "数据库账号或密码校验失败",
    "host_denied": "数据库未允许当前服务器访问，请检查账号来源授权",
    "permission": "数据库账号权限不足，请检查目标数据库授权",
    "database_missing": "目标数据库不存在，请先创建数据库或检查库名",
    "auth_plugin": "数据库认证方式不可用，请更新驱动并检查账号认证配置",
    "server_busy": "数据库连接数已满，请稍后重试",
    "unknown": "数据库连接失败，请检查后端受控诊断信息",
}


class 数据库连接错误(RuntimeError):
    def __init__(self, 原因: str, mysql_code: int | None = None):
        self.reason = 原因 if 原因 in 数据库连接提示 else "unknown"
        self.mysql_code = mysql_code
        super().__init__(数据库连接提示[self.reason])


def _规范化数据库地址(地址: Any, 端口: Any = None) -> tuple[str, int]:
    文本 = str(地址 or "").strip()
    if not 文本 or re.search(r"[\s\x00-\x1f\x7f]", 文本):
        raise 数据库连接错误("configuration")
    独立端口 = None
    if 端口 is not None and str(端口).strip():
        try:
            独立端口 = int(str(端口).strip())
        except (TypeError, ValueError):
            raise 数据库连接错误("configuration") from None
    try:
        if "://" not in 文本 and 文本.count(":") > 1 and not 文本.startswith("["):
            ipaddress.IPv6Address(文本)
            主机, 内嵌端口 = 文本, None
        else:
            解析 = urlsplit(文本 if "://" in 文本 else "mysql://" + 文本)
            if (解析.scheme.lower() != "mysql" or 解析.username is not None
                    or 解析.password is not None or 解析.path not in {"", "/"}
                    or 解析.query or 解析.fragment):
                raise ValueError("address")
            主机, 内嵌端口 = 解析.hostname or "", 解析.port
        if not 主机 or any(符号 in 主机 for 符号 in "/\\@?#;"):
            raise ValueError("host")
        if ":" not in 主机:
            主机 = 主机.encode("idna").decode("ascii")
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,253}", 主机):
                raise ValueError("host")
        else:
            ipaddress.IPv6Address(主机)
    except (ValueError, UnicodeError):
        raise 数据库连接错误("configuration") from None
    if 独立端口 is not None and 内嵌端口 is not None and 独立端口 != 内嵌端口:
        raise 数据库连接错误("configuration")
    最终端口 = 独立端口 if 独立端口 is not None else 内嵌端口 if 内嵌端口 is not None else 3306
    if not 1 <= 最终端口 <= 65535:
        raise 数据库连接错误("configuration")
    return 主机, 最终端口


def _分类数据库连接异常(异常: BaseException) -> tuple[str, int | None]:
    已检查: set[int] = set()
    待检查: list[BaseException] = [异常]
    错误码 = None
    while 待检查:
        当前 = 待检查.pop(0)
        if id(当前) in 已检查:
            continue
        已检查.add(id(当前))
        if isinstance(当前, 数据库连接错误):
            return 当前.reason, 当前.mysql_code
        if isinstance(当前, (ImportError, ModuleNotFoundError)):
            return "dependency", 错误码
        if isinstance(当前, socket.gaierror):
            return "dns", 错误码
        if isinstance(当前, ssl.SSLError):
            return "tls", 错误码
        if isinstance(当前, (TimeoutError, socket.timeout)):
            return "timeout", 错误码
        参数 = getattr(当前, "args", ())
        if 参数 and type(参数[0]) is int and 1000 <= 参数[0] <= 9999:
            错误码 = 参数[0]
        # PyMySQL 对操作系统连接异常保留 original_exception。
        for 关联 in (getattr(当前, "original_exception", None), 当前.__cause__, 当前.__context__):
            if isinstance(关联, BaseException):
                待检查.append(关联)
        if isinstance(当前, RuntimeError) and "cryptography" in str(当前).lower():
            return "dependency", 错误码
    原因 = {
        1040: "server_busy", 1044: "permission", 1045: "authentication", 1049: "database_missing",
        1130: "host_denied", 1142: "permission", 1143: "permission", 1251: "auth_plugin",
        1524: "auth_plugin", 2002: "network", 2003: "network", 2005: "dns",
        2006: "network", 2013: "network", 2026: "tls", 2059: "auth_plugin",
        2061: "auth_plugin", 3159: "tls_required",
    }.get(错误码, "network" if isinstance(异常, OSError) else "unknown")
    return 原因, 错误码


def _建立数据库连接(数据库配置: dict[str, Any]) -> Any:
    try:
        import pymysql
        from pymysql.constants import CLIENT
    except ImportError as 异常:
        raise 数据库连接错误("dependency") from 异常
    模式 = str(数据库配置.get("ssl_mode") or "preferred")
    if 模式 not in {"preferred", "required", "verify_identity", "disabled"}:
        raise 数据库连接错误("configuration")
    参数 = {
        "host": 数据库配置["host"], "port": 数据库配置["port"],
        "user": 数据库配置["user"], "password": 数据库配置["password"],
        "database": 数据库配置["database"], "charset": "utf8mb4", "autocommit": False,
        "connect_timeout": 数据库配置.get("connect_timeout", 10),
        "read_timeout": max(15, 数据库配置.get("connect_timeout", 10)),
        "write_timeout": max(15, 数据库配置.get("connect_timeout", 10)),
    }
    if 模式 != "disabled":
        if 模式 == "verify_identity":
            try:
                参数["ssl"] = ssl.create_default_context(cafile=数据库配置.get("ssl_ca") or None)
            except (OSError, ssl.SSLError) as 异常:
                raise 数据库连接错误("tls") from 异常
        else:
            上下文 = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            上下文.check_hostname = False
            上下文.verify_mode = ssl.CERT_NONE
            参数["ssl"] = 上下文
    else:
        参数["ssl_disabled"] = True
    if 模式 in {"required", "verify_identity"}:
        class 必须加密连接(pymysql.connections.Connection):
            def _request_authentication(self):
                # 上游仅在服务端声明 SSL 时协商；在认证发送前强制拒绝无 TLS 服务端。
                if not self.server_capabilities & CLIENT.SSL:
                    raise 数据库连接错误("tls_unavailable")
                return super()._request_authentication()
        return 必须加密连接(**参数)
    return pymysql.connect(**参数)


def 测试运行状态数据库连接(配置: Any) -> dict[str, Any]:
    """只连接指定数据库并 SELECT，探测不创建库、表或运行状态。"""
    if not 已配置运行状态数据库(配置):
        return {"ok": False, "status": "未配置", "reason": "configuration", "message": "请先填写数据库地址和用户名", "mysql_code": None, "version": "", "tls": False}
    连接 = None
    try:
        数据库配置 = 获取数据库配置(配置)
        连接 = _建立数据库连接(数据库配置)
        with 连接.cursor() as 游标:
            游标.execute("SELECT 1, VERSION()")
            记录 = 游标.fetchone()
        版本原文 = str((记录.get("VERSION()") if isinstance(记录, dict) else 记录[1]) or "")
        版本 = re.match(r"[0-9]+(?:\.[0-9]+){1,3}(?:-MariaDB)?", 版本原文)
        return {"ok": True, "status": "正常", "reason": "connected", "message": "数据库连接正常", "mysql_code": None, "version": 版本.group(0) if 版本 else "", "tls": bool(getattr(连接, "_secure", False))}
    except Exception as 异常:
        原因, 错误码 = _分类数据库连接异常(异常)
        return {"ok": False, "status": "异常", "reason": 原因, "message": 数据库连接提示[原因], "mysql_code": 错误码, "version": "", "tls": False}
    finally:
        if 连接 is not None:
            try:
                连接.close()
            except Exception:
                pass


def 打开数据库连接(数据库配置: dict[str, Any]) -> Any:
    """打开 MySQL 连接；目标库不存在时自动创建。"""
    库名 = str(数据库配置.get("database") or "").strip()
    if not 库名:
        raise 数据库连接错误("configuration")
    临时连接 = None
    try:
        return _建立数据库连接(数据库配置)
    except Exception as 连接异常:
        # 只有 MySQL 1049（未知数据库）需要建库。网络/鉴权失败继续建库
        # 只会重复等待连接超时，占住控制台或消息写入线程。
        原因, 错误码 = _分类数据库连接异常(连接异常)
        if 错误码 != 1049:
            raise 数据库连接错误(原因, 错误码) from 连接异常
        try:
            临时连接 = _建立数据库连接({**数据库配置, "database": None})
            with 临时连接.cursor() as 游标:
                游标.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{库名.replace('`', '``')}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            临时连接.commit()
            return _建立数据库连接(数据库配置)
        except Exception as 建库异常:
            原因, 错误码 = _分类数据库连接异常(建库异常)
            raise 数据库连接错误(原因, 错误码) from 建库异常
        finally:
            if 临时连接 is not None:
                try:
                    临时连接.close()
                except Exception:
                    pass


_配置字段缺失 = object()


def 读取数据库配置值(配置: Any, *字段列表: str) -> Any:
    """规范字段只有真正缺失时才兼容旧别名，明确空值不复活旧连接参数。"""
    for 字段名 in 字段列表:
        值 = 读取配置字段(配置, 字段名, _配置字段缺失)
        if 值 is not _配置字段缺失:
            return 值
    return None


def 读取配置字段(配置: Any, 字段名: str, 默认值: Any = None) -> Any:
    if 配置 is None:
        return 默认值
    配置字典 = 获取配置字典(配置)
    来源列表 = [配置字典] if 配置字典 is not None else []
    if 配置字典 is not 配置:
        来源列表.append(配置)
    for 来源 in 来源列表:
        # 与网页编辑器一致：当前 schema 分类优先于旧根字段。
        # 中文旧分类仅在两种规范存储均缺失时兼容，空串/None 都是明确值。
        for 分类名 in (数据库配置分类名, None, "数据库配置"):
            分类 = 来源 if 分类名 is None else 读取字段(来源, 分类名, _配置字段缺失)
            if 分类 is _配置字段缺失 or 分类 is None:
                continue
            值 = 读取字段(分类, 字段名, _配置字段缺失)
            if 值 is not _配置字段缺失:
                return 值
    return 默认值


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


def 读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名, 默认值)
    值 = getattr(对象, 字段名, _配置字段缺失)
    if 值 is not _配置字段缺失:
        return 值
    return 读取旧版配置字段(对象, 字段名, 默认值)


def 读取旧版配置字段(配置: Any, 字段名: str, 默认值: Any = None) -> Any:
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            return 获取方法(字段名, 默认值)
        except TypeError:
            # 仅接受单参数的旧对象无存在性接口时，None 保持缺失语义。
            try:
                值 = 获取方法(字段名)
                return 默认值 if 值 is None else 值
            except Exception:
                pass
        except Exception:
            pass
    return 默认值


def 安全整数(值: Any, 默认值: int) -> int:
    try:
        return int(str(值).strip())
    except (TypeError, ValueError):
        return 默认值
