"""Tokenizer integration (transformers is imported lazily)."""

from __future__ import annotations

from typing import Any


def tokenize_dataset(
    texts_path: str,
    tokenizer_name: str,
    max_length: int,
) -> tuple[Any, dict[str, list[Any]]]:
    """Tokenize the prepared texts with a Hugging Face tokenizer.

    Returns ``(tokenizer, features)`` where ``features`` maps
    ``input_ids``/``attention_mask`` to lists, ready to build a
    ``datasets.Dataset``.

    This import is intentionally lazy so the rest of the package stays
    usable without the ML stack installed.
    """
    from transformers import AutoTokenizer

    from .data_prep import read_jsonl

    texts = read_jsonl(texts_path)

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tokenized = tokenizer(
        texts,
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors="np",
    )
    features = {
        "input_ids": [ids.tolist() for ids in tokenized["input_ids"]],
        "attention_mask": [mask.tolist() for mask in tokenized["attention_mask"]],
    }
    return tokenizer, features
