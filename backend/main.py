"""
Legal Risk Mapper — FastAPI Backend
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
    AnalyzeRequest, AnalyzeResponse, HealthResponse, RiskItem
)
from backend.services.risk_analyzer import analyze_risks, compute_overall_risk
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


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Legal Risk Mapper",
    description="NLP-powered legal risk analysis for contracts, policies, and business text.",
    version="1.0.0",
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


# ── Startup: warm the semantic layer ──────────────────────────────────────────
@app.on_event("startup")
def _warmup_semantic_layer():
    """
    Preload spaCy + sentence-transformers at boot so the first /analyze
    request doesn't pay the cold-start cost (~2-3s for the model load).
    Safe no-op if dependencies aren't installed.
    """
    try:
        from backend.services.semantic_analyzer import warmup
        ready = warmup()
        logger.info(f"Semantic layer {'READY' if ready else 'DISABLED (regex-only mode)'}")
    except Exception as e:
        logger.warning(f"Semantic warmup failed: {e}")


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

@app.get("/health", response_model=HealthResponse, tags=["Meta"])
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
    return HealthResponse(
        status="ok",
        version="2.0.0",
        nlp_engine=" + ".join(engine_parts),
    )


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
@limiter.limit("30/minute")
def analyze_text(request: Request, body: AnalyzeRequest):
    """
    Analyze raw text for legal risks.
    Returns categorized risks with severity scores and explanations.
    """
    logger.info(f"Analyzing text | title={body.document_title!r} | chars={len(body.text)}")
    try:
        risks = analyze_risks(body.text)
        return _build_response(risks, body.document_title)
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.post("/analyze/upload", response_model=AnalyzeResponse, tags=["Analysis"])
@limiter.limit("30/minute")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    document_title: Optional[str] = Form(default=None),
):
    """
    Analyze an uploaded .txt file for legal risks.
    PDF support can be added via pdfminer or PyMuPDF.
    """
    if not file.filename.endswith((".txt", ".md")):
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .md files are supported. For PDF, use /analyze with extracted text."
        )

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")  # Fallback encoding

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


class BenchmarkRequest(BaseModel):
    text: str = Field(min_length=30, description="Clause text to benchmark against the market")
    clause_type: str = Field(default="liability", description="Clause category (currently: liability)")


@app.post("/benchmark", response_model=BenchmarkResult, tags=["Benchmarking"],
           dependencies=[Security(_verify_api_key)])
@limiter.limit("10/minute")
def benchmark_clause(request: Request, body: BenchmarkRequest):
    """
    Benchmark a contract clause against real SEC EDGAR filings.

    Extracts structured data from the clause, retrieves similar clauses from the
    corpus, and computes market statistics (field distributions, percentiles,
    and 5 cited real-world examples).
    """
    logger.info(
        f"Benchmarking clause | type={body.clause_type!r} | chars={len(body.text)}"
    )
    try:
        from backend.benchmarking.benchmarker import benchmark_clause as _benchmark
        result = _benchmark(body.text, clause_type=body.clause_type)
        return result
    except Exception as e:
        logger.exception("Benchmarking failed")
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


class RedlineRequest(BaseModel):
    text: str = Field(min_length=30, description="Clause text to generate redlines for")
    clause_type: str = Field(default="liability", description="Clause category (currently: liability)")


@app.post("/redline", response_model=RedlineResult, tags=["Redline"],
           dependencies=[Security(_verify_api_key)])
@limiter.limit("10/minute")
def generate_redlines(request: Request, body: RedlineRequest):
    """
    Generate grounded redline suggestions for a contract clause.

    Runs the full pipeline: benchmark the clause against EDGAR market data,
    then generate edit suggestions citing specific market statistics and
    real SEC filings.
    """
    logger.info(
        f"Generating redlines | type={body.clause_type!r} | chars={len(body.text)}"
    )
    try:
        from backend.benchmarking.benchmarker import benchmark_clause as _benchmark
        from backend.redline.generator import generate_redlines as _generate

        benchmark = _benchmark(body.text, clause_type=body.clause_type)
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
