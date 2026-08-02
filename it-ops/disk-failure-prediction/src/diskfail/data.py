"""Dataset handling for the Backblaze S.M.A.R.T. drive dataset.

The raw quarterly CSV is several GB, so all processing is chunked and the
fleet is sampled down to a configurable number of drives. Two passes over
the file plus a short pre-scan:

1. scan_fleet        — read date/serial/model/capacity/failure only; pick the
                       fleet (every drive that failed in the quarter, plus a
                       seeded sample of healthy drives).
2. detect_attrs      — pre-scan a slice of the file to learn which smart_*_raw
                       columns actually carry data (most of the 255 columns
                       are empty).
3. load_series       — read only those columns for fleet drives, keeping just
                       the rows each drive's feature windows need.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

CORE_COLUMNS = ["date", "serial_number", "model", "capacity_bytes", "failure"]
EPOCH = date(1970, 1, 1)
CHUNK_ROWS = 100_000


@dataclass
class FleetInfo:
    serial: str
    model: str
    capacity_bytes: int
    fail_date: Optional[date]
    first_date: date
    last_date: date
    days_observed: int


@dataclass
class WindowPlan:
    serial: str
    end_day: int  # days since epoch; the window covers [end-window+1, end]
    label: int
    kind: str  # "train" or "leadtime"


@dataclass
class WindowRecord:
    serial: str
    end_day: int
    label: int
    kind: str
    days: np.ndarray  # int days since epoch, ascending
    values: np.ndarray  # (n_days, n_attrs) float32


def read_header(csv_path: Path) -> List[str]:
    opener = gzip.open if str(csv_path).endswith(".gz") else open
    with opener(csv_path, "rt") as fh:
        return fh.readline().strip().split(",")


def source_files(csv_path: Path) -> List[Path]:
    """The raw source is either a single CSV or a directory of daily CSV
    snapshots (Backblaze ships one file per day); return the CSV files in
    date order."""
    if csv_path.is_dir():
        files = sorted(csv_path.glob("*.csv"))
        if not files:
            raise FileNotFoundError(f"no .csv files found in {csv_path}")
        return files
    return [csv_path]


def smart_raw_columns(header: Sequence[str]) -> List[str]:
    return [c for c in header if c.startswith("smart_") and c.endswith("_raw")]


def to_day(d: date | datetime | str) -> int:
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    elif isinstance(d, datetime):
        d = d.date()
    return (d - EPOCH).days


def scan_fleet(
    csv_path: Path, max_drives: Optional[int], seed: int
) -> Dict[str, FleetInfo]:
    """Pass 1: fleet selection — every drive that failed in the quarter plus a
    seeded sample of healthy drives, up to max_drives total (None = all)."""
    rng = np.random.default_rng(seed)
    acc: Dict[str, List] = {}  # serial -> [min_day, max_day, cap, model, any_fail, fail_day]
    dtype = {"serial_number": str, "model": str, "capacity_bytes": np.float64, "failure": np.int8}
    for file in source_files(csv_path):
        df = pd.read_csv(file, usecols=CORE_COLUMNS, dtype=dtype)
        days = pd.to_datetime(df["date"], format="%Y-%m-%d").map(to_day).to_numpy()
        fail = df["failure"].to_numpy()
        fail_day = np.where(fail == 1, days, -1)
        cap = df["capacity_bytes"].to_numpy()
        model = df["model"].to_numpy()
        ser = df["serial_number"].to_numpy()
        for i in range(len(ser)):
            s = ser[i]
            d = days[i]
            if s in acc:
                e = acc[s]
                if d < e[0]:
                    e[0] = d
                if d > e[1]:
                    e[1] = d
                if fail[i]:
                    e[4] = 1
                    if d > e[5]:
                        e[5] = d
            else:
                acc[s] = [d, d, cap[i], model[i], int(fail[i]), int(fail_day[i])]
    fleet = pd.DataFrame(
        [
            {
                "serial_number": s,
                "min_day": e[0],
                "max_day": e[1],
                "cap": e[2],
                "model": e[3],
                "any_fail": e[4],
                "fail_day": e[5],
            }
            for s, e in acc.items()
        ]
    )
    failing = fleet[fleet["any_fail"] == 1]
    healthy = fleet[fleet["any_fail"] == 0]
    if max_drives is None:
        n_healthy = len(healthy)
    else:
        n_healthy = max(max_drives - len(failing), 0)
    if len(healthy) > n_healthy:
        healthy = healthy.sample(n=n_healthy, random_state=seed)
    chosen = pd.concat([failing, healthy], ignore_index=True)

    result: Dict[str, FleetInfo] = {}
    for row in chosen.itertuples(index=False):
        fd = None if row.any_fail != 1 or row.fail_day < 0 else EPOCH + timedelta(days=int(row.fail_day))
        result[row.serial_number] = FleetInfo(
            serial=row.serial_number,
            model=row.model,
            capacity_bytes=int(row.cap) if row.cap == row.cap else 0,
            fail_date=fd,
            first_date=EPOCH + timedelta(days=int(row.min_day)),
            last_date=EPOCH + timedelta(days=int(row.max_day)),
            days_observed=int(row.max_day - row.min_day + 1),
        )
    return result


def detect_attrs(csv_path: Path, threshold: float, max_chunks: int = 50) -> List[str]:
    """Pre-scan: which smart_*_raw columns carry data (missing fraction below
    threshold) in the first portion of the file."""
    header = read_header(source_files(csv_path)[0])
    cands = smart_raw_columns(header)
    if not cands:
        return []
    nulls = np.zeros(len(cands), dtype=np.int64)
    total = 0
    chunks_seen = 0
    for file in source_files(csv_path):
        file_header = read_header(file)
        cols = [c for c in cands if c in file_header]
        if not cols:
            continue
        dtype = {c: np.float32 for c in cols}
        file_rows = 0
        for chunk in pd.read_csv(file, usecols=cols, dtype=dtype, chunksize=CHUNK_ROWS):
            for c in cols:
                nulls[cands.index(c)] += int(chunk[c].isna().sum())
            file_rows += len(chunk)
            chunks_seen += 1
            if chunks_seen >= max_chunks:
                break
        for c in cands:
            if c not in file_header:
                nulls[cands.index(c)] += file_rows
        total += file_rows
        if chunks_seen >= max_chunks:
            break
    frac = nulls / max(total, 1)
    return [c for c, f in zip(cands, frac) if f < threshold]


def plan_windows(
    fleet: Dict[str, FleetInfo],
    window_days: int,
    horizon_days: int,
    leadtime_horizons: Sequence[int],
    seed: int,
) -> Tuple[Dict[str, List[WindowPlan]], Dict[str, List[WindowPlan]]]:
    """Training windows and lead-time analysis windows per drive.

    Failing drives: one training window ending 1..horizon_days before the
    failure date (label 1 — features never see the failure row itself), plus
    one window per lead-time horizon ending that many days before failure.
    Healthy drives: a single seeded-random window ending somewhere inside
    their observed span (label 0).
    """
    rng = np.random.default_rng(seed)
    train: Dict[str, List[WindowPlan]] = {}
    lead: Dict[str, List[WindowPlan]] = {}
    for serial, info in fleet.items():
        if info.fail_date is not None:
            fd = to_day(info.fail_date)
            t = [WindowPlan(serial, fd - k, 1, "train") for k in range(1, horizon_days + 1)]
            l = [
                WindowPlan(serial, fd - h, 1, "leadtime")
                for h in leadtime_horizons
            ]
            train[serial] = t
            lead[serial] = l
        else:
            span = info.days_observed
            if span < window_days:
                continue
            lo = to_day(info.first_date) + window_days
            hi = to_day(info.last_date)
            if hi < lo:
                continue
            end = int(rng.integers(lo, hi + 1))
            train[serial] = [WindowPlan(serial, end, 0, "train")]
            lead[serial] = []
    return train, lead


def load_series(
    csv_path: Path,
    fleet: Dict[str, FleetInfo],
    train_plans: Dict[str, List[WindowPlan]],
    lead_plans: Dict[str, List[WindowPlan]],
    attrs: Sequence[str],
    missing_threshold: float,
    window_days: int,
) -> Tuple[Dict[str, Tuple[np.ndarray, np.ndarray]], List[str]]:
    """Pass 2: load only the rows each drive's windows need, only for the
    populated SMART columns. Returns {serial: (days, values float32)} plus the
    attrs that were still populated inside the kept rows."""
    lo: Dict[str, int] = {}
    hi: Dict[str, int] = {}
    for serial in fleet:
        ends = [p.end_day for p in train_plans.get(serial, [])]
        ends += [p.end_day for p in lead_plans.get(serial, [])]
        if not ends:
            continue
        # Keep a 2x-window margin before the earliest window start so every
        # drive retains enough history to be re-planned from a raw sample
        # (the sample writer slices the last N days of each drive's series).
        lo[serial] = min(ends) - 2 * window_days + 2
        hi[serial] = max(ends)

    usecols = ["date", "serial_number"] + list(attrs)
    dtype = {"serial_number": str, **{c: np.float32 for c in attrs}}
    kept: Dict[str, List[Tuple[int, np.ndarray]]] = {}
    nulls = np.zeros(len(attrs), dtype=np.int64)
    total_rows = 0

    for file in source_files(csv_path):
        file_header = read_header(file)
        cols = [c for c in attrs if c in file_header]
        usecols = ["date", "serial_number"] + cols
        dtype = {"serial_number": str, **{c: np.float32 for c in cols}}
        for chunk in pd.read_csv(file, usecols=usecols, dtype=dtype, chunksize=CHUNK_ROWS):
            ser = chunk["serial_number"].to_numpy()
            days = pd.to_datetime(chunk["date"], format="%Y-%m-%d").map(to_day).to_numpy()
            mask = np.fromiter((s in lo for s in ser), dtype=bool, count=len(ser))
            if not mask.any():
                continue
            lo_v = np.fromiter((lo.get(s, 1 << 62) for s in ser[mask]), dtype=np.int64)
            hi_v = np.fromiter((hi.get(s, -(1 << 62)) for s in ser[mask]), dtype=np.int64)
            keep = mask.copy()
            keep[mask] = (days[mask] >= lo_v) & (days[mask] <= hi_v)
            if not keep.any():
                continue
            sub = chunk[keep]
            if len(cols) < len(attrs):
                for c in attrs:
                    if c not in sub.columns:
                        sub[c] = np.nan
            sub_days = days[keep]
            sub_vals = sub[list(attrs)].to_numpy(dtype=np.float32)
            nulls += np.isnan(sub_vals).sum(axis=0)
            total_rows += len(sub)
            for serial, day, vals in zip(sub["serial_number"].to_numpy(), sub_days, sub_vals):
                kept.setdefault(serial, []).append((int(day), vals.astype(np.float32, copy=False)))

    series: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for serial, rows in kept.items():
        rows.sort(key=lambda r: r[0])
        day_arr = np.array([r[0] for r in rows], dtype=np.int64)
        val_arr = np.stack([r[1] for r in rows])
        # keep the last row when a (serial, day) repeats
        _, idx = np.unique(day_arr, return_index=True)
        if len(idx) < len(day_arr):
            day_arr = day_arr[idx]
            val_arr = val_arr[idx]
        series[serial] = (day_arr, val_arr)

    frac = nulls / max(total_rows, 1)
    populated = [a for a, f in zip(attrs, frac) if f < missing_threshold]
    if populated != list(attrs):
        for serial, (days_arr, vals) in series.items():
            idx = [attrs.index(a) for a in populated]
            series[serial] = (days_arr, vals[:, idx])
    return series, populated


def collect_windows(
    series: Dict[str, Tuple[np.ndarray, np.ndarray]],
    plans: Dict[str, List[WindowPlan]],
    window_days: int,
    min_obs: int,
) -> List[WindowRecord]:
    records: List[WindowRecord] = []
    for serial, plan_list in plans.items():
        if serial not in series:
            continue
        days_arr, vals = series[serial]
        for plan in plan_list:
            lo_day, hi_day = plan.end_day - window_days + 1, plan.end_day
            m = (days_arr >= lo_day) & (days_arr <= hi_day)
            n = int(m.sum())
            if n < min_obs:
                continue
            records.append(
                WindowRecord(
                    serial=serial,
                    end_day=plan.end_day,
                    label=plan.label,
                    kind=plan.kind,
                    days=days_arr[m],
                    values=vals[m],
                )
            )
    return records


def write_raw_sample(
    series: Dict[str, Tuple[np.ndarray, np.ndarray]],
    fleet: Dict[str, FleetInfo],
    attrs: Sequence[str],
    n_drives: int,
    n_days: int,
    seed: int,
    out_csv: Path,
    provenance: dict,
) -> int:
    """Write a small gzipped slice of the real data (data/samples/) with the
    same schema as the source file, plus a provenance JSON sidecar."""
    rng = np.random.default_rng(seed)
    failing = [s for s, i in fleet.items() if i.fail_date is not None and s in series]
    healthy = [s for s in series if s not in failing]
    n_fail = min(len(failing), max(1, n_drives // 4))
    n_health = max(0, n_drives - n_fail)
    chosen = failing[:n_fail]
    if healthy:
        chosen += list(rng.choice(healthy, size=min(n_health, len(healthy)), replace=False))
    chosen = [c for c in chosen if c in series]
    header = CORE_COLUMNS + list(attrs)
    rows: List[List] = []
    for serial in chosen:
        days_arr, vals = series[serial]
        info = fleet[serial]
        take = days_arr[-n_days:]
        vals = vals[-len(take):]
        for day, v in zip(take, vals):
            rows.append(
                [
                    (EPOCH + timedelta(days=int(day))).strftime("%Y-%m-%d"),
                    serial,
                    info.model,
                    int(info.capacity_bytes),
                    1 if info.fail_date is not None else 0,
                    *[float(x) for x in v],
                ]
            )
    df = pd.DataFrame(rows, columns=header)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, compression="gzip")
    sidecar = out_csv.with_suffix(".json")
    payload = dict(provenance)
    payload.update(
        {
            "drives": len(chosen),
            "failing_drives": len(failing[:n_fail]),
            "rows": len(df),
            "columns": header,
        }
    )
    sidecar.write_text(json.dumps(payload, indent=2))
    return len(df)


def load_features(path: Path) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Load a committed gzipped feature matrix → (X, y, serials)."""
    df = pd.read_csv(path)
    y = df["label"].astype(int)
    serials = df["serial"].astype(str)
    x_cols = [c for c in df.columns if c not in ("label", "serial", "end_day")]
    return df[x_cols], y, serials


def split_by_drive(
    feature_df: pd.DataFrame,
    test_size: float,
    seed: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split windows by drive (never by row) so no drive appears in both
    train and test. Stratifies on whether the drive failed."""
    drives = feature_df.groupby("serial")["label"].max().rename("failed").reset_index()
    from sklearn.model_selection import train_test_split

    tr_drives, te_drives = train_test_split(
        drives["serial"], test_size=test_size, random_state=seed, stratify=drives["failed"]
    )
    tr_set = set(tr_drives)
    return feature_df[feature_df["serial"].isin(tr_set)], feature_df[~feature_df["serial"].isin(tr_set)]
