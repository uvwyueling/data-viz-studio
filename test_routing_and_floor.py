import pathlib
import sys

import pandas as pd


ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / "scripts"))

import dataviz as tmpl


def assert_floor_contract():
    kinds = [
        "box", "grouped_box", "facet_box", "scatter", "heatmap",
        "histogram", "bar_means", "grouped_bar_means", "facet_bar_means",
        "line", "rate", "kpi",
    ]
    assert tmpl._BORDERLINE_FOR_MID == {"box", "grouped_box", "facet_box", "scatter", "heatmap"}
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


if __name__ == "__main__":
    assert_floor_contract()
    assert_route_contract()
    assert_integrated_floor_for_reachable_routes()
    print("test_routing_and_floor ok")
