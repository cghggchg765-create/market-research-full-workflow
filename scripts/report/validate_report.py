#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate a standard industry report and its production artifacts."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from forbidden_rules import check_forbidden, labelled_list_ratio

PARTS = (
    "01-executive-summary.md", "02-industry-definition-scale.md", "03-structure-competition.md",
    "04-user-insight.md", "05-drivers-policy.md", "06-trends-opportunities.md",
    "07-commercialization-roadmap.md", "08-risk-conclusion-references.md",
)
SECTIONS = (
    "## 核心观点", "## 可视化图表索引",
    "## 一、行业定义、规模测算与历史坐标",
    "## 二、行业结构、产业链与竞争格局",
    "## 三、用户需求与行为洞察",
    "## 四、核心驱动力、制约因素与政策环境",
    "## 五、趋势研判与结构性机会",
    "## 六、商业化路径、盈利质量与落地建议",
    "## 七、风险提示、结论与展望",
    "## 参考文献", "## 附录：数据来源、方法与术语",
)


def count_words(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text)) + len(re.findall(r"[A-Za-z0-9]+", text))


def check_part(name: str, text: str) -> list[str]:
    issues = []
    if not text.strip():
        issues.append("分片为空")
    issues.extend(f"{name}：{msg}" for msg in check_forbidden(text))
    ratio = labelled_list_ratio(text)
    if ratio > 0.45:
        issues.append(f"{name}：行首 `-` 列表占比 {ratio:.0%}，正文过度清单化，应改为自然段落")
    return issues


def validate_part_file(file_path: Path) -> list[str]:
    """单片即时校验：写作完成后立即执行，未通过不得进入组装。"""
    if not file_path.is_file():
        return [f"文件不存在: {file_path}"]
    name = file_path.name
    text = file_path.read_text(encoding="utf-8")
    issues = check_part(name, text)
    if name not in PARTS:
        issues.append(f"不是 canonical 分片文件名: {name}")
    return issues


def validate(run_dir: Path, target_words: int) -> list[str]:
    issues: list[str] = []
    parts = run_dir / "parts"
    for name in PARTS:
        path = parts / name
        if not path.is_file():
            issues.append(f"缺少分片: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        issues.extend(check_part(name, text))

    # 证据目录与卡片是标准产物；不允许只交报告而丢失可追溯链。
    for required in (
        run_dir / "evidence" / "knowledge-cards.industry.md",
        run_dir / "evidence" / "knowledge-cards.competitor.md",
        run_dir / "evidence" / "knowledge-cards.user.md",
        run_dir / "evidence" / "source-ledger.jsonl",
        run_dir / "evidence" / "knowledge-cards.md",
        run_dir / "evidence" / "card-index.json",
        run_dir / "analysis" / "judgment-spine.md",
    ):
        if not required.is_file():
            issues.append(f"缺少可追溯产物: {required.relative_to(run_dir)}")

    report = run_dir / "output" / "report.md"
    if not report.is_file():
        issues.append("缺少 output/report.md")
        return issues
    text = report.read_text(encoding="utf-8")
    if len(re.findall(r"^#\s+", text, re.M)) != 1:
        issues.append("最终报告 H1 数量不是 1")
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺少标准章节: {section}")
    if count_words(text) < int(target_words * 0.88):
        issues.append(f"正文净字数不足: {count_words(text)} < {int(target_words * 0.88)}")
    if text.count("### 回扣主线") < 5:
        issues.append("主体板块回扣主线数量不足")
    if text.count("资料来源：") < 5:
        issues.append("资料来源行不足")
    if re.search(r"\[(\d{1,3})\]", text):
        issues.append("正文残留 [n] 编号引用，应使用作者/机构+年份")
    if re.search(r"【(?:事实|推断|结论|备注|数据)】", text):
        issues.append("最终报告残留内部标签词")
    if re.search(r"^\s*\*\s+", text, re.M):
        issues.append("最终报告存在星号无序列表")

    # 图表产物硬门禁：正文必须实际引用图表，且索引/规格/视觉检查记录齐全
    spec_path = run_dir / "charts" / "specs.json"
    if not spec_path.is_file():
        issues.append("缺少 charts/specs.json（可视化被跳过？）")
    else:
        try:
            payload = json.loads(spec_path.read_text(encoding="utf-8"))
            specs = payload.get("specs", payload) if isinstance(payload, dict) else payload
            png_count = sum(1 for item in specs if item.get("type") != "mermaid")
            if png_count < 5:
                issues.append(f"PNG 图表不足 5 张，当前 {png_count} 张")
        except json.JSONDecodeError:
            issues.append("charts/specs.json 不是合法 JSON")
    if "## 可视化图表索引" not in text:
        issues.append("最终报告缺少「可视化图表索引」节")
    figure_refs = re.findall(r"!\[图(\d+)", text)
    if figure_refs:
        nums = sorted({int(n) for n in figure_refs})
        missing = [i for i in range(1, nums[-1] + 1) if i not in nums]
        if missing:
            issues.append(f"正文图号缺失: {missing}（当前图号 {nums}）")
    if not run_dir.joinpath("charts", "inspection.json").is_file():
        issues.append("缺少 charts/inspection.json（图表视觉检查未执行）")

    ledger = run_dir / "evidence" / "source-ledger.jsonl"
    if ledger.is_file():
        for line_no, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    issues.append(f"证据台账第 {line_no} 行不是 JSON")
                    continue
                for key in ("source_id", "card_id", "source_value", "unit", "definition", "base_period"):
                    if item.get(key) in (None, ""):
                        issues.append(f"证据台账第 {line_no} 行缺少 {key}")
    return issues


def main() -> int:
    p = argparse.ArgumentParser(description="校验标准行业报告（part 单片 / final 全量）")
    p.add_argument("--stage", choices=("part", "final"), default="final")
    p.add_argument("--file", type=Path, help="--stage part 时校验的单片文件")
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--target-words", type=int, default=32000)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if args.stage == "part":
        if not args.file:
            p.error("--stage part 需要 --file")
        issues = validate_part_file(args.file)
    else:
        if not args.run_dir:
            p.error("--stage final 需要 --run-dir")
        issues = validate(args.run_dir, args.target_words)
    result = {"ok": not issues, "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else ("[validate_report] ✅ 通过" if not issues else "\n".join("[validate_report] ✗ " + x for x in issues)))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
