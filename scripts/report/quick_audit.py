#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot audit of a run directory: gates, figures, evidence, cohesion hints.

诊断工具（不改动任何产物）。编排者可在任意阶段运行查看健康度。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from chart_manifest import load_state, png_file_name, png_items
from forbidden_rules import check_figure_table_support, check_forbidden, labelled_list_ratio
from inspection_gate import gate_check
from validate_report import PARTS, SECTIONS, validate_part_file, count_words


def audit(run_dir: Path, target_words: int) -> dict:
    report = {"run_dir": str(run_dir), "target_words": target_words, "sections": {}, "issues": []}

    # 1) parts
    parts_dir = run_dir / "parts"
    part_issues = []
    for name in PARTS:
        path = parts_dir / name
        if not path.is_file():
            part_issues.append(f"缺少分片: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        part_issues.extend(check_part_file_text(name, text))
        report["sections"][name] = {"words": count_words(text)}
    report["parts_ok"] = not part_issues
    report["issues"].extend(part_issues)

    # 2) 证据产物
    for rel in ("evidence/source-ledger.jsonl", "evidence/knowledge-cards.md",
                "evidence/card-index.json", "analysis/judgment-spine.md"):
        if not (run_dir / rel).is_file():
            report["issues"].append(f"缺少 {rel}")

    # 3) 图表产物与图文配套（清单：chart-manifest.json 优先，兼容旧 specs.json）
    spec_path, spec_ok, spec_err = load_state(run_dir)
    if spec_path is None:
        report["issues"].append("缺少 charts/chart-manifest.json（或旧 charts/specs.json）")
    elif not spec_ok:
        report["issues"].append(spec_err)
    else:
        png = png_items(run_dir)
        report["chart_count"] = len(png)
        if len(png) < 5:
            report["issues"].append(f"PNG 图表不足 5 张：{len(png)}")
        missing = []
        for item in png:
            name = png_file_name(item)
            if name and not (run_dir / "charts" / name).is_file():
                missing.append(name)
        if missing:
            report["issues"].append(f"PNG 文件缺失: {missing}")
    vis_ok, vis_msg = gate_check(run_dir)
    if not vis_ok:
        report["issues"].append(vis_msg)

    report_md = run_dir / "output" / "report.md"
    if report_md.is_file():
        text = report_md.read_text(encoding="utf-8")
        report["report_words"] = count_words(text)
        report["issues"].extend(f"图文配套：{m}" for m in check_figure_table_support(text))
        for section in SECTIONS:
            if section not in text:
                report["issues"].append(f"最终报告缺少章节: {section}")

    # 4) 数据-正文协同提示（供 fact-checker / quality 使用）
    ledger = run_dir / "evidence" / "source-ledger.jsonl"
    if ledger.is_file() and report_md.is_file():
        rows = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        body = report_md.read_text(encoding="utf-8")
        year_ref = re.findall(r"[（(][^）)]*20\d{2}[）)]", body)
        report["cohesion"] = {
            "ledger_rows": len(rows),
            "parenthetical_year_refs": len(year_ref),
            "hint": "正文含（机构，年份）引用但台账行数偏多，说明部分证据未进正文" if year_ref and len(rows) > len(year_ref) * 3 else "正常",
        }
    else:
        report["cohesion"] = {"note": "缺台账或报告，无法评估数据-正文协同"}
    return report


def check_part_file_text(name: str, text: str) -> list[str]:
    issues = []
    issues.extend(f"{name}：{m}" for m in check_forbidden(text))
    return issues


def main() -> int:
    p = argparse.ArgumentParser(description="一键诊断 run_dir 健康度")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--target-words", type=int, default=32000)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    result = audit(args.run_dir, args.target_words)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"[audit] run_dir={result['run_dir']}")
    if result.get("parts_ok"):
        print("[audit] ✅ 分片禁则/结构通过")
    if not result["issues"]:
        print("[audit] ✅ 未发现问题")
    for issue in result["issues"]:
        print("  ✗ " + issue)
    if "cohesion" in result:
        print(f"[audit] 协同提示：{result['cohesion']}")
    return 1 if result["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())