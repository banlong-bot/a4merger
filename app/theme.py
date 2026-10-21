"""app/theme.py —— 「花笺」主题：暖纸底 + 竹绿 + 白卡片 + 柔和阴影 + 克制动效。

本文件是 DESIGN.md 的唯一实现处：
- `TOKENS` 与 DESIGN.md frontmatter 一一对应，界面代码不再散落十六进制色值；
- `theme.qss` 用 `$token` 占位符书写，`load_qss()` 时替换（长名优先，避免前缀误替换）；
- `apply()` 把样式挂到 QApplication，主窗口 / 结果对话框 / 消息框统一生效；
- 动画对象由模块级 `_ALIVE` 保活，否则被 GC 回收后动画不跑；
- `motion_enabled()` 为 False（环境变量 `A4_MOTION=0` 或界面开关关闭）时，
  所有动画函数直接落到终态，不创建任何动画对象。

字体：内置 `fonts/HarmonyOS_Sans_SC.ttf`（可变字重），打包后从 PyInstaller 的
`sys._MEIPASS` 读取；注册失败时回退系统 UI 字体，不阻断启动。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QEvent, QLocale,
                            QObject, QPropertyAnimation)
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect, QWidget)

# ---------------------------------------------------------------------------
# 设计 token（改色只改这里与 DESIGN.md frontmatter，两处必须一致）
# 颜色 17 个：暖纸底 / 卡片白 / 墨色文字 / 竹绿主色 / 三种语义状态色
TOKENS: dict[str, str] = {
    # 纸与表面
    "paper": "#F6F3EC",          # 暖纸底：窗口根、标题栏
    "paper-deep": "#EDE7DA",     # 暖纸深：状态栏、表头、悬停衬底
    "surface": "#FFFDF8",        # 次级表面：输入框、日志区、隔行
    "surface-raised": "#FFFFFF",  # 卡片白：分组卡、动作条、菜单、弹层
    "surface-subtle": "#F1ECE1",  # 弱化衬底：进度轨道、滚动槽
    "border": "#E3DCCD",         # 发丝线：1px 分隔与描边
    "border-strong": "#C8BFAC",  # 强发丝线：输入框描边、滚动条
    # 文字
    "ink": "#2B2A26",            # 主墨：正文
    "ink-muted": "#6A6559",      # 次墨：说明、状态栏（纸底对比 5.2:1）
    # 主色：竹绿
    "bamboo": "#2D5A3D",         # 竹绿：主按钮、焦点、选中下划线
    "bamboo-deep": "#1F4229",    # 竹绿深：悬停/按下
    "bamboo-soft": "#E6EEE4",    # 竹绿浅：选中/悬停衬底
    # 语义状态色
    "ok": "#2E7D4F",             # 成功绿（纸底对比 4.7:1）
    "warn": "#8F5A14",           # 警告琥珀（纸底对比 5.2:1）
    "error": "#B3261E",          # 错误红（纸底对比 5.9:1）
    "error-bg": "#FBEAE6",       # 错误红底：行内提示
    "error-border": "#C0392B",   # 错误描边：非法输入、行内提示边框
    # 圆角
    "radius-sm": "6px",
    "radius-md": "10px",
    "radius-lg": "14px",
    "radius-pill": "999px",     # 契约值：语义上表示「胶囊」
    # Qt 会忽略超大圆角（实测 999px / 50% 都画成直角），真实绘制用「半高像素值」：
    "radius-pill-px": "22px",
    # 间距（只用这五档）
    "gap-xs": "4px",
    "gap-sm": "8px",
    "gap-md": "12px",
    "gap-lg": "16px",
    "gap-xl": "24px",
    # 动效
    "motion-fast": "120ms",
    "motion-base": "180ms",
    "motion-slow": "240ms",
    "easing": "cubic-bezier(0.22,1,0.36,1)",
}

# M8 旧 token 名的兼容别名（其它模块若还按旧名取色，不至于回退成主墨色）
_ALIASES: dict[str, str] = {
    "accent": "bamboo",
    "accent-deep": "bamboo-deep",
    "accent-soft": "bamboo-soft",
}

QSS_PATH = Path(__file__).with_name("theme.qss")
FONT_FILE = "HarmonyOS_Sans_SC.ttf"
FONT_FAMILY_FALLBACK = "Microsoft YaHei UI"
_FONT_FAMILY: str | None = None
_MOTION_OVERRIDE: bool | None = None
_ALIVE: list[Any] = []          # 动画 / 事件过滤器保活（防 GC 后动画不动）

# 阴影档位：模糊半径、纵向偏移、颜色不透明度（0-255）
# M9 终稿：用户要求「阴影更明显一点」，在花笺原有极淡阴影上抬一档（仍是柔和投影，不做硬边）
_SHADOW_LEVELS = {
    "card": (26, 7, 54),
    "raised": (34, 10, 66),
    "float": (46, 14, 80),
}


# ---------------------------------------------------------------------------
# 颜色 / 样式表
def color(name: str) -> str:
    """取语义色（界面代码里替代散落的十六进制值）；未知名字回退 ink，不抛异常。"""
    if name in TOKENS:
        return TOKENS[name]
    if name in _ALIASES:
        return TOKENS[_ALIASES[name]]
    return TOKENS["ink"]


def _assets_dir() -> Path | None:
    """定位 UI 小图标目录（app/assets/）：源码运行 → PyInstaller onefile → onedir。"""
    here = Path(__file__).resolve().parent
    candidates = [here / "assets"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "app" / "assets")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "app" / "assets")
    for path in candidates:
        if path.is_dir():
            return path
    return None


def load_qss() -> str:
    """读取 theme.qss，替换全部 $token 与 $assets；文件缺失时返回空串（不阻断启动）。

    `$assets` 替换为 app/assets 的绝对路径（QSS 的 url() 用正斜杠）。
    图标目录缺失（如打包漏了资源）时，删掉所有 `image: url($assets/...)` 声明，
    退化成纯色块而不是报错或画出破图。
    """
    if not QSS_PATH.exists():
        return ""
    text = QSS_PATH.read_text(encoding="utf-8")
    assets = _assets_dir()
    if assets is not None:
        text = text.replace("$assets", assets.as_posix())
    else:
        text = re.sub(r"image:\s*url\(\$assets[^)]*\)\s*;?", "", text)
        text = text.replace("$assets", "")
    for key in sorted(TOKENS, key=len, reverse=True):   # 长名优先，避免前缀误替换
        text = text.replace(f"${key}", TOKENS[key])
    return text


# ---------------------------------------------------------------------------
# 字体
def _font_candidates() -> list[Path]:
    """内置字体候选路径：源码运行 → PyInstaller onefile → onedir。"""
    here = Path(__file__).resolve()
    candidates = [here.parent.parent / "fonts" / FONT_FILE]      # 仓库 fonts/
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "fonts" / FONT_FILE)   # onefile 解包目录
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "fonts" / FONT_FILE)
    return candidates


def ensure_fonts() -> str:
    """注册内置字体，返回首选 family 名；注册失败返回系统回退字体名。"""
    global _FONT_FAMILY
    if _FONT_FAMILY is not None:
        return _FONT_FAMILY
    if QApplication.instance() is None:          # 还没有 QGuiApplication，先不注册
        return FONT_FAMILY_FALLBACK
    for path in _font_candidates():
        try:
            if not path.is_file():
                continue
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id < 0:
                continue
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _FONT_FAMILY = families[0]
                return _FONT_FAMILY
        except Exception:                        # 字体损坏 / 权限问题都不阻断启动
            continue
    _FONT_FAMILY = FONT_FAMILY_FALLBACK
    return _FONT_FAMILY


def ui_font_family() -> str:
    """首选字体 family（供启动日志 / 诊断包展示）。"""
    return ensure_fonts()


def _use_latin_digits() -> None:
    """把默认区域固定为「简体中文-中国」，强制数字控件用拉丁数字。

    背景：本机系统区域是 zh_MO（澳门），Qt 6.12 在该区域用**汉字数码**格式化数字，
    QSpinBox 里的 600 会显示成「〩〩〩」一类的怪字符（看起来像乱码 / 字形被裁）。
    zh_CN 区域使用拉丁数字，语义不变，只影响数字显示。
    """
    QLocale.setDefault(QLocale(QLocale.Language.Chinese, QLocale.Country.China))


def apply(app: QApplication | None = None) -> None:
    """把主题挂到 QApplication（幂等：重复调用不会叠加样式表）。"""
    app = app or QApplication.instance()
    if app is None:
        return
    ensure_fonts()
    _use_latin_digits()
    app.setStyleSheet(load_qss())


# ---------------------------------------------------------------------------
# 动效开关
def motion_enabled() -> bool:
    """动效是否开启：环境变量 A4_MOTION 优先（=0 强制关闭），其次界面开关。"""
    env = os.environ.get("A4_MOTION")
    if env is not None and env.strip() != "":
        return env.strip().lower() not in {"0", "off", "false", "no"}
    if _MOTION_OVERRIDE is not None:
        return _MOTION_OVERRIDE
    return True


def set_motion_enabled(on: bool) -> None:
    """界面开关同步；关闭后新动画一律直接落终态。"""
    global _MOTION_OVERRIDE
    _MOTION_OVERRIDE = bool(on)


def _duration(token: str, fallback: int) -> int:
    """把 motion-* token（如 "180ms"）转成整数毫秒。"""
    try:
        return int(str(TOKENS.get(token, "")).strip().lower().rstrip("ms")) or fallback
    except ValueError:
        return fallback


def _easing() -> QEasingCurve:
    return QEasingCurve(QEasingCurve.Type.OutCubic)


def _keep(obj: Any) -> None:
    """保活动画对象，结束后自动从列表移除。"""
    _ALIVE.append(obj)
    try:
        obj.finished.connect(lambda *_: _ALIVE.remove(obj) if obj in _ALIVE else None)
    except Exception:
        pass


def _run(anim: QPropertyAnimation) -> None:
    _keep(anim)
    anim.start(QAbstractAnimation.DeletionPolicy.KeepWhenStopped)


# ---------------------------------------------------------------------------
# 动画
def fade_in(widget: QWidget, ms: int | None = None, start: float = 0.0) -> None:
    """窗口 / 整块淡入（windowOpacity）。"""
    if widget is None:
        return
    ms = _duration("motion-base", 180) if ms is None else int(ms)
    if not motion_enabled():
        widget.setWindowOpacity(1.0)
        return
    widget.setWindowOpacity(max(0.0, min(1.0, start)))
    anim = QPropertyAnimation(widget, b"windowOpacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(float(widget.windowOpacity()))
    anim.setEndValue(1.0)
    anim.setEasingCurve(_easing())
    _run(anim)


def fade_widget(widget: QWidget, ms: int | None = None, start: float = 0.0) -> None:
    """控件级淡入（QGraphicsOpacityEffect）；控件已有非透明度 effect 时不动。"""
    if widget is None:
        return
    ms = _duration("motion-fast", 120) if ms is None else int(ms)
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        if effect is not None:                   # 已有阴影等 effect：保持原样，直接可见
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    if not motion_enabled():
        effect.setOpacity(1.0)
        return
    effect.setOpacity(max(0.0, min(1.0, start)))
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(float(effect.opacity()))
    anim.setEndValue(1.0)
    anim.setEasingCurve(_easing())
    _run(anim)


def animate_progress(bar: QWidget, value: int, ms: int | None = None) -> None:
    """进度条平滑推进；关闭动效时直接 setValue。"""
    if bar is None:
        return
    ms = _duration("motion-slow", 240) if ms is None else int(ms)
    value = int(value)
    if not motion_enabled() or bar.value() == value:
        bar.setValue(value)
        return
    anim = QPropertyAnimation(bar, b"value", bar)
    anim.setDuration(ms)
    anim.setStartValue(int(bar.value()))
    anim.setEndValue(value)
    anim.setEasingCurve(_easing())
    _run(anim)


def animate_expand(panel: QWidget, expanded: bool, ms: int | None = None) -> None:
    """折叠面板高度展开 / 收起（改 maximumHeight）；关闭动效时同步落终态。"""
    if panel is None:
        return
    ms = _duration("motion-slow", 240) if ms is None else int(ms)
    unlimited = 16777215                          # QWIDGETSIZE_MAX
    if not motion_enabled():
        panel.setMaximumHeight(unlimited if expanded else 0)
        return
    target = panel.sizeHint().height() if expanded else 0
    current = panel.maximumHeight()
    if current >= unlimited or current < 0:
        current = panel.height()
    anim = QPropertyAnimation(panel, b"maximumHeight", panel)
    anim.setDuration(ms)
    anim.setStartValue(int(current))
    anim.setEndValue(int(target))
    anim.setEasingCurve(_easing())
    if expanded:
        anim.finished.connect(lambda: panel.setMaximumHeight(unlimited))
    _run(anim)


# ---------------------------------------------------------------------------
# 阴影
class _ShadowHover(QObject):
    """卡片悬停时把阴影加深一点（静态阴影由 attach_card_shadow 创建）。"""

    def __init__(self, widget: QWidget, effect: QGraphicsDropShadowEffect,
                 base_blur: int, hover_blur: int) -> None:
        super().__init__(widget)
        self._effect = effect
        self._base = base_blur
        self._hover = hover_blur

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt 命名)
        if event.type() == QEvent.Type.Enter:
            self._to(self._hover)
        elif event.type() == QEvent.Type.Leave:
            self._to(self._base)
        return False

    def _to(self, blur: int) -> None:
        effect = self._effect
        if motion_enabled():
            anim = QPropertyAnimation(effect, b"blurRadius", effect)
            anim.setDuration(_duration("motion-base", 180))
            anim.setStartValue(int(effect.blurRadius()))
            anim.setEndValue(int(blur))
            anim.setEasingCurve(_easing())
            _run(anim)
        else:
            effect.setBlurRadius(blur)


def attach_card_shadow(widget: QWidget, level: str = "card") -> None:
    """给卡片加柔和阴影（QGraphicsDropShadowEffect），悬停时轻微加深。

    QSS 不支持 box-shadow，阴影统一由这里提供；QScrollArea 内不要把同一控件叠加两层。
    """
    if widget is None:
        return
    blur, offset_y, alpha = _SHADOW_LEVELS.get(level, _SHADOW_LEVELS["card"])
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsDropShadowEffect):
        effect = QGraphicsDropShadowEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setBlurRadius(blur)
    effect.setOffset(0, offset_y)
    effect.setColor(QColor(46, 42, 33, alpha))
    if not getattr(widget, "_a4_shadow_attached", False):
        widget._a4_shadow_attached = True          # type: ignore[attr-defined]
        hover = _ShadowHover(widget, effect, blur, blur + 10)
        _ALIVE.append(hover)                       # 事件过滤器保活（随控件存活）
        widget.installEventFilter(hover)


# ---------------------------------------------------------------------------
# 最大化圆角 / 边框
def set_maximized_chrome(window: QWidget, maximized: bool) -> None:
    """最大化时窗口圆角归零、去掉 1px 边框。

    实现说明（对契约的补充，不是擅自改 API）：
    - Qt 把 `maximized` 作为 QWidget 的**内建只读属性**（metaObject writable=False），
      在窗口或外壳上 setProperty("maximized", ...) 会被静默忽略、property() 恒为 False，
      所以契约里的 `windowShell[maximized="true"]` 选择器永远命中不了；
    - 因此改用自定义动态属性 `winMaximized`（可读可写），QSS 里用
      `QFrame#windowShell[winMaximized="true"]` 命中；
    - 同时保留 `QMainWindow[maximized="true"] QFrame#windowShell` 兜底：即使窗口状态
      被系统直接改变（如双击标题栏）而没走到本函数，也能由内建属性命中；
    - 最后把窗口与外壳 unpolish/polish，让属性选择器重新求值。
    """
    if window is None:
        return
    shell = window.findChild(QFrame, "windowShell")
    targets: list[QWidget] = [window]
    if shell is not None:
        targets.append(shell)
        # 注意：属性值用 Python bool，QSS 侧按 "true"/"false" 字符串比较
        shell.setProperty("winMaximized", bool(maximized))
    for target in targets:
        style = target.style()
        style.unpolish(target)
        style.polish(target)
        target.update()
