# ALRM — Automated Legal Risk Monitor

ML-based risk classification across 5 categories, structured extraction from 6 clause types with per-field F1 evaluation, pgvector market benchmarking against 116 real SEC EDGAR contracts, and grounded redline generation where every suggestion cites specific market statistics from actual filings.

<!-- TODO: Add screenshot of redline view with market citations -->

What separates ALRM from a typical contract analysis project: the risk classifier is a trained ensemble of 5 independent LogisticRegression models over sentence embeddings — not API calls to a general-purpose LLM. The EDGAR corpus is 18,001 clause chunks scraped directly from SEC EX-10 exhibits, not synthetic data. Each of the 6 extraction categories has a hand-labeled evaluation set and a measured F1 score. And redline suggestions are constrained to cite specific market statistics ("73% of similar contracts include X") derived from structured extractions over the corpus, not LLM legal opinion.

---

## Architecture

```
Input text / PDF upload
        │
        ▼
┌───────────────────────────────────┐
│   spaCy clause segmentation       │  [traditional NLP]
│   en_core_web_sm sentencizer      │
└───────────────┬───────────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌──────────────┐  ┌──────────────────────────────────────┐
│ ML Risk      │  │ LLM Structured Extraction             │
│ Classifier   │  │ Groq llama-3.3-70b-versatile          │
│ [ML]         │  │ 6 Pydantic schemas w/ source_text     │
│              │  │ [LLM]                                 │
│ 5 independent│  └──────────────────┬─────────────────── ┘
│ LR models    │                     │
│ MiniLM-L6-v2 │          ┌──────────┴──────────┐
│ embeddings   │          │                     │
│ [ML]         │          ▼                     ▼
└──────┬───────┘  ┌──────────────────┐  ┌──────────────────┐
       │          │ pgvector RAG     │  │ Redline          │
       │          │ Benchmarking     │  │ Generation       │
       │          │                  │  │                  │
       │          │ MiniLM cosine    │  │ Groq LLM with    │
       │          │ search over      │  │ market context   │
       │          │ 18,001 chunks    │  │ injected into    │
       │          │ [ML + DB]        │  │ prompt           │
       │          │                  │  │ [LLM]            │
       │          │ Field distrib.   │  │                  │
       │          │ percentile rank  │  │ Every suggestion │
       │          │ 5 cited examples │  │ cites a specific │
       │          └──────────────────┘  │ market stat      │
       │                                └──────────────────┘
       ▼
Risk results:
category, severity,
flagged snippet,
confidence score
```

**Pipeline 1 — Risk Classification.** Five independent binary classifiers rather than a single multi-label model because each category has different class balance, different regularization requirements (C values range from 5.0 to 10.0 across categories), and threshold tuning that needs to happen per-category. A semantic similarity layer runs in parallel using cosine distance against 30 auto-generated canonical clause embeddings (cluster centroids from training data). When both layers flag the same clause for the same category, they merge into a single boosted-confidence result. Graceful degradation: if the pkl file is missing, the system falls back to regex rules; if sentence-transformers fails to load, the semantic layer is silently disabled.

**Pipeline 2 — Structured Extraction.** Each of the 6 clause types has a dedicated Pydantic schema with every factual field accompanied by a `source_text` field requiring a verbatim quote. This is not optional — it is enforced in the prompt as a critical rule and validated at the schema level. Groq's llama-3.3-70b-versatile handles inference because the 8B model produces meaningful false positives on fields like `is_mutual` and `has_pre_existing_ip_carveout` where context sensitivity matters. The LLM router tries Anthropic first (if `ANTHROPIC_API_KEY` set), then Groq, then Ollama — same prompts and schemas across all backends.

**Pipeline 3 — Benchmarking.** pgvector over Pinecone because the structured extraction data already lives in Supabase — co-locating the vector index with the relational data eliminates a service dependency and enables joining on extraction results in a single query. The `match_clauses()` Postgres RPC function handles cosine similarity over 18,001 384-dim vectors using IVFFlat. Percentile calculation: for a boolean field with 73% market prevalence, a user clause that has the feature is at the 73rd percentile; one that lacks it is at the 27th percentile. Retrieval quality: MRR@5 of 0.917.

**Pipeline 4 — Redline Generation.** The prompt receives a formatted market context block containing field distributions, user percentile rankings, and 3 cited examples with their extracted fields. The LLM is explicitly constrained: every suggestion must cite a specific market statistic, `original_text` must be an exact quote from the clause, `proposed_text` must be a concrete replacement. This constraint exists because "you should consider adding X" is not useful to a lawyer. "X appears in 81% of similar contracts; your clause lacks it" is.

---

## Evaluation Results

### Risk Classification — 617 labeled examples, 5-fold cross-validation

| Category               | Detection F1 | Severity Macro F1 | CV Score |
|------------------------|:------------:|:-----------------:|:--------:|
| Privacy/Data Risk      | 1.000        | 1.000             | 0.994    |
| Financial Risk         | 0.980        | 0.984             | 0.955    |
| Contractual Ambiguity  | 0.977        | 0.980             | 0.957    |
| Liability Risk         | 0.941        | 0.830             | 0.959    |
| Compliance Risk        | 0.927        | 0.966             | 0.979    |
| **Average**            | **0.965**    | **0.952**         | —        |

Regularization parameter C was cross-validated independently per category. Per-category reports (precision, recall, F1 by severity level) are stored in `data/models/risk_classifier.pkl` under the `metrics` key.

### Extraction — 35 hand-labeled examples per category (42 for liability)

| Clause Type     | Core Field F1 | Success Rate | Avg Grounding Score | Eval Examples |
|-----------------|:-------------:|:------------:|:-------------------:|:-------------:|
| Governing Law   | 0.971         | 100%         | 1.000               | 35            |
| Payment         | 0.941         | 100%         | 1.000               | 35            |
| IP              | 0.921         | 100%         | 0.996               | 35            |
| Confidentiality | 0.920         | 100%         | 0.953               | 35            |
| Termination     | 0.881         | 94.3%        | 0.973               | 35            |
| Liability       | 0.762         | 97.6%        | 0.975               | 42            |

Grounding score measures the fraction of extracted field values where the accompanying `source_text` is a verified substring of the input clause. A grounding score below 1.0 indicates fields where the model generated a source quote that drifts from the exact contract language.

### Retrieval — pgvector over 18,001 chunks from 116 contracts

| Metric             | Value  |
|--------------------|--------|
| MRR@5              | 0.917  |
| NDCG@5             | 0.987  |
| Avg query latency  | 0.243s |

All evaluation code is in `scripts/` and labeled datasets are in `data/eval/`. To regenerate:

```bash
python -m backend.extraction.eval --eval-file data/eval/liability_eval.json
python -m scripts.eval_retrieval
python -m scripts.eval_classifier
```

---

## Data Pipeline

The EDGAR corpus was built in three stages. First, SEC EDGAR's full-text search API (`efts.sec.gov/LATEST/search-index`) was queried for EX-10 exhibit filings containing MSA-related terms across 2018–2023. EX-10 exhibits are material contracts that public companies are required to file; they include SaaS MSAs, software license agreements, and professional services contracts. 116 contracts passed content verification (minimum MSA content, successfully downloaded, adequate length).

Each contract was chunked at section boundaries using a regex pattern that detects numbered headings (`1.`, `1.1`, `ARTICLE I`) and all-caps section titles. Within sections, long paragraphs were sub-split to stay within 1,500 characters. Each chunk was classified into one of 6 target categories using keyword-density heuristics — this is a fast pre-filter, not the final extraction. Chunks classified as `other` remain in the database but are excluded from typed retrieval queries.

Embeddings were generated using `all-MiniLM-L6-v2` (384-dim) in batches of 64, matching the embedding model used across the ML classifier and semantic analysis layer for a consistent vector space. Vectors are stored in Supabase using the pgvector extension.

The Supabase schema has three tables: `contracts` (id, company, form_type, filed_date, accession, exhibit_url), `clause_chunks` (id, contract_id, chunk_index, text, section_header, clause_type, embedding vector(384)), and `structured_extractions` (chunk_id, clause_type, extracted_data jsonb, model_used). The pgvector index uses IVFFlat with cosine distance.

**Current extraction coverage:**

| Clause Type     | Chunks | Extracted | Coverage |
|-----------------|-------:|----------:|:--------:|
| Governing Law   | 874    | 708       | 81.0%    |
| Liability       | 1,999  | 981       | 49.1%    |
| Confidentiality | 2,423  | 990       | 40.9%    |
| IP              | 656    | 18        | 2.7%     |
| Termination     | 1,434  | 11        | 0.8%     |
| Payment         | 2,156  | 15        | 0.7%     |

Batch extraction is in progress using Claude Haiku (`claude-haiku-4-5-20251001`) via the Anthropic API. The extractor script supports resume — it skips chunks with existing rows in `structured_extractions`.

---

## Tech Stack

| Layer           | Technology                                                                                          |
|-----------------|-----------------------------------------------------------------------------------------------------|
| Backend         | FastAPI 0.111, Gunicorn 22 + Uvicorn workers                                                        |
| ML Classifier   | sklearn LogisticRegression (5 independent models), sentence-transformers all-MiniLM-L6-v2 (384-dim) |
| LLM Inference   | Groq API, llama-3.3-70b-versatile (extraction + redlines)                                           |
| Database        | Supabase PostgreSQL + pgvector, IVFFlat index                                                       |
| NLP             | spaCy en_core_web_sm (clause segmentation), MiniLM-L6-v2 (embeddings)                              |
| PDF Extraction  | PyMuPDF (MuPDF bindings)                                                                            |
| Frontend        | Vanilla HTML/CSS/JS, no framework, Vercel static hosting                                            |
| Deployment      | Docker on Hugging Face Spaces (backend, free CPU tier)                                              |
| CI              | GitHub Actions, pytest on push and PR                                                               |

---

## API Reference

| Method | Path              | Auth             | Rate Limit | Description                               |
|--------|-------------------|------------------|:----------:|-------------------------------------------|
| GET    | `/health`         | None             | —          | Version and NLP engine status             |
| GET    | `/corpus/stats`   | None             | —          | Live extraction coverage per clause type  |
| POST   | `/analyze`        | None             | 30/min     | ML risk classification of raw text        |
| POST   | `/analyze/upload` | None             | 30/min     | Upload and analyze .pdf, .txt, or .md     |
| POST   | `/extract`        | None             | 30/min     | Extract raw text from an uploaded file    |
| POST   | `/benchmark`      | Optional API key | 10/min     | RAG benchmarking against EDGAR corpus     |
| POST   | `/redline`        | Optional API key | 10/min     | Benchmark then generate grounded redlines |

Live health check: `https://sriniv-1-legal-risk-mapper.hf.space/health`

Swagger docs at `/docs` when running locally.

---

## Key Technical Decisions

**5 independent binary classifiers over one multi-label model.** Each risk category has different class balance and different optimal regularization. Per-category classifiers allow independent threshold tuning, produce cleaner per-category probability scores, and fail gracefully — if one category's training data is insufficient, the other four classifiers are unaffected. In practice, C values vary from 5.0 (Privacy/Data, Financial) to 10.0 (Compliance, Liability, Ambiguity) across categories, which a single model could not accommodate.

**Source-text grounding on every extracted field.** Every boolean field in the 6 Pydantic schemas has a companion `source_text` field. The extraction prompt enforces this as a critical rule, and grounding scores are measured in eval (0.953–1.000 across categories). Legal professionals do not act on ungrounded output — a claim that a contract "has_carve_outs: true" is only useful if it cites the exact contract language that supports the claim.

**pgvector over a dedicated vector database.** The structured extraction data already lives in Supabase. Co-locating the vector index eliminates an additional service dependency, allows SQL joins between similarity search results and `structured_extractions` in a single Postgres RPC call, and avoids paying for a separate managed vector store. At 18,001 384-dim vectors, IVFFlat performs adequately with 0.243s average query latency.

**Groq 70B over local Ollama 8B for user-facing inference.** The 8B model produces measurable false positives on context-sensitive fields (`is_mutual`, `has_pre_existing_ip_carveout`, `has_residuals_clause`) that show up as extraction errors against the eval sets. Groq's free tier has no GPU requirement and handles portfolio-level traffic. The LLM router (Anthropic → Groq → Ollama) means the code works in all environments without changes.

**Market-grounded redlines over pure LLM legal knowledge.** The redline generator receives a structured prompt block containing field distributions from real EDGAR filings and user percentile rankings, and is explicitly constrained to cite specific statistics in every suggestion. This is more persuasive to a transactional lawyer than LLM opinion, and it is verifiable — the cited statistic traces back to real SEC filings linked in the UI.

---

## Limitations and Future Work

**Current limitations:**

The corpus extraction coverage is uneven: governing law is 81% complete, but termination (0.8%), payment (0.7%), and IP (2.7%) have almost no structured extractions. Benchmarking against these clause types returns thin market samples and unreliable distributions. Batch extraction is in progress.

The corpus was extracted with Ollama 8B locally; user clauses are extracted with Groq 70B. These models have different extraction tendencies, which causes occasional cross-model inconsistencies where a field appears in the user extraction but rarely in the corpus extractions. The correct fix is to re-extract the corpus with the same model used at inference time.

Liability extraction F1 is 0.762 — the lowest category and the one with the most legal consequence. The weak fields are `consequential_excluded` (0.762 in the per-field breakdown) and `is_mutual` (which requires understanding whether both parties are subject to the same limitations). Both need more labeled examples and prompt iteration.

ALRM is English-only and US law only. It does not support scanned PDFs (no OCR). The free HF Spaces tier cold-starts after inactivity with a 1–2 minute warmup. Groq's free tier allows approximately 1,000 requests per day.

**Planned improvements:**

Complete batch extraction for termination, payment, and IP to reach meaningful market sample sizes. Re-extract the corpus with Groq 70B for cross-model consistency. Iterate on the liability extraction prompt and expand the eval set to target 0.85+ F1. Add confidence calibration to the risk classifier using Platt scaling. Expand beyond SaaS MSAs to NDA templates, employment agreements, and vendor contracts.

---

## Local Development

**Prerequisites:** Python 3.12+, a Supabase project with pgvector enabled, and a Groq API key (free at console.groq.com, no credit card).

```bash
git clone https://github.com/SriniV-1/legal-risk-mapper.git
cd legal-risk-mapper

pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

**Environment variables:**

| Variable                | Required | Purpose                                                                                  |
|-------------------------|:--------:|------------------------------------------------------------------------------------------|
| `SUPABASE_URL`          | Yes      | Supabase project URL                                                                     |
| `SUPABASE_KEY`          | Yes      | Supabase service-role key                                                                |
| `GROQ_API_KEY`          | Yes      | Groq API key for extraction and redlines                                                 |
| `ANTHROPIC_API_KEY`     | No       | Use Claude for extraction (falls back to Groq)                                           |
| `LRM_EXTRACTION_MODEL`  | No       | Override extraction model (default: `llama3.1:8b`, auto-switched to Groq when key present) |
| `LRM_API_KEY`           | No       | Require `X-API-Key` header on `/benchmark` and `/redline`                               |
| `CORS_ORIGINS`          | No       | Comma-separated allowed origins (default: `*`)                                           |

```bash
cp .env.example .env
# Edit .env with your credentials

# Start backend
set -a; source .env; set +a
python -m uvicorn backend.main:app --reload
```

Open `frontend/index.html` in a browser, or serve with `python -m http.server 3000` from `frontend/`.

**Run tests:**

```bash
python -m pytest tests/ -v
```

49 tests covering schema validation, API endpoints, extraction pipeline integrity, and risk analysis. Tests stub Supabase credentials and do not require a live database.

**Run extraction eval:**

```bash
python -m backend.extraction.eval liability
python -m backend.extraction.eval termination
python -m backend.extraction.eval payment
python -m backend.extraction.eval confidentiality
python -m backend.extraction.eval ip
python -m backend.extraction.eval governing_law
```

---

## Project Structure

```
legal-risk-mapper/
├── backend/
│   ├── main.py                      # FastAPI app — 7 endpoints, rate limiting, API key auth
│   ├── corpus/                      # EDGAR data pipeline (one-time collection)
│   │   ├── edgar_scraper.py         # EFTS search + EX-10 exhibit downloader
│   │   ├── chunker.py               # Section-boundary chunking + keyword-density classifier
│   │   ├── embedder.py              # MiniLM-L6-v2 batch encoder (batch size 64)
│   │   ├── db.py                    # Supabase client — CRUD + pgvector RPC wrapper
│   │   └── retrieval.py             # Cosine similarity search with clause type filter
│   ├── extraction/                  # LLM structured extraction
│   │   ├── schemas.py               # 6 Pydantic models — all fields grounded with source_text
│   │   ├── extractor.py             # LLM router (Anthropic → Groq → Ollama) + per-type prompts
│   │   └── eval.py                  # Field-level precision/recall/F1 harness
│   ├── benchmarking/                # RAG market statistics
│   │   ├── aggregator.py            # Field distributions, percentile ranking, per-category registry
│   │   └── benchmarker.py           # Orchestrator: extract → retrieve → join extractions → aggregate
│   ├── redline/                     # Grounded suggestion generation
│   │   ├── generator.py             # Market context formatter + LLM prompt + response parser
│   │   └── schemas.py               # RedlineSuggestion, RedlineResult
│   └── services/                   # ML risk classification engine
│       ├── risk_analyzer.py         # Full pipeline: segment → classify → semantic → merge → score
│       ├── risk_classifier.py       # Trained model loader + inference (5 LR classifiers)
│       ├── risk_knowledge_base.py   # 30 canonical clause embeddings (cluster centroids)
│       └── semantic_analyzer.py     # Cosine similarity layer, spaCy segmentation
├── data/
│   ├── eval/                        # Hand-labeled evaluation datasets (35-42 examples each)
│   │   ├── liability_eval.json      # 42 examples with full ground truth
│   │   ├── termination_eval.json
│   │   ├── payment_eval.json
│   │   ├── confidentiality_eval.json
│   │   ├── ip_eval.json
│   │   └── governing_law_eval.json
│   └── models/
│       ├── risk_classifier.pkl      # Trained sklearn bundle: 5 LR models + per-category metrics
│       └── canonical_clauses.json   # 30 canonical clause embeddings for semantic layer
├── scripts/                         # One-time training and evaluation scripts
│   ├── run_corpus_pipeline.py       # EDGAR scrape → chunk → embed → store
│   ├── run_batch_extraction.py      # Batch LLM extraction with resume support
│   ├── generate_training_data.py    # 617 labeled example generator
│   ├── train_risk_classifier.py     # Train 5 LR classifiers + generate canonicals
│   ├── eval_classifier.py           # ML vs regex comparison
│   └── eval_retrieval.py            # MRR@5 / NDCG@5 retrieval eval
├── tests/                           # 49 pytest tests
│   ├── test_api.py                  # FastAPI endpoint integration tests
│   ├── test_extraction.py           # Prompt coverage, schema registry, grounding rules
│   ├── test_risk_analyzer.py        # Risk detection and severity scoring
│   └── test_schemas.py              # Pydantic schema validation and constraints
├── frontend/
│   ├── index.html                   # Landing page
│   ├── app.html                     # Analysis tool — risk, benchmark, redline views
│   └── config.js                    # window.LRM_API_BASE
├── Dockerfile                       # python:3.12-slim, port 7860 for HF Spaces
└── .github/workflows/ci.yml         # pytest on push and PR, Python 3.12
```

---

## Disclaimer

ALRM is a research and portfolio project. It is not a substitute for qualified legal advice. Always consult a licensed attorney for legal decisions.
