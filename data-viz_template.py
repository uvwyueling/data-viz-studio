"""
data-viz-studio · 种子模板 (v0.5)
==================================
单一职责：读取用户上传的 CSV/Excel → 输出能回答【数据问题】、并向【特定技术画像受众】、
在【特定使用场合】下以最低沟通成本传达洞察的可视化图。

── 输出（v0.3 变更）────────────────────────────────────────────
路线 A：matplotlib 出图 → 存成 SVG → 内嵌进一个自包含的 HTML 页面。
所有判断逻辑（场合配色 / 受众降级 / 注释组合）原样保留，只换了最后的输出层。

── 分层（重要）────────────────────────────────────────────────
本文件 = 确定性渲染层：套配色、选图型/降级、定注释、出图。
找洞察那一步（分析数据问题 → 挖出 insight）是【推理】，留在 SKILL.md 里由 Claude 做；
本文件只接收一个已被推理出来的 `insight` 字符串，负责把它渲染好。
"""

import io
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


# ── 0. 中文字体守卫 + SVG 字形外框化（头号翻车点，HTML 版）──────────
_CJK_PROBE = "中"  # 拿这个字去探：某字体到底有没有中文字形（不靠字体名，靠真查字形表）

# 三级兜底全落空时，按文件路径强行注册的常见系统中文字体（存在才用）。
# 专治 macOS：PingFang/STHeiti 等是 .ttc 集合，matplotlib 常按名枚举不到。
_KNOWN_CJK_FILES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def _has_cjk_glyph(font_path):
    """这个字体文件里到底有没有中文字形？不信字体名，直接查字形表。"""
    from matplotlib.ft2font import FT2Font
    try:
        return FT2Font(font_path).get_char_index(ord(_CJK_PROBE)) != 0
    except Exception:
        return False


def _scan_registered_cjk():
    """遍历 matplotlib 已注册字体，挑第一个真能渲染中文的；偏好干净黑体/无衬线，避开装饰体。"""
    seen, hits = set(), []
    for f in fm.fontManager.ttflist:
        if f.name in seen:
            continue
        seen.add(f.name)
        if _has_cjk_glyph(f.fname):
            hits.append(f.name)
    if not hits:
        return None

    def score(n):  # 0=黑体/无衬线优先，1=宋/明，2=其它
        s = n.lower()
        if any(k in s for k in ["hei", "黑", "gothic", "sans", "yahei", "pingfang", "yuan", "圆"]):
            return 0
        if any(k in s for k in ["song", "宋", "ming", "mincho", "serif"]):
            return 1
        return 2

    return sorted(hits, key=score)[0]


def _register_known_cjk():
    """连扫描都落空（系统字体多为 .ttc、没被 matplotlib 枚举进来），按已知路径强行注册一个。"""
    import os
    for path in _KNOWN_CJK_FILES:
        if os.path.exists(path) and _has_cjk_glyph(path):
            fm.fontManager.addfont(path)
            return next((f.name for f in fm.fontManager.ttflist if f.fname == path), None)
    return None


def setup_cjk_font():
    # 1) 先试"指名道姓"的常用中文字体：命中最稳，渲染质量也可控
    preferred = ["Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC",
                 "Heiti SC", "STHeiti", "Hiragino Sans GB", "Arial Unicode MS",
                 "Microsoft YaHei", "SimHei", "WenQuanYi Zen Hei"]
    available = {f.name for f in fm.fontManager.ttflist}
    chosen = next((n for n in preferred if n in available), None)

    # 2) 名单落空 → 扫描已注册字体里任何一个真含中文字形的（macOS 上多半走这条）
    if chosen is None:
        chosen = _scan_registered_cjk()

    # 3) 还落空 → 按已知系统路径强行注册（专治 .ttc 没被枚举）
    if chosen is None:
        chosen = _register_known_cjk()

    if chosen is None:
        raise RuntimeError("未找到可用中文字体，请先安装 CJK 字体；宁可报错也不要静默输出 □□□。")

    plt.rcParams["font.sans-serif"] = [chosen]
    plt.rcParams["axes.unicode_minus"] = False
    # 关键：把 SVG 里的文字转成矢量路径（path），而不是留作依赖字体的 <text>。
    # 这样生成时需要中文字体（这里已校验），但【浏览器端不再需要任何字体】，
    # 中文永远按路径渲染——HTML 世界里的 □□□ 风险被结构性根除。
    plt.rcParams["svg.fonttype"] = "path"
    return chosen


# ── 0.5 数据读取：把用户上传的文件读成 DataFrame（visualize 的入口）────
def load_dataframe(path):
    """按扩展名分发读取 CSV/Excel/JSON，处理编码并做基础清洗，返回干净的 DataFrame。

    visualize() 只接收 df；从"用户上传的文件"到 df 的这一步由这里负责。
    """
    import os
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = _read_csv_smart(path)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)          # .xlsx 需 openpyxl，.xls 需 xlrd
    elif ext == ".json":
        df = _read_json_smart(path)
    else:
        raise ValueError(f"不支持的文件类型：{ext}（仅支持 .csv / .xlsx / .xls / .json）")
    return _basic_clean(df)


def _read_csv_smart(path):
    """CSV 编码逐个试：UTF-8 → GBK → UTF-8-SIG。
    中文 CSV 头号翻车点就是编码：Excel 导出常是 GBK，带 BOM 的是 utf-8-sig。
    先试 UTF-8（自校验，不是合法 UTF-8 会抛错），再退 GBK——顺序很关键，能避开乱码。
    """
    last_err = None
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    raise UnicodeError(f"CSV 编码无法识别（已试 utf-8/gbk/utf-8-sig）：{path}") from last_err


def _read_json_smart(path):
    """JSON：先 read_json；不行再 json.load + json_normalize（兼容对象/嵌套/records 各种形状）。"""
    try:
        return pd.read_json(path)
    except ValueError:
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return pd.json_normalize(data)


def _basic_clean(df):
    """基础清洗：列名去首尾空格、丢全空的行与列、去重复行。只整形不改数据值本身。"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")   # 全空的行/列
    return df.drop_duplicates().reset_index(drop=True)


# ── 1. 使用场合 → 配色 + 注释基准〔Valeria 校准〕────────────────────
# annotate_base: 图上注释的"基准档"（0=最少，靠标题/图注；1=补一句关键标注；2=叙事式多标注）
OCCASION_PROFILES = {
    "journal": {   # 理科期刊图：色盲安全、克制、细节靠图注承载
        "label": "理科期刊图", "annotate_base": 0,
        "palette": {"highlight": "#4C72B0", "muted": "#BFC4CB", "ink": "#1a1a1a", "grid": "#ececec"},
    },
    "keynote": {   # 大型公众演讲单页：大字大色块、讲者口头解释、图上文字极少
        "label": "公众演讲单页", "annotate_base": 0,
        "palette": {"highlight": "#E4572E", "muted": "#D9DCE1", "ink": "#222222", "grid": "#efefef"},
    },
    "internal": {  # 团队内部汇报：自己看、无讲者，需中等注释
        "label": "团队内部汇报", "annotate_base": 1,
        "palette": {"highlight": "#2F6690", "muted": "#CDD3D9", "ink": "#222222", "grid": "#ededed"},
    },
    "portfolio": { # 作品集 / 对外讲故事：自含叙事、引导式标注
        "label": "作品集/对外", "annotate_base": 2,
        "palette": {"highlight": "#1F4E5F", "muted": "#CBD3D3", "ink": "#1a1a1a", "grid": "#eaeaea"},
    },
}


# ── 2. 受众技术画像 → 图型降级 + 注释加成 + 标题写法〔运行时由用户指定〕──
AUDIENCE_PROFILES = {
    "high": {"label": "数据/分析专业", "downgrade": False, "annotate_bump": 0, "title_mode": "descriptive"},
    "mid":  {"label": "业务/产品",     "downgrade": False, "annotate_bump": 0, "title_mode": "takeaway"},
    "low":  {"label": "高管/外行",     "downgrade": True,  "annotate_bump": 1, "title_mode": "takeaway"},
}

ANNOTATE_MAX = 2


# ── 工具 ────────────────────────────────────────────────────────
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
    ax.annotate(f"↓ {emphasize}组平均低约 {gap:.2f}",
                xy=(0.5, -0.16), xycoords="axes fraction", ha="center",
                color=palette["highlight"], fontsize=12, fontweight="bold")
    if level >= 2:  # 叙事档：把每组均值直接标到图上
        for i, (g, m) in enumerate(means.items(), start=1):
            ax.annotate(f"{m:.2f}", xy=(i, m), xytext=(0, 8),
                        textcoords="offset points", ha="center",
                        color=palette["ink"], fontsize=10)


def _fig_to_svg(fig):
    """把 matplotlib 图存成可内嵌、可自适应的 SVG 字符串。"""
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    svg = buf.getvalue()
    svg = svg[svg.find("<svg"):]                       # 去掉 XML 声明 / DOCTYPE，便于内嵌
    svg = re.sub(r'(<svg[^>]*?)\s+width="[\d.]+pt"\s+height="[\d.]+pt"',
                 r"\1", svg, count=1)                   # 去掉固定 pt 宽高，靠 viewBox + CSS 自适应
    return svg


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
    _annotate(ax, df, group_col, value_col, emphasize, level, palette)
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
    ax.set_ylabel(f"{value_col}（均值 ± 标准差）", color=palette["ink"]); ax.tick_params(colors=palette["ink"])
    _title(ax, audience_prof, insight, descriptive, palette)
    _annotate(ax, df, group_col, value_col, emphasize, level, palette)
    return _fig_to_svg(fig)


def _looks_like_rate(s):
    """value 列是不是 0/1 比例数据？是的话该走 rate_comparison，而不是 box/bar_means。"""
    u = set(pd.unique(s.dropna()))
    return 0 < len(u) <= 2 and u.issubset({0, 1, True, False})


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
    ax.annotate(f"↓ {emphasize} 比最高组低约 {gap_pp:.0f} 个百分点",
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

    fig, ax = plt.subplots(figsize=(7.5, 5))
    for hi, hue in enumerate(hues):
        positions = _grouped_positions(len(groups), hi, n_h, width)
        data = [df[(df[group_col] == g) & (df[hue_col] == hue)][value_col].dropna().values
                for g in groups]
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
    ax.set_ylabel(f"{value_col}（均值 ± 标准差）", color=palette["ink"]); ax.tick_params(colors=palette["ink"])
    ax.legend(handles=[Patch(facecolor=colors[h], label=str(h)) for h in hues],
              title=hue_col, frameon=False, loc="best")
    _title(ax, audience_prof, insight, descriptive, palette)
    return _fig_to_svg(fig)


# ── HTML 外壳：把 SVG 内嵌成一个自包含页面 ──────────────────────
def render_html(title, meta, primary_svg, alt_items, save_to):
    """alt_items: [(说明, svg), ...]。生成一个不依赖任何外部资源的 .html。"""
    alts = ""
    for label, svg in alt_items:
        alts += f'<section class="alt"><h3>{label}</h3><div class="chart">{svg}</div></section>'
    alts_block = f'<div class="alts"><h2>其他视角</h2>{alts}</div>' if alt_items else ""
    html = f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  *{{box-sizing:border-box;}}
  body{{margin:0 auto;max-width:880px;padding:32px 20px;background:#fff;color:#222;
       font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}}
  h1{{font-size:20px;margin:0 0 4px;}}
  .meta{{color:#666;font-size:13px;margin:0 0 24px;}}
  .chart svg{{width:100%;height:auto;display:block;}}
  .alts{{margin-top:32px;padding-top:8px;border-top:1px solid #e8e8e8;}}
  .alts>h2{{font-size:13px;color:#666;font-weight:600;letter-spacing:.04em;margin:16px 0 8px;}}
  .alt h3{{font-size:14px;color:#666;font-weight:500;margin:24px 0 4px;}}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">{meta}</p>
  <div class="primary chart">{primary_svg}</div>
  {alts_block}
</body>
</html>"""
    with open(save_to, "w", encoding="utf-8") as f:
        f.write(html)
    return save_to


# ── orchestrator：一张最优 + 1~2 张候选视角，输出单个 HTML ────────
def visualize(df, group_col, value_col, *, question, insight,
              audience, occasion, emphasize=None, hue_col=None, emphasize_hue=None,
              save_to="chart.html"):
    occ = OCCASION_PROFILES[occasion]
    aud = AUDIENCE_PROFILES[audience]
    palette = occ["palette"]
    level = max(0, min(ANNOTATE_MAX, occ["annotate_base"] + aud["annotate_bump"]))  # ← 你定的组合规则
    descriptive = (f"各{group_col} × {hue_col} 的{value_col}分布" if hue_col
                   else f"各{group_col}的{value_col}对比")

    common = dict(insight=insight, descriptive=descriptive, palette=palette,
                  audience_prof=aud, level=level, emphasize=emphasize)

    # 给了 hue_col → 两/多子总体跨类别对比（分组箱线 / 低受众降级为分组均值条）
    if hue_col is not None:
        gcommon = dict(common, emphasize_hue=emphasize_hue)
        if aud["downgrade"]:
            primary_svg = grouped_bar_means_comparison(df, group_col, value_col, hue_col, **gcommon)
            alt_items = [("技术受众视角 · 分组箱线",
                          grouped_box_comparison(df, group_col, value_col, hue_col, **gcommon))]
        else:
            primary_svg = grouped_box_comparison(df, group_col, value_col, hue_col, **gcommon)
            alt_items = [("高管视角 · 分组均值条",
                          grouped_bar_means_comparison(df, group_col, value_col, hue_col, **gcommon))]
    # 否则看数据类型：0/1 比例数据 → 比率图（box/bar_means 对比例都是错的）
    elif _looks_like_rate(df[value_col]):
        tech = not aud["downgrade"]   # 技术受众默认带 95% 置信区间，低受众用纯比例条
        primary_svg = rate_comparison(df, group_col, value_col, **common, show_ci=tech)
        alt_label = "高管视角 · 纯比例条" if tech else "技术受众视角 · 含 95% 置信区间"
        alt_items = [(alt_label, rate_comparison(df, group_col, value_col, **common, show_ci=not tech))]
    # 否则按受众驱动图型：低画像降级为均值条，否则用箱线图
    elif aud["downgrade"]:
        primary_svg = bar_means_comparison(df, group_col, value_col, **common)
        alt_items = [("技术受众视角 · 箱线图", box_comparison(df, group_col, value_col, **common))]
    else:
        primary_svg = box_comparison(df, group_col, value_col, **common)
        alt_items = [("高管视角 · 均值条", bar_means_comparison(df, group_col, value_col, **common))]

    meta = f"受众：{aud['label']} ｜ 场合：{occ['label']} ｜ 注释档：{level}"
    path = render_html(title=question, meta=meta,
                       primary_svg=primary_svg, alt_items=alt_items, save_to=save_to)
    return {"html": path, "annotation_level": level,
            "occasion": occ["label"], "audience": aud["label"]}


# ── demo：把两个决定都跑出来，输出 HTML ─────────────────────────
if __name__ == "__main__":
    print("使用字体:", setup_cjk_font())
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "分组": ["自选"] * 60 + ["调剂"] * 60,
        "首年GPA": np.concatenate([rng.normal(3.2, 0.40, 60),
                                   rng.normal(2.7, 0.45, 60)]).clip(0, 4),
    })
    insight = "调剂学生首年GPA显著更低"  # 真实调用里由 Claude 的 EDA 步产出

    r1 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="low", occasion="keynote", emphasize="调剂", save_to="c1.html")
    print("案例1:", r1)

    r2 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="high", occasion="journal", emphasize="调剂", save_to="c2.html")
    print("案例2:", r2)
