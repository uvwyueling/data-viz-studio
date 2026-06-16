# ── HTML 外壳：把 SVG 内嵌成一个自包含页面 ──────────────────────
def render_html(title, meta=None, primary_svg=None, alt_items=None, save_to="chart.html", show_meta=False):
    """alt_items: [(说明, svg), ...]。生成一个不依赖任何外部资源的 .html。"""
    alt_items = alt_items or []
    alts = ""
    for label, svg in alt_items:
        alts += f'<section class="alt"><h3>{label}</h3><div class="chart">{svg}</div></section>'
    alts_block = f'<div class="alts"><h2>其他视角</h2>{alts}</div>' if alt_items else ""
    meta_block = f'<p class="meta">{meta}</p>' if show_meta else ""
    title_block = f"<h1>{title}</h1>" if title else ""
    html = f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  *{{box-sizing:border-box;}}
  body{{margin:0 auto;max-width:1040px;padding:40px 28px;background:#FAFAF7;color:#1F2933;
       font-family:-apple-system,"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Microsoft YaHei","Helvetica Neue",sans-serif;
       line-height:1.5;}}
  h1{{font-size:22px;line-height:1.35;margin:0 0 6px;font-weight:700;letter-spacing:0;}}
  .meta{{color:#6B7280;font-size:13px;margin:0 0 24px;}}
  .chart{{margin-top:10px;}}
  .chart svg{{width:100%;height:auto;display:block;}}
  .alts{{margin-top:36px;padding-top:12px;border-top:1px solid #E5E7EB;}}
  .alts>h2{{font-size:13px;color:#6B7280;font-weight:600;letter-spacing:0;margin:16px 0 8px;}}
  .alt h3{{font-size:14px;color:#6B7280;font-weight:500;margin:24px 0 6px;}}
  @media (max-width: 640px){{body{{padding:24px 14px;}} h1{{font-size:19px;}}}}
</style>
</head>
<body>
  {title_block}
  {meta_block}
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
