#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cli.py —— A4 合并助手命令行入口（薄封装 core/runner）。

兼容原脚本 merge_to_a4_wps.py 的全部参数与输出风格，新增：
    --output-dir DIR     模式B：统一输出到指定目录
    --only 路径[,路径…]   只处理指定目标（相对路径 / 唯一名称简写）
    --engine auto|wps|native   转换引擎选择
    --no-report          不生成合并报告.txt

常用用法：
    python cli.py                          # 每个一级子文件夹合成一个 PDF（默认）
    python cli.py --level 2                # 改为每个二级子文件夹各合成一个 PDF
    python cli.py -r "D:\\某目录"           # 指定根目录
    python cli.py --output-dir "D:\\合并结果"   # 统一输出目录
    python cli.py --dry-run                # 只预览将合并哪些文件
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import __version__
from core.collect import PDF_EXTS
from core.types import MergeConfig
from core.util import log, setup_console
from core.deps import ensure_module


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="用 WPS/纯Python 把每个一级子文件夹（例如每位股东）里的 PDF / 图片 / "
                    "Word 等文件按顺序合并成一个 A4 大小的 PDF。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-r", "--root", default=None, help="根目录（默认为本脚本所在目录）")
    p.add_argument("--level", type=int, default=1, choices=(1, 2),
                   help="处理第几级子文件夹：1=每个一级子文件夹各合成一个 PDF（默认），"
                        "2=每个二级子文件夹各合成一个 PDF")
    p.add_argument("--output-name", default="【合并】{folder}.pdf",
                   help="输出文件名模板，默认 【合并】{folder}.pdf（{folder} 表示文件夹名）")
    p.add_argument("--output-dir", default=None,
                   help="统一输出目录（模式B）：所有成品集中生成到该目录，默认生成在各子文件夹内")
    p.add_argument("--only", default=None,
                   help="只处理指定目标，逗号分隔（相对路径精确匹配；名称简写仅全局唯一时可用）")
    p.add_argument("--margin-mm", type=float, default=0.0,
                   help="四周留白毫米数，默认 0（内容最大化铺满 A4）")
    p.add_argument("--orientation", default="auto",
                   choices=("auto", "portrait", "landscape"),
                   help="A4 方向：auto=横向内容用 A4 横向（默认）")
    p.add_argument("--image-fit", default="page", choices=("page", "origin"),
                   help="图片是否放大铺满 A4：page=铺满（默认），origin=只缩小不放大")
    p.add_argument("--engine", default="auto", choices=("auto", "wps", "native"),
                   help="转换引擎：auto=自动（默认）/ wps=仅WPS / native=仅纯Python")
    p.add_argument("--wps-timeout", type=int, default=600,
                   help="调用 WPS 转换的超时秒数，默认 600")
    p.add_argument("--include-lookalikes", action="store_true",
                   help="把「与所在文件夹同名的 PDF」也当作素材合并进去"
                        "（默认视为上次生成的成品而跳过）")
    p.add_argument("--password", action="append", default=[],
                   help="加密文件的打开密码，可以写多次，也可以用逗号分隔多个，"
                        "例如 --password 123456 --password abc,888888")
    p.add_argument("--password-file", default=None,
                   help="从文本文件读取密码，每行一个")
    p.add_argument("--no-prompt", action="store_true",
                   help="遇到加密文件不要停下来询问密码，直接跳过")
    p.add_argument("--no-report", action="store_true",
                   help="不生成合并报告.txt")
    p.add_argument("--dry-run", action="store_true",
                   help="只列出将要合并的文件，不生成 PDF")
    p.add_argument("--version", action="version", version=f"A4 合并助手 {__version__}")
    return p


def load_passwords(args) -> list[str]:
    """汇总命令行和密码文件里的密码（去重，保持顺序）。"""
    words: list[str] = []
    for item in args.password or []:
        words.extend(x.strip() for x in str(item).split(","))
    if args.password_file:
        path = Path(args.password_file).expanduser()
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    words.extend(x.strip() for x in line.split(","))
        else:
            log(f"密码文件不存在：{path}")
    return list(dict.fromkeys(w for w in words if w != ""))


def try_first_password(path, verify, known: list[str]):
    """先用已载入的密码尝试；成功返回密码，否则 None。"""
    for pwd in known:
        try:
            if verify(pwd):
                return pwd
        except Exception:
            continue
    return None


def main(argv=None) -> int:
    setup_console()
    args = build_parser().parse_args(argv)
    # 显式 -r 优先；未给时默认当前工作目录（打包版无脚本路径可依，见计划 3.4）
    root = Path(args.root).expanduser().resolve() if args.root else Path.cwd().resolve()

    if not root.is_dir():
        log(f"根目录不存在：{root}")
        return 1

    if not args.dry_run and not ensure_module("pypdf", "pypdf"):
        return 1

    passwords = load_passwords(args)
    if passwords:
        log(f"已载入 {len(passwords)} 个密码，用于尝试打开加密文件。")

    cfg = MergeConfig(
        root=root, level=args.level,
        output_name=args.output_name,
        output_dir=Path(args.output_dir).expanduser().resolve() if args.output_dir else None,
        only=[x.strip() for x in args.only.split(",")] if args.only else None,
        margin_mm=args.margin_mm, orientation=args.orientation,
        image_fit=args.image_fit, include_lookalikes=args.include_lookalikes,
        passwords=passwords, prompt=not args.no_prompt,
        dry_run=args.dry_run, wps_timeout=args.wps_timeout,
        engine=args.engine, report=not args.no_report,
    )

    known = list(passwords)          # 交互输入成功的密码也加入，后续同密码文件自动使用

    def on_log(level: str, msg: str) -> None:
        log(msg)

    def on_progress(kind: str, done: int, total: int, text: str) -> None:
        if kind == "folder":
            log(f"〔进度 {done + 1}/{total}〕 {text}")

    def ask_password(path: Path, verify) -> str | None:
        pwd = try_first_password(path, verify, known)
        if pwd:
            return pwd
        if not cfg.prompt:
            return None
        log(f"   ⏸  「{path.name}」已加密，需要密码")
        for _ in range(3):
            try:
                typed = input("      请输入打开密码（直接回车＝跳过这个文件）：").strip()
            except (EOFError, KeyboardInterrupt):
                log("      （当前环境无法输入密码，已跳过）")
                return None
            if not typed:
                return None
            if verify(typed):
                if typed not in known:
                    known.append(typed)
                log("      ✔ 密码正确")
                return typed
            log("      ✘ 密码不正确，请重试")
        return None

    try:
        summary = __import__("core.runner", fromlist=["run"]).run(
            cfg, on_log=on_log, on_progress=on_progress,
            ask_password=ask_password, should_cancel=lambda: False)
    except ValueError as exc:
        log(f"配置错误：{exc}")
        return 2
    except Exception as exc:
        log(f"运行失败：{exc}")
        return 1

    # ------------------------------------------------------------ 结果汇总
    if args.dry_run:
        log("\n" + "=" * 62)
        log("预览完成，未生成任何文件。（去掉 --dry-run 即可真正生成）")
        return 0

    done = sum(1 for r in summary.results if r.done)
    failed = sum(1 for r in summary.results if r.files_count and not r.done)
    log("\n" + "=" * 62)
    log(f"处理完成：成功 {done} 个文件夹，失败 {failed} 个。")
    for res in summary.results:
        if res.done:
            log(f"  ✔ {res.label} → {res.out_path.name}（{res.pages} 页）")
        elif res.files_count:
            keep = "（原来的同名 PDF 保留未更新）" if res.out_path and res.out_path.exists() else ""
            log(f"  ✘ {res.label} 未生成{keep}")

    warns = [(r.label, w) for r in summary.results for w in r.warnings]
    if warns:
        log("\n注意事项：")
        for name, w in warns:
            log(f"  · [{name}] {w}")

    failures = [(r.folder, f) for r in summary.results for f in r.failures]
    if failures:
        def _show(p: Path) -> str:
            try:
                return str(p.relative_to(root))
            except Exception:
                return str(p)

        pdf_fail = [x for x in failures if x[1].path.suffix.lower() in PDF_EXTS]
        other_fail = [x for x in failures if x[1].path.suffix.lower() not in PDF_EXTS]
        log(f"\n没能成功打开/合并的文件共 {len(failures)} 个：")
        if pdf_fail:
            log(f"  【PDF（{len(pdf_fail)} 个）】")
            for _folder, f in pdf_fail:
                log(f"    · {_show(f.path)}    —— {f.reason}"
                    + (f"（跳过 {f.skipped_pages} 页）" if f.skipped_pages else ""))
        if other_fail:
            log(f"  【其它文件（{len(other_fail)} 个）】")
            for _folder, f in other_fail:
                log(f"    · {_show(f.path)}    —— {f.reason}")
        log("  这些文件没有进入合并结果，其余文件正常合并。")
    else:
        log("\n所有文件都成功打开并合并。")

    skipped_look = [(r.label, f.relative_to(r.folder))
                    for r in summary.results for f in r.lookalikes]
    if skipped_look:
        log(f"\n已跳过 {len(skipped_look)} 个「与所在文件夹同名」的 PDF"
            f"（按上次生成的成品处理，没有重复合并）：")
        for label, f in skipped_look:
            log(f"  · {label} → {f.name}")
        log("  如需把它们也合并进去，运行时加上 --include-lookalikes")

    ignored = sorted({f.name for r in summary.results for f in r.ignored})
    if ignored:
        log("\n以下文件类型不支持/已排除，忽略：" + "、".join(ignored))
    return 0


if __name__ == "__main__":
    sys.exit(main())