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


# ── Termination Extraction ───────────────────────────────────────────────────

class CurePeriodInfo(BaseModel):
    """Structured representation of a cure/remedy period."""
    has_cure_period: bool = Field(default=False, description="Whether the clause provides a period to cure a breach before termination")
    cure_days: Optional[int] = Field(default=None, description="Number of days to cure (e.g. 30)")
    cure_source_text: Optional[str] = Field(default=None, description="Exact quote describing the cure period")


class NoticePeriodInfo(BaseModel):
    """Structured representation of a termination notice period."""
    has_notice_period: bool = Field(default=False, description="Whether advance notice is required before termination")
    notice_days: Optional[int] = Field(default=None, description="Number of days of advance notice required (e.g. 30, 60, 90)")
    notice_source_text: Optional[str] = Field(default=None, description="Exact quote describing the notice requirement")


class TerminationExtraction(BaseModel):
    """
    Structured extraction from a termination clause.

    Every field that captures a factual claim about the clause MUST have a
    corresponding source_text field with the exact quote from the contract.
    """
    # Termination for cause (material breach)
    has_termination_for_cause: Optional[bool] = Field(default=None, description="True if either party can terminate for the other's material breach or default")
    termination_for_cause_source_text: Optional[str] = Field(default=None, description="Exact quote about termination for cause")

    # Termination for convenience (without cause)
    has_termination_for_convenience: Optional[bool] = Field(default=None, description="True if a party can terminate without cause")
    convenience_termination_who: Optional[str] = Field(default=None, description="Who can terminate for convenience: 'either_party', 'provider_only', 'customer_only'")
    termination_for_convenience_source_text: Optional[str] = Field(default=None, description="Exact quote about termination for convenience")

    # Cure period
    cure_period: CurePeriodInfo = Field(default_factory=CurePeriodInfo)

    # Notice period
    notice_period: NoticePeriodInfo = Field(default_factory=NoticePeriodInfo)

    # Auto-renewal
    has_auto_renewal: Optional[bool] = Field(default=None, description="True if the agreement auto-renews at end of term")
    auto_renewal_source_text: Optional[str] = Field(default=None, description="Exact quote about auto-renewal")

    # Survival clauses
    has_survival_clause: Optional[bool] = Field(default=None, description="True if specific provisions survive termination")
    surviving_sections: list[str] = Field(default_factory=list, description="List of sections/provisions that survive, e.g. ['confidentiality', 'limitation of liability', 'indemnification']")
    survival_source_text: Optional[str] = Field(default=None, description="Exact quote listing survival provisions")

    # Post-termination obligations
    has_post_termination_obligations: Optional[bool] = Field(default=None, description="True if there are obligations after termination (data return, transition, wind-down)")
    post_termination_obligations: list[str] = Field(default_factory=list, description="List of obligations, e.g. ['data return', 'data deletion', 'transition assistance', 'final payment']")
    post_termination_source_text: Optional[str] = Field(default=None, description="Exact quote about post-termination obligations")

    # Termination fee / early termination penalty
    has_termination_fee: Optional[bool] = Field(default=None, description="True if early termination incurs a fee or penalty")
    termination_fee_amount: Optional[str] = Field(default=None, description="The fee amount or formula, e.g. 'remaining contract value', '50% of remaining fees'")
    termination_fee_source_text: Optional[str] = Field(default=None, description="Exact quote about the termination fee")

    # Overall confidence
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Model's confidence in the extraction (0-1)")


# ── Mapping for future categories ────────────────────────────────────────────

EXTRACTION_SCHEMAS = {
    "liability": LiabilityExtraction,
    "termination": TerminationExtraction,
}
