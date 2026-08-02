"""Per-engine benchmark runner, meant to be run as a subprocess.

Each engine gets its own process so peak memory (``ru_maxrss``) is measured
cleanly — no other engine's data is loaded in the same run. Prints one
JSON document to stdout::

    {"engine": "...", "load_ms": ..., "queries_ms": {...}, "peak_rss_mb": ...}
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from querybench.bench import peak_rss_mb, time_query
from querybench.queries import ENGINES, load_context, run_query


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=ENGINES, required=True)
    parser.add_argument("--orders", required=True, help="path to orders file")
    parser.add_argument("--customers", required=True, help="path to customers file")
    parser.add_argument("--format", choices=("parquet", "csv"), default="parquet")
    parser.add_argument("--queries", required=True, help="comma-separated query names")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    queries = [q.strip() for q in args.queries.split(",") if q.strip()]

    start = time.perf_counter_ns()
    ctx = load_context(args.engine, args.orders, args.customers, args.format)
    load_ms = (time.perf_counter_ns() - start) / 1e6

    query_ms = {}
    for name in queries:
        query_ms[name] = time_query(
            lambda name=name: run_query(name, args.engine, ctx),
            warmup=args.warmup,
            runs=args.runs,
        )

    report = {
        "engine": args.engine,
        "load_ms": round(load_ms, 1),
        "queries_ms": {name: round(ms, 1) for name, ms in query_ms.items()},
        "peak_rss_mb": round(peak_rss_mb(), 1),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
