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
import re
from typing import List, Dict, Tuple

from backend.utils.text_utils import (
    clean_text, extract_sentences, get_context_window,
    compute_tfidf_boost, deduplicate_risks
)
from backend.services import semantic_analyzer
from backend.services import risk_classifier
from backend.services.explanation_engine import generate_explanation

logger = logging.getLogger("lrm.analyzer")


# ─────────────────────────────────────────────
#  RISK RULE DEFINITIONS
#  Each rule: (pattern, severity, explanation, corpus_freq)
#  corpus_freq: estimated frequency in general text (used for TF-IDF boost)
# ─────────────────────────────────────────────

RISK_RULES: Dict[str, List[Tuple]] = {

    "Compliance Risk": [
        # (regex_pattern, base_severity, explanation, corpus_freq)
        (r'\b(GDPR|General Data Protection Regulation)\b', "High",
         "Reference to GDPR indicates obligations under EU data protection law. Non-compliance carries fines up to 4% of global turnover.", 0.01),

        (r'\b(HIPAA|Health Insurance Portability)\b', "High",
         "HIPAA reference signals healthcare data obligations. Violations can result in criminal penalties and civil fines.", 0.01),

        (r'\b(CCPA|California Consumer Privacy Act)\b', "High",
         "CCPA imposes consumer data rights obligations for California residents. Non-compliance may trigger regulatory action.", 0.01),

        (r'\b(SOX|Sarbanes.Oxley)\b', "High",
         "SOX reference indicates financial reporting obligations for public companies. Violations may result in criminal liability.", 0.01),

        (r'\b(PCI.DSS|Payment Card Industry)\b', "High",
         "PCI-DSS compliance required for payment card data processing. Non-compliance can result in card processing suspension.", 0.01),

        (r'\bmust comply with\s+(?:all\s+)?(?:applicable\s+)?(?:laws?|regulations?|rules?|requirements?)\b', "High",
         "Broad compliance obligation with unspecified laws creates open-ended legal exposure.", 0.05),

        (r'\bregulatory\s+(?:approval|requirement|compliance|obligation)\b', "Medium",
         "Regulatory requirements mentioned without specificity may create ambiguous obligations.", 0.08),

        # NOTE: Removed generic 'applicable law / governing law' rule — standard
        # governing-law clauses are boilerplate, not a risk, and produced high FP rate.
        # Real ambiguity about jurisdiction is now caught by 'must comply with applicable laws' above.

        (r'\bexport\s+(?:control|restriction|law|regulation|compliance)\b', "High",
         "Export control laws (EAR, ITAR) carry severe penalties including criminal prosecution.", 0.02),

        (r'\b(anti.?bribery|anti.?corruption|FCPA|Bribery Act)\b', "High",
         "Anti-bribery law reference. FCPA and UK Bribery Act violations carry criminal penalties.", 0.01),

        (r'\bsanction[s]?\b(?!\s+(?:from|by|against))', "High",
         "Sanctions compliance (OFAC, EU) is critical — violations can result in severe financial and criminal penalties.", 0.03),

        (r'\bindustry\s+standard[s]?\b', "Low",
         "Vague reference to 'industry standards' may be difficult to enforce or verify objectively.", 0.15),
    ],

    "Liability Risk": [
        (r'\bindemnif(?:y|ied|ication|ies)\b', "High",
         "Indemnification clause requires one party to compensate the other for losses. Scope and caps are critical to review.", 0.02),

        (r'\bhold\s+harmless\b', "High",
         "'Hold harmless' clauses waive rights to sue. Broad versions can eliminate remedies for serious harm.", 0.02),

        (r'\bunlimited\s+liability\b', "High",
         "Unlimited liability exposure creates catastrophic financial risk with no ceiling on damages.", 0.005),

        (r'\bliquidated\s+damages?\b', "High",
         "Liquidated damages clauses pre-set penalty amounts. May be enforceable even if actual harm is lower.", 0.02),

        (r'\blimitation\s+of\s+liability\b', "Medium",
         "Liability cap present — verify the cap amount is adequate and note exclusions from the cap.", 0.05),

        (r'\bexclusiv(?:e|ity)\s+(?:remedy|remedies)\b', "Medium",
         "Exclusive remedy clauses restrict available legal recourse to specific remedies only.", 0.03),

        (r'\bwithout\s+(?:any\s+)?(?:liability|recourse|warranty)\b', "High",
         "Express disclaimer of liability. May eliminate legal recourse for significant harms.", 0.04),

        (r'\bno\s+warrant(?:y|ies|ee)\b|AS.IS\b|without\s+warranty\b', "Medium",
         "As-is warranty disclaimer — no guarantees of fitness or quality. Buyer assumes condition risk.", 0.06),

        (r'\b(?:consequential|incidental|punitive|indirect)\s+damages?\b', "Medium",
         "Damages categories referenced — check whether these are excluded or capped in the agreement.", 0.04),

        (r'\bforce\s+majeure\b', "Medium",
         "Force majeure clause — review triggers and notice requirements. Overly broad clauses can excuse non-performance.", 0.04),

        (r'\bnegligence\b', "Medium",
         "Negligence referenced — determine whether liability for negligence is limited, excluded, or retained.", 0.06),

        (r'\bwarrant(?:y|ies|ee)\b', "Low",
         "Warranty terms present — review scope, duration, and exclusions carefully.", 0.10),
    ],

    "Privacy/Data Risk": [
        (r'\bpersonal(?:ly)?\s+(?:identifiable\s+)?(?:information|data)\b|PII\b', "High",
         "Personal/PII data processing triggers privacy obligations under GDPR, CCPA, and other frameworks.", 0.04),

        (r'\bsell(?:ing|s)?\s+(?:your\s+)?(?:data|information|profile)\b', "High",
         "Explicit sale of user data raises significant privacy concerns and may violate consumer protection laws.", 0.01),

        (r'\bshare\s+(?:your\s+)?(?:data|information)\s+with\s+third.part(?:y|ies)\b', "High",
         "Third-party data sharing requires informed consent under most privacy regulations.", 0.02),

        (r'\bdata\s+breach\b', "High",
         "Data breach reference — verify incident response obligations, notification timelines, and liability caps.", 0.03),

        (r'\bbiometric(?:\s+data)?\b', "High",
         "Biometric data is subject to heightened protection under BIPA (Illinois) and similar state laws.", 0.01),

        (r'\btrack(?:ing|ed|s)?\s+(?:your\s+)?(?:location|activity|behavior|browsing)\b', "High",
         "Behavioral or location tracking may require explicit consent and disclosure under privacy laws.", 0.03),

        (r'\bcollect(?:ing|s|ed)?\s+(?:your\s+)?(?:data|information|cookies)\b', "Medium",
         "Data collection requires purpose limitation and legal basis under privacy regulations.", 0.06),

        (r'\bcookie[s]?\b', "Low",
         "Cookie use requires disclosure and, under GDPR/ePrivacy, informed consent for non-essential cookies.", 0.12),

        (r'\bencrypt(?:ion|ed|s)?\b', "Low",
         "Encryption referenced — verify whether specific standards (AES-256, TLS 1.3) are mandated.", 0.08),

        (r'\bdata\s+retent(?:ion|ion period)\b', "Medium",
         "Data retention policies must align with regulatory minimums and stated collection purposes.", 0.05),

        (r'\bthird.part(?:y|ies)\s+(?:service|provider|partner|vendor)\b', "Medium",
         "Third-party data processor relationships require data processing agreements and due diligence.", 0.06),

        (r'\bopt.out\b', "Low",
         "Opt-out mechanism mentioned — verify it is accessible and effective per regulatory requirements.", 0.08),
    ],

    "Financial Risk": [
        (r'\bautomatic(?:ally)?\s+renew(?:al|s|ed)?\b|auto.renew', "High",
         "Automatic renewal clauses can create unexpected long-term financial commitments without active consent.", 0.02),

        (r'\bearly\s+termination\s+(?:fee|penalty|charge)\b', "High",
         "Early termination fees can impose significant costs. Verify fee calculation method and caps.", 0.02),

        (r'\bpenalt(?:y|ies)\b', "High",
         "Penalty clauses create financial exposure. Distinguish from liquidated damages — some penalties are unenforceable.", 0.05),

        (r'\binterest\s+(?:rate|charges?)\s+of\s+[\d\.]+\s*%', "High",
         "Specific interest rate on unpaid amounts — verify this rate is legally permissible in applicable jurisdiction.", 0.02),

        (r'\bunilateral(?:ly)?\s+(?:change|modify|adjust|increase)\s+(?:price|fee|rate|cost)\b', "High",
         "Unilateral price change rights allow the counterparty to increase costs without negotiation or consent.", 0.02),

        (r'\bnon.refundable\b', "Medium",
         "Non-refundable payments eliminate recourse for service failures. Assess against value and risk.", 0.04),

        (r'\bcancellation\s+(?:fee|charge|penalty)\b', "Medium",
         "Cancellation fees may apply even for non-performance by the other party. Review trigger conditions.", 0.03),

        (r'\bpayment\s+within\s+\d+\s+days?\b|net\s+\d+\b', "Low",
         "Payment terms defined — review for late payment penalties and dispute resolution provisions.", 0.10),

        (r'\bescrow\b', "Low",
         "Escrow arrangements affect cash flow and access to funds. Review release conditions carefully.", 0.05),

        (r'\bmin(?:imum)?\s+(?:purchase|order|commitment|spend)\b', "Medium",
         "Minimum purchase/spend commitments create fixed financial obligations regardless of actual need.", 0.04),

        (r'\bsetoff\b|right\s+of\s+offset\b', "Medium",
         "Setoff rights allow the counterparty to deduct amounts owed to them from payments due to you.", 0.03),

        (r'\bcurrency\s+(?:risk|fluctuation|conversion)\b', "Medium",
         "Foreign currency exposure can cause significant financial losses in cross-border agreements.", 0.03),
    ],

    "Contractual Ambiguity": [
        (r'\bat\s+(?:our|its|their|(?:the\s+)?company\'?s?)\s+(?:sole\s+)?discretion\b', "High",
         "Unilateral discretion clauses give one party unchecked decision-making power without criteria or standards.", 0.03),

        (r'\bmay\s+change\s+(?:at\s+any\s+time|without\s+notice|from\s+time\s+to\s+time)\b', "High",
         "Right to change terms at any time without notice undermines contractual certainty and predictability.", 0.03),

        (r'\bas\s+(?:we\s+)?deem(?:ed)?\s+(?:appropriate|necessary|fit|reasonable)\b', "High",
         "Subjective 'deemed appropriate' standard gives one party broad, unreviewable authority.", 0.02),

        (r'\breasonable\s+(?:efforts?|endeavours?|notice|time)\b', "Medium",
         "'Reasonable' is a subjective standard that creates ambiguity about required performance level.", 0.08),

        (r'\bincluding\s+but\s+not\s+limited\s+to\b|including\s+without\s+limitation\b', "Low",
         "Non-exhaustive lists expand scope unpredictably. May include items not contemplated at signing.", 0.12),

        (r'\bmaterial(?:ly)?\s+(?:adverse|change|breach)\b', "Medium",
         "'Material' is an undefined standard. Disputes about what constitutes materiality are common.", 0.06),

        (r'\bfrom\s+time\s+to\s+time\b', "Low",
         "Vague temporal reference creates uncertainty about when changes or obligations take effect.", 0.10),

        (r'\bsubject\s+to\s+change\b', "Medium",
         "Terms subject to change without clear notice requirements create instability in the agreement.", 0.06),

        (r'\bgood\s+faith\b', "Low",
         "Good faith obligation is context-dependent and may create implied duties not explicitly stated.", 0.09),

        (r'\bin\s+its\s+(?:sole\s+)?(?:and\s+absolute\s+)?discretion\b', "High",
         "Absolute discretion clauses effectively give one party uncapped authority over key decisions.", 0.02),

        (r'\bcustomary\s+(?:terms?|practice|standard)\b', "Medium",
         "Reference to 'customary' terms introduces external, undefined standards into the agreement.", 0.04),

        (r'\bgenerally\s+accepted\b|(?:common|normal|standard)\s+practice\b', "Low",
         "Vague industry practice references may be disputed or difficult to establish objectively.", 0.08),
    ],
}

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


def _find_matches_in_clause(
    clause_text: str, clause_idx: int, rules: List[Tuple], risk_type: str
) -> List[Dict]:
    """
    Apply all regex rules for one risk category against a single clause.
    Returns one risk dict per regex hit, tagged with the clause index so
    later stages can merge with semantic hits on the same clause.
    """
    results = []
    for pattern, base_severity, explanation, corpus_freq in rules:
        for match in re.finditer(pattern, clause_text, re.IGNORECASE):
            matched_text = match.group(0)

            # Use the whole clause as the snippet — it's the natural unit
            # of legal analysis and aligns with the semantic layer's output.
            snippet = clause_text if len(clause_text) <= 300 else clause_text[:297] + "..."

            # TF-IDF boost: frequent-in-clause terms get a confidence bump
            tfidf_boost = compute_tfidf_boost(matched_text, clause_text, corpus_freq)
            base_score = {"Low": 0.45, "Medium": 0.65, "High": 0.85}[base_severity]
            regex_score = min(1.0, base_score + tfidf_boost * 0.15)

            results.append({
                "clause_idx": clause_idx,
                "risk_type": risk_type,
                "severity": base_severity,
                "text_snippet": snippet,
                "explanation": explanation,          # seed; generator overwrites later
                "score": round(regex_score, 3),
                "keywords_matched": [matched_text],
                "sources": ["regex"],
                "_pattern_explanation": explanation,
            })
    return results


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


def analyze_risks(text: str) -> List[Dict]:
    """
    Main HYBRID analysis pipeline.

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
    text = clean_text(text)

    # Step 1: Clause segmentation
    clauses = semantic_analyzer.segment_clauses(text)
    if not clauses:
        return []

    # Step 2: Primary detection — ML classifier (preferred) or regex fallback
    if risk_classifier.is_available():
        logger.info("Using ML classifier for risk detection")
        primary_risks = _classify_clauses_ml(clauses)
    else:
        logger.info("ML classifier unavailable — falling back to regex rules")
        primary_risks: List[Dict] = []
        for idx, clause in enumerate(clauses):
            for risk_type, rules in RISK_RULES.items():
                primary_risks.extend(
                    _find_matches_in_clause(clause, idx, rules, risk_type)
                )

    # Step 3: Semantic scan (may return [] if embeddings unavailable)
    semantic_risks = semantic_analyzer.semantic_analyze(clauses)

    # Step 4: Hybrid merge (works identically whether primary is ML or regex)
    merged = _merge_regex_and_semantic(primary_risks, semantic_risks)

    # Step 5: Snippet-similarity dedup (safety net across clauses)
    merged = deduplicate_risks(merged)

    # Step 6: Cross-category severity escalation (tags `_escalated`)
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
