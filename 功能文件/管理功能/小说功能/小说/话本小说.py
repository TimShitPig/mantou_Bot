"""话本小说分享链接、异步下载和统一 TXT/网盘出口。"""

from __future__ import annotations

import asyncio
import html
import json
import re
from pathlib import Path
from typing import Any, AsyncIterator, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

try:
    from astrbot.api import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.话本接口 import AsyncHuabenClient, HuabenError
from 功能文件.管理功能.小说功能.小说 import 番茄小说
from 功能文件.管理功能.网盘功能 import 小说网盘

话本小说缓存目录 = 文件缓存工具.小说缓存目录
话本下载失败提示 = "下载失败 请重试"
话本文件发送失败提示 = "文件发送失败，请稍后再试"
_链接正则 = re.compile(r"https?://[^\s<>\"']+", re.I)


def 提取话本书籍编号(来源: Any) -> str:
    文本 = html.unescape(str(来源 or "")).replace("\\/", "/").strip()
    try:
        地址 = urlsplit(文本)
        主机 = (地址.hostname or "").lower().rstrip(".")
        if (
            地址.scheme not in {"http", "https"}
            or 地址.username
            or 地址.password
            or not (主机 == "ihuaben.com" or 主机.endswith(".ihuaben.com"))
        ):
            return ""
        匹配 = re.fullmatch(r"/(?:book|list)/(\d{1,15})(?:\.html)?/?", 地址.path, re.I)
        if 匹配:
            return 匹配.group(1)
        查询 = parse_qs(地址.query)
        for 字段 in ("bookId", "bookid", "book_id"):
            候选 = 查询.get(字段, [])
            if len(候选) == 1 and re.fullmatch(r"\d{1,15}", 候选[0]):
                return 候选[0]
    except ValueError:
        pass
    return ""


def _字段(对象: Any, 名称: str) -> Any:
    return 对象.get(名称) if isinstance(对象, Mapping) else getattr(对象, 名称, None)


def _当前输入文本(event: Any, 命令文本: Any) -> list[str]:
    """仅检查本条文字和分享卡片，跳过引用、作者和提及资料。"""
    文本 = [值 for 值 in (命令文本, _字段(event, "message_str")) if isinstance(值, str)]
    队列 = [(event, 0, False)]
    已见: set[int] = set()
    排除 = {"author", "sender", "user", "member", "mentions", "reply", "quote",
            "message_reference", "msg_elements", "quoted_message", "reference"}
    while 队列 and len(已见) < 256:
        当前, 深度, 卡片 = 队列.pop(0)
        if 当前 is None or 深度 > 8 or id(当前) in 已见:
            continue
        已见.add(id(当前))
        if isinstance(当前, str):
            try:
                当前 = json.loads(当前)
            except (ValueError, TypeError):
                if 卡片:
                    文本.append(当前)
                continue
        if isinstance(当前, (list, tuple)):
            队列.extend((子项, 深度 + 1, 卡片) for 子项 in 当前[:128])
            continue
        类型 = _字段(当前, "type")
        类型 = str(getattr(类型, "value", 类型) or "").lower().removeprefix("componenttype.")
        if 类型 in {"reply", "at", "atall", "forward", "node", "nodes"}:
            continue
        if 类型 in {"json", "ark"}:
            队列.append((_字段(当前, "data"), 深度 + 1, True))
            continue
        if 卡片 and isinstance(当前, Mapping):
            队列.extend((值, 深度 + 1, True) for 键, 值 in 当前.items()
                        if str(键).lower() not in 排除 and isinstance(值, (str, dict, list)))
            continue
        for 名称 in ("content", "text"):
            值 = _字段(当前, 名称)
            if isinstance(值, str):
                文本.append(值)
        for 名称 in ("message_obj", "raw_message", "message", "raw_data", "d", "data", "ark"):
            队列.append((_字段(当前, 名称), 深度 + 1, 名称 == "ark"))
    return 文本


def 提取话本来源(event: Any, 命令文本: Any = "") -> str | None:
    for 文本 in _当前输入文本(event, 命令文本):
        for _ in range(3):
            文本 = html.unescape(文本).replace("\\/", "/")
            for 匹配 in _链接正则.finditer(文本):
                链接 = 匹配.group().rstrip("，。；;）)]}>\\")
                if 提取话本书籍编号(链接):
                    return 链接
            文本 = unquote(文本)
    return None


def 规范化话本书籍信息(书籍编号: str, 详情: Mapping[str, Any]) -> dict[str, Any]:
    字数 = 详情.get("word_count")
    if isinstance(字数, bool) or not isinstance(字数, (int, str)) or not re.fullmatch(r"\d+", str(字数)):
        字数文本 = "未知"
    else:
        字数文本 = f"{int(字数):,}字" if int(字数) > 0 else "未知"
    状态 = str(详情.get("serial_state_text") or "")
    return {
        "title": str(详情.get("book_name") or f"话本小说{书籍编号}"),
        "author": str(详情.get("author_name") or "未知"),
        "status": "完结" if 状态 in {"完结", "已完结", "完本"} else "连载",
        "word_count": 字数文本,
        "intro": str(详情.get("intro") or "").strip(),
    }


def 生成话本小说文件内容(
    书籍编号: str, 书籍信息: dict[str, Any],
    目录: list[dict[str, Any]], 章节结果: list[dict[str, Any]],
) -> tuple[str, bytes]:
    """先确认全量成功，再直接复用番茄的文件名、声明、头部和编码。"""
    if not 目录 or len(目录) != len(章节结果):
        raise HuabenError("incomplete_chapters")
    输出 = []
    for 序号, (章节, 结果) in enumerate(zip(目录, 章节结果), 1):
        if (
            str(章节.get("chapter_id")) != str(结果.get("chapter_id"))
            or str(结果.get("book_id")) != str(书籍编号)
            or not str(结果.get("text") or "").strip()
        ):
            raise HuabenError("invalid_chapter")
        标题 = 结果.get("title") or 章节.get("title") or f"第{序号}章"
        if not 番茄小说.去除章节正文重复标题(标题, 结果["text"]).strip():
            raise HuabenError("empty_chapter")
        输出.append({"index": 序号, "title": 标题, "content": 结果["text"], "success": True})
    return 番茄小说.生成番茄小说文件内容(书籍编号, 书籍信息, 目录, 输出)


def 写入话本下载缓存文件(文件名: str, 内容: bytes) -> Path:
    话本小说缓存目录.mkdir(parents=True, exist_ok=True)
    安全名称 = Path(番茄小说.清理番茄文件名(文件名)).name
    if not 安全名称.lower().endswith(".txt"):
        安全名称 += ".txt"
    路径 = 话本小说缓存目录 / 安全名称
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
    任务 = asyncio.create_task(asyncio.to_thread(写入话本下载缓存文件, 文件名, 内容))
    try:
        return await asyncio.shield(任务)
    except asyncio.CancelledError:
        # 等待正在写入的文件完成并释放，避免取消后留下无人持有的占用标记。
        try:
            路径 = await 任务
            文件缓存工具.删除小说缓存文件(路径)
        finally:
            raise


async def 生成话本下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取话本书籍编号(来源)
    if not 书籍编号:
        yield 话本下载失败提示
        return
    阶段 = "metadata"
    路径: Path | None = None
    try:
        async with AsyncHuabenClient(concurrency=400) as client:
            结果 = await asyncio.gather(client.get_book(书籍编号), client.get_catalog(书籍编号),
                                       return_exceptions=True)
            for 项 in 结果:
                if isinstance(项, BaseException):
                    raise 项
            详情, 目录 = 结果
            if not 目录:
                raise HuabenError("empty_catalog")
            声明数 = 详情.get("chapter_count")
            if isinstance(声明数, int) and not isinstance(声明数, bool) and 声明数 > 0 and 声明数 != len(目录):
                raise HuabenError("incomplete_catalog")
            书籍信息 = 规范化话本书籍信息(书籍编号, 详情)
            yield 番茄小说.格式化番茄下载提示(书籍信息, len(目录))
            阶段 = "chapters"
            章节结果 = await client.download_all(书籍编号, 目录)
        阶段 = "txt"
        文件名, 内容 = await asyncio.to_thread(生成话本小说文件内容, 书籍编号, 书籍信息, 目录, 章节结果)
        路径 = await _写入缓存(文件名, 内容)
        阶段 = "upload"
        上传 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传.get("success"):
            yield 话本文件发送失败提示
            return
        阶段 = "share"
        发送 = await 小说网盘.发送小说下载完成链接(event, 书籍信息["title"], 书籍信息["author"],
                                                 str(上传.get("share_url") or ""))
        if not 发送.get("sent"):
            yield str(发送.get("fallback_text") or 话本文件发送失败提示)
    except Exception as exc:
        logger.warning("话本小说处理失败：stage=%s, book_id=%s, error_type=%s, reason=%s, code=%s, http_status=%s",
                       阶段, 书籍编号, type(exc).__name__,
                       exc.reason if isinstance(exc, HuabenError) else "operation_failed",
                       exc.code if isinstance(exc, HuabenError) else None,
                       exc.status if isinstance(exc, HuabenError) else None)
        yield 话本文件发送失败提示 if 阶段 in {"upload", "share"} else 话本下载失败提示
    finally:
        # 统一清理函数会保留等待续传的上传任务，不另开后台备份。
        if 路径 is not None:
            文件缓存工具.删除小说缓存文件(路径)


def 获取话本小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取话本来源(event, 命令文本)
    return 生成话本下载回复流(event, 来源, 配置) if 来源 else None


async def 搜索话本小说(关键词: str, 数量上限: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        上限 = max(1, min(int(数量上限), 30))
        async with AsyncHuabenClient(concurrency=2) as client:
            搜索 = await client.search(关键词, page=1, page_size=上限)
        return [{"platform": "话本", "book_id": str(书["book_id"]),
                 "title": 书["book_name"], "author": 书.get("author_name") or "未知",
                 "url": f"https://www.ihuaben.com/book/{书['book_id']}.html",
                 "word_count": 书.get("word_count"), "chapter_count": 书.get("chapter_count"),
                 "intro": 书.get("intro") or ""}
                for 书 in 搜索.get("items", [])[:上限]
                if str(书.get("book_id") or "").isdigit() and 书.get("book_name")]
    except Exception as exc:
        logger.debug("话本小说搜索失败：error_type=%s", type(exc).__name__)
        return []
