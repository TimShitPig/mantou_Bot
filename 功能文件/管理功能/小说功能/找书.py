from __future__ import annotations

import asyncio
import html
import json
import re
import time
import urllib.parse
from typing import Any, AsyncIterator

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能.权限工具 import 获取发送者QQ, 读取字段

try:
    from 功能文件.管理功能.基础功能.权限工具 import 是QQ官方机器人
except Exception:
    def 是QQ官方机器人(event: Any) -> bool:  # type: ignore
        return False

try:
    from 功能文件.管理功能.小说功能 import 七猫小说
except Exception as exc:
    七猫小说 = None
    logger.warning(f"找书加载七猫失败：error={exc}")

try:
    from 功能文件.管理功能.小说功能 import 书旗小说
except Exception as exc:
    书旗小说 = None
    logger.warning(f"找书加载书旗失败：error={exc}")

try:
    from 功能文件.管理功能.小说功能 import 番茄小说
except Exception as exc:
    番茄小说 = None
    logger.warning(f"找书加载番茄失败：error={exc}")


每页数量 = 5
会话等待秒数 = 300
找书会话: dict[str, dict[str, Any]] = {}
找书命令正则 = re.compile(r"^(?:找书|找)\s*(.+)$")
翻页命令集合 = {"上一页", "下一页", "上页", "下页", "上", "下"}
分隔线 = "————————"


def 清理文本(值: Any) -> str:
    文本 = html.unescape(str(值 or ""))
    文本 = re.sub(r"<[^>]+>", "", 文本)
    文本 = re.sub(r"\s+", " ", 文本).strip()
    return 文本


def 规范标题(值: Any) -> str:
    文本 = 清理文本(值).lower()
    文本 = re.sub(r"[\s\-_/\\|·•·【】\[\]（）()《》<>\"'“”‘’：:，,。.!！?？~～]+", "", 文本)
    return 文本


def 获取找书会话键(event: Any) -> str:
    群号 = 获取群号(event)
    用户 = 获取发送者QQ(event)
    return f"{群号 or 'private'}:{用户 or 'unknown'}"


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id",):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            try:
                值 = 方法()
            except Exception:
                continue
            if hasattr(值, "__await__"):
                continue
            if 值:
                return str(值)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "group_id")
        if 值:
            return str(值)
    return ""


def 清理过期会话() -> None:
    现在 = time.time()
    for 键 in [k for k, v in 找书会话.items() if 现在 - float(v.get("ts") or 0) > 会话等待秒数]:
        找书会话.pop(键, None)


def 解析找书关键词(命令文本: str) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None
    匹配 = 找书命令正则.match(文本)
    if not 匹配:
        return None
    关键词 = 清理文本(匹配.group(1))
    if not 关键词 or 关键词 in 翻页命令集合:
        return None
    # 避免误伤其他「找」开头命令
    if 关键词.startswith(("书登录", "书状态", "书清理")):
        return None
    return 关键词


def 构造番茄链接(书籍编号: str) -> str:
    return f"https://fanqienovel.com/page/{书籍编号}"


def 构造七猫链接(书籍编号: str, 是否短篇: bool = False) -> str:
    if 是否短篇:
        return f"https://app-share.wtzw.com/app-h5/freebook/short-story-detail/{书籍编号}"
    return f"https://www.qimao.com/shuku/{书籍编号}/"


def 构造书旗链接(书籍编号: str) -> str:
    return f"https://www.shuqi.com/book/{书籍编号}.html"


def _安全浮点(值: Any, 默认: float = 0.0) -> float:
    try:
        if 值 is None or 值 == "":
            return 默认
        return float(值)
    except Exception:
        return 默认


def _安全整数热度(值: Any) -> int:
    try:
        if 值 is None or 值 == "":
            return 0
        if isinstance(值, bool):
            return 0
        if isinstance(值, (int, float)):
            return int(值)
        文本 = str(值).strip().replace(",", "")
        if not 文本:
            return 0
        if 文本.endswith("亿"):
            return int(float(文本[:-1]) * 100000000)
        if 文本.endswith("万"):
            return int(float(文本[:-1]) * 10000)
        return int(float(文本))
    except Exception:
        return 0


def _格式化数量(数量: int) -> str:
    if 数量 >= 100000000:
        return f"{数量 / 100000000:.1f}".rstrip("0").rstrip(".") + "亿"
    if 数量 >= 10000:
        return f"{数量 / 10000:.1f}".rstrip("0").rstrip(".") + "万"
    return str(int(数量))


def 格式化热度显示(热度值: float, 评分: float = 0.0, 阅读量: int = 0) -> str:
    """优先展示阅读/订阅热度，其次评分；字数不算热度，不展示。"""
    if 阅读量 > 0:
        return _格式化数量(阅读量)
    if 评分 > 0:
        文本 = f"{评分:.1f}".rstrip("0").rstrip(".")
        return f"评分{文本}"
    return ""


def 计算热度排序值(阅读量: int = 0, 评分: float = 0.0, 字数: int = 0) -> float:
    """跨平台排序：阅读量 > 评分 > 字数兜底。分档避免字数冒充热度压过评分。"""
    if 阅读量 > 0:
        return 2_000_000_000_000.0 + float(阅读量) + 评分 * 1000.0
    if 评分 > 0:
        return 1_000_000_000_000.0 + 评分 * 1_000_000.0 + (字数 / 100.0)
    return float(字数)


def 提取番茄搜索书(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    books = row.get("books")
    book = books[0] if isinstance(books, list) and books and isinstance(books[0], dict) else None
    if book is None:
        book = row.get("book") or row.get("book_info") or row
    if not isinstance(book, dict):
        return None
    book_id = str(book.get("book_id") or row.get("book_id") or book.get("id") or "").strip()
    title = 清理文本(book.get("book_name") or book.get("title") or row.get("title") or "")
    author = 清理文本(book.get("author") or row.get("author") or "未知") or "未知"
    if not book_id or not book_id.isdigit() or not title:
        return None
    阅读量 = max(
        _安全整数热度(book.get("read_count")),
        _安全整数热度(book.get("play_num")),
        _安全整数热度(book.get("subscribe_num")),
        _安全整数热度(book.get("collect_num")),
        _安全整数热度(book.get("search_num")),
    )
    评分 = _安全浮点(book.get("score"))
    字数 = _安全整数热度(book.get("word_number") or book.get("word_count"))
    热度值 = 计算热度排序值(阅读量=阅读量, 评分=评分, 字数=字数)
    return {
        "platform": "番茄",
        "book_id": book_id,
        "title": title,
        "author": author,
        "url": 构造番茄链接(book_id),
        "heat": 热度值,
        "heat_text": 格式化热度显示(热度值, 评分=评分, 阅读量=阅读量),
        "score": 评分,
        "read_count": 阅读量,
    }


async def 搜索番茄(session: aiohttp.ClientSession, 关键词: str, *, 需要数量: int = 30) -> list[dict[str, Any]]:
    if 番茄小说 is None:
        return []
    结果: list[dict[str, str]] = []
    偏移 = 0
    每批 = 10
    while len(结果) < 需要数量 and 偏移 < 60:
        try:
            data = await asyncio.to_thread(
                番茄小说.signed_app_json,
                "/novelfm/bookmall/search/page/v1/",
                {"query": 关键词, "offset": 偏移, "limit": 每批},
                method="POST",
            )
        except Exception as exc:
            logger.warning(f"找书番茄搜索失败：keyword={关键词}, offset={偏移}, error={exc}")
            break
        if not isinstance(data, dict) or data.get("code") not in (0, "0", None):
            break
        d = data.get("data") if isinstance(data.get("data"), dict) else {}
        rows = d.get("search_data") or []
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            item = 提取番茄搜索书(row)
            if item:
                结果.append(item)
        if not d.get("has_more"):
            break
        偏移 = int(d.get("next_offset") or (偏移 + 每批))
        if 偏移 <= 0:
            偏移 += 每批
    return 结果[:需要数量]


async def 搜索七猫(session: aiohttp.ClientSession, 关键词: str, *, 需要数量: int = 30) -> list[dict[str, Any]]:
    if 七猫小说 is None:
        return []
    结果: list[dict[str, str]] = []
    页码 = 1
    while len(结果) < 需要数量 and 页码 <= 5:
        try:
            参数 = 七猫小说.签名参数({
                "extend": "",
                "tab": "0",
                "gender": "0",
                "refresh_state": "8",
                "page": str(页码),
                "wd": 关键词,
                "is_short_story_user": "0",
            })
            数据 = await 七猫小说.请求JSON(
                session,
                "https://api-bc.wtzw.com/search/v1/words",
                参数,
                七猫小说.生成请求头("00000000", "api-bc.wtzw.com"),
            )
        except Exception as exc:
            logger.warning(f"找书七猫搜索失败：keyword={关键词}, page={页码}, error={exc}")
            break
        书籍列表 = 七猫小说.读取字段路径(数据, ("data", "books")) if hasattr(七猫小说, "读取字段路径") else ((数据 or {}).get("data") or {}).get("books")
        if not isinstance(书籍列表, list) or not 书籍列表:
            break
        for 书籍 in 书籍列表:
            if not isinstance(书籍, dict):
                continue
            book_id = str(书籍.get("id") or "").strip()
            title = 清理文本(书籍.get("title") or 书籍.get("original_title") or "")
            author = 清理文本(书籍.get("author") or 书籍.get("original_author") or "未知") or "未知"
            if not book_id or not title:
                continue
            reader_type = str(书籍.get("reader_type") or 书籍.get("type") or "")
            是否短篇 = reader_type in {"4", "short"} or "短篇" in str(书籍.get("sub_title") or "")
            评分 = _安全浮点(书籍.get("score"))
            字数 = _安全整数热度(书籍.get("words_num") or 书籍.get("word_count") or 书籍.get("words"))
            # sub_title 里常有「653万字」
            if 字数 <= 0:
                副 = str(书籍.get("sub_title") or "")
                m = re.search(r"([\d.]+)\s*万字", 副)
                if m:
                    字数 = int(float(m.group(1)) * 10000)
            热度值 = 计算热度排序值(评分=评分, 字数=字数)
            结果.append({
                "platform": "七猫",
                "book_id": book_id,
                "title": title,
                "author": author,
                "url": 构造七猫链接(book_id, 是否短篇),
                "heat": 热度值,
                "heat_text": 格式化热度显示(热度值, 评分=评分, 阅读量=0),
                "score": 评分,
                "read_count": 0,
            })
        if len(书籍列表) < 8:
            break
        页码 += 1
    return 结果[:需要数量]


def 从对象提取书旗书(obj: dict[str, Any]) -> dict[str, Any] | None:
    book_id = str(obj.get("bookId") or obj.get("bid") or obj.get("id") or "").strip()
    title = 清理文本(obj.get("bookName") or obj.get("displayBookName") or obj.get("title") or obj.get("name") or "")
    if not book_id.isdigit() or not title:
        return None
    author = 清理文本(obj.get("authorName") or obj.get("author") or "未知") or "未知"
    评分 = _安全浮点(obj.get("novelScore") or obj.get("score"))
    字数 = _安全整数热度(obj.get("wordCount") or obj.get("words") or obj.get("word_count"))
    阅读量 = max(
        _安全整数热度(obj.get("readCount")),
        _安全整数热度(obj.get("hotValue")),
        _安全整数热度(obj.get("hot")),
        _安全整数热度(obj.get("clickCount")),
    )
    热度值 = 计算热度排序值(阅读量=阅读量, 评分=评分, 字数=字数)
    return {
        "platform": "书旗",
        "book_id": book_id,
        "title": title,
        "author": author,
        "url": 构造书旗链接(book_id),
        "heat": 热度值,
        "heat_text": 格式化热度显示(热度值, 评分=评分, 阅读量=阅读量),
        "score": 评分,
        "read_count": 阅读量,
    }


def 遍历书旗搜索结果(obj: Any, out: list[dict[str, Any]], seen: set[str]) -> None:
    if isinstance(obj, dict):
        item = 从对象提取书旗书(obj)
        if item and item["book_id"] not in seen:
            # 优先 book 节点
            if any(k in obj for k in ("bookId", "bookName", "displayBookName", "authorName")) or "book" in obj:
                if "book" in obj and isinstance(obj["book"], dict):
                    item2 = 从对象提取书旗书(obj["book"])
                    if item2 and item2["book_id"] not in seen:
                        seen.add(item2["book_id"])
                        out.append(item2)
                elif item["book_id"] not in seen and (obj.get("bookId") or obj.get("bookName") or obj.get("displayBookName")):
                    seen.add(item["book_id"])
                    out.append(item)
        for value in obj.values():
            遍历书旗搜索结果(value, out, seen)
    elif isinstance(obj, list):
        for value in obj:
            遍历书旗搜索结果(value, out, seen)


async def 搜索书旗(session: aiohttp.ClientSession, 关键词: str, *, 需要数量: int = 30) -> list[dict[str, Any]]:
    if 书旗小说 is None:
        return []
    结果: list[dict[str, str]] = []
    seen: set[str] = set()
    页码 = 1
    while len(结果) < 需要数量 and 页码 <= 5:
        try:
            params = {
                "_public": 书旗小说.构造公共参数(书旗小说.DEFAULT_USER_ID, "an"),
                "page": "searchResultV3",
                "query": 关键词,
                "fromSug": "0",
                "kind": "",
                "relatedBid": "",
                "showMore": "0",
                "showPost": "0",
                "showTypes": "",
                "pagination": json.dumps({"page": 页码, "pageSize": 20}, ensure_ascii=False),
                "isTeenMode": "0",
            }
            signed = 书旗小说.签名参数(params, add_reqid=False)
            url = f"https://ocean.shuqireader.com/sqan/render/render/search/native_v3?_reqid={书旗小说.请求ID()}"
            headers = {
                "User-Agent": 书旗小说.APP_USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            async with session.post(url, data=signed, headers=headers) as resp:
                文本 = await resp.text(errors="ignore")
            data = json.loads(文本) if 文本 else {}
        except Exception as exc:
            logger.warning(f"找书书旗搜索失败：keyword={关键词}, page={页码}, error={exc}")
            break
        if str(data.get("status") or data.get("state") or "") not in {"200", "0"}:
            break
        before = len(结果)
        遍历书旗搜索结果(data.get("data", data), 结果, seen)
        if len(结果) == before:
            break
        页码 += 1
    return 结果[:需要数量]


async def 搜索书旗联想(session: aiohttp.ClientSession, 关键词: str) -> list[str]:
    if 书旗小说 is None:
        return []
    try:
        params = {
            "_public": 书旗小说.构造公共参数(书旗小说.DEFAULT_USER_ID, "an"),
            "query": 关键词,
            "isTeenMode": "0",
        }
        signed = 书旗小说.签名参数(params, add_reqid=False)
        url = f"https://ocean.shuqireader.com/sqan/render/render/search/findSuggest?_reqid={书旗小说.请求ID()}"
        headers = {
            "User-Agent": 书旗小说.APP_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        async with session.post(url, data=signed, headers=headers) as resp:
            文本 = await resp.text(errors="ignore")
        data = json.loads(文本) if 文本 else {}
    except Exception as exc:
        logger.debug(f"找书书旗联想失败：keyword={关键词}, error={exc}")
        return []
    建议: list[str] = []
    seen: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key in ("query", "word", "keyword", "title", "name", "sug", "suggest"):
                val = 清理文本(obj.get(key))
                if val and val not in seen and val != 关键词:
                    seen.add(val)
                    建议.append(val)
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                if isinstance(value, str):
                    val = 清理文本(value)
                    if val and val not in seen and val != 关键词:
                        seen.add(val)
                        建议.append(val)
                else:
                    walk(value)

    walk(data.get("data", data))
    return 建议[:8]


def 去重合并(结果列表: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """同平台同书去重；不同平台即使同名也分开保留；最终按热度从高到低排序。"""
    合并: list[dict[str, Any]] = []
    索引: set[str] = set()
    for 列表 in 结果列表:
        for 项 in 列表:
            平台 = str(项.get("platform") or "")
            标题 = 规范标题(项.get("title"))
            作者 = 规范标题(项.get("author"))
            book_id = str(项.get("book_id") or "")
            键 = f"{平台}|{book_id}|{标题}|{作者}"
            if 键 in 索引:
                continue
            索引.add(键)
            if "heat" not in 项:
                项["heat"] = 0
            if not 项.get("heat_text"):
                项["heat_text"] = 格式化热度显示(
                    float(项.get("heat") or 0),
                    评分=_安全浮点(项.get("score")),
                    阅读量=_安全整数热度(项.get("read_count")),
                )
            合并.append(项)
    合并.sort(key=lambda x: float(x.get("heat") or 0), reverse=True)
    return 合并


async def 聚合搜索(关键词: str) -> list[dict[str, Any]]:
    timeout = aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        番茄任务 = asyncio.create_task(搜索番茄(session, 关键词))
        七猫任务 = asyncio.create_task(搜索七猫(session, 关键词))
        书旗任务 = asyncio.create_task(搜索书旗(session, 关键词))
        联想任务 = asyncio.create_task(搜索书旗联想(session, 关键词))
        番茄结果, 七猫结果, 书旗结果, 联想词 = await asyncio.gather(
            番茄任务, 七猫任务, 书旗任务, 联想任务, return_exceptions=False
        )
        合并 = 去重合并([番茄结果, 七猫结果, 书旗结果])
        # 结果太少时，用联想词补搜
        if len(合并) < 每页数量 and 联想词:
            补搜词 = [w for w in 联想词 if 规范标题(w) != 规范标题(关键词)][:3]
            补任务 = [
                搜索番茄(session, w, 需要数量=10),
                搜索七猫(session, w, 需要数量=10),
                搜索书旗(session, w, 需要数量=10),
            ] if False else []
            # 并行补搜每个联想词
            补结果集合: list[list[dict[str, Any]]] = [番茄结果, 七猫结果, 书旗结果]
            for w in 补搜词:
                t1 = asyncio.create_task(搜索番茄(session, w, 需要数量=10))
                t2 = asyncio.create_task(搜索七猫(session, w, 需要数量=10))
                t3 = asyncio.create_task(搜索书旗(session, w, 需要数量=10))
                r1, r2, r3 = await asyncio.gather(t1, t2, t3)
                补结果集合.extend([r1, r2, r3])
            合并 = 去重合并(补结果集合)
        return 合并


def 格式化找书结果(会话: dict[str, Any]) -> str:
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    总页 = max(1, (len(结果) + 每页数量 - 1) // 每页数量) if 结果 else 1
    if 页码 > 总页:
        页码 = 总页
        会话["page"] = 页码
    起始 = (页码 - 1) * 每页数量
    当前页 = 结果[起始:起始 + 每页数量]
    行: list[str] = []
    if not 当前页:
        行.append("没有找到相关书籍")
    else:
        for 项 in 当前页:
            行.append(分隔线)
            行.append(f"书名：{项.get('title') or '未知'}")
            行.append(f"作者：{项.get('author') or '未知'}")
            热度文案 = str(项.get("heat_text") or "").strip()
            if 热度文案:
                行.append(f"热度：{热度文案}")
        行.append(分隔线)
    行.append(f"当前页数：{页码}/{总页}")
    左 = "上一页" if 页码 > 1 else ""
    右 = "下一页" if 页码 < 总页 else ""
    if 左 or 右:
        行.append(f"       {左}                           {右}".rstrip())
    if 当前页:
        行.append("发送 选1～选5 下载当前页对应书籍")
    return "\n".join(行)


def _指令链编码(文本: str) -> str:
    值 = str(文本 or "")
    if len(值) > 100:
        值 = 值[:100]
    return urllib.parse.quote(值, safe="")


def _生成指令链(发送文本: str, 外显: str, *, 直接发送: bool) -> str:
    """QQ 官方 Markdown 指令链：私聊 enter 直接发送，群聊 input 填入输入框。"""
    text = _指令链编码(发送文本)
    show = _指令链编码(外显 or 发送文本)
    if 直接发送:
        return f'<qqbot-cmd-enter text="{text}" show="{show}" />'
    return f'<qqbot-cmd-input text="{text}" show="{show}" reference="false" />'


def 格式化找书结果MD(会话: dict[str, Any], *, 直接发送: bool = True) -> str:
    """官方机器人 Markdown：书名/作者为指令链蓝字，展示热度，不展示来源/链接/键盘。"""
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    总页 = max(1, (len(结果) + 每页数量 - 1) // 每页数量) if 结果 else 1
    if 页码 > 总页:
        页码 = 总页
        会话["page"] = 页码
    起始 = (页码 - 1) * 每页数量
    当前页 = 结果[起始:起始 + 每页数量]
    行: list[str] = ["**找书结果**", ""]
    if not 当前页:
        行.append("没有找到相关书籍")
    else:
        for 序号, 项 in enumerate(当前页, start=1):
            书名 = 清理文本(项.get("title") or "未知") or "未知"
            作者 = 清理文本(项.get("author") or "未知") or "未知"
            选书指令 = f"选{序号}"
            热度文案 = str(项.get("heat_text") or "").strip()
            行.append(分隔线)
            行.append(f"书名：{_生成指令链(选书指令, 书名, 直接发送=直接发送)}")
            行.append(f"作者：{_生成指令链(选书指令, 作者, 直接发送=直接发送)}")
            if 热度文案:
                行.append(f"热度：{热度文案}")
        行.append(分隔线)
    行.append(f"当前页数：{页码}/{总页}")
    翻页: list[str] = []
    if 页码 > 1:
        翻页.append(_生成指令链("上一页", "上一页", 直接发送=直接发送))
    if 页码 < 总页:
        翻页.append(_生成指令链("下一页", "下一页", 直接发送=直接发送))
    if 翻页:
        行.append(" ".join(翻页))
    if 当前页:
        行.append("点击书名即可开始下载" if 直接发送 else "点击书名填入指令后发送即可下载")
    return "\n".join(行)


def 获取当前页结果(会话: dict[str, Any]) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    起始 = (页码 - 1) * 每页数量
    return 结果[起始:起始 + 每页数量]


选书命令正则 = re.compile(r"^选([1-5])$")


def 解析找书选中项(event: Any, 命令文本: str) -> dict[str, Any] | str | None:
    """识别指令链/选N，映射当前页第 N 本书。"""
    清理过期会话()
    文本 = str(命令文本 or "").strip()
    匹配 = 选书命令正则.fullmatch(文本)
    if not 匹配:
        return None
    会话 = 找书会话.get(获取找书会话键(event))
    if not 会话:
        return "找书结果已过期，请重新发送 找 关键词"
    会话["ts"] = time.time()
    当前页 = 获取当前页结果(会话)
    if not 当前页:
        return "没有可选书籍"
    序号 = int(匹配.group(1))
    if 序号 < 1 or 序号 > len(当前页):
        return "下载失败"
    return 当前页[序号 - 1]


def 获取找书下载回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | str | None:
    选中 = 解析找书选中项(event, 命令文本)
    if 选中 is None:
        return None
    if isinstance(选中, str):
        return 选中
    平台 = str(选中.get("platform") or "")
    链接 = str(选中.get("url") or "")
    标题 = 选中.get("title") or ""
    logger.info(f"找书选择下载：platform={平台}, title={标题}, book_id={选中.get('book_id')}")
    if not 链接:
        return "下载失败"
    if 平台 == "番茄" and 番茄小说 is not None:
        return 番茄小说.生成番茄下载回复流(event, 链接, 配置)
    if 平台 == "七猫" and 七猫小说 is not None:
        return 七猫小说.生成下载回复流(event, 链接, 配置)
    if 平台 == "书旗" and 书旗小说 is not None:
        return 书旗小说.生成下载回复流(event, 链接, 配置)
    return "下载失败"


async def 处理找书指令(event: Any, 命令文本: str, 配置: Any = None) -> str | dict[str, Any] | None:
    """返回纯文本；官方机器人返回 {md, keyboard=None, text}，md 内嵌指令链。"""
    清理过期会话()
    文本 = str(命令文本 or "").strip()
    会话键 = 获取找书会话键(event)
    关键词 = 解析找书关键词(文本)
    会话 = None
    if 关键词 is not None:
        try:
            结果 = await 聚合搜索(关键词)
        except Exception as exc:
            logger.warning(f"找书搜索失败：keyword={关键词}, error={exc}")
            return "搜索失败，请稍后再试"
        会话 = {
            "keyword": 关键词,
            "results": 结果,
            "page": 1,
            "ts": time.time(),
        }
        找书会话[会话键] = 会话
        logger.info(f"找书搜索完成：keyword={关键词}, total={len(结果)}, session={会话键}")
        if not 结果:
            return f"没有找到和「{关键词}」相关的书"
    else:
        # 选书指令由 获取找书下载回复流 处理，这里直接跳过
        if 选书命令正则.fullmatch(文本):
            return None
        if 文本 not in 翻页命令集合:
            return None
        会话 = 找书会话.get(会话键)
        if not 会话:
            return None
        会话["ts"] = time.time()
        页码 = max(1, int(会话.get("page") or 1))
        总页 = max(1, (len(会话.get("results") or []) + 每页数量 - 1) // 每页数量)
        if 文本 in {"上一页", "上页", "上"}:
            if 页码 <= 1:
                return "已经是第一页了"
            会话["page"] = 页码 - 1
        elif 文本 in {"下一页", "下页", "下"}:
            if 页码 >= 总页:
                return "已经是最后一页了"
            会话["page"] = 页码 + 1
        else:
            return None

    if 会话 is None:
        return None
    if 是QQ官方机器人(event):
        # 回车指令链仅私聊可用；群聊使用 input 指令链
        直接发送 = not bool(获取群号(event))
        return {
            "md": 格式化找书结果MD(会话, 直接发送=直接发送),
            "keyboard": None,
            "text": 格式化找书结果(会话),
        }
    return 格式化找书结果(会话)


def 是否找书翻页会话(event: Any) -> bool:
    清理过期会话()
    return 获取找书会话键(event) in 找书会话
