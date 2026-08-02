"""Schema and database-building tests: structure, constraints, integrity."""
from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from canlab.db import build_database

from conftest import make_labour_csv, make_population_csv


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def _views(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()
    return {r[0] for r in rows}


def test_build_creates_schema_and_views(db):
    assert _tables(db) == {"regions", "labour_force", "population"}
    assert {"v_unemployment_rate", "v_employment", "v_employment_per_capita"} <= _views(db)


def test_row_counts_match_frames(db, frames):
    regions, labour, population = frames
    counts = {
        "regions": db.execute("SELECT COUNT(*) FROM regions").fetchone()[0],
        "labour_force": db.execute("SELECT COUNT(*) FROM labour_force").fetchone()[0],
        "population": db.execute("SELECT COUNT(*) FROM population").fetchone()[0],
    }
    assert counts == {
        "regions": len(regions),
        "labour_force": len(labour),
        "population": len(population),
    }


def test_primary_key_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO regions VALUES ('CA', 'Canada', 'country')"
        )


def test_foreign_key_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO labour_force VALUES "
            "(2000, 'ZZ', 'Total', '15 years and over', 'Employment', 1.0, "
            "'Persons in thousands')"
        )


def test_check_constraints_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO regions VALUES ('XX', 'Nowhere', 'kingdom')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO labour_force VALUES "
            "(2000, 'CA', 'Total', '15 years and over', 'Employment', 1.0, 'Bananas')"
        )


def test_rebuild_replaces_stale_db(tmp_path, sql_dir):
    from canlab.config import DEFAULT_POPULATION_AGE_GROUPS
    from canlab.etl import build_regions, load_labour_force, load_population

    make_labour_csv(tmp_path / "14100327.csv")
    make_population_csv(tmp_path / "17100005.csv")
    labour = load_labour_force(tmp_path / "14100327.csv")
    population = load_population(
        tmp_path / "17100005.csv", keep_age_groups=DEFAULT_POPULATION_AGE_GROUPS
    )
    regions = build_regions(labour, population)

    db_path = tmp_path / "w.db"
    db_path.write_bytes(b"stale garbage")  # simulate an old/incompatible file
    conn = build_database(db_path, sql_dir, regions, labour, population)
    conn.close()
    # The stale file was replaced by a valid database.
    with sqlite3.connect(db_path) as check:
        assert check.execute("SELECT COUNT(*) FROM regions").fetchone()[0] == 4


def test_views_are_queryable(db):
    for view in ("v_unemployment_rate", "v_employment_per_capita", "v_part_time_share"):
        df = pd.read_sql_query(f"SELECT * FROM {view}", db)
        assert len(df) > 0
