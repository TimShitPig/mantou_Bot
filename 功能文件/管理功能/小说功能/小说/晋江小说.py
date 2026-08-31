"""晋江小说异步详情、目录和正文下载链路。

只保留晋江公开接口、可下载章节、TXT 生成和统一小说网盘出口。
付费章节、锁定章节和外部上传服务不在本模块处理范围内。
"""

from __future__ import annotations

import asyncio
import html
import json
import re
from pathlib import Path
from typing import Any, AsyncIterator, Mapping
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception:
    百度网盘 = None

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

晋江详情地址 = "https://app-cdn.jjwxc.net/androidapi/novelbasicinfo"
晋江目录地址 = "https://app-cdn.jjwxc.net/androidapi/chapterList"
晋江正文地址 = "https://app-cdn.jjwxc.net/androidapi/chapterContent"
晋江搜索地址 = "https://android.jjwxc.net/androidapi/search"
晋江域名集合 = {"jjwxc.net", "jjwxc.com"}
晋江请求并发上限 = 50
晋江搜索数量上限 = 30
晋江请求重试次数 = 3
晋江进度日志分段数 = 10
晋江下载缓存目录 = 小说缓存工具.下载缓存目录
晋江文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
)
晋江下载失败提示 = "下载失败 请重试"
晋江没有可下载章节提示 = "没有可下载章节"
晋江文件发送失败提示 = "文件发送失败，请稍后再试"
晋江请求头 = {
    "User-Agent": "okhttp/4.9.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}
晋江链接正则 = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def 创建晋江HTTP会话(并发数: int = 晋江请求并发上限) -> aiohttp.ClientSession:
    """创建下载期间复用的异步连接池。"""
    并发数 = max(1, min(int(并发数 or 1), 晋江请求并发上限))
    connector = aiohttp.TCPConnector(
        limit=并发数,
        limit_per_host=并发数,
        ttl_dns_cache=300,
        keepalive_timeout=30,
    )
    timeout = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    return aiohttp.ClientSession(
        headers=晋江请求头,
        timeout=timeout,
        connector=connector,
        cookie_jar=aiohttp.DummyCookieJar(),
    )


def _清理来源(值: Any) -> str:
    return (
        html.unescape(str(值 or ""))
        .replace("\\/", "/")
        .strip()
        .rstrip("\"'`，。；;]}>）)")
    )


def _文本候选(值: Any, 结果: list[str], 已见: set[int], 深度: int = 0) -> None:
    if 值 is None or 深度 > 8:
        return
    if isinstance(值, str):
        if 值.strip():
            结果.append(值)
        return
    if isinstance(值, Mapping):
        for 子值 in 值.values():
            _文本候选(子值, 结果, 已见, 深度 + 1)
        return
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            _文本候选(子值, 结果, 已见, 深度 + 1)
        return
    标识 = id(值)
    if 标识 in 已见:
        return
    已见.add(标识)
    for 字段 in (
        "message_str",
        "raw_message",
        "message",
        "message_obj",
        "text",
        "content",
        "data",
        "jump_url",
        "url",
    ):
        try:
            _文本候选(getattr(值, 字段, None), 结果, 已见, 深度 + 1)
        except Exception:
            continue


def _是晋江链接(链接: str) -> bool:
    try:
        主机 = (urlparse(链接).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return any(主机 == 域名 or 主机.endswith(f".{域名}") for 域名 in 晋江域名集合)


def 提取晋江来源(event: Any, 命令文本: Any = "") -> str | None:
    候选: list[str] = []
    _文本候选(命令文本, 候选, set())
    _文本候选(event, 候选, set())
    for 文本 in 候选:
        当前文本 = 文本
        for _ in range(2):
            当前文本 = unquote(当前文本)
        当前文本 = 当前文本.replace("\\/", "/")
        for 匹配 in 晋江链接正则.finditer(当前文本):
            链接 = _清理来源(匹配.group(0))
            if _是晋江链接(链接):
                return 链接
    return None


def 提取晋江书籍编号(来源: Any) -> str:
    文本 = _清理来源(来源)
    try:
        解析 = urlparse(文本)
    except ValueError:
        return ""
    if not _是晋江链接(文本):
        return ""
    查询 = parse_qs(解析.query, keep_blank_values=True)
    for 值 in 查询.get("novelid", []) + 查询.get("novelId", []):
        if re.fullmatch(r"\d{1,12}", str(值 or "")):
            return str(值)
    匹配 = re.search(
        r"/(?:book2|book|novel)/(\d{1,12})(?:[/?#]|$)", 解析.path, re.IGNORECASE
    )
    if 匹配:
        return 匹配.group(1)
    return ""


async def 请求晋江JSON(
    session: aiohttp.ClientSession,
    地址: str,
    参数: Mapping[str, Any],
    *,
    重试次数: int = 晋江请求重试次数,
) -> dict[str, Any]:
    最后异常: Exception | None = None
    for 次数 in range(max(1, int(重试次数 or 1))):
        try:
            async with session.get(地址, params=dict(参数)) as response:
                response.raise_for_status()
                raw = await response.read()
            data = json.loads(raw.decode("utf-8-sig", "replace"))
            if not isinstance(data, dict):
                raise ValueError("response is not object")
            return data
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            json.JSONDecodeError,
            UnicodeError,
            ValueError,
        ) as exc:
            最后异常 = exc
            if 次数 + 1 < max(1, int(重试次数 or 1)):
                await asyncio.sleep(min(1.5, 0.25 * (次数 + 1)))
    raise RuntimeError("晋江接口请求失败") from 最后异常


def _安全整数(值: Any, 默认值: int = 0) -> int:
    try:
        return int(float(str(值).strip()))
    except (TypeError, ValueError):
        return 默认值


def _是真值(值: Any) -> bool:
    if isinstance(值, bool):
        return 值
    if isinstance(值, (int, float)):
        return 值 != 0
    return str(值 or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def 格式化晋江字数(值: Any, 格式化值: Any = "") -> str:
    原始 = str(格式化值 or 值 or "").strip()
    if not 原始:
        return "未知"
    if "万" in 原始:
        return 原始 if 原始.endswith("字") else f"{原始}字"
    数字文本 = re.sub(r"[\s,，]", "", str(值 or 原始))
    if 数字文本.isdigit():
        数字 = int(数字文本)
        return f"{数字}字" if 数字 < 10000 else f"{数字 / 10000:.1f}万字"
    return 原始 if 原始.endswith("字") else f"{原始}字"


def _清理正文(值: Any) -> str:
    文本 = html.unescape(str(值 or "")).replace("\r\n", "\n").replace("\r", "\n")
    文本 = re.sub(r"(?i)<br\s*/?>", "\n", 文本)
    文本 = re.sub(r"(?s)<[^>]+>", "", 文本)
    文本 = re.sub(r"\n{3,}", "\n\n", 文本)
    return 文本.strip()


async def 获取晋江详情(
    session: aiohttp.ClientSession,
    书籍编号: str,
) -> dict[str, Any]:
    data = await 请求晋江JSON(session, 晋江详情地址, {"novelId": 书籍编号})
    if str(data.get("novelId") or "").strip() != str(书籍编号):
        raise RuntimeError("晋江详情不可用")
    step = _安全整数(data.get("novelStep"), 1)
    return {
        "title": str(data.get("novelName") or f"晋江小说{书籍编号}").strip(),
        "author": str(data.get("authorName") or "未知").strip(),
        "status": "完结" if step == 2 else "连载",
        "word_count": 格式化晋江字数(
            data.get("novelSize"), data.get("novelsizeformat")
        ),
        "chapter_count": _安全整数(data.get("novelChapterCount")),
        "intro": _清理正文(data.get("novelIntro") or data.get("novelIntroShort")),
    }


def _章节可下载(章节: Mapping[str, Any]) -> bool:
    if _安全整数(章节.get("islock"), 0) != 0:
        return False
    vip = _安全整数(章节.get("isvip"), -1)
    if vip == 0:
        return True
    return _是真值(章节.get("pointfreevip")) and _安全整数(章节.get("point"), 1) <= 0


async def 获取晋江目录(
    session: aiohttp.ClientSession,
    书籍编号: str,
) -> list[dict[str, Any]]:
    data = await 请求晋江JSON(
        session,
        晋江目录地址,
        {"novelId": 书籍编号, "more": "0", "whole": "1"},
    )
    rows = data.get("chapterlist")
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, Mapping):
            continue
        chapter_id = str(item.get("chapterid") or item.get("chapterId") or "").strip()
        if not chapter_id.isdigit():
            continue
        result.append(
            {
                "id": chapter_id,
                "title": str(
                    item.get("chaptername") or item.get("chapterName") or f"第{index}章"
                ).strip(),
                "isvip": item.get("isvip"),
                "islock": item.get("islock"),
                "point": item.get("point"),
                "pointfreevip": item.get("pointfreevip"),
                "available": _章节可下载(item),
                "index": index,
            }
        )
    return result


async def 获取晋江正文(
    session: aiohttp.ClientSession,
    书籍编号: str,
    章节编号: str,
) -> str:
    data = await 请求晋江JSON(
        session,
        晋江正文地址,
        {"novelId": 书籍编号, "chapterId": 章节编号},
    )
    content = _清理正文(data.get("content"))
    if not content:
        raise RuntimeError("晋江正文为空")
    return content


async def 下载晋江正文(
    session: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    total = len(目录)
    if not total:
        return []
    concurrency = min(晋江请求并发上限, total)
    request_sem = asyncio.Semaphore(concurrency)
    results: list[dict[str, Any] | None] = [None] * total
    progress_lock = asyncio.Lock()
    completed = 0
    success = 0
    next_log = max(1, total // 晋江进度日志分段数)
    logger.info(
        "晋江小说章节进度：书籍编号=%s, 进度=0/%s, 百分比=0%%, "
        "可下载章节并发数=%s, 会话复用=开启, 重试次数=%s",
        书籍编号,
        total,
        concurrency,
        晋江请求重试次数,
    )

    async def 下载一章(index: int, chapter: dict[str, Any]) -> None:
        nonlocal completed, success, next_log
        content = ""
        for attempt in range(1, 晋江请求重试次数 + 1):
            try:
                async with request_sem:
                    content = await 获取晋江正文(session, 书籍编号, str(chapter["id"]))
                if content:
                    break
            except Exception as exc:
                logger.debug(
                    "晋江小说单章请求失败：书籍编号=%s, 序号=%s, 轮次=%s, 错误类型=%s",
                    书籍编号,
                    index + 1,
                    attempt,
                    type(exc).__name__,
                )
                if attempt < 晋江请求重试次数:
                    await asyncio.sleep(min(1.5, 0.25 * attempt))
        results[index] = {
            "id": str(chapter["id"]),
            "title": str(chapter.get("title") or f"第{index + 1}章"),
            "content": content,
            "success": bool(content),
        }
        async with progress_lock:
            completed += 1
            success += int(bool(content))
            if completed >= next_log or completed == total:
                percent = int(completed * 100 / max(1, total))
                logger.info(
                    "晋江小说章节进度：书籍编号=%s, 进度=%s/%s, 百分比=%s%%, 成功=%s, 失败=%s",
                    书籍编号,
                    completed,
                    total,
                    percent,
                    success,
                    completed - success,
                )
                while next_log <= completed:
                    next_log += max(1, total // 晋江进度日志分段数)

    await asyncio.gather(
        *(下载一章(index, chapter) for index, chapter in enumerate(目录))
    )
    output = [item for item in results if item is not None]
    if len(output) != total or any(not item.get("success") for item in output):
        raise RuntimeError("晋江小说正文不完整")
    logger.info(
        "晋江小说章节下载完成：书籍编号=%s, 成功=%s, 总数=%s",
        书籍编号,
        len(output),
        total,
    )
    return output


def _清理文件名(值: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(值 or "")).strip(" .")
    return 文本[:80] or "晋江小说"


def 生成晋江小说文件内容(
    书籍编号: str,
    详情: dict[str, Any],
    目录: list[dict[str, Any]],
    章节结果: list[dict[str, Any]],
) -> tuple[str, bytes]:
    状态 = str(详情.get("status") or "连载")
    书名 = str(详情.get("title") or f"晋江小说{书籍编号}")
    作者 = str(详情.get("author") or "未知")
    文件名 = f"[{状态}]书名：{_清理文件名(书名)} 作者：{_清理文件名(作者)}.txt"
    行列表 = [
        晋江文件声明,
        "",
        f"名称：{书名}",
        f"作者：{作者}",
        f"状态：{状态}",
        f"字数：{详情.get('word_count') or '未知'}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(目录)}",
        "",
    ]
    简介 = str(详情.get("intro") or "").strip()
    if 简介:
        行列表.extend(["简介：", 简介, ""])
    for chapter in 章节结果:
        title = str(chapter.get("title") or "章节")
        content = 去除章节正文重复标题(title, chapter.get("content"))
        if not str(content or "").strip():
            raise RuntimeError("晋江小说正文为空")
        行列表.extend([title, "", str(content).strip(), ""])
    text = "\n".join(行列表).replace("\r\n", "\n").replace("\r", "\n")
    return 文件名, text.replace("\n", "\r\n").encode("utf-8")


def 写入晋江下载缓存文件(文件名: str, 内容: bytes) -> Path:
    晋江下载缓存目录.mkdir(parents=True, exist_ok=True)
    path = 晋江下载缓存目录 / Path(_清理文件名(文件名)).name
    if path.exists():
        for index in range(1, 1000):
            candidate = 晋江下载缓存目录 / f"{path.stem}_{index}{path.suffix}"
            if not candidate.exists():
                path = candidate
                break
    path.write_bytes(内容)
    小说缓存工具.标记下载缓存正在使用(path)
    return path


def 删除晋江缓存文件(path: Any) -> None:
    if path:
        小说缓存工具.删除下载缓存文件(path)


async def 准备发送晋江文本文件(
    event: Any,
    文件名: str,
    内容: bytes,
    配置: Any,
    *,
    书名: str,
    作者: str,
) -> dict[str, Any]:
    path = 写入晋江下载缓存文件(文件名, 内容)
    if 小说网盘 is None:
        删除晋江缓存文件(path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    try:
        upload = await 小说网盘.上传小说并获取分享链接(配置, path, 文件名)
        if not upload.get("success"):
            删除晋江缓存文件(path)
            return {"sent": False, "fallback_text": "", "source_cache_path": None}
        sent = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(upload.get("share_url") or "")
        )
        if sent.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": path}
        fallback = str(sent.get("fallback_text") or "")
        if fallback:
            return {"sent": False, "fallback_text": fallback, "source_cache_path": path}
        删除晋江缓存文件(path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    except Exception as exc:
        logger.warning("晋江小说文件发送失败：错误类型=%s", type(exc).__name__)
        删除晋江缓存文件(path)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}


def 启动晋江百度后台上传并清理源文件(配置: Any, path: Any, 文件名: str) -> None:
    if not path:
        return

    async def 任务() -> None:
        备份完成 = True
        try:
            if 百度网盘 is not None:
                result = await 百度网盘.后台上传小说文件(配置, path, 文件名)
                if not isinstance(result, dict) or (
                    result.get("enabled")
                    and not (result.get("success") or result.get("skipped"))
                ):
                    备份完成 = False
                    logger.warning("晋江小说百度后台备份失败：文件=%s", 文件名)
        except Exception as exc:
            备份完成 = False
            logger.warning("晋江小说百度后台备份异常：错误类型=%s", type(exc).__name__)
        finally:
            if not 备份完成:
                小说缓存工具.更新上传任务(
                    path, "backup_pending", last_error="百度网盘后台备份未完成"
                )
            else:
                小说缓存工具.更新上传任务(path, "primary_done", last_error="")
            删除晋江缓存文件(path)

    try:
        asyncio.create_task(任务())
    except RuntimeError:
        删除晋江缓存文件(path)


async def 生成晋江下载回复流(
    event: Any,
    来源: str,
    配置: Any = None,
) -> AsyncIterator[Any]:
    书籍编号 = 提取晋江书籍编号(来源)
    if not 书籍编号:
        yield 晋江下载失败提示
        return
    stage = "详情目录"
    try:
        async with 创建晋江HTTP会话() as session:
            详情, 全部目录 = await asyncio.gather(
                获取晋江详情(session, 书籍编号),
                获取晋江目录(session, 书籍编号),
            )
            可下载目录 = [item for item in 全部目录 if item.get("available")]
            if not 全部目录:
                raise RuntimeError("晋江目录为空")
            if not 可下载目录:
                logger.info(
                    "晋江小说没有可下载章节：书籍编号=%s, 总章节=%s",
                    书籍编号,
                    len(全部目录),
                )
                yield 晋江没有可下载章节提示
                return
            logger.info(
                "晋江小说开始下载：书籍编号=%s, 书名=%s, 作者=%s, "
                "总章节=%s, 可下载章节=%s",
                书籍编号,
                详情.get("title"),
                详情.get("author"),
                len(全部目录),
                len(可下载目录),
            )
            yield "\n".join(
                [
                    f"书名：{详情.get('title') or '未知'}",
                    f"作者：{详情.get('author') or '未知'}",
                    f"状态：{详情.get('status') or '连载'}",
                    f"章节：{len(可下载目录)} 章",
                    f"字数：{详情.get('word_count') or '未知'}",
                    "",
                    "正在下载中请稍等.....",
                ]
            )
            stage = "正文"
            章节结果 = await 下载晋江正文(session, 书籍编号, 可下载目录)
        文件名, 内容 = 生成晋江小说文件内容(书籍编号, 详情, 可下载目录, 章节结果)
        发送结果 = await 准备发送晋江文本文件(
            event,
            文件名,
            内容,
            配置,
            书名=str(详情.get("title") or "未知"),
            作者=str(详情.get("author") or "未知"),
        )
        path = 发送结果.get("source_cache_path")
        if 发送结果.get("sent"):
            启动晋江百度后台上传并清理源文件(配置, path, 文件名)
            return
        fallback = str(发送结果.get("fallback_text") or "")
        if fallback:
            try:
                yield fallback
            finally:
                启动晋江百度后台上传并清理源文件(配置, path, 文件名)
            return
        yield 晋江文件发送失败提示
    except Exception as exc:
        logger.warning(
            "晋江小说下载失败：书籍编号=%s, 阶段=%s, 错误类型=%s",
            书籍编号,
            stage,
            type(exc).__name__,
        )
        yield 晋江下载失败提示


def 获取晋江小说回复流(
    event: Any,
    命令文本: str,
    配置: Any = None,
) -> AsyncIterator[Any] | None:
    来源 = 提取晋江来源(event, 命令文本)
    if 来源 is None:
        return None
    return 生成晋江下载回复流(event, 来源, 配置)


def 解析晋江搜索结果(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: Any = data.get("items")
    if not isinstance(rows, list):
        nested = data.get("data")
        rows = nested.get("items") if isinstance(nested, Mapping) else []
    result: list[dict[str, Any]] = []
    for item in rows if isinstance(rows, list) else []:
        if not isinstance(item, Mapping):
            continue
        book_id = str(
            item.get("novelid") or item.get("novelId") or item.get("book_id") or ""
        ).strip()
        title = str(
            item.get("novelname") or item.get("novelName") or item.get("title") or ""
        ).strip()
        if not book_id.isdigit() or not title:
            continue
        result.append(
            {
                "platform": "晋江",
                "book_id": book_id,
                "title": title,
                "author": str(
                    item.get("authorname")
                    or item.get("authorName")
                    or item.get("author")
                    or "未知"
                ).strip()
                or "未知",
                "url": f"https://www.jjwxc.net/onebook.php?novelid={book_id}",
                "word_count": item.get("novelsize") or item.get("novelSize") or 0,
                "heat": item.get("novelbefavoritedcount") or item.get("heat") or 0,
                "score": item.get("novelScore") or item.get("score") or 0,
            }
        )
    return result


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        async with 创建晋江HTTP会话(2) as session:
            data = await 请求晋江JSON(
                session,
                晋江搜索地址,
                {
                    "keyword": 关键词,
                    "type": "1",
                    "page": "1",
                    "searchType": "1",
                    "sortMode": "DESC",
                },
            )
        return 解析晋江搜索结果(data)[
            : max(1, min(int(需要数量 or 20), 晋江搜索数量上限))
        ]
    except Exception as exc:
        logger.debug("晋江小说搜索失败：错误类型=%s", type(exc).__name__)
        return []


生成下载回复流 = 生成晋江下载回复流
