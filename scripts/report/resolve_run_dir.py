#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the run directory for an industry-analysis task.

优先级（从高到低）：
1. --run-dir 显式指定（用户当前任务指定的文件夹，最优先）
2. --workspace 显式指定的任务工作区
3. 当前工作目录 CWD——仅当其看起来是任务工作区（含 inputs/、parts/、evidence/ 或 .workflow.json 之一）
4. 其余情况：不猜测、不默认 Desktop，退出并要求用户指定文件夹

绝不默认创建 C:/Users/.../Desktop/...。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_MARKERS = ("inputs", "parts", "evidence", "analysis", "charts", ".workflow.json")


def looks_like_workspace(path: Path) -> bool:
    return any((path / marker).exists() for marker in WORKSPACE_MARKERS)


def looks_like_desktop(path: Path) -> bool:
    return "Desktop" in path.parts


def resolve(explicit: str | None, workspace: str | None, cwd: Path) -> tuple[Path, str]:
    if explicit:
        return Path(explicit).expanduser().resolve(), "explicit"
    if workspace:
        return Path(workspace).expanduser().resolve(), "workspace"
    if looks_like_workspace(cwd):
        return cwd.resolve(), "cwd"
    # 不再回退到 Desktop；让编排者停下来询问用户
    raise SystemExit(
        "[resolve_run_dir] 无法确定任务目录：\n"
        f"  当前目录 {cwd} 不是任务工作区（缺少 inputs/parts/evidence/.workflow.json）。\n"
        "  请在用户当前任务指定的文件夹内运行，或用 --run-dir/--workspace 显式指定。\n"
        "  本工具不会默认创建 Desktop 目录。"
    )


def main() -> int:
    p = argparse.ArgumentParser(description="解析行业分析任务运行目录（禁止默认 Desktop）")
    p.add_argument("--run-dir", help="用户显式指定的任务目录（最优先）")
    p.add_argument("--workspace", help="任务工作区目录（次优先）")
    p.add_argument("--cwd", type=Path, default=Path.cwd(), help="判定用当前目录")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    run_dir, source = resolve(args.run_dir, args.workspace, args.cwd)
    if looks_like_desktop(run_dir) and source != "explicit":
        raise SystemExit(f"[resolve_run_dir] 解析结果落在 Desktop 且非用户显式指定，拒绝：{run_dir}")
    info = {"run_dir": str(run_dir), "source": source, "is_workspace": looks_like_workspace(run_dir)}
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())