#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared Markdown/expression forbidden-rule checks for parts and final report."""
from __future__ import annotations

import re

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

    # 3) 每张表上方第 2 行应有表名行（表N），表后 3 行内应有资料来源/数据来源
    for si, _ in enumerate(lines):
        if not TABLE_SEP.match(lines[si]):
            continue
        name_line = lines[si - 2].strip() if si >= 2 else ""
        if not re.match(r"^表\d+", name_line):
            issues.append(f"第 {si + 1} 行表格上方缺少表名行（表头上方空一行写 `表N 表名`）")
        after = "\n".join(lines[si + 1:si + 4])
        if not re.search(r"资料来源|数据来源", after):
            issues.append(f"第 {si + 1} 行表格下方缺少「资料来源：」行（表后 3 行内）")
    return issues