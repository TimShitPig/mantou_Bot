"""QQ 浏览器小说的最小下载链路。

这里只处理搜索、详情、目录和正文。源项目中的 EPUB、封面、Cookie、
代理接口和独立上传逻辑不属于插件功能，统一交给现有小说网盘出口。
"""

from __future__ import annotations

import asyncio
import html
import json
import re
import uuid
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

from astrbot.api import logger

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception as exc:
    小说网盘 = None
    logger.warning("QQ浏览器小说网盘模块加载失败：error=%s", type(exc).__name__)

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题


QQ浏览器搜索地址 = "https://so.html5.qq.com/ajax/real/search_result"
QQ浏览器详情地址 = "https://novel.html5.qq.com/qbread/api/novel/bookInfo"
QQ浏览器目录地址 = "https://novel.html5.qq.com/qbread/api/book/all-chapter"
QQ浏览器正文地址 = "https://novel.html5.qq.com/be-api/content/ads-read"
QQ浏览器域名集合 = {"bookshelf.html5.qq.com", "novel.html5.qq.com", "qbnovel.qq.com"}
QQ浏览器搜索数量上限 = 30
QQ浏览器正文批量章节数 = 50
QQ浏览器正文最大并发数 = 4
QQ浏览器请求重试次数 = 3
QQ浏览器进度日志分段数 = 10
QQ浏览器下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
QQ浏览器文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
)
QQ浏览器下载失败提示 = "下载失败"
QQ浏览器文件发送失败提示 = "文件发送失败，请稍后再试"

QQ浏览器请求头 = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; zh-cn; V2183A Build/TP1A.220624.014) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
        "Chrome/89.0.4389.72 MQQBrowser/13.4 Mobile Safari/537.36"
    ),
    "Referer": "https://novel.html5.qq.com/",
    "Accept": "application/json, text/plain, */*",
}

QQ浏览器链接正则 = re.compile(
    r"(?:https?://(?:bookshelf\.html5\.qq\.com|novel\.html5\.qq\.com|qbnovel\.qq\.com)"
    r"[^\s<>\"']*|qb://ext/novelreader[^\s<>\"']*)",
    re.IGNORECASE,
)


def 创建QQ浏览器HTTP会话(并发数: int = QQ浏览器正文最大并发数) -> aiohttp.ClientSession:
    """创建只在内存中保存状态的会话，不读取或持久化 Cookie。"""
    并发数 = max(1, int(并发数 or 1))
    headers = dict(QQ浏览器请求头)
    headers["Q-GUID"] = uuid.uuid4().hex
    connector = aiohttp.TCPConnector(
        limit=并发数,
        limit_per_host=并发数,
        keepalive_timeout=30,
        ttl_dns_cache=300,
    )
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    return aiohttp.ClientSession(
        headers=headers,
        timeout=timeout,
        connector=connector,
        cookie_jar=aiohttp.DummyCookieJar(),
    )


async def 请求QQ浏览器JSON(
    HTTP会话: aiohttp.ClientSession,
    方法: str,
    地址: str,
    *,
    参数: dict[str, Any] | None = None,
    JSON数据: dict[str, Any] | None = None,
    重试次数: int = QQ浏览器请求重试次数,
) -> Any:
    """请求 QQ 浏览器接口并隐藏远端响应细节，调用方自行校验业务码。"""
    最后异常: Exception | None = None
    for 次数 in range(max(1, int(重试次数 or 1))):
        try:
            async with HTTP会话.request(
                方法,
                地址,
                params=参数,
                json=JSON数据,
                headers={"Content-Type": "application/json"} if JSON数据 is not None else None,
            ) as 响应:
                响应.raise_for_status()
                原始内容 = await 响应.read()
            if not 原始内容:
                raise RuntimeError("empty response")
            return json.loads(原始内容.decode("utf-8-sig", "replace"))
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, UnicodeError, RuntimeError) as 异常:
            最后异常 = 异常
            if 次数 + 1 < max(1, int(重试次数 or 1)):
                await asyncio.sleep(min(1.5, 0.25 * (次数 + 1)))
    raise RuntimeError("QQ浏览器接口请求失败") from 最后异常


def _QQ浏览器业务成功(数据: Any, 字段: str = "ret") -> bool:
    if not isinstance(数据, dict):
        return False
    值 = 数据.get(字段)
    return 值 in (0, "0", None) if 字段 == "code" else 值 in (0, "0")


def _QQ浏览器真值(值: Any) -> bool:
    if isinstance(值, bool):
        return 值
    if isinstance(值, (int, float)):
        return 值 != 0
    return str(值 or "").strip().lower() in {"1", "true", "yes", "y"}


def _清理QQ浏览器文本(值: Any, *, 保留换行: bool = False) -> str:
    文本 = html.unescape(str(值 or ""))
    文本 = 文本.replace("\r\n", "\n").replace("\r", "\n")
    if 保留换行:
        文本 = re.sub(r"\n{3,}", "\n\n", 文本)
    else:
        文本 = re.sub(r"\s+", " ", 文本)
    return 文本.strip()


def 格式化QQ浏览器字数(值: Any) -> str:
    if isinstance(值, bool):
        return "未知"
    文本 = re.sub(r"[\s,，]", "", str(值 or ""))
    if 文本.endswith("字"):
        文本 = 文本[:-1]
    if not 文本.isdigit():
        return "未知"
    字数 = int(文本)
    if 字数 <= 0:
        return "未知"
    if 字数 >= 10000:
        万字 = f"{字数 / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{万字}万字"
    return f"{字数}字"


def _QQ浏览器安全整数(值: Any, 默认值: int = 0) -> int:
    try:
        return int(float(str(值).strip()))
    except (TypeError, ValueError):
        return 默认值


def _QQ浏览器搜索书籍编号(*候选值: Any) -> str:
    for 候选 in 候选值:
        文本 = str(候选 or "").strip()
        if not 文本:
            continue
        匹配 = re.search(r"(?:^|_)(\d{6,})$", 文本)
        if 匹配:
            return 匹配.group(1)
        编号 = 提取QQ浏览器书籍编号(文本)
        if 编号:
            return 编号
    return ""


def 构造QQ浏览器链接(书籍编号: str) -> str:
    return f"https://bookshelf.html5.qq.com/autojump/intro?bookid={书籍编号}"


def _QQ浏览器候选文本(值: Any) -> list[str]:
    原文 = html.unescape(str(值 or "")).replace("\\/", "/").strip()
    if not 原文:
        return []
    候选 = [原文]
    当前 = 原文
    for _ in range(2):
        解码 = unquote(当前)
        if 解码 == 当前:
            break
        候选.append(解码)
        当前 = 解码
    return 候选


def _是QQ浏览器链接(值: Any) -> bool:
    try:
        解析 = urlparse(str(值 or ""))
    except Exception:
        return False
    主机 = str(解析.hostname or "").lower()
    if 主机 in QQ浏览器域名集合:
        return True
    return 解析.scheme.lower() == "qb" and 主机 == "ext" and 解析.path.lower().startswith("/novelreader")


def 提取QQ浏览器书籍编号(来源: Any) -> str:
    for 原文 in _QQ浏览器候选文本(来源):
        if not _是QQ浏览器链接(原文):
            continue
        try:
            查询 = parse_qs(urlparse(原文).query)
        except Exception:
            查询 = {}
        for 键, 值列表 in 查询.items():
            if 键.lower() in {"bookid", "resourceid", "book_id"}:
                for 值 in 值列表:
                    匹配 = re.fullmatch(r"\d{6,}", str(值 or "").strip())
                    if 匹配:
                        return 匹配.group(0)
        匹配 = re.search(r"(?:bookid|resourceid|book_id)\s*[=:]\s*[\"']?(\d{6,})", 原文, re.IGNORECASE)
        if 匹配:
            return 匹配.group(1)
        if urlparse(原文).hostname in QQ浏览器域名集合:
            匹配 = re.search(r"/(?:book|reader|intro)[^\d]{0,20}(\d{6,})(?:\D|$)", urlparse(原文).path, re.IGNORECASE)
            if 匹配:
                return 匹配.group(1)
    return ""


def 提取直接QQ浏览器来源(命令文本: Any) -> str | None:
    for 文本 in _QQ浏览器候选文本(命令文本):
        匹配 = QQ浏览器链接正则.search(文本)
        if 匹配:
            return 匹配.group(0).rstrip("\"'，。；;]}>")
    return None


def _收集QQ浏览器事件文本(值: Any, 候选: list[str], 已见对象: set[int], 深度: int = 0) -> None:
    # 分享卡片通常经过 event -> message_obj -> message -> component -> data。
    if 值 is None or 深度 > 8:
        return
    if isinstance(值, str):
        候选.append(值)
        return
    if isinstance(值, dict):
        for 项目 in 值.values():
            _收集QQ浏览器事件文本(项目, 候选, 已见对象, 深度 + 1)
        return
    if isinstance(值, (list, tuple, set)):
        for 项目 in 值:
            _收集QQ浏览器事件文本(项目, 候选, 已见对象, 深度 + 1)
        return
    对象标识 = id(值)
    if 对象标识 in 已见对象:
        return
    已见对象.add(对象标识)
    for 字段 in ("message_str", "message", "raw_message", "message_obj", "text", "content", "data"):
        try:
            项目 = getattr(值, 字段, None)
        except Exception:
            项目 = None
        _收集QQ浏览器事件文本(项目, 候选, 已见对象, 深度 + 1)
    try:
        文本 = str(值)
    except Exception:
        文本 = ""
    if re.search(r"(?:https?|qb)(?::|%3a)", 文本, re.IGNORECASE):
        候选.append(文本)


def 提取事件QQ浏览器来源(event: Any) -> str | None:
    文本候选: list[str] = []
    _收集QQ浏览器事件文本(event, 文本候选, set())
    for 文本 in 文本候选:
        来源 = 提取直接QQ浏览器来源(文本)
        if 来源:
            return 来源
    return None


def 解析QQ浏览器搜索结果(数据: Any) -> list[dict[str, Any]]:
    if not _QQ浏览器业务成功(数据, "code"):
        return []
    状态 = ((数据.get("data") or {}).get("state") if isinstance(数据, dict) else None) or []
    if not isinstance(状态, list):
        return []
    结果: list[dict[str, Any]] = []
    已见: set[str] = set()
    for 分组 in 状态:
        if not isinstance(分组, dict) or 分组.get("moduleName") != "NovelAggregation":
            continue
        项目列表 = 分组.get("items") or []
        if not isinstance(项目列表, list):
            continue
        for 项目 in 项目列表:
            if not isinstance(项目, dict):
                continue
            书籍编号 = _QQ浏览器搜索书籍编号(
                项目.get("docId"),
                分组.get("groupID"),
                项目.get("jump_url"),
            )
            标题 = _清理QQ浏览器文本(项目.get("title"))
            if not 书籍编号 or not 标题 or 书籍编号 in 已见:
                continue
            已见.add(书籍编号)
            结果.append(
                {
                    "book_id": 书籍编号,
                    "title": 标题,
                    "author": _清理QQ浏览器文本(项目.get("author")) or "未知",
                    "abstract": _清理QQ浏览器文本(项目.get("abstract"), 保留换行=True),
                    "url": 构造QQ浏览器链接(书籍编号),
                    "word_count": 0,
                    "score": 0,
                    "read_count": 0,
                    "heat": max(0, 1000 - len(结果)),
                    "is_finished": _QQ浏览器真值(项目.get("is_finished")),
                }
            )
    return 结果


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    关键词 = _清理QQ浏览器文本(关键词)
    if not 关键词:
        return []
    try:
        async with 创建QQ浏览器HTTP会话(2) as HTTP会话:
            数据 = await 请求QQ浏览器JSON(
                HTTP会话,
                "GET",
                QQ浏览器搜索地址,
                参数={"tabId": "360", "q": 关键词},
            )
        return 解析QQ浏览器搜索结果(数据)[: max(1, min(QQ浏览器搜索数量上限, int(需要数量 or 20)))]
    except Exception as 异常:
        logger.warning("QQ浏览器小说搜索失败：error=%s", type(异常).__name__)
        return []


def 解析QQ浏览器详情(数据: Any, 书籍编号: str) -> dict[str, Any]:
    if not _QQ浏览器业务成功(数据):
        return {}
    书籍信息 = (((数据.get("data") or {}).get("bookInfo")) if isinstance(数据, dict) else None) or {}
    if not isinstance(书籍信息, dict):
        return {}
    标题 = _清理QQ浏览器文本(书籍信息.get("resourceName"))
    if not 标题:
        return {}
    实际编号 = str(书籍信息.get("resourceID") or 书籍编号).strip() or 书籍编号
    return {
        "book_id": 实际编号,
        "title": 标题,
        "author": _清理QQ浏览器文本(书籍信息.get("author")) or "未知",
        "intro": _清理QQ浏览器文本(书籍信息.get("summary"), 保留换行=True),
        "status": "完结" if _QQ浏览器真值(书籍信息.get("isfinish")) else "连载",
        "word_count": 格式化QQ浏览器字数(书籍信息.get("contentsize")),
        "chapter_count": _QQ浏览器安全整数(书籍信息.get("serialnum")),
    }


async def 获取QQ浏览器书籍详情(HTTP会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    数据 = await 请求QQ浏览器JSON(
        HTTP会话,
        "GET",
        QQ浏览器详情地址,
        参数={"resourceId": str(书籍编号)},
    )
    return 解析QQ浏览器详情(数据, str(书籍编号))


def 解析QQ浏览器目录(数据: Any) -> list[dict[str, Any]]:
    if not _QQ浏览器业务成功(数据):
        return []
    行列表: Any = 数据.get("rows") if isinstance(数据, dict) else None
    if not isinstance(行列表, list):
        行列表 = ((数据.get("data") or {}).get("rows") if isinstance(数据, dict) else None) or []
    if not isinstance(行列表, list):
        return []
    目录: list[dict[str, Any]] = []
    for 行 in 行列表:
        if not isinstance(行, dict):
            continue
        章节编号 = str(行.get("serialID") or 行.get("serialUniqID") or "").strip()
        if not re.fullmatch(r"\d+", 章节编号):
            continue
        标题 = _清理QQ浏览器文本(行.get("serialName")) or f"第{章节编号}章"
        目录.append({"id": 章节编号, "title": 标题, "is_free": _QQ浏览器真值(行.get("isFree"))})
    return 目录


async def 获取QQ浏览器章节目录(HTTP会话: aiohttp.ClientSession, 书籍编号: str) -> list[dict[str, Any]]:
    数据 = await 请求QQ浏览器JSON(
        HTTP会话,
        "GET",
        QQ浏览器目录地址,
        参数={"bookId": str(书籍编号)},
    )
    return 解析QQ浏览器目录(数据)


def _QQ浏览器正文文本(值: Any) -> str:
    if isinstance(值, list):
        return "\n".join(文本 for 文本 in (_QQ浏览器正文文本(项目) for 项目 in 值) if 文本)
    if isinstance(值, dict):
        for 键 in ("Content", "content", "Text", "text", "paragraph"):
            if 键 in 值:
                return _QQ浏览器正文文本(值.get(键))
        return ""
    return _清理QQ浏览器文本(值, 保留换行=True)


def 解析QQ浏览器正文(数据: Any) -> dict[str, str]:
    if not _QQ浏览器业务成功(数据):
        return {}
    内容列表 = ((数据.get("data") or {}).get("Content") if isinstance(数据, dict) else None) or []
    if not isinstance(内容列表, list):
        return {}
    结果: dict[str, str] = {}
    for 项目 in 内容列表:
        if not isinstance(项目, dict):
            continue
        锚点 = 项目.get("ContentAnchor") or {}
        章节信息 = 项目.get("ChapterInfo") or {}
        章节编号 = ""
        for 对象 in (锚点, 章节信息):
            if not isinstance(对象, dict):
                continue
            for 键 in ("ChapterSeqNo", "ChapterID", "SerialID", "serialID"):
                值 = 对象.get(键)
                if 值 is not None and str(值).strip():
                    章节编号 = str(值).strip()
                    break
            if 章节编号:
                break
        正文 = _QQ浏览器正文文本(项目.get("Content"))
        if 章节编号 and 正文:
            结果[章节编号] = 正文
    return 结果


async def _获取QQ浏览器正文批次(
    HTTP会话: aiohttp.ClientSession,
    书籍编号: str,
    章节编号列表: list[str],
) -> dict[str, str]:
    请求体 = {
        "ContentAnchorBatch": [
            {"BookID": str(书籍编号), "ChapterSeqNo": [int(编号) if str(编号).isdigit() else str(编号) for 编号 in 章节编号列表]}
        ],
        "Scene": "chapter",
    }
    最后结果: dict[str, str] = {}
    for 次数 in range(QQ浏览器请求重试次数):
        try:
            数据 = await 请求QQ浏览器JSON(
                HTTP会话,
                "POST",
                QQ浏览器正文地址,
                JSON数据=请求体,
                重试次数=1,
            )
        except Exception:
            if 次数 + 1 < QQ浏览器请求重试次数:
                await asyncio.sleep(0.3 * (次数 + 1))
                continue
            return 最后结果
        最后结果.update(解析QQ浏览器正文(数据))
        if all(编号 in 最后结果 for 编号 in 章节编号列表):
            return 最后结果
        if 次数 + 1 < QQ浏览器请求重试次数:
            await asyncio.sleep(0.3 * (次数 + 1))
    return 最后结果


async def 下载QQ浏览器全部章节(
    HTTP会话: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    结果: list[dict[str, Any] | None] = [None] * len(目录)
    批次: list[tuple[list[str], list[int]]] = []
    当前编号: list[str] = []
    当前下标: list[int] = []
    for 下标, 章节 in enumerate(目录):
        编号 = str(章节.get("id") or "").strip()
        if not 编号:
            continue
        当前编号.append(编号)
        当前下标.append(下标)
        if len(当前编号) >= QQ浏览器正文批量章节数:
            批次.append((当前编号, 当前下标))
            当前编号, 当前下标 = [], []
    if 当前编号:
        批次.append((当前编号, 当前下标))
    if not 批次:
        return []

    实际并发数 = max(1, min(QQ浏览器正文最大并发数, len(批次)))
    信号量 = asyncio.Semaphore(实际并发数)
    进度锁 = asyncio.Lock()
    已完成 = 0
    已成功 = 0
    下次进度 = max(1, len(目录) // QQ浏览器进度日志分段数)
    logger.info(
        "QQ浏览器小说章节进度：book_id=%s, progress=0/%s, percent=0%%, batches=%s, concurrency=%s",
        书籍编号,
        len(目录),
        len(批次),
        实际并发数,
    )

    async def 下载一批(章节编号列表: list[str], 下标列表: list[int]) -> None:
        nonlocal 已完成, 已成功, 下次进度
        async with 信号量:
            正文映射 = await _获取QQ浏览器正文批次(HTTP会话, 书籍编号, 章节编号列表)
        本批成功 = 0
        for 编号, 下标 in zip(章节编号列表, 下标列表):
            章节 = 目录[下标]
            正文 = str(正文映射.get(编号) or "").strip()
            if 正文:
                本批成功 += 1
            结果[下标] = {
                "id": 编号,
                "title": str(章节.get("title") or f"第{编号}章"),
                "content": 正文,
                "success": bool(正文),
            }
        async with 进度锁:
            已完成 += len(下标列表)
            已成功 += 本批成功
            当前百分比 = int(已完成 * 100 / max(1, len(目录)))
            if 已完成 == len(目录) or 已完成 >= 下次进度:
                logger.info(
                    "QQ浏览器小说章节进度：book_id=%s, progress=%s/%s, percent=%s%%, success=%s, failed=%s",
                    书籍编号,
                    已完成,
                    len(目录),
                    当前百分比,
                    已成功,
                    已完成 - 已成功,
                )
                下次进度 += max(1, len(目录) // QQ浏览器进度日志分段数)

    await asyncio.gather(*(下载一批(编号列表, 下标列表) for 编号列表, 下标列表 in 批次))
    输出: list[dict[str, Any]] = []
    for 下标, 章节 in enumerate(目录):
        项目 = 结果[下标]
        if 项目 is None:
            项目 = {
                "id": str(章节.get("id") or ""),
                "title": str(章节.get("title") or "章节"),
                "content": "",
                "success": False,
            }
        输出.append(项目)
    logger.info(
        "QQ浏览器小说章节下载完成：book_id=%s, success=%s, total=%s",
        书籍编号,
        sum(1 for 项目 in 输出 if 项目.get("success")),
        len(输出),
    )
    return 输出


def 清理QQ浏览器文件名(文件名: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(文件名 or "")).strip(" .")
    return 文本[:80] or "QQ浏览器小说"


def 生成QQ浏览器小说文件名(书籍编号: str, 书籍信息: dict[str, Any]) -> str:
    状态 = str(书籍信息.get("status") or "连载")
    书名 = 清理QQ浏览器文件名(书籍信息.get("title") or f"QQ浏览器小说{书籍编号}")
    作者 = 清理QQ浏览器文件名(书籍信息.get("author") or "未知")
    return f"[{状态}]书名：{书名} 作者：{作者}.txt"


def 编码QQ浏览器TXT内容(内容列表: list[str]) -> bytes:
    文本 = "\n".join(str(行) for 行 in 内容列表)
    文本 = 文本.replace("\r\n", "\n").replace("\r", "\n")
    return 文本.replace("\n", "\r\n").encode("utf-8")


def 生成QQ浏览器小说文件内容(
    书籍编号: str,
    书籍信息: dict[str, Any],
    目录: list[dict[str, Any]],
    章节结果: list[dict[str, Any]],
) -> tuple[str, bytes]:
    文件名 = 生成QQ浏览器小说文件名(书籍编号, 书籍信息)
    内容列表 = [
        QQ浏览器文件声明,
        "",
        f"名称：{书籍信息.get('title') or f'QQ浏览器小说{书籍编号}'}",
        f"作者：{书籍信息.get('author') or '未知'}",
        f"状态：{书籍信息.get('status') or '连载'}",
        f"字数：{书籍信息.get('word_count') or '未知'}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(目录)}",
        "",
    ]
    简介 = str(书籍信息.get("intro") or "").strip()
    if 简介:
        内容列表.extend(["简介：", 简介, ""])
    for 章节 in 章节结果:
        if not 章节.get("success"):
            continue
        标题 = str(章节.get("title") or "章节")
        正文 = 去除章节正文重复标题(标题, 章节.get("content"))
        内容列表.extend([标题, "", 正文, ""])
    return 文件名, 编码QQ浏览器TXT内容(内容列表)


def 生成不冲突QQ浏览器缓存路径(文件名: str) -> Path:
    安全文件名 = Path(清理QQ浏览器文件名(文件名)).name or "QQ浏览器小说.txt"
    if not 安全文件名.lower().endswith(".txt"):
        安全文件名 = f"{安全文件名}.txt"
    路径 = QQ浏览器下载缓存目录 / 安全文件名
    if not 路径.exists():
        return 路径
    for 序号 in range(1, 1000):
        候选 = QQ浏览器下载缓存目录 / f"{路径.stem}_{序号}{路径.suffix}"
        if not 候选.exists():
            return 候选
    raise RuntimeError("QQ浏览器下载缓存文件名冲突")


def 写入QQ浏览器下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    QQ浏览器下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 生成不冲突QQ浏览器缓存路径(文件名)
    路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(路径)
    return 路径


def 删除QQ浏览器缓存文件(缓存路径: Any) -> None:
    if 缓存路径:
        小说缓存工具.删除下载缓存文件(缓存路径)


async def 准备发送QQ浏览器文本文件(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    缓存路径 = 写入QQ浏览器下载缓存文件(文件名, 文件内容)
    if 小说网盘 is None:
        删除QQ浏览器缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "小说网盘未加载"}
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not 网盘结果.get("success"):
            删除QQ浏览器缓存文件(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "小说网盘上传失败"}
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event,
            书名,
            作者,
            str(网盘结果.get("share_url") or ""),
        )
        if 完成结果.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 缓存路径, "error": ""}
        删除QQ浏览器缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "完成消息发送失败"}
    except Exception as 异常:
        logger.warning("QQ浏览器小说文件发送失败：error=%s", type(异常).__name__)
        删除QQ浏览器缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "小说文件发送失败"}


async def 生成QQ浏览器下载回复流(
    event: Any,
    来源: str,
    配置: Any = None,
) -> AsyncIterator[Any]:
    书籍编号 = 提取QQ浏览器书籍编号(来源)
    if not 书籍编号:
        yield QQ浏览器下载失败提示
        return
    try:
        async with 创建QQ浏览器HTTP会话(QQ浏览器正文最大并发数) as HTTP会话:
            详情, 目录 = await asyncio.gather(
                获取QQ浏览器书籍详情(HTTP会话, 书籍编号),
                获取QQ浏览器章节目录(HTTP会话, 书籍编号),
            )
            if not 详情 or not 目录:
                logger.warning("QQ浏览器小说详情或目录为空：book_id=%s", 书籍编号)
                yield QQ浏览器下载失败提示
                return
            书名 = str(详情.get("title") or "未知")
            作者 = str(详情.get("author") or "未知")
            logger.info(
                "QQ浏览器小说开始下载：book_id=%s, title=%s, author=%s, chapters=%s",
                书籍编号,
                书名,
                作者,
                len(目录),
            )
            yield "\n".join(
                [
                    f"书名：{书名}",
                    f"作者：{作者}",
                    f"状态：{详情.get('status') or '连载'}",
                    f"章节：{len(目录)} 章",
                    f"字数：{详情.get('word_count') or '未知'}",
                    "",
                    "正在下载中请稍等.....",
                ]
            )
            章节结果 = await 下载QQ浏览器全部章节(HTTP会话, 书籍编号, 目录)
        if len(章节结果) != len(目录) or any(not 项目.get("success") for 项目 in 章节结果):
            logger.warning(
                "QQ浏览器小说正文不完整：book_id=%s, success=%s, total=%s",
                书籍编号,
                sum(1 for 项目 in 章节结果 if 项目.get("success")),
                len(目录),
            )
            yield QQ浏览器下载失败提示
            return
        文件名, 文件内容 = 生成QQ浏览器小说文件内容(书籍编号, 详情, 目录, 章节结果)
        发送结果 = await 准备发送QQ浏览器文本文件(
            event,
            文件名,
            文件内容,
            配置,
            书名=书名,
            作者=作者,
        )
        if 发送结果.get("sent"):
            删除QQ浏览器缓存文件(发送结果.get("source_cache_path"))
            return
        降级文本 = str(发送结果.get("fallback_text") or "")
        if 降级文本:
            try:
                yield 降级文本
            finally:
                删除QQ浏览器缓存文件(发送结果.get("source_cache_path"))
            return
        yield QQ浏览器文件发送失败提示
    except Exception as 异常:
        logger.warning("QQ浏览器小说下载失败：error=%s", type(异常).__name__)
        yield QQ浏览器下载失败提示


def 获取QQ浏览器小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取直接QQ浏览器来源(命令文本) or 提取事件QQ浏览器来源(event)
    if 来源 is None or not 提取QQ浏览器书籍编号(来源):
        return None
    return 生成QQ浏览器下载回复流(event, 来源, 配置)
