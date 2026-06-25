from __future__ import annotations

import json
import re
import time
from typing import Any

from astrbot.api import logger

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 是QQ官方机器人, 获取发送者QQ, 读取字段


帮助选择等待秒数 = 120
待选择帮助会话: dict[str, dict[str, Any]] = {}

帮助大类 = [
    {
        "名称": "主动触发",
        "小类": [
            {
                "名称": "API功能",
                "触发项": [
                    {"名称": "随机英文单词", "触发": "随机英文单词", "详情": "返回单词、翻译、例句和译文。"},
                    {"名称": "随机一言", "触发": "随机一言", "详情": "返回一言内容、出处和时间。"},
                    {"名称": "疯狂星期四", "触发": "疯狂星期四", "详情": "返回随机 KFC 文案。"},
                    {"名称": "古诗词名句", "触发": "古诗词名句", "详情": "返回名句、作者和作品。"},
                    {"名称": "番茄小说API切换", "触发": "查看API -> 1 / 2", "详情": "发送 查看API 后，在 120 秒内发送 1 切换 OIAPI，发送 2 切换析API。"},
                ],
            },
            {
                "名称": "管理功能",
                "触发项": [
                    {"名称": "踢人", "触发": "@用户 踢 / @用户 踢了", "详情": "管理员可一次 @ 多个用户踢出，当前群成功后会跨群检查并踢出；每个目标用户最多撤回最近 50 条消息。"},
                    {"名称": "全员禁言", "触发": "开启禁言 / 关闭禁言 / 开启全部禁言 / 关闭全部禁言", "详情": "管理员可开启或关闭当前群及机器人所在全部群的全员禁言。"},
                    {"名称": "群文件清理", "触发": "清理群文件 / 群文件清理 / 清理全部群文件", "详情": "扫描并发删除当前群或机器人所在全部群的群文件。"},
                    {"名称": "授权链接", "触发": "授权 / 授权 数字群号 / 授权 数字群号 机器人QQ", "详情": "生成 QQ 群服务授权链接。"},
                    {"名称": "小说开关", "触发": "开启番茄 / 关闭番茄 / 开启七猫 / 关闭七猫", "详情": "管理员可开关番茄小说和七猫小说下载功能。"},
                    {"名称": "付费开关", "触发": "开启收费 / 关闭收费 / 开启群聊收费 / 关闭群聊收费 / 开启私聊收费 / 关闭私聊收费", "详情": "关闭收费让未单独设置开关的范围免费，已单独开启收费的群聊/私聊仍收费；开启收费强制全部收费。"},
                    {"名称": "状态", "触发": "状态", "详情": "查看系统信息、插件版本、小说功能开关、当前番茄 API、收费开关和网盘启用状态。"},
                    {"名称": "帮助", "触发": "帮助 / 帮助 数字 / 0", "详情": "查看帮助菜单，数字选择下一层，0 返回上一层。"},
                ],
            },
            {
                "名称": "用户激活",
                "触发项": [
                    {"名称": "激活用户", "触发": "@用户 激活 [天数] / 激活 用户QQ [天数]", "详情": "默认 30 天，支持一次操作多个 @ 或 QQ 号。"},
                    {"名称": "重置用户", "触发": "@用户 重置 / 重置 用户QQ", "详情": "取消用户激活，支持批量。"},
                    {"名称": "增加时间", "触发": "@用户 增加 天数 / 增加 用户QQ 天数", "详情": "在原到期时间基础上增加天数。"},
                    {"名称": "减少时间", "触发": "@用户 减少 天数 / 减少 用户QQ 天数", "详情": "在原到期时间基础上减少天数，到期则取消激活。"},
                    {"名称": "查询", "触发": "查询 / 查询 用户QQ / @用户 查询", "详情": "普通用户查自己，管理员可查指定用户；回复会显示 QQ、卡密、激活天数、剩余时间、激活时间和结束时间。"},
                    {"名称": "查询用户", "触发": "查询用户 / 下一页 / 下 / 上一页 / 上", "详情": "分页查看当前群已激活用户，每页 10 条，按剩余时间从少到多显示 QQ、卡密和剩余时间。"},
                    {"名称": "生成卡密", "触发": "生成卡密 [数量]", "详情": "生成 12 位一次性激活卡密，默认 1 个。"},
                    {"名称": "查询卡密", "触发": "查询卡密 -> 1/2/0 / 查询卡密 [使用/没使用/筛选] / 下一页 / 下 / 上一页 / 上 / 复制 [天数]", "详情": "查询卡密先选择已使用或未使用；已有查询结果时，发送 复制 输出全部卡密，发送 复制 30 只输出 30 天卡密。"},
                ],
            },
        ],
    },
    {
        "名称": "被动触发",
        "小类": [
            {
                "名称": "小说功能",
                "触发项": [
                    {"名称": "七猫小说", "触发": "七猫链接/七猫分享卡片", "详情": "识别七猫链接或分享卡片，下载 txt 并发送。"},
                    {"名称": "番茄小说", "触发": "番茄链接/番茄 JSON 分享卡片", "详情": "识别番茄链接或分享卡片，按当前选择的 API 下载 txt 并发送。"},
                ],
            },
            {
                "名称": "群管功能",
                "触发项": [
                    {"名称": "数字撤回", "触发": "连续 9-12 位数字", "详情": "QQ群主和管理员不撤回；普通成员撤回当前消息并拉取 100 条群历史，最多撤回该用户最近 8 条消息；同一成员累计 3 次后跨群踢出。"},
                    {"名称": "卡片撤回", "触发": "群名片/JSON 卡片/群分享卡片", "详情": "QQ群主和管理员不撤回；普通成员自动撤回当前卡片消息，并最多撤回该用户最近 8 条消息。"},
                    {"名称": "合并转发撤回", "触发": "合并转发/聊天记录", "详情": "QQ群主和管理员不撤回；普通成员自动撤回当前合并转发消息，并最多撤回该用户最近 8 条消息。"},
                    {"名称": "QQ闪传撤回", "触发": "QQ闪传", "详情": "QQ群主和管理员不撤回；普通成员自动撤回当前 QQ 闪传消息，并最多撤回该用户最近 8 条消息。"},
                ],
            },
        ],
    },
]


def 处理帮助指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None

    会话键 = 获取帮助会话键(event)
    帮助匹配 = re.fullmatch(r"帮助\s*(\d{1,2})?", 文本, re.IGNORECASE)
    if 帮助匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用帮助"
        编号 = 帮助匹配.group(1)
        if 编号:
            return 进入帮助小类(会话键, 编号)
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类()

    帮助状态 = 获取有效帮助状态(会话键)
    if re.fullmatch(r"\d{1,2}", 文本) and 帮助状态 is not None:
        if not 是群文件清理管理员(event, 配置):
            待选择帮助会话.pop(会话键, None)
            return "没有权限使用帮助"
        return 处理帮助数字选择(会话键, 帮助状态, 文本)

    return None


def 格式化帮助大类() -> str:
    行列表 = ["请选择帮助大类："]
    for 序号, 大类 in enumerate(帮助大类, start=1):
        行列表.append(f"{序号}. {大类['名称']}")
    行列表.append(f"请在 {帮助选择等待秒数} 秒内发送数字查看小类，例如 1")
    行列表.append("也可以直接发送：帮助 1")
    return "\n".join(行列表)


def 进入帮助小类(会话键: str, 编号文本: str) -> str:
    编号 = int(编号文本)
    if 编号 < 1 or 编号 > len(帮助大类):
        return f"帮助编号无效，请发送 1-{len(帮助大类)}"
    设置帮助状态(会话键, "小类", 编号 - 1)
    return 格式化帮助小类(编号 - 1)


def 格式化帮助小类(大类序号: int) -> str:
    大类 = 帮助大类[大类序号]
    行列表 = [f"{大类['名称']}："]
    for 序号, 小类 in enumerate(大类["小类"], start=1):
        行列表.append(f"{序号}. {小类['名称']}")
    行列表.append("0. 返回上一步")
    return "\n".join(行列表)


def 进入触发项列表(会话键: str, 大类序号: int, 小类编号文本: str) -> str:
    小类编号 = int(小类编号文本)
    小类列表 = 帮助大类[大类序号]["小类"]
    if 小类编号 < 1 or 小类编号 > len(小类列表):
        return f"帮助编号无效，请发送 1-{len(小类列表)} 或 0 返回上一步"
    小类序号 = 小类编号 - 1
    设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
    return 格式化触发项列表(大类序号, 小类序号)


def 格式化触发项列表(大类序号: int, 小类序号: int) -> str:
    小类 = 帮助大类[大类序号]["小类"][小类序号]
    行列表 = [f"{小类['名称']}："]
    for 序号, 触发项 in enumerate(小类["触发项"], start=1):
        行列表.append(f"{序号}. {触发项['触发']}")
    行列表.append("0. 返回上一步")
    return "\n".join(行列表)


def 格式化帮助详情(大类序号: int, 小类序号: int, 触发编号文本: str) -> str:
    触发编号 = int(触发编号文本)
    触发项列表 = 帮助大类[大类序号]["小类"][小类序号]["触发项"]
    if 触发编号 < 1 or 触发编号 > len(触发项列表):
        return f"帮助编号无效，请发送 1-{len(触发项列表)} 或 0 返回上一步"

    触发项 = 触发项列表[触发编号 - 1]
    return "\n".join([
        触发项["名称"],
        f"触发：{触发项['触发']}",
        触发项["详情"],
        "0. 返回上一步",
    ])


def 处理帮助数字选择(会话键: str, 帮助状态: dict[str, Any], 编号文本: str) -> str:
    层级 = 帮助状态.get("层级")
    大类序号 = 帮助状态.get("大类序号")
    小类序号 = 帮助状态.get("小类序号")

    if 编号文本 == "0":
        return 返回帮助上一层(会话键, 层级, 大类序号, 小类序号)

    if 层级 == "大类":
        return 进入帮助小类(会话键, 编号文本)

    if 层级 == "小类" and isinstance(大类序号, int):
        return 进入触发项列表(会话键, 大类序号, 编号文本)

    if 层级 in {"触发项", "详情"} and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "详情", 大类序号, 小类序号)
        return 格式化帮助详情(大类序号, 小类序号, 编号文本)

    设置帮助状态(会话键, "大类")
    return 格式化帮助大类()


def 返回帮助上一层(会话键: str, 层级: str, 大类序号: Any, 小类序号: Any) -> str:
    if 层级 == "详情" and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
        return 格式化触发项列表(大类序号, 小类序号)
    if 层级 == "触发项" and isinstance(大类序号, int):
        设置帮助状态(会话键, "小类", 大类序号)
        return 格式化帮助小类(大类序号)
    if 层级 == "小类":
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类()
    待选择帮助会话.pop(会话键, None)
    return "已退出帮助菜单"


def 设置帮助状态(会话键: str, 层级: str, 大类序号: int | None = None, 小类序号: int | None = None) -> None:
    待选择帮助会话[会话键] = {
        "时间": time.time(),
        "层级": 层级,
        "大类序号": 大类序号,
        "小类序号": 小类序号,
    }


def 获取有效帮助状态(会话键: str) -> dict[str, Any] | None:
    帮助状态 = 待选择帮助会话.get(会话键)
    if not 帮助状态:
        return None
    开始时间 = 帮助状态.get("时间")
    if isinstance(开始时间, (int, float)) and time.time() - 开始时间 <= 帮助选择等待秒数:
        return 帮助状态
    待选择帮助会话.pop(会话键, None)
    return None


def 获取帮助会话键(event: Any) -> str:
    群号 = 获取群号(event)
    用户QQ = 获取发送者QQ(event)
    return f"{群号 or 'private'}:{用户QQ or 'unknown'}"


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
        if hasattr(值, "group_id"):
            值 = 值.group_id
        if isinstance(值, dict):
            值 = 值.get("group_id") or 值.get("group_openid") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 获取群openid同步(event: Any) -> str:
    return 获取群号(event)


def 获取用户openid同步(event: Any) -> str:
    方法 = getattr(event, "get_sender_id", None)
    if callable(方法):
        try:
            值 = 方法()
            if hasattr(值, "__await__"):
                值 = None
            if 值:
                return str(值)
        except Exception:
            pass

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "sender")
        if 值:
            if hasattr(值, "user_id"):
                值 = 值.user_id
            elif isinstance(值, dict):
                值 = 值.get("user_id") or 值.get("user_openid") or 值.get("member_openid")
            if 值:
                return str(值)
        值 = 读取字段(对象, "user_openid") or 读取字段(对象, "openid")
        if 值:
            return str(值)
    return ""


def 格式化帮助大类MD() -> str:
    行列表 = ["## 请选择帮助大类\n"]
    for 序号, 大类 in enumerate(帮助大类, start=1):
        行列表.append(f"**{序号}.** {大类['名称']}")
    行列表.append(f"\n请在 {帮助选择等待秒数} 秒内发送数字查看小类，例如 `1`")
    行列表.append("也可以直接发送：`帮助 1`")
    return "\n".join(行列表)


def 格式化帮助小类MD(大类序号: int) -> str:
    大类 = 帮助大类[大类序号]
    行列表 = [f"## {大类['名称']}\n"]
    for 序号, 小类 in enumerate(大类["小类"], start=1):
        行列表.append(f"**{序号}.** {小类['名称']}")
    行列表.append("\n**0.** 返回上一步")
    return "\n".join(行列表)


def 格式化触发项列表MD(大类序号: int, 小类序号: int) -> str:
    小类 = 帮助大类[大类序号]["小类"][小类序号]
    行列表 = [f"## {小类['名称']}\n"]
    for 序号, 触发项 in enumerate(小类["触发项"], start=1):
        行列表.append(f"**{序号}.** `{触发项['触发']}`")
    行列表.append("\n**0.** 返回上一步")
    return "\n".join(行列表)


def 格式化帮助详情MD(大类序号: int, 小类序号: int, 触发编号文本: str) -> str:
    触发编号 = int(触发编号文本)
    触发项列表 = 帮助大类[大类序号]["小类"][小类序号]["触发项"]
    if 触发编号 < 1 or 触发编号 > len(触发项列表):
        return f"帮助编号无效，请发送 1-{len(触发项列表)} 或 0 返回上一步"

    触发项 = 触发项列表[触发编号 - 1]
    return "\n".join([
        f"## {触发项['名称']}\n",
        f"**触发：** `{触发项['触发']}`\n",
        触发项["详情"],
        "\n**0.** 返回上一步",
    ])


def 进入帮助小类MD(会话键: str, 编号文本: str) -> str:
    编号 = int(编号文本)
    if 编号 < 1 or 编号 > len(帮助大类):
        return f"帮助编号无效，请发送 1-{len(帮助大类)}"
    设置帮助状态(会话键, "小类", 编号 - 1)
    return 格式化帮助小类MD(编号 - 1)


def 进入触发项列表MD(会话键: str, 大类序号: int, 小类编号文本: str) -> str:
    小类编号 = int(小类编号文本)
    小类列表 = 帮助大类[大类序号]["小类"]
    if 小类编号 < 1 or 小类编号 > len(小类列表):
        return f"帮助编号无效，请发送 1-{len(小类列表)} 或 0 返回上一步"
    小类序号 = 小类编号 - 1
    设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
    return 格式化触发项列表MD(大类序号, 小类序号)


def 处理帮助数字选择MD(会话键: str, 帮助状态: dict[str, Any], 编号文本: str) -> str:
    层级 = 帮助状态.get("层级")
    大类序号 = 帮助状态.get("大类序号")
    小类序号 = 帮助状态.get("小类序号")

    if 编号文本 == "0":
        return 返回帮助上一层MD(会话键, 层级, 大类序号, 小类序号)

    if 层级 == "大类":
        return 进入帮助小类MD(会话键, 编号文本)

    if 层级 == "小类" and isinstance(大类序号, int):
        return 进入触发项列表MD(会话键, 大类序号, 编号文本)

    if 层级 in {"触发项", "详情"} and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "详情", 大类序号, 小类序号)
        return 格式化帮助详情MD(大类序号, 小类序号, 编号文本)

    设置帮助状态(会话键, "大类")
    return 格式化帮助大类MD()


def 返回帮助上一层MD(会话键: str, 层级: str, 大类序号: Any, 小类序号: Any) -> str:
    if 层级 == "详情" and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
        return 格式化触发项列表MD(大类序号, 小类序号)
    if 层级 == "触发项" and isinstance(大类序号, int):
        设置帮助状态(会话键, "小类", 大类序号)
        return 格式化帮助小类MD(大类序号)
    if 层级 == "小类":
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类MD()
    待选择帮助会话.pop(会话键, None)
    return "已退出帮助菜单"


def 处理帮助指令MD(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None

    会话键 = 获取帮助会话键(event)
    帮助匹配 = re.fullmatch(r"帮助\s*(\d{1,2})?", 文本, re.IGNORECASE)
    if 帮助匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用帮助"
        编号 = 帮助匹配.group(1)
        if 编号:
            return 进入帮助小类MD(会话键, 编号)
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类MD()

    帮助状态 = 获取有效帮助状态(会话键)
    if re.fullmatch(r"\d{1,2}", 文本) and 帮助状态 is not None:
        if not 是群文件清理管理员(event, 配置):
            待选择帮助会话.pop(会话键, None)
            return "没有权限使用帮助"
        return 处理帮助数字选择MD(会话键, 帮助状态, 文本)

    return None


def 生成按钮(编号: str, 标签: str, 点击后标签: str = "", 自动发送: bool = False) -> dict[str, Any]:
    动作: dict[str, Any] = {
        "type": 2,
        "permission": {"type": 2},
        "data": 编号,
        "unsupport_tips": "请发送对应数字",
    }
    if 自动发送:
        动作["enter"] = True
    return {
        "id": 编号,
        "render_data": {"label": 标签, "visited_label": 点击后标签 or 标签},
        "action": 动作,
    }


def 生成返回按钮(自动发送: bool = False) -> dict[str, Any]:
    return 生成按钮("0", "返回上一步", "已返回", 自动发送)


def 按钮分行(按钮列表: list[dict[str, Any]], 每行最多: int = 5) -> list[dict[str, Any]]:
    return [{"buttons": 按钮列表[开始:开始 + 每行最多]} for 开始 in range(0, len(按钮列表), 每行最多)]


def 生成帮助大类键盘(自动发送: bool = False) -> dict[str, Any]:
    按钮列表 = [生成按钮(str(序号), 大类["名称"], 自动发送=自动发送) for 序号, 大类 in enumerate(帮助大类, start=1)]
    按钮列表.append(生成返回按钮(自动发送))
    return {"rows": 按钮分行(按钮列表)}


def 生成帮助小类键盘(大类序号: int, 自动发送: bool = False) -> dict[str, Any]:
    大类 = 帮助大类[大类序号]
    按钮列表 = [生成按钮(str(序号), 小类["名称"], 自动发送=自动发送) for 序号, 小类 in enumerate(大类["小类"], start=1)]
    按钮列表.append(生成返回按钮(自动发送))
    return {"rows": 按钮分行(按钮列表)}


def 生成触发项列表键盘(大类序号: int, 小类序号: int, 自动发送: bool = False) -> dict[str, Any]:
    小类 = 帮助大类[大类序号]["小类"][小类序号]
    按钮列表 = [生成按钮(str(序号), 触发项["名称"], 自动发送=自动发送) for 序号, 触发项 in enumerate(小类["触发项"], start=1)]
    按钮列表.append(生成返回按钮(自动发送))
    return {"rows": 按钮分行(按钮列表)}


def 生成帮助详情键盘(自动发送: bool = False) -> dict[str, Any]:
    return {"rows": [{"buttons": [生成返回按钮(自动发送)]}]}


def 获取帮助键盘(会话键: str, 自动发送: bool = False) -> dict[str, Any] | None:
    帮助状态 = 获取有效帮助状态(会话键)
    if 帮助状态 is None:
        return None
    层级 = 帮助状态.get("层级")
    大类序号 = 帮助状态.get("大类序号")
    小类序号 = 帮助状态.get("小类序号")
    if 层级 == "大类":
        return 生成帮助大类键盘(自动发送)
    if 层级 == "小类" and isinstance(大类序号, int):
        return 生成帮助小类键盘(大类序号, 自动发送)
    if 层级 == "触发项" and isinstance(大类序号, int) and isinstance(小类序号, int):
        return 生成触发项列表键盘(大类序号, 小类序号, 自动发送)
    if 层级 == "详情":
        return 生成帮助详情键盘(自动发送)
    return None


def 处理帮助指令MD带键盘(event: Any, 命令文本: str, 配置: Any) -> tuple[str | None, dict[str, Any] | None]:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None, None

    会话键 = 获取帮助会话键(event)
    自动发送 = not 获取群号(event)
    帮助匹配 = re.fullmatch(r"帮助\s*(\d{1,2})?", 文本, re.IGNORECASE)
    if 帮助匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用帮助", None
        编号 = 帮助匹配.group(1)
        if 编号:
            md文本 = 进入帮助小类MD(会话键, 编号)
        else:
            设置帮助状态(会话键, "大类")
            md文本 = 格式化帮助大类MD()
        键盘 = 获取帮助键盘(会话键, 自动发送)
        return md文本, 键盘

    帮助状态 = 获取有效帮助状态(会话键)
    if re.fullmatch(r"\d{1,2}", 文本) and 帮助状态 is not None:
        if not 是群文件清理管理员(event, 配置):
            待选择帮助会话.pop(会话键, None)
            return "没有权限使用帮助", None
        md文本 = 处理帮助数字选择MD(会话键, 帮助状态, 文本)
        键盘 = 获取帮助键盘(会话键, 自动发送)
        return md文本, 键盘

    return None, None


async def 发送Markdown键盘消息(event: Any, md文本: str, 键盘: dict[str, Any] | None) -> bool:
    bot = getattr(event, "bot", None)
    api = getattr(bot, "api", None) if bot else None
    _http = getattr(api, "_http", None) if api else None
    if _http is None:
        logger.warning(f"[帮助MD键盘] 无法获取 _http，bot={type(bot).__name__ if bot else None}，api={type(api).__name__ if api else None}")
        return False

    try:
        import botpy.http as _botpy_http
        import random as _random
        Route = _botpy_http.Route
    except Exception as e:
        logger.warning(f"[帮助MD键盘] 导入 botpy.http 失败: {e}")
        return False

    消息对象 = getattr(event, "message_obj", None)
    消息ID = ""
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "message_id") or 读取字段(对象, "id") or 读取字段(对象, "msg_id")
        if 值:
            消息ID = str(值)
            break

    消息体: dict[str, Any] = {
        "content": "",
        "msg_type": 2,
        "markdown": {"content": md文本},
        "msg_seq": _random.randint(1, 10000),
    }
    if 消息ID:
        消息体["msg_id"] = 消息ID
    if 键盘 is not None:
        消息体["keyboard"] = {"content": 键盘}

    群openid = 获取群openid同步(event)
    if 群openid:
        route = Route("POST", "/v2/groups/{group_openid}/messages", group_openid=群openid)
        logger.info(f"[帮助MD键盘] 群聊发送，group_openid={群openid}，消息ID={消息ID}，按钮行数={len(键盘.get('rows', [])) if 键盘 else 0}")
    else:
        用户openid = 获取用户openid同步(event)
        if not 用户openid:
            logger.warning("[帮助MD键盘] 无法获取 group_openid 和 user_openid")
            return False
        route = Route("POST", "/v2/users/{openid}/messages", openid=用户openid)
        logger.info(f"[帮助MD键盘] 私聊发送，user_openid={用户openid}")

    try:
        响应 = await _http.request(route, json=消息体)
        logger.info(f"[帮助MD键盘] 发送成功，响应={响应}")
        return True
    except Exception as e:
        logger.warning(f"[帮助MD键盘] 发送失败: {type(e).__name__}: {e}")
        return False