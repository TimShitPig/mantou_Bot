from __future__ import annotations

import contextvars
import copy
import functools
import inspect
import re
import threading
from contextlib import contextmanager
from typing import Any


当前机器人作用域 = globals().get("当前机器人作用域") or contextvars.ContextVar(
    "mantou_bot_appid", default=""
)
_机器人配置缓存 = globals().get("_机器人配置缓存") or {}
_机器人配置锁 = globals().get("_机器人配置锁") or threading.RLock()
_机器人配置写入代次 = globals().get("_机器人配置写入代次") or {}
机器人独立配置分类 = (
    "basic_settings", "uc_pan_settings", "quark_pan_settings",
    "baidu_pan_settings", "zlibrary_account_settings",
)
机器人独立帮助字段 = {"welcome_tutorial_image_width"}
机器人业务字段分类 = {
    "group_file_cleanup_admin_qq": "basic_settings",
    "uc_pan_cookie": "uc_pan_settings", "uc_pan_upload_dir": "uc_pan_settings",
    "quark_pan_cookie": "quark_pan_settings", "quark_pan_upload_dir": "quark_pan_settings",
    "baidu_pan_cookie": "baidu_pan_settings", "baidu_pan_upload_dir": "baidu_pan_settings",
    "zlibrary_mail_api_key": "zlibrary_account_settings", "zlibrary_registration_rx": "zlibrary_account_settings",
    "welcome_tutorial_image_width": "help_web_settings",
}


def _字段(对象: Any, 名称: str) -> Any:
    return 对象.get(名称) if isinstance(对象, dict) else getattr(对象, 名称, None)


def 规范化机器人AppID(值: Any) -> str:
    文本 = str(值 or "").strip()
    return 文本 if re.fullmatch(r"[0-9]{4,32}", 文本) else ""


def 获取事件机器人AppID(event: Any) -> str:
    """消息身份只来自实际认证客户端；平台显示名不参与。"""
    对象列表 = (event, _字段(event, "bot"), _字段(event, "client"), _字段(event, "platform"))
    for 对象 in 对象列表:
        token = _字段(_字段(_字段(对象, "api"), "_http"), "_token")
        appid = 规范化机器人AppID(_字段(token, "app_id"))
        if appid:
            return appid
    for 对象 in 对象列表:
        for 来源 in (对象, _字段(对象, "config")):
            for 名称 in ("appid", "app_id"):
                appid = 规范化机器人AppID(_字段(来源, 名称))
                if appid:
                    return appid
    return ""


def 获取当前机器人AppID(配置: Any = None) -> str:
    明确 = 规范化机器人AppID(
        配置.get("__mantou_bot_appid__") if isinstance(配置, dict)
        else getattr(配置, "机器人AppID", "")
    )
    return 明确 or 规范化机器人AppID(当前机器人作用域.get())


@contextmanager
def 绑定机器人作用域(appid: str):
    token = 当前机器人作用域.set(规范化机器人AppID(appid))
    try:
        yield
    finally:
        当前机器人作用域.reset(token)


def _原配置字典(配置: Any) -> dict[str, Any] | None:
    if isinstance(配置, dict):
        return 配置
    方法 = getattr(配置, "get_config", None)
    if callable(方法):
        数据 = 方法()
        if isinstance(数据, dict):
            return 数据
    for 名称 in ("config", "_config", "data"):
        数据 = getattr(配置, 名称, None)
        if isinstance(数据, dict):
            return 数据
    return None


def _业务快照(数据: dict[str, Any]) -> dict[str, Any]:
    快照 = {名称: copy.deepcopy(数据.get(名称) or {}) for 名称 in 机器人独立配置分类}
    帮助 = 数据.get("help_web_settings") or {}
    快照["help_web_settings"] = {
        字段: copy.deepcopy(帮助[字段]) for 字段 in 机器人独立帮助字段 if 字段 in 帮助
    }
    for 字段, 分类 in 机器人业务字段分类.items():
        if 字段 in 数据 and 字段 not in 快照[分类]:
            快照[分类][字段] = copy.deepcopy(数据[字段])
    return 快照


class 机器人配置(dict):
    """共享连接/网页基础设施，独立保存当前机器人的业务设置。"""

    def __init__(self, 基础配置: Any, appid: str, 业务: dict[str, Any]):
        数据 = _原配置字典(基础配置) or {}
        super().__init__({键: copy.deepcopy(值) for 键, 值 in 数据.items() if 键 != "bot_profiles"})
        self.基础配置 = 基础配置
        self.机器人AppID = appid
        self._共享待更新: dict[tuple[str, str], Any] = {}
        self["__mantou_bot_appid__"] = appid
        for 字段 in 机器人业务字段分类:
            self.pop(字段, None)
        for 名称 in 机器人独立配置分类:
            self[名称] = copy.deepcopy(业务.get(名称) or {})
        帮助 = dict(数据.get("help_web_settings") or {})
        帮助.update(copy.deepcopy(业务.get("help_web_settings") or {}))
        self["help_web_settings"] = 帮助

    def 刷新共享配置(self) -> None:
        原始 = _原配置字典(self.基础配置) or {}
        for 分类, 值 in 原始.items():
            if 分类 in (*机器人独立配置分类, *机器人业务字段分类, "bot_profiles", "__mantou_bot_appid__"):
                continue
            if 分类 == "help_web_settings":
                旧帮助 = self.get(分类) or {}
                值 = {**(值 or {}), **{键: 旧帮助[键] for 键 in 机器人独立帮助字段 if 键 in 旧帮助}}
            self[分类] = copy.deepcopy(值)
        for (分类, 字段), 值 in self._共享待更新.items():
            self.setdefault(分类, {})[字段] = 值

    def get_config(self) -> dict[str, Any]:
        return self

    def 设置配置字段(self, 分类: str, 字段: str, 值: Any) -> None:
        if 分类 in 机器人独立配置分类 or (分类 == "help_web_settings" and 字段 in 机器人独立帮助字段):
            self.setdefault(分类, {})[字段] = 值
            return
        self.setdefault(分类, {})[字段] = 值
        self._共享待更新[(分类, 字段)] = 值

    def _开始保存(self) -> tuple[Any, ...]:
        原始 = _原配置字典(self.基础配置)
        if 原始 is None:
            raise RuntimeError("配置对象不可写入")
        表 = 原始.setdefault("bot_profiles", {})
        旧项 = copy.deepcopy(表.get(self.机器人AppID))
        新项 = _业务快照(self)
        配置键 = id(self.基础配置)
        业务代次键 = (配置键, "bot_profiles", self.机器人AppID)
        业务代次 = _机器人配置写入代次.get(业务代次键, 0) + 1
        _机器人配置写入代次[业务代次键] = 业务代次
        字段快照 = []
        for (分类, 字段), 值 in self._共享待更新.items():
            分类值 = 原始.setdefault(分类, {})
            代次键 = (配置键, 分类, 字段)
            代次 = _机器人配置写入代次.get(代次键, 0) + 1
            _机器人配置写入代次[代次键] = 代次
            字段快照.append((分类, 字段, 字段 in 分类值, copy.deepcopy(分类值.get(字段)), copy.deepcopy(值), 代次键, 代次))
            分类值[字段] = copy.deepcopy(值)
        表[self.机器人AppID] = 新项
        return 原始, 旧项, 新项, 字段快照, 业务代次键, 业务代次

    def _回滚保存(self, 快照: tuple[Any, ...]) -> None:
        原始, 旧项, 新项, 字段快照, 业务代次键, 业务代次 = 快照
        表 = 原始.setdefault("bot_profiles", {})
        if _机器人配置写入代次.get(业务代次键) == 业务代次 and 表.get(self.机器人AppID) == 新项:
            if 旧项 is None:
                表.pop(self.机器人AppID, None)
            else:
                表[self.机器人AppID] = 旧项
            _机器人配置写入代次[业务代次键] = 业务代次 + 1
        for 分类, 字段, 曾存在, 旧值, 新值, 代次键, 代次 in 字段快照:
            分类值 = 原始.setdefault(分类, {})
            if _机器人配置写入代次.get(代次键) == 代次 and 分类值.get(字段) == 新值:
                if 曾存在:
                    分类值[字段] = 旧值
                else:
                    分类值.pop(字段, None)
                _机器人配置写入代次[代次键] = 代次 + 1

    def 清除待保存字段(self) -> None:
        self._共享待更新.clear()

    def save_config(self, *参数: Any) -> Any:
        with _机器人配置锁:
            快照 = self._开始保存()
            try:
                保存 = getattr(self.基础配置, "save_config", None)
                if callable(保存):
                    必填 = [项 for 项 in inspect.signature(保存).parameters.values()
                            if 项.default is inspect.Parameter.empty and 项.kind in
                            (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
                    return 保存(_原配置字典(self.基础配置)) if 必填 else 保存()
            except BaseException:
                self._回滚保存(快照)
                raise
            finally:
                self.清除待保存字段()

    async def save_config_async(self) -> None:
        方法 = getattr(self.基础配置, "save_config_async", None)
        if not callable(方法):
            结果 = self.save_config()
            if inspect.isawaitable(结果):
                await 结果
            return
        快照 = self._开始保存()
        try:
            结果 = 方法()
            if inspect.isawaitable(结果):
                await 结果
        except BaseException:
            self._回滚保存(快照)
            raise
        finally:
            self.清除待保存字段()


def 获取机器人配置(配置: Any, appid: str = "") -> Any:
    目标 = 规范化机器人AppID(appid) or 获取当前机器人AppID(配置)
    if not 目标:
        return 配置
    if isinstance(配置, 机器人配置):
        if 配置.机器人AppID == 目标:
            return 配置
        配置 = 配置.基础配置
    elif isinstance(配置, dict):
        已绑定 = 规范化机器人AppID(配置.get("__mantou_bot_appid__"))
        if 已绑定:
            if 已绑定 != 目标:
                raise ValueError("机器人配置身份不匹配")
            return 配置
        if not any(键 in 配置 for 键 in (*机器人独立配置分类, *机器人业务字段分类, "help_web_settings", "database_settings", "bot_profiles")):
            return 配置
    数据 = _原配置字典(配置)
    if 数据 is None:
        return 配置
    键 = (id(配置), 目标)
    with _机器人配置锁:
        已有 = _机器人配置缓存.get(键)
        if 已有 is not None and 已有.基础配置 is 配置:
            已有.刷新共享配置()
            return 已有
        配置表 = 数据.setdefault("bot_profiles", {})
        if not isinstance(配置表, dict):
            raise ValueError("机器人配置格式无效")
        业务 = 配置表.get(目标)
        if not isinstance(业务, dict):
            业务 = 配置表[目标] = _业务快照(数据)
        结果 = 机器人配置(配置, 目标, 业务)
        if len(_机器人配置缓存) >= 128:
            _机器人配置缓存.pop(next(iter(_机器人配置缓存)))
        _机器人配置缓存[键] = 结果
        return 结果


def 获取事件配置(event: Any, 配置: Any) -> Any:
    return 获取机器人配置(配置, 获取事件机器人AppID(event))


def 机器人作用域缓存键(配置: Any) -> tuple[int, str]:
    return id(getattr(配置, "基础配置", 配置)), 获取当前机器人AppID(配置)


def 枚举机器人配置(配置: Any, 上下文: Any = None) -> list[Any]:
    基础 = getattr(配置, "基础配置", 配置)
    数据 = _原配置字典(基础) or {}
    appids = {规范化机器人AppID(值) for 值 in (数据.get("bot_profiles") or {})}
    if 上下文 is None:
        try:
            from 功能文件.管理功能.基础功能 import 消息记录
            上下文 = 消息记录.当前插件上下文
        except (ImportError, AttributeError):
            pass
    管理器 = getattr(上下文, "platform_manager", None)
    for 平台 in getattr(管理器, "platform_insts", ()) or ():
        appids.add(获取事件机器人AppID(平台))
    try:
        from 功能文件.管理功能.基础功能 import 消息记录
        appids.update(消息记录.获取已配置机器人AppID列表(上下文))
    except (ImportError, AttributeError):
        pass
    return [获取机器人配置(基础, 值) for 值 in sorted(appids) if 值]


def 包装机器人事件入口(函数: Any) -> Any:
    if inspect.isasyncgenfunction(函数):
        @functools.wraps(函数)
        async def 生成器(self: Any, event: Any, *参数: Any, **关键字: Any):
            appid = 获取事件机器人AppID(event)
            迭代 = 函数(self, event, *参数, **关键字).__aiter__()
            try:
                while True:
                    with 绑定机器人作用域(appid):
                        try:
                            项 = await anext(迭代)
                        except StopAsyncIteration:
                            return
                    # 交回 AstrBot pipeline 前必须恢复消费方原有上下文。
                    yield 项
            finally:
                with 绑定机器人作用域(appid):
                    await 迭代.aclose()
        return 生成器
    @functools.wraps(函数)
    async def 协程(self: Any, event: Any, *参数: Any, **关键字: Any):
        with 绑定机器人作用域(获取事件机器人AppID(event)):
            return await 函数(self, event, *参数, **关键字)
    return 协程
