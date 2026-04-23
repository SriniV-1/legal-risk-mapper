"""
Test the benchmarking pipeline end-to-end.
Uses a sample liability clause and prints market stats.

Usage:
    python -m scripts.test_benchmark
"""
import json
import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from backend.benchmarking.benchmarker import benchmark_clause

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# Sample liability clause for testing
SAMPLE_CLAUSE = """
LIMITATION OF LIABILITY. IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY
ARISING OUT OF OR RELATED TO THIS AGREEMENT EXCEED THE TOTAL AMOUNTS PAID OR
PAYABLE BY CUSTOMER DURING THE TWELVE (12) MONTH PERIOD IMMEDIATELY PRECEDING
THE EVENT GIVING RISE TO THE CLAIM. IN NO EVENT SHALL EITHER PARTY BE LIABLE
FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR PUNITIVE DAMAGES,
INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, OR USE, WHETHER IN AN
ACTION IN CONTRACT OR TORT, EVEN IF THE OTHER PARTY HAS BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGES. THE FOREGOING LIMITATIONS SHALL NOT APPLY TO
(A) BREACHES OF CONFIDENTIALITY OBLIGATIONS, (B) INDEMNIFICATION OBLIGATIONS,
OR (C) A PARTY'S WILLFUL MISCONDUCT OR GROSS NEGLIGENCE.
"""


def main():
    print("=" * 60)
    print("BENCHMARK PIPELINE TEST")
    print("=" * 60)
    print(f"\nInput clause: {len(SAMPLE_CLAUSE)} chars")
    print("-" * 60)

    result = benchmark_clause(SAMPLE_CLAUSE.strip(), clause_type="liability")

    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"Clause type: {result.clause_type}")
    print(f"Market sample size: {result.sample_size}")
    print(f"Cited examples: {len(result.cited_examples)}")

    if result.user_extraction:
        print(f"\n--- User Clause Extraction ---")
        cap = result.user_extraction.get("liability_cap", {})
        print(f"  has_cap: {cap.get('has_cap')}")
        print(f"  cap_type: {cap.get('cap_type')}")
        print(f"  is_mutual: {result.user_extraction.get('is_mutual')}")
        print(f"  has_carve_outs: {result.user_extraction.get('has_carve_outs')}")
        print(f"  consequential_excluded: {result.user_extraction.get('consequential_damages', {}).get('excluded')}")
        print(f"  has_indemnification: {result.user_extraction.get('has_indemnification')}")

    print(f"\n--- Market Distributions ---")
    for field_name, dist in result.field_distributions.items():
        if dist.total > 0:
            if dist.value_counts:
                print(f"  {field_name}: {dist.value_counts} (n={dist.total})")
            else:
                print(f"  {field_name}: {dist.true_pct:.1f}% true ({dist.true_count}/{dist.total})")

    print(f"\n--- User Percentiles (higher = more common) ---")
    for field_name, pct in result.user_percentiles.items():
        if pct is not None:
            print(f"  {field_name}: {pct:.1f}th percentile")

    print(f"\n--- Top Cited Examples ---")
    for i, ex in enumerate(result.cited_examples):
        print(f"  [{i+1}] {ex.company or ex.contract_id} (sim={ex.similarity:.3f})")
        print(f"      {ex.text_snippet[:100]}...")
        if ex.extracted_data:
            cap = ex.extracted_data.get("liability_cap", {})
            print(f"      has_cap={cap.get('has_cap')}, mutual={ex.extracted_data.get('is_mutual')}")

    print(f"\n{'=' * 60}")

    # Also dump full JSON for inspection
    print("\nFull JSON result:")
    print(json.dumps(result.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    main()
