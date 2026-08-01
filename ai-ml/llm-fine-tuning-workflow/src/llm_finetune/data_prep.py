"""Data preparation for instruction fine-tuning.

Pure Python (no torch/transformers imports at module level) so the
formatting, splitting, and file I/O are testable without the ML stack.

The prompt template follows the classic instruction-tuning format:

    ### Instruction
    <instruction>

    ### Response
    <response>
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Iterable


def format_prompt(instruction: str, response: str, context: str = "") -> str:
    """Format one instruction/response pair into a training example."""
    instruction = instruction.strip()
    response = response.strip()
    if not instruction:
        raise ValueError("instruction must not be empty")
    if not response:
        raise ValueError("response must not be empty")

    parts = [f"### Instruction\n{instruction}"]
    if context:
        parts.append(f"### Context\n{context.strip()}")
    parts.append(f"### Response\n{response}")
    return "\n\n".join(parts) + "\n"


def build_examples(rows: Iterable[dict[str, Any]]) -> list[str]:
    """Convert raw dataset rows (instruction/context/response) to texts.

    Rows without a usable response are skipped.
    """
    texts = []
    for row in rows:
        instruction = (row.get("instruction") or "").strip()
        response = (row.get("response") or "").strip()
        if not instruction or not response:
            continue
        texts.append(format_prompt(instruction, response, row.get("context") or ""))
    return texts


def split_examples(examples: list[str], val_fraction: float, seed: int = 42) -> tuple[list[str], list[str]]:
    """Deterministic train/validation split (shuffled with the given seed)."""
    if not 0.0 < val_fraction < 1.0:
        raise ValueError("val_fraction must be strictly between 0 and 1")
    rng = random.Random(seed)
    shuffled = list(examples)
    rng.shuffle(shuffled)
    n_val = max(1, int(len(shuffled) * val_fraction))
    n_train = len(shuffled) - n_val
    return shuffled[:n_train], shuffled[n_train:]


def write_jsonl(path: str | Path, texts: list[str]) -> None:
    """Write examples as newline-delimited JSON (one {"text": ...} per line)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for t in texts:
            fh.write(json.dumps({"text": t}) + "\n")


def read_jsonl(path: str | Path) -> list[str]:
    """Read examples written by :func:`write_jsonl`."""
    path = Path(path)
    texts = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            texts.append(json.loads(line)["text"])
    return texts
