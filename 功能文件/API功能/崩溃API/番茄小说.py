from __future__ import annotations

import asyncio
import html
import json
import re
import time
from typing import Any

import aiohttp
from astrbot.api import logger


崩溃API地址 = "http://111.170.14.45:2000"
下载任务轮询间隔秒 = 3
下载任务最大等待秒 = 1800
进度分段数 = 10
章节标题正则 = re.compile(r"^\s*第[一二三四五六七八九十百千万\d]+[章节卷回][^\n]{0,80}$")


async def 准备番茄小说(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    if not 书籍编号:
        return {"success": False, "error": "崩溃API没有获取到书籍ID"}

    详情响应, 目录响应 = await asyncio.gather(
        请求JSON(会话, "/info", book_id=书籍编号),
        请求JSON(会话, "/catalog", book_id=书籍编号),
    )
    详情数据 = 详情响应.get("data") if isinstance(详情响应, dict) else {}
    目录数据 = 目录响应.get("data") if isinstance(目录响应, dict) else {}
    详情数据 = 详情数据 if isinstance(详情数据, dict) else {}
    目录数据 = 目录数据 if isinstance(目录数据, dict) else {}

    书籍信息 = 合并书籍信息(
        默认书籍信息(书籍编号),
        从字典提取书籍信息(详情数据),
    )
    书籍信息 = 合并书籍信息(书籍信息, 从字典提取书籍信息(读取路径(目录数据, ("book_info",)) or {}))
    章节列表 = 提取章节目录(目录数据)
    if not 章节列表:
        return {"success": False, "error": "崩溃API没有获取到章节目录"}

    书籍信息 = 合并书籍信息(书籍信息, {"chapter_count": len(章节列表)})
    logger.info(
        f"番茄小说崩溃API准备完成：book_id={书籍编号}, title={书籍信息.get('title')}, chapters={len(章节列表)}"
    )
    return {"success": True, "book_id": 书籍编号, "book_info": 书籍信息, "chapters": 章节列表}


async def 下载完整小说(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    基础书籍信息: dict[str, Any],
    目录: list[dict[str, Any]],
) -> dict[str, Any]:
    开始时间 = time.time()
    任务数据 = await 创建下载任务(会话, 书籍编号)
    任务编号 = 提取任务编号(任务数据)
    if not 任务编号:
        return {"success": False, "error": f"崩溃API创建下载任务没有返回 taskId：{限制文本长度(任务数据, 300)}"}

    logger.info(f"番茄小说崩溃API下载任务已创建：book_id={书籍编号}, task_id={任务编号}")
    进度数据 = await 等待下载完成(会话, 任务编号, 书籍编号)
    文件文本 = await 下载任务文件(会话, 任务编号)
    解析结果 = 解析下载TXT(文件文本, 书籍编号, 基础书籍信息, 目录)
    耗时 = time.time() - 开始时间
    logger.info(
        f"番茄小说崩溃API文件下载完成：book_id={书籍编号}, task_id={任务编号}, "
        f"chapters={len(解析结果.get('chapters') or [])}, elapsed={耗时:.2f}s"
    )
    return {
        "success": True,
        "book_id": 书籍编号,
        "task_id": 任务编号,
        "progress": 进度数据,
        "book_info": 解析结果["book_info"],
        "chapters": 解析结果["chapters"],
        "chapter_results": 解析结果["chapter_results"],
        "raw_text": 文件文本,
    }


async def 创建下载任务(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    return await 请求JSON(会话, "/download", book_id=书籍编号)


async def 等待下载完成(会话: aiohttp.ClientSession, 任务编号: str, 书籍编号: str) -> dict[str, Any]:
    截止时间 = time.time() + 下载任务最大等待秒
    上一进度段 = -1
    while time.time() < 截止时间:
        响应数据 = await 请求JSON(会话, "/download/progress", task_id=任务编号)
        数据 = 响应数据.get("data") if isinstance(响应数据, dict) else {}
        数据 = 数据 if isinstance(数据, dict) else {}
        状态 = str(读取任意字段(数据, ("status", "state")) or "").lower()
        已完成 = 安全整数(读取任意字段(数据, ("completedChapters", "completed_chapters", "completed")))
        总数 = 安全整数(读取任意字段(数据, ("totalChapters", "total_chapters", "total")))
        进度段 = 计算进度段(已完成, 总数, 状态)
        if 进度段 > 上一进度段:
            上一进度段 = 进度段
            百分比 = int(已完成 * 100 / 总数) if 总数 else (100 if 是完成状态(状态) else 0)
            logger.info(
                f"番茄小说崩溃API下载进度：book_id={书籍编号}, task_id={任务编号}, "
                f"status={状态 or 'unknown'}, progress={已完成}/{总数}, percent={百分比}%"
            )
        if 是完成状态(状态):
            return 数据
        if 是失败状态(状态):
            消息 = 读取任意字段(数据, ("message", "msg", "error")) or "下载任务失败"
            raise RuntimeError(f"崩溃API下载任务失败：{限制文本长度(消息, 300)}")
        await asyncio.sleep(下载任务轮询间隔秒)
    raise RuntimeError(f"崩溃API下载任务超时：task_id={任务编号}")


async def 下载任务文件(会话: aiohttp.ClientSession, 任务编号: str) -> str:
    async with 会话.get(f"{崩溃API地址}/download/file", params={"task_id": 任务编号}, timeout=120) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"崩溃API文件下载失败：HTTP {响应.status}: {限制文本长度(文本, 200)}")
        return 文本.lstrip("\ufeff")


async def 请求JSON(会话: aiohttp.ClientSession, 路径: str, **参数: Any) -> dict[str, Any]:
    async with 会话.get(f"{崩溃API地址}{路径}", params=参数, timeout=90) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"崩溃API HTTP {响应.status}({路径})：{限制文本长度(文本, 200)}")
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f"崩溃API JSON解析失败({路径})：{限制文本长度(文本, 200)}") from 异常
    if not isinstance(响应数据, dict):
        raise RuntimeError(f"崩溃API返回格式不是对象({路径})")
    返回码 = 响应数据.get("code")
    成功 = 响应数据.get("success")
    if str(返回码) not in ("0", "1", "200") and 成功 is not True:
        消息 = 响应数据.get("message") or 响应数据.get("msg") or 响应数据.get("error") or "接口返回失败"
        raise RuntimeError(f"崩溃API返回失败({路径})：{限制文本长度(消息, 300)}")
    return 响应数据


def 解析下载TXT(
    文件文本: str,
    书籍编号: str,
    基础书籍信息: dict[str, Any],
    目录: list[dict[str, Any]],
) -> dict[str, Any]:
    文本 = 文件文本.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    行列表 = 文本.split("\n")
    书籍信息 = 合并书籍信息(默认书籍信息(书籍编号), 基础书籍信息 or {})
    书籍信息 = 合并书籍信息(书籍信息, 提取TXT头部信息(行列表))
    章节结果列表 = 提取TXT章节(行列表, 目录)
    if not 章节结果列表:
        正文 = 清理正文(文本)
        章节结果列表 = [{"id": "1", "title": "正文", "index": 1, "content": 正文 or "【下载失败】", "success": bool(正文)}]
    章节列表 = [{"id": 章节.get("id") or str(章节.get("index")), "title": 章节.get("title"), "index": 章节.get("index")} for 章节 in 章节结果列表]
    书籍信息 = 合并书籍信息(书籍信息, {"chapter_count": len(章节列表)})
    return {"book_info": 书籍信息, "chapters": 章节列表, "chapter_results": 章节结果列表}


def 提取TXT头部信息(行列表: list[str]) -> dict[str, Any]:
    信息: dict[str, Any] = {}
    简介行: list[str] = []
    正在简介 = False
    for 原始行 in 行列表:
        行 = 原始行.strip()
        if not 行:
            if 正在简介 and 简介行:
                简介行.append("")
            continue
        if 章节标题正则.match(行):
            break
        字段匹配 = re.match(r"^(书名|名称|作者|状态|字数|章节数|书籍ID)\s*[:：]\s*(.*)$", 行)
        if 字段匹配:
            正在简介 = False
            字段名, 值 = 字段匹配.group(1), 字段匹配.group(2).strip()
            if 字段名 in ("书名", "名称"):
                信息["title"] = 值
            elif 字段名 == "作者":
                信息["author"] = 值
            elif 字段名 == "状态":
                信息["status"] = 值
            elif 字段名 == "字数":
                信息["word_count"] = 值
            elif 字段名 == "章节数":
                信息["chapter_count"] = 安全整数(值)
            continue
        if 行.startswith("简介"):
            正在简介 = True
            简介文本 = re.sub(r"^简介\s*[:：]?\s*", "", 行).strip()
            if 简介文本:
                简介行.append(简介文本)
            continue
        if 正在简介:
            简介行.append(行)
    简介 = 清理简介("\n".join(简介行))
    if 简介:
        信息["intro"] = 简介
    return 信息


def 提取TXT章节(行列表: list[str], 目录: list[dict[str, Any]]) -> list[dict[str, Any]]:
    结果列表: list[dict[str, Any]] = []
    当前标题 = ""
    当前内容: list[str] = []
    当前序号 = 0

    def 保存当前() -> None:
        nonlocal 当前标题, 当前内容, 当前序号
        if not 当前标题:
            return
        内容 = 清理正文("\n".join(当前内容))
        序号 = 当前序号 or len(结果列表) + 1
        目录项 = 目录[序号 - 1] if 0 < 序号 <= len(目录) else {}
        结果列表.append(
            {
                "id": 目录项.get("id") or str(序号),
                "title": 当前标题,
                "index": 序号,
                "content": 内容 or "【下载失败】",
                "success": bool(内容),
            }
        )

    for 原始行 in 行列表:
        行 = 原始行.strip()
        if 章节标题正则.match(行):
            保存当前()
            当前序号 = len(结果列表) + 1
            当前标题 = 行
            当前内容 = []
            continue
        if 当前标题:
            当前内容.append(原始行)
    保存当前()
    return 结果列表


def 提取章节目录(数据: Any) -> list[dict[str, Any]]:
    候选列表 = 读取路径(data=数据, 路径=("item_data_list",))
    if not isinstance(候选列表, list):
        候选列表 = 读取路径(data=数据, 路径=("catalog_data", "item_data_list"))
    if not isinstance(候选列表, list):
        候选列表 = 读取路径(data=数据, 路径=("data", "item_data_list"))
    if not isinstance(候选列表, list):
        候选列表 = []
    结果列表: list[dict[str, Any]] = []
    for 位置, 项目 in enumerate(候选列表, start=1):
        if not isinstance(项目, dict):
            continue
        章节编号 = 清理文本(读取任意字段(项目, ("item_id", "itemId", "chapter_id", "chapterId", "id")))
        标题 = 清理文本(读取任意字段(项目, ("title", "chapter_title", "name"))) or f"第{位置}章"
        序号 = 安全整数(读取任意字段(项目, ("chapter_index", "chapterIndex", "index", "sort_order", "order"))) or 位置
        结果列表.append({"id": 章节编号 or str(序号), "title": 标题, "index": 序号})
    return sorted(结果列表, key=lambda 项目: int(项目.get("index") or 0))


def 提取任务编号(任务数据: dict[str, Any]) -> str:
    return 清理文本(
        读取任意字段(任务数据, ("taskId", "task_id", "id"))
        or 读取路径(任务数据, ("data", "taskId"))
        or 读取路径(任务数据, ("data", "task_id"))
        or 读取路径(任务数据, ("data", "id"))
    )


def 计算进度段(已完成: int, 总数: int, 状态: str) -> int:
    if 是完成状态(状态):
        return 进度分段数
    if 总数 <= 0:
        return 0
    return int(已完成 * 进度分段数 / 总数)


def 是完成状态(状态: str) -> bool:
    return 状态.lower() in ("completed", "complete", "done", "finish", "finished", "success")


def 是失败状态(状态: str) -> bool:
    return 状态.lower() in ("failed", "fail", "error", "canceled", "cancelled")


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
        if 当前值 in (None, "", 0, "未知") or (键 == "title" and str(当前值).startswith("番茄小说")):
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
        "chapter_count": 安全整数(读取任意字段(数据, ("chapter_count", "chapterCount", "chapter_num", "chapterNum", "all_chapter_num", "latest_chapter_index"))),
        "intro": 清理简介(读取任意字段(数据, ("abstract", "description", "summary", "book_abstract", "bookAbstract", "intro"))),
    }


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


def 读取路径(data: Any, 路径: tuple[str, ...]) -> Any:
    当前值 = data
    for 字段名 in 路径:
        if not isinstance(当前值, dict):
            return None
        当前值 = 当前值.get(字段名)
    return 当前值


def 限制文本长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."
