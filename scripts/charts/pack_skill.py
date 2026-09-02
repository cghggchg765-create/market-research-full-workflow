#!/usr/bin/env python3
"""重打包 dist/market-research-full-workflow.skill（zip，前缀 market-research-full-workflow/）"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # skill 根目录
OUT = os.path.join(ROOT, "dist", "market-research-full-workflow.skill")
EXCLUDE_DIRS = {".venv", "charts", "dist", ".git", "__pycache__"}
EXCLUDE_PARTS = ("self-test-output", ".pyc")

include = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    rel = os.path.relpath(dirpath, ROOT).replace(os.sep, "/")
    # 只排除根级目录（.venv/charts/dist/.git）与自测产物目录
    dirnames[:] = [d for d in dirnames
                   if not (rel == "." and d in EXCLUDE_DIRS)
                   and not any(p in os.path.join(rel, d) for p in EXCLUDE_PARTS)]
    for f in filenames:
        p = os.path.join(rel, f).replace(os.sep, "/") if rel != "." else f
        if any(part in p for part in EXCLUDE_PARTS):
            continue
        include.append(p)

include.sort()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for p in include:
        z.write(os.path.join(ROOT, p), f"market-research-full-workflow/{p}")

print(f"打包 {len(include)} 个文件 → dist/market-research-full-workflow.skill")
for p in include:
    print("  ", p)