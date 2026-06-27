from __future__ import annotations

import asyncio
import html
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp
from astrbot.api import logger

import main as 主模块

析API番茄小说 = getattr(主模块, "析API番茄小说模块")
崩溃API番茄小说 = getattr(主模块, "崩溃API番茄小说模块")
用户激活功能 = getattr(主模块, "用户激活功能")
小说功能开关 = getattr(主模块, "小说功能开关")
UC网盘功能 = getattr(主模块, "UC网盘功能")
百度网盘功能 = getattr(主模块, "百度网盘功能")
自建API番茄小说 = getattr(主模块, "自建API番茄小说模块")
权限工具 = getattr(主模块, "权限工具")

from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态值, 写入运行状态值

缓存目录 = Path(__file__).resolve().parents[2] / '下载缓存'
缓存目录.mkdir(parents=True, exist_ok=True)
浏览器请求头 = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'}
番茄域名正则 = re.compile(r'fanqienovel\.com|changdunovel\.com|fqnovel\.com|novelfm\.com|qimao\.com|app-share\.wtzw\.com', re.IGNORECASE)
长读短链正则 = re.compile(r'https?://(?:www\.)?(?:changdunovel\.com/t|m\.novelfm\.com/s)/[A-Za-z0-9_-]+/?', re.IGNORECASE)
链接正则 = re.compile(r'https?://[^\s\'\"<>、，。；,;`]+', re.IGNORECASE)
免责声明 = '免责声明：本文内容来源于网络，仅作个人学习交流使用。请支持正版小说。\n\n'
API选择键 = 'fq_api_choice'
API等待状态字典: dict[str, str] = {}
Cookie输入等待状态字典: dict[str, str] = {}
官方API地址 = 'https://api-novel.snssdk.com/reading/bookapi/multi/detail/v/'
落地页API地址 = 'https://novel.snssdk.com/api/novel/channel/homepage/book/detail/v/'
页面API地址 = 'https://novel.snssdk.com/api/novel/book/directory/list/v1/'
app版本号 = '70690'
设备标识 = '123456789012345'
用户UID = '1234567890'
番茄搜索 = 'https://api5-normal-lf.fqnovel.com/reading/bookapi/search/sug/v/'
章节内容API地址 = 'https://api-novel.snssdk.com/reading/bookapi/detail/v/'
浏览器Cookie = None
浏览器Cookie到期时间 = 0
崩溃API地址 = 'http://111.170.14.45:2000'
最大并发请求数 = 30
限流等待秒数 = 0.3


def 获取番茄小说key():
    配置 = getattr(主模块, 'config', None) or {}
    key = 配置.get('番茄小说key')
    if key and str(key).strip():
        return str(key).strip()
    for 候选 in [配置.get('番茄小说Key'), 配置.get('fq_api_key'), 配置.get('oiapi_key')]:
        if 候选 and str(候选).strip():
            return str(候选).strip()
    return ''


def 读取当前API选择(配置: Any = None) -> str:
    if 配置 is None:
        配置 = getattr(主模块, 'config', None) or {}
    当前选择 = 读取运行状态值(配置, API选择键, 'api', '')
    if not 当前选择:
        旧选择 = 读取运行状态值(配置, 'fanqie_api', 'current_api', '')
        if 旧选择:
            映射 = {'OIAPI': '1', '析API': '2', '崩溃API': '3'}
            当前选择 = 映射.get(旧选择, '')
            if 当前选择:
                try:
                    写入运行状态值(配置, API选择键, 'api', 当前选择)
                except Exception:
                    pass
    if 当前选择 in ('1', '2', '3', '4'):
        return 当前选择
    return '1'


def 保存当前API选择(api选择: str, 配置: Any = None):
    if 配置 is None:
        配置 = getattr(主模块, 'config', None) or {}
    try:
        写入运行状态值(配置, API选择键, 'api', api选择)
    except Exception as 异常:
        logger.warning(f'番茄小说API选择写入失败：{异常}')


def 获取API中文名称(api选择: str) -> str:
    if api选择 == '2':
        return '析API'
    if api选择 == '3':
        return '崩溃API'
    if api选择 == '4':
        return '自建API'
    return 'OIAPI'


async def 处理番茄小说API指令(事件, 命令文本: str = '', 配置: Any = None) -> str | None:
    会话键 = 事件.group_id if hasattr(事件, 'group_id') and 事件.group_id else 'private'
    用户QQ = str(事件.get_sender_id())
    管理员标识 = f'管理:{用户QQ}:{会话键}'
    if not 权限工具.是群文件清理管理员(事件, 配置):
        return None
    消息文本 = str(命令文本 or getattr(事件, 'message_str', '') or '').strip()
    if not 消息文本:
        消息文本 = getattr(事件, 'message_str', '') or ''
        消息文本 = 消息文本.strip()
    等待状态键 = f'{管理员标识}:api'
    Cookie等待键 = f'{管理员标识}:cookie'
    if 等待状态键 in API等待状态字典 and 消息文本 in {'1', '2', '3', '4'}:
        API选择 = 消息文本
        API等待状态字典.pop(等待状态键, None)
        保存当前API选择(API选择, 配置)
        logger.info(f'番茄小说API切换为：{获取API中文名称(API选择)}')
        return f'已切换到：{获取API中文名称(API选择)}'
    if 消息文本.lower() in ('oiapi', 'oi'):
        保存当前API选择('1', 配置)
        logger.info('番茄小说API切换为：OIAPI')
        return '已切换到：OIAPI'
    if 消息文本.lower() in ('析api', 'xiapi', 'xapi', '析', 'xi'):
        保存当前API选择('2', 配置)
        logger.info('番茄小说API切换为：析API')
        return '已切换到：析API'
    if 消息文本.lower() in ('崩溃api', '崩溃', 'bengkuiapi', 'bengkui', 'crashapi', 'crash'):
        保存当前API选择('3', 配置)
        logger.info('番茄小说API切换为：崩溃API')
        return '已切换到：崩溃API'
    if 消息文本.lower() in ('自建api', '自建', 'zijianapi', 'zijian', 'selfapi', 'self'):
        保存当前API选择('4', 配置)
        logger.info('番茄小说API切换为：自建API')
        return '已切换到：自建API'
    if Cookie等待键 in Cookie输入等待状态字典 and 消息文本.startswith('析APICookie'):
        Cookie内容 = 消息文本.replace('析APICookie', '', 1).strip()
        Cookie输入等待状态字典.pop(Cookie等待键, None)
        if not Cookie内容:
            return 'Cookie不能为空'
        全局变量字典 = globals()
        全局变量字典['浏览器Cookie'] = Cookie内容
        全局变量字典['浏览器Cookie到期时间'] = time.time() + 3600 * 48
        try:
            await 析API番茄小说.测试析API(Cookie内容, 0)
        except Exception as 异常:
            logger.warning(f'析APICookie保存但测试失败：{异常}')
        return f'析APICookie已保存，当前API为：{获取API中文名称(读取当前API选择(配置))}'
    if 消息文本 == '查看API':
        API等待状态字典[等待状态键] = '1'
        return '请选择使用的API站点：\n1. OIAPI\n2. 析API\n3. 崩溃API\n4. 自建API\n\n请在120秒内发送 1、2、3 或 4，选择对应API。'
    if 消息文本 == '析APICookie':
        Cookie输入等待状态字典[Cookie等待键] = '1'
        return '请直接发送「析APICookie 你的Cookie内容」完成设置，Cookie会保存48小时。'
    return None


def 获取番茄小说回复流(事件, 消息文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取直接来源(消息文本) or 提取事件来源(事件)
    if 来源 is None:
        return None
    return 生成番茄下载回复流(事件, 来源, 配置)


async def 生成番茄下载回复流(事件, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 提取书籍编号(来源)
    解析来源 = 来源
    API选择 = 读取当前API选择(配置)
    try:
        async with aiohttp.ClientSession() as 会话:
            if not 书籍编号:
                解析来源 = await 展开番茄短链(会话, 来源)
                书籍编号 = 提取书籍编号(解析来源)
            if not 书籍编号:
                yield 事件.plain_result('没有识别到番茄小说链接')
                return
            if API选择 == '3':
                yield 事件.plain_result('当前使用崩溃API下载\n正在获取书籍信息...')
                准备结果 = await 崩溃API番茄小说.准备番茄小说(会话, 书籍编号)
            elif API选择 == '4':
                yield 事件.plain_result('当前使用自建API下载\n正在获取书籍信息...')
                准备结果 = await 自建API番茄小说.准备番茄小说(会话, 书籍编号)
            else:
                yield 事件.plain_result(f'当前使用{获取API中文名称(API选择)}下载\n正在获取书籍信息...')
                准备结果 = await 准备番茄小说(会话, 书籍编号, API选择)
            if not 准备结果.get('success'):
                yield 事件.plain_result(f'获取番茄小说书籍信息失败：{准备结果.get("error") or "未知错误"}')
                return
            书籍信息 = 准备结果['book_info']
            章节目录 = 准备结果['chapters']
            信息回复 = [
                f"书名：{书籍信息['title']}",
                f"作者：{书籍信息['author']}",
                f"状态：{书籍信息['status'] or '未知'}",
                f"章节：{书籍信息['chapter_count'] or len(章节目录)}章",
                f"字数：{书籍信息['word_count'] or '未知'}"
            ]
            信息回复.append('正在下载中请稍等.....')
            yield 事件.plain_result('\n'.join(信息回复))
            logger.info(f"番茄小说开始下载：{书籍信息['title']}，共{书籍信息['chapter_count']}章，API={获取API中文名称(API选择)}")
            if API选择 == '3':
                章节结果 = await 崩溃API番茄小说.下载全部章节(会话, 书籍编号)
            elif API选择 == '4':
                章节结果 = await 自建API番茄小说.下载全部章节(会话, 书籍编号, 章节目录)
            else:
                章节结果 = await 下载全部章节(会话, 书籍编号, 章节目录, API选择)
            内容列表 = ['\n'.join((免责声明, f"书名：{书籍信息['title']}", f"作者：{书籍信息['author']}", f"状态：{书籍信息['status']}", f"字数：{书籍信息['word_count']}", f"章节：{书籍信息['chapter_count']}章"))]
            简介文本 = 书籍信息.get('intro')
            if 简介文本:
                内容列表.append(f"\n\n作品简介：\n{简介文本}\n\n")
            成功数 = 0
            失败数 = 0
            for 章节 in 章节结果:
                if 章节.get('success'):
                    成功数 += 1
                    内容列表.append(f"\n\n第{章节['index']}章 {章节['title']}\n\n")
                    内容列表.append(章节['content'])
                else:
                    失败数 += 1
            文件内容 = ''.join(内容列表)
            状态标识 = '[完结]' if 书籍信息['status'] == '完结' else '[连载]'
            文件名 = f"{状态标识}书名：{书籍信息['title']} 作者：{书籍信息['author']}.txt"
            缓存文件 = 缓存目录 / 文件名
            缓存文件.write_text(文件内容, encoding='utf-8', newline='')
            logger.info(f'番茄小说章节下载完成汇总：title={书籍信息["title"]}, total={len(章节结果)}, success={成功数}, failed={失败数}, api={获取API中文名称(API选择)}')
            UC结果 = await UC网盘功能.上传到UC网盘(事件, 缓存文件, 文件名)
            if UC结果:
                yield 事件.plain_result(UC结果[0])
                if len(UC结果) > 1 and UC结果[1] is not None:
                    yield UC结果[1]
                    百度网盘功能.后台上传到百度网盘(str(缓存文件), 文件名, 书籍信息['status'] == '完结')
            else:
                发送文件 = getattr(事件, 'file', None)
                if 发送文件:
                    yield 事件.file(name=文件名, file=str(缓存文件))
                    logger.info(f'番茄小说文件发送完成：文件名={文件名}, 发送方式=AstrBot File组件, API={获取API中文名称(API选择)}')
                    await asyncio.sleep(15)
                else:
                    import astrbot.api.message_components as 消息组件
                    路径文本 = str(缓存文件.resolve())
                    yield 事件.chain_result([消息组件.Plain('下载完成，正在尝试发送文件...\n'), 消息组件.File(path=路径文本, file=缓存文件.name)])
                    logger.info(f'番茄小说文件发送完成：文件名={文件名}, 发送方式=OneBot路径上传, API={获取API中文名称(API选择)}')
                    await asyncio.sleep(2)
                try:
                    os.remove(str(缓存文件))
                    logger.info(f'番茄小说缓存文件删除成功：文件名={文件名}')
                except Exception as 异常:
                    logger.warning(f'番茄小说缓存文件删除失败：文件名={文件名}, error={异常}')
                百度网盘功能.后台上传到百度网盘(str(缓存文件), 文件名, 书籍信息['status'] == '完结')
    except Exception as 异常:
        logger.error(f'番茄小说下载失败：{书籍编号}，API={获取API中文名称(API选择)}', exc_info=异常)
        yield 事件.plain_result(f'获取番茄小说内容失败：{异常}')


async def 展开番茄短链(会话: aiohttp.ClientSession, 来源: str) -> str:
    if not 长读短链正则.search(str(来源 or '')):
        return str(来源 or '')
    短链匹配 = 长读短链正则.search(str(来源 or ''))
    if not 短链匹配:
        return str(来源 or '')
    短链地址 = 短链匹配.group(0)
    for 地址 in [短链地址]:
        try:
            async with 会话.get(地址, headers=浏览器请求头, allow_redirects=True, timeout=20) as 响应:
                最终地址 = str(响应.url)
                logger.debug(f'番茄小说短链已展开：source={来源}, target={最终地址}')
                if 'book_id=' in 最终地址:
                    return 最终地址
                页面文本 = await 响应.text(errors='ignore')
                if re.search(r'book_id["\s:=]+(\d{15,25})', 页面文本):
                    logger.debug(f'番茄小说短链页面包含书籍ID：source={来源}')
                    替换结果 = re.sub(r'(https?://[^\s\'\"<>、，。；,;`]*)', 最终地址, str(来源 or ''), count=1)
                    return 替换结果
        except Exception as 异常:
            logger.debug(f'番茄小说短链展开失败：source={限制文本长度(来源)}, error={异常}')
    return str(来源 or '')


def 提取书籍编号(文本: str) -> str:
    for 候选路径 in 生成文本变体(str(文本 or '')):
        候选路径 = 候选路径.strip()
        if re.fullmatch(r'\d{15,25}', 候选路径):
            return 候选路径
        规则列表 = (
            r'(?:book_id|bookid|bookId)=(\d{15,25})',
            r'fanqienovel\.com/(?:page|reader)?/?(\d{15,25})',
            r'fanqienovel\.com/[^\s?&#]*/(\d{15,25})',
            r'changdunovel\.com/reader/(\d{15,25})',
            r'changdunovel\.com/reader/[^/\s?&#]+/(\d{15,25})',
            r'(?:changdunovel\.com|fqnovel\.com|novelfm\.com).*?(?:book_id|bookid|bookId)=(\d{15,25})',
        )
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


def 提取直接来源(文本: str) -> str | None:
    原始文本 = str(文本 or '')
    for 变体 in 生成文本变体(原始文本):
        for 匹配 in 链接正则.finditer(变体):
            链接 = 匹配.group(0).rstrip('),.;]`')
            if 长读短链正则.search(链接):
                return 链接
            if 番茄域名正则.search(链接) and 提取书籍编号(链接):
                return 链接
        短链匹配 = 长读短链正则.search(变体)
        if 短链匹配:
            return 短链匹配.group(0)
        if 提取书籍编号(变体):
            if 番茄域名正则.search(变体) or re.search(r'book_id=', 变体, re.IGNORECASE):
                return 变体
        if re.fullmatch(r'\d{15,25}', 变体.strip()):
            return 变体.strip()
        if re.search(r'book_id=(\d{15,25})', 变体, re.IGNORECASE):
            return 变体
    return None


def 提取事件来源(事件: Any) -> str | None:
    for 值来源 in (getattr(事件, 'message', None), getattr(事件, 'components', None), getattr(事件, 'content', None)):
        if 值来源 is None:
            continue
        if isinstance(值来源, (list, tuple)):
            for 项目 in 值来源:
                来源 = 提取番茄来源(项目)
                if 来源:
                    return 来源
        elif isinstance(值来源, dict):
            for 项目 in 值来源.values():
                来源 = 提取番茄来源(项目)
                if 来源:
                    return 来源
        else:
            来源 = 提取番茄来源(值来源)
            if 来源:
                return 来源
    原始消息 = getattr(事件, 'raw_message', '')
    if 原始消息:
        来源 = 提取直接来源(str(原始消息))
        if 来源:
            return 来源
    return None


def 提取番茄来源(值: Any) -> str:
    if 值 is None:
        return ''
    if isinstance(值, str):
        return 提取直接来源(值) or ''
    if isinstance(值, dict):
        for 键 in ('url', 'link', 'href', 'data', 'text'):
            if 键 in 值:
                来源 = 提取番茄来源(值[键])
                if 来源:
                    return 来源
        if 值.get('type') in ('image', 'video', 'record', 'face', 'reply'):
            return ''
        for 项目 in 值.values():
            来源 = 提取番茄来源(项目)
            if 来源:
                return 来源
    if isinstance(值, (list, tuple)):
        for 项目 in 值:
            来源 = 提取番茄来源(项目)
            if 来源:
                return 来源
    return ''


async def 准备番茄小说(会话: aiohttp.ClientSession, 书籍编号: str, API选择: str) -> dict[str, Any]:
    if not 书籍编号:
        return {"success": False, "error": "没有获取到书籍ID"}
    OIAPIKey = 获取番茄小说key()
    if not OIAPIKey and API选择 == '1':
        return {"success": False, "error": "番茄小说key为空，请先配置后再试。"}
    书籍信息, 目录结果 = await asyncio.gather(获取书籍信息(会话, 书籍编号, OIAPIKey), 获取章节目录(会话, 书籍编号, OIAPIKey, API选择, 书籍信息))
    if not 书籍信息.get("success") and not 目录结果.get("chapters"):
        return {"success": False, "error": 书籍信息.get("error") or 目录结果.get("error") or "获取书籍信息失败"}
    书籍信息 = 书籍信息 if 书籍信息.get("success") else {"book_info": 默认书籍信息(书籍编号)}
    章节列表 = 目录结果.get("chapters")
    if not 章节列表:
        return {"success": False, "error": "没有获取到章节目录"}
    书籍数据 = 合并书籍信息(书籍信息.get("book_info", {}), 目录结果.get("book_info", {}))
    if not 书籍数据.get("chapter_count"):
        书籍数据 = 合并书籍信息(书籍数据, {"chapter_count": len(章节列表)})
    logger.info(f"番茄小说准备完成：book_id={书籍编号}, title={书籍数据.get('title')}, chapters={len(章节列表)}, api={获取API中文名称(API选择)}")
    return {"success": True, "book_id": 书籍编号, "book_info": 书籍数据, "chapters": 章节列表}


async def 获取书籍信息(会话: aiohttp.ClientSession, 书籍编号: str, APIKey: str) -> dict[str, Any]:
    任务列表 = [获取官方书籍信息(会话, 书籍编号), 获取落地页书籍信息(会话, 书籍编号)]
    if APIKey:
        任务列表.append(获取OIAPI书籍信息(会话, 书籍编号, APIKey))
    结果列表 = await asyncio.gather(*任务列表, return_exceptions=True)
    书籍数据 = 默认书籍信息(书籍编号)
    for 结果 in 结果列表:
        if isinstance(结果, Exception) or not 结果:
            continue
        书籍数据 = 合并书籍信息(书籍数据, 结果)
    if 书籍数据.get("title") == f"番茄小说{书籍编号}":
        任务列表 = [获取网页书籍信息(会话, f"https://fanqienovel.com/page/{书籍编号}"), 获取网页书籍信息(会话, f"https://fanqienovel.com/reader/{书籍编号}")]
        结果列表 = await asyncio.gather(*任务列表, return_exceptions=True)
        for 结果 in 结果列表:
            if isinstance(结果, Exception) or not 结果:
                continue
            书籍数据 = 合并书籍信息(书籍数据, 结果)
    if 书籍数据.get("title") == f"番茄小说{书籍编号}":
        return {"success": False, "error": "获取书籍信息失败", "book_info": 书籍数据}
    return {"success": True, "book_info": 书籍数据}


async def 获取OIAPI书籍信息(会话: aiohttp.ClientSession, 书籍编号: str, APIKey: str) -> dict[str, Any]:
    try:
        响应 = await 会话.get('https://oiapi.net/api/FqRead', params={"key": APIKey, "type": "json", "book_id": 书籍编号, "method": "detail"}, timeout=20)
        响应文本 = await 响应.text()
        if 响应.status != 200:
            return {}
        try:
            数据 = json.loads(响应文本)
        except Exception:
            return {}
        if 数据.get('code') != 200:
            return {}
        书籍数据 = 数据.get('data') or {}
        return 从字典提取书籍信息(书籍数据)
    except Exception as 异常:
        logger.debug(f'番茄小说OIAPI详情失败：{书籍编号}，{异常}')
        return {}


async def 获取官方书籍信息(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    try:
        响应 = await 会话.post(官方API地址, params={"aid": "1967", "version_code": app版本号}, data={"book_ids": f'[{书籍编号}]'}, headers={"Content-Type": "application/json", "User-Agent": 浏览器请求头["User-Agent"]}, timeout=20)
        响应文本 = await 响应.text()
        if 响应.status != 200:
            return {}
        try:
            数据 = json.loads(响应文本)
        except Exception:
            return {}
        if 数据.get('code') != 0:
            return {}
        书籍列表 = 数据.get('data') or []
        if not 书籍列表:
            return {}
        return 从字典提取书籍信息(书籍列表[0] if isinstance(书籍列表, list) else 书籍列表)
    except Exception as 异常:
        logger.debug(f'番茄小说官方API详情失败：{书籍编号}，{异常}')
        return {}


async def 获取落地页书籍信息(会话: aiohttp.ClientSession, 书籍编号: str) -> dict[str, Any]:
    try:
        响应 = await 会话.get(落地页API地址, params={"book_id": 书籍编号, "aid": "1967", "version_code": app版本号}, headers=浏览器请求头, timeout=20)
        响应文本 = await 响应.text()
        if 响应.status != 200:
            return {}
        try:
            数据 = json.loads(响应文本)
        except Exception:
            return {}
        if 数据.get('code') != 0:
            return {}
        return 从字典提取书籍信息(数据.get('data') or {})
    except Exception as 异常:
        logger.debug(f'番茄小说落地页详情失败：{书籍编号}，{异常}')
        return {}


async def 获取网页书籍信息(会话: aiohttp.ClientSession, 页面地址: str) -> dict[str, Any]:
    try:
        async with 会话.get(页面地址, headers=浏览器请求头, timeout=20) as 响应:
            if 响应.status != 200:
                return {}
            页面文本 = await 响应.text(errors='ignore')
    except Exception as 异常:
        logger.debug(f'番茄小说页面详情失败：{页面地址}，{异常}')
        return {}
    脚本匹配 = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', 页面文本)
    初始数据 = {}
    if 脚本匹配:
        try:
            数据 = json.loads(html.unescape(脚本匹配.group(1)))
            页面数据 = 数据.get('props', {}).get('pageProps', {}) or {}
            if 'bookInfo' in 页面数据:
                初始数据 = 从字典提取书籍信息(页面数据['bookInfo'])
            elif 'bookData' in 页面数据:
                初始数据 = 从字典提取书籍信息(页面数据['bookData'])
        except Exception:
            pass
    if 初始数据:
        return 初始数据
    字段提取: dict[str, str] = {}
    for 字段名, 字段标签 in [('title', 'bookName'), ('author', 'author'), ('status', 'creationStatus'), ('word_count', 'wordNumber'), ('intro', 'abstract')]:
        匹配 = re.search(rf'"{字段标签}"\s*:\s*"([^"]+)"', 页面文本)
        if 匹配:
            字段提取[字段名] = html.unescape(匹配.group(1))
    return 字段提取


async def 获取章节目录(会话: aiohttp.ClientSession, 书籍编号: str, APIKey: str, API选择: str, 书籍信息: dict[str, Any]) -> dict[str, Any]:
    错误信息 = ''
    try:
        async with 会话.get(页面API地址, params={"book_id": 书籍编号, "device_id": 设备标识, "iid": 用户UID, "aid": "1967", "version_code": app版本号, "update_version": app版本号}, headers=浏览器请求头, timeout=20) as 响应:
            if 响应.status == 200:
                try:
                    目录数据 = await 响应.json(content_type=None)
                    if isinstance(目录数据, dict) and 目录数据.get('code') == 0:
                        数据对象 = 目录数据.get('data') or {}
                        章节列表 = 提取章节目录(数据对象)
                        if 章节列表:
                            书籍数据 = 从字典提取书籍信息(数据对象)
                            return {"success": True, "chapters": 章节列表, "book_info": 书籍数据}
                except Exception:
                    pass
    except Exception as 异常:
        错误信息 = f'页面目录失败：{异常}'
    if API选择 == '2':
        try:
            析API结果 = await 析API番茄小说.获取析API目录(会话, 书籍编号)
            if 析API结果.get('success'):
                return 析API结果
            if not 错误信息:
                错误信息 = 析API结果.get('error', '析API目录失败')
        except Exception as 异常:
            if not 错误信息:
                错误信息 = f'析API目录失败：{异常}'
    if APIKey:
        try:
            OIAPI结果 = await 获取OIAPI章节目录(会话, 书籍编号, APIKey)
            if OIAPI结果.get('success'):
                return OIAPI结果
            if not 错误信息:
                错误信息 = OIAPI结果.get('error', 'OIAPI目录失败')
        except Exception as 异常:
            if not 错误信息:
                错误信息 = f'OIAPI目录失败：{异常}'
    章节ID匹配 = await 获取网页章节目录(会话, f'https://fanqienovel.com/page/{书籍编号}')
    if 章节ID匹配.get('chapters'):
        return 章节ID匹配
    章节ID匹配 = await 获取网页章节目录(会话, f'https://fanqienovel.com/reader/{书籍编号}')
    if 章节ID匹配.get('chapters'):
        return 章节ID匹配
    return {"success": False, "error": 错误信息 or '获取章节目录失败', "chapters": []}


async def 获取OIAPI章节目录(会话: aiohttp.ClientSession, 书籍编号: str, APIKey: str) -> dict[str, Any]:
    async with 会话.get('https://oiapi.net/api/FqRead', params={"key": APIKey, "type": "json", "book_id": 书籍编号, "method": "chapters"}, timeout=30) as 响应:
        响应文本 = await 响应.text()
        if 响应.status != 200:
            return {"success": False, "error": f"HTTP {响应.status}", "chapters": []}
        try:
            数据 = json.loads(响应文本)
        except Exception:
            return {"success": False, "error": "OIAPI返回非JSON", "chapters": []}
        if 数据.get('code') != 200:
            return {"success": False, "error": str(数据.get('message') or 'OIAPI目录失败'), "chapters": []}
        章节列表 = 数据.get('data') or []
        if not isinstance(章节列表, list):
            return {"success": False, "error": "OIAPI章节格式错误", "chapters": []}
        结果列表: list[dict[str, Any]] = []
        for 索引, 章节项 in enumerate(章节列表, start=1):
            章节ID = str(章节项.get('item_id') or 章节项.get('chapter_id') or 索引)
            标题 = 清理文本(章节项.get('title') or 章节项.get('name') or f'第{索引}章')
            结果列表.append({"id": 章节ID, "title": 标题, "index": 索引})
        return {"success": True, "chapters": 结果列表, "book_info": {}}


async def 获取网页章节目录(会话: aiohttp.ClientSession, 页面地址: str) -> dict[str, Any]:
    try:
        async with 会话.get(页面地址, headers=浏览器请求头, timeout=20) as 响应:
            if 响应.status != 200:
                return {"chapters": []}
            页面文本 = await 响应.text(errors='ignore')
    except Exception:
        return {"chapters": []}
    脚本匹配 = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', 页面文本)
    if 脚本匹配:
        try:
            数据 = json.loads(html.unescape(脚本匹配.group(1)))
            页面数据 = 数据.get('props', {}).get('pageProps', {})
            for 关键路径 in [('pageData', 'catalog', 'itemList'), ('pageData', 'catalog', 'chapterList'), ('bookData', 'chapterList'), ('chapterList',)]:
                章节容器 = 页面数据
                for 键名 in 关键路径:
                    if isinstance(章节容器, dict):
                        章节容器 = 章节容器.get(键名)
                    else:
                        章节容器 = None
                        break
                if isinstance(章节容器, list) and 章节容器:
                    结果列表: list[dict[str, Any]] = []
                    for 索引, 章节项 in enumerate(章节容器, start=1):
                        if not isinstance(章节项, dict):
                            continue
                        章节ID = str(章节项.get('itemId') or 章节项.get('item_id') or 章节项.get('chapterId') or 章节项.get('chapter_id') or 索引)
                        标题 = 清理文本(章节项.get('title') or 章节项.get('name') or f'第{索引}章')
                        序号 = int(章节项.get('realChapterOrder') or 章节项.get('order') or 索引)
                        结果列表.append({"id": 章节ID, "title": 标题, "index": 序号})
                    if 结果列表:
                        return {"chapters": sorted(结果列表, key=lambda x: x['index'])}
        except Exception:
            pass
    all_ids匹配 = re.findall(r'"allItemIds"\s*:\s*\[([^\]]+)\]', 页面文本)
    if all_ids匹配:
        ID列表 = [x.strip().strip('"') for x in all_ids匹配[-1].split(',') if x.strip().strip('"').isdigit()]
        if ID列表:
            return {"chapters": [{"id": str(章节ID), "title": f"第{索引}章", "index": 索引} for 索引, 章节ID in enumerate(ID列表, start=1)]}
    return {"chapters": []}


def 提取章节目录(数据: Any) -> list[dict[str, Any]]:
    结果列表: list[dict[str, Any]] = []
    if not isinstance(数据, dict):
        return 结果列表
    if 数据.get('allItemIds'):
        all_ids = 数据.get('allItemIds')
        if isinstance(all_ids, str):
            all_ids = [x.strip().strip('"') for x in all_ids.split(',')]
        if isinstance(all_ids, list) and all_ids:
            for 位置, 章节ID in enumerate(all_ids, start=1):
                结果列表.append({"id": str(章节ID), "title": f"第{位置}章", "index": 位置})
    for 键名 in ['chapterList', 'itemList', 'catalogList']:
        if isinstance(数据.get(键名), list):
            for 索引, 章节项 in enumerate(数据[键名], start=1):
                if not isinstance(章节项, dict):
                    continue
                章节ID = str(章节项.get('itemId') or 章节项.get('item_id') or 章节项.get('chapterId') or 章节项.get('chapter_id') or 索引)
                标题 = 清理文本(章节项.get('title') or 章节项.get('name') or f'第{索引}章')
                序号 = int(章节项.get('realChapterOrder') or 章节项.get('order') or 索引)
                结果列表.append({"id": 章节ID, "title": 标题, "index": 序号})
            break
    if isinstance(数据.get('catalog'), dict) and isinstance(数据['catalog'].get('itemList'), list):
        for 索引, 章节项 in enumerate(数据['catalog']['itemList'], start=1):
            if not isinstance(章节项, dict):
                continue
            章节ID = str(章节项.get('itemId') or 章节项.get('item_id') or 章节项.get('chapterId') or 章节项.get('chapter_id') or 索引)
            标题 = 清理文本(章节项.get('title') or 章节项.get('name') or f'第{索引}章')
            序号 = int(章节项.get('realChapterOrder') or 章节项.get('order') or 索引)
            结果列表.append({"id": 章节ID, "title": 标题, "index": 序号})
    return sorted(结果列表, key=lambda x: x['index'])


def 从字典提取书籍信息(数据: dict[str, Any]) -> dict[str, Any]:
    return {
        'title': 清理书名(数据.get('book_name') or 数据.get('bookName') or 数据.get('title') or 数据.get('name') or ''),
        'author': 清理文本(数据.get('author') or 数据.get('author_name') or data_get('author', 'name') or ''),
        'word_count': 格式化字数(数据.get('word_count') or 数据.get('wordCount') or 数据.get('word_number') or 数据.get('total_word_count') or 数据.get('totalWords') or ''),
        'status': 规范化状态(数据.get('creation_status') or 数据.get('creationStatus') or 数据.get('status') or 数据.get('book_status') or ''),
        'chapter_count': int(数据.get('chapter_count') or 数据.get('chapterCount') or 数据.get('chapter_num') or 数据.get('chapterNum') or 数据.get('serial_count') or 数据.get('latest_chapter_index') or 0) or 0,
        'intro': 清理简介(数据.get('abstract') or 数据.get('description') or 数据.get('summary') or 数据.get('book_abstract') or 数据.get('intro') or ''),
    }


def data_get(数据: Any, *键列表: str) -> Any:
    当前值 = 数据
    for 键 in 键列表:
        if not isinstance(当前值, dict) or 键 not in 当前值:
            return ''
        当前值 = 当前值[键]
    return 当前值 if 当前值 is not None else ''


def 默认书籍信息(书籍编号: str) -> dict[str, Any]:
    return {"book_id": 书籍编号, "title": f"番茄小说{书籍编号}", "author": "未知", "status": "未知", "word_count": "未知", "chapter_count": 0, "intro": ""}


def 合并书籍信息(基础信息: dict[str, Any], 新增信息: dict[str, Any]) -> dict[str, Any]:
    结果 = dict(基础信息 or {})
    for 键, 值 in (新增信息 or {}).items():
        if 键 == "title":
            值 = 清理书名(值)
        elif 键 == "intro":
            值 = 清理简介(值)
        if 值 in (None, "", 0):
            continue
        当前值 = 结果.get(键)
        if 当前值 in (None, "", 0, "未知") or (键 == "title" and str(当前值).startswith("番茄小说")):
            结果[键] = 值
    return 结果


def 规范化状态(原始值: Any) -> str:
    文本 = str(原始值 or '').strip().lower()
    if any(关键词 in 文本 for 关键词 in ("完结", "已完结", "completed", "finish", "finished")):
        return "完结"
    if any(关键词 in 文本 for 关键词 in ("连载", "ongoing", "serial")):
        return "连载"
    if str(原始值).strip() in ("0", "2"):
        return "完结"
    if str(原始值).strip() in ("1", "3", "4"):
        return "连载"
    return ""


def 格式化字数(值: Any) -> str:
    文本 = str(值 or "").strip().replace(" ", "")
    if not 文本:
        return ""
    if re.search("[万亿千百]", 文本):
        return 文本
    try:
        数值 = int(float(文本))
    except Exception:
        return 文本
    if 数值 >= 10000:
        return f"{数值 / 10000:.1f}万字".replace(".0万", "万")
    return f"{数值}字" if 数值 else ""


async def 下载全部章节(会话: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]], API选择: str) -> list[dict[str, Any]]:
    非本地 = globals()
    信号量 = asyncio.Semaphore(最大并发请求数)
    结果列表: list[dict] = [None] * len(目录)
    总数 = len(目录)
    已完成 = 0
    进度分段数 = 10
    上一进度段 = 0
    logger.debug(f'番茄小说章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%')

    async def 下载单个章节(索引: int, 章节项: dict[str, Any]):
        nonlocal 已完成, 上一进度段
        async with 信号量:
            for 重试次数 in range(3):
                try:
                    if API选择 == '2':
                        正文结果 = await 析API番茄小说.获取析API章节(会话, 书籍编号, str(章节项['id']))
                    else:
                        正文结果 = await 获取OIAPI单个章节(会话, 书籍编号, str(章节项['id']), 获取番茄小说key())
                    if not 正文结果:
                        raise RuntimeError("正文为空")
                    结果列表[索引] = {"id": 章节项['id'], "title": 章节项.get('title') or 正文结果.get('title') or f"第{章节项['index']}章", "index": 章节项['index'], "content": 清理正文(正文结果.get('content') or ''), "success": True}
                    async with asyncio.Lock():
                        已完成 += 1
                        进度段 = 进度分段数 if 已完成 >= 总数 else int(已完成 * 进度分段数 / 总数)
                        if 进度段 > 上一进度段 or 已完成 >= 总数:
                            上一进度段 = 进度段
                            百分比 = int(已完成 * 100 / 总数) if 总数 else 100
                            logger.debug(f'番茄小说章节进度：book_id={书籍编号}, progress={已完成}/{总数}, percent={百分比}%')
                    await asyncio.sleep(限流等待秒数)
                    return
                except Exception as 异常:
                    if 重试次数 >= 2:
                        logger.warning(f"番茄小说章节下载失败：book_id={书籍编号}, chapter_id={章节项['id']}, title={章节项.get('title')}, error={异常}")
                        结果列表[索引] = {"id": 章节项['id'], "title": 章节项.get('title') or f"第{章节项['index']}章", "index": 章节项['index'], "content": "【下载失败】", "success": False}
                    else:
                        await asyncio.sleep(1)

    任务列表 = [下载单个章节(索引, 章节项) for 索引, 章节项 in enumerate(目录)]
    await asyncio.gather(*任务列表)
    return 结果列表


async def 获取OIAPI单个章节(会话: aiohttp.ClientSession, 书籍编号: str, 章节ID: str, APIKey: str) -> dict[str, Any]:
    async with 会话.get('https://oiapi.net/api/FqRead', params={"key": APIKey, "type": "json", "book_id": 书籍编号, "item_id": 章节ID, "method": "chapter"}, timeout=20) as 响应:
        响应文本 = await 响应.text()
        if 响应.status != 200:
            raise RuntimeError(f"HTTP {响应.status}")
        try:
            数据 = json.loads(响应文本)
        except Exception:
            raise RuntimeError("响应不是JSON")
        if 数据.get('code') != 200:
            raise RuntimeError(str(数据.get('message') or '接口返回失败'))
        章节数据 = 数据.get('data') or {}
        return {"title": 章节数据.get('title') or '', "content": 章节数据.get('content') or ''}


async def 获取官方单个章节(会话: aiohttp.ClientSession, 书籍编号: str, 章节ID: str) -> dict[str, Any]:
    try:
        async with 会话.get(章节内容API地址, params={"item_id": 章节ID, "book_id": 书籍编号, "aid": "1967", "device_id": 设备标识, "iid": 用户UID, "version_code": app版本号}, headers=浏览器请求头, timeout=20) as 响应:
            if 响应.status != 200:
                raise RuntimeError(f"HTTP {响应.status}")
            数据 = await 响应.json(content_type=None)
            if 数据.get('code') != 0:
                raise RuntimeError(str(数据.get('message') or '官方API失败'))
            章节数据 = (数据.get('data') or {}).get('chapter') or {}
            return {"title": 章节数据.get('title') or '', "content": 章节数据.get('content') or ''}
    except Exception:
        return {}


async def 获取网页单个章节(会话: aiohttp.ClientSession, 页面地址: str) -> dict[str, Any]:
    try:
        async with 会话.get(页面地址, headers=浏览器请求头, timeout=20) as 响应:
            if 响应.status != 200:
                return {}
            页面文本 = await 响应.text(errors='ignore')
    except Exception:
        return {}
    脚本匹配 = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', 页面文本)
    if not 脚本匹配:
        return {}
    try:
        数据 = json.loads(html.unescape(脚本匹配.group(1)))
        页面数据 = 数据.get('props', {}).get('pageProps', {})
        章节内容 = 页面数据.get('chapterData') or 页面数据.get('content') or 页面数据.get('chapterContent') or ''
        章节标题 = 页面数据.get('title') or ''
        if 章节内容:
            return {"title": 章节标题, "content": 章节内容}
    except Exception:
        pass
    return {}


def 清理正文(文本: Any) -> str:
    文本 = str(文本 or "").replace("\\n", "\n").replace("\\/", "/")
    文本 = re.sub(r"<br\s*/?>", "\n", 文本, flags=re.IGNORECASE)
    文本 = re.sub(r"</p>", "\n", 文本, flags=re.IGNORECASE)
    文本 = 清理文本(文本).replace("\r", "")
    文本 = re.sub(r"\n{3,}", "\n\n", 文本)
    return 文本.strip()


def 清理文本(文本: Any) -> str:
    文本 = re.sub(r"<[^>]+>", "", str(文本 or ""))
    return html.unescape(文本).strip()


def 清理书名(文本: Any) -> str:
    书名 = 清理文本(文本)
    书名 = re.sub(r"完整版在线免费阅读.*$", "", 书名)
    书名 = re.sub(r"在线免费阅读.*$", "", 书名)
    书名 = re.sub(r"小说[_-]?番茄小说官网.*$", "", 书名)
    书名 = re.sub(r"[_-].*番茄小说.*$", "", 书名)
    return 书名.strip(" _-｜|")


def 清理简介(文本: Any) -> str:
    简介 = 清理文本(文本)
    简介 = 简介.replace("\\n", "\n").replace("\\/", "/")
    简介 = re.sub(r"^番茄小说提供.*?精彩小说尽在番茄小说网。", "", 简介)
    简介 = re.sub(r"[ \t]+", " ", 简介)
    简介 = re.sub(r"\n{3,}", "\n\n", 简介)
    return 简介.strip()


def 限制文本长度(值: Any, 最大长度: int = 2000) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."
