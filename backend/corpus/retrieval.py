"""
Clause Retrieval
────────────────
Given a query clause (text), retrieve the top-k most similar clause chunks
from the EDGAR corpus using pgvector cosine similarity.

Used by:
  - Phase 3: RAG market benchmarking (retrieve similar real-world clauses)
  - Phase 4: Redline generation (ground edits in market data)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from backend.corpus import db
from backend.corpus.embedder import encode_single

log = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    chunk_id: int
    contract_id: str
    chunk_index: int
    text: str
    section_header: str
    clause_type: str
    similarity: float

    @classmethod
    def from_row(cls, row: dict) -> "RetrievalResult":
        return cls(
            chunk_id=row["id"],
            contract_id=row["contract_id"],
            chunk_index=row["chunk_index"],
            text=row["text"],
            section_header=row.get("section_header", ""),
            clause_type=row.get("clause_type", "other"),
            similarity=row["similarity"],
        )


def retrieve_similar(
    query_text: str,
    top_k: int = 5,
    clause_type: Optional[str] = None,
    min_similarity: float = 0.3,
) -> list[RetrievalResult]:
    """
    Retrieve top-k similar clause chunks for a given query text.

    Args:
        query_text: The clause text to search for similar clauses.
        top_k: Number of results to return.
        clause_type: Optional filter to restrict results to a specific clause type.
        min_similarity: Minimum cosine similarity threshold.

    Returns:
        List of RetrievalResult objects sorted by similarity (descending).
    """
    start = time.monotonic()

    query_embedding = encode_single(query_text)
    rows = db.search_similar_clauses(
        query_embedding=query_embedding,
        match_count=top_k * 2,  # over-fetch then filter
        clause_type=clause_type,
    )

    results = [
        RetrievalResult.from_row(r)
        for r in rows
        if r["similarity"] >= min_similarity
    ][:top_k]

    elapsed = time.monotonic() - start
    log.info(
        "Retrieved %d results for query (%.0f chars) in %.2fs",
        len(results), len(query_text), elapsed,
    )
    return results


def retrieve_for_benchmarking(
    query_text: str,
    clause_type: str,
    top_k: int = 10,
) -> dict:
    """
    Retrieve similar clauses and format for market benchmarking.

    Returns a dict with:
      - results: list of similar clause dicts
      - query_clause_type: the clause type used for filtering
      - count: number of results
    """
    results = retrieve_similar(
        query_text=query_text,
        top_k=top_k,
        clause_type=clause_type,
        min_similarity=0.35,
    )

    return {
        "results": [
            {
                "contract_id": r.contract_id,
                "text": r.text,
                "section_header": r.section_header,
                "clause_type": r.clause_type,
                "similarity": round(r.similarity, 4),
            }
            for r in results
        ],
        "query_clause_type": clause_type,
        "count": len(results),
    }
