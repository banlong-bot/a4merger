"""单元测试：GBK 解码、字体、模板校验、输出计划、自然排序、only 过滤。"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.collect import (is_skippable_excel, partition_skipped_excel,
                          plan_outputs)
from core.converters.backend_native import decode_text, font_path
from core.types import MergeConfig
from core.util import natural_key


def test_decode_text_gbk():
    raw = "补充说明（GBK 编码样例）".encode("gbk")
    text, enc = decode_text(raw)
    assert text == "补充说明（GBK 编码样例）"
    assert enc == "gbk"


def test_decode_text_utf8_bom():
    raw = b"\xef\xbb\xbf" + "中文内容".encode("utf-8")
    text, enc = decode_text(raw)
    assert text == "中文内容"
    assert enc == "utf-8-sig"


def test_decode_text_garbage():
    raw = bytes([0xff, 0xfe, 0x00, 0x81, 0x93])
    text, enc = decode_text(raw)          # 全部失败 → replace
    assert enc == "utf-8(replace)"


def test_font_available():
    f = font_path()
    assert f is not None and f.exists(), "中文字体缺失（3.11.1）"


def test_natural_key():
    names = ["10.png", "2.png", "1.png", "A2", "a1"]
    ordered = sorted(names, key=natural_key)
    assert ordered == ["1.png", "2.png", "10.png", "a1", "A2"]


def test_plan_outputs_duplicate():
    root = Path("D:/x")
    targets = [root / "客户A" / "张三", root / "客户B" / "张三", root / "李四"]
    plan = plan_outputs(targets, "【合并】{folder}.pdf", Path("D:/out"))
    assert plan[targets[0]] == Path("D:/out/【合并】张三.pdf")
    assert plan[targets[1]] == Path("D:/out/【合并】张三_2.pdf")
    assert plan[targets[2]] == Path("D:/out/【合并】李四.pdf")


def test_validate_bad_template():
    cfg = MergeConfig(root=Path("."), output_name="A:B.pdf")
    errs = cfg.validate()
    assert any("非法字符" in e for e in errs)


def test_validate_unknown_placeholder():
    cfg = MergeConfig(root=Path("."), output_name="{xxx}.pdf")
    errs = cfg.validate()
    assert any("未知占位符" in e for e in errs)


def test_validate_ok_default():
    cfg = MergeConfig(root=Path("."))
    assert cfg.validate() == []


def test_skip_excel_scope():
    """「遇到 Excel 跳过」只针对 .xls/.xlsx（大小写不敏感），其余 Excel 家族不在此列。"""
    assert is_skippable_excel(Path("a.xls"))
    assert is_skippable_excel(Path("a.XLSX"))
    assert not is_skippable_excel(Path("a.xlsm"))
    assert not is_skippable_excel(Path("a.csv"))
    assert not is_skippable_excel(Path("a.et"))
    assert not is_skippable_excel(Path("a.pdf"))


def test_partition_skipped_excel_keeps_order():
    """分组保序：可合并文件与 Excel 各自维持原顺序。"""
    files = [Path("1.pdf"), Path("2.xlsx"), Path("3.jpg"),
             Path("4.xls"), Path("5.pdf")]
    kept, skipped = partition_skipped_excel(files)
    assert [p.name for p in kept] == ["1.pdf", "3.jpg", "5.pdf"]
    assert [p.name for p in skipped] == ["2.xlsx", "4.xls"]


def test_skip_excel_default_off():
    """默认不跳过（MergeConfig 默认值），保证与基线行为一致。"""
    assert MergeConfig(root=Path(".")).skip_excel is False