"""core/collect.py —— 文件收集、自然排序、成品识别、输出计划（从原脚本迁移 + 双模式）。"""
from __future__ import annotations

from pathlib import Path

from core.util import natural_key

IMAGE_EXTS = {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".gif",
              ".tif", ".tiff", ".webp", ".heic"}
PDF_EXTS = {".pdf"}
WORD_EXTS = {".doc", ".docx", ".docm", ".rtf", ".wps"}
EXCEL_EXTS = {".xls", ".xlsx", ".xlsm", ".csv", ".et"}
PPT_EXTS = {".ppt", ".pptx", ".pptm", ".dps"}
TEXT_EXTS = {".txt", ".log", ".md"}

SUPPORTED_EXTS = IMAGE_EXTS | PDF_EXTS | WORD_EXTS | EXCEL_EXTS | PPT_EXTS | TEXT_EXTS

REPORT_PREFIX = "合并报告"     # 报告文件前缀：收集阶段一律排除（防误扫）


def wps_kind(ext: str) -> str | None:
    """把扩展名映射成转换处理方式（word/text/image/excel/ppt）。"""
    if ext in IMAGE_EXTS:
        return "image"
    if ext in WORD_EXTS or ext in TEXT_EXTS:
        return "word" if ext in WORD_EXTS else "text"
    if ext in EXCEL_EXTS:
        return "excel"
    if ext in PPT_EXTS:
        return "ppt"
    return None


def output_name_of(folder: Path, template: str) -> str:
    """按输出文件名模板算出某个文件夹的成品文件名。"""
    return template.format(folder=folder.name, name=folder.name)


def collect_files(folder: Path, skip_dirs: set[Path], skip_files: set[Path],
                  template: str, skip_lookalikes: bool = True,
                  ) -> tuple[list[Path], list[Path], list[Path]]:
    """递归收集文件夹里的文件（含更深层子文件夹），按自然顺序排序。

    返回 (要合并的文件, 被判定为"上次生成的成品"而跳过的文件, 被忽略的文件)。
    排除规则：
      - skip_dirs：整个目录树不扫描（模式B 输出目录等）
      - skip_files：精确文件路径跳过（本次所有目标的计划输出路径）
      - 以「合并报告」开头的文件一律跳过（运行报告防误扫）
      - 与所在文件夹同名（模板结果）的文件视为上次成品
    """
    files: list[Path] = []
    lookalikes: list[Path] = []
    ignored: list[Path] = []
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("~$") or p.name.startswith("."):
            continue
        if p.name.startswith(REPORT_PREFIX):
            continue                                   # 报告文件：静默排除
        try:
            pr = p.resolve()
            if pr in skip_files or any(pr.is_relative_to(d) for d in skip_dirs):
                continue                                # 计划输出路径/排除树：静默排除
        except OSError:
            pass
        # 与所在文件夹同名的 PDF，通常是上一次运行生成的成品，不重复计入
        if skip_lookalikes and p.name == output_name_of(p.parent, template):
            lookalikes.append(p)
            continue
        if p.suffix.lower() not in SUPPORTED_EXTS:
            ignored.append(p)                           # 仅不支持类型列入忽略清单
            continue
        files.append(p)
    key = lambda p: natural_key(str(p.relative_to(folder)).replace("\\", "/"))
    files.sort(key=key)
    lookalikes.sort(key=key)
    ignored.sort(key=key)
    return files, lookalikes, ignored


def iter_target_folders(root: Path, level: int, exclude_dirs: set[Path]):
    """level=1（默认）：每个一级子文件夹各合成一个 PDF；
    level=2：每个二级子文件夹各合成一个 PDF。
    一级文件夹/根目录里若直接放了受支持的文件，也会被当作一个目标。
    exclude_dirs：整棵树不参与（模式B 输出目录）。
    """
    def _clean(dirs):
        out = []
        for d in dirs:
            try:
                dr = d.resolve()
                if dr in exclude_dirs or any(dr.is_relative_to(x) for x in exclude_dirs):
                    continue
            except OSError:
                pass
            out.append(d)
        return sorted(out, key=lambda p: natural_key(p.name))

    subdirs = _clean([p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")])
    if level == 1:
        for d in subdirs:
            yield d
        if any(f.is_file() and f.suffix.lower() in SUPPORTED_EXTS for f in root.iterdir()):
            yield root
        return
    for d1 in subdirs:
        for d2 in _clean([p for p in d1.iterdir() if p.is_dir() and not p.name.startswith("_")]):
            yield d2
        if any(f.is_file() and f.suffix.lower() in SUPPORTED_EXTS for f in d1.iterdir()):
            yield d1
    if any(f.is_file() and f.suffix.lower() in SUPPORTED_EXTS for f in root.iterdir()):
        yield root


def plan_outputs(targets: list[Path], template: str,
                 output_dir: Path | None) -> dict[Path, Path]:
    """为每个目标文件夹算出成品路径（模式B 冲突自动加序号，计划 3.7 规则 2）。

    返回 {目标文件夹: 成品路径}。序号消解只针对本次运行内的同名冲突；
    历史遗留的旧成品按"覆盖更新"语义处理（沿用计划路径）。
    """
    plan: dict[Path, Path] = {}
    seen: dict[str, int] = {}
    for folder in targets:
        base = output_name_of(folder, template)
        if output_dir is not None:
            stem, suffix = _split_name(base)
            n = seen.get(base, 0) + 1
            seen[base] = n
            name = f"{stem}_{n}{suffix}" if n > 1 else base
            plan[folder] = output_dir / name
        else:
            plan[folder] = folder / base
    return plan


def _split_name(name: str) -> tuple[str, str]:
    dot = name.rfind(".")
    if dot <= 0:
        return name, ""
    return name[:dot], name[dot:]