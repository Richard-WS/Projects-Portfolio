"""End-to-end training smoke test.

Requires the ML stack (torch + transformers + peft + datasets), so it is
skipped automatically when the ``train`` extra is not installed — CI runs
the torch-free tests only, which keeps the pipeline fast and green.
"""

import shutil
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from llm_finetune.config import TrainConfig
from llm_finetune.data_prep import build_examples, write_jsonl
from llm_finetune.train import build_model_and_tokenizer, make_datasets, train

MODEL = "sshleifer/tiny-gpt2"  # shape-test fixture: validates pipeline mechanics only


@pytest.fixture(scope="module")
def tiny_data(tmp_path_factory):
    """A tiny formatted dataset on disk (no hub access needed)."""
    rows = [
        {"instruction": f"What is the capital of {country}?", "context": "", "response": f"The capital is {capital}."}
        for country, capital in [
            ("Canada", "Ottawa"),
            ("France", "Paris"),
            ("Japan", "Tokyo"),
            ("Brazil", "Brasilia"),
            ("Egypt", "Cairo"),
            ("Australia", "Canberra"),
            ("India", "New Delhi"),
            ("Mexico", "Mexico City"),
            ("Germany", "Berlin"),
            ("Spain", "Madrid"),
            ("Italy", "Rome"),
            ("Portugal", "Lisbon"),
        ]
    ]
    texts = build_examples(rows)
    path = tmp_path_factory.mktemp("data") / "tiny.jsonl"
    write_jsonl(path, texts)
    return str(path)


def test_build_model_uses_lora():
    cfg = TrainConfig(model_name=MODEL, lora_r=4)
    model, tokenizer = build_model_and_tokenizer(cfg)
    assert hasattr(model, "active_adapter")
    assert tokenizer.pad_token is not None
    # LoRA keeps the base frozen: trainable params should be a small
    # fraction of the full model.
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    assert trainable < total
    del model


def test_make_datasets_split(tiny_data):
    cfg = TrainConfig(model_name=MODEL, data_path=tiny_data, val_fraction=0.25, max_length=64)
    model, tokenizer = build_model_and_tokenizer(cfg)
    train_ds, eval_ds = make_datasets(cfg, tokenizer)
    assert len(train_ds) == 9
    assert len(eval_ds) == 3
    del model


def test_train_smoke(tiny_data, tmp_path):
    """One real training step; the adapter must be saved."""
    out_dir = tmp_path / "adapter"
    cfg = TrainConfig(
        model_name=MODEL,
        data_path=tiny_data,
        max_length=64,
        batch_size=2,
        epochs=1,
        max_steps=2,
        lora_r=4,
        lora_alpha=8,
        output_dir=str(out_dir),
    )
    metrics = train(cfg)

    assert metrics["final_perplexity"] > 0
    assert Path(out_dir, "adapter_model.safetensors").exists() or Path(out_dir, "adapter_model.bin").exists()
    assert Path(out_dir, "tokenizer_config.json").exists()
    assert metrics["trainable_params"] > 0
    shutil.rmtree(out_dir)
