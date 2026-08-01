"""Health check implementation tests — run against real local servers."""
from __future__ import annotations

import os
import socket
import subprocess
import time

import pytest

from infra_health.checks import check_disk, check_http, check_process, check_tcp
from infra_health.config import CheckConfig


def _http_cfg(url, **kwargs):
    return CheckConfig(name="t", type="http", url=url, **kwargs)


# ── http ──────────────────────────────────────────────────────────────────

def test_http_ok(http_ok):
    result = check_http(_http_cfg(f"http://127.0.0.1:{http_ok.server_port}/health"))
    assert result.ok
    assert "HTTP 200" in result.detail
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_http_wrong_status(http_ok):
    result = check_http(_http_cfg(f"http://127.0.0.1:{http_ok.server_port}/health", expected_status=204))
    assert not result.ok
    assert "HTTP 200 (expected 204)" in result.detail


def test_http_expects_503_matches(http_flaky):
    result = check_http(_http_cfg(f"http://127.0.0.1:{http_flaky.server_port}/health", expected_status=503))
    assert result.ok


def test_http_text_match(http_ok):
    ok = check_http(_http_cfg(f"http://127.0.0.1:{http_ok.server_port}/health", expected_text="ok"))
    assert ok.ok
    missing = check_http(_http_cfg(f"http://127.0.0.1:{http_ok.server_port}/health", expected_text="nope"))
    assert not missing.ok
    assert "missing 'nope'" in missing.detail


def test_http_connection_refused(free_port):
    result = check_http(_http_cfg(f"http://127.0.0.1:{free_port}/health"))
    assert not result.ok
    assert result.latency_ms is not None


# ── tcp ───────────────────────────────────────────────────────────────────

def test_tcp_ok(tcp_listener):
    port = tcp_listener.getsockname()[1]
    result = check_tcp(CheckConfig(name="t", type="tcp", host="127.0.0.1", port=port))
    assert result.ok
    assert "connected" in result.detail


def test_tcp_refused(free_port):
    result = check_tcp(CheckConfig(name="t", type="tcp", host="127.0.0.1", port=free_port))
    assert not result.ok
    assert "connection failed" in result.detail


# ── disk ──────────────────────────────────────────────────────────────────

def test_disk_ok(tmp_path):
    result = check_disk(CheckConfig(name="t", type="disk", path=str(tmp_path)))
    assert result.ok
    assert "% used" in result.detail


def test_disk_missing_path(tmp_path):
    result = check_disk(CheckConfig(name="t", type="disk", path=str(tmp_path / "nope")))
    assert not result.ok
    assert "cannot stat" in result.detail


def test_disk_over_critical(tmp_path):
    # A path that reports ~100% usage: a file isn't a mount point, so use a
    # nonexistent-but-special trick is not reliable — instead verify the
    # threshold logic directly with a tiny stub.
    import infra_health.checks as checks_mod

    real = checks_mod.shutil.disk_usage
    checks_mod.shutil.disk_usage = lambda _path: type("U", (), {"used": 99, "total": 100, "free": 1})()
    try:
        result = check_disk(CheckConfig(name="t", type="disk", path=str(tmp_path), critical_percent=95))
        assert not result.ok
        assert "above" in result.detail
    finally:
        checks_mod.shutil.disk_usage = real


# ── process ───────────────────────────────────────────────────────────────

@pytest.mark.skipif(not os.path.isdir("/proc"), reason="process checks require Linux /proc")
def test_process_found_then_gone():
    proc = subprocess.Popen(["sleep", "60"])
    try:
        assert check_process(CheckConfig(name="t", type="process", process_name="sleep")).ok
        proc.terminate()
        proc.wait(timeout=10)
        time.sleep(0.2)
        result = check_process(CheckConfig(name="t", type="process", process_name="sleep"))
        assert not result.ok
        assert "not found" in result.detail
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
