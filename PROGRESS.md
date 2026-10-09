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
| M5 打包交付 | ⬜ 未开始 | 下一个 |
| M6 灰度试运行 | ⬜ 未开始 | |

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

## M5 计划（下一里程碑）

PyInstaller 单 exe：`build/a4merger.spec`（version resource、manifest longPathAware、
字体 datas、pypdf/Pillow/fpdf2/msoffcrypto 隐藏导入）、`--windowed` 无黑框，
在「装 WPS / 未装 WPS」两类机器实机验证（无 Python、断网、长路径、双实例）。

## 遗留问题 / 注意点

1. 全局环境装了样例生成工具（python-docx/openpyxl/python-pptx），仅供 make_samples 使用，不进运行时依赖。
2. 样例里 encrypted 场景暂只有加密 PDF；加密 Office（docx 加密）待 M1 评估生成方式（msoffcrypto 仅支持解密）。
3. 字体已提交 git（16.4MB），仓库变大可接受（离线可复现优先）。
4. `build/` 目录已有历史残留（早期 PyInstaller 输出？）+ 本次的 `build/shot_results_dialog.py`
   （离屏渲染结果对话框截图，人工核对版面用；截图目录已加 .gitignore）。M5 前建议确认 `build/` 是否入库。
5. 回归稳定性加固（M4 顺带修复，非功能变更）：`test_worker_cancel_quick` 需把队列里
   `finished_signal` 处理干净再断言；`test_single_instance_lock` 改为两实例同时启动 + 3 次重试与 stderr 诊断；
   `test_worker_password_flow/skip` 改用临时目录（不再写入样例库）。
6. 结果对话框真机显示效果仍待 M6 灰度确认（offscreen 下已核对控件与文本）。

## 下一步

**M5 打包交付**：按上节 M5 计划做 PyInstaller 单 exe 与两类机器实机验证；
M4 已完成，验收标准（计划 4 节：总结对话框/失败清单双击定位/导出 TXT/状态栏）全部满足。