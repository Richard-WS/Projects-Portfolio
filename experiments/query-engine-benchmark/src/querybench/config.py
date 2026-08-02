"""Config loading for the benchmark.

Knobs live in a YAML file (configs/example.yaml). YAML parses some numbers as
strings (e.g. ``3e-4``), so numeric-looking strings are coerced on the way in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_QUERIES = [
    "q1_filter_sum",
    "q2_groupby",
    "q3_multi_groupby",
    "q4_join",
    "q5_topn",
    "q6_monthly_revenue",
]

FORMATS = ("parquet", "csv")


def coerce_scalar(value: Any) -> Any:
    """Return ``value`` as an int/float when it is a numeric-looking string."""
    if isinstance(value, str):
        cleaned = value.strip().replace("_", "")
        for cast in (int, float):
            try:
                return cast(cleaned)
            except ValueError:
                continue
    return value


@dataclass
class DatasetConfig:
    n_orders: int = 5_000_000
    n_customers: int = 200_000
    seed: int = 42
    format: str = "parquet"

    def validate(self) -> None:
        if self.n_orders < 100:
            raise ValueError("dataset.n_orders must be at least 100")
        if self.n_customers < 10:
            raise ValueError("dataset.n_customers must be at least 10")
        if self.format not in FORMATS:
            raise ValueError(f"dataset.format must be one of {FORMATS}")


@dataclass
class BenchmarkConfig:
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    queries: list[str] = field(default_factory=lambda: list(DEFAULT_QUERIES))
    runs: int = 3
    warmup: int = 1

    def validate(self) -> None:
        self.dataset.validate()
        if self.runs < 1:
            raise ValueError("runs must be >= 1")
        if self.warmup < 0:
            raise ValueError("warmup must be >= 0")
        unknown = [q for q in self.queries if q not in DEFAULT_QUERIES]
        if unknown:
            raise ValueError(f"unknown queries: {', '.join(unknown)}")


def load_config(path: str | Path) -> BenchmarkConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    dataset_raw = {k: coerce_scalar(v) for k, v in raw.get("dataset", {}).items()}
    queries = [q for q in raw.get("queries", []) or [] if q]
    queries = queries or list(DEFAULT_QUERIES)
    return BenchmarkConfig(
        dataset=DatasetConfig(**dataset_raw),
        queries=queries,
        runs=int(coerce_scalar(raw.get("runs", 3))),
        warmup=int(coerce_scalar(raw.get("warmup", 1))),
    )
