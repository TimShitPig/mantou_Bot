"""聊天媒体的类型、附件索引与范围校验，独立于云盘供应方。"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

def _媒体种类(项目: dict[str, Any]) -> str:
    类型 = str(项目.get("type") or 项目.get("media_type") or "").lower()
    MIME = str(项目.get("content_type") or "").lower()
    if 类型 in {"图片", "image", "img"} or MIME.startswith("image/"):
        return "image"
    if 类型 in {"视频", "video"} or MIME.startswith("video/"):
        return "video"
    if 类型 in {"语音", "音频", "audio", "voice"} or MIME.startswith("audio/"):
        return "audio"
    if 类型 in {"文件", "file", "document"} or 项目.get("src") or 项目.get("url") or 项目.get("download_url"):
        return "file"
    return ""


def _媒体项目列表(媒体: Any, *, 可下载: bool = True) -> list[tuple[int, dict[str, Any]]]:
    if not isinstance(媒体, dict):
        return []
    项目列表 = 媒体.get("items")
    if not isinstance(项目列表, list) or not 项目列表:
        项目列表 = [媒体]
    return [(索引, 项目) for 索引, 项目 in enumerate(项目列表)
            if isinstance(项目, dict) and _媒体种类(项目)
            and (not 可下载 or str(项目.get("src") or 项目.get("url") or 项目.get("download_url") or "").startswith(("http://", "https://")))]


def 识别图片类型(前缀: bytes, 响应类型: Any = "") -> str:
    if 前缀.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if 前缀.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if 前缀.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(前缀) >= 12 and 前缀[:4] == b"RIFF" and 前缀[8:12] == b"WEBP":
        return "image/webp"
    if 前缀.startswith(b"BM"):
        return "image/bmp"
    if 前缀.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if 前缀.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"
    if len(前缀) >= 12 and 前缀[4:8] == b"ftyp":
        if any(标识 in 前缀[8:64] for 标识 in (b"avif", b"avis")):
            return "image/avif"
        if any(标识 in 前缀[8:64] for 标识 in (b"heic", b"heix", b"heif", b"mif1")):
            return "image/heif"
    return ""


def 识别媒体类型(前缀: bytes, 响应类型: Any = "", *, 预期种类: str = "") -> str:
    if 前缀 and 预期种类 == "file":
        return "application/octet-stream"
    图片类型 = 识别图片类型(前缀)
    if 图片类型:
        return 图片类型 if 预期种类 not in {"video", "audio"} else ""
    视频类型 = ""
    if len(前缀) >= 12 and 前缀[4:8] == b"ftyp":
        if 预期种类 == "audio" or b"M4A " in 前缀[8:64]:
            return "audio/mp4" if 预期种类 not in {"image", "video"} else ""
        视频类型 = "video/quicktime" if 前缀[8:12] == b"qt  " else "video/mp4"
    elif 前缀.startswith(b"\x1aE\xdf\xa3"):
        视频类型 = "video/webm" if b"webm" in 前缀.lower() else "video/x-matroska"
    elif 前缀.startswith(b"RIFF") and 前缀[8:12] == b"AVI ":
        视频类型 = "video/x-msvideo"
    elif 前缀.startswith(b"FLV"):
        视频类型 = "video/x-flv"
    elif 前缀.startswith(b"OggS") and b"theora" in 前缀.lower():
        视频类型 = "video/ogg"
    elif 前缀.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3")):
        视频类型 = "video/mpeg"
    if 视频类型:
        return 视频类型 if 预期种类 not in {"image", "audio"} else ""
    音频类型 = ""
    if 前缀.startswith(b"RIFF") and 前缀[8:12] == b"WAVE":
        音频类型 = "audio/wav"
    elif 前缀.startswith(b"ID3") or (len(前缀) >= 2 and 前缀[0] == 0xff and 前缀[1] & 0xe0 == 0xe0):
        音频类型 = "audio/mpeg"
    elif 前缀.startswith(b"fLaC"):
        音频类型 = "audio/flac"
    elif 前缀.startswith((b"#!AMR", b"#!AMR-WB")):
        音频类型 = "audio/amr"
    elif 前缀.startswith((b"#!SILK", b"\x02#!SILK")):
        音频类型 = "audio/silk"
    elif 前缀.startswith(b"OggS"):
        音频类型 = "audio/ogg"
    if 音频类型:
        return 音频类型 if 预期种类 not in {"image", "video"} else ""
    # QQ 新格式未覆盖文件头时，只接受已声明的媒体 MIME，排除错误 HTML/JSON。
    类型 = str(响应类型 or "").split(";", 1)[0].strip().lower()
    if 类型 == "image/svg+xml" and (b"<svg" in 前缀.lower() or 前缀.lstrip().startswith(b"<?xml")) and 预期种类 != "video":
        return 类型
    if 前缀 and not 前缀.lstrip().startswith((b"<", b"{", b"[")) and re.fullmatch(r"(?:image|video|audio)/[a-z0-9.+-]+", 类型):
        return 类型 if not 预期种类 or 类型.startswith(预期种类 + "/") else ""
    if 前缀 and 预期种类 in {"image", "audio", "video"} and not 前缀.lstrip().startswith((b"<", b"{", b"[")):
        return 预期种类 + "/x-unknown"
    return ""


def _图片扩展名(内容类型: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
            "image/webp": ".webp", "image/bmp": ".bmp", "image/avif": ".avif",
            "image/heif": ".heif", "image/tiff": ".tiff", "image/x-icon": ".ico", "image/svg+xml": ".svg",
            "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm",
            "video/x-matroska": ".mkv", "video/x-msvideo": ".avi", "video/x-flv": ".flv",
            "video/ogg": ".ogv", "video/mpeg": ".mpeg", "audio/wav": ".wav",
            "audio/mpeg": ".mp3", "audio/flac": ".flac", "audio/ogg": ".ogg",
            "audio/amr": ".amr", "audio/silk": ".silk"}.get(内容类型, ".bin")


def _原附件后缀(项目: dict[str, Any], 内容类型: str) -> str:
    # 不以 .jpg 白名单限制归档；未知后缀装在真实 ZIP 内，原字节不变。
    名称 = str(项目.get("name") or 项目.get("filename") or "")
    if not 名称:
        名称 = urlsplit(str(项目.get("src") or 项目.get("url") or "")).path.rsplit("/", 1)[-1]
    后缀 = Path(名称).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{1,16}", 后缀):
        return 后缀
    return _图片扩展名(内容类型)


def 解析媒体范围(范围: str, 大小: int) -> tuple[int, int, bool]:
    if 大小 <= 0:
        raise ValueError("media_size_invalid")
    if not 范围:
        return 0, 大小 - 1, False
    匹配 = re.fullmatch(r"bytes=(\d*)-(\d*)", 范围.strip())
    if not 匹配 or not any(匹配.groups()):
        raise ValueError("range_invalid")
    首, 尾 = 匹配.groups()
    if not 首:
        长度 = int(尾)
        if 长度 <= 0:
            raise ValueError("range_invalid")
        return max(0, 大小 - 长度), 大小 - 1, True
    起点 = int(首)
    终点 = min(大小 - 1, int(尾)) if 尾 else 大小 - 1
    if 起点 >= 大小 or 终点 < 起点:
        raise ValueError("range_invalid")
    return 起点, 终点, True
