"""主窗口皮肤与信息架构用例（M8：极简浅色皮肤 + 折叠高级选项 + 行内提示）。

只测「语义与行为」：QSS 是否真的挂上、折叠默认态、行内提示替代模态弹窗、
设置能否记忆。像素级外观不做断言（截图对比见 docs/shots/）。
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "tests" / "samples"

_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


@pytest.fixture(scope="module", autouse=True)
def _app():
    qapp()
    yield


@pytest.fixture()
def win():
    """干净窗口：清掉其它用例可能残留的根目录/勾选记忆（会话共享同一 INI）。"""
    from app.settings import AppSettings
    from app.ui_main import MainWindow
    s = AppSettings()
    old_root = s.get_str("root")
    old_checked = s.get_str_list("checked_targets")
    s.qs.remove("root")
    s.qs.remove("checked_targets")
    w = MainWindow()
    w.show()
    qapp().processEvents()
    yield w
    w.close()
    w.deleteLater()
    s.qs.setValue("root", old_root)
    if old_checked:
        s.set_str_list("checked_targets", old_checked)
    else:
        s.qs.remove("checked_targets")


# ---------------------------------------------------------------- theme
def test_theme_applies_stylesheet():
    """皮肤挂在应用级 QSS 上（唯一实现处 app/theme.py）。"""
    from app import theme
    theme.apply()
    css = qapp().styleSheet()
    assert css, "应用级 QSS 为空"
    assert "#f7f8fa" in css                     # surface-subtle（画布）
    assert "#1565c0" in css                     # accent
    assert "QPushButton#primary" in css         # 主按钮强调规格


def test_theme_apply_is_idempotent():
    """重复 apply 不叠加 QSS（窗口重建/多实例时不膨胀）。"""
    from app import theme
    theme.apply()
    n1 = len(qapp().styleSheet())
    theme.apply()
    assert len(qapp().styleSheet()) == n1


def test_theme_tokens_match_design_md():
    """token 值与 DESIGN.md 一致，且 color() 对未知名字不抛错。"""
    from app import theme
    assert theme.color("accent") == "#1565c0"
    assert theme.color("surface-subtle") == "#f7f8fa"
    assert theme.color("border") == "#d9dde3"
    assert theme.color("error") == "#c62828"
    assert theme.color("不存在的名字") == "#333333"      # 回退 ink，不抛异常


def test_theme_qss_file_shipped():
    """QSS 文件随源码存在（打包时由 spec 作为 datas 带上）。"""
    from app import theme
    qss = Path(theme.__file__).with_name("theme.qss")
    assert qss.exists() and qss.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------- 信息架构
def test_window_default_state(win):
    """初始态：高级选项折叠、状态与期待行为空、开始按钮可用。"""
    assert win.adv_panel.isHidden()
    assert not win.btn_advanced.isChecked()
    assert win.lb_target_status.text() == ""
    assert win.lb_inline_error.isHidden()
    assert win.btn_start.isEnabled()
    assert "选根目录" in win.lb_expect.text()
    # 启动日志说明皮肤是否真的加载（打包漏 datas 时能立刻发现）
    assert "界面皮肤：已加载" in win.txt_log.toPlainText()


def test_advanced_options_toggle(win):
    """展开/收起只影响可见性，不改变默认值（默认仍不跳过 Excel 等）。"""
    win.resize(1080, 720)
    qapp().processEvents()
    win.btn_advanced.setChecked(True)
    assert not win.adv_panel.isHidden()
    assert win.cb_skip_excel.isChecked() is False
    # 左栏在滚动区里：展开后若内容超高，应自动滚到折叠开关处，否则用户看不到变化
    qapp().processEvents()
    sb = win.scroll_left.verticalScrollBar()
    if sb.maximum() > 0:
        assert sb.value() > 0
    win.btn_advanced.setChecked(False)
    assert win.adv_panel.isHidden()


def test_targets_scroll_area_resists_many_folders(win):
    """目标列表放在滚动区里：文件夹多时窗口不被撑高（M8 信息架构）。"""
    root = SAMPLES / "pure_pdf"
    win.ed_root.setText(str(root))
    assert win.scroll_left.widget() is not None
    hint = win.minimumSizeHint()
    assert hint.height() <= 760


def test_expect_hint_follows_selection(win):
    """期待行随勾选与「仅预览」变化，用户不必读文档才知道会发生什么。"""
    win.ed_root.setText(str(SAMPLES / "pure_pdf"))
    assert "2 个文件夹" in win.lb_expect.text()
    win.cb_dryrun.setChecked(True)
    assert "试运行" in win.lb_expect.text()
    win.cb_dryrun.setChecked(False)
    assert "A4 PDF" in win.lb_expect.text()


# ---------------------------------------------------------------- 行内提示
def test_template_error_is_inline(win, monkeypatch):
    """模板非法 → 行内红字 + 禁用开始，不弹模态框。"""
    warned: list[str] = []
    monkeypatch.setattr("app.ui_main.QMessageBox.warning",
                        lambda *a, **k: warned.append(a[2] if len(a) > 2 else ""))
    win.ed_root.setText(str(SAMPLES / "pure_pdf"))
    win.ed_template.setText("A:B.pdf")
    assert not win.btn_start.isEnabled()
    assert win.lb_inline_error.isVisible()
    assert "文件名模板" in win.lb_inline_error.text()
    assert warned == []
    win.ed_template.setText("【合并】{folder}.pdf")
    assert win.btn_start.isEnabled()
    assert not win.lb_inline_error.isVisible()


def test_invalid_root_is_inline(win, monkeypatch):
    """根目录失效 → 行内提示，不弹模态框。"""
    warned: list[str] = []
    monkeypatch.setattr("app.ui_main.QMessageBox.warning",
                        lambda *a, **k: warned.append(a[2] if len(a) > 2 else ""))
    win.ed_root.setText(str(SAMPLES / "不存在的目录"))
    assert win.lw_targets.count() == 0
    assert win.lb_target_status.text() == ""          # 不再显示误导性的「已选 0/0」
    assert win._build_config() is None
    assert "根目录" in win.lb_inline_error.text()
    assert warned == []


# ---------------------------------------------------------------- 设置记忆
def test_advanced_expanded_is_remembered(win):
    """展开状态持久化（下次打开保持上次的样子）。"""
    from app.settings import AppSettings
    s = AppSettings()
    old = s.get_bool("advanced_expanded", False)
    try:
        win.btn_advanced.setChecked(True)
        win._save_settings()
        assert AppSettings().get_bool("advanced_expanded", False) is True
        win.btn_advanced.setChecked(False)
        win._save_settings()
        assert AppSettings().get_bool("advanced_expanded", False) is False
    finally:
        s.set("advanced_expanded", old)


# ---------------------------------------------------------------- 进度与日志
def test_progress_labels_carry_text(win):
    """进度文字写在标题行（不压在蓝条上）：文件夹/页面各有独立文案。"""
    win._on_progress("folder", 0, 3, "张三")
    assert "1/3" in win.lb_prog_folder.text() and "张三" in win.lb_prog_folder.text()
    win._on_progress("page", 2, 9, "第 2/9 页")
    assert "页面进度" in win.lb_prog_page.text() and "2/9" in win.lb_prog_page.text()
    # 运行中轨道加高；空闲/结束后回到细条（避免被误读成空输入框）
    win._reset_progress()
    assert win.pb_folder.height() <= 10 and win.pb_page.height() <= 10
    assert win.lb_prog_folder.text() == "文件夹进度"


def test_log_trim_keeps_bounded(win, monkeypatch):
    """日志超过上限会截断（_trim_log 真被执行，不是占位代码）。"""
    import app.ui_main as ui
    monkeypatch.setattr(ui, "LOG_MAX_BLOCKS", 20)
    monkeypatch.setattr(ui, "LOG_TRIM_AMOUNT", 5)
    for i in range(80):
        win._append_log("info", f"第 {i} 行")
    assert win.txt_log.blockCount() <= 25
    assert "第 79 行" in win.txt_log.toPlainText()
