"""app/diagnostics.py —— debug 日志落盘、excepthook 兜底、诊断包导出（计划 3.11.7）。"""
from __future__ import annotations

import datetime
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from core import __version__

_LOGGER_NAME = "a4merger"

# 打包时写入的构建时间戳（build/make_version_info.py 以字符串替换本行）；
# 开发模式保持 0，界面显示"开发模式"。
BUILD_TIMESTAMP = 0.0


def build_time_text() -> str:
    """构建时间文本（打包版显示实际构建时间；开发模式显示"开发模式"）。"""
    if not BUILD_TIMESTAMP:
        return "开发模式（未打包）"
    return datetime.datetime.fromtimestamp(BUILD_TIMESTAMP).strftime("%Y-%m-%d %H:%M:%S")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def dependency_versions() -> dict[str, str]:
    """关键依赖版本（关于对话框 / 诊断包用，计划 3.11.10）。"""
    info: dict[str, str] = {}
    for name, mod, attr in (("PySide6", "PySide6", "__version__"),
                            ("pypdf", "pypdf", "__version__"),
                            ("Pillow", "PIL", "__version__"),
                            ("fpdf2", "fpdf", "__version__"),
                            ("msoffcrypto-tool", "msoffcrypto", None)):
        try:
            m = __import__(mod)
            if attr is None:
                from importlib.metadata import version as _v
                info[name] = _v(name)
            else:
                info[name] = str(getattr(m, attr, "未知"))
        except Exception:
            info[name] = "未安装"
    return info


def _candidate_data_dirs() -> list[Path]:
    """数据目录候选（按优先级）：%LOCALAPPDATA% → %TEMP% → 用户主目录。

    受限环境（企业策略/沙箱/只读配置文件）下写不了 %LOCALAPPDATA%，
    逐级退让，绝不因为"日志写不进去"就让应用启动失败（排障 2026-10）。
    """
    out: list[Path] = []
    base = os.environ.get("LOCALAPPDATA")
    if base:
        out.append(Path(base) / "A4合并助手")
    tmp = os.environ.get("TEMP") or os.environ.get("TMP")
    if tmp:
        out.append(Path(tmp) / "A4合并助手")
    out.append(Path.home() / ".a4merger")
    return out


def _try_dir(path: Path) -> Path | None:
    """建目录并实测可写；不可用返回 None。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".a4写入探测_{os.getpid()}"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return path
    except Exception:
        return None


def data_dir() -> Path:
    """应用数据目录（日志/诊断），自动选择第一个可写位置。"""
    for cand in _candidate_data_dirs():
        got = _try_dir(cand)
        if got is not None:
            return got
    return _candidate_data_dirs()[-1]          # 全都不可写：返回默认路径（后续操作会报错）


def log_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def current_log_file() -> Path:
    """本次运行的 debug 日志文件（启动时建立，贯穿整个进程）。"""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir() / f"a4merger_{stamp}.log"


def setup_file_logging(log_path: Path) -> logging.Logger:
    """把名为 a4merger 的 logger 同时写到日志文件（UTF-8）与 stderr（开发期）。

    日志文件打不开（权限/只读环境）时**不能让应用起不来**：退到控制台日志继续跑，
    并在 stderr 留一行中文说明。
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if logger.handlers:
        return logger
    try:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
    except Exception as exc:
        print(f"[提示] 无法写入日志文件（{type(exc).__name__}: {exc}），"
              f"本次仅输出到窗口日志区：{log_path}", file=sys.stderr, flush=True)
    try:
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(sh)
    except Exception:
        pass
    return logger


def log_debug(level: str, msg: str) -> None:
    """把 core 回调日志（level: info/warn/error/ok）写入 debug 日志文件。"""
    logger = logging.getLogger(_LOGGER_NAME)
    text = f"[{level}] {msg}"
    try:
        if level == "error":
            logger.error(text)
        elif level == "warn":
            logger.warning(text)
        else:
            logger.info(text)
    except Exception:
        pass


def install_excepthook(log_path: Path, dialog: bool = True) -> None:
    """全局兜底：未捕获异常写入日志文件，可选弹友好提示（计划 3.11.7）。"""

    def _hook(exc_type, exc_value, exc_tb):
        import traceback
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write("\n===== 未捕获异常 =====\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
        except Exception:
            pass
        if dialog:
            try:
                from PySide6.QtWidgets import QApplication, QMessageBox
                if QApplication.instance() is not None:
                    QMessageBox.critical(
                        None, "A4 合并助手",
                        "发生了意外错误，日志已保存。\n可点击「导出诊断包」发送给管理员排查。\n\n"
                        f"{exc_type.__name__}: {exc_value}")
            except Exception:
                pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


# ---------------------------------------------------------------- 系统信息

def _run_cmd(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return (r.stdout or b"").decode("utf-8", errors="replace").strip() \
            or (r.stderr or b"").decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def system_info() -> dict:
    info = {
        "app_version": __version__,
        "build_time": build_time_text(),
        "frozen": is_frozen(),
        "long_paths_enabled": _long_paths_enabled(),
        "python": platform.python_version(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "cwd": str(Path.cwd()),
        "dependencies": dependency_versions(),
    }
    try:
        disk = shutil.disk_usage(str(data_dir()))
        info["disk_free_mb"] = round(disk.free / 1024 / 1024)
    except Exception:
        pass
    return info


def _long_paths_enabled() -> bool:
    try:
        from core.longpath import long_paths_enabled
        return bool(long_paths_enabled())
    except Exception:
        return False


def engine_probe() -> dict:
    """引擎可用性 + WPS 版本（注册表探测，带超时兜底）。

    环境变量 A4_NO_POWERSHELL_PROBE=1 时跳过 PowerShell 版本探测（自动化测试用：
    受限环境下 exe 再拉 PowerShell 子进程会随机挂起，与功能正确性无关）。
    """
    from core.converters.manager import detect
    info: dict = detect()
    if os.environ.get("A4_NO_POWERSHELL_PROBE") == "1":
        info["wps_install_dir"] = "（已跳过探测）"
        return info
    wps = _run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "(Get-ItemProperty 'HKLM:\\SOFTWARE\\Kingsoft\\Office\\6.0\\common' "
                    "-ErrorAction SilentlyContinue).InstallRoot"], timeout=4.0)
    info["wps_install_dir"] = wps or "（未探测到）"
    return info


# ---------------------------------------------------------------- 诊断包

def build_diagnostic_zip(out_zip: Path, cfg=None, log_file: Path | None = None,
                         extra_text: str = "") -> Path:
    """把日志 + 配置（密码脱敏）+ 引擎探测 + 系统信息打包为 zip。"""
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        if log_file is not None and log_file.exists():
            zf.write(log_file, "logs/" + log_file.name)
        else:
            zf.writestr("logs/本次无日志.txt", "（未产生运行日志）")
        if cfg is not None:
            cfg_json = {
                "root": str(cfg.root),
                "level": cfg.level,
                "output_name": cfg.output_name,
                "output_dir": str(cfg.output_dir) if cfg.output_dir else None,
                "only": cfg.only,
                "margin_mm": cfg.margin_mm,
                "orientation": cfg.orientation,
                "image_fit": cfg.image_fit,
                "engine": cfg.engine,
                "skip_excel": cfg.skip_excel,
                "wps_timeout": cfg.wps_timeout,
                "report": cfg.report,
                "passwords": ["***" for _ in cfg.passwords],      # 脱敏
            }
            zf.writestr("config.json", json.dumps(cfg_json, ensure_ascii=False, indent=2))
        zf.writestr("engines.json",
                    json.dumps(engine_probe(), ensure_ascii=False, indent=2))
        zf.writestr("system.json", json.dumps(system_info(), ensure_ascii=False, indent=2))
        if extra_text:
            zf.writestr("note.txt", extra_text)
    return out_zip