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


# ── Payment Extraction ───────────────────────────────────────────────────────

class LateFeeInfo(BaseModel):
    """Structured representation of late payment penalties."""
    has_late_fee: bool = Field(default=False, description="Whether overdue payments incur a penalty or interest")
    late_fee_type: Optional[str] = Field(default=None, description="Type: 'flat_fee', 'percentage', 'interest_rate', 'other'")
    late_fee_amount: Optional[str] = Field(default=None, description="The fee/rate, e.g. '1.5% per month', '$50 per invoice', 'lesser of 1.5%/month or maximum legal rate'")
    late_fee_source_text: Optional[str] = Field(default=None, description="Exact quote about late fees or interest")


class PaymentExtraction(BaseModel):
    """
    Structured extraction from a payment clause.

    Every field that captures a factual claim about the clause MUST have a
    corresponding source_text field with the exact quote from the contract.
    """
    # Payment terms (net days)
    has_payment_terms: Optional[bool] = Field(default=None, description="True if the clause specifies a payment deadline (e.g. net-30)")
    payment_days: Optional[int] = Field(default=None, description="Number of days to pay after invoice (e.g. 30, 45, 60)")
    payment_terms_source_text: Optional[str] = Field(default=None, description="Exact quote about payment terms/deadline")

    # Late payment penalty / interest
    late_fee: LateFeeInfo = Field(default_factory=LateFeeInfo)

    # Price escalation / unilateral increase
    has_price_escalation: Optional[bool] = Field(default=None, description="True if provider can increase prices unilaterally or at renewal")
    price_escalation_source_text: Optional[str] = Field(default=None, description="Exact quote about price changes")

    # Non-refundable payments
    has_non_refundable: Optional[bool] = Field(default=None, description="True if payments are stated as non-refundable")
    non_refundable_source_text: Optional[str] = Field(default=None, description="Exact quote about non-refundable payments")

    # Minimum commitment / minimum spend
    has_minimum_commitment: Optional[bool] = Field(default=None, description="True if there is a minimum purchase, spend, or volume commitment")
    minimum_commitment_amount: Optional[str] = Field(default=None, description="The minimum amount or formula, e.g. '$50,000 annually', '1,000 units per quarter'")
    minimum_commitment_source_text: Optional[str] = Field(default=None, description="Exact quote about minimum commitments")

    # Invoice frequency
    invoice_frequency: Optional[str] = Field(default=None, description="How often invoices are issued: 'monthly', 'quarterly', 'annually', 'upfront', 'upon_delivery'")
    invoice_frequency_source_text: Optional[str] = Field(default=None, description="Exact quote about invoicing schedule")

    # Payment dispute process
    has_dispute_process: Optional[bool] = Field(default=None, description="True if the clause provides a process for disputing invoices")
    dispute_process_source_text: Optional[str] = Field(default=None, description="Exact quote about the dispute process")

    # Right of setoff
    has_right_of_setoff: Optional[bool] = Field(default=None, description="True if a party can offset amounts owed against payments due")
    setoff_source_text: Optional[str] = Field(default=None, description="Exact quote about setoff rights")

    # Overall confidence
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Model's confidence in the extraction (0-1)")


# ── Confidentiality Extraction ───────────────────────────────────────────────

class ConfidentialityExtraction(BaseModel):
    """
    Structured extraction from a confidentiality / NDA clause.

    Every field that captures a factual claim about the clause MUST have a
    corresponding source_text field with the exact quote from the contract.
    """
    # Definition scope — how broadly is "Confidential Information" defined?
    has_broad_definition: Optional[bool] = Field(default=None, description="True if the definition of Confidential Information is broad (e.g. 'all information disclosed', 'any and all information')")
    definition_source_text: Optional[str] = Field(default=None, description="Exact quote defining Confidential Information")

    # Standard exclusions (public domain, independent development, prior knowledge, compelled disclosure)
    has_standard_exclusions: Optional[bool] = Field(default=None, description="True if standard carve-outs are present (publicly available, independently developed, already known, legally compelled)")
    exclusions: list[str] = Field(default_factory=list, description="List of exclusion categories, e.g. ['public domain', 'independent development', 'prior knowledge', 'compelled disclosure']")
    exclusions_source_text: Optional[str] = Field(default=None, description="Exact quote listing the exclusions")

    # Duration of confidentiality obligations
    has_duration: Optional[bool] = Field(default=None, description="True if the clause specifies how long confidentiality obligations last")
    duration_years: Optional[int] = Field(default=None, description="Number of years obligations last (null if perpetual or unspecified)")
    is_perpetual: Optional[bool] = Field(default=None, description="True if obligations are stated to last indefinitely or in perpetuity")
    duration_source_text: Optional[str] = Field(default=None, description="Exact quote about duration")

    # Permitted disclosures (employees, advisors, affiliates)
    has_permitted_disclosures: Optional[bool] = Field(default=None, description="True if the clause permits disclosure to certain categories (employees, advisors, affiliates, subcontractors)")
    permitted_recipients: list[str] = Field(default_factory=list, description="List of permitted recipient categories, e.g. ['employees', 'advisors', 'affiliates', 'legal counsel']")
    permitted_disclosures_source_text: Optional[str] = Field(default=None, description="Exact quote about permitted disclosures")

    # Return or destruction of confidential information
    has_return_or_destroy: Optional[bool] = Field(default=None, description="True if the clause requires return or destruction of Confidential Information upon termination or request")
    return_destroy_source_text: Optional[str] = Field(default=None, description="Exact quote about return/destruction obligations")

    # Residuals clause (right to use general knowledge retained in memory)
    has_residuals_clause: Optional[bool] = Field(default=None, description="True if a residuals clause permits use of ideas retained in unaided memory")
    residuals_source_text: Optional[str] = Field(default=None, description="Exact quote about residuals")

    # Injunctive relief (right to seek injunction for breach)
    has_injunctive_relief: Optional[bool] = Field(default=None, description="True if the clause states that breach entitles the discloser to injunctive or equitable relief")
    injunctive_relief_source_text: Optional[str] = Field(default=None, description="Exact quote about injunctive relief")

    # Mutual vs one-sided
    is_mutual: Optional[bool] = Field(default=None, description="True if confidentiality obligations apply equally to both parties")
    mutuality_source_text: Optional[str] = Field(default=None, description="Exact quote showing mutuality or one-sidedness")

    # Overall confidence
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Model's confidence in the extraction (0-1)")


# ── Mapping for future categories ────────────────────────────────────────────

EXTRACTION_SCHEMAS = {
    "liability": LiabilityExtraction,
    "termination": TerminationExtraction,
    "payment": PaymentExtraction,
    "confidentiality": ConfidentialityExtraction,
}
