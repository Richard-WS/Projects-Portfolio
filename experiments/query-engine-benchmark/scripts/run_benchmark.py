#!/usr/bin/env python3
"""Run the full benchmark and write docs/benchmark-results.csv.

Steps:
  1. Ensure the dataset exists (generates it on first run).
  2. Verify all engines return identical results — on a 50k-row slice of the
     real dataset so the check is cheap but meaningful.
  3. Run each engine in its own subprocess (clean peak-memory measurement),
     with every query timed best-of-N after a warmup run.
  4. Write the results CSV and print a summary.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

from querybench.config import DEFAULT_QUERIES, load_config
from querybench.queries import ENGINES, assert_equivalent, load_context, run_query

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = PROJECT_ROOT / "docs" / "benchmark-results.csv"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", default=PROJECT_ROOT / "configs" / "example.yaml")
    parser.add_argument("--skip-generate", action="store_true", help="fail if data is missing")
    parser.add_argument("--verify-rows", type=int, default=50_000)
    parser.add_argument("--rows", type=int, default=None, help="override n_orders")
    return parser.parse_args(argv)


def ensure_data(cfg, n_orders) -> tuple[Path, Path]:
    raw = PROJECT_ROOT / "data" / "raw"
    ext = "parquet" if cfg.dataset.format == "parquet" else "csv"
    orders_path = raw / f"orders.{ext}"
    customers_path = raw / f"customers.{ext}"
    if not orders_path.exists() or not customers_path.exists():
        from querybench.data import generate_and_write

        print(f"Dataset missing — generating {n_orders:,} rows...")
        generate_and_write(
            orders_path,
            customers_path,
            n_orders=n_orders,
            n_customers=cfg.dataset.n_customers,
            seed=cfg.dataset.seed,
            fmt=cfg.dataset.format,
        )
    return orders_path, customers_path


def verify_equivalence(orders_path: Path, customers_path: Path, fmt: str, queries, verify_rows: int) -> None:
    """Check every engine returns identical answers on a slice of the data."""
    print(f"Verifying result equivalence on a {verify_rows:,}-row slice...")
    conn = duckdb.connect()
    src = f"read_parquet('{orders_path}')" if fmt == "parquet" else f"read_csv_auto('{orders_path}')"
    src_c = f"read_parquet('{customers_path}')" if fmt == "parquet" else f"read_csv_auto('{customers_path}')"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        conn.execute(f"COPY (SELECT * FROM {src} LIMIT {verify_rows}) TO '{tmp / 'orders.parquet'}' (FORMAT parquet)")
        conn.execute(f"COPY (SELECT * FROM {src_c} LIMIT {verify_rows}) TO '{tmp / 'customers.parquet'}' (FORMAT parquet)")

        contexts = {engine: load_context(engine, tmp / "orders.parquet", tmp / "customers.parquet", "parquet") for engine in ENGINES}
        pairs = [("pandas", "polars"), ("pandas", "duckdb"), ("polars", "duckdb")]
        for name in queries:
            results = {engine: run_query(name, engine, contexts[engine]) for engine in ENGINES}
            for a, b in pairs:
                assert_equivalent(results[a], results[b], label=f"{name} ({a} vs {b})")
    print("  OK — all engines agree on every query.")


def run_engine(engine: str, orders_path: Path, customers_path: Path, cfg, n_orders) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "querybench.runner",
        "--engine", engine,
        "--orders", str(orders_path),
        "--customers", str(customers_path),
        "--format", cfg.dataset.format,
        "--queries", ",".join(cfg.queries),
        "--runs", str(cfg.runs),
        "--warmup", str(cfg.warmup),
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    report = json.loads(proc.stdout)
    report["n_orders"] = n_orders
    return report


def write_results(reports: list[dict], queries) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = ["engine", "load_ms"] + [f"{q}_ms" for q in queries] + ["peak_rss_mb"]
    lines = [",".join(header)]
    for r in reports:
        row = [r["engine"], f"{r['load_ms']:.1f}"]
        row += [f"{r['queries_ms'][q]:.1f}" for q in queries]
        row.append(f"{r['peak_rss_mb']:.1f}")
        lines.append(",".join(row))
    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nResults written to {RESULTS_PATH}")


def print_summary(reports: list[dict], queries) -> None:
    print("\n=== Summary ===\n")
    widths = {q: max(len(q), 10) for q in queries}
    header = f"{'engine':<10}{'load ms':>10}{'peak MB':>12}" + "".join(q.ljust(widths[q] + 2) for q in queries)
    print(header)
    print("-" * len(header))
    for r in reports:
        cells = f"{r['load_ms']:>10.1f}{r['peak_rss_mb']:>12.1f}" + "".join(
            f"{r['queries_ms'][q]:>7.1f} ms".ljust(widths[q] + 2) for q in queries
        )
        print(f"{r['engine']:<10}{cells}")


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    n_orders = args.rows or cfg.dataset.n_orders

    orders_path, customers_path = ensure_data(cfg, n_orders)
    verify_equivalence(orders_path, customers_path, cfg.dataset.format, cfg.queries, args.verify_rows)

    reports = []
    for engine in ENGINES:
        print(f"Benchmarking {engine}...")
        reports.append(run_engine(engine, orders_path, customers_path, cfg, n_orders))

    write_results(reports, cfg.queries)
    print_summary(reports, cfg.queries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
