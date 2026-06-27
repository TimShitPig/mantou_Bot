from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Any

import aiohttp
from astrbot.api import logger

自建API地址 = 'http://101.35.133.34:5000'
批次大小 = 30
最大并发 = 100
进度分段数 = 10
浏览器请求头 = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36', 'Accept': 'application/json, text/plain, */*'}


async def 准备番茄小说(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    if not 书籍编号:
        return {"success": False, "error": "自建API没有获取到书籍ID"}

    详情响应, 目录响应 = await asyncio.gather(
        请求JSON(会话, "/api/detail", book_id=书籍编号),
        请求JSON(会话, "/api/book", book_id=书籍编号),
    )

    详情数据 = 解析内层数据(详情响应)
    目录数据 = 解析内层数据(目录响应)

    书籍信息 = 合并书籍信息(默认书籍信息(书籍编号), 从字典提取书籍信息(详情数据))
    章节列表 = 提取章节目录(目录数据)
    if not 章节列表:
        return {"success": False, "error": "自建API没有获取到章节目录"}

    书籍信息 = 合并书籍信息(书籍信息, {"chapter_count": len(章节列表)})
    logger.info(
        f"番茄小说自建API准备完成：book_id={书籍编号}, title={书籍信息.get('title')}, chapters={len(章节列表)}"
    )
    return {"success": True, "book_id": 书籍编号, "book_info": 书籍信息, "chapters": 章节列表}


async def 下载全部章节(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    总数 = len(目录)
    批次列表 = [目录[i:i + 批次大小] for i in range(0, 总数, 批次大小)]
    并发数 = min(最大并发, len(批次列表))
    信号量 = asyncio.Semaphore(并发数)
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上一进度段 = 0
    结果列表: list[dict[str, Any]] = []
    logger.debug(f'番茄小说自建API章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%, batches={len(批次列表)}, concurrency={并发数}')

    async def 下载单个批次(批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal 已完成, 成功数, 失败数, 上一进度段
        async with 信号量:
            for 重试次数 in range(3):
                try:
                    批次结果 = await 请求并映射批次(会话, 书籍编号, 批次)
                    async with asyncio.Lock():
                        已完成 += len(批次)
                        成功数 += sum((1 for 项目 in 批次结果 if 项目.get('success')))
                        失败数 += sum((1 for 项目 in 批次结果 if not 项目.get('success')))
                        进度段 = 进度分段数 if 已完成 >= 总数 else int(已完成 * 进度分段数 / 总数)
                        if 进度段 > 上一进度段 or 已完成 >= 总数:
                            上一进度段 = 进度段
                            百分比 = int(已完成 * 100 / 总数) if 总数 else 100
                            logger.debug(f'番茄小说自建API章节进度：book_id={书籍编号}, progress={已完成}/{总数}, percent={百分比}%, success={成功数}, failed={失败数}')
                    return 批次结果
                except Exception as 异常:
                    if 重试次数 >= 2:
                        logger.warning(f"番茄小说自建API批次下载失败：book_id={书籍编号}, range={批次[0].get('index')}-{批次[-1].get('index')}, error={异常}")
                        return [{**章节, 'content': '【下载失败】', 'success': False} for 章节 in 批次]
                    await asyncio.sleep(1)
            return [{**章节, 'content': '【下载失败】', 'success': False} for 章节 in 批次]

    任务列表 = [下载单个批次(批次) for 批次 in 批次列表]
    批次结果列表 = await asyncio.gather(*任务列表)
    for 批次结果 in 批次结果列表:
        结果列表.extend(批次结果)
    return 结果列表


async def 请求并映射批次(会话: aiohttp.ClientSession, 书籍编号: str, 批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
    章节ID列表 = [str(章节.get('id')) for 章节 in 批次 if 章节.get('id')]
    if not 章节ID列表:
        return [{**章节, 'content': '【下载失败】', 'success': False} for 章节 in 批次]
    item_ids = ','.join(章节ID列表)
    async with 会话.get(
        f'{自建API地址}/api/content',
        params={'tab': '批量', 'item_ids': item_ids, 'book_id': 书籍编号},
        timeout=120
    ) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f'自建API内容HTTP {响应.status}: {限制文本长度(文本, 200)}')
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f'自建API内容JSON解析失败：{限制文本长度(文本, 200)}') from 异常
    if not isinstance(响应数据, dict):
        raise RuntimeError('自建API内容返回格式不是对象')
    if str(响应数据.get('code')) not in ('0', '200'):
        消息 = 响应数据.get('message') or 响应数据.get('msg') or '接口返回失败'
        raise RuntimeError(f'自建API内容返回失败：{限制文本长度(str(消息), 200)}')
    数据 = 响应数据.get('data')
    章节项列表: list[dict[str, Any]] = []
    if isinstance(数据, dict):
        章节项列表 = 数据.get('chapters') or []
    elif isinstance(数据, list):
        章节项列表 = 数据
    if not isinstance(章节项列表, list):
        章节项列表 = []
    return 映射章节响应(批次, 章节项列表)


def 映射章节响应(批次: list[dict[str, Any]], 原始章节项: list[dict[str, Any]]) -> list[dict[str, Any]]:
    按编号索引: dict[str, dict[str, Any]] = {}
    for 项目 in 原始章节项:
        if not isinstance(项目, dict):
            continue
        cid = str(读取任意字段(项目, ('itemId', 'item_id', 'chapter_id', 'id')) or '')
        if cid:
            按编号索引[cid] = 项目
    结果列表: list[dict[str, Any]] = []
    for 章节 in 批次:
        cid = str(章节.get('id') or '')
        原始项 = 按编号索引.get(cid)
        正文 = 清理正文(提取正文(原始项) if 原始项 else '')
        标题 = 清理文本(读取任意字段(原始项 or {}, ('title', 'chapter_title', 'name'))) or str(章节.get('title') or f"第{章节.get('index')}章")
        结果列表.append({**章节, 'title': 标题, 'content': 正文 or '【下载失败】', 'success': bool(正文)})
    return 结果列表


def 提取正文(章节: dict[str, Any] | None) -> str:
    if not isinstance(章节, dict):
        return ''
    return 清理文本(读取任意字段(章节, ('content', 'chapter_content', 'text', 'body')))


def 解析内层数据(响应数据: Any) -> dict[str, Any]:
    if not isinstance(响应数据, dict):
        return {}
    内层 = 响应数据.get('data')
    if isinstance(内层, dict):
        if 'data' in 内层 and isinstance(内层.get('data'), dict):
            return 内层.get('data')
        return 内层
    return {}


async def 请求JSON(会话: aiohttp.ClientSession, 路径: str, **参数: Any) -> dict[str, Any]:
    async with 会话.get(f'{自建API地址}{路径}', params=参数, headers=浏览器请求头, timeout=60) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f'自建API HTTP {响应.status}({路径})：{限制文本长度(文本, 200)}')
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f'自建API JSON解析失败({路径})：{限制文本长度(文本, 200)}') from 异常
    if not isinstance(响应数据, dict):
        raise RuntimeError(f'自建API返回格式不是对象({路径})')
    if str(响应数据.get('code')) not in ('0', '200'):
        消息 = 响应数据.get('message') or 响应数据.get('msg') or '接口返回失败'
        raise RuntimeError(f'自建API返回失败({路径})：{限制文本长度(str(消息), 300)}')
    return 响应数据


def 提取章节目录(数据: Any) -> list[dict[str, Any]]:
    结果列表: list[dict[str, Any]] = []
    if not isinstance(数据, dict):
        return 结果列表

    卷列表 = 数据.get('chapterListWithVolume')
    if isinstance(卷列表, list):
        for 卷 in 卷列表:
            if not isinstance(卷, list):
                continue
            for 章 in 卷:
                if not isinstance(章, dict):
                    continue
                章节ID = str(章.get('itemId') or 章.get('chapter_id') or 章.get('item_id') or '')
                标题 = 清理文本(章.get('title') or 章.get('name') or '')
                序号 = 安全整数(章.get('realChapterOrder') or 章.get('order') or 章.get('index'))
                if not 序号:
                    序号 = len(结果列表) + 1
                if not 章节ID and not 标题:
                    continue
                结果列表.append({'id': 章节ID or str(序号), 'title': 标题 or f'第{序号}章', 'index': 序号})

    if not 结果列表:
        all_ids = 数据.get('allItemIds')
        if isinstance(all_ids, list) and all_ids:
            for 位置, 章节ID in enumerate(all_ids, start=1):
                结果列表.append({'id': str(章节ID), 'title': f'第{位置}章', 'index': 位置})

    去重结果: list[dict[str, Any]] = []
    已见集合: set[tuple[str, int]] = set()
    for 位置, 项目 in enumerate(结果列表, start=1):
        if not int(项目.get('index') or 0):
            项目['index'] = 位置
        键 = (str(项目.get('id') or ''), int(项目.get('index') or 0))
        if 键 in 已见集合:
            continue
        已见集合.add(键)
        去重结果.append(项目)
    return sorted(去重结果, key=lambda 项目: int(项目.get('index') or 0))


def 从字典提取书籍信息(数据: dict[str, Any]) -> dict[str, Any]:
    作者 = 读取任意字段(数据, ('author', 'author_name', 'authorName', 'author_nickname'))
    if isinstance(作者, dict):
        作者 = 读取任意字段(作者, ('name', 'author_name', 'authorName'))
    原始状态 = 读取任意字段(数据, ('creation_status', 'creationStatus', 'status', 'book_status', 'bookStatus'))
    状态描述 = 清理文本(读取任意字段(数据, ('status_text', 'statusText', 'status_desc', 'statusDesc')))
    return {
        'title': 清理书名(读取任意字段(数据, ('book_name', 'bookName', 'bookTitle', 'title', 'name'))),
        'author': 清理文本(作者),
        'word_count': 格式化字数(读取任意字段(数据, ('word_count', 'wordCount', 'word_number', 'wordNumber', 'totalWords'))),
        'status': 规范化状态(原始状态, 状态描述),
        'chapter_count': 安全整数(读取任意字段(数据, ('chapter_count', 'chapterCount', 'chapter_num', 'chapterNum', 'all_chapter_num', 'serial_count', 'latest_chapter_index'))),
        'intro': 清理简介(读取任意字段(数据, ('abstract', 'description', 'summary', 'book_abstract', 'bookAbstract', 'intro', 'book_abstract_v2'))),
    }


def 默认书籍信息(书籍编号: str) -> dict[str, Any]:
    return {"book_id": 书籍编号, "title": f"番茄小说{书籍编号}", "author": "未知", "status": "未知", "word_count": "未知", "chapter_count": 0, "intro": ""}


def 合并书籍信息(基础信息: dict[str, Any], 新增信息: dict[str, Any]) -> dict[str, Any]:
    结果 = dict(基础信息 or {})
    for 键, 值 in (新增信息 or {}).items():
        if 键 == "title":
            值 = 清理书名(值)
        elif 键 == "intro":
            值 = 清理简介(值)
        if 值 in (None, "", 0):
            continue
        当前值 = 结果.get(键)
        if 当前值 in (None, "", 0, "未知") or (键 == "title" and str(当前值).startswith("番茄小说")):
            结果[键] = 值
    return 结果


def 规范化状态(原始值: Any, 状态描述: str = "") -> str:
    文本 = f"{原始值 or ''} {状态描述 or ''}".strip().lower()
    if any(关键词 in 文本 for 关键词 in ("完结", "已完结", "completed", "finish", "finished")):
        return "完结"
    if any(关键词 in 文本 for 关键词 in ("连载", "ongoing", "serial")):
        return "连载"
    if str(原始值).strip().lower() in ("0", "2"):
        return "完结"
    if str(原始值).strip().lower() in ("1", "3", "4"):
        return "连载"
    return ""


def 格式化字数(值: Any) -> str:
    文本 = str(值 or "").strip().replace(" ", "")
    if not 文本:
        return ""
    if re.search("[万亿千百]", 文本):
        return 文本
    数值 = 安全整数(文本)
    if 数值 >= 10000:
        return f"{数值 / 10000:.1f}万字".replace(".0万", "万")
    return f"{数值}字" if 数值 else ""


def 清理正文(文本: Any) -> str:
    文本 = str(文本 or "").replace("\\n", "\n").replace("\\/", "/")
    文本 = re.sub(r"<br\s*/?>", "\n", 文本, flags=re.IGNORECASE)
    文本 = re.sub(r"</p>", "\n", 文本, flags=re.IGNORECASE)
    文本 = 清理文本(文本).replace("\r", "")
    文本 = re.sub(r"\n{3,}", "\n\n", 文本)
    return 文本.strip()


def 清理文本(文本: Any) -> str:
    文本 = re.sub(r"<[^>]+>", "", str(文本 or ""))
    return html.unescape(文本).strip()


def 清理书名(文本: Any) -> str:
    书名 = 清理文本(文本)
    书名 = re.sub(r"完整版在线免费阅读.*$", "", 书名)
    书名 = re.sub(r"在线免费阅读.*$", "", 书名)
    书名 = re.sub(r"小说[_-]?番茄小说官网.*$", "", 书名)
    书名 = re.sub(r"[_-].*番茄小说.*$", "", 书名)
    return 书名.strip(" _-｜|")


def 清理简介(文本: Any) -> str:
    简介 = 清理文本(文本)
    简介 = 简介.replace("\\n", "\n").replace("\\/", "/")
    简介 = re.sub(r"^番茄小说提供.*?精彩小说尽在番茄小说网。", "", 简介)
    简介 = re.sub(r"[ \t]+", " ", 简介)
    简介 = re.sub(r"\n{3,}", "\n\n", 简介)
    return 简介.strip()


def 安全整数(值: Any) -> int:
    if 值 in (None, "") or isinstance(值, bool):
        return 0
    try:
        return max(0, int(float(str(值).strip())))
    except Exception:
        匹配 = re.search(r"\d+", str(值))
        return int(匹配.group(0)) if 匹配 else 0


def 读取任意字段(数据: dict[str, Any], 字段列表: tuple[str, ...]) -> Any:
    if not isinstance(数据, dict):
        return None
    for 字段名 in 字段列表:
        值 = 数据.get(字段名)
        if 值 not in (None, ""):
            return 值
    return None


def 限制文本长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."
