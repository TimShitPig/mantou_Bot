from __future__ import annotations

import asyncio
import contextlib
import html
import json
import re
import time
from typing import Any

import aiohttp
from astrbot.api import logger


聚合API节点列表 = [
    "https://modtianmingyun-fanqie1.ms.show",
    "https://modtianmingyun-fanqie2.ms.show",
    "https://modtianmingyun-fanqie3.ms.show",
    "https://modtianmingyun-fanqie4.ms.show",
    "https://modtianmingyun-fanqie5.ms.show",
    "https://modtianmingyun-fanqie6.ms.show",
    "https://modtianmingyun-fanqie7.ms.show",
    "https://modtianmingyun-fanqie8.ms.show",
    "https://modtianmingyun-fanqie9.ms.show",
    "https://modtianmingyun-fanqie10.ms.show",
    "https://fanqieapi.6666633.xyz:9981",
    "https://fanqieapi.6666633.xyz:9982",
    "https://fanqieapi.6666633.xyz:9983",
]
聚合API地址 = 聚合API节点列表[0]
API前缀 = "/api/v1"
批次大小 = 200
最大并发批次 = 40
降级批次大小列表 = (200, 100, 50)
正文测速章节数 = 5
正文测速超时 = 10
节点缓存有效秒数 = 600
进度分段数 = 10
浏览器请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
可用节点缓存: dict[str, tuple[float, list[str]]] = {}


async def 准备番茄小说(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    if not 书籍编号:
        return {"success": False, "error": "聚合API没有获取到书籍ID"}

    try:
        详情响应, 目录响应 = await asyncio.gather(
            请求任一节点JSON(
                会话,
                f"{API前缀}/books/{书籍编号}",
                验证函数=lambda 响应: bool(提取内层数据(响应)),
            ),
            请求任一节点JSON(
                会话,
                f"{API前缀}/books/{书籍编号}/directory",
                验证函数=lambda 响应: bool(提取章节目录(提取内层数据(响应))),
            ),
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
            简化目录响应 = await 请求任一节点JSON(会话, f"{API前缀}/books/{书籍编号}/directory/fanqie")
            章节列表 = 提取章节目录(简化目录响应.get("data") if isinstance(简化目录响应, dict) else 简化目录响应)
        except Exception as 异常:
            logger.warning(f"番茄小说聚合API简化目录请求失败：book_id={书籍编号}, error={异常}")
    if not 章节列表:
        return {"success": False, "error": "聚合API没有获取到章节目录"}

    可用节点 = await 测速可用节点(会话, 书籍编号, 章节列表)
    if 可用节点:
        写入可用节点缓存(书籍编号, 可用节点)

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
    节点列表 = await 获取下载节点列表(会话, 书籍编号, 目录)
    信号量 = asyncio.Semaphore(最大并发批次)
    进度锁 = asyncio.Lock()
    节点锁 = asyncio.Lock()
    节点索引 = 0
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上一进度段 = 0
    logger.info(
        f"番茄小说聚合API章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%, "
        f"batches={len(批次列表)}, batch_size={批次大小}, concurrency={最大并发批次}, nodes={len(节点列表)}"
    )

    async def 取节点尝试顺序() -> list[str]:
        nonlocal 节点索引
        async with 节点锁:
            开始索引 = 节点索引
            节点索引 += 1
            return [节点列表[(开始索引 + 偏移) % len(节点列表)] for 偏移 in range(len(节点列表))]

    def 下一级批次大小(当前数量: int) -> int:
        for 大小 in 降级批次大小列表:
            if 当前数量 > 大小:
                return 大小
        return 0

    async def 请求批次直到成功(批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
        最后异常: Exception | None = None
        节点顺序 = await 取节点尝试顺序()
        for 尝试序号, 节点 in enumerate(节点顺序, start=1):
            try:
                return await 请求并映射批次(会话, 书籍编号, 批次, 节点)
            except Exception as 异常:
                最后异常 = 异常
                logger.warning(
                    f"番茄小说聚合API批次下载失败，换节点重试：book_id={书籍编号}, node={节点}, "
                    f"try={尝试序号}/{len(节点顺序)}, range={批次[0].get('index')}-{批次[-1].get('index')}, error={异常}"
                )
        raise RuntimeError(
            f"聚合API章节批次下载失败，已尝试 {len(节点顺序)} 个节点，"
            f"range={批次[0].get('index')}-{批次[-1].get('index')}，error={最后异常}"
        )

    async def 下载可降级批次(批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            return await 请求批次直到成功(批次)
        except Exception as 异常:
            新大小 = 下一级批次大小(len(批次))
            if 新大小 > 0:
                logger.warning(
                    f"番茄小说聚合API批次降级重试：book_id={书籍编号}, "
                    f"range={批次[0].get('index')}-{批次[-1].get('index')}, "
                    f"old_size={len(批次)}, new_size={新大小}, error={异常}"
                )
                结果列表: list[dict[str, Any]] = []
                子批次列表 = [批次[开始:开始 + 新大小] for 开始 in range(0, len(批次), 新大小)]
                for 子批次 in 子批次列表:
                    结果列表.extend(await 下载可降级批次(子批次))
                return 结果列表
            raise

    async def 下载批次(批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal 已完成, 成功数, 失败数, 上一进度段
        async with 信号量:
            批次结果 = await 下载可降级批次(批次)

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

    批次结果列表 = await asyncio.gather(*(下载批次(批次) for 批次 in 批次列表), return_exceptions=True)
    异常列表 = [项目 for 项目 in 批次结果列表 if isinstance(项目, Exception)]
    if 异常列表:
        raise RuntimeError(f"聚合API章节下载失败：{异常列表[0]}")
    结果列表: list[dict[str, Any]] = []
    for 批次结果 in 批次结果列表:
        if isinstance(批次结果, Exception):
            continue
        结果列表.extend(批次结果)
    return sorted(结果列表, key=lambda 项目: int(项目.get("index") or 0))


async def 请求并映射批次(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    批次: list[dict[str, Any]],
    节点: str | None = None,
) -> list[dict[str, Any]]:
    章节ID列表 = [str(章节.get("id") or "") for 章节 in 批次 if 章节.get("id")]
    if not 章节ID列表:
        raise RuntimeError("聚合API章节目录缺少章节ID")

    响应数据 = await 请求JSON(
        会话,
        f"{API前缀}/chapters/full",
        基础地址=节点,
        方法="POST",
        JSON数据={"book_id": 书籍编号, "item_ids": 章节ID列表},
        超时=90,
    )
    章节项列表 = 提取正文响应章节项(响应数据)
    结果列表 = 映射章节响应(批次, 章节项列表)
    成功数 = sum(1 for 项目 in 结果列表 if 项目.get("success"))
    if 成功数 < len(批次):
        raise RuntimeError(f"聚合API章节返回不完整：matched={成功数}/{len(批次)}")
    return 结果列表


async def 请求JSON(
    会话: aiohttp.ClientSession,
    路径: str,
    基础地址: str | None = None,
    方法: str = "GET",
    JSON数据: Any = None,
    超时: float = 30,
    **参数: Any,
) -> dict[str, Any]:
    基础地址 = (基础地址 or 聚合API地址).rstrip("/")
    请求参数 = {键: 值 for 键, 值 in 参数.items() if 值 not in (None, "")}
    async with 会话.request(
        方法.upper(),
        f"{基础地址}{路径}",
        params=请求参数 if 方法.upper() == "GET" else None,
        json=JSON数据 if 方法.upper() != "GET" else None,
        headers=浏览器请求头,
        timeout=aiohttp.ClientTimeout(total=超时, sock_connect=min(5, 超时), sock_read=超时),
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
    成功 = 响应数据.get("success")
    if 成功 is not True and str(返回码) not in ("0", "200"):
        消息 = 提取错误消息(响应数据) or "接口返回失败"
        raise RuntimeError(f"聚合API返回失败({路径})：{限制文本长度(消息, 300)}")
    return 响应数据


async def 请求任一节点JSON(
    会话: aiohttp.ClientSession,
    路径: str,
    验证函数: Any = None,
    方法: str = "GET",
    JSON数据: Any = None,
    **参数: Any,
) -> dict[str, Any]:
    任务列表 = [
        asyncio.create_task(请求JSON(会话, 路径, 基础地址=节点, 方法=方法, JSON数据=JSON数据, **参数))
        for 节点 in 聚合API节点列表
    ]
    错误列表: list[str] = []
    try:
        for 已完成任务 in asyncio.as_completed(任务列表):
            try:
                响应数据 = await 已完成任务
                if 验证函数 is None or 验证函数(响应数据):
                    return 响应数据
                错误列表.append("响应数据未通过验证")
            except Exception as 异常:
                错误列表.append(str(异常))
        raise RuntimeError("所有聚合API节点请求失败：" + "；".join(错误列表[:3]))
    finally:
        for 任务 in 任务列表:
            if not 任务.done():
                任务.cancel()
        for 任务 in 任务列表:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await 任务


async def 测速可用节点(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]] | None = None,
) -> list[str]:
    正文测试ID列表 = [str(章节.get("id") or "") for 章节 in (目录 or []) if 章节.get("id")][:正文测速章节数]

    async def 测试节点(节点: str) -> tuple[str, float] | None:
        开始时间 = time.perf_counter()
        try:
            await 请求JSON(会话, f"{API前缀}/books/{书籍编号}", 基础地址=节点, 超时=4)
            if 正文测试ID列表:
                响应数据 = await 请求JSON(
                    会话,
                    f"{API前缀}/chapters/full",
                    基础地址=节点,
                    方法="POST",
                    JSON数据={"book_id": 书籍编号, "item_ids": 正文测试ID列表},
                    超时=正文测速超时,
                )
                章节项 = 提取正文响应章节项(响应数据)
                测试结果 = 映射章节响应(
                    [{"id": 章节ID, "title": f"测速章节{序号}", "index": 序号} for 序号, 章节ID in enumerate(正文测试ID列表, start=1)],
                    章节项,
                )
                if sum(1 for 项目 in 测试结果 if 项目.get("success")) < len(正文测试ID列表):
                    return None
            return 节点, time.perf_counter() - 开始时间
        except Exception:
            return None

    结果列表 = await asyncio.gather(*(测试节点(节点) for 节点 in 聚合API节点列表))
    可用结果 = sorted((结果 for 结果 in 结果列表 if 结果), key=lambda 项目: 项目[1])
    节点列表 = [节点 for 节点, _ in 可用结果]
    if 节点列表:
        logger.info(f"番茄小说聚合API可用节点：book_id={书籍编号}, nodes={len(节点列表)}, fastest={节点列表[0]}")
    return 节点列表


async def 获取下载节点列表(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]] | None = None,
) -> list[str]:
    缓存时间, 缓存节点 = 可用节点缓存.get(str(书籍编号), (0.0, []))
    if 缓存节点 and time.time() - 缓存时间 <= 节点缓存有效秒数:
        return 缓存节点
    节点列表 = await 测速可用节点(会话, 书籍编号, 目录)
    if 节点列表:
        写入可用节点缓存(书籍编号, 节点列表)
        return 节点列表
    return 聚合API节点列表[:10]


def 写入可用节点缓存(书籍编号: str, 节点列表: list[str]) -> None:
    可用节点缓存[str(书籍编号)] = (time.time(), list(节点列表))


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


def 提取正文响应章节项(响应数据: Any) -> list[Any] | dict[str, Any]:
    if not isinstance(响应数据, dict):
        return []
    数据 = 响应数据.get("data")
    if isinstance(数据, dict):
        item_infos = 数据.get("item_infos")
        if isinstance(item_infos, dict):
            return item_infos
        章节列表 = 数据.get("chapters") or 读取路径(数据, ("data", "chapters"))
        if isinstance(章节列表, list):
            return 章节列表
        if any(isinstance(值, dict) and 提取正文(值) for 值 in 数据.values()):
            return 数据
    if isinstance(数据, list):
        return 数据
    return []


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

        for 字段名 in (
            "chapterListWithVolume",
            "lists",
            "list",
            "chapters",
            "chapterList",
            "item_data_list",
            "itemList",
            "item_list",
            "item_infos",
            "allItemIds",
        ):
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


def 映射章节响应(批次: list[dict[str, Any]], 原始章节项: Any) -> list[dict[str, Any]]:
    按编号索引: dict[str, dict[str, Any]] = {}
    顺序章节项: list[Any] = []
    if isinstance(原始章节项, dict):
        for 章节编号, 项目 in 原始章节项.items():
            if isinstance(项目, dict):
                按编号索引[str(章节编号)] = 项目
                内部编号 = 提取章节编号(项目)
                if 内部编号:
                    按编号索引[内部编号] = 项目
                顺序章节项.append(项目)
    elif isinstance(原始章节项, list):
        顺序章节项 = 原始章节项
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
        if 原始项 is None and len(顺序章节项) == len(批次) and isinstance(顺序章节项[索引], dict):
            原始项 = 顺序章节项[索引]
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
