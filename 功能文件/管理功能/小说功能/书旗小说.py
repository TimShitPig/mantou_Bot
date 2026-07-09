from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import io
import json
import random
import re
import time
import urllib.parse
import zipfile
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
    from astrbot.api import message_components as Comp
except Exception:
    Comp = None

try:
    from 功能文件.管理功能.网盘功能 import UC网盘
except Exception as exc:
    UC网盘 = None
    logger.warning(f"UC网盘模块加载失败：error={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={exc}")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
APP_USER_AGENT = "okhttp/3.12.13"
APP_VERSION_NAME = "12.6.4.262"
APP_VERSION_CODE = "260609"
APP_SUB_VERSION = "sqrelease"
APP_SOFT_ID = "1"
DEFAULT_USER_ID = "8000000"
APP_GATEWAY_SIGN_KEY = "467694bd8912441cae8498b3c7e4282c"
APP_CHAPTERLIST_URL = "https://ocean.shuqireader.com/api/bcspub/andapi/book/chapterlist/"
APP_DOWNLOAD_BATCH_INDEX_URL = "https://ocean.shuqireader.com/api/jspend/api/downloadbatch/index"
APP_BOOK_FREEDOWNURL = "https://ocean.shuqireader.com/api/bcspub/andapi/book/freedownurl"
APP_NO_SIGN_KEYS = {"sign", "key", "_public", "_reqid", "_beta", "_", "X-NEBULAXMLHTTPREQUEST", "callbackUrl"}
下载并发数 = 80
批量URL并发数 = 20
单章重试次数 = 3
进度日志分段数 = 10
下载缓存目录 = Path(__file__).resolve().parents[2] / "下载缓存"
文件组件缓存清理延迟 = 600
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
            书籍 = await 获取书籍(session, 目标["book_id"], 目标["type"] == "short")
            if not 书籍.chapters:
                yield "书旗小说下载失败：没有获取到章节目录"
                return
            批次 = await 获取下载批次(session, 书籍)
            logger.info(
                f"书旗小说开始下载：book_id={书籍.book_id}, type={'short' if 书籍.is_short else 'book'}, "
                f"title={书籍.book_name}, author={书籍.author_name}, chapters={len(书籍.chapters)}, batches={len(批次)}"
            )
            yield 格式化下载提示(书籍)
            章节内容 = await 下载全部章节(session, 书籍, 批次)
            成功章节 = [项目 for 项目 in 章节内容 if 项目["content"]]
            if not 成功章节:
                yield "书旗小说下载失败：没有获取到可用章节正文"
                return
            文件名, 文件内容 = 生成小说文件内容(书籍, 章节内容)
            logger.info(
                f"书旗小说章节下载完成：book_id={书籍.book_id}, title={书籍.book_name}, "
                f"success={len(成功章节)}, total={len(书籍.chapters)}, file_size={len(文件内容)}"
            )
            发送结果 = await 准备发送文本文件给当前会话(event, 文件名, 文件内容, 配置)
            文件发送结果 = 发送结果.get("chain_result")
            if 文件发送结果 is not None:
                try:
                    yield 文件发送结果
                finally:
                    启动百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名, 发送结果.get("cache_path"))
                    延迟删除下载缓存文件(发送结果.get("cache_path"))
                return
            if not 发送结果.get("sent"):
                yield f"书旗小说文件发送失败：{发送结果.get('error') or '未知错误'}"
    except Exception as exc:
        logger.warning(f"书旗小说下载失败：source={链接}, error={exc}")
        yield f"书旗小说下载失败：{exc}"


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


async def 获取书籍(session: aiohttp.ClientSession, 书籍编号: str, 是否短篇: bool = False) -> Book:
    数据 = await 请求书旗POST(session, APP_CHAPTERLIST_URL, 构造目录参数(书籍编号))
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
                is_free=bool(item.get("isFreeRead")),
                is_buy=bool(item.get("isBuy")),
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


async def 获取下载批次(session: aiohttp.ClientSession, 书籍: Book) -> list[dict[str, Any]]:
    try:
        参数 = {
            "userId": DEFAULT_USER_ID,
            "bookId": 书籍.book_id,
            "timestamp": str(int(time.time())),
            "platform": "an",
            "_public": 构造公共参数(platform="an"),
        }
        数据 = await 请求书旗POST(session, APP_DOWNLOAD_BATCH_INDEX_URL, 参数)
        state = str(数据.get("state") or 数据.get("status"))
        if state != "200":
            logger.warning(f"书旗小说批量接口不可用：book_id={书籍.book_id}, state={state}, message={数据.get('message')}")
            return []
        batch_info = ((数据.get("data") or {}).get("batchInfo") or {}) if isinstance(数据.get("data"), dict) else {}
        free_info = batch_info.get("freeInfo") if isinstance(batch_info, dict) else []
        if not isinstance(free_info, list):
            return []
        await 补全批量下载URL(session, 书籍, free_info)
        logger.info(f"书旗小说批量接口返回：book_id={书籍.book_id}, batches={len(free_info)}")
        return [项目 for 项目 in free_info if isinstance(项目, dict)]
    except Exception as exc:
        logger.warning(f"书旗小说批量接口请求失败，回退章节并发：book_id={书籍.book_id}, error={exc}")
        return []


async def 补全批量下载URL(session: aiohttp.ClientSession, 书籍: Book, 批次: list[Any]) -> None:
    有效批次 = [项目 for 项目 in 批次 if isinstance(项目, dict)]
    if not 有效批次:
        return
    章节位置 = {章节.chapter_id: idx for idx, 章节 in enumerate(书籍.chapters)}
    def 批次键(项目: dict[str, Any]) -> str:
        章节列表 = [str(v) for v in (项目.get("chapterIds") or []) if str(v)]
        first_cid = str(项目.get("firstChapterId") or 项目.get("startCid") or (章节列表[0] if 章节列表 else ""))
        last_cid = str(项目.get("lastChapterId") or 项目.get("endCid") or (章节列表[-1] if 章节列表 else first_cid))
        first_index = 章节位置.get(first_cid, 0)
        last_index = 章节位置.get(last_cid, first_index)
        return f"{DEFAULT_USER_ID}_{书籍.book_id}_{first_index}_{last_index}_{first_cid}_{last_cid}"
    batch_map = {批次键(项目): {"startCid": str(项目.get("firstChapterId") or 项目.get("startCid") or ""), "endCid": str(项目.get("lastChapterId") or 项目.get("endCid") or "")} for 项目 in 有效批次}
    参数 = {
        "bookId": 书籍.book_id,
        "timestamp": str(int(time.time())),
        "type": "4",
        "batchDown": "1",
        "batchChapterIds": json.dumps(batch_map, ensure_ascii=False, separators=(",", ":")),
        "user_id": DEFAULT_USER_ID,
        "newDownload": "1",
        "platform": "an",
        "reqEncryptType": "-1",
        "reqEncryptParam": "",
        "resEncryptType": "-1",
        "_public": 构造公共参数(platform="an"),
    }
    数据 = await 请求书旗POST(session, APP_BOOK_FREEDOWNURL, 参数)
    返回数据 = 数据.get("data") if isinstance(数据, dict) else {}
    if isinstance(返回数据, str):
        try:
            返回数据 = json.loads(返回数据)
        except Exception:
            返回数据 = {}
    if not isinstance(返回数据, dict):
        return
    unlocked = 0
    for 项目 in 有效批次:
        key = 批次键(项目)
        info = 返回数据.get(key)
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except Exception:
                info = {}
        if isinstance(info, dict):
            项目["downloadUnlocked"] = info.get("downloadUnlocked")
            项目["url"] = info.get("url") or ""
            if 项目["url"]:
                unlocked += 1
    logger.info(f"书旗小说批量包URL返回：book_id={书籍.book_id}, unlocked={unlocked}/{len(有效批次)}")


async def 下载全部章节(session: aiohttp.ClientSession, 书籍: Book, 批次: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    总数 = len(书籍.chapters)
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上次日志进度 = 0
    进度锁 = asyncio.Lock()
    批量结果 = await 下载批量包章节(session, 书籍, 批次 or [])
    if 批量结果:
        logger.info(
            f"书旗小说批量包正文命中：book_id={书籍.book_id}, "
            f"success={len(批量结果)}/{总数}, batches={len([项目 for 项目 in (批次 or []) if 项目.get('url')])}"
        )
    elif 批次:
        logger.info(f"书旗小说批量包URL不可用，回退单章动态并发：book_id={书籍.book_id}, batches={len(批次)}")

    待单章下载 = [章节 for 章节 in 书籍.chapters if 章节.chapter_id not in 批量结果]
    if not 待单章下载:
        return [批量结果.get(章节.chapter_id, {"id": 章节.chapter_id, "title": 章节.name, "content": ""}) for 章节 in 书籍.chapters]

    信号量 = asyncio.Semaphore(下载并发数)
    logger.info(
        f"书旗小说章节进度：book_id={书籍.book_id}, progress=0/{len(待单章下载)}, "
        f"percent=0%, concurrency={下载并发数}, batch_hit={len(批量结果)}"
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
                    await 记录进度(bool(正文))
                    标题 = 章节.name + ("（预览）" if 模式 == "preview" else "")
                    return {"id": 章节.chapter_id, "title": 标题, "content": 正文}
                except Exception as exc:
                    最后异常 = exc
                    logger.warning(
                        f"书旗章节下载失败，准备重试：book_id={书籍.book_id}, "
                        f"chapter_id={章节.chapter_id}, try={尝试次数}/{单章重试次数}, error={exc}"
                    )
                    if 尝试次数 < 单章重试次数:
                        await asyncio.sleep(min(1.5, 0.3 * 尝试次数))
            logger.warning(f"书旗章节下载最终失败：book_id={书籍.book_id}, chapter_id={章节.chapter_id}, error={最后异常}")
            await 记录进度(False)
            return {"id": 章节.chapter_id, "title": 章节.name, "content": ""}

    单章结果列表 = await asyncio.gather(*(下载单章(章节) for 章节 in 待单章下载))
    合并结果 = dict(批量结果)
    合并结果.update({项目["id"]: 项目 for 项目 in 单章结果列表})
    return [合并结果.get(章节.chapter_id, {"id": 章节.chapter_id, "title": 章节.name, "content": ""}) for 章节 in 书籍.chapters]


async def 下载批量包章节(session: aiohttp.ClientSession, 书籍: Book, 批次: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    可用批次 = [项目 for 项目 in 批次 if isinstance(项目, dict) and 项目.get("url")]
    if not 可用批次:
        return {}
    信号量 = asyncio.Semaphore(批量URL并发数)
    章节映射 = {章节.chapter_id: 章节 for 章节 in 书籍.chapters}
    结果: dict[str, dict[str, str]] = {}

    async def 下载一个批次(批次项: dict[str, Any]) -> dict[str, str]:
        async with 信号量:
            url = str(批次项.get("url") or "")
            数据 = await 请求字节(session, url, referer=APP_CHAPTERLIST_URL)
            return 解析书旗批量包(数据, user_id=DEFAULT_USER_ID)

    任务列表 = [asyncio.create_task(下载一个批次(批次项)) for 批次项 in 可用批次]
    try:
        for 已完成任务 in asyncio.as_completed(任务列表):
            try:
                正文映射 = await 已完成任务
            except Exception as exc:
                logger.warning(f"书旗批量包下载失败，后续回退单章：book_id={书籍.book_id}, error={exc}")
                continue
            for 章节编号, 正文 in 正文映射.items():
                章节 = 章节映射.get(str(章节编号))
                if not 章节 or not 正文:
                    continue
                结果[章节.chapter_id] = {"id": 章节.chapter_id, "title": 章节.name, "content": 正文}
    finally:
        for 任务 in 任务列表:
            if not 任务.done():
                任务.cancel()
    return 结果


def 解析书旗批量包(包数据: bytes, user_id: str = DEFAULT_USER_ID) -> dict[str, str]:
    if not 包数据:
        return {}
    if not zipfile.is_zipfile(io.BytesIO(包数据)):
        raise ShuqiError("书旗批量包不是 ZIP/SQB 格式")
    key = ord(str(user_id or DEFAULT_USER_ID)[-1]) & 0xFF
    结果: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(包数据)) as 压缩包:
        文件名列表 = sorted((名称 for 名称 in 压缩包.namelist() if 名称.lower().endswith(".sqc")), key=章节包排序键)
        if not 文件名列表:
            raise ShuqiError("书旗批量包没有 sqc 章节文件")
        for 名称 in 文件名列表:
            原始 = 压缩包.read(名称)
            明文 = bytes((字节 ^ key) for 字节 in 原始).decode("utf-8", "replace")
            章节编号 = Path(名称).stem
            正文 = 清理正文(明文)
            if 正文:
                结果[str(章节编号)] = 正文
    return 结果


def 章节包排序键(名称: str) -> tuple[int, str]:
    文件名 = Path(名称).stem
    try:
        return int(文件名), 名称
    except Exception:
        return 10**18, 名称


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
    if (章节.is_free or 章节.is_buy) and 章节.cont_url_suffix:
        return 书籍.free_prefix + 章节.cont_url_suffix, "full"
    if include_preview and 章节.short_url_suffix:
        return 书籍.short_prefix + 章节.short_url_suffix, "preview"
    return None, "skip"


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


async def 请求字节(session: aiohttp.ClientSession, url: str, referer: str = "") -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity", "Connection": "close"}
    if referer:
        headers["Referer"] = referer
    async with session.get(url, headers=headers) as resp:
        data = await resp.read()
        if resp.status >= 400:
            raise ShuqiError(f"HTTP {resp.status}: {data[:120]!r}")
        return data


async def 请求书旗POST(session: aiohttp.ClientSession, url: str, 参数: dict[str, Any]) -> dict[str, Any]:
    完整参数 = 构造公共参数字典(platform="0")
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


def app_enc_value() -> str:
    value = str(int(time.time() * 1000))[:13]
    picked = value[1] + value[3] + value[5] + value[8] + value[6]
    product = (int(picked) if int(picked) != 0 else 12347) * 24697
    return str(product)[-5:] + value


def 构造公共参数字典(user_id: str = DEFAULT_USER_ID, platform: str = "0") -> dict[str, str]:
    return {
        "soft_id": APP_SOFT_ID, "user_id": user_id, "userId": user_id, "ver": APP_VERSION_CODE, "subVer": APP_SUB_VERSION,
        "appVer": APP_VERSION_NAME, "theme": "day", "platform": platform, "placeid": "", "sdk": "", "cpu": "", "pkg_cpu": "",
        "wh": "1440x2560", "msv": "3", "enc": app_enc_value(), "vc": "", "mod": "SM-S9260", "manufacturer": "samsung",
        "brand": "Samsung", "net_type": "wifi", "net_type_str": "wifi", "first_placeid": "", "aak": "", "utype": "",
        "net": "4", "net_env": "4", "permissionType": "", "personalized": "1", "contentRecom": "1", "scene_code": "", "rom": "9",
    }


def 构造公共参数(user_id: str = DEFAULT_USER_ID, platform: str = "an") -> str:
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


async def 准备发送文本文件给当前会话(event: Any, 文件名: str, 文件内容: bytes, 配置: Any = None) -> dict[str, Any]:
    群号 = 获取群号(event)
    用户号 = 获取发送者QQ(event)
    logger.info(f"书旗小说准备发送文件：file={文件名}, size={len(文件内容)}, group_id={群号}, user_id={用户号}")
    缓存路径 = 写入下载缓存文件(文件名, 文件内容)
    logger.info(f"书旗小说写入下载缓存：file={缓存路径}, size={len(文件内容)}")
    发送缓存路径 = 缓存路径
    原小说缓存待删除 = False
    if UC网盘 is not None:
        UC结果 = await UC网盘.准备小说分享链接文件(配置, 缓存路径, 文件名, 写入下载缓存文件)
        if UC结果.get("success") and UC结果.get("cache_path"):
            发送缓存路径 = UC结果.get("cache_path")
            原小说缓存待删除 = True
            logger.info(f"书旗小说UC网盘上传成功，改发同名链接文件：file={文件名}, share_url={UC结果.get('share_url')}")
        elif UC结果.get("enabled"):
            logger.warning(f"书旗小说UC网盘上传失败，回退发送源文件：file={文件名}, error={UC结果.get('error')}")
    if Comp is not None and hasattr(event, "chain_result"):
        try:
            文件发送结果 = event.chain_result([Comp.File(name=文件名, file=str(发送缓存路径))])
            logger.info(f"书旗小说文件使用 AstrBot File 组件发送：file={文件名}, path={发送缓存路径}")
            return {"sent": True, "chain_result": 文件发送结果, "cache_path": 发送缓存路径, "source_cache_path": 缓存路径, "error": ""}
        except Exception as exc:
            logger.warning(f"书旗小说 AstrBot File 组件构建失败：file={文件名}, error={exc}")
    bot = getattr(event, "bot", None)
    api = getattr(bot, "api", None)
    调用方法 = getattr(api, "call_action", None)
    if not callable(调用方法):
        删除下载缓存文件(发送缓存路径)
        if 原小说缓存待删除:
            删除下载缓存文件(缓存路径)
        return {"sent": False, "chain_result": None, "cache_path": None, "error": "当前 bot 没有 api.call_action 接口，也无法使用 AstrBot File 组件"}
    发送成功 = False
    百度后台已启动 = False
    try:
        发送成功, 发送错误 = await 尝试发送缓存文件(调用方法, 群号, 用户号, 文件名, 发送缓存路径)
        if 发送成功 and 百度网盘 is not None:
            百度后台已启动 = True
            启动百度后台上传并清理源文件(配置, 缓存路径, 文件名, None if str(缓存路径) == str(发送缓存路径) else 发送缓存路径)
        return {"sent": 发送成功, "chain_result": None, "cache_path": None, "error": 发送错误}
    finally:
        if not (百度后台已启动 and str(缓存路径) == str(发送缓存路径)):
            删除下载缓存文件(发送缓存路径)
        if 原小说缓存待删除 and not 百度后台已启动:
            删除下载缓存文件(缓存路径)


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
        logger.info(f"书旗小说下载缓存文件已删除：file={缓存路径}")
    except Exception as exc:
        logger.warning(f"书旗小说下载缓存文件删除失败：file={缓存路径}, error={exc}")


def 延迟删除下载缓存文件(缓存路径: Any, 延迟秒数: int = 文件组件缓存清理延迟) -> None:
    if not 缓存路径:
        return
    async def 执行删除() -> None:
        await asyncio.sleep(延迟秒数)
        删除下载缓存文件(缓存路径)
    try:
        asyncio.create_task(执行删除())
    except RuntimeError:
        删除下载缓存文件(缓存路径)


async def 尝试发送缓存文件(调用方法: Any, 群号: str, 用户号: str, 文件名: str, 缓存路径: Path) -> tuple[bool, str]:
    错误列表 = []
    for 方法名, 文件参数 in (("path", str(缓存路径)), ("file_uri", 缓存路径.as_uri())):
        try:
            if 群号:
                await 调用方法("upload_group_file", group_id=群号, file=文件参数, name=文件名)
                logger.info(f"书旗小说文件发送成功：method={方法名}, target=group, file={文件名}, group_id={群号}")
                return True, ""
            await 调用方法("upload_private_file", user_id=用户号, file=文件参数, name=文件名)
            logger.info(f"书旗小说文件发送成功：method={方法名}, target=private, file={文件名}, user_id={用户号}")
            return True, ""
        except Exception as exc:
            错误列表.append(f"{方法名}: {exc}")
            logger.warning(f"书旗小说文件发送候选失败：method={方法名}, file={文件名}, error={exc}")
    return False, "；".join(错误列表)


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
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


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group", "get_group_openid"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "group_openid") or 读取字段(对象, "group_id") or 读取字段(对象, "group")
        if isinstance(值, dict):
            值 = 值.get("group_openid") or 值.get("group_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 获取发送者QQ(event: Any) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "sender_id") or 读取字段(对象, "user_id") or 读取字段(对象, "sender")
        if isinstance(值, dict):
            值 = 值.get("user_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
