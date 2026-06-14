import numpy as np
import pandas as pd

from .fonts import setup_cjk_font
from .visualize import visualize


def main():
    print("使用字体:", setup_cjk_font())
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "分组": ["自选"] * 60 + ["调剂"] * 60,
        "首年GPA": np.concatenate([rng.normal(3.2, 0.40, 60),
                                   rng.normal(2.7, 0.45, 60)]).clip(0, 4),
    })
    insight = "调剂学生首年GPA显著更低"  # 真实调用里由 Claude 的 EDA 步产出

    # 案例1 · 标准版（low）：不传 occasion → STANDARD_PALETTE + 受众地板（均值条 + 直接标注 + 结论）
    r1 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="low", emphasize="调剂", save_to="c1.html")
    print("案例1 · 标准版/low :", r1)

    # 案例2 · 标准版（high）：箱线图，地板=0（裸图可读）
    r2 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="high", emphasize="调剂", save_to="c2.html")
    print("案例2 · 标准版/high:", r2)

    # 案例3 · 4.1 精修（low + keynote）：标准版之上套演讲场合配色；注释仍不低于受众地板
    r3 = visualize(df, "分组", "首年GPA",
                   question="自选 vs 调剂，首年GPA有差异吗？", insight=insight,
                   audience="low", occasion="keynote", emphasize="调剂", save_to="c3.html")
    print("案例3 · 4.1精修/low+keynote:", r3)


if __name__ == "__main__":
    main()
