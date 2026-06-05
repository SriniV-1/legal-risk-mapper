"""
Comparison Schemas
──────────────────
Pydantic models for the multi-document comparison endpoint.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ContractInput(BaseModel):
    """A single contract to include in a comparison."""
    name: str = Field(description="Label for this contract, e.g. 'Vendor A'")
    text: str = Field(min_length=30, description="Clause text to extract and compare")


class ContractResult(BaseModel):
    """Extraction result for a single contract in the comparison."""
    name: str
    extraction: Optional[dict] = Field(
        default=None,
        description="Structured extraction of the clause (None if extraction failed)",
    )
    percentiles: dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Market percentile for each boolean field (empty if benchmarking unavailable)",
    )


class CompareRequest(BaseModel):
    """Request body for the /compare endpoint."""
    contracts: list[ContractInput] = Field(
        description="2-5 contracts to compare",
    )
    clause_type: str = Field(
        description="Clause category: liability, termination, payment, confidentiality, ip, governing_law",
    )


class CompareResponse(BaseModel):
    """Response from the /compare endpoint."""
    contracts: list[ContractResult] = Field(
        description="Per-contract extraction results with optional market percentiles",
    )
    field_comparison: dict = Field(
        default_factory=dict,
        description="Field-by-field comparison across all contracts",
    )
    recommendation: str = Field(
        default="",
        description="Summary of which contract offers more favorable terms",
    )
