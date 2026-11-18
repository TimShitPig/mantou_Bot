"""仅净化 AstrBot 收到消息时的日志展示，不修改事件及消息记录。"""

from __future__ import annotations

import logging
import unicodedata

from astrbot.core import logger as 核心日志器

_过滤器标识 = "mantou.message_combining_guard"
_组合符号上限 = 8
_相同组合符号上限 = 3
_日志前缀上限 = 256


def 净化消息日志文本(文本: str) -> str:
    """只在异常组合符号串出现时保留有界前缀，隐藏剩余日志正文。"""
    起点 = 0
    连续数 = 0
    重复数 = 0
    上个符号 = ""
    for 位置, 字符 in enumerate(文本):
        # Mc/Me 也属于组合符号；部分高棉元音的 combining class 为 0。
        if not unicodedata.category(字符).startswith("M"):
            连续数 = 重复数 = 0
            上个符号 = ""
            continue
        if not 连续数:
            起点 = 位置
        连续数 += 1
        重复数 = 重复数 + 1 if 字符 == 上个符号 else 1
        上个符号 = 字符
        if 连续数 > _组合符号上限 or 重复数 > _相同组合符号上限:
            前缀 = 文本[:min(起点, _日志前缀上限)]
            if 起点 > _日志前缀上限:
                前缀 += "…"
            return 前缀 + f"[异常叠加字符消息已隐藏，原日志字符数={len(文本)}]"
    return 文本


class _消息日志过滤器(logging.Filter):
    _mantou_filter_tag = _过滤器标识

    def filter(self, record: logging.LogRecord) -> bool:
        # 官方核心 _print_event 的聊天摘要；不处理插件诊断或其他日志。
        路径 = record.pathname.replace("\\", "/")
        if (
            record.funcName != "_print_event"
            or not 路径.endswith("/astrbot/core/event_bus.py")
            or getattr(record, "category", "user_chat") != "user_chat"
        ):
            return True
        文本 = record.getMessage()
        净化后 = 净化消息日志文本(文本)
        if 净化后 != 文本:
            record.msg = 净化后
            record.args = ()
        return True


def 安装消息日志过滤器() -> logging.Filter:
    # 热重载不叠加自身旧过滤器，不触碰其他插件的过滤器或日志处理器。
    for 过滤器 in tuple(核心日志器.filters):
        if getattr(过滤器, "_mantou_filter_tag", None) == _过滤器标识:
            核心日志器.removeFilter(过滤器)
    过滤器 = _消息日志过滤器()
    核心日志器.addFilter(过滤器)
    return 过滤器


def 移除消息日志过滤器(过滤器: logging.Filter | None) -> None:
    # 只按本轮对象身份移除，旧句柄不能卸载新版过滤器。
    if 过滤器 is not None:
        核心日志器.removeFilter(过滤器)
