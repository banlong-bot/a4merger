"""core/dpapi.py —— Windows DPAPI 加密存储（计划 3.11.9）。

用 ctypes 直调 CryptProtectData/CryptUnprotectData（零依赖，不用 pywin32）：
本机本用户可解，拷贝到其它机器无效。
非 Windows / 调用失败时退化为 base64 明文（加 "*" 前缀标记），仅用于开发环境。
"""
from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _to_blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))


def _from_blob(blob: _DATA_BLOB) -> bytes:
    if blob.cbData == 0 or not blob.pbData:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


def dpapi_protect(plain: str) -> str:
    """加密并返回 hex；失败/非 Windows 退回 base64 明文（前缀 *）。"""
    data = plain.encode("utf-8")
    if os.name != "nt":
        return "*" + base64.b64encode(data).decode("ascii")
    try:
        crypt32 = ctypes.windll.crypt32
        inb = _to_blob(data)
        outb = _DATA_BLOB()
        if not crypt32.CryptProtectData(ctypes.byref(inb), None, None, None,
                                        None, 0, ctypes.byref(outb)):
            raise ctypes.WinError()
        try:
            return _from_blob(outb).hex()
        finally:
            ctypes.windll.kernel32.LocalFree(outb.pbData)
    except Exception:
        return "*" + base64.b64encode(data).decode("ascii")


def dpapi_unprotect(token: str) -> str:
    """解密 hex 密文；* 前缀为开发退化格式。"""
    if token.startswith("*"):
        try:
            return base64.b64decode(token[1:]).decode("utf-8")
        except Exception:
            return ""
    if os.name != "nt":
        return ""
    try:
        crypt32 = ctypes.windll.crypt32
        data = bytes.fromhex(token)
        inb = _to_blob(data)
        outb = _DATA_BLOB()
        if not crypt32.CryptUnprotectData(ctypes.byref(inb), None, None, None,
                                          None, 0, ctypes.byref(outb)):
            return ""
        try:
            return _from_blob(outb).decode("utf-8", errors="replace")
        finally:
            ctypes.windll.kernel32.LocalFree(outb.pbData)
    except Exception:
        return ""