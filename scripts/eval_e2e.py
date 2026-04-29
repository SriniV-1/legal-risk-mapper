"""
End-to-End Pipeline Evaluation
───────────────────────────────
Runs the full benchmark + redline pipeline on multiple test clauses
and reports latency breakdowns, success rates, and quality metrics.

Usage:
    python -m scripts.eval_e2e
"""
import json
import logging
import sys
import time

from dotenv import load_dotenv
load_dotenv()

from backend.benchmarking.benchmarker import benchmark_clause
from backend.redline.generator import generate_redlines

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Diverse test clauses with varying characteristics
TEST_CLAUSES = [
    {
        "id": "strong_mutual",
        "description": "Strong mutual clause with carve-outs",
        "text": """LIMITATION OF LIABILITY. IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY
ARISING OUT OF OR RELATED TO THIS AGREEMENT EXCEED THE TOTAL AMOUNTS PAID OR
PAYABLE BY CUSTOMER DURING THE TWELVE (12) MONTH PERIOD IMMEDIATELY PRECEDING
THE EVENT GIVING RISE TO THE CLAIM. IN NO EVENT SHALL EITHER PARTY BE LIABLE
FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR PUNITIVE DAMAGES.
THE FOREGOING LIMITATIONS SHALL NOT APPLY TO (A) BREACHES OF CONFIDENTIALITY
OBLIGATIONS, (B) INDEMNIFICATION OBLIGATIONS, OR (C) WILLFUL MISCONDUCT.""",
    },
    {
        "id": "weak_onesided",
        "description": "Weak one-sided clause, short cap period",
        "text": """THE AGGREGATE LIABILITY OF PROVIDER ARISING OUT OF OR RELATED TO THIS
AGREEMENT SHALL NOT EXCEED THE FEES PAID BY CUSTOMER IN THE THREE (3) MONTHS
PRECEDING THE CLAIM. PROVIDER SHALL NOT BE LIABLE FOR ANY LOST PROFITS OR
INDIRECT DAMAGES ARISING UNDER THIS AGREEMENT.""",
    },
    {
        "id": "no_cap",
        "description": "Indemnification without cap",
        "text": """Customer shall indemnify, defend and hold harmless Provider and its officers,
directors, employees and agents from and against any and all claims, damages,
losses, liabilities, costs and expenses arising out of or relating to Customer's
use of the Services or any breach of this Agreement by Customer.""",
    },
    {
        "id": "warranty_disclaimer",
        "description": "AS-IS warranty disclaimer",
        "text": """THE SERVICES ARE PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE.""",
    },
    {
        "id": "complex_cap",
        "description": "Complex cap with multiple formulas",
        "text": """Except for Supplier's indemnification obligations under Section 8 and breaches
of confidentiality under Section 7, in no event shall either party's aggregate
liability under this Agreement exceed the greater of (a) $500,000 or (b) two
times the total fees paid by Customer during the twelve (12) month period prior
to the claim. Neither party shall be liable for any indirect, special,
incidental or consequential damages, except in the case of gross negligence or
willful misconduct.""",
    },
    {
        "id": "minimal",
        "description": "Minimal liability language",
        "text": """LIMITATION OF LIABILITY. Company's total liability under this Agreement shall
not exceed the amount of fees paid by Customer during the preceding twelve
months.""",
    },
    {
        "id": "consequential_only",
        "description": "Only consequential damages exclusion",
        "text": """IN NO EVENT SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY CONSEQUENTIAL,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, PUNITIVE OR ENHANCED DAMAGES,
LOST PROFITS OR REVENUES OR DIMINUTION IN VALUE, ARISING OUT OF, OR RELATING
TO, AND/OR IN CONNECTION WITH ANY BREACH OF THIS AGREEMENT, REGARDLESS OF
(A) WHETHER SUCH DAMAGES WERE FORESEEABLE, (B) WHETHER OR NOT THE OTHER PARTY
WAS ADVISED OF THE POSSIBILITY OF SUCH DAMAGES AND (C) THE LEGAL OR EQUITABLE
THEORY UPON WHICH THE CLAIM FOR DAMAGES IS BASED.""",
    },
    {
        "id": "mixed_indemnification",
        "description": "Mixed indemnification and limitation",
        "text": """Each party shall indemnify and hold harmless the other party from any third
party claims arising from the indemnifying party's breach of its representations
and warranties. Notwithstanding the foregoing, neither party's aggregate
liability shall exceed the total fees paid under this Agreement in the prior
twelve months, except that this limitation shall not apply to either party's
indemnification obligations or breaches of confidentiality.""",
    },
]


def main():
    print("=" * 70)
    print("END-TO-END PIPELINE EVALUATION")
    print("=" * 70)
    print(f"Test clauses: {len(TEST_CLAUSES)}")
    print()

    # Warm up models
    print("Warming up models...")
    from backend.corpus.embedder import encode_single
    encode_single("warmup")
    print("Ready.\n")

    results = []
    benchmark_times = []
    redline_times = []
    extraction_successes = 0
    retrieval_counts = []
    suggestion_counts = []

    for i, tc in enumerate(TEST_CLAUSES, 1):
        print(f"--- [{i}/{len(TEST_CLAUSES)}] {tc['description']} ---")

        # Benchmark
        t0 = time.monotonic()
        bench = benchmark_clause(tc["text"].strip(), clause_type="liability")
        t_bench = time.monotonic() - t0
        benchmark_times.append(t_bench)

        # Redline
        t1 = time.monotonic()
        redline = generate_redlines(tc["text"].strip(), bench)
        t_redline = time.monotonic() - t1
        redline_times.append(t_redline)

        total_time = t_bench + t_redline

        if bench.user_extraction:
            extraction_successes += 1
        retrieval_counts.append(bench.sample_size)
        suggestion_counts.append(len(redline.suggestions))

        print(f"  Benchmark: {t_bench:.1f}s | Redline: {t_redline:.1f}s | Total: {total_time:.1f}s")
        print(f"  Market sample: {bench.sample_size} | Suggestions: {len(redline.suggestions)}")

        if bench.user_extraction:
            cap = bench.user_extraction.get("liability_cap", {})
            print(f"  Extracted: cap={cap.get('has_cap')}, mutual={bench.user_extraction.get('is_mutual')}, "
                  f"carve_outs={bench.user_extraction.get('has_carve_outs')}")

        results.append({
            "id": tc["id"],
            "description": tc["description"],
            "benchmark_time": round(t_bench, 2),
            "redline_time": round(t_redline, 2),
            "total_time": round(total_time, 2),
            "extraction_success": bench.user_extraction is not None,
            "market_sample_size": bench.sample_size,
            "num_suggestions": len(redline.suggestions),
            "cited_examples": len(bench.cited_examples),
        })
        print()

    # Summary
    n = len(TEST_CLAUSES)
    avg_bench = sum(benchmark_times) / n
    avg_redline = sum(redline_times) / n
    avg_total = avg_bench + avg_redline
    avg_market = sum(retrieval_counts) / n
    avg_suggestions = sum(suggestion_counts) / n

    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"  Test clauses:           {n}")
    print(f"  Extraction success:     {extraction_successes}/{n} ({extraction_successes/n:.0%})")
    print(f"  Avg market sample:      {avg_market:.1f} clauses")
    print(f"  Avg suggestions:        {avg_suggestions:.1f}")
    print()
    print(f"  --- Latency ---")
    print(f"  Avg benchmark:          {avg_bench:.1f}s")
    print(f"  Avg redline:            {avg_redline:.1f}s")
    print(f"  Avg total (e2e):        {avg_total:.1f}s")
    print(f"  Max total:              {max(r['total_time'] for r in results):.1f}s")
    print(f"  Min total:              {min(r['total_time'] for r in results):.1f}s")
    print()
    print(f"  --- Cost ---")
    print(f"  LLM (Ollama local):     $0.00")
    print(f"  Embeddings (local):     $0.00")
    print(f"  Supabase (free tier):   $0.00")
    print(f"  Total per clause:       $0.00")
    print()
    print(f"  --- With Anthropic Sonnet (estimated) ---")
    print(f"  Extraction (~500 tokens): ~$0.002/clause")
    print(f"  Redline (~1500 tokens):   ~$0.005/clause")
    print(f"  Total per clause:         ~$0.007/clause")
    print("=" * 70)

    # Acceptance check
    all_under_30 = all(r["total_time"] < 30 for r in results)
    print(f"\n  Latency < 30s per clause: {'PASS' if all_under_30 else 'FAIL'}")
    print(f"  Extraction success > 90%: {'PASS' if extraction_successes/n >= 0.9 else 'FAIL'}")
    print("=" * 70)

    # Dump full results
    with open("data/e2e_eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to data/e2e_eval_results.json")


if __name__ == "__main__":
    main()
