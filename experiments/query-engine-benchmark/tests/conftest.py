"""Shared fixtures: tiny deterministic tables, written to disk in both formats."""
from __future__ import annotations

import pytest

from querybench.data import generate_and_write, generate_tables

N_ORDERS = 800
N_CUSTOMERS = 120


@pytest.fixture(scope="session")
def tiny_tables():
    return generate_tables(N_ORDERS, N_CUSTOMERS, seed=7, chunk_size=100)


@pytest.fixture
def data_files(tmp_path, tiny_tables):
    """orders/customers written as parquet AND csv in a temp dir."""
    generate_and_write(
        tmp_path / "orders.parquet",
        tmp_path / "customers.parquet",
        n_orders=N_ORDERS,
        n_customers=N_CUSTOMERS,
        seed=7,
        fmt="parquet",
        chunk_size=100,
    )
    generate_and_write(
        tmp_path / "orders.csv",
        tmp_path / "customers.csv",
        n_orders=N_ORDERS,
        n_customers=N_CUSTOMERS,
        seed=7,
        fmt="csv",
        chunk_size=100,
    )
    return tmp_path
