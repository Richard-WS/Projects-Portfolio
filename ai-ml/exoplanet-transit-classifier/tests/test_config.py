"""Config loading, validation, and path-resolution tests."""
from __future__ import annotations

import pytest

from exoplanet_classifier.config import Config, ConfigError, data_url


def _write(tmp_path, body: str):
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_are_self_consistent():
    cfg = Config.defaults()
    assert cfg.split.test_size == 0.25
    assert cfg.features.detrend_window == 64
    assert cfg.features.autocorr_max_lag == 400
    assert cfg.model.n_estimators == 200
    assert str(cfg.paths.model_path) == "outputs/model.joblib"
    cfg.validate()  # defaults must pass validation


def test_load_empty_config_uses_defaults(tmp_path):
    cfg = Config.load(_write(tmp_path, "# nothing\n"))
    assert cfg.split.test_size == 0.25
    assert cfg.model.cv_folds == 5


def test_load_full_config(tmp_path):
    body = (
        "data:\n"
        "  raw_dir: raw\n"
        "  raw_sample_rows: 8\n"
        "split:\n"
        "  test_size: 0.2\n"
        "  random_state: 7\n"
        "features:\n"
        "  detrend_window: 128\n"
        "  dip_threshold_mad: 2.5\n"
        "  autocorr_max_lag: 300\n"
        "model:\n"
        "  n_estimators: 150\n"
        "  max_depth: 4\n"
        "  learning_rate: 0.08\n"
        "  cv_folds: 4\n"
        "paths:\n"
        "  model_path: out/model.joblib\n"
    )
    cfg = Config.load(_write(tmp_path, body))
    assert cfg.data.raw_sample_rows == 8
    assert cfg.split.test_size == 0.2
    assert cfg.features.detrend_window == 128
    assert cfg.features.autocorr_max_lag == 300
    assert cfg.model.n_estimators == 150
    assert cfg.model.cv_folds == 4


def test_numeric_strings_are_coerced(tmp_path):
    body = (
        "split:\n"
        "  test_size: '0.3'\n"
        "  random_state: '11'\n"
        "model:\n"
        "  learning_rate: '3e-2'\n"
    )
    cfg = Config.load(_write(tmp_path, body))
    assert cfg.split.test_size == 0.3
    assert cfg.split.random_state == 11
    assert cfg.model.learning_rate == pytest.approx(0.03)


def test_relative_paths_resolve_against_config_dir(tmp_path):
    cfg = Config.load(_write(tmp_path, "paths:\n  model_path: outputs/model.joblib\n"))
    assert cfg.paths.model_path == (tmp_path / "outputs" / "model.joblib").resolve()


def test_absolute_paths_stay_absolute(tmp_path):
    body = f"paths:\n  model_path: {tmp_path}/model.joblib\n"
    cfg = Config.load(_write(tmp_path, body))
    assert cfg.paths.model_path == (tmp_path / "model.joblib").resolve()


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        Config.load(tmp_path / "nope.yaml")


def test_invalid_yaml_raises(tmp_path):
    with pytest.raises(ConfigError, match="invalid YAML"):
        Config.load(_write(tmp_path, "data: ["))


def test_non_mapping_root_raises(tmp_path):
    with pytest.raises(ConfigError, match="mapping"):
        Config.load(_write(tmp_path, "- just\n- a\n- list\n"))


def test_validation_test_size(tmp_path):
    with pytest.raises(ConfigError, match="test_size"):
        Config.load(_write(tmp_path, "split:\n  test_size: 1.5\n"))
    with pytest.raises(ConfigError, match="test_size"):
        Config.load(_write(tmp_path, "split:\n  test_size: 0\n"))


def test_validation_detrend_window(tmp_path):
    with pytest.raises(ConfigError, match="detrend_window"):
        Config.load(_write(tmp_path, "features:\n  detrend_window: 1\n"))


def test_validation_autocorr_max_lag(tmp_path):
    with pytest.raises(ConfigError, match="autocorr_max_lag"):
        Config.load(_write(tmp_path, "features:\n  autocorr_max_lag: 3\n"))
    with pytest.raises(ConfigError, match="autocorr_max_lag"):
        Config.load(_write(tmp_path, "features:\n  autocorr_max_lag: 'x'\n"))


def test_validation_model_params(tmp_path):
    with pytest.raises(ConfigError, match="n_estimators"):
        Config.load(_write(tmp_path, "model:\n  n_estimators: 0\n"))
    with pytest.raises(ConfigError, match="cv_folds"):
        Config.load(_write(tmp_path, "model:\n  cv_folds: 1\n"))
    with pytest.raises(ConfigError, match="learning_rate"):
        Config.load(_write(tmp_path, "model:\n  learning_rate: -0.1\n"))


def test_boolean_rejected_as_number(tmp_path):
    with pytest.raises(ConfigError):
        Config.load(_write(tmp_path, "split:\n  test_size: true\n"))


def test_empty_string_value_rejected(tmp_path):
    with pytest.raises(ConfigError, match="raw_train"):
        Config.load(_write(tmp_path, "data:\n  raw_train: ''\n"))


def test_data_url_env_override(monkeypatch):
    assert data_url() == ""
    monkeypatch.setenv("KEPLER_DATA_URL", "https://example.invalid/kepler/")
    assert data_url() == "https://example.invalid/kepler/"
