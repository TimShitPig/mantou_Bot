"""小说正文写入 TXT 前的通用文本处理。"""

from __future__ import annotations

import re


def 去除章节正文重复标题(标题: object, 正文: object) -> str:
    """删除正文首行中与章节标题完全相同的重复标题。"""
    文本 = str(正文 or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    标题文本 = str(标题 or "").strip()
    if not 文本 or not 标题文本:
        return 文本

    行列表 = 文本.split("\n")
    首行 = 行列表[0].strip().lstrip("\ufeff")
    if _标题比较值(首行) != _标题比较值(标题文本):
        return 文本
    return "\n".join(行列表[1:]).lstrip("\n").strip()


def _标题比较值(文本: str) -> str:
    return re.sub(r"\s+", "", str(文本 or "")).strip()
