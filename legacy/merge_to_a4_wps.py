#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
merge_to_a4_wps.py —— 把每个文件夹（默认是一级子文件夹，例如每位股东/客户）里的
PDF、图片、Word 等文件按文件名顺序合并成一个页面统一为 A4 的 PDF，
结果保存在该文件夹里（默认用文件夹名命名）。

每个人的资料通常分散在若干子文件夹里（1.身份证、2.出资核查…），脚本会把这些子文件夹
里的文件按「子文件夹顺序 + 文件夹内顺序」串起来，合成这一个人的一份完整 PDF。

转换引擎使用本机的 WPS（WPS 文字 / WPS 表格 / WPS 演示），不依赖微软 Office。
合并排版使用纯 Python 的 pypdf，把每一页等比缩放并居中排到 A4 页面上。

常用用法：
    python merge_to_a4_wps.py                    # 每个一级子文件夹合成一个 PDF（默认）
    python merge_to_a4_wps.py --level 2          # 改为每个二级子文件夹各合成一个 PDF
    python merge_to_a4_wps.py -r "D:\\某目录"     # 指定根目录
    python merge_to_a4_wps.py --dry-run          # 只预览将合并哪些文件，不生成 PDF
    python merge_to_a4_wps.py --orientation portrait   # 全部输出为 A4 纵向
    python merge_to_a4_wps.py --margin-mm 5      # 四周留 5mm 白边（默认铺满）
    python merge_to_a4_wps.py --output-name "合并_{folder}.pdf"
    python merge_to_a4_wps.py --image-fit origin # 图片不放大，只保证不超出 A4
    python merge_to_a4_wps.py --include-lookalikes     # 连同"与文件夹同名的 PDF"一起合并
    python merge_to_a4_wps.py --password 123456        # 遇到加密文件时用的打开密码
    python merge_to_a4_wps.py --password-file 密码.txt  # 密码写在文件里，每行一个

合并顺序：按相对路径的自然顺序（数字按大小排，如 2 在 10 前面）。

依赖：Python 3.9+、pypdf（合并用，缺了会自动尝试 pip 安装）；Pillow 为可选兜底。
      WPS Office 需已安装（脚本自动调用其 COM 接口）。

加密文件（需要密码才能打开的 PDF / Word / 表格）：
    · 只限制编辑、不需要密码的 PDF 会自动解开，正常合并；
    · 遇到真需要密码的文件，脚本会停下来提示你输入（最多试 3 次，直接回车＝跳过）；
    · 也可以提前把密码用 --password / --password-file 交给脚本，就不会中途打断；
    · 输入过的密码会被记住，后面同密码的文件自动使用；
    · 最终没能打开的文件会在结尾单独列出，不影响其它文件正常合并。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ------------------------------------------------------------------ 基本参数

A4_WIDTH_PT = 595.276     # A4 宽 210mm（单位：点）
A4_HEIGHT_PT = 841.89     # A4 高 297mm
MM = 72.0 / 25.4          # 1 毫米等于多少点

IMAGE_EXTS = {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".gif",
              ".tif", ".tiff", ".webp", ".heic"}
PDF_EXTS = {".pdf"}
WORD_EXTS = {".doc", ".docx", ".docm", ".rtf", ".wps"}
EXCEL_EXTS = {".xls", ".xlsx", ".xlsm", ".csv", ".et"}
PPT_EXTS = {".ppt", ".pptx", ".pptm", ".dps"}
TEXT_EXTS = {".txt", ".log", ".md"}
OOXML_EXTS = {".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm"}

SUPPORTED_EXTS = IMAGE_EXTS | PDF_EXTS | WORD_EXTS | EXCEL_EXTS | PPT_EXTS | TEXT_EXTS

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"    # 老式 Office 复合文档的文件头
PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

# WPS 的 COM 组件：文字 / 表格 / 演示
WPS_WORD_PROGID = "KWPS.Application"
WPS_EXCEL_PROGID = "KET.Application"
WPS_PPT_PROGID = "KWPP.Application"

# ------------------------------------------------------------------ WPS 转换脚本
#
# 下面这段 PowerShell 是"干活"的部分：它通过 COM 让 WPS 把各种文件导出成 PDF。
# 之所以不直接用 Python 调 COM，是为了不额外依赖 pywin32；PowerShell 每台 Windows 都有。
# 注意：这段脚本必须是纯 ASCII，否则 Windows PowerShell 5.1 会因编码问题读错中文注释。

WPS_WORKER_PS = r'''
param(
  [Parameter(Mandatory=$true)][string]$JobPath,
  [Parameter(Mandatory=$true)][string]$ResultPath
)

$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# read the JSON into a variable first: writing @(pipeline | ConvertFrom-Json)
# makes PowerShell treat several jobs as one array element
$parsed = ConvertFrom-Json -InputObject (Get-Content -LiteralPath $JobPath -Raw -Encoding UTF8)
$jobs = @($parsed)

$script:WordApp = $null
$script:ExcelApp = $null
$script:PptApp = $null

function Get-WordApp {
  if ($null -eq $script:WordApp) {
    $app = New-Object -ComObject __WPS_WORD__
    $app.Visible = $false
    try { $app.DisplayAlerts = 0 } catch {}
    $script:WordApp = $app
  }
  return $script:WordApp
}

function Get-ExcelApp {
  if ($null -eq $script:ExcelApp) {
    $app = New-Object -ComObject __WPS_EXCEL__
    $app.Visible = $false
    try { $app.DisplayAlerts = $false } catch {}
    $script:ExcelApp = $app
  }
  return $script:ExcelApp
}

function Get-PptApp {
  if ($null -eq $script:PptApp) {
    $app = New-Object -ComObject __WPS_PPT__
    try { $app.Visible = $false } catch {}
    $script:PptApp = $app
  }
  return $script:PptApp
}

function Export-DocAsPdf($doc, $out) {
  try {
    $doc.ExportAsFixedFormat($out, 17)      # 17 = wdExportFormatPDF
  } catch {
    $doc.SaveAs2($out, 17)                  # 17 = wdFormatPDF
  }
}

function Get-Passwords($p) {
  # candidate passwords; always keep one empty password as the fallback
  $list = @()
  foreach ($x in @($p)) { if ($null -ne $x) { $list += [string]$x } }
  if ($list.Count -eq 0) { $list = @("") }
  return , $list
}

function Convert-Word($src, $out, $passwords) {
  $app = Get-WordApp
  $doc = $null
  $last = ""
  # try each candidate password; passing a password explicitly stops WPS from
  # popping up a password dialog and blocking the automation
  foreach ($pwd in $passwords) {
    try {
      $doc = $app.Documents.Open($src, $false, $true, $false, $pwd, $pwd)
      break
    } catch {
      $last = $_.Exception.Message
    }
  }
  if ($null -eq $doc) { throw "cannot open the file: $last" }
  try {
    try { $doc.PageSetup.PaperSize = 7 } catch {}   # 7 = wdPaperA4
    Export-DocAsPdf $doc $out
  } finally {
    $doc.Close(0)
  }
}

function Convert-Image($src, $out, $fitToPage) {
  $app = Get-WordApp
  $doc = $app.Documents.Add()
  try {
    $ps = $doc.PageSetup
    $ps.PaperSize = 7
    $ps.TopMargin = 0; $ps.BottomMargin = 0; $ps.LeftMargin = 0; $ps.RightMargin = 0
    $shape = $doc.InlineShapes.AddPicture($src, $false, $true)
    $w0 = $shape.Width
    $h0 = $shape.Height
    $availW = $ps.PageWidth
    $availH = $ps.PageHeight
    $scale = [Math]::Min($availW / $w0, $availH / $h0)
    if (-not $fitToPage) { $scale = [Math]::Min($scale, 1.0) }
    $tw = $w0 * $scale
    $th = $h0 * $scale
    # set both dimensions explicitly so WPS will not rescale them again
    $shape.LockAspectRatio = 0
    $shape.Width = $tw
    $shape.Height = $th
    try { $doc.Paragraphs.Item(1).Alignment = 1 } catch {}   # 1 = center the paragraph
    try { $ps.LeftMargin = 0 } catch {}
    try { $ps.RightMargin = 0 } catch {}
    # center vertically by pushing the picture with the top/bottom margins
    $ps.TopMargin = [Math]::Max(($availH - $th) / 2, 0)
    $ps.BottomMargin = [Math]::Max($availH - $th - $ps.TopMargin, 0)
    Export-DocAsPdf $doc $out
  } finally {
    $doc.Close(0)
  }
}

function Convert-Excel($src, $out, $passwords) {
  $app = Get-ExcelApp
  $wb = $null
  $last = ""
  foreach ($pwd in $passwords) {
    try {
      $wb = $app.Workbooks.Open($src, 0, $true, 0, $pwd, $pwd)
      break
    } catch {
      $last = $_.Exception.Message
    }
  }
  if ($null -eq $wb) { throw "cannot open the file: $last" }
  try {
    foreach ($ws in $wb.Worksheets) {
      try {
        $ws.PageSetup.PaperSize = 9          # 9 = xlPaperA4
        $ws.PageSetup.Zoom = $false
        $ws.PageSetup.FitToPagesWide = 1     # squeeze columns into one page wide
        $ws.PageSetup.FitToPagesTall = $false
      } catch {}
    }
    $wb.ExportAsFixedFormat(0, $out)         # 0 = xlTypePDF
  } finally {
    $wb.Close($false)
  }
}

function Convert-Ppt($src, $out) {
  $app = Get-PptApp
  $pres = $app.Presentations.Open($src, $true, $false, $false)
  try {
    $pres.SaveAs($out, 32)                   # 32 = ppSaveAsPDF
  } finally {
    $pres.Close()
  }
}

$results = New-Object System.Collections.ArrayList

foreach ($job in $jobs) {
  $item = [ordered]@{ src = $job.src; out = $job.out; ok = $false; error = "" }
  try {
    if (Test-Path -LiteralPath $job.out) { Remove-Item -LiteralPath $job.out -Force }
    switch ($job.kind) {
      "word"  { Convert-Word  $job.src $job.out (Get-Passwords $job.passwords) }
      "text"  { Convert-Word  $job.src $job.out @("") }
      "image" { Convert-Image $job.src $job.out ([bool]$job.fit) }
      "excel" { Convert-Excel $job.src $job.out (Get-Passwords $job.passwords) }
      "ppt"   { Convert-Ppt   $job.src $job.out }
      default { throw "unknown kind: $($job.kind)" }
    }
    if ((Test-Path -LiteralPath $job.out) -and ((Get-Item -LiteralPath $job.out).Length -gt 0)) {
      $item.ok = $true
    } else {
      throw "WPS did not produce an output file"
    }
  } catch {
    $item.error = $_.Exception.Message
  }
  [void]$results.Add([pscustomobject]$item)
}

foreach ($app in @($script:WordApp, $script:ExcelApp, $script:PptApp)) {
  if ($null -ne $app) { try { $app.Quit() } catch {} }
}

$resultArray = @()
foreach ($r in $results) { $resultArray += $r }
$payload = [pscustomobject]@{
  jobCount = $jobs.Count
  results  = $resultArray
}
[IO.File]::WriteAllText($ResultPath, ($payload | ConvertTo-Json -Depth 5),
  (New-Object System.Text.UTF8Encoding($false)))
'''.replace("__WPS_WORD__", WPS_WORD_PROGID) \
   .replace("__WPS_EXCEL__", WPS_EXCEL_PROGID) \
   .replace("__WPS_PPT__", WPS_PPT_PROGID)


# ------------------------------------------------------------------ 通用小工具

def natural_key(text: str):
    """自然排序键：文件名里的数字按数值大小比较（2 排在 10 前面）。"""
    parts = re.split(r"(\d+)", text)
    return [(0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts if p != ""]


def log(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # 极少数老控制台编码装不下某些符号时，退化成能显示的字符，保证脚本继续跑
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def setup_console() -> None:
    """尽量让中文和符号在控制台里正常显示（管道/重定向时也能读）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    # pypdf 内部会把 "EOF marker not found" 之类的英文警告打到屏幕上，这里静音，
    # 由脚本自己用中文汇总报告
    import logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)


def decode_bytes(data: bytes) -> str:
    """Windows 下的命令行输出可能是 UTF-8 也可能是 GBK，尽力解码。"""
    for enc in ("utf-8", "gbk", "mbcs"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def find_powershell() -> str | None:
    for name in ("powershell", "powershell.exe", "pwsh", "pwsh.exe"):
        found = shutil.which(name)
        if found:
            return found
    fallback = Path(os.environ.get("SystemRoot", r"C:\Windows")) / \
        "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(fallback) if fallback.exists() else None


# ------------------------------------------------------------------ WPS 调用

def wps_kind(ext: str) -> str | None:
    """把扩展名映射成 WPS 的处理方式。"""
    if ext in IMAGE_EXTS:
        return "image"
    if ext in WORD_EXTS or ext in TEXT_EXTS:
        return "word" if ext in WORD_EXTS else "text"
    if ext in EXCEL_EXTS:
        return "excel"
    if ext in PPT_EXTS:
        return "ppt"
    return None


def run_wps_worker(jobs: list[dict], tmp_dir: Path, timeout: int) -> list[dict]:
    """把一批转换任务交给 WPS 处理，返回每个任务的结果。

    WPS 的后台实例偶尔会"没睡醒"，第一次调用不响应；这里如实返回结果，
    由调用方决定是否重试。
    """
    if not jobs:
        return []

    powershell = find_powershell()
    if not powershell:
        return [{"src": j["src"], "out": j["out"], "ok": False,
                 "error": "本机找不到 PowerShell，无法调用 WPS"} for j in jobs]

    job_file = tmp_dir / "wps_jobs.json"
    result_file = tmp_dir / "wps_results.json"
    ps_file = tmp_dir / "wps_worker.ps1"
    job_file.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    # 带 BOM 写出，Windows PowerShell 5.1 才会按 UTF-8 正确读取
    ps_file.write_text(WPS_WORKER_PS, encoding="utf-8-sig")
    if result_file.exists():
        result_file.unlink()

    cmd = [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-File", str(ps_file), str(job_file), str(result_file)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [{"src": j["src"], "out": j["out"], "ok": False,
                 "error": f"WPS 转换超时（超过 {timeout} 秒，多半是文件需要密码或已损坏）"}
                for j in jobs]

    if result_file.exists():
        try:
            data = json.loads(result_file.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict) and "results" in data:
                items = data.get("results") or []
                if len(items) < len(jobs):
                    log(f"   !  WPS 只处理了 {len(items)}/{len(jobs)} 个文件（后台可能未就绪）")
                return items
            return data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            pass

    detail = decode_bytes(proc.stdout or b"").strip() or decode_bytes(proc.stderr or b"").strip()
    detail = detail.splitlines()[-1] if detail else f"PowerShell 退出码 {proc.returncode}"
    return [{"src": j["src"], "out": j["out"], "ok": False,
             "error": f"WPS 调用失败：{detail}"} for j in jobs]


def pillow_image_to_pdf(src: Path, out: Path) -> None:
    """WPS 转换失败时，图片用 Pillow 直接落成 PDF（合并时会再排进 A4）。"""
    from PIL import Image, ImageOps

    with Image.open(src) as im:
        frames = getattr(im, "n_frames", 1)
        if frames > 1:
            pages = []
            for i in range(frames):
                im.seek(i)
                pages.append(ImageOps.exif_transpose(im.copy()).convert("RGB"))
            pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=150)
            return
        page = ImageOps.exif_transpose(im.copy())
        if page.mode not in ("RGB", "L"):
            page = page.convert("RGB")
        page.save(out, "PDF", resolution=150)


# ------------------------------------------------------------------ 加密文件

def ensure_module(import_name: str, pip_name: str) -> bool:
    """确保某个库可用，缺了就自动安装（官方源不通时换国内镜像）。"""
    try:
        __import__(import_name)
        return True
    except ImportError:
        pass
    log(f"未检测到 {pip_name}，正在尝试自动安装……")
    tries = [
        [sys.executable, "-m", "pip", "install", "--quiet", pip_name],
        [sys.executable, "-m", "pip", "install", "--quiet", "--retries", "2",
         "-i", PYPI_MIRROR, pip_name],
    ]
    for cmd in tries:
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            __import__(import_name)
            return True
        except Exception:
            continue
    log(f"{pip_name} 自动安装失败，可手动执行：pip install {pip_name}")
    return False


def office_needs_password(path: Path) -> bool:
    """判断 Office 文件是否需要打开密码。

    docx/xlsx/pptx 正常是 zip 包，加了打开密码后会变成 OLE 复合文档；
    老格式 doc/xls/ppt 则看文件里有没有加密流。
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
            if path.suffix.lower() in OOXML_EXTS:
                return head == OLE_MAGIC
            blob = fh.read(4 * 1024 * 1024)
        return b"EncryptedPackage" in blob or b"EncryptionInfo" in blob
    except OSError:
        return False


def decrypt_office(src: Path, passwords: list[str], tmp_dir: Path,
                   index: int) -> Path | None:
    """把带打开密码的 Office 文件解密成临时副本。

    这样交给 WPS 的永远是普通文件，WPS 不会弹密码框、也就不会把自动化卡住。
    """
    if not passwords:
        return None
    if not ensure_module("msoffcrypto", "msoffcrypto-tool"):
        return None

    import msoffcrypto

    out = tmp_dir / f"{index:04d}_decrypted{src.suffix.lower()}"
    for pwd in passwords:
        try:
            with open(src, "rb") as fh, open(out, "wb") as ofh:
                office = msoffcrypto.OfficeFile(fh)
                office.load_key(password=pwd)
                office.decrypt(ofh)
            if out.exists() and out.stat().st_size > 0:
                return out
        except Exception:
            try:
                out.unlink()
            except OSError:
                pass
            continue
    return None


def office_password_ok(src: Path, password: str, tmp_dir: Path) -> bool:
    """验证 Office 打开密码是否正确（能解开就是对的）。"""
    return decrypt_office(src, [password], tmp_dir, 9999) is not None


def pdf_needs_password(path: Path) -> bool:
    """PDF 是否需要打开密码（只限制编辑/打印的 PDF 不算）。"""
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
        if not reader.is_encrypted:
            return False
        try:
            return not bool(reader.decrypt(""))
        except Exception:
            return True
    except Exception:
        return False


def pdf_password_ok(path: Path, password: str) -> bool:
    """用某个密码试着打开 PDF，判断密码是否正确。"""
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
        return (not reader.is_encrypted) or bool(reader.decrypt(password))
    except Exception:
        return False


def ask_password(path: Path, verify, args, known: list[str]) -> str | None:
    """停下来让用户输入密码：已知密码先试，不行再交互式询问（最多 3 次）。"""
    for pwd in known:
        if verify(pwd):
            return pwd
    if not args.prompt:
        return None

    log(f"   ⏸  「{path.name}」已加密，需要密码")
    for _ in range(3):
        try:
            typed = input("      请输入打开密码（直接回车＝跳过这个文件）：").strip()
        except (EOFError, KeyboardInterrupt):
            log("      （当前环境无法输入密码，已跳过）")
            return None
        if not typed:
            return None
        if verify(typed):
            if typed not in known:
                known.append(typed)          # 记下来，后面遇到同密码的文件直接用
            log("      ✔ 密码正确")
            return typed
        log("      ✘ 密码不正确，请重试")
    return None


# ------------------------------------------------------------------ 收集文件

def output_name_of(folder: Path, template: str) -> str:
    """按输出文件名模板算出某个文件夹的成品文件名。"""
    return template.format(folder=folder.name, name=folder.name)


def collect_files(folder: Path, skip: set[Path], template: str,
                  skip_lookalikes: bool = True) -> tuple[list[Path], list[Path]]:
    """递归收集文件夹里的文件（含更深层子文件夹），按自然顺序排序。

    返回（要合并的文件, 被判定为"上次生成的成品"而跳过的文件）。
    """
    files: list[Path] = []
    lookalikes: list[Path] = []
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("~$") or p.name.startswith("."):
            continue
        try:
            if p.resolve() in skip:
                continue
        except OSError:
            pass
        # 与所在文件夹同名的 PDF，通常是上一次运行生成的成品，不重复计入
        if skip_lookalikes and p.name == output_name_of(p.parent, template):
            lookalikes.append(p)
            continue
        files.append(p)
    files.sort(key=lambda p: natural_key(str(p.relative_to(folder)).replace("\\", "/")))
    lookalikes.sort(key=lambda p: natural_key(str(p.relative_to(folder)).replace("\\", "/")))
    return files, lookalikes


def iter_target_folders(root: Path, level: int):
    """level=1（默认）：每个一级子文件夹各合成一个 PDF；
    level=2：每个二级子文件夹各合成一个 PDF。
    一级文件夹/根目录里若直接放了受支持的文件，也会被当作一个目标。"""
    subdirs = sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")),
                     key=lambda p: natural_key(p.name))
    if level == 1:
        for d in subdirs:
            yield d
        if any(f.is_file() and f.suffix.lower() in SUPPORTED_EXTS for f in root.iterdir()):
            yield root
        return
    for d1 in subdirs:
        for d2 in sorted((p for p in d1.iterdir() if p.is_dir() and not p.name.startswith("_")),
                         key=lambda p: natural_key(p.name)):
            yield d2
        if any(f.is_file() and f.suffix.lower() in SUPPORTED_EXTS for f in d1.iterdir()):
            yield d1
    # 脚本所在目录里如果直接放着文件（没有子文件夹），也把它们合成一个 PDF
    if any(f.is_file() and f.suffix.lower() in SUPPORTED_EXTS for f in root.iterdir()):
        yield root


# ------------------------------------------------------------------ 合并成 A4

def fit_box(src_w: float, src_h: float, margin_mm: float, orientation: str):
    """算出 A4 页面尺寸，以及内容在页面里等比缩放后居中的位置。"""
    margin = margin_mm * MM
    if orientation == "landscape" or (orientation == "auto" and src_w > src_h):
        pw, ph = A4_HEIGHT_PT, A4_WIDTH_PT      # A4 横向
    else:
        pw, ph = A4_WIDTH_PT, A4_HEIGHT_PT      # A4 纵向
    avail_w = max(pw - 2 * margin, 1.0)
    avail_h = max(ph - 2 * margin, 1.0)
    scale = min(avail_w / src_w, avail_h / src_h)
    w, h = src_w * scale, src_h * scale
    x, y = (pw - w) / 2.0, (ph - h) / 2.0
    return pw, ph, (x, y, x + w, y + h)


def merge_to_a4(source_pdfs: list[Path], out_pdf: Path, margin_mm: float,
                orientation: str, title: str = "",
                passwords: list[str] | None = None,
                passwords_by_file: dict[str, str] | None = None,
                failures: list | None = None) -> tuple[int, list[str]]:
    """把若干 PDF 逐页等比缩放、居中排到 A4 页面上并合并；返回（总页数, 警告列表）。"""
    from pypdf import PdfReader, PdfWriter, Transformation

    passwords = [""] + list(passwords or [])
    passwords_by_file = passwords_by_file or {}
    writer = PdfWriter()
    warnings: list[str] = []
    total = 0
    for src in source_pdfs:
        try:
            reader = PdfReader(str(src))
            if reader.is_encrypted:
                candidates = list(dict.fromkeys(
                    ([passwords_by_file[str(src)]] if str(src) in passwords_by_file else [])
                    + passwords))
                for pwd in candidates:                # 先试空密码，再试已知密码
                    try:
                        if reader.decrypt(pwd):
                            break
                    except Exception:
                        continue
                else:
                    raise RuntimeError("PDF 已加密，需要打开密码")
            pages = list(reader.pages)
        except Exception as exc:
            warnings.append(f"{src.name}：无法读取（{exc}）")
            if failures is not None:
                failures.append((src, str(exc)))
            continue

        for page in pages:
            try:
                page.transfer_rotation_to_content()   # 把 /Rotate 并入内容，避免页面错位
            except Exception:
                pass
            box = page.cropbox if float(page.cropbox.width) > 0 else page.mediabox
            src_w, src_h = float(box.width), float(box.height)
            if src_w <= 1 or src_h <= 1:
                continue

            pw, ph, _ = fit_box(src_w, src_h, margin_mm, orientation)
            margin = margin_mm * MM
            avail_w = max(pw - 2 * margin, 1.0)
            avail_h = max(ph - 2 * margin, 1.0)
            scale = min(avail_w / src_w, avail_h / src_h)

            trsf = Transformation().scale(scale)
            p1 = trsf.apply_on((float(box.left), float(box.bottom)))
            p2 = trsf.apply_on((float(box.right), float(box.top)))
            x0, y0 = min(p1[0], p2[0]), min(p1[1], p2[1])
            x1, y1 = max(p1[0], p2[0]), max(p1[1], p2[1])
            trsf = trsf.translate(margin + (avail_w - (x1 - x0)) / 2.0 - x0,
                                  margin + (avail_h - (y1 - y0)) / 2.0 - y0)

            blank = writer.add_blank_page(width=pw, height=ph)
            blank.merge_transformed_page(page, trsf)
            total += 1

    if title:
        writer.add_metadata({"/Title": title})
    with open(out_pdf, "wb") as fh:
        writer.write(fh)
    return total, warnings


def ensure_pypdf() -> bool:
    """确保 pypdf 可用，缺了就尝试自动安装。"""
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        pass
    log("未检测到 pypdf，正在尝试自动安装……")
    tries = [
        [sys.executable, "-m", "pip", "install", "--quiet", "pypdf"],
        [sys.executable, "-m", "pip", "install", "--quiet", "--retries", "2",
         "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "pypdf"],
    ]
    for cmd in tries:                    # 官方源不通时自动换国内镜像
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            import pypdf  # noqa: F401
            return True
        except Exception:
            continue
    log("pypdf 自动安装失败，请手动执行：pip install pypdf")
    return False


# ------------------------------------------------------------------ 处理单个文件夹

def process_folder(folder: Path, out_path: Path, args, tmp_root: Path,
                   label: str = "", skip_extra: set[Path] | None = None) -> dict:
    """把 folder 里的文件转成 PDF 并合并成 A4 文档。"""
    result = {"folder": folder, "label": label or folder.name, "out": out_path,
              "files": [], "pages": 0,
              "warnings": [], "done": False, "ignored": [], "replaced_output": False,
              "lookalikes": [], "failed": []}

    # 跳过自己即将生成的 PDF，以及其它文件夹将要生成的合并结果，避免把上一次的成品又合并一遍
    skip = set(skip_extra or ()) | {out_path.resolve()}
    all_files, lookalikes = collect_files(folder, skip, args.output_name,
                                          not args.include_lookalikes)
    used = [f for f in all_files if f.suffix.lower() in SUPPORTED_EXTS]
    result["ignored"] = [f for f in all_files if f.suffix.lower() not in SUPPORTED_EXTS]
    result["lookalikes"] = lookalikes
    result["replaced_output"] = out_path.exists()
    result["files"] = used
    if not used:
        return result

    log(f"\n▶ {result['label']}   （{len(used)} 个文件）")
    for i, f in enumerate(used, 1):
        log(f"   {i:>3}. {f.relative_to(folder)}")
    if lookalikes:
        names = "、".join(str(f.relative_to(folder)) for f in lookalikes)
        log(f"   （跳过 {len(lookalikes)} 个「与所在文件夹同名」的 PDF，"
            f"视为上次生成的成品：{names}）")
    if result["replaced_output"]:
        log(f"   （已存在同名 PDF「{out_path.name}」，视为上次的合并结果："
            f"不计入本次合并，最后会被覆盖）")
    if args.dry_run:
        return result

    tmp_dir = Path(tempfile.mkdtemp(prefix="a4merge_", dir=str(tmp_root)))
    try:
        blocked: set[Path] = set()          # 拿不到密码、只能跳过的加密文件

        # 第零步：加密的 PDF 停下来问密码
        file_pw: dict[str, str] = {}
        for f in used:
            if f.suffix.lower() not in PDF_EXTS or not pdf_needs_password(f):
                continue
            pwd = ask_password(f, lambda p, _f=f: pdf_password_ok(_f, p),
                               args, args.known_passwords)
            if pwd is None:
                blocked.add(f)
                result["failed"].append((f, "PDF 已加密，没有可用的打开密码"))
                log(f"   !! 跳过 {f.name}：没有正确的打开密码")
                continue
            file_pw[str(f)] = pwd

        # 第一步：需要转换的文件交给 WPS
        jobs: list[dict] = []
        converted: dict[Path, Path] = {}
        for i, f in enumerate(used, 1):
            kind = wps_kind(f.suffix.lower())
            if f.suffix.lower() in PDF_EXTS or kind is None:
                continue

            # 带打开密码的 Office 文件：先自己解密再交给 WPS，避免 WPS 弹密码框卡住
            if kind in ("word", "excel", "ppt") and office_needs_password(f):
                plain = decrypt_office(f, args.known_passwords, tmp_dir, i)
                if plain is None and args.prompt:        # 停下来问密码
                    pwd = ask_password(f, lambda p, _f=f: office_password_ok(_f, p, tmp_dir),
                                       args, args.known_passwords)
                    if pwd is not None:
                        plain = decrypt_office(f, [pwd], tmp_dir, i)
                if plain is None:
                    blocked.add(f)
                    result["failed"].append((f, "Office 文件已加密，没有可用的打开密码"))
                    log(f"   !! 跳过 {f.name}：文件已加密，未能打开"
                        f"（可用 --password 指定密码）")
                    continue
                src_for_wps = plain
                log(f"   ·  {f.name}：已用密码解密后再交给 WPS")
            else:
                src_for_wps = f

            out = tmp_dir / f"{i:04d}_wps.pdf"
            job = {"kind": kind, "src": str(src_for_wps.resolve()), "out": str(out),
                   "fit": args.image_fit == "page"}
            if kind in ("word", "excel"):          # 密码候选：空密码 + 用户提供的
                job["passwords"] = [""] + list(getattr(args, "password_list", []) or [])
            jobs.append(job)
            converted[f] = out

        log("   → 调用 WPS 转换文档…" if jobs else "   → 全部为 PDF，无需转换")
        # WPS 后台偶尔第一次不响应，失败的文件自动再试一次
        by_out: dict[str, dict] = {}
        pending = list(jobs)
        for attempt in (1, 2, 3):
            if not pending:
                break
            if attempt == 3:                       # 最后再不行，就一个一个单独转
                log(f"   !  仍有 {len(pending)} 个文件没转成功，改为逐个重试…")
                batches = [[j] for j in pending]
            else:
                if attempt == 2:
                    log(f"   !  {len(pending)} 个文件第一次没转成功，稍后重试…")
                    time.sleep(1.5)
                batches = [pending]
            for batch in batches:
                for item in run_wps_worker(batch, tmp_dir, args.wps_timeout):
                    if not isinstance(item.get("out"), str):
                        continue                   # 结果结构异常，交给下一轮
                    key = item["out"]
                    if item.get("ok") or not by_out.get(key, {}).get("ok"):
                        by_out[key] = item
            # 超时的文件多半是卡在"需要密码"上，重复同样的尝试只会白等，不再重试
            pending = [j for j in pending
                       if not by_out.get(j["out"], {}).get("ok")
                       and "超时" not in str(by_out.get(j["out"], {}).get("error", ""))]

        sources: list[Path] = []
        for f in used:
            if f in blocked:
                continue
            if f.suffix.lower() in PDF_EXTS:
                sources.append(f)
                continue
            tmp_pdf = converted.get(f)
            item = by_out.get(str(tmp_pdf)) if tmp_pdf else None
            if tmp_pdf and tmp_pdf.exists() and (item is None or item.get("ok")):
                sources.append(tmp_pdf)
                continue
            # WPS 没成功时，图片还能用 Pillow 兜底
            if f.suffix.lower() in IMAGE_EXTS:
                why = (item or {}).get("error") or "未生成文件"
                try:
                    pillow_image_to_pdf(f, tmp_pdf)
                    sources.append(tmp_pdf)
                    result["warnings"].append(
                        f"{f.name}：WPS 转换失败（{why}），已改用 Pillow 生成图片页")
                    log(f"   !  {f.name}：WPS 转换失败（{why}），改用 Pillow 兜底")
                    continue
                except Exception as exc:
                    result["failed"].append((f, f"转换失败（{exc}）"))
                    continue
            reason = (item or {}).get("error") or "未知原因"
            result["failed"].append((f, f"WPS 转换失败（{reason}）"))
            log(f"   !! 跳过 {f.name}：{reason}")

        if not sources:
            result["warnings"].append("没有任何可合并的页面")
            return result

        # 第二步：统一排到 A4 并合并。
        # 结果先写在目标文件夹里的临时文件上，全部成功后再替换原文件：
        # 既避免半成品覆盖旧文件，也避免临时目录与目标不在同一个盘符时无法移动。
        final_tmp = out_path.parent / f"~$merge_tmp_{os.getpid()}.pdf"
        try:
            pages, warns = merge_to_a4(sources, final_tmp, args.margin_mm,
                                       args.orientation, title=folder.name,
                                       passwords=args.known_passwords,
                                       passwords_by_file=file_pw,
                                       failures=result["failed"])
            for w in warns:                     # 已在"失败清单"里，这里只即时提示
                log(f"   !! {w}")
            if pages == 0:
                result["warnings"].append("没有生成任何页面")
                return result

            os.replace(final_tmp, out_path)
        finally:
            if final_tmp.exists():
                final_tmp.unlink()

        result["pages"] = pages
        result["done"] = True
        log(f"   ✔ 已生成 {out_path.name}（{pages} 页，"
            f"{out_path.stat().st_size / 1024 / 1024:.1f} MB）")
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ------------------------------------------------------------------ 命令行

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="用 WPS 把每个一级子文件夹（例如每位股东）里的 PDF / 图片 / Word 等"
                    "文件按顺序合并成一个 A4 大小的 PDF。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-r", "--root", default=None,
                   help="根目录（默认为本脚本所在目录）")
    p.add_argument("--level", type=int, default=1, choices=(1, 2),
                   help="处理第几级子文件夹：1=每个一级子文件夹各合成一个 PDF（默认），"
                        "2=每个二级子文件夹各合成一个 PDF")
    p.add_argument("--output-name", default="{folder}.pdf",
                   help="输出文件名模板，默认 {folder}.pdf（{folder} 表示文件夹名）")
    p.add_argument("--margin-mm", type=float, default=0.0,
                   help="四周留白毫米数，默认 0（内容最大化铺满 A4）")
    p.add_argument("--orientation", default="auto",
                   choices=("auto", "portrait", "landscape"),
                   help="A4 方向：auto=横向内容用 A4 横向（默认）")
    p.add_argument("--image-fit", default="page", choices=("page", "origin"),
                   help="图片是否放大铺满 A4：page=铺满（默认），origin=只缩小不放大")
    p.add_argument("--wps-timeout", type=int, default=600,
                   help="调用 WPS 转换的超时秒数，默认 600")
    p.add_argument("--include-lookalikes", action="store_true",
                   help="把「与所在文件夹同名的 PDF」也当作素材合并进去"
                        "（默认视为上次生成的成品而跳过）")
    p.add_argument("--password", action="append", default=[],
                   help="加密文件的打开密码，可以写多次，也可以用逗号分隔多个，"
                        "例如 --password 123456 --password abc,888888")
    p.add_argument("--password-file", default=None,
                   help="从文本文件读取密码，每行一个")
    p.add_argument("--no-prompt", action="store_true",
                   help="遇到加密文件不要停下来询问密码，直接跳过")
    p.add_argument("--dry-run", action="store_true",
                   help="只列出将要合并的文件，不生成 PDF")
    return p


def load_passwords(args) -> list[str]:
    """汇总命令行和密码文件里的密码（去重，保持顺序）。"""
    words: list[str] = []
    for item in args.password or []:
        words.extend(x.strip() for x in str(item).split(","))
    if args.password_file:
        path = Path(args.password_file).expanduser()
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    words.extend(x.strip() for x in line.split(","))
        else:
            log(f"密码文件不存在：{path}")
    return list(dict.fromkeys(w for w in words if w != ""))


def main(argv=None) -> int:
    setup_console()
    args = build_parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve() if args.root \
        else Path(__file__).resolve().parent
    if not root.is_dir():
        log(f"根目录不存在：{root}")
        return 1

    if not args.dry_run and not ensure_pypdf():
        return 1

    args.prompt = not args.no_prompt
    args.known_passwords = load_passwords(args)     # 已知密码，后续遇到加密文件先拿它试
    if args.known_passwords:
        log(f"已载入 {len(args.known_passwords)} 个密码，用于尝试打开加密文件。")

    targets = list(iter_target_folders(root, args.level))
    if not targets:
        log(f"在 {root} 下没找到需要处理的文件夹。")
        return 0

    log(f"根目录：{root}")
    log(f"待处理文件夹：{len(targets)} 个" + ("（预览模式，不会生成文件）" if args.dry_run else ""))

    # 先把所有目标文件夹的输出文件名收集起来，互相之间不当作合并素材
    all_outputs = {(f / output_name_of(f, args.output_name)).resolve()
                   for f in targets}

    tmp_root = Path(tempfile.mkdtemp(prefix="a4merge_root_"))
    done = failed = 0
    results: list[dict] = []
    try:
        for folder in targets:
            out_path = folder / output_name_of(folder, args.output_name)
            label = str(folder.relative_to(root)) if folder != root else folder.name
            try:
                res = process_folder(folder, out_path, args, tmp_root, label, all_outputs)
            except Exception as exc:                 # 单个文件夹失败不影响其它文件夹
                log(f"   !! 处理失败：{exc}")
                res = {"folder": folder, "label": label, "out": out_path,
                       "files": [], "pages": 0,
                       "warnings": [str(exc)], "done": False, "ignored": [],
                       "replaced_output": out_path.exists(),
                       "lookalikes": [], "failed": []}
            results.append(res)
            if res["done"]:
                done += 1
            elif res["files"]:
                failed += 1
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    log("\n" + "=" * 62)
    if args.dry_run:
        log("预览完成，未生成任何文件。（去掉 --dry-run 即可真正生成）")
    else:
        log(f"处理完成：成功 {done} 个文件夹，失败 {failed} 个。")
        for res in results:
            if res["done"]:
                log(f"  ✔ {res['label']} → {res['out'].name}"
                    f"（{res['pages']} 页）")
            elif res["files"]:
                old = res.get("out")
                keep = "（原来的同名 PDF 保留未更新）" if old and old.exists() else ""
                log(f"  ✘ {res['label']} 未生成{keep}")
    warns = [(r["label"], w) for r in results for w in r["warnings"]]
    if warns:
        log("\n注意事项：")
        for name, w in warns:
            log(f"  · [{name}] {w}")
    # 汇总没能打开/合并的文件，加密 PDF 单独标出来
    failures = [(r["folder"], f, why) for r in results for f, why in r["failed"]]
    if failures:
        def _show(p: Path) -> str:
            try:
                return str(p.relative_to(root))
            except Exception:
                return str(p)

        pdf_fail = [x for x in failures if x[1].suffix.lower() in PDF_EXTS]
        other_fail = [x for x in failures if x[1].suffix.lower() not in PDF_EXTS]
        log(f"\n没能成功打开/合并的文件共 {len(failures)} 个：")
        if pdf_fail:
            log(f"  【PDF（{len(pdf_fail)} 个）】")
            for _folder, f, why in pdf_fail:
                log(f"    · {_show(f)}    —— {why}")
        if other_fail:
            log(f"  【其它文件（{len(other_fail)} 个）】")
            for _folder, f, why in other_fail:
                log(f"    · {_show(f)}    —— {why}")
        log("  这些文件没有进入合并结果，其余文件正常合并。")
    elif not args.dry_run:
        log("\n所有文件都成功打开并合并。")
    skipped_look = [(r["label"], f.relative_to(r["folder"]))
                    for r in results for f in r["lookalikes"]]
    if skipped_look:
        log(f"\n已跳过 {len(skipped_look)} 个「与所在文件夹同名」的 PDF（按上次生成的成品处理，"
            f"没有重复合并）：")
        for label, f in skipped_look:
            log(f"  · {label} → {f.name}")
        log("  如需把它们也合并进去，运行时加上 --include-lookalikes")
    ignored = sorted({f.name for r in results for f in r["ignored"]})
    if ignored:
        log("\n以下文件类型不支持，已忽略：" + "、".join(ignored))
    return 0


if __name__ == "__main__":
    sys.exit(main())
