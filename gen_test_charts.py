import pathlib
import re
import sys

import pandas as pd


ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "__test__" / "gallery"
sys.path.insert(0, str(ROOT / "scripts"))

import dataviz as tmpl


def embedded_svg(html_path):
    text = pathlib.Path(html_path).read_text(encoding="utf-8")
    m = re.search(r"(<svg\b.*?</svg>)", text, flags=re.S)
    if not m:
        raise AssertionError(f"missing embedded svg: {html_path}")
    return m.group(1)


def assert_svg_paths_only(html_path):
    svg = embedded_svg(html_path)
    if "<text" in svg:
        raise AssertionError(f"svg contains <text>: {html_path}")
    if "<path" not in svg:
        raise AssertionError(f"svg contains no <path>: {html_path}")


def html_text(html_path):
    return pathlib.Path(html_path).read_text(encoding="utf-8")


def save_primary_svg(html_path, svg_path):
    svg_path.write_text(embedded_svg(html_path), encoding="utf-8")


def expected_floor(audience, chart_kind):
    return tmpl._annotation_floor(audience, chart_kind)


def render_case(name, df, audience, expected_kind, **kwargs):
    save_to = OUT / f"{name}.html"
    result = tmpl.visualize(
        df,
        question=kwargs.pop("question", name),
        insight=kwargs.pop("insight", "用于测试的洞察"),
        audience=audience,
        save_to=str(save_to),
        **kwargs,
    )
    assert result["chart_kind"] == expected_kind, (name, result)
    assert result["annotation_level"] == expected_floor(audience, expected_kind), (name, result)
    assert_svg_paths_only(save_to)
    text = html_text(save_to)
    assert "受众：" not in text and "注释档：" not in text, name
    print(f"ok {name}: {result['chart_kind']} level={result['annotation_level']}")
    return save_to, result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        if old.suffix in {".html", ".svg"}:
            old.unlink()
    tmpl.setup_cjk_font()

    superstore = tmpl.load_dataframe(ROOT / "__test__" / "superstore_zh.xlsx")
    stage = tmpl.load_dataframe(ROOT / "__test__" / "stage_reassign.csv")
    ss_small = superstore[superstore["区域"].isin(["东部", "西部", "中部", "南部"])].copy()
    stage_small = stage[stage["最终专业"].isin(["视觉传达设计", "环境设计", "服装与服饰设计"])].copy()

    # A compact reachable set across audiences and shapes.
    render_case(
        "stage_low_bar_means", stage_small, "low", "bar_means",
        group_col="最终专业", value_col="分流前_平均学分绩点",
        insight="不同最终专业的分流前 GPA 有差异", emphasize="视觉传达设计",
    )
    render_case(
        "stage_mid_box", stage_small, "mid", "box",
        group_col="最终专业", value_col="分流前_平均学分绩点",
        insight="不同最终专业的分流前 GPA 有差异", emphasize="视觉传达设计",
    )
    profit_box, _ = render_case(
        "superstore_profit_box_clipped", ss_small, "high", "box",
        group_col="区域", value_col="Profit",
        insight="各区域利润分布不同", emphasize="西部",
    )
    assert "离群点超出显示范围" in html_text(profit_box)
    render_case(
        "superstore_low_grouped_bar", ss_small, "low", "grouped_bar_means",
        group_col="区域", value_col="Sales", hue_col="类别",
        insight="区域和类别共同影响销售额", emphasize_hue="科技产品",
    )
    render_case(
        "superstore_mid_grouped_box", ss_small, "mid", "grouped_box",
        group_col="区域", value_col="Sales", hue_col="类别",
        insight="区域和类别共同影响销售额", emphasize_hue="科技产品",
    )
    render_case(
        "stage_low_facet_bar", stage_small, "low", "facet_bar_means",
        group_col="最终专业", value_col="分流前_平均学分绩点", facet_col="年级",
        insight="按年级分面后仍能比较 GPA",
    )
    gpa_box, _ = render_case(
        "stage_high_facet_box", stage_small, "high", "facet_box",
        group_col="最终专业", value_col="分流前_平均学分绩点", facet_col="年级",
        insight="按年级分面后仍能比较 GPA",
    )
    assert "离群点超出显示范围" not in html_text(gpa_box)
    render_case(
        "superstore_mid_histogram", ss_small, "mid", "histogram",
        group_col=None, value_col="Profit",
        insight="利润分布集中但有长尾",
    )
    render_case(
        "superstore_low_kpi", ss_small, "low", "kpi",
        group_col=None, value_col="Profit",
        insight="平均利润是核心指标",
    )
    render_case(
        "superstore_mid_line", ss_small, "mid", "line",
        group_col="Order Date", value_col="Sales",
        insight="销售额随时间波动",
        chart_kind="line",
    )

    rate_df = stage_small.copy()
    rate_df["高绩点"] = (rate_df["分流前_平均学分绩点"] >= 3.0).astype(int)
    render_case(
        "stage_low_rate", rate_df, "low", "rate",
        group_col="最终专业", value_col="高绩点",
        insight="不同专业高绩点比例不同", emphasize="视觉传达设计",
    )

    heatmap_low, _ = render_case(
        "superstore_low_heatmap_downgraded", ss_small, "low", "grouped_bar_means",
        group_col="区域", hue_col="类别", value_col="Sales",
        chart_kind="heatmap",
        insight="低受众热力图降级为分组均值条",
    )
    try:
        tmpl.visualize(
            ss_small,
            group_col="Sales", value_col="Profit",
            question="低受众散点应拒绝", insight="销售额和利润相关",
            audience="low", chart_kind="scatter", save_to=str(OUT / "low_scatter_should_fail.html"),
        )
    except ValueError as e:
        assert "散点图表达两个连续变量的关系，低受众读不了" in str(e)
        print("ok low scatter rejected")
    else:
        raise AssertionError("low scatter did not raise")

    # README comparison SVGs: same data, mid vs high.
    comparisons = [
        (
            "scatter",
            dict(group_col="Sales", value_col="Profit", chart_kind="scatter",
                 insight="销售额与利润整体正相关"),
            "scatter",
        ),
        (
            "heatmap",
            dict(group_col="区域", hue_col="类别", value_col="Sales", chart_kind="heatmap",
                 insight="区域 x 类别的平均销售额不同"),
            "heatmap",
        ),
        (
            "box",
            dict(group_col="最终专业", value_col="分流前_平均学分绩点",
                 insight="不同最终专业的分流前 GPA 有差异"),
            "box",
        ),
    ]
    for stem, kwargs, kind in comparisons:
        for audience in ["mid", "high"]:
            html, _ = render_case(
                f"{stem}_{audience}", stage_small if stem == "box" else ss_small, audience, kind,
                question=f"{stem} {audience}", **kwargs,
            )
            if stem == "scatter":
                text = html_text(html)
                assert "R²" not in text and "☒" not in text
            save_primary_svg(html, OUT / f"{stem}_{audience}.svg")

    print(f"gallery ok: {OUT}")


if __name__ == "__main__":
    main()
