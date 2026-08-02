"""Ephemeris computations.

Monthly heliocentric ecliptic positions from Astropy. The default
``builtin`` ephemeris is ERFA's planetary model: offline, deterministic
across machines, and accurate to arcsecond/arcminute level — far more than
a scatter-plot viewer needs. Pass ``ephemeris="jpl"`` (and optionally
include Pluto) for arcsecond-grade JPL DE440s positions, which requires a
one-time ephemeris download.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import BarycentricMeanEcliptic, SkyCoord, get_body_barycentric
from astropy.coordinates.representation import CartesianRepresentation
from astropy.time import Time

# Ephemerides are evaluated in Terrestrial Time (TT). Using TT directly
# avoids astropy's pre-1972 UTC leap-second extrapolation (which is what
# ERFA warns about on 1900-era dates) and is the standard convention for
# solar-system work.
TIME_SCALE = "tt"


def month_starts(start_iso: str, end_iso: str, step_months: int = 1) -> list[str]:
    """First day of every month from start_iso to end_iso inclusive."""
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if start.day != 1:
        raise ValueError(f"start must be the first of a month, got {start_iso}")
    if end.day != 1:
        raise ValueError(f"end must be the first of a month, got {end_iso}")
    if start > end:
        raise ValueError(f"start {start_iso} is after end {end_iso}")

    dates: list[str] = []
    y, m = start.year, start.month
    while True:
        d = date(y, m, 1)
        if d > end:
            break
        dates.append(d.isoformat())
        total = (m - 1) + step_months
        y, m = y + total // 12, total % 12 + 1
    return dates


def heliocentric_ecliptic_xy(
    body: str, times: Time, ephemeris: str = "builtin"
) -> tuple[np.ndarray, np.ndarray]:
    """Heliocentric ecliptic (x, y) of *body* at *times*, in AU.

    Barycentric ICRS vectors for the body and the Sun are differenced, then
    rotated into the mean ecliptic frame of J2000. The residual barycenter
    offset (< 0.01 AU) is negligible at this scale.
    """
    pb = get_body_barycentric(body, times, ephemeris=ephemeris)
    ps = get_body_barycentric("sun", times, ephemeris=ephemeris)
    d = pb - ps  # CartesianRepresentation, ICRS axes
    sky = SkyCoord(
        CartesianRepresentation(d.x, d.y, d.z),
        frame="icrs",
    )
    ecl = sky.transform_to(BarycentricMeanEcliptic())
    return (
        ecl.cartesian.x.to_value(u.au),
        ecl.cartesian.y.to_value(u.au),
    )


def generate_rows(
    start_iso: str,
    end_iso: str,
    bodies: list[str],
    ephemeris: str = "builtin",
    step_months: int = 1,
) -> list[dict]:
    """Rows of {date, planet, x_au, y_au} for every body at every month start."""
    dates = month_starts(start_iso, end_iso, step_months)
    times = Time(dates, scale=TIME_SCALE)
    rows: list[dict] = []
    for body in bodies:
        x, y = heliocentric_ecliptic_xy(body, times, ephemeris=ephemeris)
        for d, xi, yi in zip(dates, x, y):
            rows.append(
                {"date": d, "planet": body, "x_au": float(xi), "y_au": float(yi)}
            )
    return rows


def write_csv(rows: list[dict], path: str, precision: int = 6) -> None:
    """Write rows to CSV, rounding coordinates to *precision* decimals.

    The csv module always emits CRLF on write; we strip the CR so the
    committed file has plain LF line endings.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="\n") as fh:
        writer = csv.DictWriter(fh, fieldnames=["date", "planet", "x_au", "y_au"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "date": row["date"],
                    "planet": row["planet"],
                    "x_au": round(row["x_au"], precision),
                    "y_au": round(row["y_au"], precision),
                }
            )
    # csv.DictWriter emits \r\n regardless of newline; normalize to \n
    text = out.read_bytes()
    if b"\r\n" in text:
        out.write_bytes(text.replace(b"\r\n", b"\n"))
