"""Command-line interface: prepare, train, predict, report.

Examples:
    exo-classifier prepare -c configs/example.yaml      # raw CSVs -> feature matrices
    exo-classifier train -c configs/example.yaml        # fit + evaluate + save model
    exo-classifier report -c configs/example.yaml       # regenerate the HTML report
    exo-classifier predict -c configs/example.yaml curves.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from . import __version__
from .config import Config, ConfigError
from .data import DataError, build_feature_frame, load_features, prepare
from .features import extract_features
from .model import (
    ModelError,
    load_metrics,
    load_model,
    predict,
    save_metrics,
    save_model,
    train_pipeline,
)
from .report import render_text, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="exo-classifier",
        description="Classify Kepler light curves as exoplanet transits or non-transits.",
    )
    parser.add_argument("--version", action="version", version=f"exo-classifier {__version__}")
    # -c accepted before and after the subcommand (see portfolio scaffolding notes)
    parser.add_argument("-c", "--config", dest="main_config", help="path to the YAML config file")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", dest="sub_config", help="path to the YAML config file")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("prepare", parents=[common], help="build feature matrices from the raw light curves")

    train_p = sub.add_parser("train", parents=[common], help="train, evaluate, and save the model")
    train_p.add_argument("--no-report", action="store_true", help="skip regenerating the HTML report")

    report_p = sub.add_parser("report", parents=[common], help="regenerate the HTML report from saved results")
    report_p.add_argument("--no-model", action="store_true", help="skip recomputing curves (report only, no model)")

    predict_p = sub.add_parser("predict", parents=[common], help="score new light curves")
    predict_p.add_argument("curves", nargs="?", help="CSV of light curves (label column optional)")
    predict_p.add_argument("-o", "--output", default=None, help="output CSV path (default: outputs/predictions.csv)")
    return parser


def _load_config(args) -> Config:
    config_path = args.sub_config or args.main_config
    if not config_path:
        build_parser().error("the following arguments are required: -c/--config")
    return Config.load(config_path)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = _load_config(args)
        if args.command == "prepare":
            counts = prepare(cfg)
            print(
                f"wrote feature matrices: train {counts['train']}, val {counts['val']}, "
                f"test {counts['test']} curves"
            )
            print(f"  -> {cfg.paths.feature_train}")
            print(f"  -> {cfg.paths.feature_val}")
            print(f"  -> {cfg.paths.feature_test}")
            print(f"  -> {cfg.paths.raw_sample} (raw sample)")
            return 0

        if args.command == "train":
            X_train, y_train = load_features(cfg, "train")
            X_val, y_val = load_features(cfg, "val")
            X_test, y_test = load_features(cfg, "test")
            feature_names = _feature_names_from(cfg.paths.feature_train)
            metrics, artifacts = train_pipeline(
                X_train, y_train, cfg,
                X_val=X_val, y_val=y_val, X_test=X_test, y_test=y_test,
                feature_names=feature_names,
            )
            save_model(artifacts, cfg.paths.model_path)
            save_metrics(metrics, cfg.paths.metrics_path)
            print(render_text(metrics))
            if not args.no_report:
                write_report(cfg, metrics, artifacts, cfg.paths.report_path)
                print(f"wrote HTML report -> {cfg.paths.report_path}")
            return 0

        if args.command == "report":
            metrics = load_metrics(cfg.paths.metrics_path)
            if args.no_model:
                artifacts = {
                    "scaler": None,
                    "model": None,
                    "kind": metrics["chosen_model"],
                    "feature_names": [],
                }
                from .report import build_html_report

                path = cfg.paths.report_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(build_html_report(cfg, metrics, artifacts), encoding="utf-8")
            else:
                artifacts = load_model(cfg.paths.model_path)
                write_report(cfg, metrics, artifacts, cfg.paths.report_path)
            print(f"wrote HTML report -> {cfg.paths.report_path}")
            return 0

        if args.command == "predict":
            if not args.curves:
                build_parser().error("predict requires a CSV of light curves")
            artifacts = load_model(cfg.paths.model_path)
            df = pd.read_csv(args.curves, header=0)
            flux = df.drop(columns=[df.columns[0]]).to_numpy(dtype=float) if df.shape[1] > 1 else df.to_numpy(dtype=float)
            rows = [
                extract_features(
                    curve,
                    detrend_window=cfg.features.detrend_window,
                    dip_threshold_mad=cfg.features.dip_threshold_mad,
                    autocorr_max_lag=cfg.features.autocorr_max_lag,
                )
                for curve in flux
            ]
            feats = pd.DataFrame(rows)
            feats = feats.reindex(columns=artifacts["feature_names"])
            proba = predict(artifacts, feats.to_numpy(dtype=float))
            out = pd.DataFrame({"probability_exoplanet": proba})
            if df.shape[1] > 1:
                out.insert(0, "label", df[df.columns[0]])
            out_path = Path(args.output) if args.output else cfg.paths.predictions_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out.to_csv(out_path, index=False)
            print(f"wrote {len(proba)} predictions -> {out_path}")
            return 0

        build_parser().error(f"unknown command: {args.command}")
    except (ConfigError, DataError, ModelError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


def _feature_names_from(path: Path) -> list[str]:
    sample = pd.read_csv(path, nrows=1)
    return [c for c in sample.columns if c != "label"]
