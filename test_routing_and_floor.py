import pathlib
import re
import sys

import pandas as pd


ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / "scripts"))

import dataviz as tmpl
from scripts.deck import render_deck


def assert_floor_contract():
    kinds = [
        "box", "grouped_box", "facet_box", "scatter", "heatmap",
        "histogram", "bar_means", "grouped_bar_means", "facet_bar_means",
        "line", "rate", "kpi",
    ]
    assert tmpl._BORDERLINE_FOR_MID == {"box", "grouped_box", "facet_box", "scatter", "heatmap"}
    assert set(tmpl._READING_GUIDE) == tmpl._BORDERLINE_FOR_MID
    assert "histogram" not in tmpl._BORDERLINE_FOR_MID

    for kind in kinds:
        assert tmpl._annotation_floor("high", kind) == 0, kind
        assert tmpl._annotation_floor("low", kind) == 1, kind

    for kind in ["box", "grouped_box", "facet_box", "scatter", "heatmap"]:
        assert tmpl._annotation_floor("mid", kind) == 1, kind
    for kind in ["histogram", "bar_means"]:
        assert tmpl._annotation_floor("mid", kind) == 0, kind


def route(df, group_col, value_col, audience, hue_col=None, facet_col=None):
    aud = tmpl.AUDIENCE_PROFILES[audience]
    return tmpl._route(df, group_col, value_col, aud, hue_col, facet_col)


def resolve_visualize_chart_kind(df, group_col, value_col, audience, *, chart_kind=None, hue_col=None, facet_col=None):
    aud = tmpl.AUDIENCE_PROFILES[audience]
    kind = chart_kind or tmpl._route(df, group_col, value_col, aud, hue_col, facet_col)
    if audience == "low" and kind == "scatter":
        raise ValueError(
            "散点图表达两个连续变量的关系，低受众读不了；自动分箱会把『关系』静默换成『均值』(违反 P0 口径)。"
            "请改用 mid/high 受众，或换一个适合低受众的问题。"
        )
    if audience == "low" and kind == "heatmap":
        kind = "grouped_bar_means"
    return kind


def assert_route_contract():
    df = pd.DataFrame({
        "group": ["A", "A", "B", "B"] * 3,
        "value": [1.1, 1.3, 2.4, 2.8] * 3,
        "flag": [0, 1, 1, 0] * 3,
        "hue": ["X", "Y", "X", "Y"] * 3,
        "facet": ["F1", "F1", "F2", "F2"] * 3,
        "date": pd.date_range("2024-01-01", periods=12, freq="D"),
    })

    assert route(df, "group", "value", "high") == "box"
    assert route(df, "group", "value", "mid") == "box"
    assert route(df, "group", "value", "low") == "bar_means"

    for audience in ["high", "mid", "low"]:
        assert route(df, "date", "value", audience) == "line"
        assert route(df, "group", "flag", audience) == "rate"

    assert route(df, "group", "value", "high", hue_col="hue") == "grouped_box"
    assert route(df, "group", "value", "mid", hue_col="hue") == "grouped_box"
    assert route(df, "group", "value", "low", hue_col="hue") == "grouped_bar_means"

    assert route(df, "group", "value", "high", facet_col="facet") == "facet_box"
    assert route(df, "group", "value", "mid", facet_col="facet") == "facet_box"
    assert route(df, "group", "value", "low", facet_col="facet") == "facet_bar_means"

    assert route(df, None, "value", "high") == "histogram"
    assert route(df, None, "value", "mid") == "histogram"
    assert route(df, None, "value", "low") == "kpi"

    assert resolve_visualize_chart_kind(
        df, "group", "value", "low", chart_kind="heatmap", hue_col="hue"
    ) == "grouped_bar_means"
    try:
        resolve_visualize_chart_kind(df, "value", "flag", "low", chart_kind="scatter")
    except ValueError as e:
        assert "散点图表达两个连续变量的关系，低受众读不了" in str(e)
    else:
        raise AssertionError("low + scatter did not raise")


def assert_integrated_floor_for_reachable_routes():
    df = pd.DataFrame({
        "group": ["A", "A", "B", "B"] * 3,
        "value": [1.1, 1.3, 2.4, 2.8] * 3,
        "flag": [0, 1, 1, 0] * 3,
        "hue": ["X", "Y", "X", "Y"] * 3,
        "facet": ["F1", "F1", "F2", "F2"] * 3,
        "date": pd.date_range("2024-01-01", periods=12, freq="D"),
    })
    cases = [
        ("high", "group", "value", None, None, 0),
        ("mid", "group", "value", None, None, 1),
        ("low", "group", "value", None, None, 1),
        ("high", "date", "value", None, None, 0),
        ("mid", "date", "value", None, None, 0),
        ("low", "date", "value", None, None, 1),
        ("high", "group", "flag", None, None, 0),
        ("mid", "group", "flag", None, None, 0),
        ("low", "group", "flag", None, None, 1),
        ("high", "group", "value", "hue", None, 0),
        ("mid", "group", "value", "hue", None, 1),
        ("low", "group", "value", "hue", None, 1),
        ("high", "group", "value", None, "facet", 0),
        ("mid", "group", "value", None, "facet", 1),
        ("low", "group", "value", None, "facet", 1),
        ("high", None, "value", None, None, 0),
        ("mid", None, "value", None, None, 0),
        ("low", None, "value", None, None, 1),
    ]
    for audience, group_col, value_col, hue_col, facet_col, expected in cases:
        kind = route(df, group_col, value_col, audience, hue_col=hue_col, facet_col=facet_col)
        got = tmpl._annotation_floor(audience, kind)
        assert got == expected, (audience, kind, got, expected)


def assert_visualize_initializes_cjk_font():
    out = ROOT / "__test__" / "font_guard_visualize.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "分组": ["自选", "自选", "调剂", "调剂"],
        "首年GPA": [3.6, 3.4, 2.8, 2.7],
    })
    tmpl.visualize(
        df, "分组", "首年GPA",
        question="主动选择 vs 被动调剂的学生，分流前平均学分绩点有何差异？",
        insight="调剂学生分流前平均学分绩点更低",
        audience="low",
        emphasize="调剂",
        save_to=str(out),
    )
    html = out.read_text(encoding="utf-8")
    svg = re.search(r"(<svg\b.*?</svg>)", html, flags=re.S).group(1)
    assert "<text" not in svg
    assert "-5206" in svg or "-8c03" in svg or "-81ea" in svg


def assert_deck_strips_audience_badges_and_wraps_callout():
    out = ROOT / "__test__" / "deck_text_guard.html"
    long_callout = (
        "主动选择组均值GPA比被动调剂组高0.76分，差距在分流前已经显现，"
        "这是一句故意写得很长的数据洞察，用来验证low/mid/high三类deck的callout都能在容器内自然换行。"
    )
    render_deck(
        title="文本防护测试",
        subtitle="2015–2018 级学生分流数据 · 基础型受众版（箱线图 + 阅读指引） · 标准版",
        kpi_cards=[{"label": "样本量", "value": "120"}],
        callout=long_callout,
        chart_svg="<svg viewBox='0 0 10 10'></svg>",
        palette=tmpl.STANDARD_PALETTE,
        save_to=str(out),
    )
    html = out.read_text(encoding="utf-8")
    assert "受众版" not in html
    assert "基础型" not in html
    assert '<span class="callout__text">' in html
    assert "word-break: break-word;" in html
    assert "line-break: anywhere;" in html


def assert_chart_title_wraps_long_insight():
    out = ROOT / "__test__" / "long_insight_wrap.html"
    long_insight = (
        "主动选择组中位GPA比被动调剂高0.79分，两组箱体几乎不重叠，"
        "差距在分流前已系统性显现；Mann-Whitney检验p小于0.001，说明两组分布差异显著。"
    )
    df = pd.DataFrame({
        "分组": ["主动选择"] * 8 + ["被动调剂"] * 8,
        "分流前_平均学分绩点": [3.6, 3.7, 3.4, 3.8, 3.5, 3.9, 3.3, 3.6,
                               2.8, 2.7, 3.0, 2.9, 2.6, 3.1, 2.5, 2.8],
    })
    tmpl.visualize(
        df, "分组", "分流前_平均学分绩点",
        question="主动选择 vs 被动调剂：分流前平均学分绩点对比",
        insight=long_insight,
        audience="mid",
        emphasize="被动调剂",
        save_to=str(out),
    )
    html = out.read_text(encoding="utf-8")
    assert "主动选择组中位GPA比被动调剂高0.79分，两组箱体几乎不重叠，差距" in html
    assert "在分流前已系统性显现；Mann-Whitney检验p小于0.001，" in html
    view_box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', html)
    assert view_box is not None
    assert float(view_box.group(1)) < 700


def assert_standard_visual_baseline_is_exported():
    out = ROOT / "__test__" / "standard_visual_baseline.html"
    df = pd.DataFrame({
        "分组": ["Adelie", "Adelie", "Gentoo", "Gentoo", "Chinstrap", "Chinstrap"],
        "体重_g": [3700, 3550, 5000, 5200, 3800, 3900],
    })
    tmpl.visualize(
        df, "分组", "体重_g",
        question="不同企鹅物种的体重分布有什么差异？",
        insight="Gentoo 的体重明显更高",
        audience="low",
        emphasize="Gentoo",
        save_to=str(out),
    )
    html = out.read_text(encoding="utf-8")
    assert "background:#FAFAF7" in html
    svg = re.search(r"(<svg\b.*?</svg>)", html, flags=re.S).group(1)
    assert "#fafaf7" in svg.lower()
    view_box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    assert view_box is not None
    assert float(view_box.group(1)) > 560
    assert float(view_box.group(2)) > 380


def assert_emphasis_gap_label_uses_emphasized_group_direction():
    means = pd.Series({
        "Adelie": 3700.4,
        "Gentoo": 5076.2,
        "Chinstrap": 3733.1,
    })
    assert tmpl._emphasis_gap_label(means, "Gentoo") == "Gentoo组平均高约 1376"
    assert tmpl._emphasis_gap_label(means, "Adelie") == "Adelie组平均低约 1376"
    assert tmpl._emphasis_gap_label(means, "Missing") is None
    assert tmpl._emphasis_gap_label(pd.Series({"Gentoo": 5076.2}), "Gentoo") is None


if __name__ == "__main__":
    assert_floor_contract()
    assert_route_contract()
    assert_integrated_floor_for_reachable_routes()
    assert_visualize_initializes_cjk_font()
    assert_deck_strips_audience_badges_and_wraps_callout()
    assert_chart_title_wraps_long_insight()
    assert_standard_visual_baseline_is_exported()
    assert_emphasis_gap_label_uses_emphasized_group_direction()
    print("test_routing_and_floor ok")
