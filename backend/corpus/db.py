"""
Supabase Database Client
────────────────────────
Thin wrapper around supabase-py for corpus pipeline CRUD operations.
Uses the service-role key for full insert/update access.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.corpus.config import SUPABASE_URL, SUPABASE_KEY, EMBEDDING_DIM

log = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set. "
            "Copy .env.example to .env and fill in your Supabase credentials."
        )

    from supabase import create_client
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    log.info("Supabase client initialized: %s", SUPABASE_URL)
    return _client


# ── Contracts ────────────────────────────────────────────────────────────────

def upsert_contract(meta: dict) -> None:
    """Insert or update a contract record."""
    row = {
        "id": meta["contract_id"],
        "company": meta.get("company", ""),
        "form_type": meta.get("form_type", ""),
        "filed_date": meta.get("filed_date") or None,
        "accession": meta.get("accession", ""),
        "exhibit_url": meta.get("exhibit_url", ""),
        "char_count": meta.get("char_count", 0),
        "chunk_count": meta.get("chunk_count", 0),
    }
    _get_client().table("contracts").upsert(row).execute()


def get_contract_ids() -> set[str]:
    """Return set of all contract IDs already in the database."""
    resp = _get_client().table("contracts").select("id").execute()
    return {r["id"] for r in resp.data}


# ── Clause Chunks ────────────────────────────────────────────────────────────

def insert_chunks(chunks: list[dict]) -> int:
    """
    Bulk insert clause chunks. Each dict should have:
      contract_id, chunk_index, text, section_header, clause_type, char_count, embedding

    The embedding should be a list of floats (384-dim).
    Returns number of rows inserted.
    """
    if not chunks:
        return 0

    rows = []
    for c in chunks:
        row = {
            "contract_id": c["contract_id"],
            "chunk_index": c["chunk_index"],
            "text": c["text"],
            "section_header": c.get("section_header", ""),
            "clause_type": c.get("clause_type", c.get("estimated_category", "other")),
            "char_count": c.get("char_count", len(c["text"])),
        }
        if c.get("embedding") is not None:
            row["embedding"] = c["embedding"]
        rows.append(row)

    batch_size = 100
    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        _get_client().table("clause_chunks").upsert(
            batch, on_conflict="contract_id,chunk_index"
        ).execute()
        inserted += len(batch)
        if i + batch_size < len(rows):
            log.info("Inserted %d/%d chunks...", inserted, len(rows))

    return inserted


def get_chunks_without_embeddings(limit: int = 500) -> list[dict]:
    """Return chunks that don't have embeddings yet."""
    resp = (
        _get_client()
        .table("clause_chunks")
        .select("id, contract_id, chunk_index, text, clause_type")
        .is_("embedding", "null")
        .limit(limit)
        .execute()
    )
    return resp.data


def update_chunk_embedding(chunk_id: int, embedding: list[float]) -> None:
    """Set the embedding vector for a single chunk."""
    _get_client().table("clause_chunks").update(
        {"embedding": embedding}
    ).eq("id", chunk_id).execute()


def update_chunk_embeddings_batch(updates: list[tuple[int, list[float]]]) -> int:
    """Batch update embeddings. Each tuple is (chunk_id, embedding_vector)."""
    count = 0
    for chunk_id, emb in updates:
        _get_client().table("clause_chunks").update(
            {"embedding": emb}
        ).eq("id", chunk_id).execute()
        count += 1
    return count


# ── Retrieval (vector search) ────────────────────────────────────────────────

def search_similar_clauses(
    query_embedding: list[float],
    match_count: int = 5,
    clause_type: Optional[str] = None,
) -> list[dict]:
    """
    Find the most similar clause chunks using pgvector cosine similarity.
    Uses the match_clauses() Postgres function defined in the migration.
    """
    params = {
        "query_embedding": query_embedding,
        "match_count": match_count,
    }
    if clause_type:
        params["filter_type"] = clause_type

    resp = _get_client().rpc("match_clauses", params).execute()
    return resp.data


# ── Stats ────────────────────────────────────────────────────────────────────

def get_corpus_stats() -> dict:
    """Return summary statistics about the corpus."""
    client = _get_client()

    contracts = client.table("contracts").select("id", count="exact").execute()
    chunks = client.table("clause_chunks").select("id", count="exact").execute()
    embedded = (
        client.table("clause_chunks")
        .select("id", count="exact")
        .not_.is_("embedding", "null")
        .execute()
    )

    type_counts = (
        client.table("clause_chunks")
        .select("clause_type")
        .execute()
    )
    by_type: dict[str, int] = {}
    for row in type_counts.data:
        t = row["clause_type"]
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "contracts": contracts.count,
        "chunks": chunks.count,
        "chunks_with_embeddings": embedded.count,
        "chunks_by_type": by_type,
    }
