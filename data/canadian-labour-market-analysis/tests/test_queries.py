"""Catalog and golden-value tests.

Every catalog query runs against the fixture database and is checked against
hand-computed values derived from the fixture spec in conftest.py (constant
rates, linear employment/population series). If the fixture changes, these
tests are the contract that must be updated deliberately.
"""
from __future__ import annotations

import pandas as pd
import pytest

from canlab.queries import parse_catalog, run_query

from conftest import SQL_DIR


def _run(db, catalog, name) -> pd.DataFrame:
    entry = next(q for q in catalog if q.name == name)
    return run_query(db, entry)


def test_catalog_has_14_unique_queries(catalog):
    names = [q.name for q in catalog]
    assert len(names) == 14
    assert len(set(names)) == 14


def test_catalog_entries_have_metadata(catalog):
    for q in catalog:
        assert q.title, q.name
        assert q.question, q.name
        assert q.technique, q.name
        assert q.sql.strip().upper().startswith(("SELECT", "WITH"))


def test_parse_catalog_roundtrip():
    text = (SQL_DIR / "03_analytics.sql").read_text(encoding="utf-8")
    parsed = parse_catalog(text)
    # Re-serialized bodies must re-parse to the same names.
    assert [q.name for q in parse_catalog("\n\n".join(f"-- query: {q.name}\n{q.sql}" for q in parsed))] == [
        q.name for q in parsed
    ]


@pytest.mark.parametrize("name", [
    "q01_unemployment_national", "q02_unemployment_by_province_latest",
    "q03_employment_growth_yoy", "q04_provincial_employment_share",
    "q05_fastest_growing_provinces", "q06_recession_2008_recovery",
    "q07_covid_shock_2020", "q08_nb_vs_canada_unemployment",
    "q09_unemployment_moving_average", "q10_employment_per_working_age",
    "q11_gender_participation_gap", "q12_youth_unemployment",
    "q13_part_time_share", "q14_nb_employment_by_decade",
])
def test_every_catalog_query_runs_and_returns_rows(db, catalog, name):
    df = _run(db, catalog, name)
    assert len(df) > 0, f"{name} returned no rows"
    assert df.shape[1] >= 1


# ── golden values ────────────────────────────────────────────────────────

def test_q01_national_unemployment_constant(db, catalog):
    df = _run(db, catalog, "q01_unemployment_national")
    assert list(df.columns) == ["ref_year", "unemployment_pct"]
    assert len(df) == 13
    # Canada's fixture unemployment rate is a constant 5.0.
    assert (df["unemployment_pct"] == 5.0).all()


def test_q02_latest_year_ranking(db, catalog):
    df = _run(db, catalog, "q02_unemployment_by_province_latest")
    assert list(df.columns) == ["region_name", "unemployment_rate_pct", "employment_rate_pct"]
    assert list(df["region_name"]) == ["New Brunswick", "Ontario"]
    assert list(df["unemployment_rate_pct"]) == [8.0, 4.0]


def test_q03_yoy_growth(db, catalog):
    df = _run(db, catalog, "q03_employment_growth_yoy")
    assert df.loc[df["ref_year"] == 1976, "yoy_growth_pct"].iloc[0] is None or pd.isna(
        df.loc[df["ref_year"] == 1976, "yoy_growth_pct"].iloc[0]
    )
    row_2000 = df.loc[df["ref_year"] == 2000].iloc[0]
    assert row_2000["employment_k"] == pytest.approx(912.0)
    assert row_2000["yoy_growth_pct"] == pytest.approx(1.33)  # (912/900 - 1)*100


def test_q04_provincial_share_two_periods(db, catalog):
    df = _run(db, catalog, "q04_provincial_employment_share")
    share_1976 = dict(zip(df.loc[df["ref_year"] == 1976, "region_name"],
                          df.loc[df["ref_year"] == 1976, "share_pct"]))
    assert share_1976 == {"Ontario": 93.75, "New Brunswick": 6.25}
    share_2025 = dict(zip(df.loc[df["ref_year"] == 2025, "region_name"],
                          df.loc[df["ref_year"] == 2025, "share_pct"]))
    assert share_2025["New Brunswick"] == pytest.approx(6.76)
    assert share_2025["Ontario"] == pytest.approx(93.24)


def test_q05_fastest_growing(db, catalog):
    df = _run(db, catalog, "q05_fastest_growing_provinces")
    assert list(df["region_name"]) == ["New Brunswick", "Ontario"]
    nb = df.iloc[0]
    assert nb["emp_2000_k"] == pytest.approx(42.4)
    assert nb["emp_2025_k"] == pytest.approx(44.9)
    assert nb["growth_pct"] == pytest.approx(5.9)  # (44.9/42.4 - 1)*100


def test_q06_recession_peak_math(db, catalog):
    df = _run(db, catalog, "q06_recession_2008_recovery")
    rows = {int(r.ref_year): r for r in df.itertuples()}
    assert rows[2008].vs_peak_k == 0.0  # 2008 IS the pre-2009 peak
    assert rows[2009].vs_peak_k == pytest.approx(0.5)
    assert rows[2012].vs_peak_k == pytest.approx(2.0)


def test_q07_covid_shock(db, catalog):
    df = _run(db, catalog, "q07_covid_shock_2020")
    rows = dict(zip(df["region_code"], df["pct_change_2019_2021"]))
    assert rows["NB"] == pytest.approx(0.45)  # (44.5/44.3 - 1)*100
    assert rows["ON"] == pytest.approx(0.13)  # (618.0/617.2 - 1)*100


def test_q08_nb_canada_gap_by_decade(db, catalog):
    df = _run(db, catalog, "q08_nb_vs_canada_unemployment")
    rows = {int(r.decade): r for r in df.itertuples()}
    for decade in (1970, 2000, 2010, 2020):
        assert rows[decade].gap_pp == pytest.approx(3.0)  # 8.0 - 5.0
    assert rows[2020].nb_avg_pct == pytest.approx(8.0)
    assert rows[2020].canada_avg_pct == pytest.approx(5.0)


def test_q09_moving_average_constant_series(db, catalog):
    df = _run(db, catalog, "q09_unemployment_moving_average")
    assert (df["moving_average_5yr"] == 5.0).all()


def test_q10_employment_per_working_age(db, catalog):
    df = _run(db, catalog, "q10_employment_per_working_age")
    rows = {(r.region_name, int(r.ref_year)): r for r in df.itertuples()}
    # Provinces only (Canada excluded — the query compares provinces).
    assert list(df["region_name"]) == ["New Brunswick", "Ontario", "New Brunswick", "Ontario"]
    # 1976: NB 40,000 jobs / 400,000 people 15-64 = 100 per 1000.
    assert rows[("New Brunswick", 1976)].employed_per_1000 == pytest.approx(100.0)
    # 1976: ON 600,000 / 12,000,000 = 50 per 1000.
    assert rows[("Ontario", 1976)].employed_per_1000 == pytest.approx(50.0)
    # 2025: ON 619,600 / 13,470,000 = 46.0 per 1000.
    assert rows[("Ontario", 2025)].employed_per_1000 == pytest.approx(46.0)


def test_q11_gender_participation_gap(db, catalog):
    df = _run(db, catalog, "q11_gender_participation_gap")
    assert len(df) == 3  # 1976, 2000, 2025
    # Participation 65%, Men+ = 55% share, Women+ = 45% share -> gap 6.5 pp.
    row = df.loc[df["ref_year"] == 2025].iloc[0]
    assert row["men_pct"] == pytest.approx(35.8)
    assert row["women_pct"] == pytest.approx(29.3)
    assert row["gap_pp"] == pytest.approx(6.5)


def test_q12_youth_vs_prime_unemployment(db, catalog):
    df = _run(db, catalog, "q12_youth_unemployment")
    row = df.loc[df["ref_year"] == 2021].iloc[0]
    assert row["youth_15_24_pct"] == pytest.approx(10.0)  # 5.0 + 5.0 fixture bump
    assert row["prime_25_54_pct"] == pytest.approx(5.0)
    assert row["gap_pp"] == pytest.approx(5.0)


def test_q13_part_time_share_ranking(db, catalog):
    df = _run(db, catalog, "q13_part_time_share")
    assert list(df["region_name"]) == ["New Brunswick", "Ontario"]
    assert list(df["part_time_share_pct"]) == [18.0, 14.0]


def test_q14_nb_decades(db, catalog):
    df = _run(db, catalog, "q14_nb_employment_by_decade")
    rows = {int(r.decade): r for r in df.itertuples()}
    assert rows[1970].avg_employment_k == pytest.approx(40.0)
    assert rows[2000].avg_employment_k == pytest.approx(43.0)   # 42.4, 43.0-43.3
    assert rows[2010].avg_employment_k == pytest.approx(43.7)   # 43.4-43.6, 44.3
    assert rows[2020].avg_employment_k == pytest.approx(44.6)   # 44.4, 44.5, 44.9
