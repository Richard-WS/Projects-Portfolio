"""Model training and evaluation (gradient boosting on S.M.A.R.T. features)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold

from .config import ModelConfig


class ModelError(Exception):
    """Raised when training input is not usable (e.g. a single-class set)."""


def drop_constant_columns(X: pd.DataFrame) -> pd.DataFrame:
    """Remove zero-variance columns.

    HistGradientBoosting's binning needs at least two distinct values per
    feature, so constant columns (capacity of a single-model fleet, or SMART
    attributes that never change) must be dropped before training.
    """
    nunique = X.nunique(dropna=True)
    const = nunique[nunique <= 1].index.tolist()
    if const:
        return X.drop(columns=const)
    return X


def make_classifier(cfg: ModelConfig, seed: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=cfg.max_iter,
        learning_rate=cfg.learning_rate,
        min_samples_leaf=cfg.min_samples_leaf,
        l2_regularization=cfg.l2_regularization,
        random_state=seed,
    )


def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    drives: Sequence[str],
    cfg: ModelConfig,
    seed: int,
) -> Tuple[Dict[str, float], np.ndarray]:
    """Group-wise out-of-fold predictions — a drive's windows never straddle
    the fold boundary, so optimism from duplicated drives is avoided."""
    y_arr = y.to_numpy()
    if len(np.unique(y_arr)) < 2:
        raise ModelError("training set needs both healthy and failing drives")
    X = drop_constant_columns(X)
    if X.shape[1] == 0:
        raise ModelError("no usable features after dropping constant columns")
    oof = np.zeros(len(X))
    gkf = GroupKFold(n_splits=cfg.cv_folds)
    for tr_idx, va_idx in gkf.split(X, y, drives):
        clf = make_classifier(cfg, seed)
        clf.fit(X.iloc[tr_idx], y_arr[tr_idx])
        oof[va_idx] = clf.predict_proba(X.iloc[va_idx])[:, 1]
    return {
        "cv_roc_auc": float(roc_auc_score(y_arr, oof)),
        "cv_pr_auc": float(average_precision_score(y_arr, oof)),
    }, oof


def best_threshold(y: np.ndarray, proba: np.ndarray) -> float:
    """Threshold maximising F1 on (usually) out-of-fold predictions."""
    y_arr = np.asarray(y)
    p = np.asarray(proba)
    if len(np.unique(y_arr)) < 2:
        return 0.5
    prec, rec, th = precision_recall_curve(y_arr, p)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-9)
    return float(th[int(np.argmax(f1))]) if len(th) else 0.5


def evaluate(y: np.ndarray, proba: np.ndarray, threshold: float) -> Dict[str, float]:
    y_arr = np.asarray(y)
    p = np.asarray(proba)
    pred = (p >= threshold).astype(int)
    tp = int(((pred == 1) & (y_arr == 1)).sum())
    fp = int(((pred == 1) & (y_arr == 0)).sum())
    fn = int(((pred == 0) & (y_arr == 1)).sum())
    tn = int(((pred == 0) & (y_arr == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    has_both = len(np.unique(y_arr)) == 2
    return {
        "roc_auc": float(roc_auc_score(y_arr, p)) if has_both else float("nan"),
        "pr_auc": float(average_precision_score(y_arr, p)) if has_both else float("nan"),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_alarm_rate": float(fp / max(tn + fp, 1)),
        "threshold": float(threshold),
        "n": int(len(y_arr)),
        "n_failing": int((y_arr == 1).sum()),
        "n_healthy": int((y_arr == 0).sum()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    drives: Sequence[str],
    cfg: ModelConfig,
    seed: int,
) -> Tuple[HistGradientBoostingClassifier, Dict[str, float], float]:
    X = drop_constant_columns(X)
    cv_metrics, oof = cross_validate(X, y, drives, cfg, seed)
    threshold = best_threshold(y.to_numpy(), oof)
    clf = make_classifier(cfg, seed)
    clf.fit(X, y.to_numpy())
    return clf, cv_metrics, threshold


def lead_time_recall(
    model: HistGradientBoostingClassifier,
    leadtime_df: pd.DataFrame,
    threshold: float,
) -> List[Dict[str, float]]:
    """For each lead-time horizon (days before failure the window ends),
    what fraction of the failing drives would already have been flagged?"""
    out: List[Dict[str, float]] = []
    if leadtime_df is None or leadtime_df.empty:
        return out
    proba = model.predict_proba(leadtime_df[model.feature_names_in_])[:, 1]
    tmp = leadtime_df.copy()
    tmp["risk"] = proba
    for horizon, group in tmp.groupby("horizon"):
        flagged = int((group["risk"] >= threshold).sum())
        out.append(
            {
                "horizon_days": float(horizon),
                "drives": int(len(group)),
                "flagged": flagged,
                "recall": float(flagged / max(len(group), 1)),
                "mean_risk": float(group["risk"].mean()),
            }
        )
    out.sort(key=lambda d: d["horizon_days"])
    return out


def feature_importance(
    model: HistGradientBoostingClassifier,
    X: pd.DataFrame,
    y: pd.Series | np.ndarray,
    n_repeats: int = 5,
    seed: int = 0,
    max_rows: int = 3000,
) -> List[Dict[str, Any]]:
    """Permutation importance on held-out data.

    sklearn removed `feature_importances_` from HistGradientBoosting in 1.9,
    and permutation importance is more trustworthy anyway: it measures how
    much shuffling a feature degrades predictions on data the model has not
    memorised. Computed on (a sample of) the held-out test set.
    """
    X = X[model.feature_names_in_]
    y_arr = np.asarray(y)
    if len(X) > max_rows:
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(X), size=max_rows, replace=False)
        X = X.iloc[idx]
        y_arr = y_arr[idx]
    if len(np.unique(y_arr)) < 2:
        return []
    scorer = "roc_auc" if len(np.unique(y_arr)) == 2 else "accuracy"
    res = permutation_importance(
        model, X, y_arr, scoring=scorer, n_repeats=n_repeats,
        random_state=seed, n_jobs=1,
    )
    order = np.argsort(res.importances_mean)[::-1]
    return [
        {"feature": str(model.feature_names_in_[i]), "importance": float(res.importances_mean[i])}
        for i in order
    ]
