"""进程级冒烟：run_gui --smoke 可启动退出；单实例锁拦截第二实例（3.11.8）。"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
GUI = REPO / "run_gui.py"


def _env() -> dict:
    e = dict(os.environ)
    e["QT_QPA_PLATFORM"] = "offscreen"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def test_gui_smoke_startup():
    """完整 GUI 进程启动 → 1 秒自动退出，返回码 0。"""
    r = subprocess.run([PY, str(GUI), "--smoke"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env=_env(), timeout=40)
    assert r.returncode == 0, r.stderr


def test_single_instance_lock():
    """第二实例快速退出（不再重复弹窗/运行），首实例仍正常结束。"""
    p1 = subprocess.Popen([PY, str(GUI), "--smoke"], env=_env())
    time.sleep(0.6)                     # 等首实例 acquire 完成
    t0 = time.time()
    r2 = subprocess.run([PY, str(GUI), "--smoke"], capture_output=True,
                        text=True, encoding="utf-8", errors="replace",
                        env=_env(), timeout=30)
    dt = time.time() - t0
    assert r2.returncode == 0
    assert dt < 10, f"第二实例未快速退出：{dt:.1f}s"
    rc1 = p1.wait(timeout=30)
    assert rc1 == 0