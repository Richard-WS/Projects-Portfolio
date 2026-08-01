"""Generate the committed processed dataset from the raw StatsCan dump.

Usage (from the project directory):
    python scripts/make_processed.py [path/to/raw/18100004.csv]

Reads the raw CSV, cleans it, adds year-over-year changes, and writes
data/processed/cpi_canada_food_2015_2026.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from foodinflation.load import add_yoy, clean, load_raw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = PROJECT_ROOT / "data" / "raw" / "18100004.csv"
OUT = PROJECT_ROOT / "data" / "processed" / "cpi_canada_food_2015_2026.csv"


def main() -> None:
    raw_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RAW
    if not raw_path.exists():
        sys.exit(
            f"Raw file not found: {raw_path}\n"
            "Download it first:\n"
            "  curl -L -o data/raw/18100004.zip https://www150.statcan.gc.ca/n1/tbl/csv/18100004-eng.zip\n"
            "  unzip -o data/raw/18100004.zip -d data/raw/"
        )
    raw = load_raw(str(raw_path))
    cleaned = add_yoy(clean(raw))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(cleaned)} rows)")


if __name__ == "__main__":
    main()
