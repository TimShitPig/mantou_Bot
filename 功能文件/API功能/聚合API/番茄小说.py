from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Any

import aiohttp
from astrbot.api import logger


聚合API地址 = "http://101.35.133.34:5000"
批次大小 = 50
最大并发批次 = 10
进度分段数 = 10
浏览器请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


async def 准备番茄小说(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    if not 书籍编号:
        return {"success": False, "error": "聚合API没有获取到书籍ID"}

    try:
        详情响应, 目录响应 = await asyncio.gather(
            请求JSON(会话, "/api/detail", book_id=书籍编号),
            请求JSON(会话, "/api/book", book_id=书籍编号),
        )
    except Exception as 异常:
        return {"success": False, "error": str(异常)}

    详情数据 = 提取内层数据(详情响应)
    目录数据 = 提取内层数据(目录响应)
    if not 详情数据:
        错误 = 提取错误消息(详情响应) or "聚合API没有获取到书籍详情"
        return {"success": False, "error": 错误}

    书籍信息 = 合并书籍信息(默认书籍信息(书籍编号), 从字典提取书籍信息(详情数据))
    章节列表 = 提取章节目录(目录数据)
    if not 章节列表:
        try:
            简化目录响应 = await 请求JSON(会话, "/api/directory", book_id=书籍编号)
            章节列表 = 提取章节目录(简化目录响应.get("data") if isinstance(简化目录响应, dict) else 简化目录响应)
        except Exception as 异常:
            logger.warning(f"番茄小说聚合API简化目录请求失败：book_id={书籍编号}, error={异常}")
    if not 章节列表:
        return {"success": False, "error": "聚合API没有获取到章节目录"}

    书籍信息 = 合并书籍信息(书籍信息, {"chapter_count": len(章节列表)})
    logger.info(
        f"番茄小说聚合API准备完成：book_id={书籍编号}, title={书籍信息.get('title')}, chapters={len(章节列表)}"
    )
    return {"success": True, "book_id": 书籍编号, "book_info": 书籍信息, "chapters": 章节列表}


async def 下载全部章节(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    总数 = len(目录)
    if 总数 <= 0:
        return []

    批次列表 = [目录[开始:开始 + 批次大小] for 开始 in range(0, 总数, 批次大小)]
    信号量 = asyncio.Semaphore(最大并发批次)
    进度锁 = asyncio.Lock()
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上一进度段 = 0
    logger.info(
        f"番茄小说聚合API章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%, batches={len(批次列表)}"
    )

    async def 下载批次(批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal 已完成, 成功数, 失败数, 上一进度段
        async with 信号量:
            try:
                批次结果 = await 请求并映射批次(会话, 书籍编号, 批次)
            except Exception as 异常:
                logger.warning(
                    f"番茄小说聚合API批次下载失败：book_id={书籍编号}, "
                    f"range={批次[0].get('index')}-{批次[-1].get('index')}, error={异常}"
                )
                批次结果 = [{**章节, "content": "【下载失败】", "success": False} for 章节 in 批次]

            async with 进度锁:
                已完成 += len(批次结果)
                成功数 += sum(1 for 项目 in 批次结果 if 项目.get("success"))
                失败数 += sum(1 for 项目 in 批次结果 if not 项目.get("success"))
                进度段 = 进度分段数 if 已完成 >= 总数 else int(已完成 * 进度分段数 / 总数)
                if 进度段 > 上一进度段 or 已完成 >= 总数:
                    上一进度段 = 进度段
                    百分比 = int(已完成 * 100 / 总数) if 总数 else 100
                    logger.info(
                        f"番茄小说聚合API章节进度：book_id={书籍编号}, progress={已完成}/{总数}, "
                        f"percent={百分比}%, success={成功数}, failed={失败数}"
                    )
            return 批次结果

    批次结果列表 = await asyncio.gather(*(下载批次(批次) for 批次 in 批次列表))
    结果列表: list[dict[str, Any]] = []
    for 批次结果 in 批次结果列表:
        结果列表.extend(批次结果)
    return sorted(结果列表, key=lambda 项目: int(项目.get("index") or 0))


async def 请求并映射批次(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    批次: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    章节ID列表 = [str(章节.get("id") or "") for 章节 in 批次 if 章节.get("id")]
    if not 章节ID列表:
        return [{**章节, "content": "【下载失败】", "success": False} for 章节 in 批次]

    响应数据 = await 请求JSON(
        会话,
        "/api/content",
        tab="批量",
        item_ids=",".join(章节ID列表),
        book_id=书籍编号,
    )
    数据 = 响应数据.get("data") if isinstance(响应数据, dict) else {}
    章节项列表 = []
    if isinstance(数据, dict):
        章节项列表 = 数据.get("chapters") or 读取路径(数据, ("data", "chapters")) or []
    elif isinstance(数据, list):
        章节项列表 = 数据
    if not isinstance(章节项列表, list):
        章节项列表 = []
    return 映射章节响应(批次, 章节项列表)


async def 请求JSON(会话: aiohttp.ClientSession, 路径: str, **参数: Any) -> dict[str, Any]:
    async with 会话.get(
        f"{聚合API地址}{路径}",
        params={键: 值 for 键, 值 in 参数.items() if 值 not in (None, "")},
        headers=浏览器请求头,
        timeout=120,
    ) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"聚合API HTTP {响应.status}({路径})：{限制文本长度(文本, 300)}")
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f"聚合API JSON解析失败({路径})：{限制文本长度(文本, 300)}") from 异常

    if not isinstance(响应数据, dict):
        raise RuntimeError(f"聚合API返回格式不是对象({路径})")
    返回码 = 响应数据.get("code")
    if str(返回码) not in ("0", "200"):
        消息 = 提取错误消息(响应数据) or "接口返回失败"
        raise RuntimeError(f"聚合API返回失败({路径})：{限制文本长度(消息, 300)}")
    return 响应数据


def 提取内层数据(响应数据: Any) -> dict[str, Any]:
    if not isinstance(响应数据, dict):
        return {}
    数据 = 响应数据.get("data")
    if isinstance(数据, dict) and isinstance(数据.get("data"), dict):
        return 数据.get("data") or {}
    if isinstance(数据, dict):
        return 数据
    return {}


def 提取错误消息(响应数据: Any) -> str:
    if not isinstance(响应数据, dict):
        return ""
    for 路径 in (("message",), ("data", "message"), ("data", "msg"), ("data", "error")):
        值 = 读取路径(响应数据, 路径)
        if 值:
            return str(值)
    return ""


def 提取章节目录(数据: Any) -> list[dict[str, Any]]:
    结果列表: list[dict[str, Any]] = []

    def 遍历(值: Any) -> None:
        if isinstance(值, list):
            for 项目 in 值:
                遍历(项目)
            return
        if not isinstance(值, dict):
            return

        章节编号 = 清理文本(读取任意字段(值, ("itemId", "item_id", "chapter_id", "chapterId", "id")))
        标题 = 清理文本(读取任意字段(值, ("title", "chapter_title", "name")))
        序号 = 安全整数(读取任意字段(值, ("realChapterOrder", "real_chapter_order", "chapter_index", "chapterIndex", "index", "order")))
        if 章节编号 or 标题:
            结果列表.append({"id": 章节编号 or str(len(结果列表) + 1), "title": 标题 or f"第{序号 or len(结果列表) + 1}章", "index": 序号 or len(结果列表) + 1})
            return

        for 字段名 in ("chapterListWithVolume", "lists", "list", "chapters", "chapterList", "allItemIds"):
            子项 = 值.get(字段名)
            if 子项 is not None:
                if 字段名 == "allItemIds" and isinstance(子项, list):
                    for 章节ID in 子项:
                        结果列表.append({"id": str(章节ID), "title": f"第{len(结果列表) + 1}章", "index": len(结果列表) + 1})
                else:
                    遍历(子项)

    遍历(数据)
    去重结果: list[dict[str, Any]] = []
    已见集合: set[str] = set()
    for 位置, 项目 in enumerate(结果列表, start=1):
        章节编号 = str(项目.get("id") or "")
        if 章节编号 in 已见集合:
            continue
        已见集合.add(章节编号)
        项目["index"] = 安全整数(项目.get("index")) or 位置
        去重结果.append(项目)
    return sorted(去重结果, key=lambda 项目: int(项目.get("index") or 0))


def 映射章节响应(批次: list[dict[str, Any]], 原始章节项: list[Any]) -> list[dict[str, Any]]:
    按编号索引: dict[str, dict[str, Any]] = {}
    for 项目 in 原始章节项:
        if not isinstance(项目, dict):
            continue
        章节编号 = 提取章节编号(项目)
        if 章节编号:
            按编号索引[章节编号] = 项目

    结果列表: list[dict[str, Any]] = []
    for 索引, 章节 in enumerate(批次):
        章节编号 = str(章节.get("id") or "")
        原始项 = 按编号索引.get(章节编号)
        if 原始项 is None and len(原始章节项) == len(批次) and isinstance(原始章节项[索引], dict):
            原始项 = 原始章节项[索引]
        正文 = 清理正文(提取正文(原始项) if 原始项 else "")
        标题 = 清理文本(读取任意字段(原始项 or {}, ("title", "chapter_title", "name"))) or str(章节.get("title") or f"第{章节.get('index')}章")
        结果列表.append({**章节, "title": 标题, "content": 正文 or "【下载失败】", "success": bool(正文)})
    return 结果列表


def 提取章节编号(章节: dict[str, Any]) -> str:
    编号 = 读取任意字段(章节, ("item_id", "itemId", "chapter_id", "chapterId", "id", "group_id"))
    if 编号:
        return str(编号)
    小说数据 = 章节.get("novel_data")
    if isinstance(小说数据, dict):
        编号 = 读取任意字段(小说数据, ("item_id", "itemId", "chapter_id", "chapterId", "id", "group_id"))
        if 编号:
            return str(编号)
    return ""


def 提取正文(章节: dict[str, Any] | None) -> str:
    if not isinstance(章节, dict):
        return ""
    正文 = 读取任意字段(章节, ("content", "chapter_content", "text", "body"))
    if 正文 is None:
        return ""
    if isinstance(正文, (dict, list)):
        return json.dumps(正文, ensure_ascii=False)
    return 解码JSON字符串片段(正文)


def 从字典提取书籍信息(数据: dict[str, Any]) -> dict[str, Any]:
    作者 = 读取任意字段(数据, ("author", "author_name", "authorName", "author_nickname"))
    if isinstance(作者, dict):
        作者 = 读取任意字段(作者, ("name", "author_name", "authorName"))
    return {
        "title": 清理书名(读取任意字段(数据, ("book_name", "bookName", "bookTitle", "title", "name"))),
        "author": 清理文本(作者),
        "word_count": 格式化字数(读取任意字段(数据, ("word_number", "wordNumber", "word_count", "wordCount", "totalWords"))),
        "status": 规范化状态(读取任意字段(数据, ("creation_status", "creationStatus", "status", "book_status", "bookStatus"))),
        "chapter_count": 安全整数(读取任意字段(数据, ("serial_count", "serialCount", "chapter_count", "chapterCount", "chapter_number", "chapterNumber"))),
        "intro": 清理简介(读取任意字段(数据, ("abstract", "book_abstract_v2", "description", "summary", "intro"))),
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


def 规范化状态(值: Any) -> str:
    文本 = str(值 or "").strip().lower()
    if 文本 in ("0", "2") or any(关键词 in 文本 for 关键词 in ("完结", "已完结", "completed", "finished")):
        return "完结"
    if 文本 in ("1", "3", "4") or any(关键词 in 文本 for 关键词 in ("连载", "更新", "ongoing", "serial")):
        return "连载"
    return ""


def 格式化字数(值: Any) -> str:
    文本 = str(值 or "").strip().replace(" ", "")
    if not 文本:
        return ""
    if "字" in 文本 or "万" in 文本 or "亿" in 文本:
        return 文本
    数字 = 安全整数(文本)
    if 数字 >= 100000000:
        return f"{round(数字 / 100000000, 1):g}亿字"
    if 数字 >= 10000:
        return f"{round(数字 / 10000, 1):g}万字"
    return f"{数字}字" if 数字 else 文本


def 清理正文(文本: Any) -> str:
    文本 = 解码JSON字符串片段(文本)
    文本 = str(文本 or "").replace("\\n", "\n").replace("\\/", "/")
    文本 = re.sub("<tt-audio\\b.*?</tt-audio>", "", 文本, flags=re.IGNORECASE | re.DOTALL)
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
    书名 = 清理文本(文本)
    书名 = re.sub("完整版在线免费阅读.*$", "", 书名)
    书名 = re.sub("在线免费阅读.*$", "", 书名)
    书名 = re.sub("小说[_-]?番茄小说官网.*$", "", 书名)
    书名 = re.sub("[_-].*番茄小说.*$", "", 书名)
    return 书名.strip(" _-｜|")


def 清理简介(文本: Any) -> str:
    简介 = 清理文本(解码JSON字符串片段(文本))
    简介 = 简介.replace("\\n", "\n").replace("\\/", "/")
    简介 = re.sub("^番茄小说提供.*?精彩小说尽在番茄小说网。", "", 简介)
    简介 = re.sub("[ \\t]+", " ", 简介)
    简介 = re.sub("\\n{3,}", "\n\n", 简介)
    return 简介.strip()


def 解码JSON字符串片段(文本: Any) -> str:
    原文 = str(文本 or "")
    if not 原文:
        return ""
    try:
        return json.loads(f'"{原文}"')
    except Exception:
        return 原文


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


def 读取路径(数据: Any, 路径: tuple[str, ...]) -> Any:
    当前值 = 数据
    for 字段名 in 路径:
        if not isinstance(当前值, dict):
            return None
        当前值 = 当前值.get(字段名)
    return 当前值


def 限制文本长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."
