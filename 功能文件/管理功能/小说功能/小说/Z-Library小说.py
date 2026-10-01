"""Z-Library 公开书籍链接下载。

当前模块只处理公开书籍详情页和详情页提供的下载文件，不读取或保存
Z-Library 账号、密码、Cookie、浏览器配置和注册资料。下载到的 EPUB、FB2、
HTML、TXT 及可选 PDF 文件统一转换为小说 TXT，再交给小说网盘出口。
"""

from __future__ import annotations

import asyncio
import html
import posixpath
import re
import zipfile
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception:
    小说网盘 = None

from 功能文件.管理功能.基础功能 import 文件缓存 as 文件缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题


ZLibrary允许域名 = {
    "z-library.sk",
    "zh.z-library.sk",
}
ZLibrary链接正则 = re.compile(
    r"https?://(?:zh\.)?z-library\.sk/book/[^\s<>\"']+", re.IGNORECASE
)
ZLibrary请求超时秒数 = 35
ZLibrary详情最大字节数 = 4 * 1024 * 1024
ZLibrary文件最大字节数 = 120 * 1024 * 1024
ZLibrary压缩后最大展开字节数 = 256 * 1024 * 1024
ZLibrary文件声明 = (
    "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。"
    "内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。"
    "如喜欢本书，请支持正版。"
)
ZLibrary下载失败提示 = "下载失败 请重试"
ZLibrary文件发送失败提示 = "文件发送失败，请稍后再试"


class _ZLibrary站点错误(RuntimeError):
    pass


class _ZLibrary正文HTML解析器(HTMLParser):
    """把常见 EPUB XHTML 或网页正文转成段落文本。"""

    _块元素 = {
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "li",
        "p",
        "section",
        "tr",
    }
    _跳过元素 = {"head", "script", "style", "svg", "nav", "aside"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.片段: list[str] = []
        self.跳过深度 = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        小写标签 = tag.lower()
        if 小写标签 in self._跳过元素:
            self.跳过深度 += 1
            return
        if not self.跳过深度 and 小写标签 in self._块元素:
            self.片段.append("\n")

    def handle_endtag(self, tag: str) -> None:
        小写标签 = tag.lower()
        if 小写标签 in self._跳过元素 and self.跳过深度:
            self.跳过深度 -= 1
            return
        if not self.跳过深度 and 小写标签 in self._块元素:
            self.片段.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.跳过深度:
            self.片段.append(data)


def _清理正文(值: Any) -> str:
    if 值 is None:
        return ""
    文本 = html.unescape(str(值)).replace("\r\n", "\n").replace("\r", "\n")
    if "<" in 文本 and ">" in 文本:
        解析器 = _ZLibrary正文HTML解析器()
        try:
            解析器.feed(文本)
            文本 = "".join(解析器.片段)
        except Exception:
            文本 = re.sub(r"<[^>]+>", "", 文本)
    行列表: list[str] = []
    for 行 in 文本.split("\n"):
        行 = re.sub(r"[ \t\u3000]+", " ", 行).strip()
        if 行列表 and not 行 and not 行列表[-1]:
            continue
        if 行:
            行列表.append(行)
        elif 行列表:
            行列表.append("")
    while 行列表 and not 行列表[-1]:
        行列表.pop()
    return "\n".join(行列表).strip()


def _遍历文本候选(值: Any, 结果: list[str], 已见: set[int], 深度: int = 0) -> None:
    if 值 is None or 深度 > 7:
        return
    if isinstance(值, str):
        结果.append(值)
        return
    if isinstance(值, dict):
        for 子值 in 值.values():
            _遍历文本候选(子值, 结果, 已见, 深度 + 1)
        return
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            _遍历文本候选(子值, 结果, 已见, 深度 + 1)
        return
    标识 = id(值)
    if 标识 in 已见:
        return
    已见.add(标识)
    for 字段名 in (
        "message_str",
        "raw_message",
        "message",
        "raw_data",
        "data",
        "content",
        "text",
    ):
        try:
            _遍历文本候选(getattr(值, 字段名, None), 结果, 已见, 深度 + 1)
        except Exception:
            continue


def 提取ZLibrary来源(event: Any, 命令文本: Any) -> str | None:
    候选: list[str] = []
    _遍历文本候选(命令文本, 候选, set())
    _遍历文本候选(event, 候选, set())
    for 文本 in 候选:
        文本 = html.unescape(str(文本)).replace("\\/", "/")
        for 匹配 in ZLibrary链接正则.finditer(文本):
            链接 = 匹配.group(0).rstrip("`)]}>，。；;！!）")
            if _是ZLibrary链接(链接):
                return 链接
        try:
            解码文本 = unquote(文本)
        except Exception:
            解码文本 = 文本
        for 匹配 in ZLibrary链接正则.finditer(解码文本):
            链接 = 匹配.group(0).rstrip("`)]}>，。；;！!）")
            if _是ZLibrary链接(链接):
                return 链接
    return None


def _是ZLibrary链接(值: str) -> bool:
    try:
        地址 = urlsplit(str(值).strip())
    except ValueError:
        return False
    主机 = (地址.hostname or "").lower().strip(".")
    路径 = [项目 for 项目 in (地址.path or "").split("/") if 项目]
    return 主机 in ZLibrary允许域名 and len(路径) >= 2 and 路径[0].lower() == "book"


def 解析ZLibrary书籍编号(来源: str) -> tuple[str, str]:
    try:
        路径 = [项目 for 项目 in urlsplit(来源).path.split("/") if 项目]
    except ValueError:
        return "", ""
    if len(路径) < 2 or 路径[0].lower() != "book":
        return "", ""
    书籍编号 = unquote(路径[1]).strip()
    哈希 = unquote(路径[2]).strip() if len(路径) >= 3 else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", 书籍编号):
        return "", ""
    return 书籍编号, 哈希


def _响应文件名(headers: Any, 默认值: str = "book.bin") -> str:
    内容处置 = str(headers.get("Content-Disposition") or "")
    if 内容处置:
        try:
            消息 = Message()
            消息["Content-Disposition"] = 内容处置
            文件名 = 消息.get_filename()
            if 文件名:
                return unquote(str(文件名).strip())
        except Exception:
            pass
    return 默认值


def _清理文件名(值: Any) -> str:
    文本 = re.sub(r"[\\/:*?\"<>|]+", "_", str(值 or "").strip())
    return 文本[:90] or "Z-Library小说"


def _解析HTML字段(原始: str) -> dict[str, Any]:
    if "diamwall" in 原始.lower() or "verifying your browser" in 原始.lower():
        raise _ZLibrary站点错误("Z-Library站点验证未通过")

    def 匹配文本(选择器属性: str) -> str:
        标签选择器 = (
            选择器属性
            if 选择器属性.startswith("<")
            else rf"<[^>]*{选择器属性}"
        )
        匹配 = re.search(
            rf"{标签选择器}[^>]*>([\s\S]*?)</[^>]+>",
            原始,
            re.I,
        )
        return _清理正文(匹配.group(1)) if 匹配 else ""

    标题 = 匹配文本(r"<h1\b[^>]*itemprop\s*=\s*['\"]name['\"]")
    if not 标题:
        元数据 = re.search(
            r"<meta\b[^>]*(?:itemprop\s*=\s*['\"]name['\"]|"
            r"property\s*=\s*['\"]og:title['\"])[^>]*"
            r"content\s*=\s*['\"]([^'\"]+)['\"]",
            原始,
            re.I,
        )
        if 元数据:
            标题 = _清理正文(元数据.group(1))
    if not 标题:
        标题 = 匹配文本(r"<h1\b")
    作者列表 = [
        _清理正文(匹配.group(1))
        for 匹配 in re.finditer(
            r"<a[^>]*itemprop\s*=\s*['\"]author['\"][^>]*>([\s\S]*?)</a>",
            原始,
            re.I,
        )
    ]
    作者列表 = list(dict.fromkeys(项目 for 项目 in 作者列表 if 项目))
    详情文件类型 = ""
    文件类型匹配 = re.search(
        r"(?:property__file|itemprop\s*=\s*['\"]encodingFormat['\"])[^>]*>"
        r"([\s\S]{0,200})",
        原始,
        re.I,
    )
    if 文件类型匹配:
        详情文件类型 = _清理正文(文件类型匹配.group(1))
    下载链接 = ""
    for 匹配 in re.finditer(
        r"<(?:a|button)[^>]+(?:href|data-href|data-url)\s*=\s*['\"]([^'\"]+)['\"][^>]*>",
        原始,
        re.I,
    ):
        候选 = html.unescape(匹配.group(1))
        if "/dl/" in 候选 or "/download" in 候选 or "download" in 候选.lower():
            下载链接 = 候选
            break
    if not 下载链接:
        匹配 = re.search(r"['\"]([^'\"]*/dl/[^'\"]+)['\"]", 原始, re.I)
        if 匹配:
            下载链接 = html.unescape(匹配.group(1))
    return {
        "title": 标题,
        "author": ", ".join(作者列表) or "未知",
        "download_url": 下载链接,
        "file_type": 详情文件类型,
    }


async def _请求详情(session: aiohttp.ClientSession, 来源: str) -> dict[str, Any]:
    try:
        async with session.get(来源, headers=_请求头(来源)) as response:
            if response.status in {403, 429, 503, 513}:
                raise _ZLibrary站点错误("Z-Library站点暂时不可访问")
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            原始 = await response.content.read(ZLibrary详情最大字节数 + 1)
            if len(原始) > ZLibrary详情最大字节数:
                raise _ZLibrary站点错误("Z-Library详情响应过大")
            最终来源 = str(response.url)
    except _ZLibrary站点错误:
        raise
    except Exception as exc:
        raise RuntimeError("Z-Library详情请求失败") from exc
    详情 = _解析HTML字段(原始.decode("utf-8", "replace"))
    if not _是ZLibrary链接(最终来源):
        raise _ZLibrary站点错误("Z-Library详情发生非站点跳转")
    书籍编号, 哈希 = 解析ZLibrary书籍编号(来源)
    详情["book_id"] = 书籍编号
    详情["hash"] = 哈希
    详情["detail_url"] = 最终来源
    if not 详情.get("title") or not 详情.get("download_url"):
        raise _ZLibrary站点错误("Z-Library详情缺少下载信息")
    详情["download_url"] = urljoin(最终来源, str(详情["download_url"]))
    return 详情


def _请求头(来源: str = "") -> dict[str, str]:
    地址 = urlsplit(来源)
    return {
        "Accept": "text/html,application/xhtml+xml,application/epub+zip,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Referer": f"{地址.scheme}://{地址.netloc}/" if 地址.netloc else "https://zh.z-library.sk/",
    }


async def _下载原文件(
    session: aiohttp.ClientSession, 详情: dict[str, Any], 来源: str
) -> tuple[Path, str]:
    下载地址 = str(详情.get("download_url") or "")
    if not 下载地址:
        raise _ZLibrary站点错误("Z-Library下载地址为空")
    try:
        下载URL = urlsplit(下载地址)
    except ValueError as exc:
        raise _ZLibrary站点错误("Z-Library下载地址无效") from exc
    if 下载URL.scheme.lower() not in {"http", "https"} or not 下载URL.hostname:
        raise _ZLibrary站点错误("Z-Library下载地址无效")
    扩展名 = Path(urlsplit(下载地址).path).suffix.lower() or ".bin"
    路径 = await asyncio.to_thread(
        文件缓存工具.创建临时缓存文件, "zlibrary-", 扩展名
    )
    try:
        async with session.get(下载地址, headers=_请求头(来源), allow_redirects=True) as response:
            if response.status in {403, 429, 503, 513}:
                raise _ZLibrary站点错误("Z-Library文件暂时不可下载")
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            内容类型 = str(response.headers.get("Content-Type") or "").lower()
            文件名 = _响应文件名(response.headers, f"book{扩展名}")
            if Path(文件名).suffix.lower() not in {
                ".epub", ".fb2", ".pdf", ".txt", ".html", ".htm", ".xhtml"
            }:
                后缀 = {
                    "application/epub+zip": ".epub",
                    "application/pdf": ".pdf",
                    "text/plain": ".txt",
                    "text/html": ".html",
                    "application/xhtml+xml": ".xhtml",
                }.get(内容类型.split(";", 1)[0].strip())
                if 后缀:
                    文件名 = f"book{后缀}"
            总长度 = response.headers.get("Content-Length")
            if 总长度 and int(总长度) > ZLibrary文件最大字节数:
                raise _ZLibrary站点错误("Z-Library文件过大")
            已写入 = 0
            with 路径.open("wb") as 文件:
                async for 块 in response.content.iter_chunked(256 * 1024):
                    已写入 += len(块)
                    if 已写入 > ZLibrary文件最大字节数:
                        raise _ZLibrary站点错误("Z-Library文件过大")
                    文件.write(块)
            if 内容类型.startswith("text/html"):
                前缀 = 路径.read_bytes()[:4096].lower()
                if b"login" in 前缀 or b"diamwall" in 前缀 or b"verification" in 前缀:
                    raise _ZLibrary站点错误("Z-Library下载需要公开可用的文件地址")
            return 路径, 文件名
    except Exception:
        await asyncio.to_thread(路径.unlink, True)
        raise


def _解码文本(原始: bytes) -> str:
    for 编码 in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            文本 = 原始.decode(编码)
            if 文本.count("\ufffd") < max(2, len(文本) // 100):
                return 文本
        except UnicodeDecodeError:
            continue
    return 原始.decode("utf-8", "replace")


def _读取EPUB正文(路径: Path) -> str:
    with zipfile.ZipFile(路径) as 压缩包:
        if sum(项目.file_size for 项目 in 压缩包.infolist()) > ZLibrary压缩后最大展开字节数:
            raise RuntimeError("EPUB解压后过大")
        opf路径 = ""
        try:
            容器 = ElementTree.fromstring(压缩包.read("META-INF/container.xml"))
            for 节点 in 容器.iter():
                if 节点.tag.rsplit("}", 1)[-1] == "rootfile":
                    opf路径 = str(节点.attrib.get("full-path") or "")
                    if opf路径:
                        break
        except Exception:
            pass
        if not opf路径:
            opf候选 = [项目 for 项目 in 压缩包.namelist() if 项目.lower().endswith(".opf")]
            opf路径 = opf候选[0] if opf候选 else ""
        if not opf路径:
            raise RuntimeError("EPUB缺少目录文件")
        opf = ElementTree.fromstring(压缩包.read(opf路径))
        清单: dict[str, str] = {}
        for 节点 in opf.iter():
            if 节点.tag.rsplit("}", 1)[-1] == "item":
                标识 = str(节点.attrib.get("id") or "")
                href = str(节点.attrib.get("href") or "")
                类型 = str(节点.attrib.get("media-type") or "").lower()
                if 标识 and href and ("html" in 类型 or href.lower().endswith((".xhtml", ".html", ".htm"))):
                    清单[标识] = posixpath.normpath(posixpath.join(posixpath.dirname(opf路径), href))
        正文路径: list[str] = []
        for 节点 in opf.iter():
            if 节点.tag.rsplit("}", 1)[-1] == "itemref":
                路径 = 清单.get(str(节点.attrib.get("idref") or ""))
                if 路径:
                    正文路径.append(路径)
        if not 正文路径:
            正文路径 = list(清单.values())
        片段 = [_清理正文(_解码文本(压缩包.read(路径))) for 路径 in 正文路径 if 路径 in 压缩包.namelist()]
    return "\n\n".join(项目 for 项目 in 片段 if 项目).strip()


def _读取FB2正文(路径: Path) -> str:
    return _读取FB2内容(路径.read_bytes())


def _读取FB2内容(原始: bytes) -> str:
    根节点 = ElementTree.fromstring(原始)
    片段: list[str] = []
    for 节点 in 根节点.iter():
        标签 = 节点.tag.rsplit("}", 1)[-1]
        if 标签 in {"title", "p", "subtitle", "text-author", "epigraph"}:
            文本 = _清理正文("".join(节点.itertext()))
            if 文本:
                片段.append(文本)
    return "\n\n".join(片段).strip()


def _读取PDF正文(路径: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("PDF解析库不可用") from exc
    读取器 = PdfReader(str(路径))
    return "\n\n".join(
        文本.strip()
        for 页面 in 读取器.pages
        for 文本 in [页面.extract_text() or ""]
        if 文本.strip()
    ).strip()


def _转换为正文(路径: Path, 文件名: str) -> str:
    后缀 = Path(文件名 or 路径.name).suffix.lower() or 路径.suffix.lower()
    with 路径.open("rb") as 文件:
        文件头 = 文件.read(5)
    if 后缀 == ".pdf" or 文件头 == b"%PDF-":
        return _读取PDF正文(路径)
    if zipfile.is_zipfile(路径):
        with zipfile.ZipFile(路径) as 压缩包:
            if sum(项目.file_size for 项目 in 压缩包.infolist()) > ZLibrary压缩后最大展开字节数:
                raise RuntimeError("电子书解压后过大")
            FB2路径 = next(
                (项目 for 项目 in 压缩包.namelist() if 项目.lower().endswith(".fb2")),
                None,
            )
            if FB2路径:
                return _读取FB2内容(压缩包.read(FB2路径))
        return _读取EPUB正文(路径)
    if 后缀 == ".fb2":
        return _读取FB2正文(路径)
    if 后缀 == ".pdf":
        return _读取PDF正文(路径)
    return _清理正文(_解码文本(路径.read_bytes()))


def _生成文件内容(详情: dict[str, Any], 正文: str) -> tuple[str, bytes]:
    标题 = _清理文件名(详情.get("title") or "Z-Library小说")
    作者 = _清理文件名(详情.get("author") or "未知")
    正文 = 去除章节正文重复标题(标题, 正文)
    if len(正文.strip()) < 2:
        raise RuntimeError("Z-Library正文为空")
    行列表 = [
        ZLibrary文件声明,
        "",
        f"书名：{标题}",
        f"作者：{作者}",
        "状态：电子书文件",
        "章节数：整本文件",
        "",
        标题,
        "",
        正文.strip(),
        "",
    ]
    文本 = "\n".join(行列表).replace("\r\n", "\n").replace("\r", "\n")
    return f"[完结]书名：{标题} 作者：{作者}.txt", 文本.replace("\n", "\r\n").encode("utf-8")


def _写入小说缓存(文件名: str, 内容: bytes) -> Path:
    目录 = 文件缓存工具.小说缓存目录
    目录.mkdir(parents=True, exist_ok=True)
    基础名 = Path(_清理文件名(文件名)).name
    if not 基础名.lower().endswith(".txt"):
        基础名 += ".txt"
    路径 = 目录 / 基础名
    for 序号 in range(1000):
        候选 = 路径 if 序号 == 0 else 目录 / f"{路径.stem}_{序号}{路径.suffix}"
        if not 候选.exists():
            候选.write_bytes(内容)
            文件缓存工具.标记小说缓存正在使用(候选)
            return 候选
    raise RuntimeError("小说缓存文件过多")


async def _发送小说文件(
    event: Any,
    文件名: str,
    内容: bytes,
    配置: Any,
    书名: str,
    作者: str,
) -> dict[str, Any]:
    路径 = await asyncio.to_thread(_写入小说缓存, 文件名, 内容)
    if 小说网盘 is None:
        await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
        return {"sent": False, "fallback_text": "", "path": None}
    try:
        上传 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传.get("success"):
            await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
            return {"sent": False, "fallback_text": "", "path": None}
        完成 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(上传.get("share_url") or "")
        )
        if 完成.get("sent"):
            await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
            return {"sent": True, "fallback_text": "", "path": None}
        return {
            "sent": False,
            "fallback_text": str(完成.get("fallback_text") or ""),
            "path": 路径,
        }
    except Exception:
        await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
        raise


def _创建ZLibrary会话() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=ZLibrary请求超时秒数, sock_connect=10, sock_read=25),
        connector=aiohttp.TCPConnector(limit=4, limit_per_host=4, ttl_dns_cache=300),
        trust_env=True,
        cookie_jar=aiohttp.CookieJar(unsafe=False),
    )


def 格式化ZLibrary下载提示(详情: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"书名：{详情.get('title') or '未知'}",
            f"作者：{详情.get('author') or '未知'}",
            "状态：电子书文件",
            "章节：整本",
            "",
            "正在下载中请稍等.....",
        ]
    )


async def 生成ZLibrary下载回复流(
    event: Any, 来源: str, 配置: Any = None
) -> AsyncIterator[str]:
    临时路径: Path | None = None
    阶段 = "create_session"
    try:
        async with _创建ZLibrary会话() as session:
            阶段 = "detail"
            详情 = await _请求详情(session, 来源)
            logger.info(
                "Z-Library小说开始下载：书名=%s, 作者=%s, 下载文件=1",
                详情.get("title") or "未知",
                详情.get("author") or "未知",
            )
            yield 格式化ZLibrary下载提示(详情)
            阶段 = "download"
            临时路径, 原文件名 = await _下载原文件(session, 详情, 来源)
            阶段 = "convert"
            正文 = await asyncio.to_thread(_转换为正文, 临时路径, 原文件名)
            if len(re.sub(r"\s+", "", 正文)) < 2:
                raise RuntimeError("Z-Library正文为空")
            文件名, 内容 = await asyncio.to_thread(_生成文件内容, 详情, 正文)
            字数 = len(re.sub(r"\s+", "", 正文))
            logger.info(
                "Z-Library小说下载完成：书名=%s, 文件数=1, 字数=%s, 文件大小=%s",
                详情.get("title") or "未知",
                字数,
                len(内容),
            )
            阶段 = "share"
            发送结果 = await _发送小说文件(
                event,
                文件名,
                内容,
                配置,
                str(详情.get("title") or "未知"),
                str(详情.get("author") or "未知"),
            )
            if 发送结果.get("sent"):
                return
            路径 = 发送结果.get("path")
            if 路径:
                await asyncio.to_thread(文件缓存工具.删除小说缓存文件, 路径)
            降级文本 = str(发送结果.get("fallback_text") or "")
            if 降级文本:
                yield 降级文本
                return
            yield ZLibrary文件发送失败提示
    except Exception as exc:
        logger.warning(
            "Z-Library小说下载失败：阶段=%s, 错误类型=%s",
            阶段,
            type(exc).__name__,
        )
        yield ZLibrary下载失败提示
    finally:
        if 临时路径 is not None:
            await asyncio.to_thread(临时路径.unlink, True)


def 获取ZLibrary小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[str] | None:
    来源 = 提取ZLibrary来源(event, 命令文本)
    if not 来源:
        return None
    return 生成ZLibrary下载回复流(event, 来源, 配置)
