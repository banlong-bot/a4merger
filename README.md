# A4 合并助手

把文件夹里的 **PDF / 图片 / Office（WPS 引擎）/ 文本** 按顺序合并成统一 **A4 版式** PDF 的 Windows 桌面工具。PySide6 编写，PyInstaller 打包为单文件绿色 exe，双击即用、无需安装。

## 功能特性

- **批量合并**：根目录下每个一级子文件夹＝一个目标，可勾选只处理部分
- **输出模式**：A＝各子文件夹内生成 / B＝统一集中输出（防套娃）；支持两级处理级别
- **命名模板**：成品文件名支持 `{folder}` 变量，默认 `【合并】{folder}.pdf`
- **排版参数**：四周留白、A4 方向（自动/纵向/横向）、图片适配（铺满/只缩小不放大）
- **转换引擎**：自动 / 仅 WPS / 仅纯 Python —— 没有 WPS 也能合并 PDF、图片、txt；加密 Office 文件可解密后合并
- **加密文件**：弹窗输入密码、常用密码列表（每行一个）、遇加密直接跳过并记录；记住的密码使用 Windows DPAPI 本机加密
- **结果清单**：成功/失败/同名/忽略四类列表，双击任意一行在资源管理器定位；一键打开输出目录与合并报告、导出 TXT
- **诊断支持**：菜单「文件 → 导出诊断包…」自动打包日志、配置（密码打码）、引擎探测结果
- **稳健性**：单实例防重复启动、长路径支持、临时目录自愈、取消安全（不产生半成品）

## 快速开始

**直接使用**：从 [Releases](../../releases) 下载 `A4合并助手.exe`，放到浅目录（如 `D:\A4合并助手\`）双击运行。首次启动需解包，等待 3~10 秒属正常。同事向使用说明见 [docs/使用说明-给同事.md](docs/使用说明-给同事.md)。

**从源码构建**（需要 Python 3.12+）：

```bash
pip install -r requirements.txt   # PySide6 / pypdf / Pillow / fpdf2 / msoffcrypto-tool
python run_gui.py                 # 运行
python -m pytest -q               # 测试（67 用例，含 GUI 冒烟与打包版验收）
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyi_work build\a4merger.spec
```

## 目录结构

```
app/     主程序（main / ui_main / results_dialog / settings / worker / diagnostics）
build/   打包 spec 与一键验收脚本
tests/   pytest 测试（含冻结版 exe 验收：版本资源、无黑框、单实例、全流程真实合并）
docs/    使用说明、开发计划、里程碑验收记录
fonts/   内置字体（Noto Sans CJK）
```

## 开发里程碑

M1–M6 完整开发记录见 [PROGRESS.md](PROGRESS.md)；M6 已完成灰度试运行并全员铺开。

## 开源协议

本项目遵循开源协议发布，详见 [LICENSE](LICENSE)。