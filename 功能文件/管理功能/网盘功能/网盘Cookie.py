from __future__ import annotations

import asyncio
import contextvars
import hashlib
import io
import inspect
import json
import re
import threading
import time
import uuid
from typing import Any

import aiohttp
import qrcode
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Image, Plain
from yarl import URL

from 功能文件.管理功能.基础功能.权限工具 import (
    是群文件清理管理员,
    获取配置字典,
    读取配置字段,
)
from 功能文件.管理功能.基础功能.运行状态数据库 import (
    写入运行状态值,
    已配置运行状态数据库,
    读取运行状态值,
)

网盘Cookie命名空间 = "novel_pan_auth"
网盘账号选择命名空间 = "novel_pan_account_selection"
平台状态键 = {"UC": "uc", "夸克": "quark", "百度": "baidu"}
平台配置Cookie字段 = {
    "UC": "uc_pan_cookie",
    "夸克": "quark_pan_cookie",
    "百度": "baidu_pan_cookie",
}
平台显示名 = {"UC": "UC网盘", "夸克": "夸克网盘", "百度": "百度网盘"}
平台前缀模式 = re.compile(
    r"^\s*(UC|夸克|百度)(?:网盘)?(?:\s*Cookie)?\s*[:：#]\s*",
    re.I,
)
Cookie名称模式 = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
夸克扫码登录命令 = {"夸克登录", "登录夸克", "刷新夸克Cookie"}
夸克扫码客户端ID = 532
夸克扫码协议版本 = "1.2"
夸克二维码Token地址 = "https://uop.quark.cn/cas/ajax/getTokenForQrcodeLogin"
夸克扫码状态地址 = "https://uop.quark.cn/cas/ajax/getServiceTicketByQrcodeToken"
夸克扫码换取Cookie地址 = "https://pan.quark.cn/account/info"
夸克扫码任务: dict[str, asyncio.Task[Any]] = {}
当前网盘事件: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "mantou_current_pan_event", default=None
)
当前网盘账号覆盖: contextvars.ContextVar[tuple[str, int] | None] = contextvars.ContextVar(
    "mantou_current_pan_account_override", default=None
)
网盘账号写入锁 = threading.RLock()


def _生成夸克扫码请求参数(**附加参数: Any) -> dict[str, Any]:
    参数: dict[str, Any] = {
        "client_id": 夸克扫码客户端ID,
        "v": 夸克扫码协议版本,
        "request_id": str(uuid.uuid4()),
    }
    参数.update(附加参数)
    return 参数


class 夸克扫码登录异常(RuntimeError):
    def __init__(self, 阶段: str, 状态: Any = ""):
        super().__init__(f"夸克扫码登录失败：{阶段}")
        self.阶段 = str(阶段 or "unknown")
        self.状态 = str(状态 or "unknown")


class 夸克扫码登录客户端:
    def __init__(self, session: Any = None):
        self.session = session

    def _获取会话(self) -> Any:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                headers={
                    "accept": "application/json, text/plain, */*",
                    "content-type": "application/x-www-form-urlencoded",
                    "referer": "https://pan.quark.cn/",
                    "user-agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/150.0.0.0 Safari/537.36"
                    ),
                },
            )
        return self.session

    async def 获取登录二维码(self) -> tuple[str, str]:
        try:
            async with self._获取会话().get(
                夸克二维码Token地址,
                params=_生成夸克扫码请求参数(),
            ) as 响应:
                数据 = await 响应.json(content_type=None)
        except Exception as 异常:
            raise 夸克扫码登录异常("token", type(异常).__name__) from 异常
        if not isinstance(数据, dict):
            raise 夸克扫码登录异常("token", "invalid_response")
        Token = str(
            (((数据.get("data") or {}).get("members") or {}).get("token") or "")
        ).strip()
        if 响应.status != 200 or 数据.get("status") != 2000000 or not Token:
            raise 夸克扫码登录异常("token", 数据.get("status") or 响应.status)
        登录地址 = (
            "https://su.quark.cn/4_eMHBJ"
            f"?token={Token}&client_id={夸克扫码客户端ID}"
            "&ssb=weblogin&uc_param_str="
            "&uc_biz_str=S%3Acustom%7COPT%3ASAREA%400%7COPT%3AIMMERSIVE%401"
            "%7COPT%3ABACK_BTN_STYLE%400"
        )
        return Token, 登录地址

    async def 等待登录并获取Cookie(
        self,
        Token: str,
        timeout: float = 300,
        interval: float = 2,
    ) -> str:
        截止时间 = time.monotonic() + max(float(timeout), 0.1)
        while time.monotonic() < 截止时间:
            try:
                async with self._获取会话().get(
                    夸克扫码状态地址,
                    params=_生成夸克扫码请求参数(token=Token),
                ) as 响应:
                    数据 = await 响应.json(content_type=None)
            except Exception as 异常:
                raise 夸克扫码登录异常("poll", type(异常).__name__) from 异常
            if not isinstance(数据, dict):
                raise 夸克扫码登录异常("poll", "invalid_response")
            状态 = 数据.get("status")
            if 响应.status == 200 and 状态 == 2000000:
                票据 = str(
                    (
                        ((数据.get("data") or {}).get("members") or {}).get(
                            "service_ticket"
                        )
                        or ""
                    )
                ).strip()
                if 票据:
                    return await self._使用票据获取Cookie(票据)
                raise 夸克扫码登录异常("poll", "missing_service_ticket")
            if interval > 0:
                await asyncio.sleep(interval)
        raise TimeoutError("夸克扫码登录超时")

    async def _使用票据获取Cookie(self, 票据: str) -> str:
        try:
            async with self._获取会话().get(
                夸克扫码换取Cookie地址,
                params={
                    "st": 票据,
                    "lw": "scan",
                    "fr": "pc",
                    "platform": "pc",
                },
                allow_redirects=True,
            ) as 响应:
                数据 = await 响应.json(content_type=None)
        except Exception as 异常:
            raise 夸克扫码登录异常("auth", type(异常).__name__) from 异常
        if 响应.status != 200 or not isinstance(数据, dict) or not 数据.get("success"):
            状态 = 数据.get("code") if isinstance(数据, dict) else ""
            raise 夸克扫码登录异常("auth", 状态 or 响应.status)
        Cookie字段: dict[str, str] = {}
        for 名称, Morsel in getattr(响应, "cookies", {}).items():
            值 = str(getattr(Morsel, "value", Morsel) or "").strip()
            if 值:
                Cookie字段[str(名称)] = 值
        for 地址 in (
            "https://pan.quark.cn/",
            "https://pan.quark.cn/account/info",
            "https://drive-pc.quark.cn/",
        ):
            for 名称, Morsel in (
                self._获取会话().cookie_jar.filter_cookies(URL(地址)).items()
            ):
                值 = str(getattr(Morsel, "value", Morsel) or "").strip()
                if 值:
                    Cookie字段[str(名称)] = 值
        Cookie = "; ".join(f"{名称}={值}" for 名称, 值 in Cookie字段.items())
        解析结果 = 解析网盘Cookie(f"夸克 Cookie: {Cookie}")
        if not 解析结果 or not 解析结果[1]:
            raise 夸克扫码登录异常("cookie", "missing_required_fields")
        return 解析结果[1]

    async def 关闭(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None


def 生成夸克登录二维码(登录地址: str) -> bytes:
    二维码 = qrcode.QRCode(version=None, box_size=8, border=3)
    二维码.add_data(str(登录地址))
    二维码.make(fit=True)
    图片 = 二维码.make_image(fill_color="black", back_color="white")
    缓冲区 = io.BytesIO()
    图片.save(缓冲区, format="PNG")
    return 缓冲区.getvalue()


def _规范化平台名称(平台: Any) -> str:
    文本 = str(平台 or "").strip()
    if 文本.lower() == "uc":
        return "UC"
    if 文本 in ("夸克", "百度"):
        return 文本
    return ""


def 设置当前网盘事件(event: Any) -> contextvars.Token[Any]:
    """让后台小说任务沿用触发下载的群聊账号选择。"""
    return 当前网盘事件.set(event)


def 清除当前网盘事件(令牌: contextvars.Token[Any] | None) -> None:
    if 令牌 is None:
        return
    try:
        当前网盘事件.reset(令牌)
    except (LookupError, ValueError):
        pass


def 设置网盘账号覆盖(平台: Any, 序号: int) -> contextvars.Token[Any] | None:
    规范平台 = _规范化平台名称(平台)
    if not 规范平台:
        return None
    try:
        规范序号 = max(1, int(序号))
    except (TypeError, ValueError):
        规范序号 = 1
    return 当前网盘账号覆盖.set((规范平台, 规范序号))


def 清除网盘账号覆盖(令牌: contextvars.Token[Any] | None) -> None:
    if 令牌 is None:
        return
    try:
        当前网盘账号覆盖.reset(令牌)
    except (LookupError, ValueError):
        pass


def _读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 获取网盘群标识(event: Any = None) -> str:
    """提取普通群号或 QQ 官方 group_openid，不把事件对象转成字符串。"""
    当前事件 = event if event is not None else 当前网盘事件.get()
    if 当前事件 is None:
        return ""
    for 方法名 in ("get_group_id",):
        方法 = getattr(当前事件, 方法名, None)
        if callable(方法):
            try:
                原始值 = 方法()
                if inspect.isawaitable(原始值):
                    close = getattr(原始值, "close", None)
                    if callable(close):
                        close()
                    原始值 = ""
                值 = str(原始值 or "").strip()
            except Exception:
                值 = ""
            if 值:
                return 值
    待检查 = [当前事件]
    for 属性名 in ("message_obj", "raw_message", "message", "data"):
        值 = getattr(当前事件, 属性名, None)
        if 值 is not None:
            待检查.append(值)
    字段名列表 = ("group_openid", "group_id", "group_open_id")
    已检查: set[int] = set()
    while 待检查:
        对象 = 待检查.pop(0)
        标识 = id(对象)
        if 标识 in 已检查:
            continue
        已检查.add(标识)
        for 字段名 in 字段名列表:
            值 = _读取字段(对象, 字段名)
            if isinstance(值, dict):
                值 = 值.get("group_openid") or 值.get("group_id") or 值.get("id")
            if 值 is not None and str(值).strip():
                return str(值).strip()
        if isinstance(对象, dict):
            for 字段名 in ("message_obj", "message", "data", "event"):
                值 = 对象.get(字段名)
                if isinstance(值, (dict, list, tuple)):
                    待检查.extend(值 if isinstance(值, (list, tuple)) else [值])
    return ""


def _规范化Cookie名称(名称: Any) -> str:
    文本 = str(名称 or "").strip().strip("*`'\"")
    文本 = 文本.replace("\\_", "_").replace("\\-", "-")
    return 文本 if Cookie名称模式.fullmatch(文本) else ""


def _写入Cookie字段(字段: dict[str, tuple[str, str]], 名称: Any, 值: Any) -> None:
    Cookie名称 = _规范化Cookie名称(名称)
    Cookie值 = str(值 if 值 is not None else "").strip().strip("'\"`")
    if not Cookie名称 or not Cookie值:
        return
    字段[Cookie名称.lower()] = (Cookie名称, Cookie值)


def _从CookieJSON提取(
    数据: Any, 字段: dict[str, tuple[str, str]], 域名: set[str]
) -> None:
    if isinstance(数据, list):
        for 项目 in 数据:
            _从CookieJSON提取(项目, 字段, 域名)
        return
    if not isinstance(数据, dict):
        return
    名称 = 数据.get("name")
    值 = 数据.get("value")
    if 名称 is not None and 值 is not None:
        _写入Cookie字段(字段, 名称, 值)
    当前域名 = str(数据.get("domain") or 数据.get("host") or "").strip().lower()
    if 当前域名:
        域名.add(当前域名.lstrip("."))
    for 键, 项目值 in 数据.items():
        规范键 = _规范化Cookie名称(键)
        if 规范键 and isinstance(项目值, (str, int, float)):
            if 规范键.lower() in {
                "bduss",
                "stoken",
                "b-user-id",
                "__puus",
                "__uid",
                "__kps",
                "__kp",
                "__ktd",
                "ctoken",
                "udrive_transfer_sess",
            }:
                _写入Cookie字段(字段, 规范键, 项目值)
        elif isinstance(项目值, (dict, list)):
            _从CookieJSON提取(项目值, 字段, 域名)


def _提取Cookie候选文本(原文: str) -> list[str]:
    候选: list[str] = []
    for 模式 in (
        re.compile(r"(?:-H|--header)\s*(['\"])Cookie\s*:\s*(.*?)\1", re.I | re.S),
        re.compile(r"(?:-b|--cookie)\s*(['\"])(.*?)\1", re.I | re.S),
    ):
        候选.extend(
            匹配.group(2).strip()
            for 匹配 in 模式.finditer(原文)
            if 匹配.group(2).strip()
        )
    for 行 in 原文.splitlines():
        匹配 = re.match(r"^\s*Cookie\s*:\s*(.+)$", 行, re.I)
        if 匹配:
            候选.append(匹配.group(1).strip())
    return 候选 or [原文]


def _提取Cookie字段(文本: Any) -> tuple[dict[str, tuple[str, str]], set[str], str, str]:
    原文 = str(文本 or "").strip()
    指定平台 = ""
    前缀匹配 = 平台前缀模式.match(原文)
    if 前缀匹配:
        指定平台 = _规范化平台名称(前缀匹配.group(1))
        原文 = 原文[前缀匹配.end() :].strip()

    字段: dict[str, tuple[str, str]] = {}
    域名: set[str] = set()
    try:
        JSON数据 = json.loads(原文)
    except (TypeError, ValueError, json.JSONDecodeError):
        JSON数据 = None
    if JSON数据 is not None:
        _从CookieJSON提取(JSON数据, 字段, 域名)

    for 行 in 原文.splitlines():
        处理行 = 行.strip()
        if 处理行.startswith("#HttpOnly_"):
            处理行 = 处理行[len("#HttpOnly_") :]
        elif 处理行.startswith("#"):
            continue
        分段 = 处理行.split("\t")
        if len(分段) >= 7:
            域名.add(str(分段[0]).strip().lower().lstrip("."))
            _写入Cookie字段(字段, 分段[5], 分段[6])

    if not 字段:
        for 候选 in _提取Cookie候选文本(原文):
            for 片段 in re.split(r";\s*|\r?\n", 候选):
                片段 = 片段.strip().strip("'\"`")
                if not 片段 or "=" not in 片段:
                    continue
                名称, 值 = 片段.split("=", 1)
                _写入Cookie字段(字段, 名称, 值)
    return 字段, 域名, 指定平台, 原文


def _识别平台(
    字段: dict[str, tuple[str, str]],
    域名: set[str],
    指定平台: str,
    原文: str,
) -> str:
    if 指定平台:
        return 指定平台
    名称集合 = set(字段)
    域名文本 = " ".join(域名)
    原文小写 = 原文.lower()
    if {"bduss", "stoken"}.issubset(名称集合) or "baidu.com" in 域名文本:
        return "百度"
    if (
        "udrive_transfer_sess" in 名称集合
        or any(名称.startswith("_up_28a_") for 名称 in 名称集合)
        or "drive.uc.cn" in 原文小写
        or "uc.cn" in 域名文本
    ):
        return "UC"
    if (
        ("__puus" in 名称集合 and bool({"b-user-id", "__uid", "__kps"} & 名称集合))
        or {"ctoken", "__puus"}.issubset(名称集合)
        or "quark.cn" in 域名文本
        or "pan.quark.cn" in 原文小写
        or "drive-pc.quark.cn" in 原文小写
    ):
        return "夸克"
    return ""


def _Cookie字段完整(平台: str, 字段: dict[str, tuple[str, str]]) -> bool:
    名称集合 = set(字段)
    if 平台 == "UC":
        return "udrive_transfer_sess" in 名称集合 and bool(
            {"ctoken", "__puus", "__uid"} & 名称集合
        )
    if 平台 == "夸克":
        return "__puus" in 名称集合 and bool({"b-user-id", "__uid", "__kps"} & 名称集合)
    if 平台 == "百度":
        return {"bduss", "stoken"}.issubset(名称集合)
    return False


def _序列化Cookie字段(字段: dict[str, tuple[str, str]]) -> str:
    return "; ".join(f"{名称}={值}" for 名称, 值 in 字段.values())


def 解析网盘Cookie(文本: Any) -> tuple[str, str] | None:
    字段, 域名, 指定平台, 原文 = _提取Cookie字段(文本)
    平台 = _识别平台(字段, 域名, 指定平台, 原文)
    if not 平台:
        return None
    if not _Cookie字段完整(平台, 字段):
        return 平台, ""
    return 平台, _序列化Cookie字段(字段)


def _解析保存的网盘账号列表(原始值: Any, 平台: str) -> list[str]:
    文本 = str(原始值 or "").strip()
    if not 文本:
        return []
    try:
        数据 = json.loads(文本)
    except (TypeError, ValueError, json.JSONDecodeError):
        数据 = 文本
    候选列表: list[Any]
    if isinstance(数据, dict):
        账号数据 = 数据.get("accounts")
        if isinstance(账号数据, list):
            候选列表 = 账号数据
        else:
            候选列表 = [数据.get("cookie") or ""]
    elif isinstance(数据, list):
        候选列表 = 数据
    else:
        候选列表 = [数据]
    结果: list[str] = []
    for 项目 in 候选列表:
        if isinstance(项目, dict):
            项目 = 项目.get("cookie") or 项目.get("value") or ""
        解析结果 = 解析网盘Cookie(f"{平台} Cookie: {项目}")
        if not 解析结果 or 解析结果[0] != 平台 or not 解析结果[1]:
            continue
        Cookie = 解析结果[1]
        if Cookie not in 结果:
            结果.append(Cookie)
    return 结果


def _读取保存的网盘账号列表(配置: Any, 平台: str) -> list[str]:
    原始值 = 读取运行状态值(配置, 网盘Cookie命名空间, 平台状态键[平台], "")
    return _解析保存的网盘账号列表(原始值, 平台)


def _写入网盘账号列表(配置: Any, 平台: str, 账号列表: list[str]) -> None:
    payload = json.dumps(
        {
            "provider": 平台,
            "accounts": [
                {"index": index, "cookie": Cookie}
                for index, Cookie in enumerate(账号列表, start=1)
            ],
            "updated_at": int(time.time()),
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    写入运行状态值(配置, 网盘Cookie命名空间, 平台状态键[平台], payload)


def _读取平台配置Cookie(配置: Any, 平台: str) -> Any:
    字段名 = 平台配置Cookie字段[平台]
    值 = 读取配置字段(配置, 字段名)
    if 值:
        return 值
    配置字典 = 获取配置字典(配置)
    if not isinstance(配置字典, dict):
        return 值
    if 配置字典.get(字段名):
        return 配置字典.get(字段名)
    分类名 = {
        "UC": "uc_pan_settings",
        "夸克": "quark_pan_settings",
        "百度": "baidu_pan_settings",
    }[平台]
    旧分类名 = {"UC": "UC网盘设置", "夸克": "夸克网盘设置", "百度": "百度网盘设置"}[平台]
    for 名称 in (分类名, 旧分类名):
        分类 = 配置字典.get(名称)
        if isinstance(分类, dict) and 分类.get(字段名):
            return 分类.get(字段名)
    return 值


def _保存网盘Cookie(配置: Any, 平台: str, Cookie: str) -> int:
    """新增平台账号并返回账号序号；相同 Cookie 不重复占用新序号。"""
    with 网盘账号写入锁:
        账号列表 = _读取保存的网盘账号列表(配置, 平台)
        if not 账号列表:
            配置Cookie = _读取平台配置Cookie(配置, 平台)
            配置结果 = 解析网盘Cookie(f"{平台} Cookie: {配置Cookie or ''}")
            if 配置结果 and 配置结果[1]:
                账号列表.append(配置结果[1])
        if Cookie not in 账号列表:
            账号列表.append(Cookie)
            _写入网盘账号列表(配置, 平台, 账号列表)
        return 账号列表.index(Cookie) + 1


def _账号选择状态键(平台: str, 群标识: str) -> str:
    原键 = f"{平台}:{群标识}"
    if len(原键) <= 128:
        return 原键
    摘要 = hashlib.sha256(str(群标识).encode("utf-8", errors="replace")).hexdigest()
    return f"{平台}:sha256:{摘要}"


def _读取网盘账号序号(配置: Any, 平台: str, event: Any = None) -> int:
    覆盖 = 当前网盘账号覆盖.get()
    if 覆盖 and 覆盖[0] == 平台:
        return 覆盖[1]
    群标识 = 获取网盘群标识(event)
    if not 群标识 or not 已配置运行状态数据库(配置):
        return 1
    try:
        文本 = 读取运行状态值(
            配置,
            网盘账号选择命名空间,
            _账号选择状态键(平台, 群标识),
            "1",
        )
        序号 = int(str(文本 or "1").strip())
        return 序号 if 序号 > 0 else 1
    except Exception:
        return 1


def 获取网盘账号列表(配置: Any, 平台: str, 配置Cookie: Any = "") -> list[str]:
    规范平台 = _规范化平台名称(平台)
    if not 规范平台:
        return []
    if 已配置运行状态数据库(配置):
        try:
            保存列表 = _读取保存的网盘账号列表(配置, 规范平台)
            if 保存列表:
                return 保存列表
        except Exception as 异常:
            logger.warning(
                f"{平台显示名[规范平台]}Cookie列表读取失败：error={type(异常).__name__}"
            )
    if not 配置Cookie:
        配置Cookie = _读取平台配置Cookie(配置, 规范平台)
    配置原值 = str(配置Cookie or "").strip()
    if not 配置原值:
        return []
    解析结果 = 解析网盘Cookie(f"{规范平台} Cookie: {配置原值}")
    return [解析结果[1]] if 解析结果 and 解析结果[1] else []


def 获取网盘账号数量(配置: Any, 平台: str, 配置Cookie: Any = "") -> int:
    return len(获取网盘账号列表(配置, 平台, 配置Cookie))


def 获取当前网盘账号序号(配置: Any, 平台: str, event: Any = None) -> int:
    账号列表 = 获取网盘账号列表(配置, 平台)
    if not 账号列表:
        return 1
    return min(_读取网盘账号序号(配置, 平台, event), len(账号列表))


def 设置网盘账号序号(
    配置: Any, 平台: str, 序号: int, event: Any = None
) -> tuple[bool, str]:
    规范平台 = _规范化平台名称(平台)
    群标识 = 获取网盘群标识(event)
    if not 规范平台 or not 群标识:
        return False, "请在群聊中使用此指令"
    if not 已配置运行状态数据库(配置):
        return False, "数据库未配置，网盘账号选择未保存"
    账号数量 = 获取网盘账号数量(配置, 规范平台)
    if 序号 < 1 or 序号 > 账号数量:
        return False, f"{平台显示名[规范平台]}只有{账号数量}个账号"
    try:
        写入运行状态值(
            配置,
            网盘账号选择命名空间,
            _账号选择状态键(规范平台, 群标识),
            str(序号),
        )
    except Exception as 异常:
        logger.warning(
            f"{平台显示名[规范平台]}群账号选择写入失败：error={type(异常).__name__}"
        )
        return False, "网盘账号选择失败，请稍后再试"
    return True, ""


def 读取网盘Cookie(
    配置: Any, 平台: str, 配置Cookie: Any = "", event: Any = None
) -> str:
    规范平台 = _规范化平台名称(平台)
    账号列表 = 获取网盘账号列表(配置, 规范平台, 配置Cookie)
    if not 账号列表:
        return str(配置Cookie or "").strip()
    序号 = min(_读取网盘账号序号(配置, 规范平台, event), len(账号列表))
    return 账号列表[序号 - 1]


def 持久化刷新后的网盘Cookie(
    配置: Any,
    平台: str,
    原Cookie: Any,
    新Cookie: Any,
) -> None:
    规范平台 = _规范化平台名称(平台)
    原值 = str(原Cookie or "").strip()
    新值 = str(新Cookie or "").strip()
    if not 规范平台 or not 新值 or 新值 == 原值 or not 已配置运行状态数据库(配置):
        return
    try:
        解析结果 = 解析网盘Cookie(f"{规范平台} Cookie: {新值}")
        if not 解析结果 or not 解析结果[1]:
            return
        with 网盘账号写入锁:
            账号列表 = _读取保存的网盘账号列表(配置, 规范平台)
            if not 账号列表 or 原值 not in 账号列表:
                return
            原位置 = 账号列表.index(原值)
            新值 = 解析结果[1]
            其他位置 = next(
                (
                    位置
                    for 位置, 值 in enumerate(账号列表)
                    if 值 == 新值 and 位置 != 原位置
                ),
                None,
            )
            if 其他位置 is None:
                账号列表[原位置] = 新值
            else:
                账号列表.pop(原位置)
            _写入网盘账号列表(配置, 规范平台, 账号列表)
    except Exception as 异常:
        logger.warning(
            f"{平台显示名[规范平台]}Cookie刷新保存失败：error={type(异常).__name__}"
        )


def _事件发送者标识(event: Any) -> str:
    获取方法 = getattr(event, "get_sender_id", None)
    if callable(获取方法):
        try:
            标识 = str(获取方法() or "").strip()
            if 标识:
                return 标识
        except Exception:
            pass
    return str(id(event))


def _事件位于群聊(event: Any) -> bool:
    return bool(获取网盘群标识(event))


async def _发送扫码结果(event: Any, 文本: str) -> None:
    try:
        await event.send(MessageChain([Plain(文本)]))
    except Exception as 异常:
        logger.warning(f"夸克扫码结果通知失败：error={type(异常).__name__}")


async def _等待夸克扫码并保存(
    event: Any,
    配置: Any,
    发送者标识: str,
    客户端: 夸克扫码登录客户端,
    Token: str,
) -> None:
    当前任务 = asyncio.current_task()
    try:
        Cookie = await 客户端.等待登录并获取Cookie(Token, timeout=300, interval=2)
        账号序号 = await asyncio.to_thread(_保存网盘Cookie, 配置, "夸克", Cookie)
        await _发送扫码结果(event, f"夸克网盘登录成功，已保存为账号{账号序号}")
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        await _发送扫码结果(event, "夸克网盘登录超时，请重新发送夸克登录")
    except Exception as 异常:
        阶段 = str(getattr(异常, "阶段", "unknown") or "unknown")
        状态 = str(getattr(异常, "状态", "unknown") or "unknown")
        logger.warning(
            f"夸克扫码登录失败：stage={阶段}, status={状态}, error={type(异常).__name__}"
        )
        await _发送扫码结果(event, "夸克网盘登录失败，请稍后再试")
    finally:
        await 客户端.关闭()
        if 夸克扫码任务.get(发送者标识) is 当前任务:
            夸克扫码任务.pop(发送者标识, None)


async def 停止全部夸克扫码登录任务() -> None:
    任务列表 = list(夸克扫码任务.values())
    夸克扫码任务.clear()
    for 任务 in 任务列表:
        if not 任务.done():
            任务.cancel()
    if 任务列表:
        await asyncio.gather(*任务列表, return_exceptions=True)


async def 处理网盘Cookie指令(event: Any, 命令文本: str, 配置: Any = None) -> Any | None:
    设置当前网盘事件(event)
    文本 = str(命令文本 or "").strip()
    if 文本 in 夸克扫码登录命令:
        if not 是群文件清理管理员(event, 配置):
            return ""
        if _事件位于群聊(event):
            return "请私聊机器人发送夸克登录"
        if not 已配置运行状态数据库(配置):
            return "数据库未配置，夸克网盘登录态未保存"
        发送者标识 = _事件发送者标识(event)
        旧任务 = 夸克扫码任务.pop(发送者标识, None)
        if 旧任务 is not None and not 旧任务.done():
            旧任务.cancel()
            await asyncio.gather(旧任务, return_exceptions=True)
        客户端 = 夸克扫码登录客户端()
        try:
            Token, 登录地址 = await 客户端.获取登录二维码()
            二维码 = 生成夸克登录二维码(登录地址)
        except Exception as 异常:
            await 客户端.关闭()
            阶段 = str(getattr(异常, "阶段", "token") or "token")
            状态 = str(getattr(异常, "状态", "unknown") or "unknown")
            logger.warning(
                f"夸克扫码二维码生成失败：stage={阶段}, status={状态}, "
                f"error={type(异常).__name__}"
            )
            return "夸克网盘登录失败，请稍后再试"
        任务 = asyncio.create_task(
            _等待夸克扫码并保存(event, 配置, 发送者标识, 客户端, Token)
        )
        夸克扫码任务[发送者标识] = 任务
        return event.chain_result(
            [
                Plain(
                    "已重新获取新的夸克登录二维码，请使用夸克网盘App扫码，5分钟内有效。"
                ),
                Image.fromBytes(二维码),
            ]
        )

    解析结果 = 解析网盘Cookie(命令文本)
    if 解析结果 is None:
        return None
    平台, Cookie = 解析结果
    if not 是群文件清理管理员(event, 配置):
        return ""
    显示名 = 平台显示名[平台]
    if not Cookie:
        return f"{显示名}Cookie无效，请提供完整浏览器Cookie"
    if not 已配置运行状态数据库(配置):
        return f"数据库未配置，{显示名}Cookie未保存"
    try:
        账号序号 = await asyncio.to_thread(_保存网盘Cookie, 配置, 平台, Cookie)
    except Exception as 异常:
        logger.warning(f"{显示名}Cookie保存失败：error={type(异常).__name__}")
        return f"{显示名}Cookie保存失败，请稍后再试"
    return f"{显示名}Cookie已保存为账号{账号序号}"
