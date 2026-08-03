"""Model training, evaluation, and persistence tests (hermetic, tiny data)."""
from __future__ import annotations

import numpy as np
import pytest

from exoplanet_classifier.config import ModelConfig
from exoplanet_classifier.data import load_light_curves
from exoplanet_classifier.model import (
    ModelError,
    balanced_sample_weights,
    load_metrics,
    load_model,
    predict,
    save_metrics,
    save_model,
    staged_validation_auc,
    train_pipeline,
)


def _small_cfg(tmp_path):
    from exoplanet_classifier.config import (
        Config,
        DataConfig,
        FeaturesConfig,
        PathsConfig,
        SplitConfig,
    )

    return Config(
        data=DataConfig(raw_dir=tmp_path / "raw", samples_dir=tmp_path / "samples"),
        split=SplitConfig(test_size=0.25, random_state=42),
        features=FeaturesConfig(),
        model=ModelConfig(n_estimators=30, max_depth=3, learning_rate=0.1, cv_folds=3),
        paths=PathsConfig(
            model_path=tmp_path / "model.joblib",
            report_path=tmp_path / "report.html",
            metrics_path=tmp_path / "metrics.json",
            feature_train=tmp_path / "features_train.csv",
            feature_val=tmp_path / "features_val.csv",
            feature_test=tmp_path / "features_test.csv",
            raw_sample=tmp_path / "raw_sample.csv",
            predictions_path=tmp_path / "predictions.csv",
        ),
    )


def _features_from_csv(path, features_cfg):
    from exoplanet_classifier.data import build_feature_frame

    flux, y = load_light_curves(path)
    df = build_feature_frame(flux, y, features_cfg)
    names = [c for c in df.columns if c != "label"]
    return df[names].to_numpy(dtype=float), y, names


def test_balanced_weights():
    y = np.array([1, 1, 0, 0, 0, 0])
    w = balanced_sample_weights(y)
    assert abs(float(w.sum()) - 6.0) < 1e-9
    assert w[0] > w[2]  # minority class weighs more


def test_balanced_weights_single_class():
    with pytest.raises(ModelError):
        balanced_sample_weights(np.array([0, 0, 0]))


def test_train_pipeline_on_separable_data(tmp_path, separable_curves_csv):
    cfg = _small_cfg(tmp_path)
    X, y, names = _features_from_csv(separable_curves_csv, cfg.features)
    X_tr, X_va, y_tr, y_va = X[:80], X[80:100], y[:80], y[80:100]
    X_te, y_te = X[100:], y[100:]
    metrics, artifacts = train_pipeline(
        X_tr, y_tr, cfg, X_val=X_va, y_val=y_va, X_test=X_te, y_test=y_te,
        feature_names=names,
    )
    assert metrics["chosen_model"] in ("logistic_regression", "gradient_boosting")
    assert metrics["cv_roc_auc_mean"] > 0.7
    assert metrics["train_size"] == 80
    assert metrics["validation"]["roc_auc"] > 0.8
    assert metrics["test"]["roc_auc"] > 0.8
    assert 0.0 <= metrics["test"]["pr_auc"] <= 1.0
    assert 0.0 <= metrics["test"]["precision"] <= 1.0
    cm = metrics["test"]["confusion"]
    assert cm["tn"] + cm["fp"] + cm["fn"] + cm["tp"] == 20
    assert metrics["top_features"][0]["feature"] in names
    assert len(metrics["top_features"]) <= 10
    for key in ("scaler", "model", "kind", "feature_names", "threshold"):
        assert key in artifacts
    assert artifacts["feature_names"] == names


def test_staged_validation_auc_records_curve(tmp_path, separable_curves_csv):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    cfg = _small_cfg(tmp_path)
    X, y, names = _features_from_csv(separable_curves_csv, cfg.features)
    X_tr, X_va, y_tr, y_va = X[:80], X[80:100], y[:80], y[80:100]
    scaler = StandardScaler().fit(X_tr)
    model = GradientBoostingClassifier(
        n_estimators=30, max_depth=3, learning_rate=0.1, random_state=42
    )
    model.fit(scaler.transform(X_tr), y_tr)
    curve = staged_validation_auc(model, scaler.transform(X_va), y_va)
    assert curve and len(curve) >= 2
    assert curve[0]["iteration"] == 1
    assert curve[-1]["iteration"] == cfg.model.n_estimators
    assert all(0.0 <= p["val_roc_auc"] <= 1.0 for p in curve)
    final_auc = roc_auc_score(y_va, model.predict_proba(scaler.transform(X_va))[:, 1])
    assert abs(curve[-1]["val_roc_auc"] - final_auc) < 1e-3
    # monotone step size: points at 1, 10, 20, 30
    assert [p["iteration"] for p in curve] == [1, 10, 20, 30]


def test_staged_validation_auc_skips_non_boosting(tmp_path, separable_curves_csv):
    from sklearn.linear_model import LogisticRegression

    cfg = _small_cfg(tmp_path)
    X, y, names = _features_from_csv(separable_curves_csv, cfg.features)
    model = LogisticRegression(max_iter=500)
    model.fit(X[:80], y[:80])
    assert staged_validation_auc(model, X[80:100], y[80:100]) == []


def test_train_pipeline_single_class_fails(tmp_path, synthetic_curves_csv):
    cfg = _small_cfg(tmp_path)
    X, y, names = _features_from_csv(synthetic_curves_csv, cfg.features)
    X, y = X[:20], np.zeros(20, dtype=int)  # all non-exoplanet
    with pytest.raises(ModelError):
        train_pipeline(X, y, cfg, feature_names=names)


def test_save_load_model_roundtrip(tmp_path, separable_curves_csv):
    cfg = _small_cfg(tmp_path)
    X, y, names = _features_from_csv(separable_curves_csv, cfg.features)
    X_tr, y_tr = X[:90], y[:90]
    _, artifacts = train_pipeline(X_tr, y_tr, cfg, feature_names=names)
    path = tmp_path / "model.joblib"
    save_model(artifacts, path)
    loaded = load_model(path)
    p1 = predict(artifacts, X[90:100])
    p2 = predict(loaded, X[90:100])
    assert np.allclose(p1, p2)


def test_load_model_missing(tmp_path):
    with pytest.raises(ModelError):
        load_model(tmp_path / "nope.joblib")


def test_predict_probability_range(tmp_path, separable_curves_csv):
    cfg = _small_cfg(tmp_path)
    X, y, names = _features_from_csv(separable_curves_csv, cfg.features)
    _, artifacts = train_pipeline(X[:90], y[:90], cfg, feature_names=names)
    proba = predict(artifacts, X[90:100])
    assert proba.shape == (10,)
    assert np.all((proba >= 0.0) & (proba <= 1.0))


def test_metrics_roundtrip(tmp_path):
    metrics = {"chosen_model": "gradient_boosting", "cv_roc_auc_mean": 0.95}
    path = tmp_path / "metrics.json"
    save_metrics(metrics, path)
    assert load_metrics(path) == metrics


def test_metrics_missing(tmp_path):
    with pytest.raises(ModelError):
        load_metrics(tmp_path / "nope.json")
