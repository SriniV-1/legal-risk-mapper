"""
Corpus pipeline configuration.

All secrets come from environment variables. Copy .env.example to .env and fill in values.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CORPUS_RAW_DIR = DATA_DIR / "corpus_raw"
CORPUS_RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── EDGAR ────────────────────────────────────────────────────────────────────
EDGAR_USER_AGENT = os.getenv(
    "EDGAR_USER_AGENT",
    "LegalRiskMapper research@example.com",
)
EDGAR_RATE_LIMIT = 10  # requests per second (SEC policy)
EDGAR_EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
EDGAR_TARGET_CONTRACTS = 200

# ── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # service-role key for inserts

# ── Embedding ────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384-dim, already used by semantic layer
EMBEDDING_DIM = 384
EMBEDDING_BATCH_SIZE = 64
