---
name: A4 合并助手
description: Windows 桌面端 A4 资料合并工具：离线、绿色、极简。
colors:
  surface: "#ffffff"
  surface-subtle: "#f7f8fa"
  border: "#d9dde3"
  ink: "#333333"
  ink-muted: "#555555"
  accent: "#1565c0"
  accent-deep: "#0d47a1"
  ok: "#1e7d32"
  warn: "#b26a00"
  error: "#c62828"
  error-bg: "#fdecea"
  error-border: "#c0392b"
typography:
  display:
    fontFamily: "Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "11pt"
    fontWeight: 700
    lineHeight: 1.3
  title:
    fontFamily: "Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Microsoft YaHei UI, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 400
    lineHeight: 1.4
  mono:
    fontFamily: "Consolas, Microsoft YaHei, monospace"
    fontSize: "9pt"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "4px"
  md: "6px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "8px 20px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.accent-deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
  button-primary-disabled:
    backgroundColor: "{colors.border}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.sm}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "6px 14px"
    height: "28px"
  input-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
    height: "28px"
  group-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px"
  data-table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "0px"
  tab:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-muted}"
    padding: "6px 14px"
---

# Design System: A4 合并助手

> **现状与方向。** 结构（Qt 原生控件、左右分栏、分组表单、表格+页签结果对话框）在 v1.0.2 已上线；
> 语义色中有 8 处以内联样式落地（状态栏、日志着色、模板校验红框、对话框标题与提示）。
> 本次与用户确认的方向是**极简浅色轻量皮肤**（统一 QSS，系统蓝作唯一强调色），尚未实现。
> 本文件同时记录「已落地」值与「方向」值；实现皮肤时以本文件为准，不得自创第二套色板。

## Overview

**Creative North Star: "安心档案柜"**

界面是一排安静的档案抽屉：每一项任务都有明确的位置、明确的当前状态、明确的归属。工具本身不表演，
它让人一眼确认「哪一册成了、哪一册缺页、缺的是哪一页」，然后放心离开。视觉上极简——白底、发丝线、
一层极浅的中性底色，加上极少量、含义固定的状态色。

结构性克制来自场景：使用者是非技术同事，机器在内网、可能没有 WPS、可能不认识任何设计术语。
因此这里没有自绘控件、没有图标字体、没有动效表演；层次只靠间距、字重与 1px 描边建立，
键盘操作、高 DPI、系统主题、辅助技术全部交给 Qt 原生实现。

**Key Characteristics:**
- 极简浅色：白底 + 一层 `#f7f8fa` 中性衬底 + `#d9dde3` 发丝线；无渐变、无阴影。
- 语义色固定：蓝＝进行中/主操作，绿＝成功，琥珀＝警告，红＝错误；面积永远小于屏幕的 10%。
- 结构原生：Qt Widgets 默认行为（菜单栏、状态栏、分栏、表格、页签），不自绘。
- 中文优先：所有文案短句、动词开头；数字与路径用等宽字体承载。
- 结果优先：过程信息在日志区（次要），结果用表格与页签（主要）。

## Colors

一套极简的中性骨架，加一组含义固定的状态色；强调色只有一种蓝。

### Primary
- **系统任务蓝** (#1565c0)：唯一强调色。用于主操作按钮「开始合并」、执行中状态文字、进度条活跃段、焦点描边。已落地（状态栏 busy）。
- **系统任务蓝·深** (#0d47a1)：主按钮的 hover/pressed 与链接态。方向值（随 QSS 落地）。

### Neutral
- **纸白** (#ffffff)：窗口、表格、输入框底色。已落地（Qt 默认）。
- **抽屉衬底** (#f7f8fa)：分组框内底、日志区底、表格隔行。方向值；现为 Qt 默认底色。
- **发丝线** (#d9dde3)：1px 分隔线、输入框/表格边框、分组边界。方向值；现为 Qt 默认边框。
- **主墨** (#333333)：正文与表格文字。已落地。
- **次墨** (#555555)：提示、说明、状态栏次要段、对话框根目录行。已落地。

### Semantic
- **成功绿** (#1e7d32)：成功状态文字、状态栏 ok 段。已落地。
- **警告琥珀** (#b26a00)：警告与「有跳过」类信息。已落地。
- **错误红** (#c62828)：失败状态文字、错误日志行。已落地。
- **校验红** (#c0392b)：非法输入描边。已落地。
- **校验红底** (#fdecea)：非法输入背景。已落地。

### Named Rules
**The 语义独占五色规则。** 颜色只表达状态，不表达装饰。全界面只允许五个语义色（蓝/绿/琥珀/红/中性墨），
任何新增颜色必须先证明它属于其中之一，否则用中性灰。

**The 面积十分之一规则。** 单屏内彩色面积不超过 10%；大面积永远交给白与浅灰，颜色只落在文字、描边与小图标上。

## Typography

**Body Font:** Microsoft YaHei UI（回退 Segoe UI / 系统 UI 字体）
**Mono Font:** Consolas（回退 Microsoft YaHei）

**Character:** 系统 UI 字体负责一切可读性；等宽字体只承担「需要逐字符核对」的信息——日志、路径、文件大小、
时间戳。没有展示型字体，也不引入任何网络字体。

### Hierarchy
- **Display** (700, 11pt, 1.3)：仅用于结果对话框的总结标题（「处理完成：成功 3/5 个目标…」）。已落地。
- **Title** (600, 9pt, 1.4)：分组框标题、对话框标题、状态栏关键段。Qt 默认字重的微调目标。
- **Body** (400, 9pt, 1.5)：表单标签、按钮、表格正文、对话框文案。已落地（Windows 默认 UI 字号）。
- **Label** (400, 9pt, 1.4, 次墨)：提示行、说明句、拖动提示、日志行内补充说明。已落地。
- **Mono** (400, 9pt, 1.4)：日志区、完整路径列、文件大小、耗时。已落地（日志区）。
- 字重只用 400 / 600 / 700 三档；字距一律 normal；不写全大写（中文不适用，英文路径保持原样）。

### Named Rules
**The 等宽只读规则。** 等宽字体只用于「要逐字符核对」的内容（日志、路径、数字），不用于标题或按钮。

## Layout

桌面单窗口，左右分栏：**左 2 : 右 3**（`QSplitter` 可拖拽）。

- 窗口默认 **1080×720**，可自由缩放并记忆几何；最小可用宽度按左侧表单（约 400px）＋右侧日志（约 500px）估算。
- 左侧参数区：纵向堆叠 3 个分组框——「基本设置 / 排版与转换 / 加密文件」，内边距 6px，分组间距 8px；
  表单统一 `QFormLayout`，标签右对齐，行间距走 8px 网格。
- 右侧执行区：动作行（主按钮 + 取消 + 仅预览）→ 两条进度（文件夹 / 页面）→ 日志区（占满剩余高度）。
- 结果对话框：**1120×640**，顶部一行总结 + 一行根目录提示，中部页签表格，底部动作行 + 关闭。
- 间距只取 4 / 8 / 12 / 16 / 24 五档；不写奇数间距，不用绝对定位。
- 无响应式断点：这是桌面单窗口应用，缩放只改变分栏与日志区高度，不改变结构。高 DPI 由 Qt 自动缩放。

### Named Rules
**The 一屏一动作规则。** 每个窗口只有一个主操作：主窗口是「开始合并」，结果对话框是「关闭」。
其余动作一律次级按钮或菜单项，不得与主按钮抢视觉重量。

## Elevation & Depth

**扁平。没有阴影，没有渐变，没有浮层投影。**

层次靠三件事建立：1px 发丝线（`#d9dde3`）、一层极浅中性衬底（`#f7f8fa`）、以及字重与间距。
对话框与主窗口同层平铺，不再叠投影；焦点状态用 2px 任务蓝描边表达（方向值，现为 Qt 默认点线焦框）。

**The 发丝线规则。** 需要区分两个区域时，先加 1px 线，再考虑加底色；永远不通过阴影制造层次。

## Shapes

- 控件圆角 **4px**（按钮、输入框、下拉框、复选焦点态）；容器圆角 **6px**（分组框、卡片）；仅方向值，现为 Qt 原生圆角。
- 表格、日志区、页签内容区保持**直角**（0px），像档案格里的一张张纸。
- 描边统一 1px；不使用双线、粗描边、虚线框；不使用胶囊形、圆形按钮。
- 分隔只用水平发丝线；竖向分隔交给分栏拖拽手柄与留白。

## Components

### Buttons
- **Shape:** 4px 圆角，1px 描边（次级）或无描边（主操作）。
- **Primary（开始合并）:** 任务蓝底 + 白字，最小高度 **40px**，占动作行主宽度；默认按钮（回车触发）。
- **Secondary（取消 / 浏览… / 导出… / 打开…）:** 白底 + 主墨字 + 发丝线描边，高度 28px，左右内边距 14px。
- **Hover / Focus:** hover 加深（蓝 → `#0d47a1`）；focus 用 2px 任务蓝描边，不加发光。
- **Disabled:** 发丝线底 + 次墨字，不可点击但保留在布局中（不做隐藏）。

### Inputs / Fields
- **Style:** 白底 + 1px 发丝线 + 4px 圆角；文本主墨 9pt；占位文本用次墨。
- **Focus:** 1px 任务蓝描边，禁止用光晕。
- **Error:** 校验红描边（`#c0392b`）+ 校验红底（`#fdecea`），错误说明写在旁边 9pt 次墨文字里，不用弹窗打断。
- **Disabled:** 底色不变、文字变次墨（如模式 A 下的「输出目录」输入框）。

### Data Tables（结果对话框核心组件）
- **Style:** 白底、无竖向网格线、隔行 `#f7f8fa`、1px 表头下边线；表头次墨 9pt 600。
- **Behavior:** 整行选择、不可编辑、双击行在资源管理器中定位（这是产品的标志性交互）。
- **Columns:** 「目标文件夹 / 页数 / 文件大小 / 输出路径」——可扫描、可核对、可复制。

### Tabs（结果对话框）
- **Style:** 无边框页签，当前页签任务蓝下划线（2px）+ 主墨文字；其余页签次墨文字。
- **Labels** 带计数，如「成功（3）」「失败（2）」「跳过的 Excel（1）」——数量本身就是信息。

### Group Containers（分组框）
- **Corner Style:** 6px；**Background:** 白；**Border:** 1px 发丝线；**Internal Padding:** 12px。
- 标题只写名词短语（「基本设置」「排版与转换」「加密文件」），不加图标、不加副标题。

### Status Bar & Log Pane（本产品的两个签名组件）
- **Status Bar:** 分四段——引擎探测结果 / 长路径状态 / 任务状态（占满中部，按状态着色）/ 版本号（常驻右侧）。
  任务状态文字是全局唯一的「现在怎么样」，必须永远是句子（「就绪」「正在合并…」「成功 2/2」）。
- **Log Pane:** 等宽 9pt、只读、最多 5000 块自动截断、按级别着色（info 主墨 / ok 绿 / warn 琥珀 / error 红）、
  自动滚动到底部；溢出内容靠滚动而不是缩小字号。

## Do's and Don'ts

### Do:
- **Do** 全中文：按钮动词开头（「开始合并」「打开输出目录」「导出失败清单 TXT…」），错误句先讲原因再讲下一步。
- **Do** 用表格 + 页签承载结果，用计数标签（`成功（3）`）让人不点开就知道规模。
- **Do** 让状态色语义固定：绿=成功、琥珀=警告/跳过、红=错误、蓝=进行中；跨窗口不得改含义。
- **Do** 用 1px 发丝线与 8px 网格拉开层次，保持扁平。
- **Do** 保留 Qt 原生的键盘导航、菜单栏、状态栏、高 DPI 缩放与系统主题跟随能力。
- **Do** 数字、路径、体积、耗时用等宽字体，保证可核对。
- **Do** 主操作按钮常驻位置固定、高度 40px、回车可触发。

### Don't:
- **Don't** 自绘无边框窗口、自绘按钮、引入图标字体或外部图片作为 UI 资源（图标仅限 exe/窗口图标一个 .ico）。
- **Don't** 用阴影、渐变、模糊、动画过渡制造「高级感」——极简靠留白与秩序，不靠特效。
- **Don't** 大面积铺状态色（整行红底、整块蓝底），颜色只做小面积强调。
- **Don't** 增加第二个强调色或第二套色板；需要区分时用中性灰层次。
- **Don't** 把关键操作做成只有图标的按钮，或藏进右键菜单。
- **Don't** 改动结果对话框的四个默认页签顺序（成功 → 失败 → 跳过的成品 → 忽略的类型），
  可选页签（如「跳过的 Excel」）只能插在「跳过」类页签之间且仅在被启用时出现。
- **Don't** 用弹窗替代可解释的失败信息：失败优先落进清单与日志，弹窗只用于无法继续的阻断性错误。
