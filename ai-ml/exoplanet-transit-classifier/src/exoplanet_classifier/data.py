"""Data loading and preparation.

The raw dataset (NASA Kepler Q1-Q17 light curves, labelled as exoplanet /
non-exoplanet) ships as CSVs with one curve per row: a label column
followed by the flux values. Labels are 1 (non-exoplanet) and 2
(exoplanet); internally they are mapped to 0/1.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .config import Config
from .features import extract_features

LABEL_NON_EXOPLANET = 1
LABEL_EXOPLANET = 2


class DataError(Exception):
    """Raised when raw data is missing or malformed."""


def load_light_curves(csv_path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (flux matrix, binary labels)."""
    path = Path(csv_path)
    if not path.is_file():
        raise DataError(f"raw data file not found: {path}")
    try:
        df = pd.read_csv(path, header=0)
    except Exception as exc:
        raise DataError(f"could not read {path}: {exc}") from None
    if df.shape[1] < 2 or df.shape[0] == 0:
        raise DataError(f"expected rows of label + flux values, got shape {df.shape}")
    label_col = df.columns[0]
    labels = df[label_col].to_numpy()
    if not set(np.unique(labels)).issubset({LABEL_NON_EXOPLANET, LABEL_EXOPLANET}):
        raise DataError(f"unexpected labels in {path.name}: {sorted(set(np.unique(labels).tolist()))}")
    flux = df.drop(columns=[label_col]).to_numpy(dtype=float)
    y = (labels == LABEL_EXOPLANET).astype(int)
    return flux, y


def split_curves(flux, y, test_size: float, random_state: int):
    """Stratified train/validation split preserving class balance."""
    return train_test_split(
        flux, y, test_size=test_size, random_state=random_state, stratify=y
    )


def build_feature_frame(flux, y, features_cfg) -> pd.DataFrame:
    """Feature matrix for a set of curves, plus the label column."""
    rows = [
        extract_features(
            curve,
            detrend_window=features_cfg.detrend_window,
            dip_threshold_mad=features_cfg.dip_threshold_mad,
            autocorr_max_lag=features_cfg.autocorr_max_lag,
        )
        for curve in flux
    ]
    df = pd.DataFrame(rows)
    df["label"] = y
    return df


def download_raw(cfg: Config, *, env_url: str = "") -> None:
    """Fetch the raw CSVs into data/raw/ when they are missing.

    The default URL points at the public mirror of the Kepler labelled
    time-series dataset; ``KEPLER_DATA_URL`` (from .env) overrides it.
    """
    base = env_url or cfg.data.raw_url
    cfg.data.raw_dir.mkdir(parents=True, exist_ok=True)
    for filename in (cfg.data.raw_train, cfg.data.raw_test):
        dest = cfg.data.raw_dir / filename
        if dest.is_file():
            continue
        url = base.rstrip("/") + "/" + filename
        print(f"downloading {filename} ...")
        urllib.request.urlretrieve(url, dest)


def prepare(cfg: Config, *, env_url: str = "") -> dict[str, int]:
    """Turn raw light curves into committed feature matrices.

    Writes ``features_train.csv``, ``features_val.csv`` and
    ``features_test.csv`` into the samples directory, plus a small sample
    of real light curves for the README. Returns row counts.
    """
    download_raw(cfg, env_url=env_url)
    train_path = cfg.data.raw_dir / cfg.data.raw_train
    test_path = cfg.data.raw_dir / cfg.data.raw_test

    flux_train, y_train = load_light_curves(train_path)
    flux_test, y_test = load_light_curves(test_path)

    f_tr, f_va, y_tr, y_va = split_curves(
        flux_train, y_train, cfg.split.test_size, cfg.split.random_state
    )

    cfg.data.samples_dir.mkdir(parents=True, exist_ok=True)
    out_train = cfg.paths.feature_train
    out_val = cfg.paths.feature_val
    out_test = cfg.paths.feature_test

    build_feature_frame(f_tr, y_tr, cfg.features).to_csv(
        out_train, index=False, compression="gzip" if str(out_train).endswith(".gz") else None
    )
    build_feature_frame(f_va, y_va, cfg.features).to_csv(
        out_val, index=False, compression="gzip" if str(out_val).endswith(".gz") else None
    )
    build_feature_frame(flux_test, y_test, cfg.features).to_csv(
        out_test, index=False, compression="gzip" if str(out_test).endswith(".gz") else None
    )

    # small committed sample of real light curves
    n = cfg.data.raw_sample_rows
    keep = min(n, flux_train.shape[0])
    sample = pd.DataFrame(flux_train[:keep])
    sample.insert(0, "label", (y_train[:keep] + 1))
    sample.to_csv(cfg.paths.raw_sample, index=False)

    return {
        "train": int(y_tr.size),
        "val": int(y_va.size),
        "test": int(y_test.size),
    }


def load_features(cfg: Config, which: str = "train") -> tuple[np.ndarray, np.ndarray]:
    """Load a prepared feature matrix (train | val | test)."""
    path = Path(
        {
            "train": cfg.paths.feature_train,
            "val": cfg.paths.feature_val,
            "test": cfg.paths.feature_test,
        }[which]
    )
    if not path.is_file():
        raise DataError(f"feature matrix not found: {path} (run 'prepare' first)")
    df = pd.read_csv(path)
    y = df["label"].to_numpy()
    X = df.drop(columns=["label"]).to_numpy(dtype=float)
    if not np.all(np.isfinite(X)):
        raise DataError(f"feature matrix {path.name} contains non-finite values")
    return X, y
