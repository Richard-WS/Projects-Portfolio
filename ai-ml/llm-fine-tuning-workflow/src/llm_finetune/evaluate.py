"""Evaluation helpers: perplexity math and sample generation."""

from __future__ import annotations

import math


def perplexity_from_loss(loss: float) -> float:
    """Perplexity from a mean cross-entropy loss: ``exp(loss)``."""
    if loss < 0:
        raise ValueError("loss cannot be negative")
    return math.exp(loss)


def mean_perplexity(losses: list[float]) -> float:
    """Perplexity from a list of per-batch mean losses.

    Averages the losses first (equivalent to pooling all batches), then
    exponentiates — matching how perplexity is reported for a corpus.
    """
    if not losses:
        raise ValueError("losses list is empty")
    return perplexity_from_loss(sum(losses) / len(losses))


def format_sample(instruction: str, response: str, max_chars: int = 200) -> str:
    """Pretty-print one instruction/response sample, truncated for logs."""
    resp = response.strip()
    if len(resp) > max_chars:
        resp = resp[:max_chars].rstrip() + "…"
    return f"### Instruction\n{instruction.strip()}\n\n### Response\n{resp}\n"
