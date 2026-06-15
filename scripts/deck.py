"""
data-viz-studio · 16:9 演示版式（scripts/deck.py）
──────────────────────────────────────────────────
把已渲染的 matplotlib SVG + 数据摘要，组装成 16:9 自包含 HTML 演示页。

架构归属
  外壳（16:9 画布 / 左蓝条 / 页眉页脚 / 栅格）= 格式/场合轴（4.1 精修，keynote 风格）。
  内容块（KPI 卡 / callout / 图表 SVG）= 受众轴（由 scripts/dataviz 产出）。
  → 两轴解耦：外壳不依赖受众档，可复用给其他受众；内容块不自选图型、不自加注释。

四个 bug 的结构性消灭
  1. 标题画两遍    → 每个槽是一个组件，结构上只渲染一次。
  2. 行距不统一    → 全部 line-height 从 deck-tokens.css 里的具名变量取。
  3. 文字不居中    → flexbox 布局对齐，不手摆坐标。
  4. 文本溢出卡片  → overflow-wrap: break-word + max-width: 100% 每个文本容器都有。

槽位系统
  地板槽（每次必出）：KPI 卡 ×N、核心发现 callout、图表块。
  可选槽（条件点亮，传 None 则整块不渲染，不留空壳）：
    - gap_bar   ⟺ 恰好两组对比时
    - mini_bars ⟺ 存在额外分组维度时

token 单一真源：assets/deck-tokens.css（本模块在 render_deck 时内联到 <style>）；
调色板语义色由 render_deck(palette=...) 从 Python palette 注入。
"""

import pathlib
import re

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_ASSETS_DIR = _REPO_ROOT / "assets"


def _load_tokens_css() -> str:
    return (_ASSETS_DIR / "deck-tokens.css").read_text(encoding="utf-8")


def _palette_css(palette: dict) -> str:
    """把 Python palette 注入 deck CSS 变量，保证外壳与内嵌图表同源同色。"""
    return (
        ":root {\n"
        f"  --color-emphasis: {palette['highlight']};\n"
        f"  --color-muted: {palette['muted']};\n"
        f"  --color-ink: {palette['ink']};\n"
        f"  --color-grid: {palette['grid']};\n"
        f"  --color-accent-bar: {palette['highlight']};\n"
        "}\n"
    )


_AUDIENCE_BADGES_RE = re.compile(
    r"\s*[·｜|/-]\s*"
    r"(?:(?:低|中|高|基础|进阶|高阶|基础型|进阶型|高阶型|low|mid|high)\s*)?受众版"
    r"(?:（[^）]*）|\([^)]*\))?"
)


def _strip_audience_badge(text: str) -> str:
    """Deck 对外成品不显示内部受众档标签。"""
    text = str(text)
    prev = None
    while prev != text:
        prev = text
        text = _AUDIENCE_BADGES_RE.sub("", text)
    return text.strip(" ·｜|/-")


# ── 组件渲染函数（每个函数 = 一个槽，结构上只调一次）────────────────────

def _kpi_card_html(card: dict) -> str:
    """{"label": str, "value": str} → <div class="kpi-card">…</div>。
    标题在 DOM 里只出现一次（不是手摆坐标，无法被意外复制）。"""
    label = str(card.get("label", ""))
    value = str(card.get("value", ""))
    return (
        '<div class="kpi-card">'
        f'<div class="kpi-card__value">{value}</div>'
        f'<div class="kpi-card__label">{label}</div>'
        '</div>'
    )


def _gap_bar_html(gap_bar: dict) -> str:
    """可选槽：两组差距条（纯 HTML/CSS bar，不用 SVG 坐标）。
    gap_bar = {"groups": [str, str], "values": [float, float], "unit": str}
    bar 宽度用 style="width:X%" 直接写入——数据驱动，不是 token，不需进 CSS 文件。"""
    g0, g1 = gap_bar["groups"]
    v0, v1 = gap_bar["values"]
    unit = gap_bar.get("unit", "")
    max_v = max(abs(v0), abs(v1), 1e-9)
    pct0 = min(100, round(abs(v0) / max_v * 100))
    pct1 = min(100, round(abs(v1) / max_v * 100))
    delta = v0 - v1
    sign = "+" if delta > 0 else ""
    unit_str = f" {unit}" if unit else ""  # thin space before unit

    return (
        '<div class="gap-bar">'
        '<div class="gap-bar__title">两组对比</div>'
        '<div class="gap-bar__row">'
        f'<span class="gap-bar__name">{g0}</span>'
        '<div class="gap-bar__track">'
        f'<div class="gap-bar__fill gap-bar__fill--em" style="width:{pct0}%"></div>'
        '</div>'
        f'<span class="gap-bar__val">{v0:.1f}{unit_str}</span>'
        '</div>'
        '<div class="gap-bar__row">'
        f'<span class="gap-bar__name">{g1}</span>'
        '<div class="gap-bar__track">'
        f'<div class="gap-bar__fill gap-bar__fill--mt" style="width:{pct1}%"></div>'
        '</div>'
        f'<span class="gap-bar__val">{v1:.1f}{unit_str}</span>'
        '</div>'
        f'<div class="gap-bar__delta">△ 差距 {sign}{delta:.1f}{unit_str}</div>'
        '</div>'
    )


def _mini_bars_html(mini_bars: list) -> str:
    """可选槽：迷你条排（额外分组维度摘要，纯 HTML/CSS）。
    mini_bars = [{"label": str, "value": float, "unit": str}, …]"""
    max_v = max((abs(b["value"]) for b in mini_bars), default=1e-9) or 1e-9
    rows = []
    for b in mini_bars:
        pct = min(100, round(abs(b["value"]) / max_v * 100))
        unit_str = f" {b['unit']}" if b.get("unit") else ""
        rows.append(
            '<div class="mini-bar">'
            f'<span class="mini-bar__label">{b["label"]}</span>'
            '<div class="mini-bar__track">'
            f'<div class="mini-bar__fill" style="width:{pct}%"></div>'
            '</div>'
            f'<span class="mini-bar__val">{b["value"]:.1f}{unit_str}</span>'
            '</div>'
        )
    return '<div class="mini-bars">' + "".join(rows) + "</div>"


# ── 组件样式（行距/字号/间距基准取 token；少量结构尺寸局部定义）────────────
_COMPONENT_CSS = """
/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Canvas: 16:9 固定尺寸 ── */
.deck {
  width: var(--canvas-w);
  height: var(--canvas-h);
  background: var(--color-surface-0);
  font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
  color: var(--color-ink);
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

/* ── 左蓝条（格式/场合外壳；与受众无关，可复用）── */
.deck__accent {
  width: var(--accent-bar-w);
  background: var(--color-accent-bar);
  flex-shrink: 0;
}

/* ── 主内容区 ── */
.deck__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--content-pad-y) var(--content-pad-x);
  gap: var(--sp-3);
  min-width: 0;
}

/* ── 页眉 ── */
.deck__header { flex-shrink: 0; }
.deck__title {
  font-size: var(--fs-heading);
  font-weight: 700;
  line-height: var(--lh-tight);
  color: var(--color-ink);
  overflow-wrap: break-word;
  max-width: 100%;
}
.deck__subtitle {
  font-size: var(--fs-body);
  line-height: var(--lh-base);
  color: var(--color-muted);
  margin-top: var(--sp-1);
  min-width: 0;
  overflow-wrap: break-word;
  word-break: break-word;
  line-break: anywhere;
  max-width: 100%;
}

/* ── 分隔线 ── */
.divider { height: 1px; background: var(--divider-color); flex-shrink: 0; }

/* ── KPI + callout 行 ── */
.deck__summary {
  display: flex;
  flex-direction: row;
  gap: var(--sp-4);
  align-items: stretch;
  flex-shrink: 0;
}
.deck__kpi-row {
  display: flex;
  flex-direction: row;
  gap: var(--sp-3);
  flex-wrap: wrap;
  align-items: flex-start;
  flex-shrink: 0;
}

/* ── KPI 卡（组件渲染一次）── */
.kpi-card {
  background: var(--color-surface-1);
  border-radius: var(--card-radius);
  padding: var(--card-pad);
  max-width: var(--card-max-w);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.kpi-card__value {
  font-size: var(--fs-display);
  font-weight: 800;
  line-height: var(--lh-tight);
  color: var(--color-emphasis);
  overflow-wrap: break-word;
  max-width: 100%;
}
.kpi-card__label {
  font-size: var(--fs-body);
  line-height: var(--lh-base);
  color: var(--color-ink);
  overflow-wrap: break-word;
  max-width: 100%;
}

/* ── Callout（核心发现，一句话）── */
.callout {
  flex: 1;
  min-width: 0;
  background: var(--color-surface-2);
  border-left: 3px solid var(--color-emphasis);
  border-radius: 0 var(--card-radius) var(--card-radius) 0;
  padding: var(--card-pad);
  font-size: var(--fs-subheading);
  line-height: var(--lh-base);
  color: var(--color-ink);
  overflow-wrap: break-word;
  word-break: break-word;
  line-break: anywhere;
  white-space: normal;
  max-width: 100%;
  display: flex;
  align-items: center;
}
.callout__text {
  display: block;
  min-width: 0;
  max-width: 100%;
  overflow-wrap: break-word;
  word-break: break-word;
  line-break: anywhere;
  white-space: normal;
}

/* ── 图表 + 可选槽行 ── */
.deck__content {
  display: flex;
  flex-direction: row;
  gap: var(--sp-4);
  flex: 1;
  min-height: 0;
}

/* ── 图表块（内嵌 matplotlib SVG；deck 不二次加注释）── */
.chart-block {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.chart-block svg {
  width: 100%;
  height: 100%;
  display: block;
}

/* ── 可选槽容器 ── */
.deck__optionals {
  width: 196px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

/* ── 差距条（⟺ 恰好两组对比；纯 CSS bar，不是 SVG 坐标）── */
.gap-bar {
  background: var(--color-surface-1);
  border-radius: var(--card-radius);
  padding: var(--card-pad);
}
.gap-bar__title {
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--color-ink);
  letter-spacing: .04em;
  margin-bottom: var(--sp-2);
}
.gap-bar__row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
}
.gap-bar__name {
  font-size: var(--fs-caption);
  color: var(--color-ink);
  width: 36px;
  flex-shrink: 0;
  overflow-wrap: break-word;
  line-height: var(--lh-base);
}
.gap-bar__track {
  flex: 1;
  height: 10px;
  background: var(--color-grid);
  border-radius: 5px;
  overflow: hidden;
}
.gap-bar__fill {
  height: 100%;
  border-radius: 5px;
}
.gap-bar__fill--em { background: var(--color-emphasis); }
.gap-bar__fill--mt { background: var(--color-muted); }
.gap-bar__val {
  font-size: var(--fs-caption);
  font-weight: 700;
  color: var(--color-ink);
  width: 40px;
  text-align: right;
  flex-shrink: 0;
  line-height: var(--lh-base);
}
.gap-bar__delta {
  font-size: var(--fs-caption);
  color: var(--color-negative);
  font-weight: 600;
  text-align: right;
  line-height: var(--lh-base);
}

/* ── 迷你条排（⟺ 存在额外分组维度；纯 CSS bar）── */
.mini-bars {
  background: var(--color-surface-1);
  border-radius: var(--card-radius);
  padding: var(--card-pad);
}
.mini-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
}
.mini-bar:last-child { margin-bottom: 0; }
.mini-bar__label {
  font-size: var(--fs-caption);
  color: var(--color-ink);
  width: 44px;
  flex-shrink: 0;
  overflow-wrap: break-word;
  line-height: var(--lh-base);
}
.mini-bar__track {
  flex: 1;
  height: 8px;
  background: var(--color-grid);
  border-radius: 4px;
  overflow: hidden;
}
.mini-bar__fill {
  height: 100%;
  background: var(--color-emphasis);
  border-radius: 4px;
}
.mini-bar__val {
  font-size: var(--fs-caption);
  font-weight: 700;
  color: var(--color-ink);
  width: 40px;
  text-align: right;
  flex-shrink: 0;
  line-height: var(--lh-base);
}

/* ── 页脚 ── */
.deck__footer {
  flex-shrink: 0;
  height: var(--footer-h);
  display: flex;
  align-items: center;
}
.footer__source {
  font-size: var(--fs-caption);
  color: var(--color-muted);
  line-height: var(--lh-base);
  overflow-wrap: break-word;
  max-width: 100%;
}
"""


def render_deck(
    title: str,
    subtitle: str,
    kpi_cards: list,
    callout: str,
    chart_svg: str,
    *,
    palette: dict,
    gap_bar=None,
    mini_bars=None,
    source: str = "",
    save_to: str = "deck.html",
) -> str:
    """产出自包含 16:9 HTML 演示页。

    kpi_cards: [{"label": str, "value": str}, …]
    chart_svg: 由 scripts/dataviz 图型基元产出的 SVG 字符串
               （deck 不重选图型、不另加注释——所有判断已在渲染层完成）。
    palette: 与 chart_svg 渲染时同一份 palette（如 tmpl.STANDARD_PALETTE）。
    gap_bar=None  → 差距条整块不渲染（不留空壳）。
    mini_bars=None → 迷你条排整块不渲染。
    """
    subtitle = _strip_audience_badge(subtitle)
    tokens_css = _load_tokens_css()
    palette_css = _palette_css(palette)

    kpi_html = "".join(_kpi_card_html(c) for c in kpi_cards)
    gap_html = _gap_bar_html(gap_bar) if gap_bar is not None else ""
    mini_html = _mini_bars_html(mini_bars) if mini_bars is not None else ""
    optionals = (
        f'<div class="deck__optionals">{gap_html}{mini_html}</div>'
        if gap_html or mini_html else ""
    )
    footer_inner = (
        f'<div class="footer__source">来源：{source}</div>' if source else ""
    )

    html = f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=960">
<title>{title}</title>
<style>
/* ── Token 单一真源（内联自 assets/deck-tokens.css）── */
{tokens_css}
/* ── Palette 单一真源（注入自 Python palette）── */
{palette_css}
{_COMPONENT_CSS}
</style>
</head>
<body>
<div class="deck">
  <div class="deck__accent" role="presentation" aria-hidden="true"></div>
  <div class="deck__body">
    <header class="deck__header">
      <h1 class="deck__title">{title}</h1>
      <p class="deck__subtitle">{subtitle}</p>
    </header>
    <div class="divider" role="separator"></div>
    <div class="deck__summary">
      <div class="deck__kpi-row">{kpi_html}</div>
      <div class="callout" role="note"><span class="callout__text">{callout}</span></div>
    </div>
    <div class="deck__content">
      <div class="chart-block">{chart_svg}</div>
      {optionals}
    </div>
    <div class="divider" role="separator"></div>
    <footer class="deck__footer">{footer_inner}</footer>
  </div>
</div>
</body>
</html>"""

    with open(save_to, "w", encoding="utf-8") as f:
        f.write(html)
    return save_to


# ── Demo：验收两张 deck ───────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    import dataviz as tmpl

    print("使用字体:", tmpl.setup_cjk_font())

    pal = tmpl.STANDARD_PALETTE
    aud_low = tmpl.AUDIENCE_PROFILES["low"]
    test_dir = _REPO_ROOT / "__test__"

    # ── Demo 1: stage_reassign（自选 vs 调剂 × 首年GPA，低受众）────
    rng = np.random.default_rng(7)
    df_stage = pd.DataFrame({
        "分组": ["自选"] * 60 + ["调剂"] * 60,
        "首年GPA": np.concatenate([
            rng.normal(3.2, 0.40, 60),
            rng.normal(2.7, 0.45, 60),
        ]).clip(0, 4),
    })
    insight_s = "调剂学生首年GPA平均低约0.5分，差距在入学第一年已显现"

    chart_svg_s = tmpl.bar_means_comparison(
        df_stage, "分组", "首年GPA",
        insight=insight_s,
        descriptive="自选 vs 调剂 首年GPA均值对比",
        palette=pal, audience_prof=aud_low, level=1, emphasize="调剂",
    )
    means_s = df_stage.groupby("分组")["首年GPA"].mean()

    out1 = render_deck(
        title="自选 vs 调剂：首年学业表现有差距吗？",
        subtitle="2024届新生模拟数据 · 标准版",
        kpi_cards=[
            {"label": "自选均值 GPA", "value": f"{means_s['自选']:.2f}"},
            {"label": "调剂均值 GPA", "value": f"{means_s['调剂']:.2f}"},
            {"label": "样本量", "value": str(len(df_stage))},
        ],
        callout=insight_s,
        chart_svg=chart_svg_s,
        palette=pal,
        gap_bar={
            "groups": ["自选", "调剂"],
            "values": [float(means_s["自选"]), float(means_s["调剂"])],
            "unit": "GPA",
        },
        source="模拟数据（seed=7，N=120）",
        save_to=str(test_dir / "deck_stage_reassign.html"),
    )
    print("Demo 1:", out1)

    # ── Demo 2: titanic（各舱位生还率，低受众）────────────────────────
    # 本 CSV：class="1st"/"2nd"/"3rd"，survived="yes"/"no"（字符串）
    df_t = tmpl.load_dataframe(str(_REPO_ROOT / "__test__" / "titanic.csv"))
    df_t = df_t[df_t["class"].isin(["1st", "2nd", "3rd"])].copy()
    df_t["survived_01"] = (df_t["survived"] == "yes").astype(int)
    insight_t = "头等舱生还率 62%，三等舱仅约 25%——舱位等级是生还的最强预测因素"

    chart_svg_t = tmpl.rate_comparison(
        df_t, "class", "survived_01",
        insight=insight_t,
        descriptive="各舱位乘客生还率",
        palette=pal, audience_prof=aud_low, level=1, emphasize="1st", show_ci=False,
    )
    rates_t = df_t.groupby("class")["survived_01"].mean()
    counts_t = df_t.groupby("class")["survived_01"].count()

    out2 = render_deck(
        title="舱位等级与生还率：差距有多大？",
        subtitle="泰坦尼克号乘客数据 · 标准版",
        kpi_cards=[
            {"label": "1等舱生还率", "value": f"{rates_t['1st']:.0%}"},
            {"label": "2等舱生还率", "value": f"{rates_t['2nd']:.0%}"},
            {"label": "3等舱生还率", "value": f"{rates_t['3rd']:.0%}"},
        ],
        callout=f"头等舱乘客生还率（{rates_t['1st']:.0%}）是三等舱（{rates_t['3rd']:.0%}）的 {rates_t['1st']/rates_t['3rd']:.1f} 倍，舱位是最强预测因素。",
        chart_svg=chart_svg_t,
        palette=pal,
        gap_bar={
            "groups": ["1等舱", "3等舱"],
            "values": [float(rates_t["1st"]) * 100, float(rates_t["3rd"]) * 100],
            "unit": "%",
        },
        mini_bars=[
            {"label": lbl, "value": int(n)}
            for lbl, n in {"1等舱": counts_t["1st"], "2等舱": counts_t["2nd"], "3等舱": counts_t["3rd"]}.items()
        ],
        source="titanic.csv（Kaggle）",
        save_to=str(test_dir / "deck_titanic.html"),
    )
    print("Demo 2:", out2)
