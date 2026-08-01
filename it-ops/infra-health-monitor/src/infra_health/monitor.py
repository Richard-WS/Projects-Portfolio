"""Monitor orchestration.

The Monitor ties everything together: it runs the configured checks, records
every result in the history store, evaluates state transitions and SLO
compliance, emits alerts, and answers summary queries used by the report.
"""
from __future__ import annotations

import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable

from infra_health.alerts import AlertLogger, WebhookNotifier, build_payload
from infra_health.checks import CheckResult, run_check
from infra_health.config import CheckConfig, Config
from infra_health.history import HistoryStore, uptime_percent
from infra_health.state import StateStore

WINDOW_SECONDS = {
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "30d": 30 * 24 * 3600,
}

_UP = "up"
_DOWN = "down"
_UNKNOWN = "unknown"


class Monitor:
    """Runs checks, records results, evaluates alerts, and answers summary queries."""

    def __init__(
        self,
        config: Config,
        history_path: str | None = None,
        state_path: str | None = None,
        webhook_url: str | None = None,
        logger: AlertLogger | None = None,
    ):
        self.config = config
        self.history = HistoryStore(history_path or config.history_path)
        self.state = StateStore(state_path or config.state_path)
        self.log = logger or AlertLogger(config.alerts.log_level)
        env_webhook = os.environ.get(config.alerts.webhook_url_env)
        webhook = webhook_url or env_webhook
        self.notifier = WebhookNotifier(webhook, self.log) if webhook else None
        self._by_name = {c.name: c for c in config.checks}

    # ── running ────────────────────────────────────────────────────────────

    def run_once(self, checks: Iterable[CheckConfig] | None = None) -> list[CheckResult]:
        """Run the given checks (or all of them), record results, alert."""
        to_run = list(checks) if checks is not None else self.config.checks
        results = [run_check(cfg) for cfg in to_run]
        self.history.record_many(results)
        for result in results:
            self._evaluate_alerts(result)
        self.state.save()
        return results

    def run_loop(self, iterations: int | None = None, round_interval: float = 1.0) -> list[CheckResult]:
        """Run due checks every ``round_interval`` seconds until interrupted.

        Each check runs when its own ``interval_seconds`` has elapsed, so a
        single loop can host checks with different frequencies. With
        ``iterations`` set, the loop stops after that many rounds (useful for
        demos and smoke tests); by default it runs until interrupted.
        """
        last_run: dict[str, float] = {}
        collected: list[CheckResult] = []
        rounds = 0
        while iterations is None or rounds < iterations:
            now = time.monotonic()
            due = [
                cfg
                for cfg in self.config.checks
                if now - last_run.get(cfg.name, -math.inf) >= cfg.interval_seconds
            ]
            if due:
                collected.extend(self.run_once(due))
                for cfg in due:
                    last_run[cfg.name] = now
            rounds += 1
            if iterations is None or rounds < iterations:
                time.sleep(round_interval)
        return collected

    # ── alerts ─────────────────────────────────────────────────────────────

    def _evaluate_alerts(self, result: CheckResult) -> None:
        cfg = self._by_name[result.name]
        prev = self.state.get(result.name, "state", _UNKNOWN)
        current = _UP if result.ok else _DOWN

        if prev == _UNKNOWN:
            # First observation: alert only if the check is already down.
            if not result.ok:
                self._emit(result, "DOWN")
        elif prev != current:
            self._emit(result, "RECOVERED" if result.ok else "DOWN")
        self.state.set(result.name, "state", current)
        if self.state.get(result.name, "since") is None:
            self.state.set(result.name, "since", result.ts)

        # SLO compliance over the trailing 24-hour window.
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
        total, passed = self.history.summary(since).get(result.name, (0, 0))
        uptime = uptime_percent(passed, total)
        was_breached = bool(self.state.get(result.name, "slo_breached", False))
        if uptime is not None and uptime < cfg.slo_percent and not was_breached:
            self._emit(
                result,
                "SLO_BREACH",
                extra=(
                    f"uptime {uptime:.1f}% below the {cfg.slo_percent:.1f}% SLO "
                    f"(24h window, {passed}/{total} passes)"
                ),
            )
            self.state.set(result.name, "slo_breached", True)
        elif uptime is not None and uptime >= cfg.slo_percent and was_breached:
            self._emit(result, "SLO_CLEARED", extra=f"uptime back to {uptime:.1f}%")
            self.state.set(result.name, "slo_breached", False)

    def _emit(self, result: CheckResult, alert_type: str, extra: str | None = None) -> None:
        payload = build_payload(alert_type, result, extra=extra)
        message = f"[{alert_type}] {result.name} ({result.check_type}): {result.detail}"
        if extra:
            message += f" — {extra}"
        if alert_type in ("DOWN", "SLO_BREACH"):
            self.log.warning(message)
        else:
            self.log.info(message)
        if self.notifier:
            self.notifier.send(payload)

    # ── reporting ──────────────────────────────────────────────────────────

    def summary(self, windows: tuple[str, ...] = ("24h", "7d", "30d")) -> list[dict]:
        """Per-check summary: uptime per window, current status, downtime math.

        Downtime is estimated as failed checks multiplied by the check's
        configured interval; the SLO budget is the allowed downtime over
        30 days (``(1 - SLO) * 30d``) minus the estimate.
        """
        unknown = set(windows) - set(WINDOW_SECONDS)
        if unknown:
            raise ValueError(f"unknown window(s): {sorted(unknown)}")
        now = datetime.now(timezone.utc)
        rows = []
        for cfg in self.config.checks:
            window_data = {}
            for label in windows:
                since = (now - timedelta(seconds=WINDOW_SECONDS[label])).isoformat(timespec="seconds")
                total, passed = self.history.summary(since).get(cfg.name, (0, 0))
                uptime = uptime_percent(passed, total)
                window_data[label] = {
                    "total": total,
                    "passed": passed,
                    "uptime": uptime,
                    "breached": None if uptime is None else uptime < cfg.slo_percent,
                }
            status = self.state.get(cfg.name, "state", _UNKNOWN)
            failed_30d = window_data.get("30d", {}).get("total", 0) - window_data.get("30d", {}).get("passed", 0)
            est_downtime_s = failed_30d * cfg.interval_seconds
            budget_s = (1.0 - cfg.slo_percent / 100.0) * WINDOW_SECONDS["30d"]
            rows.append(
                {
                    "name": cfg.name,
                    "type": cfg.type,
                    "status": status,
                    "windows": window_data,
                    "slo_percent": cfg.slo_percent,
                    "est_downtime_s": est_downtime_s,
                    "budget_remaining_s": budget_s - est_downtime_s,
                }
            )
        return rows

    def close(self) -> None:
        self.history.close()
