"""Run the fine-tuning pipeline: prepare data, train, evaluate.

Usage (from the project directory):
    python scripts/run_train.py configs/default.yaml

Writes the trained adapter + tokenizer to the config's output_dir and
prints baseline vs final perplexity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from llm_finetune.config import load_config
from llm_finetune.train import train

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/run_train.py <config.yaml>")
    cfg = load_config(sys.argv[1])
    if not Path(cfg.data_path).exists():
        sys.exit(f"data file not found: {cfg.data_path}\nRun scripts/prepare_data.py first.")

    print(f"Training {cfg.model_name} with LoRA (r={cfg.lora_r})")
    metrics = train(cfg)
    print("\n=== RESULTS ===")
    print(f"baseline  eval loss: {metrics['baseline_eval_loss']:.4f}  perplexity: {metrics['baseline_perplexity']:.2f}")
    print(f"final     eval loss: {metrics['final_eval_loss']:.4f}  perplexity: {metrics['final_perplexity']:.2f}")
    print(f"trainable parameters: {metrics['trainable_params']:,}")
    print(f"loss curve: {len(metrics['loss_curve'])} training steps recorded")
    print(f"adapter saved to: {metrics['output_dir']}")

    (PROJECT_ROOT / "outputs").mkdir(exist_ok=True)
    (PROJECT_ROOT / "outputs" / "train_metrics.json").write_text(json.dumps(metrics, indent=2))
    print("metrics -> outputs/train_metrics.json")
    (PROJECT_ROOT / "outputs" / "loss_curve.json").write_text(json.dumps(metrics["loss_curve"], indent=2))
    print("loss curve -> outputs/loss_curve.json")


if __name__ == "__main__":
    main()
