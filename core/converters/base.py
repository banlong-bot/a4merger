"""core/converters/base.py —— Converter 统一接口（计划 3.6）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConvertTask:
    src: Path
    out: Path
    kind: str                  # word/text/image/excel/ppt
    passwords: list[str] = field(default_factory=list)
    fit: bool = True           # 图片：true=放大铺满 A4，false=只缩小


@dataclass
class ConvertResult:
    ok: bool
    error: str = ""


class Converter(ABC):
    """一个转换引擎后端。"""

    name: str = "abstract"

    @abstractmethod
    def available(self) -> bool:
        """后端是否可用（探测）。"""

    @abstractmethod
    def convert(self, task: ConvertTask, cancel, timeout: int) -> ConvertResult:
        """执行转换；cancel() 返回 True 时应尽快终止并返回失败结果。"""