"""Config loading, path resolution and validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from diskfail.config import Config, ConfigError


def test_load_resolves_paths(dataset):
    tmp_path, raw, cfg = dataset
    assert (cfg.paths.feature_train) == str(tmp_path / "samples" / "features_train.csv.gz")
    assert cfg.raw_csv_path().is_dir()  # points at the synthetic raw dir
    assert cfg.data.max_drives == 1000
    assert cfg.model.cv_folds == 3


def test_missing_config_file(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        Config.load(tmp_path / "nope.yaml")


def test_unknown_keys_rejected(tmp_path: Path, dataset):
    tmp_path, raw, _ = dataset
    # write a config with a bogus top-level key and expect a ConfigError
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        f"data:\n  raw_dir: {raw}\n  raw_csv: .\n  max_drives: 100\n"
        "bogus_section:\n  x: 1\n"
        "paths:\n  feature_train: out.csv\n  feature_test: out2.csv\n"
        "  leadtime_features: out3.csv\n  model_path: m.joblib\n"
        "  metrics_path: m.json\n  report_path: r.html\n  predictions_path: p.csv\n"
    )
    with pytest.raises(ConfigError, match="unknown config keys"):
        Config.load(bad)


def test_invalid_split_size_rejected(tmp_path: Path, dataset):
    tmp_path, raw, _ = dataset
    bad = tmp_path / "bad2.yaml"
    bad.write_text(
        f"data:\n  raw_dir: {raw}\n  raw_csv: .\n  max_drives: 100\n"
        "split:\n  test_size: 1.5\n"
        "paths:\n  feature_train: out.csv\n  feature_test: out2.csv\n"
        "  leadtime_features: out3.csv\n  model_path: m.joblib\n"
        "  metrics_path: m.json\n  report_path: r.html\n  predictions_path: p.csv\n"
    )
    with pytest.raises(ConfigError, match="test_size"):
        Config.load(bad)
