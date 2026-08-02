#!/usr/bin/env python3
"""Generate data/positions.csv: monthly heliocentric ecliptic (x, y) in AU.

Usage:
    python scripts/generate_positions.py -c configs/example.yaml
    python scripts/generate_positions.py -c configs/example.yaml --ephemeris jpl --include-pluto

The default ephemeris is Astropy's built-in (ERFA) model — fully offline.
``--ephemeris jpl`` downloads JPL DE440s once (cached via ASTROPY_CACHE) and
``--include-pluto`` adds the dwarf planet (JPL only; the built-in model has
no Pluto).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solarpositions.config import load_config  # noqa: E402
from solarpositions.positions import generate_rows, write_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", default="configs/example.yaml")
    parser.add_argument(
        "--ephemeris", default=None, help="override config ephemeris (e.g. jpl)"
    )
    parser.add_argument(
        "--include-pluto", action="store_true", help="add Pluto (needs JPL ephemeris)"
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.ephemeris:
        cfg.ephemeris = args.ephemeris
    bodies = list(cfg.bodies)
    if args.include_pluto:
        if cfg.ephemeris == "builtin":
            print("error: Pluto is not in the built-in ephemeris; use --ephemeris jpl", file=sys.stderr)
            return 2
        bodies.append("pluto")

    rows = generate_rows(
        cfg.start,
        cfg.end,
        bodies,
        ephemeris=cfg.ephemeris,
        step_months=cfg.step_months,
    )
    write_csv(rows, cfg.output_csv, precision=cfg.precision)

    dates = sorted({r["date"] for r in rows})
    max_au = max(max(abs(r["x_au"]), abs(r["y_au"])) for r in rows)
    print(f"ephemeris: {cfg.ephemeris}")
    print(f"frames:    {len(dates)} months ({dates[0]} .. {dates[-1]})")
    print(f"bodies:    {', '.join(bodies)}")
    print(f"rows:      {len(rows)}")
    print(f"max |x|,|y|: {max_au:.3f} AU")
    print(f"written:   {cfg.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
