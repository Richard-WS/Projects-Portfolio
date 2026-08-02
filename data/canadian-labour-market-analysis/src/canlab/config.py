"""Configuration for the canlab pipeline.

Knobs live in a YAML file (configs/example.yaml). Two conventions matter:

* Paths in the YAML are resolved relative to the config file's directory, so
  ``../data/raw`` means ``<project>/data/raw`` no matter where the process is
  started from.
* YAML parses some numbers as strings (e.g. ``3e-4``), so numeric-looking
  strings are coerced on the way in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_QUERIES = [
    "q01_unemployment_national",
    "q02_unemployment_by_province_latest",
    "q03_employment_growth_yoy",
    "q04_provincial_employment_share",
    "q05_fastest_growing_provinces",
    "q06_recession_2008_recovery",
    "q07_covid_shock_2020",
    "q08_nb_vs_canada_unemployment",
    "q09_unemployment_moving_average",
    "q10_employment_per_working_age",
    "q11_gender_participation_gap",
    "q12_youth_unemployment",
    "q13_part_time_share",
    "q14_nb_employment_by_decade",
]

# Population age groups kept in the warehouse: the groups shared with the
# labour-force table (joinable) plus "All ages".
DEFAULT_POPULATION_AGE_GROUPS = [
    "All ages",
    "15 to 24 years",
    "15 to 64 years",
    "15 years and over",
    "25 to 44 years",
    "25 to 54 years",
]


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
class SourcesConfig:
    labour_force_product_id: int = 14100327
    population_product_id: int = 17100005
    licence: str = "Statistics Canada Open Licence"


@dataclass
class PathsConfig:
    raw_dir: Path = Path("data/raw")
    db_path: Path = Path("data/canlab.db")
    sql_dir: Path = Path("sql")
    samples_dir: Path = Path("data/samples")

    def resolve_against(self, base: Path) -> "PathsConfig":
        """Resolve every path against ``base`` (the config file's directory)."""
        return PathsConfig(
            raw_dir=(base / self.raw_dir).resolve(),
            db_path=(base / self.db_path).resolve(),
            sql_dir=(base / self.sql_dir).resolve(),
            samples_dir=(base / self.samples_dir).resolve(),
        )


@dataclass
class Config:
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    population_age_groups: list[str] = field(
        default_factory=lambda: list(DEFAULT_POPULATION_AGE_GROUPS)
    )
    queries: list[str] = field(default_factory=lambda: list(DEFAULT_QUERIES))
    latest_year: int = 2025


def _to_config(raw: dict, base: Path) -> Config:
    cfg = Config()

    sources = raw.get("sources", {})
    cfg.sources.labour_force_product_id = int(
        coerce_scalar(sources.get("labour_force_product_id", cfg.sources.labour_force_product_id))
    )
    cfg.sources.population_product_id = int(
        coerce_scalar(sources.get("population_product_id", cfg.sources.population_product_id))
    )
    cfg.sources.licence = sources.get("licence", cfg.sources.licence)

    paths = raw.get("paths", {})
    cfg.paths = PathsConfig(
        raw_dir=Path(paths.get("raw_dir", "data/raw")),
        db_path=Path(paths.get("db_path", "data/canlab.db")),
        sql_dir=Path(paths.get("sql_dir", "sql")),
        samples_dir=Path(paths.get("samples_dir", "data/samples")),
    ).resolve_against(base)

    if "population_age_groups" in raw:
        cfg.population_age_groups = list(raw["population_age_groups"])
    if "queries" in raw:
        cfg.queries = [q for q in raw["queries"] if q]
    cfg.latest_year = int(coerce_scalar(raw.get("latest_year", 2025)))
    return cfg


def load_config(path: str | Path) -> Config:
    """Load and validate a YAML config; paths resolve against its directory."""
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    cfg = _to_config(raw, path.parent)
    if not cfg.paths.sql_dir.exists():
        raise FileNotFoundError(f"sql_dir does not exist: {cfg.paths.sql_dir}")
    return cfg
