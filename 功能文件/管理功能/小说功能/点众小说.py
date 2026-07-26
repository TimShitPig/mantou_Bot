from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any, AsyncIterator
import json
import random
import uuid
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from astrbot.api import logger

try:
    from 功能文件.管理功能.网盘功能 import UC网盘
except Exception as exc:
    UC网盘 = None
    logger.warning(f"UC网盘模块加载失败：error={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={exc}")

下载缓存目录 = Path(__file__).resolve().parents[2] / "下载缓存"
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
章节并发数 = 10

# ===== 点众协议与加解密（原 _点众源码） =====

KEY = b"dz#7gfy)@#ylgz&m"
IV = b"$#iupdo)8^dcr*pt"
ST = "l1t5u51n1wk1yfor1ncrypt"
BASE = "https://asgportal.dianzhong.com/asg-portal/portal/client"  # 使用能工作的域名
CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
UA = (
    "Mozilla/5.0 (Linux; Android 12; SM-G9900 Build/V417IR; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/110.0.5481.154 Safari/537.36"
)
DEVICE_FILE = None  # 插件仅使用内存设备态，不生成本地 device.json

# -------------------- 加密/解密工具 --------------------
def enc(text: str) -> str:
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(text.encode("utf-8"), 16)).hex()

def dec(hex_str: str) -> str:
    return unpad(AES.new(KEY, AES.MODE_CBC, IV).decrypt(bytes.fromhex(hex_str)), 16).decode("utf-8")

def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

# -------------------- 设备身份管理（完全复用 dz_simple.py） --------------------
def gen_utdid_tmp(ts_ms=None) -> str:
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    date = time.strftime("%Y%m%d%H%M%S", time.localtime(ts_ms / 1000.0))
    ms = f"{ts_ms % 1000:03d}"
    rand6 = "".join(random.choice(CHARS) for _ in range(6))
    return "A" + date + ms + rand6

def make_datas():
    now = int(time.time() * 1000)
    sid = str(uuid.uuid4())
    return {
        "version": "7.3.0",
        "pname": "com.dianzhong.reader",
        "channelCode": "TAXSEO1000000",
        "utdidTmp": gen_utdid_tmp(now),
        "token": "",
        "utdid": "",
        "os": "android",
        "osv": 32,
        "brand": "Samsung",
        "model": "SM-G9900",
        "manu": "Samsung",
        "userId": "",
        "launch": "third",
        "mchid": "",
        "nchid": "TAXSEO1000000",
        "session1": sid,
        "session2": sid,
        "installTime": now,
        "p": 20,
        "sex": 1,
        "launchNum": 1,
        "visitor": 1,
        "supportAd": 1,
        "changeChidDate": now,
    }

def call_api(api, body, datas, timeout=20):
    body_plain = dumps(body)
    datas_plain = dumps(datas)
    headers = {
        "User-Agent": "okhttp/4.10.0",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json; charset=utf-8",
        "st": ST,
        "datas": enc(datas_plain),
    }
    r = requests.post(f"{BASE}/{api}", data=enc(body_plain), headers=headers, timeout=timeout)
    raw = r.json()
    data_plain = None
    data_json = None
    data = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(data, str) and data:
        try:
            data_plain = dec(data)
            data_json = json.loads(data_plain)
        except Exception:
            data_plain = data
    return {
        "http": r.status_code,
        "body_plain": body_plain,
        "datas_plain": datas_plain,
        "datas": datas,
        "raw": raw,
        "data_plain": data_plain,
        "data_json": data_json,
    }

def save_device(datas, path=DEVICE_FILE):
    path.write_text(json.dumps(datas, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def load_device(path=DEVICE_FILE):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def init_and_save():
    datas = make_datas()
    body = {
        "oaid": "",
        "userAgent": UA,
        "upgradeUserId": "",
        "requestType": 1,
        "ocpcSeconds": 0,
        "lastLeftPage": "",
    }
    res = call_api(1001, body, datas)
    raw = res["raw"] if isinstance(res["raw"], dict) else {}
    user_id = raw.get("userId")
    if user_id is None and isinstance(res["data_json"], dict):
        user_id = res["data_json"].get("userId")
        if user_id is None:
            user_id = (res["data_json"].get("userInfoVo") or {}).get("userId")
    if not user_id:
        raise RuntimeError(f"init failed: {json.dumps(raw, ensure_ascii=False)[:400]}")

    datas["userId"] = str(user_id)
    datas["visitor"] = 0
    if raw.get("changeChidDate"):
        datas["changeChidDate"] = raw["changeChidDate"]
    path = save_device(datas)
    res["userId"] = str(user_id)
    res["device_file"] = str(path)
    return datas, res

def get_device(force_init=False):
    if not force_init:
        d = load_device()
        if d and d.get("userId") and d.get("utdidTmp"):
            return d
    datas, _ = init_and_save()
    return datas

# -------------------- 工具函数 --------------------

# ===== 业务封装 =====

进度日志分段数 = 10
点众域名正则 = re.compile(r"dianzhong\.com|dz\.|点众", re.I)
链接正则 = re.compile(r"https?://[^\s'\"<>]+", re.I)
书籍编号正则 = re.compile(r"(?:bookId|book[_-]?id|bid)=(\d{4,})", re.I)
路径编号正则 = re.compile(r"/(?:book|detail|chapter)/(\d{4,})", re.I)

_设备缓存: dict[str, Any] | None = None


def _获取设备() -> dict[str, Any]:
    global _设备缓存
    if _设备缓存 and _设备缓存.get("userId"):
        return _设备缓存
    # 不落本地 device.json，内存会话即可
    datas = make_datas()
    body = {
        "oaid": "",
        "userAgent": UA,
        "upgradeUserId": "",
        "requestType": 1,
        "ocpcSeconds": 0,
        "lastLeftPage": "",
    }
    res = call_api(1001, body, datas)
    raw = res["raw"] if isinstance(res.get("raw"), dict) else {}
    user_id = raw.get("userId")
    if user_id is None and isinstance(res.get("data_json"), dict):
        user_id = res["data_json"].get("userId") or (res["data_json"].get("userInfoVo") or {}).get("userId")
    if not user_id:
        raise RuntimeError("点众设备初始化失败")
    datas["userId"] = str(user_id)
    datas["visitor"] = 0
    if raw.get("changeChidDate"):
        datas["changeChidDate"] = raw["changeChidDate"]
    _设备缓存 = datas
    return datas


def 获取点众小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取直接点众来源(命令文本) or 提取事件点众来源(event)
    if 来源 is None:
        return None
    return 生成下载回复流(event, 来源, 配置)


async def 生成下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取书籍编号(来源)
    if not 书籍编号:
        yield "下载失败"
        return
    try:
        datas = await asyncio.to_thread(_获取设备)
        详情 = await asyncio.to_thread(_获取详情, datas, 书籍编号)
        目录 = await asyncio.to_thread(_获取目录, datas, 书籍编号)
        if not 目录:
            logger.warning(f"点众小说目录失败：book_id={书籍编号}")
            yield "下载失败"
            return
        书名 = str(详情.get("title") or 详情.get("bookName") or "未知")
        作者 = str(详情.get("author") or 详情.get("authorName") or "未知")
        状态原文 = str(详情.get("status") or 详情.get("serialStatus") or "")
        状态 = "完结" if ("完" in 状态原文 or str(详情.get("isEnd") or "") in {"1", "true", "True"}) else "连载"
        字数 = 格式化字数(详情.get("wordCount") or 详情.get("words") or 详情.get("wordNum"))
        logger.info(f"点众小说开始下载：book_id={书籍编号}, title={书名}, author={作者}, chapters={len(目录)}")
        yield "\n".join([
            f"书名：{书名}",
            f"作者：{作者}",
            f"状态：{状态}",
            f"章节：{len(目录)} 章",
            f"字数：{字数}",
            "",
            "正在下载中请稍等.....",
        ])
        章节结果 = await 下载全部章节(datas, 书籍编号, 目录, 书名)
        成功 = [x for x in 章节结果 if x.get("content")]
        if not 成功:
            logger.warning(f"点众小说下载失败：book_id={书籍编号}, success=0, total={len(目录)}")
            yield "下载失败"
            return
        文件名, 文件内容 = 生成小说文件(书籍编号, 书名, 作者, 状态, 字数, 章节结果)
        发送结果 = await 准备发送文本文件(event, 文件名, 文件内容, 配置, 书名=书名, 作者=作者)
        if 发送结果.get("sent"):
            启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        降级 = str(发送结果.get("fallback_text") or "")
        if 降级:
            try:
                yield 降级
            finally:
                启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(f"点众小说下载失败：source={来源}, error={exc}")
        yield "下载失败"


def _获取详情(datas: dict[str, Any], book_id: str) -> dict[str, Any]:
    res = call_api(1111, {"bookId": str(book_id), "chapterId": ""}, datas)
    data = res.get("data_json")
    if isinstance(data, dict):
        book = data.get("bookInfo") or data.get("book") or data
        if isinstance(book, dict):
            return book
    return {}


def _获取目录(datas: dict[str, Any], book_id: str) -> list[dict[str, Any]]:
    全部: list[dict[str, Any]] = []
    chap_idx = 0
    cur_id = ""
    for _ in range(200):
        body = {"bookId": str(book_id), "chapterIndex": chap_idx, "currentChapterId": cur_id}
        res = call_api(1304, body, datas)
        data = res.get("data_json") if isinstance(res.get("data_json"), dict) else {}
        items = data.get("chapterList") or data.get("chapters") or data.get("list") or []
        if not isinstance(items, list) or not items:
            break
        for it in items:
            if not isinstance(it, dict):
                continue
            cid = str(it.get("chapterId") or it.get("id") or "").strip()
            if not cid:
                continue
            全部.append({
                "id": cid,
                "title": str(it.get("chapterName") or it.get("title") or it.get("name") or f"章节{cid}"),
            })
            cur_id = cid
        if data.get("isEnd") or data.get("end") or len(items) < 20:
            break
        chap_idx = len(全部)
    # 去重保序
    见过 = set()
    结果 = []
    for it in 全部:
        if it["id"] in 见过:
            continue
        见过.add(it["id"])
        结果.append(it)
    return 结果


def _获取章节正文(datas: dict[str, Any], book_id: str, chapter_id: str, book_name: str = "") -> str:
    source = {
        "origin": "ssym",
        "originName": "搜索页面",
        "channelId": "ssjgy",
        "channelName": "搜索结果页",
        "columnId": "gjc",
        "columnName": book_name or "未知",
        "contentType": "book_detail",
        "contentId": book_id,
        "contentName": book_name or "未知书籍",
        "triggerTime": int(time.time() * 1000),
        "strategyId": "",
        "expId": "",
        "logId": "",
        "strategyName": "",
        "channelPos": "",
        "columnPos": "0",
        "contentPos": "0",
        "otypeId": "",
        "otypeName": "",
    }
    body = {
        "bookId": str(book_id),
        "chapterId": str(chapter_id),
        "offset": 0,
        "confirmWatch": "1",
        "preload": "0",
        "noDd100": 1,
        "noDd300": 1,
        "source": dumps(source),
    }
    res = call_api(1303, body, datas)
    data = res.get("data_json") if isinstance(res.get("data_json"), dict) else {}
    if data.get("status") == 5 and "orderPageVo" in data:
        order = data.get("orderPageVo") or {}
        ad_key = None
        if isinstance(order.get("unlockOperate"), dict):
            ad_key = order["unlockOperate"].get("key")
        if not ad_key and isinstance(order.get("exitRetainOperate"), dict):
            ad_key = order["exitRetainOperate"].get("key")
        if ad_key:
            ad_res = call_api(1518, {"key": ad_key, "advertValue": 0.0}, datas)
            if (ad_res.get("raw") or {}).get("code") == 0:
                res = call_api(1303, body, datas)
                data = res.get("data_json") if isinstance(res.get("data_json"), dict) else {}
    for key in ("content", "chapterContent", "text", "txt"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    chapter = data.get("chapterInfo") or data.get("chapter") or {}
    if isinstance(chapter, dict):
        for key in ("content", "chapterContent", "text", "txt"):
            val = chapter.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


async def 下载全部章节(datas: dict[str, Any], 书籍编号: str, 目录: list[dict[str, Any]], 书名: str) -> list[dict[str, str]]:
    总数 = len(目录)
    结果: list[dict[str, str] | None] = [None] * 总数
    信号量 = asyncio.Semaphore(章节并发数)
    完成 = 0
    成功 = 0

    async def 拉一章(下标: int, 章: dict[str, Any]) -> None:
        nonlocal 完成, 成功
        cid = str(章.get("id") or "")
        标题 = str(章.get("title") or f"章节{cid}")
        正文 = ""
        async with 信号量:
            try:
                正文 = await asyncio.to_thread(_获取章节正文, datas, 书籍编号, cid, 书名)
            except Exception as exc:
                logger.warning(f"点众章节下载失败：book_id={书籍编号}, chapter_id={cid}, error={exc}")
        结果[下标] = {"title": 标题, "content": 正文, "id": cid}
        完成 += 1
        if 正文:
            成功 += 1
        if 完成 == 1 or 完成 == 总数 or 完成 % max(1, 总数 // 进度日志分段数) == 0:
            logger.info(
                f"点众小说章节进度：book_id={书籍编号}, progress={完成}/{总数}, "
                f"percent={int(完成 * 100 / max(总数, 1))}%, success={成功}, failed={完成 - 成功}"
            )

    await asyncio.gather(*(拉一章(i, 章) for i, 章 in enumerate(目录)))
    return [x for x in 结果 if x is not None]


def 生成小说文件(书籍编号: str, 书名: str, 作者: str, 状态: str, 字数: str, 章节结果: list[dict[str, str]]) -> tuple[str, bytes]:
    文件名 = f"[{状态}]书名：{清理文件名(书名)} 作者：{清理文件名(作者)}.txt"
    行 = [文件声明, "", f"名称：{书名}", f"作者：{作者}", f"状态：{状态}", f"字数：{字数}", f"书籍ID：{书籍编号}", f"章节数：{len(章节结果)}", ""]
    for 章 in 章节结果:
        if not 章.get("content"):
            continue
        行.extend([章.get("title") or "章节", "", 章["content"], ""])
    return 文件名, "\n".join(行).encode("utf-8")


async def 准备发送文本文件(event: Any, 文件名: str, 文件内容: bytes, 配置: Any = None, *, 书名: Any = "", 作者: Any = "") -> dict[str, Any]:
    缓存路径 = 写入缓存(文件名, 文件内容)
    if UC网盘 is None:
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "UC网盘模块未加载"}
    try:
        UC结果 = await UC网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not UC结果.get("success"):
            删除缓存(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(UC结果.get("error") or "UC网盘未启用")}
        完成结果 = await UC网盘.发送小说下载完成链接(event, 书名, 作者, str(UC结果.get("share_url") or ""))
        if 完成结果:
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        return {"sent": False, "fallback_text": "", "source_cache_path": 缓存路径, "error": "完成消息发送失败"}
    except Exception as exc:
        删除缓存(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(exc)}


def 启动百度后台上传并清理(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    async def _任务() -> None:
        try:
            if 百度网盘 is not None and 源缓存路径:
                await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
        except Exception as exc:
            logger.warning(f"点众小说百度后台上传异常：file={文件名}, error={exc}")
        finally:
            删除缓存(源缓存路径)
    try:
        asyncio.get_running_loop().create_task(_任务())
    except Exception:
        删除缓存(源缓存路径)


def 写入缓存(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 下载缓存目录 / 文件名
    序号 = 1
    while 路径.exists():
        路径 = 下载缓存目录 / f"{Path(文件名).stem}_{序号}.txt"
        序号 += 1
    路径.write_bytes(文件内容)
    return 路径


def 删除缓存(缓存路径: Any) -> None:
    try:
        if 缓存路径:
            Path(缓存路径).unlink(missing_ok=True)
    except Exception:
        pass


def 提取直接点众来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or "")
    if not 点众域名正则.search(文本) and "bookId=" not in 文本:
        # 仅当明确点众域名时识别，避免误伤
        if "dianzhong" not in 文本.lower():
            return None
    if not 点众域名正则.search(文本) and "dianzhong" not in 文本.lower():
        return None
    m = 链接正则.search(文本)
    return m.group(0) if m else 文本.strip() or None


def 提取事件点众来源(event: Any) -> str | None:
    for 字段 in ("message_str", "message", "raw_message"):
        值 = getattr(event, 字段, None)
        if 值 is None:
            continue
        来源 = 提取直接点众来源(str(值))
        if 来源:
            return 来源
    return None


def 提取书籍编号(来源: str) -> str:
    文本 = str(来源 or "")
    for 正则 in (书籍编号正则, 路径编号正则):
        m = 正则.search(文本)
        if m:
            return m.group(1)
    m = re.search(r"(\d{5,})", 文本)
    return m.group(1) if m else ""


def 格式化字数(字数: Any) -> str:
    文本 = str(字数 or "").strip()
    if not 文本:
        return "未知"
    if "字" in 文本:
        return 文本
    if str(文本).replace(".", "", 1).isdigit():
        try:
            n = int(float(文本))
        except Exception:
            return 文本
        return f"{round(n/10000, 1)}万字" if n >= 10000 else f"{n}字"
    return 文本


def 清理文件名(文件名: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", str(文件名 or "")).strip() or "未知"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    try:
        datas = await asyncio.to_thread(_获取设备)
        body = {"keyWord": 关键词, "page": 1, "type": 0}
        res = await asyncio.to_thread(call_api, 1203, body, datas)
    except Exception as exc:
        logger.warning(f"点众搜索失败：keyword={关键词}, error={exc}")
        return []
    data = res.get("data_json") if isinstance(res.get("data_json"), dict) else {}
    rows = data.get("bookList") or data.get("list") or data.get("books") or []
    if not isinstance(rows, list):
        rows = []
    结果 = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        book = item.get("bookInfo") if isinstance(item.get("bookInfo"), dict) else item
        book_id = str(book.get("bookId") or book.get("id") or "").strip()
        if not book_id:
            continue
        结果.append({
            "title": book.get("bookName") or book.get("title") or "未知",
            "author": book.get("authorName") or book.get("author") or "未知",
            "book_id": book_id,
            "platform": "点众",
            "url": f"https://asgportal.dianzhong.com/book/{book_id}",
            "heat": 0,
            "score": 0,
        })
        if len(结果) >= 需要数量:
            break
    return 结果