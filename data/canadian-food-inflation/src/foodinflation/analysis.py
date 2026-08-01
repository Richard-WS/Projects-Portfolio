"""Analysis helpers used across the notebook, report, and tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def yoy(series: pd.Series) -> pd.Series:
    """Year-over-year percent change for a monthly index series.

    The first 12 observations are NaN (no prior-year value to compare).
    """
    return (series / series.shift(12) - 1) * 100


def ols(x, y) -> tuple[float, float, float]:
    """Least-squares fit of ``y = slope * x + intercept``.

    Returns ``(slope, intercept, r_squared)`` using ordinary least squares
    and Pearson correlation. Pure numpy, no extra dependencies.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or len(x) != len(y):
        raise ValueError("x and y must have the same length, at least 2")
    slope, intercept = np.polyfit(x, y, 1)
    r = np.corrcoef(x, y)[0, 1]
    return float(slope), float(intercept), float(r * r)


def months_above(food_yoy: pd.Series, all_items_yoy: pd.Series) -> pd.DataFrame:
    """Months where food-store inflation exceeded all-items inflation.

    Returns a frame with columns ``food`` and ``all_items`` (both in
    year-over-year percent terms), aligned by date, NaN rows dropped.
    """
    merged = pd.DataFrame({"food": food_yoy, "all_items": all_items_yoy}).dropna()
    return merged[merged["food"] > merged["all_items"]]
