# A4 合并助手 —— 开发进度记录（PROGRESS.md）

> 跨会话接力文件：每个新会话先读本文件 + docs/A4合并应用开发计划.md。
> 每完成一个里程碑：pytest 全绿 → git commit（+tag）→ 更新本文件 → 四段式汇报。

---

## 总览

| 里程碑 | 状态 | 备注 |
|---|---|---|
| M0 环境准备 | ✅ 完成（tag: m0） | 2026-02 基线建成 |
| M1 核心重构 | ✅ 完成（tag: m1） | 2026-10 pytest 28/28 全绿 |
| M2 GUI 骨架 | ⬜ 未开始 | 下一个 |
| M3 后台执行 | ⬜ 未开始 | |
| M4 结果体验 | ⬜ 未开始 | |
| M5 打包交付 | ⬜ 未开始 | |
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

## 遗留问题 / 注意点

1. 全局环境装了样例生成工具（python-docx/openpyxl/python-pptx），仅供 make_samples 使用，不进运行时依赖。
2. 样例里 encrypted 场景暂只有加密 PDF；加密 Office（docx 加密）待 M1 评估生成方式（msoffcrypto 仅支持解密）。
3. 字体已提交 git（16.4MB），仓库变大可接受（离线可复现优先）。

## 下一步（M1 核心重构）

按计划 4 节 M1：拆 core 包（types/collect/encrypt/converters/merge/report/runner/deps）→
回调接口替换 print/input → 输出双模式 → 损坏 PDF 容错（3.10）→ txt 字体与编码（3.11.1）→
pytest 黄金样本（3.11.13）→ cli.py 回归对照（内容级一致）。