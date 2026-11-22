"""书耽 App 搜索、目录及授权正文。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import re
from collections import deque
from itertools import islice
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote, urlsplit
from weakref import WeakValueDictionary

import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

try:
    from astrbot.api import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能 import 文件缓存
from 功能文件.管理功能.基础功能.消息工具 import 读取字段
from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID
from 功能文件.管理功能.小说功能.功能.文本处理 import 格式化小说字数, 去除章节正文重复标题
from 功能文件.管理功能.小说功能.小说 import 番茄小说
from 功能文件.管理功能.网盘功能 import 小说网盘


书耽正文最大并发数 = 200
_服务地址 = "https://app.shubl.com"
_协议密钥 = base64.b64decode("L6alxSR4ttjXvcGpZozYtdcJtG4l0tSnQplRUONIRsw=")
_应用签名 = "f73576612783f8ed8b68cdf73a56be94"
_最大响应字节 = 4 * 1024 * 1024
_搜索接口 = "/bookcity/get_filter_search_book_list"
_详情接口 = "/book/get_info_by_id"
_目录接口 = "/chapter/get_chapter_list_group_by_division"
_章节接口 = "/chapter/get_chapter_info"
if "_章节限额" not in globals():
    _章节限额 = WeakValueDictionary()

_下载失败 = "下载失败 请重试"
_发送失败 = "文件发送失败，请稍后再试"
_章节不可读 = "部分章节当前不可读，无法下载整本"
_书耽请求凭据: tuple[str, str] | None = None
_书耽未启用 = "书耽下载暂不可用，请联系管理员"


class 书耽请求错误(RuntimeError):
    def __init__(self, 原因: str, *, HTTP状态: int | None = None, 业务码: int | None = None):
        super().__init__(原因)
        self.原因 = 原因
        self.HTTP状态 = HTTP状态
        self.业务码 = 业务码


def _数字(值: Any) -> str:
    return str(值) if type(值) in (int, str) and re.fullmatch(r"[0-9]{1,20}", str(值)) else ""


def _编号(值: Any) -> str:
    文本 = _数字(值)
    return 文本 if 文本 and int(文本) > 0 else ""


def _文本(值: Any) -> str:
    return 值.strip() if isinstance(值, str) else ""


_书耽链接候选 = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_书耽详情路径 = re.compile(r"/book/book_detail/([1-9][0-9]{0,19})/?")
_跳过卡片分支 = {
    "author", "sender", "user", "member", "mentions", "reply", "quote",
    "quoted", "quotedmessage", "reference", "messagereference", "msgelements",
    "message", "rawmessage", "forward", "node", "nodes", "ref",
}


def 提取书耽详情书号(event: Any, 命令文本: Any = "") -> str:
    """只读当前消息的文本和分享卡片，返回书耽详情页的书号。"""
    待检查 = deque([(命令文本, 0, "text"), (event, 0, "message")])
    已检查 = set()
    while 待检查 and len(已检查) < 256:
        值, 深度, 类型 = 待检查.popleft()
        if 值 is None or 深度 > 10 or (id(值), 类型) in 已检查:
            continue
        已检查.add((id(值), 类型))
        if isinstance(值, str):
            if not 值 or len(值) > 65536:
                continue
            if 类型 != "text" and 值.lstrip().startswith(("{", "[")):
                try:
                    结构 = json.loads(值)
                except (ValueError, RecursionError):
                    continue
                待检查.append((结构, 深度 + 1, 类型))
                continue
            文本 = 值
            for _ in range(3):
                文本 = html.unescape(文本).replace("\\/", "/")
                for 匹配 in _书耽链接候选.finditer(文本):
                    链接 = 匹配.group().rstrip("，。；！？、;）)]}\x60")
                    try:
                        地址 = urlsplit(链接)
                    except ValueError:
                        continue
                    if 地址.netloc.lower() not in {"www.shubl.com", "shubl.com"}:
                        continue
                    路径 = _书耽详情路径.fullmatch(地址.path)
                    if 路径:
                        return 路径[1]
                解码 = unquote(文本)
                if 解码 == 文本:
                    break
                文本 = 解码
            continue
        if isinstance(值, (list, tuple)):
            待检查.extend((项, 深度 + 1, 类型) for 项 in 值[:128])
            continue
        if 类型 == "card" and isinstance(值, dict):
            待检查.extend(
                (项, 深度 + 1, "card") for 键, 项 in islice(值.items(), 128)
                if str(键).lower().replace("_", "").replace("-", "") not in _跳过卡片分支
                and isinstance(项, (str, dict, list))
            )
            continue
        段类型 = 读取字段(值, "type")
        段类型 = str(getattr(段类型, "value", 段类型) or "").lower().removeprefix("componenttype.")
        if 段类型 in {"reply", "at", "atall", "forward", "node", "nodes"}:
            continue
        if 段类型 in {"ark", "json", "share"} or 类型 == "card":
            模式字段 = (("data", "card"), ("url", "text"), ("kv", "card"), ("obj", "card"), ("obj_kv", "card"), ("value", "text"))
        elif 段类型 in {"plain", "text"}:
            模式字段 = (("text", "text"), ("data", "message"))
        else:
            模式字段 = (("message_str", "text"), ("content", "text"), ("text", "text"),
                         ("message_obj", "message"), ("message", "message"), ("raw_message", "message"),
                         ("ark", "card"))
        待检查.extend((读取字段(值, 字段), 深度 + 1, 模式) for 字段, 模式 in 模式字段)
    return ""


def 书耽来源(书籍编号: Any) -> str:
    编号 = _编号(书籍编号)
    return f"shubl:{编号}" if 编号 else ""


def _书耽书籍状态(书: dict[str, Any]) -> str:
    状态 = _文本(书.get("up_status"))
    if 状态 in {"完结", "已完结", "完本"}:
        return "完结"
    return "连载" if 状态 in {"连载", "连载中"} else "未知"


def _书籍资料(书: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _文本(书.get("book_name")),
        "author": _文本(书.get("author_name")) or "未知",
        "status": _书耽书籍状态(书),
        "word_count": int(_编号(书.get("total_word_count")) or "0"),
        "intro": _文本(书.get("description")),
    }


def _创建书耽会话(连接数: int) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=连接数, limit_per_host=连接数),
        timeout=aiohttp.ClientTimeout(total=25, connect=8, sock_read=12),
        headers={"app-version": "4.1.4", "User-Agent": "okhttp/3.14.9"},
        cookie_jar=aiohttp.DummyCookieJar(),
        trust_env=True,
    )


def 书耽搜索账号标识(配置: Any = None) -> tuple[str, bytes] | None:
    凭据 = _书耽请求凭据
    if 凭据 is None:
        return None
    指纹 = hashlib.sha256(json.dumps(凭据, ensure_ascii=False).encode("utf-8")).digest()
    return 获取当前机器人AppID(配置), 指纹


def _核对书耽目录章数(目录: list[dict[str, Any]], 预期数量: int, 末章资料: Any) -> None:
    if not 预期数量 or len(目录) == 预期数量:
        return
    # 详情的总数可能比完整目录少一章，此时用同书的末章及连续序号复核。
    if (
        len(目录) == 预期数量 + 1
        and isinstance(末章资料, dict)
        and _编号(末章资料.get("chapter_id")) == _编号(目录[-1].get("chapter_id"))
        and _编号(末章资料.get("chapter_index")) == str(len(目录))
        and all(_编号(章.get("chapter_index")) == str(序号) for 序号, 章 in enumerate(目录, 1))
    ):
        return
    raise 书耽请求错误("incomplete_catalog")


class 书耽客户端:
    def __init__(self, 会话: aiohttp.ClientSession):
        self.会话 = 会话
        if _书耽请求凭据 is None:
            raise 书耽请求错误("shubl_unavailable")
        self._令牌, self._账号 = _书耽请求凭据

    async def _请求(self, 接口: str, **字段: Any) -> dict[str, Any]:
        数据 = {
            "app_signature_md5": _应用签名, "app_version": "4.1.1", "channel": "default",
            **字段, "login_token": self._令牌, "account": self._账号,
        }
        明文 = json.dumps(数据, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        加密器 = AES.new(_协议密钥, AES.MODE_CBC, iv=bytes(16))
        表单 = {"secret_content": base64.b64encode(加密器.encrypt(pad(明文, AES.block_size))).decode("ascii")}
        try:
            async with self.会话.post(_服务地址 + 接口, data=表单, allow_redirects=False) as 响应:
                if 响应.status != 200:
                    raise 书耽请求错误("rate_limited" if 响应.status == 429 else "http_rejected", HTTP状态=响应.status)
                完整响应 = bytearray()
                async for 分段 in 响应.content.iter_chunked(65536):
                    完整响应.extend(分段)
                    if len(完整响应) > _最大响应字节:
                        raise 书耽请求错误("response_too_large")
        except (aiohttp.ClientError, TimeoutError):
            raise 书耽请求错误("transport_failed") from None

        try:
            响应字节 = bytes(完整响应).strip()
            if not 响应字节.startswith(b"{"):
                解密器 = AES.new(_协议密钥, AES.MODE_CBC, iv=bytes(16))
                密文 = base64.b64decode(响应字节, validate=True)
                响应字节 = unpad(解密器.decrypt(密文), AES.block_size)
            结果 = json.loads(响应字节)
        except (ValueError, RecursionError):
            raise 书耽请求错误("invalid_response") from None

        if not isinstance(结果, dict):
            raise 书耽请求错误("invalid_response")
        代码 = _数字(结果.get("code"))
        if 代码 != "100000":
            raise 书耽请求错误("login_required" if 代码 == "200001" else "business_rejected",
                               业务码=int(代码) if 代码 else None)
        if not isinstance(结果.get("data"), dict):
            raise 书耽请求错误("invalid_response")
        return 结果["data"]

    async def 搜索(self, 关键词: str, 数量: int) -> list[dict[str, Any]]:
        数据 = await self._请求(_搜索接口, order="week_click", count=str(数量),
                              category_type="1", page=0, key=关键词)
        列表 = 数据.get("book_list")
        if not isinstance(列表, list):
            raise 书耽请求错误("invalid_search")
        return 列表

    async def 详情(self, 书籍编号: str) -> dict[str, Any]:
        数据 = await self._请求(_详情接口, book_id=书籍编号)
        书 = 数据.get("book_info")
        if not isinstance(书, dict) or _编号(书.get("book_id")) != 书籍编号 or not _文本(书.get("book_name")):
            raise 书耽请求错误("invalid_book")
        return 书

    async def 目录(self, 书籍编号: str, 预期数量: int, *, 末章资料: Any = None) -> list[dict[str, Any]]:
        数据 = await self._请求(_目录接口, book_id=书籍编号, last_update_time="0")
        分卷 = 数据.get("chapter_list_group")
        if not isinstance(分卷, list):
            raise 书耽请求错误("invalid_catalog")
        章节列表 = []
        已见编号 = set()
        for 卷 in 分卷:
            章节 = 卷.get("chapter_list") if isinstance(卷, dict) else None
            if not isinstance(章节, list):
                raise 书耽请求错误("invalid_catalog")
            for 章 in 章节:
                编号 = _编号(章.get("chapter_id")) if isinstance(章, dict) else ""
                if not 编号 or 编号 in 已见编号 or not _文本(章.get("chapter_title")):
                    raise 书耽请求错误("invalid_catalog")
                if "book_id" in 章 and _编号(章["book_id"]) != 书籍编号:
                    raise 书耽请求错误("invalid_catalog")
                已见编号.add(编号)
                章节列表.append(章)
        if not 章节列表:
            raise 书耽请求错误("empty_catalog")
        _核对书耽目录章数(章节列表, 预期数量, 末章资料)
        return 章节列表

    async def 正文(self, 书籍编号: str, 章节信息: dict[str, Any]) -> str:
        章节编号 = _编号(章节信息["chapter_id"])
        数据 = await self._请求(_章节接口, chapter_id=章节编号)
        章 = 数据.get("chapter_info")
        if not isinstance(章, dict) or _编号(章.get("chapter_id")) != 章节编号:
            raise 书耽请求错误("invalid_chapter")
        if "book_id" in 章 and _编号(章["book_id"]) != 书籍编号:
            raise 书耽请求错误("invalid_chapter")
        if _数字(章.get("auth_access")) != "1":
            raise 书耽请求错误("chapter_unavailable")
        原文 = 章.get("txt_content")
        if not isinstance(原文, str):
            raise 书耽请求错误("empty_chapter")
        # 原脚本 content 的逐行清洗保留空行和行内空格。
        内容 = "\n".join(行.lstrip("\u3000 ") for 行 in 原文.split("\n"))
        if not 去除章节正文重复标题(章节信息["chapter_title"], 内容):
            raise 书耽请求错误("empty_chapter")
        return 内容

    async def 下载(self, 书籍编号: str, 目录: list[dict[str, Any]]) -> list[dict[str, Any]]:
        总数 = len(目录)
        并发数 = min(书耽正文最大并发数, 总数)
        循环 = asyncio.get_running_loop()
        限额 = _章节限额.get(循环)
        if 限额 is None:
            限额 = asyncio.Semaphore(书耽正文最大并发数)
            _章节限额[循环] = 限额
        待下载 = iter(enumerate(目录))
        结果 = [{} for _ in 目录]
        已完成 = 0
        停止 = False
        进度节点 = iter(sorted({(总数 * 百分比 + 99) // 100 for 百分比 in (25, 50, 75, 100)}))
        下一节点 = next(进度节点, 总数)
        logger.info("书耽章节进度 0/%s，工作协程=%s", 总数, 并发数)

        async def 工作():
            nonlocal 已完成, 下一节点, 停止
            for 序号, 章 in 待下载:
                async with 限额:
                    if 停止:
                        return
                    try:
                        内容 = await self.正文(书籍编号, 章)
                    except BaseException:
                        停止 = True
                        raise
                结果[序号] = {"index": 序号 + 1, "title": 章["chapter_title"], "content": 内容, "success": True}
                已完成 += 1
                if 已完成 == 下一节点:
                    logger.info("书耽章节进度 %s/%s", 已完成, 总数)
                    下一节点 = next(进度节点, 总数 + 1)

        任务 = [asyncio.create_task(工作()) for _ in range(并发数)]
        try:
            await asyncio.gather(*任务)
        finally:
            for 项 in 任务:
                if not 项.done():
                    项.cancel()
            await asyncio.gather(*任务, return_exceptions=True)
        return 结果


def _保存缓存(文件名: str, 内容: bytes) -> Path:
    文件缓存.小说缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 文件缓存.小说缓存目录 / Path(文件名).name
    for 序号 in range(1000):
        候选 = 路径.with_stem(f"{路径.stem}_{序号}") if 序号 else 路径
        try:
            文件 = 候选.open("xb")
        except FileExistsError:
            continue
        try:
            with 文件:
                文件.write(内容)
            文件缓存.标记小说缓存正在使用(候选)
            return 候选
        except BaseException:
            文件缓存.删除小说缓存文件(候选)
            raise
    raise 书耽请求错误("cache_collision")


async def _异步写入缓存(文件名: str, 内容: bytes) -> Path:
    任务 = asyncio.create_task(asyncio.to_thread(_保存缓存, 文件名, 内容))
    try:
        return await asyncio.shield(任务)
    except asyncio.CancelledError:
        try:
            路径 = await 任务
            文件缓存.删除小说缓存文件(路径)
        finally:
            raise


async def 生成书耽下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    匹配 = re.fullmatch(r"shubl:([0-9]{1,20})", str(来源 or ""))
    书籍编号 = _编号(匹配[1]) if 匹配 else ""
    if not 书籍编号:
        yield _下载失败
        return

    阶段 = "metadata"
    路径 = None
    try:
        async with _创建书耽会话(书耽正文最大并发数) as 会话:
            客户端 = 书耽客户端(会话)
            详情 = await 客户端.详情(书籍编号)
            目录 = await 客户端.目录(
                书籍编号, int(_编号(详情.get("chapter_amount")) or "0"), 末章资料=详情.get("last_chapter_info")
            )
            书籍信息 = _书籍资料(详情)
            书籍信息["word_count"] = 格式化小说字数(书籍信息["word_count"])
            yield 番茄小说.格式化番茄下载提示(书籍信息, len(目录))

            阶段 = "chapters"
            结果 = await 客户端.下载(书籍编号, 目录)

        阶段 = "txt"
        文件名, 内容 = await asyncio.to_thread(番茄小说.生成番茄小说文件内容, 书籍编号, 书籍信息, 目录, 结果)
        路径 = await _异步写入缓存(文件名, 内容)

        阶段 = "upload"
        上传 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传.get("success"):
            yield _发送失败
            return
        阶段 = "share"
        发送 = await 小说网盘.发送小说下载结果(event, 书籍信息["title"], 书籍信息["author"], 上传)
        if not 发送.get("sent"):
            yield str(发送.get("fallback_text") or _发送失败)
    except Exception as 错误:
        受控错误 = 错误 if isinstance(错误, 书耽请求错误) else None
        logger.warning("书耽下载失败：阶段=%s，类型=%s，原因=%s，HTTP=%s，业务码=%s",
                       阶段, type(错误).__name__, 受控错误.原因 if 受控错误 else "operation_failed",
                       受控错误.HTTP状态 if 受控错误 else None, 受控错误.业务码 if 受控错误 else None)
        if 受控错误 and 受控错误.原因 == "chapter_unavailable":
            yield _章节不可读
        elif 受控错误 and 受控错误.原因 == "shubl_unavailable":
            yield _书耽未启用
        else:
            yield _发送失败 if 阶段 in {"upload", "share"} else _下载失败
    finally:
        if 路径 is not None:
            文件缓存.删除小说缓存文件(路径)


def 获取书耽小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 书耽来源(提取书耽详情书号(event, 命令文本))
    return 生成书耽下载回复流(event, 来源, 配置) if 来源 else None


async def 搜索书耽小说(关键词: str, 数量上限: int = 15) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    上限 = min(15, max(1, int(数量上限)))
    async with _创建书耽会话(1) as 会话:
        列表 = await 书耽客户端(会话).搜索(关键词, 上限)
    结果 = []
    for 书 in 列表:
        if not isinstance(书, dict):
            continue
        编号 = _编号(书.get("book_id"))
        资料 = _书籍资料(书)
        if 编号 and 资料["title"]:
            结果.append({**资料, "book_id": 编号, "platform": "书耽", "url": 书耽来源(编号)})
    if 列表 and not 结果:
        raise 书耽请求错误("invalid_search")
    return 结果[:上限]
