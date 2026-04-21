"""
Corpus Pipeline Orchestrator
─────────────────────────────
Runs the full scrape → chunk → embed → store pipeline, with resume support.

Steps:
  1. Scrape: Download SaaS MSA contracts from SEC EDGAR
  2. Chunk: Segment each contract into typed clause chunks
  3. Embed + Store: Encode chunks with all-MiniLM-L6-v2, store in Supabase/pgvector

Each step is idempotent — re-running skips already-processed contracts.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from backend.corpus.config import CORPUS_RAW_DIR, EDGAR_TARGET_CONTRACTS
from backend.corpus.edgar_scraper import scrape_contracts
from backend.corpus.chunker import chunk_contract, ClauseChunk
from backend.corpus.embedder import embed_and_store_chunks, backfill_embeddings
from backend.corpus import db

log = logging.getLogger(__name__)


def run_scrape(target: int = EDGAR_TARGET_CONTRACTS) -> list[dict]:
    """Step 1: Download contracts from SEC EDGAR."""
    log.info("═" * 60)
    log.info("STEP 1: Scraping SEC EDGAR for SaaS MSA contracts")
    log.info("═" * 60)
    return scrape_contracts(target=target)


def run_chunk_and_store(
    corpus_dir: Path = CORPUS_RAW_DIR,
    embed: bool = True,
) -> dict:
    """
    Step 2+3: Chunk all downloaded contracts and store (with embeddings) in Supabase.

    Reads the manifest.json from the scraper to find downloaded contracts.
    Skips contracts already in the database.
    """
    log.info("═" * 60)
    log.info("STEP 2-3: Chunking, embedding, and storing in Supabase")
    log.info("═" * 60)

    manifest_path = corpus_dir / "manifest.json"
    if not manifest_path.exists():
        log.error("No manifest.json found in %s — run scrape first", corpus_dir)
        return {"error": "no manifest"}

    manifest = json.loads(manifest_path.read_text())
    log.info("Manifest has %d contracts", len(manifest))

    existing_ids = db.get_contract_ids()
    log.info("Database has %d contracts already", len(existing_ids))

    stats = {
        "contracts_processed": 0,
        "contracts_skipped": 0,
        "total_chunks": 0,
        "chunks_by_type": {},
    }

    for meta in manifest:
        contract_id = meta["contract_id"]
        if contract_id in existing_ids:
            stats["contracts_skipped"] += 1
            continue

        filepath = corpus_dir / meta["filename"]
        if not filepath.exists():
            log.warning("File missing for %s: %s", contract_id, filepath)
            continue

        text = filepath.read_text(encoding="utf-8")
        chunks = chunk_contract(text, contract_id=contract_id)

        chunk_dicts = []
        for c in chunks:
            d = c.to_dict()
            d["clause_type"] = d.pop("estimated_category")
            chunk_dicts.append(d)

        meta["chunk_count"] = len(chunks)
        db.upsert_contract(meta)

        if embed:
            stored = embed_and_store_chunks(chunk_dicts)
        else:
            stored = db.insert_chunks(chunk_dicts)

        stats["contracts_processed"] += 1
        stats["total_chunks"] += stored

        for c in chunks:
            cat = c.estimated_category
            stats["chunks_by_type"][cat] = stats["chunks_by_type"].get(cat, 0) + 1

        if stats["contracts_processed"] % 10 == 0:
            log.info(
                "Progress: %d contracts processed, %d chunks stored",
                stats["contracts_processed"], stats["total_chunks"],
            )

    log.info("Chunk+store complete: %s", stats)
    return stats


def run_full_pipeline(
    target_contracts: int = EDGAR_TARGET_CONTRACTS,
    skip_scrape: bool = False,
) -> dict:
    """
    Run the full corpus pipeline: scrape → chunk → embed → store.

    Args:
        target_contracts: Number of contracts to download.
        skip_scrape: If True, skip scraping and use existing downloaded files.

    Returns:
        Summary dict with stats from each step.
    """
    start = time.monotonic()
    summary = {}

    if not skip_scrape:
        contracts = run_scrape(target=target_contracts)
        summary["scrape"] = {"contracts_downloaded": len(contracts)}
    else:
        log.info("Skipping scrape — using existing files in %s", CORPUS_RAW_DIR)

    chunk_stats = run_chunk_and_store()
    summary["chunk_and_store"] = chunk_stats

    # Backfill any chunks that didn't get embeddings
    backfilled = backfill_embeddings()
    summary["backfill_embeddings"] = backfilled

    # Final stats
    try:
        corpus_stats = db.get_corpus_stats()
        summary["corpus"] = corpus_stats
    except Exception as e:
        log.warning("Could not fetch corpus stats: %s", e)

    elapsed = time.monotonic() - start
    summary["total_time_seconds"] = round(elapsed, 1)

    log.info("═" * 60)
    log.info("PIPELINE COMPLETE in %.1fs", elapsed)
    log.info("Summary: %s", json.dumps(summary, indent=2, default=str))
    log.info("═" * 60)

    return summary
