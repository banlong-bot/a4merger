"""core/util.py —— 通用小工具（从原脚本迁移）。"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path


def natural_key(text: str):
    """自然排序键：文件名里的数字按数值大小比较（2 排在 10 前面）。"""
    parts = re.split(r"(\d+)", text)
    return [(0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts if p != ""]


def log(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def setup_console() -> None:
    """尽量让中文和符号在控制台里正常显示。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    import logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)


def decode_bytes(data: bytes) -> str:
    """Windows 下的命令行输出可能是 UTF-8 也可能是 GBK，尽力解码。"""
    for enc in ("utf-8", "gbk", "mbcs"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def find_powershell() -> str | None:
    for name in ("powershell", "powershell.exe", "pwsh", "pwsh.exe"):
        found = shutil.which(name)
        if found:
            return found
    fallback = Path(os.environ.get("SystemRoot", r"C:\Windows")) / \
        "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(fallback) if fallback.exists() else None