"""Tests for the food inflation analysis package."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from foodinflation.analysis import months_above, ols, yoy
from foodinflation.load import BASE_YEAR, PRODUCTS, clean, load_raw, pivot_series

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_yoy_matches_hand_calculation():
    index = pd.Series([100.0, 105.0, 110.0], index=pd.date_range("2023-01", periods=3, freq="MS"))
    # No prior-year values -> NaN for the first 12 months of a monthly series.
    result = yoy(index)
    assert result.isna().all()


def test_yoy_after_twelve_months():
    index = pd.Series(
        [100.0] * 12 + [105.0] * 12,
        index=pd.date_range("2022-01", periods=24, freq="MS"),
    )
    result = yoy(index)
    assert np.isnan(result.iloc[:12]).all()
    # Same month last year was 100, now 105 -> 5%.
    assert result.iloc[12] == pytest.approx(5.0)
    assert result.iloc[23] == pytest.approx(5.0)


def test_ols_perfect_line():
    x = np.arange(10, dtype=float)
    y = 2.0 * x + 1.0
    slope, intercept, r2 = ols(x, y)
    assert slope == pytest.approx(2.0)
    assert intercept == pytest.approx(1.0)
    assert r2 == pytest.approx(1.0)


def test_ols_requires_matching_lengths():
    with pytest.raises(ValueError):
        ols([1.0, 2.0], [1.0])


def test_months_above_filters_correctly():
    dates = pd.date_range("2023-01", periods=5, freq="MS")
    food = pd.Series([5.0, 6.0, 7.0, 4.0, 8.0], index=dates)
    all_items = pd.Series([5.0, 4.0, 7.0, 6.0, 3.0], index=dates)
    above = months_above(food, all_items)
    assert list(above.index) == [dates[1], dates[4]]


def _tiny_raw() -> pd.DataFrame:
    """A minimal raw table covering both in-scope and out-of-scope rows."""
    rows = [
        # in scope: Canada, wanted product, right base year, in window
        ("2023-01", "Canada", "All-items", "2002=100", 150.0),
        ("2023-02", "Canada", "All-items", "2002=100", 151.0),
        # out of scope: wrong product
        ("2023-01", "Canada", "Gasoline", "2002=100", 200.0),
        # out of scope: province
        ("2023-01", "New Brunswick", "All-items", "2002=100", 149.0),
        # out of scope: wrong base year
        ("2023-01", "Canada", "All-items", "202404=100", 101.0),
        # out of scope: before window
        ("2014-12", "Canada", "All-items", "2002=100", 120.0),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "REF_DATE",
            "GEO",
            "Products and product groups",
            "UOM",
            "VALUE",
        ],
    )


def test_clean_filters_to_scope():
    cleaned = clean(_tiny_raw())
    assert set(cleaned["product"]) == {"All-items"}
    assert (cleaned["date"] >= pd.Timestamp("2015-01-01")).all()
    assert len(cleaned) == 2
    assert list(cleaned.columns) == ["date", "product", "value"]


def test_pivot_series_shapes_correctly():
    raw = _tiny_raw()
    cleaned = clean(raw)
    wide = pivot_series(cleaned)
    assert list(wide.columns) == ["All-items"]
    assert wide.index.name == "date"


def test_processed_file_schema():
    """The committed processed dataset must have the documented schema."""
    path = PROJECT_ROOT / "data" / "processed" / "cpi_canada_food_2015_2026.csv"
    assert path.exists(), "processed dataset missing — run scripts/make_processed.py"
    df = pd.read_csv(path)
    assert list(df.columns) == ["date", "product", "value", "yoy"]
    assert set(df["product"].unique()) == set(PRODUCTS)
    assert df["value"].notna().all()
    # Monthly spacing: no duplicate dates within a product.
    dupes = df.duplicated(subset=["date", "product"]).sum()
    assert dupes == 0


def test_raw_file_not_tracked_by_git():
    """The 160 MB raw dump must never be committed."""
    import subprocess

    out = subprocess.run(
        ["git", "check-ignore", "data/raw/18100004.csv"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, "data/raw/ is not gitignored"
