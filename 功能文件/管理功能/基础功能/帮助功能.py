from __future__ import annotations

import json
import re
import time
from typing import Any

from astrbot.api import logger

from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员, 是QQ官方机器人, 获取发送者QQ, 读取字段


帮助选择等待秒数 = 120
每行按钮数 = 2
待选择帮助会话: dict[str, dict[str, Any]] = {}
返回上一步别名 = {"返回上一步", "返回", "上一步", "返回上一级", "上一级"}

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
                    {"名称": "番茄小说API切换", "触发": "开启番茄API / 关闭番茄API / 查看API -> 1 / 2 / 3 / 4 / 5 或直接发送 oiapi / 析api / 崩溃api / 聚合api / y6api", "详情": "默认使用小说功能里的番茄小说下载。管理员可发送 开启番茄API 启用旧番茄API下载；发送 关闭番茄API 回到小说功能下载。开启后可发送 查看API 并在 120 秒内发送 1/2/3/4/5 切换，或直接发送 oiapi/析api/崩溃api/聚合api/y6api 快速切换。", "快捷命令": ["开启番茄API", "关闭番茄API", "查看API", "oiapi", "析api", "聚合api"]},
                ],
            },
            {
                "名称": "管理功能",
                "触发项": [
                    {"名称": "全员禁言", "触发": "开启禁言 / 关闭禁言 / 开启全部禁言 / 关闭全部禁言", "详情": "管理员可开启或关闭当前群及机器人所在全部群的全员禁言。", "快捷命令": ["开启禁言", "关闭禁言", "开启全部禁言", "关闭全部禁言"]},
                    {"名称": "群文件清理", "触发": "登录群文件 / 群文件登录cookie / 群文件状态 / 清理群文件 / 群文件清理 / 清理全部群文件 / 添加群聊 群号 / 删除群聊 群号 / 删除群聊 / 查看群聊 / 更改备注 / 更改备注 群号", "详情": "通过 QQ 群文件网页接口删除群文件，需先「登录群文件」拿 Cookie；Cookie 支持浏览器 Cookie 头、curl、Cookie Editor JSON 和 cookies.txt，保存后有 skey 时每 10 分钟自动保活；状态命令只显示群cookie生效/失效/未保存；清理群文件列出已添加群列表后点击群号按钮清理对应群（120秒有效，点返回上一步退出）；清理全部群文件清「添加群聊」添加的全部群；网页接口只删根目录文件，不递归子文件夹。", "快捷命令": ["登录群文件", "群文件状态", "清理群文件", "清理全部群文件", "查看群聊", "删除群聊", "更改备注"]},
                    {"名称": "授权链接", "触发": "授权 / 授权 数字群号 / 授权 数字群号 机器人QQ", "详情": "生成 QQ 群服务授权链接。"},
                    {"名称": "小说开关", "触发": "开启番茄 / 关闭番茄 / 开启七猫 / 关闭七猫 / 开启书旗 / 关闭书旗 / 开启QQ阅读 / 关闭QQ阅读", "详情": "管理员可开关小说功能里的番茄小说、七猫小说、书旗小说和 QQ阅读下载功能。", "快捷命令": ["开启番茄", "关闭番茄", "开启七猫", "关闭七猫", "开启书旗", "关闭书旗", "开启QQ阅读", "关闭QQ阅读"]},
                    {"名称": "状态", "触发": "状态", "详情": "查看系统信息、插件版本、小说功能开关、番茄API开关和网盘启用状态。"},
                    {"名称": "帮助", "触发": "帮助 / 帮助 数字 / 0", "详情": "查看帮助菜单，数字选择下一层，0 返回上一层。"},
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
                    {"名称": "找书", "触发": "找关键词 / 找书 关键词 / 上一页 / 下一页", "详情": "聚合搜索番茄、七猫、书旗，同平台去重后按相关度与多平台共识排序，并按相似度聚拢，每页 5 条；不显示链接和来源；官方机器人私聊点击后直接下载，群聊点击书名后发送下载；同书优先番茄>七猫>书旗。"},
                    {"名称": "七猫小说", "触发": "七猫链接/七猫分享卡片", "详情": "识别七猫链接或分享卡片，下载 txt 并发送。"},
                    {"名称": "书旗小说", "触发": "书旗链接/书旗分享卡片", "详情": "识别书旗长篇和短篇链接，优先使用批量接口并发下载 txt 后发送。"},
                    {"名称": "QQ阅读", "触发": "QQ阅读详情/目录/content链接", "详情": "识别 QQ阅读链接；默认本地 App 5 批并发下载，开启QQ阅读API 后走析API。支持管理员登录QQ阅读。"},
                    {"名称": "番茄小说", "触发": "番茄链接/番茄 JSON 分享卡片", "详情": "识别番茄链接或分享卡片，默认走小说功能内置番茄畅听下载逻辑生成 txt 并发送；开启番茄API后才走旧番茄API。"},
                ],
            },
            {
                "名称": "群管功能",
                "触发项": [
                    {"名称": "数字撤回", "触发": "连续 9-12 位数字", "详情": "QQ群主和管理员不撤回；普通成员撤回当前消息并拉取 100 条群历史，最多撤回该用户最近 8 条消息。"},
                    {"名称": "卡片撤回", "触发": "群名片/JSON 卡片/群分享卡片", "详情": "QQ群主和管理员不撤回；普通成员自动撤回当前卡片消息，并最多撤回该用户最近 8 条消息。"},
                    {"名称": "合并转发撤回", "触发": "合并转发/聊天记录", "详情": "QQ群主和管理员不撤回；普通成员自动撤回当前合并转发消息，并最多撤回该用户最近 8 条消息。"},
                    {"名称": "QQ闪传撤回", "触发": "QQ闪传", "详情": "QQ群主和管理员不撤回；普通成员自动撤回当前 QQ 闪传消息，并最多撤回该用户最近 8 条消息。"},
                ],
            },
        ],
    },
]


# ===== 状态机 =====
# 层级: 大类 -> 小类 -> 触发项 -> 详情
# 状态字段: 层级, 大类序号, 小类序号, 触发项序号(小类内)


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
            return 进入大类小类列表(会话键, 编号)
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类()

    帮助状态 = 获取有效帮助状态(会话键)
    是管理员 = 是群文件清理管理员(event, 配置)
    if 帮助状态 is not None and (re.fullmatch(r"\d{1,2}", 文本) or 文本 in 返回上一步别名):
        if not 是管理员:
            待选择帮助会话.pop(会话键, None)
            return "没有权限使用帮助"
        编号文本 = "0" if 文本 in 返回上一步别名 else 文本
        return 处理帮助数字选择(会话键, 帮助状态, 编号文本)
    if 帮助状态 is None and 文本 in 返回上一步别名:
        if not 是管理员:
            return "没有权限使用帮助"
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类()
    目标 = 匹配任意层级名称(文本)
    if 目标 is not None:
        if not 是管理员:
            if 帮助状态 is not None:
                待选择帮助会话.pop(会话键, None)
                return "没有权限使用帮助"
            return None
        return 跳转到目标(会话键, 目标)

    return None


def 设置帮助状态(会话键: str, 层级: str, 大类序号: int | None = None, 小类序号: int | None = None, 触发项序号: int | None = None) -> None:
    待选择帮助会话[会话键] = {
        "时间": time.time(),
        "层级": 层级,
        "大类序号": 大类序号,
        "小类序号": 小类序号,
        "触发项序号": 触发项序号,
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


# ===== 纯文本版 =====


def 格式化帮助大类() -> str:
    行列表 = ["请选择帮助大类："]
    for 序号, 大类 in enumerate(帮助大类, start=1):
        行列表.append(f"{序号}. {大类['名称']}")
    return "\n".join(行列表)


def 进入大类小类列表(会话键: str, 编号文本: str) -> str:
    编号 = int(编号文本)
    if 编号 < 1 or 编号 > len(帮助大类):
        return f"帮助编号无效，请发送 1-{len(帮助大类)}"
    设置帮助状态(会话键, "小类", 编号 - 1)
    return 格式化小类列表(编号 - 1)


def 格式化小类列表(大类序号: int) -> str:
    大类 = 帮助大类[大类序号]
    行列表 = [f"{大类['名称']}："]
    for 序号, 小类 in enumerate(大类["小类"], start=1):
        行列表.append(f"{序号}. {小类['名称']}")
    行列表.append("0. 返回上一步")
    return "\n".join(行列表)


def 格式化小类触发项列表(大类序号: int, 小类序号: int) -> str:
    大类 = 帮助大类[大类序号]
    小类 = 大类["小类"][小类序号]
    行列表 = [f"{大类['名称']} - {小类['名称']}："]
    for 序号, 触发项 in enumerate(小类["触发项"], start=1):
        行列表.append(f"{序号}. {触发项['触发']}")
    行列表.append("0. 返回上一步")
    return "\n".join(行列表)


def 格式化帮助详情(大类序号: int, 小类序号: int, 触发编号文本: str) -> str:
    小类 = 帮助大类[大类序号]["小类"][小类序号]
    if not 触发编号文本.isdigit():
        return f"帮助编号无效，请发送 1-{len(小类['触发项'])} 或 0 返回上一步"
    触发编号 = int(触发编号文本)
    if 触发编号 < 1 or 触发编号 > len(小类["触发项"]):
        return f"帮助编号无效，请发送 1-{len(小类['触发项'])} 或 0 返回上一步"

    触发项 = 小类["触发项"][触发编号 - 1]
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
        return 进入大类小类列表(会话键, 编号文本)

    if 层级 == "小类" and isinstance(大类序号, int):
        编号 = int(编号文本)
        小类列表 = 帮助大类[大类序号]["小类"]
        if 编号 < 1 or 编号 > len(小类列表):
            return f"帮助编号无效，请发送 1-{len(小类列表)} 或 0 返回上一步"
        设置帮助状态(会话键, "触发项", 大类序号, 编号 - 1)
        return 格式化小类触发项列表(大类序号, 编号 - 1)

    if 层级 in {"触发项", "详情"} and isinstance(大类序号, int) and isinstance(小类序号, int):
        触发项序号 = int(编号文本) - 1 if 编号文本.isdigit() else None
        设置帮助状态(会话键, "详情", 大类序号, 小类序号, 触发项序号)
        return 格式化帮助详情(大类序号, 小类序号, 编号文本)

    设置帮助状态(会话键, "大类")
    return 格式化帮助大类()


def 返回帮助上一层(会话键: str, 层级: str, 大类序号: Any, 小类序号: Any) -> str:
    if 层级 == "详情" and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
        return 格式化小类触发项列表(大类序号, 小类序号)
    if 层级 == "触发项" and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "小类", 大类序号)
        return 格式化小类列表(大类序号)
    if 层级 == "小类" and isinstance(大类序号, int):
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类()
    待选择帮助会话.pop(会话键, None)
    return "已退出帮助菜单"


# ===== Markdown 版 =====


def 格式化帮助大类MD() -> str:
    行列表 = ["## 请选择帮助大类\n"]
    for 序号, 大类 in enumerate(帮助大类, start=1):
        行列表.append(f"**{序号}.** {大类['名称']}")
    return "\n".join(行列表)


def 进入大类小类列表MD(会话键: str, 编号文本: str) -> str:
    编号 = int(编号文本)
    if 编号 < 1 or 编号 > len(帮助大类):
        return f"帮助编号无效，请发送 1-{len(帮助大类)}"
    设置帮助状态(会话键, "小类", 编号 - 1)
    return 格式化小类列表MD(编号 - 1)


def 格式化小类列表MD(大类序号: int) -> str:
    大类 = 帮助大类[大类序号]
    行列表 = [f"## {大类['名称']}\n"]
    for 序号, 小类 in enumerate(大类["小类"], start=1):
        行列表.append(f"**{序号}.** {小类['名称']}")
    行列表.append("\n**0.** 返回上一步")
    return "\n".join(行列表)


def 格式化小类触发项列表MD(大类序号: int, 小类序号: int) -> str:
    大类 = 帮助大类[大类序号]
    小类 = 大类["小类"][小类序号]
    行列表 = [f"## {大类['名称']} - {小类['名称']}\n"]
    for 序号, 触发项 in enumerate(小类["触发项"], start=1):
        行列表.append(f"**{序号}.** `{触发项['触发']}`")
    行列表.append("\n**0.** 返回上一步")
    return "\n".join(行列表)


def 格式化帮助详情MD(大类序号: int, 小类序号: int, 触发编号文本: str) -> str:
    小类 = 帮助大类[大类序号]["小类"][小类序号]
    if not 触发编号文本.isdigit():
        return f"帮助编号无效，请发送 1-{len(小类['触发项'])} 或 0 返回上一步"
    触发编号 = int(触发编号文本)
    if 触发编号 < 1 or 触发编号 > len(小类["触发项"]):
        return f"帮助编号无效，请发送 1-{len(小类['触发项'])} 或 0 返回上一步"

    触发项 = 小类["触发项"][触发编号 - 1]
    return "\n".join([
        f"## {触发项['名称']}\n",
        f"**触发：** `{触发项['触发']}`\n",
        触发项["详情"],
        "\n**0.** 返回上一步",
    ])


def 处理帮助数字选择MD(会话键: str, 帮助状态: dict[str, Any], 编号文本: str) -> str:
    层级 = 帮助状态.get("层级")
    大类序号 = 帮助状态.get("大类序号")
    小类序号 = 帮助状态.get("小类序号")

    if 编号文本 == "0":
        return 返回帮助上一层MD(会话键, 层级, 大类序号, 小类序号)

    if 层级 == "大类":
        return 进入大类小类列表MD(会话键, 编号文本)

    if 层级 == "小类" and isinstance(大类序号, int):
        编号 = int(编号文本)
        小类列表 = 帮助大类[大类序号]["小类"]
        if 编号 < 1 or 编号 > len(小类列表):
            return f"帮助编号无效，请发送 1-{len(小类列表)} 或 0 返回上一步"
        设置帮助状态(会话键, "触发项", 大类序号, 编号 - 1)
        return 格式化小类触发项列表MD(大类序号, 编号 - 1)

    if 层级 in {"触发项", "详情"} and isinstance(大类序号, int) and isinstance(小类序号, int):
        触发项序号 = int(编号文本) - 1 if 编号文本.isdigit() else None
        设置帮助状态(会话键, "详情", 大类序号, 小类序号, 触发项序号)
        return 格式化帮助详情MD(大类序号, 小类序号, 编号文本)

    设置帮助状态(会话键, "大类")
    return 格式化帮助大类MD()


def 返回帮助上一层MD(会话键: str, 层级: str, 大类序号: Any, 小类序号: Any) -> str:
    if 层级 == "详情" and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
        return 格式化小类触发项列表MD(大类序号, 小类序号)
    if 层级 == "触发项" and isinstance(大类序号, int) and isinstance(小类序号, int):
        设置帮助状态(会话键, "小类", 大类序号)
        return 格式化小类列表MD(大类序号)
    if 层级 == "小类" and isinstance(大类序号, int):
        设置帮助状态(会话键, "大类")
        return 格式化帮助大类MD()
    待选择帮助会话.pop(会话键, None)
    return "已退出帮助菜单"


# ===== 键盘按钮生成 =====


def 生成按钮(编号: str, 标签: str, 点击后标签: str = "", 自动发送: bool = False, data为标签: bool = True) -> dict[str, Any]:
    """生成 QQ 官方指令按钮。

    自动发送参数仅保留兼容旧调用；当前群聊和私聊统一使用同一套按钮格式，
    指令按钮固定 enter=True，点击后直接发送。
    """
    data值 = 标签 if data为标签 else 编号
    动作: dict[str, Any] = {
        "type": 2,
        "permission": {"type": 2},
        "data": data值,
        "enter": True,
        "unsupport_tips": "请发送对应文字",
    }
    return {
        "id": data值,
        "render_data": {"label": 标签, "visited_label": 点击后标签 or 标签},
        "action": 动作,
    }


def 生成链接按钮(标签: str, 跳转链接: str, 点击后标签: str = "") -> dict[str, Any]:
    return {
        "id": f"link_{跳转链接}",
        "render_data": {"label": 标签, "visited_label": 点击后标签 or 标签},
        "action": {
            "type": 0,
            "permission": {"type": 2},
            "data": 跳转链接,
            "unsupport_tips": "请手动复制链接到浏览器打开",
        },
    }


def 生成返回按钮(自动发送: bool = False) -> dict[str, Any]:
    return 生成按钮("返回上一步", "返回上一步", "已返回", 自动发送, data为标签=False)


def 按钮分行(按钮列表: list[dict[str, Any]], 每行最多: int = 每行按钮数) -> list[dict[str, Any]]:
    return [{"buttons": 按钮列表[开始:开始 + 每行最多]} for 开始 in range(0, len(按钮列表), 每行最多)]


def 按钮分行带返回(按钮列表: list[dict[str, Any]], 返回按钮: dict[str, Any], 每行最多: int = 每行按钮数) -> list[dict[str, Any]]:
    行 = 按钮分行(按钮列表, 每行最多)
    行.append({"buttons": [返回按钮]})
    return 行


def 生成帮助大类键盘(自动发送: bool = False) -> dict[str, Any]:
    按钮列表 = [生成按钮(大类["名称"], 大类["名称"], 自动发送=自动发送) for 大类 in 帮助大类]
    return {"rows": 按钮分行带返回(按钮列表, 生成返回按钮(自动发送))}


def 生成小类键盘(大类序号: int, 自动发送: bool = False) -> dict[str, Any]:
    大类 = 帮助大类[大类序号]
    按钮列表 = [生成按钮(小类["名称"], 小类["名称"], 自动发送=自动发送) for 小类 in 大类["小类"]]
    return {"rows": 按钮分行带返回(按钮列表, 生成返回按钮(自动发送))}


def 生成小类触发项键盘(大类序号: int, 小类序号: int, 自动发送: bool = False) -> dict[str, Any]:
    小类 = 帮助大类[大类序号]["小类"][小类序号]
    用按钮字 = bool(小类.get("按钮字触发"))
    按钮列表 = []
    for 序号, 触发项 in enumerate(小类["触发项"], start=1):
        if 用按钮字:
            data值 = 触发项.get("按钮data") or 触发项["名称"]
            按钮列表.append(生成按钮(data值, 触发项["名称"], 自动发送=自动发送, data为标签=False))
        elif 触发项.get("快捷命令"):
            按钮列表.append(生成按钮(触发项["名称"], 触发项["名称"], 自动发送=自动发送))
        else:
            按钮列表.append(生成按钮(触发项["名称"], 触发项["名称"], 自动发送=自动发送))
    return {"rows": 按钮分行带返回(按钮列表, 生成返回按钮(自动发送))}


def 生成帮助详情键盘(触发项: dict[str, Any] | None = None, 自动发送: bool = False, 配置: Any = None, 群号: str = "") -> dict[str, Any]:
    快捷命令 = 触发项.get("快捷命令") if isinstance(触发项, dict) else None
    if not 快捷命令:
        return {"rows": [{"buttons": [生成返回按钮(自动发送)]}]}
    行: list[dict[str, Any]] = []
    静态按钮列表 = []
    for 命令 in 快捷命令:
        if isinstance(命令, dict):
            data值 = str(命令.get("data") or "")
            标签 = str(命令.get("label") or data值)
            静态按钮列表.append(生成按钮(data值, 标签, 自动发送=自动发送, data为标签=False))
        else:
            静态按钮列表.append(生成按钮(命令, 命令, 自动发送=自动发送))
    行.extend(按钮分行(静态按钮列表, 每行最多=每行按钮数))
    行.append({"buttons": [生成返回按钮(自动发送)]})
    return {"rows": 行}


def 获取帮助键盘(会话键: str, 自动发送: bool = False, 配置: Any = None, 群号: str = "") -> dict[str, Any] | None:
    帮助状态 = 获取有效帮助状态(会话键)
    if 帮助状态 is None:
        return None
    层级 = 帮助状态.get("层级")
    大类序号 = 帮助状态.get("大类序号")
    小类序号 = 帮助状态.get("小类序号")
    if 层级 == "大类":
        return 生成帮助大类键盘(自动发送)
    if 层级 == "小类" and isinstance(大类序号, int):
        键盘 = 生成小类键盘(大类序号, 自动发送)
        return 检查键盘行数(键盘, 大类序号, None)
    if 层级 == "触发项" and isinstance(大类序号, int) and isinstance(小类序号, int):
        键盘 = 生成小类触发项键盘(大类序号, 小类序号, 自动发送)
        return 检查键盘行数(键盘, 大类序号, 小类序号)
    if 层级 == "详情":
        触发项序号 = 帮助状态.get("触发项序号")
        触发项 = None
        if isinstance(大类序号, int) and isinstance(小类序号, int) and isinstance(触发项序号, int):
            小类 = 帮助大类[大类序号]["小类"][小类序号]
            if 0 <= 触发项序号 < len(小类["触发项"]):
                触发项 = 小类["触发项"][触发项序号]
        键盘 = 生成帮助详情键盘(触发项, 自动发送, 配置, 群号)
        return 检查键盘行数(键盘, 大类序号, 小类序号)
    return None


def 检查键盘行数(键盘: dict[str, Any], 大类序号: int, 小类序号: int | None) -> dict[str, Any] | None:
    """QQ 官方限制：单条消息 keyboard 最多 5 行按钮，超限降级为不发按钮（只发 markdown 文本）"""
    行数 = len(键盘.get("rows", []))
    if 行数 > 5:
        位置 = f"大类{大类序号 + 1}" if 小类序号 is None else f"大类{大类序号 + 1}小类{小类序号 + 1}"
        logger.info(f"[帮助键盘] {位置} 按钮行数={行数} 超过 QQ 官方 5 行限制，降级为无按钮 markdown")
        return None
    return 键盘


# ===== 跨层匹配与跳转 =====


def 匹配任意层级名称(文本: str) -> tuple[str, int, int | None, int | None] | None:
    """跨层级匹配名称，返回 (目标层级, 大类序号, 小类序号或None, 触发项序号或None) 或 None"""
    for 序号, 大类 in enumerate(帮助大类):
        if 大类["名称"] == 文本:
            return ("小类", 序号, None, None)
    for 大类序号, 大类 in enumerate(帮助大类):
        for 小类序号, 小类 in enumerate(大类["小类"]):
            if 小类["名称"] == 文本:
                return ("触发项", 大类序号, 小类序号, None)
    for 大类序号, 大类 in enumerate(帮助大类):
        for 小类序号, 小类 in enumerate(大类["小类"]):
            for 触发项序号, 触发项 in enumerate(小类["触发项"]):
                if 触发项["名称"] == 文本 or 触发项.get("按钮data") == 文本:
                    return ("详情", 大类序号, 小类序号, 触发项序号)
    return None


def 跳转到目标(会话键: str, 目标: tuple[str, int, int | None, int | None]) -> str:
    层级, 大类序号, 小类序号, 触发项序号 = 目标
    if 层级 == "小类":
        设置帮助状态(会话键, "小类", 大类序号)
        return 格式化小类列表(大类序号)
    if 层级 == "触发项" and isinstance(小类序号, int):
        设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
        return 格式化小类触发项列表(大类序号, 小类序号)
    if 层级 == "详情" and isinstance(小类序号, int) and isinstance(触发项序号, int):
        设置帮助状态(会话键, "详情", 大类序号, 小类序号, 触发项序号)
        return 格式化帮助详情(大类序号, 小类序号, str(触发项序号 + 1))
    设置帮助状态(会话键, "大类")
    return 格式化帮助大类()


def 跳转到目标MD(会话键: str, 目标: tuple[str, int, int | None, int | None]) -> str:
    层级, 大类序号, 小类序号, 触发项序号 = 目标
    if 层级 == "小类":
        设置帮助状态(会话键, "小类", 大类序号)
        return 格式化小类列表MD(大类序号)
    if 层级 == "触发项" and isinstance(小类序号, int):
        设置帮助状态(会话键, "触发项", 大类序号, 小类序号)
        return 格式化小类触发项列表MD(大类序号, 小类序号)
    if 层级 == "详情" and isinstance(小类序号, int) and isinstance(触发项序号, int):
        设置帮助状态(会话键, "详情", 大类序号, 小类序号, 触发项序号)
        return 格式化帮助详情MD(大类序号, 小类序号, str(触发项序号 + 1))
    设置帮助状态(会话键, "大类")
    return 格式化帮助大类MD()


# ===== MD + 键盘主入口 =====


def 处理帮助指令MD带键盘(event: Any, 命令文本: str, 配置: Any) -> tuple[str | None, dict[str, Any] | None]:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None, None

    会话键 = 获取帮助会话键(event)
    # 群聊和私聊的键盘按钮使用同一套格式，统一按私聊按钮行为直接发送。
    按钮自动发送 = True
    键盘群号 = ""
    帮助匹配 = re.fullmatch(r"帮助\s*(\d{1,2})?", 文本, re.IGNORECASE)
    if 帮助匹配:
        if not 是群文件清理管理员(event, 配置):
            return "没有权限使用帮助", None
        编号 = 帮助匹配.group(1)
        if 编号:
            md文本 = 进入大类小类列表MD(会话键, 编号)
        else:
            设置帮助状态(会话键, "大类")
            md文本 = 格式化帮助大类MD()
        键盘 = 获取帮助键盘(会话键, 按钮自动发送, 配置, 键盘群号)
        return md文本, 键盘

    帮助状态 = 获取有效帮助状态(会话键)
    是管理员 = 是群文件清理管理员(event, 配置)
    if 帮助状态 is not None and (re.fullmatch(r"\d{1,2}", 文本) or 文本 in 返回上一步别名):
        if not 是管理员:
            待选择帮助会话.pop(会话键, None)
            return "没有权限使用帮助", None
        编号文本 = "0" if 文本 in 返回上一步别名 else 文本
        md文本 = 处理帮助数字选择MD(会话键, 帮助状态, 编号文本)
        键盘 = 获取帮助键盘(会话键, 按钮自动发送, 配置, 键盘群号)
        return md文本, 键盘
    if 帮助状态 is None and 文本 in 返回上一步别名:
        if not 是管理员:
            return "没有权限使用帮助", None
        设置帮助状态(会话键, "大类")
        md文本 = 格式化帮助大类MD()
        键盘 = 获取帮助键盘(会话键, 按钮自动发送, 配置, 键盘群号)
        return md文本, 键盘
    目标 = 匹配任意层级名称(文本)
    if 目标 is not None:
        if not 是管理员:
            if 帮助状态 is not None:
                待选择帮助会话.pop(会话键, None)
                return "没有权限使用帮助", None
            return None, None
        md文本 = 跳转到目标MD(会话键, 目标)
        键盘 = 获取帮助键盘(会话键, 按钮自动发送, 配置, 键盘群号)
        return md文本, 键盘

    return None, None


# ===== 会话与群号工具 =====


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
    if 键盘 is not None:
        消息体["keyboard"] = {"content": 键盘}

    群openid = 获取群openid同步(event)
    用户openid = 获取用户openid同步(event)
    if 群openid:
        route = Route("POST", "/v2/groups/{group_openid}/messages", group_openid=群openid)
        if 消息ID:
            消息体["msg_id"] = 消息ID
        logger.info(f"[帮助MD键盘] 群聊发送，group_openid={群openid}，消息ID={消息ID}，按钮行数={len(键盘.get('rows', [])) if 键盘 else 0}")
    elif 用户openid:
        route = Route("POST", "/v2/users/{openid}/messages", openid=用户openid)
        if 消息ID:
            消息体["msg_id"] = 消息ID
        logger.info(f"[帮助MD键盘] 私聊发送，user_openid={用户openid}，消息ID={消息ID}，按钮行数={len(键盘.get('rows', [])) if 键盘 else 0}")
    else:
        logger.warning("[帮助MD键盘] 无法获取 group_openid 和 user_openid")
        return False

    try:
        响应 = await _http.request(route, json=消息体)
        logger.info(f"[帮助MD键盘] 发送成功，响应={响应}")
        return True
    except Exception as e:
        logger.warning(f"[帮助MD键盘] 发送失败: {type(e).__name__}: {e}")
        return False
