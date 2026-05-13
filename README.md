# Legal Risk Mapper

![CI](https://github.com/SriniV-1/legal-risk-mapper/actions/workflows/ci.yml/badge.svg)

A contract analysis platform that performs **ML-based risk classification**, **structured clause extraction** across 6 clause categories, **RAG-based market benchmarking** against real SEC EDGAR filings, and **grounded redline generation** for SaaS Master Service Agreements. Built as a portfolio project demonstrating production-quality legal AI engineering.

---

## What It Does

1. **ML Risk Classification** — Classifies contract clauses across 5 risk categories (Compliance, Liability, Privacy/Data, Financial, Contractual Ambiguity) using trained sentence-embedding classifiers with 0.965 average detection F1.

2. **Structured Extraction (6 categories)** — Extracts structured fields from liability, termination, payment, confidentiality, IP, and governing law clauses using LLM-based extraction with source text provenance for every field.

3. **Market Benchmarking** — Retrieves similar clauses from a corpus of 116 real SEC EDGAR contracts using pgvector similarity search, then computes field-level market distributions and percentile ranks.

4. **Grounded Redlines** — Generates contract edit suggestions where every recommendation cites specific market statistics and real SEC filings, not LLM opinion.

---

## Architecture

```
User Clause (text)
    |
    +---> ML Risk Classifier (MiniLM-L6-v2 + LogisticRegression)
    |         -> 5 risk categories with severity scores
    |
    +---> LLM Extraction (Ollama/Llama 3.1 8B)
    |         -> Pydantic schema with source_text grounding
    |         -> 6 clause types: liability, termination, payment,
    |            confidentiality, IP, governing law
    |
    +---> pgvector Retrieval (all-MiniLM-L6-v2, 384-dim)
    |         -> Top-20 similar clauses from EDGAR corpus
    |         -> Join with structured_extractions table
    |
    +---> Market Aggregation
    |         -> Field distributions per clause type
    |         -> User percentile ranking
    |         -> 5 cited examples with SEC filing links
    |
    +---> Redline Generation (LLM + market context)
              -> Original -> Proposed diffs
              -> Each cites market stats + real filings
```

---

## Extraction Metrics

Each clause category has a dedicated Pydantic schema, LLM extraction prompt with critical rules, and a hand-labeled eval dataset (35 examples each). All extractors use Llama 3.1 8B running locally via Ollama.

| Clause Category | Core F1 | Success Rate | Grounding | Eval Examples | Core Fields |
|----------------|---------|-------------|-----------|--------------|-------------|
| **Governing Law** | **0.971** | 100% | 1.000 | 35 | 6 booleans |
| **Payment** | **0.941** | 100% | 1.000 | 35 | 7 booleans |
| **IP** | **0.921** | 100% | 0.996 | 35 | 9 booleans |
| **Confidentiality** | **0.920** | 100% | 0.953 | 35 | 8 booleans |
| **Termination** | **0.881** | 94.3% | 0.973 | 35 | 8 booleans |
| **Liability** | **0.762** | 97.6% | 0.975 | 42 | 6 booleans |

### Per-Field Breakdown: Payment (F1=0.941)

| Field | F1 | Notes |
|-------|-----|-------|
| has_dispute_process | 1.000 | Perfect |
| has_late_fee | 1.000 | Perfect |
| has_minimum_commitment | 1.000 | Perfect |
| has_price_escalation | 1.000 | Perfect |
| has_non_refundable | 0.923 | |
| has_payment_terms | 0.903 | |
| has_right_of_setoff | 0.762 | Rare clause |

### Per-Field Breakdown: IP (F1=0.921)

| Field | F1 | Notes |
|-------|-----|-------|
| has_ip_assignment | 1.000 | Perfect |
| has_work_for_hire | 1.000 | Perfect |
| has_non_compete | 1.000 | Perfect |
| has_source_code_escrow | 1.000 | Perfect |
| has_license_grant | 0.936 | |
| has_feedback_clause | 0.933 | |
| has_provider_owns_deliverables | 0.867 | |
| has_customer_owns_deliverables | 0.815 | |
| has_pre_existing_ip_carveout | 0.741 | Hardest boundary |

### Per-Field Breakdown: Confidentiality (F1=0.920)

| Field | F1 | Notes |
|-------|-----|-------|
| has_injunctive_relief | 1.000 | Perfect |
| has_residuals_clause | 1.000 | Rare clause, correctly sparse |
| has_return_or_destroy | 0.971 | |
| has_permitted_disclosures | 0.941 | |
| has_duration | 0.889 | |
| has_standard_exclusions | 0.889 | |
| has_broad_definition | 0.839 | |
| is_mutual | 0.833 | |

### Per-Field Breakdown: Governing Law (F1=0.971)

| Field | F1 | Notes |
|-------|-----|-------|
| has_governing_law | 1.000 | Perfect |
| has_arbitration | 1.000 | Perfect |
| has_jury_waiver | 1.000 | Perfect |
| has_class_action_waiver | 1.000 | Perfect |
| has_prevailing_party_fees | 1.000 | Perfect |
| has_venue_selection | 0.826 | Over-triggers on jurisdiction language |

### Per-Field Breakdown: Termination (F1=0.881)

| Field | F1 | Notes |
|-------|-----|-------|
| has_termination_for_convenience | 1.000 | Perfect |
| has_termination_fee | 1.000 | Perfect |
| has_auto_renewal | 0.941 | |
| has_notice_period | 0.933 | |
| has_termination_for_cause | 0.909 | |
| has_cure_period | 0.857 | |
| has_survival_clause | 0.750 | |
| has_post_termination_obligations | 0.692 | Over-triggers |

---

## ML Risk Classifier

Trained on 617 labeled clauses using MiniLM-L6-v2 embeddings (384-dim) + sklearn LogisticRegression with CV-tuned regularization. Replaces the original hardcoded regex rules.

| Risk Category | Detection F1 | Severity Macro F1 |
|---------------|-------------|-------------------|
| Privacy/Data Risk | 1.000 | 1.000 |
| Financial Risk | 0.980 | 0.984 |
| Contractual Ambiguity | 0.977 | 0.980 |
| Liability Risk | 0.941 | 0.830 |
| Compliance Risk | 0.927 | 0.966 |
| **Average** | **0.965** | **0.952** |

---

## Retrieval Metrics

| Metric | Value |
|--------|-------|
| MRR@5 | **0.917** |
| NDCG@5 | **0.987** |
| Avg latency | 0.243s |
| Corpus size | 18,001 chunks from 116 SEC EDGAR contracts |

---

## Corpus

- **116 contracts** scraped from SEC EDGAR (EX-10 exhibits, SaaS MSAs)
- **18,001 clause chunks** with 384-dim embeddings
- Clause type distribution: liability (1,976), payment (2,116), confidentiality (2,400), termination (1,399), IP (636), governing law (853)
- Companies include Dynavax, Agile Therapeutics, Savara, Ecoark, Scilex, and more

---

## Quick Start

### Prerequisites
- Python 3.10+
- Supabase project with pgvector enabled
- LLM backend — choose one:
  - **[Groq](https://console.groq.com)** (recommended, free API, no credit card): `GROQ_API_KEY=gsk_...`
  - **[Ollama](https://ollama.com)** with `llama3.1:8b` (free, local): requires Ollama running
  - **Anthropic API** (~$0.007/clause, fastest quality): `ANTHROPIC_API_KEY=sk-ant-...`

### Setup

```bash
# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Configure environment
cp .env.example .env
# Edit .env: set SUPABASE_URL, SUPABASE_KEY, and one of GROQ_API_KEY / ANTHROPIC_API_KEY

# Start the backend
python -m uvicorn backend.main:app --reload
```

Open `frontend/index.html` in your browser. The "Benchmark & Redline" button runs the full pipeline.

**Accepts:** `.pdf`, `.txt`, `.md` file uploads. Clause type auto-detected from text (override via dropdown).

### Run Extraction Evals

```bash
# Run eval for any clause category
python -m backend.extraction.eval liability
python -m backend.extraction.eval termination
python -m backend.extraction.eval payment
python -m backend.extraction.eval confidentiality
python -m backend.extraction.eval ip
python -m backend.extraction.eval governing_law
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `GET` | `/corpus/stats` | Real-time corpus coverage (contracts, chunks, extraction %) |
| `POST` | `/analyze` | Analyze text for legal risks (ML classifier + semantic) |
| `POST` | `/analyze/upload` | Upload .pdf, .txt, or .md for analysis |
| `POST` | `/benchmark` | Benchmark a clause against EDGAR market data (auto-detect type) |
| `POST` | `/redline` | Generate grounded redline suggestions |

Swagger docs at `http://localhost:8000/docs`.

**Rate limiting:** `/analyze` at 30 req/min, `/benchmark` and `/redline` at 10 req/min per IP.

**API key auth:** Set `LRM_API_KEY` env var to require `X-API-Key` header on `/benchmark` and `/redline`.

### Run Tests

```bash
python -m pytest tests/ -v
```

42 tests covering schema validation, API endpoints, extraction pipeline integrity, and risk analysis.

### Deployment (free, no credit card)

Backend runs on **Hugging Face Spaces** (Docker, free CPU tier). Frontend deploys to **Vercel** (static, free).

```bash
# Local Docker test
docker build -t legal-risk-mapper .
docker run -p 8000:8000 --env-file .env legal-risk-mapper
```

See [`deploy/DEPLOYMENT.md`](deploy/DEPLOYMENT.md) for the full step-by-step guide.

---

## Project Structure

```
legal-risk-mapper/
├── backend/
│   ├── main.py                     # FastAPI app (5 endpoints, rate limiting, API key auth)
│   ├── corpus/                     # EDGAR pipeline
│   │   ├── edgar_scraper.py        # SEC EDGAR EFTS scraper
│   │   ├── chunker.py              # Clause segmentation + classification
│   │   ├── embedder.py             # all-MiniLM-L6-v2 embeddings
│   │   ├── db.py                   # Supabase client (CRUD + vector search)
│   │   ├── retrieval.py            # pgvector similarity search
│   │   └── pipeline.py             # Orchestrator (scrape -> chunk -> embed -> store)
│   ├── extraction/                 # Structured extraction (6 categories)
│   │   ├── schemas.py              # Pydantic models for all clause types
│   │   ├── extractor.py            # Ollama LLM extractor with per-type prompts
│   │   └── eval.py                 # Field-level P/R/F1 eval harness
│   ├── benchmarking/               # RAG market benchmarking
│   │   ├── schemas.py              # BenchmarkResult, FieldDistribution, CitedExample
│   │   ├── aggregator.py           # Market stats with per-category field registry
│   │   └── benchmarker.py          # Orchestrator (extract -> retrieve -> aggregate)
│   ├── redline/                    # Grounded redline generation
│   │   ├── schemas.py              # RedlineSuggestion, RedlineResult
│   │   └── generator.py            # LLM redline with market context
│   ├── services/                   # Risk analysis engine (ML-trained)
│   │   ├── risk_analyzer.py        # Hybrid pipeline: ML classifier + semantic matching
│   │   ├── risk_classifier.py      # Trained multi-label classifier inference
│   │   ├── risk_knowledge_base.py  # Auto-generated canonical clause embeddings
│   │   └── semantic_analyzer.py    # spaCy + sentence-transformers layer
│   └── models/                     # Shared models
├── frontend/
│   ├── index.html                  # Dashboard with benchmark + redline UI
│   ├── style.css                   # CSS (charts, diff viewer, cards)
│   └── app.js                      # API integration + rendering
├── data/
│   ├── eval/                       # Hand-labeled eval datasets (35 examples each)
│   │   ├── liability_eval.json
│   │   ├── termination_eval.json
│   │   ├── payment_eval.json
│   │   ├── confidentiality_eval.json
│   │   ├── ip_eval.json
│   │   └── governing_law_eval.json
│   └── models/
│       └── canonical_clauses.json  # Auto-generated canonical clauses (ML-derived)
├── scripts/
│   ├── run_corpus_pipeline.py      # EDGAR scrape + embed CLI
│   ├── run_batch_extraction.py     # Batch extraction with resume support
│   ├── eval_retrieval.py           # MRR@5 / NDCG@5 retrieval eval
│   ├── generate_training_data.py   # Risk classifier training data generator
│   ├── train_risk_classifier.py    # ML classifier training + canonical generation
│   └── eval_classifier.py          # ML vs regex comparison eval
├── tests/                          # Pytest suite (42 tests)
│   ├── test_schemas.py             # Pydantic schema validation
│   ├── test_extraction.py          # Extraction pipeline + registry integrity
│   ├── test_risk_analyzer.py       # Risk detection + severity scoring
│   └── test_api.py                 # FastAPI endpoint tests
├── .github/workflows/ci.yml       # GitHub Actions CI (pytest on push/PR)
├── Dockerfile                      # Production container (gunicorn + uvicorn)
├── railway.json                    # Railway deployment config
└── ROADMAP.md                      # Project roadmap + session handoff log
```

---

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Pluggable LLM backend** | Routes to Groq (free cloud), Anthropic (paid, fastest), or Ollama (local) based on env vars. Same prompts, same Pydantic schemas. |
| **6 clause categories** with shared pattern | Each category follows: Pydantic schema -> LLM prompt with critical rules -> eval dataset -> field registry -> benchmarking -> redline integration. Consistent architecture scales to new categories. |
| **pgvector** over Pinecone/Weaviate | Colocated with structured data in Supabase. No separate vector DB. IVFFlat index handles ~18k vectors. |
| **all-MiniLM-L6-v2** (384-dim) | Same embedding model across semantic analysis, retrieval, and risk classification. Consistent embedding space. |
| **Pydantic source_text grounding** | Every extracted field has a verbatim quote. Avg grounding score 0.953-1.000 across categories. |
| **ML classifier over regex rules** | Trained on 617 labeled clauses. Detection F1=0.965 vs regex baseline. Auto-generates canonical clauses from training data. |
| **Per-category field registry** | Generic aggregation engine looks up (bool_fields, cat_fields) per clause type. Adding a new category requires only field definitions, not code changes. |
| **35 hand-labeled examples per category** | Consistent eval methodology. Each dataset covers all field combinations with realistic clause language from SaaS contracts. |

---

## Limitations

- **8B model boundary cases**: Llama 3.1 8B struggles with subjective fields like `is_mutual` and `has_pre_existing_ip_carveout`. Groq's `llama-3.1-70b-versatile` (also free) or Anthropic Sonnet improve precision on these.
- **Market sample size**: Benchmark quality depends on EDGAR corpus coverage per clause type. IP (636 chunks) and governing law (853 chunks) have smaller samples than liability (1,976).

---

## Disclaimer

This tool is a prototype for educational and portfolio purposes. It is not a substitute for qualified legal advice. Always consult a licensed attorney for legal decisions.
