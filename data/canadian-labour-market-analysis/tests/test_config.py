"""Config loader tests."""
from __future__ import annotations

import pytest

from canlab.config import DEFAULT_QUERIES, coerce_scalar, load_config

from conftest import ROOT


def test_example_config_loads():
    cfg = load_config(ROOT / "configs" / "example.yaml")
    assert cfg.paths.sql_dir == (ROOT / "sql").resolve()
    assert cfg.paths.raw_dir == (ROOT / "data" / "raw").resolve()
    assert cfg.paths.db_path == (ROOT / "data" / "canlab.db").resolve()


def test_example_config_full_catalog():
    cfg = load_config(ROOT / "configs" / "example.yaml")
    assert cfg.queries == DEFAULT_QUERIES
    assert len(cfg.queries) == 14
    assert cfg.latest_year == 2025


def test_config_paths_resolve_against_config_dir(tmp_path):
    sql = tmp_path / "sql"
    sql.mkdir()
    config = tmp_path / "nested" / "config.yaml"
    config.parent.mkdir()
    config.write_text(
        "paths:\n  raw_dir: ../data/raw\n  sql_dir: ../sql\n",
        encoding="utf-8",
    )
    cfg = load_config(config)
    assert cfg.paths.raw_dir == (tmp_path / "data" / "raw").resolve()
    assert cfg.paths.sql_dir == sql.resolve()


def test_numeric_strings_coerced(tmp_path):
    sql = tmp_path / "sql"
    sql.mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(
        "sources:\n  labour_force_product_id: \"14100327\"\n"
        "paths:\n  sql_dir: sql\nlatest_year: \"2025\"\n",
        encoding="utf-8",
    )
    cfg = load_config(config)
    assert cfg.sources.labour_force_product_id == 14100327
    assert isinstance(cfg.sources.labour_force_product_id, int)
    assert cfg.latest_year == 2025


def test_missing_sql_dir_raises(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("paths:\n  sql_dir: does-not-exist\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_config(config)


def test_coerce_scalar():
    assert coerce_scalar("42") == 42
    assert coerce_scalar("3e-4") == 0.0003
    assert coerce_scalar("1_000") == 1000
    assert coerce_scalar("abc") == "abc"
    assert coerce_scalar(7) == 7
    assert coerce_scalar(None) is None
