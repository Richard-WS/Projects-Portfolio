from __future__ import annotations

import pytest

from querybench.config import (
    DEFAULT_QUERIES,
    DatasetConfig,
    BenchmarkConfig,
    coerce_scalar,
    load_config,
)


def test_coerce_scalar():
    assert coerce_scalar("5_000_000") == 5_000_000
    assert coerce_scalar("3e-4") == 0.0003
    assert coerce_scalar("42") == 42
    assert coerce_scalar("parquet") == "parquet"
    assert coerce_scalar(7) == 7
    assert coerce_scalar(None) is None


def test_default_queries_filled_when_missing(tmp_path):
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text("dataset:\n  n_orders: 1000\n")
    cfg = load_config(cfg_file)
    assert cfg.queries == DEFAULT_QUERIES


def test_string_numbers_coerced_in_yaml(tmp_path):
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text("dataset:\n  n_orders: '1000'\n  n_customers: '20'\n  seed: '3'\n  format: csv\nruns: '2'\nwarmup: '0'\n")
    cfg = load_config(cfg_file)
    assert cfg.dataset.n_orders == 1000
    assert cfg.dataset.n_customers == 20
    assert cfg.dataset.seed == 3
    assert cfg.dataset.format == "csv"
    assert cfg.runs == 2
    assert cfg.warmup == 0


def test_validation_errors():
    with pytest.raises(ValueError):
        BenchmarkConfig(dataset=DatasetConfig(n_orders=10)).validate()
    with pytest.raises(ValueError):
        BenchmarkConfig(dataset=DatasetConfig(format="json")).validate()
    with pytest.raises(ValueError):
        BenchmarkConfig(queries=["nope"]).validate()
    with pytest.raises(ValueError):
        BenchmarkConfig(runs=0).validate()
    assert BenchmarkConfig().queries == DEFAULT_QUERIES
