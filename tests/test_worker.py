"""worker 后台执行测试（M3）：取消快速结束、密码弹窗回调流程。"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.worker import RunnerWorker
from core.types import MergeConfig

SAMPLES = Path(__file__).resolve().parent / "samples"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_worker_cancel_quick(qapp, tmp_path):
    """点击取消 → 数秒内结束（3.11.4），无阻塞。"""
    root = tmp_path / "pure"
    shutil.copytree(SAMPLES / "pure_pdf", root)
    cfg = MergeConfig(root=root, output_name="{folder}.pdf", report=False)
    worker = RunnerWorker(cfg)
    loop = QEventLoop()
    result: dict = {"summary": "pending"}
    worker.finished_signal.connect(lambda s: (result.update(summary=s), loop.quit()))
    worker.start()
    QTimer.singleShot(150, worker.cancel)          # 立即取消
    t0 = time.time()
    # 等 worker 真正结束（最多 20 秒）并把队列里的信号处理干净：
    # isFinished() 变 True 时 finished_signal 可能还没被主线程事件循环取走。
    while not worker.isFinished() and time.time() - t0 < 20:
        loop.processEvents()
        time.sleep(0.05)
    assert worker.isFinished(), "取消后未结束（>20s）"
    while result["summary"] == "pending" and time.time() - t0 < 25:
        loop.processEvents()
        time.sleep(0.05)
    elapsed = time.time() - t0
    assert elapsed < 10, f"取消后未快速结束：{elapsed:.1f}s"
    assert result["summary"] != "pending"          # 已完成（正常或异常都算结束）


def test_worker_password_flow(qapp, tmp_path):
    """加密文件：worker 发 password_requested → 主线程回传正确密码 → 合并成功。
    （verify 正确性由 golden 测试覆盖；本测试关注回调流程与最终结果。）"""

    def _run_once():
        root = tmp_path / "enc_flow"
        shutil.copytree(SAMPLES / "encrypted", root)
        cfg = MergeConfig(root=root, output_name="{folder}.pdf", report=False,
                          passwords=[], prompt=True)
        worker = RunnerWorker(cfg)
        loop = QEventLoop()
        result: dict = {"summary": None}
        requested: list = []

        def on_password(payload):
            requested.append(payload["path"].name)
            worker.submit_password("123456")       # 模拟用户输入正确密码

        def on_finished(s):
            result["summary"] = s
            loop.quit()

        worker.password_requested.connect(on_password)
        worker.finished_signal.connect(on_finished)
        worker.start()
        QTimer.singleShot(30000, loop.quit)
        loop.exec()
        # 兜底：finished_signal 可能晚于 30 秒兜底定时器才被事件循环取走
        deadline = time.time() + 15
        while result["summary"] is None and time.time() < deadline:
            loop.processEvents()
            time.sleep(0.05)
        return worker, result, requested

    worker, result, requested = _run_once()
    assert worker.isFinished()
    assert requested == ["加密报告.pdf"]            # 密码请求只针对加密文件
    s = result["summary"]
    assert s is not None, f"worker 未产出结果（密码请求 = {requested}）"
    done = [r for r in s.results if r.done]
    assert done and done[0].pages == 3            # 加密报告 2 页 + 普通材料 1 页


def test_worker_password_skip(qapp, tmp_path):
    """加密无密码（回调返回 None）→ 文件跳过，其余正常合并。"""
    root = tmp_path / "enc2"
    shutil.copytree(SAMPLES / "encrypted", root)
    cfg = MergeConfig(root=root, output_name="{folder}.pdf", report=False,
                      passwords=[], prompt=True)
    worker = RunnerWorker(cfg)
    loop = QEventLoop()
    result: dict = {"summary": None}

    def on_password(payload):
        worker.submit_password(None)               # 模拟用户点击取消（跳过）

    worker.password_requested.connect(on_password)
    worker.finished_signal.connect(lambda s: (result.update(summary=s), loop.quit()))
    worker.start()
    QTimer.singleShot(30000, loop.quit)
    loop.exec()
    s = result["summary"]
    assert s is not None
    done = [r for r in s.results if r.done]
    assert done and done[0].pages == 1            # 仅普通材料 1 页
    assert any("没有可用的打开密码" in f.reason
               for r in s.results for f in r.failures)