"""app/main.py —— 程序入口（单实例 + excepthook + 主窗口）。"""
from __future__ import annotations

import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from app.diagnostics import current_log_file, install_excepthook, setup_file_logging
from app.settings import AppSettings
from app.ui_main import MainWindow

SINGLE_KEY = "A4合并助手_单实例"
SERVER_KEY = "A4合并助手_激活"


class SingleInstance:
    """单实例锁（计划 3.11.8）：第二实例通过 QLocalSocket 通知首实例激活窗口。"""

    def __init__(self) -> None:
        self.mem: QSharedMemory | None = None
        self.server: QLocalServer | None = None

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
    log_file = current_log_file()                     # 先建日志文件
    setup_file_logging(log_file)
    install_excepthook(log_file, dialog=not smoke)    # smoke 模式不弹模态框

    app = QApplication(argv if argv else sys.argv)
    app.setApplicationName("A4合并助手")
    app.setOrganizationName("A4合并助手")

    if smoke:
        # 冒烟模式：启动 1 秒后自动退出（供 CI / 打包后自检）
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, app.quit)
        if not SingleInstance().acquire():
            return 0
        win = MainWindow(AppSettings())
        win.show()
        rc = app.exec()
        return rc

    if not SingleInstance().acquire():
        QMessageBox.information(None, "A4 合并助手", "应用已在运行，已切换到已有窗口。")
        return 0

    win = MainWindow(AppSettings())
    win.show()
    return app.exec()