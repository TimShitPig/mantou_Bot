from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import aiohttp
from astrbot.api import logger


基础地址 = "https://pan.baidu.com"
上传地址 = "https://c.pcs.baidu.com/rest/2.0/pcs/superfile2"
默认上传目录 = "/小说机器人"
浏览器请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://pan.baidu.com/disk/home",
    "Origin": "https://pan.baidu.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "identity",
}


class 百度网盘客户端:
    def __init__(self, cookie: str):
        self.cookie = 清理Cookie(cookie)
        self.bduss = 提取Cookie字段(self.cookie, "BDUSS")
        self.bdstoken = ""
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "百度网盘客户端":
        await self.初始化()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.关闭()

    async def 初始化(self) -> None:
        if self.session is not None:
            await self.session.close()
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=120),
            headers=浏览器请求头,
        )
        await self.获取BDSToken()

    async def 关闭(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def 获取BDSToken(self) -> str:
        数据 = await self.请求JSON("GET", "/api/gettemplatevariable", params={"fields": '["bdstoken"]'})
        self.bdstoken = str(读取路径(数据, ("result", "bdstoken")) or "")
        if not self.bdstoken:
            logger.warning(f"百度网盘没有获取到 bdstoken：response={限制文本长度(数据)}")
        return self.bdstoken

    async def 上传文件并删除同名旧文件(self, 本地路径: str | Path, 文件名: str, 上传目录: str) -> str:
        远端目录 = 规范化目录路径(上传目录)
        await self.确保目录路径(远端目录)
        if 提取文件名状态(文件名) == "完结":
            已有文件 = await self.查找同名普通文件列表(文件名, 远端目录)
            if 已有文件:
                文件ID = 提取百度文件ID(已有文件[0]) or str(已有文件[0].get("path") or "")
                logger.info(f"百度网盘完结小说已存在，跳过重复上传：file={文件名}, file_id={文件ID}, dir={远端目录}")
                return 文件ID
        await self.删除同名普通文件(文件名, 远端目录)
        文件ID = await self.上传文件(本地路径, 远端目录, 文件名)
        if not 文件ID:
            raise RuntimeError("百度网盘上传后没有返回 fs_id")
        return 文件ID

    async def 确保目录路径(self, 远端目录: str) -> bool:
        远端目录 = 规范化目录路径(远端目录)
        if 远端目录 == "/":
            return True
        当前路径 = ""
        for 片段 in 拆分目录路径(远端目录):
            当前路径 = f"{当前路径}/{片段}"
            结果 = await self.创建文件夹(当前路径)
            if str(结果.get("errno")) != "0":
                raise RuntimeError(f"百度网盘创建目录失败：path={当前路径}, response={限制文本长度(结果)}")
        return True

    async def 创建文件夹(self, 远端路径: str) -> dict[str, Any]:
        远端路径 = 规范化目录路径(远端路径)
        if 远端路径 == "/":
            return {"errno": 0}
        参数 = {
            "a": "commit",
            "channel": "chunlei",
            "web": 1,
            "app_id": 250528,
            "bdstoken": self.bdstoken,
            "clienttype": 0,
            "nc": int(time.time() * 1000),
        }
        表单 = {
            "path": 远端路径,
            "isdir": 1,
            "block_list": "[]",
            "method": "post",
            "bdstoken": self.bdstoken,
            "rtype": 3,
        }
        数据 = await self.请求JSON("POST", "/api/create", params=参数, data=表单)
        errno = 数据.get("errno")
        if errno == 0 or str(errno) == "-8" or 数据.get("category"):
            return {"errno": 0}
        return 数据

    async def 列出目录(self, 远端目录: str) -> list[dict[str, Any]]:
        参数 = {
            "dir": 规范化目录路径(远端目录),
            "order": "time",
            "desc": 1,
            "showempty": 0,
            "web": 1,
            "page": 1,
            "num": 1000,
            "bdstoken": self.bdstoken,
            "channel": "chunlei",
            "app_id": 250528,
            "clienttype": 0,
        }
        数据 = await self.请求JSON("GET", "/api/list", params=参数)
        if str(数据.get("errno")) != "0":
            raise RuntimeError(f"百度网盘目录列表获取失败：dir={远端目录}, response={限制文本长度(数据)}")
        列表 = 数据.get("list") or []
        return [项目 for 项目 in 列表 if isinstance(项目, dict)]

    async def 删除同名普通文件(self, 文件名: str, 远端目录: str) -> int:
        删除路径列表: list[str] = []
        for 项目 in await self.查找同名普通文件列表(文件名, 远端目录):
            远端路径 = str(项目.get("path") or "")
            if not 远端路径:
                远端路径 = 拼接远端路径(远端目录, 文件名)
            删除路径列表.append(远端路径)
        if not 删除路径列表:
            return 0
        数据 = await self.删除文件(删除路径列表)
        if str(数据.get("errno")) != "0":
            raise RuntimeError(f"百度网盘删除同名旧文件失败：paths={删除路径列表}, response={限制文本长度(数据)}")
        logger.info(f"百度网盘上传前已删除远端同名旧文件：file={文件名}, count={len(删除路径列表)}, dir={远端目录}")
        return len(删除路径列表)

    async def 查找同名普通文件列表(self, 文件名: str, 远端目录: str) -> list[dict[str, Any]]:
        结果列表: list[dict[str, Any]] = []
        for 项目 in await self.列出目录(远端目录):
            if 是百度文件夹项目(项目):
                continue
            if str(项目.get("server_filename") or "") == 文件名:
                结果列表.append(项目)
        return 结果列表

    async def 删除文件(self, 文件路径列表: list[str]) -> dict[str, Any]:
        参数 = {
            "opera": "delete",
            "bdstoken": self.bdstoken,
            "channel": "chunlei",
            "web": 1,
            "app_id": 250528,
            "clienttype": 0,
            "async": 2,
        }
        表单 = {"filelist": json.dumps(文件路径列表, ensure_ascii=False)}
        return await self.请求JSON("POST", "/api/filemanager", params=参数, data=表单)

    async def 上传文件(self, 本地路径: str | Path, 远端目录: str = "/", 文件名: str | None = None) -> str:
        路径 = Path(本地路径)
        if not 路径.exists():
            raise RuntimeError(f"本地文件不存在：{路径}")
        文件名 = 文件名 or 路径.name
        远端目录 = 规范化目录路径(远端目录)
        远端路径 = 拼接远端路径(远端目录, 文件名)
        文件大小 = 路径.stat().st_size
        logger.info(f"百度网盘开始上传：file={文件名}, remote_path={远端路径}, size={文件大小}")

        预创建数据 = await self.请求预创建数据(远端路径, 文件大小)
        if str(预创建数据.get("errno")) not in ("0", "2"):
            raise RuntimeError(f"百度网盘预创建上传失败：{限制文本长度(预创建数据)}")
        上传ID = str(预创建数据.get("uploadid") or "")
        if not 上传ID:
            raise RuntimeError(f"百度网盘预创建上传没有返回 uploadid：{限制文本长度(预创建数据)}")

        分片MD5 = await self.上传临时分片(路径, 文件名, 远端路径, 上传ID)
        完成数据 = await self.提交上传文件(远端路径, 文件大小, 上传ID, 分片MD5)
        if str(完成数据.get("errno")) != "0":
            raise RuntimeError(f"百度网盘提交上传失败：{限制文本长度(完成数据)}")
        文件ID = str(完成数据.get("fs_id") or "")
        logger.info(f"百度网盘上传完成：file={文件名}, remote_path={远端路径}, fs_id={文件ID}")
        return 文件ID

    async def 请求预创建数据(self, 远端路径: str, 文件大小: int) -> dict[str, Any]:
        参数 = {
            "method": "precreate",
            "app_id": 250528,
            "web": 1,
            "channel": "chunlei",
            "clienttype": 0,
            "bdstoken": self.bdstoken,
        }
        表单 = {
            "path": 远端路径,
            "size": 文件大小,
            "isdir": 0,
            "autoinit": 1,
            "block_list": json.dumps(["5910a591dd8fc18c32a8f3df4fdc1761"]),
            "rtype": 3,
        }
        return await self.请求JSON("POST", "/api/precreate", params=参数, data=表单)

    async def 上传临时分片(self, 本地路径: Path, 文件名: str, 远端路径: str, 上传ID: str) -> str:
        参数 = {
            "method": "upload",
            "type": "tmpfile",
            "app_id": 250528,
            "BDUSS": self.bduss,
            "path": 远端路径,
            "uploadid": 上传ID,
            "partseq": 0,
        }
        表单 = aiohttp.FormData()
        with 本地路径.open("rb") as 文件:
            表单.add_field("file", 文件, filename=文件名, content_type="application/octet-stream")
            数据 = await self.请求JSON(
                "POST",
                上传地址,
                params=参数,
                data=表单,
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=300),
            )
        分片MD5 = str(数据.get("md5") or "")
        if not 分片MD5:
            raise RuntimeError(f"百度网盘临时分片上传没有返回 md5：{限制文本长度(数据)}")
        return 分片MD5

    async def 提交上传文件(self, 远端路径: str, 文件大小: int, 上传ID: str, 分片MD5: str) -> dict[str, Any]:
        参数 = {
            "a": "commit",
            "app_id": 250528,
            "web": 1,
            "channel": "chunlei",
            "clienttype": 0,
            "bdstoken": self.bdstoken,
        }
        表单 = {
            "path": 远端路径,
            "size": 文件大小,
            "isdir": 0,
            "rtype": 3,
            "uploadid": 上传ID,
            "block_list": json.dumps([分片MD5]),
        }
        return await self.请求JSON("POST", "/api/create", params=参数, data=表单)

    async def 请求JSON(
        self,
        方法: str,
        路径或地址: str,
        params: dict[str, Any] | None = None,
        data: Any = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> dict[str, Any]:
        会话 = self.获取会话()
        地址 = 路径或地址 if str(路径或地址).startswith("http") else f"{基础地址}{路径或地址}"
        请求头 = dict(浏览器请求头)
        if self.cookie:
            请求头["Cookie"] = self.cookie
        async with 会话.request(方法, 地址, params=params, data=data, headers=请求头, timeout=timeout) as 响应:
            文本 = await 响应.text()
            if 响应.status >= 400:
                raise RuntimeError(f"百度网盘HTTP {响应.status}({路径或地址})：{限制文本长度(文本, 200)}")
            try:
                数据 = json.loads(文本)
            except Exception as 异常:
                raise RuntimeError(f"百度网盘JSON解析失败：{限制文本长度(文本, 200)}") from 异常
        if not isinstance(数据, dict):
            raise RuntimeError("百度网盘返回格式不是对象")
        return 数据

    def 获取会话(self) -> aiohttp.ClientSession:
        if self.session is None:
            raise RuntimeError("百度网盘客户端未初始化")
        return self.session


async def 后台上传小说文件(配置: Any, 源缓存路径: str | Path, 文件名: str) -> dict[str, Any]:
    if not 百度网盘是否启用(配置):
        return {"enabled": False, "success": False, "skipped": False, "file_id": "", "error": ""}
    上传状态 = 读取百度上传状态(配置)
    if not 百度上传状态允许(文件名, 上传状态):
        logger.info(f"百度网盘后台上传已跳过：file={文件名}, rule={上传状态}")
        return {"enabled": True, "success": False, "skipped": True, "file_id": "", "error": ""}
    源路径 = Path(源缓存路径)
    Cookie = 读取百度网盘Cookie(配置)
    上传目录 = 读取百度上传目录(配置)
    try:
        async with 百度网盘客户端(Cookie) as 客户端:
            文件ID = await 客户端.上传文件并删除同名旧文件(源路径, 文件名, 上传目录)
        logger.info(f"百度网盘后台上传成功：file={文件名}, remote_dir={上传目录}, fs_id={文件ID}")
        return {"enabled": True, "success": True, "skipped": False, "file_id": 文件ID, "error": ""}
    except Exception as 异常:
        logger.warning(f"百度网盘后台上传失败：file={文件名}, error={异常}")
        return {"enabled": True, "success": False, "skipped": False, "file_id": "", "error": str(异常)}


def 百度网盘是否启用(配置: Any) -> bool:
    return bool(读取百度网盘Cookie(配置))


def 读取百度网盘Cookie(配置: Any) -> str:
    return 清理Cookie(读取配置字段(配置, "baidu_pan_cookie") or "")


def 读取百度上传目录(配置: Any) -> str:
    目录 = str(读取配置字段(配置, "baidu_pan_upload_dir") or "").strip()
    return 目录 or 默认上传目录


def 读取百度上传状态(配置: Any) -> str:
    状态 = str(读取配置字段(配置, "baidu_pan_upload_status") or "").strip()
    if 状态 in ("连载", "全部"):
        return 状态
    return "完结"


def 百度上传状态允许(文件名: str, 上传状态: str) -> bool:
    if 上传状态 == "全部":
        return True
    文件状态 = 提取文件名状态(文件名)
    if not 文件状态:
        return 上传状态 == "全部"
    return 文件状态 == 上传状态


def 提取文件名状态(文件名: str) -> str:
    匹配 = re.match(r"^\[(完结|连载)\]", str(文件名 or "").strip())
    return 匹配.group(1) if 匹配 else ""


def 规范化目录路径(目录: Any) -> str:
    文本 = str(目录 or "/").strip().replace("\\", "/")
    if not 文本 or 文本 == "/":
        return "/"
    return "/" + 文本.strip("/")


def 拆分目录路径(目录: Any) -> list[str]:
    return [片段.strip() for 片段 in str(目录 or "").replace("\\", "/").split("/") if 片段.strip()]


def 拼接远端路径(目录: str, 文件名: str) -> str:
    目录 = 规范化目录路径(目录)
    文件名 = Path(str(文件名 or "小说.txt")).name
    if 目录 == "/":
        return f"/{文件名}"
    return f"{目录.rstrip('/')}/{文件名}"


def 是百度文件夹项目(项目: dict[str, Any]) -> bool:
    try:
        return int(项目.get("isdir") or 0) == 1
    except Exception:
        return str(项目.get("isdir") or "").strip().lower() in ("true", "yes", "folder", "dir")


def 提取百度文件ID(项目: dict[str, Any]) -> str:
    for 字段名 in ("fs_id", "fid", "file_id"):
        值 = 项目.get(字段名)
        if 值 not in (None, ""):
            return str(值)
    return ""


def 清理Cookie(cookie: Any) -> str:
    文本 = str(cookie or "").strip()
    if 文本.startswith("百度网盘#"):
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
    for 分类名 in ("baidu_pan_settings", "百度网盘设置", "basic_settings", "基础配置"):
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
