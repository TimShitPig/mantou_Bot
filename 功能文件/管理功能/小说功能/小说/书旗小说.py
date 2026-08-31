from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import os
import re
import secrets
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

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

USER_ID = "6226157280"
IOS目录URL = "https://ocean.shuqireader.com/api/bcspub/iosapi/book/chapterlist"
IOS目录UID = "8000000"
IOS目录盐值 = "37e81a9d8f02596e1b895d07c171d5c9"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
SEARCH_URL = "https://ocean.shuqireader.com/sqan/render/render/search/native_v3"
SUGGEST_URL = "https://ocean.shuqireader.com/sqan/render/render/search/findSuggest"
SEARCH_USER_AGENT = "okhttp/3.12.13"
SEARCH_GATEWAY_KEY = "467694bd8912441cae8498b3c7e4282c"
SEARCH_VERSION_NAME = "12.6.4.262"
SEARCH_VERSION_CODE = "260609"
SEARCH_SUB_VERSION = "sqrelease"
SEARCH_NO_SIGN_KEYS = {
    "sign",
    "key",
    "_public",
    "_reqid",
    "_beta",
    "_",
    "X-NEBULAXMLHTTPREQUEST",
    "callbackUrl",
}
书旗正文最大动态并发数 = 400
书旗正文最大尝试次数 = 3
书旗解码最大动态并发数 = max(4, min(64, (os.cpu_count() or 4) * 2))
下载缓存目录 = 小说缓存工具.下载缓存目录
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


class ShuqiError(RuntimeError):
    pass


@dataclass
class Chapter:
    index: int
    chapter_id: str
    name: str
    content_url: str
    word_count: int = 0


@dataclass
class Book:
    book_id: str
    book_name: str
    author_name: str
    chapter_num: int
    word_count: int
    intro: str
    status_text: str
    chapters: list[Chapter]
    raw: dict[str, Any]
    is_short: bool = False


def 获取书旗小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[str] | None:
    链接 = 提取书旗链接(命令文本) or 提取事件书旗链接(event)
    if not 链接:
        return None
    return 生成下载回复流(event, 链接, 配置)


async def 生成下载回复流(event: Any, 链接: str, 配置: Any = None) -> AsyncIterator[str]:
    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=60)
        connector = aiohttp.TCPConnector(
            limit=书旗正文最大动态并发数,
            limit_per_host=书旗正文最大动态并发数,
            ttl_dns_cache=300,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )
        async with aiohttp.ClientSession(
            timeout=timeout, connector=connector
        ) as session:
            最终链接 = await 解析书旗短链(session, 链接)
            目标 = 解析书旗下载目标(最终链接)
            书籍 = await 获取书籍(session, 目标["book_id"], 目标["type"] == "short")
            if not 书籍.chapters:
                raise ShuqiError("没有获取到章节目录")
            if 书籍.chapter_num and len(书籍.chapters) != 书籍.chapter_num:
                raise ShuqiError(
                    f"目录不完整：catalog={len(书籍.chapters)}, total={书籍.chapter_num}"
                )

            logger.info(
                f"书旗小说开始下载：书籍编号={书籍.book_id}, "
                f"书名={书籍.book_name}, 作者={书籍.author_name}, "
                f"章节数={len(书籍.chapters)}, 模式=iOS目录+逐章正文, "
                f"会话复用=开启, 最大动态并发数={书旗正文最大动态并发数}, "
                f"解码方式=标准库, 解码并发数={书旗解码最大动态并发数}"
            )
            yield 格式化下载提示(书籍)

            章节内容 = await 下载全部章节(session, 书籍, 配置)
            成功数 = sum(1 for 项 in 章节内容 if 项.get("content"))
            if 成功数 != len(书籍.chapters):
                raise ShuqiError(
                    f"章节正文不完整：success={成功数}, total={len(书籍.chapters)}"
                )
            文件名, 文件内容 = 生成小说文件内容(书籍, 章节内容)
            logger.info(
                f"书旗小说章节下载完成：书籍编号={书籍.book_id}, "
                f"成功={成功数}, 总数={len(书籍.chapters)}, 文件大小={len(文件内容)}"
            )

        发送结果 = await 准备发送文本文件给当前会话(
            event,
            文件名,
            文件内容,
            配置,
            书名=书籍.book_name,
            作者=书籍.author_name,
        )
        if 发送结果.get("sent"):
            启动百度后台上传并清理源文件(
                配置, 发送结果.get("source_cache_path"), 文件名
            )
            return
        降级文本 = str(发送结果.get("fallback_text") or "")
        if 降级文本:
            try:
                yield 降级文本
            finally:
                启动百度后台上传并清理源文件(
                    配置, 发送结果.get("source_cache_path"), 文件名
                )
            return
        logger.warning(
            f"书旗小说完成消息发送失败：书籍编号={书籍.book_id}, "
            f"文件={文件名}, 错误={发送结果.get('error')}"
        )
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(f"书旗小说下载失败：错误={exc}")
        yield "下载失败 请重试"


def _搜索请求ID() -> str:
    return secrets.token_hex(5)


def _搜索编码值() -> str:
    时间值 = str(int(time.time() * 1000))[:13]
    选中值 = 时间值[1] + 时间值[3] + 时间值[5] + 时间值[8] + 时间值[6]
    乘积 = (int(选中值) if int(选中值) != 0 else 12347) * 24697
    return str(乘积)[-5:] + 时间值


def _构造搜索公共参数() -> str:
    参数 = {
        "soft_id": "1",
        "user_id": USER_ID,
        "userId": USER_ID,
        "ver": SEARCH_VERSION_CODE,
        "subVer": SEARCH_SUB_VERSION,
        "appVer": SEARCH_VERSION_NAME,
        "theme": "day",
        "platform": "an",
        "placeid": "",
        "sdk": "",
        "cpu": "",
        "pkg_cpu": "",
        "wh": "1440x2560",
        "msv": "3",
        "enc": _搜索编码值(),
        "vc": "",
        "mod": "SM-S9260",
        "manufacturer": "samsung",
        "brand": "Samsung",
        "net_type": "wifi",
        "net_type_str": "wifi",
        "first_placeid": "",
        "aak": "",
        "utype": "",
        "net": "4",
        "net_env": "4",
        "permissionType": "",
        "personalized": "1",
        "contentRecom": "1",
        "scene_code": "",
        "rom": "9",
    }
    return urllib.parse.urlencode(参数)


def _搜索签名参数(params: dict[str, Any]) -> dict[str, str]:
    结果 = {str(键): "" if 值 is None else str(值) for 键, 值 in params.items()}
    结果["sqSv"] = "1.0"
    结果["key"] = "sq_app_gateway"
    待签名 = {键: 值 for 键, 值 in 结果.items() if 键 not in SEARCH_NO_SIGN_KEYS}
    原文 = (
        "".join(
            f"{键}={urllib.parse.quote_plus(待签名[键], safe='*-._')}&"
            for 键 in sorted(待签名)
        )
        + f"skey={SEARCH_GATEWAY_KEY}"
    )
    结果["sign"] = hashlib.md5(原文.encode("utf-8")).hexdigest()
    return 结果


async def _请求搜索接口(
    session: aiohttp.ClientSession,
    url: str,
    参数: dict[str, Any],
) -> dict[str, Any]:
    headers = {
        "User-Agent": SEARCH_USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    请求地址 = f"{url}?_reqid={_搜索请求ID()}"
    async with session.post(
        请求地址, data=_搜索签名参数(参数), headers=headers
    ) as resp:
        文本 = await resp.text(errors="ignore")
        if resp.status >= 400:
            raise ShuqiError(f"搜索接口 HTTP {resp.status}")
    try:
        数据 = json.loads(文本) if 文本 else {}
    except Exception as exc:
        raise ShuqiError("搜索接口未返回 JSON") from exc
    if not isinstance(数据, dict):
        raise ShuqiError("搜索接口数据格式异常")
    return 数据


def _从搜索对象提取书籍(obj: dict[str, Any]) -> dict[str, Any] | None:
    书籍编号 = str(obj.get("bookId") or obj.get("bid") or obj.get("id") or "").strip()
    标题 = 清理网页文本(
        obj.get("bookName")
        or obj.get("displayBookName")
        or obj.get("title")
        or obj.get("name")
    )
    if not 书籍编号.isdigit() or not 标题:
        return None
    return {
        "book_id": 书籍编号,
        "title": 标题,
        "author": 清理网页文本(obj.get("authorName") or obj.get("author") or "未知")
        or "未知",
        "score": obj.get("novelScore") or obj.get("score") or 0,
        "word_count": obj.get("wordCount")
        or obj.get("words")
        or obj.get("word_count")
        or 0,
        "read_count": max(
            安全整数(obj.get("readCount"), 0),
            安全整数(obj.get("hotValue"), 0),
            安全整数(obj.get("hot"), 0),
            安全整数(obj.get("clickCount"), 0),
        ),
        "url": f"https://www.shuqi.com/book/{书籍编号}.html",
    }


def _遍历搜索结果(obj: Any, 结果: list[dict[str, Any]], 已记录: set[str]) -> None:
    if isinstance(obj, dict):
        书籍对象 = obj.get("book") if isinstance(obj.get("book"), dict) else obj
        书籍 = _从搜索对象提取书籍(书籍对象)
        if 书籍 and 书籍["book_id"] not in 已记录:
            if 书籍对象 is not obj or any(
                键 in obj
                for 键 in ("bookId", "bookName", "displayBookName", "authorName")
            ):
                已记录.add(书籍["book_id"])
                结果.append(书籍)
        for 值 in obj.values():
            _遍历搜索结果(值, 结果, 已记录)
    elif isinstance(obj, list):
        for 值 in obj:
            _遍历搜索结果(值, 结果, 已记录)


async def 搜索小说(
    session: aiohttp.ClientSession,
    关键词: str,
    *,
    需要数量: int = 30,
) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = []
    已记录: set[str] = set()
    页码 = 1
    while len(结果) < max(1, int(需要数量 or 1)) and 页码 <= 5:
        参数 = {
            "_public": _构造搜索公共参数(),
            "page": "searchResultV3",
            "query": str(关键词 or "").strip(),
            "fromSug": "0",
            "kind": "",
            "relatedBid": "",
            "showMore": "0",
            "showPost": "0",
            "showTypes": "",
            "pagination": json.dumps(
                {"page": 页码, "pageSize": 20}, ensure_ascii=False
            ),
            "isTeenMode": "0",
        }
        数据 = await _请求搜索接口(session, SEARCH_URL, 参数)
        if str(数据.get("status") or 数据.get("state") or "") not in {"200", "0"}:
            break
        原数量 = len(结果)
        _遍历搜索结果(数据.get("data", 数据), 结果, 已记录)
        if len(结果) == 原数量:
            break
        页码 += 1
    return 结果[: max(1, int(需要数量 or 1))]


async def 搜索联想(session: aiohttp.ClientSession, 关键词: str) -> list[str]:
    参数 = {
        "_public": _构造搜索公共参数(),
        "query": str(关键词 or "").strip(),
        "isTeenMode": "0",
    }
    数据 = await _请求搜索接口(session, SUGGEST_URL, 参数)
    建议: list[str] = []
    已记录: set[str] = set()

    def 遍历(obj: Any) -> None:
        if isinstance(obj, dict):
            for 键 in ("query", "word", "keyword", "title", "name", "sug", "suggest"):
                值 = 清理网页文本(obj.get(键))
                if 值 and 值 not in 已记录 and 值 != 关键词:
                    已记录.add(值)
                    建议.append(值)
            for 值 in obj.values():
                遍历(值)
        elif isinstance(obj, list):
            for 值 in obj:
                if isinstance(值, str):
                    文本 = 清理网页文本(值)
                    if 文本 and 文本 not in 已记录 and 文本 != 关键词:
                        已记录.add(文本)
                        建议.append(文本)
                else:
                    遍历(值)

    遍历(数据.get("data", 数据))
    return 建议[:8]


async def 获取书籍(
    session: aiohttp.ClientSession, 书籍编号: str, 是否短篇: bool = False
) -> Book:
    时间戳 = str(int(time.time()))
    目录参数 = {
        "reqEncryptType": "-1",
        "resEncryptType": "-1",
        "user_id": IOS目录UID,
        "bookId": str(书籍编号),
        "timestamp": 时间戳,
        "sign": hashlib.md5(
            f"{书籍编号}{时间戳}{IOS目录UID}{IOS目录盐值}".encode()
        ).hexdigest(),
    }
    响应 = await 请求JSON(session, IOS目录URL, params=目录参数)
    return 解析目录响应(书籍编号, 响应, 是否短篇)


def 解析目录响应(书籍编号: str, 响应: dict[str, Any], 是否短篇: bool = False) -> Book:
    状态 = str(响应.get("state") or 响应.get("status") or "")
    if 状态 and 状态 not in {"200", "0"}:
        raise ShuqiError(f"目录接口异常：state={状态}")
    数据 = 响应.get("data") if isinstance(响应.get("data"), dict) else {}
    if not 数据:
        raise ShuqiError("目录接口 data 为空")
    章节列表: list[Chapter] = []
    for 分卷 in 数据.get("chapterList") or []:
        if not isinstance(分卷, dict):
            continue
        for 项 in 分卷.get("volumeList") or []:
            if not isinstance(项, dict):
                continue
            章节编号 = str(项.get("chapterId") or "").strip()
            if not 章节编号:
                continue
            if 是否短篇:
                内容前缀 = str(数据.get("shortContUrlPrefix") or 数据.get("freeContUrlPrefix") or "")
                内容后缀 = str(
                    项.get("shortContUrlSuffix")
                    or 项.get("contUrlSuffix")
                    or 项.get("freeContUrlSuffix")
                    or ""
                )
            else:
                内容前缀 = str(数据.get("freeContUrlPrefix") or "")
                内容后缀 = str(
                    项.get("contUrlSuffix")
                    or 项.get("freeContUrlSuffix")
                    or 项.get("shortContUrlSuffix")
                    or ""
                )
            if 内容后缀.startswith("http://") or 内容后缀.startswith("https://"):
                正文地址 = 内容后缀
            elif 内容前缀 and 内容后缀:
                正文地址 = 内容前缀.rstrip("/") + (
                    内容后缀 if 内容后缀.startswith("?") else "/" + 内容后缀.lstrip("/")
                )
            else:
                正文地址 = ""
            章节列表.append(
                Chapter(
                    index=len(章节列表) + 1,
                    chapter_id=章节编号,
                    name=清理网页文本(
                        项.get("chapterName") or f"第{len(章节列表) + 1}章"
                    ),
                    content_url=正文地址,
                    word_count=安全整数(
                        项.get("wordCount") or 项.get("chapterWordCount"), 0
                    ),
                )
            )

    if not 章节列表:
        raise ShuqiError("目录章节为空")
    目录章节数 = 安全整数(数据.get("chapterNum"), len(章节列表)) or len(章节列表)
    return Book(
        book_id=str(书籍编号),
        book_name=清理网页文本(数据.get("bookName") or f"书旗小说{书籍编号}"),
        author_name=清理网页文本(数据.get("authorName") or "未知") or "未知",
        chapter_num=目录章节数,
        word_count=获取书旗原始字数(数据, 章节列表),
        intro=获取书旗简介(数据),
        status_text=解析书旗状态(数据),
        chapters=章节列表,
        raw=数据,
        is_short=是否短篇,
    )


def _生成书旗字符变换表() -> dict[int, int]:
    表: dict[int, int] = {}
    for 字符码 in range(ord("A"), ord("Z") + 1):
        偏移 = (字符码 + 32 - 83) % 26 or 26
        表[字符码] = 偏移 + 64
    for 字符码 in range(ord("a"), ord("z") + 1):
        偏移 = (字符码 - 83) % 26 or 26
        表[字符码] = 偏移 + 96
    return 表


书旗字符变换表 = str.maketrans(_生成书旗字符变换表())


def _书旗字符变换(密文: str) -> str:
    文本 = str(密文 or "")
    if 文本.isascii():
        return 文本.translate(书旗字符变换表)
    结果: list[str] = []
    for 字符 in 文本:
        if 字符.isalpha():
            大写 = 字符.isupper()
            偏移 = (ord(字符.lower()) - 83) % 26 or 26
            结果.append(chr(偏移 + (64 if 大写 else 96)))
        else:
            结果.append(字符)
    return "".join(结果)


def _解码书旗正文(密文: str) -> str:
    if not str(密文 or "").strip():
        raise ShuqiError("章节正文为空")
    try:
        编码文本 = _书旗字符变换(密文)
        原始正文 = base64.b64decode(编码文本, validate=True).decode("utf-8")
    except Exception as exc:
        raise ShuqiError("章节正文解密失败") from exc
    正文 = html.unescape(原始正文).replace("<br/>", "\n")
    正文 = 正文.replace("\r\n", "\n").replace("\r", "\n")
    正文 = "\n".join(行.lstrip(" \u3000") for 行 in 正文.split("\n")).strip()
    if not 正文:
        raise ShuqiError("章节正文为空")
    return 正文


async def _请求书旗章节正文(
    session: aiohttp.ClientSession,
    章节: Chapter,
    解密执行器: ThreadPoolExecutor,
    解密信号量: asyncio.Semaphore,
) -> str:
    if not 章节.content_url:
        raise ShuqiError("章节正文地址为空")
    headers = {
        "User-Agent": "ShuQiNovel/12.6.4 (iPhone; iOS 16.0)",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    async with session.get(
        章节.content_url, headers=headers, allow_redirects=True
    ) as resp:
        if resp.status >= 400:
            raise ShuqiError(f"章节正文 HTTP {resp.status}")
        文本 = await resp.text(errors="ignore")
    try:
        数据 = json.loads(文本) if 文本 else {}
    except Exception as exc:
        raise ShuqiError("章节正文响应格式异常") from exc
    状态 = str(数据.get("state") or 数据.get("status") or "")
    if 状态 and 状态 not in {"200", "0"}:
        raise ShuqiError(f"章节正文接口异常：state={状态}")
    加密正文 = str(数据.get("ChapterContent") or "")
    if not 加密正文.strip():
        raise ShuqiError("章节正文为空")
    async with 解密信号量:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            解密执行器, _解码书旗正文, 加密正文
        )


def 计算书旗正文并发数(章节数: int, 上限: int = 书旗正文最大动态并发数) -> int:
    数量 = max(0, int(章节数 or 0))
    if not 数量:
        return 0
    return min(max(1, int(上限 or 1)), 数量)


async def 下载全部章节(
    session: aiohttp.ClientSession, 书籍: Book, 配置: Any = None
) -> list[dict[str, str]]:
    """使用 iOS 目录和正文接口按目录顺序下载，缺章时不生成 TXT。"""
    总数 = len(书籍.chapters)
    if not 总数:
        return []
    结果: list[dict[str, str]] = [
        {"id": 章节.chapter_id, "title": 章节.name, "content": ""}
        for 章节 in 书籍.chapters
    ]
    待处理 = list(range(总数))
    进度锁 = asyncio.Lock()
    已完成 = 0
    成功数 = 0
    下次进度 = 10
    解密并发数 = min(书旗解码最大动态并发数, 总数)
    解密执行器 = ThreadPoolExecutor(
        max_workers=max(1, 解密并发数), thread_name_prefix="shuqi-decode"
    )

    logger.info(
        f"书旗小说章节进度：书籍编号={书籍.book_id}, 进度=0/{总数}, "
        f"百分比=0%, 模式=iOS逐章正文, 会话复用=开启, "
        f"动态并发上限={计算书旗正文并发数(总数)}, "
        f"解码方式=标准库, 解码并发数={解密并发数}"
    )

    async def 记录首轮进度(成功: bool) -> None:
        nonlocal 已完成, 成功数, 下次进度
        async with 进度锁:
            已完成 += 1
            if 成功:
                成功数 += 1
            百分比 = 已完成 * 100 // 总数
            if 百分比 < 下次进度 and 已完成 != 总数:
                return
            logger.info(
                f"书旗小说章节进度：书籍编号={书籍.book_id}, "
                f"进度={已完成}/{总数}, 百分比={百分比}%, "
                f"成功={成功数}, 失败={已完成 - 成功数}, "
                "模式=iOS逐章正文, 会话复用=开启"
            )
            while 下次进度 <= 百分比:
                下次进度 += 10

    try:
        for 尝试次数 in range(1, 书旗正文最大尝试次数 + 1):
            if not 待处理:
                break
            本轮上限 = max(
                1, 书旗正文最大动态并发数 // (2 ** (尝试次数 - 1))
            )
            本轮并发 = min(
                计算书旗正文并发数(len(待处理)), 本轮上限
            )
            本轮结果 = await _下载章节一轮(
                session,
                书籍,
                待处理,
                本轮并发,
                解密执行器,
                解密并发数,
                记录首轮进度 if 尝试次数 == 1 else None,
            )
            下轮待处理: list[int] = []
            for 索引, 正文, 错误类型 in 本轮结果:
                if 正文:
                    结果[索引]["content"] = 正文
                else:
                    下轮待处理.append(索引)
                    logger.debug(
                        f"书旗章节下载失败，准备重试：书籍编号={书籍.book_id}, "
                        f"章节编号={书籍.chapters[索引].chapter_id}, "
                        f"轮次={尝试次数}/{书旗正文最大尝试次数}, 错误类型={错误类型}"
                    )
            待处理 = 下轮待处理
            if 待处理 and 尝试次数 < 书旗正文最大尝试次数:
                await asyncio.sleep(min(1.0, 0.25 * 尝试次数))
    finally:
        解密执行器.shutdown(wait=False, cancel_futures=True)

    成功总数 = sum(bool(项.get("content")) for 项 in 结果)
    logger.info(
        f"书旗小说章节下载汇总：书籍编号={书籍.book_id}, "
        f"成功={成功总数}, 失败={总数 - 成功总数}, 总数={总数}, "
        f"动态并发上限={计算书旗正文并发数(总数)}, 解码方式=标准库"
    )
    if 待处理:
        raise ShuqiError(f"章节正文不完整：missing={len(待处理)}")
    return 结果


async def _下载章节一轮(
    session: aiohttp.ClientSession,
    书籍: Book,
    索引列表: list[int],
    并发数: int,
    解密执行器: ThreadPoolExecutor,
    解密并发数: int,
    进度回调: Any = None,
) -> list[tuple[int, str, str]]:
    请求信号量 = asyncio.Semaphore(max(1, 并发数))
    解密信号量 = asyncio.Semaphore(max(1, 解密并发数))

    async def 下载单章(索引: int) -> tuple[int, str, str]:
        try:
            async with 请求信号量:
                正文 = await _请求书旗章节正文(
                    session,
                    书籍.chapters[索引],
                    解密执行器,
                    解密信号量,
                )
            if 进度回调 is not None:
                await 进度回调(True)
            return 索引, 正文, ""
        except Exception as exc:
            if 进度回调 is not None:
                await 进度回调(False)
            return 索引, "", type(exc).__name__

    结果: list[tuple[int, str, str]] = []
    待调度 = iter(索引列表)
    活跃任务: set[asyncio.Task[tuple[int, str, str]]] = set()
    for _ in range(min(max(1, 并发数), len(索引列表))):
        try:
            活跃任务.add(asyncio.create_task(下载单章(next(待调度))))
        except StopIteration:
            break
    while 活跃任务:
        完成任务, 活跃任务 = await asyncio.wait(
            活跃任务, return_when=asyncio.FIRST_COMPLETED
        )
        for 任务 in 完成任务:
            结果.append(任务.result())
            try:
                活跃任务.add(asyncio.create_task(下载单章(next(待调度))))
            except StopIteration:
                pass
    return 结果


async def 请求JSON(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "identity",
    }
    async with session.get(url, params=params, headers=headers) as resp:
        文本 = await resp.text(errors="ignore")
        if resp.status >= 400:
            raise ShuqiError(f"HTTP {resp.status}")
    try:
        数据 = json.loads(文本) if 文本 else {}
    except Exception as exc:
        raise ShuqiError("接口未返回 JSON") from exc
    return 数据 if isinstance(数据, dict) else {}


def 生成小说文件内容(书籍: Book, 章节内容: list[dict[str, str]]) -> tuple[str, bytes]:
    文件名 = 生成小说文件名(书籍)
    内容列表 = [
        文件声明,
        "",
        f"名称：{书籍.book_name}",
        f"作者：{书籍.author_name or '未知'}",
        f"状态：{获取状态文本(书籍)}",
        f"字数：{格式化字数(书籍.word_count)}",
        f"书籍ID：{书籍.book_id}",
        f"章节数：{len(书籍.chapters)}",
        "",
    ]
    if 书籍.intro:
        内容列表.extend(["简介：", 书籍.intro, ""])
    for 章节 in 章节内容:
        标题 = str(章节.get("title") or "")
        正文 = 去除章节正文重复标题(标题, 章节.get("content"))
        内容列表.extend(
            [
                标题,
                "",
                正文,
                "",
            ]
        )
    return 文件名, "\r\n".join(内容列表).encode("utf-8")


def 生成小说文件名(书籍: Book) -> str:
    标题 = 清理文件名(书籍.book_name or f"书旗小说{书籍.book_id}")
    作者 = 清理文件名(书籍.author_name or "未知")
    return f"[{获取状态文本(书籍)}]书名：{标题} 作者：{作者}.txt"


def 格式化下载提示(书籍: Book) -> str:
    return "\n".join(
        [
            f"书名：{书籍.book_name or '未知'}",
            f"作者：{书籍.author_name or '未知'}",
            f"状态：{获取状态文本(书籍)}",
            f"章节：{len(书籍.chapters)} 章",
            f"字数：{格式化字数(书籍.word_count)}",
            "",
            "正在下载中请稍等.....",
        ]
    )


def 获取状态文本(书籍: Book) -> str:
    return 书籍.status_text or "连载"


def 获取书旗原始字数(数据: dict[str, Any], 章节列表: list[Chapter]) -> int:
    for 字段名 in ("realTimeWordCount", "wordCount", "words", "totalWordCount"):
        字数 = 安全整数(数据.get(字段名), 0)
        if 字数 > 0:
            return 字数
    return sum(章节.word_count for 章节 in 章节列表)


def 获取书旗简介(数据: dict[str, Any]) -> str:
    for 字段名 in ("intro", "desc", "description", "bookDesc", "summary"):
        简介 = 清理网页文本(数据.get(字段名))
        if 简介:
            return 简介
    return ""


def 解析书旗状态(数据: dict[str, Any]) -> str:
    for 字段名 in ("statusText", "statusName", "bookStatus", "updateStatus"):
        文本 = 清理网页文本(数据.get(字段名))
        if "完结" in 文本 or "已完" in 文本:
            return "完结"
        if "连载" in 文本 or "更新" in 文本:
            return "连载"
    状态值 = str(数据.get("state") or 数据.get("updateType") or "").strip()
    return "完结" if 状态值 == "2" else "连载"


def 格式化字数(字数: int) -> str:
    if not 字数:
        return "未知"
    if 字数 >= 10000:
        return f"{round(字数 / 10000, 1)}万字"
    return f"{字数}字"


async def 准备发送文本文件给当前会话(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    logger.info(f"书旗小说准备上传：文件={文件名}, 大小={len(文件内容)}")
    缓存路径 = 写入下载缓存文件(文件名, 文件内容)
    if 小说网盘 is None:
        删除下载缓存文件(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "小说网盘模块未加载",
        }
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        网盘名称 = str(网盘结果.get("provider") or "小说网盘")
        if not 网盘结果.get("success"):
            logger.warning(
                f"书旗小说主网盘上传失败：网盘={网盘名称}, "
                f"文件={文件名}, 错误={网盘结果.get('error')}"
            )
            删除下载缓存文件(缓存路径)
            return {
                "sent": False,
                "fallback_text": "",
                "source_cache_path": None,
                "error": str(网盘结果.get("error") or "小说网盘未启用"),
            }
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event,
            书名,
            作者,
            str(网盘结果.get("share_url") or ""),
        )
        if 完成结果.get("sent"):
            logger.info(
                f"书旗小说主网盘上传并发送完成按钮成功：网盘={网盘名称}, 文件={文件名}"
            )
            return {
                "sent": True,
                "fallback_text": "",
                "source_cache_path": 缓存路径,
                "error": "",
            }
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {
                "sent": False,
                "fallback_text": 降级文本,
                "source_cache_path": 缓存路径,
                "error": str(完成结果.get("error") or ""),
            }
        删除下载缓存文件(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(完成结果.get("error") or "完成按钮发送失败"),
        }
    except Exception as exc:
        logger.warning(
            f"书旗小说主网盘上传或完成消息发送失败：文件={文件名}, 错误={exc}"
        )
        删除下载缓存文件(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(exc),
        }


def 启动百度后台上传并清理源文件(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    if not 源缓存路径:
        return

    async def 执行上传并清理() -> None:
        try:
            if 百度网盘 is not None:
                百度结果 = await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
                if 百度结果.get("success"):
                    logger.info(f"书旗小说百度网盘后台上传成功：文件={文件名}")
                elif 百度结果.get("skipped"):
                    logger.info(
                        f"书旗小说百度网盘后台上传按状态规则跳过：文件={文件名}"
                    )
                elif 百度结果.get("enabled"):
                    logger.warning(
                        f"书旗小说百度网盘后台上传失败，不影响主分享：文件={文件名}, 错误={百度结果.get('error')}"
                    )
        except Exception as exc:
            logger.warning(
                f"书旗小说百度网盘后台上传异常，不影响主分享：文件={文件名}, 错误={exc}"
            )
        finally:
            删除下载缓存文件(源缓存路径)

    try:
        asyncio.create_task(执行上传并清理())
    except RuntimeError:
        删除下载缓存文件(源缓存路径)


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(缓存路径)
    return 缓存路径


def 删除下载缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    if not 小说缓存工具.删除下载缓存文件(缓存路径):
        logger.debug(f"书旗小说下载缓存仍在等待续传：文件={缓存路径}")
        return
    try:
        logger.info(f"书旗小说下载缓存文件已删除：文件={缓存路径}")
    except Exception as exc:
        logger.warning(f"书旗小说下载缓存文件删除失败：文件={缓存路径}, 错误={exc}")


def 生成不冲突缓存路径(文件名: str) -> Path:
    安全文件名 = Path(清理文件名(文件名)).name or "书旗小说.txt"
    if not 安全文件名.lower().endswith(".txt"):
        安全文件名 += ".txt"
    缓存路径 = 下载缓存目录 / 安全文件名
    if not 缓存路径.exists():
        return 缓存路径
    for 序号 in range(1, 1000):
        候选路径 = 下载缓存目录 / f"{缓存路径.stem}_{序号}{缓存路径.suffix}"
        if not 候选路径.exists():
            return 候选路径
    raise RuntimeError("下载缓存目录中同名文件过多")


def 解析书旗下载目标(链接: str) -> dict[str, str]:
    文本 = str(链接 or "").strip()
    书籍编号 = 提取书籍编号(文本)
    if not 书籍编号:
        raise ShuqiError("没有识别到书旗 bookId")
    类型 = "short" if re.search(r"/shortNovel/reader/\d+", 文本, re.I) else "book"
    return {"book_id": 书籍编号, "type": 类型}


async def 解析书旗短链(session: aiohttp.ClientSession, 链接: str) -> str:
    文本 = str(链接 or "").strip()
    if not re.search(r"https?://d\.shuqi\.com/[^\s'\"<>，。]+", 文本, re.I):
        return 文本
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*",
    }
    for 方法 in ("HEAD", "GET"):
        try:
            async with session.request(
                方法, 文本, headers=headers, allow_redirects=True
            ) as resp:
                最终链接 = str(resp.url)
                if 提取书籍编号(最终链接):
                    return 最终链接
                if 方法 == "GET":
                    页面链接 = 提取书旗链接(await resp.text(errors="ignore"))
                    if 提取书籍编号(页面链接):
                        return 页面链接
        except Exception as exc:
            logger.debug(f"书旗短链解析重试：方法={方法}, 错误={exc}")
    raise ShuqiError("书旗短链解析失败")


def 提取事件书旗链接(event: Any) -> str:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            链接 = 提取书旗链接(读取字段(对象, 字段名))
            if 链接:
                return 链接
    return ""


def 提取书旗链接(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            链接 = 提取书旗链接(子值)
            if 链接:
                return 链接
        return ""
    if isinstance(值, dict):
        for 子值 in 值.values():
            链接 = 提取书旗链接(子值)
            if 链接:
                return 链接
        return ""
    文本 = str(值)
    模式列表 = (
        r"https?://d\.shuqi\.com/[^\s'\"<>，。]*",
        r"https?://(?:www\.)?shuqi\.com/book/\d+\.html[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/book/\d+/?[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/(?:catalog|cover)/\d+/?[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/shortNovel/reader/\d+/?[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/v2/query/\d+(?:/\d+)?/?[^\s'\"<>，。]*",
    )
    for 模式 in 模式列表:
        匹配 = re.search(模式, 文本, flags=re.I)
        if 匹配:
            return 匹配.group(0)
    return ""


def 提取书籍编号(文本: str) -> str:
    文本 = str(文本 or "").strip()
    for 模式 in (
        r"/catalog/(\d+)/?",
        r"/cover/(\d+)/?",
        r"/shortNovel/reader/(\d+)/?",
        r"/v2/query/(\d+)",
        r"/book/(\d+)",
        r"[?&](?:bid|bookId)=(\d+)",
    ):
        匹配 = re.search(模式, 文本, flags=re.I)
        if 匹配:
            return 匹配.group(1)
    return 文本 if re.fullmatch(r"\d{4,20}", 文本) else ""


def 清理网页文本(文本: Any) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(文本 or ""))).strip()


def 清理文件名(文件名: Any) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", str(文件名 or "")).strip()[:80] or "书旗小说"


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
