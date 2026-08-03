"""Model training and evaluation.

Two models are compared on the same split:

* a balanced logistic regression (the baseline — linear, interpretable)
* gradient boosting on the engineered features

Model selection uses the validation split; the held-out test set (the
dataset's official test curves) is scored once at the end and reported
honestly alongside a stratified cross-validated ROC-AUC on the training
set.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

from .config import Config


class ModelError(Exception):
    """Raised when training or scoring fails."""


def balanced_sample_weights(y: np.ndarray) -> np.ndarray:
    """Inverse-frequency weights so the boosting model sees both classes."""
    y = np.asarray(y)
    pos = int((y == 1).sum())
    neg = int(y.size - pos)
    if pos == 0 or neg == 0:
        raise ModelError("cannot train with a single class present")
    weights = np.where(y == 1, 1.0 / pos, 1.0 / neg)
    return weights * (y.size / weights.sum())


def staged_validation_auc(model, X, y, step: int = 10) -> list[dict]:
    """Validation ROC-AUC after every ``step`` boosting iterations.

    Reads the fitted model's staged predictions, so the curve is the real
    training trajectory, not a re-fit. Returns an empty list for models
    without staged predictions (e.g. logistic regression) or single-class
    validation sets. The last point is the final fit.
    """
    if not hasattr(model, "staged_predict_proba"):
        return []
    if len(np.unique(np.asarray(y))) < 2:
        return []
    curve: list[dict] = []
    for i, proba in enumerate(model.staged_predict_proba(X), start=1):
        if i == 1 or i % step == 0:
            curve.append(
                {
                    "iteration": i,
                    "val_roc_auc": round(float(roc_auc_score(y, proba[:, 1])), 4),
                }
            )
    if curve and curve[-1]["iteration"] != model.n_estimators:
        final = model.predict_proba(X)[:, 1]
        curve.append(
            {
                "iteration": int(model.n_estimators),
                "val_roc_auc": round(float(roc_auc_score(y, final)), 4),
            }
        )
    return curve


def train_pipeline(
    X_train, y_train, cfg: Config, X_val=None, y_val=None, X_test=None, y_test=None,
    feature_names: list[str] | None = None,
) -> tuple[dict, dict]:
    """Fit both models, pick the better one, and return (metrics, artifacts).

    ``artifacts`` holds the fitted pipeline pieces so the CLI can persist
    the chosen model and the report can reuse the evaluation details.
    """
    if feature_names is None:
        feature_names = [f"f{i}" for i in range(X_train.shape[1])]
    if len(feature_names) != X_train.shape[1]:
        raise ModelError("feature_names must match the feature matrix width")
    if len(np.unique(np.asarray(y_train))) < 2:
        raise ModelError("cannot train with a single class present")
    scaler = StandardScaler().fit(X_train)
    Xtr = scaler.transform(X_train)
    rs = cfg.split.random_state

    baseline = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=rs)
    baseline.fit(Xtr, y_train)

    booster = GradientBoostingClassifier(
        n_estimators=cfg.model.n_estimators,
        max_depth=cfg.model.max_depth,
        learning_rate=cfg.model.learning_rate,
        random_state=rs,
    )
    booster.fit(Xtr, y_train, sample_weight=balanced_sample_weights(y_train))

    names = ["logistic_regression", "gradient_boosting"]
    models = [baseline, booster]

    # pick on validation AUC when a validation set exists, else cross-validated AUC
    if X_val is not None and y_val is not None:
        Xva = scaler.transform(X_val)
        scores = [roc_auc_score(y_val, m.predict_proba(Xva)[:, 1]) for m in models]
    else:
        scores = [
            cross_val_score(m, Xtr, y_train, cv=cfg.model.cv_folds, scoring="roc_auc").mean()
            for m in models
        ]
    best_idx = int(np.argmax(scores))
    best_name = names[best_idx]
    best_model = models[best_idx]

    # honest CV estimate for the chosen model
    cv = StratifiedKFold(n_splits=cfg.model.cv_folds, shuffle=True, random_state=rs)
    cv_auc = cross_val_score(best_model, Xtr, y_train, cv=cv, scoring="roc_auc")

    metrics: dict = {
        "chosen_model": best_name,
        "comparison": {
            name: {"val_roc_auc": round(float(score), 4)}
            for name, score in zip(names, scores)
        },
        "cv_roc_auc_mean": round(float(cv_auc.mean()), 4),
        "cv_roc_auc_std": round(float(cv_auc.std()), 4),
        "cv_folds": cfg.model.cv_folds,
        "train_size": int(X_train.shape[0]),
        "n_features": int(X_train.shape[1]),
        "class_counts": {"non_exoplanet": int((np.asarray(y_train) == 0).sum()),
                         "exoplanet": int((np.asarray(y_train) == 1).sum())},
        "params": {
            "n_estimators": cfg.model.n_estimators,
            "max_depth": cfg.model.max_depth,
            "learning_rate": cfg.model.learning_rate,
            "test_size": cfg.split.test_size,
            "random_state": rs,
        },
    }

    def _score(X, y, label: str) -> None:
        if X is None or y is None:
            return
        Xs = scaler.transform(X)
        proba = best_model.predict_proba(Xs)[:, 1]
        preds = (proba >= 0.5).astype(int)
        prec, rec, f1, _ = precision_recall_fscore_support(y, preds, average="binary", zero_division=0)
        tn, fp, fn, tp = confusion_matrix(y, preds, labels=[0, 1]).ravel()
        metrics[label] = {
            "roc_auc": round(float(roc_auc_score(y, proba)), 4),
            "pr_auc": round(float(average_precision_score(y, proba)), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1": round(float(f1), 4),
            "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "n_positive": int((np.asarray(y) == 1).sum()),
            "n_negative": int((np.asarray(y) == 0).sum()),
        }

    _score(X_val, y_val, "validation")
    _score(X_test, y_test, "test")

    # real training curve: validation ROC-AUC after every 10th boosting
    # iteration, read off the fitted model's staged predictions. The last
    # point is the final fit and matches the validation metric above.
    if X_val is not None and y_val is not None:
        curve = staged_validation_auc(best_model, scaler.transform(X_val), y_val)
        if curve:
            metrics["training_curve"] = curve

    if hasattr(best_model, "feature_importances_"):
        importance = best_model.feature_importances_
        source = "gradient_boosting"
    else:
        importance = np.abs(best_model.coef_[0])
        source = "logistic_regression"
    top = np.argsort(importance)[::-1][:10]
    metrics["top_features"] = [
        {"feature": name, "importance": round(float(importance[i]), 6)}
        for name, i in zip(feature_names, top)
    ]
    metrics["importance_source"] = source

    artifacts = {
        "scaler": scaler,
        "model": best_model,
        "kind": best_name,
        "feature_names": list(feature_names),
        "threshold": 0.5,
    }
    return metrics, artifacts


def save_model(artifacts: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifacts, path)


def load_model(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ModelError(f"model file not found: {path}")
    artifacts = joblib.load(path)
    if not isinstance(artifacts, dict) or "model" not in artifacts:
        raise ModelError(f"{path} is not a classifier pipeline")
    return artifacts


def predict(artifacts: dict, X: np.ndarray) -> np.ndarray:
    """Return per-curve exoplanet probabilities."""
    X = np.asarray(X, dtype=float)
    if X.ndim != 2:
        raise ModelError("predictions need a 2-D feature matrix")
    Xs = artifacts["scaler"].transform(X)
    return artifacts["model"].predict_proba(Xs)[:, 1]


def save_metrics(metrics: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")


def load_metrics(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ModelError(f"metrics file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
