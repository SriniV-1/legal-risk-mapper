-- Legal Risk Mapper — Corpus Pipeline Schema
-- Run this in Supabase SQL Editor to set up the corpus tables.
--
-- Prerequisites: pgvector extension must be enabled.
-- In Supabase Dashboard → Database → Extensions → search "vector" → Enable

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Contracts table ─────────────────────────────────────────────────────────
-- One row per downloaded SEC EDGAR contract.
CREATE TABLE IF NOT EXISTS contracts (
    id              TEXT PRIMARY KEY,           -- e.g. "edgar_0001"
    company         TEXT NOT NULL DEFAULT '',
    form_type       TEXT NOT NULL DEFAULT '',
    filed_date      DATE,
    accession       TEXT UNIQUE,                -- SEC accession number
    exhibit_url     TEXT,
    char_count      INTEGER NOT NULL DEFAULT 0,
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contracts_company ON contracts (company);
CREATE INDEX IF NOT EXISTS idx_contracts_filed_date ON contracts (filed_date);

-- ── Clause chunks table ─────────────────────────────────────────────────────
-- One row per clause chunk extracted from a contract.
-- The embedding column stores the 384-dim vector from all-MiniLM-L6-v2.
CREATE TABLE IF NOT EXISTS clause_chunks (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contract_id     TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    section_header  TEXT NOT NULL DEFAULT '',
    clause_type     TEXT NOT NULL DEFAULT 'other',  -- liability, termination, ip, payment, confidentiality, governing_law, other
    char_count      INTEGER NOT NULL DEFAULT 0,
    embedding       vector(384),                     -- all-MiniLM-L6-v2 dimension
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (contract_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_contract ON clause_chunks (contract_id);
CREATE INDEX IF NOT EXISTS idx_chunks_clause_type ON clause_chunks (clause_type);

-- IVFFlat index for approximate nearest neighbor search.
-- Create AFTER loading data for best quality. Re-run with correct list count:
--   lists = max(1, num_rows / 1000)
-- For ~10k chunks, lists=10 is appropriate.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON clause_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

-- ── Structured extractions table (Phase 2+) ─────────────────────────────────
-- Will hold LLM-extracted structured fields per clause chunk.
-- Created now as a placeholder so the schema is complete.
CREATE TABLE IF NOT EXISTS structured_extractions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chunk_id        BIGINT NOT NULL REFERENCES clause_chunks(id) ON DELETE CASCADE,
    contract_id     TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    clause_type     TEXT NOT NULL,
    extracted_data  JSONB NOT NULL DEFAULT '{}',      -- per-category Pydantic schema as JSON
    model_used      TEXT NOT NULL DEFAULT '',          -- e.g. "claude-haiku-3"
    extraction_cost NUMERIC(10, 6) DEFAULT 0,         -- USD
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (chunk_id, clause_type)
);

CREATE INDEX IF NOT EXISTS idx_extractions_contract ON structured_extractions (contract_id);
CREATE INDEX IF NOT EXISTS idx_extractions_type ON structured_extractions (clause_type);

-- ── Retrieval function ──────────────────────────────────────────────────────
-- Postgres function for vector similarity search with clause_type filter.
CREATE OR REPLACE FUNCTION match_clauses(
    query_embedding vector(384),
    match_count     INT DEFAULT 5,
    filter_type     TEXT DEFAULT NULL
)
RETURNS TABLE (
    id              BIGINT,
    contract_id     TEXT,
    chunk_index     INTEGER,
    text            TEXT,
    section_header  TEXT,
    clause_type     TEXT,
    similarity      FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        cc.id,
        cc.contract_id,
        cc.chunk_index,
        cc.text,
        cc.section_header,
        cc.clause_type,
        1 - (cc.embedding <=> query_embedding) AS similarity
    FROM clause_chunks cc
    WHERE cc.embedding IS NOT NULL
      AND (filter_type IS NULL OR cc.clause_type = filter_type)
    ORDER BY cc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
