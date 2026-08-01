"""Interactive local inference with a fine-tuned adapter.

Usage (from the project directory):
    python scripts/run_inference.py configs/default.yaml --prompt "Explain what a database index is"

Or pipe prompts via stdin.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm_finetune.config import load_config
from llm_finetune.inference import generate, instruction_prompt, load_adapter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="path to config yaml")
    parser.add_argument("--prompt", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    model, tokenizer = load_adapter(cfg.model_name, cfg.output_dir)

    if args.prompt:
        prompts = [args.prompt]
    else:
        print("Enter instructions (blank line to quit):")
        prompts = []
        while True:
            line = input("> ").strip()
            if not line:
                break
            prompts.append(line)

    for p in prompts:
        print(f"\n### Instruction\n{p}\n")
        print(generate(model, tokenizer, instruction_prompt(p)))
        print("-" * 50)


if __name__ == "__main__":
    main()
