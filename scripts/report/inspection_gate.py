#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉检查门禁统一判定（validate/deliver/quick_audit 共用）。

inspection.json 权威字段为根级 `visual_status`：
- pending   → 仅登记/初始状态，视觉检查未确认 → 门禁拦截
- passed    → 视觉检查（模型 Read 或人工）已确认 → 放行
- degraded  → 存在缺图原因（notes 非空，编排者已确认降级）→ 放行并提示

人工/视觉模型确认方式：编辑 `charts/inspection.json` 根 `visual_status` 为
`passed`（或运行 `render_visual_check.py --visual-status passed` 重新登记）。
"""
from __future__ import annotations

import json
from pathlib import Path

INSPECTION_REL = Path("charts") / "inspection.json"


def load_inspection(run_dir: Path) -> tuple[Path | None, dict | None, str]:
    """返回 (inspection 路径, 内容 dict, 错误说明)；缺文件/非法 JSON 时内容为 None。"""
    path = run_dir / INSPECTION_REL
    if not path.is_file():
        return path, None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return path, None, f"{path.name} 不是合法 JSON: {exc}"
    return path, payload, ""


def gate_check(run_dir: Path) -> tuple[bool, str]:
    """视觉门禁：通过返回 (True, 说明)；否则返回 (False, 拦截原因)。"""
    _, payload, err = load_inspection(run_dir)
    if payload is None:
        return False, f"缺少 charts/inspection.json（{err}）：视觉检查必须执行并落盘"
    status = payload.get("visual_status", "pending")
    notes = str(payload.get("notes") or "")
    if status == "passed":
        return True, "视觉检查已确认（visual_status=passed）"
    if status == "degraded":
        if not notes.strip():
            return False, "inspection.json visual_status=degraded 但 notes 为空：必须记录缺图/降级原因"
        return True, f"视觉检查降级（visual_status=degraded，notes={notes[:60]!r}）"
    return False, f"inspection.json visual_status={status!r}：视觉检查未确认，禁止宣称通过"
