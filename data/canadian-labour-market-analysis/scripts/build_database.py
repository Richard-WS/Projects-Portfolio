#!/usr/bin/env python3
"""End-to-end build: ETL the raw CSVs, build the database, run the catalog.

    python scripts/build_database.py                 # full pipeline
    python scripts/build_database.py --samples       # demo DB from committed samples

Outputs:
    data/canlab.db                    the SQLite warehouse (gitignored)
    docs/results/<query>.csv          one CSV per catalog query (committed)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from canlab.cli import main  # noqa: E402  (sys.path set above)

if __name__ == "__main__":
    # The CLI resolves config paths relative to configs/, so run from the root.
    sys.exit(main(["--config", str(ROOT / "configs" / "example.yaml"), *sys.argv[1:]]))
