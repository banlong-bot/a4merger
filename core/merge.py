"""core/merge.py —— pypdf A4 排版合并（从原脚本迁移）+ 损坏 PDF 容错（计划 3.10）。

三层防御：
  ① 文件级：单个源文件读取失败 → 失败清单 → 继续；
  ② 损坏页修复：合并前 sanitize /Annots，剔除缺 /Rect 或 /Subtype 的无效批注项
     （对象号被复用/损坏的典型表现，坏批注去掉、页面内容保留）；
  ③ 页面级：修复后仍失败的页记录"文件名+页码+原因"后跳过，绝不中止整体。
"""
from __future__ import annotations

import os
from pathlib import Path

from core.types import FileFailure

A4_WIDTH_PT = 595.276     # A4 宽 210mm（单位：点）
A4_HEIGHT_PT = 841.89     # A4 高 297mm
MM = 72.0 / 25.4          # 1 毫米等于多少点


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


def _sanitize_annots(page) -> None:
    """剥离无效批注（计划 3.10 第②层）。对象号被复用的典型表现：/Annots 指向的
    对象不是批注字典、或缺少 /Rect /Subtype。这些引用在 pypdf 合并时会触发
    KeyError('/Rect')；处理：剔除无效项，过滤后为空则删除 /Annots 键。"""
    annots = page.get("/Annots")
    if not annots:
        return
    from pypdf.generic import ArrayObject, NameObject

    keep = []
    for a in annots:
        try:
            obj = a.get_object()
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if "/Rect" not in obj or "/Subtype" not in obj:
            continue
        keep.append(a)
    try:
        if keep:
            page[NameObject("/Annots")] = ArrayObject(keep)
        else:
            del page[NameObject("/Annots")]
    except Exception:
        pass


def merge_to_a4(source_pdfs: list[Path], out_pdf: Path, margin_mm: float,
                orientation: str, title: str = "",
                passwords: list[str] | None = None,
                passwords_by_file: dict[str, str] | None = None,
                failures: list[FileFailure] | None = None,
                on_page=None) -> tuple[int, list[str], dict[str, tuple[int, int]]]:
    """把若干 PDF 逐页等比缩放、居中排到 A4 页面上并合并。

    返回 (总页数, 警告列表, {源文件路径: (起始页, 页数)})。
    单个文件/单页失败不中止整体（计划 3.10）。
    """
    from pypdf import PdfReader, PdfWriter, Transformation

    passwords = [""] + list(passwords or [])
    passwords_by_file = passwords_by_file or {}
    writer = PdfWriter()
    warnings: list[str] = []
    total = 0
    page_map: dict[str, tuple[int, int]] = {}

    # 预统计总页数（供进度回调的 n/N）
    for src in source_pdfs:
        try:
            reader = PdfReader(str(src))
            if reader.is_encrypted:
                for pwd in passwords:
                    try:
                        if reader.decrypt(pwd):
                            break
                    except Exception:
                        continue
        except Exception:
            continue

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
                failures.append(FileFailure(src, f"无法读取：{exc}"))
            continue

        start = total
        for page_no, page in enumerate(pages, 1):
            try:
                try:
                    page.transfer_rotation_to_content()   # 把 /Rotate 并入内容，避免页面错位
                except Exception:
                    pass
                _sanitize_annots(page)                    # 3.10 第②层：损坏页修复
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
                if on_page is not None:
                    on_page(total)
            except Exception as exc:                      # 3.10 第③层：页面级隔离
                msg = f"{src.name}：第 {page_no} 页无法合并（{exc}），已跳过该页"
                warnings.append(msg)
                if failures is not None:
                    failures.append(FileFailure(src, f"第 {page_no} 页无法合并：{exc}",
                                                skipped_pages=1))
        page_map[str(src)] = (start, total - start)

    if title:
        writer.add_metadata({"/Title": title})
    out_final = out_pdf
    tmp_adj = Path(str(out_pdf) + ".tmp")
    with open(tmp_adj, "wb") as fh:
        writer.write(fh)
    os.replace(tmp_adj, out_final)
    return total, warnings, page_map