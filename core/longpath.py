"""core/longpath.py —— Windows 长路径（260 字符）支持探测与 `\\\\?\\` 兜底（计划 3.11.3）。

三层对策：
  ① exe manifest 声明 longPathAware（build/version_info.txt + build/a4merger.spec 嵌入）；
  ② 启动时读注册表 LongPathsEnabled，未开启时提示"深层目录可能受限，建议项目放浅目录"；
  ③ 关键文件操作遇到超长路径时退回 `\\\\?\\` 前缀重试；仍失败则抛出中文错误（含路径长度）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 扩展长度路径前缀（仅 Win32；UNC 路径用 \\?\UNC\）
LONG_PATH_LIMIT = 260
_EXT_PREFIX = "\\\\?\\"


def _is_windows() -> bool:
    return sys.platform == "win32" or os.name == "nt"


def long_paths_enabled() -> bool:
    """系统是否已开启长路径支持（注册表 LongPathsEnabled=1）。"""
    if not _is_windows():
        return True
    try:
        import winreg                                     # 仅 Windows 可用
    except Exception:
        return False
    try:
        with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            value, _type = winreg.QueryValueEx(key, "LongPathsEnabled")
            return int(value) == 1
    except Exception:
        return False


def extended_path(path: str | Path) -> str:
    """把路径转成 `\\\\?\\` 扩展长度形式（已带前缀/非 Windows/相对路径则原样返回）。"""
    text = str(path)
    if not _is_windows() or text.startswith(_EXT_PREFIX):
        return text
    if not os.path.isabs(text):
        return text
    if text.startswith("\\\\"):                            # UNC：\\server\share → \\?\UNC\server\share
        return _EXT_PREFIX + "UNC" + text[1:]
    return _EXT_PREFIX + text


def supports_long_path(path: str | Path) -> bool:
    """当前进程能否直接操作该路径（不依赖注册表开关的实测判定）。"""
    target = Path(path)
    try:
        probe = target / ".a4_probe_longpath"
        with open(str(probe), "w", encoding="utf-8") as fh:
            fh.write("1")
        probe.unlink()
        return True
    except OSError:
        pass
    try:                                                  # 退回 \\?\ 前缀再试一次
        probe = Path(extended_path(target)) / ".a4_probe_longpath"
        with open(str(probe), "w", encoding="utf-8") as fh:
            fh.write("1")
        probe.unlink()
        return True
    except OSError:
        return False


def long_path_error(path: str | Path, exc: BaseException | None = None) -> str:
    """超长路径的中文报错文案（含完整路径与长度，绝不静默失败）。"""
    text = str(path)
    extra = f"（{type(exc).__name__}: {exc}）" if exc is not None else ""
    hint = ("系统未开启长路径支持，建议把项目放到更浅的目录，"
            "或让管理员开启「启用 Win32 长路径」（注册表 LongPathsEnabled=1）")
    return f"路径过长（{len(text)} 字符，系统上限约 {LONG_PATH_LIMIT}）：{text}{extra}。{hint}"


def startup_hint() -> str | None:
    """启动提示：未开启长路径支持时返回中文提示，否则 None。"""
    if long_paths_enabled():
        return None
    return ("系统未开启长路径支持：路径超过 260 字符的深层目录可能无法处理，"
            "建议把资料放到较浅的目录（如 D:\\资料）。")
