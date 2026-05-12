"""
Batch extraction of clauses from the EDGAR corpus.
Extracts structured data using Ollama/Llama 3.1 and stores results in Supabase.

Supports resume — skips chunks that already have extractions.
Supports all 6 clause types.

Usage:
    python -m scripts.run_batch_extraction --type liability [--limit N] [--stats]
    python -m scripts.run_batch_extraction --type termination --limit 50
    python -m scripts.run_batch_extraction --type all --limit 100
"""
import argparse
import json
import logging
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from backend.corpus.db import _get_client
from backend.extraction.extractor import (
    extract_liability, extract_termination, extract_payment,
    extract_confidentiality, extract_ip, extract_governing_law,
    DEFAULT_MODEL,
)

log = logging.getLogger(__name__)

_EXTRACTORS = {
    "liability": extract_liability,
    "termination": extract_termination,
    "payment": extract_payment,
    "confidentiality": extract_confidentiality,
    "ip": extract_ip,
    "governing_law": extract_governing_law,
}

ALL_TYPES = list(_EXTRACTORS.keys())


def get_pending_chunks(client, clause_type: str, limit: int = 0):
    """Get chunks that don't yet have extractions for this clause type."""
    existing = client.table("structured_extractions").select("chunk_id").eq(
        "clause_type", clause_type
    ).execute()
    existing_ids = {r["chunk_id"] for r in existing.data}

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
    """Run batch extraction on pending chunks for a single clause type."""
    if clause_type not in _EXTRACTORS:
        print(f"Unknown clause type: {clause_type}. Available: {ALL_TYPES}")
        return

    extractor_fn = _EXTRACTORS[clause_type]
    client = _get_client()
    chunks = get_pending_chunks(client, clause_type, limit)

    if not chunks:
        print(f"No pending {clause_type} chunks to extract.")
        return

    total = len(chunks)
    success = 0
    failed = 0
    start_time = time.monotonic()

    print(f"\nStarting {clause_type} batch extraction: {total} chunks")
    print(f"Model: {DEFAULT_MODEL}")
    print()

    for i, chunk in enumerate(chunks):
        chunk_id = chunk["id"]
        contract_id = chunk["contract_id"]
        text = chunk["text"]

        if len(text) < 30:
            log.debug("Skipping short chunk %d (%d chars)", chunk_id, len(text))
            continue

        extraction = extractor_fn(text)

        if extraction is not None:
            row = {
                "chunk_id": chunk_id,
                "contract_id": contract_id,
                "clause_type": clause_type,
                "extracted_data": extraction.model_dump(),
                "model_used": DEFAULT_MODEL,
                "extraction_cost": 0,
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

        if (i + 1) % 10 == 0 or i == total - 1:
            elapsed = time.monotonic() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta_min = (total - i - 1) / rate / 60 if rate > 0 else 0
            print(
                f"  [{clause_type}] [{i+1}/{total}] {success} ok, {failed} failed "
                f"| {rate:.1f} chunks/s | ETA: {eta_min:.0f}m",
                flush=True,
            )

    elapsed = time.monotonic() - start_time
    print(f"\n{clause_type} batch complete: {success}/{total} extracted in {elapsed/60:.1f}m")
    return success, failed


def run_all(limit: int = 0):
    """Run batch extraction for all clause types sequentially."""
    results = {}
    for clause_type in ALL_TYPES:
        print(f"\n{'='*60}")
        print(f"  {clause_type.upper()}")
        print(f"{'='*60}")
        result = run_batch(limit=limit, clause_type=clause_type)
        if result:
            results[clause_type] = result

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for ct, (s, f) in results.items():
        print(f"  {ct}: {s} extracted, {f} failed")


def show_stats():
    """Show extraction statistics for all clause types."""
    client = _get_client()

    print("Extraction coverage by clause type:")
    print(f"{'Type':<20s} {'Extracted':>10s} {'Total Chunks':>13s} {'Coverage':>10s}")
    print("-" * 55)

    for clause_type in ALL_TYPES:
        r_ext = client.table("structured_extractions").select("id", count="exact").eq(
            "clause_type", clause_type
        ).execute()
        r_chunks = client.table("clause_chunks").select("id", count="exact").eq(
            "clause_type", clause_type
        ).execute()
        extracted = r_ext.count
        total = r_chunks.count
        pct = f"{extracted/total:.1%}" if total > 0 else "N/A"
        print(f"{clause_type:<20s} {extracted:>10d} {total:>13d} {pct:>10s}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch clause extraction")
    parser.add_argument("--type", default="liability",
                        help=f"Clause type to extract ({', '.join(ALL_TYPES)}, or 'all')")
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
    elif args.type == "all":
        run_all(limit=args.limit)
    else:
        run_batch(limit=args.limit, clause_type=args.type)
