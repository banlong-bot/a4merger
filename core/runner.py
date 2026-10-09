"""core/runner.py —— 任务编排（原 main/process_folder 逻辑重构，可重入、回调化）。"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

from core.collect import (PDF_EXTS, SUPPORTED_EXTS, collect_files,
                          iter_target_folders, plan_outputs, wps_kind)
from core.converters.base import ConvertTask
from core.converters.backend_native import NativeConverter
from core.converters.backend_wps import WpsConverter, run_wps_worker
from core.converters.manager import detect, pick
from core.encrypt import (decrypt_office, office_needs_password,
                          office_password_ok, pdf_needs_password,
                          pdf_password_ok)
from core.merge import merge_to_a4
from core.report import write_report
from core.types import (FileFailure, FolderResult, MergeConfig, RunSummary)

_pw_name = "core.runner"


def _fmt_path(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except Exception:
        return str(p)


def _filter_only(targets: list[Path], only: list[str] | None,
                 root: Path) -> list[Path]:
    """--only 过滤（计划 3.11.5）：相对路径精确匹配；名称简写仅全局唯一时可用。"""
    if not only:
        return targets
    rels = {t: str(t.relative_to(root)).replace("\\", "/") for t in targets}
    selected: list[Path] = []
    for token in only:
        token = token.strip().replace("\\", "/")
        if not token:
            continue
        hits = [t for t, r in rels.items() if r == token]
        if not hits and "/" not in token:
            name_hits = [t for t, r in rels.items() if t.name == token]
            if name_hits:
                hits = name_hits            # 名称简写：唯一可选，不唯一则进歧义分支
        if not hits:
            cand = "、".join(sorted(rels.values()))
            raise ValueError(f"--only 指定的「{token}」没有匹配的目标（候选：{cand}）")
        if len(hits) > 1:
            dup = "、".join(sorted(rels[t] for t in hits))
            raise ValueError(f"--only 指定的「{token}」匹配了多个目标（{dup}），"
                             f"请改用相对路径精确指定")
        selected.extend(hits)
    return list(dict.fromkeys(selected))


def run(cfg: MergeConfig, on_log=None, on_progress=None,
        ask_password=None, should_cancel=None) -> RunSummary:
    """执行一次完整合并。所有输出经回调上报；不依赖 Qt。"""
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.time()
    logger = on_log or (lambda level, msg: None)
    prog = on_progress or (lambda kind, done, total, text: None)

    errs = cfg.validate()
    if errs:
        raise ValueError("；".join(errs))

    engine_info = detect()
    logger("info", f"引擎探测：WPS {'可用' if engine_info.get('wps') else '不可用'} / "
                   f"纯 Python {'可用' if engine_info.get('native') else '不可用'}")

    # 模式B：预先创建输出目录（失败提前拦截）
    if cfg.output_dir is not None:
        try:
            cfg.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"输出目录创建失败：{cfg.output_dir}（{exc}）")

    exclude_dirs = {cfg.output_dir.resolve()} if cfg.output_dir else set()
    targets = list(iter_target_folders(cfg.root, cfg.level, exclude_dirs))
    targets = _filter_only(targets, cfg.only, cfg.root)
    if not targets:
        logger("warn", f"在 {cfg.root} 下没找到需要处理的文件夹。")
        return RunSummary(started, time.time() - t0, engine_info, cfg, [])

    logger("info", f"根目录：{cfg.root}")
    logger("info", f"待处理文件夹：{len(targets)} 个" +
           ("（预览模式，不会生成文件）" if cfg.dry_run else ""))

    plan = plan_outputs(targets, cfg.output_name, cfg.output_dir)
    all_outputs = set(p.resolve() for p in plan.values())

    tmp_root = Path(tempfile.mkdtemp(prefix="a4merge_root_"))
    results: list[FolderResult] = []
    wps = WpsConverter()
    native = NativeConverter()
    try:
        for i, folder in enumerate(targets):
            if should_cancel is not None and should_cancel():
                logger("warn", "已收到取消请求，停止处理后续文件夹。")
                break
            prog("folder", i, len(targets), str(folder))
            try:
                res = _process_folder(folder, plan[folder], cfg, tmp_root,
                                      all_outputs, engine_info, wps, native,
                                      logger, ask_password, should_cancel, prog)
            except Exception as exc:
                logger("error", f"   !! 处理失败：{exc}")
                res = FolderResult(folder=folder,
                                   label=_fmt_path(cfg.root, folder),
                                   out_path=plan[folder],
                                   files_count=0,
                                   warnings=[str(exc)],
                                   replaced_output=plan[folder].exists())
            results.append(res)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    summary = RunSummary(started, time.time() - t0, engine_info, cfg, results)
    if cfg.report and not cfg.dry_run:
        loc = cfg.output_dir or cfg.root
        summary.report_path = write_report(loc / "合并报告.txt", summary)
        logger("ok", f"运行报告：{summary.report_path}")
    return summary


# ------------------------------------------------------------------ 单个文件夹

def _process_folder(folder: Path, out_path: Path, cfg: MergeConfig, tmp_root: Path,
                    all_outputs: set[Path], engine_info: dict[str, bool],
                    wps: WpsConverter, native: NativeConverter,
                    logger, ask_password, should_cancel, prog) -> FolderResult:
    label = str(folder.relative_to(cfg.root)) if folder != cfg.root else folder.name
    result = FolderResult(folder=folder, label=label, out_path=out_path,
                          files_count=0, replaced_output=out_path.exists())

    skip_dirs = {cfg.output_dir.resolve()} if cfg.output_dir else set()
    files, lookalikes, ignored = collect_files(
        folder, skip_dirs, all_outputs, cfg.output_name,
        skip_lookalikes=not cfg.include_lookalikes)
    used = [f for f in files if f.suffix.lower() in SUPPORTED_EXTS]
    result.lookalikes = lookalikes
    result.ignored = ignored
    result.files_count = len(used)
    if not used:
        return result

    logger("info", f"\n▶ {label}   （{len(used)} 个文件）")
    for i, f in enumerate(used, 1):
        logger("info", f"   {i:>3}. {_fmt_path(folder, f)}")
    if lookalikes:
        names = "、".join(_fmt_path(folder, f) for f in lookalikes)
        logger("warn", f"   （跳过 {len(lookalikes)} 个「与所在文件夹同名」的 PDF，"
                       f"视为上次生成的成品：{names}）")
    if result.replaced_output:
        logger("warn", f"   （已存在同名 PDF「{out_path.name}」，视为上次的合并结果："
                       f"不计入本次合并，最后会被覆盖）")
    if cfg.dry_run:
        return result

    tmp_dir = Path(tempfile.mkdtemp(prefix="a4merge_", dir=str(tmp_root)))
    try:
        blocked: set[Path] = set()

        # 0) 加密 PDF：预置密码先行，不行再回调询问
        file_pw: dict[str, str] = {}
        for f in used:
            if f.suffix.lower() not in PDF_EXTS or not pdf_needs_password(f):
                continue
            pwd = None
            for known in cfg.passwords:
                if pdf_password_ok(f, known):
                    pwd = known
                    break
            if pwd is None and ask_password is not None and cfg.prompt:
                pwd = ask_password(f, lambda p, _f=f: pdf_password_ok(_f, p))
            if pwd is None:
                blocked.add(f)
                result.failures.append(FileFailure(f, "PDF 已加密，没有可用的打开密码"))
                logger("error", f"   !! 跳过 {f.name}：没有正确的打开密码")
                continue
            file_pw[str(f)] = pwd

        # 1) 转换：WPS 任务收集 + native 直转
        wps_jobs: list[dict] = []
        native_jobs: list[tuple[Path, Path]] = []
        converted: dict[Path, Path] = {}
        for i, f in enumerate(used, 1):
            kind = wps_kind(f.suffix.lower())
            if f.suffix.lower() in PDF_EXTS or kind is None:
                continue
            backend = pick(kind, cfg.engine, engine_info)
            out = tmp_dir / f"{i:04d}.pdf"
            if backend == "none":
                reason = ("需要 WPS" if kind in ("word", "excel", "ppt")
                          else "没有可用的转换引擎")
                result.failures.append(FileFailure(f, f"无法转换：{reason}"))
                logger("error", f"   !! 跳过 {f.name}：{reason}")
                continue
            if backend == "native":
                native_jobs.append((f, out))
                converted[f] = out
                result.engines[_fmt_path(folder, f)] = "纯Python"
                continue
            # backend == "wps"
            result.engines[_fmt_path(folder, f)] = "WPS"
            src_for_wps = f
            if kind in ("word", "excel", "ppt") and office_needs_password(f):
                plain = decrypt_office(f, cfg.passwords, tmp_dir, i)
                if plain is None and ask_password is not None and cfg.prompt:
                    pwd = ask_password(f, lambda p, _f=f: office_password_ok(_f, p, tmp_dir))
                    if pwd is not None:
                        plain = decrypt_office(f, [pwd], tmp_dir, i)
                if plain is None:
                    blocked.add(f)
                    result.failures.append(FileFailure(f, "Office 文件已加密，没有可用的打开密码"))
                    logger("error", f"   !! 跳过 {f.name}：文件已加密，未能打开"
                                    f"（可用 --password 指定密码）")
                    continue
                src_for_wps = plain
                logger("info", f"   ·  {f.name}：已用密码解密后再交给 WPS")
            job = {"kind": kind, "src": str(src_for_wps.resolve()), "out": str(out),
                   "fit": cfg.image_fit == "page"}
            if kind in ("word", "excel"):
                job["passwords"] = [""] + list(cfg.passwords or [])
            wps_jobs.append(job)
            converted[f] = out

        # native 直转
        for f, out in native_jobs:
            if should_cancel is not None and should_cancel():
                break
            r = native.convert(ConvertTask(f, out, wps_kind(f.suffix.lower()),
                                           fit=cfg.image_fit == "page"),
                               should_cancel, cfg.wps_timeout)
            if not r.ok and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                result.failures.append(FileFailure(f, f"图片转换失败（{r.error}）"))
                logger("error", f"   !! 跳过 {f.name}：{r.error}")

        # 2) WPS 批量转换：保留原脚本 3 轮重试（超时不再重试）
        logger("info", "   → 调用 WPS 转换文档…" if wps_jobs else "   → 其余为 PDF/纯Python，无需 WPS")
        by_out: dict[str, dict] = {}
        pending = list(wps_jobs)
        for attempt in (1, 2, 3):
            if not pending:
                break
            if should_cancel is not None and should_cancel():
                break
            if attempt == 3:
                logger("warn", f"   !  仍有 {len(pending)} 个文件没转成功，改为逐个重试…")
                batches = [[j] for j in pending]
            else:
                if attempt == 2:
                    logger("warn", f"   !  {len(pending)} 个文件第一次没转成功，稍后重试…")
                    time.sleep(1.5)
                batches = [pending]
            for batch in batches:
                for item in run_wps_worker(batch, tmp_dir, cfg.wps_timeout, should_cancel):
                    if not isinstance(item.get("out"), str):
                        continue
                    key = item["out"]
                    if item.get("ok") or not by_out.get(key, {}).get("ok"):
                        by_out[key] = item
            pending = [j for j in pending
                       if not by_out.get(j["out"], {}).get("ok")
                       and "超时" not in str(by_out.get(j["out"], {}).get("error", ""))]

        # 3) 组装 sources
        sources: list[Path] = []
        for f in used:
            if f in blocked:
                continue
            if f.suffix.lower() in PDF_EXTS:
                sources.append(f)
                continue
            tmp_pdf = converted.get(f)
            item = by_out.get(str(tmp_pdf)) if tmp_pdf else None
            if tmp_pdf and tmp_pdf.exists() and (item is None or item.get("ok")):
                sources.append(tmp_pdf)
                continue
            # WPS 没成功时，图片还能用 Pillow 兜底
            if f.suffix.lower() in {".jpg", ".jpeg", ".jfif", ".png", ".bmp",
                                    ".gif", ".tif", ".tiff", ".webp", ".heic"}:
                why = (item or {}).get("error") or "未生成文件"
                try:
                    r = native.convert(ConvertTask(f, tmp_pdf, "image",
                                                   fit=cfg.image_fit == "page"),
                                       should_cancel, cfg.wps_timeout)
                    if r.ok and tmp_pdf.exists():
                        sources.append(tmp_pdf)
                        result.warnings.append(
                            f"{f.name}：WPS 转换失败（{why}），已改用 Pillow 生成图片页")
                        logger("warn", f"   !  {f.name}：WPS 转换失败（{why}），改用 Pillow 兜底")
                        continue
                    raise RuntimeError(r.error)
                except Exception as exc:
                    result.failures.append(FileFailure(f, f"转换失败（{exc}）"))
                    continue
            reason = (item or {}).get("error") or "未知原因"
            result.failures.append(FileFailure(f, f"WPS 转换失败（{reason}）"))
            logger("error", f"   !! 跳过 {f.name}：{reason}")

        if not sources:
            result.warnings.append("没有任何可合并的页面")
            return result

        # 4) 统一排到 A4 并合并（原子替换，见计划 3.7）
        final_tmp = out_path.parent / f"~$merge_tmp_{os.getpid()}.pdf"
        try:
            def _on_page(done: int) -> None:
                prog("page", done, 0, f"正在排版 {label} 第 {done} 页…")

            pages, warns, _map = merge_to_a4(
                sources, final_tmp, cfg.margin_mm, cfg.orientation,
                title=folder.name, passwords=cfg.passwords,
                passwords_by_file=file_pw, failures=result.failures,
                on_page=_on_page)
            for w in warns:
                warn_only = w in [x.reason for x in result.failures]
                if not warn_only:
                    logger("warn", f"   !! {w}")
            if pages == 0:
                result.warnings.append("没有生成任何页面")
                return result
            os.replace(final_tmp, out_path)
        finally:
            if final_tmp.exists():
                final_tmp.unlink()

        result.pages = pages
        result.done = True
        size_mb = out_path.stat().st_size / 1024 / 1024
        logger("ok", f"   ✔ 已生成 {out_path.name}（{pages} 页，{size_mb:.1f} MB）")
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)