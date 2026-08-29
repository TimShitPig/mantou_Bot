# -*- coding: utf-8 -*-
"""消息记录 MySQL 持久化层。

- 消息记录写入 mantou_message_records 表（自动建表，带会话/时间与消息 ID 索引）。
- 群资料写入 mantou_group_infos 表，启动时恢复，避免每次打开控制台都请求官方接口。
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
群信息表名 = "mantou_group_infos"
元数据命名空间 = "message_panel_meta"

_消息写入SQL = (
    f"INSERT INTO `{消息记录表名}` "
    "(会话标识, 消息类型, appid, message_id, user_id, nickname, content, "
    "timestamp, ts, is_self, source, recalled, media, reference_id, refidx, raw_message) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)

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
    """建消息记录、群资料与元数据表；返回是否成功。"""
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
                    KEY idx_msg_records_session_id (会话标识, id),
                    KEY idx_msg_records_message (message_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            游标.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{群信息表名}` (
                    group_openid VARCHAR(128) NOT NULL,
                    appid VARCHAR(64) DEFAULT '',
                    group_name VARCHAR(255) DEFAULT '',
                    group_finger_memo VARCHAR(255) DEFAULT '',
                    group_class_text VARCHAR(255) DEFAULT '',
                    group_tags TEXT,
                    member_num INT DEFAULT 0,
                    is_admin TINYINT DEFAULT 0,
                    updated_at BIGINT DEFAULT 0,
                    PRIMARY KEY (group_openid),
                    KEY idx_group_infos_updated (updated_at)
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
                游标.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'is_admin'",
                    (群信息表名,),
                )
                if int(_行字段(游标.fetchone(), 0, "COUNT(*)", 默认值=0) or 0) == 0:
                    游标.execute(f"ALTER TABLE `{群信息表名}` ADD COLUMN `is_admin` TINYINT DEFAULT 0")
                    logger.info("群信息 MySQL 表已补列 is_admin")
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
                游标.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                    "AND INDEX_NAME = %s",
                    (消息记录表名, "idx_msg_records_session_id"),
                )
                if int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0) == 0:
                    游标.execute(
                        f"ALTER TABLE `{消息记录表名}` "
                        "ADD KEY idx_msg_records_session_id (会话标识, id)"
                    )
                    logger.info("消息记录 MySQL 已补充会话分页索引")
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


def _消息写入参数(记录: dict[str, Any]) -> tuple[Any, ...]:
    return (
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
    )


def _写入消息记录(记录: dict[str, Any]) -> bool:
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            会话标识 = str(记录.get("_session") or "")
            消息ID = str(记录.get("message_id") or "")
            if 消息ID:
                游标.execute(
                    f"SELECT id FROM `{消息记录表名}` WHERE 会话标识=%s AND message_id=%s LIMIT 1",
                    (会话标识, 消息ID),
                )
                if 游标.fetchone():
                    return True
            游标.execute(_消息写入SQL, _消息写入参数(记录))
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


def 批量写入消息(记录列表: list[dict[str, Any]]) -> bool:
    """使用单连接、单事务批量写入消息，供异步持久化队列调用。"""
    有效记录 = [记录 for 记录 in (记录列表 or []) if 记录 and 记录.get("_session")]
    if not 有效记录 or not _MySQL可用():
        return False
    去重记录: list[dict[str, Any]] = []
    已见键: set[tuple[str, str]] = set()
    for 记录 in 有效记录:
        消息ID = str(记录.get("message_id") or "")
        键 = (str(记录.get("_session") or ""), 消息ID)
        if 消息ID and 键 in 已见键:
            continue
        if 消息ID:
            已见键.add(键)
        去重记录.append(记录)
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            待写入: list[tuple[Any, ...]] = []
            for 记录 in 去重记录:
                消息ID = str(记录.get("message_id") or "")
                if 消息ID:
                    游标.execute(
                        f"SELECT id FROM `{消息记录表名}` WHERE 会话标识=%s AND message_id=%s LIMIT 1",
                        (str(记录.get("_session") or ""), 消息ID),
                    )
                    if 游标.fetchone():
                        continue
                待写入.append(_消息写入参数(记录))
            if 待写入:
                游标.executemany(_消息写入SQL, 待写入)
        连接.commit()
        return True
    except Exception as exc:
        try:
            连接.rollback()
        except Exception:
            pass
        logger.warning(
            "消息记录 MySQL 批量写入失败：数量=%d，错误类型=%s",
            len(去重记录),
            type(exc).__name__,
        )
        return False
    finally:
        _关闭连接(连接)


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


def 批量读取最后消息摘要(id列表: list[int]) -> dict[int, dict[str, Any]]:
    """只读取会话列表需要的最后消息字段。

    会话列表只展示昵称、时间和文本预览，不需要完整消息原文和媒体 JSON。
    这里保持与 ``_行转记录`` 相同的列顺序，用原文首尾摘要保留时间字段，
    避免列表请求把历史卡片/原始消息整批从 MySQL 传回 Python。
    """
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
                # 列顺序必须与 _行转记录 保持一致；列表预览截取前 4096 个字符，
                # 原文只保留首尾字段（含 QQ timestamp），完整消息仍由历史接口分页读取。
                游标.execute(
                    f"SELECT id, 会话标识, 消息类型, appid, message_id, user_id, nickname, "
                    f"LEFT(content, 4096) AS content, timestamp, ts, is_self, source, recalled, "
                    f"'' AS media, reference_id, refidx, "
                    f"CONCAT(LEFT(raw_message, 2048), RIGHT(raw_message, 512)) AS raw_message "
                    f"FROM `{消息记录表名}` WHERE id IN ({占位})",
                    tuple(分块),
                )
                for 行 in 游标.fetchall():
                    记录 = _行转记录(行)
                    结果[int(记录.get("id") or 0)] = 记录
    except Exception as exc:
        logger.warning("消息记录 MySQL 最后消息摘要补查失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)
    return 结果


def 分页读取历史(
    会话标识: str,
    before_id: int = 0,
    上限: int = 200,
    before_ts: int = 0,
    返回额外: bool = False,
) -> list[dict[str, Any]]:
    """按 id 倒序分页读取某会话历史消息，对齐 ElainaBot 的分页查询。

    before_id > 0 时取 id 更小的更早消息；否则按 before_ts（秒级）过滤更早消息。
    """
    if not _MySQL可用():
        return []
    会话标识 = str(会话标识 or "")
    上限 = max(1, min(上限, 2000))
    查询上限 = min(2001, 上限 + (1 if 返回额外 else 0))
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
                    (会话标识, before_id, 查询上限),
                )
            elif before_ts:
                游标.execute(
                    f"SELECT * FROM `{消息记录表名}` WHERE 会话标识=%s AND ts < %s ORDER BY id DESC LIMIT %s",
                    (会话标识, before_ts, 查询上限),
                )
            else:
                游标.execute(
                    f"SELECT * FROM `{消息记录表名}` WHERE 会话标识=%s ORDER BY id DESC LIMIT %s",
                    (会话标识, 查询上限),
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


def 写入群信息(信息: dict[str, Any], appid: str = "") -> bool:
    """持久化一份 QQ 官方群资料；只保存公开群资料，不保存消息或凭据。"""
    if not _MySQL可用() or not isinstance(信息, dict):
        return False
    群OpenID = _按列宽截断(信息.get("group_openid") or "", "会话标识")
    if not 群OpenID:
        return False
    try:
        成员数 = max(0, int(信息.get("member_num") or 信息.get("group_member_num") or 0))
    except (TypeError, ValueError):
        成员数 = 0
    标签 = 信息.get("group_tags")
    if not isinstance(标签, (list, tuple)):
        标签 = [] if 标签 in (None, "") else [标签]
    标签 = [str(值).strip() for 值 in 标签 if str(值 or "").strip()]
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                INSERT INTO `{群信息表名}` (
                    group_openid, appid, group_name, group_finger_memo,
                    group_class_text, group_tags, member_num, is_admin, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    appid=VALUES(appid),
                    group_name=VALUES(group_name),
                    group_finger_memo=VALUES(group_finger_memo),
                    group_class_text=VALUES(group_class_text),
                    group_tags=VALUES(group_tags),
                    member_num=VALUES(member_num),
                    is_admin=VALUES(is_admin),
                    updated_at=VALUES(updated_at)
                """,
                (
                    群OpenID,
                    _按列宽截断(appid, "appid"),
                    str(信息.get("group_name") or "")[:255],
                    str(信息.get("group_finger_memo") or "")[:255],
                    str(信息.get("group_class_text") or "")[:255],
                    json.dumps(标签, ensure_ascii=False),
                    成员数,
                    1 if bool(信息.get("is_admin")) else 0,
                    int(信息.get("updated_at") or time.time()),
                ),
            )
        连接.commit()
        return True
    except Exception as exc:
        logger.warning("消息记录 MySQL 群资料写入失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def 读取全部群信息() -> list[dict[str, Any]]:
    """读取持久化群资料，供插件启动时恢复内存缓存。"""
    if not _MySQL可用():
        return []
    连接 = _打开连接()
    if 连接 is None:
        return []
    结果: list[dict[str, Any]] = []
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"""
                SELECT group_openid, appid, group_name, group_finger_memo,
                       group_class_text, group_tags, member_num, is_admin, updated_at
                FROM `{群信息表名}`
                """
            )
            for 行 in 游标.fetchall():
                群OpenID = str(_行字段(行, 0, "group_openid", 默认值="") or "").strip()
                if not 群OpenID:
                    continue
                标签原值 = _行字段(行, 5, "group_tags", 默认值="[]")
                try:
                    标签 = json.loads(str(标签原值 or "[]"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    标签 = []
                if not isinstance(标签, list):
                    标签 = [str(标签)] if 标签 else []
                try:
                    成员数 = max(0, int(_行字段(行, 6, "member_num", 默认值=0) or 0))
                except (TypeError, ValueError):
                    成员数 = 0
                try:
                    更新时间 = int(_行字段(行, 8, "updated_at", 默认值=0) or 0)
                except (TypeError, ValueError):
                    更新时间 = 0
                结果.append(
                    {
                        "group_openid": 群OpenID,
                        "appid": str(_行字段(行, 1, "appid", 默认值="") or ""),
                        "group_name": str(_行字段(行, 2, "group_name", 默认值="") or ""),
                        "group_finger_memo": str(_行字段(行, 3, "group_finger_memo", 默认值="") or ""),
                        "group_class_text": str(_行字段(行, 4, "group_class_text", 默认值="") or ""),
                        "group_tags": [str(值) for 值 in 标签 if str(值 or "").strip()],
                        "member_num": 成员数,
                        "is_admin": bool(int(_行字段(行, 7, "is_admin", 默认值=0) or 0) == 1),
                        "updated_at": 更新时间,
                    }
                )
        return 结果
    except Exception as exc:
        logger.warning("消息记录 MySQL 群资料读取失败：错误类型=%s", type(exc).__name__)
        return []
    finally:
        _关闭连接(连接)


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
