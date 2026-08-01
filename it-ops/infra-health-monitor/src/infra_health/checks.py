"""Health check implementations.

Each check type probes a target using only the standard library and returns a
CheckResult with a pass/fail verdict, latency, and a short human-readable
detail string that explains the verdict.

Supported types:
  http    — GET a URL, verify status code and optional body text
  tcp     — open a TCP connection to host:port
  disk    — compare disk usage at a path against a critical threshold
  process — look for a running process by its /proc comm name (Linux)
"""
from __future__ import annotations

import os
import shutil
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from infra_health.config import CheckConfig


@dataclass
class CheckResult:
    name: str
    check_type: str
    ok: bool
    ts: str  # ISO-8601 UTC, e.g. 2026-08-01T14:03:22+00:00
    latency_ms: float | None = None
    detail: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_http(cfg: CheckConfig) -> CheckResult:
    assert cfg.url is not None  # guaranteed by config validation
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(cfg.url, timeout=cfg.timeout_seconds) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        # A non-2xx response is still a response: evaluate it like any other.
        status, body = exc.code, exc.read()
    except Exception as exc:
        return _result(
            cfg, False, _latency(started),
            f"{exc.__class__.__name__}: {exc}",
        )

    latency_ms = _latency(started)
    if status != cfg.expected_status:
        return _result(
            cfg, False, latency_ms,
            f"HTTP {status} (expected {cfg.expected_status})",
        )
    if cfg.expected_text and cfg.expected_text.encode("utf-8", errors="replace") not in body:
        return _result(
            cfg, False, latency_ms,
            f"HTTP {status} but body is missing {cfg.expected_text!r}",
        )
    return _result(cfg, True, latency_ms, f"HTTP {status} in {latency_ms:.0f}ms")


def check_tcp(cfg: CheckConfig) -> CheckResult:
    assert cfg.host is not None and cfg.port is not None  # guaranteed by config validation
    started = time.perf_counter()
    try:
        with socket.create_connection((cfg.host, int(cfg.port)), timeout=cfg.timeout_seconds):
            latency_ms = _latency(started)
        return _result(cfg, True, latency_ms, f"connected in {latency_ms:.0f}ms")
    except Exception as exc:
        return _result(
            cfg, False, _latency(started),
            f"connection failed: {exc.__class__.__name__}: {exc}",
        )


def check_disk(cfg: CheckConfig) -> CheckResult:
    assert cfg.path is not None  # guaranteed by config validation
    try:
        usage = shutil.disk_usage(cfg.path)
    except OSError as exc:
        return _result(cfg, False, None, f"cannot stat {cfg.path}: {exc}")
    percent = usage.used / usage.total * 100.0
    free_mib = usage.free / (1024 * 1024)
    detail = f"{percent:.1f}% used ({free_mib:.0f} MiB free)"
    if percent >= cfg.critical_percent:
        return _result(cfg, False, None, f"{detail} — above {cfg.critical_percent:.0f}% critical")
    return _result(cfg, True, None, detail)


def check_process(cfg: CheckConfig) -> CheckResult:
    assert cfg.process_name is not None  # guaranteed by config validation
    if not (os.name == "posix" and os.path.isdir("/proc")):
        return _result(cfg, False, None, "process checks require Linux (/proc)")
    target = cfg.process_name
    found = False
    try:
        entries = os.listdir("/proc")
    except OSError as exc:
        return _result(cfg, False, None, f"cannot read /proc: {exc}")
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/comm", encoding="utf-8") as fh:
                comm = fh.read().strip()
        except OSError:
            continue
        if comm == target:
            found = True
            break
    if found:
        return _result(cfg, True, None, f"process {target!r} is running")
    return _result(cfg, False, None, f"process {target!r} not found")


CHECK_FUNCTIONS = {
    "http": check_http,
    "tcp": check_tcp,
    "disk": check_disk,
    "process": check_process,
}


def run_check(cfg: CheckConfig) -> CheckResult:
    """Dispatch a check config to its implementation."""
    return CHECK_FUNCTIONS[cfg.type](cfg)


def _result(cfg: CheckConfig, ok: bool, latency_ms: float | None, detail: str) -> CheckResult:
    return CheckResult(
        name=cfg.name,
        check_type=cfg.type,
        ok=ok,
        ts=now_iso(),
        latency_ms=latency_ms,
        detail=detail,
    )


def _latency(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0
