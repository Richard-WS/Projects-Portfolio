"""Feature extraction tests."""
from __future__ import annotations

import numpy as np
import pytest

from diskfail import features as F
from diskfail.data import WindowRecord
from tests.conftest import ATTRS


def _record(n_days: int = 8, n_attrs: int = 3, seed: int = 0) -> WindowRecord:
    rng = np.random.default_rng(seed)
    return WindowRecord(
        serial="S1",
        end_day=100,
        label=0,
        kind="train",
        days=np.arange(93, 93 + n_days, dtype=np.int64),
        values=rng.normal(size=(n_days, n_attrs)).astype(np.float32),
    )


def test_window_stats_shape():
    rec = _record()
    stats = F.window_stats(rec.values)
    assert stats.shape == (3, 8)  # n_attrs x n_stats


def test_window_stats_trend():
    # monotonically increasing attribute 0
    vals = np.zeros((8, 2), dtype=np.float32)
    vals[:, 0] = np.arange(8, dtype=np.float32)
    vals[:, 1] = 5.0
    stats = F.window_stats(vals)
    assert stats[0, 0] == 7.0  # current
    assert stats[0, 1] == pytest.approx(3.5)  # mean
    assert stats[0, 2] == 0.0  # min
    assert stats[0, 3] == 7.0  # max
    assert stats[0, 5] == pytest.approx(7.0)  # max_delta = cur - min(prev)
    assert stats[0, 6] == pytest.approx(1.0)  # slope
    assert stats[0, 7] == 7.0  # n_increases
    assert stats[1, 0] == 5.0
    assert stats[1, 2] == 5.0
    assert stats[1, 3] == 5.0
    assert stats[1, 7] == 0.0


def test_window_stats_nan():
    vals = np.full((6, 2), np.nan, dtype=np.float32)
    vals[0, 0] = 1.0
    stats = F.window_stats(vals)
    assert np.isnan(stats[1, 0])  # current of an all-NaN attribute is NaN
    assert np.isnan(stats[1, 1])  # mean of an all-NaN attribute is NaN
    assert stats.shape == (2, 8)


def test_feature_columns():
    cols = F.feature_columns(["smart_1_raw", "smart_5_raw"])
    assert cols == [
        f"smart_{a}_raw_{s}" for a in (1, 5) for s in F.STAT_NAMES
    ]
    assert len(cols) == 2 * 8


def test_build_feature_frame(dataset):
    tmp_path, raw, cfg = dataset
    from diskfail import data as D

    fleet = D.scan_fleet(raw, cfg.data.max_drives, cfg.data.seed)
    train, lead = D.plan_windows(fleet, 7, 7, [1, 3, 7, 14, 30], seed=42)
    series, attrs = D.load_series(raw, fleet, train, lead, ATTRS, 0.99, window_days=7)
    records = D.collect_windows(series, train, 7, 3)
    df = F.build_feature_frame(records, attrs, fleet)
    assert len(df) == len(records)
    for col in F.META_COLUMNS + ["horizon"] + F.feature_columns(attrs):
        assert col in df.columns
    # horizon is NaN for training windows
    assert df["horizon"].isna().all()
    # capacity propagated from fleet info
    assert (df["capacity_bytes"] == 1_000_000_000_000).all()
    # failing windows should show the SMART 5 ramp in max_delta
    failing = df[df["label"] == 1]
    assert len(failing) == 4 * 7
    assert (failing["smart_5_raw_max_delta"] > 0).any()


def test_cap_negatives(dataset):
    tmp_path, raw, cfg = dataset
    from diskfail import data as D

    fleet = D.scan_fleet(raw, cfg.data.max_drives, cfg.data.seed)
    train, _ = D.plan_windows(fleet, 7, 7, [1, 3, 7, 14, 30], seed=42)
    series, attrs = D.load_series(raw, fleet, train, {}, ATTRS, 0.99, window_days=7)
    records = D.collect_windows(series, train, 7, 3)
    df = F.build_feature_frame(records, attrs, fleet)
    capped = F.cap_negatives(df, max_negatives=10, seed=0)
    n_neg = int((capped["label"] == 0).sum())
    assert n_neg == 10  # capped
    assert (capped["label"] == 1).sum() == (df["label"] == 1).sum()  # positives kept
