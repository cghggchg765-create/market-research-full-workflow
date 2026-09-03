#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command delivery: validate charts/assets -> assemble -> feishu copy -> upload -> manifest.

强制执行交付前置清单，任何一项缺失即中止，禁止散装/跳步交付。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from chart_manifest import load_state, png_file_name, png_items
from inspection_gate import gate_check

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable


def run(script: str, *args: str) -> bool:
    cmd = [PY, str(SCRIPTS / script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    return proc.returncode == 0


def step(name: str, ok: bool) -> bool:
    print(f"[deliver] {'✅' if ok else '❌'} {name}")
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description="一键交付：校验→组装→飞书版→上传→回读")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--target-words", type=int, default=32000)
    p.add_argument("--title", default="")
    p.add_argument("--identity", choices=("user", "bot"), default="user")
    p.add_argument("--folder-token", default="")
    p.add_argument("--dry-run", action="store_true", help="只跑到上传前，不执行 lark-cli")
    args = p.parse_args()
    run_dir = args.run_dir.resolve()

    # 1) 8 片单片校验
    parts = run_dir / "parts"
    part_ok = True
    if parts.is_dir():
        for f in sorted(parts.glob("*.md")):
            if not run("validate_report.py", "--stage", "part", "--file", str(f)):
                part_ok = False
    else:
        part_ok = False
        print("[deliver] ❌ 缺少 parts/ 目录")
    if not step("8 片单片校验", part_ok):
        return 1

    # 2) 证据索引（缺失则补生成）
    cards = run_dir / "evidence" / "knowledge-cards.md"
    ledger = run_dir / "evidence" / "source-ledger.jsonl"
    index = run_dir / "evidence" / "card-index.json"
    if index.is_file():
        ok = step("card-index.json 已存在", True)
    elif cards.is_file():
        ok = run("card_index.py", "--cards", str(cards),
                 "--ledger", str(ledger), "--out", str(index))
        ok = step("生成 card-index.json", ok)
    else:
        ok = step("card-index.json（缺 knowledge-cards.md）", False)
    if not ok:
        return 1

    # 3) 图表产物与 PNG 检查（清单：chart-manifest.json 优先，兼容旧 specs.json）
    spec_path, spec_ok, spec_err = load_state(run_dir)
    if spec_path is None:
        return 1 if not step("charts/chart-manifest.json（或 specs.json）存在", False) else 1
    if not spec_ok:
        return 1 if not step(spec_err, False) else 1
    png = png_items(run_dir)
    if len(png) < 5:
        return 1 if not step(f"PNG 图表 ≥5（当前 {len(png)}）", False) else 1
    missing_png = []
    for item in png:
        name = png_file_name(item)
        if name and not (run_dir / "charts" / name).is_file():
            missing_png.append(name)
    if missing_png:
        return 1 if not step(f"PNG 文件齐全（缺 {missing_png}）", False) else 1
    step(f"图表产物校验（{len(png)} 张 PNG，清单 {spec_path.name}）", True)
    vis_ok, vis_msg = gate_check(run_dir)
    if not vis_ok:
        print(f"[deliver] ❌ {vis_msg}")
        return 1
    step(f"视觉检查门禁：{vis_msg}", True)

    # 3.5) 板块覆盖检查：7个主体板块必须各有专属图表，防止某章无图只能重复引用
    import json as _json
    import re as _re
    sections = ["一、", "二、", "三、", "四、", "五、", "六、", "七、"]
    try:
        manifest_data = _json.loads(spec_path.read_text(encoding="utf-8"))
        manifest_list = manifest_data.get("specs", manifest_data) if isinstance(manifest_data, dict) else manifest_data
    except Exception:
        manifest_list = []
    covered = set()
    for item in manifest_list:
        pos = item.get("position", "")
        for sec in sections:
            if pos.startswith(sec) or sec in pos[:4]:
                covered.add(sec)
    missing_sections = [s for s in sections if s not in covered]
    if missing_sections:
        return 1 if not step(f"板块覆盖检查：7个主体板块必须各有专属图表（缺失: {missing_sections}）", False) else 1
    step(f"板块覆盖检查：7/7 主体板块均有专属图表", True)

    # 4) 组装（带清单，注入图表索引 + 图号门禁）
    if not run("assemble_report.py", "--parts-dir", str(parts), "--out",
               str(run_dir / "output" / "report.md"), "--target-words", str(args.target_words),
               "--spec", str(spec_path)):
        return 1 if not step("组装与图号门禁", False) else 1
    step("组装与图号门禁", True)

    # 5) 最终整篇校验（含图表硬门禁）
    if not run("validate_report.py", "--stage", "final", "--run-dir", str(run_dir),
               "--target-words", str(args.target_words)):
        return 1 if not step("final 校验", False) else 1
    step("final 校验", True)

    # 6) 飞书推送副本
    feishu = run_dir / "output" / "report.feishu.md"
    if not run("make_feishu_copy.py", "--report", str(run_dir / "output" / "report.md"),
               "--charts-dir", str(run_dir / "charts"), "--out", str(feishu)):
        return 1 if not step("飞书推送副本", False) else 1
    step("飞书推送副本", True)

    # 7) 上传（upload_report 自带交付硬门禁 + 重试 + 回读清单）
    if args.dry_run:
        print("[deliver] --dry-run：已到达上传前，跳过 lark-cli（副本已生成）")
        return 0
    if not run("upload_report.py", "--file", str(feishu), "--title",
               args.title or "行业深度研究报告", "--identity", args.identity,
               "--folder-token", args.folder_token,
               "--manifest", str(run_dir / "delivery.json"),
               "--run-dir", str(run_dir), "--target-words", str(args.target_words)):
        return 1 if not step("飞书上传与回读", False) else 1
    step("飞书上传与回读", True)
    print(f"[deliver] ✅ 交付完成：{run_dir / 'delivery.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())