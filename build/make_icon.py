# -*- mode: python ; coding: utf-8 -*-
"""build/make_icon.py —— 由源图生成多尺寸 Windows 应用图标 assets/app.ico。

用法（工程根目录，与打包同一 Python 3.12）：
    python build/make_icon.py

产物 assets/app.ico 的两种用途：
  · `build/a4merger.spec` 的 `icon=` —— 写进 exe 的 PE 资源（文件/桌面/任务栏图标）；
  · `app/icon.py` 运行时读取 —— 窗口标题栏与任务栏图标（datas 随包解包）。

源图 assets/app-icon.jpg 入库，保证换图后离线可复现（与 fonts/ 同一取舍）。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "assets" / "app-icon.jpg"
TARGET = REPO / "assets" / "app.ico"

# Windows 图标实际会用到的尺寸：16/24/32（任务栏·文件列表）、48/64（大图标）、
# 128/256（缩略图与"超大图标"视图）。缺哪档，系统就会拿别的尺寸硬缩，糊。
SIZES = (16, 24, 32, 48, 64, 128, 256)


def build(source: Path = SOURCE, target: Path = TARGET) -> Path:
    """源图 → 居中裁成正方形 → 逐档重采样后写出多尺寸 .ico。"""
    with Image.open(source) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGBA")
    side = min(img.size)                              # 源图允许非正方形：裁中间，避免变形
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    base = img.resize((max(SIZES), max(SIZES)), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    # 交给 Pillow 写 ICO：每档由 256 基图按 LANCZOS 重采样（尺寸为 2 的幂/整除数时最干净）
    base.save(target, format="ICO", sizes=[(s, s) for s in SIZES])
    return target


def main() -> int:
    target = build()
    with Image.open(target) as ico:
        got = sorted(ico.info.get("sizes", set()))
    print(f"源图：{SOURCE}")
    print(f"已生成：{target}（{target.stat().st_size} 字节）")
    print("内含尺寸：" + ", ".join(f"{w}x{h}" for w, h in got))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
