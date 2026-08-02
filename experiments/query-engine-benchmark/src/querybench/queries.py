"""The six benchmark queries, implemented natively in each engine.

Every query is written the way an experienced user of that engine would write
it — pandas idioms, Polars expressions, and SQL for DuckDB. Results are
canonicalized to sorted row tuples so they can be compared across engines.

The queries::

    q1_filter_sum        total revenue, one region
    q2_groupby           total revenue by category
    q3_multi_groupby     count / avg price / total qty by region x category
    q4_join              orders x customers, revenue by customer tier
    q5_topn              top 10 customers by spend
    q6_monthly_revenue   total revenue by month
"""
from __future__ import annotations

import math
from typing import Callable

import duckdb
import numpy as np
import pandas as pd
import polars as pl

ENGINES = ("pandas", "polars", "duckdb")

_REL_TOL = 1e-6
_ABS_TOL = 1e-6


def load_context(engine: str, orders_path: str, customers_path: str, fmt: str):
    """Load both tables into the engine's native in-memory form."""
    if engine == "pandas":
        if fmt == "csv":
            return (pd.read_csv(orders_path), pd.read_csv(customers_path))
        return (pd.read_parquet(orders_path), pd.read_parquet(customers_path))
    if engine == "polars":
        if fmt == "csv":
            return (pl.read_csv(orders_path), pl.read_csv(customers_path))
        return (pl.read_parquet(orders_path), pl.read_parquet(customers_path))
    if engine == "duckdb":
        conn = duckdb.connect()
        if fmt == "csv":
            conn.execute(f"CREATE TABLE orders AS SELECT * FROM read_csv_auto('{orders_path}')")
            conn.execute(f"CREATE TABLE customers AS SELECT * FROM read_csv_auto('{customers_path}')")
        else:
            conn.execute(f"CREATE TABLE orders AS SELECT * FROM read_parquet('{orders_path}')")
            conn.execute(f"CREATE TABLE customers AS SELECT * FROM read_parquet('{customers_path}')")
        return conn
    raise ValueError(f"unknown engine: {engine!r}")


def run_query(name: str, engine: str, ctx) -> list[tuple]:
    """Execute ``name`` on ``ctx`` and return its rows."""
    return QUERY_IMPLS[name][engine](ctx)


# ── pandas ────────────────────────────────────────────────────────────────

def _pandas_q1(ctx):
    orders, _ = ctx
    revenue = orders["price"] * orders["quantity"]
    return pd.DataFrame({"total": [revenue[orders["region"] == "West"].sum()]})


def _pandas_q2(ctx):
    orders, _ = ctx
    revenue = orders["price"] * orders["quantity"]
    return (
        orders.assign(revenue=revenue)
        .groupby("category")["revenue"]
        .sum()
        .reset_index()
    )


def _pandas_q3(ctx):
    orders, _ = ctx
    revenue = orders["price"] * orders["quantity"]
    return (
        orders.assign(revenue=revenue)
        .groupby(["region", "category"])
        .agg(count=("order_id", "count"), avg_price=("price", "mean"), total_qty=("quantity", "sum"))
        .reset_index()
    )


def _pandas_q4(ctx):
    orders, customers = ctx
    revenue = orders["price"] * orders["quantity"]
    return (
        orders.assign(revenue=revenue)
        .merge(customers, on="customer_id")
        .groupby("tier")["revenue"]
        .sum()
        .reset_index()
    )


def _pandas_q5(ctx):
    orders, _ = ctx
    revenue = orders["price"] * orders["quantity"]
    return (
        orders.assign(revenue=revenue)
        .groupby("customer_id")["revenue"]
        .sum()
        .reset_index()
        .sort_values(["revenue", "customer_id"], ascending=[False, True])
        .head(10)
    )


def _pandas_q6(ctx):
    orders, _ = ctx
    revenue = orders["price"] * orders["quantity"]
    return (
        orders.assign(revenue=revenue, month=orders["order_date"].str.slice(0, 7))
        .groupby("month")["revenue"]
        .sum()
        .reset_index()
    )


# ── Polars ────────────────────────────────────────────────────────────────

def _polars_q1(ctx):
    orders, _ = ctx
    return orders.filter(pl.col("region") == "West").select(
        (pl.col("price") * pl.col("quantity")).sum().alias("total")
    )


def _polars_q2(ctx):
    orders, _ = ctx
    return (
        orders.with_columns(revenue=pl.col("price") * pl.col("quantity"))
        .group_by("category")
        .agg(pl.col("revenue").sum())
        .sort("category")
    )


def _polars_q3(ctx):
    orders, _ = ctx
    return (
        orders.with_columns(revenue=pl.col("price") * pl.col("quantity"))
        .group_by("region", "category")
        .agg(
            count=pl.len(),
            avg_price=pl.col("price").mean(),
            total_qty=pl.col("quantity").sum(),
        )
        .sort(["region", "category"])
    )


def _polars_q4(ctx):
    orders, customers = ctx
    return (
        orders.join(customers, on="customer_id")
        .with_columns(revenue=pl.col("price") * pl.col("quantity"))
        .group_by("tier")
        .agg(pl.col("revenue").sum())
        .sort("tier")
    )


def _polars_q5(ctx):
    orders, _ = ctx
    return (
        orders.with_columns(revenue=pl.col("price") * pl.col("quantity"))
        .group_by("customer_id")
        .agg(pl.col("revenue").sum())
        .sort(["revenue", "customer_id"], descending=[True, False])
        .head(10)
    )


def _polars_q6(ctx):
    orders, _ = ctx
    return (
        orders.with_columns(
            revenue=pl.col("price") * pl.col("quantity"),
            month=pl.col("order_date").str.slice(0, 7),
        )
        .group_by("month")
        .agg(pl.col("revenue").sum())
        .sort("month")
    )


# ── DuckDB ────────────────────────────────────────────────────────────────

def _duckdb_q1(ctx):
    return ctx.execute(
        "SELECT SUM(price * quantity) AS total FROM orders WHERE region = 'West'"
    ).fetchall()


def _duckdb_q2(ctx):
    return ctx.execute(
        "SELECT category, SUM(price * quantity) AS revenue FROM orders "
        "GROUP BY category ORDER BY category"
    ).fetchall()


def _duckdb_q3(ctx):
    return ctx.execute(
        "SELECT region, category, COUNT(*) AS count, AVG(price) AS avg_price, "
        "SUM(quantity) AS total_qty FROM orders GROUP BY region, category "
        "ORDER BY region, category"
    ).fetchall()


def _duckdb_q4(ctx):
    return ctx.execute(
        "SELECT c.tier, SUM(o.price * o.quantity) AS revenue FROM orders o "
        "JOIN customers c ON o.customer_id = c.customer_id "
        "GROUP BY c.tier ORDER BY c.tier"
    ).fetchall()


def _duckdb_q5(ctx):
    return ctx.execute(
        "SELECT customer_id, SUM(price * quantity) AS revenue FROM orders "
        "GROUP BY customer_id ORDER BY revenue DESC, customer_id LIMIT 10"
    ).fetchall()


def _duckdb_q6(ctx):
    return ctx.execute(
        "SELECT substr(CAST(order_date AS VARCHAR), 1, 7) AS month, "
        "SUM(price * quantity) AS revenue FROM orders "
        "GROUP BY month ORDER BY month"
    ).fetchall()


QUERY_IMPLS: dict[str, dict[str, Callable]] = {
    "q1_filter_sum": {"pandas": _pandas_q1, "polars": _polars_q1, "duckdb": _duckdb_q1},
    "q2_groupby": {"pandas": _pandas_q2, "polars": _polars_q2, "duckdb": _duckdb_q2},
    "q3_multi_groupby": {"pandas": _pandas_q3, "polars": _polars_q3, "duckdb": _duckdb_q3},
    "q4_join": {"pandas": _pandas_q4, "polars": _polars_q4, "duckdb": _duckdb_q4},
    "q5_topn": {"pandas": _pandas_q5, "polars": _polars_q5, "duckdb": _duckdb_q5},
    "q6_monthly_revenue": {"pandas": _pandas_q6, "polars": _polars_q6, "duckdb": _duckdb_q6},
}


# ── Result comparison ─────────────────────────────────────────────────────

def to_rows(result) -> list[tuple]:
    """Any engine's result → list of plain Python tuples."""
    if isinstance(result, pd.DataFrame):
        return [tuple(_py(v) for v in row) for row in result.itertuples(index=False, name=None)]
    if isinstance(result, pl.DataFrame):
        return [tuple(_py(v) for v in row) for row in result.rows()]
    return [tuple(_py(v) for v in row) for row in result]


def _py(value):
    if isinstance(value, np.generic):
        return value.item()
    return value


def _row_key(row: tuple) -> tuple:
    return tuple(("s", v) if isinstance(v, str) else ("n", float(v)) for v in row)


def sorted_rows(result) -> list[tuple]:
    return sorted(to_rows(result), key=_row_key)


def assert_equivalent(result_a, result_b, label: str = "") -> None:
    """Assert two engines' results match, floats within a tolerance."""
    rows_a = sorted_rows(result_a)
    rows_b = sorted_rows(result_b)
    if len(rows_a) != len(rows_b):
        raise AssertionError(f"{label}: row counts differ ({len(rows_a)} vs {len(rows_b)})")
    for i, (row_a, row_b) in enumerate(zip(rows_a, rows_b)):
        if len(row_a) != len(row_b):
            raise AssertionError(f"{label}: row {i} has {len(row_a)} vs {len(row_b)} columns")
        for j, (va, vb) in enumerate(zip(row_a, row_b)):
            if isinstance(va, float) or isinstance(vb, float):
                if not math.isclose(float(va), float(vb), rel_tol=_REL_TOL, abs_tol=_ABS_TOL):
                    raise AssertionError(f"{label}: row {i} col {j}: {va!r} != {vb!r}")
            elif va != vb:
                raise AssertionError(f"{label}: row {i} col {j}: {va!r} != {vb!r}")
