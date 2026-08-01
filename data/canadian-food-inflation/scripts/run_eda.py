"""EDA companion to notebooks/01_food_inflation_eda.ipynb.

Runs the same analysis as the notebook and prints the outputs, so the
findings are reproducible from the command line without a Jupyter kernel.

Usage (from the project directory):
    python scripts/run_eda.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from foodinflation.analysis import months_above, ols

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_wide() -> pd.DataFrame:
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "cpi_canada_food_2015_2026.csv", parse_dates=["date"])
    return df.pivot(index="date", columns="product", values="value").sort_index()


def main() -> None:
    wide = load_wide()
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "cpi_canada_food_2015_2026.csv", parse_dates=["date"])

    print("=" * 60)
    print("CANADIAN GROCERY INFLATION, 2015-2026")
    print("=" * 60)

    # Data quality
    print("\n[1] Data quality")
    print(f"    Missing values: {df.isna().sum().sum()}")
    print(f"    Months per product: {df.groupby('product')['date'].count().to_dict()}")

    # Cumulative growth
    base = wide.loc["2015-01-01"]
    latest = wide.loc[wide.index[-1]]
    growth = (latest / base - 1) * 100
    print("\n[2] Cumulative index growth, Jan 2015 -> latest (%):")
    for prod, g in growth.sort_values(ascending=False).items():
        print(f"    {prod:32s} {g:6.1f}")

    # YoY
    yoy = wide.pct_change(12) * 100
    print("\n[3] Latest YoY inflation (%):")
    for prod, v in yoy.tail(1).T.sort_values(by=yoy.index[-1], ascending=False).iloc[:, 0].items():
        print(f"    {prod:32s} {v:6.1f}")

    # Food vs all-items
    food_yoy = yoy["Food purchased from stores"]
    all_yoy = yoy["All-items"]
    above = months_above(food_yoy, all_yoy)
    total = food_yoy.notna().sum()
    print("\n[4] Food-store vs all-items inflation")
    print(f"    Months food > all-items: {len(above)}/{total} ({len(above)/total*100:.0f}%)")
    print(f"    Avg food-store inflation: {food_yoy.mean():.2f}%")
    print(f"    Avg all-items inflation:  {all_yoy.mean():.2f}%")

    # Gap
    gap = food_yoy - all_yoy
    print("\n[5] Widest food vs all-items gap")
    print(f"    {gap.idxmax():%Y-%m}: {gap.max():.1f} percentage points")
    print(f"    Latest gap: {gap.iloc[-1]:.1f} pp")

    # Regression
    mask = food_yoy.notna() & all_yoy.notna()
    slope, intercept, r2 = ols(all_yoy[mask].values, food_yoy[mask].values)
    print("\n[6] Regression: food_yoy = a * all_yoy + b")
    print(f"    slope={slope:.2f}  intercept={intercept:.2f}  r2={r2:.3f}  n={int(mask.sum())}")


if __name__ == "__main__":
    main()
