from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import random
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple

import aiohttp
import loky
from astrbot.api import logger
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from loky import BrokenProcessPool, ProcessPoolExecutor, cpu_count

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception as exc:
    小说网盘 = None
    logger.warning(f"小说网盘模块加载失败：错误类型={type(exc).__name__}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：错误类型={type(exc).__name__}")

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题
from 功能文件.管理功能.小说功能.功能.得间解密 import 解密得间正文并计时

下载缓存目录 = 小说缓存工具.下载缓存目录
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
得间正文最大并发数 = 128
得间正文重试次数 = 3
得间清单最大并发数 = 8
得间解密最大动态并发数 = max(1, min(4, cpu_count() - 1))
_旧得间解密执行器 = globals().get("得间解密执行器")
if _旧得间解密执行器 is not None:
    try:
        _旧得间解密执行器.shutdown(wait=False, kill_workers=True)
    except TypeError:
        _旧得间解密执行器.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
得间解密执行器: ProcessPoolExecutor | None = None
_得间解密信号量: asyncio.Semaphore | None = None
_得间解密失败截止时间 = 0.0


async def 异步解密得间正文(*参数: Any) -> Tuple[str, float]:
    global 得间解密执行器, _得间解密信号量, _得间解密失败截止时间
    循环 = asyncio.get_running_loop()
    if 循环.time() < _得间解密失败截止时间:
        raise RuntimeError("得间解密执行器冷却中")
    if 得间解密执行器 is None:
        # AstrBot 可把依赖装到 --target 目录；loky 启动器须在恢复 sys.path 前找到库。
        依赖目录 = str(Path(loky.__file__).resolve().parent.parent)
        子进程路径 = [路径 for 路径 in os.environ.get("PYTHONPATH", "").split(os.pathsep) if 路径]
        if 依赖目录 not in 子进程路径:
            os.environ["PYTHONPATH"] = os.pathsep.join([依赖目录, *子进程路径])
        # loky 不重新执行 AstrBot 主模块，避免子进程重复加载框架与数据库。
        得间解密执行器 = ProcessPoolExecutor(
            max_workers=得间解密最大动态并发数,
            timeout=60,
            env={"OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
        )
        _得间解密信号量 = asyncio.Semaphore(得间解密最大动态并发数 * 2)
    执行器 = 得间解密执行器
    信号量 = _得间解密信号量
    assert 信号量 is not None
    try:
        async with 信号量:
            任务 = await asyncio.to_thread(执行器.submit, 解密得间正文并计时, *参数)
            return await asyncio.wrap_future(任务, loop=循环)
    except BrokenProcessPool:
        if 得间解密执行器 is 执行器:
            关闭得间资源()
            _得间解密失败截止时间 = 循环.time() + 10
            logger.warning("得间解密执行器异常：错误分类=工作进程退出, 冷却=10秒")
        raise

# ===== 得间协议与解密（原 _得间源码） =====

BASE = "https://dj.palmestore.com"
PACKAGE = "com.chaozh.iReader.dj"
APP_UA = (
    "Mozilla/5.0 (Linux; Android 9; Pixel 4 Build/PQ3B.190801.002; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120 Mobile Safari/537.36"
)

APP_DIR = Path(__file__).resolve().parent

EMBEDDED_KEY_PK8_B64 = "MIICdQIBADANBgkqhkiG9w0BAQEFAASCAl8wggJbAgEAAoGBAMXGjyS3p+3AVnlBJe5VQ6tC9inh8tVBve4r+yBjC5HQD6th2n3tSyuNVYaNRAFSEq+OENwnwwhjbYUnjLWb+qZscB43K1+4/WlKdvfgwQVXm0ZQ2+jMBf+165UBEEuuWT2WqXeKkkUqPQta5lrt4eFfbo53JcOO4D5fDSGQS5bZAgMBAAECgYAor4I/AXEQXeLsKtTMxMmY77uIPi0gZdfWqUGOFhIJOw4eKZEzGp++I+MWPPVieCnT55vcTmm2zg13uP0fVykmukWqZszG/ZNpPKYleOqnZOqQj7O3au8Ywz18F/pqD++PsUzxRVeXxSOOwmjQ0D2Pe/9yutz62pyiFGAzDsaI6QJBAMn8DeBT3AtcWuONdiHL3yC4NkGJDdyBbMOaWyvrcvUUZr13uS9mZO6pLTN6v9tkmPUdvYxcPTJ9wdGR7NcNPDsCQQD6qluGI2VAlz4s5UoDnelFKrwDPeiruE3I6wsrasK6h37DsAE6OrQgx2dm4yH7ntJHUlJCZ5ay1EBNfEexgQv7AkA1r2vUwxVKY7q4nqHWa8SbgrrRAmePw0qwVreC3erJHyoLk+XBpnqPQKIF+8tAueU5yTTXOLD/WZOJazrDEf5/AkBpwG+Ggu5Xtrcbd8ynA/sDHElf0MGVmNbwOgFnWs42pa1cX6fU6ilOXvIH3TFcF6A9SMS9kThpz9QlHJaek4P7AkAavQillA/wnrha9GsK5UFmzmwNfkjLLW4psAUsXOsqFXWMoxTd0xWuSbuVOzERpbFMBl1VoZQmD9BLSVOTNe+v"

DEFAULT_SESSION: Dict[str, str] = {
    "p3": "25272056",
}

def p7_encrypt(s: str) -> str:
    out = ["__"]
    repl = {1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1, 0: 0}
    for ch in s or "":
        if "0" <= ch <= "9":
            out.append(str((repl[ord(ch) - 48] * 3) % 10))
        else:
            out.append(ch)
    return "".join(out)


def load_session() -> Dict[str, str]:
    data = DEFAULT_SESSION.copy()
    # 生成 8 位随机数字作为 usr
    data["usr"] = str(random.randint(10000000, 99999999))
    # 补全必要的派生字段（这些是算法必须的，不补会出错）
    if not data.get("p7"):
        data["p7"] = p7_encrypt("1234567890abcdef")
    if not data.get("p31"):
        data["p31"] = data["p7"]
    if not data.get("p30"):
        data["p30"] = "__"
    if not data.get("devId"):
        data["devId"] = data.get("p7", "")
    return data


def sorted_param_str(params: Dict[str, Any]) -> str:
    parts = []
    for k in sorted(str(x) for x in params.keys() if str(x)):
        v = params.get(k, "")
        if v is None or str(v) == "":
            continue
        parts.append(f"{k}={v}")
    return "&".join(parts)


_SIGN_KEY = None


def app_sign(sorted_s: str) -> str:
    global _SIGN_KEY
    if _SIGN_KEY is None:
        raw = base64.b64decode(EMBEDDED_KEY_PK8_B64)
        _SIGN_KEY = serialization.load_der_private_key(raw, password=None)
    sig = _SIGN_KEY.sign(sorted_s.encode("utf-8"), padding.PKCS1v15(), hashes.SHA1())
    return base64.b64encode(sig).decode("ascii")


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        m = re.search(r"\d+", str(v or ""))
        return int(m.group(0)) if m else default


def extract_token_b64(auth: Any, chapter_id: int) -> str:
    if not isinstance(auth, dict):
        raise RuntimeError("auth error")
    body = auth.get("body")
    if not isinstance(body, dict):
        raise RuntimeError("no auth body")
    key = f"chapter_{chapter_id}"
    node = body.get(key)
    if isinstance(node, dict) and node.get("token"):
        return str(node["token"])
    if body.get("token"):
        return str(body["token"])
    for value in body.values():
        if isinstance(value, dict) and value.get("token"):
            return str(value["token"])
    raise RuntimeError("no token")


def 创建得间HTTP会话(并发数: int) -> aiohttp.ClientSession:
    并发数 = max(1, int(并发数 or 1))
    connector = aiohttp.TCPConnector(
        limit=并发数,
        limit_per_host=并发数,
        keepalive_timeout=30,
        ttl_dns_cache=300,
        ssl=False,
    )
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=120)
    return aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={"User-Agent": APP_UA, "Accept": "application/json,text/plain,*/*"},
    )


async def 异步请求得间JSON(
    HTTP会话: aiohttp.ClientSession,
    方法: str,
    地址: str,
    *,
    参数: Optional[Dict[str, Any]] = None,
    表单: Optional[Dict[str, Any]] = None,
    请求信号量: Optional[asyncio.Semaphore] = None,
    超时秒数: int = 20,
) -> Any:
    超时 = aiohttp.ClientTimeout(total=max(1, int(超时秒数 or 20)))

    async def 请求() -> bytes:
        async with HTTP会话.request(
            方法,
            地址,
            params=参数,
            data=表单,
            timeout=超时,
        ) as 响应:
            响应.raise_for_status()
            return await 响应.read()

    if 请求信号量 is None:
        原始响应 = await 请求()
    else:
        async with 请求信号量:
            原始响应 = await 请求()
    if not 原始响应:
        return {}
    try:
        return json.loads(原始响应.decode("utf-8-sig", "replace"))
    except json.JSONDecodeError as 异常:
        raise RuntimeError("得间接口响应不是JSON") from 异常


async def 异步下载得间字节(
    HTTP会话: aiohttp.ClientSession,
    地址: str,
    请求信号量: Optional[asyncio.Semaphore] = None,
) -> bytes:
    超时 = aiohttp.ClientTimeout(total=120)

    async def 请求() -> bytes:
        async with HTTP会话.get(地址, timeout=超时) as 响应:
            响应.raise_for_status()
            return await 响应.read()

    if 请求信号量 is None:
        return await 请求()
    async with 请求信号量:
        return await 请求()


class 得间异步客户端:
    """参考得间.py 的 DejianClient，仅将 requests 会话替换为共享 aiohttp 会话。"""

    def __init__(
        self,
        HTTP会话: aiohttp.ClientSession,
        请求信号量: asyncio.Semaphore,
    ) -> None:
        self.HTTP会话 = HTTP会话
        self.请求信号量 = 请求信号量
        self.会话参数 = load_session()

    def 账号参数(self) -> Dict[str, str]:
        参数: Dict[str, str] = {}
        for 键 in ("zyeid", "usr", "rgt", "p1"):
            值 = self.会话参数.get(键, "")
            if 值 or 键 in ("usr", "rgt", "p1"):
                参数[键] = 值
        if self.会话参数.get("usr"):
            参数["ku"] = self.会话参数["usr"]
        return 参数

    def 设备参数(self) -> Dict[str, str]:
        键列表 = (
            "pc",
            "p2",
            "p3",
            "p4",
            "p5",
            "p7",
            "p9",
            "p12",
            "p16",
            "p21",
            "p22",
            "p25",
            "p26",
            "p28",
            "p29",
            "p30",
            "p31",
            "p33",
            "p34",
            "firm",
            "d1",
        )
        return {键: self.会话参数.get(键, "") for 键 in 键列表 if 键 in self.会话参数}

    def 附加参数(self, 参数: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        结果: Dict[str, Any] = {}
        结果.update(self.账号参数())
        结果.update(self.设备参数())
        if 参数:
            结果.update(参数)
        return 结果

    def 签名参数(self, 参数: Dict[str, Any]) -> Dict[str, Any]:
        结果 = dict(参数)
        结果["timestamp"] = str(int(time.time() * 1000))
        结果["sign"] = app_sign(sorted_param_str(结果))
        return 结果

    async def 获取JSON(
        self,
        路径或地址: str,
        参数: Optional[Dict[str, Any]] = None,
        *,
        需要公共参数: bool = True,
    ) -> Any:
        地址 = 路径或地址 if 路径或地址.startswith("http") else f"{BASE}{路径或地址}"
        查询参数 = self.附加参数(参数) if 需要公共参数 else dict(参数 or {})
        return await 异步请求得间JSON(
            self.HTTP会话,
            "GET",
            地址,
            参数=查询参数,
            请求信号量=self.请求信号量,
        )

    async def 提交JSON(self, 路径或地址: str, 表单: Dict[str, Any]) -> Any:
        地址 = 路径或地址 if 路径或地址.startswith("http") else f"{BASE}{路径或地址}"
        return await 异步请求得间JSON(
            self.HTTP会话,
            "POST",
            地址,
            参数=self.附加参数({}),
            表单=表单,
            请求信号量=self.请求信号量,
        )

    async def 下载(self, 地址: str) -> bytes:
        return await 异步下载得间字节(self.HTTP会话, 地址, self.请求信号量)

    async def 获取批量下载清单(self, 书籍编号: str) -> Dict[str, Any]:
        信息 = await self.获取JSON(
            "/zybook3/u/p/api.php",
            {"Act": "batchDownloadChapteres", "bid": str(书籍编号)},
        )
        正文 = 信息.get("body") if isinstance(信息, dict) else None
        地址 = str(正文.get("downUrl") or "").strip() if isinstance(正文, dict) else ""
        if not 地址:
            raise RuntimeError("no downUrl")
        return {
            "bookId": str(书籍编号),
            "downUrl": 地址,
            "maxChapId": _to_int(正文.get("maxChapId")),
            "downloadCount": _to_int(正文.get("downloadCount")),
        }

    async def 获取批量章节清单(
        self,
        书籍编号: str,
        批量下载清单: Optional[Dict[str, Any]] = None,
        页回调: Optional[Callable[[List[Dict[str, Any]]], Awaitable[None]]] = None,
    ) -> List[Dict[str, Any]]:
        """使用 batchDownloadChapteres 返回的地址一次读取整本正文地址清单。"""
        清单 = 批量下载清单 or await self.获取批量下载清单(书籍编号)
        基础地址 = str(清单.get("downUrl") or "").strip()
        if not 基础地址:
            raise RuntimeError("no batch downUrl")
        async def 获取一页(当前章节: int) -> Tuple[List[Dict[str, Any]], bool]:
            分隔符 = "&" if "?" in 基础地址 else "?"
            地址 = (
                f"{基础地址}{分隔符}{urllib.parse.urlencode({'startChapID': 当前章节})}"
            )
            for 轮次 in range(1, 得间正文重试次数 + 1):
                try:
                    信息 = await self.获取JSON(地址, 需要公共参数=False)
                    break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if 轮次 == 得间正文重试次数:
                        raise
                    await asyncio.sleep(0.1 * 轮次)
            正文 = 信息.get("body") if isinstance(信息, dict) else None
            if not isinstance(正文, dict):
                raise RuntimeError("no chapter list body")
            章节列表 = 正文.get("downInfo") or []
            if not isinstance(章节列表, list):
                raise RuntimeError("bad chapter list")
            有效章节 = [项 for 项 in 章节列表 if isinstance(项, dict) and _to_int(项.get("chapterId")) > 0]
            if 页回调 is not None:
                await 页回调(有效章节)
            return 有效章节, bool(正文.get("end"))

        结果, 已结束 = await 获取一页(1)
        if not 结果 or 已结束:
            return 结果
        最大章节 = _to_int(清单.get("maxChapId"))
        最后章节 = _to_int(结果[-1].get("chapterId"))
        页大小 = len(结果)
        首章 = _to_int(结果[0].get("chapterId"))
        首包章节号 = [_to_int(项.get("chapterId")) for 项 in 结果]
        if 最大章节 >= 最后章节 and 首包章节号 == list(range(首章, 最后章节 + 1)):
            页起点 = iter(range(最后章节 + 1, 最大章节 + 1, 页大小))
            页结果: Dict[int, List[Dict[str, Any]]] = {}

            async def 获取后续页() -> None:
                for 起点 in 页起点:
                    当前章节 = 起点
                    终点 = min(最大章节, 起点 + 页大小 - 1)
                    当前结果: List[Dict[str, Any]] = []
                    while 当前章节 <= 终点:
                        章节列表, 已结束 = await 获取一页(当前章节)
                        if not 章节列表:
                            break
                        新最后章节 = _to_int(章节列表[-1].get("chapterId"))
                        if 新最后章节 < 当前章节:
                            raise RuntimeError("chapter list did not advance")
                        当前结果.extend(章节列表)
                        当前章节 = 新最后章节 + 1
                        if 已结束:
                            break
                    页结果[起点] = 当前结果

            任务 = [asyncio.create_task(获取后续页()) for _ in range(得间清单最大并发数)]
            try:
                await asyncio.gather(*任务)
            finally:
                for 任务项 in 任务:
                    任务项.cancel()
                await asyncio.gather(*任务, return_exceptions=True)
            for 起点 in sorted(页结果):
                结果.extend(页结果[起点])
        else:
            # 无法从首包确认连续分页宽度时，继续按实际返回的章节号推进。
            while 最后章节 > 0:
                章节列表, 已结束 = await 获取一页(最后章节 + 1)
                if not 章节列表:
                    break
                新最后章节 = _to_int(章节列表[-1].get("chapterId"))
                if 新最后章节 <= 最后章节:
                    raise RuntimeError("chapter list did not advance")
                结果.extend(章节列表)
                最后章节 = 新最后章节
                if 已结束 or (最大章节 > 0 and 最后章节 >= 最大章节):
                    break
        唯一章节: Dict[int, Dict[str, Any]] = {}
        for 项 in 结果:
            唯一章节[_to_int(项.get("chapterId"))] = 项
        return [唯一章节[编号] for 编号 in sorted(唯一章节)]

    async def 获取章节授权(self, 书籍编号: str, 章节编号: int) -> Any:
        表单 = self.签名参数(
            {
                "bookId": str(书籍编号),
                "chapterId": str(int(章节编号)),
                "devId": self.会话参数.get("devId", ""),
                "usrName": self.会话参数.get("usr", ""),
            }
        )
        表单.update({"type": "0", "fid": "72"})
        return await self.提交JSON("/dj_drm/djdrm/getAuthChapter", 表单)


async def 异步下载得间章节正文(
    HTTP会话: aiohttp.ClientSession,
    书籍编号: str,
    章节编号: int,
    章节项: Dict[str, Any],
    请求信号量: asyncio.Semaphore,
    解密信号量: asyncio.Semaphore,
    计时统计: Optional[Dict[str, float]] = None,
) -> str:
    """使用批量清单中的正文地址；授权接口仍按平台协议为每章签发密钥。"""
    当前客户端 = 得间异步客户端(HTTP会话, 请求信号量)
    for 重试轮次 in range(1, 得间正文重试次数 + 1):
        try:
            用户名 = str(当前客户端.会话参数.get("usr") or "")
            设备号 = str(当前客户端.会话参数.get("devId") or "")
            if not 用户名 or not 设备号:
                raise RuntimeError("bad session")
            正文地址 = str(
                章节项.get("url")
                or 章节项.get("downUrl")
                or 章节项.get("downloadUrl")
                or ""
            ).strip()
            if not 正文地址:
                raise RuntimeError("no chapter url")
            开始 = time.perf_counter()
            授权结果 = await 当前客户端.获取章节授权(书籍编号, 章节编号)
            if 计时统计 is not None:
                计时统计["auth"] += time.perf_counter() - 开始
            授权令牌 = extract_token_b64(授权结果, 章节编号)
            开始 = time.perf_counter()
            正文数据 = await 当前客户端.下载(正文地址)
            if 计时统计 is not None:
                计时统计["body"] += time.perf_counter() - 开始
            async with 解密信号量:
                正文, 解密耗时 = await 异步解密得间正文(
                    正文数据,
                    授权令牌,
                    用户名,
                    设备号,
                )
                if 计时统计 is not None:
                    计时统计["decrypt"] += 解密耗时
                return 正文
        except Exception as 异常:
            logger.debug(
                f"得间章节下载重试：书籍编号={书籍编号}, 章节编号={章节编号}, "
                f"轮次={重试轮次}, 错误类型={type(异常).__name__}"
            )
            if 重试轮次 < 得间正文重试次数:
                await asyncio.sleep(0.05 * 重试轮次)
    return ""


def generate_search_usr(length: int = 6) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def 解析得间搜索数据(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict) or data.get("code", -1) != 0:
        return {"success": True, "count": 0, "results": [], "raw": data}

    body = data.get("body") or {}
    book = body.get("book") if isinstance(body, dict) else {}
    datas = (book or {}).get("datas") if isinstance(book, dict) else []
    if not isinstance(datas, list):
        datas = []

    results: List[Dict[str, Any]] = []
    for item in datas:
        if not isinstance(item, dict):
            continue
        info = item.get("data_info") or {}
        if not isinstance(info, dict) or not info:
            continue

        raw_name = str(info.get("bookName") or info.get("displayBookName") or "")
        title = raw_name.strip("《》")
        title = re.sub(r"^《|》$", "", raw_name)
        if not title:
            title = raw_name

        complete_state = info.get("completeState") or "N"
        status = "已完结" if complete_state == "Y" else "连载中"
        tag_list = info.get("tagList") or []
        if not isinstance(tag_list, list):
            tag_list = []

        kind_parts = ["得间"]
        if tag_list:
            kind_parts.extend(str(x) for x in tag_list if x)
        kind_parts.append(status)

        results.append(
            {
                "title": title,
                "author": str(info.get("bookAuthor") or ""),
                "abstract": str(info.get("bookDescription") or ""),
                "cover_url": str(info.get("picUrl") or ""),
                "book_id": str(info.get("bookId") or ""),
                "source": "得间",
                "kind": ",".join(kind_parts),
                "word_count": "",
                "last_chapter": f"得间_{status}",
            }
        )

    return {"success": True, "count": len(results), "results": results}


async def 异步搜索得间书籍(
    HTTP会话: aiohttp.ClientSession,
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    current_page = max(1, int(page or 1))
    data = await 异步请求得间JSON(
        HTTP会话,
        "GET",
        f"{BASE}/zybk/api/search/freeapp/book",
        参数={
            "word": query,
            "type": "book,listen",
            "pageSize": page_size,
            "currentPage": current_page,
            "usr": generate_search_usr(),
            "p2": "124013",
            "p3": "17418056",
        },
    )
    return 解析得间搜索数据(data)


def 解析得间书籍详情(data: Any, bid: str) -> Dict[str, Any]:
    if not isinstance(data, dict) or data.get("code", -1) != 0:
        业务码 = data.get("code") if isinstance(data, dict) else None
        return {
            "success": False,
            "detail": {},
            "raw": data,
            "error_code": 业务码 if isinstance(业务码, int) else "未知",
            "error_category": "书籍无详情" if 业务码 == 404 else "详情接口拒绝",
        }

    body = data.get("body") or {}
    info = body.get("bookInfo") if isinstance(body, dict) else {}
    if not isinstance(info, dict) or not info.get("bookId") or not info.get("bookName"):
        return {
            "success": False, "detail": {}, "raw": data,
            "error_code": 0, "error_category": "缺少书籍信息",
        }
    if str(info["bookId"]) != str(bid):
        return {
            "success": False, "detail": {}, "raw": data,
            "error_code": 0, "error_category": "书籍编号不一致",
        }

    complete_state = info.get("completeState") or "N"
    status = "已完结" if complete_state == "Y" else "连载中"
    cats = info.get("categorys") or []
    if not isinstance(cats, list):
        cats = []
    cat_names = [str(c["name"]) for c in cats if isinstance(c, dict) and c.get("name")]

    price = info.get("priceInfo") or {}
    if not isinstance(price, dict):
        price = {}

    detail = {
        "book_id": str(info.get("bookId") or bid),
        "title": str(info.get("bookName") or ""),
        "author": str(info.get("author") or ""),
        "abstract": str(info.get("desc") or ""),
        "cover_url": str(info.get("picUrl") or ""),
        "word_count": str(info.get("wordCount") or info.get("wordNum") or ""),
        "status": status,
        "category": ",".join(cat_names),
        "from_source": str(info.get("fromSource") or ""),
        "is_free": bool(price.get("isFree")),
        "last_chapter_time": str(info.get("lastChapterTime") or ""),
        "raw_book_info": info,
    }
    return {"success": True, "detail": detail, "raw": data}


async def 异步获取得间书籍详情(
    HTTP会话: aiohttp.ClientSession,
    bid: str,
) -> Dict[str, Any]:
    data = await 异步请求得间JSON(
        HTTP会话,
        "GET",
        f"{BASE}/zybk/api/detail/index",
        参数={"p3": "17111111", "p2": "1", "p4": "1", "bid": str(bid)},
    )
    return 解析得间书籍详情(data, bid)


async def 异步获取得间批量下载清单(
    HTTP会话: aiohttp.ClientSession,
    bid: str,
) -> Dict[str, Any]:
    """下载前读取批量正文地址，避免按章节重复请求批量清单。"""
    try:
        客户端 = 得间异步客户端(HTTP会话, asyncio.Semaphore(得间清单最大并发数))
        清单 = await 客户端.获取批量下载清单(bid)
        清单["chapters"] = await 客户端.获取批量章节清单(bid, 清单)
        return 清单
    except Exception as 异常:
        logger.debug(
            f"得间可下载章节范围获取失败：书籍编号={bid}, "
            f"错误类型={type(异常).__name__}"
        )
        return {}


def 解析得间章节目录(xml_text: str) -> Dict[str, Any]:
    if not xml_text or "<cp>" not in xml_text:
        return {"success": False, "count": 0, "chapters": [], "raw": xml_text}

    total_record = 0
    m_total = re.search(r"<totalRecord>(\d+)</totalRecord>", xml_text)
    if m_total:
        total_record = int(m_total.group(1))

    chapters: List[Dict[str, Any]] = [
        {
            "chapter_id": int(m.group(1)),
            "cs": int(m.group(2)),
            "word_count": int(m.group(3)),
            "title": re.sub(r"\s+", " ", m.group(4)).strip(),
        }
        for m in re.finditer(
            r"<cp>\s*<id>(\d+)</id>\s*<cs>(\d+)</cs>\s*<wc>(\d+)</wc>.*?<cn>(.*?)</cn>",
            xml_text,
            flags=re.S,
        )
    ]

    if not chapters:
        ids = re.findall(r"<cp>\s*<id>(\d+)</id>", xml_text)
        titles = re.findall(r"<cn>(.*?)</cn>", xml_text)
        for i, cid in enumerate(ids):
            chapters.append(
                {
                    "chapter_id": int(cid),
                    "cs": 0,
                    "word_count": 0,
                    "title": titles[i].strip() if i < len(titles) else "",
                }
            )

    return {
        "success": True,
        "count": len(chapters),
        "total_record": total_record or len(chapters),
        "chapters": chapters,
        "raw": xml_text,
    }


async def 异步获取得间章节目录(
    HTTP会话: aiohttp.ClientSession,
    bid: str,
) -> Dict[str, Any]:
    async with HTTP会话.get(
        f"{BASE}/zybook/u/p/api.php",
        params={"Act": "getChapterListVersion", "p4": "501656", "bid": str(bid)},
        timeout=aiohttp.ClientTimeout(total=20),
    ) as response:
        response.raise_for_status()
        xml_text = await response.text(encoding="utf-8", errors="replace")
    return 解析得间章节目录(xml_text)


# ===== 业务封装 =====

# 每个正文下载流程包含 0% 起始行，因此最多再输出 4 个进度节点。
进度日志分段数 = 25
得间域名正则 = re.compile(r"(?:^|\.)(?:palmestore|zhangyue|ireader|idejian)\.com$", re.I)
链接正则 = re.compile(r"https?://[^\s'\"<>]+", re.I)
路径编号正则 = re.compile(r"/(?:book|detail|books?)/([0-9]{5,})(?=/|\.html?$|$)", re.I)


def 计算得间正文并发数(章节总数: int) -> int:
    return max(1, min(得间正文最大并发数, int(章节总数 or 0)))


def 得间存在未购买章节(目录: list[dict[str, Any]], 批量清单: Dict[str, Any]) -> bool:
    """根据 App 清单判断整本是否含当前会话不可访问的章节。"""
    if not 批量清单 or not 目录:
        return False
    总章节数 = len(目录)
    可下载章节数 = _to_int(批量清单.get("downloadCount"))
    最大可下载章节号 = _to_int(批量清单.get("maxChapId"))
    目录章节号 = [_to_int(章节.get("id") or 章节.get("chapter_id")) for 章节 in 目录]
    有效章节号 = [章节号 for 章节号 in 目录章节号 if 章节号 > 0]
    if 可下载章节数 > 0 and 可下载章节数 < 总章节数:
        return True
    if 最大可下载章节号 > 0 and 有效章节号:
        return 最大可下载章节号 < max(有效章节号)
    return False


def 获取得间小说回复流(
    event: Any, 命令文本: str, 配置: Any = None
) -> AsyncIterator[Any] | None:
    来源 = 提取直接得间来源(命令文本) or 提取事件得间来源(event)
    if 来源 is None:
        return None
    return 生成下载回复流(event, 来源, 配置)


async def 生成下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取书籍编号(来源)
    if not 书籍编号:
        logger.warning("得间小说链接解析失败：阶段=link, 错误分类=链接缺少书籍编号")
        yield "链接不完整，请重新分享或发送书名找书"
        return
    try:
        async with 创建得间HTTP会话(2) as HTTP会话:
            预检开始 = time.perf_counter()
            详情包, 目录包 = await asyncio.gather(
                异步获取得间书籍详情(HTTP会话, 书籍编号),
                异步获取得间章节目录(HTTP会话, 书籍编号),
            )
        if not 详情包.get("success"):
            logger.warning(
                f"得间小说详情失败：书籍编号={书籍编号}, 阶段=detail, "
                f"业务码={详情包.get('error_code', '未知')}, "
                f"错误分类={详情包.get('error_category', '详情异常')}"
            )
            yield "下载失败 请重试"
            return
        详情 = 详情包.get("detail") or {}
        目录 = 目录包.get("chapters") or []
        if not 目录 or _to_int(目录包.get("total_record"), len(目录)) != len(目录):
            logger.warning(f"得间小说目录失败：书籍编号={书籍编号}")
            yield "下载失败 请重试"
            return
        书名 = str(详情.get("title") or "未知")
        作者 = str(详情.get("author") or "未知")
        状态 = "完结" if "完结" in str(详情.get("status") or "") else "连载"
        字数 = 格式化字数(详情.get("word_count"))
        logger.info(
            f"得间小说开始下载：书籍编号={书籍编号}, 书名={书名}, 作者={作者}, "
            f"章节数={len(目录)}, 详情目录耗时={time.perf_counter() - 预检开始:.3f}秒"
        )
        yield "\n".join(
            [
                f"书名：{书名}",
                f"作者：{作者}",
                f"状态：{状态}",
                f"章节：{len(目录)} 章",
                f"字数：{字数}",
                "",
                "正在下载中请稍等.....",
            ]
        )

        async with 创建得间HTTP会话(得间清单最大并发数) as HTTP会话:
            清单客户端 = 得间异步客户端(HTTP会话, asyncio.Semaphore(得间清单最大并发数))
            批量清单 = await 清单客户端.获取批量下载清单(书籍编号)
            if 得间存在未购买章节(目录, 批量清单):
                可下载章节数 = _to_int(批量清单.get("downloadCount"))
                logger.warning(
                    f"得间小说包含未购买章节：书籍编号={书籍编号}, "
                    f"可下载章节数={可下载章节数}, 总章节数={len(目录)}"
                )
                yield "该书包含未购买章节，暂不支持下载"
                return
            章节结果 = await 下载得间章节流水线(书籍编号, 目录, 清单客户端, 批量清单)
        成功 = [x for x in 章节结果 if x.get("content")]
        if len(成功) != len(目录):
            logger.warning(
                f"得间小说下载失败：书籍编号={书籍编号}, 成功={len(成功)}, 总数={len(目录)}"
            )
            yield "下载失败 请重试"
            return

        文件名, 文件内容 = await asyncio.to_thread(
            生成小说文件, 书籍编号, 书名, 作者, 状态, 字数, 章节结果
        )
        发送结果 = await 准备发送文本文件(
            event, 文件名, 文件内容, 配置, 书名=书名, 作者=作者
        )
        if 发送结果.get("sent"):
            启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        降级 = str(发送结果.get("fallback_text") or "")
        if 降级:
            try:
                yield 降级
            finally:
                启动百度后台上传并清理(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        logger.warning(
            f"得间小说完成消息发送失败：书籍编号={书籍编号}, 错误={发送结果.get('error')}"
        )
        yield "文件发送失败，请稍后再试"
    except Exception as exc:
        logger.warning(f"得间小说下载失败：来源={来源}, 错误类型={type(exc).__name__}")
        yield "下载失败 请重试"


async def 下载得间章节流水线(
    书籍编号: str,
    目录: list[dict[str, Any]],
    清单客户端: 得间异步客户端,
    批量清单: Dict[str, Any],
) -> list[dict[str, str]]:
    """地址分页与单章授权/正文重叠执行，队列提供背压且最终必须完整。"""
    并发数 = 计算得间正文并发数(len(目录))
    地址队列: asyncio.Queue[Dict[str, Any] | None] = asyncio.Queue(maxsize=并发数 * 2)
    清单开始 = time.perf_counter()

    async def 放入地址(章节列表: List[Dict[str, Any]]) -> None:
        for 章节项 in 章节列表:
            await 地址队列.put(章节项)

    async def 获取清单() -> None:
        章节列表 = await 清单客户端.获取批量章节清单(书籍编号, 批量清单, 放入地址)
        logger.info(
            f"得间小说正文地址清单完成：书籍编号={书籍编号}, "
            f"地址数={len(章节列表)}, 并发数={得间清单最大并发数}, "
            f"耗时={time.perf_counter() - 清单开始:.3f}秒, 与正文下载重叠=开启"
        )
        for _ in range(并发数):
            await 地址队列.put(None)

    清单任务 = asyncio.create_task(获取清单())
    正文任务 = asyncio.create_task(下载全部章节(书籍编号, 目录, {}, 地址队列))
    try:
        _, 章节结果 = await asyncio.gather(清单任务, 正文任务)
        return 章节结果
    finally:
        清单任务.cancel()
        正文任务.cancel()
        await asyncio.gather(清单任务, 正文任务, return_exceptions=True)


async def 下载全部章节(
    书籍编号: str,
    目录: list[dict[str, Any]],
    批量清单: Dict[str, Any],
    地址队列: Optional[asyncio.Queue[Dict[str, Any] | None]] = None,
) -> list[dict[str, str]]:
    总数 = len(目录)
    结果: list[dict[str, str] | None] = [None] * 总数
    章节下标表: Dict[int, List[int]] = {}
    无效章节下标: List[int] = []
    for 下标, 章节 in enumerate(目录):
        章节编号 = _to_int(章节.get("id") or 章节.get("chapter_id"))
        if 章节编号 > 0:
            章节下标表.setdefault(章节编号, []).append(下标)
        else:
            无效章节下标.append(下标)
    if 无效章节下标 or not 章节下标表 or len(章节下标表) != 总数:
        logger.warning(
            f"得间小说目录章节编号无效或重复：书籍编号={书籍编号}, "
            f"无效数={len(无效章节下标)}, 唯一章节数={len(章节下标表)}, 总章节数={总数}"
        )
        if 地址队列 is not None:
            raise RuntimeError("得间目录章节编号无效或重复")
        return []

    批量章节 = 批量清单.get("chapters") if isinstance(批量清单, dict) else None
    if 地址队列 is None and not isinstance(批量章节, list):
        logger.warning(f"得间小说批量章节地址缺失：书籍编号={书籍编号}")
        return []
    批量章节表: Dict[int, Dict[str, Any]] = {}
    for 项 in 批量章节 or []:
        if not isinstance(项, dict):
            continue
        章节编号 = _to_int(项.get("chapterId") or 项.get("chapter_id"))
        正文地址 = str(
            项.get("url") or 项.get("downUrl") or 项.get("downloadUrl") or ""
        ).strip()
        if 章节编号 > 0 and 正文地址:
            批量章节表[章节编号] = 项
    缺失章节 = sorted(章节编号 for 章节编号 in 章节下标表 if 章节编号 not in 批量章节表)
    if 地址队列 is None and (缺失章节 or len(批量章节表) != len(章节下标表)):
        logger.warning(
            f"得间小说批量章节地址不完整：书籍编号={书籍编号}, "
            f"目录章节数={len(章节下标表)}, 批量地址数={len(批量章节表)}, 缺失数={len(缺失章节)}"
        )
        return []

    实际正文并发数 = 计算得间正文并发数(len(章节下标表))
    解密并发数 = max(1, min(实际正文并发数, 得间解密最大动态并发数))
    完成 = len(无效章节下标)
    成功 = 0
    上次日志百分比 = 0
    进度锁 = asyncio.Lock()
    请求信号量 = asyncio.Semaphore(实际正文并发数)
    解密信号量 = asyncio.Semaphore(解密并发数)
    正文模式 = "单章正文流水线" if 地址队列 is not None else "单章正文"
    下载开始 = time.perf_counter()
    计时统计 = {"auth": 0.0, "body": 0.0, "decrypt": 0.0}
    async with 创建得间HTTP会话(实际正文并发数) as HTTP会话:
        logger.info(
            f"得间小说章节进度：书籍编号={书籍编号}, 进度=0/{总数}, 百分比=0%, "
            f"模式={正文模式}, 并发数={实际正文并发数}, 最大并发数={得间正文最大并发数}, "
            f"HTTP会话复用=开启, 每章授权=开启, 解密并发数={解密并发数}, 重试次数={得间正文重试次数}"
        )

        async def 下载一章(章节编号: int, 下标列表: List[int]) -> None:
            nonlocal 完成, 成功, 上次日志百分比
            正文 = (
                await 异步下载得间章节正文(
                    HTTP会话,
                    书籍编号,
                    章节编号,
                    批量章节表[章节编号],
                    请求信号量,
                    解密信号量,
                    计时统计,
                )
            ).strip()
            for 下标 in 下标列表:
                章 = 目录[下标]
                标题 = str(章.get("title") or 章.get("cn") or f"第{章节编号}章")
                结果[下标] = {"title": 标题, "content": 正文, "id": str(章节编号)}
            async with 进度锁:
                完成 += len(下标列表)
                if 正文:
                    成功 += len(下标列表)
                当前百分比 = int(完成 * 100 / max(总数, 1))
                if 完成 == 总数 or 当前百分比 >= min(
                    100, 上次日志百分比 + 进度日志分段数
                ):
                    logger.info(
                        f"得间小说章节进度：书籍编号={书籍编号}, 进度={完成}/{总数}, "
                        f"百分比={当前百分比}%, 成功={成功}, 失败={完成 - 成功}"
                    )
                    上次日志百分比 = 当前百分比

        待下载章节 = iter(章节下标表.items())

        async def 下载工作流() -> None:
            if 地址队列 is None:
                for 章节编号, 下标列表 in 待下载章节:
                    await 下载一章(章节编号, 下标列表)
                return
            while True:
                章节项 = await 地址队列.get()
                if 章节项 is None:
                    return
                章节编号 = _to_int(章节项.get("chapterId") or 章节项.get("chapter_id"))
                正文地址 = str(章节项.get("url") or 章节项.get("downUrl") or 章节项.get("downloadUrl") or "").strip()
                if 章节编号 not in 章节下标表 or not 正文地址:
                    raise RuntimeError("得间正文地址不在目录内或为空")
                if 章节编号 in 批量章节表:
                    continue
                批量章节表[章节编号] = 章节项
                await 下载一章(章节编号, 章节下标表[章节编号])

        任务 = [asyncio.create_task(下载工作流()) for _ in range(实际正文并发数)]
        try:
            await asyncio.gather(*任务)
        finally:
            for 任务项 in 任务:
                任务项.cancel()
            await asyncio.gather(*任务, return_exceptions=True)
    输出: list[dict[str, str]] = []
    for 下标, 章 in enumerate(目录):
        已下载 = 结果[下标]
        if 已下载 is None:
            章节编号 = _to_int(章.get("id") or 章.get("chapter_id"))
            已下载 = {
                "title": str(章.get("title") or 章.get("cn") or f"第{章节编号}章"),
                "content": "",
                "id": str(章节编号),
            }
        输出.append(已下载)
    logger.info(
        f"得间小说章节下载完成：书籍编号={书籍编号}, 成功={成功}, 总数={总数}, "
        f"模式={正文模式}, 并发数={实际正文并发数}, 最大并发数={得间正文最大并发数}, "
        f"HTTP会话复用=开启, 每章授权=开启, 解密进程数={解密并发数}, "
        f"总耗时={time.perf_counter() - 下载开始:.3f}秒, "
        f"授权累计={计时统计['auth']:.3f}秒, 正文请求累计={计时统计['body']:.3f}秒, "
        f"纯解密累计={计时统计['decrypt']:.3f}秒"
    )
    if len(批量章节表) != 总数:
        logger.warning(
            f"得间小说流水线章节地址不完整：书籍编号={书籍编号}, "
            f"地址数={len(批量章节表)}, 总数={总数}"
        )
        return []
    return 输出


def 生成小说文件(
    书籍编号: str,
    书名: str,
    作者: str,
    状态: str,
    字数: str,
    章节结果: list[dict[str, str]],
) -> tuple[str, bytes]:
    文件名 = f"[{状态}]书名：{清理文件名(书名)} 作者：{清理文件名(作者)}.txt"
    行 = [
        文件声明,
        "",
        f"名称：{书名}",
        f"作者：{作者}",
        f"状态：{状态}",
        f"字数：{字数}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(章节结果)}",
        "",
    ]
    for 章 in 章节结果:
        if not 章.get("content"):
            continue
        标题 = str(章.get("title") or "章节")
        正文 = 去除章节正文重复标题(标题, 章.get("content"))
        行.extend([标题, "", 正文, ""])
    return 文件名, "\n".join(行).encode("utf-8")


async def 准备发送文本文件(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    缓存路径 = await asyncio.to_thread(写入缓存, 文件名, 文件内容)
    if 小说网盘 is None:
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": "小说网盘模块未加载",
        }
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not 网盘结果.get("success"):
            删除缓存(缓存路径)
            return {
                "sent": False,
                "fallback_text": "",
                "source_cache_path": None,
                "error": str(网盘结果.get("error") or "小说网盘未启用"),
            }
        完成结果 = await 小说网盘.发送小说下载完成链接(
            event, 书名, 作者, str(网盘结果.get("share_url") or "")
        )
        if 完成结果.get("sent"):
            return {
                "sent": True,
                "fallback_text": "",
                "source_cache_path": 缓存路径,
                "error": "",
            }
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {
                "sent": False,
                "fallback_text": 降级文本,
                "source_cache_path": 缓存路径,
                "error": str(完成结果.get("error") or ""),
            }
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(完成结果.get("error") or "完成消息发送失败"),
        }
    except Exception as exc:
        删除缓存(缓存路径)
        return {
            "sent": False,
            "fallback_text": "",
            "source_cache_path": None,
            "error": str(exc),
        }


def 启动百度后台上传并清理(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    async def _任务() -> None:
        try:
            if 百度网盘 is not None and 源缓存路径:
                await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
        except Exception as exc:
            logger.warning(f"得间小说百度后台上传异常：文件={文件名}, 错误={exc}")
        finally:
            删除缓存(源缓存路径)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_任务())
    except Exception:
        删除缓存(源缓存路径)


def 写入缓存(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 下载缓存目录 / 文件名
    序号 = 1
    while 路径.exists():
        路径 = 下载缓存目录 / f"{Path(文件名).stem}_{序号}.txt"
        序号 += 1
    路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(路径)
    return 路径


def 删除缓存(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    小说缓存工具.删除下载缓存文件(缓存路径)


def 关闭得间资源() -> None:
    """释放专用解密进程，供插件停止和热重载使用。"""
    global 得间解密执行器, _得间解密信号量
    执行器 = 得间解密执行器
    得间解密执行器 = None
    _得间解密信号量 = None
    if 执行器 is not None:
        try:
            执行器.shutdown(wait=False, kill_workers=True)
        except Exception:
            pass


def 提取直接得间来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or "")
    for 匹配 in 链接正则.finditer(文本):
        地址 = 匹配.group(0)
        try:
            主机 = urllib.parse.urlsplit(地址).hostname or ""
        except ValueError:
            continue
        if 得间域名正则.search(主机):
            return 地址
    return None


def 提取事件得间来源(event: Any) -> str | None:
    for 字段 in ("message_str", "message", "raw_message"):
        值 = getattr(event, 字段, None)
        if 值 is None:
            continue
        来源 = 提取直接得间来源(str(值))
        if 来源:
            return 来源
    return None


def 提取书籍编号(来源: str) -> str:
    文本 = str(来源 or "").strip()
    if re.fullmatch(r"[0-9]{5,}", 文本):
        return 文本
    匹配 = 链接正则.search(文本)
    if not 匹配:
        return ""
    try:
        地址 = urllib.parse.urlsplit(匹配.group(0))
    except ValueError:
        return ""
    for 键, 值列表 in urllib.parse.parse_qs(地址.query).items():
        if 键.lower() not in {"bid", "bookid", "book_id", "book-id"}:
            continue
        for 值 in 值列表:
            if re.fullmatch(r"[0-9]{5,}", 值):
                return 值
    # 分享地址的书籍编号位于 /book/编号/1.html，uique 等参数不能作为编号。
    路径匹配 = 路径编号正则.search(地址.path)
    return 路径匹配.group(1) if 路径匹配 else ""


def 格式化字数(字数: Any) -> str:
    文本 = str(字数 or "").strip()
    if not 文本:
        return "未知"
    数字文本 = re.sub(r"[\s,，]", "", 文本)
    if 数字文本.endswith("字"):
        数字文本 = 数字文本[:-1]
    if 数字文本.isdigit():
        n = int(数字文本)
        return f"{round(n / 10000, 1)}万字" if n >= 10000 else f"{n}字"
    return 文本


def 清理文件名(文件名: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", str(文件名 or "")).strip() or "未知"


async def 搜索小说(关键词: str, *, 需要数量: int = 20) -> list[dict[str, Any]]:
    try:
        async with 创建得间HTTP会话(2) as HTTP会话:
            数据 = await 异步搜索得间书籍(HTTP会话, 关键词, 1, max(需要数量, 20))
    except Exception as exc:
        logger.warning(f"得间搜索失败：关键词={关键词}, 错误={exc}")
        return []
    结果 = []
    for item in 数据.get("results") or []:
        book_id = str(item.get("book_id") or "").strip()
        if not book_id:
            continue
        结果.append(
            {
                "title": item.get("title") or "未知",
                "author": item.get("author") or "未知",
                "book_id": book_id,
                "platform": "得间",
                "url": f"https://dj.palmestore.com/zybk/api/detail/index?bid={book_id}",
                "heat": 0,
                "score": 0,
            }
        )
        if len(结果) >= 需要数量:
            break
    return 结果
