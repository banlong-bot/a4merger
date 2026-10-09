"""core/converters/manager.py —— 引擎探测与选择（WPS → 纯 Python，计划 3.6）。"""
from __future__ import annotations

from core.converters.backend_native import NativeConverter
from core.converters.backend_wps import WpsConverter


def detect() -> dict[str, bool]:
    """返回各引擎可用性：{"wps": bool, "native": bool}。"""
    return {"wps": WpsConverter().available(), "native": NativeConverter().available()}


def pick(kind: str, engine: str, available: dict[str, bool]) -> str:
    """按文件类型与用户引擎选择，决定使用哪个后端。

    返回 "wps" / "native" / "none"。
    - engine=auto：word/excel/ppt 必须 WPS（无则 none）；image/text 优先 WPS、否则 native；
    - engine=wps：一律 WPS（无则 none）；
    - engine=native：一律 native（word/excel/ppt 不支持 → none）。
    """
    if engine == "native":
        return "native" if kind in ("image", "text") else "none"
    if engine == "wps":
        return "wps" if available.get("wps") else "none"
    # auto
    if kind in ("word", "excel", "ppt"):
        return "wps" if available.get("wps") else "none"
    return "wps" if available.get("wps") else "native" if available.get("native") else "none"