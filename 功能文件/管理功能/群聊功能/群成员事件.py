from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit

import aiohttp

from 功能文件.管理功能.基础功能 import 帮助功能

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)


群成员加入事件标记 = "mantou_group_member_add"
欢迎回调前缀 = "欢迎回调:"
欢迎回调标签 = {
    "教程": "使用教程",
    "小说列表": "小说列表",
}
欢迎回调按钮ID = {
    "教程": "welcome_tutorial",
    "小说列表": "welcome_novel_list",
}
小说列表平台 = (
    ("番茄", "番茄小说"),
    ("七猫", "七猫小说"),
    ("书旗", "书旗小说"),
    ("QQ阅读", "QQ阅读"),
    ("QQ浏览器", "QQ浏览器小说"),
    ("得间", "得间小说"),
    ("点众", "点众小说"),
    ("盐言", "盐言小说"),
    ("塔读", "塔读小说"),
    ("百度", "百度小说"),
    ("小米", "小米小说"),
    ("宜搜", "宜搜小说"),
    ("米读", "米读小说"),
    ("猫眼", "猫眼小说"),
    ("酷我", "酷我小说"),
    ("酷匠", "酷匠小说"),
    ("连城", "连城小说"),
    ("菠萝包", "菠萝包小说"),
)


def _读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    if isinstance(对象, dict):
        return 对象.get(字段名, 默认值)
    return getattr(对象, 字段名, 默认值)


def _提取群成员加入数据(event: Any) -> dict[str, Any] | None:
    候选对象 = (
        event,
        _读取字段(event, "message_obj"),
        _读取字段(event, "message"),
    )
    for 候选对象项 in 候选对象:
        原始消息 = _读取字段(候选对象项, "raw_message")
        原始数据 = _读取字段(原始消息, "raw_data")
        if not isinstance(原始数据, dict):
            continue
        if 原始数据.get(群成员加入事件标记) is not True:
            continue
        事件数据 = 原始数据.get("group_member_add")
        return dict(事件数据) if isinstance(事件数据, dict) else {}
    return None


def _生成欢迎回调按钮(标识: str, 标签: str) -> dict[str, Any]:
    数据 = 欢迎回调前缀 + 标识
    return {
        "id": 欢迎回调按钮ID[标识],
        "render_data": {"label": 标签, "visited_label": "已查看"},
        "action": {
            "type": 1,
            "permission": {"type": 2},
            "data": 数据,
            "unsupport_tips": "当前客户端暂不支持该操作",
        },
    }


def 获取欢迎键盘(好友邀请链接: str = "") -> dict[str, Any]:
    按钮 = [_生成欢迎回调按钮(标识, 标签) for 标识, 标签 in 欢迎回调标签.items()]
    if 好友邀请链接:
        按钮.append({
            "id": "welcome_add_robot",
            "render_data": {"label": "添加机器人", "visited_label": "添加机器人"},
            "action": {
                "type": 0,
                "permission": {"type": 2},
                "data": 好友邀请链接,
                "unsupport_tips": "当前客户端暂不支持该操作",
            },
        })
    return {
        "rows": [{"buttons": 按钮[偏移 : 偏移 + 2]} for 偏移 in range(0, len(按钮), 2)],
    }


def 解析欢迎回调命令(文本: str) -> str | None:
    数据 = str(文本 or "").strip()
    if not 数据.startswith(欢迎回调前缀):
        return None
    标识 = 数据[len(欢迎回调前缀) :].strip()
    if 标识 == "如何下载":
        return "教程"
    return 标识 if 标识 in 欢迎回调标签 else None


def _获取小说列表内容(配置: Any = None) -> str:
    from 功能文件.管理功能.小说功能.功能 import 小说功能开关

    小说功能状态 = 小说功能开关.读取小说功能状态(配置)
    小说总开关已开启 = 小说功能开关.小说总开关是否开启(配置)
    平台名 = [
        显示名
        for 功能名, 显示名 in 小说列表平台
        if 小说总开关已开启 and 小说功能状态.get(功能名, True)
    ]
    平台行 = ["　　".join(平台名[偏移 : 偏移 + 2]) for 偏移 in range(0, len(平台名), 2)]
    return "\n\n".join(["## 小说列表", "\n".join(平台行) or "暂无开启的小说平台。"])


教程图片规格 = (
    ("share-link.jpg", 1080, 1102),
    ("search-command.png", 1080, 528),
    ("select-result.png", 1080, 1007),
    ("open-book.jpg", 1080, 1475),
)


def _获取使用教程内容(配置: Any = None) -> str:
    from 功能文件.页面功能 import 帮助网页后端

    宽度值 = 帮助网页后端._读取帮助网页字段(配置, "welcome_tutorial_image_width")
    try:
        图片宽度 = max(160, min(1080, int(宽度值))) if not isinstance(宽度值, bool) else 480
    except (TypeError, ValueError, OverflowError):
        图片宽度 = 480
    基础地址 = 帮助网页后端.获取帮助网页地址(配置)
    地址 = urlsplit(基础地址)
    图片路径 = quote(地址.path.rstrip("/"), safe="/%") + "/tutorial-images/"
    步骤 = (
        "**1. 直接下载**：把小说的分享链接直接发送到群里即可。",
        "**2. 找书**：发送 `找xx`，xx 可以是书名或作者。**一定要加“找”，不加不会进行找书。**",
        "**3. 选择小说**：在找书结果中点击书名或作者，再发送填入的选书指令即可下载。",
        "**4. 打开小说**：下载完成后点击“打开”（图中“点击打开”）即可查看小说。",
    )
    内容 = ["## 使用教程"]
    for 序号, (说明, (文件名, 原宽, 原高)) in enumerate(zip(步骤, 教程图片规格), 1):
        内容.append(说明)
        if 基础地址:
            图片地址 = urlunsplit((地址.scheme, 地址.netloc, 图片路径 + 文件名, "", ""))
            图片高度 = round(原高 * 图片宽度 / 原宽)
            内容.append(f"![步骤{序号}示例 #{图片宽度}px #{图片高度}px]({图片地址})")
    if not 基础地址:
        logger.warning("使用教程配图未生成：reason=web_service_unavailable")
    return "\n\n".join(内容)


def 获取欢迎回调内容(文本: str, 配置: Any = None) -> tuple[str, None] | None:
    标识 = 解析欢迎回调命令(文本)
    if 标识 is None:
        return None
    if 标识 == "小说列表":
        return _获取小说列表内容(配置), None
    return _获取使用教程内容(配置), None


async def _获取好友邀请链接(event: Any) -> str:
    """使用当前事件的官方认证生成带来源群的好友链接；失败保留原欢迎。"""
    阶段 = "scope"
    try:
        群号 = 帮助功能.获取群openid同步(event)
        if not isinstance(群号, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", 群号):
            return ""
        for 对象 in (event, _读取字段(event, "message_obj"), _读取字段(event, "message")):
            原始数据 = _读取字段(_读取字段(对象, "raw_message"), "raw_data")
            for 资料 in (对象, 原始数据, _读取字段(原始数据, "group_member_add")):
                for 字段 in ("group_openid", "group_id"):
                    标识 = _读取字段(资料, 字段)
                    if 标识 not in (None, "") and 标识 != 群号:
                        return ""
        http = _读取字段(_读取字段(_读取字段(event, "bot"), "api"), "_http")
        if http is None or getattr(http, "is_sandbox", False):
            return ""
        appid = str(getattr(getattr(http, "_token", None), "app_id", ""))
        if not re.fullmatch(r"[0-9]{4,32}", appid):
            return ""

        async def 请求链接() -> str:
            nonlocal 阶段
            阶段 = "auth"
            await http.check_session()
            请求头 = dict(getattr(http, "_headers", {}) or {})
            认证 = 请求头.get("Authorization", "")
            if (str(getattr(getattr(http, "_token", None), "app_id", "")) != appid
                    or not isinstance(认证, str) or not 认证.startswith("QQBot ") or not 认证[6:].strip()):
                return ""
            阶段 = "generate_url_link"
            # SDK request() 会重放连接中断的 POST；底层会话只提交一次。
            async with http._session.request(
                "POST", "https://api.bot.qq.com/v2/generate_url_link",
                headers=请求头, json={"callback_data": 群号},
                allow_redirects=False, timeout=aiohttp.ClientTimeout(total=5),
            ) as 响应:
                if not 200 <= 响应.status < 300:
                    return ""
                数据 = await 响应.json(content_type=None)
            阶段 = "response"
            if not isinstance(数据, dict) or any(
                数据.get(字段) not in (None, "", 0, "0") for 字段 in ("code", "err_code", "retcode")
            ):
                return ""
            资料 = 数据.get("data")
            链接 = 资料.get("url") if isinstance(资料, dict) else None
            if (not isinstance(链接, str) or len(链接) > 4096
                    or any(字符.isspace() or ord(字符) < 32 or ord(字符) == 127 for 字符 in 链接)):
                return ""
            地址 = urlsplit(链接)
            if (地址.scheme != "https" or 地址.hostname not in ("qun.qq.com", "bot.q.qq.com")
                    or 地址.username is not None or 地址.password is not None
                    or 地址.port not in (None, 443)):
                return ""
            if 地址.hostname == "bot.q.qq.com" and (
                not re.fullmatch(r"/s/[A-Za-z0-9_-]{6,128}", 地址.path)
                or "?" in 链接 or "#" in 链接
            ):
                return ""
            返回AppID = parse_qs(地址.query).get("robot_appid")
            if 返回AppID is not None and 返回AppID != [appid]:
                return ""
            return 链接

        # 总预算也覆盖 SDK 的认证刷新；官方未声明链接寿命，不缓存链接。
        return await asyncio.wait_for(请求链接(), timeout=5)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("QQ官方群欢迎好友链接生成失败：stage=%s, error_type=%s", 阶段, type(exc).__name__)
        return ""


async def _发送欢迎消息(event: Any, 成员openid: str) -> bool:
    好友邀请链接 = await _获取好友邀请链接(event)
    文本 = "\n".join(
        [
            f"欢迎<@{成员openid}> 加入本群",
            "",
            "点击下方按钮查看使用教程和小说列表。",
        ]
    )
    return await 帮助功能.发送Markdown键盘消息(
        event,
        文本,
        获取欢迎键盘(好友邀请链接),
        主动发送=True,
        自动提及=False,
    )


async def 发送群成员加入欢迎(event: Any, 成员openid: str) -> bool:
    """发送入群欢迎消息，供 QQ 官方网关桥直接调用。"""
    成员 = str(成员openid or "").strip()
    if not 成员:
        return False
    return await _发送欢迎消息(event, 成员)


async def 处理群成员加入事件(event: Any) -> bool:
    """消费 QQ 官方 GROUP_MEMBER_ADD 内部事件并发送欢迎消息。"""
    事件数据 = _提取群成员加入数据(event)
    if 事件数据 is None:
        return False

    群号 = str(事件数据.get("group_openid") or "").strip()
    成员 = str(事件数据.get("member_openid") or "").strip()
    有跨应用用户标识 = bool(str(事件数据.get("user_openid") or "").strip())
    if not 群号 or not 成员:
        logger.warning(
            "QQ官方群成员加入事件无效：has_group=%s, has_member=%s",
            bool(群号),
            bool(成员),
        )
        return True

    logger.info(
        "QQ官方群成员加入：group_openid=%s, member_openid=%s, has_user_openid=%s",
        群号,
        成员,
        有跨应用用户标识,
    )
    发送成功 = await _发送欢迎消息(event, 成员)
    if 发送成功:
        logger.info("QQ官方群成员欢迎消息已发送：group_openid=%s", 群号)
    else:
        logger.warning("QQ官方群成员欢迎消息发送失败：group_openid=%s", 群号)
    return True
