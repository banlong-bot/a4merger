"""tests/conftest.py —— pytest 共享 fixture。"""
from __future__ import annotations

import os
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


@pytest.fixture(scope="session", autouse=True)
def _isolated_settings(tmp_path_factory):
    """把 GUI 设置重定向到本会话的临时 INI：既不读本机残留，也不写脏真实设置。

    背景（1.0.2 修复）：开发态 GUI 用例的 MainWindow 会读写
    `HKCU\\Software\\A4合并助手`。原来的做法是会话开始时 `winreg.DeleteKey` 清一次，
    但**该键一旦有子键（`window/geometry` 等，正常用过一次 GUI 就会有）就删不掉**，
    异常又被吞掉——于是真实使用留下的设置（如「输出模式＝B」「输出目录＝桌面某目录」）
    会串进测试，导致 test_gui_smoke/test_results_dialog 随机失败。
    现在统一走 app/settings.py 已支持的 `A4_SETTINGS_DIR`（INI 形式），
    与打包版验收（test_frozen_exe）同样的隔离方式；本机真实设置不再被测试读写或清除。
    """
    d = tmp_path_factory.mktemp("a4_settings")
    old = os.environ.get("A4_SETTINGS_DIR")
    os.environ["A4_SETTINGS_DIR"] = str(d)
    yield d
    if old is None:
        os.environ.pop("A4_SETTINGS_DIR", None)
    else:
        os.environ["A4_SETTINGS_DIR"] = old


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