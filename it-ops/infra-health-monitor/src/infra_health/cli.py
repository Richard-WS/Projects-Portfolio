"""Command-line interface: check, run, report.

Examples:
    infra-health check -c configs/example.yaml      # one round, exit code for cron
    infra-health run -c configs/example.yaml        # loop on each check's interval
    infra-health report -c configs/example.yaml     # text summary
    infra-health report -c configs/example.yaml --html docs/report.html --csv data/samples/history.csv
"""
from __future__ import annotations

import argparse
import sys

from infra_health.alerts import AlertLogger
from infra_health.config import Config, ConfigError
from infra_health.monitor import Monitor
from infra_health.report import format_check_table, format_summary_table, render_html, utc_now_str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="infra-health",
        description="Config-driven infrastructure health checks with SLO tracking.",
    )
    # -c is accepted on the main parser (before the subcommand) and on each
    # subparser (after it); either position works.
    parser.add_argument("-c", "--config", dest="main_config", help="path to the YAML config file")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", dest="sub_config", help="path to the YAML config file")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", parents=[common], help="run every check once and exit (exit 1 if anything is down)")

    run_p = sub.add_parser("run", parents=[common], help="run checks on their intervals until interrupted")
    run_p.add_argument("-n", "--iterations", type=int, default=None, help="stop after N rounds (default: run forever)")
    run_p.add_argument("-i", "--round-interval", type=float, default=1.0, help="seconds between rounds (default: 1)")

    report_p = sub.add_parser("report", parents=[common], help="summarize the recorded history")
    report_p.add_argument("--windows", default="24h,7d,30d", help="comma-separated windows (default: 24h,7d,30d)")
    report_p.add_argument("--html", metavar="PATH", help="also write a self-contained HTML report")
    report_p.add_argument("--csv", metavar="PATH", help="also export the raw history to CSV")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.sub_config or args.main_config
    if not config_path:
        build_parser().error("the following arguments are required: -c/--config")
    try:
        config = Config.load(config_path)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    logger = AlertLogger(config.alerts.log_level)

    if args.command == "check":
        monitor = Monitor(config, logger=logger)
        results = monitor.run_once()
        print(format_check_table(results))
        failed = [r for r in results if not r.ok]
        if failed:
            print(f"{len(failed)} of {len(results)} checks down", file=sys.stderr)
            return 1
        return 0

    if args.command == "run":
        monitor = Monitor(config, logger=logger)
        try:
            monitor.run_loop(iterations=args.iterations, round_interval=args.round_interval)
        except KeyboardInterrupt:
            print("stopped (interrupted)", file=sys.stderr)
        return 0

    if args.command == "report":
        monitor = Monitor(config, logger=logger)
        windows = tuple(w.strip() for w in args.windows.split(",") if w.strip())
        try:
            rows = monitor.summary(windows=windows)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(format_summary_table(rows))
        if args.html:
            html_text = render_html(rows, monitor.history.failures(limit=50), utc_now_str())
            with open(args.html, "w", encoding="utf-8") as fh:
                fh.write(html_text)
            print(f"wrote HTML report -> {args.html}")
        if args.csv:
            count = monitor.history.export_csv(args.csv)
            print(f"exported {count} history rows -> {args.csv}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
