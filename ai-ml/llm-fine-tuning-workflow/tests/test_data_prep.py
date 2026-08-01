"""Tests for data preparation (pure python, no ML stack)."""

import pytest

from llm_finetune.data_prep import (
    build_examples,
    format_prompt,
    read_jsonl,
    split_examples,
    write_jsonl,
)


def test_format_prompt_basic():
    out = format_prompt("What is 2+2?", "4")
    assert "### Instruction\nWhat is 2+2?" in out
    assert "### Response\n4" in out


def test_format_prompt_with_context():
    out = format_prompt("Summarize", "Done", context="A long article")
    assert "### Context\nA long article" in out


def test_format_prompt_rejects_empty():
    with pytest.raises(ValueError):
        format_prompt("", "response")
    with pytest.raises(ValueError):
        format_prompt("instruction", "")


def test_build_examples_skips_bad_rows():
    rows = [
        {"instruction": "A", "context": "", "response": "1"},
        {"instruction": "B", "context": "", "response": ""},  # skipped
        {"instruction": "", "context": "", "response": "3"},  # skipped
        {"instruction": "C", "context": "ctx", "response": "2"},
    ]
    out = build_examples(rows)
    assert len(out) == 2
    assert "### Response\n1" in out[0]
    assert "### Context\nctx" in out[1]


def test_split_examples_deterministic():
    examples = [f"example {i}" for i in range(100)]
    a1, b1 = split_examples(examples, 0.2, seed=42)
    a2, b2 = split_examples(examples, 0.2, seed=42)
    assert a1 == a2 and b1 == b2
    assert len(a1) == 80 and len(b1) == 20
    assert set(a1) | set(b1) == set(examples)  # no loss


def test_split_rejects_bad_fraction():
    with pytest.raises(ValueError):
        split_examples(["a"], 0.0)
    with pytest.raises(ValueError):
        split_examples(["a"], 1.0)


def test_jsonl_roundtrip(tmp_path):
    p = tmp_path / "ex.jsonl"
    texts = ["hello", "world"]
    write_jsonl(p, texts)
    assert read_jsonl(p) == texts
