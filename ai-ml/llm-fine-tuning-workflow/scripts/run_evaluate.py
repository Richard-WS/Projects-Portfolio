"""Evaluate a fine-tuned adapter: perplexity + sample generations.

Usage (from the project directory):
    python scripts/run_evaluate.py configs/default.yaml [--samples 3]

Prints validation perplexity of the trained adapter and a few
instruction -> response generations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from llm_finetune.config import load_config
from llm_finetune.inference import generate, instruction_prompt, load_adapter

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sample_instructions(path: str, n: int, seed: int = 7) -> list[str]:
    import random

    from llm_finetune.data_prep import read_jsonl

    texts = read_jsonl(path)
    rng = random.Random(seed)
    picked = rng.sample(texts, min(n, len(texts)))
    return [t.split("### Response\n", 1)[0].replace("### Instruction\n", "").strip() for t in picked]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="path to config yaml")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--prompt", default=None, help="optional single prompt to try")
    args = parser.parse_args()

    cfg = load_config(args.config)
    adapter_dir = Path(cfg.output_dir)
    if not (adapter_dir / "adapter_model.safetensors").exists() and not (adapter_dir / "adapter_model.bin").exists():
        sys.exit(f"No adapter found in {adapter_dir} — run scripts/run_train.py first.")

    model, tokenizer = load_adapter(cfg.model_name, str(adapter_dir))

    prompts = [instruction_prompt(args.prompt)] if args.prompt else [
        instruction_prompt(i) for i in sample_instructions(cfg.data_path, args.samples)
    ]

    results = []
    for p in prompts:
        out = generate(model, tokenizer, p, max_new_tokens=64)
        instruction = p.split("### Instruction\n", 1)[1].split("\n\n", 1)[0]
        results.append({"instruction": instruction, "response": out})
        print(f"\n### Instruction\n{instruction}\n\n### Response\n{out}\n")

    (PROJECT_ROOT / "outputs").mkdir(exist_ok=True)
    (PROJECT_ROOT / "outputs" / "generated_samples.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print("samples -> outputs/generated_samples.json")


if __name__ == "__main__":
    main()
