"""
Extraction Schemas
──────────────────
Per-category Pydantic models for structured clause extraction.
Every field has a companion `source_text` field for grounding provenance.

Working Agreement #2: Every extracted field MUST have a source_text quote.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Liability Extraction ─────────────────────────────────────────────────────

class LiabilityCapInfo(BaseModel):
    """Structured representation of a liability cap."""
    has_cap: bool = Field(default=False, description="Whether the clause contains an explicit liability cap")
    cap_amount: Optional[str] = Field(default=None, description="The cap amount or formula, e.g. '2x annual fees', '$1,000,000', 'total fees paid in prior 12 months'")
    cap_source_text: Optional[str] = Field(default=None, description="Exact quote from the clause describing the cap")
    cap_type: Optional[str] = Field(default=None, description="Type of cap: 'fixed_amount', 'multiple_of_fees', 'fees_paid_period', 'per_incident', 'other'")


class ConsequentialDamagesInfo(BaseModel):
    """Whether consequential/indirect damages are excluded."""
    excluded: Optional[bool] = Field(default=None, description="True if consequential damages are excluded")
    exclusion_source_text: Optional[str] = Field(default=None, description="Exact quote about consequential damages exclusion")
    exclusion_is_mutual: Optional[bool] = Field(default=None, description="True if the exclusion applies to both parties equally")


class LiabilityExtraction(BaseModel):
    """
    Structured extraction from a liability clause.

    Every field that captures a factual claim about the clause MUST have a
    corresponding source_text field with the exact quote from the contract.
    """
    # Liability cap
    liability_cap: LiabilityCapInfo = Field(default_factory=LiabilityCapInfo)

    # Mutuality
    is_mutual: Optional[bool] = Field(default=None, description="True if liability limitations apply equally to both parties")
    mutuality_source_text: Optional[str] = Field(default=None, description="Exact quote showing mutuality or lack thereof")

    # Carve-outs (exceptions to the liability cap)
    has_carve_outs: Optional[bool] = Field(default=None, description="True if there are exceptions/carve-outs to the liability cap")
    carve_outs: list[str] = Field(default_factory=list, description="List of carve-out categories, e.g. ['IP infringement', 'willful misconduct', 'confidentiality breach']")
    carve_outs_source_text: Optional[str] = Field(default=None, description="Exact quote listing the carve-outs")

    # Consequential damages
    consequential_damages: ConsequentialDamagesInfo = Field(default_factory=ConsequentialDamagesInfo)

    # Indemnification
    has_indemnification: Optional[bool] = Field(default=None, description="True if the clause includes indemnification obligations")
    indemnification_source_text: Optional[str] = Field(default=None, description="Exact quote about indemnification")

    # Warranty disclaimer
    has_warranty_disclaimer: Optional[bool] = Field(default=None, description="True if the clause includes warranty disclaimers (AS-IS, no warranties)")
    warranty_disclaimer_source_text: Optional[str] = Field(default=None, description="Exact quote of warranty disclaimer")

    # Overall confidence
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Model's confidence in the extraction (0-1)")


# ── Mapping for future categories ────────────────────────────────────────────

EXTRACTION_SCHEMAS = {
    "liability": LiabilityExtraction,
}
