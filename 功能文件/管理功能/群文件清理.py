from __future__ import annotations
import json
import re
from typing import Any

import aiohttp
from astrbot.api import logger


清理群文件命令正则 = re.compile(r"^(清理群文件|群文件清理)(?:\s+([1-9]\d{4,11}))?$")
NapCat地址配置名 = "napcat_onebot_http_url"
NapCat令牌配置名 = "napcat_onebot_access_token"
NapCat调试地址配置名 = "napcat_webui_url"
NapCat调试令牌配置名 = "napcat_webui_token"
群号映射配置名 = "group_file_cleanup_group_map"


async def 处理群文件清理(event: Any, 命令文本: str, 配置: Any) -> str | None:
    手动群号 = 解析清理群文件命令(命令文本)
    if 手动群号 is None:
        return None

    发送者 = 获取发送者QQ(event)
    管理员列表 = 获取管理员QQ列表(配置)
    if not 发送者 or 发送者 not in 管理员列表:
        return "没有权限使用群文件清理"

    事件群号 = 获取群号(event)
    if not 事件群号:
        return "群文件清理只能在群聊中使用"
    群号 = 手动群号 or 获取映射群号(事件群号, 配置) or 事件群号
    if not 是数字群号(群号):
        return "群文件清理失败：当前适配器没有返回数字QQ群号，请发送“清理群文件 数字群号”或配置 group_file_cleanup_group_map"

    bot = getattr(event, "bot", None)
    if bot is None:
        return "群文件清理失败：当前事件缺少 bot 实例"

    try:
        删除成功 = 0
        删除失败 = 0
        已失败文件: set[str] = set()

        async with 群文件动作调用器(bot, 配置) as 调用器:
            while True:
                文件列表 = await 获取全部群文件(调用器, 群号)
                待删文件 = [文件 for 文件 in 文件列表 if 获取文件去重键(文件) not in 已失败文件]
                if not 待删文件:
                    break

                本轮成功 = 0
                for 文件 in 待删文件:
                    try:
                        await 删除群文件(调用器, 群号, 文件["file_id"], 文件.get("busid"))
                        删除成功 += 1
                        本轮成功 += 1
                    except Exception as exc:
                        删除失败 += 1
                        已失败文件.add(获取文件去重键(文件))
                        logger.warning(f"群文件删除失败：group_id={群号}, file={文件}, error={exc}")

                if 本轮成功 == 0:
                    break

        return f"群文件清理完成：成功 {删除成功} 个，失败 {删除失败} 个"
    except Exception as exc:
        logger.warning(f"群文件清理失败：group_id={群号}, error={exc}")
        return f"群文件清理失败：{exc}"


async def 获取全部群文件(调用器: "群文件动作调用器", 群号: Any) -> list[dict[str, Any]]:
    根目录 = await 调用器.调用("get_group_root_files", group_id=群号)
    文件列表 = 提取文件列表(根目录)
    待处理文件夹 = 提取文件夹列表(根目录)
    已处理文件夹: set[str] = set()

    while 待处理文件夹:
        文件夹 = 待处理文件夹.pop(0)
        文件夹编号 = 文件夹.get("folder_id") or 文件夹.get("id")
        if not 文件夹编号 or str(文件夹编号) in 已处理文件夹:
            continue
        已处理文件夹.add(str(文件夹编号))
        文件夹内容 = await 调用器.调用("get_group_files_by_folder", group_id=群号, folder_id=文件夹编号)
        文件列表.extend(提取文件列表(文件夹内容))
        待处理文件夹.extend(提取文件夹列表(文件夹内容))
    return 去重文件列表(文件列表)


async def 删除群文件(调用器: "群文件动作调用器", 群号: Any, 文件编号: Any, busid: Any = None) -> None:
    参数 = {"group_id": 群号, "file_id": 文件编号}
    if busid is not None:
        参数["busid"] = busid
    await 调用器.调用("delete_group_file", **参数)


class 群文件动作调用器:
    def __init__(self, bot: Any, 配置: Any):
        self.bot = bot
        self.NapCat地址 = 获取配置字符串(配置, NapCat地址配置名)
        self.NapCat令牌 = 获取配置字符串(配置, NapCat令牌配置名)
        self.NapCat调试地址 = 获取配置字符串(配置, NapCat调试地址配置名)
        self.NapCat调试令牌 = 获取配置字符串(配置, NapCat调试令牌配置名)
        self.NapCat调试适配器 = ""
        self.会话: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "群文件动作调用器":
        if not self.有AstrBot动作接口() and (self.NapCat地址 or self.NapCat调试地址):
            self.会话 = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.会话 is not None:
            await self.会话.close()

    def 有AstrBot动作接口(self) -> bool:
        api = getattr(self.bot, "api", None)
        return callable(getattr(api, "call_action", None))

    async def 调用(self, 动作: str, **参数: Any) -> Any:
        api = getattr(self.bot, "api", None)
        调用方法 = getattr(api, "call_action", None)
        if callable(调用方法):
            return await 调用方法(动作, **参数)
        if self.NapCat地址:
            return await self.调用NapCatHTTP(动作, **参数)
        if not self.NapCat调试地址:
            raise RuntimeError("当前适配器没有群文件接口；如需借用 NapCat 清理，请配置 napcat_onebot_http_url 或 napcat_webui_url")
        return await self.调用NapCat调试HTTP(动作, **参数)

    async def 调用NapCatHTTP(self, 动作: str, **参数: Any) -> Any:
        if not self.NapCat地址:
            raise RuntimeError("当前适配器没有群文件接口；如需借用 NapCat 清理，请配置 napcat_onebot_http_url 或 napcat_webui_url")
        if not self.NapCat地址.startswith(("http://", "https://")):
            raise RuntimeError("napcat_onebot_http_url 必须以 http:// 或 https:// 开头")

        if self.会话 is None:
            self.会话 = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))

        地址 = self.NapCat地址.rstrip("/") + "/" + 动作
        请求头 = {"Content-Type": "application/json"}
        if self.NapCat令牌:
            请求头["Authorization"] = f"Bearer {self.NapCat令牌}"

        async with self.会话.post(地址, json=参数, headers=请求头) as 响应:
            响应文本 = await 响应.text()
            if 响应.status >= 400:
                raise RuntimeError(f"NapCat HTTP {动作} 请求失败：HTTP {响应.status} {限制文本长度(响应文本, 300)}")
            try:
                响应数据 = json.loads(响应文本) if 响应文本 else {}
            except Exception:
                raise RuntimeError(f"NapCat HTTP {动作} 返回不是 JSON：{限制文本长度(响应文本, 300)}")

        if isinstance(响应数据, dict):
            retcode = 响应数据.get("retcode")
            状态 = 响应数据.get("status")
            if retcode not in (None, 0) or 状态 in {"failed", "error"}:
                错误 = 响应数据.get("wording") or 响应数据.get("message") or 响应数据.get("msg") or 响应数据
                raise RuntimeError(f"NapCat HTTP {动作} 调用失败：{限制文本长度(错误, 300)}")
        logger.info(f"群文件清理调用 NapCat HTTP：action={动作}, params={参数}")
        return 响应数据

    async def 调用NapCat调试HTTP(self, 动作: str, **参数: Any) -> Any:
        await self.确保NapCat调试适配器()
        地址 = self.NapCat调试地址.rstrip("/") + "/api/Debug/call/" + self.NapCat调试适配器
        响应数据 = await self.请求NapCat调试接口(地址, {"action": 动作, "params": 参数})
        内层响应 = 响应数据.get("data") if isinstance(响应数据, dict) else 响应数据
        if isinstance(内层响应, dict):
            retcode = 内层响应.get("retcode")
            状态 = 内层响应.get("status")
            if retcode not in (None, 0) or 状态 in {"failed", "error"}:
                错误 = 内层响应.get("wording") or 内层响应.get("message") or 内层响应.get("msg") or 内层响应
                raise RuntimeError(f"NapCat 实时调试 {动作} 调用失败：{限制文本长度(错误, 300)}")
        logger.info(f"群文件清理调用 NapCat 实时调试：action={动作}, params={参数}")
        return 内层响应

    async def 确保NapCat调试适配器(self) -> None:
        if self.NapCat调试适配器:
            return
        if not self.NapCat调试地址:
            raise RuntimeError("当前适配器没有群文件接口；如需借用 NapCat 实时调试清理，请配置 napcat_webui_url")
        if not self.NapCat调试地址.startswith(("http://", "https://")):
            raise RuntimeError("napcat_webui_url 必须以 http:// 或 https:// 开头")
        地址 = self.NapCat调试地址.rstrip("/") + "/api/Debug/create"
        响应数据 = await self.请求NapCat调试接口(地址, {})
        数据 = 响应数据.get("data") if isinstance(响应数据, dict) else None
        if not isinstance(数据, dict) or not 数据.get("adapterName"):
            raise RuntimeError(f"NapCat 实时调试适配器创建失败：{限制文本长度(响应数据, 300)}")
        self.NapCat调试适配器 = str(数据["adapterName"])

    async def 请求NapCat调试接口(self, 地址: str, 数据: dict[str, Any]) -> Any:
        if self.会话 is None:
            self.会话 = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        请求头 = {"Content-Type": "application/json"}
        if self.NapCat调试令牌:
            请求头["Authorization"] = f"Bearer {self.NapCat调试令牌}"
        async with self.会话.post(地址, json=数据, headers=请求头) as 响应:
            响应文本 = await 响应.text()
            if 响应.status >= 400:
                raise RuntimeError(f"NapCat 实时调试请求失败：HTTP {响应.status} {限制文本长度(响应文本, 300)}")
            try:
                响应数据 = json.loads(响应文本) if 响应文本 else {}
            except Exception:
                raise RuntimeError(f"NapCat 实时调试返回不是 JSON：{限制文本长度(响应文本, 300)}")
        if isinstance(响应数据, dict) and 响应数据.get("code") not in (None, 0):
            错误 = 响应数据.get("message") or 响应数据.get("msg") or 响应数据
            raise RuntimeError(f"NapCat 实时调试调用失败：{限制文本长度(错误, 300)}")
        return 响应数据


def 提取文件列表(响应: Any) -> list[dict[str, Any]]:
    数据 = 响应.get("data") if isinstance(响应, dict) and isinstance(响应.get("data"), dict) else 响应
    if not isinstance(数据, dict):
        return []
    文件列表 = 数据.get("files") or []
    return [文件 for 文件 in 文件列表 if isinstance(文件, dict)]


def 提取文件夹列表(响应: Any) -> list[dict[str, Any]]:
    数据 = 响应.get("data") if isinstance(响应, dict) and isinstance(响应.get("data"), dict) else 响应
    if not isinstance(数据, dict):
        return []
    文件夹列表 = 数据.get("folders") or []
    return [文件夹 for 文件夹 in 文件夹列表 if isinstance(文件夹, dict)]


def 去重文件列表(文件列表: list[dict[str, Any]]) -> list[dict[str, Any]]:
    结果 = []
    已见文件: set[str] = set()
    for 文件 in 文件列表:
        去重键 = 获取文件去重键(文件)
        if not 去重键:
            continue
        if 去重键 in 已见文件:
            continue
        已见文件.add(去重键)
        结果.append(文件)
    return 结果


def 获取文件去重键(文件: dict[str, Any]) -> str:
    文件编号 = 文件.get("file_id")
    if not 文件编号:
        return ""
    return f"{文件编号}:{文件.get('busid', '')}"


def 解析清理群文件命令(命令文本: str) -> str | None:
    匹配 = 清理群文件命令正则.fullmatch(str(命令文本 or "").strip())
    if not 匹配:
        return None
    return 匹配.group(2) or ""


def 获取映射群号(事件群号: str, 配置: Any) -> str:
    if not 事件群号:
        return ""
    映射列表 = 读取字段(配置, 群号映射配置名) or []
    if isinstance(映射列表, str):
        映射列表 = [映射列表]
    if not isinstance(映射列表, list):
        return ""
    for 项目 in 映射列表:
        文本 = str(项目 or "").strip()
        if "=" not in 文本:
            continue
        左侧, 右侧 = [部分.strip() for 部分 in 文本.split("=", 1)]
        if 左侧 == str(事件群号) and 是数字群号(右侧):
            return 右侧
    return ""


def 是数字群号(值: Any) -> bool:
    文本 = str(值 or "").strip()
    return bool(re.fullmatch(r"[1-9]\d{4,11}", 文本))


def 获取配置字符串(配置: Any, 字段名: str) -> str:
    值 = 读取字段(配置, 字段名)
    return str(值 or "").strip()


def 限制文本长度(值: Any, 最大长度: int = 300) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."


def 获取管理员QQ列表(配置: Any) -> set[str]:
    if not 配置:
        return set()
    值 = 读取字段(配置, "group_file_cleanup_admin_qq") or []
    if isinstance(值, str):
        值 = [值]
    if not isinstance(值, list):
        return set()
    return {str(项目).strip() for 项目 in 值 if str(项目).strip()}


def 获取发送者QQ(event: Any) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("sender_id", "user_id", "sender"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("user_id") or 值.get("id")
            if 值:
                return str(值)
    return ""


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)

    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        for 字段名 in ("group_id", "group"):
            值 = 读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("group_id") or 值.get("id")
            if 值:
                return str(值)
    return ""


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
