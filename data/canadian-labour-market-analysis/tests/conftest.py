"""Shared fixtures for the canlab test suite.

The fixtures synthesize tiny Statistics Canada-format CSVs — UTF-8 BOM,
fully quoted fields, empty VALUE for suppressed cells — with values chosen
so every catalog query returns deterministic, hand-computable results.
Rates are region constants (5.0 / 8.0 / 4.0 unemployment), employment grows
linearly per region, and population follows its own linear series, so the
golden-value assertions in the tests are exact.
"""
from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"

YEARS = [1976, 2000, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2019, 2020, 2021, 2025]
LABOUR_REGIONS = ["Canada", "New Brunswick", "Ontario"]
POP_REGIONS = LABOUR_REGIONS + ["Yukon"]
LABOUR_GENDERS = ["Total - Gender", "Men+", "Women+"]
POP_GENDERS = ["Total - gender", "Men+", "Women+"]
LABOUR_AGES = ["15 years and over", "15 to 64 years", "25 to 54 years", "15 to 24 years"]
# Population raw rows include groups the ETL must filter out.
POP_AGES = [
    "All ages", "15 to 24 years", "15 to 64 years", "15 years and over",
    "25 to 44 years", "25 to 54 years", "0 to 14 years", "Average age",
]

RATES = {
    "Canada": {
        "Unemployment rate": 5.0, "Employment rate": 60.0,
        "Participation rate": 65.0, "Proportion employed part-time": 12.0,
    },
    "New Brunswick": {
        "Unemployment rate": 8.0, "Employment rate": 55.0,
        "Participation rate": 60.0, "Proportion employed part-time": 18.0,
    },
    "Ontario": {
        "Unemployment rate": 4.0, "Employment rate": 62.0,
        "Participation rate": 66.0, "Proportion employed part-time": 14.0,
    },
}
EMPLOYMENT_BASE = {"Canada": 900.0, "New Brunswick": 40.0, "Ontario": 600.0}
EMPLOYMENT_STEP = {"Canada": 0.5, "New Brunswick": 0.1, "Ontario": 0.4}
POP_BASE = {"Canada": 20_000_000.0, "New Brunswick": 400_000.0, "Ontario": 12_000_000.0, "Yukon": 30_000.0}
POP_STEP = {"Canada": 50_000.0, "New Brunswick": 1_000.0, "Ontario": 30_000.0, "Yukon": 100.0}

AGE_FACTOR = {
    "15 years and over": 1.0, "15 to 64 years": 0.95,
    "25 to 54 years": 0.75, "15 to 24 years": 0.10,
}
POP_FACTOR = {
    "All ages": 1.5, "15 to 24 years": 0.15, "15 to 64 years": 1.0,
    "15 years and over": 1.35, "25 to 44 years": 0.6, "25 to 54 years": 0.75,
}


def _employment_total(year: int, region: str) -> float:
    return EMPLOYMENT_BASE[region] + (year - 1976) * EMPLOYMENT_STEP[region]


def _pop_15_64(year: int, region: str) -> float:
    return POP_BASE[region] + (year - 1976) * POP_STEP[region]


def _write_stats_can_csv(path: Path, header: list[str], rows: list[list]) -> None:
    """Write a StatsCan-style CSV: UTF-8 BOM, all fields quoted."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow(header)
    writer.writerows(rows)
    path.write_text("\ufeff" + buf.getvalue(), encoding="utf-8")


def make_labour_csv(path: Path) -> None:
    header = [
        "REF_DATE", "GEO", "DGUID", "Labour force characteristics", "Gender",
        "Age group", "UOM", "UOM_ID", "SCALAR_FACTOR", "SCALAR_ID", "VECTOR",
        "COORDINATE", "VALUE", "STATUS", "SYMBOL", "TERMINATED", "DECIMALS",
    ]
    rows: list[list] = []
    for year in YEARS:
        for geo in LABOUR_REGIONS:
            for gender in LABOUR_GENDERS:
                for age in LABOUR_AGES:
                    for char in ["Employment", *RATES[geo]]:
                        if char == "Employment":
                            base = _employment_total(year, geo)
                            value = base * AGE_FACTOR[age]
                            if gender == "Men+":
                                value *= 0.55
                            elif gender == "Women+":
                                value *= 0.45
                            uom = "Persons in thousands"
                        else:
                            value = RATES[geo][char]
                            if char == "Unemployment rate" and age == "15 to 24 years":
                                value += 5.0
                            if gender == "Men+":
                                value *= 0.55
                            elif gender == "Women+":
                                value *= 0.45
                            uom = "Percent"
                        rows.append(
                            [year, geo, f"d-{geo[:2]}", char, gender, age,
                             uom, "249", "units", "0", "v1", "1", f"{value:.6g}",
                             "", "", "", "0"]
                        )
    # A suppressed cell: VALUE empty, must be dropped by the ETL.
    rows.append(
        [1976, "Ontario", "d-On", "Participation rate", "Men+", "15 to 24 years",
         "Percent", "249", "units", "0", "v1", "1", "", "", "", "", "0"]
    )
    _write_stats_can_csv(path, header, rows)


def make_population_csv(path: Path) -> None:
    header = [
        "REF_DATE", "GEO", "DGUID", "Gender", "Age group", "UOM", "UOM_ID",
        "SCALAR_FACTOR", "SCALAR_ID", "VECTOR", "COORDINATE", "VALUE", "STATUS",
        "SYMBOL", "TERMINATED", "DECIMALS",
    ]
    rows: list[list] = []
    for year in YEARS:
        for geo in POP_REGIONS:
            for gender in POP_GENDERS:
                for age in POP_AGES:
                    base = _pop_15_64(year, geo)
                    factor = POP_FACTOR.get(age, 1.0)
                    value = base * factor
                    if gender == "Men+":
                        value *= 0.5
                    elif gender == "Women+":
                        value *= 0.5
                    rows.append(
                        [year, geo, f"d-{geo[:2]}", gender, age, "Persons",
                         "249", "units", "0", "v1", "1", f"{value:.6g}",
                         "", "", "", "0"]
                    )
    _write_stats_can_csv(path, header, rows)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    make_labour_csv(tmp_path / "14100327.csv")
    make_population_csv(tmp_path / "17100005.csv")
    return tmp_path


@pytest.fixture
def sql_dir() -> Path:
    return SQL_DIR


@pytest.fixture
def catalog():
    from canlab.queries import load_catalog

    return load_catalog(SQL_DIR)


@pytest.fixture
def frames(raw_dir: Path):
    """ETL output on the fixture CSVs."""
    from canlab.config import DEFAULT_POPULATION_AGE_GROUPS
    from canlab.etl import build_regions, load_labour_force, load_population

    labour = load_labour_force(raw_dir / "14100327.csv")
    population = load_population(
        raw_dir / "17100005.csv", keep_age_groups=DEFAULT_POPULATION_AGE_GROUPS
    )
    regions = build_regions(labour, population)
    return regions, labour, population


@pytest.fixture
def db(raw_dir: Path, sql_dir: Path, tmp_path: Path):
    """A fully built SQLite warehouse from the fixture CSVs."""
    from canlab.config import DEFAULT_POPULATION_AGE_GROUPS
    from canlab.db import build_database
    from canlab.etl import build_regions, load_labour_force, load_population

    labour = load_labour_force(raw_dir / "14100327.csv")
    population = load_population(
        raw_dir / "17100005.csv", keep_age_groups=DEFAULT_POPULATION_AGE_GROUPS
    )
    regions = build_regions(labour, population)
    conn = build_database(tmp_path / "test.db", sql_dir, regions, labour, population)
    yield conn
    conn.close()
