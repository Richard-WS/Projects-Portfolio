#!/usr/bin/env python3
"""Build the self-contained viewer.html from data/positions.csv.

Usage:
    python scripts/build_viewer.py -c configs/example.yaml
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solarpositions.build import csv_to_json, render_html  # noqa: E402
from solarpositions.config import load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", default="configs/example.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    data = csv_to_json(cfg.output_csv, precision=cfg.precision)
    render_html(cfg.template, data, cfg.output_html, precision=cfg.precision)

    n_frames = len(data["dates"])
    n_bodies = len(data["planets"])
    size_kb = Path(cfg.output_html).stat().st_size / 1024
    print(f"frames:  {n_frames} ({data['dates'][0]} .. {data['dates'][-1]})")
    print(f"bodies:  {', '.join(data['planets'])}")
    print(f"size:    {size_kb:.0f} KB")
    print(f"written: {cfg.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
