#!/usr/bin/env python3
"""
Model Comparison Framework for ALRM Clause Extraction
──────────────────────────────────────────────────────
Benchmarks different LLM backends on clause extraction quality and latency:
  1. Ollama (local 8B model) — free, always tested if Ollama is running
  2. Groq API (70B model) — free tier, requires GROQ_API_KEY
  3. Fine-tuned LoRA adapter — requires adapter in models/lora_adapter/

Metrics per category:
  - Field-level F1 score (boolean fields)
  - Average latency per extraction
  - Estimated cost per 1000 extractions

Skips unavailable backends gracefully.

Usage:
  python scripts/compare_models.py [--clause-types liability termination] [--max-samples 5]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)


# ── Backend availability checks ────────────────────────────────────────────


def _check_ollama() -> bool:
    """Check if Ollama is running and reachable."""
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _check_groq() -> bool:
    """Check if Groq API key is set."""
    return bool(os.environ.get("GROQ_API_KEY"))


def _check_finetuned() -> bool:
    """Check if LoRA adapter weights exist."""
    adapter_path = os.path.join(_REPO_ROOT, "models", "lora_adapter")
    return os.path.isdir(adapter_path) and any(
        f.endswith((".bin", ".safetensors", "adapter_config.json"))
        for f in os.listdir(adapter_path)
    )


# ── Eval data loading ──────────────────────────────────────────────────────


def load_eval_data(clause_type: str, max_samples: int = 10) -> list[dict]:
    """Load eval data for a clause type. Returns list of {text, ground_truth}."""
    eval_path = os.path.join(_REPO_ROOT, "data", "eval", f"{clause_type}_eval.json")
    if not os.path.isfile(eval_path):
        return []
    with open(eval_path, "r") as f:
        data = json.load(f)
    # Take up to max_samples
    return data[:max_samples]


# ── Extraction wrappers ───────────────────────────────────────────────────


def run_extraction(
    clause_text: str,
    clause_type: str,
    backend: str,
) -> tuple[Optional[dict], float]:
    """Run extraction with a specific backend. Returns (result_dict, latency_seconds).

    Sets environment variables to route to the correct backend, then calls
    the extractor. Returns (None, latency) on failure.
    """
    from backend.extraction.extractor import extract_clause

    # Save and set env vars for backend routing
    orig_groq = os.environ.get("GROQ_API_KEY")
    orig_backend = os.environ.get("LLM_BACKEND")

    try:
        if backend == "ollama":
            os.environ.pop("GROQ_API_KEY", None)
            os.environ.pop("LLM_BACKEND", None)
        elif backend == "groq":
            # GROQ_API_KEY should already be set
            os.environ.pop("LLM_BACKEND", None)
        elif backend == "finetuned":
            os.environ["LLM_BACKEND"] = "finetuned"
            os.environ.pop("GROQ_API_KEY", None)

        start = time.monotonic()
        result = extract_clause(clause_text, clause_type=clause_type, max_retries=1)
        elapsed = time.monotonic() - start

        if result is not None:
            return result.model_dump(), elapsed
        return None, elapsed

    except Exception as exc:
        return None, 0.0

    finally:
        # Restore env vars
        if orig_groq is not None:
            os.environ["GROQ_API_KEY"] = orig_groq
        else:
            os.environ.pop("GROQ_API_KEY", None)
        if orig_backend is not None:
            os.environ["LLM_BACKEND"] = orig_backend
        else:
            os.environ.pop("LLM_BACKEND", None)


# ── Metrics ────────────────────────────────────────────────────────────────


def _flatten_bools(d: dict, prefix: str = "") -> dict[str, bool]:
    """Recursively extract boolean fields from a nested dict."""
    result = {}
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, bool):
            result[full_key] = value
        elif isinstance(value, dict):
            result.update(_flatten_bools(value, full_key))
    return result


def compute_f1(predicted: dict, ground_truth: dict) -> dict:
    """Compute field-level precision, recall, F1 for boolean fields.

    Compares boolean fields in predicted extraction against ground_truth.
    Returns {"precision": float, "recall": float, "f1": float, "total_fields": int}.
    """
    gt_bools = _flatten_bools(ground_truth)
    pred_bools = _flatten_bools(predicted) if predicted else {}

    if not gt_bools:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "total_fields": 0}

    tp = fp = fn = 0
    for field, gt_val in gt_bools.items():
        pred_val = pred_bools.get(field)
        if gt_val is True:
            if pred_val is True:
                tp += 1
            else:
                fn += 1
        else:  # gt_val is False
            if pred_val is True:
                fp += 1
            # True negatives don't affect P/R/F1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "total_fields": len(gt_bools),
    }


# ── Cost estimates ─────────────────────────────────────────────────────────

COST_PER_1K = {
    "ollama": "$0.00 (local, electricity only)",
    "groq": "~$0.00 (free tier, rate-limited)",
    "finetuned": "$0.00 (local, electricity only)",
}


# ── Main comparison logic ─────────────────────────────────────────────────


def run_comparison(
    clause_types: list[str],
    backends: list[str],
    max_samples: int = 5,
) -> dict:
    """Run extraction comparison across backends and clause types.

    Returns nested dict: results[backend][clause_type] = {f1, latency, ...}
    """
    results: dict[str, dict] = {b: {} for b in backends}

    for clause_type in clause_types:
        eval_data = load_eval_data(clause_type, max_samples=max_samples)
        if not eval_data:
            print(f"  WARNING: No eval data for '{clause_type}' — skipping")
            continue

        for backend in backends:
            print(f"  Running {backend} on {clause_type} ({len(eval_data)} samples)...", end=" ", flush=True)

            f1_scores = []
            latencies = []
            successes = 0

            for item in eval_data:
                pred, latency = run_extraction(item["text"], clause_type, backend)
                latencies.append(latency)
                if pred is not None:
                    successes += 1
                    metrics = compute_f1(pred, item["ground_truth"])
                    f1_scores.append(metrics["f1"])

            avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

            results[backend][clause_type] = {
                "avg_f1": round(avg_f1, 3),
                "avg_latency_s": round(avg_latency, 2),
                "success_rate": f"{successes}/{len(eval_data)}",
                "cost_per_1k": COST_PER_1K.get(backend, "unknown"),
            }
            print(f"F1={avg_f1:.3f}, latency={avg_latency:.1f}s, success={successes}/{len(eval_data)}")

    return results


def print_comparison_table(results: dict, clause_types: list[str]) -> None:
    """Print a formatted comparison table to stdout."""
    # Header
    print("\n" + "=" * 80)
    print("MODEL COMPARISON RESULTS")
    print("=" * 80)

    backends = list(results.keys())

    for clause_type in clause_types:
        has_data = any(clause_type in results[b] for b in backends)
        if not has_data:
            continue

        print(f"\n--- {clause_type.upper()} ---")
        print(f"{'Backend':<15} {'F1':>8} {'Latency':>10} {'Success':>10} {'Cost/1K':>30}")
        print("-" * 75)

        for backend in backends:
            if clause_type in results[backend]:
                r = results[backend][clause_type]
                print(
                    f"{backend:<15} {r['avg_f1']:>8.3f} {r['avg_latency_s']:>8.1f}s "
                    f"{r['success_rate']:>10} {r['cost_per_1k']:>30}"
                )
            else:
                print(f"{backend:<15} {'(no data)':>8}")

    # Overall averages
    print(f"\n--- OVERALL AVERAGES ---")
    print(f"{'Backend':<15} {'Avg F1':>8} {'Avg Latency':>12}")
    print("-" * 40)
    for backend in backends:
        all_f1 = [r["avg_f1"] for r in results[backend].values()]
        all_lat = [r["avg_latency_s"] for r in results[backend].values()]
        if all_f1:
            print(f"{backend:<15} {sum(all_f1)/len(all_f1):>8.3f} {sum(all_lat)/len(all_lat):>10.1f}s")
        else:
            print(f"{backend:<15} {'(skipped)':>8}")

    print("\n" + "=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ALRM extraction backends (Ollama, Groq, Fine-tuned)"
    )
    parser.add_argument(
        "--clause-types",
        nargs="+",
        default=["liability", "termination", "governing_law"],
        help="Clause types to test (default: liability termination governing_law)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=5,
        help="Max eval samples per clause type (default: 5)",
    )
    args = parser.parse_args()

    print("Checking available backends...")

    available_backends = []

    if _check_ollama():
        available_backends.append("ollama")
        print("  Ollama:     AVAILABLE")
    else:
        print("  Ollama:     NOT AVAILABLE (is Ollama running?)")

    if _check_groq():
        available_backends.append("groq")
        print("  Groq:       AVAILABLE (GROQ_API_KEY set)")
    else:
        print("  Groq:       SKIPPED (no GROQ_API_KEY)")

    if _check_finetuned():
        available_backends.append("finetuned")
        print("  Fine-tuned: AVAILABLE (adapter found)")
    else:
        print("  Fine-tuned: SKIPPED (no adapter in models/lora_adapter/)")

    if not available_backends:
        print("\nNo backends available. Start Ollama or set GROQ_API_KEY.")
        sys.exit(1)

    print(f"\nRunning comparison with: {', '.join(available_backends)}")
    print(f"Clause types: {', '.join(args.clause_types)}")
    print(f"Max samples per type: {args.max_samples}\n")

    results = run_comparison(args.clause_types, available_backends, args.max_samples)
    print_comparison_table(results, args.clause_types)


if __name__ == "__main__":
    main()
