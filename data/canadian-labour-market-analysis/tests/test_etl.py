"""ETL tests: raw StatsCan CSVs -> normalized warehouse frames."""
from __future__ import annotations

import pandas as pd
import pytest

from canlab.config import DEFAULT_POPULATION_AGE_GROUPS
from canlab.etl import (
    REGION_CODES,
    build_regions,
    load_labour_force,
    load_population,
    normalize_gender,
    region_code,
)

from conftest import (
    LABOUR_GENDERS,
    POP_AGES,
    POP_REGIONS,
    YEARS,
    _employment_total,
    _pop_15_64,
)


def test_labour_force_normalized(raw_dir):
    df = load_labour_force(raw_dir / "14100327.csv")
    assert list(df.columns) == [
        "ref_year", "region_code", "gender", "age_group", "characteristic", "value", "uom",
    ]
    assert df["ref_year"].dtype.kind == "i"  # int years
    assert df["value"].dtype.kind == "f"     # float values
    assert set(df["region_code"]) == {"CA", "NB", "ON"}
    assert set(df["gender"]) == {"Total", "Men+", "Women+"}
    assert set(df["uom"]) == {"Persons in thousands", "Percent"}


def test_labour_force_drops_suppressed_rows(raw_dir):
    df = load_labour_force(raw_dir / "14100327.csv")
    # The fixture has one suppressed cell (empty VALUE); nothing survives NaN.
    assert df["value"].notna().all()


def test_labour_force_values(raw_dir):
    df = load_labour_force(raw_dir / "14100327.csv")
    # Employment, Canada, 15+, total, 1976 = 900.0 thousand.
    row = df[
        (df["ref_year"] == 1976)
        & (df["region_code"] == "CA")
        & (df["gender"] == "Total")
        & (df["age_group"] == "15 years and over")
        & (df["characteristic"] == "Employment")
    ]
    assert len(row) == 1
    assert row.iloc[0]["value"] == pytest.approx(_employment_total(1976, "Canada"))


def test_labour_force_gender_split(raw_dir):
    df = load_labour_force(raw_dir / "14100327.csv")
    men = df[
        (df["ref_year"] == 2025) & (df["region_code"] == "ON")
        & (df["gender"] == "Men+") & (df["age_group"] == "15 years and over")
        & (df["characteristic"] == "Employment")
    ].iloc[0]["value"]
    women = df[
        (df["ref_year"] == 2025) & (df["region_code"] == "ON")
        & (df["gender"] == "Women+") & (df["age_group"] == "15 years and over")
        & (df["characteristic"] == "Employment")
    ].iloc[0]["value"]
    assert men == pytest.approx(619.6 * 0.55)
    assert women == pytest.approx(619.6 * 0.45)


def test_population_filtered_to_kept_age_groups(raw_dir):
    df = load_population(
        raw_dir / "17100005.csv", keep_age_groups=DEFAULT_POPULATION_AGE_GROUPS
    )
    kept = set(df["age_group"])
    assert "All ages" in kept and "15 to 64 years" in kept
    # The fixture's extra raw groups must be dropped by the ETL.
    assert "0 to 14 years" not in kept
    assert "Average age" not in kept
    assert set(df["region_code"]) == {"CA", "NB", "ON", "YT"}


def test_population_values(raw_dir):
    df = load_population(
        raw_dir / "17100005.csv", keep_age_groups=DEFAULT_POPULATION_AGE_GROUPS
    )
    row = df[
        (df["ref_year"] == 1976) & (df["region_code"] == "NB")
        & (df["gender"] == "Total") & (df["age_group"] == "15 to 64 years")
    ]
    assert len(row) == 1
    assert row.iloc[0]["value"] == pytest.approx(_pop_15_64(1976, "New Brunswick"))


def test_normalize_gender():
    assert normalize_gender("Total - Gender") == "Total"
    assert normalize_gender("Total - gender") == "Total"
    assert normalize_gender("Men+") == "Men+"
    assert normalize_gender("Women+") == "Women+"
    with pytest.raises(ValueError):
        normalize_gender("Unknown")


def test_region_code_mapping_covers_all_names():
    # Every name used by either raw table must resolve.
    for name in (
        "Canada", "Newfoundland and Labrador", "Prince Edward Island",
        "Nova Scotia", "New Brunswick", "Quebec", "Ontario", "Manitoba",
        "Saskatchewan", "Alberta", "British Columbia", "Yukon",
        "Northwest Territories", "Nunavut",
        "Northwest Territories including Nunavut",
    ):
        assert region_code(name) in REGION_CODES.values()
    with pytest.raises(ValueError):
        region_code("Atlantis")


def test_build_regions_union_and_types(raw_dir):
    labour = load_labour_force(raw_dir / "14100327.csv")
    population = load_population(
        raw_dir / "17100005.csv", keep_age_groups=DEFAULT_POPULATION_AGE_GROUPS
    )
    regions = build_regions(labour, population)
    assert set(regions["region_code"]) == {"CA", "NB", "ON", "YT"}
    types = dict(zip(regions["region_code"], regions["region_type"]))
    assert types == {"CA": "country", "NB": "province", "ON": "province", "YT": "territory"}
