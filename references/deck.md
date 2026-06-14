# Deck

## 4.1 演示版式

`scripts/deck.py · render_deck(...)` 把已渲染的 matplotlib SVG + 数据摘要，组装成 **16:9 自包含 HTML** 演示页。

## 架构归属

- **外壳**（16:9 画布 / 左蓝条 / 页眉页脚 / 栅格）= 格式/场合轴。外壳与受众无关，可复用给 mid/high。
- **内容块**（KPI 卡 / callout / 图表 SVG）= 受众轴（由 `scripts/dataviz` 产出）。

## 纪律

deck 不重选图型、不另加图表注释——图型判断和注释地板由渲染层已处理完毕；`chart_svg` 原样内嵌。

## Token 单一真源

`assets/deck-tokens.css` 提供字号阶 / 行距 / 间距基准 / 结构 token / deck 专属色。
调色板语义色由 `render_deck(palette=...)` 从 Python palette 注入；少量结构尺寸（列宽 / 轨道高 / 边框）由组件局部定义。

## 槽位系统

| 槽位 | 类型 | 点亮条件 |
|--|--|--|
| KPI 卡 ×N | 地板（必出）| 始终渲染 |
| 核心发现 callout | 地板（必出）| 始终渲染 |
| 图表块 | 地板（必出）| 始终渲染 |
| `gap_bar` 差距条 | 可选 | ⟺ 恰好两组对比（传 `None` 则整块不渲染）|
| `mini_bars` 迷你条排 | 可选 | ⟺ 存在额外分组维度（传 `None` 则整块不渲染）|

## 调用示例

```python
import sys
sys.path.insert(0, "<repo_root>/scripts")
import dataviz as dv
from scripts.deck import render_deck

dv.setup_cjk_font()
pal = dv.STANDARD_PALETTE

chart_svg = dv.bar_means_comparison(df, group_col, value_col,
    insight=insight, descriptive=...,
    palette=pal,
    audience_prof=dv.AUDIENCE_PROFILES["low"],
    level=1, emphasize=...)

render_deck(
    title=..., subtitle=...,
    kpi_cards=[{"label": ..., "value": ...}, ...],
    callout=...,          # 一句结论
    chart_svg=chart_svg,
    palette=pal,          # 与 chart_svg 使用同一份 palette
    gap_bar={"groups": [g0, g1], "values": [v0, v1], "unit": ...},  # 两组时传
    mini_bars=[{"label": ..., "value": ...}, ...],                  # 多维度时传
    source=...,
    save_to="deck.html")
```
