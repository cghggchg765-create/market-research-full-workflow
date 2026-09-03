#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图表代码级审计与无视觉能力替代检查（正式技能工具）。

图表生成后的检查分两条通道（见 references/chart-inspection.md）：
1. 有视觉能力的模型：Read 逐张查看 PNG（最高标准）。
2. 模型无视觉能力（读图被拒）时【强制替代，不允许跳过或假装通过】：
   a. bbox 审计：fig 脚本在 savefig 后调用 `from figlib_audit import audit; audit(fig, 名称)`，
      自动检查文本越界 / 相邻刻度重叠 / 图例越界（[FAIL]/[WARN]）。
   b. 像素健全性：`pixel` 子命令检查 PNG 非空白、方差正常。
   c. 拼版图 + 人工清单：`contact` 子命令生成 contact sheet，配合 inspection.json
      的 checklist（预期关键数值），由人工完成最终视觉确认。

CLI 用法（CWD 任意，脚本须自带中文字体注册）：
  {task_python} scripts/charts/figlib_audit.py audit --script {run_dir}/scripts/charts/fig_03_x.py
  {task_python} scripts/charts/figlib_audit.py pixel --dir {run_dir}/charts --glob "图*.png"
  {task_python} scripts/charts/figlib_audit.py contact --dir {run_dir}/charts --out {run_dir}/charts/_contact_sheet.png
退出码：audit 有 [FAIL] → 1；脚本未接入 audit → 2；pixel 有 FAIL → 1；全部通过 → 0。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

_MARGIN = 2.0


# ---------------------------------------------------------------- 库接口
def _inside_fig(fig, bb) -> bool:
    w, h = fig.bbox.width, fig.bbox.height
    return not (bb.x0 < -_MARGIN or bb.y0 < -_MARGIN or bb.x1 > w + _MARGIN or bb.y1 > h + _MARGIN)


def audit(fig, name: str) -> tuple[bool, list[str]]:
    """bbox 审计：文本/刻度/图例越出画布、相邻 x 刻度重叠。

    fig 脚本在 savefig 后调用；返回 (无 FAIL, 问题行)。问题行同时打印到 stdout，
    供 CLI 子进程模式解析。
    """
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    lines: list[str] = []
    for ax in fig.axes:
        axes_on = bool(getattr(ax, "axison", True)) and ax.get_visible()
        texts = [ax.title, ax.xaxis.label, ax.yaxis.label] + list(ax.texts)
        for t in texts:
            if not t.get_text().strip():
                continue
            # 隐藏轴（axis('off')）的轴标题/轴标签不渲染，跳过；手动注释（ax.texts）始终检查
            if not t.get_visible() or (not axes_on and t is not ax.title and t not in ax.texts):
                continue
            try:
                bb = t.get_window_extent(rend)
            except Exception:
                continue
            if not _inside_fig(fig, bb):
                lines.append(f"[FAIL] 文本越出画布: {t.get_text()[:24]!r} "
                             f"bbox=({bb.x0:.0f},{bb.y0:.0f},{bb.width:.0f}x{bb.height:.0f})")
        if axes_on:
            for lb in ax.get_xticklabels() + ax.get_yticklabels():
                if not lb.get_text().strip() or not lb.get_visible():
                    continue
                bb = lb.get_window_extent(rend)
                if not _inside_fig(fig, bb):
                    lines.append(f"[FAIL] 刻度标签越出画布: {lb.get_text()!r}")
            xlabs = [lb.get_window_extent(rend) for lb in ax.get_xticklabels()
                     if lb.get_text().strip() and lb.get_visible()]
            for a, b in zip(xlabs, xlabs[1:]):
                ox = min(a.x1, b.x1) - max(a.x0, b.x0)
                oy = min(a.y1, b.y1) - max(a.y0, b.y0)
                if ox > 2.0 and oy > 2.0:
                    idx_a, idx_b = xlabs.index(a), xlabs.index(b)
                    la = ax.get_xticklabels()[idx_a].get_text()
                    lb_ = ax.get_xticklabels()[idx_b].get_text()
                    lines.append(f"[WARN] 相邻 x 刻度标签重叠: {la!r} 与 {lb_!r}（ox={ox:.0f}px）")
            leg = ax.get_legend()
            if leg is not None:
                bb = leg.get_window_extent(rend)
                if not _inside_fig(fig, bb):
                    lines.append(f"[FAIL] 图例越出画布: bbox=({bb.x0:.0f},{bb.y0:.0f},{bb.width:.0f}x{bb.height:.0f})")

            # === 增强检查：多轴 x 范围一致性 ===
            all_axes = fig.axes
            if len(all_axes) > 1:
                main_xlim = all_axes[0].get_xlim()
                for other_ax in all_axes[1:]:
                    other_xlim = other_ax.get_xlim()
                    if abs(main_xlim[0] - other_xlim[0]) > 0.01 or abs(main_xlim[1] - other_xlim[1]) > 0.01:
                        lines.append(f"[FAIL] 多轴 x 范围不一致: 主轴={main_xlim}, 次轴={other_xlim}（数据系列 x 坐标会错位，导致横坐标堆叠）")

            # === 增强检查：类别轴数据越界 ===
            xlim = ax.get_xlim()
            x_range = xlim[1] - xlim[0]
            xtick_labels = [lb.get_text() for lb in ax.get_xticklabels()
                           if lb.get_text().strip() and lb.get_visible()]
            n_categories = len(xtick_labels)
            is_category_axis = 0 < n_categories <= 20

            # 检查折线数据 x 坐标
            for line in ax.get_lines():
                xdata = line.get_xdata()
                if len(xdata) > 0:
                    xmin, xmax = min(xdata), max(xdata)
                    if xmin < xlim[0] - x_range * 0.5 or xmax > xlim[1] + x_range * 0.5:
                        lines.append(f"[FAIL] 折线数据 x 坐标超出轴范围: 数据=[{xmin:.1f},{xmax:.1f}], x轴={xlim}")
                    if is_category_axis and x_range > 0 and (xmax - xmin) > x_range * 0.8 and xmin > xlim[0] + x_range * 0.3:
                        lines.append(f"[WARN] 折线数据 x 范围与轴类别不匹配: 数据=[{xmin:.1f},{xmax:.1f}], x轴={xlim}（疑似 hlines 把数值画在了类别轴上）")

            # === 增强检查：hlines/vlines 方向与轴匹配 ===
            bar_x_max = 0
            for patch in ax.patches:
                if hasattr(patch, 'get_x') and hasattr(patch, 'get_width'):
                    bx = patch.get_x() + patch.get_width()
                    bar_x_max = max(bar_x_max, bx)

            for coll in ax.collections:
                coll_type = type(coll).__name__
                if 'LineCollection' in coll_type:
                    segs = coll.get_segments()
                    if segs and len(segs) > 0:
                        for seg in segs[:5]:
                            if len(seg) >= 2:
                                xs = [float(p[0]) for p in seg]
                                ys = [float(p[1]) for p in seg]
                                # 水平线：y 相同，x 变化
                                if max(ys) - min(ys) < 0.01 and max(xs) - min(xs) > 1:
                                    if is_category_axis and min(xs) > n_categories * 1.5:
                                        lines.append(f"[FAIL] hlines 在类别轴上 x 坐标越界: x=[{min(xs):.0f},{max(xs):.0f}], 类别数={n_categories}（哑铃图应改用 vlines，hlines 会把数值画在类别轴上导致横坐标堆叠）")
                                    elif bar_x_max > 0 and min(xs) > bar_x_max * 2:
                                        lines.append(f"[FAIL] hlines 的 x 范围与柱状图不匹配: hlines x=[{min(xs):.0f},{max(xs):.0f}], 柱状图 x_max={bar_x_max:.1f}（轴错位）")
    if lines:
        print(f"[audit {name}]")
        for ln in lines:
            print("  " + ln)
    else:
        print(f"[audit {name}] CLEAN")
    return not any(ln.startswith("[FAIL]") for ln in lines), lines


# ---------------------------------------------------------------- CLI
def _cmd_audit(script: Path) -> int:
    """子进程运行 fig 脚本并解析其 audit 输出（脚本须 import 本模块并调用 audit）。"""
    if not script.is_file():
        print(f"[audit-cli] 脚本不存在: {script}")
        return 2
    proc = subprocess.run([sys.executable, str(script)], cwd=str(script.parent),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    audit_lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith(("[audit ", "  [FAIL]", "  [WARN]"))]
    if proc.returncode != 0:
        print("[audit-cli] 脚本运行失败，退出码非 0")
        return 1
    if not audit_lines:
        print("[audit-cli] 脚本未接入 figlib_audit.audit()：请在每个 fig 脚本 savefig 后调用 audit(fig, 名称)")
        return 2
    has_fail = any("  [FAIL]" in ln for ln in audit_lines)
    print("[audit-cli] " + ("FAIL：存在越界问题，需修复后重跑" if has_fail else "通过（无 FAIL）"))
    return 1 if has_fail else 0


def _cmd_pixel(charts_dir: Path, pattern: str) -> int:
    """像素健全性：非空白、非纯白、尺寸正常（语义仍需人工/视觉模型）。"""
    from PIL import Image
    files = sorted(charts_dir.glob(pattern))
    if not files:
        print(f"[pixel] {charts_dir} 下无匹配 {pattern!r}")
        return 2
    bad = 0
    for p in files:
        im = Image.open(p).convert("RGB")
        small = im.resize((64, 40))
        if hasattr(small, "get_flattened_data"):
            px = list(small.get_flattened_data())
        else:
            px = list(small.getdata())
        var = sum((sum(c) / 3 - 128) ** 2 for c in px) / len(px)
        white = sum(1 for c in px if sum(c) / 3 > 245) / len(px)
        flag = ""
        if var < 30 or white > 0.92:
            flag = "  <- FAIL"
            bad += 1
        print(f"[pixel] {p.name}  {im.size}  var={var:7.1f}  近白像素={white:5.1%}{flag}")
    print(f"[pixel] {'FAIL' if bad else 'PASS'}（{len(files)} 张）")
    return 1 if bad else 0


def _cmd_contact(charts_dir: Path, out: Path, cols: int) -> int:
    """生成拼版图（缩略网格 + ASCII 序号），供人工/视觉模型一次过目。"""
    from PIL import Image
    files = sorted(p for p in charts_dir.glob("*.png") if "_contact_sheet" not in p.name)
    if not files:
        print(f"[contact] {charts_dir} 下无 PNG")
        return 2
    import math
    rows = math.ceil(len(files) / cols)
    tw, th, pad, lab = 460, 280, 14, 30
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, rows * (th + lab) + (rows + 1) * pad), "white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(sheet)
    for i, p in enumerate(files):
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw, th))
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + lab + pad)
        sheet.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        draw.text((x, y + th + 4), f"[{i + 1:02d}] {p.stem[:24]}", fill="black")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"[contact] {len(files)} 张 → {out}（{sheet.size}）")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="图表代码级审计与无视觉能力替代检查")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="运行 fig 脚本并解析 bbox 审计输出")
    a.add_argument("--script", type=Path, required=True)
    px = sub.add_parser("pixel", help="PNG 像素健全性检查（非空白/方差）")
    px.add_argument("--dir", type=Path, required=True)
    px.add_argument("--glob", default="*.png")
    ct = sub.add_parser("contact", help="生成人工检查拼版图")
    ct.add_argument("--dir", type=Path, required=True)
    ct.add_argument("--out", type=Path, required=True)
    ct.add_argument("--cols", type=int, default=4)
    args = p.parse_args()
    if args.cmd == "audit":
        return _cmd_audit(args.script)
    if args.cmd == "pixel":
        return _cmd_pixel(args.dir, args.glob)
    return _cmd_contact(args.dir, args.out, args.cols)


if __name__ == "__main__":
    sys.exit(main())
