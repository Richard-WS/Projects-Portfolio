"""Hermetic fixtures: synthetic light curves with a controllable transit signal.

A synthetic curve is a baseline with Gaussian noise, optionally a set of
periodic transit dips (box-shaped, in the Kepler spirit) and optionally a
flare or outlier. Generators here keep every test independent of the
network and of the real dataset.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_curve(
    *,
    transit: bool = False,
    noise: float = 0.002,
    dips: int = 3,
    depth: float = 0.01,
    n_points: int = 2048,
    seed: int = 0,
) -> np.ndarray:
    """One synthetic light curve (raw flux, un-normalized)."""
    local = np.random.default_rng(seed)
    flux = 1.0 + local.normal(0.0, noise, n_points)
    if transit:
        # periodic box dips
        spacing = n_points // (dips + 1)
        width = max(3, n_points // 300)
        for i in range(1, dips + 1):
            start = i * spacing
            flux[start : start + width] -= depth
    return flux


def make_curve_csv(path, n_curves: int = 40, *, transit_frac: float = 0.5, **kwargs):
    """Write a dataset-format CSV (label 1/2 + flux columns) to ``path``."""
    rows = []
    for i in range(n_curves):
        is_transit = i % 2 == 0 if transit_frac == 0.5 else (i < n_curves * transit_frac)
        flux = make_curve(transit=is_transit, seed=i, **kwargs)
        rows.append([2 if is_transit else 1, *flux])
    pd.DataFrame(rows).to_csv(path, index=False, header=["LABEL"] + [f"f{j}" for j in range(len(rows[0]) - 1)])
    return path


@pytest.fixture
def synthetic_curves_csv(tmp_path):
    return make_curve_csv(tmp_path / "curves.csv", n_curves=40, transit_frac=0.5)


@pytest.fixture
def separable_curves_csv(tmp_path):
    """Strong transits vs pure noise — a model should separate these easily."""
    path = tmp_path / "separable.csv"
    rows = []
    for i in range(120):
        transit = i % 2 == 0  # interleave so any contiguous slice stays balanced
        flux = make_curve(transit=transit, depth=0.05, dips=4, noise=0.001, seed=i)
        rows.append([2 if transit else 1, *flux])
    pd.DataFrame(rows).to_csv(path, index=False, header=["LABEL"] + [f"f{j}" for j in range(len(rows[0]) - 1)])
    return path
