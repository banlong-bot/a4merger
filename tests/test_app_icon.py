"""应用图标（assets/app.ico）回归测试。

覆盖「源图 → 多尺寸 ico → 打包/运行期取用」这条链路的可自动化部分：
  · 源图与 ico 都在仓库里（换图后离线可复现）；
  · ico 含 Windows 实际会用到的 7 档尺寸，且每档都能取出位图；
  · spec 把 ico 写进 exe 资源（icon=）并随 datas 打包（运行期窗口图标）；
  · app/icon.py 的定位顺序：打包解包目录（sys._MEIPASS）→ 工程目录；
  · 主窗口拿到非空图标（Qt 下空图标会静默退回系统默认，肉眼很难发现）。

exe 里真正有没有图标资源，由 tests/test_frozen_exe.py 在打包产物上断言。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "assets" / "app-icon.jpg"
ICO = REPO / "assets" / "app.ico"

# Windows 的图标尺寸档：16（列表/标题栏）、24/32（任务栏）、48/64（大图标）、
# 128/256（缩略图/超大图标）。任何一档缺失，系统就会拿别的尺寸硬缩，发糊。
WANTED = (16, 24, 32, 48, 64, 128, 256)


def test_source_image_committed():
    """源图入库（换图 + 重跑 build/make_icon.py 即可复现，无需联网）。"""
    assert SOURCE.exists() and SOURCE.stat().st_size > 0, f"缺少源图 {SOURCE}"


def test_ico_has_all_windows_sizes():
    """7 档尺寸齐全，且逐档可真正取出位图（不是只有目录项）。"""
    assert ICO.exists() and ICO.stat().st_size > 0, "缺少 assets/app.ico（先跑 build/make_icon.py）"
    with Image.open(ICO) as im:
        sizes = {w for w, _ in im.info.get("sizes", set())}
        assert set(WANTED) <= sizes, f"ico 缺档：{sorted(set(WANTED) - sizes)}"
        for side in WANTED:
            frame = im.ico.getimage((side, side))
            assert frame.size == (side, side)


def test_ico_is_square():
    """正方形（非正方形会被 Windows 拉伸变形）；最大档为 256。"""
    with Image.open(ICO) as im:
        big = im.ico.getimage((256, 256))
    assert big.size == (256, 256)
    assert big.width == big.height


def test_spec_embeds_and_bundles_icon():
    """打包配置：icon= 写进 exe 的 PE 资源；同时进 datas 供运行期读窗口图标。"""
    spec = (REPO / "build" / "a4merger.spec").read_text(encoding="utf-8")
    assert 'ICON_FILE = REPO / "assets" / "app.ico"' in spec
    assert "icon=str(ICON_FILE)" in spec
    assert '(str(ICON_FILE), "assets")' in spec


def test_icon_path_prefers_frozen_bundle(tmp_path, monkeypatch):
    """打包版优先用 sys._MEIPASS/assets/app.ico（datas 解包目录）。"""
    from app import icon as icon_mod

    bundled = tmp_path / "assets"
    bundled.mkdir()
    (bundled / icon_mod.ICON_NAME).write_bytes(ICO.read_bytes())
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert icon_mod.icon_path() == bundled / icon_mod.ICON_NAME


def test_icon_path_falls_back_to_repo(monkeypatch):
    """开发态（无 _MEIPASS）落到工程 assets/app.ico。"""
    from app import icon as icon_mod

    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert icon_mod.icon_path() == ICO


def test_main_window_has_icon():
    """主窗口图标非空（与 exe 图标同源）。"""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from app.icon import app_icon
    from app.ui_main import MainWindow

    qapp = QApplication.instance() or QApplication([])
    assert not app_icon().isNull(), "assets/app.ico 未能被 Qt 读取"
    win = MainWindow()
    try:
        assert not win.windowIcon().isNull()
    finally:
        win.deleteLater()
