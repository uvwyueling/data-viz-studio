import pandas as pd

from .config import _BORDERLINE_FOR_MID, ANNOTATE_MAX


def _annotation_floor(audience, chart_kind):
    """受众注释地板（固有属性，单一真源）。返回 level：
       0=仅标题+轴；1=加一句解读/结论；2=叙事式多标注。
    - low：地板=1 —— 必含直接标注(柱顶数值，图型函数无条件给)+一句结论；这是低受众读懂图的结构，不是装饰。
    - mid + 临界图型（箱线类 / 高受众图型）：地板=1 —— 补一句翻译解读。
    - mid + 普通图型 / high：地板=0 —— 裸图可读。
    场合（4.1）只能在此地板之上叠加（见 _resolve_level），绝不减到地板以下。
    """
    if audience == "low":
        return 1
    if audience == "mid" and chart_kind in _BORDERLINE_FOR_MID:
        return 1
    return 0


def _route(df, group_col, value_col, aud, hue_col, facet_col=None):
    """选型路由（单一真源）：按数据形状 + 受众，定这次画哪种图，返回 chart_kind。
    注释地板(_annotation_floor)与 visualize 的分发都依赖它。
    scatter / heatmap 需手传 chart_kind 覆盖（无法从数据形状自动判断）。"""
    if group_col is None:                                          # 单变量模式（直方图 / 大数字KPI）
        return "kpi" if aud["downgrade"] else "histogram"
    if facet_col is not None:                                      # 小多图（facet_col → 一图一面板）
        return "facet_bar_means" if aud["downgrade"] else "facet_box"
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


# ── 工具 ────────────────────────────────────────────────────────
_GROUP_WARN = 8    # group_col 超过这个数量发出警告
_HUE_WARN   = 4   # hue_col 超过这个数量发出警告


def _check_cardinality(df, group_col, hue_col, facet_col=None):
    """类别过多时提前告知，避免出一张谁也看不清的图。不抛错——只打印提示，让调用方决定是否截断。"""
    if (group_col is not None
            and not pd.api.types.is_datetime64_any_dtype(df[group_col])
            and not pd.api.types.is_numeric_dtype(df[group_col])):
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
                f" 超过 {_HUE_WARN} 个系列时分组图会过于拥挤，考虑改用分面（small multiples / facet_col）。"
            )
    if facet_col is not None:
        n_facets = df[facet_col].nunique()
        if n_facets > _GROUP_WARN:
            print(
                f"[data-viz-studio] 警告：facet_col='{facet_col}' 有 {n_facets} 个面板（建议 ≤{_GROUP_WARN}）。"
                f" 面板太多时小多图会变得很小，考虑筛选后再出图。"
            )


def _looks_like_rate(s):
    """value 列是不是 0/1 比例数据？是的话该走 rate_comparison，而不是 box/bar_means。"""
    u = set(pd.unique(s.dropna()))
    return 0 < len(u) <= 2 and u.issubset({0, 1, True, False})


def _looks_like_trend(s):
    """group_col 是否为时序（datetime dtype）？是则路由到折线趋势图。
    整数年份（如 2020/2021）不自动判定，需手传 chart_kind='line' 明确指定。"""
    return pd.api.types.is_datetime64_any_dtype(s)

