"""tests/compare_pdfs.py —— 内容级一致性比对工具（计划 M1 验收）。

对比两个 PDF：页数、每页尺寸（cropbox）、每页内容流 md5。
只要排版变换与页面内容一致，签名即一致（不要求逐字节相同）。
"""
from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

from pypdf import PdfReader


def page_signature(path: Path | str) -> list[tuple[tuple[float, float], str]]:
    """返回每页 (尺寸, 内容流 md5) 列表。"""
    reader = PdfReader(str(path))
    sig: list[tuple[tuple[float, float], str]] = []
    for pg in reader.pages:
        box = pg.cropbox if float(pg.cropbox.width) > 0 else pg.mediabox
        dims = (round(float(box.width), 3), round(float(box.height), 3))
        data = b""
        contents = pg.get("/Contents")
        if contents is not None:
            items = contents if isinstance(contents, list) else [contents]
            for it in items:
                try:
                    raw = it.get_object().get_data()
                    try:
                        raw = zlib.decompress(raw)
                    except Exception:
                        pass
                    data += raw
                except Exception:
                    pass
        sig.append((dims, hashlib.md5(data).hexdigest()))
    return sig


def compare_pdfs(a: Path | str, b: Path | str,
                 label: str = "") -> list[str]:
    """比较两个 PDF，返回不一致说明列表（空 = 内容级一致）。"""
    sa, sb = page_signature(a), page_signature(b)
    issues: list[str] = []
    if len(sa) != len(sb):
        issues.append(f"{label or 'PDF'}: 页数不一致 {len(sa)} vs {len(sb)}")
    for i, (pa, pb) in enumerate(zip(sa, sb), 1):
        if pa != pb:
            issues.append(f"{label or 'PDF'} 第 {i} 页不一致: "
                          f"尺寸/内容 {pa} vs {pb}")
    return issues