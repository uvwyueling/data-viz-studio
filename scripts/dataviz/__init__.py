from .fonts import setup_cjk_font
from .io import load_dataframe, encode_binary
from .config import STANDARD_PALETTE, OCCASION_PROFILES, AUDIENCE_PROFILES, _BORDERLINE_FOR_MID, _READING_GUIDE, ANNOTATE_MAX
from .routing import _route, _annotation_floor, _resolve_level, _check_cardinality, _looks_like_rate, _looks_like_trend
from .charts import (
    box_comparison, bar_means_comparison, rate_comparison, grouped_box_comparison, grouped_bar_means_comparison,
    histogram_distribution, line_trend, kpi_number, facet_box_comparison, facet_bar_means_comparison,
    scatter_regression, heatmap_comparison,
)
from .render import render_html
from .visualize import visualize

__all__ = [
    "visualize", "setup_cjk_font", "load_dataframe", "encode_binary", "render_html",
    "STANDARD_PALETTE", "OCCASION_PROFILES", "AUDIENCE_PROFILES", "_BORDERLINE_FOR_MID", "_READING_GUIDE", "ANNOTATE_MAX",
    "_route", "_annotation_floor", "_resolve_level", "_check_cardinality", "_looks_like_rate", "_looks_like_trend",
    "box_comparison", "bar_means_comparison", "rate_comparison", "grouped_box_comparison",
    "grouped_bar_means_comparison", "histogram_distribution", "line_trend", "kpi_number",
    "facet_box_comparison", "facet_bar_means_comparison", "scatter_regression", "heatmap_comparison",
]
