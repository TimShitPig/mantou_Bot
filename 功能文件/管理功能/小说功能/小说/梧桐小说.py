"""梧桐入口与独立客户端，复用疯狂追书的小说文件和网盘流程。"""

from __future__ import annotations

import logging
import re
from typing import Any, AsyncIterator, Mapping

try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger(__name__)

from 功能文件.管理功能.小说功能.功能.梧桐接口 import AsyncWutongClient
from 功能文件.管理功能.小说功能.小说 import 番茄小说, 疯狂追书小说

_下载命令正则 = re.compile(r"梧桐(?:小说)?[\s：:]+([0-9a-f]{24})", re.I)
提取梧桐书籍编号 = 疯狂追书小说.提取疯狂追书书籍编号
生成梧桐小说文件内容 = 疯狂追书小说.生成疯狂追书小说文件内容


def 提取梧桐来源(event: Any, 命令文本: Any = "") -> str | None:
    消息文本 = event.get("message_str") if isinstance(event, Mapping) else getattr(event, "message_str", "")
    for 文本 in (命令文本, 消息文本):
        if isinstance(文本, str):
            匹配 = _下载命令正则.fullmatch(文本.strip())
            if 匹配:
                return 匹配.group(1).lower()
    return None


def 规范化梧桐书籍信息(书籍编号: str, 详情: Mapping[str, Any]) -> dict[str, Any]:
    信息 = 疯狂追书小说.规范化疯狂追书书籍信息(书籍编号, 详情)
    if not 番茄小说.清理番茄网页文本(详情.get("title")):
        信息["title"] = f"梧桐小说{书籍编号}"
    return 信息


def 生成梧桐下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    return 疯狂追书小说.生成疯狂追书下载回复流(
        event, 来源, 配置, 客户端类=AsyncWutongClient,
        平台名="梧桐", 书籍信息规范化=规范化梧桐书籍信息,
    )


def 获取梧桐小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取梧桐来源(event, 命令文本)
    return 生成梧桐下载回复流(event, 来源, 配置) if 来源 else None


async def 搜索梧桐小说(关键词: str, 数量上限: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        上限 = max(1, min(int(数量上限), 30))
        async with AsyncWutongClient(concurrency=2) as client:
            搜索 = await client.search(关键词, page=1, page_size=上限)
        return [
            {"platform": "梧桐", "book_id": str(书["book_id"]),
             "title": 书["title"], "author": 书.get("author") or "未知", "url": "",
             "word_count": 书.get("word_count"), "chapter_count": 书.get("chapter_count"),
             "intro": 书.get("intro") or "", "score": 书.get("score"), "heat": 书.get("read_num")}
            for 书 in 搜索.get("items", [])[:上限]
            if 提取梧桐书籍编号(书.get("book_id")) and 书.get("title")
        ]
    except Exception as exc:
        logger.debug("梧桐小说搜索失败：error_type=%s", type(exc).__name__)
        return []
