"""core/converters/backend_wps.py —— WPS COM 后端（原脚本 WPS_WORKER_PS 原样迁移）。

- 通过 PowerShell + COM 调用 WPS 文字/表格/演示导出 PDF（不依赖 pywin32）；
- run_wps_worker 支持取消：Popen 轮询，取消时立即 terminate 子进程（计划 3.11.4）；
- 结果通过 JSON 文件回传，失败条目如实返回（由调用方决定重试/兜底）。
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from core.converters.base import ConvertResult, ConvertTask, Converter
from core.util import decode_bytes, find_powershell, log

WPS_WORD_PROGID = "KWPS.Application"
WPS_EXCEL_PROGID = "KET.Application"
WPS_PPT_PROGID = "KWPP.Application"

py_name = Path(__file__).name
_WORKER_VAR = WPS_WORKER_PS = r'''
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


def run_wps_worker(jobs: list[dict], tmp_dir: Path, timeout: int,
                   cancel=None) -> list[dict]:
    """把一批转换任务交给 WPS 处理，返回每个任务的 {src,out,ok,error}。

    支持取消：Popen 轮询，cancel() 返回 True 时立即 terminate（计划 3.11.4）。
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
    ps_file.write_text(WPS_WORKER_PS, encoding="utf-8-sig")   # BOM：PS 5.1 按 UTF-8 读取
    if result_file.exists():
        result_file.unlink()

    cmd = [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-File", str(ps_file), str(job_file), str(result_file)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return [{"src": j["src"], "out": j["out"], "ok": False,
                 "error": f"无法启动 PowerShell：{exc}"} for j in jobs]

    deadline = time.time() + timeout
    try:
        while True:
            if cancel is not None and cancel():
                _terminate(proc)
                return [{"src": j["src"], "out": j["out"], "ok": False,
                         "error": "任务已取消"} for j in jobs]
            if proc.poll() is not None:
                break
            if time.time() > deadline:
                _terminate(proc)
                return [{"src": j["src"], "out": j["out"], "ok": False,
                         "error": f"WPS 转换超时（超过 {timeout} 秒，多半是文件需要密码或已损坏）"}
                        for j in jobs]
            time.sleep(0.2)
        stdout, stderr = proc.communicate()
    except Exception as exc:            # 异常兜底：进程若存活则终止
        _terminate(proc)
        return [{"src": j["src"], "out": j["out"], "ok": False,
                 "error": f"WPS 调用异常：{exc}"} for j in jobs]

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

    detail = decode_bytes(stdout or b"").strip() or decode_bytes(stderr or b"").strip()
    detail = detail.splitlines()[-1] if detail else f"PowerShell 退出码 {proc.returncode}"
    return [{"src": j["src"], "out": j["out"], "ok": False,
             "error": f"WPS 调用失败：{detail}"} for j in jobs]


def _terminate(proc: subprocess.Popen) -> None:
    """终止子进程（terminate 后给 5 秒，仍不退则 kill）。"""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass


class WpsConverter(Converter):
    """WPS COM 后端。"""

    name = "wps"

    def available(self) -> bool:
        return find_powershell() is not None

    def convert(self, task: ConvertTask, cancel, timeout: int) -> ConvertResult:
        job = {"kind": task.kind, "src": str(task.src.resolve()),
               "out": str(task.out), "fit": task.fit}
        if task.kind in ("word", "excel"):
            job["passwords"] = [""] + list(task.passwords or [])
        items = run_wps_worker([job], task.out.parent, timeout, cancel)
        item = items[0] if items else {}
        if item.get("ok") and task.out.exists() and task.out.stat().st_size > 0:
            return ConvertResult(True)
        return ConvertResult(False, item.get("error") or "WPS 未生成输出文件")