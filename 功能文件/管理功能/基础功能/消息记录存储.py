# -*- coding: utf-8 -*-
"""消息记录 MySQL 持久化层。

- 消息记录写入 mantou_message_records 表（自动建表，带会话/时间与消息 ID 索引）。
- 置顶/备注/昵称等元数据写入现有 mantou_runtime_state 表（namespace 隔离）。
- 依赖插件 database_settings 配置；未配置时接口直接返回默认值/空，
  不尝试连接数据库、不刷告警（与运行状态数据库一致）。
"""
from __future__ import annotations

import json
import time
from typing import Any

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

消息记录表名 = "mantou_message_records"
元数据命名空间 = "message_panel_meta"

_数据库配置引用: dict[str, Any] = {}


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
                """
                CREATE TABLE IF NOT EXISTS mantou_runtime_state (
                    namespace VARCHAR(64) NOT NULL,
                    state_key VARCHAR(128) NOT NULL,
                    state_value TEXT NOT NULL,
                    updated_at BIGINT NOT NULL,
                    PRIMARY KEY (namespace, state_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        # 表结构自修复：旧表可能为 utf8（无法存 emoji）或缺新列，转为 utf8mb4 并补齐
        try:
            游标.execute(f"SELECT CHARACTER_SET_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{消息记录表名}' AND COLUMN_NAME = 'content'")
            行 = 游标.fetchone()
            if 行 and str(行[0] or "").lower() != "utf8mb4":
                游标.execute(f"ALTER TABLE `{消息记录表名}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                连接.commit()
                logger.warning("消息记录 MySQL 表已转为 utf8mb4")
            for 列名, 定义 in (("refidx", "VARCHAR(128) DEFAULT ''"), ("recalled", "TINYINT DEFAULT 0"), ("reference_id", "VARCHAR(128) DEFAULT ''"), ("media", "TEXT"), ("source", "VARCHAR(32) DEFAULT ''")):
                游标.execute(f"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{消息记录表名}' AND COLUMN_NAME = '{列名}'")
                if int(游标.fetchone()[0] or 0) == 0:
                    游标.execute(f"ALTER TABLE `{消息记录表名}` ADD COLUMN `{列名}` {定义}")
                    连接.commit()
                    logger.warning("消息记录 MySQL 表已补列 %s", 列名)
        except Exception as 修复异常:
            logger.debug("消息记录 MySQL 表结构检查跳过：错误类型=%s", type(修复异常).__name__)
        连接.commit()
        return True
    except Exception as exc:
        logger.warning("消息记录 MySQL 建表失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def _写入消息记录(记录: dict[str, Any]) -> None:
    连接 = _打开连接()
    if 连接 is None:
        return
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"INSERT INTO `{消息记录表名}` (会话标识, 消息类型, appid, message_id, user_id, nickname, content, timestamp, ts, is_self, source, recalled, media, reference_id, refidx, raw_message) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    str(记录.get("_session") or ""),
                    str(记录.get("chat_type") or "group"),
                    str(记录.get("appid") or ""),
                    str(记录.get("message_id") or ""),
                    str(记录.get("user_id") or ""),
                    str(记录.get("nickname") or ""),
                    str(记录.get("content") or ""),
                    str(记录.get("timestamp") or ""),
                    int(记录.get("ts") or 0),
                    1 if 记录.get("is_self") else 0,
                    str(记录.get("source") or ""),
                    1 if 记录.get("recalled") else 0,
                    json.dumps(记录.get("media") or {}, ensure_ascii=False),
                    str(记录.get("reference_id") or ""),
                    str(记录.get("refidx") or ""),
                    str(记录.get("raw_message") or ""),
                ),
            )
        连接.commit()
    except Exception as exc:
        logger.warning(
            "消息记录 MySQL 写入失败：错误类型=%s，详情=%s",
            type(exc).__name__,
            str(exc)[:300],
        )
    finally:
        _关闭连接(连接)


def 写入消息(记录: dict[str, Any]) -> None:
    """写入一条消息记录；MySQL 不可用时静默跳过。"""
    if not 记录 or not 记录.get("_session"):
        return
    if not _MySQL可用():
        return
    _写入消息记录(记录)


def 标记消息撤回(会话标识: str, message_id: str) -> None:
    会话标识 = str(会话标识 or "")
    message_id = str(message_id or "")
    if not message_id or not _MySQL可用():
        return
    连接 = _打开连接()
    if 连接 is None:
        return
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"UPDATE `{消息记录表名}` SET recalled=1 WHERE 会话标识=%s AND message_id=%s",
                (会话标识, message_id),
            )
        连接.commit()
    except Exception as exc:
        logger.warning("消息记录 MySQL 撤回标记失败：错误类型=%s", type(exc).__name__)
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
            return [str(行[0]) for 行 in 游标.fetchall() if 行 and 行[0]]
    except Exception as exc:
        logger.warning("消息记录 MySQL 会话列表读取失败：错误类型=%s", type(exc).__name__)
        return []
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
            总数 = int(游标.fetchone()[0])
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
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                "SELECT state_value FROM mantou_runtime_state WHERE namespace=%s AND state_key=%s LIMIT 1",
                (元数据命名空间, str(key)),
            )
            行 = 游标.fetchone()
        if 行:
            return json.loads(str(行[0]))
    except Exception as exc:
        logger.warning("消息记录 MySQL 元数据读取失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)
    return 默认值


def 写入元数据(key: str, value: Any) -> None:
    """写入一条元数据（置顶/备注/昵称等）。"""
    if not _MySQL可用():
        return
    连接 = _打开连接()
    if 连接 is None:
        return
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                "INSERT INTO mantou_runtime_state (namespace, state_key, state_value, updated_at) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE state_value=VALUES(state_value), updated_at=VALUES(updated_at)",
                (元数据命名空间, str(key), json.dumps(value, ensure_ascii=False), int(time.time())),
            )
        连接.commit()
    except Exception as exc:
        logger.warning("消息记录 MySQL 元数据写入失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)


def 读取全部元数据() -> dict[str, Any]:
    if not _MySQL可用():
        return {}
    结果: dict[str, Any] = {}
    连接 = _打开连接()
    if 连接 is None:
        return {}
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                "SELECT state_key, state_value FROM mantou_runtime_state WHERE namespace=%s",
                (元数据命名空间,),
            )
            for 行 in 游标.fetchall():
                结果[str(行[0])] = json.loads(str(行[1]))
    except Exception as exc:
        logger.warning("消息记录 MySQL 元数据批量读取失败：错误类型=%s", type(exc).__name__)
    finally:
        _关闭连接(连接)
    return 结果


def _行转记录(行: Any) -> dict[str, Any]:
    """MySQL 行转消息记录；兼容元组游标（默认）与字典游标。列顺序见建表语句。"""
    def 取值(索引: int, 默认值: str = "") -> str:
        if isinstance(行, dict):
            return str(行.get(索引) if 行.get(索引) is not None else 默认值)
        return str(行[索引] if 索引 < len(行) and 行[索引] is not None else 默认值)

    try:
        媒体 = json.loads(取值(13, "{}"))
    except Exception:
        媒体 = {}
    return {
        "id": int(取值(0, "0") or 0),
        "message_id": 取值(4),
        "user_id": 取值(5),
        "_session": 取值(1),
        "appid": 取值(3),
        "nickname": 取值(6),
        "content": 取值(7),
        "timestamp": 取值(8),
        "ts": int(取值(9, "0") or 0),
        "is_self": bool(取值(10, "0")),
        "source": 取值(11),
        "recalled": bool(取值(12, "0")),
        "media": 媒体 or None,
        "reference_id": 取值(14),
        "refidx": 取值(15),
        "raw_message": 取值(16),
    }
