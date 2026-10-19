"""app/main.py —— 程序入口（单实例 + excepthook + 主窗口）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSharedMemory
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from app.diagnostics import current_log_file, install_excepthook, setup_file_logging
from app.icon import app_icon
from app.settings import AppSettings
from app.ui_main import MainWindow

SINGLE_KEY = "A4合并助手_单实例"
SERVER_KEY = "A4合并助手_激活"


class SingleInstance:
    """单实例锁（计划 3.11.8）：第二实例通过 QLocalSocket 通知首实例激活窗口。"""

    def __init__(self) -> None:
        self.mem: QSharedMemory | None = None
        self.server: QLocalServer | None = None

    def release(self) -> None:
        """显式释放共享内存与本地服务（退出前调用，避免退出期的资源析构竞争）。"""
        try:
            if self.server is not None:
                self.server.close()
                self.server = None
        except Exception:
            pass
        try:
            if self.mem is not None:
                self.mem.detach()
                self.mem = None
        except Exception:
            pass

    def acquire(self) -> bool:
        mem = QSharedMemory(SINGLE_KEY)
        if mem.attach():                 # 已有实例持有
            # 通知首实例把窗口带到前台
            sock = QLocalSocket()
            sock.connectToServer(SERVER_KEY)
            if sock.waitForConnected(300):
                sock.write(b"show")
                sock.waitForBytesWritten(300)
            sock.disconnectFromServer()
            return False
        if not mem.create(1):
            return False
        self.mem = mem                   # 保持引用直到进程退出
        self.server = QLocalServer()
        self.server.removeServer(SERVER_KEY)
        self.server.listen(SERVER_KEY)
        self.server.newConnection.connect(self._on_connection)
        return True

    def _on_connection(self) -> None:
        conn = self.server.nextPendingConnection()
        if conn is not None:
            conn.readAll()
            conn.disconnectFromServer()
            for w in QApplication.topLevelWidgets():
                if isinstance(w, MainWindow):
                    w.showNormal()
                    w.raise_()
                    w.activateWindow()
                    break


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv)
    smoke = "--smoke" in argv
    if smoke:
        argv.remove("--smoke")
    auto_run = "--auto-run" in argv                  # 打包验收：自动跑一次合并
    if auto_run:
        argv.remove("--auto-run")
    auto = auto_run and os.environ.get("A4_AUTOMATION") == "1"
    if auto:
        # 自动验收用独立的设置文件：不受本机残留设置影响，也不写脏真实设置
        os.environ.setdefault("A4_SETTINGS_DIR",
                              str(Path(os.environ.get("A4_AUTOMATION_DIR", "."))
                                  / "验收设置"))
    smoke_wait_ms = 1000                              # 冒烟自检存活时长（打包冒烟用）
    for arg in list(argv):
        if arg.startswith("--smoke-wait="):
            argv.remove(arg)
            smoke_wait_ms = max(500, int(arg.split("=", 1)[1]))
    log_file = current_log_file()                     # 先建日志文件
    setup_file_logging(log_file)
    install_excepthook(log_file, dialog=not smoke)    # smoke 模式不弹模态框

    app = QApplication(argv if argv else sys.argv)
    app.setApplicationName("A4合并助手")
    app.setOrganizationName("A4合并助手")
    # 应用图标（标题栏 + 任务栏）：必须在 QApplication 之后构造 QIcon；
    # 打包版与 exe 的 PE 图标同源（assets/app.ico），窗口图标缺失时退回系统默认。
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    single = SingleInstance()
    if smoke:
        from PySide6.QtCore import QTimer
        if not single.acquire():
            return _finish(0, single)
        win = MainWindow(AppSettings())
        win.show()
        if auto:
            # 自动化验收：由 _schedule_automation 自己的超时定时器收尾，
            # 不再挂「1 秒即退」的冒烟定时器（否则任务会被提前打断）。
            _schedule_automation(win, app)
            return _finish(app.exec(), single)
        # 冒烟模式：启动 1 秒后自动退出（供 CI / 打包后自检；可用 --smoke-wait=毫秒 调整）
        QTimer.singleShot(smoke_wait_ms, app.quit)
        return _finish(app.exec(), single)

    if not single.acquire():
        QMessageBox.information(None, "A4 合并助手", "应用已在运行，已切换到已有窗口。")
        return _finish(0, single)

    win = MainWindow(AppSettings())
    win.show()
    if auto:
        _schedule_automation(win, app)
    return _finish(app.exec(), single)


def _finish(rc: int, single: SingleInstance) -> int:
    """退出前的收尾：显式释放单实例锁并冲净日志。

    打包版另外**跳过的解释器终结阶段**（os._exit）：PyInstaller onefile 下
    Python 终结 + Qt 插件卸载存在偶发崩溃（0xC0000409），而这是无人值守的自检路径，
    直接按返回码退出更可靠；开发模式仍走正常返回，便于测试与调试。
    """
    single.release()
    try:
        import logging
        logging.shutdown()
    except Exception:
        pass
    if getattr(sys, "frozen", False) and os.environ.get("A4_NO_HARD_EXIT") != "1":
        sys.stdout.flush() if sys.stdout else None
        sys.stderr.flush() if sys.stderr else None
        os._exit(rc)
    return rc


def _schedule_automation(win, app) -> None:
    """打包验收专用：自动填根目录 → 开始合并 → 写结果文件 → 自动退出。

    仅在环境变量 A4_AUTOMATION=1 且传入 --auto-run 时启用，正常使用完全不受影响。
    """
    import json
    import time as _time
    from pathlib import Path

    from PySide6.QtCore import QTimer

    report_path = Path(os.environ.get("A4_AUTOMATION_REPORT",
                                      str(Path.cwd() / "自动化验收结果.json")))
    root = os.environ.get("A4_AUTOMATION_ROOT", "")
    out_dir = os.environ.get("A4_AUTOMATION_OUTDIR", "")
    engine = os.environ.get("A4_AUTOMATION_ENGINE", "")      # auto/wps/native
    timeout_s = float(os.environ.get("A4_AUTOMATION_TIMEOUT", "300"))
    state = {"t0": _time.time(), "written": False, "dep_probe": "", "imports": {},
             "finished_at": 0.0, "started": False}

    def write(result: dict) -> None:
        """写出验收结果（只写一次）并记录收工时刻，由 watchdog 负责退出。"""
        if state["written"]:
            return
        state["written"] = True
        state["finished_at"] = _time.time()          # 无论成功/失败都要记，否则永不退出
        result["elapsed"] = round(state["finished_at"] - state["t0"], 1)
        result.setdefault("frozen_dep_probe", state["dep_probe"])
        result.setdefault("imports", state["imports"])
        try:
            report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        except Exception:
            pass

    def watchdog() -> None:
        """每 0.5 秒巡检：结果写出后宽限 3 秒收工；任务一直不结束则按超时收工。

        冒烟模式初始会挂「即退」定时器，因此自动验收以「结果已写 + 宽限」作为
        唯一退出条件；本函数自己重排下一次巡检（注意必须在本函数定义之后注册首次调用）。
        """
        now = _time.time()
        if os.environ.get("A4_AUTOMATION_TRACE"):
            with open(os.environ["A4_AUTOMATION_TRACE"], "a", encoding="utf-8") as fh:
                fh.write(f"tick t={now - state['t0']:.2f} written={state['written']} "
                         f"fin={state['finished_at']:.1f} "
                         f"summary={win._last_summary is not None}\n")
        if not state["written"]:
            if state["started"] and win._last_summary is not None:
                on_done()                                  # 任务已结束：记录结果
            elif state["started"] and now - state["t0"] > timeout_s:
                write({"error": "自动化验收超时（%.0f 秒）" % timeout_s,
                       "state_text": win.lb_state.text()})
        elif now - state["finished_at"] > 3:
            app.quit()
            return
        QTimer.singleShot(500, watchdog)

    def on_done(*_a) -> None:
        summary = win._last_summary
        dlg = win._result_dialog
        result: dict = {"ok": True,
                        "state_text": win.lb_state.text(),
                        "engine_text": win.lb_engine.text(),
                        "longpath_text": win.lb_longpath.text(),
                        "dialog": None}
        if summary is not None:
            result["targets"] = len(summary.results)
            result["pages"] = sum(r.pages for r in summary.results)
            result["skip_excel"] = bool(getattr(summary.config, "skip_excel", False))
            result["skipped_excel"] = [str(p) for r in summary.results
                                       for p in (r.skipped_excel or [])]
            result["report_path"] = str(summary.report_path or "")
            result["outputs"] = [
                {"label": r.label, "out": str(r.out_path), "pages": r.pages,
                 "done": r.done, "size": (r.out_path.stat().st_size
                                          if r.out_path and r.out_path.exists() else 0)}
                for r in summary.results]
            result["failures"] = [{"file": str(f.path), "reason": f.reason}
                                  for r in summary.results for f in r.failures]
        if dlg is not None:
            result["dialog"] = {
                "title": dlg.windowTitle(),
                "head": dlg.lb_head.text(),
                "success_rows": dlg.tb_success.rowCount(),
                "failure_rows": dlg.tb_failures.rowCount(),
                "lookalike_rows": dlg.tb_lookalikes.rowCount(),
                "skipped_excel_rows": (dlg.tb_skipped_excel.rowCount()
                                       if dlg.tb_skipped_excel is not None else 0),
                "ignored_rows": dlg.tb_ignored.rowCount(),
                "export_fail_enabled": dlg.btn_export_fail.isEnabled(),
                "export_all_enabled": dlg.btn_export_all.isEnabled(),
                "open_dir": str(dlg.open_output_dir_target()),
                "report": str(dlg._report_path() or ""),
            }
        state["finished_at"] = _time.time()
        write(result)

    def probe_frozen_deps() -> str:
        """打包版依赖自检：走 core/deps.py 的 frozen 分支（计划 3.8.3）。
        正常返回空串；组件缺失时返回中文报错原文（M5 验收要求验证"绝不触发 pip"）。"""
        from core.deps import ensure_module
        try:
            ensure_module("a4merger_不存在的组件_自检用", "a4merger-not-exist")
            return "（自检异常：缺失组件竟然通过了）"
        except RuntimeError as exc:
            return str(exc)
        except Exception as exc:                       # ImportError 等非预期路径
            return f"（非预期异常：{type(exc).__name__}: {exc}）"

    def probe_engine_imports() -> dict:
        """逐个 import 关键库，把失败原因落进验收报告（打包排障）。"""
        import traceback
        out: dict = {}
        for name in ("PIL", "PIL.Image", "PIL.ImageOps", "fpdf", "pypdf",
                     "msoffcrypto"):
            try:
                __import__(name)
                out[name] = "ok"
            except Exception as exc:
                out[name] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        return out

    def kick() -> None:
        if not root:
            write({"error": "未设置 A4_AUTOMATION_ROOT"})
            return
        win.ed_root.setText(root)
        if out_dir:
            win.ra_mode_b.setChecked(True)
            win.ed_outdir.setText(out_dir)
        level = os.environ.get("A4_AUTOMATION_LEVEL", "")       # 0/1/2（可空＝默认）
        if level:
            from app.ui_main import _level_index
            try:
                win.cb_level.setCurrentIndex(_level_index(int(level)))
            except ValueError:
                pass
        if engine:
            from app.ui_main import ENGINE_MAP
            for idx, (label, value) in enumerate(ENGINE_MAP.items()):
                if value == engine:
                    win.cb_engine.setCurrentIndex(idx)
                    break
            if ENGINE_MAP.get(win.cb_engine.currentText()) != engine:
                win.cb_engine.setCurrentText(
                    next(k for k, v in ENGINE_MAP.items() if v == engine))
        if os.environ.get("A4_AUTOMATION_SKIP_EXCEL") == "1":
            win.cb_skip_excel.setChecked(True)       # 自动验收：勾选「遇到 Excel 跳过」
        win._set_targets_checked(True)
        state["dep_probe"] = probe_frozen_deps()
        state["imports"] = probe_engine_imports()
        if win.lw_targets.count() == 0:
            write({"error": "目标文件夹为空（根目录或级别不对）"})
            return
        original_start = win._start

        def start_and_hook() -> None:
            original_start()                     # 内部建 worker 并 start()
            if win.worker is not None:
                win.worker.finished_signal.connect(on_done)
            else:                                # 配置校验未通过：磁盘上留证
                write({"error": "启动被拦截（请检查根目录/输出目录/模板）",
                       "state_text": win.lb_state.text()})

        win._start = start_and_hook
        start_and_hook()
        state["started"] = True

    QTimer.singleShot(700, kick)
    QTimer.singleShot(500, watchdog)      # 注意：必须在 watchdog 定义之后注册