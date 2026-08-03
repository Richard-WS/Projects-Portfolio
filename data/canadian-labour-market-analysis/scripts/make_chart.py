"""Chart the committed query results into the project's preview image.

Reads docs/results/*.csv (produced by the project's own SQL catalog) and
writes docs/screenshot.png — the image embedded in the README and the root
portfolio page. Run from the project directory:

    python scripts/make_chart.py

Requires matplotlib only.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results"
OUT = ROOT / "docs" / "screenshot.png"


def read_csv(name: str) -> list[dict]:
    with (RESULTS / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    gap = read_csv("q08_nb_vs_canada_unemployment.csv")
    national = read_csv("q09_unemployment_moving_average.csv")

    fig, (ax_gap, ax_nat) = plt.subplots(1, 2, figsize=(10.5, 4.6))

    # NB vs Canada by decade — the headline story.
    decades = [int(r["decade"]) for r in gap]
    ax_gap.plot(decades, [float(r["nb_avg_pct"]) for r in gap], marker="o", color="#1f77b4",
                label="New Brunswick")
    ax_gap.plot(decades, [float(r["canada_avg_pct"]) for r in gap], marker="s", color="#ff7f0e",
                label="Canada")
    ax_gap.annotate("4.2 pp gap", xy=(1970, 11.9), xytext=(1972, 13.4),
                    arrowprops=dict(arrowstyle="->", color="#555555"), fontsize=9)
    ax_gap.annotate("1.1 pp gap", xy=(2020, 7.93), xytext=(2006, 5.6),
                    arrowprops=dict(arrowstyle="->", color="#555555"), fontsize=9)
    ax_gap.set_title("Unemployment by decade, NB vs Canada", fontsize=10)
    ax_gap.set_xlabel("Decade")
    ax_gap.set_ylabel("Unemployment rate (%)")
    ax_gap.set_xticks(decades)
    ax_gap.grid(alpha=0.3)
    ax_gap.legend(fontsize=9, loc="upper right")

    # National annual series with a 5-year moving average.
    years = [int(r["ref_year"]) for r in national]
    ax_nat.plot(years, [float(r["unemployment_pct"]) for r in national],
                color="#1f77b4", lw=1.2, label="Canada, annual")
    ax_nat.plot(years, [float(r["moving_average_5yr"]) for r in national],
                color="#d62728", lw=2, label="5-year moving average")
    ax_nat.set_title("Canada unemployment rate, 1976–2026", fontsize=10)
    ax_nat.set_xlabel("Year")
    ax_nat.set_ylabel("Unemployment rate (%)")
    ax_nat.grid(alpha=0.3)
    ax_nat.legend(fontsize=9, loc="upper right")

    fig.suptitle("Canadian labour market — SQL warehouse results", fontsize=12, y=1.0)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
