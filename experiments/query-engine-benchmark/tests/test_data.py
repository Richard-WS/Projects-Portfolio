from __future__ import annotations

import numpy as np
import pandas as pd

from querybench.data import (
    CATEGORIES,
    CUSTOMER_COLUMNS,
    ORDER_COLUMNS,
    REGIONS,
    TIERS,
    generate_and_write,
    generate_tables,
)


def test_deterministic_same_seed():
    a = generate_tables(500, 40, seed=3)
    b = generate_tables(500, 40, seed=3)
    assert np.array_equal(a.orders["order_id"], b.orders["order_id"])
    assert np.array_equal(a.orders["price"], b.orders["price"])
    assert np.array_equal(a.customers["tier"], b.customers["tier"])


def test_different_seed_changes_data():
    a = generate_tables(500, 40, seed=3)
    b = generate_tables(500, 40, seed=4)
    assert not np.array_equal(a.orders["price"], b.orders["price"])


def test_chunk_size_only_changes_stream_not_validity():
    # Bounded draws (integers/choice) use rejection sampling, so chunk
    # boundaries legitimately change the values — but both must be valid.
    small = generate_tables(500, 40, seed=3, chunk_size=100)
    big = generate_tables(500, 40, seed=3, chunk_size=100_000)
    for tables in (small, big):
        assert len(tables.orders["order_id"]) == 500
        assert tables.orders["customer_id"].min() >= 1
        assert tables.orders["customer_id"].max() <= 40
        assert set(tables.orders["category"]).issubset(CATEGORIES)


def test_in_memory_matches_disk_same_chunk_size(tmp_path):
    """Same seed + same chunk size ⇒ identical data in memory and on disk."""
    tables = generate_tables(500, 40, seed=3, chunk_size=100)
    generate_and_write(
        tmp_path / "orders.parquet",
        tmp_path / "customers.parquet",
        n_orders=500,
        n_customers=40,
        seed=3,
        fmt="parquet",
        chunk_size=100,
    )
    df = pd.read_parquet(tmp_path / "orders.parquet")
    for col in ORDER_COLUMNS:
        assert (df[col].to_numpy() == tables.orders[col]).all()


def test_schema_shape():
    tables = generate_tables(1000, 50, seed=1)
    assert list(tables.orders.keys()) == ORDER_COLUMNS
    assert list(tables.customers.keys()) == CUSTOMER_COLUMNS
    assert len(tables.orders["order_id"]) == 1000
    assert len(tables.customers["customer_id"]) == 50
    assert tables.orders["order_id"].dtype == np.int64
    assert tables.orders["price"].dtype == np.float64
    assert tables.orders["customer_id"].min() >= 1
    assert tables.orders["customer_id"].max() <= 50
    assert set(tables.orders["category"]).issubset(CATEGORIES)
    assert set(tables.orders["region"]).issubset(REGIONS)
    assert set(tables.customers["tier"]).issubset(TIERS)
    assert all(len(d) == 10 for d in tables.orders["order_date"])
    assert all(d.startswith("202") for d in tables.orders["order_date"])


def test_write_roundtrip_both_formats(tmp_path):
    tables = generate_tables(500, 40, seed=5, chunk_size=200)
    for fmt in ("parquet", "csv"):
        ext = "parquet" if fmt == "parquet" else "csv"
        orders_path = tmp_path / f"orders.{ext}"
        customers_path = tmp_path / f"customers.{ext}"
        generate_and_write(
            orders_path,
            customers_path,
            n_orders=500,
            n_customers=40,
            seed=5,
            fmt=fmt,
            chunk_size=200,
        )
        df = pd.read_csv(orders_path) if fmt == "csv" else pd.read_parquet(orders_path)
        assert len(df) == 500
        assert list(df.columns) == ORDER_COLUMNS
        assert np.isclose(df["price"].sum(), tables.orders["price"].sum())
        cust = pd.read_csv(customers_path) if fmt == "csv" else pd.read_parquet(customers_path)
        assert len(cust) == 40
        assert list(cust.columns) == CUSTOMER_COLUMNS


def test_samples_written(tmp_path):
    generate_and_write(
        tmp_path / "orders.parquet",
        tmp_path / "customers.parquet",
        sample_orders_path=tmp_path / "orders_sample.csv",
        sample_customers_path=tmp_path / "customers_sample.csv",
        n_orders=1000,
        n_customers=50,
        seed=9,
        fmt="parquet",
        sample_rows=25,
    )
    sample = pd.read_csv(tmp_path / "orders_sample.csv")
    assert len(sample) == 25
    assert list(sample.columns) == ORDER_COLUMNS
    # sample rows must be the first rows of the dataset
    full = pd.read_parquet(tmp_path / "orders.parquet")
    assert sample["order_id"].tolist() == full["order_id"].head(25).tolist()
