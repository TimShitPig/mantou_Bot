from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

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
    "如何下载": "如何下载",
}
欢迎回调按钮ID = {
    "教程": "welcome_tutorial",
    "小说列表": "welcome_novel_list",
    "如何下载": "welcome_download",
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
        "rows": [
            {"buttons": 按钮[:2]},
            {"buttons": 按钮[2:]},
        ],
    }


def 解析欢迎回调命令(文本: str) -> str | None:
    数据 = str(文本 or "").strip()
    if not 数据.startswith(欢迎回调前缀):
        return None
    标识 = 数据[len(欢迎回调前缀) :].strip()
    return 标识 if 标识 in 欢迎回调标签 else None


def _获取小说列表内容(配置: Any = None) -> str:
    from 功能文件.管理功能.小说功能.功能 import 小说功能开关

    小说功能状态 = 小说功能开关.读取小说功能状态(配置)
    小说总开关已开启 = 小说功能开关.小说总开关是否开启(配置)
    平台行 = [
        f"- **{显示名}**：分享链接或分享卡片"
        for 功能名, 显示名 in 小说列表平台
        if 小说总开关已开启 and 小说功能状态.get(功能名, True)
    ]
    if not 平台行:
        return "\n".join(
            [
                "## 支持下载的小说\n",
                "当前没有开启的小说下载功能。",
            ]
        )
    return "\n".join(
        [
            "## 支持下载的小说\n",
            "以下平台的书籍支持下载：",
            *平台行,
            "直接发送对应书籍的分享链接或分享卡片即可下载；也可以发送 `找关键词` 搜索具体书名。",
        ]
    )


def 获取欢迎回调内容(文本: str, 配置: Any = None) -> tuple[str, dict[str, Any]] | None:
    标识 = 解析欢迎回调命令(文本)
    if 标识 is None:
        return None

    内容 = {
        "教程": "\n".join(
            [
                "## 使用教程\n",
                "**1. 直接下载**：将支持平台的小说分享链接或分享卡片直接发送到群内。",
                "**2. 找书下载**：发送 `找关键词` 或 `找书 关键词` 搜索书名、作者。",
                "**3. 精确搜索**：发送 `找书名 关键词` 只按书名找，发送 `找作者 关键词` 只按作者找。",
                "**4. 选择结果**：在搜索结果中点击书名，或手动发送 `选N`；可发送 `上一页`、`下一页` 翻页。",
                "**5. 获取文件**：下载、合成 TXT 并上传完成后，点击机器人发送的“点击打开”即可查看。",
            ]
        ),
        "小说列表": _获取小说列表内容(配置),
        "如何下载": "\n".join(
            [
                "## 如何下载小说\n",
                "**方式一：分享链接或卡片**\n将书籍的分享链接、图文 H5 卡片或平台分享卡片直接发送到群内，机器人会识别书籍并开始下载。",
                "**方式二：找书**\n发送 `找关键词`、`找书 关键词`；需要限定条件时使用 `找书名 关键词` 或 `找作者 关键词`。",
                "**选择与翻页**\n搜索结果每页最多 5 本，点击结果或发送 `选1` 至 `选5` 下载；发送 `上一页`、`下一页` 浏览更多结果。",
                "**下载完成**\n机器人会先下载并合成完整 TXT，随后上传到当前网盘，并在同一条完成消息中提供“点击打开”链接。",
            ]
        ),
    }
    return 内容[标识], 获取欢迎键盘()


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
                数据.get(字段) not in (None, "", 0, "0") for 字段 in ("code", "err_code")
            ):
                return ""
            资料 = 数据.get("data")
            链接 = 资料.get("url") if isinstance(资料, dict) else None
            if (not isinstance(链接, str) or len(链接) > 4096
                    or any(字符.isspace() or ord(字符) < 32 or ord(字符) == 127 for 字符 in 链接)):
                return ""
            地址 = urlsplit(链接)
            if (地址.scheme != "https" or 地址.hostname != "qun.qq.com"
                    or 地址.username is not None or 地址.password is not None
                    or 地址.port not in (None, 443)):
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
            "点击下方按钮查看机器人的使用教程、可下载小说和下载方式。",
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
