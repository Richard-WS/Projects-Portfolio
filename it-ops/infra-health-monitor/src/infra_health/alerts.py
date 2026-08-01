"""Alerting: console logging plus an optional webhook notifier.

Alerts are plain JSON payloads, so a generic webhook (Slack/Teams or a small
relay) can consume them. A failed webhook delivery never crashes the monitor
— it is logged and the next alert retries.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from infra_health.checks import CheckResult


class AlertLogger:
    """Logger for all monitor output; level comes from the config."""

    def __init__(self, level: str = "info"):
        self._logger = logging.getLogger("infra-health")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
            self._logger.addHandler(handler)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)


def build_payload(alert_type: str, result: CheckResult, extra: str | None = None) -> dict:
    """Shape the alert payload sent to logs and webhooks."""
    payload = {
        "alert": alert_type,
        "check": result.name,
        "type": result.check_type,
        "ts": result.ts,
        "detail": result.detail,
    }
    if extra:
        payload["message"] = extra
    return payload


class WebhookNotifier:
    def __init__(self, url: str, logger: AlertLogger):
        self.url = url
        self.log = logger

    def send(self, payload: dict) -> bool:
        """POST the payload as JSON; return True on a 2xx response."""
        try:
            body = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                self.url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as resp:
                status = resp.status
            self.log.info(f"webhook delivered (HTTP {status})")
            return True
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.log.warning(f"webhook failed: {exc.__class__.__name__}: {exc}")
            return False
