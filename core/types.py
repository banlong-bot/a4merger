"""core/types.py —— 结构化类型、回调接口与统一配置。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# 回调接口（core 不依赖 Qt，GUI 用 Signal 包装这些回调）
LogFn = Callable[[str, str], None]                      # (level, message) level: info/warn/error/ok
ProgressFn = Callable[[str, int, int, str], None]       # (kind, done, total, text)
AskPasswordFn = Callable[[Path, Callable[[str], bool]], Optional[str]]
CancelFn = Callable[[], bool]


@dataclass
class MergeConfig:
    """一次运行的全部配置（对应 cli 参数 / GUI 表单）。"""
    root: Path
    level: int = 1                          # 0=当前文件夹（根目录本身）/ 1=一级 / 2=二级
    output_name: str = "【合并】{folder}.pdf"
    output_dir: Optional[Path] = None       # 模式B：统一输出目录
    only: Optional[list[str]] = None        # 相对路径子集（--only）
    margin_mm: float = 0.0
    orientation: str = "auto"               # auto/portrait/landscape
    image_fit: str = "page"                 # page/origin
    include_lookalikes: bool = False
    passwords: list[str] = field(default_factory=list)
    prompt: bool = True                     # 是否允许交互询问密码
    dry_run: bool = False
    wps_timeout: int = 600
    engine: str = "auto"                    # auto/wps/native
    report: bool = True                     # 是否生成合并报告.txt

    def validate(self) -> list[str]:
        """启动期校验（计划 3.11.6：模板非法字符/未知占位符等）。返回错误列表。"""
        errs: list[str] = []
        bad = set('\\/:*?"<>|')
        if any(c in bad for c in self.output_name.replace("{", "").replace("}", "")):
            errs.append(f"输出文件名模板含非法字符：{self.output_name}")
        import re
        for m in re.finditer(r"\{([^{}]*)\}", self.output_name):
            if m.group(1) not in ("folder", "name"):
                errs.append(f"模板含未知占位符 {{{m.group(1)}}}（仅支持 {{folder}}/{{name}}，将按字面输出）")
        if self.level not in (0, 1, 2):
            errs.append(f"未知处理级别：{self.level}（仅支持 0=当前文件夹 / 1 / 2）")
        if self.orientation not in ("auto", "portrait", "landscape"):
            errs.append(f"未知方向：{self.orientation}")
        if self.image_fit not in ("page", "origin"):
            errs.append(f"未知图片适配：{self.image_fit}")
        if self.engine not in ("auto", "wps", "native"):
            errs.append(f"未知引擎：{self.engine}")
        return errs


@dataclass
class FileFailure:
    """单个文件未能合并的记录。"""
    path: Path
    reason: str
    skipped_pages: int = 0


@dataclass
class FolderResult:
    """一个目标文件夹的处理结果。"""
    folder: Path
    label: str
    out_path: Optional[Path]
    files_count: int
    pages: int = 0
    done: bool = False
    engines: dict[str, str] = field(default_factory=dict)      # 文件 -> 使用的引擎
    failures: list[FileFailure] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    lookalikes: list[Path] = field(default_factory=list)
    ignored: list[Path] = field(default_factory=list)
    replaced_output: bool = False


@dataclass
class RunSummary:
    """整次运行的总览（供报告文件与 GUI 总结框）。"""
    started: str
    elapsed: float
    engine_info: dict[str, bool]
    config: MergeConfig
    results: list[FolderResult] = field(default_factory=list)
    report_path: Optional[Path] = None