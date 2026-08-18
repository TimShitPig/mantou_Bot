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
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception:
    百度网盘 = None

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题


百度搜索地址 = "https://novelapi.baidu.com/boxnovel/cors"
百度详情地址 = 百度搜索地址
百度目录地址 = "https://novelapi.baidu.com/searchbox"
百度正文地址 = 百度目录地址
百度允许域名 = {"mr.baidu.com", "boxnovel.baidu.com", "novel.baidu.com"}
百度链接正则 = re.compile(
    r"https?://(?:mr\.baidu\.com|boxnovel\.baidu\.com|novel\.baidu\.com)" r"[^\s<>\"']*",
    re.IGNORECASE,
)
百度卡片编号正则 = re.compile(
    r"[\"'`]?\b(?:gid|book[_-]?id|bookgid|resource[_-]?id)[\"'`]?\s*[:=]\s*[\"'`]?([0-9]{5,30})",
    re.IGNORECASE,
)
百度请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://novel.baidu.com/",
}
百度固定UID = "juB18g8oHi_-aH88lPHl8g8nHi_ju2avgi25ugi3Sf8R9WMxpiWmuYMaA"
百度固定UA = "_a-qiyuuvigyNE64I5me6NN0v8oZu-I4_C2Hiyat2iqlC"
百度AES密钥 = b"D0CD8B760CE07BC3"
百度AES向量 = b"2011121211143000"
百度最大并发数 = 10
百度请求重试次数 = 3
百度下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
百度文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
)
百度下载失败提示 = "下载失败"
百度文件发送失败提示 = "文件发送失败，请稍后再试"


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
    for 字段 in ("message_str", "message", "raw_message", "message_obj", "text", "content", "data"):
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
        for 匹配 in 百度链接正则.finditer(文本):
            return _清理来源(匹配.group(0))
        解码文本 = 文本
        for _ in range(2):
            新文本 = _安全解码(解码文本)
            if 新文本 == 解码文本:
                break
            解码文本 = 新文本
        for 匹配 in 百度链接正则.finditer(解码文本):
            return _清理来源(匹配.group(0))
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


def _数字文本(值: Any) -> str:
    文本 = str(值 or "").strip()
    return 文本 if re.fullmatch(r"\d{5,30}", 文本) else ""


def 解析百度书籍编号(来源: Any) -> str:
    文本 = _清理来源(来源)
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
    for 键 in ("gid", "bookid", "book_id", "bookgid"):
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
            for 键 in ("gid", "bookid", "book_id", "bookGid"):
                书籍编号 = _数字文本(数据.get(键))
                if 书籍编号:
                    return 书籍编号
    路径匹配 = re.search(r"(?:book|novel|detail|reader)[^0-9]{0,20}(\d{5,30})", 解析.path, re.IGNORECASE)
    if 路径匹配:
        return 路径匹配.group(1)
    原文匹配 = re.search(r"(?:gid|bookid|book_id)%?3?d%?22?%?3a?%?22?(\d{5,30})", 文本, re.IGNORECASE)
    return 原文匹配.group(1) if 原文匹配 else ""


def 构造百度链接(书籍编号: Any) -> str:
    return f"https://boxnovel.baidu.com/boxnovel/reader?gid={书籍编号}"


def 创建百度HTTP会话(并发数: int = 百度最大并发数) -> aiohttp.ClientSession:
    并发数 = max(1, int(并发数 or 1))
    超时 = aiohttp.ClientTimeout(total=90, sock_connect=15, sock_read=60)
    连接器 = aiohttp.TCPConnector(limit=并发数, limit_per_host=并发数, ttl_dns_cache=300)
    return aiohttp.ClientSession(headers=百度请求头, timeout=超时, connector=连接器)


async def _请求JSON(会话: aiohttp.ClientSession, 地址: str, 参数: dict[str, Any]) -> dict[str, Any]:
    最后异常: Exception | None = None
    for 次数 in range(百度请求重试次数):
        try:
            async with 会话.get(地址, params=参数) as 响应:
                响应.raise_for_status()
                数据 = await 响应.json(content_type=None)
            return 数据 if isinstance(数据, dict) else {}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as 异常:
            最后异常 = 异常
            if 次数 + 1 < 百度请求重试次数:
                await asyncio.sleep(0.25 * (次数 + 1))
    raise RuntimeError("百度接口请求失败") from 最后异常


async def _解析短链(会话: aiohttp.ClientSession, 来源: str) -> str:
    try:
        async with 会话.get(来源, allow_redirects=False) as 响应:
            位置 = 响应.headers.get("Location") or ""
        if not 位置:
            return ""
        return 解析百度书籍编号(位置)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return ""


async def _异步解析书籍编号(来源: str, 会话: aiohttp.ClientSession) -> str:
    编号 = 解析百度书籍编号(来源)
    if 编号:
        return 编号
    try:
        主机 = (urllib.parse.urlsplit(来源).hostname or "").lower()
    except Exception:
        主机 = ""
    return await _解析短链(会话, 来源) if 主机 == "mr.baidu.com" else ""


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
    数字 = _安全整数(值)
    return f"{数字:,}字" if 数字 > 0 else "未知"


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
    数据 = await _请求JSON(
        会话,
        百度详情地址,
        {
            "osname": "bdboxnovelsdk",
            "action": "novel",
            "type": "detail",
            "tojsondata": "1",
            "data": json.dumps({"gid": 书籍编号, "frombox": True}, separators=(",", ":")),
        },
    )
    if not _百度成功(数据):
        return {}
    return _取详情字段(数据)


async def 获取百度目录(会话: aiohttp.ClientSession, 书籍编号: str) -> list[dict[str, Any]]:
    数据 = await _请求JSON(
        会话,
        百度目录地址,
        {
            "action": "novel",
            "type": "chapter",
            "data": json.dumps({"gid": 书籍编号}, separators=(",", ":")),
        },
    )
    if not _百度成功(数据):
        return []
    项目列表 = 数据.get("data", {}).get("novel", {}).get("chapter", {}).get("dataset", {}).get("items", [])
    if not isinstance(项目列表, list):
        return []
    目录: list[dict[str, Any]] = []
    已见: set[str] = set()
    for 项目 in 项目列表:
        if not isinstance(项目, dict):
            continue
        编号 = str(项目.get("cid") or "").strip()
        标题 = str(项目.get("title") or "").strip()
        if 编号 and 标题 and 编号 not in 已见:
            已见.add(编号)
            目录.append({"id": 编号, "title": 标题})
    return 目录


def _解密百度正文(密文: bytes) -> str:
    if not 密文 or AES is None or unpad is None:
        return ""
    try:
        明文 = unpad(AES.new(百度AES密钥, AES.MODE_CBC, 百度AES向量).decrypt(密文), AES.block_size)
        return 明文.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").strip()
    except Exception:
        return ""


async def _下载百度章节(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    章节: dict[str, Any],
    信号量: asyncio.Semaphore,
) -> str:
    编号 = str(章节.get("id") or "")
    async with 信号量:
        for 次数 in range(百度请求重试次数):
            try:
                元数据 = await _请求JSON(
                    会话,
                    百度正文地址,
                    {
                        "action": "novel",
                        "type": "content",
                        "uid": 百度固定UID,
                        "ua": 百度固定UA,
                        "ctv": "2",
                        "cen": "ua_uid",
                        "data": json.dumps({"gid": 书籍编号, "cid": 编号}, separators=(",", ":")),
                    },
                )
                内容地址 = (
                    元数据.get("data", {})
                    .get("novel", {})
                    .get("content", {})
                    .get("dataset", {})
                    .get("content_url")
                )
                if not isinstance(内容地址, str) or urllib.parse.urlsplit(内容地址).scheme not in {"http", "https"}:
                    raise RuntimeError("content url missing")
                async with 会话.get(内容地址) as 响应:
                    响应.raise_for_status()
                    密文 = await 响应.read()
                if len(密文) > 16 * 1024 * 1024:
                    raise RuntimeError("content too large")
                正文 = await asyncio.to_thread(_解密百度正文, 密文)
                if 正文:
                    return 正文
                raise RuntimeError("empty content")
            except Exception as 异常:
                logger.debug("百度小说章节获取失败：chapter=%s, error=%s", 编号, type(异常).__name__)
                if 次数 + 1 < 百度请求重试次数:
                    await asyncio.sleep(0.25 * (次数 + 1))
    return ""


async def 下载百度正文(
    会话: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
) -> list[str]:
    结果 = [""] * len(目录)
    信号量 = asyncio.Semaphore(百度最大并发数)
    已完成 = 0
    下次日志 = max(1, len(目录) // 10)
    锁 = asyncio.Lock()

    async def 下载一章(下标: int, 章节: dict[str, Any]) -> None:
        nonlocal 已完成, 下次日志
        结果[下标] = await _下载百度章节(会话, 书籍编号, 章节, 信号量)
        async with 锁:
            已完成 += 1
            if 已完成 >= 下次日志 or 已完成 == len(目录):
                logger.info(
                    "百度小说章节进度：book_id=%s, progress=%s/%s, success=%s",
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
    return 文本[:80] or "百度小说"


def 生成百度小说文件内容(
    书籍编号: str,
    详情: dict[str, Any],
    目录: list[dict[str, Any]],
    正文列表: list[str],
) -> tuple[str, bytes]:
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
    百度下载缓存目录.mkdir(parents=True, exist_ok=True)
    安全文件名 = Path(_清理文件名(文件名)).name
    路径 = 百度下载缓存目录 / 安全文件名
    if 路径.exists():
        for 序号 in range(1, 1000):
            候选 = 百度下载缓存目录 / f"{路径.stem}_{序号}{路径.suffix}"
            if not 候选.exists():
                路径 = 候选
                break
    路径.write_bytes(内容)
    小说缓存工具.标记下载缓存正在使用(路径)
    return 路径


def 删除百度缓存文件(路径: Any) -> None:
    if 路径:
        小说缓存工具.删除下载缓存文件(路径)


async def _准备发送文本文件(event: Any, 文件名: str, 内容: bytes, 配置: Any, 书名: str, 作者: str) -> dict[str, Any]:
    路径 = 写入百度下载缓存文件(文件名, 内容)
    if 小说网盘 is None:
        删除百度缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    try:
        上传结果 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传结果.get("success"):
            删除百度缓存文件(路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None}
        完成结果 = await 小说网盘.发送小说下载完成链接(event, 书名, 作者, str(上传结果.get("share_url") or ""))
        if 完成结果.get("sent"):
            return {"sent": True, "fallback_text": "", "source_cache_path": 路径}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 路径}
        删除百度缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}
    except Exception as 异常:
        logger.warning("百度小说文件发送失败：error=%s", type(异常).__name__)
        删除百度缓存文件(路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None}


def 启动百度后台上传并清理源文件(配置: Any, 路径: Any, 文件名: str) -> None:
    if not 路径:
        return

    async def 任务() -> None:
        备份完成 = True
        try:
            if 百度网盘 is not None:
                结果 = await 百度网盘.后台上传小说文件(配置, 路径, 文件名)
                if not isinstance(结果, dict) or (
                    结果.get("enabled") and not (结果.get("success") or 结果.get("skipped"))
                ):
                    备份完成 = False
                    logger.warning("百度小说后台备份失败：file=%s, error=UploadFailed", 文件名)
        except Exception as 异常:
            备份完成 = False
            logger.warning("百度小说后台备份异常：error=%s", type(异常).__name__)
        finally:
            if not 备份完成:
                小说缓存工具.更新上传任务(
                    路径,
                    "backup_pending",
                    last_error="百度网盘后台备份未完成",
                )
            else:
                小说缓存工具.更新上传任务(路径, "primary_done", last_error="")
            删除百度缓存文件(路径)

    try:
        asyncio.create_task(任务())
    except RuntimeError:
        删除百度缓存文件(路径)


async def 生成百度下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    stage = "解析"
    try:
        async with 创建百度HTTP会话() as 会话:
            书籍编号 = await _异步解析书籍编号(来源, 会话)
            if not 书籍编号:
                yield 百度下载失败提示
                return
            stage = "详情目录"
            详情, 目录 = await asyncio.gather(获取百度详情(会话, 书籍编号), 获取百度目录(会话, 书籍编号))
            if not 详情 or not 目录:
                yield 百度下载失败提示
                return
            logger.info("百度小说开始下载：book_id=%s, chapters=%s", 书籍编号, len(目录))
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
            正文列表 = await 下载百度正文(会话, 书籍编号, 目录)
        if len(正文列表) != len(目录) or any(not 正文 for 正文 in 正文列表):
            logger.warning("百度小说正文不完整：book_id=%s, success=%s, total=%s", 书籍编号, sum(bool(x) for x in 正文列表), len(目录))
            yield 百度下载失败提示
            return
        文件名, 内容 = 生成百度小说文件内容(书籍编号, 详情, 目录, 正文列表)
        发送结果 = await _准备发送文本文件(event, 文件名, 内容, 配置, str(详情.get("title") or "未知"), str(详情.get("author") or "未知"))
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
        logger.warning("百度小说下载失败：stage=%s, error=%s", stage, type(异常).__name__)
        yield 百度下载失败提示


def 获取百度小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取百度来源(event, 命令文本)
    if 来源 is None:
        return None
    return 生成百度下载回复流(event, 来源, 配置)


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    try:
        async with 创建百度HTTP会话(2) as 会话:
            数据 = await _请求JSON(
                会话,
                百度搜索地址,
                {
                    "osname": "bdboxnovelsdk",
                    "action": "novel",
                    "type": "search",
                    "data": json.dumps({"word": 关键词, "fromaction": "search", "pageNum": 1}, ensure_ascii=False, separators=(",", ":")),
                },
            )
        if not _百度成功(数据):
            return []
        项目列表 = 数据.get("novel", {}).get("search", {}).get("data", {}).get("list", [])
        结果: list[dict[str, Any]] = []
        for 项目 in 项目列表 if isinstance(项目列表, list) else []:
            if not isinstance(项目, dict):
                continue
            编号 = _数字文本(项目.get("gid"))
            标题 = str(项目.get("title") or "").strip()
            if not 编号 or not 标题:
                continue
            结果.append(
                {
                    "book_id": 编号,
                    "title": 标题,
                    "author": str(项目.get("author") or "未知").strip(),
                    "intro": str(项目.get("summary") or "").strip(),
                    "url": 构造百度链接(编号),
                    "score": 项目.get("score") or 0,
                    "word_count": 项目.get("wordCount") or 0,
                }
            )
        return 结果[: max(1, min(30, int(需要数量 or 20)))]
    except Exception as 异常:
        logger.debug("百度小说搜索失败：error=%s", type(异常).__name__)
        return []
