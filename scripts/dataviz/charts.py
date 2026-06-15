import io
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .config import _READING_GUIDE
from .fonts import setup_cjk_font
from .routing import _looks_like_rate


def _despine(ax, palette):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(palette["ink"])


def _title(ax, audience_prof, insight, descriptive, palette):
    text = descriptive if audience_prof["title_mode"] == "descriptive" else insight
    ax.set_title(text, color=palette["ink"], fontsize=16, fontweight="bold", loc="left", pad=14)


def _annotate(ax, df, group_col, value_col, emphasize, level, palette):
    """按组合后的注释档位往图上加解释。level: 0/1/2。"""
    if level <= 0 or emphasize is None:
        return
    means = df.groupby(group_col)[value_col].mean()
    gap = means.max() - means.min()
    ax.annotate(f"{emphasize}组平均低约 {gap:.2f}",
                xy=(0.5, -0.16), xycoords="axes fraction", ha="center",
                color=palette["highlight"], fontsize=12, fontweight="bold")
    if level >= 2:  # 叙事档：把每组均值直接标到图上
        for i, (g, m) in enumerate(means.items(), start=1):
            ax.annotate(f"{m:.2f}", xy=(i, m), xytext=(0, 8),
                        textcoords="offset points", ha="center",
                        color=palette["ink"], fontsize=10)


def _reading_guide(ax, chart_kind, palette, y=-0.26):
    ax.annotate(_READING_GUIDE[chart_kind],
                xy=(0.5, y), xycoords="axes fraction", ha="center",
                color=palette["muted"], fontsize=9, fontweight="normal")


def _fig_to_svg(fig):
    """把 matplotlib 图存成可内嵌、可自适应的 SVG 字符串。"""
    setup_cjk_font()
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    svg = buf.getvalue()
    svg = svg[svg.find("<svg"):]                       # 去掉 XML 声明 / DOCTYPE，便于内嵌
    svg = re.sub(r'(<svg[^>]*?)\s+width="[\d.]+pt"\s+height="[\d.]+pt"',
                 r"\1", svg, count=1)                   # 去掉固定 pt 宽高，靠 viewBox + CSS 自适应
    return svg


def _clip_boxplot_view(ax, grouped_values, palette, *, annotate=None):
    """偏态/离群点过多时夹到须线范围附近，并无条件标注被移出视野的离群点。"""
    groups = [np.asarray(values, dtype=float) for values in grouped_values]
    groups = [values[np.isfinite(values)] for values in groups if len(values)]
    groups = [values for values in groups if len(values)]
    if not groups:
        return False

    all_values = np.concatenate(groups)
    actual_lo, actual_hi = float(all_values.min()), float(all_values.max())
    actual_span = actual_hi - actual_lo
    whisker_lows, whisker_highs = [], []
    outlier_count = 0
    for values in groups:
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        whisker_lows.append(lo)
        whisker_highs.append(hi)
        outlier_count += int(((values < lo) | (values > hi)).sum())

    w_lo, w_hi = min(whisker_lows), max(whisker_highs)
    whisker_span = w_hi - w_lo
    if whisker_span <= 0:
        return False
    outlier_ratio = outlier_count / len(all_values)
    if actual_span <= 3 * whisker_span and outlier_ratio <= 0.05:
        return False

    margin = whisker_span * 0.08
    view_lo, view_hi = w_lo - margin, w_hi + margin
    hidden_count = int(((all_values < view_lo) | (all_values > view_hi)).sum())
    if hidden_count <= 0:
        return False

    ax.set_ylim(view_lo, view_hi)
    note = f"另有 {hidden_count} 个离群点超出显示范围（实际范围 [{actual_lo:g}, {actual_hi:g}]）"
    if annotate is None:
        ax.annotate(r"$\blacktriangle$ " + note,
                    xy=(0.5, -0.16), xycoords="axes fraction", ha="center",
                    color=palette["ink"], fontsize=9)
    else:
        annotate(r"$\blacktriangle$ " + note)
    return True


# ── 图型基元（返回 SVG 字符串）──────────────────────────────────
def box_comparison(df, group_col, value_col, *, insight, descriptive,
                   palette, audience_prof, level, emphasize):
    """箱线图：给得懂分布的受众。"""
    grouped = list(df.groupby(group_col)[value_col])
    labels = [g for g, _ in grouped]
    data = [v.values for _, v in grouped]
    fig, ax = plt.subplots(figsize=(7, 5))
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.5,
                    medianprops=dict(color=palette["ink"], linewidth=2),
                    whiskerprops=dict(color=palette["ink"]),
                    capprops=dict(color=palette["ink"]),
                    flierprops=dict(marker="o", markersize=4,
                                    markerfacecolor=palette["muted"], markeredgecolor="none"))
    for patch, lab in zip(bp["boxes"], labels):
        emph = (emphasize is not None and lab == emphasize)
        patch.set_facecolor(palette["highlight"] if emph else palette["muted"])
        patch.set_edgecolor("none")
    _despine(ax, palette); ax.yaxis.grid(True, color=palette["grid"]); ax.set_axisbelow(True)
    ax.set_ylabel(value_col, color=palette["ink"]); ax.tick_params(colors=palette["ink"])
    _title(ax, audience_prof, insight, descriptive, palette)
    if level >= 1:
        _reading_guide(ax, "box", palette)
    _clip_boxplot_view(ax, data, palette)
    return _fig_to_svg(fig)


def bar_means_comparison(df, group_col, value_col, *, insight, descriptive,
                         palette, audience_prof, level, emphasize):
    """均值 + 范围条：箱线图的"降级翻译"，给统计基础弱的受众。"""
    agg = df.groupby(group_col)[value_col].agg(["mean", "std"])
    labels = list(agg.index)
    means, stds = agg["mean"].values, agg["std"].values
    colors = [palette["highlight"] if (emphasize is not None and lab == emphasize)
              else palette["muted"] for lab in labels]
    tops = means + np.nan_to_num(stds)   # 标签锚到误差棒上端之上，避免压住横帽（自检 P1）
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, means, width=0.55, color=colors, edgecolor="none",
           yerr=stds, capsize=6, error_kw=dict(ecolor=palette["ink"], lw=1))
    for i, m in enumerate(means):  # 均值直接标出——低画像受众不用读坐标轴
        ax.annotate(f"{m:.2f}", xy=(i, tops[i]), xytext=(0, 6), textcoords="offset points",
                    ha="center", color=palette["ink"], fontsize=11, fontweight="bold")
    _despine(ax, palette); ax.yaxis.grid(True, color=palette["grid"]); ax.set_axisbelow(True)
    ax.set_ylabel(f"{value_col}（均值 $\\pm$ 标准差）", color=palette["ink"]); ax.tick_params(colors=palette["ink"])
    _title(ax, audience_prof, insight, descriptive, palette)
    _annotate(ax, df, group_col, value_col, emphasize, level, palette)
    return _fig_to_svg(fig)


def _wilson_ci(p, n, z=1.96):
    """Wilson 95% 置信区间（向量化）。关键：结果恒落在 [0,1] 内，
    不会像 ±std 那样把比例的误差棒画到负数或超过 100%。"""
    p = np.asarray(p, float); n = np.asarray(n, float)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return np.clip(center - half, 0, 1), np.clip(center + half, 0, 1)


def _annotate_rate(ax, rates, labels, emphasize, level, palette):
    """比率图的注释：用「百分点」说话，而不是 0.xx。"""
    if level <= 0 or emphasize is None or emphasize not in labels:
        return
    gap_pp = (max(rates) - dict(zip(labels, rates))[emphasize]) * 100
    if gap_pp < 1:   # 被强调的恰好是最高组，没有"低多少"可说
        return
    ax.annotate(f"{emphasize} 比最高组低约 {gap_pp:.0f} 个百分点",
                xy=(0.5, -0.16), xycoords="axes fraction", ha="center",
                color=palette["highlight"], fontsize=12, fontweight="bold")


def rate_comparison(df, group_col, value_col, *, insight, descriptive,
                    palette, audience_prof, level, emphasize, show_ci=False):
    """比率图：专给「分类 × 0/1 比例」用（生还率、转化率、合格率…）。
    柱高 = 比例(%)，**绝不画 ±std**——0/1 变量 std≈0.5，误差棒会冲出 [0,100%] 把人教错。
    show_ci=True 时改画 Wilson 95% 置信区间（恒在 [0,1] 内），给技术受众看不确定性。
    """
    from matplotlib.ticker import PercentFormatter
    agg = df.groupby(group_col)[value_col].agg(["mean", "count"])
    labels = list(agg.index)
    rates, ns = agg["mean"].values, agg["count"].values
    colors = [palette["highlight"] if (emphasize is not None and lab == emphasize)
              else palette["muted"] for lab in labels]

    yerr = None
    label_y = rates                       # 默认：标签贴柱顶
    if show_ci:
        lo, hi = _wilson_ci(rates, ns)
        yerr = np.vstack([np.clip(rates - lo, 0, None), np.clip(hi - rates, 0, None)])
        label_y = hi                      # 有误差棒时把标签抬到 CI 上端之上，避开横帽

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, rates, width=0.55, color=colors, edgecolor="none",
           yerr=yerr, capsize=6 if show_ci else 0, error_kw=dict(ecolor=palette["ink"], lw=1))
    for i, r in enumerate(rates):  # 直接标百分比——受众不用读坐标轴；锚点避开误差棒
        ax.annotate(f"{r:.0%}", xy=(i, label_y[i]), xytext=(0, 6), textcoords="offset points",
                    ha="center", color=palette["ink"], fontsize=11, fontweight="bold")
    _despine(ax, palette); ax.yaxis.grid(True, color=palette["grid"]); ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    # 默认给足 0~100% 的整轴（比例本就是"占多少"，不截断更诚实）；比例都很小才放大看
    top = 1.0 if rates.max() >= 0.25 else min(1.0, float(rates.max()) * 1.8)
    ax.set_ylim(0, top)
    ax.set_ylabel(f"{value_col}（占比）", color=palette["ink"]); ax.tick_params(colors=palette["ink"])
    _title(ax, audience_prof, insight, descriptive, palette)
    _annotate_rate(ax, rates, labels, emphasize, level, palette)
    return _fig_to_svg(fig)


# ── 分组对比图元：两/多子总体跨类别对比（hue_col 把每个类别再切几条）────
def _series_colors(palette, hues, emphasize_hue):
    """给每个 hue 系列定色：被强调的系列用 highlight，其余用 muted（中性灰）。
    没指定强调时，默认强调排序后的最后一个系列——让"对照 → 重点"有个落点。"""
    if emphasize_hue is None and hues:
        emphasize_hue = hues[-1]
    return {h: (palette["highlight"] if h == emphasize_hue else palette["muted"]) for h in hues}


def _grouped_positions(n_groups, hi, n_h, width):
    """第 hi 个 hue 系列、在 n_groups 个类别下的并排 x 坐标。"""
    offset = (hi - (n_h - 1) / 2) * width
    return [gi + offset for gi in range(n_groups)]


def grouped_box_comparison(df, group_col, value_col, hue_col, *, insight, descriptive,
                           palette, audience_prof, level, emphasize=None, emphasize_hue=None):
    """分组箱线图：x=group_col 的每个类别下，按 hue_col 并排多个箱体。
    用于"两/多子总体跨类别对比"，如 各舱位 × 生还与否 的年龄分布。"""
    from matplotlib.patches import Patch
    groups = sorted(df[group_col].dropna().unique())
    hues = sorted(df[hue_col].dropna().unique())
    colors = _series_colors(palette, hues, emphasize_hue)
    n_h = len(hues); width = 0.8 / max(1, n_h)
    all_data = []

    fig, ax = plt.subplots(figsize=(7.5, 5))
    for hi, hue in enumerate(hues):
        positions = _grouped_positions(len(groups), hi, n_h, width)
        data = [df[(df[group_col] == g) & (df[hue_col] == hue)][value_col].dropna().values
                for g in groups]
        all_data.extend(data)
        bp = ax.boxplot(data, positions=positions, widths=width * 0.9, patch_artist=True,
                        medianprops=dict(color=palette["ink"], linewidth=1.5),
                        whiskerprops=dict(color=palette["ink"]),
                        capprops=dict(color=palette["ink"]),
                        flierprops=dict(marker="o", markersize=3,
                                        markerfacecolor=palette["muted"], markeredgecolor="none"))
        for patch in bp["boxes"]:
            patch.set_facecolor(colors[hue]); patch.set_edgecolor("none")

    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups)
    _despine(ax, palette); ax.yaxis.grid(True, color=palette["grid"]); ax.set_axisbelow(True)
    ax.set_ylabel(value_col, color=palette["ink"]); ax.tick_params(colors=palette["ink"])
    ax.legend(handles=[Patch(facecolor=colors[h], label=str(h)) for h in hues],
              title=hue_col, frameon=False, loc="best")
    _title(ax, audience_prof, insight, descriptive, palette)
    if level >= 1:
        _reading_guide(ax, "grouped_box", palette)
    _clip_boxplot_view(ax, all_data, palette)
    return _fig_to_svg(fig)


def grouped_bar_means_comparison(df, group_col, value_col, hue_col, *, insight, descriptive,
                                 palette, audience_prof, level, emphasize=None, emphasize_hue=None):
    """分组均值条：分组箱线图给低受众的"降级翻译"。每类别下按 hue 并排柱，柱高=均值、误差棒=std。"""
    from matplotlib.patches import Patch
    groups = sorted(df[group_col].dropna().unique())
    hues = sorted(df[hue_col].dropna().unique())
    colors = _series_colors(palette, hues, emphasize_hue)
    n_h = len(hues); width = 0.8 / max(1, n_h)

    fig, ax = plt.subplots(figsize=(7.5, 5))
    for hi, hue in enumerate(hues):
        positions = _grouped_positions(len(groups), hi, n_h, width)
        sub = df[df[hue_col] == hue].groupby(group_col)[value_col]
        means = [sub.mean().get(g, np.nan) for g in groups]
        stds = [sub.std().get(g, np.nan) for g in groups]
        ax.bar(positions, means, width=width * 0.9, color=colors[hue], edgecolor="none",
               yerr=stds, capsize=4, error_kw=dict(ecolor=palette["ink"], lw=1))
        if level >= 1:  # 低受众：均值直接标出，锚到误差棒上端之上（自检 P1）
            for x, mv, sv in zip(positions, means, stds):
                if mv == mv:  # 跳过 NaN
                    top = mv + (sv if sv == sv else 0)
                    ax.annotate(f"{mv:.0f}", xy=(x, top), xytext=(0, 4), textcoords="offset points",
                                ha="center", color=palette["ink"], fontsize=9, fontweight="bold")

    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups)
    _despine(ax, palette); ax.yaxis.grid(True, color=palette["grid"]); ax.set_axisbelow(True)
    ax.set_ylabel(f"{value_col}（均值 $\\pm$ 标准差）", color=palette["ink"]); ax.tick_params(colors=palette["ink"])
    ax.legend(handles=[Patch(facecolor=colors[h], label=str(h)) for h in hues],
              title=hue_col, frameon=False, loc="best")
    _title(ax, audience_prof, insight, descriptive, palette)
    return _fig_to_svg(fig)


# ── 新增图型基元（v0.8）────────────────────────────────────────────

def histogram_distribution(df, value_col, *, insight, descriptive,
                           palette, audience_prof, level, emphasize=None,
                           hue_col=None, bins="auto"):
    """单变量分布直方图。hue_col 给了则叠加多组分布（半透明，便于比较形状）。
    适合 mid/high 受众；low 受众由路由改走 kpi_number。
    level >= 1 时在均值处画一条虚线参考线，帮助读者定位中心。"""
    fig, ax = plt.subplots(figsize=(7, 5))

    if hue_col is not None:
        hues = sorted(df[hue_col].dropna().unique())
        colors = _series_colors(palette, hues, emphasize)
        for hue in hues:
            vals = df[df[hue_col] == hue][value_col].dropna()
            ax.hist(vals, bins=bins, color=colors[hue],
                    edgecolor="none", alpha=0.72, label=str(hue))
        ax.legend(title=hue_col, frameon=False, loc="upper right")
    else:
        ax.hist(df[value_col].dropna(), bins=bins,
                color=palette["highlight"], edgecolor="none", alpha=0.85)

    if level >= 1:
        mean_val = df[value_col].dropna().mean()
        ax.axvline(mean_val, color=palette["ink"], linestyle="--",
                   linewidth=1.2, alpha=0.75)
        ylim = ax.get_ylim()
        ax.annotate(f"均值 {mean_val:.1f}",
                    xy=(mean_val, ylim[1] * 0.88),
                    xytext=(6, 0), textcoords="offset points",
                    color=palette["ink"], fontsize=10, fontweight="bold")

    _despine(ax, palette)
    ax.yaxis.grid(True, color=palette["grid"])
    ax.set_axisbelow(True)
    ax.set_xlabel(value_col, color=palette["ink"])
    ax.set_ylabel("频次", color=palette["ink"])
    ax.tick_params(colors=palette["ink"])
    _title(ax, audience_prof, insight, descriptive, palette)
    return _fig_to_svg(fig)


def line_trend(df, group_col, value_col, *, insight, descriptive,
               palette, audience_prof, level, emphasize=None, hue_col=None):
    """折线趋势图：x 轴为时间或有序序列，y 轴为各期均值。
    hue_col 给了则画多条线（一条线 = 一个子总体）。
    level >= 1 时在每个数据点标出数值，帮助低受众不必读坐标轴。"""
    fig, ax = plt.subplots(figsize=(8, 5))

    if hue_col is not None:
        hues = sorted(df[hue_col].dropna().unique())
        colors = _series_colors(palette, hues, emphasize)
        all_xs = []
        for hue in hues:
            sub = df[df[hue_col] == hue].groupby(group_col)[value_col].mean()
            xs, ys = list(sub.index), sub.values
            all_xs = xs  # 取最后一个系列的 x 轴（假设各系列 x 对齐）
            ax.plot(xs, ys, color=colors[hue], linewidth=2.5,
                    marker="o", markersize=6, label=str(hue))
            if level >= 1:
                for x, y in zip(xs, ys):
                    ax.annotate(f"{y:.1f}", xy=(x, y), xytext=(0, 8),
                                textcoords="offset points", ha="center",
                                color=colors[hue], fontsize=9, fontweight="bold")
        ax.legend(title=hue_col, frameon=False, loc="best")
    else:
        agg = df.groupby(group_col)[value_col].mean()
        xs, ys = list(agg.index), agg.values
        all_xs = xs
        ax.plot(xs, ys, color=palette["highlight"], linewidth=2.5,
                marker="o", markersize=7)
        if level >= 1:
            for x, y in zip(xs, ys):
                ax.annotate(f"{y:.1f}", xy=(x, y), xytext=(0, 8),
                            textcoords="offset points", ha="center",
                            color=palette["ink"], fontsize=11, fontweight="bold")

    if len(all_xs) > 6:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    _despine(ax, palette)
    ax.yaxis.grid(True, color=palette["grid"])
    ax.set_axisbelow(True)
    ax.set_xlabel(group_col, color=palette["ink"])
    ax.set_ylabel(value_col, color=palette["ink"])
    ax.tick_params(colors=palette["ink"])
    _title(ax, audience_prof, insight, descriptive, palette)
    return _fig_to_svg(fig)


def kpi_number(df, value_col, *, insight, descriptive,
               palette, audience_prof, level, emphasize=None):
    """大数字 KPI：低受众的单指标摘要——把最重要的数字放到最大。
    自动检测 0/1 列并以百分比格式呈现；其余列展示均值。
    level >= 1（低受众）时在图底部补一句结论（insight）。"""
    s = df[value_col].dropna()
    is_rate = _looks_like_rate(s)
    val = s.mean()
    n = len(s)

    if is_rate:
        val_fmt = f"{val:.0%}"
        unit_label = "（占比）"
    elif val == int(val):
        val_fmt = f"{int(val):,}"
        unit_label = ""
    elif abs(val) >= 100:
        val_fmt = f"{val:,.1f}"
        unit_label = "（均值）"
    else:
        val_fmt = f"{val:.2f}"
        unit_label = "（均值）"

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.axis("off")
    # 大数字
    ax.text(0.5, 0.60, val_fmt, transform=ax.transAxes,
            ha="center", va="center", fontsize=72, fontweight="900",
            color=palette["highlight"])
    # 指标标签
    ax.text(0.5, 0.28, f"{value_col}{unit_label}", transform=ax.transAxes,
            ha="center", va="center", fontsize=15, color=palette["ink"])
    # 样本量
    ax.text(0.5, 0.12, f"n = {n:,}", transform=ax.transAxes,
            ha="center", va="center", fontsize=11, color=palette["muted"])
    # 一句结论（level >= 1 = 低受众必有）
    if level >= 1 and insight:
        fig.text(0.5, 0.02, insight, ha="center", fontsize=10,
                 color=palette["ink"], fontweight="bold")

    return _fig_to_svg(fig)


# ── 分面（small multiples）、相关图、热力图（v0.8 续）────────────────

def facet_box_comparison(df, group_col, value_col, facet_col, *, insight, descriptive,
                         palette, audience_prof, level, emphasize=None):
    """小多图（箱线）：每个 facet_col 值独立一个子图，子图内按 group_col 分组画箱线。
    sharey=True 确保跨面板 y 轴可比；level >= 1 时图底补一句结论。"""
    facets = sorted(df[facet_col].dropna().unique())
    n_f = len(facets)
    ncols = min(3, n_f)
    nrows = (n_f + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.8 * nrows),
                             sharey=True, squeeze=False)
    axes_flat = axes.flatten()
    all_grouped = []

    for i, facet in enumerate(facets):
        ax = axes_flat[i]
        sub = df[df[facet_col] == facet]
        grouped = [(g, v.dropna().values) for g, v in sub.groupby(group_col)[value_col]]
        labels, data = zip(*grouped) if grouped else ([], [])
        all_grouped.extend(data)
        bp = ax.boxplot(list(data), tick_labels=list(labels), patch_artist=True, widths=0.5,
                        medianprops=dict(color=palette["ink"], linewidth=1.5),
                        whiskerprops=dict(color=palette["ink"]),
                        capprops=dict(color=palette["ink"]),
                        flierprops=dict(marker="o", markersize=3,
                                        markerfacecolor=palette["muted"], markeredgecolor="none"))
        for patch, lab in zip(bp["boxes"], labels):
            emph = (emphasize is not None and lab == emphasize)
            patch.set_facecolor(palette["highlight"] if emph else palette["muted"])
            patch.set_edgecolor("none")
        ax.set_title(f"{facet_col} = {facet}", fontsize=11, color=palette["ink"], pad=6)
        _despine(ax, palette)
        ax.yaxis.grid(True, color=palette["grid"])
        ax.set_axisbelow(True)
        ax.set_ylabel(value_col if i % ncols == 0 else "", color=palette["ink"])
        ax.tick_params(colors=palette["ink"])

    for j in range(i + 1, len(axes_flat)):
        axes_flat[j].set_visible(False)

    title_text = descriptive if audience_prof["title_mode"] == "descriptive" else insight
    fig.suptitle(title_text, color=palette["ink"], fontsize=14, fontweight="bold")
    if level >= 1:
        fig.text(0.5, 0.01, _READING_GUIDE["facet_box"], ha="center", fontsize=9,
                 color=palette["muted"], fontweight="normal")
    _clip_boxplot_view(
        axes_flat[0], all_grouped, palette,
        annotate=lambda note: fig.text(0.5, -0.025, note, ha="center", fontsize=9, color=palette["ink"]),
    )
    fig.tight_layout()
    return _fig_to_svg(fig)


def facet_bar_means_comparison(df, group_col, value_col, facet_col, *, insight, descriptive,
                               palette, audience_prof, level, emphasize=None):
    """小多图（均值条）：分面箱线对低受众的降级版。每面板内均值柱 + std 误差棒 + 直接标值。"""
    facets = sorted(df[facet_col].dropna().unique())
    n_f = len(facets)
    ncols = min(3, n_f)
    nrows = (n_f + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.8 * nrows),
                             sharey=True, squeeze=False)
    axes_flat = axes.flatten()

    for i, facet in enumerate(facets):
        ax = axes_flat[i]
        sub = df[df[facet_col] == facet]
        agg = sub.groupby(group_col)[value_col].agg(["mean", "std"])
        labels = list(agg.index)
        means, stds = agg["mean"].values, agg["std"].values
        colors = [palette["highlight"] if (emphasize is not None and lab == emphasize)
                  else palette["muted"] for lab in labels]
        tops = means + np.nan_to_num(stds)
        ax.bar(labels, means, color=colors, edgecolor="none", width=0.55,
               yerr=stds, capsize=5, error_kw=dict(ecolor=palette["ink"], lw=1))
        for xi, mv, top in zip(range(len(labels)), means, tops):
            ax.annotate(f"{mv:.1f}", xy=(xi, top), xytext=(0, 5),
                        textcoords="offset points", ha="center",
                        color=palette["ink"], fontsize=9, fontweight="bold")
        ax.set_title(f"{facet_col} = {facet}", fontsize=11, color=palette["ink"], pad=6)
        _despine(ax, palette)
        ax.yaxis.grid(True, color=palette["grid"])
        ax.set_axisbelow(True)
        ax.set_ylabel(value_col if i % ncols == 0 else "", color=palette["ink"])
        ax.tick_params(colors=palette["ink"])

    for j in range(i + 1, len(axes_flat)):
        axes_flat[j].set_visible(False)

    title_text = descriptive if audience_prof["title_mode"] == "descriptive" else insight
    fig.suptitle(title_text, color=palette["ink"], fontsize=14, fontweight="bold")
    if level >= 1:
        fig.text(0.5, 0.01, insight, ha="center", fontsize=11,
                 color=palette["highlight"], fontweight="bold")
    fig.tight_layout()
    return _fig_to_svg(fig)


def _draw_regression(ax, x, y, color, level, row_offset=0):
    """画回归线；level >= 1 时标注 R^2 和方向（row_offset 用于多系列避免标注重叠）。"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 2:
        return
    m, b = np.polyfit(x, y, 1)
    x_plot = np.array([x.min(), x.max()])
    ax.plot(x_plot, m * x_plot + b, color=color, linewidth=1.8, linestyle="--", alpha=0.8)
    if level >= 1:
        y_pred = m * x + b
        ss_res = ((y - y_pred) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        direction = "正相关" if m > 0 else "负相关"
        ax.annotate(f"{direction}，$R^2$={r2:.2f}",
                    xy=(0.04, 0.93 - row_offset * 0.09), xycoords="axes fraction",
                    color=color, fontsize=10, fontweight="bold")


def scatter_regression(df, x_col, y_col, *, insight, descriptive,
                       palette, audience_prof, level, emphasize=None, hue_col=None):
    """散点图 + 线性回归线：探索两个连续变量的关系。
    hue_col 给了则分颜色显示各子总体并分别画回归线。
    调用方式：visualize(df, x_col, y_col, chart_kind='scatter', ...)。"""
    fig, ax = plt.subplots(figsize=(7, 5))

    if hue_col is not None:
        hues = sorted(df[hue_col].dropna().unique())
        colors = _series_colors(palette, hues, emphasize)
        for offset, hue in enumerate(hues):
            sub = df[df[hue_col] == hue][[x_col, y_col]].dropna()
            ax.scatter(sub[x_col], sub[y_col], c=colors[hue],
                       alpha=0.55, s=28, edgecolors="none", label=str(hue))
            _draw_regression(ax, sub[x_col], sub[y_col], colors[hue], level, offset)
        ax.legend(title=hue_col, frameon=False)
    else:
        clean = df[[x_col, y_col]].dropna()
        ax.scatter(clean[x_col], clean[y_col], c=palette["highlight"],
                   alpha=0.55, s=28, edgecolors="none")
        _draw_regression(ax, clean[x_col], clean[y_col], palette["highlight"], level)

    _despine(ax, palette)
    ax.yaxis.grid(True, color=palette["grid"])
    ax.xaxis.grid(True, color=palette["grid"])
    ax.set_axisbelow(True)
    ax.set_xlabel(x_col, color=palette["ink"])
    ax.set_ylabel(y_col, color=palette["ink"])
    ax.tick_params(colors=palette["ink"])
    _title(ax, audience_prof, insight, descriptive, palette)
    return _fig_to_svg(fig)


def heatmap_comparison(df, row_col, col_col, value_col, *, insight, descriptive,
                       palette, audience_prof, level, emphasize=None):
    """热力图：row_col × col_col 交叉均值，颜色深浅 = value_col 均值，格子内始终标数值。
    调用方式：visualize(df, group_col=row_col, hue_col=col_col, value_col=…, chart_kind='heatmap', …)。"""
    from matplotlib.colors import LinearSegmentedColormap
    pivot = df.groupby([row_col, col_col])[value_col].mean().unstack(col_col)
    n_rows, n_cols = pivot.shape
    fig, ax = plt.subplots(figsize=(max(5, n_cols * 1.5), max(4, n_rows * 0.9)))

    cmap = LinearSegmentedColormap.from_list("em", ["#f0f4f8", palette["highlight"]])
    im = ax.imshow(pivot.values, cmap=cmap, aspect="auto")

    ax.set_xticks(range(n_cols)); ax.set_xticklabels(pivot.columns, rotation=30, ha="right",
                                                       color=palette["ink"])
    ax.set_yticks(range(n_rows)); ax.set_yticklabels(pivot.index, color=palette["ink"])
    ax.set_xlabel(col_col, color=palette["ink"])
    ax.set_ylabel(row_col, color=palette["ink"])
    ax.tick_params(colors=palette["ink"])

    vmax = np.nanmax(pivot.values)
    for i in range(n_rows):
        for j in range(n_cols):
            val = pivot.iloc[i, j]
            if not pd.isna(val):
                text_color = "white" if (vmax > 0 and val / vmax > 0.55) else palette["ink"]
                ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                        color=text_color, fontsize=10, fontweight="bold")

    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.ax.tick_params(colors=palette["ink"], labelsize=9)
    cbar.set_label(value_col, color=palette["ink"], fontsize=10)

    _title(ax, audience_prof, insight, descriptive, palette)
    if level >= 1:
        _reading_guide(ax, "heatmap", palette, y=-0.32)
    fig.tight_layout()
    return _fig_to_svg(fig)
