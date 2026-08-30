from __future__ import annotations

import asyncio
import html
import json
import re
import time
import urllib.parse
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, AsyncIterator, Awaitable

import aiohttp

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from 功能文件.管理功能.基础功能.权限工具 import 获取发送者QQ, 读取字段
from 功能文件.管理功能.小说功能.功能 import 小说功能开关

try:
    from 功能文件.管理功能.基础功能.权限工具 import 是QQ官方机器人
except Exception:

    def 是QQ官方机器人(event: Any) -> bool:  # type: ignore
        return False


try:
    from 功能文件.管理功能.小说功能.小说 import 七猫小说
except Exception as exc:
    七猫小说 = None
    logger.warning(f"找书加载七猫失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 书旗小说
except Exception as exc:
    书旗小说 = None
    logger.warning(f"找书加载书旗失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 追书小说
except Exception as exc:
    追书小说 = None
    logger.warning(f"找书加载追书失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 番茄小说
except Exception as exc:
    番茄小说 = None
    logger.warning(f"找书加载番茄失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 得间小说
except Exception as exc:
    得间小说 = None
    logger.warning(f"找书加载得间失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 点众小说
except Exception as exc:
    点众小说 = None
    logger.warning(f"找书加载点众失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import QQ阅读 as QQ阅读小说
except Exception as exc:
    QQ阅读小说 = None
    logger.warning(f"找书加载QQ阅读失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import QQ浏览器小说
except Exception as exc:
    QQ浏览器小说 = None
    logger.warning(f"找书加载QQ浏览器失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 塔读小说
except Exception as exc:
    塔读小说 = None
    logger.warning(f"找书加载塔读失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 百度小说
except Exception as exc:
    百度小说 = None
    logger.warning(f"找书加载百度失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 小米小说
except Exception as exc:
    小米小说 = None
    logger.warning(f"找书加载小米失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 宜搜小说
except Exception as exc:
    宜搜小说 = None
    logger.warning(f"找书加载宜搜失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 米读小说
except Exception as exc:
    米读小说 = None
    logger.warning(f"找书加载米读失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 猫眼小说
except Exception as exc:
    猫眼小说 = None
    logger.warning(f"找书加载猫眼失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 酷我小说
except Exception as exc:
    酷我小说 = None
    logger.warning(f"找书加载酷我失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 酷匠小说
except Exception as exc:
    酷匠小说 = None
    logger.warning(f"找书加载酷匠失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 连城小说
except Exception as exc:
    连城小说 = None
    logger.warning(f"找书加载连城失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 菠萝包小说
except Exception as exc:
    菠萝包小说 = None
    logger.warning(f"找书加载菠萝包失败：错误={exc}")

try:
    from 功能文件.管理功能.小说功能.小说 import 晋江小说
except Exception as exc:
    晋江小说 = None
    logger.warning(f"找书加载晋江失败：错误={exc}")


每页数量 = 5
会话等待秒数 = 300
找书搜索候选数量 = 15
找书单平台超时秒数 = 12.0
找书联想超时秒数 = 5.0
找书结果缓存秒数 = 60.0
找书结果缓存上限 = 128
找书会话: dict[str, dict[str, Any]] = {}
找书结果缓存: dict[
    tuple[str, str, tuple[str, ...]], tuple[float, list[dict[str, Any]]]
] = {}
找书命令正则 = re.compile(r"^(?:找书|找)\s*(.+)$")
找书名命令正则 = re.compile(r"^找(?:书名|小说名)\s*[:：]?\s*(.+)$")
找作者命令正则 = re.compile(r"^找(?:作者|作家)\s*[:：]?\s*(.+)$")
空找书模式正则 = re.compile(r"^找(?:书名|小说名|作者|作家)\s*[:：]?\s*$")
查询书名模式正则 = re.compile(r"^(?:书名|小说名)\s*[:：]?\s*(.+)$")
查询作者模式正则 = re.compile(r"^(?:作者|作家)\s*[:：]?\s*(.+)$")
翻页命令集合 = {"上一页", "下一页", "上页", "下页", "上", "下"}
分隔线 = "————————"
# 找书列表中的番茄记录有一部分已下线，只能从搜索接口拿到壳信息。
# 搜索时只预检最可能展示在前面的候选，避免用户点击后才发现没有目录。
番茄目录预检缓存秒数 = 600
番茄目录预检并发数 = 4
番茄目录预检最大候选数 = 8
番茄目录预检缓存: dict[str, tuple[float, bool | None]] = {}
# QQ 阅读找书会保留有免费章节的 VIP/单章付费书籍；搜索候选必须先完成详情
# 与完整目录预检，没有可下载免费章节或目录不完整时不保留。
QQ阅读预检缓存秒数 = 600
QQ阅读预检并发数 = 5
QQ阅读预检缓存: dict[str, tuple[float, bool]] = {}


def _规范化允许平台(允许平台: Any = None) -> frozenset[str]:
    """把调用方提供的平台集合规范化；省略时保持旧的全平台搜索行为。"""
    if 允许平台 is None:
        return frozenset(小说功能开关.默认状态)
    if isinstance(允许平台, str):
        值列表 = [允许平台]
    else:
        try:
            值列表 = list(允许平台)
        except TypeError:
            值列表 = []
    return frozenset(
        str(值).strip()
        for 值 in 值列表
        if str(值).strip() in 小说功能开关.默认状态
    )


def _过滤不可用平台结果(
    结果: Any, 允许平台: frozenset[str]
) -> list[dict[str, Any]]:
    """只保留当前事件允许使用的平台结果，避免旧缓存/会话泄漏关闭平台。"""
    if not isinstance(结果, list):
        return []
    return [
        项
        for 项 in 结果
        if isinstance(项, dict)
        and str(项.get("platform") or "").strip() in 允许平台
    ]


def _更新会话可用结果(会话: dict[str, Any], 允许平台: frozenset[str]) -> bool:
    """刷新会话中的平台结果并返回是否因开关变化而移除了项目。"""
    原结果 = 会话.get("results")
    新结果 = _过滤不可用平台结果(原结果, 允许平台)
    会话["results"] = 新结果
    当前平台快照 = tuple(sorted(允许平台))
    旧平台快照 = 会话.get("allowed_platforms")
    平台集合已变化 = (
        isinstance(旧平台快照, (list, tuple, set, frozenset))
        and tuple(sorted(str(平台) for 平台 in 旧平台快照)) != 当前平台快照
    )
    会话["allowed_platforms"] = 当前平台快照
    return (
        平台集合已变化
        or not isinstance(原结果, list)
        or len(新结果) != len(原结果)
    )


async def _空搜索结果() -> list[Any]:
    """占位搜索任务；平台关闭时不创建任何网络请求。"""
    return []


def 清理文本(值: Any) -> str:
    文本 = html.unescape(str(值 or ""))
    文本 = re.sub(r"<[^>]+>", "", 文本)
    文本 = re.sub(r"\s+", " ", 文本).strip()
    return 文本


def 清理搜索关键词(值: Any) -> str:
    """删除搜索词中的标点和装饰符，只保留文字、数字及必要空格。

    平台搜索接口对书名中的全角标点、引号和分享文案兼容性不一致，
    统一在请求前净化可以避免同一查询在不同平台得到不一致结果。空白
    会折叠为单个 ASCII 空格，中文、字母和数字原样保留。
    """
    文本 = 清理文本(值)
    保留字符 = [字符 for 字符 in 文本 if 字符.isspace() or 字符.isalnum()]
    return re.sub(r"\s+", " ", "".join(保留字符)).strip()


def 规范标题(值: Any) -> str:
    文本 = 清理文本(值).lower()
    文本 = re.sub(
        r"[\s\-_/\\|·•·【】\[\]（）()《》<>\"'“”‘’：:，,。.!！?？~～]+", "", 文本
    )
    return 文本


def _收集事件对象(event: Any) -> list[Any]:
    候选: list[Any] = [
        event,
        getattr(event, "message_obj", None),
        getattr(event, "raw_message", None),
    ]
    消息对象 = getattr(event, "message_obj", None)
    if 消息对象 is not None:
        候选.extend(
            [
                getattr(消息对象, "raw_message", None),
                getattr(消息对象, "raw", None),
                getattr(消息对象, "data", None),
                getattr(消息对象, "extra", None),
            ]
        )
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
    if not 用户:
        return ""
    return f"{群号 or 'private'}:{用户}"


def 获取找书用户标识(event: Any) -> str:
    群聊 = bool(获取群号(event))
    # QQ 官方群消息与按钮回调可能分别只提供 user_openid 或
    # group_member_openid；群聊优先成员 openid，保证两种事件能命中同一会话。

    def 安全用户文本(值: Any) -> str:
        if 值 is None:
            return ""
        文本 = str(值).strip()
        if not 文本 or re.search(r"<[^>]+ object at 0x[0-9a-f]+>", 文本, re.IGNORECASE):
            return ""
        return 文本

    if not 群聊:
        用户文本 = 安全用户文本(获取发送者QQ(event))
        if 用户文本:
            return 用户文本
    对象列表 = _收集事件对象(event)

    def 读取用户字段(对象: Any, 字段名: str) -> Any:
        值 = 读取字段(对象, 字段名)
        if isinstance(值, dict):
            值 = (
                值.get("user_id")
                or 值.get("id")
                or 值.get("openid")
                or 值.get("user_openid")
            )
        return 值

    if 群聊:
        # 先扫描所有对象及 sender/author 的成员字段，避免顶层 user_openid
        # 抢在官方群本群成员标识前面。
        for 对象 in 对象列表:
            for 字段名 in ("group_member_openid", "member_openid"):
                值 = 安全用户文本(读取用户字段(对象, 字段名))
                if 值:
                    return 值
            for 发送者字段 in ("author", "sender", "user", "member"):
                发送者 = 读取字段(对象, 发送者字段)
                if 发送者 is not None:
                    for 字段名 in ("group_member_openid", "member_openid"):
                        值 = 安全用户文本(读取用户字段(发送者, 字段名))
                        if 值:
                            return 值
            # AstrBot 对部分 QQ 官方普通群消息会把 member_openid 映射为
            # sender.user_id；在顶层同时存在 user_openid 时仍应优先本群成员。
            发送者 = 读取字段(对象, "sender")
            if 发送者 is not None:
                for 字段名 in ("user_id", "openid"):
                    值 = 安全用户文本(读取用户字段(发送者, 字段名))
                    if 值:
                        return 值

    for 对象 in 对象列表:
        for 字段名 in (
            "user_openid",
            "openid",
            "user_id",
            "sender_id",
        ):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = (
                    值.get("user_id")
                    or 值.get("id")
                    or 值.get("openid")
                    or 值.get("user_openid")
                )
            值文本 = 安全用户文本(值)
            if 值文本:
                return 值文本
        for 发送者字段 in ("author", "sender", "user", "member"):
            发送者 = 读取字段(对象, 发送者字段)
            if 发送者 is None:
                continue
            for 字段名 in ("user_openid", "id", "user_id", "openid"):
                值 = 安全用户文本(读取用户字段(发送者, 字段名))
                if 值:
                    return 值

    if 群聊:
        用户 = 获取发送者QQ(event)
        用户文本 = 安全用户文本(用户)
        if 用户文本:
            return 用户文本
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
                关闭方法 = getattr(值, "close", None)
                if callable(关闭方法):
                    try:
                        关闭方法()
                    except Exception:
                        pass
                continue
            if 值:
                return str(值)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("group_openid", "group_id", "group_open_id"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = (
                    值.get("group_openid")
                    or 值.get("group_id")
                    or 值.get("id")
                )
            if 值:
                return str(值)
    for 对象 in _收集事件对象(event):
        for 字段名 in ("group_openid", "group_id", "group_open_id"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = (
                    值.get("group_openid")
                    or 值.get("group_id")
                    or 值.get("id")
                )
            if 值:
                return str(值)
    return ""


def 清理过期会话() -> None:
    现在 = time.time()
    for 键 in [
        k for k, v in 找书会话.items() if 现在 - float(v.get("ts") or 0) > 会话等待秒数
    ]:
        找书会话.pop(键, None)


def 解析找书查询(命令文本: str) -> dict[str, str] | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None
    if 空找书模式正则.fullmatch(文本):
        return None
    搜索类型 = "auto"
    匹配 = 找书名命令正则.match(文本)
    if 匹配:
        搜索类型 = "title"
    else:
        匹配 = 找作者命令正则.match(文本)
        if 匹配:
            搜索类型 = "author"
        else:
            匹配 = 找书命令正则.match(文本)
    if not 匹配:
        return None
    # 先按原始文本识别「找 书名：」/「找 作者：」前缀，再净化实际查询词；
    # 直接先删标点会把前缀和关键词粘在一起，导致类型判断失效。
    关键词 = 清理文本(匹配.group(1))
    if 搜索类型 == "auto":
        类型匹配 = 查询书名模式正则.match(关键词)
        if 类型匹配:
            搜索类型 = "title"
            关键词 = 清理文本(类型匹配.group(1))
        else:
            类型匹配 = 查询作者模式正则.match(关键词)
            if 类型匹配:
                搜索类型 = "author"
                关键词 = 清理文本(类型匹配.group(1))
    关键词 = 清理搜索关键词(关键词)
    if not 关键词 or 关键词 in 翻页命令集合:
        return None
    # 避免误伤其他「找」开头命令
    if 关键词.startswith(("书登录", "书状态", "书清理")):
        return None
    return {"keyword": 关键词, "type": 搜索类型}


def 构造番茄链接(书籍编号: str) -> str:
    return f"https://fanqienovel.com/page/{书籍编号}"


def 构造七猫链接(书籍编号: str, 是否短篇: bool = False) -> str:
    if 是否短篇:
        return (
            f"https://app-share.wtzw.com/app-h5/freebook/short-story-detail/{书籍编号}"
        )
    return f"https://www.qimao.com/shuku/{书籍编号}/"


def 构造书旗链接(书籍编号: str) -> str:
    return f"https://www.shuqi.com/book/{书籍编号}.html"


def 构造追书链接(书籍编号: str) -> str:
    if 追书小说 is not None and hasattr(追书小说, "构造追书链接"):
        return str(追书小说.构造追书链接(书籍编号))
    return f"https://m.zhuishushenqi.com/books/{书籍编号}?shareFrom=app"


def 构造QQ阅读链接(书籍编号: str) -> str:
    return f"https://book.qq.com/book-detail/{书籍编号}"


def 构造QQ浏览器链接(书籍编号: str) -> str:
    return f"https://bookshelf.html5.qq.com/autojump/intro?bookid={书籍编号}"


def 构造塔读链接(书籍编号: str) -> str:
    return f"https://reader.tadu.com/book/{书籍编号}"


def 构造百度链接(书籍编号: str) -> str:
    return f"https://boxnovel.baidu.com/boxnovel/reader?gid={书籍编号}"


def 构造小米链接(书籍编号: str) -> str:
    return f"https://reader.browser.miui.com/#page=book&id={书籍编号}"


def 构造晋江链接(书籍编号: str) -> str:
    return f"https://www.jjwxc.net/onebook.php?novelid={书籍编号}"


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


书名噪声后缀 = (
    "原版小说",
    "原版",
    "动漫版",
    "广播剧",
    "同人",
    "后续",
    "续写",
    "新书",
    "大全集",
    "全集",
    "完本",
)
无效作者名称 = {"", "未知", "unknown", "佚名", "匿名"}


def 计算匹配字数(候选文本: Any, 关键词: Any) -> int:
    候选 = 规范标题(候选文本)
    查询 = 规范标题(关键词)
    if not 候选 or not 查询:
        return 0
    return sum((Counter(候选) & Counter(查询)).values())


def _计算文本匹配详情(候选文本: Any, 关键词: Any, *, 字段类型: str) -> dict[str, Any]:
    原文 = 清理文本(候选文本)
    候选 = 规范标题(原文)
    查询 = 规范标题(关键词)
    if not 候选 or not 查询:
        return {"tier": 0, "score": 0.0, "chars": 0, "coverage": 0.0, "ratio": 0.0}
    if 字段类型 == "author" and 候选 in 无效作者名称:
        return {"tier": 0, "score": 0.0, "chars": 0, "coverage": 0.0, "ratio": 0.0}

    匹配字数 = 计算匹配字数(候选, 查询)
    覆盖率 = 匹配字数 / max(len(查询), 1)
    相似度 = SequenceMatcher(None, 查询, 候选).ratio()

    if 候选 == 查询:
        return {
            "tier": 6,
            "score": 10000.0,
            "chars": 匹配字数,
            "coverage": 1.0,
            "ratio": 1.0,
        }

    if 字段类型 == "title":
        去后缀 = 候选
        for 后缀 in 书名噪声后缀:
            规范后缀 = 规范标题(后缀)
            if 规范后缀 and 去后缀.endswith(规范后缀) and len(去后缀) > len(规范后缀):
                去后缀 = 去后缀[: -len(规范后缀)]
                break
        if 去后缀 == 查询:
            return {
                "tier": 5,
                "score": 9000.0,
                "chars": 匹配字数,
                "coverage": 覆盖率,
                "ratio": 相似度,
            }

    if 候选.startswith(查询):
        多余 = len(候选) - len(查询)
        基础分 = 7800.0 if 字段类型 == "author" else 7600.0
        return {
            "tier": 4,
            "score": max(基础分 - 多余 * 35.0, 5200.0),
            "chars": 匹配字数,
            "coverage": 覆盖率,
            "ratio": 相似度,
        }
    if 查询 in 候选:
        位置 = 候选.find(查询)
        多余 = len(候选) - len(查询)
        基础分 = 7000.0 if 字段类型 == "author" else 6200.0
        return {
            "tier": 3,
            "score": max(基础分 - 位置 * 20.0 - 多余 * 20.0, 4300.0),
            "chars": 匹配字数,
            "coverage": 覆盖率,
            "ratio": 相似度,
        }

    最少反向长度 = max(3 if 字段类型 == "title" else 2, (len(查询) * 2 + 2) // 3)
    if 候选 in 查询 and len(候选) >= 最少反向长度:
        return {
            "tier": 2,
            "score": 4800.0 + 覆盖率 * 600.0,
            "chars": 匹配字数,
            "coverage": 覆盖率,
            "ratio": 相似度,
        }

    if 字段类型 == "author":
        最少匹配字数 = max(2, (len(查询) * 3 + 3) // 4)
        可模糊 = (
            len(查询) >= 3
            and 匹配字数 >= 最少匹配字数
            and 覆盖率 >= 0.75
            and 相似度 >= 0.78
        )
    else:
        最少匹配字数 = max(2, (len(查询) * 65 + 99) // 100)
        可模糊 = (
            len(查询) >= 3
            and 匹配字数 >= 最少匹配字数
            and 覆盖率 >= 0.65
            and 相似度 >= 0.68
        )
    if 可模糊:
        return {
            "tier": 1,
            "score": 1800.0 + 匹配字数 * 260.0 + 覆盖率 * 700.0 + 相似度 * 700.0,
            "chars": 匹配字数,
            "coverage": 覆盖率,
            "ratio": 相似度,
        }
    return {
        "tier": 0,
        "score": 0.0,
        "chars": 匹配字数,
        "coverage": 覆盖率,
        "ratio": 相似度,
    }


def 计算标题相关度(标题: str, 关键词: str) -> float:
    return float(_计算文本匹配详情(标题, 关键词, 字段类型="title")["score"])


def 计算作者相关度(作者: str, 关键词: str) -> float:
    return float(_计算文本匹配详情(作者, 关键词, 字段类型="author")["score"])


def _拆分查询词(关键词: str) -> list[str]:
    结果: list[str] = []
    for 文本 in re.split(r"[\s,，;；/|]+", 清理文本(关键词)):
        规范词 = 规范标题(文本)
        if 规范词 and 规范词 not in 结果:
            结果.append(规范词)
    return 结果 or ([规范标题(关键词)] if 规范标题(关键词) else [])


def _评估找书项(项: dict[str, Any], 关键词: str) -> dict[str, Any]:
    标题 = 清理文本(项.get("title") or "")
    作者 = 清理文本(项.get("author") or "")
    标题匹配 = _计算文本匹配详情(标题, 关键词, 字段类型="title")
    作者匹配 = _计算文本匹配详情(作者, 关键词, 字段类型="author")
    查询词 = _拆分查询词(关键词)
    标题词全匹配 = bool(查询词) and all(
        _计算文本匹配详情(标题, 词, 字段类型="title")["score"] > 0 for 词 in 查询词
    )
    作者词全匹配 = bool(查询词) and all(
        _计算文本匹配详情(作者, 词, 字段类型="author")["score"] > 0 for 词 in 查询词
    )
    混合词详情 = [
        max(
            _计算文本匹配详情(标题, 词, 字段类型="title"),
            _计算文本匹配详情(作者, 词, 字段类型="author"),
            key=lambda 详情: (详情["tier"], 详情["chars"], 详情["score"]),
        )
        for 词 in 查询词
    ]
    混合词全匹配 = bool(查询词) and all(详情["score"] > 0 for 详情 in 混合词详情)
    return {
        "title": 标题匹配,
        "author": 作者匹配,
        "tokens": 查询词,
        "title_all": 标题词全匹配,
        "author_all": 作者词全匹配,
        "mixed_all": 混合词全匹配,
        "mixed_chars": sum(int(详情["chars"]) for 详情 in 混合词详情),
        "mixed_score": sum(float(详情["score"]) for 详情 in 混合词详情),
    }


def _推断找书搜索类型(评估结果: list[dict[str, Any]], 搜索类型: str) -> str:
    if 搜索类型 in {"title", "author"}:
        return 搜索类型
    if not 评估结果:
        return "auto"
    if any(len(详情["tokens"]) > 1 and 详情["mixed_all"] for 详情 in 评估结果):
        return "mixed"
    # 自动搜索不再先把整批结果强行判定为书名或作者；每本候选单独
    # 比较书名和作者的命中字数，避免“赵心姚”只能搜作者或“斗破”只能搜书名。
    return "auto"


def _选择主匹配(详情: dict[str, Any], 搜索类型: str) -> dict[str, Any]:
    if 搜索类型 == "author":
        return 详情["author"]
    if 搜索类型 == "auto":
        if len(详情["tokens"]) > 1:
            if not 详情["mixed_all"]:
                return {
                    "tier": 0,
                    "score": 0.0,
                    "chars": 0,
                    "coverage": 0.0,
                    "ratio": 0.0,
                }
            总字数 = sum(len(词) for 词 in 详情["tokens"])
            return {
                "tier": 7,
                "score": 12000.0 + float(详情["mixed_score"]),
                "chars": int(详情["mixed_chars"]),
                "coverage": min(1.0, int(详情["mixed_chars"]) / max(总字数, 1)),
                "ratio": 1.0,
            }
        return max(
            (详情["title"], 详情["author"]),
            key=lambda 匹配: (
                int(匹配["chars"]),
                float(匹配["coverage"]),
                int(匹配["tier"]),
                float(匹配["score"]),
            ),
        )
    if 搜索类型 == "mixed" and len(详情["tokens"]) > 1:
        if not 详情["mixed_all"]:
            return {"tier": 0, "score": 0.0, "chars": 0, "coverage": 0.0, "ratio": 0.0}
        总字数 = sum(len(词) for 词 in 详情["tokens"])
        return {
            "tier": 7,
            "score": 12000.0 + float(详情["mixed_score"]),
            "chars": int(详情["mixed_chars"]),
            "coverage": min(1.0, int(详情["mixed_chars"]) / max(总字数, 1)),
            "ratio": 1.0,
        }
    return 详情["title"]


def 排序找书结果(
    结果: list[dict[str, Any]],
    关键词: str,
    搜索类型: str = "auto",
) -> list[dict[str, Any]]:
    """按书名/作者意图、匹配字数和覆盖率过滤排序，无直接关系的候选不展示。"""
    if not 结果:
        return []
    全部评估 = [_评估找书项(项, 关键词) for 项 in 结果]
    实际类型 = _推断找书搜索类型(全部评估, 搜索类型)
    筛选后: list[dict[str, Any]] = []
    for 原项, 详情 in zip(结果, 全部评估):
        主匹配 = _选择主匹配(详情, 实际类型)
        if 实际类型 == "title" and len(详情["tokens"]) > 1 and not 详情["title_all"]:
            continue
        if 实际类型 == "author" and len(详情["tokens"]) > 1 and not 详情["author_all"]:
            continue
        if float(主匹配["score"]) <= 0:
            continue
        项 = dict(原项)
        项["_match_type"] = 实际类型
        项["_match_tier"] = int(主匹配["tier"])
        项["_match_chars"] = int(主匹配["chars"])
        项["_match_coverage"] = float(主匹配["coverage"])
        项["_match_score"] = float(主匹配["score"])
        筛选后.append(项)
    if not 筛选后:
        return []

    平台原始: dict[str, list[float]] = {}
    for 项 in 筛选后:
        平台原始.setdefault(str(项.get("platform") or ""), []).append(
            float(项.get("heat") or 0)
        )
    平台区间 = {
        平台: (min(值列表), max(值列表)) if 值列表 else (0.0, 0.0)
        for 平台, 值列表 in 平台原始.items()
    }

    def 平台内相对热度(项: dict[str, Any]) -> float:
        下限, 上限 = 平台区间.get(str(项.get("platform") or ""), (0.0, 0.0))
        当前值 = float(项.get("heat") or 0)
        return (当前值 - 下限) / (上限 - 下限) if 上限 > 下限 else 0.5

    def 排序键(项: dict[str, Any]) -> tuple:
        标题规范 = 规范标题(项.get("title"))
        作者规范 = 规范标题(项.get("author"))
        共识平台数 = max(1, int(项.get("_source_count") or 1))
        有效作者 = 1 if 作者规范 not in 无效作者名称 else 0
        if 实际类型 == "auto":
            # 自动搜索的第一排序依据是实际命中的字符数；番茄等平台
            # 返回的原始顺序只作为同等匹配结果的稳定兜底。
            return (
                int(项.get("_match_chars") or 0),
                float(项.get("_match_coverage") or 0),
                int(项.get("_match_tier") or 0),
                float(项.get("_match_score") or 0),
                共识平台数,
                1 if 项.get("目录可用") else 0,
                _平台原始排序信号(项),
                _平台优先级值(项.get("platform")),
                _安全浮点(项.get("score")),
                平台内相对热度(项),
                有效作者,
                -len(标题规范),
            )
        return (
            int(项.get("_match_tier") or 0),
            int(项.get("_match_chars") or 0),
            float(项.get("_match_coverage") or 0),
            float(项.get("_match_score") or 0),
            共识平台数,
            1 if 项.get("目录可用") else 0,
            _平台原始排序信号(项),
            _安全浮点(项.get("score")),
            平台内相对热度(项),
            _平台优先级值(项.get("platform")),
            有效作者,
            -len(标题规范),
        )

    筛选后.sort(key=排序键, reverse=True)
    return 筛选后


def 提取番茄搜索书(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    books = row.get("books")
    book = (
        books[0]
        if isinstance(books, list) and books and isinstance(books[0], dict)
        else None
    )
    if book is None:
        book = row.get("book") or row.get("book_info") or row
    if not isinstance(book, dict):
        return None
    book_id = str(
        book.get("book_id") or row.get("book_id") or book.get("id") or ""
    ).strip()
    title = 清理文本(
        book.get("book_name") or book.get("title") or row.get("title") or ""
    )
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
    原始字数 = book.get("word_number") or book.get("word_count")
    字数 = _安全整数热度(原始字数)
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
        "word_count": 原始字数,
    }


async def 搜索番茄(
    session: aiohttp.ClientSession, 关键词: str, *, 需要数量: int = 30
) -> list[dict[str, Any]]:
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
            logger.warning(
                f"找书番茄搜索失败：关键词={关键词}, 偏移={偏移}, 错误={exc}"
            )
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
                f"找书番茄目录预检暂不可判断：书籍编号={书籍编号}, 错误={错误文本}"
            )
    番茄目录预检缓存[书籍编号] = (现在, 状态)
    return 状态


def 获取番茄预检候选(
    结果: list[dict[str, Any]],
    关键词: str,
    *,
    搜索类型: str = "auto",
    最大数量: int = 番茄目录预检最大候选数,
) -> list[dict[str, Any]]:
    """只预检与书名或作者相关、且最终最可能展示的番茄候选。"""
    数量上限 = max(1, int(最大数量))
    return 排序找书结果(结果, 关键词, 搜索类型)[:数量上限]


async def 过滤无目录番茄搜索结果(
    结果: list[dict[str, Any]],
    关键词: str,
    *,
    搜索类型: str = "auto",
    最大数量: int = 番茄目录预检最大候选数,
) -> list[dict[str, Any]]:
    """过滤已明确无目录的番茄候选，保留网络状态未知的候选。"""
    if not 结果 or 番茄小说 is None:
        return 结果

    候选 = 获取番茄预检候选(
        结果,
        关键词,
        搜索类型=搜索类型,
        最大数量=最大数量,
    )
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
                f"找书跳过无目录番茄候选：书籍编号={书籍编号}, "
                f"书名={清理文本(项.get('title') or '')}"
            )
            continue
        if 状态 is True:
            项 = dict(项)
            项["目录可用"] = True
        筛选后.append(项)
    return 筛选后


async def 搜索七猫(
    session: aiohttp.ClientSession, 关键词: str, *, 需要数量: int = 30
) -> list[dict[str, Any]]:
    if 七猫小说 is None:
        return []
    结果: list[dict[str, str]] = []
    页码 = 1
    while len(结果) < 需要数量 and 页码 <= 5:
        try:
            参数 = 七猫小说.签名参数(
                {
                    "extend": "",
                    "tab": "0",
                    "gender": "0",
                    "refresh_state": "8",
                    "page": str(页码),
                    "wd": 关键词,
                    "is_short_story_user": "0",
                }
            )
            数据 = await 七猫小说.请求JSON(
                session,
                "https://api-bc.wtzw.com/search/v1/words",
                参数,
                七猫小说.生成请求头("00000000", "api-bc.wtzw.com"),
            )
        except Exception as exc:
            logger.warning(
                f"找书七猫搜索失败：关键词={关键词}, 页码={页码}, 错误={exc}"
            )
            break
        书籍列表 = (
            七猫小说.读取字段路径(数据, ("data", "books"))
            if hasattr(七猫小说, "读取字段路径")
            else ((数据 or {}).get("data") or {}).get("books")
        )
        if not isinstance(书籍列表, list) or not 书籍列表:
            break
        for 书籍 in 书籍列表:
            if not isinstance(书籍, dict):
                continue
            book_id = str(书籍.get("id") or "").strip()
            title = 清理文本(书籍.get("title") or 书籍.get("original_title") or "")
            author = (
                清理文本(书籍.get("author") or 书籍.get("original_author") or "未知")
                or "未知"
            )
            if not book_id or not title:
                continue
            reader_type = str(书籍.get("reader_type") or 书籍.get("type") or "")
            是否短篇 = reader_type in {"4", "short"} or "短篇" in str(
                书籍.get("sub_title") or ""
            )
            评分 = _安全浮点(书籍.get("score"))
            字数 = _安全整数热度(
                书籍.get("words_num") or 书籍.get("word_count") or 书籍.get("words")
            )
            # sub_title 里常有「653万字」
            if 字数 <= 0:
                副 = str(书籍.get("sub_title") or "")
                m = re.search(r"([\d.]+)\s*万字", 副)
                if m:
                    字数 = int(float(m.group(1)) * 10000)
            热度值 = 计算热度排序值(评分=评分, 字数=字数)
            结果.append(
                {
                    "platform": "七猫",
                    "book_id": book_id,
                    "title": title,
                    "author": author,
                    "url": 构造七猫链接(book_id, 是否短篇),
                    "heat": 热度值,
                    "heat_text": 格式化热度显示(热度值, 评分=评分, 阅读量=0),
                    "score": 评分,
                    "read_count": 0,
                }
            )
        if len(书籍列表) < 8:
            break
        页码 += 1
    return 结果[:需要数量]


async def 搜索书旗(
    session: aiohttp.ClientSession,
    关键词: str,
    *,
    需要数量: int = 30,
) -> list[dict[str, Any]]:
    if 书旗小说 is None:
        return []
    try:
        原始结果 = await 书旗小说.搜索小说(session, 关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(f"找书书旗搜索失败：关键词={关键词}, 错误={exc}")
        return []

    结果: list[dict[str, Any]] = []
    for 书籍 in 原始结果:
        if not isinstance(书籍, dict):
            continue
        book_id = str(书籍.get("book_id") or "").strip()
        title = 清理文本(书籍.get("title"))
        if not book_id.isdigit() or not title:
            continue
        author = 清理文本(书籍.get("author") or "未知") or "未知"
        评分 = _安全浮点(书籍.get("score"))
        字数 = _安全整数热度(书籍.get("word_count"))
        阅读量 = _安全整数热度(书籍.get("read_count"))
        热度值 = 计算热度排序值(阅读量=阅读量, 评分=评分, 字数=字数)
        结果.append(
            {
                "platform": "书旗",
                "book_id": book_id,
                "title": title,
                "author": author,
                "url": str(书籍.get("url") or 构造书旗链接(book_id)),
                "heat": 热度值,
                "heat_text": 格式化热度显示(热度值, 评分=评分, 阅读量=阅读量),
                "score": 评分,
                "read_count": 阅读量,
            }
        )
    return 结果[:需要数量]


async def 搜索书旗联想(session: aiohttp.ClientSession, 关键词: str) -> list[str]:
    if 书旗小说 is None:
        return []
    try:
        return await 书旗小说.搜索联想(session, 关键词)
    except Exception as exc:
        logger.debug(f"找书书旗联想失败：关键词={关键词}, 错误={exc}")
        return []


async def 搜索追书(
    session: aiohttp.ClientSession,
    关键词: str,
    *,
    需要数量: int = 20,
) -> list[dict[str, Any]]:
    if 追书小说 is None:
        return []
    try:
        原始结果 = await 追书小说.搜索小说(
            session,
            关键词,
            需要数量=需要数量,
        )
    except Exception as exc:
        logger.debug(
            "找书追书搜索失败：关键词=%s, 错误类型=%s",
            关键词,
            type(exc).__name__,
        )
        return []
    结果: list[dict[str, Any]] = []
    for 书籍 in 原始结果:
        if not isinstance(书籍, dict):
            continue
        书籍编号 = str(书籍.get("_id") or 书籍.get("id") or "").strip()
        书名 = 清理文本(书籍.get("title") or 书籍.get("name"))
        if not 书籍编号 or not 书名:
            continue
        # 追书搜索会同时返回不可公开阅读的记录；找书只展示允许免费读取的书。
        if 书籍.get("allowFree") is False and not 书籍.get("hasCp"):
            continue
        作者 = 清理文本(书籍.get("author") or 书籍.get("originalAuthor") or "未知") or "未知"
        评分 = _安全浮点(
            书籍.get("rating", {}).get("score")
            if isinstance(书籍.get("rating"), dict)
            else 书籍.get("score")
        )
        字数 = _安全整数热度(
            书籍.get("wordCount") or 书籍.get("word_count") or 书籍.get("words")
        )
        阅读量 = _安全整数热度(
            书籍.get("latelyFollower")
            or 书籍.get("totalFollower")
            or 书籍.get("dailyLatelyFollower")
        )
        热度值 = 计算热度排序值(阅读量=阅读量, 评分=评分, 字数=字数)
        结果.append(
            {
                "platform": "追书",
                "book_id": 书籍编号,
                "title": 书名,
                "author": 作者,
                "url": 构造追书链接(书籍编号),
                "heat": 热度值,
                "heat_text": 格式化热度显示(热度值, 评分=评分, 阅读量=阅读量),
                "score": 评分,
                "read_count": 阅读量,
                "word_count": 字数,
            }
        )
    return 结果[: max(1, int(需要数量 or 20))]


async def 搜索QQ阅读(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if QQ阅读小说 is None:
        return []
    try:
        原始结果 = await QQ阅读小说.搜索小说(关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(
            f"找书QQ阅读搜索失败：关键词={关键词}, 错误={type(exc).__name__}"
        )
        return []

    结果: list[dict[str, Any]] = []
    for 书籍 in 原始结果:
        if not isinstance(书籍, dict):
            continue
        book_id = str(书籍.get("book_id") or "").strip()
        title = 清理文本(书籍.get("title"))
        if not book_id.isdigit() or not title:
            continue
        author = 清理文本(书籍.get("author") or "未知") or "未知"
        评分 = _安全浮点(书籍.get("score"))
        if 评分 > 10:
            评分 /= 10
        字数 = _安全整数热度(书籍.get("word_count"))
        阅读量 = _安全整数热度(书籍.get("read_count"))
        热度值 = 计算热度排序值(阅读量=阅读量, 评分=评分, 字数=字数)
        结果.append(
            {
                "platform": "QQ阅读",
                "book_id": book_id,
                "title": title,
                "author": author,
                "url": str(书籍.get("url") or 构造QQ阅读链接(book_id)),
                "heat": 热度值,
                "heat_text": 格式化热度显示(热度值, 评分=评分, 阅读量=阅读量),
                "score": 评分,
                "read_count": 阅读量,
                "word_count": 书籍.get("word_count") or 0,
            }
        )
    return 结果[:需要数量]


async def 搜索QQ浏览器(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if QQ浏览器小说 is None:
        return []
    try:
        原始结果 = await QQ浏览器小说.搜索小说(关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(
            f"找书QQ浏览器搜索失败：关键词={关键词}, 错误={type(exc).__name__}"
        )
        return []

    结果: list[dict[str, Any]] = []
    for 书籍 in 原始结果:
        if not isinstance(书籍, dict):
            continue
        book_id = str(书籍.get("book_id") or "").strip()
        title = 清理文本(书籍.get("title"))
        if not book_id.isdigit() or not title:
            continue
        author = 清理文本(书籍.get("author") or "未知") or "未知"
        字数 = _安全整数热度(书籍.get("word_count"))
        热度值 = _安全浮点(书籍.get("heat"), 0.0)
        if 热度值 <= 0:
            热度值 = 计算热度排序值(字数=字数)
        结果.append(
            {
                "platform": "QQ浏览器",
                "book_id": book_id,
                "title": title,
                "author": author,
                "url": str(书籍.get("url") or 构造QQ浏览器链接(book_id)),
                "heat": 热度值,
                "heat_text": 格式化热度显示(热度值),
                "score": 0,
                "read_count": 0,
                "word_count": 书籍.get("word_count") or 0,
            }
        )
    return 结果[:需要数量]


async def 搜索百度(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 百度小说 is None:
        return []
    try:
        原始结果 = await 百度小说.搜索小说(关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(f"找书百度搜索失败：关键词={关键词}, 错误={type(exc).__name__}")
        return []
    结果: list[dict[str, Any]] = []
    for 书籍 in 原始结果:
        if not isinstance(书籍, dict):
            continue
        book_id = str(书籍.get("book_id") or "").strip()
        title = 清理文本(书籍.get("title"))
        if not book_id.isdigit() or not title:
            continue
        评分 = _安全浮点(书籍.get("score"))
        字数 = _安全整数热度(书籍.get("word_count"))
        结果.append(
            {
                "platform": "百度",
                "book_id": book_id,
                "title": title,
                "author": 清理文本(书籍.get("author") or "未知") or "未知",
                "url": str(书籍.get("url") or 构造百度链接(book_id)),
                "heat": 计算热度排序值(评分=评分, 字数=字数),
                "heat_text": "",
                "score": 评分,
                "read_count": 0,
                "word_count": 字数,
            }
        )
    return 结果[:需要数量]


async def 搜索小米(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 小米小说 is None:
        return []
    try:
        原始结果 = await 小米小说.搜索小说(关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(f"找书小米搜索失败：关键词={关键词}, 错误={type(exc).__name__}")
        return []
    结果: list[dict[str, Any]] = []
    for 书籍 in 原始结果:
        if not isinstance(书籍, dict):
            continue
        book_id = str(书籍.get("book_id") or "").strip()
        title = 清理文本(书籍.get("title"))
        if not book_id.isdigit() or not title:
            continue
        评分 = _安全浮点(书籍.get("score"))
        热度 = _安全整数热度(书籍.get("heat"))
        结果.append(
            {
                "platform": "小米",
                "book_id": book_id,
                "title": title,
                "author": 清理文本(书籍.get("author") or "未知") or "未知",
                "url": str(书籍.get("url") or 构造小米链接(book_id)),
                "heat": 热度 or 计算热度排序值(评分=评分),
                "heat_text": "",
                "score": 评分,
                "read_count": 热度,
                "word_count": 书籍.get("word_count") or 0,
            }
        )
    return 结果[:需要数量]


def _整理新增平台搜索结果(
    平台: str, 原始结果: Any, 需要数量: int
) -> list[dict[str, Any]]:
    """把各独立平台模块的搜索字段接入统一找书会话。"""
    if not isinstance(原始结果, list):
        return []
    结果: list[dict[str, Any]] = []
    for 书籍 in 原始结果:
        if not isinstance(书籍, dict):
            continue
        书籍编号 = str(书籍.get("book_id") or "").strip()
        书名 = 清理文本(书籍.get("title"))
        if not 书籍编号 or not 书名:
            continue
        作者 = 清理文本(书籍.get("author") or "未知") or "未知"
        评分 = _安全浮点(书籍.get("score"))
        字数 = _安全整数热度(书籍.get("word_count"))
        热度 = _安全整数热度(书籍.get("heat"))
        结果.append(
            {
                "platform": 平台,
                "book_id": 书籍编号,
                "title": 书名,
                "author": 作者,
                "url": str(书籍.get("url") or ""),
                "heat": 热度 or 计算热度排序值(评分=评分, 字数=字数),
                "heat_text": "",
                "score": 评分,
                "read_count": 热度,
                "word_count": 字数,
            }
        )
    return 结果[: max(1, int(需要数量 or 20))]


async def 搜索宜搜(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 宜搜小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "宜搜", await 宜搜小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书宜搜搜索失败：错误类型=%s", type(exc).__name__)
        return []


async def 搜索米读(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 米读小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "米读", await 米读小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书米读搜索失败：错误类型=%s", type(exc).__name__)
        return []


async def 搜索猫眼(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 猫眼小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "猫眼", await 猫眼小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书猫眼搜索失败：错误类型=%s", type(exc).__name__)
        return []


async def 搜索酷我(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 酷我小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "酷我", await 酷我小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书酷我搜索失败：错误类型=%s", type(exc).__name__)
        return []


async def 搜索酷匠(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 酷匠小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "酷匠", await 酷匠小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书酷匠搜索失败：错误类型=%s", type(exc).__name__)
        return []


async def 搜索连城(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 连城小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "连城", await 连城小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书连城搜索失败：错误类型=%s", type(exc).__name__)
        return []


async def 搜索菠萝包(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 菠萝包小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "菠萝包", await 菠萝包小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书菠萝包搜索失败：错误类型=%s", type(exc).__name__)
        return []


async def 搜索晋江(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 晋江小说 is None:
        return []
    try:
        return _整理新增平台搜索结果(
            "晋江", await 晋江小说.搜索小说(关键词, 需要数量=需要数量), 需要数量
        )
    except Exception as exc:
        logger.debug("找书晋江搜索失败：错误类型=%s", type(exc).__name__)
        return []


def _清理QQ阅读预检缓存() -> None:
    现在 = time.time()
    if len(QQ阅读预检缓存) < 512:
        return
    for book_id, (缓存时间, _状态) in list(QQ阅读预检缓存.items()):
        if 现在 - 缓存时间 >= QQ阅读预检缓存秒数:
            QQ阅读预检缓存.pop(book_id, None)


async def 预检QQ阅读候选(
    book_id: str,
    session: aiohttp.ClientSession | None = None,
) -> bool:
    """确认目录完整且至少有一章可下载的 QQ 阅读候选可以进入找书结果。"""
    书籍编号 = str(book_id or "").strip()
    if not 书籍编号.isdigit() or QQ阅读小说 is None:
        return False
    _清理QQ阅读预检缓存()
    现在 = time.time()
    缓存 = QQ阅读预检缓存.get(书籍编号)
    if 缓存 is not None and 现在 - 缓存[0] < QQ阅读预检缓存秒数:
        return 缓存[1]

    async def _检查(有效会话: aiohttp.ClientSession | None) -> bool:
        details = await QQ阅读小说.获取参考书籍详情(书籍编号, 有效会话)
        chapter_count = _安全整数热度(details.get("chapters"))
        catalog, _published = await QQ阅读小说.获取参考兼容目录(
            书籍编号,
            chapter_count,
            有效会话,
        )
        # 目录必须完整，避免搜索页保留最终无法合成完整 TXT 的候选。
        available = bool(catalog) and (
            chapter_count <= 0 or len(catalog) == chapter_count
        )
        catalog = QQ阅读小说.获取QQ阅读可下载目录(details, catalog)
        return available and bool(catalog)

    try:
        if session is not None:
            allowed = await _检查(session)
        else:
            allowed = await _检查(None)
    except Exception as exc:
        logger.debug(
            f"找书QQ阅读候选预检失败：书籍编号={书籍编号}, 错误={type(exc).__name__}"
        )
        allowed = False
    QQ阅读预检缓存[书籍编号] = (现在, allowed)
    return allowed


async def 过滤章节单独付费QQ阅读搜索结果(
    结果: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """找书保留全免费、VIP 或含免费章节的单章付费 QQ 阅读书籍。"""
    if not 结果 or QQ阅读小说 is None:
        return []
    限流 = asyncio.Semaphore(QQ阅读预检并发数)

    async def 检查(
        项: dict[str, Any],
        session: aiohttp.ClientSession | None = None,
    ) -> tuple[str, bool]:
        书籍编号 = str(项.get("book_id") or "").strip()
        async with 限流:
            try:
                allowed = await asyncio.wait_for(
                    预检QQ阅读候选(书籍编号, session),
                    timeout=12.0,
                )
            except asyncio.TimeoutError:
                logger.debug(f"找书QQ阅读候选预检超时：书籍编号={书籍编号}")
                allowed = False
            return 书籍编号, allowed

    创建会话 = getattr(QQ阅读小说, "创建QQ阅读HTTP会话", None)
    if callable(创建会话):
        async with 创建会话(concurrency=QQ阅读预检并发数) as session:
            检查结果 = await asyncio.gather(*(检查(项, session) for 项 in 结果))
    else:
        检查结果 = await asyncio.gather(*(检查(项) for 项 in 结果))
    可用书籍编号 = {book_id for book_id, allowed in 检查结果 if allowed}
    return [项 for 项 in 结果 if str(项.get("book_id") or "").strip() in 可用书籍编号]


def _平台优先级值(平台: Any) -> int:
    """跨平台同书优先：主流平台优先，新增平台作为后置候选。"""
    return {
        "番茄": 11,
        "七猫": 10,
        "QQ阅读": 9,
        "书旗": 8,
        "追书": 7,
        "得间": 7,
        "点众": 6,
        "QQ浏览器": 5,
        "塔读": 4,
        "百度": 3,
        "小米": 2,
        "宜搜": 1,
        "米读": 0,
        "猫眼": -1,
        "酷我": -2,
        "酷匠": -3,
        "连城": -4,
        "菠萝包": -5,
        "晋江": -6,
    }.get(str(平台 or ""), 0)


def _平台原始排序信号(项: dict[str, Any]) -> float:
    """保留各平台搜索接口的原始位次，作为相关性之后的弱排序信号。"""
    位次 = max(0, int(项.get("_platform_rank") or 0))
    return 1.0 / (位次 + 1.0)


def _书籍优劣键(项: dict[str, Any]) -> tuple:
    """跨平台同书择优：平台优先级 > 评分 > 热度参考 > 有效作者。"""
    作者 = 规范标题(项.get("author"))
    有效作者 = 1 if 作者 and 作者 not in {"未知", "unknown"} else 0
    return (
        _平台优先级值(项.get("platform")),
        _安全浮点(项.get("score")),
        float(项.get("heat") or 0),
        有效作者,
    )


def 去重合并(结果列表: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """同书去重并保留跨平台共识数量，供推荐排序使用。"""
    合并: list[dict[str, Any]] = []
    平台书号索引: set[str] = set()
    书名作者位置: dict[str, int] = {}
    for 列表 in 结果列表:
        for 原项 in 列表:
            项 = dict(原项)
            平台 = str(项.get("platform") or "")
            标题 = 规范标题(项.get("title"))
            作者 = 规范标题(项.get("author"))
            book_id = str(项.get("book_id") or "")
            if not 标题:
                continue
            平台键 = f"{平台}|{book_id}|{标题}|{作者}"
            if 平台键 in 平台书号索引:
                continue
            平台书号索引.add(平台键)
            if "heat" not in 项:
                项["heat"] = 0
            项["_source_platforms"] = [平台] if 平台 else []
            项["_source_count"] = max(1, len(项["_source_platforms"]))
            书名键 = f"{标题}|{作者}"
            if 书名键 in 书名作者位置:
                旧位 = 书名作者位置[书名键]
                旧项 = 合并[旧位]
                共识平台 = set(旧项.get("_source_platforms") or []) | set(
                    项.get("_source_platforms") or []
                )
                胜出项 = 项 if _书籍优劣键(项) > _书籍优劣键(旧项) else 旧项
                胜出项 = dict(胜出项)
                胜出项["_source_platforms"] = sorted(
                    平台名 for 平台名 in 共识平台 if 平台名
                )
                胜出项["_source_count"] = max(1, len(胜出项["_source_platforms"]))
                合并[旧位] = 胜出项
                continue
            书名作者位置[书名键] = len(合并)
            合并.append(项)
    return 合并


async def 搜索得间(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 得间小说 is None:
        return []
    try:
        return await 得间小说.搜索小说(关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(f"找书得间搜索失败：关键词={关键词}, 错误={exc}")
        return []


async def 搜索点众(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 点众小说 is None:
        return []
    try:
        return await 点众小说.搜索小说(关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(f"找书点众搜索失败：关键词={关键词}, 错误={exc}")
        return []


async def 搜索塔读(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    if 塔读小说 is None:
        return []
    try:
        return await 塔读小说.搜索小说(关键词, 需要数量=需要数量)
    except Exception as exc:
        logger.warning(f"找书塔读搜索失败：关键词={关键词}, 错误={exc}")
        return []


async def _限时搜索(
    平台: str,
    任务: Awaitable[list[Any]],
    超时秒数: float = 找书单平台超时秒数,
) -> list[Any]:
    """限制单个平台的等待时间，避免一个慢源拖住全部找书结果。"""
    try:
        结果 = await asyncio.wait_for(任务, timeout=max(1.0, float(超时秒数)))
        return 结果 if isinstance(结果, list) else []
    except asyncio.TimeoutError:
        logger.debug(f"找书平台搜索超时：平台={平台}")
    except Exception as exc:
        logger.debug(f"找书平台搜索异常：平台={平台}, 错误={type(exc).__name__}")
    return []


async def _聚合搜索未缓存(
    关键词: str,
    搜索类型: str = "auto",
    允许平台: Any = None,
) -> list[dict[str, Any]]:
    timeout = aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20)
    关键词 = 清理搜索关键词(关键词)
    if not 关键词:
        return []
    async with aiohttp.ClientSession(timeout=timeout) as session:
        数量 = 找书搜索候选数量
        允许平台集合 = _规范化允许平台(允许平台)

        def 平台搜索任务(
            平台: str,
            工厂: Any,
            日志平台: str | None = None,
        ) -> Awaitable[list[Any]]:
            if 平台 not in 允许平台集合:
                return _空搜索结果()
            return _限时搜索(日志平台 or 平台, 工厂())

        搜索任务 = (
            平台搜索任务("番茄", lambda: 搜索番茄(session, 关键词, 需要数量=数量)),
            平台搜索任务("七猫", lambda: 搜索七猫(session, 关键词, 需要数量=数量)),
            平台搜索任务("书旗", lambda: 搜索书旗(session, 关键词, 需要数量=数量)),
            平台搜索任务("QQ阅读", lambda: 搜索QQ阅读(关键词, 需要数量=数量)),
            平台搜索任务("QQ浏览器", lambda: 搜索QQ浏览器(关键词, 需要数量=数量)),
            平台搜索任务("得间", lambda: 搜索得间(关键词, 需要数量=数量)),
            平台搜索任务("点众", lambda: 搜索点众(关键词, 需要数量=数量)),
            平台搜索任务("塔读", lambda: 搜索塔读(关键词, 需要数量=数量)),
            平台搜索任务("百度", lambda: 搜索百度(关键词, 需要数量=数量)),
            平台搜索任务("小米", lambda: 搜索小米(关键词, 需要数量=数量)),
            平台搜索任务("宜搜", lambda: 搜索宜搜(关键词, 需要数量=数量)),
            平台搜索任务("米读", lambda: 搜索米读(关键词, 需要数量=数量)),
            平台搜索任务("猫眼", lambda: 搜索猫眼(关键词, 需要数量=数量)),
            平台搜索任务("酷我", lambda: 搜索酷我(关键词, 需要数量=数量)),
            平台搜索任务("酷匠", lambda: 搜索酷匠(关键词, 需要数量=数量)),
            平台搜索任务("连城", lambda: 搜索连城(关键词, 需要数量=数量)),
            平台搜索任务("菠萝包", lambda: 搜索菠萝包(关键词, 需要数量=数量)),
            平台搜索任务("晋江", lambda: 搜索晋江(关键词, 需要数量=数量)),
            平台搜索任务("追书", lambda: 搜索追书(session, 关键词, 需要数量=数量)),
        )
        (
            番茄结果,
            七猫结果,
            书旗结果,
            QQ阅读结果,
            QQ浏览器结果,
            得间结果,
            点众结果,
            塔读结果,
            百度结果,
            小米结果,
            宜搜结果,
            米读结果,
            猫眼结果,
            酷我结果,
            酷匠结果,
            连城结果,
            菠萝包结果,
            晋江结果,
            追书结果,
        ) = await asyncio.gather(
            *搜索任务,
            return_exceptions=False,
        )
        for 平台结果 in (
            番茄结果,
            七猫结果,
            书旗结果,
            QQ阅读结果,
            QQ浏览器结果,
            得间结果,
            点众结果,
            塔读结果,
            百度结果,
            小米结果,
            宜搜结果,
            米读结果,
            猫眼结果,
            酷我结果,
            酷匠结果,
            连城结果,
            菠萝包结果,
            晋江结果,
            追书结果,
        ):
            for 排名, 项 in enumerate(平台结果):
                if isinstance(项, dict):
                    项.setdefault("_platform_rank", 排名)
        # 先筛掉搜索接口仍会返回、但畅听目录已为空的番茄记录；必须在
        # 跨平台去重前处理，才能让同书的七猫/书旗候选正常补位。
        番茄结果 = await 过滤无目录番茄搜索结果(
            番茄结果,
            关键词,
            搜索类型=搜索类型,
        )
        QQ阅读结果 = await 过滤章节单独付费QQ阅读搜索结果(QQ阅读结果)
        合并 = 去重合并(
            [
                番茄结果,
                七猫结果,
                QQ阅读结果,
                QQ浏览器结果,
                书旗结果,
                追书结果,
                得间结果,
                点众结果,
                塔读结果,
                百度结果,
                小米结果,
                宜搜结果,
                米读结果,
                猫眼结果,
                酷我结果,
                酷匠结果,
                连城结果,
                菠萝包结果,
                晋江结果,
            ]
        )
        初步结果 = 排序找书结果(合并, 关键词, 搜索类型)
        # 严格相关结果太少时才用联想词补搜，补回内容仍按原关键词过滤。
        联想词: list[str] = []
        if len(初步结果) < 每页数量 and "书旗" in 允许平台集合:
            联想词 = await _限时搜索(
                "书旗联想",
                搜索书旗联想(session, 关键词),
                找书联想超时秒数,
            )
        if len(初步结果) < 每页数量 and 联想词:
            补搜词 = [w for w in 联想词 if 规范标题(w) != 规范标题(关键词)][:3]
            补结果集合: list[list[dict[str, Any]]] = [
                番茄结果,
                七猫结果,
                QQ阅读结果,
                QQ浏览器结果,
                书旗结果,
                得间结果,
                点众结果,
                塔读结果,
                百度结果,
                小米结果,
                宜搜结果,
                米读结果,
                猫眼结果,
                酷我结果,
                酷匠结果,
                连城结果,
                菠萝包结果,
                晋江结果,
                追书结果,
            ]

            async def 补搜一个词(w: str) -> tuple[list[dict[str, Any]], ...]:
                return await asyncio.gather(
                    平台搜索任务("番茄", lambda: 搜索番茄(session, w, 需要数量=10), "番茄联想"),
                    平台搜索任务("七猫", lambda: 搜索七猫(session, w, 需要数量=10), "七猫联想"),
                    平台搜索任务("书旗", lambda: 搜索书旗(session, w, 需要数量=10), "书旗联想结果"),
                    平台搜索任务("QQ阅读", lambda: 搜索QQ阅读(w, 需要数量=10), "QQ阅读联想"),
                    平台搜索任务("QQ浏览器", lambda: 搜索QQ浏览器(w, 需要数量=10), "QQ浏览器联想"),
                    平台搜索任务("得间", lambda: 搜索得间(w, 需要数量=10), "得间联想"),
                    平台搜索任务("点众", lambda: 搜索点众(w, 需要数量=10), "点众联想"),
                    平台搜索任务("塔读", lambda: 搜索塔读(w, 需要数量=10), "塔读联想"),
                    平台搜索任务("百度", lambda: 搜索百度(w, 需要数量=10), "百度联想"),
                    平台搜索任务("小米", lambda: 搜索小米(w, 需要数量=10), "小米联想"),
                    平台搜索任务("宜搜", lambda: 搜索宜搜(w, 需要数量=10), "宜搜联想"),
                    平台搜索任务("米读", lambda: 搜索米读(w, 需要数量=10), "米读联想"),
                    平台搜索任务("猫眼", lambda: 搜索猫眼(w, 需要数量=10), "猫眼联想"),
                    平台搜索任务("酷我", lambda: 搜索酷我(w, 需要数量=10), "酷我联想"),
                    平台搜索任务("酷匠", lambda: 搜索酷匠(w, 需要数量=10), "酷匠联想"),
                    平台搜索任务("连城", lambda: 搜索连城(w, 需要数量=10), "连城联想"),
                    平台搜索任务("菠萝包", lambda: 搜索菠萝包(w, 需要数量=10), "菠萝包联想"),
                    平台搜索任务("晋江", lambda: 搜索晋江(w, 需要数量=10), "晋江联想"),
                    平台搜索任务("追书", lambda: 搜索追书(session, w, 需要数量=10), "追书联想"),
                )

            补搜结果 = await asyncio.gather(*(补搜一个词(w) for w in 补搜词))
            for 补搜项 in 补搜结果:
                补搜项 = list(补搜项)
                for 平台结果 in 补搜项:
                    for 排名, 项 in enumerate(平台结果):
                        if isinstance(项, dict):
                            项.setdefault("_platform_rank", 排名)
                r1 = await 过滤无目录番茄搜索结果(
                    补搜项[0],
                    关键词,
                    搜索类型=搜索类型,
                    最大数量=5,
                )
                r4 = await 过滤章节单独付费QQ阅读搜索结果(补搜项[3])
                补搜项[0] = r1
                补搜项[3] = r4
                补结果集合.extend(补搜项)
            合并 = 去重合并(补结果集合)
        return 排序找书结果(合并, 关键词, 搜索类型)


async def 聚合搜索(
    关键词: str,
    搜索类型: str = "auto",
    允许平台: Any = None,
) -> list[dict[str, Any]]:
    """搜索结果短缓存，避免重复查询反复等待所有平台响应。"""
    关键词 = 清理搜索关键词(关键词)
    if not 关键词:
        return []
    缓存键 = (规范标题(关键词), str(搜索类型 or "auto"))
    if not 缓存键[0]:
        return []
    允许平台集合 = _规范化允许平台(允许平台)
    缓存键 = (缓存键[0], 缓存键[1], tuple(sorted(允许平台集合)))
    现在 = time.monotonic()
    缓存 = 找书结果缓存.get(缓存键)
    if 缓存 is not None:
        缓存时间, 缓存结果 = 缓存
        if 现在 - 缓存时间 < 找书结果缓存秒数:
            return _过滤不可用平台结果(
                [dict(项) for 项 in 缓存结果], 允许平台集合
            )
        找书结果缓存.pop(缓存键, None)

    结果 = await _聚合搜索未缓存(
        关键词,
        搜索类型,
        允许平台=允许平台集合,
    )
    结果 = _过滤不可用平台结果(结果, 允许平台集合)
    找书结果缓存[缓存键] = (time.monotonic(), [dict(项) for 项 in 结果])
    if len(找书结果缓存) > 找书结果缓存上限:
        最旧键 = min(找书结果缓存, key=lambda key: 找书结果缓存[key][0])
        找书结果缓存.pop(最旧键, None)
    return [dict(项) for 项 in 结果]


def 格式化找书结果(会话: dict[str, Any]) -> str:
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    总页 = max(1, (len(结果) + 每页数量 - 1) // 每页数量) if 结果 else 1
    if 页码 > 总页:
        页码 = 总页
        会话["page"] = 页码
    起始 = (页码 - 1) * 每页数量
    当前页 = 结果[起始 : 起始 + 每页数量]
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
        行.append("发送 选1～选5 下载当前页对应书籍")
    return "\n".join(行)


def _指令链编码(文本: str) -> str:
    """QQ 官方 Markdown 指令链属性必须 URL 编码，单项最多 100 个字符。"""
    值 = str(文本 or "")[:100]
    return urllib.parse.quote(值, safe="")


def _生成找书文字指令(发送文本: str, 外显文本: str) -> str:
    """把正文书名或作者渲染成可点文字。

    `qqbot-cmd-input` 支持自定义 `show` 文案；点击后只把对应命令填入
    输入框，用户发送后会进入现有的 `选N` 下载流程。
    """
    return (
        f'<qqbot-cmd-input text="{_指令链编码(发送文本)}" '
        f'show="{_指令链编码(外显文本)}" reference="false" />'
    )


def 格式化找书结果MD(会话: dict[str, Any]) -> str:
    """官方机器人 Markdown 找书结果：正文书名和作者均为可点文字。"""
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    总页 = max(1, (len(结果) + 每页数量 - 1) // 每页数量) if 结果 else 1
    if 页码 > 总页:
        页码 = 总页
        会话["page"] = 页码
    起始 = (页码 - 1) * 每页数量
    当前页 = 结果[起始 : 起始 + 每页数量]
    行: list[str] = ["**找书结果**", ""]
    if not 当前页:
        行.append("没有找到相关书籍")
    else:
        for 序号, 项 in enumerate(当前页, start=1):
            书名 = 清理文本(项.get("title") or "未知") or "未知"
            作者 = 清理文本(项.get("author") or "未知") or "未知"
            选书指令 = f"选{序号}"
            行.append(分隔线)
            行.append(f"书名：{_生成找书文字指令(选书指令, 书名)}")
            行.append(f"作者：{_生成找书文字指令(选书指令, 作者)}")
        行.append(分隔线)
    行.append(f"当前页数：{页码}/{总页}")
    翻页: list[str] = []
    if 页码 > 1:
        翻页.append(_生成找书文字指令("上一页", "上一页"))
    if 页码 < 总页:
        翻页.append(_生成找书文字指令("下一页", "下一页"))
    if 翻页:
        行.append("  ".join(翻页))
    if 当前页:
        行.append("点击书名或作者后发送即可下载")
    return "\n".join(行)


def 获取当前页结果(会话: dict[str, Any]) -> list[dict[str, Any]]:
    结果: list[dict[str, Any]] = 会话.get("results") or []
    页码 = max(1, int(会话.get("page") or 1))
    起始 = (页码 - 1) * 每页数量
    return 结果[起始 : 起始 + 每页数量]


选书命令正则 = re.compile(r"^选([1-5])$")


def 解析找书选中项(
    event: Any, 命令文本: str, 配置: Any = None
) -> dict[str, Any] | str | None:
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
    允许平台 = _规范化允许平台(
        小说功能开关.获取当前事件可用小说平台(event, 配置)
    )
    if _更新会话可用结果(会话, 允许平台):
        找书会话.pop(获取找书会话键(event), None)
        return "找书结果已更新，请重新发送 找 关键词"
    当前页 = 获取当前页结果(会话)
    if not 当前页:
        return "没有可选书籍"
    序号 = int(匹配.group(1))
    if 序号 < 1 or 序号 > len(当前页):
        return "下载失败"
    return 当前页[序号 - 1]


def 获取找书下载回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[Any] | str | None:
    """main 优先调用：用户点击指令链发出 选N 后，这里直接进入各平台下载流。"""
    文本 = str(命令文本 or "").strip()
    if not 选书命令正则.fullmatch(文本):
        return None
    if not 小说功能开关.小说总开关是否开启(配置):
        找书会话.clear()
        return 小说功能开关.获取小说功能关闭回复("", 配置)
    选中 = 解析找书选中项(event, 命令文本, 配置)
    if 选中 is None:
        return None
    if isinstance(选中, str):
        return 选中
    平台 = str(选中.get("platform") or "")
    链接 = str(选中.get("url") or "")
    书籍编号 = str(选中.get("book_id") or "").strip()
    标题 = 选中.get("title") or ""
    if not 小说功能开关.当前事件可使用小说功能(event, 平台, 配置):
        return 小说功能开关.获取小说功能关闭回复(平台, 配置)
    logger.info(f"找书选择下载：平台={平台}, 书名={标题}, 书籍编号={书籍编号}")
    if 平台 == "番茄" and 番茄小说 is not None:
        # 找书结果只在内部把已校验的书籍 ID 交给下载器，不开放裸 ID 消息入口。
        if not re.fullmatch(r"\d{15,25}", 书籍编号):
            return "下载失败"
        return 番茄小说.生成番茄下载回复流(
            event,
            书籍编号,
            配置,
            找书候选=选中,
        )
    if not 链接:
        return "下载失败"
    if 平台 == "七猫" and 七猫小说 is not None:
        return 七猫小说.生成下载回复流(event, 链接, 配置)
    if 平台 == "书旗" and 书旗小说 is not None:
        return 书旗小说.生成下载回复流(event, 链接, 配置)
    if 平台 == "追书" and 追书小说 is not None:
        return 追书小说.生成下载回复流(event, 链接, 配置)
    if 平台 == "QQ阅读" and QQ阅读小说 is not None:
        return QQ阅读小说.生成下载回复流(event, 链接, 配置)
    if 平台 == "QQ浏览器" and QQ浏览器小说 is not None:
        return QQ浏览器小说.生成QQ浏览器下载回复流(event, 链接, 配置)
    if 平台 == "得间" and 得间小说 is not None:
        return 得间小说.生成下载回复流(event, 链接, 配置)
    if 平台 == "点众" and 点众小说 is not None:
        return 点众小说.生成下载回复流(event, 链接, 配置)
    if 平台 == "塔读" and 塔读小说 is not None:
        return 塔读小说.生成塔读下载回复流(event, 链接, 配置)
    if 平台 == "百度" and 百度小说 is not None:
        return 百度小说.生成百度下载回复流(event, 链接, 配置)
    if 平台 == "小米" and 小米小说 is not None:
        return 小米小说.生成小米下载回复流(event, 链接, 配置)
    if 平台 == "宜搜" and 宜搜小说 is not None:
        return 宜搜小说.生成宜搜下载回复流(event, 链接, 配置)
    if 平台 == "米读" and 米读小说 is not None:
        return 米读小说.生成米读下载回复流(event, 链接, 配置)
    if 平台 == "猫眼" and 猫眼小说 is not None:
        return 猫眼小说.生成猫眼下载回复流(event, 链接, 配置)
    if 平台 == "酷我" and 酷我小说 is not None:
        return 酷我小说.生成酷我下载回复流(event, 链接, 配置)
    if 平台 == "酷匠" and 酷匠小说 is not None:
        return 酷匠小说.生成酷匠下载回复流(event, 链接, 配置)
    if 平台 == "连城" and 连城小说 is not None:
        return 连城小说.生成连城下载回复流(event, 链接, 配置)
    if 平台 == "菠萝包" and 菠萝包小说 is not None:
        return 菠萝包小说.生成菠萝包下载回复流(event, 链接, 配置)
    if 平台 == "晋江" and 晋江小说 is not None:
        return 晋江小说.生成晋江下载回复流(event, 链接, 配置)
    return "下载失败"


async def 处理找书指令(
    event: Any, 命令文本: str, 配置: Any = None
) -> str | dict[str, Any] | None:
    """返回纯文本；官方机器人返回内嵌文字指令链的 Markdown。"""
    清理过期会话()
    文本 = str(命令文本 or "").strip()
    会话键 = 获取找书会话键(event)
    查询 = 解析找书查询(文本)
    if not 会话键 and 查询 is not None:
        return "暂时无法识别当前用户，请稍后再试"
    是当前会话翻页 = 文本 in 翻页命令集合 and 会话键 in 找书会话
    if 查询 is None and not 是当前会话翻页:
        # 找书处理器会被主分发器对每条消息调用；非找书消息不读取开关状态。
        return None
    if (查询 is not None or 是当前会话翻页) and not 小说功能开关.小说总开关是否开启(
        配置
    ):
        找书会话.clear()
        return 小说功能开关.获取小说功能关闭回复("", 配置)
    允许平台 = _规范化允许平台(
        小说功能开关.获取当前事件可用小说平台(event, 配置)
    )
    会话 = None
    if 查询 is not None:
        关键词 = 查询["keyword"]
        搜索类型 = 查询["type"]
        try:
            结果 = _过滤不可用平台结果(
                await 聚合搜索(
                    关键词,
                    搜索类型,
                    允许平台=允许平台,
                ),
                允许平台,
            )
        except Exception as exc:
            logger.warning(
                f"找书搜索失败：关键词={关键词}, 类型={搜索类型}, 错误={exc}"
            )
            return "搜索失败，请稍后再试"
        logger.info(
            f"找书搜索完成：关键词={关键词}, 类型={搜索类型}, "
            f"总数={len(结果)}, 会话={会话键}"
        )
        if not 结果:
            找书会话.pop(会话键, None)
            return f"没有找到和「{关键词}」相关的书"
        会话 = {
            "keyword": 关键词,
            "search_type": 搜索类型,
            "results": 结果,
            "allowed_platforms": tuple(sorted(允许平台)),
            "page": 1,
            "ts": time.time(),
        }
        找书会话[会话键] = 会话
    else:
        # 选书指令由 获取找书下载回复流 处理，这里直接跳过
        会话 = 找书会话.get(会话键)
        if not 会话:
            return None
        会话["ts"] = time.time()
        if _更新会话可用结果(会话, 允许平台):
            找书会话.pop(会话键, None)
            return "找书结果已更新，请重新发送 找 关键词"
        if not 会话["results"]:
            找书会话.pop(会话键, None)
            return "没有可用书籍，请重新发送 找 关键词"
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
            "keyboard": None,
            "text": 格式化找书结果(会话),
        }
    return 格式化找书结果(会话)


def 是否找书翻页会话(event: Any) -> bool:
    清理过期会话()
    return 获取找书会话键(event) in 找书会话
