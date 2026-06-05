#!/usr/bin/env python3
"""
Ablation Study — Layer Contribution Analysis
=============================================
Runs the risk analysis pipeline under 7 different layer configurations
and reports how each layer (regex, ML classifier, semantic similarity,
merge) contributes to overall detection quality.

Usage:
    python -m scripts.ablation_study
"""
import sys
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple

# Ensure project root is on sys.path so imports work from any cwd
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.services.risk_analyzer import analyze_risks  # noqa: E402

# ─────────────────────────────────────────────
#  TEST CORPUS — contract snippets with known risks
# ─────────────────────────────────────────────

TEST_SNIPPETS: List[Dict] = [
    {
        "id": "snippet_01",
        "text": (
            "The Client shall indemnify and hold harmless the Company from "
            "any and all claims, damages, and liabilities arising from the "
            "Client's use of the service."
        ),
        "expected_categories": ["Liability Risk"],
    },
    {
        "id": "snippet_02",
        "text": (
            "This agreement automatically renews for successive one-year "
            "terms unless either party provides written notice of "
            "non-renewal at least 90 days prior to expiration. Early "
            "termination fee of $5,000 applies."
        ),
        "expected_categories": ["Financial Risk"],
    },
    {
        "id": "snippet_03",
        "text": (
            "We may share your personal data with third-party advertising "
            "partners for targeted marketing purposes. Your biometric data "
            "may be collected for identity verification."
        ),
        "expected_categories": ["Privacy/Data Risk"],
    },
    {
        "id": "snippet_04",
        "text": (
            "All parties must comply with applicable GDPR regulations and "
            "HIPAA requirements. Export control laws apply to all "
            "cross-border transfers."
        ),
        "expected_categories": ["Compliance Risk"],
    },
    {
        "id": "snippet_05",
        "text": (
            "The Company may change pricing at its sole discretion and "
            "without prior notice. Terms are subject to change from time "
            "to time as we deem appropriate."
        ),
        "expected_categories": ["Contractual Ambiguity", "Financial Risk"],
    },
    {
        "id": "snippet_06",
        "text": (
            "THE SOFTWARE IS PROVIDED AS-IS WITHOUT WARRANTY OF ANY KIND. "
            "IN NO EVENT SHALL THE COMPANY BE LIABLE FOR ANY INDIRECT, "
            "CONSEQUENTIAL, OR INCIDENTAL DAMAGES."
        ),
        "expected_categories": ["Liability Risk"],
    },
    {
        "id": "snippet_07",
        "text": (
            "Vendor shall maintain PCI-DSS compliance for all payment "
            "processing. Anti-bribery and anti-corruption policies must "
            "be followed in accordance with the FCPA."
        ),
        "expected_categories": ["Compliance Risk"],
    },
    {
        "id": "snippet_08",
        "text": (
            "The service provider reserves the right to unilaterally "
            "increase fees. Non-refundable setup charges apply. Minimum "
            "annual purchase commitment of $50,000 is required."
        ),
        "expected_categories": ["Financial Risk"],
    },
    {
        "id": "snippet_09",
        "text": (
            "We collect your browsing activity and location data to "
            "improve services. Data retention period is indefinite. "
            "You may opt-out of tracking via account settings."
        ),
        "expected_categories": ["Privacy/Data Risk"],
    },
    {
        "id": "snippet_10",
        "text": (
            "This contract shall be governed by reasonable efforts and "
            "industry standards. Material adverse changes allow either "
            "party to renegotiate in good faith."
        ),
        "expected_categories": ["Contractual Ambiguity"],
    },
]


# ─────────────────────────────────────────────
#  PIPELINE CONFIGURATIONS (7 ablation combos)
# ─────────────────────────────────────────────

CONFIGURATIONS: List[Tuple[str, List[str]]] = [
    ("regex_only",       ["regex"]),
    ("ml_only",          ["ml"]),
    ("semantic_only",    ["semantic"]),
    ("regex+ml",         ["regex", "ml"]),
    ("regex+semantic",   ["regex", "semantic"]),
    ("ml+semantic",      ["ml", "semantic"]),
    ("all_layers",       ["regex", "ml", "semantic", "merge"]),
]
# Special entry: production mode uses layers=None (ML preferred over regex,
# not both simultaneously).  We run this separately below.
PRODUCTION_CONFIG = ("production", None)


# ─────────────────────────────────────────────
#  ANALYSIS HELPERS
# ─────────────────────────────────────────────

def _run_config(layers) -> List[Dict]:
    """Run all test snippets through one pipeline configuration.

    Args:
        layers: list of layer names, or None for production mode.
    """
    all_risks: List[Dict] = []
    for snippet in TEST_SNIPPETS:
        if layers is None:
            risks = analyze_risks(snippet["text"])
        else:
            risks = analyze_risks(snippet["text"], layers=layers)
        for r in risks:
            r["_snippet_id"] = snippet["id"]
        all_risks.extend(risks)
    return all_risks


def _severity_distribution(risks: List[Dict]) -> Dict[str, int]:
    """Count risks by severity."""
    dist = Counter(r["severity"] for r in risks)
    return {"High": dist.get("High", 0),
            "Medium": dist.get("Medium", 0),
            "Low": dist.get("Low", 0)}


def _category_breakdown(risks: List[Dict]) -> Dict[str, int]:
    """Count risks by category."""
    return dict(Counter(r["risk_type"] for r in risks))


def _detection_recall(risks: List[Dict]) -> float:
    """
    Fraction of expected categories across all snippets that appear
    in detected risks.  A rough recall proxy (we don't have per-clause
    ground-truth labels, so we use expected_categories from the corpus).
    """
    total_expected = 0
    total_found = 0
    for snippet in TEST_SNIPPETS:
        detected_cats = {r["risk_type"] for r in risks
                         if r.get("_snippet_id") == snippet["id"]}
        for cat in snippet["expected_categories"]:
            total_expected += 1
            if cat in detected_cats:
                total_found += 1
    return total_found / total_expected if total_expected else 0.0


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 78)
    print("  ABLATION STUDY — Layer Contribution Analysis")
    print("=" * 78)
    print()

    results: Dict[str, Dict] = {}

    # Run all ablation configurations + the production baseline
    all_configs = list(CONFIGURATIONS) + [PRODUCTION_CONFIG]

    for name, layers in all_configs:
        label = f"layers={layers}" if layers is not None else "layers=None (default)"
        print(f"  Running: {name:20s} ({label}) ...", end=" ", flush=True)
        try:
            risks = _run_config(layers)
            sev = _severity_distribution(risks)
            cats = _category_breakdown(risks)
            recall = _detection_recall(risks)
            results[name] = {
                "layers": layers,
                "total_detections": len(risks),
                "severity": sev,
                "categories": cats,
                "recall": recall,
                "risks": risks,
            }
            print(f"{len(risks):3d} detections, recall={recall:.0%}")
        except Exception as e:
            print(f"ERROR: {e}")
            results[name] = {
                "layers": layers,
                "total_detections": 0,
                "severity": {"High": 0, "Medium": 0, "Low": 0},
                "categories": {},
                "recall": 0.0,
                "risks": [],
                "error": str(e),
            }

    # ── Comparison table ─────────────────────────────────────────────
    print()
    print("-" * 78)
    print(f"{'Configuration':<20s} {'Detections':>10s} {'High':>6s} "
          f"{'Med':>6s} {'Low':>6s} {'Recall':>8s}")
    print("-" * 78)

    for name, data in results.items():
        sev = data["severity"]
        print(f"{name:<20s} {data['total_detections']:>10d} "
              f"{sev['High']:>6d} {sev['Medium']:>6d} {sev['Low']:>6d} "
              f"{data['recall']:>7.0%}")

    print("-" * 78)
    print()

    # ── Per-category breakdown ───────────────────────────────────────
    all_cats = sorted({cat for d in results.values() for cat in d["categories"]})
    if all_cats:
        print(f"{'Configuration':<20s}", end="")
        for cat in all_cats:
            short = cat.replace(" Risk", "").replace("Contractual ", "")[:12]
            print(f" {short:>12s}", end="")
        print()
        print("-" * (20 + 13 * len(all_cats)))

        for name, data in results.items():
            print(f"{name:<20s}", end="")
            for cat in all_cats:
                print(f" {data['categories'].get(cat, 0):>12d}", end="")
            print()
        print()

    # ── Marginal contribution analysis ───────────────────────────────
    print("=" * 78)
    print("  MARGINAL CONTRIBUTION ANALYSIS")
    print("=" * 78)
    print()

    def _marginal(baseline_name: str, enhanced_name: str, added_layer: str):
        b = results.get(baseline_name, {})
        e = results.get(enhanced_name, {})
        b_det = b.get("total_detections", 0)
        e_det = e.get("total_detections", 0)
        b_rec = b.get("recall", 0.0)
        e_rec = e.get("recall", 0.0)
        det_delta = e_det - b_det
        rec_delta = e_rec - b_rec
        det_pct = (det_delta / b_det * 100) if b_det else float("inf")
        rec_pct = rec_delta * 100

        print(f"  Adding {added_layer:<12s} to {baseline_name:<20s} -> {enhanced_name}")
        print(f"    Detections: {b_det:>3d} -> {e_det:>3d}  "
              f"({det_delta:+d}, {det_pct:+.1f}%)")
        print(f"    Recall:     {b_rec:>5.0%} -> {e_rec:>5.0%}  "
              f"({rec_pct:+.1f} pp)")
        print()

    # ML added to regex
    _marginal("regex_only", "regex+ml", "ML")
    # Semantic added to regex
    _marginal("regex_only", "regex+semantic", "semantic")
    # Semantic added to ML
    _marginal("ml_only", "ml+semantic", "semantic")
    # ML added to semantic
    _marginal("semantic_only", "ml+semantic", "ML")
    # Full pipeline vs regex+ml
    # All layers vs regex+ml
    _marginal("regex+ml", "all_layers", "semantic+merge")
    # All layers vs regex+semantic
    _marginal("regex+semantic", "all_layers", "ML+merge")
    # All layers vs ml+semantic
    _marginal("ml+semantic", "all_layers", "regex+merge")

    # ── Summary ──────────────────────────────────────────────────────
    print("=" * 78)
    print("  SUMMARY")
    print("=" * 78)
    print()

    prod = results.get("production", {})
    all_layers = results.get("all_layers", {})
    best_subset_name = ""
    best_subset_recall = -1.0
    for name, data in results.items():
        if name in ("production", "all_layers"):
            continue
        if data.get("recall", 0) > best_subset_recall:
            best_subset_recall = data["recall"]
            best_subset_name = name

    prod_recall = prod.get("recall", 0.0)
    prod_det = prod.get("total_detections", 0)
    all_recall = all_layers.get("recall", 0.0)
    all_det = all_layers.get("total_detections", 0)

    print(f"  Production mode:   {prod_det} detections, {prod_recall:.0%} recall")
    print(f"  All layers mode:   {all_det} detections, {all_recall:.0%} recall")
    print(f"  Best subset:       {best_subset_name} "
          f"({results.get(best_subset_name, {}).get('total_detections', 0)} detections, "
          f"{best_subset_recall:.0%} recall)")
    gap = prod_recall - best_subset_recall
    print(f"  Prod vs best gap:  {gap * 100:+.1f} percentage points recall")
    print()
    if gap > 0:
        print("  Conclusion: The production pipeline outperforms every subset —")
        print("  every layer contributes measurably.")
    elif gap == 0:
        print("  Conclusion: The production pipeline matches but does not exceed the")
        print(f"  best subset ({best_subset_name}). Review whether all layers")
        print("  are needed.")
    else:
        print("  Conclusion: A subset outperforms the production pipeline, suggesting")
        print("  potential for simplification.")
    print()


if __name__ == "__main__":
    main()
