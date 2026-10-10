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


@pytest.fixture(scope="session", autouse=True)
def _clean_qsettings():
    """测试会话开始前清掉本机 QSettings 残留（HKCU\\Software\\A4合并助手）。

    背景：GUI 测试运行时会保存/读取"真实注册表设置"（output_mode、output_dir、
    checked_targets 等）；前一次测试会话残留的脏值会让后来跑的用例
    （比如打包版冻结验收加载窗口时）用错输出目录/目标列表。
    打包版自动验收另有独立设置文件（A4_SETTINGS_DIR），这里兜底清掉开发态残留。
    """
    try:
        import winreg as _winreg
        key = r"Software\A4合并助手\A4合并助手"
        try:
            _winreg.DeleteKey(_winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass
    except Exception:
        pass
    yield


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