"""M1 验收：新 cli 与 legacy 基线的内容级一致对照（计划 4 节 M1 验收）+ 加密场景。"""
from __future__ import annotations

import shutil
from pathlib import Path

from conftest import CLI, LEGACY, PY, SAMPLES, run_cli, run_legacy
from compare_pdfs import compare_pdfs


def _assert_success(proc, what: str):
    assert proc.returncode == 0, f"{what} 失败：\n{proc.stdout}\n{proc.stderr}"


def test_cli_matches_legacy_content(pure_pdf_copy: Path, scratch: Path):
    """同输入下，新 cli 与 legacy 输出内容级一致（页数/尺寸/内容流 hash）。"""
    legacy_root = scratch / "legacy_run"
    new_root = scratch / "new_run"
    shutil.copytree(pure_pdf_copy, legacy_root)
    shutil.copytree(pure_pdf_copy, new_root)

    p_legacy = run_legacy("-r", str(legacy_root))
    _assert_success(p_legacy, "legacy")

    p_new = run_cli("-r", str(new_root), "--output-name", "{folder}.pdf", "--no-report")
    _assert_success(p_new, "cli")

    for folder in ("张三", "李四"):
        a = legacy_root / folder / f"{folder}.pdf"
        b = new_root / folder / f"{folder}.pdf"
        assert a.exists(), f"legacy 未生成 {a}"
        assert b.exists(), f"cli 未生成 {b}"
        issues = compare_pdfs(a, b, folder)
        assert not issues, f"内容级不一致：{issues}"

    # 文件集合一致：各文件夹内成品存在，且无冲突序号变体
    for folder in ("张三", "李四"):
        files_new = {p.name for p in (new_root / folder).rglob("*") if p.is_file()}
        assert f"{folder}.pdf" in files_new, f"{folder} 缺少成品"
        assert f"{folder}_2.pdf" not in files_new, f"{folder} 出现冲突变体"


def test_golden_pure_pdf(pure_pdf_copy: Path):
    """黄金样本：页数（样例=每行一页，共 13 页）与 A4 尺寸断言。"""
    from compare_pdfs import page_signature

    p = run_cli("-r", str(pure_pdf_copy), "--output-name", "{folder}.pdf", "--no-report")
    _assert_success(p, "cli")
    sig = page_signature(pure_pdf_copy / "张三" / "张三.pdf")
    assert len(sig) == 13                      # 扫描1-3(3+3+3) + 核查报告(2) + 流水(2)
    for dims, _ in sig:
        assert dims == (595.276, 841.89), f"非 A4 纵向：{dims}"


def test_output_pages_have_content(pure_pdf_copy: Path):
    """合并输出的页面确实携带内容流（非空页）。"""
    from pypdf import PdfReader

    p = run_cli("-r", str(pure_pdf_copy), "--output-name", "{folder}.pdf", "--no-report")
    _assert_success(p, "cli")
    reader = PdfReader(str(pure_pdf_copy / "张三" / "张三.pdf"))
    for pg in reader.pages:
        contents = pg.get("/Contents")
        assert contents is not None, "页面缺少 /Contents"


def test_encrypted_with_password(scratch: Path):
    """加密 PDF：有密码正常合并（encrypted 场景，密码 123456）。"""
    dst = scratch / "encrypted"
    shutil.copytree(SAMPLES / "encrypted", dst)
    p = run_cli("-r", str(dst), "--password", "123456",
                "--output-name", "{folder}.pdf", "--no-report")
    _assert_success(p, "cli")
    out = dst / "李四" / "李四.pdf"
    assert out.exists()
    from compare_pdfs import page_signature
    assert len(page_signature(out)) == 3       # 加密报告 2 页 + 普通材料 1 页


def test_encrypted_without_password(scratch: Path):
    """加密 PDF：无密码 → 文件进失败清单，其余正常合并。"""
    dst = scratch / "encrypted_no"
    shutil.copytree(SAMPLES / "encrypted", dst)
    p = run_cli("-r", str(dst), "--no-prompt", "--output-name", "{folder}.pdf", "--no-report")
    assert p.returncode == 0
    assert "加密报告.pdf" in p.stdout and "没有正确的打开密码" in p.stdout
    out = dst / "李四" / "李四.pdf"
    assert out.exists()
    from compare_pdfs import page_signature
    assert len(page_signature(out)) == 1       # 只有普通材料