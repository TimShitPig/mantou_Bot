from __future__ import annotations

import asyncio
import html
import json
import re
import urllib.parse
from typing import Any, AsyncIterator

import aiohttp
from astrbot.api import logger

try:
    from 功能文件.API功能.OIAPI import 番茄小说 as 番茄输出
except Exception as 异常:
    番茄输出 = None
    logger.warning(f"QQ阅读析API输出模块加载失败：error={异常}")


QQ阅读详情地址 = "https://h5.reader.qq.com/9/intro"
QQ阅读目录地址 = "https://ubook.reader.qq.com/api/book/chapter-list"
QQ阅读正文地址 = "http://154.12.91.167:7000/content"
QQ阅读正文批量章节数 = 50
QQ阅读正文并发数 = 10
QQ阅读正文最大请求次数 = 3
QQ阅读正文重试基础等待秒数 = 1
进度分段数 = 10
QQ阅读来源正则 = re.compile("reader\\.qq\\.com|book\\.qq\\.com|novel\\.html5\\.qq\\.com|154\\.12\\.91\\.167:7000", re.IGNORECASE)
链接正则 = re.compile("https?://[^\\s'\"<>\\u3001\\uff0c\\u3002]+", re.IGNORECASE)


def 获取QQ阅读回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取直接QQ阅读来源(命令文本) or 提取事件QQ阅读来源(event)
    if 来源 is None:
        return None
    return 生成QQ阅读下载回复流(event, 来源, 配置)


async def 生成QQ阅读下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = ""
    书籍信息: dict[str, Any] = {}
    章节列表: list[dict[str, Any]] = []
    章节结果列表: list[dict[str, Any]] = []
    成功章节列表: list[dict[str, Any]] = []
    文件名 = ""
    已发送 = False
    发送错误 = ""
    try:
        if 番茄输出 is None:
            logger.warning("QQ阅读下载失败：番茄输出模块不可用")
            yield "下载失败"
            return
        超时 = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=120)
        async with aiohttp.ClientSession(timeout=超时, headers={"User-Agent": "Mozilla/5.0"}) as 会话:
            准备结果 = await 准备QQ阅读小说(会话, 来源)
            if not 准备结果.get("success"):
                logger.warning(
                    f"QQ阅读析API准备失败：source={限制文本长度(来源)}, "
                    f"error={限制文本长度(准备结果.get('error') or '析API准备失败', 500)}"
                )
                yield "下载失败"
                return
            书籍编号 = str(准备结果.get("book_id") or "")
            书籍信息 = 准备结果.get("book_info") or QQ阅读默认书籍信息(书籍编号)
            章节列表 = 准备结果.get("chapters") or []
            logger.info(
                f"QQ阅读开始下载：source=析API, book_id={书籍编号}, "
                f"title={书籍信息.get('title')}, author={书籍信息.get('author')}, chapters={len(章节列表)}"
            )
            yield 番茄输出.格式化下载提示(书籍信息, len(章节列表))
            章节结果列表 = await 下载QQ阅读全部章节(会话, 书籍编号, 章节列表)
            成功章节列表 = [项目 for 项目 in 章节结果列表 if 项目.get("success")]
            if not 成功章节列表 or len(成功章节列表) < len(章节列表):
                yield "下载失败"
                return
            文件名, 文件内容 = 番茄输出.构造TXT文件(书籍编号, 书籍信息, 章节列表, 章节结果列表)
            logger.info(
                f"QQ阅读章节下载完成：book_id={书籍编号}, title={书籍信息.get('title')}, "
                f"success={len(成功章节列表)}, total={len(章节列表)}, file_size={len(文件内容)}"
            )
            发送结果 = await 番茄输出.准备发送文本文件(event, 文件名, 文件内容, 配置)
            缓存路径 = 发送结果.get("cache_path")
            链式结果 = 发送结果.get("chain_result")
            if 链式结果 is not None:
                try:
                    yield 链式结果
                finally:
                    番茄输出.延迟删除缓存文件(缓存路径)
                return
            已发送 = bool(发送结果.get("sent"))
            发送错误 = str(发送结果.get("error") or "")
    except Exception as 异常:
        logger.warning(f"QQ阅读下载失败：source={限制文本长度(来源)}, book_id={书籍编号}, error={异常}")
        yield "下载失败"
        return
    if 已发送:
        return
    logger.warning(
        f"QQ阅读文件发送失败：book_id={书籍编号}, file={文件名}, "
        f"success={len(成功章节列表)}/{len(章节列表)}, error={发送错误}"
    )
    yield "文件发送失败，请稍后再试"


async def 准备QQ阅读小说(会话: aiohttp.ClientSession, 来源: str, 书籍编号: str = "") -> dict[str, Any]:
    来源信息 = 解析QQ阅读来源(来源)
    实际书籍编号 = 清理文本(书籍编号) or 来源信息.get("book_id", "")
    if not 实际书籍编号:
        return {"success": False, "error": "QQ阅读析API没有识别到书籍ID"}

    详情响应 = await 请求QQ阅读详情(会话, 实际书籍编号)
    目录响应 = await 请求QQ阅读目录(会话, 实际书籍编号)
    书籍信息 = 合并QQ阅读书籍信息(QQ阅读默认书籍信息(实际书籍编号), 从QQ阅读详情提取书籍信息(详情响应))
    章节列表 = 提取QQ阅读目录(目录响应) or 提取QQ阅读目录(详情响应)

    起始章 = 安全整数(来源信息.get("start")) or 1
    结束章 = 安全整数(来源信息.get("end"))
    if 结束章 > 0:
        if 章节列表:
            章节列表 = [章节 for 章节 in 章节列表 if 起始章 <= 安全整数(章节.get("index")) <= 结束章]
        else:
            章节列表 = 构造QQ阅读目录(实际书籍编号, 起始章, 结束章)
    if not 章节列表:
        总章节 = 安全整数(书籍信息.get("chapter_count"))
        if 总章节 > 0:
            章节列表 = 构造QQ阅读目录(实际书籍编号, 1, 总章节)
    if not 章节列表:
        return {"success": False, "error": "QQ阅读析API没有获取到章节目录"}

    章节列表 = sorted(章节列表, key=lambda 项目: 安全整数(项目.get("index")))
    书籍信息 = 合并QQ阅读书籍信息(书籍信息, {"chapter_count": len(章节列表)})
    logger.info(f"QQ阅读析API准备完成：book_id={实际书籍编号}, title={书籍信息.get('title')}, chapters={len(章节列表)}")
    return {"success": True, "book_id": 实际书籍编号, "book_info": 书籍信息, "chapters": 章节列表, "chapter_results": []}


async def 下载QQ阅读全部章节(会话: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]]) -> list[dict[str, Any]]:
    总数 = len(目录)
    if 总数 <= 0:
        return []
    已完成 = 0
    成功数 = 0
    上一进度段 = 0
    分批列表 = [(序号, 目录[起点:起点 + QQ阅读正文批量章节数]) for 序号, 起点 in enumerate(range(0, 总数, QQ阅读正文批量章节数))]
    分批结果: dict[int, list[dict[str, Any]]] = {}
    信号量 = asyncio.Semaphore(QQ阅读正文并发数)
    logger.info(
        f"QQ阅读析API章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%, "
        f"batch_size={QQ阅读正文批量章节数}, concurrency={QQ阅读正文并发数}"
    )

    def 记录进度(批次结果: list[dict[str, Any]]) -> None:
        nonlocal 已完成, 成功数, 上一进度段
        已完成 += len(批次结果)
        成功数 += sum(1 for 项目 in 批次结果 if 项目.get("success"))
        进度段 = 进度分段数 if 已完成 >= 总数 else int(已完成 * 进度分段数 / 总数)
        if 进度段 <= 上一进度段 and 已完成 < 总数:
            return
        上一进度段 = 进度段
        百分比 = int(已完成 * 100 / 总数) if 总数 else 100
        logger.info(f"QQ阅读析API章节进度：book_id={书籍编号}, progress={已完成}/{总数}, percent={百分比}%, success={成功数}")

    async def 下载分批(序号: int, 批次: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        async with 信号量:
            return 序号, await 下载QQ阅读章节批次(会话, 书籍编号, 批次)

    任务列表 = [asyncio.create_task(下载分批(序号, 批次)) for 序号, 批次 in 分批列表]
    try:
        for 已完成任务 in asyncio.as_completed(任务列表):
            序号, 批次结果 = await 已完成任务
            分批结果[序号] = 批次结果
            记录进度(批次结果)
    except Exception:
        for 任务 in 任务列表:
            if not 任务.done():
                任务.cancel()
        raise

    结果列表: list[dict[str, Any]] = []
    for 序号, _批次 in 分批列表:
        结果列表.extend(分批结果.get(序号, []))
    if 成功数 != 总数:
        raise RuntimeError(f"QQ阅读析API章节正文不完整：成功 {成功数}/{总数}")
    return 结果列表


async def 下载QQ阅读章节批次(会话: aiohttp.ClientSession, 书籍编号: str, 批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 批次:
        return []
    起始章 = 安全整数(批次[0].get("index"))
    结束章 = 安全整数(批次[-1].get("index"))
    try:
        return await 重试下载QQ阅读章节批次(会话, 书籍编号, 批次)
    except Exception as 异常:
        if len(批次) <= 1:
            raise
        logger.warning(
            f"QQ阅读析API整批正文失败，改用单章重试：book_id={书籍编号}, "
            f"range={起始章}-{结束章}, error={异常}"
        )
    单章结果: list[dict[str, Any]] = []
    for 章节 in 批次:
        单章结果.extend(await 重试下载QQ阅读章节批次(会话, 书籍编号, [章节]))
    return 单章结果


async def 重试下载QQ阅读章节批次(会话: aiohttp.ClientSession, 书籍编号: str, 批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
    起始章 = 安全整数(批次[0].get("index"))
    结束章 = 安全整数(批次[-1].get("index"))
    最后异常: Exception | None = None
    for 请求次数 in range(1, QQ阅读正文最大请求次数 + 1):
        try:
            return await 下载一次QQ阅读章节批次(会话, 书籍编号, 批次)
        except Exception as 异常:
            最后异常 = 异常
            if 请求次数 >= QQ阅读正文最大请求次数:
                break
            等待秒数 = QQ阅读正文重试基础等待秒数 * 请求次数
            logger.warning(
                f"QQ阅读析API正文请求失败，准备重试：book_id={书籍编号}, "
                f"range={起始章}-{结束章}, attempt={请求次数}/{QQ阅读正文最大请求次数}, "
                f"wait={等待秒数}s, error={异常}"
            )
            await asyncio.sleep(等待秒数)
    raise RuntimeError(f"QQ阅读析API正文请求失败，已重试{QQ阅读正文最大请求次数}次：{最后异常}") from 最后异常


async def 下载一次QQ阅读章节批次(会话: aiohttp.ClientSession, 书籍编号: str, 批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
    起始章 = 安全整数(批次[0].get("index"))
    结束章 = 安全整数(批次[-1].get("index"))
    正文列表 = await 请求QQ阅读正文批次(会话, 书籍编号, 起始章, 结束章)
    if len(正文列表) < len(批次):
        raise RuntimeError(f"QQ阅读析API章节正文不完整：book_id={书籍编号}, range={起始章}-{结束章}, got={len(正文列表)}, expected={len(批次)}")
    批次结果: list[dict[str, Any]] = []
    for 位置, 章节 in enumerate(批次):
        标题, 正文 = 提取QQ阅读正文和标题(正文列表[位置], 清理文本(章节.get("title")))
        批次结果.append({**章节, "title": 标题 or f"第{章节.get('index')}章", "content": 正文, "success": bool(正文)})
    空章节 = [str(章节.get("index")) for 章节 in 批次结果 if not 章节.get("success")]
    if 空章节:
        raise RuntimeError(f"QQ阅读析API章节正文为空：book_id={书籍编号}, range={起始章}-{结束章}, empty={','.join(空章节[:20])}")
    return 批次结果


async def 请求QQ阅读详情(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    try:
        async with 会话.get(QQ阅读详情地址, params={"bid": 书籍编号}, timeout=20) as 响应:
            文本 = await 响应.text()
            if 响应.status >= 400:
                logger.debug(f"QQ阅读析API详情HTTP错误：book_id={书籍编号}, status={响应.status}")
                return {}
            return json.loads(文本)
    except Exception as 异常:
        logger.debug(f"QQ阅读析API详情请求失败：book_id={书籍编号}, error={异常}")
        return {}


async def 请求QQ阅读目录(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    try:
        async with 会话.get(QQ阅读目录地址, params={"bid": 书籍编号}, timeout=30) as 响应:
            文本 = await 响应.text()
            if 响应.status >= 400:
                logger.debug(f"QQ阅读析API目录HTTP错误：book_id={书籍编号}, status={响应.status}")
                return {}
            return json.loads(文本)
    except Exception as 异常:
        logger.debug(f"QQ阅读析API目录请求失败：book_id={书籍编号}, error={异常}")
        return {}


async def 请求QQ阅读正文批次(会话: aiohttp.ClientSession, 书籍编号: str, 起始章: int, 结束章: int) -> list[Any]:
    async with 会话.get(QQ阅读正文地址, params={"bookid": 书籍编号, "s": 起始章, "e": 结束章}, timeout=120) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"QQ阅读析API HTTP {响应.status}: {限制文本长度(文本, 120)}")
        try:
            数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f"QQ阅读析API JSON解析失败：{限制文本长度(文本, 120)}") from 异常
    if not isinstance(数据, dict):
        raise RuntimeError("QQ阅读析API返回格式不是对象")
    if str(数据.get("code")) not in ("0", "200"):
        raise RuntimeError(f"QQ阅读析API返回失败：{限制文本长度(数据.get('msg') or 数据.get('message') or 数据, 200)}")
    正文列表 = 数据.get("data")
    if isinstance(正文列表, list):
        return 正文列表
    if isinstance(正文列表, dict):
        return [正文列表.get(str(序号)) or 正文列表.get(序号) or "" for 序号 in range(起始章, 结束章 + 1)]
    raise RuntimeError("QQ阅读析API返回格式缺少正文列表")


def 提取直接QQ阅读来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None
    return 提取QQ阅读来源(文本) or None


def 提取事件QQ阅读来源(event: Any) -> str | None:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            来源 = 提取QQ阅读来源(读取字段(对象, 字段名))
            if 来源:
                return 来源
    return None


def 提取QQ阅读来源(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, (list, tuple, set)):
        for 项目 in 值:
            来源 = 提取QQ阅读来源(项目)
            if 来源:
                return 来源
        return ""
    if isinstance(值, dict):
        for 项目 in 值.values():
            来源 = 提取QQ阅读来源(项目)
            if 来源:
                return 来源
        return ""
    原始文本 = str(值 or "")
    for 文本 in 生成文本变体(原始文本):
        for 匹配 in 链接正则.finditer(文本):
            链接 = 匹配.group(0).rstrip("),.;]`")
            if QQ阅读来源正则.search(链接) and 解析QQ阅读来源(链接).get("book_id"):
                return 链接
        if QQ阅读来源正则.search(文本) and 解析QQ阅读来源(文本).get("book_id"):
            return 文本
    return ""


def 解析QQ阅读来源(文本: str) -> dict[str, Any]:
    for 候选路径 in 生成文本变体(str(文本 or "")):
        候选路径 = 候选路径.strip()
        if not QQ阅读来源正则.search(候选路径):
            continue
        try:
            解析结果 = urllib.parse.urlsplit(候选路径)
            查询参数 = dict(urllib.parse.parse_qsl(解析结果.query, keep_blank_values=True))
        except Exception:
            查询参数 = {}
        书籍编号 = 清理文本(查询参数.get("bid") or 查询参数.get("bookid") or 查询参数.get("bookId") or 查询参数.get("book_id"))
        if not 书籍编号:
            匹配 = re.search("(?:bid|bookid|bookId|book_id)=(\\d{5,15})", 候选路径, re.IGNORECASE)
            if 匹配:
                书籍编号 = 匹配.group(1)
        if not 书籍编号:
            匹配 = re.search("book\\.qq\\.com/book-detail/(\\d{5,15})", 候选路径, re.IGNORECASE)
            if 匹配:
                书籍编号 = 匹配.group(1)
        if not 书籍编号:
            continue
        起始章 = 安全整数(查询参数.get("s") or 查询参数.get("start") or 查询参数.get("startSeq")) or 1
        结束章 = 安全整数(查询参数.get("e") or 查询参数.get("end") or 查询参数.get("endSeq"))
        return {"book_id": 书籍编号, "start": 起始章, "end": 结束章}
    return {}


def 构造QQ阅读目录(书籍编号: str, 起始章: int, 结束章: int) -> list[dict[str, Any]]:
    起始章 = max(1, 安全整数(起始章) or 1)
    结束章 = 安全整数(结束章)
    if 结束章 < 起始章:
        return []
    return [{"id": str(序号), "title": f"第{序号}章", "index": 序号} for 序号 in range(起始章, 结束章 + 1)]


def QQ阅读默认书籍信息(书籍编号: str) -> dict[str, Any]:
    return {"book_id": 书籍编号, "title": f"QQ阅读{书籍编号}", "author": "未知", "status": "未知", "word_count": "未知", "chapter_count": 0}


def 合并QQ阅读书籍信息(基础信息: dict[str, Any], 新增信息: dict[str, Any]) -> dict[str, Any]:
    结果 = dict(基础信息 or {})
    for 键, 值 in (新增信息 or {}).items():
        if 键 == "title":
            值 = 清理书名(值)
        elif 键 == "intro":
            值 = 清理简介(值)
        if 值 in (None, "", 0):
            continue
        当前值 = 结果.get(键)
        if 当前值 in (None, "", 0, "未知") or (键 == "title" and str(当前值).startswith("QQ阅读")):
            结果[键] = 值
    return 结果


def 从QQ阅读详情提取书籍信息(数据: Any) -> dict[str, Any]:
    if not isinstance(数据, dict):
        return {}
    书籍 = 数据.get("book") if isinstance(数据.get("book"), dict) else 数据
    完结值 = 读取任意字段(书籍, ("finished", "isFinished", "complete", "status"))
    状态 = "完结" if str(完结值).strip().lower() in ("1", "true", "finished", "complete") else "连载" if str(完结值).strip().lower() in ("0", "false", "serial") else ""
    return {
        "title": 清理书名(读取任意字段(书籍, ("title", "bookName", "book_name", "name"))),
        "author": 清理文本(读取任意字段(书籍, ("author", "authorName", "author_name"))),
        "word_count": 格式化字数(读取任意字段(书籍, ("totalWords", "total_words", "wordCount", "word_count"))),
        "status": 状态,
        "chapter_count": 安全整数(读取任意字段(书籍, ("lastChapter", "chapterCount", "chapter_count", "chapterNum", "chapter_num"))),
        "intro": 清理简介(读取任意字段(书籍, ("intro", "description", "summary"))),
    }


def 提取QQ阅读目录(数据: Any) -> list[dict[str, Any]]:
    if not isinstance(数据, dict):
        return []
    候选列表: list[Any] = []
    if isinstance(数据.get("chapters"), list):
        候选列表 = 数据.get("chapters") or []
    数据项 = 数据.get("data")
    if not 候选列表 and isinstance(数据项, dict) and isinstance(数据项.get("chapters"), list):
        候选列表 = 数据项.get("chapters") or []
    if not 候选列表 and isinstance(数据项, list):
        候选列表 = 数据项
    结果: list[dict[str, Any]] = []
    已见: set[int] = set()
    for 位置, 项目 in enumerate(候选列表, start=1):
        if not isinstance(项目, dict):
            continue
        序号 = 安全整数(读取任意字段(项目, ("seq", "index", "chapter", "chapterSeq", "chapter_seq"))) or 位置
        if 序号 in 已见:
            continue
        已见.add(序号)
        标题 = 清理文本(读取任意字段(项目, ("title", "chapterTitle", "chapter_title", "name"))) or f"第{序号}章"
        结果.append({"id": str(序号), "title": 标题, "index": 序号})
    return sorted(结果, key=lambda 项目: 安全整数(项目.get("index")))


def 提取QQ阅读正文和标题(原始正文: Any, 默认标题: str = "") -> tuple[str, str]:
    if isinstance(原始正文, dict):
        标题 = 清理文本(读取任意字段(原始正文, ("title", "chapterTitle", "chapter_title", "name"))) or 默认标题
        正文 = 清理正文(读取任意字段(原始正文, ("content", "text", "body")) or "")
    else:
        标题 = 默认标题
        正文 = 清理正文(原始正文)
    行列表 = [行.strip() for 行 in 正文.splitlines()]
    while 行列表 and not 行列表[0]:
        行列表.pop(0)
    if 行列表:
        首行 = 行列表[0].strip()
        if not 标题 and re.match("第\\s*\\d+\\s*[章节回卷].*", 首行):
            标题 = 首行
            行列表 = 行列表[1:]
        elif 标题 and 规范化标题比较文本(首行) == 规范化标题比较文本(标题):
            行列表 = 行列表[1:]
        正文 = "\n".join(行列表).strip()
    return 标题 or 默认标题, 正文


def 生成文本变体(文本: str) -> list[str]:
    文本 = html.unescape(str(文本 or "")).replace("\\/", "/")
    变体列表 = [文本]
    for _ in range(2):
        解码文本 = urllib.parse.unquote(变体列表[-1])
        if 解码文本 == 变体列表[-1]:
            break
        变体列表.append(解码文本)
    return 变体列表


def 格式化字数(值: Any) -> str:
    文本 = str(值 or "").strip().replace(" ", "")
    if not 文本:
        return ""
    if "字" in 文本:
        return 文本
    字数 = 解析字数(文本)
    if 字数 <= 0:
        return 文本
    if 字数 >= 100000000:
        return f"{round(字数 / 100000000, 1):g}亿字"
    if 字数 >= 10000:
        return f"{round(字数 / 10000, 1):g}万字"
    return f"{字数}字"


def 解析字数(值: Any) -> int:
    匹配 = re.search("([\\d.]+)", str(值 or "").strip().replace(" ", ""))
    if not 匹配:
        return 0
    数字 = float(匹配.group(1))
    文本 = str(值 or "")
    if "亿" in 文本:
        数字 *= 100000000
    elif "万" in 文本:
        数字 *= 10000
    return int(数字)


def 清理正文(文本: Any) -> str:
    文本 = str(文本 or "").replace("\\n", "\n").replace("\\/", "/")
    文本 = re.sub("<script\\b.*?</script>", "", 文本, flags=re.IGNORECASE | re.DOTALL)
    文本 = re.sub("<style\\b.*?</style>", "", 文本, flags=re.IGNORECASE | re.DOTALL)
    文本 = re.sub("<br\\s*/?>", "\n", 文本, flags=re.IGNORECASE)
    文本 = re.sub("</(?:p|div|section|article|h[1-6])>", "\n\n", 文本, flags=re.IGNORECASE)
    文本 = 清理文本(文本).replace("\r", "")
    文本 = re.sub("[ \\t]+\\n", "\n", 文本)
    文本 = re.sub("\\n[ \\t]+", "\n", 文本)
    文本 = re.sub("\\n{3,}", "\n\n", 文本)
    return 文本.strip()


def 清理文本(文本: Any) -> str:
    文本 = re.sub("<[^>]+>", "", str(文本 or ""))
    return html.unescape(文本).strip()


def 清理书名(文本: Any) -> str:
    return 清理文本(文本).strip(" _-｜|")


def 清理简介(文本: Any) -> str:
    简介 = 清理文本(str(文本 or "").replace("\\n", "\n").replace("\\/", "/"))
    简介 = re.sub("[ \t]+", " ", 简介)
    简介 = re.sub("\n{3,}", "\n\n", 简介)
    return 简介.strip()


def 规范化标题比较文本(文本: Any) -> str:
    return re.sub("\\s+", "", 清理文本(文本)).strip()


def 安全整数(值: Any) -> int:
    if 值 in (None, "") or isinstance(值, bool):
        return 0
    try:
        return max(0, int(float(str(值).strip())))
    except Exception:
        匹配 = re.search("\\d+", str(值))
        return int(匹配.group(0)) if 匹配 else 0


def 读取任意字段(数据: dict[str, Any], 字段列表: tuple[str, ...]) -> Any:
    if not isinstance(数据, dict):
        return None
    for 字段名 in 字段列表:
        值 = 数据.get(字段名)
        if 值 not in (None, ""):
            return 值
    return None


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 限制文本长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."
