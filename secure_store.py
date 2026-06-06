"""
secure_store.py — 本地密文存储（Windows DPAPI）
当系统凭据管理器（keyring）不可用时，用 Windows 数据保护 API（DPAPI）
对 API Key 做按当前用户绑定的加密，替代明文落盘。
DPAPI 密文仅能被同一 Windows 用户解密，比明文 JSON 安全得多。

非 Windows 平台无 DPAPI：available() 返回 False，调用方应回退到明文并告警。
"""
from __future__ import annotations

import base64
import sys
from typing import Optional

from logger import get_logger

log = get_logger()

_ENTROPY = b"case-archiver::deepseek_api_key::v1"  # 附加熵，绑定用途


def available() -> bool:
    """当前平台是否支持 DPAPI（仅 Windows）。"""
    return sys.platform.startswith("win")


def _crypt(blob_in: bytes, *, protect: bool) -> Optional[bytes]:
    """调用 CryptProtectData / CryptUnprotectData。"""
    if not available():
        return None
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _to_blob(data: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    blob_in_s = _to_blob(blob_in)
    entropy_s = _to_blob(_ENTROPY)
    blob_out = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    # BOOL fn(pDataIn, szDescr, pEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
    ok = fn(
        ctypes.byref(blob_in_s),
        None,
        ctypes.byref(entropy_s),
        None,
        None,
        0,
        ctypes.byref(blob_out),
    )
    if not ok:
        return None
    try:
        out = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return out
    finally:
        kernel32.LocalFree(blob_out.pbData)


def encrypt(plaintext: str) -> Optional[str]:
    """加密明文，返回 base64 字符串；失败返回 None。"""
    if not plaintext:
        return None
    try:
        enc = _crypt(plaintext.encode("utf-8"), protect=True)
        if enc is None:
            return None
        return base64.b64encode(enc).decode("ascii")
    except Exception as e:  # noqa: BLE001
        log.warning("DPAPI 加密失败：%s", e)
        return None


def decrypt(token: str) -> Optional[str]:
    """解密 base64 密文，返回明文；失败返回 None。"""
    if not token:
        return None
    try:
        raw = base64.b64decode(token.encode("ascii"))
        dec = _crypt(raw, protect=False)
        if dec is None:
            return None
        return dec.decode("utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("DPAPI 解密失败：%s", e)
        return None
