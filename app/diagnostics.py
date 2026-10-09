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


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    d = Path(base) / "A4合并助手" if base else Path.home() / ".a4merger"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def current_log_file() -> Path:
    """本次运行的 debug 日志文件（启动时建立，贯穿整个进程）。"""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir() / f"a4merger_{stamp}.log"


def setup_file_logging(log_path: Path) -> logging.Logger:
    """把名为 a4merger 的 logger 同时写到日志文件（UTF-8）与 stderr（开发期）。"""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if logger.handlers:
        return logger
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
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
        "python": platform.python_version(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "cwd": str(Path.cwd()),
    }
    try:
        disk = shutil.disk_usage(str(data_dir()))
        info["disk_free_mb"] = round(disk.free / 1024 / 1024)
    except Exception:
        pass
    return info


def engine_probe() -> dict:
    """引擎可用性 + WPS 版本（注册表探测，带超时兜底）。"""
    from core.converters.manager import detect
    info: dict = detect()
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