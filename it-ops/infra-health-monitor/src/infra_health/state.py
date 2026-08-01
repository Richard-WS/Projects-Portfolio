"""Persistent per-check state.

A small JSON file records the last observed status of every check, when that
status started, and whether an SLO breach is currently flagged. The monitor
uses it to detect up/down transitions across restarts and to deduplicate SLO
alerts, so a cron-driven setup never re-alerts on every invocation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            return {}

    def get(self, check_name: str, key: str, default=None):
        return self._data.get(check_name, {}).get(key, default)

    def set(self, check_name: str, key: str, value) -> None:
        self._data.setdefault(check_name, {})[key] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)
