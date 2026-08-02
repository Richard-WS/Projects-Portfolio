"""Timing and memory measurement helpers."""
from __future__ import annotations

import platform
import resource
import time
from typing import Callable


def median(values: list[float]) -> float:
    """Median of a non-empty list."""
    if not values:
        raise ValueError("median() of an empty list")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def time_query(fn: Callable[[], object], warmup: int = 1, runs: int = 3) -> float:
    """Wall-clock time for ``fn`` in ms, reported as the median of ``runs``."""
    for _ in range(warmup):
        fn()
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - start) * 1000.0)
    return median(timings)


def peak_rss_mb() -> float:
    """Peak resident set size of this process, in MiB."""
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Linux":
        return rss_kb / 1024.0
    return rss_kb / (1024.0 * 1024.0)
