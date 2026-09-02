#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a structured visual-inspection manifest from generated charts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="登记图表程序检查与视觉检查状态")
    p.add_argument("--charts-dir", type=Path, required=True)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--visual-status", choices=("pending", "passed", "degraded"), default="pending")
    p.add_argument("--notes", default="")
    args = p.parse_args()
    payload = json.loads(args.spec.read_text(encoding="utf-8"))
    specs = payload.get("specs", payload) if isinstance(payload, dict) else payload
    charts = []
    for item in specs:
        if item.get("type") == "mermaid":
            charts.append({"id": item.get("id"), "type": "mermaid", "status": "pending"})
            continue
        name = item.get("display_name") or item.get("filename")
        path = args.charts_dir / name
        charts.append({"id": item.get("id"), "file": name, "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else 0, "status": "pending"})
    result = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "visual_status": args.visual_status, "notes": args.notes, "charts": charts}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[render_visual_check] 登记 {len(charts)} 个图表：{args.out}")
    return 0 if all(x.get("exists", True) for x in charts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
