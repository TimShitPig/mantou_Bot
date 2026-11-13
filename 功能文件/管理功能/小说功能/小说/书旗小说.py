from __future__ import annotations

import asyncio
import base64
import codecs
import hashlib
import html
import json
import re
import secrets
import time
import urllib.parse
import xml.etree.ElementTree as ET
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

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

USER_ID = "8000000"
XML_CHAPTERLIST_URL = "http://api.shuqireader.com/reader/bc_chapter.php"
BOOK_METADATA_URL = "https://ocean.shuqireader.com/api/bcspub/andapi/book/chapterlist/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
XML_USER_AGENT = "Mozilla/5.0"
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
下载并发数 = 16
单章重试次数 = 3
目录重试次数 = 3
进度日志分段数 = 4
小说缓存目录 = 文件缓存工具.小说缓存目录
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


class ShuqiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        reason: str = "request_failed",
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.http_status = http_status


@dataclass
class Chapter:
    chapter_id: str
    name: str
    content_url: str


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


def 获取书旗小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[str] | None:
    链接 = 提取书旗链接(命令文本) or 提取事件书旗链接(event)
    if not 链接:
        return None
    return 生成下载回复流(event, 链接, 配置)


async def 生成下载回复流(event: Any, 链接: str, 配置: Any = None) -> AsyncIterator[str]:
    阶段 = "share_link"
    书籍编号 = ""
    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=60)
        connector = aiohttp.TCPConnector(
            limit=下载并发数,
            limit_per_host=下载并发数,
            ttl_dns_cache=300,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )
        async with aiohttp.ClientSession(
            timeout=timeout, connector=connector
        ) as session:
            最终链接 = await 解析书旗短链(session, 链接)
            目标 = 解析书旗下载目标(最终链接)
            书籍编号 = 目标["book_id"]
            阶段 = "catalog"
            书籍 = await 获取书籍(session, 书籍编号)
            if not 书籍.chapters:
                raise ShuqiError("没有获取到章节目录", reason="empty_catalog")
            logger.info(
                f"书旗小说开始下载：书籍编号={书籍.book_id}, "
                f"书名={书籍.book_name}, 作者={书籍.author_name}, "
                f"章节数={len(书籍.chapters)}, 模式=XML目录+XML单章正文, "
                f"会话复用=开启, 最大并发数={下载并发数}"
            )
            yield 格式化下载提示(书籍)

            阶段 = "content"
            所有章节内容 = await 下载全部章节(session, 书籍)
            章节内容 = [
                项 for 项 in 所有章节内容 if str(项.get("content") or "").strip()
            ]
            成功数 = len(章节内容)
            if not 成功数:
                raise ShuqiError("没有获取到可用章节正文", reason="all_chapters_failed")
            if 成功数 != len(书籍.chapters):
                logger.warning(
                    "书旗小说正文部分获取：book_id=%s, success=%s, catalog=%s, declared=%s",
                    书籍.book_id,
                    成功数,
                    len(书籍.chapters),
                    书籍.chapter_num,
                )
            阶段 = "file"
            文件名, 文件内容 = 生成小说文件内容(书籍, 章节内容)
            logger.info(
                f"书旗小说章节下载完成：书籍编号={书籍.book_id}, "
                f"成功={成功数}, 目录={len(书籍.chapters)}, 声明={书籍.chapter_num}, "
                f"文件大小={len(文件内容)}"
            )

        阶段 = "upload_send"
        发送结果 = await 准备发送文本文件给当前会话(
            event,
            文件名,
            文件内容,
            配置,
            书名=书籍.book_name,
            作者=书籍.author_name,
        )
        try:
            if 发送结果.get("sent"):
                return
            降级文本 = str(发送结果.get("fallback_text") or "")
            if 降级文本:
                yield 降级文本
                return
            logger.warning(
                "书旗小说完成消息发送失败：stage=upload_send, book_id=%s, reason=%s",
                书籍.book_id, 发送结果.get("reason") or "upload_or_delivery_failed",
            )
            yield "文件发送失败，请稍后再试"
        finally:
            删除小说缓存文件(发送结果.get("source_cache_path"))
    except Exception as exc:
        logger.warning(
            "书旗小说下载失败：stage=%s, book_id=%s, error_type=%s, reason=%s, http_status=%s",
            阶段, 书籍编号, type(exc).__name__, 书旗失败原因(exc),
            getattr(exc, "http_status", None) or "none",
        )
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
        "_search_status": {key: obj[key] for key in ("status", "statusText", "state", "stateText", "bookStatus", "bookStatusText",) if key in obj},
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


async def 获取书旗详情(
    session: aiohttp.ClientSession, 书籍编号: str
) -> dict[str, Any]:
    """恢复旧接口的书籍资料，忽略其中的目录与正文地址。"""
    请求参数 = _搜索签名参数({
        "bookId": str(书籍编号),
        "user_id": USER_ID,
        "timestamp": str(int(time.time() * 1000)),
        "resEncryptType": "-1",
    })
    headers = {
        "User-Agent": SEARCH_USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json,*/*",
        "Accept-Encoding": "identity",
    }
    try:
        async with asyncio.timeout(10):
            async with session.post(
                BOOK_METADATA_URL, data=请求参数, headers=headers, allow_redirects=False
            ) as resp:
                if not 200 <= resp.status < 300:
                    raise ShuqiError(
                        "书籍资料 HTTP 状态异常", reason="metadata_http_status",
                        http_status=int(resp.status),
                    )
                响应 = await resp.json(content_type=None)
        if not isinstance(响应, dict) or str(响应.get("state")) != "200":
            raise ShuqiError("书籍资料状态异常", reason="metadata_status")
        资料 = 响应.get("data")
        if not isinstance(资料, dict) or str(资料.get("bookId") or "") != str(书籍编号):
            raise ShuqiError("书籍资料编号不匹配", reason="metadata_book_id")
        return {
            字段: 资料[字段]
            for 字段 in (
                "bookId", "bookName", "authorName", "state",
                "realTimeWordCount", "wordCount", "words", "totalWordCount",
                "intro", "desc", "description", "bookDesc", "summary",
            )
            if 字段 in 资料
        }
    except Exception as exc:
        logger.debug(
            "书旗详情补充失败：book_id=%s, reason=%s, error_type=%s",
            书籍编号, 书旗失败原因(exc), type(exc).__name__,
        )
        return {}


async def 获取书籍(
    session: aiohttp.ClientSession,
    书籍编号: str,
) -> Book:
    if not re.fullmatch(r"\d+", str(书籍编号)):
        raise ShuqiError("书籍编号无效", reason="invalid_book_id")
    详情任务 = asyncio.create_task(获取书旗详情(session, 书籍编号))
    try:
        XML资料, XML章节 = await 获取书旗XML目录(session, 书籍编号)
        详情 = await 详情任务
    finally:
        if not 详情任务.done():
            详情任务.cancel()
        await asyncio.gather(详情任务, return_exceptions=True)
    chapters = [
        Chapter(
            chapter_id=item["ChapterId"],
            name=清理网页文本(item.get("BookChapter")) or f"第{index}章",
            content_url=item["ContentURL"],
        )
        for index, item in enumerate(XML章节, 1)
    ]
    return Book(
        book_id=书籍编号,
        book_name=(
            清理网页文本(XML资料.get("BookName"))
            or 清理网页文本(详情.get("bookName")) or f"书旗小说{书籍编号}"
        ),
        author_name=(
            清理网页文本(XML资料.get("Author"))
            or 清理网页文本(详情.get("authorName")) or "未知"
        ),
        chapter_num=(
            安全整数(XML资料.get("NumChapter"), 0)
            or len(chapters)
        ),
        word_count=next((
            字数 for 字段 in ("realTimeWordCount", "wordCount", "words", "totalWordCount")
            if (字数 := 安全整数(详情.get(字段), 0)) > 0
        ), 0),
        intro=next((
            简介 for 字段 in ("intro", "desc", "description", "bookDesc", "summary")
            if (简介 := 清理网页文本(详情.get(字段)))
        ), ""),
        status_text={"1": "连载", "2": "完结"}.get(str(详情.get("state", "")).strip(), "未知"),
        chapters=chapters,
    )


async def 下载全部章节(
    session: aiohttp.ClientSession,
    书籍: Book,
) -> list[dict[str, str]]:
    总数 = len(书籍.chapters)
    if not 总数:
        return []
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上次日志进度 = 0
    进度锁 = asyncio.Lock()
    logger.info(
        f"书旗小说章节进度：book_id={书籍.book_id}, progress=0/{总数}, "
        f"percent=0%, concurrency={下载并发数}"
    )

    失败分类: dict[str, int] = {}
    首个失败: dict[str, str | int | None] | None = None
    当前请求并发上限 = max(1, 下载并发数)
    活动请求数 = 0
    并发条件 = asyncio.Condition()

    async def 获取章节正文受控(章节: Chapter) -> tuple[str, str]:
        nonlocal 当前请求并发上限, 活动请求数
        async with 并发条件:
            await 并发条件.wait_for(lambda: 活动请求数 < 当前请求并发上限)
            活动请求数 += 1
        try:
            return await 获取章节正文(session, 书籍, 章节)
        except Exception as exc:
            if getattr(exc, "http_status", None) in {403, 429}:
                async with 并发条件:
                    新并发上限 = max(1, 当前请求并发上限 // 2)
                    if 新并发上限 < 当前请求并发上限:
                        当前请求并发上限 = 新并发上限
                        logger.debug(
                            "书旗正文遇到访问限制，降低后续并发：book_id=%s, concurrency=%s",
                            书籍.book_id,
                            当前请求并发上限,
                        )
                        并发条件.notify_all()
            raise
        finally:
            async with 并发条件:
                活动请求数 -= 1
                并发条件.notify_all()

    async def 记录进度(
        成功: bool,
        失败原因: str | None = None,
        HTTP状态: int | None = None,
        失败章节: str = "",
    ) -> None:
        nonlocal 已完成, 成功数, 失败数, 上次日志进度
        nonlocal 首个失败
        async with 进度锁:
            已完成 += 1
            if 成功:
                成功数 += 1
            else:
                失败数 += 1
                分类 = 失败原因 or "unknown_error"
                失败分类[分类] = 失败分类.get(分类, 0) + 1
                if 首个失败 is None:
                    首个失败 = {
                        "chapter_id": 失败章节,
                        "reason": 分类,
                        "http_status": HTTP状态,
                    }
            当前进度 = 进度日志分段数 if 已完成 >= 总数 else int(已完成 * 进度日志分段数 / 总数)
            if 当前进度 <= 上次日志进度 and 已完成 < 总数:
                return
            上次日志进度 = 当前进度
            百分比 = int(已完成 * 100 / 总数) if 总数 else 100
            logger.info(f"书旗小说章节进度：book_id={书籍.book_id}, progress={已完成}/{总数}, percent={百分比}%, success={成功数}, failed={失败数}")

    async def 下载单章(章节: Chapter) -> dict[str, str]:
        最后异常: Exception | None = None
        for 尝试次数 in range(1, 单章重试次数 + 1):
            try:
                _, 正文 = await 获取章节正文受控(章节)
                if not str(正文 or "").strip():
                    raise ShuqiError("章节正文为空", reason="empty_decoded_content")
                await 记录进度(True)
                return {"id": 章节.chapter_id, "title": 章节.name, "content": 正文}
            except Exception as exc:
                最后异常 = exc
                logger.debug(
                    "书旗章节下载失败，准备重试：book_id=%s, chapter_id=%s, "
                    "try=%s/%s, reason=%s, http_status=%s",
                    书籍.book_id, 章节.chapter_id, 尝试次数, 单章重试次数,
                    书旗失败原因(exc), getattr(exc, "http_status", None) or "none",
                )
                if 尝试次数 < 单章重试次数:
                    if getattr(exc, "http_status", None) in {403, 429}:
                        await asyncio.sleep(min(15.0, 3.0 * (2 ** (尝试次数 - 1))))
                    else:
                        await asyncio.sleep(min(1.5, 0.3 * 尝试次数))
        await 记录进度(
            False,
            失败原因=书旗失败原因(最后异常),
            HTTP状态=getattr(最后异常, "http_status", None),
            失败章节=章节.chapter_id,
        )
        return {"id": 章节.chapter_id, "title": 章节.name, "content": ""}

    结果: list[dict[str, str]] = [{} for _ in 书籍.chapters]
    待下载 = iter(enumerate(书籍.chapters))

    async def 下载工作任务() -> None:
        for 索引, 章节 in 待下载:
            结果[索引] = await 下载单章(章节)

    任务列表 = [
        asyncio.create_task(下载工作任务())
        for _ in range(min(下载并发数, 总数))
    ]
    try:
        await asyncio.gather(*任务列表)
        if 失败数:
            原因摘要 = ",".join(
                f"{原因}:{数量}" for 原因, 数量 in sorted(失败分类.items())
            )
            logger.warning(
                "书旗章节下载汇总：book_id=%s, success=%s, failed=%s, "
                "failure_reasons=%s, first_failed_chapter=%s, "
                "first_failure_reason=%s, first_failure_http_status=%s",
                书籍.book_id,
                成功数,
                失败数,
                原因摘要,
                (首个失败 or {}).get("chapter_id", ""),
                (首个失败 or {}).get("reason", "unknown_error"),
                (首个失败 or {}).get("http_status") or "none",
            )
        return 结果
    finally:
        for 任务 in 任务列表:
            if not 任务.done():
                任务.cancel()
        await asyncio.gather(*任务列表, return_exceptions=True)


async def 获取章节正文(session: aiohttp.ClientSession, 书籍: Book, 章节: Chapter) -> tuple[str, str]:
    if not 校验书旗XML正文URL(章节.content_url, 书籍.book_id, 章节.chapter_id):
        raise ShuqiError("XML章节正文地址无效", reason="invalid_content_url")
    编码正文 = await 请求GETXML章节正文(session, 章节.content_url)
    if not 编码正文:
        raise ShuqiError("XML章节正文为空", reason="empty_payload")
    正文 = 清理正文(解码章节正文(编码正文))
    if not 正文:
        raise ShuqiError("XML章节正文解码后为空", reason="empty_decoded_content")
    return "full", 正文


def 书旗失败原因(exc: BaseException | None) -> str:
    if isinstance(exc, ShuqiError):
        return exc.reason
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, aiohttp.ClientError):
        return "network_error"
    return type(exc).__name__ if exc is not None else "unknown_error"


async def 请求书旗XML目录(
    session: aiohttp.ClientSession, 书籍编号: str, 分卷编号: str = ""
) -> ET.Element:
    if not re.fullmatch(r"\d+", str(书籍编号)):
        raise ShuqiError("书籍编号无效", reason="invalid_book_id")
    参数 = {
        "pagesize": "99999999",
        "bookId": str(书籍编号),
        "isShowChapterInfo": "true",
    }
    if 分卷编号:
        if not re.fullmatch(r"\d+", 分卷编号):
            raise ShuqiError("分卷编号无效", reason="invalid_volume_id")
        参数["vid"] = 分卷编号
    headers = {
        "User-Agent": XML_USER_AGENT,
        "Accept": "application/xml,text/xml,*/*",
        "Accept-Encoding": "identity",
    }
    # 根目录和分卷共用恢复逻辑；只有瞬时请求错误重试，不因声明章数差异反复请求。
    for 尝试次数 in range(1, 目录重试次数 + 1):
        try:
            async with session.get(
                f"{XML_CHAPTERLIST_URL}?{urllib.parse.urlencode(参数)}", headers=headers,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=20, sock_connect=10, sock_read=15),
            ) as resp:
                if not 200 <= resp.status < 300:
                    raise ShuqiError(
                        "目录接口 HTTP 状态异常", reason="catalog_http_status",
                        http_status=int(resp.status),
                    )
                内容 = await resp.read()
            if not 内容.strip():
                raise ShuqiError("XML目录响应为空", reason="catalog_empty_body")
            try:
                root = ET.fromstring(内容)
            except ET.ParseError as exc:
                raise ShuqiError("XML目录格式异常", reason="catalog_xml_parse") from exc
            break
        except (ShuqiError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            状态 = getattr(exc, "http_status", None)
            可重试 = isinstance(exc, (aiohttp.ClientError, asyncio.TimeoutError)) or (
                isinstance(exc, ShuqiError) and (
                    exc.reason in {"catalog_empty_body", "catalog_xml_parse"}
                    or (exc.reason == "catalog_http_status" and (
                        状态 in {408, 429} or (状态 is not None and 500 <= 状态 < 600)
                    ))
                )
            )
            if not 可重试 or 尝试次数 >= 目录重试次数:
                raise
            logger.debug(
                "书旗XML目录请求重试：book_id=%s, vid=%s, try=%s/%s, reason=%s, http_status=%s",
                书籍编号, 分卷编号 or "0", 尝试次数, 目录重试次数,
                书旗失败原因(exc), 状态 or "none",
            )
            await asyncio.sleep((3.0 if 状态 == 429 else 0.5) * 尝试次数)
    if root.tag.rsplit("}", 1)[-1] != "BookInfos":
        raise ShuqiError("XML目录根节点异常", reason="catalog_xml_root")
    返回书籍编号 = str(root.attrib.get("BookId") or "").strip()
    if 返回书籍编号 != str(书籍编号):
        raise ShuqiError("XML目录书籍编号不匹配", reason="catalog_book_id_mismatch")
    if 分卷编号 and str(root.attrib.get("Vid") or "") != 分卷编号:
        raise ShuqiError("XML目录分卷编号不匹配", reason="catalog_volume_id_mismatch")
    return root


def 提取XML目录节点(root: ET.Element) -> list[dict[str, str]]:
    节点 = [
        dict(item.attrib) for item in root.iter()
        if item is not root and item.tag.rsplit("}", 1)[-1] == "Book"
    ]
    声明数量 = 安全整数(root.attrib.get("TotalCount"), -1)
    if 声明数量 != len(节点):
        logger.warning(
            "书旗XML目录返回条目数量不一致：reason=entry_count_mismatch, book_id=%s, vid=%s, expected=%s, actual=%s",
            root.attrib.get("BookId", ""),
            root.attrib.get("Vid", ""),
            声明数量,
            len(节点),
        )
    return 节点


async def 获取书旗XML目录(
    session: aiohttp.ClientSession, 书籍编号: str
) -> tuple[dict[str, str], list[dict[str, str]]]:
    root = await 请求书旗XML目录(session, 书籍编号)
    节点列表 = 提取XML目录节点(root)
    总章数 = 安全整数(root.attrib.get("NumChapter"), 0)
    if 总章数 <= 0:
        logger.warning(
            "书旗XML目录未提供有效总章数：book_id=%s, actual=%s",
            书籍编号,
            len(节点列表),
        )
    if (
        root.attrib.get("GatherId") == "1"
        and str(root.attrib.get("Vid") or "0") == "0"
        and all(not item.get("ContentURL") for item in 节点列表)
    ):
        分卷编号: list[str] = []
        已记录分卷: set[str] = set()
        无效分卷数 = 0
        重复分卷数 = 0
        for item in 节点列表:
            编号 = str(item.get("ChapterId") or "").strip()
            if not re.fullmatch(r"\d+", 编号):
                无效分卷数 += 1
                continue
            if 编号 in 已记录分卷:
                重复分卷数 += 1
                continue
            已记录分卷.add(编号)
            分卷编号.append(编号)
        if 无效分卷数 or 重复分卷数:
            logger.warning(
                "书旗XML分卷列表跳过无效项：book_id=%s, invalid=%s, duplicate=%s",
                书籍编号,
                无效分卷数,
                重复分卷数,
            )
        if not 分卷编号:
            raise ShuqiError("没有有效XML分卷", reason="empty_volumes")
        分卷信号量 = asyncio.Semaphore(4)

        async def 读取分卷(编号: str) -> list[dict[str, str]]:
            async with 分卷信号量:
                分卷 = await 请求书旗XML目录(session, 书籍编号, 编号)
                分卷总数 = 安全整数(分卷.attrib.get("NumChapter"), 0)
                if 总章数 > 0 and 分卷总数 != 总章数:
                    logger.warning(
                        "书旗XML分卷总数不一致：book_id=%s, vid=%s, root=%s, volume=%s",
                        书籍编号,
                        编号,
                        总章数,
                        分卷总数,
                    )
                return 提取XML目录节点(分卷)

        任务列表 = [asyncio.create_task(读取分卷(编号)) for 编号 in 分卷编号]
        try:
            分卷结果 = await asyncio.gather(*任务列表, return_exceptions=True)
        finally:
            for 任务 in 任务列表:
                if not 任务.done():
                    任务.cancel()
            await asyncio.gather(*任务列表, return_exceptions=True)
        节点列表 = []
        for 编号, 结果 in zip(分卷编号, 分卷结果):
            if isinstance(结果, BaseException):
                logger.warning(
                    "书旗XML分卷读取失败：book_id=%s, vid=%s, error_type=%s, reason=%s, http_status=%s",
                    书籍编号,
                    编号,
                    type(结果).__name__,
                    书旗失败原因(结果),
                    getattr(结果, "http_status", None) or "none",
                )
                continue
            节点列表.extend(结果)

    已记录: set[str] = set()
    有效节点: list[dict[str, str]] = []
    无效数量 = 0
    重复数量 = 0
    for item in 节点列表:
        章节编号 = str(item.get("ChapterId") or "").strip()
        正文URL = str(item.get("ContentURL") or "").strip()
        if not re.fullmatch(r"\d+", 章节编号) or not 校验书旗XML正文URL(
            正文URL, str(书籍编号), 章节编号
        ):
            无效数量 += 1
            continue
        if 章节编号 in 已记录:
            重复数量 += 1
            continue
        已记录.add(章节编号)
        item["ChapterId"] = 章节编号
        item["ContentURL"] = 正文URL
        有效节点.append(item)
    if 无效数量 or 重复数量:
        logger.warning(
            "书旗XML目录跳过无效条目：book_id=%s, invalid=%s, duplicate=%s",
            书籍编号,
            无效数量,
            重复数量,
        )
    if not 有效节点:
        raise ShuqiError("没有获取到有效XML章节", reason="empty_catalog")
    if 总章数 > 0 and len(有效节点) != 总章数:
        # NumChapter 与实际发布的 XML 列表可能更新不同步；真实丢条/坏条/失败卷已单独告警。
        logger.debug(
            "书旗XML声明与有效目录数量不同：reason=declared_count_mismatch, book_id=%s, declared=%s, actual=%s, action=continue",
            书籍编号,
            总章数,
            len(有效节点),
        )
    return dict(root.attrib), 有效节点


def 校验书旗XML正文URL(url: str, 书籍编号: str, 章节编号: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme.lower() not in {"http", "https"}:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.query or parsed.fragment:
            return False
        if hostname != "shuqireader.com" and not hostname.endswith(".shuqireader.com"):
            return False
        if parsed.port not in {None, 80, 443}:
            return False
    except ValueError:
        return False
    match = re.fullmatch(
        r"/httpserver/filecache/get_book_content_(\d+)_(\d+)_\d+_\d+_\d+\.xml",
        parsed.path,
    )
    return bool(match and match.group(1) == 书籍编号 and match.group(2) == 章节编号)


async def 请求GETXML章节正文(
    session: aiohttp.ClientSession, url: str
) -> str:
    headers = {
        "User-Agent": XML_USER_AGENT,
        "Accept": "application/xml,text/xml,*/*",
        "Accept-Encoding": "identity",
    }
    # 部分 CDN 会缓存 200 空正文；仅空响应时刷新同一原始地址的缓存。
    for 刷新缓存 in (False, True):
        参数 = {"_sq_retry": str(time.time_ns())} if 刷新缓存 else None
        async with session.get(
            url, params=参数, headers=headers, allow_redirects=False
        ) as resp:
            if resp.status < 200 or resp.status >= 300:
                raise ShuqiError(
                    "章节接口 HTTP 状态异常",
                    reason="http_status",
                    http_status=int(resp.status),
                )
            内容 = await resp.read()
        if 内容.strip():
            break
    else:
        raise ShuqiError(
            "章节接口正文为空", reason="empty_body", http_status=int(resp.status)
        )
    try:
        root = ET.fromstring(内容)
    except ET.ParseError as exc:
        raise ShuqiError("章节接口 XML 格式异常", reason="xml_parse") from exc
    if root.tag.rsplit("}", 1)[-1] != "ChapterContent":
        raise ShuqiError("章节接口 XML 根节点异常", reason="xml_root")
    正文 = "".join(root.itertext()).strip()
    if not 正文:
        raise ShuqiError("章节接口加密正文为空", reason="empty_payload")
    return 正文


def 解码章节正文(encoded: str) -> str:
    b64 = codecs.decode("".join(encoded.split()), "rot_13")
    if len(b64) % 4:
        b64 += "=" * (4 - len(b64) % 4)
    try:
        return base64.b64decode(b64, validate=True).decode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise ShuqiError("章节正文解码失败", reason="decrypt_failed") from exc


def 清理正文(decoded_html: str) -> str:
    text = html.unescape(decoded_html)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def 生成小说文件内容(书籍: Book, 章节内容: list[dict[str, str]]) -> tuple[str, bytes]:
    可用章节 = [
        章节 for 章节 in 章节内容 if str(章节.get("content") or "").strip()
    ]
    if not 可用章节:
        raise ShuqiError("没有获取到可用章节正文", reason="empty_decoded_content")
    文件名 = 生成小说文件名(书籍)
    内容列表 = [
        文件声明,
        "",
        f"名称：{书籍.book_name}",
        f"作者：{书籍.author_name or '未知'}",
        f"状态：{获取状态文本(书籍)}",
        f"字数：{格式化字数(书籍.word_count)}",
        f"书籍ID：{书籍.book_id}",
        f"章节数：{max(书籍.chapter_num, len(书籍.chapters))}",
        "",
    ]
    if 书籍.intro:
        内容列表.extend(["简介：", 书籍.intro, ""])
    for 章节 in 可用章节:
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
    文件文本 = "\n".join(内容列表).replace("\r\n", "\n").replace("\r", "\n")
    return 文件名, 文件文本.replace("\n", "\r\n").encode("utf-8")


def 生成小说文件名(书籍: Book) -> str:
    标题 = 清理文件名(书籍.book_name or f"书旗小说{书籍.book_id}")
    作者 = 清理文件名(书籍.author_name or "未知")
    return f"[{获取状态文本(书籍)}]书名：{标题} 作者：{作者}.txt"


def 格式化下载提示(书籍: Book) -> str:
    章节提示 = f"章节：{max(书籍.chapter_num, len(书籍.chapters))} 章"
    return "\n".join(
        [
            f"书名：{书籍.book_name or '未知'}",
            f"作者：{书籍.author_name or '未知'}",
            f"状态：{获取状态文本(书籍)}",
            章节提示,
            f"字数：{格式化字数(书籍.word_count)}",
            "",
            "正在下载中请稍等.....",
        ]
    )


def 获取状态文本(书籍: Book) -> str:
    return 书籍.status_text or "未知"


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
        删除小说缓存文件(缓存路径)
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
            删除小说缓存文件(缓存路径)
            return {
                "sent": False,
                "fallback_text": "",
                "source_cache_path": None,
                "error": str(网盘结果.get("error") or "小说网盘未启用"),
            }
        完成结果 = await 小说网盘.发送小说下载结果(
            event,
            书名,
            作者,
            网盘结果,
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
        删除小说缓存文件(缓存路径)
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
        删除小说缓存文件(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(exc),
        }


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    小说缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    文件缓存工具.标记小说缓存正在使用(缓存路径)
    return 缓存路径


def 删除小说缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    if not 文件缓存工具.删除小说缓存文件(缓存路径):
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
    缓存路径 = 小说缓存目录 / 安全文件名
    if not 缓存路径.exists():
        return 缓存路径
    for 序号 in range(1, 1000):
        候选路径 = 小说缓存目录 / f"{缓存路径.stem}_{序号}{缓存路径.suffix}"
        if not 候选路径.exists():
            return 候选路径
    raise RuntimeError("小说缓存目录中同名文件过多")


def _规范化书旗链接文本(值: str) -> str:
    文本 = str(值 or "")[:262144].strip().replace("\\/", "/")
    for _ in range(3):
        新文本 = html.unescape(文本)
        if 新文本 == 文本:
            break
        文本 = 新文本
    return 文本


def _校验书旗官方URL(值: str) -> str:
    文本 = _规范化书旗链接文本(值)
    文本 = 文本.rstrip(".,!?;:，。！？；：、）】》〉」』”’)]}>")
    try:
        parsed = urllib.parse.urlsplit(文本)
        主机 = (parsed.hostname or "").lower()
        官方主机 = 主机 in {"shuqi.com", "www.shuqi.com", "t.shuqi.com", "d.shuqi.com"}
        官方主机 = 官方主机 or bool(re.fullmatch(r"c[0-9]+\.shuqireader\.com", 主机))
        if not 官方主机 or parsed.scheme.lower() not in {"http", "https"}:
            return ""
        if parsed.username is not None or parsed.password is not None:
            return ""
        if parsed.port not in {None, 80, 443}:
            return ""
    except (TypeError, ValueError):
        return ""
    return urllib.parse.urlunsplit(parsed)


def _解析书旗官方URL(值: str, 深度: int = 0) -> dict[str, str] | None:
    if 深度 > 3:
        return None
    文本 = _规范化书旗链接文本(值)
    for _ in range(3):
        if re.match(r"^https?://", 文本, re.I):
            break
        新文本 = urllib.parse.unquote(文本)
        if 新文本 == 文本:
            break
        文本 = 新文本
    链接 = _校验书旗官方URL(文本)
    if not 链接:
        return None
    parsed = urllib.parse.urlsplit(链接)
    路径 = urllib.parse.unquote(parsed.path)
    类型 = "short" if re.fullmatch(r"/shortNovel/reader/[0-9]+/?", 路径, re.I) else "book"
    编号集合: set[str] = set()
    for 模式 in (
        r"/(?:catalog|cover)/([0-9]{1,20})/?",
        r"/shortNovel/reader/([0-9]{1,20})/?",
        r"/v2/query/([0-9]{1,20})(?:/[0-9]{1,20})?(?:\.html)?/?",
        r"/book/([0-9]{1,20})(?:\.html)?/?",
    ):
        匹配 = re.fullmatch(模式, 路径, re.I)
        if 匹配:
            编号集合.add(匹配.group(1))
            break
    try:
        参数 = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=64)
    except ValueError:
        return None
    嵌套目标: list[dict[str, str]] = []
    for 键, 值 in 参数:
        if 键.lower() in {"bid", "bookid"} and 值:
            if not re.fullmatch(r"[0-9]{1,20}", 值):
                return None
            编号集合.add(值)
        elif 键.lower() in {"url", "link", "redirect", "redirect_url", "redirect_uri", "target", "target_url", "share_url", "shareurl", "jump_url", "jumpurl"}:
            目标 = _解析书旗官方URL(值, 深度 + 1)
            if 目标 and (目标["book_id"] or urllib.parse.urlsplit(目标["url"]).hostname == "d.shuqi.com"):
                嵌套目标.append(目标)
                if 目标["book_id"]:
                    编号集合.add(目标["book_id"])
    if len(编号集合) > 1:
        return None
    if 嵌套目标 and not any(re.fullmatch(模式, 路径, re.I) for 模式 in (r"/(?:catalog|cover|book)/[0-9]+(?:\.html)?/?", r"/shortNovel/reader/[0-9]+/?", r"/v2/query/[0-9]+(?:/[0-9]+)?(?:\.html)?/?")):
        if not 编号集合 and len({目标["url"] for 目标 in 嵌套目标}) > 1:
            return None
        return next((目标 for 目标 in 嵌套目标 if 目标["book_id"]), 嵌套目标[0])
    return {"url": 链接, "book_id": next(iter(编号集合), ""), "type": 类型}


def 解析书旗下载目标(链接: str) -> dict[str, str]:
    目标 = _解析书旗官方URL(链接)
    if not 目标 or not 目标["book_id"]:
        raise ShuqiError("没有识别到书旗 bookId")
    return {"book_id": 目标["book_id"], "type": 目标["type"]}


def _提取书旗页面目标(文本: str, 基准链接: str) -> str:
    跳转链接: list[str] = []
    页面链接: list[str] = []
    for 标签 in re.findall(r"<(?:meta|link|a)\b[^>]{0,8192}>", 文本, re.I):
        属性 = {键.lower(): 值 for 键, _, 值 in re.findall(r"([\w-]+)\s*=\s*(['\"])(.*?)\2", 标签, re.S)}
        if re.match(r"<meta\b", 标签, re.I) and 属性.get("http-equiv", "").lower() == "refresh":
            匹配 = re.search(r"(?:^|;)\s*url\s*=\s*(.+)$", 属性.get("content", ""), re.I)
            if 匹配:
                跳转链接.append(匹配.group(1).strip(" '\""))
        elif re.match(r"<link\b", 标签, re.I) and 属性.get("rel", "").lower() == "canonical":
            跳转链接.append(属性.get("href", ""))
        elif re.match(r"<a\b", 标签, re.I):
            页面链接.append(属性.get("href", ""))
    for 脚本 in re.findall(r"<script\b[^>]*>(.*?)</script\s*>", 文本, re.I | re.S):
        跳转链接.extend(re.findall(r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]", 脚本, re.I))
        跳转链接.extend(re.findall(r"(?:window\.)?location\.(?:replace|assign)\(\s*['\"]([^'\"]+)['\"]", 脚本, re.I))
    for 候选列表 in (跳转链接, 页面链接):
        目标列表: list[dict[str, str]] = []
        for 候选 in 候选列表:
            目标 = _解析书旗官方URL(urllib.parse.urljoin(基准链接, _规范化书旗链接文本(候选)))
            if 目标 and (目标["book_id"] or urllib.parse.urlsplit(目标["url"]).hostname == "d.shuqi.com"):
                目标列表.append(目标)
        if 目标列表:
            编号集合 = {目标["book_id"] for 目标 in 目标列表 if 目标["book_id"]}
            链接集合 = {目标["url"] for 目标 in 目标列表}
            if len(编号集合) > 1 or (not 编号集合 and len(链接集合) > 1):
                return ""
            return next((目标["url"] for 目标 in 目标列表 if 目标["book_id"]), 目标列表[0]["url"])
    return ""


async def 解析书旗短链(session: aiohttp.ClientSession, 链接: str) -> str:
    目标 = _解析书旗官方URL(链接)
    if not 目标:
        raise ShuqiError("书旗分享链接无效")
    if 目标["book_id"]:
        return 目标["url"]
    当前链接 = 目标["url"]
    跳转数 = 0
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"}
    for 方法 in ("HEAD", "GET"):
        已访问: set[str] = set()
        while 当前链接 not in 已访问:
            已访问.add(当前链接)
            try:
                async with session.request(方法, 当前链接, headers=headers, allow_redirects=False) as resp:
                    if 300 <= resp.status < 400:
                        新链接 = _校验书旗官方URL(urllib.parse.urljoin(当前链接, resp.headers.get("Location", "")))
                        if not 新链接 or 新链接 == 当前链接 or 跳转数 >= 5:
                            raise ShuqiError("书旗短链跳转无效")
                        跳转数 += 1
                        当前链接 = 新链接
                    elif 200 <= resp.status < 300 and 方法 == "GET":
                        内容 = bytearray()
                        async with asyncio.timeout(20):
                            while True:
                                分块 = await resp.content.read(min(65536, 262145 - len(内容)))
                                if not 分块:
                                    break
                                内容.extend(分块)
                                if len(内容) > 262144:
                                    raise ShuqiError("书旗短链页面过大")
                        新链接 = _提取书旗页面目标(内容.decode("utf-8", errors="ignore"), 当前链接)
                        if not 新链接 or 新链接 == 当前链接 or 跳转数 >= 5:
                            raise ShuqiError("书旗短链页面未返回目标")
                        跳转数 += 1
                        当前链接 = 新链接
                    else:
                        break
                目标 = _解析书旗官方URL(当前链接)
                if not 目标:
                    raise ShuqiError("书旗短链目标无效")
                if 目标["book_id"]:
                    return 目标["url"]
            except ShuqiError:
                raise
            except Exception as exc:
                logger.debug("书旗短链解析重试：方法=%s，错误类型=%s", 方法, type(exc).__name__)
                break
    raise ShuqiError("书旗短链解析失败")


def 提取事件书旗链接(event: Any) -> str:
    消息对象 = 读取字段(event, "message_obj")
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            链接 = 提取书旗链接(读取字段(对象, 字段名))
            if 链接:
                return 链接
    return ""


def 提取书旗链接(值: Any) -> str:
    已访问: set[int] = set()
    已读节点 = 0

    def 遍历(对象: Any, 深度: int = 0) -> str:
        nonlocal 已读节点
        已读节点 += 1
        if 对象 is None or 深度 > 8 or 已读节点 > 256:
            return ""
        if isinstance(对象, (dict, list, tuple, set)):
            if id(对象) in 已访问:
                return ""
            已访问.add(id(对象))
            for 子值 in (对象.values() if isinstance(对象, dict) else 对象):
                链接 = 遍历(子值, 深度 + 1)
                if 链接:
                    return 链接
            return ""
        if not isinstance(对象, str):
            for 字段名 in ("data", "content", "text", "url", "jump_url"):
                子值 = 读取字段(对象, 字段名)
                if 子值 is not 对象:
                    链接 = 遍历(子值, 深度 + 1)
                    if 链接:
                        return 链接
            return ""
        文本 = _规范化书旗链接文本(对象)
        if 文本.startswith(("{", "[")):
            try:
                return 遍历(json.loads(文本), 深度 + 1)
            except (ValueError, TypeError):
                pass
        for _ in range(3):
            for 匹配 in re.finditer(r"https?://[^\s'\"<>，。！？；：、（）【】《》]+", 文本, re.I):
                目标 = _解析书旗官方URL(匹配.group(0))
                if not 目标:
                    continue
                parsed = urllib.parse.urlsplit(目标["url"])
                if 目标["book_id"] or parsed.hostname == "d.shuqi.com" or re.fullmatch(r"/sapi/book/sharecover/?", parsed.path, re.I):
                    return 目标["url"]
            新文本 = urllib.parse.unquote(文本)
            if 新文本 == 文本:
                break
            文本 = 新文本
        return ""

    return 遍历(值)


def 提取书籍编号(文本: str) -> str:
    文本 = str(文本 or "").strip()
    if re.fullmatch(r"[0-9]{4,20}", 文本):
        return 文本
    目标 = _解析书旗官方URL(文本)
    return 目标["book_id"] if 目标 else ""


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
