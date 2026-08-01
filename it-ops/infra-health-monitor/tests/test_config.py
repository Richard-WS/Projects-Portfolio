"""Config loading and validation tests."""
from __future__ import annotations

import textwrap

import pytest

from infra_health.config import Config, ConfigError

EXAMPLE = """
checks:
  - name: api
    type: http
    url: https://example.com/health
    interval_seconds: 60
    slo_percent: 99.9
  - name: db
    type: tcp
    host: db.internal
    port: 5432
"""


def _write(tmp_path, yaml_text, name="config.yaml"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(yaml_text), encoding="utf-8")
    return path


def test_load_valid_config(tmp_path):
    cfg = Config.load(_write(tmp_path, EXAMPLE))
    assert [c.name for c in cfg.checks] == ["api", "db"]
    assert cfg.checks[0].type == "http"
    assert cfg.checks[0].slo_percent == 99.9
    assert cfg.checks[1].timeout_seconds == 10.0  # default
    assert cfg.checks[1].interval_seconds == 60.0


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        Config.load(tmp_path / "nope.yaml")


def test_invalid_yaml(tmp_path):
    with pytest.raises(ConfigError, match="invalid YAML"):
        Config.load(_write(tmp_path, "checks: ["))


def test_empty_checks_rejected(tmp_path):
    with pytest.raises(ConfigError, match="non-empty 'checks'"):
        Config.load(_write(tmp_path, "checks: []"))


def test_unknown_check_type(tmp_path):
    with pytest.raises(ConfigError, match="unknown type"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: ping"))


def test_unknown_check_key(tmp_path):
    with pytest.raises(ConfigError, match="unknown key"):
        Config.load(
            _write(
                tmp_path,
                "checks:\n  - name: a\n    type: http\n    url: http://x\n    intervall: 5",
            )
        )


def test_unknown_top_level_key(tmp_path):
    with pytest.raises(ConfigError, match="unknown top-level"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: http\n    url: http://x\nfoo: 1"))


def test_duplicate_names(tmp_path):
    with pytest.raises(ConfigError, match="duplicate check names"):
        Config.load(_write(tmp_path, EXAMPLE.replace("name: db", "name: api")))


def test_http_requires_url(tmp_path):
    with pytest.raises(ConfigError, match="'url'"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: http"))


def test_http_url_scheme(tmp_path):
    with pytest.raises(ConfigError, match="http:// or https://"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: http\n    url: ftp://x"))


def test_tcp_requires_host_and_port(tmp_path):
    with pytest.raises(ConfigError, match="'port'"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: tcp\n    host: db.internal"))
    with pytest.raises(ConfigError, match="'host'"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: tcp\n    port: 5432"))


def test_tcp_port_range(tmp_path):
    with pytest.raises(ConfigError, match="'port' must be between"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: tcp\n    host: h\n    port: 99999"))


def test_disk_requires_path(tmp_path):
    with pytest.raises(ConfigError, match="'path'"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: disk"))


def test_disk_threshold_order(tmp_path):
    with pytest.raises(ConfigError, match="warn_percent' must be below"):
        Config.load(
            _write(
                tmp_path,
                "checks:\n  - name: a\n    type: disk\n    path: /tmp\n    warn_percent: 90\n    critical_percent: 80",
            )
        )


def test_process_requires_name(tmp_path):
    with pytest.raises(ConfigError, match="'process_name'"):
        Config.load(_write(tmp_path, "checks:\n  - name: a\n    type: process"))


def test_slo_out_of_range(tmp_path):
    with pytest.raises(ConfigError, match="slo_percent"):
        Config.load(
            _write(tmp_path, "checks:\n  - name: a\n    type: http\n    url: http://x\n    slo_percent: 101")
        )
    with pytest.raises(ConfigError, match="slo_percent"):
        Config.load(
            _write(tmp_path, "checks:\n  - name: a\n    type: http\n    url: http://x\n    slo_percent: 0")
        )


def test_interval_must_be_positive(tmp_path):
    with pytest.raises(ConfigError, match="interval_seconds"):
        Config.load(
            _write(tmp_path, "checks:\n  - name: a\n    type: http\n    url: http://x\n    interval_seconds: -5")
        )


def test_bad_alerts_block(tmp_path):
    with pytest.raises(ConfigError, match="invalid log_level"):
        Config.load(
            _write(
                tmp_path,
                "checks:\n  - name: a\n    type: http\n    url: http://x\nalerts:\n  log_level: loud",
            )
        )


def test_relative_paths_resolve_against_config_dir(tmp_path):
    cfg = Config.load(
        _write(
            tmp_path,
            "checks:\n  - name: a\n    type: http\n    url: http://x\n"
            "history:\n  db_path: var/history.db\n  state_path: var/state.json",
        )
    )
    assert cfg.history_path == str((tmp_path / "var" / "history.db").resolve())
    assert cfg.state_path == str((tmp_path / "var" / "state.json").resolve())
