#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Knowledge-card index and per-chapter evidence injection packs.

- parse：按 `## Kxx｜标题` 块切分，`- 字段：值` 单行字段 + 后续缩进/子要点行保留为多行原文
  （「核心要点/关键数据点」等整段随卡片进入注入包，Writer 可直接粘贴数据点）；
  每卡另存 `raw`（整卡原文），供注入提示词原样引用。
- 章节关联支持多章节：`chapter_hints` 为该卡命中全部章节 token（如「二、… / 六、…」→ 两章各得一份）；
  命令行按目标章节过滤，命中多章不丢失。
- 「参考文献/附录」与「七、」共用 08 分片：目标 slug 已存在时**合并写入**（不覆盖）。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# 容忍 `K01 | 标题`（竖线前有空格）与 `K01｜标题` 两种写法
CARD_RE = re.compile(r"^##\s+(K[\w-]+)\s*[｜|]\s*(.+?)\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*)$")

TOKEN_FALLBACK = {
    "执行摘要": "执行摘要", "核心观点": "执行摘要",
    "行业定义": "一、", "定义与规模": "一、", "规模": "一、", "历史": "一、",
    "行业结构": "二、", "产业链": "二、", "竞争格局": "二、", "竞争": "二、",
    "用户需求": "三、", "用户": "三、", "行为洞察": "三、",
    "驱动力": "四、", "驱动": "四、", "制约": "四、", "政策": "四、", "监管": "四、",
    "趋势": "五、", "机会": "五、", "预期差": "五、", "情景": "五、",
    "商业化": "六、", "盈利": "六、", "盈利质量": "六、", "落地建议": "六、",
    "风险": "七、", "结论": "七、", "展望": "七、", "风险提示": "七、",
    "参考文献": "参考文献", "附录": "附录", "数据来源": "附录", "方法": "附录", "术语": "附录",
}
TOKEN_ORDER = ("一、", "二、", "三、", "四、", "五、", "六、", "七、")
# 注入包分片 slug：七/风险结论/参考文献/附录均归 08（writer08 消费），合并写入
SLUG_MAP = {"一、": "02", "二、": "03", "三、": "04", "四、": "05", "五、": "06",
            "六、": "07", "七、": "08", "执行摘要": "01", "参考文献": "08", "附录": "08"}


def parse_cards(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    blocks = []
    matches = list(CARD_RE.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        fields = {}
        current = None
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            fm = FIELD_RE.match(line)
            if fm:
                current = fm.group(1).strip()
                fields[current] = fm.group(2).strip()
                continue
            if current and not fm:
                # 字段的续行/子要点（非空行、非新字段行）：保留原文，追加为多行值
                prev = fields.get(current, "")
                fields[current] = (prev + "\n" + line).strip("\n") if prev else line
        blocks.append({"id": match.group(1), "title": match.group(2).strip(),
                       "raw": body.strip(), **fields})
    return blocks


def chapter_tokens(text: str, fallback_text: str = "") -> list[str]:
    """返回卡片关联的全部章节 token（多章节不丢失；无命中给兜底映射）。"""
    corpus = f"{text} {fallback_text}"
    hits = [tok for tok in TOKEN_ORDER if tok in corpus]
    if "执行摘要" in corpus and "执行摘要" not in hits:
        hits.append("执行摘要")
    if "参考文献" in corpus and "参考文献" not in hits:
        hits.append("参考文献")
    elif ("附录" in corpus or "数据来源" in corpus) and "参考文献" not in hits:
        hits.append("附录")
    if hits:
        return hits
    for key, token in TOKEN_FALLBACK.items():
        if key in corpus:
            return [token]
    return ["未标注"]


def local_file_field(card: dict) -> str:
    """兼容「本地文件」与「local_file」两种字段名。"""
    return card.get("local_file") or card.get("本地文件") or ""


def build_index(cards: list[dict]) -> list[dict]:
    """卡片索引（键名与 references/knowledge-cards.md 声明一致，供下游 agent 读取）。"""
    return [
        {
            "id": c["id"],
            "title": c.get("title", ""),
            "type": c.get("类型", ""),
            "source": c.get("来源机构", ""),
            "year": c.get("年份", ""),
            "metric_key": c.get("metric_key", ""),
            "source_id": c.get("source_id", ""),
            "local_file": local_file_field(c),
            "supports_claim": c.get("supports_claim", ""),
            "interpretation": c.get("解读策略", c.get("interpretation", "")),
            "usage_note": c.get("使用建议", c.get("usage_note", "")),
            "limitation": c.get("反证与边界", c.get("limitation", "")),
            "key_points": c.get("核心要点", ""),
            "data_points": c.get("关键数据点", ""),
            "raw": c.get("raw", ""),
            "chapter_hint": (chapter_tokens(c.get("章节关联", ""), c.get("title", "")) or [""])[0],
            "chapter_hints": chapter_tokens(c.get("章节关联", ""), c.get("title", "")),
        }
        for c in cards
    ]


def ledger_rows(ledger_path: Path, card_ids: set[str]) -> list[dict]:
    rows = []
    if not ledger_path.is_file():
        return rows
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("card_id") in card_ids:
            rows.append(item)
    return rows


def card_snippets(cards: list[dict], token: str) -> list[str]:
    """按章节输出卡片片段：保真输出整卡原文（raw 缺失时回退字段拼接）。"""
    hits = [c for c in cards if token in c.get("chapter_hints", [])]
    parts = []
    for c in hits:
        raw = c.get("raw", "").strip()
        if raw:
            parts.append(f"### {c['id']}｜{c.get('title', '')}\n\n{raw}")
        else:
            body = "\n".join(f"- {k}：{v}" for k, v in c.items()
                             if k not in ("id", "title", "raw", "chapter_hint", "chapter_hints"))
            parts.append(f"### {c['id']}｜{c.get('title', '')}\n\n{body}")
    return parts


def merge_package(path: Path, new: dict) -> dict:
    """目标 slug 已存在（如 08 先写七、再写参考文献）时合并卡片与台账行，去重保序。"""
    if not path.is_file():
        return new
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return new
    seen = {c["id"] for c in old.get("cards", [])}
    cards = list(old.get("cards", [])) + [c for c in new.get("cards", []) if c["id"] not in seen]
    rows = old.get("ledger_rows", []) + new.get("ledger_rows", [])
    old.update({"cards": cards, "ledger_rows": rows,
                "chapter": old.get("chapter", "") + " / " + new.get("chapter", "")})
    return old


def main() -> int:
    p = argparse.ArgumentParser(description="生成知识卡片索引，并按章节输出证据注入包")
    p.add_argument("--cards", type=Path, required=True, help="合并后的 knowledge-cards.md")
    p.add_argument("--ledger", type=Path)
    p.add_argument("--out", type=Path, required=True, help="card-index.json 输出")
    p.add_argument("--chapter", help="按章节输出注入包；同时写 <out>.<slug>.md 片段")
    args = p.parse_args()

    cards = parse_cards(args.cards)
    index = build_index(cards)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"cards": index, "total": len(index)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[card_index] 索引 {len(index)} 张卡片 → {args.out}")

    if args.chapter:
        token = chapter_tokens(args.chapter)[0]
        hits = [c for c in index if token in c["chapter_hints"]]
        ids = {c["id"] for c in hits}
        rows = ledger_rows(args.ledger, ids) if args.ledger else []
        package = {"chapter": args.chapter, "chapter_token": token,
                   "cards": hits, "ledger_rows": rows}
        slug = SLUG_MAP.get(token, "misc")
        package_path = args.out.with_name(f"inject.{slug}.json")
        merged = merge_package(package_path, package)
        package_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        snippet_path = args.out.with_name(f"cards.{slug}.md")
        snippets = card_snippets(index, token)
        existing = snippet_path.read_text(encoding="utf-8").strip() if snippet_path.is_file() else ""
        snippet_text = "\n\n".join(snippets)
        snippet_path.write_text((existing + "\n\n" + snippet_text).strip() + "\n" if existing else snippet_text + "\n", encoding="utf-8")
        print(f"[card_index] 章节注入包 {len(merged.get('cards', []))} 张卡片 + {len(merged.get('ledger_rows', []))} 台账行 → {package_path}")
        print(f"[card_index] 卡片片段 → {snippet_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
