"""Data-layer tests: fleet scan, window planning, series loading."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from diskfail import data as D
from tests.conftest import ATTRS, FAIL_DAY, make_synthetic_dataset


def test_source_files_single(sample_csv):
    assert D.source_files(sample_csv) == [sample_csv]


def test_source_files_directory(dataset):
    tmp_path, raw, _ = dataset
    files = D.source_files(raw)
    assert len(files) == 60
    assert files == sorted(files)
    assert all(f.suffix == ".csv" for f in files)


def test_smart_raw_columns():
    header = ["date", "serial_number", "smart_1_raw", "smart_5_raw", "smart_9_raw", "smart_9_normalized", "failure"]
    assert D.smart_raw_columns(header) == ["smart_1_raw", "smart_5_raw", "smart_9_raw"]


def test_to_day():
    assert D.to_day("2024-01-01") == (date(2024, 1, 1) - D.EPOCH).days
    assert D.to_day(date(2024, 1, 1)) == (date(2024, 1, 1) - D.EPOCH).days


def test_scan_fleet_finds_failures(dataset):
    tmp_path, raw, _ = dataset
    fleet = D.scan_fleet(raw, max_drives=1000, seed=42)
    failing = [s for s, i in fleet.items() if i.fail_date is not None]
    # 40 healthy + 4 failing, all 4 failing drives detected with the right date
    assert len(fleet) == 44
    assert len(failing) == 4
    for s in failing:
        info = fleet[s]
        assert info.fail_date == date(2024, 1, 1) + timedelta(days=FAIL_DAY - 1)
        assert info.capacity_bytes == 1_000_000_000_000


def test_scan_fleet_caps_healthy(tmp_path):
    raw = make_synthetic_dataset(tmp_path, n_healthy=200, n_failing=2)
    fleet = D.scan_fleet(raw, max_drives=50, seed=1)
    # 2 failing always kept; healthy sampled down to 48
    n_fail = sum(1 for i in fleet.values() if i.fail_date is not None)
    assert n_fail == 2
    assert len(fleet) == 50


def test_detect_attrs(dataset):
    tmp_path, raw, _ = dataset
    attrs = D.detect_attrs(raw, threshold=0.99)
    assert attrs == ATTRS


def test_plan_windows_failing_drive(dataset):
    tmp_path, raw, cfg = dataset
    fleet = D.scan_fleet(raw, cfg.data.max_drives, cfg.data.seed)
    train, lead = D.plan_windows(fleet, 7, 7, [1, 3, 7, 14, 30], seed=42)
    fail_serial = next(s for s in fleet if fleet[s].fail_date is not None)
    fail_date = fleet[fail_serial].fail_date
    assert fail_date is not None
    fd = D.to_day(fail_date)
    ends = sorted(p.end_day for p in train[fail_serial])
    assert ends == list(range(fd - 7, fd))  # 1..7 days before failure
    lead_ends = sorted(p.end_day for p in lead[fail_serial])
    assert lead_ends == [fd - 30, fd - 14, fd - 7, fd - 3, fd - 1]


def test_plan_windows_healthy_drive(dataset):
    tmp_path, raw, cfg = dataset
    fleet = D.scan_fleet(raw, cfg.data.max_drives, cfg.data.seed)
    train, lead = D.plan_windows(fleet, 7, 7, [1, 3, 7, 14, 30], seed=42)
    healthy = [s for s, i in fleet.items() if i.fail_date is None]
    assert healthy
    s = healthy[0]
    assert len(train[s]) == 1
    assert train[s][0].label == 0
    end = train[s][0].end_day
    lo = D.to_day(fleet[s].first_date) + 7
    hi = D.to_day(fleet[s].last_date)
    assert lo <= end <= hi
    assert lead[s] == []


def test_load_series_window_range(dataset):
    tmp_path, raw, cfg = dataset
    fleet = D.scan_fleet(raw, cfg.data.max_drives, cfg.data.seed)
    train, lead = D.plan_windows(fleet, 7, 7, [1, 3, 7, 14, 30], seed=42)
    series, attrs = D.load_series(
        raw, fleet, train, lead, ATTRS, 0.99, window_days=7
    )
    assert attrs == ATTRS
    assert set(series) == set(fleet)
    fail_serial = next(s for s in fleet if fleet[s].fail_date is not None)
    fail_serial = next(s for s in fleet if fleet[s].fail_date is not None)
    fail_date = fleet[fail_serial].fail_date
    assert fail_date is not None
    fd = D.to_day(fail_date)
    days, vals = series[fail_serial]
    # days cover [fd-42, fd-1]: longest lead-time window (30) + 2x-window margin
    assert days.min() == fd - 42
    assert days.max() == fd - 1
    assert vals.shape == (len(days), len(ATTRS))
    assert vals.dtype == np.float32

    # healthy drives keep a 2x-window margin too, so a sample sliced from the
    # series can be re-planned offline (demo path) without losing windows
    healthy = [s for s, i in fleet.items() if i.fail_date is None]
    s = healthy[0]
    h_days, _ = series[s]
    end = train[s][0].end_day
    assert h_days.max() == end
    assert h_days.min() >= end - 12  # margin, clipped only by dataset start
    assert len(h_days) >= 8          # enough history for a re-plan


def test_collect_windows_labels(dataset):
    tmp_path, raw, cfg = dataset
    fleet = D.scan_fleet(raw, cfg.data.max_drives, cfg.data.seed)
    train, lead = D.plan_windows(fleet, 7, 7, [1, 3, 7, 14, 30], seed=42)
    series, _ = D.load_series(raw, fleet, train, lead, ATTRS, 0.99, window_days=7)
    records = D.collect_windows(series, train, 7, 3)
    labels = {r.label for r in records}
    assert labels == {0, 1}
    n_fail_windows = sum(1 for r in records if r.label == 1)
    # 4 failing drives x 7 horizons
    assert n_fail_windows == 4 * 7
    for r in records:
        assert len(r.days) >= 3
        assert r.values.shape[1] == len(ATTRS)
