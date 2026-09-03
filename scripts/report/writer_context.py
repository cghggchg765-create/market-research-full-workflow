#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为每个 Writer 生成完整上下文注入包，从源头避免图号/表号重复和内容重复。

输出：{run_dir}/evidence/writer-context.{NN}.md
包含：全局主线、全局大纲、完整图表清单（按章节分组）、表号预分配、
其他章节摘要、本章证据注入包、本章图号/表号区间。

编排者启动 Writer 前必须运行本脚本，并把输出内容原文粘贴进 Writer prompt。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# 8 个分片与章节标题的映射（与 industry-report-standard.md 一致）
PART_MAP = [
    ("01", "摘要与核心观点", "01-executive-summary.md"),
    ("02", "一、行业定义、规模与生命周期", "02-industry-definition-scale.md"),
    ("03", "二、产业链、利润池与竞争格局", "03-structure-competition.md"),
    ("04", "三、用户分层、需求与付费行为", "04-user-insight.md"),
    ("05", "四、核心驱动力、制约因素与政策环境", "05-drivers-policy.md"),
    ("06", "五、趋势、预期差与三情景推演", "06-trends-opportunities.md"),
    ("07", "六、商业模式、单位经济与落地路径", "07-commercialization-roadmap.md"),
    ("08", "七、风险提示、结论与展望", "08-risk-conclusion-references.md"),
]


def read_file(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"[缺失: {path.name}]"


def extract_chapter_summary(text: str, max_lines: int = 15) -> str:
    """从分片或大纲中提取核心论点摘要（前 N 行非空内容）。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return "\n".join(lines[:max_lines]) if lines else "[无内容]"


def load_chart_manifest(charts_dir: Path) -> list[dict]:
    manifest = charts_dir / "chart-manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("specs", data.get("charts", []))
        return data
    return []


def charts_by_position(charts: list[dict]) -> dict[str, list[dict]]:
    """按 position 字段（章节标题关键词）分组图表。"""
    groups: dict[str, list[dict]] = {}
    for chart in charts:
        pos = chart.get("position", "")
        # 提取章节关键词（position 可能是 "2.2 市场规模" 或 "一、行业定义"）
        key = pos[:4] if pos else "未分配"
        groups.setdefault(key, []).append(chart)
    return groups


def assign_table_numbers(framework: str, parts_dir: Path) -> list[dict]:
    """从 framework.md 和已完成分片中扫描表号，生成全文档表号预分配表。"""
    tables = []
    # 先扫描已完成分片
    for _, _, fname in PART_MAP:
        fpath = parts_dir / fname
        if fpath.is_file():
            text = fpath.read_text(encoding="utf-8")
            for m in re.finditer(r"^(表\d+)\s+(.+)$", text, re.MULTILINE):
                tables.append({"table_no": m.group(1), "title": m.group(2).strip(), "source": fname})
    # 再扫描 framework.md 中的表号规划
    for m in re.finditer(r"(表\d+)\s+(.+)", framework):
        no = m.group(1)
        if not any(t["table_no"] == no for t in tables):
            tables.append({"table_no": no, "title": m.group(2).strip()[:50], "source": "framework规划"})
    return sorted(tables, key=lambda x: int(re.search(r"\d+", x["table_no"]).group()))


def generate_context(run_dir: Path, part_no: str) -> str:
    """为指定分片生成完整上下文注入包。"""
    evidence_dir = run_dir / "evidence"
    analysis_dir = run_dir / "analysis"
    charts_dir = run_dir / "charts"
    parts_dir = run_dir / "parts"

    part_info = next((p for p in PART_MAP if p[0] == part_no), None)
    if not part_info:
        return f"错误: 未知分片编号 {part_no}"

    _, chapter_title, part_file = part_info

    # 1. 全局判断主线
    spine = read_file(analysis_dir / "judgment-spine.md")

    # 2. 全局大纲
    framework = read_file(analysis_dir / "framework.md")

    # 3. 完整图表清单
    charts = load_chart_manifest(charts_dir)
    chart_lines = []
    for c in charts:
        cid = c.get("id", "")
        title = c.get("title", "")
        pos = c.get("position", "")
        display = c.get("display_name", "")
        chart_lines.append(f"- {cid} | {display or title} | 章节: {pos}")
    chart_list = "\n".join(chart_lines) if chart_lines else "[图表清单尚未生成]"

    # 4. 本章图号区间（按章节序号匹配，如"二、"匹配 position 以"二"开头的图表）
    chapter_num = chapter_title.split("、")[0] if "、" in chapter_title else chapter_title[:2]
    my_charts = [c for c in charts if c.get("position", "").startswith(chapter_num) or chapter_num in c.get("position", "")[:4]]
    my_fig_nos = sorted(set(int(re.search(r"\d+", c.get("id", "")).group()) for c in my_charts if re.search(r"\d+", c.get("id", ""))))
    fig_range = f"图{my_fig_nos[0]}-图{my_fig_nos[-1]}" if my_fig_nos else "本章无预分配图表"

    # 5. 表号预分配
    all_tables = assign_table_numbers(framework, parts_dir)
    table_lines = [f"- {t['table_no']} | {t['title']} | 来源: {t['source']}" for t in all_tables]
    table_list = "\n".join(table_lines) if table_lines else "[暂无表号规划]"
    my_tables = [t for t in all_tables if part_file in t.get("source", "")]
    my_table_nos = sorted(set(int(re.search(r"\d+", t["table_no"]).group()) for t in my_tables))
    table_range = f"表{my_table_nos[0]}-表{my_table_nos[-1]}" if my_table_nos else "本章无预分配表格"

    # 6. 其他章节摘要
    other_summaries = []
    for pno, ptitle, pfname in PART_MAP:
        if pno == part_no:
            continue
        fpath = parts_dir / pfname
        if fpath.is_file():
            summary = extract_chapter_summary(fpath.read_text(encoding="utf-8"), 8)
        else:
            # 从 framework.md 中提取该章节的规划
            summary = f"[该分片尚未完成，以下为框架规划]\n{extract_chapter_summary(framework, 10)}"
        other_summaries.append(f"### {pno} {ptitle}\n{summary}")
    other_summary_text = "\n\n".join(other_summaries)

    # 7. 本章证据注入包
    cards_file = evidence_dir / f"cards.{part_no}.md"
    cards = read_file(cards_file)

    # 组装
    context = f"""# Writer 上下文注入包 — 分片 {part_no} {chapter_title}

> **本文件由 writer_context.py 自动生成，编排者必须将以下全部内容原文粘贴进 Writer prompt，不得删减。**

---

## 一、全局判断主线（全文统一，不得偏离）

{spine}

---

## 二、全局大纲（所有章节结构，写作前必须通读）

{framework}

---

## 三、完整图表清单（全文档所有图，只能引用分配给本章的图号）

{chart_list}

**本章允许使用的图号：{fig_range}**
⚠️ 严禁引用其他章节的图号，严禁自行新增图号，严禁重复插入同一张图。

---

## 四、表号预分配（全文档所有表）

{table_list}

**本章允许使用的表号：{table_range}**
⚠️ 严禁使用其他章节的表号，严禁自行新增表号。

---

## 五、其他章节核心论点摘要（防止内容重复和论点冲突）

{other_summary_text}

⚠️ 写作前先对照以上摘要，确认本章不重复已有论述、不与其他章节数据矛盾。

---

## 六、本章证据注入包（卡片原文，80% 论点必须基于此）

{cards}

---

## 七、写作纪律

1. 图号只能用 {fig_range}，表号只能用 {table_range}
2. 每个数据点必须配一句解读（意味着什么、与哪个指标印证、决策含义）
3. **严禁暴露内部研究编号和分级**（最高优先级，违反即打回）：
   - ❌ 错误写法（资料来源行）：`资料来源：基于K-user-02（中新经纬，A级）、K-user-05（三农雷哥，B级）等知识卡片综合整理`
   - ❌ 错误写法（正文）：`据K01卡片显示`、`K03数据表明`、`（A级来源）`
   - ✅ 正确写法（资料来源行）：`资料来源：中新经纬、三农雷哥、农业一二事等公开报道，本研究整理`
   - ✅ 正确写法（正文引用）：`据中新经纬2026年报道`、`三农雷哥调研显示`
   - 规则：正文和资料来源行**只能出现来源机构名称+年份**，不得出现 K-user-xx、K01、K02、（A级）、（B级）、（C级）、知识卡片、证据台账、source_id、card_id 等任何内部研究过程标识
4. 不得使用【事实】【推断】等内部标签，不得使用 **关键词**：内容 句式
5. 正文禁用 -/*/• 项目列表，改用有序 1./① 或自然段
6. 缺证据时写"公开信息有限"，不得编造数据
"""
    return context


def main() -> int:
    p = argparse.ArgumentParser(description="为每个 Writer 生成完整上下文注入包")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--part", choices=[p[0] for p in PART_MAP], help="指定分片编号（缺省则生成全部8个）")
    args = p.parse_args()

    out_dir = args.run_dir / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = [args.part] if args.part else [p[0] for p in PART_MAP]
    for part_no in parts:
        context = generate_context(args.run_dir, part_no)
        out_file = out_dir / f"writer-context.{part_no}.md"
        out_file.write_text(context, encoding="utf-8")
        print(f"[writer_context] 已生成: {out_file}（{len(context)} 字符）")

    print("\n[writer_context] ✅ 全部上下文注入包已生成。编排者启动 Writer 前必须将对应文件内容原文粘贴进 prompt。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
