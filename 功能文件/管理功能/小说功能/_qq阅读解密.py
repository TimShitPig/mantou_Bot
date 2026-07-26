# -*- coding: utf-8 -*-
from __future__ import annotations
import base64, gzip, hashlib, zlib
from typing import Callable, Optional
from Crypto.Cipher import AES, DES
from Crypto.Hash import MD2, MD4, MD5
from Crypto.Util import Counter
from Crypto.Util.Padding import unpad

# === decrypt ===
"""Pure-Python QQRead chapter decrypt (libfock algorithm recovery).

Wire format:
  enc = header_cipher(256) || body_cipher
  body = header_plain[128:256] || enc[256:]

Key schedule:
  knva = AES-128-CBC(key=c9ajudte0zb21ksg, iv=58jb6v2lzcspwymg).decrypt(embedded_ct)
  master = SHA256(fuid || knva)
  header / keypool = AES-256-CBC(master, iv=master[:16])
  token_index = int(mode_digit_string) % len(tokens)
  content_key = SHA256(token_ascii || fuid || stt)

Mode id = int(header mode string first 8 decimal digits). Content chains:

  21123123 AES-CBC -> AES-CBC
  21132184 DES-CBC -> AES-CBC
  29344484 AES-CTR -> DES-CBC
  29859828 AES-CBC -> AES-CTR
  31344423 DES-CBC -> AES-CTR
  31932881 AES-CBC -> DES-CBC
  34232881 AES-CTR -> AES-CTR
  34941028 DES-CBC -> DES-CBC
  94859123 AES-CTR -> AES-CBC

AES-CTR: nonce=content_key[:12], BE32 counter starts at 2 (GCM data style).

fock_sn (request signing helper, not content AES):
  table = [MD2, MD4, MD5]
  a = table[len % 3](data)           # 16B
  b = table[(len >> 8) % 3](a)       # 16B
  c = table[(len >> 8) % 3](b)       # 16B
  return c.hex()                     # 32 lowercase hex chars
"""



# knva is NOT plaintext in libfock.so; real_dec builds:
#   master_material = fuid || AES128-CBC_decrypt(KNVA_CT)
# Embedded pool at runtime get_master (0x1200ca48):
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
