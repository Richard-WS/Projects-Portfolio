"""History store tests: recording, window summaries, exports."""
from __future__ import annotations

import csv

from infra_health.checks import CheckResult
from infra_health.history import HistoryStore, uptime_percent


def _result(name, ok, ts, detail="", latency=1.0):
    return CheckResult(name=name, check_type="http", ok=ok, ts=ts, latency_ms=latency, detail=detail)


def test_record_and_window_summary(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.record_many(
        [
            _result("a", True, "2026-08-01T10:00:00+00:00"),
            _result("a", False, "2026-08-01T10:00:01+00:00"),
            _result("b", True, "2026-08-01T10:00:02+00:00"),
        ]
    )
    assert store.summary("2026-08-01T10:00:00+00:00") == {"a": (2, 1), "b": (1, 1)}
    # Window starting after the first row excludes it.
    assert store.summary("2026-08-01T10:00:01+00:00") == {"a": (1, 0), "b": (1, 1)}
    store.close()


def test_record_empty_is_noop(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    assert store.record_many([]) == 0
    assert store.summary("2000-01-01T00:00:00+00:00") == {}
    store.close()


def test_uptime_percent():
    assert uptime_percent(0, 0) is None
    assert uptime_percent(3, 4) == 75.0
    assert uptime_percent(4, 4) == 100.0


def test_failures_newest_first(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.record_many(
        [
            _result("a", True, "2026-08-01T10:00:00+00:00"),
            _result("a", False, "2026-08-01T10:00:01+00:00", detail="first failure"),
            _result("b", False, "2026-08-01T10:00:02+00:00", detail="second failure"),
            _result("b", True, "2026-08-01T10:00:03+00:00"),
        ]
    )
    failures = store.failures()
    assert [f["detail"] for f in failures] == ["second failure", "first failure"]
    assert failures[0]["name"] == "b"
    assert len(store.failures(limit=1)) == 1
    store.close()


def test_export_csv(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.record_many(
        [
            _result("a", True, "2026-08-01T10:00:00+00:00", detail="HTTP 200 in 3ms", latency=3.1),
            _result("a", False, "2026-08-01T10:00:01+00:00", detail="HTTP 503"),
        ]
    )
    out = tmp_path / "export.csv"
    assert store.export_csv(out) == 2
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["ts", "check_name", "check_type", "ok", "latency_ms", "detail"]
    assert rows[1][1] == "a" and rows[1][3] == "1" and rows[1][5] == "HTTP 200 in 3ms"
    assert rows[2][3] == "0"
    store.close()


def test_persists_across_instances(tmp_path):
    db = tmp_path / "h.db"
    first = HistoryStore(db)
    first.record_many([_result("a", True, "2026-08-01T10:00:00+00:00")])
    first.close()
    second = HistoryStore(db)
    assert second.summary("2000-01-01T00:00:00+00:00")["a"] == (1, 1)
    second.close()
