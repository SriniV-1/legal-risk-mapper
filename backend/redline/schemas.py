"""
Redline Schemas
───────────────
Response models for grounded redline generation.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RedlineSuggestion(BaseModel):
    """A single contract edit suggestion grounded in market data."""
    original_text: str = Field(description="Exact text from the original clause to be changed")
    proposed_text: str = Field(description="Suggested replacement text")
    justification: str = Field(description="Why this edit is suggested, citing market data")
    market_citation: str = Field(
        default="",
        description="Specific market stat cited, e.g. '72% of similar clauses include mutual caps'"
    )
    risk_addressed: str = Field(
        default="",
        description="The risk or gap this edit addresses"
    )
    priority: str = Field(
        default="medium",
        description="Suggestion priority: high, medium, low"
    )


class RedlineResult(BaseModel):
    """Complete redline output for a clause."""
    clause_type: str
    original_clause: str
    suggestions: list[RedlineSuggestion] = Field(default_factory=list)
    summary: str = Field(default="", description="High-level summary of suggested changes")
    model_used: str = Field(default="")
