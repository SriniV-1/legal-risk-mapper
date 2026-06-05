"""
ML Classifier vs Regex Comparison Eval
───────────────────────────────────────
Runs the same test documents through both detection paths and compares.

Usage:
    python -m scripts.eval_classifier
"""
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from backend.utils.text_utils import clean_text
from backend.services import semantic_analyzer
from backend.services.risk_analyzer import (
    RISK_RULES, _find_matches_in_clause, _merge_regex_and_semantic,
    _classify_clauses_ml, _escalate_cross_category, _finalize_scoring,
    deduplicate_risks,
)
from backend.services.explanation_engine import generate_explanation
from backend.services import risk_classifier


# ── Test documents ───────────────────────────────────────────────────────────

TEST_DOCS = [
    {
        "id": "multi_risk",
        "description": "Contract with all 5 risk types",
        "text": """
LIMITATION OF LIABILITY. IN NO EVENT SHALL PROVIDER'S AGGREGATE LIABILITY
EXCEED THE FEES PAID IN THE PRECEDING THREE MONTHS. PROVIDER MAKES NO
WARRANTIES OF ANY KIND. THE SERVICES ARE PROVIDED AS-IS.

Customer shall indemnify and hold harmless Provider from all claims arising
from Customer's use of the Services or breach of this Agreement.

We may collect your personal data including browsing behavior and share it
with third-party advertising partners for marketing purposes.

This Agreement automatically renews for successive one-year terms. Early
termination incurs a penalty equal to the remaining contract value.

Provider may modify these terms at any time at its sole discretion
without notice. Continued use constitutes acceptance of modified terms.

Customer must comply with all applicable data protection laws including
GDPR and CCPA in connection with its use of the Services.
""",
        "expected_categories": {
            "Liability Risk", "Privacy/Data Risk", "Financial Risk",
            "Contractual Ambiguity", "Compliance Risk",
        },
    },
    {
        "id": "neutral",
        "description": "Neutral boilerplate — should detect minimal risks",
        "text": """
This Agreement shall be governed by and construed in accordance with the
laws of the State of Delaware. This Agreement constitutes the entire
agreement between the parties. Neither party may assign this Agreement
without the prior written consent of the other party. The headings in
this Agreement are for convenience only.
""",
        "expected_categories": set(),
    },
    {
        "id": "paraphrased",
        "description": "Paraphrased risks — no regex keywords, tests ML generalization",
        "text": """
The receiving party agrees to make the disclosing party whole for any
losses and costs resulting from the receiving party's actions.

The company reserves the right to adjust its practices regarding user
information at any time as it sees fit, without prior consultation.

Fees once remitted cannot be recovered under any circumstances, even
if the engagement concludes ahead of schedule.

Both parties shall observe all statutes, rules, and governmental
directives pertinent to their respective obligations hereunder.
""",
        "expected_categories": {
            "Liability Risk", "Privacy/Data Risk", "Financial Risk",
            "Compliance Risk",
        },
    },
    {
        "id": "privacy_heavy",
        "description": "Privacy-focused document",
        "text": """
We collect your personal information including name, email, IP address,
device identifiers, and browsing behavior. This data may be shared with
affiliated companies and advertising partners. Your data may be
transferred to servers outside your country of residence. We use cookies
and tracking pixels to monitor your activity across the web.
""",
        "expected_categories": {"Privacy/Data Risk"},
    },
]


def _run_pipeline(clauses, primary_risks, semantic_risks):
    """Run the merge + scoring pipeline (shared between ML and regex paths)."""
    merged = _merge_regex_and_semantic(primary_risks, semantic_risks)
    merged = deduplicate_risks(merged)
    merged = _escalate_cross_category(merged)
    for r in merged:
        _finalize_scoring(r)
        r["explanation"] = generate_explanation(r)
        r.pop("_pattern_explanation", None)
        r.pop("_escalated", None)
        if "clause_idx" in r:
            r["clause_index"] = r.pop("clause_idx")
    merged.sort(key=lambda r: -r["score"])
    return merged


def run_comparison():
    """Run both ML and regex paths on all test documents."""
    # Warm up
    semantic_analyzer.warmup()
    risk_classifier.is_available()

    print("=" * 70)
    print("ML CLASSIFIER vs REGEX COMPARISON")
    print("=" * 70)

    results = []

    for doc in TEST_DOCS:
        print(f"\n{'─' * 70}")
        print(f"Test: {doc['description']}")
        print(f"{'─' * 70}")

        text = clean_text(doc["text"])
        clauses = semantic_analyzer.segment_clauses(text)
        semantic_risks = semantic_analyzer.semantic_analyze(clauses)

        # ── ML classifier path ──
        import copy
        t0 = time.monotonic()
        ml_primary = _classify_clauses_ml(clauses)
        ml_risks = _run_pipeline(clauses, ml_primary, copy.deepcopy(semantic_risks))
        ml_time = time.monotonic() - t0

        # ── Regex path ──
        t0 = time.monotonic()
        regex_primary = []
        for idx, clause in enumerate(clauses):
            for risk_type, rules in RISK_RULES.items():
                regex_primary.extend(
                    _find_matches_in_clause(clause, idx, rules, risk_type)
                )
        regex_risks = _run_pipeline(clauses, regex_primary, copy.deepcopy(semantic_risks))
        regex_time = time.monotonic() - t0

        # ── Compare ──
        ml_cats = {r["risk_type"] for r in ml_risks}
        regex_cats = {r["risk_type"] for r in regex_risks}
        expected = doc["expected_categories"]

        ml_hit = ml_cats & expected if expected else set()
        ml_extra = ml_cats - expected if expected else ml_cats
        ml_miss = expected - ml_cats if expected else set()

        regex_hit = regex_cats & expected if expected else set()
        regex_extra = regex_cats - expected if expected else regex_cats
        regex_miss = expected - regex_cats if expected else set()

        print(f"\n  {'':20s} {'ML Classifier':>15s}  {'Regex':>15s}")
        print(f"  {'Risks detected':20s} {len(ml_risks):>15d}  {len(regex_risks):>15d}")
        print(f"  {'Categories hit':20s} {len(ml_cats):>15d}  {len(regex_cats):>15d}")
        print(f"  {'Expected hit':20s} {len(ml_hit):>15d}  {len(regex_hit):>15d}")
        print(f"  {'Missed':20s} {len(ml_miss):>15d}  {len(regex_miss):>15d}")
        print(f"  {'Extra (FP)':20s} {len(ml_extra):>15d}  {len(regex_extra):>15d}")
        print(f"  {'Latency':20s} {ml_time*1000:>12.0f} ms  {regex_time*1000:>12.0f} ms")

        if ml_miss:
            print(f"  ML missed: {ml_miss}")
        if regex_miss:
            print(f"  Regex missed: {regex_miss}")

        # Category-level detail
        all_cats = ml_cats | regex_cats
        if all_cats:
            print(f"\n  Category detail:")
            for cat in sorted(all_cats):
                ml_count = sum(1 for r in ml_risks if r["risk_type"] == cat)
                regex_count = sum(1 for r in regex_risks if r["risk_type"] == cat)
                in_expected = "✓" if cat in expected else "✗"
                print(f"    {in_expected} {cat:25s}  ML={ml_count}  Regex={regex_count}")

        results.append({
            "id": doc["id"],
            "ml_total": len(ml_risks),
            "regex_total": len(regex_risks),
            "ml_categories": len(ml_cats),
            "regex_categories": len(regex_cats),
            "ml_expected_hit": len(ml_hit),
            "regex_expected_hit": len(regex_hit),
            "ml_missed": len(ml_miss),
            "regex_missed": len(regex_miss),
            "ml_extra": len(ml_extra),
            "regex_extra": len(regex_extra),
            "ml_time_ms": round(ml_time * 1000),
            "regex_time_ms": round(regex_time * 1000),
        })

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")

    total_ml_hit = sum(r["ml_expected_hit"] for r in results)
    total_regex_hit = sum(r["regex_expected_hit"] for r in results)
    total_ml_miss = sum(r["ml_missed"] for r in results)
    total_regex_miss = sum(r["regex_missed"] for r in results)
    total_ml_extra = sum(r["ml_extra"] for r in results)
    total_regex_extra = sum(r["regex_extra"] for r in results)
    total_expected = sum(len(d["expected_categories"]) for d in TEST_DOCS)

    ml_recall = total_ml_hit / total_expected if total_expected else 0
    regex_recall = total_regex_hit / total_expected if total_expected else 0

    print(f"  Category recall:     ML={ml_recall:.0%}  Regex={regex_recall:.0%}")
    print(f"  Categories missed:   ML={total_ml_miss}  Regex={total_regex_miss}")
    print(f"  Extra categories:    ML={total_ml_extra}  Regex={total_regex_extra}")
    print(f"  Avg ML latency:      {sum(r['ml_time_ms'] for r in results) / len(results):.0f} ms")
    print(f"  Avg regex latency:   {sum(r['regex_time_ms'] for r in results) / len(results):.0f} ms")

    # ── Calibration metrics ──
    calibration_path = Path(__file__).resolve().parent.parent / "data" / "models" / "calibration_data.json"
    if calibration_path.exists():
        print(f"\n{'─' * 70}")
        print("CALIBRATION METRICS (from training)")
        print(f"{'─' * 70}")
        with open(calibration_path) as f:
            cal_data = json.load(f)

        for key in sorted(cal_data.keys()):
            entry = cal_data[key]
            ece = entry.get("ece", "N/A")
            print(f"  {key:30s}  ECE = {ece}")

        # Reliability diagram data (per-bucket)
        if "overall" in cal_data and "buckets" in cal_data["overall"]:
            print(f"\n  Reliability diagram (overall):")
            print(f"  {'Bin':>10s}  {'Count':>6s}  {'Avg Conf':>9s}  {'Avg Acc':>8s}  {'Gap':>6s}")
            for b in cal_data["overall"]["buckets"]:
                if b["count"] > 0:
                    print(f"  {b['bin']:>10s}  {b['count']:>6d}  {b['avg_confidence']:>9.4f}  {b['avg_accuracy']:>8.4f}  {b['gap']:>6.4f}")
    else:
        print("\n  Calibration data not found. Run training to generate.")

    # Save results
    out_path = Path(__file__).resolve().parent.parent / "data" / "classifier_eval.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    run_comparison()
