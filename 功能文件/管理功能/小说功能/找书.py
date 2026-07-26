from __future__ import annotations

import asyncio
import html
import json
import re
import time
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
找书按钮最大行数 = 5
找书按钮标签最大长度 = 12
静默找书按钮前缀 = "找书:"
# 找书列表中的番茄记录有一部分已下线，只能从搜索接口拿到壳信息。
# 搜索时只预检最可能展示在前面的候选，避免用户点击后才发现没有目录。
番茄目录预检缓存秒数 = 600
番茄目录预检并发数 = 4
番茄目录预检最大候选数 = 8
番茄目录预检缓存: dict[str, tuple[float, bool | None]] = {}


def 清理文本(值: Any) -> str:
    文本 = html.unescape(str(值 or ""))
    文本 = re.sub(r"<[^>]+>", "", 文本)
    文本 = re.sub(r"\s+", " ", 文本).strip()
    return 文本


def 规范标题(值: Any) -> str:
    文本 = 清理文本(值).lower()
    文本 = re.sub(r"[\s\-_/\\|·•·【】\[\]（）()《》<>\"'“”‘’：:，,。.!！?？~～]+", "", 文本)
    return 文本


def _收集事件对象(event: Any) -> list[Any]:
    候选: list[Any] = [event, getattr(event, "message_obj", None), getattr(event, "raw_message", None)]
    消息对象 = getattr(event, "message_obj", None)
    if 消息对象 is not None:
        候选.extend([
            getattr(消息对象, "raw_message", None),
            getattr(消息对象, "raw", None),
            getattr(消息对象, "data", None),
            getattr(消息对象, "extra", None),
        ])
    结果: list[Any] = []
    for 对象 in 候选:
        if 对象 is None:
            continue
        if isinstance(对象, str):
            文本 = 对象.strip()
            if not 文本:
                continue
            try:
                对象 = json.loads(文本)
            except Exception:
                continue
        结果.append(对象)
        if isinstance(对象, dict):
            for 键 in ("d", "data", "interaction", "payload", "event", "raw"):
                内 = 对象.get(键)
                if 内 is not None:
                    结果.append(内)
    return 结果


def 获取找书会话键(event: Any) -> str:
    群号 = 获取群号(event)
    用户 = 获取找书用户标识(event)
    return f"{群号 or 'private'}:{用户 or 'unknown'}"


def 获取找书用户标识(event: Any) -> str:
    用户 = 获取发送者QQ(event)
    if 用户:
        return 用户
    for 对象 in _收集事件对象(event):
        for 字段名 in (
            "user_openid",
            "group_member_openid",
            "member_openid",
            "openid",
            "user_id",
            "sender_id",
        ):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("user_id") or 值.get("id") or 值.get("openid") or 值.get("user_openid")
            if 值:
                return str(值)
        author = 读取字段(对象, "author") or 读取字段(对象, "user") or 读取字段(对象, "member")
        if isinstance(author, dict):
            for 字段名 in ("user_openid", "member_openid", "id", "user_id", "openid"):
                值 = author.get(字段名)
                if 值:
                    return str(值)
    return ""


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
        值 = 读取字段(对象, "group_id") or 读取字段(对象, "group_openid")
        if 值:
            return str(值)
    for 对象 in _收集事件对象(event):
        for 字段名 in ("group_id", "group_openid", "group_open_id"):
            值 = 读取字段(对象, 字段名)
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
    """仅内部兼容保留，找书结果不再展示热度。"""
    if 阅读量 > 0:
        return _格式化数量(阅读量)
    if 评分 > 0:
        文本 = f"{评分:.1f}".rstrip("0").rstrip(".")
        return f"评分{文本}"
    return ""


def 计算热度排序值(阅读量: int = 0, 评分: float = 0.0, 字数: int = 0) -> float:
    """平台内热度参考值，仅用于同平台归一化，不直接跨平台比较。"""
    if 阅读量 > 0:
        return float(阅读量) + 评分 * 1000.0
    if 评分 > 0:
        return 评分 * 100000.0 + (字数 / 100.0)
    return float(字数) / 1000.0


def 计算标题相关度(标题: str, 关键词: str) -> float:
    """搜索相关度：精确书名优先，避免各平台原始阅读量互相碾压。"""
    原标题 = 清理文本(标题)
    t = 规范标题(标题)
    k = 规范标题(关键词)
    if not k or not t:
        return 0.0
    if t == k:
        return 10000.0
    去后缀 = t
    for 后缀 in ("原版小说", "原版", "动漫版", "广播剧", "同人", "后续", "续写", "新书", "大全集", "全集", "完本"):
        s = 规范标题(后缀)
        if s and 去后缀.endswith(s) and len(去后缀) > len(s):
            去后缀 = 去后缀[: -len(s)]
            break
    if 去后缀 == k:
        return 8200.0
    if t.startswith(k):
        多余 = len(t) - len(k)
        分 = 7000.0 - 多余 * 40.0
        if "：" in 原标题 or ":" in 原标题 or "·" in 原标题:
            分 -= 500.0
        return max(分, 4200.0)
    if k in t:
        位置 = t.find(k)
        多余 = len(t) - len(k)
        分 = 3800.0 - 位置 * 15.0 - 多余 * 25.0
        if "：" in 原标题 or ":" in 原标题:
            分 -= 400.0
        for 词 in ("同人", "衍生", "续写", "后续", "之旅", "系统"):
            if 词 in 原标题:
                分 -= 150.0
        return max(分, 300.0)
    return 50.0


def 排序找书结果(结果: list[dict[str, Any]], 关键词: str) -> list[dict[str, Any]]:
    """通用找书排序（不写死书名）：

    1) 先选用户最可能要的那本：精确书名 > 近精确 > 前缀/包含；
       同档内优先「多平台同名同作者共识」，再参考评分与平台内相对热度。
    2) 再把剩余结果按与第一本的相似度聚拢：同名多平台、同作者、同系列前缀。

    平台原始阅读量不可跨平台比较，只做平台内归一化参考；热度不展示给用户。
    """
    if not 结果:
        return []
    from collections import Counter

    关键词规范 = 规范标题(关键词)
    书名作者频次: Counter[tuple[str, str]] = Counter()
    书名频次: Counter[str] = Counter()
    精确书名作者频次: Counter[tuple[str, str]] = Counter()

    for 项 in 结果:
        t0 = 规范标题(项.get("title"))
        a0 = 规范标题(项.get("author"))
        书名作者频次[(t0, a0)] += 1
        书名频次[t0] += 1
        if 关键词规范 and t0 == 关键词规范:
            精确书名作者频次[(t0, a0)] += 1

    平台原始: dict[str, list[float]] = {}
    for 项 in 结果:
        平台 = str(项.get("platform") or "")
        平台原始.setdefault(平台, []).append(float(项.get("heat") or 0))
    平台区间: dict[str, tuple[float, float]] = {
        平台: ((min(vals), max(vals)) if vals else (0.0, 0.0))
        for 平台, vals in 平台原始.items()
    }

    def 平台内相对热度(项: dict[str, Any]) -> float:
        平台 = str(项.get("platform") or "")
        lo, hi = 平台区间.get(平台, (0.0, 0.0))
        raw = float(项.get("heat") or 0)
        if hi > lo:
            return (raw - lo) / (hi - lo)
        return 0.5

    def 标题信息(项: dict[str, Any]) -> tuple[str, str, str]:
        标题 = str(项.get("title") or "")
        作者 = str(项.get("author") or "")
        return 标题, 规范标题(标题), 规范标题(作者)

    def 基础分(项: dict[str, Any]) -> tuple:
        标题, t1, a1 = 标题信息(项)
        相关度 = 计算标题相关度(标题, 关键词)
        共识作者 = 书名作者频次.get((t1, a1), 1)
        共识书名 = 书名频次.get(t1, 1)
        精确共识 = 精确书名作者频次.get((t1, a1), 0)
        # 硬档：精确匹配书名永远压过带后缀/同人
        if 关键词规范 and t1 == 关键词规范:
            档 = 3
            相关度 += 精确共识 * 500.0 + 共识作者 * 200.0 + 共识书名 * 80.0
        else:
            档 = 2 if 相关度 >= 8000 else (1 if 相关度 >= 4000 else 0)
            相关度 += 共识作者 * 90.0 + 共识书名 * 30.0
        评分 = _安全浮点(项.get("score"))
        相对热度 = 平台内相对热度(项)
        有效作者 = 1 if a1 and a1 not in {"未知", "unknown", ""} else 0
        平台分 = _平台优先级值(项.get("platform"))
        return (档, 相关度, 精确共识, 共识作者, 平台分, 有效作者, 评分, 相对热度, -len(t1))

    def 公共前缀长度(a: str, b: str) -> int:
        n = 0
        for x, y in zip(a or "", b or ""):
            if x != y:
                break
            n += 1
        return n

    def 与锚点相似度(项: dict[str, Any], 锚点: dict[str, Any]) -> float:
        _, t1, a1 = 标题信息(项)
        _, at, aa = 标题信息(锚点)
        s = 0.0
        if a1 and aa and a1 == aa and a1 not in {"", "未知", "unknown"}:
            s += 6000.0
        if t1 and at and t1 == at:
            s += 5500.0
        if at and t1.startswith(at):
            s += max(3600.0 - (len(t1) - len(at)) * 40.0, 1400.0)
        elif t1 and at.startswith(t1):
            s += 3000.0
        pre = 公共前缀长度(t1, at)
        需要 = max(2, min(len(关键词规范), 4) if 关键词规范 else 2)
        if pre >= 需要:
            s += pre * 100.0
        if 关键词规范:
            if t1 == 关键词规范:
                s += 2500.0
            elif t1.startswith(关键词规范):
                s += 1000.0
            elif 关键词规范 in t1:
                s += 350.0
        s += 平台内相对热度(项) * 60.0
        s += _安全浮点(项.get("score")) * 15.0
        return s

    剩余 = list(结果)
    # 第一本：按“用户意图档位”选，不靠某个平台的绝对阅读量
    剩余.sort(key=基础分, reverse=True)
    已选: list[dict[str, Any]] = [剩余.pop(0)]

    while 剩余:
        def 选取键(项: dict[str, Any]) -> tuple:
            sim = 与锚点相似度(项, 已选[0]) + 与锚点相似度(项, 已选[-1]) * 0.4
            b = 基础分(项)
            return (sim, b[0], b[1], b[2], b[3], b[5], b[6])

        剩余.sort(key=选取键, reverse=True)
        已选.append(剩余.pop(0))
    return 已选


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


async def 预检番茄目录(书籍编号: str) -> bool | None:
    """返回番茄候选的目录状态。

    ``False`` 代表接口明确没有任何章节，应从找书结果中剔除；网络异常则
    返回 ``None``，保留候选，避免短暂网络波动把本来可下载的书误删。
    """
    书籍编号 = str(书籍编号 or "").strip()
    if not 书籍编号 or 番茄小说 is None:
        return None

    现在 = time.time()
    if len(番茄目录预检缓存) >= 512:
        for 缓存编号, (缓存时间, _缓存状态) in list(番茄目录预检缓存.items()):
            if 现在 - 缓存时间 >= 番茄目录预检缓存秒数:
                番茄目录预检缓存.pop(缓存编号, None)
    缓存 = 番茄目录预检缓存.get(书籍编号)
    if 缓存 is not None and 现在 - 缓存[0] < 番茄目录预检缓存秒数:
        return 缓存[1]

    状态: bool | None = None
    try:
        目录 = await asyncio.to_thread(番茄小说.resolve_directory, 书籍编号)
        状态 = bool(目录)
    except Exception as 异常:
        错误文本 = str(异常)
        # 目录接口正常返回、但没有章节，是已下线候选的稳定特征；其余
        # 网络/签名问题不能据此排除搜索结果。
        if "未返回章节" in 错误文本:
            状态 = False
        else:
            logger.debug(
                f"找书番茄目录预检暂不可判断：book_id={书籍编号}, error={错误文本}"
            )
    番茄目录预检缓存[书籍编号] = (现在, 状态)
    return 状态


def 获取番茄预检候选(结果: list[dict[str, Any]], 关键词: str, *, 最大数量: int = 番茄目录预检最大候选数) -> list[dict[str, Any]]:
    """优先预检精确书名，再补足最靠前的番茄搜索结果。"""
    关键词规范 = 规范标题(关键词)
    数量上限 = max(1, int(最大数量))
    已选编号: set[str] = set()
    候选: list[dict[str, Any]] = []

    def 加入(项: dict[str, Any]) -> None:
        书籍编号 = str(项.get("book_id") or "").strip()
        if not 书籍编号 or 书籍编号 in 已选编号:
            return
        已选编号.add(书籍编号)
        候选.append(项)

    # 精确书名即使在搜索接口的后面，也可能被最终排序推到首页。
    for 项 in 结果:
        if len(候选) >= 数量上限:
            break
        if 关键词规范 and 规范标题(项.get("title")) == 关键词规范:
            加入(项)

    其余 = sorted(
        结果,
        key=lambda 项: (
            计算标题相关度(str(项.get("title") or ""), 关键词),
            _安全浮点(项.get("score")),
            float(项.get("heat") or 0),
        ),
        reverse=True,
    )
    for 项 in 其余:
        if len(候选) >= 数量上限:
            break
        加入(项)
    return 候选


async def 过滤无目录番茄搜索结果(
    结果: list[dict[str, Any]],
    关键词: str,
    *,
    最大数量: int = 番茄目录预检最大候选数,
) -> list[dict[str, Any]]:
    """过滤已明确无目录的番茄候选，保留网络状态未知的候选。"""
    if not 结果 or 番茄小说 is None:
        return 结果

    候选 = 获取番茄预检候选(结果, 关键词, 最大数量=最大数量)
    if not 候选:
        return 结果

    限流 = asyncio.Semaphore(番茄目录预检并发数)

    async def 检查(项: dict[str, Any]) -> tuple[str, bool | None]:
        书籍编号 = str(项.get("book_id") or "").strip()
        async with 限流:
            return 书籍编号, await 预检番茄目录(书籍编号)

    预检结果 = await asyncio.gather(*(检查(项) for 项 in 候选), return_exceptions=False)
    状态表 = {书籍编号: 状态 for 书籍编号, 状态 in 预检结果}
    筛选后: list[dict[str, Any]] = []
    for 项 in 结果:
        书籍编号 = str(项.get("book_id") or "").strip()
        状态 = 状态表.get(书籍编号)
        if 状态 is False:
            logger.info(
                f"找书跳过无目录番茄候选：book_id={书籍编号}, "
                f"title={清理文本(项.get('title') or '')}"
            )
            continue
        if 状态 is True:
            项 = dict(项)
            项["目录可用"] = True
        筛选后.append(项)
    return 筛选后


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


def _平台优先级值(平台: Any) -> int:
    """下载速度优先：番茄 > 七猫 > 书旗。"""
    return {"番茄": 3, "七猫": 2, "书旗": 1}.get(str(平台 or ""), 0)


def _书籍优劣键(项: dict[str, Any]) -> tuple:
    """跨平台同书择优：平台(番茄>七猫>书旗) > 评分 > 热度参考 > 有效作者。"""
    作者 = 规范标题(项.get("author"))
    有效作者 = 1 if 作者 and 作者 not in {"未知", "unknown"} else 0
    return (
        _平台优先级值(项.get("platform")),
        _安全浮点(项.get("score")),
        float(项.get("heat") or 0),
        有效作者,
    )


def 去重合并(结果列表: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """同书去重：同平台同ID去重，跨平台同名同作者只保留最优一本。"""
    合并: list[dict[str, Any]] = []
    平台书号索引: set[str] = set()
    书名作者位置: dict[str, int] = {}
    for 列表 in 结果列表:
        for 项 in 列表:
            平台 = str(项.get("platform") or "")
            标题 = 规范标题(项.get("title"))
            作者 = 规范标题(项.get("author"))
            book_id = str(项.get("book_id") or "")
            平台键 = f"{平台}|{book_id}|{标题}|{作者}"
            if 平台键 in 平台书号索引:
                continue
            if "heat" not in 项:
                项["heat"] = 0
            书名键 = f"{标题}|{作者}"
            if 书名键 in 书名作者位置:
                旧位 = 书名作者位置[书名键]
                if _书籍优劣键(项) > _书籍优劣键(合并[旧位]):
                    合并[旧位] = 项
                continue
            平台书号索引.add(平台键)
            书名作者位置[书名键] = len(合并)
            合并.append(项)
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
        # 先筛掉搜索接口仍会返回、但畅听目录已为空的番茄记录；必须在
        # 跨平台去重前处理，才能让同书的七猫/书旗候选正常补位。
        番茄结果 = await 过滤无目录番茄搜索结果(番茄结果, 关键词)
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
                r1 = await 过滤无目录番茄搜索结果(r1, w, 最大数量=5)
                补结果集合.extend([r1, r2, r3])
            合并 = 去重合并(补结果集合)
        return 排序找书结果(合并, 关键词)


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
        行.append(分隔线)
    行.append(f"当前页数：{页码}/{总页}")
    左 = "上一页" if 页码 > 1 else ""
    右 = "下一页" if 页码 < 总页 else ""
    if 左 or 右:
        行.append(f"       {左}                           {右}".rstrip())
    if 当前页:
        行.append("发送 选1～选5 或点击按钮下载")
    return "\n".join(行)


def _截断找书按钮标签(文本: str) -> str:
    文本 = str(文本 or "").strip()
    if len(文本) <= 找书按钮标签最大长度:
        return 文本
    return 文本[:找书按钮标签最大长度 - 1] + "…"


def _生成找书指令按钮(data: str, 标签: str, *, 按钮ID: str, 点击后: str = "处理中") -> dict[str, Any]:
    """QQ 官方原生回调按钮：点击后静默回调后端，不往聊天里发送指令。"""
    return {
        "id": 按钮ID[:40],
        "render_data": {
            "label": _截断找书按钮标签(标签),
            "visited_label": _截断找书按钮标签(点击后),
            "style": 1,
        },
        "action": {
            "type": 1,
            "permission": {"type": 2},
            "data": 静默找书按钮前缀 + data,
            "unsupport_tips": "当前客户端暂不支持该操作",
        },
    }


def 生成找书下载键盘(会话: dict[str, Any]) -> dict[str, Any] | None:
    """生成 QQ 官方找书回调键盘：点击书名后静默开始下载。

    每本书 1 行 1 个按钮（书名），最多 5 行；翻页并入最后一行，避免超限。
    """
    当前页 = 获取当前页结果(会话)
    if not 当前页:
        return None
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    总页 = max(1, (len(结果) + 每页数量 - 1) // 每页数量) if 结果 else 1
    行: list[dict[str, Any]] = []
    总数 = len(当前页)
    for 序号, 项 in enumerate(当前页, start=1):
        书名 = 清理文本(项.get("title") or "未知") or "未知"
        本行 = [_生成找书指令按钮(f"选{序号}", 书名, 按钮ID=f"fb{页码}t{序号}", 点击后="下载中")]
        if 序号 == 总数:
            if 页码 > 1:
                本行.insert(0, _生成找书指令按钮("上一页", "上一页", 按钮ID=f"fb{页码}p", 点击后="翻页中"))
            if 页码 < 总页:
                本行.append(_生成找书指令按钮("下一页", "下一页", 按钮ID=f"fb{页码}n", 点击后="翻页中"))
        行.append({"buttons": 本行})
    if len(行) > 找书按钮最大行数:
        行 = 行[:找书按钮最大行数]
    return {"rows": 行}


def 格式化找书结果MD(会话: dict[str, Any]) -> str:
    """官方机器人 Markdown 找书结果正文。

    下载交互走底部回调按钮（不发聊天消息）；正文只展示书名作者，不塞指令链。
    """
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
        for 项 in 当前页:
            书名 = 清理文本(项.get("title") or "未知") or "未知"
            作者 = 清理文本(项.get("author") or "未知") or "未知"
            行.append(分隔线)
            行.append(f"书名：{书名}")
            行.append(f"作者：{作者}")
        行.append(分隔线)
    行.append(f"当前页数：{页码}/{总页}")
    if 当前页:
        行.append("点击下方书名按钮即可下载")
    return "\n".join(行)


def 获取当前页结果(会话: dict[str, Any]) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    起始 = (页码 - 1) * 每页数量
    return 结果[起始:起始 + 每页数量]


选书命令正则 = re.compile(r"^选([1-5])$")


def 解析找书选中项(event: Any, 命令文本: str) -> dict[str, Any] | str | None:
    """识别点击指令链发来的 选N，映射当前页第 N 本并交给下载流。"""
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
    """main 优先调用：用户点击指令链发出 选N 后，这里直接进入各平台下载流。"""
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
    """返回纯文本；官方机器人返回 {md, keyboard=回调按钮, text}。"""
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
        return {
            "md": 格式化找书结果MD(会话),
            "keyboard": 生成找书下载键盘(会话),
            "text": 格式化找书结果(会话),
        }
    return 格式化找书结果(会话)


def _读取嵌套字段(对象: Any, *路径: str) -> Any:
    当前 = 对象
    for 键 in 路径:
        if 当前 is None:
            return None
        if isinstance(当前, dict):
            当前 = 当前.get(键)
            continue
        当前 = getattr(当前, 键, None)
    return 当前


def _规范找书按钮数据(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, dict):
        for 键 in ("button_data", "data", "id", "text", "value", "command"):
            内 = 值.get(键)
            if 内 is not None and not isinstance(内, (dict, list)):
                文本 = str(内).strip()
                if 文本:
                    return 文本
        resolved = 值.get("resolved")
        if isinstance(resolved, dict):
            return _规范找书按钮数据(resolved)
        return ""
    文本 = str(值).strip()
    if not 文本:
        return ""
    if 文本.startswith("{") and 文本.endswith("}"):
        try:
            return _规范找书按钮数据(json.loads(文本))
        except Exception:
            return 文本
    if 文本.startswith(静默找书按钮前缀):
        return 文本[len(静默找书按钮前缀):].strip()
    return 文本


def _是否找书按钮数据(文本: str) -> bool:
    文本 = str(文本 or "").strip()
    return bool(选书命令正则.fullmatch(文本) or 文本 in 翻页命令集合)


def _是否静默找书桥事件(event: Any) -> bool:
    """桥接后的互动已回应过 QQ，后续按普通选书命令处理即可。"""
    for 对象 in _收集事件对象(event):
        原始数据 = 读取字段(对象, "raw_data")
        if isinstance(原始数据, dict) and 原始数据.get("mantou_silent_findbook") is True:
            return True
    return False


def 提取找书交互数据(event: Any) -> tuple[str, str]:
    """从 QQ 官方 INTERACTION_CREATE / 适配器事件中提取 (interaction_id, 找书命令)。"""
    候选 = _收集事件对象(event)
    消息对象 = getattr(event, "message_obj", None)
    候选.extend([event, 消息对象])
    交互ID候选: list[str] = []
    按钮候选: list[str] = []
    疑似交互 = False

    for 对象 in 候选:
        if 对象 is None:
            continue
        类型值 = 读取字段(对象, "type") or 读取字段(对象, "event_type") or 读取字段(对象, "t")
        if 类型值 is not None:
            类型文本 = str(类型值).upper()
            if "INTERACTION" in 类型文本 or 类型文本 in {"11", "12", "INTERACTION_CREATE"}:
                疑似交互 = True
        if 读取字段(对象, "interaction_id") or 读取字段(对象, "chat_type") is not None:
            if 读取字段(对象, "data") is not None or 读取字段(对象, "resolved") is not None:
                疑似交互 = True

        for 路径 in (
            ("id",),
            ("interaction_id",),
            ("interaction", "id"),
            ("d", "id"),
            ("data", "id"),
            ("event_id",),
        ):
            值 = _读取嵌套字段(对象, *路径) if len(路径) > 1 else 读取字段(对象, 路径[0])
            if 值 and not str(值).startswith("ROBOT"):
                交互ID候选.append(str(值))

        for 路径 in (
            ("button_data",),
            ("data",),
            ("data", "data"),
            ("data", "resolved"),
            ("data", "resolved", "button_data"),
            ("data", "button_data"),
            ("d", "data"),
            ("d", "data", "resolved"),
            ("d", "data", "resolved", "button_data"),
            ("d", "data", "button_data"),
            ("interaction", "data"),
            ("interaction", "data", "resolved"),
            ("interaction", "data", "resolved", "button_data"),
            ("resolved", "button_data"),
            ("message_str",),
        ):
            值 = _读取嵌套字段(对象, *路径) if len(路径) > 1 else 读取字段(对象, 路径[0])
            文本 = _规范找书按钮数据(值)
            if _是否找书按钮数据(文本):
                按钮候选.append(文本)

    for 交互ID in 交互ID候选:
        for 文本 in 按钮候选:
            if _是否找书按钮数据(文本):
                return 交互ID, 文本

    for 文本 in 按钮候选:
        if _是否找书按钮数据(文本):
            return (交互ID候选[0] if 交互ID候选 else ""), 文本

    if 疑似交互:
        logger.warning(
            "找书交互解析失败：疑似 INTERACTION 但未识别按钮 data，"
            f"session={获取找书会话键(event)}, ids={交互ID候选[:3]}, buttons={按钮候选[:5]}"
        )
    return "", ""


async def 回应找书交互(event: Any, interaction_id: str, code: int = 0) -> bool:
    """官方要求：收到回调后 PUT /interactions/{id}，否则客户端一直 loading。"""
    if not interaction_id:
        return False
    bot = getattr(event, "bot", None)
    api = getattr(bot, "api", None) if bot else None
    _http = getattr(api, "_http", None) if api else None
    if _http is None:
        return False
    try:
        import botpy.http as _botpy_http
        Route = _botpy_http.Route
        route = Route("PUT", "/interactions/{interaction_id}", interaction_id=str(interaction_id))
        await _http.request(route, json={"code": int(code)})
        return True
    except Exception as exc:
        logger.warning(f"找书交互回应失败：id={interaction_id}, error={exc}")
        return False


async def 处理找书交互回调(event: Any, 配置: Any = None) -> str | dict[str, Any] | AsyncIterator[Any] | None:
    """处理原生回调按钮：聊天不出现点击消息，直接翻页或进入下载流。"""
    if _是否静默找书桥事件(event):
        return None
    interaction_id, data = 提取找书交互数据(event)
    if not data:
        return None
    会话键 = 获取找书会话键(event)
    if interaction_id:
        logger.info(f"找书交互回调：id={interaction_id}, data={data}, session={会话键}")
    await 回应找书交互(event, interaction_id, 0)
    下载 = 获取找书下载回复流(event, data, 配置)
    if 下载 is not None:
        return 下载
    return await 处理找书指令(event, data, 配置)


def 是否找书翻页会话(event: Any) -> bool:
    清理过期会话()
    return 获取找书会话键(event) in 找书会话
