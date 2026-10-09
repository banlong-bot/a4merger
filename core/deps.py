"""core/deps.py —— 依赖保障（开发模式 pip 自动安装；打包后禁用，见计划 3.8.3）。"""
from __future__ import annotations

import subprocess
import sys

PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def ensure_module(import_name: str, pip_name: str) -> bool:
    """确保某个库可用。

    打包版（sys.frozen）绝不尝试 pip——直接报错提示重装应用；
    开发模式缺依赖时自动安装（官方源不通时换国内镜像）。
    """
    try:
        __import__(import_name)
        return True
    except ImportError:
        pass
    if is_frozen():
        raise RuntimeError(
            f"应用组件缺失（{pip_name}），请重新安装《A4 合并助手》最新版本")
    from core.util import log
    log(f"未检测到 {pip_name}，正在尝试自动安装……")
    tries = [
        [sys.executable, "-m", "pip", "install", "--quiet", pip_name],
        [sys.executable, "-m", "pip", "install", "--quiet", "--retries", "2",
         "-i", PYPI_MIRROR, pip_name],
    ]
    for cmd in tries:
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            __import__(import_name)
            return True
        except Exception:
            continue
    log(f"{pip_name} 自动安装失败，可手动执行：pip install {pip_name}")
    return False