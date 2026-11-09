"""QQ 阅读第三方任务接口；与控制台登录、QQ 发送及网盘上传分离。"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
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


def _所有者(appid: str, key: str) -> str:
    return hashlib.sha256((appid + "\x1f" + key).encode()).hexdigest()


def _公开任务(任务: dict[str, Any]) -> dict[str, Any]:
    结果 = {键: 任务[键] for 键 in (
        "task_id", "book_id", "status", "stage", "created_at", "expires_at",
    )}
    for 键 in ("title", "author", "chapter_count", "size_bytes", "error"):
        if 键 in 任务:
            结果[键] = 任务[键]
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
        配置 = _读取接口配置(self.读取配置())
        return 配置.get("qq_reader_api_enabled") is True and hmac.compare_digest(
            任务["owner"], _所有者(
                规范化机器人AppID(配置.get("qq_reader_api_appid")),
                str(配置.get("qq_reader_api_key") or ""),
            ),
        )

    @web.middleware
    async def 中间件(self, request: web.Request, handler: Any) -> web.StreamResponse:
        if not request.path.startswith("/openapi/qq-reader/"):
            return await handler(request)
        try:
            配置 = _读取接口配置(self.读取配置())
            key = str(配置.get("qq_reader_api_key") or "")
            if 配置.get("qq_reader_api_enabled") is not True or self.已停止:
                响应 = _错误(503, "api_disabled", "接口未开启")
            elif not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key):
                响应 = _错误(503, "api_not_configured", "接口尚未配置完成")
            else:
                header = request.headers.get("Authorization", "")
                parts = header.split(" ", 1)
                if len(parts) != 2 or parts[0].lower() != "bearer" or not hmac.compare_digest(parts[1].encode(), key.encode()):
                    响应 = _错误(401, "unauthorized", "API Key 无效")
                    响应.headers["WWW-Authenticate"] = "Bearer"
                else:
                    appid = 规范化机器人AppID(配置.get("qq_reader_api_appid"))
                    from 功能文件.管理功能.基础功能 import 消息记录
                    if not appid or appid not in 消息记录.获取已配置机器人AppID列表():
                        响应 = _错误(503, "bot_unavailable", "绑定机器人不可用")
                    else:
                        request["qq_api_owner"] = _所有者(appid, key)
                        request["qq_api_appid"] = appid
                        with 绑定机器人作用域(appid):
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
        return 响应

    async def 启动(self, app: web.Application) -> None:
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

    async def 创建任务(self, request: web.Request) -> web.Response:
        数据 = await self._读取提交(request)
        if isinstance(数据, web.Response):
            return 数据
        if not isinstance(数据, dict) or set(数据) != {"book_id"}:
            return _错误(400, "invalid_book_id", "仅允许提交 book_id")
        book_id = self._书籍编号(数据["book_id"])
        if not book_id:
            return _错误(400, "invalid_book_id", "书籍 ID 无效")
        return await self._提交任务(request, [book_id])

    async def 批量创建任务(self, request: web.Request) -> web.Response:
        数据 = await self._读取提交(request, 批量=True)
        if isinstance(数据, web.Response):
            return 数据
        if not isinstance(数据, dict) or set(数据) != {"book_ids"} or not isinstance(数据["book_ids"], list) or not 数据["book_ids"]:
            return _错误(400, "invalid_book_ids", "请提交非空 book_ids 数组")
        编号列表 = [self._书籍编号(值) for 值 in 数据["book_ids"]]
        if not all(编号列表):
            return _错误(400, "invalid_book_ids", "书籍 ID 无效，整批未提交")
        return await self._提交任务(request, list(dict.fromkeys(编号列表)), 批量=True)

    async def _提交任务(self, request: web.Request, 编号列表: list[str], *, 批量: bool = False) -> web.Response:
        await self.清理()
        已有 = {任务["book_id"]: 任务 for 任务 in 任务表.values()
                if 任务["owner"] == request["qq_api_owner"] and 任务["status"] != "failed"}
        提交结果, 新任务 = [], []
        for book_id in 编号列表:
            任务 = 已有.get(book_id)
            if 任务 is None:
                任务 = {
                    "task_id": secrets.token_hex(16), "book_id": book_id,
                    "appid": request["qq_api_appid"], "owner": request["qq_api_owner"],
                    "status": "queued", "stage": "queued", "created_at": int(time.time()),
                    "expires_at": None, "initializing": True,
                }
                任务表[任务["task_id"]] = 任务
                新任务.append(任务)
            提交结果.append(任务)
        try:
            if 新任务:
                from 功能文件.管理功能.小说功能.小说 import QQ阅读
                配置 = 获取机器人配置(self.读取配置(), request["qq_api_appid"])
                # 一批任务共用提交时捕获的同一账号快照。
                账号 = await asyncio.to_thread(QQ阅读._读取QQ阅读登录态, 配置)
                if self.已停止:
                    for 任务 in 新任务:
                        任务表.pop(任务["task_id"], None)
                    return _错误(503, "api_disabled", "接口暂不可用")
                for 任务 in 新任务:
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
                    "Content-Type": "text/plain; charset=utf-8",
                    "Content-Length": str(任务["size_bytes"]),
                    "Content-Disposition": f"attachment; filename=qq-reader-{任务['book_id']}.txt; filename*=UTF-8''{quote(任务['filename'], safe='')}",
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                })
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
                    async for 结果 in QQ阅读.生成QQ阅读下载文件流(任务["book_id"]):
                        任务["stage"] = 结果["stage"]
                        if 结果["kind"] == "error":
                            任务["error"] = {"code": 结果["code"], "message": 结果["message"]}
                            任务["status"] = "failed"
                        elif 结果["kind"] == "file":
                            content = 结果["content"]
                            if len(content) > 文件大小上限:
                                raise ValueError("result_too_large")
                            路径 = 文件缓存.创建临时缓存文件("qq-reader-api-", ".txt")
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
    # 在控制台中间件清空公开路由作用域后，再绑定 API 的明确 AppID。
    app.middlewares.append(服务.中间件)
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
