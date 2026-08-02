"""Configuration loading and validation.

Config files live in configs/ and use paths relative to their own directory,
so the data/, docs/ and outputs/ entries in example.yaml (written with ../)
resolve to the project root regardless of where the CLI is invoked from.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, List, cast, get_type_hints

import yaml


class ConfigError(Exception):
    """Raised when a config file is missing, malformed, or invalid."""


def _coerce_for(field_type: Any, value: Any) -> Any:
    """YAML parses some numbers as strings (e.g. 3e-4); coerce when the
    dataclass field expects a number and the string looks numeric."""
    if isinstance(value, str) and field_type in (int, float):
        try:
            return float(value) if field_type is float else int(float(value))
        except ValueError:
            return value
    return value


def _from_dict(cls: Any, data: dict) -> Any:
    cls = cast(type, cls)
    if not is_dataclass(cls):
        raise ConfigError(f"{cls.__name__} is not a dataclass")
    # get_type_hints resolves string annotations (required because the module
    # uses `from __future__ import annotations`).
    hints = get_type_hints(cls)
    unknown = set(data) - set(hints)
    if unknown:
        raise ConfigError(f"unknown config keys for {cls.__name__}: {sorted(unknown)}")
    kwargs: dict = {}
    for name, ftype in hints.items():
        if name not in data:
            continue
        value = data[name]
        if is_dataclass(ftype):
            kwargs[name] = _from_dict(ftype, value)
        else:
            kwargs[name] = _coerce_for(ftype, value)
    return cls(**kwargs)


@dataclass
class DataConfig:
    raw_dir: str = "data/raw/backblaze"
    raw_csv: str = "data_Q1_2024.csv"
    samples_dir: str = "data/samples"
    raw_sample: str = "raw_smart_sample.csv.gz"
    sample_drives: int = 250
    sample_days: int = 12
    max_drives: int = 60000
    smart_missing_threshold: float = 0.99
    seed: int = 42


@dataclass
class LabelConfig:
    pre_failure_days: int = 30
    horizon_days: int = 7


@dataclass
class FeaturesConfig:
    window_days: int = 7
    min_window_obs: int = 3
    leadtime_horizons: List[int] = field(default_factory=lambda: [1, 3, 7, 14, 30])


@dataclass
class SplitConfig:
    test_size: float = 0.2
    seed: int = 42
    max_negative_drives: int = 40000


@dataclass
class ModelConfig:
    max_iter: int = 300
    learning_rate: float = 0.1
    min_samples_leaf: int = 20
    l2_regularization: float = 1.0
    cv_folds: int = 5


@dataclass
class PathsConfig:
    feature_train: str = "data/samples/features_train.csv.gz"
    feature_test: str = "data/samples/features_test.csv.gz"
    leadtime_features: str = "data/samples/leadtime_features.csv.gz"
    model_path: str = "outputs/model.joblib"
    metrics_path: str = "docs/metrics.json"
    report_path: str = "docs/disk-failure-report.html"
    predictions_path: str = "outputs/predictions.csv"


@dataclass
class Config:
    data: DataConfig = field(default_factory=DataConfig)
    labels: LabelConfig = field(default_factory=LabelConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    config_dir: Path = field(default=Path("."), repr=False)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"config file not found: {p}")
        try:
            raw = yaml.safe_load(p.read_text())
        except yaml.YAMLError as exc:
            raise ConfigError(f"malformed YAML in {p}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"config root must be a mapping, got {type(raw).__name__}")
        cfg = _from_dict(cls, raw)
        cfg.config_dir = p.resolve().parent
        cfg._resolve_paths()  # noqa: SLF001
        cfg._validate()  # noqa: SLF001
        return cfg

    def _resolve_paths(self) -> None:
        """Turn relative path fields into absolute paths rooted at configs/."""
        root = self.config_dir
        for f in fields(self.paths):
            value = getattr(self.paths, f.name)
            if not isinstance(value, str) or not value:
                continue
            resolved = (root / value).resolve()
            setattr(self.paths, f.name, str(resolved))
        # Data fields are relative to the project root (one level up from configs/)
        for f in fields(self.data):
            value = getattr(self.data, f.name)
            if not isinstance(value, str) or not value:
                continue
            if value.startswith("..") or "/" in value or "\\" in value:
                resolved = (root / value).resolve()
                setattr(self.data, f.name, str(resolved))

    def _validate(self) -> None:
        for f in fields(self.paths):
            value = getattr(self.paths, f.name)
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"paths.{f.name} must be a non-empty path")
        if self.data.max_drives <= 0:
            raise ConfigError("data.max_drives must be positive")
        if not 0.0 < self.split.test_size < 1.0:
            raise ConfigError("split.test_size must be in (0, 1)")
        if self.model.cv_folds < 2:
            raise ConfigError("model.cv_folds must be >= 2")

    def raw_csv_path(self) -> Path:
        return Path(self.data.raw_dir) / self.data.raw_csv

    def sample_csv_path(self) -> Path:
        return Path(self.data.samples_dir) / self.data.raw_sample

    def summary(self) -> dict:
        return {
            "raw_csv": str(self.raw_csv_path()),
            "max_drives": self.data.max_drives,
            "horizon_days": self.labels.horizon_days,
            "window_days": self.features.window_days,
            "test_size": self.split.test_size,
        }
