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
    from 功能文件.管理功能.小说功能 import _qq阅读解密 as qq解密
except Exception:
    qq解密 = None
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

登录态命名空间="qq_reader_auth"; 登录态状态键="login_state"
登录会话等待秒数=300; 滑块服务保留秒数=300; 默认滑块端口=8765; 滑块备用端口=(8765,8766,8767,8768,8769,8770); 进度日志分段数=10
下载缓存目录=Path(__file__).resolve().parents[2]/"下载缓存"
免责声明="声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
下载失败提示="下载失败"; 收费书提示="收费书籍不支持下载\n请下载VIP或者免费书"; 文件发送失败提示="文件发送失败，请稍后再试"; 登录失败提示="登录失败，请稍后再试"
详情地址="https://commontgw.reader.qq.com/book/queryBookInfo"
批量正文地址="https://newminerva-tgw.reader.qq.com/ChapBatAuthWithPD"
发短信地址="https://ptlogin.yuewen.com/sdk/sendphonecode"
验证码登录地址="https://ptlogin.yuewen.com/sdk/phonecodelogin"
默认UA="QQReaderAndroid/8.5.2.890"; 滑块AppId="1600000770"; 默认登录版本="8.5.2.890"
默认YW签名=("oMI3aDG4BEctqSrQUTmYDrBNwDYS744OQHMy9qWjqaf0xAI+9W9wtpd3VpfB "
"zyQl0baDZNuqwu5iI43zZe9+fXiErR7tkuMWqshGfT09oNnEtpPCrkYNFBwT "
"k+Faez58Fc442YO4kFw="); 默认YW_SDK="401"
默认IBEX=("n3Bl6YO_sAraVTVlp6JYHRIznI5tlwdCvgNDxWs6XmJfE3B8Erqx0l-pH-9Tm_b362BPtnuU3t4Pc5j_"
"MstRVEkFvuZCxW0ukz2AwnwljbDUDpuo81UrYQVIexitiw-UcBgx4YD2BQNiKid-uzBHqQTO94uFsH4Oc_"
"ZL-0ZkoTbc2KHy5Risa0iuPY4lSBGRzUaGdoG-wWIIKeRa43QW9OhJFK4ALX1V5XiHTyo-Xv-IGgnoZaTa8_"
"7h1zsHwPf2jIOeiWwYAhbdA5iirmZhwHHkHChmO9yp3n-NFn5q1A9b3hqJMPMacGAjdXKLBIBsIyiPTp-"
"iiRriFYjSwyXhzVLUdhYg_B5RNxCuXSlDKSF9E6RCOxVl5wAAFfB3vQbAjsHRSVak0KuFPoTHb3x7hVz0P"
"CupP82oZGMwZjU2NzJhYWI0ZGEwZTZjMjM2NDkyNDI5MThiMmY=")
默认设备={"qimei":"0022ece0af3ed4d0052148e33e8bce20ab31a706cf9af04b","qimei36":"104a6cc03680b90a518e73db10001f31a706","source":"00000","version":默认登录版本,"version_code":"8520888","osversion":f"Android 28 {默认登录版本} 8520888","devicetype":"OnePlus_GM1910","ibex":默认IBEX,"sdkversion":默认YW_SDK,"fuid":"89306811035542cd868d49def7d3857d"}
默认设备keypool_b64="s8ik23/eJ4Px+8RF/ZULIhnfLfrV7M6GiLA0eMhguCZiSm9os7KTYOBcPiJL9LvNoeTB8ne1q3QD/tMoY0LMDInFIfOSU545mz92K+VzsU/tK88BS0h4dHOxkYuisAZLszM2h+fRnmCnwupLxZIglp5Ntlkas9cHpfsWAZ6X2wnstj6ACzw2Onv0e+uYtRA5sjoYMfvmb2ziqwLhgU6sGpmk2tK7Q3hdLjOCV9UZ1oF6BPycMigZ3n2SB4szP3fq8CFvYn4Stty0u9H2/llIgA1vEd838DJvxLsvtliUNfUWAy8Y58GbHU0/gxbcO/PYNVfkkeLl64kbTqCUfvIjkGBXVd0kVd254oS9kv0YNPZbztQe0drh5EifeAXQ/VBOidwyzQZZayuPNgkD4h3bC1LcgGVozVSGwutVBRTP/ZnFjPzZ2wmcUmn5ogfhHIzP6v3k4kWv9FuAZxny/8sDfA=="
正文解密重试次数=6; 缺章补拉轮次=3; 缺章补拉并发=12; 批量章节上限=50; 批量并发上限=6
QQ阅读来源正则=re.compile(r"reader\.qq\.com|book\.qq\.com|novel\.html5\.qq\.com", re.I)
链接正则=re.compile(r"https?://[^\s'\"<>\u3001\uff0c\u3002]+", re.I)
手机号正则=re.compile(r"^1\d{10}$"); 验证码正则=re.compile(r"^\d{4,8}$")
待登录会话: dict[str, dict[str, Any]] = {}

# ===== 一、基础工具 =====

def _是公网IPv4(ip: str) -> bool:
    文本 = str(ip or "").strip()
    if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", 文本):
        return False
    a, b, c, d = [int(x) for x in 文本.split(".")]
    if any(x > 255 for x in (a, b, c, d)):
        return False
    if a == 0 or a == 127 or a >= 224:
        return False
    if a == 10:
        return False
    if a == 169 and b == 254:
        return False
    if a == 172 and 16 <= b <= 31:
        return False
    if a == 192 and b == 168:
        return False
    if a == 100 and 64 <= b <= 127:
        return False
    return True

def 获取滑块公网主机() -> str:
    """自动获取可外网访问公网 IP；过滤 Docker/局域网私网地址。"""
    候选: list[str] = []

    def _收录(值: str) -> None:
        ip = str(值 or "").strip()
        ip = ip.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip()
        if _是公网IPv4(ip) and ip not in 候选:
            候选.append(ip)

    for url in (
        "https://api.ipify.org",
        "http://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ip.sb",
        "https://icanhazip.com",
        "https://checkip.amazonaws.com",
        "https://ipv4.icanhazip.com",
    ):
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                _收录(resp.read().decode("utf-8", "replace").strip())
            if 候选:
                return 候选[0]
        except Exception:
            continue

    # 环境变量兜底（可选）
    import os
    for key in ("QQ_READER_CAPTCHA_PUBLIC_HOST", "MANTOU_CAPTCHA_PUBLIC_HOST", "PUBLIC_IP", "SERVER_PUBLIC_IP"):
        _收录(os.environ.get(key) or "")
        if 候选:
            return 候选[0]

    # 出口 IP 仅当它是公网地址时才用，避免 Docker 172.x
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            _收录(sock.getsockname()[0])
    except Exception:
        pass
    if 候选:
        return 候选[0]
    return ""

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

# ===== 二、登录态读写 =====

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

# ===== 三、正文解密算法 =====

def 是否二进制(data: bytes) -> bool:
    if not data: return False
    sample = data[:256]
    return b"\x00" in sample or sum(1 for b in sample if b < 9 or (13 < b < 32)) > 10

def 解码文本(data: bytes) -> str:
    for enc in ("utf-8", "gb18030", "gbk"):
        try: return data.decode(enc)
        except UnicodeDecodeError: pass
    return data.decode("utf-8", "replace")

def 读取keypool字节(登录态: Optional[Mapping[str, str]] = None) -> bytes:
    src = 登录态 or {}
    b64 = str(src.get("keypool_b64") or 默认设备keypool_b64 or "")
    if not b64:
        return b""
    try:
        return base64.b64decode(b64 + "===")
    except Exception:
        return b""

def 解密章节密文(cipher: bytes, *, bid: str, cid: str, fuid: str, keypool: bytes = b"") -> Tuple[Optional[bytes], str]:
    """仅使用 _qq阅读解密 多模式 libfock，不再走旧算法。"""
    if not cipher:
        return None, "empty"
    if not 是否二进制(cipher):
        return cipher, "plain"
    if cipher[:2] == bytes([0x1f, 0x8b]):
        try:
            return gzip.decompress(cipher), "gzip"
        except Exception:
            pass
    if qq解密 is None:
        return None, "no_decrypt_module"
    if not keypool:
        return None, "missing_keypool"
    stt = f"{bid}_{cid}_s"
    try:
        text = qq解密.try_decrypt_chapter(cipher, stt, fuid, keypool)
        if text is None:
            return None, "decrypt_fail"
        return text.encode("utf-8"), "fock_multi"
    except Exception as e:
        return None, f"decrypt_error:{e}"

def 解密章节(cipher: bytes, bid: str, cid: str, 登录态: Mapping[str, str]) -> Tuple[Optional[str], str]:
    fuid = str(登录态.get("fuid") or 默认设备.get("fuid") or "")
    keypool = 读取keypool字节(登录态)
    plain, note = 解密章节密文(cipher, bid=bid, cid=cid, fuid=fuid, keypool=keypool)
    if plain is None:
        if not 是否二进制(cipher):
            return 解码文本(cipher).strip(), "plain"
        return None, note
    return 解码文本(plain).strip(), note

# ===== 四、章节包与目录解析 =====

@dataclass
class Tar成员:
    name: str
    size: int
    data: bytes

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

# ===== 五、请求头与下载态 =====

def 组装URL(base: str, params: Mapping[str, Any]) -> str:
    query = urllib.parse.urlencode({k: str(v) for k, v in params.items() if v is not None}, doseq=True)
    return f"{base}?{query}" if query else base

def 最小请求头(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """对齐小说大全 sanitize(minimal)：登录只带 Cookie/yw*；fuid 放 query。

    多带设备指纹头容易 deny；游客态无 Cookie。
    """
    src = {str(k): str(v) for k, v in (登录态 or {}).items() if v not in (None, "")}
    ywguid = src.get("ywguid") or src.get("login_uin") or src.get("uid") or ""
    ywkey = src.get("ywkey") or src.get("login_key") or ""
    cookie = src.get("Cookie") or src.get("cookie") or ""
    if (not cookie) and ywguid and ywkey:
        cookie = f"ywguid={ywguid}; ywkey={ywkey};"
    fuid = src.get("fuid") or str(默认设备.get("fuid") or "")
    out = {
        "User-Agent": src.get("User-Agent") or 默认UA,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    if cookie:
        out["Cookie"] = cookie
    if ywguid:
        out["ywguid"] = ywguid
        out["login_uin"] = ywguid
        out["uid"] = ywguid
    if ywkey:
        out["ywkey"] = ywkey
        out["login_key"] = ywkey
    # fuid 主要走 query；header 也带一份给解密侧读取
    if fuid:
        out["fuid"] = fuid
    if src.get("qrsn"):
        out["qrsn"] = src["qrsn"]
    return out

def 组装本地下载态(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """App 设备态 + 可选账号登录态。免费书只靠设备 fuid/keypool，不强制账号登录。"""
    out = {str(k): str(v) for k, v in (登录态 or {}).items() if v not in (None, "")}
    if not out.get("fuid"):
        out["fuid"] = str(默认设备.get("fuid") or "")
    if not out.get("User-Agent"):
        out["User-Agent"] = 默认UA
    if not out.get("keypool_b64"):
        out["keypool_b64"] = 默认设备keypool_b64
    return out

def 组装游客下载态(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """免费/广告书游客态：去掉登录 Cookie/yw*，保留 fuid+keypool。

    小说大全实测：登录态下广告免费书会被 adBookSeeXChapter=5 卡住；
    游客 + adState=0 可拿全本授权；VIP 付费章不会因此放行。
    """
    基 = 组装本地下载态(登录态)
    out = {
        "fuid": str(基.get("fuid") or 默认设备.get("fuid") or ""),
        "User-Agent": str(基.get("User-Agent") or 默认UA),
        "keypool_b64": str(基.get("keypool_b64") or 默认设备keypool_b64 or ""),
    }
    if 基.get("qrsn"):
        out["qrsn"] = str(基.get("qrsn"))
    return out

# ===== 六、HTTP 与接口请求 =====

async def http_get_bytes(session: aiohttp.ClientSession, url: str, headers: Mapping[str, str], timeout: int = 60) -> Tuple[bytes, int]:
    async with session.get(url, headers=dict(headers), timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        return await resp.read(), resp.status

async def http_get_json(session: aiohttp.ClientSession, url: str, headers: Mapping[str, str], timeout: int = 30) -> Any:
    data, status = await http_get_bytes(session, url, headers, timeout=timeout)
    if status >= 400: raise RuntimeError(f"HTTP {status}")
    return json.loads(data.decode("utf-8", "replace"))

async def http_post_form_json(session: aiohttp.ClientSession, url: str, params: Mapping[str, Any], timeout: int = 30) -> Any:
    body = urllib.parse.urlencode({k: str(v) for k, v in params.items() if v is not None}, doseq=True).encode("utf-8")
    # YWLogin SDK 登录接口对 App 上下文和 okhttp 头敏感；用 QQReaderAndroid UA 会直接 code=3。
    headers = {
        "User-Agent": "okhttp/3.12.13",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "Keep-Alive",
        "referer": "http://android.qidian.com",
        "Referer": "http://android.qidian.com",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with session.post(url, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        return json.loads(await resp.text())

async def 请求书籍信息(session: aiohttp.ClientSession, bid: str, 登录态: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    url = 组装URL(详情地址, {"bid": bid, "types": "1,2,3,4,5"})
    data = await http_get_json(session, url, 最小请求头(登录态), timeout=30)
    return data if isinstance(data, dict) else {}

async def 请求批量包(
    session: aiohttp.ClientSession,
    bid: str,
    scids: str,
    *,
    登录态: Optional[Mapping[str, str]] = None,
    text_type: int = 1,
    useindex: bool = False,
    usepreview: int = 0,
    ad_state: Optional[int] = None,
    noclick: Optional[int] = None,
    timeout: int = 300,
) -> bytes:
    headers = 最小请求头(登录态)
    fuid = headers.get("fuid") or str((登录态 or {}).get("fuid") or "")
    有登录 = bool(headers.get("Cookie") or headers.get("ywguid") or headers.get("ywkey"))
    if ad_state is None:
        ad_state = 1 if 有登录 else 0
    if noclick is None:
        noclick = 1 if int(ad_state) == 1 else 0
    if fuid:
        params = {
            "bookId": bid,
            "usepreview": int(usepreview),
            "type": 0,
            "tafauth": 1,
            "scids": scids,
            "scene": 0,
            "adState": int(ad_state),
            "fuid": fuid,
            "noclick": int(noclick),
            "text_type": int(text_type),
            "useindex": 1 if useindex else 0,
        }
    else:
        # 无 fuid 时尽量仍带 adState=0 游客路径
        params = {
            "bookId": bid,
            "scids": scids,
            "type": 0,
            "text_type": int(text_type),
            "useindex": 1 if useindex else 0,
            "tafauth": 1,
            "usepreview": int(usepreview),
            "scene": 0,
            "adState": int(ad_state),
            "noclick": int(noclick),
        }
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

async def 探测可下载章节编号(
    session: aiohttp.ClientSession,
    bid: str,
    章节列表: list[dict[str, Any]],
    登录态: Optional[Mapping[str, str]] = None,
    *,
    text_types: Optional[Sequence[int]] = None,
    ad_state: Optional[int] = None,
) -> set[str]:
    """通过 App 批量接口 info.txt 探测当前态下可下发正文的章节（code=0）。"""
    if not 章节列表:
        return set()
    可下: set[str] = set()
    下载态 = 组装本地下载态(登录态)
    类型候选 = [int(x) for x in (text_types or (1, 2))]
    索引列表 = [安全整数(ch.get("index")) or (i + 1) for i, ch in enumerate(章节列表)]
    # 分段探测，避免超长 scids
    段大小 = 50
    for i in range(0, len(索引列表), 段大小):
        段 = 索引列表[i:i + 段大小]
        if not 段:
            continue
        scids = str(段[0]) if len(段) == 1 else f"{段[0]}-{段[-1]}"
        for text_type in 类型候选:
            try:
                blob = await 请求批量包(
                    session, bid, scids, 登录态=下载态, text_type=text_type,
                    useindex=False, usepreview=0, ad_state=ad_state, timeout=60,
                )
                if 是否deny(blob):
                    continue
                for e in 解析tar(blob):
                    if e.name != "info.txt" or not e.data:
                        continue
                    try:
                        info = json.loads(解码文本(e.data))
                    except Exception:
                        continue
                    if not isinstance(info, list):
                        continue
                    for row in info:
                        if not isinstance(row, dict):
                            continue
                        if "book_title" in row:
                            continue
                        code = str(row.get("code") or "")
                        cid = str(row.get("chapter_id") or row.get("cid") or row.get("uuid") or "")
                        if code in {"0", "OK", "ok"} and cid:
                            可下.add(cid)
            except Exception as e:
                logger.debug(f"QQ阅读探测可下载章节失败：book_id={bid}, range={scids}, text_type={text_type}, error={e}")
    return 可下

def 从详情提取书籍(data: Any, bid: str) -> Dict[str, Any]:
    root = data if isinstance(data, dict) else {}
    # queryBookInfo 多数字段在根层；兼容 data/bookInfo 嵌套
    candidates = []
    if isinstance(root, dict):
        candidates.append(root)
        if isinstance(root.get("data"), dict):
            candidates.append(root["data"])
            if isinstance(root["data"].get("bookInfo"), dict):
                candidates.append(root["data"]["bookInfo"])
        if isinstance(root.get("bookInfo"), dict):
            candidates.append(root["bookInfo"])
        if isinstance(root.get("book"), dict):
            candidates.append(root["book"])

    def 取(*keys, default=""):
        for obj in candidates:
            for k in keys:
                if k in obj and obj.get(k) not in (None, ""):
                    return obj.get(k)
        return default

    title = str(取("title", "bookName", "book_name", default=f"QQ阅读{bid}") or f"QQ阅读{bid}")
    author = str(取("author", "authorName", "author_name", default="未知") or "未知")
    status_raw = 取("isfinished", "finished", "finishstate", "status", "isFinished", default="")
    status_text = str(status_raw).strip().lower()
    if status_text in {"1", "完结", "完本", "true", "yes"}:
        status = "完结"
    elif status_text in {"0", "连载", "false", "no"}:
        status = "连载"
    else:
        status = str(status_raw or "未知")
    words = 取("wordscount", "wordCount", "words", "allwords", "totalWords", "word_count", default="未知")
    chapters = 取("totalChapters", "chapterNum", "chapters", "totalChapter", "chapter_count", default=0)
    # newtotalchapters.txt 兼容
    ntc = 取("newtotalchapters", default=None)
    if isinstance(ntc, dict) and chapters in (0, "0", "", None):
        chapters = ntc.get("txt") or ntc.get("epub") or chapters
    intro = str(取("intro", "desc", "summary", "description", default="") or "")
    category = str(取("categoryName", "category", "categoryInfoV4SlaveName", default="") or "")
    maxfree = 安全整数(取("maxfreechapter", "maxFreeChapter", "freeChapter", "freeChapters", default=0))
    free_flag = 取("free", "isFree", "isfree", default=None)
    is_all_free = str(free_flag).strip().lower() in {"1", "true", "yes"}
    is_ad = 取("isAdBook", "isadbook", "adBook", default=None)
    is_ad_book = str(is_ad).strip().lower() in {"1", "true", "yes"}
    limit_free = 取("islimitfreebook", "isLimitFreeBook", default=None)
    is_limit_free = str(limit_free).strip().lower() in {"1", "true", "yes"}
    price = 取("price", "bookPrice", default=None)
    return {
        "book_id": str(bid),
        "title": title,
        "author": author,
        "status": status,
        "word_count": words if words not in (None, "") else "未知",
        "chapter_count": 安全整数(chapters),
        "max_free_chapter": maxfree,
        "is_all_free": is_all_free,
        "is_ad_book": is_ad_book,
        "is_limit_free": is_limit_free,
        "price": price,
        "intro": intro,
        "category": category,
        "raw": root,
    }

# ===== 七、书籍可下判断 =====

def 是否全书免费可下(书籍信息: Mapping[str, Any], 详情: Any = None) -> bool:
    """是否整本都可下（游客全本）。对所有书通用，不按 book_id 特判。

    规则：
    - free=1 / is_all_free，且没有“部分免费上限”：整本免费
    - isAdBook 且 maxfreechapter=0（或不限）：广告全本，可游客整本下
    - maxfreechapter > 0 且 < 总章数：只是试读/部分免费，不能整本硬下
    """
    if not isinstance(书籍信息, Mapping):
        return False
    total = 安全整数(书籍信息.get("chapter_count"))
    maxfree = 安全整数(书籍信息.get("max_free_chapter"))
    # 先看部分免费上限，避免 free/isAdBook 误判成全本
    if maxfree > 0 and total > 0 and maxfree < total:
        return False
    if 书籍信息.get("is_all_free"):
        return True
    if 书籍信息.get("is_limit_free") and (maxfree <= 0 or total <= 0 or maxfree >= total):
        return True
    # 广告书仅当没有部分免费上限时，才当作全本可下
    if 书籍信息.get("is_ad_book") and maxfree <= 0:
        return True
    nodes: list[Any] = []
    for src in (详情, 书籍信息.get("raw")):
        if isinstance(src, dict):
            nodes.append(src)
            for k in ("data", "bookInfo", "book", "result"):
                v = src.get(k)
                if isinstance(v, dict):
                    nodes.append(v)
    for b in nodes:
        if not isinstance(b, dict):
            continue
        total_b = 安全整数(b.get("totalChapters") or b.get("chapterNum") or total)
        max_b = 安全整数(b.get("maxfreechapter") or b.get("maxFreeChapter") or maxfree)
        if isinstance(b.get("newmaxfreechapter"), dict):
            max_b = max(max_b, 安全整数(b["newmaxfreechapter"].get("txt")))
        if max_b > 0 and total_b > 0 and max_b < total_b:
            return False
        if b.get("free") in (1, "1", True):
            return True
        if b.get("isAdBook") in (1, "1", True) and max_b <= 0:
            return True
        if str(b.get("islimitfreebook") or "").lower() in {"1", "true"} and max_b <= 0:
            return True
    return False

def 是否免费或广告书(书籍信息: Mapping[str, Any], 详情: Any = None) -> bool:
    """兼容旧名：实际表示“可游客下载的免费/广告相关书”，不等价于整本免费。"""
    if not isinstance(书籍信息, Mapping):
        return False
    if 是否全书免费可下(书籍信息, 详情):
        return True
    if 书籍信息.get("is_ad_book") or 书籍信息.get("is_limit_free") or 书籍信息.get("is_all_free"):
        return True
    return False

def 识别正文类型(详情: Any, 书籍信息: Optional[Mapping[str, Any]] = None) -> list[int]:
    """网文 text_type=1，出版 text_type=2。返回候选顺序。"""
    blobs: list[Any] = []
    for src in (详情, (书籍信息 or {}).get("raw") if 书籍信息 else None):
        if isinstance(src, dict):
            blobs.append(src)
            for key in ("data", "bookInfo", "book", "info"):
                v = src.get(key)
                if isinstance(v, dict):
                    blobs.append(v)
    texts: list[str] = []
    for b in blobs:
        if not isinstance(b, dict):
            continue
        for k, v in b.items():
            if v is None:
                continue
            kl = str(k).lower()
            if any(x in kl for x in ("form", "channel", "category", "cata", "type", "source", "pub", "classname")):
                texts.append(str(v))
        if b.get("isbn") or b.get("publisher") or b.get("ISBN"):
            return [2]
        nm = b.get("newmaxfreechapter") or {}
        if isinstance(nm, dict) and 安全整数(nm.get("cteb")) > 0 and 安全整数(nm.get("txt")) == 0:
            return [2]
        for key in ("form", "bookForm", "book_form", "formType", "form_type", "sourceType", "bookType"):
            if key in b:
                try:
                    val = int(b[key])
                    if val == 2:
                        return [2]
                    if val == 1:
                        return [1, 2]
                except Exception:
                    s = str(b[key])
                    if "出版" in s:
                        return [2]
                    if "网文" in s or "原创" in s:
                        return [1, 2]
    joined = " ".join(texts)
    if any(x in joined for x in ("出版", "纸书", "出版社", "图书", "ISBN", "isbn")):
        return [2]
    cat = str((书籍信息 or {}).get("category") or "")
    if any(x in cat for x in ("出版", "纸书", "图书")):
        return [2]
    return [1, 2]

# ===== 八、登录与滑块 =====

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
    version_code = str(d.get("version_code") or "8520888")
    if version_code in {"", "417", "0888"}:
        version_code = "8520888"
    osversion = str(d.get("osversion") or f"Android 28 {version} {version_code}")
    if osversion.endswith(" 417") or " 417" in osversion:
        osversion = f"Android 28 {version} {version_code}"
    params = {"referer":"http://android.qidian.com","appid":"1450000219","areaid":"1","auto":"1","autotime":"30","ticket":"0","format":"json","signature":默认YW签名,"source":d.get("source") or "00000","version":version,"devicetype":d.get("devicetype") or "OnePlus_GM1910","devicename":"GM1910","returnurl":"http://www.qidian.com","osversion":osversion,"sdkversion":默认YW_SDK,"ibex":d.get("ibex") or 默认IBEX}
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
        if not isinstance(obj, dict):
            continue
        ywguid = (
            obj.get("ywGuid")
            or obj.get("ywguid")
            or obj.get("login_uin")
            or obj.get("uid")
            or obj.get("YWGuid")
        )
        ywkey = (
            obj.get("ywKey")
            or obj.get("ywkey")
            or obj.get("login_key")
            or obj.get("YWKey")
        )
        if ywguid and ywkey:
            清洗 = dict(obj)
            清洗["ywguid"] = str(ywguid)
            清洗["ywkey"] = str(ywkey)
            清洗["ywGuid"] = str(ywguid)
            清洗["ywKey"] = str(ywkey)
            if obj.get("ticket") is not None:
                清洗["ticket"] = str(obj.get("ticket"))
            if obj.get("autoLoginSessionKey") is not None:
                清洗["autoLoginSessionKey"] = str(obj.get("autoLoginSessionKey"))
            return 清洗
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
    if ticket:
        out["sig"] = ticket
        out["ticket"] = ticket
        out["captchaticket"] = ticket
    if randstr:
        out["code"] = randstr
        out["randstr"] = randstr
        out["captcharandstr"] = randstr
    return out

def 从登录载荷构造登录态(payload: Mapping[str, Any], phone: str = "") -> Dict[str, str]:
    ywguid = str(
        payload.get("ywGuid")
        or payload.get("ywguid")
        or payload.get("login_uin")
        or payload.get("uid")
        or ""
    )
    ywkey = str(
        payload.get("ywKey")
        or payload.get("ywkey")
        or payload.get("login_key")
        or ""
    )
    fuid = str(payload.get("fuid") or 默认设备.get("fuid") or "")
    cookie = str(payload.get("Cookie") or payload.get("cookie") or "")
    if not cookie and ywguid and ywkey:
        cookie = f"ywguid={ywguid}; ywkey={ywkey};"
    out = {
        "User-Agent": 默认UA,
        "login_type": "2",
        "ywguid": ywguid,
        "ywkey": ywkey,
        "uid": ywguid,
        "Cookie": cookie,
        "fuid": fuid,
        "qimei": 默认设备.get("qimei", ""),
        "qimei36": 默认设备.get("qimei36", ""),
        "ibex": 默认设备.get("ibex", ""),
    }
    if phone:
        out["phone"] = phone
    for key in ("ticket", "autoLoginSessionKey", "autoLoginKeepTime", "autoLoginExpiredTime", "ywOpenId", "alk", "alkts", "qrsn"):
        if payload.get(key) not in (None, ""):
            out[key] = str(payload.get(key))
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
function postResult(payload){{fetch(CB,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload||{{}})}}).then(function(r){{if(r&&r.ok&&payload&&Number(payload.ret)===0&&payload.ticket){{setStatus('ok','验证成功，请返回QQ发送：完成');}}else{{setStatus('bad','回传失败，请检查端口放行后重试');}}}}).catch(function(){{setStatus('bad','回传失败，请检查端口放行后重试');}});}}
function start(){{setStatus('busy','验证中…'); try{{const captcha=new TencentCaptcha(APPID,function(res){{const payload={{ret:res&&res.ret,ticket:(res&&res.ticket)||'',randstr:(res&&res.randstr)||'',time:Date.now()/1000}}; if(Number(payload.ret)===0&&payload.ticket){{setStatus('busy','验证中…'); postResult(payload);}} else setStatus('bad','验证失败，请重试');}},{{}}); captcha.show();}}catch(e){{setStatus('bad','验证失败，请重试');}}}}
btn.addEventListener('click',start); retry.addEventListener('click',start); setTimeout(start,400);
</script></body></html>"""

def 启动滑块本地服务(*, host: str = "0.0.0.0", port: int = 默认滑块端口, timeout: int = 滑块服务保留秒数, public_host: str = "") -> Dict[str, Any]:
    """启动滑块页服务：监听 0.0.0.0，自动获取公网 IP；只使用固定端口段，避免跳到未放行随机端口。"""
    result: Dict[str, Any] = {}
    done = threading.Event()
    closed = threading.Event()
    page_html = ""
    保留秒数 = max(30, int(timeout or 滑块服务保留秒数))
    绑定主机 = str(host or "0.0.0.0").strip() or "0.0.0.0"
    访问主机 = str(public_host or "").strip() or 获取滑块公网主机()
    访问主机 = 访问主机.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip()
    if not _是公网IPv4(访问主机):
        raise RuntimeError("未能自动获取服务器公网IP")

    class 可复用HTTPServer(HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send(self, code: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._send(204, b"")

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/captcha", "/", "/health", "/ping"):
                if path in ("/health", "/ping"):
                    self._send(200, b"ok")
                    return
                self._send(200, page_html.encode("utf-8"), "text/html; charset=utf-8")
                return
            self._send(404, b"not found")

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path not in ("/captcha", "/"):
                self._send(404, b"not found")
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                payload = {}
            if isinstance(payload, dict) and payload.get("ticket"):
                result.update(payload)
                done.set()
                self._send(200, b"ok")
            else:
                self._send(400, b"bad")

    端口列表: list[int] = []
    for p in (port, *滑块备用端口):
        try:
            n = int(p)
        except Exception:
            continue
        if n > 0 and n not in 端口列表:
            端口列表.append(n)
    if not 端口列表:
        端口列表 = [默认滑块端口]

    httpd = None
    last_error: Exception | None = None
    for 尝试端口 in 端口列表:
        try:
            httpd = 可复用HTTPServer((绑定主机, 尝试端口), Handler)
            break
        except OSError as e:
            last_error = e
            logger.warning(f"QQ阅读滑块端口不可用：host={绑定主机}, port={尝试端口}, error={e}")
            continue
    if httpd is None:
        raise RuntimeError(f"滑块端口都被占用，请释放 {端口列表[0]}-{端口列表[-1]} 后重试: {last_error}")

    actual_port = int(httpd.server_address[1])
    callback_url = f"http://{访问主机}:{actual_port}/captcha"
    page_html = 生成滑块HTML(callback_url=callback_url)

    def _关闭服务() -> None:
        if closed.is_set():
            return
        closed.set()
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass
        logger.info(f"QQ阅读滑块本地服务已关闭：url={callback_url}")

    def _自动关闭() -> None:
        done.wait(timeout=保留秒数)
        _关闭服务()

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    threading.Thread(target=_自动关闭, daemon=True).start()
    logger.info(f"QQ阅读滑块本地服务已启动：bind={绑定主机}:{actual_port}, url={callback_url}, keep={保留秒数}s")
    return {
        "url": callback_url,
        "bind": f"{绑定主机}:{actual_port}",
        "port": actual_port,
        "public_host": 访问主机,
        "result": result,
        "done": done,
        "closed": closed,
        "close": _关闭服务,
        "expires_at": time.time() + 保留秒数,
        "ticket": "",
        "randstr": "",
    }

def 关闭滑块服务(会话: Optional[Mapping[str, Any]] = None, 滑块: Optional[Mapping[str, Any]] = None) -> None:
    对象 = 滑块 or (会话 or {}).get("captcha") or {}
    close = 对象.get("close") if isinstance(对象, Mapping) else None
    if callable(close):
        try:
            close()
        except Exception as e:
            logger.warning(f"QQ阅读滑块服务关闭失败：error={e}")

async def 完成QQ阅读滑块验证(会话: dict[str, Any], 配置: Any) -> Tuple[bool, str]:
    滑块 = 会话.get("captcha") if isinstance(会话.get("captcha"), dict) else {}
    done = 滑块.get("done")
    result = 滑块.get("result") if isinstance(滑块.get("result"), dict) else {}
    过期时间 = float(滑块.get("expires_at") or 会话.get("expires_at") or 0)
    链接 = str(滑块.get("url") or "")
    if 过期时间 and time.time() > 过期时间 and not (isinstance(done, threading.Event) and done.is_set()):
        关闭滑块服务(会话=会话)
        return False, "安全验证已过期，请重新发送 登录QQ阅读"
    if not (isinstance(done, threading.Event) and done.is_set() and result.get("ticket")):
        if 链接:
            return False, f"请先点击链接完成安全验证（5分钟内有效）：\n{链接}\n完成后发送：完成\n发送 0 取消"
        return False, "请先完成安全验证，或发送 0 取消"
    ticket = str(result.get("ticket") or "")
    randstr = str(result.get("randstr") or "")
    滑块["ticket"] = ticket
    滑块["randstr"] = randstr
    会话["captcha"] = 滑块
    try:
        async with aiohttp.ClientSession() as 会话http:
            结果 = await 发送手机验证码(
                会话http,
                str(会话.get("phone") or ""),
                ticket=ticket,
                randstr=randstr,
                session_key=str(会话.get("session_key") or ""),
                登录态=读取QQ阅读登录态(配置),
            )
    except Exception as e:
        logger.warning(f"QQ阅读滑块后发短信失败：error={e}")
        关闭滑块服务(会话=会话)
        return False, 登录失败提示
    if not 结果.get("success"):
        logger.warning(f"QQ阅读滑块后发短信失败：resp={限制文本长度(结果.get('response'), 200)}")
        关闭滑块服务(会话=会话)
        return False, 登录失败提示
    关闭滑块服务(会话=会话)
    会话.update({
        "step": "code",
        "session_key": 结果.get("session_key") or 会话.get("session_key") or "",
        "phone": 结果.get("phone") or 会话.get("phone"),
        "ts": time.time(),
        "captcha": None,
    })
    return True, "验证成功，请发送短信验证码\n发送 0 取消"

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

# ===== 九、文件生成与发送 =====

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
    return "\n".join([
        f"书名：{书籍信息.get('title') or '未知'}",
        f"作者：{书籍信息.get('author') or '未知'}",
        f"状态：{书籍信息.get('status') or '未知'}",
        f"章节：{章节数} 章",
        f"字数：{格式化字数(书籍信息.get('word_count'))}",
        "",
        "正在下载中请稍等.....",
    ])

def 生成小说文件名(书籍信息: dict[str, Any]) -> str:
    状态 = str(书籍信息.get("status") or "")
    前缀 = "[完结]" if "完结" in 状态 or "完本" in 状态 else "[连载]"
    书名 = re.sub(r'[\\/:*?"<>|]', "_", str(书籍信息.get("title") or "未知书名"))
    作者 = re.sub(r'[\\/:*?"<>|]', "_", str(书籍信息.get("author") or "未知"))
    return f"{前缀}书名：{书名} 作者：{作者}.txt"

def 构造TXT文件(书籍编号: str, 书籍信息: dict[str, Any], 章节结果列表: list[dict[str, Any]]) -> tuple[str, bytes]:
    文件名 = 生成小说文件名(书籍信息)
    成功章节 = [项目 for 项目 in 章节结果列表 if str(项目.get("content") or "").strip()]
    行 = [
        免责声明,
        "",
        f"名称：{书籍信息.get('title') or '未知'}",
        f"作者：{书籍信息.get('author') or '未知'}",
        f"状态：{书籍信息.get('status') or '未知'}",
        f"字数：{格式化字数(书籍信息.get('word_count'))}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(成功章节)}",
        "",
    ]
    for 项目 in 成功章节:
        标题 = 清理文本(项目.get("title") or f"第{项目.get('index')}章")
        正文 = str(项目.get("content") or "").strip()
        行.append(标题)
        行.append("")
        行.append(正文)
        行.append("")
    return 文件名, "\n".join(行).encode("utf-8")

def 写入下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    下载缓存目录.mkdir(parents=True, exist_ok=True)
    路径 = 下载缓存目录 / 文件名; 路径.write_bytes(文件内容); return 路径

def 删除QQ阅读缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    try:
        Path(缓存路径).unlink(missing_ok=True)
        logger.info(f"QQ阅读下载缓存文件已删除：file={缓存路径}")
    except Exception as e:
        logger.warning(f"QQ阅读下载缓存文件删除失败：file={缓存路径}, error={e}")

def 启动QQ阅读百度后台上传并清理源文件(配置: Any, 源缓存路径: Any, 文件名: str) -> None:
    if not 源缓存路径:
        return

    async def 执行上传并清理() -> None:
        try:
            if 百度网盘 is not None:
                百度结果 = await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
                if 百度结果.get("success"):
                    logger.info(f"QQ阅读百度网盘后台上传成功：file={文件名}, fs_id={百度结果.get('file_id')}")
                elif 百度结果.get("skipped"):
                    logger.info(f"QQ阅读百度网盘后台上传按状态规则跳过：file={文件名}")
                elif 百度结果.get("enabled"):
                    logger.warning(f"QQ阅读百度网盘后台上传失败，不影响QQ发送：file={文件名}, error={百度结果.get('error')}")
        except Exception as e:
            logger.warning(f"QQ阅读百度网盘后台上传异常，不影响QQ发送：file={文件名}, error={e}")
        finally:
            删除QQ阅读缓存文件(源缓存路径)

    try:
        asyncio.create_task(执行上传并清理())
    except RuntimeError:
        删除QQ阅读缓存文件(源缓存路径)

async def 准备发送文本文件(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    缓存路径 = 写入下载缓存文件(文件名, 文件内容)
    logger.info(f"QQ阅读准备上传：file={文件名}, size={len(文件内容)}")
    if UC网盘 is None:
        删除QQ阅读缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "UC网盘模块未加载"}
    try:
        UC结果 = await UC网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        if not UC结果.get("success"):
            logger.warning(f"QQ阅读UC网盘上传失败：file={文件名}, error={UC结果.get('error')}")
            删除QQ阅读缓存文件(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(UC结果.get("error") or "UC网盘未启用")}
        完成结果 = await UC网盘.发送小说下载完成链接(event, 书名, 作者, str(UC结果.get("share_url") or ""))
        if 完成结果.get("sent"):
            logger.info(f"QQ阅读UC网盘上传并发送完成按钮成功：file={文件名}")
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 缓存路径, "error": str(完成结果.get("error") or "")}
        删除QQ阅读缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(完成结果.get("error") or "完成按钮发送失败")}
    except Exception as e:
        logger.warning(f"QQ阅读UC网盘上传或完成消息发送失败：file={文件名}, error={e}")
        删除QQ阅读缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(e)}

# ===== 十、链接识别与入口 =====

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
    return 生成本地下载回复流(event, 来源, 配置)

# ===== 十一、章节下载流程 =====

async def 下载全书批量(
    session: aiohttp.ClientSession,
    书籍编号: str,
    目录: list[dict[str, Any]],
    登录态: dict[str, str],
    *,
    text_types: Optional[Sequence[int]] = None,
    ad_state: Optional[int] = None,
) -> list[dict[str, Any]]:
    """按大批量(默认最多500章/批)拆分，动态并发请求。"""
    if not 目录:
        return []
    下载态 = 组装本地下载态(登录态)
    类型候选 = [int(x) for x in (text_types or (1, 2))]
    总数 = len(目录)
    每批 = max(1, min(批量章节上限, 总数))
    分批 = []
    i = 0
    for s in range(0, 总数, 每批):
        e = min(总数, s + 每批)
        分批.append((i, 目录[s:e]))
        i += 1
    并发 = max(1, min(批量并发上限, len(分批)))
    信号量 = asyncio.Semaphore(并发)
    结果映射: dict[int, list[dict[str, Any]]] = {}
    已完成 = 0
    成功累计 = 0
    失败累计 = 0
    上次日志进度 = 0
    进度锁 = asyncio.Lock()
    logger.info(
        f"QQ阅读章节进度：book_id={书籍编号}, progress=0/{总数}, percent=0%, "
        f"batches={len(分批)}, batch_size={每批}, concurrency={并发}"
    )

    async def 记录进度(完成增量: int, 成功增量: int) -> None:
        nonlocal 已完成, 成功累计, 失败累计, 上次日志进度
        async with 进度锁:
            已完成 += 完成增量
            成功累计 += 成功增量
            失败累计 += max(完成增量 - 成功增量, 0)
            当前进度 = 进度日志分段数 if 已完成 >= 总数 else int(已完成 * 进度日志分段数 / 总数)
            if 当前进度 <= 上次日志进度 and 已完成 < 总数:
                return
            上次日志进度 = 当前进度
            百分比 = int(已完成 * 100 / 总数) if 总数 else 100
            logger.info(
                f"QQ阅读章节进度：book_id={书籍编号}, "
                f"progress={已完成}/{总数}, percent={百分比}%, success={成功累计}, failed={失败累计}"
            )

    async def 下载一批(序号: int, 批次: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        async with 信号量:
            if not 批次:
                return 序号, []
            起始 = 安全整数(批次[0].get("index")) or (序号 * 每批 + 1)
            结束 = 安全整数(批次[-1].get("index")) or (起始 + len(批次) - 1)
            scids = str(起始) if 起始 == 结束 else f"{起始}-{结束}"
            最后异常 = None
            for text_type in 类型候选:
                最佳结果: list[dict[str, Any]] | None = None
                最佳成功 = -1
                for 尝试 in range(1, 正文解密重试次数 + 1):
                    try:
                        blob = await 请求批量包(
                            session, 书籍编号, scids, 登录态=下载态,
                            text_type=text_type, useindex=False, usepreview=0,
                            ad_state=ad_state, timeout=180,
                        )
                        if 是否deny(blob):
                            raise RuntimeError("批量接口拒绝")
                        entries = 解析tar(blob)
                        chaps = 章节成员(entries, 书籍编号)
                        by_cid = {章节编号(e.name, 书籍编号): e for e in chaps}
                        结果: list[dict[str, Any]] = []
                        成功数 = 0
                        空文件 = 0
                        密文文件 = 0
                        解密失败 = 0
                        for j, 章节 in enumerate(批次):
                            cid = str(章节.get("cid") or 章节.get("id") or 章节.get("index") or "")
                            标题 = 清理文本(章节.get("title") or f"第{章节.get('index')}章")
                            e = by_cid.get(cid)
                            if e is None and len(chaps) == len(批次):
                                e = chaps[j]
                            if e is None or not e.data:
                                空文件 += 1
                                结果.append({**章节, "title": 标题, "content": "", "success": False})
                                continue
                            if 是否二进制(e.data):
                                密文文件 += 1
                            正文, note = 解密章节(e.data, 书籍编号, cid, 下载态)
                            if 正文:
                                成功数 += 1
                                结果.append({**章节, "title": 标题, "content": 正文, "success": True})
                            else:
                                解密失败 += 1
                                if 尝试 == 正文解密重试次数:
                                    logger.debug(
                                        f"QQ阅读章节解密失败：book_id={书籍编号}, cid={cid}, note={限制文本长度(note, 80)}"
                                    )
                                结果.append({**章节, "title": 标题, "content": "", "success": False})
                        logger.debug(
                            f"QQ阅读批次完成：book_id={书籍编号}, batch={序号+1}/{len(分批)}, range={起始}-{结束}, "
                            f"text_type={text_type}, try={尝试}/{正文解密重试次数}, success={成功数}/{len(批次)}, "
                            f"tar_files={len(chaps)}, empty={空文件}, binary={密文文件}, decrypt_fail={解密失败}"
                        )
                        if 成功数 > 最佳成功:
                            最佳成功 = 成功数
                            最佳结果 = 结果
                        if 成功数 == len(批次):
                            return 序号, 结果
                        # 完全没有章节文件：当前 text_type/权限下不可下，直接换类型
                        if len(chaps) == 0:
                            break
                        # 有密文但解不开：重拉（服务端密文形态会在 b480/1bdccb 间抖动）
                        if 密文文件 > 0 and 成功数 < 密文文件:
                            continue
                        # 本 text_type 已有部分成功：记录后换下一个 text_type 试更高成功率
                        # 注意：绝不能在 type=1 只有 1 章成功时就 return，否则会错过 type=2 的 190+ 章
                        break
                    except Exception as e:
                        最后异常 = e
                        logger.debug(
                            f"QQ阅读批次重试：book_id={书籍编号}, batch={序号+1}/{len(分批)}, "
                            f"range={起始}-{结束}, text_type={text_type}, try={尝试}, error={e}"
                        )
            # 所有 text_type 试完后取成功率最高的结果
            if 最佳成功 > 0 and 最佳结果 is not None:
                return 序号, 最佳结果
            if 最后异常:
                logger.warning(f"QQ阅读批次最终失败：book_id={书籍编号}, range={起始}-{结束}, error={最后异常}")
            return 序号, [{**章节, "title": 清理文本(章节.get("title")), "content": "", "success": False} for 章节 in 批次]

    任务 = [asyncio.create_task(下载一批(i, batch)) for i, batch in 分批]
    for fut in asyncio.as_completed(任务):
        序号, 数据 = await fut
        结果映射[序号] = 数据
        成功增量 = sum(1 for x in 数据 if x.get("success"))
        await 记录进度(len(数据), 成功增量)
    合并: list[dict[str, Any]] = []
    for i, _ in 分批:
        合并.extend(结果映射.get(i) or [])
    成功 = sum(1 for x in 合并 if x.get("success"))
    logger.info(
        f"QQ阅读章节下载完成：book_id={书籍编号}, success={成功}, total={总数}, file_ready={成功 == 总数}"
    )
    return 合并

async def 下载单章正文(
    session: aiohttp.ClientSession,
    书籍编号: str,
    章节: dict[str, Any],
    下载态: dict[str, str],
    *,
    text_types: Optional[Sequence[int]] = None,
    ad_state: Optional[int] = None,
) -> dict[str, Any]:
    """缺章定向补拉：单章 scids + text_type 有限重试。"""
    索引 = 安全整数(章节.get("index")) or 0
    cid = str(章节.get("cid") or 章节.get("id") or 索引 or "")
    标题 = 清理文本(章节.get("title") or f"第{索引}章")
    if not 索引 and not cid:
        return {**章节, "title": 标题, "content": "", "success": False}
    scids = str(索引) if 索引 else cid
    最佳正文 = ""
    for text_type in [int(x) for x in (text_types or (1, 2))]:
        for 尝试 in range(1, 正文解密重试次数 + 1):
            try:
                blob = await 请求批量包(
                    session, 书籍编号, scids, 登录态=下载态,
                    text_type=text_type, useindex=False, usepreview=0,
                    ad_state=ad_state, timeout=90,
                )
                if 是否deny(blob):
                    break
                entries = 解析tar(blob)
                chaps = 章节成员(entries, 书籍编号)
                e = None
                by_cid = {章节编号(x.name, 书籍编号): x for x in chaps}
                if cid:
                    e = by_cid.get(cid)
                if e is None and chaps:
                    e = chaps[0]
                if e is None or not e.data:
                    continue
                正文, note = 解密章节(e.data, 书籍编号, cid or 章节编号(e.name, 书籍编号), 下载态)
                if 正文:
                    return {**章节, "title": 标题, "content": 正文, "success": True}
                logger.debug(
                    f"QQ阅读缺章补拉解密失败：book_id={书籍编号}, index={索引}, cid={cid}, "
                    f"text_type={text_type}, try={尝试}, note={限制文本长度(note, 60)}"
                )
            except Exception as e:
                logger.debug(
                    f"QQ阅读缺章补拉重试：book_id={书籍编号}, index={索引}, cid={cid}, "
                    f"text_type={text_type}, try={尝试}, error={e}"
                )
    return {**章节, "title": 标题, "content": 最佳正文, "success": bool(最佳正文)}

async def 补拉缺失章节(
    session: aiohttp.ClientSession,
    书籍编号: str,
    结果列表: list[dict[str, Any]],
    登录态: dict[str, str],
    *,
    text_types: Optional[Sequence[int]] = None,
    ad_state: Optional[int] = None,
) -> list[dict[str, Any]]:
    """主批量后对失败章做有限轮次单章补拉，不无限循环。"""
    if not 结果列表:
        return 结果列表
    下载态 = 组装本地下载态(登录态)
    合并 = list(结果列表)
    for 轮次 in range(1, 缺章补拉轮次 + 1):
        缺失索引 = [i for i, x in enumerate(合并) if not x.get("success") or not str(x.get("content") or "").strip()]
        if not 缺失索引:
            break
        logger.info(
            f"QQ阅读缺章补拉：book_id={书籍编号}, round={轮次}/{缺章补拉轮次}, "
            f"missing={len(缺失索引)}, concurrency={缺章补拉并发}"
        )
        # 第 1 轮：把缺失章按连续 index 合成小批（最多 20）重拉，比单章快且更容易拿到可解密密文
        if 轮次 == 1 and len(缺失索引) > 1:
            缺失章 = [(i, 合并[i]) for i in 缺失索引]
            缺失章.sort(key=lambda x: 安全整数(x[1].get("index")) or 0)
            小批列表: list[list[tuple[int, dict[str, Any]]]] = []
            当前批: list[tuple[int, dict[str, Any]]] = []
            上一索引 = None
            for item in 缺失章:
                idx = 安全整数(item[1].get("index")) or 0
                if not 当前批:
                    当前批 = [item]
                elif 上一索引 is not None and idx == 上一索引 + 1 and len(当前批) < 20:
                    当前批.append(item)
                else:
                    小批列表.append(当前批)
                    当前批 = [item]
                上一索引 = idx
            if 当前批:
                小批列表.append(当前批)
            信号量 = asyncio.Semaphore(min(缺章补拉并发, max(1, len(小批列表))))

            async def 补一小批(组: list[tuple[int, dict[str, Any]]]) -> list[tuple[int, dict[str, Any]]]:
                async with 信号量:
                    章节们 = [x[1] for x in 组]
                    起始 = 安全整数(章节们[0].get("index")) or 0
                    结束 = 安全整数(章节们[-1].get("index")) or 起始
                    scids = str(起始) if 起始 == 结束 else f"{起始}-{结束}"
                    类型候选 = [int(x) for x in (text_types or (1, 2))]
                    最佳映射: dict[str, dict[str, Any]] = {}
                    最佳成功 = -1
                    for text_type in 类型候选:
                        for 尝试 in range(1, 正文解密重试次数 + 1):
                            try:
                                blob = await 请求批量包(
                                    session, 书籍编号, scids, 登录态=下载态,
                                    text_type=text_type, useindex=False, usepreview=0,
                                    ad_state=ad_state, timeout=120,
                                )
                                if 是否deny(blob):
                                    break
                                chaps = 章节成员(解析tar(blob), 书籍编号)
                                by_cid = {章节编号(e.name, 书籍编号): e for e in chaps}
                                映射: dict[str, dict[str, Any]] = {}
                                成功数 = 0
                                密文 = 0
                                for 章节 in 章节们:
                                    cid = str(章节.get("cid") or 章节.get("id") or 章节.get("index") or "")
                                    标题 = 清理文本(章节.get("title") or f"第{章节.get('index')}章")
                                    e = by_cid.get(cid)
                                    if e is None and len(chaps) == len(章节们):
                                        # 按顺序兜底
                                        pos = 章节们.index(章节)
                                        e = chaps[pos] if pos < len(chaps) else None
                                    if e is None or not e.data:
                                        映射[cid] = {**章节, "title": 标题, "content": "", "success": False}
                                        continue
                                    if 是否二进制(e.data):
                                        密文 += 1
                                    正文, _note = 解密章节(e.data, 书籍编号, cid, 下载态)
                                    if 正文:
                                        成功数 += 1
                                        映射[cid] = {**章节, "title": 标题, "content": 正文, "success": True}
                                    else:
                                        映射[cid] = {**章节, "title": 标题, "content": "", "success": False}
                                if 成功数 > 最佳成功:
                                    最佳成功 = 成功数
                                    最佳映射 = 映射
                                if 成功数 == len(章节们):
                                    break
                                if 密文 > 0 and 成功数 < 密文:
                                    continue
                                break
                            except Exception:
                                continue
                        if 最佳成功 == len(章节们):
                            break
                    out = []
                    for 位置, 章节 in 组:
                        cid = str(章节.get("cid") or 章节.get("id") or 章节.get("index") or "")
                        新章 = 最佳映射.get(cid) or {**章节, "content": "", "success": False}
                        out.append((位置, 新章))
                    return out

            任务 = [asyncio.create_task(补一小批(g)) for g in 小批列表]
            本轮成功 = 0
            for fut in asyncio.as_completed(任务):
                for 位置, 新章 in await fut:
                    if 新章.get("success") and str(新章.get("content") or "").strip():
                        合并[位置] = 新章
                        本轮成功 += 1
        else:
            信号量 = asyncio.Semaphore(缺章补拉并发)

            async def 补一章(位置: int) -> tuple[int, dict[str, Any]]:
                async with 信号量:
                    章节 = 合并[位置]
                    新章 = await 下载单章正文(
                        session, 书籍编号, 章节, 下载态,
                        text_types=text_types, ad_state=ad_state,
                    )
                    return 位置, 新章

            任务 = [asyncio.create_task(补一章(i)) for i in 缺失索引]
            本轮成功 = 0
            for fut in asyncio.as_completed(任务):
                位置, 新章 = await fut
                if 新章.get("success") and str(新章.get("content") or "").strip():
                    合并[位置] = 新章
                    本轮成功 += 1
        仍缺 = sum(1 for x in 合并 if not x.get("success") or not str(x.get("content") or "").strip())
        logger.info(
            f"QQ阅读缺章补拉结果：book_id={书籍编号}, round={轮次}/{缺章补拉轮次}, "
            f"recovered={本轮成功}, still_missing={仍缺}"
        )
        if 仍缺 == 0 or 本轮成功 == 0:
            break
    return 合并

async def 生成本地下载回复流(event: Any, 来源: str, 配置: Any = None) -> AsyncIterator[Any]:
    书籍编号 = 解析书籍编号(来源)
    if not 书籍编号:
        logger.warning(f"QQ阅读本地下载失败：未识别书籍ID source={限制文本长度(来源)}")
        yield 下载失败提示; return
    登录态 = 组装本地下载态(读取QQ阅读登录态(配置))
    超时 = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=300)
    try:
        async with aiohttp.ClientSession(timeout=超时) as 会话:
            # 详情/目录走 App 接口；正文用设备 fuid，不强制账号登录
            try:
                详情 = await 请求书籍信息(会话, 书籍编号, 登录态)
            except Exception as e:
                logger.warning(f"QQ阅读详情失败：book_id={书籍编号}, error={e}")
                详情 = {}
            书籍信息 = 从详情提取书籍(详情, 书籍编号)
            try:
                目录 = await 请求目录(会话, 书籍编号, 登录态)
            except Exception as e:
                logger.warning(f"QQ阅读目录失败：book_id={书籍编号}, error={e}")
                目录 = []
            if not 目录:
                总数 = 安全整数(书籍信息.get("chapter_count"))
                if 总数 > 0:
                    目录 = [{"cid": str(i), "id": str(i), "title": f"第{i}章", "index": i} for i in range(1, 总数 + 1)]
            if not 目录:
                logger.warning(f"QQ阅读本地下载失败：无目录 book_id={书籍编号}"); yield 下载失败提示; return
            for i, ch in enumerate(目录, start=1):
                ch["index"] = 安全整数(ch.get("index")) or i
            有账号 = bool(登录态.get("ywguid") and 登录态.get("ywkey"))
            免费章上限 = 安全整数(书籍信息.get("max_free_chapter"))
            全书免费 = 是否全书免费可下(书籍信息, 详情) or bool(书籍信息.get("is_all_free"))
            是广告书 = bool(书籍信息.get("is_ad_book"))
            # 广告全本/整本免费：游客 adState=0。部分免费广告书也先用游客探测，再决定是否收费。
            if 全书免费 or 是广告书:
                下载态 = 组装游客下载态(登录态)
                ad_state = 0
                模式 = "guest"
            else:
                下载态 = 组装本地下载态(登录态)
                ad_state = 1 if 有账号 else 0
                模式 = "login" if 有账号 else "device"
            类型候选 = 识别正文类型(详情, 书籍信息)

            if 全书免费:
                # 真全免：跳过探测，整本最快下载
                下载目录 = list(目录)
                logger.debug(
                    f"QQ阅读跳过探测：book_id={书籍编号}, all_free=True, "
                    f"download={len(下载目录)}, mode={模式}"
                )
            else:
                # 详情已标明部分免费/试读：所有书统一直接收费，不硬下整本、不空转探测
                if 免费章上限 > 0 and len(目录) > 0 and 免费章上限 < len(目录):
                    logger.warning(
                        f"QQ阅读本地下载失败：详情部分免费 book_id={书籍编号}, "
                        f"maxfree={免费章上限}, catalog={len(目录)}, mode={模式}, has_account={有账号}"
                    )
                    yield 收费书提示
                    return
                # 其余非全免（含 VIP）：全量探测实际可下章
                可下编号 = await 探测可下载章节编号(
                    会话, 书籍编号, 目录, 下载态, text_types=类型候选, ad_state=ad_state,
                )
                下载目录 = [
                    ch for ch in 目录
                    if str(ch.get("cid") or ch.get("id") or ch.get("index") or "") in 可下编号
                ]
                logger.info(
                    f"QQ阅读可下载探测：book_id={书籍编号}, authorized={len(下载目录)}, "
                    f"catalog={len(目录)}, maxfree={免费章上限}, mode={模式}, has_account={有账号}"
                )
                if not 下载目录:
                    logger.warning(
                        f"QQ阅读本地下载失败：无可下载章节 book_id={书籍编号}, maxfree={免费章上限}, "
                        f"mode={模式}, has_account={有账号}"
                    )
                    yield 收费书提示
                    return
                # 只能下部分章：按收费书处理，不硬下整本
                if len(下载目录) < len(目录):
                    logger.warning(
                        f"QQ阅读本地下载失败：收费/VIP书仅部分可下 book_id={书籍编号}, "
                        f"authorized={len(下载目录)}, catalog={len(目录)}, maxfree={免费章上限}, has_account={有账号}"
                    )
                    yield 收费书提示
                    return

            书籍信息["chapter_count"] = len(目录)
            logger.info(
                f"QQ阅读开始下载：source=local, book_id={书籍编号}, title={书籍信息.get('title')}, "
                f"author={书籍信息.get('author')}, status={书籍信息.get('status')}, "
                f"words={书籍信息.get('word_count')}, chapters={len(目录)}, download_chapters={len(下载目录)}, "
                f"mode={模式}, all_free={全书免费}, text_types={list(类型候选)}, has_account={有账号}"
            )
            yield 格式化下载提示(书籍信息, len(目录))

            # 全免游客整本下载；VIP 付费书籍需要登录态。
            章节结果 = await 下载全书批量(
                会话, 书籍编号, 下载目录, 下载态,
                text_types=类型候选, ad_state=ad_state,
            )
            缺少数 = sum(1 for x in 章节结果 if not x.get("success") or not str(x.get("content") or "").strip())
            if 缺少数:
                章节结果 = await 补拉缺失章节(
                    会话, 书籍编号, 章节结果, 下载态,
                    text_types=类型候选, ad_state=ad_state,
                )
            成功列表 = [x for x in 章节结果 if x.get("success") and str(x.get("content") or "").strip()]
            if not 成功列表 or len(成功列表) < len(下载目录):
                logger.warning(
                    f"QQ阅读本地下载失败：book_id={书籍编号}, success={len(成功列表)}, total={len(下载目录)}, "
                    f"catalog_total={len(目录)}, mode={模式}, has_account={有账号}"
                )
                if (not 全书免费) and len(成功列表) < len(目录):
                    yield 收费书提示
                else:
                    yield 下载失败提示
                return
            文件名, 文件内容 = 构造TXT文件(书籍编号, 书籍信息, 章节结果)
            logger.info(f"QQ阅读章节下载完成：book_id={书籍编号}, title={书籍信息.get('title')}, success={len(成功列表)}, total={len(目录)}, file_size={len(文件内容)}")
            发送结果 = await 准备发送文本文件(
                event,
                文件名,
                文件内容,
                配置,
                书名=书籍信息.get("title"),
                作者=书籍信息.get("author"),
            )
            if 发送结果.get("sent"):
                启动QQ阅读百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
                return
            降级文本 = str(发送结果.get("fallback_text") or "")
            if 降级文本:
                try:
                    yield 降级文本
                finally:
                    启动QQ阅读百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
                return
            logger.warning(f"QQ阅读文件发送失败：book_id={书籍编号}, file={文件名}, error={发送结果.get('error')}")
            yield 文件发送失败提示
    except Exception as e:
        logger.warning(f"QQ阅读本地下载失败：book_id={书籍编号}, error={e}"); yield 下载失败提示

# ===== 十二、登录指令 =====

def 清理过期登录会话() -> None:
    现在 = time.time()
    for k in [k for k, v in 待登录会话.items() if 现在 - float(v.get("ts") or 0) > 登录会话等待秒数]:
        关闭滑块服务(会话=待登录会话.get(k))
        待登录会话.pop(k, None)

async def 处理QQ阅读登录指令(event: Any, 命令文本: str, 配置: Any) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None
    清理过期登录会话()
    会话键 = 获取会话键(event)
    if 文本 in ("登录QQ阅读", "qq阅读登录", "QQ阅读登录"):
        if not 是群文件清理管理员(event, 配置):
            return "没有权限登录QQ阅读"
        旧会话 = 待登录会话.pop(会话键, None)
        关闭滑块服务(会话=旧会话)
        待登录会话[会话键] = {"step": "phone", "ts": time.time()}
        return "请发送手机号（仅支持中国大陆手机号）" + chr(10) + "发送 0 取消"
    会话 = 待登录会话.get(会话键)
    if not 会话:
        return None
    if not 是群文件清理管理员(event, 配置):
        关闭滑块服务(会话=会话)
        待登录会话.pop(会话键, None)
        return "没有权限登录QQ阅读"
    if 文本 in {"0", "取消", "返回", "返回上一步"}:
        关闭滑块服务(会话=会话)
        待登录会话.pop(会话键, None)
        return "已取消QQ阅读登录"
    步骤 = str(会话.get("step") or "")
    if 步骤 == "phone":
        号码 = 文本.replace(" ", "")
        if 号码.startswith("+86"):
            号码 = 号码[3:]
        if 号码.startswith("86") and len(号码) == 13:
            号码 = 号码[2:]
        if not 手机号正则.fullmatch(号码):
            return "手机号格式不正确，请重新发送" + chr(10) + "发送 0 取消"
        try:
            async with aiohttp.ClientSession() as 会话http:
                结果 = await 发送手机验证码(会话http, 号码, 登录态=读取QQ阅读登录态(配置))
        except Exception as e:
            logger.warning(f"QQ阅读发短信失败：error={e}")
            return 登录失败提示
        if 结果.get("need_captcha"):
            try:
                滑块 = await asyncio.to_thread(启动滑块本地服务, timeout=滑块服务保留秒数)
            except Exception as e:
                logger.warning(f"QQ阅读滑块服务启动失败：error={e}")
                待登录会话.pop(会话键, None)
                err = str(e or "")
                if "公网IP" in err:
                    return "无法获取服务器公网地址，请检查服务器网络"
                return 登录失败提示
            会话.update({
                "step": "captcha_wait",
                "phone": 结果.get("phone") or 号码,
                "session_key": 结果.get("session_key") or "",
                "captcha": 滑块,
                "expires_at": float(滑块.get("expires_at") or (time.time() + 滑块服务保留秒数)),
                "ts": time.time(),
            })
            待登录会话[会话键] = 会话
            链接 = str(滑块.get("url") or "")
            logger.info(f"QQ阅读滑块链接已下发：url={链接}")
            端口 = str((滑块 or {}).get("port") or 默认滑块端口)
            主机 = str((滑块 or {}).get("public_host") or "")
            if not 链接.startswith("http://") and not 链接.startswith("https://"):
                链接 = "http://" + 链接
            # 私网地址直接失败，避免发打不开的链接
            if 主机 and not _是公网IPv4(主机.split(":")[0]):
                关闭滑块服务(会话=会话)
                待登录会话.pop(会话键, None)
                logger.warning(f"QQ阅读滑块公网地址无效：host={主机}")
                return "无法获取服务器公网地址，请检查服务器网络"
            return (
                "请用手机浏览器打开链接完成验证（5分钟内有效）"
                + chr(10)
                + 链接
                + chr(10)
                + "若QQ内打不开，请复制到浏览器"
                + chr(10)
                + "需放行端口 "
                + 端口
                + chr(10)
                + "完成后发送：完成"
                + chr(10)
                + "发送 0 取消"
            )
        if not 结果.get("success"):
            logger.warning(f"QQ阅读发短信失败：resp={限制文本长度(结果.get('response'),200)}")
            待登录会话.pop(会话键, None)
            return 登录失败提示
        会话.update({
            "step": "code",
            "phone": 结果.get("phone") or 号码,
            "session_key": 结果.get("session_key") or "",
            "ts": time.time(),
        })
        待登录会话[会话键] = 会话
        return "验证码已发送，请发送短信验证码" + chr(10) + "发送 0 取消"
    if 步骤 in ("captcha_wait", "captcha"):
        成功, 回复 = await 完成QQ阅读滑块验证(会话, 配置)
        if 成功:
            待登录会话[会话键] = 会话
            return 回复
        if "已过期" in 回复 or 回复 == 登录失败提示:
            待登录会话.pop(会话键, None)
        else:
            待登录会话[会话键] = 会话
        return 回复
    if 步骤 == "code":
        if not 验证码正则.fullmatch(文本):
            return "验证码格式不正确，请重新发送" + chr(10) + "发送 0 取消"
        try:
            async with aiohttp.ClientSession() as 会话http:
                结果 = await 提交手机验证码(
                    会话http,
                    str(会话.get("phone") or ""),
                    文本,
                    str(会话.get("session_key") or ""),
                    登录态=读取QQ阅读登录态(配置),
                )
        except Exception as e:
            logger.warning(f"QQ阅读验证码登录失败：error={e}")
            待登录会话.pop(会话键, None)
            return 登录失败提示
        if not 结果.get("success"):
            logger.warning(f"QQ阅读验证码登录失败：code={((结果.get('response') or {}) if isinstance(结果.get('response'), dict) else {}).get('code', '')}, has_payload={bool(结果.get('auth'))}, resp={限制文本长度(结果.get('response'),120)}")
            待登录会话.pop(会话键, None)
            return 登录失败提示
        try:
            写入QQ阅读登录态(配置, 结果.get("auth") or {})
        except Exception as e:
            logger.warning(f"QQ阅读登录态写入数据库失败：error={e}")
            待登录会话.pop(会话键, None)
            return 登录失败提示
        待登录会话.pop(会话键, None)
        return "QQ阅读登录成功"
    return None

