"""tests/conftest.py —— pytest 共享 fixture。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SAMPLES = REPO / "tests" / "samples"
LEGACY = REPO / "legacy" / "merge_to_a4_wps.py"
CLI = REPO / "cli.py"
PY = sys.executable


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(CLI), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          cwd=cwd, timeout=600)


def run_legacy(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(LEGACY), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=600)


@pytest.fixture()
def scratch(tmp_path: Path) -> Path:
    """一个干净的临时工作目录（测试结束后自动清理）。"""
    return tmp_path


@pytest.fixture()
def pure_pdf_copy(scratch: Path) -> Path:
    """pure_pdf 样例的独立副本（合并不污染样例库）。"""
    src = SAMPLES / "pure_pdf"
    dst = scratch / "pure_pdf"
    shutil.copytree(src, dst)
    return dst