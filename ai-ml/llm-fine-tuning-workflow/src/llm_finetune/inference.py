"""Local inference with a fine-tuned LoRA adapter."""

from __future__ import annotations

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def load_adapter(base_model_name: str, adapter_dir: str):
    """Load the base model + LoRA adapter and its tokenizer."""
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model_name)
    model = PeftModel.from_pretrained(model, adapter_dir)
    model.eval()
    return model, tokenizer


def generate(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 64,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> str:
    """Complete a prompt with the fine-tuned model."""
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)


def instruction_prompt(instruction: str, context: str = "") -> str:
    """Wrap an instruction in the same template used for training."""
    parts = [f"### Instruction\n{instruction.strip()}"]
    if context:
        parts.append(f"### Context\n{context.strip()}")
    parts.append("### Response\n")
    return "\n\n".join(parts)
