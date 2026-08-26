# -*- coding: utf-8 -*-
"""消息记录 MySQL 持久化层。

- 消息记录写入 mantou_message_records 表（自动建表，带会话/时间与消息 ID 索引）。
- 置顶/备注/昵称等元数据写入现有 mantou_runtime_state 表（namespace 隔离）。
- 依赖插件 database_settings 配置；未配置时接口直接返回默认值/空，
  不尝试连接数据库、不刷告警（与运行状态数据库一致）。
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

消息记录表名 = "mantou_message_records"
元数据命名空间 = "message_panel_meta"

# 各 VARCHAR 列的最大字符数，写入前按列宽截断，避免 DataError (1406 Data too long)
_列最大长度: dict[str, int] = {
    "会话标识": 128,
    "消息类型": 16,
    "appid": 64,
    "message_id": 128,
    "user_id": 128,
    "nickname": 255,
    "timestamp": 32,
    "source": 32,
    "reference_id": 128,
    "refidx": 128,
}

_数据库配置引用: dict[str, Any] = {}


def _运行状态表名() -> str:
    """返回与运行状态数据库相同的表名，避免消息面板读写另一张表。"""
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        配置 = 运行状态数据库.获取数据库配置(_读取插件配置())
        表名 = str(配置.get("runtime_state_table") or 运行状态数据库.运行状态数据库表名).strip()
    except Exception:
        表名 = "mantou_runtime_state"
    # 表名不能使用参数占位符，只接受数据库标识符，防止配置值破坏 SQL。
    if not re.fullmatch(r"[A-Za-z0-9_]+", 表名):
        return "mantou_runtime_state"
    return 表名


def _行字段(行: Any, 索引: int, *字段名: str, 默认值: Any = None) -> Any:
    """兼容 PyMySQL 元组游标和 DictCursor，避免字典行按数字索引触发 TypeError。"""
    if isinstance(行, Mapping):
        for 字段 in 字段名:
            if 字段 in 行:
                return 行.get(字段)
        return 默认值
    try:
        return 行[索引] if 索引 < len(行) else 默认值
    except (IndexError, KeyError, TypeError):
        return 默认值


def 设置数据库配置(配置: Any) -> None:
    """注入插件配置引用，用于读取 MySQL 连接信息。"""
    _数据库配置引用["配置"] = 配置


def _读取插件配置() -> Any:
    return _数据库配置引用.get("配置")


def _MySQL可用() -> bool:
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        return 运行状态数据库.已配置运行状态数据库(_读取插件配置())
    except Exception:
        return False


def _打开连接() -> Any | None:
    """打开 MySQL 连接；失败返回 None。"""
    try:
        from 功能文件.管理功能.基础功能 import 运行状态数据库

        if not 运行状态数据库.已配置运行状态数据库(_读取插件配置()):
            return None
        配置 = 运行状态数据库.获取数据库配置(_读取插件配置())
        return 运行状态数据库.打开数据库连接(配置)
    except Exception as exc:
        logger.warning("消息记录 MySQL 连接失败：错误类型=%s", type(exc).__name__)
        return None


def _关闭连接(连接: Any | None) -> None:
    if 连接 is None:
        return
    try:
        连接.close()
    except Exception:
        pass


def 初始化数据库() -> bool:
    """建消息记录表与元数据表；返回是否成功。"""
    if not _MySQL可用():
        return False
    连接 = _打开连接()
    if 连接 is None:
        return False
    状态表名 = _运行状态表名()
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{消息记录表名}` (
                    id BIGINT NOT NULL AUTO_INCREMENT,
                    会话标识 VARCHAR(128) NOT NULL,
                    消息类型 VARCHAR(16) DEFAULT 'group',
                    appid VARCHAR(64) DEFAULT '',
                    message_id VARCHAR(128) DEFAULT '',
                    user_id VARCHAR(128) DEFAULT '',
                    nickname VARCHAR(255) DEFAULT '',
                    content MEDIUMTEXT,
                    timestamp VARCHAR(32) DEFAULT '',
                    ts BIGINT DEFAULT 0,
                    is_self TINYINT DEFAULT 0,
                    source VARCHAR(32) DEFAULT '',
                    recalled TINYINT DEFAULT 0,
                    media TEXT,
                    reference_id VARCHAR(128) DEFAULT '',
                    refidx VARCHAR(128) DEFAULT '',
                    raw_message MEDIUMTEXT,
                    PRIMARY KEY (id),
                    KEY idx_msg_records_session (会话标识, ts),
                    KEY idx_msg_records_message (message_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            游标.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{状态表名}` (
                    namespace VARCHAR(64) NOT NULL,
                    state_key VARCHAR(128) NOT NULL,
                    state_value TEXT NOT NULL,
                    updated_at BIGINT NOT NULL,
                    PRIMARY KEY (namespace, state_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            # 表结构检查必须在游标仍有效时执行。旧实现离开 with 后复用已关闭游标，
            # 导致字符集和历史列修复被异常吞掉。
            try:
                游标.execute(
                    "SELECT CHARACTER_SET_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'content'",
                    (消息记录表名,),
                )
                行 = 游标.fetchone()
                if str(_行字段(行, 0, "CHARACTER_SET_NAME", 默认值="") or "").lower() != "utf8mb4":
                    游标.execute(f"ALTER TABLE `{消息记录表名}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    logger.warning("消息记录 MySQL 表已转为 utf8mb4")
                for 列名, 定义 in (
                    ("refidx", "VARCHAR(128) DEFAULT ''"),
                    ("recalled", "TINYINT DEFAULT 0"),
                    ("reference_id", "VARCHAR(128) DEFAULT ''"),
                    ("media", "TEXT"),
                    ("source", "VARCHAR(32) DEFAULT ''"),
                ):
                    游标.execute(
                        "SELECT COUNT(*) FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                        (消息记录表名, 列名),
                    )
                    if int(_行字段(游标.fetchone(), 0, "COUNT(*)", 默认值=0) or 0) == 0:
                        游标.execute(f"ALTER TABLE `{消息记录表名}` ADD COLUMN `{列名}` {定义}")
                        logger.warning("消息记录 MySQL 表已补列 %s", 列名)
                # 旧版本可能把长字段建成 TEXT；原始消息/卡片超过 64KB 时会直接 DataError。
                for 列名 in ("content", "media", "raw_message"):
                    游标.execute(
                        "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                        (消息记录表名, 列名),
                    )
                    数据类型 = str(_行字段(游标.fetchone(), 0, "DATA_TYPE", 默认值="") or "").lower()
                    if 数据类型 and 数据类型 not in {"mediumtext", "longtext"}:
                        游标.execute(f"ALTER TABLE `{消息记录表名}` MODIFY COLUMN `{列名}` MEDIUMTEXT")
                        logger.warning("消息记录 MySQL 长字段已扩容：列=%s", 列名)
            except Exception as 修复异常:
                logger.debug("消息记录 MySQL 表结构检查跳过：错误类型=%s", type(修复异常).__name__)
        连接.commit()
        return True
    except Exception as exc:
        logger.warning("消息记录 MySQL 建表失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def _按列宽截断(值: Any, 列名: str) -> str:
    文本 = str(值 if 值 is not None else "")
    上限 = _列最大长度.get(列名)
    if 上限 and len(文本) > 上限:
        return 文本[:上限]
    return 文本


def _写入消息记录(记录: dict[str, Any]) -> bool:
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"INSERT INTO `{消息记录表名}` (会话标识, 消息类型, appid, message_id, user_id, nickname, content, timestamp, ts, is_self, source, recalled, media, reference_id, refidx, raw_message) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    _按列宽截断(记录.get("_session") or "", "会话标识"),
                    _按列宽截断(记录.get("chat_type") or "group", "消息类型"),
                    _按列宽截断(记录.get("appid") or "", "appid"),
                    _按列宽截断(记录.get("message_id") or "", "message_id"),
                    _按列宽截断(记录.get("user_id") or "", "user_id"),
                    _按列宽截断(记录.get("nickname") or "", "nickname"),
                    str(记录.get("content") or ""),
                    _按列宽截断(记录.get("timestamp") or "", "timestamp"),
                    int(记录.get("ts") or 0),
                    1 if 记录.get("is_self") else 0,
                    _按列宽截断(记录.get("source") or "", "source"),
                    1 if 记录.get("recalled") else 0,
                    json.dumps(记录.get("media") or {}, ensure_ascii=False),
                    _按列宽截断(记录.get("reference_id") or "", "reference_id"),
                    _按列宽截断(记录.get("refidx") or "", "refidx"),
                    str(记录.get("raw_message") or ""),
                ),
            )
        连接.commit()
        return True
    except Exception as exc:
        logger.warning(
            "消息记录 MySQL 写入失败：错误类型=%s，详情=%s",
            type(exc).__name__,
            str(exc)[:600],
        )
        return False
    finally:
        _关闭连接(连接)


def 写入消息(记录: dict[str, Any]) -> bool:
    """写入一条消息记录，返回是否已提交。"""
    if not 记录 or not 记录.get("_session"):
        return False
    if not _MySQL可用():
        return False
    return _写入消息记录(记录)


def 标记消息撤回(会话标识: str, message_id: str) -> bool:
    会话标识 = str(会话标识 or "")
    message_id = str(message_id or "")
    if not message_id or not _MySQL可用():
        return False
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"UPDATE `{消息记录表名}` SET recalled=1 WHERE 会话标识=%s AND message_id=%s",
                (会话标识, message_id),
            )
        连接.commit()
        return True
    except Exception as exc:
        logger.warning("消息记录 MySQL 撤回标记失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def 读取会话消息(会话标识: str, 上限: int = 500) -> list[dict[str, Any]]:
    """按时间正序返回某会话最近 N 条消息。"""
    if not _MySQL可用():
        return []
    上限 = max(1, min(上限, 5000))
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT * FROM (SELECT * FROM `{消息记录表名}` WHERE 会话标识=%s ORDER BY ts DESC, id DESC LIMIT %s) t ORDER BY ts ASC, id ASC",
                (str(会话标识 or ""), 上限),
            )
            行列表 = 游标.fetchall()
        return [_行转记录(行) for 行 in 行列表]
    except Exception as exc:
        logger.warning("消息记录 MySQL 读取失败：错误类型=%s", type(exc).__name__)
        return []
    finally:
        _关闭连接(连接)


def 读取全部会话标识() -> list[str]:
    if not _MySQL可用():
        return []
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            游标.execute(f"SELECT DISTINCT 会话标识 FROM `{消息记录表名}`")
            return [
                str(_行字段(行, 0, "会话标识", 默认值=""))
                for 行 in 游标.fetchall()
                if _行字段(行, 0, "会话标识", 默认值="")
            ]
    except Exception as exc:
        logger.warning("消息记录 MySQL 会话列表读取失败：错误类型=%s", type(exc).__name__)
        return []
    finally:
        _关闭连接(连接)


def 聚合聊天列表(上限: int = 200) -> list[dict[str, Any]]:
    """对齐 ElainaBot：单次 GROUP BY 聚合所有会话的最后消息 id/时间与条数。

    等价于 ElainaBot 的 _aggregate_chats_sync（SQLite GROUP BY group_id），
    这里按 会话标识 聚合，返回每个会话的 last_id/last_ts/msg_count 骨架。
    """
    if not _MySQL可用():
        return []
    上限 = max(1, min(上限, 500))
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT 会话标识, MAX(id) AS last_id, MAX(ts) AS last_ts, COUNT(*) AS n "
                f"FROM `{消息记录表名}` WHERE 会话标识 != '' GROUP BY 会话标识 ORDER BY last_ts DESC LIMIT %s",
                (上限,),
            )
            行列表 = 游标.fetchall()
        结果: list[dict[str, Any]] = []
        for 行 in 行列表:
            if isinstance(行, Mapping):
                会话标识 = str(_行字段(行, 0, "会话标识", 默认值="") or "")
                结果.append(
                    {
                        "会话标识": 会话标识,
                        "last_id": int(_行字段(行, 1, "last_id", 默认值=0) or 0),
                        "last_ts": int(_行字段(行, 2, "last_ts", 默认值=0) or 0),
                        "msg_count": int(_行字段(行, 3, "n", "msg_count", 默认值=0) or 0),
                    }
                )
            else:
                结果.append(
                    {
                        "会话标识": str(_行字段(行, 0, "会话标识", 默认值="") or ""),
                        "last_id": int(_行字段(行, 1, "last_id", 默认值=0) or 0),
                        "last_ts": int(_行字段(行, 2, "last_ts", 默认值=0) or 0),
                        "msg_count": int(_行字段(行, 3, "n", "msg_count", 默认值=0) or 0),
                    }
                )
        return 结果
    except Exception as exc:
        logger.warning("消息记录 MySQL 会话聚合失败：错误类型=%s", type(exc).__name__)
        return []
    finally:
        _关闭连接(连接)


def 批量读取最后消息(id列表: list[int]) -> dict[int, dict[str, Any]]:
    """按 id 批量读取消息，返回 {id: 记录}，分块 500 对齐 ElainaBot 的 last_content 补查。"""
    结果: dict[int, dict[str, Any]] = {}
    if not id列表 or not _MySQL可用():
        return 结果
    连接 = _打开连接()
    if 连接 is None:
        return 结果
    try:
        for 起点 in range(0, len(id列表), 500):
            分块 = id列表[起点 : 起点 + 500]
            占位 = ",".join(["%s"] * len(分块))
            with 连接.cursor() as 游标:
                游标.execute(f"SELECT * FROM `{消息记录表名}` WHERE id IN ({占位})", tuple(分块))
                for 行 in 游标.fetchall():
                    记录 = _行转记录(行)
                    结果[int(记录.get("id") or 0)] = 记录
    except Exception as exc:
        logger.warning("消息记录 MySQL 最后消息补查失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)
    return 结果


def 分页读取历史(会话标识: str, before_id: int = 0, 上限: int = 200, before_ts: int = 0) -> list[dict[str, Any]]:
    """按 id 倒序分页读取某会话历史消息，对齐 ElainaBot 的分页查询。

    before_id > 0 时取 id 更小的更早消息；否则按 before_ts（秒级）过滤更早消息。
    """
    if not _MySQL可用():
        return []
    会话标识 = str(会话标识 or "")
    上限 = max(1, min(上限, 2000))
    before_id = max(0, int(before_id or 0))
    before_ts = max(0, int(before_ts or 0))
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            if before_id:
                游标.execute(
                    f"SELECT * FROM `{消息记录表名}` WHERE 会话标识=%s AND id < %s ORDER BY id DESC LIMIT %s",
                    (会话标识, before_id, 上限),
                )
            elif before_ts:
                游标.execute(
                    f"SELECT * FROM `{消息记录表名}` WHERE 会话标识=%s AND ts < %s ORDER BY id DESC LIMIT %s",
                    (会话标识, before_ts, 上限),
                )
            else:
                游标.execute(
                    f"SELECT * FROM `{消息记录表名}` WHERE 会话标识=%s ORDER BY id DESC LIMIT %s",
                    (会话标识, 上限),
                )
            行列表 = 游标.fetchall()
        return [_行转记录(行) for 行 in 行列表]
    except Exception as exc:
        logger.warning("消息记录 MySQL 历史分页读取失败：错误类型=%s", type(exc).__name__)
        return []
    finally:
        _关闭连接(连接)




def 统计会话消息数(会话标识: str) -> int:
    """统计某会话在 MySQL 中的消息总数（用于判断是否还有更早历史）。"""
    if not _MySQL可用():
        return 0
    会话标识 = str(会话标识 or "")
    连接 = _打开连接()
    if 连接 is None:
        return 0
    try:
        with 连接.cursor() as 游标:
            游标.execute(f"SELECT COUNT(*) FROM `{消息记录表名}` WHERE 会话标识=%s", (会话标识,))
            行 = 游标.fetchone()
        return int(_行字段(行, 0, "c", "COUNT(*)", 默认值=0) or 0) if 行 else 0
    except Exception as exc:
        logger.warning("消息记录 MySQL 会话消息数统计失败：错误类型=%s", type(exc).__name__)
        return 0
    finally:
        _关闭连接(连接)


def 裁剪总消息(上限: int) -> None:
    """按 id 顺序删除最旧的超量消息，保持总量不超过上限。"""
    if not _MySQL可用():
        return
    连接 = _打开连接()
    if 连接 is None:
        return
    try:
        with 连接.cursor() as 游标:
            游标.execute(f"SELECT COUNT(*) AS c FROM `{消息记录表名}`")
            总数 = int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0)
            if 总数 > 上限:
                需要删 = 总数 - 上限
                游标.execute(
                    f"DELETE FROM `{消息记录表名}` WHERE id IN (SELECT id FROM (SELECT id FROM `{消息记录表名}` ORDER BY id ASC LIMIT %s) t)",
                    (需要删,),
                )
        连接.commit()
    except Exception as exc:
        logger.warning("消息记录 MySQL 裁剪失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)


def 读取元数据(key: str, 默认值: Any = None) -> Any:
    """读取一条元数据（置顶/备注/昵称等）。"""
    if not _MySQL可用():
        return 默认值
    连接 = _打开连接()
    if 连接 is None:
        return 默认值
    状态表名 = _运行状态表名()
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT state_value FROM `{状态表名}` WHERE namespace=%s AND state_key=%s LIMIT 1",
                (元数据命名空间, str(key)),
            )
            行 = 游标.fetchone()
        if 行:
            return json.loads(str(_行字段(行, 0, "state_value", 默认值="")))
    except Exception as exc:
        logger.warning("消息记录 MySQL 元数据读取失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)
    return 默认值


def 写入元数据(key: str, value: Any) -> bool:
    """写入一条元数据（置顶/备注/昵称等）。"""
    if not _MySQL可用():
        return False
    连接 = _打开连接()
    if 连接 is None:
        return False
    状态表名 = _运行状态表名()
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"INSERT INTO `{状态表名}` (namespace, state_key, state_value, updated_at) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE state_value=VALUES(state_value), updated_at=VALUES(updated_at)",
                (元数据命名空间, str(key), json.dumps(value, ensure_ascii=False), int(time.time())),
            )
        连接.commit()
        return True
    except Exception as exc:
        logger.warning("消息记录 MySQL 元数据写入失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def 读取全部元数据() -> dict[str, Any]:
    if not _MySQL可用():
        return {}
    结果: dict[str, Any] = {}
    连接 = _打开连接()
    if 连接 is None:
        return {}
    状态表名 = _运行状态表名()
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT state_key, state_value FROM `{状态表名}` WHERE namespace=%s",
                (元数据命名空间,),
            )
            for 行 in 游标.fetchall():
                键 = _行字段(行, 0, "state_key", 默认值="")
                值 = _行字段(行, 1, "state_value", 默认值="")
                if 键:
                    try:
                        结果[str(键)] = json.loads(str(值))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        logger.debug("消息记录元数据格式无效：键=%s", str(键)[:80])
    except Exception as exc:
        logger.warning("消息记录 MySQL 元数据批量读取失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)
    return 结果


def _行转记录(行: Any) -> dict[str, Any]:
    """MySQL 行转消息记录；兼容元组游标（默认）与字典游标。列顺序见建表语句。"""
    def 取值(索引: int, 默认值: str = "") -> str:
        字段映射 = {
            0: ("id",),
            1: ("会话标识",),
            2: ("消息类型",),
            3: ("appid",),
            4: ("message_id",),
            5: ("user_id",),
            6: ("nickname",),
            7: ("content",),
            8: ("timestamp",),
            9: ("ts",),
            10: ("is_self",),
            11: ("source",),
            12: ("recalled",),
            13: ("media",),
            14: ("reference_id",),
            15: ("refidx",),
            16: ("raw_message",),
        }
        值 = _行字段(行, 索引, *字段映射.get(索引, ()), 默认值=None)
        return str(值 if 值 is not None else 默认值)

    try:
        媒体 = json.loads(取值(13, "{}"))
    except Exception:
        媒体 = {}
    return {
        "id": int(取值(0, "0") or 0),
        "_session": 取值(1),
        "chat_type": 取值(2, "group") or "group",
        "appid": 取值(3),
        "message_id": 取值(4),
        "user_id": 取值(5),
        "nickname": 取值(6),
        "content": 取值(7),
        "timestamp": 取值(8),
        "ts": int(取值(9, "0") or 0),
        "is_self": str(取值(10, "0") or "0").strip() in ("1", "true", "True"),
        "source": 取值(11),
        "recalled": str(取值(12, "0") or "0").strip() in ("1", "true", "True"),
        "media": 媒体 or None,
        "reference_id": 取值(14),
        "refidx": 取值(15),
        "raw_message": 取值(16),
    }
