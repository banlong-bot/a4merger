"""app/settings.py —— QSettings 配置持久化（计划 2.2：记住全部配置与勾选）。

安全约定（计划 3.11.9）：密码默认不保存；保存走 DPAPI 由 M3 的
core/encrypt 侧实现（ctypes CryptProtectData），本模块只做存取。
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QSettings

ORG = "A4合并助手"
APP = "A4合并助手"


class AppSettings:
    def __init__(self) -> None:
        self.qs = QSettings(ORG, APP)
        self.qs.setFallbacksEnabled(False)

    # ------------------------------------------------------------ 基础
    def get(self, key: str, default: Any = None) -> Any:
        return self.qs.value(key, default)

    def set(self, key: str, value: Any) -> None:
        self.qs.setValue(key, value)

    def get_str(self, key: str, default: str = "") -> str:
        v = self.qs.value(key, default)
        return v if isinstance(v, str) else str(v)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """类型韧性的布尔读取（注册表可能把 bool 漂移成 str）。"""
        v = self.qs.value(key, default)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        return str(v).strip().lower() in ("true", "1", "yes", "on")

    def get_int(self, key: str, default: int = 0) -> int:
        v = self.qs.value(key, default)
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------ 结构化存取
    def get_str_list(self, key: str) -> list[str]:
        raw = self.get_str(key, "")
        if not raw:
            return []
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except Exception:
            return []

    def set_str_list(self, key: str, items: list[str]) -> None:
        self.set(key, json.dumps(list(items), ensure_ascii=False))

    # ------------------------------------------------------------ 窗口
    def save_window(self, w) -> None:
        self.set("window/geometry", w.saveGeometry().toBase64().data().decode("ascii"))
        self.set("window/state", w.saveState().toBase64().data().decode("ascii"))

    def restore_window(self, w) -> None:
        geo = self.get_str("window/geometry")
        state = self.get_str("window/state")
        if geo:
            from PySide6.QtCore import QByteArray
            w.restoreGeometry(QByteArray.fromBase64(geo.encode("ascii")))
        if state:
            from PySide6.QtCore import QByteArray
            w.restoreState(QByteArray.fromBase64(state.encode("ascii")))