"""Config loading: defaults, YAML coercion, path resolution, validation."""

from __future__ import annotations

import pytest
import yaml

from solarpositions.config import DEFAULT_BODIES, SolarConfig, load_config


def test_defaults():
    cfg = SolarConfig()
    assert cfg.start == "1900-01-01"
    assert cfg.end == "2100-12-01"
    assert cfg.step_months == 1
    assert cfg.bodies == DEFAULT_BODIES
    assert cfg.ephemeris == "builtin"
    assert cfg.precision == 6


def test_yaml_coerces_numeric_strings(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        yaml.safe_dump({"step_months": "6", "precision": "4"})
    )
    cfg = load_config(cfg_file)
    assert cfg.step_months == 6
    assert cfg.precision == 4


def test_paths_resolve_against_config_dir(tmp_path):
    cfg_file = tmp_path / "configs" / "example.yaml"
    cfg_file.parent.mkdir()
    cfg_file.write_text(yaml.safe_dump({"output_csv": "../data/positions.csv"}))
    cfg = load_config(cfg_file)
    assert cfg.output_csv == str((tmp_path / "data" / "positions.csv").resolve())


def test_invalid_ephemeris_rejected(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"ephemeris": "nasa"}))
    with pytest.raises(ValueError, match="ephemeris"):
        load_config(cfg_file)


def test_precision_bounds(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"precision": 15}))
    with pytest.raises(ValueError, match="precision"):
        load_config(cfg_file)


def test_empty_bodies_rejected(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"bodies": []}))
    with pytest.raises(ValueError, match="bodies"):
        load_config(cfg_file)
