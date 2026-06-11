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
import sys
from collections import Counter
from contextlib import asynccontextmanager
from typing import Optional

import structlog

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from backend.services.circuit_breaker import groq_breaker
from backend.routers.metrics_router import metrics_router
from backend.routers.auth_router import auth_router
from backend.routers.compare_router import compare_router
from backend.auth.middleware import get_current_user, require_role
from backend.benchmarking.schemas import BenchmarkResult
from backend.redline.schemas import RedlineResult

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("lrm")

# ── Rate Limiting ────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan (startup/shutdown) ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm every model at startup so the FIRST real request isn't paying the
    cold-load cost. Without this, the initial /analyze call eats the full
    sentence-transformers load, spaCy load, classifier-pickle load, AND the
    first torch inference (JIT) — easily 10–30s. Warming here moves all of that
    to boot time and makes the first user request as fast as the rest."""
    import time as _t
    t0 = _t.monotonic()

    # 1. Semantic layer (embedding model + spaCy + canonical embeddings)
    try:
        from backend.services.semantic_analyzer import warmup
        ready = warmup()
        logger.info(f"Semantic layer {'READY' if ready else 'DISABLED (regex-only mode)'}")
    except Exception as e:
        logger.warning(f"Semantic warmup failed: {e}")

    # 2. ML risk classifier (pickle bundle) + a real forward pass so the
    #    expensive first torch inference happens now, not on request #1.
    try:
        from backend.services.risk_analyzer import analyze_risks
        analyze_risks("This Agreement shall be governed by the laws of the State of Delaware.")
        logger.info("Risk classifier WARM (model loaded + first inference primed)")
    except Exception as e:
        logger.warning(f"Classifier warmup failed: {e}")

    logger.info(f"Startup warmup complete in {_t.monotonic() - t0:.1f}s")
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

_cors_origins = [
    o.strip() for o in
    os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
# A wildcard origin cannot be combined with credentials — the browser rejects
# it and it would expose authenticated responses to any site. If "*" is
# configured, drop credentials so the wildcard is at least safe for public,
# unauthenticated use rather than silently broken.
_allow_credentials = "*" not in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(auth_router)
app.include_router(compare_router)

# Structured logging + request tracing
from backend.middleware.trace import TraceMiddleware  # noqa: E402
app.add_middleware(TraceMiddleware)

# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


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
        "circuit_breaker": {
            "llm": groq_breaker.status(),
        },
    })


@app.post("/cache/clear", tags=["Meta"], dependencies=[Depends(require_role("admin"))])
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


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Analysis"],
           dependencies=[Depends(get_current_user)])
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


def _extract_text_from_upload(filename: str, content: bytes) -> tuple[str, str]:
    """Extract plain text from an uploaded file (txt, md, or pdf).

    Returns:
        (text, extraction_method) where method is "digital", "ocr", or "text".
    """
    if filename.lower().endswith(".pdf"):
        try:
            from backend.services.ocr import extract_text_from_pdf
            return extract_text_from_pdf(content)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not extract text from PDF: {e}. Try saving as .txt."
            )
    try:
        return content.decode("utf-8"), "text"
    except UnicodeDecodeError:
        return content.decode("latin-1"), "text"


_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_upload(filename: str, content: bytes) -> None:
    """Shared upload guard: extension allowlist, size cap, and magic-byte check.

    Raises HTTPException (400/413) on any violation. Applied before any parsing
    so an attacker cannot trigger PDF/text decoding on an oversized or spoofed
    payload (memory-exhaustion DoS).
    """
    allowed = (".txt", ".md", ".pdf")
    fname_lower = filename.lower() if filename else ""
    if not fname_lower.endswith(allowed):
        raise HTTPException(status_code=400, detail="Only .txt, .md, and .pdf files are supported.")

    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content)} bytes). Maximum allowed is {_MAX_UPLOAD_BYTES} bytes (10 MB).",
        )

    if fname_lower.endswith(".pdf"):
        if not content.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400,
                detail="File does not appear to be a valid PDF (missing %PDF header).",
            )
    else:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content.decode("latin-1")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="File content is not valid text (UTF-8 or Latin-1).",
                )


@app.post("/analyze/upload", response_model=AnalyzeResponse, tags=["Analysis"],
           dependencies=[Depends(get_current_user)])
@limiter.limit("10/minute")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    document_title: Optional[str] = Form(default=None),
):
    """
    Analyze an uploaded file (.txt, .md, or .pdf) for legal risks.
    PDF text is extracted with PyMuPDF.

    Hardening:
      - 10 MB file size limit (HTTP 413)
      - MIME / magic-byte validation (HTTP 400)
      - Stricter rate limit: 10 requests/minute
    """
    content = await file.read()

    # ── Audit log every upload attempt ────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        "Upload received | filename=%s | size=%d | content_type=%s | client_ip=%s",
        file.filename, len(content), file.content_type, client_ip,
    )

    # ── Extension allowlist, size cap, magic-byte validation ──────────────
    _validate_upload(file.filename, content)

    text, extraction_method = _extract_text_from_upload(file.filename, content)

    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Uploaded file appears to be empty or too short.")

    title = document_title or file.filename
    logger.info(f"Analyzing uploaded file | title={title!r} | chars={len(text)} | method={extraction_method}")

    try:
        risks = analyze_risks(text)
        response = _build_response(risks, title)
        return JSONResponse(
            content=response.model_dump(mode="json"),
            headers={"X-Extraction-Method": extraction_method},
        )
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
    content = await file.read()
    _validate_upload(file.filename, content)
    text, extraction_method = _extract_text_from_upload(file.filename, content)
    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="File appears empty or too short.")
    return {"text": text, "char_count": len(text), "extraction_method": extraction_method}


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


import errno as _errno
import socket as _socket

_CORPUS_CONN_HINTS = (
    "Name or service not known", "getaddrinfo", "Could not resolve",
    "Temporary failure in name resolution", "nodename nor servname",
    "Failed to establish a new connection", "Max retries exceeded",
    "Connection refused", "[Errno -2]", "[Errno -3]", "[Errno 8]",
)


def _is_corpus_unreachable(exc: BaseException) -> bool:
    """True when an exception looks like the market-corpus DB (Supabase) being
    unreachable — DNS failure, refused/timed-out connection — rather than a real
    application bug. Walks the cause/context chain so wrapped errors are caught."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, _socket.gaierror):
            return True
        if isinstance(cur, OSError) and cur.errno in (
            _errno.ENETUNREACH, _errno.ECONNREFUSED, _errno.ETIMEDOUT, -2, -3,
        ):
            return True
        if any(h in str(cur) for h in _CORPUS_CONN_HINTS):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


_CORPUS_DOWN_DETAIL = (
    "Market corpus database is unreachable. The benchmark and redline features "
    "read the EDGAR clause corpus from Supabase, and the configured SUPABASE_URL "
    "host did not resolve. Configure a reachable Supabase project (see README → "
    "Local Development) to enable these features. Risk analysis is unaffected."
)


class BenchmarkRequest(BaseModel):
    text: str = Field(min_length=30, description="Clause text to benchmark against the market")
    clause_type: str = Field(default="auto", description="Clause category, or 'auto' to detect from text")


@app.post("/benchmark", response_model=BenchmarkResult, tags=["Benchmarking"],
           dependencies=[Depends(require_role("pro"))])
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
        if _is_corpus_unreachable(e):
            raise HTTPException(status_code=503, detail=_CORPUS_DOWN_DETAIL)
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


class RedlineRequest(BaseModel):
    text: str = Field(min_length=30, description="Clause text to generate redlines for")
    clause_type: str = Field(default="auto", description="Clause category, or 'auto' to detect from text")


@app.post("/redline", response_model=RedlineResult, tags=["Redline"],
           dependencies=[Depends(require_role("pro"))])
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
        if _is_corpus_unreachable(e):
            raise HTTPException(status_code=503, detail=_CORPUS_DOWN_DETAIL)
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
