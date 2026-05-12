"""
Market Benchmarker
──────────────────
Orchestrates the full benchmarking pipeline:
  1. Extract structured data from the user's clause
  2. Retrieve similar clauses from the EDGAR corpus
  3. Look up structured extractions for retrieved clauses
  4. Aggregate market statistics and compute percentiles
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.benchmarking.aggregator import aggregate_market_stats
from backend.benchmarking.schemas import BenchmarkResult
from backend.corpus.retrieval import retrieve_similar
from backend.corpus.db import _get_client
from backend.extraction.extractor import (
    extract_liability, extract_termination, extract_payment,
    extract_confidentiality, extract_ip, extract_governing_law,
)

log = logging.getLogger(__name__)


def _get_extractions_for_chunks(chunk_ids: list[int], clause_type: str) -> dict[int, dict]:
    """Fetch structured extractions for a list of chunk IDs."""
    if not chunk_ids:
        return {}

    client = _get_client()
    resp = (
        client.table("structured_extractions")
        .select("chunk_id, extracted_data")
        .eq("clause_type", clause_type)
        .in_("chunk_id", chunk_ids)
        .execute()
    )

    return {row["chunk_id"]: row["extracted_data"] for row in resp.data}


def _get_contract_metadata(contract_ids: list[str]) -> dict[str, dict]:
    """Fetch contract metadata (company, filed_date, exhibit_url) for citations."""
    if not contract_ids:
        return {}

    client = _get_client()
    resp = (
        client.table("contracts")
        .select("id, company, filed_date, exhibit_url")
        .in_("id", contract_ids)
        .execute()
    )

    return {row["id"]: row for row in resp.data}


def benchmark_clause(
    clause_text: str,
    clause_type: str = "liability",
    top_k: int = 20,
    min_similarity: float = 0.35,
) -> BenchmarkResult:
    """
    Run full market benchmarking pipeline for a user-uploaded clause.

    Args:
        clause_text: The raw clause text from the user's contract.
        clause_type: Category to benchmark (currently only "liability").
        top_k: Number of similar clauses to retrieve for the market sample.
        min_similarity: Minimum cosine similarity threshold for retrieval.

    Returns:
        BenchmarkResult with market stats, user percentiles, and cited examples.
    """
    log.info("Benchmarking %s clause (%d chars)", clause_type, len(clause_text))

    # Step 1: Extract structured data from the user's clause
    _extractors = {
        "liability": extract_liability,
        "termination": extract_termination,
        "payment": extract_payment,
        "confidentiality": extract_confidentiality,
        "ip": extract_ip,
        "governing_law": extract_governing_law,
    }
    user_extraction = None
    extractor_fn = _extractors.get(clause_type)
    if extractor_fn:
        ext = extractor_fn(clause_text)
        if ext:
            user_extraction = ext.model_dump()
            log.info("User clause extraction succeeded")
        else:
            log.warning("User clause extraction failed — benchmarking without user extraction")

    # Step 2: Retrieve similar clauses from EDGAR corpus
    retrieved = retrieve_similar(
        query_text=clause_text,
        top_k=top_k,
        clause_type=clause_type,
        min_similarity=min_similarity,
    )
    log.info("Retrieved %d similar clauses", len(retrieved))

    if not retrieved:
        return BenchmarkResult(
            clause_type=clause_type,
            user_extraction=user_extraction,
            sample_size=0,
        )

    # Step 3: Look up structured extractions for retrieved clauses
    chunk_ids = [r.chunk_id for r in retrieved]
    extractions_by_chunk = _get_extractions_for_chunks(chunk_ids, clause_type)
    log.info(
        "Found extractions for %d/%d retrieved clauses",
        len(extractions_by_chunk), len(retrieved),
    )

    # Step 4: Fetch contract metadata for citations
    contract_ids = list({r.contract_id for r in retrieved})
    contract_meta = _get_contract_metadata(contract_ids)

    # Step 5: Build market extraction list and cited clauses
    market_extractions = []
    cited_clauses = []

    for r in retrieved:
        ext_data = extractions_by_chunk.get(r.chunk_id)
        meta = contract_meta.get(r.contract_id, {})

        cited_clauses.append({
            "contract_id": r.contract_id,
            "company": meta.get("company", ""),
            "filed_date": str(meta.get("filed_date", "")) if meta.get("filed_date") else None,
            "exhibit_url": meta.get("exhibit_url", ""),
            "text": r.text,
            "similarity": r.similarity,
            "extracted_data": ext_data,
        })

        if ext_data:
            market_extractions.append(ext_data)

    # Step 6: Aggregate and return
    result = aggregate_market_stats(
        user_extraction=user_extraction,
        market_extractions=market_extractions,
        cited_clauses=cited_clauses,
        clause_type=clause_type,
    )

    log.info(
        "Benchmark complete: %d market samples, %d cited examples",
        result.sample_size, len(result.cited_examples),
    )
    return result
