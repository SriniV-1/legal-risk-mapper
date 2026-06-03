"""
ALRM — Automated Legal Risk Monitor — FastAPI Backend
Endpoints:
  POST /analyze    → analyze text for legal risks
  POST /benchmark  → benchmark a clause against EDGAR market data
  POST /redline    → generate grounded redline suggestions
  GET  /health     → service health check
"""
import io
import logging
import os
from collections import Counter
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.models.schemas import (
    AnalyzeRequest, AnalyzeResponse, HealthResponse, ReadyResponse, RiskItem
)
from backend.services.risk_analyzer import analyze_risks, compute_overall_risk
from backend.services.cache import cache_get, cache_set, cache_clear, cache_stats, _text_hash
from backend.services.metrics import record_analysis, record_error
from backend.routers.metrics_router import metrics_router
from backend.benchmarking.schemas import BenchmarkResult
from backend.redline.schemas import RedlineResult

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("lrm")

# ── Rate Limiting ────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── API Key Auth ─────────────────────────────────────────────────────────────
# If LRM_API_KEY is set, /benchmark and /redline require X-API-Key header.
# If not set, auth is disabled (local dev mode).
_API_KEY = os.environ.get("LRM_API_KEY")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_api_key(api_key: Optional[str] = Security(_api_key_header)):
    """Validate API key if one is configured. No-op in dev mode."""
    if _API_KEY is None:
        return  # Auth disabled — dev mode
    if api_key != _API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ── Lifespan (startup/shutdown) ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the semantic layer at startup so the first request doesn't stall."""
    try:
        from backend.services.semantic_analyzer import warmup
        ready = warmup()
        logger.info(f"Semantic layer {'READY' if ready else 'DISABLED (regex-only mode)'}")
    except Exception as e:
        logger.warning(f"Semantic warmup failed: {e}")
    yield  # application runs here


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ALRM — Automated Legal Risk Monitor",
    description="NLP-powered legal risk analysis for contracts, policies, and business text.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_response(risks: list, document_title: Optional[str]) -> AnalyzeResponse:
    risk_summary = dict(Counter(r["risk_type"] for r in risks))
    severity_breakdown = dict(Counter(r["severity"] for r in risks))
    overall = compute_overall_risk(risks)

    risk_items = [RiskItem(**r) for r in risks]

    notes = []
    if not risks:
        notes.append("No significant legal risks detected. Consider a professional legal review for critical documents.")
    else:
        high = severity_breakdown.get("High", 0)
        if high > 0:
            notes.append(f"{high} HIGH severity issue(s) require immediate legal attention.")
        notes.append("This is an automated analysis. Always consult a qualified attorney for legal decisions.")

    return AnalyzeResponse(
        document_title=document_title,
        total_risks=len(risks),
        risk_summary=risk_summary,
        severity_breakdown=severity_breakdown,
        risks=risk_items,
        overall_risk_level=overall,
        analysis_notes=" ".join(notes),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health_check():
    """Service liveness check. Reports whether the semantic layer is active."""
    from backend.models import embeddings
    engine_parts = ["regex", "TF-IDF"]
    if embeddings.is_available():
        engine_parts.append("sentence-transformers (MiniLM-L6)")
    try:
        import spacy  # noqa: F401
        engine_parts.append("spaCy clause segmentation")
    except ImportError:
        pass
    return JSONResponse(content={
        "status": "ok",
        "version": "2.0.0",
        "nlp_engine": " + ".join(engine_parts),
        "cache": cache_stats(),
    })


@app.post("/cache/clear", tags=["Meta"])
def clear_cache():
    """Clear the analysis cache. Returns the number of evicted entries."""
    evicted = cache_clear()
    return {"evicted": evicted}


@app.get("/ready", response_model=ReadyResponse, tags=["Meta"])
def readiness_check():
    """Deep readiness check — probes core dependencies."""
    checks: dict[str, str] = {}

    # 1. Semantic layer (sentence-transformers)
    try:
        from backend.models import embeddings
        checks["semantic"] = "ok" if embeddings.is_available() else "unavailable"
    except Exception:
        checks["semantic"] = "unavailable"

    # 2. spaCy model
    try:
        import spacy
        spacy.load("en_core_web_sm")
        checks["spacy"] = "ok"
    except Exception:
        checks["spacy"] = "unavailable"

    # 3. ML risk classifier
    try:
        from backend.services.risk_classifier import is_available as clf_available
        checks["risk_classifier"] = "ok" if clf_available() else "unavailable"
    except Exception:
        checks["risk_classifier"] = "unavailable"

    # 4. Supabase (optional — does not affect readiness)
    try:
        from backend.corpus.db import _get_client
        _get_client()
        checks["supabase"] = "ok"
    except Exception:
        checks["supabase"] = "unavailable"

    # Core services: semantic + spaCy must be up
    ready = checks.get("semantic") == "ok" and checks.get("spacy") == "ok"
    response = ReadyResponse(ready=ready, checks=checks)

    if ready:
        return response
    return JSONResponse(status_code=503, content=response.model_dump())


@app.get("/corpus/stats", tags=["Meta"])
def corpus_stats():
    """
    Return corpus coverage statistics: contracts, chunks by type,
    and extraction coverage for each clause category.
    """
    try:
        from backend.corpus.db import _get_client
        client = _get_client()

        r_contracts = client.table("contracts").select("id", count="exact").execute()
        r_chunks = client.table("clause_chunks").select("id", count="exact").execute()

        clause_types = ["liability", "termination", "payment", "confidentiality", "ip", "governing_law"]
        chunk_counts, extraction_counts = {}, {}
        for ct in clause_types:
            rc = client.table("clause_chunks").select("id", count="exact").eq("clause_type", ct).execute()
            re = client.table("structured_extractions").select("id", count="exact").eq("clause_type", ct).execute()
            chunk_counts[ct] = rc.count or 0
            extraction_counts[ct] = re.count or 0

        return {
            "contracts": r_contracts.count,
            "total_chunks": r_chunks.count,
            "clause_types": {
                ct: {
                    "chunks": chunk_counts[ct],
                    "extractions": extraction_counts[ct],
                    "coverage_pct": round(extraction_counts[ct] / chunk_counts[ct] * 100, 1) if chunk_counts[ct] > 0 else 0,
                }
                for ct in clause_types
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats unavailable: {e}")


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
@limiter.limit("30/minute")
def analyze_text(request: Request, body: AnalyzeRequest):
    """
    Analyze raw text for legal risks.
    Returns categorized risks with severity scores and explanations.
    """
    text_hash = _text_hash(body.text)
    cached = cache_get(text_hash)
    if cached is not None:
        logger.info(f"Cache HIT | title={body.document_title!r} | hash={text_hash[:12]}")
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    logger.info(f"Analyzing text | title={body.document_title!r} | chars={len(body.text)}")
    import time as _time
    t0 = _time.monotonic()
    try:
        risks = analyze_risks(body.text)
        response = _build_response(risks, body.document_title)
        result_dict = response.model_dump(mode="json")
        cache_set(text_hash, result_dict)
        record_analysis(_time.monotonic() - t0, risks, cache_hit=False)
        return JSONResponse(content=result_dict, headers={"X-Cache": "MISS"})
    except Exception as e:
        logger.exception("Analysis failed")
        record_error()
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


def _extract_text_from_upload(filename: str, content: bytes) -> str:
    """Extract plain text from an uploaded file (txt, md, or pdf)."""
    if filename.lower().endswith(".pdf"):
        try:
            import pymupdf  # fitz
            doc = pymupdf.open(stream=content, filetype="pdf")
            pages = [page.get_text() for page in doc]
            doc.close()
            return "\n\n".join(pages)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not extract text from PDF: {e}. Try saving as .txt."
            )
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


@app.post("/analyze/upload", response_model=AnalyzeResponse, tags=["Analysis"])
@limiter.limit("30/minute")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    document_title: Optional[str] = Form(default=None),
):
    """
    Analyze an uploaded file (.txt, .md, or .pdf) for legal risks.
    PDF text is extracted with PyMuPDF.
    """
    allowed = (".txt", ".md", ".pdf")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400,
            detail="Only .txt, .md, and .pdf files are supported."
        )

    content = await file.read()
    text = _extract_text_from_upload(file.filename, content)

    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Uploaded file appears to be empty or too short.")

    title = document_title or file.filename
    logger.info(f"Analyzing uploaded file | title={title!r} | chars={len(text)}")

    try:
        risks = analyze_risks(text)
        return _build_response(risks, title)
    except Exception as e:
        logger.exception("Upload analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.post("/extract", tags=["Analysis"])
@limiter.limit("30/minute")
async def extract_text(
    request: Request,
    file: UploadFile = File(...),
):
    """Extract plain text from an uploaded .txt, .md, or .pdf file."""
    allowed = (".txt", ".md", ".pdf")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(status_code=400, detail="Only .txt, .md, and .pdf files are supported.")
    content = await file.read()
    text = _extract_text_from_upload(file.filename, content)
    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="File appears empty or too short.")
    return {"text": text, "char_count": len(text)}


def _resolve_clause_type(text: str, requested: str) -> str:
    """
    Resolve the effective clause type.

    If the client passes "auto" (or doesn't know), detect from the text using
    the same keyword-density classifier used by the corpus chunker. Falls back
    to "liability" if no signal is found (most common clause type).
    """
    if requested != "auto":
        return requested
    from backend.corpus.chunker import _classify_chunk
    detected = _classify_chunk(text)
    if detected == "other":
        detected = "liability"  # safest fallback
    logger.info(f"Auto-detected clause type: {detected!r}")
    return detected


class BenchmarkRequest(BaseModel):
    text: str = Field(min_length=30, description="Clause text to benchmark against the market")
    clause_type: str = Field(default="auto", description="Clause category, or 'auto' to detect from text")


@app.post("/benchmark", response_model=BenchmarkResult, tags=["Benchmarking"],
           dependencies=[Security(_verify_api_key)])
@limiter.limit("10/minute")
def benchmark_clause(request: Request, body: BenchmarkRequest):
    """
    Benchmark a contract clause against real SEC EDGAR filings.

    Pass `clause_type: "auto"` (default) to auto-detect from the text using
    keyword-density classification. Or specify explicitly: liability, termination,
    payment, confidentiality, ip, governing_law.
    """
    clause_type = _resolve_clause_type(body.text, body.clause_type)
    logger.info(
        f"Benchmarking clause | type={clause_type!r} | chars={len(body.text)}"
    )
    try:
        from backend.benchmarking.benchmarker import benchmark_clause as _benchmark
        result = _benchmark(body.text, clause_type=clause_type)
        return result
    except Exception as e:
        logger.exception("Benchmarking failed")
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


class RedlineRequest(BaseModel):
    text: str = Field(min_length=30, description="Clause text to generate redlines for")
    clause_type: str = Field(default="auto", description="Clause category, or 'auto' to detect from text")


@app.post("/redline", response_model=RedlineResult, tags=["Redline"],
           dependencies=[Security(_verify_api_key)])
@limiter.limit("10/minute")
def generate_redlines(request: Request, body: RedlineRequest):
    """
    Generate grounded redline suggestions for a contract clause.

    Pass `clause_type: "auto"` (default) to auto-detect from the text.
    Runs the full pipeline: benchmark against EDGAR market data, then generate
    edit suggestions citing specific market statistics and real SEC filings.
    """
    clause_type = _resolve_clause_type(body.text, body.clause_type)
    logger.info(
        f"Generating redlines | type={clause_type!r} | chars={len(body.text)}"
    )
    try:
        from backend.benchmarking.benchmarker import benchmark_clause as _benchmark
        from backend.redline.generator import generate_redlines as _generate

        benchmark = _benchmark(body.text, clause_type=clause_type)
        result = _generate(body.text, benchmark)
        return result
    except Exception as e:
        logger.exception("Redline generation failed")
        raise HTTPException(status_code=500, detail=f"Redline error: {str(e)}")


@app.exception_handler(422)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "details": str(exc)},
    )


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
