#!/usr/bin/env python3
"""
LoRA Fine-Tuning Script for ALRM Clause Extractor
══════════════════════════════════════════════════

This script is designed to run on Google Colab free tier (T4 GPU, 15GB VRAM).
It fine-tunes a Llama-3.1-8B-Instruct model using QLoRA (4-bit quantization +
LoRA adapters) on the instruction-tuning data produced by prepare_finetune_data.py.

┌─────────────────────────────────────────────────────────────────────────┐
│  COLAB SETUP — paste these into the first cell of a new Colab notebook │
│                                                                        │
│  !pip install -q torch transformers accelerate peft trl bitsandbytes   │
│  !pip install -q datasets einops sentencepiece protobuf                │
│  !pip install -q huggingface_hub                                       │
│                                                                        │
│  # Login to Hugging Face (required for gated Llama models)             │
│  from huggingface_hub import login                                     │
│  login(token="hf_YOUR_TOKEN_HERE")                                     │
│                                                                        │
│  # Upload your training data to Colab or mount Google Drive:           │
│  # from google.colab import drive                                      │
│  # drive.mount('/content/drive')                                       │
│  #                                                                     │
│  # Or upload train.jsonl / val.jsonl directly via Colab file upload.   │
└─────────────────────────────────────────────────────────────────────────┘

Hyperparameters (tuned for T4 15GB VRAM):
  - LoRA rank: 16, alpha: 32
  - Target modules: q_proj, v_proj
  - 4-bit quantization (NF4) via BitsAndBytes
  - 3 epochs, batch size 1, gradient accumulation 8
  - Cosine LR scheduler, peak LR 2e-4
  - Eval loss monitoring for early stopping insight

Usage (local or Colab):
  python scripts/finetune_extractor.py \\
      --train-file data/finetune/train.jsonl \\
      --val-file data/finetune/val.jsonl \\
      --output-dir models/lora_adapter \\
      --model meta-llama/Meta-Llama-3.1-8B-Instruct \\
      --epochs 3

The script will fail gracefully if GPU or required packages are unavailable,
printing clear error messages about what is missing.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _check_dependencies() -> list[str]:
    """Check for required packages and return list of missing ones."""
    missing = []
    for pkg in ["torch", "transformers", "peft", "trl", "bitsandbytes", "datasets"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return missing


def _check_gpu() -> bool:
    """Check if a CUDA GPU is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def load_jsonl(path: str) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def format_for_sft(example: dict) -> dict:
    """Format an instruction-tuning pair into a single 'text' field for SFTTrainer.

    Uses the Llama-3.1 chat template format:
      <|begin_of_text|><|start_header_id|>user<|end_header_id|>
      {instruction}
      <|eot_id|><|start_header_id|>assistant<|end_header_id|>
      {output}
      <|eot_id|>
    """
    text = (
        "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
        f"{example['instruction']}\n"
        "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        f"{example['output']}\n"
        "<|eot_id|>"
    )
    return {"text": text}


def run_training(args: argparse.Namespace) -> None:
    """Execute the full QLoRA fine-tuning pipeline."""
    # Colab: pip install torch transformers accelerate peft trl bitsandbytes datasets
    import torch
    from datasets import Dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer

    # ── Load data ──────────────────────────────────────────────────────────
    log.info("Loading training data from %s", args.train_file)
    train_records = load_jsonl(args.train_file)
    train_formatted = [format_for_sft(r) for r in train_records]
    train_dataset = Dataset.from_list(train_formatted)

    val_dataset = None
    if args.val_file and os.path.isfile(args.val_file):
        log.info("Loading validation data from %s", args.val_file)
        val_records = load_jsonl(args.val_file)
        val_formatted = [format_for_sft(r) for r in val_records]
        val_dataset = Dataset.from_list(val_formatted)

    log.info("Train: %d examples, Val: %s examples",
             len(train_dataset), len(val_dataset) if val_dataset else 0)

    # ── Quantization config (4-bit NF4) ───────────────────────────────────
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    # ── Load base model ───────────────────────────────────────────────────
    log.info("Loading base model: %s (4-bit quantized)", args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        model.config.pad_token_id = tokenizer.eos_token_id

    # ── LoRA config ───────────────────────────────────────────────────────
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    trainable, total = model.get_nb_trainable_parameters()
    log.info("Trainable parameters: %s / %s (%.2f%%)",
             f"{trainable:,}", f"{total:,}", 100 * trainable / total)

    # ── Training arguments ────────────────────────────────────────────────
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        weight_decay=0.01,
        fp16=True,
        logging_steps=5,
        save_strategy="epoch",
        eval_strategy="epoch" if val_dataset else "no",
        save_total_limit=2,
        load_best_model_at_end=True if val_dataset else False,
        metric_for_best_model="eval_loss" if val_dataset else None,
        greater_is_better=False,
        report_to="none",  # Disable wandb/tensorboard for Colab simplicity
        max_grad_norm=0.3,
        optim="paged_adamw_8bit",
    )

    # ── Trainer ───────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        max_seq_length=2048,
    )

    # ── Train ─────────────────────────────────────────────────────────────
    log.info("Starting training for %d epochs...", args.epochs)
    trainer.train()

    # ── Save adapter ──────────────────────────────────────────────────────
    log.info("Saving LoRA adapter to %s", output_dir)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Save training config for reproducibility
    config_path = os.path.join(output_dir, "training_config.json")
    with open(config_path, "w") as f:
        json.dump({
            "base_model": args.model,
            "lora_rank": args.lora_rank,
            "lora_alpha": args.lora_alpha,
            "target_modules": ["q_proj", "v_proj"],
            "epochs": args.epochs,
            "learning_rate": args.lr,
            "train_examples": len(train_dataset),
            "val_examples": len(val_dataset) if val_dataset else 0,
        }, f, indent=2)

    log.info("Training complete. Adapter saved to %s", output_dir)
    if val_dataset:
        eval_results = trainer.evaluate()
        log.info("Final eval loss: %.4f", eval_results.get("eval_loss", float("nan")))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LoRA fine-tune a Llama model for ALRM clause extraction"
    )
    parser.add_argument(
        "--train-file",
        default=os.path.join(_REPO_ROOT, "data", "finetune", "train.jsonl"),
        help="Path to training JSONL file",
    )
    parser.add_argument(
        "--val-file",
        default=os.path.join(_REPO_ROOT, "data", "finetune", "val.jsonl"),
        help="Path to validation JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(_REPO_ROOT, "models", "lora_adapter"),
        help="Directory to save LoRA adapter weights",
    )
    parser.add_argument(
        "--model",
        default="meta-llama/Meta-Llama-3.1-8B-Instruct",
        help="Base model name or path (default: Meta-Llama-3.1-8B-Instruct)",
    )
    parser.add_argument(
        "--lora-rank", type=int, default=16,
        help="LoRA rank (default: 16)",
    )
    parser.add_argument(
        "--lora-alpha", type=int, default=32,
        help="LoRA alpha (default: 32)",
    )
    parser.add_argument(
        "--epochs", type=int, default=3,
        help="Number of training epochs (default: 3)",
    )
    parser.add_argument(
        "--lr", type=float, default=2e-4,
        help="Peak learning rate (default: 2e-4)",
    )
    args = parser.parse_args()

    # ── Pre-flight checks ─────────────────────────────────────────────────
    missing = _check_dependencies()
    if missing:
        print(f"\nMissing required packages: {', '.join(missing)}")
        print("\nInstall them with:")
        print(f"  pip install {' '.join(missing)}")
        print("\nFor Google Colab, paste into a cell:")
        print("  !pip install -q torch transformers accelerate peft trl bitsandbytes datasets")
        sys.exit(1)

    if not _check_gpu():
        print("\nNo CUDA GPU detected. This script requires a GPU to run.")
        print("On Google Colab: Runtime -> Change runtime type -> T4 GPU")
        print("\nTo generate training data without GPU, run:")
        print("  python scripts/prepare_finetune_data.py")
        sys.exit(1)

    if not os.path.isfile(args.train_file):
        print(f"\nTraining file not found: {args.train_file}")
        print("Generate it first:")
        print("  python scripts/prepare_finetune_data.py")
        sys.exit(1)

    run_training(args)


if __name__ == "__main__":
    main()
