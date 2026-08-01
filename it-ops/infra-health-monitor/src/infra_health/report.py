"""Report generation: a text summary for the terminal and a self-contained
HTML report that opens in any browser (no external assets).
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from string import Template

_HTML_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Infrastructure health report</title>
<style>
  :root { --fg:#1c2733; --muted:#5b6b7b; --line:#dde5ec; --bg:#f5f8fa; --ok:#1a7f37; --bad:#cf222e; --warn:#9a6700; }
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--fg); }
  header { padding:24px 32px; background:#fff; border-bottom:1px solid var(--line); }
  h1 { margin:0 0 4px; font-size:22px; }
  .sub { color:var(--muted); font-size:13px; }
  main { padding:24px 32px; max-width:1100px; margin:0 auto; }
  .cards { display:flex; gap:12px; margin:18px 0 24px; flex-wrap:wrap; }
  .card { background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px 18px; min-width:150px; }
  .card .n { font-size:26px; font-weight:600; }
  .card .l { font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  .ok { color:var(--ok); } .bad { color:var(--bad); } .warn { color:var(--warn); }
  table { width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; font-size:13px; }
  th, td { padding:8px 10px; text-align:left; border-bottom:1px solid var(--line); }
  th { background:#eef3f7; font-size:12px; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); }
  tr:last-child td { border-bottom:none; }
  td.num { font-variant-numeric:tabular-nums; }
  .pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600; }
  .pill.up { background:#dafbe1; color:var(--ok); }
  .pill.down { background:#ffebe9; color:var(--bad); }
  .pill.unknown { background:#eaeef2; color:var(--muted); }
  h2 { font-size:16px; margin:28px 0 10px; }
  ul.incidents { background:#fff; border:1px solid var(--line); border-radius:8px; padding:10px 14px 10px 32px; font-size:13px; margin:0; }
  ul.incidents li { padding:4px 0; }
  .mono { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:12px; }
  footer { color:var(--muted); font-size:12px; padding:20px 32px 40px; max-width:1100px; margin:0 auto; line-height:1.5; }
</style>
</head>
<body>
<header>
  <h1>Infrastructure health report</h1>
  <div class="sub">Generated $generated (UTC) — uptime is measured over the samples available in each window; sample counts are shown alongside</div>
</header>
<main>
  <div class="cards">$cards</div>
  <h2>Checks vs SLO</h2>
  <table>
    <thead>
      <tr><th>Check</th><th>Type</th><th>Status</th><th>Uptime 24h</th><th>Uptime 7d</th><th>Uptime 30d</th><th>SLO</th><th>Breach</th><th>Est. downtime (30d)</th><th>Budget left (30d)</th></tr>
    </thead>
    <tbody>$table_rows</tbody>
  </table>
  <h2>Incidents</h2>
  $incidents
</main>
<footer>
  Downtime is estimated as failed checks &times; the check's configured interval. The SLO budget is the allowed downtime over 30 days minus that estimate.
  Windows with thin coverage show their sample counts so fresh history is not mistaken for long-running statistics.
  History is stored in a local SQLite database (gitignored); this report is self-contained and can be archived or emailed as-is.
</footer>
</body>
</html>
""")


def format_check_table(results) -> str:
    """One-off run results, e.g. from the ``check`` command."""
    rows = []
    for r in results:
        status = "UP" if r.ok else "DOWN"
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms is not None else "—"
        rows.append([r.name, r.check_type, status, latency, r.detail])
    return _render_text_table(["check", "type", "status", "latency", "detail"], rows)


def format_summary_table(rows: list[dict]) -> str:
    """Per-check summary rows produced by Monitor.summary()."""
    header = ["check", "type", "status", "uptime 24h", "uptime 7d", "uptime 30d", "slo", "breach", "est downtime 30d", "budget left"]
    table = []
    for row in rows:
        windows = row["windows"]
        table.append(
            [
                row["name"],
                row["type"],
                row["status"],
                _fmt_uptime(windows["24h"]),
                _fmt_uptime(windows["7d"]),
                _fmt_uptime(windows["30d"]),
                f"{row['slo_percent']:.1f}%",
                _fmt_breach(windows["24h"]),
                _fmt_duration(row["est_downtime_s"]),
                _fmt_duration(row["budget_remaining_s"]),
            ]
        )
    return _render_text_table(header, table)


def render_html(rows: list[dict], failures: list[dict], generated_ts: str) -> str:
    """Build the self-contained HTML report."""
    cards = _cards_html(rows)
    table_rows = "\n".join(_row_html(row) for row in rows)
    incidents = _incidents_html(failures)
    return _HTML_TEMPLATE.substitute(
        generated=html.escape(generated_ts),
        cards=cards,
        table_rows=table_rows,
        incidents=incidents,
    )


def _render_text_table(header: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in header]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(header))]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def _fmt_uptime(window: dict) -> str:
    if window["uptime"] is None:
        return "no data"
    return f"{window['uptime']:.1f}% ({window['passed']}/{window['total']})"


def _fmt_breach(window: dict) -> str:
    breached = window["breached"]
    if breached is None:
        return "—"
    return "yes" if breached else "no"


def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{days}d{hours}h{minutes}m"
    if hours:
        return f"{hours}h{minutes}m{seconds}s"
    if minutes:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def _cards_html(rows: list[dict]) -> str:
    total = len(rows)
    up = sum(1 for r in rows if r["status"] == "up")
    down = sum(1 for r in rows if r["status"] == "down")
    breaches = sum(
        1 for r in rows for w in r["windows"].values() if w["breached"] is True
    )
    cards = [
        f'<div class="card"><div class="n">{total}</div><div class="l">Checks</div></div>',
        f'<div class="card"><div class="n ok">{up}</div><div class="l">Up now</div></div>',
        f'<div class="card"><div class="n {"bad" if down else "ok"}">{down}</div><div class="l">Down now</div></div>',
        f'<div class="card"><div class="n {"bad" if breaches else "ok"}">{breaches}</div><div class="l">SLO breaches</div></div>',
    ]
    return "\n".join(cards)


def _row_html(row: dict) -> str:
    windows = row["windows"]
    status = row["status"]
    pill_class = status if status in ("up", "down") else "unknown"
    cells = [
        f"<td><strong>{html.escape(row['name'])}</strong></td>",
        f"<td>{html.escape(row['type'])}</td>",
        f'<td><span class="pill {pill_class}">{status}</span></td>',
        f'<td class="num">{_fmt_uptime(windows["24h"])}</td>',
        f'<td class="num">{_fmt_uptime(windows["7d"])}</td>',
        f'<td class="num">{_fmt_uptime(windows["30d"])}</td>',
        f'<td class="num">{row["slo_percent"]:.1f}%</td>',
        f'<td class="num {_breach_class(windows["24h"])}">{_fmt_breach(windows["24h"])}</td>',
        f'<td class="num">{_fmt_duration(row["est_downtime_s"])}</td>',
        f'<td class="num">{_fmt_duration(row["budget_remaining_s"])}</td>',
    ]
    return "<tr>" + "".join(cells) + "</tr>"


def _breach_class(window: dict) -> str:
    if window["breached"] is True:
        return "bad"
    if window["breached"] is False:
        return "ok"
    return ""


def _incidents_html(failures: list[dict]) -> str:
    if not failures:
        return '<p class="sub">No failures recorded in the visible history.</p>'
    items = [
        f"<li><span class='mono'>{html.escape(f['ts'])}</span> — "
        f"<strong>{html.escape(f['name'])}</strong> ({html.escape(f['type'])}): "
        f"{html.escape(f['detail'])}</li>"
        for f in failures
    ]
    return '<ul class="incidents">' + "\n".join(items) + "</ul>"


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
