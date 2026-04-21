#!/usr/bin/env python3
"""
Test Retrieval Quality
──────────────────────
Runs sample queries against the corpus and reports retrieval quality metrics.
Verifies that retrieval completes in < 2 seconds per query.

Usage:
    python -m scripts.test_retrieval
"""
import sys
import time
import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from backend.corpus.retrieval import retrieve_similar
from backend.corpus.db import get_corpus_stats

# ── Sample queries (representative clauses from each category) ───────────────

SAMPLE_QUERIES = [
    {
        "text": (
            "The aggregate liability of either party under this Agreement shall "
            "not exceed the total fees paid by Customer in the twelve (12) month "
            "period immediately preceding the claim."
        ),
        "expected_type": "liability",
        "description": "Liability cap clause",
    },
    {
        "text": (
            "Either party may terminate this Agreement for convenience upon "
            "ninety (90) days prior written notice to the other party."
        ),
        "expected_type": "termination",
        "description": "Termination for convenience",
    },
    {
        "text": (
            "All intellectual property rights in the Software and any derivative "
            "works thereof shall remain the exclusive property of Provider. "
            "Customer is granted a limited, non-exclusive license to use the "
            "Software during the term."
        ),
        "expected_type": "ip",
        "description": "IP ownership + license grant",
    },
    {
        "text": (
            "Customer shall pay all invoices within thirty (30) days of receipt. "
            "Late payments shall accrue interest at the rate of 1.5% per month "
            "or the maximum rate permitted by law, whichever is less."
        ),
        "expected_type": "payment",
        "description": "Payment terms + late fees",
    },
    {
        "text": (
            "Each party agrees to hold in confidence all Confidential Information "
            "of the other party for a period of five (5) years following disclosure. "
            "The receiving party shall return or destroy all Confidential Information "
            "upon termination."
        ),
        "expected_type": "confidentiality",
        "description": "Confidentiality obligations",
    },
    {
        "text": (
            "This Agreement shall be governed by and construed in accordance with "
            "the laws of the State of Delaware, without regard to its conflicts "
            "of law principles. Any disputes shall be resolved by binding "
            "arbitration in Wilmington, Delaware."
        ),
        "expected_type": "governing_law",
        "description": "Governing law + arbitration",
    },
]


def main():
    print("=" * 70)
    print("CORPUS RETRIEVAL QUALITY TEST")
    print("=" * 70)

    # Show corpus stats
    try:
        stats = get_corpus_stats()
        print(f"\nCorpus: {stats['contracts']} contracts, "
              f"{stats['chunks']} chunks, "
              f"{stats['chunks_with_embeddings']} with embeddings")
        print(f"By type: {stats['chunks_by_type']}")
    except Exception as e:
        print(f"\nWarning: Could not get corpus stats: {e}")

    # Warm up: load model once so first query latency isn't penalized
    print("\nWarming up embedding model...")
    from backend.corpus.embedder import encode_single
    encode_single("warmup")
    print("Model ready.\n")

    print(f"Running {len(SAMPLE_QUERIES)} retrieval queries...\n")

    total_time = 0.0
    type_matches = 0
    all_results = []

    for i, query in enumerate(SAMPLE_QUERIES, 1):
        print(f"--- Query {i}: {query['description']} ---")
        print(f"    Expected type: {query['expected_type']}")

        start = time.monotonic()
        results = retrieve_similar(
            query_text=query["text"],
            top_k=5,
            min_similarity=0.3,
        )
        elapsed = time.monotonic() - start
        total_time += elapsed

        print(f"    Latency: {elapsed:.3f}s {'✓' if elapsed < 2.0 else '✗ SLOW'}")
        print(f"    Results: {len(results)}")

        if results:
            top_type_match = results[0].clause_type == query["expected_type"]
            if top_type_match:
                type_matches += 1
            for j, r in enumerate(results[:3], 1):
                type_flag = "✓" if r.clause_type == query["expected_type"] else "·"
                print(f"      [{j}] sim={r.similarity:.3f} type={r.clause_type} {type_flag}")
                print(f"          {r.text[:120]}...")
        else:
            print("      (no results)")

        all_results.append({
            "query": query,
            "results": results,
            "latency": elapsed,
        })
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    avg_latency = total_time / len(SAMPLE_QUERIES) if SAMPLE_QUERIES else 0
    print(f"  Average latency:    {avg_latency:.3f}s (target: < 2.0s)")
    print(f"  Type match @1:      {type_matches}/{len(SAMPLE_QUERIES)} "
          f"({type_matches/len(SAMPLE_QUERIES)*100:.0f}%)")
    print(f"  All queries < 2s:   {'✓ PASS' if all(r['latency'] < 2.0 for r in all_results) else '✗ FAIL'}")

    # Check acceptance criteria
    passed = (
        avg_latency < 2.0
        and all(r["latency"] < 2.0 for r in all_results)
        and all(len(r["results"]) > 0 for r in all_results)
    )
    print(f"\n  Overall: {'✓ PASS' if passed else '✗ FAIL — see above'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
