---
name: data-viz-studio
description: 把用户上传的数据集（CSV/Excel/JSON）+ 一个数据问题，做成「面向特定受众、用对图像语言」的可视化图表（自包含 HTML）。当用户上传表格数据、想把其中某个数据问题或某一列做成图传达给特定受众时使用——尤其当受众的统计基础参差、需要替他们挑图型、做降级翻译时。涉及「这张图给谁看 / 他看得懂吗 / 选什么图型 / 数据可视化 / 出图 / 作图 / 图表选型」时都应触发本 skill。
---

# Data Viz Studio

## 目的
面对合适的受众，用合适的图像语言传达数据洞察——以最低沟通成本、最低调试成本出图。

**核心只有一根轴：受众。** 受众决定图表「是什么」（图型 + 必需注释，结构层、不可逆、用户自己判断不了）——这是 skill 独有的判断。场合只决定图表「穿什么」（配色 / 字体 / 尺寸 / 格式，样式层、可逆、用户自己有主见），是出图后的可选精修。

## 触发
用户上传 Excel/CSV/JSON，想把其中某个数据问题做成图表传达时使用。

## 输入
1. 数据集文件（.csv / .xlsx / .xls / .json）
2. 待回答的数据问题（或要重点看哪一列）
3. 受众的图型素养：`high` / `mid` / `low`（定义见「受众轴」）

注：**应用场合不是必填输入**。默认出「标准版」；用户拿到后若要按实际场合精修，再进第 4.1 步。

## 何时不适合
1. 实时数据流的可视化。
2. 理科期刊投稿图：读者恒为同行专家（用不上本 skill 的受众翻译引擎），且需要矢量 PDF/EPS、双栏窄尺寸（本 skill 出 HTML）——这类有专门工具，不在范围内。

## 工作流

### 第 0 步 · 用户上传数据集文件

### 第 1 步 · 确定这张图要回答的问题
没说清就主动问："你想用这张图回答什么问题？" 或 "想重点看哪一列？"

### 第 2 步 · 进数据做 EDA，挖出洞察（insight）
这一步是**推理**，由 Claude 做；产出一个 insight 字符串传给渲染层，不在渲染层里现挖。

### 第 3 步 · 按受众图型素养选型 → 出【标准版】
依「受众轴」选图型 / 决定是否降级，调 `visualize()` 出图（**不传 occasion**）。
标准版 = `STANDARD_PALETTE`（中性样式基线）+ 受众注释地板。这一步就把标准版交付给用户。

### 第 4 步 · 交付与精修
- **4.0** 用户觉得好 → 导出，工作流结束。
- **4.1** 用户按实际场合提精修：主题色 / 字体 / 导出尺寸 / 注释密度 / 导出格式等。
  传 `occasion="keynote" / "internal" / "portfolio"` 套对应场合预设。
  **铁律：场合只能在受众注释地板之上叠加注释，绝不能减到地板以下**——低受众的直接标注+结论是「结构」，不是场合能动的样式。

### 自检
对照下方自检列表过一遍，修掉明显问题再交付。

## 决策依据

### 受众轴（唯一核心）→ 以「能读懂哪种图型」定义，不用职业标签
分界线钉在具体图型上：**高/中 = 箱线图；中/低 = 直方图（分布）**。

| 受众档 | 分界判据 | 读得懂的图型集 | 注释地板（固有属性） |
|--|--|--|--|
| **high** | 直接读懂**箱线图** | 箱线 / 小提琴 / ECDF / 散点+回归 / 热力图 / 对数轴 / 误差棒 | 主标题 + x/y 轴标签 |
| **mid** | 读不了箱线，但跟得上**直方图** | 条形 / 折线 / 分组堆叠 / 直方 / 散点；箱线临界 | 主标题 + 轴标签 +（**遇箱线类补一句解读**） |
| **low** | 连直方图都"盯着发呆" | 条形 / 折线 / 大数字 KPI / 简单部分对整体；**避免分布类与双编码** | 主标题 + 轴标签 + **直接标注 + 一句结论** |

注释地板是**受众档的固有属性**，不是一个可调旋钮：每一档的图型与它必需的注释是一体的（low 的直接标注、mid 遇箱线的解读句，都是「读懂这张图」的结构，不是装饰）。
为什么用图型而非职业定义：职业（高管 / 科研）只是图型素养的代理，且常猜错（量化高管读得懂箱线，转行新人读不了）。换成「能读懂什么图」，也正好能直接拿去问用户："你的受众能直接看懂箱线图吗？"

### 注释模型（两层，分挂两轴）
- **地板层 = 受众设定**（结构，烤进标准版）。
- **叠加层 = 场合设定**（样式，4.1 才加）：作品集的引导叙事、来源脚注等。
- **方向**：地板由受众来，场合在其上叠，**只增不减**。
- **实现**：单一真源 `_annotation_floor(audience, chart_kind)`，图型函数一律调用它、不各自实现。"中受众遇箱线类补一句"的判断也在这里查表（`_BORDERLINE_FOR_MID`），不复制进每个图型函数（避免 DRY 反模式）。

### 场合预设（4.1 精修，可选）→ 标准版之上换肤
| 场合 | 配色性格 | 注释叠加 |
|--|--|--|
| `keynote` 公众演讲单页 | 一个高亮 + 中性灰，大色块 | 极少（讲者口头解释） |
| `internal` 团队内部汇报 | 团队 / 品牌色 | 适度 |
| `portfolio` 作品集 / 对外 | 强设计语言、自定义排印 | 引导式叙事标注 |

### 4.1 演示版式（Deck）→ 低受众 keynote 的确定性呈现层

`scripts/deck.py · render_deck(...)` 把已渲染的 matplotlib SVG + 数据摘要，组装成 **16:9 自包含 HTML** 演示页。

**架构归属**（外壳与内容不焊回去）：
- **外壳**（16:9 画布 / 左蓝条 / 页眉页脚 / 栅格）= 格式/场合轴。外壳与受众无关，可复用给 mid/high。
- **内容块**（KPI 卡 / callout / 图表 SVG）= 受众轴（由 `data-viz_template.py` 产出）。

**纪律**：deck 不重选图型、不另加图表注释——图型判断和注释地板由渲染层已处理完毕；`chart_svg` 原样内嵌。

**token 单一真源**：`assets/deck-tokens.css`（字号阶 / 行距 / 间距 / 语义色 / 16:9 画布）。所有组件只从这里取值，不写裸数值。语义色 emphasis/muted 与 `STANDARD_PALETTE` 一致，外壳与内嵌图表同色系。

**槽位系统**：

| 槽位 | 类型 | 点亮条件 |
|--|--|--|
| KPI 卡 ×N | 地板（必出）| 始终渲染 |
| 核心发现 callout | 地板（必出）| 始终渲染 |
| 图表块 | 地板（必出）| 始终渲染 |
| `gap_bar` 差距条 | 可选 | ⟺ 恰好两组对比（传 `None` 则整块不渲染）|
| `mini_bars` 迷你条排 | 可选 | ⟺ 存在额外分组维度（传 `None` 则整块不渲染）|

```python
# 先从渲染层拿 SVG（直接调图型基元，不经 visualize()）
import importlib, sys
sys.path.insert(0, "<repo_root>")
tmpl = importlib.import_module("data-viz_template")
tmpl.setup_cjk_font()

chart_svg = tmpl.bar_means_comparison(df, group_col, value_col,
    insight=insight, descriptive=…,
    palette=tmpl.STANDARD_PALETTE,
    audience_prof=tmpl.AUDIENCE_PROFILES["low"],
    level=1, emphasize=…)

# 再组装 deck
from scripts.deck import render_deck
render_deck(
    title=…, subtitle=…,
    kpi_cards=[{"label": …, "value": …}, …],
    callout=…,          # 一句结论
    chart_svg=chart_svg,
    gap_bar={"groups": [g0, g1], "values": [v0, v1], "unit": …},  # 两组时传
    mini_bars=[{"label": …, "value": …}, …],                       # 多维度时传
    source=…,
    save_to="deck.html")
```

## 调用渲染层

```python
# ① 把上传文件读成 DataFrame（按扩展名分发，自动兜底 CSV 的 GBK/UTF-8 编码）
df = load_dataframe(<上传文件路径>)        # .csv / .xlsx / .xls / .json

# 文本型 0/1 列预处理（如 "yes"/"no" → 1/0）
df["col_01"] = encode_binary(df, "col", pos_value="yes")

# ② 出【标准版】（第 3 步）：不传 occasion
visualize(df, group_col, value_col,
    question=…, insight=<第 2 步 EDA 得到的洞察>,
    audience=<high/mid/low>,
    emphasize=<要强调的组>,
    hue_col=<可选：要对比的子总体列；给了就出"分组对比图">,
    emphasize_hue=<可选：高亮哪个子总体>,
    chart_kind=<可选：手动覆盖路由，如 "line" 用于整数年份等无法自动判断的有序 x>,
    save_to="output.html")

# 单变量模式：group_col 不传（或传 None）→ 直方图（mid/high）/ 大数字KPI（low）
visualize(df, value_col="age", question=…, insight=…, audience=…, save_to=…)

# ③ 4.1 精修（可选）：在标准版之上套场合
visualize(..., occasion="keynote"/"internal"/"portfolio", ...)
```

**路由规则**（`_route` 单一真源，`chart_kind` 可覆盖）：

| 条件（按优先级） | 路由结果 |
|--|--|
| `group_col=None` + low 受众 | `kpi`（大数字 KPI） |
| `group_col=None` + mid/high | `histogram`（直方图） |
| `hue_col` 非空 | `grouped_box`（low → `grouped_bar_means`） |
| `value_col` 是 0/1 列 | `rate`（比率图） |
| `group_col` 是 datetime | `line`（折线趋势图） |
| low 受众 | `bar_means`（均值条） |
| 其余 | `box`（箱线图） |

**datetime 列以外的有序 x**（整数年份、月份字符串等）需手传 `chart_kind="line"`。
这一步只渲染、不做判断——判断在第 1–4 步做完；**不要**在这里现写 matplotlib 代码。

## 自检列表

### P0（对错）
1. **图表回答的是不是用户原话里那个问题？** 比较对象 / 分组 / 子总体 / 度量 / 口径必须与用户逐字对应；严禁把 A vs B 擅自换成别的（例：把"全体 vs 幸存"换成"幸存 vs 遇难"、把子集换成补集、把"分布"换成"均值"）。框架对当前图型不顺手就**回去问用户，不要静默替换**。
2. **标准版有没有被悄悄套了某个场合的风格？** 第 3 步只该用标准样式基线 + 受众地板；场合风格只在用户进 4.1 后才加。
3. 中文是否妥善渲染？CSS / 字体里的 CJK font-family 是否加载到？
4. 图表类型是否适配数据类型？

### P1（易读性）
1. 标签 / 数字有没有与任何图表结构（柱体、误差棒、网格线、坐标轴、相邻标签）重叠？重叠就移锚点或缩字号。

## 维护
<每次手动改了图，把那条规则回填到对应小节——这是经验沉淀的入口。
新增图型时，记得在 `_BORDERLINE_FOR_MID` 登记它对「中」受众是否临界（要不要补解读句）。
新增 deck 槽位时，在「槽位系统」表里登记它的点亮条件（不登记 = 调用者不知道什么时候传）。>
