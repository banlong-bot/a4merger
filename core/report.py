"""core/report.py —— 运行报告生成（合并报告.txt，UTF-8-sig，计划 3.8.2）。"""
from __future__ import annotations

import datetime
from pathlib import Path

from core import __version__
from core.types import RunSummary


def _fmt(sec: float) -> str:
    return f"{sec:.1f} 秒"


def write_report(path: Path, summary: RunSummary) -> Path:
    cfg = summary.config
    mode = "B：统一输出目录" if cfg.output_dir is not None else "A：各子文件夹内"
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("A4 合并助手 运行报告")
    lines.append("=" * 60)
    lines.append(f"应用版本    ：{__version__}")
    lines.append(f"运行时间    ：{summary.started}")
    lines.append(f"总耗时      ：{_fmt(summary.elapsed)}")
    lines.append(f"根目录      ：{cfg.root}")
    lines.append(f"输出模式    ：{mode}"
                 + (f" → {cfg.output_dir}" if cfg.output_dir else ""))
    lines.append(f"处理级别    ：{cfg.level} 级子文件夹")
    lines.append(f"文件名模板  ：{cfg.output_name}")
    lines.append(f"A4 方向     ：{cfg.orientation}　　留白：{cfg.margin_mm}mm")
    lines.append(f"图片适配    ：{cfg.image_fit}　　引擎：{cfg.engine}")
    lines.append(f"已载入密码  ：{len(cfg.passwords)} 个")
    lines.append(f"引擎探测    ：WPS {'可用' if summary.engine_info.get('wps') else '不可用'} / "
                 f"纯 Python {'可用' if summary.engine_info.get('native') else '不可用'}")
    lines.append("")
    lines.append("【目标清单】")
    for r in summary.results:
        mark = "✔ 成功" if r.done else ("✘ 未生成" if r.files_count else "○ 无素材")
        extra = ""
        if r.out_path and r.done:
            size = f"{r.out_path.stat().st_size / 1024 / 1024:.1f} MB"
            extra = f" →  {r.out_path}（{r.pages} 页，{size}）"
        lines.append(f"{mark}  {r.label}{extra}")
    lines.append("")
    lines.append("【未能合并的文件】")
    fail_count = 0
    for r in summary.results:
        for f in r.failures:
            fail_count += 1
            lines.append(f"  · {f.path}    —— {f.reason}"
                         + (f"（跳过 {f.skipped_pages} 页）" if f.skipped_pages else ""))
    if fail_count == 0:
        lines.append("  （无）")
    lines.append("")
    lines.append("【跳过的成品 PDF（默认视为上次生成结果）】")
    skip_count = 0
    for r in summary.results:
        for p in r.lookalikes:
            skip_count += 1
            lines.append(f"  · {r.label} → {p.name}")
    if skip_count == 0:
        lines.append("  （无）")
    lines.append("")
    lines.append("【忽略的文件】")
    ign = sorted({f.name for r in summary.results for f in r.ignored})
    lines.append("  " + (("、".join(ign)) if ign else "（无）"))
    lines.append("")
    total_pages = sum(r.pages for r in summary.results)
    lines.append(f"合计：成功 {sum(1 for r in summary.results if r.done)} 个目标，"
                 f"共 {total_pages} 页。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path