"""Report generation: a console summary and a self-contained HTML report.

The HTML report embeds the ROC and precision-recall curves, the feature
importance chart, and a few real light curves from the committed sample.
It uses no external assets, so it can be archived or emailed as-is.

Note: the template uses ``string.Template`` (``$name`` placeholders) —
never ``str.format``, which would collide with CSS braces.
"""
from __future__ import annotations

import base64
import html as html_mod
import io
from datetime import datetime, timezone
from pathlib import Path
from string import Template

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, roc_curve

from .config import Config
from .data import load_features
from .model import load_metrics, load_model, predict


def _pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _img_tag(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _roc_figure(curves: list[tuple[np.ndarray, np.ndarray, str, float]]) -> plt.Figure:
    """One ROC figure with a curve per (y_true, proba, label, auc)."""
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    for y_true, proba, label, auc in curves:
        fpr, tpr, _ = roc_curve(y_true, proba)
        ax.plot(fpr, tpr, lw=2, label=f"{label} (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.6, label="chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curve")
    ax.legend(loc="lower right")
    return fig


def _pr_figure(curves: list[tuple[np.ndarray, np.ndarray, str]]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    for y_true, proba, label in curves:
        precision, recall, _ = precision_recall_curve(y_true, proba)
        ax.plot(recall, precision, lw=2, label=label)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-recall curve")
    ax.legend(loc="upper right")
    return fig


def _importance_figure(top_features: list[dict]) -> plt.Figure:
    names = [f["feature"] for f in top_features][::-1]
    values = [f["importance"] for f in top_features][::-1]
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.barh(names, values, color="#2c7fb8")
    ax.set_xlabel("Importance")
    ax.set_title("Top features by importance")
    return fig


def _training_curve_figure(curve: list[dict]) -> plt.Figure:
    iters = [p["iteration"] for p in curve]
    aucs = [p["val_roc_auc"] for p in curve]
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.plot(iters, aucs, lw=2, color="#2c7fb8", marker="o", ms=3)
    ax.set_xlabel("Boosting iteration")
    ax.set_ylabel("Validation ROC-AUC")
    ax.set_title("Validation ROC-AUC during training")
    ax.grid(True, alpha=0.3)
    return fig


def _curves_figure(raw_sample_path: Path) -> plt.Figure | None:
    """Plot four real light curves from the committed raw sample."""
    if not Path(raw_sample_path).is_file():
        return None
    df = pd.read_csv(raw_sample_path)
    if df.shape[0] < 4:
        return None
    fig, axes = plt.subplots(2, 2, figsize=(8, 5), sharex=True)
    for ax, (_, row) in zip(axes.ravel(), df.iterrows()):
        flux = row.iloc[1:].to_numpy(dtype=float)
        z = (flux - np.median(flux)) / max(np.median(np.abs(flux - np.median(flux))), 1e-9)
        ax.plot(z, lw=0.4, color="#444")
        is_exo = bool(row.iloc[0] == 2)
        ax.set_title("exoplanet" if is_exo else "non-exoplanet", fontsize=9)
        ax.set_yticks([])
    fig.suptitle("Sample Kepler light curves (normalized)")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig


def render_text(metrics: dict) -> str:
    lines = [
        "Exoplanet transit classifier — results",
        "=" * 40,
        f"chosen model : {metrics['chosen_model']}",
        f"CV ROC-AUC   : {metrics['cv_roc_auc_mean']} +/- {metrics['cv_roc_auc_std']} "
        f"({metrics['cv_folds']} folds)",
        "",
    ]
    for split in ("validation", "test"):
        if split not in metrics:
            continue
        m = metrics[split]
        lines.append(f"{split}:")
        lines.append(f"  ROC-AUC    {m['roc_auc']}")
        lines.append(f"  PR-AUC     {m['pr_auc']}")
        lines.append(f"  precision  {m['precision']}   recall {m['recall']}   f1 {m['f1']}")
        lines.append(
            f"  confusion  TN {m['confusion']['tn']}  FP {m['confusion']['fp']}  "
            f"FN {m['confusion']['fn']}  TP {m['confusion']['tp']}"
        )
    lines.append("")
    lines.append("top features:")
    for f in metrics.get("top_features", []):
        lines.append(f"  {f['feature']:<24s} {f['importance']}")
    return "\n".join(lines)


HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Exoplanet transit classifier — results</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         margin: 0; background: #f6f7f9; color: #222; }
  header { background: #12283e; color: #fff; padding: 28px 32px; }
  header h1 { margin: 0 0 6px; font-size: 24px; }
  header p { margin: 0; color: #b8c6d4; }
  main { max-width: 960px; margin: 24px auto; padding: 0 16px; }
  .cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
  .card { background: #fff; border: 1px solid #e2e6ea; border-radius: 8px;
          padding: 14px 18px; flex: 1 1 170px; }
  .card .label { font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
                 color: #667; }
  .card .value { font-size: 22px; font-weight: 600; margin-top: 4px; }
  section { background: #fff; border: 1px solid #e2e6ea; border-radius: 8px;
            padding: 18px 22px; margin-bottom: 22px; }
  section h2 { margin-top: 0; font-size: 17px; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: right; padding: 6px 10px; border-bottom: 1px solid #eef0f2; }
  th:first-child, td:first-child { text-align: left; }
  th { color: #667; font-weight: 600; }
  .charts { display: flex; flex-wrap: wrap; gap: 18px; }
  .charts figure { margin: 0; flex: 1 1 300px; text-align: center; }
  .charts img { max-width: 100%; }
  footer { max-width: 960px; margin: 0 auto 40px; padding: 0 16px;
           color: #667; font-size: 13px; }
</style>
</head>
<body>
<header>
  <h1>Exoplanet transit classifier — results</h1>
  <p>Kepler light curves classified as exoplanet transit or non-transit
     &middot; generated $generated_at</p>
</header>
<main>
  <div class="cards">
    <div class="card"><div class="label">Chosen model</div>
      <div class="value">$chosen_model</div></div>
    <div class="card"><div class="label">CV ROC-AUC (mean &plusmn; std)</div>
      <div class="value">$cv_auc</div></div>
    <div class="card"><div class="label">Test ROC-AUC</div>
      <div class="value">$test_auc</div></div>
    <div class="card"><div class="label">Test PR-AUC</div>
      <div class="value">$test_pr_auc</div></div>
    <div class="card"><div class="label">Train size</div>
      <div class="value">$train_size</div></div>
  </div>

  <section>
    <h2>Evaluation</h2>
    $metrics_table
  </section>

  <section>
    <h2>Confusion matrix (test, threshold 0.5)</h2>
    $confusion_table
  </section>

  <section>
    <h2>Curves</h2>
    <div class="charts">
      <figure><img src="$roc_img" alt="ROC curve"></figure>
      <figure><img src="$pr_img" alt="Precision-recall curve"></figure>
    </div>
  </section>

  $training_curve_section

  <section>
    <h2>What the model looks at</h2>
    <div class="charts">
      <figure><img src="$importance_img" alt="Feature importance"></figure>
      $curves_figure_html
    </div>
    <p>$importance_note</p>
  </section>
</main>
<footer>
  <p>Data: NASA Kepler Q1-Q17 light curves (Kepler labelled time-series
     dataset, public mirror). Features are computed with numpy; models are
     scikit-learn. This report is self-contained and can be archived as-is.</p>
</footer>
</body>
</html>
"""
)


def build_html_report(cfg: Config, metrics: dict, artifacts: dict) -> str:
    """Render the full HTML report; recomputes curves from saved artifacts."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # curve data — one figure per chart type, all scored splits on it
    roc_curves: list[tuple[np.ndarray, np.ndarray, str, float]] = []
    pr_curves: list[tuple[np.ndarray, np.ndarray, str]] = []
    for split in ("validation", "test"):
        if split not in metrics:
            continue
        try:
            X, y = load_features(cfg, split)
        except Exception:
            continue
        proba = predict(artifacts, X)
        roc_curves.append((y, proba, split, metrics[split]["roc_auc"]))
        pr_curves.append((y, proba, split))
    roc_img = _img_tag(_roc_figure(roc_curves)) if roc_curves else ""
    pr_img = _img_tag(_pr_figure(pr_curves)) if pr_curves else ""

    metrics_rows = []
    for split in ("validation", "test"):
        if split not in metrics:
            continue
        m = metrics[split]
        metrics_rows.append(
            "<tr>"
            f"<td>{split}</td>"
            f"<td>{m['roc_auc']:.3f}</td>"
            f"<td>{m['pr_auc']:.3f}</td>"
            f"<td>{_pct(m['precision'])}</td>"
            f"<td>{_pct(m['recall'])}</td>"
            f"<td>{m['f1']:.3f}</td>"
            f"<td>{m['n_positive']} / {m['n_negative']}</td>"
            "</tr>"
        )
    metrics_table = (
        "<table><tr><th>split</th><th>ROC-AUC</th><th>PR-AUC</th>"
        "<th>precision</th><th>recall</th><th>F1</th><th>pos / neg</th></tr>"
        + "".join(metrics_rows)
        + "</table>"
    )

    if "test" in metrics:
        c = metrics["test"]["confusion"]
        confusion_table = (
            "<table>"
            "<tr><th></th><th>predicted non-exoplanet</th><th>predicted exoplanet</th></tr>"
            f"<tr><td>actual non-exoplanet</td><td>{c['tn']}</td><td>{c['fp']}</td></tr>"
            f"<tr><td>actual exoplanet</td><td>{c['fn']}</td><td>{c['tp']}</td></tr>"
            "</table>"
        )
    else:
        confusion_table = "<p>No test split scored.</p>"

    importance_img = _img_tag(_importance_figure(metrics.get("top_features", [])))

    training_curve_section = ""
    curve = metrics.get("training_curve") or []
    if curve:
        tc_img = _img_tag(_training_curve_figure(curve))
        training_curve_section = (
            "<section><h2>Training curve</h2>"
            '<div class="charts"><figure><img src="' + tc_img
            + '" alt="Validation ROC-AUC during training"></figure></div>'
            "<p>Validation ROC-AUC measured after every 10th boosting iteration of "
            "the chosen model; the last point is the fitted model.</p></section>"
        )

    curves_html = ""
    curves_fig = _curves_figure(cfg.paths.raw_sample)
    if curves_fig is not None:
        curves_html = (
            f'<figure><img src="{_img_tag(curves_fig)}" '
            'alt="Sample light curves"></figure>'
        )

    importance_note = (
        f"Importance from {metrics.get('importance_source', 'the chosen model')}."
        if metrics.get("top_features")
        else "No importance values recorded."
    )

    test_auc = metrics.get("test", {}).get("roc_auc", float("nan"))
    test_pr = metrics.get("test", {}).get("pr_auc", float("nan"))

    return HTML_TEMPLATE.substitute(
        generated_at=html_mod.escape(generated),
        chosen_model=html_mod.escape(metrics["chosen_model"]),
        cv_auc=f"{metrics['cv_roc_auc_mean']} &plusmn; {metrics['cv_roc_auc_std']}",
        test_auc=f"{test_auc:.3f}",
        test_pr_auc=f"{test_pr:.3f}",
        train_size=str(metrics.get("train_size", "?")),
        metrics_table=metrics_table,
        confusion_table=confusion_table,
        roc_img=roc_img,
        pr_img=pr_img,
        importance_img=importance_img,
        curves_figure_html=curves_html,
        training_curve_section=training_curve_section,
        importance_note=html_mod.escape(importance_note),
    )


def write_report(cfg: Config, metrics: dict, artifacts: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html_report(cfg, metrics, artifacts), encoding="utf-8")
