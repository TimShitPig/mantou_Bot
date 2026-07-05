from __future__ import annotations

import html
import asyncio
import json
import os
import re
import urllib.parse
from typing import Any

import aiohttp
from astrbot.api import logger


析API批量正文地址 = "http://43.248.187.60:27042/multi-content"
析API批量正文key = os.environ.get("MANTOU_XI_API_KEY", "n48wkONBw8fcTl9VEVA-4ZN5KwRPso4MEDMhXw9myhchPp-OVkIqYr-i5tCBtsRw")
官方书籍信息地址 = "https://fanqienovel.com/api/book/info"
官方章节目录地址 = "https://fanqienovel.com/api/reader/directory/detail"
正文批量章节数 = 800
正文降级批量章节数 = 200
正文批次并发数 = 6
正文缺章补拉批量序列 = (50, 10, 1)
进度分段数 = 10

番茄域名正则 = re.compile("fanqienovel\\.com|changdunovel\\.com|fqnovel\\.com|novelfm\\.com", re.IGNORECASE)
长读短链正则 = re.compile("https?://(?:www\\.)?(?:changdunovel\\.com/t|m\\.novelfm\\.com/s)/[A-Za-z0-9_-]+/?", re.IGNORECASE)


async def 下载番茄小说(会话: aiohttp.ClientSession, 来源: str, 书籍编号: str = "", 基础书籍信息: dict[str, Any] | None = None) -> dict[str, Any]:
    准备结果 = await 准备番茄小说(会话, 来源, 书籍编号, 基础书籍信息)
    if not 准备结果.get("success"):
        return 准备结果
    实际书籍编号 = str(准备结果.get("book_id") or "")
    章节列表 = 准备结果.get("chapters") or []
    try:
        章节结果列表 = await 下载全部章节(会话, 实际书籍编号, 章节列表)
    except Exception as 异常:
        return {"success": False, "error": str(异常)}
    成功数 = sum(1 for 项目 in 章节结果列表 if 项目.get("success"))
    if 成功数 <= 0:
        return {"success": False, "error": "析API没有获取到可用章节正文"}
    if 成功数 < len(章节列表):
        return {"success": False, "error": f"析API章节正文不完整：成功 {成功数}/{len(章节列表)}"}
    return {**准备结果, "chapter_results": 章节结果列表}


async def 准备番茄小说(会话: aiohttp.ClientSession, 来源: str, 书籍编号: str = "", 基础书籍信息: dict[str, Any] | None = None) -> dict[str, Any]:
    实际书籍编号 = 书籍编号 or 提取书籍编号(来源)
    if not 实际书籍编号:
        return {"success": False, "error": "析API没有识别到书籍ID"}

    书籍信息 = 合并书籍信息(默认书籍信息(实际书籍编号), 基础书籍信息 or {})
    if not 有有效书籍详情(书籍信息):
        详情响应 = await 请求详情(会话, 实际书籍编号)
        详情数据 = 详情响应.get("data") if isinstance(详情响应, dict) else {}
        书籍信息 = 合并书籍信息(书籍信息, 从字典提取书籍信息(详情数据 if isinstance(详情数据, dict) else {}))

    目录响应 = await 请求目录(会话, 实际书籍编号)
    目录数据 = 目录响应.get("data") if isinstance(目录响应, dict) else 目录响应
    章节列表 = 提取官方章节目录(目录数据)
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


async def 下载全部章节(会话: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]]) -> list[dict[str, Any]]:
    总数 = len(目录)
    已完成 = 0
    成功数 = 0
    上一进度段 = 0
    结果列表: list[dict[str, Any]] = []
    if 总数 <= 0:
        return []
    logger.info(
        f"番茄小说析API章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%, batch_size={正文批量章节数}"
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
        logger.info(
            f"番茄小说析API章节进度：book_id={书籍编号}, progress={已完成}/{总数}, percent={百分比}%, success={成功数}"
        )

    分批列表 = [(序号, 目录[起点:起点 + 正文批量章节数]) for 序号, 起点 in enumerate(range(0, 总数, 正文批量章节数))]
    分批结果: dict[int, list[dict[str, Any]]] = {}
    信号量 = asyncio.Semaphore(正文批次并发数)

    async def 下载分批(序号: int, 批次: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        async with 信号量:
            return 序号, await 下载章节批次(会话, 书籍编号, 批次)

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
    for 序号, _批次 in 分批列表:
        结果列表.extend(分批结果.get(序号, []))
    if 成功数 != 总数:
        raise RuntimeError(f"析API章节正文不完整：成功 {成功数}/{总数}")
    return 结果列表


async def 下载章节批次(会话: aiohttp.ClientSession, 书籍编号: str, 批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
    章节编号列表 = [清理文本(章节.get("id")) for 章节 in 批次]
    缺少编号 = [str(章节.get("index") or 位置 + 1) for 位置, 章节 in enumerate(批次) if not 清理文本(章节.get("id"))]
    if 缺少编号:
        raise RuntimeError(f"析API章节目录缺少 item_id：{','.join(缺少编号[:10])}")
    正文映射 = await 请求批量正文(会话, 章节编号列表)
    批次结果: list[dict[str, Any]] = []
    缺失章节: list[str] = []
    空正文章节: list[str] = []
    for 章节 in 批次:
        章节编号 = 清理文本(章节.get("id"))
        if 章节编号 not in 正文映射:
            缺失章节.append(f"{章节.get('index')}:{章节编号}")
            正文 = ""
            成功 = False
        else:
            正文 = 清理正文(正文映射.get(章节编号, ""))
            成功 = True
            if not 正文:
                空正文章节.append(f"{章节.get('index')}:{章节编号}")
        批次结果.append({
            **章节,
            "title": 清理文本(章节.get("title")) or f"第{章节.get('index')}章",
            "content": 正文,
            "success": 成功,
        })
    if 缺失章节:
        if len(缺失章节) == len(批次) and len(批次) > 正文降级批量章节数:
            logger.warning(
                f"番茄小说析API批量正文整批不完整，自动降级小批重试：book_id={书籍编号}, "
                f"range={批次[0].get('index')}-{批次[-1].get('index')}, "
                f"batch_size={len(批次)}, fallback_size={正文降级批量章节数}"
            )
            降级结果列表: list[dict[str, Any]] = []
            for 起点 in range(0, len(批次), 正文降级批量章节数):
                子批次 = 批次[起点:起点 + 正文降级批量章节数]
                降级结果列表.extend(await 下载章节批次(会话, 书籍编号, 子批次))
            return 降级结果列表
        logger.warning(
            f"番茄小说析API部分章节缺失，开始定向补拉：book_id={书籍编号}, "
            f"missing={限制文本长度(','.join(缺失章节), 300)}"
        )
        正文映射 = await 补拉缺失章节正文(会话, 书籍编号, 批次, 正文映射)
        批次结果, 缺失章节, 空正文章节 = 构造析API批次结果(批次, 正文映射)
        if 缺失章节:
            raise RuntimeError(
                f"析API章节正文不完整：book_id={书籍编号}, missing={限制文本长度(','.join(缺失章节), 300)}"
            )
    if 空正文章节:
        if len(空正文章节) == len(批次):
            raise RuntimeError(
                f"析API章节正文为空：book_id={书籍编号}, empty={限制文本长度(','.join(空正文章节), 300)}"
            )
        logger.warning(
            f"番茄小说析API部分章节正文为空，保留章节标题继续：book_id={书籍编号}, "
            f"empty={限制文本长度(','.join(空正文章节), 300)}"
        )
    return 批次结果


def 构造析API批次结果(批次: list[dict[str, Any]], 正文映射: dict[str, str]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    批次结果: list[dict[str, Any]] = []
    缺失章节: list[str] = []
    空正文章节: list[str] = []
    for 章节 in 批次:
        章节编号 = 清理文本(章节.get("id"))
        if 章节编号 not in 正文映射:
            缺失章节.append(f"{章节.get('index')}:{章节编号}")
            正文 = ""
            成功 = False
        else:
            正文 = 清理正文(正文映射.get(章节编号, ""))
            成功 = True
            if not 正文:
                空正文章节.append(f"{章节.get('index')}:{章节编号}")
        批次结果.append({
            **章节,
            "title": 清理文本(章节.get("title")) or f"第{章节.get('index')}章",
            "content": 正文,
            "success": 成功,
        })
    return 批次结果, 缺失章节, 空正文章节


async def 补拉缺失章节正文(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    批次: list[dict[str, Any]],
    正文映射: dict[str, str],
) -> dict[str, str]:
    合并映射 = dict(正文映射)
    缺失章节 = [章节 for 章节 in 批次 if 清理文本(章节.get("id")) and 清理文本(章节.get("id")) not in 合并映射]
    for 轮次, 批量大小 in enumerate(正文缺章补拉批量序列, start=1):
        if not 缺失章节:
            break
        logger.warning(
            f"番茄小说析API缺章补拉：book_id={书籍编号}, round={轮次}/{len(正文缺章补拉批量序列)}, "
            f"batch_size={批量大小}, missing={len(缺失章节)}"
        )
        本轮仍缺失: list[dict[str, Any]] = []
        for 起点 in range(0, len(缺失章节), 批量大小):
            子批次 = 缺失章节[起点:起点 + 批量大小]
            子编号列表 = [清理文本(章节.get("id")) for 章节 in 子批次 if 清理文本(章节.get("id"))]
            if not 子编号列表:
                continue
            子映射 = await 请求批量正文(会话, 子编号列表)
            合并映射.update(子映射)
            for 章节 in 子批次:
                章节编号 = 清理文本(章节.get("id"))
                if 章节编号 not in 合并映射:
                    本轮仍缺失.append(章节)
        缺失章节 = 本轮仍缺失
    if 缺失章节:
        logger.warning(
            f"番茄小说析API缺章补拉后仍缺失：book_id={书籍编号}, "
            f"missing={限制文本长度(格式化缺失章节(缺失章节), 300)}"
        )
    return 合并映射


def 格式化缺失章节(章节列表: list[dict[str, Any]]) -> str:
    return ",".join(f"{章节.get('index')}:{清理文本(章节.get('id'))}" for 章节 in 章节列表)


async def 请求详情(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    try:
        async with 会话.get(官方书籍信息地址, params={"bookId": 书籍编号}, timeout=20) as 响应:
            文本 = await 响应.text()
            if 响应.status >= 400:
                logger.debug(f"番茄小说析API官方详情HTTP错误：book_id={书籍编号}, status={响应.status}")
                return {}
            try:
                响应数据 = json.loads(文本)
            except Exception as 异常:
                logger.debug(f"番茄小说析API官方详情JSON解析失败：book_id={书籍编号}, error={异常}")
                return {}
    except Exception as 异常:
        logger.debug(f"番茄小说析API官方详情请求失败：book_id={书籍编号}, error={异常}")
        return {}
    return 响应数据 if isinstance(响应数据, dict) else {}


async def 请求目录(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    try:
        async with 会话.get(官方章节目录地址, params={"bookId": 书籍编号}, timeout=30) as 响应:
            文本 = await 响应.text()
            if 响应.status >= 400:
                logger.debug(f"番茄小说析API官方目录HTTP错误：book_id={书籍编号}, status={响应.status}")
                return {}
            try:
                响应数据 = json.loads(文本)
            except Exception as 异常:
                logger.debug(f"番茄小说析API官方目录JSON解析失败：book_id={书籍编号}, error={异常}")
                return {}
    except Exception as 异常:
        logger.debug(f"番茄小说析API官方目录请求失败：book_id={书籍编号}, error={异常}")
        return {}
    return 响应数据 if isinstance(响应数据, dict) else {}


async def 请求批量正文(会话: aiohttp.ClientSession, 章节编号列表: list[str]) -> dict[str, str]:
    有效编号列表 = [清理文本(章节编号) for 章节编号 in 章节编号列表 if 清理文本(章节编号)]
    if not 有效编号列表:
        return {}
    if len(有效编号列表) > 正文批量章节数:
        raise ValueError(f"析API单次最多请求 {正文批量章节数} 章")
    请求参数 = {"item_ids": ",".join(有效编号列表), "key": 析API批量正文key}
    async with 会话.get(析API批量正文地址, params=请求参数, timeout=180) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f"析API HTTP {响应.status}: {限制文本长度(文本, 120)}")
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f"析API JSON解析失败：{限制文本长度(文本, 120)}") from 异常
    正文项目列表 = 提取批量正文项目列表(响应数据)
    正文映射: dict[str, str] = {}
    for 项目 in 正文项目列表:
        if not isinstance(项目, dict):
            continue
        章节编号 = 清理文本(读取任意字段(项目, ("item_id", "itemId", "chapter_id", "chapterId", "id")))
        if not 章节编号:
            continue
        正文映射[章节编号] = 提取正文(项目)
    return 正文映射


def 提取批量正文项目列表(响应数据: Any) -> list[Any]:
    if isinstance(响应数据, list):
        return 响应数据
    if not isinstance(响应数据, dict):
        raise RuntimeError("析API返回格式不是数组")
    for 键 in ("data", "chapters", "list", "items", "result"):
        值 = 响应数据.get(键)
        if isinstance(值, list):
            return 值
        if isinstance(值, dict):
            for 子键 in ("chapters", "list", "items"):
                子值 = 值.get(子键)
                if isinstance(子值, list):
                    return 子值
    返回码 = 响应数据.get("code")
    成功 = 响应数据.get("success")
    消息 = 响应数据.get("message") or 响应数据.get("msg") or 响应数据.get("error")
    if str(返回码) not in ("0", "1", "200", "None") or 成功 is False or 消息:
        raise RuntimeError(f"析API返回失败：{限制文本长度(消息 or 响应数据, 200)}")
    raise RuntimeError("析API返回格式缺少正文列表")


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


def 提取官方章节目录(数据: Any) -> list[dict[str, Any]]:
    if not isinstance(数据, dict):
        return 提取章节目录(数据)
    章节列表: list[dict[str, Any]] = []
    卷列表 = 数据.get("chapterListWithVolume")
    if isinstance(卷列表, list):
        for 卷 in 卷列表:
            if not isinstance(卷, list):
                continue
            for 章节 in 卷:
                if not isinstance(章节, dict):
                    continue
                章节编号 = 清理文本(读取任意字段(章节, ("itemId", "item_id", "chapter_id", "chapterId", "id")))
                标题 = 清理文本(读取任意字段(章节, ("title", "chapter_title", "name")))
                序号 = 安全整数(读取任意字段(章节, ("realChapterOrder", "chapter", "index", "order", "chapter_index", "chapterIndex")))
                if 序号 <= 0:
                    序号 = len(章节列表) + 1
                if 章节编号 or 标题:
                    章节列表.append({"id": 章节编号, "title": 标题 or f"第{序号}章", "index": 序号})
    if not 章节列表:
        章节列表 = 提取章节目录(数据)
    if not 章节列表:
        全部编号 = 数据.get("allItemIds")
        if isinstance(全部编号, list):
            for 位置, 章节编号 in enumerate(全部编号, start=1):
                章节列表.append({"id": 清理文本(章节编号), "title": f"第{位置}章", "index": 位置})
    去重结果: list[dict[str, Any]] = []
    已见集合: set[tuple[str, int]] = set()
    for 位置, 项目 in enumerate(章节列表, start=1):
        项目["index"] = 安全整数(项目.get("index")) or 位置
        键 = (清理文本(项目.get("id")), int(项目.get("index") or 0))
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


def 有有效书籍详情(书籍信息: dict[str, Any]) -> bool:
    标题 = str(书籍信息.get("title") or "")
    作者 = str(书籍信息.get("author") or "")
    return bool(标题 and not 标题.startswith("番茄小说") and 作者 and 作者 != "未知")


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
