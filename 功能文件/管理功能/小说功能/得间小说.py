from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, AsyncIterator

from astrbot.api import logger

try:
    from 功能文件.管理功能.网盘功能 import UC网盘
except Exception as exc:
    UC网盘 = None
    logger.warning(f"UC网盘模块加载失败：error={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={exc}")

from 功能文件.管理功能.小说功能 import _得间源码 as 得间源码

下载缓存目录 = Path(__file__).resolve().parents[2] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
章节并发数 = 8
进度日志分段数 = 10
得间域名正则 = re.compile(r"palmestore\.com|zhangyue\.com|ireader\.com|dejian", re.I)
链接正则 = re.compile(r"https?://[^\s'\"<>]+", re.I)
书籍编号正则 = re.compile(r"(?:bid|book[_-]?id|bookId)=(\d{5,})", re.I)
路径编号正则 = re.compile(r"/(?:book|detail|books?)/(\d{5,})", re.I)


def 获取得间小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取直接得间来源(命令文本) or 提取事件得间来源(event)
    if 来源 is None:
        return None
    return 生成下载回复流(event, 来源, 配置)


async def 生成下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取书籍编号(来源)
    if not 书籍编号:
        yield "下载失败"
        return
    try:
        详情包 = await asyncio.to_thread(得间源码.get_book_detail, 书籍编号)
        if not 详情包.get("success"):
            logger.warning(f"得间小说详情失败：book_id={书籍编号}")
            yield "下载失败"
            return
        详情 = 详情包.get("detail") or {}
        目录包 = await asyncio.to_thread(得间源码.get_chapter_catalog, 书籍编号)
        目录 = 目录包.get("chapters") or []
        if not 目录:
            logger.warning(f"得间小说目录失败：book_id={书籍编号}")
            yield "下载失败"
            return

        书名 = str(详情.get("title") or "未知")
        作者 = str(详情.get("author") or "未知")
        状态 = "完结" if "完结" in str(详情.get("status") or "") else "连载"
        字数 = 格式化字数(详情.get("word_count"))
        logger.info(f"得间小说开始下载：book_id={书籍编号}, title={书名}, author={作者}, chapters={len(目录)}")
        yield "\n".join([
            f"书名：{书名}",
            f"作者：{作者}",
            f"状态：{状态}",
            f"章节：{len(目录)} 章",
            f"字数：{字数}",
            "",
            "正在下载中请稍等.....",
        ])

        章节结果 = await 下载全部章节(书籍编号, 目录)
        成功 = [x for x in 章节结果 if x.get("content")]
        if not 成功:
            logger.warning(f"得间小说下载失败：book_id={书籍编号}, success=0, total={len(目录)}")
            yield "下载失败"
            return

        文件名, 文件内容 = 生成小说文件(书籍编号, 书名, 作者, 状态, 字数, 章节结果)
        发送结果 = await 准备发送文本文件(event, 文件名, 文件内容, 配置, 书名=书名, 作者=作者)
        if 发送结果.get("sent"):
            启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        降级 = str(发送结果.get("fallback_text") or "")
        if 降级:
            try:
                yield 降级
            finally:
                启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        logger.warning(f"得间小说完成消息发送失败：book_id={书籍编号}, error={发送结果.get('error')}")
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(f"得间小说下载失败：source={来源}, error={exc}")
        yield "下载失败"


async def 下载全部章节(书籍编号: str, 目录: list[dict[str, Any]]) -> list[dict[str, str]]:
    总数 = len(目录)
    结果: list[dict[str, str] | None] = [None] * 总数
    信号量 = asyncio.Semaphore(章节并发数)
    完成 = 0
    成功 = 0

    async def 拉一章(下标: int, 章: dict[str, Any]) -> None:
        nonlocal 完成, 成功
        cid = int(章.get("id") or 章.get("chapter_id") or 0)
        标题 = str(章.get("title") or 章.get("cn") or f"第{cid}章")
        正文 = ""
        async with 信号量:
            if cid > 0:
                try:
                    正文 = await asyncio.to_thread(得间源码.get_chapter_text, 书籍编号, cid)
                except Exception as exc:
                    logger.warning(f"得间章节下载失败：book_id={书籍编号}, chapter_id={cid}, error={exc}")
                    正文 = ""
        结果[下标] = {"title": 标题, "content": str(正文 or "").strip(), "id": str(cid)}
        完成 += 1
        if 正文:
            成功 += 1
        if 完成 == 1 or 完成 == 总数 or 完成 % max(1, 总数 // 进度日志分段数) == 0:
            logger.info(
                f"得间小说章节进度：book_id={书籍编号}, progress={完成}/{总数}, "
                f"percent={int(完成 * 100 / max(总数, 1))}%, success={成功}, failed={完成 - 成功}"
            )

    await asyncio.gather(*(拉一章(i, 章) for i, 章 in enumerate(目录)))
    return [x for x in 结果 if x is not None]


def 生成小说文件(书籍编号: str, 书名: str, 作者: str, 状态: str, 字数: str, 章节结果: list[dict[str, str]]) -> tuple[str, bytes]:
    文件名 = f"[{状态}]书名：{清理文件名(书名)} 作者：{清理文件名(作者)}.txt"
    行 = [文件声明, "", f"名称：{书名}", f"作者：{作者}", f"状态：{状态}", f"字数：{字数}", f"书籍ID：{书籍编号}", f"章节数：{len(章节结果)}", ""]
    for 章 in 章节结果:
        if not 章.get("content"):
            continue
        行.extend([章.get("title") or "章节", "", 章["content"], ""])
    return 文件名, "\n".join(行).encode("utf-8")


async def 准备发送文本文件(event: Any, 文件名: str, 文件内容: bytes, 配置: Any = None, *, 书名: Any = "", 作者: Any = "") -> dict[str, Any]:
    缓存路径 = 写入缓存(文件名, 文件内容)
    if UC网盘 is None:
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "UC网盘模块未加载"}
    try:
        UC结果 = await UC网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not UC结果.get("success"):
            删除缓存(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(UC结果.get("error") or "UC网盘未启用")}
        完成结果 = await UC网盘.发送小说下载完成链接(event, 书名, 作者, str(UC结果.get("share_url") or ""))
        if 完成结果:
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        return {"sent": False, "fallback_text": "", "source_cache_path": 缓存路径, "error": "完成消息发送失败"}
    except Exception as exc:
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(exc)}


def 启动百度后台上传并清理(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    async def _任务() -> None:
        try:
            if 百度网盘 is not None and 源缓存路径:
                await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
        except Exception as exc:
            logger.warning(f"得间小说百度后台上传异常：file={文件名}, error={exc}")
        finally:
            删除缓存(源缓存路径)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_任务())
    except Exception:
        删除缓存(源缓存路径)


def 写入缓存(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 下载缓存目录 / 文件名
    序号 = 1
    while 路径.exists():
        路径 = 下载缓存目录 / f"{Path(文件名).stem}_{序号}.txt"
        序号 += 1
    路径.write_bytes(文件内容)
    return 路径


def 删除缓存(缓存路径: Any) -> None:
    try:
        if 缓存路径:
            Path(缓存路径).unlink(missing_ok=True)
    except Exception:
        pass


def 提取直接得间来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or "")
    if not 得间域名正则.search(文本):
        return None
    m = 链接正则.search(文本)
    return m.group(0) if m else 文本.strip() or None


def 提取事件得间来源(event: Any) -> str | None:
    for 字段 in ("message_str", "message", "raw_message"):
        值 = getattr(event, 字段, None)
        if 值 is None:
            continue
        来源 = 提取直接得间来源(str(值))
        if 来源:
            return 来源
    return None


def 提取书籍编号(来源: str) -> str:
    文本 = str(来源 or "")
    for 正则 in (书籍编号正则, 路径编号正则):
        m = 正则.search(文本)
        if m:
            return m.group(1)
    m = re.search(r"(\d{6,})", 文本)
    return m.group(1) if m else ""


def 格式化字数(字数: Any) -> str:
    文本 = str(字数 or "").strip()
    if not 文本:
        return "未知"
    if "字" in 文本:
        return 文本
    if 文本.isdigit():
        n = int(文本)
        return f"{round(n/10000, 1)}万字" if n >= 10000 else f"{n}字"
    return 文本


def 清理文件名(文件名: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", str(文件名 or "")).strip() or "未知"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    try:
        数据 = await asyncio.to_thread(得间源码.search_books, 关键词, 1, max(需要数量, 20))
    except Exception as exc:
        logger.warning(f"得间搜索失败：keyword={关键词}, error={exc}")
        return []
    结果 = []
    for item in 数据.get("results") or []:
        book_id = str(item.get("book_id") or "").strip()
        if not book_id:
            continue
        结果.append({
            "title": item.get("title") or "未知",
            "author": item.get("author") or "未知",
            "book_id": book_id,
            "platform": "得间",
            "url": f"https://dj.palmestore.com/zybk/api/detail/index?bid={book_id}",
            "heat": 0,
            "score": 0,
        })
        if len(结果) >= 需要数量:
            break
    return 结果