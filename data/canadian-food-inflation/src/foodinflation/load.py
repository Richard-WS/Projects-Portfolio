"""Loading and cleaning Statistics Canada CPI data (table 18-10-0004-01).

The raw table dump is large (all geographies, all products, all index base
years), so this module reduces it to the series this project analyses:
Canada, a small set of product groups, one consistent base year (2002=100),
from 2015 onward.
"""

from __future__ import annotations

import pandas as pd

# Series of interest, as named in the Statistics Canada table.
PRODUCTS = [
    "All-items",
    "Food purchased from stores",
    "Food purchased from restaurants",
    "Fresh vegetables",
    "Fresh fruit",
]

# All of these series share the 2002=100 base, so index levels are
# directly comparable. Other base years exist in the table for other series.
BASE_YEAR = "2002=100"

# Analysis window. CPI data goes back to 1914; the recent decade is the
# story we want to tell (pre-COVID, the 2021-2023 inflation spike, easing).
START = "2015-01"


def load_raw(path: str) -> pd.DataFrame:
    """Read the Statistics Canada CSV dump.

    The file is encoded with a UTF-8 BOM, hence ``utf-8-sig``.
    """
    return pd.read_csv(path, encoding="utf-8-sig")


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Reduce the raw table to the tidy dataset used for analysis.

    Keeps only Canada, the selected products, the shared base year, and the
    analysis window. Returns a long-format frame with columns
    ``date`` (datetime), ``product`` (str), ``value`` (float index level).
    """
    df = raw.copy()
    df = df[
        (df["GEO"] == "Canada")
        & (df["Products and product groups"].isin(PRODUCTS))
        & (df["UOM"] == BASE_YEAR)
        & (df["REF_DATE"] >= START)
    ]
    df = df[["REF_DATE", "Products and product groups", "VALUE"]]
    df = df.rename(
        columns={
            "REF_DATE": "date",
            "Products and product groups": "product",
            "VALUE": "value",
        }
    )
    df["date"] = pd.to_datetime(df["date"] + "-01")
    df = df.sort_values(["product", "date"]).reset_index(drop=True)
    return df


def add_yoy(df: pd.DataFrame) -> pd.DataFrame:
    """Append a ``yoy`` column: year-over-year percent change per product.

    The first twelve observations of each product have no prior-year
    comparison and are NaN.
    """
    out = df.copy()
    out["yoy"] = out.groupby("product")["value"].transform(
        lambda s: (s / s.shift(12) - 1) * 100
    )
    return out


def pivot_series(df: pd.DataFrame) -> pd.DataFrame:
    """Wide form: one column per product, datetime index."""
    return df.pivot(index="date", columns="product", values="value").sort_index()
