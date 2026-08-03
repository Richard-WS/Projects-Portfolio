"""Report generation tests: text summary, HTML structure, escaping, images."""
from __future__ import annotations

import base64

from exoplanet_classifier.config import Config, DataConfig, FeaturesConfig, ModelConfig, PathsConfig, SplitConfig
from exoplanet_classifier.data import build_feature_frame, load_light_curves
from exoplanet_classifier.model import train_pipeline
from exoplanet_classifier.report import build_html_report, render_text, write_report


def _trained(tmp_path, separable_curves_csv):
    cfg = Config(
        data=DataConfig(raw_dir=tmp_path / "raw", samples_dir=tmp_path / "samples", raw_sample_rows=8),
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
    flux, y = load_light_curves(separable_curves_csv)
    df = build_feature_frame(flux, y, cfg.features)
    names = [c for c in df.columns if c != "label"]
    X = df[names].to_numpy(dtype=float)
    metrics, artifacts = train_pipeline(
        X[:80], y[:80], cfg, X_val=X[80:100], y_val=y[80:100],
        X_test=X[100:], y_test=y[100:], feature_names=names,
    )
    return cfg, metrics, artifacts


def _persist_artifacts(tmp_path, cfg, separable_curves_csv):
    """Write the feature matrices + raw sample so the report can recompute
    curves exactly like a real `train` run."""
    import pandas as pd

    flux, y = load_light_curves(separable_curves_csv)
    df = build_feature_frame(flux, y, cfg.features)
    df.iloc[:80].to_csv(cfg.paths.feature_train, index=False)
    df.iloc[80:100].to_csv(cfg.paths.feature_val, index=False)
    df.iloc[100:].to_csv(cfg.paths.feature_test, index=False)
    sample = pd.DataFrame(flux[:4])
    sample.insert(0, "label", y[:4] + 1)
    sample.to_csv(cfg.paths.raw_sample, index=False)


def test_render_text_contains_key_results():
    metrics = {
        "chosen_model": "gradient_boosting",
        "cv_roc_auc_mean": 0.93,
        "cv_roc_auc_std": 0.02,
        "cv_folds": 5,
        "validation": {"roc_auc": 0.9, "pr_auc": 0.8, "precision": 0.8, "recall": 0.7,
                       "f1": 0.75, "confusion": {"tn": 1, "fp": 1, "fn": 1, "tp": 1}},
        "test": {"roc_auc": 0.95, "pr_auc": 0.85, "precision": 0.9, "recall": 0.8,
                 "f1": 0.85, "confusion": {"tn": 2, "fp": 1, "fn": 1, "tp": 3}},
        "top_features": [{"feature": "deepest_dip", "importance": 0.5}],
    }
    text = render_text(metrics)
    assert "gradient_boosting" in text
    assert "0.93 +/- 0.02" in text
    assert "ROC-AUC" in text and "TN 2" in text and "deepest_dip" in text


def test_html_report_full(tmp_path, separable_curves_csv):
    cfg, metrics, artifacts = _trained(tmp_path, separable_curves_csv)
    _persist_artifacts(tmp_path, cfg, separable_curves_csv)
    html = build_html_report(cfg, metrics, artifacts)
    assert "<title>Exoplanet transit classifier — results</title>" in html
    assert metrics["chosen_model"] in html  # whatever won the comparison
    assert "ROC-AUC" in html
    assert "$" not in html  # no Template placeholders left behind
    # roc, pr, importance, sample light curves (+ training curve if boosting won)
    expected = 5 if metrics.get("training_curve") else 4
    assert html.count("data:image/png;base64,") == expected
    for part in html.split("data:image/png;base64,")[1:]:
        b64 = part.split('"')[0]
        assert base64.b64decode(b64)[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic


def test_html_report_training_curve_section(tmp_path, separable_curves_csv):
    cfg, metrics, artifacts = _trained(tmp_path, separable_curves_csv)
    metrics["training_curve"] = [
        {"iteration": 1, "val_roc_auc": 0.60},
        {"iteration": 15, "val_roc_auc": 0.85},
        {"iteration": 30, "val_roc_auc": 0.92},
    ]
    _persist_artifacts(tmp_path, cfg, separable_curves_csv)
    html = build_html_report(cfg, metrics, artifacts)
    assert "Training curve" in html
    assert "Validation ROC-AUC during training" in html
    assert html.count("data:image/png;base64,") == 5


def test_html_escapes_text(tmp_path, separable_curves_csv):
    cfg, metrics, artifacts = _trained(tmp_path, separable_curves_csv)
    metrics["chosen_model"] = "<gradient_boosting>"
    html = build_html_report(cfg, metrics, artifacts)
    assert "&lt;gradient_boosting&gt;" in html
    assert "<gradient_boosting>" not in html


def test_write_report_creates_file(tmp_path, separable_curves_csv):
    cfg, metrics, artifacts = _trained(tmp_path, separable_curves_csv)
    out = tmp_path / "docs" / "report.html"
    write_report(cfg, metrics, artifacts, out)
    assert out.is_file()
    assert "Exoplanet transit classifier" in out.read_text(encoding="utf-8")


def test_html_report_minimal_metrics(tmp_path):
    cfg = Config(
        data=DataConfig(raw_dir=tmp_path / "raw", samples_dir=tmp_path / "samples"),
        split=SplitConfig(),
        features=FeaturesConfig(),
        model=ModelConfig(),
        paths=PathsConfig(report_path=tmp_path / "report.html", raw_sample=tmp_path / "none.csv"),
    )
    metrics = {
        "chosen_model": "logistic_regression",
        "cv_roc_auc_mean": 0.8,
        "cv_roc_auc_std": 0.05,
        "cv_folds": 5,
        "train_size": 100,
        "top_features": [{"feature": "bin_00", "importance": 0.1}],
        "importance_source": "logistic_regression",
    }
    artifacts = {"scaler": None, "model": None, "kind": "logistic_regression",
                 "feature_names": [], "threshold": 0.5}
    html = build_html_report(cfg, metrics, artifacts)
    assert "No test split scored" in html
    assert html.count("data:image/png;base64,") == 1  # importance only
