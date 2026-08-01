"""Configuration for the fine-tuning workflow.

Configs are plain YAML files loaded into a validated ``TrainConfig``
dataclass. Unknown keys and invalid values fail fast, so a typo in a
config never silently changes a run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml


@dataclass
class TrainConfig:
    # Model and data
    model_name: str = "distilgpt2"
    data_path: str = "data/raw/dolly_subset.jsonl"
    max_examples: int = 400
    val_fraction: float = 0.1

    # Tokenizer / sequence
    max_length: int = 256

    # Training
    batch_size: int = 4
    learning_rate: float = 3e-4
    epochs: int = 1
    max_steps: int = -1  # -1 means "run the full epochs"

    # LoRA
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05

    # Reproducibility / output
    seed: int = 42
    output_dir: str = "models/fine-tuned"

    def validate(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if self.max_examples < 1:
            raise ValueError("max_examples must be >= 1")
        if not 0.0 < self.val_fraction < 1.0:
            raise ValueError("val_fraction must be strictly between 0 and 1")
        if self.max_length < 32:
            raise ValueError("max_length must be >= 32")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if self.epochs < 0:
            raise ValueError("epochs must be >= 0")
        if self.lora_r < 1:
            raise ValueError("lora_r must be >= 1")


_KNOWN = {f.name for f in fields(TrainConfig)}


def _coerce_numeric_strings(raw: dict) -> dict:
    """PyYAML leaves values like ``3e-4`` as strings (no decimal point).

    Coerce string values back to int/float for fields typed as such, so
    conventional scientific notation in configs behaves as expected.
    """
    coerced = dict(raw)
    # NOTE: with `from __future__ import annotations`, field type names are
    # strings ("int"/"float"), so compare against the names directly.
    for name, val in list(coerced.items()):
        ftype = TrainConfig.__dataclass_fields__[name].type if name in _KNOWN else None
        if ftype in ("int", "float") and isinstance(val, str):
            try:
                coerced[name] = float(val) if ftype == "float" else int(val)
            except ValueError:
                pass  # leave for validate() to report clearly
    return coerced


def load_config(path: str | Path) -> TrainConfig:
    """Load a YAML config, validating keys and values."""
    path = Path(path)
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}

    unknown = set(raw) - _KNOWN
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)} (in {path})")

    cfg = TrainConfig(**{**raw, **_coerce_numeric_strings({k: v for k, v in raw.items()})})
    cfg.validate()
    return cfg


def config_to_dict(cfg: TrainConfig) -> dict:
    """Dataclass back to plain dict (for logging / reporting)."""
    return asdict(cfg)
