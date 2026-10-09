"""3.10 损坏 PDF 容错：坏批注修复、文件级/页面级隔离、不连坐。"""
from __future__ import annotations

import shutil
from pathlib import Path

from conftest import SAMPLES, run_cli
from compare_pdfs import page_signature


def _run(root: Path, name: str = "王五"):
    return run_cli("-r", str(root), "--output-name", "{folder}.pdf", "--no-report")


def test_corrupted_annots_fixed(scratch: Path):
    """坏批注 PDF 被 sanitize 修复：6 个文件 7 页全部合并，无失败项。"""
    root = scratch / "corrupted"
    shutil.copytree(SAMPLES / "corrupted", root)
    p = _run(root)
    assert p.returncode == 0, p.stdout + p.stderr
    out = root / "王五" / "王五.pdf"
    assert out.exists()
    assert len(page_signature(out)) == 7       # 坏批注(修复) + 正常1-5 + 附件
    assert "所有文件都成功打开并合并" in p.stdout   # 失败清单为空


def test_43_files_no_collateral(scratch: Path):
    """43 文件连坐场景：1 个损坏 + 42 个正常 → 全部合并成功（sanitize 修复）。"""
    root = scratch / "many"
    (root / "王五" / "1.证件").mkdir(parents=True)
    shutil.copy(SAMPLES / "corrupted" / "王五" / "1.证件" / "坏批注.pdf",
                root / "王五" / "1.证件" / "坏批注.pdf")
    for i in range(42):
        shutil.copy(SAMPLES / "corrupted" / "王五" / "1.证件" / "正常1.pdf",
                    root / "王五" / "1.证件" / f"正常{i}.pdf")
    p = _run(root)
    assert p.returncode == 0, p.stdout + p.stderr
    out = root / "王五" / "王五.pdf"
    assert len(page_signature(out)) == 43
    assert "所有文件都成功打开并合并" in p.stdout   # 失败清单为空


def test_unreadable_file_isolated(scratch: Path):
    """读取失败的损坏文件：进失败清单，其余 42 个文件正常合并（文件级隔离）。"""
    root = scratch / "broken"
    (root / "王五" / "1.证件").mkdir(parents=True)
    # 截断一半的正常 PDF → 无法读取
    good = SAMPLES / "corrupted" / "王五" / "1.证件" / "正常1.pdf"
    bad = root / "王五" / "1.证件" / "截断损坏.pdf"
    data = good.read_bytes()
    bad.write_bytes(data[: len(data) // 2])
    for i in range(42):
        shutil.copy(good, root / "王五" / "1.证件" / f"正常{i}.pdf")
    p = _run(root)
    assert p.returncode == 0, p.stdout + p.stderr
    out = root / "王五" / "王五.pdf"
    assert len(page_signature(out)) == 42      # 42 个正常页
    assert "截断损坏.pdf" in p.stdout          # 失败清单点名
    assert "其余文件正常合并" in p.stdout