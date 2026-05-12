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
    # Dynamically set per clause type
    CORE_FIELDS = {
        "has_cap", "is_mutual", "has_carve_outs",
        "consequential_excluded", "has_indemnification", "has_warranty_disclaimer",
    }

    TERMINATION_CORE_FIELDS = {
        "has_termination_for_cause", "has_termination_for_convenience",
        "has_cure_period", "has_notice_period", "has_auto_renewal",
        "has_survival_clause", "has_post_termination_obligations", "has_termination_fee",
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


# ── Termination eval ────────────────────────────────────────────────────────

def _get_gt_termination_field(gt: dict, field_name: str) -> bool:
    """Get a ground truth boolean value by field name for termination."""
    if field_name == "has_cure_period":
        return gt.get("cure_period", {}).get("has_cure_period", False)
    elif field_name == "has_notice_period":
        return gt.get("notice_period", {}).get("has_notice_period", False)
    else:
        return gt.get(field_name, False)


def evaluate_termination(
    eval_file: str | Path,
    extractions: list[dict],
) -> EvalResult:
    """
    Evaluate termination extractions against ground truth.

    Args:
        eval_file: Path to eval JSON with ground_truth labels.
        extractions: List of dicts with 'id' and 'extracted_data'.
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
    result.CORE_FIELDS = EvalResult.TERMINATION_CORE_FIELDS

    # Initialize field metrics
    bool_fields = [
        "has_termination_for_cause", "has_termination_for_convenience",
        "has_cure_period", "has_notice_period", "has_auto_renewal",
        "has_survival_clause", "has_post_termination_obligations", "has_termination_fee",
    ]
    cat_fields = ["convenience_termination_who"]
    all_fields = bool_fields + cat_fields

    for f_name in all_fields:
        result.field_metrics[f_name] = FieldMetrics(field_name=f_name)

    success_count = 0
    for gt_item in eval_data:
        item_id = gt_item["id"]
        gt = gt_item["ground_truth"]
        ext_item = ext_by_id.get(item_id)

        if ext_item is None or ext_item.get("extracted_data") is None:
            for f_name in all_fields:
                result.field_metrics[f_name].total += 1
                gt_val = _get_gt_termination_field(gt, f_name) if f_name in bool_fields else (gt.get(f_name) is not None)
                if gt_val:
                    result.field_metrics[f_name].fn += 1
                else:
                    result.field_metrics[f_name].tn += 1
            continue

        success_count += 1
        ext = ext_item["extracted_data"]

        # Boolean fields
        for f_name in bool_fields:
            if f_name == "has_cure_period":
                pred = ext.get("cure_period", {}).get("has_cure_period")
                gt_val = gt.get("cure_period", {}).get("has_cure_period", False)
            elif f_name == "has_notice_period":
                pred = ext.get("notice_period", {}).get("has_notice_period")
                gt_val = gt.get("notice_period", {}).get("has_notice_period", False)
            else:
                pred = ext.get(f_name)
                gt_val = gt.get(f_name, False)

            _compare_bool(pred, gt_val, result.field_metrics[f_name])

        # Categorical
        _compare_categorical(
            ext.get("convenience_termination_who"),
            gt.get("convenience_termination_who"),
            result.field_metrics["convenience_termination_who"],
        )

        # Grounding checks
        clause_text = gt_item["text"]
        for source_field in [
            ext.get("termination_for_cause_source_text"),
            ext.get("termination_for_convenience_source_text"),
            ext.get("cure_period", {}).get("cure_source_text"),
            ext.get("notice_period", {}).get("notice_source_text"),
            ext.get("auto_renewal_source_text"),
            ext.get("survival_source_text"),
            ext.get("post_termination_source_text"),
            ext.get("termination_fee_source_text"),
        ]:
            score = _check_grounding(source_field, clause_text)
            result.grounding_scores.append(score)

    result.extraction_success_rate = success_count / len(eval_data) if eval_data else 0.0
    return result


def run_termination_eval(eval_file: str = "data/eval/termination_eval.json") -> EvalResult:
    """Run termination extraction on eval set and evaluate."""
    from backend.extraction.extractor import extract_termination

    with open(eval_file) as f:
        eval_data = json.load(f)

    log.info("Running termination extraction on %d eval examples...", len(eval_data))

    extractions = []
    for item in eval_data:
        text = item["text"]
        if len(text) < 30:
            continue

        ext = extract_termination(text)
        extractions.append({
            "id": item["id"],
            "extracted_data": ext.model_dump() if ext else None,
        })

    result = evaluate_termination(eval_file, extractions)
    return result


# ── Payment eval ────────────────────────────────────────────────────────────

PAYMENT_CORE_FIELDS = {
    "has_payment_terms", "has_late_fee", "has_price_escalation",
    "has_non_refundable", "has_minimum_commitment",
    "has_dispute_process", "has_right_of_setoff",
}


def _get_gt_payment_field(gt: dict, field_name: str) -> bool:
    """Get a ground truth boolean value by field name for payment."""
    if field_name == "has_late_fee":
        return gt.get("late_fee", {}).get("has_late_fee", False)
    else:
        return gt.get(field_name, False)


def evaluate_payment(
    eval_file: str | Path,
    extractions: list[dict],
) -> EvalResult:
    """Evaluate payment extractions against ground truth."""
    with open(eval_file) as f:
        eval_data = json.load(f)

    ext_by_id = {}
    for e in extractions:
        eid = e.get("id") or e.get("chunk_id")
        if eid:
            ext_by_id[eid] = e

    result = EvalResult(total_examples=len(eval_data))
    result.CORE_FIELDS = PAYMENT_CORE_FIELDS

    bool_fields = [
        "has_payment_terms", "has_late_fee", "has_price_escalation",
        "has_non_refundable", "has_minimum_commitment",
        "has_dispute_process", "has_right_of_setoff",
    ]
    cat_fields = ["invoice_frequency", "late_fee_type"]
    all_fields = bool_fields + cat_fields

    for f_name in all_fields:
        result.field_metrics[f_name] = FieldMetrics(field_name=f_name)

    success_count = 0
    for gt_item in eval_data:
        item_id = gt_item["id"]
        gt = gt_item["ground_truth"]
        ext_item = ext_by_id.get(item_id)

        if ext_item is None or ext_item.get("extracted_data") is None:
            for f_name in all_fields:
                result.field_metrics[f_name].total += 1
                gt_val = _get_gt_payment_field(gt, f_name) if f_name in bool_fields else (gt.get(f_name) is not None)
                if gt_val:
                    result.field_metrics[f_name].fn += 1
                else:
                    result.field_metrics[f_name].tn += 1
            continue

        success_count += 1
        ext = ext_item["extracted_data"]

        for f_name in bool_fields:
            if f_name == "has_late_fee":
                pred = ext.get("late_fee", {}).get("has_late_fee")
                gt_val = gt.get("late_fee", {}).get("has_late_fee", False)
            else:
                pred = ext.get(f_name)
                gt_val = gt.get(f_name, False)
            _compare_bool(pred, gt_val, result.field_metrics[f_name])

        # Categorical
        _compare_categorical(
            ext.get("invoice_frequency"),
            gt.get("invoice_frequency"),
            result.field_metrics["invoice_frequency"],
        )
        _compare_categorical(
            ext.get("late_fee", {}).get("late_fee_type"),
            gt.get("late_fee", {}).get("late_fee_type"),
            result.field_metrics["late_fee_type"],
        )

        # Grounding checks
        clause_text = gt_item["text"]
        for source_field in [
            ext.get("payment_terms_source_text"),
            ext.get("late_fee", {}).get("late_fee_source_text"),
            ext.get("price_escalation_source_text"),
            ext.get("non_refundable_source_text"),
            ext.get("minimum_commitment_source_text"),
            ext.get("invoice_frequency_source_text"),
            ext.get("dispute_process_source_text"),
            ext.get("setoff_source_text"),
        ]:
            score = _check_grounding(source_field, clause_text)
            result.grounding_scores.append(score)

    result.extraction_success_rate = success_count / len(eval_data) if eval_data else 0.0
    return result


def run_payment_eval(eval_file: str = "data/eval/payment_eval.json") -> EvalResult:
    """Run payment extraction on eval set and evaluate."""
    from backend.extraction.extractor import extract_payment

    with open(eval_file) as f:
        eval_data = json.load(f)

    log.info("Running payment extraction on %d eval examples...", len(eval_data))

    extractions = []
    for item in eval_data:
        text = item["text"]
        if len(text) < 30:
            continue

        ext = extract_payment(text)
        extractions.append({
            "id": item["id"],
            "extracted_data": ext.model_dump() if ext else None,
        })

    result = evaluate_payment(eval_file, extractions)
    return result


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

    clause_type = sys.argv[1] if len(sys.argv) > 1 else "liability"

    if clause_type == "termination":
        result = run_termination_eval()
    elif clause_type == "payment":
        result = run_payment_eval()
    else:
        result = run_eval()

    print(result.summary())
    sys.exit(0 if result.macro_f1 >= 0.75 else 1)
