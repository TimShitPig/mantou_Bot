"""番茄小说下载功能。

仅保留番茄小说 TXT 下载和 QQ 文件发送，正文下载使用番茄畅听接口。
不包含音频、媒体、搜索、命令行调试和抓包请求逻辑。
"""

from __future__ import annotations

import asyncio
import base64
from contextlib import AsyncExitStack
import gzip
import hashlib
import html
import json
import os
import re
import secrets
import socket
import ssl
import struct
import threading
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import aiohttp
except Exception:
    aiohttp = None

try:
    import httpx
except Exception:
    httpx = None

try:
    from Crypto.Cipher import AES as PYCRYPTODOME_AES
except Exception:
    PYCRYPTODOME_AES = None

try:
    import gmpy2
except Exception:
    gmpy2 = None

try:
    from astrbot.api import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

try:
    from 功能文件.管理功能.网盘功能 import 小说网盘
except Exception as 异常:
    小说网盘 = None
    logger.warning(f"小说网盘模块加载失败, 错误={异常}")

try:
    from 功能文件.管理功能.网盘功能 import 百度网盘
except Exception as 异常:
    百度网盘 = None
    logger.warning(f"百度网盘模块加载失败, 错误={异常}")

from 功能文件.管理功能.小说功能.功能 import 下载缓存清理 as 小说缓存工具
from 功能文件.管理功能.小说功能.功能.文本处理 import 去除章节正文重复标题

# 正文接口按章节 ID 解析内容，固定一个已可用的请求书籍上下文以兼容已下线的书籍记录。
NOVELFM_REQUEST_BOOK_ID = os.environ.get(
    "FANQIE_NOVELFM_REQUEST_BOOK_ID", "7320841644486446142"
).strip() or "7320841644486446142"


# ===== 番茄畅听签名算法 =====
SIGN_KEY32_3040 = bytes.fromhex("4e54b707757a4c15473ba0ba01740ed1b3eac6088de0441fbaf79d28dee33ddf")

def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()

def u32le(x: int) -> bytes:
    return struct.pack("<I", x & 0xFFFFFFFF)

def proto_varint(n: int) -> bytes:
    n = int(n)
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)

def _proto_read_varint(data: bytes | bytearray, offset: int = 0) -> tuple[int, int]:
    """Read protobuf varint and return `(value, next_offset)`."""
    value = 0
    shift = 0
    i = offset
    while i < len(data):
        b = data[i]
        i += 1
        value |= (b & 0x7F) << shift
        if b < 0x80:
            return value, i
        shift += 7
        if shift > 70:
            raise ValueError("protobuf varint too long")
    raise ValueError("truncated protobuf varint")

def proto_key(field_no: int, wire_type: int) -> bytes:
    return proto_varint((field_no << 3) | wire_type)

def proto_field_varint(field_no: int, value: int) -> bytes:
    return proto_key(field_no, 0) + proto_varint(value)

def proto_field_bytes(field_no: int, value: bytes | str) -> bytes:
    if isinstance(value, str):
        value = value.encode()
    return proto_key(field_no, 2) + proto_varint(len(value)) + value


def proto_field_fixed32(field_no: int, value: int | bytes) -> bytes:
    raw = value if isinstance(value, bytes) else int(value).to_bytes(4, "little")
    return proto_key(field_no, 5) + raw



IV = [
    0x7380166F, 0x4914B2B9, 0x172442D7, 0xDA8A0600,
    0xA96F30BC, 0x163138AA, 0xE38DEE4D, 0xB0FB0E4E,
]

def _rol(x: int, n: int) -> int:
    x &= 0xFFFFFFFF
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

def _p0(x: int) -> int:
    return x ^ _rol(x, 9) ^ _rol(x, 17)

def _p1(x: int) -> int:
    return x ^ _rol(x, 15) ^ _rol(x, 23)

def sm3(data: bytes) -> bytes:
    msg = bytearray(data)
    bit_len = len(msg) * 8
    msg.append(0x80)
    while (len(msg) % 64) != 56:
        msg.append(0)
    msg += bit_len.to_bytes(8, "big")

    v = IV[:]
    for off in range(0, len(msg), 64):
        block = msg[off:off+64]
        w = [int.from_bytes(block[i:i+4], "big") for i in range(0, 64, 4)]
        for j in range(16, 68):
            w.append(_p1(w[j-16] ^ w[j-9] ^ _rol(w[j-3], 15)) ^ _rol(w[j-13], 7) ^ w[j-6])
        w1 = [w[j] ^ w[j+4] for j in range(64)]
        a, b, c, d, e, f, g, h = v
        for j in range(64):
            tj = 0x79CC4519 if j <= 15 else 0x7A879D8A
            ss1 = _rol((_rol(a, 12) + e + _rol(tj, j % 32)) & 0xFFFFFFFF, 7)
            ss2 = ss1 ^ _rol(a, 12)
            if j <= 15:
                ff = a ^ b ^ c
                gg = e ^ f ^ g
            else:
                ff = (a & b) | (a & c) | (b & c)
                gg = (e & f) | ((~e) & g)
            tt1 = (ff + d + ss2 + w1[j]) & 0xFFFFFFFF
            tt2 = (gg + h + ss1 + w[j]) & 0xFFFFFFFF
            d = c
            c = _rol(b, 9)
            b = a
            a = tt1
            h = g
            g = _rol(f, 19)
            f = e
            e = _p0(tt2)
        v = [x ^ y for x, y in zip(v, [a, b, c, d, e, f, g, h])]
    return b"".join(x.to_bytes(4, "big") for x in v)

def x_argus(khronos: int | None = None) -> str:
    if khronos is None:
        khronos = int(time.time())
    return b64(u32le(khronos))



def reverse_xor(reverse_source: bytes, key4: bytes) -> bytes:
    """first_intermediate = reverse(source) xor repeating key4."""
    if len(key4) != 4:
        raise ValueError("key4 must be 4 bytes")
    n = len(reverse_source)
    return bytes(reverse_source[n - 1 - i] ^ key4[i & 3] for i in range(n))

STAGE34A_FINALIZER_TARGET_BITS = (6, 5, 3, 4, 2, 7, 1, 0)

STAGE34A_FINALIZER_CONTROL_BIT_BY_TARGET = (1, 7, 3, 6, 2, 0, 4, 5)

MEDUSA3040_F2_BYTE_PER_BIT = (7, 5, 6, 2, 4, 0, 3, 1)

MEDUSA3040_F2_BIT_BASE = (4, 0, 3, 1, 2, 7, 6, 5)

def medusa3040_prefix20(khronos: int) -> bytes:
    """3040 X-Medusa raw prefix[0:20] = khronos_le XOR five constants."""
    k = int(khronos) & 0xFFFFFFFF
    return b"".join(((k ^ item) & 0xFFFFFFFF).to_bytes(4, "little") for item in (
        0x00000005,
        0xCA4F4B2D,
        0x430D7549,
        0x2CAEB53F,
        0x56CC6D22,
    ))

def stage34a_finalizer_after_bits_from_control(control: int) -> int:
    value = 0
    current = int(control) & 0xFF
    for target_index, source_bit in enumerate(STAGE34A_FINALIZER_CONTROL_BIT_BY_TARGET):
        value |= ((current >> int(source_bit)) & 1) << target_index
    return value & 0xFF

def apply_stage34a_finalizer_control(chunk8: bytes | bytearray | memoryview, control: int) -> bytes:
    raw = bytearray(bytes(chunk8))
    if len(raw) != 8:
        raise ValueError("stage34a finalizer chunk must be exactly 8 bytes")
    after_bits = stage34a_finalizer_after_bits_from_control(control)
    for index, target_bit in enumerate(STAGE34A_FINALIZER_TARGET_BITS):
        mask = 1 << int(target_bit)
        if (after_bits >> index) & 1:
            raw[index] |= mask
        else:
            raw[index] &= (~mask) & 0xFF
    return bytes(raw)

def stage34a_finalizer_control_from_target_bits(chunk8: bytes | bytearray | memoryview) -> int:
    raw = bytes(chunk8)
    if len(raw) != 8:
        raise ValueError("stage34a finalizer chunk must be exactly 8 bytes")
    after_bits = 0
    for index, target_bit in enumerate(STAGE34A_FINALIZER_TARGET_BITS):
        after_bits |= ((raw[index] >> int(target_bit)) & 1) << index
    control = 0
    for target_index, source_bit in enumerate(STAGE34A_FINALIZER_CONTROL_BIT_BY_TARGET):
        control |= ((after_bits >> target_index) & 1) << int(source_bit)
    return control & 0xFF

def stage34a_prefinalizer_prefix248_from_head9_and_stage33f(
    head9: bytes | bytearray | memoryview,
    stage33f: bytes | bytearray | memoryview,
) -> bytes:
    head = bytes(head9)
    source = bytes(stage33f)
    if len(head) != 9:
        raise ValueError("stage34a head must be exactly 9 bytes")
    if len(source) < 239:
        raise ValueError("stage33f must contain at least 239 bytes")
    return head + source[:239]

def finalizer_copy_source31_from_stage34a_prefix248(prefix248: bytes | bytearray | memoryview) -> bytes:
    raw = bytes(prefix248)
    if len(raw) != 31 * 8:
        raise ValueError("stage34a pre-finalizer prefix must be exactly 248 bytes")
    return bytes(stage34a_finalizer_control_from_target_bits(raw[i:i + 8]) for i in range(0, 31 * 8, 8))

def finalizer_copy_source31_from_head9_and_stage33f(
    head9: bytes | bytearray | memoryview,
    stage33f: bytes | bytearray | memoryview,
) -> bytes:
    return finalizer_copy_source31_from_stage34a_prefix248(
        stage34a_prefinalizer_prefix248_from_head9_and_stage33f(head9, stage33f)
    )

def apply_stage34a_finalizer_control31(
    prefix248: bytes | bytearray | memoryview,
    control31: bytes | bytearray | memoryview,
) -> bytes:
    prefix = bytes(prefix248)
    control = bytes(control31)
    if len(prefix) != 31 * 8:
        raise ValueError("stage34a finalizer prefix must be exactly 248 bytes")
    if len(control) < 31:
        raise ValueError("stage34a finalizer control must contain at least 31 bytes")
    out = bytearray()
    for index in range(31):
        out.extend(apply_stage34a_finalizer_control(prefix[index * 8:(index + 1) * 8], control[index]))
    return bytes(out)

def stage34a_tail_fields_from_rand3(rand3: int) -> tuple[int, bytes]:
    high2 = ((int(rand3) >> 16) & 0xFFFF).to_bytes(2, "little")
    # Current 3040 appends only the two high-rand bytes at the end of the
    # stage34a body.  Older notes treated this as `low, high, NUL`; live
    # 6.5.6.32 traces show the byte before these two bytes still belongs to
    # stage33f, and the final two bytes are exactly high16(rand3) little-endian.
    return high2[0], high2[1:2]

def stage33f_to_stage34a_with_control(
    stage33f: bytes | bytearray | memoryview,
    head9: bytes | bytearray | memoryview,
    control31: bytes | bytearray | memoryview,
    *,
    rand3: int | None = None,
    tail_marker: int | None = None,
    tail2: bytes | bytearray | memoryview | None = None,
) -> bytes:
    source = bytes(stage33f)
    if len(source) < 240:
        raise ValueError("stage33f must contain at least 240 bytes")
    if rand3 is not None:
        tail_marker, tail2 = stage34a_tail_fields_from_rand3(int(rand3))
    if tail_marker is None or tail2 is None:
        raise ValueError("either rand3 or tail_marker/tail2 must be supplied")
    suffix = bytes(tail2)
    if len(suffix) not in {1, 2}:
        raise ValueError("stage34a tail2 must be one or two bytes")
    prefix248 = stage34a_prefinalizer_prefix248_from_head9_and_stage33f(head9, source)
    finalized_prefix = apply_stage34a_finalizer_control31(prefix248, control31)
    return finalized_prefix + source[239:-1] + bytes([int(tail_marker) & 0xFF]) + suffix

def medusa3040_f2_scatter(pre_slot8: bytes | bytearray | memoryview, slot10: bytes | bytearray | memoryview, count: int = 19) -> bytes:
    """Pure Python equivalent of the current 3040 late F2 bit scatter."""
    out = bytearray(bytes(pre_slot8))
    source = bytes(slot10)
    for source_index in range(min(int(count), len(source))):
        for source_bit in range(8):
            dest_byte = 8 * source_index + MEDUSA3040_F2_BYTE_PER_BIT[source_bit]
            if dest_byte >= len(out):
                continue
            dest_bit = MEDUSA3040_F2_BIT_BASE[source_bit]
            value = (source[source_index] >> source_bit) & 1
            out[dest_byte] = (out[dest_byte] & ~(1 << dest_bit)) | (value << dest_bit)
    return bytes(out)

def medusa3040_f2_recover_slot10(post_slot8: bytes | bytearray | memoryview, count: int = 19) -> bytes:
    """Recover the F2 slot10 bytes that are visible in a final X-Medusa body."""
    post = bytes(post_slot8)
    out = bytearray(int(count))
    for source_index in range(int(count)):
        value = 0
        for source_bit in range(8):
            dest_byte = 8 * source_index + MEDUSA3040_F2_BYTE_PER_BIT[source_bit]
            if dest_byte >= len(post):
                continue
            dest_bit = MEDUSA3040_F2_BIT_BASE[source_bit]
            value |= ((post[dest_byte] >> dest_bit) & 1) << source_bit
        out[source_index] = value
    return bytes(out)

CONTROL32_SBOX_3892_3040 = bytes.fromhex(
    "38922563e36406d37a24100b7902a028044e218453c2a399199c9d13dc40c55b"
    "a67e502273850ebdc1a2e2188b8f2d9e3cb909b8c46a2a9f4a6dd93007eafa"
    "65b7b3a881aa908cc74f0ad76bbbb58617c37012ca05a469fd44e62eecf1e"
    "4272ce860c0ae5eadf99b20d8f0234174006f3f110d7657d01645d4eff8f714"
    "71cbfe1cb2f52648727bf3c9de55153e031b4d61757db63dbf7782eeafe9018"
    "a8891362fb14759ac32bab03b349aeb5a377c5156be4c8dfbe13a684bda39cf"
    "836697c894545fe0f2491acea9fc6252f4ff1e0fe72bd2df6e67a7f635e5bc"
    "c6d1a5dd951d89960887a18eb40c785cdb1f80ed42299333ab98cdd67f316c"
    "d54346585dcc"
)

CONTROL32_SBOX_5329_3040 = bytes.fromhex(
    "53290fe9e51f316f90f74a7e034d367784ab49237cd0135cdc632c322fd3be0e"
    "2624a417ecd9151a7ff64f60730a87f9445ec6ada2f865d22b696c4188f24c"
    "0df37b75510b939f6bc2fe6883e68bc8c722181ba0bdb08c9871b50c9a16"
    "b46eea8eed20ba4b8a14e0fcf1468dbbef05a93e5a9d7dcf06898635c1f"
    "d99f5de287a80c594daaab19b6279fbd75070cb52eb2555c456e39e78398"
    "53874e2f0013ac0b64742d8ca10e4b79c955de8b843ce4ed464a6a72ed5"
    "08091c92e7b3eedd1e1dd12afac321618fa3d65f9167c982f43d66a53c6"
    "a1997585b346dbf9672ff37cdbc073b2dae11453304df00815476b2a13fcc"
    "db30b957a8acafe1274002485912"
)

CONTROL32_SBOX_D09A_3040 = bytes.fromhex(
    "d09a515ba58cbbab3e37b09fd4f6d9244df80512e84cd7956be301cf64f1429d"
    "58577cc241f3a2c655144f81aaf95a4e108da894b38970561ae9002619fbbac9"
    "1fa922ed202bfc62cb08e0de2a7f3631435f8b47c8a3c563b4db4071ce74c46d"
    "a6fa696a9e282d1e825d663b93bfd56c48dce1884bb10fccea063929f746443"
    "fd830a4232e53da21a1f2d1bdfebc3a02c10a1b8ad31d04fd616590d272ac"
    "737e98eb33af60528716bee78ec0ee8699031177277d9cff32542c67caf5f44"
    "591681335ae0e178f3409a7803db83892dde5b9b7f0c750e24aef077badd6"
    "78a09b850b84ec1597e4963cb5e675df1c0d6fb618496ecd76c35c79832559"
    "0c2fb27a5e"
)

CONTROL32_MD5_SIGN_KEY_HALF_3040 = hashlib.md5(SIGN_KEY32_3040[16:32]).digest()

CONTROL32_3892_ORDER = (1, 3, 2, 0)

CONTROL32_3892_SHIFT = (0, 9, 14, 11, 4, 13, 2, 3, 8, 1, 6, 15, 12, 5, 10, 7)

CONTROL32_3892_MIX_OUT_COLS = (3, 0, 2, 1)

CONTROL32_3892_K0_RAW = bytes.fromhex("335d5f2dfc59c1543d880c5519c489e6")

CONTROL32_3892_MID_RAW = bytes.fromhex("4c83d1b1b0da10e58d521cb094969556")

CONTROL32_3892_B_RAW = bytes.fromhex("583cb88ce8e6a86965b4b4d9f122218f")

CONTROL32_3892_FINAL_XOR = bytes.fromhex("4c83d1b1b0da10e58d521cb094969556")

CONTROL32_FULL_MGET_PROFILES_3040 = {
    "5329": {
        "sbox": CONTROL32_SBOX_5329_3040,
        "order": (2, 0, 3, 1),
        "shift": (0, 9, 14, 15, 4, 13, 2, 7, 8, 1, 6, 3, 12, 5, 10, 11),
        "mix_out_cols": (1, 3, 0, 2),
        "k0_raw": bytes.fromhex("1a0e8942d50a173b14dbda3a30975f89"),
        "mid_raw": bytes.fromhex("fde4720628ee653d3c35bf070ca2e08e"),
        "b_raw": bytes.fromhex("0a58200522b645381e83fa3f12211ab1"),
        "final_xor": bytes.fromhex("fde4720628ee653d3c35bf070ca2e08e"),
    },
    "3892": {
        "sbox": CONTROL32_SBOX_3892_3040,
        "order": CONTROL32_3892_ORDER,
        "shift": CONTROL32_3892_SHIFT,
        "mix_out_cols": CONTROL32_3892_MIX_OUT_COLS,
        "k0_raw": CONTROL32_3892_K0_RAW,
        "mid_raw": CONTROL32_3892_MID_RAW,
        "b_raw": CONTROL32_3892_B_RAW,
        "final_xor": CONTROL32_3892_FINAL_XOR,
    },
    "d09a": {
        "sbox": CONTROL32_SBOX_D09A_3040,
        "order": (2, 3, 1, 0),
        "shift": (0, 9, 14, 15, 4, 13, 2, 3, 8, 1, 6, 11, 12, 5, 10, 7),
        "mix_out_cols": (3, 2, 0, 1),
        "k0_raw": bytes.fromhex("a171c4706e755a09afa497088be812bb"),
        "mid_raw": bytes.fromhex("b57431cddb016bc474a5fcccff4dee77"),
        "b_raw": bytes.fromhex("321bfd93e91a96579dbf6a9b62f284ec"),
        "final_xor": bytes.fromhex("b57431cddb016bc474a5fcccff4dee77"),
    },
}

def _control32_reorder_u32_blocks_3040(block16: bytes, order: tuple[int, int, int, int]) -> bytes:
    if len(block16) != 16:
        raise ValueError("block16 must be exactly 16 bytes")
    return bytes(block16[4 * group + int(order[index])] for group in range(4) for index in range(4))

def _control32_subbytes_group_permuted_3040(block16: bytes, sbox: bytes, group_perm: tuple[int, int, int, int]) -> bytes:
    if len(block16) != 16:
        raise ValueError("block16 must be exactly 16 bytes")
    substituted = bytes(sbox[value] for value in block16)
    return b"".join(substituted[4 * int(group):4 * int(group) + 4] for group in group_perm)

def _control32_mix_column(col: list[int]) -> list[int]:
    a0, a1, a2, a3 = [x & 0xFF for x in col]
    return [
        _gf256_mul_aes(a0, 2) ^ _gf256_mul_aes(a1, 3) ^ a2 ^ a3,
        a0 ^ _gf256_mul_aes(a1, 2) ^ _gf256_mul_aes(a2, 3) ^ a3,
        a0 ^ a1 ^ _gf256_mul_aes(a2, 2) ^ _gf256_mul_aes(a3, 3),
        _gf256_mul_aes(a0, 3) ^ a1 ^ a2 ^ _gf256_mul_aes(a3, 2),
    ]

def _control32_mix_columns_profile_3040(block16: bytes, out_cols: tuple[int, int, int, int]) -> bytes:
    if len(block16) != 16:
        raise ValueError("block16 must be exactly 16 bytes")
    out = bytearray(16)
    for in_col, out_col in enumerate(out_cols):
        mixed = _control32_mix_column([block16[in_col + 4 * row] for row in range(4)])
        for row, val in enumerate(mixed):
            out[int(out_col) + 4 * row] = val & 0xFF
    return bytes(out)

def _xor_same_len(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("xor inputs must have the same length")
    return bytes(a ^ b for a, b in zip(left, right))

def _control32_profile_3040(profile: str):
    name = str(profile or "3892").strip().lower()
    aliases = {"default": "3892", "current": "d09a", "latest": "d09a", "53290f": "5329", "389225": "3892", "d09a51": "d09a"}
    name = aliases.get(name, name)
    if name not in CONTROL32_FULL_MGET_PROFILES_3040:
        raise ValueError(f"unknown 3040 control32 profile: {profile!r}")
    return name, CONTROL32_FULL_MGET_PROFILES_3040[name]

def _control32_half_transform_profile_3040(block16: bytes, profile_data) -> bytes:
    order = tuple(profile_data["order"])
    k0 = _control32_reorder_u32_blocks_3040(profile_data["k0_raw"], order)
    mid = _control32_reorder_u32_blocks_3040(profile_data["mid_raw"], order)
    b_region = _control32_reorder_u32_blocks_3040(profile_data["b_raw"], order)
    x = _xor_same_len(block16, k0)
    x = _control32_subbytes_group_permuted_3040(x, profile_data["sbox"], order)
    x = bytes(x[index] for index in tuple(profile_data["shift"]))
    x = _control32_mix_columns_profile_3040(x, tuple(profile_data["mix_out_cols"]))
    x = _xor_same_len(x, mid)
    x = _control32_subbytes_group_permuted_3040(x, profile_data["sbox"], order)
    x = bytes(x[index] for index in tuple(profile_data["shift"]))
    x = _xor_same_len(x, b_region)
    return _xor_same_len(x, profile_data["final_xor"])

def medusa3040_control32_profile_from_random32(
    random32: bytes | bytearray | memoryview,
    *,
    profile: str = "3892",
    force_last: int = 1,
) -> bytes:
    """3040/full-mget control32 generator for recovered profiles 5329/3892/d09a."""
    _name, profile_data = _control32_profile_3040(profile)
    state = bytearray(bytes(random32))
    if len(state) != 32:
        raise ValueError("random32 must be exactly 32 bytes")
    state[31] = int(force_last) & 0xFF
    for i, v in enumerate(CONTROL32_MD5_SIGN_KEY_HALF_3040):
        state[i] ^= v
    first16 = _control32_half_transform_profile_3040(bytes(state[:16]), profile_data)
    second_pre = _xor_same_len(bytes(state[16:32]), first16)
    return first16 + _control32_half_transform_profile_3040(second_pre, profile_data)

def medusa3040_control32_3892_from_random32(
    random32: bytes | bytearray | memoryview,
    *,
    force_last: int = 1,
) -> bytes:
    """3040/full-mget control32 profile `3892`, pure Python.

    Current 6.5.6.32 sets byte31 to 1.  The older server-accepted 6.4.4.32
    profile uses the same transform but sets byte31 to 0x41.
    """
    return medusa3040_control32_profile_from_random32(random32, profile="3892", force_last=force_last)

def medusa3040_control32_3892_legacy41_from_random32(random32: bytes | bytearray | memoryview) -> bytes:
    return medusa3040_control32_3892_from_random32(random32, force_last=0x41)

def medusa3040_head9_from_query_rand4_byte(
    query: bytes | bytearray | memoryview | str,
    rand4: int,
    head_byte: int = 1,
) -> bytes:
    """Build the current full/mget head9 when the head byte is separate.

    Live 6.5.6.32 traces show the suffix byte used here is not always the
    first byte of source336.field13.  For the current full/mget family it is
    stable as low6 == 1.
    """
    q = query.encode("ascii") if isinstance(query, str) else bytes(query)
    suffix = ((0x18 & 0xFF) << 24) | ((sm3(q)[0] & 0x3F) << 14) | ((int(head_byte) & 0x3F) << 8) | 1
    return b"\x8a" + (int(rand4) & 0xFFFFFFFF).to_bytes(4, "little") + suffix.to_bytes(4, "little")

SOURCE336_ALLOC_SIZE = 0x400

SOURCE336_FIELD1_FIXED_SEED = bytes.fromhex("2d4b4fca49750d433fb5ae2c226dcc56")

SOURCE336_MSSDK_VERSION = b"v04.09.09-ml-android"

SOURCE336_REPORT_VERSION = b"v04.09.09.01-bugfix"

SOURCE336_NOT_SET = b"!notset!"

SOURCE336_3040_MSSDK_LICENSE = b"1532254240"

SOURCE336_3040_DEVICE_INSTALL_ID = b"AOpP2oWXxrKyOifBQBXX_Rjlc"

SOURCE336_3040_TIMEZONE = b"Asia/Shanghai,8"

SOURCE336_3040_LOCALE = b"zh_CN"

SOURCE336_3040_PHYSICAL_SIZE = b"Physical size: 1440x2560"

SOURCE336_3040_DEVICE_TYPE = b"SM-S9260"

SOURCE336_3040_DEVICE_BRAND = b"Samsung"

SOURCE336_3040_SOC_MODEL = b"marlin"

SOURCE336_3040_HARDWARE = b"qcom"

SOURCE336_3040_FIELD23_SENTINEL = 1_777_775

def source336_3040_field15_message(
    *,
    field1: int = 190,
    field2: int = 8,
    field3: int = 1_388_734,
    field4: int | None = None,
    field5: int = 716_836_180,
) -> bytes:
    out = bytearray()
    out += proto_field_varint(1, int(field1))
    out += proto_field_varint(2, int(field2))
    out += proto_field_varint(3, int(field3))
    if field4 is not None:
        out += proto_field_varint(4, int(field4))
    out += proto_field_varint(5, int(field5))
    return bytes(out)

def source336_3040_metrics_json(
    *,
    cmr: int = 16_777_216,
    cmr2: int = 16_777_216,
    un_h: int = 1_884_036_224,
    vpn: int = 0,
    sts: int = 32_251,
    kd: int = 0,
    fkd: int = 842_674_847,
    pd: int = -575_868_740,
    lp: str = "2|520830913191|522717356745|2089099191808|129984601251936",
    fl: str = "0|0|737340615|3344993835|2856852299|859378443|1595182919|0|0|0",
    dyn: str = "",
    do: int = 0,
    tk: bool = True,
) -> bytes:
    tk_text = "true" if bool(tk) else "false"
    return (
        f'{{"cmr":{int(cmr)},"cmr2":{int(cmr2)},"un_h":{int(un_h)},"vpn":{int(vpn)},'
        f'"sts":{int(sts)},"kd":{int(kd)},"fkd":{int(fkd)},"pd":{int(pd)},'
        f'"lp":"{str(lp)}","fl":"{str(fl)}","dyn":"{str(dyn)}","do":{int(do)},"tk":{tk_text}}}'
    ).encode("utf-8")

def _bswap32(value: int) -> int:
    return int.from_bytes((int(value) & 0xFFFFFFFF).to_bytes(4, "little"), "big")

def source336_3040_metrics_fl_from_words(
    *,
    fl2: int,
    fl4: int,
    fl5: int,
    fl6: int,
    ladon_raw: bytes | bytearray | memoryview | None = None,
    fl9: int = 0,
) -> str:
    raw = bytes(ladon_raw or b"")
    last = int(fl9)
    if raw:
        if len(raw) != 4:
            raise ValueError("ladon raw must be exactly 4 bytes")
        last = int.from_bytes(raw, "big")
    return "|".join(str(x) for x in (0, 0, int(fl2) & 0xFFFFFFFF, _bswap32(fl2), int(fl4) & 0xFFFFFFFF, int(fl5) & 0xFFFFFFFF, int(fl6) & 0xFFFFFFFF, 0, 0, last & 0xFFFFFFFF))

def _query_value_bytes(url: str, key: str, default: str = "") -> bytes:
    for current_key, current_value in urllib.parse.parse_qsl(urllib.parse.urlsplit(str(url)).query, keep_blank_values=True):
        if current_key == key:
            return current_value.encode("utf-8")
    return default.encode("utf-8")

def source336_3040_nested_device_message(
    url: str,
    *,
    timestamp_base: int,
    field16: int = 1_111_836_827,
    field17: int = 1_111_724_915,
    field18: int = 1_085_939_368,
    field19: int = 1_083_679_440,
    field20: int = 1_117_544_273,
    field21: int = 1_116_735_557,
    field25: int = 3_565_709_330_792,
    field26: int = 0,
    field27: int = 0,
    field28: int | None = None,
    field40: int = 0,
) -> bytes:
    base_ms = int(timestamp_base) * 1000
    if not field26:
        field26 = base_ms - 40_250
    if not field27:
        field27 = base_ms - 1_482_000
    if field28 is None:
        field28 = base_ms + 3_534
    if not field40:
        field40 = base_ms - 40_796
    out = bytearray()
    out += proto_field_varint(1, 2)
    out += proto_field_varint(2, 4)
    out += proto_field_bytes(3, _query_value_bytes(url, "aid", "3040"))
    out += proto_field_bytes(4, _query_value_bytes(url, "device_id", ""))
    out += proto_field_bytes(5, SOURCE336_3040_DEVICE_INSTALL_ID)
    out += proto_field_bytes(6, b"!noperm!")
    out += proto_field_varint(7, SOURCE336_3040_FIELD23_SENTINEL)
    out += proto_field_varint(8, SOURCE336_3040_FIELD23_SENTINEL)
    out += proto_field_varint(9, 4)
    out += proto_field_varint(10, SOURCE336_3040_FIELD23_SENTINEL)
    out += proto_field_bytes(11, SOURCE336_NOT_SET)
    out += proto_field_bytes(12, SOURCE336_3040_TIMEZONE)
    out += proto_field_bytes(13, SOURCE336_3040_LOCALE)
    out += proto_field_varint(14, 12)
    out += proto_field_bytes(15, SOURCE336_3040_PHYSICAL_SIZE)
    for no, val in ((16, field16), (17, field17), (18, field18), (19, field19), (20, field20), (21, field21)):
        out += proto_field_fixed32(no, int(val))
    out += proto_field_bytes(22, b"9")
    out += proto_field_varint(23, 204)
    out += proto_field_varint(24, 10)
    for no, val in ((25, field25), (26, field26), (27, field27), (28, field28), (29, 1)):
        out += proto_field_varint(no, int(val))
    out += proto_field_bytes(30, SOURCE336_3040_DEVICE_TYPE)
    out += proto_field_bytes(31, SOURCE336_3040_DEVICE_BRAND)
    out += proto_field_bytes(32, SOURCE336_3040_DEVICE_TYPE)
    out += proto_field_bytes(33, SOURCE336_3040_DEVICE_TYPE)
    out += proto_field_bytes(34, SOURCE336_3040_SOC_MODEL)
    out += proto_field_bytes(35, SOURCE336_3040_DEVICE_BRAND)
    out += proto_field_bytes(36, SOURCE336_3040_HARDWARE)
    out += proto_field_varint(38, 62)
    out += proto_field_varint(40, int(field40))
    return bytes(out)

def source336_3040_nested_report_message_accepted881(url: str, timestamp_base: int) -> bytes:
    """Build the server-accepted 6.5.6.32 / full/mget 881-byte source report.

    This family is recovered by inverting an accepted App request from
    ``out/frida_main_requests.log``.  It uses the 0x4081 top field10 family,
    a 387-byte nested report, and top-level field21=624.
    """
    ts2 = int(timestamp_base)
    base_ms = ts2 * 1000
    nested13 = (
        proto_field_varint(1, ts2 - 1_182)
        + proto_field_varint(2, 3)
        + proto_field_varint(4, 400)
    )
    device = source336_3040_nested_device_message(
        url,
        timestamp_base=ts2,
        field16=0x4245489B,
        field17=0x4244CDEF,
        field18=0x40BA1EA8,
        field19=0x4098AA28,
        field20=0x429C5F51,
        field21=0x4293E288,
        field25=base_ms - 1_213_168,
        field26=base_ms - 1_214_530,
        field27=base_ms - 112_618_000,
        field28=base_ms + 6_366,
        field40=base_ms - 1_340_644,
    )
    # This accepted family omits device subfield 5 (install/device token).
    token_field = proto_field_bytes(5, SOURCE336_3040_DEVICE_INSTALL_ID)
    device = device.replace(token_field, b"", 1)
    out = bytearray()
    out += proto_field_varint(1, 1_222)
    out += proto_field_varint(2, 2_943_156_234)
    out += proto_field_varint(3, 2_943_156_236)
    out += proto_field_varint(5, 14)
    out += proto_field_bytes(6, SOURCE336_REPORT_VERSION)
    out += proto_field_varint(7, 11_348)
    out += proto_field_bytes(12, device)
    out += proto_field_bytes(13, nested13)
    out += proto_field_bytes(14, b"6.5.6.32")
    out += proto_field_varint(15, 3_152)
    out += proto_field_varint(17, 12_286)
    out += proto_field_varint(18, 259_962_334_872_344 + ts2)
    out += proto_field_varint(19, ts2 - 8)
    out += proto_field_varint(20, (ts2 - 125_245_400) & 0xFFFFFFFF)
    out += proto_field_varint(22, 3_476_936_026)
    out += proto_field_varint(23, 3_476_936_026)
    return bytes(out)

def source336_container_alloc_3040_accepted881(
    url: str,
    *,
    rand2: int,
    khronos: int,
    field13: bytes,
    ladon_raw: bytes,
) -> tuple[bytes, int]:
    """Build the server-accepted 881-byte 0x4081 source336 family."""
    query = urllib.parse.urlsplit(str(url)).query.encode("ascii")
    timestamp_base = int(khronos) * 2
    field3 = (int(rand2) << 1) & 0xFFFFFFFF
    raw13 = bytes(field13)
    if len(raw13) != 20:
        raise ValueError("field13 must be exactly 20 bytes")
    out = bytearray()
    out += proto_field_bytes(1, SOURCE336_FIELD1_FIXED_SEED)
    out += proto_field_varint(2, 10)
    out += proto_field_varint(3, field3)
    out += proto_field_bytes(4, _query_value_bytes(url, "aid", "3040"))
    out += proto_field_bytes(5, _query_value_bytes(url, "device_id", ""))
    out += proto_field_bytes(6, SOURCE336_3040_MSSDK_LICENSE)
    out += proto_field_bytes(7, b"6.5.6.32")
    out += proto_field_bytes(8, SOURCE336_MSSDK_VERSION)
    out += proto_field_varint(9, 0x08121200)
    out += proto_field_bytes(10, bytes.fromhex("4081000000000000"))
    out += proto_field_varint(12, timestamp_base)
    out += proto_field_bytes(13, raw13)
    out += proto_field_bytes(14, sm3(query)[:6])
    out += proto_field_bytes(15, source336_3040_field15_message(field1=1_004, field2=12, field3=2, field5=2_221_243_644))
    out += proto_field_bytes(16, b"A9wc4sIzhYaDXS9btdyBd7QR5")
    out += proto_field_varint(17, timestamp_base)
    out += proto_field_bytes(20, b"none")
    out += proto_field_varint(21, 624)
    out += proto_field_bytes(23, source336_3040_nested_report_message_accepted881(url, timestamp_base))
    out += proto_field_bytes(
        24,
        source336_3040_metrics_json(
            sts=32_251,
            fkd=616_091_946,
            pd=-1_691_704_523,
            lp="2|520830913191|522126584745|2089179275852|129984460294688",
            fl=source336_3040_metrics_fl_from_words(
                fl2=792_258_699,
                fl4=3_238_562_437,
                fl5=438_905_606,
                fl6=3_817_201_890,
                ladon_raw=ladon_raw,
            ),
            do=0,
            tk=True,
        ),
    )
    if len(out) > SOURCE336_ALLOC_SIZE:
        raise ValueError(f"source336 payload too large: {len(out)}")
    return bytes(out) + (b"\x00" * (SOURCE336_ALLOC_SIZE - len(out))), len(out)

def x_medusa_3040_full_mget_accepted881(
    url: str,
    *,
    khronos: int,
    rand2: int = 0x79813FCA,
    rand3: int = 0x1AB094D1,
    rand4: int = 0x3460F886,
    field13: bytes = bytes.fromhex("65a328e4bb1ed9fbcde952c463f3a70e2e73fab2"),
    ladon_raw: bytes = bytes.fromhex("d2da60f1"),
) -> str:
    """Server-accepted 6.5.6.32 full/mget X-Medusa profile.

    This is pure Python and uses the recovered 881-byte source336 family.  The
    head9 suffix for this family is built by
    ``medusa3040_head9_from_query_rand4_byte(..., field13[0])``.
    """
    source336, payload_size = source336_container_alloc_3040_accepted881(
        url,
        rand2=rand2,
        khronos=khronos,
        field13=field13,
        ladon_raw=ladon_raw,
    )
    stage33f = medusa_source336_to_stage33f(source336, int(rand3), payload_size=payload_size)
    query = urllib.parse.urlsplit(str(url)).query
    head9 = medusa3040_head9_from_query_rand4_byte(query, rand4, bytes(field13)[0])
    copy31 = finalizer_copy_source31_from_head9_and_stage33f(head9, stage33f)
    control32 = medusa3040_control32_3892_from_random32(copy31 + b"\x00")
    stage34a = stage33f_to_stage34a_with_control(stage33f, head9, control32[:31], rand3=int(rand3))
    post_f2 = medusa3040_f2_scatter(stage34a, medusa3040_f2_recover_slot10(stage34a, 19), 19)
    raw = medusa3040_prefix20(int(khronos)) + ((int(rand3) & 0xFFFF).to_bytes(2, "little")) + b"\x00\x01" + control32[31:32] + post_f2
    return b64(raw)

LEGACY_CODE0_3040_KHRONOS = 1_778_923_030

LEGACY_CODE0_3040_RAND3 = 0x1F5011F6

LEGACY_CODE0_3040_HEAD9 = bytes.fromhex("8a3776177f01b90658")

LEGACY_CODE0_3040_STAGE33F = base64.b64decode(
    "ynaGszWCFmPQ2T13uwlc6aaIInv5/FX3M1f+KYQqtEUzZjEa0nWnPNw941Pfbe55uUDvE1Sb4y7Vn6iWBmiRRN4HWXkCBxe4BEYPeVmS1NmnZ5fW17vMC/e68XqJEFSaAGdrWjNhC8/803AlFcTd7KLjeM6oF4CrQLjXV0qRGRFqhdIpRSi1ZBTDv1jIhsN5FJOMBbllP7vLJ4KiJ3634DICr30/o+MCggZ7KvZHtrhErA8TteCmA+rfLOjXLsJu9FcqyPQ6JLid10BcHwXFnXcqD0r45XTPX772Z6KM1I6mBi6zkL+B/dmnjOUGcHOmH6kJ7zb+ecMOHfVshXxJeWod8IHjTfQmclFlM2fxvxj+MNFvtAR3bqPxLGJ4fCn4o43C4mhU0QWje8y7SAfaqkJoA2DniCbGOtBf23tb5Qqg3wR1YSuPQ6ZQADkERNsBt5sAkuY116W7v5IJMSG4uQV/f8CUzYix/riCrqC+ElWu6pkixhUVDRvuomtHcCEDE9bsqF35y4uCyJvuRi81yAlwS7TkVQcpoK20IlhMtQWY5x3C0Y+F4eBIi/I+uWeYtY+IcTs5tq6SDacK4RSCtU542pNmmRn+5g65Xg1P8P3DS0ZUHPEVm9OaIA6II0PSlE6ekBQc6gTQgvi13EWcI30drt3rVOq81J/4zpWQlu8wSCoXtLyvbqhPA8UwOzuZRJgrVpJAjVq8nQdpKd6PCg44ZY3L9brUVUUi4c2jc3d6YopS0C0BqeJkO04yyiQWGz/8HE+62W5jtWM4KYwKohgGN7Xwcs66ymkgDqyE91VCsQspmqD1ROWPjBhPv4ggNQ6b2H5PCiNZhym7j95jGX3W4NEN3+8M+zfixVd6fqVHFtzRolL+Z6CUhLlC38baf+8dh/P0gPNKlTun6rat7JSPcdTlTGec/DwIJc811CCCY3CCxvahJUFwWrpnjo9QugJD0gFr6v64bymzci+p3MJlYPAkDmjmCs44Znuc6g0fcmZP79kxiXt1BlBomYAvCX3HQLmMzCVX/AS5UixZYeOV18gH+7VqhlnwI+iqwD/jlCJ54hNjdDNJZToMEtdWeH5/UiGQdVKht7Dt9ZV5xgGSciTzQjyzSjy1tcYnKbyxevgZaHs4Qk0qa2mYuJiKxzsRgdM+H4f3PvMikbVIGhAxqPpJiEQ/JeViyU8gvyJcCvUO//1/sv/9/vIA"
)

def medusa3040_raw_legacy_code0() -> bytes:
    """Pure-Python assembly of the server-accepted 3040/full-mget profile."""
    copy31 = finalizer_copy_source31_from_head9_and_stage33f(
        LEGACY_CODE0_3040_HEAD9,
        LEGACY_CODE0_3040_STAGE33F,
    )
    control32 = medusa3040_control32_3892_legacy41_from_random32(copy31 + b"\x00")
    stage34a = stage33f_to_stage34a_with_control(
        LEGACY_CODE0_3040_STAGE33F,
        LEGACY_CODE0_3040_HEAD9,
        control32[:31],
        rand3=LEGACY_CODE0_3040_RAND3,
    )
    post_f2 = medusa3040_f2_scatter(stage34a, medusa3040_f2_recover_slot10(stage34a, 19), 19)
    return (
        medusa3040_prefix20(LEGACY_CODE0_3040_KHRONOS)
        + (LEGACY_CODE0_3040_RAND3 & 0xFFFF).to_bytes(2, "little")
        + b"\x00\x01"
        + control32[31:32]
        + post_f2
    )

def x_medusa_3040_full_mget_legacy_code0() -> str:
    return b64(medusa3040_raw_legacy_code0())


def proto_field_fixed32(field: int, value: int | bytes) -> bytes:
    if isinstance(value, bytes):
        if len(value) != 4:
            raise ValueError("fixed32 bytes must be exactly 4 bytes")
        data = value
    else:
        data = (value & 0xFFFFFFFF).to_bytes(4, "little")
    return proto_key(field, 5) + data

def _gf256_mul_aes(x: int, k: int) -> int:
    x &= 0xFF
    k &= 0xFF
    out = 0
    while k:
        if k & 1:
            out ^= x
        x = (((x << 1) & 0xFF) ^ (0x1B if x & 0x80 else 0)) & 0xFF
        k >>= 1
    return out & 0xFF

def medusa_reverse_source_prefix_from_src_a(src_a: bytes) -> bytes:
    """Return top-level protobuf field 10, used as reverse_source[0:8].

    3040 allocation traces show:
      reverse_source = src_a.field10(8 bytes) || stage33f/control output
    Older drafts used eight zero bytes here; that does not match current app
    output.
    """
    i = 0
    while i < len(src_a):
        key, i = _proto_read_varint(src_a, i)
        field_no, wire_type = key >> 3, key & 7
        if wire_type == 0:
            _v, i = _proto_read_varint(src_a, i)
        elif wire_type == 1:
            i += 8
        elif wire_type == 2:
            ln, i = _proto_read_varint(src_a, i)
            value = src_a[i:i + ln]
            i += ln
            if field_no == 10:
                if len(value) != 8:
                    raise ValueError("src_a field10 must be 8 bytes")
                return value
        elif wire_type == 5:
            i += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire_type}")
    raise ValueError("src_a field10 not found")

def _rol8(value: int, amount: int) -> int:
    value &= 0xFF
    amount &= 7
    return ((value << amount) & 0xFF) | (value >> (8 - amount))

def medusa_stage336_ring32_from_rand3(rand3: int, sign_key32: bytes = SIGN_KEY32_3040) -> bytes:
    """3040 stage336 slot6 ring.

    Verified against live allocation traces: the stage336 first pass consumes
    bytes `[0,1], [4,5], ... [28,29]` from
    `SM3(sign_key32 || uint32_le(rand3) || sign_key32)`.
    """
    if len(sign_key32) != 32:
        raise ValueError("sign_key32 must be exactly 32 bytes")
    return sm3(sign_key32 + u32le(rand3) + sign_key32)

def medusa_stage336_first_pass(
    source336: bytes,
    ring32: bytes,
    *,
    payload_size: int | None = None,
) -> bytes:
    payload_len = len(source336.rstrip(b"\x00")) if payload_size is None else int(payload_size)
    if payload_len <= 0:
        raise ValueError("payload_size must be positive")
    if len(ring32) < 32:
        raise ValueError("ring32 must be at least 32 bytes")
    out = bytearray(payload_len)
    for index in range(payload_len):
        source_a = ring32[(index * 4) & 31]
        source_b = ring32[((index * 4) + 1) & 31]
        proto_mix = _rol8(source336[index], 4)
        first_mix = (~((((proto_mix + source_a) & 0xFF) ^ source_b))) & 0xFF
        value = (~((((source_b + _rol8(first_mix, 3)) & 0xFF) ^ source_a))) & 0xFF
        out[payload_len - 1 - index] = value
    return bytes(out)

def medusa_stage336_second_pass(first_pass: bytes) -> bytes:
    raw = bytes(first_pass)
    n = len(raw)
    if n < 3:
        raise ValueError("first_pass too short")
    out = bytearray(raw)
    initial_mix = (~(raw[n - 1] ^ raw[n - 2])) & 0xFF
    out[0] = (raw[0] + initial_mix) & 0xFF
    out[1] = (((raw[-1] ^ out[0]) ^ 0xFE) + raw[1]) & 0xFF
    for offset in range(2, n - 1):
        value = (~((_rol8(out[offset - 1], 3) ^ out[offset - 2]) ^ (offset & 0xFF))) & 0xFF
        out[offset] = (value + raw[offset]) & 0xFF
    out[n - 1] = raw[n - 1] ^ out[n - 2]
    accumulator = (out[0] ^ out[1]) & 0xFF
    for offset in range(1, n):
        accumulator = (accumulator + out[offset]) & 0xFF
    out[0] = accumulator
    return bytes(out)

def medusa_source336_to_stage33f(src_a: bytes, d71bc_rand: int, payload_size: int | None = None) -> bytes:
    """Current 3040 `source336 -> stage33f` transform, pure Python.

    This replaces the older `block_d71bc_encode` assumption for NovelFM 3040
    full/mget.  Live traces show:
      stage33e = src_a.field10 || stage336(src_a, SM3(key3040||rand3||key3040))
      stage33f = reverse(stage33e) xor key4(high16(rand3)) || 00
    """
    src = bytes(src_a)
    payload_len = len(src.rstrip(b"\x00")) if payload_size is None else int(payload_size)
    if payload_len < 0 or payload_len > len(src):
        raise ValueError("payload_size out of source336 buffer range")
    source = src[:payload_len]
    prefix8 = medusa_reverse_source_prefix_from_src_a(source)
    ring32 = medusa_stage336_ring32_from_rand3(d71bc_rand)
    stage336 = medusa_stage336_second_pass(medusa_stage336_first_pass(source, ring32, payload_size=payload_len))
    key4 = medusa_reverse_key4_from_d71bc_rand(d71bc_rand)
    return reverse_xor(prefix8 + stage336, key4) + b"\x00"

def medusa_tail2_hash(tail2: bytes) -> int:
    """还原 tail2 -> helper_ret 的小 VM hash。

    这个 helper 用于生成 reverse-xor 的 4 字节 key；输入就是
    X-Medusa raw[20:22] 那两个随机低字节。
    """
    if len(tail2) != 2:
        raise ValueError("tail2 must be 2 bytes")
    state = 0
    for i, b in enumerate(tail2):
        if i & 1:
            t = (((state << 11) & 0xFFFFFFFF) | b) & 0xFFFFFFFF
            t ^= (state & 0xFFFFFFFF) >> 5
            t ^= state & 0xFFFFFFFF
            state = (~t) & 0xFFFFFFFF
        else:
            t = (((state << 7) & 0xFFFFFFFF) ^ b) & 0xFFFFFFFF
            t ^= (state & 0xFFFFFFFF) >> 3
            state = (state ^ t) & 0xFFFFFFFF
    return state

def medusa_reverse_key4_from_high2(high2: bytes) -> bytes:
    """Current 3040 reverse-xor key: hash the high 16 bits of d71bc_rand.

    Allocation traces confirm `key4 == medusa_tail2_hash(high2).to_bytes(4,
    "big")`; e.g. high2 `6e3e` -> `fffc8fac`.
    """
    if len(high2) != 2:
        raise ValueError("high2 must be 2 bytes")
    return medusa_tail2_hash(high2).to_bytes(4, "big")

def medusa_reverse_key4_from_d71bc_rand(d71bc_rand: int) -> bytes:
    return medusa_reverse_key4_from_high2(u32le(d71bc_rand)[2:])


orjson = None

API_HOST = "https://api5-sinfonlinec.novelfm.com"

DEFAULT_UA = "com.xs.fm/656 (Linux; U; Android 9; zh_CN; SM-S9260; Build/PQ3A.190605.02261134;tt-ok/3.12.13.17)"

FULL_MGET_SIGNED_URL = (
    "https://api5-sinfonlinec.novelfm.com/novelfm/playerapi/full/mget/v1/?device_platform=android&os=android&ssmix=a&_rticket=1783204359936"
    "&cdid=7634657e-a134-47cf-9ac3-c38ea9923097&channel=54157680a&aid=3040&app_name=novel_fm&version_code=656"
    "&version_name=6.5.6.32&manifest_version_code=656&update_version_code=65632&resolution=1440*2560&dpi=640"
    "&device_type=SM-S9260&device_brand=Samsung&language=zh&os_api=28&os_version=9&ac=wifi&device_id=3001028083774489"
    "&iid=1395712309393850&comment_tag_c=5&vip_state=0&host_abi=arm64-v8a&category_style=1&need_personal_recommend=1"
    "&ab_sdk_version=90111254%2C90975474%2C16797554%2C91986083%2C90126074%2C91986082%2C91008840%2C91281044%2C92120672%2C90110758%2C90174492%2C5711286%2C16963142%2C17225371%2C90114353%2C90098780%2C92100130%2C91347266%2C90952506%2C90614667%2C91801013%2C91763052%2C91763051%2C91763050%2C91787063%2C90661280%2C91633046%2C90609513%2C92319500"
    "&rom_version=PQ3A.190605.02261134+release-keys&klink_egdi=AAK_uq0vE8PrXz2HmNU9hVK7t9H-AFvbvPlsZSPYH3E9haMKxm0o-Yqm"
)




CAPTURED_CODE0_SIGNED_URL = (
    "https://api5-sinfonlinec.novelfm.com/novelfm/playerapi/full/mget/v1/?device_platform=android&os=android&ssmix=a"
    "&_rticket=1778923033155&cdid=5b00d94e-eaa2-42fa-8095-6e994728a48f&channel=vivo_3040_64&aid=3040"
    "&app_name=novel_fm&version_code=644&version_name=6.4.4.32&manifest_version_code=644&update_version_code=64432"
    "&resolution=1440*2560&dpi=640&device_type=SM-S9260&device_brand=Samsung&language=zh&os_api=28&os_version=9"
    "&ac=wifi&device_id=3001028083774489&iid=3313243055211242&comment_tag_c=5&vip_state=0&host_abi=arm64-v8a"
    "&category_style=1&need_personal_recommend=1"
    "&ab_sdk_version=90975474%2C91016290%2C91847784%2C91008840%2C91281044%2C92120672%2C90110758%2C91273322"
    "%2C91799786%2C90174492%2C91225968%2C5711286%2C90098780%2C91279070%2C90952506%2C90614667%2C91801013"
    "%2C91787063%2C90661280%2C91633046%2C91766414%2C92280103%2C91294212%2C92280104%2C90609513%2C92280105"
    "&rom_version=PQ3A.190605.02261134+release-keys"
)


APP_COMMON_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "application/json; charset=utf-8,application/x-protobuf",
    "Accept-Encoding": "gzip",
    "X-Xs-From-Web": "0",
    "Content-Type": "application/json; charset=utf-8",
}

DEFAULT_QUERY = {
    "device_platform": "android", "os": "android", "ssmix": "a", "channel": "54157680a", "aid": "3040",
    "app_name": "novel_fm", "cdid": "7634657e-a134-47cf-9ac3-c38ea9923097", "version_code": "656",
    "version_name": "6.5.6.32", "manifest_version_code": "656", "update_version_code": "65632", "resolution": "1440*2560",
    "dpi": "640", "device_type": "SM-S9260", "device_brand": "Samsung", "language": "zh", "os_api": "28",
    "os_version": "9", "ac": "wifi", "device_id": "3001028083774489", "iid": "1395712309393850",
    "comment_tag_c": "5", "vip_state": "0", "host_abi": "arm64-v8a", "category_style": "1", "need_personal_recommend": "1",
}

# ===== 番茄畅听正文加密参数 =====
DHP = int("ffffffffffffffffc90fdaa22168c234c4c6628b80dc1cd129024e088a67cc74020bbea63b139b22514a08798e3404ddef9519b3cd3a431b302b0a6df25f14374fe1356d6d51c245e485b576625e7ec6f44c42e9a637ed6b0bff5cb6f406b7edee386bfb5a899fa5ae9f24117c4b1fe649286651ece45b3dc2007cb8a163bf0598da48361c55d39a69163fa8fd24cf5f83655d23dca3ad961c62f356208552bb9ed529077096966d670c354e4abc9804f1746c08ca237327ffffffffffffffff", 16)

DHG = 2

DHAES_TOKEN = base64.b64decode("rCXGfd2POMGzeiNIgo4iLg==")

# ===== AES/CBC 正文解密 =====

def _pkcs7_pad(data: bytes) -> bytes:
    padding = 16 - len(data) % 16
    return data + bytes([padding]) * padding


def _pkcs7_unpad(data: bytes) -> bytes:
    padding = data[-1]
    if padding < 1 or padding > 16 or data[-padding:] != bytes([padding]) * padding:
        raise ValueError("无效的 PKCS7 填充")
    return data[:-padding]


def aes_cbc_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if PYCRYPTODOME_AES is None:
        raise RuntimeError("缺少 PyCryptodome 依赖，无法加密正文请求")
    return PYCRYPTODOME_AES.new(key, PYCRYPTODOME_AES.MODE_CBC, iv).encrypt(_pkcs7_pad(data))


def aes_cbc_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if PYCRYPTODOME_AES is None:
        raise RuntimeError("缺少 PyCryptodome 依赖，无法解密正文")
    plaintext = PYCRYPTODOME_AES.new(key, PYCRYPTODOME_AES.MODE_CBC, iv).decrypt(data)
    return _pkcs7_unpad(plaintext)


def aes_cbc_decrypt_fast(data: bytes, key: bytes, iv: bytes) -> bytes:
    """使用 PyCryptodome 执行 AES/CBC 正文解密。"""
    return aes_cbc_decrypt(data, key, iv)
def java_bigint_bytes(n:int)->bytes:
    if n==0: return b'\x00'
    b=n.to_bytes((n.bit_length()+7)//8,'big')
    return b'\x00'+b if b[0]&0x80 else b

def strip_leading_zero_to_32(b:bytes)->bytes:
    i=0
    while i<len(b) and b[i]==0: i+=1
    if i+31>=len(b): i=max(0,len(b)-32)
    key=b[i:i+32]
    if len(key)!=32: raise ValueError('bad shared key length')
    return key

def _获取DH私钥位数() -> int:
    """限制临时 DH 私钥位数，减少正文请求前的本地幂运算耗时。"""
    try:
        位数 = int(os.environ.get("FANQIE_DH_PRIVATE_BITS", "128"))
    except (TypeError, ValueError):
        位数 = 128
    return max(128, min(2048, 位数))


DH_PRIVATE_BITS = _获取DH私钥位数()


def make_encrypt_context()->Tuple[int,str]:
    x=secrets.randbits(DH_PRIVATE_BITS)|(1<<(DH_PRIVATE_BITS-1))|1
    y=pow(DHG,x,DHP); yb=java_bigint_bytes(y)
    iv=os.urandom(16); enc=aes_cbc_encrypt(yb,DHAES_TOKEN,iv)
    return x, base64.b64encode(iv+enc).decode()

def decrypt_content(content_b64:str, server_y_b64:str, client_x:int)->str:
    iv=content_b64.encode('utf-8')[:16]
    ciphertext=base64.b64decode(content_b64)
    server_y=int.from_bytes(base64.b64decode(server_y_b64),'big')
    shared=int(gmpy2.powmod(server_y,client_x,DHP)) if gmpy2 is not None else pow(server_y,client_x,DHP)
    aes_key=strip_leading_zero_to_32(java_bigint_bytes(shared))
    plaintext=aes_cbc_decrypt_fast(ciphertext,aes_key,iv)
    return plaintext[16:].decode('utf-8','replace')

# ===== HTTP/2 正文请求 =====
FULL_MGET_TRANSPORT=os.environ.get('FANQIE_FULL_MGET_TRANSPORT','auto').lower()

if FULL_MGET_TRANSPORT not in {'auto','http1','http2'}:
    FULL_MGET_TRANSPORT='auto'

FULL_MGET_HTTP_REUSE=os.environ.get('FANQIE_FULL_MGET_HTTP_REUSE','1').strip().lower() not in {'0','false','off','no'}

try:
    FULL_MGET_HTTP_REUSE_MAX_REQUESTS=max(1,int(os.environ.get('FANQIE_FULL_MGET_HTTP_REUSE_MAX_REQUESTS','80')))
except Exception:
    FULL_MGET_HTTP_REUSE_MAX_REQUESTS=80

_H2_THREAD_LOCAL=threading.local()

def _h2_frame(frame_type:int, flags:int, stream_id:int, payload:bytes=b'')->bytes:
    return len(payload).to_bytes(3,'big')+bytes([frame_type&0xff,flags&0xff])+struct.pack('>I',stream_id&0x7fffffff)+payload

def _h2_recv_exact(sock:ssl.SSLSocket, size:int)->bytes:
    parts=[]
    while size:
        chunk=sock.recv(size)
        if not chunk:
            raise EOFError('HTTP/2 connection closed before response completed')
        parts.append(chunk)
        size-=len(chunk)
    return b''.join(parts)

def _hpack_int(value:int, prefix_bits:int, prefix:int=0)->bytes:
    limit=(1<<prefix_bits)-1
    if value<limit:
        return bytes([prefix|value])
    out=bytearray([prefix|limit])
    value-=limit
    while value>=128:
        out.append((value&0x7f)|0x80)
        value>>=7
    out.append(value)
    return bytes(out)

def _hpack_string(value:str|bytes)->bytes:
    raw=value.encode('utf-8') if isinstance(value,str) else bytes(value)
    # High bit remains clear: sending literal strings avoids a Huffman table.
    return _hpack_int(len(raw),7)+raw

def _hpack_literal_header(name:str, value:str)->bytes:
    # Literal Header Field without Indexing, new-name representation.
    return _hpack_int(0,4)+_hpack_string(name.lower())+_hpack_string(value)

def _http2_post_bytes(url:str, headers:Dict[str,str], data:bytes, timeout:int=60)->bytes:
    """Issue one HTTPS HTTP/2 POST and return its raw response body."""
    split=urllib.parse.urlsplit(url)
    if split.scheme!='https' or not split.hostname:
        raise ValueError('HTTP/2 transport only supports absolute HTTPS URLs')
    host=split.hostname
    port=split.port or 443
    path=(split.path or '/')+(('?'+split.query) if split.query else '')
    tcp:Optional[socket.socket]=None
    sock:Optional[ssl.SSLSocket]=None
    try:
        context=ssl.create_default_context()
        context.set_alpn_protocols(['h2'])
        tcp=socket.create_connection((host,port),timeout=timeout)
        sock=context.wrap_socket(tcp,server_hostname=host)
        tcp=None
        sock.settimeout(timeout)
        if sock.selected_alpn_protocol()!='h2':
            raise RuntimeError('server did not negotiate HTTP/2')

        sock.sendall(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')
        # A larger per-stream receive window prevents a 64 KiB pause on
        # multi-chapter responses.  HTTP/2 also has a separate connection
        # window; if it stays at the default 65 KiB the server must wait for a
        # round-trip every few DATA frames, which makes 1000+ chapter mget
        # responses look much slower than the App/Cronet capture.  Open both
        # windows up-front, then still replenish credits as frames are read.
        h2_window=16*1024*1024
        sock.sendall(_h2_frame(4,0,0,struct.pack('>HI',4,h2_window)))
        sock.sendall(_h2_frame(8,0,0,struct.pack('>I',h2_window-65535)))

        pairs=[
            (':method','POST'),
            (':scheme','https'),
            (':authority',split.netloc),
            (':path',path),
        ]
        seen=set()
        forbidden={'connection','host','keep-alive','proxy-connection','transfer-encoding','upgrade'}
        for key,value in headers.items():
            name=key.lower()
            if name in forbidden or name.startswith(':'):
                continue
            seen.add(name)
            pairs.append((name,str(value)))
        if 'content-length' not in seen:
            pairs.append(('content-length',str(len(data))))
        block=b''.join(_hpack_literal_header(name,value) for name,value in pairs)
        if len(block)>16_384:
            raise ValueError('HTTP/2 header block exceeds supported frame size')
        sock.sendall(_h2_frame(1,0x04|(0x01 if not data else 0),1,block))
        for offset in range(0,len(data),16_384):
            chunk=data[offset:offset+16_384]
            flags=0x01 if offset+len(chunk)==len(data) else 0
            sock.sendall(_h2_frame(0,flags,1,chunk))

        response=bytearray()
        while True:
            header=_h2_recv_exact(sock,9)
            payload_size=int.from_bytes(header[:3],'big')
            frame_type=header[3]
            flags=header[4]
            stream_id=struct.unpack('>I',header[5:9])[0]&0x7fffffff
            payload=_h2_recv_exact(sock,payload_size)
            if frame_type==4:  # SETTINGS
                if not (flags&0x01):
                    sock.sendall(_h2_frame(4,0x01,0))
                continue
            if frame_type==6:  # PING
                if not (flags&0x01):
                    sock.sendall(_h2_frame(6,0x01,0,payload))
                continue
            if frame_type==0 and stream_id==1:  # DATA
                flow_bytes=len(payload)
                if flags&0x08:  # PADDED
                    if not payload:
                        raise RuntimeError('invalid padded HTTP/2 DATA frame')
                    pad_len=payload[0]
                    if pad_len>=len(payload):
                        raise RuntimeError('invalid HTTP/2 DATA padding')
                    payload=payload[1:len(payload)-pad_len]
                response.extend(payload)
                if flow_bytes:
                    increment=struct.pack('>I',flow_bytes)
                    sock.sendall(_h2_frame(8,0,0,increment))
                    sock.sendall(_h2_frame(8,0,1,increment))
                if flags&0x01:
                    return bytes(response)
                continue
            if frame_type==1 and stream_id==1 and (flags&0x01):
                return bytes(response)
            if frame_type==3 and stream_id==1:
                code=int.from_bytes(payload[:4],'big') if len(payload)>=4 else -1
                raise RuntimeError(f'HTTP/2 RST_STREAM code={code}')
            if frame_type==7:
                raise RuntimeError('HTTP/2 GOAWAY received')
    finally:
        if sock is not None:
            sock.close()
        elif tcp is not None:
            tcp.close()

class _ReusableHttp2Connection:
    """线程内复用的简易 HTTP/2 连接，用于分批下载时减少 TLS 握手耗时。"""

    def __init__(self, host:str, port:int, timeout:int=60):
        self.host=host
        self.port=port
        self.sock:Optional[ssl.SSLSocket]=None
        self.next_stream_id=1
        self.request_count=0
        self._connect(timeout)

    @property
    def key(self)->Tuple[str,int]:
        return (self.host,self.port)

    @property
    def closed(self)->bool:
        return self.sock is None

    def close(self)->None:
        sock=self.sock
        self.sock=None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    def __del__(self):
        self.close()

    def _connect(self, timeout:int=60)->None:
        self.close()
        context=ssl.create_default_context()
        context.set_alpn_protocols(['h2'])
        tcp:Optional[socket.socket]=None
        try:
            tcp=socket.create_connection((self.host,self.port),timeout=timeout)
            sock=context.wrap_socket(tcp,server_hostname=self.host)
            tcp=None
            sock.settimeout(timeout)
            if sock.selected_alpn_protocol()!='h2':
                sock.close()
                raise RuntimeError('server did not negotiate HTTP/2')
            h2_window=16*1024*1024
            sock.sendall(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')
            sock.sendall(_h2_frame(4,0,0,struct.pack('>HI',4,h2_window)))
            sock.sendall(_h2_frame(8,0,0,struct.pack('>I',h2_window-65535)))
            self.sock=sock
            self.next_stream_id=1
            self.request_count=0
        finally:
            if tcp is not None:
                try:
                    tcp.close()
                except Exception:
                    pass

    def post_bytes(self, url:str, headers:Dict[str,str], data:bytes, timeout:int=60)->bytes:
        split=urllib.parse.urlsplit(url)
        if split.scheme!='https' or not split.hostname:
            raise ValueError('HTTP/2 transport only supports absolute HTTPS URLs')
        port=split.port or 443
        if (split.hostname,port)!=self.key:
            raise ValueError('HTTP/2 reusable connection host changed')
        if self.closed or self.next_stream_id>=0x7ffffff0:
            self._connect(timeout)
        sock=self.sock
        if sock is None:
            raise RuntimeError('HTTP/2 reusable connection is closed')
        sock.settimeout(timeout)
        stream_id=self.next_stream_id
        self.next_stream_id+=2
        self.request_count+=1
        path=(split.path or '/')+(('?'+split.query) if split.query else '')

        pairs=[
            (':method','POST'),
            (':scheme','https'),
            (':authority',split.netloc),
            (':path',path),
        ]
        seen=set()
        forbidden={'connection','host','keep-alive','proxy-connection','transfer-encoding','upgrade'}
        for key,value in headers.items():
            name=key.lower()
            if name in forbidden or name.startswith(':'):
                continue
            seen.add(name)
            pairs.append((name,str(value)))
        if 'content-length' not in seen:
            pairs.append(('content-length',str(len(data))))
        block=b''.join(_hpack_literal_header(name,value) for name,value in pairs)
        if len(block)>16_384:
            raise ValueError('HTTP/2 header block exceeds supported frame size')

        try:
            sock.sendall(_h2_frame(1,0x04|(0x01 if not data else 0),stream_id,block))
            for offset in range(0,len(data),16_384):
                chunk=data[offset:offset+16_384]
                flags=0x01 if offset+len(chunk)==len(data) else 0
                sock.sendall(_h2_frame(0,flags,stream_id,chunk))

            response=bytearray()
            while True:
                header=_h2_recv_exact(sock,9)
                payload_size=int.from_bytes(header[:3],'big')
                frame_type=header[3]
                flags=header[4]
                frame_stream_id=struct.unpack('>I',header[5:9])[0]&0x7fffffff
                payload=_h2_recv_exact(sock,payload_size)
                if frame_type==4:  # SETTINGS
                    if not (flags&0x01):
                        sock.sendall(_h2_frame(4,0x01,0))
                    continue
                if frame_type==6:  # PING
                    if not (flags&0x01):
                        sock.sendall(_h2_frame(6,0x01,0,payload))
                    continue
                if frame_type==0 and frame_stream_id==stream_id:  # DATA
                    flow_bytes=len(payload)
                    if flags&0x08:  # PADDED
                        if not payload:
                            raise RuntimeError('invalid padded HTTP/2 DATA frame')
                        pad_len=payload[0]
                        if pad_len>=len(payload):
                            raise RuntimeError('invalid HTTP/2 DATA padding')
                        payload=payload[1:len(payload)-pad_len]
                    response.extend(payload)
                    if flow_bytes:
                        increment=struct.pack('>I',flow_bytes)
                        sock.sendall(_h2_frame(8,0,0,increment))
                        sock.sendall(_h2_frame(8,0,stream_id,increment))
                    if flags&0x01:
                        return bytes(response)
                    continue
                if frame_type==1 and frame_stream_id==stream_id and (flags&0x01):
                    return bytes(response)
                if frame_type==3 and frame_stream_id==stream_id:
                    code=int.from_bytes(payload[:4],'big') if len(payload)>=4 else -1
                    raise RuntimeError(f'HTTP/2 RST_STREAM code={code}')
                if frame_type==7:
                    raise RuntimeError('HTTP/2 GOAWAY received')
        except Exception:
            self.close()
            raise

def _close_thread_h2_connection()->None:
    conn=getattr(_H2_THREAD_LOCAL,'conn',None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        try:
            delattr(_H2_THREAD_LOCAL,'conn')
        except Exception:
            pass

def _get_thread_h2_connection(url:str, timeout:int=60)->_ReusableHttp2Connection:
    split=urllib.parse.urlsplit(url)
    if split.scheme!='https' or not split.hostname:
        raise ValueError('HTTP/2 transport only supports absolute HTTPS URLs')
    key=(split.hostname,split.port or 443)
    conn=getattr(_H2_THREAD_LOCAL,'conn',None)
    if (
        conn is None
        or getattr(conn,'closed',True)
        or getattr(conn,'key',None)!=key
        or getattr(conn,'request_count',0)>=FULL_MGET_HTTP_REUSE_MAX_REQUESTS
    ):
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        conn=_ReusableHttp2Connection(key[0],key[1],timeout)
        _H2_THREAD_LOCAL.conn=conn
    return conn

def _http2_post_bytes_reused(url:str, headers:Dict[str,str], data:bytes, timeout:int=60)->bytes:
    last:Optional[BaseException]=None
    for _attempt in range(2):
        try:
            conn=_get_thread_h2_connection(url,timeout)
            return conn.post_bytes(url,headers,data,timeout)
        except Exception as e:
            last=e
            _close_thread_h2_connection()
    raise last  # type: ignore[misc]

def full_mget_http_json(url:str, headers:Dict[str,str], data:bytes, timeout:int=60, retries:int=3)->Any:
    """Use HTTP/2 for full/mget when available, then fall back to urllib."""
    if FULL_MGET_TRANSPORT in {'auto','http2'}:
        try:
            raw=_http2_post_bytes_reused(url,headers,data,timeout) if FULL_MGET_HTTP_REUSE else _http2_post_bytes(url,headers,data,timeout)
            if raw[:2]==b'\x1f\x8b':
                raw=gzip.decompress(raw)
            if not raw:
                return {}
            return orjson.loads(raw) if orjson is not None else json.loads(raw.decode('utf-8','replace'))
        except Exception:
            if FULL_MGET_TRANSPORT=='http2':
                raise
    return http_json_bytes(url,'POST',headers,data,timeout=timeout,retries=retries)

def _open_with_retries(req:urllib.request.Request, timeout:int=30, retries:int=3, backoff:float=0.8)->bytes:
    last:Optional[BaseException]=None
    for attempt in range(1, max(1, retries)+1):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                raw=r.read()
                if r.headers.get('Content-Encoding','').lower()=='gzip': raw=gzip.decompress(raw)
                return raw
        except Exception as e:
            last=e
            if attempt >= max(1, retries):
                break
            time.sleep(backoff * attempt)
    raise last  # type: ignore[misc]

def http_json(url:str, method='GET', headers:Optional[Dict[str,str]]=None, body:Any=None, timeout=30, retries:int=3)->Any:
    data=None
    h=dict(headers or {})
    if body is not None:
        data=orjson.dumps(body) if orjson is not None else json.dumps(body,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        h.setdefault('Content-Type','application/json; charset=utf-8')
    req=urllib.request.Request(url,data=data,headers=h,method=method)
    raw=_open_with_retries(req,timeout=timeout,retries=retries)
    if not raw: return {}
    return orjson.loads(raw) if orjson is not None else json.loads(raw.decode('utf-8','replace'))

def json_body_bytes(body:Any)->bytes:
    return orjson.dumps(body) if orjson is not None else json.dumps(body,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def http_json_bytes(url:str, method='POST', headers:Optional[Dict[str,str]]=None, data:bytes=b'', timeout=30, retries:int=3)->Any:
    h=dict(headers or {})
    h.setdefault('Content-Type','application/json; charset=utf-8')
    req=urllib.request.Request(url,data=data,headers=h,method=method)
    raw=_open_with_retries(req,timeout=timeout,retries=retries)
    if not raw: return {}
    return orjson.loads(raw) if orjson is not None else json.loads(raw.decode('utf-8','replace'))

def make_url(path:str, query:Dict[str,str], *, host:str=API_HOST)->str:
    q=dict(DEFAULT_QUERY); q['_rticket']=str(int(time.time()*1000)); q.update(query)
    if not path.startswith('/'):
        path='/'+path
    return host+path+'?'+urllib.parse.urlencode(q)

def make_app_headers(url: str, body_bytes: bytes = b"", sign_mode: str = "auto") -> Dict[str, str]:
    """构造番茄畅听 App 接口的纯 Python 签名请求头。"""
    mode = (sign_mode or "auto").lower()
    if mode not in {"auto", "pure3040", "legacy3040"}:
        raise ValueError("签名模式必须为 auto、pure3040 或 legacy3040")
    headers = dict(APP_COMMON_HEADERS)
    if mode == "legacy3040":
        headers.update(build_pure3040_legacy_headers(url, body_bytes))
    else:
        headers.update(build_pure3040_headers(url, body_bytes, khronos=1_783_204_357))
    return headers

def signed_app_json(path:str, body:Any=None, query:Optional[Dict[str,str]]=None, *,
                    method:str='POST', sign_mode:str='auto', timeout:int=60,
                    host:str=API_HOST, unsigned_fallback:bool=True)->Any:
    """Request an App RPC JSON endpoint with pure-Python signing."""
    url=make_url(path, query or {}, host=host)
    method=method.upper()
    body_bytes=b'' if body is None else json_body_bytes(body)
    try:
        return http_json_bytes(url, method, make_app_headers(url, body_bytes, sign_mode), body_bytes, timeout=timeout)
    except Exception:
        if not unsigned_fallback:
            raise
        # Some business endpoints do not enforce metasec; keep an unsigned fallback.
        h={k:v for k,v in APP_COMMON_HEADERS.items() if method!='GET' or k.lower()!='content-type'}
        if body is None:
            return http_json(url, method, h, None, timeout=timeout)
        return http_json_bytes(url, method, h, body_bytes, timeout=timeout)


async def 异步签名番茄JSON(
    client: Any,
    path: str,
    body: Any = None,
    query: Optional[Dict[str, str]] = None,
    *,
    method: str = "POST",
    sign_mode: str = "auto",
    unsigned_fallback: bool = True,
) -> Dict[str, Any]:
    """使用复用异步会话请求番茄 App RPC，并保留必要的无签名兼容分支。"""
    url = make_url(path, query or {})
    method = method.upper()
    body_bytes = b"" if body is None else json_body_bytes(body)
    try:
        return await 异步番茄JSON请求(
            client,
            url,
            method=method,
            headers=make_app_headers(url, body_bytes, sign_mode),
            content=body_bytes,
            retries=2,
        )
    except Exception:
        if not unsigned_fallback:
            raise
        headers = {
            key: value
            for key, value in APP_COMMON_HEADERS.items()
            if method != "GET" or key.lower() != "content-type"
        }
        return await 异步番茄JSON请求(
            client,
            url,
            method=method,
            headers=headers,
            content=body_bytes,
            retries=2,
        )

def resolve_book_id(value:str)->str:
    """从 book_id、番茄小说链接、App schema/share 文本中提取 book_id。

    现有正文接口本质只需要 book_id + item_id 列表；不同频道（看书/短篇/
    出版物/故事等）只要仍是书籍详情页或 schema 里的 book_id，都走同一套
    full/mget 下载链。
    """
    text=(value or '').strip()
    if not text:
        raise ValueError('empty book id/url')
    if re.fullmatch(r'\d{8,}', text):
        return text
    # 常见 App/schema/share 参数：book_id=、bookId=、bookid=
    m=re.search(r'(?i)(?:book[_-]?id|bookId)=([0-9]{8,})', text)
    if m:
        return m.group(1)
    # 公开页：https://fanqienovel.com/page/<book_id>
    m=re.search(r'fanqienovel\.com/(?:page|book)/([0-9]{8,})', text)
    if m:
        return m.group(1)
    # 有些分享文本里只暴露 /page/数字 或 aweme schema 内的 page%2F数字
    m=re.search(r'(?:/|%2[fF])(?:page|book)(?:/|%2[fF])([0-9]{8,})', text)
    if m:
        return m.group(1)
    # 最后兜底：如果整段文本只有一个长数字，认为是 book_id。
    ids=re.findall(r'\d{16,}', text)
    uniq=[]
    for x in ids:
        if x not in uniq:
            uniq.append(x)
    if len(uniq)==1:
        return uniq[0]
    raise ValueError(f'无法从输入提取 book_id: {value!r}')

def _u32le(n:int)->bytes:
    return int(n & 0xFFFFFFFF).to_bytes(4,'little')

def _ror64(value:int,count:int)->int:
    value &= 0xFFFFFFFFFFFFFFFF; count &= 63
    return ((value>>count)|(value<<(64-count))) & 0xFFFFFFFFFFFFFFFF

def _helios3040_encrypt_block(hash_table:List[int], block16:bytes)->bytes:
    data0=int.from_bytes(block16[:8],'little')
    data1=int.from_bytes(block16[8:],'little')
    for i in range(0x22):
        data1=(hash_table[i]^((data0+_ror64(data1,8))&0xFFFFFFFFFFFFFFFF))&0xFFFFFFFFFFFFFFFF
        data0=(data1^_ror64(data0,61))&0xFFFFFFFFFFFFFFFF
    return data0.to_bytes(8,'little')+data1.to_bytes(8,'little')

def x_helios_3040(khronos:int, rand32:Optional[int]=None)->str:
    """纯 Python 生成 3040 / app 6.5.6.32 的 X-Helios。

    已用 out/medusa_oracle_batch.jsonl 八组样本校验：
      base64(uint32_le(rand) || enc(pkcs7(f"{khronos}-1532254240-3040")))
    """
    if rand32 is None:
        rand32=secrets.randbits(32)
    rand32 &= 0xFFFFFFFF
    md5=hashlib.md5(_u32le(rand32)+b'3040').digest()
    hex_table=b'0123456789abcdef'
    keybuf=bytearray(32)
    for i,v in enumerate(md5):
        keybuf[2*i]=hex_table[v>>4]; keybuf[2*i+1]=hex_table[v&15]
    words=[int.from_bytes(keybuf[i:i+8],'little') for i in range(0,32,8)]
    hash_table=[words[0]]
    b0,b8=words[0],words[1]
    q=words[2:]
    for i in range(0x22):
        x=((_ror64(b8,8)+b0)^i)&0xFFFFFFFFFFFFFFFF
        q.append(x)
        x=(x^_ror64(b0,61))&0xFFFFFFFFFFFFFFFF
        hash_table.append(x)
        b0=x; b8=q.pop(0)
    raw=f'{int(khronos)}-1532254240-3040'.encode('ascii')
    pad=16-len(raw)%16
    raw+=bytes([pad])*pad
    enc=b''.join(_helios3040_encrypt_block(hash_table,raw[i:i+16]) for i in range(0,len(raw),16))
    return base64.b64encode(_u32le(rand32)+enc).decode()

def _pure3040_rand31() -> int:
    return secrets.randbelow(0x80000000)

def build_pure3040_656_url(epoch_ms:int)->str:
    # Use the 6.5.6.32 api5-sinfonlinec.novelfm.com query profile that matches the
    # recovered accepted881 Medusa source family. The fully current 891-byte
    # family is body-bound; downloader defaults to this known code=0 profile.
    _ = epoch_ms
    return FULL_MGET_SIGNED_URL

def build_pure3040_headers(url:str, body_bytes:bytes, *, khronos:int|None=None)->Dict[str,str]:
    """纯 Python 生成 3040 full/mget metasec 头。

    使用本项目内的 stage336 -> stage33f -> stage34a/control32(3892) 管线；
    不再调用外部项目、App、adb、frida 或 so。
    """
    # 6.5.6.32 / aid=3040 的 accepted881 profile。实测 top_rand 只进入
    # X-Helios；X-Medusa 由 recovered source336 family 在 Python 内生成。
    if khronos is None:
        khronos=int(time.time())
    top_rand=_pure3040_rand31()
    # Server-accepted 6.5.6.32 / full/mget 881-byte Medusa profile.  These
    # values are not copied headers: X-Medusa is assembled in pure Python from
    # the recovered source336 family for the paired URL/khronos profile.
    ladon_raw=bytes.fromhex("d2da60f1")
    return {
        "X-Khronos": str(khronos),
        # App full/mget sends an empty X-SS-STUB for this request family.
        "X-SS-STUB": "",
        "X-Argus": x_argus(khronos),
        # 当前 App 返回的 X-Ladon 是 4 字节短串；同一 raw 值也进入
        # source336.metrics.fl 最后一项。这里先保持 Medusa 内外一致。
        "X-Ladon": base64.b64encode(ladon_raw).decode(),
        "X-Helios": x_helios_3040(khronos, top_rand),
        "X-Medusa": x_medusa_3040_full_mget_accepted881(
            url,
            khronos=khronos,
            ladon_raw=ladon_raw,
        ),
    }

def build_pure3040_legacy_headers(url:str, body_bytes:bytes)->Dict[str,str]:
    """旧 6.4.4.32 code=0 profile：保留为可用基线/自动兜底。"""
    return {
        "X-Khronos": str(LEGACY_CODE0_3040_KHRONOS),
        "X-Argus": x_argus(LEGACY_CODE0_3040_KHRONOS),
        "X-Helios": x_helios_3040(LEGACY_CODE0_3040_KHRONOS, 0x64C6140C),
        "X-Medusa": x_medusa_3040_full_mget_legacy_code0(),
    }



def full_mget_request_options(body_bytes: bytes, sign_mode: str = "auto") -> List[Tuple[str, Dict[str, str], str]]:
    """按签名模式生成正文接口请求候选项。"""
    mode = (sign_mode or "auto").lower()
    if mode not in {"auto", "pure3040", "legacy3040"}:
        raise ValueError("签名模式必须为 auto、pure3040 或 legacy3040")

    options: List[Tuple[str, Dict[str, str], str]] = []
    if mode in {"auto", "pure3040"}:
        url = build_pure3040_656_url(int(time.time() * 1000))
        headers = {**APP_COMMON_HEADERS, **build_pure3040_headers(url, body_bytes, khronos=1_783_204_357)}
        options.append(("畅听3040", headers, url))
    if mode in {"auto", "legacy3040"}:
        url = CAPTURED_CODE0_SIGNED_URL
        headers = {**APP_COMMON_HEADERS, **build_pure3040_legacy_headers(url, body_bytes)}
        options.append(("畅听旧签名", headers, url))
    return options


def 创建番茄正文HTTP客户端(并发数: int) -> Any:
    """创建支持 HTTP/2 多路复用的正文会话。"""
    if httpx is None:
        raise RuntimeError("番茄小说缺少 httpx 依赖")
    并发数 = max(1, int(并发数 or 1))
    return httpx.AsyncClient(
        http2=FULL_MGET_TRANSPORT != "http1",
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=并发数,
            max_keepalive_connections=并发数,
            keepalive_expiry=30.0,
        ),
        timeout=httpx.Timeout(60.0, connect=15.0),
    )


async def 异步番茄JSON请求(
    client: Any,
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    content: bytes = b"",
    retries: int = 2,
) -> Dict[str, Any]:
    """在复用会话中请求并解析 JSON，网络重试不占用解密线程。"""
    latest_error: BaseException | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                content=content if content else None,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            latest_error = exc
            if attempt < max(1, retries):
                await asyncio.sleep(0.2 * attempt)
    raise RuntimeError("番茄小说正文请求失败") from latest_error


async def 异步full_mget(
    client: Any,
    book_id: str,
    item_ids: List[str],
    sign_mode: str = "auto",
) -> Tuple[Dict[str, Any], int]:
    """使用 HTTP/2 异步会话拉取一批畅听正文。"""
    client_x, request_key = await asyncio.to_thread(make_encrypt_context)
    request_body = {
        "item_ids": [str(item_id) for item_id in item_ids],
        "book_id": NOVELFM_REQUEST_BOOK_ID,
        "key": request_key,
        "need_stt": False,
        "scene": 3,
        "tone_id": 91,
    }
    body_bytes = json_body_bytes(request_body)
    last_response: Dict[str, Any] = {}
    request_options = await asyncio.to_thread(
        full_mget_request_options,
        body_bytes,
        sign_mode,
    )
    for index, (mode, headers, url) in enumerate(request_options):
        data = await 异步番茄JSON请求(
            client,
            url,
            method="POST",
            headers=headers,
            content=body_bytes,
            retries=2,
        )
        last_response = data if isinstance(data, dict) else {}
        if (
            last_response.get("code") == 6000
            and index < len(request_options) - 1
            and mode not in {"fixed", "pure3040-legacy"}
        ):
            logger.debug("番茄小说正文签名已失效，继续尝试下一个内置签名")
            continue
        return last_response, client_x
    return last_response, client_x

def html_to_text(doc:str)->str:
    doc=re.sub(r'(?is)<(script|style).*?>.*?</\1>','',doc)
    paras=re.findall(r'(?is)<p\b[^>]*>(.*?)</p>',doc)
    if paras:
        lines=[]
        for p in paras:
            p=re.sub(r'(?is)<br\s*/?>','\n',p); p=re.sub(r'(?is)<[^>]+>','',p); p=html.unescape(p).strip()
            if p: lines.append(p)
        return '\n\n'.join(lines).strip()+'\n'
    text=re.sub(r'(?is)<br\s*/?>','\n',doc); text=re.sub(r'(?is)</p\s*>','\n\n',text); text=re.sub(r'(?is)<[^>]+>','',text)
    return re.sub(r'\n{3,}','\n\n',html.unescape(text)).strip()+'\n'

def batches(xs:List[str], n:int):
    for i in range(0,len(xs),n): yield xs[i:i+n]

def book_detail(book_id:str)->Dict[str,Any]:
    data=http_json(make_url('/novelfm/bookapi/detail/v1/',{'book_id':book_id}),headers={'User-Agent':DEFAULT_UA,'Accept-Encoding':'gzip'})
    return data.get('data') or {}


async def 异步获取番茄书籍详情(client: Any, book_id: str) -> Dict[str, Any]:
    url = make_url("/novelfm/bookapi/detail/v1/", {"book_id": str(book_id)})
    latest_error: BaseException | None = None
    for attempt in range(1, 4):
        try:
            data = await 异步番茄JSON请求(
                client,
                url,
                headers={"User-Agent": DEFAULT_UA, "Accept-Encoding": "gzip"},
                retries=1,
            )
            detail = data.get("data") if isinstance(data, dict) else None
            code = data.get("code") if isinstance(data, dict) else None
            if (
                code in (None, 0, "0")
                and isinstance(detail, dict)
                and (detail.get("book_name") or detail.get("title"))
            ):
                if detail.get("author") or detail.get("author_name"):
                    return detail
            latest_error = RuntimeError(f"详情业务响应无效：code={code}")
        except Exception as exc:
            latest_error = exc
        if attempt < 3:
            await asyncio.sleep(0.2 * attempt)
    raise RuntimeError("番茄小说详情请求失败") from latest_error


def 标准化番茄书籍比对文本(值: Any) -> str:
    文本 = html.unescape(str(值 or "")).strip().casefold()
    return re.sub(r"[\s\-_/\\|·•【】\[\]（）()《》<>\"'“”‘’：:，,。.!！?？~～]+", "", 文本)


def 提取番茄搜索书籍行(行: Any) -> list[Dict[str, Any]]:
    if not isinstance(行, dict):
        return []
    书籍列表 = 行.get("books")
    if isinstance(书籍列表, list):
        return [书籍 for 书籍 in 书籍列表 if isinstance(书籍, dict)]
    for 字段 in ("book", "book_info"):
        书籍 = 行.get(字段)
        if isinstance(书籍, dict):
            return [书籍]
    return [行]


def 获取番茄同书精确字数(
    书籍编号: str,
    详情: Dict[str, Any],
    章节数: int = 0,
) -> int:
    """为缺少字数的畅听副本查询同书的规范记录，并二次详情确认。"""
    if 提取有效番茄字数(
        详情.get("word_number"), 详情.get("word_count"), 详情.get("words")
    ) > 0:
        return 0
    标题 = str(详情.get("book_name") or 详情.get("title") or "").strip()
    作者 = str(详情.get("author") or 详情.get("author_name") or "").strip()
    标准标题 = 标准化番茄书籍比对文本(标题)
    标准作者 = 标准化番茄书籍比对文本(作者)
    目标章节数 = max(0, int(章节数 or 0))
    if not 标准标题 or not 标准作者:
        return 0
    try:
        响应 = signed_app_json(
            "/novelfm/bookmall/search/page/v1/",
            {"query": 标题, "offset": 0, "limit": 20},
            method="POST",
            timeout=20,
        )
    except Exception as 异常:
        logger.debug(
            f"番茄小说精确字数补查失败：书籍编号={书籍编号}, "
            f"错误={限制番茄日志文本(str(异常), 160)}"
        )
        return 0

    数据 = 响应.get("data") if isinstance(响应, dict) else None
    行列表 = 数据.get("search_data") if isinstance(数据, dict) else None
    候选列表: list[tuple[int, str, int]] = []
    for 行 in 行列表 if isinstance(行列表, list) else []:
        for 候选 in 提取番茄搜索书籍行(行):
            候选编号 = str(候选.get("book_id") or 候选.get("id") or "").strip()
            候选字数 = 提取有效番茄字数(
                候选.get("word_number"), 候选.get("word_count"), 候选.get("words")
            )
            if not 候选编号 or 候选编号 == str(书籍编号) or 候选字数 <= 0:
                continue
            if 标准化番茄书籍比对文本(候选.get("book_name") or 候选.get("title")) != 标准标题:
                continue
            if 标准化番茄书籍比对文本(候选.get("author") or 候选.get("author_name")) != 标准作者:
                continue
            候选章节数 = 安全番茄整数(
                候选.get("serial_count") or 候选.get("chapter_number"), 0
            )
            差异 = abs(候选章节数 - 目标章节数) if 候选章节数 and 目标章节数 else 0
            if 候选章节数 and 目标章节数 and 差异 > 1:
                continue
            候选列表.append((差异, 候选编号, 候选字数))

    for _差异, 候选编号, 搜索字数 in sorted(候选列表):
        try:
            候选详情 = book_detail(候选编号)
        except Exception as 异常:
            logger.debug(
                f"番茄小说规范字数详情失败：书籍编号={书籍编号}, "
                f"候选编号={候选编号}, 错误={限制番茄日志文本(str(异常), 160)}"
            )
            continue
        if 标准化番茄书籍比对文本(候选详情.get("book_name") or 候选详情.get("title")) != 标准标题:
            continue
        if 标准化番茄书籍比对文本(候选详情.get("author") or 候选详情.get("author_name")) != 标准作者:
            continue
        详情字数 = 提取有效番茄字数(
            候选详情.get("word_number"), 候选详情.get("word_count"), 候选详情.get("words")
        )
        if 详情字数 == 搜索字数:
            logger.debug(
                f"番茄小说精确字数补查成功：书籍编号={书籍编号}, 候选编号={候选编号}"
            )
            return 详情字数
    return 0


async def 异步获取番茄同书精确字数(
    client: Any,
    书籍编号: str,
    详情: Dict[str, Any],
    章节数: int = 0,
) -> int:
    if 提取有效番茄字数(
        详情.get("word_number"), 详情.get("word_count"), 详情.get("words")
    ) > 0:
        return 0
    title = str(详情.get("book_name") or 详情.get("title") or "").strip()
    author = str(详情.get("author") or 详情.get("author_name") or "").strip()
    normalized_title = 标准化番茄书籍比对文本(title)
    normalized_author = 标准化番茄书籍比对文本(author)
    target_count = max(0, int(章节数 or 0))
    if not normalized_title or not normalized_author:
        return 0
    try:
        response = await 异步签名番茄JSON(
            client,
            "/novelfm/bookmall/search/page/v1/",
            {"query": title, "offset": 0, "limit": 20},
            method="POST",
        )
    except Exception as exc:
        logger.debug(
            f"番茄小说精确字数补查失败：书籍编号={书籍编号}, 错误={type(exc).__name__}"
        )
        return 0
    data = response.get("data") if isinstance(response, dict) else None
    rows = data.get("search_data") if isinstance(data, dict) else None
    candidates: list[tuple[int, str, int]] = []
    for row in rows if isinstance(rows, list) else []:
        for candidate in 提取番茄搜索书籍行(row):
            candidate_id = str(candidate.get("book_id") or candidate.get("id") or "").strip()
            word_count = 提取有效番茄字数(
                candidate.get("word_number"), candidate.get("word_count"), candidate.get("words")
            )
            if not candidate_id or candidate_id == str(书籍编号) or word_count <= 0:
                continue
            if 标准化番茄书籍比对文本(candidate.get("book_name") or candidate.get("title")) != normalized_title:
                continue
            if 标准化番茄书籍比对文本(candidate.get("author") or candidate.get("author_name")) != normalized_author:
                continue
            candidate_chapters = 安全番茄整数(
                candidate.get("serial_count") or candidate.get("chapter_number"), 0
            )
            difference = abs(candidate_chapters - target_count) if candidate_chapters and target_count else 0
            if candidate_chapters and target_count and difference > 1:
                continue
            candidates.append((difference, candidate_id, word_count))
    for _difference, candidate_id, expected_words in sorted(candidates):
        try:
            candidate_detail = await 异步获取番茄书籍详情(client, candidate_id)
        except Exception as exc:
            logger.debug(
                f"番茄小说规范字数详情失败：书籍编号={书籍编号}, 候选编号={candidate_id}, "
                f"错误={type(exc).__name__}"
            )
            continue
        if 标准化番茄书籍比对文本(candidate_detail.get("book_name") or candidate_detail.get("title")) != normalized_title:
            continue
        if 标准化番茄书籍比对文本(candidate_detail.get("author") or candidate_detail.get("author_name")) != normalized_author:
            continue
        actual_words = 提取有效番茄字数(
            candidate_detail.get("word_number"), candidate_detail.get("word_count"), candidate_detail.get("words")
        )
        if actual_words == expected_words:
            logger.debug(
                f"番茄小说精确字数补查成功：书籍编号={书籍编号}, 候选编号={candidate_id}"
            )
            return actual_words
    return 0


def unique_item_ids(ids:Iterable[Any], book_id:str='')->List[str]:
    out=[]; seen=set()
    for x in ids:
        s=str(x).strip()
        if not re.fullmatch(r'\d{8,}', s): continue
        if book_id and s==str(book_id): continue
        if s in seen: continue
        seen.add(s); out.append(s)
    return out


def resolve_directory(book_id: str) -> List[str]:
    """通过番茄畅听目录接口获取章节 ID。"""
    last_error: Exception | None = None
    for version in (2, 1):
        try:
            item_ids, _response = app_directory_items(book_id, version=version, sign_mode="auto")
            if item_ids:
                return item_ids
        except Exception as error:
            last_error = error
    if last_error is not None:
        raise RuntimeError("番茄畅听目录接口请求失败") from last_error
    raise RuntimeError("番茄畅听目录接口未返回章节")


def directory_infos(book_id: str, item_ids: List[str], sign_mode: str = "auto") -> Dict[str, Dict[str, Any]]:
    """通过番茄畅听目录元数据接口批量读取章节标题和状态。"""
    body = {"book_id": str(book_id), "item_ids": [str(item_id) for item_id in item_ids], "page_scene": 6}
    data = signed_app_json("/novelfm/bookapi/directory/all_infos/v1/", body, sign_mode=sign_mode)
    rows = (data.get("data") if isinstance(data, dict) else None) or []
    return {str(row.get("item_id")): row for row in rows if isinstance(row, dict) and row.get("item_id")}


def 读取番茄目录元数据(书籍编号: str, item_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """读取章节元数据；失败只写日志，不影响正文下载。"""
    元数据: Dict[str, Dict[str, Any]] = {}
    for 批次 in batches(item_ids, 500):
        try:
            元数据.update(directory_infos(书籍编号, list(批次), sign_mode="auto"))
        except Exception as 异常:
            logger.warning(
                f"番茄小说目录元数据获取失败：书籍编号={书籍编号}, "
                f"范围={len(元数据) + 1}-{len(元数据) + len(批次)}, 错误={限制番茄日志文本(str(异常), 200)}"
            )
            break
    return 元数据


def 获取番茄目录标题(元数据: Dict[str, Any], 序号: int) -> str:
    """从目录元数据提取真实章节标题，避免全部回退成“第N章”。"""
    通用标题 = {"目录", "章节目录", "正文", "内容"}
    for 字段 in ("origin_chapter_title", "chapter_title", "title", "name"):
        标题 = 清理番茄网页文本(元数据.get(字段) if isinstance(元数据, dict) else "")
        if 标题 and 标题 not in 通用标题:
            return 标题
    return f"第{序号}章"

def app_directory_items(book_id:str, *, page_scene:int=6, version:int=2, sign_mode:str='auto')->Tuple[List[str],Dict[str,Any]]:
    """Try App directory item_id endpoints and return raw response for comparison."""
    path='/novelfm/bookapi/directory/all_items_v2/v1/' if version==2 else '/novelfm/bookapi/directory/all_items/v1/'
    query={'book_id':str(book_id),'page_scene':str(page_scene)}
    data=signed_app_json(path, None, query, method='GET', sign_mode=sign_mode)
    ids:List[Any]=[]
    if isinstance(data,dict):
        d=data.get('data')
        candidates=[d, data]
        for obj in candidates:
            if isinstance(obj,dict):
                for key in ('item_ids','itemIds','chapter_ids','chapterIds','ids'):
                    v=obj.get(key)
                    if isinstance(v,list):
                        ids.extend(v)
                for key in ('items','chapters','list','chapter_list','item_data_list','item_list','data_list'):
                    v=obj.get(key)
                    if isinstance(v,list):
                        for it in v:
                            if isinstance(it,dict):
                                ids.append(it.get('item_id') or it.get('itemId') or it.get('id'))
            elif isinstance(obj,list):
                for it in obj:
                    if isinstance(it,dict):
                        ids.append(it.get('item_id') or it.get('itemId') or it.get('id'))
                    else:
                        ids.append(it)
    return unique_item_ids(ids, book_id), data if isinstance(data,dict) else {'raw':data}


def 解析番茄目录项目(data: Any, book_id: str) -> List[str]:
    ids: List[Any] = []
    if isinstance(data, dict):
        payload = data.get("data")
        candidates = [payload, data]
        for obj in candidates:
            if isinstance(obj, dict):
                for key in ("item_ids", "itemIds", "chapter_ids", "chapterIds", "ids"):
                    value = obj.get(key)
                    if isinstance(value, list):
                        ids.extend(value)
                for key in ("items", "chapters", "list", "chapter_list", "item_data_list", "item_list", "data_list"):
                    value = obj.get(key)
                    if not isinstance(value, list):
                        continue
                    for item in value:
                        if isinstance(item, dict):
                            ids.append(item.get("item_id") or item.get("itemId") or item.get("id"))
            elif isinstance(obj, list):
                for item in obj:
                    ids.append(
                        (item.get("item_id") or item.get("itemId") or item.get("id"))
                        if isinstance(item, dict)
                        else item
                    )
    return unique_item_ids(ids, book_id)


async def 异步获取番茄目录项目(
    client: Any,
    book_id: str,
    *,
    page_scene: int = 6,
    version: int = 2,
    sign_mode: str = "auto",
) -> Tuple[List[str], Dict[str, Any]]:
    path = "/novelfm/bookapi/directory/all_items_v2/v1/" if version == 2 else "/novelfm/bookapi/directory/all_items/v1/"
    data = await 异步签名番茄JSON(
        client,
        path,
        None,
        {"book_id": str(book_id), "page_scene": str(page_scene)},
        method="GET",
        sign_mode=sign_mode,
    )
    return 解析番茄目录项目(data, book_id), data if isinstance(data, dict) else {"raw": data}


async def 异步解析番茄目录(
    client: Any,
    book_id: str,
) -> List[str]:
    latest_error: BaseException | None = None
    for version in (2, 1):
        try:
            item_ids, _response = await 异步获取番茄目录项目(client, book_id, version=version)
            if item_ids:
                return item_ids
        except Exception as exc:
            latest_error = exc
    if latest_error is not None:
        raise RuntimeError("番茄畅听目录接口请求失败") from latest_error
    raise RuntimeError("番茄畅听目录接口未返回章节")


async def 异步读取番茄目录元数据(
    client: Any,
    book_id: str,
    item_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    chunks = [list(chunk) for chunk in batches(item_ids, 500)]
    gate = asyncio.Semaphore(max(1, min(番茄正文最大动态并发数, len(chunks))))

    async def 请求一批(chunk: List[str]) -> Dict[str, Dict[str, Any]]:
        async with gate:
            data = await 异步签名番茄JSON(
                client,
                "/novelfm/bookapi/directory/all_infos/v1/",
                {"book_id": str(book_id), "item_ids": [str(item_id) for item_id in chunk], "page_scene": 6},
            )
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return {}
        return {
            str(row.get("item_id")): row
            for row in rows if isinstance(row, dict) and row.get("item_id")
        }

    metadata: Dict[str, Dict[str, Any]] = {}
    for index, result in enumerate(await asyncio.gather(*(请求一批(chunk) for chunk in chunks), return_exceptions=True)):
        if isinstance(result, Exception):
            logger.warning(
                f"番茄小说目录元数据获取失败：书籍编号={book_id}, 批次={index + 1}, "
                f"错误={type(result).__name__}"
            )
            continue
        metadata.update(result)
    return metadata


# ===== 番茄阅读正文补拉 =====
# 番茄畅听正文偶尔会返回 code=0 但单章正文为空；另有部分书在畅听/TTS
# 记录失效后仍可通过番茄阅读正文接口读取。该补拉只在畅听正文不可用或缺
# 章节时启用，返回结构会转换成 full/mget 的 item_infos 形态。
番茄阅读API地址 = "https://api5-normal-sinfonlinec.fqnovel.com"
番茄阅读请求书籍编号 = os.environ.get("FANQIE_NOVELAPP_REQUEST_BOOK_ID", "7320841644486446142").strip() or "7320841644486446142"
番茄阅读设备ID = "375350790467434"
番茄阅读安装ID = "375350790471530"
番茄阅读渠道 = "43536163a"
番茄阅读版本号 = "70132"
番茄阅读版本名 = "7.0.1.32"
番茄阅读设备型号 = "P30"
番茄阅读设备品牌 = "realme"
番茄阅读系统API = "30"
番茄阅读系统版本 = "10"
番茄阅读分辨率 = "1280*720"
番茄阅读DPI = "240"
番茄阅读ROM版本 = "JZUM.440813.61127057+release-keys"
番茄阅读CDID = "f4a80914-8137-4604-9e95-18946143c295"
番茄阅读UA = (
    "com.dragon.read.oversea.gp/70132 (Linux; U; Android 10; zh_CN; P30; "
    "Build/JZUM.440813.61127057;tt-ok/3.12.13.4-tiktok)"
)
番茄阅读注册AES密钥 = bytes.fromhex("ac25c67ddd8f38c1b37a2348828e222e")
番茄阅读ArgusAES密钥 = bytes.fromhex("d31e3718288a1027baab59f146a09a9c")
番茄阅读ArgusAES向量 = bytes.fromhex("ea180a0336ed352fcd24e4d50018ae54")
番茄阅读Argus掩码 = bytes.fromhex("f2f7fcfff2f7fcff")
番茄阅读Argus魔数 = bytes.fromhex("a66ead9f7701d00c18")
番茄阅读正文单次上限 = 30
番茄阅读注册密钥缓存: Dict[int, bytes] = {}
番茄阅读注册密钥异步锁: asyncio.Lock | None = None


def _番茄阅读URL编码值(键: str, 值: Any) -> str:
    文本 = str(值)
    if 键 in {"book_id", "device_type", "resolution", "rom_version"}:
        return urllib.parse.quote_plus(文本, safe="*")
    return 文本


def 构造番茄阅读查询(额外参数: Iterable[Tuple[str, Any]] = (), *, 毫秒时间戳: Optional[int] = None) -> str:
    if 毫秒时间戳 is None:
        毫秒时间戳 = int(time.time() * 1000)
    参数: List[Tuple[str, Any]] = [
        ("iid", 番茄阅读安装ID),
        ("device_id", 番茄阅读设备ID),
        ("ac", "wifi"),
        ("channel", 番茄阅读渠道),
        ("aid", "1967"),
        ("app_name", "novelapp"),
        ("version_code", 番茄阅读版本号),
        ("version_name", 番茄阅读版本名),
        ("device_platform", "android"),
        ("os", "android"),
        ("ssmix", "a"),
        ("device_type", 番茄阅读设备型号),
        ("device_brand", 番茄阅读设备品牌),
        ("language", "zh"),
        ("os_api", 番茄阅读系统API),
        ("os_version", 番茄阅读系统版本),
        ("manifest_version_code", 番茄阅读版本号),
        ("resolution", 番茄阅读分辨率),
        ("dpi", 番茄阅读DPI),
        ("update_version_code", 番茄阅读版本号),
        ("_rticket", str(int(毫秒时间戳))),
        ("host_abi", "arm64-v8a"),
        ("dragon_device_type", "pad"),
        ("pv_player", 番茄阅读版本号),
        ("compliance_status", "0"),
        ("need_personal_recommend", "1"),
        ("player_so_load", "1"),
        ("is_android_pad_screen", "1"),
        ("rom_version", 番茄阅读ROM版本),
        ("cdid", 番茄阅读CDID),
    ]
    参数.extend((str(键), 值) for 键, 值 in 额外参数)
    return "&".join(f"{键}={_番茄阅读URL编码值(键, 值)}" for 键, 值 in 参数)


def _生成番茄阅读Simon密钥() -> List[int]:
    初始值 = bytes.fromhex(
        "fc78e0a9657a0c748ce51559903ccf03"
        "510e51d3cff232d71343e88a321c5304"
    )
    掩码 = 0xFFFFFFFFFFFFFFFF
    密钥 = [int.from_bytes(初始值[i:i + 8], "little") for i in range(0, 32, 8)]
    种子 = 0x03DC94C3A046D678B
    for 序号 in range(4, 72):
        临时值 = _ror64(密钥[序号 - 1], 3) ^ 密钥[序号 - 3]
        位序号 = (((0xFC if 序号 < 0x42 else 0xBE) + 序号) & 0xFF) & 63
        z值 = ((~2 if ((种子 >> 位序号) & 1) else ~3) & 掩码) ^ 密钥[序号 - 4]
        密钥.append((_ror64(临时值, 1) ^ 临时值 ^ z值) & 掩码)
    return 密钥


番茄阅读Simon密钥 = _生成番茄阅读Simon密钥()


def _番茄阅读Simon加密(数据: bytes) -> bytes:
    if len(数据) % 16:
        raise ValueError("番茄阅读 Simon 输入必须按 16 字节对齐")
    掩码 = 0xFFFFFFFFFFFFFFFF
    输出 = bytearray()
    for 偏移 in range(0, len(数据), 16):
        左 = int.from_bytes(数据[偏移:偏移 + 8], "little")
        右 = int.from_bytes(数据[偏移 + 8:偏移 + 16], "little")
        for 密钥 in 番茄阅读Simon密钥:
            左, 右 = 右, (左 ^ _ror64(右, 62) ^ (_ror64(右, 56) & _ror64(右, 63)) ^ 密钥) & 掩码
        输出.extend(左.to_bytes(8, "little"))
        输出.extend(右.to_bytes(8, "little"))
    return bytes(输出)


def _番茄阅读半区反转交换(数据: bytes) -> bytes:
    输出 = bytearray(数据)
    半长 = len(输出) // 2
    后半起点 = len(输出) - 半长
    for 左 in range(半长):
        右 = 后半起点 + (半长 - 1 - 左)
        输出[左], 输出[右] = 输出[右], 输出[左]
    return bytes(输出)


def 生成番茄阅读XArgus(原始查询: str, 秒时间戳: int, *, 随机值: Optional[int] = None) -> str:
    if 随机值 is None:
        随机值 = secrets.randbits(31)
    pv = lambda 字段, 值: proto_key(字段, 0) + proto_varint(int(值))
    pb = lambda 字段, 值: proto_field_bytes(字段, 值)
    嵌套 = (
        pb(1, 番茄阅读设备型号)
        + pb(2, 番茄阅读系统版本)
        + pb(3, b"googleplay")
        + pv(4, 0x50000000)
    )
    载荷 = b"".join((
        pv(1, 0x40401252),
        pv(2, 2),
        pv(3, int(随机值) & 0x7FFFFFFF),
        pb(4, b"1967"),
        pb(5, 番茄阅读设备ID.encode()),
        pb(6, b"1611921764"),
        pb(7, 番茄阅读版本名.encode()),
        pb(8, b"v04.04.05-ov-android"),
        pv(9, 0x08080A40),
        pb(10, b"\x00" * 8),
        pv(11, 0),
        pv(12, int(秒时间戳) * 2),
        pb(13, sm3(b"\x00" * 16)[:6]),
        pb(14, sm3(原始查询.encode())[:6]),
        pv(20, 738),
        pb(23, 嵌套),
    ))
    加密后 = _番茄阅读Simon加密(_pkcs7_pad(载荷))
    异或后 = bytes(值 ^ 番茄阅读Argus掩码[序号 & 7] for 序号, 值 in enumerate(加密后))
    帧 = 番茄阅读Argus魔数 + _番茄阅读半区反转交换(番茄阅读Argus掩码 + 异或后) + b"ao"
    return base64.b64encode(b"\xf2\x81" + aes_cbc_encrypt(帧, 番茄阅读ArgusAES密钥, 番茄阅读ArgusAES向量)).decode()


def 生成番茄阅读Ladon(秒时间戳: int, *, 随机前缀: Optional[bytes] = None) -> str:
    if 随机前缀 is None:
        随机前缀 = secrets.token_bytes(4)
    if len(随机前缀) != 4:
        raise ValueError("番茄阅读 Ladon 随机前缀必须是 4 字节")
    掩码 = 0xFFFFFFFFFFFFFFFF
    md5十六进制 = hashlib.md5(随机前缀 + b"1967").hexdigest().encode()
    表 = bytearray(288)
    表[:32] = md5十六进制
    队列 = [int.from_bytes(表[序号:序号 + 8], "little") for 序号 in range(0, 32, 8)]
    第一, 第二 = 队列[0], 队列[1]
    队列 = 队列[2:]
    for 序号 in range(0x22):
        值 = ((_ror64(第二, 8) + 第一) ^ 序号) & 掩码
        队列.append(值)
        值 ^= _ror64(第一, 0x3D)
        值 &= 掩码
        表[(序号 + 1) * 8:(序号 + 2) * 8] = 值.to_bytes(8, "little")
        第一 = 值
        第二 = 队列.pop(0)
    原始 = _pkcs7_pad(f"{int(秒时间戳)}-1611921764-3019".encode())
    加密结果 = bytearray()
    for 偏移 in range(0, len(原始), 16):
        左 = int.from_bytes(原始[偏移:偏移 + 8], "little")
        右 = int.from_bytes(原始[偏移 + 8:偏移 + 16], "little")
        for 序号 in range(0x22):
            密钥 = int.from_bytes(表[序号 * 8:序号 * 8 + 8], "little")
            右 = (密钥 ^ (左 + _ror64(右, 8))) & 掩码
            左 = (右 ^ _ror64(左, 0x3D)) & 掩码
        加密结果.extend(左.to_bytes(8, "little"))
        加密结果.extend(右.to_bytes(8, "little"))
    return base64.b64encode(随机前缀 + bytes(加密结果)).decode()


def 构造番茄阅读请求头(原始查询: str, 毫秒时间戳: int, *, 内容类型: Optional[str] = None) -> Dict[str, str]:
    秒时间戳 = int(time.time())
    请求头 = {
        "Accept-Encoding": "gzip",
        "Accept": "application/json; charset=utf-8,application/x-protobuf",
        "X-Xs-From-Web": "0",
        "X-SS-REQ-TICKET": str(int(毫秒时间戳)),
        "X-Reading-Request": f"{int(毫秒时间戳)}-{secrets.randbelow(2_000_000_000)}",
        "X-VC-BDTuring-SDK-Version": "3.7.2.cn",
        "LC": "101",
        "SDK-Version": "2",
        "Passport-SDK-Version": "50564",
        "X-TT-Store-Region": "cn-zj",
        "X-TT-Store-Region-Src": "did",
        "User-Agent": 番茄阅读UA,
        "Cookie": f"store-region=cn-zj; store-region-src=did; install_id={番茄阅读安装ID};",
        "X-Khronos": str(秒时间戳),
        "X-Argus": 生成番茄阅读XArgus(原始查询, 秒时间戳),
        "X-Ladon": 生成番茄阅读Ladon(秒时间戳),
        "X-Helios": 生成番茄阅读Ladon(秒时间戳),
    }
    if 内容类型:
        请求头["Content-Type"] = 内容类型
    return 请求头


def 请求番茄阅读JSON(路径: str, 额外参数: Iterable[Tuple[str, Any]] = (), *, method: str = "GET", body: Any = None) -> Dict[str, Any]:
    毫秒时间戳 = int(time.time() * 1000)
    原始查询 = 构造番茄阅读查询(额外参数, 毫秒时间戳=毫秒时间戳)
    地址 = f"{番茄阅读API地址}{路径}?{原始查询}"
    请求体 = b"" if body is None else json_body_bytes(body)
    请求头 = 构造番茄阅读请求头(原始查询, 毫秒时间戳, 内容类型="application/json" if body is not None else None)
    响应 = http_json_bytes(地址, method, 请求头, 请求体, timeout=60, retries=2)
    return 响应 if isinstance(响应, dict) else {}


def _获取番茄阅读注册密钥异步锁() -> asyncio.Lock:
    global 番茄阅读注册密钥异步锁
    if 番茄阅读注册密钥异步锁 is None:
        番茄阅读注册密钥异步锁 = asyncio.Lock()
    return 番茄阅读注册密钥异步锁


async def 异步请求番茄阅读JSON(
    client: Any,
    路径: str,
    额外参数: Iterable[Tuple[str, Any]] = (),
    *,
    method: str = "GET",
    body: Any = None,
) -> Dict[str, Any]:
    毫秒时间戳 = int(time.time() * 1000)
    原始查询 = 构造番茄阅读查询(额外参数, 毫秒时间戳=毫秒时间戳)
    地址 = f"{番茄阅读API地址}{路径}?{原始查询}"
    请求体 = b"" if body is None else json_body_bytes(body)
    请求头 = 构造番茄阅读请求头(
        原始查询,
        毫秒时间戳,
        内容类型="application/json" if body is not None else None,
    )
    return await 异步番茄JSON请求(
        client,
        地址,
        method=method,
        headers=请求头,
        content=请求体,
        retries=2,
    )


def 获取番茄阅读注册密钥(需要版本: int = 0) -> bytes:
    if 需要版本 and 需要版本 in 番茄阅读注册密钥缓存:
        return 番茄阅读注册密钥缓存[需要版本]
    iv = secrets.token_bytes(16)
    载荷 = struct.pack("<QQ", int(番茄阅读设备ID), 0)
    content = base64.b64encode(iv + aes_cbc_encrypt(载荷, 番茄阅读注册AES密钥, iv)).decode()
    响应 = 请求番茄阅读JSON("/reading/crypt/registerkey", method="POST", body={"content": content, "keyver": 1})
    data = 响应.get("data") or {}
    if 响应.get("code") != 0 or not isinstance(data, dict) or not data.get("key"):
        raise RuntimeError(f"番茄阅读注册密钥失败：code={响应.get('code')}, message={响应.get('message') or 响应.get('msg')}")
    raw = base64.b64decode(str(data["key"]))
    if len(raw) < 32:
        raise RuntimeError("番茄阅读注册密钥响应过短")
    明文 = aes_cbc_decrypt(raw[16:], 番茄阅读注册AES密钥, raw[:16])
    if len(明文) < 16:
        raise RuntimeError("番茄阅读注册密钥明文过短")
    版本 = int(data.get("keyver") or 0)
    密钥 = 明文[:16]
    if 版本:
        番茄阅读注册密钥缓存[版本] = 密钥
    if 需要版本:
        番茄阅读注册密钥缓存[需要版本] = 密钥
    return 密钥


async def 异步获取番茄阅读注册密钥(client: Any, 需要版本: int = 0) -> bytes:
    if 需要版本 and 需要版本 in 番茄阅读注册密钥缓存:
        return 番茄阅读注册密钥缓存[需要版本]
    async with _获取番茄阅读注册密钥异步锁():
        if 需要版本 and 需要版本 in 番茄阅读注册密钥缓存:
            return 番茄阅读注册密钥缓存[需要版本]
        iv = secrets.token_bytes(16)
        payload = struct.pack("<QQ", int(番茄阅读设备ID), 0)
        encrypted = aes_cbc_encrypt(payload, 番茄阅读注册AES密钥, iv)
        content = base64.b64encode(iv + encrypted).decode()
        response = await 异步请求番茄阅读JSON(
            client,
            "/reading/crypt/registerkey",
            method="POST",
            body={"content": content, "keyver": 1},
        )
        data = response.get("data") or {}
        if response.get("code") != 0 or not isinstance(data, dict) or not data.get("key"):
            raise RuntimeError("番茄阅读注册密钥失败")
        raw = base64.b64decode(str(data["key"]))
        if len(raw) < 32:
            raise RuntimeError("番茄阅读注册密钥响应过短")
        plaintext = await asyncio.to_thread(
            aes_cbc_decrypt,
            raw[16:],
            番茄阅读注册AES密钥,
            raw[:16],
        )
        if len(plaintext) < 16:
            raise RuntimeError("番茄阅读注册密钥明文过短")
        version = int(data.get("keyver") or 0)
        key = plaintext[:16]
        if version:
            番茄阅读注册密钥缓存[version] = key
        if 需要版本:
            番茄阅读注册密钥缓存[需要版本] = key
        return key


def 解密番茄阅读正文(content: str, 密钥: bytes) -> str:
    raw = base64.b64decode(content)
    if len(raw) < 32:
        raise RuntimeError("番茄阅读章节密文过短")
    明文 = aes_cbc_decrypt(raw[16:], 密钥[:16], raw[:16])
    if 明文[:2] == b"\x1f\x8b":
        明文 = gzip.decompress(明文)
    elif 明文[:1] == b"\x78":
        try:
            明文 = zlib.decompress(明文)
        except zlib.error:
            pass
    return 明文.decode("utf-8", "replace")


def 请求番茄阅读原始正文(item_ids: List[str]) -> Dict[str, Any]:
    """使用固定阅读 App 书籍上下文读取原始章节响应。"""
    ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
    if len(ids) > 番茄阅读正文单次上限:
        raise ValueError("番茄阅读原始正文请求超过单次章节上限")
    if not ids:
        return {"code": 0, "message": "", "data": {}}
    return 请求番茄阅读JSON(
        "/reading/reader/batch_full/v",
        (
            ("item_ids", ",".join(ids)),
            ("key_register_ts", "0"),
            ("book_id", 番茄阅读请求书籍编号),
            ("req_type", "0"),
        ),
    )


async def 异步请求番茄阅读原始正文(client: Any, item_ids: List[str]) -> Dict[str, Any]:
    """通过当前 HTTP/2 会话请求阅读 App 的缺章补拉接口。"""
    ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
    if len(ids) > 番茄阅读正文单次上限:
        raise ValueError("番茄阅读原始正文请求超过单次章节上限")
    if not ids:
        return {"code": 0, "message": "", "data": {}}
    return await 异步请求番茄阅读JSON(
        client,
        "/reading/reader/batch_full/v",
        (
            ("item_ids", ",".join(ids)),
            ("key_register_ts", "0"),
            ("book_id", 番茄阅读请求书籍编号),
            ("req_type", "0"),
        ),
    )


def 解析番茄阅读章节书籍编号(章节编号: str) -> Tuple[str, Dict[str, Any]]:
    """将 /reader/ 中的章节 ID 解析为真实书籍 ID，仅走阅读 App 正文接口。"""
    候选章节编号 = str(章节编号 or "").strip()
    if not re.fullmatch(r"\d{8,}", 候选章节编号):
        raise RuntimeError("番茄阅读章节编号无效")

    响应 = 请求番茄阅读原始正文([候选章节编号])
    if 响应.get("code") != 0:
        raise RuntimeError("番茄阅读正文接口未返回章节")
    原始章节 = 响应.get("data") or {}
    if not isinstance(原始章节, dict):
        raise RuntimeError("番茄阅读正文响应格式错误")
    章节信息 = 原始章节.get(候选章节编号)
    if not isinstance(章节信息, dict):
        raise RuntimeError("番茄阅读正文未返回目标章节")
    书籍元数据 = 章节信息.get("novel_data")
    if not isinstance(书籍元数据, dict):
        raise RuntimeError("番茄阅读正文未返回书籍信息")
    真实书籍编号 = str(书籍元数据.get("book_id") or "").strip()
    if not re.fullmatch(r"\d{8,}", 真实书籍编号):
        raise RuntimeError("番茄阅读正文未返回有效书籍编号")
    return 真实书籍编号, 书籍元数据


async def 异步解析番茄阅读章节书籍编号(
    client: Any,
    章节编号: str,
) -> Tuple[str, Dict[str, Any]]:
    candidate_id = str(章节编号 or "").strip()
    if not re.fullmatch(r"\d{8,}", candidate_id):
        raise RuntimeError("番茄阅读章节编号无效")
    response = await 异步请求番茄阅读原始正文(client, [candidate_id])
    if response.get("code") != 0:
        raise RuntimeError("番茄阅读正文接口未返回章节")
    raw_items = response.get("data") or {}
    if not isinstance(raw_items, dict):
        raise RuntimeError("番茄阅读正文响应格式错误")
    item = raw_items.get(candidate_id)
    if not isinstance(item, dict):
        raise RuntimeError("番茄阅读正文未返回目标章节")
    metadata = item.get("novel_data")
    if not isinstance(metadata, dict):
        raise RuntimeError("番茄阅读正文未返回书籍信息")
    book_id = str(metadata.get("book_id") or "").strip()
    if not re.fullmatch(r"\d{8,}", book_id):
        raise RuntimeError("番茄阅读正文未返回有效书籍编号")
    return book_id, metadata


def 读取番茄阅读正文(书籍编号: str, item_ids: List[str]) -> Dict[str, Any]:
    """读取番茄阅读正文，并转换成 full/mget 风格响应。"""
    ids = [str(item_id) for item_id in item_ids]
    if len(ids) > 番茄阅读正文单次上限:
        合并: Dict[str, Dict[str, Any]] = {}
        for 分段 in batches(ids, 番茄阅读正文单次上限):
            部分响应 = 读取番茄阅读正文(书籍编号, list(分段))
            if 部分响应.get("code") != 0:
                return 部分响应
            部分正文 = (部分响应.get("data") or {}).get("item_infos") or {}
            if not isinstance(部分正文, dict):
                raise RuntimeError("番茄阅读正文分段响应格式错误")
            合并.update(部分正文)
        return {
            "code": 0,
            "message": "",
            "data": {"item_infos": 合并},
            "source": "novelapp_reader_batch_full",
            "request_book_id": 番茄阅读请求书籍编号,
        }

    响应 = 请求番茄阅读原始正文(ids)
    if 响应.get("code") != 0:
        return 响应
    原始章节 = 响应.get("data") or {}
    if not isinstance(原始章节, dict):
        raise RuntimeError("番茄阅读正文响应格式错误")
    infos: Dict[str, Dict[str, Any]] = {}
    for item_id in ids:
        item = 原始章节.get(item_id)
        if not isinstance(item, dict):
            continue
        密文 = str(item.get("content") or "")
        if not 密文:
            continue
        版本 = int(item.get("key_version") or 0)
        明文 = 解密番茄阅读正文(密文, 获取番茄阅读注册密钥(版本))
        info = dict(item)
        info["content"] = 明文
        info["crypt_status"] = 0
        info.setdefault("title", item.get("title") or "")
        infos[item_id] = info
    return {
        "code": 0,
        "message": 响应.get("message") or "",
        "data": {"item_infos": infos},
        "source": "novelapp_reader_batch_full",
        "request_book_id": 番茄阅读请求书籍编号,
    }


async def 异步读取番茄阅读正文(
    client: Any,
    书籍编号: str,
    item_ids: List[str],
) -> Dict[str, Any]:
    """异步读取阅读 App 正文，并用 PyCryptodome 的 AES-CBC 解密补拉内容。"""
    ids = [str(item_id) for item_id in item_ids]
    if len(ids) > 番茄阅读正文单次上限:
        merged: Dict[str, Dict[str, Any]] = {}
        parts = [list(part) for part in batches(ids, 番茄阅读正文单次上限)]
        gate = asyncio.Semaphore(min(番茄正文最大动态并发数, len(parts)))

        async def 读取分段(part: List[str]) -> Dict[str, Any]:
            async with gate:
                return await 异步读取番茄阅读正文(client, 书籍编号, part)

        for partial in await asyncio.gather(*(读取分段(part) for part in parts)):
            if partial.get("code") != 0:
                return partial
            item_infos = (partial.get("data") or {}).get("item_infos") or {}
            if not isinstance(item_infos, dict):
                raise RuntimeError("番茄阅读正文分段响应格式错误")
            merged.update(item_infos)
        return {
            "code": 0,
            "message": "",
            "data": {"item_infos": merged},
            "source": "novelapp_reader_batch_full",
            "request_book_id": 番茄阅读请求书籍编号,
        }

    response = await 异步请求番茄阅读原始正文(client, ids)
    if response.get("code") != 0:
        return response
    raw_items = response.get("data") or {}
    if not isinstance(raw_items, dict):
        raise RuntimeError("番茄阅读正文响应格式错误")
    decrypt_gate = asyncio.Semaphore(max(1, min(64, (os.cpu_count() or 4) * 2)))

    async def 解密章节(item_id: str) -> tuple[str, Dict[str, Any] | None]:
        item = raw_items.get(item_id)
        if not isinstance(item, dict):
            return item_id, None
        ciphertext = str(item.get("content") or "")
        if not ciphertext:
            return item_id, None
        version = int(item.get("key_version") or 0)
        key = await 异步获取番茄阅读注册密钥(client, version)
        async with decrypt_gate:
            plaintext = await asyncio.to_thread(解密番茄阅读正文, ciphertext, key)
        info = dict(item)
        info["content"] = plaintext
        info["crypt_status"] = 0
        info.setdefault("title", item.get("title") or "")
        return item_id, info

    infos: Dict[str, Dict[str, Any]] = {}
    for item_id, item in await asyncio.gather(*(解密章节(item_id) for item_id in ids)):
        if item is not None:
            infos[item_id] = item
    return {
        "code": 0,
        "message": response.get("message") or "",
        "data": {"item_infos": infos},
        "source": "novelapp_reader_batch_full",
        "request_book_id": 番茄阅读请求书籍编号,
    }


def 尝试番茄阅读正文补拉(书籍编号: str, item_ids: List[str], 原因: str) -> Optional[Dict[str, Any]]:
    try:
        响应 = 读取番茄阅读正文(书籍编号, item_ids)
        infos = (响应.get("data") or {}).get("item_infos") or {}
        if 响应.get("code") == 0 and infos:
            logger.debug(
                f"番茄小说正文补拉成功：书籍编号={书籍编号}, 原因={原因}, "
                f"成功={len(infos)}/{len(item_ids)}"
            )
            return 响应
        logger.debug(
            f"番茄小说正文补拉无可用章节：书籍编号={书籍编号}, 原因={原因}, "
            f"业务代码={响应.get('code')}, 消息={限制番茄日志文本(str(响应.get('message') or 响应.get('msg') or ''), 200)}, "
            f"成功={len(infos)}/{len(item_ids)}"
        )
    except Exception as 异常:
        logger.warning(
            f"番茄小说正文补拉失败：书籍编号={书籍编号}, 原因={原因}, "
            f"错误={限制番茄日志文本(str(异常), 200)}"
        )
    return None


async def 异步尝试番茄阅读正文补拉(
    client: Any,
    书籍编号: str,
    item_ids: List[str],
    原因: str,
) -> Optional[Dict[str, Any]]:
    try:
        response = await 异步读取番茄阅读正文(client, 书籍编号, item_ids)
        infos = (response.get("data") or {}).get("item_infos") or {}
        if response.get("code") == 0 and infos:
            logger.debug(
                f"番茄小说正文补拉成功：书籍编号={书籍编号}, 原因={原因}, "
                f"成功={len(infos)}/{len(item_ids)}"
            )
            return response
        logger.debug(
            f"番茄小说正文补拉无可用章节：书籍编号={书籍编号}, 原因={原因}, "
            f"业务代码={response.get('code')}, 成功={len(infos)}/{len(item_ids)}"
        )
    except Exception as exc:
        logger.warning(
            f"番茄小说正文补拉失败：书籍编号={书籍编号}, 原因={原因}, "
            f"错误={type(exc).__name__}"
        )
    return None

# ===== 正文下载 =====
def full_mget(book_id: str, item_ids: List[str], sign_mode: str = "auto") -> Tuple[Dict[str, Any], int]:
    """按章节 ID 批量请求正文，使用稳定的畅听请求上下文。"""
    client_x, request_key = make_encrypt_context()
    request_body = {
        "item_ids": [str(item_id) for item_id in item_ids],
        "book_id": NOVELFM_REQUEST_BOOK_ID,
        "key": request_key,
        "need_stt": False,
        "scene": 3,
        "tone_id": 91,
    }
    body_bytes = json_body_bytes(request_body)
    last_response: Dict[str, Any] = {}
    request_options = full_mget_request_options(body_bytes, sign_mode)
    for index, (mode, headers, url) in enumerate(request_options):
        data = full_mget_http_json(url, headers, body_bytes, timeout=60)
        last_response = data if isinstance(data, dict) else {}
        if last_response.get("code") == 6000 and index < len(request_options) - 1 and mode not in {"fixed", "pure3040-legacy"}:
            logger.debug("番茄小说正文签名已失效，继续尝试下一个内置签名")
            continue
        return last_response, client_x
    return last_response, client_x

class FullMgetBusinessError(RuntimeError):
    """full/mget 明确返回业务错误时使用；这类错误拆分重试也不会恢复。"""

    pass

def _full_mget_response_message(resp:Dict[str,Any])->str:
    return str(resp.get('message') or resp.get('msg') or resp.get('err_msg') or resp.get('error') or '')

def _is_full_mget_non_split_error(resp:Dict[str,Any])->bool:
    code=resp.get('code')
    msg=_full_mget_response_message(resp)
    if code in {1021001, 1021002, 1021003}:
        return True
    return any(key in msg for key in ('该书不存在', '停止合作', '付费', '请去书城阅读新书'))

def download_batch(book_id:str, batch:List[str], allow_split:bool=True, sign_mode:str='auto')->List[Tuple[str,Optional[Dict[str,Any]],Optional[int],Optional[BaseException]]]:
    try:
        resp,x=full_mget(book_id,batch,sign_mode)
        if resp.get('code')!=0:
            if _is_full_mget_non_split_error(resp):
                补拉响应 = 尝试番茄阅读正文补拉(book_id, batch, f'full_mget code={resp.get("code")}')
                if 补拉响应:
                    补拉正文 = (补拉响应.get('data') or {}).get('item_infos') or {}
                    return [(item_id, 补拉正文.get(str(item_id)), 0, None) for item_id in batch]
                raise FullMgetBusinessError(f'full_mget 业务错误: code={resp.get("code")}, message={_full_mget_response_message(resp)}')
            raise RuntimeError(f'full_mget 错误: {resp}')
        infos=(resp.get('data') or {}).get('item_infos') or {}
        if allow_split and len(batch)>1 and len(infos)<len(batch):
            mid=max(1,len(batch)//2)
            return download_batch(book_id,batch[:mid],True,sign_mode)+download_batch(book_id,batch[mid:],True,sign_mode)
        if len(batch)==1 and len(infos)<len(batch):
            补拉响应 = 尝试番茄阅读正文补拉(book_id, batch, 'full_mget missing item_info')
            if 补拉响应:
                补拉正文 = (补拉响应.get('data') or {}).get('item_infos') or {}
                if 补拉正文.get(str(batch[0])):
                    return [(batch[0], 补拉正文.get(str(batch[0])), 0, None)]
        return [(item_id, infos.get(str(item_id)), x, None) for item_id in batch]
    except Exception as e:
        if isinstance(e, FullMgetBusinessError):
            return [(item_id, None, None, e) for item_id in batch]
        if allow_split and len(batch)>1:
            mid=max(1,len(batch)//2)
            return download_batch(book_id,batch[:mid],True,sign_mode)+download_batch(book_id,batch[mid:],True,sign_mode)
        return [(item_id, None, None, e) for item_id in batch]


async def 异步下载番茄正文批次(
    client: Any,
    request_gate: asyncio.Semaphore,
    book_id: str,
    batch: List[str],
    *,
    allow_split: bool = True,
    sign_mode: str = "auto",
) -> List[Tuple[str, Optional[Dict[str, Any]], Optional[int], Optional[BaseException]]]:
    """异步拉取正文；缺章时只拆分失败范围并继续复用同一 HTTP/2 会话。"""
    try:
        async with request_gate:
            response, client_x = await 异步full_mget(client, book_id, batch, sign_mode)
        if response.get("code") != 0:
            if _is_full_mget_non_split_error(response):
                fallback = await 异步尝试番茄阅读正文补拉(
                    client,
                    book_id,
                    batch,
                    f"full_mget code={response.get('code')}",
                )
                if fallback:
                    infos = (fallback.get("data") or {}).get("item_infos") or {}
                    return [(item_id, infos.get(str(item_id)), 0, None) for item_id in batch]
                raise FullMgetBusinessError(
                    f"full_mget 业务错误: code={response.get('code')}, "
                    f"message={_full_mget_response_message(response)}"
                )
            raise RuntimeError("full_mget 响应失败")

        infos = (response.get("data") or {}).get("item_infos") or {}
        if allow_split and len(batch) > 1 and len(infos) < len(batch):
            midpoint = max(1, len(batch) // 2)
            first, second = await asyncio.gather(
                异步下载番茄正文批次(
                    client, request_gate, book_id, batch[:midpoint], sign_mode=sign_mode
                ),
                异步下载番茄正文批次(
                    client, request_gate, book_id, batch[midpoint:], sign_mode=sign_mode
                ),
            )
            return first + second
        if len(batch) == 1 and len(infos) < 1:
            fallback = await 异步尝试番茄阅读正文补拉(
                client,
                book_id,
                batch,
                "full_mget missing item_info",
            )
            if fallback:
                infos = (fallback.get("data") or {}).get("item_infos") or {}
                if infos.get(str(batch[0])):
                    return [(batch[0], infos.get(str(batch[0])), 0, None)]
        return [(item_id, infos.get(str(item_id)), client_x, None) for item_id in batch]
    except Exception as exc:
        if isinstance(exc, FullMgetBusinessError):
            return [(item_id, None, None, exc) for item_id in batch]
        if allow_split and len(batch) > 1:
            midpoint = max(1, len(batch) // 2)
            first, second = await asyncio.gather(
                异步下载番茄正文批次(
                    client, request_gate, book_id, batch[:midpoint], sign_mode=sign_mode
                ),
                异步下载番茄正文批次(
                    client, request_gate, book_id, batch[midpoint:], sign_mode=sign_mode
                ),
            )
            return first + second
        return [(item_id, None, None, exc) for item_id in batch]

def decrypt_item_worker(args:Tuple[int,str,Dict[str,Any],int])->Dict[str,Any]:
    index,item_id,info,x=args
    try:
        content=info.get('content') or ''
        server_key=info.get('key') or ''
        chapter_html=decrypt_content(content,server_key,x) if info.get('crypt_status')==1 and content and server_key and x is not None else content
        title=获取番茄章节标题(info, index, chapter_html)
        text=html_to_text(chapter_html)
        return {'index':index,'item_id':item_id,'title':title,'text':text,'error':None}
    except Exception as e:
        return {'index':index,'item_id':item_id,'title':f'第{index}章','text':'','error':str(e)}


def 获取番茄章节标题(正文信息: Dict[str, Any], 序号: int, 正文HTML: Any = "") -> str:
    """忽略“目录”等通用响应标题，优先保留真实章节标题。"""
    小说数据 = 正文信息.get("novel_data") if isinstance(正文信息.get("novel_data"), dict) else {}
    候选标题 = (
        正文信息.get("chapter_title"),
        正文信息.get("chapterTitle"),
        正文信息.get("origin_chapter_title"),
        小说数据.get("chapter_title"),
        小说数据.get("chapterTitle"),
        小说数据.get("origin_chapter_title"),
        小说数据.get("title"),
        正文信息.get("title"),
        正文信息.get("name"),
        小说数据.get("name"),
    )
    通用标题 = {"目录", "章节目录", "正文", "内容"}
    for 候选标题文本 in 候选标题:
        标题 = html.unescape(re.sub(r"<[^>]+>", "", str(候选标题文本 or ""))).strip()
        if 标题 and 标题 not in 通用标题:
            return 标题

    标题匹配 = re.search(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", str(正文HTML or ""))
    if 标题匹配:
        标题 = html.unescape(re.sub(r"<[^>]+>", "", 标题匹配.group(1))).strip()
        if 标题 and 标题 not in 通用标题:
            return 标题
    return f"第{序号}章"


def 番茄章节信息返回成功(正文信息: Dict[str, Any]) -> bool:
    """只要接口明确返回该章节且章节 code 为 0，就视为成功；正文为空可能是审核中章节。"""
    if not isinstance(正文信息, dict) or not 正文信息:
        return False
    章节代码 = 正文信息.get("code")
    if 章节代码 in (None, "", 0, "0"):
        return True
    try:
        return int(章节代码) == 0
    except (TypeError, ValueError):
        return False

def fetch_batch_worker(args:Tuple[int,int,str,List[str],str])->Dict[str,Any]:
    bi,start_index,book_id,batch,sign_mode=args
    t0=time.perf_counter()
    results=download_batch(book_id,batch,allow_split=True,sign_mode=sign_mode)
    ok=sum(1 for _item_id,info,_x,err in results if info and not err)
    fatal_error=next((err for _item_id,_info,_x,err in results if isinstance(err,FullMgetBusinessError)),None)
    return {
        'batch':bi,
        'start':start_index,
        'end':start_index+len(batch)-1,
        'count':len(batch),
        'ok':ok,
        'fatal_error':str(fatal_error) if fatal_error else '',
        'elapsed':time.perf_counter()-t0,
        'results':results,
    }

番茄正文最大批量章节数 = 1500

番茄正文最大动态并发数 = 5

番茄进度日志分段数 = 10


番茄下载缓存目录 = Path(__file__).resolve().parents[3] / "下载缓存"

番茄文件声明 = "声明：本文件由机器人自动整理生成，仅供个人学习交流和临时阅读使用。内容版权归原作者及相关平台所有，请勿用于商业用途或二次传播。如喜欢本书，请支持正版。"

番茄下载失败提示 = "下载失败"

番茄文件发送失败提示 = "文件发送失败，请稍后再试"

番茄域名正则 = re.compile(r"fanqienovel\.com|changdunovel\.com|fqnovel\.com|novelfm\.com", re.I)

番茄长读短链正则 = re.compile(r"https?://(?:www\.)?(?:changdunovel\.com/t|m\.novelfm\.com/s)/[A-Za-z0-9_-]+/?", re.I)

番茄链接正则 = re.compile(r"https?://[^\s'\"<>，。]+", re.I)

番茄短篇详情地址 = "https://api5-normal-sinfonlinec.fqnovel.com/reading/ugc/postdata/detail/v1/"

def 计算番茄正文批量参数(章节总数: int) -> tuple[int, int]:
    章节总数 = max(0, int(章节总数 or 0))
    if 章节总数 <= 0:
        return 0, 1
    批量章节数 = min(章节总数, max(1, 番茄正文最大批量章节数))
    批次数 = (章节总数 + 批量章节数 - 1) // 批量章节数
    动态并发数 = max(1, min(番茄正文最大动态并发数, 批次数))
    return 批量章节数, 动态并发数

def 获取番茄小说回复流(event: Any, 命令文本: str, 配置: Any = None):
    来源 = 提取直接番茄链接参数(命令文本) or 提取事件番茄链接(event)
    if 来源 is None:
        return None
    return 生成番茄下载回复流(event, 来源, 配置)


async def 是否番茄一章短篇来源(命令文本: Any) -> bool:
    """识别短篇分享；短链需展开后才能区分普通书籍和短篇。"""
    文本 = str(命令文本 or "")
    if 提取番茄短篇编号(文本) or re.search(r"short-story-share|一章短篇", 文本, re.I):
        return True
    来源 = 提取直接番茄链接参数(文本)
    if not 来源 or not 番茄长读短链正则.search(来源):
        return False
    展开来源 = await 展开番茄短链(来源)
    return bool(提取番茄短篇编号(展开来源))

async def 生成番茄下载回复流(
    event: Any,
    来源: str,
    配置: Any = None,
    找书候选: dict[str, Any] | None = None,
):
    try:
        解析来源 = str(来源 or "").strip()
        if not 解析来源:
            yield "没有识别到番茄小说链接"
            return

        书籍编号 = 提取番茄书籍编号(解析来源)
        短篇编号 = 提取番茄短篇编号(解析来源)
        if not 书籍编号 and not 短篇编号 and 番茄长读短链正则.search(解析来源):
            解析来源 = await 展开番茄短链(解析来源)
            书籍编号 = 提取番茄书籍编号(解析来源)
            短篇编号 = 提取番茄短篇编号(解析来源)
        if not 书籍编号 and not 短篇编号:
            yield "没有识别到番茄小说链接"
            return

        async with 创建番茄正文HTTP客户端(番茄正文最大动态并发数) as HTTP客户端:
            if 短篇编号:
                准备结果 = await 异步准备番茄短篇下载数据(
                    HTTP客户端, 解析来源, 短篇编号
                )
            else:
                准备结果 = await 异步准备番茄下载数据(
                    HTTP客户端, 书籍编号, 找书候选
                )
            书籍编号 = str(准备结果.get("book_id") or 书籍编号 or "")
            书籍信息 = 准备结果.get("book_info") or 默认番茄书籍信息(书籍编号)
            目录 = 准备结果.get("chapters") or []
            if not 目录:
                logger.warning(f"番茄小说下载失败：书籍编号={书籍编号}, 错误=没有获取到章节目录")
                yield 番茄下载失败提示
                return

            logger.info(
                f"番茄小说开始下载：书籍编号={书籍编号}, 书名={书籍信息.get('title')}, "
                f"作者={书籍信息.get('author')}, 章节数={len(目录)}"
            )
            yield 格式化番茄下载提示(书籍信息, len(目录))

            章节结果列表 = await 异步下载番茄全部章节(书籍编号, 目录, HTTP客户端)
        成功章节列表 = [项目 for 项目 in 章节结果列表 if 项目.get("success")]
        if len(成功章节列表) < len(目录):
            logger.warning(
                f"番茄小说下载失败：书籍编号={书籍编号}, "
                f"成功={len(成功章节列表)}, 总数={len(目录)}, 错误=章节正文不完整"
            )
            yield 番茄下载失败提示
            return

        文件名, 文件内容 = 生成番茄小说文件内容(书籍编号, 书籍信息, 目录, 章节结果列表)
        logger.info(
            f"番茄小说章节下载完成：书籍编号={书籍编号}, 书名={书籍信息.get('title')}, "
            f"成功={len(成功章节列表)}, 总数={len(目录)}, 文件大小={len(文件内容)}"
        )
        发送结果 = await 准备发送番茄文本文件(
            event,
            文件名,
            文件内容,
            配置,
            书名=书籍信息.get("title"),
            作者=书籍信息.get("author"),
        )
        if 发送结果.get("sent"):
            启动番茄百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        降级文本 = str(发送结果.get("fallback_text") or "")
        if 降级文本:
            try:
                yield 降级文本
            finally:
                启动番茄百度后台上传并清理源文件(配置, 发送结果.get("source_cache_path"), 文件名)
            return
        if not 发送结果.get("sent"):
            yield 番茄文件发送失败提示
    except Exception as 异常:
        logger.warning(f"番茄小说下载失败：来源={限制番茄日志文本(来源, 300)}, 错误={异常}")
        yield 番茄下载失败提示

def 准备番茄下载数据同步(
    书籍编号: str,
    找书候选: dict[str, Any] | None = None,
) -> dict[str, Any]:
    原始书籍编号 = str(书籍编号 or "").strip()
    直接正文书籍元数据: dict[str, Any] = {}
    try:
        item_ids = resolve_directory(原始书籍编号)
    except Exception as 目录异常:
        try:
            真实书籍编号, 直接正文书籍元数据 = 解析番茄阅读章节书籍编号(原始书籍编号)
            if 真实书籍编号 == 原始书籍编号:
                raise RuntimeError("番茄阅读章节未映射到其他书籍编号")
            item_ids = resolve_directory(真实书籍编号)
            书籍编号 = 真实书籍编号
            logger.debug(
                f"番茄小说目录回退成功：来源=阅读正文, 章节数={len(item_ids)}"
            )
        except Exception as 直接正文异常:
            logger.warning(
                f"番茄畅听目录获取失败：书籍编号={原始书籍编号}, "
                f"错误={限制番茄日志文本(str(目录异常), 200)}, "
                f"直接正文错误={限制番茄日志文本(str(直接正文异常), 200)}"
            )
            raise 目录异常 from 直接正文异常

    详情: dict[str, Any] = {}
    try:
        详情 = book_detail(书籍编号)
    except Exception as 异常:
        logger.warning(f"番茄小说详情请求失败：书籍编号={书籍编号}, 错误={异常}")
    if not 详情 and 直接正文书籍元数据:
        详情 = 直接正文书籍元数据

    目录元数据 = 读取番茄目录元数据(书籍编号, item_ids)
    目录 = [
        {"id": str(item_id), "title": 获取番茄目录标题(目录元数据.get(str(item_id)) or {}, 序号), "index": 序号}
        for 序号, item_id in enumerate(item_ids, start=1)
        if str(item_id or "").strip()
    ]
    书籍信息 = 规范化番茄书籍信息(书籍编号, 详情, len(目录))
    候选信息 = 找书候选 if isinstance(找书候选, dict) else {}
    详情字数 = 提取有效番茄字数(书籍信息.get("word_count"))
    候选字数 = 提取有效番茄字数(
        候选信息.get("word_count"),
        候选信息.get("word_number"),
        候选信息.get("words"),
    )
    if 详情字数 <= 0 and 候选字数 > 0:
        书籍信息["word_count"] = 格式化番茄字数(候选字数)
        详情字数 = 候选字数
    if 详情字数 <= 0:
        精确字数 = 获取番茄同书精确字数(书籍编号, 详情, len(目录))
        if 精确字数 > 0:
            书籍信息["word_count"] = 格式化番茄字数(精确字数)
    return {"book_id": 书籍编号, "book_info": 书籍信息, "chapters": 目录}


def 准备番茄短篇下载数据同步(来源: str, 短篇编号: str) -> dict[str, Any]:
    """读取短篇分享详情，并将关联章节交给统一正文下载链路。"""
    链接参数 = urllib.parse.parse_qs(urllib.parse.urlsplit(str(来源 or "")).query)

    def 读取参数(名称: str, 默认值: str = "") -> str:
        值列表 = 链接参数.get(名称) or []
        return str(值列表[0] if 值列表 else 默认值).strip()

    请求参数 = {
        "post_id": str(短篇编号),
        "forum_book_id": 读取参数("forum_book_id", "0"),
        "service_id": 读取参数("service_id", "0"),
        "source_type": 读取参数("source_type", "28"),
        "aid": 读取参数("aid", "1967"),
        "update_version_code": 读取参数("update_version_code", "72732"),
    }
    请求头 = {
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json, text/plain, */*",
    }
    分享码 = 读取参数("share_code")
    if 分享码:
        请求头["share-code"] = 分享码
    阅读进度 = 读取参数("percent")
    if 阅读进度:
        请求头["percent"] = 阅读进度

    响应 = http_json(
        f"{番茄短篇详情地址}?{urllib.parse.urlencode(请求参数)}",
        headers=请求头,
        timeout=30,
        retries=2,
    )
    详情 = (响应 or {}).get("data") if isinstance(响应, dict) else None
    if not isinstance(详情, dict) or (响应 or {}).get("code") != 0:
        raise RuntimeError("番茄短篇详情接口未返回可下载内容")

    书籍编号 = str(详情.get("relate_book_id") or "").strip()
    章节编号 = str(详情.get("relate_item_id") or "").strip()
    if not re.fullmatch(r"\d{8,}", 书籍编号) or not re.fullmatch(r"\d{8,}", 章节编号):
        raise RuntimeError("番茄短篇详情未返回关联章节")

    作者信息 = 详情.get("user_info") if isinstance(详情.get("user_info"), dict) else {}
    标题 = 清理番茄网页文本(详情.get("title") or f"番茄短篇{短篇编号}")
    书籍信息 = {
        "book_id": 书籍编号,
        "title": 标题,
        "author": 清理番茄网页文本(作者信息.get("user_name") or "未知"),
        "status": "完结",
        "word_count": 格式化番茄字数(详情.get("total_word_num") or 详情.get("truncate_word_num") or ""),
        "chapter_count": 1,
        "intro": "",
    }
    return {
        "book_id": 书籍编号,
        "book_info": 书籍信息,
        "chapters": [{"id": 章节编号, "title": 标题 or "第1章", "index": 1}],
    }


async def 异步准备番茄下载数据(
    client: Any,
    书籍编号: str,
    找书候选: dict[str, Any] | None = None,
) -> dict[str, Any]:
    original_id = str(书籍编号 or "").strip()
    reader_metadata: dict[str, Any] = {}
    try:
        item_ids = await 异步解析番茄目录(client, original_id)
    except Exception as directory_error:
        try:
            real_book_id, reader_metadata = await 异步解析番茄阅读章节书籍编号(client, original_id)
            if real_book_id == original_id:
                raise RuntimeError("番茄阅读章节未映射到其他书籍编号")
            item_ids = await 异步解析番茄目录(client, real_book_id)
            书籍编号 = real_book_id
            logger.debug(f"番茄小说目录回退成功：来源=阅读正文, 章节数={len(item_ids)}")
        except Exception as reader_error:
            logger.warning(
                f"番茄畅听目录获取失败：书籍编号={original_id}, "
                f"错误={type(directory_error).__name__}, 直接正文错误={type(reader_error).__name__}"
            )
            raise directory_error from reader_error

    detail: dict[str, Any] = {}
    try:
        detail = await 异步获取番茄书籍详情(client, str(书籍编号))
    except Exception as exc:
        logger.warning(f"番茄小说详情请求失败：书籍编号={书籍编号}, 错误={type(exc).__name__}")
    if not detail and reader_metadata:
        detail = reader_metadata
    if not detail or not (detail.get("book_name") or detail.get("title")) or not (
        detail.get("author") or detail.get("author_name")
    ):
        logger.warning(f"番茄小说详情不完整：书籍编号={书籍编号}")
        raise RuntimeError("番茄小说详情不完整")

    metadata = await 异步读取番茄目录元数据(client, str(书籍编号), item_ids)
    catalog = [
        {
            "id": str(item_id),
            "title": 获取番茄目录标题(metadata.get(str(item_id)) or {}, index),
            "index": index,
        }
        for index, item_id in enumerate(item_ids, start=1)
        if str(item_id or "").strip()
    ]
    book_info = 规范化番茄书籍信息(str(书籍编号), detail, len(catalog))
    candidate = 找书候选 if isinstance(找书候选, dict) else {}
    detail_words = 提取有效番茄字数(book_info.get("word_count"))
    candidate_words = 提取有效番茄字数(
        candidate.get("word_count"), candidate.get("word_number"), candidate.get("words")
    )
    if detail_words <= 0 and candidate_words > 0:
        book_info["word_count"] = 格式化番茄字数(candidate_words)
        detail_words = candidate_words
    if detail_words <= 0:
        exact_words = await 异步获取番茄同书精确字数(
            client, str(书籍编号), detail, len(catalog)
        )
        if exact_words > 0:
            book_info["word_count"] = 格式化番茄字数(exact_words)
    return {"book_id": str(书籍编号), "book_info": book_info, "chapters": catalog}


async def 异步准备番茄短篇下载数据(
    client: Any,
    来源: str,
    短篇编号: str,
) -> dict[str, Any]:
    link_params = urllib.parse.parse_qs(urllib.parse.urlsplit(str(来源 or "")).query)

    def 读取参数(name: str, default: str = "") -> str:
        values = link_params.get(name) or []
        return str(values[0] if values else default).strip()

    params = {
        "post_id": str(短篇编号),
        "forum_book_id": 读取参数("forum_book_id", "0"),
        "service_id": 读取参数("service_id", "0"),
        "source_type": 读取参数("source_type", "28"),
        "aid": 读取参数("aid", "1967"),
        "update_version_code": 读取参数("update_version_code", "72732"),
    }
    headers = {"User-Agent": DEFAULT_UA, "Accept": "application/json, text/plain, */*"}
    share_code = 读取参数("share_code")
    if share_code:
        headers["share-code"] = share_code
    percent = 读取参数("percent")
    if percent:
        headers["percent"] = percent
    response = await 异步番茄JSON请求(
        client,
        f"{番茄短篇详情地址}?{urllib.parse.urlencode(params)}",
        headers=headers,
        retries=2,
    )
    detail = response.get("data") if isinstance(response, dict) else None
    if not isinstance(detail, dict) or response.get("code") != 0:
        raise RuntimeError("番茄短篇详情接口未返回可下载内容")
    book_id = str(detail.get("relate_book_id") or "").strip()
    chapter_id = str(detail.get("relate_item_id") or "").strip()
    if not re.fullmatch(r"\d{8,}", book_id) or not re.fullmatch(r"\d{8,}", chapter_id):
        raise RuntimeError("番茄短篇详情未返回关联章节")
    author_info = detail.get("user_info") if isinstance(detail.get("user_info"), dict) else {}
    title = 清理番茄网页文本(detail.get("title") or f"番茄短篇{短篇编号}")
    return {
        "book_id": book_id,
        "book_info": {
            "book_id": book_id,
            "title": title,
            "author": 清理番茄网页文本(author_info.get("user_name") or "未知"),
            "status": "完结",
            "word_count": 格式化番茄字数(detail.get("total_word_num") or detail.get("truncate_word_num") or ""),
            "chapter_count": 1,
            "intro": "",
        },
        "chapters": [{"id": chapter_id, "title": title or "第1章", "index": 1}],
    }

async def 异步下载番茄全部章节(
    书籍编号: str,
    目录: list[dict[str, Any]],
    HTTP客户端: Any = None,
) -> list[dict[str, Any]]:
    item_ids = [str(章节.get("id") or "").strip() for 章节 in 目录 if str(章节.get("id") or "").strip()]
    if not item_ids:
        return []
    总数 = len(item_ids)
    批量章节数, 动态并发数 = 计算番茄正文批量参数(总数)
    任务列表: list[tuple[int, int, str, list[str], str]] = []
    起始序号 = 1
    for 批次序号, 批次 in enumerate(batches(item_ids, 批量章节数), start=1):
        任务列表.append((批次序号, 起始序号, 书籍编号, list(批次), "auto"))
        起始序号 += len(批次)

    已完成 = 0
    下次进度 = max(1, 总数 // 番茄进度日志分段数)
    结果按序号: dict[int, dict[str, Any]] = {}
    logger.info(
        f"番茄小说章节进度：书籍编号={书籍编号}, 进度=0/{总数}, "
        f"百分比=0%, 批次数={len(任务列表)}, 批量章节数={批量章节数}, "
        f"并发数={动态并发数}, HTTP会话复用={'开启' if FULL_MGET_HTTP_REUSE else 'off'}"
    )

    请求信号量 = asyncio.Semaphore(max(1, 动态并发数))
    解密信号量 = asyncio.Semaphore(max(1, min(64, (os.cpu_count() or 4) * 2)))

    async def 请求批次(任务: tuple[int, int, str, list[str], str]) -> dict[str, Any]:
        批次序号, 起始序号, 请求书籍编号, 批次章节, 签名模式 = 任务
        started_at = time.perf_counter()
        results = await 异步下载番茄正文批次(
            HTTP客户端,
            请求信号量,
            请求书籍编号,
            批次章节,
            allow_split=True,
            sign_mode=签名模式,
        )
        ok = sum(1 for _item_id, info, _x, error in results if info and not error)
        fatal_error = next(
            (error for _item_id, _info, _x, error in results if isinstance(error, FullMgetBusinessError)),
            None,
        )
        return {
            "batch": 批次序号,
            "start": 起始序号,
            "end": 起始序号 + len(批次章节) - 1,
            "count": len(批次章节),
            "ok": ok,
            "fatal_error": str(fatal_error) if fatal_error else "",
            "elapsed": time.perf_counter() - started_at,
            "results": results,
        }

    async def 解密章节(参数: tuple[int, str, dict[str, Any], int]) -> dict[str, Any]:
        async with 解密信号量:
            return await asyncio.to_thread(decrypt_item_worker, 参数)

    async with AsyncExitStack() as stack:
        if HTTP客户端 is None:
            HTTP客户端 = await stack.enter_async_context(创建番茄正文HTTP客户端(动态并发数))
        for 任务协程 in asyncio.as_completed([请求批次(任务) for 任务 in 任务列表]):
            批次结果 = await 任务协程
            批次起始 = int(批次结果.get("start") or 1)
            批次数量 = int(批次结果.get("count") or 0)
            批次成功 = 0
            if 批次结果.get("fatal_error"):
                logger.warning(
                    f"番茄小说正文业务错误，停止拆分重试：书籍编号={书籍编号}, "
                    f"范围={批次起始}-{批次结果.get('end')}, 错误={限制番茄日志文本(str(批次结果.get('fatal_error')), 200)}"
                )
            原始结果 = list(批次结果.get("results") or [])
            解密输入: list[tuple[int, str, dict[str, Any], int] | None] = []
            for 偏移, (item_id, 正文信息, 解密参数, 错误) in enumerate(原始结果):
                序号 = 批次起始 + 偏移
                if 错误 or not 正文信息:
                    解密输入.append(None)
                    continue
                解密输入.append((序号, item_id, 正文信息, 解密参数 if 解密参数 is not None else 0))
            解密结果列表 = await asyncio.gather(*(
                解密章节(参数) for 参数 in 解密输入 if 参数 is not None
            ))
            解密结果迭代器 = iter(解密结果列表)
            for 偏移, (item_id, 正文信息, _解密参数, 错误) in enumerate(原始结果):
                序号 = 批次起始 + 偏移
                原章节 = 目录[序号 - 1] if 0 <= 序号 - 1 < len(目录) else {"title": f"第{序号}章"}
                if 错误 or not 正文信息:
                    结果按序号[序号] = {
                        "index": 序号,
                        "id": item_id,
                        "title": 原章节.get("title") or f"第{序号}章",
                        "content": "",
                        "success": False,
                        "error": str(错误 or "no item_info"),
                    }
                    continue
                解密结果 = next(解密结果迭代器)
                解密标题 = 清理番茄网页文本(解密结果.get("title") or "")
                原目录标题 = 清理番茄网页文本(原章节.get("title") or "")
                if 解密标题 == f"第{序号}章" and 原目录标题 and 原目录标题 != 解密标题:
                    标题 = 原目录标题
                else:
                    标题 = 清理番茄网页文本(解密标题 or 原目录标题 or f"第{序号}章")
                正文 = 规范化番茄正文(解密结果.get("text") or "")
                成功 = (not 解密结果.get("error")) and 番茄章节信息返回成功(正文信息)
                if 成功:
                    批次成功 += 1
                    if not 正文.strip():
                        logger.debug(
                            f"番茄小说章节正文为空但接口返回成功，保留章节标题：书籍编号={书籍编号}, "
                            f"章节={序号}, 章节编号={item_id}, 书名={限制番茄日志文本(标题, 80)}"
                        )
                结果按序号[序号] = {
                    "index": 序号,
                    "id": item_id,
                    "title": 标题,
                    "content": 正文,
                    "success": 成功,
                    "error": 解密结果.get("error") or "",
                }
            已完成 += 批次数量
            if 已完成 >= 下次进度 or 已完成 >= 总数:
                百分比 = int(min(100, 已完成 * 100 / max(1, 总数)))
                当前成功 = sum(1 for 项目 in 结果按序号.values() if 项目.get("success"))
                logger.info(
                    f"番茄小说章节进度：书籍编号={书籍编号}, 进度={min(已完成, 总数)}/{总数}, "
                    f"百分比={百分比}%, 成功={当前成功}, 本批成功={批次成功}/{批次数量}"
                )
                下次进度 += max(1, 总数 // 番茄进度日志分段数)

    章节结果列表: list[dict[str, Any]] = []
    for 序号, 章节 in enumerate(目录, start=1):
        结果 = 结果按序号.get(序号)
        if 结果 is None:
            结果 = {
                "index": 序号,
                "id": 章节.get("id"),
                "title": 章节.get("title") or f"第{序号}章",
                "content": "",
                "success": False,
                "error": "missing result",
            }
        章节结果列表.append(结果)
    return 章节结果列表

def 提取有效番茄字数(*候选值: Any) -> int:
    """只接受接口给出的原始正整数总字数，展示用的“万字”值不作为精确数据。"""
    for 候选 in 候选值:
        if isinstance(候选, bool):
            continue
        if isinstance(候选, int) and 候选 > 0:
            return 候选
        if isinstance(候选, float) and 候选.is_integer() and 候选 > 0:
            return int(候选)
        文本 = str(候选 or "").strip().replace(",", "").replace(" ", "")
        if not 文本:
            continue
        匹配 = re.fullmatch(r"(\d+)(?:字)?", 文本)
        if not 匹配:
            continue
        try:
            字数 = int(匹配.group(1))
        except (TypeError, ValueError):
            continue
        if 字数 > 0:
            return 字数
    return 0


def 规范化番茄书籍信息(书籍编号: str, 详情: dict[str, Any], 章节数: int) -> dict[str, Any]:
    详情 = 详情 if isinstance(详情, dict) else {}
    字数 = 提取有效番茄字数(
        详情.get("word_number"),
        详情.get("word_count"),
        详情.get("words"),
    )
    return {
        "book_id": 书籍编号,
        "title": 清理番茄网页文本(详情.get("book_name") or 详情.get("title") or f"番茄小说{书籍编号}"),
        "author": 清理番茄网页文本(详情.get("author") or 详情.get("author_name") or "未知"),
        "status": 获取番茄状态文本(详情),
        "word_count": 格式化番茄字数(字数),
        "chapter_count": 安全番茄整数(详情.get("chapter_number") or 详情.get("serial_count") or 章节数, 章节数),
        "intro": 清理番茄网页文本(详情.get("abstract") or 详情.get("sub_abstract") or 详情.get("description") or ""),
    }

def 默认番茄书籍信息(书籍编号: str) -> dict[str, Any]:
    return {
        "book_id": 书籍编号,
        "title": f"番茄小说{书籍编号}",
        "author": "未知",
        "status": "连载",
        "word_count": "未知",
        "chapter_count": 0,
        "intro": "",
    }

def 获取番茄状态文本(详情: dict[str, Any]) -> str:
    文本 = " ".join(str(详情.get(字段) or "") for 字段 in ("status", "status_text", "book_status_text", "creation_status_text", "last_chapter_title"))
    if any(关键词 in 文本 for 关键词 in ("完结", "已完结", "完本", "终章", "大结局", "finished", "completed")):
        return "完结"
    if any(关键词 in 文本 for 关键词 in ("连载", "更新中", "ongoing", "serial")):
        return "连载"
    创作状态 = str(详情.get("creation_status") or 详情.get("status") or "").strip().lower()
    if 创作状态 in ("0", "2"):
        return "完结"
    if 创作状态 in ("1", "3", "4"):
        return "连载"
    书籍状态 = str(详情.get("book_status") or "").strip().lower()
    if 书籍状态 in ("1", "2"):
        return "完结"
    if 书籍状态 in ("0", "3", "4"):
        return "连载"
    return "连载"

def 格式化番茄下载提示(书籍信息: dict[str, Any], 章节数: int) -> str:
    return "\n".join([
        f"书名：{书籍信息.get('title') or '未知'}",
        f"作者：{书籍信息.get('author') or '未知'}",
        f"状态：{书籍信息.get('status') or '连载'}",
        f"章节：{章节数} 章",
        f"字数：{书籍信息.get('word_count') or '未知'}",
        "",
        "正在下载中请稍等.....",
    ])

def 生成番茄小说文件内容(
    书籍编号: str,
    书籍信息: dict[str, Any],
    目录: list[dict[str, Any]],
    章节结果列表: list[dict[str, Any]],
) -> tuple[str, bytes]:
    文件名 = 生成番茄小说文件名(书籍编号, 书籍信息)
    内容列表 = [
        番茄文件声明,
        "",
        f"名称：{书籍信息.get('title') or f'番茄小说{书籍编号}'}",
        f"作者：{书籍信息.get('author') or '未知'}",
        f"状态：{书籍信息.get('status') or '连载'}",
        f"字数：{书籍信息.get('word_count') or '未知'}",
        f"书籍ID：{书籍编号}",
        f"章节数：{len(目录)}",
        "",
    ]
    简介 = str(书籍信息.get("intro") or "").strip()
    if 简介:
        内容列表.extend(["简介：", 简介, ""])
    for 章节 in 章节结果列表:
        if not 章节.get("success"):
            continue
        标题 = str(章节.get("title") or f"第{章节.get('index')}章")
        正文 = 去除章节正文重复标题(标题, 章节.get("content"))
        内容列表.append(标题)
        内容列表.append("")
        if 正文:
            内容列表.append(正文)
        内容列表.append("")
    return 文件名, 编码番茄TXT内容(内容列表)

def 生成番茄小说文件名(书籍编号: str, 书籍信息: dict[str, Any]) -> str:
    状态 = str(书籍信息.get("status") or "连载")
    书名 = 清理番茄文件名(书籍信息.get("title") or f"番茄小说{书籍编号}")
    作者 = 清理番茄文件名(书籍信息.get("author") or "未知")
    return f"[{状态}]书名：{书名} 作者：{作者}.txt"

def 编码番茄TXT内容(内容列表: list[str]) -> bytes:
    文本 = "\n".join(str(行) for 行 in 内容列表)
    文本 = 文本.replace("\r\n", "\n").replace("\r", "\n")
    return 文本.replace("\n", "\r\n").encode("utf-8")

async def 准备发送番茄文本文件(
    event: Any,
    文件名: str,
    文件内容: bytes,
    配置: Any = None,
    *,
    书名: Any = "",
    作者: Any = "",
) -> dict[str, Any]:
    logger.debug(f"番茄小说准备上传：文件={文件名}, 大小={len(文件内容)}")
    缓存路径 = 写入番茄下载缓存文件(文件名, 文件内容)
    logger.debug(f"番茄小说写入下载缓存：文件={缓存路径}, 大小={len(文件内容)}")
    if 小说网盘 is None:
        删除番茄缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": "小说网盘模块未加载"}
    try:
        网盘结果 = await 小说网盘.上传小说并获取分享链接(配置, 缓存路径, 文件名)
        网盘名称 = str(网盘结果.get("provider") or "小说网盘")
        if not 网盘结果.get("success"):
            logger.warning(f"番茄小说主网盘上传失败：网盘={网盘名称}, 文件={文件名}, 错误={网盘结果.get('error')}")
            删除番茄缓存文件(缓存路径)
            return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(网盘结果.get("error") or "小说网盘未启用")}
        完成结果 = await 小说网盘.发送小说下载完成链接(event, 书名, 作者, str(网盘结果.get("share_url") or ""))
        if 完成结果.get("sent"):
            logger.debug(f"番茄小说主网盘上传并发送完成按钮成功：网盘={网盘名称}, 文件={文件名}")
            return {"sent": True, "fallback_text": "", "source_cache_path": 缓存路径, "error": ""}
        降级文本 = str(完成结果.get("fallback_text") or "")
        if 降级文本:
            return {"sent": False, "fallback_text": 降级文本, "source_cache_path": 缓存路径, "error": str(完成结果.get("error") or "")}
        删除番茄缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(完成结果.get("error") or "完成按钮发送失败")}
    except Exception as 异常:
        logger.warning(f"番茄小说主网盘上传或完成消息发送失败：文件={文件名}, 错误={异常}")
        删除番茄缓存文件(缓存路径)
        return {"sent": False, "fallback_text": "", "source_cache_path": None, "error": str(异常)}

def 启动番茄百度后台上传并清理源文件(配置: Any, 源缓存路径: Any, 文件名: str, 发送缓存路径: Any = None) -> None:
    if not 源缓存路径:
        return

    async def 执行上传并清理() -> None:
        try:
            if 百度网盘 is not None:
                百度结果 = await 百度网盘.后台上传小说文件(配置, 源缓存路径, 文件名)
                if 百度结果.get("success"):
                    logger.debug(f"番茄小说百度网盘后台上传成功：文件={文件名}, 文件编号={百度结果.get('file_id')}")
                elif 百度结果.get("skipped"):
                    logger.debug(f"番茄小说百度网盘后台上传按状态规则跳过：文件={文件名}")
                elif 百度结果.get("enabled"):
                    logger.warning(f"番茄小说百度网盘后台上传失败，不影响QQ发送：文件={文件名}, 错误={百度结果.get('error')}")
        except Exception as 异常:
            logger.warning(f"番茄小说百度网盘后台上传异常，不影响QQ发送：文件={文件名}, 错误={异常}")
        finally:
            if str(源缓存路径) != str(发送缓存路径 or ""):
                删除番茄缓存文件(源缓存路径)

    try:
        asyncio.create_task(执行上传并清理())
    except RuntimeError:
        if str(源缓存路径) != str(发送缓存路径 or ""):
            删除番茄缓存文件(源缓存路径)

def 删除番茄缓存文件(缓存路径: Any) -> None:
    if not 缓存路径:
        return
    if not 小说缓存工具.删除下载缓存文件(缓存路径):
        logger.debug(f"番茄小说下载缓存仍在等待续传：文件={缓存路径}")
        return
    try:
        logger.debug(f"番茄小说下载缓存文件已删除：文件={缓存路径}")
    except Exception as 异常:
        logger.warning(f"番茄小说下载缓存文件删除失败：文件={缓存路径}, 错误={异常}")

def 写入番茄下载缓存文件(文件名: str, 文件内容: bytes) -> Path:
    番茄下载缓存目录.mkdir(parents=True, exist_ok=True)
    缓存路径 = 生成不冲突番茄缓存路径(文件名)
    缓存路径.write_bytes(文件内容)
    小说缓存工具.标记下载缓存正在使用(缓存路径)
    return 缓存路径

def 生成不冲突番茄缓存路径(文件名: str) -> Path:
    安全文件名 = Path(清理番茄文件名(文件名)).name or "番茄小说.txt"
    if not 安全文件名.lower().endswith(".txt"):
        安全文件名 = f"{安全文件名}.txt"
    缓存路径 = 番茄下载缓存目录 / 安全文件名
    if not 缓存路径.exists():
        return 缓存路径
    后缀 = 缓存路径.suffix
    主名 = 缓存路径.stem
    for 序号 in range(1, 1000):
        候选路径 = 番茄下载缓存目录 / f"{主名}_{序号}{后缀}"
        if not 候选路径.exists():
            return 候选路径
    raise RuntimeError("下载缓存目录中同名文件过多")

async def 展开番茄短链(来源: str) -> str:
    文本 = str(来源 or "").strip()
    if aiohttp is None:
        return 文本
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers={"User-Agent": DEFAULT_UA}) as session:
            async with session.get(文本, allow_redirects=True) as 响应:
                最终链接 = str(响应.url)
                if 提取番茄书籍编号(最终链接) or 提取番茄短篇编号(最终链接):
                    return 最终链接
                页面文本 = await 响应.text(errors="ignore")
                页面链接 = 提取番茄链接(页面文本)
                if 页面链接:
                    return 页面链接
    except Exception as 异常:
        logger.warning(f"番茄短链解析失败：来源={限制番茄日志文本(文本, 200)}, 错误={异常}")
    return 文本

def 提取直接番茄链接参数(命令文本: str) -> str | None:
    文本 = str(命令文本 or "").strip()
    if not 文本:
        return None
    if re.fullmatch(r"\d{15,25}", 文本):
        return 文本
    return 提取番茄链接(文本) or None

def 提取事件番茄链接(event: Any) -> str | None:
    消息对象 = getattr(event, "message_obj", None)
    for 对象 in (event, 消息对象):
        if 对象 is None:
            continue
        for 字段名 in ("message_str", "raw_message", "message"):
            链接 = 提取番茄链接(读取番茄字段(对象, 字段名))
            if 链接:
                return 链接
    return None

def 提取番茄链接(值: Any) -> str:
    if 值 is None:
        return ""
    if isinstance(值, (list, tuple, set)):
        for 子值 in 值:
            链接 = 提取番茄链接(子值)
            if 链接:
                return 链接
        return ""
    if isinstance(值, dict):
        for 子值 in 值.values():
            链接 = 提取番茄链接(子值)
            if 链接:
                return 链接
        return ""
    文本 = str(值)
    for 匹配 in 番茄链接正则.finditer(文本):
        链接 = 匹配.group(0).rstrip("`，。；;、")
        if 番茄域名正则.search(链接) and (
            提取番茄书籍编号(链接) or 提取番茄短篇编号(链接) or 番茄长读短链正则.search(链接)
        ):
            return 链接
    if 番茄域名正则.search(文本) and (提取番茄书籍编号(文本) or 提取番茄短篇编号(文本)):
        return 文本
    if re.fullmatch(r"\d{15,25}", 文本.strip()):
        return 文本.strip()
    return ""

def 提取番茄书籍编号(文本: Any) -> str:
    原文 = str(文本 or "").strip()
    if not 原文:
        return ""
    try:
        return resolve_book_id(原文)
    except Exception:
        pass
    for 规则 in (
        r"(?:book[_-]?id|bookId|bookid)=([0-9]{8,})",
        r"fanqienovel\.com/(?:page|book)/([0-9]{8,})",
        r"(?:/|%2[fF])(?:page|book)(?:/|%2[fF])([0-9]{8,})",
    ):
        匹配 = re.search(规则, 原文, re.I)
        if 匹配:
            return 匹配.group(1)
    编号列表 = re.findall(r"\d{16,25}", 原文)
    去重列表: list[str] = []
    for 编号 in 编号列表:
        if 编号 not in 去重列表:
            去重列表.append(编号)
    return 去重列表[0] if len(去重列表) == 1 else ""


def 提取番茄短篇编号(文本: Any) -> str:
    原文 = str(文本 or "").strip()
    if not 原文:
        return ""
    匹配 = re.search(r"(?:post[_-]?id|postId)=([0-9]{8,})", 原文, re.I)
    return 匹配.group(1) if 匹配 else ""

def 规范化番茄正文(正文: Any) -> str:
    文本 = str(正文 or "").replace("\r\n", "\n").replace("\r", "\n")
    文本 = re.sub(r"\n{3,}", "\n\n", 文本).strip()
    return 文本

def 格式化番茄字数(值: Any) -> str:
    字数 = 提取有效番茄字数(值)
    if 字数 <= 0:
        return "未知"
    if 字数 >= 10000:
        万字 = f"{字数 / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{万字}万字"
    return f"{字数}字"

def 清理番茄网页文本(文本: Any) -> str:
    文本 = re.sub(r"<[^>]+>", "", str(文本 or ""))
    return html.unescape(文本).strip()

def 清理番茄文件名(文件名: Any) -> str:
    文本 = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(文件名 or "")).strip(" .")
    return 文本[:80] or "番茄小说"

def 安全番茄整数(值: Any, 默认值: int = 0) -> int:
    try:
        return int(float(str(值).strip()))
    except Exception:
        return 默认值

def 限制番茄日志文本(值: Any, 最大长度: int = 300) -> str:
    文本 = str(值 or "")
    return 文本 if len(文本) <= 最大长度 else 文本[:最大长度] + "..."

def 读取番茄字段(对象: Any, 字段名: str) -> Any:
    if 对象 is None:
        return None
    if isinstance(对象, dict):
        return 对象.get(字段名)
    return getattr(对象, 字段名, None)
