"""The core guarantee: all three engines return identical answers.

Every query is run in every engine on both file formats (parquet and csv) and
the outputs are compared pairwise with a float tolerance. If an engine's
native expression for a query is wrong, or silently differs, these tests fail.
"""
from __future__ import annotations

import pytest

from querybench.config import DEFAULT_QUERIES
from querybench.data import CATEGORIES, TIERS
from querybench.queries import ENGINES, assert_equivalent, load_context, run_query, to_rows

ENGINE_PAIRS = [("pandas", "polars"), ("pandas", "duckdb"), ("polars", "duckdb")]


@pytest.mark.parametrize("query", DEFAULT_QUERIES)
@pytest.mark.parametrize("pair", ENGINE_PAIRS)
@pytest.mark.parametrize("fmt", ["parquet", "csv"])
def test_equivalence_across_engines(query, pair, fmt, data_files):
    ext = "parquet" if fmt == "parquet" else "csv"
    ctx_a = load_context(pair[0], data_files / f"orders.{ext}", data_files / f"customers.{ext}", fmt)
    ctx_b = load_context(pair[1], data_files / f"orders.{ext}", data_files / f"customers.{ext}", fmt)
    result_a = run_query(query, pair[0], ctx_a)
    result_b = run_query(query, pair[1], ctx_b)
    assert_equivalent(result_a, result_b, label=f"{query} ({pair[0]} vs {pair[1]}, {fmt})")


@pytest.mark.parametrize("fmt", ["parquet", "csv"])
def test_q1_single_number(fmt, data_files):
    ext = "parquet" if fmt == "parquet" else "csv"
    for engine in ENGINES:
        ctx = load_context(engine, data_files / f"orders.{ext}", data_files / f"customers.{ext}", fmt)
        rows = to_rows(run_query("q1_filter_sum", engine, ctx))
        assert len(rows) == 1
        assert rows[0][0] > 0


@pytest.mark.parametrize("fmt", ["parquet", "csv"])
def test_q2_covers_categories(fmt, data_files):
    ext = "parquet" if fmt == "parquet" else "csv"
    for engine in ENGINES:
        ctx = load_context(engine, data_files / f"orders.{ext}", data_files / f"customers.{ext}", fmt)
        rows = to_rows(run_query("q2_groupby", engine, ctx))
        categories = {row[0] for row in rows}
        assert categories.issubset(set(CATEGORIES))
        assert len(rows) <= len(CATEGORIES)  # tiny data: not every category guaranteed


@pytest.mark.parametrize("fmt", ["parquet", "csv"])
def test_q4_tiers(fmt, data_files):
    ext = "parquet" if fmt == "parquet" else "csv"
    for engine in ENGINES:
        ctx = load_context(engine, data_files / f"orders.{ext}", data_files / f"customers.{ext}", fmt)
        rows = to_rows(run_query("q4_join", engine, ctx))
        tiers = {row[0] for row in rows}
        assert tiers.issubset(set(TIERS))
        assert tiers  # join produced something


@pytest.mark.parametrize("fmt", ["parquet", "csv"])
def test_q5_top10(fmt, data_files):
    ext = "parquet" if fmt == "parquet" else "csv"
    for engine in ENGINES:
        ctx = load_context(engine, data_files / f"orders.{ext}", data_files / f"customers.{ext}", fmt)
        rows = to_rows(run_query("q5_topn", engine, ctx))
        assert len(rows) == 10
        spends = [row[1] for row in rows]
        assert spends == sorted(spends, reverse=True)  # descending order


@pytest.mark.parametrize("fmt", ["parquet", "csv"])
def test_q6_monthly(fmt, data_files):
    ext = "parquet" if fmt == "parquet" else "csv"
    for engine in ENGINES:
        ctx = load_context(engine, data_files / f"orders.{ext}", data_files / f"customers.{ext}", fmt)
        rows = to_rows(run_query("q6_monthly_revenue", engine, ctx))
        assert rows
        for month, _ in rows:
            assert len(month) == 7 and month[4] == "-"
