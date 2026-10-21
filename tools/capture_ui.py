"""tools/capture_ui.py —— 主窗口截图工具（皮肤改版前后对比用）。

用法（在仓库根执行）：
    python tools/capture_ui.py --prefix main-after --root tests/samples/pure_pdf

产物：docs/shots/<prefix>-empty.png、<prefix>-filled.png、<prefix>-advanced.png。
渲染：默认用 Windows 原生平台（字体/样式与真机一致）；无桌面环境可设 A4_SHOT_OFFSCREEN=1
退化为 offscreen（会额外加载仓库自带中文字体，避免截图全是方块）。
设置隔离：临时 A4_SETTINGS_DIR，且每次运行前清空，保证三张图都是「首次打开」的确定性状态。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="截取 A4 合并助手主窗口截图")
    ap.add_argument("--prefix", default="main", help="输出文件名前缀")
    ap.add_argument("--root", default="", help="填入的根目录（可选，用于截取已填充状态）")
    ap.add_argument("--outdir", default=str(REPO / "docs" / "shots"), help="输出目录")
    args = ap.parse_args(argv)

    # 默认用 Windows 原生平台渲染（字体/样式与真机一致）；offline/无桌面时设 A4_SHOT_OFFSCREEN=1
    offscreen = os.environ.get("A4_SHOT_OFFSCREEN") == "1"
    if not offscreen:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    settings_dir = REPO / ".tmpx" / "shot-settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    for stale in settings_dir.glob("*.ini"):        # 清掉上次截图留下的表单/折叠状态
        stale.unlink(missing_ok=True)
    os.environ["A4_SETTINGS_DIR"] = str(settings_dir)

    sys.path.insert(0, str(REPO))
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from app.ui_main import MainWindow

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    if offscreen:      # offscreen 插件没有系统字体目录，用仓库自带中文字体兜底（只为截图可读）
        font_file = REPO / "fonts" / "NotoSansCJKsc-Regular.otf"
        if font_file.exists():
            QFontDatabase.addApplicationFont(str(font_file))
    win = MainWindow()
    win.resize(1080, 720)
    win.show()
    app.processEvents()

    def shot(name: str, scroll: int | None = 0) -> None:
        """scroll=0 回顶部；None 保持当前滚动位置（展开高级选项后要看到面板）。"""
        if scroll is not None and hasattr(win, "scroll_left"):
            bar = win.scroll_left.verticalScrollBar()
            bar.setValue(0 if scroll == 0 else bar.maximum())
        app.processEvents()
        path = outdir / f"{args.prefix}-{name}.png"
        win.grab().save(str(path))
        print(f"已保存：{path}")

    shot("empty")
    if args.root:
        win.ed_root.setText(str((REPO / args.root) if not Path(args.root).is_absolute() else Path(args.root)))
        win.ed_root.setCursorPosition(0)        # 截图看路径开头，别显示成末尾滚动状态
        app.processEvents()
        shot("filled")
    if hasattr(win, "btn_advanced"):           # 新版才有折叠区
        win.btn_advanced.setChecked(True)
        app.processEvents()
        shot("advanced", scroll=None)
    win.close()
    app.processEvents()
    # Qt 原生平台在解释器退出期偶发 0xC0000409（与打包版同类）；截图已落盘，直接结束进程
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
