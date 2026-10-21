"""app/theme.py —— 主窗口极简浅色皮肤（DESIGN.md 的唯一实现处）。

- `TOKENS` 与 DESIGN.md frontmatter 的颜色/圆角/间距一一对应，别处不再散落十六进制色值；
- `theme.qss` 用 `$token` 占位符书写，加载时替换（长名优先替换，避免 $surface / $surface-subtle 互相踩踏）；
- `apply()` 把样式挂到 QApplication 上，主窗口、结果对话框、消息框统一生效。

皮肤改版依据：docs/shape-主窗口极简浅色皮肤.md（用户确认：允许大改信息架构、
高级选项折叠、三步引导只留一行字、试运行留在主按钮区）。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

# DESIGN.md frontmatter 原值（改色只改这里 + DESIGN.md，两处必须一致）
TOKENS: dict[str, str] = {
    "surface": "#ffffff",
    "surface-subtle": "#f7f8fa",
    "border": "#d9dde3",
    "ink": "#333333",
    "ink-muted": "#555555",
    "accent": "#1565c0",
    "accent-deep": "#0d47a1",
    "accent-soft": "#eef4fb",
    "ok": "#1e7d32",
    "warn": "#b26a00",
    "error": "#c62828",
    "error-bg": "#fdecea",
    "error-border": "#c0392b",
    # 形状与间距（DESIGN.md rounded / spacing）
    "radius-sm": "4px",
    "radius-md": "6px",
    "gap-xs": "4px",
    "gap-sm": "8px",
    "gap-md": "12px",
}

QSS_PATH = Path(__file__).with_name("theme.qss")


def color(name: str) -> str:
    """取语义色（界面代码里替代散落的十六进制值）；未知名字回退 ink，不抛异常。"""
    return TOKENS.get(name, TOKENS["ink"])


def load_qss() -> str:
    """读取 theme.qss 并替换全部 $token；文件缺失时返回空串（不阻断启动）。"""
    if not QSS_PATH.exists():
        return ""
    text = QSS_PATH.read_text(encoding="utf-8")
    for key in sorted(TOKENS, key=len, reverse=True):   # 长名优先，避免前缀误替换
        text = text.replace(f"${key}", TOKENS[key])
    return text


def apply(app: QApplication | None = None) -> None:
    """把皮肤挂到 QApplication（重复调用无副作用）。"""
    app = app or QApplication.instance()
    if app is None:
        return
    app.setStyleSheet(load_qss())
