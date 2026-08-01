"""Configuration loading and validation for the classifier pipeline.

Config files are YAML. All relative paths are resolved against the config
file's directory, so commands can be run from anywhere.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when a config file is missing, malformed, or invalid."""


def _coerce_float(value, name: str) -> float:
    """YAML parses some numeric-looking strings (e.g. ``3e-4``) as str."""
    if isinstance(value, bool):
        raise ConfigError(f"'{name}' must be a number, got a boolean")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            pass
    raise ConfigError(f"'{name}' must be a number, got {value!r}")


def _coerce_int(value, name: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"'{name}' must be an integer, got a boolean")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"'{name}' must be an integer, got {value!r}") from None


@dataclass
class DataConfig:
    raw_dir: Path = Path("data/raw")
    raw_train: str = "exoTrain.csv"
    raw_test: str = "exoTest.csv"
    samples_dir: Path = Path("data/samples")
    raw_url: str = "https://media.githubusercontent.com/media/AarejSyed/Labelled-Kepler-Light-Curve-Dataset/main/"
    raw_sample_rows: int = 20


@dataclass
class SplitConfig:
    test_size: float = 0.25
    random_state: int = 42


@dataclass
class FeaturesConfig:
    detrend_window: int = 64
    dip_threshold_mad: float = 3.0
    autocorr_max_lag: int = 400


@dataclass
class ModelConfig:
    n_estimators: int = 200
    max_depth: int = 3
    learning_rate: float = 0.05
    cv_folds: int = 5


@dataclass
class PathsConfig:
    model_path: Path = Path("outputs/model.joblib")
    report_path: Path = Path("docs/classification-report.html")
    metrics_path: Path = Path("docs/metrics.json")
    feature_train: Path = Path("data/samples/features_train.csv.gz")
    feature_val: Path = Path("data/samples/features_val.csv.gz")
    feature_test: Path = Path("data/samples/features_test.csv.gz")
    raw_sample: Path = Path("data/samples/raw_lightcurves_sample.csv")
    predictions_path: Path = Path("outputs/predictions.csv")


@dataclass
class Config:
    data: DataConfig
    split: SplitConfig
    features: FeaturesConfig
    model: ModelConfig
    paths: PathsConfig

    @classmethod
    def defaults(cls) -> "Config":
        return cls(
            data=DataConfig(),
            split=SplitConfig(),
            features=FeaturesConfig(),
            model=ModelConfig(),
            paths=PathsConfig(),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"config file not found: {path}")
        try:
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {path}: {exc}") from None
        if not isinstance(raw, dict):
            raise ConfigError(f"config root must be a mapping, got {type(raw).__name__}")

        cfg = cls.defaults()
        base = path.resolve().parent

        data = raw.get("data") or {}
        cfg.data.raw_dir = _resolve(base, _str(data, "raw_dir", cfg.data.raw_dir))
        cfg.data.raw_train = _str(data, "raw_train", cfg.data.raw_train)
        cfg.data.raw_test = _str(data, "raw_test", cfg.data.raw_test)
        cfg.data.samples_dir = _resolve(base, _str(data, "samples_dir", cfg.data.samples_dir))
        cfg.data.raw_url = _str(data, "raw_url", cfg.data.raw_url)
        cfg.data.raw_sample_rows = _coerce_int(_get(data, "raw_sample_rows", cfg.data.raw_sample_rows), "data.raw_sample_rows")

        split = raw.get("split") or {}
        cfg.split.test_size = _coerce_float(_get(split, "test_size", cfg.split.test_size), "split.test_size")
        cfg.split.random_state = _coerce_int(_get(split, "random_state", cfg.split.random_state), "split.random_state")

        features = raw.get("features") or {}
        cfg.features.detrend_window = _coerce_int(_get(features, "detrend_window", cfg.features.detrend_window), "features.detrend_window")
        cfg.features.dip_threshold_mad = _coerce_float(_get(features, "dip_threshold_mad", cfg.features.dip_threshold_mad), "features.dip_threshold_mad")
        cfg.features.autocorr_max_lag = _coerce_int(_get(features, "autocorr_max_lag", cfg.features.autocorr_max_lag), "features.autocorr_max_lag")

        model = raw.get("model") or {}
        cfg.model.n_estimators = _coerce_int(_get(model, "n_estimators", cfg.model.n_estimators), "model.n_estimators")
        cfg.model.max_depth = _coerce_int(_get(model, "max_depth", cfg.model.max_depth), "model.max_depth")
        cfg.model.learning_rate = _coerce_float(_get(model, "learning_rate", cfg.model.learning_rate), "model.learning_rate")
        cfg.model.cv_folds = _coerce_int(_get(model, "cv_folds", cfg.model.cv_folds), "model.cv_folds")

        paths = raw.get("paths") or {}
        cfg.paths.model_path = _resolve(base, _str(paths, "model_path", cfg.paths.model_path))
        cfg.paths.report_path = _resolve(base, _str(paths, "report_path", cfg.paths.report_path))
        cfg.paths.metrics_path = _resolve(base, _str(paths, "metrics_path", cfg.paths.metrics_path))
        cfg.paths.feature_train = _resolve(base, _str(paths, "feature_train", cfg.paths.feature_train))
        cfg.paths.feature_val = _resolve(base, _str(paths, "feature_val", cfg.paths.feature_val))
        cfg.paths.feature_test = _resolve(base, _str(paths, "feature_test", cfg.paths.feature_test))
        cfg.paths.raw_sample = _resolve(base, _str(paths, "raw_sample", cfg.paths.raw_sample))
        cfg.paths.predictions_path = _resolve(base, _str(paths, "predictions_path", cfg.paths.predictions_path))

        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not 0.0 < self.split.test_size < 1.0:
            raise ConfigError("'split.test_size' must be between 0 and 1")
        if self.split.random_state < 0:
            raise ConfigError("'split.random_state' must be >= 0")
        if self.features.detrend_window < 3:
            raise ConfigError("'features.detrend_window' must be at least 3")
        if self.features.dip_threshold_mad <= 0:
            raise ConfigError("'features.dip_threshold_mad' must be positive")
        if self.features.autocorr_max_lag < 8:
            raise ConfigError("'features.autocorr_max_lag' must be at least 8")
        if self.model.n_estimators < 1:
            raise ConfigError("'model.n_estimators' must be >= 1")
        if self.model.max_depth < 1:
            raise ConfigError("'model.max_depth' must be >= 1")
        if self.model.learning_rate <= 0:
            raise ConfigError("'model.learning_rate' must be positive")
        if not 2 <= self.model.cv_folds <= 20:
            raise ConfigError("'model.cv_folds' must be between 2 and 20")


def _resolve(base: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p)


def _get(mapping: dict, key: str, default):
    return mapping.get(key, default)


def _str(mapping: dict, key: str, default: str | Path) -> str:
    value = mapping.get(key, default)
    if isinstance(value, Path):
        value = str(value)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"'{key}' must be a non-empty string")
    return value.strip()


def data_url(env_name: str = "KEPLER_DATA_URL") -> str:
    """Raw-data base URL, overridable via the environment (.env)."""
    return os.environ.get(env_name, "").strip()
