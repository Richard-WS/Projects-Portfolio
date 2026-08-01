"""Monitor tests: orchestration, alerts, state persistence, summaries."""
from __future__ import annotations

import json
import logging

from infra_health.config import CheckConfig, Config
from infra_health.monitor import Monitor


def _config(checks, tmp_path, **kwargs):
    return Config(
        checks=checks,
        history_path=str(tmp_path / "history.db"),
        state_path=str(tmp_path / "state.json"),
        **kwargs,
    )


def _http_check(name, url, interval=1.0, slo=99.9):
    return CheckConfig(name=name, type="http", url=url, interval_seconds=interval, slo_percent=slo)


def test_run_once_records_and_state(tmp_path, http_ok):
    config = _config([_http_check("svc", f"http://127.0.0.1:{http_ok.server_port}/health")], tmp_path)
    monitor = Monitor(config)
    results = monitor.run_once()
    assert len(results) == 1 and results[0].ok
    assert monitor.history.summary("2000-01-01T00:00:00+00:00")["svc"] == (1, 1)
    assert monitor.state.get("svc", "state") == "up"
    monitor.close()


def test_state_transition_alerts(tmp_path, http_flaky, caplog):
    config = _config([_http_check("svc", f"http://127.0.0.1:{http_flaky.server_port}/health")], tmp_path)
    monitor = Monitor(config)
    with caplog.at_level(logging.INFO, logger="infra-health"):
        for _ in range(4):  # down, down, down, up
            monitor.run_once()
    text = caplog.text
    assert "DOWN" in text
    assert "RECOVERED" in text
    assert "SLO_BREACH" in text
    monitor.close()


def test_slo_breach_alerts_once(tmp_path, http_flaky, caplog):
    config = _config([_http_check("svc", f"http://127.0.0.1:{http_flaky.server_port}/health")], tmp_path)
    monitor = Monitor(config)
    with caplog.at_level(logging.INFO, logger="infra-health"):
        for _ in range(6):
            monitor.run_once()
    assert caplog.text.count("SLO_BREACH") == 1
    assert "below the 99.9% SLO" in caplog.text
    monitor.close()


def test_state_persists_across_restart(tmp_path, http_flaky, caplog):
    config = _config([_http_check("svc", f"http://127.0.0.1:{http_flaky.server_port}/health")], tmp_path)
    first = Monitor(config)
    for _ in range(3):  # exhaust the flaky server's failures (all down)
        first.run_once()
    first.close()
    # The flaky server is healthy by now.
    second = Monitor(config)
    with caplog.at_level(logging.INFO, logger="infra-health"):
        second.run_once()  # up → RECOVERED across restart
    assert "RECOVERED" in caplog.text
    assert second.state.get("svc", "state") == "up"
    second.close()


def test_webhook_receives_payload(tmp_path, http_flaky, webhook_server):
    server, captured = webhook_server
    config = _config([_http_check("svc", f"http://127.0.0.1:{http_flaky.server_port}/health")], tmp_path)
    monitor = Monitor(config, webhook_url=f"http://127.0.0.1:{server.server_port}/hook")
    monitor.run_once()  # down → DOWN alert
    assert captured
    payload = json.loads(captured[0])
    assert payload["alert"] == "DOWN"
    assert payload["check"] == "svc"
    assert payload["type"] == "http"
    assert payload["ts"]
    assert payload["detail"]
    monitor.close()


def test_webhook_from_env(tmp_path, http_flaky, webhook_server, monkeypatch):
    server, captured = webhook_server
    monkeypatch.setenv(
        "ALERT_WEBHOOK_URL", f"http://127.0.0.1:{server.server_port}/hook"
    )
    config = _config([_http_check("svc", f"http://127.0.0.1:{http_flaky.server_port}/health")], tmp_path)
    monitor = Monitor(config)
    monitor.run_once()
    assert captured
    monitor.close()


def test_webhook_failure_does_not_crash(tmp_path, http_flaky, free_port, caplog):
    config = _config([_http_check("svc", f"http://127.0.0.1:{http_flaky.server_port}/health")], tmp_path)
    monitor = Monitor(config, webhook_url=f"http://127.0.0.1:{free_port}/hook")
    with caplog.at_level(logging.INFO, logger="infra-health"):
        monitor.run_once()
    assert "webhook failed" in caplog.text
    monitor.close()


def test_run_loop_respects_intervals(tmp_path, http_ok):
    check = CheckConfig(name="svc", type="http", url=f"http://127.0.0.1:{http_ok.server_port}/health",
                        interval_seconds=0.2)
    config = _config([check], tmp_path)
    monitor = Monitor(config)
    monitor.run_loop(iterations=4, round_interval=0.1)
    total = monitor.history.summary("2000-01-01T00:00:00+00:00")["svc"][0]
    assert 1 <= total <= 4
    monitor.close()


def test_summary_windows_and_budget(tmp_path, http_ok):
    check = CheckConfig(name="svc", type="http", url=f"http://127.0.0.1:{http_ok.server_port}/health",
                        interval_seconds=60, slo_percent=99.9)
    config = _config([check], tmp_path)
    monitor = Monitor(config)
    for _ in range(3):
        monitor.run_once()
    rows = monitor.summary()
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "up"
    for label in ("24h", "7d", "30d"):
        assert row["windows"][label]["total"] == 3
        assert row["windows"][label]["passed"] == 3
        assert row["windows"][label]["breached"] is False
    assert row["est_downtime_s"] == 0
    assert row["budget_remaining_s"] > 0
    monitor.close()


def test_summary_flags_breach_and_downtime(tmp_path, http_flaky):
    check = CheckConfig(name="svc", type="http", url=f"http://127.0.0.1:{http_flaky.server_port}/health",
                        interval_seconds=1000, slo_percent=99.9)
    config = _config([check], tmp_path)
    monitor = Monitor(config)
    for _ in range(3):  # all three fail while the server is flaky
        monitor.run_once()
    row = monitor.summary()[0]
    assert row["windows"]["24h"]["breached"] is True
    # 3 failures x 1000s interval exceeds the 30-day SLO budget (2592s at 99.9%)
    assert row["est_downtime_s"] == 3000
    assert row["budget_remaining_s"] < 0
    monitor.close()


def test_summary_unknown_window(tmp_path, http_ok):
    check = _http_check("svc", f"http://127.0.0.1:{http_ok.server_port}/health")
    config = _config([check], tmp_path)
    monitor = Monitor(config)
    try:
        monitor.summary(windows=("1y",))
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "1y" in str(exc)
    monitor.close()
