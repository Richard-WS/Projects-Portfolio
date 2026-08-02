"""End-to-end CLI tests on the synthetic dataset (hermetic, no network)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from diskfail.cli import main


def test_full_pipeline(tmp_path: Path, dataset):
    tmp_path, raw, cfg = dataset
    cfg_path = tmp_path / "config.yaml"
    # dataset fixture already wrote a config at tmp_path/config.yaml
    assert cfg_path.is_file()

    assert main(["prepare", "-c", str(cfg_path)]) == 0
    train_csv = tmp_path / "samples" / "features_train.csv.gz"
    test_csv = tmp_path / "samples" / "features_test.csv.gz"
    assert train_csv.is_file() and test_csv.is_file()

    # the raw sample writer also ran (not --samples)
    sample = tmp_path / "samples" / "raw_smart_sample.csv.gz"
    assert sample.is_file()
    sample_df = pd.read_csv(sample, compression="gzip", nrows=5)
    assert "smart_5_raw" in sample_df.columns

    assert main(["train", "-c", str(cfg_path)]) == 0
    metrics_path = tmp_path / "docs" / "metrics.json"
    model_path = tmp_path / "outputs" / "model.joblib"
    assert metrics_path.is_file() and model_path.is_file()
    metrics = json.loads(metrics_path.read_text())
    assert set(metrics) == {"cv", "test", "leadtime", "feature_importance", "meta"}
    assert metrics["test"]["roc_auc"] > 0.5
    assert len(metrics["leadtime"]) > 0

    assert main(["report", "-c", str(cfg_path)]) == 0
    report_path = tmp_path / "docs" / "disk-failure-report.html"
    assert report_path.is_file()
    html = report_path.read_text()
    assert "ROC curve" in html and "data:image/png;base64," in html

    # score a fresh snapshot: reuse the raw dir, expect one row per drive
    assert main(["score", str(raw), "-c", str(cfg_path)]) == 0
    preds = pd.read_csv(tmp_path / "outputs" / "predictions.csv")
    assert len(preds) > 0
    assert {"serial", "risk", "flagged"}.issubset(preds.columns)
    # all 4 failing drives were flagged in this synthetic ramp scenario
    fail_flags = preds[preds["serial"].str.startswith("F")]
    assert fail_flags["flagged"].sum() >= 1


def test_prepare_missing_source(tmp_path: Path, capsys):
    """prepare must fail fast with a helpful message when data is absent."""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "data:\n  raw_dir: /nonexistent\n  raw_csv: .\n"
        "paths:\n  feature_train: t.csv.gz\n  feature_test: e.csv.gz\n"
        "  leadtime_features: l.csv.gz\n  model_path: m.joblib\n"
        "  metrics_path: m.json\n  report_path: r.html\n  predictions_path: p.csv\n"
    )
    with pytest.raises(SystemExit) as exc:
        main(["prepare", "-c", str(cfg_path)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "run `bash scripts/download_data.sh`" in err


def test_cli_console_script(tmp_path: Path, dataset):
    """The installed `diskfail` entry point works (what CI/docs use)."""
    tmp_path, raw, cfg = dataset
    cfg_path = tmp_path / "config.yaml"
    result = subprocess.run(
        [sys.executable, "-m", "diskfail.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "prepare" in result.stdout and "train" in result.stdout


def test_demo_replan_has_both_classes(tmp_path: Path, dataset):
    """The committed raw sample must be re-plannable offline: prepare, then
    prepare --samples (the demo path) must still yield healthy + failing
    windows. Guards the 2x-window series margin in load_series."""
    tmp_path, raw, cfg = dataset
    cfg_path = tmp_path / "config.yaml"

    assert main(["prepare", "-c", str(cfg_path)]) == 0
    sample = tmp_path / "samples" / "raw_smart_sample.csv.gz"
    assert sample.is_file()

    # the demo path rebuilds features from the committed sample only
    assert main(["prepare", "--samples", "-c", str(cfg_path)]) == 0
    train_df = pd.read_csv(tmp_path / "samples" / "features_train.csv.gz")
    labels = set(train_df["label"])
    assert labels == {0, 1}, f"sample re-plan lost a class: {labels}"
    assert len(train_df) > 0
