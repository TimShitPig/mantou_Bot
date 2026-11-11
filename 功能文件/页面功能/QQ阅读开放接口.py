"""QQ 阅读第三方任务接口；与控制台登录、QQ 发送及网盘上传分离。"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aiohttp import web

from 功能文件.管理功能.基础功能 import 文件缓存
from 功能文件.管理功能.基础功能.机器人作用域 import (
    绑定机器人作用域, 获取机器人配置, 规范化机器人AppID,
)

logger = logging.getLogger(__name__)
接口前缀 = "/openapi/qq-reader/v1"
并发上限 = 2
结果保留秒数 = 3600
下载超时秒数 = 1800
文件大小上限 = 64 * 1024 * 1024
# 热重载保留纯内存任务和已完成文件；进程重启不恢复任务。
任务表: dict[str, dict[str, Any]] = globals().get("任务表", {})
当前服务 = globals().get("当前服务")


def _错误(status: int, code: str, message: str) -> web.Response:
    return web.json_response(
        {"ok": False, "error": {"code": code, "message": message}}, status=status,
    )


def _读取接口配置(配置: Any) -> dict[str, Any]:
    值 = 配置.get("qq_reader_api_settings", {}) if 配置 is not None else {}
    return 值 if isinstance(值, dict) else {}


def 规范接口密钥列表(值: Any) -> list[str]:
    """配置可使用字符串列表或每行一个 Key；空列表表示撤销全部。"""
    if isinstance(值, str):
        值 = 值.splitlines()
    if not isinstance(值, list):
        raise ValueError("API Key 列表格式无效")
    结果 = []
    for key in 值:
        if not isinstance(key, str):
            raise ValueError("API Key 格式无效")
        key = key.strip()
        if not key:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key):
            raise ValueError("API Key 应为 32 至 128 位字母、数字、下划线或短横线")
        if key not in 结果:
            结果.append(key)
    return 结果


def 读取接口密钥(配置: Any) -> list[str]:
    设置 = _读取接口配置(配置)
    try:
        结果 = 规范接口密钥列表(设置.get("qq_reader_api_keys", []))
    except ValueError:
        return []
    # 旧单 Key 继续有效；首次管理或替换列表时将它一并迁移并清空旧字段。
    旧值 = 设置.get("qq_reader_api_key")
    if isinstance(旧值, str) and re.fullmatch(r"[A-Za-z0-9_-]{32,128}", 旧值) and 旧值 not in 结果:
        结果.append(旧值)
    return 结果


def _所有者(key: str) -> str:
    return hashlib.sha256(("qq-reader-key-v2\x1f" + key).encode()).hexdigest()


def 读取接口密钥摘要(配置: Any) -> list[dict[str, str]]:
    return [{"id": _所有者(key)[:16]} for key in 读取接口密钥(配置)]


async def _下载账号快照(配置: Any) -> tuple[str, dict[str, Any] | None]:
    # 调用方仍只提供 Key；按实际已选账号判断，不能把多机器人等同于匿名。
    from 功能文件.管理功能.基础功能 import 消息记录
    from 功能文件.管理功能.小说功能.小说 import QQ阅读
    appids = sorted({规范化机器人AppID(x) for x in 消息记录.获取已配置机器人AppID列表()} - {""})
    快照 = [(appid, dict(获取机器人配置(配置, appid))) for appid in appids]

    def 读取() -> tuple[str, dict[str, Any] | None]:
        候选 = []
        for appid, 机器人配置 in 快照:
            账号 = QQ阅读._读取QQ阅读登录态(机器人配置)
            if 账号:
                候选.append((appid, dict(账号)))
                if len(候选) > 1:
                    return "", None
        if 候选:
            return 候选[0]
        return (appids[0], None) if len(appids) == 1 else ("", None)

    return await asyncio.to_thread(读取)


def _公开任务(任务: dict[str, Any]) -> dict[str, Any]:
    结果 = {键: 任务[键] for 键 in (
        "task_id", "book_id", "status", "stage", "created_at", "expires_at",
    )}
    for 键 in ("title", "author", "chapter_count", "size_bytes", "error"):
        if 键 in 任务:
            结果[键] = 任务[键]
    结果["chapter_range"] = 任务.get("chapter_range", "1-n")
    结果["result_format"] = 任务.get("result_format", "txt")
    结果["status_url"] = f"{接口前缀}/tasks/{任务['task_id']}"
    if 任务["status"] == "succeeded":
        结果["download_url"] = 结果["status_url"] + "/file"
        结果["filename"] = 任务["filename"]
    return 结果


def _删除文件(任务: dict[str, Any]) -> None:
    路径 = 任务.get("path")
    if 路径:
        if not 文件缓存.删除小说缓存文件(路径):
            raise OSError("cache_cleanup_failed")
        文件缓存.解除临时缓存占用(路径)
        任务.pop("path", None)


class QQ阅读接口服务:
    def __init__(self, 读取配置: Any):
        self.读取配置 = 读取配置
        self.任务: dict[str, asyncio.Task[Any]] = {}
        self.队列: asyncio.Queue[str] = asyncio.Queue()
        self.工作任务: list[asyncio.Task[Any]] = []
        self.清理任务: asyncio.Task[Any] | None = None
        self.已停止 = False

    def _已授权(self, 任务: dict[str, Any]) -> bool:
        配置 = self.读取配置()
        return _读取接口配置(配置).get("qq_reader_api_enabled") is True and any(
            hmac.compare_digest(任务["owner"], _所有者(key)) for key in 读取接口密钥(配置)
        )

    @web.middleware
    async def 中间件(self, request: web.Request, handler: Any) -> web.StreamResponse:
        if not request.path.startswith("/openapi/qq-reader/"):
            return await handler(request)
        try:
            配置 = self.读取配置()
            设置 = _读取接口配置(配置)
            keys = 读取接口密钥(配置)
            if 设置.get("qq_reader_api_enabled") is not True or self.已停止:
                响应 = _错误(503, "api_disabled", "接口未开启")
            elif not keys:
                响应 = _错误(503, "api_not_configured", "接口尚未配置完成")
            else:
                header = request.headers.get("Authorization", "")
                parts = header.split(" ", 1)
                候选 = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else ""
                # 仅这三个浏览器入口允许 URL Key；显式 Authorization 始终优先。
                if not header and request.method == "GET" and request.path in {f"{接口前缀}/{项}" for 项 in ("download", "chapter", "chapters")}:
                    参数密钥 = request.query.getall("key", [])
                    候选 = 参数密钥[0] if len(参数密钥) == 1 else ""
                key = ""
                if re.fullmatch(r"[A-Za-z0-9_-]{32,128}", 候选):
                    for 已配置 in keys:
                        if hmac.compare_digest(候选.encode(), 已配置.encode()):
                            key = 已配置
                if not key:
                    响应 = _错误(401, "unauthorized", "API Key 无效")
                    响应.headers["WWW-Authenticate"] = "Bearer"
                else:
                    request["qq_api_owner"] = _所有者(key)
                    # 外部 Key 是独立作用域，不继承控制台当前选中的机器人。
                    with 绑定机器人作用域(""):
                        响应 = await handler(request)
        except web.HTTPException as exc:
            响应 = _错误(exc.status, "invalid_request", "请求无效")
        except (ValueError, UnicodeDecodeError):
            响应 = _错误(400, "invalid_request", "请求参数无效")
        except Exception as exc:
            logger.warning("QQ阅读开放接口失败：error_type=%s", type(exc).__name__)
            响应 = _错误(500, "internal_error", "接口处理失败")
        if not 响应.prepared:
            响应.headers["Cache-Control"] = "private, no-store"
            响应.headers["X-Content-Type-Options"] = "nosniff"
            响应.headers["Referrer-Policy"] = "no-referrer"
        return 响应

    async def 启动(self, app: web.Application) -> None:
        # 兼容旧版同进程任务，保留已捕获的账号及原始执行作用域。
        for 任务 in 任务表.values():
            for key in 读取接口密钥(self.读取配置()):
                旧所有者 = hashlib.sha256((str(任务.get("appid") or "") + "\x1f" + key).encode()).hexdigest()
                if hmac.compare_digest(任务["owner"], 旧所有者):
                    任务["owner"] = _所有者(key)
                    break
        await self.清理()
        for 任务 in list(任务表.values()):
            if 任务["status"] == "queued":
                self._安排(任务)
        self.工作任务 = [asyncio.create_task(self._工作循环(), name="QQ阅读API下载") for _ in range(并发上限)]
        self.清理任务 = asyncio.create_task(self._定期清理(), name="QQ阅读API缓存清理")

    def _安排(self, 任务: dict[str, Any]) -> None:
        self.队列.put_nowait(任务["task_id"])

    async def _工作循环(self) -> None:
        while True:
            编号 = await self.队列.get()
            try:
                任务 = 任务表.get(编号)
                if 任务 is not None and 任务["status"] == "queued":
                    self.任务[编号] = asyncio.current_task()
                    await self._执行(任务)
            finally:
                self.任务.pop(编号, None)
                self.队列.task_done()

    async def 停止(self, *, 保留任务: bool = False) -> None:
        if self.已停止:
            return
        self.已停止 = True
        活动 = list(self.工作任务)
        if self.清理任务 is not None:
            活动.append(self.清理任务)
        for task in 活动:
            task.cancel()
        if 活动:
            await asyncio.gather(*活动, return_exceptions=True)
        if not 保留任务:
            for 编号, 任务 in list(任务表.items()):
                try:
                    _删除文件(任务)
                    任务表.pop(编号, None)
                except OSError as exc:
                    logger.warning("QQ阅读API缓存清理失败：error_type=%s", type(exc).__name__)

    async def 清理(self) -> None:
        for 编号, 任务 in list(任务表.items()):
            if 任务.get("readers", 0) or 任务.get("initializing") or 编号 in self.任务:
                continue
            文件丢失 = 任务["status"] == "succeeded" and not Path(任务["path"]).is_file()
            if 文件丢失 or not self._已授权(任务) or (任务["expires_at"] and 任务["expires_at"] <= time.time()):
                try:
                    _删除文件(任务)
                    任务表.pop(编号, None)
                except OSError as exc:
                    logger.warning("QQ阅读API缓存清理失败：error_type=%s", type(exc).__name__)

    async def _定期清理(self) -> None:
        while True:
            await asyncio.sleep(60)
            await self.清理()

    async def _读取提交(self, request: web.Request, *, 批量: bool = False) -> Any:
        if request.content_type != "application/json":
            return _错误(415, "json_required", "请提交 JSON 请求")
        if not 批量 and request.content_length is not None and request.content_length > 8192:
            return _错误(413, "request_too_large", "请求过大")
        try:
            async with asyncio.timeout(10):
                # 批量不设书籍数量及请求体字节上限；只在鉴权后读取。
                return await request.clone(client_max_size=0 if 批量 else 8192).json()
        except asyncio.TimeoutError:
            return _错误(408, "request_timeout", "请求读取超时")

    @staticmethod
    def _书籍编号(原值: Any) -> str:
        book_id = str(原值) if type(原值) in (str, int) else ""
        return book_id if re.fullmatch(r"[1-9][0-9]{0,19}", book_id) else ""

    @staticmethod
    def _章节范围(数据: dict[str, Any]) -> str:
        from 功能文件.管理功能.小说功能.小说 import QQ阅读
        return QQ阅读.规范QQ阅读章节范围(数据.get("chapter_range", "1-n"))

    async def 创建任务(self, request: web.Request) -> web.Response:
        数据 = await self._读取提交(request)
        if isinstance(数据, web.Response):
            return 数据
        if not isinstance(数据, dict) or "book_id" not in 数据 or set(数据) - {"book_id", "chapter_range"}:
            return _错误(400, "invalid_book_id", "请提交 book_id，可选 chapter_range")
        book_id = self._书籍编号(数据["book_id"])
        if not book_id:
            return _错误(400, "invalid_book_id", "书籍 ID 无效")
        try:
            范围 = self._章节范围(数据)
        except ValueError:
            return _错误(400, "invalid_chapter_range", "章节范围须为 1-100 或 1-n 等正序范围")
        return await self._提交任务(request, [book_id], 章节范围=范围)

    async def 直达下载(self, request: web.Request) -> web.StreamResponse:
        return await self._直达结果(request)

    async def 单章正文(self, request: web.Request) -> web.StreamResponse:
        return await self._直达结果(request, 单章=True, 结果格式="json")

    async def 多章正文(self, request: web.Request) -> web.StreamResponse:
        return await self._直达结果(request, 结果格式="json")

    async def _直达结果(self, request: web.Request, *, 单章: bool = False, 结果格式: str = "txt") -> web.StreamResponse:
        参数 = request.query
        允许参数 = {"key", "book_id", "chapter" if 单章 else "chapter_range"}
        if set(参数) - 允许参数 or any(len(参数.getall(键)) != 1 for 键 in 参数):
            return _错误(400, "invalid_request", "请求参数无效")
        book_id = self._书籍编号(参数.get("book_id"))
        if not book_id:
            return _错误(400, "invalid_book_id", "书籍 ID 无效")
        数据 = dict(参数)
        if 单章:
            章节 = 参数.get("chapter", "")
            if not re.fullmatch(r"[1-9][0-9]{0,19}", 章节):
                return _错误(400, "invalid_chapter", "章节序号须为正整数")
            数据["chapter_range"] = f"{章节}-{章节}"
        try:
            范围 = self._章节范围(数据)
        except ValueError:
            return _错误(400, "invalid_chapter_range", "章节范围须为 1-100 或 1-n 等正序范围")
        响应 = await self._提交任务(request, [book_id], 章节范围=范围, 结果格式=结果格式)
        if 响应.status not in {200, 202}:
            return 响应
        编号 = json.loads(响应.body)["task"]["task_id"]
        # 等待的是共享队列任务；浏览器断开不取消正文，重新打开同链接可复用。
        while True:
            if self.已停止:
                return _错误(503, "api_disabled", "接口暂不可用")
            任务 = 任务表.get(编号)
            if 任务 is None or (任务["expires_at"] and 任务["expires_at"] <= time.time()):
                return _错误(404, "task_not_found", "任务不存在或已过期")
            if not self._已授权(任务):
                return _错误(401, "unauthorized", "API Key 无效")
            if 任务["status"] == "succeeded":
                return await self._发送文件(request, 任务)
            if 任务["status"] == "failed":
                return _错误(502, "download_failed", "下载失败，请稍后重试")
            if request.transport is None or request.transport.is_closing():
                raise asyncio.CancelledError
            await asyncio.sleep(0.5)

    async def 批量创建任务(self, request: web.Request) -> web.Response:
        数据 = await self._读取提交(request, 批量=True)
        if isinstance(数据, web.Response):
            return 数据
        if not isinstance(数据, dict) or set(数据) - {"book_id", "book_ids", "chapter_range"} or ("book_id" in 数据) == ("book_ids" in 数据):
            return _错误(400, "invalid_book_ids", "请提交 book_id 或非空 book_ids 数组，可选 chapter_range")
        原编号 = [数据["book_id"]] if "book_id" in 数据 else 数据["book_ids"]
        if not isinstance(原编号, list) or not 原编号:
            return _错误(400, "invalid_book_ids", "请提交非空 book_ids 数组")
        编号列表 = [self._书籍编号(值) for 值 in 原编号]
        if not all(编号列表):
            return _错误(400, "invalid_book_ids", "书籍 ID 无效，整批未提交")
        try:
            范围 = self._章节范围(数据)
        except ValueError:
            return _错误(400, "invalid_chapter_range", "章节范围须为 1-100 或 1-n 等正序范围")
        return await self._提交任务(request, list(dict.fromkeys(编号列表)), 批量=True, 章节范围=范围)

    async def _提交任务(self, request: web.Request, 编号列表: list[str], *, 批量: bool = False, 章节范围: str = "1-n", 结果格式: str = "txt") -> web.Response:
        appid, 账号 = await _下载账号快照(self.读取配置())
        账号指纹 = hashlib.sha256(json.dumps(账号, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if 账号 else ""
        if self.已停止:
            return _错误(503, "api_disabled", "接口暂不可用")
        await self.清理()
        已有 = {(任务["book_id"], 任务.get("chapter_range", "1-n"), 任务.get("result_format", "txt")): 任务 for 任务 in 任务表.values()
                if 任务["owner"] == request["qq_api_owner"] and 任务["status"] != "failed"
                and 任务.get("account_fingerprint", "") == 账号指纹}
        提交结果, 新任务 = [], []
        for book_id in 编号列表:
            任务 = 已有.get((book_id, 章节范围, 结果格式))
            if 任务 is None:
                任务 = {
                    "task_id": secrets.token_hex(16), "book_id": book_id, "chapter_range": 章节范围,
                    "result_format": 结果格式, "account_fingerprint": 账号指纹,
                    "appid": "", "owner": request["qq_api_owner"],
                    "status": "queued", "stage": "queued", "created_at": int(time.time()),
                    "expires_at": None, "initializing": True,
                }
                任务表[任务["task_id"]] = 任务
                新任务.append(任务)
            提交结果.append(任务)
        try:
            if 新任务:
                # 一批任务固定提交时的账号；已有任务继续保留原快照。
                if self.已停止:
                    for 任务 in 新任务:
                        任务表.pop(任务["task_id"], None)
                    return _错误(503, "api_disabled", "接口暂不可用")
                for 任务 in 新任务:
                    任务["appid"] = appid
                    任务["account"] = 账号
                    任务.pop("initializing", None)
                    self._安排(任务)
        except BaseException:
            for 任务 in 新任务:
                任务表.pop(任务["task_id"], None)
            raise
        状态码 = 200 if all(任务["status"] == "succeeded" for 任务 in 提交结果) else 202
        if 批量:
            return web.json_response({"ok": True, "count": len(提交结果), "tasks": [_公开任务(任务) for 任务 in 提交结果]}, status=状态码)
        响应 = web.json_response({"ok": True, "task": _公开任务(提交结果[0])}, status=状态码)
        响应.headers["Location"] = f"{接口前缀}/tasks/{提交结果[0]['task_id']}"
        return 响应

    def _查任务(self, request: web.Request) -> dict[str, Any] | None:
        任务 = 任务表.get(request.match_info.get("task_id", ""))
        if 任务 is None or not hmac.compare_digest(任务["owner"], request["qq_api_owner"]):
            return None
        return None if 任务["expires_at"] and 任务["expires_at"] <= time.time() else 任务

    async def 查询任务(self, request: web.Request) -> web.Response:
        任务 = self._查任务(request)
        if 任务 is None:
            return _错误(404, "task_not_found", "任务不存在或已过期")
        return web.json_response({"ok": True, "task": _公开任务(任务)})

    async def 获取文件(self, request: web.Request) -> web.StreamResponse:
        任务 = self._查任务(request)
        if 任务 is None:
            return _错误(404, "task_not_found", "任务不存在或已过期")
        return await self._发送文件(request, 任务)

    async def _发送文件(self, request: web.Request, 任务: dict[str, Any]) -> web.StreamResponse:
        if 任务["status"] != "succeeded":
            return _错误(409, "file_not_ready", "任务尚未完成或已失败")
        任务["readers"] = 任务.get("readers", 0) + 1
        try:
            try:
                文件 = Path(任务["path"]).open("rb")
            except OSError:
                return _错误(410, "file_expired", "文件已失效，请重新提交任务")
            with 文件:
                响应 = web.StreamResponse(headers={
                    "Content-Type": "application/json; charset=utf-8" if 任务.get("result_format") == "json" else "text/plain; charset=utf-8",
                    "Content-Length": str(任务["size_bytes"]),
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer",
                })
                if 任务.get("result_format", "txt") == "txt":
                    响应.headers["Content-Disposition"] = f"attachment; filename=qq-reader-{任务['book_id']}.txt; filename*=UTF-8''{quote(任务['filename'], safe='')}"
                try:
                    await 响应.prepare(request)
                    if request.method != "HEAD":
                        while 数据 := await asyncio.to_thread(文件.read, 256 * 1024):
                            await 响应.write(数据)
                    await 响应.write_eof()
                except (ConnectionResetError, BrokenPipeError):
                    logger.debug("QQ阅读API文件传输结束：reason=client_disconnected")
                except OSError as exc:
                    logger.warning("QQ阅读API文件读取失败：error_type=%s", type(exc).__name__)
                    if request.transport is not None:
                        request.transport.close()
                return 响应
        finally:
            任务["readers"] -= 1

    async def _执行(self, 任务: dict[str, Any]) -> None:
        try:
            if not self._已授权(任务):
                raise ValueError("api_configuration_changed")
            from 功能文件.管理功能.小说功能.小说 import QQ阅读
            任务.update(status="running", stage="details")
            _删除文件(任务)
            async with asyncio.timeout(下载超时秒数):
                with 绑定机器人作用域(任务["appid"]), QQ阅读.QQ阅读账号上下文(任务["account"]):
                    参数 = {"章节范围": 任务.get("chapter_range", "1-n"), "状态配置": dict(获取机器人配置(self.读取配置(), 任务["appid"]))}
                    if 任务.get("result_format") == "json":
                        参数["返回章节"] = True
                    async for 结果 in QQ阅读.生成QQ阅读下载文件流(任务["book_id"], **参数):
                        if not self._已授权(任务):
                            raise ValueError("api_key_revoked")
                        任务["stage"] = 结果["stage"]
                        if 结果["kind"] == "error":
                            任务["error"] = {"code": 结果["code"], "message": 结果["message"]}
                            任务["status"] = "failed"
                        elif 结果["kind"] == "file":
                            content = 结果["content"]
                            if len(content) > 文件大小上限:
                                raise ValueError("result_too_large")
                            路径 = 文件缓存.创建临时缓存文件("qq-reader-api-", ".json" if 任务.get("result_format") == "json" else ".txt")
                            任务["path"] = str(路径)
                            文件缓存.标记临时缓存正在使用(路径)
                            文件缓存.标记小说缓存正在使用(路径)
                            写入 = asyncio.create_task(asyncio.to_thread(路径.write_bytes, content))
                            try:
                                await asyncio.shield(写入)
                            except asyncio.CancelledError:
                                await 写入
                                raise
                            任务.update(status="succeeded", stage="completed", filename=结果["filename"],
                                        size_bytes=len(content), chapter_count=结果["chapter_count"],
                                        title=结果["title"], author=结果["author"])
            if 任务["status"] == "running":
                raise RuntimeError("missing_result")
        except asyncio.CancelledError:
            任务.update(status="queued", stage="queued")
            raise
        except Exception as exc:
            code = "download_timeout" if isinstance(exc, asyncio.TimeoutError) else "download_failed"
            任务.update(status="failed", error={"code": code, "message": "下载失败，请稍后重试"})
            logger.warning("QQ阅读API任务失败：stage=%s, error_type=%s", 任务["stage"], type(exc).__name__)
        finally:
            if 任务["status"] != "succeeded":
                try:
                    _删除文件(任务)
                except OSError as exc:
                    logger.warning("QQ阅读API缓存清理失败：error_type=%s", type(exc).__name__)
            if 任务["status"] in {"succeeded", "failed"}:
                任务["expires_at"] = int(time.time()) + 结果保留秒数
                任务.pop("account", None)


async def _未知路由(request: web.Request) -> web.Response:
    return _错误(404, "route_not_found", "接口不存在或方法不支持")


def 注册路由(app: web.Application, 读取配置: Any) -> None:
    global 当前服务
    服务 = 当前服务 = QQ阅读接口服务(读取配置)
    # 外部路由使用独立 Key；浏览器三个入口支持 URL Key，不依赖控制台会话或调用方 AppID。
    app.middlewares.append(服务.中间件)
    app.router.add_get(f"{接口前缀}/download", 服务.直达下载, allow_head=False)
    app.router.add_get(f"{接口前缀}/chapter", 服务.单章正文, allow_head=False)
    app.router.add_get(f"{接口前缀}/chapters", 服务.多章正文, allow_head=False)
    app.router.add_post(f"{接口前缀}/tasks", 服务.创建任务)
    app.router.add_post(f"{接口前缀}/tasks/batch", 服务.批量创建任务)
    app.router.add_get(f"{接口前缀}/tasks/{{task_id}}", 服务.查询任务)
    app.router.add_get(f"{接口前缀}/tasks/{{task_id}}/file", 服务.获取文件)
    app.router.add_route("*", "/openapi/qq-reader/{tail:.*}", _未知路由)
    app.on_startup.append(服务.启动)

    async def 清理(app: web.Application) -> None:
        await 服务.停止()

    app.on_cleanup.append(清理)


async def 停止接口服务(*, 保留任务: bool = False) -> None:
    if 当前服务 is not None:
        await 当前服务.停止(保留任务=保留任务)
