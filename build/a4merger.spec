# -*- mode: python ; coding: utf-8 -*-
"""build/a4merger.spec —— PyInstaller 打包配置（计划 3.4 / 3.11.3 / 3.11.10，M5）。

用法（工程根目录执行，环境＝ requirements-dev.txt 锁定的 Python 3.12）：
    python -m PyInstaller --noconfirm --clean build/a4merger.spec

产物：dist/A4合并助手.exe（onefile + windowed，无控制台黑框）

要点：
  · 中文字体 fonts/ 进 datas（纯 Python 文本转 PDF 用，见 3.11.1）；
  · 应用图标 assets/app.ico：icon= 写进 exe 的 PE 资源（桌面/任务栏/文件图标），
    同时进 datas 供 app/icon.py 运行期取用（窗口图标）；由 build/make_icon.py 生成；
  · 隐藏导入：pypdf / PIL / fpdf / msoffcrypto（见 3.4）；
  · version resource（build/version_info.txt）+ longPathAware manifest（见 3.11.3）；
  · 依赖全部内置，运行期绝不触发 pip（core/deps.py 的 sys.frozen 分流，见 3.8.3）；
  · 构建时间戳写入 app/diagnostics.py 的 BUILD_TIMESTAMP（打包期间临时改写，结束还原）。
"""
import sys
import time
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
REPO = SPEC_DIR.parent
sys.path.insert(0, str(REPO))

from build.make_version_info import (MANIFEST_TEXT, VERSION_INFO_TEXT,  # noqa: E402
                                     restore_build_stamp, write_build_stamp)

STAMP = time.time()
VERSION_INFO_FILE = SPEC_DIR / "version_info.txt"
MANIFEST_FILE = SPEC_DIR / "a4merger.manifest"
# 应用图标：换图只需替换 assets/app-icon.jpg 后执行 `python build/make_icon.py` 重打包。
ICON_FILE = REPO / "assets" / "app.ico"
if not ICON_FILE.exists():
    raise SystemExit(f"缺少应用图标 {ICON_FILE}：先执行 python build/make_icon.py")
VERSION_INFO_FILE.write_text(VERSION_INFO_TEXT, encoding="utf-8")
MANIFEST_FILE.write_text(MANIFEST_TEXT, encoding="utf-8")
# 构建时间戳只在打包期间存在；无论成败都还原（异常也还原，避免仓库被污染）
_ORIGINAL_DIAGNOSTICS = write_build_stamp(REPO, STAMP)
try:
    a = Analysis(
        [str(REPO / "run_gui.py")],
        pathex=[str(REPO)],
        binaries=[],
        datas=[
            (str(REPO / "fonts" / "NotoSansCJKsc-Regular.otf"), "fonts"),
            (str(REPO / "app" / "theme.qss"), "app"),      # 主窗口皮肤 QSS（app/theme.py 运行期读取）
            (str(ICON_FILE), "assets"),
        ],
        hiddenimports=[
            # pypdf 6.19 无 pypdf._crt（旧版才有），不要写不存在的东西（会报 ERROR 噪音）
            "pypdf", "PIL", "PIL.Image", "PIL.ImageFile",
            "fpdf", "fpdf.svg", "msoffcrypto", "msoffcrypto.format",
            "msoffcrypto.format.ooxml", "msoffcrypto.format.doc97",
        ],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[str(SPEC_DIR / "rthook_tempdir.py")],   # 临时目录自愈（见该文件说明）
        excludes=[
            # 注意：不要排除 unittest —— fpdf2 的 fpdf/sign.py 会 import unittest，
            # 一旦排除会导致「纯 Python 引擎不可用」（文本/图片兜底全部失效）。
            "tkinter", "pydoc", "doctest", "test",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
            "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtQuick",
            "PySide6.QtQml", "PySide6.QtBluetooth", "PySide6.QtCharts",
            "PySide6.QtDataVisualization", "PySide6.QtDesigner",
            "PySide6.QtNetworkAuth", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
            "PySide6.QtPositioning", "PySide6.QtQuick3D", "PySide6.QtRemoteObjects",
            "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
            "PySide6.QtStateMachine", "PySide6.QtTest", "PySide6.QtTextToSpeech",
            "PySide6.QtWebChannel", "PySide6.QtWebSockets",
        ],
        noarchive=False,
        optimize=0,
    )
    pyz = PYZ(a.pure)

    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="A4合并助手",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,                       # --windowed：无控制台黑框
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(ICON_FILE),                 # 应用图标（窗口/任务栏/文件图标，见顶部说明）
        version=str(VERSION_INFO_FILE),      # 文件属性版本（3.11.10）
        manifest=str(MANIFEST_FILE),         # longPathAware（3.11.3）
    )
finally:
    restore_build_stamp(REPO, _ORIGINAL_DIAGNOSTICS)
    print(f"[a4merger.spec] 构建时间戳已还原；本次构建时间戳 = {STAMP:.1f}"
          f"（写入 exe 的 app/diagnostics.py）")
