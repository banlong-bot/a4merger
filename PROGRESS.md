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

## 下一步

项目收官：milestone 全部完成（M0~M6），git tag：baseline-v0, m0~m6, v1.0.0, v1.0.1, v1.0.2。
后续维护：新需求/缺陷按「改 → pytest tests/ 全绿 → 重打包 → 发新版」节奏走；
报障收集用诊断包（诊断 zip 会自动带上版本号，能确认同事跑的是哪一版）。
