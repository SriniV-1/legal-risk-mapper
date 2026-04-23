"""
Extraction Eval Harness
───────────────────────
Field-level precision, recall, and F1 for structured clause extraction.

Evaluates boolean fields (exact match), categorical fields (exact match),
list fields (set overlap), and source_text grounding (substring check).

Usage:
    python -m backend.extraction.eval --eval-file data/eval/liability_eval.json
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class FieldMetrics:
    """Per-field evaluation metrics."""
    field_name: str
    tp: int = 0  # true positives
    fp: int = 0  # false positives
    fn: int = 0  # false negatives
    tn: int = 0  # true negatives
    total: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.total if self.total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "field": self.field_name,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
            "accuracy": round(self.accuracy, 3),
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
            "total": self.total,
        }


@dataclass
class EvalResult:
    """Overall evaluation result."""
    field_metrics: dict[str, FieldMetrics] = field(default_factory=dict)
    grounding_scores: list[float] = field(default_factory=list)
    extraction_success_rate: float = 0.0
    total_examples: int = 0

    # Core boolean fields used for pass/fail (excludes categorical sub-fields)
    CORE_FIELDS = {
        "has_cap", "is_mutual", "has_carve_outs",
        "consequential_excluded", "has_indemnification", "has_warranty_disclaimer",
    }

    @property
    def macro_f1(self) -> float:
        """Macro F1 over core boolean fields only (excludes cap_type)."""
        f1s = [m.f1 for m in self.field_metrics.values()
               if m.total > 0 and m.field_name in self.CORE_FIELDS]
        return sum(f1s) / len(f1s) if f1s else 0.0

    @property
    def macro_f1_all(self) -> float:
        """Macro F1 including all fields (informational)."""
        f1s = [m.f1 for m in self.field_metrics.values() if m.total > 0]
        return sum(f1s) / len(f1s) if f1s else 0.0

    @property
    def avg_grounding(self) -> float:
        return sum(self.grounding_scores) / len(self.grounding_scores) if self.grounding_scores else 0.0

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "EXTRACTION EVAL RESULTS",
            "=" * 60,
            f"Examples: {self.total_examples}",
            f"Extraction success rate: {self.extraction_success_rate:.1%}",
            f"Macro F1 (core booleans): {self.macro_f1:.3f} (target: > 0.750)",
            f"Macro F1 (all fields):    {self.macro_f1_all:.3f}",
            f"Avg grounding score: {self.avg_grounding:.3f}",
            "",
            f"{'Field':<30s} {'P':>6s} {'R':>6s} {'F1':>6s} {'Acc':>6s}  {'TP':>3s} {'FP':>3s} {'FN':>3s} {'TN':>3s}",
            "-" * 75,
        ]
        for name, m in sorted(self.field_metrics.items()):
            lines.append(
                f"{name:<30s} {m.precision:>6.3f} {m.recall:>6.3f} {m.f1:>6.3f} {m.accuracy:>6.3f}  {m.tp:>3d} {m.fp:>3d} {m.fn:>3d} {m.tn:>3d}"
            )
        lines.extend([
            "-" * 75,
            f"{'MACRO AVG (core)':<30s} {'':>6s} {'':>6s} {self.macro_f1:>6.3f}",
            f"{'MACRO AVG (all)':<30s} {'':>6s} {'':>6s} {self.macro_f1_all:>6.3f}",
            "=" * 60,
            f"PASS: core F1 = {self.macro_f1:.3f} >= 0.75" if self.macro_f1 >= 0.75
            else f"FAIL: core F1 = {self.macro_f1:.3f} < 0.75",
        ])
        return "\n".join(lines)


# ── Comparison helpers ───────────────────────────────────────────────────────

def _compare_bool(predicted: Optional[bool], ground_truth: bool, metrics: FieldMetrics):
    """Compare a boolean field."""
    metrics.total += 1
    pred = bool(predicted) if predicted is not None else False

    if pred and ground_truth:
        metrics.tp += 1
    elif pred and not ground_truth:
        metrics.fp += 1
    elif not pred and ground_truth:
        metrics.fn += 1
    else:
        metrics.tn += 1


def _compare_categorical(predicted: Optional[str], ground_truth: Optional[str], metrics: FieldMetrics):
    """Compare a categorical field (exact match)."""
    if ground_truth is None:
        return
    metrics.total += 1
    if predicted == ground_truth:
        metrics.tp += 1
    else:
        metrics.fp += 1
        metrics.fn += 1


def _check_grounding(source_text: Optional[str], clause_text: str) -> float:
    """Check if source_text is actually present in the clause. Returns 0 or 1."""
    if source_text is None:
        return 1.0  # null source_text is fine if field is null
    normalized_source = " ".join(source_text.lower().split())
    normalized_clause = " ".join(clause_text.lower().split())
    if normalized_source in normalized_clause:
        return 1.0
    # Fuzzy: check if first 50 chars match (handles truncation)
    if len(normalized_source) > 50 and normalized_source[:50] in normalized_clause:
        return 0.8
    return 0.0


# ── Main eval function ───────────────────────────────────────────────────────

def evaluate_liability(
    eval_file: str | Path,
    extractions: list[dict],
) -> EvalResult:
    """
    Evaluate liability extractions against ground truth.

    Args:
        eval_file: Path to eval JSON file with ground_truth labels.
        extractions: List of extraction result dicts (from extractor.batch_extract
                     or extract_clause). Each must have 'id' and 'extracted_data'.
    """
    with open(eval_file) as f:
        eval_data = json.load(f)

    gt_by_id = {e["id"]: e for e in eval_data}
    ext_by_id = {}
    for e in extractions:
        eid = e.get("id") or e.get("chunk_id")
        if eid:
            ext_by_id[eid] = e

    result = EvalResult(total_examples=len(eval_data))

    # Initialize field metrics
    fields = [
        "has_cap", "cap_type", "is_mutual", "has_carve_outs",
        "consequential_excluded", "has_indemnification", "has_warranty_disclaimer",
    ]
    for f_name in fields:
        result.field_metrics[f_name] = FieldMetrics(field_name=f_name)

    success_count = 0
    for gt_item in eval_data:
        item_id = gt_item["id"]
        gt = gt_item["ground_truth"]
        ext_item = ext_by_id.get(item_id)

        if ext_item is None or ext_item.get("extracted_data") is None:
            # Count as all false negatives
            for f_name in fields:
                result.field_metrics[f_name].total += 1
                gt_val = _get_gt_field(gt, f_name)
                if gt_val:
                    result.field_metrics[f_name].fn += 1
                else:
                    result.field_metrics[f_name].tn += 1
            continue

        success_count += 1
        ext = ext_item["extracted_data"]

        # Boolean fields
        _compare_bool(
            ext.get("liability_cap", {}).get("has_cap"),
            gt["liability_cap"]["has_cap"],
            result.field_metrics["has_cap"],
        )
        _compare_bool(
            ext.get("is_mutual"),
            gt["is_mutual"],
            result.field_metrics["is_mutual"],
        )
        _compare_bool(
            ext.get("has_carve_outs"),
            gt["has_carve_outs"],
            result.field_metrics["has_carve_outs"],
        )
        _compare_bool(
            ext.get("consequential_damages", {}).get("excluded"),
            gt["consequential_damages"]["excluded"],
            result.field_metrics["consequential_excluded"],
        )
        _compare_bool(
            ext.get("has_indemnification"),
            gt["has_indemnification"],
            result.field_metrics["has_indemnification"],
        )
        _compare_bool(
            ext.get("has_warranty_disclaimer"),
            gt["has_warranty_disclaimer"],
            result.field_metrics["has_warranty_disclaimer"],
        )

        # Categorical
        _compare_categorical(
            ext.get("liability_cap", {}).get("cap_type"),
            gt["liability_cap"].get("cap_type"),
            result.field_metrics["cap_type"],
        )

        # Grounding checks
        clause_text = gt_item["text"]
        for source_field in [
            ext.get("liability_cap", {}).get("cap_source_text"),
            ext.get("mutuality_source_text"),
            ext.get("carve_outs_source_text"),
            ext.get("consequential_damages", {}).get("exclusion_source_text"),
            ext.get("indemnification_source_text"),
            ext.get("warranty_disclaimer_source_text"),
        ]:
            score = _check_grounding(source_field, clause_text)
            result.grounding_scores.append(score)

    result.extraction_success_rate = success_count / len(eval_data) if eval_data else 0.0
    return result


def _get_gt_field(gt: dict, field_name: str) -> bool:
    """Get a ground truth boolean value by field name."""
    if field_name == "has_cap":
        return gt["liability_cap"]["has_cap"]
    elif field_name == "cap_type":
        return gt["liability_cap"].get("cap_type") is not None
    elif field_name == "consequential_excluded":
        return gt["consequential_damages"]["excluded"]
    else:
        return gt.get(field_name, False)


# ── CLI ──────────────────────────────────────────────────────────────────────

def run_eval(eval_file: str = "data/eval/liability_eval.json") -> EvalResult:
    """Run extraction on eval set and evaluate."""
    from backend.extraction.extractor import extract_liability

    with open(eval_file) as f:
        eval_data = json.load(f)

    log.info("Running extraction on %d eval examples...", len(eval_data))

    extractions = []
    for item in eval_data:
        text = item["text"]
        if len(text) < 30:
            continue

        ext = extract_liability(text)
        extractions.append({
            "id": item["id"],
            "extracted_data": ext.model_dump() if ext else None,
        })

    result = evaluate_liability(eval_file, extractions)
    return result


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    result = run_eval()
    print(result.summary())
    sys.exit(0 if result.macro_f1 >= 0.75 else 1)
