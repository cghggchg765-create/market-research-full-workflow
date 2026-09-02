#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evidence-ledger validation and summary for industry-report runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = ("source_id", "title", "author_or_org", "year", "url", "source_level", "source_value", "unit", "definition", "base_period", "card_id")
LEVELS = {"A", "B", "C"}


def read_records(path: Path) -> list[dict]:
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {line_no} 行不是合法 JSON: {exc}") from exc
        item["_line"] = line_no
        records.append(item)
    return records


def validate(records: list[dict]) -> list[str]:
    issues = []
    seen = set()
    for item in records:
        line = item["_line"]
        for key in REQUIRED:
            if key not in item or item[key] in (None, ""):
                issues.append(f"第 {line} 行缺少 {key}")
        source_id = item.get("source_id")
        if source_id in seen:
            issues.append(f"第 {line} 行 source_id 重复: {source_id}")
        seen.add(source_id)
        if item.get("source_level") not in LEVELS:
            issues.append(f"第 {line} 行 source_level 必须为 A/B/C")
        if not isinstance(item.get("year"), int):
            issues.append(f"第 {line} 行 year 必须为整数")
        url = item.get("url", "")
        if url and not url.startswith(("http://", "https://", "doi:")):
            issues.append(f"第 {line} 行 URL/DOI 格式异常")
    return issues


def main() -> int:
    p = argparse.ArgumentParser(description="校验证据台账并输出摘要")
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--summary", type=Path)
    args = p.parse_args()
    records = read_records(args.ledger)
    issues = validate(records)
    levels = {level: sum(x.get("source_level") == level for x in records) for level in sorted(LEVELS)}
    cards = len({x.get("card_id") for x in records if x.get("card_id")})
    summary = {"records": len(records), "cards": cards, "levels": levels, "issues": issues}
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
