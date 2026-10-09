"""DPAPI 加密存储单测（3.11.9）：往返一致；非 Windows 退化可用。"""
from __future__ import annotations

import os

import pytest

from core.dpapi import dpapi_protect, dpapi_unprotect


def test_roundtrip():
    for pwd in ("123456", "中文密码！@#", "a" * 64):
        token = dpapi_protect(pwd)
        assert token
        assert dpapi_unprotect(token) == pwd


def test_token_not_plaintext_on_windows():
    """Windows 下密文不应包含明文（非退化格式）。"""
    if os.name == "nt":
        token = dpapi_protect("secret123")
        assert not token.startswith("*")
        assert "secret123" not in token
    else:
        token = dpapi_protect("secret123")
        assert token.startswith("*")            # 非 Windows 退化


def test_garbage_token():
    assert dpapi_unprotect("not-a-hex!!") == ""
    assert dpapi_unprotect("*%%%bad") == ""