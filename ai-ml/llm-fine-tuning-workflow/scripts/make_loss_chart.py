"""Chart the fine-tuning loss curve into the project's preview image.

Reads docs/loss_curve.csv (per-step training loss from a real run, produced
by scripts/run_train.py -> outputs/loss_curve.json and committed as CSV) and
writes docs/screenshot.png. Run from the project directory:

    python scripts/make_loss_chart.py

Requires matplotlib only.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CURVE = ROOT / "docs" / "loss_curve.csv"
OUT = ROOT / "docs" / "screenshot.png"


def main() -> None:
    with CURVE.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    steps = [int(r["step"]) for r in rows]
    losses = [float(r["train_loss"]) for r in rows]

    fig, ax = plt.subplots(figsize=(8.6, 5))
    ax.plot(steps, losses, color="#1f77b4", lw=1.8)
    ax.set_xlabel("Training step")
    ax.set_ylabel("Training loss")
    ax.set_title(f"LoRA fine-tuning loss — distilgpt2, {len(steps)} steps", fontsize=11)
    ax.grid(alpha=0.3)

    first, last = losses[0], losses[-1]
    ax.annotate(f"start: {first:.3f}", xy=(steps[0], first), xytext=(steps[0] + len(steps) * 0.04, first),
                fontsize=9, color="#333333")
    ax.annotate(f"end: {last:.3f}", xy=(steps[-1], last), xytext=(steps[-1] - len(steps) * 0.30, last + 0.02),
                fontsize=9, color="#333333")
    ax.scatter([steps[-1]], [last], color="#d62728", s=28, zorder=3)

    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
