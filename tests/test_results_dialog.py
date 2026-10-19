"""M4 结果体验测试：完成总结对话框（成功/失败/跳过/忽略、双击定位、TXT 导出）。

全部基于 offscreen 平台；不真的打开资源管理器（monkeypatch reveal_in_explorer）。
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from app import results_dialog as rd
from app.results_dialog import ResultDialog
from core.types import FileFailure, FolderResult, MergeConfig, RunSummary


_APP = None          # 保持 QApplication 引用：被回收会拖垮后续模块的事件循环


@pytest.fixture(scope="module", autouse=True)
def qapp():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    yield _APP


@pytest.fixture()
def revealed(monkeypatch):
    """拦截「打开资源管理器」调用，记录被定位的路径。"""
    calls: list = []
    monkeypatch.setattr(rd, "reveal_in_explorer", lambda p: calls.append(p))
    return calls


def make_pdf(path: Path, pages: int) -> Path:
    """生成只有 blank 页的 PDF 并写到 path（用于真实文件大小）。"""
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=595.276, height=841.89)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        w.write(fh)
    return path


@pytest.fixture()
def scenario(tmp_path: Path):
    """一份典型运行结果：1 成功 + 1 未生成 + 失败/跳过/忽略各若干。"""
    root = tmp_path / "资料"
    (root / "张三").mkdir(parents=True)
    out = make_pdf(root / "张三" / "【合并】张三.pdf", 3)
    report = root / "合并报告.txt"
    report.write_text("报告内容\n", encoding="utf-8-sig")

    cfg = MergeConfig(root=root, report=True)
    ok = FolderResult(folder=root / "张三", label="张三", out_path=out,
                      files_count=2, pages=3, done=True)
    bad = FolderResult(
        folder=root / "李四", label="李四", out_path=root / "李四" / "【合并】李四.pdf",
        files_count=3, pages=0, done=False,
        failures=[
            FileFailure(root / "李四" / "坏报告.pdf", "PDF 已加密，没有可用的打开密码"),
            FileFailure(root / "李四" / "出资证明.docx", "WPS 转换失败（超时）", skipped_pages=2),
        ],
        warnings=["没有任何可合并的页面"],
    )
    look = FolderResult(folder=root / "王五", label="王五",
                        out_path=root / "王五" / "【合并】王五.pdf",
                        files_count=1, pages=1, done=True,
                        lookalikes=[root / "王五" / "王五.pdf"])
    ign = FolderResult(folder=root / "赵六", label="赵六",
                       out_path=root / "赵六" / "【合并】赵六.pdf",
                       files_count=1, pages=1, done=True,
                       ignored=[root / "赵六" / "备注.rar"])
    empty = FolderResult(folder=root / "空目录", label="空目录",
                         out_path=root / "空目录" / "【合并】空目录.pdf", files_count=0)
    summary = RunSummary("2026-10-01 10:00:00", 12.5, {"wps": True, "native": True},
                         cfg, [ok, bad, look, ign, empty], report_path=report)
    return summary


# ------------------------------------------------------------------ 单测

def test_format_size():
    """文件大小文本（B/KB/MB）。"""
    assert rd.format_size(0) == "0 B"
    assert rd.format_size(900) == "900 B"
    assert rd.format_size(2048) == "2 KB"
    assert rd.format_size(3 * 1024 * 1024) == "3.0 MB"
    assert rd.safe_size(Path("__不存在__.pdf")) == "—"


def test_output_dir_for_modes(tmp_path):
    """「打开输出目录」按模式定位：模式B→输出目录，模式A→根目录。"""
    root = tmp_path / "r"
    assert rd.output_dir_for(MergeConfig(root=root)) == root
    out = tmp_path / "结果"
    assert rd.output_dir_for(MergeConfig(root=root, output_dir=out)) == out


# ------------------------------------------------------------------ 对话框

def test_dialog_success_and_counts(qapp, scenario):
    """成功页签：目标/页数/大小/输出路径；标签页计数正确；真实文件大小。"""
    dlg = ResultDialog(scenario, cfg=scenario.config)
    assert dlg.tb_success.rowCount() == 3                       # 王五、赵六 也成功
    assert dlg.tb_success.item(0, 0).text() == "张三"
    assert dlg.tb_success.item(0, 1).text() == "3"
    import re
    assert re.fullmatch(r"\d+(\.\d)? (B|KB|MB)", dlg.tb_success.item(0, 2).text())
    assert dlg.tb_success.item(0, 3).text().endswith("【合并】张三.pdf")
    assert dlg.tabs.tabText(0) == "成功（3）"
    assert dlg.tabs.tabText(1) == "失败（2）"
    assert dlg.tabs.tabText(2) == "跳过的成品（1）"
    assert dlg.tabs.tabText(3) == "忽略的类型（1）"
    assert "成功 3/5 个目标" in dlg.lb_head.text()
    assert "失败 2 个文件" in dlg.lb_head.text()
    # 版面：内容不超出窗口（失败清单里长路径列不撑破版面）
    hint = dlg.minimumSizeHint()
    assert hint.height() <= 620
    dlg.deleteLater()


def test_dialog_failure_tab_and_double_click(qapp, scenario, revealed):
    """失败清单：文件名+原因+跳过页数+完整路径；双击定位；未生成目标也在列。"""
    dlg = ResultDialog(scenario, cfg=scenario.config)
    assert dlg.tb_failures.rowCount() == 3                      # 2 个失败文件 + 1 个未生成目标
    assert dlg.tb_failures.item(0, 1).text() == "坏报告.pdf"
    assert "打开密码" in dlg.tb_failures.item(0, 2).text()
    assert dlg.tb_failures.item(0, 3).text() == "0"
    assert dlg.tb_failures.item(1, 3).text() == "2"             # 跳过的页数
    assert dlg.tb_failures.item(2, 1).text() == "（整个目标）"
    assert "没有任何可合并的页面" in dlg.tb_failures.item(2, 2).text()

    dlg.tb_failures.itemDoubleClicked.emit(dlg.tb_failures.item(0, 0))
    assert len(revealed) == 1
    assert revealed[0].name == "坏报告.pdf"
    assert Path(dlg.tb_failures.item(0, 4).text()).name == "坏报告.pdf"
    dlg.deleteLater()


def test_dialog_lookalike_and_ignored_tabs(qapp, scenario, revealed):
    """跳过成品清单 + 忽略类型清单（含无素材目标），双击可定位。"""
    dlg = ResultDialog(scenario, cfg=scenario.config)
    dlg.tabs.setCurrentIndex(2)
    assert dlg.tb_lookalikes.rowCount() == 1
    assert dlg.tb_lookalikes.item(0, 1).text() == "王五.pdf"
    assert "同名成品" in rd.LOOKALIKE_HINT
    dlg.tb_lookalikes.itemDoubleClicked.emit(dlg.tb_lookalikes.item(0, 0))
    assert revealed and revealed[-1].name == "王五.pdf"

    dlg.tabs.setCurrentIndex(3)
    assert dlg.tb_ignored.rowCount() == 2                       # 1 个忽略文件 + 1 个空目录
    names = [dlg.tb_ignored.item(i, 1).text() for i in range(dlg.tb_ignored.rowCount())]
    assert "备注.rar" in names
    assert "（无素材，未生成）" in names
    dlg.deleteLater()


def test_dialog_empty_lists_hint(qapp, tmp_path):
    """没有任何失败/跳过/忽略时：表格为空，页签显示中文提示，失败导出按钮禁用。"""
    root = tmp_path / "r"
    root.mkdir()
    cfg = MergeConfig(root=root, report=False)
    summary = RunSummary("2026-10-01 10:00:00", 1.0, {"wps": False, "native": True},
                         cfg, [])
    dlg = ResultDialog(summary, cfg=cfg)
    assert dlg.tb_success.rowCount() == 0
    assert dlg.tb_failures.rowCount() == 0
    assert not dlg.btn_export_fail.isEnabled()                  # 没失败 → 无导出必要
    assert not dlg.btn_open_report.isEnabled()                  # 无报告路径 → 禁用
    assert dlg.tabs.tabText(3) == "忽略的类型（0）"
    dlg.deleteLater()


def test_dialog_open_buttons(qapp, scenario, revealed, monkeypatch):
    """打开输出目录（按模式定位）/ 打开运行报告；缺失时中文提示不崩。"""
    warned: list[str] = []
    monkeypatch.setattr(rd.QMessageBox, "information",
                        lambda *a, **k: warned.append(a[2] if len(a) > 2 else ""))
    dlg = ResultDialog(scenario, cfg=scenario.config)
    assert dlg.open_output_dir_target() == scenario.config.root   # 模式A → 根目录
    dlg.btn_open_dir.click()
    assert revealed and revealed[-1] == scenario.config.root

    assert len(revealed) == 1 and revealed[0] == scenario.config.root
    dlg.btn_open_report.click()                                  # 报告存在 → 定位
    assert len(revealed) == 2 and revealed[-1].name == "合并报告.txt"

    # 报告不存在 → 中文提示，不抛异常
    dlg.summary.report_path = scenario.config.root / "不存在.txt"
    dlg.btn_open_report.click()
    assert any("报告文件不存在" in m for m in warned)

    # 输出目录改为模式B 且不存在 → 提示
    dlg.cfg = MergeConfig(root=scenario.config.root,
                          output_dir=scenario.config.root / "还没建")
    dlg.btn_open_dir.click()
    assert any("目录不存在" in m for m in warned)
    dlg.deleteLater()


def test_export_failures_txt(qapp, scenario, tmp_path):
    """失败清单导 TXT：UTF-8-sig 可读，含原因/页数/未生成目标。"""
    dlg = ResultDialog(scenario, cfg=scenario.config)
    out = dlg.export_failures(tmp_path / "失败清单.txt")
    assert out is not None and out.exists()
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                       # UTF-8-sig（记事本可读）
    text = out.read_text(encoding="utf-8-sig")
    assert "A4 合并助手 失败清单" in text
    assert "失败文件：2 个" in text
    assert "坏报告.pdf" in text and "跳过的页数" not in text       # 无页数时不写标记
    assert "出资证明.docx" in text and "（跳过 2 页）" in text
    assert "没有任何可合并的页面" in text
    dlg.deleteLater()


def test_export_summary_txt(qapp, scenario, tmp_path):
    """运行总结导 TXT：成功/失败/跳过/忽略/无素材段齐全。"""
    dlg = ResultDialog(scenario, cfg=scenario.config)
    out = dlg.export_summary(tmp_path / "运行总结.txt")
    text = out.read_text(encoding="utf-8-sig")
    assert "A4 合并助手 运行总结" in text
    assert "成功 3/5 个目标，共 5 页" in text
    assert "【成功列表】" in text and "输出：" in text
    assert "【失败清单】" in text and "【跳过的同名成品 PDF】" in text
    assert "王五.pdf" in text and "备注.rar" in text
    assert "【无素材（未生成）】" in text and "空目录" in text
    dlg.deleteLater()


def test_dry_run_wording(qapp, tmp_path):
    """预览模式：标题写「预览完成（未生成文件）」，大小列显示占位。"""
    root = tmp_path / "r"
    root.mkdir()
    cfg = MergeConfig(root=root, dry_run=True)
    res = FolderResult(folder=root / "甲", label="甲", out_path=root / "甲" / "【合并】甲.pdf",
                       files_count=2, pages=0)
    summary = RunSummary("2026-10-01 10:00:00", 0.5, {"wps": False, "native": True},
                         cfg, [res])
    dlg = ResultDialog(summary, cfg=cfg)
    assert "预览完成（未生成文件）" in dlg.lb_head.text()
    text = rd.build_summary_text(summary)
    assert "（预览模式，未生成文件）" in text
    dlg.deleteLater()


def test_close_button(qapp, scenario):
    """关闭按钮走 reject（不影响主窗口）。"""
    dlg = ResultDialog(scenario, cfg=scenario.config)
    box = dlg.findChild(QDialogButtonBox)
    assert box is not None
    assert box.button(QDialogButtonBox.Close).text() == "关闭"
    box.rejected.emit()
    assert dlg.result() == QDialog.Rejected


# ------------------------------------------------------------------ 主窗口联动

def test_main_window_shows_result_dialog(qapp, scenario, monkeypatch):
    """_on_finished：状态栏更新 + 结果对话框弹出（内容正确、不阻塞）。"""
    from app.ui_main import MainWindow
    win = MainWindow()
    win.smoke = True                                  # 冒烟模式：exec 不阻塞（也断言此行为）
    win._last_cfg = scenario.config
    win._append_log = lambda level, msg: None         # 不写日志文件
    win._on_finished(scenario)
    assert "成功 3/5 个目标" in win.lb_state.text()
    assert win.pb_folder.value() == 1
    dlg = win._result_dialog                          # 对话框已构建并保持引用
    assert dlg is not None and dlg.tb_success.rowCount() == 3
    assert dlg.tb_failures.rowCount() == 3
    win.deleteLater()
    qapp.processEvents()


def test_main_window_finished_none(qapp, monkeypatch):
    """异常结束（summary=None）：中文提示 + 状态栏标红，不弹结果对话框。"""
    from app import ui_main
    from app.ui_main import MainWindow
    warned: list[str] = []
    monkeypatch.setattr(ui_main.QMessageBox, "warning",
                        lambda *a, **k: warned.append(a[2] if len(a) > 2 else ""))
    win = MainWindow()
    win.smoke = True
    win._append_log = lambda level, msg: None
    win._on_finished(None)
    assert any("异常" in m for m in warned)
    assert "异常" in win.lb_state.text()
    win.deleteLater()
    qapp.processEvents()


def test_status_bar_widgets(qapp):
    """状态栏三要素：引擎探测结果 / 任务状态 / 版本号。"""
    from app.ui_main import MainWindow
    from core import __version__
    win = MainWindow()
    assert win.lb_version.text() == f"v{__version__}"
    win._set_state("正在运行…", "busy")
    assert win.lb_state.text() == "正在运行…"
    win._probe_engines()
    assert win.lb_engine.text().startswith("引擎：")
    assert win.statusBar() is not None
    win.deleteLater()
    qapp.processEvents()


def test_end_to_end_real_run_summary(qapp, tmp_path):
    """真实跑一遍 GUI 流程：填目录 → 开始合并 → 结果对话框展示真实页数/体积/输出路径。"""
    import shutil

    from app.ui_main import MainWindow

    root = tmp_path / "pure_pdf"
    shutil.copytree(Path(__file__).resolve().parent / "samples" / "pure_pdf", root)
    win = MainWindow()
    win.smoke = True                                  # 冒烟模式：结果对话框不阻塞 exec
    win.ed_root.setText(str(root))
    win._set_targets_checked(True)
    assert win.lw_targets.count() == 2
    win._start()
    assert win.worker is not None
    assert win.lb_state.text() == "正在运行…"
    deadline = 60
    import time as _t
    t0 = _t.time()
    while (win.worker is not None and not win.worker.isFinished()
           and _t.time() - t0 < deadline):
        qapp.processEvents()
        _t.sleep(0.05)
    assert win.worker is not None and win.worker.isFinished()
    while win._result_dialog is None and _t.time() - t0 < deadline:
        qapp.processEvents()                          # 等 finished_signal 排队投递
        _t.sleep(0.05)

    dlg = win._result_dialog
    assert dlg is not None, "运行结束后没有弹出完成总结对话框"
    assert dlg.tb_success.rowCount() == 2             # 张三 / 李四
    assert all(dlg.tb_success.item(i, 3).text().endswith(".pdf")
               for i in range(dlg.tb_success.rowCount()))
    assert all(dlg.tb_success.item(i, 2).text() not in ("—", "—（预览）")
               for i in range(dlg.tb_success.rowCount()))
    assert all(int(dlg.tb_success.item(i, 1).text()) > 0
               for i in range(dlg.tb_success.rowCount()))
    assert dlg.tb_failures.rowCount() == 0
    assert dlg.open_output_dir_target() == root
    assert dlg._report_path() is not None and dlg._report_path().exists()
    assert "成功 2/2 个目标" in win.lb_state.text()
    win.deleteLater()
    qapp.processEvents()


# ------------------------------------------------------------ 遇到 Excel 跳过

@pytest.fixture()
def scenario_skip_excel(tmp_path: Path):
    """启用「遇到 Excel 跳过」后的结果：1 个正常目标 + 1 个只剩 Excel 的目标。"""
    root = tmp_path / "资料"
    (root / "张三").mkdir(parents=True)
    out = make_pdf(root / "张三" / "【合并】张三.pdf", 2)
    cfg = MergeConfig(root=root, report=False, skip_excel=True)
    ok = FolderResult(folder=root / "张三", label="张三", out_path=out,
                      files_count=2, pages=2, done=True,
                      skipped_excel=[root / "张三" / "出资证明.xlsx"])
    only_excel = FolderResult(folder=root / "王五", label="王五",
                              out_path=root / "王五" / "【合并】王五.pdf",
                              files_count=0, pages=0,
                              skipped_excel=[root / "王五" / "明细.xls",
                                             root / "王五" / "流水.xlsx"])
    return RunSummary("2026-10-01 10:05:00", 3.0, {"wps": True, "native": True},
                      cfg, [ok, only_excel], report_path=None)


def test_dialog_skip_excel_tab(qapp, scenario_skip_excel, revealed):
    """启用选项后多出「跳过的 Excel」页签：逐行列清单，双击可定位，不计失败。"""
    dlg = ResultDialog(scenario_skip_excel, cfg=scenario_skip_excel.config)
    assert dlg.tabs.count() == 5
    assert dlg.tabs.tabText(3) == "跳过的 Excel（3）"
    assert dlg.tb_skipped_excel.rowCount() == 3
    assert dlg.tb_skipped_excel.item(0, 1).text() == "出资证明.xlsx"
    assert dlg.tb_skipped_excel.item(1, 1).text() == "明细.xls"
    assert dlg.tb_failures.rowCount() == 0                    # 跳过不计失败
    assert "跳过 Excel 3 个" in dlg.lb_head.text()
    dlg.tb_skipped_excel.itemDoubleClicked.emit(dlg.tb_skipped_excel.item(0, 1))
    assert revealed and revealed[0].name == "出资证明.xlsx"

    text = rd.build_summary_text(scenario_skip_excel)
    assert "遇到 Excel：跳过" in text
    assert "【跳过的 Excel（遇到 Excel 跳过）】" in text
    assert "出资证明.xlsx" in text and "明细.xls" in text
    assert rd.SKIP_EXCEL_HINT in text
    dlg.deleteLater()


def test_dialog_skip_excel_tab_absent_by_default(qapp, scenario):
    """默认关闭时不新增页签（仍是四个页签），文本说明未启用该选项。"""
    dlg = ResultDialog(scenario, cfg=scenario.config)
    assert dlg.tabs.count() == 4
    assert dlg.tb_skipped_excel is None
    assert dlg.tabs.tabText(3) == "忽略的类型（1）"
    text = rd.build_summary_text(scenario)
    assert "遇到 Excel：正常处理" in text
    assert rd.NO_SKIP_EXCEL_HINT in text
    dlg.deleteLater()


def test_empty_folder_reason_counts_skipped_excel(tmp_path):
    """只剩 Excel 的目标：忽略页签原因写「N 个 Excel 已跳过」，导出文本同步。"""
    root = tmp_path / "资料"
    e = FolderResult(folder=root / "空", label="空",
                     out_path=root / "空" / "【合并】空.pdf", files_count=0,
                     skipped_excel=[root / "空" / "a.xlsx", root / "空" / "b.xlsx"])
    assert rd._empty_reason(e) == "（2 个 Excel 已跳过，无其它素材）"
    assert rd._empty_reason(FolderResult(folder=root / "空2", label="空2",
                                        out_path=root / "空2" / "【合并】空2.pdf",
                                        files_count=0)) == "（无素材，未生成）"
    cfg = MergeConfig(root=root, skip_excel=True)
    txt = rd.build_failures_text(RunSummary("t", 1.0, {}, cfg, [e]))
    assert "2 个 Excel 已跳过" in txt
