---
name: A4 合并助手
description: Windows 桌面端 A4 资料合并工具：离线、绿色、花笺式浅色暖纸界面。
colors:
  paper: "#F6F3EC"
  paper-deep: "#EDE7DA"
  surface: "#FFFDF8"
  surface-raised: "#FFFFFF"
  surface-subtle: "#F1ECE1"
  border: "#E3DCCD"
  border-strong: "#C8BFAC"
  ink: "#2B2A26"
  ink-muted: "#6A6559"
  bamboo: "#2D5A3D"
  bamboo-deep: "#1F4229"
  bamboo-soft: "#E6EEE4"
  ok: "#2E7D4F"
  warn: "#8F5A14"
  error: "#B3261E"
  error-bg: "#FBEAE6"
  error-border: "#C0392B"
typography:
  display:
    fontFamily: "HarmonyOS Sans SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "11pt"
    fontWeight: 700
    lineHeight: 1.3
  title:
    fontFamily: "HarmonyOS Sans SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "HarmonyOS Sans SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "HarmonyOS Sans SC, Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 400
    lineHeight: 1.4
  mono:
    fontFamily: "Consolas, HarmonyOS Sans SC, Microsoft YaHei, monospace"
    fontSize: "9pt"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.bamboo}"
    textColor: "{colors.surface-raised}"
    rounded: "{rounded.pill}"
    padding: "8px 30px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.bamboo-deep}"
    textColor: "{colors.surface-raised}"
    rounded: "{rounded.pill}"
  button-primary-disabled:
    backgroundColor: "{colors.border}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.pill}"
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "6px 14px"
    height: "28px"
  input-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "5px 10px"
    height: "28px"
  card:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "14px"
  title-bar:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    height: "40px"
  window-button:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.sm}"
    height: "28px"
    width: "28px"
  window-button-close-hover:
    backgroundColor: "{colors.error}"
    textColor: "{colors.surface-raised}"
  action-bar:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    height: "64px"
  status-bar:
    backgroundColor: "{colors.paper-deep}"
    textColor: "{colors.ink-muted}"
    height: "24px"
  data-table:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    rounded: "0px"
  tab:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    padding: "6px 14px"
---

# Design System: A4 合并助手

> **现状。** M8 的极简浅色皮肤在 M9 升级为「花笺」：暖纸底、竹绿主色、白卡片 + 柔和阴影、
> 无边框自绘标题栏、内置 HarmonyOS Sans SC 中文字体、克制动效。
> 实现侧唯一色值来源是 `app/theme.py` 的 `TOKENS`，样式在 `app/theme.qss`（`$token` 占位符）；
> 本文件 frontmatter 与 `TOKENS` 一一对应，改色两处必须同步（`tests/test_ui_theme.py` 会校验）。
> 主窗口结构截图见 `docs/shots/main-m9-*.png`。

## Overview

**Creative North Star: "花笺"**

界面像一叠放在木案上的信笺：暖纸色的底、白色的卡片、竹绿色的落款。它安静、有纸感，
但绝不花哨——纸的暖、竹的绿、墨的黑，三种材质就够。工具本身不表演，它让人一眼确认
「哪一册成了、哪一册缺页、缺的是哪一页」，然后放心离开。

结构性克制来自场景：使用者是非技术同事，机器在内网、可能没有 WPS、可能不认识任何设计术语。
因此这里没有图标字体、没有 Web 式花哨绘制：标题栏只为一个「拖动窗口」与几个按钮存在，
动效只服务于「界面出现了 / 面板展开了 / 进度推进了」三件事，其余全部交给 Qt 原生控件与键盘导航。

**Key Characteristics:**
- 暖纸 + 竹绿 + 墨色 + 白卡片：四类色共 17 个 token，无渐变、无图片资源。
- 卡片承载一切：每块信息是一张白卡片，10px 圆角 + 1px 发丝线 + 一层柔和阴影。
- 无边框但守规矩：自绘 40px 标题栏、28px 窗口按钮，最大化时圆角与边框归零。
- 中文优先：内置 HarmonyOS Sans SC（可变字重），全中文文案、动词开头。
- 动效克制：120–240ms 淡入 / 展开 / 进度，可一键关闭，关闭后所有动画直接落终态。
- 结果优先：过程信息在日志区（次要），结果用表格与页签（主要）。

## Colors

一套暖纸中性骨架，一种竹绿强调色，一组含义固定的状态色。

### 纸与表面
- **暖纸底** (#F6F3EC)：窗口根容器、标题栏。整个界面的「纸」。
- **暖纸深** (#EDE7DA)：状态栏、表头、按钮按下态、悬停衬底。
- **次级表面** (#FFFDF8)：输入框、下拉列表、日志区、表格隔行。
- **卡片白** (#FFFFFF)：分组卡、动作条、菜单、弹层、主按钮文字。
- **弱化衬底** (#F1ECE1)：进度轨道、滚动槽、禁用控件。

### 线与墨
- **发丝线** (#E3DCCD)：1px 分隔与描边（卡片、动作条、状态栏）。
- **强发丝线** (#C8BFAC)：输入框描边、滚动条、窗口外框。
- **主墨** (#2B2A26)：正文、表格文字、标题（纸底对比 ≈ 12:1）。
- **次墨** (#6A6559)：提示、说明、状态栏（纸底对比 ≈ 5.2:1，达到 AA）。

### 主色：竹绿
- **竹绿** (#2D5A3D)：唯一强调色。主按钮「开始合并」、焦点描边、进度条活跃段、页签下划线。
- **竹绿深** (#1F4229)：主按钮 hover/pressed、开关文字按下态。
- **竹绿浅** (#E6EEE4)：选中/悬停衬底（按钮 hover、列表选中、文本选区）。

### 语义状态色
- **成功绿** (#2E7D4F)：成功状态文字、状态栏 ok 段（纸底对比 ≈ 4.7:1）。
- **警告琥珀** (#8F5A14)：警告与「有跳过」类信息（≈ 5.2:1）。
- **错误红** (#B3261E)：失败状态文字、错误日志行（≈ 5.9:1）。
- **错误红底** (#FBEAE6)：行内错误提示底。
- **错误描边** (#C0392B)：非法输入边框、行内提示边框。

### Named Rules
**The 竹绿唯一规则。** 全界面只有一种强调色（竹绿）。任何新颜色必须先证明它属于「纸/墨/竹绿/语义状态」
之一，否则退回中性纸色；禁止引入第二个彩色主色。

**The 语义独占规则。** 颜色只表达状态，不表达装饰。绿=成功、琥珀=警告/跳过、红=错误、竹绿=主操作/进行中；
跨窗口不得改变含义。

**The 面积十分之一规则。** 单屏内彩色面积不超过 10%；大面积永远交给暖纸与白卡片，颜色只落在文字、描边、
进度条与主按钮上。

## Typography

**Body Font:** HarmonyOS Sans SC（内置 `fonts/HarmonyOS_Sans_SC.ttf`，可变字重，许可证见
`fonts/LICENSE_HarmonyOS_Sans.txt`；注册失败回退 Microsoft YaHei UI / Segoe UI）
**Mono Font:** Consolas（回退 HarmonyOS Sans SC / Microsoft YaHei）

**Character:** 内置中文字体保证在未装任何字体的干净机器上也有统一字形；等宽字体只承担
「需要逐字符核对」的信息——日志、路径、文件大小、时间戳。没有展示型字体，不联网取字体。

### Hierarchy
- **Display** (700, 11pt, 1.3)：标题栏「A4 合并助手」、结果对话框总结标题。
- **Title** (600, 9pt, 1.4)：卡片标题、菜单、状态栏关键段。
- **Body** (400, 9pt, 1.5)：表单标签、按钮、表格正文、对话框文案。
- **Label** (400, 9pt, 1.4, 次墨)：提示行、说明句、副标题、状态栏。
- **Mono** (400, 9pt, 1.4)：日志区、完整路径列、文件大小、耗时。
- 字重只用 400 / 600 / 700 三档；字距一律 normal；不写全大写（中文不适用，英文路径保持原样）。

### Named Rules
**The 等宽只读规则。** 等宽字体只用于「要逐字符核对」的内容（日志、路径、数字），不用于标题或按钮。

## Layout

桌面单窗口，**无边框**，外边距 1px（画外框）+ 内容圆角 14px。

- 窗口默认 **1080×720**，可自由缩放并记忆几何；最小可用宽度按左栏表单（约 400px）＋右栏日志（约 500px）估算。
- 顶部 **40px 自绘标题栏**：左「A4 合并助手」（11pt/700）+ 副标题；右「文件 / 帮助 / 界面」菜单按钮 +
  最小化 / 最大化 / 关闭（各 28×28）。标题栏可拖动、双击最大化，窗口四边 6px 命中可缩放。
- 内容区左右分栏 **3 : 4**（`QSplitter` 可拖拽）：左栏参数（滚动区：基本设置卡片 → 目标文件夹卡片 →
  折叠「高级选项」卡片），右栏执行区（两条进度轨道 + 日志卡片）。
- 底部常驻 **动作条**（白底、顶部发丝线、跨满整宽）：左侧一句话预告 + 行内错误，右侧
  「试运行 / 取消 / 开始合并」。主按钮永远可见，不需要滚动才能开始。
- 最底部 **自绘状态栏**（`statusBarCustom`，暖纸深底、顶部发丝线，24px）：引擎 / 长路径 / 任务状态
  （占满中部、按状态着色）/ 版本号。
- 结果对话框 **1120×640**：顶部总结 + 根目录提示，中部页签表格，底部动作行 + 关闭。
- 间距只取 4 / 8 / 12 / 16 / 24 五档；不写奇数间距，不用绝对定位。
- 无响应式断点：桌面单窗口应用，缩放只改变分栏与日志区高度，不改变结构。高 DPI 由 Qt 自动缩放。

### Named Rules
**The 一屏一动作规则。** 每个窗口只有一个主操作：主窗口是「开始合并」，结果对话框是「关闭」。
其余动作一律次级按钮或菜单项，不得与主按钮抢视觉重量。

**The 标题栏只做三件事规则。** 自绘标题栏只负责：显示应用名、拖动/缩放窗口、放菜单与窗口按钮。
不放大块信息、不放主操作、不做动画展示。

## Elevation & Depth

**卡片浮在纸上，但只浮起一层。** 层次由「1px 发丝线 + 一层柔和阴影」共同建立。

阴影一律由 `theme.attach_card_shadow()` 用 `QGraphicsDropShadowEffect` 提供（QSS 不做 box-shadow，
Qt 也不支持）；三档强度：

| 档位 | 模糊半径 | 纵向偏移 | 黑色不透明度 | 用途 |
| --- | --- | --- | --- | --- |
| `card` | 20px | 5px | 34/255 | 分组卡、动作条（默认） |
| `raised` | 28px | 8px | 44/255 | 悬停加深、浮起卡片 |
| `float` | 40px | 12px | 58/255 | 菜单、弹层、对话框 |

- 悬停时由 `card` 平滑过渡到 `raised`（160ms），离开再回落。
- 阴影永远中性黑，不用彩色阴影；文字、按钮、表格行不加阴影。
- 卡片在滚动区内只保留一层 effect（不叠加），滚动时阴影由子控件自身绘制。

**The 一层阴影规则。** 需要区分层次时，先加 1px 发丝线，再考虑一层阴影；永远不叠两层阴影，
也不给非容器控件加阴影。

## Shapes

- 窗口圆角 **14px**（最大化时归零、外框去掉）；卡片圆角 **10px**；输入框/按钮/菜单项圆角 **6px**。
- 主按钮是**胶囊**（pill）：高 44px、圆角取半高 22px 绘制（Qt 画不出 999px，token 里语义值仍为 999px）。
- 表格、页签内容区、日志区保持**直角或 10px**——像档案格里的一张张纸，不做全圆角。
- 描边统一 1px；不使用双线、粗描边、虚线框；复选框/单选框是「1px 描边 → 竹绿实心 + 白色勾/白点」。
- 分隔只用水平发丝线；竖向分隔交给分栏拖拽手柄与留白。

## Motion

动效只服务于「状态变化被看见」，全部可一键关闭（界面「界面 → 启用界面动效」或环境变量 `A4_MOTION=0`）；
关闭后所有动画函数**同步落到终态**，不创建动画对象。

| 场景 | 时长 | 曲线 | 实现 |
| --- | --- | --- | --- |
| 窗口首帧淡入 | 180ms | OutCubic | `theme.fade_in(window)` |
| 行内错误/提示淡入 | 160ms | OutCubic | `theme.fade_widget(widget)` |
| 高级选项面板展开/收起 | 200ms | OutCubic | `theme.animate_expand(panel, expanded)` |
| 进度条推进 | 240ms | OutCubic | `theme.animate_progress(bar, value)` |
| 卡片悬停阴影加深 | 160ms | OutCubic | `theme.attach_card_shadow(widget)` 内部 |

**The 三件事规则。** 只允许「出现 / 展开 / 推进」三类动效；不做弹跳、旋转、闪烁、连续呼吸，
不做页面切换动画。

## Components

### Title Bar（自绘标题栏，M9 新增）
- **Shape:** 高 40px，背景 = 暖纸底，无边框；鼠标左键拖动调用 `startSystemMove()`，双击切换最大化。
- **Title:** `titleText` 11pt/700 主墨 + `titleSub` 9pt 次墨（「把一叠资料，合成一册 A4」）。
- **Menu:** `menuButton`（QToolButton）文字按钮「文件 / 帮助 / 界面」，无边框、hover 竹绿浅底。
- **Window Buttons:** `winMin`/`winMax`/`winClose`，28×28、无边框、hover 竹绿浅底；
  `winClose` hover 红底白字（唯一允许的红色面）。

### Buttons
- **Primary（开始合并）:** 竹绿实心 + 白字胶囊，总高 44px、最小宽度 180px，固定在动作条右侧；
  默认按钮（回车触发）。hover/pressed 加深为竹绿深，禁用为发丝线底 + 次墨字。
- **Secondary（取消 / 浏览… / 导出… / 打开…）:** 白底 + 主墨字 + 1px 强发丝线，高度 28px、内边距 6×14px；
  hover 竹绿浅底 + 竹绿描边。
- **Text（advancedToggle / menuButton）:** 无边框、竹绿文字，箭头随展开旋转（由 B 用文字箭头实现）。
- **Focus:** 统一 1px 竹绿描边，不加发光。

### Cards（`cardBox`）
- **Corner Style:** 10px；**Background:** 卡片白；**Border:** 1px 发丝线；**Padding:** 14px；
  **Shadow:** `card` 档（悬停 `raised`）。
- 标题只写名词短语（「基本设置」「目标文件夹」「高级选项」），不加图标、不加副标题。

### Action Bar（`actionBar`）
- 白底、顶部 1px 发丝线、底部随窗口圆角；左侧 `expectLabel` 预告一句话 + `inlineError` 行内红字，
  右侧「试运行」勾选 + 取消 + 主按钮。行内错误替代可预期校验的模态弹窗。

### Status Bar（`statusBarCustom`，M9 新增自绘）
- 暖纸深底、顶部发丝线，24px；四段：引擎探测 / 长路径状态 / 任务状态（占满中部、按状态着色）/
  版本号（常驻右侧）。任务状态文字是全局唯一的「现在怎么样」，必须永远是句子。

### Inputs / Fields
- **Style:** 次级表面底 + 1px 强发丝线 + 6px 圆角；文本主墨 9pt；占位文本次墨。
- **Focus:** 1px 竹绿描边，禁止光晕。
- **Error:** 错误描边 + 错误红底，错误说明写在旁边 9pt 次墨文字里，不用弹窗打断。
- **Disabled:** 弱化衬底 + 次墨字（如模式 A 下的「输出目录」输入框）。
- **下拉箭头:** 透明的 `::drop-down` + `app/assets/chevron-down.png`（12×12 次墨小箭头），
  不交给系统绘制（系统会在圆角边框上压一个带灰底、直角的按钮）。

### Checkboxes / Radios
- **Style:** 14×14 方框/圆框，1px 强发丝线；hover 竹绿描边。
- **Checked:** 竹绿实心 + 白色勾（`app/assets/check-white.png`）/ 白色圆点（`radio-dot.png`）。
- **Why 图标:** Qt 一旦给 indicator 设了 background 就不再画系统勾形，必须自己补一个透明底小图标；
  图标由 Pillow 以 4 倍超采样生成，可在 `app/assets/` 用脚本重建。图标目录缺失时 QSS 自动退化为纯色块。
- 目标文件夹列表里的勾选框沿用同一套外观（`QListWidget::indicator` + 白色勾）。

### Data Tables（结果对话框核心组件）
- **Style:** 卡片白底、无竖向网格线、隔行次级表面、1px 表头下边线；表头次墨 9pt 600、暖纸深底。
- **Behavior:** 整行选择、不可编辑、双击行在资源管理器中定位（产品标志性交互）。
- **Columns:** 「目标文件夹 / 页数 / 文件大小 / 输出路径」——可扫描、可核对、可复制。

### Tabs（结果对话框）
- **Style:** 无边框页签，当前页签竹绿下划线（2px）+ 主墨文字；其余页签次墨文字；hover 竹绿浅底。
- **Labels** 带计数，如「成功（3）」「失败（2）」「跳过的 Excel（1）」——数量本身就是信息。

## Do's and Don'ts

### Do:
- **Do** 全中文：按钮动词开头（「开始合并」「打开输出目录」「导出失败清单 TXT…」），错误句先讲原因再讲下一步。
- **Do** 保持「暖纸 + 白卡片 + 竹绿」三件套：新增界面先想「它是不是一张纸上的卡片」。
- **Do** 用表格 + 页签承载结果，用计数标签（`成功（3）`）让人不点开就知道规模。
- **Do** 让状态色语义固定：绿=成功、琥珀=警告/跳过、红=错误、竹绿=主操作/进行中；跨窗口不得改含义。
- **Do** 用 1px 发丝线、8px 网格、10px 卡片圆角建立秩序。
- **Do** 保留 Qt 原生的键盘导航、高 DPI 缩放，以及无边框窗口的拖动/缩放/最大化可用性。
- **Do** 数字、路径、体积、耗时用等宽字体，保证可核对。
- **Do** 主操作按钮常驻位置固定、竹绿胶囊、回车可触发。

### Don't:
- **Don't** 引入图标字体或外部图片作为 UI 资源（图标仅限 exe/窗口图标一个 .ico）；箭头、加号等用文字字符。
- **Don't** 用渐变、模糊、发光制造「高级感」；阴影只用 `attach_card_shadow` 的一层中性黑。
- **Don't** 大面积铺状态色（整行红底、整块绿底），颜色只做小面积强调（红线白字也仅限关闭按钮 hover）。
- **Don't** 增加第二个强调色或第二套色板；需要区分时用纸色层次与字重。
- **Don't** 把关键操作做成只有图标的按钮，或藏进右键菜单。
- **Don't** 改动结果对话框的四个默认页签顺序（成功 → 失败 → 跳过的成品 → 忽略的类型），
  可选页签（如「跳过的 Excel」）只能插在「跳过」类页签之间且仅在被启用时出现。
- **Don't** 用弹窗替代可解释的失败信息：失败优先落进清单与日志，弹窗只用于无法继续的阻断性错误。
- **Don't** 在无边框窗口里省掉拖动/缩放/最大化的鼠标命中区（自绘了标题栏，就必须把系统交互补回来）。

## 实现映射（M9 已落地）

| 设计物 | 代码位置 | 说明 |
| --- | --- | --- |
| 颜色 / 圆角 / 间距 / 动效 token | `app/theme.py` 的 `TOKENS` | 与本文件 frontmatter 一一对应（17 色），改色两处同步 |
| 公开 API | `app/theme.py` | `color/load_qss/ensure_fonts/ui_font_family/apply/motion_enabled/set_motion_enabled/fade_in/fade_widget/animate_progress/animate_expand/attach_card_shadow/set_maximized_chrome` |
| 控件样式 QSS | `app/theme.qss` | 只用 `$token`；主窗口、无边框窗口壳、结果对话框、菜单、表格统一 |
| 内置字体 | `fonts/HarmonyOS_Sans_SC.ttf` | `ensure_fonts()` 用 `QFontDatabase.addApplicationFont` 注册；打包时由 spec datas 收进 `fonts/` |
| UI 小图标 | `app/assets/`（check-white / check-dark / radio-dot / chevron-down） | Pillow 4 倍超采样生成（脚本见 `.tmpx/make_assets.py`）；`load_qss()` 把 `$assets` 换成绝对路径，缺失时自动删掉 `image:` 声明退化 |
| 下拉箭头 / 勾选态 | `app/theme.qss` | `QComboBox::drop-down` 透明 + `down-arrow` 图标；勾选态用 14×14 透明底勾图标（不可用 `QComboBox:hover::down-arrow` 组合选择器，Qt 会重复绘制） |
| 无边框窗口 / 标题栏 | `app/ui_main.py` | `windowShell`、`titleBar`、`titleText/titleSub`、`menuButton`、`winMin/winMax/winClose`、`statusBarCustom` |
| 卡片阴影 / 动效接线 | `app/ui_main.py` | `theme.attach_card_shadow` / `fade_in` / `animate_expand` / `animate_progress` |
| 行内提示 | `app/ui_main.py` | `_set_inline_error` / `inlineError`，替代可预期校验的模态弹窗 |
| 语义色引用 | `app/ui_main.py`、`app/results_dialog.py` | 一律 `theme.color(...)`，不写十六进制 |
| 回归测试 | `tests/test_ui_theme.py` 等 | token 一致 / 字体注册 / 动效开关 / 阴影生效 / 无边框标题栏 |
| 视觉证据 | `docs/shots/main-m9-*.png` | M9 改版后主窗口（改版前：`main-after-*.png`） |
