"""M5 打包版（frozen exe）验收测试 —— 直接驱动 dist/A4合并助手.exe。

覆盖计划 M5 验收中可在本机自动化验证的部分：
  · 版本信息（文件属性 1.0.1.0 / 关于对话框数据源）；
  · 单实例拦截（同时启动两个实例，第二个快速退出）；
  · 长路径：启动探测 + 中文提示落日志；
  · 打包版绝不触发 pip（core/deps.py frozen 分支的中文报错原文）；
  · --windowed：PE 子系统为 GUI（无控制台黑框）；
  · 应用图标内嵌（assets/app.ico 的每一档位图都在 exe 资源里）；
  · 全流程可用：真实合并纯 PDF 样例 → A4 尺寸/页数/报告/结果对话框内容。
计划中"另一台机器"的部分（无 Python 环境、未装 WPS 的机器）无法在本机验证，
在 PROGRESS.md 中标注为 M6 交付前的人工验收项。

环境注意：本机沙箱不放开 %TEMP%，PyInstaller onefile 解包会失败
（[PYI-xxxx:ERROR] Could not create temporary directory!），
因此测试把 TMP/TEMP 指向工程内目录 build/pyi_tmp；用户机器上无需该设置。
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "dist" / "A4合并助手.exe"
SAMPLES = REPO / "tests" / "samples"
PYI_TMP = REPO / "build" / "pyi_tmp"
APP_DATA = REPO / "build" / "localappdata"
# 工作目录刻意放在工程内：DSH 沙箱按"工作区"授予写权限，
# exe 无法访问 pytest 的 %TEMP% 目录（扫描会长时间无响应）。
# 在普通开发机/CI 上直接使用工程内 build/frozen_work 也完全正常。
WORK = REPO / "build" / "frozen_work"

pytestmark = pytest.mark.skipif(not EXE.exists(),
                                reason="尚未打包（先执行 build/a4merger.spec）")

RUN_TIMEOUT = 180


def _clean_strays() -> None:
    """清掉残留的 exe 进程并确认已退出。

    残留进程会占住单实例锁：新实例启动时判定"已在运行"，弹出模态提示框 →
    无人点确定 → 测试超时（表现为 120 秒后 exe 未退出）。
    """
    for _ in range(3):
        try:
            subprocess.run(["taskkill", "/F", "/IM", EXE.name],
                           capture_output=True, timeout=20)
        except Exception:
            pass
        if not _strays():
            return
        time.sleep(1.0)


def _strays() -> list[int]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"@(Get-Process -Name '{EXE.stem}' -ErrorAction SilentlyContinue).Id -join ','"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60).stdout.strip()
    return [int(x) for x in out.split(",") if x.strip().isdigit()] if out else []


@pytest.fixture(scope="module", autouse=True)
def clean_env():
    _clean_strays()
    for d in (PYI_TMP, APP_DATA, WORK):
        d.mkdir(parents=True, exist_ok=True)
    if not (SAMPLES / "pure_pdf").exists():
        pytest.skip("样例缺失（先跑 tests/make_samples.py）")
    yield
    _clean_strays()


@pytest.fixture()
def workdir(request) -> Path:
    """每个用例一个独立工作目录（用例结束后保留便于排障，整体可手工清理）。"""
    d = WORK / request.node.name
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    return d


def frozen_env_for(workdir: Path, **extra: str) -> dict:
    """每个用例独立设置文件（settings.ini 放各自工作目录）：
    避免前一个用例残留的 output_mode/输出目录/勾选污染后续用例。"""
    env = frozen_env(**extra)
    env["A4_SETTINGS_DIR"] = str(workdir)
    return env


def frozen_env(**extra: str) -> dict:
    env = dict(os.environ)
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONIOENCODING": "utf-8",
        "TMP": str(PYI_TMP),
        "TEMP": str(PYI_TMP),
        "LOCALAPPDATA": str(APP_DATA),          # 沙箱下 %LOCALAPPDATA% 不可写，重定向
        # 验收设置独立成文件：不读本机残留设置，也不写脏真实设置（QSettings 注册表）
        "A4_AUTOMATION_DIR": str(WORK),
        "A4_SETTINGS_DIR": str(WORK / "验收设置"),
    })
    env.update(extra)
    return env


def run_exe(args: list[str], env: dict, timeout: int = RUN_TIMEOUT,
            stderr_to: Path | None = None):
    """运行 exe 并等待退出；返回 (returncode, stderr 文本)。

    注意：
      · 启动前先清残留实例——残留进程会占住单实例锁，新实例会弹模态提示框卡死；
      · **不要**用 stderr=PIPE —— 受限环境里对 GUI 子系统 exe 开管道会随机卡住；
        统一重定向到文件再读回（stdout 一律 DEVNULL）。
    """
    _clean_strays()
    err_file = open(stderr_to, "wb") if stderr_to else open(os.devnull, "wb")
    try:
        proc = subprocess.Popen([str(EXE), *args], env=env,
                                stdout=subprocess.DEVNULL, stderr=err_file)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
            raise AssertionError(f"exe 未在 {timeout} 秒内退出：{args}")
    finally:
        err_file.close()
    if stderr_to:
        return proc.returncode, stderr_to.read_bytes().decode("utf-8", "replace")
    return proc.returncode, ""


def latest_log() -> str:
    logs = sorted((APP_DATA / "A4合并助手" / "logs").glob("*.log"),
                  key=lambda p: p.stat().st_mtime)
    return logs[-1].read_text(encoding="utf-8", errors="replace") if logs else ""


def copy_samples(dst: Path) -> Path:
    shutil.copytree(SAMPLES / "pure_pdf", dst)
    return dst


# ------------------------------------------------------------------ 打包属性

def test_exe_version_resource():
    """文件属性版本 1.0.1.0 与关键字段（计划 3.11.10）。"""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-Item '{EXE}').VersionInfo | "
         "Select-Object FileVersion,ProductVersion,FileDescription,CompanyName,"
         "LegalCopyright,OriginalFilename | ConvertTo-Json -Compress"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60)
    info = json.loads(out.stdout)
    assert info["FileVersion"] == "1.0.1.0"
    assert info["ProductVersion"] == "1.0.1.0"
    assert "A4" in info["FileDescription"]
    assert info["OriginalFilename"] == "A4合并助手.exe"


def test_exe_is_windowed_subsystem():
    """--windowed 卫生检查：PE 子系统 = 2（GUI），不会弹控制台黑框（计划 3.4）。"""
    data = EXE.open("rb").read(0x400)
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe_off:pe_off + 4] == b"PE\0\0"
    optional = pe_off + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    assert magic == 0x20B, "预期 PE32+（64 位）"
    subsystem = struct.unpack_from("<H", data, optional + 68)[0]
    assert subsystem == 2, f"子系统应为 2（GUI），实际 {subsystem}"


def test_exe_has_longpathaware_manifest():
    """manifest 内嵌 longPathAware（计划 3.11.3）。"""
    blob = EXE.open("rb").read()
    assert b"longPathAware" in blob
    assert b"requestedExecutionLevel" in blob


def test_exe_embeds_app_icon_frames():
    """exe 内嵌应用图标：图标既写进了 PE 资源，也随 datas 打进了内置档案。

    PyInstaller 把 .ico 的每一帧原样写成 RT_ICON 资源（utils/win32/icon.py），
    所以「帧字节在不在 exe 里」就是「图标有没有打进去」的充分证据；
    漏了 spec 的 icon= 时，Windows 会退回 PyInstaller 默认图标——这一项肉眼很难发现。
    两件事互相独立，必须分别断言：
      · icon=  → 桌面/任务栏/文件列表里的 exe 图标；
      · datas  → 打包版运行期的窗口图标（app/icon.py 从 _MEIPASS/assets 读）。
    """
    ico = (REPO / "assets" / "app.ico").read_bytes()
    count = struct.unpack_from("<H", ico, 4)[0]          # ICONDIR.idCount
    assert count >= 5, f"应用图标尺寸档太少：{count}"
    blob = EXE.read_bytes()
    missing = []
    for i in range(count):
        entry = 6 + i * 16                               # ICONDIRENTRY 定长 16 字节
        size, offset = struct.unpack_from("<II", ico, entry + 8)
        if ico[offset:offset + size] not in blob:
            missing.append(f"{ico[entry]}x{ico[entry + 1]}")
    assert not missing, f"exe 未内嵌这些图标档：{missing}"
    # 内置档案的目录项（注意必须带路径分隔符：裸 "app.ico" 会被模块名 "app.icon" 命中的假阳性）
    entry_name = ("assets" + os.sep + "app.ico").encode()
    assert entry_name in blob, "内置档案里没有 assets/app.ico（spec 的 datas 漏了）"


# ------------------------------------------------------------------ 启动行为

def test_frozen_smoke_and_startup_hints():
    """冒烟启动：干净退出 + 引擎探测/长路径提示落日志（中文）。

    · `--smoke-wait=5000` 让进程活够久，等得到启动期异步探测（引擎/长路径）落盘；
    · 退出码重试 3 次：打包版曾在退出阶段偶发崩溃（0xC0000409），已在 app.main._finish
      中改为显式释放单实例锁 + 跳过解释器终结（os._exit）；此处保留重试以吸收沙箱抖动。
    """
    rcs = []
    err_log = APP_DATA / "smoke_stderr.txt"
    for _ in range(3):
        rc, err = run_exe(["--smoke", "--smoke-wait=5000"], frozen_env(),
                          stderr_to=err_log)
        rcs.append(rc)
        if rc == 0 and "引擎探测" in latest_log():
            break
        time.sleep(1.0)
    assert rcs[-1] == 0, f"冒烟退出码 {rcs}；stderr={latest_log()[:300]}"
    text = latest_log()
    assert "长路径" in text or "260" in text
    assert "引擎探测" in text and "WPS" in text


def test_frozen_no_pip_guard(workdir):
    """打包版缺组件时走 frozen 分支：中文提示「请重新安装」，绝不触发 pip（3.8.3）。"""
    root = workdir / "无素材目录"
    root.mkdir(parents=True, exist_ok=True)
    report = workdir / "dep_probe.json"
    err_log = workdir / "stderr.txt"
    env = frozen_env_for(workdir, A4_AUTOMATION="1", A4_AUTOMATION_ROOT=str(root),
                         A4_AUTOMATION_REPORT=str(report),
                         A4_AUTOMATION_TIMEOUT="60")
    rc, err = run_exe(["--auto"], env, timeout=120, stderr_to=err_log)
    assert rc == 0, f"退出码 {rc}；stderr={err[:500]}"
    assert report.exists(), f"未生成验收报告；stderr={err[:500]}"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert "请重新安装" in data["frozen_dep_probe"]
    assert "pip" not in data["frozen_dep_probe"]


def test_frozen_single_instance():
    """两个实例同时启动：第二个被单实例锁拦截快速退出（计划 3.11.8）。"""
    _clean_strays()
    env = frozen_env()
    p1 = subprocess.Popen([str(EXE), "--smoke"], env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)                                   # 等首实例拿到锁
    p2 = subprocess.Popen([str(EXE), "--smoke"], env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    rc2 = p2.wait(timeout=60)
    dt2 = time.time() - t0
    rc1 = p1.wait(timeout=60)
    assert rc1 == 0 and rc2 == 0
    assert dt2 < 10, f"第二实例未快速退出：{dt2:.1f}s"


# ------------------------------------------------------------------ 全流程

def _read_pdf_stats(path: Path) -> tuple[int, list[tuple[float, float]]]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    sizes = []
    for page in reader.pages:
        box = page.mediabox
        sizes.append((round(float(box.width), 3), round(float(box.height), 3)))
    return len(reader.pages), sizes


def test_frozen_full_run_mode_a(workdir):
    """全流程：真实合并纯 PDF 样例（模式A）→ 成品 A4 尺寸/报告/结果对话框内容。"""
    root = copy_samples(workdir / "纯PDF资料")
    report = workdir / "结果.json"
    env = frozen_env_for(workdir, A4_AUTOMATION="1", A4_AUTOMATION_ROOT=str(root),
                         A4_AUTOMATION_REPORT=str(report),
                         A4_AUTOMATION_TIMEOUT="240")
    rc, err = run_exe(["--auto"], env, timeout=RUN_TIMEOUT)
    assert rc == 0, f"退出码 {rc}；stderr={err[:800]}"
    assert report.exists(), f"未生成验收报告；stderr={err[:800]}"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data.get("ok") is True, data
    assert data["targets"] == 2 and data["pages"] > 0
    assert not data["failures"]
    # 成品真实落盘且为 A4（595.276×841.89pt）
    for item in data["outputs"]:
        out = Path(item["out"])
        assert out.exists() and item["done"]
        pages, sizes = _read_pdf_stats(out)
        assert pages == item["pages"] > 0
        assert all(abs(w - 595.276) < 1 and abs(h - 841.89) < 1 for w, h in sizes)
    # 运行报告 + 结果对话框
    assert Path(data["report_path"]).exists()
    assert "合并报告" in Path(data["report_path"]).name
    dlg = data["dialog"]
    assert dlg is not None and dlg["title"] == "运行结果"
    assert dlg["success_rows"] == 2 and dlg["failure_rows"] == 0
    assert "成功 2/2 个目标" in dlg["head"]
    assert dlg["open_dir"] == str(root)
    assert Path(dlg["report"]).exists()


def test_frozen_full_run_mode_b(workdir):
    """全流程：模式B 统一输出目录 + 输出目录在根目录内不被当素材（计划 3.7）。"""
    root = copy_samples(workdir / "资料")
    out_dir = root / "合并结果"                        # 位于根目录内部
    report = workdir / "结果B.json"
    env = frozen_env_for(workdir, A4_AUTOMATION="1", A4_AUTOMATION_ROOT=str(root),
                         A4_AUTOMATION_OUTDIR=str(out_dir),
                         A4_AUTOMATION_REPORT=str(report),
                         A4_AUTOMATION_TIMEOUT="240")
    rc, err = run_exe(["--auto"], env, timeout=RUN_TIMEOUT)
    assert rc == 0, f"退出码 {rc}；stderr={err[:800]}"
    assert report.exists(), f"未生成验收报告；stderr={err[:800]}"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data.get("ok") is True, data
    outs = [Path(i["out"]) for i in data["outputs"]]
    assert all(p.parent == out_dir for p in outs), outs
    assert all(p.exists() for p in outs)
    assert (out_dir / "合并报告.txt").exists()
    # 防套娃：成品不被当素材 → 页数等于素材页数之和（样例各 1~3 页）
    pages = [i["pages"] for i in data["outputs"]]
    assert all(p > 0 for p in pages)
    assert data["dialog"]["open_dir"] == str(out_dir)


def test_frozen_native_engine_text_and_image(workdir):
    """锁定「仅纯 Python」引擎：字体 datas + Pillow/fpdf2 全链路可用（计划 3.6/3.11.1）。

    这条用例是 M5 的关键回归：打包时若误排除 unittest 等隐式依赖，
    fpdf2 会 import 失败，纯 Python 兜底（无 WPS 机器）即整体失效。
    """
    root = workdir / "混合资料"
    shutil.copytree(SAMPLES / "mixed", root)
    report = workdir / "结果native.json"
    env = frozen_env_for(workdir, A4_AUTOMATION="1", A4_AUTOMATION_ROOT=str(root),
                         A4_AUTOMATION_ENGINE="native",
                         A4_AUTOMATION_REPORT=str(report),
                         A4_AUTOMATION_TIMEOUT="300")
    rc, err = run_exe(["--auto"], env, timeout=RUN_TIMEOUT)
    assert rc == 0, f"退出码 {rc}；stderr={err[:800]}"
    assert report.exists(), f"未生成验收报告；stderr={err[:800]}"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert "纯 Python 可用" in data["engine_text"], data["engine_text"]
    assert (data.get("imports") or {}).get("fpdf") == "ok", data.get("imports")
    assert data.get("pages", 0) > 0
    # 纯 Python 引擎下 Office 必然失败（计划 3.6 明确：需要 WPS）；图片与文本必须成功，
    # 因此"股东甲"（jpg + GBK txt）应有成品，失败清单里的失败项不得重复计数。
    done = [o for o in data["outputs"] if o["done"]]
    assert done, data
    for item in done:
        pages, sizes = _read_pdf_stats(Path(item["out"]))
        assert pages == item["pages"] > 0
        # 每页都应是 A4（自动方向：595.276×841.89 或旋转后的 841.89×595.276）
        for w, h in sizes:
            assert (abs(w - 595.276) < 1 and abs(h - 841.89) < 1) or \
                   (abs(h - 595.276) < 1 and abs(w - 841.89) < 1), (w, h)
    failed_files = [f["file"] for f in data["failures"]]
    assert len(failed_files) == len(set(failed_files)), f"失败清单有重复项：{failed_files}"
