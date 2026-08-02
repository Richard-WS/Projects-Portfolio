"""Configuration loading for the solar system positions project."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# YAML parses values like 3e-4 as strings; coerce anything that looks numeric.
_NUMERIC = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")

DEFAULT_BODIES = [
    "mercury",
    "venus",
    "earth",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
]

VALID_EPHEMERIDES = {"builtin", "jpl", "de430", "de432s", "de440", "de440s"}


def _coerce(value):
    if isinstance(value, str) and _NUMERIC.match(value.strip()):
        try:
            return int(value)
        except ValueError:
            return float(value)
    return value


@dataclass
class SolarConfig:
    start: str = "1900-01-01"
    end: str = "2100-12-01"
    step_months: int = 1
    bodies: list[str] = field(default_factory=lambda: list(DEFAULT_BODIES))
    ephemeris: str = "builtin"
    output_csv: str = "../data/positions.csv"
    output_html: str = "../viewer.html"
    template: str = "../templates/viewer_template.html"
    precision: int = 6

    def resolve(self, base_dir: Path) -> "SolarConfig":
        """Resolve relative paths against the config file's directory."""
        if not Path(self.output_csv).is_absolute():
            self.output_csv = str((base_dir / self.output_csv).resolve())
        if not Path(self.output_html).is_absolute():
            self.output_html = str((base_dir / self.output_html).resolve())
        if not Path(self.template).is_absolute():
            self.template = str((base_dir / self.template).resolve())
        return self


def load_config(path: str | Path) -> SolarConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    cfg = SolarConfig()
    for key in (
        "start",
        "end",
        "step_months",
        "bodies",
        "ephemeris",
        "output_csv",
        "output_html",
        "template",
        "precision",
    ):
        if key in raw:
            setattr(cfg, key, _coerce(raw[key]))
    if cfg.ephemeris not in VALID_EPHEMERIDES:
        raise ValueError(
            f"ephemeris {cfg.ephemeris!r} not supported; "
            f"choose from {sorted(VALID_EPHEMERIDES)}"
        )
    if cfg.precision < 0 or cfg.precision > 12:
        raise ValueError(f"precision {cfg.precision} out of range [0, 12]")
    if cfg.step_months < 1:
        raise ValueError("step_months must be >= 1")
    if not cfg.bodies:
        raise ValueError("bodies must not be empty")
    return cfg.resolve(path.parent)
