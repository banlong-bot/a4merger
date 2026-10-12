# -*- mode: python ; coding: utf-8 -*-
"""build/make_version_info.py —— 生成 Windows version resource 与 longPathAware manifest。

计划 3.11.10：`--version-file` 写入文件属性版本（见下方 VERSION，发布新版本时改这里），
关于对话框显示版本号与构建时间；
计划 3.11.3：manifest 声明 longPathAware，让 exe 获得长路径感知。

被 build/a4merger.spec 导入使用（打包时自动写出 version_info.txt 与 a4merger.manifest）；
也可单独执行以只生成这两个文本文件、人工核对内容：
    python build/make_version_info.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VERSION = (1, 0, 1, 0)
VERSION_TEXT = ".".join(str(x) for x in VERSION)
APP_NAME = "A4 合并助手"
COMPANY = "A4 合并助手"
DESCRIPTION = "把文件夹里的 PDF/图片/Office/文本按顺序合并成统一的 A4 PDF"
COPYRIGHT = "© 2026 A4 合并助手"

# exe 内嵌 Python（见计划 3.4：建议 3.11，本机锁定环境 3.12）
EMBEDDED_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

VERSION_INFO_TEXT = f"""# UTF-8 —— PyInstaller version resource（由 build/make_version_info.py 生成）
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSION},
    prodvers={VERSION},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '080404b0',
        [StringStruct('CompanyName', '{COMPANY}'),
        StringStruct('FileDescription', '{DESCRIPTION}'),
        StringStruct('FileVersion', '{VERSION_TEXT}'),
        StringStruct('InternalName', 'A4合并助手'),
        StringStruct('LegalCopyright', '{COPYRIGHT}'),
        StringStruct('OriginalFilename', 'A4合并助手.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{VERSION_TEXT}')])
      ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""

MANIFEST_TEXT = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <!-- 注意：不要声明 assemblyIdentity / 依赖程序集，否则会触发 SideBySide 错误
       （WinError 14001 应用程序无法启动，应用程序的并行配置不正确）。 -->
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows 10 / 11 -->
      <supportedOS Id="{{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}}"/>
    </application>
  </compatibility>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <!-- 计划 3.11.3：声明长路径感知 -->
      <longPathAware xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">true</longPathAware>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2</dpiAwareness>
    </windowsSettings>
  </application>
</assembly>
"""

_STAMP_RE = re.compile(r"^BUILD_TIMESTAMP\s*=\s*[0-9.]+\s*$", re.M)


def write_build_stamp(repo: Path, stamp: float) -> str:
    """把构建时间戳写进 app/diagnostics.py，返回原文（打包结束用 restore 还原）。"""
    target = Path(repo) / "app" / "diagnostics.py"
    original = target.read_text(encoding="utf-8")
    updated, n = _STAMP_RE.subn(f"BUILD_TIMESTAMP = {stamp:.1f}", original)
    if n != 1:
        raise RuntimeError("未能在 app/diagnostics.py 中找到 BUILD_TIMESTAMP 定义行")
    target.write_text(updated, encoding="utf-8")
    return original


def restore_build_stamp(repo: Path, original: str) -> None:
    """还原 app/diagnostics.py（构建时间戳只进打包产物，不进仓库）。"""
    target = Path(repo) / "app" / "diagnostics.py"
    target.write_text(original, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    out_dir = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "version_info.txt").write_text(VERSION_INFO_TEXT, encoding="utf-8")
    (out_dir / "a4merger.manifest").write_text(MANIFEST_TEXT, encoding="utf-8")
    print(f"已生成：{out_dir / 'version_info.txt'}")
    print(f"已生成：{out_dir / 'a4merger.manifest'}")
    print(f"版本号：{VERSION_TEXT}    内嵌 Python：{EMBEDDED_PYTHON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
