"""app/icon.py —— 应用图标定位（窗口标题栏 + 任务栏）。

图标文件由 `build/make_icon.py` 从 `assets/app-icon.jpg` 生成：
  · 打包版：随 spec 的 datas 解包到 `sys._MEIPASS/assets/app.ico`；
  · 开发版：直接读工程 `assets/app.ico`。

定位不到时返回空 QIcon（退回系统默认图标）——图标缺失不应该影响程序启动。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

ICON_NAME = "app.ico"


def icon_path() -> Path | None:
    """按「打包解包目录 → 工程目录」顺序找图标文件；找不到返回 None。"""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "assets" / ICON_NAME)
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / ICON_NAME)
    for p in candidates:
        if p.exists():
            return p
    return None


def app_icon() -> QIcon:
    """应用图标（QIcon 必须晚于 QApplication 创建，见 app/main.py 的调用位置）。"""
    p = icon_path()
    return QIcon(str(p)) if p is not None else QIcon()
