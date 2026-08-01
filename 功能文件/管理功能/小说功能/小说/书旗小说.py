from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import random
import re
import time
import urllib.parse
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
    logger.warning(f"小说网盘模块加载失败：error={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={exc}")

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
APP_USER_AGENT = "okhttp/3.12.13"
APP_VERSION_NAME = "12.6.4.262"
APP_VERSION_CODE = "260609"
APP_SUB_VERSION = "sqrelease"
APP_SOFT_ID = "1"
UID发现游客ID = "8000000"
APP_GATEWAY_SIGN_KEY = "467694bd8912441cae8498b3c7e4282c"
APP_CHAPTERLIST_URL = "https://ocean.shuqireader.com/api/bcspub/andapi/book/chapterlist/"
APP_SEARCH_URL = "https://ocean.shuqireader.com/sqan/render/render/search/native_v3"
APP_BOOK_COMMENT_LIST_URL = "https://ocean.shuqireader.com/api/interact/comment/book/list"
APP_NO_SIGN_KEYS = {"sign", "key", "_public", "_reqid", "_beta", "_", "X-NEBULAXMLHTTPREQUEST", "callbackUrl"}
UID自动搜索词 = ("剑来", "凡人修仙传", "斗破苍穹")
UID兜底书籍 = ("7106468",)
UID候选书上限 = 8
UID评论最大页数 = 3
UID评论每页数量 = 50
下载并发数 = 80
单章重试次数 = 3
进度日志分段数 = 10
下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


class ShuqiError(RuntimeError):
    pass


@dataclass
class Chapter:
    index: int
    chapter_id: str
    name: str
    is_free: bool
    is_buy: bool
    cont_url_suffix: str
    short_url_suffix: str
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
    free_prefix: str
    short_prefix: str
    charge_prefix: str
    chapters: list[Chapter]
    raw: dict[str, Any]
    is_short: bool = False


def 获取书旗小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[str] | None:
    下载链接 = 提取书旗链接(命令文本) or 提取直接书旗链接参数(命令文本) or 提取事件书旗链接(event)
    if 下载链接 is None:
        return None
    return 生成下载回复流(event, 下载链接, 配置)


async def 生成下载回复流(event: Any, 链接: str, 配置: Any = None) -> AsyncIterator[str]:
    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            解析后链接 = await 解析书旗短链(session, 链接)
            目标 = 解析书旗下载目标(解析后链接)
            用户ID = await 自动获取用户ID(session)
            书籍 = await 获取书籍(session, 目标["book_id"], 目标["type"] == "short", user_id=用户ID)
            if not 书籍.chapters:
                logger.warning(f"书旗小说下载失败：book_id={书籍.book_id}, error=没有获取到章节目录")
                yield "下载失败"
                return
            可读章节数 = 获取目录可读章节数(书籍)
            if 可读章节数 != len(书籍.chapters):
                logger.warning(
                    f"书旗小说下载失败：book_id={书籍.book_id}, error=目录授权不完整，"
                    f"readable={可读章节数}, total={len(书籍.chapters)}"
                )
                yield "下载失败"
                return
            logger.info(
                f"书旗小说开始下载：book_id={书籍.book_id}, type={'short' if 书籍.is_short else 'book'}, "
                f"title={书籍.book_name}, author={书籍.author_name}, chapters={len(书籍.chapters)}, source=catalog_single"
            )
            yield 格式化下载提示(书籍)
            章节内容 = await 下载全部章节(session, 书籍, user_id=用户ID)
            成功章节 = [项目 for 项目 in 章节内容 if 项目["content"]]
            if len(成功章节) != len(书籍.chapters):
                logger.warning(
                    f"书旗小说下载失败：book_id={书籍.book_id}, error=章节正文不完整，"
                    f"success={len(成功章节)}, total={len(书籍.chapters)}"
                )
                yield "下载失败"
                return
            文件名, 文件内容 = 生成小说文件内容(书籍, 章节内容)
            logger.info(
                f"书旗小说章节下载完成：book_id={书籍.book_id}, title={书籍.book_name}, "
                f"success={len(成功章节)}, total={len(书籍.chapters)}, file_size={len(文件内容)}"
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
                启动百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
                return
            降级文本 = str(发送结果.get("fallback_text") or "")
            if 降级文本:
                try:
                    yield 降级文本
                finally:
                    启动百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
                return
            if not 发送结果.get("sent"):
                logger.warning(f"书旗小说完成消息发送失败：book_id={书籍.book_id}, file={文件名}, error={发送结果.get('error')}")
                yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(f"书旗小说下载失败：source={链接}, error={exc}")
        yield "下载失败"


def 解析书旗下载目标(链接: str) -> dict[str, str]:
    文本 = str(链接 or "").strip()
    类型 = "short" if re.search(r"/shortNovel/reader/\d+", 文本, re.I) else "book"
    书籍编号 = 提取书籍编号(文本)
    if not 书籍编号:
        raise ShuqiError("没有识别到书旗 bookId")
    return {"book_id": 书籍编号, "type": 类型}


async def 解析书旗短链(session: aiohttp.ClientSession, 链接: str) -> str:
    文本 = str(链接 or "").strip()
    if not re.search(r"https?://d\.shuqi\.com/[^\s'\"<>，。]+", 文本, re.I):
        return 文本
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*", "Connection": "close"}
    最后错误 = ""
    for 方法 in ("HEAD", "GET"):
        try:
            async with session.request(方法, 文本, headers=headers, allow_redirects=True) as resp:
                最终链接 = str(resp.url)
                if 最终链接 and 最终链接 != 文本 and 提取书籍编号(最终链接):
                    logger.info(f"书旗短链解析成功：source={文本}, target={最终链接}")
                    return 最终链接
                if 方法 == "GET":
                    页面文本 = await resp.text(errors="ignore")
                    页面链接 = 提取书旗链接(页面文本)
                    if 页面链接 and 提取书籍编号(页面链接):
                        logger.info(f"书旗短链页面解析成功：source={文本}, target={页面链接}")
                        return 页面链接
        except Exception as exc:
            最后错误 = str(exc)
    raise ShuqiError(f"书旗短链解析失败：{最后错误 or '未获取到跳转目标'}")


async def 获取书籍(
    session: aiohttp.ClientSession,
    书籍编号: str,
    是否短篇: bool = False,
    *,
    user_id: str,
) -> Book:
    数据 = await 请求书旗POST(session, APP_CHAPTERLIST_URL, 构造目录参数(书籍编号), user_id=user_id)
    state = str(数据.get("state") or 数据.get("status"))
    if state != "200":
        raise ShuqiError(f"目录接口异常：state={state}, message={数据.get('message')}")
    data = 数据.get("data") if isinstance(数据, dict) else {}
    if not isinstance(data, dict):
        raise ShuqiError("目录接口 data 为空")
    chapters: list[Chapter] = []
    for volume in data.get("chapterList") or []:
        if not isinstance(volume, dict):
            continue
        for item in volume.get("volumeList") or []:
            if not isinstance(item, dict) or not item.get("chapterId"):
                continue
            chapters.append(Chapter(
                index=len(chapters) + 1,
                chapter_id=str(item.get("chapterId") or ""),
                name=清理网页文本(item.get("chapterName") or f"第{len(chapters) + 1}章"),
                is_free=解析布尔值(item.get("isFreeRead")),
                is_buy=解析布尔值(item.get("isBuy")),
                cont_url_suffix=html.unescape(str(item.get("contUrlSuffix") or "")),
                short_url_suffix=html.unescape(str(item.get("shortContUrlSuffix") or "")),
                word_count=安全整数(item.get("wordCount") or item.get("chapterWordCount"), 0),
            ))
    return Book(
        book_id=书籍编号,
        book_name=清理网页文本(data.get("bookName") or f"书旗小说{书籍编号}"),
        author_name=清理网页文本(data.get("authorName") or "未知"),
        chapter_num=安全整数(data.get("chapterNum"), len(chapters)),
        word_count=获取书旗原始字数(data, chapters),
        intro=获取书旗简介(data),
        status_text=解析书旗状态(data),
        free_prefix=str(data.get("freeContUrlPrefix") or ""),
        short_prefix=str(data.get("shortContUrlPrefix") or ""),
        charge_prefix=str(data.get("chargeContUrlPrefix") or ""),
        chapters=chapters,
        raw=data,
        is_short=是否短篇,
    )


def 获取目录可读章节数(书籍: Book) -> int:
    return sum(
        1
        for 章节 in 书籍.chapters
        if 获取章节正文URL(书籍, 章节, include_preview=书籍.is_short)[0]
    )


async def 自动获取用户ID(session: aiohttp.ClientSession) -> str:
    候选书 = await 获取UID候选书(session)
    错误列表: list[str] = []
    for 书籍编号 in 候选书:
        try:
            书籍 = await 获取书籍(session, 书籍编号, user_id=UID发现游客ID)
            用户ID = await 从书评获取年费VIP用户ID(session, 书籍)
            if 用户ID:
                logger.info(f"书旗自动获取UID成功：source_book={书籍编号}, user_id={用户ID}")
                return 用户ID
        except Exception as exc:
            错误列表.append(f"{书籍编号}:{exc}")
    raise ShuqiError(f"自动获取书旗UID失败：{'; '.join(错误列表) or '没有找到有效年费VIP用户'}")


async def 获取UID候选书(session: aiohttp.ClientSession) -> list[str]:
    候选书: list[str] = []
    已记录: set[str] = set()

    def 添加候选(书籍编号: Any) -> None:
        编号 = str(书籍编号 or "").strip()
        if not re.fullmatch(r"\d+", 编号) or 编号 in 已记录 or len(候选书) >= UID候选书上限:
            return
        已记录.add(编号)
        候选书.append(编号)

    for 关键词 in UID自动搜索词:
        if len(候选书) >= UID候选书上限:
            break
        try:
            参数 = {
                "page": "searchResultV3",
                "query": 关键词,
                "fromSug": "0",
                "kind": "",
                "relatedBid": "",
                "showMore": "0",
                "showPost": "0",
                "showTypes": "",
                "pagination": json.dumps({"page": 1, "pageSize": UID候选书上限}, ensure_ascii=False),
            }
            数据 = await 请求书旗公共POST(session, APP_SEARCH_URL, 参数, user_id=UID发现游客ID)
            if str(数据.get("status") or 数据.get("state")) != "200":
                continue
            for 书籍编号 in 提取搜索书籍编号(数据, UID候选书上限):
                添加候选(书籍编号)
        except Exception:
            continue

    for 书籍编号 in UID兜底书籍:
        if 书籍编号 not in 已记录 and len(候选书) >= UID候选书上限:
            已移除 = 候选书.pop()
            已记录.discard(已移除)
        添加候选(书籍编号)
    return 候选书


def 提取搜索书籍编号(数据: Any, 上限: int) -> list[str]:
    结果: list[str] = []
    已记录: set[str] = set()

    def 遍历(对象: Any) -> None:
        if len(结果) >= 上限:
            return
        if isinstance(对象, dict):
            书籍编号 = str(对象.get("bookId") or 对象.get("bid") or 对象.get("id") or "").strip()
            标题 = 对象.get("bookName") or 对象.get("displayBookName") or 对象.get("title") or 对象.get("name")
            if 标题 and re.fullmatch(r"\d+", 书籍编号) and 书籍编号 not in 已记录:
                已记录.add(书籍编号)
                结果.append(书籍编号)
            for 值 in 对象.values():
                遍历(值)
        elif isinstance(对象, list):
            for 值 in 对象:
                遍历(值)

    遍历(数据.get("data", 数据) if isinstance(数据, dict) else 数据)
    return 结果


async def 从书评获取年费VIP用户ID(session: aiohttp.ClientSession, 书籍: Book) -> str:
    item_index = 0
    for _ in range(UID评论最大页数):
        参数 = {
            "userId": UID发现游客ID,
            "authorId": 书籍.raw.get("authorId") or "",
            "bookId": 书籍.book_id,
            "chapterId": "",
            "paragraphId": "",
            "itemIndex": str(item_index),
            "size": str(UID评论每页数量),
            "sort": "1",
            "type": "1",
            "filterCommentIds": "",
        }
        数据 = await 请求书旗POST(session, APP_BOOK_COMMENT_LIST_URL, 参数, user_id=UID发现游客ID)
        state = str(数据.get("status") or 数据.get("state"))
        if state != "200":
            raise ShuqiError(f"书评接口异常：state={state}, message={数据.get('message')}")
        返回数据 = 数据.get("data") if isinstance(数据.get("data"), dict) else {}
        for 评论 in 返回数据.get("commentList") or []:
            if not isinstance(评论, dict):
                continue
            VIP状态 = 评论.get("vipStatus")
            if not isinstance(VIP状态, dict):
                continue
            if 安全整数(VIP状态.get("status")) != 2 or 安全整数(VIP状态.get("annualVipStatus")) != 1:
                continue
            用户ID = str(评论.get("userId") or 评论.get("uid") or "").strip()
            if re.fullmatch(r"\d+", 用户ID) and 用户ID != "0":
                return 用户ID
        next_index = 安全整数(返回数据.get("nextItemIndex"), item_index + UID评论每页数量)
        if not 返回数据.get("hasMore") or next_index == item_index:
            break
        item_index = next_index
    return ""


async def 下载全部章节(
    session: aiohttp.ClientSession,
    书籍: Book,
    *,
    user_id: str,
) -> list[dict[str, str]]:
    总数 = len(书籍.chapters)
    if not 总数:
        return []
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上次日志进度 = 0
    进度锁 = asyncio.Lock()
    信号量 = asyncio.Semaphore(下载并发数)
    logger.info(
        f"书旗小说章节进度：book_id={书籍.book_id}, progress=0/{总数}, "
        f"percent=0%, concurrency={下载并发数}, source=catalog_single, uid_bound={bool(user_id)}"
    )

    async def 记录进度(成功: bool) -> None:
        nonlocal 已完成, 成功数, 失败数, 上次日志进度
        async with 进度锁:
            已完成 += 1
            if 成功:
                成功数 += 1
            else:
                失败数 += 1
            当前进度 = 进度日志分段数 if 已完成 >= 总数 else int(已完成 * 进度日志分段数 / 总数)
            if 当前进度 <= 上次日志进度 and 已完成 < 总数:
                return
            上次日志进度 = 当前进度
            百分比 = int(已完成 * 100 / 总数) if 总数 else 100
            logger.info(f"书旗小说章节进度：book_id={书籍.book_id}, progress={已完成}/{总数}, percent={百分比}%, success={成功数}, failed={失败数}")

    async def 下载单章(章节: Chapter) -> dict[str, str]:
        async with 信号量:
            最后异常: Exception | None = None
            for 尝试次数 in range(1, 单章重试次数 + 1):
                try:
                    模式, 正文 = await 获取章节正文(session, 书籍, 章节, include_preview=书籍.is_short)
                    if not str(正文 or "").strip():
                        raise ShuqiError("章节正文为空")
                    await 记录进度(bool(正文))
                    标题 = 章节.name + ("（预览）" if 模式 == "preview" else "")
                    return {"id": 章节.chapter_id, "title": 标题, "content": 正文}
                except Exception as exc:
                    最后异常 = exc
                    logger.debug(
                        f"书旗章节下载失败，准备重试：book_id={书籍.book_id}, "
                        f"chapter_id={章节.chapter_id}, try={尝试次数}/{单章重试次数}, error={exc}"
                    )
                    if 尝试次数 < 单章重试次数:
                        await asyncio.sleep(min(1.5, 0.3 * 尝试次数))
            logger.warning(f"书旗章节下载最终失败：book_id={书籍.book_id}, chapter_id={章节.chapter_id}, error={最后异常}")
            await 记录进度(False)
            return {"id": 章节.chapter_id, "title": 章节.name, "content": ""}

    单章结果列表 = await asyncio.gather(*(下载单章(章节) for 章节 in 书籍.chapters))
    return list(单章结果列表)


async def 获取章节正文(session: aiohttp.ClientSession, 书籍: Book, 章节: Chapter, include_preview: bool = False) -> tuple[str, str]:
    url, 模式 = 获取章节正文URL(书籍, 章节, include_preview)
    if not url:
        return 模式, ""
    数据 = await 请求GETJSON(session, url, referer=APP_CHAPTERLIST_URL)
    state = str(数据.get("state") or 数据.get("status"))
    if state != "200":
        raise ShuqiError(f"章节接口异常：state={state}, message={数据.get('message')}")
    编码正文 = str(数据.get("ChapterContent") or "").strip()
    if not 编码正文:
        chapter_data = ((数据.get("data") or {}).get("chapter") or {}) if isinstance(数据.get("data"), dict) else {}
        编码正文 = str(chapter_data.get("content") or "").strip()
    if not 编码正文:
        return 模式, ""
    return 模式, 清理正文(解码章节正文(编码正文))


def 获取章节正文URL(书籍: Book, 章节: Chapter, include_preview: bool = False) -> tuple[str | None, str]:
    if 章节.is_free and 章节.cont_url_suffix:
        return 拼接章节URL(书籍.free_prefix, 章节.cont_url_suffix), "full"
    if 章节.is_buy and 章节.cont_url_suffix:
        return 拼接章节URL(书籍.charge_prefix or 书籍.free_prefix, 章节.cont_url_suffix), "full"
    if include_preview and 章节.short_url_suffix:
        return 拼接章节URL(书籍.short_prefix, 章节.short_url_suffix), "preview"
    return None, "skip"


def 拼接章节URL(前缀: str, 后缀: str) -> str | None:
    前缀文本 = html.unescape(str(前缀 or "")).strip()
    后缀文本 = html.unescape(str(后缀 or "")).strip()
    if not 后缀文本:
        return None
    if re.match(r"^https?://", 后缀文本, re.I):
        return 后缀文本
    if not 前缀文本:
        return None
    return urllib.parse.urljoin(前缀文本, 后缀文本)


async def 请求GETJSON(session: aiohttp.ClientSession, url: str, referer: str = "") -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*", "Accept-Encoding": "identity", "Connection": "close"}
    if referer:
        headers["Referer"] = referer
    async with session.get(url, headers=headers) as resp:
        text = await resp.text()
        if resp.status >= 400:
            raise ShuqiError(f"HTTP {resp.status}: {text[:120]}")
        try:
            data = json.loads(text)
        except Exception as exc:
            raise ShuqiError(f"JSON解析失败：{text[:120]}") from exc
        return data if isinstance(data, dict) else {}


async def 请求书旗POST(
    session: aiohttp.ClientSession,
    url: str,
    参数: dict[str, Any],
    *,
    user_id: str,
) -> dict[str, Any]:
    完整参数 = 构造公共参数字典(user_id=user_id, platform="0")
    完整参数.update({str(k): "" if v is None else str(v) for k, v in 参数.items()})
    完整参数["isTeenMode"] = "0"
    data = 签名参数(完整参数)
    headers = {"User-Agent": APP_USER_AGENT, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json,*/*", "Accept-Encoding": "identity", "Connection": "close"}
    async with session.post(url, data=data, headers=headers) as resp:
        text = await resp.text()
        if resp.status >= 400:
            raise ShuqiError(f"HTTP {resp.status}: {text[:120]}")
        try:
            payload = json.loads(text)
        except Exception as exc:
            raise ShuqiError(f"JSON解析失败：{text[:120]}") from exc
        return payload if isinstance(payload, dict) else {}


async def 请求书旗公共POST(
    session: aiohttp.ClientSession,
    url: str,
    参数: dict[str, Any],
    *,
    user_id: str,
    platform: str = "an",
) -> dict[str, Any]:
    完整参数: dict[str, Any] = {"_public": 构造公共参数(user_id=user_id, platform=platform)}
    完整参数.update({str(k): "" if v is None else str(v) for k, v in 参数.items()})
    完整参数["isTeenMode"] = "0"
    data = 签名参数(完整参数, add_reqid=False)
    headers = {"User-Agent": APP_USER_AGENT, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json,*/*", "Accept-Encoding": "identity", "Connection": "close"}
    async with session.post(追加请求ID(url), data=data, headers=headers) as resp:
        text = await resp.text()
        if resp.status >= 400:
            raise ShuqiError(f"HTTP {resp.status}: {text[:120]}")
        try:
            payload = json.loads(text)
        except Exception as exc:
            raise ShuqiError(f"JSON解析失败：{text[:120]}") from exc
        return payload if isinstance(payload, dict) else {}


def 构造目录参数(书籍编号: str) -> dict[str, Any]:
    return {"bookId": str(书籍编号), "timestamp": str(int(time.time() * 1000)), "reqEncryptType": "-1", "resEncryptType": "-1", "placeid": "", "apv": APP_VERSION_NAME}


def 签名参数(params: dict[str, Any], add_reqid: bool = True) -> dict[str, str]:
    signed = {str(k): "" if v is None else str(v) for k, v in params.items()}
    signed["sqSv"] = "1.0"
    signed["key"] = "sq_app_gateway"
    sign_items = {k: v for k, v in signed.items() if k not in APP_NO_SIGN_KEYS}
    raw = "".join(f"{k}={java_urlencode(sign_items[k])}&" for k in sorted(sign_items)) + f"skey={APP_GATEWAY_SIGN_KEY}"
    signed["sign"] = hashlib.md5(raw.encode("utf-8")).hexdigest()
    if add_reqid:
        signed["_reqid"] = 请求ID()
    return signed


def java_urlencode(value: Any) -> str:
    return urllib.parse.quote_plus("" if value is None else str(value), safe="*-._")


def 请求ID() -> str:
    seed = f"{time.time_ns()}-{random.getrandbits(32)}"
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:10]


def 追加请求ID(url: str) -> str:
    分隔符 = "&" if "?" in url else "?"
    return f"{url}{分隔符}_reqid={urllib.parse.quote(请求ID(), safe='')}"


def app_enc_value() -> str:
    value = str(int(time.time() * 1000))[:13]
    picked = value[1] + value[3] + value[5] + value[8] + value[6]
    product = (int(picked) if int(picked) != 0 else 12347) * 24697
    return str(product)[-5:] + value


def 构造公共参数字典(user_id: str, platform: str = "0") -> dict[str, str]:
    return {
        "soft_id": APP_SOFT_ID, "user_id": user_id, "userId": user_id, "ver": APP_VERSION_CODE, "subVer": APP_SUB_VERSION,
        "appVer": APP_VERSION_NAME, "theme": "day", "platform": platform, "placeid": "", "sdk": "", "cpu": "", "pkg_cpu": "",
        "wh": "1440x2560", "msv": "3", "enc": app_enc_value(), "vc": "", "mod": "SM-S9260", "manufacturer": "samsung",
        "brand": "Samsung", "net_type": "wifi", "net_type_str": "wifi", "first_placeid": "", "aak": "", "utype": "",
        "net": "4", "net_env": "4", "permissionType": "", "personalized": "1", "contentRecom": "1", "scene_code": "", "rom": "9",
    }


def 构造公共参数(user_id: str, platform: str = "an") -> str:
    params = {
        "soft_id": APP_SOFT_ID, "user_id": user_id, "userId": user_id, "ver": APP_VERSION_CODE, "subVer": APP_SUB_VERSION,
        "appVer": APP_VERSION_NAME, "theme": "day", "platform": platform, "placeid": "", "sdk": "", "cpu": "", "pkg_cpu": "",
        "wh": "1440x2560", "msv": "3", "enc": app_enc_value(), "vc": "", "mod": "SM-S9260", "manufacturer": "samsung",
        "brand": "Samsung", "net_type": "wifi", "net_type_str": "wifi", "first_placeid": "", "aak": "", "utype": "",
        "net": "4", "net_env": "4", "permissionType": "", "personalized": "1", "contentRecom": "1", "scene_code": "", "rom": "9",
    }
    return urllib.parse.urlencode(params, doseq=True)


def 解码章节正文(encoded: str) -> str:
    chars: list[str] = []
    for ch in encoded.strip():
        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            lower_code = ord(ch.lower())
            value = (lower_code - 83) % 26
            if value == 0:
                value = 26
            base = 64 if "A" <= ch <= "Z" else 96
            chars.append(chr(value + base))
        else:
            chars.append(ch)
    b64 = re.sub(r"[^A-Za-z0-9+/=]", "", "".join(chars))
    if len(b64) % 4:
        b64 += "=" * (4 - len(b64) % 4)
    return base64.b64decode(b64).decode("utf-8", errors="replace")


def 清理正文(decoded_html: str) -> str:
    text = html.unescape(decoded_html)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def 生成小说文件内容(书籍: Book, 章节内容: list[dict[str, str]]) -> tuple[str, bytes]:
    文件名 = 生成小说文件名(书籍)
    简介 = 获取书旗简介(书籍.raw) or 书籍.intro
    内容列表 = [
        文件声明,
        "",
        f"名称：{书籍.book_name}",
        f"作者：{书籍.author_name or '未知'}",
        f"状态：{获取状态文本(书籍)}",
        f"字数：{格式化字数(获取书旗总字数(书籍))}",
        f"书籍ID：{书籍.book_id}",
        f"章节数：{len(书籍.chapters)}",
        "",
    ]
    if 简介:
        内容列表.extend(["简介：", 简介, ""])
    for 章节 in 章节内容:
        if not 章节.get("content"):
            continue
        内容列表.append(str(章节.get("title") or ""))
        内容列表.append("")
        内容列表.append(str(章节.get("content") or "").strip())
        内容列表.append("")
    return 文件名, "\r\n".join(内容列表).encode("utf-8")


def 生成小说文件名(书籍: Book) -> str:
    标题 = 清理文件名(书籍.book_name or f"书旗小说{书籍.book_id}")
    作者 = 清理文件名(书籍.author_name or "未知")
    状态 = 获取状态文本(书籍)
    return f"[{状态}]书名：{标题} 作者：{作者}.txt"


def 格式化下载提示(书籍: Book) -> str:
    return "\n".join([f"书名：{书籍.book_name or '未知'}", f"作者：{书籍.author_name or '未知'}", f"状态：{获取状态文本(书籍)}", f"章节：{len(书籍.chapters)} 章", f"字数：{格式化字数(获取书旗总字数(书籍))}", "", "正在下载中请稍等....."])


def 获取状态文本(书籍: Book) -> str:
    if 书籍.status_text:
        return 书籍.status_text
    状态文本 = 解析书旗状态(书籍.raw)
    if 状态文本:
        return 状态文本
    文本 = json.dumps(书籍.raw, ensure_ascii=False).lower()
    if "完结" in 文本 or '"isover":true' in 文本 or '"finish"' in 文本:
        return "完结"
    return "连载"


def 获取书旗总字数(书籍: Book) -> int:
    return 书籍.word_count or 获取书旗原始字数(书籍.raw, 书籍.chapters)


def 获取书旗原始字数(data: dict[str, Any], chapters: list[Chapter]) -> int:
    for 字段名 in ("wordCount", "realTimeWordCount", "words", "word_count", "totalWords", "totalWordCount"):
        字数 = 安全整数(data.get(字段名), 0)
        if 字数 > 0:
            return 字数
    return sum(章.word_count for 章 in chapters)


def 获取书旗简介(data: dict[str, Any]) -> str:
    for 字段名 in ("intro", "desc", "description", "bookDesc", "summary", "brief", "abstract"):
        简介 = 清理网页文本(data.get(字段名))
        if 简介:
            return 简介
    return ""


def 解析书旗状态(data: dict[str, Any]) -> str:
    for 字段名 in ("statusText", "statusName", "stateName", "bookStatus", "serialStatus", "updateStatus", "finishStatus"):
        文本 = 清理网页文本(data.get(字段名))
        if "完结" in 文本 or "已完" in 文本:
            return "完结"
        if "连载" in 文本 or "更新" in 文本:
            return "连载"
    for 字段名 in ("isOver", "isFinished", "isFinish", "finish", "finished"):
        值 = data.get(字段名)
        if isinstance(值, bool):
            return "完结" if 值 else "连载"
        if str(值).lower() in ("1", "true", "yes"):
            return "完结"
    状态值 = str(data.get("state") or data.get("status") or data.get("updateType") or "").strip()
    if 状态值 == "2":
        return "完结"
    if 状态值:
        return "连载"
    return ""


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
    logger.info(f"书旗小说准备上传：file={文件名}, size={len(文件内容)}")
    缓存路径 = 写入下载缓存文件(文件名, 文件内容)
    logger.info(f"书旗小说写入下载缓存：file={缓存路径}, size={len(文件内容)}")
    if 小说网盘 is None:
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "小说网盘模块未加载"}
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        网盘名称 = str(网盘结果.get("provider") or "小说网盘")
        if not 网盘结果.get("success"):
            logger.warning(f"书旗小说主网盘上传失败：provider={网盘名称}, file={文件名}, error={网盘结果.get('error')}")
            删除下载缓存文件(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(网盘结果.get("error") or "小说网盘未启用")}
        完成结果 = await 小说网盘.发送小说下载完成链接(event, 书名, 作者, str(网盘结果.get("share_url") or ""))
        if 完成结果.get("sent"):
            logger.info(f"书旗小说主网盘上传并发送完成按钮成功：provider={网盘名称}, file={文件名}")
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 缓存路径, "error": str(完成结果.get("error") or "")}
        删除下载缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(完成结果.get("error") or "完成按钮发送失败")}
    except Exception as exc:
        logger.warning(f"书旗小说主网盘上传或完成消息发送失败：file={文件名}, error={exc}")
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
                    logger.info(f"书旗小说百度网盘后台上传成功：file={文件名}, fs_id={百度结果.get('file_id')}")
                elif 百度结果.get("skipped"):
                    logger.info(f"书旗小说百度网盘后台上传按状态规则跳过：file={文件名}")
                elif 百度结果.get("enabled"):
                    logger.warning(f"书旗小说百度网盘后台上传失败，不影响QQ发送：file={文件名}, error={百度结果.get('error')}")
        except Exception as exc:
            logger.warning(f"书旗小说百度网盘后台上传异常，不影响QQ发送：file={文件名}, error={exc}")
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
    try:
        Path(缓存路径).unlink(missing_ok=True)
        小说缓存工具.解除下载缓存占用(缓存路径)
        logger.info(f"书旗小说下载缓存文件已删除：file={缓存路径}")
    except Exception as exc:
        logger.warning(f"书旗小说下载缓存文件删除失败：file={缓存路径}, error={exc}")


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(缓存路径)
    return 缓存路径


def 生成不冲突缓存路径(文件名: str) -> Path:
    安全文件名 = Path(清理文件名(文件名)).name or "书旗小说.txt"
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


def 提取直接书旗链接参数(命令文本: str) -> str | None:
    文本 = str(命令文本 or "").strip()
    return 文本 if 包含书旗链接(文本) else None


def 提取事件书旗链接(event: Any) -> str | None:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            链接 = 提取书旗链接(读取字段(对象, 字段名))
            if 链接:
                return 链接
    return None


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
    for 模式 in (r"https?://d\.shuqi\.com/[^\s'\"<>，。]*", r"https?://(?:www\.)?shuqi\.com/book/\d+\.html[^\s'\"<>，。]*", r"https?://t\.shuqi\.com/(?:catalog|cover)/\d+/?[^\s'\"<>，。]*", r"https?://t\.shuqi\.com/shortNovel/reader/\d+/?[^\s'\"<>，。]*"):
        匹配 = re.search(模式, 文本, flags=re.I)
        if 匹配:
            return 匹配.group(0)
    return ""


def 包含书旗链接(文本: str) -> bool:
    return bool(re.search(r"d\.shuqi\.com/|shuqi\.com/book/\d+|t\.shuqi\.com/(?:catalog|cover)/\d+|t\.shuqi\.com/shortNovel/reader/\d+", str(文本 or ""), flags=re.I))


def 提取书籍编号(文本: str) -> str:
    文本 = str(文本 or "").strip()
    for 模式 in (r"/catalog/(\d+)/?", r"/cover/(\d+)/?", r"/shortNovel/reader/(\d+)/?", r"/book/(\d+)", r"[?&](?:bid|bookId)=(\d+)"):
        匹配 = re.search(模式, 文本, flags=re.I)
        if 匹配:
            return 匹配.group(1)
    return 文本 if re.fullmatch(r"\d{4,20}", 文本) else ""


def 清理网页文本(文本: Any) -> str:
    文本 = re.sub(r"<[^>]+>", "", str(文本 or ""))
    return html.unescape(文本).strip()


def 清理文件名(文件名: str) -> str:
    文件名 = re.sub(r'[\\/:*?"<>|]', "_", str(文件名 or "")).strip()
    return 文件名[:80] or "书旗小说"


def 安全整数(值: Any, 默认值: int = 0) -> int:
    try:
        return int(值)
    except Exception:
        return 默认值


def 解析布尔值(值: Any) -> bool:
    if isinstance(值, str):
        return 值.strip().lower() in {"1", "true", "yes", "on"}
    return bool(值)


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
