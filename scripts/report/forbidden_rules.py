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
STAR_LIST = re.compile(r"^\s*\*\s+", re.MULTILINE)
TAG_BRACKET = re.compile(r"^\s*【(?:事实|推断|结论|备注|数据|来源)】", re.MULTILINE)
BOLD_KEYWORD = re.compile(r"\*\*[^*：]{1,30}\*\*：")
FAKE_HEADING = re.compile(r"^\s*(?:\d+(?:\.\d+)*|（[一二三四五六七八九十]+）|[一二三四五六七八九十]+、)\s+\S", re.MULTILINE)


def check_forbidden(text: str) -> list[str]:
    """返回违反表达禁则的问题列表；空列表表示通过。"""
    issues = []
    if STAR_LIST.search(text):
        issues.append("无序列表使用星号 `*`，应改为短横线 `-` 或自然段")
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
    """行首 `-` 列表行占总正文行比例，用于清单化程度提示。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    dash = sum(1 for ln in lines if ln.startswith("- "))
    return dash / len(lines)