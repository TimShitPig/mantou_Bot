"""小米浏览器小说异步详情、目录和正文下载链路。"""

from __future__ import annotations

import asyncio
import base64
import html
import json
import re
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

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

# 小米阅读网页的旧 /api/v2/search 目前只返回固定推荐项；搜索改用当前 dushu
# 网页的 onebox 接口。旧 reader.browser 接口仍保留，用于兼容用户已有的分享链接。
小米搜索地址 = "https://dushu.xiaomi.com/store/v0/lib/query/onebox"
小米新接口主机 = "dushu.xiaomi.com"
小米新接口详情地址 = "https://dushu.xiaomi.com/hs/v0/android/fiction/book"
小米新接口目录地址 = "https://dushu.xiaomi.com/store/v0/fiction/detail"
小米新接口正文链接地址 = "https://dushu.xiaomi.com/drm/v0/fiction/link"
小米详情地址 = "https://reader.browser.miui.com/api/v2/book"
小米目录地址 = "https://reader.browser.miui.com/api/v2/chapter/list"
小米正文地址 = "https://reader.browser.miui.com/api/v2/chapter/content"
小米允许域名 = {
    "reader.browser.miui.com",
    "reader.miui.com",
    "novel.browser.miui.com",
    "dushu.xiaomi.com",
    "www.dushu.xiaomi.com",
}
小米链接正则 = re.compile(
    r"https?://(?:reader\.browser\.miui\.com|reader\.miui\.com|novel\.browser\.miui\.com|dushu\.xiaomi\.com|www\.dushu\.xiaomi\.com)"
    r"[^\s<>\"']*",
    re.IGNORECASE,
)
小米卡片编号正则 = re.compile(
    r"[\"'`]?\b(?:book[_-]?id|resource[_-]?id|fiction[_-]?id|source[_-]?id|id)[\"'`]?\s*[:=]\s*[\"'`]?([0-9]{1,30})",
    re.IGNORECASE,
)
小米卡片来源编号正则 = re.compile(
    r"[\"'`]?\bsource[_-]?id[\"'`]?\s*[:=]\s*[\"'`]?([0-9]{1,30})",
    re.IGNORECASE,
)
小米请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://dushu.xiaomi.com/",
}
小米设备编号 = f"D950{uuid.uuid4().hex[:12].upper()}"
小米目录每批数量 = 150
小米目录最大批次 = 200
小米最大并发数 = 10
小米请求重试次数 = 3
小米下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
小米文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
)
小米下载失败提示 = "下载失败 请重试"
小米文件发送失败提示 = "文件发送失败，请稍后再试"


def _文本候选(值: Any, 结果: list[str], 已见: set[int], 深度: int = 0) -> None:
    if 值 is None or 深度 > 8:
        return
    if isinstance(值, str):
        结果.append(值)
        return
    if isinstance(值, dict):
        try:
            序列化 = json.dumps(值, ensure_ascii=False, default=str)
            if (
                "小米" in 序列化
                or "miui" in 序列化.lower()
                or "xiaomi" in 序列化.lower()
            ):
                结果.append(序列化)
        except Exception:
            pass
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
        "message",
        "raw_message",
        "message_obj",
        "text",
        "content",
        "data",
    ):
        try:
            _文本候选(getattr(值, 字段, None), 结果, 已见, 深度 + 1)
        except Exception:
            continue
    try:
        文本 = str(值)
    except Exception:
        文本 = ""
    if (
        "miui.com" in 文本.lower()
        or "dushu.xiaomi.com" in 文本.lower()
        or "小米" in 文本
    ):
        结果.append(文本)


def _清理来源(值: Any) -> str:
    文本 = html.unescape(str(值 or "")).replace("\\/", "/").strip()
    return 文本.rstrip("\"'`，。；;]}>）)")


def 提取小米来源(event: Any, 命令文本: Any) -> str | None:
    候选: list[str] = []
    _文本候选(命令文本, 候选, set())
    _文本候选(event, 候选, set())
    for 文本 in 候选:
        for 当前 in (文本, urllib.parse.unquote(文本)):
            匹配 = 小米链接正则.search(当前)
            if 匹配:
                return _清理来源(匹配.group(0))
    for 文本 in 候选:
        if (
            "小米" not in 文本
            and "miui" not in 文本.lower()
            and "xiaomi" not in 文本.lower()
        ):
            continue
        解码文本 = urllib.parse.unquote(文本)
        匹配 = 小米卡片来源编号正则.search(解码文本) or 小米卡片编号正则.search(
            解码文本
        )
        if 匹配:
            return 构造小米链接(匹配.group(1))
    return None


def _数字文本(值: Any) -> str:
    文本 = "" if 值 is None else str(值).strip()
    return 文本 if re.fullmatch(r"\d{1,30}", 文本) else ""


def 解析小米书籍编号(来源: Any) -> str:
    文本 = _清理来源(来源)
    try:
        解析 = urllib.parse.urlsplit(文本)
    except Exception:
        return ""
    if (解析.hostname or "").lower() not in 小米允许域名:
        return ""
    新接口 = (解析.hostname or "").lower() in {小米新接口主机, "www." + 小米新接口主机}
    查询: dict[str, list[str]] = {}
    for 部分 in (解析.query, urllib.parse.unquote(解析.fragment).lstrip("#?")):
        try:
            for 键, 值 in urllib.parse.parse_qs(部分, keep_blank_values=True).items():
                查询.setdefault(键.lower(), []).extend(值)
        except Exception:
            continue
    新接口 = 新接口 or bool(查询.get("source_id"))
    if 新接口:
        for 值 in 查询.get("source_id", []):
            编号 = _数字文本(值)
            if 编号:
                return f"dushu:{编号}"
    for 键 in ("id", "bookid", "book_id", "resourceid"):
        for 值 in 查询.get(键, []):
            编号 = _数字文本(值)
            if 编号:
                return f"dushu:{编号}" if 新接口 else 编号
    匹配 = re.search(
        r"(?:book|novel|detail)[^0-9]{0,20}(\d{1,30})", 解析.path, re.IGNORECASE
    )
    if 匹配:
        编号 = 匹配.group(1)
        return f"dushu:{编号}" if 新接口 else 编号
    匹配 = re.search(
        r"(?:^|[=&])(?:id|bookId|book_id)[=:]?\s*(\d{1,30})", 文本, re.IGNORECASE
    )
    if not 匹配:
        return ""
    编号 = 匹配.group(1)
    return f"dushu:{编号}" if 新接口 else 编号


def 构造小米链接(书籍编号: Any) -> str:
    文本 = str(书籍编号 or "").strip()
    if 文本.lower().startswith("dushu:"):
        文本 = 文本.split(":", 1)[1]
    编号 = _数字文本(文本)
    return f"https://reader.browser.miui.com/#page=book&id={编号}&source_id={编号}&source=2"


def _拆分小米书籍编号(书籍编号: Any) -> tuple[bool, str]:
    文本 = str(书籍编号 or "").strip()
    if 文本.lower().startswith("dushu:"):
        return True, 文本.split(":", 1)[1]
    return False, 文本


def _小米设备参数() -> dict[str, Any]:
    """复用 dushu 网页生成的动态设备参数；不落盘保存设备或登录状态。"""
    时间戳 = int(time.time())
    校验和 = 0
    for 字符 in f"{小米设备编号}&{时间戳}":
        校验和 = (131 * 校验和 + ord(字符)) % 65536
    return {
        "app_id": "mi_wap",
        "build": "8888",
        "channel": "",
        "device_id": 小米设备编号,
        "user_type": "2",
        "_t": 时间戳,
        "_c": 校验和,
    }


def 创建小米HTTP会话(并发数: int = 小米最大并发数) -> aiohttp.ClientSession:
    并发数 = max(1, int(并发数 or 1))
    超时 = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    连接器 = aiohttp.TCPConnector(
        limit=并发数, limit_per_host=并发数, ttl_dns_cache=300
    )
    return aiohttp.ClientSession(
        headers=小米请求头,
        timeout=超时,
        connector=连接器,
        cookies={"device_id": 小米设备编号},
    )


async def _请求JSON(
    会话: aiohttp.ClientSession, 地址: str, 参数: dict[str, Any]
) -> dict[str, Any]:
    最后异常: Exception | None = None
    for 次数 in range(小米请求重试次数):
        try:
            async with 会话.get(地址, params=参数) as 响应:
                响应.raise_for_status()
                数据 = await 响应.json(content_type=None)
            return 数据 if isinstance(数据, dict) else {}
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            json.JSONDecodeError,
        ) as 异常:
            最后异常 = 异常
            if 次数 + 1 < 小米请求重试次数:
                await asyncio.sleep(0.25 * (次数 + 1))
    raise RuntimeError("小米接口请求失败") from 最后异常


def _小米业务成功(数据: Any) -> bool:
    if not isinstance(数据, dict):
        return False
    return any(数据.get(字段) in (0, "0") for 字段 in ("status", "result", "code"))


def _安全整数(值: Any, 默认值: int = 0) -> int:
    if isinstance(值, bool):
        return 默认值
    try:
        return int(str(值).replace(",", "").strip())
    except (TypeError, ValueError):
        return 默认值


def 格式化小米字数(值: Any) -> str:
    数字 = _安全整数(值)
    return f"{数字:,}字" if 数字 > 0 else "未知"


async def 获取小米详情(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    新接口, 实际编号 = _拆分小米书籍编号(书籍编号)
    if 新接口:
        数据 = await _请求JSON(
            会话,
            f"{小米新接口详情地址}/{urllib.parse.quote(实际编号)}",
            _小米设备参数(),
        )
        if not _小米业务成功(数据):
            return {}
        信息 = 数据.get("item")
        if not isinstance(信息, dict) or not str(信息.get("title") or "").strip():
            return {}
        return {
            "title": str(信息.get("title") or "未知").strip(),
            "author": str(信息.get("authors") or "未知").strip(),
            "intro": str(信息.get("summary") or 信息.get("content") or "").strip(),
            "status": "完结" if 信息.get("finish") else "连载",
            "word_count": 信息.get("word_count") or 0,
            "chapter_count": _安全整数(信息.get("chapter_count")),
        }
    数据 = await _请求JSON(会话, f"{小米详情地址}/{urllib.parse.quote(书籍编号)}", {})
    if not _小米业务成功(数据):
        return {}
    信息 = 数据.get("data", {}).get("bookInfo", {})
    if not isinstance(信息, dict) or not str(信息.get("name") or "").strip():
        return {}
    return {
        "title": str(信息.get("name") or "未知").strip(),
        "author": str(信息.get("author") or 信息.get("authorName") or "未知").strip(),
        "intro": str(信息.get("description") or "").strip(),
        "status": str(信息.get("bookStatus") or "连载").strip(),
        "word_count": 信息.get("wordCount") or 0,
        # 当前详情接口只返回最后章节 ID（跨卷时不是章节总数），总数以目录接口为准。
        "chapter_count": _安全整数(
            (数据.get("data", {}).get("bookInfo") or {}).get("chapterCount")
            or (数据.get("data", {}).get("lastChapter") or {}).get("chapterCount")
        ),
    }


async def 获取小米目录(
    会话: aiohttp.ClientSession, 书籍编号: str
) -> list[dict[str, Any]]:
    新接口, 实际编号 = _拆分小米书籍编号(书籍编号)
    if 新接口:
        目录: list[dict[str, Any]] = []
        已见: set[str] = set()
        游标 = 0
        目标数量 = 0
        for _ in range(小米目录最大批次):
            参数 = _小米设备参数()
            参数.update({"chapter_id": 游标, "count": 小米目录每批数量})
            数据 = await _请求JSON(
                会话,
                f"{小米新接口目录地址}/{urllib.parse.quote(实际编号)}",
                参数,
            )
            if not _小米业务成功(数据):
                return []
            信息 = 数据.get("item") if isinstance(数据.get("item"), dict) else {}
            目标数量 = _安全整数(信息.get("chapter_count"), 目标数量)
            项目列表 = 信息.get("toc", [])
            if not isinstance(项目列表, list) or not 项目列表:
                break
            本批新增 = 0
            最大编号 = 游标
            for 项目 in 项目列表:
                if not isinstance(项目, dict):
                    continue
                编号 = _数字文本(项目.get("chapter_id"))
                标题 = str(项目.get("title") or "").strip()
                if not 编号 or not 标题:
                    continue
                最大编号 = max(最大编号, _安全整数(编号, 最大编号))
                if 编号 in 已见:
                    continue
                已见.add(编号)
                目录.append(
                    {
                        "id": 编号,
                        "title": 标题,
                        "free": bool(项目.get("free")),
                        "price": _安全整数(项目.get("price")),
                    }
                )
                本批新增 += 1
            if 本批新增 == 0 or (目标数量 and len(目录) >= 目标数量):
                break
            游标 = 最大编号 + 1
        return 目录 if (not 目标数量 or len(目录) == 目标数量) else []
    数据 = await _请求JSON(会话, f"{小米目录地址}/{urllib.parse.quote(书籍编号)}", {})
    if not _小米业务成功(数据):
        return []
    项目列表 = 数据.get("data", {}).get("list", [])
    if not isinstance(项目列表, list):
        return []
    目录: list[dict[str, Any]] = []
    已见: set[str] = set()
    for 项目 in 项目列表:
        if not isinstance(项目, dict):
            continue
        编号 = _数字文本(项目.get("chapterId"))
        标题 = str(项目.get("chapterName") or "").strip()
        if 编号 and 标题 and 编号 not in 已见:
            已见.add(编号)
            目录.append({"id": 编号, "title": 标题})
    return 目录


def _解析旧版正文页面(页面: bytes) -> str:
    文本 = 页面.decode("utf-8", "replace")
    匹配 = re.search(
        r"duokan_fiction_chapter(?:_\d+_\d+)?\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", 文本
    )
    if not 匹配:
        return ""
    try:
        数据 = json.loads(base64.b64decode(匹配.group(1)).decode("utf-8"))
    except Exception:
        return ""
    段落 = 数据.get("p") if isinstance(数据, dict) else None
    if not isinstance(段落, list):
        return ""
    return "\n".join(
        str(段落项).strip() for 段落项 in 段落 if str(段落项).strip()
    ).strip()


async def _解析小米正文(会话: aiohttp.ClientSession, 数据: dict[str, Any]) -> str:
    内容列表 = 数据.get("data", {}).get("contentList", [])
    if not isinstance(内容列表, list) or not 内容列表:
        return ""
    文本内容 = [
        str(项目).strip()
        for 项目 in 内容列表
        if isinstance(项目, str) and str(项目).strip()
    ]
    if not 文本内容:
        return ""
    if len(文本内容) == 1 and urllib.parse.urlsplit(文本内容[0]).scheme in {
        "http",
        "https",
    }:
        try:
            async with 会话.get(文本内容[0]) as 响应:
                响应.raise_for_status()
                页面 = await 响应.read()
            return await asyncio.to_thread(_解析旧版正文页面, 页面)
        except Exception:
            return ""
    return "\n".join(文本内容).replace("\r\n", "\n").replace("\r", "\n").strip()


async def _下载小米章节(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    章节: dict[str, Any],
    信号量: asyncio.Semaphore,
) -> str:
    编号 = str(章节.get("id") or "")
    新接口, 实际编号 = _拆分小米书籍编号(书籍编号)
    async with 信号量:
        for 次数 in range(小米请求重试次数):
            try:
                if 新接口:
                    参数 = _小米设备参数()
                    参数.update(
                        {
                            "fiction_id": 实际编号,
                            "chapter_id": 编号,
                            "format": "jsonp",
                        }
                    )
                    数据 = await _请求JSON(会话, 小米新接口正文链接地址, 参数)
                    if not _小米业务成功(数据):
                        raise RuntimeError("chapter unavailable")
                    内容地址 = str(数据.get("url") or "").strip()
                    if urllib.parse.urlsplit(内容地址).scheme not in {"http", "https"}:
                        raise RuntimeError("content url missing")
                    async with 会话.get(内容地址) as 响应:
                        响应.raise_for_status()
                        页面 = await 响应.read()
                    正文 = await asyncio.to_thread(_解析旧版正文页面, 页面)
                    if 正文:
                        return 正文
                    raise RuntimeError("empty content")
                数据 = await _请求JSON(
                    会话,
                    f"{小米正文地址}/{urllib.parse.quote(书籍编号)}",
                    {"chapterId": 编号, "volumeId": "1"},
                )
                if not _小米业务成功(数据):
                    raise RuntimeError("business failure")
                正文 = await _解析小米正文(会话, 数据)
                if 正文:
                    return 正文
                raise RuntimeError("empty content")
            except Exception as 异常:
                logger.debug(
                    "小米小说章节获取失败：章节=%s, 错误=%s", 编号, type(异常).__name__
                )
                if 次数 + 1 < 小米请求重试次数:
                    await asyncio.sleep(0.25 * (次数 + 1))
    return ""


async def 下载小米正文(
    会话: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]]
) -> list[str]:
    结果 = [""] * len(目录)
    信号量 = asyncio.Semaphore(小米最大并发数)
    已完成 = 0
    下次日志 = max(1, len(目录) // 10)
    锁 = asyncio.Lock()

    async def 下载一章(下标: int, 章节: dict[str, Any]) -> None:
        nonlocal 已完成, 下次日志
        结果[下标] = await _下载小米章节(会话, 书籍编号, 章节, 信号量)
        async with 锁:
            已完成 += 1
            if 已完成 >= 下次日志 or 已完成 == len(目录):
                logger.info(
                    "小米小说章节进度：书籍编号=%s, 进度=%s/%s, 成功=%s",
                    书籍编号,
                    已完成,
                    len(目录),
                    sum(bool(正文) for 正文 in 结果),
                )
                下次日志 += max(1, len(目录) // 10)

    await asyncio.gather(*(下载一章(下标, 章节) for 下标, 章节 in enumerate(目录)))
    return 结果


def _清理文件名(值: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(值 or "")).strip(" .")
    return 文本[:80] or "小米小说"


def 生成小米小说文件内容(
    书籍编号: str, 详情: dict[str, Any], 目录: list[dict[str, Any]], 正文列表: list[str]
) -> tuple[str, bytes]:
    状态 = str(详情.get("status") or "连载")
    书名 = _清理文件名(详情.get("title") or f"小米小说{书籍编号}")
    作者 = _清理文件名(详情.get("author") or "未知")
    文件名 = f"[{状态}]书名：{书名} 作者：{作者}.txt"
    行列表 = [
        小米文件声明,
        "",
        f"名称：{详情.get('title') or '未知'}",
        f"作者：{详情.get('author') or '未知'}",
        f"状态：{状态}",
        f"字数：{格式化小米字数(详情.get('word_count'))}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(目录)}",
        "",
    ]
    简介 = str(详情.get("intro") or "").strip()
    if 简介:
        行列表.extend(["简介：", 简介, ""])
    for 章节, 正文 in zip(目录, 正文列表):
        标题 = str(章节.get("title") or "章节")
        行列表.extend([标题, "", 去除章节正文重复标题(标题, 正文), ""])
    文本 = "\n".join(行列表).replace("\r\n", "\n").replace("\r", "\n")
    return 文件名, 文本.replace("\n", "\r\n").encode("utf-8")


def 写入小米下载缓存文件(文件名: str, 内容: bytes) -> Path:
    小米下载缓存目录.mkdir(parents=True, exist_ok=True)
    安全文件名 = Path(_清理文件名(文件名)).name
    路径 = 小米下载缓存目录 / 安全文件名
    if 路径.exists():
        for 序号 in range(1, 1000):
            候选 = 小米下载缓存目录 / f"{路径.stem}_{序号}{路径.suffix}"
            if not 候选.exists():
                路径 = 候选
                break
    路径.write_bytes(内容)
    小说缓存工具.标记下载缓存正在使用(路径)
    return 路径


def 删除小米缓存文件(路径: Any) -> None:
    if 路径:
        小说缓存工具.删除下载缓存文件(路径)


async def _准备发送文本文件(
    event: Any, 文件名: str, 内容: bytes, 配置: Any, 书名: str, 作者: str
) -> dict[str, Any]:
    路径 = 写入小米下载缓存文件(文件名, 内容)
    if 小说网盘 is None:
        删除小米缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    try:
        上传结果 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传结果.get("success"):
            删除小米缓存文件(路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None}
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(上传结果.get("share_url") or "")
        )
        if 完成结果.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": 路径}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 路径}
        删除小米缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    except Exception as 异常:
        logger.warning("小米小说文件发送失败：错误=%s", type(异常).__name__)
        删除小米缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}


def 启动小米后台上传并清理源文件(配置: Any, 路径: Any, 文件名: str) -> None:
    if not 路径:
        return

    async def 任务() -> None:
        备份完成 = True
        try:
            if 百度网盘 is not None:
                结果 = await 百度网盘.后台上传小说文件(配置, 路径, 文件名)
                if not isinstance(结果, dict) or (
                    结果.get("enabled")
                    and not (结果.get("success") or 结果.get("skipped"))
                ):
                    备份完成 = False
                    logger.warning(
                        "小米小说后台备份失败：文件=%s, 错误=UploadFailed", 文件名
                    )
        except Exception as 异常:
            备份完成 = False
            logger.warning("小米小说后台备份异常：错误=%s", type(异常).__name__)
        finally:
            if not 备份完成:
                小说缓存工具.更新上传任务(
                    路径,
                    "backup_pending",
                    last_error="百度网盘后台备份未完成",
                )
            else:
                小说缓存工具.更新上传任务(路径, "primary_done", last_error="")
            删除小米缓存文件(路径)

    try:
        asyncio.create_task(任务())
    except RuntimeError:
        删除小米缓存文件(路径)


async def 生成小米下载回复流(
    event: Any, 来源: str, 配置: Any = None
) -> AsyncIterator[Any]:
    stage = "解析"
    try:
        书籍编号 = 解析小米书籍编号(来源)
        if not 书籍编号:
            yield 小米下载失败提示
            return
        async with 创建小米HTTP会话() as 会话:
            stage = "详情目录"
            详情, 目录 = await asyncio.gather(
                获取小米详情(会话, 书籍编号), 获取小米目录(会话, 书籍编号)
            )
            if not 详情 or not 目录:
                yield 小米下载失败提示
                return
            logger.info("小米小说开始下载：书籍编号=%s, 章节数=%s", 书籍编号, len(目录))
            yield "\n".join(
                [
                    f"书名：{详情.get('title') or '未知'}",
                    f"作者：{详情.get('author') or '未知'}",
                    f"状态：{详情.get('status') or '连载'}",
                    f"章节：{len(目录)} 章",
                    f"字数：{格式化小米字数(详情.get('word_count'))}",
                    "",
                    "正在下载中请稍等.....",
                ]
            )
            stage = "正文"
            正文列表 = await 下载小米正文(会话, 书籍编号, 目录)
        if len(正文列表) != len(目录) or any(not 正文 for 正文 in 正文列表):
            logger.warning(
                "小米小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s",
                书籍编号,
                sum(bool(x) for x in 正文列表),
                len(目录),
            )
            yield 小米下载失败提示
            return
        文件名, 内容 = 生成小米小说文件内容(书籍编号, 详情, 目录, 正文列表)
        发送结果 = await _准备发送文本文件(
            event,
            文件名,
            内容,
            配置,
            str(详情.get("title") or "未知"),
            str(详情.get("author") or "未知"),
        )
        路径 = 发送结果.get("source_cache_path")
        if 发送结果.get("sent"):
            启动小米后台上传并清理源文件(配置, 路径, 文件名)
            return
        降级文本 = str(发送结果.get("fallback_text") or "")
        if 降级文本:
            try:
                yield 降级文本
            finally:
                启动小米后台上传并清理源文件(配置, 路径, 文件名)
            return
        yield 小米文件发送失败提示
    except Exception as 异常:
        logger.warning("小米小说下载失败：阶段=%s, 错误=%s", stage, type(异常).__name__)
        yield 小米下载失败提示


def 获取小米小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[Any] | None:
    来源 = 提取小米来源(event, 命令文本)
    if 来源 is None:
        return None
    return 生成小米下载回复流(event, 来源, 配置)


def _小米搜索结果相关(项目: dict[str, Any], 关键词: str) -> bool:
    查询词 = [
        re.sub(r"\s+", "", 词).casefold()
        for 词 in re.split(r"[\s,，;；/|]+", str(关键词 or ""))
        if re.sub(r"\s+", "", 词)
    ]
    if not 查询词:
        return False
    文本 = str(项目.get("title") or "") + _小米搜索作者(项目)
    文本 = re.sub(r"\s+", "", 文本).casefold()
    return all(词 in 文本 for 词 in 查询词)


def _小米搜索作者(项目: dict[str, Any]) -> str:
    作者 = 项目.get("author") or 项目.get("authorName")
    if 作者:
        return str(作者).strip()
    角色 = 项目.get("role")
    if isinstance(角色, list):
        for 项 in 角色:
            if (
                isinstance(项, (list, tuple))
                and len(项) >= 2
                and str(项[0]).strip() == "作者"
            ):
                return str(项[1]).strip()
    return "未知"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        async with 创建小米HTTP会话(2) as 会话:
            数量 = max(1, min(50, int(需要数量 or 20)))
            数据 = await _请求JSON(
                会话,
                小米搜索地址,
                {"s": 关键词, "start": 0, "count": 数量, "source": "2,5"},
            )
        项目列表 = 数据.get("items", []) if isinstance(数据, dict) else []
        结果: list[dict[str, Any]] = []
        for 项目 in 项目列表 if isinstance(项目列表, list) else []:
            if not isinstance(项目, dict):
                continue
            if not _小米搜索结果相关(项目, 关键词):
                continue
            # onebox 的 id 是聚合结果 ID，正文链路必须使用 source_id。
            编号 = _数字文本(项目.get("source_id") or 项目.get("fiction_id"))
            标题 = str(项目.get("title") or "").strip()
            if not 编号 or not 标题:
                continue
            结果.append(
                {
                    "book_id": 编号,
                    "title": 标题,
                    "author": _小米搜索作者(项目),
                    "intro": str(
                        项目.get("intro") or 项目.get("description") or ""
                    ).strip(),
                    "url": 构造小米链接(编号),
                    "score": 项目.get("rate") or 项目.get("score") or 0,
                    "heat": _安全整数(项目.get("click") or 项目.get("hot")),
                    "word_count": 项目.get("word_count") or 0,
                }
            )
        return 结果[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as 异常:
        logger.debug("小米小说搜索失败：错误=%s", type(异常).__name__)
        return []
