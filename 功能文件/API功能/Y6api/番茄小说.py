from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Any

import aiohttp
from astrbot.api import logger


Y6API地址 = "https://y68-napi.hf.space"
Y6来源 = "番茄"
Y6标签 = "小说"
进度分段数 = 10
浏览器请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://y68-napi.hf.space/sss.mhtml",
}


async def 准备番茄小说(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    if not 书籍编号:
        return {"success": False, "error": "Y6api没有获取到书籍ID"}

    try:
        详情响应, 目录响应 = await asyncio.gather(
            请求JSON(会话, "/api/detail", book_id=书籍编号),
            请求JSON(会话, "/api/directory", book_id=书籍编号),
        )
    except Exception as 异常:
        return {"success": False, "error": str(异常)}

    详情数据 = 提取内层数据(详情响应)
    目录数据 = 提取内层数据(目录响应)
    if not 详情数据:
        return {"success": False, "error": 提取错误消息(详情响应) or "Y6api没有获取到书籍详情"}

    书籍信息 = 合并书籍信息(默认书籍信息(书籍编号), 从字典提取书籍信息(详情数据))
    章节列表 = 提取章节目录(目录数据)
    if not 章节列表:
        return {"success": False, "error": "Y6api没有获取到章节目录"}

    书籍信息 = 合并书籍信息(书籍信息, {"chapter_count": len(章节列表)})
    logger.info(
        f"番茄小说Y6api准备完成：book_id={书籍编号}, title={书籍信息.get('title')}, chapters={len(章节列表)}"
    )
    return {"success": True, "book_id": 书籍编号, "book_info": 书籍信息, "chapters": 章节列表}


async def 下载完整小说(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    书籍信息: dict[str, Any],
    章节列表: list[dict[str, Any]],
) -> dict[str, Any]:
    if not 书籍编号:
        return {"success": False, "error": "Y6api没有获取到书籍ID"}
    if not 章节列表:
        return {"success": False, "error": "Y6api没有获取到章节目录"}

    try:
        打包文本 = await 请求文本(会话, "/api/download", book_id=书籍编号)
    except Exception as 异常:
        return {"success": False, "error": str(异常)}

    打包书籍信息, 章节结果列表 = 解析打包TXT(打包文本, 章节列表)
    书籍信息 = 合并书籍信息(书籍信息, 打包书籍信息)
    成功数 = sum(1 for 项目 in 章节结果列表 if 项目.get("success"))
    if 成功数 <= 0:
        return {"success": False, "error": "Y6api打包TXT没有解析到章节正文"}

    logger.info(
        f"番茄小说Y6api打包下载完成：book_id={书籍编号}, success={成功数}, total={len(章节列表)}"
    )
    return {
        "success": True,
        "book_info": 书籍信息,
        "chapters": 章节列表,
        "chapter_results": 章节结果列表,
    }


async def 请求JSON(会话: aiohttp.ClientSession, 路径: str, **参数: Any) -> dict[str, Any]:
    async with 会话.get(
        f"{Y6API地址}{路径}",
        params=构造请求参数(参数),
        headers=浏览器请求头,
        timeout=120,
    ) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"Y6api HTTP {响应.status}({路径})：{限制文本长度(文本, 300)}")
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f"Y6api JSON解析失败({路径})：{限制文本长度(文本, 300)}") from 异常

    if not isinstance(响应数据, dict):
        raise RuntimeError(f"Y6api返回格式不是对象({路径})")
    返回码 = 响应数据.get("code")
    if str(返回码) not in ("0", "200"):
        消息 = 提取错误消息(响应数据) or "接口返回失败"
        raise RuntimeError(f"Y6api返回失败({路径})：{限制文本长度(消息, 300)}")
    return 响应数据


async def 请求文本(会话: aiohttp.ClientSession, 路径: str, **参数: Any) -> str:
    超时 = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=600)
    请求头 = dict(浏览器请求头)
    请求头["Accept"] = "text/plain, */*"
    async with 会话.get(
        f"{Y6API地址}{路径}",
        params=构造请求参数(参数),
        headers=请求头,
        timeout=超时,
    ) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"Y6api HTTP {响应.status}({路径})：{限制文本长度(文本, 300)}")
    if not 文本.strip():
        raise RuntimeError("Y6api返回空TXT")
    return 文本


def 构造请求参数(参数: dict[str, Any]) -> dict[str, Any]:
    请求参数 = {"source": Y6来源, "tab": Y6标签}
    请求参数.update({键: 值 for 键, 值 in 参数.items() if 值 not in (None, "")})
    return 请求参数


def 解析打包TXT(文本: str, 目录: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    行列表 = str(文本 or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    首章行号 = 查找首章行号(行列表, 目录)
    书籍信息 = 提取打包头部信息(行列表[:首章行号 if 首章行号 >= 0 else len(行列表)])
    章节结果列表 = 按目录解析章节(行列表, 目录)
    return 书籍信息, 章节结果列表


def 查找首章行号(行列表: list[str], 目录: list[dict[str, Any]]) -> int:
    标题集合 = {清理标题(章节.get("title")) for 章节 in 目录 if 清理标题(章节.get("title"))}
    if not 标题集合:
        return -1
    for 行号, 行 in enumerate(行列表):
        if 清理标题(行) in 标题集合:
            return 行号
    return -1


def 提取打包头部信息(头部行列表: list[str]) -> dict[str, Any]:
    书籍信息: dict[str, Any] = {}
    简介行列表: list[str] = []
    正在读取简介 = False
    for 原行 in 头部行列表:
        行 = 原行.strip()
        if not 行 and not 正在读取简介:
            continue
        匹配 = re.match(r"^(?:书名|名称)[:：]\s*(.*)$", 行)
        if 匹配:
            书籍信息["title"] = 清理书名(匹配.group(1))
            正在读取简介 = False
            continue
        匹配 = re.match(r"^作者[:：]\s*(.*)$", 行)
        if 匹配:
            书籍信息["author"] = 清理文本(匹配.group(1))
            正在读取简介 = False
            continue
        匹配 = re.match(r"^简介[:：]\s*(.*)$", 行) or re.match(r"^(简介)$", 行)
        if 匹配:
            正在读取简介 = True
            首行 = 清理文本(匹配.group(1) if 匹配.lastindex and 匹配.group(1) != "简介" else "")
            if 首行:
                简介行列表.append(首行)
            continue
        if 正在读取简介:
            简介行列表.append(行)
    简介 = 清理简介("\n".join(简介行列表))
    if 简介:
        书籍信息["intro"] = 简介
    return 书籍信息


def 按目录解析章节(行列表: list[str], 目录: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 目录:
        return []

    标题索引: dict[str, list[int]] = {}
    for 位置, 章节 in enumerate(目录):
        标题 = 清理标题(章节.get("title"))
        if 标题:
            标题索引.setdefault(标题, []).append(位置)

    按位置结果: dict[int, dict[str, Any]] = {}
    当前位置: int | None = None
    当前正文行: list[str] = []
    下一个目录位置 = 0

    def 保存当前章节() -> None:
        nonlocal 当前位置, 当前正文行
        if 当前位置 is None:
            return
        章节 = 目录[当前位置]
        正文 = 清理章节正文(当前正文行)
        按位置结果[当前位置] = {
            **章节,
            "content": 正文 or "【下载失败】",
            "success": bool(正文),
        }
        当前位置 = None
        当前正文行 = []

    for 行 in 行列表:
        标题 = 清理标题(行)
        匹配位置 = 匹配章节标题位置(标题索引, 标题, 下一个目录位置)
        if 匹配位置 is not None:
            保存当前章节()
            当前位置 = 匹配位置
            下一个目录位置 = 匹配位置 + 1
            目录[当前位置]["title"] = 标题 or str(目录[当前位置].get("title") or "")
            continue
        if 当前位置 is not None:
            当前正文行.append(行)
    保存当前章节()

    结果列表: list[dict[str, Any]] = []
    for 位置, 章节 in enumerate(目录):
        结果列表.append(
            按位置结果.get(
                位置,
                {**章节, "content": "【下载失败】", "success": False},
            )
        )
    return 结果列表


def 匹配章节标题位置(标题索引: dict[str, list[int]], 标题: str, 起始位置: int) -> int | None:
    if not 标题:
        return None
    候选位置列表 = 标题索引.get(标题) or []
    for 位置 in 候选位置列表:
        if 位置 >= 起始位置:
            return 位置
    return None


def 清理章节正文(行列表: list[str]) -> str:
    处理后行列表: list[str] = []
    for 行 in 行列表:
        文本 = 行.rstrip()
        if 文本.startswith("    "):
            文本 = 文本[4:]
        elif 文本.startswith("\t"):
            文本 = 文本.lstrip()
        处理后行列表.append(文本)
    正文 = "\n".join(处理后行列表)
    正文 = 清理文本(正文).replace("\r", "")
    正文 = re.sub(r"[ \t]+\n", "\n", 正文)
    正文 = re.sub(r"\n[ \t]+", "\n", 正文)
    正文 = re.sub(r"\n{3,}", "\n\n", 正文)
    return 正文.strip()


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
            结果列表.append({
                "id": 章节编号 or str(len(结果列表) + 1),
                "title": 标题 or f"第{序号 or len(结果列表) + 1}章",
                "index": 序号 or len(结果列表) + 1,
            })
            return

        for 字段名 in ("chapterListWithVolume", "lists", "list", "chapters", "chapterList", "allItemIds"):
            子项 = 值.get(字段名)
            if 子项 is None:
                continue
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


def 从字典提取书籍信息(数据: dict[str, Any]) -> dict[str, Any]:
    作者 = 读取任意字段(数据, ("author", "author_name", "authorName", "author_nickname"))
    if isinstance(作者, dict):
        作者 = 读取任意字段(作者, ("name", "author_name", "authorName"))
    return {
        "title": 清理书名(读取任意字段(数据, ("book_name", "bookName", "bookTitle", "title", "name"))),
        "author": 清理文本(作者),
        "word_count": 格式化字数(读取任意字段(数据, ("word_number", "wordNumber", "word_count", "wordCount", "totalWords"))),
        "status": 规范化状态(读取任意字段(数据, ("creation_status", "creationStatus", "status", "book_status", "bookStatus"))),
        "chapter_count": 安全整数(读取任意字段(数据, ("serial_count", "serialCount", "chapter_count", "chapterCount", "chapter_number", "chapterNumber", "content_chapter_number"))),
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


def 清理标题(文本: Any) -> str:
    return 清理文本(文本).strip()


def 清理文本(文本: Any) -> str:
    文本 = re.sub(r"<[^>]+>", "", str(文本 or ""))
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
