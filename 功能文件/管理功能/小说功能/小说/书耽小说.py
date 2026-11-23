"""完整书耽源脚本与 AstrBot 调用适配。"""
from __future__ import annotations

import asyncio
import html
import hashlib
import logging
import json
import re
import time
from collections import deque
from itertools import islice
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote, urlsplit
from weakref import WeakValueDictionary

try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能 import 文件缓存
from 功能文件.管理功能.基础功能.消息工具 import 读取字段
from 功能文件.管理功能.基础功能.机器人作用域 import 获取当前机器人AppID
from 功能文件.管理功能.小说功能.功能.文本处理 import 格式化小说字数
from 功能文件.管理功能.小说功能.功能.平台隔离执行 import (
    创建平台同步调用, 创建平台缓存调用, 运行原脚本, 关闭平台原脚本,
)

_平台同步调用 = 创建平台同步调用("书耽")
_平台缓存调用 = 创建平台缓存调用("书耽", 文件缓存.删除小说缓存文件)
from 功能文件.管理功能.小说功能.小说 import 番茄小说
from 功能文件.管理功能.网盘功能 import 小说网盘

# 用户提供的完整原脚本。以下源码区不删改账号、函数、默认参数或请求行为。
_书耽原脚本 = r'''# -*- coding: utf-8 -*-
"""
书耽 App 书源 Python 版
对应 Legado 源：
  搜索  -> /bookcity/get_filter_search_book_list
  详情  -> /book/get_info_by_id
  目录  -> /chapter/get_chapter_list_group_by_division
  章节  -> /chapter/get_chapter_info
  段评  -> /chapter/get_paragraph_tsukkomi_list  (仅付费试读章用来拼正文)

用法：
  python shubl.py search 关键词
  python shubl.py detail <book_id>
  python shubl.py toc    <book_id>
  python shubl.py content <chapter_id>
  python shubl.py all    关键词
"""
import sys
import json
import base64
import re
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

# ----------------- 常量（与书源一一对应） -----------------
BASE         = "https://app.shubl.com"
TOKEN        = "0f6bd1d063f202f71c3b84678027ce81"          # getToken()
ACCOUNT      = "%E8%90%8C%E5%8F%8B521068519938"            # getA()  (urlencode 后的 萌友521068519938)
APP_SIGN     = "f73576612783f8ed8b68cdf73a56be94"          # app_signature_md5
APP_VERSION  = "4.1.1"                                     # 请求 JSON 里用的版本
HEADER_VER   = "4.1.4"                                     # header 里用的版本

# AES-256 / CBC / PKCS7，IV 全 0
KEY = base64.b64decode("L6alxSR4ttjXvcGpZozYtdcJtG4l0tSnQplRUONIRsw=")
IV  = base64.b64decode("AAAAAAAAAAAAAAAAAAAAAA==")

# ----------------- 加解密（对应 jsLib 的 encode / decode） -----------------
def encrypt(text: str) -> str:
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(text.encode("utf-8")) + padder.finalize()
    enc = Cipher(algorithms.AES(KEY), modes.CBC(IV)).encryptor()
    return base64.b64encode(enc.update(padded) + enc.finalize()).decode("ascii")


def decrypt(b64_text: str) -> str:
    ct = base64.b64decode(b64_text.strip())
    dec = Cipher(algorithms.AES(KEY), modes.CBC(IV)).decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


# ----------------- 会话 -----------------
SESSION = requests.Session()
SESSION.headers.update({
    "app-version": HEADER_VER,
    "User-Agent": "okhttp/3.14.9",
})
_retry = Retry(total=3, backoff_factor=0.5,
               status_forcelist=(500, 502, 503, 504),
               allowed_methods=frozenset(["POST"]))
SESSION.mount("https://", HTTPAdapter(max_retries=_retry))


# ----------------- 请求封装 -----------------
# 注意：书源里只有「段评」接口使用了 encodeURIComponent；
#      其他接口只是 "secret_content=" + base64。这里默认对全部接口做
#      标准 form 编码（更稳），若要完全还原原书源，传 urlencode_body=False。
def _post(path: str, obj: dict, urlencode_body: bool = True, timeout: int = 60) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    b64 = encrypt(raw)

    if urlencode_body:
        # requests 会自动 urlencode，并把 Content-Type 设为 x-www-form-urlencoded
        resp = SESSION.post(BASE + path, data={"secret_content": b64}, timeout=timeout)
    else:
        body = ("secret_content=" + b64).encode("utf-8")
        resp = SESSION.post(
            BASE + path,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    resp.raise_for_status()
    return resp.text


def _decode_resp(text: str) -> dict:
    """响应通常是纯 Base64 密文；异常时可能是明文 JSON。"""
    text = (text or "").strip()
    try:
        return json.loads(decrypt(text))
    except Exception:
        try:
            return json.loads(text)
        except Exception:
            raise RuntimeError("无法解析响应: " + text[:200])


def _payload(**extra) -> dict:
    d = {
        "app_signature_md5": APP_SIGN,
        "app_version": APP_VERSION,
        "channel": "default",
    }
    d.update(extra)
    d["login_token"] = TOKEN
    d["account"] = ACCOUNT
    return d


# ----------------- 搜索（searchUrl + ruleSearch） -----------------
def search(key: str, page: int = 1,
           order: str = "week_click",
           count: str = "15",
           category_type: str = "1",
           urlencode_body: bool = True) -> list:
    obj = {
        "app_signature_md5": APP_SIGN,
        "app_version": APP_VERSION,
        "channel": "default",
        "order": order,
        "count": count,
        "category_type": category_type,
        "page": page - 1,          # 0 起
        "key": key,
        "login_token": TOKEN,
        "account": ACCOUNT,
    }
    text = _post("/bookcity/get_filter_search_book_list", obj, urlencode_body)
    data = _decode_resp(text)
    return (data.get("data") or {}).get("book_list") or []


# ----------------- 详情（ruleBookInfo / bookUrl） -----------------
def book_info(book_id, urlencode_body: bool = True) -> dict:
    text = _post("/book/get_info_by_id", _payload(book_id=book_id), urlencode_body)
    data = _decode_resp(text)
    return (data.get("data") or {}).get("book_info") or {}


# ----------------- 目录（tocUrl + ruleToc） -----------------
def chapter_list(book_id, urlencode_body: bool = True) -> list:
    obj = _payload(last_update_time="0", book_id=book_id)
    text = _post("/chapter/get_chapter_list_group_by_division", obj, urlencode_body)
    data = _decode_resp(text)
    groups = (data.get("data") or {}).get("chapter_list_group") or []
    chapters = []
    for g in groups:
        chapters.extend(g.get("chapter_list") or [])
    return chapters


# ----------------- 章节信息（chapterUrl） -----------------
def chapter_info(chapter_id, urlencode_body: bool = True) -> dict:
    text = _post("/chapter/get_chapter_info", _payload(chapter_id=chapter_id), urlencode_body)
    data = _decode_resp(text)
    return (data.get("data") or {}).get("chapter_info") or {}


# ----------------- 段评（正文拼装用） -----------------
def paragraph(chapter_id, idx: int, urlencode_body: bool = True) -> str:
    obj = _payload(chapter_id=str(chapter_id), paragraph_index=str(idx))
    try:
        text = _post("/chapter/get_paragraph_tsukkomi_list", obj, urlencode_body)
        data = _decode_resp(text)
        if str(data.get("code")) == "100000" and data.get("data"):
            return data["data"].get("paragraph_content") or ""
    except Exception as e:
        print(f"  [para {idx}] error: {e}")
    return ""


# ----------------- 正文（ruleContent） -----------------
def content(chapter_id, max_paras: int = 300,
            empty_limit: int = 15,
            urlencode_body: bool = True,
            verbose: bool = True) -> str:
    text = _post("/chapter/get_chapter_info",
                 _payload(chapter_id=chapter_id), urlencode_body)
    info = _decode_resp(text)
    ci = (info.get("data") or {}).get("chapter_info") or {}

    txt = ci.get("txt_content") or ""
    is_paid = str(ci.get("is_paid")) == "1"
    trial   = str(ci.get("auth_access")) == "0" or len(txt) <= 300

    if is_paid and trial:
        if verbose:
            print(f"  付费试读，改用段评接口拼正文（chapter_id={chapter_id}）")
        out = {}
        empty_run = 0

        pc0 = paragraph(chapter_id, 0, urlencode_body)
        if pc0:
            out[0] = pc0
        i = 1
        while i <= max_paras and empty_run < empty_limit:
            pc = paragraph(chapter_id, i, urlencode_body)
            if pc:
                out[i] = pc
                empty_run = 0
            else:
                empty_run += 1
            if verbose and i % 20 == 0:
                print(f"  段落进度: {i}, 已获取 {len(out)} 段")
            i += 1
        if out:
            full = "\n".join(out[k] for k in sorted(out))
            if re.sub(r"\s+", "", full):
                txt = full

    # 清洗：只去行首的全角空格与半角空格（保持与原书源一致）
    lines = txt.split("\n")
    clean = [ln.lstrip("\u3000 ") for ln in lines]
    return "\n".join(clean)


# ----------------- 测试函数 -----------------
def t_search(keyword: str) -> list:
    print(f"=== 搜索: {keyword} ===")
    t0 = time.time()
    books = search(keyword)
    print(f"  耗时 {time.time()-t0:.2f}s, 返回 {len(books)} 本")
    for b in books[:10]:
        print(f"  - {b.get('book_name')} | {b.get('author_name')} "
              f"| id={b.get('book_id')} | {b.get('total_word_count')}字 "
              f"| {b.get('tag')}")
    return books


def t_detail(book_id) -> dict:
    print(f"=== 详情: {book_id} ===")
    info = book_info(book_id)
    print(f"  书名: {info.get('book_name')}")
    print(f"  作者: {info.get('author_name')}")
    print(f"  标签: {info.get('tag')}")
    print(f"  字数: {info.get('total_word_count')}")
    lc = info.get("last_chapter_info") or {}
    print(f"  最新: {lc.get('chapter_title')} / {lc.get('uptime')}")
    print(f"  简介: {(info.get('description') or '')[:80]}...")
    return info


def t_toc(book_id) -> list:
    print(f"=== 目录: {book_id} ===")
    chs = chapter_list(book_id)
    print(f"  共 {len(chs)} 章")
    for c in chs[:8]:
        vip = "VIP" if str(c.get("auth_access")) != "0" else "免费"
        print(f"  - [{vip}] {c.get('chapter_title')} "
              f"| id={c.get('chapter_id')} | {c.get('word_count')}字")
    return chs


def t_content(chapter_id) -> str:
    print(f"=== 正文: {chapter_id} ===")
    t0 = time.time()
    txt = content(chapter_id)
    print(f"  耗时 {time.time()-t0:.2f}s, 长度 {len(txt)}")
    print("  预览:")
    print("  " + "\n  ".join(txt[:300].splitlines()[:8]))
    return txt


def t_all(keyword: str):
    books = t_search(keyword)
    if not books:
        print("搜索无结果，结束")
        return
    bid = books[0]["book_id"]
    t_detail(bid)
    chs = t_toc(bid)
    if not chs:
        print("目录为空，结束")
        return
    # 优先拿一个付费章验证段评拼装；没有就取最后一章
    vip = [c for c in chs if str(c.get("auth_access")) != "0"]
    target = (vip or chs[-1:])[0]
    t_content(target["chapter_id"])


# ----------------- CLI -----------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "search":
        t_search(arg or "测试")
    elif cmd == "detail":
        t_detail(arg)
    elif cmd == "toc":
        t_toc(arg)
    elif cmd == "content":
        t_content(arg)
    elif cmd == "all":
        t_all(arg or "测试")
    else:
        print(__doc__)'''

_书耽链接候选 = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

_书耽详情路径 = re.compile(r"/book/book_detail/([1-9][0-9]{0,19})/?")

_跳过卡片分支 = {
    "author", "sender", "user", "member", "mentions", "reply", "quote",
    "quoted", "quotedmessage", "reference", "messagereference", "msgelements",
    "message", "rawmessage", "forward", "node", "nodes", "ref",
}

def _数字(值: Any) -> str:
    return str(值) if type(值) in (int, str) and re.fullmatch(r"[0-9]{1,20}", str(值)) else ""

def _编号(值: Any) -> str:
    文本 = _数字(值)
    return 文本 if 文本 and int(文本) > 0 else ""

def _文本(值: Any) -> str:
    return 值.strip() if isinstance(值, str) else ""

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
    原始状态 = 书.get("up_status")
    状态 = _文本(原始状态)
    if 状态 in {"完结", "已完结", "完本"}:
        return "完结"
    if 状态 in {"连载", "连载中"}:
        return "连载"
    # 同书 App 详情与官方网页核对：0 连载，1 完结；其他数值不猜测。
    return {"0": "连载", "1": "完结"}.get(_数字(原始状态), "未知")

def _书籍资料(书: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _文本(书.get("book_name")),
        "author": _文本(书.get("author_name")) or "未知",
        "status": _书耽书籍状态(书),
        "word_count": int(_编号(书.get("total_word_count")) or "0"),
        "intro": _文本(书.get("description")),
    }

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
    return await _平台缓存调用(_保存缓存, 文件名, 内容)


def 获取书耽小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 书耽来源(提取书耽详情书号(event, 命令文本))
    return 生成书耽下载回复流(event, 来源, 配置) if 来源 else None

_书耽源指纹 = hashlib.sha256(_书耽原脚本.encode("utf-8")).digest()
书耽正文最大并发数 = 200
_书耽段落并发数 = 8
_书耽段落最大索引 = 300
_书耽连续空段上限 = 15
_书耽进度日志分段数 = 4
if "_书耽已关闭" not in globals():
    _书耽已关闭 = False
if "_章节限额" not in globals():
    _章节限额 = WeakValueDictionary()
if "_书耽请求限额" not in globals():
    _书耽请求限额 = WeakValueDictionary()

_下载失败 = "下载失败 请重试"
_发送失败 = "文件发送失败，请稍后再试"


class 书耽请求错误(RuntimeError):
    pass


async def _调用原函数(名称: str, *参数: Any) -> Any:
    if _书耽已关闭:
        raise 书耽请求错误("service_stopped")
    循环 = asyncio.get_running_loop()
    限额 = _书耽请求限额.get(循环)
    if 限额 is None:
        限额 = asyncio.Semaphore(书耽正文最大并发数)
        _书耽请求限额[循环] = 限额
    # 与章节额度分开，避免所有章节持有额度后互相等待段落请求。
    async with 限额:
        if _书耽已关闭:
            raise 书耽请求错误("service_stopped")
        任务 = asyncio.create_task(运行原脚本(
            "书耽", _书耽原脚本, 名称, 参数, max_workers=书耽正文最大并发数
        ))
        try:
            return await asyncio.shield(任务)
        except asyncio.CancelledError:
            # 原请求结束前继续占用额度，防止取消时放行另一批请求。
            while not 任务.done():
                try:
                    await asyncio.shield(任务)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not 任务.cancelled():
                任务.exception()
            raise


async def _获取书耽章节正文(章节编号: str) -> str:
    """使用原请求函数滑动取段，保持原 content 的拼接和停止规则。"""
    信息 = await _调用原函数("chapter_info", 章节编号)
    正文 = 信息.get("txt_content") or ""
    if str(信息.get("is_paid")) == "1" and (
        str(信息.get("auth_access")) == "0" or len(正文) <= 300
    ):
        段落 = {}
        待拼接 = {}
        任务列表 = {}
        索引 = 0
        下一索引 = 0
        连续空段 = 0
        try:
            while 索引 <= _书耽段落最大索引 and 连续空段 < _书耽连续空段上限:
                # 未知段落即使全为空，也不能越过原脚本最早可能的停止点。
                最后可请求 = min(
                    _书耽段落最大索引,
                    max(1, 索引) + _书耽连续空段上限 - 连续空段 - 1,
                )
                while len(任务列表) < _书耽段落并发数 and 下一索引 <= 最后可请求:
                    任务列表[下一索引] = asyncio.create_task(
                        _调用原函数("paragraph", 章节编号, 下一索引)
                    )
                    下一索引 += 1
                if not 任务列表:
                    break
                完成, _ = await asyncio.wait(
                    任务列表.values(), return_when=asyncio.FIRST_COMPLETED,
                )
                for i, 任务 in list(任务列表.items()):
                    if 任务 in 完成:
                        del 任务列表[i]
                        待拼接[i] = 任务.result()
                while 索引 in 待拼接:
                    内容 = 待拼接.pop(索引)
                    if 内容:
                        段落[索引] = 内容
                        连续空段 = 0
                    elif 索引:
                        连续空段 += 1
                    索引 += 1
                    if 连续空段 >= _书耽连续空段上限:
                        break
        finally:
            for 任务 in 任务列表.values():
                if not 任务.done():
                    任务.cancel()
            await asyncio.gather(*任务列表.values(), return_exceptions=True)
        if 段落:
            全文 = "\n".join(段落[i] for i in sorted(段落))
            if re.sub(r"\s+", "", 全文):
                正文 = 全文
    return "\n".join(行.lstrip("\u3000 ") for 行 in 正文.split("\n"))


def 启动书耽资源() -> None:
    global _书耽已关闭
    _书耽已关闭 = False


async def 关闭书耽资源() -> None:
    global _书耽已关闭
    _书耽已关闭 = True
    # 热升级时仅收尾已存在的旧线程池，不再向它提交任何下载。
    旧池 = globals().get("_书耽线程池")
    if 旧池 is not None:
        globals()["_书耽线程池"] = None
        await asyncio.to_thread(旧池.shutdown, wait=True, cancel_futures=True)
        for 会话 in list(globals().get("_书耽会话", {}).values()):
            会话.close()
        globals().get("_书耽会话", {}).clear()
    await 关闭平台原脚本("书耽")


def 书耽搜索账号标识(配置: Any = None) -> tuple[str, bytes]:
    return 获取当前机器人AppID(配置), hashlib.sha256(_书耽源指纹 + b"up-status-0-1").digest()


async def _下载原脚本章节(目录: list[dict[str, Any]], *, 书籍编号: str = "") -> list[dict[str, Any]]:
    总数 = len(目录)
    if not 总数:
        return []
    循环 = asyncio.get_running_loop()
    限额 = _章节限额.get(循环)
    if 限额 is None:
        限额 = asyncio.Semaphore(书耽正文最大并发数)
        _章节限额[循环] = 限额
    待下载 = iter(enumerate(目录))
    结果 = [{} for _ in 目录]
    已完成 = 0
    失败数 = 0
    进度步长 = max(1, (总数 + _书耽进度日志分段数 - 1) // _书耽进度日志分段数)
    下次进度 = 进度步长
    上次已处理 = -1

    def 记录进度(*, 强制: bool = False) -> None:
        nonlocal 下次进度, 上次已处理
        已处理 = 已完成 + 失败数
        if 已处理 == 上次已处理 or (not 强制 and 已处理 < 下次进度 and 已处理 < 总数):
            return
        logger.info(
            "书耽小说章节进度：书籍编号=%s, 已处理=%s/%s, 处理百分比=%s%%, 成功=%s, 失败=%s",
            书籍编号, 已处理, 总数, min(100, 已处理 * 100 // 总数), 已完成, 失败数,
        )
        上次已处理 = 已处理
        while 下次进度 <= 已处理:
            下次进度 += 进度步长

    async def 工作():
        nonlocal 已完成, 失败数
        for 序号, 章 in 待下载:
            try:
                async with 限额:
                    正文 = await _获取书耽章节正文(_编号(章.get("chapter_id")))
                if not isinstance(正文, str) or not 正文.strip():
                    raise 书耽请求错误("empty_chapter")
                结果[序号] = {
                    "index": 序号 + 1, "title": 章["chapter_title"],
                    "content": 正文, "success": True,
                }
            except asyncio.CancelledError:
                raise
            except Exception:
                失败数 += 1
                raise
            已完成 += 1
            记录进度()

    并发数 = min(书耽正文最大并发数, 总数)
    logger.info("书耽正文下载开始：书号=%s，章节=%s，工作协程=%s", 书籍编号, 总数, 并发数)
    记录进度(强制=True)
    任务列表 = [asyncio.create_task(工作()) for _ in range(并发数)]
    try:
        await asyncio.gather(*任务列表)
    finally:
        for 任务 in 任务列表:
            if not 任务.done():
                任务.cancel()
        await asyncio.gather(*任务列表, return_exceptions=True)
        if 失败数:
            记录进度(强制=True)
    return 结果


async def _获取书耽书籍元数据(书籍编号: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """详情和目录只依赖书号，共用原函数并行读取并统一收尾。"""
    任务列表 = [
        asyncio.create_task(_调用原函数("book_info", 书籍编号)),
        asyncio.create_task(_调用原函数("chapter_list", 书籍编号)),
    ]
    try:
        详情, 目录 = await asyncio.gather(*任务列表)
        return 详情, 目录
    finally:
        for 任务 in 任务列表:
            if not 任务.done():
                任务.cancel()
        await asyncio.gather(*任务列表, return_exceptions=True)


async def 生成书耽下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    匹配 = re.fullmatch(r"shubl:([0-9]{1,20})", str(来源 or ""))
    书籍编号 = _编号(匹配[1]) if 匹配 else ""
    if not 书籍编号:
        yield _下载失败
        return
    阶段 = "metadata"
    路径 = None
    开始 = time.monotonic()
    logger.info("书耽下载任务开始：书号=%s", 书籍编号)
    try:
        详情, 目录 = await _获取书耽书籍元数据(书籍编号)
        if not isinstance(详情, dict) or not isinstance(目录, list) or not 目录:
            raise 书耽请求错误("invalid_metadata")
        if _编号(详情.get("book_id")) != 书籍编号:
            raise 书耽请求错误("invalid_book")
        for 章 in 目录:
            if not isinstance(章, dict) or not _编号(章.get("chapter_id")) or not _文本(章.get("chapter_title")):
                raise 书耽请求错误("invalid_catalog")
        书籍信息 = _书籍资料(详情)
        书籍信息["word_count"] = 格式化小说字数(书籍信息["word_count"])
        logger.info("书耽目录加载完成：书号=%s，章节=%s，状态=%s",
                    书籍编号, len(目录), 书籍信息["status"])
        yield 番茄小说.格式化番茄下载提示(书籍信息, len(目录))
        阶段 = "chapters"
        结果 = await _下载原脚本章节(目录, 书籍编号=书籍编号)
        阶段 = "txt"
        logger.info("书耽生成TXT：书号=%s，章节=%s", 书籍编号, len(结果))
        文件名, 内容 = await _平台同步调用(番茄小说.生成番茄小说文件内容, 书籍编号, 书籍信息, 目录, 结果)
        路径 = await _异步写入缓存(文件名, 内容)
        阶段 = "upload"
        logger.info("书耽文件交付开始：书号=%s，字节=%s", 书籍编号, len(内容))
        上传 = await 小说网盘.上传小说并获取分享链接(配置, 路径, 文件名)
        if not 上传.get("success"):
            logger.warning("书耽文件交付失败：书号=%s，阶段=upload", 书籍编号)
            yield _发送失败
            return
        阶段 = "share"
        发送 = await 小说网盘.发送小说下载结果(event, 书籍信息["title"], 书籍信息["author"], 上传)
        if not 发送.get("sent"):
            logger.warning("书耽文件交付失败：书号=%s，阶段=share", 书籍编号)
            yield str(发送.get("fallback_text") or _发送失败)
        else:
            logger.info("书耽下载完成：书号=%s，章节=%s，用时=%.1f秒",
                        书籍编号, len(目录), time.monotonic() - 开始)
    except asyncio.CancelledError:
        logger.info("书耽下载已取消：书号=%s，阶段=%s", 书籍编号, 阶段)
        raise
    except Exception as 错误:
        logger.warning("书耽下载失败：书号=%s，阶段=%s，类型=%s", 书籍编号, 阶段, type(错误).__name__)
        yield _发送失败 if 阶段 in {"upload", "share"} else _下载失败
    finally:
        if 路径 is not None:
            文件缓存.删除小说缓存文件(路径)


async def 搜索书耽小说(关键词: str, 数量上限: int = 15) -> list[dict[str, Any]]:
    关键词 = str(关键词 or "").strip()
    if not 关键词:
        return []
    列表 = await _调用原函数("search", 关键词)
    if not isinstance(列表, list):
        raise 书耽请求错误("invalid_search")
    结果 = []
    上限 = min(15, max(1, int(数量上限)))
    for 书 in 列表:
        if not isinstance(书, dict):
            continue
        编号 = _编号(书.get("book_id"))
        资料 = _书籍资料(书)
        if 编号 and 资料["title"]:
            结果.append({**资料, "book_id": 编号, "platform": "书耽", "url": 书耽来源(编号)})
        if len(结果) == 上限:
            break
    return 结果
