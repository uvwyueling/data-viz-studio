# Chart Catalog

## 调用渲染层

```python
import sys
sys.path.insert(0, "<repo_root>/scripts")
import dataviz as dv

df = dv.load_dataframe(<上传文件路径>)        # .csv / .xlsx / .xls / .json
df["col_01"] = dv.encode_binary(df, "col", pos_value="yes")

dv.visualize(df, group_col, value_col,
    question=..., insight=<第 2 步 EDA 得到的洞察>,
    audience=<high/mid/low>,
    emphasize=<要强调的组>,
    hue_col=<可选：要对比的子总体列；给了就出"分组对比图">,
    emphasize_hue=<可选：高亮哪个子总体>,
    facet_col=<可选：分面列；给了就出 small multiples>,
    chart_kind=<可选：手动覆盖路由，如 "line" 用于整数年份等无法自动判断的有序 x>,
    save_to="output.html")

# 单变量模式：group_col 不传（或传 None）→ 直方图（进阶型 / 高阶型统计素养人群）/ 大数字 KPI（基础型统计素养人群）
dv.visualize(df, value_col="age", question=..., insight=..., audience=..., save_to=...)

# 散点 + 回归：group_col 传 x_col，value_col 传 y_col；可选 hue_col 分系列
dv.visualize(df, group_col="Sales", value_col="Profit",
    question=..., insight=..., audience="mid", chart_kind="scatter", hue_col=..., save_to=...)

# 热力图：group_col 传 row_col，hue_col 传 col_col，value_col 传格子聚合值
dv.visualize(df, group_col="区域", hue_col="类别", value_col="Sales",
    question=..., insight=..., audience="mid", chart_kind="heatmap", save_to=...)

# 4.1 精修（可选）：在标准版之上套场合
dv.visualize(..., occasion="keynote"/"internal"/"portfolio", ...)
```

## 路由规则

`_route` 是自动选型单一真源；`chart_kind` 可覆盖。基础型统计素养人群的 scatter / heatmap 覆盖规则在 `visualize()` 解析覆盖处集中执行。

| 条件（按优先级） | 路由结果 |
|--|--|
| `group_col=None` + 基础型统计素养人群（`low`） | `kpi` |
| `group_col=None` + 进阶型 / 高阶型统计素养人群（`mid` / `high`） | `histogram` |
| `facet_col` 非空 | `facet_box`（`low` → `facet_bar_means`） |
| `hue_col` 非空 | `grouped_box`（`low` → `grouped_bar_means`） |
| `value_col` 是 0/1 列 | `rate` |
| `group_col` 是 datetime | `line` |
| 基础型统计素养人群（`low`） | `bar_means` |
| 其余 | `box` |

**datetime 列以外的有序 x**（整数年份、月份字符串等）需手传 `chart_kind="line"`。

## 图型目录

| chart_kind | 是什么 | 何时用 | 需要哪些列 | 对进阶型统计素养人群是否临界 | 基础型统计素养人群降级到什么 |
|--|--|--|--|--|--|
| `box` | 分类 × 连续值的箱线图 | 比较各组分布、中位数、离散程度 | `group_col` 分类；`value_col` 连续数值 | 是 | `bar_means` |
| `bar_means` | 均值柱 + 标准差误差棒 | 基础型统计素养人群比较组间均值 | `group_col` 分类；`value_col` 连续数值 | 否 | 已是基础型统计素养人群图型 |
| `rate` | 分类 × 0/1 比率图 | 生还率、转化率、合格率等 | `group_col` 分类；`value_col` 0/1 | 否 | 仍用 `rate`，基础型统计素养人群不显示 CI |
| `grouped_box` | 分类 × 子总体 × 连续值的分组箱线图 | 比较多个子总体在各类别下的分布 | `group_col` 分类；`hue_col` 子总体；`value_col` 连续数值 | 是 | `grouped_bar_means` |
| `grouped_bar_means` | 分类 × 子总体的分组均值条 | 基础型统计素养人群比较多子总体均值 | `group_col` 分类；`hue_col` 子总体；`value_col` 连续数值 | 否 | 已是基础型统计素养人群图型 |
| `facet_box` | 小多图箱线图 | 用一个额外维度分面比较分布 | `group_col` 分类；`facet_col` 分面；`value_col` 连续数值 | 是 | `facet_bar_means` |
| `facet_bar_means` | 小多图均值条 | 基础型统计素养人群在分面内比较均值 | `group_col` 分类；`facet_col` 分面；`value_col` 连续数值 | 否 | 已是基础型统计素养人群图型 |
| `histogram` | 单变量直方图 | 查看一个连续变量的分布 | `value_col` 连续数值；`group_col=None` | 否，histogram 在进阶型统计素养人群下沿但够得着 | `kpi` |
| `kpi` | 大数字 KPI | 基础型统计素养人群只需要一个核心指标 | `value_col` 数值或 0/1；`group_col=None` | 否 | 已是基础型统计素养人群图型 |
| `line` | 折线趋势图 | 时间或明确有序 x 上的趋势 | `group_col` datetime 或有序 x；`value_col` 数值；可选 `hue_col` | 否 | 仍用 `line`，基础型统计素养人群标数据点 |
| `scatter` | 散点 + 线性回归 | 两个连续变量的关系 | `group_col` 传 x_col；`value_col` 传 y_col；可选 `hue_col` | 是 | **拒绝渲染**：基础型统计素养人群需要更明确的图形引导；自动分箱会把「关系」静默换成「均值」，违反 P0 口径 |
| `heatmap` | 双分类交叉均值热力图 | 两个分类维度交叉后的平均值 | `group_col` 传 row_col；`hue_col` 传 col_col；`value_col` 数值 | 是 | `grouped_bar_means`（row_col→group_col，col_col→hue_col） |
