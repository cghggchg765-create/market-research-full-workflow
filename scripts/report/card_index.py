#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Knowledge-card index and per-chapter evidence injection packs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# 容忍 `K01 | 标题`（竖线前有空格）与 `K01｜标题` 两种写法
CARD_RE = re.compile(r"^##\s+(K[\w-]+)\s*[｜|]\s*(.+?)\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*)$")

# 章节关联常见写法 → 章节 token（兜底映射，防止证据静默落入 misc）
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


def parse_cards(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    blocks = []
    matches = list(CARD_RE.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        fields = {}
        for line in body.splitlines():
            fm = FIELD_RE.match(line.strip())
            if fm:
                fields[fm.group(1).strip()] = fm.group(2).strip()
        blocks.append({"id": match.group(1), "title": match.group(2).strip(), **fields})
    return blocks


def chapter_token(text: str, fallback_text: str = "") -> str:
    corpus = f"{text} {fallback_text}"
    for token in TOKEN_ORDER:
        if token in corpus:
            return token
    if "执行摘要" in corpus:
        return "执行摘要"
    if "附录" in corpus or "参考文献" in corpus:
        return "附录"
    for key, token in TOKEN_FALLBACK.items():
        if key in corpus:
            return token
    return "未标注"


def local_file_field(card: dict) -> str:
    """兼容「本地文件」与「local_file」两种字段名。"""
    return card.get("local_file") or card.get("本地文件") or ""


def build_index(cards: list[dict]) -> list[dict]:
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
            "chapter_hint": chapter_token(c.get("章节关联", ""), c.get("title", "")),
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
    hits = [c for c in cards if chapter_token(c.get("章节关联", ""), c.get("title", "")) == token]
    return [
        f"### {c['id']}｜{c.get('title','')}\n"
        + "\n".join(f"- {k}：{v}" for k, v in c.items() if k not in ("id", "title"))
        for c in hits
    ]


def main() -> int:
    p = argparse.ArgumentParser(description="生成知识卡片索引，并按章节输出证据注入包")
    p.add_argument("--cards", type=Path, required=True, help="合并后的 knowledge-cards.md")
    p.add_argument("--ledger", type=Path)
    p.add_argument("--out", type=Path, required=True, help="card-index.json 输出")
    p.add_argument("--chapter", help="按章节输出注入包；同时写 <out>.chapter.md 片段")
    args = p.parse_args()

    cards = parse_cards(args.cards)
    index = build_index(cards)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"cards": index, "total": len(index)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[card_index] 索引 {len(index)} 张卡片 → {args.out}")

    if args.chapter:
        token = chapter_token(args.chapter)
        hits = [c for c in index if c["chapter_hint"] == token]
        ids = {c["id"] for c in hits}
        rows = ledger_rows(args.ledger, ids) if args.ledger else []
        package = {"chapter": args.chapter, "chapter_token": token, "cards": hits, "ledger_rows": rows}
        mapping = {"一、": "02", "二、": "03", "三、": "04", "四、": "05", "五、": "06", "六、": "07", "七、": "08", "执行摘要": "01", "附录": "08"}
        slug = mapping.get(token, "misc")
        package_path = args.out.with_name(f"inject.{slug}.json")
        package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        snippet_path = args.out.with_name(f"cards.{slug}.md")
        snippet_path.write_text("\n\n".join(card_snippets(cards, token)) + "\n", encoding="utf-8")
        print(f"[card_index] 章节注入包 {len(hits)} 张卡片 + {len(rows)} 台账行 → {package_path}")
        print(f"[card_index] 卡片片段 → {snippet_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())