from .config import AUDIENCE_PROFILES, OCCASION_PROFILES, STANDARD_PALETTE
from .routing import _route, _resolve_level, _check_cardinality
from .charts import (
    box_comparison, bar_means_comparison, grouped_box_comparison, grouped_bar_means_comparison,
    rate_comparison, facet_box_comparison, facet_bar_means_comparison, scatter_regression,
    heatmap_comparison, line_trend, histogram_distribution, kpi_number,
)
from .render import render_html


def _alternative_item(label_kind, svg):
    """探索/调试用备选图型。标签保持中性，不暗示未配置的受众档。"""
    return (f"备选图型 · {label_kind}", svg)


# ── orchestrator：按受众交付标准版 primary；备选图仅探索/调试时打开 ────────
def visualize(df, group_col=None, value_col=None, *, question, insight,
              audience, occasion=None, emphasize=None, hue_col=None, emphasize_hue=None,
              facet_col=None, chart_kind=None, show_alternatives=False, save_to="chart.html"):
    """出图主入口。
    group_col=None → 单变量模式（直方图 / 大数字KPI）。
    facet_col     → 小多图（每个 facet 值一个子图）。
    chart_kind    → 手动覆盖路由（scatter / heatmap 必须手传；整数年份折线用 'line'）。
      heatmap 时 hue_col 作为热力图列轴（第二分类维度）。
    show_alternatives=False → 标准版只交付 primary；True 仅作探索/调试，附中性标签备选图型。
    occasion=None → 标准版（STANDARD_PALETTE + 受众注释地板），第 3 步默认走这条。
    occasion="keynote"/"internal"/"portfolio" → 4.1 精修：换场合配色、把注释往地板之上叠。
    """
    aud = AUDIENCE_PROFILES[audience]
    occ = OCCASION_PROFILES[occasion] if occasion is not None else None    # 标准版不预设场合
    palette = occ["palette"] if occ is not None else STANDARD_PALETTE

    _check_cardinality(df, group_col, hue_col, facet_col)                  # 类别过多提前提示
    chart_kind = chart_kind or _route(df, group_col, value_col, aud, hue_col, facet_col)
    if audience == "low" and chart_kind == "scatter":
        raise ValueError(
            "散点图表达两个连续变量的关系，低受众读不了；自动分箱会把『关系』静默换成『均值』(违反 P0 口径)。"
            "请改用 mid/high 受众，或换一个适合低受众的问题。"
        )
    if audience == "low" and chart_kind == "heatmap":
        chart_kind = "grouped_bar_means"
    level = _resolve_level(audience, chart_kind, occ)                      # 受众地板 +（场合叠加）
    if group_col is None:
        descriptive = f"{value_col} 的分布"
    elif facet_col:
        descriptive = f"各{group_col} 按 {facet_col} 分面的{value_col}对比"
    elif hue_col:
        descriptive = f"各{group_col} × {hue_col} 的{value_col}分布"
    else:
        descriptive = f"各{group_col}的{value_col}对比"

    common = dict(insight=insight, descriptive=descriptive, palette=palette,
                  audience_prof=aud, level=level, emphasize=emphasize)

    alt_items = []

    # 按 chart_kind 分发（路由已在 _route 定好，这里只取对应图元；备选图仅探索/调试时生成）
    if chart_kind == "grouped_box":
        gcommon = dict(common, emphasize_hue=emphasize_hue)
        primary_svg = grouped_box_comparison(df, group_col, value_col, hue_col, **gcommon)
        if show_alternatives:
            alt_items = [_alternative_item(
                "grouped_bar_means",
                grouped_bar_means_comparison(df, group_col, value_col, hue_col, **gcommon))]
    elif chart_kind == "grouped_bar_means":
        gcommon = dict(common, emphasize_hue=emphasize_hue)
        primary_svg = grouped_bar_means_comparison(df, group_col, value_col, hue_col, **gcommon)
        if show_alternatives:
            alt_items = [_alternative_item(
                "grouped_box",
                grouped_box_comparison(df, group_col, value_col, hue_col, **gcommon))]
    elif chart_kind == "rate":
        tech = not aud["downgrade"]   # 技术受众默认带 95% 置信区间，低受众用纯比例条
        primary_svg = rate_comparison(df, group_col, value_col, **common, show_ci=tech)
        if show_alternatives:
            alt_items = [_alternative_item(
                "rate",
                rate_comparison(df, group_col, value_col, **common, show_ci=not tech))]
    elif chart_kind == "facet_box":
        primary_svg = facet_box_comparison(df, group_col, value_col, facet_col, **common)
        if show_alternatives:
            alt_items = [_alternative_item(
                "facet_bar_means",
                facet_bar_means_comparison(df, group_col, value_col, facet_col, **common))]
    elif chart_kind == "facet_bar_means":
        primary_svg = facet_bar_means_comparison(df, group_col, value_col, facet_col, **common)
        if show_alternatives:
            alt_items = [_alternative_item(
                "facet_box",
                facet_box_comparison(df, group_col, value_col, facet_col, **common))]
    elif chart_kind == "scatter":
        primary_svg = scatter_regression(df, group_col, value_col, **common, hue_col=hue_col)
    elif chart_kind == "heatmap":
        if hue_col is None:
            raise ValueError("heatmap 需要 hue_col 作为列轴（第二个分类维度）")
        primary_svg = heatmap_comparison(df, group_col, hue_col, value_col, **common)
    elif chart_kind == "line":
        primary_svg = line_trend(df, group_col, value_col, **common, hue_col=hue_col)
    elif chart_kind == "histogram":
        primary_svg = histogram_distribution(df, value_col, **common, hue_col=hue_col)
        if show_alternatives:
            alt_items = [_alternative_item("kpi", kpi_number(df, value_col, **common))]
    elif chart_kind == "kpi":
        primary_svg = kpi_number(df, value_col, **common)
        if show_alternatives:
            alt_items = [_alternative_item(
                "histogram",
                histogram_distribution(df, value_col, **common, hue_col=hue_col))]
    elif chart_kind == "bar_means":
        primary_svg = bar_means_comparison(df, group_col, value_col, **common)
        if show_alternatives:
            alt_items = [_alternative_item("box", box_comparison(df, group_col, value_col, **common))]
    else:  # box
        primary_svg = box_comparison(df, group_col, value_col, **common)
        if show_alternatives:
            alt_items = [_alternative_item(
                "bar_means",
                bar_means_comparison(df, group_col, value_col, **common))]

    version_label = occ["label"] if occ is not None else "标准版（受众地板）"
    meta = f"受众：{aud['label']} ｜ 版本：{version_label} ｜ 注释档：{level}"
    path = render_html(title=question, meta=meta,
                       primary_svg=primary_svg, alt_items=alt_items, save_to=save_to)
    return {"html": path, "annotation_level": level, "chart_kind": chart_kind,
            "version": version_label, "audience": aud["label"]}

