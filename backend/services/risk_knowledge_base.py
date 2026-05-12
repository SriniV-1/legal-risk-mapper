"""
Canonical Risk Clause Knowledge Base
─────────────────────────────────────
Auto-generated canonical clauses for the semantic similarity layer.

These clauses are loaded from data/models/canonical_clauses.json, which is
produced by the training pipeline (scripts/train_risk_classifier.py). Each
entry is the most representative example for its (category, severity) group,
selected by centroid distance from the training embeddings.

The semantic layer embeds these at startup and uses them as reference points
for cosine similarity matching — providing a "second opinion" alongside the
ML classifier.

No hand-curated entries: everything derives from the trained dataset.

Fields per entry:
  id       — stable identifier for debugging / traceability
  category — one of the 5 risk categories
  severity — High | Medium | Low (base severity; adjusted by similarity)
  text     — the representative clause text (used for embedding)
  keywords — auto-extracted distinctive terms
  rationale — auto-generated one-line explanation of the risk pattern
"""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_CANONICAL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "canonical_clauses.json"

# ── Load canonical clauses ──────────────────────────────────────────────────

CANONICAL_CLAUSES: list[dict] = []


def _load_canonicals() -> list[dict]:
    """Load canonical clauses from the generated JSON file."""
    global CANONICAL_CLAUSES

    if CANONICAL_CLAUSES:
        return CANONICAL_CLAUSES

    if not _CANONICAL_PATH.exists():
        log.warning(
            "Canonical clauses file not found at %s. "
            "Run 'python -m scripts.train_risk_classifier' to generate it. "
            "Semantic layer will be disabled.",
            _CANONICAL_PATH,
        )
        return []

    try:
        with open(_CANONICAL_PATH) as f:
            CANONICAL_CLAUSES = json.load(f)
        log.info("Loaded %d canonical clauses from %s", len(CANONICAL_CLAUSES), _CANONICAL_PATH)
    except (json.JSONDecodeError, IOError) as e:
        log.error("Failed to load canonical clauses: %s", e)
        return []

    return CANONICAL_CLAUSES


# ── Public API (same interface as before) ───────────────────────────────────

def get_canonical_texts() -> list[str]:
    """Return just the text fields — used for embedding."""
    clauses = _load_canonicals()
    return [c["text"] for c in clauses]


def get_canonical_by_index(idx: int) -> dict:
    clauses = _load_canonicals()
    return clauses[idx]


def count_by_category() -> dict:
    """Diagnostic helper."""
    from collections import Counter
    clauses = _load_canonicals()
    return dict(Counter(c["category"] for c in clauses))
