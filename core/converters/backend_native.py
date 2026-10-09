"""core/converters/backend_native.py —— 纯 Python 兜底后端（图片 Pillow / 文本 fpdf2）。

图片路径保留原脚本 Pillow 兜底（含 ImageOps.exif_transpose，计划 3.11.2）；
文本路径：编码探测（UTF-8-sig → UTF-8 → GBK → GB18030，计划 3.11.1）+ fpdf2 渲染
（内嵌 OFL 开源中文字体）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from core.converters.base import ConvertResult, ConvertTask, Converter


def font_path() -> Path | None:
    """中文字体查找：打包后 sys._MEIPASS/fonts，开发时工程 fonts/。"""
    candidates = []
    if getattr(sys, "_MEIPASS", None):
        candidates.append(Path(sys._MEIPASS) / "fonts")
    here = Path(__file__).resolve().parent.parent.parent   # a4merger/
    candidates.append(here / "fonts")
    for d in candidates:
        for f in ("NotoSansCJKsc-Regular.otf", "NotoSansSC-Regular.otf"):
            p = d / f
            if p.exists():
                return p
    return None


def decode_text(raw: bytes) -> tuple[str, str]:
    """按编码优先级尝试解码，返回 (文本, 实际编码)。"""
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


class NativeConverter(Converter):
    """纯 Python 后端：image 用 Pillow，text 用 fpdf2。"""

    name = "native"

    def __init__(self) -> None:
        self.last_encoding: str = "?"

    def available(self) -> bool:
        try:
            import PIL  # noqa: F401
            import fpdf  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, task: ConvertTask, cancel, timeout: int) -> ConvertResult:
        try:
            if task.kind == "image":
                return self._image(task)
            if task.kind == "text":
                return self._text(task)
            return ConvertResult(False, f"native 后端不支持 {task.kind}")
        except Exception as exc:
            return ConvertResult(False, str(exc))

    # ------------------------------------------------------------ 图片

    def _image(self, task: ConvertTask) -> ConvertResult:
        import PIL.Image
        import PIL.ImageOps

        src, out = task.src, task.out
        with PIL.Image.open(src) as im:
            frames = getattr(im, "n_frames", 1)
            if frames > 1:
                pages = []
                for i in range(frames):
                    im.seek(i)
                    pages.append(PIL.ImageOps.exif_transpose(im.copy()).convert("RGB"))
                pages[0].save(out, "PDF", save_all=True, append_images=pages[1:],
                              resolution=150)
            else:
                page = PIL.ImageOps.exif_transpose(im.copy())
                if page.mode not in ("RGB", "L"):
                    page = page.convert("RGB")
                page.save(out, "PDF", resolution=150)
        return ConvertResult(True) if out.exists() and out.stat().st_size > 0 \
            else ConvertResult(False, "未生成输出文件")

    # ------------------------------------------------------------ 文本

    def _text(self, task: ConvertTask) -> ConvertResult:
        from fpdf import FPDF

        raw = task.src.read_bytes()
        text, self.last_encoding = decode_text(raw)
        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(15, 15, 15)
        f = font_path()
        if f is not None:
            pdf.add_font("CJK", "", str(f))
            pdf.set_font("CJK", size=11)
        else:
            pdf.set_font("Helvetica", size=11)
        pdf.add_page()
        for line in text.replace("\r\n", "\n").split("\n"):
            pdf.multi_cell(0, 6, line if line.strip() else " ")
        pdf.output(str(task.out))
        if not (task.out.exists() and task.out.stat().st_size > 0):
            return ConvertResult(False, "未生成输出文件")
        return ConvertResult(True)