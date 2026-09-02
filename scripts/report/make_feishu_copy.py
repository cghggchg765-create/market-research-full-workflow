#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书推送副本生成器：把本地报告（绝对路径图引用）转换为飞书 lark-cli 可用的推送副本。

规则（对齐 lark-doc skill）：
- 图片引用 `![alt](绝对路径)` → `@./charts/{文件名}`（相对 CWD，推送时 cd 到交付目录）
- 文件名含空格 → 尖括号包裹：`![alt](<@./charts/产品 对比.png>)`
- 校验：每个被引用的图片文件必须存在（缺图直接报错列出）
- 输出副本 + 统计（图片数 / 校验结果）

用法：
  make_feishu_copy.py --report report.md --charts-dir charts --out {topic}_飞书版.md
"""
import argparse
import io
import os
import re
import sys


def convert(report_path, charts_dir, out_path):
    with io.open(report_path, "r", encoding="utf-8") as f:
        text = f.read()

    missing = []
    converted = []

    def repl(m):
        alt = m.group(1)
        raw_path = m.group(2).strip()
        # 跳过已经是 @./ 形式的（幂等）
        if raw_path.startswith("@./") or raw_path.startswith("@"):
            return m.group(0)
        base = os.path.basename(raw_path.replace("\\", "/"))
        src = os.path.join(charts_dir, base)
        if not os.path.exists(src):
            missing.append(base)
            return m.group(0)  # 保留原文，供报错后人工处理
        target = f"@./charts/{base}"
        if " " in base or any(c in base for c in "（）()"):
            target = f"<{target}>"
        converted.append(base)
        return f"![{alt}]({target})"

    out = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, text)

    if missing:
        print("[ERROR] 以下图片文件不存在，副本未生成：")
        for b in missing:
            print(f"  ✗ {b}")
        return 1, missing, []

    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(out)

    mermaid_count = out.count("```mermaid")
    print(f"[OK] 飞书推送副本已生成: {out_path}")
    print(f"  图片引用转换: {len(converted)} 张（目标 @./charts/）")
    print(f"  mermaid 块: {mermaid_count} 个")
    return 0, missing, converted


def main():
    ap = argparse.ArgumentParser(description="飞书推送副本生成器")
    ap.add_argument("--report", required=True, help="本地报告 report.md 路径")
    ap.add_argument("--charts-dir", default="charts", help="图表目录")
    ap.add_argument("--out", required=True, help="输出副本路径")
    args = ap.parse_args()
    code, missing, converted = convert(args.report, args.charts_dir, args.out)
    return code


if __name__ == "__main__":
    sys.exit(main())