from __future__ import annotations

import asyncio
import base64
from datetime import date
import hashlib
import json
import mimetypes
import re
import time
import weakref
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
目录列表最大并发数 = 4
目录扫描完整性重试次数 = 3
目录扫描重试每页数量 = 100
文件可见重试次数 = 12
分享链接重试次数 = 12
查询失败重试次数 = 3
可重试查询路径 = frozenset({"/file/sort", "/task", "/share/mypage/detail"})
请求阶段 = {
    "/file/sort": "directory_list",
    "/file": "directory_create",
    "/file/delete": "file_delete",
    "/file/upload/pre": "upload_pre",
    "/file/update/hash": "upload_hash",
    "/file/upload/auth": "upload_auth",
    "/file/upload/finish": "upload_finish",
    "/file/download": "download_info",
    "/task": "task",
    "/share": "share_create",
    "/share/mypage/detail": "share_list",
    "/share/password": "share_link",
}
_夸克同名上传锁表 = globals().get("_夸克同名上传锁表")
if not isinstance(_夸克同名上传锁表, weakref.WeakValueDictionary):
    _夸克同名上传锁表 = weakref.WeakValueDictionary()
_夸克账号操作锁表 = globals().get("_夸克账号操作锁表")
if not isinstance(_夸克账号操作锁表, weakref.WeakValueDictionary):
    _夸克账号操作锁表 = weakref.WeakValueDictionary()
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


class 夸克网盘请求错误(RuntimeError):
    def __init__(
        self,
        路径: str,
        *,
        HTTP状态: int | None = None,
        业务码: int | None = None,
        原因: str = "http_error",
        页码: int | None = None,
    ):
        self.阶段 = 请求阶段.get(路径, "api_request")
        self.HTTP状态 = HTTP状态
        self.业务码 = 业务码
        self.原因 = 原因
        self.页码 = 页码
        super().__init__(
            f"夸克网盘请求失败：阶段={self.阶段}, HTTP状态={HTTP状态}, "
            f"业务码={业务码}, 原因={原因}, 页码={页码}"
        )


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
        上传目录 = 网盘清理工具.生成每日上传目录(上传目录)
        上传锁 = 获取夸克同名上传锁(self.cookie, 上传目录, 文件名)
        async with 上传锁:
            # 目录使用偏移分页；同账号不同小说的写入也会使正在扫描的页错位。
            async with 获取夸克账号操作锁(self.cookie):
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
        async with 网盘清理工具.获取目录创建锁(self.cookie, 父目录ID, 目录名):
            return await self._确保文件夹(目录名, 父目录ID)

    async def _确保文件夹(self, 目录名: str, 父目录ID: str) -> str:
        已有ID = await self.查找文件夹ID(目录名, 父目录ID)
        if 已有ID:
            return 已有ID
        目录冲突: 夸克网盘请求错误 | None = None
        try:
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
        except 夸克网盘请求错误 as 异常:
            if 异常.业务码 != 23008:
                raise
            目录冲突 = 异常
        else:
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
        if 目录冲突 is not None:
            raise 目录冲突
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
        已删除ID: set[str] = set()
        for 尝试次数 in range(1, 文件可见重试次数 + 1):
            文件ID列表 = await self.查找同名普通文件ID列表(文件名, 父目录ID)
            if not 文件ID列表:
                logger.debug(
                    f"夸克网盘同名清理确认完成：file={文件名}, "
                    f"deleted={len(已删除ID)}, parent_id={父目录ID}"
                )
                return
            待删ID = [文件ID for 文件ID in 文件ID列表 if 文件ID not in 已删除ID]
            if 待删ID:
                try:
                    await self.删除文件ID列表(待删ID)
                    已删除ID.update(待删ID)
                except Exception as 异常:
                    logger.warning(
                        f"夸克网盘删除同名旧文件重试：file={文件名}, "
                        f"attempt={尝试次数}/{文件可见重试次数}, "
                        f"error_type={type(异常).__name__}"
                    )
                    if 尝试次数 == 文件可见重试次数:
                        raise RuntimeError("夸克网盘删除同名旧文件失败") from 异常
            if 尝试次数 < 文件可见重试次数:
                await asyncio.sleep(计算等待秒数(尝试次数))

        剩余ID = await self.查找同名普通文件ID列表(文件名, 父目录ID)
        if 剩余ID:
            raise RuntimeError(
                f"夸克网盘同名旧文件仍可见，停止上传：file={文件名}, "
                f"count={len(剩余ID)}, parent_id={父目录ID}"
            )
        logger.debug(
            f"夸克网盘同名清理确认完成：file={文件名}, "
            f"deleted={len(已删除ID)}, parent_id={父目录ID}"
        )

    async def 查找同名普通文件ID列表(
        self, 文件名: str, 父目录ID: str
    ) -> list[str]:
        文件ID列表 = []
        for 项目 in await self.列出目录全部项目(父目录ID):
            if not isinstance(项目, dict):
                continue
            if 是文件夹项目(项目) or 读取文件名(项目) != 文件名:
                continue
            文件ID = 读取文件ID(项目)
            if 文件ID and 文件ID not in 文件ID列表:
                文件ID列表.append(文件ID)
        return 文件ID列表

    async def 清理早于当天小说(
        self, 上传目录: str, 当前日期: date | None = None
    ) -> int:
        """清理前两天及更早小说，并删除确认清空的日期子目录。"""
        目录片段 = 拆分上传目录(上传目录)
        if 目录片段 and 目录片段[0] == "QQ聊天媒体":
            return 0
        async with 获取夸克账号操作锁(self.cookie):
            return await 网盘清理工具.清理日期目录小说(self, 上传目录, 当前日期)

    async def 列出目录全部项目(
        self, 父目录ID: str, *, _完整性重试次数: int = 0,
        _串行扫描: bool = False,
    ) -> list[dict[str, Any]]:
        class 扫描不一致(RuntimeError):
            def __init__(self, 原因: str, 页码: int, 已收集: int, 总数: int | None):
                self.原因, self.页码 = 原因, 页码
                self.已收集, self.总数 = 已收集, 总数

        async def 请求目录页(
            页码: int, 每页数量: int,
        ) -> tuple[list[dict[str, Any]], int | None, int]:
            数据 = await self.请求JSON(
                "GET", "/file/sort",
                params={
                    "pdir_fid": str(父目录ID),
                    "_page": 页码,
                    "_size": 每页数量,
                    "_fetch_total": 1,
                    "_fetch_sub_dirs": 0,
                    # 更新时间会随远端操作变化，不适合作为偏移分页的排序。
                    "_sort": "file_type:asc,file_name:asc",
                    "fetch_all_file": 1,
                    "fetch_risk_file_name": 1,
                },
            )
            if not 接口成功(数据):
                raise RuntimeError(f"夸克网盘目录列表获取失败：{限制文本长度(数据)}")
            数据主体 = 数据.get("data")
            if not isinstance(数据主体, dict):
                raise RuntimeError("夸克网盘目录响应缺少有效数据主体")
            项目列表 = 数据主体.get("list")
            if not isinstance(项目列表, list):
                raise RuntimeError("夸克网盘目录响应缺少有效列表")
            元数据字段: dict[str, int] = {}
            for 主体 in (数据主体, 数据):
                if "metadata" not in 主体:
                    continue
                元数据 = 主体["metadata"]
                if not isinstance(元数据, dict):
                    raise RuntimeError("夸克网盘目录元数据无效")
                for 字段 in ("_total", "total", "total_count", "total_num", "_page", "_size", "_count"):
                    值 = 元数据.get(字段)
                    if 值 is None:
                        continue
                    if type(值) is int and 值 >= 0:
                        数值 = 值
                    elif isinstance(值, str) and re.fullmatch(r"[0-9]+", 值):
                        数值 = int(值)
                    else:
                        raise RuntimeError("夸克网盘目录分页元数据无效")
                    键 = "_total" if 字段 in {"total", "total_count", "total_num"} else 字段
                    if 键 in 元数据字段 and 元数据字段[键] != 数值:
                        raise RuntimeError("夸克网盘目录分页元数据不一致")
                    元数据字段[键] = 数值
            总数 = 元数据字段.get("_total")
            实际页宽 = 元数据字段.get("_size", 每页数量)
            if 实际页宽 < 1 or 实际页宽 > 每页数量:
                raise RuntimeError("夸克网盘目录分页大小无效")
            if 元数据字段.get("_page", 页码) != 页码:
                raise 扫描不一致("page_mismatch", 页码, 0, 总数)
            if 元数据字段.get("_count", len(项目列表)) != len(项目列表):
                raise 扫描不一致("count_mismatch", 页码, 0, 总数)
            if len(项目列表) > 实际页宽 or (总数 is not None and len(项目列表) > 总数):
                raise 扫描不一致("page_overflow", 页码, len(项目列表), 总数)
            页内ID: set[str] = set()
            for 项目 in 项目列表:
                if not isinstance(项目, dict) or not 读取文件ID(项目).strip():
                    raise RuntimeError("夸克网盘目录项目结构或文件ID无效")
                文件ID = 读取文件ID(项目)
                if 文件ID in 页内ID:
                    raise 扫描不一致("duplicate_id", 页码, len(页内ID), 总数)
                页内ID.add(文件ID)
            return 项目列表, 总数, 实际页宽

        for 轮次 in range(_完整性重试次数, 目录扫描完整性重试次数 + 1):
            串行 = _串行扫描 or 轮次 > 0
            请求页宽 = 目录扫描重试每页数量 if 串行 else 目录列表每页数量
            结果: list[dict[str, Any]] = []
            已见ID: set[str] = set()
            总数量: int | None = None
            try:
                首页项目, 总数量, 实际页宽 = await 请求目录页(1, 请求页宽)
                前页未满 = False

                def 合并页面(
                    页码: int, 页面: tuple[list[dict[str, Any]], int | None, int],
                ) -> bool:
                    nonlocal 前页未满
                    项目列表, 页总数, 页宽 = 页面
                    if 页宽 != 实际页宽 or 页总数 != 总数量:
                        raise 扫描不一致("metadata_changed", 页码, len(结果), 页总数)
                    if 总数量 is None and 前页未满 and 项目列表:
                        raise 扫描不一致("short_page_followed_by_data", 页码, len(结果), None)
                    for 项目 in 项目列表:
                        文件ID = 读取文件ID(项目)
                        if 文件ID in 已见ID:
                            raise 扫描不一致("duplicate_id", 页码, len(结果), 总数量)
                        已见ID.add(文件ID)
                        结果.append(项目)
                    if 总数量 is not None:
                        预期数量 = min(实际页宽, max(0, 总数量 - (页码 - 1) * 实际页宽))
                        if len(项目列表) != 预期数量 or len(结果) > 总数量:
                            raise 扫描不一致("incomplete_page", 页码, len(结果), 总数量)
                        return len(结果) == 总数量
                    # 没有总数时必须继续至空页，不能把短页当作扫描终点。
                    前页未满 = len(项目列表) < 实际页宽
                    return not 项目列表

                已完成 = 合并页面(1, (首页项目, 总数量, 实际页宽))
                页码 = 2
                while not 已完成:
                    if not 串行 and 总数量 is not None:
                        总页数 = (总数量 + 实际页宽 - 1) // 实际页宽
                        页码列表 = list(range(页码, min(页码 + 目录列表最大并发数, 总页数 + 1)))
                        批次结果 = await asyncio.gather(
                            *(请求目录页(值, 实际页宽) for 值 in 页码列表),
                            return_exceptions=True,
                        )
                        if any(isinstance(响应, asyncio.CancelledError) for 响应 in 批次结果):
                            raise asyncio.CancelledError
                        # HTTP/业务失败保留原来的错误，不把它们当成目录不一致。
                        for 响应 in 批次结果:
                            if isinstance(响应, BaseException) and not isinstance(响应, 扫描不一致):
                                raise 响应
                        for 响应 in 批次结果:
                            if isinstance(响应, 扫描不一致):
                                raise 响应
                        for 当前页, 页面 in zip(页码列表, 批次结果):
                            已完成 = 合并页面(当前页, 页面)
                        页码 += len(页码列表)
                    else:
                        已完成 = 合并页面(页码, await 请求目录页(页码, 实际页宽))
                        页码 += 1
                # 总数相同仍可能换入/换出；复验首页，不拼接不同轮次的旧页面。
                复查首页, 复查总数, 复查页宽 = await 请求目录页(1, 实际页宽)
                if (
                    复查总数 != 总数量 or 复查页宽 != 实际页宽
                    or [读取文件ID(项目) for 项目 in 复查首页]
                    != [读取文件ID(项目) for 项目 in 首页项目]
                ):
                    raise 扫描不一致("head_changed", 1, len(结果), 复查总数)
                return 结果
            except 扫描不一致 as 异常:
                if 轮次 >= 目录扫描完整性重试次数:
                    logger.warning(
                        "夸克网盘目录扫描仍不完整，停止使用部分结果："
                        "page=%s, collected=%s, reported_total=%s, reason=%s",
                        异常.页码, 异常.已收集, 异常.总数, 异常.原因,
                    )
                    raise RuntimeError("夸克网盘目录扫描不完整，已停止后续文件操作") from None
                logger.info(
                    "夸克网盘目录扫描不一致，退避后从首页串行重扫："
                    "page=%s, collected=%s, reported_total=%s, reason=%s, attempt=%s/%s",
                    异常.页码, 异常.已收集, 异常.总数, 异常.原因,
                    轮次 + 1, 目录扫描完整性重试次数,
                )
                await asyncio.sleep(0.5 * 2 ** 轮次)
        raise RuntimeError("夸克网盘目录扫描不完整，已停止后续文件操作")


    async def 上传文件(self, 本地路径: str | Path, 父目录ID: str, 文件名: str) -> str:
        路径 = Path(本地路径)
        if not 路径.is_file():
            raise RuntimeError("夸克网盘上传文件不存在")
        MD5, SHA1 = await asyncio.to_thread(计算文件哈希, 路径)
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

    async def 获取文件下载地址(self, 文件ID: str) -> str:
        """解析当前登录账号内精确文件的原文件地址；调用方负责同源代理。"""
        if not isinstance(文件ID, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", 文件ID):
            raise 夸克网盘请求错误("/file/download", 原因="invalid_file_id")
        数据 = await self.请求JSON(
            "POST", "/file/download", json_data={"fids": [文件ID]},
        )
        项目列表 = 数据.get("data")
        if not isinstance(项目列表, list):
            raise 夸克网盘请求错误("/file/download", 原因="invalid_download_response")
        匹配项目 = [
            项目 for 项目 in 项目列表
            if isinstance(项目, dict) and 项目.get("fid") == 文件ID
        ]
        if len(匹配项目) != 1:
            raise 夸克网盘请求错误("/file/download", 原因="download_file_mismatch")
        地址 = 匹配项目[0].get("download_url")
        if not isinstance(地址, str) or not 地址 or len(地址) > 16384 or any(
            ord(字符) < 32 or ord(字符) == 127 for 字符 in 地址
        ):
            raise 夸克网盘请求错误("/file/download", 原因="invalid_download_url")
        try:
            解析 = urlsplit(地址)
            主机 = str(解析.hostname or "").lower()
            有效 = (
                解析.scheme == "https"
                and 解析.username is None and 解析.password is None
                and 解析.port in (None, 443)
                and re.fullmatch(
                    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*quark\.cn", 主机,
                ) is not None
                and not 解析.fragment
            )
        except ValueError:
            有效 = False
        if not 有效:
            raise 夸克网盘请求错误("/file/download", 原因="invalid_download_url")
        return 地址

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
        查询异常 = None
        if 分享ID:
            try:
                密码数据 = await self.请求JSON(
                    "POST", "/share/password", json_data={"share_id": 分享ID}
                )
                分享链接 = 提取分享链接(密码数据)
                if 分享链接:
                    return 分享链接
            except 夸克网盘请求错误 as 异常:
                if 异常.原因 != "query_failed":
                    raise
                查询异常 = 异常
        分享链接 = await self.等待分享短链接(分享ID, 文件ID)
        if not 分享链接 and 查询异常 is not None:
            raise 查询异常
        return 分享链接

    async def 轮询任务(self, 任务ID: str) -> dict[str, Any]:
        for 尝试次数 in range(分享链接重试次数):
            最后数据 = await self.请求JSON(
                "GET",
                "/task",
                params={"task_id": 任务ID, "retry_index": 尝试次数},
            )
            任务数据 = (
                最后数据.get("data") if isinstance(最后数据.get("data"), dict) else {}
            )
            if not 接口成功(最后数据):
                raise 夸克网盘请求错误(
                    "/task", HTTP状态=200,
                    业务码=安全整数(最后数据.get("code"), -1), 原因="business_error"
                )
            任务状态 = 安全整数(任务数据.get("status"), -1)
            if 任务状态 == 2:
                return 最后数据
            if 任务状态 == 3:
                raise 夸克网盘请求错误("/task", HTTP状态=200, 原因="task_failed")
            if 尝试次数 + 1 < 分享链接重试次数:
                await asyncio.sleep(1)
        raise 夸克网盘请求错误("/task", HTTP状态=200, 原因="task_timeout")

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
                        当前分享ID == 分享ID
                        if 分享ID
                        else 文件ID == 首文件ID or 文件ID in 文件ID列表
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
        for 尝试次数 in range(1, 查询失败重试次数 + 1):
            async with 会话.request(方法, 地址, params=请求参数, json=json_data) as 响应:
                self.同步服务器时间(响应.headers)
                文本 = await 响应.text()
                self.刷新会话Cookie(响应)
                HTTP状态 = 响应.status
            try:
                数据 = json.loads(文本)
            except (TypeError, ValueError):
                raise 夸克网盘请求错误(
                    路径, HTTP状态=HTTP状态,
                    原因="http_error" if HTTP状态 >= 400 else "invalid_json"
                ) from None
            if not isinstance(数据, dict):
                raise 夸克网盘请求错误(路径, HTTP状态=HTTP状态, 原因="invalid_shape")
            业务码 = 安全整数(数据.get("code"), -1) if "code" in 数据 else None
            查询失败 = (
                HTTP状态 in (200, 400)
                and 业务码 == 15020
                and str(数据.get("message") or "").strip() == "query fail [61004]"
            )
            if HTTP状态 >= 400 or not 接口成功(数据):
                异常 = 夸克网盘请求错误(
                    路径, HTTP状态=HTTP状态, 业务码=业务码,
                    原因="query_failed" if 查询失败 else (
                        "http_error" if HTTP状态 >= 400 else "business_error"
                    ),
                    页码=安全整数(请求参数.get("_page"), 0) or None,
                )
                if (
                    查询失败 and 方法.upper() == "GET"
                    and 路径 in 可重试查询路径 and 尝试次数 < 查询失败重试次数
                ):
                    logger.warning(
                        "夸克网盘查询失败重试：阶段=%s, HTTP状态=%s, 业务码=%s, "
                        "页码=%s, 尝试=%s/%s",
                        异常.阶段, HTTP状态, 业务码, 异常.页码,
                        尝试次数, 查询失败重试次数,
                    )
                    await asyncio.sleep(计算等待秒数(尝试次数))
                    continue
                raise 异常
            return 数据
        raise 夸克网盘请求错误(路径, 原因="query_failed")

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


def 获取夸克账号操作锁(cookie: str) -> asyncio.Lock:
    """账号级写入窗口跨客户端共用，刷新 __puus 不生成另一把锁。"""
    稳定Cookie = sorted(
        片段.strip()
        for 片段 in 清理Cookie(cookie).split(";")
        if 片段.strip()
        and 片段.split("=", 1)[0].strip().lower() not in {"__puus", "ctoken"}
    )
    键 = hashlib.sha256(";".join(稳定Cookie).encode("utf-8")).hexdigest()
    锁 = _夸克账号操作锁表.get(键)
    if 锁 is None:
        锁 = asyncio.Lock()
        _夸克账号操作锁表[键] = 锁
    return 锁


def 获取夸克同名上传锁(cookie: str, 上传目录: str, 文件名: str) -> asyncio.Lock:
    稳定Cookie片段 = [
        片段.strip()
        for 片段 in 清理Cookie(cookie).split(";")
        if 片段.strip()
        and 片段.split("=", 1)[0].strip().lower() not in {"__puus", "ctoken"}
    ]
    稳定Cookie片段.sort()
    账号摘要 = hashlib.sha256(";".join(稳定Cookie片段).encode("utf-8")).hexdigest()
    目录路径 = "/".join(拆分上传目录(上传目录))
    锁键 = hashlib.sha256(
        f"{账号摘要}\0{目录路径}\0{文件名}".encode("utf-8")
    ).hexdigest()
    锁 = _夸克同名上传锁表.get(锁键)
    if 锁 is None:
        锁 = asyncio.Lock()
        _夸克同名上传锁表[锁键] = 锁
    return 锁


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
