#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tests/make_samples.py —— 生成 M1 回归对照用的样例数据（幂等：重复运行先清空重建）。

覆盖场景（对应计划第 5 节测试矩阵）：
  pure_pdf/      纯 PDF 多子文件夹
  mixed/         混合 Word/Excel/PPT/图片/txt（GBK 编码）
  encrypted/     加密 PDF（密码 123456）+ 普通 PDF
  corrupted/     损坏 annots PDF（/Annots 指向 /Type /XRef 对象）+ 正常文件混排
  duplicate/     两个父目录下同名子文件夹（模式B 冲突消解）
  misc/          空文件夹、纯不支持类型、同名成品 PDF（【合并】张三.pdf）、根层散文件
  images/        EXIF 旋转照片（orientation=6）

用法：<venv>python tests/make_samples.py
依赖：pypdf / Pillow / fpdf2 / python-docx / openpyxl / python-pptx
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent / "samples"
FONT = Path(__file__).resolve().parent.parent / "fonts" / "NotoSansCJKsc-Regular.otf"

PASSWORD = "123456"


def reset() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)


def w(rel: str) -> Path:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------- PDF

def make_pdf(path: Path, lines: list[str]) -> None:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    if FONT.exists():
        pdf.add_font("CJK", "", str(FONT))
        pdf.set_font("CJK", size=12)
    else:
        pdf.set_font("Helvetica", size=12)
    for ln in lines:
        pdf.add_page()
        pdf.multi_cell(0, 8, ln)
    pdf.output(str(path))


def make_encrypted_pdf(path: Path, src: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(PASSWORD, algorithm="AES-256")
    with open(path, "wb") as fh:
        writer.write(fh)


def make_bad_annots_pdf(path: Path) -> None:
    """构造「损坏批注」PDF：第 1 页 /Annots 指向对象 47，而 47 是 XRef 流字典
    （/Type /XRef，无 /Rect /Subtype）——复现 pypdf 合并时 a['/Rect'] KeyError 的场景。
    对象偏移手工计算，xref 表合法，pypdf 可正常打开。"""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.276 841.89]"
           b" /Contents 4 0 R /Annots [47 0 R] >>",
        47: b"<< /Type /XRef /W [1 2 2] /Index [0 1] >>",
    }
    stream = b"BT /F1 24 Tf 72 720 Td (corrupted annots sample) Tj ET"
    objs[4] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref_pos = len(out)
    # 子段式 xref：0-0 空闲、1-4 有效对象、47-47 有效对象（避免为不存在的对象写条目）
    out += b"xref\n0 1\n0000000000 65535 f \n"
    for start, end in ((1, 5), (47, 48)):
        out += b"%d %d\n" % (start, end - start)
        for n in range(start, end):
            out += b"%010d 00000 n \n" % offsets.get(n, 0)
    out += b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % xref_pos
    path.write_bytes(bytes(out))


# ---------------------------------------------------------------- 图片

def make_image(path: Path, text: str, size=(720, 480), exif_orientation: int | None = None) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, (235, 235, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, size[0] - 8, size[1] - 8], outline=(60, 60, 60), width=3)
    d.text((40, size[1] // 2 - 12), text, fill=(30, 30, 30))
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[274] = exif_orientation            # 274 = Orientation
        img.save(str(path), exif=exif)
    else:
        img.save(str(path))


# ---------------------------------------------------------------- 文本

def make_txt(path: Path, text: str, encoding: str) -> None:
    path.write_text(text, encoding=encoding)


# ---------------------------------------------------------------- Office

def make_docx(path: Path) -> None:
    from docx import Document

    doc = Document()
    doc.add_heading("出资核查说明（样例）", level=1)
    doc.add_paragraph("本文件由 make_samples.py 自动生成，用于回归对照测试。")
    doc.add_paragraph("包含中文段落、列表与表格，用于验证 WPS 转换与 A4 排版。")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "项目"
    table.cell(0, 1).text = "金额"
    table.cell(1, 0).text = "出资款"
    table.cell(1, 1).text = "1000000 元"
    doc.save(str(path))


def make_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "出资明细"
    ws.append(["序号", "股东", "出资额", "日期"])
    ws.append([1, "张三", 500000, "2024-01-01"])
    ws.append([2, "李四", 500000, "2024-01-02"])
    wb.save(str(path))


def make_pptx(path: Path) -> None:
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "核查材料（样例）"
    slide.placeholders[1].text = "汇报 PPT 样例，验证 WPS 演示转换。"
    prs.save(str(path))


# ---------------------------------------------------------------- 组织样例

def build_pure_pdf() -> None:
    for i in range(1, 4):
        make_pdf(w(f"pure_pdf/张三/1.身份证/扫描{i}.pdf"),
                 [f"身份证扫描件 第 {i} 页（样例）", "", "图形与文字均来自 fpdf2 中文渲染。"])
    make_pdf(w("pure_pdf/张三/2.出资核查/核查报告.pdf"), ["出资核查报告（样例）", "结论：出资到位。"])
    make_pdf(w("pure_pdf/张三/3.银行流水/流水.pdf"), ["银行流水（样例）", "交易明细若干页。"])
    make_pdf(w("pure_pdf/李四/1.证件/护照.pdf"), ["护照页（样例）", "李四的护照扫描。"])
    make_pdf(w("pure_pdf/李四/2.出资核查/报告.pdf"), ["李四核查报告（样例）"])


def build_mixed() -> None:
    make_image(w("mixed/股东甲/1.身份证/身份证正面.jpg"), "身份证正面（样例）", exif_orientation=6)
    make_image(w("mixed/股东甲/1.身份证/身份证反面.jpg"), "身份证反面（样例）")
    make_docx(w("mixed/股东甲/2.出资核查/核查报告.docx"))
    make_xlsx(w("mixed/股东甲/2.出资核查/出资证明.xlsx"))
    make_txt(w("mixed/股东甲/3.补充材料/说明.txt"),
             "补充说明（GBK 编码样例）\n本文件用于验证 txt 编码探测。\n第二行：中文内容。",
             encoding="gbk")
    make_pdf(w("mixed/股东甲/3.补充材料/流水.pdf"), ["流水补充页（样例）"])
    make_pptx(w("mixed/股东乙/1.证件/汇报材料.pptx"))
    make_pdf(w("mixed/股东乙/2.核查/报告.pdf"), ["股东乙核查报告（样例）"])
    make_txt(w("mixed/根层散文件/根层说明.md"), "# 根层说明\n直接放在目标文件夹根层的文件。", encoding="utf-8")


def build_encrypted() -> None:
    plain = w("encrypted/.tmp_plain.pdf")
    make_pdf(plain, ["加密样例 PDF", "打开密码：123456。"])
    make_encrypted_pdf(w("encrypted/李四/1.证件/加密报告.pdf"), plain)
    plain.unlink()
    make_pdf(w("encrypted/李四/2.资料/普通材料.pdf"), ["普通材料（无密码）（样例）"])


def build_corrupted() -> None:
    make_bad_annots_pdf(w("corrupted/王五/1.证件/坏批注.pdf"))
    for i in range(1, 6):
        make_pdf(w(f"corrupted/王五/1.证件/正常{i}.pdf"), [f"正常文件 {i}（样例）"])
    make_pdf(w("corrupted/王五/2.资料/附件.pdf"), ["附件（样例）"])


def build_duplicate() -> None:
    make_pdf(w("duplicate/客户A/张三/1.证件/身份证.pdf"), ["客户A 张三 证件（样例）"])
    make_pdf(w("duplicate/客户B/张三/1.证件/身份证.pdf"), ["客户B 张三 证件（样例）"])


def build_misc() -> None:
    make_pdf(w("misc/赵六/1.资料/资料.pdf"), ["赵六资料（样例）"])
    # 上次运行的成品（lookalike：与模板输出同名）
    make_pdf(w("misc/赵六/【合并】赵六.pdf"), ["旧成品（应被跳过，不参与合并）（样例）"])
    # 空文件夹
    w("misc/空文件夹").mkdir(parents=True, exist_ok=True)
    # 只有不支持类型的文件夹
    w("misc/仅含不支持类型/notes.xyz").write_text("not supported", encoding="ascii")
    # 以前的旧命名成品（模板变更场景：无标记 张三.pdf）
    make_pdf(w("misc/孙七/张三.pdf"), ["旧命名成品（模板变更后应作为素材）（样例）"])
    make_pdf(w("misc/孙七/1.证件/证件.pdf"), ["孙七证件（样例）"])


def main() -> None:
    reset()
    build_pure_pdf()
    build_mixed()
    build_encrypted()
    build_corrupted()
    build_duplicate()
    build_misc()
    count = sum(1 for p in ROOT.rglob("*") if p.is_file())
    print(f"样例生成完成：{count} 个文件，根目录 {ROOT}")
    print("注意：encrypted 场景密码为", PASSWORD)


if __name__ == "__main__":
    main()