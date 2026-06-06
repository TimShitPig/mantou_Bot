from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import random
import re
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp
from astrbot.api import logger

try:
    from astrbot.api import message_components as Comp
except Exception:
    Comp = None

try:
    from 功能文件.管理功能.网盘功能 import UC网盘
except Exception as exc:
    UC网盘 = None
    logger.warning(f"UC网盘模块加载失败：error={exc}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as exc:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={exc}")

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except Exception:
    AES = None
    unpad = None


签名密钥 = "d3dGiJc651gSQ8w1"
应用版本列表 = [
    "73720", "73700", "73620", "73600", "73500", "73420", "73400",
    "73328", "73325", "73320", "73300", "73220", "73200", "73100",
    "73000", "72900", "72820", "72800", "70720", "62010", "62112",
]
解密密钥 = bytes.fromhex("32343263636238323330643730396531")
下载并发数 = 20
进度日志分段数 = 10
下载缓存目录 = Path(__file__).resolve().parents[2] / "下载缓存"
文件组件缓存清理延迟 = 600
文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"


def 获取七猫小说回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[str] | None:
    下载关键词 = (
        提取直接七猫链接参数(命令文本)
        or 提取事件七猫链接(event)
    )
    if 下载关键词 is None:
        return None
    return 生成下载回复流(event, 下载关键词, 配置)


async def 生成下载回复流(event: Any, 关键词: str, 配置: Any = None) -> AsyncIterator[str]:
    if not 关键词:
        yield "没有识别到七猫小说链接"
        return
    if AES is None or unpad is None:
        yield "七猫小说下载失败：缺少 pycryptodome 依赖，请先安装 requirements.txt"
        return

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=30)) as session:
            书籍编号 = await 解析书籍编号(session, 关键词)
            if not 书籍编号:
                yield "没有找到可下载的七猫小说"
                return

            详情 = await 获取小说详情(session, 书籍编号)
            目录 = await 获取小说目录(session, 书籍编号)
            if not 目录:
                yield "七猫小说下载失败：没有获取到章节目录"
                return

            logger.info(
                f"七猫小说开始下载：book_id={书籍编号}, "
                f"title={详情.get('title')}, author={详情.get('author')}, chapters={len(目录)}"
            )
            yield 格式化下载提示(详情, len(目录))

            章节内容 = await 下载全部章节(session, 书籍编号, 目录)
            成功章节 = [项目 for 项目 in 章节内容 if 项目["content"]]
            if not 成功章节:
                yield "七猫小说下载失败：没有获取到可用章节正文"
                return

            文件名, 文件内容 = 生成小说文件内容(书籍编号, 详情, 目录, 章节内容)
            logger.info(
                f"七猫小说章节下载完成：book_id={书籍编号}, "
                f"title={详情.get('title')}, success={len(成功章节)}, total={len(目录)}, file_size={len(文件内容)}"
            )
            发送结果 = await 准备发送文本文件给当前会话(event, 文件名, 文件内容, 配置)
            文件发送结果 = 发送结果.get("chain_result")
            if 文件发送结果 is not None:
                try:
                    yield 文件发送结果
                finally:
                    延迟删除下载缓存文件(发送结果.get("cache_path"))
                return
            发送成功 = bool(发送结果.get("sent"))
            发送错误 = str(发送结果.get("error") or "")
    except Exception as exc:
        logger.warning(f"七猫小说下载失败：keyword={关键词}, error={exc}")
        yield f"七猫小说下载失败：{exc}"
        return

    if 发送成功:
        return

    标题 = 详情.get("title") or f"七猫小说{书籍编号}"
    失败数量 = len(章节内容) - len(成功章节)
    回复 = [
        f"七猫小说文件发送失败：{标题}",
        f"章节：成功 {len(成功章节)} / 总计 {len(目录)}",
        f"文件：{文件名}",
    ]
    if 失败数量:
        回复.append(f"失败章节：{失败数量}")
    回复.append(f"原因：{发送错误}")
    回复.append("下载缓存文件已删除，没有保存在本地")
    yield "\n".join(回复)


async def 搜索小说(session: aiohttp.ClientSession, 关键词: str) -> list[dict[str, Any]]:
    参数 = 签名参数({
        "extend": "",
        "tab": "0",
        "gender": "0",
        "refresh_state": "8",
        "page": "1",
        "wd": 关键词,
        "is_short_story_user": "0",
    })
    数据 = await 请求JSON(session, "https://api-bc.wtzw.com/search/v1/words", 参数, 生成请求头("00000000"))
    书籍列表 = 读取字段路径(数据, ("data", "books"))
    return [书籍 for 书籍 in (书籍列表 or []) if isinstance(书籍, dict)]


async def 解析书籍编号(session: aiohttp.ClientSession, 关键词: str) -> str:
    链接编号 = 提取书籍编号(关键词)
    if 链接编号:
        return 链接编号
    搜索结果 = await 搜索小说(session, 关键词)
    if not 搜索结果:
        return ""
    return str(搜索结果[0].get("id") or "")


async def 获取小说详情(session: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    数据 = await 请求JSON(
        session,
        "https://api-bc.wtzw.com/api/v1/reader/detail",
        签名参数({"id": 书籍编号}),
        生成请求头(书籍编号),
    )
    详情 = 数据.get("data") if isinstance(数据, dict) else {}
    if not isinstance(详情, dict) or not 详情:
        raise RuntimeError("小说详情接口没有返回有效数据")
    return {
        "title": 清理网页文本(详情.get("title") or f"七猫小说{书籍编号}"),
        "author": 清理网页文本(详情.get("author") or "未知"),
        "intro": 清理网页文本(详情.get("intro") or ""),
        "words_num": 详情.get("words_num") or "",
        "is_over": 详情.get("is_over") or "",
        "chapters": 详情.get("chapters") or "",
        "chapter_list_desc": 清理网页文本(详情.get("chapter_list_desc") or ""),
        "category_over_words": 清理网页文本(详情.get("category_over_words") or ""),
        "tags": "、".join(
            清理网页文本(标签.get("title") or "")
            for 标签 in 详情.get("book_tag_list", [])
            if isinstance(标签, dict) and 标签.get("title")
        ),
    }


async def 获取小说目录(session: aiohttp.ClientSession, 书籍编号: str) -> list[dict[str, Any]]:
    数据 = await 请求JSON(
        session,
        "https://api-ks.wtzw.com/api/v1/chapter/chapter-list",
        签名参数({"chapter_ver": "0", "id": 书籍编号}),
        生成请求头(书籍编号),
    )
    章节列表 = 读取字段路径(数据, ("data", "chapter_lists")) or []
    目录 = [章节 for 章节 in 章节列表 if isinstance(章节, dict) and 章节.get("id")]
    return sorted(目录, key=lambda 章节: int(章节.get("chapter_sort") or 0))


async def 下载全部章节(
    session: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
) -> list[dict[str, str]]:
    信号量 = asyncio.Semaphore(下载并发数)
    总数 = len(目录)
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上次日志进度 = 0
    进度锁 = asyncio.Lock()

    logger.info(f"七猫小说章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%")

    async def 记录进度(是否成功: bool) -> None:
        nonlocal 已完成, 成功数, 失败数, 上次日志进度
        async with 进度锁:
            已完成 += 1
            if 是否成功:
                成功数 += 1
            else:
                失败数 += 1

            当前进度 = 进度日志分段数 if 已完成 >= 总数 else int(已完成 * 进度日志分段数 / 总数)
            if 当前进度 <= 上次日志进度 and 已完成 < 总数:
                return
            上次日志进度 = 当前进度
            百分比 = int(已完成 * 100 / 总数) if 总数 else 100
            logger.info(
                f"七猫小说章节进度：book_id={书籍编号}, "
                f"progress={已完成}/{总数}, percent={百分比}%, success={成功数}, failed={失败数}"
            )

    async def 下载单章(章节: dict[str, Any]) -> dict[str, str]:
        async with 信号量:
            标题 = 清理网页文本(章节.get("title") or f"第{章节.get('chapter_sort', '')}章")
            章节编号 = str(章节.get("id"))
            try:
                正文 = await 获取章节正文(session, 书籍编号, 章节编号)
                await 记录进度(True)
                return {"id": 章节编号, "title": 标题, "content": 正文}
            except Exception as exc:
                logger.warning(f"七猫章节下载失败：book_id={书籍编号}, chapter_id={章节编号}, error={exc}")
                await 记录进度(False)
                return {"id": 章节编号, "title": 标题, "content": ""}

    return await asyncio.gather(*(下载单章(章节) for 章节 in 目录))


async def 获取章节正文(session: aiohttp.ClientSession, 书籍编号: str, 章节编号: str) -> str:
    数据 = await 请求JSON(
        session,
        "https://api-ks.wtzw.com/api/v1/chapter/content",
        签名参数({"id": 书籍编号, "chapterId": 章节编号}),
        生成请求头(书籍编号),
    )
    加密正文 = 读取字段路径(数据, ("data", "content"))
    if not 加密正文:
        错误 = 读取字段路径(数据, ("errors", "details")) or "章节正文为空"
        raise RuntimeError(str(错误))
    return 解密正文(str(加密正文))


async def 请求JSON(
    session: aiohttp.ClientSession,
    地址: str,
    参数: dict[str, Any],
    请求头: dict[str, str],
) -> dict[str, Any]:
    async with session.get(地址, params=参数, headers=请求头) as response:
        文本 = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}: {文本[:120]}")
        try:
            数据 = await response.json(content_type=None)
        except Exception as exc:
            raise RuntimeError(f"JSON解析失败：{文本[:120]}") from exc
        if isinstance(数据, dict) and 数据.get("errors"):
            详情 = 读取字段路径(数据, ("errors", "details")) or 读取字段路径(数据, ("errors", "title"))
            raise RuntimeError(str(详情 or "接口返回错误"))
        return 数据


def 生成小说文件内容(
    书籍编号: str,
    详情: dict[str, Any],
    目录: list[dict[str, Any]],
    章节内容: list[dict[str, str]],
) -> tuple[str, bytes]:
    标题 = 详情.get("title") or f"七猫小说{书籍编号}"
    文件名 = 生成小说文件名(书籍编号, 详情)
    标签 = 详情.get("tags") or ""

    内容列表 = [
        文件声明,
        "",
        f"名称：{标题}",
        f"作者：{详情.get('author') or '未知'}",
        f"标签：{标签}",
        f"字数：{详情.get('words_num') or '未知'}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(目录)}",
        "",
        "简介：",
        str(详情.get("intro") or ""),
        "",
    ]

    for 章节 in 章节内容:
        if not 章节["content"]:
            continue
        内容列表.append(章节["title"])
        内容列表.append("")
        内容列表.append(章节["content"].strip())
        内容列表.append("")

    return 文件名, "\n".join(内容列表).encode("utf-8")


def 生成小说文件名(书籍编号: str, 详情: dict[str, Any]) -> str:
    状态 = 获取状态文本(详情)
    标题 = 清理文件名(详情.get("title") or f"七猫小说{书籍编号}")
    作者 = 清理文件名(详情.get("author") or "未知")
    return f"[{状态}]书名：{标题} 作者：{作者}.txt"


def 格式化下载提示(详情: dict[str, Any], 目录数量: int) -> str:
    return "\n".join([
        f"书名：{详情.get('title') or '未知'}",
        f"作者：{详情.get('author') or '未知'}",
        f"状态：{获取状态文本(详情)}",
        f"章节：{获取章节数量文本(详情, 目录数量)}",
        f"字数：{格式化字数(详情.get('words_num'))}",
        "",
        "正在下载中请稍等.....",
    ])


def 获取状态文本(详情: dict[str, Any]) -> str:
    if str(详情.get("is_over")) == "1":
        return "完结"
    for 字段名 in ("category_over_words", "chapter_list_desc"):
        文本 = str(详情.get(字段名) or "")
        if "完结" in 文本:
            return "完结"
        if "连载" in 文本:
            return "连载"
    return "连载"


def 获取章节数量文本(详情: dict[str, Any], 目录数量: int) -> str:
    章节数 = str(详情.get("chapters") or "").strip()
    if not 章节数:
        章节数 = str(目录数量)
    return f"{章节数} 章"


def 格式化字数(字数: Any) -> str:
    文本 = str(字数 or "").strip()
    if not 文本:
        return "未知"
    if "字" in 文本:
        return 文本
    if 文本.isdigit():
        数值 = int(文本)
        if 数值 >= 10000:
            return f"{round(数值 / 10000)}万字"
        return f"{数值}字"
    return 文本



async def 准备发送文本文件给当前会话(event: Any, 文件名: str, 文件内容: bytes, 配置: Any = None) -> dict[str, Any]:
    群号 = 获取群号(event)
    用户号 = 获取发送者QQ(event)
    logger.info(f"七猫小说准备发送文件：file={文件名}, size={len(文件内容)}, group_id={群号}, user_id={用户号}")

    缓存路径 = 写入下载缓存文件(文件名, 文件内容)
    logger.info(f"七猫小说写入下载缓存：file={缓存路径}, size={len(文件内容)}")
    发送缓存路径 = 缓存路径
    原小说缓存待删除 = False
    if UC网盘 is not None:
        UC结果 = await UC网盘.准备小说分享链接文件(配置, 缓存路径, 文件名, 写入下载缓存文件)
        if UC结果.get("success") and UC结果.get("cache_path"):
            发送缓存路径 = UC结果.get("cache_path")
            原小说缓存待删除 = True
            logger.info(f"七猫小说UC网盘上传成功，改发同名链接文件：file={文件名}, share_url={UC结果.get('share_url')}")
        elif UC结果.get("enabled"):
            logger.warning(f"七猫小说UC网盘上传失败，回退发送源文件：file={文件名}, error={UC结果.get('error')}")

    if 百度网盘 is not None:
        百度结果 = await 百度网盘.后台上传小说文件(配置, 缓存路径, 文件名)
        if 百度结果.get("success"):
            logger.info(f"七猫小说百度网盘后台上传成功：file={文件名}, fs_id={百度结果.get('file_id')}")
        elif 百度结果.get("skipped"):
            logger.info(f"七猫小说百度网盘后台上传按状态规则跳过：file={文件名}")
        elif 百度结果.get("enabled"):
            logger.warning(f"七猫小说百度网盘后台上传失败，不影响QQ发送：file={文件名}, error={百度结果.get('error')}")

    if 原小说缓存待删除:
        删除下载缓存文件(缓存路径)

    if Comp is not None and hasattr(event, "chain_result"):
        try:
            文件发送结果 = event.chain_result([Comp.File(name=文件名, file=str(发送缓存路径))])
            logger.info(f"七猫小说文件使用 AstrBot File 组件发送：file={文件名}, path={发送缓存路径}")
            return {"sent": True, "chain_result": 文件发送结果, "cache_path": 发送缓存路径, "error": ""}
        except Exception as exc:
            logger.warning(f"七猫小说 AstrBot File 组件构建失败：file={文件名}, error={exc}")

    bot = getattr(event, "bot", None)
    api = getattr(bot, "api", None)
    调用方法 = getattr(api, "call_action", None)
    if not callable(调用方法):
        删除下载缓存文件(发送缓存路径)
        return {"sent": False, "chain_result": None, "cache_path": None, "error": "当前 bot 没有 api.call_action 接口，也无法使用 AstrBot File 组件"}

    try:
        发送成功, 发送错误 = await 尝试发送缓存文件(调用方法, 群号, 用户号, 文件名, 发送缓存路径)
        return {"sent": 发送成功, "chain_result": None, "cache_path": None, "error": 发送错误}
    finally:
        删除下载缓存文件(发送缓存路径)


def 删除下载缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    try:
        Path(缓存路径).unlink(missing_ok=True)
        logger.info(f"七猫小说下载缓存文件已删除：file={缓存路径}")
    except Exception as exc:
        logger.warning(f"七猫小说下载缓存文件删除失败：file={缓存路径}, error={exc}")


def 延迟删除下载缓存文件(缓存路径: Any, 延迟秒数: int = 文件组件缓存清理延迟) -> None:
    if not 缓存路径:
        return

    async def 执行删除() -> None:
        await asyncio.sleep(延迟秒数)
        删除下载缓存文件(缓存路径)

    try:
        asyncio.create_task(执行删除())
    except RuntimeError:
        删除下载缓存文件(缓存路径)

async def 尝试发送缓存文件(
    调用方法: Any,
    群号: str,
    用户号: str,
    文件名: str,
    缓存路径: Path,
) -> tuple[bool, str]:
    候选列表 = [("path", str(缓存路径)), ("file_uri", 缓存路径.as_uri())]
    成功, 错误 = await 按候选发送文件(调用方法, 群号, 用户号, 文件名, 候选列表)
    if 成功:
        return True, ""
    logger.warning(f"七猫小说下载缓存文件发送失败：file={缓存路径}, error={错误}")
    return False, 错误


async def 按候选发送文件(
    调用方法: Any,
    群号: str,
    用户号: str,
    文件名: str,
    候选列表: list[tuple[str, str]],
) -> tuple[bool, str]:
    if not 群号 and not 用户号:
        return False, "没有获取到群号或用户号"

    错误列表 = []
    for 方法名, 文件参数 in 候选列表:
        try:
            if 群号:
                await 调用方法("upload_group_file", group_id=群号, file=文件参数, name=文件名)
                logger.info(f"七猫小说文件发送成功：method={方法名}, target=group, file={文件名}, group_id={群号}")
                return True, ""
            await 调用方法("upload_private_file", user_id=用户号, file=文件参数, name=文件名)
            logger.info(f"七猫小说文件发送成功：method={方法名}, target=private, file={文件名}, user_id={用户号}")
            return True, ""
        except Exception as exc:
            错误文本 = f"{方法名}: {exc}"
            错误列表.append(错误文本)
            logger.warning(f"七猫小说文件发送候选失败：method={方法名}, file={文件名}, error={exc}")
    return False, "；".join(错误列表)


def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    return 缓存路径


def 生成不冲突缓存路径(文件名: str) -> Path:
    安全文件名 = Path(清理文件名(文件名)).name or "七猫小说.txt"
    if not 安全文件名.lower().endswith(".txt"):
        安全文件名 = f"{安全文件名}.txt"
    缓存路径 = 下载缓存目录 / 安全文件名
    if not 缓存路径.exists():
        return 缓存路径

    后缀 = 缓存路径.suffix
    主名 = 缓存路径.stem
    for 序号 in range(1, 1000):
        候选路径 = 下载缓存目录 / f"{主名}_{序号}{后缀}"
        if not 候选路径.exists():
            return 候选路径
    raise RuntimeError("下载缓存目录中同名文件过多")


def 签名参数(参数: dict[str, Any]) -> dict[str, Any]:
    结果 = dict(参数)
    待签名 = "".join(f"{键}={结果[键]}" for 键 in sorted(结果)) + 签名密钥
    结果["sign"] = hashlib.md5(待签名.encode("utf-8")).hexdigest()
    return 结果


def 生成请求头(书籍编号: str) -> dict[str, str]:
    random.seed(书籍编号)
    请求头 = {
        "AUTHORIZATION": "",
        "app-version": random.choice(应用版本列表),
        "application-id": "com.****.reader",
        "channel": "unknown",
        "net-env": "1",
        "platform": "android",
        "qm-params": "",
        "reg": "0",
    }
    待签名 = "".join(f"{键}={请求头[键]}" for 键 in sorted(请求头)) + 签名密钥
    请求头["sign"] = hashlib.md5(待签名.encode("utf-8")).hexdigest()
    return 请求头


def 解密正文(加密正文: str) -> str:
    原始内容 = base64.b64decode(加密正文)
    cipher = AES.new(解密密钥, AES.MODE_CBC, iv=原始内容[:16])
    解密内容 = unpad(cipher.decrypt(原始内容[16:]), AES.block_size)
    return 解密内容.decode("utf-8").strip()


def 提取直接七猫链接参数(命令文本: str) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None
    if 包含七猫链接(文本):
        return 文本
    return None


def 提取事件七猫链接(event: Any) -> str | None:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            链接 = 提取七猫链接(读取字段(对象, 字段名))
            if 链接:
                return 链接
    return None


def 提取七猫链接(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            链接 = 提取七猫链接(子值)
            if 链接:
                return 链接
        return ""
    if isinstance(值, dict):
        for 子值 in 值.values():
            链接 = 提取七猫链接(子值)
            if 链接:
                return 链接
        return ""
    文本 = str(值)
    for 模式 in (
        r"https?://(?:www\.)?qimao\.com/shuku/\d+/?",
        r"https?://app-share\.wtzw\.com/[^\s'\"<>，。]+(?:article-detail|short-story-detail)/\d+[^\s'\"<>，。]*",
    ):
        匹配 = re.search(模式, 文本)
        if 匹配:
            return 匹配.group(0)
    if 包含七猫链接(文本):
        return 文本
    return ""


def 包含七猫链接(文本: str) -> bool:
    return bool(
        re.search(r"qimao\.com/shuku/\d+", 文本)
        or re.search(r"app-share\.wtzw\.com/.+(?:article-detail|short-story-detail)/\d+", 文本)
    )


def 提取书籍编号(文本: str) -> str:
    文本 = str(文本 or "").strip()
    if re.fullmatch(r"\d{4,20}", 文本):
        return 文本
    for 模式 in (
        r"qimao\.com/shuku/(\d+)",
        r"(?:article-detail|short-story-detail)/(\d+)",
        r"(?:book_id|bookid|id)=(\d+)",
    ):
        匹配 = re.search(模式, 文本)
        if 匹配:
            return 匹配.group(1)
    return ""


def 清理网页文本(文本: Any) -> str:
    文本 = re.sub(r"<[^>]+>", "", str(文本 or ""))
    return html.unescape(文本).strip()


def 清理文件名(文件名: str) -> str:
    文件名 = re.sub(r'[\\/:*?"<>|]', "_", 文件名).strip()
    return 文件名[:80] or "七猫小说"


def 读取字段路径(数据: Any, 路径: tuple[str, ...]) -> Any:
    当前 = 数据
    for 字段 in 路径:
        if not isinstance(当前, dict):
            return None
        当前 = 当前.get(字段)
    return 当前


def 获取群号(event: Any) -> str:
    for 方法名 in ("get_group_id", "get_group"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "group_id") or 读取字段(对象, "group")
        if isinstance(值, dict):
            值 = 值.get("group_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 获取发送者QQ(event: Any) -> str:
    for 方法名 in ("get_sender_id", "get_user_id"):
        方法 = getattr(event, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        值 = 读取字段(对象, "sender_id") or 读取字段(对象, "user_id") or 读取字段(对象, "sender")
        if isinstance(值, dict):
            值 = 值.get("user_id") or 值.get("id")
        if 值:
            return str(值)
    return ""


def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
