from __future__ import annotations

import asyncio
import gzip
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, AsyncIterator, Iterable
from urllib.parse import urlsplit

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
外部提取地址 = "http://154.12.91.167:17324/extract"
章节详情地址模板 = "https://api.zhihu.com/km-indep-home/manuscript/{}/{}/header"
目录地址模板 = "https://api.zhihu.com/km-indep-home/catalog/{}"
请求超时秒数 = 20
正文重试次数 = 3
盐言正文最大并发数 = 16
# 每个正文下载流程包含 0% 起始行，因此最多再输出 4 个进度节点。
进度日志分段数 = 4
目录最大章节数 = 10000
目录页大小 = 50
盐言网页请求头 = {
    "Accept": "application/json,text/plain,*/*",
    "Accept-Encoding": "identity",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://story.zhihu.com/",
}


class _盐言目录接口异常(RuntimeError):
    pass


下载缓存目录 = 小说缓存工具.下载缓存目录
文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。"
    "如喜欢本书，请支持正版。"
)
链接正则 = re.compile(
    r"https?://story\.zhihu\.com/manuscript/paid_column/\d{8,30}/\d{8,30}(?:\?[^\s'\"<>，。；;！!]*)?",
    re.I,
)
允许主机 = {"story.zhihu.com"}
正文键 = {
    "content",
    "body",
    "html",
    "text",
    "markdown",
    "richtext",
    "rich_text",
    "answercontent",
    "answer_content",
    "articlecontent",
    "article_content",
    "paidcontent",
    "paid_content",
    "正文",
    "内容",
    "文章内容",
    "回答内容",
}
标题键 = {
    "title",
    "name",
    "questiontitle",
    "question_title",
    "articletitle",
    "article_title",
    "contenttitle",
    "content_title",
    "booktitle",
    "book_title",
    "columntitle",
    "column_title",
    "标题",
    "名称",
    "问题标题",
    "文章标题",
}
class _正文HTML解析器(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.片段: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {
            "br",
            "p",
            "div",
            "section",
            "article",
            "li",
            "blockquote",
            "h1",
            "h2",
            "h3",
            "h4",
        }:
            self.片段.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {
            "p",
            "div",
            "section",
            "article",
            "li",
            "blockquote",
            "h1",
            "h2",
            "h3",
            "h4",
        }:
            self.片段.append("\n")

    def handle_data(self, data: str) -> None:
        self.片段.append(data)


def _规范键(值: Any) -> str:
    return re.sub(r"[\s_\-]", "", str(值 or "").strip().lower())


def _展开JSON文本(值: Any) -> Any:
    if not isinstance(值, str):
        return 值
    文本 = 值.strip()
    if 文本[:1] not in {"{", "["}:
        return 值
    try:
        return json.loads(文本)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 值


def 清理正文(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, (dict, list, tuple)):
        return _内容值转文本(值)
    文本 = html.unescape(str(值)).replace("\\r\\n", "\n").replace("\\n", "\n")
    文本 = re.sub(
        r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<title[\s\S]*?</title>",
        "",
        文本,
        flags=re.I,
    )
    if "<" in 文本 and ">" in 文本:
        解析器 = _正文HTML解析器()
        try:
            解析器.feed(文本)
            文本 = "".join(解析器.片段)
        except Exception:
            文本 = re.sub(r"<[^>]+>", "", 文本)
    文本 = html.unescape(文本).replace("\u200b", "").replace("\ufeff", "")
    行列表: list[str] = []
    for 行 in 文本.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        行 = re.sub(r"[ \t\u3000]+", " ", 行).strip()
        if 行列表 and not 行 and not 行列表[-1]:
            continue
        行列表.append(行)
    return "\n".join(行列表).strip()


def _内容值转文本(值: Any, 深度: int = 0) -> str:
    if 深度 > 12 or 值 is None:
        return ""
    值 = _展开JSON文本(值)
    if isinstance(值, str):
        return 清理正文(值)
    if isinstance(值, (list, tuple)):
        部分 = [_内容值转文本(项目, 深度 + 1) for 项目 in 值]
        return "\n\n".join(项目 for 项目 in 部分 if 项目).strip()
    if isinstance(值, dict):
        for 键 in (
            "text",
            "content",
            "body",
            "html",
            "value",
            "正文",
            "内容",
            "paragraphs",
            "blocks",
            "nodes",
            "children",
        ):
            if 键 in 值:
                文本 = _内容值转文本(值.get(键), 深度 + 1)
                if 文本:
                    return 文本
        子项 = 值.get("children") or 值.get("blocks") or 值.get("nodes")
        if isinstance(子项, (list, tuple)):
            return _内容值转文本(子项, 深度 + 1)
    return ""


def _遍历对象(根: Any, 最大深度: int = 10) -> Iterable[tuple[Any, int]]:
    待处理: list[tuple[Any, int]] = [(根, 0)]
    已访问: set[int] = set()
    while 待处理:
        当前, 深度 = 待处理.pop()
        if 当前 is None or 深度 > 最大深度:
            continue
        if isinstance(当前, (dict, list, tuple)):
            标识 = id(当前)
            if 标识 in 已访问:
                continue
            已访问.add(标识)
        yield 当前, 深度
        当前 = _展开JSON文本(当前)
        if isinstance(当前, dict):
            待处理.extend((值, 深度 + 1) for 值 in 当前.values())
        elif isinstance(当前, (list, tuple)):
            待处理.extend((值, 深度 + 1) for 值 in 当前)


def _字段值(根: Any, 目标键: set[str], *, 最长: bool = False) -> Any:
    目标键 = {_规范键(键) for 键 in 目标键}
    候选: list[Any] = []
    for 当前, _深度 in _遍历对象(根):
        if not isinstance(当前, dict):
            continue
        for 键, 值 in 当前.items():
            if _规范键(键) in 目标键 and 值 not in (None, "", [], {}):
                候选.append(值)
    if not 候选:
        return None
    if 最长:
        return max(候选, key=lambda 项: len(_内容值转文本(项)))
    return 候选[0]


def _解压响应(原始: bytes) -> bytes:
    if 原始.startswith(b"\x1f\x8b"):
        try:
            return gzip.decompress(原始)
        except OSError:
            return 原始
    return 原始


def _解析响应对象(原始: bytes) -> Any:
    原始 = _解压响应(原始)
    文本 = 原始.decode("utf-8", "replace").lstrip("\ufeff\n\r\t ")
    try:
        return json.loads(文本)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 文本


def _解析章节进度(值: Any) -> tuple[int, int]:
    匹配 = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", str(值 or ""))
    if not 匹配:
        return 0, 0
    return int(匹配.group(1)), int(匹配.group(2))


def _章节引用(值: Any) -> str:
    if not isinstance(值, dict):
        return ""
    return str(值.get("id") or "").strip()


def _解析盐言作者(值: Any) -> str:
    if isinstance(值, dict):
        return 清理正文(
            值.get("name")
            or 值.get("nick_name")
            or 值.get("nickname")
            or 值.get("display_name")
            or ""
        )
    if isinstance(值, (list, tuple)):
        for 项目 in 值:
            作者 = _解析盐言作者(项目)
            if 作者:
                return 作者
    return 清理正文(值)


def 解析盐言章节详情(
    原始: bytes | dict[str, Any], 业务编号: str = "", 章节编号: str = ""
) -> dict[str, Any]:
    数据 = _解析响应对象(原始) if isinstance(原始, bytes) else 原始
    if not isinstance(数据, dict):
        raise RuntimeError("盐言章节详情格式错误")
    if 数据.get("error"):
        raise RuntimeError("盐言章节详情返回错误")

    基础 = 数据.get("base") if isinstance(数据.get("base"), dict) else {}
    父级 = 数据.get("parent") if isinstance(数据.get("parent"), dict) else {}
    实际业务编号 = str(基础.get("business_id") or 业务编号 or "").strip()
    实际章节编号 = str(基础.get("id") or 章节编号 or "").strip()
    if 业务编号 and 实际业务编号 and 实际业务编号 != str(业务编号):
        raise RuntimeError("盐言章节详情专栏不匹配")
    if 章节编号 and 实际章节编号 and 实际章节编号 != str(章节编号):
        raise RuntimeError("盐言章节详情章节不匹配")

    当前序号, 声明总数 = _解析章节进度(父级.get("progress"))
    作者 = _解析盐言作者(数据.get("authors"))
    if not 作者:
        作者 = _解析盐言作者(父级.get("authors"))
    下章 = (
        数据.get("next_section") if isinstance(数据.get("next_section"), dict) else {}
    )
    上章 = 数据.get("pre_section") if isinstance(数据.get("pre_section"), dict) else {}
    标题 = 清理正文(数据.get("title") or 基础.get("title") or "")
    专栏标题 = 清理正文(父级.get("title") or "")
    目录信息 = (
        数据.get("catalog_info") if isinstance(数据.get("catalog_info"), dict) else {}
    )
    简介 = 清理正文(
        父级.get("description") or 父级.get("desc") or 目录信息.get("desc") or ""
    )
    return {
        "business_id": 实际业务编号,
        "section_id": 实际章节编号,
        "title": 标题 or f"第{当前序号 or 1}节",
        "column_title": 专栏标题,
        "author": 作者 or "未知",
        "intro": 简介,
        "index": 当前序号,
        "declared_total": 声明总数,
        "next_id": _章节引用(下章),
        "pre_id": _章节引用(上章),
        "is_limit_free": bool(基础.get("is_limit_free")),
    }


async def _请求盐言章节详情(
    session: aiohttp.ClientSession,
    业务编号: str,
    章节编号: str,
) -> dict[str, Any]:
    地址 = 章节详情地址模板.format(业务编号, 章节编号)
    最后异常: Exception | None = None
    for 尝试次数 in range(3):
        try:
            async with session.get(
                地址,
                headers=盐言网页请求头,
            ) as response:
                原始 = await response.read()
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")
                return 解析盐言章节详情(原始, 业务编号, 章节编号)
        except Exception as exc:
            最后异常 = exc
            if 尝试次数 + 1 < 3:
                await asyncio.sleep(0.2 * (尝试次数 + 1))
    raise RuntimeError("盐言章节详情请求失败") from 最后异常


async def _请求盐言目录页(
    session: aiohttp.ClientSession,
    业务编号: str,
    偏移量: int,
) -> dict[str, Any]:
    地址 = 目录地址模板.format(业务编号)
    最后异常: Exception | None = None
    for 尝试次数 in range(3):
        try:
            async with session.get(
                地址,
                params={"limit": 目录页大小, "offset": 偏移量},
                headers=盐言网页请求头,
            ) as response:
                原始 = await response.read()
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")
                数据 = _解析响应对象(原始)
                if not isinstance(数据, dict) or not isinstance(数据.get("data"), list):
                    raise RuntimeError("盐言目录响应格式错误")
                return 数据
        except Exception as exc:
            最后异常 = exc
            if 尝试次数 + 1 < 3:
                await asyncio.sleep(0.25 * (尝试次数 + 1))
    raise _盐言目录接口异常("盐言目录请求失败") from 最后异常


async def _获取盐言目录接口(
    session: aiohttp.ClientSession,
    业务编号: str,
    起始章节编号: str,
) -> dict[str, Any]:
    所有项目: list[dict[str, Any]] = []
    已有章节编号: set[str] = set()
    父级信息: dict[str, Any] = {}
    作者信息: Any = None
    偏移量 = 0
    声明总数 = 0
    页数 = 0

    while True:
        页数 += 1
        if 页数 > (目录最大章节数 // 目录页大小) + 2:
            raise RuntimeError("盐言目录分页数量异常")
        数据 = await _请求盐言目录页(session, 业务编号, 偏移量)
        if not 父级信息 and isinstance(数据.get("parent"), dict):
            父级信息 = 数据["parent"]
        if 作者信息 is None:
            作者信息 = 数据.get("author")
        分页 = 数据.get("paging") if isinstance(数据.get("paging"), dict) else {}
        try:
            声明总数 = int(分页.get("total") or 声明总数 or 0)
        except (TypeError, ValueError):
            声明总数 = 0

        for 项目 in 数据.get("data") or []:
            if not isinstance(项目, dict):
                continue
            章节编号 = str(项目.get("section_id") or "").strip()
            if not 章节编号 or 章节编号 in 已有章节编号:
                continue
            if 项目.get("business_id") and str(项目.get("business_id")) != str(
                业务编号
            ):
                raise RuntimeError("盐言目录专栏不匹配")
            try:
                原始序号 = 项目.get("idx")
                序号 = int(原始序号) + 1 if 原始序号 is not None else 0
            except (TypeError, ValueError):
                序号 = 0
            if 序号 <= 0:
                序号匹配 = re.search(
                    r"(\d+)", str(项目.get("serial_number_text") or "")
                )
                序号 = int(序号匹配.group(1)) if 序号匹配 else len(所有项目) + 1
            所有项目.append(
                {
                    "id": 章节编号,
                    "title": 清理正文(项目.get("title") or "") or f"第{序号}节",
                    "index": 序号,
                    "word_count": 解析字数(项目.get("word_count")),
                    "is_limit_free": bool(项目.get("is_limit_free")),
                }
            )
            已有章节编号.add(章节编号)

        当前偏移 = 分页.get("offset")
        当前限制 = 分页.get("limit")
        try:
            当前偏移 = int(当前偏移) if 当前偏移 is not None else 偏移量
            当前限制 = int(当前限制) if 当前限制 is not None else 目录页大小
        except (TypeError, ValueError):
            当前偏移, 当前限制 = 偏移量, 目录页大小
        if bool(分页.get("is_end")) or not 数据.get("data"):
            break
        下一偏移 = 当前偏移 + max(1, 当前限制)
        if 下一偏移 <= 偏移量:
            raise RuntimeError("盐言目录分页未前进")
        偏移量 = 下一偏移

    if not 所有项目:
        raise RuntimeError("盐言目录为空")
    所有项目.sort(
        key=lambda 项目: (int(项目.get("index") or 0), str(项目.get("id") or ""))
    )
    if 声明总数 and len(所有项目) != 声明总数:
        raise RuntimeError("盐言目录章节数量不完整")
    序号列表 = [int(项目.get("index") or 0) for 项目 in 所有项目]
    if len(set(序号列表)) != len(序号列表) or 序号列表 != list(
        range(1, len(序号列表) + 1)
    ):
        raise RuntimeError("盐言目录章节序号不连续")

    详情作者 = ""
    try:
        详情 = await _请求盐言章节详情(session, 业务编号, 起始章节编号)
        详情作者 = str(详情.get("author") or "")
    except Exception as exc:
        logger.debug(
            f"盐言章节详情补充元数据失败：阶段=header, 错误={type(exc).__name__}"
        )
    作者 = _解析盐言作者(作者信息) or 详情作者 or "未知"
    专栏标题 = 清理正文(父级信息.get("title") or "") or "盐言专栏"
    子标题 = 清理正文(父级信息.get("sub_title") or "")
    简介 = 清理正文(父级信息.get("introduction") or "")
    return {
        "business_id": str(业务编号),
        "chapters": 所有项目,
        "title": 专栏标题,
        "author": 作者,
        "intro": 简介,
        "declared_total": 声明总数 or len(所有项目),
        "word_count": sum(int(项目.get("word_count") or 0) for 项目 in 所有项目),
        "complete": "完结" in 子标题,
        "source": "catalog",
    }


async def 获取盐言目录(
    session: aiohttp.ClientSession,
    业务编号: str,
    起始章节编号: str,
) -> dict[str, Any]:
    try:
        return await _获取盐言目录接口(session, 业务编号, 起始章节编号)
    except _盐言目录接口异常 as exc:
        logger.debug(f"盐言分页目录不可用，回退章节详情链：错误={type(exc).__name__}")
        return await _获取盐言目录头部链(session, 业务编号, 起始章节编号)


async def _获取盐言目录头部链(
    session: aiohttp.ClientSession,
    业务编号: str,
    起始章节编号: str,
) -> dict[str, Any]:
    """沿章节头部的前后指针收集可见目录，支持从任意分享章节开始。"""
    节点: dict[str, dict[str, Any]] = {}
    反向编号: list[str] = []

    async def 加载(章节编号: str) -> dict[str, Any]:
        章节编号 = str(章节编号 or "").strip()
        if not 章节编号:
            raise RuntimeError("盐言目录章节编号为空")
        if 章节编号 not in 节点:
            if len(节点) >= 目录最大章节数:
                raise RuntimeError("盐言目录章节数量异常")
            节点[章节编号] = await _请求盐言章节详情(session, 业务编号, 章节编号)
        return 节点[章节编号]

    起点 = await 加载(起始章节编号)
    当前编号 = 起点.get("pre_id")
    while 当前编号 and 当前编号 not in 节点:
        反向编号.append(当前编号)
        当前编号 = (await 加载(当前编号)).get("pre_id")

    正向编号: list[str] = []
    当前编号 = str(起始章节编号)
    是否循环 = False
    while 当前编号:
        if 当前编号 in 正向编号:
            是否循环 = True
            break
        当前 = await 加载(当前编号)
        正向编号.append(当前编号)
        下一个编号 = str(当前.get("next_id") or "").strip()
        if not 下一个编号:
            break
        if 下一个编号 in 节点:
            是否循环 = True
            break
        当前编号 = 下一个编号

    编号顺序 = list(reversed(反向编号)) + 正向编号
    编号顺序 = list(dict.fromkeys(编号顺序))
    if not 编号顺序:
        raise RuntimeError("盐言目录为空")

    目录节点 = [节点[编号] for 编号 in 编号顺序]
    有效进度 = [节点信息 for 节点信息 in 目录节点 if 节点信息.get("index", 0) > 0]
    if len(有效进度) == len(目录节点):
        进度集合 = [int(节点信息["index"]) for 节点信息 in 有效进度]
        if len(set(进度集合)) != len(进度集合):
            raise RuntimeError("盐言目录章节序号重复")
        进度排序 = sorted(进度集合)
        if 进度排序 != list(range(进度排序[0], 进度排序[-1] + 1)):
            raise RuntimeError("盐言目录章节不连续")
        目录节点.sort(
            key=lambda 项目: (
                int(项目.get("index") or 0),
                str(项目.get("section_id") or ""),
            )
        )

    声明总数 = max(
        (int(项目.get("declared_total") or 0) for 项目 in 目录节点), default=0
    )
    if not 是否循环 and 声明总数 and len(目录节点) < 声明总数:
        raise RuntimeError("盐言目录不完整")

    首节点 = 目录节点[0]
    return {
        "business_id": str(业务编号),
        "chapters": [
            {
                "id": str(项目.get("section_id") or ""),
                "title": str(项目.get("title") or ""),
                "index": int(项目.get("index") or 序号),
            }
            for 序号, 项目 in enumerate(目录节点, 1)
        ],
        "title": str(首节点.get("column_title") or 首节点.get("title") or "盐言专栏"),
        "author": str(首节点.get("author") or "未知"),
        "intro": str(首节点.get("intro") or ""),
        "declared_total": 声明总数,
        "word_count": sum(int(项目.get("word_count") or 0) for 项目 in 目录节点),
        "complete": bool(声明总数 and len(目录节点) >= 声明总数),
        "source": "header_chain",
    }


def 解析字数(值: Any) -> int:
    if isinstance(值, bool):
        return 0
    if isinstance(值, (int, float)):
        return max(0, int(值))
    文本 = 清理正文(值).replace(",", "").replace("，", "")
    if not 文本:
        return 0
    匹配 = re.search(r"(\d+(?:\.\d+)?)\s*(万|千)?", 文本)
    if not 匹配:
        return 0
    数值 = float(匹配.group(1))
    if 匹配.group(2) == "万":
        数值 *= 10000
    elif 匹配.group(2) == "千":
        数值 *= 1000
    return max(0, int(数值))


def 解析盐言章节正文(原始: bytes, 默认标题: str = "") -> dict[str, str]:
    根对象 = _解析响应对象(原始)
    if isinstance(根对象, dict):
        代码 = 根对象.get("code")
        if 代码 not in (None, 0, "0"):
            raise RuntimeError("盐言正文接口返回错误")
    正文值 = _字段值(根对象, 正文键, 最长=True)
    正文 = _内容值转文本(正文值)
    if not 正文 and isinstance(根对象, str):
        正文 = 清理正文(根对象)
    if len(正文) < 2:
        raise RuntimeError("盐言章节正文为空")
    来源标题 = 清理正文(_字段值(根对象, 标题键))
    if 来源标题 in {"链接查阅", "文章详情", "盐言文章"}:
        来源标题 = ""
    标题 = 来源标题 or 清理正文(默认标题) or "盐言章节"
    return {"title": 标题, "content": 正文, "source_title": 来源标题}


def _规范盐言章节标题(值: Any) -> str:
    """用于校验正文来源标题，忽略空白和常见标题分隔符。"""
    文本 = 清理正文(值)
    return re.sub(r"[\s\W_]+", "", 文本, flags=re.UNICODE).lower()


def _盐言章节标题候选(值: Any) -> set[str]:
    标题 = _规范盐言章节标题(值)
    if not 标题:
        return set()
    候选 = {标题}
    去序号 = re.sub(r"^(?:第)?\d+(?:章|节|篇)?", "", 标题)
    if 去序号:
        候选.add(去序号)
    return 候选


def 盐言章节标题一致(期望标题: Any, 来源标题: Any) -> bool:
    """判断提取结果显式标题是否仍指向目录中的同一章节。"""
    期望候选 = _盐言章节标题候选(期望标题)
    来源候选 = _盐言章节标题候选(来源标题)
    return bool(期望候选 and 来源候选 and 期望候选 & 来源候选)


def _校验并固定盐言章节标题(结果: dict[str, str], 章节标题: str) -> dict[str, str]:
    """拒绝标题明确错配的正文，并始终使用官方目录标题写入 TXT。"""
    来源标题 = 清理正文(结果.pop("source_title", ""))
    目录标题 = 清理正文(章节标题)
    if 来源标题 and 目录标题 and not 盐言章节标题一致(目录标题, 来源标题):
        raise RuntimeError("盐言章节正文标题不匹配")
    if 目录标题:
        结果["title"] = 目录标题
    return 结果


async def _请求外部提取(
    session: aiohttp.ClientSession, 业务编号: str, 章节编号: str
) -> bytes:
    async with session.get(
        外部提取地址,
        params={"q": 业务编号, "a": 章节编号},
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "mantoubot/yanyan",
            "Connection": "keep-alive",
        },
    ) as response:
        内容 = await response.read()
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
        return 内容


async def _获取单章正文(
    session: aiohttp.ClientSession,
    来源: str,
    业务编号: str,
    章节: dict[str, Any],
) -> dict[str, str]:
    章节编号 = str(章节.get("id") or "").strip()
    章节标题 = str(章节.get("title") or "").strip()
    if not 章节编号:
        raise RuntimeError("盐言章节编号为空")

    最后异常: Exception | None = None
    for 尝试次数 in range(正文重试次数):
        try:
            原始 = await _请求外部提取(session, 业务编号, 章节编号)
            结果 = _校验并固定盐言章节标题(
                解析盐言章节正文(原始, 章节标题),
                章节标题,
            )
            结果["section_id"] = 章节编号
            return 结果
        except Exception as exc:
            最后异常 = exc
            logger.debug(
                f"盐言章节提取失败：章节编号={章节编号}, "
                f"轮次={尝试次数 + 1}/{正文重试次数}, 错误={type(exc).__name__}"
            )
            if 尝试次数 + 1 < 正文重试次数:
                await asyncio.sleep(min(1.5, 0.25 * (尝试次数 + 1)))

    raise RuntimeError("盐言章节正文获取失败") from 最后异常


async def 下载盐言全部章节(
    session: aiohttp.ClientSession,
    来源: str,
    业务编号: str,
    目录: list[dict[str, Any]],
) -> list[dict[str, str]]:
    总数 = len(目录)
    if not 总数:
        raise RuntimeError("盐言目录为空")
    动态并发数 = max(1, min(盐言正文最大并发数, 总数))
    结果列表: list[dict[str, str] | None] = [None] * 总数
    待重试 = set(range(总数))
    # 0% 起始行已经记录了第 0 桶，避免首章再额外输出一条 0% 进度。
    上次进度桶 = 0
    logger.info(
        f"盐言小说章节进度：业务编号={业务编号}, 进度=0/{总数}, "
        f"百分比=0%, 并发数={动态并发数}, 重试次数={正文重试次数}"
    )

    async def 记录进度(轮次: int) -> None:
        nonlocal 上次进度桶
        成功数 = sum(项目 is not None for 项目 in 结果列表)
        失败数 = len(待重试)
        进度桶 = int(成功数 * 进度日志分段数 / 总数)
        if 成功数 >= 总数:
            进度桶 = 进度日志分段数
        if 进度桶 <= 上次进度桶 and 成功数 < 总数:
            return
        上次进度桶 = 进度桶
        百分比 = int(成功数 * 100 / 总数)
        logger.info(
            f"盐言小说章节进度：业务编号={业务编号}, 进度={成功数}/{总数}, "
            f"百分比={百分比}%, 成功={成功数}, 失败={失败数}, 轮次={轮次}"
        )

    for 轮次 in range(1, 正文重试次数 + 1):
        if not 待重试:
            break
        当前待处理 = sorted(待重试)
        信号量 = asyncio.Semaphore(动态并发数)

        async def 下载任务(序号: int) -> tuple[int, dict[str, str] | None]:
            async with 信号量:
                try:
                    return 序号, await _获取单章正文(
                        session, 来源, 业务编号, 目录[序号]
                    )
                except Exception as exc:
                    logger.debug(
                        f"盐言章节下载失败：章节编号={目录[序号].get('id')}, "
                        f"轮次={轮次}, 错误={type(exc).__name__}"
                    )
                    return 序号, None

        任务列表 = [asyncio.create_task(下载任务(序号)) for 序号 in 当前待处理]
        for 任务 in asyncio.as_completed(任务列表):
            序号, 结果 = await 任务
            if 结果:
                结果列表[序号] = 结果
                待重试.discard(序号)
            await 记录进度(轮次)

        if 待重试 and 轮次 < 正文重试次数:
            logger.debug(
                f"盐言小说失败章节重试：业务编号={业务编号}, "
                f"轮次={轮次 + 1}, 数量={len(待重试)}"
            )
            await asyncio.sleep(0.4)

    if 待重试:
        await 记录进度(正文重试次数)
        raise RuntimeError(f"盐言章节正文不完整：missing={len(待重试)}")
    await 记录进度(正文重试次数)
    return [项目 for 项目 in 结果列表 if 项目 is not None]


async def _准备盐言分享章节书籍(
    session: aiohttp.ClientSession, 来源: str
) -> dict[str, Any]:
    业务编号, 起始章节编号 = 解析盐言编号(来源)
    if not 业务编号 or not 起始章节编号:
        raise RuntimeError("盐言链接参数不完整")
    详情 = await _请求盐言章节详情(session, 业务编号, 起始章节编号)
    分享章节标题 = 清理正文(详情.get("title")) or "盐言章节"
    return {
        "title": 分享章节标题,
        "author": 详情.get("author") or "未知",
        "intro": 详情.get("intro") or "",
        "status": "完结",
        "word_count": 0,
        "chapters": [{"id": 起始章节编号, "title": 分享章节标题}],
        "column_id": 业务编号,
        "section_id": 起始章节编号,
        "declared_total": 1,
        "catalog_source": "share_section",
    }


async def _下载盐言分享章节(
    session: aiohttp.ClientSession,
    来源: str,
    书籍: dict[str, Any],
) -> dict[str, Any]:
    章节目录 = list(书籍.get("chapters") or [])
    if len(章节目录) != 1:
        raise RuntimeError("盐言分享章节数量异常")
    章节 = await _获取单章正文(
        session,
        来源,
        str(书籍.get("column_id") or ""),
        章节目录[0],
    )
    if not str(章节.get("content") or "").strip():
        raise RuntimeError("盐言分享章节正文为空")
    书籍["title"] = str(章节.get("title") or 书籍.get("title") or "盐言章节")
    书籍["chapters"] = [章节]
    书籍["word_count"] = len(re.sub(r"\s+", "", str(章节.get("content") or "")))
    return 书籍


def _创建盐言会话() -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=请求超时秒数, sock_connect=8, sock_read=15)
    connector = aiohttp.TCPConnector(
        limit=max(8, 盐言正文最大并发数),
        limit_per_host=max(8, 盐言正文最大并发数),
        ttl_dns_cache=300,
    )
    return aiohttp.ClientSession(timeout=timeout, connector=connector)


async def 获取盐言正文(来源: str) -> dict[str, Any]:
    async with _创建盐言会话() as session:
        书籍 = await _准备盐言分享章节书籍(session, 来源)
        return await _下载盐言分享章节(session, 来源, 书籍)


def 获取盐言小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[str] | None:
    来源 = 提取直接盐言来源(命令文本) or 提取事件盐言来源(event)
    if not 来源:
        return None
    return 生成下载回复流(event, 来源, 配置)


async def 生成下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[str]:
    try:
        async with _创建盐言会话() as session:
            书籍 = await _准备盐言分享章节书籍(session, 来源)
            目录 = list(书籍.get("chapters") or [])
            logger.info(
                f"盐言小说开始下载：业务编号={书籍.get('column_id')}, "
                f"书名={书籍.get('title')}, 作者={书籍.get('author')}, "
                f"章节数={len(目录)}, declared_总数={书籍.get('declared_total')}, "
                f"catalog_来源={书籍.get('catalog_source') or 'catalog'}"
            )
            书籍 = await _下载盐言分享章节(session, 来源, 书籍)
            章节 = list(书籍.get("chapters") or [])
            if len(章节) != len(目录) or any(not 项目.get("content") for 项目 in 章节):
                raise RuntimeError("盐言章节正文不完整")
            yield 格式化下载提示(书籍)
            文件名, 文件内容 = 生成小说文件内容(书籍)
            logger.info(
                f"盐言小说章节下载完成：业务编号={书籍.get('column_id')}, "
                f"成功={len(章节)}, 总数={len(目录)}, 字数={书籍.get('word_count')}, "
                f"文件大小={len(文件内容)}"
            )
            发送结果 = await 准备发送文本文件(
                event,
                文件名,
                文件内容,
                配置,
                书名=书籍.get("title"),
                作者=书籍.get("author"),
            )
            源缓存路径 = 发送结果.get("source_cache_path")
            if 发送结果.get("sent"):
                启动百度后台上传并清理(配置, 源缓存路径, 文件名)
                return
            降级文本 = str(发送结果.get("fallback_text") or "")
            if 降级文本:
                try:
                    yield 降级文本
                finally:
                    启动百度后台上传并清理(配置, 源缓存路径, 文件名)
                return
            yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(
            f"盐言小说下载失败：阶段=extract_or_upload, 错误={type(exc).__name__}"
        )
        yield "下载失败 请重试"


def 生成小说文件内容(书籍: dict[str, Any]) -> tuple[str, bytes]:
    书名 = str(书籍.get("title") or "盐言文章").strip()
    作者 = str(书籍.get("author") or "未知").strip()
    章节 = 书籍.get("chapters") or []
    if not 章节 or any(not str(项目.get("content") or "").strip() for 项目 in 章节):
        raise RuntimeError("盐言章节正文不完整")
    行列表 = [
        文件声明,
        "",
        f"名称：{书名}",
        f"作者：{作者}",
        f"状态：{书籍.get('status') or '完结'}",
        f"字数：{格式化字数(书籍.get('word_count'))}",
        f"书籍ID：{书籍.get('column_id') or 书籍.get('question_id') or '未知'}",
        f"章节数：{len(章节)}",
        "",
    ]
    简介 = str(书籍.get("intro") or "").strip()
    if 简介:
        行列表.extend(["简介：", 简介, ""])
    for 序号, 项目 in enumerate(章节, 1):
        标题 = str(项目.get("title") or f"第{序号}节").strip()
        正文 = 去除章节正文重复标题(标题, 项目.get("content"))
        if not 正文:
            continue
        行列表.extend([标题, "", 正文, ""])
    文本 = "\n".join(行列表).replace("\r\n", "\n").replace("\r", "\n")
    return 生成小说文件名(书籍), 文本.replace("\n", "\r\n").encode("utf-8")


def 生成小说文件名(书籍: dict[str, Any]) -> str:
    状态 = "完结" if str(书籍.get("status") or "").find("完") >= 0 else "连载"
    return f"[{状态}]书名：{清理文件名(书籍.get('title') or '盐言文章')} 作者：{清理文件名(书籍.get('author') or '未知')}.txt"


def 格式化下载提示(书籍: dict[str, Any]) -> str:
    行列表 = [
        f"书名：{书籍.get('title') or '未知'}",
        f"作者：{书籍.get('author') or '未知'}",
        f"状态：{书籍.get('status') or '完结'}",
        f"章节：{len(书籍.get('chapters') or [])} 章",
        f"字数：{格式化字数(书籍.get('word_count'))}",
        "",
        "正在下载中请稍等.....",
    ]
    return "\n".join(行列表)


def 格式化字数(值: Any) -> str:
    数值 = 解析字数(值)
    if 数值 <= 0:
        return "未知"
    if 数值 >= 10000:
        万字 = f"{数值 / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{万字}万字"
    return f"{数值}字"


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
            "error": "网盘模块未加载",
        }
    try:
        上传结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not 上传结果.get("success"):
            logger.warning(
                f"盐言小说主网盘上传失败：文件={文件名}, 错误={type(上传结果.get('error')).__name__}"
            )
            删除缓存(缓存路径)
            return {
                "sent": False,
                "fallback_text": "",
                "source_cache_path": None,
                "error": "上传失败",
            }
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(上传结果.get("share_url") or "")
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
                "error": "",
            }
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "发送失败",
        }
    except Exception as exc:
        logger.warning(
            f"盐言小说主网盘上传异常：文件={文件名}, 错误={type(exc).__name__}"
        )
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "上传异常",
        }


def 启动百度后台上传并清理(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    if not 源缓存路径:
        return

    async def _任务() -> None:
        try:
            if 百度网盘 is not None:
                await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
        except Exception as exc:
            logger.warning(
                f"盐言小说百度后台上传异常：文件={文件名}, 错误={type(exc).__name__}"
            )
        finally:
            删除缓存(源缓存路径)

    try:
        asyncio.create_task(_任务())
    except RuntimeError:
        删除缓存(源缓存路径)


def 写入缓存(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    基础名 = Path(清理文件名(文件名)).name or "盐言文章.txt"
    if not 基础名.lower().endswith(".txt"):
        基础名 += ".txt"
    路径 = 下载缓存目录 / 基础名
    for 序号 in range(1000):
        候选 = 路径 if 序号 == 0 else 下载缓存目录 / f"{路径.stem}_{序号}{路径.suffix}"
        if not 候选.exists():
            候选.write_bytes(文件内容)
            小说缓存工具.标记下载缓存正在使用(候选)
            return 候选
    raise RuntimeError("下载缓存文件过多")


def 删除缓存(路径: Any) -> None:
    if not 路径:
        return
    小说缓存工具.删除下载缓存文件(路径)


def 清理文件名(值: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|]+", "_", str(值 or "").strip())
    return 文本[:80] or "盐言文章"


def 解析盐言编号(来源: str) -> tuple[str, str]:
    try:
        路径 = [项目 for 项目 in urlsplit(来源).path.split("/") if 项目]
    except ValueError:
        return "", ""
    if len(路径) >= 3 and 路径[-3].lower() == "paid_column":
        return 路径[-2], 路径[-1]
    匹配 = re.search(r"paid_column/(\d{8,30})/(\d{8,30})", 来源, re.I)
    return (匹配.group(1), 匹配.group(2)) if 匹配 else ("", "")


def _是盐言链接(值: str) -> bool:
    try:
        地址 = urlsplit(值)
    except ValueError:
        return False
    主机 = (地址.hostname or "").lower().strip(".")
    return 主机 in 允许主机 and bool(解析盐言编号(值)[0])


def 提取盐言链接(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, dict):
        for 子值 in 值.values():
            结果 = 提取盐言链接(子值)
            if 结果:
                return 结果
        return ""
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            结果 = 提取盐言链接(子值)
            if 结果:
                return 结果
        return ""
    文本 = html.unescape(str(值)).replace("\\/", "/")
    for 匹配 in 链接正则.finditer(文本):
        链接 = 匹配.group(0).rstrip("`)]}>，。；;！!")
        if _是盐言链接(链接):
            return 链接
    return ""


def 提取直接盐言来源(命令文本: Any) -> str | None:
    链接 = 提取盐言链接(命令文本)
    return 链接 or None


def 提取事件盐言来源(event: Any) -> str | None:
    对象列表 = [event, getattr(event, "message_obj", None)]
    for 对象 in 对象列表:
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message", "raw_data", "data"):
            链接 = 提取盐言链接(
                getattr(对象, 字段名, None)
                if not isinstance(对象, dict)
                else 对象.get(字段名)
            )
            if 链接:
                return 链接
    return None
