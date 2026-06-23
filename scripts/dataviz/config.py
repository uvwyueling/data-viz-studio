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
STANDARD_PALETTE = {"highlight": "#2F6690", "muted": "#C9CFD6", "ink": "#1F2933", "grid": "#E5E7EB"}


# ── 1.6 标准版视觉地板：70 分可交付，不直接暴露 matplotlib 默认外观 ────────
# 这不是作品集/keynote 精修主题，而是所有标准版都必须先达到的中性完成度。
STANDARD_STYLE = {
    "figsize": (9.6, 6.0),
    "kpi_figsize": (7.2, 4.6),
    "dpi": 140,
    "font_sizes": {
        "title": 18,
        "subtitle": 13,
        "axis_label": 12,
        "tick": 10,
        "annotation": 11,
        "legend": 10,
        "facet_title": 11,
    },
    "colors": {
        "background": "#FAFAF7",
        "axis": "#CBD5E1",
        "muted_text": "#6B7280",
    },
}


# ── 2. 受众图型素养 → 图型降级 + 标题写法〔运行时由用户指定〕──────────
# v0.6：受众档以「能读懂哪种图型」定义，不再用职业标签（高管/科研只是代理，且常猜错）。
#   high  ↔ 能直接读懂箱线图
#   mid   ↔ 读不了箱线、但跟得上直方图              （高/中分界 = 箱线图）
#   low   ↔ 连直方图都吃力，需降级为均值条+直接标注    （中/低分界 = 直方图/分布）
#   unknown/unclear/unsure ↔ 用户无法判断受众统计素养；按 low 保守出图，不对用户显式说明
# 注释地板已移出本表，改由 _annotation_floor 统一管（单一真源），不再用 annotate_bump。
AUDIENCE_PROFILES = {
    "high": {"label": "能直接读懂箱线图", "downgrade": False, "title_mode": "descriptive"},
    "mid":  {"label": "读不了箱线、能读直方图", "downgrade": False, "title_mode": "takeaway"},
    "low":  {"label": "连直方图都吃力，需降级+直接标注", "downgrade": True, "title_mode": "takeaway"},
}

UNKNOWN_AUDIENCE_KEYS = {"unknown", "unclear", "unsure", "not_sure", "dont_know", "do_not_know"}


def normalize_audience_key(audience):
    """Normalize audience aliases before routing.

    Unknown public-audience cases are intentionally conservative: treat them
    like low-literacy audiences without exposing that internal decision.
    """
    if audience in AUDIENCE_PROFILES:
        return audience
    if isinstance(audience, str) and audience.strip().lower() in UNKNOWN_AUDIENCE_KEYS:
        return "low"
    valid = sorted([*AUDIENCE_PROFILES, *UNKNOWN_AUDIENCE_KEYS])
    raise ValueError(f"unknown audience={audience!r}; expected one of {valid}")


# ── 2.5 注释地板：受众档的固有属性（单一真源）──────────────────────
# 把"中受众遇箱线类要补一句解读"做成 (audience, chart_kind) 查表，而非复制进每个图型函数（DRY）。
# _BORDERLINE_FOR_MID：哪些图型对「中」受众算"临界/要翻译"——这条属性也是 references 图型目录该登记的字段。
# 原则：临界 = 图型在中受众舒适区之上、仍展示时补一句翻译。
# histogram 在中受众下沿但够得着，不登记；scatter/heatmap 是高受众图，对中受众够不着，登记。
# high 受众任何图机制天然返回 0，无需登记。
_BORDERLINE_FOR_MID = {"box", "grouped_box", "facet_box", "scatter", "heatmap"}

_READING_GUIDE = {
    "box": "箱体=中间50%的数据，黑线=中位数，上下须=典型范围",
    "grouped_box": "箱体=中间50%的数据，黑线=中位数，上下须=典型范围",
    "facet_box": "箱体=中间50%的数据，黑线=中位数，上下须=典型范围",
    "scatter": "每个点是一条记录，看点云整体走向判断关系",
    "heatmap": "颜色越深=平均值越大，格子里的数字是具体均值",
}

ANNOTATE_MAX = 2
