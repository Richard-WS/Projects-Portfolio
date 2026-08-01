"""Generate the charts embedded in the dashboard report.

Produces PNG/SVG figures into docs/charts/ using matplotlib with a
consistent style. Run from the project directory:
    python scripts/make_charts.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from foodinflation.analysis import months_above, ols

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = PROJECT_ROOT / "docs" / "charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
    }
)


def load_wide() -> pd.DataFrame:
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "cpi_canada_food_2015_2026.csv", parse_dates=["date"])
    return df.pivot(index="date", columns="product", values="value").sort_index()


def chart_index_levels(wide: pd.DataFrame) -> None:
    """Index levels (2002=100) for the four headline series."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for prod in ["All-items", "Food purchased from stores", "Food purchased from restaurants", "Fresh vegetables"]:
        ax.plot(wide.index, wide[prod], label=prod, lw=1.6)
    ax.set_title("Consumer Price Index, Canada (2002 = 100)")
    ax.set_xlabel("")
    ax.set_ylabel("Index level")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "index_levels.png", dpi=150)
    plt.close(fig)


def chart_yoy(wide: pd.DataFrame) -> None:
    """Year-over-year inflation, food store vs all-items."""
    yoy = wide.pct_change(12) * 100
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(yoy.index, yoy["All-items"], label="All-items", lw=1.8, color="#1f77b4")
    ax.plot(yoy.index, yoy["Food purchased from stores"], label="Food purchased from stores", lw=1.8, color="#d62728")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title("Year-over-year inflation, Canada")
    ax.set_ylabel("Percent change vs same month last year")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "yoy_food_vs_all.png", dpi=150)
    plt.close(fig)


def chart_food_gap(wide: pd.DataFrame) -> None:
    """Food-store minus all-items inflation gap."""
    yoy = wide.pct_change(12) * 100
    gap = yoy["Food purchased from stores"] - yoy["All-items"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(gap.index, gap, color=["#d62728" if v > 0 else "#1f77b4" for v in gap], width=28)
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title("Grocery inflation minus overall inflation (percentage points)")
    ax.set_ylabel("Percentage points")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "food_gap.png", dpi=150)
    plt.close(fig)


def main() -> None:
    wide = load_wide()
    chart_index_levels(wide)
    chart_yoy(wide)
    chart_food_gap(wide)
    print(f"Charts written to {CHART_DIR}")


if __name__ == "__main__":
    main()
