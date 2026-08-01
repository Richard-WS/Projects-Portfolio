"""Assemble docs/dashboard.html from the generated charts.

Reads the PNG charts and inlines them as base64 data URIs so the report is
a single self-contained file. Run from the project directory:
    python scripts/make_dashboard.py
"""

from __future__ import annotations

import base64
import string
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = PROJECT_ROOT / "docs" / "charts"

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canadian Grocery Inflation 2015-2026</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         max-width: 900px; margin: 0 auto; padding: 24px; color: #222; line-height: 1.5; }
  h1 { font-size: 1.8em; margin-bottom: 4px; }
  .sub { color: #666; margin-top: 0; }
  h2 { font-size: 1.3em; margin-top: 40px; border-bottom: 2px solid #eee; padding-bottom: 6px; }
  figure { margin: 20px 0; }
  figcaption { color: #666; font-size: 0.9em; margin-top: 6px; }
  img { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 6px; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; }
  th, td { border: 1px solid #ddd; padding: 8px 10px; text-align: left; }
  th { background: #f5f5f5; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .callout { background: #f0f7ff; border-left: 4px solid #1f77b4; padding: 12px 16px; border-radius: 0 6px 6px 0; }
  footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #eee; color: #888; font-size: 0.85em; }
</style>
</head>
<body>
<h1>Canadian Grocery Inflation, 2015-2026</h1>
<p class="sub">Analysis of grocery prices vs overall inflation &middot; Statistics Canada Table 18-10-0004-01 (CPI, monthly)</p>

<h2>Summary</h2>
<div class="callout">
  <strong>Food purchased from stores is up 43.4% since January 2015</strong> &mdash; well ahead of the 36.0% rise in the all-items
  CPI. Grocery inflation exceeded overall inflation in <strong>77 of 126 months (61%)</strong>. The gap peaked at
  <strong>6.3 percentage points</strong> in June 2023 and has since narrowed to about 1 percentage point.
</div>

<h2>1. The overall picture</h2>
<figure>
  <img src="$chart_index" alt="Consumer Price Index levels, Canada, 2002=100">
  <figcaption>Index levels (2002 = 100). All series share the same base year and are directly comparable.</figcaption>
</figure>
<table>
  <tr><th>Series</th><th class="num">Jan 2015</th><th class="num">Jun 2026</th><th class="num">Total change</th><th class="num">Annualized</th></tr>
  <tr><td>Fresh vegetables</td><td class="num">129.6</td><td class="num">200.9</td><td class="num">+55.0%</td><td class="num">+4.1%/yr</td></tr>
  <tr><td>Food purchased from restaurants</td><td class="num">128.2</td><td class="num">192.7</td><td class="num">+50.3%</td><td class="num">+3.8%/yr</td></tr>
  <tr><td>Food purchased from stores</td><td class="num">126.6</td><td class="num">181.5</td><td class="num">+43.4%</td><td class="num">+3.4%/yr</td></tr>
  <tr><td>All-items</td><td class="num">124.3</td><td class="num">169.1</td><td class="num">+36.0%</td><td class="num">+2.9%/yr</td></tr>
  <tr><td>Fresh fruit</td><td class="num">135.9</td><td class="num">177.9</td><td class="num">+30.9%</td><td class="num">+2.5%/yr</td></tr>
</table>

<h2>2. Year-over-year inflation</h2>
<figure>
  <img src="$chart_yoy" alt="Year-over-year inflation, food store vs all-items">
  <figcaption>Year-over-year percent change. Grocery inflation ran above the all-items rate for most of the decade, spiking in 2021-2023.</figcaption>
</figure>

<h2>3. The grocery gap</h2>
<figure>
  <img src="$chart_gap" alt="Grocery inflation minus overall inflation">
  <figcaption>Grocery-store inflation minus all-items inflation, in percentage points. Positive bars mean groceries outran the overall basket.</figcaption>
</figure>
<p>Regression (ordinary least squares, monthly YoY, Jan 2016 - Jun 2026, n=126):</p>
<table>
  <tr><th>Coefficient</th><th class="num">Estimate</th><th class="num">r&sup2;</th></tr>
  <tr><td>All-items inflation (slope)</td><td class="num">1.44</td><td class="num">0.54</td></tr>
  <tr><td>Intercept</td><td class="num">-0.52</td><td class="num"></td></tr>
</table>
<div class="callout">
  For every 1 percentage point the all-items CPI rose, grocery-store inflation rose about <strong>1.44 percentage points</strong>.
  Groceries are structurally more inflationary than the overall basket.
</div>

<h2>4. Where we are now</h2>
<p>As of June 2026, food purchased from stores was inflating at <strong>3.9%</strong> year-over-year, vs <strong>2.8%</strong> for the
all-items CPI &mdash; a gap of about 1 percentage point, down from its 6.3-point peak in June 2023.</p>

<h2>Data &amp; method</h2>
<ul>
  <li><strong>Source:</strong> Statistics Canada Table 18-10-0004-01, Consumer Price Index, monthly, not seasonally adjusted.</li>
  <li><strong>Scope:</strong> Canada, selected product groups, index base 2002=100, January 2015 &ndash; June 2026.</li>
  <li><strong>Cleaning:</strong> <code>src/foodinflation/load.py</code> filters to the scope; <code>scripts/make_processed.py</code> regenerates the dataset.</li>
  <li><strong>Analysis:</strong> <code>src/foodinflation/analysis.py</code> (YoY, OLS, gap) &mdash; all unit-tested.</li>
  <li><strong>Reproduce:</strong> <code>scripts/make_processed.py</code> &rarr; <code>scripts/run_eda.py</code> &rarr; <code>scripts/make_charts.py</code> &rarr; this file.</li>
</ul>

<footer>Richard Seyeau &middot; Portfolio project &middot; Data analysis</footer>
</body>
</html>
"""


def _data_uri(name: str) -> str:
    path = CHART_DIR / name
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main() -> None:
    html = string.Template(TEMPLATE).substitute(
        chart_index=_data_uri("index_levels.png"),
        chart_yoy=_data_uri("yoy_food_vs_all.png"),
        chart_gap=_data_uri("food_gap.png"),
    )
    out = PROJECT_ROOT / "docs" / "dashboard.html"
    out.write_text(html)
    print(f"Wrote {out} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
