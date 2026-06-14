# ── HTML 外壳：把 SVG 内嵌成一个自包含页面 ──────────────────────
def render_html(title, meta, primary_svg, alt_items, save_to):
    """alt_items: [(说明, svg), ...]。生成一个不依赖任何外部资源的 .html。"""
    alts = ""
    for label, svg in alt_items:
        alts += f'<section class="alt"><h3>{label}</h3><div class="chart">{svg}</div></section>'
    alts_block = f'<div class="alts"><h2>其他视角</h2>{alts}</div>' if alt_items else ""
    html = f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  *{{box-sizing:border-box;}}
  body{{margin:0 auto;max-width:880px;padding:32px 20px;background:#fff;color:#222;
       font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}}
  h1{{font-size:20px;margin:0 0 4px;}}
  .meta{{color:#666;font-size:13px;margin:0 0 24px;}}
  .chart svg{{width:100%;height:auto;display:block;}}
  .alts{{margin-top:32px;padding-top:8px;border-top:1px solid #e8e8e8;}}
  .alts>h2{{font-size:13px;color:#666;font-weight:600;letter-spacing:.04em;margin:16px 0 8px;}}
  .alt h3{{font-size:14px;color:#666;font-weight:500;margin:24px 0 4px;}}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">{meta}</p>
  <div class="primary chart">{primary_svg}</div>
  {alts_block}
</body>
</html>"""
    with open(save_to, "w", encoding="utf-8") as f:
        f.write(html)
    return save_to


def _alternative_item(label_kind, svg):
    """探索/调试用备选图型。标签保持中性，不暗示未配置的受众档。"""
    return (f"备选图型 · {label_kind}", svg)


