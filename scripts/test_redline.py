"""
Test the redline generation pipeline end-to-end.
Runs: clause → benchmark → redline suggestions.

Usage:
    python -m scripts.test_redline
"""
import json
import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from backend.benchmarking.benchmarker import benchmark_clause
from backend.redline.generator import generate_redlines

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# A clause that's missing some market-standard protections
# (no mutual cap, no carve-outs, weak consequential damages language)
SAMPLE_CLAUSE = """
LIMITATION OF LIABILITY. THE AGGREGATE LIABILITY OF PROVIDER ARISING OUT OF
OR RELATED TO THIS AGREEMENT SHALL NOT EXCEED THE FEES PAID BY CUSTOMER IN
THE THREE (3) MONTHS PRECEDING THE CLAIM. PROVIDER SHALL NOT BE LIABLE FOR
ANY LOST PROFITS OR INDIRECT DAMAGES ARISING UNDER THIS AGREEMENT.
"""


def main():
    print("=" * 60)
    print("REDLINE GENERATION TEST")
    print("=" * 60)
    print(f"\nInput clause ({len(SAMPLE_CLAUSE.strip())} chars):")
    print(f"  {SAMPLE_CLAUSE.strip()[:200]}...")
    print()

    # Step 1: Benchmark
    print("Step 1: Running market benchmark...")
    benchmark = benchmark_clause(SAMPLE_CLAUSE.strip(), clause_type="liability")
    print(f"  Market sample: {benchmark.sample_size} clauses")
    print(f"  Cited examples: {len(benchmark.cited_examples)}")

    if benchmark.user_extraction:
        cap = benchmark.user_extraction.get("liability_cap", {})
        print(f"  User has_cap: {cap.get('has_cap')}")
        print(f"  User is_mutual: {benchmark.user_extraction.get('is_mutual')}")
        print(f"  User has_carve_outs: {benchmark.user_extraction.get('has_carve_outs')}")
        print(f"  User consequential_excluded: {benchmark.user_extraction.get('consequential_damages', {}).get('excluded')}")

    # Step 2: Generate redlines
    print("\nStep 2: Generating redline suggestions...")
    result = generate_redlines(SAMPLE_CLAUSE.strip(), benchmark)

    print(f"\n{'=' * 60}")
    print("REDLINE RESULTS")
    print(f"{'=' * 60}")
    print(f"Model: {result.model_used}")
    print(f"Suggestions: {len(result.suggestions)}")
    print(f"Summary: {result.summary}")

    for i, s in enumerate(result.suggestions, 1):
        print(f"\n--- Suggestion {i} [{s.priority.upper()}] ---")
        print(f"  Risk: {s.risk_addressed}")
        print(f"  Original: \"{s.original_text[:100]}{'...' if len(s.original_text) > 100 else ''}\"")
        print(f"  Proposed: \"{s.proposed_text[:100]}{'...' if len(s.proposed_text) > 100 else ''}\"")
        print(f"  Justification: {s.justification}")
        print(f"  Market citation: {s.market_citation}")

    print(f"\n{'=' * 60}")

    # Full JSON
    print("\nFull JSON:")
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
