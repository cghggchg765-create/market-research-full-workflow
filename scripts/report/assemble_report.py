#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the canonical eight-part industry report with hard quality gates."""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import tempfile
from pathlib import Path

from chart_manifest import resolve_spec
from forbidden_rules import check_forbidden, labelled_list_ratio

PARTS = (
    "01-executive-summary.md",
    "02-industry-definition-scale.md",
    "03-structure-competition.md",
    "04-user-insight.md",
    "05-drivers-policy.md",
    "06-trends-opportunities.md",
    "07-commercialization-roadmap.md",
    "08-risk-conclusion-references.md",
)
TOLERANCE = 0.12
CITATION_RE = re.compile(r"\[(\d{1,3})\]")
FIGURE_RE = re.compile(r"!\[图(\d+)[^\]]*\]\(")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?:<[^>]+>|[^)]+)\)")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def word_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text)) + len(re.findall(r"[A-Za-z0-9]+", text))


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def check_part_structure(contents: list[tuple[str, str]]) -> list[str]:
    issues: list[str] = []
    for index, (name, text) in enumerate(contents):
        if not text.strip():
            issues.append(f"[缺失] {name} 为空")
        for msg in check_forbidden(text):
            issues.append(f"[禁则] {name}: {msg}")
        h1 = re.findall(r"^#\s+[^#].*$", text, re.MULTILINE)
        if index == 0 and len(h1) != 1:
            issues.append(f"[结构] {name} 应有且仅有一个 H1，当前 {len(h1)} 个")
        if index > 0 and h1:
            issues.append(f"[结构] {name} 不应包含 H1")
        if index > 0 and "### 回扣主线" not in text and index < 7:
            issues.append(f"[结构] {name} 缺少 ### 回扣主线")
        if not re.search(r"^###\s+（[一二三四五六七八九十]+）", text, re.MULTILINE) and index not in (0, 7):
            issues.append(f"[结构] {name} 缺少中文序号二级小节（### （一）…）")
        if "**" in text and re.search(r"\*\*[^*：]{1,30}\*\*：", text):
            issues.append(f"[格式] {name} 存在“加粗关键词+冒号”句式")
        if re.search(r"^\s*\*\s+", text, re.MULTILINE):
            issues.append(f"[格式] {name} 使用星号无序列表，应改为短横线")
        if re.search(r"^\s*【(?:事实|推断|结论|备注|数据)】", text, re.MULTILINE):
            issues.append(f"[格式] {name} 含内部标签词，应改为自然表述")
    return issues


def check_markdown(texts: list[tuple[str, str]]) -> list[str]:
    issues: list[str] = []
    for name, text in texts:
        if text.count("```") % 2:
            issues.append(f"[语法] {name} 代码围栏未闭合")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not (stripped.startswith("|") and set(stripped.replace("|", "").replace("-", "").replace(":", "").strip()) == set()):
                continue
            expected = stripped.count("|") - 1
            for j in range(i + 1, min(i + 12, len(lines))):
                row = lines[j].strip()
                if not row.startswith("|"):
                    break
                actual = row.count("|") - 1
                if actual != expected:
                    issues.append(f"[语法] {name} 第 {j + 1} 行表格列数 {actual} ≠ {expected}")
                    break
    return issues


def check_citations(texts: list[tuple[str, str]]) -> list[str]:
    issues: list[str] = []
    for name, text in texts:
        clean = re.sub(r"```.*?```", "", text, flags=re.S)
        clean = MARKDOWN_IMAGE_RE.sub("", clean)
        if CITATION_RE.search(clean):
            issues.append(f"[引用] {name} 残留 [n] 编号制引用，应使用作者/机构+年份")
    return issues


def check_figures(texts: list[tuple[str, str]], spec_path: Path | None) -> tuple[list[str], list[dict]]:
    issues: list[str] = []
    refs: list[int] = []
    for _, text in texts:
        refs.extend(int(x) for x in FIGURE_RE.findall(text))
    if spec_path and spec_path.exists():
        payload = json.loads(spec_path.read_text(encoding="utf-8"))
        specs = payload.get("specs", payload) if isinstance(payload, dict) else payload
        # 图号只分配给 PNG：mermaid 以代码块呈现，不占图号
        expected = list(range(1, sum(1 for item in specs if item.get("type") != "mermaid") + 1))
        if sorted(set(refs)) != expected:
            issues.append(f"[图表] 正文图号 {sorted(set(refs))} 与规格 PNG 图号 {expected} 不一致")
    if refs:
        missing = [i for i in range(1, max(refs) + 1) if i not in refs]
        if missing:
            issues.append(f"[图表] 图号缺失: {missing}")
    return issues, [{"figure": n} for n in refs]


def chart_index(spec_path: Path | None) -> str:
    if not spec_path or not spec_path.exists():
        return ""
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    specs = payload.get("specs", payload) if isinstance(payload, dict) else payload
    rows = ["## 可视化图表索引", "", "| 图号 | 图表名称 | 对应章节 | 交付文件 |", "|---|---|---|---|"]
    png_no = 0
    for item in specs:
        if item.get("type") == "mermaid":
            continue  # 流程类图不占图号，避免索引表与正文学号不一致（幽灵图号）
        png_no += 1
        name = item.get("display_name") or item.get("filename", "")
        rows.append(f"| 图{png_no} | {item.get('title', '')} | {item.get('position', '')} | {name} |")
    if png_no == 0:
        return ""
    return "\n".join(rows) + "\n"


def assemble(parts_dir: Path, out: Path, target_words: int, spec: Path | None) -> int:
    missing = [name for name in PARTS if not (parts_dir / name).is_file()]
    if missing:
        print("[assemble] 缺少分片: " + ", ".join(missing))
        return 1
    if spec is None:
        # 未显式传 --spec 时，按 {run_dir}/parts 约定从上级目录探测图表清单
        spec = resolve_spec(parts_dir.parent)
    contents = [(name, read_text(parts_dir / name).strip()) for name in PARTS]
    issues = check_part_structure(contents) + check_markdown(contents) + check_citations(contents)
    figure_issues, refs = check_figures(contents, spec)
    issues.extend(figure_issues)
    body = "\n\n".join(text for _, text in contents) + "\n"
    index = chart_index(spec)
    if index:
        first, rest = contents[0][1], "\n\n".join(text for _, text in contents[1:])
        body = first + "\n\n" + index + "\n" + rest + "\n"
    issues.extend(f"图文配套：{msg}" for msg in check_figure_table_support(body))
    count = word_count(body)
    if count < int(target_words * (1 - TOLERANCE)):
        issues.append(f"[字数] {count} < 下限 {int(target_words * (1 - TOLERANCE))}")
    atomic_write(out, body)
    print("[assemble] 分片字数：" + ", ".join(f"{n}={word_count(t)}" for n, t in contents))
    print(f"[assemble] 正文净字数={count}，目标={target_words}，图表引用={len(refs)}")
    if issues:
        for issue in issues:
            print("  ✗ " + issue)
        return 1
    print(f"[assemble] ✅ 组装通过: {out}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="组装并校验标准行业报告八分片")
    p.add_argument("--parts-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--target-words", type=int, default=32000)
    p.add_argument("--spec", type=Path)
    args = p.parse_args()
    return assemble(args.parts_dir, args.out, args.target_words, args.spec)


if __name__ == "__main__":
    raise SystemExit(main())
