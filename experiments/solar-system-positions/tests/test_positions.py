"""Position data: month enumeration, committed CSV invariants, Astropy golden checks."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest
from astropy.time import Time

from solarpositions.positions import (
    TIME_SCALE,
    heliocentric_ecliptic_xy,
    month_starts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "positions.csv"

EXPECTED_BODIES = [
    "mercury", "venus", "earth", "mars",
    "jupiter", "saturn", "uranus", "neptune",
]

# 1900-01 .. 2100-12 inclusive
EXPECTED_FRAMES = 201 * 12  # 2412


# ---------- month enumeration ----------

def test_month_starts_full_range():
    dates = month_starts("1900-01-01", "2100-12-01")
    assert len(dates) == EXPECTED_FRAMES
    assert dates[0] == "1900-01-01"
    assert dates[-1] == "2100-12-01"
    # strictly increasing, all on the first of a month
    for a, b in zip(dates, dates[1:]):
        assert a < b
        assert b.endswith("-01")


def test_month_starts_step():
    assert len(month_starts("2000-01-01", "2000-12-01", step_months=2)) == 6
    assert len(month_starts("2000-01-01", "2000-12-01", step_months=12)) == 1


def test_month_starts_validation():
    with pytest.raises(ValueError, match="first of a month"):
        month_starts("2000-01-15", "2000-12-01")
    with pytest.raises(ValueError, match="after end"):
        month_starts("2001-01-01", "2000-12-01")


# ---------- committed CSV invariants ----------

def _load_csv():
    rows = list(csv.DictReader(open(CSV_PATH, newline="")))
    return rows


@pytest.mark.skipif(not CSV_PATH.exists(), reason="positions.csv not generated yet")
def test_csv_shape():
    rows = _load_csv()
    assert len(rows) == EXPECTED_FRAMES * len(EXPECTED_BODIES)
    bodies = {r["planet"] for r in rows}
    assert bodies == set(EXPECTED_BODIES)
    dates = sorted({r["date"] for r in rows})
    assert len(dates) == EXPECTED_FRAMES
    assert dates[0] == "1900-01-01"
    assert dates[-1] == "2100-12-01"


@pytest.mark.skipif(not CSV_PATH.exists(), reason="positions.csv not generated yet")
def test_csv_all_finite():
    for r in _load_csv():
        assert math.isfinite(float(r["x_au"]))
        assert math.isfinite(float(r["y_au"]))


@pytest.mark.skipif(not CSV_PATH.exists(), reason="positions.csv not generated yet")
def test_orbital_order_every_frame():
    """Radial distances never cross: Mercury < Venus < ... < Neptune."""
    by_frame: dict[str, dict[str, float]] = {}
    for r in _load_csv():
        by_frame.setdefault(r["date"], {})[r["planet"]] = math.hypot(
            float(r["x_au"]), float(r["y_au"])
        )
    for date, radii in by_frame.items():
        ordered = [radii[b] for b in EXPECTED_BODIES]
        assert ordered == sorted(ordered), f"orbit order violated on {date}"


@pytest.mark.skipif(not CSV_PATH.exists(), reason="positions.csv not generated yet")
def test_earth_stays_near_one_au():
    for r in _load_csv():
        if r["planet"] != "earth":
            continue
        d = math.hypot(float(r["x_au"]), float(r["y_au"]))
        assert 0.95 <= d <= 1.05


# ---------- Astropy golden checks ----------

@pytest.mark.skipif(not CSV_PATH.exists(), reason="positions.csv not generated yet")
def test_committed_values_match_astropy_builtin():
    """Recompute a handful of (date, planet) pairs and compare with the CSV."""
    rows = {(r["date"], r["planet"]): r for r in _load_csv()}
    checks = [
        ("1900-01-01", "earth"),
        ("1900-01-01", "jupiter"),
        ("2000-06-01", "mars"),
        ("2050-03-01", "venus"),
        ("2100-12-01", "neptune"),
        ("2100-12-01", "mercury"),
    ]
    for date, planet in checks:
        times = Time([date], scale=TIME_SCALE)
        x, y = heliocentric_ecliptic_xy(planet, times, ephemeris="builtin")
        row = rows[(date, planet)]
        assert x[0] == pytest.approx(float(row["x_au"]), abs=5e-5)
        assert y[0] == pytest.approx(float(row["y_au"]), abs=5e-5)


def test_ecliptic_orientation_march_equinox_2000():
    """Earth sits near ecliptic longitude 180 deg at the March equinox,
    i.e. x is strongly negative — confirms the ICRS->ecliptic rotation sign."""
    times = Time(["2000-03-20"], scale=TIME_SCALE)
    x, y = heliocentric_ecliptic_xy("earth", times, ephemeris="builtin")
    assert x[0] < -0.9
    assert abs(y[0]) < 0.5


def test_astropy_builtin_works_offline():
    """The whole pipeline must not need a network. The built-in ephemeris
    computes straight away (ERFA), unlike JPL which downloads on first use."""
    times = Time(["2020-01-01"], scale=TIME_SCALE)
    x, y = heliocentric_ecliptic_xy("mercury", times, ephemeris="builtin")
    assert np.isfinite(x[0]) and np.isfinite(y[0])
