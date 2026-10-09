"""app/worker.py —— 后台执行线程（M2 骨架；M3 完善取消与密码弹窗）。"""
from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from core.runner import run as runner_run
from core.types import MergeConfig, RunSummary


class RunnerWorker(QThread):
    """把 core.runner 放到线程执行，信号桥接回主线程。"""

    log_signal = Signal(str, str)               # (level, message)
    progress_signal = Signal(str, int, int, str)  # (kind, done, total, text)
    finished_signal = Signal(object)            # RunSummary

    def __init__(self, cfg: MergeConfig, parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self._cancel = False

    def cancel(self) -> None:
        """置取消标志；core 侧 WPS 批处理会立即 terminate 子进程（3.11.4）。"""
        self._cancel = True

    def run(self) -> None:                      # QThread 入口
        t0 = time.time()
        try:
            summary = runner_run(
                self.cfg,
                on_log=lambda level, msg: self.log_signal.emit(level, msg),
                on_progress=lambda k, d, t, x: self.progress_signal.emit(k, d, t, x),
                ask_password=None,               # M2：遇到加密直接跳过；M3 改弹窗
                should_cancel=lambda: self._cancel)
            self.log_signal.emit("info", f"总耗时 {time.time() - t0:.1f} 秒")
            self.finished_signal.emit(summary)
        except Exception as exc:                 # 兜底：绝不静默
            self.log_signal.emit("error", f"运行失败：{exc}")
            self.finished_signal.emit(None)