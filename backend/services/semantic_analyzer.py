"""
Semantic Risk Analyzer
──────────────────────
Embedding-based risk detection that complements the regex layer.

Pipeline:
  1. Segment input text into clauses (spaCy if available, else regex fallback)
  2. Encode each clause into a 384-dim vector via all-MiniLM-L6-v2
  3. Compare each clause against the precomputed canonical-clause embeddings
  4. For each clause, emit risks for the top-K canonical matches above threshold
     (with de-duplication across risk categories)

Why this catches what regex misses:
  Regex matches exact patterns — "indemnify", "hold harmless", etc.
  Semantic matching catches paraphrases: a clause that says
  "the receiving party agrees to make whole the disclosing party" will
  still flag as Liability Risk even though it contains no regex keywords.

Fallbacks:
  • No spaCy   → uses the regex sentence splitter from text_utils
  • No sentence-transformers → semantic layer returns [] (silent disable)
  In both cases the regex layer still works, so the system degrades gracefully.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional

import numpy as np

from backend.models import embeddings as emb
from backend.services.risk_knowledge_base import (
    CANONICAL_CLAUSES, get_canonical_texts, get_canonical_by_index
)
from backend.utils.text_utils import extract_sentences, clean_text

logger = logging.getLogger("lrm.semantic")

# ── Config: similarity thresholds ─────────────────────────────────────────────
# all-MiniLM-L6-v2 produces cosine sims in roughly [0.1, 0.9] for related text.
# These thresholds were chosen empirically to balance precision/recall.
MIN_SIMILARITY = 0.42   # below this → ignore match entirely
MED_SIMILARITY = 0.55   # above this → full canonical severity
HIGH_SIMILARITY = 0.68  # above this → canonical severity + small score bonus

# Max matches per clause (prevents one clause from generating 40 risks)
TOP_K_PER_CLAUSE = 3

# Minimum clause length (chars). Shorter = probably fragment / noise.
MIN_CLAUSE_CHARS = 20
# Max clause length before we try to sub-split on semicolons
MAX_CLAUSE_CHARS = 400

# Severity order (for downgrade math)
_SEVERITY_ORDER = ["Low", "Medium", "High"]

# Domain-specific canonicals that must NOT fire unless the clause text
# contains at least one of the gate tokens.  Prevents hallucinated
# HIPAA/SOX/PCI warnings on generic compliance clauses.
_DOMAIN_GATES: Dict[str, List[str]] = {
    "COMP_07": ["hipaa", "health insurance", "protected health", "phi"],
    "COMP_04": ["fcpa", "bribery", "corruption", "ofac"],
    "COMP_06": ["export control", "ear", "itar"],
}


def _passes_domain_gate(canonical_id: str, clause_text: str) -> bool:
    gate_tokens = _DOMAIN_GATES.get(canonical_id)
    if gate_tokens is None:
        return True
    text_lower = clause_text.lower()
    return any(tok in text_lower for tok in gate_tokens)


# ── spaCy loader ──────────────────────────────────────────────────────────────
_spacy_nlp = None
_spacy_load_attempted = False


def _get_spacy():
    """
    Lazy-load spaCy.
    Uses en_core_web_sm if available; otherwise falls back to a blank English
    pipeline with only a sentencizer (still better than regex for many cases).
    """
    global _spacy_nlp, _spacy_load_attempted
    if _spacy_nlp is not None:
        return _spacy_nlp
    if _spacy_load_attempted:
        return None

    _spacy_load_attempted = True
    try:
        import spacy
        try:
            _spacy_nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
            logger.info("spaCy loaded: en_core_web_sm")
        except OSError:
            # Model not downloaded — fall back to blank pipeline + sentencizer
            logger.warning(
                "en_core_web_sm not found — using blank English pipeline. "
                "Install with: python -m spacy download en_core_web_sm"
            )
            _spacy_nlp = spacy.blank("en")
            _spacy_nlp.add_pipe("sentencizer")
        return _spacy_nlp
    except ImportError:
        logger.warning("spaCy not installed — falling back to regex sentence splitter")
        return None


# ── Clause segmentation ──────────────────────────────────────────────────────

def segment_clauses(text: str) -> List[str]:
    """
    Split input text into analyzable clauses.

    Strategy:
      1. Use spaCy sentence segmentation if available (handles abbreviations,
         line breaks, and numbered lists better than regex)
      2. Fall back to our regex-based splitter otherwise
      3. Sub-split over-long clauses on semicolons (legal text often has
         very long sentences containing multiple independent obligations)
      4. Drop fragments below MIN_CLAUSE_CHARS
    """
    text = clean_text(text)
    nlp = _get_spacy()

    if nlp is not None:
        try:
            # Long docs: bump max_length if needed (safe, just uses more RAM)
            if len(text) > nlp.max_length:
                nlp.max_length = len(text) + 1000
            doc = nlp(text)
            sents = [s.text.strip() for s in doc.sents if s.text.strip()]
        except Exception as e:
            logger.warning(f"spaCy segmentation failed ({e}); using regex fallback")
            sents = extract_sentences(text)
    else:
        sents = extract_sentences(text)

    # Sub-split long clauses on semicolons
    clauses: List[str] = []
    for s in sents:
        if len(s) > MAX_CLAUSE_CHARS and ";" in s:
            parts = [p.strip() for p in s.split(";") if p.strip()]
            clauses.extend(parts if parts else [s])
        else:
            clauses.append(s)

    # Drop short fragments
    clauses = [c for c in clauses if len(c) >= MIN_CLAUSE_CHARS]
    return clauses


# ── Severity math ─────────────────────────────────────────────────────────────

def _downgrade(severity: str, steps: int) -> str:
    """Move severity down by N steps (e.g. High → Medium → Low). Floor at Low."""
    idx = _SEVERITY_ORDER.index(severity) if severity in _SEVERITY_ORDER else 1
    return _SEVERITY_ORDER[max(0, idx - steps)]


def _severity_from_similarity(canonical_severity: str, similarity: float) -> str:
    """
    Map (canonical severity, similarity score) → detected severity.

    Rationale: a weak semantic match to a High-severity canonical clause is
    still evidence, but we shouldn't report it as High with full confidence.
    """
    if similarity >= HIGH_SIMILARITY:
        return canonical_severity
    if similarity >= MED_SIMILARITY:
        return _downgrade(canonical_severity, 1)
    # MIN_SIMILARITY ≤ sim < MED_SIMILARITY
    return _downgrade(canonical_severity, 2)


# ── Warmup (called at server startup) ─────────────────────────────────────────

_canonical_embeddings: Optional[np.ndarray] = None


def warmup() -> bool:
    """
    Precompute/load canonical embeddings so the first request is fast.
    Called from FastAPI startup event. Safe to call multiple times.
    Returns True if semantic layer is ready; False if disabled.
    """
    global _canonical_embeddings
    if _canonical_embeddings is not None:
        return True

    if not emb.is_available():
        logger.warning("Semantic layer disabled: embedding model unavailable")
        return False

    canonical_texts = get_canonical_texts()
    _canonical_embeddings = emb.load_or_compute_canonical_embeddings(canonical_texts)
    if _canonical_embeddings is None:
        return False

    # Also warm up spaCy (cheap compared to sentence-transformers)
    _get_spacy()
    logger.info(
        f"Semantic layer ready: {len(canonical_texts)} canonical clauses, "
        f"embedding dim={_canonical_embeddings.shape[1]}"
    )
    return True


# ── Main entry: semantic analysis ─────────────────────────────────────────────

def semantic_analyze(clauses: List[str]) -> List[Dict]:
    """
    Run semantic risk detection over a list of clauses.

    Returns a list of risk dicts with the same shape as the regex layer
    plus additional fields:
      • clause_idx           — which clause triggered this risk
      • semantic_similarity  — raw cosine similarity (0..1)
      • semantic_match_id    — id of the canonical clause it matched
      • canonical_rationale  — short reason from the knowledge base
      • sources              — ["semantic"]

    Returns [] if the embedding model is unavailable.
    """
    if not clauses:
        return []

    # Lazy warmup on first call (handles the case where FastAPI startup
    # didn't run, e.g. running the module directly in a test script).
    if _canonical_embeddings is None:
        if not warmup():
            return []

    assert _canonical_embeddings is not None  # for type checker

    # Encode clauses (single batch for efficiency)
    clause_embeddings = emb.encode(clauses, normalize=True)
    if clause_embeddings is None:
        return []

    # Similarity matrix: (n_clauses, n_canonical)
    sim_matrix = emb.cosine_similarity(clause_embeddings, _canonical_embeddings)

    results: List[Dict] = []

    for i, clause in enumerate(clauses):
        # Top-K canonical matches for this clause
        top_indices = np.argsort(sim_matrix[i])[::-1][:TOP_K_PER_CLAUSE]

        # Track categories we've already emitted for this clause to avoid
        # duplicate risks when the top-K are all similar variants of the
        # same risk type.
        seen_categories = set()

        for j in top_indices:
            sim = float(sim_matrix[i, int(j)])
            if sim < MIN_SIMILARITY:
                break  # argsort is descending; subsequent matches are worse

            canonical = get_canonical_by_index(int(j))
            if canonical["category"] in seen_categories:
                continue
            if not _passes_domain_gate(canonical["id"], clause):
                continue
            seen_categories.add(canonical["category"])

            severity = _severity_from_similarity(canonical["severity"], sim)

            # Build a clean snippet from the clause
            snippet = clause if len(clause) <= 280 else clause[:277] + "..."

            # Confidence score: similarity, with a small bonus when the
            # canonical severity is High (reflecting domain importance)
            base_score = sim
            if canonical["severity"] == "High" and sim >= HIGH_SIMILARITY:
                base_score = min(1.0, sim + 0.05)

            results.append({
                "clause_idx": i,
                "risk_type": canonical["category"],
                "severity": severity,
                "text_snippet": snippet,
                # Placeholder; real explanation is generated later in the
                # pipeline using the template engine, which has access to
                # both regex keywords and semantic match info.
                "explanation": canonical["rationale"],
                "score": round(base_score, 3),
                "keywords_matched": list(canonical["keywords"]),
                "sources": ["semantic"],
                "semantic_similarity": round(sim, 3),
                "semantic_match_id": canonical["id"],
                "canonical_rationale": canonical["rationale"],
            })

    return results
