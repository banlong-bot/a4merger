"""M2 GUI 骨架冒烟测试（offscreen 平台）与诊断包单测。"""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.diagnostics import build_diagnostic_zip, setup_file_logging
from app.ui_main import MainWindow
from core.types import MergeConfig

SAMPLES = Path(__file__).resolve().parent / "samples"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def win(qapp, tmp_path):
    w = MainWindow()
    w.lw_targets.blockSignals(True)
    yield w
    w.deleteLater()


def test_window_controls(win):
    """关键控件存在且初始状态正确。"""
    assert win.ed_root is not None
    assert win.ed_template.text() == "【合并】{folder}.pdf"
    assert win.ra_mode_a.isChecked()          # 默认模式A
    assert not win.ed_outdir.isEnabled()      # 模式A 输出目录禁用
    assert win.btn_start.isEnabled()
    assert win.cb_report.isChecked()


def test_template_validation(win):
    """模板实时校验：非法字符 → 红框 + 开始禁用；恢复后可用。"""
    win.ed_template.setText("A:B.pdf")
    assert not win.btn_start.isEnabled()
    assert win.ed_template.toolTip() != ""
    win.ed_template.setText("【合并】{folder}.pdf")
    assert win.btn_start.isEnabled()
    assert win.ed_template.toolTip() == ""


def test_output_mode_linkage(win):
    """输出模式联动：模式B 启用输出目录行。"""
    win.ra_mode_b.setChecked(True)
    assert win.ed_outdir.isEnabled()
    win.ra_mode_a.setChecked(True)
    assert not win.ed_outdir.isEnabled()


def test_targets_refresh(win):
    """根目录变化 → 目标列表刷新（pure_pdf 两个目标、默认全勾选）。"""
    root = SAMPLES / "pure_pdf"
    win.ed_root.setText(str(root))
    assert win.lw_targets.count() == 2
    names = [win.lw_targets.item(i).text() for i in range(win.lw_targets.count())]
    assert names == ["张三", "李四"]
    for i in range(win.lw_targets.count()):
        assert win.lw_targets.item(i).checkState() == Qt.Checked
    assert win.lb_target_status.text() == "已选 2/2"


def test_targets_uncheck_all(win, monkeypatch):
    """全不选 → 状态更新；开始构建配置被拦截并弹提示（modal 需 monkeypatch）。"""
    warned: list[str] = []
    monkeypatch.setattr("app.ui_main.QMessageBox.warning",
                        lambda *a, **k: warned.append(a[2] if len(a) > 2 else ""))
    root = SAMPLES / "pure_pdf"
    win.ed_root.setText(str(root))
    win._set_targets_checked(False)
    assert win.lb_target_status.text() == "已选 0/2"
    assert win._build_config() is None        # 无勾选 → 拒绝启动
    assert any("至少勾选" in m for m in warned)


def test_diagnostic_zip(tmp_path):
    """诊断包：日志 + 配置（密码脱敏）+ 引擎 + 系统信息。"""
    log_file = tmp_path / "a4merger_test.log"
    log_file.write_text("测试日志内容\n", encoding="utf-8")
    cfg = MergeConfig(root=Path("D:/x"), passwords=["123456", "secret"])
    out = tmp_path / "diag.zip"
    build_diagnostic_zip(out, cfg=cfg, log_file=log_file)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "logs/a4merger_test.log" in names
        assert "config.json" in names and "engines.json" in names and "system.json" in names
        cfg_json = json.loads(zf.read("config.json"))
        assert cfg_json["passwords"] == ["***", "***"]     # 脱敏
        assert "123456" not in zf.read("config.json").decode("utf-8")


def test_file_logging(tmp_path):
    """debug 日志落盘可用。"""
    log_path = tmp_path / "a.log"
    logger = setup_file_logging(log_path)
    import logging
    logging.getLogger("a4merger").info("单元测试日志行")
    assert "单元测试日志行" in log_path.read_text(encoding="utf-8")