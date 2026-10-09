#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_gui.py —— 程序入口（开发期直接运行；打包版同一入口）。

自动化验收（仅打包版验收使用，见 tests/test_frozen_exe.py）：
    A4_AUTOMATION=1 时可用 `--auto`，启动后自动填根目录 → 开始合并 →
    结果写到 A4_AUTOMATION_REPORT 指定的文件后自动退出。
不带 --auto 时行为完全不变。
"""
import sys

from app.main import main


def _expand_argv(argv: list[str]) -> list[str]:
    """把 --auto 展开成主窗口认识的等价参数（--smoke 让结果对话框不阻塞）。"""
    out: list[str] = []
    for arg in argv:
        if arg == "--auto":
            out.extend(["--smoke", "--auto-run"])
        else:
            out.append(arg)
    return out


if __name__ == "__main__":
    sys.exit(main(_expand_argv(sys.argv)))
