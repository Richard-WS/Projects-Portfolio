"""CLI tests: subprocess runs of `python -m exoplanet_classifier`."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.conftest import make_curve_csv

PROJECT = Path(__file__).resolve().parents[1]


def _run(*args, cwd=PROJECT, timeout=120):
    return subprocess.run(
        [sys.executable, "-m", "exoplanet_classifier", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
    )


def _config_yaml(tmp_path, raw_dir):
    """Config with absolute tmp paths + tiny model params for fast runs."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"data:\n"
        f"  raw_dir: {raw_dir}\n"
        f"  raw_train: exoTrain.csv\n"
        f"  raw_test: exoTest.csv\n"
        f"  samples_dir: {tmp_path}/samples\n"
        f"  raw_sample_rows: 8\n"
        f"split:\n"
        f"  test_size: 0.25\n"
        f"  random_state: 42\n"
        f"features:\n"
        f"  detrend_window: 64\n"
        f"  dip_threshold_mad: 3.0\n"
        f"  autocorr_max_lag: 50\n"
        f"model:\n"
        f"  n_estimators: 30\n"
        f"  max_depth: 3\n"
        f"  learning_rate: 0.1\n"
        f"  cv_folds: 3\n"
        f"paths:\n"
        f"  model_path: {tmp_path}/outputs/model.joblib\n"
        f"  report_path: {tmp_path}/docs/report.html\n"
        f"  metrics_path: {tmp_path}/docs/metrics.json\n"
        f"  feature_train: {tmp_path}/samples/features_train.csv\n"
        f"  feature_val: {tmp_path}/samples/features_val.csv\n"
        f"  feature_test: {tmp_path}/samples/features_test.csv\n"
        f"  raw_sample: {tmp_path}/samples/raw_sample.csv\n"
        f"  predictions_path: {tmp_path}/outputs/predictions.csv\n",
        encoding="utf-8",
    )
    return cfg


def test_help():
    proc = _run("--help")
    assert proc.returncode == 0
    for cmd in ("prepare", "train", "predict", "report"):
        assert cmd in proc.stdout


def test_version():
    proc = _run("--version")
    assert proc.returncode == 0
    assert "0.1.0" in proc.stdout


def test_prepare_writes_artifacts(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=40, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=12, transit_frac=0.5)
    config = _config_yaml(tmp_path, raw)
    proc = _run("prepare", "-c", str(config))
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "samples" / "features_train.csv").is_file()
    assert (tmp_path / "samples" / "features_test.csv").is_file()
    assert (tmp_path / "samples" / "raw_sample.csv").is_file()


def test_train_end_to_end(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=80, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=20, transit_frac=0.5)
    config = _config_yaml(tmp_path, raw)
    assert _run("prepare", "-c", str(config)).returncode == 0
    proc = _run("train", "-c", str(config))
    assert proc.returncode == 0, proc.stderr
    assert "chosen model" in proc.stdout
    assert (tmp_path / "outputs" / "model.joblib").is_file()
    assert (tmp_path / "docs" / "metrics.json").is_file()
    assert (tmp_path / "docs" / "report.html").is_file()


def test_train_missing_features_exits_2(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=40, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=12, transit_frac=0.5)
    config = _config_yaml(tmp_path, raw)
    proc = _run("train", "-c", str(config))
    assert proc.returncode == 2
    assert "feature matrix not found" in proc.stderr


def test_predict_writes_predictions(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=80, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=20, transit_frac=0.5)
    config = _config_yaml(tmp_path, raw)
    _run("prepare", "-c", str(config))
    _run("train", "-c", str(config), "--no-report")
    curves = tmp_path / "new_curves.csv"
    make_curve_csv(curves, n_curves=6, transit_frac=0.5)
    out = tmp_path / "predictions.csv"
    proc = _run("predict", "-c", str(config), str(curves), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert len(content.strip().splitlines()) == 7  # header + 6 rows
    assert "probability_exoplanet" in content


def test_report_from_saved_metrics(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=80, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=20, transit_frac=0.5)
    config = _config_yaml(tmp_path, raw)
    _run("prepare", "-c", str(config))
    _run("train", "-c", str(config))
    proc = _run("report", "-c", str(config))
    assert proc.returncode == 0, proc.stderr
    assert "wrote HTML report" in proc.stdout


def test_bad_config_exits_2(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("data: [", encoding="utf-8")
    proc = _run("prepare", "-c", str(path))
    assert proc.returncode == 2
    assert "error:" in proc.stderr


def test_missing_config_exits_2(tmp_path):
    proc = _run("train", "-c", str(tmp_path / "nope.yaml"))
    assert proc.returncode == 2
    assert "config file not found" in proc.stderr


def test_config_flag_before_and_after_subcommand(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=40, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=12, transit_frac=0.5)
    config = _config_yaml(tmp_path, raw)
    before = _run("-c", str(config), "prepare")
    after = _run("prepare", "-c", str(config))
    assert before.returncode == 0, before.stderr
    assert after.returncode == 0, after.stderr
