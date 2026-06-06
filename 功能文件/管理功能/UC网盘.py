from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import mimetypes
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable

import aiohttp
from astrbot.api import logger


基础接口地址 = "https://pc-api.uc.cn/1/clouddrive"
默认上传目录 = "/小说机器人"
网盘名称 = "UC网盘"
同名冲突备用文件名最大次数 = 5
上传完成重试次数 = 6
上传完成重试基础间隔秒 = 2
上传完成文件可见重试次数 = 12
上传完成文件可见基础间隔秒 = 3
浏览器请求头 = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*",
    "referer": "https://drive.uc.cn/",
    "origin": "https://drive.uc.cn",
    "pr": "UCBrowser",
    "fr": "pc",
}


class UC网盘处理中错误(RuntimeError):
    pass


class UC网盘客户端:
    def __init__(self, cookie: str):
        self.cookie = 清理Cookie(cookie)
        self.ctoken = 提取Cookie字段(self.cookie, "ctoken")
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "UC网盘客户端":
        await self.初始化()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.关闭()

    async def 初始化(self) -> None:
        if self.session is not None:
            await self.session.close()
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=90),
            headers=浏览器请求头,
        )

    async def 关闭(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def 上传文件并创建分享(self, 本地路径: str | Path, 文件名: str, 上传目录: str) -> str:
        目录ID = await self.确保目录路径(上传目录)
        文件ID = ""
        最后异常: Exception | None = None
        for 尝试次数 in range(1, 同名冲突备用文件名最大次数 + 1):
            远端文件名 = 文件名 if 尝试次数 == 1 else 生成UC备用上传文件名(文件名, 尝试次数)
            try:
                文件ID = await self.上传文件(本地路径, 目录ID, 远端文件名)
                break
            except Exception as 异常:
                if not 是UC同名冲突错误(异常) or 尝试次数 >= 同名冲突备用文件名最大次数:
                    raise
                最后异常 = 异常
                logger.warning(
                    f"UC网盘远端文件名冲突，保留旧文件并改用备用文件名上传："
                    f"file={文件名}, remote_file={远端文件名}, attempt={尝试次数}/{同名冲突备用文件名最大次数}"
                )
                await asyncio.sleep(min(尝试次数 * 上传完成重试基础间隔秒, 10))
        if not 文件ID and 最后异常:
            raise 最后异常
        if not 文件ID:
            raise RuntimeError("UC网盘上传后没有返回文件ID")
        分享链接 = await self.创建分享(文件ID, 文件名)
        if not 分享链接:
            raise RuntimeError("UC网盘没有返回分享链接")
        return 分享链接

    async def 确保目录路径(self, 上传目录: str) -> str:
        当前目录ID = "0"
        for 目录名 in 拆分上传目录(上传目录):
            当前目录ID = await self.确保文件夹(目录名, 当前目录ID)
        return 当前目录ID

    async def 确保文件夹(self, 目录名: str, 父目录ID: str = "0") -> str:
        数据 = await self.请求JSON("GET", "/file/sort", params={"pdir_fid": 父目录ID, "_size": 100})
        项目列表 = 读取路径(数据, ("data", "list")) or []
        for 项目 in 项目列表:
            if isinstance(项目, dict) and 项目.get("file_name") == 目录名 and str(项目.get("dir")) == "1":
                文件ID = str(项目.get("fid") or "")
                if 文件ID:
                    return 文件ID

        创建数据 = await self.请求JSON("POST", "/file", json_data={"pdir_fid": str(父目录ID), "file_name": 目录名})
        文件ID = str(读取路径(创建数据, ("data", "fid")) or "")
        if not 文件ID:
            raise RuntimeError(f"UC网盘创建目录失败：{限制文本长度(创建数据)}")
        return 文件ID

    async def 请求预上传数据(
        self,
        目标目录ID: str,
        文件名: str,
        文件大小: int,
        媒体类型: str,
        当前毫秒: int,
    ) -> dict[str, Any]:
        预上传载荷 = {
            "pdir_fid": str(目标目录ID),
            "file_name": 文件名,
            "size": 文件大小,
            "format_type": 媒体类型,
            "ccp_hash_update": True,
            "parallel_upload": True,
            "l_updated_at": 当前毫秒,
            "l_created_at": 当前毫秒,
        }
        预上传数据 = await self.请求JSON("POST", "/file/upload/pre", json_data=预上传载荷)
        if str(预上传数据.get("code")) != "0" and 是UC同名冲突错误(预上传数据):
            raise RuntimeError(f"UC网盘预上传同名冲突：{限制文本长度(预上传数据)}")
        return 预上传数据

    async def 上传文件(self, 本地路径: str | Path, 目标目录ID: str = "0", 文件名: str | None = None) -> str:
        路径 = Path(本地路径)
        if not 路径.exists():
            raise RuntimeError(f"本地文件不存在：{路径}")
        文件名 = 文件名 or 路径.name
        文件大小 = 路径.stat().st_size
        媒体类型 = mimetypes.guess_type(str(路径))[0] or "application/octet-stream"
        内容SHA1, 内容MD5 = 计算文件哈希(路径)
        当前毫秒 = int(time.time() * 1000)

        预上传数据 = await self.请求预上传数据(目标目录ID, 文件名, 文件大小, 媒体类型, 当前毫秒)
        if str(预上传数据.get("code")) != "0":
            raise RuntimeError(f"UC网盘预上传失败：{限制文本长度(预上传数据)}")

        数据 = 预上传数据.get("data") if isinstance(预上传数据.get("data"), dict) else {}
        if 数据.get("finish"):
            文件ID = str(数据.get("fid") or "")
            if 文件ID:
                return 文件ID

        任务ID = str(数据.get("task_id") or "")
        上传ID = str(数据.get("upload_id") or "")
        对象键 = str(数据.get("obj_key") or "")
        存储桶 = str(数据.get("bucket") or "ul-zb")
        if not 任务ID or not 上传ID or not 对象键:
            raise RuntimeError(f"UC网盘预上传参数不完整：{限制文本长度(预上传数据)}")

        签名日期 = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        OSS用户代理 = "oss-pc-client-novel-search"
        资源路径 = f"/{存储桶}/{对象键}?partNumber=1&uploadId={上传ID}"
        规范头 = f"x-oss-date:{签名日期}\nx-oss-user-agent:{OSS用户代理}\n"
        签名元数据 = f"PUT\n\n{媒体类型}\n{签名日期}\n{规范头}{资源路径}"
        授权数据 = await self.请求JSON(
            "POST",
            f"/file/upload/auth?uploadId={urllib.parse.quote(上传ID)}",
            json_data={"task_id": 任务ID, "auth_meta": 签名元数据},
        )
        授权键 = str(读取路径(授权数据, ("data", "auth_key")) or "")
        if not 授权键:
            raise RuntimeError(f"UC网盘上传授权失败：{限制文本长度(授权数据)}")

        OSS地址 = f"https://{存储桶}.pds.uc.cn/{对象键}?partNumber=1&uploadId={urllib.parse.quote(上传ID)}"
        OSS头 = {
            "authorization": 授权键 if 授权键.startswith("OSS ") else f"OSS {授权键}",
            "x-oss-date": 签名日期,
            "x-oss-user-agent": OSS用户代理,
            "content-type": 媒体类型,
        }
        OSS响应头 = await self.请求OSS("PUT", OSS地址, data=路径.read_bytes(), headers=OSS头)
        响应ETag = 提取OSS响应ETag(OSS响应头)
        ETag = 响应ETag or 内容MD5
        if not 响应ETag:
            logger.warning(f"UC网盘OSS上传未返回ETag，使用本地MD5作为单分片ETag：file={文件名}")

        await self.请求JSON("POST", "/file/update/hash", json_data={"task_id": 任务ID, "md5": 内容MD5, "sha1": 内容SHA1})

        回调数据 = 数据.get("callback") if isinstance(数据.get("callback"), dict) else {}
        回调JSON = json.dumps(
            {"callbackUrl": 回调数据.get("callbackUrl", ""), "callbackBody": 回调数据.get("callbackBody", "")},
            ensure_ascii=False,
        )
        回调头 = base64.b64encode(回调JSON.encode()).decode()
        XML内容 = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<CompleteMultipartUpload>\n"
            "<Part>\n"
            "<PartNumber>1</PartNumber>\n"
            f'<ETag>"{ETag}"</ETag>\n'
            "</Part>\n"
            "</CompleteMultipartUpload>"
        )
        XML_MD5 = base64.b64encode(hashlib.md5(XML内容.encode()).digest()).decode()
        完成日期 = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        完成规范头 = f"x-oss-callback:{回调头}\nx-oss-date:{完成日期}\nx-oss-user-agent:{OSS用户代理}\n"
        完成资源 = f"/{存储桶}/{对象键}?uploadId={上传ID}"
        完成签名元数据 = f"POST\n{XML_MD5}\napplication/xml\n{完成日期}\n{完成规范头}{完成资源}"
        完成授权数据 = await self.请求JSON(
            "POST",
            f"/file/upload/auth?uploadId={urllib.parse.quote(上传ID)}",
            json_data={"task_id": 任务ID, "auth_meta": 完成签名元数据},
        )
        完成授权键 = str(读取路径(完成授权数据, ("data", "auth_key")) or "")
        if not 完成授权键:
            raise RuntimeError(f"UC网盘完成上传授权失败：{限制文本长度(完成授权数据)}")

        完成地址 = f"https://{存储桶}.pds.uc.cn/{对象键}?uploadId={urllib.parse.quote(上传ID)}"
        完成头 = {
            "authorization": 完成授权键 if 完成授权键.startswith("OSS ") else f"OSS {完成授权键}",
            "content-md5": XML_MD5,
            "x-oss-date": 完成日期,
            "x-oss-user-agent": OSS用户代理,
            "x-oss-callback": 回调头,
            "content-type": "application/xml",
        }
        await self.请求OSS("POST", 完成地址, data=XML内容.encode(), headers=完成头)

        预上传文件ID = str(数据.get("fid") or "")
        try:
            完成数据 = await self.完成上传任务(任务ID, 对象键)
        except Exception as 异常:
            if 是UC同名冲突错误(异常):
                if 预上传文件ID:
                    logger.warning(
                        f"UC网盘上传完成接口仍返回处理中，沿用预上传文件ID继续创建分享："
                        f"file={文件名}, fid={预上传文件ID}, error={异常}"
                    )
                    return 预上传文件ID
                文件ID = await self.等待上传文件可用(目标目录ID, 文件名, 文件大小, 预上传文件ID)
                if 文件ID:
                    return 文件ID
            raise
        文件ID = str(读取路径(完成数据, ("data", "fid")) or 数据.get("fid") or "")
        if not 文件ID and str(完成数据.get("code")) == "0":
            文件ID = str(数据.get("fid") or "")
        if not 文件ID:
            raise RuntimeError(f"UC网盘上传完成后没有返回文件ID：{限制文本长度(完成数据)}")
        return 文件ID

    async def 完成上传任务(self, 任务ID: str, 对象键: str) -> dict[str, Any]:
        最后异常: Exception | None = None
        最后冲突响应: Any = None
        for 尝试次数 in range(1, 上传完成重试次数 + 1):
            try:
                完成数据 = await self.请求JSON(
                    "POST",
                    "/file/upload/finish",
                    json_data={"task_id": 任务ID, "obj_key": 对象键},
                )
            except Exception as 异常:
                if not 是UC同名冲突错误(异常) or 尝试次数 >= 上传完成重试次数:
                    raise
                最后异常 = 异常
                logger.warning(
                    f"UC网盘上传完成仍在处理中，等待后重试："
                    f"task_id={任务ID}, attempt={尝试次数}/{上传完成重试次数}, error={异常}"
                )
                await asyncio.sleep(计算UC重试等待秒数(尝试次数))
                continue

            if str(完成数据.get("code")) != "0" and 是UC同名冲突错误(完成数据):
                最后冲突响应 = 完成数据
                if 尝试次数 >= 上传完成重试次数:
                    break
                logger.warning(
                    f"UC网盘上传完成返回处理中，等待后重试："
                    f"task_id={任务ID}, attempt={尝试次数}/{上传完成重试次数}, response={限制文本长度(完成数据)}"
                )
                await asyncio.sleep(计算UC重试等待秒数(尝试次数))
                continue
            return 完成数据

        if 最后异常:
            raise 最后异常
        if 最后冲突响应 is not None:
            raise RuntimeError(f"UC网盘上传完成重试后仍返回同名冲突：{限制文本长度(最后冲突响应)}")
        raise RuntimeError("UC网盘上传完成重试后仍未成功")

    async def 等待上传文件可用(self, 目标目录ID: str, 文件名: str, 文件大小: int, 预上传文件ID: str = "") -> str:
        for 尝试次数 in range(1, 上传完成文件可见重试次数 + 1):
            文件ID = await self.查找目录文件ID(目标目录ID, 文件名, 文件大小, 预上传文件ID)
            if 文件ID:
                logger.warning(
                    f"UC网盘上传完成接口仍返回处理中，已从目录列表确认文件可用："
                    f"file={文件名}, fid={文件ID}, attempt={尝试次数}/{上传完成文件可见重试次数}"
                )
                return 文件ID
            if 尝试次数 < 上传完成文件可见重试次数:
                await asyncio.sleep(计算UC文件可见等待秒数(尝试次数))

        if 预上传文件ID:
            logger.warning(
                f"UC网盘上传完成接口仍返回处理中，目录暂未刷新，使用预上传文件ID继续创建分享："
                f"file={文件名}, fid={预上传文件ID}"
            )
            return 预上传文件ID
        return ""

    async def 查找目录文件ID(self, 目标目录ID: str, 文件名: str, 文件大小: int, 预上传文件ID: str = "") -> str:
        数据 = await self.请求JSON("GET", "/file/sort", params={"pdir_fid": str(目标目录ID), "_size": 200})
        项目列表 = 读取路径(数据, ("data", "list")) or []
        for 项目 in 项目列表:
            if not isinstance(项目, dict):
                continue
            文件ID = str(项目.get("fid") or "")
            if 预上传文件ID and 文件ID == 预上传文件ID:
                return 文件ID
            if 项目.get("file_name") != 文件名:
                continue
            if not UC文件大小匹配(项目, 文件大小):
                continue
            if 文件ID:
                return 文件ID
        return ""

    async def 创建分享(self, 文件ID: str, 标题: str) -> str:
        分享数据: dict[str, Any] | None = None
        分享载荷 = {"fid_list": [str(文件ID)], "title": 标题, "url_type": 1, "expired_type": 1, "public_search": 1}
        for 尝试次数 in range(1, 上传完成文件可见重试次数 + 1):
            try:
                分享数据 = await self.请求JSON("POST", "/share", json_data=分享载荷)
            except Exception as 异常:
                if not 是UC同名冲突错误(异常) or 尝试次数 >= 上传完成文件可见重试次数:
                    raise
                logger.warning(
                    f"UC网盘创建分享时文件仍在处理中，等待后重试："
                    f"fid={文件ID}, attempt={尝试次数}/{上传完成文件可见重试次数}, error={异常}"
                )
                await asyncio.sleep(计算UC文件可见等待秒数(尝试次数))
                continue

            if str(分享数据.get("code")) != "0" and 是UC同名冲突错误(分享数据):
                if 尝试次数 >= 上传完成文件可见重试次数:
                    raise UC网盘处理中错误(f"UC网盘创建分享重试后文件仍在处理中：{限制文本长度(分享数据)}")
                logger.warning(
                    f"UC网盘创建分享返回文件处理中，等待后重试："
                    f"fid={文件ID}, attempt={尝试次数}/{上传完成文件可见重试次数}, response={限制文本长度(分享数据)}"
                )
                await asyncio.sleep(计算UC文件可见等待秒数(尝试次数))
                continue
            break
        if 分享数据 is None:
            raise RuntimeError("UC网盘创建分享没有返回数据")
        if str(分享数据.get("code")) != "0":
            raise RuntimeError(f"UC网盘创建分享失败：{限制文本长度(分享数据)}")
        任务ID = str(分享数据.get("task_id") or 读取路径(分享数据, ("data", "task_id")) or "")
        if not 任务ID:
            raise RuntimeError(f"UC网盘分享任务ID为空：{限制文本长度(分享数据)}")

        分享ID = ""
        for 重试序号 in range(15):
            await asyncio.sleep(0.5)
            任务数据 = await self.请求JSON可等待("GET", "/task", params={"task_id": 任务ID, "retry_index": 重试序号})
            任务详情 = 任务数据.get("data") if isinstance(任务数据.get("data"), dict) else {}
            if str(任务详情.get("status")) == "2":
                分享ID = str(任务详情.get("share_id") or "")
                break
        if not 分享ID:
            raise RuntimeError("UC网盘分享任务超时")

        链接数据 = await self.请求JSON可等待("POST", "/share/password", json_data={"share_id": 分享ID})
        if str(链接数据.get("code")) != "0":
            raise RuntimeError(f"UC网盘获取分享链接失败：{限制文本长度(链接数据)}")
        分享链接 = str(读取路径(链接数据, ("data", "share_url")) or "")
        if 分享链接 and not 分享链接.startswith("http"):
            分享链接 = f"https://drive.uc.cn{分享链接}"
        return 分享链接

    async def 请求JSON(
        self,
        方法: str,
        路径: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.确保CToken()
        会话 = self.获取会话()
        请求头 = dict(浏览器请求头)
        请求头["cookie"] = self.cookie
        if 方法.upper() == "POST":
            请求头["content-type"] = "application/json"
        async with 会话.request(方法, self.构造地址(路径, params), headers=请求头, json=json_data) as 响应:
            文本 = await 响应.text()
            self.合并响应Cookie(响应.cookies)
            if 响应.status >= 400:
                try:
                    错误数据 = json.loads(文本)
                except Exception:
                    错误数据 = None
                if isinstance(错误数据, dict) and 是UC同名冲突错误(错误数据):
                    raise UC网盘处理中错误(
                        f"UC网盘HTTP {响应.status}({路径})：{提取UC错误消息(错误数据) or 限制文本长度(错误数据, 200)}"
                    )
                错误文本 = 提取UC错误消息(错误数据) if isinstance(错误数据, dict) else ""
                raise RuntimeError(f"UC网盘HTTP {响应.status}({路径})：{错误文本 or 限制文本长度(文本, 200)}")
            try:
                数据 = json.loads(文本)
            except Exception as 异常:
                raise RuntimeError(f"UC网盘JSON解析失败：{限制文本长度(文本, 200)}") from 异常
        if not isinstance(数据, dict):
            raise RuntimeError("UC网盘返回格式不是对象")
        return 数据

    async def 请求JSON可等待(
        self,
        方法: str,
        路径: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for 尝试次数 in range(1, 上传完成文件可见重试次数 + 1):
            try:
                return await self.请求JSON(方法, 路径, params=params, json_data=json_data)
            except Exception as 异常:
                if not 是UC同名冲突错误(异常) or 尝试次数 >= 上传完成文件可见重试次数:
                    raise
                logger.warning(
                    f"UC网盘接口返回文件处理中，等待后重试："
                    f"path={路径}, attempt={尝试次数}/{上传完成文件可见重试次数}, error={异常}"
                )
                await asyncio.sleep(计算UC文件可见等待秒数(尝试次数))
        raise RuntimeError(f"UC网盘接口重试后仍无返回：{路径}")

    async def 请求OSS(self, 方法: str, 地址: str, data: bytes, headers: dict[str, str]) -> dict[str, str]:
        会话 = self.获取会话()
        async with 会话.request(方法, 地址, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as 响应:
            文本 = await 响应.text()
            if 响应.status not in (200, 201):
                raise RuntimeError(f"UC网盘OSS上传失败：HTTP {响应.status}: {限制文本长度(文本, 200)}")
            return dict(响应.headers)

    async def 确保CToken(self) -> None:
        if self.ctoken:
            return
        会话 = self.获取会话()
        请求头 = dict(浏览器请求头)
        请求头["cookie"] = self.cookie
        try:
            async with 会话.get("https://drive.uc.cn/", headers=请求头, timeout=aiohttp.ClientTimeout(total=20)) as 响应:
                await 响应.text()
                self.合并响应Cookie(响应.cookies)
        except Exception as 异常:
            logger.debug(f"UC网盘ctoken探测失败：error={异常}")
        self.ctoken = self.ctoken or 提取Cookie字段(self.cookie, "ctoken")

    def 构造地址(self, 路径: str, params: dict[str, Any] | None = None) -> str:
        查询 = {"pr": "UCBrowser", "fr": "pc"}
        if params:
            查询.update({键: 值 for 键, 值 in params.items() if 值 is not None})
        if self.ctoken:
            查询["ctoken"] = self.ctoken
        分隔符 = "&" if "?" in 路径 else "?"
        return f"{基础接口地址}{路径}{分隔符}{urllib.parse.urlencode(查询, safe=':,')}"

    def 合并响应Cookie(self, cookies: Any) -> None:
        for 名称, morsel in cookies.items():
            值 = getattr(morsel, "value", morsel)
            self.cookie = 更新Cookie字段(self.cookie, 名称, str(值))
            if 名称 == "ctoken":
                self.ctoken = str(值)

    def 获取会话(self) -> aiohttp.ClientSession:
        if self.session is None:
            raise RuntimeError("UC网盘客户端未初始化")
        return self.session


async def 准备小说分享链接文件(
    配置: Any,
    源缓存路径: str | Path,
    文件名: str,
    写入缓存文件函数: Callable[[str, bytes], Path],
) -> dict[str, Any]:
    if not UC网盘是否启用(配置):
        return {"enabled": False, "success": False, "cache_path": None, "share_url": "", "error": ""}
    源路径 = Path(源缓存路径)
    Cookie = 读取UC网盘Cookie(配置)
    上传目录 = 读取UC上传目录(配置)
    try:
        async with UC网盘客户端(Cookie) as 客户端:
            分享链接 = await 客户端.上传文件并创建分享(源路径, 文件名, 上传目录)
        链接文件内容 = 生成分享链接文件内容(分享链接)
        链接缓存路径 = 写入缓存文件函数(文件名, 链接文件内容)
        return {"enabled": True, "success": True, "cache_path": 链接缓存路径, "share_url": 分享链接, "error": ""}
    except Exception as 异常:
        logger.warning(f"UC网盘上传分享失败，回退发送源文件：file={文件名}, error={异常}")
        return {"enabled": True, "success": False, "cache_path": None, "share_url": "", "error": str(异常)}


def UC网盘是否启用(配置: Any) -> bool:
    return bool(读取UC网盘Cookie(配置))


def 读取UC网盘Cookie(配置: Any) -> str:
    return 清理Cookie(读取配置字段(配置, "uc_pan_cookie") or "")


def 读取UC上传目录(配置: Any) -> str:
    目录 = str(读取配置字段(配置, "uc_pan_upload_dir") or "").strip()
    return 目录 or 默认上传目录


def 生成分享链接文件内容(分享链接: str) -> bytes:
    文本 = f"请复制链接打开{网盘名称}\r\n链接：{str(分享链接 or '').strip()}\r\n"
    return 文本.encode("utf-8")


def 拆分上传目录(上传目录: str) -> list[str]:
    文本 = str(上传目录 or 默认上传目录).strip().replace("\\", "/")
    return [片段.strip() for 片段 in 文本.split("/") if 片段.strip()]


def 计算文件哈希(路径: Path) -> tuple[str, str]:
    sha1 = hashlib.sha1()
    md5 = hashlib.md5()
    with 路径.open("rb") as 文件:
        while True:
            数据 = 文件.read(1024 * 1024)
            if not 数据:
                break
            sha1.update(数据)
            md5.update(数据)
    return sha1.hexdigest().lower(), md5.hexdigest().lower()


def 提取OSS响应ETag(响应头: Any) -> str:
    if not 响应头:
        return ""
    获取方法 = getattr(响应头, "get", None)
    if callable(获取方法):
        for 字段名 in ("etag", "ETag", "Etag"):
            值 = 获取方法(字段名)
            if 值:
                return str(值).strip().strip('"')
    if isinstance(响应头, dict):
        for 字段名, 值 in 响应头.items():
            if str(字段名).lower() == "etag" and 值:
                return str(值).strip().strip('"')
    return ""


def 是UC同名冲突错误(值: Any) -> bool:
    if isinstance(值, dict):
        错误码 = str(值.get("code") or "")
        消息 = str(值.get("message") or 值.get("msg") or 值)
        return 错误码 == "23008" or 是UC同名冲突错误(消息)
    文本 = str(值 or "").lower()
    return (
        "23008" in 文本
        or "同名冲突" in 文本
        or "file is doloading" in 文本
        or "file is downloading" in 文本
    )


def 提取UC错误消息(值: Any) -> str:
    if not isinstance(值, dict):
        return ""
    for 字段名 in ("message", "msg", "error"):
        消息 = str(值.get(字段名) or "").strip()
        if 消息:
            return 消息
    return ""


def 生成UC备用上传文件名(文件名: str, 序号: int) -> str:
    路径 = Path(str(文件名 or "小说.txt"))
    后缀 = 路径.suffix or ".txt"
    主名 = 路径.stem or "小说"
    时间戳 = int(time.time() * 1000)
    return f"{主名}_UC上传_{时间戳}_{序号}{后缀}"


def 计算UC重试等待秒数(尝试次数: int) -> int:
    return min(max(尝试次数, 1) * 上传完成重试基础间隔秒, 10)


def 计算UC文件可见等待秒数(尝试次数: int) -> int:
    return min(max(尝试次数, 1) * 上传完成文件可见基础间隔秒, 10)


def UC文件大小匹配(项目: dict[str, Any], 文件大小: int) -> bool:
    for 字段名 in ("size", "file_size", "file_size_int", "length", "content_length"):
        值 = 项目.get(字段名)
        if 值 is None or 值 == "":
            continue
        try:
            return int(值) == int(文件大小)
        except Exception:
            continue
    return True


def 清理Cookie(cookie: Any) -> str:
    文本 = str(cookie or "").strip()
    if 文本.startswith("UC网盘#"):
        文本 = 文本.split("#", 1)[1].strip()
    return 文本


def 提取Cookie字段(cookie: str, 字段名: str) -> str:
    for 片段 in re.split(r";\s*", str(cookie or "")):
        if "=" not in 片段:
            continue
        名称, 值 = 片段.split("=", 1)
        if 名称.strip() == 字段名:
            return 值.strip()
    return ""


def 更新Cookie字段(cookie: str, 字段名: str, 值: str) -> str:
    片段列表 = [片段.strip() for 片段 in str(cookie or "").split(";") if 片段.strip()]
    结果列表: list[str] = []
    已存在 = False
    for 片段 in 片段列表:
        if 片段.startswith(f"{字段名}="):
            结果列表.append(f"{字段名}={值}")
            已存在 = True
        else:
            结果列表.append(片段)
    if not 已存在:
        结果列表.append(f"{字段名}={值}")
    return "; ".join(结果列表)


def 读取配置字段(配置: Any, 字段名: str) -> Any:
    配置字典 = 获取配置字典(配置)
    if 配置字典 is not None and 配置字典 is not 配置:
        值 = 读取配置字段(配置字典, 字段名)
        if 值 is not None:
            return 值

    值 = 读取字段(配置, 字段名)
    if 值 is None:
        值 = 读取旧版配置字段(配置, 字段名)
    if 值 is not None:
        return 值
    for 分类名 in ("uc_pan_settings", "UC网盘设置", "basic_settings", "基础配置"):
        分类 = 读取字段(配置, 分类名)
        if 分类 is None:
            分类 = 读取旧版配置字段(配置, 分类名)
        if isinstance(分类, dict):
            值 = 分类.get(字段名)
            if 值 is not None:
                return 值
        elif 分类 is not None:
            值 = 读取字段(分类, 字段名)
            if 值 is None:
                值 = 读取旧版配置字段(分类, 字段名)
            if 值 is not None:
                return 值
    return None


def 获取配置字典(配置: Any) -> dict[str, Any] | None:
    if isinstance(配置, dict):
        return 配置
    获取方法 = getattr(配置, "get_config", None)
    if callable(获取方法):
        try:
            数据 = 获取方法()
            if isinstance(数据, dict):
                return 数据
        except Exception:
            pass
    for 字段名 in ("data", "obj"):
        数据 = getattr(配置, 字段名, None)
        if isinstance(数据, dict):
            return 数据
    return None


def 读取旧版配置字段(配置: Any, 字段名: str) -> Any:
    获取方法 = getattr(配置, "get", None)
    if callable(获取方法):
        try:
            return 获取方法(字段名)
        except Exception:
            pass
    return getattr(配置, 字段名, None)


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)


def 读取路径(数据: Any, 路径: tuple[str, ...]) -> Any:
    当前值 = 数据
    for 字段名 in 路径:
        if not isinstance(当前值, dict):
            return None
        当前值 = 当前值.get(字段名)
    return 当前值


def 限制文本长度(值: Any, 最大长度: int = 500) -> str:
    文本 = str(值 or "")
    if len(文本) > 最大长度:
        return 文本[:最大长度] + "..."
    return 文本
