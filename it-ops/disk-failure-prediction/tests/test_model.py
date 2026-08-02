"""Model training / evaluation tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from diskfail import data as D
from diskfail import features as F
from diskfail import model as M
from diskfail.config import ModelConfig
from tests.conftest import ATTRS


@pytest.fixture
def feature_frames(dataset):
    """Build train/test/leadtime feature frames from the synthetic data."""
    tmp_path, raw, cfg = dataset
    fleet = D.scan_fleet(raw, cfg.data.max_drives, cfg.data.seed)
    train, lead = D.plan_windows(fleet, 7, 7, [1, 3, 7, 14, 30], seed=42)
    series, attrs = D.load_series(raw, fleet, train, lead, ATTRS, 0.99, window_days=7)
    windows = D.collect_windows(series, train, 7, 3)
    lead_windows = D.collect_windows(series, lead, 7, 3)
    feat = F.build_feature_frame(windows, attrs, fleet)
    lead_feat = F.build_feature_frame(lead_windows, attrs, fleet)
    train_df, test_df = D.split_by_drive(feat, 0.2, seed=42)
    return train_df, test_df, lead_feat


def _cfg() -> ModelConfig:
    return ModelConfig(max_iter=20, learning_rate=0.1, min_samples_leaf=5,
                       l2_regularization=1.0, cv_folds=3)


def test_evaluate_counts():
    y = np.array([1, 1, 1, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.1, 0.2, 0.3, 0.05])
    m = M.evaluate(y, p, threshold=0.5)
    assert m["tp"] == 2
    assert m["fp"] == 0
    assert m["fn"] == 1
    assert m["tn"] == 3
    assert m["precision"] == pytest.approx(1.0)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(0.8)
    assert m["false_alarm_rate"] == pytest.approx(0.0)


def test_best_threshold_prefers_f1():
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.7, 0.2, 0.6, 0.55, 0.1, 0.05])
    th = M.best_threshold(y, p)
    assert 0.2 <= th <= 0.7


def test_cross_validate_grouped(feature_frames):
    train_df, _, _ = feature_frames
    X = train_df.drop(columns=["serial", "end_day", "label", "kind"])
    y = train_df["label"].astype(int)
    drives = train_df["serial"].astype(str)
    metrics, oof = M.cross_validate(X, y, drives, _cfg(), seed=42)
    assert set(metrics) == {"cv_roc_auc", "cv_pr_auc"}
    assert 0.0 <= metrics["cv_roc_auc"] <= 1.0
    assert oof.shape == (len(train_df),)
    assert np.all((oof >= 0) & (oof <= 1))


def test_train_model_and_evaluate(feature_frames):
    train_df, test_df, _ = feature_frames
    Xtr = train_df.drop(columns=["serial", "end_day", "label", "kind"])
    ytr = train_df["label"].astype(int)
    Xte = test_df.drop(columns=["serial", "end_day", "label", "kind"])
    yte = test_df["label"].astype(int)
    clf, cv, threshold = M.train_model(
        Xtr, ytr, train_df["serial"].astype(str), _cfg(), seed=42
    )
    proba = clf.predict_proba(Xte[clf.feature_names_in_])[:, 1]
    metrics = M.evaluate(yte.to_numpy(), proba, threshold)
    assert 0.5 <= metrics["roc_auc"] <= 1.0
    assert "precision" in metrics and "recall" in metrics
    assert set(cv) == {"cv_roc_auc", "cv_pr_auc"}


def test_lead_time_recall_improves_near_failure(feature_frames):
    train_df, _, lead_df = feature_frames
    Xtr = train_df.drop(columns=["serial", "end_day", "label", "kind"])
    ytr = train_df["label"].astype(int)
    clf, _, threshold = M.train_model(
        Xtr, ytr, train_df["serial"].astype(str), _cfg(), seed=42
    )
    lead = M.lead_time_recall(clf, lead_df, threshold)
    assert lead
    horizons = [int(d["horizon_days"]) for d in lead]
    assert horizons == sorted(horizons)
    near = next(d for d in lead if int(d["horizon_days"]) == 1)
    far = next(d for d in lead if int(d["horizon_days"]) == 30)
    # Synthetic failing drives ramp SMART attributes -> recall should be
    # higher (or at least not catastrophically lower) close to failure.
    assert near["recall"] >= far["recall"]


def test_feature_importance_sorted(feature_frames):
    train_df, test_df, _ = feature_frames
    Xtr = train_df.drop(columns=["serial", "end_day", "label", "kind"])
    ytr = train_df["label"].astype(int)
    Xte = test_df.drop(columns=["serial", "end_day", "label", "kind"])
    yte = test_df["label"].astype(int)
    clf, _, _ = M.train_model(Xtr, ytr, train_df["serial"].astype(str), _cfg(), seed=42)
    imp = M.feature_importance(clf, Xte, yte, n_repeats=3, max_rows=1000)
    assert len(imp) > 0
    vals = [float(d["importance"]) for d in imp]
    assert vals == sorted(vals, reverse=True)


def test_single_class_raises(feature_frames):
    train_df, _, _ = feature_frames
    X = train_df.drop(columns=["serial", "end_day", "label", "kind"])
    y = pd.Series(np.zeros(len(train_df), dtype=int))  # all healthy
    with pytest.raises(M.ModelError):
        M.cross_validate(X, y, train_df["serial"].astype(str), _cfg(), seed=42)
