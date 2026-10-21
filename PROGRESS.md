# A4 合并助手 —— 开发进度记录（PROGRESS.md）

> 跨会话接力文件：每个新会话先读本文件 + docs/A4合并应用开发计划.md。
> 每完成一个里程碑：pytest 全绿 → git commit（+tag）→ 更新本文件 → 四段式汇报。

---

## 总览

| 里程碑 | 状态 | 备注 |
|---|---|---|
| M0 环境准备 | ✅ 完成（tag: m0） | 2026-02 基线建成 |
| M1 核心重构 | ✅ 完成（tag: m1） | 2026-10 pytest 28/28 全绿 |
| M2 GUI 骨架 | ✅ 完成（tag: m2） | 2026-10 pytest 37/37 全绿 |
| M3 后台执行 | ✅ 完成（tag: m3） | 2026-10 pytest 43/43 ×2 遍稳定 |
| M4 结果体验 | ✅ 完成（tag: m4） | 2026-10 pytest 58/58 ×4 遍稳定 |
| M5 打包交付 | ✅ 完成（tag: m5） | 2026-10 pytest 67/67 稳定；异机人工验收（A机绿色/B机无WPS）**已通过** |
| M6 灰度试运行 | ✅ 完成（tag: m6） | 2026-10 试点一周**无阻塞性报障**，验收通过 → 全员铺开 |

## 环境说明（M0 结论）

- **开发/打包环境**：全局 Python 3.12.10（`C:\Users\25792\AppData\Local\Programs\Python\Python312\python.exe`）
  - 沙箱下 venv 的 ensurepip（chmod）一度失败；完全权限放开后本可重建，但全局环境已装齐且验证可用，为一致性采用全局环境。
  - 工程内不再使用 .venv；后续所有命令统一用该 python。
- **版本锁定**：`requirements.txt`（运行时 5 个）+ `requirements-dev.txt`（测试/打包/样例生成）。全为 pip freeze 实际版本。
- **关键版本**：pypdf==6.19.0（正是用户报 KeyError 的版本，容错直接在此版本验证）、PySide6==6.12.0、PyInstaller==6.22.3。
- **中文字体**：fonts/NotoSansCJKsc-Regular.otf（16.4MB，OFL 授权，GitHub notofonts/noto-cjk 下载），fpdf2 加载验证通过。
- **git**：流水线 → `git commit -m "M{n}: ..."` + 里程碑 tag。已存在 tag：baseline-v0（初始基线）、m0。

## 样例与验证（M0 成果）

- `tests/make_samples.py`：幂等生成 32 个样例文件，覆盖 8 个场景目录：
  pure_pdf / mixed（docx·xlsx·pptx·jpg·GBK txt）/ encrypted（密码 123456）/ corrupted（坏批注 PDF）/ duplicate（同名"张三"×2 父目录）/ misc（空目录·不支持类型·【合并】旧成品·旧命名成品）/ images（EXIF orientation=6）
- **坏批注样例已验证**：手写构造（子段式 xref、/Annots→47 号对象= /Type /XRef 字典），
  在 pypdf 6.19.0 下 `merge_transformed_page` 稳定复现 `KeyError: '/Rect'`，无警告。
- EXIF=6、GBK 可解、加密 PDF is_encrypted=True 均已验证。
- 基线脚本 dry-run 冒烟通过（中文路径、自然排序、2 目标文件夹枚举正确）。

## M1 成果（核心重构，2026-10）

- **core 包**（不依赖 Qt，回调化）：
  - util.py（自然排序/控制台/PowerShell 查找）、types.py（MergeConfig/回调接口/FolderResult）、
    deps.py（frozen 分流）、encrypt.py（PDF/Office 加密检测与解密）、
    collect.py（收集/排除规则/双模式输出计划 plan_outputs/冲突序号消解）、
    converters/{base,manager,backend_wps,backend_native}.py。
  - backend_wps.py：WPS_WORKER_PS **原样迁移** + Popen 轮询版 run_wps_worker（取消 terminate，≤0.2s 响应）。
  - backend_native.py：图片 Pillow（exif_transpose 保留）+ 文本 fpdf2（编码探测 GBK→GB18030 + 开源字体）。
  - merge.py：原样迁移 fit_box/merge_to_a4 + **3.10 三层容错**（_sanitize_annots 无效批注剥离 + 页级隔离 + 文件级隔离）。
  - report.py：合并报告.txt（UTF-8-sig）。runner.py：双模式/--only（相对路径+歧义报错）/取消/失败清单。
- **cli.py**：legacy 全部参数兼容 + 新增 --output-dir / --only / --engine / --no-report / --version。
- **pytest 28/28 全绿**（14 秒基线）：内容级一致对照（cli vs legacy）、黄金样本（A4 尺寸/页数）、
  坏批注修复、43 文件不连坐、截断文件隔离、加密有/无密码、模式B 统一/冲突序号/防套娃、
  报告防误扫、lookalike 两级场景、--only 歧义、模板校验、GBK 解码、自然排序、WPS 全链路集成（本机实转）。
- **M1 验收对照结果**：新 cli 与 legacy 对同一 pure_pdf 输入产出**内容级一致**（页数/每页尺寸/内容流 hash 全同）。
- mixed 全链路实测：WPS 真实转换 docx/xlsx/pptx/jpg/GBK txt 成功，3 目标 3 成品 + 报告。

## M2 成果（GUI 骨架，2026-10）

- **app 包**：main.py（单实例 QSharedMemory + QLocalServer 激活已有窗口 + --smoke 冒烟模式）、
  ui_main.py（参数表单：根目录/目标勾选/输出双模式联动/模板实时校验红框/引擎下拉/密码列表/
  日志区着色+容量截断+自动滚动/两级进度条/菜单：诊断导出·关于）、settings.py（QSettings 记忆，
  类型韧性读取 get_bool/get_int）、worker.py（QThread 桥接 core.runner 信号，M3 完善取消/密码弹窗）、
  diagnostics.py（debug 日志落盘 %LOCALAPPDATA%\\A4合并助手\\logs、excepthook 可开关弹框、诊断包 zip：
  日志+配置[密码脱敏]+引擎探测+系统信息）。
- **测试**：test_gui_smoke（控件/模板校验/模式联动/目标刷新/诊断包/日志落盘）、
  test_app_smoke（进程级 GUI 冒烟 --smoke、单实例锁第二实例快速退出）。
- **踩坑记录**：① QSettings 注册表 bool 漂移成 str → get_bool 韧性读取；② 无头环境 excepthook
  弹模态框卡死 → install_excepthook(dialog=False) 用于 smoke；③ 测试弹 QMessageBox 会挂 → monkeypatch。
- GUI 真机显示效果留给 M6 灰度确认（offscreen 冒烟已验证逻辑）。

## M3 计划（下一里程碑）

Worker 完善：取消时终止 WPS 子进程（core 已支持 cancel 回调）、密码弹窗（ask_password 信号 →
模态输入框，3 次重试，回车跳过）、密码记住走 DPAPI（ctypes CryptProtectData，3.11.9）。

## M3 成果（后台执行，2026-10）

- **core/dpapi.py**：ctypes 直调 CryptProtectData/CryptUnprotectData（零依赖）；非 Windows 退化
  base64 明文（"*" 前缀标记）；测试：往返一致、Windows 密文不含明文。
- **runner.py**：WPS 重试过滤新增"已取消"（取消后不再空等重试轮）。
- **worker.py**：密码弹窗跨线程回调——password_requested 信号 + submit_password(Event) 回传，
  等待期间可被取消打断；cancel() 置位（core 侧轮询到后立即 terminate WPS 子进程，3.11.4）。
- **ui_main.py**：密码输入槽（QInputDialog 3 次重试/取消=跳过，密码正确回显日志）；
  "记住密码"复选框（DPAPI 加密存 QSettings，本机可解拷贝无效；取消勾选即清除）。
- **测试**：test_dpapi（4 例）、test_worker（取消快速结束 <10s / 密码流程 3 页 / 跳过 1 页+failure）；
  稳定性加固：offscreen 子进程偶发崩溃 → smoke 重试 3 次；worker 流程断言收敛到最终结果。
- **全量验证**：43 passed ×2 遍（28~31s）。

## M4 成果（结果体验，2026-10，tag: m4）

- **app/results_dialog.py（新增）**：完成总结对话框（计划 2.2「完成总结对话框」）
  - 头部：成功 N/M 个目标、共 X 页、失败 Y 个文件、耗时；根目录 + 输出目录一行；
  - 页签①成功：目标文件夹 / 页数 / 文件大小（真实体积，预览模式显示"—（预览）"）/ 输出路径，双击定位成品；
  - 页签②失败：目标 / 文件名 / 原因 / 跳过页数 / 完整路径，另列「未生成的目标文件夹」，双击 `explorer /select` 定位；
  - 页签③跳过的成品：被当作上次产物的同名 PDF + 中文提示（勾选「同名成品」即可并入）；
  - 页签④忽略的类型：不支持类型清单 + 「无素材，未生成」的目标文件夹；
  - 按钮：打开输出目录（模式B→输出目录；模式A→根目录）、打开运行报告、导出失败清单 TXT、导出运行总结 TXT（UTF-8-sig，记事本可读）、关闭；
  - 纯函数 `build_failures_text` / `build_summary_text` / `format_size` / `safe_size` / `output_dir_for` 与 GUI 解耦，便于单测。
- **app/ui_main.py**：`_on_finished` 用完整对话框替换 M2 简版 QMessageBox；
  状态栏拆为三段（引擎探测 / 任务状态[着色] / 版本号，计划 2.2 + 3.11.10）；
  运行结束同步保存配置记忆；`smoke` 模式下结果对话框不阻塞 exec。
- **测试 tests/test_results_dialog.py（15 例）**：大小格式化、模式定位、四页签计数与内容、
  双击定位（monkeypatch 拦截，不真开资源管理器）、导出两份 TXT（校验 BOM/内容）、
  预览模式文案、空清单提示、状态栏三要素、`None` 结果中文提示，
  以及 **GUI 驱动的真实端到端**：填根目录 → `_start()` → worker 完成 → 结果对话框显示真实页数/体积/输出路径。
- **全量验证**：58 passed ×4 遍稳定（29~35s）。

## M5 成果（打包交付，2026-10，tag: m5）

- **产物**：`dist/A4合并助手.exe`（78.3 MB，onefile + windowed 无控制台黑框；
  PE 子系统 = 2 已由测试断言）。打包命令（工程根目录，全局 Python 3.12.10）：
  `python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyi_work build\a4merger.spec`
- **build/a4merger.spec**：version resource 1.0.0.0、longPathAware+DPI manifest、
  `fonts/NotoSansCJKsc-Regular.otf` 进 datas、隐藏导入 pypdf/PIL/fpdf/msoffcrypto、
  剪掉 QtWebEngine/QtQuick 等无用模块；构建时间戳临时写入 `app/diagnostics.py`，
  **try/finally 保证打包后还原**（仓库不被污染）。
- **踩坑记录（都已在代码注释里写明）**：
  1. manifest 里**不要**写 `assemblyIdentity` → 否则 SideBySide 错误 WinError 14001，exe 无法启动；
  2. **不要排除 `unittest`** → fpdf2 的 `fpdf/sign.py` 依赖它，排除后 `import fpdf` 失败、
     "纯 Python 引擎"整体失效（无 WPS 机器直接不可用）；`tests/test_frozen_exe.py` 已加回归；
  3. PyInstaller onefile 依赖可写的 `%TEMP%`；本机沙箱不放开该目录时启动会报
     `[PYI-xxxx:ERROR] Could not create temporary directory!`（测试把 TMP/TEMP 指向工作区内）；
  4. 打包版退出阶段曾在 onefile 下偶发 0xC0000409 → `app/main._finish()` 显式释放单实例锁 +
     `logging.shutdown()` + 打包版 `os._exit(rc)`；正常使用（非 --smoke）不受影响；
  5. 对 GUI 子系统 exe 用 `stderr=PIPE` 抓输出会随机卡住 → 测试统一重定向到文件。
- **core/longpath.py（计划 3.11.3）**：`LongPathsEnabled` 注册表探测、启动中文提示
  （未开启时提示"路径超过 260 字符可能无法处理"）、`\\?\` 扩展路径工具、超长路径中文报错文案；
  状态栏新增「长路径：已开启/未开启」指示。
- **app/diagnostics.py**：构建时间（打包写入）、frozen 标记、依赖版本、长路径状态、诊断包系统信息；
  关于对话框显示版本号/构建时间/依赖版本/更新方式。
- **app/main.py**：`--smoke-wait=毫秒`；`--auto`（仅 `A4_AUTOMATION=1` 时生效）打包验收自动化：
  自动填目录→合并→导出验收 JSON（状态栏/引擎/长路径/成品页数体积/失败清单/结果对话框内容/依赖守卫）→退出。
- **core/runner.py**：无法转换（需 WPS）的文件不再进入后续 WPS 轮次，失败清单不再出现重复项。
- **tests/test_frozen_exe.py（9 例）**：版本资源、PE 子系统 GUI、manifest 内嵌、冒烟退出+启动提示、
  单实例拦截（双实例快速退出）、无 pip 守卫（`请重新安装《A4 合并助手》`）、
  模式A 全流程（真实 A4 尺寸 595.276×841.89 / 页数 / 报告 / 结果对话框）、
  模式B（输出目录在根目录内不被当素材）、仅纯 Python 引擎全链路（字体 + fpdf2 兜底）。
- **全量验证**：`pytest tests/` **67 passed ×2 遍**（74 s/遍），含 58 例开发期用例 + 9 例打包版用例。
- **⚠️ M5 验收缺口（必须人工完成，本机无法覆盖）**：
  1. **无 Python/无 pip 的绿色机器**上双击 exe 全流程 —— 本机必然带 Python，无法证明；
     （可验证的部分已覆盖：exe 单文件、无黑框、依赖内置、frozen 下绝不调 pip、断网不影响）
  2. **未装 WPS 的机器**：Office 文件应明确提示"需要安装 WPS"，图片/文本/PDF 仍可用 —— 本机装了 WPS；
     （纯 Python 引擎路径已用「仅纯 Python」模式在打包版上验证通过）
  3. 真机目视：界面中文显示、长路径提示、双击定位/打开目录/导出 TXT 的手感。
  建议：把 `dist/A4合并助手.exe` 拷到一台干净 Win10/11 同事机按上表逐条走一遍，再进 M6。
  **照单执行 → `docs/M5人工异机验收单.md`**（含测试数据准备脚本、逐条预期结果、报障五件套、结果回填表）。

## M6 计划（下一里程碑，需人工参与）

交付 1~2 位同事真机试用一周；收集诊断包报障 → 修复 → 回归；通过后全员铺开。

## 遗留问题 / 注意点

1. 全局环境装了样例生成工具（python-docx/openpyxl/python-pptx），仅供 make_samples 使用，不进运行时依赖。
2. 样例里 encrypted 场景暂只有加密 PDF；加密 Office（docx 加密）待评估生成方式（msoffcrypto 仅支持解密）。
3. 字体已提交 git（16.4MB），仓库变大可接受（离线可复现优先）。
4. `build/` 只保留打包源码（`a4merger.spec`、`make_version_info.py`）并入库；
   `version_info.txt` / `a4merger.manifest` / `pyi_work/` / `frozen_work/` / `localappdata/` /
   `pyi_tmp/` 均为生成物，已 gitignore。`dist/` 同样 gitignore（exe 不进仓库，靠 spec 复现）。
5. 回归稳定性加固（M4/M5 顺带修复，非功能变更）：取消用例需把队列里 `finished_signal` 处理干净；
   双实例用例两实例同时启动 + 重试；worker 加密样例走临时目录；打包版用例统一「先清残留实例 + stderr 落文件」。
6. 结果对话框与主界面真机显示效果仍待 M6 灰度确认（offscreen 下已核对控件与文本）。
7. 计划 3.4 建议用 Python 3.11 打包；实际采用与 requirements 锁定的 **3.12.10**（PyInstaller 6.22.3
   官方支持 3.8~3.14，本机打包与 frozen 验收全绿）。如需严格对齐计划，可另建 3.11 环境重打包验证。
8. **"Could not create temporary directory" 排障结论（2026-10，已加固）**：
   onefile 版启动要把内置文件解包到 `%TEMP%\_MEIxxxxxx`；`%TEMP%` 不可写时引导器只甩这句英文。
   - 本机复现条件：exe 放在**DSH 会话工作区**内、又用**会话场景启动**（受限令牌）→ 写 `%TEMP%` 被拦；
     同一 exe **鼠标双击**（资源管理器/ShellExecute，普通用户令牌）或放到工作区外（如桌面、D:\）
     均正常（已逐项实测：5 次双击启动全部 4~5 秒干净退出）。
   - 已做加固：`build/rthook_tempdir.py` 运行时钩子（在 import 主程序前探测 TMP/TEMP 可写性，
     不可写则退让到 `%LOCALAPPDATA%\A4合并助手\临时目录` → 用户主目录，并写回 TMP/TEMP）；
     `app/diagnostics.setup_file_logging` 写不了日志文件时降级为仅窗口日志，**不再让应用起不来**；
     `data_dir()` 逐级退让（%LOCALAPPDATA% → %TEMP% → 用户主目录）。
   - 给同事的分发建议：exe 放浅目录（如 `D:\A4合并助手\`）再双击；不要放在受限/同步目录里运行。
   - **为什么"放进 DSH 工作区就不行"（本机实测矩阵，2026-10）**：同一个 exe（SHA256 相同）
     · 放工作区 `Desktop\66\a4merger\dist\` → 会话 CreateProcess 与资源管理器双击**都不行**（无日志、无输出）；
     · 拷到 `Desktop\a4m_test\` → 两种方式**都正常**（4~7 秒干净退出、日志齐全）；
     · `cwd` 在工作区还是外面**无影响**；开发 Python 子进程无论 cwd 在哪都能写 `%TEMP%`/`%LOCALAPPDATA%`
       （排除 ACL、磁盘、TEMP 损坏等猜测）。
     结论：这是 **DSH 工作区的路径级限制**——工作区内的可执行文件被以受限令牌运行（ACL 证据：工作区内的文件
     带着额外 ACE `S-1-4-547675…`，桌面副本没有），因此既解不了包（`%TEMP%` 建目录失败）也写不了日志；
     与 exe 内容、与"是不是 PyInstaller"无关。产品侧只影响"在工作区内直接运行 exe"这一种用法。

## M6 灰度试运行（✅ 完成，2026-10，tag: m6）

- **入口条件已满足**：M5 人工异机验收通过（用户确认"两种情况下均无问题"——
  A 机=绿色机器、B 机=未装 WPS，均全流程可用）。
- **已备好交付物**（`python build\make_acceptance_kit.py` 一键生成到 `桌面\A4合并助手-验收包\`）：
  - `A4合并助手.exe`（1.0.0.0，78,330,762 字节，SHA256 A0C50A70…31CC6）
  - `使用说明-给同事.md`：选项说明、常见情况、报错怎么帮我、更新方式
  - `M6灰度报障登记表.md`：试点信息 + 一周按天登记 + 问题明细 + 结束判定三项
  - `M5人工异机验收单.md`、`验收测试数据.zip`
- **M6 开工前的测试隔离修复（2026-10，重要）**：QSettings 脏数据串测
  （regression 见下方"遗留问题"第 1 条）：`app/settings.py` 支持 `A4_SETTINGS_DIR`
  切 INI 存储；`app/main.py` 自动验收强制独立设置文件；冻结测试每用例独立设置目录；
  `tests/conftest.py` 会话开始清注册表残留。修复后 pytest 67 全绿 ×3 遍稳定。
- **灰度结果（用户确认，2026-10）**：试点同事真实使用一周，**无阻塞性报障**，
  按计划 4 节 M6 验收标准（1~2 位同事一周内无阻塞性报障、反馈问题全部修复并回归）**验收通过**。
- **全员铺开**：把 `桌面\A4合并助手-验收包` 分发给全体同事即可（exe 放浅目录双击；
  更新方式＝整包替换 exe；报障走「导出诊断包 + 一句话」）。至此 **M0~M6 全部完成**。

## 维护记录 1：应用图标（2026-10）

- **需求**：把应用图标换成用户提供的 `ys.jpg`（764×761）。原 spec 是 `icon=None`，
  即 exe 从来没有自己的图标（Windows 显示 PyInstaller/默认图标）。
- **资产（新增 assets/）**：
  - `assets/app-icon.jpg`：源图入库（199 KB），换图后离线可复现，与 fonts/ 同一取舍；
  - `assets/app.ico`：178 KB，含 Windows 实际会用到的 **7 档** 16/24/32/48/64/128/256
    （缺档就会被系统硬缩、发糊；256 档按 ICO 约定写成 PNG 帧）。
- **build/make_icon.py（新增）**：源图 → 居中裁正方形 → LANCZOS 逐档重采样 → 写 ico。
  换图标＝替换 `assets/app-icon.jpg` → `python build/make_icon.py` → 重新打包。
- **打包（build/a4merger.spec）**：
  - `icon=str(ICON_FILE)`：图标写进 exe 的 PE 资源（桌面/任务栏/文件列表图标）；
  - `(str(ICON_FILE), "assets")` 进 datas：运行期窗口图标可直接读；
  - ico 缺失时打包**前**就抛中文错误退出，不再出现"悄悄产出无图标 exe"。
- **运行期（app/icon.py 新增 + 两处接线）**：按 `sys._MEIPASS/assets/app.ico`（打包）
  → `工程/assets/app.ico`（开发）顺序定位；`app/main.py` 在 QApplication **之后**
  `setWindowIcon`（标题栏 + 任务栏），`app/ui_main.py` 主窗口同步设置；
  定位不到只退回系统默认图标，**绝不影响启动**。
- **测试（+8 例，67 → 75）**：
  - `tests/test_app_icon.py` 7 例：源图入库、7 档尺寸齐全且逐档取得出位图、正方形、
    spec 两处引用（icon=/datas）、打包与开发两条定位路径、主窗口图标非空；
  - `tests/test_frozen_exe.py::test_exe_embeds_app_icon_frames`：两条独立断言，
    防"改了 spec 却没人发现图标根本没进 exe"——
    ① 拿 ico 的每一帧字节去 exe 里比对（PyInstaller 原样写成 RT_ICON）；
    ② 内置档案里必须有 `assets\app.ico` 目录项（datas 漏了的话，打包版窗口图标会静默退回默认；
       注意裸字符串 `app.ico` 会被模块名 `app.icon` 命中，断言必须带路径分隔符）。
- **验证**：`pytest tests/` **75 passed ×2 遍**（92 s / 89 s，含 9 例打包版用例）。
- **产物**：重打包 `dist/A4合并助手.exe` **78,635,165 字节** / SHA256 `699C6AFA…93BB21`
  （中间态，随即被下面的 1.0.1 正式版取代）；构建日志出现 `Copying icon to EXE`；
  Windows `ExtractAssociatedIcon` 实测取到的就是新图标。
- **文档同步**：README（构建步骤 + 目录结构 + 用例数）、
  `docs/M5人工异机验收单.md`（指纹更新为本次产物 + 外观检查加一条"任务栏/标题栏图标"）。
- **注意**：改图标不涉及功能逻辑，`app/diagnostics.py` 的构建时间戳仍由 spec 的
  try/finally 保证打包后还原（本次重打包后 `git status` 无该文件改动，已核对）。

## 维护记录 2：发布 v1.0.1（2026-10）

- **提交**：`50c52ad feat(icon): 应用图标替换为 ys.jpg（写进 exe PE 资源 + 窗口/任务栏图标），补 8 例回归`
  ——已推送 `origin/main`（本机直连 github.com 不通，推送走系统代理 `127.0.0.1:7897`，
  仅一次性 `-c http.proxy=…`，**未写进仓库配置**）。
- **版本号提升（1.0.0 → 1.0.1）**：`build/make_version_info.py` 的 `VERSION = (1, 0, 1, 0)`
  （文件属性 1.0.1.0）+ `core/__init__.py` 的 `__version__ = "1.0.1"`（窗口标题/状态栏/关于/诊断包同源）；
  `tests/test_frozen_exe.py` 的版本断言同步改 1.0.1.0。**不提升的话，Release 标 v1.0.1
  而 exe 属性仍是 1.0.0.0，同事按验收单核对文件版本会以为发错包。**
- **重打包**：`dist/A4合并助手.exe` **78,636,490 字节**，SHA256 `2B6C8C16…F9F671`，文件版本 1.0.1.0；
  图标 7 档帧 + 内置档案 `assets\app.ico` 均已在 exe 内复核。
- **发布**：GitHub Release **v1.0.1**（tag 指向本次提交），资产沿用 v1.0.0 的英文命名规范：
  `A4MergeAssistant-v1.0.1.zip`（解压即 `A4合并助手.exe`）与 `A4MergeAssistant.exe`。
- **文档同步**：README（下载资产名 + 1.0.1 变更说明）、`docs/使用说明-给同事.md`（版本 1.0.1.0）、
  `docs/M5人工异机验收单.md`（指纹变更记录：M5 → 1.0.1，标题栏/状态栏期望版本改 v1.0.1）。
- **验收包脚本**：`build/make_acceptance_kit.py` 的 `EXPECTED_SIZE / EXPECTED_SHA256`
  锁定本次 1.0.1 指纹（发错 exe 会直接中止，提示先更新指纹）。

## 维护记录 3：处理级别新增「当前文件夹」（2026-10）

- **需求**：处理级别原只有「1 级子文件夹 / 2 级子文件夹」，新增第三档
  **「当前文件夹」＝根目录本身整体合成一份 PDF**（根目录下所有层级的素材按
  「相对路径自然排序」串成一份成品，根层散文件也计入）。
- **core**：
  - `core/collect.py`：`iter_target_folders` 支持 `level=0`（只 yield 根目录本身，不参与
    "排除树"判定——计划输出文件已由 `skip_files` 排除，故"输出目录＝根目录"也不会自吞）；
    新增 `LEVEL_TEXTS` / `level_text()`（报告与日志的中文级别名）、
    `rel_target()`（目标相对根目录的稳定标识，**根目录记为 `.`**）、
    `target_display()`（界面显示名，级别0 显示为「xxx（当前文件夹）」）。
  - `core/types.py`：`MergeConfig.validate()` 校验 `level ∈ {0,1,2}`（未知值中文报错）。
  - `core/runner.py`：`--only` 过滤改用 `rel_target`（根目录＝`.`）；候选清单用显示名；
    启动日志新增「处理级别：当前文件夹（根目录）／1 级子文件夹／2 级子文件夹」。
  - `core/report.py`：合并报告的「处理级别」写中文级别名（原为"N 级子文件夹"）。
- **CLI**：`--level 0|1|2`（默认 1，`--level 3` 由 argparse 直接拒绝）；
  `python cli.py --level 0` 即"整个根目录合成一份"。
- **GUI（app/ui_main.py）**：`LEVEL_MAP` 直接由 `LEVEL_TEXTS` 生成（新增项排在最前），
  默认仍是 1 级；设置读取改为**按级别值映射下标**（历史 `level=1/2` 记忆不受新增项影响）；
  目标列表把「显示名」与「真实标识」分离——真实标识存 `Qt.UserRole`（根目录为 `.`），
  `--only` 与勾选记忆一律用标识，因此级别0 下界面显示「xxx（当前文件夹）」而传参仍是 `.`。
- **打包验收（app/main.py）**：新增 `A4_AUTOMATION_LEVEL`（0/1/2），自动验收可指定级别。
- **顺带修一个既有坑（模式B 输出目录＝根目录）**：原来 `exclude_dirs` 把输出目录整树排除，
  用户若把「统一输出目录」选成根目录本身，则**所有目标/素材都被排掉**（级别1/2 下目标为空、
  级别0 下"无素材"，静默什么都不做）。新增 `core/collect.py: exclusion_dirs(root, output_dir)`：
  仅当输出目录≠根目录时才排除（防套娃语义不变，输出目录位于根目录内的用例仍覆盖），
  runner 与 GUI 目标列表统一走它；成品仍由「计划输出路径 + 同名成品识别」两条规则兜底。
- **测试（+8 例，共 83）**：`tests/test_modes.py` 6 例（级别0 模式A 页数=16、重复运行不套娃、
  级别0+模式B、级别0+`--only .`、非法级别退出码 2、模式B 输出目录＝根目录）、
  `tests/test_gui_smoke.py` 1 例（下拉含新项 + 级别0 目标只有根目录且标识为 `.`、
  `_build_config` 得到 `level=0/only=["."]`）、`tests/test_frozen_exe.py` 1 例
  （打包版级别0 全流程：目标数=1、成品落在根目录、页数=16、报告写「当前文件夹（根目录）」）。
- **验证**：`pytest tests/` **83 passed**（72 例开发期 + 11 例打包版冻结验收），
  连跑两遍稳定（100s / 102s）。
- **环境注意（仅当 DSH 以受限沙箱跑测试时）**：受限沙箱下 `mode=0o700` 新建的目录**不可读**
  （pytest 的 `tmp_path`、`tempfile.mkdtemp` 都会踩到；ACL 诊断脚本结论 `UNREADABLE`，
  不是可修复的 ACL 问题）。**改用完全权限运行即恢复正常**（本次最终验证就是在完全权限下 83 passed）。
  若只能在受限沙箱里跑，兜底办法：`PYTHONPATH` 指向一个把 `os.mkdir` 的 mode 强制为 0o777 的
  `sitecustomize.py`，并把 `--basetemp` 指向非点号目录。与工程代码无关，不需要改仓库。
- **待办**：`dist/A4合并助手.exe` 已在维护记录 4 重打包为 1.0.2.0（见下）。

## 维护记录 4：发布 v1.0.2（2026-10）

- **内容**：处理级别新增「当前文件夹」（级别 0，整个根目录合成一份 PDF）+
  修复「模式B 统一输出目录选成根目录时收不到素材」。详见维护记录 3。
- **版本号提升（1.0.1 → 1.0.2）**：`build/make_version_info.py` 的 `VERSION = (1, 0, 2, 0)`
  （文件属性 1.0.2.0）+ `core/__init__.py` 的 `__version__ = "1.0.2"`（窗口标题/状态栏/关于/诊断包同源）；
  `tests/test_frozen_exe.py` 的版本断言同步改 1.0.2.0。
- **重打包**：`python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyi_work build\a4merger.spec`
  → `dist/A4合并助手.exe` **78,636,788 字节**，SHA256 `AB50ADAA…E8D23`，文件版本 1.0.2.0；
  构建日志含 `Copying icon to EXE` / `Copying version information to EXE` / `Embedding manifest in EXE`；
  `app/diagnostics.py` 的构建时间戳已由 spec 的 try/finally 还原（`git status` 无该文件改动，已核对）。
- **验证**：`pytest tests/` **83 passed**，连跑两遍稳定（含 11 例打包版冻结验收，直接驱动新 exe：
  版本资源 1.0.2.0、图标帧、PE 子系统、单实例、模式A/模式B、**级别0 当前文件夹全流程**、
  仅纯 Python 引擎全链路）。
- **顺带修一个测试隔离缺陷（tests/conftest.py）**：开发态 GUI 用例的 MainWindow 会读写
  `HKCU\Software\A4合并助手`，原来只在会话开始时 `winreg.DeleteKey` 清一次——**该键一旦有子键
  （`window/geometry` 等，正常用过一次 GUI 就会有）就删不掉**，异常又被吞掉，于是真实使用留下的
  设置（输出模式＝B、输出目录＝桌面某目录）会串进测试，导致 `test_gui_smoke::test_window_controls`
  与 `test_results_dialog::test_end_to_end_real_run_summary` 失败。现改为把 GUI 设置重定向到
  本会话临时 INI（`A4_SETTINGS_DIR`，与打包版验收同一套隔离机制）：既不读本机残留，
  也不再清除/污染用户的真实设置。排查时曾一度以为是本次改动引入，实为既有隐患被真实设置触发。
- **文档同步**：README（当前版本 1.0.2 + 资产名 `A4MergeAssistant-v1.0.2.zip`）、
  `docs/使用说明-给同事.md`（版本 1.0.2.0）、`docs/M5人工异机验收单.md`
  （指纹改为本次产物 + 标题栏/状态栏期望 v1.0.2 + 新增 2.2b「当前文件夹」验收条目）、
  `build/make_acceptance_kit.py` 指纹锁定 v1.0.2（发错 exe 会直接中止）。
- **发布**：GitHub Release **v1.0.2（Latest）已发布** →
  https://github.com/banlong-bot/a4merger/releases/tag/v1.0.2
  资产沿用英文命名规范：`A4MergeAssistant-v1.0.2.zip`（78,239,217 字节，内含 `A4合并助手.exe`）
  与 `A4MergeAssistant.exe`（78,636,788 字节）。tag `v1.0.2` 指向提交 `c34bb70`，main 已推送。
  本次直连 github.com 可用，**无需代理**（维护记录 2 里的代理参数只是当时需要）。
- **提交拆分**：`feat(level)` 功能 → `test(conftest)` 测试隔离修复 → `chore(release)` 版本与文档，
  再打 tag；便于日后回滚或摘取单个改动。

- **遗留（未处理，勿当 bug）**：v1.0.2 发布期间（2026-10-12 21:13）工作区里
  `assets/app-icon.jpg` 与重新生成的 `assets/app.ico` 被替换（未提交，非本次改动）。
  **已发布的 v1.0.2 exe 是 20:47 打包的，内嵌的仍是旧图标**，因此当前工作区下
  `tests/test_frozen_exe.py::test_exe_embeds_app_icon_frames` 会对这个 exe 报失败——
  这是"exe 与工作区图标不一致"，不是打包或代码回归。用户决定**先不动图标**。
  后续若要启用新图标：提交图标 → 提版本号（1.0.3）→ 重打包 → 更新指纹/验收单 → 发 Release。

## 维护记录 5（M7：遇到 Excel 跳过，2026-10）— 代码完成，未打包/未发版

- **需求来源**：计划文档没有这一项，是用户新增需求（原话「增加一个可选项，遇到 excel 可跳过」），
  经我提问确认三条设计后实现：① 范围只含 `.xls/.xlsx`（`~$` 临时锁文件本来就静默排除，不重复处理）；
  ② **默认不勾选**，保持旧行为完全不变；③ 环境为项目文件夹改回 `C:\Users\25792\Desktop\66` 后正常。
  ——属于计划外新增，故单独记为 M7，不改动计划文档（计划文档是里程碑基线）。
- **core 层**：
  - `core/types.py`：`MergeConfig.skip_excel: bool = False`；`FolderResult.skipped_excel: list[Path]`。
  - `core/collect.py`：新增 `SKIP_EXCEL_EXTS = {".xls", ".xlsx"}`、`is_skippable_excel(path)`、
    `partition_skipped_excel(files) -> (kept, skipped)`（保序，不动只读的 collect_files）。
  - `core/runner.py`：`_process_folder` 里在算出「支持类型」的 `used` 后分流——跳过项写入
    `result.skipped_excel`、**不进转换队列**，因此既不算失败也不触发 WPS 轮次；开头日志加一行
    「遇到 Excel：按选项跳过（.xls/.xlsx 不合并、不计失败）」。
  - `core/report.py`：报告参数行加「遇到 Excel ：跳过/正常处理」，单列【跳过的 Excel】章节
    （未启用时写明「（未启用该选项）」），合计行加「跳过 Excel N 个（未计入失败）」；
    「只剩 Excel」的目标不再报「无素材」，改标「Excel 已按选项跳过」。
- **界面/入口**：「转换选项」组新增复选 `cb_skip_excel`（文案「遇到 Excel（.xls/.xlsx）跳过：
  不合并、不计失败」，带中文提示），设置项 `skip_excel` 记忆；状态栏与收尾日志在启用时追加
  「跳过 Excel N 个」；`app/main.py` 自动化验收新增 `A4_AUTOMATION_SKIP_EXCEL=1` 与
  JSON 结果字段 `skip_excel/skipped_excel/skipped_excel_rows`；`app/diagnostics.py` 的
  config.json 同步输出该开关（便于远程报障时确认同事勾没勾）。
- **结果对话框**：启用时第 4 个页签变为「跳过的 Excel（N）」（逐行：目标/文件名/完整路径，
  双击定位），默认关闭时仍是原来四个页签、不凭空多一列；「无素材」原因改为按 Excel 跳过数量说明。
- **测试（+9，共 92 用例）**：`test_core_units.py` 3 例（范围判定 / 保序分流 / 默认关闭）、
  `test_modes.py` 2 例（`--skip-excel` 真跑：PDF 3 页照常合并 + 报告单列跳过清单 + 不出现「需要 WPS」；
  默认不勾选时 Excel 仍计失败，行为不变）、`test_gui_smoke.py` 1 例（默认不勾 + 配置透传 + 设置记忆）、
  `test_results_dialog.py` 3 例（页签/双击定位/默认不出现该页签/「N 个 Excel 已跳过」文案）。
- **验证**：`pytest tests/` **91 passed + 1 failed**；唯一失败是既有的
  `test_exe_embeds_app_icon_frames`（工作区新图标 vs v1.0.2 exe 旧图标，见维护记录 4 的遗留，非本次回归）。
- **排查教训（测试隔离）**：新用例里调用 `_save_settings()` 会把窗口状态（含根目录）写进**同一会话
  共享的隔离 INI**，导致后续 `test_gui_smoke::test_targets_uncheck_all`（该用例因 fixture
  `blockSignals(True)` 依赖“setText 触发一次刷新”来更新状态栏）与
  `test_results_dialog::test_end_to_end_real_run_summary` 失败。改为直接 `AppSettings().set/get`
  验证持久化并复原，不再走 `_save_settings()`。——**新写 GUI 用例时不要把 `_save_settings()` 当断言手段**。
- **文档同步**：README 功能特性新增「Excel 跳过选项」并在结果清单条目里注明第五列；
  `docs/使用说明-给同事.md` 选项表新增「遇到 Excel 跳过」一行。
- **重打包（按用户决定：只出 exe，不发版）**：`python -m PyInstaller --noconfirm --clean
  --distpath dist --workpath build\pyi_work build\a4merger.spec` → `dist/A4合并助手.exe`
  **78,488,574 字节**，SHA256 `08DC1A95…A40822`，文件版本仍是 **1.0.2.0**（未提版本号），
  构建日志含 `Copying icon to EXE` / `Copying version information to EXE` / `Embedding manifest in EXE`；
  构建时间戳已由 spec 的 try/finally 还原（`git status` 仅剩两个图标文件，已核对）。
- **验收**：`pytest tests/test_frozen_exe.py` **11 passed**（直接驱动新 exe）；全量 `pytest tests/`
  **92 passed**（129.6s）。——本次重打包顺带把工作区未提交的**新图标**嵌进了 exe，因此
  `test_exe_embeds_app_icon_frames` **恢复通过**（图标字节与工作区 `assets/app.ico` 一致）。
- **重要提醒（版本号相同但内容不同）**：新 exe 与 GitHub Release v1.0.2 的 exe **字节不同却同为 1.0.2.0**
  （旧 78,636,788 / `AB50ADAA…E8D23` vs 新 78,488,574 / `08DC1A95…A40822`），差异来自 M7 代码 +
  新图标。**未打 tag、未推 GitHub main、未发 Release**（用户决定）。日后要发版必须先提版本号到 1.0.3，
  否则同事无法凭版本号区分两个 exe。
- **未提交**：`assets/app-icon.jpg`、`assets/app.ico`（新图标，用户此前决定先不动；本次打包已用上但未入库）。
- **遗留（待用户决定）**：① 是否发 v1.0.3（提版本号 + 提交图标 + 重打包 + 更新验收单指纹 + tag + Release）；
  ② 打包版冻结验收里还没有「遇到 Excel 跳过」的自动化用例，发版时应补一例（自动化环境变量
  `A4_AUTOMATION_SKIP_EXCEL=1`、结果字段 `skipped_excel_rows` 已就绪）。

## 维护记录 6（impeccable init：产品事实入库，2026-10）

- **缘由**：用户要求「用 impeccable 给这个项目做 init」——把持久的产品事实（用户、目的、定位、约束）
  一次性写进 `PRODUCT.md`，供后续设计/评审类工作复用，避免反复询问。
- **工具**：`impeccable context` 报 `NO_PRODUCT_MD` / `PRODUCT_INIT_REQUIRED`（项目尚无 PRODUCT.md），
  按 `reference/init.md` 走「探索 → 一轮访谈 → 写文件」，**不生成 DESIGN.md**（init 不管视觉）。
- **访谈确认（用户三问答复）**：① 用户范围已扩大到**跨部门同事与外部协作同事**（不再只是自己和本组）；
  ② 核心定位＝**完全离线 + 绿色单 exe、双击即用、无需安装**；③ 硬约束三条＝**全中文界面/日志/注释**、
  **Windows 10/11 桌面端（不做 macOS/Linux/移动）**、**完全离线（不联网/不云端/不账号）**。
- **产物**：仓库根新增 `PRODUCT.md`（`impeccable:product-schema 1`），含 Platform（记为 `windows`——
  原生桌面端，schema 枚举只覆盖 web/ios/android/adaptive，已在该节注明）、Users、Product Purpose、
  Positioning、Operating Context、Capabilities and Constraints、Brand Commitments、Evidence on Hand、
  Product Principles（5 条）、Accessibility & Inclusion。**未写 DESIGN.md**（按 init 规则留给
  `/impeccable document`）；也未记录 `buildPath`（本机无图像生成能力，code-first 是唯一路径），
  未配置 live 模式（原生桌面应用，无浏览器渲染目标）。
- **验证**：`PRODUCT.md` 已落盘；不改任何代码，无需重跑 pytest（下次改动前仍以 92 例回归为准）。
- **下一步**：若要记录现有 Qt 界面体系 → `/impeccable document` 生成 DESIGN.md；
  若要评审主窗口 → `/impeccable critique app/ui_main.py`。

## 维护记录 7（impeccable document：设计体系入库，2026-10-21）

- **缘由**：用户在同一天要求 `impeccable document`——把现有界面的视觉体系固化成 `DESIGN.md`，
  供后续新界面/改造保持同源。前置：`PRODUCT.md`（维护记录 6）已存在。
- **扫描结果（现状事实）**：项目**没有 QSS 文件**，视觉由 Qt/Windows 原生控件决定；
  全工程仅 8 处内联样式：日志区 `Consolas/Microsoft YaHei 9pt`、结果对话框标题 `11pt/700`、
  提示与根目录行 `#555555`、模板校验 `#c0392b/#fdecea`、状态与日志着色
  `#333333/#1565c0/#1e7d32/#b26a00/#c62828`。窗口 1080×720（可记忆几何）、
  结果对话框 1120×640、左右分栏 2:3、主按钮最小高 40px、日志上限 5000 块。
- **访谈确认（用户答复）**：① 北极星＝**「安心档案柜」**；② 视觉基调＝**轻量统一皮肤（浅色）**、
  **极简风**（用户原话「走极简风，」）；③ 密度与手感未单独选，按极简方向取「紧凑原生」为默认。
- **产物**：
  - `DESIGN.md`（仓库根，DESIGN.md 规范格式）：YAML frontmatter（12 色 + 5 字体角色 + 圆角/间距 + 8 组件）
    + 八节正文（Overview/Colors/Typography/Layout/Elevation/Shapes/Components/Do's and Don'ts），
    含 5 条 Named Rules（语义独占五色、面积十分之一、等宽只读、一屏一动作、发丝线）。
  - `.impeccable/design.json`（sidecar，schemaVersion 2）：12 色的 8 级 tonalRamp、typographyMeta、
    shadows/motion 为空（扁平无动效）、breakpoint desktop-min 900px、8 个 Qt 组件的 QSS 片段与结构、
    narrative（北极星/概述/关键特征/规则/Do/Don't）。
- **诚实标注（重要）**：文件开头已写明——**结构已落地（v1.0.2 现网），语义色 8 处已落地，
  统一浅色 QSS 皮肤是本次确认的方向、尚未实现**；每条颜色/圆角 token 都标注了「已落地」或「方向」，
  不做"已完成"的假记录。
- **未做**：没有改任何界面代码（document 只记录不实施），故 `pytest tests/` 无需重跑（基线仍 92 例）；
  没有新增 DESIGN.md 相关测试。
- **下一步**：若要把「极简浅色皮肤」真正落地 → 新建 `app/theme.py` + `app/theme.qss`，
  按 DESIGN.md 的 token 做 QSS，并补截图对比回归（该项属于代码改动，需单独确认后再做）。

## 维护记录 8（M8：极简浅色皮肤 + 主窗口信息架构落地，2026-10-21）

- **缘由**：`/impeccable shape` 规划后用户确认「**确认，开始实施**」——把 DESIGN.md 里记为「方向」的
  极简浅色皮肤真正实现，同时按 shape 简报重排主窗口信息架构。验收口径（用户选定）：
  **改版前后截图对比 + 现有 92 例 pytest 全绿**。
- **用户拍板的三项取舍**：① 高级选项（排版/转换/加密三组）默认**折叠**，展开状态记忆；
  ② 空状态（未选根目录）在动作条**只留一行引导字**，目标列表不塞提示；③ 「试运行」留在**主按钮区**。
  范围上用户允许大改信息架构（不只是换色）。
- **皮肤实现（唯一实现处）**：
  - 新增 `app/theme.py`：`TOKENS`（13 色 + 圆角/间距，与 DESIGN.md frontmatter 一一对应）、
    `color()`（未知名字回退主墨，不抛异常）、`load_qss()`（`$token` 占位符替换，长名优先避免前缀误替换）、
    `apply()`（挂到 QApplication，重复调用无副作用）。
  - 新增 `app/theme.qss`：只用 DESIGN.md 的 13 色（M8 追加 `accent-soft #eef4fb` 作悬停衬底）；
    无阴影/渐变/动效；发丝线一律 1px；含 `QPushButton#primaryButton`（任务蓝底、40px、hover `#0d47a1`）、
    `QLabel#expectLabel`、`QLabel#inlineError`、`QFrame#actionBar`、`QProgressBar`、`QScrollBar`、
    `QTabBar`、分组框 6px 圆角等。
  - 截图复核后修掉的三个视觉缺陷（都在 QSS 层）：① 下拉框被 QSS 化后箭头消失 → 去掉
    `QComboBox::drop-down` 覆盖，箭头交回 Qt 原生绘制；② 目标列表的勾选框变成“只有勾没方框”
    → 显式写 `QListWidget::indicator`（勾选＝实心任务蓝方块）；③ 滚动条是默认粗条 →
    细轨 + 无箭头 + 悬停浅蓝。
  - 进度条改为「标题行写文字、细轨道画进度」：空闲 8px、运行中 18px，文字进
    `lb_prog_folder` / `lb_prog_page`（原来压在蓝条上，深色字看不清）。
  - 顺带修掉 `_append_log` 里的历史占位 bug：日志超限时 `self.txt_log.blockCountChanged.emit`
    是空操作，真正的 `_trim_log()` 从未执行（长跑会无限增长）。
  - `MainWindow.__init__` 调 `theme.apply()`；`_set_state` / `_append_log` 原来写死的 5 个
    十六进制色改为 `theme.color(...)`。**界面代码里不再散落十六进制色值。**
- **信息架构重排（`app/ui_main.py`）**：
  - 顶部：应用名 + 一句话用途（「把一组文件夹各自合成一册 A4 PDF」）。
  - 左栏放进 `QScrollArea`（`self.scroll_left`）：基本设置 → 目标文件夹（带「已选 N/M · 将生成 M 册」
    状态行）→ 可折叠高级选项（`btn_advanced` / `adv_panel`，`advanced_expanded` 记忆）。
  - **动作条常驻窗口底部**（`QFrame#actionBar`，跨满整宽）：左侧「将把 N 个文件夹各自合成一册 A4 PDF」
    预告行 + 行内错误，右侧 试运行 / 取消 / 开始合并。修掉了改版前「1080×720 下主按钮被左栏滚动裁掉」的问题。
  - 进度条空闲显示「—」（原来像空白输入框）；分栏比例 3:4。
  - **行内提示替代模态弹窗**：模板非法、根目录无效、未勾选、模式B 缺输出目录、配置校验失败
    一律写进 `lb_inline_error`（红字，`_set_inline_error`），不再 `QMessageBox.warning` 打断；
    根目录为空时目标状态行留空（不再显示误导性的「已选 0/0」）。
- **测试**：
  - 新增 `tests/test_ui_theme.py`（13 例）：QSS 已挂载且含关键 token、`apply()` 幂等、token 与 DESIGN.md 一致、
    QSS 文件随源码存在、初始折叠态、折叠切换不改默认值、左栏滚动区存在且最小高度 ≤760、
    预告行随勾选/试运行变化、模板非法→行内红字且**不弹模态**、根目录失效→行内提示、
    `advanced_expanded` 设置记忆（用 `AppSettings` 直接读写并在 finally 复原，避免污染同会话）、
    进度文案随进度进标题行、日志超限真截断（防历史占位 bug 回归）。
  - 更新 `tests/test_gui_smoke.py` 两例以匹配新文案与行内提示语义（不再 monkeypatch 弹窗）。
  - 测试隔离教训：新用例的窗口 fixture 需先清掉会话共享 INI 里的 `root` / `checked_targets`
    再构造窗口，否则前一个用例保存的表单会让「默认态」断言失败（本次实测踩到）。
- **截图（验收证据）**：新增 `tools/capture_ui.py`（默认 Windows 原生平台渲染，`A4_SHOT_OFFSCREEN=1`
  可退化为 offscreen；offscreen 下加载仓库自带 Noto 中文字体，避免截图全是方块）。
  产物 `docs/shots/main-before-{empty,filled}.png` 与 `docs/shots/main-after-{empty,filled,advanced}.png`。
  注意：原生平台在解释器退出期偶发 `0xC0000409`（与打包版同类），工具末尾改为截图落盘后 `os._exit(0)`。
- **打包**：`build/a4merger.spec` 的 `datas` 增加 `(app/theme.qss, "app")`，否则打包版读不到 QSS。
  exe 已重建：`dist/A4合并助手.exe` **78,495,490 字节**，SHA256 `F1CFF13BE4A351BCBE356E10CAC1CF0AA1EFF416B832E9838064EAF04F05FAA7`。
- **验证**：`pytest tests/` 全量 **105 passed**（92 既有 + 13 新增 `tests/test_ui_theme.py`）；
  `pytest tests/test_frozen_exe.py` 对**重建后的 exe** **11 passed**（含新增断言「界面皮肤：已加载」，
  确保 `app/theme.qss` 真的随打包进去）；`docs/shots/main-before-*.png` 与 `main-after-*.png` 可对照。
- **未做**：没有发版（版本号仍 1.0.2）、没有 push——沿用维护记录 5 的节奏，等你决定是否出 1.0.3
  （届时要把 78,497,916 字节这个本地 exe 与 Release 里同版本号但字节不同的旧 exe 区分开）。

## 维护记录 9（M9：参照「花笺」重做视觉 —— 暖纸+竹绿、无边框圆角窗口、阴影+动效、内置 HarmonyOS Sans 字体，2026-10-21）

- **缘由**：用户（m03461）要求参照开源项目 **花笺 floral-notepaper**（https://github.com/Achilng/floral-notepaper ，MIT）
  的 UI 样式重做界面，「可以增加一些阴影和动效，换一个更合适的字体」。四项经确认取舍：
  ① 配色 = **全套花笺**（暖纸底 + 竹绿主色，主色由蓝改绿）；② 字体 = **内置 HarmonyOS Sans SC**（与参考同款）；
  ③ 动效 = **轻量全套 + 设置开关**；④ 窗口外框 = **无边框圆角 + 自绘标题栏**（不要系统标题栏）。
- **协作方式**：按 Agent Teams 分工（Lead 定接口契约 + 收口；theme-artisan 做主题；window-shell 做窗口；
  test-sentinel 做测试）。接口契约落盘在 `docs/m9-ui-contract.md`（API / token / objectName / 分工写权限），
  三人写权限互斥，Lead 统一跑全量、打包、提交。
- **视觉定稿（`app/theme.py` TOKENS，17 色 + 圆角/间距/动效）**：paper `#F6F3EC`、paper-deep `#EDE7DA`、
  surface `#FFFDF8`、surface-raised `#FFFFFF`、border `#E3DCCD`、ink `#2B2A26`、ink-muted `#6A6559`、
  **bamboo `#2D5A3D`** / bamboo-deep `#1F4229` / bamboo-soft `#E6EEE4`、ok `#2E7D4F` / warn `#8F5A14` /
  error `#B3261E`；圆角 6/10/14px + pill 22px；间距 4/8/12/16/24；动效 120/180/240ms。
  阴影三档 `card/raised/float`（QGraphicsDropShadowEffect，模糊 26/34/46、不透明度 54/66/80），悬停加深。
- **字体与许可（合规硬要求）**：`fonts/HarmonyOS_Sans_SC.ttf`（20,617,156 字节，可变字重）＋
  `fonts/LICENSE_HarmonyOS_Sans.txt`（3315 字符协议全文）。协议 2.1 要求「软件内显著声明」→
  在**关于对话框**写明 HarmonyOS Sans SC / Copyright 2021 Huawei Device Co., Ltd. / 许可文件路径；
  README 增加「第三方字体」小节；`build/a4merger.spec` datas 同时打包字体与许可证。
  协议同时禁止改字形、禁止单独售卖字体——本仓库只原样随软件分发，符合要求。
- **主题实现（`app/theme.py` 412 行 / `app/theme.qss` 约 14.5KB）**：
  `load_qss()` 支持 `$token` 与 `$assets` 两种占位符（长名优先替换；图标目录缺失时自动删除 9 条
  `image: url(...)` 降级为纯色块，不抛异常）；`apply()` 幂等并 `QLocale.setDefault(zh_CN)`（本机区域 zh_MO
  下 Qt 6.12 会把 QSpinBox 的 600 显示成汉字数码「〩〩」）；动画对象由模块级 `_ALIVE` 保活；
  `A4_MOTION=0` 或界面开关关闭时 `fade_in/fade_widget/animate_progress/animate_expand/attach_card_shadow`
  全部同步落终态（不创建动画对象）。
  新增 `app/assets/`：check-white / check-dark / radio-dot / chevron-down 四个透明 PNG（约 1.1KB，Pillow 4×超采样）。
  （生成脚本暂放 `.tmpx/make_assets.py`，未入库；如需交接可挪到 `tools/`。）
- **无边框窗口（`app/ui_main.py`，约 1264 行）**：`FramelessWindowHint|Window` + `WA_TranslucentBackground`，
  centralWidget = `QFrame#windowShell`（14px 圆角 + 1px 发丝线，普通态留 1px 外沿、最大化归零）。
  结构：40px 自绘 `#titleBar`（标题 + 副标题 + 「文件/帮助/界面」三个 `#menuButton` + 最小化/最大化/关闭）
  → 内容区（原 head/QSplitter/actionBar；内容区重复的大标题已隐藏，对象保留）→ 自绘 `#statusBarCustom`
  （原 `lb_engine/lb_longpath/lb_state/lb_version` 全保留；**不再调用 `menuBar()` / `statusBar()`**）。
  拖拽 `QWindow.startSystemMove()`；缩放 6px 边缘命中 `startSystemResize(edges)`（四边 + 四角，hover 变光标）；
  双击标题栏最大化/还原；窗口按钮改 **QPainter 自绘 1.5px 线框图标**（内置字体缺 ✕/❐ 字形，不能靠文字）。
- **动效接线（全部受 `motion_enabled()` 门控）**：首帧窗口淡入 180ms；高级选项 `animate_expand`（240ms，
  收起动画结束后才 hide）；进度条 `animate_progress`（240ms）；卡片 `attach_card_shadow` 悬停阴影加深；
  行内错误 `fade_widget`。菜单「界面 → 启用界面动效」勾选项（`AppSettings` key `motion`，默认开）。
  启动日志三行：「界面皮肤：已加载（theme.qss，N 字符）」「界面字体：HarmonyOS Sans SC（内置）」
  「界面动效：开/关」——打包漏资产时能立刻发现。
- **视觉复核后修掉的问题**：① 复选框勾选态被 QSS 化成实心绿方块（Qt 只要给 indicator 设 background
  就不再画系统勾形）→ 自带 14×14 透明勾图标；② 下拉框原生 drop-down 在圆角边框上压灰底直角块 →
  透明 `::drop-down` + `chevron-down.png`（教训：**不要写 `QComboBox:hover::down-arrow`**，Qt 对这种
  「父伪状态+子控件」组合选择器解析异常，会叠画两个箭头）；③ 主按钮 999px 圆角被 Qt 忽略 → `radius-pill-px=22px`；
  ④ 进度条 8pt 百分比文字被裁 → max-height 16→18px；⑤ 目标文件夹卡片被拉成空白大块 → 列表 maxHeight 300
  + 左栏顶部对齐（`lv.addStretch(1)`）；⑥ 卡片阴影用户觉得偏淡 → 阴影三档整体上抬一档（M9 终稿值见上）。
- **Qt 关键坑（已写进注释，后续别再踩）**：`QWidget.maximized` 是**内建只读属性**，
  `setProperty("maximized", ...)` 被静默忽略、`property("maximized")` 恒 False →
  最大化圆角改用自定义动态属性 **`winMaximized`**（`QFrame#windowShell[winMaximized="true"]`），
  同时保留 `QMainWindow[maximized="true"] QFrame#windowShell` 兜底选择器。
- **测试**：`pytest tests/` 全量 **118 passed**（原 103 例；本轮重写 `tests/test_ui_theme.py` 22 例、
  `tests/test_gui_smoke.py` 13 例，`tests/test_results_dialog.py` 把 `statusBar()` 断言改为 `statusBarCustom`、
  进度断言改为等动画终值）。测试侧踩到的两处误判：① QSS **注释里的字面「$token」**被当成未替换 token
  （改为先剥注释再扫描）；② 平滑动画是异步的，同步断言瞬时值必然失败（改为等待终值，并另加
  `test_animations_terminal_when_motion_off` 覆盖关动效时的同步落终态）。`test_worker_password_flow`
  在全量负载下曾偶发超时（单跑 1.2s 通过），最终轮未复现，未削弱该用例。
- **打包与验收**：`build/a4merger.spec` datas 增加 `(app/assets, "app/assets")`、HarmonyOS 字体与许可证；
  重打包 `dist/A4合并助手.exe` **93,394,416 字节**，SHA256 `E087A036015EA45341B619AB2BD85AF3E2CEA2269D6A2D739FB8C0123EBA8C6E`
  （比 M8 的 78.5MB 大 14.8MB，主要是内置字体）。`tests/test_frozen_exe.py` 增加断言
  「界面字体：HarmonyOS Sans SC」「界面动效：」必须出现在打包版启动日志里（防止字体/资产漏打包）。
  截图：`docs/shots/main-m9-{empty,filled,advanced,maximized}.png`（native 2x 渲染）。
- **未做 / 待人工**：
  - **未发版、未 push、未打 tag**：版本号仍 1.0.2.0；`assets/app-icon.{jpg,ico}` 的未提交改动继续保持不动
    （沿用维护记录 5 的决定）。若发 v1.0.3：提交图标 + 提版本号（`build/make_version_info.py`、`core/__init__.py`、
    冻结验收断言、README/说明、验收单指纹）+ tag/Release + push。
  - 无边框窗口的**拖拽手感、贴边分屏、多屏/高 DPI** 只能真机人工验证（离屏自动化覆盖不到 `startSystemMove`）。
  - 建议在 Win10 实机上目视一次字体与阴影（HarmonyOS Sans 在 Win10 的 ClearType 观感与 Win11 略有差异）。


## 维护记录 10：发布 v1.0.3（M9 界面改版正式发版）

- **背景**：用户 m03834「可以，提交发布到 github 上吧」——授权把 M9（花笺风格界面改版）按
  维护记录 5 的流程正式发版：提交新图标 → 提版本号 → 重打包 → tag/Release → push main。
- **版本号提升 1.0.2 → 1.0.3**（三处代码 + 文档同步）：
  - `core/__init__.py`：`__version__ = "1.0.3"`（关于对话框 / 状态栏 / 报告 / 诊断包统一取自这里）；
  - `build/make_version_info.py`：`VERSION = (1, 0, 3, 0)`（exe 文件属性）；
  - `tests/test_frozen_exe.py`：版本断言改为 `1.0.3.0`（另保留「1.0.2 新增」等历史注释不动）。
- **新图标入库**：`assets/app-icon.jpg`、`assets/app.ico` 的未提交改动随本版一起提交，
  关闭维护记录 5 遗留的「exe 内嵌旧图标」问题。
- **文档同步**：`README.md`（版本段、`A4MergeAssistant-v1.0.3.zip`、测试数 118）、
  `docs/使用说明-给同事.md`（1.0.3.0 + 界面改版说明）、`PRODUCT.md`（能力基线 v1.0.3、
  版本事实、118 例）、`docs/M5人工异机验收单.md`（1.0.3 指纹、新增 1.7~1.10 界面项、
  2.7 Excel 跳过项、回填表补 2.2b/2.7 行）、`build/make_acceptance_kit.py`（指纹锁定 1.0.3）。
- **重打包**：`dist/A4合并助手.exe` **93,394,732 字节**，
  SHA256 `3A2ED45CFB87B9B9199BE432E4537E92CAD8603A83435CAB497D79D242CCCA93`，
  文件版本 **1.0.3.0**，构建时间戳 1792571134.2（spec 已还原源文件）。
- **验证**：`pytest tests/test_frozen_exe.py` → **11 passed**（版本资源 / 图标 / 无黑框 / 单实例 /
  长路径 / 无 pip 守卫 / 全流程模式 A·B / 当前文件夹 / 纯 Python 引擎 / 界面字体与动效日志）；
  开发态全量 118 例在 M9 提交时已全绿（本次只改版本常量与文档，未动业务逻辑）。
- **发布**：`git tag v1.0.3` → Release「A4 合并助手 1.0.3（花笺界面改版）」，
  资产 `A4MergeAssistant-v1.0.3.zip` 与 `A4MergeAssistant.exe`；`main` 与 tag 推送 GitHub。
- **未做 / 待人工**（沿用维护记录 9）：无边框窗口的拖拽、贴边分屏、多屏与高 DPI 只能真机人工确认；
  Win10 实机建议目视一次 HarmonyOS Sans 的 ClearType 观感与阴影层次。

## 下一步

- **发布状态**：v1.0.3 已发布（tag `v1.0.3`），发布资产与本地 `dist/A4合并助手.exe` 同源
  （93,394,732 字节 / SHA256 `3A2ED45C…CCCA93` / 版本 1.0.3.0）。
- **后续维护**：新需求/缺陷按「改 → `pytest tests/` 全绿 → 重打包 → 提交 `M{编号}: …` → 发新版」的节奏走；
  发版时先提版本号并同步 README / 使用说明 / 验收单指纹 / `build/make_acceptance_kit.py`。
- **待人工**：Win10 实机与未装 WPS 机器按 `docs/M5人工异机验收单.md` 走一遍（重点 1.7~1.10 新界面项）；
  报障继续用诊断包收集（诊断 zip 带版本号）。
