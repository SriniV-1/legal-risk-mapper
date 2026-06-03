"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum


class RiskSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class RiskType(str, Enum):
    COMPLIANCE = "Compliance Risk"
    LIABILITY = "Liability Risk"
    PRIVACY = "Privacy/Data Risk"
    FINANCIAL = "Financial Risk"
    AMBIGUITY = "Contractual Ambiguity"


class RiskItem(BaseModel):
    risk_type: str
    severity: RiskSeverity
    text_snippet: str
    explanation: str
    score: int = Field(ge=0, le=100, description="Risk score 0-100 (0-39 Low, 40-69 Medium, 70-100 High)")
    feature_scores: Optional[Dict[str, int]] = Field(default=None, description="Per-feature sub-scores: liability, financial, compliance, ambiguity, enforceability")
    keywords_matched: List[str] = []
    # Hybrid-layer metadata (v2)
    sources: List[str] = Field(default_factory=list, description="Detection layers: regex / semantic")
    semantic_similarity: Optional[float] = Field(default=None, description="Raw cosine similarity (0-1) from the semantic layer")
    semantic_match_id: Optional[str] = Field(default=None, description="ID of the canonical clause matched semantically")
    clause_index: Optional[int] = Field(default=None, description="Index of the source clause in the segmented document")


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=10, description="Text to analyze for legal risks")
    document_title: Optional[str] = Field(default=None, description="Optional document title")


class AnalyzeResponse(BaseModel):
    document_title: Optional[str]
    total_risks: int
    risk_summary: dict  # {risk_type: count}
    severity_breakdown: dict  # {severity: count}
    risks: List[RiskItem]
    overall_risk_level: RiskSeverity
    analysis_notes: str


class HealthResponse(BaseModel):
    status: str
    version: str
    nlp_engine: str


class ReadyResponse(BaseModel):
    ready: bool
    checks: Dict[str, str]
