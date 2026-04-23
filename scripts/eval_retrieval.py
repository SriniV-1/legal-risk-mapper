"""
Retrieval Eval
──────────────
Computes MRR@5 and NDCG@5 for the liability retrieval pipeline.

Uses eval set clauses as queries and checks whether retrieved results
are relevant (same clause_type, have structured extractions, high similarity).

Usage:
    python -m scripts.eval_retrieval
"""
import json
import logging
import math
import sys
import time

from dotenv import load_dotenv
load_dotenv()

from backend.corpus.retrieval import retrieve_similar
from backend.corpus.db import _get_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _dcg(relevances: list[float], k: int) -> float:
    """Discounted cumulative gain at rank k."""
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        dcg += rel / math.log2(i + 2)  # i+2 because rank starts at 1
    return dcg


def _ndcg(relevances: list[float], k: int) -> float:
    """Normalized DCG at rank k."""
    dcg = _dcg(relevances, k)
    ideal = _dcg(sorted(relevances, reverse=True), k)
    return dcg / ideal if ideal > 0 else 0.0


def main():
    # Load eval examples as queries
    eval_path = "data/eval/liability_eval.json"
    with open(eval_path) as f:
        eval_data = json.load(f)

    log.info("Loaded %d eval examples as retrieval queries", len(eval_data))

    # Warm up embedding model
    from backend.corpus.embedder import encode_single
    encode_single("warmup")

    # Get chunk IDs from our eval set so we can exclude self-matches
    eval_chunk_ids = {e.get("chunk_id") for e in eval_data if e.get("chunk_id")}

    # Get all chunk IDs that have structured extractions (these are higher quality matches)
    client = _get_client()
    ext_resp = client.table("structured_extractions").select("chunk_id").eq(
        "clause_type", "liability"
    ).execute()
    extracted_chunk_ids = {r["chunk_id"] for r in ext_resp.data}
    log.info("Found %d chunks with extractions (higher quality matches)", len(extracted_chunk_ids))

    reciprocal_ranks = []
    ndcg_scores = []
    latencies = []
    type_match_at_1 = 0
    type_match_at_5 = 0

    print(f"\n{'='*60}")
    print("RETRIEVAL EVAL")
    print(f"{'='*60}")
    print(f"Queries: {len(eval_data)} (from eval set)")
    print(f"Corpus extractions available: {len(extracted_chunk_ids)}")
    print()

    for i, item in enumerate(eval_data):
        query_text = item["text"]
        query_id = item.get("chunk_id") or item["id"]

        start = time.monotonic()
        results = retrieve_similar(
            query_text=query_text,
            top_k=5,
            clause_type="liability",  # filter to same type
            min_similarity=0.3,
        )
        elapsed = time.monotonic() - start
        latencies.append(elapsed)

        # Filter out self-match if the query is from the corpus
        results = [r for r in results if r.chunk_id != query_id][:5]

        # Relevance scoring:
        # - 1.0 if same clause_type AND has a structured extraction (verified quality)
        # - 0.7 if same clause_type AND similarity > 0.6 (likely relevant)
        # - 0.3 if same clause_type AND similarity > 0.4
        # - 0.0 otherwise
        relevances = []
        for r in results:
            if r.clause_type == "liability":
                if r.chunk_id in extracted_chunk_ids:
                    relevances.append(1.0)
                elif r.similarity > 0.6:
                    relevances.append(0.7)
                elif r.similarity > 0.4:
                    relevances.append(0.3)
                else:
                    relevances.append(0.0)
            else:
                relevances.append(0.0)

        # MRR: reciprocal rank of first relevant result (relevance >= 0.7)
        rr = 0.0
        for rank, rel in enumerate(relevances, 1):
            if rel >= 0.7:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        # NDCG@5
        ndcg = _ndcg(relevances, 5)
        ndcg_scores.append(ndcg)

        # Type match
        if results and results[0].clause_type == "liability":
            type_match_at_1 += 1
        if any(r.clause_type == "liability" for r in results):
            type_match_at_5 += 1

    # Compute aggregate metrics
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0
    avg_ndcg = sum(ndcg_scores) / len(ndcg_scores) if ndcg_scores else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    print(f"{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"  MRR@5:            {mrr:.3f}  (target: > 0.70)")
    print(f"  NDCG@5:           {avg_ndcg:.3f}  (target: > 0.75)")
    print(f"  Type match @1:    {type_match_at_1}/{len(eval_data)} ({type_match_at_1/len(eval_data):.0%})")
    print(f"  Type match @5:    {type_match_at_5}/{len(eval_data)} ({type_match_at_5/len(eval_data):.0%})")
    print(f"  Avg latency:      {avg_latency:.3f}s")
    print(f"  Max latency:      {max(latencies):.3f}s")
    print(f"{'='*60}")

    mrr_pass = mrr > 0.70
    ndcg_pass = avg_ndcg > 0.75
    print(f"  MRR@5:  {'PASS' if mrr_pass else 'FAIL'} ({mrr:.3f} {'>' if mrr_pass else '<='} 0.70)")
    print(f"  NDCG@5: {'PASS' if ndcg_pass else 'FAIL'} ({avg_ndcg:.3f} {'>' if ndcg_pass else '<='} 0.75)")
    print(f"{'='*60}")

    return 0 if (mrr_pass and ndcg_pass) else 1


if __name__ == "__main__":
    sys.exit(main())
