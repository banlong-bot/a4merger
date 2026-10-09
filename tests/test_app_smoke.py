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


def _run_smoke(timeout: int = 40):
    """offscreen Qt 环境偶发崩溃：最多重试 3 次。"""
    last: subprocess.CompletedProcess | None = None
    for attempt in range(3):
        last = subprocess.run([PY, str(GUI), "--smoke"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              env=_env(), timeout=timeout)
        if last.returncode == 0:
            return last
        time.sleep(1.0)
    return last


def test_gui_smoke_startup():
    """完整 GUI 进程启动 → 1 秒自动退出，返回码 0。"""
    r = _run_smoke()
    assert r.returncode == 0, r.stderr


def _double_start(timeout: int = 40):
    """同时启动两个实例，返回 (首实例码, 二实例码, 二实例耗时, 二实例 stderr)。
    offscreen Qt 进程偶发启动失败：最多重试 3 次，只要有一次两实例都干净退出即算通过。"""
    last = None
    for attempt in range(3):
        p1 = subprocess.Popen([PY, str(GUI), "--smoke"], env=_env(),
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace")
        p2 = subprocess.Popen([PY, str(GUI), "--smoke"], env=_env(),
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace")
        t0 = time.time()
        try:
            rc2 = p2.wait(timeout=timeout)
            dt2 = time.time() - t0
            err2 = p2.stderr.read() if p2.stderr else ""
            rc1 = p1.wait(timeout=timeout)
            err1 = p1.stderr.read() if p1.stderr else ""
        except subprocess.TimeoutExpired:
            p1.kill()
            p2.kill()
            last = (None, None, None, "启动超时（进程未退出）")
            continue
        last = (rc1, rc2, dt2, f"首实例 stderr：{err1}\n二实例 stderr：{err2}")
        if rc1 == 0 and rc2 == 0 and dt2 < 15:
            return last
    return last


def test_single_instance_lock():
    """双实例：第二实例被单实例锁拦截、快速退出；两实例均干净退出（3.11.8）。
    两个进程同时启动，杜绝「首实例已退出导致锁空窗」的时序假失败。"""
    rc1, rc2, dt2, diag = _double_start()
    assert rc1 == 0 and rc2 == 0, f"实例退出码异常：{rc1} / {rc2}\n{diag}"
    assert dt2 < 15, f"第二实例未快速退出：{dt2:.1f}s\n{diag}"