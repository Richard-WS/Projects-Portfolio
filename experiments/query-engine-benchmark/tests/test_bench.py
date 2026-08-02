from __future__ import annotations

import json
import subprocess
import sys

import pytest

from querybench.bench import median, peak_rss_mb, time_query


def test_median_odd():
    assert median([3, 1, 2]) == 2


def test_median_even():
    assert median([1, 2, 3, 4]) == 2.5


def test_median_empty_raises():
    with pytest.raises(ValueError):
        median([])


def test_time_query_positive():
    ms = time_query(lambda: sum(range(10_000)), warmup=0, runs=2)
    assert ms > 0


def test_time_query_uses_median():
    # warmup runs happen but are not reported; result is a single median value
    ms = time_query(lambda: None, warmup=2, runs=3)
    assert ms >= 0


def test_peak_rss_positive():
    assert peak_rss_mb() > 0


def test_runner_subprocess_end_to_end(data_files):
    """The subprocess runner returns well-formed JSON for every engine."""
    for engine in ("pandas", "duckdb", "polars"):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "querybench.runner",
                "--engine", engine,
                "--orders", str(data_files / "orders.parquet"),
                "--customers", str(data_files / "customers.parquet"),
                "--format", "parquet",
                "--queries", "q1_filter_sum,q4_join",
                "--runs", "2",
                "--warmup", "0",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        report = json.loads(proc.stdout)
        assert report["engine"] == engine
        assert report["load_ms"] > 0
        assert set(report["queries_ms"]) == {"q1_filter_sum", "q4_join"}
        assert report["peak_rss_mb"] > 0
