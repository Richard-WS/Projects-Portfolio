#!/usr/bin/env python3
"""Run a short live demo of the monitor against local demo services.

Starts a healthy HTTP endpoint, a flaky one (fails its first five requests),
a TCP listener, and a worker process (stopped and restarted partway through),
then runs 20 rounds of checks. The resulting history is exported to a
committed sample CSV and a self-contained HTML report.

Run from the project root:  python scripts/run_demo.py
"""
from __future__ import annotations

import http.server
import logging
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from infra_health.config import CheckConfig, Config  # noqa: E402
from infra_health.monitor import Monitor  # noqa: E402
from infra_health.report import format_summary_table, render_html, utc_now_str  # noqa: E402

ROUNDS = 20


class _TextHandler(http.server.BaseHTTPRequestHandler):
    status = 200
    body = b"ok"

    def do_GET(self):  # noqa: N802 (http.server API)
        self.send_response(self.status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, format, *args):  # keep demo output clean  # noqa: A002
        pass


class _FlakyHandler(_TextHandler):
    failures_left = 5

    def do_GET(self):  # noqa: N802
        if _FlakyHandler.failures_left > 0:
            _FlakyHandler.failures_left -= 1
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(b"degraded")))
            self.end_headers()
            self.wfile.write(b"degraded")
        else:
            super().do_GET()


def _start_tcp_listener() -> socket.socket:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(8)

    def _accept_loop() -> None:
        while True:
            try:
                conn, _ = server.accept()
                conn.close()
            except OSError:
                return

    threading.Thread(target=_accept_loop, daemon=True).start()
    return server


def main() -> int:
    print("infra-health demo — starting local services...")
    healthy = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _TextHandler)
    flaky = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FlakyHandler)
    for server in (healthy, flaky):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    tcp = _start_tcp_listener()
    worker = subprocess.Popen(["sleep", "120"])

    raw_dir = ROOT / "data" / "raw" / "demo"
    raw_dir.mkdir(parents=True, exist_ok=True)

    checks = [
        CheckConfig(name="api-gateway", type="http", url=f"http://127.0.0.1:{flaky.server_port}/health",
                    interval_seconds=1, timeout_seconds=3, slo_percent=99.9),
        CheckConfig(name="auth-service", type="http", url=f"http://127.0.0.1:{healthy.server_port}/health",
                    expected_text="ok", interval_seconds=1, timeout_seconds=3, slo_percent=99.9),
        CheckConfig(name="database-port", type="tcp", host="127.0.0.1", port=tcp.getsockname()[1],
                    interval_seconds=1, timeout_seconds=3, slo_percent=99.5),
        CheckConfig(name="web-disk", type="disk", path=str(ROOT),
                    critical_percent=95, interval_seconds=1, slo_percent=99.9),
        CheckConfig(name="demo-worker", type="process", process_name="sleep",
                    interval_seconds=1, slo_percent=99.9),
    ]
    config = Config(
        checks=checks,
        history_path=str(raw_dir / "history.db"),
        state_path=str(raw_dir / "state.json"),
    )

    monitor = Monitor(config)

    # Route alert log lines to stdout so they are captured in the demo output.
    infra_logger = logging.getLogger("infra-health")
    for handler in list(infra_logger.handlers):
        infra_logger.removeHandler(handler)
    infra_logger.addHandler(logging.StreamHandler(sys.stdout))

    print(f"demo: {len(checks)} checks x {ROUNDS} rounds, 1s interval")
    print()

    for round_no in range(1, ROUNDS + 1):
        if round_no == 11:
            worker.terminate()
            worker.wait()
            print("demo: worker process stopped (simulating a crash)")
        elif round_no == 16:
            worker = subprocess.Popen(["sleep", "120"])
            print("demo: worker process restarted")
        monitor.run_once()
        time.sleep(1)

    for server in (healthy, flaky):
        server.shutdown()
        server.server_close()
    tcp.close()
    if worker.poll() is None:
        worker.terminate()
        worker.wait()

    rows = monitor.summary()
    print()
    print("=" * 78)
    print("SUMMARY (uptime over the samples available in each window)")
    print("=" * 78)
    print(format_summary_table(rows))

    samples_dir = ROOT / "data" / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    count = monitor.history.export_csv(samples_dir / "demo-history.csv")

    report_path = docs_dir / "demo-report.html"
    html_text = render_html(rows, monitor.history.failures(limit=50), utc_now_str())
    report_path.write_text(html_text, encoding="utf-8")

    print()
    print(f"wrote {count} history rows -> data/samples/demo-history.csv")
    print(f"wrote HTML report      -> docs/demo-report.html")
    monitor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
