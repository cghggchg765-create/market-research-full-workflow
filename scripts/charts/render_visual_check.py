#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登记图表检查状态清单（inspection.json 的读写入口）。

根级 `visual_status` 为门禁权威字段（pending/passed/degraded）：
- 图表编码完成后登记：默认 pending（仅机器侧程序检查完成）；
- 视觉模型 Read 逐张确认后（或人工对照拼版图确认后）重新登记为 passed；
- 确因数据不足降级时登记为 degraded，且必须提供 notes 说明原因。

再次运行时按 --chart "id:status" 可逐图更新状态；未指定的图表保留旧状态（幂等）。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="登记/更新图表视觉检查状态清单")
    p.add_argument("--charts-dir", type=Path, required=True)
    p.add_argument("--spec", type=Path, required=True, help="图表清单（chart-manifest.json 或 specs.json）")
    p.add_argument("--out", type=Path, required=True, help="输出 inspection.json 路径")
    p.add_argument("--visual-status", choices=("pending", "passed", "degraded"),
                   help="根视觉状态（缺省保留旧值，首次登记默认 pending）")
    p.add_argument("--capability", choices=("visual", "unavailable", "manual"),
                   help="检查通道：visual=模型可读图；unavailable=模型无视觉能力；manual=人工核验（缺省保留旧值）")
    p.add_argument("--chart", action="append", default=[], metavar="id:status",
                   help="逐图状态，如 chart-01:passed（可多次）")
    p.add_argument("--notes", default="", help="备注（degraded 时必填缺图/降级原因；缺省保留旧值）")
    args = p.parse_args()

    payload = json.loads(args.spec.read_text(encoding="utf-8"))
    specs = payload.get("specs", payload) if isinstance(payload, dict) else payload
    chart_updates = {}
    for pair in args.chart:
        cid, _, st = pair.partition(":")
        if st not in ("pending", "passed", "degraded"):
            p.error(f"--chart 状态非法: {pair!r}（应为 id:passed/degraded/pending）")
        chart_updates[cid] = st

    # 已存在的清单：根状态与未指定图表的历史状态保留（幂等更新）
    old_root: dict = {}
    old_map = {}
    if args.out.is_file():
        try:
            old_payload = json.loads(args.out.read_text(encoding="utf-8"))
            old_root = old_payload
            old_map = {c.get("id"): c for c in old_payload.get("charts", []) if c.get("id")}
        except json.JSONDecodeError:
            pass
    visual_status = args.visual_status or old_root.get("visual_status", "pending")
    capability = args.capability or old_root.get("visual_capability", "visual")
    notes = args.notes or old_root.get("notes", "")

    charts = []
    for item in specs:
        cid = item.get("id")
        if item.get("type") == "mermaid":
            charts.append({"id": cid, "type": "mermaid",
                           "status": chart_updates.get(cid, old_map.get(cid, {}).get("status", "pending"))})
            continue
        name = item.get("display_name") or item.get("filename")
        path = args.charts_dir / name
        prev = old_map.get(cid, {})
        status = chart_updates.get(cid, prev.get("status", "pending"))
        charts.append({
            "id": cid, "file": name, "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
            "status": status,
            "note": prev.get("note", ""),
        })
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "visual_status": visual_status,
        "visual_capability": capability,
        "notes": notes,
        "charts": charts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[render_visual_check] 登记 {len(charts)} 个图表：{args.out}（visual_status={visual_status}，capability={capability}）")
    return 0 if all(x.get("exists", True) for x in charts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
