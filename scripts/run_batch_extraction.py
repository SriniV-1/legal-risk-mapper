"""
Batch extraction of liability clauses from the EDGAR corpus.
Extracts structured data using Ollama/Llama 3.1 and stores results in Supabase.

Supports resume — skips chunks that already have extractions.

Usage:
    python -m scripts.run_batch_extraction [--limit N] [--stats]
"""
import argparse
import json
import logging
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from backend.corpus.db import _get_client
from backend.extraction.extractor import extract_liability, DEFAULT_MODEL

log = logging.getLogger(__name__)


def get_pending_chunks(client, clause_type: str = "liability", limit: int = 0):
    """Get liability chunks that don't yet have extractions."""
    # Get chunk IDs that already have extractions
    existing = client.table("structured_extractions").select("chunk_id").eq(
        "clause_type", clause_type
    ).execute()
    existing_ids = {r["chunk_id"] for r in existing.data}

    # Get all liability chunks
    query = client.table("clause_chunks").select(
        "id,contract_id,text"
    ).eq("clause_type", clause_type)

    if limit > 0:
        query = query.limit(limit)

    result = query.execute()
    pending = [r for r in result.data if r["id"] not in existing_ids]

    log.info(
        "Found %d %s chunks, %d already extracted, %d pending",
        len(result.data), clause_type, len(existing_ids), len(pending),
    )
    return pending


def run_batch(limit: int = 0, clause_type: str = "liability"):
    """Run batch extraction on pending chunks."""
    client = _get_client()
    chunks = get_pending_chunks(client, clause_type, limit)

    if not chunks:
        print("No pending chunks to extract.")
        return

    total = len(chunks)
    success = 0
    failed = 0
    start_time = time.monotonic()

    for i, chunk in enumerate(chunks):
        chunk_id = chunk["id"]
        contract_id = chunk["contract_id"]
        text = chunk["text"]

        if len(text) < 30:
            log.debug("Skipping short chunk %d (%d chars)", chunk_id, len(text))
            continue

        extraction = extract_liability(text)

        if extraction is not None:
            # Store in Supabase
            row = {
                "chunk_id": chunk_id,
                "contract_id": contract_id,
                "clause_type": clause_type,
                "extracted_data": extraction.model_dump(),
                "model_used": DEFAULT_MODEL,
                "extraction_cost": 0,  # Local model, no cost
            }
            try:
                client.table("structured_extractions").upsert(
                    row, on_conflict="chunk_id,clause_type"
                ).execute()
                success += 1
            except Exception as e:
                log.error("DB insert failed for chunk %d: %s", chunk_id, e)
                failed += 1
        else:
            failed += 1

        # Progress update every 10 items
        if (i + 1) % 10 == 0 or i == total - 1:
            elapsed = time.monotonic() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta_min = (total - i - 1) / rate / 60 if rate > 0 else 0
            print(
                f"  [{i+1}/{total}] {success} ok, {failed} failed "
                f"| {rate:.1f} chunks/s | ETA: {eta_min:.0f}m",
                flush=True,
            )

    elapsed = time.monotonic() - start_time
    print(f"\nBatch complete: {success}/{total} extracted in {elapsed/60:.1f}m")


def show_stats():
    """Show extraction statistics."""
    client = _get_client()

    # Count extractions
    r = client.table("structured_extractions").select("id", count="exact").execute()
    total_extractions = r.count

    # Count by clause type
    r = client.table("structured_extractions").select(
        "clause_type"
    ).execute()
    by_type = {}
    for row in r.data:
        ct = row["clause_type"]
        by_type[ct] = by_type.get(ct, 0) + 1

    # Count pending liability chunks
    r_chunks = client.table("clause_chunks").select("id", count="exact").eq(
        "clause_type", "liability"
    ).execute()
    total_liability = r_chunks.count

    print(f"Total extractions: {total_extractions}")
    print(f"By type: {by_type}")
    print(f"Liability chunks in corpus: {total_liability}")
    print(f"Extraction coverage: {total_extractions}/{total_liability} = {total_extractions/total_liability:.1%}" if total_liability > 0 else "")

    # Sample extraction stats
    if total_extractions > 0:
        r = client.table("structured_extractions").select(
            "extracted_data"
        ).eq("clause_type", "liability").limit(100).execute()

        has_cap = sum(1 for row in r.data if row["extracted_data"].get("liability_cap", {}).get("has_cap"))
        has_indem = sum(1 for row in r.data if row["extracted_data"].get("has_indemnification"))
        has_consq = sum(1 for row in r.data if row["extracted_data"].get("consequential_damages", {}).get("excluded"))

        n = len(r.data)
        print(f"\nSample stats (first {n}):")
        print(f"  has_cap: {has_cap}/{n} ({has_cap/n:.0%})")
        print(f"  has_indemnification: {has_indem}/{n} ({has_indem/n:.0%})")
        print(f"  consequential_excluded: {has_consq}/{n} ({has_consq/n:.0%})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch liability extraction")
    parser.add_argument("--limit", type=int, default=0, help="Max chunks to process (0=all)")
    parser.add_argument("--stats", action="store_true", help="Show extraction stats only")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if args.stats:
        show_stats()
    else:
        run_batch(limit=args.limit)
