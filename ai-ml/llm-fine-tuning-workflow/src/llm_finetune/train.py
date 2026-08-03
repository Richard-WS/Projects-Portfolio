"""LoRA fine-tuning with the Hugging Face Trainer."""

from __future__ import annotations

import math
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

from .config import TrainConfig

# GPT-2-family target modules for LoRA. Other architectures may need a
# different list — see the README notes.
TARGET_MODULES_GPT2 = ["attn.c_attn", "attn.c_proj"]


def build_model_and_tokenizer(cfg: TrainConfig):
    """Load the base model and tokenizer, then wrap the model in LoRA."""
    model = AutoModelForCausalLM.from_pretrained(cfg.model_name)
    tokenizer = AutoTokenizer.from_pretrained(cfg.model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=TARGET_MODULES_GPT2,
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.config.use_cache = False  # required for gradient checkpointing-friendly train loop
    model.print_trainable_parameters()
    return model, tokenizer


def make_datasets(cfg: TrainConfig, tokenizer) -> tuple[Dataset, Dataset]:
    """Build train/validation ``datasets.Dataset`` objects from the config."""
    from .data_prep import read_jsonl

    texts = read_jsonl(cfg.data_path)
    tokenized = tokenizer(
        texts,
        truncation=True,
        max_length=cfg.max_length,
        padding="max_length",
        return_tensors="np",
    )
    features = {
        "input_ids": [ids.tolist() for ids in tokenized["input_ids"]],
        "attention_mask": [mask.tolist() for mask in tokenized["attention_mask"]],
    }
    ds = Dataset.from_dict(features)
    n_val = max(1, int(len(ds) * cfg.val_fraction))
    train_ds = ds.select(range(len(ds) - n_val))
    eval_ds = ds.select(range(len(ds) - n_val, len(ds)))
    return train_ds, eval_ds


def train(cfg: TrainConfig) -> dict:
    """Run the training loop. Returns evaluation metrics dict."""
    torch.manual_seed(cfg.seed)

    model, tokenizer = build_model_and_tokenizer(cfg)
    train_ds, eval_ds = make_datasets(cfg, tokenizer)

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    args = TrainingArguments(
        output_dir=cfg.output_dir,
        per_device_train_batch_size=cfg.batch_size,
        per_device_eval_batch_size=cfg.batch_size,
        learning_rate=cfg.learning_rate,
        num_train_epochs=cfg.epochs,
        max_steps=cfg.max_steps if cfg.max_steps > 0 else -1,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        seed=cfg.seed,
        dataloader_num_workers=0,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
    )

    # Baseline (untrained adapter) perplexity on the validation set.
    baseline_loss = trainer.evaluate(eval_dataset=eval_ds)
    baseline_ppl = math.exp(baseline_loss["eval_loss"])

    trainer.train()

    # Per-step training loss from the trainer's log history (logging_steps=1),
    # the data behind the training-curve chart.
    loss_curve = [
        {"step": h.get("step"), "train_loss": h["loss"]}
        for h in trainer.state.log_history
        if "loss" in h and "eval_loss" not in h
    ]

    # Final evaluation with the trained adapter.
    final_metrics = trainer.evaluate(eval_dataset=eval_ds)
    final_ppl = math.exp(final_metrics["eval_loss"])

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)

    return {
        "baseline_eval_loss": baseline_loss["eval_loss"],
        "baseline_perplexity": baseline_ppl,
        "final_eval_loss": final_metrics["eval_loss"],
        "final_perplexity": final_ppl,
        "train_loss": trainer.state.log_history[-1].get("loss"),
        "loss_curve": loss_curve,
        "output_dir": str(out_dir),
        "trainable_params": sum(p.numel() for p in model.parameters() if p.requires_grad),
    }
