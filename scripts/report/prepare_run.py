#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare a task run directory: structure, task-level .venv, chart helper copies.

在已解析的 run_dir 内完成运行时准备（幂等）：
- 目录结构
- {run_dir}/.venv（Windows: .venv/Scripts/python.exe），不复用 skill 安装目录的 .venv
- 只把「检查登记」辅助脚本复制到 {run_dir}/scripts/charts/（render_visual_check.py）；
  gen_chart.py 保留在 skill 内仅作字体/布局工具参考——正式图表一律由 AI 按数据手写代码，不复制固定生成器
- 把运行时信息写回 stdout（JSON）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/report -> skill root
CHART_HELPERS = ("render_visual_check.py",)
REQUIRED_PKGS = ("matplotlib", "pandas", "numpy")
MIRROR = "https://mirrors.aliyun.com/pypi/simple/"


def task_python(run_dir: Path) -> Path:
    if os.name == "nt":
        return run_dir / ".venv" / "Scripts" / "python.exe"
    return run_dir / ".venv" / "bin" / "python"


def ensure_venv(run_dir: Path) -> Path:
    py = task_python(run_dir)
    marker = run_dir / ".venv" / "pyvenv.cfg"
    if not py.is_file():
        print(f"[prepare_run] 创建任务虚拟环境: {run_dir / '.venv'}")
        venv.EnvBuilder(with_pip=True, clear=False).create(run_dir / ".venv")
    if not marker.is_file():
        raise SystemExit(f"[prepare_run] 任务虚拟环境异常（缺 pyvenv.cfg）: {run_dir / '.venv'}")
    # 依赖检查（幂等）
    check = subprocess.run([str(py), "-c", "import matplotlib,pandas,numpy"],
                           capture_output=True, text=True)
    if check.returncode != 0:
        print("[prepare_run] 安装图表依赖（matplotlib/pandas/numpy）...")
        subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip", "-q"], check=False)
        install = subprocess.run([str(py), "-m", "pip", "install", "-q", *REQUIRED_PKGS],
                                 capture_output=True, text=True)
        if install.returncode != 0:
            print("[prepare_run] 官方源失败，切换阿里云镜像重试...")
            install = subprocess.run([str(py), "-m", "pip", "install", "-q",
                                      *REQUIRED_PKGS, "-i", MIRROR], capture_output=True, text=True)
        if install.returncode != 0:
            raise SystemExit(f"[prepare_run] 依赖安装失败：\n{install.stderr[-800:]}")
    return py


def copy_chart_helpers(run_dir: Path) -> list[str]:
    out_dir = run_dir / "scripts" / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in CHART_HELPERS:
        src = SKILL_ROOT / "scripts" / "charts" / name
        dst = out_dir / name
        if src.is_file():
            shutil.copy2(src, dst)
            copied.append(str(dst))
    return copied


def ensure_dirs(run_dir: Path) -> None:
    for sub in ("inputs", "evidence/sources", "analysis", "parts", "charts",
                "reviews", "output", "logs", "scripts/charts"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description="准备任务运行目录（目录结构/任务 venv/检查登记脚本副本）")
    p.add_argument("--run-dir", type=Path, required=True, help="已解析的任务目录（禁止 Desktop 默认）")
    args = p.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    if "Desktop" in run_dir.parts:
        raise SystemExit(f"[prepare_run] 拒绝在 Desktop 下创建任务目录：{run_dir}（请使用当前任务指定文件夹）")
    ensure_dirs(run_dir)
    py = ensure_venv(run_dir)
    copied = copy_chart_helpers(run_dir)
    info = {
        "run_dir": str(run_dir),
        "task_python": str(py),
        "python_version": subprocess.run([str(py), "--version"], capture_output=True,
                                         text=True).stdout.strip(),
        "chart_helpers": copied,
        "note": "skill 安装目录的 .venv 不会被任务使用；gen_chart.py 仅作参考库不复制",
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())