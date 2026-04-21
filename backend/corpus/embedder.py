"""
Embedding Pipeline
──────────────────
Encodes clause chunks using all-MiniLM-L6-v2 (384-dim) and stores vectors
in Supabase via pgvector.

Uses the same model as the existing semantic_analyzer.py to keep the embedding
space consistent across the whole system (Working Agreement #6).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from backend.corpus.config import EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE, EMBEDDING_DIM
from backend.corpus import db

log = logging.getLogger(__name__)

_model = None


def _get_model():
    """Lazy-load the sentence-transformer model (singleton)."""
    global _model
    if _model is not None:
        return _model

    from sentence_transformers import SentenceTransformer
    log.info("Loading embedding model: %s", EMBEDDING_MODEL)
    _model = SentenceTransformer(EMBEDDING_MODEL)
    log.info("Model loaded. Dimension: %d", _model.get_embedding_dimension())
    return _model


def encode_texts(texts: list[str], batch_size: int = EMBEDDING_BATCH_SIZE) -> np.ndarray:
    """
    Encode a list of texts into normalized embedding vectors.
    Returns an (N, 384) numpy array.
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=True,
    )
    return np.asarray(embeddings, dtype=np.float32)


def encode_single(text: str) -> list[float]:
    """Encode a single text and return as a Python list (for Supabase/JSON)."""
    vec = encode_texts([text])[0]
    return vec.tolist()


# ── Batch embed + store ──────────────────────────────────────────────────────

def embed_and_store_chunks(chunks: list[dict]) -> int:
    """
    Embed a list of chunk dicts (must have 'text' key) and add 'embedding' field.
    Then insert into Supabase.
    Returns number of chunks stored.
    """
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    embeddings = encode_texts(texts)

    for chunk, emb_vec in zip(chunks, embeddings):
        chunk["embedding"] = emb_vec.tolist()

    return db.insert_chunks(chunks)


def backfill_embeddings(batch_size: int = 200) -> int:
    """
    Find chunks in Supabase without embeddings and fill them in.
    Useful for resuming after a partial pipeline run.
    Returns total number of embeddings added.
    """
    total = 0
    while True:
        rows = db.get_chunks_without_embeddings(limit=batch_size)
        if not rows:
            break

        texts = [r["text"] for r in rows]
        embeddings = encode_texts(texts)

        updates = [
            (row["id"], emb.tolist())
            for row, emb in zip(rows, embeddings)
        ]
        count = db.update_chunk_embeddings_batch(updates)
        total += count
        log.info("Backfilled %d embeddings (total: %d)", count, total)

    log.info("Backfill complete: %d embeddings added", total)
    return total
