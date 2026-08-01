"""Configuration loading and validation.

The monitor is configured with a YAML file describing the checks to run,
where history is stored, and how alerts behave. This module turns that file
into typed dataclasses and fails fast with clear errors, so a bad config is
caught at startup rather than mid-run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_CHECK_TYPES = ("http", "tcp", "disk", "process")

_SHARED_KEYS = {"name", "type", "interval_seconds", "timeout_seconds", "slo_percent"}
_TYPE_KEYS = {
    "http": {"url", "expected_status", "expected_text"},
    "tcp": {"host", "port"},
    "disk": {"path", "warn_percent", "critical_percent"},
    "process": {"process_name"},
}
_TOP_LEVEL_KEYS = {"checks", "history", "alerts"}


class ConfigError(ValueError):
    """Raised when a configuration file is missing, malformed, or invalid."""


@dataclass
class CheckConfig:
    """A single check: what to probe, how often, and the availability target."""

    name: str
    type: str
    interval_seconds: float = 60.0
    timeout_seconds: float = 10.0
    slo_percent: float = 99.9
    # http
    url: str | None = None
    expected_status: int = 200
    expected_text: str | None = None
    # tcp
    host: str | None = None
    port: int | None = None
    # disk
    path: str | None = None
    warn_percent: float = 85.0
    critical_percent: float = 95.0
    # process
    process_name: str | None = None


@dataclass
class AlertConfig:
    log_level: str = "info"
    webhook_url_env: str = "ALERT_WEBHOOK_URL"
    cooldown_seconds: float = 300.0


@dataclass
class Config:
    checks: list[CheckConfig] = field(default_factory=list)
    history_path: str = "data/raw/history.db"
    state_path: str = "data/raw/state.json"
    alerts: AlertConfig = field(default_factory=AlertConfig)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        """Load and validate a YAML config file.

        Relative paths in the file are resolved against the file's own
        directory, so the monitor can be run from anywhere.
        """
        cfg_path = Path(path)
        if not cfg_path.is_file():
            raise ConfigError(f"config file not found: {cfg_path}")
        try:
            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {cfg_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"{cfg_path}: config must be a YAML mapping")

        unknown_top = set(raw) - _TOP_LEVEL_KEYS
        if unknown_top:
            raise ConfigError(f"unknown top-level key(s): {sorted(unknown_top)}")

        raw_checks = raw.get("checks")
        if not raw_checks:
            raise ConfigError("config requires a non-empty 'checks' list")
        if not isinstance(raw_checks, list):
            raise ConfigError("'checks' must be a list")

        checks = [_build_check(entry, i) for i, entry in enumerate(raw_checks)]
        names = [c.name for c in checks]
        if len(set(names)) != len(names):
            raise ConfigError(f"duplicate check names: {names}")

        base = cfg_path.parent
        history = raw.get("history") or {}
        alerts = raw.get("alerts") or {}
        return cls(
            checks=checks,
            history_path=str(_resolve(base, history.get("db_path", "data/raw/history.db"))),
            state_path=str(_resolve(base, history.get("state_path", "data/raw/state.json"))),
            alerts=_build_alerts(alerts),
        )


def _build_check(raw: Any, index: int) -> CheckConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"check #{index + 1} must be a mapping")
    name = raw.get("name")
    ctype = raw.get("type")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"check #{index + 1}: 'name' is required")
    if ctype not in SUPPORTED_CHECK_TYPES:
        raise ConfigError(
            f"check {name!r}: unknown type {ctype!r} "
            f"(supported: {', '.join(SUPPORTED_CHECK_TYPES)})"
        )

    allowed = _SHARED_KEYS | _TYPE_KEYS[ctype]
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError(f"check {name!r}: unknown key(s): {sorted(unknown)}")

    check = CheckConfig(name=name, type=ctype)
    for key, value in raw.items():
        if key in ("name", "type"):
            continue
        setattr(check, key, value)

    _validate_number(check, "interval_seconds", minimum=0.1)
    _validate_number(check, "timeout_seconds", minimum=0.1)
    _validate_number(check, "slo_percent", minimum=0.0, maximum=100.0)
    if check.slo_percent <= 0:
        raise ConfigError(f"check {name!r}: 'slo_percent' must be greater than 0")

    if ctype == "http":
        if not isinstance(check.url, str) or not check.url.startswith(("http://", "https://")):
            raise ConfigError(f"check {name!r}: 'url' must start with http:// or https://")
        if not isinstance(check.expected_status, int):
            raise ConfigError(f"check {name!r}: 'expected_status' must be an integer")
    elif ctype == "tcp":
        _require(check, "host")
        _require(check, "port")
        assert check.port is not None
        if not (1 <= int(check.port) <= 65535):
            raise ConfigError(f"check {name!r}: 'port' must be between 1 and 65535")
    elif ctype == "disk":
        _require(check, "path")
        _validate_number(check, "warn_percent", minimum=0.0, maximum=100.0)
        _validate_number(check, "critical_percent", minimum=0.0, maximum=100.0)
        if check.warn_percent >= check.critical_percent:
            raise ConfigError(
                f"check {name!r}: 'warn_percent' must be below 'critical_percent'"
            )
    elif ctype == "process":
        _require(check, "process_name")

    return check


def _build_alerts(raw: Any) -> AlertConfig:
    if not isinstance(raw, dict):
        raise ConfigError("'alerts' must be a mapping")
    allowed = {"log_level", "webhook_url_env", "cooldown_seconds"}
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError(f"alerts: unknown key(s): {sorted(unknown)}")
    level = str(raw.get("log_level", "info")).lower()
    if level not in ("debug", "info", "warning", "error"):
        raise ConfigError(f"alerts: invalid log_level {level!r}")
    cooldown = float(raw.get("cooldown_seconds", 300.0))
    if cooldown < 0:
        raise ConfigError("alerts: cooldown_seconds must be >= 0")
    return AlertConfig(
        log_level=level,
        webhook_url_env=str(raw.get("webhook_url_env", "ALERT_WEBHOOK_URL")),
        cooldown_seconds=cooldown,
    )


def _require(check: CheckConfig, key: str) -> None:
    if getattr(check, key) in (None, ""):
        raise ConfigError(f"check {check.name!r} (type {check.type!r}) requires '{key}'")


def _validate_number(check: CheckConfig, key: str, minimum: float, maximum: float | None = None) -> None:
    value = getattr(check, key)
    if not isinstance(value, (int, float)):
        raise ConfigError(f"check {check.name!r}: '{key}' must be a number")
    if value < minimum:
        raise ConfigError(f"check {check.name!r}: '{key}' must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"check {check.name!r}: '{key}' must be <= {maximum}")


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()
