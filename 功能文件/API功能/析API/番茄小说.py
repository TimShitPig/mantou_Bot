from __future__ import annotations

import asyncio
import html
import json
import re
import urllib.parse
from typing import Any

import aiohttp
from astrbot.api import logger


析API番茄小说地址 = "https://biek.top//api/fq.php"
章节并发数 = 200
进度分段数 = 10

番茄域名正则 = re.compile("fanqienovel\\.com|changdunovel\\.com|fqnovel\\.com|novelfm\\.com", re.IGNORECASE)
长读短链正则 = re.compile("https?://(?:www\\.)?changdunovel\\.com/t/[A-Za-z0-9_-]+/?", re.IGNORECASE)


async def 下载番茄小说(会话: aiohttp.ClientSession, 来源: str, 书籍编号: str = "", 基础书籍信息: dict[str, Any] | None = None) -> dict[str, Any]:
    准备结果 = await 准备番茄小说(会话, 来源, 书籍编号, 基础书籍信息)
    if not 准备结果.get("success"):
        return 准备结果
    实际书籍编号 = str(准备结果.get("book_id") or "")
    章节列表 = 准备结果.get("chapters") or []
    章节结果列表 = await 下载全部章节(会话, 实际书籍编号, 章节列表)
    成功数 = sum(1 for 项目 in 章节结果列表 if 项目.get("success"))
    if 成功数 <= 0:
        return {"success": False, "error": "析API没有获取到可用章节正文"}
    return {**准备结果, "chapter_results": 章节结果列表}


async def 准备番茄小说(会话: aiohttp.ClientSession, 来源: str, 书籍编号: str = "", 基础书籍信息: dict[str, Any] | None = None) -> dict[str, Any]:
    实际书籍编号 = 书籍编号 or 提取书籍编号(来源) or await 搜索书籍编号(会话, 来源)
    if not 实际书籍编号:
        return {"success": False, "error": "析API没有识别到书籍ID"}

    详情响应 = await 请求详情(会话, 实际书籍编号)
    详情数据 = 详情响应.get("data") if isinstance(详情响应, dict) else {}
    书籍信息 = 合并书籍信息(默认书籍信息(实际书籍编号), 基础书籍信息 or {})
    书籍信息 = 合并书籍信息(书籍信息, 从字典提取书籍信息(详情数据 if isinstance(详情数据, dict) else {}))

    目录响应 = await 请求目录(会话, 实际书籍编号)
    目录数据 = 目录响应.get("data") if isinstance(目录响应, dict) else 目录响应
    章节列表 = 提取章节目录(目录数据)
    if not 章节列表:
        章节列表 = 提取章节目录(详情数据)
    if not 章节列表:
        return {"success": False, "error": "析API没有获取到章节目录"}

    书籍信息 = 合并书籍信息(书籍信息, {"chapter_count": len(章节列表)})
    logger.info(
        f"番茄小说析API准备完成：book_id={实际书籍编号}, title={书籍信息.get('title')}, chapters={len(章节列表)}"
    )
    return {
        "success": True,
        "book_id": 实际书籍编号,
        "book_info": 书籍信息,
        "chapters": 章节列表,
        "chapter_results": [],
    }


async def 搜索书籍编号(会话: aiohttp.ClientSession, 来源: str) -> str:
    响应数据 = await 请求搜索(会话, 来源)
    搜索结果 = 读取路径(响应数据, ("data", "ret_data"))
    if not isinstance(搜索结果, list):
        return ""
    for 项目 in 搜索结果:
        if not isinstance(项目, dict):
            continue
        书籍编号 = 清理文本(项目.get("book_id"))
        if re.fullmatch("\\d{15,25}", 书籍编号):
            logger.info(f"番茄小说析API搜索命中：book_id={书籍编号}, title={项目.get('title')}")
            return 书籍编号
    return ""


async def 下载全部章节(会话: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]]) -> list[dict[str, Any]]:
    总数 = len(目录)
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上一进度段 = 0
    结果列表: list[dict[str, Any]] = []
    logger.info(f"番茄小说析API章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%")

    def 记录进度(批次结果: list[dict[str, Any]]) -> None:
        nonlocal 已完成, 成功数, 失败数, 上一进度段
        已完成 += len(批次结果)
        成功数 += sum(1 for 项目 in 批次结果 if 项目.get("success"))
        失败数 += sum(1 for 项目 in 批次结果 if not 项目.get("success"))
        进度段 = 进度分段数 if 已完成 >= 总数 else int(已完成 * 进度分段数 / 总数)
        if 进度段 <= 上一进度段 and 已完成 < 总数:
            return
        上一进度段 = 进度段
        百分比 = int(已完成 * 100 / 总数) if 总数 else 100
        logger.info(
            f"番茄小说析API章节进度：book_id={书籍编号}, progress={已完成}/{总数}, percent={百分比}%, success={成功数}, failed={失败数}"
        )

    for 起点 in range(0, 总数, 章节并发数):
        批次 = 目录[起点:起点 + 章节并发数]
        批次结果 = await asyncio.gather(*(下载单章(会话, 书籍编号, 章节) for 章节 in 批次))
        记录进度(批次结果)
        结果列表.extend(批次结果)
    return 结果列表


async def 下载单章(会话: aiohttp.ClientSession, 书籍编号: str, 章节: dict[str, Any]) -> dict[str, Any]:
    章节编号 = 清理文本(章节.get("id"))
    try:
        响应数据 = await 请求正文(会话, 章节编号)
        数据 = 响应数据.get("data") if isinstance(响应数据, dict) else {}
        数据 = 数据 if isinstance(数据, dict) else {}
        正文 = 清理正文(提取正文(数据))
        章名 = 清理文本(读取任意字段(数据, ("title", "chapter_title", "name"))) or str(章节.get("title") or f"第{章节.get('index')}章")
        return {**章节, "title": 章名, "content": 正文 or "【下载失败】", "success": bool(正文)}
    except Exception as 异常:
        logger.warning(f"番茄小说析API章节下载失败：book_id={书籍编号}, chapter={章节.get('index')}, item_id={章节编号}, error={异常}")
        return {**章节, "content": "【下载失败】", "success": False}


async def 请求详情(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    return await 请求析API(会话, "detail", book_id=书籍编号)


async def 请求目录(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    return await 请求析API(会话, "catalog", book_id=书籍编号)


async def 请求正文(会话: aiohttp.ClientSession, 章节编号: str) -> dict[str, Any]:
    return await 请求析API(会话, "content", item_id=章节编号)


async def 请求搜索(会话: aiohttp.ClientSession, 关键词: str, 页码: int = 0) -> dict[str, Any]:
    return await 请求析API(会话, "search", q=关键词, page=页码)


async def 请求析API(会话: aiohttp.ClientSession, 动作: str, **参数: Any) -> dict[str, Any]:
    请求参数 = {"action": 动作}
    请求参数.update({键: 值 for 键, 值 in 参数.items() if 值 not in (None, "")})
    async with 会话.get(析API番茄小说地址, params=请求参数, timeout=90) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"析API HTTP {响应.status}: {限制文本长度(文本, 120)}")
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f"析API JSON解析失败：{限制文本长度(文本, 120)}") from 异常
    if not isinstance(响应数据, dict):
        raise RuntimeError("析API 返回格式不是对象")
    返回码 = 响应数据.get("code")
    成功 = 响应数据.get("success")
    if str(返回码) not in ("0", "1", "200") and 成功 is not True:
        消息 = 响应数据.get("message") or 响应数据.get("msg") or 响应数据.get("error") or "接口返回失败"
        raise RuntimeError(f"析API返回失败：code={返回码}, message={限制文本长度(消息, 200)}")
    return 响应数据


def 提取章节目录(数据: Any) -> list[dict[str, Any]]:
    项目列表: list[dict[str, Any]] = []

    def 遍历(值: Any) -> None:
        if isinstance(值, list):
            for 项目 in 值:
                遍历(项目)
            return
        if not isinstance(值, dict):
            return
        书名 = 清理文本(读取任意字段(值, ("title", "chapter_title", "name")))
        章节编号 = 清理文本(读取任意字段(值, ("chapter_id", "chapterId", "item_id", "itemId", "id")))
        序号 = 安全整数(读取任意字段(值, ("chapter", "index", "order", "chapter_index", "chapterIndex", "realChapterOrder")))
        if (书名 or 章节编号) and (章节编号 or 序号):
            项目列表.append({"id": 章节编号 or str(序号), "title": 书名 or f"第{序号 or len(项目列表) + 1}章", "index": 序号 or len(项目列表) + 1})
            return
        for 子项 in 值.values():
            if isinstance(子项, (dict, list)):
                遍历(子项)

    遍历(数据)
    去重结果: list[dict[str, Any]] = []
    已见集合: set[tuple[str, int]] = set()
    for 位置, 项目 in enumerate(项目列表, start=1):
        项目["index"] = 安全整数(项目.get("index")) or 位置
        键 = (str(项目.get("id") or ""), int(项目.get("index") or 0))
        if 键 in 已见集合:
            continue
        已见集合.add(键)
        去重结果.append(项目)
    return sorted(去重结果, key=lambda 项目: int(项目.get("index") or 0))


def 提取正文(章节: dict[str, Any] | None) -> str:
    if not isinstance(章节, dict):
        return ""
    正文 = 读取任意字段(章节, ("content", "chapter_content", "text", "body"))
    if 正文 is None:
        return ""
    if isinstance(正文, (dict, list)):
        return json.dumps(正文, ensure_ascii=False)
    return 解码JSON字符串片段(正文)


def 提取书籍编号(文本: str) -> str:
    for 候选路径 in 生成文本变体(str(文本 or "")):
        候选路径 = 候选路径.strip()
        if re.fullmatch("\\d{15,25}", 候选路径):
            return 候选路径
        规则列表 = (
            "(?:book_id|bookid|bookId)=(\\d{15,25})",
            "fanqienovel\\.com/(?:page|reader)?/?(\\d{15,25})",
            "fanqienovel\\.com/[^\\s?&#]*/(\\d{15,25})",
            "(?:changdunovel\\.com|fqnovel\\.com|novelfm\\.com).*?(?:book_id|bookid|bookId)=(\\d{15,25})",
        )
        for 规则 in 规则列表:
            匹配 = re.search(规则, 候选路径, re.IGNORECASE)
            if 匹配:
                return 匹配.group(1)
    return ""


def 生成文本变体(文本: str) -> list[str]:
    文本 = html.unescape(str(文本 or "")).replace("\\/", "/")
    变体列表 = [文本]
    for _ in range(2):
        解码文本 = urllib.parse.unquote(变体列表[-1])
        if 解码文本 == 变体列表[-1]:
            break
        变体列表.append(解码文本)
    return 变体列表


def 默认书籍信息(书籍编号: str) -> dict[str, Any]:
    return {"book_id": 书籍编号, "title": f"番茄小说{书籍编号}", "author": "未知", "status": "未知", "word_count": "未知", "chapter_count": 0}


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
        if 当前值 in (None, "", 0, "未知") or (键 == "title" and 应覆盖书名(当前值, 值)):
            结果[键] = 值
    return 结果


def 从字典提取书籍信息(数据: dict[str, Any]) -> dict[str, Any]:
    作者 = 读取任意字段(数据, ("author", "author_name", "authorName", "author_nickname"))
    if isinstance(作者, dict):
        作者 = 读取任意字段(作者, ("name", "author_name", "authorName"))
    原始状态 = 读取任意字段(数据, ("creation_status", "creationStatus", "status", "book_status", "bookStatus"))
    状态描述 = 清理文本(读取任意字段(数据, ("status_text", "statusText", "status_desc", "statusDesc")))
    return {
        "title": 清理书名(读取任意字段(数据, ("book_name", "bookName", "bookTitle", "title", "name"))),
        "author": 清理文本(作者),
        "word_count": 格式化字数(读取任意字段(数据, ("word_count", "wordCount", "word_number", "wordNumber", "totalWords"))),
        "status": 规范化状态(原始状态, 状态描述),
        "chapter_count": 安全整数(读取任意字段(数据, ("chapter_count", "chapterCount", "chapter_num", "chapterNum", "all_chapter_num", "latest_chapter_index", "serial_num"))),
        "intro": 清理简介(读取任意字段(数据, ("abstract", "description", "summary", "book_abstract", "bookAbstract", "intro"))),
    }


def 规范化状态(原始项: Any, 状态描述: str = "") -> str:
    文本 = f"{原始项 or ''} {状态描述 or ''}".strip().lower()
    if any(关键词 in 文本 for 关键词 in ("已完结", "完结", "完本", "finished", "completed", "ended")):
        return "完结"
    if any(关键词 in 文本 for 关键词 in ("连载", "更新", "ongoing", "serial")):
        return "连载"
    if str(原始项).strip().lower() in ("0", "2"):
        return "完结"
    if str(原始项).strip().lower() in ("1", "3", "4"):
        return "连载"
    return ""


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
    文本 = str(值 or "").strip().replace(" ", "")
    匹配 = re.search("([\\d.]+)", 文本)
    if not 匹配:
        return 0
    数字 = float(匹配.group(1))
    if "亿" in 文本:
        数字 *= 100000000
    elif "万" in 文本:
        数字 *= 10000
    return int(数字)


def 清理正文(文本: Any) -> str:
    文本 = 解码JSON字符串片段(文本)
    文本 = str(文本 or "").replace("\\n", "\n").replace("\\/", "/")
    文本 = re.sub("<tt-audio\\b.*?</tt-audio>", "", 文本, flags=re.IGNORECASE | re.DOTALL)
    文本 = re.sub("<script\\b.*?</script>", "", 文本, flags=re.IGNORECASE | re.DOTALL)
    文本 = re.sub("<style\\b.*?</style>", "", 文本, flags=re.IGNORECASE | re.DOTALL)
    文本 = re.sub("<br\\s*/?>", "\n", 文本, flags=re.IGNORECASE)
    文本 = re.sub("</(?:p|div|section|article|h[1-6])>", "\n\n", 文本, flags=re.IGNORECASE)
    文本 = re.sub("</span>\\s*<span\\b[^>]*>", "", 文本, flags=re.IGNORECASE)
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
    简介 = re.sub("[ \t]+", " ", 简介)
    简介 = re.sub("\n{3,}", "\n\n", 简介)
    return 简介.strip()


def 解码JSON字符串片段(文本: Any) -> str:
    原文 = str(文本 or "")
    if not 原文:
        return ""
    try:
        return json.loads(f'"{原文}"')
    except Exception:
        return 原文


def 应覆盖书名(当前值: Any, 新值: Any) -> bool:
    当前书名 = 清理书名(当前值)
    新书名 = 清理书名(新值)
    if not 新书名:
        return False
    if "免费阅读" in str(当前值) or "番茄小说官网" in str(当前值):
        return True
    return (not 当前书名) or 当前书名.startswith("番茄小说")


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
