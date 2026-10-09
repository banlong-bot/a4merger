"""输出双模式（3.7）：统一目录、冲突序号、防套娃、报告防误扫、--only、模板校验。"""
from __future__ import annotations

import shutil
from pathlib import Path

from conftest import SAMPLES, run_cli
from compare_pdfs import page_signature


def test_mode_b_unified_output(scratch: Path):
    """模式B：所有成品集中在指定输出目录，自动创建。"""
    root = scratch / "pure"
    shutil.copytree(SAMPLES / "pure_pdf", root)
    out = scratch / "合并结果"
    p = run_cli("-r", str(root), "--output-dir", str(out))
    assert p.returncode == 0, p.stdout + p.stderr
    assert (out / "【合并】张三.pdf").exists()
    assert (out / "【合并】李四.pdf").exists()
    assert not (root / "张三" / "【合并】张三.pdf").exists()   # 不在原地生成


def test_mode_b_duplicate_names(scratch: Path):
    """模式B：两个同名子文件夹（level2）自动加序号（张三.pdf / 张三_2.pdf）。"""
    root = scratch / "dup"
    shutil.copytree(SAMPLES / "duplicate", root)
    out = scratch / "out"
    p = run_cli("-r", str(root), "--level", "2", "--output-dir", str(out))
    assert p.returncode == 0, p.stdout + p.stderr
    assert (out / "【合并】张三.pdf").exists()
    assert (out / "【合并】张三_2.pdf").exists()


def test_mode_b_no_rescan(scratch: Path):
    """模式B：输出目录位于根目录内 → 不被当素材、不被当目标文件夹（防套娃）。"""
    root = scratch / "parent"
    (root / "客户" / "1.证件").mkdir(parents=True)
    shutil.copy(SAMPLES / "pure_pdf" / "张三" / "1.身份证" / "扫描1.pdf",
                root / "客户" / "1.证件" / "证件.pdf")
    out = root / "合并结果"
    p1 = run_cli("-r", str(root), "--output-dir", str(out))
    assert p1.returncode == 0, p1.stdout + p1.stderr
    n1 = len(page_signature(out / "【合并】客户.pdf"))
    # 第二次运行：输出目录若被扫描，成品会被当素材 → 页数翻倍
    p2 = run_cli("-r", str(root), "--output-dir", str(out))
    assert p2.returncode == 0, p2.stdout + p2.stderr
    n2 = len(page_signature(out / "【合并】客户.pdf"))
    assert n1 == n2 == 3, f"套娃发生：{n1} → {n2}"   # 样例=每行一页共 3 页；两轮一致=未套娃


def test_report_not_rescanned(scratch: Path):
    """合并报告.txt 不被当作素材：根目录有散文件时重复运行页数不变。"""
    root = scratch / "report_test"
    (root / "张三" / "1.证件").mkdir(parents=True)
    shutil.copy(SAMPLES / "pure_pdf" / "张三" / "1.身份证" / "扫描1.pdf",
                root / "张三" / "1.证件" / "证件.pdf")
    (root / "根层说明.txt").write_text("根目录散文件\n", encoding="gbk")
    p1 = run_cli("-r", str(root), "--engine", "native", "--output-name", "{folder}.pdf")
    assert p1.returncode == 0, p1.stdout + p1.stderr
    report = root / "合并报告.txt"
    assert report.exists()                     # 模式A：报告在根目录
    n1 = len(page_signature(root / "张三" / "张三.pdf"))
    p2 = run_cli("-r", str(root), "--engine", "native", "--output-name", "{folder}.pdf")
    assert p2.returncode == 0, p2.stdout + p2.stderr
    n2 = len(page_signature(root / "张三" / "张三.pdf"))
    assert n1 == n2, "合并报告被误当素材（txt 根层目标被扩大）"


def test_lookalike_skipped_and_overwritten(scratch: Path):
    """默认模板下：旧成品【合并】xxx.pdf 被跳过不重复合并、最后被覆盖更新。"""
    root = scratch / "misc"
    shutil.copytree(SAMPLES / "misc", root)
    p = run_cli("-r", str(root))
    assert p.returncode == 0, p.stdout + p.stderr
    zhao = root / "赵六" / "【合并】赵六.pdf"
    assert zhao.exists()
    assert len(page_signature(zhao)) == 1, "旧成品被重复合并了（本应为 1 页素材）"
    assert "视为上次的合并结果" in p.stdout          # replaced_output 提示


def test_subfolder_lookalike_skipped(scratch: Path):
    """子文件夹里的同名 PDF（lookalike 分支）：视为上次成品跳过，不参与合并。"""
    root = scratch / "look"
    sub = root / "李明" / "2.出资核查"
    sub.mkdir(parents=True)
    src = SAMPLES / "pure_pdf" / "张三" / "1.身份证" / "扫描1.pdf"
    shutil.copy(src, sub / "材料.pdf")
    shutil.copy(src, sub / "2.出资核查.pdf")          # 与子文件夹同名 → 应跳过
    p = run_cli("-r", str(root), "--output-name", "{folder}.pdf", "--no-report")
    assert p.returncode == 0, p.stdout + p.stderr
    out = root / "李明" / "李明.pdf"
    assert out.exists()
    assert len(page_signature(out)) == 3, "同名 PDF 未被跳过（3 页素材被并进）"
    assert "视为上次生成的成品" in p.stdout or "已跳过" in p.stdout


def test_only_relative_path(scratch: Path):
    """--only：相对路径精确匹配；名称简写歧义时报错（level2 下候选为二级文件夹）。"""
    root = scratch / "dup"
    shutil.copytree(SAMPLES / "duplicate", root)
    p = run_cli("-r", str(root), "--level", "2", "--only", "客户A/张三",
                "--output-name", "{folder}.pdf", "--no-report")
    assert p.returncode == 0, p.stdout + p.stderr
    p2 = run_cli("-r", str(root), "--level", "2", "--only", "张三",
                 "--output-name", "{folder}.pdf", "--no-report")
    assert p2.returncode != 0                  # 简写匹配两个 → 报错
    assert "匹配了多个目标" in p2.stdout


def test_template_validation(scratch: Path):
    """模板校验：非法字符拦截（cli 退出码 2）。"""
    root = scratch / "pure"
    shutil.copytree(SAMPLES / "pure_pdf", root)
    p = run_cli("-r", str(root), "--output-name", "A:B.pdf")
    assert p.returncode == 2
    assert "非法字符" in p.stdout


def test_dry_run_no_output(scratch: Path):
    """dry-run：只预览不生成。"""
    root = scratch / "pure"
    shutil.copytree(SAMPLES / "pure_pdf", root)
    p = run_cli("-r", str(root), "--dry-run")
    assert p.returncode == 0
    assert "预览完成" in p.stdout
    assert not (root / "张三" / "【合并】张三.pdf").exists()