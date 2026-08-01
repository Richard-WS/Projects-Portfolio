"""Prepare the instruction dataset for fine-tuning.

Downloads a sample of databricks/databricks-dolly-15k (CC-BY-SA-3.0) from
the Hugging Face hub, formats it into the instruction prompt template,
splits off a validation set, and writes train/validation JSONL files.

Outputs (both under data/raw/, gitignored):
  - data/raw/dolly_subset.jsonl       all formatted examples (train+val)
  - data/raw/dolly_train.jsonl        train split
  - data/raw/dolly_val.jsonl          validation split
  - data/raw/dolly_provenance.txt     dataset + license note

Usage:
    python scripts/prepare_data.py [--max-examples 1000] [--seed 42]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from llm_finetune.data_prep import build_examples, split_examples, write_jsonl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw"

DATASET_NAME = "databricks/databricks-dolly-15k"
LICENSE_NOTE = (
    f"Source: {DATASET_NAME} (Hugging Face hub), CC-BY-SA-3.0.\n"
    "Downsampled deterministically (seed + take). See "
    "https://huggingface.co/datasets/databricks/databricks-dolly-15k\n"
)


def fetch_rows(max_examples: int, seed: int) -> list[dict]:
    """Deterministically sample rows from the hub dataset."""
    from datasets import load_dataset

    ds = load_dataset(DATASET_NAME, split="train")
    ds = ds.shuffle(seed=seed).select(range(min(max_examples, len(ds))))
    return [{"instruction": r["instruction"], "context": r["context"], "response": r["response"]} for r in ds]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-examples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = fetch_rows(args.max_examples, args.seed)
    print(f"Fetched {len(rows)} rows from {DATASET_NAME}")

    examples = build_examples(rows)
    print(f"Formatted {len(examples)} usable examples (skipped {len(rows) - len(examples)} without a response)")

    train, val = split_examples(examples, val_fraction=0.1, seed=args.seed)
    RAW.mkdir(parents=True, exist_ok=True)
    write_jsonl(RAW / "dolly_subset.jsonl", train + val)
    write_jsonl(RAW / "dolly_train.jsonl", train)
    write_jsonl(RAW / "dolly_val.jsonl", val)
    (RAW / "dolly_provenance.txt").write_text(LICENSE_NOTE)

    print(f"Train: {len(train)} examples -> data/raw/dolly_train.jsonl")
    print(f"Val:   {len(val)} examples -> data/raw/dolly_val.jsonl")


if __name__ == "__main__":
    main()
