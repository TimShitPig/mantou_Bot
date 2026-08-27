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
from http.cookies import SimpleCookie
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
    读取运行状态命名空间,
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
夸克账号资料地址 = "https://pan.quark.cn/account/info"
夸克扫码刷新Cookie地址 = "https://drive-pc.quark.cn/1/clouddrive/auth/pc/flush"
夸克扫码任务: dict[str, asyncio.Task[Any]] = {}
夸克账号查看命令 = {"夸克账号", "夸克账号列表", "夸克账户", "夸克账户列表"}
夸克账号添加命令 = {"添加夸克", "添加夸克账号"}
夸克账号删除模式 = re.compile(
    r"^(?:删|删除)\s*(?:夸|夸克)(?:网盘)?(?:账号)?\s*([1-9]\d*)$"
)
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

        def 收集响应Cookie(响应链: Any) -> None:
            for 响应项 in 响应链:
                for 名称, Morsel in getattr(响应项, "cookies", {}).items():
                    值 = str(getattr(Morsel, "value", Morsel) or "").strip()
                    if 值:
                        Cookie字段[str(名称)] = 值
                头部 = getattr(响应项, "headers", None)
                获取全部 = getattr(头部, "getall", None)
                if not callable(获取全部):
                    continue
                for 原始Cookie in 获取全部("Set-Cookie", ()):
                    try:
                        解析Cookie = SimpleCookie()
                        解析Cookie.load(str(原始Cookie))
                    except Exception:
                        continue
                    for 名称, Morsel in 解析Cookie.items():
                        值 = str(getattr(Morsel, "value", Morsel) or "").strip()
                        if 值:
                            Cookie字段[str(名称)] = 值

        响应链 = [*(getattr(响应, "history", ()) or ()), 响应]
        收集响应Cookie(响应链)
        刷新响应链: list[Any] = []
        for 地址 in (
            "https://uop.quark.cn/",
            "https://su.quark.cn/",
            "https://b.quark.cn/",
            "https://quark.cn/",
            "https://pan.quark.cn/",
            "https://pan.quark.cn/account/info",
            "https://drive-pc.quark.cn/",
            "https://drive-h.quark.cn/",
        ):
            for 名称, Morsel in (
                self._获取会话().cookie_jar.filter_cookies(URL(地址)).items()
            ):
                值 = str(getattr(Morsel, "value", Morsel) or "").strip()
                if 值:
                    Cookie字段[str(名称)] = 值
        if "__puus" not in {名称.lower() for 名称 in Cookie字段} and "__pus" in {
            名称.lower() for 名称 in Cookie字段
        }:
            当前Cookie = "; ".join(
                f"{名称}={值}" for 名称, 值 in Cookie字段.items()
            )
            try:
                async with self._获取会话().get(
                    夸克扫码刷新Cookie地址,
                    params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
                    headers={
                        "Cookie": 当前Cookie,
                        "Origin": "https://pan.quark.cn",
                        "Referer": "https://pan.quark.cn/",
                    },
                    allow_redirects=True,
                ) as 刷新响应:
                    刷新响应链 = [
                        *(getattr(刷新响应, "history", ()) or ()),
                        刷新响应,
                    ]
                    收集响应Cookie(刷新响应链)
                    if not 200 <= int(getattr(刷新响应, "status", 0) or 0) < 300:
                        logger.warning(
                            "夸克扫码刷新登录态失败：stage=auth, status=%s, error=http_status",
                            getattr(刷新响应, "status", "unknown"),
                        )
                    读取正文 = getattr(刷新响应, "read", None)
                    if callable(读取正文):
                        读取结果 = 读取正文()
                        if inspect.isawaitable(读取结果):
                            await 读取结果
            except Exception as 异常:
                logger.warning(
                    "夸克扫码刷新登录态失败：stage=auth, status=flush, error=%s",
                    type(异常).__name__,
                )
        if 刷新响应链:
            收集响应Cookie(刷新响应链)

        JSON字段, _, _, _ = _提取Cookie字段(json.dumps(数据, ensure_ascii=False))
        for _, (名称, 值) in JSON字段.items():
            Cookie字段[名称] = 值
        for 名称, 值 in _提取夸克扫码JSONCookie(数据).items():
            Cookie字段[名称] = 值
        if 刷新响应链:
            收集响应Cookie(刷新响应链)
        Cookie = "; ".join(f"{名称}={值}" for 名称, 值 in Cookie字段.items())
        解析结果 = 解析网盘Cookie(f"夸克 Cookie: {Cookie}")
        if not 解析结果 or not 解析结果[1]:
            logger.warning(
                "夸克扫码登录态字段不完整：stage=cookie, fields=%s",
                ",".join(sorted(名称.lower() for 名称 in Cookie字段)),
            )
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


def _提取夸克扫码JSONCookie(数据: Any) -> dict[str, str]:
    """兼容账号接口把 Cookie 放在 JSON 字符串字段中的返回格式。"""
    结果: dict[str, str] = {}

    def 遍历(对象: Any) -> None:
        if isinstance(对象, dict):
            for 键, 值 in 对象.items():
                if isinstance(值, str) and (
                    "=" in 值
                    or str(键).lower() in {"cookie", "cookies", "set-cookie"}
                ):
                    字段, _, _, _ = _提取Cookie字段(值)
                    for _, (名称, 字段值) in 字段.items():
                        结果[名称] = 字段值
                elif isinstance(值, (dict, list, tuple)):
                    遍历(值)
        elif isinstance(对象, (list, tuple)):
            for 项目 in 对象:
                遍历(项目)

    遍历(数据)
    return 结果


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


def _获取网盘Cookie身份键(平台: str, Cookie: Any) -> str:
    """返回不随会话刷新变化的账号键；夸克优先使用用户 ID。"""
    if 平台 != "夸克":
        return ""
    字段, _, _, _ = _提取Cookie字段(Cookie)
    for 名称 in ("__uid", "b-user-id", "__kps"):
        值 = 字段.get(名称)
        if 值 and 值[1]:
            return f"{平台}:{名称}:{值[1]}"
    return ""


def _清理账号资料文本(值: Any, 最大长度: int = 128) -> str:
    文本 = re.sub(r"[\x00-\x1f\x7f\r\n]+", " ", str(值 or "")).strip()
    if not 文本:
        return ""
    return 文本[:最大长度]


def _脱敏手机号(值: Any) -> str:
    """只保留可展示的脱敏手机号，绝不把完整号码写入运行状态。"""
    文本 = str(值 or "").strip()
    if not 文本:
        return ""
    数字 = re.sub(r"\D", "", 文本)
    if len(数字) >= 7:
        return f"{数字[:3]}****{数字[-4:]}"
    if "*" in 文本 and len(文本) <= 32:
        return 文本
    return ""


def _递归查找账号资料字段(对象: Any, 字段名集合: set[str]) -> str:
    if isinstance(对象, dict):
        for 键, 值 in 对象.items():
            if str(键).lower() in 字段名集合 and isinstance(值, (str, int, float)):
                文本 = str(值).strip()
                if 文本:
                    return 文本
        for 值 in 对象.values():
            结果 = _递归查找账号资料字段(值, 字段名集合)
            if 结果:
                return 结果
    elif isinstance(对象, (list, tuple)):
        for 值 in 对象:
            结果 = _递归查找账号资料字段(值, 字段名集合)
            if 结果:
                return 结果
    return ""


def _解析夸克账号资料(响应数据: Any) -> tuple[str, str]:
    if not isinstance(响应数据, dict) or not (
        响应数据.get("success")
        or str(响应数据.get("code") or "").upper() == "OK"
        or 响应数据.get("status") == 2000000
    ):
        return "", ""
    数据 = 响应数据.get("data")
    名称 = _递归查找账号资料字段(
        数据,
        {
            "nickname",
            "nick_name",
            "username",
            "user_name",
            "displayname",
            "display_name",
            "account_name",
            "uname",
        },
    )
    手机号 = _递归查找账号资料字段(
        数据,
        {
            "mobile",
            "phone",
            "phone_number",
            "mobile_phone",
            "mobilephone",
            "phonenum",
            "mobile_num",
            "masked_mobile",
            "masked_phone",
        },
    )
    return _清理账号资料文本(名称), _脱敏手机号(手机号)


def _解析保存的网盘账号记录(原始值: Any, 平台: str) -> list[dict[str, str]]:
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
    结果: list[dict[str, str]] = []
    for 项目 in 候选列表:
        元数据: dict[str, Any] = 项目 if isinstance(项目, dict) else {}
        if isinstance(项目, dict):
            项目 = 项目.get("cookie") or 项目.get("value") or ""
        解析结果 = 解析网盘Cookie(f"{平台} Cookie: {项目}")
        if not 解析结果 or 解析结果[0] != 平台 or not 解析结果[1]:
            continue
        Cookie = 解析结果[1]
        记录 = {
            "cookie": Cookie,
            "identity": _清理账号资料文本(
                元数据.get("identity") or _获取网盘Cookie身份键(平台, Cookie)
            ),
            "name": _清理账号资料文本(
                元数据.get("name") or 元数据.get("nickname")
            ),
            "phone": _脱敏手机号(
                元数据.get("phone") or 元数据.get("mobile")
            ),
        }
        已有位置 = next(
            (
                位置
                for 位置, 已有记录 in enumerate(结果)
                if (
                    记录["identity"]
                    and 已有记录.get("identity") == 记录["identity"]
                )
                or 已有记录.get("cookie") == Cookie
            ),
            None,
        )
        if 已有位置 is None:
            结果.append(记录)
        else:
            已有记录 = 结果[已有位置]
            for 字段 in ("name", "phone"):
                if 记录[字段]:
                    已有记录[字段] = 记录[字段]
    return 结果


def _解析保存的网盘账号列表(原始值: Any, 平台: str) -> list[str]:
    return [记录["cookie"] for 记录 in _解析保存的网盘账号记录(原始值, 平台)]


def _合并配置网盘账号记录(
    配置: Any, 平台: str, 账号记录: list[dict[str, str]]
) -> list[dict[str, str]]:
    """把插件配置中的账号1合并到已持久化列表，保持数据库优先。"""
    配置Cookie = _读取平台配置Cookie(配置, 平台)
    配置结果 = 解析网盘Cookie(f"{平台} Cookie: {配置Cookie or ''}")
    if not 配置结果 or 配置结果[0] != 平台 or not 配置结果[1]:
        return 账号记录
    配置Cookie = 配置结果[1]
    配置身份 = _获取网盘Cookie身份键(平台, 配置Cookie)
    已存在 = any(
        记录.get("cookie") == 配置Cookie
        or (配置身份 and 记录.get("identity") == 配置身份)
        for 记录 in 账号记录
    )
    if not 已存在:
        账号记录.insert(
            0,
            {
                "cookie": 配置Cookie,
                "identity": 配置身份,
                "name": "",
                "phone": "",
            },
        )
    return 账号记录


def _读取保存的网盘账号记录(配置: Any, 平台: str) -> list[dict[str, str]]:
    原始值 = 读取运行状态值(配置, 网盘Cookie命名空间, 平台状态键[平台], "")
    return _合并配置网盘账号记录(
        配置, 平台, _解析保存的网盘账号记录(原始值, 平台)
    )


def _读取保存的网盘账号列表(配置: Any, 平台: str) -> list[str]:
    return [记录["cookie"] for 记录 in _读取保存的网盘账号记录(配置, 平台)]


def _写入网盘账号记录(
    配置: Any, 平台: str, 账号记录: list[dict[str, Any]]
) -> None:
    账号数据: list[dict[str, Any]] = []
    for index, 原记录 in enumerate(账号记录, start=1):
        Cookie = str(原记录.get("cookie") or "").strip()
        if not Cookie:
            continue
        记录: dict[str, Any] = {"index": index, "cookie": Cookie}
        身份 = _清理账号资料文本(
            原记录.get("identity") or _获取网盘Cookie身份键(平台, Cookie)
        )
        名称 = _清理账号资料文本(原记录.get("name") or 原记录.get("nickname"))
        手机号 = _脱敏手机号(原记录.get("phone") or 原记录.get("mobile"))
        if 身份:
            记录["identity"] = 身份
        if 名称:
            记录["name"] = 名称
        if 手机号:
            记录["phone"] = 手机号
        账号数据.append(记录)
    payload = json.dumps(
        {
            "provider": 平台,
            "accounts": 账号数据,
            "updated_at": int(time.time()),
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    写入运行状态值(配置, 网盘Cookie命名空间, 平台状态键[平台], payload)


def _写入网盘账号列表(配置: Any, 平台: str, 账号列表: list[str]) -> None:
    旧记录 = _读取保存的网盘账号记录(配置, 平台)
    新记录: list[dict[str, Any]] = []
    for Cookie in 账号列表:
        身份 = _获取网盘Cookie身份键(平台, Cookie)
        原记录 = next(
            (
                记录
                for 记录 in 旧记录
                if (身份 and 记录.get("identity") == 身份)
                or 记录.get("cookie") == Cookie
            ),
            {},
        )
        新记录.append(
            {
                "cookie": Cookie,
                "identity": 身份 or 原记录.get("identity", ""),
                "name": 原记录.get("name", ""),
                "phone": 原记录.get("phone", ""),
            }
        )
    _写入网盘账号记录(配置, 平台, 新记录)


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


def _保存网盘Cookie(
    配置: Any,
    平台: str,
    Cookie: str,
    *,
    名称: Any = "",
    手机号: Any = "",
) -> int:
    """保存平台账号；同一夸克身份刷新 Cookie 时保留原账号序号。"""
    规范平台 = _规范化平台名称(平台)
    新身份键 = _获取网盘Cookie身份键(规范平台, Cookie)
    新名称 = _清理账号资料文本(名称)
    新手机号 = _脱敏手机号(手机号)
    with 网盘账号写入锁:
        账号记录 = _读取保存的网盘账号记录(配置, 规范平台)
        if not 账号记录:
            配置Cookie = _读取平台配置Cookie(配置, 规范平台)
            配置结果 = 解析网盘Cookie(f"{规范平台} Cookie: {配置Cookie or ''}")
            if 配置结果 and 配置结果[0] == 规范平台 and 配置结果[1]:
                账号记录.append(
                    {
                        "cookie": 配置结果[1],
                        "identity": _获取网盘Cookie身份键(规范平台, 配置结果[1]),
                        "name": "",
                        "phone": "",
                    }
                )
        if 新身份键:
            for 位置, 已保存记录 in enumerate(账号记录):
                if (
                    已保存记录.get("identity")
                    or _获取网盘Cookie身份键(
                        规范平台, 已保存记录.get("cookie", "")
                    )
                ) != 新身份键:
                    continue
                已保存记录["cookie"] = Cookie
                已保存记录["identity"] = 新身份键
                if 新名称:
                    已保存记录["name"] = 新名称
                if 新手机号:
                    已保存记录["phone"] = 新手机号
                _写入网盘账号记录(配置, 规范平台, 账号记录)
                return 位置 + 1
        已有位置 = next(
            (
                位置
                for 位置, 已保存记录 in enumerate(账号记录)
                if 已保存记录.get("cookie") == Cookie
            ),
            None,
        )
        if 已有位置 is not None:
            if 新名称:
                账号记录[已有位置]["name"] = 新名称
            if 新手机号:
                账号记录[已有位置]["phone"] = 新手机号
            _写入网盘账号记录(配置, 规范平台, 账号记录)
            return 已有位置 + 1
        账号记录.append(
            {
                "cookie": Cookie,
                "identity": 新身份键,
                "name": 新名称,
                "phone": 新手机号,
            }
        )
        _写入网盘账号记录(配置, 规范平台, 账号记录)
        return len(账号记录)


def _查找网盘配置账号身份(配置: Any, 平台: str) -> tuple[str, str]:
    配置Cookie = _读取平台配置Cookie(配置, 平台)
    解析结果 = 解析网盘Cookie(f"{平台} Cookie: {配置Cookie or ''}")
    if not 解析结果 or not 解析结果[1]:
        return "", ""
    Cookie = 解析结果[1]
    return Cookie, _获取网盘Cookie身份键(平台, Cookie)


def _删除后调整网盘账号选择(
    配置: Any, 平台: str, 删除序号: int, 新账号数量: int
) -> None:
    if not 已配置运行状态数据库(配置):
        return
    try:
        状态字典 = 读取运行状态命名空间(配置, 网盘账号选择命名空间)
        前缀 = f"{平台}:"
        for 状态键, 原值 in 状态字典.items():
            if not str(状态键).startswith(前缀):
                continue
            try:
                原序号 = int(str(原值 or "1"))
            except (TypeError, ValueError):
                continue
            if 原序号 > 删除序号:
                新序号 = 原序号 - 1
            elif 原序号 == 删除序号:
                新序号 = min(删除序号, 新账号数量)
            else:
                continue
            写入运行状态值(配置, 网盘账号选择命名空间, str(状态键), str(max(1, 新序号)))
    except Exception as 异常:
        logger.warning(
            f"{平台显示名[平台]}账号选择整理失败：error={type(异常).__name__}"
        )


def _删除网盘账号(配置: Any, 平台: str, 序号: int) -> tuple[bool, str]:
    规范平台 = _规范化平台名称(平台)
    if not 规范平台:
        return False, "网盘账号不存在"
    if not 已配置运行状态数据库(配置):
        return False, "数据库未配置，网盘账号未保存"
    with 网盘账号写入锁:
        账号记录 = _读取保存的网盘账号记录(配置, 规范平台)
        if 序号 < 1 or 序号 > len(账号记录):
            return False, f"{平台显示名[规范平台]}只有{len(账号记录)}个账号"
        if len(账号记录) <= 1:
            return False, "至少要保留一个夸克账号"
        当前Cookie = str(账号记录[序号 - 1].get("cookie") or "")
        配置Cookie, 配置身份 = _查找网盘配置账号身份(配置, 规范平台)
        当前身份 = str(账号记录[序号 - 1].get("identity") or "")
        if (配置Cookie and 当前Cookie == 配置Cookie) or (
            配置身份 and 当前身份 == 配置身份
        ):
            return False, "插件配置中的账号1不能删除，请先修改夸克Cookie配置"
        账号记录.pop(序号 - 1)
        _写入网盘账号记录(配置, 规范平台, 账号记录)
        _删除后调整网盘账号选择(配置, 规范平台, 序号, len(账号记录))
    return True, ""


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


def _网盘账号摘要(账号记录: list[dict[str, str]]) -> list[dict[str, Any]]:
    摘要列表: list[dict[str, Any]] = []
    for 序号, 记录 in enumerate(账号记录, start=1):
        if not str(记录.get("cookie") or "").strip():
            continue
        摘要列表.append(
            {
                "index": 序号,
                "name": _清理账号资料文本(记录.get("name")) or "未命名账号",
                "phone": _脱敏手机号(记录.get("phone")) or "未获取",
                "configured": True,
            }
        )
    return 摘要列表


def 获取网盘账号摘要批量(
    配置: Any, 平台列表: tuple[str, ...] = ("UC", "夸克", "百度")
) -> dict[str, list[dict[str, Any]]]:
    """一次读取网盘账号命名空间，供控制台批量展示账号摘要。"""
    规范平台列表: list[str] = []
    for 平台 in 平台列表:
        规范平台 = _规范化平台名称(平台)
        if 规范平台 and 规范平台 not in 规范平台列表:
            规范平台列表.append(规范平台)
    if not 规范平台列表:
        return {}
    状态字典: dict[str, str] = {}
    if 已配置运行状态数据库(配置):
        try:
            状态字典 = 读取运行状态命名空间(配置, 网盘Cookie命名空间)
        except Exception as 异常:
            logger.warning(
                "网盘账号批量读取失败：error=%s", type(异常).__name__
            )
    结果: dict[str, list[dict[str, Any]]] = {}
    for 平台 in 规范平台列表:
        账号记录 = _解析保存的网盘账号记录(
            状态字典.get(平台状态键[平台], ""), 平台
        )
        账号记录 = _合并配置网盘账号记录(配置, 平台, 账号记录)
        结果[平台] = _网盘账号摘要(账号记录)
    return 结果


def 获取网盘账号摘要(配置: Any, 平台: str) -> list[dict[str, Any]]:
    """返回控制台可展示的账号摘要，不返回 Cookie 或身份令牌。"""
    规范平台 = _规范化平台名称(平台)
    if not 规范平台:
        return []
    try:
        账号记录 = _读取保存的网盘账号记录(配置, 规范平台)
    except Exception as 异常:
        logger.warning(
            f"{平台显示名.get(规范平台, 规范平台)}账号摘要读取失败：error={type(异常).__name__}"
        )
        账号记录 = []
    return _网盘账号摘要(账号记录)


async def _获取夸克账号资料(Cookie: str) -> tuple[str, str]:
    if not Cookie:
        return "", ""
    try:
        Timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(
            timeout=Timeout,
            headers={
                "accept": "application/json, text/plain, */*",
                "referer": "https://pan.quark.cn/",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/150.0.0.0 Safari/537.36"
                ),
                "Cookie": Cookie,
            },
        ) as 会话:
            async with 会话.get(
                夸克账号资料地址,
                params={"lw": "scan", "fr": "pc", "platform": "pc"},
            ) as 响应:
                数据 = await 响应.json(content_type=None)
                if 响应.status != 200:
                    return "", ""
        return _解析夸克账号资料(数据)
    except Exception as 异常:
        logger.warning(
            "夸克账号资料读取失败：stage=profile, error=%s",
            type(异常).__name__,
        )
        return "", ""


async def _刷新夸克账号资料(配置: Any) -> list[dict[str, str]]:
    账号记录 = await asyncio.to_thread(_读取保存的网盘账号记录, 配置, "夸克")
    if not 账号记录:
        配置Cookie, 配置身份 = _查找网盘配置账号身份(配置, "夸克")
        if 配置Cookie:
            账号记录 = [
                {
                    "cookie": 配置Cookie,
                    "identity": 配置身份,
                    "name": "",
                    "phone": "",
                }
            ]
    if not 账号记录:
        return []
    信号量 = asyncio.Semaphore(4)

    async def 刷新单个账号(记录: dict[str, str]) -> bool:
        if 记录.get("name") and 记录.get("phone"):
            return False
        async with 信号量:
            名称, 手机号 = await _获取夸克账号资料(
                str(记录.get("cookie") or "")
            )
        已变更 = False
        if 名称 and 名称 != 记录.get("name"):
            记录["name"] = 名称
            已变更 = True
        if 手机号 and 手机号 != 记录.get("phone"):
            记录["phone"] = 手机号
            已变更 = True
        return 已变更

    更新结果 = await asyncio.gather(
        *(刷新单个账号(记录) for 记录 in 账号记录),
        return_exceptions=True,
    )
    已更新 = any(结果 is True for 结果 in 更新结果)
    if 已更新:
        await asyncio.to_thread(_写入网盘账号记录, 配置, "夸克", 账号记录)
    return 账号记录


def _格式化夸克账号列表(
    配置: Any, event: Any, 账号记录: list[dict[str, str]]
) -> str:
    当前序号 = min(
        _读取网盘账号序号(配置, "夸克", event),
        len(账号记录),
    )
    行列表 = [f"夸克账号共{len(账号记录)}个"]
    for index, 记录 in enumerate(账号记录, start=1):
        名称 = 记录.get("name") or "未获取"
        手机号 = 记录.get("phone") or "未获取"
        当前标记 = "（当前）" if index == 当前序号 else ""
        行列表.append(
            f"账号{index}：名称={名称}，手机号={手机号}{当前标记}"
        )
    return "\n".join(行列表)


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


def 设置网盘账号序号按群标识(
    配置: Any, 平台: str, 序号: int, 群标识: str
) -> tuple[bool, str]:
    """供管理后台使用的群账号选择入口，不依赖伪造事件对象。"""
    规范平台 = _规范化平台名称(平台)
    群标识 = str(群标识 or "").strip()
    if not 规范平台 or not 群标识:
        return False, "群账号参数无效"
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
        名称, 手机号 = await _获取夸克账号资料(Cookie)
        账号序号 = await asyncio.to_thread(
            _保存网盘Cookie,
            配置,
            "夸克",
            Cookie,
            名称=名称,
            手机号=手机号,
        )
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
    删除匹配 = 夸克账号删除模式.fullmatch(文本)
    if 文本 in 夸克账号查看命令:
        if not 是群文件清理管理员(event, 配置):
            return ""
        if _事件位于群聊(event):
            return "请私聊机器人查看夸克账号"
        if not 已配置运行状态数据库(配置):
            return "数据库未配置，夸克账号未保存"
        账号记录 = await _刷新夸克账号资料(配置)
        if not 账号记录:
            return "暂未保存夸克账号"
        return _格式化夸克账号列表(配置, event, 账号记录)
    if 删除匹配 is not None:
        if not 是群文件清理管理员(event, 配置):
            return ""
        if _事件位于群聊(event):
            return "请私聊机器人删除夸克账号"
        try:
            序号 = int(删除匹配.group(1))
        except (TypeError, ValueError):
            return "夸克账号序号无效"
        成功, 错误 = await asyncio.to_thread(_删除网盘账号, 配置, "夸克", 序号)
        if not 成功:
            return 错误
        return f"已删除夸克账号{序号}"
    if 文本 in 夸克账号添加命令:
        if not 是群文件清理管理员(event, 配置):
            return ""
        if _事件位于群聊(event):
            return "请私聊机器人添加夸克账号"
        return "请发送夸克Cookie，或发送夸克登录扫码添加账号"
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
        资料名称 = ""
        资料手机号 = ""
        if 平台 == "夸克":
            资料名称, 资料手机号 = await _获取夸克账号资料(Cookie)
        账号序号 = await asyncio.to_thread(
            _保存网盘Cookie,
            配置,
            平台,
            Cookie,
            名称=资料名称,
            手机号=资料手机号,
        )
    except Exception as 异常:
        logger.warning(f"{显示名}Cookie保存失败：error={type(异常).__name__}")
        return f"{显示名}Cookie保存失败，请稍后再试"
    return f"{显示名}Cookie已保存为账号{账号序号}"
