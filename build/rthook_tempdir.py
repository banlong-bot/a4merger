"""build/rthook_tempdir.py —— PyInstaller 运行时钩子：保证 onefile 解包有可写的临时目录。

背景（M5 实机排障）：onefile 版启动时要把内置文件解包到 `%TEMP%\_MEIxxxxxx`。
若 `%TEMP%` 不可写（企业策略把临时目录重定向到只读位置、受限/沙箱会话、
残留的畸形 TMP 变量等），引导器只会甩出一句英文：
    [PYI-xxxx:ERROR] Could not create temporary directory!
用户完全无从下手。

本钩子在**主程序 import 之前**执行，做两件事：
  1. 探测 TMP/TEMP 是否真的可写（建目录 + 写探针文件 + 删除）；
  2. 不可写就逐级退让到 `%LOCALAPPDATA%\\A4合并助手\\临时目录`、用户主目录，并把
     选中的目录写回 TMP/TEMP 环境变量（对应用自身与 WPS 转换子进程同样有效）。

在正常机器上（%TEMP% 可写）行为完全不变：仍用系统临时目录。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".a4_tmp_probe_{os.getpid()}"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _candidates() -> list[Path]:
    out: list[Path] = []
    for var in ("TEMP", "TMP"):
        value = os.environ.get(var)
        if value:
            out.append(Path(value))
    try:
        out.append(Path(tempfile.gettempdir()))
    except Exception:
        pass
    base = os.environ.get("LOCALAPPDATA")
    if base:
        out.append(Path(base) / "A4合并助手" / "临时目录")
    out.append(Path.home() / "A4合并助手临时目录")
    seen: list[Path] = []
    for p in out:
        if p not in seen:
            seen.append(p)
    return seen


def _ensure_writable_temp() -> None:
    candidates = _candidates()
    if candidates and _writable(candidates[0]):
        return                                     # 系统临时目录可用：保持原样
    for cand in candidates[1:]:
        if _writable(cand):
            os.environ["TMP"] = os.environ["TEMP"] = str(cand)
            print(f"[提示] 系统临时目录不可写，本次改用：{cand}", flush=True)
            return
    print("[警告] 找不到可写的临时目录，应用可能无法启动。"
          "请联系管理员检查 TEMP/TMP 环境变量。", flush=True)


try:
    _ensure_writable_temp()
except Exception:                                  # 钩子绝不阻断启动
    pass
