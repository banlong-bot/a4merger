"""WPS 全链路集成测试（docx/xlsx/pptx/jpg/GBK txt 真实转换）。

本机无 WPS 时自动跳过（部署前提：目标同事均装 WPS）。
"""
from __future__ import annotations

import shutil

import pytest

from conftest import SAMPLES, run_cli
from compare_pdfs import page_signature

try:
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    from core.converters.manager import detect
    WPS_OK = detect().get("wps", False)
finally:
    pass


pytestmark = pytest.mark.skipif(not WPS_OK, reason="本机未安装/无法调用 WPS")


def test_mixed_full_chain(scratch):
    """mixed 场景：jpg(EXIF) + xlsx + docx + pdf + GBK txt + pptx + md 全链路。"""
    root = scratch / "mixed"
    shutil.copytree(SAMPLES / "mixed", root)
    out = scratch / "out"
    p = run_cli("-r", str(root), "--output-dir", str(out))
    assert p.returncode == 0, p.stdout + p.stderr
    assert (out / "【合并】股东甲.pdf").exists()
    assert (out / "【合并】股东乙.pdf").exists()
    assert (out / "【合并】根层散文件.pdf").exists()
    # 股东甲：2 图片页 + xlsx 1 + docx 2 + 流水 pdf 2 + GBK txt 1 = 8 页上下浮动，
    # 只要成功生成且 >0 页即可（WPS 分页由版本决定，不断言精确值）
    assert len(page_signature(out / "【合并】股东甲.pdf")) > 0
    assert "所有文件都成功打开并合并" in p.stdout


def test_mixed_engine_native_fallback(scratch):
    """--engine native 时：Office 文件明确报"需要 WPS"，图片/文本/PDF 仍正常。"""
    root = scratch / "mixed"
    shutil.copytree(SAMPLES / "mixed", root)
    p = run_cli("-r", str(root), "--engine", "native",
                "--output-name", "{folder}.pdf", "--no-report")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "需要 WPS" in p.stdout           # 股东甲的 docx/xlsx、股东乙的 pptx 被跳过提示
    # 剩图片/PDF/文本的股东乙：报告.pdf（pdf）
    out = root / "股东乙" / "股东乙.pdf"
    assert out.exists()