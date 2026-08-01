"""Tests for evaluation math (pure python, no ML stack)."""

import math

import pytest

from llm_finetune.evaluate import format_sample, mean_perplexity, perplexity_from_loss


def test_perplexity_from_loss_known_value():
    # Perplexity of a model that is right 75% of the time (2-class)
    # is exp(-ln(0.75)) = 4/3.
    loss = -math.log(0.75)
    assert perplexity_from_loss(loss) == pytest.approx(4 / 3)


def test_perplexity_zero_loss():
    assert perplexity_from_loss(0.0) == pytest.approx(1.0)


def test_perplexity_rejects_negative_loss():
    with pytest.raises(ValueError):
        perplexity_from_loss(-0.1)


def test_mean_perplexity_pools_batches():
    # Two batches with losses 0 and 2*ln(10): pooled mean loss = ln(10),
    # so perplexity = 10.
    losses = [0.0, 2 * math.log(10)]
    assert mean_perplexity(losses) == pytest.approx(10.0)


def test_mean_perplexity_empty_raises():
    with pytest.raises(ValueError):
        mean_perplexity([])


def test_format_sample_truncates():
    long_response = "x" * 500
    out = format_sample("q", long_response, max_chars=50)
    assert "…" in out
    assert len(out) < 200


def test_format_sample_short_response_untouched():
    out = format_sample("q", "ok")
    assert "ok" in out
