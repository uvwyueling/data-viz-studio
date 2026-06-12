"""
data-viz-studio · 种子模板 (v0)
================================
单一职责：读取用户上传的 CSV/Excel → 输出一张能向【特定技术画像的受众】
传达【一句数据洞察】的图。

设计分工：
  · 视觉风格（配色 / 字体 / 平面规范）→ 由 Valeria 定义（见下方 STYLE，现在是占位默认）
  · 受众技术画像（高 / 中 / 低）        → 由用户在调用时指定
  · 数据 + 那句洞察                      → 由用户随文件一起给出

先让它跑起来，再迭代。带〔待定义〕的地方就是留给你的部分。
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


# ── 0. 中文字体守卫（头号翻车点）────────────────────────────────
# 不设的话，matplotlib 会把所有中文静默渲染成 □□□，而且不报错。
# 这里宁可主动报错，也不交付一张全是方框的图。
def setup_cjk_font():
    candidates = ["Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC",
                  "Microsoft YaHei", "SimHei", "WenQuanYi Zen Hei"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False   # 负号正常显示
            return name
    raise RuntimeError(
        "未找到可用中文字体，请先安装一款 CJK 字体（如 fonts-noto-cjk）。"
        "宁可在这里停下，也不要静默输出方框。"
    )


# ── 1. 视觉风格〔Valeria 定义——你的部分，现在是占位默认〕──────────
STYLE = {
    "highlight": "#1f4e5f",   # 高亮色：只给"要强调的那一项"
    "muted":     "#cfd4d8",   # 灰：背景项
    "ink":       "#222222",   # 文字 / 轴线
    "grid":      "#ededed",   # 网格
    "dpi":       200,
}


# ── 2. 受众技术画像〔运行时由用户指定〕──────────────────────────
# 同一份数据，画像不同 → 标题写法、标注密度都不同。
AUDIENCE_PROFILES = {
    "high": {"label": "数据/分析专业", "title_mode": "descriptive", "annotate": False, "title_size": 15},
    "mid":  {"label": "业务/产品",     "title_mode": "takeaway",    "annotate": False, "title_size": 16},
    "low":  {"label": "高管/外行",     "title_mode": "takeaway",    "annotate": True,  "title_size": 17},
}


def _despine(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(STYLE["ink"])


def make_box_comparison(df, group_col, value_col, insight,
                        audience="mid", emphasize=None,
                        descriptive_title=None, save_to="chart.png"):
    """按组对比某数值的分布（箱线图）。insight = 用户给的那句洞察。"""
    prof = AUDIENCE_PROFILES[audience]
    grouped = list(df.groupby(group_col)[value_col])
    labels = [g for g, _ in grouped]
    data = [v.values for _, v in grouped]

    fig, ax = plt.subplots(figsize=(7, 5))
    bp = ax.boxplot(
        data, tick_labels=labels, patch_artist=True, widths=0.5,
        medianprops=dict(color=STYLE["ink"], linewidth=2),
        whiskerprops=dict(color=STYLE["ink"]),
        capprops=dict(color=STYLE["ink"]),
        flierprops=dict(marker="o", markersize=4,
                        markerfacecolor=STYLE["muted"], markeredgecolor="none"),
    )
    # 只给被强调的那一组上高亮色，其余压灰
    for patch, lab in zip(bp["boxes"], labels):
        is_emph = (emphasize is not None and lab == emphasize)
        patch.set_facecolor(STYLE["highlight"] if is_emph else STYLE["muted"])
        patch.set_edgecolor("none")

    _despine(ax)
    ax.yaxis.grid(True, color=STYLE["grid"])
    ax.set_axisbelow(True)
    ax.set_ylabel(value_col, color=STYLE["ink"])
    ax.tick_params(colors=STYLE["ink"])

    # 标题：高素养受众用中性描述，其余直接上"结论句"
    if prof["title_mode"] == "descriptive":
        title = descriptive_title or f"各{group_col}的{value_col}分布"
    else:
        title = insight
    ax.set_title(title, color=STYLE["ink"], fontsize=prof["title_size"],
                 fontweight="bold", loc="left", pad=14)

    # 低素养受众：补一句大白话标注，把差距直接说出来
    if prof["annotate"] and emphasize is not None:
        means = df.groupby(group_col)[value_col].mean()
        gap = means.max() - means.min()
        ax.annotate(f"↓ {emphasize}组平均低约 {gap:.2f}",
                    xy=(0.5, -0.16), xycoords="axes fraction", ha="center",
                    color=STYLE["highlight"], fontsize=12, fontweight="bold")

    fig.savefig(save_to, dpi=STYLE["dpi"], bbox_inches="tight")
    plt.close(fig)
    return save_to


# ── demo：证明它能跑（同一份数据，两种受众画像）───────────────────
if __name__ == "__main__":
    used = setup_cjk_font()
    print("使用字体:", used)

    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "分组": ["自选"] * 60 + ["调剂"] * 60,
        "首年GPA": np.concatenate([
            rng.normal(3.2, 0.40, 60),
            rng.normal(2.7, 0.45, 60),
        ]).clip(0, 4),
    })

    make_box_comparison(df, "分组", "首年GPA",
                        insight="调剂学生首年GPA显著更低",
                        audience="high", emphasize="调剂",
                        save_to="demo_high.png")
    make_box_comparison(df, "分组", "首年GPA",
                        insight="调剂学生首年GPA显著更低",
                        audience="low", emphasize="调剂",
                        save_to="demo_low.png")
    print("已生成 demo_high.png 与 demo_low.png")
