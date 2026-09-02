#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert local absolute-image Markdown into a validated Feishu copy."""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path

# Supports Markdown destinations wrapped in <...>, including parentheses in filenames.
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<dest><[^>]+>|[^\n]*?\.(?:png|jpg|jpeg|gif|svg)(?:\?[^)]*)?)\)", re.IGNORECASE)


def destination_path(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1]
    return raw


def convert(report_path: Path, charts_dir: Path, out_path: Path) -> tuple[int, int]:
    text = report_path.read_text(encoding="utf-8")
    missing: list[str] = []
    converted: list[str] = []

    def repl(match: re.Match[str]) -> str:
        alt = match.group("alt")
        raw = destination_path(match.group("dest"))
        if raw.startswith("@"):
            return match.group(0)
        # Resolve both Windows and POSIX separators without treating drive colon as syntax.
        base = raw.replace("\\", "/").rsplit("/", 1)[-1]
        base = base.split("?", 1)[0]
        src = charts_dir / base
        if not src.is_file():
            missing.append(base)
            return match.group(0)
        target = f"@./charts/{base}"
        if any(c in base for c in " ()（）"):
            target = f"<{target}>"
        converted.append(base)
        return f"![{alt}]({target})"

    out = IMAGE_RE.sub(repl, text)
    if missing:
        print("[ERROR] 图片文件不存在，副本未生成：", file=sys.stderr)
        for name in sorted(set(missing)):
            print(f"  - {name}", file=sys.stderr)
        return 1, 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    print(f"[OK] 飞书推送副本已生成: {out_path}")
    print(f"  图片引用转换: {len(converted)} 张（目标 @./charts/）")
    print(f"  Mermaid 块: {out.count('```mermaid')} 个")
    return 0, len(converted)


def main() -> int:
    p = argparse.ArgumentParser(description="生成并校验飞书 Markdown 推送副本")
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--charts-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    code, _ = convert(args.report, args.charts_dir, args.out)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
