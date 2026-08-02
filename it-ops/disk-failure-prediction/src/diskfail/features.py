"""Feature extraction: per-drive S.M.A.R.T. window statistics.

Each training/evaluation example is one drive observed over a trailing
window of `window_days` (config). For every populated SMART raw attribute we
compute eight statistics that capture both the current state and the recent
trend — the values maintenance engineers actually look at when a drive
starts misbehaving.
"""
from __future__ import annotations

import warnings
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from .data import FleetInfo, WindowRecord, to_day

STAT_NAMES = [
    "current",
    "mean",
    "min",
    "max",
    "std",
    "max_delta",
    "slope",
    "n_increases",
]

META_COLUMNS = ["serial", "end_day", "label", "kind", "capacity_bytes", "days_observed", "window_obs"]


def window_stats(values: np.ndarray) -> np.ndarray:
    """One window → (n_attrs, n_stats) float array.

    values: (n_days, n_attrs) float32, rows chronological.
    Stats per attribute:
      current      — value on the last day of the window
      mean/min/max/std — nan-aware window summaries
      max_delta    — current value minus the minimum of the earlier days
      slope        — (last - first) / (days - 1), a per-day change rate
      n_increases  — days on which the attribute increased vs. the day before
    Attributes with no valid readings stay NaN (the model handles NaN).
    """
    n_days, n_attrs = values.shape
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)  # empty/all-NaN slices
        cur = values[-1]
        vmean = np.nanmean(values, axis=0)
        vmin = np.nanmin(values, axis=0)
        vmax = np.nanmax(values, axis=0)
        vstd = np.nanstd(values, axis=0)
        prev = values[:-1]
        pmin = np.nanmin(prev, axis=0) if n_days > 1 else np.full(n_attrs, np.nan)
        max_delta = cur - pmin
        slope = (cur - values[0]) / max(n_days - 1, 1)
        n_inc = np.zeros(n_attrs, dtype=np.float32)
        if n_days > 1:
            n_inc = (values[1:] > values[:-1]).sum(axis=0).astype(np.float32)
    return np.stack([cur, vmean, vmin, vmax, vstd, max_delta, slope, n_inc], axis=1)


def feature_columns(attrs: Sequence[str]) -> List[str]:
    return [f"{a}_{s}" for a in attrs for s in STAT_NAMES]


def build_feature_frame(
    records: Sequence[WindowRecord],
    attrs: Sequence[str],
    fleet: Dict[str, FleetInfo],
) -> pd.DataFrame:
    rows: List[dict] = []
    for rec in records:
        info = fleet.get(rec.serial)
        stats = window_stats(rec.values)
        row = {
            "serial": rec.serial,
            "end_day": rec.end_day,
            "label": rec.label,
            "kind": rec.kind,
            "capacity_bytes": float(info.capacity_bytes) if info else float("nan"),
            "days_observed": float(info.days_observed) if info else float("nan"),
            "window_obs": float(len(rec.days)),
        }
        if rec.kind == "leadtime" and info is not None and info.fail_date is not None:
            row["horizon"] = float(to_day(info.fail_date) - rec.end_day)
        else:
            row["horizon"] = float("nan")
        for j, attr in enumerate(attrs):
            for k, stat in enumerate(STAT_NAMES):
                row[f"{attr}_{stat}"] = float(stats[j, k])
        rows.append(row)
    cols = META_COLUMNS + ["horizon"] + feature_columns(attrs)
    return pd.DataFrame(rows, columns=cols)


def cap_negatives(feature_df: pd.DataFrame, max_negatives: int, seed: int) -> pd.DataFrame:
    """Cap healthy-drive training windows (seeded) so one giant fleet of
    healthy drives cannot dominate the positives."""
    if max_negatives <= 0:
        return feature_df
    neg = feature_df[feature_df["label"] == 0]
    pos = feature_df[feature_df["label"] == 1]
    if len(neg) <= max_negatives:
        return feature_df
    keep = neg.sample(n=max_negatives, random_state=seed)
    return pd.concat([pos, keep], ignore_index=True)
