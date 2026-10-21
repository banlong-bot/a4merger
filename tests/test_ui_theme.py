"""主窗口「花笺」皮肤与信息架构用例（M9：暖纸底 + 竹绿 + 无边框窗口 + 动效）。

只测「语义与行为」：QSS 是否真的挂上、token 与 DESIGN.md 是否一致、字体/动效开关、
动画在关闭动效时是否落终态、阴影/最大化外壳是否生效、折叠与行内提示等交互。
像素级外观不做断言（截图对比见 docs/shots/）。
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect, QMainWindow, QProgressBar,
                               QWidget)

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "tests" / "samples"
QSS_FILE = REPO / "app" / "theme.qss"

_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def wait_until(pred, timeout_ms: int = 1500, step_ms: int = 20) -> bool:
    """事件循环推进直到 pred 为真（动效/定时器是异步的，不能同步断言）。"""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        qapp().processEvents()
        if pred():
            return True
        QTest.qWait(step_ms)
    qapp().processEvents()
    return bool(pred())


@pytest.fixture(scope="module", autouse=True)
def _app():
    qapp()
    yield


@pytest.fixture()
def win():
    """干净窗口：清掉其它用例可能残留的根目录/勾选/展开记忆（会话共享同一 INI）。"""
    from app.settings import AppSettings
    from app.ui_main import MainWindow

    s = AppSettings()
    old_root = s.get_str("root")
    old_checked = s.get_str_list("checked_targets")
    old_expanded = s.get_bool("advanced_expanded", False)
    s.qs.remove("root")
    s.qs.remove("checked_targets")
    s.qs.remove("advanced_expanded")
    w = MainWindow()
    w.show()
    qapp().processEvents()
    yield w
    w.close()
    w.deleteLater()
    qapp().processEvents()
    s.qs.setValue("root", old_root)
    if old_checked:
        s.set_str_list("checked_targets", old_checked)
    else:
        s.qs.remove("checked_targets")
    s.set("advanced_expanded", old_expanded)


# ---------------------------------------------------------------- 主题 / token
def test_theme_applies_stylesheet():
    """皮肤挂在应用级 QSS 上（唯一实现处 app/theme.py），且是花笺配色。"""
    from app import theme

    theme.apply()
    css = qapp().styleSheet()
    assert css, "应用级 QSS 为空"
    assert theme.color("paper").lower() in css.lower()      # 暖纸底
    assert theme.color("bamboo").lower() in css.lower()     # 竹绿主色
    assert f'font-family: "{theme.ui_font_family()}"' in css or "HarmonyOS Sans SC" in css
    assert "QPushButton#primaryButton" in css               # 主按钮规格
    assert "QFrame#windowShell" in css                      # 无边框窗口外壳


def test_theme_apply_is_idempotent():
    """重复 apply 不叠加 QSS（窗口重建/多实例时不膨胀）。"""
    from app import theme

    theme.apply()
    n1 = len(qapp().styleSheet())
    theme.apply()
    assert len(qapp().styleSheet()) == n1


def _design_frontmatter() -> dict[str, dict[str, str]]:
    """解析 DESIGN.md 的 YAML frontmatter（只需 colors/rounded/spacing 三段）。"""
    text = (REPO / "DESIGN.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].strip() == "---", "DESIGN.md 缺少 frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    sections: dict[str, dict[str, str]] = {}
    current = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            current = line.split(":", 1)[0].strip()
            sections[current] = {}
            continue
        if current is None:
            continue
        key, _, value = line.strip().partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        # 只保留简单标量（typography/components 是嵌套结构，这里不需要）
        sections[current][key] = value
    return sections


def test_theme_tokens_match_design_md():
    """token 值与 DESIGN.md frontmatter 一致（颜色/圆角/间距三组）。"""
    from app import theme

    design = _design_frontmatter()
    colors = design.get("colors", {})
    assert len(colors) >= 17, f"DESIGN.md 颜色 token 少于 17 个：{len(colors)}"
    for key, value in colors.items():
        assert theme.TOKENS.get(key, "").lower() == value.lower(), f"颜色 {key} 不一致"

    rounded = design.get("rounded", {})
    for key, value in rounded.items():
        assert theme.TOKENS.get(f"radius-{key}") == value, f"圆角 radius-{key} 不一致"
    assert theme.TOKENS["radius-lg"] == "14px"

    spacing = design.get("spacing", {})
    for key, value in spacing.items():
        assert theme.TOKENS.get(f"gap-{key}") == value, f"间距 gap-{key} 不一致"


def test_theme_color_semantics():
    """关键语义色：竹绿主色、暖纸底、错误红；未知名字回退墨色不抛错。"""
    from app import theme

    def rgb(name: str) -> tuple[int, int, int]:
        h = theme.color(name).lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    br, bg, bb = rgb("bamboo")
    assert bg > br and bg > bb, "bamboo 不是绿色系"

    pr, pg, pb = rgb("paper")
    assert pr >= pg >= pb, "paper 不是暖色纸底"

    assert theme.color("不存在的名字") == theme.color("ink")   # 回退，不抛 KeyError
    assert theme.color("accent") == theme.color("bamboo")      # M8 旧名别名兼容
    assert "motion-base" in theme.TOKENS


def test_qss_has_no_unresolved_tokens():
    """$token 全部被替换；内置字体与最大化选择器都在最终 QSS 里。"""
    from app import theme

    css = theme.load_qss()
    assert css.strip()
    # 注释里可以出现「$token」这种说明文字，扫描前先剥掉注释
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert not re.search(r"\$[A-Za-z][A-Za-z0-9_-]*", body), "QSS 里还有未替换的 $token"
    assert "HarmonyOS Sans SC" in css
    assert 'winMaximized="true"' in css
    assert 'QMainWindow[maximized="true"]' in css


def test_qss_covers_contract_object_names():
    """契约第四节的 objectName 在 QSS 里都有样式（防止装修漏掉某类控件）。"""
    css = QSS_FILE.read_text(encoding="utf-8")
    required = [
        "#windowShell", "#titleBar", "#menuButton", "#winMin", "#winMax", "#winClose",
        "#statusBarCustom", "#cardBox", "#actionBar", "#primaryButton",
        "#advancedToggle", "#logView", "#sectionLabel", "#targetStatus",
        "#expectLabel", "#inlineError",
    ]
    missing = [name for name in required if name not in css]
    assert not missing, f"QSS 缺少这些 objectName 的样式：{missing}"


def test_theme_assets_exist():
    """QSS 用到的自绘小图标随源码存在（打包由 spec 的 datas 带上）。"""
    assets = REPO / "app" / "assets"
    assert assets.is_dir()
    for name in ("check-white.png", "check-dark.png", "radio-dot.png", "chevron-down.png"):
        f = assets / name
        assert f.is_file() and f.stat().st_size > 0, f"缺少图标 {name}"


# ---------------------------------------------------------------- 字体
def test_font_registration():
    """内置 HarmonyOS Sans SC 注册成功，QSS 字体就是它。"""
    from app import theme

    family = theme.ui_font_family()
    assert family
    assert "harmony" in family.lower(), f"内置字体未注册，实际 family={family}"
    assert theme.ensure_fonts() == family                      # 幂等
    assert Path(theme.__file__).with_name("theme.qss").exists()


# ---------------------------------------------------------------- 动效开关
def test_motion_env_switch(monkeypatch):
    """A4_MOTION=0 强制关闭动效；无环境变量时由界面开关决定。"""
    from app import theme

    monkeypatch.setenv("A4_MOTION", "0")
    assert theme.motion_enabled() is False
    monkeypatch.delenv("A4_MOTION", raising=False)
    old = theme.motion_enabled()
    try:
        theme.set_motion_enabled(True)
        assert theme.motion_enabled() is True
        theme.set_motion_enabled(False)
        assert theme.motion_enabled() is False
    finally:
        theme.set_motion_enabled(old)


def test_animations_terminal_when_motion_off():
    """关闭动效后所有动画函数同步落终态（不创建动画、等待时间为 0）。"""
    from app import theme

    old = theme.motion_enabled()
    try:
        theme.set_motion_enabled(False)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        theme.animate_progress(bar, 42)
        assert bar.value() == 42

        panel = QWidget()
        theme.animate_expand(panel, True)
        assert panel.maximumHeight() == 16777215            # QWIDGETSIZE_MAX
        theme.animate_expand(panel, False)
        assert panel.maximumHeight() == 0

        label = QWidget()
        theme.fade_widget(label)
        effect = label.graphicsEffect()
        assert isinstance(effect, QGraphicsOpacityEffect)
        assert effect.opacity() == 1.0

        window = QWidget()
        theme.fade_in(window)
        assert window.windowOpacity() == 1.0
    finally:
        theme.set_motion_enabled(old)


def test_card_shadow_effect():
    """卡片阴影：挂上 QGraphicsDropShadowEffect，重复 attach 不叠加新的。"""
    from app import theme

    card = QWidget()
    theme.attach_card_shadow(card)
    effect = card.graphicsEffect()
    assert isinstance(effect, QGraphicsDropShadowEffect)
    assert effect.blurRadius() > 0
    theme.attach_card_shadow(card)
    assert card.graphicsEffect() is effect, "重复 attach 叠加了第二层阴影"


def test_maximized_chrome_sets_property():
    """最大化外壳：优先读外壳自定义属性 winMaximized（Qt 内建 maximized 只读）。"""
    from app import theme

    host = QMainWindow()
    shell = QFrame(host)
    shell.setObjectName("windowShell")
    host.setCentralWidget(shell)
    host.show()
    qapp().processEvents()
    try:
        theme.set_maximized_chrome(host, True)
        assert shell.property("winMaximized") in (True, "true")
        theme.set_maximized_chrome(host, False)
        assert shell.property("winMaximized") in (False, "false", None)
    finally:
        host.close()
        host.deleteLater()
        qapp().processEvents()


# ---------------------------------------------------------------- 窗口信息架构
def test_window_default_state(win):
    """初始态：高级选项折叠、无行内错误、开始按钮可用、主题三行日志。"""
    assert win.adv_panel.isHidden()
    assert not win.btn_advanced.isChecked()
    assert win.lb_target_status.text() == ""
    assert win.lb_inline_error.isHidden()
    assert win.btn_start.isEnabled()
    assert "选根目录" in win.lb_expect.text()
    log = win.txt_log.toPlainText()
    assert "界面皮肤：已加载" in log
    assert "界面字体：" in log
    assert "界面动效：" in log


def test_window_is_frameless(win):
    """无边框窗口：没有原生标题栏/菜单栏，外壳是 #windowShell。"""
    assert win.windowFlags() & Qt.WindowType.FramelessWindowHint
    shell = win.findChild(QFrame, "windowShell")
    assert shell is not None
    assert win.centralWidget() is shell


def test_advanced_options_toggle(win):
    """展开/收起只影响可见性与高度，不改变默认值（默认仍不跳过 Excel 等）。"""
    qapp().processEvents()
    win.btn_advanced.setChecked(True)
    assert wait_until(lambda: not win.adv_panel.isHidden(), 1200)
    assert win.cb_skip_excel.isChecked() is False
    win.btn_advanced.setChecked(False)
    # 收起走 240ms 高度动画，动画结束才隐藏（不能同步断言）
    assert wait_until(lambda: win.adv_panel.isHidden(), 1500)


def test_targets_scroll_area_resists_many_folders(win):
    """目标列表放在滚动区里：文件夹多时窗口不被撑高（M8 信息架构保留）。"""
    root = SAMPLES / "pure_pdf"
    win.ed_root.setText(str(root))
    assert win.scroll_left.widget() is not None
    hint = win.minimumSizeHint()
    assert hint.height() <= 780


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
    assert not win.lb_inline_error.isHidden()
    assert "文件名模板" in win.lb_inline_error.text()
    assert warned == []
    win.ed_template.setText("【合并】{folder}.pdf")
    assert win.btn_start.isEnabled()
    assert win.lb_inline_error.isHidden()


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
def test_advanced_expanded_is_remembered():
    """展开状态持久化：关窗口保存，下次打开保持上次样子。"""
    from app.settings import AppSettings
    from app.ui_main import MainWindow

    s = AppSettings()
    old = s.get_bool("advanced_expanded", False)
    first = second = None
    try:
        s.set("advanced_expanded", True)
        first = MainWindow()
        first.show()
        qapp().processEvents()
        assert wait_until(lambda: not first.adv_panel.isHidden(), 1200)
        first.close()
        qapp().processEvents()

        second = MainWindow()
        second.show()
        qapp().processEvents()
        assert wait_until(lambda: not second.adv_panel.isHidden(), 1200)

        second.btn_advanced.setChecked(False)
        second.close()                                # closeEvent → _save_settings
        qapp().processEvents()
        assert AppSettings().get_bool("advanced_expanded", True) is False
    finally:
        for w in (first, second):
            if w is not None:
                w.deleteLater()
        qapp().processEvents()
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
