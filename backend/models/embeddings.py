"""
Embedding model wrapper.

Responsibilities:
  • Lazy-load sentence-transformers (all-MiniLM-L6-v2 — ~80 MB, 384-dim)
  • Encode text into L2-normalized vectors
  • Cosine similarity helper (dot product on normalized vectors)
  • Disk-level cache for canonical clause embeddings
  • Graceful fallback if sentence-transformers is not installed

Design notes:
  • We keep a SINGLE singleton instance of the model — loading is the
    expensive part (1–3 s cold start); inference is cheap.
  • We cache canonical embeddings by hash(model_name + clause_texts),
    so the cache invalidates automatically when either changes.
  • Nothing in this file references the risk-detection domain — this is
    a generic, reusable embedding layer.
"""
from __future__ import annotations

import hashlib
import logging
import pickle
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger("lrm.embeddings")

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384  # all-MiniLM-L6-v2 output dim

# On-disk cache for canonical clause embeddings
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = _PROJECT_ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "canonical_embeddings.pkl"

# ── Singleton state ───────────────────────────────────────────────────────────
_model = None            # holds the SentenceTransformer instance
_model_load_attempted = False   # prevents repeated failed imports


def get_model():
    """
    Lazy-load the embedding model.
    Returns None (not an exception) if sentence-transformers isn't installed —
    callers MUST handle the None case, which disables semantic analysis.
    """
    global _model, _model_load_attempted
    if _model is not None:
        return _model
    if _model_load_attempted:
        return None  # already failed; don't retry

    _model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
        logger.info(f"Embedding model loaded (dim={EMBED_DIM})")
        return _model
    except ImportError:
        logger.warning(
            "sentence-transformers not installed — semantic layer disabled. "
            "Install with: pip install sentence-transformers"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        return None


def is_available() -> bool:
    """True if the embedding model can be used."""
    return get_model() is not None


def encode(texts: List[str], normalize: bool = True) -> Optional[np.ndarray]:
    """
    Encode a list of texts into embeddings.
    Returns an (n, EMBED_DIM) numpy array, or None if the model is unavailable.

    When normalize=True, each row has unit L2 norm so cosine similarity
    reduces to a plain dot product.
    """
    model = get_model()
    if model is None:
        return None
    if not texts:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=32,
    )

    if normalize:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0   # avoid div-by-zero on empty strings
        embeddings = embeddings / norms

    return embeddings.astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Cosine similarity between two batches of vectors.
    ASSUMES inputs are already L2-normalized (see encode(normalize=True)).

    Shapes:
        a: (m, d)
        b: (n, d)
        returns: (m, n) matrix where [i, j] is similarity of a[i] to b[j]
    """
    return a @ b.T


# ── Canonical embedding cache ─────────────────────────────────────────────────

def _cache_key(texts: List[str]) -> str:
    """Stable hash of (model, canonical texts). Changing either invalidates cache."""
    h = hashlib.sha256()
    h.update(MODEL_NAME.encode("utf-8"))
    for t in texts:
        h.update(b"\x00")
        h.update(t.encode("utf-8"))
    return h.hexdigest()[:16]


def load_or_compute_canonical_embeddings(texts: List[str]) -> Optional[np.ndarray]:
    """
    Return embeddings for a fixed list of canonical clauses, using an
    on-disk cache. On cache miss (or hash mismatch), recomputes and saves.
    """
    key = _cache_key(texts)

    # Try loading cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            if data.get("key") == key and data.get("embeddings") is not None:
                logger.info(f"Loaded {len(texts)} canonical embeddings from cache")
                return data["embeddings"]
            logger.info("Canonical embedding cache is stale — recomputing")
        except Exception as e:
            logger.warning(f"Cache load failed ({e}); recomputing")

    # Compute fresh
    logger.info(f"Computing embeddings for {len(texts)} canonical clauses…")
    embeddings = encode(texts, normalize=True)
    if embeddings is None:
        return None

    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump({"key": key, "embeddings": embeddings}, f)
        logger.info(f"Cached canonical embeddings → {CACHE_FILE.name}")
    except Exception as e:
        logger.warning(f"Cache save failed: {e}")

    return embeddings
