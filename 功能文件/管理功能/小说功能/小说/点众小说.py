from __future__ import annotations

import asyncio
import json
import random
import re
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp
from astrbot.api import logger
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

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

下载缓存目录 = 小说缓存工具.下载缓存目录
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
最大章节并发数 = 60
最大目录并发数 = 500
失败章节重试轮数 = 3
最小章节并发数 = 4
初始章节并发数 = 16
每通道章节窗口 = 6
通道初始化并发数 = 4

# ===== 点众协议与加解密（原 _点众源码） =====

KEY = b"dz#7gfy)@#ylgz&m"
IV = b"$#iupdo)8^dcr*pt"
ST = "l1t5u51n1wk1yfor1ncrypt"
BASE = "https://asgportal.dianzhong.com/asg-portal/portal/client"  # 使用能工作的域名
CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
UA = (
    "Mozilla/5.0 (Linux; Android 12; SM-G9900 Build/V417IR; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/110.0.5481.154 Safari/537.36"
)


# -------------------- 加密/解密工具 --------------------
def enc(text: str) -> str:
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(text.encode("utf-8"), 16)).hex()


def dec(hex_str: str) -> str:
    return unpad(
        AES.new(KEY, AES.MODE_CBC, IV).decrypt(bytes.fromhex(hex_str)), 16
    ).decode("utf-8")


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# -------------------- 设备身份管理（完全复用 dz_simple.py） --------------------
def gen_utdid_tmp(ts_ms=None) -> str:
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    date = time.strftime("%Y%m%d%H%M%S", time.localtime(ts_ms / 1000.0))
    ms = f"{ts_ms % 1000:03d}"
    rand6 = "".join(random.choice(CHARS) for _ in range(6))
    return "A" + date + ms + rand6


def make_datas():
    now = int(time.time() * 1000)
    sid = str(uuid.uuid4())
    return {
        "version": "7.3.0",
        "pname": "com.dianzhong.reader",
        "channelCode": "TAXSEO1000000",
        "utdidTmp": gen_utdid_tmp(now),
        "token": "",
        "utdid": "",
        "os": "android",
        "osv": 32,
        "brand": "Samsung",
        "model": "SM-G9900",
        "manu": "Samsung",
        "userId": "",
        "launch": "third",
        "mchid": "",
        "nchid": "TAXSEO1000000",
        "session1": sid,
        "session2": sid,
        "installTime": now,
        "p": 20,
        "sex": 1,
        "launchNum": 1,
        "visitor": 1,
        "supportAd": 1,
        "changeChidDate": now,
    }


async def 异步调用接口(
    session: aiohttp.ClientSession,
    api: int,
    body: dict[str, Any],
    datas: dict[str, Any],
    *,
    timeout: int = 20,
) -> dict[str, Any]:
    body_plain = dumps(body)
    headers = {
        "User-Agent": "okhttp/4.10.0",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json; charset=utf-8",
        "st": ST,
        "datas": enc(dumps(datas)),
    }
    请求超时 = aiohttp.ClientTimeout(total=max(1, int(timeout or 20)))
    async with session.post(
        f"{BASE}/{api}",
        data=enc(body_plain),
        headers=headers,
        timeout=请求超时,
    ) as response:
        response.raise_for_status()
        文本 = await response.text(errors="replace")
    try:
        raw = json.loads(文本) if 文本 else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("点众接口未返回JSON") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("点众接口响应格式异常")
    data_plain = None
    data_json = None
    data = raw.get("data")
    if isinstance(data, str) and data:
        try:
            data_plain = dec(data)
            data_json = json.loads(data_plain)
        except Exception:
            # 部分错误响应会直接把明文 JSON 放在 data 中，保留参考工具的回退路径。
            data_plain = data
            try:
                明文回退 = json.loads(data)
            except (TypeError, json.JSONDecodeError):
                明文回退 = None
            if isinstance(明文回退, dict):
                data_json = 明文回退
    return {
        "http": response.status,
        "raw": raw,
        "data_json": data_json,
        "data_plain": data_plain,
    }


async def 初始化设备(session: aiohttp.ClientSession) -> dict[str, Any]:
    datas = make_datas()
    body = {
        "oaid": "",
        "userAgent": UA,
        "upgradeUserId": "",
        "requestType": 1,
        "ocpcSeconds": 0,
        "lastLeftPage": "",
    }
    res = await 异步调用接口(session, 1001, body, datas)
    raw = res["raw"] if isinstance(res["raw"], dict) else {}
    user_id = raw.get("userId")
    if user_id is None and isinstance(res["data_json"], dict):
        user_id = res["data_json"].get("userId")
        if user_id is None:
            user_id = (res["data_json"].get("userInfoVo") or {}).get("userId")
    if not user_id:
        raise RuntimeError("点众设备初始化失败")

    datas["userId"] = str(user_id)
    datas["visitor"] = 0
    if raw.get("changeChidDate"):
        datas["changeChidDate"] = raw["changeChidDate"]
    return datas


# -------------------- 工具函数 --------------------

# ===== 业务封装 =====

# 每个正文下载流程包含 0% 起始行，因此最多再输出 4 个进度节点。
进度日志分段数 = 4
点众域名正则 = re.compile(r"dianzhong\.com|dz\.|点众", re.I)
链接正则 = re.compile(r"https?://[^\s'\"<>]+", re.I)
书籍编号正则 = re.compile(r"(?:bookId|book[_-]?id|bid)=(\d{4,})", re.I)
路径编号正则 = re.compile(r"/(?:book|detail|chapter)/(\d{4,})", re.I)


def 计算动态章节并发数(章节数: int) -> int:
    return min(最大章节并发数, max(1, int(章节数 or 0)))


def 计算起始章节并发数(章节数: int, *, 重试: bool = False) -> int:
    上限 = 计算动态章节并发数(章节数)
    if 上限 <= 最小章节并发数:
        return 上限
    if 重试:
        return min(上限, max(最小章节并发数, 初始章节并发数 // 2))
    if 上限 <= 初始章节并发数:
        return 上限
    return 初始章节并发数


def 计算下一窗口并发数(当前并发: int, 成功数: int, 总数: int) -> int:
    if 总数 <= 0:
        return 当前并发
    成功率 = 成功数 / 总数
    if 成功率 >= 0.98:
        增量 = 16 if 当前并发 < 32 else 8
        return min(最大章节并发数, 当前并发 + 增量)
    if 成功率 >= 0.92:
        return min(最大章节并发数, 当前并发 + 4)
    if 成功率 >= 0.80:
        return max(最小章节并发数, 当前并发 - 4)
    return max(最小章节并发数, 当前并发 // 2)


def 获取点众小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[Any] | None:
    来源 = 提取直接点众来源(命令文本) or 提取事件点众来源(event)
    if 来源 is None:
        return None
    return 生成下载回复流(event, 来源, 配置)


async def 生成下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取书籍编号(来源)
    if not 书籍编号:
        yield "下载失败 请重试"
        return
    try:
        连接器 = aiohttp.TCPConnector(
            limit=最大目录并发数,
            limit_per_host=最大目录并发数,
            ttl_dns_cache=300,
            keepalive_timeout=30,
        )
        超时 = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=60)
        async with aiohttp.ClientSession(timeout=超时, connector=连接器) as session:
            datas = await 初始化设备(session)
            详情 = await 异步获取详情(session, datas, 书籍编号)
            目录 = await 异步获取目录(session, datas, 书籍编号)
            if not 目录:
                logger.warning(f"点众小说目录失败：书籍编号={书籍编号}")
                yield "下载失败 请重试"
                return
            书名 = str(详情.get("title") or 详情.get("bookName") or "未知")
            作者 = str(详情.get("author") or 详情.get("authorName") or "未知")
            状态原文 = str(详情.get("status") or 详情.get("serialStatus") or "")
            状态 = (
                "完结"
                if (
                    "完" in 状态原文
                    or str(详情.get("isEnd") or "") in {"1", "true", "True"}
                )
                else "连载"
            )
            字数 = 格式化字数(
                详情.get("wordCount")
                or 详情.get("words")
                or 详情.get("totalWordSize")
                or 详情.get("totalWords")
                or 详情.get("wordSize")
                or 详情.get("wordNum")
            )
            动态并发 = 计算动态章节并发数(len(目录))
            logger.info(
                f"点众小说开始下载：书籍编号={书籍编号}, 书名={书名}, 作者={作者}, "
                f"章节数={len(目录)}, 目录并发数={最大目录并发数}, "
                f"content_最大并发数={动态并发}"
            )
            yield "\n".join(
                [
                    f"书名：{书名}",
                    f"作者：{作者}",
                    f"状态：{状态}",
                    f"章节：{len(目录)} 章",
                    f"字数：{字数}",
                    "",
                    "正在下载中请稍等.....",
                ]
            )
            章节结果 = await 异步下载全部章节(书籍编号, 目录, 书名)
        成功 = [x for x in 章节结果 if x.get("content")]
        if len(成功) != len(目录):
            logger.warning(
                f"点众小说下载失败：书籍编号={书籍编号}, 成功={len(成功)}, 总数={len(目录)}"
            )
            yield "下载失败 请重试"
            return
        文件名, 文件内容 = 生成小说文件(书籍编号, 书名, 作者, 状态, 字数, 章节结果)
        发送结果 = await 准备发送文本文件(
            event, 文件名, 文件内容, 配置, 书名=书名, 作者=作者
        )
        if 发送结果.get("sent"):
            启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        降级 = str(发送结果.get("fallback_text") or "")
        if 降级:
            try:
                yield 降级
            finally:
                启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(
            f"点众小说下载失败：书籍编号={书籍编号}, 错误={type(exc).__name__}"
        )
        yield "下载失败 请重试"


async def 异步获取详情(
    session: aiohttp.ClientSession,
    datas: dict[str, Any],
    book_id: str,
) -> dict[str, Any]:
    res = await 异步调用接口(
        session, 1111, {"bookId": str(book_id), "chapterId": ""}, datas
    )
    data = res.get("data_json")
    if isinstance(data, dict):
        book = (
            data.get("bookDetail") or data.get("bookInfo") or data.get("book") or data
        )
        if isinstance(book, dict):
            return book
    return {}


async def 异步获取目录(
    session: aiohttp.ClientSession,
    datas: dict[str, Any],
    book_id: str,
) -> list[dict[str, Any]]:
    首页响应 = await 异步调用接口(
        session,
        1304,
        {"bookId": str(book_id), "chapterIndex": 0, "currentChapterId": ""},
        datas,
    )
    首页数据 = (
        首页响应.get("data_json") if isinstance(首页响应.get("data_json"), dict) else {}
    )
    首页 = (
        首页数据.get("chapterList")
        or 首页数据.get("chapters")
        or 首页数据.get("list")
        or []
    )
    if not isinstance(首页, list) or not 首页:
        return []
    book_info = (
        首页数据.get("bookInfo") if isinstance(首页数据.get("bookInfo"), dict) else {}
    )
    try:
        目录总数 = int(book_info.get("totalChapterNum") or 0)
    except (TypeError, ValueError):
        目录总数 = 0

    所有窗口: list[list[dict[str, Any]]] = [首页]
    if 目录总数 > len(首页):
        中心下标 = list(range(101, 目录总数 + 50, 101))
        信号量 = asyncio.Semaphore(min(最大目录并发数, len(中心下标)))

        async def 获取窗口(下标: int) -> list[dict[str, Any]]:
            try:
                async with 信号量:
                    res = await 异步调用接口(
                        session,
                        1304,
                        {
                            "bookId": str(book_id),
                            "chapterIndex": 下标,
                            "currentChapterId": "",
                        },
                        datas,
                    )
                data = (
                    res.get("data_json")
                    if isinstance(res.get("data_json"), dict)
                    else {}
                )
                items = (
                    data.get("chapterList")
                    or data.get("chapters")
                    or data.get("list")
                    or []
                )
                return items if isinstance(items, list) else []
            except Exception as exc:
                logger.debug(
                    f"点众目录窗口请求失败：书籍编号={book_id}, 序号={下标}, "
                    f"错误={type(exc).__name__}"
                )
                return []

        所有窗口.extend(
            窗口
            for 窗口 in await asyncio.gather(*(获取窗口(下标) for 下标 in 中心下标))
            if 窗口
        )

    章节映射: dict[str, tuple[int, dict[str, Any]]] = {}
    后备下标 = 0
    for 窗口 in 所有窗口:
        for it in 窗口:
            if not isinstance(it, dict):
                continue
            cid = str(it.get("chapterId") or it.get("id") or "").strip()
            if not cid:
                continue
            try:
                排序下标 = int(it.get("index"))
            except (TypeError, ValueError):
                排序下标 = 目录总数 + 后备下标
                后备下标 += 1
            章节映射[cid] = (
                排序下标,
                {
                    "id": cid,
                    "title": str(
                        it.get("chapterName")
                        or it.get("title")
                        or it.get("name")
                        or f"章节{cid}"
                    ),
                    "has_lock": it.get("hasLock") is True
                    or str(it.get("hasLock") or "").lower() in {"1", "true"},
                },
            )
    结果 = [章节 for _, 章节 in sorted(章节映射.values(), key=lambda 项: 项[0])]
    if 目录总数 and len(结果) != 目录总数:
        logger.warning(
            f"点众小说目录不完整：书籍编号={book_id}, 成功={len(结果)}, 总数={目录总数}"
        )
        return []
    return 结果


def _提取正文(data: dict[str, Any]) -> str:
    for key in ("content", "chapterContent", "text", "txt"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    chapter = data.get("chapterInfo") or data.get("chapter") or {}
    if isinstance(chapter, dict):
        for key in ("content", "chapterContent", "text", "txt"):
            val = chapter.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


async def 异步获取章节正文结果(
    session: aiohttp.ClientSession,
    datas: dict[str, Any],
    book_id: str,
    chapter_id: str,
    book_name: str = "",
) -> tuple[str, str]:
    source = {
        "origin": "ssym",
        "originName": "搜索页面",
        "channelId": "ssjgy",
        "channelName": "搜索结果页",
        "columnId": "gjc",
        "columnName": book_name or "未知",
        "contentType": "book_detail",
        "contentId": book_id,
        "contentName": book_name or "未知书籍",
        "triggerTime": int(time.time() * 1000),
        "strategyId": "",
        "expId": "",
        "logId": "",
        "strategyName": "",
        "channelPos": "",
        "columnPos": "0",
        "contentPos": "0",
        "otypeId": "",
        "otypeName": "",
    }
    body = {
        "bookId": str(book_id),
        "chapterId": str(chapter_id),
        "offset": 0,
        "confirmWatch": "1",
        "preload": "0",
        "noDd100": 1,
        "noDd300": 1,
        "source": dumps(source),
    }
    res = await 异步调用接口(session, 1303, body, datas)
    data = res.get("data_json") if isinstance(res.get("data_json"), dict) else {}
    if str(data.get("status")) == "5" and "orderPageVo" in data:
        order = data.get("orderPageVo")
        if not isinstance(order, dict):
            order = {}
        ad_key = None
        if isinstance(order.get("unlockOperate"), dict):
            ad_key = order["unlockOperate"].get("key")
        if not ad_key and isinstance(order.get("exitRetainOperate"), dict):
            ad_key = order["exitRetainOperate"].get("key")
        有广告解锁入口 = bool(ad_key)
        if ad_key:
            ad_res = await 异步调用接口(
                session, 1518, {"key": ad_key, "advertValue": 0.0}, datas
            )
            if str((ad_res.get("raw") or {}).get("code")) == "0":
                res = await 异步调用接口(session, 1303, body, datas)
                data = (
                    res.get("data_json")
                    if isinstance(res.get("data_json"), dict)
                    else {}
                )
        content = _提取正文(data)
        if content:
            return content, "ok"
        return "", "empty" if 有广告解锁入口 else "member_required"
    content = _提取正文(data)
    return content, "ok" if content else "empty"


async def 异步获取章节正文(
    session: aiohttp.ClientSession,
    datas: dict[str, Any],
    book_id: str,
    chapter_id: str,
    book_name: str = "",
) -> str:
    正文, _ = await 异步获取章节正文结果(session, datas, book_id, chapter_id, book_name)
    return 正文


async def 异步新建下载通道() -> tuple[aiohttp.ClientSession, dict[str, Any]] | None:
    for 尝试次数 in range(1, 4):
        连接器 = aiohttp.TCPConnector(
            limit=1,
            limit_per_host=1,
            ttl_dns_cache=300,
            keepalive_timeout=30,
        )
        超时 = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=60)
        会话 = aiohttp.ClientSession(timeout=超时, connector=连接器)
        try:
            return 会话, await 初始化设备(会话)
        except asyncio.CancelledError:
            await 会话.close()
            raise
        except Exception as exc:
            await 会话.close()
            logger.debug(
                f"点众下载通道初始化失败：尝试次数={尝试次数}/3, "
                f"错误={type(exc).__name__}"
            )
            if 尝试次数 < 3:
                await asyncio.sleep(0.2 * 尝试次数)
    return None


async def 异步执行章节下载轮(
    任务: list[tuple[int, dict[str, Any]]],
    书籍编号: str,
    书名: str,
    进度回调: Any = None,
    *,
    起始并发: int | None = None,
) -> list[tuple[int, dict[str, str]]]:
    if not 任务:
        return []

    async def 下载单章(
        会话: aiohttp.ClientSession,
        身份: dict[str, Any],
        下标: int,
        章: dict[str, Any],
    ) -> tuple[int, dict[str, str]]:
        cid = str(章.get("id") or "")
        标题 = str(章.get("title") or f"章节{cid}")
        正文 = ""
        访问状态 = "error"
        try:
            # 同一 App 身份只在本通道内串行使用，避免广告解锁状态交叉覆盖。
            正文, 访问状态 = await 异步获取章节正文结果(会话, 身份, 书籍编号, cid, 书名)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug(
                f"点众章节请求失败：书籍编号={书籍编号}, 章节编号={cid}, "
                f"错误={type(exc).__name__}"
            )
        if callable(进度回调):
            await 进度回调(bool(正文))
        return 下标, {"title": 标题, "content": 正文, "id": cid, "access": 访问状态}

    async def 执行通道(
        通道: tuple[aiohttp.ClientSession, dict[str, Any]],
        通道任务: list[tuple[int, dict[str, Any]]],
    ) -> list[tuple[int, dict[str, str]]]:
        会话, 身份 = 通道
        return [await 下载单章(会话, 身份, 下标, 章) for 下标, 章 in 通道任务]

    通道池: list[tuple[aiohttp.ClientSession, dict[str, Any]]] = []
    结果: list[tuple[int, dict[str, str]]] = []
    待处理 = list(任务)
    当前并发 = min(
        计算动态章节并发数(len(待处理)),
        max(1, int(起始并发 or 计算起始章节并发数(len(待处理)))),
    )

    async def 扩容至(目标并发: int) -> None:
        待创建 = max(0, 目标并发 - len(通道池))
        if not 待创建:
            return
        信号量 = asyncio.Semaphore(min(通道初始化并发数, 待创建))

        async def 创建一个通道() -> tuple[aiohttp.ClientSession, dict[str, Any]] | None:
            async with 信号量:
                return await 异步新建下载通道()

        新通道 = await asyncio.gather(*(创建一个通道() for _ in range(待创建)))
        通道池.extend(通道 for 通道 in 新通道 if 通道 is not None)

    async def 收缩至(目标并发: int) -> None:
        if len(通道池) <= 目标并发:
            return
        待关闭 = 通道池[目标并发:]
        del 通道池[目标并发:]
        await asyncio.gather(
            *(会话.close() for 会话, _ in 待关闭), return_exceptions=True
        )

    try:
        while 待处理:
            目标窗口并发 = min(当前并发, len(待处理))
            await 扩容至(目标窗口并发)
            活跃通道 = 通道池[: min(目标窗口并发, len(通道池))]
            if not 活跃通道:
                for 下标, 章 in 待处理:
                    cid = str(章.get("id") or "")
                    标题 = str(章.get("title") or f"章节{cid}")
                    if callable(进度回调):
                        await 进度回调(False)
                    结果.append((下标, {"title": 标题, "content": "", "id": cid}))
                break

            窗口任务数 = min(len(待处理), len(活跃通道) * 每通道章节窗口)
            当前窗口 = 待处理[:窗口任务数]
            del 待处理[:窗口任务数]
            通道任务 = [[] for _ in 活跃通道]
            for 序号, 项 in enumerate(当前窗口):
                通道任务[序号 % len(活跃通道)].append(项)

            窗口结果 = await asyncio.gather(
                *(
                    执行通道(通道, 分配任务)
                    for 通道, 分配任务 in zip(活跃通道, 通道任务)
                    if 分配任务
                )
            )
            扁平结果 = [项 for 通道结果 in 窗口结果 for 项 in 通道结果]
            结果.extend(扁平结果)
            窗口成功数 = sum(1 for _, 项 in 扁平结果 if 项.get("content"))
            原并发 = 当前并发
            当前并发 = 计算下一窗口并发数(当前并发, 窗口成功数, len(扁平结果))
            logger.debug(
                f"点众章节动态并发：书籍编号={书籍编号}, 窗口={len(扁平结果)}, "
                f"成功={窗口成功数}, 并发数={原并发}->{当前并发}"
            )
            if 窗口成功数 / max(len(扁平结果), 1) < 0.8:
                await 收缩至(当前并发)
                await asyncio.sleep(0.3)
    finally:
        await asyncio.gather(
            *(会话.close() for 会话, _ in 通道池), return_exceptions=True
        )

    return 结果


async def 异步下载全部章节(
    书籍编号: str,
    目录: list[dict[str, Any]],
    书名: str,
) -> list[dict[str, str]]:
    总数 = len(目录)
    结果: list[dict[str, str] | None] = [None] * 总数
    完成 = 0
    成功 = 0
    进度锁 = asyncio.Lock()
    下次进度 = 25

    async def 记录进度(成功一章: bool) -> None:
        nonlocal 完成, 成功, 下次进度
        async with 进度锁:
            完成 += 1
            if 成功一章:
                成功 += 1
            百分比 = int(完成 * 100 / max(总数, 1))
            if 百分比 >= 下次进度 or 完成 == 总数:
                while 下次进度 <= 百分比:
                    下次进度 += max(1, 100 // 进度日志分段数)
                logger.info(
                    f"点众小说章节进度：书籍编号={书籍编号}, 进度={完成}/{总数}, "
                    f"百分比={百分比}%, 成功={成功}, 失败={完成 - 成功}"
                )

    首轮并发 = 计算起始章节并发数(总数)
    logger.info(
        f"点众小说章节进度：书籍编号={书籍编号}, 进度=0/{总数}, 百分比=0%, "
        f"并发数={首轮并发}, 最大并发数={最大章节并发数}, 会话复用=分路"
    )
    首轮结果 = await 异步执行章节下载轮(
        list(enumerate(目录)), 书籍编号, 书名, 记录进度, 起始并发=首轮并发
    )
    for 下标, 章节结果 in 首轮结果:
        结果[下标] = 章节结果

    for 轮次 in range(1, 失败章节重试轮数 + 1):
        缺失任务 = [
            (i, 目录[i])
            for i, 项 in enumerate(结果)
            if not 项
            or (not 项.get("content") and 项.get("access") != "member_required")
        ]
        if not 缺失任务:
            break
        logger.debug(
            f"点众失败章节重试：书籍编号={书籍编号}, 轮次={轮次}/{失败章节重试轮数}, "
            f"缺失={len(缺失任务)}, 并发数={计算起始章节并发数(len(缺失任务), 重试=True)}"
        )
        重试结果 = await 异步执行章节下载轮(
            缺失任务,
            书籍编号,
            书名,
            起始并发=计算起始章节并发数(len(缺失任务), 重试=True),
        )
        恢复数 = 0
        for 下标, 章节结果 in 重试结果:
            if 章节结果.get("content"):
                结果[下标] = 章节结果
                恢复数 += 1
        logger.debug(
            f"点众失败章节重试结果：书籍编号={书籍编号}, 轮次={轮次}/{失败章节重试轮数}, "
            f"恢复={恢复数}, 仍缺失={len(缺失任务) - 恢复数}"
        )

    完整结果 = [
        项
        if 项 is not None
        else {
            "title": str(目录[i].get("title") or f"章节{目录[i].get('id') or ''}"),
            "content": "",
            "id": str(目录[i].get("id") or ""),
            "access": "missing",
        }
        for i, 项 in enumerate(结果)
    ]
    最终成功 = sum(1 for 项 in 完整结果 if 项.get("content"))
    会员锁定 = sum(1 for 项 in 完整结果 if 项.get("access") == "member_required")
    if 会员锁定:
        logger.warning(
            f"点众小说章节需要会员：书籍编号={书籍编号}, 会员锁定={会员锁定}, 总数={总数}"
        )
    logger.info(
        f"点众小说章节下载完成：书籍编号={书籍编号}, 成功={最终成功}, 总数={总数}, "
        f"文件就绪={最终成功 == 总数}"
    )
    return 完整结果


def 生成小说文件(
    书籍编号: str,
    书名: str,
    作者: str,
    状态: str,
    字数: str,
    章节结果: list[dict[str, str]],
) -> tuple[str, bytes]:
    文件名 = f"[{状态}]书名：{清理文件名(书名)} 作者：{清理文件名(作者)}.txt"
    行 = [
        文件声明,
        "",
        f"名称：{书名}",
        f"作者：{作者}",
        f"状态：{状态}",
        f"字数：{字数}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(章节结果)}",
        "",
    ]
    for 章 in 章节结果:
        if not 章.get("content"):
            continue
        标题 = str(章.get("title") or "章节")
        正文 = 去除章节正文重复标题(标题, 章.get("content"))
        行.extend([标题, "", 正文, ""])
    return 文件名, "\n".join(行).encode("utf-8")


async def 准备发送文本文件(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    缓存路径 = 写入缓存(文件名, 文件内容)
    if 小说网盘 is None:
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "小说网盘模块未加载",
        }
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not 网盘结果.get("success"):
            删除缓存(缓存路径)
            return {
                "sent": False,
                "fallback_text": "",
                "source_cache_path": None,
                "error": str(网盘结果.get("error") or "小说网盘未启用"),
            }
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(网盘结果.get("share_url") or "")
        )
        if 完成结果.get("sent"):
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
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(完成结果.get("error") or "完成消息发送失败"),
        }
    except Exception as exc:
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(exc),
        }


def 启动百度后台上传并清理(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    async def _任务() -> None:
        try:
            if 百度网盘 is not None and 源缓存路径:
                await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
        except Exception as exc:
            logger.warning(f"点众小说百度后台上传异常：文件={文件名}, 错误={exc}")
        finally:
            删除缓存(源缓存路径)

    try:
        asyncio.get_running_loop().create_task(_任务())
    except Exception:
        删除缓存(源缓存路径)


def 写入缓存(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 下载缓存目录 / 文件名
    序号 = 1
    while 路径.exists():
        路径 = 下载缓存目录 / f"{Path(文件名).stem}_{序号}.txt"
        序号 += 1
    路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(路径)
    return 路径


def 删除缓存(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    小说缓存工具.删除下载缓存文件(缓存路径)


def 提取直接点众来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or "")
    if not 点众域名正则.search(文本) and "bookId=" not in 文本:
        # 仅当明确点众域名时识别，避免误伤
        if "dianzhong" not in 文本.lower():
            return None
    if not 点众域名正则.search(文本) and "dianzhong" not in 文本.lower():
        return None
    m = 链接正则.search(文本)
    return m.group(0) if m else 文本.strip() or None


def 提取事件点众来源(event: Any) -> str | None:
    for 字段 in ("message_str", "message", "raw_message"):
        值 = getattr(event, 字段, None)
        if 值 is None:
            continue
        来源 = 提取直接点众来源(str(值))
        if 来源:
            return 来源
    return None


def 提取书籍编号(来源: str) -> str:
    文本 = str(来源 or "")
    for 正则 in (书籍编号正则, 路径编号正则):
        m = 正则.search(文本)
        if m:
            return m.group(1)
    m = re.search(r"(\d{5,})", 文本)
    return m.group(1) if m else ""


def 格式化字数(字数: Any) -> str:
    文本 = str(字数 or "").strip()
    if not 文本:
        return "未知"
    数字文本 = re.sub(r"[\s,，]", "", 文本)
    if 数字文本.endswith("字"):
        数字文本 = 数字文本[:-1]
    if 数字文本.replace(".", "", 1).isdigit():
        try:
            n = int(float(数字文本))
        except Exception:
            return 文本
        return f"{round(n / 10000, 1)}万字" if n >= 10000 else f"{n}字"
    return 文本


def 清理文件名(文件名: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", str(文件名 or "")).strip() or "未知"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    try:
        timeout = aiohttp.ClientTimeout(total=30, sock_connect=15, sock_read=20)
        connector = aiohttp.TCPConnector(limit=2, limit_per_host=2, ttl_dns_cache=300)
        async with aiohttp.ClientSession(
            timeout=timeout, connector=connector
        ) as session:
            datas = await 初始化设备(session)
            body = {"keyWord": 关键词, "page": 1, "type": 0}
            res = await 异步调用接口(session, 1203, body, datas)
    except Exception as exc:
        logger.warning(f"点众搜索失败：关键词={关键词}, 错误={exc}")
        return []
    data = res.get("data_json") if isinstance(res.get("data_json"), dict) else {}
    rows = data.get("bookList") or data.get("list") or data.get("books") or []
    if not isinstance(rows, list):
        rows = []
    结果 = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        book = item.get("bookInfo") if isinstance(item.get("bookInfo"), dict) else item
        book_id = str(book.get("bookId") or book.get("id") or "").strip()
        if not book_id:
            continue
        结果.append(
            {
                "title": book.get("bookName") or book.get("title") or "未知",
                "author": book.get("authorName") or book.get("author") or "未知",
                "book_id": book_id,
                "platform": "点众",
                "url": f"https://asgportal.dianzhong.com/book/{book_id}",
                "heat": 0,
                "score": 0,
            }
        )
        if len(结果) >= 需要数量:
            break
    return 结果
