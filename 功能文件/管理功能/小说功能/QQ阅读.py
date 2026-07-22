from __future__ import annotations
import asyncio, base64, gzip, hashlib, io, json, re, tarfile, threading, time, urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional, Sequence, Tuple
import aiohttp
from astrbot.api import logger
from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态值, 写入运行状态值
try:
    from astrbot.api import message_components as Comp
except Exception:
    Comp = None
try:
    from Crypto.Cipher import AES, DES
    from Crypto.Util.Padding import unpad as _unpad
    _有加密库 = True
except Exception:
    AES = DES = _unpad = None
    _有加密库 = False
try:
    from 功能文件.管理功能.网盘功能 import UC网盘
except Exception as e:
    UC网盘 = None
    logger.warning(f"UC网盘模块加载失败：error={e}")
try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as e:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败：error={e}")
try:
    from 功能文件.API功能.析API import QQ阅读 as 析APIQQ阅读
except Exception as e:
    析APIQQ阅读 = None
    logger.warning(f"QQ阅读析API模块加载失败：error={e}")

API状态命名空间="qq_reader_api"; API开关状态键="enabled"
登录态命名空间="qq_reader_auth"; 登录态状态键="login_state"
登录会话等待秒数=180; 文件组件缓存清理延迟=600
下载缓存目录=Path(__file__).resolve().parents[2]/"下载缓存"
免责声明="声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
下载失败提示="下载失败"; 文件发送失败提示="文件发送失败，请稍后再试"; 登录失败提示="登录失败，请稍后再试"
详情地址="https://commontgw.reader.qq.com/book/queryBookInfo"
批量正文地址="https://newminerva-tgw.reader.qq.com/ChapBatAuthWithPD"
发短信地址="https://ptlogin.yuewen.com/sdk/sendphonecode"
验证码登录地址="https://ptlogin.yuewen.com/sdk/phonecodelogin"
默认UA="QQReaderAndroid/8.5.2.890"; 滑块AppId="1600000770"; 默认登录版本="8.5.2.890"
默认YW签名="0F69C1415A21FE8D8D504F4C6C792847"; 默认YW_SDK="401"
默认IBEX=("n3Bl6YO_sAraVTVlp6JYHRIznI5tlwdCvgNDxWs6XmJfE3B8Erqx0l-pH-9Tm_b362BPtnuU3t4Pc5j_"
"MstRVEkFvuZCxW0ukz2AwnwljbDUDpuo81UrYQVIexitiw-UcBgx4YD2BQNiKid-uzBHqQTO94uFsH4Oc_"
"ZL-0ZkoTbc2KHy5Risa0iuPY4lSBGRzUaGdoG-wWIIKeRa43QW9OhJFK4ALX1V5XiHTyo-Xv-IGgnoZaTa8_"
"7h1zsHwPf2jIOeiWwYAhbdA5iirmZhwHHkHChmO9yp3n-NFn5q1A9b3hqJMPMacGAjdXKLBIBsIyiPTp-"
"iiRriFYjSwyXhzVLUdhYg_B5RNxCuXSlDKSF9E6RCOxVl5wAAFfB3vQbAjsHRSVak0KuFPoTHb3x7hVz0P"
"CupP82oZGMwZjU2NzJhYWI0ZGEwZTZjMjM2NDkyNDI5MThiMmY=")
默认设备={"qimei":"0022ece0af3ed4d0052148e33e8bce20ab31a706cf9af04b","qimei36":"104a6cc03680b90a518e73db10001f31a706","source":"00000","version":默认登录版本,"version_code":"417","osversion":f"Android 28 {默认登录版本} 417","devicetype":"OnePlus_GM1910","ibex":默认IBEX,"sdkversion":默认YW_SDK,"fuid":"89306811035542cd868d49def7d3857d"}
FOCK_TOKEN="KNVA76RTD8YZXZ6Z"; FOCK_TOKEN_PWD=b"c9ajudte0zb21ksg"; FOCK_TOKEN_IV=b"58jb6v2lzcspwymg"
_FOCK_TOKEN_BLOB=bytes.fromhex("8f400c5fcec88186569c7c407e35d2895495f9025321cd94976e786a65f18550")
QQ阅读来源正则=re.compile(r"reader\.qq\.com|book\.qq\.com|novel\.html5\.qq\.com|154\.12\.91\.167:7000", re.I)
链接正则=re.compile(r"https?://[^\s'\"<>\u3001\uff0c\u3002]+", re.I)
手机号正则=re.compile(r"^1\d{10}$"); 验证码正则=re.compile(r"^\d{4,8}$")
待登录会话: dict[str, dict[str, Any]] = {}

def 读取字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None: return None
    if isinstance(对象, dict): return 对象.get(字段名)
    return getattr(对象, 字段名, None)

def 清理文本(文本: Any) -> str:
    return re.sub(r"\s+", " ", str(文本 or "")).strip()

def 限制文本长度(值: Any, 最大长度: int = 200) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."

def 安全整数(值: Any) -> int:
    try: return int(str(值).strip())
    except Exception: return 0

def 获取会话键(event: Any) -> str:
    群号 = 读取字段(event, "group_id") or 读取字段(getattr(event, "message_obj", None), "group_id") or "private"
    用户 = "unknown"
    try:
        if callable(getattr(event, "get_sender_id", None)):
            用户 = str(event.get_sender_id() or "unknown")
    except Exception:
        用户 = str(读取字段(event, "sender_id") or "unknown")
    return f"{群号}:{用户}"

def QQ阅读API是否开启(配置: Any = None) -> bool:
    if 配置 is None: return False
    try:
        状态 = str(读取运行状态值(配置, API状态命名空间, API开关状态键, "off") or "").strip().lower()
        return 状态 in ("on", "1", "true", "yes", "开启")
    except Exception as e:
        logger.warning(f"QQ阅读API开关读取失败：error={e}")
        return False

def 写入QQ阅读API开关(配置: Any, 是否开启: bool) -> None:
    写入运行状态值(配置, API状态命名空间, API开关状态键, "on" if 是否开启 else "off")

def 读取QQ阅读登录态(配置: Any) -> dict[str, str]:
    try:
        文本 = 读取运行状态值(配置, 登录态命名空间, 登录态状态键, "")
        if not 文本: return {}
        数据 = json.loads(文本)
        if isinstance(数据, dict):
            return {str(k): str(v) for k, v in 数据.items() if v not in (None, "")}
    except Exception as e:
        logger.warning(f"QQ阅读登录态读取失败：error={e}")
    return {}

def 写入QQ阅读登录态(配置: Any, 登录态: dict[str, Any]) -> None:
    清洗 = {str(k): str(v) for k, v in (登录态 or {}).items() if v not in (None, "")}
    写入运行状态值(配置, 登录态命名空间, 登录态状态键, json.dumps(清洗, ensure_ascii=False))
    logger.info("QQ阅读登录态已保存到数据库")

def _unpad_pkcs7(data: bytes, block: int) -> bytes:
    if _有加密库 and _unpad is not None:
        return _unpad(data, block)
    if not data: raise ValueError("empty")
    pad = data[-1]
    if pad < 1 or pad > block or data[-pad:] != bytes([pad]) * pad:
        raise ValueError("bad pkcs7")
    return data[:-pad]

def fock_token() -> str:
    if not _有加密库: return FOCK_TOKEN
    try:
        pt = AES.new(FOCK_TOKEN_PWD, AES.MODE_CBC, iv=FOCK_TOKEN_IV).decrypt(_FOCK_TOKEN_BLOB)
        tok = _unpad_pkcs7(pt, 16).decode("ascii")
        if tok: return tok
    except Exception:
        pass
    return FOCK_TOKEN

def 解析keypool_ids(keypool_plain: bytes) -> List[str]:
    return re.findall(r"[0-9a-fA-F]{16}", keypool_plain.decode("ascii", "ignore"))

def 解密keypool_ids(keypool: bytes, fuid: str, token: str = "") -> List[str]:
    if not _有加密库: return 解析keypool_ids(keypool)
    fuid_b = fuid.encode("utf-8"); tok = (token or fock_token()).encode("ascii")
    key1 = hashlib.sha256(fuid_b + tok).digest()
    if len(keypool) % 16: keypool = keypool[:len(keypool)//16*16]
    if len(keypool) < 16: return []
    pt = AES.new(key1, AES.MODE_CBC, iv=key1[:16]).decrypt(keypool)
    try: pt = _unpad_pkcs7(pt, 16)
    except Exception: pt = pt.rstrip(b"\r\n")
    return 解析keypool_ids(pt)

def 是否二进制(data: bytes) -> bool:
    if not data: return False
    sample = data[:256]
    return b"\x00" in sample or sum(1 for b in sample if b < 9 or (13 < b < 32)) > 10

def 解码文本(data: bytes) -> str:
    for enc in ("utf-8", "gb18030", "gbk"):
        try: return data.decode(enc)
        except UnicodeDecodeError: pass
    return data.decode("utf-8", "replace")

def 解密章节密文(cipher: bytes, *, bid: str, cid: str, fuid: str, keypool: bytes = b"") -> Tuple[Optional[bytes], str]:
    if not cipher: return None, "empty"
    if not 是否二进制(cipher): return cipher, "plain"
    if cipher[:2] == b"\x1f\x8b":
        try: return gzip.decompress(cipher), "gzip"
        except Exception: pass
    if not _有加密库: return None, "no_crypto"
    if not keypool: return None, "missing_keypool"
    try:
        fuid_b = fuid.encode("utf-8"); ak_b = f"{bid}_{cid}_s".encode("utf-8"); tok = fock_token().encode("ascii")
        key1 = hashlib.sha256(fuid_b + tok).digest()
        hdr = AES.new(key1, AES.MODE_CBC, iv=key1[:16]).decrypt(cipher[:0x100])
        ids = 解密keypool_ids(keypool, fuid, tok.decode("ascii")) or 解析keypool_ids(keypool)
        if not ids: return None, "no_pool_ids"
        bodies = []
        body80 = hdr[0x80:0x100] + cipher[0x100:]; n = len(body80)//16*16
        if n >= 16: bodies.append(body80[:n])
        body100 = cipher[0x100:]; n2 = len(body100)//16*16
        if n2 >= 16: bodies.append(body100[:n2])
        for pid in ids:
            key2 = hashlib.sha256(pid.encode("ascii") + fuid_b + ak_b).digest()
            for body in bodies:
                try:
                    mid = AES.new(key2, AES.MODE_CBC, iv=key2[:16]).decrypt(body)
                    mid = _unpad_pkcs7(mid, 16)
                    m = len(mid)//8*8
                    if m < 8: continue
                    gz = DES.new(key2[:8], DES.MODE_CBC, iv=key2[:8]).decrypt(mid[:m])
                    gz = _unpad_pkcs7(gz, 8)
                    if gz[:2] != b"\x1f\x8b": continue
                    return gzip.decompress(gz), f"fock_uk:{pid}"
                except Exception:
                    continue
        return None, "decrypt_fail"
    except Exception as e:
        return None, f"decrypt_error:{e}"

@dataclass
class Tar成员:
    name: str
    size: int
    data: bytes

def 组装URL(base: str, params: Mapping[str, Any]) -> str:
    query = urllib.parse.urlencode({k: str(v) for k, v in params.items() if v is not None}, doseq=True)
    return f"{base}?{query}" if query else base

def 最小请求头(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    src = {str(k): str(v) for k, v in (登录态 or {}).items() if v not in (None, "")}
    ywguid = src.get("ywguid") or src.get("login_uin") or src.get("uid") or ""
    ywkey = src.get("ywkey") or src.get("login_key") or ""
    cookie = src.get("Cookie") or src.get("cookie") or ""
    if (not cookie) and ywguid and ywkey:
        cookie = f"ywguid={ywguid}; ywkey={ywkey};"
    out = {"User-Agent": src.get("User-Agent") or 默认UA, "Accept": "*/*"}
    if cookie: out["Cookie"] = cookie
    if ywguid: out["ywguid"] = ywguid; out["uid"] = ywguid
    if ywkey: out["ywkey"] = ywkey
    if src.get("fuid"): out["fuid"] = src["fuid"]
    return out

def 是否deny(data: bytes) -> bool:
    if not data or data[:1] != b"{": return False
    try: obj = json.loads(data.decode("utf-8", "replace"))
    except Exception: return False
    return isinstance(obj, dict) and str(obj.get("code")) in {"-1", "401", "403"} and "deny" in str(obj.get("msg", "")).lower()

def 解析tar(blob: bytes) -> List[Tar成员]:
    if 是否deny(blob): raise RuntimeError("接口拒绝访问")
    if not blob or blob[:1] == b"{": raise RuntimeError("返回不是章节包")
    out: List[Tar成员] = []
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
        for m in tf.getmembers():
            if not m.isfile(): continue
            f = tf.extractfile(m)
            data = f.read() if f else b""
            out.append(Tar成员(name=m.name, size=len(data), data=data))
    return out

def 解析目录文本(text: str) -> List[Dict[str, Any]]:
    chapters: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        parts = line.split(",")
        if len(parts) < 2: continue
        cid = parts[0].strip(); title = parts[1].strip() or f"第{cid}章"
        chapters.append({"cid": cid, "id": cid, "title": title, "index": len(chapters) + 1})
    return chapters

def 找目录成员(entries: Sequence[Tar成员], bid: str) -> Optional[Tar成员]:
    names = {f"{bid}_ALL_o", f"{bid}_ALL_s"}
    for e in entries:
        if e.name in names or e.name.endswith("_ALL_o") or e.name.endswith("_ALL_s"):
            return e
    return None

def 章节成员(entries: Sequence[Tar成员], bid: str) -> List[Tar成员]:
    prefix = f"{bid}_"
    return [e for e in entries if e.name.startswith(prefix) and e.name.endswith("_s") and "_ALL_" not in e.name]

def 章节编号(name: str, bid: str) -> str:
    mid = name
    if mid.startswith(f"{bid}_"): mid = mid[len(bid)+1:]
    if mid.endswith("_s"): mid = mid[:-2]
    return mid

async def http_get_bytes(session: aiohttp.ClientSession, url: str, headers: Mapping[str, str], timeout: int = 60) -> Tuple[bytes, int]:
    async with session.get(url, headers=dict(headers), timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        return await resp.read(), resp.status

async def http_get_json(session: aiohttp.ClientSession, url: str, headers: Mapping[str, str], timeout: int = 30) -> Any:
    data, status = await http_get_bytes(session, url, headers, timeout=timeout)
    if status >= 400: raise RuntimeError(f"HTTP {status}")
    return json.loads(data.decode("utf-8", "replace"))

async def http_post_form_json(session: aiohttp.ClientSession, url: str, params: Mapping[str, Any], timeout: int = 30) -> Any:
    body = urllib.parse.urlencode({k: str(v) for k, v in params.items() if v is not None}, doseq=True).encode("utf-8")
    headers = {"User-Agent": 默认UA, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json,text/plain,*/*"}
    async with session.post(url, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        return json.loads(await resp.text())

async def 请求书籍信息(session: aiohttp.ClientSession, bid: str, 登录态: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    url = 组装URL(详情地址, {"bid": bid, "types": "1,2,3,4,5"})
    data = await http_get_json(session, url, 最小请求头(登录态), timeout=30)
    return data if isinstance(data, dict) else {}

async def 请求批量包(session: aiohttp.ClientSession, bid: str, scids: str, *, 登录态: Optional[Mapping[str, str]] = None, text_type: int = 1, useindex: bool = False, usepreview: int = 0, timeout: int = 300) -> bytes:
    headers = 最小请求头(登录态)
    fuid = headers.get("fuid") or str((登录态 or {}).get("fuid") or "")
    if fuid:
        params = {"bookId": bid, "usepreview": usepreview, "type": 0, "tafauth": 1, "scids": scids, "scene": 0, "adState": 1, "fuid": fuid, "noclick": 1, "text_type": int(text_type), "useindex": 1 if useindex else 0}
    else:
        params = {"bookId": bid, "scids": scids, "type": 0, "text_type": 0, "useindex": 1 if useindex else 0, "tafauth": 1}
    url = 组装URL(批量正文地址, params)
    data, status = await http_get_bytes(session, url, headers, timeout=timeout)
    if status >= 400: raise RuntimeError(f"批量接口 HTTP {status}")
    return data

async def 请求目录(session: aiohttp.ClientSession, bid: str, 登录态: Optional[Mapping[str, str]] = None) -> List[Dict[str, Any]]:
    blob = await 请求批量包(session, bid, "0", 登录态=登录态, text_type=0, useindex=True, usepreview=0, timeout=60)
    entries = 解析tar(blob)
    ce = 找目录成员(entries, bid)
    if not ce: return []
    return 解析目录文本(解码文本(ce.data))

def 从详情提取书籍(data: Any, bid: str) -> Dict[str, Any]:
    root = data if isinstance(data, dict) else {}
    info = root.get("data") if isinstance(root.get("data"), dict) else root
    book = info.get("bookInfo") if isinstance(info.get("bookInfo"), dict) else info
    if not isinstance(book, dict): book = {}
    title = str(book.get("title") or book.get("bookName") or f"QQ阅读{bid}")
    author = str(book.get("author") or book.get("authorName") or "未知")
    status_raw = str(book.get("finished") or book.get("finishstate") or book.get("status") or "")
    if status_raw in {"1", "完结", "完本", "true", "True"}: status = "完结"
    elif status_raw in {"0", "连载", "false", "False"}: status = "连载"
    else: status = status_raw or "未知"
    words = book.get("totalWords") or book.get("allwords") or book.get("wordCount") or book.get("words") or "未知"
    chapters = book.get("chapterNum") or book.get("chapters") or book.get("totalChapter") or 0
    return {"book_id": bid, "title": title, "author": author, "status": status, "word_count": words, "chapter_count": chapters}

def 解密章节(cipher: bytes, bid: str, cid: str, 登录态: Mapping[str, str]) -> Tuple[Optional[str], str]:
    fuid = str(登录态.get("fuid") or 默认设备.get("fuid") or "")
    keypool = b""
    b64 = str(登录态.get("keypool_b64") or "")
    if b64:
        try: keypool = base64.b64decode(b64 + "===")
        except Exception: keypool = b""
    plain, note = 解密章节密文(cipher, bid=bid, cid=cid, fuid=fuid, keypool=keypool)
    if plain is None:
        if not 是否二进制(cipher): return 解码文本(cipher).strip(), "plain"
        return None, note
    return 解码文本(plain).strip(), note

def 手机号带区号(phone: str, area: str = "+86") -> str:
    value = re.sub(r"[\s\-()]+", "", str(phone or ""))
    if not value: raise ValueError("手机号不能为空")
    if value.startswith("+"): return value
    if value.startswith("86") and len(value) == 13: return f"+{value}"
    if not re.fullmatch(r"1\d{10}", value): raise ValueError("手机号格式不正确")
    return f"{area}{value}"

def 登录默认参数(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    d = dict(默认设备)
    if 登录态:
        for k in ("qimei", "qimei36", "ibex", "version", "version_code", "osversion", "devicetype", "source", "fuid"):
            if 登录态.get(k): d[k] = 登录态[k]
    version = d.get("version") or 默认登录版本
    version_code = d.get("version_code") or "417"
    params = {"referer":"http://android.qidian.com","appid":"1450000219","areaid":"1","auto":"1","autotime":"30","ticket":"0","format":"json","signature":默认YW签名,"source":d.get("source") or "00000","version":version,"devicetype":d.get("devicetype") or "OnePlus_GM1910","devicename":"GM1910","returnurl":"http://www.qidian.com","osversion":d.get("osversion") or f"Android 28 {version} {version_code}","sdkversion":默认YW_SDK,"ibex":d.get("ibex") or 默认IBEX}
    qimei = str(d.get("qimei") or ""); qimei36 = str(d.get("qimei36") or "")
    if len(qimei) >= 16: params["qimei"] = qimei
    if len(qimei36) >= 16: params["qimei36"] = qimei36
    return params

def 遍历JSON对象(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values(): yield from 遍历JSON对象(v)
    elif isinstance(value, list):
        for item in value: yield from 遍历JSON对象(item)

def 查找登录载荷(response: Any) -> Optional[Dict[str, Any]]:
    for obj in 遍历JSON对象(response):
        ywguid = obj.get("ywguid") or obj.get("login_uin") or obj.get("uid")
        ywkey = obj.get("ywkey") or obj.get("login_key")
        if ywguid and ywkey: return dict(obj)
    return None

def 查找nextAction(response: Any) -> int:
    for obj in 遍历JSON对象(response):
        v = obj.get("nextAction")
        if v is not None and str(v).isdigit(): return int(v)
    return 0

def 查找字符串字段(response: Any, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for obj in 遍历JSON对象(response):
        for k, v in obj.items():
            if str(k).lower() in wanted and v not in (None, ""): return str(v)
    return ""

def 应用滑块参数(params: Dict[str, Any], ticket: str = "", randstr: str = "", session_key: str = "") -> Dict[str, Any]:
    out = dict(params)
    if session_key: out["sessionKey"] = session_key
    if ticket: out["sig"] = ticket; out["ticket"] = ticket
    if randstr: out["code"] = randstr; out["randstr"] = randstr
    return out

def 从登录载荷构造登录态(payload: Mapping[str, Any], phone: str = "") -> Dict[str, str]:
    ywguid = str(payload.get("ywguid") or payload.get("login_uin") or payload.get("uid") or "")
    ywkey = str(payload.get("ywkey") or payload.get("login_key") or "")
    fuid = str(payload.get("fuid") or 默认设备.get("fuid") or "")
    cookie = str(payload.get("Cookie") or "")
    if not cookie and ywguid and ywkey: cookie = f"ywguid={ywguid}; ywkey={ywkey};"
    out = {"User-Agent":默认UA,"login_type":"2","ywguid":ywguid,"ywkey":ywkey,"uid":ywguid,"Cookie":cookie,"fuid":fuid,"qimei":默认设备.get("qimei",""),"qimei36":默认设备.get("qimei36",""),"ibex":默认设备.get("ibex","")}
    if phone: out["phone"] = phone
    if payload.get("qrsn"): out["qrsn"] = str(payload.get("qrsn"))
    return out

def 生成滑块HTML(appid: str = 滑块AppId, callback_url: str = "http://127.0.0.1:8765/captcha") -> str:
    appid_json = json.dumps(str(appid)); cb_json = json.dumps(str(callback_url))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/><title>QQ阅读登录</title><script src="https://turing.captcha.qcloud.com/TCaptcha.js"></script>
<style>:root{{--bg:#F7F5F2;--card:#fff;--title:#1F2329;--muted:#8A8F98;--primary:#FF6A00;--ok:#18A058;--bad:#E34D59;--shadow:0 12px 40px rgba(31,35,41,.08)}}*{{box-sizing:border-box}}html,body{{height:100%;margin:0}}body{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;color:var(--title);background:radial-gradient(1200px 480px at 50% -120px,rgba(255,106,0,.16),transparent 60%),var(--bg);display:flex;align-items:center;justify-content:center;padding:24px 16px}}.shell{{width:100%;max-width:420px}}.brand{{display:flex;align-items:center;gap:10px;margin-bottom:16px}}.logo{{width:36px;height:36px;border-radius:10px;background:linear-gradient(145deg,#FF8A33,#FF6A00);color:#fff;display:grid;place-items:center;font-weight:700}}.card{{background:var(--card);border-radius:20px;box-shadow:var(--shadow);padding:28px 22px 22px;text-align:center}}h1{{margin:0 0 8px;font-size:24px}}.desc{{margin:0 0 22px;color:var(--muted);font-size:14px}}.status{{min-height:52px;margin:8px 0 18px;border-radius:14px;background:#FAF8F6;display:flex;align-items:center;justify-content:center;gap:8px;color:var(--muted);font-size:14px;padding:12px}}.status.ok{{color:var(--ok);background:rgba(24,160,88,.08)}}.status.bad{{color:var(--bad);background:rgba(227,77,89,.08)}}.status.busy{{color:var(--primary);background:rgba(255,106,0,.08)}}.dot{{width:8px;height:8px;border-radius:50%;background:currentColor}}.btn{{width:100%;border:0;border-radius:999px;padding:14px 18px;font-size:16px;font-weight:600}}.btn-primary{{background:var(--primary);color:#fff}}.btn-ghost{{margin-top:10px;background:transparent;color:var(--muted);border:1px solid #E8E4DE;display:none}}.btn-ghost.show{{display:block}}.foot{{margin-top:16px;color:var(--muted);font-size:12px}}</style></head>
<body><div class="shell"><div class="brand"><div class="logo">QQ</div><div>QQ阅读登录</div></div><div class="card"><h1>安全验证</h1><p class="desc">完成滑动验证后继续登录</p><div id="status" class="status"><span class="dot"></span><span id="statusText">等待验证</span></div><button id="btn" class="btn btn-primary" type="button">开始验证</button><button id="retry" class="btn btn-ghost" type="button">重新验证</button><div class="foot">验证完成后请返回 QQ 继续输入短信验证码</div></div></div>
<script>
const APPID={appid_json}; const CB={cb_json};
const statusEl=document.getElementById('status'); const statusText=document.getElementById('statusText');
const btn=document.getElementById('btn'); const retry=document.getElementById('retry');
function setStatus(kind,text){{statusEl.className='status'+(kind?' '+kind:''); statusText.textContent=text; retry.classList.toggle('show',kind==='bad');}}
function postResult(payload){{fetch(CB,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload||{{}})}}).then(function(){{setStatus((payload&&Number(payload.ret)===0&&payload.ticket)?'ok':'bad',(payload&&Number(payload.ret)===0&&payload.ticket)?'验证成功，正在返回':'验证失败，请重试');}}).catch(function(){{setStatus((payload&&Number(payload.ret)===0&&payload.ticket)?'ok':'bad',(payload&&Number(payload.ret)===0&&payload.ticket)?'验证成功，正在返回':'验证失败，请重试');}});}}
function start(){{setStatus('busy','验证中…'); try{{const captcha=new TencentCaptcha(APPID,function(res){{const payload={{ret:res&&res.ret,ticket:(res&&res.ticket)||'',randstr:(res&&res.randstr)||'',time:Date.now()/1000}}; if(Number(payload.ret)===0&&payload.ticket){{setStatus('busy','验证中…'); postResult(payload);}} else setStatus('bad','验证失败，请重试');}},{{}}); captcha.show();}}catch(e){{setStatus('bad','验证失败，请重试');}}}}
btn.addEventListener('click',start); retry.addEventListener('click',start); setTimeout(start,400);
</script></body></html>"""

def 启动滑块本地服务(*, host: str = "127.0.0.1", port: int = 8765, timeout: int = 180) -> Dict[str, str]:
    result: Dict[str, Any] = {}; done = threading.Event()
    callback_url = f"http://{host}:{port}/captcha"; page_html = 生成滑块HTML(callback_url=callback_url)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None: return
        def _send(self, code: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
            self.send_response(code); self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_OPTIONS(self) -> None: self._send(204, b"")
        def do_GET(self) -> None:
            if self.path.startswith("/captcha") or self.path == "/" or self.path.startswith("/?"): self._send(200, page_html.encode("utf-8"), "text/html; charset=utf-8"); return
            self._send(404, b"not found")
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0); raw = self.rfile.read(length) if length > 0 else b"{}"
            try: payload = json.loads(raw.decode("utf-8", "replace"))
            except Exception: payload = {}
            if isinstance(payload, dict) and payload.get("ticket"): result.update(payload); done.set(); self._send(200, b"ok")
            else: self._send(400, b"bad")
    httpd = HTTPServer((host, port), Handler); threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        import webbrowser; webbrowser.open(callback_url)
    except Exception: pass
    ok = done.wait(timeout=timeout)
    try: httpd.shutdown()
    except Exception: pass
    if not ok or not result.get("ticket"): raise TimeoutError("滑块验证超时")
    return {"ticket": str(result.get("ticket") or ""), "randstr": str(result.get("randstr") or "")}

async def 发送手机验证码(session: aiohttp.ClientSession, phone: str, *, ticket: str = "", randstr: str = "", session_key: str = "", 登录态: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    full_phone = 手机号带区号(phone); params = 登录默认参数(登录态)
    params.update({"type": "1", "needRegister": "1", "phone": full_phone})
    if ticket or randstr or session_key: params = 应用滑块参数(params, ticket=ticket, randstr=randstr, session_key=session_key)
    response = await http_post_form_json(session, 发短信地址, params, timeout=30)
    next_action = 查找nextAction(response); key = 查找字符串字段(response, "sessionKey", "sessionkey", "phonekey")
    return {"response": response, "next_action": next_action, "session_key": key, "phone": full_phone, "success": bool(key) and next_action != 11, "need_captcha": next_action == 11}

async def 提交手机验证码(session: aiohttp.ClientSession, phone: str, code: str, session_key: str, *, 登录态: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    full_phone = 手机号带区号(phone); params = 登录默认参数(登录态)
    params.update({"phonekey": session_key, "phonecode": str(code).strip(), "phone": urllib.parse.quote_plus(full_phone)})
    response = await http_post_form_json(session, 验证码登录地址, params, timeout=30)
    payload = 查找登录载荷(response)
    if not payload: return {"success": False, "response": response}
    return {"success": True, "auth": 从登录载荷构造登录态(payload, phone=full_phone), "response": response}

def 格式化字数(值: Any) -> str:
    if isinstance(值, (int, float)): 数 = int(值)
    else:
        文本 = str(值 or "").strip()
        if not 文本 or 文本 == "未知": return "未知"
        m = re.search(r"([\d.]+)\s*万", 文本)
        if m: return f"{m.group(1)}万字"
        try: 数 = int(float(文本))
        except Exception: return 文本 if "字" in 文本 else f"{文本}字"
    if 数 >= 10000: return f"{数/10000:.1f}万字".replace(".0万", "万")
    return f"{数}字"

def 格式化下载提示(书籍信息: dict[str, Any], 章节数: int) -> str:
    return "\n".join([f"书名：{书籍信息.get('title') or '未知'}", f"作者：{书籍信息.get('author') or '未知'}", f"状态：{书籍信息.get('status') or '未知'}", f"章节：{章节数} 章", f"字数：{格式化字数(书籍信息.get('word_count'))}", "", "正在下载中请稍等....."])

def 生成小说文件名(书籍信息: dict[str, Any]) -> str:
    状态 = str(书籍信息.get("status") or "")
    前缀 = "[完结]" if "完结" in 状态 or "完本" in 状态 else "[连载]"
    书名 = re.sub(r'[\\/:*?"<>|]', "_", str(书籍信息.get("title") or "未知书名"))
    作者 = re.sub(r'[\\/:*?"<>|]', "_", str(书籍信息.get("author") or "未知"))
    return f"{前缀}书名：{书名} 作者：{作者}.txt"

def 构造TXT文件(书籍编号: str, 书籍信息: dict[str, Any], 章节结果列表: list[dict[str, Any]]) -> tuple[str, bytes]:
    文件名 = 生成小说文件名(书籍信息)
    行 = [免责声明, "", f"书名：{书籍信息.get('title') or '未知'}", f"作者：{书籍信息.get('author') or '未知'}", f"状态：{书籍信息.get('status') or '未知'}", f"章节：{len(章节结果列表)} 章", f"字数：{格式化字数(书籍信息.get('word_count'))}", f"来源：QQ阅读 {书籍编号}", ""]
    for 项目 in 章节结果列表:
        行.append(清理文本(项目.get("title") or f"第{项目.get('index')}章")); 行.append(""); 行.append(str(项目.get("content") or "").strip()); 行.append("")
    return 文件名, "\n".join(行).encode("utf-8")

def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 下载缓存目录 / 文件名; 路径.write_bytes(文件内容); return 路径

def 延迟删除缓存文件(缓存路径: Any, 延迟秒数: int = 文件组件缓存清理延迟) -> None:
    if not 缓存路径: return
    async def _删除() -> None:
        await asyncio.sleep(max(1, 延迟秒数))
        try: Path(缓存路径).unlink(missing_ok=True)
        except Exception: pass
    try: asyncio.get_running_loop().create_task(_删除())
    except Exception: pass

async def 准备发送文本文件(event: Any, 文件名: str, 文件内容: bytes, 配置: Any = None) -> dict[str, Any]:
    缓存路径 = 写入下载缓存文件(文件名, 文件内容); 发送路径 = 缓存路径; 发送文件名 = 文件名
    if UC网盘 is not None:
        try:
            UC结果 = await UC网盘.准备小说分享链接文件(配置, 缓存路径, 文件名, 写入下载缓存文件)
            if UC结果 and UC结果.get("success") and UC结果.get("path"):
                发送路径 = Path(UC结果["path"]); 发送文件名 = str(UC结果.get("file_name") or 文件名)
                logger.info(f"QQ阅读UC网盘上传成功，改发同名链接文件：file={发送文件名}")
        except Exception as e:
            logger.warning(f"QQ阅读UC网盘上传失败：error={e}")
    链式结果 = None
    if Comp is not None:
        try: 链式结果 = event.chain_result([Comp.File(file=str(发送路径), name=发送文件名)])
        except Exception as e: logger.warning(f"QQ阅读 File 组件构造失败：error={e}")
    if 百度网盘 is not None:
        try:
            启动百度 = getattr(百度网盘, "启动百度后台上传并清理源文件", None)
            if callable(启动百度):
                if 链式结果 is not None:
                    def _后台() -> None:
                        try: 启动百度(配置, 缓存路径, 文件名, 发送路径 if 发送路径 != 缓存路径 else None)
                        except Exception as exc: logger.warning(f"QQ阅读百度网盘后台上传失败：error={exc}")
                    asyncio.get_running_loop().call_later(1.0, _后台)
                else:
                    启动百度(配置, 缓存路径, 文件名, None)
        except Exception as e:
            logger.warning(f"QQ阅读百度网盘处理失败：error={e}")
    if 链式结果 is not None: return {"sent": False, "chain_result": 链式结果, "cache_path": 发送路径}
    try:
        client = getattr(event, "bot", None) or getattr(event, "client", None)
        group_id = 读取字段(event, "group_id") or 读取字段(getattr(event, "message_obj", None), "group_id")
        user_id = None
        try:
            if callable(getattr(event, "get_sender_id", None)): user_id = event.get_sender_id()
        except Exception: pass
        if client is not None and group_id and hasattr(client, "upload_group_file"):
            await client.upload_group_file(group_id=group_id, file=str(发送路径), name=发送文件名); return {"sent": True, "cache_path": 发送路径}
        if client is not None and user_id and hasattr(client, "upload_private_file"):
            await client.upload_private_file(user_id=user_id, file=str(发送路径), name=发送文件名); return {"sent": True, "cache_path": 发送路径}
    except Exception as e:
        return {"sent": False, "error": str(e), "cache_path": 发送路径}
    return {"sent": False, "error": "当前适配器无法发送文件", "cache_path": 发送路径}

def 提取QQ阅读来源(值: Any) -> str:
    if 值 is None: return ""
    if isinstance(值, (list, tuple, set)):
        for 项目 in 值:
            来源 = 提取QQ阅读来源(项目)
            if 来源: return 来源
        return ""
    if isinstance(值, dict):
        for 项目 in 值.values():
            来源 = 提取QQ阅读来源(项目)
            if 来源: return 来源
        return ""
    文本 = str(值)
    if not QQ阅读来源正则.search(文本): return ""
    for 匹配 in 链接正则.findall(文本):
        if QQ阅读来源正则.search(匹配): return 匹配.rstrip(")，。；;,]")
    return 文本 if QQ阅读来源正则.search(文本) else ""

def 提取直接QQ阅读来源(命令文本: str) -> str | None:
    文本 = str(命令文本 or "").strip(); return 提取QQ阅读来源(文本) or None if 文本 else None

def 提取事件QQ阅读来源(event: Any) -> str | None:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None: continue
        for 字段名 in ("message_str", "raw_message", "message"):
            来源 = 提取QQ阅读来源(读取字段(对象, 字段名))
            if 来源: return 来源
    return None

def 解析书籍编号(来源: str) -> str:
    文本 = str(来源 or "")
    for 模式 in (r"[?&]bid=(\d+)", r"[?&]bookid=(\d+)", r"/book-detail/(\d+)", r"/intro\?bid=(\d+)", r"bid%3D(\d+)", r"/(\d{5,})"):
        m = re.search(模式, 文本, re.I)
        if m: return m.group(1)
    m = re.search(r"(\d{5,})", 文本); return m.group(1) if m else ""

def 获取QQ阅读回复流(event: Any, 命令文本: str, 配置: Any = None) -> AsyncIterator[Any] | None:
    来源 = 提取直接QQ阅读来源(命令文本) or 提取事件QQ阅读来源(event)
    if 来源 is None: return None
    if QQ阅读API是否开启(配置) and 析APIQQ阅读 is not None:
        return 析APIQQ阅读.获取QQ阅读回复流(event, 命令文本, 配置)
    return 生成本地下载回复流(event, 来源, 配置)

async def 下载全书批量(session: aiohttp.ClientSession, 书籍编号: str, 目录: list[dict[str, Any]], 登录态: dict[str, str]) -> list[dict[str, Any]]:
    """固定拆成最多 5 批，动态并发请求（有空位就继续发）。"""
    if not 目录:
        return []
    总数 = len(目录)
    批次数 = min(5, 总数)
    每批 = (总数 + 批次数 - 1) // 批次数
    分批 = []
    for i in range(批次数):
        s = i * 每批
        e = min(总数, s + 每批)
        if s >= e:
            break
        分批.append((i, 目录[s:e]))
    信号量 = asyncio.Semaphore(5)
    结果映射: dict[int, list[dict[str, Any]]] = {}
    logger.info(f"QQ阅读本地5批并发：book_id={书籍编号}, chapters={总数}, batches={len(分批)}, batch_size~={每批}, concurrency=5")

    async def 下载一批(序号: int, 批次: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        async with 信号量:
            if not 批次:
                return 序号, []
            起始 = 安全整数(批次[0].get("index")) or (序号 * 每批 + 1)
            结束 = 安全整数(批次[-1].get("index")) or (起始 + len(批次) - 1)
            scids = str(起始) if 起始 == 结束 else f"{起始}-{结束}"
            最后异常 = None
            for text_type in (1, 2):
                try:
                    blob = await 请求批量包(session, 书籍编号, scids, 登录态=登录态, text_type=text_type, useindex=False, usepreview=0, timeout=180)
                    entries = 解析tar(blob)
                    chaps = 章节成员(entries, 书籍编号)
                    by_cid = {章节编号(e.name, 书籍编号): e for e in chaps}
                    结果: list[dict[str, Any]] = []
                    成功数 = 0
                    for j, 章节 in enumerate(批次):
                        cid = str(章节.get("cid") or 章节.get("id") or 章节.get("index") or "")
                        标题 = 清理文本(章节.get("title") or f"第{章节.get('index')}章")
                        e = by_cid.get(cid)
                        if e is None and len(chaps) == len(批次):
                            e = chaps[j]
                        if e is None or not e.data:
                            结果.append({**章节, "title": 标题, "content": "", "success": False})
                            continue
                        正文, note = 解密章节(e.data, 书籍编号, cid, 登录态)
                        if 正文:
                            成功数 += 1
                            结果.append({**章节, "title": 标题, "content": 正文, "success": True})
                        else:
                            logger.debug(f"QQ阅读章节解密失败：book_id={书籍编号}, cid={cid}, note={限制文本长度(note, 80)}")
                            结果.append({**章节, "title": 标题, "content": "", "success": False})
                    logger.info(f"QQ阅读批次完成：book_id={书籍编号}, batch={序号+1}/{len(分批)}, range={起始}-{结束}, text_type={text_type}, success={成功数}/{len(批次)}")
                    if 成功数 > 0:
                        return 序号, 结果
                except Exception as e:
                    最后异常 = e
                    logger.warning(f"QQ阅读批次失败：book_id={书籍编号}, batch={序号+1}/{len(分批)}, range={起始}-{结束}, text_type={text_type}, error={e}")
            if 最后异常:
                logger.warning(f"QQ阅读批次最终失败：book_id={书籍编号}, range={起始}-{结束}, error={最后异常}")
            return 序号, [{**章节, "title": 清理文本(章节.get("title")), "content": "", "success": False} for 章节 in 批次]

    任务 = [asyncio.create_task(下载一批(i, batch)) for i, batch in 分批]
    for fut in asyncio.as_completed(任务):
        序号, 数据 = await fut
        结果映射[序号] = 数据
    合并: list[dict[str, Any]] = []
    for i, _ in 分批:
        合并.extend(结果映射.get(i) or [])
    成功 = sum(1 for x in 合并 if x.get("success"))
    logger.info(f"QQ阅读本地5批汇总：book_id={书籍编号}, success={成功}/{总数}")
    return 合并

async def 生成本地下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 解析书籍编号(来源)
    if not 书籍编号:
        logger.warning(f"QQ阅读本地下载失败：未识别书籍ID source={限制文本长度(来源)}")
        yield 下载失败提示; return
    登录态 = 读取QQ阅读登录态(配置)
    超时 = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=300)
    try:
        async with aiohttp.ClientSession(timeout=超时) as 会话:
            try: 详情 = await 请求书籍信息(会话, 书籍编号, 登录态)
            except Exception as e:
                logger.warning(f"QQ阅读详情失败：book_id={书籍编号}, error={e}"); 详情 = {}
            书籍信息 = 从详情提取书籍(详情, 书籍编号)
            try: 目录 = await 请求目录(会话, 书籍编号, 登录态)
            except Exception as e:
                logger.warning(f"QQ阅读目录失败：book_id={书籍编号}, error={e}"); 目录 = []
            if not 目录:
                总数 = 安全整数(书籍信息.get("chapter_count"))
                if 总数 > 0:
                    目录 = [{"cid": str(i), "id": str(i), "title": f"第{i}章", "index": i} for i in range(1, 总数 + 1)]
            if not 目录:
                logger.warning(f"QQ阅读本地下载失败：无目录 book_id={书籍编号}"); yield 下载失败提示; return
            for i, ch in enumerate(目录, start=1):
                ch["index"] = 安全整数(ch.get("index")) or i
            书籍信息["chapter_count"] = len(目录)
            logger.info(f"QQ阅读开始下载：source=local, book_id={书籍编号}, title={书籍信息.get('title')}, author={书籍信息.get('author')}, chapters={len(目录)}")
            yield 格式化下载提示(书籍信息, len(目录))
            章节结果 = await 下载全书批量(会话, 书籍编号, 目录, 登录态)
            成功列表 = [x for x in 章节结果 if x.get("success")]
            if not 成功列表 or len(成功列表) < len(目录):
                logger.warning(f"QQ阅读本地下载失败：book_id={书籍编号}, success={len(成功列表)}, total={len(目录)}"); yield 下载失败提示; return
            文件名, 文件内容 = 构造TXT文件(书籍编号, 书籍信息, 章节结果)
            logger.info(f"QQ阅读章节下载完成：book_id={书籍编号}, title={书籍信息.get('title')}, success={len(成功列表)}, total={len(目录)}, file_size={len(文件内容)}")
            发送结果 = await 准备发送文本文件(event, 文件名, 文件内容, 配置)
            缓存路径 = 发送结果.get("cache_path"); 链式结果 = 发送结果.get("chain_result")
            if 链式结果 is not None:
                try: yield 链式结果
                finally: 延迟删除缓存文件(缓存路径)
                return
            if 发送结果.get("sent"): 延迟删除缓存文件(缓存路径); return
            logger.warning(f"QQ阅读文件发送失败：book_id={书籍编号}, file={文件名}, error={发送结果.get('error')}")
            yield 文件发送失败提示
    except Exception as e:
        logger.warning(f"QQ阅读本地下载失败：book_id={书籍编号}, error={e}"); yield 下载失败提示

def 处理QQ阅读API指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if 文本 in ("开启QQ阅读API", "开启qq阅读API", "开启QQ阅读api", "开启qq阅读api"):
        if not 是群文件清理管理员(event, 配置): return "没有权限使用QQ阅读API开关"
        try: 写入QQ阅读API开关(配置, True)
        except Exception as e:
            logger.warning(f"QQ阅读API开关写入失败：enabled=True, error={e}"); return "切换失败，请稍后再试"
        return "QQ阅读API已开启"
    if 文本 in ("关闭QQ阅读API", "关闭qq阅读API", "关闭QQ阅读api", "关闭qq阅读api"):
        if not 是群文件清理管理员(event, 配置): return "没有权限使用QQ阅读API开关"
        try: 写入QQ阅读API开关(配置, False)
        except Exception as e:
            logger.warning(f"QQ阅读API开关写入失败：enabled=False, error={e}"); return "切换失败，请稍后再试"
        return "QQ阅读API已关闭"
    return None

def 清理过期登录会话() -> None:
    现在 = time.time()
    for k in [k for k, v in 待登录会话.items() if 现在 - float(v.get("ts") or 0) > 登录会话等待秒数]:
        待登录会话.pop(k, None)

async def 处理QQ阅读登录指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本: return None
    清理过期登录会话(); 会话键 = 获取会话键(event)
    if 文本 in ("登录QQ阅读", "qq阅读登录", "QQ阅读登录"):
        if not 是群文件清理管理员(event, 配置): return "没有权限登录QQ阅读"
        待登录会话[会话键] = {"step": "phone", "ts": time.time()}
        return "请发送手机号（仅支持中国大陆手机号）\n发送 0 取消"
    会话 = 待登录会话.get(会话键)
    if not 会话: return None
    if not 是群文件清理管理员(event, 配置):
        待登录会话.pop(会话键, None); return "没有权限登录QQ阅读"
    if 文本 in {"0", "取消", "返回", "返回上一步"}:
        待登录会话.pop(会话键, None); return "已取消QQ阅读登录"
    步骤 = str(会话.get("step") or "")
    if 步骤 == "phone":
        号码 = 文本.replace(" ", "")
        if 号码.startswith("+86"): 号码 = 号码[3:]
        if 号码.startswith("86") and len(号码) == 13: 号码 = 号码[2:]
        if not 手机号正则.fullmatch(号码): return "手机号格式不正确，请重新发送\n发送 0 取消"
        try:
            async with aiohttp.ClientSession() as 会话http:
                结果 = await 发送手机验证码(会话http, 号码, 登录态=读取QQ阅读登录态(配置))
        except Exception as e:
            logger.warning(f"QQ阅读发短信失败：error={e}"); return 登录失败提示
        if 结果.get("need_captcha"):
            会话.update({"step": "captcha", "phone": 结果.get("phone") or 号码, "session_key": 结果.get("session_key") or "", "ts": time.time()})
            待登录会话[会话键] = 会话
            try:
                滑块 = await asyncio.to_thread(启动滑块本地服务, timeout=180)
                async with aiohttp.ClientSession() as 会话http:
                    结果2 = await 发送手机验证码(会话http, 会话["phone"], ticket=滑块.get("ticket") or "", randstr=滑块.get("randstr") or "", session_key=会话.get("session_key") or "", 登录态=读取QQ阅读登录态(配置))
                if not 结果2.get("success"):
                    logger.warning(f"QQ阅读滑块后发短信失败：resp={限制文本长度(结果2.get('response'),200)}")
                    待登录会话.pop(会话键, None); return 登录失败提示
                会话.update({"step": "code", "session_key": 结果2.get("session_key") or 会话.get("session_key") or "", "phone": 结果2.get("phone") or 会话.get("phone"), "ts": time.time()})
                待登录会话[会话键] = 会话
                return "验证成功，请发送短信验证码\n发送 0 取消"
            except Exception as e:
                logger.warning(f"QQ阅读滑块验证失败：error={e}")
                待登录会话.pop(会话键, None)
                return "需要完成安全验证，请在机器人服务器本机浏览器完成滑块后重试登录"
        if not 结果.get("success"):
            logger.warning(f"QQ阅读发短信失败：resp={限制文本长度(结果.get('response'),200)}")
            待登录会话.pop(会话键, None); return 登录失败提示
        会话.update({"step": "code", "phone": 结果.get("phone") or 号码, "session_key": 结果.get("session_key") or "", "ts": time.time()})
        待登录会话[会话键] = 会话
        return "验证码已发送，请发送短信验证码\n发送 0 取消"
    if 步骤 == "code":
        if not 验证码正则.fullmatch(文本): return "验证码格式不正确，请重新发送\n发送 0 取消"
        try:
            async with aiohttp.ClientSession() as 会话http:
                结果 = await 提交手机验证码(会话http, str(会话.get("phone") or ""), 文本, str(会话.get("session_key") or ""), 登录态=读取QQ阅读登录态(配置))
        except Exception as e:
            logger.warning(f"QQ阅读验证码登录失败：error={e}"); 待登录会话.pop(会话键, None); return 登录失败提示
        if not 结果.get("success"):
            logger.warning(f"QQ阅读验证码登录失败：resp={限制文本长度(结果.get('response'),200)}")
            待登录会话.pop(会话键, None); return 登录失败提示
        try: 写入QQ阅读登录态(配置, 结果.get("auth") or {})
        except Exception as e:
            logger.warning(f"QQ阅读登录态写入数据库失败：error={e}"); 待登录会话.pop(会话键, None); return 登录失败提示
        待登录会话.pop(会话键, None); return "QQ阅读登录成功"
    if 步骤 == "captcha":
        return "请先完成安全验证，或发送 0 取消"
    return None
