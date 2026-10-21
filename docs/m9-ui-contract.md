# M9 视觉改版接口契约（Lead 定稿，A/B/C 三方共同遵守）

> 目标：主窗口换成「花笺」风格（暖纸底 + 竹绿 + 卡片圆角 + 阴影 + 动效 + 无边框自绘标题栏），
> 内置 HarmonyOS Sans SC 字体。所有文案仍为简体中文。

## 一、分工与写权限（禁止越界写别人文件）

| 负责人 | 唯一可写文件 |
| --- | --- |
| A（theme） | `app/theme.py`、`app/theme.qss`、`DESIGN.md`、`.impeccable/design.json` |
| B（window） | `app/ui_main.py`、`app/main.py`、`tools/capture_ui.py` |
| C（tests） | `tests/test_ui_theme.py`、`tests/test_gui_smoke.py`、`tests/test_results_dialog.py`（仅第 313 行 statusBar 断言）、`tests/conftest.py`（如需） |
| Lead | `fonts/`、`build/a4merger.spec`、`README.md`、`docs/使用说明-给同事.md`、`PROGRESS.md`、git 提交、打包 |

任何人**不执行** `git commit` / `git push` / 改 `legacy/` / 改 `core/`。提交由 Lead 统一做。

## 二、`app/theme.py` 公开 API（A 实现，B 调用）

```python
TOKENS: dict[str, str]                      # 颜色/圆角/间距/动效时长 token，见第三节
def color(name: str) -> str                 # 未知名字回退 ink，禁止 KeyError
def load_qss() -> str                       # 读 app/theme.qss，替换 $token
def ensure_fonts() -> str                   # 注册内置字体，返回首选 family 名（失败返回 "Microsoft YaHei UI"）
def apply(app=None) -> None                 # 幂等：注册字体 + QApplication.setStyleSheet(load_qss())
def ui_font_family() -> str                 # 首选字体 family（供日志/诊断）
def motion_enabled() -> bool                # 默认 True；环境变量 A4_MOTION=0 时 False
def set_motion_enabled(on: bool) -> None    # 界面开关同步（关掉后新动画立即结束）
def fade_in(widget, ms: int = 180, start: float = 0.0) -> None
def fade_widget(widget, ms: int = 160, start: float = 0.0) -> None      # 通用透明度淡入（QGraphicsOpacityEffect）
def animate_progress(bar, value: int, ms: int = 240) -> None            # 平滑推进进度条
def animate_expand(panel, expanded: bool, ms: int = 200) -> None        # 高度展开/收起（改 maximumHeight）
def attach_card_shadow(widget, level: str = "card") -> None             # 静态阴影 + 悬停加深动画
def set_maximized_chrome(window, maximized: bool) -> None               # 设 window.property("maximized") 并重刷样式
```

约束：
- 动画对象必须由 theme 内部**保活**（模块级 list），否则被 GC 后动画不动。
- `motion_enabled()` 为 False 时所有动画函数直接落到终态（同步设置属性，不创建动画）。
- `attach_card_shadow` 用 `QGraphicsDropShadowEffect`；对位于 `QScrollArea` 内的控件注意不要叠加两层 effect。
- 不在 theme 里 import `app.settings`（避免循环依赖）。

## 三、`TOKENS` 必备键（A 按花笺调色板定稿，DESIGN.md 同步）

颜色：`surface`、`surface-raised`（卡片白）、`surface-subtle`、`paper`（暖纸底）、`paper-deep`、
`border`、`border-strong`、`ink`、`ink-muted`、`bamboo`（主色竹绿）、`bamboo-deep`、`bamboo-soft`、
`ok`、`warn`、`error`、`error-bg`、`error-border`。
圆角：`radius-sm`(6px)、`radius-md`(10px)、`radius-lg`(14px)、`radius-pill`(999px)。
间距：`gap-xs`(4px)、`gap-sm`(8px)、`gap-md`(12px)、`gap-lg`(16px)、`gap-xl`(24px)。
动效：`motion-fast`(120ms)、`motion-base`(180ms)、`motion-slow`(240ms)、`easing`(cubic-bezier(0.22,1,0.36,1))。

## 四、QSS objectName 契约（A 写样式，B 设置 objectName）

| objectName | 控件 | 说明 |
| --- | --- | --- |
| `windowShell` | QFrame | 无边框窗口根容器：暖纸背景、14px 圆角、1px 边框 |
| `titleBar` | QWidget | 自绘标题栏（高 40px），可拖拽 |
| `titleText` | QLabel | 「A4 合并助手」标题，11pt/700 |
| `titleSub` | QLabel | 副标题（灰色小字） |
| `menuButton` | QToolButton | 标题栏里的「文件 / 帮助 / 界面」菜单按钮 |
| `winMin` `winMax` `winClose` | QToolButton | 窗口按钮（28×28，hover 变浅，关闭 hover 红底白字） |
| `appTitle` `appSubtitle` | QLabel | 内容区大标题/副标题（保留现有） |
| `sectionLabel` `targetStatus` `expectLabel` `inlineError` | QLabel | 现有语义保留 |
| `cardBox` | QGroupBox | 卡片：白底、10px 圆角、1px 发丝线、内边距 14px |
| `actionBar` | QFrame | 底部动作条：白底、顶部发丝线、圆角底 |
| `primaryButton` | QPushButton | 主按钮：竹绿实心、pill 圆角、hover 加深 |
| `advancedToggle` | QToolButton | 高级选项开关（无边框竹绿字 + 箭头） |
| `logView` | QPlainTextEdit | 日志：等宽字体、浅底、圆角 |
| `statusBarCustom` | QFrame | 自绘状态栏（替代 QMainWindow.statusBar），顶部发丝线 |
| `windowShell[maximized="true"]` | — | 最大化时圆角变 0、边框去掉 |
| `QMenu` `QToolTip` `QScrollBar` `QProgressBar` `QTabWidget/QTabBar` `QHeaderView` `QTableWidget` | — | 统一浅色花笺风；结果对话框 `.qss` 也要覆盖 |

## 五、B 的实现要点（`app/ui_main.py`）

1. 无边框：`Qt.FramelessWindowHint | Qt.Window` + `WA_TranslucentBackground`；`setCentralWidget(windowShell)`。
2. 结构：`windowShell` → VBox(0 边距)：`titleBar`（标题 + 菜单按钮 + 最小化/最大化/关闭）→ 内容区（现有 head + splitter + actionBar）→ `statusBarCustom`（原 lb_engine/lb_longpath/lb_state/lb_version 全部保留，**不再**调用 `self.statusBar()`）。
3. 拖拽：titleBar 鼠标左键 `windowHandle().startSystemMove()`；双击 `_toggle_maximize()`。
4. 缩放：MainWindow 上 6px 边框命中 → `windowHandle().startSystemResize(edges)`；hover 时改光标。
5. 最大化/还原：`theme.set_maximized_chrome(self, maximized)`，并调整窗口边距（最大化时 0，普通时 1px 边框 + 圆角）。
6. 菜单：原 `menuBar()` 改成 titleBar 里的 `menuButton` + QMenu（文件：导出诊断包、退出；帮助：使用说明、关于；界面：启用界面动效 勾选项，默认开，写 `AppSettings` key `motion`）。
7. 动效接线（均先判断 `theme.motion_enabled()`）：首帧窗口 `fade_in`；`adv_panel` 展开/收起走 `animate_expand`；`pb_folder/pb_page` 的 `setValue` 走 `animate_progress`；卡片 `attach_card_shadow`（gb_base/gb_targets/adv_panel 内两组、actionBar）；行内错误 `fade_widget`。
8. 启动日志：`_log_theme_state()` 增加字体行：「界面字体：HarmonyOS Sans SC（内置）」/「界面字体：系统回退」与「界面动效：开/关」。
9. 保留全部既有属性名与行为（tests 依赖）：`lb_expect`、`lb_inline_error`、`btn_start`、`btn_cancel`、`cb_dryrun`、`adv_panel`、`btn_advanced`、`scroll_left`、`pb_folder`、`pb_page`、`lb_prog_folder`、`lb_prog_page`、`txt_log`、`lb_target_status`、`lb_state`、`lb_engine`、`lb_longpath`、`lb_version`、`_set_targets_checked`、`_build_config`、`_on_finished`、`smoke`。
10. `tests/test_results_dialog.py:313` 的 `win.statusBar() is not None` 由 C 改为断言 `win.statusBarCustom is not None`（B 提供该属性）。

## 六、C 的测试要求

- `tests/test_ui_theme.py`：按新 TOKENS 断言（竹绿主色、暖纸底、radius-lg=14px）、字体注册成功（`ui_font_family()` 含 "HarmonyOS"）、`motion_enabled()` 受 `A4_MOTION=0` 控制、动画函数在关闭动效时同步落终态、`attach_card_shadow` 生效（`widget.graphicsEffect()` 非空）。
- `tests/test_gui_smoke.py`：既有断言保持通过（文案/状态行）；新增：窗口 `windowFlags() & Qt.FramelessWindowHint`、`titleBar`/`winMin`/`winMax`/`winClose` 存在且 objectName 正确、双击标题栏后 `isMaximized()`、`statusBarCustom` 存在、`_build_config` 不受影响。
- 所有新用例必须可 headless（offline）运行，禁止弹真实窗口阻塞；`QTest.mouseDClick` 用 `QTest` 同步发送事件即可。
- 严禁把 `_save_settings()` 当断言手段（写会话共享 INI 会污染其它用例）；需要写设置时用 `AppSettings()` 直接读写并在 finally 复原。

## 七、验收（Lead）

`pytest tests/` 全绿（原 103 例 + 新增）→ `pytest tests/test_frozen_exe.py` 全绿 → 重打包 exe → 截图 `docs/shots/main-m9-*.png` → PROGRESS.md 维护记录 9 → 提交 `M9: ...`。
