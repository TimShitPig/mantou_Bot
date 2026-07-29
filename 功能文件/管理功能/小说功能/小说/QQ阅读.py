from __future__ import annotations
import asyncio, base64, gzip, io, json, re, secrets, tarfile, threading, time, urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
import aiohttp
from astrbot.api import logger
from 功能文件.管理功能.基础功能.权限工具 import 是群文件清理管理员
from 功能文件.管理功能.基础功能.运行状态数据库 import 读取运行状态值, 写入运行状态值
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

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具

import hashlib
import zlib
from typing import Callable
try:
    from Crypto.Cipher import AES, DES
    from Crypto.Hash import MD2, MD4, MD5
    from Crypto.Util import Counter
    from Crypto.Util.Padding import unpad
except Exception as e:
    AES = DES = MD2 = MD4 = MD5 = Counter = unpad = None
    logger.warning(f"QQ阅读解密依赖加载失败：error={e}")

登录态命名空间="qq_reader_auth"; 登录态状态键="login_state"
登录会话等待秒数=300; 滑块服务保留秒数=300; 默认滑块端口=8765; 滑块备用端口=(8765,8766,8767,8768,8769,8770); 进度日志分段数=10
下载缓存目录=Path(__file__).resolve().parents[3]/"下载缓存"
免责声明="声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"
下载失败提示="下载失败"; 收费书提示="收费书籍不支持下载\n请下载VIP或者免费书"; 文件发送失败提示="文件发送失败，请稍后再试"; 登录失败提示="登录失败，请稍后再试"
详情地址="https://commontgw.reader.qq.com/book/queryBookInfo"
批量正文地址="https://newminerva-tgw.reader.qq.com/ChapBatAuthWithPD"
发短信地址="https://ptlogin.yuewen.com/sdk/sendphonecode"
验证码登录地址="https://ptlogin.yuewen.com/sdk/phonecodelogin"
默认UA="QQReaderAndroid/8.5.2.890"; App默认UA="okhttp/3.12.13"; 滑块AppId="1600000770"; 默认登录版本="8.5.2.890"; 登录协议版本号="8520888"
默认YW签名=("oMI3aDG4BEctqSrQUTmYDrBNwDYS744OQHMy9qWjqaf0xAI+9W9wtpd3VpfB "
"zyQl0baDZNuqwu5iI43zZe9+fXiErR7tkuMWqshGfT09oNnEtpPCrkYNFBwT "
"k+Faez58Fc442YO4kFw="); 默认YW_SDK="401"
默认IBEX=("n3Bl6YO_sAraVTVlp6JYHRIznI5tlwdCvgNDxWs6XmJfE3B8Erqx0l-pH-9Tm_b362BPtnuU3t4Pc5j_"
"MstRVEkFvuZCxW0ukz2AwnwljbDUDpuo81UrYQVIexitiw-UcBgx4YD2BQNiKid-uzBHqQTO94uFsH4Oc_"
"ZL-0ZkoTbc2KHy5Risa0iuPY4lSBGRzUaGdoG-wWIIKeRa43QW9OhJFK4ALX1V5XiHTyo-Xv-IGgnoZaTa8_"
"7h1zsHwPf2jIOeiWwYAhbdA5iirmZhwHHkHChmO9yp3n-NFn5q1A9b3hqJMPMacGAjdXKLBIBsIyiPTp-"
"iiRriFYjSwyXhzVLUdhYg_B5RNxCuXSlDKSF9E6RCOxVl5wAAFfB3vQbAjsHRSVak0KuFPoTHb3x7hVz0P"
"CupP82oZGMwZjU2NzJhYWI0ZGEwZTZjMjM2NDkyNDI5MThiMmY=")
默认App请求身份={
    "loginType":"50", "c_platform":"android", "c_version":"qqreader_8.3.3.0888_android",
    "channel":"10005136", "qrsn":"0022ece0af3ed4d0052148e33e8bce20ab31a706cf9af04b",
    "usid":"yw9GVpCYd7Lx", "uid":"900071413951", "fuid":"89306811035542cd868d49def7d3857d",
}
App签名尾部="B74H5a2Yh73gfu8F"; 密钥池缓存秒数=20 * 60
内存密钥池缓存: dict[str, tuple[float, str]] = {}
默认设备={"qimei":"0022ece0af3ed4d0052148e33e8bce20ab31a706cf9af04b","qimei36":"104a6cc03680b90a518e73db10001f31a706","source":"00000","version":默认登录版本,"version_code":"417","osversion":f"Android 28 {默认登录版本} 417","devicetype":"OnePlus_GM1910","ibex":默认IBEX,"sdkversion":默认YW_SDK,"fuid":默认App请求身份["fuid"]}
正文解密重试次数=4; 缺章补拉轮次=3; 缺章补拉并发=8; 批量章节上限=500; 批量并发上限=4
QQ阅读来源正则=re.compile(r"reader\.qq\.com|book\.qq\.com|novel\.html5\.qq\.com", re.I)
链接正则=re.compile(r"https?://[^\s'\"<>\u3001\uff0c\u3002]+", re.I)
手机号正则=re.compile(r"^1\d{10}$"); 验证码正则=re.compile(r"^\d{4,8}$")
QQ阅读Cookie命令正则 = re.compile(r"^(?:QQ阅读|qq阅读)(?:登录)?cookie\s+(.+)$", re.I | re.S)
QQ阅读Cookie状态命令 = {"QQ阅读cookie状态", "qq阅读cookie状态", "QQ阅读登录状态", "qq阅读登录状态"}
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

def 提取Cookie键值对(原始Cookie: Any) -> list[tuple[str, str]]:
    """兼容浏览器 Cookie、curl、Cookie Editor JSON 与 Netscape cookies.txt。"""
    文本 = str(原始Cookie or "").strip()
    if not 文本:
        return []

    键值对: list[tuple[str, str]] = []
    try:
        对象 = json.loads(文本)
    except Exception:
        对象 = None
    if isinstance(对象, dict):
        对象 = 对象.get("cookies") or 对象.get("Cookies") or 对象
    if isinstance(对象, list):
        for 项 in 对象:
            if isinstance(项, dict):
                名称 = str(项.get("name") or 项.get("Name") or "").strip()
                值 = str(项.get("value") or 项.get("Value") or "")
                if 名称:
                    键值对.append((名称, 值))
        if 键值对:
            return 键值对

    匹配 = re.search(r"(?:^|\s)(?:-H|--header)\s+['\"]?Cookie\s*:\s*([^'\"]+)", 文本, re.I)
    if 匹配:
        文本 = 匹配.group(1).strip()
    文本 = re.sub(r"^\s*Cookie\s*:\s*", "", 文本, flags=re.I).strip().strip("'\"")

    # Netscape cookies.txt：domain / flag / path / secure / expire / name / value
    for 行 in 文本.splitlines():
        行 = 行.strip()
        if not 行 or (行.startswith("#") and not 行.startswith("#HttpOnly_")):
            continue
        列 = 行.split("\t")
        if len(列) >= 7:
            名称, 值 = 列[-2].strip(), 列[-1].strip()
            if 名称:
                键值对.append((名称, 值))
    if 键值对:
        return 键值对

    for 项 in re.split(r";\s*", 文本.replace("\r", "").replace("\n", ";")):
        if "=" not in 项:
            continue
        名称, 值 = 项.split("=", 1)
        名称, 值 = 名称.strip(), 值.strip()
        if 名称:
            键值对.append((名称, 值))
    return 键值对


def 解析QQ阅读Cookie(原始Cookie: Any) -> dict[str, str]:
    """把外部 Cookie 统一成下载链路使用的登录态字段。"""
    键值对 = 提取Cookie键值对(原始Cookie)
    if not 键值对:
        return {}
    去重键值: dict[str, tuple[str, str]] = {}
    for 名称, 值 in 键值对:
        去重键值[名称.lower()] = (名称, 值)
    Cookie = "; ".join(f"{名称}={值}" for 名称, 值 in 去重键值.values())
    if Cookie:
        Cookie += ";"
    字段映射 = {
        "ywguid": "ywguid",
        "ywkey": "ywkey",
        "yw_guid": "ywguid",
        "yw_key": "ywkey",
        "qrsn": "qrsn",
        "fuid": "fuid",
        "uid": "uid",
        "login_uin": "login_uin",
        "login_key": "login_key",
        "ticket": "ticket",
        "autologinsessionkey": "autoLoginSessionKey",
    }
    结果 = {"Cookie": Cookie}
    for Cookie名, 字段名 in 字段映射.items():
        项 = 去重键值.get(Cookie名)
        if 项 and 项[1]:
            结果[字段名] = 项[1]
    if not 结果.get("uid") and 结果.get("ywguid"):
        结果["uid"] = 结果["ywguid"]
    if not 结果.get("login_uin") and 结果.get("ywguid"):
        结果["login_uin"] = 结果["ywguid"]
    if not 结果.get("login_key") and 结果.get("ywkey"):
        结果["login_key"] = 结果["ywkey"]
    return 结果


def 是QQ阅读Cookie文本(原始Cookie: Any) -> bool:
    """判断消息是否为可直接保存的 QQ 阅读登录 Cookie。"""
    登录态 = 解析QQ阅读Cookie(原始Cookie)
    有YW登录态 = bool(登录态.get("ywguid") and 登录态.get("ywkey"))
    有通用登录态 = bool(登录态.get("login_uin") and 登录态.get("login_key"))
    return 有YW登录态 or 有通用登录态


def 补齐QQ阅读登录态(登录态: Mapping[str, Any] | None) -> dict[str, str]:
    结果 = {str(k): str(v) for k, v in (登录态 or {}).items() if v not in (None, "")}
    Cookie登录态 = 解析QQ阅读Cookie(结果.get("Cookie") or 结果.get("cookie") or "")
    for 键, 值 in Cookie登录态.items():
        结果.setdefault(键, 值)
    if 结果.get("ywguid") and not 结果.get("uid"):
        结果["uid"] = 结果["ywguid"]
    if 结果.get("ywkey") and not 结果.get("login_key"):
        结果["login_key"] = 结果["ywkey"]
    return 结果


def 读取QQ阅读登录态(配置: Any) -> dict[str, str]:
    try:
        文本 = 读取运行状态值(配置, 登录态命名空间, 登录态状态键, "")
        if not 文本: return {}
        数据 = json.loads(文本)
        if isinstance(数据, dict):
            return 补齐QQ阅读登录态(数据)
    except Exception as e:
        logger.warning(f"QQ阅读登录态读取失败：error={e}")
    return {}

def 写入QQ阅读登录态(配置: Any, 登录态: dict[str, Any]) -> None:
    清洗 = 补齐QQ阅读登录态(登录态)
    for 字段名 in ("phone", "ticket", "autoLoginSessionKey", "autoLoginKeepTime", "autoLoginExpiredTime", "alk", "alkts"):
        清洗.pop(字段名, None)
    写入运行状态值(配置, 登录态命名空间, 登录态状态键, json.dumps(清洗, ensure_ascii=False))
    logger.info("QQ阅读登录态已保存到数据库")

# ===== 三、正文解密算法 =====

# --- libfock 多模式解密（原 _qq阅读解密） ---

KNVA_AES_KEY = b"c9ajudte0zb21ksg"
KNVA_AES_IV = b"58jb6v2lzcspwymg"
# 32B ciphertext @ SO/runtime file offset 0x15cf0
KNVA_CIPHERTEXT = bytes.fromhex(
    "8f400c5fcec88186569c7c407e35d289"
    "5495f9025321cd94976e786a65f18550"
)


# mode id (first 8 digits) -> name
MODE_AES_AES = 21123123
MODE_DES_AES = 21132184
MODE_CTR_DES = 29344484
MODE_AES_CTR = 29859828
MODE_DES_CTR = 31344423
MODE_AES_DES = 31932881
MODE_CTR_CTR = 34232881
MODE_DES_DES = 34941028
MODE_CTR_AES = 94859123

# fock_sn hash table order (runtime 0x1201efc8)
_SN_HASHES = (MD2, MD4, MD5)


def derive_knva(
    ciphertext: bytes = KNVA_CIPHERTEXT,
    key: bytes = KNVA_AES_KEY,
    iv: bytes = KNVA_AES_IV,
) -> bytes:
    """Recover knva from libfock embedded AES-128-CBC blob.

    Matches get_master @ runtime 0x1200ca48:
      key = "c9ajudte0zb21ksg", iv = "58jb6v2lzcspwymg", AES-128-CBC, PKCS7.
    """
    if len(ciphertext) % 16:
        raise ValueError("knva ciphertext length must be multiple of 16")
    pt = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(ciphertext)
    return unpad(pt, 16)


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= 16 and data.endswith(bytes([pad]) * pad):
        return data[:-pad]
    if data.endswith(b"\r"):
        return data.rstrip(b"\r")
    return data


def master_key(fuid: str | bytes, knva: bytes | None = None) -> bytes:
    if knva is None:
        knva = derive_knva()
    if isinstance(fuid, str):
        fuid_b = fuid.encode("utf-8")
    else:
        fuid_b = fuid
    if isinstance(knva, str):
        knva = knva.encode("ascii")
    return hashlib.sha256(fuid_b + knva).digest()


def decrypt_keypool(keypool: bytes, master: bytes) -> list[str]:
    if len(keypool) % 16:
        raise ValueError("keypool length must be multiple of 16")
    pt = AES.new(master, AES.MODE_CBC, iv=master[:16]).decrypt(keypool)
    pt = _pkcs7_unpad(pt)
    s = pt.decode("ascii", "replace").strip().strip("\r")
    return [p for p in s.split(",") if p]


def decrypt_header(enc: bytes, master: bytes) -> bytes:
    if len(enc) < 256:
        raise ValueError("chapter too short")
    return AES.new(master, AES.MODE_CBC, iv=master[:16]).decrypt(enc[:256])


def content_key(token_ascii: str | bytes, fuid: str | bytes, stt: str | bytes) -> bytes:
    if isinstance(token_ascii, str):
        token_ascii = token_ascii.encode("ascii")
    if isinstance(fuid, str):
        fuid = fuid.encode("utf-8")
    if isinstance(stt, str):
        stt = stt.encode("utf-8")
    return hashlib.sha256(token_ascii + fuid + stt).digest()


def _gunzip_loose(data: bytes) -> bytes:
    if data[:2] != b"\x1f\x8b":
        raise ValueError("not gzip")
    dco = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = dco.decompress(data)
        out += dco.flush()
        return out
    except zlib.error:
        for cut in range(len(data), max(len(data) - 64, 16), -1):
            try:
                return gzip.decompress(data[:cut])
            except Exception:
                continue
        raise


def _body(enc: bytes, header_plain: bytes) -> bytes:
    return header_plain[128:256] + enc[256:]


def _aes_cbc(data: bytes, key32: bytes) -> bytes:
    if len(data) % 16:
        raise ValueError(f"AES block len {len(data)}")
    return AES.new(key32, AES.MODE_CBC, iv=key32[:16]).decrypt(data)


def _des_cbc(data: bytes, key32: bytes) -> bytes:
    if len(data) % 8:
        raise ValueError(f"DES block len {len(data)}")
    return DES.new(key32[:8], DES.MODE_CBC, iv=key32[:8]).decrypt(data)


def _aes_ctr(data: bytes, key32: bytes, initial_value: int = 2) -> bytes:
    ctr = Counter.new(
        32,
        prefix=key32[:12],
        initial_value=initial_value,
        little_endian=False,
    )
    return AES.new(key32, AES.MODE_CTR, counter=ctr).decrypt(data)


def _unpad8(data: bytes) -> bytes:
    return unpad(data, 8)


def _unpad16(data: bytes) -> bytes:
    return unpad(data, 16)


def mode_string_from_header(header: bytes) -> str:
    mode = header[:16].split(b"\x00", 1)[0]
    digits = bytes(b for b in mode if 48 <= b <= 57)
    if not digits:
        raise ValueError(f"no mode digits in {mode!r}")
    return digits.decode("ascii")


def mode_id_from_header(header: bytes) -> int:
    """Native compares atoi(mode_str[:8])."""
    digits = mode_string_from_header(header)
    if len(digits) < 8:
        return int(digits)
    return int(digits[:8])


def token_index_from_header(header: bytes, token_count: int) -> int:
    """token_index = int(full_mode_digit_string) % token_count.

    Verified on samples c1-c15 (20-token pools):
      3193288111 % 20 = 11
      3134442310 % 20 = 10
      349410281  % 20 = 1
      9485912317 % 20 = 17
    """
    if token_count <= 0:
        raise ValueError("empty keypool tokens")
    return int(mode_string_from_header(header)) % token_count


def decrypt_mode_aes_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_cbc(_aes_cbc(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_des_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_cbc(_des_cbc(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_ctr_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _des_cbc(_aes_ctr(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_aes_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_unpad16(_aes_cbc(body, key32)), key32)
    return _gunzip_loose(mid)


def decrypt_mode_des_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_unpad8(_des_cbc(body, key32)), key32)
    return _gunzip_loose(mid)


def decrypt_mode_aes_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _des_cbc(_aes_cbc(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_ctr_ctr(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _aes_ctr(_aes_ctr(body, key32), key32)
    return _gunzip_loose(mid)


def decrypt_mode_des_des(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _unpad8(_des_cbc(_unpad8(_des_cbc(body, key32)), key32))
    return _gunzip_loose(mid)


def decrypt_mode_ctr_aes(enc: bytes, key32: bytes, header_plain: bytes) -> bytes:
    body = _body(enc, header_plain)
    mid = _unpad16(_aes_cbc(_aes_ctr(body, key32), key32))
    return _gunzip_loose(mid)


_MODE_HANDLERS: dict[int, Callable[[bytes, bytes, bytes], bytes]] = {
    MODE_AES_AES: decrypt_mode_aes_aes,
    MODE_DES_AES: decrypt_mode_des_aes,
    MODE_CTR_DES: decrypt_mode_ctr_des,
    MODE_AES_CTR: decrypt_mode_aes_ctr,
    MODE_DES_CTR: decrypt_mode_des_ctr,
    MODE_AES_DES: decrypt_mode_aes_des,
    MODE_CTR_CTR: decrypt_mode_ctr_ctr,
    MODE_DES_DES: decrypt_mode_des_des,
    MODE_CTR_AES: decrypt_mode_ctr_aes,
}


def select_token(tokens: list[str], index: int = 11) -> str:
    if not tokens:
        raise ValueError("empty keypool tokens")
    if index < 0 or index >= len(tokens):
        return tokens[-1]
    return tokens[index]


def fock_sn(data: bytes | str, length: int | None = None) -> str:
    """Pure-Python fock_sn (ELF VA 0x6dd0 / runtime 0x1200bdd0).

    Native flow:
      n = strlen(data)                 # used only for table index
      h1 = table[n % 3]
      h2 = table[(n >> 8) % 3]
      a = h1(data, length_arg)         # length_arg is JNI len (usually == n)
      b = h2(a, 16)
      c = h2(b, 16)
      return hex_encode(c)             # 32 lowercase hex chars + NUL

    table order (runtime GOT @ 0x1201efc8): MD2, MD4, MD5.
    """
    if isinstance(data, str):
        data_b = data.encode("utf-8")
    else:
        data_b = data
    if not data_b:
        raise ValueError("fock_sn: empty input")
    n = data_b.find(b"\x00")
    if n < 0:
        n = len(data_b)
    if n == 0:
        raise ValueError("fock_sn: empty C-string")
    if length is None:
        payload = data_b[:n]
    else:
        payload = data_b[:length]
    h_first = _SN_HASHES[n % 3]
    h_rest = _SN_HASHES[(n >> 8) % 3]
    a = h_first.new(payload).digest()
    b = h_rest.new(a).digest()
    c = h_rest.new(b).digest()
    return c.hex()


def decrypt_chapter(
    enc: bytes,
    stt: str | bytes,
    fuid: str | bytes,
    keypool: bytes,
    knva: bytes | None = None,
    token_index: Optional[int] = None,
) -> str:
    if knva is None:
        knva = derive_knva()
    master = master_key(fuid, knva)
    tokens = decrypt_keypool(keypool, master)
    header = decrypt_header(enc, master)
    mid = mode_id_from_header(header)
    handler = _MODE_HANDLERS.get(mid)
    if handler is None:
        mode = header[:16].split(b"\x00", 1)[0]
        raise NotImplementedError(f"mode id {mid} ({mode!r}) not supported")

    if token_index is None:
        token_index = token_index_from_header(header, len(tokens))

    last_err: Optional[Exception] = None
    order = [token_index] + [i for i in range(len(tokens)) if i != token_index]
    for ti in order:
        try:
            key32 = content_key(select_token(tokens, ti), fuid, stt)
            raw = handler(enc, key32, header)
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"decrypt failed for mode id {mid}: {last_err}")


def try_decrypt_chapter(
    enc: bytes,
    stt: str | bytes,
    fuid: str | bytes,
    keypool: bytes,
    knva: bytes | None = None,
) -> Optional[str]:
    try:
        return decrypt_chapter(enc, stt, fuid, keypool, knva)
    except Exception:
        return None

# === csigs ===
"""Csigs: bcrypt-like csigs algorithm ported from com.qq.reader.api.Csigs."""


MASK32 = 0xFFFFFFFF
BCRYPT_ALPHABET = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
DEC_TABLE = [-1] * 128
for _i, _ch in enumerate(BCRYPT_ALPHABET):
    DEC_TABLE[ord(_ch)] = _i

P_INIT = [
    608135816, -2052912941, 320440878, 57701188, -1542899678, 698298832, 137296536, -330404727, 1160258022, 953160567, -1101764913, 887688300,
    -1062458953, -914599715, 1065670069, -1253635817, -1843997223, -1988494565
]

S_INIT = [
    -785314906, -1730169428, 805139163, -803545161, -1193168915, 1780907670, -1166241723, -248741991, 614570311, -1282315017, 134345442, -2054226922,
    1667834072, 1901547113, -1537671517, -191677058, 227898511, 1921955416, 1904987480, -2112533778, 2069144605, -1034266187, -1674521287, 720527379,
    -976113629, 677414384, -901678824, -1193592593, -1904616272, 1614419982, 1822297739, -1340175810, -686458943, -1120842969, 2024746970, 1432378464,
    -430627341, -1437226092, 1464375394, 1676153920, 1439316330, 715854006, -1261675468, 289532110, -1588296017, 2087905683, -1276242927, 1668267050,
    732546397, 1947742710, -832815594, -1685613794, -1344882125, 1814351708, 2050118529, 680887927, 999245976, 1800124847, -994056165, 1713906067,
    1641548236, -81679983, 1216130144, 1575780402, -276538019, -377129551, -601480446, -345695352, 596196993, -745100091, 258830323, -2081144263,
    772490370, -1534844924, 1774776394, -1642095778, 566650946, -152474470, 1728879713, -1412200208, 1783734482, -665571480, -1777359064, -1420741725,
    1861159788, 326777828, -1170476976, 2130389656, -1578015459, 967770486, 1724537150, -2109534584, -1930525159, 1164943284, 2105845187, 998989502,
    -529566248, -2050940813, 1075463327, 1455516326, 1322494562, 910128902, 469688178, 1117454909, 936433444, -804646328, -619713837, 1240580251,
    122909385, -2137449605, 634681816, -152510729, -469872614, -1233564613, -1754472259, 79693498, -1045868618, 1084186820, 1583128258, 426386531,
    1761308591, 1047286709, 322548459, 995290223, 1845252383, -1691314900, -863943356, -1352745719, -1092366332, -567063811, 1712269319, 422464435,
    -1060394921, 1170764815, -771006663, -1177289765, 1434042557, 442511882, -694091578, 1076654713, 1738483198, -81812532, -1901729288, -617471240,
    1014306527, -43947243, 793779912, -1392160085, 842905082, -48003232, 1395751752, 1040244610, -1638115397, -898659168, 445077038, -552113701,
    -717051658, 679411651, -1402522938, -1940957837, 1767581616, -1144366904, -503340195, -1192226400, 284835224, -48135240, 1258075500, 768725851,
    -1705778055, -1225243291, -762426948, 1274779536, -505548070, -1530167757, 1660621633, -823867672, -283063590, 913787905, -797008130, 737222580,
    -1780753843, -1366257256, -357724559, 1804850592, -795946544, -1345903136, -1908647121, -1904896841, -1879645445, -233690268, -2004305902, -1878134756,
    1336762016, 1754252060, -774901359, -1280786003, 791618072, -1106372745, -361419266, -1962795103, -442446833, -1250986776, 413987798, -829824359,
    -1264037920, -49028937, 2093235073, -760370983, 375366246, -2137688315, -1815317740, 555357303, -424861595, 2008414854, -950779147, -73583153,
    -338841844, 2067696032, -700376109, -1373733303, 2428461, 544322398, 577241275, 1471733935, 610547355, -267798242, 1432588573, 1507829418,
    2025931657, -648391809, 545086370, 48609733, -2094660746, 1653985193, 298326376, 1316178497, -1287180854, 2064951626, 458293330, -1705826027,
    -703637697, -1130641692, 727753846, -2115603456, 146436021, 1461446943, -224990101, 705550613, -1235000031, -407242314, -13368018, -981117340,
    1404054877, -1449160799, 146425753, 1854211946, 1266315497, -1246549692, -613086930, -1004984797, -1385257296, 1235738493, -1662099272, -1880247706,
    -324367247, 1771706367, 1449415276, -1028546847, 422970021, 1963543593, -1604775104, -468174274, 1062508698, 1531092325, 1804592342, -1711849514,
    -1580033017, -269995787, 1294809318, -265986623, 1289560198, -2072974554, 1669523910, 35572830, 157838143, 1052438473, 1016535060, 1802137761,
    1753167236, 1386275462, -1214491899, -1437595849, 1040679964, 2145300060, -1904392980, 1461121720, -1338320329, -263189491, -266592508, 33600511,
    -1374882534, 1018524850, 629373528, -603381315, -779021319, 2091462646, -1808644237, 586499841, 988145025, 935516892, -927631820, -1695294041,
    -1455136442, 265290510, -322386114, -1535828415, -499593831, 1005194799, 847297441, 406762289, 1314163512, 1332590856, 1866599683, -167115585,
    750260880, 613907577, 1450815602, -1129346641, -560302305, -644675568, -1282691566, -590397650, 1427272223, 778793252, 1343938022, -1618686585,
    2052605720, 1946737175, -1130390852, -380928628, -327488454, -612033030, 1661551462, -1000029230, -283371449, 840292616, -582796489, 616741398,
    312560963, 711312465, 1351876610, 322626781, 1910503582, 271666773, -2119403562, 1594956187, 70604529, -677132437, 1007753275, 1495573769,
    -225450259, -1745748998, -1631928532, 504708206, -2031925904, -353800271, -2045878774, 1514023603, 1998579484, 1312622330, 694541497, -1712906993,
    -2143385130, 1382467621, 776784248, -1676627094, -971698502, -1797068168, -1510196141, 503983604, -218673497, 907881277, 423175695, 432175456,
    1378068232, -149744970, -340918674, -356311194, -474200683, -1501837181, -1317062703, 26017576, -1020076561, -1100195163, 1700274565, 1756076034,
    -288447217, -617638597, 720338349, 1533947780, 354530856, 688349552, -321042571, 1637815568, 332179504, -345916010, 53804574, -1442618417,
    -1250730864, 1282449977, -711025141, -877994476, -288586052, 1617046695, -1666491221, -1292663698, 1686838959, 431878346, -1608291911, 1700445008,
    1080580658, 1009431731, 832498133, -1071531785, -1688990951, -2023776103, -1778935426, 1648197032, -130578278, -1746719369, 300782431, 375919233,
    238389289, -941219882, -1763778655, 2019080857, 1475708069, 455242339, -1685863425, 448939670, -843904277, 1395535956, -1881585436, 1841049896,
    1491858159, 885456874, -30872223, -293847949, 1565136089, -396052509, 1108368660, 540939232, 1173283510, -1549095958, -613658859, -87339056,
    -951913406, -278217803, 1699691293, 1103962373, -669091426, -2038084153, -464828566, 1031889488, -815619598, 1535977030, -58162272, -1043876189,
    2132092099, 1774941330, 1199868427, 1452454533, 157007616, -1390851939, 342012276, 595725824, 1480756522, 206960106, 497939518, 591360097,
    863170706, -1919713727, -698356495, 1814182875, 2094937945, -873565088, 1082520231, -831049106, -1509457788, 435703966, -386934699, 1641649973,
    -1452693590, -989067582, 1510255612, -2146710820, -1639679442, -1018874748, -36346107, 236887753, -613164077, 274041037, 1734335097, -479771840,
    -976997275, 1899903192, 1026095262, -244449504, 356393447, -1884275382, -421290197, -612127241, -381855128, -1803468553, -162781668, -1805047500,
    1091903735, 1979897079, -1124832466, -727580568, -737663887, 857797738, 1136121015, 1342202287, 507115054, -1759230650, 337727348, -1081374656,
    1301675037, -1766485585, 1895095763, 1721773893, -1078195732, 62756741, 2142006736, 835421444, -1762973773, 1442658625, -635090970, -1412822374,
    676362277, 1392781812, 170690266, -373920261, 1759253602, -683120384, 1745797284, 664899054, 1329594018, -393761396, -1249058810, 2062866102,
    -1429332356, -751345684, -830954599, 1080764994, 553557557, -638351943, -298199125, 991055499, 499776247, 1265440854, 648242737, -354183246,
    980351604, -581221582, 1749149687, -898096901, -83167922, -654396521, 1161844396, -1169648345, 1431517754, 545492359, -26498633, -795437749,
    1437099964, -1592419752, -861329053, -1713251533, -1507177898, 1060185593, 1593081372, -1876348548, -34019326, 69676912, -2135222948, 86519011,
    -1782508216, -456757982, 1220612927, -955283748, 133810670, 1090789135, 1078426020, 1569222167, 845107691, -711212847, -222510705, 1091646820,
    628848692, 1613405280, -537335645, 526609435, 236106946, 48312990, -1352249391, -892239595, 1797494240, 859738849, 992217954, -289490654,
    -2051890674, -424014439, -562951028, 765654824, -804095931, -1783130883, 1685915746, -405998096, 1414112111, -2021832454, -1013056217, -214004450,
    172450625, -1724973196, 980381355, -185008841, -1475158944, -1578377736, -1726226100, -613520627, -964995824, 1835478071, 660984891, -590288892,
    -248967737, -872349789, -1254551662, 1762651403, 1719377915, -824476260, -1601057013, -652910941, -1156370552, 1364962596, 2073328063, 1983633131,
    926494387, -871278215, -2144935273, -198299347, 1749200295, -966120645, 309677260, 2016342300, 1779581495, -1215147545, 111262694, 1274766160,
    443224088, 298511866, 1025883608, -488520759, 1145181785, 168956806, -653464466, -710153686, 1689216846, -628709281, -1094719096, 1692713982,
    -1648590761, -252198778, 1618508792, 1610833997, -771914938, -164094032, 2001055236, -684262196, -2092799181, -266425487, -1333771897, 1006657119,
    2006996926, -1108824540, 1430667929, -1084739999, 1314452623, -220332638, -193663176, -2021016126, 1399257539, -927756684, -1267338667, 1190975929,
    2062231137, -1960976508, -2073424263, -1856006686, 1181637006, 548689776, -1932175983, -922558900, -1190417183, -1149106736, 296247880, 1970579870,
    -1216407114, -525738999, 1714227617, -1003338189, -396747006, 166772364, 1251581989, 493813264, 448347421, 195405023, -1584991729, 677966185,
    -591930749, 1463355134, -1578971493, 1338867538, 1343315457, -1492745222, -1610435132, 233230375, -1694987225, 2000651841, -1017099258, 1638401717,
    -266896856, -1057650976, 6314154, 819756386, 300326615, 590932579, 1405279636, -1027467724, -1144263082, -1866680610, -335774303, -833020554,
    1862657033, 1266418056, 963775037, 2089974820, -2031914401, 1917689273, 448879540, -744572676, -313240200, 150775221, -667058989, 1303187396,
    508620638, -1318983944, -1568336679, 1817252668, 1876281319, 1457606340, 908771278, -574175177, -677760460, -1838972398, 1729034894, 1080033504,
    976866871, -738527793, -1413318857, 1522871579, 1555064734, 1336096578, -746444992, -1715692610, -720269667, -1089506539, -701686658, -956251013,
    -1215554709, 564236357, -1301368386, 1781952180, 1464380207, -1131123079, -962365742, 1699332808, 1393555694, 1183702653, -713881059, 1288719814,
    691649499, -1447410096, -1399511320, -1101077756, -1577396752, 1781354906, 1676643554, -1702433246, -1064713544, 1126444790, -1524759638, -1661808476,
    -2084544070, -1679201715, -1880812208, -1167828010, 673620729, -1489356063, 1269405062, -279616791, -953159725, -145557542, 1057255273, 2012875353,
    -2132498155, -2018474495, -1693849939, 993977747, -376373926, -1640704105, 753973209, 36408145, -1764381638, 25011837, -774947114, 2088578344,
    530523599, -1376601957, 1524020338, 1518925132, -534139791, -535190042, 1202760957, -309069157, -388774771, 674977740, -120232407, 2031300136,
    2019492241, -311074731, -141160892, -472686964, 352677332, -1997247046, 60907813, 90501309, -1007968747, 1016092578, -1759044884, -1455814870,
    457141659, 509813237, -174299397, 652014361, 1966332200, -1319764491, 55981186, -1967506245, 676427537, -1039476232, -1412673177, -861040033,
    1307055953, 942726286, 933058658, -1826555503, -361066302, -79791154, 1361170020, 2001714738, -1464409218, -1020707514, 1222529897, 1679025792,
    -1565652976, -580013532, 1770335741, 151462246, -1281735158, 1682292957, 1483529935, 471910574, 1539241949, 458788160, -858652289, 1807016891,
    -576558466, 978976581, 1043663428, -1129001515, 1927990952, -94075717, -1922690386, -1086558393, -761535389, 1412390302, -1362987237, -162634896,
    1947078029, -413461673, -126740879, -1353482915, 1077988104, 1320477388, 886195818, 18198404, -508558296, -1785185763, 112762804, -831610808,
    1866414978, 891333506, 18488651, 661792760, 1628790961, -409780260, -1153795797, 876946877, -1601685023, 1372485963, 791857591, -1608533303,
    -534984578, -1127755274, -822013501, -1578587449, 445679433, -732971622, -790962485, -720709064, 54117162, -963561881, -1913048708, -525259953,
    -140617289, 1140177722, -220915201, 668550556, -1080614356, 367459370, 261225585, -1684794075, -85617823, -826893077, -1029151655, 314222801,
    -1228863650, -486184436, 282218597, -888953790, -521376242, 379116347, 1285071038, 846784868, -1625320142, -523005217, -744475605, -1989021154,
    453669953, 1268987020, -977374944, -1015663912, -550133875, -1684459730, -435458233, 266596637, -447948204, 517658769, -832407089, -851542417,
    370717030, -47440635, -2070949179, -151313767, -182193321, -1506642397, -1817692879, 1456262402, -1393524382, 1517677493, 1846949527, -1999473716,
    -560569710, -2118563376, 1280348187, 1908823572, -423180355, 846861322, 1172426758, -1007518822, -911584259, 1655181056, -1155153950, 901632758,
    1897031941, -1308360158, -1228157060, -847864789, 1393639104, 373351379, 950779232, 625454576, -1170726756, -146354570, 2007998917, 544563296,
    -2050228658, -1964470824, 2058025392, 1291430526, 424198748, 50039436, 29584100, -689184263, -1865090967, -1503863136, 1057563949, -1039604065,
    -1219600078, -831004069, 1469046755, 985887462
]

CIHAI_INIT = [
    1332899944, 1700884034, 1701343084, 1684370003, 1668446532, 1869963892
]

def _u32(x: int) -> int:
    return x & MASK32


def _i32(x: int) -> int:
    x &= MASK32
    return x if x < 0x80000000 else x - 0x100000000


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def to_hex(data: bytes) -> str:
    return data.hex()


def generate_salt(rounds: int = 4, random_bytes: Optional[bytes] = None) -> str:
    if rounds < 4 or rounds > 30:
        raise ValueError("log_rounds exceeds maximum (30)")
    salt_bytes = random_bytes if random_bytes is not None else secrets.token_bytes(16)
    if len(salt_bytes) != 16:
        raise ValueError("salt must be 16 bytes")
    salt_b64 = magic_b64_encode(salt_bytes, len(salt_bytes))
    return f"$2a${rounds:02d}${salt_b64}"


def magic_b64_decode(s: str, max_len: int) -> bytes:
    L = len(s)
    tmp = bytearray(max_len)
    out_len = 0
    i = 0
    while i < L - 1 and out_len < max_len:
        c1 = s[i]
        c2 = s[i + 1]
        if ord(c1) >= 0x80 or ord(c2) >= 0x80:
            break
        b1 = DEC_TABLE[ord(c1)]
        b2 = DEC_TABLE[ord(c2)]
        if b1 == -1 or b2 == -1:
            break
        tmp[out_len] = ((b1 << 2) | ((b2 & 0x30) >> 4)) & 0xFF
        out_len += 1
        if out_len >= max_len or i + 2 >= L:
            break
        c3 = s[i + 2]
        if ord(c3) >= 0x80:
            break
        b3 = DEC_TABLE[ord(c3)]
        if b3 == -1:
            break
        tmp[out_len] = (((b2 & 0xF) << 4) | ((b3 & 0x3C) >> 2)) & 0xFF
        out_len += 1
        if out_len >= max_len or i + 3 >= L:
            break
        c4 = s[i + 3]
        if ord(c4) >= 0x80:
            break
        b4 = DEC_TABLE[ord(c4)]
        if b4 == -1:
            break
        tmp[out_len] = (((b3 & 3) << 6) | b4) & 0xFF
        out_len += 1
        i += 4
    return bytes(tmp[:out_len])


def magic_b64_encode(b: bytes, length: int) -> str:
    sb = []
    i = 0
    while i < length:
        c1 = b[i] & 0xFF
        sb.append(BCRYPT_ALPHABET[(c1 >> 2) & 0x3F])
        c1 = (c1 & 3) << 4
        i += 1
        if i >= length:
            sb.append(BCRYPT_ALPHABET[c1 & 0x3F])
            break
        c2 = b[i] & 0xFF
        sb.append(BCRYPT_ALPHABET[(c1 | ((c2 >> 4) & 0xF)) & 0x3F])
        c1 = (c2 & 0xF) << 2
        i += 1
        if i >= length:
            sb.append(BCRYPT_ALPHABET[c1 & 0x3F])
            break
        c3 = b[i] & 0xFF
        sb.append(BCRYPT_ALPHABET[(c1 | ((c3 >> 6) & 3)) & 0x3F])
        sb.append(BCRYPT_ALPHABET[c3 & 0x3F])
        i += 1
    return "".join(sb)


def stream_to_word(data: bytes, idx_ref: List[int]) -> int:
    if not data:
        return 0
    idx = idx_ref[0]
    w = 0
    for _ in range(4):
        w = ((w << 8) | (data[idx] & 0xFF)) & MASK32
        idx = (idx + 1) % len(data)
    idx_ref[0] = idx
    return w


def blowfish_encrypt_block(P: List[int], S: List[int], l: int, r: int):
    i3 = _u32(l)
    i5 = _u32(r)
    i6 = 0
    i7 = _u32(P[0])
    while True:
        i3 = _u32(i3 ^ i7)
        if i6 > 14:
            l_out = _u32(i5 ^ P[17])
            r_out = i3
            return l_out, r_out
        s0 = S[(i3 >> 24) & 0xFF]
        s1 = S[((i3 >> 16) & 0xFF) | 0x100]
        s2 = S[((i3 >> 8) & 0xFF) | 0x200]
        s3 = S[(i3 & 0xFF) | 0x300]
        f = _u32((_u32(s0 + s1) ^ s2) + s3)
        i9 = i6 + 1
        i6 = i9 + 1
        i5 = _u32(i5 ^ _u32(f ^ P[i9]))
        s0 = S[(i5 >> 24) & 0xFF]
        s1 = S[((i5 >> 16) & 0xFF) | 0x100]
        s2 = S[((i5 >> 8) & 0xFF) | 0x200]
        s3 = S[(i5 & 0xFF) | 0x300]
        f2 = _u32((_u32(s0 + s1) ^ s2) + s3)
        i7 = _u32(P[i6] ^ f2)


def expand_with_key(P: List[int], S: List[int], key_bytes: bytes) -> None:
    idx_ref = [0]
    for i in range(len(P)):
        P[i] = _i32(P[i] ^ stream_to_word(key_bytes, idx_ref))
    block_l = 0
    block_r = 0
    for i in range(0, len(P), 2):
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        P[i] = _i32(block_l)
        P[i + 1] = _i32(block_r)
    for i in range(0, len(S), 2):
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        S[i] = _i32(block_l)
        S[i + 1] = _i32(block_r)


def expand_with_salt_and_key(P: List[int], S: List[int], salt: bytes, key: bytes) -> None:
    idx_key = [0]
    idx_salt = [0]
    for i in range(len(P)):
        P[i] = _i32(P[i] ^ stream_to_word(key, idx_key))
    block_l = 0
    block_r = 0
    for i in range(0, len(P), 2):
        block_l = _u32(block_l ^ stream_to_word(salt, idx_salt))
        block_r = _u32(block_r ^ stream_to_word(salt, idx_salt))
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        P[i] = _i32(block_l)
        P[i + 1] = _i32(block_r)
    for i in range(0, len(S), 2):
        block_l = _u32(block_l ^ stream_to_word(salt, idx_salt))
        block_r = _u32(block_r ^ stream_to_word(salt, idx_salt))
        block_l, block_r = blowfish_encrypt_block(P, S, block_l, block_r)
        S[i] = _i32(block_l)
        S[i + 1] = _i32(block_r)


def magic_search_final(password_bytes: bytes, salt_bytes: bytes, rounds_log2: int, cihai_init: List[int]) -> bytes:
    if rounds_log2 < 4 or rounds_log2 > 30:
        raise ValueError("Bad number of rounds")
    if len(salt_bytes) != 16:
        raise ValueError("Bad salt length")
    P = list(P_INIT)
    S = list(S_INIT)
    i_arr = list(cihai_init)
    expand_with_salt_and_key(P, S, salt_bytes, password_bytes)
    loops = 1 << rounds_log2
    for _ in range(loops):
        expand_with_key(P, S, password_bytes)
        expand_with_key(P, S, salt_bytes)
    half_len = len(i_arr) >> 1
    for _round in range(64):
        for j in range(half_len):
            idx = j * 2
            l = i_arr[idx]
            r = i_arr[idx + 1]
            lr0, lr1 = blowfish_encrypt_block(P, S, l, r)
            i_arr[idx] = _i32(lr0)
            i_arr[idx + 1] = _i32(lr1)
    out = bytearray(len(i_arr) * 4)
    k = 0
    for v in i_arr:
        vv = _u32(v)
        out[k] = (vv >> 24) & 0xFF
        out[k + 1] = (vv >> 16) & 0xFF
        out[k + 2] = (vv >> 8) & 0xFF
        out[k + 3] = vv & 0xFF
        k += 4
    return bytes(out)


def search(password: str, salt_str: Optional[str] = None) -> str:
    if salt_str is None:
        salt_str = generate_salt(4)
    if len(salt_str) < 4 or salt_str[0] != "$" or salt_str[1] != "2":
        raise ValueError("Invalid salt version")
    c_rev = "\x00"
    i2 = 3
    if salt_str[2] != "$":
        c_rev = salt_str[2]
        if c_rev != "a" or salt_str[3] != "$":
            raise ValueError("Invalid salt revision")
        i2 = 4
    i3 = i2 + 2
    if salt_str[i3] != "$":
        raise ValueError("Missing salt rounds")
    rounds_log2 = int(salt_str[i2:i3])
    salt_b64 = salt_str[i2 + 3 : i2 + 25]
    if len(salt_b64) != 22:
        raise ValueError("Bad bcrypt-like salt length")
    pwd_bytes = password.encode("utf-8")
    if c_rev >= "a":
        pwd_bytes = password.encode("utf-8") + b"\x00"
    salt_bytes = magic_b64_decode(salt_b64, 16)
    out_bytes = magic_search_final(pwd_bytes, salt_bytes, rounds_log2, CIHAI_INIT)
    sb = ["$2"]
    if c_rev >= "a":
        sb.append(c_rev)
    sb.append("$")
    if rounds_log2 < 10:
        sb.append("0")
    if rounds_log2 > 30:
        raise ValueError("rounds exceeds maximum (30)")
    sb.append(str(rounds_log2))
    sb.append("$")
    sb.append(magic_b64_encode(salt_bytes, len(salt_bytes)))
    sb.append(magic_b64_encode(out_bytes, len(CIHAI_INIT) * 4 - 1))
    return "".join(sb)

# --- 业务侧封装 ---

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
    b64 = str(src.get("keypool_b64") or "")
    if not b64:
        return b""
    try:
        return base64.b64decode(b64 + "===")
    except Exception:
        return b""

def 解密章节密文(cipher: bytes, *, bid: str, cid: str, fuid: str, keypool: bytes = b"") -> Tuple[Optional[bytes], str]:
    """多模式 libfock 解密。"""
    if not cipher:
        return None, "empty"
    if not 是否二进制(cipher):
        return cipher, "plain"
    if cipher[:2] == bytes([0x1f, 0x8b]):
        try:
            return gzip.decompress(cipher), "gzip"
        except Exception:
            pass
    if AES is None or unpad is None:
        return None, "no_crypto"
    if not keypool:
        return None, "missing_keypool"
    stt = f"{bid}_{cid}_s"
    try:
        text = try_decrypt_chapter(cipher, stt, fuid, keypool)
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

def 构建App请求头(登录态: Optional[Mapping[str, str]] = None, *, 时间毫秒: Optional[int] = None) -> Dict[str, str]:
    """使用 QQ 阅读 App 的身份字段和 csigs 签名构造请求头。"""
    src = {str(k): str(v) for k, v in (登录态 or {}).items() if v not in (None, "")}
    app = dict(默认App请求身份)
    for 键 in ("loginType", "c_platform", "c_version", "channel", "qrsn", "fuid"):
        if src.get(键):
            app[键] = src[键]
    if src.get("app_uid"):
        app["uid"] = src["app_uid"]
    if src.get("app_usid"):
        app["usid"] = src["app_usid"]
    时间毫秒 = int(时间毫秒 or time.time() * 1000)
    签名原文 = (
        f"{app['loginType']}|||{app['c_version']}|{app['c_platform']}|{app['channel']}|"
        f"{app['qrsn']}|{app['qrsn']}||||0|{时间毫秒}|{App签名尾部}"
    )
    try:
        csigs = search(sha256_hex(签名原文), generate_salt())
    except Exception as e:
        raise RuntimeError("App请求签名生成失败") from e

    ywguid = src.get("ywguid") or src.get("login_uin") or ""
    ywkey = src.get("ywkey") or src.get("login_key") or ""
    cookie = src.get("Cookie") or src.get("cookie") or ""
    if (not cookie) and ywguid and ywkey:
        cookie = f"ywguid={ywguid}; ywkey={ywkey};"
    out = {
        "User-Agent": src.get("User-Agent") or App默认UA,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "loginType": app["loginType"],
        "c_platform": app["c_platform"],
        "c_version": app["c_version"],
        "channel": app["channel"],
        "qrsn": app["qrsn"],
        "qrsn_new": app["qrsn"],
        "usid": app["usid"],
        "uid": app["uid"],
        "youngerMode": "0",
        "ttime": str(时间毫秒),
        "csigs": csigs,
        "fuid": app["fuid"],
    }
    if cookie:
        out["Cookie"] = cookie
    if ywguid:
        out["ywguid"] = ywguid
        out["login_uin"] = ywguid
    if ywkey:
        out["ywkey"] = ywkey
        out["login_key"] = ywkey
    return out


def 最小请求头(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """兼容旧调用：正文和详情统一使用 App 签名请求头。"""
    return 构建App请求头(登录态)


def 组装本地下载态(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """App 设备态加可选数据库登录态；密钥池只在内存中刷新。"""
    out = dict(默认App请求身份)
    out.update({str(k): str(v) for k, v in (登录态 or {}).items() if v not in (None, "")})
    if not (登录态 or {}).get("app_uid"):
        out["uid"] = 默认App请求身份["uid"]
    if not (登录态 or {}).get("app_usid"):
        out["usid"] = 默认App请求身份["usid"]
    if not out.get("fuid"):
        out["fuid"] = 默认App请求身份["fuid"]
    if not out.get("User-Agent"):
        out["User-Agent"] = App默认UA
    return out

def 组装游客下载态(登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """游客正文请求只保留 App 身份、fuid 和当前内存密钥池。"""
    基 = 组装本地下载态(登录态)
    out = {键: str(基.get(键) or 默认App请求身份.get(键) or "") for 键 in 默认App请求身份}
    out["User-Agent"] = str(基.get("User-Agent") or App默认UA)
    if 基.get("keypool_b64"):
        out["keypool_b64"] = str(基["keypool_b64"])
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
    ywguid = str(params.get("ywguid") or "").strip()
    ywkey = str(params.get("ywkey") or "").strip()
    if ywguid or ywkey:
        Cookie片段 = []
        if ywguid:
            Cookie片段.append(f"ywguid={ywguid}")
        if ywkey:
            Cookie片段.append(f"ywkey={ywkey}")
        headers["Cookie"] = "; ".join(Cookie片段) + ";"
    async with session.post(url, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        return json.loads(await resp.text())


async def 请求动态密钥池(session: aiohttp.ClientSession, 下载态: Mapping[str, str]) -> str:
    """从 App 密钥池接口取当前 fuid 对应的解密令牌，仅保留进程内短缓存。"""
    fuid = str(下载态.get("fuid") or 默认App请求身份["fuid"])
    已缓存 = 内存密钥池缓存.get(fuid)
    当前时间 = time.monotonic()
    if 已缓存 and 当前时间 - 已缓存[0] < 密钥池缓存秒数:
        return 已缓存[1]

    地址 = 组装URL("https://newminerva-tgw.reader.qq.com/sk", {"fuid": fuid})
    请求头 = {"User-Agent": App默认UA, "Accept": "*/*", "Accept-Encoding": "identity"}
    响应 = await http_get_json(session, 地址, 请求头, timeout=30)
    密钥池 = str(响应.get("pool") or "").strip() if isinstance(响应, dict) else ""
    if not 密钥池:
        raise RuntimeError("App密钥池为空")
    try:
        令牌列表 = decrypt_keypool(base64.b64decode(密钥池), master_key(fuid))
    except Exception as e:
        raise RuntimeError("App密钥池校验失败") from e
    if not 令牌列表:
        raise RuntimeError("App密钥池无可用令牌")
    内存密钥池缓存[fuid] = (当前时间, 密钥池)
    return 密钥池


async def 准备App下载态(session: aiohttp.ClientSession, 登录态: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """下载开始前统一准备 App 身份和动态密钥池，不落地到文件或数据库。"""
    下载态 = 组装本地下载态(登录态)
    try:
        下载态["keypool_b64"] = await 请求动态密钥池(session, 下载态)
    except Exception:
        if not 下载态.get("keypool_b64"):
            raise
    return 下载态


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
    timeout: int = 300,
) -> bytes:
    请求态 = 组装本地下载态(登录态)
    headers = 构建App请求头(请求态)
    fuid = str(请求态.get("fuid") or 默认App请求身份["fuid"])
    # 外部源码验证的 App 请求形态：type=2 + App 签名；不混入网页正文参数。
    params = {
        "bookId": bid,
        "type": 2,
        "scids": scids,
        "fuid": fuid,
        "text_type": int(text_type),
    }
    if useindex:
        params["useindex"] = 1
    url = 组装URL(批量正文地址, params)
    data, status = await http_get_bytes(session, url, headers, timeout=timeout)
    if status >= 400: raise RuntimeError(f"批量接口 HTTP {status}")
    return data


async def 请求目录包(session: aiohttp.ClientSession, bid: str, *, timeout: int = 60) -> bytes:
    """目录必须使用 App 的 type=0 授权包，不能混用正文 type=2 参数。"""
    params = {
        "bookId": bid,
        "type": 0,
        "tafauth": 1,
        "scids": "0",
        "text_type": 0,
        "useindex": 1,
    }
    headers = {
        "User-Agent": 默认UA,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    data, status = await http_get_bytes(session, 组装URL(批量正文地址, params), headers, timeout=timeout)
    if status >= 400:
        raise RuntimeError(f"目录接口 HTTP {status}")
    return data


async def 请求目录(session: aiohttp.ClientSession, bid: str, 登录态: Optional[Mapping[str, str]] = None) -> List[Dict[str, Any]]:
    blob = await 请求目录包(session, bid, timeout=60)
    entries = 解析tar(blob)
    ce = 找目录成员(entries, bid)
    if not ce: return []
    return 解析目录文本(解码文本(ce.data))

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
    # 短信登录沿用解密算法调整前已验证的 YWLogin SDK 客户端标识。
    # 正文下载仍使用默认设备态；这里不改变下载或解密参数。
    version_code = str(d.get("version_code") or 登录协议版本号)
    if version_code in {"", "417", "0888"}:
        version_code = 登录协议版本号
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


def 构造安全登录诊断(阶段: str, 参数: Mapping[str, Any], 响应: Any) -> str:
    """只记录协议排查所需的非敏感摘要，绝不写入手机号、凭证或响应原文。"""
    敏感字段 = {
        "phone", "phonecode", "phonekey", "sessionkey", "ticket", "sig",
        "captchaticket", "randstr", "captcharandstr", "ywguid", "ywkey", "signature",
    }
    字段名 = sorted(
        str(k) for k, v in 参数.items()
        if v not in (None, "") and str(k).lower() not in 敏感字段
    )

    def 指纹(字段名: str) -> str:
        值 = str(参数.get(字段名) or "")
        if not 值:
            return "0"
        摘要 = hashlib.sha256(值.encode("utf-8", "ignore")).hexdigest()[:12]
        return f"{len(值)}:{摘要}"

    响应码 = 查找字符串字段(响应, "code") or "-"
    下一步 = 查找nextAction(响应)
    有会话键 = bool(查找字符串字段(响应, "sessionKey", "sessionkey", "phonekey"))
    有登录态 = bool(参数.get("ywguid") or 参数.get("ywkey"))
    return (
        f"stage={阶段}, code={响应码}, next_action={下一步}, session_key={'yes' if 有会话键 else 'no'}, "
        f"has_auth={'yes' if 有登录态 else 'no'}, fields={','.join(字段名)}, "
        f"version={参数.get('version') or '-'}, osversion={参数.get('osversion') or '-'}, "
        f"source={参数.get('source') or '-'}, qimei={指纹('qimei')}, "
        f"qimei36={指纹('qimei36')}, ibex={指纹('ibex')}"
    )


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

def 从登录载荷构造登录态(payload: Mapping[str, Any]) -> Dict[str, str]:
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
        "account_uid": ywguid,
        "Cookie": cookie,
        "fuid": fuid,
        "qimei": 默认设备.get("qimei", ""),
        "qimei36": 默认设备.get("qimei36", ""),
        "ibex": 默认设备.get("ibex", ""),
    }
    for key in ("ywOpenId", "qrsn"):
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
                登录态=None,
            )
    except Exception as e:
        logger.warning(f"QQ阅读滑块后发短信失败：error={e}")
        关闭滑块服务(会话=会话)
        return False, 登录失败提示
    if not 结果.get("success"):
        logger.warning(f"QQ阅读滑块后发短信失败：{结果.get('diagnostic') or '未生成受控诊断'}")
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
    完整登录态 = 补齐QQ阅读登录态(登录态)
    full_phone = 手机号带区号(phone); params = 登录默认参数(完整登录态)
    params.update({"type": "1", "needRegister": "1", "phone": full_phone})
    ywguid = str(完整登录态.get("ywguid") or 完整登录态.get("login_uin") or "").strip()
    ywkey = str(完整登录态.get("ywkey") or 完整登录态.get("login_key") or "").strip()
    if ywguid:
        params["ywguid"] = ywguid
    if ywkey:
        params["ywkey"] = ywkey
    if ticket or randstr or session_key: params = 应用滑块参数(params, ticket=ticket, randstr=randstr, session_key=session_key)
    response = await http_post_form_json(session, 发短信地址, params, timeout=30)
    next_action = 查找nextAction(response); key = 查找字符串字段(response, "sessionKey", "sessionkey", "phonekey")
    return {
        "response": response,
        "next_action": next_action,
        "session_key": key,
        "phone": full_phone,
        "success": bool(key) and next_action != 11,
        "need_captcha": next_action == 11,
        "diagnostic": 构造安全登录诊断("send_phone", params, response),
    }

async def 提交手机验证码(session: aiohttp.ClientSession, phone: str, code: str, session_key: str, *, 登录态: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    full_phone = 手机号带区号(phone); params = 登录默认参数(登录态)
    params.update({"phonekey": session_key, "phonecode": str(code).strip(), "phone": urllib.parse.quote_plus(full_phone)})
    response = await http_post_form_json(session, 验证码登录地址, params, timeout=30)
    诊断 = 构造安全登录诊断("verify_code", params, response)
    payload = 查找登录载荷(response)
    if not payload: return {"success": False, "response": response, "diagnostic": 诊断}
    return {
        "success": True,
        "auth": 从登录载荷构造登录态(payload),
        "response": response,
        "diagnostic": 诊断,
    }

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
    路径 = 下载缓存目录 / 文件名
    路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(路径)
    return 路径

def 删除QQ阅读缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    try:
        Path(缓存路径).unlink(missing_ok=True)
        小说缓存工具.解除下载缓存占用(缓存路径)
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
) -> list[dict[str, Any]]:
    """按 App 可接受的最多 500 章范围拆分，并发请求正文。"""
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
                            text_type=text_type, useindex=False, timeout=180,
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
                    text_type=text_type, useindex=False, timeout=90,
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
                                    text_type=text_type, useindex=False, timeout=120,
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
                        text_types=text_types,
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
    已保存登录态 = 读取QQ阅读登录态(配置)
    超时 = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=300)
    try:
        async with aiohttp.ClientSession(timeout=超时) as 会话:
            # 整个下载链路均使用 App 身份、App 签名和动态密钥池。
            登录态 = await 准备App下载态(会话, 已保存登录态)
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
                logger.warning(f"QQ阅读本地下载失败：无目录 book_id={书籍编号}"); yield 下载失败提示; return
            for i, ch in enumerate(目录, start=1):
                ch["index"] = 安全整数(ch.get("index")) or i
            有账号 = bool(登录态.get("ywguid") and 登录态.get("ywkey"))
            免费章上限 = 安全整数(书籍信息.get("max_free_chapter"))
            全书免费 = 是否全书免费可下(书籍信息, 详情) or bool(书籍信息.get("is_all_free"))
            # 未登录时使用游客 App 设备态；已保存的 Cookie 则直接叠加到 App 请求。
            if not 有账号:
                下载态 = 组装游客下载态(登录态)
            模式 = "login" if 有账号 else "guest"
            类型候选 = 识别正文类型(详情, 书籍信息)
            下载目录 = list(目录)
            疑似收费 = 免费章上限 > 0 and 免费章上限 < len(目录)

            书籍信息["chapter_count"] = len(目录)
            logger.info(
                f"QQ阅读开始下载：source=local, book_id={书籍编号}, title={书籍信息.get('title')}, "
                f"author={书籍信息.get('author')}, status={书籍信息.get('status')}, "
                f"words={书籍信息.get('word_count')}, chapters={len(目录)}, download_chapters={len(下载目录)}, "
                f"mode={模式}, all_free={全书免费}, text_types={list(类型候选)}, has_account={有账号}"
            )
            yield 格式化下载提示(书籍信息, len(目录))

            章节结果 = await 下载全书批量(
                会话, 书籍编号, 下载目录, 下载态,
                text_types=类型候选,
            )
            缺少数 = sum(1 for x in 章节结果 if not x.get("success") or not str(x.get("content") or "").strip())
            if 缺少数:
                章节结果 = await 补拉缺失章节(
                    会话, 书籍编号, 章节结果, 下载态,
                    text_types=类型候选,
                )
            成功列表 = [x for x in 章节结果 if x.get("success") and str(x.get("content") or "").strip()]
            if not 成功列表 or len(成功列表) < len(下载目录):
                logger.warning(
                    f"QQ阅读本地下载失败：book_id={书籍编号}, success={len(成功列表)}, total={len(下载目录)}, "
                    f"catalog_total={len(目录)}, mode={模式}, has_account={有账号}"
                )
                if 疑似收费 or (成功列表 and len(成功列表) < len(目录)):
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
    Cookie匹配 = QQ阅读Cookie命令正则.fullmatch(文本)
    是直接Cookie = 是QQ阅读Cookie文本(文本)
    if Cookie匹配 or 是直接Cookie:
        if not 是群文件清理管理员(event, 配置):
            return None
        原始Cookie = Cookie匹配.group(1) if Cookie匹配 else 文本
        登录态 = 解析QQ阅读Cookie(原始Cookie)
        if not 是QQ阅读Cookie文本(原始Cookie):
            return "QQ阅读Cookie格式不正确"
        try:
            写入QQ阅读登录态(配置, 登录态)
        except Exception as e:
            logger.warning(f"QQ阅读Cookie写入数据库失败：error={e}")
            return 登录失败提示
        旧会话 = 待登录会话.pop(会话键, None)
        关闭滑块服务(会话=旧会话)
        字段名 = ",".join(sorted(k for k in 登录态 if k != "Cookie"))
        logger.info(f"QQ阅读Cookie已识别并保存：fields={字段名}")
        return "QQ阅读Cookie已保存"
    if 文本 in QQ阅读Cookie状态命令:
        if not 是群文件清理管理员(event, 配置):
            return None
        登录态 = 读取QQ阅读登录态(配置)
        return "QQ阅读Cookie：已保存" if 是QQ阅读Cookie文本(登录态.get("Cookie") or "") else "QQ阅读Cookie：未保存"
    if 文本 in ("登录QQ阅读", "qq阅读登录", "QQ阅读登录"):
        if not 是群文件清理管理员(event, 配置):
            return None
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
        return None
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
                结果 = await 发送手机验证码(会话http, 号码, 登录态=None)
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
            logger.warning(f"QQ阅读发短信失败：{结果.get('diagnostic') or '未生成受控诊断'}")
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
                    登录态=None,
                )
        except Exception as e:
            logger.warning(f"QQ阅读验证码登录失败：error={e}")
            待登录会话.pop(会话键, None)
            return 登录失败提示
        if not 结果.get("success"):
            logger.warning(
                f"QQ阅读验证码登录失败：has_payload={bool(结果.get('auth'))}, "
                f"{结果.get('diagnostic') or '未生成受控诊断'}"
            )
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

