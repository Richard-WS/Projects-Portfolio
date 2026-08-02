"""Command-line interface: diskfail prepare | train | report | score | demo."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import warnings
from dataclasses import fields, replace
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from . import data as D
from . import features as F
from . import model as M
from . import report as R
from .config import Config, ConfigError, PathsConfig

DATASET_PAGE = "https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data"
DATASET_LICENSE = "CC BY-SA 4.0 (Backblaze Hard Drive Data)"


def _common() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(
        "-c", "--config", default="configs/example.yaml",
        help="config file (default: configs/example.yaml)",
    )
    return p


def _fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def _ensure_parents(*paths: str) -> None:
    for p in paths:
        Path(p).parent.mkdir(parents=True, exist_ok=True)


def prepare(cfg: Config, samples: bool = False) -> None:
    """Raw S.M.A.R.T. CSV → gzipped feature matrices + a small raw sample."""
    src = Path(cfg.sample_csv_path()) if samples else cfg.raw_csv_path()
    if not src.exists():
        _fail(
            f"source csv not found: {src}\n"
            "  run `bash scripts/download_data.sh` to fetch the dataset"
        )
    print(f"scanning {src}")
    attrs = D.detect_attrs(src, cfg.data.smart_missing_threshold)
    if not attrs:
        _fail("no populated smart_*_raw columns detected — is this the right file?")
    print(f"detected {len(attrs)} populated S.M.A.R.T. raw attributes")
    fleet = D.scan_fleet(src, cfg.data.max_drives, cfg.data.seed)
    n_failed = sum(1 for i in fleet.values() if i.fail_date is not None)
    print(f"fleet: {len(fleet)} drives ({n_failed} failing)")
    train_plans, lead_plans = D.plan_windows(
        fleet,
        cfg.features.window_days,
        cfg.labels.horizon_days,
        cfg.features.leadtime_horizons,
        cfg.data.seed,
    )
    series, attrs = D.load_series(
        src, fleet, train_plans, lead_plans, attrs,
        cfg.data.smart_missing_threshold, cfg.features.window_days,
    )
    windows = D.collect_windows(
        series, train_plans, cfg.features.window_days, cfg.features.min_window_obs
    )
    lead_windows = D.collect_windows(
        series, lead_plans, cfg.features.window_days, cfg.features.min_window_obs
    )
    feat = F.build_feature_frame(windows, attrs, fleet)
    lead_feat = F.build_feature_frame(lead_windows, attrs, fleet)
    train_df, test_df = D.split_by_drive(feat, cfg.split.test_size, cfg.split.seed)
    train_df = F.cap_negatives(train_df, cfg.split.max_negative_drives, cfg.split.seed)
    _ensure_parents(cfg.paths.feature_train, cfg.paths.feature_test, cfg.paths.leadtime_features)
    train_df.drop(columns=["kind"]).to_csv(cfg.paths.feature_train, index=False, compression="gzip")
    test_df.drop(columns=["kind"]).to_csv(cfg.paths.feature_test, index=False, compression="gzip")
    lead_feat.drop(columns=["kind"]).to_csv(cfg.paths.leadtime_features, index=False, compression="gzip")

    meta = {
        "fleet_drives": len(fleet),
        "failing_drives": n_failed,
        "attrs": attrs,
        "n_features": len(F.feature_columns(attrs)) + 3,
        "n_train_windows": len(train_df),
        "n_test_windows": len(test_df),
        "n_leadtime_windows": len(lead_feat),
        "prepared_at": date.today().isoformat(),
        "source": f"Backblaze Hard Drive Data Q1 2024 ({DATASET_PAGE})",
        "license": DATASET_LICENSE,
        "config": cfg.summary(),
    }
    samples_dir = Path(cfg.data.samples_dir)
    samples_dir.mkdir(parents=True, exist_ok=True)
    (samples_dir / "prepare-meta.json").write_text(json.dumps(meta, indent=2))

    if not samples:
        provenance = {
            "source": meta["source"],
            "license": DATASET_LICENSE,
            "extracted_from": str(src),
            "extracted_at": date.today().isoformat(),
            "notes": "Seeded slice of the full quarterly file, kept for offline demos and tests.",
        }
        n_rows = D.write_raw_sample(
            series, fleet, attrs, cfg.data.sample_drives, cfg.data.sample_days,
            cfg.data.seed, Path(cfg.data.samples_dir) / cfg.data.raw_sample, provenance,
        )
        print(f"raw sample: {n_rows} rows -> {cfg.data.samples_dir}/{cfg.data.raw_sample}")

    print(f"train windows: {len(train_df)}  test windows: {len(test_df)}")
    print(f"wrote {cfg.paths.feature_train}")
    print(f"wrote {cfg.paths.feature_test}")


def train(cfg: Config) -> None:
    """Fit the boosting model, evaluate on held-out drives, write metrics."""
    Xtr, ytr, ser_tr = D.load_features(Path(cfg.paths.feature_train))
    Xte, yte, ser_te = D.load_features(Path(cfg.paths.feature_test))
    if Xtr.empty or Xte.empty:
        _fail("feature matrices are empty — run `diskfail prepare` first")
    clf, cv, threshold = M.train_model(Xtr, ytr, ser_tr, cfg.model, cfg.split.seed)
    proba = clf.predict_proba(Xte[clf.feature_names_in_])[:, 1]
    test = M.evaluate(yte.to_numpy(), proba, threshold)

    lead: list = []
    lt_path = Path(cfg.paths.leadtime_features)
    if lt_path.is_file():
        lt_df = pd.read_csv(lt_path)
        if not lt_df.empty and "horizon" in lt_df.columns:
            lt_df = lt_df[lt_df["horizon"].notna()]
            lead = M.lead_time_recall(clf, lt_df, threshold)

    meta = {"model": "HistGradientBoosting", "threshold": threshold,
            "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
            "n_features": int(Xtr.shape[1])}
    meta_path = Path(cfg.data.samples_dir) / "prepare-meta.json"
    if meta_path.is_file():
        meta.update(json.loads(meta_path.read_text()))
    metrics = {
        "cv": cv,
        "test": test,
        "leadtime": lead,
        "feature_importance": M.feature_importance(clf, Xte, yte),
        "meta": meta,
    }
    _ensure_parents(cfg.paths.model_path, cfg.paths.metrics_path)
    joblib.dump(clf, cfg.paths.model_path)
    Path(cfg.paths.metrics_path).write_text(json.dumps(metrics, indent=2))
    R.print_summary(metrics)
    print(f"model saved to {cfg.paths.model_path}")
    print(f"metrics saved to {cfg.paths.metrics_path}")


def report(cfg: Config) -> None:
    """Render the self-contained HTML report from the trained model + metrics."""
    model_path, metrics_path = Path(cfg.paths.model_path), Path(cfg.paths.metrics_path)
    if not model_path.is_file():
        _fail(f"model not found at {model_path} — run `diskfail train` first")
    if not metrics_path.is_file():
        _fail(f"metrics not found at {metrics_path} — run `diskfail train` first")
    clf = joblib.load(model_path)
    metrics = json.loads(metrics_path.read_text())
    Xte, yte, _ = D.load_features(Path(cfg.paths.feature_test))
    proba = clf.predict_proba(Xte[clf.feature_names_in_])[:, 1]
    html = R.build_report(metrics, yte.to_numpy(), proba)
    _ensure_parents(cfg.paths.report_path)
    Path(cfg.paths.report_path).write_text(html)
    print(f"report written to {cfg.paths.report_path}")


def score(cfg: Config, csv_in: str, out: str) -> None:
    """Score a fresh daily S.M.A.R.T. snapshot: one risk per drive."""
    src = Path(csv_in)
    if not src.exists():
        _fail(f"input csv or directory not found: {src}")
    model_path = Path(cfg.paths.model_path)
    if not model_path.is_file():
        _fail(f"model not found at {model_path} — run `diskfail train` first")
    clf = joblib.load(model_path)

    attrs = D.detect_attrs(src, cfg.data.smart_missing_threshold)
    fleet = D.scan_fleet(src, max_drives=None, seed=cfg.data.seed)
    plans = {s: [D.WindowPlan(s, D.to_day(i.last_date), 0, "train")] for s, i in fleet.items()}
    series, attrs = D.load_series(
        src, fleet, plans, {}, attrs, cfg.data.smart_missing_threshold, cfg.features.window_days
    )
    windows = D.collect_windows(series, plans, cfg.features.window_days, cfg.features.min_window_obs)
    feat = F.build_feature_frame(windows, attrs, fleet)
    if feat.empty:
        _fail(
            "no drives could be scored: every drive needs at least "
            f"{cfg.features.min_window_obs} daily observations within the "
            f"{cfg.features.window_days}-day window — point score at a "
            "directory of consecutive daily snapshots, not a single file"
        )
    missing = [c for c in clf.feature_names_in_ if c not in feat.columns]
    if missing:
        # Attributes can be entirely absent from a live feed (drives that stop
        # reporting SMART, or a feed with fewer columns). The booster handles
        # NaN natively, so predict on NaN-filled columns instead of failing.
        print(f"note: {len(missing)} model features absent from input, filled with NaN", file=sys.stderr)
        for c in missing:
            feat[c] = np.nan
    risk = clf.predict_proba(feat[clf.feature_names_in_])[:, 1]
    metrics_path = Path(cfg.paths.metrics_path)
    threshold = 0.5
    if metrics_path.is_file():
        threshold = float(json.loads(metrics_path.read_text())["test"]["threshold"])
    out_df = feat[["serial"]].copy()
    out_df["risk"] = risk
    out_df["flagged"] = risk >= threshold
    out_df["capacity_bytes"] = feat["capacity_bytes"]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    print(f"scored {len(out_df)} drives (threshold {threshold:.4f}) -> {out}")


def demo(cfg: Config, workdir: str | None) -> None:
    """Run the whole pipeline on the committed sample in an isolated folder."""
    wd = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="diskfail-demo-"))
    wd.mkdir(parents=True, exist_ok=True)
    new_paths = PathsConfig(
        **{f.name: str(wd / Path(getattr(cfg.paths, f.name)).name) for f in fields(PathsConfig)}
    )
    cfg2 = replace(cfg, paths=new_paths)
    print(f"demo workspace: {wd}")
    prepare(cfg2, samples=True)
    train(cfg2)
    report(cfg2)
    print(f"demo complete — open {Path(cfg2.paths.report_path)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="diskfail",
        description="Predict imminent hard-drive failure from S.M.A.R.T. telemetry.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="{prepare,train,report,score,demo}")

    p_prep = sub.add_parser("prepare", parents=[_common()], help="raw CSV -> feature matrices")
    p_prep.add_argument("--samples", action="store_true",
                        help="build features from the committed raw sample instead of the full file")
    p_prep.set_defaults(func=lambda a: prepare(_load(a.config), samples=a.samples))

    p_train = sub.add_parser("train", parents=[_common()], help="fit + evaluate the model")
    p_train.set_defaults(func=lambda a: train(_load(a.config)))

    p_rep = sub.add_parser("report", parents=[_common()], help="render the HTML report")
    p_rep.set_defaults(func=lambda a: report(_load(a.config)))

    p_score = sub.add_parser("score", parents=[_common()], help="score a fresh snapshot (single daily CSV or a directory of them)")
    p_score.add_argument("csv_in", help="daily S.M.A.R.T. CSV, or a directory of daily CSVs, with the same schema as the raw data")
    p_score.add_argument("-o", "--out", default=None, help="output CSV (default: outputs/predictions.csv)")
    p_score.set_defaults(func=lambda a: score(_load(a.config), a.csv_in, a.out or _load(a.config).paths.predictions_path))

    p_demo = sub.add_parser("demo", parents=[_common()], help="sample-data pipeline in an isolated folder")
    p_demo.add_argument("--workdir", default=None, help="output folder (default: a fresh temp dir)")
    p_demo.set_defaults(func=lambda a: demo(_load(a.config), a.workdir))

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ConfigError as exc:
        parser.exit(2, f"config error: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "interrupted\n")
    return 0


def _load(path: str) -> Config:
    return Config.load(path)


if __name__ == "__main__":
    raise SystemExit(main())
