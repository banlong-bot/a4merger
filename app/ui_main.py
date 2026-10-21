"""app/ui_main.py —— 主窗口（M2 骨架 + M3 后台执行 + M4 结果体验）。

包含：参数表单（根目录/目标勾选/输出模式/模板实时校验/引擎/密码）、
日志区（着色 + 容量截断 + 自动滚动）、两级进度条、
状态栏（引擎探测 + 任务状态 + 版本）、诊断导出与关于对话框、
完成总结对话框（M4：成功/失败清单、双击定位、导出 TXT、打开输出目录/报告）。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QGroupBox, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMenuBar, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QRadioButton, QScrollArea, QSpinBox, QSplitter,
                               QToolButton, QVBoxLayout, QWidget)

from app import theme
from app.diagnostics import build_diagnostic_zip, current_log_file, engine_probe
from app.icon import app_icon
from app.results_dialog import ResultDialog
from app.settings import AppSettings
from app.worker import RunnerWorker
from core import __version__
from core.collect import (LEVEL_TEXTS, exclusion_dirs, iter_target_folders,
                          rel_target, target_display)
from core.types import MergeConfig

LOG_MAX_BLOCKS = 5000      # 日志区容量截断（3.11.7）
LOG_TRIM_AMOUNT = 1000

# 处理级别：0=当前文件夹（根目录本身）/ 1=一级子文件夹 / 2=二级子文件夹
LEVEL_MAP = {LEVEL_TEXTS[0]: 0, LEVEL_TEXTS[1]: 1, LEVEL_TEXTS[2]: 2}
DEFAULT_LEVEL = 1
ORIENTATION_MAP = {"自动": "auto", "纵向": "portrait", "横向": "landscape"}
IMAGE_FIT_MAP = {"铺满 A4 页面": "page", "只缩小不放大": "origin"}
ENGINE_MAP = {"自动": "auto", "仅 WPS": "wps", "仅纯 Python": "native"}


def _level_index(level: int) -> int:
    """级别值 → 下拉框下标（历史设置里的未知值回落到默认级别）。"""
    values = list(LEVEL_MAP.values())
    return values.index(level) if level in values else values.index(DEFAULT_LEVEL)


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None) -> None:
        super().__init__()
        theme.apply()                            # 极简浅色皮肤（DESIGN.md；唯一实现处 app/theme.py）
        self.settings = settings or AppSettings()
        self.setWindowTitle(f"A4 合并助手 v{__version__}")
        self.setWindowIcon(app_icon())        # 标题栏/任务栏图标（与 exe 图标同源，见 app/icon.py）
        self.resize(1080, 720)
        self.worker: RunnerWorker | None = None
        self._last_cfg: MergeConfig | None = None
        self._last_log_file = current_log_file()
        self._last_summary = None
        self._result_dialog: ResultDialog | None = None
        self.smoke = False                       # 冒烟/测试模式：结果对话框不阻塞

        self._build_ui()
        self._connect_signals()
        self._sync_mode_ui()                 # 初始状态同步（build 时 setChecked 早于信号连接）
        self._load_settings()
        self._apply_template_validation()
        self._log_theme_state()
        self.settings.restore_window(self)

    # ================================================================ UI 构建

    def _log_theme_state(self) -> None:
        """启动日志记录皮肤是否真的加载（打包漏 datas 时能立刻看出来，不静默退化）。"""
        css = theme.load_qss()
        if css:
            self._append_log("info", f"界面皮肤：已加载（theme.qss，{len(css)} 字符）")
        else:
            self._append_log("warn", "界面皮肤文件缺失：使用系统默认样式（不影响合并功能）")

    def _build_ui(self) -> None:
        """构建主界面：顶部一句话用途 + 左（基本设置 / 目标 / 动作 / 高级折叠）+ 右（进度 / 日志）。

        信息分层依据 docs/shape-主窗口极简浅色皮肤.md：
        首次使用者看顶部与动作区，熟练用户只碰基本设置与目标列表，低频项收进高级选项。
        """
        self._template_error_active = False

        central = QWidget()
        central.setObjectName("central")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 12, 16, 8)
        outer.setSpacing(10)

        # ------------------------------------------------ 顶部：名称 + 一句话用途
        head = QHBoxLayout()
        head.setSpacing(12)
        lb_title = QLabel("A4 合并助手")
        lb_title.setObjectName("appTitle")
        lb_sub = QLabel("把一组文件夹各自合成一册 A4 PDF")
        lb_sub.setObjectName("appSubtitle")
        head.addWidget(lb_title)
        head.addWidget(lb_sub, 0, Qt.AlignBottom)
        head.addStretch(1)
        outer.addLayout(head)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ------------------------------------------------ 左侧：设置 + 目标 + 动作 + 高级
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 8, 0)
        lv.setSpacing(10)

        # ---- 基本设置（每次都必须看到的项）
        gb_base = QGroupBox("基本设置")
        f = QFormLayout(gb_base)
        f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ed_root = QLineEdit(self)
        self.ed_root.setPlaceholderText("请选择要合并的根目录…")
        btn_root = QPushButton("浏览…")
        row_root = QWidget()
        rh = QHBoxLayout(row_root)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.addWidget(self.ed_root, 1)
        rh.addWidget(btn_root)
        f.addRow("根目录", row_root)

        self.cb_level = QComboBox()
        self.cb_level.addItems(LEVEL_MAP.keys())
        f.addRow("处理级别", self.cb_level)

        self.ra_mode_a = QRadioButton("生成到各子文件夹内（模式A）")
        self.ra_mode_b = QRadioButton("统一输出到指定文件夹（模式B）")
        self.ra_mode_a.setChecked(True)
        mrow = QWidget()
        mh = QVBoxLayout(mrow)
        mh.setContentsMargins(0, 0, 0, 0)
        mh.addWidget(self.ra_mode_a)
        mh.addWidget(self.ra_mode_b)
        f.addRow("输出位置", mrow)

        self.ed_outdir = QLineEdit(self)
        self.ed_outdir.setPlaceholderText("模式B 输出目录（不存在会自动创建）")
        btn_outdir = QPushButton("浏览…")
        orow = QWidget()
        oh = QHBoxLayout(orow)
        oh.setContentsMargins(0, 0, 0, 0)
        oh.addWidget(self.ed_outdir, 1)
        oh.addWidget(btn_outdir)
        f.addRow("输出目录", orow)

        self.ed_template = QLineEdit("【合并】{folder}.pdf")
        f.addRow("文件名模板", self.ed_template)

        self.cb_report = QCheckBox("生成 合并报告.txt")
        self.cb_report.setChecked(True)
        f.addRow("运行报告", self.cb_report)
        lv.addWidget(gb_base)

        # ---- 目标文件夹（状态行直接说「将生成几册」）
        gb_targets = QGroupBox("目标文件夹")
        tv = QVBoxLayout(gb_targets)
        self.lw_targets = QListWidget(self)
        self.lw_targets.setSelectionMode(QListWidget.NoSelection)
        self.lw_targets.setMinimumHeight(110)
        tv.addWidget(self.lw_targets, 1)
        hb = QHBoxLayout()
        self.btn_all = QPushButton("全选")
        self.btn_none = QPushButton("全不选")
        self.lb_target_status = QLabel("")
        self.lb_target_status.setObjectName("targetStatus")
        hb.addWidget(self.btn_all)
        hb.addWidget(self.btn_none)
        hb.addStretch(1)
        hb.addWidget(self.lb_target_status)
        tv.addLayout(hb)
        lv.addWidget(gb_targets, 1)

        # ---- 主按钮区（固定在窗口底部；整屏唯一实心按钮，点之前知道会发生什么）
        action = QFrame()
        action.setObjectName("actionBar")
        av = QHBoxLayout(action)
        av.setContentsMargins(14, 10, 14, 10)
        av.setSpacing(10)
        tcol = QVBoxLayout()
        tcol.setSpacing(4)
        self.lb_expect = QLabel("")
        self.lb_expect.setObjectName("expectLabel")
        self.lb_expect.setWordWrap(True)
        tcol.addWidget(self.lb_expect)
        self.lb_inline_error = QLabel("")
        self.lb_inline_error.setObjectName("inlineError")
        self.lb_inline_error.setWordWrap(True)
        self.lb_inline_error.setVisible(False)
        tcol.addWidget(self.lb_inline_error)
        av.addLayout(tcol, 1)
        self.btn_start = QPushButton("开始合并")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setMinimumWidth(180)
        self.btn_start.setDefault(True)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        self.cb_dryrun = QCheckBox("试运行（只看清单，不生成文件）")
        av.addWidget(self.cb_dryrun)
        av.addWidget(self.btn_cancel)
        av.addWidget(self.btn_start)

        # ---- 高级选项（可折叠，默认收起，状态记忆）：排版 / 转换 / 加密
        advrow = QHBoxLayout()
        self.btn_advanced = QToolButton()
        self.btn_advanced.setObjectName("advancedToggle")
        self.btn_advanced.setText("高级选项：排版 / 转换 / 加密")
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.setChecked(False)
        self.btn_advanced.setArrowType(Qt.RightArrow)
        self.btn_advanced.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_advanced.setCursor(Qt.PointingHandCursor)
        advrow.addWidget(self.btn_advanced)
        advrow.addStretch(1)
        lv.addLayout(advrow)

        self.adv_panel = QWidget()
        self.adv_panel.setObjectName("advPanel")
        pv = QVBoxLayout(self.adv_panel)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(10)

        # ---- 排版与转换
        gb_conv = QGroupBox("排版与转换")
        f2 = QFormLayout(gb_conv)
        f2.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sp_margin = QDoubleSpinBox()
        self.sp_margin.setRange(0, 100)
        self.sp_margin.setDecimals(1)
        self.sp_margin.setSuffix(" mm")
        f2.addRow("四周留白", self.sp_margin)

        self.cb_orientation = QComboBox()
        self.cb_orientation.addItems(ORIENTATION_MAP.keys())
        f2.addRow("A4 方向", self.cb_orientation)

        self.cb_image_fit = QComboBox()
        self.cb_image_fit.addItems(IMAGE_FIT_MAP.keys())
        f2.addRow("图片适配", self.cb_image_fit)

        self.cb_engine = QComboBox()
        self.cb_engine.addItems(ENGINE_MAP.keys())
        f2.addRow("转换引擎", self.cb_engine)

        self.sp_timeout = QSpinBox()
        self.sp_timeout.setRange(30, 3600)
        self.sp_timeout.setSuffix(" 秒")
        self.sp_timeout.setValue(600)
        f2.addRow("WPS 超时", self.sp_timeout)

        self.cb_lookalike = QCheckBox("把「与文件夹同名」的 PDF 也当作素材")
        f2.addRow("同名成品", self.cb_lookalike)

        self.cb_skip_excel = QCheckBox("遇到 Excel（.xls/.xlsx）跳过：不合并、不计失败")
        self.cb_skip_excel.setToolTip(
            "默认不勾选：Excel 会尝试用 WPS 转换（未装 WPS 时会进入失败清单）。\n"
            "勾选后：.xls/.xlsx 在预检阶段被跳过，不计入失败清单，\n"
            "结果对话框与运行报告会单列「跳过的 Excel」清单。")
        f2.addRow("Excel 处理", self.cb_skip_excel)
        pv.addWidget(gb_conv)

        # ---- 加密文件
        gb_enc = QGroupBox("加密文件")
        f3 = QFormLayout(gb_enc)
        f3.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pt_passwords = QPlainTextEdit()
        self.pt_passwords.setPlaceholderText("每行一个密码（可用逗号分隔多个）")
        self.pt_passwords.setMaximumHeight(80)
        f3.addRow("打开密码", self.pt_passwords)
        btn_pwfile = QPushButton("导入密码文件…")
        f3.addRow("", btn_pwfile)
        self.cb_no_prompt = QCheckBox("遇到加密文件直接跳过（不弹窗）")
        f3.addRow("", self.cb_no_prompt)
        self.cb_remember_pw = QCheckBox("记住密码（Windows 本机加密保存，DPAPI）")
        f3.addRow("", self.cb_remember_pw)
        pv.addWidget(gb_enc)

        self.adv_panel.setVisible(False)
        lv.addWidget(self.adv_panel)

        scroll = QScrollArea()
        self.scroll_left = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(left)

        # ------------------------------------------------ 右侧：进度 + 日志
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        rv.setSpacing(6)

        self.lb_prog_folder = QLabel("文件夹进度")
        self.lb_prog_folder.setObjectName("sectionLabel")
        self.pb_folder = QProgressBar()
        self.lb_prog_page = QLabel("页面进度")
        self.lb_prog_page.setObjectName("sectionLabel")
        self.pb_page = QProgressBar()
        for pb in (self.pb_folder, self.pb_page):     # 空闲时只留一条细轨道，进度文字由上方小标题承载
            pb.setRange(0, 1)
            pb.setValue(0)
            pb.setTextVisible(False)
            pb.setFixedHeight(8)
        rv.addWidget(self.lb_prog_folder)
        rv.addWidget(self.pb_folder)
        rv.addWidget(self.lb_prog_page)
        rv.addWidget(self.pb_page)

        lb_log = QLabel("运行日志")
        lb_log.setObjectName("sectionLabel")
        rv.addWidget(lb_log)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setObjectName("logView")
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(LOG_MAX_BLOCKS + LOG_TRIM_AMOUNT * 2)
        rv.addWidget(self.txt_log, 1)

        splitter.addWidget(scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        outer.addWidget(splitter, 1)
        outer.addWidget(action)                 # 动作条常驻窗口底部，不用滚动就能点「开始合并」
        self.setCentralWidget(central)

        # 菜单
        mb = self.menuBar()
        m_file = mb.addMenu("文件")
        m_file.addAction("导出诊断包…", self._export_diagnostics)
        m_file.addSeparator()
        m_file.addAction("退出", self.close)
        m_help = mb.addMenu("帮助")
        m_help.addAction("关于", self._show_about)

        # 状态栏：引擎探测 + 长路径状态 + 任务状态 + 版本号（计划 2.2 / 3.11.3 / 3.11.10）
        self.lb_engine = QLabel("引擎：探测中…")
        self.lb_longpath = QLabel("长路径：检测中…")
        self.lb_state = QLabel("就绪")
        self.lb_version = QLabel(f"v{__version__}")
        sb = self.statusBar()
        sb.addWidget(self.lb_engine)
        sb.addWidget(self.lb_longpath)
        sb.addWidget(self.lb_state, 1)          # 任务状态占满中间
        sb.addPermanentWidget(self.lb_version)
        self._btn_root = btn_root
        self._btn_outdir = btn_outdir
        self._btn_pwfile = btn_pwfile

        # 初始文案（无根目录时动作区即三步引导；不占列表空间）
        self._update_expect()

    # ================================================================ 高级选项与行内提示

    def _toggle_advanced(self, on: bool) -> None:
        """展开/收起高级选项（默认收起：首次使用者不被低频项淹没）。

        左栏在滚动区里，展开后内容可能在折叠处下方——自动滚到「高级选项」这一行，
        否则用户点了开关却看不到任何变化。
        """
        self.adv_panel.setVisible(on)
        self.btn_advanced.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        if on:
            QTimer.singleShot(0, lambda: self.scroll_left.ensureWidgetVisible(
                self.adv_panel, 0, 40))

    def _set_advanced_expanded(self, on: bool) -> None:
        self.btn_advanced.setChecked(on)
        self._toggle_advanced(on)

    def _set_inline_error(self, text: str) -> None:
        """行内错误：在动作区就近说明原因与下一步，不用弹窗打断（可预期校验）。"""
        self.lb_inline_error.setText(text)
        self.lb_inline_error.setVisible(bool(text))

    def _update_expect(self) -> None:
        """动作区一句话：点之前就知道会发生什么（首次使用者最关键的一行）。"""
        total = self.lw_targets.count()
        checked = sum(1 for i in range(total)
                      if self.lw_targets.item(i).checkState() == Qt.Checked)
        if not self.ed_root.text().strip() or total == 0:
            self.lb_expect.setText("① 选根目录 → ② 勾选要合并的文件夹 → ③ 点「开始合并」")
            return
        if checked == 0:
            self.lb_expect.setText("请至少勾选一个文件夹，再点「开始合并」")
            return
        if self.cb_dryrun.isChecked():
            self.lb_expect.setText(
                f"试运行：只列出 {checked} 个文件夹会合并哪些文件，不生成 PDF")
            return
        self.lb_expect.setText(f"将把 {checked} 个文件夹各自合成一册 A4 PDF")

    def _connect_signals(self) -> None:
        self._btn_root.clicked.connect(self._pick_root)
        self._btn_outdir.clicked.connect(self._pick_outdir)
        self._btn_pwfile.clicked.connect(self._pick_pwfile)
        self.ed_root.textChanged.connect(self._refresh_targets)
        self.cb_level.currentIndexChanged.connect(self._refresh_targets)
        self.ra_mode_a.toggled.connect(self._sync_mode_ui)
        self.ra_mode_b.toggled.connect(self._sync_mode_ui)
        self.ed_template.textChanged.connect(self._apply_template_validation)
        self.ed_outdir.textChanged.connect(self._refresh_targets)
        self.btn_all.clicked.connect(lambda: self._set_targets_checked(True))
        self.btn_none.clicked.connect(lambda: self._set_targets_checked(False))
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_advanced.toggled.connect(self._toggle_advanced)
        self.cb_dryrun.toggled.connect(self._update_expect)
        self.lw_targets.itemChanged.connect(self._update_target_status)

    # ================================================================ 设置记忆

    def _load_settings(self) -> None:
        s = self.settings
        self.ed_root.setText(s.get_str("root"))
        self.ra_mode_b.setChecked(s.get_str("output_mode") == "B")
        self.ra_mode_a.setChecked(s.get_str("output_mode") != "B")
        self.ed_outdir.setText(s.get_str("output_dir"))
        self.cb_level.setCurrentIndex(_level_index(s.get_int("level", DEFAULT_LEVEL)))
        self.ed_template.setText(s.get_str("output_name", "【合并】{folder}.pdf"))
        self.cb_report.setChecked(s.get_bool("report", True))
        self.sp_margin.setValue(float(s.get_str("margin_mm", "0.0") or "0.0"))
        orient = s.get_str("orientation", "auto")
        self.cb_orientation.setCurrentIndex(
            list(ORIENTATION_MAP.values()).index(orient) if orient in ORIENTATION_MAP.values() else 0)
        fit = s.get_str("image_fit", "page")
        self.cb_image_fit.setCurrentIndex(
            list(IMAGE_FIT_MAP.values()).index(fit) if fit in IMAGE_FIT_MAP.values() else 0)
        eng = s.get_str("engine", "auto")
        self.cb_engine.setCurrentIndex(
            list(ENGINE_MAP.values()).index(eng) if eng in ENGINE_MAP.values() else 0)
        self.sp_timeout.setValue(s.get_int("wps_timeout", 600))
        self.cb_lookalike.setChecked(s.get_bool("include_lookalikes", False))
        self.cb_skip_excel.setChecked(s.get_bool("skip_excel", False))
        self.cb_no_prompt.setChecked(s.get_bool("no_prompt", False))
        self.cb_remember_pw.setChecked(s.get_bool("remember_pw", False))
        self.cb_dryrun.setChecked(s.get_bool("dry_run", False))
        tokens = s.get_str_list("passwords")
        if tokens:
            from core.dpapi import dpapi_unprotect
            self.pt_passwords.setPlainText(
                "\n".join(dpapi_unprotect(t) for t in tokens))
        self._set_advanced_expanded(s.get_bool("advanced_expanded", False))

    def _save_settings(self) -> None:
        s = self.settings
        s.set("root", self.ed_root.text())
        s.set("output_mode", "B" if self.ra_mode_b.isChecked() else "A")
        s.set("output_dir", self.ed_outdir.text())
        s.set("level", LEVEL_MAP[self.cb_level.currentText()])
        s.set("output_name", self.ed_template.text())
        s.set("report", self.cb_report.isChecked())
        s.set("margin_mm", self.sp_margin.value())
        s.set("orientation", ORIENTATION_MAP[self.cb_orientation.currentText()])
        s.set("image_fit", IMAGE_FIT_MAP[self.cb_image_fit.currentText()])
        s.set("engine", ENGINE_MAP[self.cb_engine.currentText()])
        s.set("wps_timeout", self.sp_timeout.value())
        s.set("include_lookalikes", self.cb_lookalike.isChecked())
        s.set("skip_excel", self.cb_skip_excel.isChecked())
        s.set("advanced_expanded", self.btn_advanced.isChecked())
        s.set("no_prompt", self.cb_no_prompt.isChecked())
        s.set("dry_run", self.cb_dryrun.isChecked())
        checked = self._checked_targets()
        s.set_str_list("checked_targets", checked)
        pws = [x.strip() for x in self.pt_passwords.toPlainText().replace("，", ",").splitlines() if x.strip()]
        if pws and self.cb_remember_pw.isChecked():
            # DPAPI 加密后再保存（3.11.9）：本机本用户可解，拷贝走无效
            from core.dpapi import dpapi_protect
            s.set_str_list("passwords", [dpapi_protect(p) for p in pws])
            s.set("remember_pw", True)
        else:
            self.settings.qs.remove("passwords")
            self.settings.qs.remove("remember_pw")

    def closeEvent(self, ev) -> None:            # noqa: N802
        self._save_settings()
        self.settings.save_window(self)
        super().closeEvent(ev)

    # ================================================================ 交互

    def _pick_root(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择根目录", self.ed_root.text())
        if d:
            self.ed_root.setText(d)

    def _pick_outdir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择统一输出目录", self.ed_outdir.text())
        if d:
            self.ed_outdir.setText(d)

    def _pick_pwfile(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "选择密码文件", "", "文本文件 (*.txt)")
        if f:
            try:
                lines = Path(f).read_text(encoding="utf-8-sig", errors="replace").splitlines()
            except Exception as exc:
                QMessageBox.warning(self, "导入失败", str(exc))
                return
            words = []
            for ln in lines:
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    words.extend(x.strip() for x in ln.split(",") if x.strip())
            cur = [x.strip() for x in self.pt_passwords.toPlainText().splitlines() if x.strip()]
            self.pt_passwords.setPlainText("\n".join(dict.fromkeys(cur + words)))

    def _sync_mode_ui(self) -> None:
        """模式B 时启用输出目录输入。"""
        is_b = self.ra_mode_b.isChecked()
        self.ed_outdir.setEnabled(is_b)
        self._btn_outdir.setEnabled(is_b)

    def _refresh_targets(self) -> None:
        """按根目录+级别刷新目标文件夹候选（保留勾选记忆，排除模式B输出目录）。

        列表显示名用 target_display（级别0 显示为「xxx（当前文件夹）」）；
        真实目标标识（相对根目录的路径，根目录记为 "."）存在 UserRole 里，
        传给 core 的 --only 与勾选记忆一律用该标识。
        """
        root_txt = self.ed_root.text().strip()
        root = Path(root_txt)
        if not root_txt or not root.is_dir():
            self.lw_targets.clear()
            self.lb_target_status.setText("")
            self._update_expect()
            return
        out_dir = Path(self.ed_outdir.text().strip()) if self.ra_mode_b.isChecked() else None
        exclude = exclusion_dirs(root, out_dir)
        try:
            targets = list(iter_target_folders(root, LEVEL_MAP[self.cb_level.currentText()],
                                               exclude))
        except OSError:
            targets = []
        remembered = set(self.settings.get_str_list("checked_targets"))
        was_empty = self.lw_targets.count() == 0
        self.lw_targets.blockSignals(True)
        self.lw_targets.clear()
        for t in targets:
            rel = rel_target(root, t)
            item = QListWidgetItem(target_display(root, t))
            item.setData(Qt.UserRole, rel)          # 真实标识（--only 用）
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if remembered or was_empty:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Checked)     # 全部默认勾选
            self.lw_targets.addItem(item)
        self.lw_targets.blockSignals(False)
        self._update_target_status()

    def _checked_targets(self) -> list[str]:
        """已勾选目标的真实标识（相对根目录路径，根目录记为 "."）。"""
        out: list[str] = []
        for i in range(self.lw_targets.count()):
            item = self.lw_targets.item(i)
            if item.checkState() != Qt.Checked:
                continue
            rel = item.data(Qt.UserRole)
            out.append(str(rel) if rel else item.text())
        return out

    def _set_targets_checked(self, on: bool) -> None:
        for i in range(self.lw_targets.count()):
            self.lw_targets.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def _update_target_status(self) -> None:
        """目标状态行：一眼看出「已选几个 / 将生成几册」。"""
        total = self.lw_targets.count()
        checked = sum(1 for i in range(total)
                      if self.lw_targets.item(i).checkState() == Qt.Checked)
        if total == 0:
            self.lb_target_status.setText("")
        elif checked == 0:
            self.lb_target_status.setText(f"已选 0/{total} · 请勾选文件夹")
        else:
            self.lb_target_status.setText(f"已选 {checked}/{total} · 将生成 {checked} 册")
        self._update_expect()

    def _apply_template_validation(self) -> None:
        """模板实时校验（3.11.6）：非法字符/未知占位符 → 红框 + 行内说明 + 禁用开始。"""
        text = self.ed_template.text()
        errs = MergeConfig(root=Path("."), output_name=text).validate()
        if errs and text:
            self.ed_template.setStyleSheet(
                f"QLineEdit{{border:1px solid {theme.color('error-border')};"
                f"background:{theme.color('error-bg')};}}")
            self.ed_template.setToolTip("\n".join(errs))
            self._set_inline_error("文件名模板有误：" + "；".join(errs))
            self._template_error_active = True
        else:
            self.ed_template.setStyleSheet("")
            self.ed_template.setToolTip("")
            if getattr(self, "_template_error_active", False):
                self._set_inline_error("")
                self._template_error_active = False
        self.btn_start.setEnabled(not bool(errs))

    # ================================================================ 执行

    def _build_config(self) -> MergeConfig | None:
        """把表单收成 MergeConfig；可预期的问题就近行内提示，不用弹窗打断。"""
        root_txt = self.ed_root.text().strip()
        root = Path(root_txt) if root_txt else None
        if root is None or not root.is_dir():
            self._set_inline_error("请先选择有效的根目录：点「浏览…」挑一个文件夹。")
            return None
        checked = self._checked_targets()
        if not checked:
            self._set_inline_error("请至少勾选一个目标文件夹。")
            return None
        out_dir = None
        if self.ra_mode_b.isChecked():
            t = self.ed_outdir.text().strip()
            if not t:
                self._set_inline_error("模式B 需要填写统一输出目录（或改回模式A）。")
                return None
            out_dir = Path(t)
        pws = []
        for ln in self.pt_passwords.toPlainText().replace("，", ",").splitlines():
            pws.extend(x.strip() for x in ln.split(",") if x.strip())
        cfg = MergeConfig(
            root=root,
            level=LEVEL_MAP[self.cb_level.currentText()],
            output_name=self.ed_template.text(),
            output_dir=out_dir,
            only=checked,
            margin_mm=self.sp_margin.value(),
            orientation=ORIENTATION_MAP[self.cb_orientation.currentText()],
            image_fit=IMAGE_FIT_MAP[self.cb_image_fit.currentText()],
            engine=ENGINE_MAP[self.cb_engine.currentText()],
            wps_timeout=self.sp_timeout.value(),
            include_lookalikes=self.cb_lookalike.isChecked(),
            skip_excel=self.cb_skip_excel.isChecked(),
            passwords=pws,
            prompt=not self.cb_no_prompt.isChecked(),
            report=self.cb_report.isChecked(),
            dry_run=self.cb_dryrun.isChecked(),
        )
        errs = cfg.validate()
        if errs:
            self._set_inline_error("配置有误：" + "；".join(errs))
            return None
        self._set_inline_error("")
        return cfg

    def _start(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        cfg = self._build_config()
        if cfg is None:
            return
        self._set_inline_error("")
        self._last_cfg = cfg
        self._set_running(True)
        self._set_state("正在运行…", "busy")
        self.txt_log.clear()
        for pb in (self.pb_folder, self.pb_page):
            pb.setTextVisible(False)             # 进度文字在上方小标题里（字体可控、不压在蓝条上）
            pb.setFixedHeight(18)                # 运行中轨道加高，蓝色进度更醒目
            pb.setRange(0, 0)
        self.lb_prog_folder.setText("文件夹进度  准备中…")
        self.lb_prog_page.setText("页面进度  准备中…")
        self._append_log("info", f"开始处理：{cfg.root}（{'预览' if cfg.dry_run else '合并'}模式）")

        self.worker = RunnerWorker(cfg, self)
        self.worker.log_signal.connect(self._append_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.password_requested.connect(self._on_password_request)
        self.worker.start()

    def _on_password_request(self, payload: dict) -> None:
        """主线程：加密文件密码输入框（最多 3 次，取消/失败=跳过该文件）。"""
        path = payload.get("path")
        verify = payload.get("verify")
        if path is None or not callable(verify) or self.worker is None:
            return
        self._append_log("warn", f"「{path.name}」已加密，请在弹出的窗口输入密码…")
        for _ in range(3):
            text, ok = QInputDialog.getText(
                self, "输入密码",
                f"「{path.name}」已加密，需要打开密码\n（点击「取消」＝跳过这个文件）",
                QLineEdit.Password)
            if not ok:
                self.worker.submit_password(None)
                self._append_log("info", f"已跳过 {path.name}（未输入密码）")
                return
            try:
                if verify(text):
                    self.worker.submit_password(text)
                    self._append_log("ok", f"{path.name}：密码正确")
                    return
            except Exception:
                pass
            QMessageBox.warning(self, "密码错误", "密码不正确，请重试。")
        self.worker.submit_password(None)
        self._append_log("warn", f"已跳过 {path.name}（3 次密码均不正确）")

    def _cancel(self) -> None:
        if self.worker is not None:
            self._append_log("warn", "正在取消…（将终止正在运行的转换进程）")
            self._set_state("正在取消…", "warn")
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)

    def _set_state(self, text: str, kind: str = "idle") -> None:
        """状态栏「当前任务状态」（计划 2.2：引擎探测 / 任务状态 / 版本号）。"""
        colors = {"idle": theme.color("ink"), "busy": theme.color("accent"),
                  "ok": theme.color("ok"), "warn": theme.color("warn"),
                  "error": theme.color("error")}
        self.lb_state.setText(text)
        self.lb_state.setToolTip(text)
        self.lb_state.setStyleSheet(f"color:{colors.get(kind, theme.color('ink'))};")

    def _set_running(self, running: bool) -> None:
        self.btn_start.setEnabled(not running and not bool(
            MergeConfig(root=Path("."), output_name=self.ed_template.text()).validate()))
        self.btn_cancel.setEnabled(running)

    def _on_progress(self, kind: str, done: int, total: int, text: str) -> None:
        if kind == "folder":
            self.pb_folder.setRange(0, max(total, 1))
            self.pb_folder.setValue(done + 1)
            self.lb_prog_folder.setText(f"文件夹进度  {done + 1}/{total}：{text}")
        elif kind == "page":
            self.pb_page.setRange(0, 0)          # 页级进度是“进行中”的不定态
            self.lb_prog_page.setText(f"页面进度  {text}")

    def _reset_progress(self) -> None:
        """进度归零（空闲/结束后）：轨道清空并收细、小标题回到基础文案。"""
        self.pb_folder.setRange(0, 1)
        self.pb_page.setRange(0, 1)
        self.lb_prog_folder.setText("文件夹进度")
        self.lb_prog_page.setText("页面进度")
        for pb in (self.pb_folder, self.pb_page):
            pb.setFixedHeight(8)

    def _on_finished(self, summary) -> None:
        """运行结束：状态栏收尾 + 日志汇总 + 弹出完成总结对话框（M4）。"""
        self._set_running(False)
        self._reset_progress()
        self.pb_folder.setValue(1)               # 结束后保留满轨道（本次已处理完）
        self.pb_page.setValue(1)
        if summary is None:
            self._append_log("error", "处理异常结束（详见日志）。")
            self._set_state("运行异常结束，详见日志", "error")
            QMessageBox.warning(self, "运行失败",
                                "处理过程中发生异常，已结束本次任务。\n详见日志区与诊断包。")
            self.worker = None
            return

        self._last_summary = summary
        self._save_settings()                    # 运行后同步勾选/参数记忆
        ok = sum(1 for r in summary.results if r.done)
        total = len(summary.results)
        pages = sum(r.pages for r in summary.results)
        fails = [(r.label, f) for r in summary.results for f in r.failures]
        skipped = sum(len(r.lookalikes) for r in summary.results)
        excel = sum(len(r.skipped_excel or []) for r in summary.results)
        prefix = "预览完成" if summary.config.dry_run else "处理完成"
        self._append_log(
            "info",
            f"{prefix}：成功 {ok}/{total} 个目标，共 {pages} 页，"
            f"失败 {len(fails)} 个文件，跳过成品 {skipped} 个，"
            + (f"跳过 Excel {excel} 个，" if summary.config.skip_excel else "")
            + f"耗时 {summary.elapsed:.1f} 秒。"
            + (f"报告：{summary.report_path}" if summary.report_path else ""))
        tone = "error" if fails else ("warn" if skipped or not ok else "ok")
        self._set_state(
            f"{prefix}：成功 {ok}/{total} 个目标，共 {pages} 页"
            + (f"，失败 {len(fails)} 个" if fails else "")
            + (f"，跳过 Excel {excel} 个" if summary.config.skip_excel else ""), tone)
        self._show_result_dialog(summary)
        self.worker = None

    def _show_result_dialog(self, summary) -> None:
        """弹出完成总结对话框（M4）；冒烟测试下不显示、不阻塞。"""
        dlg = ResultDialog(summary, cfg=self._last_cfg or summary.config, parent=self)
        self._result_dialog = dlg                    # 保持引用，防被回收
        dlg.finished.connect(lambda _r: setattr(self, "_result_dialog", None))
        if getattr(self, "smoke", False):
            return
        dlg.exec()

    # ================================================================ 日志

    def _append_log(self, level: str, msg: str) -> None:
        color = {"info": theme.color("ink"), "ok": theme.color("ok"),
                 "warn": theme.color("warn"), "error": theme.color("error")}.get(
                     level, theme.color("ink"))
        import html as _html
        self.txt_log.appendHtml(
            f'<span style="color:{color};">{_html.escape(msg)}</span>')
        from app.diagnostics import log_debug
        log_debug(level, msg)                    # 同时写 debug 日志文件
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())                # 自动滚动到底
        if self.txt_log.blockCount() > LOG_MAX_BLOCKS + LOG_TRIM_AMOUNT:
            self._trim_log()

    def _trim_log(self) -> None:
        """容量截断：超过上限删除开头一段（保留最新）。"""
        doc = self.txt_log.document()
        while doc.blockCount() > LOG_MAX_BLOCKS:
            doc.setPlainText(doc.toPlainText()[len(doc.findBlockByNumber(0).text()) + 1:])

    # ================================================================ 其它

    def _export_diagnostics(self) -> None:
        f, _ = QFileDialog.getSaveFileName(self, "导出诊断包", "A4合并助手_诊断包.zip",
                                           "ZIP 文件 (*.zip)")
        if not f:
            return
        try:
            build_diagnostic_zip(Path(f), cfg=self._last_cfg, log_file=self._last_log_file)
            QMessageBox.information(self, "导出成功", f"诊断包已保存：\n{f}")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def _show_about(self) -> None:
        from PySide6.QtCore import __version__ as qt_ver
        from app.diagnostics import (build_time_text, dependency_versions,
                                     is_frozen)
        deps = "、".join(f"{k} {v}" for k, v in dependency_versions().items())
        QMessageBox.about(
            self, "关于 A4 合并助手",
            f"<b>A4 合并助手</b> v{__version__}"
            f"（{'打包版' if is_frozen() else '开发模式'}）<br>"
            f"构建时间：{build_time_text()}<br>"
            "把每位股东/客户文件夹里的 PDF、图片、Word、Excel、PPT、文本"
            "按顺序合并成统一的 A4 PDF。"
            "<br><br>更新方式：整包替换 exe（无自动更新）。"
            f"<br>Qt {qt_ver}<br>依赖：{deps}")

    def showEvent(self, ev) -> None:             # noqa: N802
        super().showEvent(ev)
        QTimer.singleShot(50, self._probe_engines)
        QTimer.singleShot(80, self._check_long_paths)

    def _check_long_paths(self) -> None:
        """启动探测系统长路径支持（计划 3.11.3）：未开启时中文提示，不静默。"""
        try:
            from core.longpath import long_paths_enabled, startup_hint
            hint = startup_hint()
            self.lb_longpath.setText(
                "长路径：已开启" if long_paths_enabled() else "长路径：未开启")
            if hint:
                self.lb_longpath.setToolTip(hint)
                self._append_log("warn", hint)
        except Exception:
            self.lb_longpath.setText("长路径：未知")

    def _probe_engines(self) -> None:
        try:
            info = engine_probe()
            wps = "WPS 可用" if info.get("wps") else "WPS 不可用"
            native = "纯 Python 可用" if info.get("native") else "纯 Python 不可用"
            self.lb_engine.setText(f"引擎：{wps} / {native}")
            self._append_log(                       # 探测结果同时进日志（排障取证）
                "info",
                f"引擎探测：{wps} / {native}"
                + (f"（WPS 安装目录：{info['wps_install_dir']}）"
                   if info.get("wps_install_dir") else ""))
        except Exception as exc:
            self.lb_engine.setText("引擎：探测失败")
            self._append_log("warn", f"引擎探测失败：{exc}")
        self.lb_version.setText(f"v{__version__}")