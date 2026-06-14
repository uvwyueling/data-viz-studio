"""
data-viz-studio · 种子模板 (v0.6)
==================================
单一职责：读取用户上传的 CSV/Excel → 输出能回答【数据问题】、并以适配【受众图型素养】
的图像语言、最低沟通成本传达洞察的可视化图。

── 架构（v0.6 变更：受众轴成为唯一常驻核心）────────────────────
受众轴决定图表「是什么」（图型选择 + 注释地板，结构层、不可逆、用户自己判断不了）——这是核心。
场合轴降为「标准版出图后」的可选精修（4.1）：改配色/注释/尺寸/格式（样式层、可逆、用户自己有主见）。
默认出「标准版」：用 STANDARD_PALETTE + 受众注释地板，不预设任何场合。

── 注释模型（两层，分别挂在两根轴上）──────────────────────────
地板 = 受众档固有属性（单一真源 _annotation_floor）：low 含直接标注+结论；mid 遇箱线类补一句解读。
叠加 = 场合（4.1）在地板之上加叙事注释——只增不减，绝不压到地板以下。

── 输出（v0.3 起）─────────────────────────────────────────────
matplotlib 出图 → 存成 SVG（字形外框化）→ 内嵌进一个自包含的 HTML 页面。

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
        try:
            df = pd.read_excel(path)
        except ImportError as e:
            engine = "xlrd" if ext == ".xls" else "openpyxl"
            raise ImportError(
                f"读取 {ext} 需要 {engine}，请先安装：pip install {engine}"
            ) from e
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


def encode_binary(df, col, pos_value):
    """文本型 0/1 标签列转换为数值（如 "yes"/"no" → 1/0）。
    pos_value 是代表"正例/1"的那个值（如 "yes"、"存活"、True）；其余非空值一律编为 0。
    用法：df["survived_01"] = encode_binary(df, "survived", "yes")
    """
    return df[col].map(lambda v: 1 if v == pos_value else (0 if pd.notna(v) else float("nan")))


def _basic_clean(df):
    """基础清洗：列名去首尾空格、丢全空的行与列、去重复行。只整形不改数据值本身。"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")   # 全空的行/列
    return df.drop_duplicates().reset_index(drop=True)


# ── 1. 场合预设（4.1 精修）→ 配色 + 注释叠加〔Valeria 校准〕──────────
# v0.6：场合不再是出图入口闸门，而是「标准版出图后」的可选精修预设。
# annotate_base 改为「叠加档」：只能把注释往受众地板之上抬，绝不减到地板以下（见 _resolve_level）。
# 「理科期刊图」场景已下线：既用不上受众翻译引擎（读者恒为 high），又要矢量 PDF 管线（本层只出 HTML）。
OCCASION_PROFILES = {
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


# ── 1.5 标准版样式基线（TODO 里删掉「样式基线」一词后，它在这里落地）────
# 这是 standard version 的视觉 DNA：一个高亮 + 中性灰，色盲友好、克制中性、沟通优先。
# 它不是某个场合的风格，而是「还没指定场合时」有意选定的默认。4.1 的场合预设在它之上改写。
STANDARD_PALETTE = {"highlight": "#2F6690", "muted": "#C9CFD6", "ink": "#1a1a1a", "grid": "#ececec"}


# ── 2. 受众图型素养 → 图型降级 + 标题写法〔运行时由用户指定〕──────────
# v0.6：受众档以「能读懂哪种图型」定义，不再用职业标签（高管/科研只是代理，且常猜错）。
#   high  ↔ 能直接读懂箱线图
#   mid   ↔ 读不了箱线、但跟得上直方图              （高/中分界 = 箱线图）
#   low   ↔ 连直方图都吃力，需降级为均值条+直接标注    （中/低分界 = 直方图/分布）
# 注释地板已移出本表，改由 _annotation_floor 统一管（单一真源），不再用 annotate_bump。
AUDIENCE_PROFILES = {
    "high": {"label": "能直接读懂箱线图", "downgrade": False, "title_mode": "descriptive"},
    "mid":  {"label": "读不了箱线、能读直方图", "downgrade": False, "title_mode": "takeaway"},
    "low":  {"label": "连直方图都吃力，需降级+直接标注", "downgrade": True, "title_mode": "takeaway"},
}


# ── 2.5 注释地板：受众档的固有属性（单一真源）──────────────────────
# 把"中受众遇箱线类要补一句解读"做成 (audience, chart_kind) 查表，而非复制进每个图型函数（DRY）。
# _BORDERLINE_FOR_MID：哪些图型对「中」受众算"临界/要翻译"——这条属性也是 references 图型目录该登记的字段。
_BORDERLINE_FOR_MID = {"box", "grouped_box"}


def _annotation_floor(audience, chart_kind):
    """受众注释地板（固有属性，单一真源）。返回 level：
       0=仅标题+轴；1=加一句解读/结论；2=叙事式多标注。
    - low：地板=1 —— 必含直接标注(柱顶数值，图型函数无条件给)+一句结论；这是低受众读懂图的结构，不是装饰。
    - mid + 临界图型（箱线类）：地板=1 —— 补一句翻译解读。
    - mid + 普通图型 / high：地板=0 —— 裸图可读。
    场合（4.1）只能在此地板之上叠加（见 _resolve_level），绝不减到地板以下。
    """
    if audience == "low":
        return 1
    if audience == "mid" and chart_kind in _BORDERLINE_FOR_MID:
        return 1
    return 0


def _route(df, group_col, value_col, aud, hue_col):
    """选型路由（单一真源）：按数据形状 + 受众，定这次画哪种图，返回 chart_kind。
    注释地板(_annotation_floor)与 visualize 的分发都依赖它。"""
    if group_col is None:                                          # 单变量模式（直方图 / 大数字KPI）
        return "kpi" if aud["downgrade"] else "histogram"
    if hue_col is not None:
        return "grouped_bar_means" if aud["downgrade"] else "grouped_box"
    if _looks_like_rate(df[value_col]):
        return "rate"
    if _looks_like_trend(df[group_col]):                           # datetime 列 → 折线趋势图
        return "line"
    if aud["downgrade"]:
        return "bar_means"
    return "box"


def _resolve_level(audience, chart_kind, occ):
    """最终注释档 = 受众地板；场合（4.1）只能往上叠，不能压到地板以下。"""
    level = _annotation_floor(audience, chart_kind)
    if occ is not None:
        level = max(level, occ["annotate_base"])
    return min(ANNOTATE_MAX, level)

ANNOTATE_MAX = 2


# ── 工具 ────────────────────────────────────────────────────────
_GROUP_WARN = 8    # group_col 超过这个数量发出警告
_HUE_WARN   = 4   # hue_col 超过这个数量发出警告


def _check_cardinality(df, group_col, hue_col):
    """类别过多时提前告知，避免出一张谁也看不清的图。不抛错——只打印提示，让调用方决定是否截断。"""
    if group_col is not None and not pd.api.types.is_datetime64_any_dtype(df[group_col]):
        n_groups = df[group_col].nunique()
        if n_groups > _GROUP_WARN:
            print(
                f"[data-viz-studio] 警告：group_col='{group_col}' 有 {n_groups} 个类别（建议 ≤{_GROUP_WARN}）。"
                f" 考虑用 df[df['{group_col}'].isin([...])] 筛选或按计数取 top-N，否则图会过于拥挤。"
            )
    if hue_col is not None:
        n_hues = df[hue_col].nunique()
        if n_hues > _HUE_WARN:
            print(
                f"[data-viz-studio] 警告：hue_col='{hue_col}' 有 {n_hues} 个系列（建议 ≤{_HUE_WARN}）。"
                f" 超过 {_HUE_WARN} 个系列时分组图会过于拥挤，考虑改用分面（small multiples）。"
            )


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


def _looks_like_trend(s):
    """group_col 是否为时序（datetime dtype）？是则路由到折线趋势图。
    整数年份（如 2020/2021）不自动判定，需手传 chart_kind='line' 明确指定。"""
    return pd.api.types.is_datetime64_any_dtype(s)


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
def visualize(df, group_col=None, value_col=None, *, question, insight,
              audience, occasion=None, emphasize=None, hue_col=None, emphasize_hue=None,
              chart_kind=None, save_to="chart.html"):
    """出图主入口。
    group_col=None → 单变量模式（直方图 / 大数字KPI）。
    chart_kind 可手动覆盖自动路由（如 chart_kind='line' 强制折线，适用于整数年份等无法自动判断的有序 x）。
    occasion=None → 标准版（STANDARD_PALETTE + 受众注释地板），第 3 步默认走这条。
    occasion="keynote"/"internal"/"portfolio" → 4.1 精修：换场合配色、把注释往地板之上叠。
    """
    aud = AUDIENCE_PROFILES[audience]
    occ = OCCASION_PROFILES[occasion] if occasion is not None else None    # 标准版不预设场合
    palette = occ["palette"] if occ is not None else STANDARD_PALETTE

    _check_cardinality(df, group_col, hue_col)                             # 类别过多提前提示
    chart_kind = chart_kind or _route(df, group_col, value_col, aud, hue_col)  # 选型单一真源（可覆盖）
    level = _resolve_level(audience, chart_kind, occ)                      # 受众地板 +（场合叠加）
    if group_col is None:
        descriptive = f"{value_col} 的分布"
    elif hue_col:
        descriptive = f"各{group_col} × {hue_col} 的{value_col}分布"
    else:
        descriptive = f"各{group_col}的{value_col}对比"

    common = dict(insight=insight, descriptive=descriptive, palette=palette,
                  audience_prof=aud, level=level, emphasize=emphasize)

    # 按 chart_kind 分发（路由已在 _route 定好，这里只取对应图元 + 配一张候选视角）
    if chart_kind == "grouped_box":
        gcommon = dict(common, emphasize_hue=emphasize_hue)
        primary_svg = grouped_box_comparison(df, group_col, value_col, hue_col, **gcommon)
        alt_items = [("低受众版 · 分组均值条",
                      grouped_bar_means_comparison(df, group_col, value_col, hue_col, **gcommon))]
    elif chart_kind == "grouped_bar_means":
        gcommon = dict(common, emphasize_hue=emphasize_hue)
        primary_svg = grouped_bar_means_comparison(df, group_col, value_col, hue_col, **gcommon)
        alt_items = [("技术版 · 分组箱线",
                      grouped_box_comparison(df, group_col, value_col, hue_col, **gcommon))]
    elif chart_kind == "rate":
        tech = not aud["downgrade"]   # 技术受众默认带 95% 置信区间，低受众用纯比例条
        primary_svg = rate_comparison(df, group_col, value_col, **common, show_ci=tech)
        alt_label = "低受众版 · 纯比例条" if tech else "技术版 · 含 95% 置信区间"
        alt_items = [(alt_label, rate_comparison(df, group_col, value_col, **common, show_ci=not tech))]
    elif chart_kind == "line":
        primary_svg = line_trend(df, group_col, value_col, **common, hue_col=hue_col)
        alt_items = []
    elif chart_kind == "histogram":
        primary_svg = histogram_distribution(df, value_col, **common, hue_col=hue_col)
        alt_items = [("低受众版 · 大数字KPI", kpi_number(df, value_col, **common))]
    elif chart_kind == "kpi":
        primary_svg = kpi_number(df, value_col, **common)
        alt_items = [("技术版 · 直方图", histogram_distribution(df, value_col, **common, hue_col=hue_col))]
    elif chart_kind == "bar_means":
        primary_svg = bar_means_comparison(df, group_col, value_col, **common)
        alt_items = [("技术版 · 箱线图", box_comparison(df, group_col, value_col, **common))]
    else:  # box
        primary_svg = box_comparison(df, group_col, value_col, **common)
        alt_items = [("低受众版 · 均值条", bar_means_comparison(df, group_col, value_col, **common))]

    version_label = occ["label"] if occ is not None else "标准版（受众地板）"
    meta = f"受众：{aud['label']} ｜ 版本：{version_label} ｜ 注释档：{level}"
    path = render_html(title=question, meta=meta,
                       primary_svg=primary_svg, alt_items=alt_items, save_to=save_to)
    return {"html": path, "annotation_level": level, "chart_kind": chart_kind,
            "version": version_label, "audience": aud["label"]}


# ── demo：标准版 + 一次 4.1 精修，输出 HTML ───────────────────────
if __name__ == "__main__":
    print("使用字体:", setup_cjk_font())
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "分组": ["自选"] * 60 + ["调剂"] * 60,
        "首年GPA": np.concatenate([rng.normal(3.2, 0.40, 60),
                                   rng.normal(2.7, 0.45, 60)]).clip(0, 4),
    })
    insight = "调剂学生首年GPA显著更低"  # 真实调用里由 Claude 的 EDA 步产出

    # 案例1 · 标准版（low）：不传 occasion → STANDARD_PALETTE + 受众地板（均值条 + 直接标注 + 结论）
    r1 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="low", emphasize="调剂", save_to="c1.html")
    print("案例1 · 标准版/low :", r1)

    # 案例2 · 标准版（high）：箱线图，地板=0（裸图可读）
    r2 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="high", emphasize="调剂", save_to="c2.html")
    print("案例2 · 标准版/high:", r2)

    # 案例3 · 4.1 精修（low + keynote）：标准版之上套演讲场合配色；注释仍不低于受众地板
    r3 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="low", occasion="keynote", emphasize="调剂", save_to="c3.html")
    print("案例3 · 4.1精修/low+keynote:", r3)
