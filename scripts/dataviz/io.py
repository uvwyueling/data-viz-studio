import pandas as pd


# ── 0.5 数据读取：把用户上传的文件读成 DataFrame（visualize 的入口）────
def load_dataframe(path):
    """按扩展名分发读取 CSV/Excel/JSON，处理编码并做基础清洗，返回干净的 DataFrame。

    visualize() 只接收 df；从"用户上传的文件"到 df 的这一步由这里负责。
    """
    import os
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = _read_csv_smart(path)
    elif ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(path)
        except ImportError as e:
            engine = "xlrd" if ext == ".xls" else "openpyxl"
            raise ImportError(
                f"读取 {ext} 需要 {engine}，请先安装：pip install {engine}"
            ) from e
    elif ext == ".json":
        df = _read_json_smart(path)
    else:
        raise ValueError(f"不支持的文件类型：{ext}（仅支持 .csv / .xlsx / .xls / .json）")
    return _basic_clean(df)


def _read_csv_smart(path):
    """CSV 编码逐个试：UTF-8 → GBK → UTF-8-SIG。
    中文 CSV 头号翻车点就是编码：Excel 导出常是 GBK，带 BOM 的是 utf-8-sig。
    先试 UTF-8（自校验，不是合法 UTF-8 会抛错），再退 GBK——顺序很关键，能避开乱码。
    """
    last_err = None
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    raise UnicodeError(f"CSV 编码无法识别（已试 utf-8/gbk/utf-8-sig）：{path}") from last_err


def _read_json_smart(path):
    """JSON：先 read_json；不行再 json.load + json_normalize（兼容对象/嵌套/records 各种形状）。"""
    try:
        return pd.read_json(path)
    except ValueError:
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return pd.json_normalize(data)


def encode_binary(df, col, pos_value):
    """文本型 0/1 标签列转换为数值（如 "yes"/"no" → 1/0）。
    pos_value 是代表"正例/1"的那个值（如 "yes"、"存活"、True）；其余非空值一律编为 0。
    用法：df["survived_01"] = encode_binary(df, "survived", "yes")
    """
    return df[col].map(lambda v: 1 if v == pos_value else (0 if pd.notna(v) else float("nan")))


def _basic_clean(df):
    """基础清洗：列名去首尾空格、丢全空的行与列、去重复行。只整形不改数据值本身。"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")   # 全空的行/列
    return df.drop_duplicates().reset_index(drop=True)


