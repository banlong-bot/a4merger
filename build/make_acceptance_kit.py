# -*- mode: python ; coding: utf-8 -*-
"""build/make_acceptance_kit.py —— 一键准备验收包（M5 人工异机验收用）。

做的事：
  1. 检查 dist/A4合并助手.exe 是否存在，打印大小/版本/SHA256，**不匹配就中止**；
  2. 把 exe 复制到指定目录（默认 `%USERPROFILE%\\Desktop\\A4合并助手-验收包\\`）；
  3. 生成验收测试数据（调用 tests/make_samples.py）并打包为 zip；
  4. 复制《M5人工异机验收单.md》一并放进验收包；
  5. 打印验收包清单，直接拷贝该目录到 U 盘即可。

用法：
    python build/make_acceptance_kit.py                 # 默认桌面
    python build/make_acceptance_kit.py D:\\验收包        # 指定输出目录
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "dist" / "A4合并助手.exe"
CHECKLIST = REPO / "docs" / "M5人工异机验收单.md"
SAMPLES = REPO / "tests" / "samples"
# 每次重新打包后，把指纹填到这里即可让脚本自动拦截"发错 exe"（留空=只打印不校验）
EXPECTED_SIZE = 0
EXPECTED_SHA256 = ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    out = Path(argv[0]).resolve() if argv else \
        Path.home() / "Desktop" / "A4合并助手-验收包"
    if not EXE.exists():
        print(f"[中止] 未找到 {EXE}，请先执行：\n"
              f"  python -m PyInstaller --noconfirm --clean --distpath dist "
              f"--workpath build\\pyi_work build/a4merger.spec")
        return 2

    digest = sha256(EXE)
    print(f"exe      ：{EXE}")
    print(f"大小     ：{EXE.stat().st_size:,} 字节")
    print(f"SHA256   ：{digest}")
    if EXPECTED_SIZE and EXE.stat().st_size != EXPECTED_SIZE:
        print(f"[中止] 大小与验收单记录不一致（期望 {EXPECTED_SIZE:,}）——"
              f"请先更新验收单里的指纹再发验收包。")
        return 3
    if EXPECTED_SHA256 and digest != EXPECTED_SHA256:
        print("[中止] SHA256 与验收单记录不一致——请先更新验收单里的指纹。")
        return 3

    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXE, out / EXE.name)
    print("已复制 exe")

    print("重建测试样例（tests/make_samples.py）…")
    subprocess.run([sys.executable, str(REPO / "tests" / "make_samples.py")],
                   check=True, cwd=str(REPO))
    zip_base = out / "验收测试数据"
    if (out / "验收测试数据.zip").exists():
        (out / "验收测试数据.zip").unlink()
    shutil.make_archive(str(zip_base), "zip", str(SAMPLES))
    print("已生成 验收测试数据.zip")

    if CHECKLIST.exists():
        shutil.copy2(CHECKLIST, out / CHECKLIST.name)
        print("已复制 验收单")

    print("\n验收包清单：")
    for p in sorted(out.iterdir()):
        size = p.stat().st_size
        print(f"  {p.name}    {size/1024/1024:.2f} MB" if size > 1024 * 1024
              else f"  {p.name}    {size/1024:.0f} KB")
    print(f"\n输出目录：{out}\n把它整个拷到 U 盘 → 目标机器解压/放置到浅目录（如 D:\\A4合并助手\\）即可开始验收。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
