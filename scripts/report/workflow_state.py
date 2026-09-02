#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atomic .workflow.json state management for resumable report runs."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "updated_at": now(), "steps": {}, "artifacts": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # 损坏的状态文件：保留现场，重置为初始状态并标记损坏
        return {"version": 1, "updated_at": now(), "corrupt": True,
                "steps": {}, "artifacts": {}}


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def update(path: Path, step: str, status: str, **fields: object) -> dict:
    state = load(path)
    entry = state.setdefault("steps", {}).setdefault(step, {})
    entry.update(fields, status=status, updated_at=now())
    save(path, state)
    return state


def main() -> int:
    p = argparse.ArgumentParser(description="更新或查看报告工作流状态")
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--step")
    p.add_argument("--status", choices=("pending", "running", "done", "failed", "degraded"))
    p.add_argument("--retries", type=int)
    p.add_argument("--artifact")
    p.add_argument("--value")
    p.add_argument("--show", action="store_true")
    args = p.parse_args()
    if args.show:
        print(json.dumps(load(args.state), ensure_ascii=False, indent=2))
        return 0
    if not args.step or not args.status:
        p.error("更新状态需要 --step 和 --status")
    fields = {}
    if args.retries is not None:
        fields["retries"] = args.retries
    if args.artifact:
        fields["artifact"] = args.artifact
    if args.value:
        fields["value"] = args.value
    update(args.state, args.step, args.status, **fields)
    print(f"[workflow_state] {args.step}={args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
