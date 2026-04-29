# Legal Risk Mapper

A contract analysis platform that performs **structured clause extraction**, **RAG-based market benchmarking**, and **grounded redline generation** for SaaS Master Service Agreements. It analyzes liability clauses from uploaded contracts, compares them against a corpus of real SEC EDGAR filings, and generates specific edit suggestions backed by market data.

---

## What It Does

1. **Structured Extraction** — Extracts structured fields from liability clauses (caps, mutuality, carve-outs, consequential damages, indemnification, warranty disclaimers) with source text provenance for every field.

2. **Market Benchmarking** — Retrieves similar clauses from a corpus of 116 real SEC EDGAR contracts using pgvector similarity search, then computes field-level market distributions and percentile ranks.

3. **Grounded Redlines** — Generates contract edit suggestions where every recommendation cites specific market statistics and real SEC filings, not LLM opinion.

---

## Architecture

```
User Clause (text)
    │
    ├─→ LLM Extraction (Ollama/Llama 3.1 8B)
    │       → Pydantic schema with source_text grounding
    │
    ├─→ pgvector Retrieval (all-MiniLM-L6-v2, 384-dim)
    │       → Top-20 similar clauses from EDGAR corpus
    │       → Join with structured_extractions table
    │
    ├─→ Market Aggregation
    │       → Field distributions (% with caps, % mutual, etc.)
    │       → User percentile ranking
    │       → 5 cited examples with SEC filing links
    │
    └─→ Redline Generation (LLM + market context)
            → Original → Proposed diffs
            → Each cites market stats + real filings
```

---

## Evaluation Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Extraction F1 (core booleans) | **0.762** | >= 0.75 |
| Extraction success rate | 97.6% | - |
| Grounding score | 0.975 | - |
| Retrieval MRR@5 | **0.917** | > 0.70 |
| Retrieval NDCG@5 | **0.987** | > 0.75 |
| Retrieval latency | 0.243s avg | < 2.0s |
| E2E latency (local 8B) | 57.5s avg | ~3-5s with Sonnet |
| E2E extraction success | 100% (8/8 test clauses) | > 90% |
| Cost per clause (local) | **$0.00** | ~$0.007 with Sonnet |

**Per-field extraction results (42 hand-labeled examples):**

| Field | Precision | Recall | F1 |
|-------|-----------|--------|----|
| has_cap | 0.800 | 1.000 | 0.889 |
| has_indemnification | 0.846 | 0.917 | 0.880 |
| consequential_excluded | 0.714 | 1.000 | 0.833 |
| is_mutual | 0.750 | 0.750 | 0.750 |
| has_warranty_disclaimer | 0.600 | 0.750 | 0.667 |
| has_carve_outs | 0.455 | 0.714 | 0.556 |

---

## Corpus

- **116 contracts** scraped from SEC EDGAR (EX-10 exhibits, SaaS MSAs)
- **18,001 clause chunks** with 384-dim embeddings
- **~1,999 liability clauses** with structured extractions
- Companies include Dynavax, Agile Therapeutics, Savara, Ecoark, Scilex, and more

---

## Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) with `llama3.1:8b` model
- Supabase project with pgvector enabled

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Supabase URL/key

# Pull the LLM model
ollama pull llama3.1:8b

# Start the backend
python -c "from dotenv import load_dotenv; load_dotenv(); import uvicorn; uvicorn.run('backend.main:app', host='0.0.0.0', port=8000)"
```

Open `frontend/index.html` in your browser. The "Benchmark & Redline" button runs the full pipeline.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/analyze` | Analyze text for legal risks (regex + semantic) |
| `POST` | `/analyze/upload` | Upload a .txt file for analysis |
| `POST` | `/benchmark` | Benchmark a clause against EDGAR market data |
| `POST` | `/redline` | Generate grounded redline suggestions |

Swagger docs at `http://localhost:8000/docs`.

---

## Project Structure

```
legal-risk-mapper/
├── backend/
│   ├── main.py                     # FastAPI app (5 endpoints)
│   ├── corpus/                     # Phase 1: EDGAR pipeline
│   │   ├── edgar_scraper.py        # SEC EDGAR EFTS scraper
│   │   ├── chunker.py              # Clause segmentation + classification
│   │   ├── embedder.py             # all-MiniLM-L6-v2 embeddings
│   │   ├── db.py                   # Supabase client (CRUD + vector search)
│   │   ├── retrieval.py            # pgvector similarity search
│   │   └── pipeline.py             # Orchestrator (scrape → chunk → embed → store)
│   ├── extraction/                 # Phase 2: Structured extraction
│   │   ├── schemas.py              # LiabilityExtraction Pydantic models
│   │   ├── extractor.py            # Ollama LLM extractor with retry logic
│   │   └── eval.py                 # Field-level P/R/F1 eval harness
│   ├── benchmarking/               # Phase 3: RAG market benchmarking
│   │   ├── schemas.py              # BenchmarkResult, FieldDistribution, CitedExample
│   │   ├── aggregator.py           # Market stats computation
│   │   └── benchmarker.py          # Orchestrator (extract → retrieve → aggregate)
│   ├── redline/                    # Phase 4: Grounded redline generation
│   │   ├── schemas.py              # RedlineSuggestion, RedlineResult
│   │   └── generator.py            # LLM redline with market context
│   ├── services/                   # v1/v2: Risk analysis engine
│   │   ├── risk_analyzer.py        # 60+ regex patterns + semantic matching
│   │   └── semantic_analyzer.py    # spaCy + sentence-transformers layer
│   └── models/                     # Shared models
├── frontend/
│   ├── index.html                  # Dashboard with benchmark + redline UI
│   ├── style.css                   # Polished CSS (charts, diff viewer, cards)
│   └── app.js                      # API integration + rendering
├── data/
│   └── eval/
│       └── liability_eval.json     # 42 hand-labeled ground truth examples
├── migrations/
│   └── 001_corpus_tables.sql       # Supabase schema (contracts, chunks, extractions)
├── scripts/
│   ├── run_corpus_pipeline.py      # EDGAR scrape + embed CLI
│   ├── run_batch_extraction.py     # Batch extraction with resume support
│   ├── eval_retrieval.py           # MRR@5 / NDCG@5 retrieval eval
│   ├── test_benchmark.py           # Benchmark pipeline test
│   └── test_redline.py             # Redline pipeline test
└── ROADMAP.md                      # Project roadmap + session handoff log
```

---

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Ollama/Llama 3.1 8B** over Anthropic Haiku | Zero API cost. Trades ~10% accuracy for fully local inference. Sonnet/Haiku is a drop-in upgrade. |
| **pgvector** over Pinecone/Weaviate | Colocated with structured data in Supabase. No separate vector DB to manage. IVFFlat index is fast enough for ~18k vectors. |
| **all-MiniLM-L6-v2** (384-dim) | Same model as the semantic analysis layer. Consistent embedding space. Fast inference on MPS/CPU. |
| **Pydantic source_text grounding** | Every extracted field has a verbatim quote. Prevents hallucination. Grounding score of 0.975 confirms real provenance. |
| **Keyword heuristic → manual audit** for ground truth | Initial labels generated programmatically, then manually corrected over 5 prompt iterations. Caught 6 mislabeled examples. |
| **Core F1 threshold of 0.75** (not 0.85) | Realistic for 8B local model. Documented that larger models would push above 0.85. |

---

## Limitations

- **Liability only**: Currently handles one clause category. The extraction → RAG → redline pattern is proven and can be replicated to termination, IP, payment, confidentiality, and governing law.
- **8B model accuracy**: Llama 3.1 8B struggles with nuanced fields like `cap_type` (F1=0.375) and `has_carve_outs` (F1=0.556). A 70B or API model would improve these.
- **No PDF parsing**: Accepts .txt input only. PDF support can be added with PyMuPDF.
- **Market sample size**: Benchmark quality depends on extraction coverage. With ~1,000 extractions across 1,999 liability chunks, most queries get 5-15 market data points.

---

## Disclaimer

This tool is a prototype for educational and portfolio purposes. It is not a substitute for qualified legal advice. Always consult a licensed attorney for legal decisions.
