"""
Core risk analysis engine — HYBRID pipeline.

Architecture (v3 — fully ML-trained):
  1. spaCy clause segmentation  (backend/services/semantic_analyzer.py)
  2. ML classifier: per-clause multi-label risk classification using
     sentence embeddings + trained LogisticRegression classifiers
     (backend/services/risk_classifier.py)
  3. Per-clause semantic similarity matching against auto-generated
     canonical embeddings (training representatives selected by centroid)
  4. Intelligent merge: ML classifier + semantic hits on the same clause are
     combined into a single, boosted-confidence risk
  5. Severity escalation when multiple categories cluster in one clause
  6. Template-based explanation generation
     (backend/services/explanation_engine.py)

Both the ML classifier AND the semantic layer are fully ML-derived from
the training dataset (617 labeled examples). No hand-curated rules or
knowledge bases. Regex rules are preserved only as a FALLBACK if the
trained model file is unavailable.

Graceful degradation:
  • If ML classifier unavailable → falls back to regex rules
  • If sentence-transformers unavailable → semantic layer returns []
  • If spaCy unavailable → regex sentence splitter fallback
"""
import logging
from typing import List, Dict, Optional, Set, Tuple

from backend.utils.text_utils import clean_text, deduplicate_risks
from backend.services import semantic_analyzer
from backend.services import risk_classifier
from backend.services.explanation_engine import generate_explanation
from backend.services.rules_engine import RISK_RULES, scan as regex_scan

logger = logging.getLogger("lrm.analyzer")

# Valid layer names for the ablation / selective-layer parameter
VALID_LAYERS = {"regex", "ml", "semantic", "merge"}

# Severity escalation: if multiple high-weight matches cluster in a sentence
SEVERITY_ORDER = {"Low": 1, "Medium": 2, "High": 3}
SEVERITY_REVERSE = {1: "Low", 2: "Medium", 3: "High"}

# ─────────────────────────────────────────────
#  UNIFIED SCORING (0–100)
# ─────────────────────────────────────────────
#
# Every detected risk is rescored on a single 0–100 scale at the end of the
# pipeline so that the entire system speaks one scoring language. The mapping
# from score to severity is STRICT and deterministic:
#
#     0–39  → Low
#     40–69 → Medium
#     70–100 → High
#
# The score itself is built from five auditable feature dimensions, each
# contributing up to 100 points. The final score is the weighted sum of the
# features active for a given risk category, rounded to an int. Because every
# number is traceable to a feature and an evidence source, the output is
# explainable ("why is this 82? → liability=90, enforceability=60, etc.").

FEATURE_NAMES = ["liability", "financial", "compliance", "ambiguity", "enforceability"]

# Which features each risk category contributes to, and how much weight.
# Weights per category sum to 1.0 — the weighted sum IS the final score.
CATEGORY_FEATURE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "Liability Risk":        {"liability": 0.75, "enforceability": 0.25},
    "Financial Risk":        {"financial": 0.80, "enforceability": 0.20},
    "Compliance Risk":       {"compliance": 0.85, "enforceability": 0.15},
    "Privacy/Data Risk":     {"compliance": 0.60, "liability": 0.25, "ambiguity": 0.15},
    "Contractual Ambiguity": {"ambiguity": 0.65, "enforceability": 0.35},
}

# Base intensity (0–100) per original rule severity — the starting point for
# that category's primary feature before evidence adjustments.
_BASE_INTENSITY = {"Low": 32, "Medium": 58, "High": 80}


def _score_to_severity(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _finalize_scoring(risk: Dict) -> None:
    """
    Normalize a detected risk to the 0-100 scoring scheme in place.

    Inputs used (all already present on the risk dict at this stage):
      • risk_type         — selects feature weights
      • severity          — seed intensity (Low/Medium/High from detection layer)
      • sources           — ["regex"], ["semantic"], or both
      • semantic_similarity (optional) — raw cosine, 0..1
      • score (old 0..1)  — preserved only as a minor TF-IDF signal
      • _escalated        — bonus when the clause crosses multiple categories

    Outputs written back:
      • score             — int 0..100
      • severity          — derived from score bands
      • feature_scores    — dict of 5 feature sub-scores (0..100)
    """
    category = risk.get("risk_type", "")
    weights = CATEGORY_FEATURE_WEIGHTS.get(category, {"ambiguity": 1.0})

    sources = risk.get("sources") or ["regex"]
    has_regex = "regex" in sources
    has_ml = "ml_classifier" in sources
    has_primary = has_regex or has_ml
    has_semantic = "semantic" in sources
    sim = risk.get("semantic_similarity") or 0.0
    old_score = risk.get("score", 0.0) or 0.0   # 0..1 from detection layer

    # ── Primary feature intensity ─────────────────────────────────────────
    primary = _BASE_INTENSITY.get(risk.get("severity", "Medium"), 55)

    # Agreement bonus: both layers confirm → strong evidence.
    if has_primary and has_semantic:
        primary += 12
    # ML classifier confidence bonus (high-confidence predictions get a bump)
    elif has_ml and not has_semantic:
        ml_conf = risk.get("ml_confidence", 0.5)
        if ml_conf >= 0.75:
            primary += 6
    # Semantic-only penalty when similarity is in the weak band.
    elif has_semantic and not has_primary and sim < 0.58:
        primary -= 12

    # TF-IDF echo (the detection layer already folded a boost into old_score;
    # surface a small residual so it stays traceable).
    primary += int(round(max(0.0, old_score - 0.6) * 10))

    # Cross-category escalation bonus (set earlier by _escalate_cross_category).
    if risk.get("_escalated"):
        primary += 8

    primary = max(0, min(100, primary))

    # ── Secondary features ────────────────────────────────────────────────
    # Non-primary features scale proportionally but are capped so they
    # don't dominate — they exist to give reviewers a decomposition.
    features: Dict[str, int] = {name: 0 for name in FEATURE_NAMES}
    for feat, w in weights.items():
        features[feat] = int(round(primary * (0.6 + 0.4 * w)))  # 60-100% of primary

    # ── Weighted final score ──────────────────────────────────────────────
    final_score = int(round(sum(features[f] * w for f, w in weights.items())))
    final_score = max(0, min(100, final_score))

    risk["score"] = final_score
    risk["severity"] = _score_to_severity(final_score)
    risk["feature_scores"] = features


def _merge_regex_and_semantic(
    primary_risks: List[Dict], semantic_risks: List[Dict]
) -> List[Dict]:
    """
    Intelligent hybrid merge.

    Policy:
      • If a (clause_idx, risk_type) pair has BOTH a primary (ML or regex)
        and a semantic hit → merge into one risk. The merged score is a
        weighted blend plus a +0.08 agreement bonus (capped at 1.0).
        Severity can be escalated from Medium → High on strong agreement.
      • Otherwise, keep each risk as a standalone finding.

    Why this works:
      • Primary layer (ML classifier or regex) gives category precision
      • Semantics gives recall (paraphrased variants, canonical matching)
      • Agreement between the two is stronger evidence than either alone.
    """
    merged: Dict[Tuple[int, str], Dict] = {}

    # Seed with primary risks (ML classifier or regex)
    for r in primary_risks:
        key = (r["clause_idx"], r["risk_type"])
        if key not in merged:
            merged[key] = r
        else:
            # Same category triggered multiple patterns in the clause —
            # accumulate keywords, keep highest score and severity.
            existing = merged[key]
            existing["keywords_matched"].extend(r["keywords_matched"])
            existing["score"] = max(existing["score"], r["score"])
            if SEVERITY_ORDER[r["severity"]] > SEVERITY_ORDER[existing["severity"]]:
                existing["severity"] = r["severity"]

    # Fold semantic risks in
    for s in semantic_risks:
        key = (s["clause_idx"], s["risk_type"])
        if key in merged:
            # ─── HYBRID HIT: both layers agree ───
            existing = merged[key]
            regex_score = existing["score"]
            sem_score = s["score"]

            # Weighted blend + agreement bonus
            blended = 0.55 * regex_score + 0.45 * sem_score + 0.08
            existing["score"] = round(min(1.0, blended), 3)

            # Extend sources and keyword evidence
            if "semantic" not in existing["sources"]:
                existing["sources"].append("semantic")
            existing["semantic_similarity"] = s.get("semantic_similarity")
            existing["semantic_match_id"] = s.get("semantic_match_id")
            existing["canonical_rationale"] = s.get("canonical_rationale")

            # Merge keyword lists (dedupe, preserve order)
            seen = set()
            combined_keywords = []
            for kw in existing["keywords_matched"] + s.get("keywords_matched", []):
                k_low = kw.lower()
                if k_low not in seen:
                    seen.add(k_low)
                    combined_keywords.append(kw)
            existing["keywords_matched"] = combined_keywords

            # Escalate Medium → High on strong semantic agreement
            if (
                existing["severity"] == "Medium"
                and sem_score >= 0.65
            ):
                existing["severity"] = "High"
        else:
            # Semantic-only risk — keep as-is
            merged[key] = s

    return list(merged.values())


def _escalate_cross_category(risks: List[Dict]) -> List[Dict]:
    """
    Escalate severity when a single clause triggers multiple risk categories.
    Co-occurrence is evidence that the clause is multi-dimensionally risky.
    """
    # Group by clause
    clause_groups: Dict[int, List[Dict]] = {}
    for r in risks:
        cid = r.get("clause_idx", -1)
        clause_groups.setdefault(cid, []).append(r)

    for cid, group in clause_groups.items():
        if len(group) < 2:
            continue
        high_count = sum(1 for r in group if r["severity"] == "High")
        distinct_categories = {r["risk_type"] for r in group}

        # If the clause has ≥1 High and ≥2 distinct categories,
        # upgrade any Medium risks on the clause to High.
        if high_count >= 1 and len(distinct_categories) >= 2:
            for r in group:
                if r["severity"] == "Medium":
                    r["severity"] = "High"
                    r["score"] = round(min(1.0, r["score"] + 0.05), 3)
                    # Mark for explanation generator
                    r["_escalated"] = True
    return risks


def _classify_clauses_ml(clauses: List[str]) -> List[Dict]:
    """
    Run the ML classifier over all clauses and convert predictions
    into risk dicts compatible with the merge pipeline.

    Each prediction becomes a risk dict with the same shape as regex results:
      clause_idx, risk_type, severity, text_snippet, score, keywords_matched, sources
    """
    batch_results = risk_classifier.classify_clauses_batch(clauses)

    ml_risks: List[Dict] = []
    for idx, (clause, predictions) in enumerate(zip(clauses, batch_results)):
        for pred in predictions:
            snippet = clause if len(clause) <= 300 else clause[:297] + "..."

            # Map classifier confidence to 0-1 score compatible with the
            # existing merge and scoring pipeline
            base_score = {"Low": 0.45, "Medium": 0.65, "High": 0.85}.get(
                pred["severity"], 0.55
            )
            # Blend base_score with classifier confidence
            score = 0.5 * base_score + 0.5 * pred["confidence"]

            ml_risks.append({
                "clause_idx": idx,
                "risk_type": pred["risk_type"],
                "severity": pred["severity"],
                "text_snippet": snippet,
                "explanation": "",  # filled by explanation engine later
                "score": round(score, 3),
                "keywords_matched": [],  # ML doesn't produce keywords
                "sources": ["ml_classifier"],
                "ml_confidence": pred["confidence"],
                "ml_risk_probability": pred["risk_probability"],
            })

    return ml_risks


def analyze_risks(
    text: str,
    layers: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Main HYBRID analysis pipeline.

    Args:
        text: Contract text to analyze.
        layers: Optional list of pipeline layers to activate.  When ``None``
            (the default) every layer runs — fully backward compatible.
            Valid layer names: ``"regex"``, ``"ml"``, ``"semantic"``, ``"merge"``.
            The ``"merge"`` layer controls hybrid merging + cross-category
            escalation; without it primary and semantic risks are simply
            concatenated.

    Supported configurations (for ablation studies):
        ["regex"]                  — regex only
        ["ml"]                     — ML classifier only
        ["semantic"]               — semantic similarity only
        ["regex", "ml"]            — regex + ML (no semantic)
        ["regex", "semantic"]      — regex + semantic
        ["ml", "semantic"]         — ML + semantic
        ["regex", "ml", "semantic", "merge"]  — full pipeline (default)

    Steps:
      1. Clean input
      2. Segment into clauses (spaCy → regex fallback)
      3. Run ML classifier PER CLAUSE (falls back to regex if unavailable)
      4. Run semantic similarity analysis per clause
      5. Merge ML/regex + semantic hits intelligently
      6. Deduplicate near-identical snippets
      7. Cross-category severity escalation
      8. Generate dynamic explanations from templates
      9. Sort by severity and score

    Returns a list of risk dicts ready for the API response.
    """
    # ── Resolve active layers ────────────────────────────────────────────
    if layers is None:
        active: Set[str] = {"regex", "ml", "semantic", "merge"}
    else:
        unknown = set(layers) - VALID_LAYERS
        if unknown:
            raise ValueError(
                f"Invalid layer(s): {unknown}. Valid layers: {sorted(VALID_LAYERS)}"
            )
        active = set(layers)

    text = clean_text(text)

    # Step 1: Clause segmentation
    clauses = semantic_analyzer.segment_clauses(text)
    if not clauses:
        return []

    # Step 2: Primary detection — selected layers only
    #
    # When `layers` was None (default / production), ML is *preferred*
    # and regex is the fallback — identical to the original pipeline.
    # When `layers` is explicitly provided (ablation mode), each named
    # layer runs independently: ["regex", "ml"] means BOTH run.
    primary_risks: List[Dict] = []
    use_ml = "ml" in active
    use_regex = "regex" in active
    explicit_layers = layers is not None  # ablation mode

    if explicit_layers:
        # Ablation mode: run each requested layer independently
        if use_ml:
            if risk_classifier.is_available():
                logger.info("Using ML classifier for risk detection")
                primary_risks.extend(_classify_clauses_ml(clauses))
            else:
                logger.info("ML classifier unavailable — skipping ML layer")
        if use_regex:
            logger.info("Using regex rules for risk detection")
            primary_risks.extend(regex_scan(clauses))
    else:
        # Production mode: ML preferred, regex as fallback (original behavior)
        if risk_classifier.is_available():
            logger.info("Using ML classifier for risk detection")
            primary_risks.extend(_classify_clauses_ml(clauses))
        else:
            logger.info("ML classifier unavailable — falling back to regex rules")
            primary_risks.extend(regex_scan(clauses))

    # Step 3: Semantic scan (only if layer enabled)
    semantic_risks: List[Dict] = []
    if "semantic" in active:
        semantic_risks = semantic_analyzer.semantic_analyze(clauses)

    # Step 4: Hybrid merge (only when "merge" layer active + both sides present)
    if "merge" in active and primary_risks and semantic_risks:
        merged = _merge_regex_and_semantic(primary_risks, semantic_risks)
    else:
        # No merge — concatenate whatever we have
        merged = primary_risks + semantic_risks

    # Step 5: Snippet-similarity dedup (safety net across clauses)
    merged = deduplicate_risks(merged)

    # Step 6: Cross-category severity escalation (only with merge layer)
    if "merge" in active:
        merged = _escalate_cross_category(merged)

    # Step 7: Finalize unified 0–100 scoring + feature decomposition
    for r in merged:
        _finalize_scoring(r)

    # Step 8: Generate explanations (after scoring so they can reflect the
    # final severity band, and are grounded in the clause text itself).
    for r in merged:
        r["explanation"] = generate_explanation(r)
        # Clean internal fields
        r.pop("_pattern_explanation", None)
        r.pop("_escalated", None)
        # Attach clause_index as a user-facing field (rename private)
        if "clause_idx" in r:
            r["clause_index"] = r.pop("clause_idx")

    # Step 9: Sort (score desc — severity already follows the score bands)
    merged.sort(key=lambda r: -r["score"])
    return merged


def compute_overall_risk(risks: List[Dict]) -> str:
    """
    Determine overall document risk from the distribution of per-risk scores.
    Uses the same 0–100 → band mapping so the whole system is consistent.
    """
    if not risks:
        return "Low"
    # Top-3 average reflects the document's worst-case tone while still
    # damping a single outlier. Pure max was too noisy on short docs.
    top = sorted((r["score"] for r in risks), reverse=True)[:3]
    agg = sum(top) / len(top)
    return _score_to_severity(int(round(agg)))
