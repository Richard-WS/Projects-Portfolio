"""Chart the committed benchmark results into the project's preview image.

Reads docs/benchmark-results.csv (the real 5M-order run: per-engine query
times and peak memory, best-of-N medians) and writes docs/screenshot.png.
Run from the project directory:

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
CSV_PATH = ROOT / "docs" / "benchmark-results.csv"
OUT = ROOT / "docs" / "screenshot.png"

QUERY_COLS = ["load_ms", "q1_filter_sum_ms", "q2_groupby_ms", "q3_multi_groupby_ms",
              "q4_join_ms", "q5_topn_ms", "q6_monthly_revenue_ms"]
ENGINES = ["pandas", "polars", "duckdb"]
COLORS = {"pandas": "#d62728", "polars": "#2ca02c", "duckdb": "#1f77b4"}


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        rows = {r["engine"]: r for r in csv.DictReader(fh)}

    fig, (ax_time, ax_mem) = plt.subplots(1, 2, figsize=(11, 4.6))

    # Per-query times, log scale (fastest ~9 ms, slowest ~970 ms).
    n = len(QUERY_COLS)
    width = 0.26
    for i, engine in enumerate(ENGINES):
        times = [float(rows[engine][col]) for col in QUERY_COLS]
        x = [j + (i - 1) * width for j in range(n)]
        ax_time.bar(x, times, width, label=engine, color=COLORS[engine])
    ax_time.set_yscale("log")
    ax_time.set_xticks(range(n))
    ax_time.set_xticklabels(["load", "q1 filter\n+sum", "q2 groupby", "q3 multi\ngroupby",
                             "q4 join", "q5 top-N", "q6 monthly\nrevenue"],
                            rotation=0, fontsize=8)
    ax_time.set_ylabel("Time (ms, log scale)")
    ax_time.set_title("Query time by engine — 5M orders", fontsize=10)
    ax_time.grid(axis="y", alpha=0.3)
    ax_time.legend(fontsize=9)

    # Peak memory per engine.
    mem = [float(rows[e]["peak_rss_mb"]) for e in ENGINES]
    bars = ax_mem.bar(ENGINES, mem, color=[COLORS[e] for e in ENGINES])
    ax_mem.bar_label(bars, fmt="%.0f", fontsize=9)
    ax_mem.set_ylabel("Peak RSS (MB)")
    ax_mem.set_title("Peak memory by engine", fontsize=10)
    ax_mem.grid(axis="y", alpha=0.3)

    fig.suptitle("Query engine benchmark — pandas vs Polars vs DuckDB", fontsize=12, y=1.0)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
