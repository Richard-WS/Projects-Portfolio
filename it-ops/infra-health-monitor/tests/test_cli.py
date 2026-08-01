"""CLI tests: subprocess runs of `python -m infra_health`."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "infra_health", *args],
        capture_output=True,
        text=True,
        cwd=PROJECT,
        timeout=60,
    )


def _config_file(tmp_path, url, history="data/raw/history.db", name="config.yaml"):
    path = tmp_path / name
    path.write_text(
        f"checks:\n"
        f"  - name: svc\n"
        f"    type: http\n"
        f"    url: {url}\n"
        f"    interval_seconds: 60\n"
        f"history:\n"
        f"  db_path: {history}\n"
        f"  state_path: data/raw/state.json\n",
        encoding="utf-8",
    )
    return path


def test_help():
    proc = _run("--help")
    assert proc.returncode == 0
    assert "check" in proc.stdout and "run" in proc.stdout and "report" in proc.stdout


def test_check_down_exits_1(tmp_path, free_port):
    config = _config_file(tmp_path, f"http://127.0.0.1:{free_port}/health")
    proc = _run("check", "-c", str(config))
    assert proc.returncode == 1
    assert "DOWN" in proc.stdout
    assert "1 of 1 checks down" in proc.stderr


def test_check_up_exits_0(tmp_path, http_ok):
    config = _config_file(tmp_path, f"http://127.0.0.1:{http_ok.server_port}/health")
    proc = _run("check", "-c", str(config))
    assert proc.returncode == 0
    assert "UP" in proc.stdout


def test_bad_config_exits_2(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("checks: [", encoding="utf-8")
    proc = _run("check", "-c", str(path))
    assert proc.returncode == 2
    assert "error:" in proc.stderr


def test_report_after_check(tmp_path, http_ok):
    history = str(tmp_path / "history.db")
    config = _config_file(tmp_path, f"http://127.0.0.1:{http_ok.server_port}/health", history=history)
    check = _run("check", "-c", str(config))
    assert check.returncode == 0
    report = _run("report", "-c", str(config))
    assert report.returncode == 0
    assert "svc" in report.stdout
    assert "100.0%" in report.stdout
    assert "uptime 24h" in report.stdout


def test_report_exports_html_and_csv(tmp_path, http_ok):
    history = str(tmp_path / "history.db")
    config = _config_file(tmp_path, f"http://127.0.0.1:{http_ok.server_port}/health", history=history)
    _run("check", "-c", str(config))
    html_path = tmp_path / "report.html"
    csv_path = tmp_path / "history.csv"
    proc = _run("report", "-c", str(config), "--html", str(html_path), "--csv", str(csv_path))
    assert proc.returncode == 0
    assert html_path.is_file()
    assert "Infrastructure health report" in html_path.read_text(encoding="utf-8")
    assert csv_path.is_file()
    assert "Infrastructure health report" not in proc.stderr
