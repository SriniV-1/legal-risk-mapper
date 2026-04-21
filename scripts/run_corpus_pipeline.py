#!/usr/bin/env python3
"""
Corpus Pipeline CLI
───────────────────
Run the full EDGAR → chunk → embed → Supabase pipeline.

Usage:
    # Full pipeline (scrape + chunk + embed + store)
    python -m scripts.run_corpus_pipeline

    # Skip scraping, just chunk and store existing files
    python -m scripts.run_corpus_pipeline --skip-scrape

    # Custom target count
    python -m scripts.run_corpus_pipeline --target 50

    # Only backfill missing embeddings
    python -m scripts.run_corpus_pipeline --backfill-only

    # Show corpus stats
    python -m scripts.run_corpus_pipeline --stats
"""
import argparse
import json
import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from backend.corpus.pipeline import run_full_pipeline
from backend.corpus.embedder import backfill_embeddings
from backend.corpus.db import get_corpus_stats


def main():
    parser = argparse.ArgumentParser(description="EDGAR Corpus Pipeline")
    parser.add_argument("--target", type=int, default=200, help="Number of contracts to download (default: 200)")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip EDGAR scraping, use existing files")
    parser.add_argument("--backfill-only", action="store_true", help="Only backfill missing embeddings")
    parser.add_argument("--stats", action="store_true", help="Show corpus statistics and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.stats:
        try:
            stats = get_corpus_stats()
            print(json.dumps(stats, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    if args.backfill_only:
        count = backfill_embeddings()
        print(f"Backfilled {count} embeddings")
        return 0

    summary = run_full_pipeline(
        target_contracts=args.target,
        skip_scrape=args.skip_scrape,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
