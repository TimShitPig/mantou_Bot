# -*- coding: utf-8 -*-
"""消息记录 MySQL 持久化层。

- 消息记录写入 mantou_message_records 表；用户昵称写入 mantou_message_user_profiles 表。
- 群资料写入 mantou_group_infos 表，启动时恢复，避免每次打开控制台都请求官方接口。
- 置顶/备注/昵称等元数据写入现有 mantou_runtime_state 表（namespace 隔离）。
- 依赖插件 database_settings 配置；未配置时接口直接返回默认值/空，
  不尝试连接数据库、不刷告警（与运行状态数据库一致）。
"""
from __future__ import annotations

import hashlib
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
会话索引表名 = "mantou_message_conversations"
会话索引状态表名 = "mantou_message_conversation_state"
群信息表名 = "mantou_group_infos"
用户资料表名 = "mantou_message_user_profiles"
群成员映射表名 = "mantou_message_member_links"
元数据命名空间 = "message_panel_meta"
会话索引就绪键 = "conversation_summary_v1"
群成员映射回填键 = "group_member_links_v1"
统一用户资料回填键 = "user_profile_union_openid_v1"

_消息写入SQL = (
    f"INSERT INTO `{消息记录表名}` "
    "(会话标识, 消息类型, appid, message_id, user_id, nickname, content, "
    "timestamp, ts, is_self, source, recalled, media, reference_id, refidx, avatar, raw_message, member_role, msg_seq) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
_消息更新SQL = (
    f"UPDATE `{消息记录表名}` SET 消息类型=%s, appid=%s, user_id=%s, nickname=%s, content=%s, "
    "timestamp=%s, ts=%s, is_self=%s, source=%s, recalled=%s, media=%s, reference_id=%s, "
    "refidx=%s, avatar=%s, raw_message=%s, member_role=%s, msg_seq=%s WHERE 会话标识=%s AND message_id=%s"
)
_消息查重分块大小 = 200

# 历史页只需要截断后的原始消息用于时间/提及解析和原始数据预览。
# 显式列出字段避免 SELECT * 搬运未来新增列；正文与媒体字段保持完整。
_历史查询字段SQL = (
    "id, 会话标识, 消息类型, appid, message_id, user_id, nickname, content, "
    "timestamp, ts, is_self, source, recalled, media, reference_id, refidx, "
    "avatar, LEFT(raw_message, 4096) AS raw_message, member_role, msg_seq"
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
    "avatar": 1024,
    "member_role": 16,
    "msg_seq": 64,
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


def _原始消息统一用户标识表达式(别名: str) -> str:
    路径列表 = (
        "$.author.union_openid",
        "$.union_openid",
        "$.member.union_openid",
        "$.data.union_openid",
        "$.data.author.union_openid",
        "$.d.union_openid",
        "$.d.author.union_openid",
        "$.raw_data.union_openid",
        "$.raw_data.author.union_openid",
    )
    候选项 = ",".join(
        "NULLIF(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(" + f"{别名}.raw_message, '{路径}'" + ")),''),'null')"
        for 路径 in 路径列表
    )
    return (
        f"CASE WHEN JSON_VALID({别名}.raw_message) "
        f"THEN COALESCE({候选项},'') ELSE '' END"
    )


def _原始消息昵称表达式(别名: str, 用户字段: str) -> str:
    路径列表 = (
        "$.author.username",
        "$.author.member_name",
        "$.author.nickname",
        "$.author.user_name",
        "$.author.name",
        "$.member.username",
        "$.member.nick",
        "$.member.nickname",
        "$.member.member_name",
        "$.username",
        "$.member_name",
        "$.nickname",
        "$.data.author.username",
        "$.data.author.member_name",
        "$.data.author.nickname",
        "$.d.author.username",
        "$.d.author.member_name",
        "$.d.author.nickname",
        "$.raw_data.author.username",
        "$.raw_data.author.member_name",
        "$.raw_data.author.nickname",
    )
    原始候选 = ",".join(
        "NULLIF(NULLIF(JSON_UNQUOTE(JSON_EXTRACT("
        + f"{别名}.raw_message, '{路径}'"
        + ")),''),'null')"
        for 路径 in 路径列表
    )
    return (
        f"CASE WHEN JSON_VALID({别名}.raw_message) THEN "
        f"COALESCE({原始候选},NULLIF({别名}.nickname,''),'') "
        f"ELSE COALESCE(NULLIF({别名}.nickname,''),'') END"
    )


def _MySQL错误摘要(异常: Exception) -> str:
    """生成不包含连接配置的 MySQL 诊断信息。"""
    参数 = getattr(异常, "args", ())
    错误码 = getattr(异常, "errno", None)
    if 错误码 is None and 参数 and isinstance(参数[0], int):
        错误码 = 参数[0]
    SQL状态 = getattr(异常, "sqlstate", None) or getattr(异常, "sql_state", None)
    详情值 = getattr(异常, "msg", None)
    if not 详情值 and len(参数) > 1:
        详情值 = 参数[1]
    if not 详情值:
        详情值 = str(异常)
    详情 = re.sub(r"\s+", " ", str(详情值)).strip()
    详情 = re.sub(
        r"(?i)\b(password|passwd|token|cookie|secret|key)\b\s*([=:])\s*[^\s,;]+",
        r"\1\2<redacted>",
        详情,
    )
    详情 = re.sub(r"(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?!\w)", "<ip>", 详情)
    详情 = re.sub(r"https?://\S+", "<url>", 详情)
    return (
        f"错误码={错误码 if 错误码 is not None else 'none'}, "
        f"SQLSTATE={SQL状态 or 'none'}, 错误详情={详情[:240] or 'none'}"
    )


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
    初始化阶段 = "建消息记录表"
    try:
        with 连接.cursor() as 游标:
            初始化阶段 = "建消息记录表"
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
                    avatar VARCHAR(1024) DEFAULT '',
                    raw_message MEDIUMTEXT,
                    member_role VARCHAR(16) DEFAULT '',
                    msg_seq VARCHAR(64) DEFAULT '',
                    PRIMARY KEY (id),
                    KEY idx_msg_records_session (会话标识, ts),
                    KEY idx_msg_records_session_id (会话标识, id),
                    KEY idx_msg_records_member_time (会话标识(64), user_id(64), ts, id),
                    KEY idx_msg_records_session_message (会话标识(64), message_id(64)),
                    KEY idx_msg_records_message (message_id),
                    KEY idx_msg_records_user_id (user_id(64), 消息类型, is_self, id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            初始化阶段 = "建用户资料表"
            游标.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{用户资料表名}` (
                    profile_key CHAR(64) NOT NULL,
                    appid VARCHAR(64) NOT NULL DEFAULT '',
                    user_id VARCHAR(128) NOT NULL,
                    nickname VARCHAR(255) NOT NULL DEFAULT '',
                    union_openid VARCHAR(128) NOT NULL DEFAULT '',
                    updated_at BIGINT NOT NULL DEFAULT 0,
                    PRIMARY KEY (profile_key),
                    KEY idx_user_profiles_lookup (appid(32), user_id(64)),
                    KEY idx_user_profiles_user (user_id(64), updated_at),
                    KEY idx_user_profiles_union (union_openid(64), updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            初始化阶段 = "检查用户资料统一OpenID字段"
            游标.execute(
                "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='union_openid'",
                (用户资料表名,),
            )
            if int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0) == 0:
                游标.execute(
                    f"ALTER TABLE `{用户资料表名}` "
                    "ADD COLUMN union_openid VARCHAR(128) NOT NULL DEFAULT ''"
                )
            初始化阶段 = "检查索引_idx_user_profiles_union"
            游标.execute(
                "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s",
                (用户资料表名, "idx_user_profiles_union"),
            )
            if int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0) == 0:
                游标.execute(
                    f"ALTER TABLE `{用户资料表名}` "
                    "ADD KEY idx_user_profiles_union (union_openid(64), updated_at)"
                )
            初始化阶段 = "建群成员映射表"
            游标.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{群成员映射表名}` (
                    mapping_key CHAR(64) NOT NULL,
                    appid VARCHAR(64) NOT NULL DEFAULT '',
                    group_openid VARCHAR(128) NOT NULL,
                    user_openid VARCHAR(128) NOT NULL,
                    member_openid VARCHAR(128) NOT NULL,
                    updated_at BIGINT NOT NULL DEFAULT 0,
                    PRIMARY KEY (mapping_key),
                    KEY idx_member_links_user (appid(32), user_openid(64), updated_at),
                    KEY idx_member_links_group_user (group_openid(64), user_openid(64)),
                    KEY idx_member_links_user_openid (user_openid(64), appid(32), updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            初始化阶段 = "检查群成员映射字段_mapping_key"
            游标.execute(
                "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='mapping_key'",
                (群成员映射表名,),
            )
            映射键字段 = 游标.fetchone()
            if 映射键字段 is None:
                游标.execute(
                    f"ALTER TABLE `{群成员映射表名}` ADD COLUMN mapping_key CHAR(64) NULL"
                )
            if 映射键字段 is None or str(
                _行字段(映射键字段, 0, "IS_NULLABLE", 默认值="") or ""
            ).upper() == "YES":
                初始化阶段 = "回填群成员映射字段_mapping_key"
                游标.execute(
                    f"UPDATE `{群成员映射表名}` SET mapping_key=SHA2(CONCAT("
                    "COALESCE(appid,''),CHAR(31),group_openid,CHAR(31),member_openid),256) "
                    "WHERE mapping_key IS NULL OR mapping_key=''"
                )
                游标.execute(
                    f"ALTER TABLE `{群成员映射表名}` MODIFY COLUMN mapping_key CHAR(64) NOT NULL"
                )
            初始化阶段 = "建会话摘要表"
            游标.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{会话索引表名}` (
                    chat_type VARCHAR(16) NOT NULL,
                    conversation_id VARCHAR(128) NOT NULL,
                    last_id BIGINT NOT NULL DEFAULT 0,
                    last_ts BIGINT NOT NULL DEFAULT 0,
                    message_count BIGINT NOT NULL DEFAULT 0,
                    PRIMARY KEY (chat_type, conversation_id),
                    KEY idx_message_conversations_recent (chat_type, last_ts, last_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            初始化阶段 = "建会话摘要状态表"
            游标.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{会话索引状态表名}` (
                    state_key VARCHAR(64) NOT NULL,
                    state_value VARCHAR(32) NOT NULL DEFAULT '',
                    PRIMARY KEY (state_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            初始化阶段 = "建群资料表"
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
            初始化阶段 = "建运行状态表"
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
                初始化阶段 = "检查消息表字符集"
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
                    ("avatar", "VARCHAR(1024) DEFAULT ''"),
                    ("member_role", "VARCHAR(16) DEFAULT ''"),
                    ("msg_seq", "VARCHAR(64) DEFAULT ''"),
                ):
                    初始化阶段 = f"检查消息字段_{列名}"
                    游标.execute(
                        "SELECT COUNT(*) FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                        (消息记录表名, 列名),
                    )
                    if int(_行字段(游标.fetchone(), 0, "COUNT(*)", 默认值=0) or 0) == 0:
                        游标.execute(f"ALTER TABLE `{消息记录表名}` ADD COLUMN `{列名}` {定义}")
                        logger.warning("消息记录 MySQL 表已补列 %s", 列名)
                初始化阶段 = "检查群资料字段_is_admin"
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
                    初始化阶段 = f"检查长字段_{列名}"
                    游标.execute(
                        "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                        (消息记录表名, 列名),
                    )
                    数据类型 = str(_行字段(游标.fetchone(), 0, "DATA_TYPE", 默认值="") or "").lower()
                    if 数据类型 and 数据类型 not in {"mediumtext", "longtext"}:
                        游标.execute(f"ALTER TABLE `{消息记录表名}` MODIFY COLUMN `{列名}` MEDIUMTEXT")
                        logger.warning("消息记录 MySQL 长字段已扩容：列=%s", 列名)
                初始化阶段 = "检查索引_idx_msg_records_session_id"
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
                初始化阶段 = "检查索引_idx_msg_records_session_message"
                游标.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                    "AND INDEX_NAME = %s",
                    (消息记录表名, "idx_msg_records_session_message"),
                )
                if int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0) == 0:
                    游标.execute(
                        f"ALTER TABLE `{消息记录表名}` "
                        "ADD KEY idx_msg_records_session_message (会话标识(64), message_id(64))"
                    )
                    logger.info("消息记录 MySQL 已补充会话消息去重索引")
                初始化阶段 = "检查索引_idx_msg_records_member_time"
                游标.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
                    (消息记录表名, "idx_msg_records_member_time"),
                )
                if int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0) == 0:
                    游标.execute(
                        f"ALTER TABLE `{消息记录表名}` "
                        "ADD KEY idx_msg_records_member_time (会话标识(64), user_id(64), ts, id)"
                    )
                    logger.info("消息记录 MySQL 已补充群成员历史索引")
                初始化阶段 = "检查索引_idx_msg_records_user_id"
                游标.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
                    (消息记录表名, "idx_msg_records_user_id"),
                )
                if int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0) == 0:
                    游标.execute(
                        f"ALTER TABLE `{消息记录表名}` "
                        "ADD KEY idx_msg_records_user_id (user_id(64), 消息类型, is_self, id)"
                    )
                    logger.info("消息记录 MySQL 已补充用户 OpenID 查询索引")
                初始化阶段 = "检查索引_idx_member_links_user_openid"
                游标.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
                    (群成员映射表名, "idx_member_links_user_openid"),
                )
                if int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0) == 0:
                    游标.execute(
                        f"ALTER TABLE `{群成员映射表名}` "
                        "ADD KEY idx_member_links_user_openid (user_openid(64), appid(32), updated_at)"
                    )
                    logger.info("消息记录 MySQL 已补充群成员映射反查索引")
                初始化阶段 = "读取群成员映射回填状态"
                游标.execute(
                    f"SELECT state_value FROM `{会话索引状态表名}` WHERE state_key=%s LIMIT 1",
                    (群成员映射回填键,),
                )
                映射回填状态 = 游标.fetchone()
                if str(_行字段(映射回填状态, 0, "state_value", 默认值="") or "") != "ready":
                    初始化阶段 = "回填群成员 OpenID 映射"
                    用户OpenID表达式 = "COALESCE(" + ",".join(
                        "NULLIF(JSON_UNQUOTE(JSON_EXTRACT(raw_message, '%s')), '')" % 路径
                        for 路径 in (
                            "$.author.user_openid",
                            "$.user_openid",
                            "$.raw_data.user_openid",
                            "$.raw_data.author.user_openid",
                            "$.data.author.user_openid",
                            "$.d.author.user_openid",
                        )
                    ) + ")"
                    成员OpenID表达式 = "COALESCE(" + ",".join(
                        "NULLIF(JSON_UNQUOTE(JSON_EXTRACT(raw_message, '%s')), '')" % 路径
                        for 路径 in (
                            "$.author.member_openid",
                            "$.member_openid",
                            "$.raw_data.member_openid",
                            "$.raw_data.author.member_openid",
                            "$.data.author.member_openid",
                            "$.d.author.member_openid",
                        )
                    ) + ")"
                    映射键表达式 = (
                        "SHA2(CONCAT(COALESCE(appid,''),CHAR(31),会话标识,CHAR(31),"
                        f"{成员OpenID表达式}),256)"
                    )
                    游标.execute(
                        f"INSERT INTO `{群成员映射表名}` "
                        "(mapping_key, appid, group_openid, user_openid, member_openid, updated_at) "
                        f"SELECT {映射键表达式}, COALESCE(appid,''), 会话标识, {用户OpenID表达式}, {成员OpenID表达式}, COALESCE(MAX(ts),0) "
                        f"FROM `{消息记录表名}` "
                        "WHERE 消息类型='group' AND source IN ('group_member_join','group_member_leave') "
                        "AND message_id LIKE 'group-event:%' AND 会话标识<>'' AND JSON_VALID(raw_message) "
                        f"AND {用户OpenID表达式} IS NOT NULL AND {成员OpenID表达式} IS NOT NULL "
                        f"GROUP BY COALESCE(appid,''), 会话标识, {用户OpenID表达式}, {成员OpenID表达式} "
                        "ON DUPLICATE KEY UPDATE "
                        "user_openid=IF(VALUES(updated_at)>=updated_at,VALUES(user_openid),user_openid), "
                        "updated_at=GREATEST(updated_at,VALUES(updated_at))"
                    )
                    游标.execute(
                        f"INSERT INTO `{会话索引状态表名}` (state_key,state_value) VALUES (%s,%s) "
                        "ON DUPLICATE KEY UPDATE state_value=VALUES(state_value)",
                        (群成员映射回填键, "ready"),
                    )
                    logger.info("消息记录 MySQL 群成员 ID 映射历史回填完成")
                初始化阶段 = "读取会话摘要初始化状态"
                游标.execute(
                    f"SELECT state_value FROM `{会话索引状态表名}` WHERE state_key=%s LIMIT 1",
                    (会话索引就绪键,),
                )
                状态行 = 游标.fetchone()
                if str(_行字段(状态行, 0, "state_value", 默认值="") or "") != "ready":
                    初始化阶段 = "回填会话摘要"
                    游标.execute(
                        f"""
                        INSERT INTO `{会话索引表名}`
                            (chat_type, conversation_id, last_id, last_ts, message_count)
                        SELECT 汇总.chat_type, 汇总.会话标识, 汇总.last_id, 最后消息.ts, 汇总.message_count
                        FROM (
                            SELECT COALESCE(消息类型, 'group') AS chat_type, 会话标识,
                                MAX(id) AS last_id, COUNT(*) AS message_count
                            FROM `{消息记录表名}`
                            WHERE 会话标识 != ''
                            GROUP BY COALESCE(消息类型, 'group'), 会话标识
                        ) 汇总
                        JOIN `{消息记录表名}` 最后消息 ON 最后消息.id = 汇总.last_id
                        ON DUPLICATE KEY UPDATE
                            last_ts=IF(VALUES(last_id)>=last_id, VALUES(last_ts), last_ts),
                            last_id=GREATEST(last_id, VALUES(last_id)),
                            message_count=GREATEST(message_count, VALUES(message_count))
                        """
                    )
                    初始化阶段 = "标记会话摘要就绪"
                    游标.execute(
                        f"INSERT INTO `{会话索引状态表名}` (state_key, state_value) VALUES (%s, %s) "
                        "ON DUPLICATE KEY UPDATE state_value=VALUES(state_value)",
                        (会话索引就绪键, "ready"),
                    )
                    logger.info("消息记录 MySQL 会话索引已初始化")
            except Exception as 修复异常:
                logger.warning(
                    "消息记录 MySQL 结构/会话索引初始化失败：阶段=%s，错误类型=%s，%s",
                    初始化阶段,
                    type(修复异常).__name__,
                    _MySQL错误摘要(修复异常),
                )
        初始化阶段 = "提交初始化事务"
        连接.commit()
        return True
    except Exception as exc:
        logger.warning(
            "消息记录 MySQL 建表失败：阶段=%s，错误类型=%s，%s",
            初始化阶段,
            type(exc).__name__,
            _MySQL错误摘要(exc),
        )
        return False
    finally:
        _关闭连接(连接)


def 回填历史用户资料批次(批次大小: int = 300) -> tuple[int, bool]:
    """断点续跑地补充历史消息里的 union_openid 与群昵称。"""
    if not _MySQL可用():
        return 0, True
    try:
        批次大小 = max(50, min(1000, int(批次大小)))
    except (TypeError, ValueError):
        批次大小 = 300
    连接 = _打开连接()
    if 连接 is None:
        return 0, False
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT state_value FROM `{会话索引状态表名}` WHERE state_key=%s LIMIT 1",
                (统一用户资料回填键,),
            )
            状态值 = str(_行字段(游标.fetchone(), 0, "state_value", 默认值="") or "")
            if 状态值 == "ready":
                return 0, True
            游标.execute(
                f"SELECT state_value FROM `{会话索引状态表名}` WHERE state_key=%s LIMIT 1",
                (统一用户资料回填键 + "_cursor",),
            )
            游标状态 = str(_行字段(游标.fetchone(), 0, "state_value", 默认值="") or "")
            try:
                游标位置 = max(0, int(游标状态))
            except (TypeError, ValueError):
                游标位置 = 0
            UnionOpenID表达式 = _原始消息统一用户标识表达式("m")
            原始昵称表达式 = _原始消息昵称表达式("m", "m.user_id")
            游标.execute(
                f"SELECT m.id,m.appid,m.user_id,m.nickname,m.ts,"
                f"{UnionOpenID表达式} AS union_openid,{原始昵称表达式} AS raw_nickname "
                f"FROM `{消息记录表名}` m "
                "WHERE m.id>%s AND m.消息类型 IN ('group','user') AND m.is_self=0 "
                "AND m.user_id<>'' AND JSON_VALID(m.raw_message) "
                f"AND {UnionOpenID表达式}<>'' ORDER BY m.id ASC LIMIT %s",
                (游标位置, 批次大小),
            )
            行列表 = list(游标.fetchall() or ())
            if not 行列表:
                游标.execute(
                    f"INSERT INTO `{会话索引状态表名}` (state_key,state_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE state_value=VALUES(state_value)",
                    (统一用户资料回填键, "ready"),
                )
                连接.commit()
                return 0, True

            待写资料: list[tuple[Any, ...]] = []
            for 行 in 行列表:
                记录ID = int(_行字段(行, 0, "id", 默认值=0) or 0)
                appid = str(_行字段(行, 1, "appid", 默认值="") or "").strip()[:64]
                用户标识 = str(_行字段(行, 2, "user_id", 默认值="") or "").strip()[:128]
                if not 记录ID or not 用户标识:
                    continue
                昵称 = _有效用户昵称(用户标识, _行字段(行, 6, "raw_nickname", 默认值=""))
                if not 昵称:
                    昵称 = _有效用户昵称(用户标识, _行字段(行, 3, "nickname", 默认值=""))
                统一用户标识 = str(_行字段(行, 5, "union_openid", 默认值="") or "").strip()[:128]
                if not 统一用户标识:
                    continue
                profile_key = hashlib.sha256(
                    f"{appid}\0{用户标识}".encode("utf-8", errors="ignore")
                ).hexdigest()
                待写资料.append((
                    profile_key,
                    appid,
                    用户标识,
                    昵称[:255],
                    统一用户标识,
                    int(_行字段(行, 4, "ts", 默认值=0) or 0),
                ))
            if 待写资料:
                游标.executemany(
                    f"INSERT INTO `{用户资料表名}` "
                    "(profile_key,appid,user_id,nickname,union_openid,updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                    "nickname=IF(VALUES(nickname)<>'',VALUES(nickname),nickname), "
                    "union_openid=IF(VALUES(union_openid)<>'',VALUES(union_openid),union_openid), "
                    "updated_at=GREATEST(updated_at,VALUES(updated_at))",
                    待写资料,
                )
            最后ID = int(_行字段(行列表[-1], 0, "id", 默认值=游标位置) or 游标位置)
            游标.execute(
                f"INSERT INTO `{会话索引状态表名}` (state_key,state_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE state_value=VALUES(state_value)",
                (统一用户资料回填键 + "_cursor", str(最后ID)),
            )
        连接.commit()
        return len(行列表), False
    except Exception as exc:
        try:
            连接.rollback()
        except Exception:
            pass
        logger.warning(
            "消息记录 MySQL 历史用户资料分批回填失败：错误类型=%s，%s",
            type(exc).__name__,
            _MySQL错误摘要(exc),
        )
        return 0, False
    finally:
        _关闭连接(连接)


def _按列宽截断(值: Any, 列名: str) -> str:
    文本 = str(值 if 值 is not None else "")
    上限 = _列最大长度.get(列名)
    if 上限 and len(文本) > 上限:
        return 文本[:上限]
    return 文本


def _规范消息ID(值: Any) -> str:
    """统一历史消息 ID，避免旧记录空白导致重复落库。"""
    return (
        str(值 or "")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
        .strip()
    )


def _消息写入参数(记录: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _按列宽截断(记录.get("_session") or "", "会话标识"),
        _按列宽截断(记录.get("chat_type") or "group", "消息类型"),
        _按列宽截断(记录.get("appid") or "", "appid"),
        _按列宽截断(_规范消息ID(记录.get("message_id")), "message_id"),
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
        _按列宽截断(记录.get("avatar") or "", "avatar"),
        str(记录.get("raw_message") or ""),
        _按列宽截断(记录.get("member_role") or "", "member_role"),
        _按列宽截断(记录.get("msg_seq") or "", "msg_seq"),
    )


def _消息更新参数(记录: dict[str, Any]) -> tuple[Any, ...]:
    值 = _消息写入参数(记录)
    return (*值[1:3], *值[4:], 值[0], 值[3])


def _消息记录去重键(记录: dict[str, Any]) -> tuple[str, str]:
    """返回与实际入库列宽一致的会话/消息 ID 去重键。"""
    return (
        _按列宽截断(记录.get("_session") or "", "会话标识"),
        _按列宽截断(_规范消息ID(记录.get("message_id")), "message_id"),
    )


def _写入会话索引(
    游标: Any, 会话标识: str, 类型: str, 最后消息ID: int, 时间戳: int, 新增数量: int
) -> None:
    if not 会话标识:
        return
    游标.execute(
        f"""
        INSERT INTO `{会话索引表名}`
            (chat_type, conversation_id, last_id, last_ts, message_count)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            last_ts=IF(VALUES(last_id)>=last_id, VALUES(last_ts), last_ts),
            last_id=GREATEST(last_id, VALUES(last_id)),
            message_count=message_count+VALUES(message_count)
        """,
        (
            _按列宽截断(类型 or "group", "消息类型"),
            _按列宽截断(会话标识, "会话标识"),
            max(0, int(最后消息ID or 0)),
            max(0, int(时间戳 or 0)),
            max(0, int(新增数量 or 0)),
        ),
    )


def _同步批量会话索引(游标: Any, 新增参数: list[tuple[Any, ...]]) -> None:
    """按批次消息 ID 回查新增行，避免扫描整个活跃会话历史。"""
    新增数量: dict[tuple[str, str], int] = {}
    空ID会话: set[tuple[str, str]] = set()
    消息键列表: list[tuple[str, str]] = []
    for 参数 in 新增参数:
        会话 = str(参数[0] or "")
        类型 = str(参数[1] or "group")
        if 会话:
            键 = (类型, 会话)
            新增数量[键] = 新增数量.get(键, 0) + 1
            消息ID = str(参数[3] or "")
            if 消息ID:
                消息键列表.append((会话, 消息ID))
            else:
                空ID会话.add(键)
    if not 新增数量:
        return

    最后消息: dict[tuple[str, str], tuple[int, int]] = {}
    for 起点 in range(0, len(消息键列表), _消息查重分块大小):
        分块 = 消息键列表[起点 : 起点 + _消息查重分块大小]
        占位符 = ",".join(["(%s,%s)"] * len(分块))
        查询参数: list[str] = []
        for 会话, 消息ID in 分块:
            查询参数.extend((会话, 消息ID))
        游标.execute(
            f"SELECT 会话标识, 消息类型, id, ts FROM `{消息记录表名}` "
            f"WHERE (会话标识, message_id) IN ({占位符})",
            tuple(查询参数),
        )
        for 行 in 游标.fetchall():
            键 = (
                str(_行字段(行, 1, "消息类型", 默认值="group") or "group"),
                str(_行字段(行, 0, "会话标识", 默认值="") or ""),
            )
            消息ID = int(_行字段(行, 2, "id", 默认值=0) or 0)
            时间戳 = int(_行字段(行, 3, "ts", 默认值=0) or 0)
            if 键 in 新增数量 and 消息ID > 最后消息.get(键, (0, 0))[0]:
                最后消息[键] = (消息ID, 时间戳)

    for 类型, 会话 in 空ID会话:
        游标.execute(
            f"SELECT id, ts FROM `{消息记录表名}` "
            "WHERE 会话标识=%s AND 消息类型=%s ORDER BY id DESC LIMIT 1",
            (会话, 类型),
        )
        行 = 游标.fetchone()
        if 行:
            最后消息[(类型, 会话)] = (
                int(_行字段(行, 0, "id", 默认值=0) or 0),
                int(_行字段(行, 1, "ts", 默认值=0) or 0),
            )

    for (类型, 会话), 数量 in 新增数量.items():
        最后ID, 时间戳 = 最后消息.get((类型, 会话), (0, 0))
        if 最后ID:
            _写入会话索引(游标, 会话, 类型, 最后ID, 时间戳, 数量)


def _批量读取已存在消息键(游标: Any, 键列表: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """一次查询一批已入库消息，避免批量写入时逐条 SELECT。"""
    已存在: set[tuple[str, str]] = set()
    有效键 = [(会话, 消息ID) for 会话, 消息ID in 键列表 if 会话 and 消息ID]
    for 起点 in range(0, len(有效键), _消息查重分块大小):
        分块 = 有效键[起点 : 起点 + _消息查重分块大小]
        占位符 = ",".join(["(%s,%s)"] * len(分块))
        参数: list[str] = []
        for 会话, 消息ID in 分块:
            参数.extend((会话, 消息ID))
        游标.execute(
            f"SELECT 会话标识, message_id FROM `{消息记录表名}` "
            f"WHERE (会话标识, message_id) IN ({占位符})",
            tuple(参数),
        )
        for 行 in 游标.fetchall():
            会话 = str(_行字段(行, 0, "会话标识", 默认值="") or "")
            消息ID = str(_行字段(行, 1, "message_id", 默认值="") or "")
            if 会话 and 消息ID:
                已存在.add((会话, 消息ID))
    return 已存在


def _写入消息记录(记录: dict[str, Any]) -> bool:
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            会话标识, 消息ID = _消息记录去重键(记录)
            if 消息ID:
                游标.execute(
                    f"SELECT id FROM `{消息记录表名}` WHERE 会话标识=%s AND message_id=%s LIMIT 1",
                    (会话标识, 消息ID),
                )
                已有行 = 游标.fetchone()
                if 已有行:
                    游标.execute(_消息更新SQL, _消息更新参数(记录))
                    最后消息ID = int(_行字段(已有行, 0, "id", 默认值=0) or 0)
                    游标.execute(
                        f"SELECT ts FROM `{消息记录表名}` WHERE id=%s LIMIT 1",
                        (最后消息ID,),
                    )
                    时间行 = 游标.fetchone()
                    参数 = _消息写入参数(记录)
                    _写入会话索引(
                        游标,
                        会话标识,
                        str(参数[1] or "group"),
                        最后消息ID,
                        int(_行字段(时间行, 0, "ts", 默认值=0) or 0),
                        0,
                    )
                    连接.commit()
                    return True
            参数 = _消息写入参数(记录)
            游标.execute(_消息写入SQL, 参数)
            _写入会话索引(
                游标,
                会话标识,
                str(参数[1] or "group"),
                int(getattr(游标, "lastrowid", 0) or 0),
                int(参数[8] or 0),
                1,
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


def 读取消息媒体归档(
    会话标识: str, 消息ID: str, 类型: str = ""
) -> dict[str, Any] | None:
    会话标识 = str(会话标识 or "").strip()
    消息ID = _规范消息ID(消息ID)
    类型 = str(类型 or "").strip().lower()
    if not 会话标识 or not 消息ID or not _MySQL可用():
        return None
    连接 = _打开连接()
    if 连接 is None:
        return None
    try:
        with 连接.cursor() as 游标:
            类型过滤 = " AND 消息类型=%s" if 类型 in {"group", "user"} else ""
            参数: tuple[str, ...] = (
                (会话标识, 消息ID, 类型)
                if 类型过滤
                else (会话标识, 消息ID)
            )
            游标.execute(
                f"SELECT media FROM `{消息记录表名}` "
                f"WHERE 会话标识=%s AND message_id=%s{类型过滤} "
                "ORDER BY id DESC LIMIT 1",
                参数,
            )
            行 = 游标.fetchone()
        if not 行:
            return None
        原文 = _行字段(行, 0, "media", 默认值="{}")
        if isinstance(原文, bytes):
            原文 = 原文.decode("utf-8", errors="replace")
        媒体 = json.loads(str(原文 or "{}"))
        归档 = 媒体.get("_lanzou_archive") if isinstance(媒体, dict) else None
        return 归档 if isinstance(归档, dict) else None
    except Exception as exc:
        logger.debug("消息记录 MySQL 图片归档读取失败：错误类型=%s", type(exc).__name__)
        return None
    finally:
        _关闭连接(连接)


def 批量写入消息(记录列表: list[dict[str, Any]]) -> bool:
    """使用单连接、单事务批量写入消息，供异步持久化队列调用。"""
    有效记录 = [记录 for 记录 in (记录列表 or []) if 记录 and 记录.get("_session")]
    if not 有效记录 or not _MySQL可用():
        return False
    去重记录: list[dict[str, Any]] = []
    已见索引: dict[tuple[str, str], int] = {}
    for 记录 in 有效记录:
        键 = _消息记录去重键(记录)
        消息ID = 键[1]
        if 消息ID and 键 in 已见索引:
            去重记录[已见索引[键]] = 记录
            continue
        if 消息ID:
            已见索引[键] = len(去重记录)
        去重记录.append(记录)
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            记录键列表 = [(记录, _消息记录去重键(记录)) for 记录 in 去重记录]
            已存在 = _批量读取已存在消息键(
                游标,
                [键 for _, 键 in 记录键列表],
            )
            待更新记录 = [记录 for 记录, 键 in 记录键列表 if 键[1] and 键 in 已存在]
            待写入记录 = [记录 for 记录, 键 in 记录键列表 if not 键[1] or 键 not in 已存在]
            待更新 = [_消息更新参数(记录) for 记录 in 待更新记录]
            待写入 = [_消息写入参数(记录) for 记录 in 待写入记录]
            if 待更新:
                游标.executemany(_消息更新SQL, 待更新)
            if 待写入:
                游标.executemany(_消息写入SQL, 待写入)
                _同步批量会话索引(游标, 待写入)
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
    message_id = _规范消息ID(message_id)
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
            已更新 = int(getattr(游标, "rowcount", 0) or 0)
        连接.commit()
        return 已更新 > 0
    except Exception as exc:
        logger.warning("消息记录 MySQL 撤回标记失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def 读取群成员最近消息(
    会话标识: str, 用户标识: str, 当前消息: str, 截至时间: int, 上限: int = 30,
) -> list[dict[str, Any]]:
    """只取撤回需要的标识与状态，不限制消息年龄，不加载正文或媒体。"""
    if not 会话标识 or not 用户标识 or not _MySQL可用():
        return []
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                f"SELECT id, ts FROM `{消息记录表名}` "
                "WHERE 会话标识=%s AND message_id=%s AND user_id=%s "
                "AND 消息类型='group' ORDER BY id DESC LIMIT 1",
                (会话标识, 当前消息, 用户标识),
            )
            锚点 = 游标.fetchone()
            锚点ID = int(_行字段(锚点, 0, "id", 默认值=0) or 0)
            锚点时间 = int(_行字段(锚点, 1, "ts", 默认值=截至时间) or 截至时间)
            时间上限 = min(截至时间, 锚点时间)
            条件 = ["会话标识=%s", "user_id=%s", "消息类型='group'", "is_self=0", "message_id<>''", "ts<=%s"]
            参数: list[Any] = [会话标识, 用户标识, 时间上限]
            if 锚点ID:
                条件.append("id<=%s")
                参数.append(锚点ID)
            参数.append(max(1, min(30, int(上限))))
            游标.execute(
                f"SELECT message_id, ts, recalled FROM `{消息记录表名}` WHERE "
                + " AND ".join(条件) + " ORDER BY ts DESC, id DESC LIMIT %s",
                tuple(参数),
            )
            return [
                {"message_id": _规范消息ID(_行字段(行, 0, "message_id")),
                 "ts": int(_行字段(行, 1, "ts", 默认值=0) or 0),
                 "recalled": bool(_行字段(行, 2, "recalled", 默认值=False))}
                for 行 in 游标.fetchall()
            ]
    except Exception as exc:
        logger.warning(
            "群成员历史消息读取失败：group_id=%s, user_id=%s, error_type=%s",
            会话标识, 用户标识, type(exc).__name__,
        )
        return []
    finally:
        _关闭连接(连接)


def _读取最近群消息昵称(用户标识: str, 会话标识: str = "", appid: str = "") -> str:
    用户标识 = str(用户标识 or "").strip()
    会话标识 = str(会话标识 or "").strip()
    appid = str(appid or "").strip()
    if not 用户标识 or not _MySQL可用():
        return ""
    身份路径 = (
        "$.author.member_openid",
        "$.author.user_openid",
        "$.author.id",
        "$.member.member_openid",
        "$.member.user_openid",
        "$.data.author.member_openid",
        "$.data.author.user_openid",
        "$.d.author.member_openid",
        "$.d.author.user_openid",
    )
    身份条件 = ["m.user_id=%s"]
    参数: tuple[str, ...] = (用户标识,)
    for 路径 in 身份路径:
        身份条件.append(
            "CASE WHEN JSON_VALID(m.raw_message) "
            f"THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '{路径}')) "
            "ELSE '' END=%s"
        )
        参数 += (用户标识,)
    where_sql = (
        "WHERE m.消息类型='group' AND m.is_self=0 AND ("
        + " OR ".join(身份条件)
        + ")"
    )
    if 会话标识:
        where_sql += " AND m.会话标识=%s"
        参数 += (会话标识,)
    if appid:
        where_sql += " AND m.appid=%s"
        参数 += (appid,)
    连接 = _打开连接()
    if 连接 is None:
        return ""
    try:
        with 连接.cursor() as 游标:
            游标.execute(
                "SELECT m.nickname, "
                "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.author.username')) ELSE '' END AS author_username, "
                "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.author.member_name')) ELSE '' END AS author_member_name, "
                "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.author.nickname')) ELSE '' END AS author_nickname, "
                "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.member.nick')) ELSE '' END AS member_nick, "
                "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.member.nickname')) ELSE '' END AS member_nickname, "
                "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.data.author.username')) ELSE '' END AS data_author_username "
                f"FROM `{消息记录表名}` m {where_sql} ORDER BY m.ts DESC, m.id DESC LIMIT 256",
                参数,
            )
            行列表 = 游标.fetchall()
        for 行 in 行列表 or ():
            for 索引, 字段名 in enumerate((
                "nickname",
                "author_username",
                "author_member_name",
                "author_nickname",
                "member_nick",
                "member_nickname",
                "data_author_username",
            )):
                昵称 = str(_行字段(行, 索引, 字段名, 默认值="") or "").strip()
                if (
                    not 昵称
                    or 昵称 == 用户标识
                    or 昵称 in {"成员", "新成员", "未知", "未知用户", "机器人", "我"}
                    or any(ord(字符) < 32 or 127 <= ord(字符) <= 159 for 字符 in 昵称)
                ):
                    continue
                return 昵称
        if not 会话标识:
            关联参数: list[str] = [用户标识]
            appid条件 = ""
            if appid:
                appid条件 = " AND mapping.appid=%s AND m.appid=%s"
                关联参数.extend((appid, appid))
            else:
                appid条件 = " AND (mapping.appid=m.appid OR mapping.appid='' OR m.appid='')"
            with 连接.cursor() as 游标:
                游标.execute(
                    "SELECT m.nickname, "
                    "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.author.username')) ELSE '' END AS author_username, "
                    "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.author.member_name')) ELSE '' END AS author_member_name, "
                    "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.author.nickname')) ELSE '' END AS author_nickname, "
                    "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.member.nick')) ELSE '' END AS member_nick, "
                    "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.member.nickname')) ELSE '' END AS member_nickname, "
                    "CASE WHEN JSON_VALID(m.raw_message) THEN JSON_UNQUOTE(JSON_EXTRACT(m.raw_message, '$.data.author.username')) ELSE '' END AS data_author_username "
                    f"FROM `{群成员映射表名}` mapping "
                    f"JOIN `{消息记录表名}` m ON mapping.group_openid=m.会话标识 "
                    "AND mapping.member_openid=m.user_id AND m.消息类型='group' AND m.is_self=0 "
                    "WHERE mapping.user_openid=%s"
                    + appid条件
                    + " ORDER BY m.ts DESC, m.id DESC LIMIT 256",
                    tuple(关联参数),
                )
                映射行列表 = 游标.fetchall()
            for 行 in 映射行列表 or ():
                for 索引, 字段名 in enumerate((
                    "nickname",
                    "author_username",
                    "author_member_name",
                    "author_nickname",
                    "member_nick",
                    "member_nickname",
                    "data_author_username",
                )):
                    昵称 = str(_行字段(行, 索引, 字段名, 默认值="") or "").strip()
                    if (
                        not 昵称
                        or 昵称 == 用户标识
                        or 昵称 in {"成员", "新成员", "未知", "未知用户", "机器人", "我"}
                        or any(ord(字符) < 32 or 127 <= ord(字符) <= 159 for 字符 in 昵称)
                    ):
                        continue
                    return 昵称
        return ""
    except Exception as exc:
        logger.warning("群成员昵称回查失败：错误类型=%s", type(exc).__name__)
        return ""
    finally:
        _关闭连接(连接)


def _有效用户昵称(用户标识: str, 昵称: Any) -> str:
    昵称 = str(昵称 or "").strip()
    if (
        not 昵称
        or 昵称 == 用户标识
        or 昵称 == "用户" + str(用户标识 or "")[-6:]
        or 昵称 in {"成员", "新成员", "未知", "未知用户", "机器人", "我"}
        or any(ord(字符) < 32 or 127 <= ord(字符) <= 159 for 字符 in 昵称)
    ):
        return ""
    return 昵称


def 批量保存用户昵称(资料列表: list[dict[str, Any]]) -> bool:
    """按应用和 OpenID 持久化 QQ 消息事件中的有效用户名。"""
    if not _MySQL可用() or not 资料列表:
        return not 资料列表
    当前时间 = int(time.time())
    按用户去重: dict[tuple[str, str], tuple[str, str, str, str, str, int]] = {}
    for 资料 in 资料列表:
        if not isinstance(资料, dict):
            continue
        用户标识 = str(资料.get("user_id") or "").strip()
        昵称 = _有效用户昵称(用户标识, 资料.get("nickname"))
        统一用户标识 = str(资料.get("union_openid") or "").strip()[:128]
        if not 用户标识 or (not 昵称 and not 统一用户标识):
            continue
        appid = str(资料.get("appid") or "").strip()
        profile_key = hashlib.sha256(f"{appid}\0{用户标识}".encode("utf-8")).hexdigest()
        按用户去重[(appid, 用户标识)] = (
            profile_key, appid, 用户标识, 昵称, 统一用户标识, 当前时间
        )
    if not 按用户去重:
        return True
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            游标.executemany(
                f"INSERT INTO `{用户资料表名}` "
                "(profile_key, appid, user_id, nickname, union_openid, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "nickname=IF(VALUES(nickname)<>'',VALUES(nickname),nickname), "
                "union_openid=IF(VALUES(union_openid)<>'',VALUES(union_openid),union_openid), "
                "updated_at=GREATEST(updated_at,VALUES(updated_at))",
                list(按用户去重.values()),
            )
        连接.commit()
        return True
    except Exception as exc:
        logger.warning("QQ用户昵称资料写入失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def 批量保存群成员映射(映射列表: list[dict[str, Any]]) -> bool:
    """持久化 QQ 群成员 OpenID 与私聊 user_openid 的关联。"""
    if not _MySQL可用() or not 映射列表:
        return not 映射列表
    当前时间 = int(time.time())
    去重映射: dict[tuple[str, str, str], tuple[str, str, str, str, str, int]] = {}
    for 映射 in 映射列表:
        if not isinstance(映射, dict):
            continue
        appid = str(映射.get("appid") or "").strip()[:64]
        群标识 = str(映射.get("group_openid") or "").strip()[:128]
        用户标识 = str(映射.get("user_openid") or "").strip()[:128]
        成员标识 = str(映射.get("member_openid") or "").strip()[:128]
        if not 群标识 or not 用户标识 or not 成员标识:
            continue
        映射键 = hashlib.sha256(
            "\x1f".join((appid, 群标识, 成员标识)).encode("utf-8", errors="ignore")
        ).hexdigest()
        去重映射[(appid, 群标识, 成员标识)] = (
            映射键, appid, 群标识, 用户标识, 成员标识, 当前时间
        )
    if not 去重映射:
        return True
    连接 = _打开连接()
    if 连接 is None:
        return False
    try:
        with 连接.cursor() as 游标:
            游标.executemany(
                f"INSERT INTO `{群成员映射表名}` "
                "(mapping_key, appid, group_openid, user_openid, member_openid, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "user_openid=VALUES(user_openid), updated_at=VALUES(updated_at)",
                list(去重映射.values()),
            )
        连接.commit()
        return True
    except Exception as exc:
        logger.warning("QQ群成员映射写入失败：错误类型=%s", type(exc).__name__)
        return False
    finally:
        _关闭连接(连接)


def 保存用户昵称(appid: str, 用户标识: str, 昵称: str) -> bool:
    return 批量保存用户昵称([{"appid": appid, "user_id": 用户标识, "nickname": 昵称}])


def 读取用户昵称(用户标识: str, appid: str = "") -> str:
    """按应用和 OpenID 读取消息事件中最近保存的用户昵称。"""
    用户标识 = str(用户标识 or "").strip()
    appid = str(appid or "").strip()
    if not 用户标识 or not _MySQL可用():
        return ""
    连接 = _打开连接()
    if 连接 is None:
        return ""
    try:
        with 连接.cursor() as 游标:
            if appid:
                游标.execute(
                    f"SELECT nickname FROM `{用户资料表名}` WHERE appid=%s AND user_id=%s LIMIT 1",
                    (appid, 用户标识),
                )
            else:
                游标.execute(
                    f"SELECT nickname FROM `{用户资料表名}` WHERE user_id=%s "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (用户标识,),
                )
            行 = 游标.fetchone()
        return _有效用户昵称(用户标识, _行字段(行, 0, "nickname", 默认值=""))
    except Exception as exc:
        logger.warning("QQ用户昵称资料读取失败：错误类型=%s", type(exc).__name__)
        return ""
    finally:
        _关闭连接(连接)


def 批量读取用户昵称(用户列表: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """按 appid + user_openid 批量读取资料，避免聊天列表逐用户查库。"""
    结果: dict[tuple[str, str], str] = {}
    if not 用户列表 or not _MySQL可用():
        return 结果
    查询项 = list(dict.fromkeys(
        (str(项.get("appid") or "").strip()[:64], str(项.get("user_id") or "").strip()[:128])
        for 项 in 用户列表
        if isinstance(项, dict) and str(项.get("user_id") or "").strip()
    ))
    if not 查询项:
        return 结果
    连接 = _打开连接()
    if 连接 is None:
        return 结果
    try:
        for 起点 in range(0, len(查询项), 200):
            分块 = 查询项[起点 : 起点 + 200]
            条件 = " OR ".join("(appid=%s AND user_id=%s)" for _ in 分块)
            参数: list[str] = []
            for appid, 用户标识 in 分块:
                参数.extend((appid, 用户标识))
            with 连接.cursor() as 游标:
                游标.execute(
                    f"SELECT appid, user_id, nickname FROM `{用户资料表名}` WHERE {条件}",
                    tuple(参数),
                )
                for 行 in 游标.fetchall() or ():
                    appid = str(_行字段(行, 0, "appid", 默认值="") or "").strip()
                    用户标识 = str(_行字段(行, 1, "user_id", 默认值="") or "").strip()
                    昵称 = _有效用户昵称(用户标识, _行字段(行, 2, "nickname", 默认值=""))
                    if 用户标识 and 昵称:
                        结果[(appid, 用户标识)] = 昵称
        return 结果
    except Exception as exc:
        logger.warning("QQ用户昵称批量读取失败：错误类型=%s", type(exc).__name__)
        return 结果
    finally:
        _关闭连接(连接)


def 批量读取用户最近群聊昵称(用户列表: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """按用户批量读取最近有效群昵称，优先走 OpenID 映射和可用索引。"""
    结果: dict[tuple[str, str], str] = {}
    if not 用户列表 or not _MySQL可用():
        return 结果
    分组: dict[str, list[str]] = {}
    for 项 in 用户列表:
        if not isinstance(项, dict):
            continue
        appid = str(项.get("appid") or "").strip()[:64]
        用户标识 = str(项.get("user_id") or "").strip()[:128]
        if 用户标识:
            用户列表项 = 分组.setdefault(appid, [])
            if 用户标识 not in 用户列表项:
                用户列表项.append(用户标识)
    if not 分组:
        return 结果
    连接 = _打开连接()
    if 连接 is None:
        return 结果
    结果时间: dict[tuple[str, str], tuple[int, int]] = {}

    def 记录昵称(
        记录appid: str,
        用户标识: str,
        昵称: str,
        时间戳: Any,
        记录ID: Any,
        允许跨应用回退: bool,
    ) -> None:
        排序键 = (int(时间戳 or 0), int(记录ID or 0))
        键列表 = [(记录appid, 用户标识)]
        if 允许跨应用回退:
            键列表.append(("", 用户标识))
        for 键 in 键列表:
            if 排序键 >= 结果时间.get(键, (-1, -1)):
                结果时间[键] = 排序键
                结果[键] = 昵称

    def 昵称条件(消息别名: str, 用户字段: str) -> str:
        昵称表达式 = _原始消息昵称表达式(消息别名, 用户字段)
        return (
            f"{昵称表达式}<>'' "
            f"AND {昵称表达式}<>COALESCE({用户字段},'') "
            f"AND {昵称表达式}<>CONCAT('用户',RIGHT(COALESCE({用户字段},''),6)) "
            f"AND {昵称表达式} NOT IN ('成员','新成员','未知','未知用户','机器人','我')"
        )

    try:
        for appid, 用户标识列表 in 分组.items():
            for 起点 in range(0, len(用户标识列表), 200):
                分块 = 用户标识列表[起点 : 起点 + 200]
                占位符 = ",".join("%s" for _ in 分块)
                appid条件 = " AND x.appid=%s" if appid else ""
                直接参数: list[str] = list(分块)
                if appid:
                    直接参数.append(appid)
                有效昵称 = 昵称条件("x", "x.user_id")
                with 连接.cursor() as 游标:
                    游标.execute(
                        "SELECT m.appid,m.user_id,"
                        f"{_原始消息昵称表达式('m', 'm.user_id')} AS nickname,m.ts,m.id "
                        f"FROM `{消息记录表名}` m JOIN ("
                        f"SELECT x.appid,x.user_id,MAX(x.id) AS last_id FROM `{消息记录表名}` x "
                        f"WHERE x.消息类型='group' AND x.is_self=0 AND x.user_id IN ({占位符})"
                        f"{appid条件} AND {有效昵称} GROUP BY x.appid,x.user_id"
                        ") latest ON latest.last_id=m.id ORDER BY m.ts DESC,m.id DESC",
                        tuple(直接参数),
                    )
                    直接行列表 = 游标.fetchall() or ()
                for 行 in 直接行列表:
                    记录appid = str(_行字段(行, 0, "appid", 默认值="") or "").strip()
                    用户标识 = str(_行字段(行, 1, "user_id", 默认值="") or "").strip()
                    昵称 = _有效用户昵称(
                        用户标识,
                        _行字段(行, 2, "nickname", 默认值=""),
                    )
                    if not 用户标识 or not 昵称:
                        continue
                    记录昵称(
                        记录appid,
                        用户标识,
                        昵称,
                        _行字段(行, 3, "ts", 默认值=0),
                        _行字段(行, 4, "id", 默认值=0),
                        not appid,
                    )

                映射appid条件 = " AND (l.appid=%s OR l.appid='')" if appid else ""
                映射参数: list[str] = list(分块)
                if appid:
                    映射参数.append(appid)
                有效映射昵称 = 昵称条件("m", "l.member_openid")
                有效子查询昵称 = 昵称条件("r", "l.member_openid")
                with 连接.cursor() as 游标:
                    游标.execute(
                        "SELECT l.appid,l.user_openid,"
                        f"{_原始消息昵称表达式('m', 'l.member_openid')} AS nickname,m.ts,m.id "
                        f"FROM `{群成员映射表名}` l JOIN `{消息记录表名}` m "
                        "ON m.会话标识=l.group_openid AND m.user_id=l.member_openid "
                        "AND m.消息类型='group' AND m.is_self=0 "
                        "AND (l.appid='' OR m.appid=l.appid) "
                        f"WHERE l.user_openid IN ({占位符}){映射appid条件} "
                        f"AND {有效映射昵称} AND m.id=(SELECT MAX(r.id) "
                        f"FROM `{消息记录表名}` r WHERE r.会话标识=l.group_openid "
                        "AND r.user_id=l.member_openid AND r.消息类型='group' AND r.is_self=0 "
                        "AND (l.appid='' OR r.appid=l.appid) "
                        f"AND {有效子查询昵称}) ORDER BY m.ts DESC,m.id DESC",
                        tuple(映射参数),
                    )
                    映射行列表 = 游标.fetchall() or ()
                for 行 in 映射行列表:
                    记录appid = str(_行字段(行, 0, "appid", 默认值="") or "").strip()
                    用户标识 = str(_行字段(行, 1, "user_openid", 默认值="") or "").strip()
                    昵称 = _有效用户昵称(
                        用户标识,
                        _行字段(行, 2, "nickname", 默认值=""),
                    )
                    if not 用户标识 or not 昵称:
                        continue
                    记录昵称(
                        记录appid,
                        用户标识,
                        昵称,
                        _行字段(行, 3, "ts", 默认值=0),
                        _行字段(行, 4, "id", 默认值=0),
                        not appid or not 记录appid,
                    )

                资料appid条件 = " AND (p.appid=%s OR p.appid='')" if appid else ""
                资料参数: list[str] = list(分块)
                if appid:
                    资料参数.append(appid)
                with 连接.cursor() as 游标:
                    游标.execute(
                        "SELECT p.appid,p.user_id,g.nickname,g.updated_at "
                        f"FROM `{用户资料表名}` p JOIN `{用户资料表名}` g "
                        "ON g.union_openid=p.union_openid "
                        f"WHERE p.user_id IN ({占位符}){资料appid条件} "
                        "AND p.union_openid<>'' AND g.nickname<>'' "
                        "AND g.nickname<>COALESCE(g.user_id,'') "
                        "AND g.nickname<>CONCAT('用户',RIGHT(COALESCE(g.user_id,''),6)) "
                        "AND g.nickname NOT IN ('成员','新成员','未知','未知用户','机器人','我') "
                        "ORDER BY g.updated_at DESC LIMIT 2000",
                        tuple(资料参数),
                    )
                    资料行列表 = 游标.fetchall() or ()
                for 行 in 资料行列表:
                    记录appid = str(_行字段(行, 0, "appid", 默认值="") or "").strip()
                    用户标识 = str(_行字段(行, 1, "user_id", 默认值="") or "").strip()
                    昵称 = _有效用户昵称(
                        用户标识,
                        _行字段(行, 2, "nickname", 默认值=""),
                    )
                    if not 用户标识 or not 昵称:
                        continue
                    记录昵称(
                        记录appid,
                        用户标识,
                        昵称,
                        _行字段(行, 3, "updated_at", 默认值=0),
                        0,
                        not appid,
                    )
        return 结果
    except Exception as exc:
        logger.warning("QQ用户批量群昵称读取失败：错误类型=%s", type(exc).__name__)
        return 结果
    finally:
        _关闭连接(连接)


def 读取群成员最近昵称(会话标识: str, 用户标识: str, appid: str = "") -> str:
    """从该群成员最近保存的消息或原始事件字段读取有效昵称。"""
    会话标识 = str(会话标识 or "").strip()
    if not 会话标识:
        return ""
    return _读取最近群消息昵称(用户标识, 会话标识=会话标识, appid=appid)


def 读取用户最近群聊昵称(用户标识: str, appid: str = "") -> str:
    """按用户 OpenID 跨群读取最近有效昵称，供私聊联系人资料复用。"""
    return _读取最近群消息昵称(用户标识, appid=appid)


def 读取会话消息(
    会话标识: str, 上限: int = 500, 会话类型: str = ""
) -> list[dict[str, Any]]:
    """按时间正序返回某会话最近 N 条消息。"""
    if not _MySQL可用():
        return []
    上限 = max(1, min(上限, 5000))
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            会话类型 = str(会话类型 or "").strip().lower()
            类型条件 = " AND 消息类型=%s" if 会话类型 in {"group", "user"} else ""
            参数: tuple[Any, ...] = (
                (str(会话标识 or ""), 会话类型, 上限)
                if 类型条件
                else (str(会话标识 or ""), 上限)
            )
            游标.execute(
                f"SELECT * FROM (SELECT {_历史查询字段SQL} FROM `{消息记录表名}` "
                f"WHERE 会话标识=%s{类型条件} ORDER BY ts DESC, id DESC LIMIT %s) t ORDER BY ts ASC, id ASC",
                参数,
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
            游标.execute(
                f"SELECT state_value FROM `{会话索引状态表名}` WHERE state_key=%s LIMIT 1",
                (会话索引就绪键,),
            )
            索引就绪 = str(
                _行字段(游标.fetchone(), 0, "state_value", 默认值="") or ""
            ) == "ready"
            if 索引就绪:
                游标.execute(
                    f"SELECT DISTINCT conversation_id FROM `{会话索引表名}` WHERE message_count > 0"
                )
            else:
                游标.execute(f"SELECT DISTINCT 会话标识 FROM `{消息记录表名}`")
            return [
                str(_行字段(行, 0, "conversation_id" if 索引就绪 else "会话标识", 默认值=""))
                for 行 in 游标.fetchall()
                if _行字段(行, 0, "conversation_id" if 索引就绪 else "会话标识", 默认值="")
            ]
    except Exception as exc:
        logger.warning("消息记录 MySQL 会话列表读取失败：错误类型=%s", type(exc).__name__)
        return []
    finally:
        _关闭连接(连接)


def 聚合聊天列表(上限: int = 200, 类型过滤: str = "") -> list[dict[str, Any]]:
    """从按房间维护的轻量索引读取会话列表，不扫描消息正文表。"""
    if not _MySQL可用():
        return []
    try:
        上限 = int(上限)
    except (TypeError, ValueError):
        上限 = 200
    # 上限 <= 0 表示读取全部会话，供控制台群列表使用。
    上限 = 0 if 上限 <= 0 else min(上限, 5000)
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            类型过滤 = str(类型过滤 or "").strip().lower()
            游标.execute(
                f"SELECT state_value FROM `{会话索引状态表名}` WHERE state_key=%s LIMIT 1",
                (会话索引就绪键,),
            )
            索引就绪 = str(
                _行字段(游标.fetchone(), 0, "state_value", 默认值="") or ""
            ) == "ready"
            if 索引就绪:
                查询 = (
                    f"SELECT chat_type, conversation_id, last_id, last_ts, message_count "
                    f"FROM `{会话索引表名}` WHERE message_count > 0"
                )
                参数: tuple[Any, ...] = ()
                if 类型过滤 in {"group", "user"}:
                    查询 += " AND chat_type=%s"
                    参数 = (类型过滤,)
                查询 += " ORDER BY last_ts DESC, last_id DESC"
                if 上限 > 0:
                    查询 += " LIMIT %s"
                    游标.execute(查询, (*参数, 上限))
                else:
                    游标.execute(查询, 参数)
                行列表 = 游标.fetchall()
            else:
                # 回填未完成时保持旧读取路径，避免升级中会话暂时消失。
                查询 = (
                    f"SELECT 统计.会话标识, 统计.last_id, 消息.ts AS last_ts, 统计.n "
                    f"FROM (SELECT 会话标识, MAX(id) AS last_id, COUNT(*) AS n "
                    f"FROM `{消息记录表名}` "
                    "WHERE 会话标识 != '' GROUP BY 会话标识) 统计 "
                    f"JOIN `{消息记录表名}` 消息 ON 消息.id = 统计.last_id "
                    "ORDER BY 消息.ts DESC, 消息.id DESC"
                )
                if 上限 > 0:
                    查询 += " LIMIT %s"
                    游标.execute(查询, (上限,))
                else:
                    游标.execute(查询)
                行列表 = 游标.fetchall()
        结果: list[dict[str, Any]] = []
        for 行 in 行列表:
            if isinstance(行, Mapping):
                if 索引就绪:
                    结果.append(
                        {
                            "会话标识": str(_行字段(行, 1, "conversation_id", 默认值="") or ""),
                            "chat_type": str(_行字段(行, 0, "chat_type", 默认值="group") or "group"),
                            "last_id": int(_行字段(行, 2, "last_id", 默认值=0) or 0),
                            "last_ts": int(_行字段(行, 3, "last_ts", 默认值=0) or 0),
                            "msg_count": int(_行字段(行, 4, "message_count", "msg_count", 默认值=0) or 0),
                        }
                    )
                else:
                    结果.append(
                        {
                            "会话标识": str(_行字段(行, 0, "会话标识", 默认值="") or ""),
                            "chat_type": "",
                            "last_id": int(_行字段(行, 1, "last_id", 默认值=0) or 0),
                            "last_ts": int(_行字段(行, 2, "last_ts", 默认值=0) or 0),
                            "msg_count": int(_行字段(行, 3, "n", "msg_count", 默认值=0) or 0),
                        }
                    )
            else:
                if 索引就绪:
                    结果.append(
                        {
                            "会话标识": str(_行字段(行, 1, "conversation_id", 默认值="") or ""),
                            "chat_type": str(_行字段(行, 0, "chat_type", 默认值="group") or "group"),
                            "last_id": int(_行字段(行, 2, "last_id", 默认值=0) or 0),
                            "last_ts": int(_行字段(行, 3, "last_ts", 默认值=0) or 0),
                            "msg_count": int(_行字段(行, 4, "message_count", "msg_count", 默认值=0) or 0),
                        }
                    )
                else:
                    结果.append(
                        {
                            "会话标识": str(_行字段(行, 0, "会话标识", 默认值="") or ""),
                            "chat_type": "",
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
                游标.execute(
                    f"SELECT {_历史查询字段SQL} FROM `{消息记录表名}` WHERE id IN ({占位})",
                    tuple(分块),
                )
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
                # 列顺序必须与 _行转记录 保持一致；列表预览截取前 1024 个字符，
                # 原文只保留首尾字段（含 QQ timestamp），完整消息仍由历史接口分页读取。
                游标.execute(
                    f"SELECT id, 会话标识, 消息类型, appid, message_id, user_id, nickname, "
                     f"LEFT(content, 1024) AS content, timestamp, ts, is_self, source, recalled, "
                     f"'' AS media, reference_id, refidx, avatar, "
                     f"CONCAT(LEFT(raw_message, 2048), RIGHT(raw_message, 512)) AS raw_message, member_role, msg_seq "
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
    会话类型: str = "",
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
    会话类型 = str(会话类型 or "").strip().lower()
    连接 = _打开连接()
    if 连接 is None:
        return []
    try:
        with 连接.cursor() as 游标:
            条件 = ["会话标识=%s"]
            参数列表: list[Any] = [会话标识]
            if 会话类型 in {"group", "user"}:
                条件.append("消息类型=%s")
                参数列表.append(会话类型)
            if before_id:
                条件.append("id < %s")
                参数列表.append(before_id)
            elif before_ts:
                条件.append("ts < %s")
                参数列表.append(before_ts)
            参数列表.append(查询上限)
            游标.execute(
                f"SELECT {_历史查询字段SQL} FROM `{消息记录表名}` "
                f"WHERE {' AND '.join(条件)} ORDER BY id DESC LIMIT %s",
                tuple(参数列表),
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
            游标.execute(
                f"SELECT state_value FROM `{会话索引状态表名}` WHERE state_key=%s LIMIT 1",
                (会话索引就绪键,),
            )
            索引就绪 = str(
                _行字段(游标.fetchone(), 0, "state_value", 默认值="") or ""
            ) == "ready"
            if 索引就绪:
                游标.execute(
                    f"SELECT COALESCE(SUM(message_count), 0) AS c FROM `{会话索引表名}`"
                )
            else:
                游标.execute(f"SELECT COUNT(*) AS c FROM `{消息记录表名}`")
            总数 = int(_行字段(游标.fetchone(), 0, "c", "COUNT(*)", 默认值=0) or 0)
            if 总数 > 上限:
                需要删 = 总数 - 上限
                受影响会话 = []
                if 索引就绪:
                    游标.execute(
                        f"SELECT 旧消息.消息类型, 旧消息.会话标识, COUNT(*) AS n FROM "
                        f"(SELECT 消息类型, 会话标识 FROM `{消息记录表名}` ORDER BY id ASC LIMIT %s) 旧消息 "
                        "GROUP BY 旧消息.消息类型, 旧消息.会话标识",
                        (需要删,),
                    )
                    受影响会话 = [
                        (
                            str(_行字段(行, 0, "消息类型", 默认值="group") or "group"),
                            str(_行字段(行, 1, "会话标识", 默认值="") or ""),
                            int(_行字段(行, 2, "n", "COUNT(*)", 默认值=0) or 0),
                        )
                        for 行 in 游标.fetchall()
                    ]
                游标.execute(
                    f"DELETE FROM `{消息记录表名}` WHERE id IN (SELECT id FROM (SELECT id FROM `{消息记录表名}` ORDER BY id ASC LIMIT %s) t)",
                    (需要删,),
                )
                if 索引就绪:
                    for 类型, 会话, 数量 in 受影响会话:
                        游标.execute(
                            f"UPDATE `{会话索引表名}` SET message_count=GREATEST(message_count-%s, 0) "
                            "WHERE chat_type=%s AND conversation_id=%s",
                            (数量, 类型, 会话),
                        )
                    游标.execute(f"DELETE FROM `{会话索引表名}` WHERE message_count <= 0")
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
            16: ("avatar",),
            17: ("raw_message",),
            18: ("member_role",),
            19: ("msg_seq",),
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
        "message_id": _规范消息ID(取值(4)),
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
        "avatar": 取值(16),
        "raw_message": 取值(17),
        "member_role": 取值(18),
        "msg_seq": 取值(19),
    }
