"""Extract, transform and load the two Statistics Canada tables.

Both raw CSVs share the StatsCan long format: one row per (reference period,
geography, gender, age group [, characteristic]) with a UTF-8 BOM, quoted
fields, and a ``VALUE`` column that is empty for suppressed cells. The ETL
normalizes them into the warehouse's star schema:

* full geography names -> stable region codes (``New Brunswick`` -> ``NB``)
* gender labels -> ``Total`` / ``Men+`` / ``Women+``
* year strings -> ints, values -> floats, suppressed rows dropped
* population restricted to the age groups shared with the labour table
  (plus ``All ages``) so the two fact tables join cleanly
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# StatsCan geography names -> warehouse region codes.
REGION_CODES = {
    "Canada": "CA",
    "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE",
    "Nova Scotia": "NS",
    "New Brunswick": "NB",
    "Quebec": "QC",
    "Ontario": "ON",
    "Manitoba": "MB",
    "Saskatchewan": "SK",
    "Alberta": "AB",
    "British Columbia": "BC",
    "Yukon": "YT",
    "Northwest Territories": "NT",
    "Nunavut": "NU",
    "Northwest Territories including Nunavut": "NTI",
}

REGION_TYPES = {
    "CA": "country",
    "NL": "province",
    "PE": "province",
    "NS": "province",
    "NB": "province",
    "QC": "province",
    "ON": "province",
    "MB": "province",
    "SK": "province",
    "AB": "province",
    "BC": "province",
    "YT": "territory",
    "NT": "territory",
    "NU": "territory",
    "NTI": "territory",
}

GENDERS = ("Total", "Men+", "Women+")

LABOUR_COLUMNS = ["ref_year", "region_code", "gender", "age_group", "characteristic", "value", "uom"]
POPULATION_COLUMNS = ["ref_year", "region_code", "gender", "age_group", "value"]


def normalize_gender(label: str) -> str:
    """Map StatsCan gender labels to the warehouse vocabulary."""
    label = label.strip()
    if label.lower().startswith("total"):
        return "Total"
    if label == "Men+":
        return "Men+"
    if label == "Women+":
        return "Women+"
    raise ValueError(f"unexpected gender label: {label!r}")


def region_code(name: str) -> str:
    """Map a StatsCan geography name to its warehouse code."""
    try:
        return REGION_CODES[name.strip()]
    except KeyError:
        raise ValueError(
            f"unexpected geography {name!r} — known geographies: {sorted(REGION_CODES)}"
        ) from None


def _read_stats_can_csv(path: Path, usecols: list[str]) -> pd.DataFrame:
    """Read a StatsCan CSV (UTF-8 BOM, quoted) keeping only needed columns."""
    return pd.read_csv(path, encoding="utf-8-sig", usecols=usecols)


def load_labour_force(path: str | Path) -> pd.DataFrame:
    """Load and normalize the labour-force table (14-10-0327-01)."""
    df = _read_stats_can_csv(
        Path(path),
        usecols=[
            "REF_DATE",
            "GEO",
            "Gender",
            "Age group",
            "Labour force characteristics",
            "VALUE",
            "UOM",
        ],
    )
    df = df.rename(
        columns={
            "REF_DATE": "ref_year",
            "GEO": "geo",
            "Gender": "gender",
            "Age group": "age_group",
            "Labour force characteristics": "characteristic",
            "VALUE": "value",
            "UOM": "uom",
        }
    )
    df["ref_year"] = df["ref_year"].astype(int)
    df["region_code"] = df["geo"].map(region_code)
    df["gender"] = df["gender"].map(normalize_gender)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["uom"] = df["uom"].str.strip()
    df = df.dropna(subset=["value"])
    df = df[LABOUR_COLUMNS]
    df = df.sort_values(
        ["ref_year", "region_code", "gender", "age_group", "characteristic"]
    ).reset_index(drop=True)
    return df


def load_population(
    path: str | Path, keep_age_groups: list[str] | None = None
) -> pd.DataFrame:
    """Load and normalize the population table (17-10-0005-01).

    Only the age groups in ``keep_age_groups`` are kept — the raw table has
    139 age categories including single-year ages and derived rows
    ("Average age", "Median age") that are not part of the labour analysis.
    """
    keep = set(keep_age_groups) if keep_age_groups else None
    df = _read_stats_can_csv(
        Path(path), usecols=["REF_DATE", "GEO", "Gender", "Age group", "VALUE"]
    )
    df = df.rename(
        columns={
            "REF_DATE": "ref_year",
            "GEO": "geo",
            "Gender": "gender",
            "Age group": "age_group",
            "VALUE": "value",
        }
    )
    df["ref_year"] = df["ref_year"].astype(int)
    df["region_code"] = df["geo"].map(region_code)
    df["gender"] = df["gender"].map(normalize_gender)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    if keep is not None:
        df = df[df["age_group"].isin(keep)]
    df = df[POPULATION_COLUMNS]
    df = df.sort_values(["ref_year", "region_code", "gender", "age_group"]).reset_index(
        drop=True
    )
    return df


def build_regions(labour: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    """Build the region dimension from every region present in either table."""
    codes = set(labour["region_code"]) | set(population["region_code"])
    rows = [
        {"region_code": code, "region_name": name, "region_type": REGION_TYPES[code]}
        for name, code in REGION_CODES.items()
        if code in codes
    ]
    return pd.DataFrame(rows, columns=["region_code", "region_name", "region_type"])
