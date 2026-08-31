from __future__ import annotations

import asyncio
import base64
from datetime import date
import hashlib
import json
import mimetypes
import re
import time
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path
from typing import Any

import aiohttp
from astrbot.api import logger

from 功能文件.管理功能.网盘功能.网盘Cookie import (
    持久化刷新后的网盘Cookie,
    读取网盘Cookie,
)
from 功能文件.管理功能.网盘功能 import 网盘状态
from 功能文件.管理功能.网盘功能 import 网盘清理工具

基础接口地址 = "https://drive-pc.quark.cn/1/clouddrive"
默认上传目录 = "/小说机器人"
PDS_ID = "ccp-sz3-zjk-1609940055"
目录列表每页数量 = 200
目录列表最大页数 = 20
文件可见重试次数 = 12
分享链接重试次数 = 12
浏览器请求头 = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
    "origin": "https://pan.quark.cn",
    "referer": "https://pan.quark.cn/",
}


class 夸克网盘客户端:
    def __init__(self, cookie: str):
        self.cookie = 清理Cookie(cookie)
        self.session: aiohttp.ClientSession | None = None
        self.服务器时间偏移秒 = 0.0

    async def __aenter__(self) -> "夸克网盘客户端":
        await self.初始化()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.关闭()

    async def 初始化(self) -> None:
        await self.关闭()
        请求头 = dict(浏览器请求头)
        请求头["cookie"] = self.cookie
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=120),
            headers=请求头,
        )

    async def 关闭(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def 上传文件并创建分享(
        self, 本地路径: str | Path, 文件名: str, 上传目录: str
    ) -> str:
        目录ID = await self.确保目录路径(上传目录)
        await self.删除同名普通文件(文件名, 目录ID)
        文件ID = await self.上传文件(本地路径, 目录ID, 文件名)
        if not 文件ID:
            raise RuntimeError("夸克网盘上传后没有返回文件ID")
        分享链接 = await self.创建分享(文件ID, 文件名)
        if not 分享链接:
            raise RuntimeError("夸克网盘没有返回分享链接")
        return 分享链接

    async def 确保目录路径(self, 上传目录: str) -> str:
        当前目录ID = "0"
        for 目录名 in 拆分上传目录(上传目录):
            当前目录ID = await self.确保文件夹(目录名, 当前目录ID)
        return 当前目录ID

    async def 确保文件夹(self, 目录名: str, 父目录ID: str) -> str:
        已有ID = await self.查找文件夹ID(目录名, 父目录ID)
        if 已有ID:
            return 已有ID
        数据 = await self.请求JSON(
            "POST",
            "/file",
            json_data={
                "pdir_fid": str(父目录ID),
                "file_name": 目录名,
                "dir_path": "",
                "dir_init_lock": False,
            },
        )
        if not 接口成功(数据):
            raise RuntimeError(f"夸克网盘创建目录失败：{限制文本长度(数据)}")
        文件ID = 读取文件ID(数据.get("data"))
        if 文件ID:
            return 文件ID
        for 尝试次数 in range(1, 文件可见重试次数 + 1):
            await asyncio.sleep(计算等待秒数(尝试次数))
            文件ID = await self.查找文件夹ID(目录名, 父目录ID)
            if 文件ID:
                return 文件ID
        raise RuntimeError("夸克网盘创建目录后没有返回文件ID")

    async def 查找文件夹ID(self, 目录名: str, 父目录ID: str) -> str:
        for 项目 in await self.列出目录全部项目(父目录ID):
            if 是文件夹项目(项目) and 读取文件名(项目) == 目录名:
                return 读取文件ID(项目)
        return ""

    async def 删除文件ID列表(self, 文件ID列表: list[str]) -> int:
        去重ID = list(dict.fromkeys(str(值).strip() for 值 in 文件ID列表 if str(值).strip()))
        if not 去重ID:
            return 0
        数据 = await self.请求JSON(
            "POST",
            "/file/delete",
            json_data={"action_type": 2, "filelist": 去重ID, "exclude_fids": []},
        )
        if not 接口成功(数据):
            raise RuntimeError(f"夸克网盘删除文件失败：{限制文本长度(数据)}")
        返回数据 = 数据.get("data") if isinstance(数据.get("data"), dict) else {}
        任务ID = str(返回数据.get("task_id") or "")
        if 任务ID:
            任务数据 = await self.轮询任务(任务ID)
            任务结果 = (
                任务数据.get("data") if isinstance(任务数据.get("data"), dict) else {}
            )
            if 安全整数(任务结果.get("status"), -1) != 2:
                raise RuntimeError("夸克网盘删除文件任务未完成")
        return len(去重ID)

    async def 删除同名普通文件(self, 文件名: str, 父目录ID: str) -> None:
        文件ID列表 = [
            读取文件ID(项目)
            for 项目 in await self.列出目录全部项目(父目录ID)
            if not 是文件夹项目(项目)
            and 读取文件名(项目) == 文件名
            and 读取文件ID(项目)
        ]
        if not 文件ID列表:
            return
        try:
            await self.删除文件ID列表(文件ID列表)
        except Exception as 异常:
            raise RuntimeError(
                f"夸克网盘删除同名旧文件失败：错误类型={type(异常).__name__}"
            ) from 异常
        logger.debug(
            f"夸克网盘上传前已删除同名旧文件：file={文件名}, count={len(文件ID列表)}"
        )

    async def 清理早于当天小说(
        self, 上传目录: str, 当前日期: date | None = None
    ) -> int:
        """删除上传目录中前两天及更早的小说 TXT，不删除文件夹。"""
        目录ID = await self.确保目录路径(上传目录)
        待删除: list[str] = []
        for 项目 in await self.列出目录全部项目(目录ID):
            if not isinstance(项目, dict) or 是文件夹项目(项目):
                continue
            if not 网盘清理工具.是应清理的小说(项目, 当前日期, 保留天数=2):
                continue
            文件ID = 读取文件ID(项目)
            if 文件ID and 文件ID not in 待删除:
                待删除.append(文件ID)
        return await self.删除文件ID列表(待删除)

    async def 列出目录全部项目(self, 父目录ID: str) -> list[dict[str, Any]]:
        结果: list[dict[str, Any]] = []
        for 页码 in range(1, 目录列表最大页数 + 1):
            数据 = await self.请求JSON(
                "GET",
                "/file/sort",
                params={
                    "pdir_fid": str(父目录ID),
                    "_page": 页码,
                    "_size": 目录列表每页数量,
                    "_fetch_total": 1,
                    "_fetch_sub_dirs": 0,
                    "_sort": "file_type:asc,updated_at:desc",
                    "fetch_all_file": 1,
                    "fetch_risk_file_name": 1,
                },
            )
            if not 接口成功(数据):
                raise RuntimeError(f"夸克网盘目录列表获取失败：{限制文本长度(数据)}")
            项目列表 = 读取列表(数据, ("data", "list"))
            结果.extend(项目 for 项目 in 项目列表 if isinstance(项目, dict))
            if len(项目列表) < 目录列表每页数量:
                break
        return 结果

    async def 上传文件(self, 本地路径: str | Path, 父目录ID: str, 文件名: str) -> str:
        路径 = Path(本地路径)
        if not 路径.is_file():
            raise RuntimeError("夸克网盘上传文件不存在")
        MD5, SHA1 = 计算文件哈希(路径)
        文件大小 = 路径.stat().st_size
        文件状态 = 路径.stat()
        内容类型 = mimetypes.guess_type(文件名)[0] or "application/octet-stream"
        预上传数据 = await self.请求JSON(
            "POST",
            "/file/upload/pre",
            json_data={
                "ccp_hash_update": True,
                "parallel_upload": True,
                "pdir_fid": str(父目录ID),
                "dir_name": "",
                "size": 文件大小,
                "file_name": 文件名,
                "format_type": 内容类型,
                "l_updated_at": int(文件状态.st_mtime * 1000),
                "l_created_at": int(文件状态.st_ctime * 1000),
            },
        )
        if not 接口成功(预上传数据):
            raise RuntimeError(f"夸克网盘预上传失败：{限制文本长度(预上传数据)}")
        上传参数 = (
            预上传数据.get("data") if isinstance(预上传数据.get("data"), dict) else {}
        )
        任务ID = str(上传参数.get("task_id") or "")
        对象键 = str(上传参数.get("obj_key") or "")
        存储桶 = str(上传参数.get("bucket") or "")
        上传ID = str(上传参数.get("upload_id") or "")
        if not all((任务ID, 对象键, 存储桶, 上传ID)):
            raise RuntimeError(f"夸克网盘预上传参数不完整：{限制文本长度(预上传数据)}")

        秒传数据 = await self.请求JSON(
            "POST",
            "/file/update/hash",
            json_data={"task_id": 任务ID, "md5": MD5, "sha1": SHA1},
        )
        秒传结果 = (
            秒传数据.get("data") if isinstance(秒传数据.get("data"), dict) else {}
        )
        if 接口成功(秒传数据) and 解析布尔值(秒传结果.get("finish")):
            文件ID = 读取文件ID(秒传结果)
            return 文件ID or await self.等待文件可见(文件名, 父目录ID, 文件大小)

        ETag = await self.上传OSS单分片(路径, MD5, 上传参数)
        await self.完成OSS单分片(ETag, 上传参数)
        完成数据 = await self.请求JSON(
            "POST",
            "/file/upload/finish",
            json_data={"task_id": 任务ID, "obj_key": 对象键},
        )
        if not 接口成功(完成数据):
            raise RuntimeError(f"夸克网盘完成上传失败：{限制文本长度(完成数据)}")
        文件ID = 读取文件ID(完成数据.get("data"))
        return 文件ID or await self.等待文件可见(文件名, 父目录ID, 文件大小)

    async def 上传OSS单分片(
        self, 路径: Path, MD5: str, 上传参数: dict[str, Any]
    ) -> str:
        存储桶 = str(上传参数.get("bucket") or "")
        对象键 = str(上传参数.get("obj_key") or "")
        上传ID = str(上传参数.get("upload_id") or "")
        PDS编号 = str(上传参数.get("pds_id") or PDS_ID)
        OSS用户代理 = "aliyun-sdk-js/1.0.0 Chrome 150.0.0.0 on Windows 10 64-bit"
        内容类型 = mimetypes.guess_type(路径.name)[0] or "application/octet-stream"
        地址 = f"https://{存储桶}.pds.quark.cn/{对象键}?partNumber=1&uploadId={上传ID}"
        for 尝试次数 in range(2):
            当前时间 = self.获取OSS时间()
            鉴权元数据 = (
                f"PUT\n\n{内容类型}\n{当前时间}\n"
                f"x-oss-date:{当前时间}\n"
                f"x-oss-user-agent:{OSS用户代理}\n"
                f"/{PDS编号}/{存储桶}/{对象键}?partNumber=1&uploadId={上传ID}"
            )
            鉴权键 = await self.获取上传鉴权(上传参数, 鉴权元数据)
            请求头 = {
                "authorization": 鉴权键,
                "x-oss-date": 当前时间,
                "x-oss-user-agent": OSS用户代理,
                "content-type": 内容类型,
            }
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=300)
            ) as 会话:
                with 路径.open("rb") as 文件:
                    async with 会话.put(地址, data=文件, headers=请求头) as 响应:
                        响应文本 = await 响应.text()
                        if 响应.status in (200, 201):
                            return 提取ETag(响应.headers) or MD5
                        if 尝试次数 == 0 and 响应.status == 403 and "requesttimeskewed" in 响应文本.lower():
                            self.同步服务器时间(响应.headers)
                            continue
                        raise RuntimeError(
                            f"夸克网盘OSS上传失败：HTTP {响应.status}: {限制文本长度(响应文本, 200)}"
                        )
        raise RuntimeError("夸克网盘OSS上传失败：时间校准后仍未成功")

    async def 完成OSS单分片(self, ETag: str, 上传参数: dict[str, Any]) -> None:
        存储桶 = str(上传参数.get("bucket") or "")
        对象键 = str(上传参数.get("obj_key") or "")
        上传ID = str(上传参数.get("upload_id") or "")
        PDS编号 = str(上传参数.get("pds_id") or PDS_ID)
        OSS用户代理 = "aliyun-sdk-js/1.0.0 Chrome 150.0.0.0 on Windows 10 64-bit"
        回调文本 = 规范化回调文本(上传参数.get("callback"))
        回调编码 = base64.b64encode(回调文本.encode("utf-8")).decode("ascii")
        规范ETag = str(ETag or "").strip().strip('"')
        if re.fullmatch(r"[0-9a-fA-F]{32}", 规范ETag):
            规范ETag = 规范ETag.upper()
        XML正文 = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<CompleteMultipartUpload>\n"
            "<Part>\n"
            "<PartNumber>1</PartNumber>\n"
            f'<ETag>"{规范ETag}"</ETag>\n'
            "</Part>\n"
            "</CompleteMultipartUpload>"
        )
        XML字节 = XML正文.encode("utf-8")
        内容MD5 = base64.b64encode(hashlib.md5(XML字节).digest()).decode("ascii")
        地址 = f"https://{存储桶}.pds.quark.cn/{对象键}?uploadId={上传ID}"
        for 尝试次数 in range(2):
            当前时间 = self.获取OSS时间()
            鉴权元数据 = (
                f"POST\n{内容MD5}\napplication/xml\n{当前时间}\n"
                f"x-oss-callback:{回调编码}\n"
                f"x-oss-date:{当前时间}\n"
                f"x-oss-user-agent:{OSS用户代理}\n"
                f"/{PDS编号}/{存储桶}/{对象键}?uploadId={上传ID}"
            )
            鉴权键 = await self.获取上传鉴权(上传参数, 鉴权元数据)
            请求头 = {
                "authorization": 鉴权键,
                "content-md5": 内容MD5,
                "content-type": "application/xml",
                "x-oss-date": 当前时间,
                "x-oss-user-agent": OSS用户代理,
                "x-oss-callback": 回调编码,
            }
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=120),
            ) as 会话:
                async with 会话.post(地址, data=XML字节, headers=请求头) as 响应:
                    响应文本 = await 响应.text()
                    if 响应.status == 203 and "CallbackFailed" in 响应文本:
                        logger.warning(
                            "夸克网盘OSS合并分片回调未确认，继续请求上传完成：status=%s",
                            响应.status,
                        )
                        return
                    if 响应.status in (200, 201):
                        return
                    if 尝试次数 == 0 and 响应.status == 403 and "requesttimeskewed" in 响应文本.lower():
                        self.同步服务器时间(响应.headers)
                        continue
                    raise RuntimeError(
                        f"夸克网盘合并分片失败：HTTP {响应.status}: {限制文本长度(响应文本, 200)}"
                    )
        raise RuntimeError("夸克网盘OSS合并分片失败：时间校准后仍未成功")

    async def 获取上传鉴权(self, 上传参数: dict[str, Any], 鉴权元数据: str) -> str:
        数据 = await self.请求JSON(
            "POST",
            "/file/upload/auth",
            json_data={
                "task_id": 上传参数.get("task_id"),
                "auth_info": 上传参数.get("auth_info"),
                "auth_meta": 鉴权元数据,
                "callback_meta": 上传参数.get("callback"),
            },
        )
        if not 接口成功(数据):
            raise RuntimeError(f"夸克网盘上传鉴权失败：{限制文本长度(数据)}")
        鉴权键 = str((数据.get("data") or {}).get("auth_key") or "")
        if not 鉴权键:
            raise RuntimeError("夸克网盘上传鉴权没有返回 auth_key")
        return 鉴权键

    async def 等待文件可见(self, 文件名: str, 父目录ID: str, 文件大小: int) -> str:
        for 尝试次数 in range(1, 文件可见重试次数 + 1):
            for 项目 in await self.列出目录全部项目(父目录ID):
                if 是文件夹项目(项目) or 读取文件名(项目) != 文件名:
                    continue
                if 文件大小匹配(项目, 文件大小):
                    文件ID = 读取文件ID(项目)
                    if 文件ID:
                        return 文件ID
            await asyncio.sleep(计算等待秒数(尝试次数))
        return ""

    async def 创建分享(self, 文件ID: str, 文件名: str) -> str:
        数据 = await self.请求JSON(
            "POST",
            "/share",
            params={"uc_param_str": ""},
            json_data={
                "fid_list": [文件ID],
                "title": 文件名,
                "url_type": 1,
                "expired_type": 1,
            },
        )
        if not 接口成功(数据):
            raise RuntimeError(f"夸克网盘创建分享失败：{限制文本长度(数据)}")
        直接链接 = 提取分享链接(数据)
        if 直接链接:
            return 直接链接
        返回数据 = 数据.get("data") if isinstance(数据.get("data"), dict) else {}
        分享ID = str(返回数据.get("share_id") or "")
        任务ID = str(返回数据.get("task_id") or "")
        if 任务ID:
            任务数据 = await self.轮询任务(任务ID)
            直接链接 = 提取分享链接(任务数据)
            if 直接链接:
                return 直接链接
            任务结果 = (
                任务数据.get("data") if isinstance(任务数据.get("data"), dict) else {}
            )
            分享ID = str(任务结果.get("share_id") or 分享ID)
        分享链接 = await self.等待分享短链接(分享ID, 文件ID)
        if 分享链接:
            return 分享链接
        if 分享ID:
            密码数据 = await self.请求JSON(
                "POST", "/share/password", json_data={"share_id": 分享ID}
            )
            return 提取分享链接(密码数据)
        return ""

    async def 轮询任务(self, 任务ID: str) -> dict[str, Any]:
        最后数据: dict[str, Any] = {}
        for 尝试次数 in range(分享链接重试次数):
            最后数据 = await self.请求JSON(
                "GET",
                "/task",
                params={"task_id": 任务ID, "retry_index": 尝试次数},
            )
            任务数据 = (
                最后数据.get("data") if isinstance(最后数据.get("data"), dict) else {}
            )
            if 安全整数(任务数据.get("status"), -1) == 2:
                return 最后数据
            await asyncio.sleep(1)
        return 最后数据

    async def 等待分享短链接(self, 分享ID: str, 文件ID: str) -> str:
        for 尝试次数 in range(1, 分享链接重试次数 + 1):
            数据 = await self.请求JSON(
                "GET",
                "/share/mypage/detail",
                params={
                    "_page": 1,
                    "_size": 50,
                    "_order_field": "created_at",
                    "_order_type": "desc",
                    "_fetch_total": 1,
                    "_fetch_notify_follow": 1,
                },
            )
            if 接口成功(数据):
                for 项目 in 读取列表(数据, ("data", "list")):
                    if not isinstance(项目, dict):
                        continue
                    当前分享ID = str(项目.get("share_id") or "")
                    首文件ID = str(项目.get("first_fid") or "")
                    文件ID列表 = {str(值) for 值 in (项目.get("fid_list") or [])}
                    if (
                        (分享ID and 当前分享ID == 分享ID)
                        or 文件ID == 首文件ID
                        or 文件ID in 文件ID列表
                    ):
                        链接 = 提取分享链接(项目)
                        if 链接:
                            return 链接
            await asyncio.sleep(计算等待秒数(尝试次数))
        return ""

    def 同步服务器时间(self, 响应头: Any) -> None:
        """按夸克/OSS Date 响应头校准本次上传会话的签名时间。"""
        try:
            日期文本 = str(响应头.get("Date") or "").strip()
            if not 日期文本:
                return
            服务器时间 = parsedate_to_datetime(日期文本).timestamp()
            偏移 = 服务器时间 - time.time()
            if abs(偏移) <= 365 * 24 * 60 * 60:
                self.服务器时间偏移秒 = 偏移
        except (AttributeError, TypeError, ValueError, OverflowError):
            return

    def 获取OSS时间(self) -> str:
        return formatdate(
            timeval=time.time() + float(self.服务器时间偏移秒 or 0),
            usegmt=True,
        )

    async def 请求JSON(
        self,
        方法: str,
        路径: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        会话 = self.获取会话()
        请求参数 = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        请求参数.update(params or {})
        地址 = 路径 if 路径.startswith("http") else f"{基础接口地址}{路径}"
        async with 会话.request(方法, 地址, params=请求参数, json=json_data) as 响应:
            self.同步服务器时间(响应.headers)
            文本 = await 响应.text()
            self.刷新会话Cookie(响应)
            if 响应.status >= 400:
                raise RuntimeError(
                    f"夸克网盘HTTP {响应.status}：{限制文本长度(文本, 200)}"
                )
            try:
                数据 = json.loads(文本)
            except Exception as 异常:
                raise RuntimeError(
                    f"夸克网盘JSON解析失败：{限制文本长度(文本, 200)}"
                ) from 异常
            if not isinstance(数据, dict):
                raise RuntimeError("夸克网盘返回格式不是对象")
            return 数据

    def 刷新会话Cookie(self, 响应: aiohttp.ClientResponse) -> None:
        已更新 = False
        for 名称 in ("__puus",):
            新值 = 响应.cookies.get(名称)
            if not 新值:
                continue
            值 = str(getattr(新值, "value", 新值) or "").strip()
            if not 值:
                continue
            self.cookie = 更新Cookie字段(self.cookie, 名称, 值)
            已更新 = True
        if 已更新:
            self.获取会话().headers["cookie"] = self.cookie

    def 获取会话(self) -> aiohttp.ClientSession:
        if self.session is None:
            raise RuntimeError("夸克网盘客户端未初始化")
        return self.session


async def 上传小说并获取分享链接(
    配置: Any, 源缓存路径: str | Path, 文件名: str
) -> dict[str, Any]:
    if not 夸克网盘是否启用(配置):
        return {
            "enabled": False,
            "success": False,
            "share_url": "",
            "provider": "夸克网盘",
            "error": "",
        }
    路径 = Path(源缓存路径)
    if not 路径.is_file():
        logger.warning(f"夸克网盘上传分享失败：file={文件名}, error=本地文件不存在")
        return {
            "enabled": True,
            "success": False,
            "share_url": "",
            "provider": "夸克网盘",
            "error": "本地文件不存在",
        }
    Cookie = 读取夸克网盘Cookie(配置)
    客户端 = 夸克网盘客户端(Cookie)
    try:
        async with 客户端:
            分享链接 = await 客户端.上传文件并创建分享(
                路径, 文件名, 读取夸克上传目录(配置)
            )
        return {
            "enabled": True,
            "success": True,
            "share_url": 分享链接,
            "provider": "夸克网盘",
            "error": "",
        }
    except Exception as 异常:
        logger.warning(f"夸克网盘上传分享失败：file={文件名}, error={异常}")
        return {
            "enabled": True,
            "success": False,
            "share_url": "",
            "provider": "夸克网盘",
            "error": str(异常),
        }
    finally:
        await asyncio.to_thread(
            持久化刷新后的网盘Cookie, 配置, "夸克", Cookie, 客户端.cookie
        )


def 夸克网盘是否启用(配置: Any) -> bool:
    return 网盘状态.网盘开关是否开启(配置, "夸克") and bool(读取夸克网盘Cookie(配置))


def 读取夸克网盘Cookie(配置: Any) -> str:
    配置Cookie = 清理Cookie(读取配置字段(配置, "quark_pan_cookie") or "")
    return 读取网盘Cookie(配置, "夸克", 配置Cookie)


def 读取夸克上传目录(配置: Any) -> str:
    return (
        str(读取配置字段(配置, "quark_pan_upload_dir") or 默认上传目录).strip()
        or 默认上传目录
    )


def 读取配置字段(配置: Any, 字段名: str) -> Any:
    if 配置 is None:
        return None
    if isinstance(配置, dict):
        if 字段名 in 配置:
            return 配置.get(字段名)
        分类 = 配置.get("quark_pan_settings") or 配置.get("夸克网盘设置")
        return 分类.get(字段名) if isinstance(分类, dict) else None
    获取配置方法 = getattr(配置, "get_config", None)
    if callable(获取配置方法):
        try:
            值 = 读取配置字段(获取配置方法(), 字段名)
            if 值 is not None:
                return 值
        except Exception:
            pass
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            值 = 获取方法(字段名)
            if 值 is not None:
                return 值
            分类 = 获取方法("quark_pan_settings")
            if isinstance(分类, dict):
                return 分类.get(字段名)
        except Exception:
            pass
    值 = getattr(配置, 字段名, None)
    if 值 is not None:
        return 值
    分类 = getattr(配置, "quark_pan_settings", None)
    return getattr(分类, 字段名, None) if 分类 is not None else None


def 计算文件哈希(路径: Path) -> tuple[str, str]:
    MD5 = hashlib.md5()
    SHA1 = hashlib.sha1()
    with 路径.open("rb") as 文件:
        while True:
            数据 = 文件.read(1024 * 1024)
            if not 数据:
                break
            MD5.update(数据)
            SHA1.update(数据)
    return MD5.hexdigest().lower(), SHA1.hexdigest().lower()


def 拆分上传目录(上传目录: str) -> list[str]:
    return [
        片段.strip()
        for 片段 in str(上传目录 or 默认上传目录).replace("\\", "/").split("/")
        if 片段.strip()
    ]


def 接口成功(数据: Any) -> bool:
    if not isinstance(数据, dict):
        return False
    状态 = 数据.get("status")
    错误码 = 数据.get("code")
    return 状态 in (None, 200, "200") and 错误码 in (None, 0, "0")


def 提取分享链接(数据: Any) -> str:
    if isinstance(数据, dict):
        for 字段名 in ("share_url", "url"):
            值 = str(数据.get(字段名) or "").strip()
            if re.match(r"^https?://pan\.quark\.cn/", 值, re.I):
                return 值
        for 值 in 数据.values():
            链接 = 提取分享链接(值)
            if 链接:
                return 链接
    elif isinstance(数据, list):
        for 值 in 数据:
            链接 = 提取分享链接(值)
            if 链接:
                return 链接
    return ""


def 读取列表(数据: Any, 路径: tuple[str, ...]) -> list[Any]:
    当前 = 数据
    for 字段名 in 路径:
        if not isinstance(当前, dict):
            return []
        当前 = 当前.get(字段名)
    return 当前 if isinstance(当前, list) else []


def 读取文件ID(数据: Any) -> str:
    if not isinstance(数据, dict):
        return ""
    for 字段名 in ("fid", "file_id", "fileId", "id"):
        值 = 数据.get(字段名)
        if 值 not in (None, ""):
            return str(值)
    for 字段名 in ("file", "item"):
        文件ID = 读取文件ID(数据.get(字段名))
        if 文件ID:
            return 文件ID
    return ""


def 读取文件名(项目: dict[str, Any]) -> str:
    return str(项目.get("file_name") or 项目.get("fileName") or 项目.get("name") or "")


def 是文件夹项目(项目: dict[str, Any]) -> bool:
    return 解析布尔值(项目.get("dir") if "dir" in 项目 else 项目.get("is_dir"))


def 文件大小匹配(项目: dict[str, Any], 文件大小: int) -> bool:
    for 字段名 in ("size", "file_size", "file_size_int", "length"):
        if 项目.get(字段名) not in (None, ""):
            return 安全整数(项目.get(字段名), -1) == 文件大小
    return True


def 解析布尔值(值: Any) -> bool:
    if isinstance(值, str):
        return 值.strip().lower() in {"1", "true", "yes", "on"}
    return bool(值)


def 安全整数(值: Any, 默认值: int = 0) -> int:
    try:
        return int(值)
    except Exception:
        return 默认值


def 清理Cookie(cookie: Any) -> str:
    文本 = str(cookie or "").strip()
    if 文本.startswith("夸克网盘#"):
        文本 = 文本.split("#", 1)[1].strip()
    if 文本.lower().startswith("cookie:"):
        文本 = 文本.split(":", 1)[1].strip()
    return 文本


def 更新Cookie字段(cookie: str, 字段名: str, 值: str) -> str:
    片段列表 = [片段.strip() for 片段 in str(cookie or "").split(";") if 片段.strip()]
    结果: list[str] = []
    已更新 = False
    for 片段 in 片段列表:
        if 片段.startswith(f"{字段名}="):
            结果.append(f"{字段名}={值}")
            已更新 = True
        else:
            结果.append(片段)
    if not 已更新:
        结果.append(f"{字段名}={值}")
    return "; ".join(结果)


def 规范化回调文本(值: Any) -> str:
    if isinstance(值, str):
        if 是回调JSON对象(值):
            return 值
        try:
            已解码文本 = base64.b64decode(
                值.strip().encode("ascii"), validate=True
            ).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return 值
        if 是回调JSON对象(已解码文本):
            return 已解码文本
        return 值
    return json.dumps(值 or {}, ensure_ascii=False, separators=(",", ":"))


def 是回调JSON对象(文本: str) -> bool:
    try:
        数据 = json.loads(文本)
    except (TypeError, ValueError):
        return False
    return isinstance(数据, dict) and bool(
        数据.get("callbackUrl") or 数据.get("callback_url")
    )


def 提取ETag(响应头: Any) -> str:
    for 字段名 in ("etag", "ETag", "Etag"):
        值 = 响应头.get(字段名) if hasattr(响应头, "get") else None
        if 值:
            return str(值).strip().strip('"')
    return ""


def 计算等待秒数(尝试次数: int) -> float:
    return min(max(尝试次数, 1), 5) * 0.5


def 限制文本长度(值: Any, 长度: int = 500) -> str:
    try:
        文本 = (
            json.dumps(值, ensure_ascii=False)
            if isinstance(值, (dict, list))
            else str(值)
        )
    except Exception:
        文本 = str(type(值).__name__)
    return 文本[:长度]
