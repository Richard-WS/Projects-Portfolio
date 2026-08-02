"""Console summary and a self-contained HTML report with embedded charts."""
from __future__ import annotations

import base64
import io
import json
from string import Template
from typing import Any, Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402

from .model import evaluate  # noqa: E402

TEMPLATE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Drive failure prediction — report</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
         margin: 0; padding: 2rem 1.5rem; background: #f6f7f9; color: #1c2733; }
  h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
  .sub { color: #5a6b7b; margin-bottom: 1.5rem; font-size: .9rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
           gap: .75rem; margin-bottom: 1.5rem; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
          padding: .75rem 1rem; }
  .card .k { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em;
             color: #5a6b7b; }
  .card .v { font-size: 1.25rem; font-weight: 600; margin-top: .25rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
          gap: 1rem; }
  .panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
           padding: 1rem; }
  .panel h2 { font-size: .95rem; margin: 0 0 .75rem; }
  .panel img { width: 100%; height: auto; }
  table { border-collapse: collapse; width: 100%; font-size: .85rem; }
  th, td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #eef2f6; }
  th { color: #5a6b7b; font-weight: 600; }
  .note { font-size: .8rem; color: #5a6b7b; margin-top: 1.5rem; line-height: 1.5; }
</style>
</head>
<body>
<h1>Drive failure prediction — Q1 2024 S.M.A.R.T. telemetry</h1>
<div class="sub">Gradient boosting on engineered S.M.A.R.T. window features.
All numbers in <code>docs/metrics.json</code>.</div>
<div class="cards">
$cards
</div>
<div class="grid">
  <div class="panel"><h2>ROC curve (held-out test drives)</h2><img src="$chart_roc" alt="ROC curve"></div>
  <div class="panel"><h2>Precision-recall curve (held-out test drives)</h2><img src="$chart_pr" alt="Precision-recall curve"></div>
  <div class="panel"><h2>Detection lead time — recall vs. days before failure</h2><img src="$chart_lead" alt="Lead-time recall"></div>
  <div class="panel"><h2>Top features by importance</h2><img src="$chart_imp" alt="Feature importances"></div>
</div>
<h2 style="font-size:1rem;margin:1.25rem 0 .5rem">Lead-time analysis</h2>
<div class="panel">$lead_table</div>
<div class="note">
S.M.A.R.T. data &copy; Backblaze (CC BY-SA 4.0), Q1 2024, via
backblaze.com/cloud-storage/resources/hard-drive-test-data. Model, metrics and
reproducibility details are in the project README. Raw telemetry is not
included in the repository.
</div>
</body>
</html>
""")


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _card(key: str, value: str) -> str:
    return f'<div class="card"><div class="k">{key}</div><div class="v">{value}</div></div>'


def _roc_chart(y_test: np.ndarray, proba: np.ndarray) -> str:
    fpr, tpr, _ = roc_curve(y_test, proba)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(fpr, tpr, label="model")
    ax.plot([0, 1], [0, 1], ls="--", color="#94a3b8", label="chance")
    ax.set_xlabel("False alarm rate")
    ax.set_ylabel("Recall")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")
    return _png(fig)


def _pr_chart(y_test: np.ndarray, proba: np.ndarray) -> str:
    prec, rec, _ = precision_recall_curve(y_test, proba)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(rec, prec)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    return _png(fig)


def _lead_chart(leadtime: List[Dict[str, Any]]) -> str:
    fig, ax = plt.subplots(figsize=(5, 4))
    if leadtime:
        horizons = [int(d["horizon_days"]) for d in leadtime]
        recall = [float(d["recall"]) for d in leadtime]
        ax.plot(horizons, recall, marker="o")
        ax.set_xlabel("Days before failure (window end)")
        ax.set_ylabel("Fraction flagged")
        ax.set_xlim(min(horizons) - 1, max(horizons) + 1)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3)
        ax.invert_xaxis()
    else:
        ax.text(0.5, 0.5, "no lead-time data", ha="center", va="center")
        ax.set_axis_off()
    return _png(fig)


def _imp_chart(importance: List[Dict[str, Any]], top: int = 15) -> str:
    fig, ax = plt.subplots(figsize=(5, 4))
    items = importance[:top]
    names = [str(d["feature"]) for d in items][::-1]
    vals = [float(d["importance"]) for d in items][::-1]
    ax.barh(names, vals)
    ax.set_xlabel("Importance")
    ax.set_title(f"Top {len(items)} features")
    ax.grid(alpha=0.3, axis="x")
    return _png(fig)


def _lead_table(leadtime: List[Dict[str, Any]]) -> str:
    if not leadtime:
        return "<p>No lead-time windows were available.</p>"
    rows = "\n".join(
        "<tr>"
        f"<td>{int(d['horizon_days'])}</td>"
        f"<td>{int(d['drives'])}</td>"
        f"<td>{int(d['flagged'])}</td>"
        f"<td>{float(d['recall']):.1%}</td>"
        f"<td>{float(d['mean_risk']):.3f}</td>"
        "</tr>"
        for d in leadtime
    )
    return (
        "<table><tr><th>Window ends this many days before failure</th>"
        "<th>Drives</th><th>Flagged</th><th>Recall</th><th>Mean risk</th></tr>"
        f"{rows}</table>"
    )


def build_report(
    metrics: dict,
    y_test: np.ndarray,
    proba: np.ndarray,
) -> str:
    cards = "".join(
        [
            _card("Test ROC-AUC", f"{metrics['test']['roc_auc']:.3f}"),
            _card("Test PR-AUC", f"{metrics['test']['pr_auc']:.3f}"),
            _card("Precision", f"{metrics['test']['precision']:.1%}"),
            _card("Recall", f"{metrics['test']['recall']:.1%}"),
            _card("False alarm rate", f"{metrics['test']['false_alarm_rate']:.1%}"),
            _card("Fleet drives", f"{metrics['meta']['fleet_drives']:,}"),
            _card("Failures in fleet", f"{metrics['meta']['failing_drives']:,}"),
            _card("Features", f"{metrics['meta']['n_features']}"),
        ]
    )
    return TEMPLATE.substitute(
        cards=cards,
        chart_roc=_roc_chart(y_test, proba),
        chart_pr=_pr_chart(y_test, proba),
        chart_lead=_lead_chart(metrics.get("leadtime", [])),
        chart_imp=_imp_chart(metrics.get("feature_importance", [])),
        lead_table=_lead_table(metrics.get("leadtime", [])),
    )


def print_summary(metrics: dict) -> None:
    test = metrics["test"]
    print("Model: gradient boosting (HistGradientBoosting)")
    print(f"  CV ROC-AUC (group 5-fold): {metrics['cv']['cv_roc_auc']:.4f} +/- n/a")
    print(f"  Test ROC-AUC: {test['roc_auc']:.4f}  PR-AUC: {test['pr_auc']:.4f}")
    print(
        f"  At threshold {test['threshold']:.4f}: precision {test['precision']:.3f}, "
        f"recall {test['recall']:.3f}, false alarm rate {test['false_alarm_rate']:.3f}"
    )
    print(f"  Test set: {test['n']} windows ({test['n_failing']} failing, {test['n_healthy']} healthy)")
    for d in metrics.get("leadtime", []):
        print(
            f"  Lead time {int(d['horizon_days']):>2}d before failure: "
            f"recall {d['recall']:.2f} ({d['flagged']}/{d['drives']} drives)"
        )
