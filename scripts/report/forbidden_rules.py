#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared Markdown/expression forbidden-rule checks for parts and final report."""
from __future__ import annotations

import re
from collections import Counter

# 常见模板化标签词：单独以 `**词**：` 或行首 `词：` 出现即视为清单化写作
LABEL_WORDS = (
    "核心命题", "核心判断", "事件描述", "触发逻辑", "量化影响", "受影响环节",
    "受益环节", "承压端", "受益端", "时间表与验证信号", "验证信号", "缓解动作",
    "关键发现", "关键数据", "深层逻辑", "我们构建", "我们设计", "综上",
)
LABEL_PATTERN_BOLD = re.compile(r"\*\*(?:[^*：]{0,20})?(" + "|".join(LABEL_WORDS) + r")\*\*：")
LABEL_PATTERN_PLAIN = re.compile(r"^\s*(" + "|".join(LABEL_WORDS) + r")[：:](?=\D)", re.MULTILINE)
NUMERIC_SECTION = re.compile(r"^###\s+\d+(?:\.\d+)*\s", re.MULTILINE)
# 正文禁止行首 `-` / `*` / `•` 项目列表（用户规范：itemize 不用星号也不用短横线）
DASH_STAR_BULLET = re.compile(r"^\s*(?:-|\*|•|◦|·)\s+\S", re.MULTILINE)
BULLET_DOT = re.compile(r"^\s*•\s+", re.MULTILINE)
TAG_BRACKET = re.compile(r"^\s*【(?:事实|推断|结论|备注|数据|来源)】", re.MULTILINE)
BOLD_KEYWORD = re.compile(r"\*\*[^*：]{1,30}\*\*：")
# 伪标题：正文普通行以  `1.1 标题文字` / `（一）标题文字` / `一、标题文字` 开头（≠ Markdown 标题，≠ 合法有序列表 `1. 动作`）
# 内部知识卡片编号：禁止在正文中出现 K-user-01、K-industry-02、K01 等内部研究编号
INTERNAL_CARD_ID = re.compile(r"K-[a-z]+-\d+|K\d{2,}", re.IGNORECASE)
# 证据等级标签：禁止在正文中出现（A级/B级/C级）等内部证据分级术语
EVIDENCE_LEVEL = re.compile(r"[（(][^）)]*[ABC]\s*级[^）)]*[）)]")

FAKE_HEADING = re.compile(
    r"^\s*(?:\d+\.\d+(?:\.\d+)*|（[一二三四五六七八九十]+）|[一二三四五六七八九十]+、)\s*\S",
    re.MULTILINE,
)


def _strip_fences(text: str) -> str:
    """剥离代码块内容，避免把 mermaid/公式内的 `-` 误判为列表。"""
    return re.sub(r"```.*?```", "", text, flags=re.S)


def check_forbidden(text: str) -> list[str]:
    """返回违反表达禁则的问题列表；空列表表示通过。"""
    issues = []
    prose = _strip_fences(text)
    if DASH_STAR_BULLET.search(prose):
        issues.append("正文出现行首 `-`/`*`/`•` 项目列表：正文一律禁用这些项目编号，要点改用有序 `1.`/`①` 或自然段")
    if BULLET_DOT.search(text):
        issues.append("项目编号使用圆点 `•`，应改为有序 `1.`/`①` 或自然段（正文禁用一切 `-`/`*`/`•` 项目编号）")
    if TAG_BRACKET.search(text):
        issues.append("存在【事实】【推断】等方括号内部标签词")
    if BOLD_KEYWORD.search(text):
        issues.append("存在「**加粗关键词**：内容」句式（如 `**事件描述**：`），应改为自然段")
    if LABEL_PATTERN_BOLD.search(text):
        issues.append("存在模板化标签句式：`**" + "或**：".join(LABEL_WORDS[:3]) + "**：` 类（如 事件描述/触发逻辑/量化影响），应改为自然论述")
    if LABEL_PATTERN_PLAIN.search(text) and not LABEL_PATTERN_BOLD.search(text):
        issues.append("存在行首模板标签词（无加粗）：`事件描述：`/`量化影响：` 类，应改为自然论述")
    if NUMERIC_SECTION.search(text):
        issues.append("小节标题使用阿拉伯数字编号（`### 1.1`），应使用中文序号 `### （一）`")
    if FAKE_HEADING.search(text):
        issues.append("正文出现伪标题编号（非标题以 `1.1 文字`/`（一）文字`/`一、文字` 开头），编号只允许存在于 Markdown 标题内；正文如需列表用有序 `1.`/`①`，优先改写为自然段")
    if INTERNAL_CARD_ID.search(prose):
        issues.append("正文出现内部知识卡片编号（K-user-01/K-industry-02/K01等）：正式报告只写来源机构名称，不得暴露内部研究过程编号")
    if EVIDENCE_LEVEL.search(prose):
        issues.append("正文出现内部证据等级标签（A级/B级/C级）：正式报告不得暴露内部证据分级，只写来源机构名称")
    fences = text.count("```")
    if fences % 2:
        issues.append("代码块围栏 ``` 未闭合")
    return issues


def has_analysis_paragraph(text: str) -> bool:
    """分析性小节必须有自然段论述，不允许整节只有列表/表格。"""
    sections = re.split(r"(?m)^###\s+", text)
    for section in sections[1:]:
        lines = section.splitlines()
        body = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith(("#", "|", "-", "*", ">"))]
        if not body:
            return True  # 交由调用方（需要具体报错）处理
    return False


def labelled_list_ratio(text: str) -> float:
    """行首 `-` 列表行占比（诊断用；正文本已由 check_forbidden 硬拦）。"""
    prose = _strip_fences(text)
    lines = [ln.strip() for ln in prose.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    dash = sum(1 for ln in lines if re.match(r"^[-*•◦·]\s+", ln))
    return dash / len(lines)


TABLE_SEP = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$", re.MULTILINE)
FIGURE_REF = re.compile(r"!\[(图\d+)[^\]]*\]\(")


def check_figure_table_support(text: str) -> list[str]:
    """图文配套门禁：图名行、表格表名行与资料来源行、正文引导句。

    针对实际产物暴露的问题：图表插入正文但无表名/来源/引导句，图表与文字脱节。
    """
    issues = []
    lines = text.splitlines()

    # 1) 每张图之后 2 行内必须有图名行
    for m in FIGURE_REF.finditer(text):
        fig_no = m.group(1)
        ln = text[:m.start()].count("\n")
        tail = "\n".join(lines[ln + 1:ln + 3])
        if not re.search(rf"^{re.escape(fig_no)}\s+\S", tail, re.MULTILINE):
            issues.append(f"图片 {fig_no} 下方缺少图名行（图片后空一行写 `{fig_no} 标题（数据来源…）`）")

    # 2) 正文引导句：`如图N所示` 覆盖至少 60% 的图
    fig_count = len(FIGURE_REF.findall(text))
    mentioned = len(re.findall(r"如图\d+所示", text))
    if fig_count and mentioned < fig_count * 0.6:
        issues.append(f"图表引导句不足：{mentioned}/{fig_count} 张图被『如图N所示』提及，应逐个引导（图文不脱节）")

    # 3) 每张表上方应有表名行（表N），表后应有资料来源/数据来源
    # 表名格式：表名行 + 空行 + 表头行 + 分隔线，所以表名在分隔线上方第3行
    # 资料来源在表格数据行之后，需扫描到表格结束
    for si, _ in enumerate(lines):
        if not TABLE_SEP.match(lines[si]):
            continue
        # 跳过自动注入的图表索引表格
        header_line = lines[si - 1].strip() if si >= 1 else ""
        above_section = "\n".join(lines[max(0, si - 10):si])
        is_auto_index = ("可视化图表索引" in above_section) or ("图号" in header_line and "图表名称" in header_line)
        if is_auto_index:
            continue
        # 表名检查：分隔线上方第2行（无空行）或第3行（有空行）
        name_line = ""
        if si >= 3:
            candidate1 = lines[si - 2].strip()  # 表名直接在表头上方（无空行）
            candidate2 = lines[si - 3].strip()  # 表名 + 空行 + 表头
            if re.match(r"^表\d+", candidate1):
                name_line = candidate1
            elif re.match(r"^表\d+", candidate2):
                name_line = candidate2
        if not name_line:
            issues.append(f"第 {si + 1} 行表格上方缺少表名行（表头上方空一行写 `表N 表名`）")
        # 资料来源检查：从分隔线后开始扫描，直到表格结束（空行或非表格行），再检查后续3行
        table_end = si + 1
        while table_end < len(lines) and lines[table_end].strip().startswith("|"):
            table_end += 1
        after = "\n".join(lines[table_end:table_end + 3])
        if not re.search(r"资料来源|数据来源", after):
            issues.append(f"第 {si + 1} 行表格下方缺少「资料来源：」行（表后 3 行内）")

    # 4) 图号连续性与唯一性检查（防止并行写作时图号重复/跳号/错用）
    # 图片引用（![图N ...](path)）是首次插入，必须连续且唯一
    fig_insert_refs = FIGURE_REF.findall(text)
    if fig_insert_refs:
        fig_nums = [int(re.search(r"\d+", f).group()) for f in fig_insert_refs]
        # 唯一性检查
        fig_dups = {k: v for k, v in Counter(fig_nums).items() if v > 1}
        if fig_dups:
            issues.append(f"图片重复插入: 图号 {sorted(fig_dups.keys())} 被多次插入（每张图只能在一个章节首次插入，其他章节用『见图N』交叉引用）")
        # 连续性检查
        unique_figs = sorted(set(fig_nums))
        expected_figs = list(range(1, len(unique_figs) + 1))
        if unique_figs != expected_figs:
            missing = [n for n in expected_figs if n not in unique_figs]
            unexpected = [n for n in unique_figs if n not in expected_figs]
            issues.append(f"图号不连续: 实际={unique_figs}, 期望从1开始连续; 缺失={missing}, 跳号={unexpected}")

    # 5) 表号连续性与唯一性检查
    table_name_refs = re.findall(r"^(表\d+)\s+", text, re.MULTILINE)
    if table_name_refs:
        table_nums = [int(re.search(r"\d+", t).group()) for t in table_name_refs]
        table_dups = {k: v for k, v in Counter(table_nums).items() if v > 1}
        if table_dups:
            issues.append(f"表号重复: 表号 {sorted(table_dups.keys())} 出现多次（每张表只能有一个表名行）")
        unique_tables = sorted(set(table_nums))
        expected_tables = list(range(1, len(unique_tables) + 1))
        if unique_tables != expected_tables:
            missing_t = [n for n in expected_tables if n not in unique_tables]
            unexpected_t = [n for n in unique_tables if n not in expected_tables]
            issues.append(f"表号不连续: 实际={unique_tables}, 期望从1开始连续; 缺失={missing_t}, 跳号={unexpected_t}")

    return issues