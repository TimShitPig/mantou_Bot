from __future__ import annotations
import html
import asyncio
import json
import math
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator
import aiohttp
from astrbot.api import logger
try:
    from astrbot.api import message_components as 消息组件
except Exception:
    消息组件 = None
try:
    from 功能文件.API功能.析API import 番茄小说 as 析API番茄小说
except Exception as 异常:
    析API番茄小说 = None
    logger.warning(f'析API番茄小说模块加载失败：error={异常}')
OIAPI地址 = 'https://oiapi.net/api/FqRead'
落地页接口地址 = 'https://api.fqnovel.com/novel_ug/share/landing_page'
下载缓存目录 = Path(__file__).resolve().parents[2] / '下载缓存'
API状态文件 = 下载缓存目录 / '番茄小说API.json'
免责声明 = '声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。'
每段最大字数 = 5000000
进度分段数 = 10
文件组件缓存删除延迟 = 600
API选择等待秒数 = 120
API选项 = {'1': 'OIAPI', '2': '析API'}
待选择API会话: dict[str, float] = {}
浏览器请求头 = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36', 'Accept': 'application/json, text/plain, */*', 'Referer': 'https://fanqienovel.com/'}
番茄域名正则 = re.compile('fanqienovel\\.com|changdunovel\\.com|fqnovel\\.com|novelfm\\.com', re.IGNORECASE)
长读短链正则 = re.compile('https?://(?:www\\.)?changdunovel\\.com/t/[A-Za-z0-9_-]+/?', re.IGNORECASE)
链接正则 = re.compile('https?://[^\\s\'\\"<>\\u3001\\uff0c\\u3002]+', re.IGNORECASE)

def 获取番茄小说回复流(事件: Any, 命令文本: str, 配置: Any) -> AsyncIterator[str] | None:
    来源 = 提取直接来源(命令文本) or 提取事件来源(事件)
    if 来源 is None:
        return None
    return 生成下载回复流(事件, 来源, 配置)


def 处理番茄小说API指令(事件: Any, 命令文本: str) -> str | None:
    文本 = str(命令文本 or '').strip()
    会话键 = 获取API会话键(事件)
    if 文本.lower() == '查看api':
        待选择API会话[会话键] = time.time()
        当前接口 = 读取当前番茄小说接口()
        return '\n'.join([
            f'当前番茄小说API：{当前接口}',
            '请选择番茄小说API：',
            '1. OIAPI（oiapi.net，需要配置 番茄小说key）',
            '2. 析API（biek.top，不需要 番茄小说key）',
            f'请在 {API选择等待秒数} 秒内发送 1 或 2 完成切换',
        ])
    if 文本 in API选项 and API选择等待中(会话键):
        接口名称 = API选项[文本]
        写入当前番茄小说接口(接口名称)
        待选择API会话.pop(会话键, None)
        return f'番茄小说API已切换为：{接口名称}'
    return None


async def 生成下载回复流(事件: Any, 来源: str, 配置: Any) -> AsyncIterator[str]:
    接口key = 获取番茄小说key(配置)
    接口来源 = 读取当前番茄小说接口()
    书籍编号 = 提取书籍编号(来源)
    解析来源 = 来源
    章节列表: list[dict[str, Any]] = []
    章节结果列表: list[dict[str, Any]] = []
    成功章节列表: list[dict[str, Any]] = []
    文件名 = ''
    书籍信息: dict[str, Any] = {}
    已发送 = False
    发送错误 = ''
    try:
        超时 = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=90)
        async with aiohttp.ClientSession(timeout=超时, headers=浏览器请求头) as 会话:
            if not 书籍编号:
                解析来源 = await 展开番茄短链(会话, 来源)
                书籍编号 = 提取书籍编号(解析来源)
            if 接口来源 == '析API':
                if 析API番茄小说 is None:
                    yield '番茄小说下载失败：析API模块不可用'
                    return
                准备来源 = 解析来源 if 书籍编号 else 来源
                准备结果 = await 析API番茄小说.准备番茄小说(会话, 准备来源, 书籍编号, {})
                if not 准备结果.get('success'):
                    yield f"番茄小说下载失败：{限制文本长度(准备结果.get('error') or '析API准备失败', 500)}"
                    return
                书籍编号 = str(准备结果.get('book_id') or 书籍编号)
                书籍信息 = 准备结果.get('book_info') or 默认书籍信息(书籍编号)
                章节列表 = 准备结果.get('chapters') or []
                logger.info(f"番茄小说开始下载：source=析API, book_id={书籍编号}, title={书籍信息.get('title')}, author={书籍信息.get('author')}, chapters={len(章节列表)}")
                yield 格式化下载提示(书籍信息, len(章节列表))
                章节结果列表 = await 析API番茄小说.下载全部章节(会话, 书籍编号, 章节列表)
                成功章节列表 = [项目 for 项目 in 章节结果列表 if 项目.get('success')]
                if not 成功章节列表:
                    yield '番茄小说下载失败：析API没有获取到可用章节正文'
                    return
            else:
                if not 接口key:
                    yield '番茄小说下载失败：缺少插件配置 番茄小说key；如需使用析API，请发送“查看API”后选择 2'
                    return
                if not 书籍编号:
                    yield '没有识别到番茄小说链接'
                    return
                书籍信息 = await 获取书籍信息(会话, 书籍编号, 解析来源)
                章节列表 = await 获取章节目录(会话, 书籍编号, 接口key)
                if not 章节列表:
                    章节列表 = 构造序号目录(安全整数(书籍信息.get('chapter_count')))
                if not 章节列表:
                    yield '番茄小说下载失败：OIAPI没有获取到章节目录'
                    return
                书籍信息 = 合并书籍信息(书籍信息, {'chapter_count': len(章节列表)})
                logger.info(f"番茄小说开始下载：source=OIAPI, book_id={书籍编号}, title={书籍信息.get('title')}, author={书籍信息.get('author')}, chapters={len(章节列表)}")
                yield 格式化下载提示(书籍信息, len(章节列表))
                章节结果列表 = await 下载全部章节(会话, 书籍编号, 章节列表, 接口key, 解析字数(书籍信息.get('word_count')))
                成功章节列表 = [项目 for 项目 in 章节结果列表 if 项目.get('success')]
                if not 成功章节列表:
                    yield '番茄小说下载失败：OIAPI没有获取到可用章节正文'
                    return
            文件名, 文件内容 = 构造TXT文件(书籍编号, 书籍信息, 章节列表, 章节结果列表)
            logger.info(f"番茄小说章节下载完成：book_id={书籍编号}, title={书籍信息.get('title')}, success={len(成功章节列表)}, total={len(章节列表)}, file_size={len(文件内容)}")
            发送结果 = await 准备发送文本文件(事件, 文件名, 文件内容)
            缓存路径 = 发送结果.get('cache_path')
            链式结果 = 发送结果.get('chain_result')
            if 链式结果 is not None:
                try:
                    yield 链式结果
                finally:
                    延迟删除缓存文件(缓存路径)
                return
            已发送 = bool(发送结果.get('sent'))
            发送错误 = str(发送结果.get('error') or '')
    except Exception as 异常:
        logger.warning(f'番茄小说下载失败：source={限制文本长度(解析来源)}, book_id={书籍编号}, error={异常}')
        yield f'番茄小说下载失败：{异常}'
        return
    if 已发送:
        return
    书名 = 书籍信息.get('title') or f'番茄小说{书籍编号}'
    yield '\n'.join([f'番茄小说文件发送失败：{书名}', f'章节：成功 {len(成功章节列表)} / 总计 {len(章节列表)}', f'文件：{文件名}', f'原因：{限制文本长度(发送错误, 500)}', '下载缓存文件已删除，没有保存在本地'])


async def 获取书籍信息(会话: aiohttp.ClientSession, 书籍编号: str, 来源: str) -> dict[str, Any]:
    书籍信息 = 默认书籍信息(书籍编号)
    书籍信息 = 合并书籍信息(书籍信息, await 获取分享落地页信息(会话, 来源, 书籍编号))
    return 合并书籍信息(书籍信息, await 获取网页书籍信息(会话, 书籍编号))

async def 获取分享落地页信息(会话: aiohttp.ClientSession, 来源: str, 书籍编号: str) -> dict[str, Any]:
    if not str(来源 or '').startswith('http'):
        return {}
    try:
        async with 会话.get(来源, allow_redirects=True, timeout=20) as 响应:
            网页文本 = await 响应.text()
            最终地址 = str(响应.url)
    except Exception as 异常:
        logger.debug(f'fanqie share page failed: source={限制文本长度(来源)}, error={异常}')
        return {}
    查询参数 = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(最终地址).query, keep_blank_values=True))
    参数 = {'aid': 查询参数.get('aid', '1967'), 'series_id': 查询参数.get('series_id', '0'), 'encrypt_did': 查询参数.get('encrypt_did', ''), 'performance_optimization': '1', 'share_type': 查询参数.get('share_type', '11'), 'video_id': 查询参数.get('video_id', ''), 'actor_id': 查询参数.get('actor_id', ''), 'post_id': 查询参数.get('post_id', ''), 'book_id': 查询参数.get('book_id') or 书籍编号, 'pos_info_str': 'undefined:undefined:undefined:undefined:undefined:undefined'}
    请求头 = dict(浏览器请求头)
    请求头.update({'Referer': 'https://changdunovel.com/', 'x-xs-from-web': '1', 'Content-Type': 'application/json'})
    try:
        async with 会话.get(落地页接口地址, params=参数, headers=请求头, timeout=20) as 响应:
            响应数据 = await 响应.json(content_type=None)
    except Exception as 异常:
        logger.debug(f'fanqie landing meta failed: book_id={书籍编号}, error={异常}')
        return 从网页文本提取书籍信息(网页文本)
    数据 = 读取路径(响应数据, ('data', 'book_data'))
    if not isinstance(数据, dict):
        return 从网页文本提取书籍信息(网页文本)
    作者 = 数据.get('author')
    if isinstance(作者, dict):
        作者 = 作者.get('name')
    return {'title': 清理书名(读取任意字段(数据, ('book_name', 'bookName', 'bookTitle', 'title', 'name'))), 'author': 清理文本(作者), 'word_count': 格式化字数(数据.get('word_count') or 数据.get('preview_word_count')), 'status': 规范化状态(数据.get('creation_status'), ''), 'chapter_count': 安全整数(数据.get('chapter_count') or 数据.get('chapter_num') or 数据.get('all_chapter_num') or 数据.get('latest_chapter_index')), 'intro': 清理简介(读取任意字段(数据, ('abstract', 'description', 'summary', 'book_abstract', 'bookAbstract', 'intro')))}

async def 获取网页书籍信息(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    try:
        async with 会话.get(f'https://fanqienovel.com/page/{书籍编号}', timeout=20) as 响应:
            if 响应.status >= 400:
                return {}
            网页文本 = await 响应.text()
    except Exception as 异常:
        logger.debug(f'fanqie page meta failed: book_id={书籍编号}, error={异常}')
        return {}
    return 合并书籍信息(从网页文本提取书籍信息(网页文本), 从状态提取书籍信息(提取初始状态(网页文本)))

async def 展开番茄短链(会话: aiohttp.ClientSession, 来源: str) -> str:
    if not 长读短链正则.search(str(来源 or '')):
        return 来源
    try:
        async with 会话.get(来源, allow_redirects=True, timeout=20) as 响应:
            最终地址 = str(响应.url)
            网页文本 = await 响应.text()
    except Exception as 异常:
        logger.debug(f'番茄小说短链展开失败：source={限制文本长度(来源)}, error={异常}')
        return 来源
    if 提取书籍编号(最终地址):
        logger.info(f'番茄小说短链已展开：source={来源}, target={最终地址}')
        return 最终地址
    if 提取书籍编号(网页文本):
        logger.info(f'番茄小说短链页面包含书籍ID：source={来源}')
        return 网页文本
    return 最终地址 or 来源

async def 获取章节目录(会话: aiohttp.ClientSession, 书籍编号: str, 接口key: str) -> list[dict[str, Any]]:
    响应数据 = await 请求FqRead(会话, 书籍编号, 接口key, 'chapters', '')
    目录 = 提取章节目录(响应数据.get('data') if isinstance(响应数据, dict) else 响应数据)
    if not 目录 and isinstance(响应数据, dict):
        目录 = 提取章节目录(响应数据.get('message'))
    logger.info(f'番茄小说目录获取完成：book_id={书籍编号}, chapters={len(目录)}')
    return 目录

async def 下载全部章节(会话: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]], 接口key: str, 总字数: int) -> list[dict[str, Any]]:
    总数 = len(目录)
    已完成 = 0
    成功数 = 0
    失败数 = 0
    上一进度段 = 0
    结果列表: list[dict[str, Any]] = []
    logger.info(f'番茄小说章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%')

    def 记录进度(批次结果: list[dict[str, Any]]) -> None:
        nonlocal 已完成, 成功数, 失败数, 上一进度段
        已完成 += len(批次结果)
        成功数 += sum((1 for 项目 in 批次结果 if 项目.get('success')))
        失败数 += sum((1 for 项目 in 批次结果 if not 项目.get('success')))
        进度段 = 进度分段数 if 已完成 >= 总数 else int(已完成 * 进度分段数 / 总数)
        if 进度段 <= 上一进度段 and 已完成 < 总数:
            return
        上一进度段 = 进度段
        百分比 = int(已完成 * 100 / 总数) if 总数 else 100
        logger.info(f'番茄小说章节进度：book_id={书籍编号}, progress={已完成}/{总数}, percent={百分比}%, success={成功数}, failed={失败数}')
    for 分段 in 拆分章节目录(目录, 总字数):
        批次结果 = await 下载章节批次(会话, 书籍编号, 接口key, 分段)
        记录进度(批次结果)
        结果列表.extend(批次结果)
    return 结果列表

async def 下载章节批次(会话: aiohttp.ClientSession, 书籍编号: str, 接口key: str, 批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        return await 请求并映射章节批次(会话, 书籍编号, 接口key, 批次)
    except Exception as 异常:
        if len(批次) <= 1:
            章节 = 批次[0]
            logger.warning(f"番茄小说章节下载失败：book_id={书籍编号}, chapter={章节.get('index')}, chapter_id={章节.get('id')}, error={异常}")
            return [{**章节, 'content': '【下载失败】', 'success': False}]
        中点 = max(1, len(批次) // 2)
        logger.warning(f"番茄小说范围请求失败，拆分重试：book_id={书籍编号}, range={批次[0].get('index')}-{批次[-1].get('index')}, error={异常}")
        左侧结果 = await 下载章节批次(会话, 书籍编号, 接口key, 批次[:中点])
        右侧结果 = await 下载章节批次(会话, 书籍编号, 接口key, 批次[中点:])
        return 左侧结果 + 右侧结果

async def 请求并映射章节批次(会话: aiohttp.ClientSession, 书籍编号: str, 接口key: str, 批次: list[dict[str, Any]]) -> list[dict[str, Any]]:
    开始章 = min((int(章节.get('index') or 0) for 章节 in 批次))
    结束章 = max((int(章节.get('index') or 0) for 章节 in 批次))
    章节参数 = str(开始章) if 开始章 == 结束章 else f'{开始章}-{结束章}'
    响应数据 = await 请求FqRead(会话, 书籍编号, 接口key, 'chapter', 章节参数)
    原始章节项 = 规范化响应章节(响应数据.get('data') if isinstance(响应数据, dict) else 响应数据)
    if not 原始章节项 and isinstance(响应数据, dict):
        原始章节项 = 规范化响应章节(响应数据.get('message'))
    if not 原始章节项:
        raise RuntimeError('章节正文接口没有返回章节数据')
    结果列表 = 映射章节响应(批次, 原始章节项)
    匹配数 = sum((1 for 项目 in 结果列表 if 项目.get('success')))
    if 匹配数 < len(批次):
        raise RuntimeError(f'章节返回不完整：matched={匹配数}/{len(批次)}')
    return 结果列表

async def 请求FqRead(会话: aiohttp.ClientSession, 书籍编号: str, 接口key: str, 方法: str, 章节参数: str) -> dict[str, Any]:
    参数 = {'id': 书籍编号, 'book_id': 书籍编号, 'method': 方法, 'key': 接口key, 'type': 'json'}
    if 章节参数:
        参数['chapter'] = 章节参数
    async with 会话.get(OIAPI地址, params=参数, timeout=90) as 响应:
        文本 = await 响应.text()
        if 响应.status >= 400:
            raise RuntimeError(f'OIAPI HTTP {响应.status}: {限制文本长度(文本, 120)}')
        try:
            响应数据 = json.loads(文本)
        except Exception as 异常:
            raise RuntimeError(f'OIAPI JSON解析失败：{限制文本长度(文本, 120)}') from 异常
    if not isinstance(响应数据, dict):
        raise RuntimeError('OIAPI 返回格式不是对象')
    返回码 = 响应数据.get('code')
    if str(返回码) not in ('1', '200'):
        消息 = 响应数据.get('message') or 响应数据.get('msg') or 响应数据.get('error') or '接口返回失败'
        raise RuntimeError(f'OIAPI返回失败：code={返回码}, message={限制文本长度(消息, 200)}')
    return 响应数据

def 提取章节目录(数据: Any) -> list[dict[str, Any]]:
    项目列表: list[dict[str, Any]] = []

    def 遍历(值: Any) -> None:
        if isinstance(值, list):
            for 项目 in 值:
                遍历(项目)
            return
        if not isinstance(值, dict):
            return
        书名 = 清理文本(读取任意字段(值, ('title', 'chapter_title', 'name')))
        章节编号 = 清理文本(读取任意字段(值, ('chapter_id', 'chapterId', 'item_id', 'itemId', 'id')))
        序号 = 安全整数(读取任意字段(值, ('chapter', 'index', 'order', 'chapter_index', 'chapterIndex', 'realChapterOrder')))
        if (书名 or 章节编号) and (章节编号 or 序号):
            项目列表.append({'id': 章节编号 or str(序号), 'title': 书名 or f'第{序号 or len(项目列表) + 1}章', 'index': 序号 or len(项目列表) + 1})
            return
        for 子项 in 值.values():
            if isinstance(子项, (dict, list)):
                遍历(子项)
    遍历(数据)
    去重结果: list[dict[str, Any]] = []
    已见集合: set[tuple[str, int]] = set()
    for 位置, 项目 in enumerate(项目列表, start=1):
        项目['index'] = 安全整数(项目.get('index')) or 位置
        键 = (str(项目.get('id') or ''), int(项目.get('index') or 0))
        if 键 in 已见集合:
            continue
        已见集合.add(键)
        去重结果.append(项目)
    return sorted(去重结果, key=lambda 项目: int(项目.get('index') or 0))

def 规范化响应章节(数据: Any) -> list[dict[str, Any]]:
    结果列表: list[dict[str, Any]] = []

    def 遍历(值: Any) -> None:
        if isinstance(值, list):
            for 项目 in 值:
                遍历(项目)
            return
        if not isinstance(值, dict):
            return
        if 提取正文(值):
            结果列表.append(值)
            return
        for 子项 in 值.values():
            if isinstance(子项, (dict, list)):
                遍历(子项)
    遍历(数据)
    return 结果列表

def 映射章节响应(批次: list[dict[str, Any]], 原始章节项: list[dict[str, Any]]) -> list[dict[str, Any]]:
    按编号索引 = {清理文本(读取任意字段(项目, ('chapter_id', 'chapterId', 'item_id', 'itemId', 'id'))): 项目 for 项目 in 原始章节项}
    按序号索引 = {str(安全整数(读取任意字段(项目, ('chapter', 'index', 'order', 'chapter_index', 'chapterIndex')))): 项目 for 项目 in 原始章节项}
    使用顺序 = len(原始章节项) == len(批次)
    结果列表: list[dict[str, Any]] = []
    for 位置, 章节 in enumerate(批次):
        原始项 = 按编号索引.get(str(章节.get('id') or '')) or 按序号索引.get(str(章节.get('index') or ''))
        if 原始项 is None and 使用顺序:
            原始项 = 原始章节项[位置]
        正文 = 清理正文(提取正文(原始项) if 原始项 else '')
        书名 = 清理文本(读取任意字段(原始项 or {}, ('title', 'chapter_title', 'name'))) or str(章节.get('title') or f"第{章节.get('index')}章")
        结果列表.append({**章节, 'title': 书名, 'content': 正文 or '【下载失败】', 'success': bool(正文)})
    return 结果列表

def 提取正文(章节: dict[str, Any] | None) -> str:
    if not isinstance(章节, dict):
        return ''
    return 清理文本(读取任意字段(章节, ('content', 'chapter_content', 'text', 'body')))

def 拆分章节目录(目录: list[dict[str, Any]], 总字数: int) -> list[list[dict[str, Any]]]:
    if not 目录:
        return []
    拆分数 = max(1, math.ceil(总字数 / 每段最大字数)) if 总字数 > 0 else 1
    分段大小 = max(1, math.ceil(len(目录) / 拆分数))
    return [目录[开始章:开始章 + 分段大小] for 开始章 in range(0, len(目录), 分段大小)]

def 构造序号目录(章节数: int) -> list[dict[str, Any]]:
    if 章节数 <= 0:
        return []
    return [{'id': str(序号), 'title': f'第{序号}章', 'index': 序号} for 序号 in range(1, 章节数 + 1)]

def 构造TXT文件(书籍编号: str, 书籍信息: dict[str, Any], 目录: list[dict[str, Any]], 章节结果列表: list[dict[str, Any]]) -> tuple[str, bytes]:
    文件名 = 构造文件名(书籍编号, 书籍信息)
    行列表 = [免责声明, '', f"名称：{书籍信息.get('title') or f'番茄小说{书籍编号}'}", f"作者：{书籍信息.get('author') or '未知'}", f'状态：{状态文本(书籍信息)}', f"字数：{书籍信息.get('word_count') or '未知'}", f'书籍ID：{书籍编号}', f'章节数：{len(目录)}', '']
    简介 = 清理简介(书籍信息.get('intro'))
    if 简介:
        行列表.extend(['简介：', 简介, ''])
    for 章节 in 章节结果列表:
        行列表.append(str(章节.get('title') or f"第{章节.get('index')}章"))
        行列表.append('')
        行列表.append(str(章节.get('content') or '【下载失败】').strip())
        行列表.append('')
    return (文件名, '\n'.join(行列表).encode('utf-8'))

def 构造文件名(书籍编号: str, 书籍信息: dict[str, Any]) -> str:
    书名 = 清理文件名(书籍信息.get('title') or f'番茄小说{书籍编号}')
    作者 = 清理文件名(书籍信息.get('author') or '未知')
    return f'[{状态文本(书籍信息)}]书名：{书名} 作者：{作者}.txt'

def 格式化下载提示(书籍信息: dict[str, Any], 章节数: int) -> str:
    return '\n'.join([f"书名：{书籍信息.get('title') or '未知'}", f"作者：{书籍信息.get('author') or '未知'}", f'状态：{状态文本(书籍信息)}', f'章节：{章节数} 章', f"字数：{书籍信息.get('word_count') or '未知'}", '', '正在下载中请稍等.....'])

async def 准备发送文本文件(事件: Any, 文件名: str, 文件内容: bytes) -> dict[str, Any]:
    群号 = 获取群号(事件)
    用户QQ = 获取用户QQ(事件)
    logger.info(f'番茄小说准备发送文件：file={文件名}, size={len(文件内容)}, group_id={群号}, user_id={用户QQ}')
    缓存路径 = 写入缓存文件(文件名, 文件内容)
    logger.info(f'番茄小说写入下载缓存：file={缓存路径}, size={len(文件内容)}')
    if 消息组件 is not None and hasattr(事件, 'chain_result'):
        try:
            链式结果 = 事件.chain_result([消息组件.File(name=文件名, file=str(缓存路径))])
            logger.info(f'番茄小说文件使用 AstrBot File 组件发送：file={文件名}, path={缓存路径}')
            return {'sent': True, 'chain_result': 链式结果, 'cache_path': 缓存路径, 'error': ''}
        except Exception as 异常:
            logger.warning(f'番茄小说 AstrBot File 组件构建失败：file={文件名}, error={异常}')
    机器人 = getattr(事件, 'bot', None)
    接口 = getattr(机器人, 'api', None)
    调用动作 = getattr(接口, 'call_action', None)
    if callable(调用动作):
        已发送, 错误 = await 尝试发送文件候选(调用动作, 群号, 用户QQ, 文件名, [('path', str(缓存路径)), ('file_uri', 缓存路径.as_uri())])
        删除缓存文件(缓存路径)
        return {'sent': 已发送, 'chain_result': None, 'cache_path': None, 'error': 错误}
    删除缓存文件(缓存路径)
    return {'sent': False, 'chain_result': None, 'cache_path': None, 'error': '当前 bot 没有 api.call_action 接口，也无法使用 AstrBot File 组件'}

def 延迟删除缓存文件(缓存路径: Any, 延迟秒数: int=文件组件缓存删除延迟) -> None:
    if not 缓存路径:
        return

    async def 稍后删除() -> None:
        await asyncio.sleep(延迟秒数)
        删除缓存文件(缓存路径)
    try:
        asyncio.create_task(稍后删除())
    except RuntimeError:
        删除缓存文件(缓存路径)

def 删除缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    try:
        Path(缓存路径).unlink(missing_ok=True)
        logger.info(f'番茄小说下载缓存文件已删除：file={缓存路径}')
    except Exception as 异常:
        logger.warning(f'番茄小说下载缓存文件删除失败：file={缓存路径}, error={异常}')

async def 尝试发送文件候选(调用动作: Any, 群号: str, 用户QQ: str, 文件名: str, 候选列表: list[tuple[str, str]]) -> tuple[bool, str]:
    if not 群号 and (not 用户QQ):
        return (False, '没有获取到群号或用户号')
    错误列表 = []
    for 方法名, 文件参数 in 候选列表:
        try:
            if 群号:
                await 调用动作('upload_group_file', group_id=群号, file=文件参数, name=文件名)
                logger.info(f'番茄小说文件发送成功：method={方法名}, target=group, file={文件名}, group_id={群号}')
                return (True, '')
            await 调用动作('upload_private_file', user_id=用户QQ, file=文件参数, name=文件名)
            logger.info(f'番茄小说文件发送成功：method={方法名}, target=private, file={文件名}, user_id={用户QQ}')
            return (True, '')
        except Exception as 异常:
            错误列表.append(f'{方法名}: {异常}')
            logger.warning(f'番茄小说文件发送候选失败：method={方法名}, file={文件名}, error={异常}')
    return (False, '；'.join(错误列表))

def 写入缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 获取唯一缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    return 缓存路径

def 获取唯一缓存路径(文件名: str) -> Path:
    安全名称 = Path(清理文件名(文件名)).name or '番茄小说.txt'
    if not 安全名称.lower().endswith('.txt'):
        安全名称 = f'{安全名称}.txt'
    缓存路径 = 下载缓存目录 / 安全名称
    if not 缓存路径.exists():
        return 缓存路径
    后缀 = 缓存路径.suffix
    主文件名 = 缓存路径.stem
    for 序号 in range(1, 1000):
        候选路径 = 下载缓存目录 / f'{主文件名}_{序号}{后缀}'
        if not 候选路径.exists():
            return 候选路径
    raise RuntimeError('下载缓存目录中同名文件过多')

def 提取直接来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or '').strip()
    if not 文本:
        return None
    if re.fullmatch('\\d{15,25}', 文本):
        return 文本
    return 提取番茄来源(文本) or None

def 提取事件来源(事件: Any) -> str | None:
    消息对象 = getattr(事件, 'message_obj', None)
    for 对象 in (事件, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ('message_str', 'raw_message', 'message'):
            来源 = 提取番茄来源(读取字段(对象, 字段名))
            if 来源:
                return 来源
    return None

def 提取番茄来源(值: Any) -> str:
    if 值 is None:
        return ''
    if isinstance(值, (list, tuple, set)):
        for 项目 in 值:
            来源 = 提取番茄来源(项目)
            if 来源:
                return 来源
        return ''
    if isinstance(值, dict):
        for 项目 in 值.values():
            来源 = 提取番茄来源(项目)
            if 来源:
                return 来源
        return ''
    原始文本 = str(值 or '')
    for 文本 in 生成文本变体(原始文本):
        for 匹配 in 链接正则.finditer(文本):
            链接 = 匹配.group(0).rstrip('),.;]')
            if 长读短链正则.search(链接):
                return 链接
            if 番茄域名正则.search(链接) and 提取书籍编号(链接):
                return 链接
        短链匹配 = 长读短链正则.search(文本)
        if 短链匹配:
            return 短链匹配.group(0)
        if 番茄域名正则.search(文本) and 提取书籍编号(文本):
            return 文本
        if re.fullmatch('\\d{15,25}', 文本.strip()):
            return 文本.strip()
    return ''

def 提取书籍编号(文本: str) -> str:
    for 候选路径 in 生成文本变体(str(文本 or '')):
        候选路径 = 候选路径.strip()
        if re.fullmatch('\\d{15,25}', 候选路径):
            return 候选路径
        规则列表 = ('(?:book_id|bookid|bookId)=(\\d{15,25})', 'fanqienovel\\.com/(?:page|reader)?/?(\\d{15,25})', 'fanqienovel\\.com/[^\\s?&#]*/(\\d{15,25})', '(?:changdunovel\\.com|fqnovel\\.com|novelfm\\.com).*?(?:book_id|bookid|bookId)=(\\d{15,25})')
        for 规则 in 规则列表:
            匹配 = re.search(规则, 候选路径, re.IGNORECASE)
            if 匹配:
                return 匹配.group(1)
    return ''

def 生成文本变体(文本: str) -> list[str]:
    文本 = html.unescape(str(文本 or '')).replace('\\/', '/')
    变体列表 = [文本]
    for _ in range(2):
        解码文本 = urllib.parse.unquote(变体列表[-1])
        if 解码文本 == 变体列表[-1]:
            break
        变体列表.append(解码文本)
    return 变体列表

def 获取番茄小说key(配置: Any) -> str:
    值 = 读取字段(配置, '番茄小说key')
    return str(值 or '').strip()

def API选择等待中(会话键: str) -> bool:
    开始时间 = 待选择API会话.get(会话键)
    if not 开始时间:
        return False
    if time.time() - 开始时间 <= API选择等待秒数:
        return True
    待选择API会话.pop(会话键, None)
    return False

def 读取当前番茄小说接口() -> str:
    try:
        if API状态文件.exists():
            数据 = json.loads(API状态文件.read_text(encoding='utf-8'))
            return 规范化番茄小说接口(数据.get('current_api'))
    except Exception as 异常:
        logger.warning(f'番茄小说API状态读取失败：file={API状态文件}, error={异常}')
    return 'OIAPI'

def 写入当前番茄小说接口(接口名称: str) -> None:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    当前接口 = 规范化番茄小说接口(接口名称)
    数据 = {'current_api': 当前接口, 'updated_at': int(time.time())}
    API状态文件.write_text(json.dumps(数据, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f'番茄小说API已切换：api={当前接口}, file={API状态文件}')

def 规范化番茄小说接口(值: Any) -> str:
    文本 = str(值 or '').strip().lower()
    if 文本 in ('析api', 'xiapi', 'xapi', '析', 'xi', '2'):
        return '析API'
    return 'OIAPI'

def 获取API会话键(事件: Any) -> str:
    群号 = 获取群号(事件)
    用户QQ = 获取用户QQ(事件)
    return f'{群号 or "private"}:{用户QQ or "unknown"}'

def 默认书籍信息(书籍编号: str) -> dict[str, Any]:
    return {'book_id': 书籍编号, 'title': f'番茄小说{书籍编号}', 'author': '未知', 'status': '未知', 'word_count': '未知', 'chapter_count': 0}

def 合并书籍信息(基础信息: dict[str, Any], 新增信息: dict[str, Any]) -> dict[str, Any]:
    结果 = dict(基础信息 or {})
    for 键, 值 in (新增信息 or {}).items():
        if 键 == 'title':
            值 = 清理书名(值)
        elif 键 == 'intro':
            值 = 清理简介(值)
        if 值 in (None, '', 0):
            continue
        当前值 = 结果.get(键)
        if 当前值 in (None, '', 0, '未知') or (键 == 'title' and 应覆盖书名(当前值, 值)):
            结果[键] = 值
    return 结果

def 从状态提取书籍信息(状态数据: Any) -> dict[str, Any]:
    候选列表: list[tuple[int, dict[str, Any]]] = []

    def 遍历(值: Any) -> None:
        if isinstance(值, list):
            for 项目 in 值:
                遍历(项目)
            return
        if not isinstance(值, dict):
            return
        书籍信息 = 从字典提取书籍信息(值)
        分数 = 0
        if 书籍信息.get('title') and (not re.match('\\u7b2c.+[\\u7ae0\\u8282\\u56de]', str(书籍信息.get('title')))):
            分数 += 3
        if 书籍信息.get('author'):
            分数 += 3
        if 书籍信息.get('word_count') and 书籍信息.get('word_count') != '未知':
            分数 += 1
        if 书籍信息.get('chapter_count'):
            分数 += 1
        if 分数 >= 3:
            候选列表.append((分数, 书籍信息))
        for 项目 in 值.values():
            if isinstance(项目, (dict, list)):
                遍历(项目)
    遍历(状态数据)
    if not 候选列表:
        return {}
    候选列表.sort(key=lambda 项目: 项目[0], reverse=True)
    return 候选列表[0][1]

def 从字典提取书籍信息(数据: dict[str, Any]) -> dict[str, Any]:
    作者 = 读取任意字段(数据, ('author', 'author_name', 'authorName'))
    if isinstance(作者, dict):
        作者 = 读取任意字段(作者, ('name', 'author_name', 'authorName'))
    原始状态 = 读取任意字段(数据, ('creation_status', 'creationStatus', 'status', 'book_status', 'bookStatus'))
    状态描述 = 清理文本(读取任意字段(数据, ('status_text', 'statusText', 'status_desc', 'statusDesc')))
    return {'title': 清理书名(读取任意字段(数据, ('book_name', 'bookName', 'bookTitle', 'title', 'name'))), 'author': 清理文本(作者), 'word_count': 格式化字数(读取任意字段(数据, ('word_count', 'wordCount', 'word_number', 'wordNumber', 'totalWords'))), 'status': 规范化状态(原始状态, 状态描述), 'chapter_count': 安全整数(读取任意字段(数据, ('chapter_count', 'chapterCount', 'chapter_num', 'chapterNum', 'all_chapter_num', 'latest_chapter_index'))), 'intro': 清理简介(读取任意字段(数据, ('abstract', 'description', 'summary', 'book_abstract', 'bookAbstract', 'intro')))}

def 从网页文本提取书籍信息(网页文本: str) -> dict[str, Any]:
    文本 = str(网页文本 or '')
    书名 = 提取HTML字段(文本, ('<meta[^>]+property=["\\\']og:title["\\\'][^>]+content=["\\\']([^"\\\']+)', '<title>(.*?)</title>'))
    书名 = re.sub('[_-].*\\u756a\\u8304\\u5c0f\\u8bf4.*$', '', 书名).strip()
    作者 = 提取HTML字段(文本, ('authorName["\\\']?\\s*[:=]\\s*["\\\']([^"\\\']+)', 'author_name["\\\']?\\s*[:=]\\s*["\\\']([^"\\\']+)'))
    简介 = 提取HTML字段(文本, ('"abstract"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"', '<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', 'description["\']?\\s*[:=]\\s*["\']([^"\']+)'))
    return {'title': 清理书名(书名), 'author': 清理文本(作者), 'intro': 清理简介(简介)}

def 提取初始状态(网页文本: str) -> dict[str, Any]:
    匹配 = re.search('window\\.__INITIAL_STATE__\\s*=\\s*(\\{.+?)</script>', 网页文本 or '', re.DOTALL)
    if not 匹配:
        匹配 = re.search('window\\.__INITIAL_STATE__\\s*=\\s*(\\{.+)', 网页文本 or '', re.DOTALL)
    if not 匹配:
        return {}
    正文 = 匹配.group(1)
    balance = 0
    分段 = []
    for char in 正文:
        分段.append(char)
        if char == '{':
            balance += 1
        elif char == '}':
            balance -= 1
            if balance == 0:
                break
    try:
        return json.loads(''.join(分段))
    except Exception:
        return {}

def 提取HTML字段(文本: str, 规则列表: tuple[str, ...]) -> str:
    for 规则 in 规则列表:
        匹配 = re.search(规则, 文本, re.IGNORECASE | re.DOTALL)
        if 匹配:
            return 清理文本(匹配.group(1))
    return ''

def 规范化状态(原始项: Any, 状态描述: str='') -> str:
    文本 = f"{原始项 or ''} {状态描述 or ''}".strip().lower()
    if any((关键词 in 文本 for 关键词 in ('已完结', '完结', '完本', 'finished', 'completed', 'ended'))):
        return '完结'
    if any((关键词 in 文本 for 关键词 in ('连载', '更新', 'ongoing', 'serial'))):
        return '连载'
    if str(原始项).strip().lower() in ('0', '2'):
        return '完结'
    if str(原始项).strip().lower() in ('1', '3', '4'):
        return '连载'
    return ''

def 状态文本(书籍信息: dict[str, Any]) -> str:
    return 规范化状态(书籍信息.get('status'), '') or '连载'

def 格式化字数(值: Any) -> str:
    文本 = str(值 or '').strip().replace(' ', '')
    if not 文本:
        return ''
    if '字' in 文本:
        return 文本
    字数 = 解析字数(文本)
    if 字数 <= 0:
        return 文本
    if 字数 >= 100000000:
        return f'{round(字数 / 100000000, 1):g}亿字'
    if 字数 >= 10000:
        return f'{round(字数 / 10000, 1):g}万字'
    return f'{字数}字'

def 解析字数(值: Any) -> int:
    文本 = str(值 or '').strip().replace(' ', '')
    匹配 = re.search('([\\d.]+)', 文本)
    if not 匹配:
        return 0
    数字 = float(匹配.group(1))
    if '亿' in 文本:
        数字 *= 100000000
    elif '万' in 文本:
        数字 *= 10000
    return int(数字)

def 清理正文(文本: Any) -> str:
    文本 = str(文本 or '')
    文本 = re.sub('<br\\s*/?>', '\n', 文本, flags=re.IGNORECASE)
    文本 = re.sub('</p>', '\n', 文本, flags=re.IGNORECASE)
    文本 = 清理文本(文本).replace('\r', '')
    文本 = re.sub('\\n{3,}', '\n\n', 文本)
    return 文本.strip()

def 清理文本(文本: Any) -> str:
    文本 = re.sub('<[^>]+>', '', str(文本 or ''))
    return html.unescape(文本).strip()

def 清理书名(文本: Any) -> str:
    书名 = 清理文本(文本)
    书名 = re.sub('完整版在线免费阅读.*$', '', 书名)
    书名 = re.sub('在线免费阅读.*$', '', 书名)
    书名 = re.sub('小说[_-]?番茄小说官网.*$', '', 书名)
    书名 = re.sub('[_-].*番茄小说.*$', '', 书名)
    return 书名.strip(' _-｜|')

def 清理简介(文本: Any) -> str:
    简介 = 清理文本(解码JSON字符串片段(文本))
    简介 = 简介.replace('\\n', '\n').replace('\\/', '/')
    简介 = re.sub('^番茄小说提供.*?精彩小说尽在番茄小说网。', '', 简介)
    简介 = re.sub('[ \t]+', ' ', 简介)
    简介 = re.sub('\n{3,}', '\n\n', 简介)
    return 简介.strip()

def 解码JSON字符串片段(文本: Any) -> str:
    原文 = str(文本 or '')
    if not 原文:
        return ''
    try:
        return json.loads(f'"{原文}"')
    except Exception:
        return 原文

def 应覆盖书名(当前值: Any, 新值: Any) -> bool:
    当前书名 = 清理书名(当前值)
    新书名 = 清理书名(新值)
    if not 新书名:
        return False
    if '免费阅读' in str(当前值) or '番茄小说官网' in str(当前值):
        return True
    return (not 当前书名) or 当前书名.startswith('番茄小说')

def 清理文件名(文件名: Any) -> str:
    文件名 = re.sub('[\\\\/:*?"<>|]', '_', str(文件名 or '')).strip().rstrip('.')
    return 文件名[:80] or '番茄小说'

def 限制文本长度(值: Any, 最大长度: int=2000) -> str:
    文本 = str(值 or '')
    if len(文本) > 最大长度:
        return 文本[:最大长度] + '...'
    return 文本

def 安全整数(值: Any) -> int:
    if 值 in (None, '') or isinstance(值, bool):
        return 0
    try:
        return max(0, int(float(str(值).strip())))
    except Exception:
        匹配 = re.search('\\d+', str(值))
        return int(匹配.group(0)) if 匹配 else 0

def 读取任意字段(数据: dict[str, Any], 字段列表: tuple[str, ...]) -> Any:
    if not isinstance(数据, dict):
        return None
    for 字段名 in 字段列表:
        值 = 数据.get(字段名)
        if 值 not in (None, ''):
            return 值
    return None

def 读取路径(数据: Any, 路径: tuple[str, ...]) -> Any:
    当前值 = 数据
    for 字段名 in 路径:
        if not isinstance(当前值, dict):
            return None
        当前值 = 当前值.get(字段名)
    return 当前值

def 获取群号(事件: Any) -> str:
    for 方法名 in ('get_group_id', 'get_group'):
        方法 = getattr(事件, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)
    消息对象 = getattr(事件, 'message_obj', None)
    for 对象 in (事件, 消息对象):
        值 = 读取字段(对象, 'group_id') or 读取字段(对象, 'group')
        if isinstance(值, dict):
            值 = 值.get('group_id') or 值.get('id')
        if 值:
            return str(值)
    return ''

def 获取用户QQ(事件: Any) -> str:
    for 方法名 in ('get_sender_id', 'get_user_id'):
        方法 = getattr(事件, 方法名, None)
        if callable(方法):
            值 = 方法()
            if 值:
                return str(值)
    消息对象 = getattr(事件, 'message_obj', None)
    for 对象 in (事件, 消息对象):
        值 = 读取字段(对象, 'sender_id') or 读取字段(对象, 'user_id') or 读取字段(对象, 'sender')
        if isinstance(值, dict):
            值 = 值.get('user_id') or 值.get('id')
        if 值:
            return str(值)
    return ''

def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
