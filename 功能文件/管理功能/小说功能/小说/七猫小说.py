from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import random
import re
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp
from astrbot.api import logger

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception as exc:
    小说网盘 = None
    logger.warning(f"小说网盘模块加载失败：错误={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：错误={exc}")

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except Exception:
    AES = None
    unpad = None


签名密钥 = "d3dGiJc651gSQ8w1"
应用ID = "com.kmxs.reader"
渠道名 = "qm-guanfang_lf"
应用版本列表 = ["79105"]
解密密钥 = bytes.fromhex("32343263636238323330643730396531")
下载并发数 = 200
批量章节数 = 50
批量下载并发数 = 下载并发数
进度日志分段数 = 10
下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
QM参数字符映射 = {
    "+": "P", "/": "X", "0": "M", "1": "U", "2": "l", "3": "E", "4": "r", "5": "Y",
    "6": "W", "7": "b", "8": "d", "9": "J", "A": "9", "B": "s", "C": "a", "D": "I",
    "E": "0", "F": "o", "G": "y", "H": "_", "I": "H", "J": "G", "K": "i", "L": "t",
    "M": "g", "N": "N", "O": "A", "P": "8", "Q": "F", "R": "k", "S": "3", "T": "h",
    "U": "f", "V": "R", "W": "q", "X": "C", "Y": "4", "Z": "p", "a": "m", "b": "B",
    "c": "O", "d": "u", "e": "c", "f": "6", "g": "K", "h": "x", "i": "5", "j": "T",
    "k": "-", "l": "2", "m": "z", "n": "S", "o": "Z", "p": "1", "q": "V", "r": "v",
    "s": "j", "t": "Q", "u": "7", "v": "D", "w": "w", "x": "n", "y": "L", "z": "e",
}


def 获取七猫小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[str] | None:
    下载关键词 = (
        提取直接七猫链接参数(命令文本)
        or 提取事件七猫链接(event)
    )
    if 下载关键词 is None:
        return None
    return 生成下载回复流(event, 下载关键词, 配置)


async def 生成下载回复流(event: Any, 关键词: str, 配置: Any = None) -> AsyncIterator[str]:
    if not 关键词:
        yield "没有识别到七猫小说链接"
        return
    if AES is None or unpad is None:
        logger.warning("七猫小说下载失败：缺少 pycryptodome 依赖")
        yield "下载失败"
        return

    try:
        connector = aiohttp.TCPConnector(
            limit=下载并发数,
            limit_per_host=下载并发数,
            ttl_dns_cache=300,
            keepalive_timeout=30,
        )
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=30)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            下载目标 = await 解析七猫下载目标(session, 关键词)
            书籍编号 = 下载目标.get("book_id", "")
            if not 书籍编号:
                yield "没有找到可下载的七猫小说"
                return
            是否短篇 = 下载目标.get("type") == "short"

            详情 = await 获取小说详情(session, 书籍编号, 是否短篇)
            目录 = await 获取小说目录(session, 书籍编号, 是否短篇)
            if not 目录:
                logger.warning(f"七猫小说下载失败：书籍编号={书籍编号}, 错误=没有获取到章节目录")
                yield "下载失败"
                return
            if not str(详情.get("words_num") or "").strip():
                目录字数 = sum(安全整数(章节.get("words") or 章节.get("word_count") or 章节.get("chapter_words"), 0) for 章节 in 目录)
                if 目录字数:
                    详情["words_num"] = str(目录字数)
            if not str(详情.get("chapters") or "").strip():
                详情["chapters"] = str(len(目录))

            logger.info(
                f"七猫小说开始下载：书籍编号={书籍编号}, "
                f"类型={'短篇' if 是否短篇 else '整本'}, "
                f"书名={详情.get('title')}, 作者={详情.get('author')}, 章节数={len(目录)}"
            )
            yield 格式化下载提示(详情, len(目录))

            章节内容 = await 下载全部章节(session, 书籍编号, 目录, 是否短篇)
            成功章节 = [项目 for 项目 in 章节内容 if 项目["content"]]
            if not 成功章节:
                logger.warning(f"七猫小说下载失败：书籍编号={书籍编号}, 错误=没有获取到可用章节正文")
                yield "下载失败"
                return

            文件名, 文件内容 = 生成小说文件内容(书籍编号, 详情, 目录, 章节内容)
            logger.info(
                f"七猫小说章节下载完成：书籍编号={书籍编号}, "
                f"书名={详情.get('title')}, 成功={len(成功章节)}, 总数={len(目录)}, 文件大小={len(文件内容)}"
            )
            发送结果 = await 准备发送文本文件给当前会话(
                event,
                文件名,
                文件内容,
                配置,
                书名=详情.get("title"),
                作者=详情.get("author"),
            )
            if 发送结果.get("sent"):
                启动百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
                return
            降级文本 = str(发送结果.get("fallback_text") or "")
            if 降级文本:
                try:
                    yield 降级文本
                finally:
                    启动百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
                return
            logger.warning(f"七猫小说完成消息发送失败：书籍编号={书籍编号}, 文件={文件名}, 错误={发送结果.get('error')}")
            yield "文件发送失败，请稍后再试"
            return
    except Exception as exc:
        logger.warning(f"七猫小说下载失败：关键词={关键词}, 错误={exc}")
        yield "下载失败"
        return

async def 搜索小说(session: aiohttp.ClientSession, 关键词: str) -> list[dict[str, Any]]:
    参数 = 签名参数({
        "extend": "",
        "tab": "0",
        "gender": "0",
        "refresh_state": "8",
        "page": "1",
        "wd": 关键词,
        "is_short_story_user": "0",
    })
    数据 = await 请求JSON(session, "https://api-bc.wtzw.com/search/v1/words", 参数, 生成请求头("00000000", "api-bc.wtzw.com"))
    书籍列表 = 读取字段路径(数据, ("data", "books"))
    return [书籍 for 书籍 in (书籍列表 or []) if isinstance(书籍, dict)]


async def 解析书籍编号(session: aiohttp.ClientSession, 关键词: str) -> str:
    链接编号 = 提取书籍编号(关键词)
    if 链接编号:
        return 链接编号
    搜索结果 = await 搜索小说(session, 关键词)
    if not 搜索结果:
        return ""
    return str(搜索结果[0].get("id") or "")


async def 解析七猫下载目标(session: aiohttp.ClientSession, 关键词: str) -> dict[str, str]:
    链接类型 = 解析七猫链接类型(关键词)
    链接编号 = 提取书籍编号(关键词)
    if 链接编号:
        return {"book_id": 链接编号, "type": 链接类型}
    搜索结果 = await 搜索小说(session, 关键词)
    if not 搜索结果:
        return {"book_id": "", "type": 链接类型}
    return {"book_id": str(搜索结果[0].get("id") or ""), "type": 链接类型}


async def 获取小说详情(session: aiohttp.ClientSession, 书籍编号: str, 是否短篇: bool = False) -> dict[str, Any]:
    if 是否短篇:
        数据 = await 请求JSON(
            session,
            "https://api-bc.wtzw.com/api/v1/story/detail",
            {},
            生成请求头(书籍编号, "api-bc.wtzw.com"),
            方法="POST",
            表单=签名参数({"bookid": 书籍编号, "book_privacy": "0", "ex_bookids": ""}),
        )
    else:
        数据 = await 请求JSON(
            session,
            "https://api-bc.wtzw.com/api/v1/reader/detail",
            签名参数({"id": 书籍编号}),
            生成请求头(书籍编号, "api-bc.wtzw.com"),
        )
    详情 = 数据.get("data") if isinstance(数据, dict) else {}
    if not isinstance(详情, dict) or not 详情:
        raise RuntimeError("小说详情接口没有返回有效数据")
    if isinstance(详情.get("book"), dict):
        详情 = {**详情.get("book", {}), **详情}
    return {
        "title": 清理网页文本(读取首个字段(详情, ("title", "book_name", "name", "share_title")) or f"七猫小说{书籍编号}"),
        "author": 清理网页文本(读取首个字段(详情, ("author", "author_name", "pen_name")) or 读取字段路径(详情, ("author_info", "name")) or "未知"),
        "intro": 清理网页文本(读取首个字段(详情, ("intro", "description", "desc", "book_intro")) or ""),
        "words_num": 读取首个字段(详情, ("words_num", "word_count", "words", "total_words")) or "",
        "is_over": 读取首个字段(详情, ("is_over", "is_finish", "finish", "completed")) or ("1" if 是否短篇 else ""),
        "chapters": 读取首个字段(详情, ("chapters", "chapter_count", "chapter_num", "total_chapters")) or "",
        "chapter_list_desc": 清理网页文本(详情.get("chapter_list_desc") or ""),
        "category_over_words": 清理网页文本(详情.get("category_over_words") or ""),
        "tags": "、".join(
            清理网页文本(标签.get("title") or "")
            for 标签 in 详情.get("book_tag_list", [])
            if isinstance(标签, dict) and 标签.get("title")
        ),
    }


async def 获取小说目录(session: aiohttp.ClientSession, 书籍编号: str, 是否短篇: bool = False) -> list[dict[str, Any]]:
    数据 = await 请求JSON(
        session,
        "https://api-ks.wtzw.com/api/v1/chapter/chapter-list",
        签名参数({"chapter_ver": "0", "id": 书籍编号, "reader_type": "4" if 是否短篇 else "0"}),
        生成请求头(书籍编号, "api-ks.wtzw.com"),
    )
    章节列表 = 读取字段路径(数据, ("data", "chapter_lists")) or []
    目录 = [章节 for 章节 in 章节列表 if isinstance(章节, dict) and 章节.get("id")]
    return sorted(目录, key=lambda 章节: int(章节.get("chapter_sort") or 0))


async def 下载全部章节(
    session: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
    是否短篇: bool = False,
) -> list[dict[str, str]]:
    批量信号量 = asyncio.Semaphore(批量下载并发数)
    单章信号量 = asyncio.Semaphore(下载并发数)
    总数 = len(目录)
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上次日志进度 = 0
    进度锁 = asyncio.Lock()

    logger.info(f"七猫小说章节进度：书籍编号={书籍编号}, 进度=0/{总数}, 百分比=0%")

    async def 记录进度(完成增量: int, 成功增量: int) -> None:
        nonlocal 已完成, 成功数, 失败数, 上次日志进度
        async with 进度锁:
            已完成 += 完成增量
            成功数 += 成功增量
            失败数 += max(完成增量 - 成功增量, 0)

            当前进度 = 进度日志分段数 if 已完成 >= 总数 else int(已完成 * 进度日志分段数 / 总数)
            if 当前进度 <= 上次日志进度 and 已完成 < 总数:
                return
            上次日志进度 = 当前进度
            百分比 = int(已完成 * 100 / 总数) if 总数 else 100
            logger.info(
                f"七猫小说章节进度：书籍编号={书籍编号}, "
                f"进度={已完成}/{总数}, 百分比={百分比}%, 成功={成功数}, 失败={失败数}"
            )

    async def 下载单章(章节: dict[str, Any]) -> dict[str, str]:
        async with 单章信号量:
            标题 = 清理网页文本(章节.get("title") or f"第{章节.get('chapter_sort', '')}章")
            章节编号 = str(章节.get("id"))
            try:
                正文 = await 获取章节正文(session, 书籍编号, 章节编号, 是否短篇)
                await 记录进度(1, 1 if 正文 else 0)
                return {"id": 章节编号, "title": 标题, "content": 正文}
            except Exception as exc:
                logger.warning(f"七猫章节下载失败：书籍编号={书籍编号}, 章节编号={章节编号}, 错误={exc}")
                await 记录进度(1, 0)
                return {"id": 章节编号, "title": 标题, "content": ""}

    async def 下载批次(批次目录: list[dict[str, Any]], 批次序号: int, 批次数量: int) -> list[dict[str, str]]:
        async with 批量信号量:
            try:
                章节编号列表 = [str(章节.get("id")) for 章节 in 批次目录 if 章节.get("id")]
                正文映射 = await 获取批量章节正文(session, 书籍编号, 章节编号列表, 是否短篇)
                结果列表 = []
                成功增量 = 0
                for 章节 in 批次目录:
                    标题 = 清理网页文本(章节.get("title") or f"第{章节.get('chapter_sort', '')}章")
                    章节编号 = str(章节.get("id"))
                    正文 = 正文映射.get(章节编号, "")
                    if 正文:
                        成功增量 += 1
                    结果列表.append({"id": 章节编号, "title": 标题, "content": 正文})
                await 记录进度(len(批次目录), 成功增量)
                if 成功增量 < len(批次目录):
                    缺失数量 = len(批次目录) - 成功增量
                    logger.warning(
                        f"七猫小说批量正文缺失：书籍编号={书籍编号}, 批次={批次序号}/{批次数量}, "
                        f"缺失={缺失数量}, 批量章节数={len(批次目录)}"
                    )
                return 结果列表
            except Exception as exc:
                logger.warning(
                    f"七猫小说批量章节下载失败，回退单章：书籍编号={书籍编号}, "
                    f"批次={批次序号}/{批次数量}, 批量章节数={len(批次目录)}, 错误={exc}"
                )
        return await asyncio.gather(*(下载单章(章节) for 章节 in 批次目录))

    批次列表 = [目录[开始:开始 + 批量章节数] for 开始 in range(0, len(目录), 批量章节数)]
    批次结果 = await asyncio.gather(*(
        下载批次(批次, 序号, len(批次列表))
        for 序号, 批次 in enumerate(批次列表, 1)
    ))
    return [章节 for 批次 in 批次结果 for 章节 in 批次]


async def 获取批量章节正文(
    session: aiohttp.ClientSession,
    书籍编号: str,
    章节编号列表: list[str],
    是否短篇: bool = False,
) -> dict[str, str]:
    if not 章节编号列表:
        return {}
    参数 = {"id": 书籍编号, "chapterIds": ",".join(章节编号列表)}
    if 是否短篇:
        参数["reader_agent"] = "1"
    数据 = await 请求JSON(
        session,
        "https://api-ks.wtzw.com/api/v1/chapter/preload-chapter-content",
        签名参数(参数),
        生成请求头(书籍编号, "api-ks.wtzw.com"),
    )
    章节列表 = (
        读取字段路径(数据, ("data", "chapter_contents"))
        or 读取字段路径(数据, ("data", "chapter_content"))
        or []
    )
    正文映射: dict[str, str] = {}
    for 项目 in 章节列表:
        if not isinstance(项目, dict):
            continue
        章节编号 = str(读取首个字段(项目, ("id", "chapter_id", "chapterId")) or "")
        加密正文 = 读取首个字段(项目, ("content", "chapter_content", "body"))
        if 章节编号 and 加密正文:
            正文映射[章节编号] = 解密正文(str(加密正文))
    return 正文映射


async def 获取章节正文(session: aiohttp.ClientSession, 书籍编号: str, 章节编号: str, 是否短篇: bool = False) -> str:
    参数 = {"id": 书籍编号, "chapterId": 章节编号}
    if 是否短篇:
        参数["reader_agent"] = "1"
    数据 = await 请求JSON(
        session,
        "https://api-ks.wtzw.com/api/v1/chapter/content",
        签名参数(参数),
        生成请求头(书籍编号, "api-ks.wtzw.com"),
    )
    加密正文 = 读取字段路径(数据, ("data", "content"))
    if not 加密正文:
        错误 = 读取字段路径(数据, ("errors", "details")) or "章节正文为空"
        raise RuntimeError(str(错误))
    return 解密正文(str(加密正文))


async def 请求JSON(
    session: aiohttp.ClientSession,
    地址: str,
    参数: dict[str, Any] | None,
    请求头: dict[str, str],
    方法: str = "GET",
    表单: dict[str, Any] | None = None,
) -> dict[str, Any]:
    请求方法 = 方法.upper()
    if 请求方法 == "POST":
        请求上下文 = session.post(地址, params=参数 or None, data=表单 or {}, headers=请求头)
    else:
        请求上下文 = session.get(地址, params=参数 or None, headers=请求头)
    async with 请求上下文 as response:
        文本 = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}: {文本[:120]}")
        try:
            数据 = await response.json(content_type=None)
        except Exception as exc:
            raise RuntimeError(f"JSON解析失败：{文本[:120]}") from exc
        if isinstance(数据, dict) and 数据.get("errors"):
            详情 = 读取字段路径(数据, ("errors", "details")) or 读取字段路径(数据, ("errors", "title"))
            raise RuntimeError(str(详情 or "接口返回错误"))
        return 数据


def 生成小说文件内容(
    书籍编号: str,
    详情: dict[str, Any],
    目录: list[dict[str, Any]],
    章节内容: list[dict[str, str]],
) -> tuple[str, bytes]:
    标题 = 详情.get("title") or f"七猫小说{书籍编号}"
    文件名 = 生成小说文件名(书籍编号, 详情)
    简介 = str(详情.get("intro") or "").strip()

    内容列表 = [
        文件声明,
        "",
        f"名称：{标题}",
        f"作者：{详情.get('author') or '未知'}",
        f"状态：{获取状态文本(详情)}",
        f"字数：{格式化字数(详情.get('words_num'))}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(目录)}",
        "",
    ]
    if 简介:
        内容列表.extend(["简介：", 简介, ""])

    for 章节 in 章节内容:
        if not 章节["content"]:
            continue
        内容列表.append(章节["title"])
        内容列表.append("")
        内容列表.append(去除章节正文重复标题(章节["title"], 章节["content"]))
        内容列表.append("")

    return 文件名, "\n".join(内容列表).encode("utf-8")


def 生成小说文件名(书籍编号: str, 详情: dict[str, Any]) -> str:
    状态 = 获取状态文本(详情)
    标题 = 清理文件名(详情.get("title") or f"七猫小说{书籍编号}")
    作者 = 清理文件名(详情.get("author") or "未知")
    return f"[{状态}]书名：{标题} 作者：{作者}.txt"


def 格式化下载提示(详情: dict[str, Any], 目录数量: int) -> str:
    return "\n".join([
        f"书名：{详情.get('title') or '未知'}",
        f"作者：{详情.get('author') or '未知'}",
        f"状态：{获取状态文本(详情)}",
        f"章节：{获取章节数量文本(详情, 目录数量)}",
        f"字数：{格式化字数(详情.get('words_num'))}",
        "",
        "正在下载中请稍等.....",
    ])


def 获取状态文本(详情: dict[str, Any]) -> str:
    if str(详情.get("is_over")) == "1":
        return "完结"
    for 字段名 in ("category_over_words", "chapter_list_desc"):
        文本 = str(详情.get(字段名) or "")
        if "完结" in 文本:
            return "完结"
        if "连载" in 文本:
            return "连载"
    return "连载"


def 获取章节数量文本(详情: dict[str, Any], 目录数量: int) -> str:
    章节数 = str(详情.get("chapters") or "").strip()
    if not 章节数:
        章节数 = str(目录数量)
    return f"{章节数} 章"


def 格式化字数(字数: Any) -> str:
    文本 = str(字数 or "").strip()
    if not 文本:
        return "未知"
    数字文本 = re.sub(r"[\s,，]", "", 文本)
    if 数字文本.endswith("字"):
        数字文本 = 数字文本[:-1]
    if 数字文本.isdigit():
        数值 = int(数字文本)
        if 数值 >= 10000:
            万字 = f"{数值 / 10000:.1f}".rstrip("0").rstrip(".")
            return f"{万字}万字"
        return f"{数值}字"
    return 文本



async def 准备发送文本文件给当前会话(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    logger.info(f"七猫小说准备上传：文件={文件名}, 大小={len(文件内容)}")
    缓存路径 = 写入下载缓存文件(文件名, 文件内容)
    logger.info(f"七猫小说写入下载缓存：文件={缓存路径}, 大小={len(文件内容)}")
    if 小说网盘 is None:
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "小说网盘模块未加载"}
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        网盘名称 = str(网盘结果.get("provider") or "小说网盘")
        if not 网盘结果.get("success"):
            logger.warning(f"七猫小说主网盘上传失败：网盘={网盘名称}, 文件={文件名}, 错误={网盘结果.get('error')}")
            删除下载缓存文件(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(网盘结果.get("error") or "小说网盘未启用")}
        完成结果 = await 小说网盘.发送小说下载完成链接(event, 书名, 作者, str(网盘结果.get("share_url") or ""))
        if 完成结果.get("sent"):
            logger.info(f"七猫小说主网盘上传并发送完成按钮成功：网盘={网盘名称}, 文件={文件名}")
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 缓存路径, "error": str(完成结果.get("error") or "")}
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(完成结果.get("error") or "完成按钮发送失败")}
    except Exception as exc:
        logger.warning(f"七猫小说主网盘上传或完成消息发送失败：文件={文件名}, 错误={exc}")
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(exc)}


def 启动百度后台上传并清理源文件(配置: Any, 源缓存路径: Any, 文件名: str, 发送缓存路径: Any = None) -> None:
    if not 源缓存路径:
        return

    async def 执行上传并清理() -> None:
        try:
            if 百度网盘 is not None:
                百度结果 = await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
                if 百度结果.get("success"):
                    logger.info(f"七猫小说百度网盘后台上传成功：文件={文件名}, 文件编号={百度结果.get('file_id')}")
                elif 百度结果.get("skipped"):
                    logger.info(f"七猫小说百度网盘后台上传按状态规则跳过：文件={文件名}")
                elif 百度结果.get("enabled"):
                    logger.warning(f"七猫小说百度网盘后台上传失败，不影响QQ发送：文件={文件名}, 错误={百度结果.get('error')}")
        except Exception as exc:
            logger.warning(f"七猫小说百度网盘后台上传异常，不影响QQ发送：文件={文件名}, 错误={exc}")
        finally:
            if str(源缓存路径) != str(发送缓存路径 or ""):
                删除下载缓存文件(源缓存路径)

    try:
        asyncio.create_task(执行上传并清理())
    except RuntimeError:
        if str(源缓存路径) != str(发送缓存路径 or ""):
            删除下载缓存文件(源缓存路径)


def 删除下载缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    if not 小说缓存工具.删除下载缓存文件(缓存路径):
        logger.debug(f"七猫小说下载缓存仍在等待续传：文件={缓存路径}")
        return
    try:
        logger.info(f"七猫小说下载缓存文件已删除：文件={缓存路径}")
    except Exception as exc:
        logger.warning(f"七猫小说下载缓存文件删除失败：文件={缓存路径}, 错误={exc}")


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(缓存路径)
    return 缓存路径


def 生成不冲突缓存路径(文件名: str) -> Path:
    安全文件名 = Path(清理文件名(文件名)).name or "七猫小说.txt"
    if not 安全文件名.lower().endswith(".txt"):
        安全文件名 = f"{安全文件名}.txt"
    缓存路径 = 下载缓存目录 / 安全文件名
    if not 缓存路径.exists():
        return 缓存路径

    后缀 = 缓存路径.suffix
    主名 = 缓存路径.stem
    for 序号 in range(1, 1000):
        候选路径 = 下载缓存目录 / f"{主名}_{序号}{后缀}"
        if not 候选路径.exists():
            return 候选路径
    raise RuntimeError("下载缓存目录中同名文件过多")


def 签名参数(参数: dict[str, Any]) -> dict[str, Any]:
    结果 = dict(参数)
    待签名 = "".join(f"{键}={转换请求值(结果[键])}" for 键 in sorted(结果)) + 签名密钥
    结果["sign"] = hashlib.md5(待签名.encode("utf-8")).hexdigest()
    return 结果


def 生成请求头(书籍编号: str, 主机: str = "") -> dict[str, str]:
    随机源 = random.Random(书籍编号)
    请求头 = {
        "AUTHORIZATION": "",
        "app-version": 随机源.choice(应用版本列表),
        "application-id": 应用ID,
        "channel": 渠道名,
        "is-white": "0",
        "net-env": "1",
        "platform": "android",
        "qm-params": 生成QM参数(主机),
        "reg": "0",
    }
    待签名 = "".join(f"{键}={请求头[键]}" for 键 in sorted(请求头)) + 签名密钥
    请求头["sign"] = hashlib.md5(待签名.encode("utf-8")).hexdigest()
    请求头["no-permiss"] = "0"
    请求头["User-Agent"] = f"Android 7.91.5 {应用ID}"
    return 请求头


def 转换请求值(值: Any) -> str:
    if 值 is True:
        return "1"
    if 值 is False:
        return "0"
    return "" if 值 is None else str(值)


def 生成QM参数(主机: str = "") -> str:
    参数 = {
        "uuid": "",
        "imei": "",
        "qimei": "",
        "uid": "",
        "oaid-no-cache": "",
        "oaid": "",
        "smid": "",
        "mac": "",
        "brand": "samsung",
        "sub-brand": "",
        "phone-level": "",
        "model": "SM-G9750",
        "sys-ver": "9",
        "android-id": "dc83b70db61dac96",
        "sourceuid": "",
        "static_score": "",
        "oaid_status": "",
        "session-id": "",
        "cf": "0",
    }
    if 主机 == "api-bc.wtzw.com":
        参数["refresh-type"] = "0"
    原始 = json.dumps(参数, ensure_ascii=False, separators=(",", ":"))
    编码 = base64.b64encode(原始.encode("utf-8")).decode("utf-8").replace("+", "-").replace("/", "_")
    return "".join(QM参数字符映射.get(字符, 字符) for 字符 in 编码)


def 解密正文(加密正文: str) -> str:
    原始内容 = base64.b64decode(加密正文)
    cipher = AES.new(解密密钥, AES.MODE_CBC, iv=原始内容[:16])
    解密内容 = unpad(cipher.decrypt(原始内容[16:]), AES.block_size)
    return 解密内容.decode("utf-8").strip()


def 提取直接七猫链接参数(命令文本: str) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None
    if 包含七猫链接(文本):
        return 文本
    return None


def 提取事件七猫链接(event: Any) -> str | None:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            链接 = 提取七猫链接(读取字段(对象, 字段名))
            if 链接:
                return 链接
    return None


def 提取七猫链接(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            链接 = 提取七猫链接(子值)
            if 链接:
                return 链接
        return ""
    if isinstance(值, dict):
        for 子值 in 值.values():
            链接 = 提取七猫链接(子值)
            if 链接:
                return 链接
        return ""
    文本 = str(值)
    for 模式 in (
        r"https?://(?:www\.)?qimao\.com/shuku/\d+/?",
        r"https?://app-share\.wtzw\.com/[^\s'\"<>，。]+(?:article-detail|short-story-detail)/\d+[^\s'\"<>，。]*",
    ):
        匹配 = re.search(模式, 文本)
        if 匹配:
            return 匹配.group(0)
    if 包含七猫链接(文本):
        return 文本
    return ""


def 包含七猫链接(文本: str) -> bool:
    return bool(
        re.search(r"qimao\.com/shuku/\d+", 文本)
        or re.search(r"app-share\.wtzw\.com/.+(?:article-detail|short-story-detail)/\d+", 文本)
    )


def 解析七猫链接类型(文本: str) -> str:
    return "short" if re.search(r"short-story-detail/\d+", str(文本 or "")) else "book"


def 提取书籍编号(文本: str) -> str:
    文本 = str(文本 or "").strip()
    if re.fullmatch(r"\d{4,20}", 文本):
        return 文本
    for 模式 in (
        r"qimao\.com/shuku/(\d+)",
        r"(?:article-detail|short-story-detail)/(\d+)",
        r"(?:book_id|bookid|id)=(\d+)",
    ):
        匹配 = re.search(模式, 文本)
        if 匹配:
            return 匹配.group(1)
    return ""


def 清理网页文本(文本: Any) -> str:
    文本 = re.sub(r"<[^>]+>", "", str(文本 or ""))
    return html.unescape(文本).strip()


def 清理文件名(文件名: str) -> str:
    文件名 = re.sub(r'[\\/:*?"<>|]', "_", 文件名).strip()
    return 文件名[:80] or "七猫小说"


def 读取字段路径(数据: Any, 路径: tuple[str, ...]) -> Any:
    当前 = 数据
    for 字段 in 路径:
        if not isinstance(当前, dict):
            return None
        当前 = 当前.get(字段)
    return 当前


def 读取首个字段(数据: dict[str, Any], 字段列表: tuple[str, ...]) -> Any:
    if not isinstance(数据, dict):
        return None
    for 字段 in 字段列表:
        值 = 数据.get(字段)
        if 值 not in (None, ""):
            return 值
    return None


def 安全整数(值: Any, 默认值: int = 0) -> int:
    try:
        return int(值)
    except Exception:
        return 默认值

def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
