from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import io
import json
import re
import secrets
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

USER_ID = "6226157280"
整本下载UID = "28382828"
整本下载盐值 = "37e81a9d8f02596e1b895d07c171d5c9"
整本下载目录URL = "https://ocean.shuqireader.com/api/bcspub/openapi/book/chapterlist"
整本下载地址URL = "https://ocean.shuqireader.com/api/bcspub/qsandapi/chapter/downurl"
App目录URL = "https://ocean.shuqireader.com/api/bcspub/andapi/book/chapterlist/"
App书评列表URL = "https://ocean.shuqireader.com/api/interact/comment/book/list"
App下载批次URL = "https://ocean.shuqireader.com/api/jspend/api/downloadbatch/index"
App免费下载URL = "https://ocean.shuqireader.com/api/bcspub/andapi/book/freedownurl"
自动VIP搜索词 = ("剑来", "凡人修仙传", "斗破苍穹")
自动VIP回退书 = ("7106468",)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
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
# 自动获取的年费 VIP 用户 ID 缓存：持久化到 MySQL，新 UID 直接替换旧 UID，插件重载不丢失
_VIP用户ID缓存: dict[str, Any] = {}
_VIP用户ID锁: asyncio.Lock | None = None
# 已失效的 UID 集合：只在失效时记录，重新扫描时跳过，避免拿到同一个失效 UID 白重试
_已失效书旗VIPUID: set[str] = set()
书旗VIPUID命名空间 = "shuqi_vip_uid"
书旗VIPUID状态键 = "uid"


def _读取持久化书旗VIPUID(配置: Any) -> str:
    """从 MySQL 读取已保存的年费 VIP UID；未配置或读取失败返回空串。"""
    if not 配置:
        return ""
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态值
        return str(
            读取运行状态值(配置, 书旗VIPUID命名空间, 书旗VIPUID状态键, "") or ""
        ).strip()
    except Exception as exc:
        logger.debug(f"书旗持久化 UID 读取失败：错误类型={type(exc).__name__}")
        return ""


def _保存持久化书旗VIPUID(配置: Any, uid: str) -> None:
    """把新获取的 UID 写入 MySQL 替换旧值；未配置或空值不写。"""
    if not 配置 or not str(uid or "").strip():
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 写入运行状态值
        写入运行状态值(
            配置, 书旗VIPUID命名空间, 书旗VIPUID状态键, str(uid).strip()
        )
    except Exception as exc:
        logger.debug(f"书旗持久化 UID 写入失败：错误类型={type(exc).__name__}")


def _删除持久化书旗VIPUID(配置: Any) -> None:
    """失效时删除 MySQL 里保存的 UID，下次重新获取新的。"""
    if not 配置:
        return
    try:
        from 功能文件.管理功能.基础功能.运行状态数据库 import 删除运行状态值
        删除运行状态值(配置, 书旗VIPUID命名空间, 书旗VIPUID状态键)
    except Exception as exc:
        logger.debug(f"书旗持久化 UID 删除失败：错误类型={type(exc).__name__}")
下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


class ShuqiError(RuntimeError):
    pass


@dataclass
class Chapter:
    index: int
    chapter_id: str
    name: str
    content_url: str
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
    chapters: list[Chapter]
    raw: dict[str, Any]
    is_short: bool = False


def 获取书旗小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[str] | None:
    链接 = 提取书旗链接(命令文本) or 提取事件书旗链接(event)
    if not 链接:
        return None
    return 生成下载回复流(event, 链接, 配置)


async def 生成下载回复流(event: Any, 链接: str, 配置: Any = None) -> AsyncIterator[str]:
    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=60)
        connector = aiohttp.TCPConnector(
            limit=16,
            limit_per_host=16,
            ttl_dns_cache=300,
            keepalive_timeout=30,
        )
        async with aiohttp.ClientSession(
            timeout=timeout, connector=connector
        ) as session:
            最终链接 = await 解析书旗短链(session, 链接)
            目标 = 解析书旗下载目标(最终链接)
            书籍 = await 获取书籍(session, 目标["book_id"], 目标["type"] == "short")
            if not 书籍.chapters:
                raise ShuqiError("没有获取到章节目录")
            if 书籍.chapter_num and len(书籍.chapters) != 书籍.chapter_num:
                raise ShuqiError(
                    f"目录不完整：catalog={len(书籍.chapters)}, total={书籍.chapter_num}"
                )

            logger.info(
                f"书旗小说开始下载：书籍编号={书籍.book_id}, "
                f"书名={书籍.book_name}, 作者={书籍.author_name}, "
                f"章节数={len(书籍.chapters)}, 模式=整本压缩包优先, 回退=VIP批量包"
            )
            yield 格式化下载提示(书籍)

            章节内容 = await 下载全部章节(session, 书籍, 配置)
            成功数 = sum(1 for 项 in 章节内容 if 项.get("content"))
            if 成功数 != len(书籍.chapters):
                raise ShuqiError(
                    f"章节正文不完整：success={成功数}, total={len(书籍.chapters)}"
                )
            文件名, 文件内容 = 生成小说文件内容(书籍, 章节内容)
            logger.info(
                f"书旗小说章节下载完成：书籍编号={书籍.book_id}, "
                f"成功={成功数}, 总数={len(书籍.chapters)}, 文件大小={len(文件内容)}"
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
            启动百度后台上传并清理源文件(
                配置, 发送结果.get("source_cache_path"), 文件名
            )
            return
        降级文本 = str(发送结果.get("fallback_text") or "")
        if 降级文本:
            try:
                yield 降级文本
            finally:
                启动百度后台上传并清理源文件(
                    配置, 发送结果.get("source_cache_path"), 文件名
                )
            return
        logger.warning(
            f"书旗小说完成消息发送失败：书籍编号={书籍.book_id}, "
            f"文件={文件名}, 错误={发送结果.get('error')}"
        )
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(f"书旗小说下载失败：错误={exc}")
        yield "下载失败"


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


async def 获取书籍(
    session: aiohttp.ClientSession, 书籍编号: str, 是否短篇: bool = False
) -> Book:
    时间戳 = str(int(time.time()))
    响应 = await 请求JSON(
        session,
        整本下载目录URL,
        params={
            "platform": "0",
            "user_id": 整本下载UID,
            "bookId": str(书籍编号),
            "timestamp": 时间戳,
            "sign": hashlib.md5(
                f"{书籍编号}{时间戳}{整本下载UID}{整本下载盐值}".encode()
            ).hexdigest(),
        },
    )
    书籍 = 解析目录响应(书籍编号, 响应, 是否短篇)
    try:
        下载地址 = await 获取整本下载地址(session, str(书籍编号), 时间戳)
        书籍.raw["_archive_url"] = re.sub(
            r"try_\d+",
            f"try_{书籍.chapter_num or len(书籍.chapters)}",
            下载地址,
            flags=re.I,
        )
    except Exception as exc:
        logger.warning(
            f"书旗整本下载地址获取失败（不影响 VIP 下载）：书籍={书籍编号}, 错误={exc}"
        )
        书籍.raw["_archive_url"] = ""
    return 书籍


def 解析目录响应(书籍编号: str, 响应: dict[str, Any], 是否短篇: bool = False) -> Book:
    状态 = str(响应.get("state") or 响应.get("status") or "")
    if 状态 and 状态 not in {"200", "0"}:
        raise ShuqiError(f"目录接口异常：state={状态}")
    数据 = 响应.get("data") if isinstance(响应.get("data"), dict) else {}
    if not 数据:
        raise ShuqiError("目录接口 data 为空")
    章节列表: list[Chapter] = []
    for 分卷 in 数据.get("chapterList") or []:
        if not isinstance(分卷, dict):
            continue
        for 项 in 分卷.get("volumeList") or []:
            if not isinstance(项, dict):
                continue
            章节编号 = str(项.get("chapterId") or "").strip()
            if not 章节编号:
                continue
            章节列表.append(
                Chapter(
                    index=len(章节列表) + 1,
                    chapter_id=章节编号,
                    name=清理网页文本(
                        项.get("chapterName") or f"第{len(章节列表) + 1}章"
                    ),
                    content_url="",
                    word_count=安全整数(
                        项.get("wordCount") or 项.get("chapterWordCount"), 0
                    ),
                )
            )

    if not 章节列表:
        raise ShuqiError("目录章节为空")
    目录章节数 = 安全整数(数据.get("chapterNum"), len(章节列表)) or len(章节列表)
    return Book(
        book_id=str(书籍编号),
        book_name=清理网页文本(数据.get("bookName") or f"书旗小说{书籍编号}"),
        author_name=清理网页文本(数据.get("authorName") or "未知") or "未知",
        chapter_num=目录章节数,
        word_count=获取书旗原始字数(数据, 章节列表),
        intro=获取书旗简介(数据),
        status_text=解析书旗状态(数据),
        chapters=章节列表,
        raw=数据,
        is_short=是否短篇,
    )


def m9en(明文: str) -> bytes:
    密钥 = b"20c60107f6363a18"
    随机头 = secrets.token_bytes(4)
    头部 = list(随机头)
    加法表 = 头部 + [
        (头部[0] + 87) & 255,
        (头部[1] + 29) & 255,
        (头部[2] + 171) & 255,
        (头部[3] + 148) & 255,
    ]
    状态 = list(密钥[:8])
    输出 = bytearray(b"m90" + bytes([1]) + 随机头)
    校验 = 0
    明文字节 = str(明文).encode()
    for 索引, 字节 in enumerate(明文字节):
        位置 = 索引 & 7
        if 位置 == 0:
            状态 = [(状态[i] + 密钥[i + 8] + 加法表[i]) & 255 for i in range(8)]
        加密字节 = 字节 ^ 状态[位置]
        输出.append(加密字节)
        校验 ^= 字节
    输出.extend((校验 ^ 状态[0], 校验 ^ 状态[1]))
    return bytes(输出)


def m9de(密文: bytes, 密钥: bytes) -> bytes | None:
    if len(密文) <= 9 or not 密文.startswith(b"m90") or len(密钥) < 16:
        return None
    头部 = list(密文[4:8])
    加法表 = 头部 + [
        (头部[0] + 87) & 255,
        (头部[1] + 29) & 255,
        (头部[2] + 171) & 255,
        (头部[3] + 148) & 255,
    ]
    状态 = list(密钥[:8])
    输出 = bytearray()
    校验 = 0
    for 索引, 字节 in enumerate(密文[8:-2]):
        位置 = 索引 & 7
        if 位置 == 0:
            状态 = [(状态[i] + 密钥[i + 8] + 加法表[i]) & 255 for i in range(8)]
        明文字节 = 字节 ^ 状态[位置]
        输出.append(明文字节)
        校验 ^= 明文字节
    if 密文[-2:] != bytes((校验 ^ 状态[0], 校验 ^ 状态[1])):
        return None
    return bytes(输出)


def m9r(密文: bytes) -> bytes | None:
    if 密文.startswith(b"m90"):
        for 密钥 in (b"aa171021f9438cb2", b"e19237a3a933f7eb"):
            解密结果 = m9de(密文, 密钥)
            if 解密结果 is not None:
                return 解密结果
        return None
    if len(密文) < 2:
        return None
    状态 = (238, 185, 233, 179, 129, 142, 151, 167)
    输出 = bytearray()
    校验 = 0
    for 索引, 字节 in enumerate(密文[:-2]):
        明文字节 = 字节 ^ 状态[索引 & 7]
        输出.append(明文字节)
        校验 ^= 明文字节
    if 密文[-2:] != bytes((校验 ^ 状态[0], 校验 ^ 状态[1])):
        return None
    return bytes(输出)



# ================= 自动获取年费 VIP UID =================

def _获取VIP锁() -> asyncio.Lock:
    global _VIP用户ID锁
    if _VIP用户ID锁 is None:
        _VIP用户ID锁 = asyncio.Lock()
    return _VIP用户ID锁


def 清除书旗VIP用户ID缓存(配置: Any = None, 失效UID: str = "") -> None:
    _VIP用户ID缓存.pop("uid", None)
    _删除持久化书旗VIPUID(配置)
    失效UID = str(失效UID or "").strip()
    if 失效UID:
        # 记录已失效 UID，重新扫描时跳过，确保换到下一个不同的 UID
        _已失效书旗VIPUID.add(失效UID)
        if len(_已失效书旗VIPUID) > 50:
            # 只保留最近 50 个失效 UID，防止集合无限增长
            _已失效书旗VIPUID.pop()


def _构造App公共参数(user_id: str = USER_ID) -> dict[str, str]:
    return {
        "soft_id": "1",
        "user_id": user_id,
        "userId": user_id,
        "ver": SEARCH_VERSION_CODE,
        "subVer": SEARCH_SUB_VERSION,
        "appVer": SEARCH_VERSION_NAME,
        "theme": "day",
        "platform": "0",
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


def _构造App公共参数字符串(user_id: str = USER_ID, platform: str = "an") -> str:
    参数 = _构造App公共参数(user_id)
    参数["platform"] = platform
    return urllib.parse.urlencode(参数)


async def _请求App签名接口(
    session: aiohttp.ClientSession,
    url: str,
    业务参数: dict[str, Any],
    *,
    user_id: str = USER_ID,
    用公共字段: bool = False,
    platform: str = "an",
) -> dict[str, Any]:
    if 用公共字段:
        参数: dict[str, Any] = _构造App公共参数(user_id)
        参数.update({str(k): "" if v is None else str(v) for k, v in 业务参数.items()})
        参数["isTeenMode"] = "0"
    else:
        参数 = {"_public": _构造App公共参数字符串(user_id, platform)}
        参数.update({str(k): "" if v is None else str(v) for k, v in 业务参数.items()})
        参数["isTeenMode"] = "0"
    参数["_reqid"] = _搜索请求ID()
    headers = {
        "User-Agent": SEARCH_USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    async with session.post(url, data=_搜索签名参数(参数), headers=headers) as resp:
        文本 = await resp.text(errors="ignore")
        if resp.status >= 400:
            raise ShuqiError(f"App 接口 HTTP {resp.status}")
    try:
        数据 = json.loads(文本) if 文本 else {}
    except Exception as exc:
        raise ShuqiError("App 接口未返回 JSON") from exc
    if not isinstance(数据, dict):
        raise ShuqiError("App 接口数据格式异常")
    return 数据


async def 获取App目录(
    session: aiohttp.ClientSession,
    书籍编号: str,
    *,
    user_id: str = USER_ID,
) -> dict[str, Any]:
    业务参数 = {
        "bookId": str(书籍编号),
        "timestamp": str(int(time.time() * 1000)),
        "reqEncryptType": "-1",
        "resEncryptType": "-1",
        "placeid": "",
        "apv": SEARCH_VERSION_NAME,
    }
    数据 = await _请求App签名接口(
        session, App目录URL, 业务参数, user_id=user_id, 用公共字段=True
    )
    状态 = str(数据.get("state") or 数据.get("status"))
    if 状态 and 状态 != "200":
        raise ShuqiError(f"App 目录接口异常：state={状态}")
    目录 = 数据.get("data") if isinstance(数据.get("data"), dict) else {}
    if not 目录:
        raise ShuqiError("App 目录接口 data 为空")
    return 目录


def _书评页参数(
    书籍编号: str,
    *,
    author_id: str = "",
    item_index: int = 0,
    size: int = 50,
    sort: int = 1,
) -> dict[str, str]:
    return {
        "userId": USER_ID,
        "authorId": author_id,
        "bookId": str(书籍编号),
        "chapterId": "",
        "paragraphId": "",
        "itemIndex": str(max(0, item_index)),
        "size": str(max(1, size)),
        "sort": str(sort),
        "type": str(sort),
        "filterCommentIds": "",
    }


def 从书评提取年费VIP用户ID(
    评论: list[dict[str, Any]], 跳过UID: set[str] | None = None
) -> str:
    for obj in 评论:
        if not isinstance(obj, dict):
            continue
        vip = obj.get("vipStatus")
        if not isinstance(vip, dict):
            continue
        if 安全整数(vip.get("status"), 0) != 2:
            continue
        if 安全整数(vip.get("annualVipStatus"), 0) != 1:
            continue
        uid = str(obj.get("userId") or obj.get("uid") or "").strip()
        if uid and uid != "0" and (not 跳过UID or uid not in 跳过UID):
            return uid
    return ""


async def 扫描书评获取VIP用户ID(
    session: aiohttp.ClientSession,
    书籍编号: str,
    *,
    author_id: str = "",
    max_pages: int = 3,
    size: int = 50,
    跳过UID: set[str] | None = None,
) -> str:
    if not author_id:
        try:
            目录 = await 获取App目录(session, 书籍编号)
            author_id = str(目录.get("authorId") or "")
        except Exception as exc:
            logger.debug(f"书旗 App 目录获取失败：书籍={书籍编号}, 错误={exc}")
    item_index = 0
    for _页码 in range(max(1, max_pages)):
        业务参数 = _书评页参数(书籍编号, author_id=author_id, item_index=item_index, size=size)
        数据 = await _请求App签名接口(
            session, App书评列表URL, 业务参数, user_id=USER_ID, 用公共字段=True
        )
        状态 = str(数据.get("status") or 数据.get("state"))
        if 状态 and 状态 != "200":
            raise ShuqiError(f"书评接口异常：status={状态}")
        响应数据 = 数据.get("data") if isinstance(数据.get("data"), dict) else {}
        评论 = 响应数据.get("commentList") or []
        uid = 从书评提取年费VIP用户ID(
            评论 if isinstance(评论, list) else [], 跳过UID
        )
        if uid:
            return uid
        next_index = 安全整数(响应数据.get("nextItemIndex"), item_index + size)
        has_more = bool(响应数据.get("hasMore"))
        if not has_more or next_index <= item_index:
            break
        item_index = next_index
    return ""


async def 发现VIP候选书(
    session: aiohttp.ClientSession,
    *,
    max_candidates: int = 8,
) -> list[dict[str, str]]:
    候选: list[dict[str, str]] = []
    已记录: set[str] = set()
    for 词 in 自动VIP搜索词:
        if len(候选) >= max_candidates:
            break
        try:
            书籍列表 = await 搜索小说(session, 词, 需要数量=5)
        except Exception as exc:
            logger.debug(f"书旗 VIP 候选搜索失败：词={词}, 错误={exc}")
            continue
        for 书 in 书籍列表:
            book_id = str(书.get("book_id") or "").strip()
            if not book_id or book_id in 已记录 or len(候选) >= max_candidates:
                continue
            已记录.add(book_id)
            候选.append({"bookId": book_id, "bookName": str(书.get("title") or "")})
    for book_id in 自动VIP回退书:
        if book_id not in 已记录:
            已记录.add(book_id)
            候选.append({"bookId": book_id, "bookName": ""})
    return 候选


async def 自动获取书旗VIP用户ID(session: aiohttp.ClientSession) -> str:
    候选 = await 发现VIP候选书(session)
    for 书 in 候选:
        book_id = 书["bookId"]
        try:
            uid = await 扫描书评获取VIP用户ID(
                session, book_id, 跳过UID=_已失效书旗VIPUID
            )
            if uid:
                logger.info(
                    f"书旗自动获取年费 VIP UID 成功：书籍={book_id}, "
                    f"书名={书.get('bookName') or ''}, UID尾号={uid[-4:] if len(uid) > 4 else uid}"
                )
                return uid
        except Exception as exc:
            logger.debug(f"书旗书评扫描失败：书籍={book_id}, 错误={exc}")
    raise ShuqiError("自动扫描候选书后未找到年费 VIP UID")


async def 获取书旗VIP用户ID(
    session: aiohttp.ClientSession, 配置: Any = None
) -> str:
    uid = str(_VIP用户ID缓存.get("uid") or "").strip()
    if uid:
        return uid
    async with _获取VIP锁():
        uid = str(_VIP用户ID缓存.get("uid") or "").strip()
        if uid:
            return uid
        uid = _读取持久化书旗VIPUID(配置)
        if uid:
            _VIP用户ID缓存["uid"] = uid
            return uid
        uid = await 自动获取书旗VIP用户ID(session)
        if uid:
            _VIP用户ID缓存["uid"] = uid
            _保存持久化书旗VIPUID(配置, uid)
    return uid


# ================= VIP UID 批量下载（downloadbatch + freedownurl） =================

def _批次键(
    user_id: str,
    书籍编号: str,
    first_index: int,
    first_cid: str,
    last_index: int,
    last_cid: str,
) -> str:
    return f"{user_id}_{书籍编号}_{first_index}_{last_index}_{first_cid}_{last_cid}"


def _批次章节索引(书籍: Book, 项: dict[str, Any]) -> tuple[int, int]:
    章节位置 = {章节.chapter_id: 章节.index - 1 for 章节 in 书籍.chapters}
    first_cid = str(项.get("firstChapterId") or (项.get("chapterIds") or [""])[0] or "")
    last_cid = str(项.get("lastChapterId") or (项.get("chapterIds") or [""])[-1] or first_cid)
    first_raw = 项.get("firstChapterIndex")
    last_raw = 项.get("lastChapterIndex")
    if first_raw is not None and last_raw is not None:
        try:
            return int(first_raw), int(last_raw)
        except (TypeError, ValueError):
            pass
    if first_cid in 章节位置 and last_cid in 章节位置:
        return 章节位置[first_cid], 章节位置[last_cid]
    数量 = 安全整数(项.get("chapterCount") or len(项.get("chapterIds") or []), 1)
    return 0, max(0, 数量 - 1)


async def 获取下载批次(
    session: aiohttp.ClientSession,
    书籍: Book,
    *,
    user_id: str,
) -> list[dict[str, Any]]:
    业务参数 = {
        "userId": user_id,
        "bookId": 书籍.book_id,
        "timestamp": str(int(time.time())),
        "platform": "an",
    }
    数据 = await _请求App签名接口(
        session, App下载批次URL, 业务参数, user_id=user_id, 用公共字段=False
    )
    状态 = str(数据.get("state") or 数据.get("status"))
    if 状态 and 状态 != "200":
        raise ShuqiError(f"下载批次接口异常：state={状态}")
    响应数据 = 数据.get("data") if isinstance(数据.get("data"), dict) else {}
    批次信息 = 响应数据.get("batchInfo") if isinstance(响应数据.get("batchInfo"), dict) else {}
    免费批次 = 批次信息.get("freeInfo") or []
    return [项 for 项 in 免费批次 if isinstance(项, dict)]


async def 获取批次下载地址(
    session: aiohttp.ClientSession,
    书籍: Book,
    批次列表: list[dict[str, Any]],
    *,
    user_id: str,
) -> list[dict[str, Any]]:
    if not 批次列表:
        return []
    批次章节: dict[str, dict[str, str]] = {}
    键映射: dict[str, dict[str, Any]] = {}
    for 项 in 批次列表:
        first_index, last_index = _批次章节索引(书籍, 项)
        first_cid = str(项.get("firstChapterId") or (项.get("chapterIds") or [""])[0] or "")
        last_cid = str(项.get("lastChapterId") or (项.get("chapterIds") or [""])[-1] or first_cid)
        key = _批次键(user_id, 书籍.book_id, first_index, first_cid, last_index, last_cid)
        批次章节[key] = {"startCid": first_cid, "endCid": last_cid}
        键映射[key] = 项
        项["_batch_key"] = key
    业务参数 = {
        "bookId": 书籍.book_id,
        "timestamp": str(int(time.time())),
        "type": "4",
        "batchDown": "1",
        "batchChapterIds": json.dumps(批次章节, ensure_ascii=False, separators=(",", ":")),
        "user_id": user_id,
        "newDownload": "1",
        "platform": "an",
        "reqEncryptType": "-1",
        "reqEncryptParam": "",
        "resEncryptType": "-1",
    }
    数据 = await _请求App签名接口(
        session, App免费下载URL, 业务参数, user_id=user_id, 用公共字段=False
    )
    状态 = str(数据.get("state") or 数据.get("status"))
    if 状态 and 状态 != "200":
        raise ShuqiError(f"批量下载 URL 接口异常：state={状态}")
    响应数据 = 数据.get("data") or {}
    if isinstance(响应数据, str):
        try:
            响应数据 = json.loads(响应数据)
        except Exception:
            响应数据 = {}
    if not isinstance(响应数据, dict):
        响应数据 = {}
    for key, 项 in 键映射.items():
        info = 响应数据.get(key)
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except Exception:
                info = {}
        if not isinstance(info, dict):
            continue
        项["url"] = str(info.get("url") or "")
        项["downloadUnlocked"] = bool(info.get("downloadUnlocked"))
    return 批次列表


def 解析书旗压缩包分段(压缩包: bytes) -> dict[str, str]:
    内容按章节: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(压缩包)) as 压缩文件:
            for 信息 in 压缩文件.infolist():
                if not re.fullmatch(r"\d+\.sqc", 信息.filename, flags=re.I):
                    continue
                原文 = 压缩文件.read(信息)
                # downloadbatch 链路的 sqc 使用 XOR 0x36 解密（整本包链路使用 0x38）
                解密正文 = bytes(字节 ^ 0x36 for 字节 in 原文)
                正文 = 解密正文.decode("utf-8", errors="ignore")
                正文 = 正文.replace("<br/>", "\n")
                正文 = html.unescape(正文).replace("\r\n", "\n").replace("\r", "\n")
                正文 = "\n".join(
                    行.lstrip(" \u3000") for 行 in 正文.split("\n")
                ).strip()
                if 正文:
                    内容按章节[信息.filename[:-4]] = 正文
    except zipfile.BadZipFile as exc:
        raise ShuqiError("整本下载包格式异常") from exc
    return 内容按章节


async def 下载全部章节VIP(
    session: aiohttp.ClientSession,
    书籍: Book,
    *,
    user_id: str,
) -> list[dict[str, str]]:
    总数 = len(书籍.chapters)
    if not 总数:
        return []
    批次列表 = await 获取下载批次(session, 书籍, user_id=user_id)
    if not 批次列表:
        raise ShuqiError("下载批次为空")
    批次列表 = await 获取批次下载地址(session, 书籍, 批次列表, user_id=user_id)
    已解锁 = [项 for 项 in 批次列表 if 项.get("downloadUnlocked") and str(项.get("url") or "").strip()]
    if not 已解锁:
        raise ShuqiError("VIP 用户未解锁下载 URL，UID 可能失效")
    logger.info(
        f"书旗小说章节进度：书籍编号={书籍.book_id}, 进度=0/{总数}, "
        f"百分比=0%, 模式=VIP批量包, 批次={len(已解锁)}, UID尾号={user_id[-4:] if len(user_id) > 4 else user_id}"
    )
    内容按章节: dict[str, str] = {}

    async def 下载并解析一个批次(项: dict[str, Any]) -> None:
        url = str(项.get("url") or "").strip()
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
        async with session.get(url, headers=headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                raise ShuqiError(f"批次包 HTTP {resp.status}")
            压缩包 = await resp.read()
        分段 = await asyncio.to_thread(解析书旗压缩包分段, 压缩包)
        内容按章节.update(分段)

    并发上限 = 8
    for 起始 in range(0, len(已解锁), 并发上限):
        一组 = 已解锁[起始 : 起始 + 并发上限]
        await asyncio.gather(*(下载并解析一个批次(项) for 项 in 一组))
        已完成 = 起始 + len(一组)
        if 已完成 >= 总数 or (已完成 * 10) // 总数 > ((起始) * 10) // 总数:
            logger.info(
                f"书旗小说章节进度：书籍编号={书籍.book_id}, 进度={已完成}/{总数}, "
                f"百分比={已完成 * 100 // 总数}%, 模式=VIP批量包"
            )
    结果: list[dict[str, str]] = []
    缺失章节: list[str] = []
    for 章节 in 书籍.chapters:
        正文 = 内容按章节.get(章节.chapter_id, "")
        if not 正文:
            缺失章节.append(章节.chapter_id)
        结果.append({"id": 章节.chapter_id, "title": 章节.name, "content": 正文})
    if 缺失章节:
        raise ShuqiError(f"VIP 批量包缺少章节：missing={len(缺失章节)}")
    return 结果


async def _尝试整本下载(
    session: aiohttp.ClientSession, 书籍: Book
) -> list[dict[str, str]] | None:
    """优先尝试整本压缩包（固定 UID 通道）；地址缺失/下载失败返回 None 走 VIP 兜底。"""
    下载地址 = str(书籍.raw.get("_archive_url") or "").strip()
    if not 下载地址:
        # 整本地址可能在获取书籍时瞬时失败，这里重试一次自愈
        try:
            时间戳 = str(int(time.time()))
            重试地址 = await 获取整本下载地址(session, 书籍.book_id, 时间戳)
            if 重试地址:
                书籍.raw["_archive_url"] = re.sub(
                    r"try_d+",
                    f"try_{书籍.chapter_num or len(书籍.chapters)}",
                    重试地址,
                    flags=re.I,
                )
                下载地址 = str(书籍.raw.get("_archive_url") or "").strip()
        except Exception as exc:
            logger.debug(f"书旗整本下载地址重试失败：书籍={书籍.book_id}, 错误={exc}")
    if not 下载地址:
        return None
    try:
        return await 下载全部章节整本包(session, 书籍)
    except Exception as exc:
        logger.warning(f"书旗整本下载失败，回退 VIP 批量包：书籍={书籍.book_id}, 错误={exc}")
        return None


async def 下载全部章节(
    session: aiohttp.ClientSession, 书籍: Book, 配置: Any = None
) -> list[dict[str, str]]:
    总数 = len(书籍.chapters)
    if not 总数:
        return []
    # 整本压缩包优先：固定 UID 通道稳定，多数书可直接成功，避免每次下载都先触发书评借 UID 与换新
    整本结果 = await _尝试整本下载(session, 书籍)
    if 整本结果:
        return 整本结果
    # 整本不可用（地址缺失/缺章）时回退 VIP 批量包；未解锁不清缓存（书级无权限，非 UID 失效）
    try:
        uid = await 获取书旗VIP用户ID(session, 配置)
    except Exception as exc:
        logger.warning(f"书旗自动获取 VIP UID 失败：错误={exc}")
        return []
    try:
        return await 下载全部章节VIP(session, 书籍, user_id=uid)
    except ShuqiError as exc:
        信息 = str(exc)
        if "未解锁" in 信息:
            logger.warning(f"书旗 VIP 未解锁本书：书籍={书籍.book_id}, 错误={exc}")
            return []
        if "失效" in 信息:
            清除书旗VIP用户ID缓存(配置, uid)
            logger.warning(f"书旗 VIP UID 失效，清除缓存后重试一次：错误={exc}")
            try:
                uid = await 获取书旗VIP用户ID(session, 配置)
                return await 下载全部章节VIP(session, 书籍, user_id=uid)
            except Exception as 重试异常:
                logger.warning(f"书旗 VIP 重试仍失败：错误={重试异常}")
                return []
        logger.warning(f"书旗 VIP 批量下载失败：错误={exc}")
        return []
    except Exception as exc:
        logger.warning(f"书旗 VIP 批量下载异常：错误={exc}")
        return []


async def 下载全部章节整本包(
    session: aiohttp.ClientSession, 书籍: Book
) -> list[dict[str, str]]:
    总数 = len(书籍.chapters)
    下载地址 = str(书籍.raw.get("_archive_url") or "").strip()
    if not 总数 or not 下载地址:
        return []
    logger.info(
        f"书旗小说章节进度：书籍编号={书籍.book_id}, 进度=0/{总数}, "
        "百分比=0%, 模式=整本压缩包, 请求次数=1"
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
    }
    try:
        async with session.get(下载地址, headers=headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                raise ShuqiError(f"整本下载 HTTP {resp.status}")
            压缩包 = await resp.read()
    except ShuqiError:
        raise
    except Exception as exc:
        raise ShuqiError("整本下载请求失败") from exc

    章节内容 = await asyncio.to_thread(解析书旗压缩包, 压缩包, 书籍)
    logger.info(
        f"书旗小说章节进度：书籍编号={书籍.book_id}, 进度={总数}/{总数}, "
        f"百分比=100%, 成功={总数}, 失败=0"
    )
    return 章节内容


async def 获取整本下载地址(
    session: aiohttp.ClientSession,
    书籍编号: str,
    时间戳: str,
) -> str:
    uid = 整本下载UID
    参数 = {
        "bookId": base64.b64encode(m9en(书籍编号)).decode(),
        "timestamp": 时间戳,
        "sign": hashlib.md5(
            f"{书籍编号}{时间戳}1{uid}{整本下载盐值}".encode()
        ).hexdigest(),
        "user_id": base64.b64encode(m9en(uid)).decode(),
        "type": "1",
        "reqEncryptType": "1",
        "reqEncryptParam": "bookId:user_id",
        "resEncryptType": "1",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; U; Android 12; zh-CN) AppleWebKit/537.36 UCBrowser/18.10.2.1528 Mobile Safari/537.36",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with session.post(整本下载地址URL, data=参数, headers=headers) as resp:
        if resp.status >= 400:
            raise ShuqiError(f"整本下载地址 HTTP {resp.status}")
        响应 = await resp.read()
    解密结果 = m9r(响应)
    if 解密结果 is None:
        raise ShuqiError("整本下载地址解密失败")
    try:
        数据 = json.loads(解密结果.decode("utf-8"))
    except Exception as exc:
        raise ShuqiError("整本下载地址格式异常") from exc
    下载地址 = str((数据.get("data") or {}).get("url") or "").strip()
    if not 下载地址:
        raise ShuqiError("整本下载地址为空")
    return 下载地址


def 解析书旗压缩包(压缩包: bytes, 书籍: Book) -> list[dict[str, str]]:
    内容按章节: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(压缩包)) as 压缩文件:
            for 信息 in 压缩文件.infolist():
                if not re.fullmatch(r"\d+\.sqc", 信息.filename, flags=re.I):
                    continue
                原文 = 压缩文件.read(信息)
                解密正文 = bytes(字节 ^ 0x38 for 字节 in 原文)
                正文 = 解密正文.decode("utf-8", errors="ignore")
                正文 = 正文.replace("<br/>", "\n")
                正文 = html.unescape(正文).replace("\r\n", "\n").replace("\r", "\n")
                正文 = "\n".join(
                    行.lstrip(" \u3000") for 行 in 正文.split("\n")
                ).strip()
                if 正文:
                    内容按章节[信息.filename[:-4]] = 正文
    except zipfile.BadZipFile as exc:
        raise ShuqiError("整本下载包格式异常") from exc

    结果: list[dict[str, str]] = []
    缺失章节: list[str] = []
    for 章节 in 书籍.chapters:
        正文 = 内容按章节.get(章节.chapter_id, "")
        if not 正文:
            缺失章节.append(章节.chapter_id)
        结果.append({"id": 章节.chapter_id, "title": 章节.name, "content": 正文})
    if 缺失章节:
        raise ShuqiError(f"整本下载包缺少章节：missing={len(缺失章节)}")
    return 结果


async def 请求JSON(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "identity",
    }
    async with session.get(url, params=params, headers=headers) as resp:
        文本 = await resp.text(errors="ignore")
        if resp.status >= 400:
            raise ShuqiError(f"HTTP {resp.status}")
    try:
        数据 = json.loads(文本) if 文本 else {}
    except Exception as exc:
        raise ShuqiError("接口未返回 JSON") from exc
    return 数据 if isinstance(数据, dict) else {}


def 生成小说文件内容(书籍: Book, 章节内容: list[dict[str, str]]) -> tuple[str, bytes]:
    文件名 = 生成小说文件名(书籍)
    内容列表 = [
        文件声明,
        "",
        f"名称：{书籍.book_name}",
        f"作者：{书籍.author_name or '未知'}",
        f"状态：{获取状态文本(书籍)}",
        f"字数：{格式化字数(书籍.word_count)}",
        f"书籍ID：{书籍.book_id}",
        f"章节数：{len(书籍.chapters)}",
        "",
    ]
    if 书籍.intro:
        内容列表.extend(["简介：", 书籍.intro, ""])
    for 章节 in 章节内容:
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
    return 文件名, "\r\n".join(内容列表).encode("utf-8")


def 生成小说文件名(书籍: Book) -> str:
    标题 = 清理文件名(书籍.book_name or f"书旗小说{书籍.book_id}")
    作者 = 清理文件名(书籍.author_name or "未知")
    return f"[{获取状态文本(书籍)}]书名：{标题} 作者：{作者}.txt"


def 格式化下载提示(书籍: Book) -> str:
    return "\n".join(
        [
            f"书名：{书籍.book_name or '未知'}",
            f"作者：{书籍.author_name or '未知'}",
            f"状态：{获取状态文本(书籍)}",
            f"章节：{len(书籍.chapters)} 章",
            f"字数：{格式化字数(书籍.word_count)}",
            "",
            "正在下载中请稍等.....",
        ]
    )


def 获取状态文本(书籍: Book) -> str:
    return 书籍.status_text or "连载"


def 获取书旗原始字数(数据: dict[str, Any], 章节列表: list[Chapter]) -> int:
    for 字段名 in ("realTimeWordCount", "wordCount", "words", "totalWordCount"):
        字数 = 安全整数(数据.get(字段名), 0)
        if 字数 > 0:
            return 字数
    return sum(章节.word_count for 章节 in 章节列表)


def 获取书旗简介(数据: dict[str, Any]) -> str:
    for 字段名 in ("intro", "desc", "description", "bookDesc", "summary"):
        简介 = 清理网页文本(数据.get(字段名))
        if 简介:
            return 简介
    return ""


def 解析书旗状态(数据: dict[str, Any]) -> str:
    for 字段名 in ("statusText", "statusName", "bookStatus", "updateStatus"):
        文本 = 清理网页文本(数据.get(字段名))
        if "完结" in 文本 or "已完" in 文本:
            return "完结"
        if "连载" in 文本 or "更新" in 文本:
            return "连载"
    状态值 = str(数据.get("state") or 数据.get("updateType") or "").strip()
    return "完结" if 状态值 == "2" else "连载"


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
        删除下载缓存文件(缓存路径)
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
            删除下载缓存文件(缓存路径)
            return {
                "sent": False,
                "fallback_text": "",
                "source_cache_path": None,
                "error": str(网盘结果.get("error") or "小说网盘未启用"),
            }
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event,
            书名,
            作者,
            str(网盘结果.get("share_url") or ""),
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
        删除下载缓存文件(缓存路径)
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
        删除下载缓存文件(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(exc),
        }


def 启动百度后台上传并清理源文件(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    if not 源缓存路径:
        return

    async def 执行上传并清理() -> None:
        try:
            if 百度网盘 is not None:
                百度结果 = await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
                if 百度结果.get("success"):
                    logger.info(f"书旗小说百度网盘后台上传成功：文件={文件名}")
                elif 百度结果.get("skipped"):
                    logger.info(
                        f"书旗小说百度网盘后台上传按状态规则跳过：文件={文件名}"
                    )
                elif 百度结果.get("enabled"):
                    logger.warning(
                        f"书旗小说百度网盘后台上传失败，不影响主分享：文件={文件名}, 错误={百度结果.get('error')}"
                    )
        except Exception as exc:
            logger.warning(
                f"书旗小说百度网盘后台上传异常，不影响主分享：文件={文件名}, 错误={exc}"
            )
        finally:
            删除下载缓存文件(源缓存路径)

    try:
        asyncio.create_task(执行上传并清理())
    except RuntimeError:
        删除下载缓存文件(源缓存路径)


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(缓存路径)
    return 缓存路径


def 删除下载缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    if not 小说缓存工具.删除下载缓存文件(缓存路径):
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
    缓存路径 = 下载缓存目录 / 安全文件名
    if not 缓存路径.exists():
        return 缓存路径
    for 序号 in range(1, 1000):
        候选路径 = 下载缓存目录 / f"{缓存路径.stem}_{序号}{缓存路径.suffix}"
        if not 候选路径.exists():
            return 候选路径
    raise RuntimeError("下载缓存目录中同名文件过多")


def 解析书旗下载目标(链接: str) -> dict[str, str]:
    文本 = str(链接 or "").strip()
    书籍编号 = 提取书籍编号(文本)
    if not 书籍编号:
        raise ShuqiError("没有识别到书旗 bookId")
    类型 = "short" if re.search(r"/shortNovel/reader/\d+", 文本, re.I) else "book"
    return {"book_id": 书籍编号, "type": 类型}


async def 解析书旗短链(session: aiohttp.ClientSession, 链接: str) -> str:
    文本 = str(链接 or "").strip()
    if not re.search(r"https?://d\.shuqi\.com/[^\s'\"<>，。]+", 文本, re.I):
        return 文本
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*",
    }
    for 方法 in ("HEAD", "GET"):
        try:
            async with session.request(
                方法, 文本, headers=headers, allow_redirects=True
            ) as resp:
                最终链接 = str(resp.url)
                if 提取书籍编号(最终链接):
                    return 最终链接
                if 方法 == "GET":
                    页面链接 = 提取书旗链接(await resp.text(errors="ignore"))
                    if 提取书籍编号(页面链接):
                        return 页面链接
        except Exception as exc:
            logger.debug(f"书旗短链解析重试：方法={方法}, 错误={exc}")
    raise ShuqiError("书旗短链解析失败")


def 提取事件书旗链接(event: Any) -> str:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            链接 = 提取书旗链接(读取字段(对象, 字段名))
            if 链接:
                return 链接
    return ""


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
    模式列表 = (
        r"https?://d\.shuqi\.com/[^\s'\"<>，。]*",
        r"https?://(?:www\.)?shuqi\.com/book/\d+\.html[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/book/\d+/?[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/(?:catalog|cover)/\d+/?[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/shortNovel/reader/\d+/?[^\s'\"<>，。]*",
        r"https?://t\.shuqi\.com/v2/query/\d+(?:/\d+)?/?[^\s'\"<>，。]*",
    )
    for 模式 in 模式列表:
        匹配 = re.search(模式, 文本, flags=re.I)
        if 匹配:
            return 匹配.group(0)
    return ""


def 提取书籍编号(文本: str) -> str:
    文本 = str(文本 or "").strip()
    for 模式 in (
        r"/catalog/(\d+)/?",
        r"/cover/(\d+)/?",
        r"/shortNovel/reader/(\d+)/?",
        r"/v2/query/(\d+)",
        r"/book/(\d+)",
        r"[?&](?:bid|bookId)=(\d+)",
    ):
        匹配 = re.search(模式, 文本, flags=re.I)
        if 匹配:
            return 匹配.group(1)
    return 文本 if re.fullmatch(r"\d{4,20}", 文本) else ""


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
