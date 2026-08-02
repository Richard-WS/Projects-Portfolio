"""Shared fixtures: a tiny synthetic Backblaze-style daily-snapshot dataset
and a Config wired to it. No network, no real data — fully hermetic."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from diskfail.config import Config

ATTRS = ["smart_1_raw", "smart_4_raw", "smart_5_raw", "smart_9_raw", "smart_187_raw"]
FAIL_DAY = 50  # failing drives are flagged on day 50 and disappear after


def make_synthetic_dataset(root: Path, n_days: int = 60, n_healthy: int = 40,
                           n_failing: int = 4, seed: int = 0) -> Path:
    """Build daily CSV snapshots in root/raw, one file per day, same columns
    as the Backblaze quarterly dumps. Failing drives ramp up SMART 5 and 187
    from day 45 and are flagged on FAIL_DAY."""
    rng = np.random.default_rng(seed)
    start = date(2024, 1, 1)
    healthy = [f"H{str(i).zfill(3)}" for i in range(n_healthy)]
    failing = [f"F{str(i).zfill(3)}" for i in range(n_failing)]
    all_drives = healthy + failing

    base = {}
    for s in all_drives:
        base[s] = {
            "smart_1_raw": float(rng.integers(1000, 5000)),
            "smart_4_raw": float(rng.integers(50, 200)),
            "smart_5_raw": 0.0,
            "smart_9_raw": float(rng.integers(5000, 9000)),
            "smart_187_raw": 0.0,
        }

    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for d in range(1, n_days + 1):
        day = start + timedelta(days=d - 1)
        rows = []
        for s in all_drives:
            if s in failing and d > FAIL_DAY:
                continue  # failed drives disappear after the failure day
            v = dict(base[s])
            if s in failing and d >= 45:
                v["smart_5_raw"] = float((d - 45) * 10)
                v["smart_187_raw"] = float((d - 45) * 3)
            v["smart_9_raw"] += float(d)
            rows.append(
                {
                    "date": day.isoformat(),
                    "serial_number": s,
                    "model": "TestDrive-1TB",
                    "capacity_bytes": 1_000_000_000_000,
                    "failure": 1 if (s in failing and d == FAIL_DAY) else 0,
                    **{a: v[a] for a in ATTRS},
                }
            )
        pd.DataFrame(rows).to_csv(raw / f"{day.isoformat()}.csv", index=False)
    return raw


def make_config(root: Path, raw_dir: Path, **data_overrides) -> Config:
    """Write a config file pointing at the synthetic raw dir and load it."""
    cfg_yaml = f"""
data:
  raw_dir: {raw_dir}
  raw_csv: .            # directory of daily CSVs
  samples_dir: {root / 'samples'}
  raw_sample: raw_smart_sample.csv.gz
  sample_drives: 40
  sample_days: 10
  max_drives: 1000
  smart_missing_threshold: 0.99
  seed: 42
labels:
  pre_failure_days: 30
  horizon_days: 7
features:
  window_days: 7
  min_window_obs: 3
  leadtime_horizons: [1, 3, 7, 14, 30]
split:
  test_size: 0.2
  seed: 42
  max_negative_drives: 100
model:
  max_iter: 25
  learning_rate: 0.1
  min_samples_leaf: 5
  l2_regularization: 1.0
  cv_folds: 3
paths:
  feature_train: {root / 'samples' / 'features_train.csv.gz'}
  feature_test: {root / 'samples' / 'features_test.csv.gz'}
  leadtime_features: {root / 'samples' / 'leadtime_features.csv.gz'}
  model_path: {root / 'outputs' / 'model.joblib'}
  metrics_path: {root / 'docs' / 'metrics.json'}
  report_path: {root / 'docs' / 'disk-failure-report.html'}
  predictions_path: {root / 'outputs' / 'predictions.csv'}
"""
    cfg_path = root / "config.yaml"
    cfg_path.write_text(cfg_yaml)
    return Config.load(cfg_path)


@pytest.fixture
def dataset(tmp_path: Path):
    raw = make_synthetic_dataset(tmp_path)
    cfg = make_config(tmp_path, raw)
    return tmp_path, raw, cfg


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """A tiny single-file dataset for read_header/source_files tests."""
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "serial_number": ["X1", "X2"],
            "model": ["A", "A"],
            "capacity_bytes": [1e12, 1e12],
            "failure": [0, 0],
            "smart_1_raw": [1.0, 2.0],
            "smart_5_raw": [0.0, 0.0],
        }
    )
    p = tmp_path / "one.csv"
    df.to_csv(p, index=False)
    return p
