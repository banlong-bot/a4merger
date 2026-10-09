"""app/results_dialog.py —— 运行结果总结对话框（M4 结果体验）。

内容（计划 2.2「完成总结对话框」）：
  · 成功列表：目标（文件夹）→ 页数 → 文件大小 → 输出路径；
  · 失败清单：文件名 + 原因 + 跳过页数，双击在资源管理器中定位；
  · 被跳过的「同名成品 PDF」清单（提示如何包含）；
  · 忽略的不支持类型清单；
  · 按钮：打开输出目录（按当前模式定位）、打开运行报告、导出失败清单 TXT、
    导出运行总结 TXT、关闭。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox,
                               QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from core import __version__
from core.types import MergeConfig, RunSummary

# 失败清单导出的段落标题（同时用于 TXT 导出；与本模块标签一致）
NO_LOOKALIKE_HINT = "本次没有跳过「与所在文件夹同名」的 PDF。"
LOOKALIKE_HINT = "这些文件默认被视为上次生成的成品而没有并入；如需并入，请勾选「同名成品」后重跑。"
NO_IGNORED_HINT = "本次没有被忽略的文件（不支持的类型会被忽略，旧成品 PDF 会被跳过）。"
IGNORED_HINT = "这些类型不在支持范围内，未参与合并。"


# ------------------------------------------------------------------ 工具函数

def format_size(size_bytes: float) -> str:
    """人类可读的字节数（中文单位）。"""
    n = float(size_bytes)
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f} {unit}" if unit != "MB" else f"{n:.1f} MB"
        n /= 1024
    return f"{n:.1f} MB"


def safe_size(path: Path | None) -> str:
    """文件大小文本；文件不存在（预览/失败）返回「—」，绝不抛异常。"""
    if path is None:
        return "—"
    try:
        st = os.stat(path)
    except OSError:
        return "—"
    return format_size(st.st_size)


def reveal_in_explorer(path: Path | None) -> None:
    """在资源管理器中定位文件/文件夹（双击定位用）。失败时静默。"""
    if path is None:
        return
    p = Path(path)
    try:
        if p.is_dir():
            os.startfile(str(p))                     # noqa: S606 —— 打开文件夹
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)])   # 选中该文件
        elif p.parent.is_dir():
            os.startfile(str(p.parent))              # noqa: S606
    except Exception:
        pass


def output_dir_for(cfg: MergeConfig) -> Path | None:
    """「打开输出目录」的目标：按当前模式定位（模式B→输出目录；模式A→根目录）。"""
    if cfg.output_dir is not None:
        return Path(cfg.output_dir)
    return Path(cfg.root) if cfg.root is not None else None


def _fmt_sec(sec: float) -> str:
    return f"{sec:.1f} 秒"


def _counts(summary: RunSummary) -> dict:
    results = summary.results
    done = [r for r in results if r.done]
    failures = [(r, f) for r in results for f in r.failures]
    lookalikes = [(r, p) for r in results for p in r.lookalikes]
    ignored = [(r, p) for r in results for p in r.ignored]
    return {
        "done": done,
        "failures": failures,
        "lookalikes": lookalikes,
        "ignored": ignored,
        "failed_folders": [r for r in results if r.files_count and not r.done],
        "empty_folders": [r for r in results if not r.files_count],
        "pages": sum(r.pages for r in results),
    }


def build_failures_text(summary: RunSummary) -> str:
    """失败清单 TXT 内容（UTF-8-sig 写出后记事本直接可读）。"""
    c = _counts(summary)
    lines = [
        "=" * 60,
        "A4 合并助手 失败清单",
        "=" * 60,
        f"应用版本：{__version__}    运行时间：{summary.started}",
        f"根目录　：{summary.config.root}",
        f"失败文件：{len(c['failures'])} 个    未生成目标：{len(c['failed_folders'])} 个",
        "",
    ]
    index = 0
    for r in summary.results:
        if not r.failures and r.done:
            continue
        head = f"【{r.label}】" + ("" if r.files_count else "（无素材，未生成）")
        lines.append(head)
        for f in r.failures:
            index += 1
            page = f"（跳过 {f.skipped_pages} 页）" if f.skipped_pages else ""
            lines.append(f"  {index}. {f.path}")
            lines.append(f"     原因：{f.reason}{page}")
        for w in r.warnings:
            lines.append(f"  · 提示：{w}")
        if not r.failures:
            lines.append("  （本目标没有失败文件）")
        lines.append("")
    if index == 0:
        lines.append("（本次没有失败文件）")
        lines.append("")
    return "\n".join(lines)


def build_summary_text(summary: RunSummary) -> str:
    """运行总结 TXT 内容（成功/失败/跳过/忽略 全量）。"""
    cfg = summary.config
    c = _counts(summary)
    mode = "B：统一输出目录" if cfg.output_dir is not None else "A：各子文件夹内"
    lines = [
        "=" * 60,
        "A4 合并助手 运行总结",
        "=" * 60,
        f"应用版本：{__version__}    运行时间：{summary.started}    总耗时：{_fmt_sec(summary.elapsed)}",
        f"根目录　：{cfg.root}",
        f"输出模式：{mode}" + (f" → {cfg.output_dir}" if cfg.output_dir else ""),
        f"文件名模板：{cfg.output_name}",
        f"结果　　：成功 {len(c['done'])}/{len(summary.results)} 个目标，共 {c['pages']} 页"
        + ("（预览模式，未生成文件）" if cfg.dry_run else ""),
        "",
        "【成功列表】",
    ]
    if c["done"]:
        for r in c["done"]:
            size = safe_size(r.out_path) if not cfg.dry_run else "—（预览）"
            lines.append(f"  ✔ {r.label}    页数 {r.pages}    大小 {size}")
            lines.append(f"      输出：{r.out_path}")
    else:
        lines.append("  （无）")
    lines.append("")
    lines.append("【失败清单】")
    if c["failures"]:
        for i, (_r, f) in enumerate(c["failures"], 1):
            page = f"（跳过 {f.skipped_pages} 页）" if f.skipped_pages else ""
            lines.append(f"  {i}. {f.path}    —— {f.reason}{page}")
    else:
        lines.append("  （无）")
    if c["failed_folders"]:
        lines.append("【未生成的目标文件夹】")
        for r in c["failed_folders"]:
            why = "；".join(r.warnings) or "没有可合并的页面"
            lines.append(f"  · {r.label}（{r.files_count} 个素材）—— {why}")
    lines.append("")
    lines.append("【跳过的同名成品 PDF】")
    if c["lookalikes"]:
        for r, p in c["lookalikes"]:
            lines.append(f"  · {r.label} → {p.name}")
        lines.append(f"  {LOOKALIKE_HINT}")
    else:
        lines.append(f"  {NO_LOOKALIKE_HINT}")
    lines.append("")
    lines.append("【忽略的文件类型】")
    if c["ignored"]:
        for r, p in c["ignored"]:
            lines.append(f"  · {r.label} → {p.name}")
        lines.append(f"  {IGNORED_HINT}")
    else:
        lines.append(f"  {NO_IGNORED_HINT}")
    lines.append("")
    if c["empty_folders"]:
        lines.append("【无素材（未生成）】")
        for r in c["empty_folders"]:
            lines.append(f"  ○ {r.label}")
        lines.append("")
    return "\n".join(lines)


def _make_table(headers: list[str], stretch_col: int) -> QTableWidget:
    tb = QTableWidget(0, len(headers))
    tb.setHorizontalHeaderLabels(headers)
    tb.verticalHeader().setVisible(False)
    tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tb.setSelectionBehavior(QAbstractItemView.SelectRows)
    tb.setSelectionMode(QAbstractItemView.ExtendedSelection)
    tb.setAlternatingRowColors(True)
    hh = tb.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeToContents)
    hh.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    return tb


def _cell(text: str, tip: str = "") -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setToolTip(tip or text)
    return it


def _hint_label(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setWordWrap(True)
    lb.setStyleSheet("color:#555555;")
    return lb


# ------------------------------------------------------------------ 对话框

class ResultDialog(QDialog):
    """运行结果总结对话框。"""

    def __init__(self, summary: RunSummary, cfg: MergeConfig | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.summary = summary
        self.cfg = cfg or summary.config
        self.counts = _counts(summary)
        self.setWindowTitle("运行结果")
        self.resize(1120, 640)
        self._build_ui()

    # ------------------------------------------------------------ 构建

    def _build_ui(self) -> None:
        cfg, c = self.cfg, self.counts
        lay = QVBoxLayout(self)

        head = ("预览完成（未生成文件）：" if cfg.dry_run else "处理完成：") + \
               f"成功 {len(c['done'])}/{len(self.summary.results)} 个目标，" + \
               f"共 {c['pages']} 页，失败 {len(c['failures'])} 个文件，" + \
               f"耗时 {_fmt_sec(self.summary.elapsed)}"
        self.lb_head = QLabel(head)
        self.lb_head.setStyleSheet("font-size:11pt;font-weight:bold;")
        lay.addWidget(self.lb_head)

        root_hint = QLabel(f"根目录：{cfg.root}" +
                           (f"　　输出目录：{cfg.output_dir}" if cfg.output_dir else ""))
        root_hint.setStyleSheet("color:#555555;")
        lay.addWidget(root_hint)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._tab_success(), f"成功（{len(c['done'])}）")
        self.tabs.addTab(self._tab_failures(), f"失败（{len(c['failures'])}）")
        self.tabs.addTab(self._tab_lookalikes(), f"跳过的成品（{len(c['lookalikes'])}）")
        self.tabs.addTab(self._tab_ignored(), f"忽略的类型（{len(c['ignored'])}）")
        lay.addWidget(self.tabs, 1)

        # ---- 按钮行
        row = QHBoxLayout()
        self.btn_open_dir = QPushButton("打开输出目录")
        self.btn_open_dir.setToolTip(
            "模式B：打开统一输出目录\n模式A：打开根目录（成品分散在各子文件夹内）")
        self.btn_open_report = QPushButton("打开运行报告")
        self.btn_open_report.setEnabled(self._report_path() is not None)
        self.btn_export_fail = QPushButton("导出失败清单 TXT…")
        self.btn_export_fail.setEnabled(bool(c["failures"]) or bool(c["failed_folders"]))
        self.btn_export_all = QPushButton("导出运行总结 TXT…")
        row.addWidget(self.btn_open_dir)
        row.addWidget(self.btn_open_report)
        row.addStretch(1)
        row.addWidget(self.btn_export_fail)
        row.addWidget(self.btn_export_all)
        lay.addLayout(row)

        bb = QDialogButtonBox(QDialogButtonBox.Close, self)
        bb.button(QDialogButtonBox.Close).setText("关闭")
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.btn_open_dir.clicked.connect(self._open_output_dir)
        self.btn_open_report.clicked.connect(self._open_report)
        self.btn_export_fail.clicked.connect(self.export_failures)
        self.btn_export_all.clicked.connect(self.export_summary)

    def _tab_success(self) -> QWidget:
        cfg = self.cfg
        w = QWidget()
        v = QVBoxLayout(w)
        self.tb_success = _make_table(
            ["目标文件夹", "页数", "文件大小", "输出路径"], stretch_col=3)
        self.tb_success.itemDoubleClicked.connect(
            lambda item: reveal_in_explorer(self._success_path(item.row())))
        self._success_rows: list[Path | None] = []
        for r in self.counts["done"]:
            row = self.tb_success.rowCount()
            self.tb_success.insertRow(row)
            self.tb_success.setItem(row, 0, _cell(r.label))
            self.tb_success.setItem(row, 1, _cell(str(r.pages)))
            size = "—（预览）" if cfg.dry_run else safe_size(r.out_path)
            self.tb_success.setItem(row, 2, _cell(size))
            self.tb_success.setItem(row, 3, _cell(str(r.out_path) if r.out_path else "—",
                                                  f"双击定位：{r.out_path}"))
            self._success_rows.append(r.out_path)
        v.addWidget(self.tb_success, 1)
        v.addWidget(_hint_label("提示：双击一行可在资源管理器中定位成品；"
                                "「文件大小」为生成的 PDF 体积。"))
        return w

    def _tab_failures(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.tb_failures = _make_table(
            ["目标文件夹", "文件", "原因", "跳过页数", "完整路径"], stretch_col=4)
        self.tb_failures.itemDoubleClicked.connect(self._reveal_failure)
        self._failure_rows: list[Path] = []
        for r, f in self.counts["failures"]:
            row = self.tb_failures.rowCount()
            self.tb_failures.insertRow(row)
            self.tb_failures.setItem(row, 0, _cell(r.label))
            self.tb_failures.setItem(row, 1, _cell(f.path.name))
            self.tb_failures.setItem(row, 2, _cell(f.reason))
            self.tb_failures.setItem(row, 3, _cell(str(f.skipped_pages)))
            self.tb_failures.setItem(row, 4, _cell(str(f.path), f"双击定位：{f.path}"))
            self._failure_rows.append(f.path)
        # 未生成的目标文件夹（有素材但一页都没出来）
        for r in self.counts["failed_folders"]:
            row = self.tb_failures.rowCount()
            self.tb_failures.insertRow(row)
            why = "；".join(r.warnings) or "没有可合并的页面"
            self.tb_failures.setItem(row, 0, _cell(r.label))
            self.tb_failures.setItem(row, 1, _cell("（整个目标）"))
            self.tb_failures.setItem(row, 2, _cell(why))
            self.tb_failures.setItem(row, 3, _cell("0"))
            self.tb_failures.setItem(row, 4, _cell(str(r.folder), f"双击定位：{r.folder}"))
            self._failure_rows.append(r.folder)
        v.addWidget(self.tb_failures, 1)
        v.addWidget(_hint_label("提示：双击一行可在资源管理器中定位该文件；"
                                "单个文件失败不影响其它文件与其它目标。"))
        return w

    def _tab_lookalikes(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.tb_lookalikes = _make_table(["目标文件夹", "被跳过的 PDF", "完整路径"],
                                         stretch_col=2)
        self.tb_lookalikes.itemDoubleClicked.connect(
            lambda item: reveal_in_explorer(self._lookalike_path(item.row())))
        self._lookalike_rows: list[Path] = []
        for r, p in self.counts["lookalikes"]:
            row = self.tb_lookalikes.rowCount()
            self.tb_lookalikes.insertRow(row)
            self.tb_lookalikes.setItem(row, 0, _cell(r.label))
            self.tb_lookalikes.setItem(row, 1, _cell(p.name))
            self.tb_lookalikes.setItem(row, 2, _cell(str(p), f"双击定位：{p}"))
            self._lookalike_rows.append(p)
        v.addWidget(self.tb_lookalikes, 1)
        v.addWidget(_hint_label(LOOKALIKE_HINT if self.counts["lookalikes"]
                                else NO_LOOKALIKE_HINT))
        return w

    def _tab_ignored(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.tb_ignored = _make_table(["目标文件夹", "被忽略的文件", "完整路径"],
                                      stretch_col=2)
        self.tb_ignored.itemDoubleClicked.connect(
            lambda item: reveal_in_explorer(self._ignored_path(item.row())))
        self._ignored_rows: list[Path] = []
        for r, p in self.counts["ignored"]:
            row = self.tb_ignored.rowCount()
            self.tb_ignored.insertRow(row)
            self.tb_ignored.setItem(row, 0, _cell(r.label))
            self.tb_ignored.setItem(row, 1, _cell(p.name))
            self.tb_ignored.setItem(row, 2, _cell(str(p), f"双击定位：{p}"))
            self._ignored_rows.append(p)
        # 无素材的目标文件夹也列在这里（用户最关心"为什么没生成"）
        for r in self.counts["empty_folders"]:
            row = self.tb_ignored.rowCount()
            self.tb_ignored.insertRow(row)
            self.tb_ignored.setItem(row, 0, _cell(r.label))
            self.tb_ignored.setItem(row, 1, _cell("（无素材，未生成）"))
            self.tb_ignored.setItem(row, 2, _cell(str(r.folder), f"双击定位：{r.folder}"))
        v.addWidget(self.tb_ignored, 1)
        v.addWidget(_hint_label(IGNORED_HINT if self.counts["ignored"]
                                else NO_IGNORED_HINT))
        return w

    # ------------------------------------------------------------ 辅助

    def _success_path(self, row: int) -> Path | None:
        return self._success_rows[row] if 0 <= row < len(self._success_rows) else None

    def _reveal_failure(self, item) -> None:
        if 0 <= item.row() < len(self._failure_rows):
            reveal_in_explorer(self._failure_rows[item.row()])

    def _lookalike_path(self, row: int) -> Path | None:
        return self._lookalike_rows[row] if 0 <= row < len(self._lookalike_rows) else None

    def _ignored_path(self, row: int) -> Path | None:
        return self._ignored_rows[row] if 0 <= row < len(self._ignored_rows) else None

    def _report_path(self) -> Path | None:
        p = self.summary.report_path
        return Path(p) if p else None

    def open_output_dir_target(self) -> Path | None:
        """「打开输出目录」将要打开的路径（按当前模式定位）。"""
        return output_dir_for(self.cfg)

    # ------------------------------------------------------------ 动作

    def _open_output_dir(self) -> None:
        target = self.open_output_dir_target()
        if target is None:
            QMessageBox.information(self, "提示", "没有可打开的输出目录。")
            return
        if not Path(target).exists():
            QMessageBox.information(self, "提示", f"目录不存在（预览模式可能尚未创建）：\n{target}")
            return
        reveal_in_explorer(target)

    def _open_report(self) -> None:
        p = self._report_path()
        if p is None:
            QMessageBox.information(self, "提示", "本次运行没有生成报告（可能未勾选「生成运行报告」。）")
            return
        if not p.exists():
            QMessageBox.information(self, "提示", f"报告文件不存在：\n{p}")
            return
        reveal_in_explorer(p)

    def _save_text(self, default_name: str, text: str) -> Path | None:
        f, _ = QFileDialog.getSaveFileName(self, "导出 TXT", str(default_name),
                                           "文本文件 (*.txt)")
        if not f:
            return None
        path = Path(f)
        if path.suffix.lower() != ".txt":
            path = path.with_suffix(".txt")
        path.write_text(text, encoding="utf-8-sig")      # 记事本直接可读
        QMessageBox.information(self, "导出成功", f"已保存：\n{path}")
        return path

    def export_failures(self, path: Path | None = None) -> Path | None:
        """导出失败清单 TXT（GUI 走文件对话框；测试可直接传路径）。"""
        text = build_failures_text(self.summary)
        if path is not None:
            Path(path).write_text(text, encoding="utf-8-sig")
            return Path(path)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        return self._save_text(f"失败清单_{stamp}.txt", text)

    def export_summary(self, path: Path | None = None) -> Path | None:
        """导出运行总结 TXT（GUI 走文件对话框；测试可直接传路径）。"""
        text = build_summary_text(self.summary)
        if path is not None:
            Path(path).write_text(text, encoding="utf-8-sig")
            return Path(path)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        return self._save_text(f"运行总结_{stamp}.txt", text)
