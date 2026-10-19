"""百度小说异步详情、目录和正文下载链路。"""

from __future__ import annotations

import asyncio
import html
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except Exception:
    AES = None
    unpad = None

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

百度搜索地址 = "https://appyd.baidu.com/nabook/search/newbookseo"
百度详情地址 = "https://appyd.baidu.com/nabook/detail/wap"
百度目录地址 = "https://appyd.baidu.com/nabook/chapter"
百度正文地址 = "https://appyd.baidu.com/nabook/content"
百度旧版详情地址 = "https://novelapi.baidu.com/boxnovel/cors"
百度旧版目录地址 = "https://novelapi.baidu.com/searchbox"
百度出版详情地址 = "https://appyd.baidu.com/nabook/detail/wap"
百度出版图书地址 = "https://appyd.baidu.com/nabook/book"
百度出版目录地址 = "https://appyd.baidu.com/nabook/chapter"
百度出版正文地址 = "https://appyd.baidu.com/mobile/getbdjson"
百度允许域名 = {"mr.baidu.com", "boxnovel.baidu.com", "novel.baidu.com", "yd.baidu.com"}
百度详情页路径 = "/boxnovel/yuedu/wapdetail"
百度详情页路径集合 = {"/boxnovel/yuedu/wapdetail", "/boxnovel/yuedu/wapcontent"}
百度详情页最大响应字节 = 1024 * 1024
百度链接正则 = re.compile(
    r"https?://(?:mr\.baidu\.com|boxnovel\.baidu\.com|novel\.baidu\.com|yd\.baidu\.com)"
    r"(?::[0-9]{1,5})?(?=[/?#\s<>\"']|$)[^\s<>\"']*",
    re.IGNORECASE,
)
百度卡片编号正则 = re.compile(
    r"[\"'`]?\b(?:gid|book[_-]?id|bookgid|resource[_-]?id)[\"'`]?\s*[:=]\s*[\"'`]?([0-9]{5,30})",
    re.IGNORECASE,
)
百度请求头 = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; V1838T Build/QP1A.190711.020; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
        "Chrome/91.0.4472.114 Mobile Safari/537.36 baiduboxapp/12.8.0.10"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://boxnovel.baidu.com/",
}
百度固定UID = "juB18g8oHi_-aH88lPHl8g8nHi_ju2avgi25ugi3Sf8R9WMxpiWmuYMaA"
百度固定UA = "_a-qiyuuvigyNE64I5me6NN0v8oZu-I4_C2Hiyat2iqlC"
百度AES密钥 = b"D0CD8B760CE07BC3"
百度AES向量 = b"2011121211143000"
百度最大并发数 = 32
百度每秒请求上限 = 200
百度请求重试次数 = 3
百度小说缓存目录 = 文件缓存工具.小说缓存目录
百度文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
)
百度下载失败提示 = "下载失败 请重试"
百度文件发送失败提示 = "文件发送失败，请稍后再试"


class _百度访问错误(RuntimeError):
    """远端明确拒绝时停止本书任务，避免重放所有剩余章节。"""


class _百度请求节流器:
    def __init__(self) -> None:
        self.锁 = asyncio.Lock()
        self.下次 = 0.0

    async def 等待(self) -> None:
        async with self.锁:
            循环 = asyncio.get_running_loop()
            等待秒 = self.下次 - 循环.time()
            if 等待秒 > 0:
                await asyncio.sleep(等待秒)
            self.下次 = 循环.time() + 1 / 百度每秒请求上限


def _百度网页参数(数据: dict[str, Any]) -> dict[str, str]:
    return {"data": json.dumps(数据, ensure_ascii=False, separators=(",", ":")), "fr": "9"}


def _是百度官方地址(地址: Any) -> bool:
    if not isinstance(地址, str):
        return False
    try:
        解析 = urllib.parse.urlsplit(地址)
        主机 = (解析.hostname or "").lower()
        return 解析.scheme in {"http", "https"} and not 解析.username and not 解析.password and any(
            主机 == 后缀 or 主机.endswith("." + 后缀)
            for 后缀 in ("baidu.com", "bcebos.com", "baidubce.com", "bdstatic.com", "bdimg.com")
        )
    except ValueError:
        return False


def _检查百度章节权限(数据: Any) -> None:
    if not isinstance(数据, dict):
        return
    if any(str(数据.get(键) or "").lower() in {"1", "true"} for 键 in (
        "need_login", "needLogin", "login_required", "need_pay", "needPay", "need_purchase", "purchase_required",
    )):
        raise _百度访问错误("chapter_access_required")
    状态 = 数据.get("status") if isinstance(数据.get("status"), dict) else {}
    消息 = " ".join(str(值 or "") for 值 in (状态.get("msg"), 数据.get("message"), 数据.get("msg"), 数据.get("error_msg")))
    if re.search(r"login|log\s*in|sign\s*in|登录|登陆|purchase|payment.required|pay.required|购买|付费", 消息, re.IGNORECASE):
        raise _百度访问错误("chapter_access_required")
    if "free" in 数据 and str(数据["free"]) == "0" and str(数据.get("purchase") or "0") != "1":
        raise _百度访问错误("chapter_purchase_required")
    if "public_status" in 数据 and str(数据["public_status"]) != "1":
        raise _百度访问错误("chapter_unavailable")


def _校验百度目录(目录: list[dict[str, Any]]) -> None:
    if not 目录:
        raise RuntimeError("empty_catalog")
    已见 = set()
    for 章节 in 目录:
        if not isinstance(章节, dict):
            raise RuntimeError("invalid_catalog")
        编号 = str(章节.get("id") or "").strip()
        if not 编号 or 编号 in 已见 or not str(章节.get("title") or "").strip():
            raise RuntimeError("invalid_catalog_identity")
        已见.add(编号)


def _文本候选(值: Any, 结果: list[str], 已见: set[int], 深度: int = 0) -> None:
    if 值 is None or 深度 > 8:
        return
    if isinstance(值, str):
        结果.append(值)
        return
    if isinstance(值, dict):
        try:
            序列化 = json.dumps(值, ensure_ascii=False, default=str)
            if "百度" in 序列化 or "baidu" in 序列化.lower():
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
    if "baidu.com" in 文本.lower() or "百度" in 文本:
        结果.append(文本)


def _清理来源(值: Any) -> str:
    文本 = html.unescape(str(值 or "")).replace("\\/", "/").strip()
    return 文本.rstrip("\"'`，。；;]}>）)")


def 提取百度来源(event: Any, 命令文本: Any) -> str | None:
    候选: list[str] = []
    _文本候选(命令文本, 候选, set())
    _文本候选(event, 候选, set())
    for 文本 in 候选:
        解码文本 = html.unescape(文本).replace("\\/", "/")
        # 每次解码后立即匹配，避免继续解码把 data 查询中的 JSON 引号展开截断。
        for _ in range(3):
            for 匹配 in 百度链接正则.finditer(解码文本):
                return _清理来源(匹配.group(0))
            新文本 = html.unescape(_安全解码(解码文本)).replace("\\/", "/")
            if 新文本 == 解码文本:
                break
            解码文本 = 新文本
    for 文本 in 候选:
        if "百度" not in 文本 and "baidu" not in 文本.lower():
            continue
        匹配 = 百度卡片编号正则.search(_安全解码(文本))
        if 匹配:
            return 构造百度链接(匹配.group(1))
    return None


def _安全解码(文本: str) -> str:
    try:
        return urllib.parse.unquote(文本)
    except Exception:
        return 文本


def _解析百度文档编号(来源: Any) -> str:
    文本 = _清理来源(来源)
    if _是百度文档编号(文本):
        return 文本.lower()
    try:
        解析 = urllib.parse.urlsplit(文本)
        if (解析.hostname or "").lower() not in 百度允许域名:
            return ""
        查询 = urllib.parse.parse_qs(解析.query, keep_blank_values=True)
    except (TypeError, ValueError):
        return ""
    for 值 in 查询.get("doc_id", []):
        if _是百度文档编号(值):
            return str(值).lower()
    for 值 in 查询.get("data", []):
        for _ in range(3):
            try:
                数据 = json.loads(值)
            except (TypeError, ValueError):
                数据 = None
            if isinstance(数据, dict) and _是百度文档编号(数据.get("doc_id")):
                return str(数据["doc_id"]).lower()
            新值 = urllib.parse.unquote(str(值))
            if 新值 == 值:
                break
            值 = 新值
    return ""


def _是百度文档编号(值: Any) -> bool:
    文本 = str(值 or "").strip()
    return bool(re.fullmatch(r"[0-9a-fA-F]{16,64}", 文本)) and not bool(_数字文本(文本))


def _数字文本(值: Any) -> str:
    文本 = str(值 or "").strip()
    return 文本 if re.fullmatch(r"\d{5,30}", 文本) else ""


def 解析百度书籍编号(来源: Any) -> str:
    文本 = _清理来源(来源)
    文档编号 = _解析百度文档编号(文本)
    if 文档编号:
        return 文档编号
    try:
        解析 = urllib.parse.urlsplit(文本)
    except Exception:
        return ""
    if (解析.hostname or "").lower() not in 百度允许域名:
        return ""
    查询: dict[str, list[str]] = {}
    for 部分 in (解析.query, urllib.parse.unquote(解析.fragment).lstrip("#?")):
        try:
            for 键, 值 in urllib.parse.parse_qs(部分, keep_blank_values=True).items():
                查询.setdefault(键.lower(), []).extend(值)
        except Exception:
            continue
    for 键 in ("gid", "bookid", "book_id", "bookgid", "novel_book_id"):
        for 值 in 查询.get(键, []):
            书籍编号 = _数字文本(值)
            if 书籍编号:
                return 书籍编号
    for 值列表 in 查询.get("data", []):
        当前 = 值列表
        for _ in range(2):
            当前 = urllib.parse.unquote_plus(str(当前))
        try:
            数据 = json.loads(当前)
        except Exception:
            数据 = None
        if isinstance(数据, dict):
            for 键 in (
                "gid",
                "bookid",
                "book_id",
                "bookGid",
                "novel_book_id",
                "novelBookId",
            ):
                书籍编号 = _数字文本(数据.get(键))
                if 书籍编号:
                    return 书籍编号
    路径匹配 = re.search(
        r"(?:book|novel|detail|reader)[^0-9]{0,20}(\d{5,30})", 解析.path, re.IGNORECASE
    )
    if 路径匹配:
        return 路径匹配.group(1)
    原文匹配 = re.search(
        r"(?:gid|bookid|book_id)%?3?d%?22?%?3a?%?22?(\d{5,30})", 文本, re.IGNORECASE
    )
    return 原文匹配.group(1) if 原文匹配 else ""


def 构造百度链接(书籍编号: Any) -> str:
    编号 = str(书籍编号 or "").strip().lower()
    if _是百度文档编号(编号):
        查询 = urllib.parse.urlencode({"data": json.dumps({"doc_id": 编号}, separators=(",", ":"))})
        return "https://boxnovel.baidu.com/boxnovel/yuedu/wapdetail?" + 查询
    return f"https://boxnovel.baidu.com/boxnovel/reader?gid={编号}" if _数字文本(编号) else ""


def 创建百度HTTP会话(并发数: int = 百度最大并发数) -> aiohttp.ClientSession:
    并发数 = max(1, int(并发数 or 1))
    超时 = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    连接器 = aiohttp.TCPConnector(
        limit=并发数, limit_per_host=并发数, ttl_dns_cache=300
    )
    return aiohttp.ClientSession(headers=百度请求头, timeout=超时, connector=连接器)


async def _请求JSON(
    会话: aiohttp.ClientSession, 地址: str, 参数: dict[str, Any], *,
    节流器: _百度请求节流器 | None = None, 重试: bool = True,
) -> dict[str, Any]:
    最后异常: Exception | None = None
    次数上限 = 百度请求重试次数 if 重试 else 1
    for 次数 in range(次数上限):
        try:
            if 节流器 is not None:
                await 节流器.等待()
            async with 会话.get(地址, params=参数, allow_redirects=False) as 响应:
                if 响应.status in {403, 429}:
                    raise _百度访问错误("http_blocked")
                响应.raise_for_status()
                数据 = await 响应.json(content_type=None)
            if not isinstance(数据, dict):
                raise ValueError("invalid_json_object")
            return 数据
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as 异常:
            最后异常 = 异常
            if 次数 + 1 < 次数上限:
                await asyncio.sleep(0.25 * (次数 + 1))
    raise RuntimeError("百度接口请求失败") from 最后异常


async def _解析短链(会话: aiohttp.ClientSession, 来源: str) -> str:
    当前 = 来源
    for _ in range(5):
        try:
            if (urllib.parse.urlsplit(当前).hostname or "").lower() not in 百度允许域名:
                return ""
            async with 会话.get(当前, allow_redirects=False) as 响应:
                位置 = 响应.headers.get("Location") or ""
                if 位置:
                    当前 = urllib.parse.urljoin(当前, 位置)
                    编号 = _解析百度文档编号(当前) or 解析百度书籍编号(当前)
                    if 编号:
                        return 编号
                    continue
                if 响应.status != 200:
                    return ""
                页面 = await 响应.read()
                if len(页面) > 百度详情页最大响应字节:
                    return ""
                return _从百度详情页提取编号(页面.decode("utf-8", "replace"))
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return ""
    return ""


def _从百度详情页提取编号(页面: str) -> str:
    文本 = html.unescape(str(页面 or ""))
    匹配 = re.search(r'["\']doc_id["\']\s*:\s*["\']([0-9a-fA-F]{16,64})["\']', 文本)
    if 匹配 and _是百度文档编号(匹配.group(1)):
        return 匹配.group(1).lower()
    for 字段 in ("novel_book_id", "novelBookId", "book_id", "gid"):
        匹配 = re.search(rf'["\']{re.escape(字段)}["\']\s*:\s*["\']?(\d{{5,30}})', 文本)
        if 匹配:
            return 匹配.group(1)
    return ""


async def _解析百度详情页编号(会话: aiohttp.ClientSession, 来源: str) -> str:
    try:
        解析 = urllib.parse.urlsplit(来源)
        主机 = (解析.hostname or "").lower()
        路径 = (解析.path or "").rstrip("/").lower()
        if (
            主机 not in {"boxnovel.baidu.com", "novel.baidu.com", "yd.baidu.com"}
            or 路径 not in 百度详情页路径集合
        ):
            return ""
    except (TypeError, ValueError):
        return ""
    for 次数 in range(百度请求重试次数):
        try:
            async with 会话.get(来源) as 响应:
                响应.raise_for_status()
                if 响应.content_length and 响应.content_length > 百度详情页最大响应字节:
                    return ""
                页面 = await 响应.content.read(百度详情页最大响应字节 + 1)
            if len(页面) > 百度详情页最大响应字节:
                return ""
            书籍编号 = _从百度详情页提取编号(页面.decode("utf-8", "replace"))
            if 书籍编号:
                return 书籍编号
        except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeError):
            pass
        if 次数 + 1 < 百度请求重试次数:
            await asyncio.sleep(0.25 * (次数 + 1))
    logger.debug("百度小说分享页解析失败：阶段=detail_page,错误=ParseFailed")
    return ""


async def _异步解析书籍编号(来源: str, 会话: aiohttp.ClientSession) -> str:
    编号 = _解析百度文档编号(来源) or 解析百度书籍编号(来源)
    if 编号:
        return 编号
    try:
        主机 = (urllib.parse.urlsplit(来源).hostname or "").lower()
    except ValueError:
        return ""
    if 主机 == "mr.baidu.com":
        return await _解析短链(会话, 来源)
    return await _解析百度详情页编号(会话, 来源)


def _百度成功(数据: Any) -> bool:
    return isinstance(数据, dict) and str(数据.get("errno", "0")) == "0"


def _安全整数(值: Any, 默认值: int = 0) -> int:
    if isinstance(值, bool):
        return 默认值
    try:
        return int(str(值).replace(",", "").strip())
    except (TypeError, ValueError):
        return 默认值


def 格式化百度字数(值: Any) -> str:
    文本 = re.sub(r"[\s,，]", "", str(值 or ""))
    if re.fullmatch(r"\d+(?:\.\d+)?(?:万|亿)字?", 文本):
        # 上游已给展示单位时保留原精度，不重复除以一万。
        数值文本 = re.match(r"\d+(?:\.\d+)?", 文本).group()
        if float(数值文本) <= 0:
            return "未知"
        return 文本 if 文本.endswith("字") else f"{文本}字"
    if 文本.endswith("字"):
        文本 = 文本[:-1]
    数字 = _安全整数(文本)
    if 数字 <= 0:
        return "未知"
    if 数字 >= 10000:
        万字 = f"{数字 / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{万字}万字"
    return f"{数字}字"


def _取详情字段(数据: dict[str, Any]) -> dict[str, Any]:
    节点 = 数据.get("novel", {}).get("detail", {}).get("data", {})
    if not isinstance(节点, dict):
        return {}
    return {
        "title": str(节点.get("title") or "未知").strip(),
        "author": str(节点.get("author") or "未知").strip(),
        "intro": str(节点.get("summary") or "").strip(),
        "status": str(节点.get("status") or "连载").strip(),
        "word_count": 节点.get("words_num") or 节点.get("wordCount") or "",
        "chapter_count": _安全整数(节点.get("chapter_num")),
    }


async def 获取百度详情(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    if _是百度文档编号(书籍编号):
        数据 = await _请求JSON(会话, 百度详情地址, _百度网页参数({"doc_id": 书籍编号}))
        if not _百度出版接口成功(数据):
            return {}
        节点 = 数据.get("data")
        if not isinstance(节点, dict) or str(节点.get("doc_id") or "").lower() != str(书籍编号).lower():
            return {}
        详情 = _取百度出版详情字段(数据)
        if 详情:
            详情["doc_id"] = 书籍编号
        return 详情
    数据 = await _请求JSON(会话, 百度旧版详情地址, {
        "osname": "bdboxnovelsdk", "action": "novel", "type": "detail", "tojsondata": "1",
        "data": json.dumps({"gid": 书籍编号, "frombox": True}, separators=(",", ":")),
    })
    if not _百度成功(数据):
        return {}
    详情 = _取详情字段(数据)
    节点 = 数据.get("novel", {}).get("detail", {}).get("data", {})
    if isinstance(节点, dict) and _是百度文档编号(节点.get("doc_id")):
        return await 获取百度详情(会话, str(节点["doc_id"]).lower())
    return 详情


async def _补查百度文档编号(会话: aiohttp.ClientSession, 旧编号: str, 详情: dict[str, Any]) -> str:
    标题 = str(详情.get("title") or "").strip()
    if not 标题 or 标题 == "未知":
        return ""
    for 起点 in (0, 10, 20):
        数据 = await _请求JSON(会话, 百度搜索地址, _百度网页参数({"pn": 起点, "rn": 10, "query": 标题}))
        if not _百度出版接口成功(数据):
            return ""
        项目列表 = (数据.get("data") or {}).get("doc_info")
        if not isinstance(项目列表, list):
            return ""
        for 项目 in 项目列表:
            if isinstance(项目, dict) and str(项目.get("novel_book_id") or "") == 旧编号 and _是百度文档编号(项目.get("doc_id")):
                return str(项目["doc_id"]).lower()
        if len(项目列表) < 10:
            break
    return ""


async def 获取百度目录(会话: aiohttp.ClientSession, 书籍编号: str) -> list[dict[str, Any]]:
    if _是百度文档编号(书籍编号):
        数据 = await _请求JSON(会话, 百度目录地址, _百度网页参数({"doc_id": 书籍编号}))
        if not _百度出版接口成功(数据):
            return []
        项目列表 = (数据.get("data") or {}).get("items")
    else:
        数据 = await _请求JSON(会话, 百度旧版目录地址, {
            "action": "novel", "type": "chapter",
            "data": json.dumps({"gid": 书籍编号}, separators=(",", ":")),
        })
        if not _百度成功(数据):
            return []
        项目列表 = 数据.get("data", {}).get("novel", {}).get("chapter", {}).get("dataset", {}).get("items")
    if not isinstance(项目列表, list):
        return []
    目录 = []
    已见 = set()
    for 项目 in 项目列表:
        if not isinstance(项目, dict):
            raise RuntimeError("invalid_catalog_item")
        编号 = str(项目.get("cid") or "").strip()
        标题 = str(项目.get("title") or "").strip()
        if not 编号 or not 标题 or 编号 in 已见:
            raise RuntimeError("invalid_catalog_identity")
        已见.add(编号)
        目录.append({**项目, "id": 编号, "title": 标题})
    return 目录


def _百度出版接口成功(数据: Any) -> bool:
    状态 = 数据.get("status") if isinstance(数据, dict) else None
    return isinstance(状态, dict) and not isinstance(状态.get("code"), bool) and str(状态.get("code")) == "0"


def _取百度出版详情字段(数据: dict[str, Any]) -> dict[str, Any]:
    节点 = 数据.get("data")
    if not isinstance(节点, dict) or not str(节点.get("title") or "").strip():
        return {}
    return {
        "book_id": str(节点.get("novel_book_id") or 节点.get("gid") or "").strip(),
        "doc_id": str(节点.get("doc_id") or "").strip().lower(),
        "title": str(节点["title"]).strip(),
        "author": str(节点.get("author") or "未知").strip(),
        "intro": str(节点.get("description") or 节点.get("summary") or "").strip(),
        "status": str(节点.get("status") or "连载").strip(),
        "word_count": 节点.get("words_num") or 节点.get("wordCount") or "",
        "chapter_count": _安全整数(节点.get("chapter_num")),
        "is_yuedu_source": str(节点.get("is_yuedu_source") or "0").lower() in {"1", "true"},
    }




def _取百度出版图书数据(数据: dict[str, Any]) -> dict[str, Any]:
    if not _百度出版接口成功(数据):
        return {}
    节点 = 数据.get("data")
    return 节点 if isinstance(节点, dict) else {}


async def 获取百度出版图书(
    会话: aiohttp.ClientSession, 文档编号: str
) -> dict[str, Any]:
    数据 = await _请求JSON(
        会话,
        百度出版图书地址,
        {"na_uncheck": "1", "opid": "wk_na", "doc_id": 文档编号},
    )
    return _取百度出版图书数据(数据)


def _百度出版坐标(值: Any) -> tuple[int, int] | None:
    if not isinstance(值, str) or not re.fullmatch(r"[1-9][0-9]*-[1-9][0-9]*", 值):
        return None
    页码, 段落 = 值.split("-", 1)
    return int(页码), int(段落)

def _百度出版正整数(值: Any) -> int | None:
    if isinstance(值, bool) or not re.fullmatch(r"[1-9][0-9]*", str(值)):
        return None
    return int(值)

def _百度出版图书匹配(图书数据: Any, 文档编号: str) -> bool:
    if not isinstance(图书数据, dict):
        return False
    详情 = 图书数据.get("docInfo")
    图书 = 图书数据.get("bdjson")
    return (
        isinstance(详情, dict)
        and isinstance(文档编号, str)
        and bool(文档编号)
        and 详情.get("doc_id") == 文档编号
        and isinstance(详情.get("version"), str)
        and bool(详情["version"].strip())
        and isinstance(图书, dict)
        and 图书.get("exist") is True
    )

def _百度出版标题匹配(节点: Any, 标题: str) -> bool:
    return (
        isinstance(节点, dict)
        and 节点.get("t") in {"h1", "h2", "h3", "h4", "h5", "h6"}
        and bool(_百度出版标题键(标题))
        and _百度出版标题键(_百度出版节点文本(节点)) == _百度出版标题键(标题)
    )


def _从百度出版图书提取目录(
    图书数据: dict[str, Any], 文档编号: str = ""
) -> list[dict[str, Any]]:
    """保留真实目录次序及边界；缺标题、坏 map 不伪造为可读正文。

    缺少完整分片元数据时返回空目录。单章 map 不可用或越过免费边界
    时仍保留该真实目录项，使整本下载的缺章检查明确失败。
    """
    if not isinstance(图书数据, dict):
        return []
    详情 = 图书数据.get("docInfo")
    图书 = 图书数据.get("bdjson")
    if not isinstance(详情, dict) or not isinstance(图书, dict):
        return []
    实际编号 = 详情.get("doc_id")
    if not isinstance(实际编号, str) or not 实际编号:
        return []
    if not _百度出版图书匹配(图书数据, 文档编号 or 实际编号):
        return []
    页数 = _百度出版正整数(图书.get("page"))
    原始段数 = 图书.get("para_of_page")
    if not 页数 or not isinstance(原始段数, list) or len(原始段数) != 页数:
        return []
    每页段数 = [_百度出版正整数(值) for 值 in 原始段数]
    if any(值 is None for 值 in 每页段数):
        return []
    免费信息 = 图书.get("freeInfo")
    免费边界文本 = 免费信息.get("free") if isinstance(免费信息, dict) else None
    免费边界 = _百度出版坐标(免费边界文本)
    if 免费边界 is None:
        return []
    项目列表 = 图书.get("catalogs")
    if not isinstance(项目列表, list) or not 项目列表:
        return []
    索引: dict[str, dict[str, Any]] = {}
    for 项目 in 项目列表:
        if not isinstance(项目, dict):
            return []
        编号 = 项目.get("href")
        坐标 = _百度出版坐标(编号)
        if 坐标 is None or 编号 in 索引 or 坐标[0] > 页数:
            return []
        if 坐标[1] > 每页段数[坐标[0] - 1]:
            return []
        索引[编号] = 项目
    目录: list[dict[str, Any]] = []
    for 编号, 项目 in 索引.items():
        坐标 = _百度出版坐标(编号)
        标题 = 项目.get("title")
        标题 = 标题.strip() if isinstance(标题, str) else ""
        范围 = 项目.get("map")
        范围 = 范围 if isinstance(范围, str) else ""
        分隔范围 = 范围.split(",")
        结束编号 = 分隔范围[1] if len(分隔范围) == 2 else ""
        下一项目 = 索引.get(结束编号)
        下一标题 = 下一项目.get("title") if isinstance(下一项目, dict) else None
        下一标题 = 下一标题.strip() if isinstance(下一标题, str) else ""
        目录.append(
            {
                "id": 编号,
                "title": 标题,
                "source_page": str(坐标[0]),
                "source_cid": 编号,
                "source_map": 范围,
                "source_para_count": 每页段数[坐标[0] - 1],
                "source_free_boundary": 免费边界文本,
                "source_next_title": 下一标题,
                "source_doc_id": 实际编号,
                "source_version": 详情["version"],
            }
        )
    return 目录


def _获取百度出版版本(图书数据: dict[str, Any]) -> str:
    详情 = 图书数据.get("docInfo", {})
    return str(详情.get("version") or "").strip() if isinstance(详情, dict) else ""




def _百度出版节点文本(值: Any) -> str:
    if isinstance(值, str):
        # BDJSON 的 c 已是文本；沿用官方批量参考实现，不再次作 HTML 解码。
        return 值
    if isinstance(值, (list, tuple)):
        return "".join(_百度出版节点文本(子值) for 子值 in 值)
    if isinstance(值, dict):
        return _百度出版节点文本(值.get("c", 值.get("text", "")))
    return ""


def _百度出版标题键(值: Any) -> str:
    return re.sub(r"\s+", "", html.unescape(值)) if isinstance(值, str) else ""


def _拆分百度出版页面正文(
    内容: Any, 页面目录: list[dict[str, Any]]
) -> dict[str, str]:
    """只返回完整、可读、与目录边界一致的同分片章节。

    结束坐标和免费边界均为排他边界。跨分片范围、缺少真实标题、
    尾章 0 段占位或无元数据的旧缓存不会被推测补齐。
    """
    if (
        not isinstance(内容, dict)
        or 内容.get("t") != "div"
        or not isinstance(内容.get("c"), list)
        or not isinstance(页面目录, list)
        or not 页面目录
    ):
        return {}
    页码 = _百度出版正整数(内容.get("blockNum"))
    if 页码 is None:
        return {}
    区块列表 = 内容["c"]
    结果: dict[str, str] = {}
    已见: set[str] = set()
    for 章节 in 页面目录:
        if not isinstance(章节, dict):
            return {}
        编号 = 章节.get("id")
        if not isinstance(编号, str) or 编号 in 已见:
            return {}
        已见.add(编号)
        标题 = 章节.get("title")
        if not isinstance(标题, str) or not 标题.strip():
            continue
        起点 = _百度出版坐标(编号)
        范围 = 章节.get("source_map")
        范围项 = 范围.split(",") if isinstance(范围, str) else []
        if len(范围项) != 2:
            continue
        范围起点 = _百度出版坐标(范围项[0])
        终点 = _百度出版坐标(范围项[1])
        免费边界 = _百度出版坐标(章节.get("source_free_boundary"))
        段数 = _百度出版正整数(章节.get("source_para_count"))
        下一标题 = 章节.get("source_next_title")
        if (
            起点 is None
            or 范围起点 != 起点
            or 终点 is None
            or 免费边界 is None
            or not isinstance(下一标题, str)
            or not 下一标题.strip()
            or 段数 != len(区块列表)
            or 起点[0] != 页码
            or 终点[0] != 页码
            or str(章节.get("source_page")) != str(页码)
            or 终点 <= 起点
            or 终点[1] > 段数
            or 起点 >= 免费边界
            or (页码, 终点[1] - 1) >= 免费边界
        ):
            continue
        起始下标, 结束下标 = 起点[1] - 1, 终点[1] - 1
        if not _百度出版标题匹配(区块列表[起始下标], 标题):
            continue
        if 终点 < 免费边界 and not _百度出版标题匹配(区块列表[结束下标], 下一标题):
            continue
        正文区块 = 区块列表[起始下标 + 1 : 结束下标]
        if any(
            not isinstance(区块, dict)
            or 区块.get("t") in {"h1", "h2", "h3", "h4", "h5", "h6"}
            for 区块 in 正文区块
        ):
            continue
        正文 = "\n".join(_百度出版节点文本(区块) for 区块 in 正文区块)
        if 正文.strip():
            结果[编号] = 正文
    return 结果


async def 下载百度出版正文(
    会话: aiohttp.ClientSession,
    文档编号: str,
    目录: list[dict[str, Any]],
    版本: str,
) -> list[str | None]:
    结果: list[str | None] = [None] * len(目录)
    分组: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for 下标, 章节 in enumerate(目录):
        页面编号 = str(章节.get("source_page") or "").strip()
        if 页面编号:
            分组.setdefault(页面编号, []).append((下标, 章节))
    信号量 = asyncio.Semaphore(百度最大并发数)
    节流器 = _百度请求节流器()
    页面结果: dict[str, dict[str, str]] = {}
    页面锁 = asyncio.Lock()
    页面进度锁 = asyncio.Lock()
    已完成页面 = 0
    下次页面日志 = max(1, (len(分组) + 3) // 4)

    async def 下载页面(
        页面编号: str, 页面目录: list[tuple[int, dict[str, Any]]]
    ) -> None:
        nonlocal 已完成页面, 下次页面日志
        async with 信号量:
            try:
                if any(章节.get("source_doc_id") != 文档编号 or 章节.get("source_version") != 版本 for _, 章节 in 页面目录):
                    raise RuntimeError("published_identity_mismatch")
                数据 = await _请求JSON(
                    会话,
                    百度出版正文地址,
                    {"cn": 页面编号, "version": 版本, "doc_id": 文档编号},
                    节流器=节流器,
                )
                状态 = 数据.get("status") if isinstance(数据, dict) else None
                if not isinstance(状态, dict) or _安全整数(状态.get("code"), -1) != 0:
                    logger.debug(
                        "百度出版正文页面获取失败：页码=%s, 错误=BusinessError",
                        页面编号,
                    )
                    return
                数据节点 = 数据.get("data")
                内容 = 数据节点.get("content") if isinstance(数据节点, dict) else None
                当前目录 = [章节 for _, 章节 in 页面目录]
                拆分结果 = _拆分百度出版页面正文(内容, 当前目录)
                async with 页面锁:
                    页面结果[页面编号] = 拆分结果
            except _百度访问错误:
                raise
            except Exception as 异常:
                logger.debug(
                    "百度出版正文页面获取失败：页码=%s, 错误=%s",
                    页面编号,
                    type(异常).__name__,
                )
            finally:
                async with 页面进度锁:
                    已完成页面 += 1
                    if 已完成页面 >= 下次页面日志 or 已完成页面 == len(分组):
                        logger.info(
                            "百度出版正文进度：书籍编号=%s, 进度=%s/%s, 成功=%s",
                            文档编号,
                            已完成页面,
                            len(分组),
                            sum(bool(页面结果.get(页面, {})) for 页面 in 分组),
                        )
                        下次页面日志 += max(1, (len(分组) + 3) // 4)

    工作项 = iter(分组.items())

    async def 工作() -> None:
        for 页面编号, 项目 in 工作项:
            await 下载页面(页面编号, 项目)

    任务 = [asyncio.create_task(工作()) for _ in range(min(百度最大并发数, len(分组)))]
    try:
        await asyncio.gather(*任务)
    finally:
        for 当前 in 任务:
            if not 当前.done():
                当前.cancel()
        await asyncio.gather(*任务, return_exceptions=True)
    for 页面编号, 页面目录 in 分组.items():
        当前结果 = 页面结果.get(页面编号)
        if 当前结果 is None:
            continue
        for 下标, 章节 in 页面目录:
            章节编号 = str(章节.get("id") or "")
            if 章节编号 in 当前结果:
                结果[下标] = 当前结果[章节编号]
    return 结果


def _解密百度正文(密文: bytes) -> str:
    if not 密文 or len(密文) % 16 or AES is None or unpad is None:
        return ""
    try:
        明文 = unpad(AES.new(百度AES密钥, AES.MODE_CBC, 百度AES向量).decrypt(密文), AES.block_size)
        正文 = 明文.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").strip()
        if 正文.lower().startswith(("<!doctype html", "<html")):
            return ""
        return 正文
    except (ValueError, UnicodeError):
        return ""


async def _下载百度章节(
    会话: aiohttp.ClientSession, 书籍编号: str, 章节: dict[str, Any],
    信号量: asyncio.Semaphore, 节流器: _百度请求节流器 | None = None,
) -> str:
    编号 = str(章节.get("id") or "")
    async with 信号量:
        _检查百度章节权限(章节)
        for 次数 in range(百度请求重试次数):
            try:
                新版 = _是百度文档编号(书籍编号)
                参数 = _百度网页参数({"doc_id": 书籍编号, "cid": 编号}) if 新版 else {
                    "action": "novel", "type": "content", "uid": 百度固定UID, "ua": 百度固定UA,
                    "ctv": "2", "cen": "ua_uid",
                    "data": json.dumps({"gid": 书籍编号, "cid": 编号}, separators=(",", ":")),
                }
                元数据 = await _请求JSON(会话, 百度正文地址 if 新版 else 百度旧版目录地址, 参数, 节流器=节流器, 重试=False)
                if 新版:
                    _检查百度章节权限(元数据)
                    数据 = 元数据.get("data")
                    数据 = 数据 if isinstance(数据, dict) else {}
                    _检查百度章节权限(数据)
                    if not _百度出版接口成功(元数据):
                        raise RuntimeError("chapter_business_error")
                    章节数据 = 数据.get("items")
                    if not isinstance(章节数据, dict) or str(章节数据.get("cid") or "") != 编号:
                        raise RuntimeError("chapter_identity_mismatch")
                    _检查百度章节权限(章节数据)
                    内容地址 = 章节数据.get("cdn_url")
                else:
                    if not _百度成功(元数据):
                        raise RuntimeError("chapter_business_error")
                    内容地址 = 元数据.get("data", {}).get("novel", {}).get("content", {}).get("dataset", {}).get("content_url")
                if not _是百度官方地址(内容地址):
                    raise RuntimeError("invalid_content_host")
                if 节流器 is not None:
                    await 节流器.等待()
                async with 会话.get(内容地址, allow_redirects=False) as 响应:
                    if 响应.status in {403, 429}:
                        raise _百度访问错误("http_blocked")
                    响应.raise_for_status()
                    if 响应.status != 200:
                        raise RuntimeError("unexpected_content_status")
                    密文 = await 响应.read()
                if len(密文) > 16 * 1024 * 1024:
                    raise RuntimeError("content_too_large")
                正文 = _解密百度正文(密文)
                if 正文:
                    return 正文
                raise RuntimeError("invalid_content")
            except _百度访问错误:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, ValueError) as 异常:
                logger.debug("百度小说章节获取失败：阶段=chapter, 错误类型=%s", type(异常).__name__)
                if 次数 + 1 < 百度请求重试次数:
                    await asyncio.sleep(0.25 * (次数 + 1))
    return ""


async def 下载百度正文(
    会话: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]],
) -> list[str]:
    _校验百度目录(目录)
    结果 = [""] * len(目录)
    信号量 = asyncio.Semaphore(百度最大并发数)
    节流器 = _百度请求节流器()
    工作项 = iter(enumerate(目录))
    已完成 = 0
    进度节点 = {max(1, (len(目录) * n + 3) // 4) for n in range(1, 5)}
    logger.info("百度小说章节进度：书籍编号=%s, 进度=0/%s, 并发数=%s", 书籍编号, len(目录), min(百度最大并发数, len(目录)))

    async def 工作() -> None:
        nonlocal 已完成
        for 下标, 章节 in 工作项:
            结果[下标] = await _下载百度章节(会话, 书籍编号, 章节, 信号量, 节流器)
            已完成 += 1
            if 已完成 in 进度节点:
                logger.info("百度小说章节进度：书籍编号=%s, 进度=%s/%s, 成功=%s", 书籍编号, 已完成, len(目录), sum(bool(x) for x in 结果))

    任务 = [asyncio.create_task(工作()) for _ in range(min(百度最大并发数, len(目录)))]
    try:
        await asyncio.gather(*任务)
    finally:
        for 当前 in 任务:
            if not 当前.done():
                当前.cancel()
        await asyncio.gather(*任务, return_exceptions=True)
    return 结果


def _清理文件名(值: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(值 or "")).strip(" .")
    return 文本[:80] or "百度小说"


def 生成百度小说文件内容(
    书籍编号: str,
    详情: dict[str, Any],
    目录: list[dict[str, Any]],
    正文列表: list[str],
) -> tuple[str, bytes]:
    _校验百度目录(目录)
    预期 = _安全整数(详情.get("chapter_count"))
    if 预期 > 0 and 预期 != len(目录):
        raise RuntimeError("incomplete_book_catalog")
    if len(目录) != len(正文列表) or any(not isinstance(正文, str) or not 正文.strip() for 正文 in 正文列表):
        raise RuntimeError("incomplete_book_content")
    状态 = str(详情.get("status") or "连载")
    书名 = _清理文件名(详情.get("title") or f"百度小说{书籍编号}")
    作者 = _清理文件名(详情.get("author") or "未知")
    文件名 = f"[{状态}]书名：{书名} 作者：{作者}.txt"
    行列表 = [
        百度文件声明,
        "",
        f"名称：{详情.get('title') or '未知'}",
        f"作者：{详情.get('author') or '未知'}",
        f"状态：{状态}",
        f"字数：{格式化百度字数(详情.get('word_count'))}",
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


def 写入百度下载缓存文件(文件名: str, 内容: bytes) -> Path:
    if not isinstance(内容, bytes) or not 内容:
        raise ValueError("empty_txt")
    百度小说缓存目录.mkdir(parents=True, exist_ok=True)
    安全文件名 = _清理文件名(Path(str(文件名)).stem) + ".txt"
    for 序号 in range(1000):
        路径 = 百度小说缓存目录 / (安全文件名 if 序号 == 0 else f"{Path(安全文件名).stem}_{序号}.txt")
        try:
            输出 = 路径.open("xb")
        except FileExistsError:
            continue
        try:
            with 输出:
                输出.write(内容)
            文件缓存工具.标记小说缓存正在使用(路径)
            return 路径
        except BaseException:
            路径.unlink(missing_ok=True)
            raise
    raise RuntimeError("cache_name_conflict")


def 删除百度缓存文件(路径: Any) -> None:
    if 路径:
        文件缓存工具.删除小说缓存文件(路径)


async def _准备发送文本文件(
    event: Any, 文件名: str, 内容: bytes, 配置: Any, 书名: str, 作者: str
) -> dict[str, Any]:
    路径 = 写入百度下载缓存文件(文件名, 内容)
    if 小说网盘 is None:
        删除百度缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    try:
        上传结果 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传结果.get("success"):
            删除百度缓存文件(路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None}
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(上传结果.get("share_url") or "")
        )
        if 完成结果.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": 路径}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 路径}
        删除百度缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    except Exception as 异常:
        logger.warning("百度小说文件发送失败：错误=%s", type(异常).__name__)
        删除百度缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}


def 启动百度后台上传并清理源文件(配置: Any, 路径: Any, 文件名: str) -> None:
    if 路径:
        删除百度缓存文件(路径)


async def 生成百度下载回复流(
    event: Any, 来源: str, 配置: Any = None
) -> AsyncIterator[Any]:
    stage = "解析"
    try:
        async with 创建百度HTTP会话() as 会话:
            书籍编号 = await _异步解析书籍编号(来源, 会话)
            if not 书籍编号:
                yield 百度下载失败提示
                return
            stage = "详情目录"
            详情 = await 获取百度详情(会话, 书籍编号)
            if not 详情:
                yield 百度下载失败提示
                return
            if not _是百度文档编号(书籍编号) and not _是百度文档编号(详情.get("doc_id")):
                新编号 = await _补查百度文档编号(会话, 书籍编号, 详情)
                if 新编号:
                    书籍编号 = 新编号
                    详情 = await 获取百度详情(会话, 新编号)
                    if not 详情:
                        yield 百度下载失败提示
                        return
            if _是百度文档编号(详情.get("doc_id")):
                书籍编号 = str(详情["doc_id"])
            出版模式 = False
            出版来源 = bool(详情.get("is_yuedu_source")) and _是百度文档编号(书籍编号)
            正文版本 = ""
            if 出版来源:
                stage = "出版目录"
                图书数据 = await 获取百度出版图书(会话, 书籍编号)
                出版模式 = _百度出版图书匹配(图书数据, 书籍编号)
                if not 出版模式:
                    yield 百度下载失败提示
                    return
                目录 = _从百度出版图书提取目录(图书数据, 书籍编号)
                正文版本 = _获取百度出版版本(图书数据)
                if not 目录 or not 正文版本:
                    yield 百度下载失败提示
                    return
            else:
                目录 = await 获取百度目录(会话, 书籍编号)
                if not 目录:
                    yield 百度下载失败提示
                    return
            预期章节数 = _安全整数(详情.get("chapter_count"))
            if 预期章节数 > 0 and len(目录) != 预期章节数:
                logger.warning(
                    "百度小说目录不完整：书籍编号=%s, 目录=%s, 预期=%s",
                    书籍编号,
                    len(目录),
                    预期章节数,
                )
                yield 百度下载失败提示
                return
            logger.info("百度小说开始下载：书籍编号=%s, 章节数=%s", 书籍编号, len(目录))
            yield "\n".join(
                [
                    f"书名：{详情.get('title') or '未知'}",
                    f"作者：{详情.get('author') or '未知'}",
                    f"状态：{详情.get('status') or '连载'}",
                    f"章节：{len(目录)} 章",
                    f"字数：{格式化百度字数(详情.get('word_count'))}",
                    "",
                    "正在下载中请稍等.....",
                ]
            )
            stage = "正文"
            if 出版模式:
                出版正文列表 = await 下载百度出版正文(
                    会话, 书籍编号, 目录, 正文版本
                )
                正文缺失 = any(not 正文 or not 正文.strip() for 正文 in 出版正文列表)
                正文列表 = [正文 or "" for 正文 in 出版正文列表]
            else:
                正文列表 = await 下载百度正文(会话, 书籍编号, 目录)
                正文缺失 = any(not 正文 for 正文 in 正文列表)
        if len(正文列表) != len(目录) or 正文缺失:
            logger.warning(
                "百度小说正文不完整：书籍编号=%s, 成功=%s, 总数=%s",
                书籍编号,
                sum(bool(x) for x in 正文列表),
                len(目录),
            )
            yield 百度下载失败提示
            return
        文件名, 内容 = 生成百度小说文件内容(书籍编号, 详情, 目录, 正文列表)
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
            启动百度后台上传并清理源文件(配置, 路径, 文件名)
            return
        降级文本 = str(发送结果.get("fallback_text") or "")
        if 降级文本:
            try:
                yield 降级文本
            finally:
                启动百度后台上传并清理源文件(配置, 路径, 文件名)
            return
        yield 百度文件发送失败提示
    except Exception as 异常:
        logger.warning("百度小说下载失败：阶段=%s, 错误=%s", stage, type(异常).__name__)
        yield 百度下载失败提示


def 获取百度小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[Any] | None:
    来源 = 提取百度来源(event, 命令文本)
    if 来源 is None:
        return None
    return 生成百度下载回复流(event, 来源, 配置)


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    数量 = max(1, min(30, int(需要数量 or 20)))
    结果 = []
    已见 = set()
    try:
        async with 创建百度HTTP会话(2) as 会话:
            for 起点 in range(0, 数量, 10):
                数据 = await _请求JSON(会话, 百度搜索地址, _百度网页参数({"pn": 起点, "rn": 10, "query": 关键词}))
                if not _百度出版接口成功(数据):
                    break
                项目列表 = (数据.get("data") or {}).get("doc_info")
                if not isinstance(项目列表, list):
                    break
                for 项目 in 项目列表:
                    if not isinstance(项目, dict):
                        continue
                    编号 = str(项目.get("doc_id") or "").strip().lower()
                    标题 = str(项目.get("title") or "").strip()
                    if not _是百度文档编号(编号) or not 标题 or 编号 in 已见:
                        continue
                    已见.add(编号)
                    结果.append({
                        "book_id": 编号, "doc_id": 编号, "title": 标题,
                        "novel_book_id": str(项目.get("novel_book_id") or ""),
                        "author": str(项目.get("author") or "未知").strip(),
                        "intro": str(项目.get("description") or "").strip(),
                        "url": 构造百度链接(编号), "score": 项目.get("score") or 0,
                        "word_count": 项目.get("words_num") or 项目.get("wordCount") or 0,
                    })
                if len(项目列表) < 10 or len(结果) >= 数量:
                    break
        return 结果[:数量]
    except Exception as 异常:
        logger.debug("百度小说搜索失败：错误类型=%s", type(异常).__name__)
        return 结果[:数量]
