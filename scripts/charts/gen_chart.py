#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场调研报告通用图表生成器
读取 specs.json（可视化 SubAgent 产出的图表规格），用 matplotlib 批量生成 PNG。
支持图型：bar / hbar / stacked_bar / line / pie / donut / radar / scatter / heatmap
mermaid 型条目不透传绘图，直接输出代码块文本（由编排者嵌入报告）。

用法：
  gen_chart.py --spec specs.json --outdir charts [--dpi 150]
  gen_chart.py --self-test            # 内置演示数据生成 6 张图（验证环境）
  gen_chart.py --list-types           # 列出支持的图型
"""
import argparse
import shutil
import json
import os
import sys

# ---------------------------------------------------------------- 中文环境
_FONT_CANDIDATES = [
    r"C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    r"C:/Windows/Fonts/simhei.ttf",    # 黑体
    r"C:/Windows/Fonts/simsun.ttc",    # 宋体
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def setup_chinese_font():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager
    installed = False
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
                installed = True
                break
            except Exception:
                continue
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "sans-serif"
    if installed:
        try:
            from matplotlib import font_manager as fm
            name = fm.FontProperties(fname=_FONT_CANDIDATES[0]).get_name() \
                if os.path.exists(_FONT_CANDIDATES[0]) else "DejaVu Sans"
            plt.rcParams["font.sans-serif"] = [name, "Microsoft YaHei", "SimHei",
                                               "PingFang SC", "Noto Sans CJK SC",
                                               "DejaVu Sans"]
        except Exception:
            pass
    plt.rcParams["axes.unicode_minus"] = False  # 负号正常显示
    return installed


_PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
            "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC", "#647687"]

_CURRENT_SPEC = {}  # 当前生成的 spec，供 figsize 覆盖读取


def _figsize(default):
    """spec.figsize=[w, h] 可覆盖默认画布尺寸（重绘时用于缓解标签拥挤）。"""
    fs = _CURRENT_SPEC.get("figsize")
    if isinstance(fs, (list, tuple)) and len(fs) == 2:
        return float(fs[0]), float(fs[1])
    return default


def _require_numbers(values, ctx):
    out = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, str):
            try:
                out.append(float(v.replace(",", "").replace("%", "")))
            except ValueError:
                raise ValueError(f"{ctx}: 无法解析数值 '{v}'")
        else:
            raise ValueError(f"{ctx}: 非法数值类型 {type(v).__name__}")
    return out


def _place_subtitle(ax):
    """把副题精确放置在标题正下方（渲染后按 title bbox 定位，避免与标题重叠）。
    ax.text 的 y 是文本基线，需额外让出字号上升部（ascent）再放。"""
    subtitle = getattr(ax, "_subtitle", None)
    if not subtitle:
        return
    fig = ax.figure
    fig.canvas.draw()
    tb = ax.title.get_window_extent()
    inv = ax.transAxes.inverted()
    ascent_px = 10 * fig.dpi / 72.0 + 2        # 10pt 字号上升部 ≈ 10pt + 2px 余量
    y_baseline = tb.y0 - 4 - ascent_px         # 标题底边下方 4px 间隙 + 文本上升部
    y_axes = inv.transform((0, y_baseline))[1]
    y_axes = min(y_axes, 1.10)                 # 上限保护，防止副题超出 figure
    ax.text(0.5, y_axes, subtitle, transform=ax.transAxes, ha="center",
            fontsize=10, color="#666666")


def _style_ax(ax, title, subtitle, source, notes):
    from matplotlib import pyplot as plt
    ax.set_title(title, fontsize=13, fontweight="bold", pad=14)
    ax._subtitle = subtitle                   # 由 _place_subtitle 在布局后放置
    if source:
        ax.text(0.0, -0.12, f"数据来源：{source}", transform=ax.transAxes,
                fontsize=8.5, color="#888888")
    if notes:
        ax.text(0.0, -0.16, "；".join(notes), transform=ax.transAxes,
                fontsize=8, color="#999999")
    if ax.name == "polar":
        ax.grid(alpha=0.3, linestyle="--")
    else:
        for spine in ("top", "right"):
            if spine in ax.spines:
                ax.spines[spine].set_visible(False)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- 各图型
def draw_bar(spec, out_path):
    import matplotlib.pyplot as plt
    d = spec["data"]
    cats = d["categories"]
    series = d["series"]
    fig, ax = plt.subplots(figsize=_figsize((10, max(5, len(cats) * 0.35 + 2.5))))
    width = 0.8 / len(series)
    x = range(len(cats))
    for i, s in enumerate(series):
        vals = _require_numbers(s["values"], s["name"])
        off = (i - (len(series) - 1) / 2) * width
        ax.bar([t + off for t in x], vals, width, label=s["name"],
               color=_PALETTE[i % len(_PALETTE)])
        for t, v in zip(x, vals):
            if v is not None:
                ax.text(t + off, v, f"{v:g}", ha="center", va="bottom",
                        fontsize=8, color="#444444")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats, fontsize=10)
    if len(series) > 1:
        ax.legend(fontsize=9, frameon=False)
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


def draw_hbar(spec, out_path):
    import matplotlib.pyplot as plt
    d = spec["data"]
    cats = d["categories"]
    series = d["series"]
    fig, ax = plt.subplots(figsize=_figsize((10, max(4.5, len(cats) * 0.45 + 1.5))))
    y = range(len(cats))
    height = 0.8 / len(series)
    for i, s in enumerate(series):
        vals = _require_numbers(s["values"], s["name"])
        off = (i - (len(series) - 1) / 2) * height
        ax.barh([t + off for t in y], vals, height, label=s["name"],
                color=_PALETTE[i % len(_PALETTE)])
        for t, v in zip(y, vals):
            if v is not None:
                ax.text(v, t + off, f"{v:g}", va="center", ha="left",
                        fontsize=8, color="#444444")
    ax.set_yticks(list(y))
    ax.set_yticklabels(cats, fontsize=10)
    if len(series) > 1:
        ax.legend(fontsize=9, frameon=False)
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


def draw_stacked_bar(spec, out_path):
    import matplotlib.pyplot as plt
    d = spec["data"]
    cats = d["categories"]
    series = d["series"]
    fig, ax = plt.subplots(figsize=_figsize((10, max(5, len(cats) * 0.35 + 2.5))))
    x = range(len(cats))
    bottom = [0.0] * len(cats)
    for i, s in enumerate(series):
        vals = _require_numbers(s["values"], s["name"])
        ax.bar(x, vals, bottom=bottom, label=s["name"],
               color=_PALETTE[i % len(_PALETTE)], width=0.6)
        bottom = [b + (v if v is not None else 0.0) for b, v in zip(bottom, vals)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats, fontsize=10)
    ax.legend(fontsize=9, frameon=False)
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


def draw_line(spec, out_path):
    import matplotlib.pyplot as plt
    d = spec["data"]
    xs = [str(v) for v in d["x"]]
    fig, ax = plt.subplots(figsize=_figsize((10, 5.5)))
    for i, s in enumerate(d["series"]):
        vals = _require_numbers(s["values"], s["name"])
        ax.plot(range(len(xs)), vals, marker="o", markersize=5, linewidth=2,
                label=s["name"], color=_PALETTE[i % len(_PALETTE)])
        for t, v in enumerate(vals):
            if v is not None:
                ax.text(t, v, f"{v:g}", ha="center", va="bottom", fontsize=8,
                        color="#444444")
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels(xs, fontsize=10)
    ax.legend(fontsize=9, frameon=False, loc="upper left")
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


def _draw_pie(spec, out_path, donut=False):
    import matplotlib.pyplot as plt
    d = spec["data"]
    labels = d["labels"]
    vals = _require_numbers(d["values"], "pie")
    fig, ax = plt.subplots(figsize=_figsize((8.5, 5.5)))
    wedges, *_ = ax.pie(vals, labels=None, startangle=90, counterclock=False,
                       colors=_PALETTE[:len(labels)],
                       autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
                       pctdistance=0.78,
                       wedgeprops=dict(width=0.42) if donut else dict())
    if donut:
        ax.text(0, 0, d.get("center_text", ""), ha="center", va="center",
                fontsize=12, fontweight="bold")
    total = sum(v for v in vals if v is not None) or 1
    legend_labels = [f"{l}（{v / total * 100:.1f}%）" if v is not None else l
                     for l, v in zip(labels, vals)]
    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
              fontsize=9, frameon=False)
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


def draw_pie(spec, out_path):
    _draw_pie(spec, out_path, donut=False)


def draw_donut(spec, out_path):
    _draw_pie(spec, out_path, donut=True)


def draw_radar(spec, out_path):
    import numpy as np
    import matplotlib.pyplot as plt
    d = spec["data"]
    cats = d["categories"]
    series = d["series"]
    n = len(cats)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=_figsize((8, 8)), subplot_kw=dict(polar=True))
    for i, s in enumerate(series):
        vals = _require_numbers(s["values"], s["name"])
        vals = vals + vals[:1]
        ax.plot(angles, vals, linewidth=2, label=s["name"],
                color=_PALETTE[i % len(_PALETTE)])
        ax.fill(angles, vals, alpha=0.12, color=_PALETTE[i % len(_PALETTE)])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(cats, fontsize=10)
    ax.set_ylim(0, max([max(_require_numbers(s["values"], s["name"]))
                        for s in series] + [1]) * 1.2)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.05), fontsize=9,
              frameon=False)
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


def draw_scatter(spec, out_path):
    import matplotlib.pyplot as plt
    d = spec["data"]
    fig, ax = plt.subplots(figsize=_figsize((9, 7)))
    pts = d["points"]
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    ax.scatter(xs, ys, s=90, color=d.get("color", "#4C78A8"), zorder=3,
               edgecolors="white", linewidths=1)
    for p in pts:
        ax.annotate(p.get("label", ""), (p["x"], p["y"]),
                    textcoords="offset points", xytext=(6, 6), fontsize=9)
    ax.set_xlabel(d.get("xlabel", ""), fontsize=11)
    ax.set_ylabel(d.get("ylabel", ""), fontsize=11)
    if d.get("quadrants"):
        q = d["quadrants"]
        ax.axvline(q.get("x", 0.5), color="#CCCCCC", linestyle="--", alpha=0.8)
        ax.axhline(q.get("y", 0.5), color="#CCCCCC", linestyle="--", alpha=0.8)
        ax.text(0.02, 0.98, q.get("q1", ""), transform=ax.transAxes, fontsize=9,
                color="#888888", va="top")
        ax.text(0.98, 0.98, q.get("q2", ""), transform=ax.transAxes, fontsize=9,
                color="#888888", ha="right", va="top")
        ax.text(0.02, 0.02, q.get("q3", ""), transform=ax.transAxes, fontsize=9,
                color="#888888")
        ax.text(0.98, 0.02, q.get("q4", ""), transform=ax.transAxes, fontsize=9,
                color="#888888", ha="right")
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


def draw_heatmap(spec, out_path):
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    d = spec["data"]
    rows = d["rows"]
    cols = d["cols"]
    matrix = d["matrix"]
    arr = np.array(matrix, dtype=float)
    cmap = LinearSegmentedColormap.from_list(
        "risk", ["#2E7D32", "#FFEB3B", "#F44336"]) if d.get("color_scale") == "risk" \
        else plt.get_cmap("YlOrRd")
    fig, ax = plt.subplots(figsize=_figsize((max(7, len(cols) * 1.1 + 2), max(5, len(rows) * 0.6 + 2))))
    im = ax.imshow(arr, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, fontsize=10)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=10)
    for i in range(len(rows)):
        for j in range(len(cols)):
            v = arr[i, j]
            ax.text(j, i, f"{v:g}", ha="center", va="center", fontsize=10,
                    color="#111111" if 0.35 < v < 0.75 else "white" if v > 0.45 else "#111111")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.03)
    cb.set_label(d.get("colorbar_label", ""), fontsize=9)
    ax.set_xticks(ax.get_xticks())
    ax.set_yticks(ax.get_yticks())
    ax.set_xticklabels(cols, fontsize=10)
    ax.set_yticklabels(rows, fontsize=10)
    _style_ax(ax, spec["title"], spec.get("subtitle"), spec.get("source"),
              spec.get("notes"))
    fig.tight_layout()
    _place_subtitle(ax)
    _warn_layout(ax, spec)
    fig.savefig(out_path, dpi=spec.get("dpi", 150), bbox_inches="tight")
    plt.close(fig)


_DRAWERS = {
    "bar": draw_bar,
    "hbar": draw_hbar,
    "stacked_bar": draw_stacked_bar,
    "line": draw_line,
    "pie": draw_pie,
    "donut": draw_donut,
    "radar": draw_radar,
    "scatter": draw_scatter,
    "heatmap": draw_heatmap,
}


# ---------------------------------------------------------------- 主流程
def _validate_spec(spec):
    t = spec.get("type")
    if t == "mermaid":
        if not spec.get("title") or not spec.get("code") or not spec.get("lang"):
            raise ValueError(f"mermaid 图 '{spec.get('title')}' 缺少 title/code/lang")
        return
    if t not in _DRAWERS:
        raise ValueError(f"不支持的图型 '{t}'，可选：{', '.join(_DRAWERS)} + mermaid（透传）")
    for field in ("card_id", "source_id", "year", "unit", "definition", "base_period", "source", "position"):
        if spec.get(field) in (None, ""):
            raise ValueError(f"图表 '{spec.get('title', '')}' 缺少证据字段 {field}")
    if not spec.get("title"):
        raise ValueError("图表缺少 title")
    if not spec.get("filename"):
        raise ValueError(f"图表 '{spec['title']}' 缺少 filename")
    if "data" not in spec:
        raise ValueError(f"图表 '{spec['title']}' 缺少 data")
    d = spec["data"]
    if t in ("bar", "hbar", "stacked_bar", "line", "radar"):
        if not d.get("categories") and t != "line":
            raise ValueError(f"图表 '{spec['title']}' 缺少 categories")
        if not d.get("series"):
            raise ValueError(f"图表 '{spec['title']}' 缺少 series")
    elif t in ("pie", "donut"):
        if not d.get("labels") or not d.get("values"):
            raise ValueError(f"图表 '{spec['title']}' 缺少 labels/values")
    elif t == "scatter":
        if not d.get("points"):
            raise ValueError(f"图表 '{spec['title']}' 缺少 points")
    elif t == "heatmap":
        if not d.get("rows") or not d.get("cols") or not d.get("matrix"):
            raise ValueError(f"图表 '{spec['title']}' 缺少 rows/cols/matrix")


def _bbox_overlap(a, b):
    """两个窗口 bbox 是否相交，返回 (是否相交, 相交面积px²)。"""
    ox = min(a.x1, b.x1) - max(a.x0, b.x0)
    oy = min(a.y1, b.y1) - max(a.y0, b.y0)
    if ox <= 0 or oy <= 0:
        return False, 0.0
    return True, ox * oy


def _warn_layout(ax, spec):
    """渲染后布局校验：文字重叠/文本出界/图例遮挡/x轴标签重叠。
    只输出 WARN 供视觉检查优先复核，不阻断生成。"""
    fig = ax.figure
    fig.canvas.draw()
    issues = []

    texts = [(t, t.get_window_extent())
             for t in ax.texts if t.get_text().strip() and t.get_visible()]
    # 1) 可见文字两两重叠（数据标签/副题/来源等）
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            overlap, area = _bbox_overlap(texts[i][1], texts[j][1])
            if overlap and area > 40:  # 经验阈值：40px² 以上视为真实重叠
                issues.append(
                    f"文字重叠: '{texts[i][0].get_text()[:12]}' × '{texts[j][0].get_text()[:12]}'")
    # 2) 文本超出 figure 边界
    fb = fig.bbox
    for t, tb in texts:
        if tb.x1 > fb.width + 2 or tb.y1 > fb.height + 2 or tb.x0 < -2 or tb.y0 < -2:
            issues.append(f"文本出界: '{t.get_text()[:12]}'")
    # 2b) 数值标签越过数据绘图区顶部（bar/line 顶标常见）
    axb = ax.get_window_extent()
    for t, tb in texts:
        txt = t.get_text().strip().replace("%", "").replace(",", "")
        if txt.replace(".", "").replace("-", "").isdigit() and tb.y1 > axb.y1 + 2:
            issues.append(f"数值标签超出绘图区: '{t.get_text()[:12]}'")
    # 3) 图例遮挡数据区（相交面积 > 数据区 8%）
    leg = ax.get_legend()
    if leg is not None:
        axb = ax.get_window_extent()
        lb = leg.get_window_extent()
        overlap, area = _bbox_overlap(axb, lb)
        if overlap and area > axb.width * axb.height * 0.08:
            issues.append("图例遮挡数据区")
    # 4) 坐标轴类别标签重叠（长分类名常见）：相邻标签相交视为重叠
    for getter_name in ("get_xticklabels", "get_yticklabels"):
        getter = getattr(ax, getter_name)
        labs = [l for l in getter() if l.get_text() and l.get_visible()]
        kind = "x轴" if getter_name == "get_xticklabels" else "y轴"
        for i in range(len(labs) - 1):
            if _bbox_overlap(labs[i].get_window_extent(),
                             labs[i + 1].get_window_extent())[0]:
                issues.append(f"{kind}类别标签重叠（分类名过长，建议缩短或旋转）")
                break
    for msg in issues:
        print(f"  [WARN] {spec.get('filename', '?' )}: {msg}")
    return issues


def generate(specs, outdir, dpi=150):
    os.makedirs(outdir, exist_ok=True)
    results = []
    for spec in specs:
        _validate_spec(spec)
        _CURRENT_SPEC.clear()
        _CURRENT_SPEC.update(spec)
        if spec["type"] == "mermaid":
            results.append({"filename": spec.get("id", "mermaid"),
                            "title": spec["title"], "type": "mermaid",
                            "size": len(spec["code"])})
            continue
        fname = spec["filename"]
        if not fname.lower().endswith(".png"):
            fname += ".png"
        out_path = os.path.join(outdir, fname)
        _DRAWERS[spec["type"]](spec, out_path)
        size = os.path.getsize(out_path)
        if size < 1024:
            raise RuntimeError(f"图表 '{fname}' 生成异常（仅 {size} 字节）")
        disp = spec.get("display_name")
        if disp:
            if not disp.lower().endswith(".png"):
                disp += ".png"
            try:
                shutil.copy2(out_path, os.path.join(outdir, disp))
            except OSError as e:
                print(f"  [WARN] {fname}: 语义副本创建失败 {disp}（{e}）")
        results.append({"filename": fname, "display_name": disp,
                        "title": spec["title"],
                        "type": spec["type"], "size": size})
    return results


def self_test(outdir):
    spec = {
        "specs": [
            {"type": "line", "title": "市场规模与增速趋势（2022-2027E）",
             "subtitle": "单位：亿元", "filename": "chart-01-market-size.png",
             "source": "艾瑞咨询 2026；前瞻产业研究院",
             "notes": ["2026-2027E 为预测值，来源标注于报告正文"],
             "data": {"x": ["2022", "2023", "2024", "2025", "2026E", "2027E"],
                      "series": [{"name": "市场规模", "values": [82, 105, 138, 172, 210, 255]},
                                 {"name": "同比增速（%）", "values": [24, 28, 31, 25, 22, 21]}]}},
            {"type": "donut", "title": "市场份额分布（2025）",
             "subtitle": "按营收计", "filename": "chart-02-market-share.png",
             "source": "各公司年报 2025；估算", "center_text": "TOP5\n68%",
             "data": {"labels": ["企业A", "企业B", "企业C", "企业D", "企业E", "其他"],
                      "values": [22, 15, 12, 10, 9, 32]}},
            {"type": "radar", "title": "头部竞品多维能力对比",
             "subtitle": "评分 0-10（自评口径）", "filename": "chart-03-competitor-radar.png",
             "source": "分析师综合评估 2026", "notes": ["评分为 0-10 综合估算"],
             "data": {"categories": ["产品功能", "客户服务", "价格竞争力", "生态集成", "品牌影响力", "技术创新"],
                      "series": [{"name": "企业A", "values": [9, 7, 6, 8, 9, 8]},
                                 {"name": "企业B", "values": [6, 8, 9, 7, 5, 6]},
                                 {"name": "企业C", "values": [5, 6, 8, 6, 4, 7]}]}},
            {"type": "hbar", "title": "各产品线价格带对比",
             "subtitle": "单位：元/年", "filename": "chart-04-price-band.png",
             "source": "官网公开报价 2026",
             "data": {"categories": ["企业A 标准版", "企业B 标准版", "企业C 标准版",
                                      "企业A 旗舰版", "企业B 旗舰版"],
                      "series": [{"name": "单价", "values": [1980, 2680, 1580, 8800, 6800]}]}},
            {"type": "heatmap", "title": "风险概率 × 影响矩阵",
             "subtitle": "1-5 分，颜色越深风险越高", "filename": "chart-05-risk-matrix.png",
             "source": "风险评估 2026", "color_scale": "risk",
             "data": {"rows": ["政策监管", "技术迭代", "竞争加剧", "需求波动", "供应链"],
                      "cols": ["影响 1", "影响 2", "影响 3", "影响 4", "影响 5"],
                      "matrix": [[1, 1, 2, 2, 3],
                                 [1, 1, 1, 2, 2],
                                 [2, 2, 3, 3, 3],
                                 [2, 2, 2, 3, 4],
                                 [1, 1, 2, 2, 3]]}},
            {"type": "bar", "title": "LTV 与 CAC 对比（核心经济模型）",
             "subtitle": "单位：元", "filename": "chart-06-ltv-cac.png",
             "source": "财务模型估算 2026", "notes": ["健康线要求 LTV > 3×CAC"],
             "data": {"categories": ["获客成本 CAC", "生命周期价值 LTV"],
                      "series": [{"name": "企业A", "values": [2200, 9800]},
                                 {"name": "企业B", "values": [1800, 6200]},
                                 {"name": "行业平均", "values": [1600, 5200]}]}},
        ]
    }
    for item in spec["specs"]:
        if item.get("type") != "mermaid":
            item.setdefault("card_id", "SELF-TEST")
            item.setdefault("source_id", "SELF-TEST")
            item.setdefault("year", 2026)
            item.setdefault("unit", "演示单位")
            item.setdefault("definition", "演示数据，仅用于验证绘图链路")
            item.setdefault("base_period", "演示区间")
            item.setdefault("position", "附录：演示")
    return generate(spec["specs"], outdir, dpi=150)


def main():
    ap = argparse.ArgumentParser(description="市场调研报告图表生成器")
    ap.add_argument("--spec", help="specs.json 路径")
    ap.add_argument("--outdir", default="charts", help="输出目录")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--self-test", action="store_true", help="内置演示数据自测")
    ap.add_argument("--list-types", action="store_true", help="列出支持图型")
    args = ap.parse_args()

    setup_chinese_font()

    if args.list_types:
        print("支持图型：" + ", ".join(_DRAWERS))
        return 0

    if args.self_test:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "self-test-output")
        results = self_test(outdir)
        print(f"[self-test] 生成 {len(results)} 张图 → {outdir}")
        for r in results:
            print(f"  ✅ {r['filename']}  {r['title']}  ({r['size']} bytes)")
        return 0

    if not args.spec:
        ap.error("请提供 --spec 或使用 --self-test")

    with open(args.spec, "r", encoding="utf-8") as f:
        payload = json.load(f)
    specs = payload.get("specs", payload) if isinstance(payload, dict) else payload
    results = generate(specs, args.outdir, dpi=args.dpi)

    print(f"[gen_chart] 生成 {len(results)} 张图 → {args.outdir}")
    for r in results:
        if r["type"] == "mermaid":
            print(f"  ⏭ {r['title']}  (mermaid 透传，{r['size']} 字符)")
        else:
            print(f"  ✅ {r['filename']}  {r['title']}  ({r['size']} bytes)")
    print("[gen_chart] 全部成功")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 —— 面向 agent 排障的完整堆栈
        import traceback
        traceback.print_exc()
        print(f"[gen_chart] ERROR: {e}", file=sys.stderr)
        sys.exit(1)