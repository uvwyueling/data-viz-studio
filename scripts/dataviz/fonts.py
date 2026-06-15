import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 外框化只保证字体已有的字形；数学/特殊符号请用 mathtext 或 ASCII，勿直接写 ²³μ± 等字符。

# ── 0. 中文字体守卫 + SVG 字形外框化（头号翻车点，HTML 版）──────────
_CJK_PROBE = "中"  # 拿这个字去探：某字体到底有没有中文字形（不靠字体名，靠真查字形表）

# 三级兜底全落空时，按文件路径强行注册的常见系统中文字体（存在才用）。
# 专治 macOS：PingFang/STHeiti 等是 .ttc 集合，matplotlib 常按名枚举不到。
_KNOWN_CJK_FILES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def _has_cjk_glyph(font_path):
    """这个字体文件里到底有没有中文字形？不信字体名，直接查字形表。"""
    from matplotlib.ft2font import FT2Font
    try:
        return FT2Font(font_path).get_char_index(ord(_CJK_PROBE)) != 0
    except Exception:
        return False


def _scan_registered_cjk():
    """遍历 matplotlib 已注册字体，挑第一个真能渲染中文的；偏好干净黑体/无衬线，避开装饰体。"""
    seen, hits = set(), []
    for f in fm.fontManager.ttflist:
        if f.name in seen:
            continue
        seen.add(f.name)
        if _has_cjk_glyph(f.fname):
            hits.append(f.name)
    if not hits:
        return None

    def score(n):  # 0=黑体/无衬线优先，1=宋/明，2=其它
        s = n.lower()
        if any(k in s for k in ["hei", "黑", "gothic", "sans", "yahei", "pingfang", "yuan", "圆"]):
            return 0
        if any(k in s for k in ["song", "宋", "ming", "mincho", "serif"]):
            return 1
        return 2

    return sorted(hits, key=score)[0]


def _register_known_cjk():
    """连扫描都落空（系统字体多为 .ttc、没被 matplotlib 枚举进来），按已知路径强行注册一个。"""
    import os
    for path in _KNOWN_CJK_FILES:
        if os.path.exists(path) and _has_cjk_glyph(path):
            fm.fontManager.addfont(path)
            return next((f.name for f in fm.fontManager.ttflist if f.fname == path), None)
    return None


def setup_cjk_font():
    # 1) 先试"指名道姓"的常用中文字体：命中最稳，渲染质量也可控
    preferred = ["Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC",
                 "Heiti SC", "STHeiti", "Hiragino Sans GB", "Arial Unicode MS",
                 "Microsoft YaHei", "SimHei", "WenQuanYi Zen Hei"]
    available = {f.name for f in fm.fontManager.ttflist}
    chosen = next((n for n in preferred if n in available), None)

    # 2) 名单落空 → 扫描已注册字体里任何一个真含中文字形的（macOS 上多半走这条）
    if chosen is None:
        chosen = _scan_registered_cjk()

    # 3) 还落空 → 按已知系统路径强行注册（专治 .ttc 没被枚举）
    if chosen is None:
        chosen = _register_known_cjk()

    if chosen is None:
        raise RuntimeError("未找到可用中文字体，请先安装 CJK 字体；宁可报错也不要静默输出 □□□。")

    plt.rcParams["font.sans-serif"] = [chosen]
    plt.rcParams["axes.unicode_minus"] = False
    # 关键：把 SVG 里的文字转成矢量路径（path），而不是留作依赖字体的 <text>。
    # 这样生成时需要中文字体（这里已校验），但【浏览器端不再需要任何字体】，
    # 中文永远按路径渲染——HTML 世界里的 □□□ 风险被结构性根除。
    plt.rcParams["svg.fonttype"] = "path"
    return chosen

