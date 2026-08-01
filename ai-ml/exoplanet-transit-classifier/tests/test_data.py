"""Data loading and preparation tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from exoplanet_classifier.config import (
    Config,
    DataConfig,
    FeaturesConfig,
    ModelConfig,
    PathsConfig,
    SplitConfig,
)
from exoplanet_classifier.data import (
    DataError,
    build_feature_frame,
    download_raw,
    load_features,
    load_light_curves,
    prepare,
    split_curves,
)
from tests.conftest import make_curve_csv


def _test_config(tmp_path, raw_dir=None):
    return Config(
        data=DataConfig(
            raw_dir=raw_dir or tmp_path / "raw",
            samples_dir=tmp_path / "samples",
            raw_url="http://127.0.0.1:9/",
            raw_sample_rows=8,
        ),
        split=SplitConfig(test_size=0.25, random_state=42),
        features=FeaturesConfig(detrend_window=64, dip_threshold_mad=3.0, autocorr_max_lag=50),
        model=ModelConfig(n_estimators=20, max_depth=2, learning_rate=0.1, cv_folds=3),
        paths=PathsConfig(
            model_path=tmp_path / "outputs" / "model.joblib",
            report_path=tmp_path / "docs" / "report.html",
            metrics_path=tmp_path / "docs" / "metrics.json",
            feature_train=tmp_path / "samples" / "features_train.csv",
            feature_val=tmp_path / "samples" / "features_val.csv",
            feature_test=tmp_path / "samples" / "features_test.csv",
            raw_sample=tmp_path / "samples" / "raw_sample.csv",
            predictions_path=tmp_path / "outputs" / "predictions.csv",
        ),
    )


def test_load_light_curves(synthetic_curves_csv):
    flux, y = load_light_curves(synthetic_curves_csv)
    assert flux.shape == (40, 2048)
    assert set(np.unique(y)) == {0, 1}
    assert int(y.sum()) == 20


def test_load_missing_file(tmp_path):
    with pytest.raises(DataError):
        load_light_curves(tmp_path / "nope.csv")


def test_load_bad_labels(tmp_path):
    df = pd.DataFrame([[3, 1.0, 1.0], [1, 1.0, 1.0]])
    path = tmp_path / "bad.csv"
    df.to_csv(path, index=False)
    with pytest.raises(DataError):
        load_light_curves(path)


def test_load_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("LABEL\n", encoding="utf-8")
    with pytest.raises(DataError):
        load_light_curves(path)


def test_split_is_stratified():
    flux = np.zeros((100, 32))
    y = np.array([1] * 10 + [0] * 90)
    f_tr, f_va, y_tr, y_va = split_curves(flux, y, 0.25, 42)
    assert f_tr.shape[0] == 75 and f_va.shape[0] == 25
    assert 0 < y_tr.sum() < 10 and 0 < y_va.sum() < 10


def test_build_feature_frame(synthetic_curves_csv):
    flux, y = load_light_curves(synthetic_curves_csv)
    df = build_feature_frame(flux[:4], y[:4], FeaturesConfig())
    assert df.shape[0] == 4
    assert "label" in df.columns
    assert df["label"].tolist() == y[:4].tolist()
    assert not df.drop(columns=["label"]).isna().any().any()


def test_prepare_writes_all_artifacts(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=40, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=12, transit_frac=0.5)
    cfg = _test_config(tmp_path, raw_dir=raw)
    counts = prepare(cfg)
    assert counts == {"train": 30, "val": 10, "test": 12}
    for key in ("feature_train", "feature_val", "feature_test", "raw_sample"):
        assert getattr(cfg.paths, key).is_file()


def test_load_features_roundtrip(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=40, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=12, transit_frac=0.5)
    cfg = _test_config(tmp_path, raw_dir=raw)
    prepare(cfg)
    X, y = load_features(cfg, "train")
    assert X.shape[0] == 30
    assert X.shape[1] == 50 + 20  # 50 autocorr lags + 11 stats + 5 dips + 2 periodicity + 2 fft
    assert y.shape == (30,)
    assert np.all(np.isfinite(X))


def test_load_features_missing(tmp_path):
    cfg = _test_config(tmp_path)
    with pytest.raises(DataError):
        load_features(cfg, "train")


def test_prepare_writes_gzip_when_configured(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_curve_csv(raw / "exoTrain.csv", n_curves=40, transit_frac=0.5)
    make_curve_csv(raw / "exoTest.csv", n_curves=12, transit_frac=0.5)
    cfg = _test_config(tmp_path, raw_dir=raw)
    cfg.paths.feature_train = tmp_path / "samples" / "features_train.csv.gz"
    cfg.paths.feature_val = tmp_path / "samples" / "features_val.csv.gz"
    cfg.paths.feature_test = tmp_path / "samples" / "features_test.csv.gz"
    prepare(cfg)
    assert (tmp_path / "samples" / "features_train.csv.gz").is_file()
    X, y = load_features(cfg, "train")
    assert X.shape == (30, 70)
    assert np.all(np.isfinite(X))


def test_download_raw_skips_existing(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in ("exoTrain.csv", "exoTest.csv"):
        (raw / name).write_text("already here", encoding="utf-8")
    cfg = _test_config(tmp_path, raw_dir=raw)
    download_raw(cfg)  # must not touch the network
    assert (raw / "exoTrain.csv").read_text(encoding="utf-8") == "already here"
    assert (raw / "exoTest.csv").read_text(encoding="utf-8") == "already here"
