"""
Benchmarking Schemas
────────────────────
Response models for the market benchmarking endpoint.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class FieldDistribution(BaseModel):
    """Distribution of a boolean or categorical field across the market sample."""
    field_name: str
    true_count: int = 0
    false_count: int = 0
    total: int = 0
    true_pct: float = 0.0

    # For categorical fields like cap_type
    value_counts: dict[str, int] = Field(default_factory=dict)


class CitedExample(BaseModel):
    """A real-world clause cited as a market comparison."""
    contract_id: str
    company: str = ""
    filed_date: Optional[str] = None
    exhibit_url: str = ""
    text_snippet: str = Field(description="First ~300 chars of the clause")
    similarity: float
    extracted_data: Optional[dict] = None


class BenchmarkResult(BaseModel):
    """Complete market benchmark for a single clause."""
    clause_type: str
    user_extraction: Optional[dict] = Field(
        default=None, description="Structured extraction of the user's uploaded clause"
    )
    sample_size: int = Field(description="Number of similar clauses in the market sample")
    field_distributions: dict[str, FieldDistribution] = Field(
        default_factory=dict,
        description="Market distribution for each key field",
    )
    cited_examples: list[CitedExample] = Field(
        default_factory=list,
        description="Top-5 most similar real-world clauses with metadata",
    )
    user_percentiles: dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Where the user's clause falls in the market distribution per field (0-100)",
    )
