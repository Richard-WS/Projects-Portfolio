"""Report tests: text tables, HTML output, duration formatting."""
from __future__ import annotations

from infra_health.checks import CheckResult
from infra_health.report import (
    _fmt_duration,
    format_check_table,
    format_summary_table,
    render_html,
)


def _row(name="api", status="up", uptime: float | None = 99.94, total=200, passed=199, slo=99.9):
    def window(value):
        return {
            "total": total,
            "passed": passed,
            "uptime": value,
            "breached": False if value is None else value < slo,
        }

    return {
        "name": name,
        "type": "http",
        "status": status,
        "windows": {"24h": window(uptime), "7d": window(uptime), "30d": window(uptime)},
        "slo_percent": slo,
        "est_downtime_s": 0,
        "budget_remaining_s": 2592,
    }


def test_text_table_contains_rows():
    table = format_summary_table([_row(), _row("db", status="down", uptime=90.0, passed=180)])
    assert "api" in table and "db" in table
    assert "99.9%" in table
    assert "99.9% (199/200)" in table
    assert "down" in table


def test_text_table_no_data():
    table = format_summary_table([_row(uptime=None)])
    assert "no data" in table


def test_check_table():
    table = format_check_table(
        [
            CheckResult(name="api", check_type="http", ok=True, ts="t", latency_ms=12.3, detail="HTTP 200 in 12ms"),
            CheckResult(name="db", check_type="tcp", ok=False, ts="t", latency_ms=None, detail="connection failed"),
        ]
    )
    assert "UP" in table and "DOWN" in table
    assert "12ms" in table and "connection failed" in table


def test_html_report_structure():
    failures = [
        {"name": "db", "type": "tcp", "ts": "2026-08-01T10:00:01+00:00", "detail": "connection failed: timeout"},
    ]
    html = render_html([_row(), _row("db", status="down", uptime=90.0, passed=180)], failures, "2026-08-01 12:00")
    assert "<title>Infrastructure health report</title>" in html
    assert "2026-08-01 12:00" in html
    assert ">api<" in html and ">db<" in html
    assert "SLO breaches" in html
    assert "connection failed: timeout" in html
    assert "99.9% (199/200)" in html
    # one header row + two data rows
    assert html.count("<tr>") == 3
    assert "Incidents" in html


def test_html_escapes_dynamic_text():
    html = render_html([_row(name="<evil>")], [], "2026-08-01 12:00")
    assert "&lt;evil&gt;" in html
    assert "<evil>" not in html


def test_html_no_incidents_message():
    html = render_html([_row()], [], "2026-08-01 12:00")
    assert "No failures recorded" in html


def test_duration_formatting():
    assert _fmt_duration(0) == "0s"
    assert _fmt_duration(90) == "1m30s"
    assert _fmt_duration(3700) == "1h1m40s"
    assert _fmt_duration(90061) == "1d1h1m"
    assert _fmt_duration(-5) == "0s"
