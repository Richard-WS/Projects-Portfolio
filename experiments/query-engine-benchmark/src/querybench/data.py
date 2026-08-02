"""Synthetic retail dataset generator.

Deterministic (seeded numpy) so benchmarks are reproducible. The generator
writes in chunks, so a multi-million-row dataset never needs to exist in
memory all at once. Column values are simple and inspectable: a handful of
categories, regions, and customer tiers — the kind of shape real sales tables
have, without any real data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

CATEGORIES = [
    "electronics",
    "apparel",
    "grocery",
    "home",
    "sports",
    "books",
    "toys",
    "beauty",
]
REGIONS = ["West", "East", "Central", "South", "North"]
TIERS = ["basic", "plus", "premium"]

ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "product_id",
    "category",
    "region",
    "price",
    "quantity",
    "order_date",
]
CUSTOMER_COLUMNS = ["customer_id", "tier", "signup_date"]

_ORDER_START = np.datetime64("2023-01-01")
_CUSTOMER_START = np.datetime64("2020-01-01")


@dataclass
class Tables:
    orders: dict[str, np.ndarray]
    customers: dict[str, np.ndarray]


def _order_chunk(rng: np.random.Generator, start: int, n: int, n_customers: int) -> dict[str, np.ndarray]:
    days = rng.integers(0, 730, size=n)
    return {
        "order_id": np.arange(start, start + n, dtype=np.int64),
        "customer_id": rng.integers(1, n_customers + 1, size=n, dtype=np.int64),
        "product_id": rng.integers(1, 5001, size=n, dtype=np.int64),
        "category": rng.choice(CATEGORIES, size=n),
        "region": rng.choice(REGIONS, size=n),
        "price": np.round(rng.uniform(1.0, 500.0, size=n), 2),
        "quantity": rng.integers(1, 6, size=n, dtype=np.int64),
        "order_date": (_ORDER_START + days.astype("timedelta64[D]")).astype("datetime64[D]").astype(str),
    }


def _customer_chunk(rng: np.random.Generator, n: int) -> dict[str, np.ndarray]:
    days = rng.integers(0, 1500, size=n)
    return {
        "customer_id": np.arange(1, n + 1, dtype=np.int64),
        "tier": rng.choice(TIERS, size=n, p=[0.6, 0.3, 0.1]),
        "signup_date": (_CUSTOMER_START + days.astype("timedelta64[D]")).astype("datetime64[D]").astype(str),
    }


def _iter_order_chunks(
    rng: np.random.Generator, n_orders: int, n_customers: int, chunk_size: int
):
    start = 0
    while start < n_orders:
        size = min(chunk_size, n_orders - start)
        yield _order_chunk(rng, start, size, n_customers)
        start += size


def generate_tables(
    n_orders: int, n_customers: int, seed: int = 42, chunk_size: int = 1_000_000
) -> Tables:
    """Full in-memory tables (used by tests and sample writing).

    The chunk generator is consumed exactly once, so column values stay
    aligned with each other and independent of the chunk size.
    """
    rng = np.random.default_rng(seed)
    chunks = list(_iter_order_chunks(rng, n_orders, n_customers, chunk_size))
    orders = {col: np.concatenate([c[col] for c in chunks]) for col in ORDER_COLUMNS}
    customers = _customer_chunk(rng, n_customers)
    return Tables(orders=orders, customers=customers)


class _ParquetSink:
    def __init__(self, path: Path, first_chunk: dict[str, np.ndarray]):
        self._writer = pq.ParquetWriter(path, pa.Table.from_pydict(first_chunk).schema)

    def write(self, chunk: dict[str, np.ndarray]) -> None:
        self._writer.write_table(pa.Table.from_pydict(chunk))

    def close(self) -> None:
        self._writer.close()


class _CsvSink:
    def __init__(self, path: Path, first_chunk: dict[str, np.ndarray]):
        self._path = path
        self._columns = list(first_chunk.keys())
        self._first = True

    def write(self, chunk: dict[str, np.ndarray]) -> None:
        df = pd.DataFrame({col: chunk[col] for col in self._columns})
        df.to_csv(self._path, mode="a", index=False, header=self._first)
        self._first = False

    def close(self) -> None:
        pass


def _open_sink(fmt: str, path: Path, first_chunk: dict[str, np.ndarray]):
    if fmt == "parquet":
        return _ParquetSink(path, first_chunk)
    if fmt == "csv":
        return _CsvSink(path, first_chunk)
    raise ValueError(f"fmt must be 'parquet' or 'csv', got {fmt!r}")


def generate_and_write(
    orders_path: str | Path,
    customers_path: str | Path,
    sample_orders_path: str | Path | None = None,
    sample_customers_path: str | Path | None = None,
    n_orders: int = 5_000_000,
    n_customers: int = 200_000,
    seed: int = 42,
    fmt: str = "parquet",
    chunk_size: int = 1_000_000,
    sample_rows: int = 2000,
) -> None:
    """Generate the dataset chunk-by-chunk and write it to disk.

    The first ``sample_rows`` of each table are written as plain CSVs for the
    committed ``data/samples/`` directory (provenance: generated from seed).
    """
    orders_path = Path(orders_path)
    customers_path = Path(customers_path)
    orders_path.parent.mkdir(parents=True, exist_ok=True)
    customers_path.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)

    order_chunks = _iter_order_chunks(rng, n_orders, n_customers, chunk_size)
    first = next(order_chunks)
    orders_sink = _open_sink(fmt, orders_path, first)
    sample_orders = {col: first[col][:sample_rows] for col in ORDER_COLUMNS}
    try:
        orders_sink.write(first)
        for chunk in order_chunks:
            orders_sink.write(chunk)
    finally:
        orders_sink.close()

    customers = _customer_chunk(rng, n_customers)
    customers_sink = _open_sink(fmt, customers_path, customers)
    sample_customers = {col: customers[col][:sample_rows] for col in CUSTOMER_COLUMNS}
    try:
        customers_sink.write(customers)
    finally:
        customers_sink.close()

    if sample_orders_path is not None:
        sample_orders_path = Path(sample_orders_path)
        sample_orders_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(sample_orders).to_csv(sample_orders_path, index=False)
    if sample_customers_path is not None:
        sample_customers_path = Path(sample_customers_path)
        sample_customers_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(sample_customers).to_csv(sample_customers_path, index=False)
