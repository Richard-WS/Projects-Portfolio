"""SQLite-backed check history.

One row per check result. Timestamps are UTC ISO-8601 strings, which sort
lexicographically, so window queries are simple string comparisons on the
ts column. The database lives outside the repo (gitignored); small exports
can be committed as samples via ``export_csv``.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable

from infra_health.checks import CheckResult


def uptime_percent(passed: int, total: int) -> float | None:
    """Uptime as a percentage, or None when there is no data to measure."""
    if total <= 0:
        return None
    return passed / total * 100.0


class HistoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_name TEXT NOT NULL,
                check_type TEXT NOT NULL,
                ts TEXT NOT NULL,
                ok INTEGER NOT NULL,
                latency_ms REAL,
                detail TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_results_name_ts ON results(check_name, ts)"
        )
        self._conn.commit()

    def record_many(self, results: Iterable[CheckResult]) -> int:
        """Insert results and return how many rows were written."""
        rows = [
            (r.name, r.check_type, r.ts, int(r.ok), r.latency_ms, r.detail)
            for r in results
        ]
        if not rows:
            return 0
        self._conn.executemany(
            "INSERT INTO results (check_name, check_type, ts, ok, latency_ms, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def summary(self, since_iso: str) -> dict[str, tuple[int, int]]:
        """Return {check_name: (total, passed)} for rows with ts >= since_iso."""
        cur = self._conn.execute(
            "SELECT check_name, COUNT(*), COALESCE(SUM(ok), 0) FROM results "
            "WHERE ts >= ? GROUP BY check_name",
            (since_iso,),
        )
        return {row[0]: (int(row[1]), int(row[2])) for row in cur.fetchall()}

    def failures(self, limit: int = 50) -> list[dict]:
        """Most recent failed results, newest first."""
        cur = self._conn.execute(
            "SELECT check_name, check_type, ts, detail FROM results "
            "WHERE ok = 0 ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {"name": row[0], "type": row[1], "ts": row[2], "detail": row[3]}
            for row in cur.fetchall()
        ]

    def export_csv(self, path: str | Path) -> int:
        """Write the full history as CSV and return the number of rows."""
        rows = self._conn.execute(
            "SELECT ts, check_name, check_type, ok, latency_ms, detail "
            "FROM results ORDER BY id"
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["ts", "check_name", "check_type", "ok", "latency_ms", "detail"])
            writer.writerows(rows)
        return len(rows)

    def close(self) -> None:
        self._conn.close()
