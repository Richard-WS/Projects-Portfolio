"""The query catalog: parsing and execution.

``03_analytics.sql`` is a runnable, documented catalog. Each query block
starts with a header the parser reads::

    -- query: <name>
    -- title: <short title>
    -- question: <what it answers>
    -- technique: <SQL techniques used>

The loader splits the file at ``-- query:`` markers and keeps the metadata
plus the SQL body, so the catalog stays human-readable SQL with no separate
registry to keep in sync.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pandas as pd

_QUERY_MARKER = re.compile(r"^-- query: (\S+)\s*$")
_META_FIELD = re.compile(r"^-- (title|question|technique):\s*(.*)$")
_SEPARATOR = re.compile(r"^--\s*[=\-]{4,}\s*$")

_ANALYTICS_FILE = "03_analytics.sql"


@dataclass
class CatalogQuery:
    name: str
    title: str
    question: str
    technique: str
    sql: str


def parse_catalog(sql_text: str) -> list[CatalogQuery]:
    """Parse the analytics SQL file into ordered catalog entries.

    The header block is every comment line between the ``-- query:`` marker
    and the first SQL statement: metadata lines (``-- title:`` etc.), their
    wrapped continuations, and separator lines. Once the first non-comment
    line appears, everything else is the query body (including any inline
    comments).
    """
    lines = sql_text.splitlines()
    entries: list[CatalogQuery] = []
    current: dict | None = None
    body: list[str] = []
    body_started = False

    def flush() -> None:
        nonlocal current, body, body_started
        if current is not None:
            entries.append(
                CatalogQuery(
                    name=current["name"],
                    title=current.get("title", ""),
                    question=current.get("question", ""),
                    technique=current.get("technique", ""),
                    sql="\n".join(body).strip(),
                )
            )
        current = None
        body = []
        body_started = False

    for line in lines:
        marker = _QUERY_MARKER.match(line)
        if marker:
            flush()
            current = {"name": marker.group(1)}
            continue
        if current is None:
            continue  # preamble comments before the first marker
        if body_started:
            body.append(line)
            continue
        if _SEPARATOR.match(line):
            continue
        meta = _META_FIELD.match(line)
        if meta:
            current[meta.group(1)] = meta.group(2).strip()
            current["_last"] = meta.group(1)
            continue
        if line.startswith("--"):
            # Wrapped continuation of the previous metadata field.
            if current.get("_last"):
                key = current["_last"]
                current[key] = f"{current[key]} {line[2:].strip()}".strip()
            continue
        body_started = True
        body.append(line)
    flush()
    return entries


def load_catalog(sql_dir: str | Path) -> list[CatalogQuery]:
    return parse_catalog((Path(sql_dir) / _ANALYTICS_FILE).read_text(encoding="utf-8"))


def catalog_names(catalog: list[CatalogQuery]) -> set[str]:
    return {entry.name for entry in catalog}


def run_query(conn: sqlite3.Connection, entry: CatalogQuery) -> pd.DataFrame:
    """Execute one catalog query and return its results as a DataFrame."""
    return pd.read_sql_query(entry.sql, conn)


def iter_catalog(conn: sqlite3.Connection, catalog: list[CatalogQuery]) -> Iterator[tuple[CatalogQuery, pd.DataFrame]]:
    """Yield (entry, result) pairs for every catalog query."""
    for entry in catalog:
        yield entry, run_query(conn, entry)
