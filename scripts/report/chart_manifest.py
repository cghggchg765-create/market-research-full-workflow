#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""charts 产物清单统一解析（单一事实源）。

可视化 Agent（chart-coder）产出的规范清单为 `{run_dir}/charts/chart-manifest.json`；
历史运行目录可能只留下旧的 `charts/specs.json`。本模块对所有读取方提供一致入口：

- 优先 `chart-manifest.json`，缺失时回退 `specs.json`；
- 两种结构都兼容 `{"specs": [...]}` 包装与裸数组；
- 图号只分配给 PNG：`type=mermaid` 的条目以代码块呈现，不占图号、不参与门禁。
"""
from __future__ import annotations

import json
from pathlib import Path

CANONICAL = "charts/chart-manifest.json"
LEGACY = "charts/specs.json"


def resolve_spec(run_dir: Path) -> Path | None:
    """返回实际存在的清单文件路径；两者都缺时返回 None。"""
    canonical = run_dir / CANONICAL
    if canonical.is_file():
        return canonical
    legacy = run_dir / LEGACY
    return legacy if legacy.is_file() else None


def load_state(run_dir: Path) -> tuple[Path | None, bool, str]:
    """探测清单状态：(路径, 是否可解析, 错误说明)。

    路径为 None → 清单缺失；可解析=False → 文件不是合法 JSON（err 含原因）。
    """
    path = resolve_spec(run_dir)
    if path is None:
        return None, False, "missing"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return path, False, f"{path.name} 不是合法 JSON: {exc}"
    return path, True, ""


def load_items(run_dir: Path) -> list[dict]:
    """返回全部图表条目；缺文件/非法 JSON 时返回 []。"""
    path = resolve_spec(run_dir)
    if path is None:
        return []
    return load_items_at(path)


def load_items_at(path: Path) -> list[dict]:
    """按给定清单文件路径读取条目（供 assemble 等已知路径的调用方）；异常返回 []。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    items = payload.get("specs", payload) if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


def png_items(run_dir: Path) -> list[dict]:
    """排除 mermaid 后、参与图号分配与硬门禁的 PNG 条目。"""
    return [item for item in load_items(run_dir) if item.get("type") != "mermaid"]


def png_file_name(item: dict) -> str:
    """条目对应的 PNG 文件名（display_name 优先，兼容旧 filename 键）。"""
    return str(item.get("display_name") or item.get("filename") or "")
