"""Command-line interface for the canlab pipeline.

Subcommands::

    python -m canlab list                 show the query catalog
    python -m canlab build                ETL the raw CSVs and build the database
    python -m canlab build --samples      build a small demo database from committed samples
    python -m canlab query <name>         run one catalog query (table or CSV output)
    python -m canlab run-all              run the full catalog into docs/results/
    python -m canlab samples              write normalized sample CSVs to data/samples/

``--config`` defaults to ``configs/example.yaml``; ``--db`` overrides the
database path from the config.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from canlab import __version__
from canlab.config import load_config
from canlab.db import build_database, load_from_samples
from canlab.etl import build_regions, load_labour_force, load_population
from canlab.queries import load_catalog, run_query

DEFAULT_CONFIG = "configs/example.yaml"


def _main_common() -> argparse.ArgumentParser:
    """Flags accepted before the subcommand (top-level defaults)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", dest="config", default=DEFAULT_CONFIG,
                        help="path to the YAML config")
    parser.add_argument("--db", dest="db", default=None,
                        help="override the database path")
    return parser


def _sub_common() -> argparse.ArgumentParser:
    """The same flags accepted after the subcommand (win over top-level)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", dest="sub_config", default=None,
                        help="path to the YAML config")
    parser.add_argument("--db", dest="sub_db", default=None,
                        help="override the database path")
    return parser


def _connect(cfg, args) -> sqlite3.Connection:
    db_path = _build_db_path(cfg, args)
    if not db_path.exists():
        raise SystemExit(
            f"database not found: {db_path}\n"
            f"build it first:  python -m canlab build"
        )
    return sqlite3.connect(db_path)


def cmd_list(cfg, args) -> int:
    catalog = load_catalog(cfg.paths.sql_dir)
    width = max(len(q.name) for q in catalog)
    for q in catalog:
        print(f"{q.name:<{width}}  {q.title}")
    print(f"\n{len(catalog)} queries in the catalog")
    return 0


def _build_db_path(cfg, args) -> Path:
    return Path(args.db) if args.db else cfg.paths.db_path


def cmd_build(cfg, args) -> int:
    if args.samples:
        regions, labour, population = load_from_samples(cfg.paths.samples_dir)
        source = "committed samples"
    else:
        raw_dir = cfg.paths.raw_dir
        labour = load_labour_force(raw_dir / f"{cfg.sources.labour_force_product_id}.csv")
        population = load_population(
            raw_dir / f"{cfg.sources.population_product_id}.csv",
            keep_age_groups=cfg.population_age_groups,
        )
        regions = build_regions(labour, population)
        source = "raw Statistics Canada CSVs"
    conn = build_database(_build_db_path(cfg, args), cfg.paths.sql_dir, regions, labour, population)
    conn.close()
    print(
        f"built {_build_db_path(cfg, args)} from {source}: "
        f"{len(labour):,} labour-force rows, {len(population):,} population rows, "
        f"{len(regions)} regions"
    )
    return 0


def cmd_query(cfg, args) -> int:
    conn = _connect(cfg, args)
    catalog = load_catalog(cfg.paths.sql_dir)
    try:
        entry = next(q for q in catalog if q.name == args.name)
    except StopIteration:
        raise SystemExit(f"unknown query: {args.name} (see `python -m canlab list`)") from None
    result = run_query(conn, entry)
    conn.close()
    if args.out == "csv":
        print(result.to_csv(index=False), end="")
    else:
        print(f"{entry.title}\n{entry.question}\n")
        print(result.to_string(index=False))
    return 0


def cmd_run_all(cfg, args) -> int:
    conn = _connect(cfg, args)
    catalog = load_catalog(cfg.paths.sql_dir)
    out_dir = (args.outdir and Path(args.outdir)) or (
        cfg.paths.db_path.parent.parent / "docs" / "results"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for entry in catalog:
        result = run_query(conn, entry)
        out_path = out_dir / f"{entry.name}.csv"
        result.to_csv(out_path, index=False)
        print(f"{entry.name}: {len(result):,} rows -> {out_path}")
    conn.close()
    print(f"\n{len(catalog)} query results written to {out_dir}")
    return 0


def cmd_samples(cfg, args) -> int:
    raw_dir = cfg.paths.raw_dir
    labour = load_labour_force(raw_dir / f"{cfg.sources.labour_force_product_id}.csv")
    population = load_population(
        raw_dir / f"{cfg.sources.population_product_id}.csv",
        keep_age_groups=cfg.population_age_groups,
    )
    regions = build_regions(labour, population)

    # Sample scope: 2020-2025, both-genders total, the headline age groups,
    # all characteristics — small enough to commit, wide enough to demo.
    sample_age_groups = [
        "15 years and over",
        "15 to 64 years",
        "25 to 54 years",
        "15 to 24 years",
    ]
    labour_sample = labour[
        (labour["ref_year"].between(2020, 2025))
        & (labour["gender"] == "Total")
        & (labour["age_group"].isin(sample_age_groups))
    ]
    population_sample = population[
        (population["ref_year"].between(2020, 2025))
        & (population["gender"] == "Total")
    ]

    samples_dir = cfg.paths.samples_dir
    samples_dir.mkdir(parents=True, exist_ok=True)
    regions.to_csv(samples_dir / "regions.csv", index=False)
    labour_sample.to_csv(samples_dir / "labour_force_sample.csv", index=False)
    population_sample.to_csv(samples_dir / "population_sample.csv", index=False)
    print(
        f"samples written to {samples_dir}: regions.csv ({len(regions)} rows), "
        f"labour_force_sample.csv ({len(labour_sample):,} rows), "
        f"population_sample.csv ({len(population_sample):,} rows)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m canlab", description="Statistics Canada labour-market warehouse"
    )
    parser.add_argument("--version", action="version", version=f"canlab {__version__}")
    main_common = _main_common()
    for action in main_common._actions:
        if action.dest != "help":
            parser._add_action(action)
    sub = parser.add_subparsers(dest="command", required=True)

    sub_common = _sub_common()

    p_list = sub.add_parser("list", parents=[sub_common], help="show the query catalog")

    p_build = sub.add_parser("build", parents=[sub_common], help="build the database")
    p_build.add_argument("--samples", action="store_true", help="build from committed samples")

    p_query = sub.add_parser("query", parents=[sub_common], help="run one catalog query")
    p_query.add_argument("name", help="query name (see `list`)")
    p_query.add_argument("--out", choices=("table", "csv"), default="table")

    p_run = sub.add_parser("run-all", parents=[sub_common], help="run the full catalog")
    p_run.add_argument("--outdir", default=None, help="output directory for results")

    p_samples = sub.add_parser("samples", parents=[sub_common], help="write sample CSVs")

    args = parser.parse_args(argv)

    # Merge: explicit subcommand flags win over top-level ones; the top-level
    # default applies only when neither is given.
    config_path = args.sub_config if getattr(args, "sub_config", None) else args.config
    db_override = args.sub_db if getattr(args, "sub_db", None) else args.db
    args.db = db_override
    cfg = load_config(config_path)

    handlers = {
        "list": cmd_list,
        "build": cmd_build,
        "query": cmd_query,
        "run-all": cmd_run_all,
        "samples": cmd_samples,
    }
    return handlers[args.command](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
