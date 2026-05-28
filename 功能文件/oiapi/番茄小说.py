from __future__ import annotations

import html
import asyncio
import json
import math
import re
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp
from astrbot.api import logger

try:
    from astrbot.api import message_components as Comp
except Exception:
    Comp = None


API_URL = "https://oiapi.net/api/FqRead"
LANDING_URL = "https://api.fqnovel.com/novel_ug/share/landing_page"
CACHE_DIR = Path(__file__).resolve().parents[1] / "\u4e0b\u8f7d\u7f13\u5b58"
DISCLAIMER = "\u58f0\u660e\uff1a\u672c\u6587\u4ef6\u7531\u673a\u5668\u4eba\u81ea\u52a8\u6574\u7406\u751f\u6210\uff0c\u4ec5\u4f9b\u4e2a\u4eba\u5b66\u4e60\u4ea4\u6d41\u548c\u4e34\u65f6\u9605\u8bfb\u4f7f\u7528\u3002\u5185\u5bb9\u7248\u6743\u5f52\u539f\u4f5c\u8005\u53ca\u76f8\u5173\u5e73\u53f0\u6240\u6709\uff0c\u8bf7\u52ff\u7528\u4e8e\u5546\u4e1a\u7528\u9014\u6216\u4e8c\u6b21\u4f20\u64ad\u3002\u5982\u559c\u6b22\u672c\u4e66\uff0c\u8bf7\u652f\u6301\u6b63\u7248\u3002"
MAX_WORDS_PER_RANGE = 5_000_000
PROGRESS_STEPS = 10
FILE_COMPONENT_CACHE_DELETE_DELAY = 600
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fanqienovel.com/",
}
DOMAIN_RE = re.compile(r"fanqienovel\.com|changdunovel\.com|fqnovel\.com|novelfm\.com", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s'\"<>\u3001\uff0c\u3002]+", re.IGNORECASE)


def get_fanqie_reply_stream(event: Any, command_text: str, config: Any) -> AsyncIterator[str] | None:
    source = extract_direct_source(command_text) or extract_event_source(event)
    if source is None:
        return None
    return generate_download_stream(event, source, config)


async def generate_download_stream(event: Any, source: str, config: Any) -> AsyncIterator[str]:
    api_key = get_fanqie_key(config)
    if not api_key:
        yield "\u756a\u8304\u5c0f\u8bf4\u4e0b\u8f7d\u5931\u8d25\uff1a\u7f3a\u5c11\u63d2\u4ef6\u914d\u7f6e \u756a\u8304\u5c0f\u8bf4key"
        return

    book_id = extract_book_id(source)
    if not book_id:
        yield "\u6ca1\u6709\u8bc6\u522b\u5230\u756a\u8304\u5c0f\u8bf4\u94fe\u63a5"
        return

    chapters: list[dict[str, Any]] = []
    chapter_results: list[dict[str, Any]] = []
    ok_chapters: list[dict[str, Any]] = []
    file_name = ""
    meta: dict[str, Any] = {}
    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=90)
        async with aiohttp.ClientSession(timeout=timeout, headers=BROWSER_HEADERS) as session:
            meta = await fetch_book_meta(session, book_id, source)
            chapters = await fetch_catalog(session, book_id, api_key)
            if not chapters:
                chapters = build_index_catalog(safe_int(meta.get("chapter_count")))
            if not chapters:
                yield "\u756a\u8304\u5c0f\u8bf4\u4e0b\u8f7d\u5931\u8d25\uff1a\u6ca1\u6709\u83b7\u53d6\u5230\u7ae0\u8282\u76ee\u5f55"
                return

            meta = merge_meta(meta, {"chapter_count": len(chapters)})
            logger.info(
                f"\u756a\u8304\u5c0f\u8bf4\u5f00\u59cb\u4e0b\u8f7d\uff1abook_id={book_id}, "
                f"title={meta.get('title')}, author={meta.get('author')}, chapters={len(chapters)}"
            )
            yield format_download_notice(meta, len(chapters))

            chapter_results = await download_all_chapters(session, book_id, chapters, api_key, parse_word_count(meta.get("word_count")))
            ok_chapters = [item for item in chapter_results if item.get("success")]
            if not ok_chapters:
                yield "\u756a\u8304\u5c0f\u8bf4\u4e0b\u8f7d\u5931\u8d25\uff1a\u6ca1\u6709\u83b7\u53d6\u5230\u53ef\u7528\u7ae0\u8282\u6b63\u6587"
                return

            file_name, file_content = build_txt_file(book_id, meta, chapters, chapter_results)
            logger.info(
                f"\u756a\u8304\u5c0f\u8bf4\u7ae0\u8282\u4e0b\u8f7d\u5b8c\u6210\uff1abook_id={book_id}, "
                f"title={meta.get('title')}, success={len(ok_chapters)}, total={len(chapters)}, file_size={len(file_content)}"
            )
            send_result = await prepare_text_file_send(event, file_name, file_content)
            cache_path = send_result.get("cache_path")
            chain_result = send_result.get("chain_result")
            if chain_result is not None:
                try:
                    yield chain_result
                finally:
                    schedule_delete_cache_file(cache_path)
                return
            sent = bool(send_result.get("sent"))
            send_error = str(send_result.get("error") or "")
    except Exception as exc:
        logger.warning(f"\u756a\u8304\u5c0f\u8bf4\u4e0b\u8f7d\u5931\u8d25\uff1asource={limit_text(source)}, book_id={book_id}, error={exc}")
        yield f"\u756a\u8304\u5c0f\u8bf4\u4e0b\u8f7d\u5931\u8d25\uff1a{exc}"
        return

    if sent:
        return

    title = meta.get("title") or f"\u756a\u8304\u5c0f\u8bf4{book_id}"
    yield "\n".join([
        f"\u756a\u8304\u5c0f\u8bf4\u6587\u4ef6\u53d1\u9001\u5931\u8d25\uff1a{title}",
        f"\u7ae0\u8282\uff1a\u6210\u529f {len(ok_chapters)} / \u603b\u8ba1 {len(chapters)}",
        f"\u6587\u4ef6\uff1a{file_name}",
        f"\u539f\u56e0\uff1a{limit_text(send_error, 500)}",
        "\u4e0b\u8f7d\u7f13\u5b58\u6587\u4ef6\u5df2\u5220\u9664\uff0c\u6ca1\u6709\u4fdd\u5b58\u5728\u672c\u5730",
    ])


async def fetch_book_meta(session: aiohttp.ClientSession, book_id: str, source: str) -> dict[str, Any]:
    meta = default_meta(book_id)
    meta = merge_meta(meta, await fetch_share_landing_meta(session, source, book_id))
    return merge_meta(meta, await fetch_web_meta(session, book_id))


async def fetch_share_landing_meta(session: aiohttp.ClientSession, source: str, book_id: str) -> dict[str, Any]:
    if not str(source or "").startswith("http"):
        return {}
    try:
        async with session.get(source, allow_redirects=True, timeout=20) as response:
            page_text = await response.text()
            final_url = str(response.url)
    except Exception as exc:
        logger.debug(f"fanqie share page failed: source={limit_text(source)}, error={exc}")
        return {}

    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(final_url).query, keep_blank_values=True))
    params = {
        "aid": query.get("aid", "1967"),
        "series_id": query.get("series_id", "0"),
        "encrypt_did": query.get("encrypt_did", ""),
        "performance_optimization": "1",
        "share_type": query.get("share_type", "11"),
        "video_id": query.get("video_id", ""),
        "actor_id": query.get("actor_id", ""),
        "post_id": query.get("post_id", ""),
        "book_id": query.get("book_id") or book_id,
        "pos_info_str": "undefined:undefined:undefined:undefined:undefined:undefined",
    }
    headers = dict(BROWSER_HEADERS)
    headers.update({"Referer": "https://changdunovel.com/", "x-xs-from-web": "1", "Content-Type": "application/json"})
    try:
        async with session.get(LANDING_URL, params=params, headers=headers, timeout=20) as response:
            payload = await response.json(content_type=None)
    except Exception as exc:
        logger.debug(f"fanqie landing meta failed: book_id={book_id}, error={exc}")
        return extract_meta_from_page_text(page_text)

    data = read_path(payload, ("data", "book_data"))
    if not isinstance(data, dict):
        return extract_meta_from_page_text(page_text)
    author = data.get("author")
    if isinstance(author, dict):
        author = author.get("name")
    return {
        "title": clean_text(data.get("title")),
        "author": clean_text(author),
        "intro": clean_text(data.get("intro")),
        "word_count": format_word_count(data.get("word_count") or data.get("preview_word_count")),
        "status": normalize_status(data.get("creation_status"), ""),
        "chapter_count": safe_int(data.get("chapter_count") or data.get("chapter_num") or data.get("all_chapter_num") or data.get("latest_chapter_index")),
    }


async def fetch_web_meta(session: aiohttp.ClientSession, book_id: str) -> dict[str, Any]:
    try:
        async with session.get(f"https://fanqienovel.com/page/{book_id}", timeout=20) as response:
            if response.status >= 400:
                return {}
            page_text = await response.text()
    except Exception as exc:
        logger.debug(f"fanqie page meta failed: book_id={book_id}, error={exc}")
        return {}
    return merge_meta(extract_meta_from_page_text(page_text), extract_meta_from_state(extract_initial_state(page_text)))


async def fetch_catalog(session: aiohttp.ClientSession, book_id: str, api_key: str) -> list[dict[str, Any]]:
    payload = await request_fqread(session, book_id, api_key, "chapters", "")
    catalog = extract_catalog(payload.get("data") if isinstance(payload, dict) else payload)
    if not catalog and isinstance(payload, dict):
        catalog = extract_catalog(payload.get("message"))
    logger.info(f"\u756a\u8304\u5c0f\u8bf4\u76ee\u5f55\u83b7\u53d6\u5b8c\u6210\uff1abook_id={book_id}, chapters={len(catalog)}")
    return catalog


async def download_all_chapters(
    session: aiohttp.ClientSession,
    book_id: str,
    catalog: list[dict[str, Any]],
    api_key: str,
    total_words: int,
) -> list[dict[str, Any]]:
    total = len(catalog)
    finished = 0
    success = 0
    failed = 0
    last_step = 0
    results: list[dict[str, Any]] = []
    logger.info(f"\u756a\u8304\u5c0f\u8bf4\u7ae0\u8282\u8fdb\u5ea6\uff1abook_id={book_id}, progress=0/{total}, percent=0%")

    def log_progress(batch_results: list[dict[str, Any]]) -> None:
        nonlocal finished, success, failed, last_step
        finished += len(batch_results)
        success += sum(1 for item in batch_results if item.get("success"))
        failed += sum(1 for item in batch_results if not item.get("success"))
        step = PROGRESS_STEPS if finished >= total else int(finished * PROGRESS_STEPS / total)
        if step <= last_step and finished < total:
            return
        last_step = step
        percent = int(finished * 100 / total) if total else 100
        logger.info(
            f"\u756a\u8304\u5c0f\u8bf4\u7ae0\u8282\u8fdb\u5ea6\uff1abook_id={book_id}, "
            f"progress={finished}/{total}, percent={percent}%, success={success}, failed={failed}"
        )

    for chunk in split_catalog(catalog, total_words):
        chunk_results = await download_chapter_batch(session, book_id, api_key, chunk)
        log_progress(chunk_results)
        results.extend(chunk_results)
    return results


async def download_chapter_batch(
    session: aiohttp.ClientSession,
    book_id: str,
    api_key: str,
    batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        return await request_and_map_chapter_batch(session, book_id, api_key, batch)
    except Exception as exc:
        if len(batch) <= 1:
            chapter = batch[0]
            logger.warning(
                f"\u756a\u8304\u5c0f\u8bf4\u7ae0\u8282\u4e0b\u8f7d\u5931\u8d25\uff1abook_id={book_id}, "
                f"chapter={chapter.get('index')}, chapter_id={chapter.get('id')}, error={exc}"
            )
            return [{**chapter, "content": "\u3010\u4e0b\u8f7d\u5931\u8d25\u3011", "success": False}]
        mid = max(1, len(batch) // 2)
        logger.warning(
            f"\u756a\u8304\u5c0f\u8bf4\u8303\u56f4\u8bf7\u6c42\u5931\u8d25\uff0c\u62c6\u5206\u91cd\u8bd5\uff1abook_id={book_id}, "
            f"range={batch[0].get('index')}-{batch[-1].get('index')}, error={exc}"
        )
        left = await download_chapter_batch(session, book_id, api_key, batch[:mid])
        right = await download_chapter_batch(session, book_id, api_key, batch[mid:])
        return left + right


async def request_and_map_chapter_batch(
    session: aiohttp.ClientSession,
    book_id: str,
    api_key: str,
    batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    start = min(int(chapter.get("index") or 0) for chapter in batch)
    end = max(int(chapter.get("index") or 0) for chapter in batch)
    chapter_arg = str(start) if start == end else f"{start}-{end}"
    payload = await request_fqread(session, book_id, api_key, "chapter", chapter_arg)
    raw_items = normalize_response_chapters(payload.get("data") if isinstance(payload, dict) else payload)
    if not raw_items and isinstance(payload, dict):
        raw_items = normalize_response_chapters(payload.get("message"))
    if not raw_items:
        raise RuntimeError("\u7ae0\u8282\u6b63\u6587\u63a5\u53e3\u6ca1\u6709\u8fd4\u56de\u7ae0\u8282\u6570\u636e")

    results = map_chapter_response(batch, raw_items)
    matched = sum(1 for item in results if item.get("success"))
    if matched < len(batch):
        raise RuntimeError(f"\u7ae0\u8282\u8fd4\u56de\u4e0d\u5b8c\u6574\uff1amatched={matched}/{len(batch)}")
    return results


async def request_fqread(
    session: aiohttp.ClientSession,
    book_id: str,
    api_key: str,
    method: str,
    chapter_arg: str,
) -> dict[str, Any]:
    params = {"id": book_id, "book_id": book_id, "method": method, "key": api_key, "type": "json"}
    if chapter_arg:
        params["chapter"] = chapter_arg
    async with session.get(API_URL, params=params, timeout=90) as response:
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"OIAPI HTTP {response.status}: {limit_text(text, 120)}")
        try:
            payload = json.loads(text)
        except Exception as exc:
            raise RuntimeError(f"OIAPI JSON\u89e3\u6790\u5931\u8d25\uff1a{limit_text(text, 120)}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("OIAPI \u8fd4\u56de\u683c\u5f0f\u4e0d\u662f\u5bf9\u8c61")
    code = payload.get("code")
    if str(code) not in ("1", "200"):
        message = payload.get("message") or payload.get("msg") or payload.get("error") or "\u63a5\u53e3\u8fd4\u56de\u5931\u8d25"
        raise RuntimeError(f"OIAPI\u8fd4\u56de\u5931\u8d25\uff1acode={code}, message={limit_text(message, 200)}")
    return payload


def extract_catalog(data: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        title = clean_text(read_any(value, ("title", "chapter_title", "name")))
        chapter_id = clean_text(read_any(value, ("chapter_id", "chapterId", "item_id", "itemId", "id")))
        index = safe_int(read_any(value, ("chapter", "index", "order", "chapter_index", "chapterIndex", "realChapterOrder")))
        if (title or chapter_id) and (chapter_id or index):
            items.append({"id": chapter_id or str(index), "title": title or f"\u7b2c{index or len(items) + 1}\u7ae0", "index": index or len(items) + 1})
            return
        for child in value.values():
            if isinstance(child, (dict, list)):
                walk(child)

    walk(data)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for pos, item in enumerate(items, start=1):
        item["index"] = safe_int(item.get("index")) or pos
        key = (str(item.get("id") or ""), int(item.get("index") or 0))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return sorted(deduped, key=lambda item: int(item.get("index") or 0))



def normalize_response_chapters(data: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        if extract_content(value):
            results.append(value)
            return
        for child in value.values():
            if isinstance(child, (dict, list)):
                walk(child)

    walk(data)
    return results


def map_chapter_response(batch: list[dict[str, Any]], raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {clean_text(read_any(item, ("chapter_id", "chapterId", "item_id", "itemId", "id"))): item for item in raw_items}
    by_index = {str(safe_int(read_any(item, ("chapter", "index", "order", "chapter_index", "chapterIndex")))): item for item in raw_items}
    use_order = len(raw_items) == len(batch)
    results: list[dict[str, Any]] = []
    for pos, chapter in enumerate(batch):
        raw = by_id.get(str(chapter.get("id") or "")) or by_index.get(str(chapter.get("index") or ""))
        if raw is None and use_order:
            raw = raw_items[pos]
        content = clean_content(extract_content(raw) if raw else "")
        title = clean_text(read_any(raw or {}, ("title", "chapter_title", "name"))) or str(chapter.get("title") or f"\u7b2c{chapter.get('index')}\u7ae0")
        results.append({**chapter, "title": title, "content": content or "\u3010\u4e0b\u8f7d\u5931\u8d25\u3011", "success": bool(content)})
    return results


def extract_content(chapter: dict[str, Any] | None) -> str:
    if not isinstance(chapter, dict):
        return ""
    return clean_text(read_any(chapter, ("content", "chapter_content", "text", "body")))


def split_catalog(catalog: list[dict[str, Any]], total_words: int) -> list[list[dict[str, Any]]]:
    if not catalog:
        return []
    split_count = max(1, math.ceil(total_words / MAX_WORDS_PER_RANGE)) if total_words > 0 else 1
    chunk_size = max(1, math.ceil(len(catalog) / split_count))
    return [catalog[start:start + chunk_size] for start in range(0, len(catalog), chunk_size)]


def build_index_catalog(chapter_count: int) -> list[dict[str, Any]]:
    if chapter_count <= 0:
        return []
    return [{"id": str(index), "title": f"\u7b2c{index}\u7ae0", "index": index} for index in range(1, chapter_count + 1)]


def build_txt_file(
    book_id: str,
    meta: dict[str, Any],
    catalog: list[dict[str, Any]],
    chapter_results: list[dict[str, Any]],
) -> tuple[str, bytes]:
    file_name = build_file_name(book_id, meta)
    lines = [
        DISCLAIMER,
        "",
        f"\u540d\u79f0\uff1a{meta.get('title') or f'\u756a\u8304\u5c0f\u8bf4{book_id}'}",
        f"\u4f5c\u8005\uff1a{meta.get('author') or '\u672a\u77e5'}",
        f"\u72b6\u6001\uff1a{status_text(meta)}",
        f"\u5b57\u6570\uff1a{meta.get('word_count') or '\u672a\u77e5'}",
        f"\u7b80\u4ecb\uff1a{meta.get('intro') or '\u6682\u65e0\u7b80\u4ecb'}",
        f"\u4e66\u7c4dID\uff1a{book_id}",
        f"\u7ae0\u8282\u6570\uff1a{len(catalog)}",
        "",
    ]
    for chapter in chapter_results:
        lines.append(str(chapter.get("title") or f"\u7b2c{chapter.get('index')}\u7ae0"))
        lines.append("")
        lines.append(str(chapter.get("content") or "\u3010\u4e0b\u8f7d\u5931\u8d25\u3011").strip())
        lines.append("")
    return file_name, "\n".join(lines).encode("utf-8")


def build_file_name(book_id: str, meta: dict[str, Any]) -> str:
    title = clean_file_name(meta.get("title") or f"\u756a\u8304\u5c0f\u8bf4{book_id}")
    author = clean_file_name(meta.get("author") or "\u672a\u77e5")
    return f"[{status_text(meta)}]\u4e66\u540d\uff1a{title} \u4f5c\u8005\uff1a{author}.txt"


def format_download_notice(meta: dict[str, Any], chapter_count: int) -> str:
    intro = limit_text(meta.get("intro") or "\u6682\u65e0\u7b80\u4ecb", 160)
    return "\n".join([
        f"\u4e66\u540d\uff1a{meta.get('title') or '\u672a\u77e5'}",
        f"\u4f5c\u8005\uff1a{meta.get('author') or '\u672a\u77e5'}",
        f"\u72b6\u6001\uff1a{status_text(meta)}",
        f"\u7ae0\u8282\uff1a{chapter_count} \u7ae0",
        f"\u5b57\u6570\uff1a{meta.get('word_count') or '\u672a\u77e5'}",
        f"\u7b80\u4ecb\uff1a{intro}",
        "",
        "\u6b63\u5728\u4e0b\u8f7d\u4e2d\u8bf7\u7a0d\u7b49.....",
    ])


async def prepare_text_file_send(event: Any, file_name: str, file_content: bytes) -> dict[str, Any]:
    group_id = get_group_id(event)
    user_id = get_user_id(event)
    logger.info(f"\u756a\u8304\u5c0f\u8bf4\u51c6\u5907\u53d1\u9001\u6587\u4ef6\uff1afile={file_name}, size={len(file_content)}, group_id={group_id}, user_id={user_id}")
    cache_path = write_cache_file(file_name, file_content)
    logger.info(f"\u756a\u8304\u5c0f\u8bf4\u5199\u5165\u4e0b\u8f7d\u7f13\u5b58\uff1afile={cache_path}, size={len(file_content)}")

    if Comp is not None and hasattr(event, "chain_result"):
        try:
            chain_result = event.chain_result([Comp.File(name=file_name, file=str(cache_path))])
            logger.info(f"\u756a\u8304\u5c0f\u8bf4\u6587\u4ef6\u4f7f\u7528 AstrBot File \u7ec4\u4ef6\u53d1\u9001\uff1afile={file_name}, path={cache_path}")
            return {"sent": True, "chain_result": chain_result, "cache_path": cache_path, "error": ""}
        except Exception as exc:
            logger.warning(f"\u756a\u8304\u5c0f\u8bf4 AstrBot File \u7ec4\u4ef6\u6784\u5efa\u5931\u8d25\uff1afile={file_name}, error={exc}")

    bot = getattr(event, "bot", None)
    api = getattr(bot, "api", None)
    call_action = getattr(api, "call_action", None)
    if callable(call_action):
        sent, error = await send_file_candidates(call_action, group_id, user_id, file_name, [("path", str(cache_path)), ("file_uri", cache_path.as_uri())])
        delete_cache_file(cache_path)
        return {"sent": sent, "chain_result": None, "cache_path": None, "error": error}

    delete_cache_file(cache_path)
    return {"sent": False, "chain_result": None, "cache_path": None, "error": "\u5f53\u524d bot \u6ca1\u6709 api.call_action \u63a5\u53e3\uff0c\u4e5f\u65e0\u6cd5\u4f7f\u7528 AstrBot File \u7ec4\u4ef6"}


def schedule_delete_cache_file(cache_path: Any, delay_seconds: int = FILE_COMPONENT_CACHE_DELETE_DELAY) -> None:
    if not cache_path:
        return

    async def delete_later() -> None:
        await asyncio.sleep(delay_seconds)
        delete_cache_file(cache_path)

    try:
        asyncio.create_task(delete_later())
    except RuntimeError:
        delete_cache_file(cache_path)


def delete_cache_file(cache_path: Any) -> None:
    if not cache_path:
        return
    try:
        Path(cache_path).unlink(missing_ok=True)
        logger.info(f"\u756a\u8304\u5c0f\u8bf4\u4e0b\u8f7d\u7f13\u5b58\u6587\u4ef6\u5df2\u5220\u9664\uff1afile={cache_path}")
    except Exception as exc:
        logger.warning(f"\u756a\u8304\u5c0f\u8bf4\u4e0b\u8f7d\u7f13\u5b58\u6587\u4ef6\u5220\u9664\u5931\u8d25\uff1afile={cache_path}, error={exc}")


async def send_file_candidates(
    call_action: Any,
    group_id: str,
    user_id: str,
    file_name: str,
    candidates: list[tuple[str, str]],
) -> tuple[bool, str]:
    if not group_id and not user_id:
        return False, "\u6ca1\u6709\u83b7\u53d6\u5230\u7fa4\u53f7\u6216\u7528\u6237\u53f7"

    errors = []
    for method_name, file_arg in candidates:
        try:
            if group_id:
                await call_action("upload_group_file", group_id=group_id, file=file_arg, name=file_name)
                logger.info(f"\u756a\u8304\u5c0f\u8bf4\u6587\u4ef6\u53d1\u9001\u6210\u529f\uff1amethod={method_name}, target=group, file={file_name}, group_id={group_id}")
                return True, ""
            await call_action("upload_private_file", user_id=user_id, file=file_arg, name=file_name)
            logger.info(f"\u756a\u8304\u5c0f\u8bf4\u6587\u4ef6\u53d1\u9001\u6210\u529f\uff1amethod={method_name}, target=private, file={file_name}, user_id={user_id}")
            return True, ""
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")
            logger.warning(f"\u756a\u8304\u5c0f\u8bf4\u6587\u4ef6\u53d1\u9001\u5019\u9009\u5931\u8d25\uff1amethod={method_name}, file={file_name}, error={exc}")
    return False, "\uff1b".join(errors)


def write_cache_file(file_name: str, file_content: bytes) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = unique_cache_path(file_name)
    cache_path.write_bytes(file_content)
    return cache_path


def unique_cache_path(file_name: str) -> Path:
    safe_name = Path(clean_file_name(file_name)).name or "\u756a\u8304\u5c0f\u8bf4.txt"
    if not safe_name.lower().endswith(".txt"):
        safe_name = f"{safe_name}.txt"
    cache_path = CACHE_DIR / safe_name
    if not cache_path.exists():
        return cache_path
    suffix = cache_path.suffix
    stem = cache_path.stem
    for index in range(1, 1000):
        candidate = CACHE_DIR / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("\u4e0b\u8f7d\u7f13\u5b58\u76ee\u5f55\u4e2d\u540c\u540d\u6587\u4ef6\u8fc7\u591a")



def extract_direct_source(command_text: str) -> str | None:
    text = str(command_text or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{15,25}", text):
        return text
    return extract_source(text) or None


def extract_event_source(event: Any) -> str | None:
    message_obj = getattr(event, "message_obj", None)
    for obj in (event, message_obj):
        if obj is None:
            continue
        for field in ("message_str", "raw_message", "message"):
            source = extract_source(read_field(obj, field))
            if source:
                return source
    return None


def extract_source(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            source = extract_source(item)
            if source:
                return source
        return ""
    if isinstance(value, dict):
        for item in value.values():
            source = extract_source(item)
            if source:
                return source
        return ""

    raw_text = str(value or "")
    for text in text_variants(raw_text):
        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip("),.;]")
            if DOMAIN_RE.search(url) and extract_book_id(url):
                return url
        if DOMAIN_RE.search(text) and extract_book_id(text):
            return text
        if re.fullmatch(r"\d{15,25}", text.strip()):
            return text.strip()
    return ""


def extract_book_id(text: str) -> str:
    for candidate in text_variants(str(text or "")):
        candidate = candidate.strip()
        if re.fullmatch(r"\d{15,25}", candidate):
            return candidate
        patterns = (
            r"(?:book_id|bookid|bookId)=(\d{15,25})",
            r"fanqienovel\.com/(?:page|reader)?/?(\d{15,25})",
            r"fanqienovel\.com/[^\s?&#]*/(\d{15,25})",
            r"(?:changdunovel\.com|fqnovel\.com|novelfm\.com).*?(?:book_id|bookid|bookId)=(\d{15,25})",
        )
        for pattern in patterns:
            match = re.search(pattern, candidate, re.IGNORECASE)
            if match:
                return match.group(1)
    return ""


def text_variants(text: str) -> list[str]:
    text = html.unescape(str(text or "")).replace("\\/", "/")
    variants = [text]
    for _ in range(2):
        decoded = urllib.parse.unquote(variants[-1])
        if decoded == variants[-1]:
            break
        variants.append(decoded)
    return variants


def get_fanqie_key(config: Any) -> str:
    value = read_field(config, "\u756a\u8304\u5c0f\u8bf4key")
    return str(value or "").strip()


def default_meta(book_id: str) -> dict[str, Any]:
    return {
        "book_id": book_id,
        "title": f"\u756a\u8304\u5c0f\u8bf4{book_id}",
        "author": "\u672a\u77e5",
        "intro": "",
        "status": "\u672a\u77e5",
        "word_count": "\u672a\u77e5",
        "chapter_count": 0,
    }


def merge_meta(base: dict[str, Any], new_values: dict[str, Any]) -> dict[str, Any]:
    result = dict(base or {})
    for key, value in (new_values or {}).items():
        if value in (None, "", 0):
            continue
        current = result.get(key)
        if current in (None, "", 0, "\u672a\u77e5", "\u6682\u65e0\u7b80\u4ecb") or (key == "title" and str(current).startswith("\u756a\u8304\u5c0f\u8bf4")):
            result[key] = value
    return result


def extract_meta_from_state(state: Any) -> dict[str, Any]:
    candidates: list[tuple[int, dict[str, Any]]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        meta = extract_meta_from_dict(value)
        score = 0
        if meta.get("title") and not re.match(r"\u7b2c.+[\u7ae0\u8282\u56de]", str(meta.get("title"))):
            score += 3
        if meta.get("author"):
            score += 3
        if meta.get("intro"):
            score += 1
        if meta.get("word_count") and meta.get("word_count") != "\u672a\u77e5":
            score += 1
        if meta.get("chapter_count"):
            score += 1
        if score >= 3:
            candidates.append((score, meta))
        for item in value.values():
            if isinstance(item, (dict, list)):
                walk(item)

    walk(state)
    if not candidates:
        return {}
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def extract_meta_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    author = read_any(data, ("author", "author_name", "authorName"))
    if isinstance(author, dict):
        author = read_any(author, ("name", "author_name", "authorName"))
    status_raw = read_any(data, ("creation_status", "creationStatus", "status", "book_status", "bookStatus"))
    status_desc = clean_text(read_any(data, ("status_text", "statusText", "status_desc", "statusDesc")))
    return {
        "title": clean_text(read_any(data, ("book_name", "bookName", "bookTitle", "title", "name"))),
        "author": clean_text(author),
        "intro": clean_text(read_any(data, ("intro", "abstract", "description", "summary", "bookAbstract"))),
        "word_count": format_word_count(read_any(data, ("word_count", "wordCount", "word_number", "wordNumber", "totalWords"))),
        "status": normalize_status(status_raw, status_desc),
        "chapter_count": safe_int(read_any(data, ("chapter_count", "chapterCount", "chapter_num", "chapterNum", "all_chapter_num", "latest_chapter_index"))),
    }


def extract_meta_from_page_text(page_text: str) -> dict[str, Any]:
    text = str(page_text or "")
    title = extract_html_field(text, (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', r"<title>(.*?)</title>"))
    title = re.sub(r"[_-].*\u756a\u8304\u5c0f\u8bf4.*$", "", title).strip()
    author = extract_html_field(text, (r'authorName["\']?\s*[:=]\s*["\']([^"\']+)', r'author_name["\']?\s*[:=]\s*["\']([^"\']+)'))
    intro = extract_html_field(text, (r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', r'intro["\']?\s*[:=]\s*["\']([^"\']+)'))
    return {"title": clean_text(title), "author": clean_text(author), "intro": clean_text(intro)}


def extract_initial_state(page_text: str) -> dict[str, Any]:
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.+?)</script>", page_text or "", re.DOTALL)
    if not match:
        match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.+)", page_text or "", re.DOTALL)
    if not match:
        return {}
    content = match.group(1)
    balance = 0
    chunk = []
    for char in content:
        chunk.append(char)
        if char == "{":
            balance += 1
        elif char == "}":
            balance -= 1
            if balance == 0:
                break
    try:
        return json.loads("".join(chunk))
    except Exception:
        return {}


def extract_html_field(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return clean_text(match.group(1))
    return ""


def normalize_status(raw: Any, desc: str = "") -> str:
    text = f"{raw or ''} {desc or ''}".strip().lower()
    if any(keyword in text for keyword in ("\u5df2\u5b8c\u7ed3", "\u5b8c\u7ed3", "\u5b8c\u672c", "finished", "completed", "ended")):
        return "\u5b8c\u7ed3"
    if any(keyword in text for keyword in ("\u8fde\u8f7d", "\u66f4\u65b0", "ongoing", "serial")):
        return "\u8fde\u8f7d"
    if str(raw).strip().lower() in ("0", "2"):
        return "\u5b8c\u7ed3"
    if str(raw).strip().lower() in ("1", "3", "4"):
        return "\u8fde\u8f7d"
    return ""



def status_text(meta: dict[str, Any]) -> str:
    return normalize_status(meta.get("status"), "") or "\u8fde\u8f7d"


def format_word_count(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return ""
    if "\u5b57" in text:
        return text
    count = parse_word_count(text)
    if count <= 0:
        return text
    if count >= 100_000_000:
        return f"{round(count / 100_000_000, 1):g}\u4ebf\u5b57"
    if count >= 10_000:
        return f"{round(count / 10_000, 1):g}\u4e07\u5b57"
    return f"{count}\u5b57"


def parse_word_count(value: Any) -> int:
    text = str(value or "").strip().replace(" ", "")
    match = re.search(r"([\d.]+)", text)
    if not match:
        return 0
    number = float(match.group(1))
    if "\u4ebf" in text:
        number *= 100_000_000
    elif "\u4e07" in text:
        number *= 10_000
    return int(number)


def clean_content(text: Any) -> str:
    text = str(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = clean_text(text).replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(text or ""))
    return html.unescape(text).strip()


def clean_file_name(file_name: Any) -> str:
    file_name = re.sub(r'[\\/:*?"<>|]', "_", str(file_name or "")).strip().rstrip(".")
    return file_name[:80] or "\u756a\u8304\u5c0f\u8bf4"


def limit_text(value: Any, max_length: int = 2000) -> str:
    text = str(value or "")
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def safe_int(value: Any) -> int:
    if value in (None, "") or isinstance(value, bool):
        return 0
    try:
        return max(0, int(float(str(value).strip())))
    except Exception:
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else 0


def read_any(data: dict[str, Any], fields: tuple[str, ...]) -> Any:
    if not isinstance(data, dict):
        return None
    for field in fields:
        value = data.get(field)
        if value not in (None, ""):
            return value
    return None


def read_path(data: Any, path: tuple[str, ...]) -> Any:
    current = data
    for field in path:
        if not isinstance(current, dict):
            return None
        current = current.get(field)
    return current


def get_group_id(event: Any) -> str:
    for method_name in ("get_group_id", "get_group"):
        method = getattr(event, method_name, None)
        if callable(method):
            value = method()
            if value:
                return str(value)
    message_obj = getattr(event, "message_obj", None)
    for obj in (event, message_obj):
        value = read_field(obj, "group_id") or read_field(obj, "group")
        if isinstance(value, dict):
            value = value.get("group_id") or value.get("id")
        if value:
            return str(value)
    return ""


def get_user_id(event: Any) -> str:
    for method_name in ("get_sender_id", "get_user_id"):
        method = getattr(event, method_name, None)
        if callable(method):
            value = method()
            if value:
                return str(value)
    message_obj = getattr(event, "message_obj", None)
    for obj in (event, message_obj):
        value = read_field(obj, "sender_id") or read_field(obj, "user_id") or read_field(obj, "sender")
        if isinstance(value, dict):
            value = value.get("user_id") or value.get("id")
        if value:
            return str(value)
    return ""


def read_field(obj: Any, field: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


# main.py \u4f7f\u7528\u4e2d\u6587\u5165\u53e3\uff0c\u5176\u4ed6\u903b\u8f91\u4fdd\u6301\u5728\u672c\u6587\u4ef6\u5185\u3002
globals()["\u83b7\u53d6\u756a\u8304\u5c0f\u8bf4\u56de\u590d\u6d41"] = get_fanqie_reply_stream
globals()["\u63d0\u53d6\u4e66\u7c4d\u7f16\u53f7"] = extract_book_id
globals()["\u63d0\u53d6\u756a\u8304\u6765\u6e90"] = extract_source
