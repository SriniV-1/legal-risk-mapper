"""
ML Risk Classifier — Inference Wrapper
───────────────────────────────────────
Loads a trained multi-label risk classifier and provides a predict API
that replaces the hardcoded regex rules.

Architecture:
  Input:  clause text → MiniLM-L6-v2 embedding (384-dim)
  Model:  5 independent LogisticRegression classifiers (one per risk category)
  Output: list of (category, severity, confidence) predictions

The classifier was trained on 387 labeled contract clauses
(template-augmented + canonical clauses from the knowledge base).

Graceful degradation:
  If the model file is missing or sklearn is unavailable, classify_clause()
  returns [] and the system falls back to regex rules.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.models import embeddings as emb

logger = logging.getLogger("alrm.classifier")

# ── Config ───────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = _PROJECT_ROOT / "data" / "models" / "risk_classifier.pkl"

# Minimum risk probability to report (1 - P(None)). Filters out noise.
# Tuned to avoid false positives on neutral governing-law clauses.
MIN_CONFIDENCE = 0.55

# ── Singleton state ──────────────────────────────────────────────────────────
_model_bundle: Optional[Dict] = None
_load_attempted = False


def _load_model() -> Optional[Dict]:
    """Load the trained model bundle from disk. Returns None on failure."""
    global _model_bundle, _load_attempted
    if _model_bundle is not None:
        return _model_bundle
    if _load_attempted:
        return None

    _load_attempted = True

    if not MODEL_PATH.exists():
        logger.warning(f"Risk classifier model not found at {MODEL_PATH}")
        return None

    try:
        with open(MODEL_PATH, "rb") as f:
            _model_bundle = pickle.load(f)
        logger.info(
            f"Risk classifier loaded: {len(_model_bundle['categories'])} categories, "
            f"v{_model_bundle.get('version', '?')}"
        )
        return _model_bundle
    except Exception as e:
        logger.error(f"Failed to load risk classifier: {e}")
        return None


def is_available() -> bool:
    """True if the trained classifier can be used."""
    return _load_model() is not None and emb.is_available()


def classify_clause(text: str) -> List[Dict]:
    """
    Classify a single clause for legal risks.

    Returns a list of risk predictions, one per detected risk category:
    [
        {
            "risk_type": "Liability Risk",
            "severity": "High",
            "confidence": 0.87,
            "severity_probs": {"None": 0.05, "Low": 0.03, "Medium": 0.05, "High": 0.87},
        },
        ...
    ]

    Returns [] if the model is unavailable (graceful degradation to regex).
    """
    bundle = _load_model()
    if bundle is None:
        return []

    # Encode the clause
    embedding = emb.encode([text], normalize=True)
    if embedding is None:
        return []

    results = []
    for cat in bundle["categories"]:
        clf = bundle["classifiers"][cat]
        le = bundle["encoders"][cat]

        # Get probability distribution over severity classes
        probs = clf.predict_proba(embedding)[0]
        classes = le.classes_

        # Build probability dict
        prob_dict = {cls: float(prob) for cls, prob in zip(classes, probs)}

        # The "None" class probability = probability of no risk
        none_prob = prob_dict.get("None", 0.0)
        risk_prob = 1.0 - none_prob

        if risk_prob < MIN_CONFIDENCE:
            continue

        # Predicted severity = highest-probability non-None class
        severity_probs = {k: v for k, v in prob_dict.items() if k != "None"}
        if not severity_probs:
            continue

        predicted_severity = max(severity_probs, key=severity_probs.get)
        confidence = severity_probs[predicted_severity]

        results.append({
            "risk_type": cat,
            "severity": predicted_severity,
            "confidence": round(confidence, 3),
            "risk_probability": round(risk_prob, 3),
            "severity_probs": {k: round(v, 3) for k, v in prob_dict.items()},
        })

    return results


def classify_clauses_batch(texts: List[str]) -> List[List[Dict]]:
    """
    Classify multiple clauses in a single batch (more efficient than
    calling classify_clause() in a loop because embeddings are batched).

    Returns a list of results, one per input text.
    """
    bundle = _load_model()
    if bundle is None:
        return [[] for _ in texts]

    if not texts:
        return []

    # Batch encode
    embeddings = emb.encode(texts, normalize=True)
    if embeddings is None:
        return [[] for _ in texts]

    all_results = []
    for i, text in enumerate(texts):
        clause_embedding = embeddings[i:i+1]
        results = []

        for cat in bundle["categories"]:
            clf = bundle["classifiers"][cat]
            le = bundle["encoders"][cat]

            probs = clf.predict_proba(clause_embedding)[0]
            classes = le.classes_
            prob_dict = {cls: float(prob) for cls, prob in zip(classes, probs)}

            none_prob = prob_dict.get("None", 0.0)
            risk_prob = 1.0 - none_prob

            if risk_prob < MIN_CONFIDENCE:
                continue

            severity_probs = {k: v for k, v in prob_dict.items() if k != "None"}
            if not severity_probs:
                continue

            predicted_severity = max(severity_probs, key=severity_probs.get)
            confidence = severity_probs[predicted_severity]

            results.append({
                "risk_type": cat,
                "severity": predicted_severity,
                "confidence": round(confidence, 3),
                "risk_probability": round(risk_prob, 3),
                "severity_probs": {k: round(v, 3) for k, v in prob_dict.items()},
            })

        all_results.append(results)

    return all_results
