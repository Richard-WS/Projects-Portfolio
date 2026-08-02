"""Build and load the SQLite warehouse.

The pipeline is deliberately script-driven: a fresh database is created by
executing the schema and view files verbatim (so the committed SQL is the
single source of truth for the warehouse structure), then populated from the
normalized frames produced by :mod:`canlab.etl`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

_SCHEMA_FILE = "01_schema.sql"
_VIEWS_FILE = "02_views.sql"
_INSERT_BATCH = 50_000


def _read_sql(path: Path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _insert_frames(conn: sqlite3.Connection, df: pd.DataFrame, table: str) -> None:
    """Insert a DataFrame in batches, one transaction per batch."""
    columns = list(df.columns)
    placeholders = ",".join("?" * len(columns))
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
    rows = list(df.itertuples(index=False, name=None))
    for start in range(0, len(rows), _INSERT_BATCH):
        conn.executemany(sql, rows[start : start + _INSERT_BATCH])
        conn.commit()


def build_database(
    db_path: str | Path,
    sql_dir: str | Path,
    regions: pd.DataFrame,
    labour: pd.DataFrame,
    population: pd.DataFrame,
) -> sqlite3.Connection:
    """Create the schema, load all three tables, create the views."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(_read_sql(Path(sql_dir) / _SCHEMA_FILE))
        _insert_frames(conn, regions, "regions")
        _insert_frames(conn, labour, "labour_force")
        _insert_frames(conn, population, "population")
        conn.executescript(_read_sql(Path(sql_dir) / _VIEWS_FILE))
        conn.commit()
    except Exception:
        conn.close()
        db_path.unlink(missing_ok=True)
        raise
    return conn


def load_from_samples(samples_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the committed normalized sample CSVs (demo path, no download)."""
    samples_dir = Path(samples_dir)
    return (
        pd.read_csv(samples_dir / "regions.csv"),
        pd.read_csv(samples_dir / "labour_force_sample.csv"),
        pd.read_csv(samples_dir / "population_sample.csv"),
    )
