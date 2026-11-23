"""平台独立的同步执行器与原脚本子进程，不在事件循环执行阻塞 I/O。"""

from __future__ import annotations

import asyncio
from concurrent.futures import Future, InvalidStateError, ThreadPoolExecutor
import contextvars
import functools
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
from typing import Any, Callable


class 平台执行错误(RuntimeError):
    def __init__(self, category: str, error_type: str = ""):
        self.category = category
        self.error_type = error_type if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,63}", error_type) else ""
        self.type = self.error_type
        super().__init__(category + (":" + self.error_type if self.error_type else ""))


# reload 复用存活执行器、进程及其 I/O 线程；关闭完成后再由生命周期显式启动。
if "_资源锁" not in globals():
    _资源锁 = threading.RLock()
if "_资源条件" not in globals():
    _资源条件 = threading.Condition(_资源锁)
if "_平台状态" not in globals():
    _平台状态: dict[str, dict[str, Any]] = {}
if "_接受调用" not in globals():
    _接受调用 = True
if "_全部关闭任务" not in globals():
    _全部关闭任务: Future[Any] | None = None


_子进程引导 = r'''
import concurrent.futures, json, sys, threading
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
write_lock = threading.Lock()
local = threading.local()
sessions = {}
sessions_lock = threading.Lock()
def emit(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    with write_lock:
        sys.stdout.write(raw)
        sys.stdout.flush()
def error_kind(exc):
    name = type(exc).__name__
    return name if name.isascii() and name.isidentifier() and len(name) <= 64 else "Exception"
def silent_print(*args, **kwargs):
    pass
try:
    init = json.loads(sys.stdin.readline())
    code = compile(init["source"], "<platform-original>", "exec")
    workers = init["max_workers"]
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="original")
except BaseException as exc:
    emit({"kind":"startup_error", "error_type":error_kind(exc)})
    raise SystemExit(1)
def invoke(name, args):
    namespace = getattr(local, "namespace", None)
    if namespace is None:
        namespace = {"__name__":"_mantou_platform_original", "print":silent_print}
        exec(code, namespace)
        local.namespace = namespace
        session = namespace.get("SESSION")
        if session is not None:
            with sessions_lock:
                sessions[id(session)] = session
    return namespace[name](*args)
def completed(request_id, future):
    try:
        result = future.result()
        # 检查可序列化性，异常只传固定分类和异常类型，不能传原文或参数。
        json.dumps(result, ensure_ascii=False, allow_nan=False)
    except BaseException as exc:
        emit({"kind":"result", "id":request_id, "ok":False, "error_type":error_kind(exc)})
    else:
        emit({"kind":"result", "id":request_id, "ok":True, "result":result})
emit({"kind":"ready"})
try:
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("kind") == "close":
            break
        request_id = message["id"]
        future = pool.submit(invoke, message["name"], message["args"])
        future.add_done_callback(lambda done, request_id=request_id: completed(request_id, done))
finally:
    pool.shutdown(wait=True)
    with sessions_lock:
        to_close = list(sessions.values())
        sessions.clear()
    for session in to_close:
        close = getattr(session, "close", None)
        if callable(close):
            try:
                close()
            except BaseException:
                pass
    emit({"kind":"closed", "sessions":len(to_close)})
'''


def _完成(future: Future[Any], *, value: Any = None, error: BaseException | None = None) -> None:
    try:
        if error is not None:
            future.set_exception(error)
        else:
            future.set_result(value)
    except InvalidStateError:
        pass


class _原脚本进程:
    def __init__(self, source: str, workers: int):
        self.fingerprint = hashlib.sha256(source.encode("utf-8")).digest()
        self.workers = workers
        self.lock = threading.RLock()
        self.pending: dict[int, Future[Any]] = {}
        self.sequence = 0
        self.failure: 平台执行错误 | None = None
        self.accepting = True
        self.ready = False
        self.ready_event = threading.Event()
        self.closed_sessions = 0
        self.outgoing: queue.Queue[bytes | None] = queue.Queue()
        self.process = subprocess.Popen(
            [sys.executable, "-B", "-u", "-c", _子进程引导],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.reader = threading.Thread(target=self._读取, name="platform-reader", daemon=True)
        self.writer = threading.Thread(target=self._写入, name="platform-writer", daemon=True)
        self.reader.start()
        self.writer.start()
        # 源码只经过本地 stdin，不进入进程参数、日志或异常文本。
        self.outgoing.put(self._编码({"source": source, "max_workers": workers}))
        if not self.ready_event.wait(20) or not self.ready:
            self._故障("startup_failed", "ProcessStart")
            self.关闭()
            raise self.failure or 平台执行错误("startup_failed")

    @staticmethod
    def _编码(message: dict[str, Any]) -> bytes:
        return (json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")

    def _故障(self, category: str = "worker_crashed", error_type: str = "ProcessExit") -> None:
        with self.lock:
            if self.failure is None:
                self.failure = 平台执行错误(category, error_type)
            self.accepting = False
            pending, self.pending = self.pending, {}
            error = self.failure
        self.ready_event.set()
        for future in pending.values():
            _完成(future, error=error)
        # 协议出错的子进程也要结束；这里仅在进程 I/O/控制线程内调用。
        if self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass

    def _写入(self) -> None:
        try:
            while True:
                message = self.outgoing.get()
                if message is None:
                    return
                self.process.stdin.write(message)
                self.process.stdin.flush()
        except (OSError, ValueError):
            self._故障()

    def _读取(self) -> None:
        graceful = False
        try:
            for raw in self.process.stdout:
                message = json.loads(raw)
                kind = message.get("kind")
                if kind == "ready":
                    self.ready = True
                    self.ready_event.set()
                elif kind == "startup_error":
                    self._故障("startup_failed", str(message.get("error_type") or "Exception"))
                    return
                elif kind == "closed":
                    graceful = True
                    self.closed_sessions = int(message.get("sessions") or 0)
                elif kind == "result":
                    with self.lock:
                        future = self.pending.pop(message["id"], None)
                    if future is not None:
                        if message.get("ok") is True:
                            _完成(future, value=message.get("result"))
                        else:
                            _完成(future, error=平台执行错误("call_failed", str(message.get("error_type") or "Exception")))
                else:
                    raise ValueError("invalid worker message")
        except (OSError, ValueError, KeyError, TypeError):
            self._故障("worker_protocol_failed", "WorkerProtocol")
        finally:
            if not graceful:
                self._故障()

    def 可用(self) -> bool:
        with self.lock:
            return self.accepting and self.failure is None and self.process.poll() is None

    def 提交(self, name: str, args: tuple[Any, ...]) -> Future[Any]:
        future: Future[Any] = Future()
        with self.lock:
            if not self.accepting or self.failure is not None:
                raise self.failure or 平台执行错误("service_stopped")
            self.sequence += 1
            request_id = self.sequence
            try:
                encoded = self._编码({"kind": "call", "id": request_id, "name": name, "args": args})
            except (TypeError, ValueError):
                raise 平台执行错误("invalid_input", "SerializationError") from None
            self.pending[request_id] = future
            self.outgoing.put(encoded)
        return future

    def 关闭(self) -> None:
        with self.lock:
            if self.accepting:
                self.accepting = False
                self.outgoing.put(self._编码({"kind": "close"}))
        self.process.wait()
        self.outgoing.put(None)
        self.writer.join(timeout=2)
        self.reader.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()
        with self.lock:
            pending, self.pending = self.pending, {}
        for future in pending.values():
            _完成(future, error=self.failure or 平台执行错误("worker_crashed", "ProcessExit"))


def _平台名称(platform: str) -> str:
    if not isinstance(platform, str) or not platform.strip():
        raise 平台执行错误("invalid_input", "PlatformName")
    return platform.strip()


def _工作数(workers: int) -> int:
    if type(workers) is not int or workers < 1:
        raise 平台执行错误("invalid_input", "WorkerCount")
    return workers


def _状态(platform: str) -> dict[str, Any]:
    with _资源锁:
        if not _接受调用:
            raise 平台执行错误("service_stopped")
        return _平台状态.setdefault(platform, {"sync": None, "control": None, "process": None, "raw_closed": False, "cache_calls": 0})


def _控制执行器(state: dict[str, Any]) -> ThreadPoolExecutor:
    with _资源锁:
        executor = state["control"]
        if executor is None:
            executor = state["control"] = ThreadPoolExecutor(max_workers=1, thread_name_prefix="platform-control")
        return executor


def 创建平台同步调用(platform: str, max_workers: int = 32) -> Callable[..., Any]:
    """返回与 to_thread 相同调用形式的协程函数，保留上下文和关键字参数。"""
    platform, workers = _平台名称(platform), _工作数(max_workers)

    async def 调用(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        state = _状态(platform)
        context = contextvars.copy_context()
        work = functools.partial(context.run, functools.partial(function, *args, **kwargs))
        with _资源锁:
            if not _接受调用:
                raise 平台执行错误("service_stopped")
            executor = state["sync"]
            if executor is None:
                executor = state["sync"] = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="platform-sync")
            future = executor.submit(work)
        return await asyncio.wrap_future(future)

    return 调用


async def _排空结果(future: Future[Any]) -> tuple[Any, asyncio.CancelledError | None]:
    """保留调用者取消，取回已经准入的同步工作结果供资源清理使用。"""
    wrapped = asyncio.wrap_future(future)
    cancelled = None
    while not wrapped.done():
        try:
            await asyncio.shield(wrapped)
        except asyncio.CancelledError as exc:
            cancelled = exc
        except Exception:
            break
    try:
        result = wrapped.result()
    except BaseException:
        if cancelled is not None:
            raise cancelled from None
        raise
    return result, cancelled


def 创建平台缓存调用(platform: str, cleanup_callable: Callable[[Any], Any]) -> Callable[..., Any]:
    """缓存写入被取消时，等写入完成并在同池删除结果，避免遗留 TXT 占用。"""
    platform = _平台名称(platform)
    if not callable(cleanup_callable):
        raise 平台执行错误("invalid_input", "CleanupCallable")

    async def 调用(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        state = _状态(platform)
        context, cleanup_context = contextvars.copy_context(), contextvars.copy_context()
        work = functools.partial(context.run, functools.partial(function, *args, **kwargs))
        with _资源条件:
            if not _接受调用:
                raise 平台执行错误("service_stopped")
            executor = state["sync"]
            if executor is None:
                executor = state["sync"] = ThreadPoolExecutor(max_workers=32, thread_name_prefix="platform-sync")
            state["cache_calls"] = state.get("cache_calls", 0) + 1
            try:
                future = executor.submit(work)
            except Exception:
                state["cache_calls"] -= 1
                _资源条件.notify_all()
                raise
        try:
            result, cancelled = await _排空结果(future)
            if cancelled is None:
                return result
            # 全局关闭等待本调用占用释放，因此已准入清理仍可提交到原池。
            cleanup = executor.submit(cleanup_context.run, cleanup_callable, result)
            try:
                await _排空结果(cleanup)
            except Exception as exc:
                add_note = getattr(cancelled, "add_note", None)
                if callable(add_note):
                    add_note("cache_cleanup_failed:" + type(exc).__name__)
            raise cancelled
        finally:
            with _资源条件:
                state["cache_calls"] -= 1
                _资源条件.notify_all()

    return 调用


def _取得原脚本进程(platform: str, state: dict[str, Any], source: str, workers: int) -> _原脚本进程:
    with _资源锁:
        if not _接受调用 or state["raw_closed"] or _平台状态.get(platform) is not state:
            raise 平台执行错误("service_stopped")
        process = state["process"]
    fingerprint = hashlib.sha256(source.encode("utf-8")).digest()
    if process is not None and process.fingerprint == fingerprint and getattr(process, "workers", workers) == workers and process.可用():
        return process
    if process is not None:
        process.关闭()
    try:
        process = _原脚本进程(source, workers)
    except 平台执行错误:
        raise
    except Exception as exc:
        raise 平台执行错误("startup_failed", type(exc).__name__) from None
    with _资源锁:
        accepted = _接受调用 and not state["raw_closed"] and _平台状态.get(platform) is state
        if accepted:
            state["process"] = process
    if not accepted:
        process.关闭()
        raise 平台执行错误("service_stopped")
    return process


async def _等待原调用(future: Future[Any]) -> Any:
    wrapped = asyncio.wrap_future(future)
    try:
        return await asyncio.shield(wrapped)
    except asyncio.CancelledError:
        while not wrapped.done():
            try:
                await asyncio.shield(wrapped)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not wrapped.cancelled():
            wrapped.exception()
        raise


async def 运行原脚本(platform: str, source: str, name: str, args: tuple[Any, ...], max_workers: int = 200) -> Any:
    platform, workers = _平台名称(platform), _工作数(max_workers)
    if not isinstance(source, str) or not isinstance(name, str) or not name.isidentifier() or not isinstance(args, (tuple, list)):
        raise 平台执行错误("invalid_input", "ScriptCall")
    state = _状态(platform)
    with _资源锁:
        if state["raw_closed"]:
            raise 平台执行错误("service_stopped")
        control = _控制执行器(state)
        start = control.submit(_取得原脚本进程, platform, state, source, workers)
    process = await _等待原调用(start)
    return await _等待原调用(process.提交(name, tuple(args)))


def _关闭状态原脚本(state: dict[str, Any]) -> None:
    with _资源锁:
        process, state["process"] = state["process"], None
    if process is not None:
        process.关闭()


async def 关闭平台原脚本(platform: str) -> None:
    platform = _平台名称(platform)
    with _资源锁:
        state = _平台状态.setdefault(platform, {"sync": None, "control": None, "process": None, "raw_closed": False, "cache_calls": 0})
        state["raw_closed"] = True
        if state["control"] is None and state["process"] is None:
            return
        work = _控制执行器(state).submit(_关闭状态原脚本, state)
    await _等待原调用(work)


def _关闭状态(state: dict[str, Any]) -> None:
    try:
        _关闭状态原脚本(state)
    finally:
        with _资源条件:
            while state.get("cache_calls", 0):
                _资源条件.wait()
            executor, state["sync"] = state["sync"], None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)


def _关闭协调(states: list[dict[str, Any]], completion: Future[Any]) -> None:
    futures = [(_控制执行器(state), state) for state in states]
    failed = False
    submitted = [executor.submit(_关闭状态, state) for executor, state in futures]
    for future in submitted:
        try:
            future.result()
        except Exception:
            failed = True
    for executor, _ in futures:
        try:
            executor.shutdown(wait=True, cancel_futures=True)
        except Exception:
            failed = True
    with _资源锁:
        _平台状态.clear()
    if failed:
        _完成(completion, error=平台执行错误("shutdown_failed", "ExecutorShutdown"))
    else:
        _完成(completion)


async def 关闭全部平台执行器() -> None:
    global _接受调用, _全部关闭任务
    with _资源锁:
        if _全部关闭任务 is not None and not _全部关闭任务.done():
            completion = _全部关闭任务
        else:
            _接受调用 = False
            states = list(_平台状态.values())
            for state in states:
                state["raw_closed"] = True
            completion = _全部关闭任务 = Future()
            threading.Thread(target=_关闭协调, args=(states, completion), name="platform-shutdown", daemon=True).start()
    await _等待原调用(completion)


def 启动平台执行器() -> None:
    global _接受调用
    with _资源锁:
        if _全部关闭任务 is not None and not _全部关闭任务.done():
            raise 平台执行错误("shutdown_in_progress")
        _接受调用 = True
        for state in _平台状态.values():
            state["raw_closed"] = False
