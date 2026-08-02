#!/usr/bin/env python3
"""Generate the benchmark dataset from configs/example.yaml.

Writes the full orders/customers tables into data/raw/ (gitignored) and a
2000-row sample of each into data/samples/ (committed, provenance: generated
from seed 42).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from querybench.config import load_config
from querybench.data import generate_and_write

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", default=PROJECT_ROOT / "configs" / "example.yaml")
    parser.add_argument("--rows", type=int, default=None, help="override n_orders")
    parser.add_argument("--format", choices=("parquet", "csv"), default=None)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    n_orders = args.rows or cfg.dataset.n_orders
    fmt = args.format or cfg.dataset.format

    raw = PROJECT_ROOT / "data" / "raw"
    samples = PROJECT_ROOT / "data" / "samples"
    ext = "parquet" if fmt == "parquet" else "csv"
    orders_path = raw / f"orders.{ext}"
    customers_path = raw / f"customers.{ext}"

    print(f"Generating {n_orders:,} orders x {cfg.dataset.n_customers:,} customers ({fmt})...")
    generate_and_write(
        orders_path,
        customers_path,
        sample_orders_path=samples / "orders_sample.csv",
        sample_customers_path=samples / "customers_sample.csv",
        n_orders=n_orders,
        n_customers=cfg.dataset.n_customers,
        seed=cfg.dataset.seed,
        fmt=fmt,
    )
    print(f"Wrote {orders_path}")
    print(f"Wrote {customers_path}")
    print(f"Samples in {samples}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
