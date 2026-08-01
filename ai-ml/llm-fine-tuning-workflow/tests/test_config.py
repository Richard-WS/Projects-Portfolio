"""Tests for config loading and validation (no ML stack required)."""

import pytest

from llm_finetune.config import TrainConfig, load_config


def test_defaults_validate():
    cfg = TrainConfig()
    cfg.validate()  # should not raise
    assert cfg.model_name == "distilgpt2"


def test_load_config_roundtrip(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text(
        "model_name: gpt2\n"
        "max_examples: 50\n"
        "val_fraction: 0.2\n"
        "output_dir: models/x\n"
    )
    cfg = load_config(p)
    assert cfg.model_name == "gpt2"
    assert cfg.max_examples == 50
    assert cfg.val_fraction == 0.2
    assert cfg.output_dir == "models/x"
    # defaults for unspecified fields
    assert cfg.batch_size == 4


def test_unknown_key_rejected(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("model_name: gpt2\nbogus_key: 1\n")
    with pytest.raises(ValueError, match="Unknown config keys"):
        load_config(p)


def test_scientific_notation_coerced(tmp_path):
    # PyYAML parses "3e-4" as a string; the loader must coerce it to float.
    p = tmp_path / "cfg.yaml"
    p.write_text("model_name: gpt2\nlearning_rate: 3e-4\n")
    cfg = load_config(p)
    assert isinstance(cfg.learning_rate, float)
    assert cfg.learning_rate == pytest.approx(0.0003)


def test_empty_model_name_rejected():
    cfg = TrainConfig(model_name="   ")
    with pytest.raises(ValueError, match="model_name"):
        cfg.validate()


def test_bad_val_fraction_rejected():
    with pytest.raises(ValueError, match="val_fraction"):
        TrainConfig(val_fraction=1.5).validate()
    with pytest.raises(ValueError, match="val_fraction"):
        TrainConfig(val_fraction=0.0).validate()


def test_bad_learning_rate_rejected():
    with pytest.raises(ValueError, match="learning_rate"):
        TrainConfig(learning_rate=0).validate()


def test_bad_lora_r_rejected():
    with pytest.raises(ValueError, match="lora_r"):
        TrainConfig(lora_r=0).validate()
