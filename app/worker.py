"""app/worker.py —— 后台执行线程（M3：密码弹窗回调 + 取消终止子进程）。

密码流程：worker 线程需要密码时发 password_requested 信号 → 主线程弹模态输入框
（3 次重试，取消=跳过）→ 通过 submit_password() 回传；worker 用 Event 等待。
取消：置 _cancel 标志，core 侧 WPS 批处理会立即 terminate 子进程（3.11.4）。
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThread, Signal

from core.runner import run as runner_run
from core.types import MergeConfig, RunSummary


class RunnerWorker(QThread):
    log_signal = Signal(str, str)                  # (level, message)
    progress_signal = Signal(str, int, int, str)   # (kind, done, total, text)
    finished_signal = Signal(object)               # RunSummary | None
    password_requested = Signal(object)            # {"path": Path, "verify": callable}

    def __init__(self, cfg: MergeConfig, parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self._cancel = False
        self._pw_event = threading.Event()
        self._pw_pending = False
        self._pw_result: str | None = None

    # ------------------------------------------------------------ 取消

    def cancel(self) -> None:
        """置取消标志；core 侧 WPS 批处理轮询到后立即 terminate 子进程（3.11.4）。"""
        self._cancel = True
        if self._pw_pending:                 # 密码等待中：直接释放，按跳过处理
            self.submit_password(None)

    # ------------------------------------------------------------ 密码回传

    def submit_password(self, pwd: str | None) -> None:
        """主线程弹窗结束后调用（任意线程安全）。"""
        self._pw_result = pwd
        self._pw_pending = False
        self._pw_event.set()

    def _ask_password(self, path, verify) -> str | None:
        """worker 线程内被 core 回调；等待主线程弹窗结果（可被取消打断）。"""
        if self._pw_pending:
            return None
        self._pw_result = None
        self._pw_pending = True
        self._pw_event.clear()
        self.password_requested.emit({"path": path, "verify": verify})
        while self._pw_pending and not self._cancel:
            self._pw_event.wait(0.1)
        self._pw_pending = False
        return self._pw_result

    # ------------------------------------------------------------ 执行

    def run(self) -> None:                           # QThread 入口（worker 线程）
        t0 = time.time()
        try:
            summary = runner_run(
                self.cfg,
                on_log=lambda level, msg: self.log_signal.emit(level, msg),
                on_progress=lambda k, d, t, x: self.progress_signal.emit(k, d, t, x),
                ask_password=self._ask_password if self.cfg.prompt else None,
                should_cancel=lambda: self._cancel)
            self.log_signal.emit("info", f"总耗时 {time.time() - t0:.1f} 秒")
            self.finished_signal.emit(summary)
        except Exception as exc:                     # 兜底：绝不静默
            self.log_signal.emit("error", f"运行失败：{exc}")
            self.finished_signal.emit(None)