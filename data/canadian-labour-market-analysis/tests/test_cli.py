"""CLI integration tests: build, query, run-all, samples end to end."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from canlab.cli import main

from conftest import SQL_DIR, make_labour_csv, make_population_csv


def _write_config(tmp_path: Path, raw_dir: Path) -> Path:
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
sources:
  labour_force_product_id: 14100327
  population_product_id: 17100005
paths:
  raw_dir: {raw_dir}
  db_path: out/canlab.db
  sql_dir: {SQL_DIR}
  samples_dir: samples
queries:
  - q01_unemployment_national
  - q02_unemployment_by_province_latest
  - q08_nb_vs_canada_unemployment
  - q10_employment_per_working_age
""",
        encoding="utf-8",
    )
    return config


def test_build_then_query(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_labour_csv(raw / "14100327.csv")
    make_population_csv(raw / "17100005.csv")
    config = _write_config(tmp_path, raw)

    assert main(["--config", str(config), "build"]) == 0
    db_path = tmp_path / "out" / "canlab.db"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM labour_force").fetchone()[0] > 0

    assert main(["--config", str(config), "query", "q01_unemployment_national"]) == 0


def test_query_csv_output(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_labour_csv(raw / "14100327.csv")
    make_population_csv(raw / "17100005.csv")
    config = _write_config(tmp_path, raw)
    main(["--config", str(config), "build"])
    capsys.readouterr()  # drain the build output

    assert main(["--config", str(config), "query", "q01_unemployment_national", "--out", "csv"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("ref_year,")


def test_unknown_query_exits_nonzero(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_labour_csv(raw / "14100327.csv")
    make_population_csv(raw / "17100005.csv")
    config = _write_config(tmp_path, raw)
    main(["--config", str(config), "build"])
    with pytest.raises(SystemExit) as exc:
        main(["--config", str(config), "query", "q99_nope"])
    assert exc.value.code != 0


def test_run_all_writes_result_files(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_labour_csv(raw / "14100327.csv")
    make_population_csv(raw / "17100005.csv")
    config = _write_config(tmp_path, raw)
    main(["--config", str(config), "build"])

    assert main(["--config", str(config), "run-all"]) == 0
    results = tmp_path / "docs" / "results"
    names = {p.name for p in results.glob("*.csv")}
    assert {"q01_unemployment_national.csv", "q02_unemployment_by_province_latest.csv",
            "q08_nb_vs_canada_unemployment.csv", "q10_employment_per_working_age.csv"} <= names


def test_samples_then_build_from_samples(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_labour_csv(raw / "14100327.csv")
    make_population_csv(raw / "17100005.csv")
    config = _write_config(tmp_path, raw)

    assert main(["--config", str(config), "samples"]) == 0
    samples_dir = tmp_path / "samples"
    assert (samples_dir / "regions.csv").exists()
    assert (samples_dir / "labour_force_sample.csv").exists()
    assert (samples_dir / "population_sample.csv").exists()

    # A demo build from the committed samples alone (no raw CSVs).
    assert main(["--config", str(config), "build", "--samples"]) == 0
    db_path = tmp_path / "out" / "canlab.db"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0] > 0


def test_query_without_database_fails(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    config = _write_config(tmp_path, raw)
    with pytest.raises(SystemExit) as exc:
        main(["--config", str(config), "query", "q01_unemployment_national"])
    assert "database not found" in str(exc.value)
