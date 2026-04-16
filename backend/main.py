"""
Legal Risk Mapper — FastAPI Backend
Endpoints:
  POST /analyze  → analyze text for legal risks
  GET  /health   → service health check
"""
import io
import logging
from collections import Counter
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.models.schemas import (
    AnalyzeRequest, AnalyzeResponse, HealthResponse, RiskItem
)
from backend.services.risk_analyzer import analyze_risks, compute_overall_risk

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("lrm")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Legal Risk Mapper",
    description="NLP-powered legal risk analysis for contracts, policies, and business text.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Tighten in production
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
def analyze_text(request: AnalyzeRequest):
    """
    Analyze raw text for legal risks.
    Returns categorized risks with severity scores and explanations.
    """
    logger.info(f"Analyzing text | title={request.document_title!r} | chars={len(request.text)}")
    try:
        risks = analyze_risks(request.text)
        return _build_response(risks, request.document_title)
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.post("/analyze/upload", response_model=AnalyzeResponse, tags=["Analysis"])
async def analyze_upload(
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
