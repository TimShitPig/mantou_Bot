"""疯狂追书入口、异步下载与番茄一致的 TXT/网盘出口。"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

try:
    from astrbot.api import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.疯狂追书接口 import AsyncFkzsClient, FkzsError
from 功能文件.管理功能.小说功能.小说 import 番茄小说
from 功能文件.管理功能.网盘功能 import 小说网盘

疯狂追书小说缓存目录 = 文件缓存工具.小说缓存目录
疯狂追书下载失败提示 = "下载失败 请重试"
疯狂追书文件发送失败提示 = "文件发送失败，请稍后再试"
_书籍编号正则 = re.compile(r"[0-9a-f]{24}", re.I)
_下载命令正则 = re.compile(r"疯狂追书(?:小说)?[\s：:]+([0-9a-f]{24})", re.I)


def 提取疯狂追书书籍编号(来源: Any) -> str:
    文本 = str(来源 or "").strip()
    return 文本.lower() if _书籍编号正则.fullmatch(文本) else ""


def 提取疯狂追书来源(event: Any, 命令文本: Any = "") -> str | None:
    """只接受本条明确的平台下载指令，不把引用或普通裸 ID 当下载入口。"""
    消息文本 = event.get("message_str") if isinstance(event, Mapping) else getattr(event, "message_str", "")
    for 文本 in (命令文本, 消息文本):
        if isinstance(文本, str):
            匹配 = _下载命令正则.fullmatch(文本.strip())
            if 匹配:
                return 匹配.group(1).lower()
    return None


def 规范化疯狂追书书籍信息(书籍编号: str, 详情: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": 番茄小说.清理番茄网页文本(详情.get("title")) or f"疯狂追书小说{书籍编号}",
        "author": 番茄小说.清理番茄网页文本(详情.get("author")) or "未知",
        "status": "完结" if str(详情.get("status") or "") in {"完结", "已完结", "完本"} else "连载",
        "word_count": 番茄小说.格式化番茄字数(详情.get("word_count")),
        "intro": 番茄小说.清理番茄网页文本(详情.get("intro")),
    }


def 生成疯狂追书小说文件内容(
    书籍编号: str, 书籍信息: dict[str, Any],
    目录: list[dict[str, Any]], 章节结果: list[dict[str, Any]],
) -> tuple[str, bytes]:
    """目录顺序、书籍和章节身份全部通过后复用番茄文件生成器。"""
    if not 目录 or len(目录) != len(章节结果):
        raise FkzsError("incomplete_chapters")
    输出 = []
    for 序号, (章节, 结果) in enumerate(zip(目录, 章节结果), 1):
        if (
            not 提取疯狂追书书籍编号(章节.get("chapter_id"))
            or str(章节.get("chapter_id")) != str(结果.get("chapter_id"))
            or str(结果.get("book_id")) != str(书籍编号)
            or not str(结果.get("text") or "").strip()
        ):
            raise FkzsError("invalid_chapter")
        标题 = 结果.get("title") or 章节.get("title") or f"第{序号}章"
        if not 番茄小说.去除章节正文重复标题(标题, 结果["text"]).strip():
            raise FkzsError("empty_chapter")
        输出.append({"index": 序号, "title": 标题, "content": 结果["text"], "success": True})
    return 番茄小说.生成番茄小说文件内容(书籍编号, 书籍信息, 目录, 输出)


def 写入疯狂追书下载缓存文件(文件名: str, 内容: bytes) -> Path:
    疯狂追书小说缓存目录.mkdir(parents=True, exist_ok=True)
    安全名称 = Path(番茄小说.清理番茄文件名(文件名)).name
    if not 安全名称.lower().endswith(".txt"):
        安全名称 += ".txt"
    路径 = 疯狂追书小说缓存目录 / 安全名称
    for 序号 in range(1000):
        候选 = 路径 if 序号 == 0 else 路径.with_name(f"{路径.stem}_{序号}{路径.suffix}")
        try:
            文件 = 候选.open("xb")
        except FileExistsError:
            continue
        try:
            with 文件:
                文件.write(内容)
            文件缓存工具.标记小说缓存正在使用(候选)
            return 候选
        except BaseException:
            文件缓存工具.删除小说缓存文件(候选)
            raise
    raise RuntimeError("cache_name_conflict")


async def _写入缓存(文件名: str, 内容: bytes) -> Path:
    任务 = asyncio.create_task(asyncio.to_thread(写入疯狂追书下载缓存文件, 文件名, 内容))
    try:
        return await asyncio.shield(任务)
    except asyncio.CancelledError:
        try:
            路径 = await 任务
            文件缓存工具.删除小说缓存文件(路径)
        finally:
            raise


async def 生成疯狂追书下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取疯狂追书书籍编号(来源)
    if not 书籍编号:
        yield 疯狂追书下载失败提示
        return
    阶段 = "metadata"
    路径: Path | None = None
    try:
        async with AsyncFkzsClient(concurrency=400) as client:
            详情 = await client.get_book(书籍编号)
            目录 = await client.get_catalog(书籍编号, toc_id=详情.get("toc_id"))
            if not 目录:
                raise FkzsError("empty_catalog")
            声明数 = 详情.get("chapter_count")
            if isinstance(声明数, int) and not isinstance(声明数, bool) and 声明数 > 0 and 声明数 != len(目录):
                raise FkzsError("incomplete_catalog")
            书籍信息 = 规范化疯狂追书书籍信息(书籍编号, 详情)
            yield 番茄小说.格式化番茄下载提示(书籍信息, len(目录))
            阶段 = "chapters"
            章节结果 = await client.download_all(书籍编号, 目录, toc_id=详情.get("toc_id"))
        阶段 = "txt"
        文件名, 内容 = await asyncio.to_thread(生成疯狂追书小说文件内容, 书籍编号, 书籍信息, 目录, 章节结果)
        路径 = await _写入缓存(文件名, 内容)
        阶段 = "upload"
        上传 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传.get("success"):
            yield 疯狂追书文件发送失败提示
            return
        阶段 = "share"
        发送 = await 小说网盘.发送小说下载完成链接(
            event, 书籍信息["title"], 书籍信息["author"], str(上传.get("share_url") or "")
        )
        if not 发送.get("sent"):
            yield 疯狂追书文件发送失败提示
    except Exception as exc:
        logger.warning(
            "疯狂追书小说处理失败：stage=%s, book_id=%s, error_type=%s, reason=%s, code=%s, http_status=%s",
            阶段, 书籍编号, type(exc).__name__,
            exc.reason if isinstance(exc, FkzsError) else "operation_failed",
            exc.code if isinstance(exc, FkzsError) else None,
            exc.status if isinstance(exc, FkzsError) else None,
        )
        yield 疯狂追书文件发送失败提示 if 阶段 in {"upload", "share"} else 疯狂追书下载失败提示
    finally:
        if 路径 is not None:
            文件缓存工具.删除小说缓存文件(路径)


def 获取疯狂追书小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取疯狂追书来源(event, 命令文本)
    return 生成疯狂追书下载回复流(event, 来源, 配置) if 来源 else None


async def 搜索疯狂追书小说(关键词: str, 数量上限: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        上限 = max(1, min(int(数量上限), 30))
        async with AsyncFkzsClient(concurrency=2) as client:
            搜索 = await client.search(关键词, page=1, page_size=上限)
        return [
            {"platform": "疯狂追书", "book_id": str(书["book_id"]),
             "title": 书["title"], "author": 书.get("author") or "未知", "url": "",
             "word_count": 书.get("word_count"), "chapter_count": 书.get("chapter_count"),
             "intro": 书.get("intro") or "", "score": 书.get("score"), "heat": 书.get("read_num")}
            for 书 in 搜索.get("items", [])[:上限]
            if 提取疯狂追书书籍编号(书.get("book_id")) and 书.get("title")
        ]
    except Exception as exc:
        logger.debug("疯狂追书小说搜索失败：error_type=%s", type(exc).__name__)
        return []
