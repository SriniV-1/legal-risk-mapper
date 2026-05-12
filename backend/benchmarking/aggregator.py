"""
Market Aggregator
─────────────────
Computes market statistics from structured extractions of similar clauses.
Takes retrieved clause extractions and produces field-level distributions,
percentile ranks, and cited examples.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.benchmarking.schemas import (
    BenchmarkResult,
    CitedExample,
    FieldDistribution,
)

log = logging.getLogger(__name__)

# ── Per-category field definitions ──────────────────────────────────────────

# Liability
_LIABILITY_BOOL_FIELDS = [
    ("has_cap", lambda e: e.get("liability_cap", {}).get("has_cap")),
    ("is_mutual", lambda e: e.get("is_mutual")),
    ("has_carve_outs", lambda e: e.get("has_carve_outs")),
    ("consequential_excluded", lambda e: e.get("consequential_damages", {}).get("excluded")),
    ("has_indemnification", lambda e: e.get("has_indemnification")),
    ("has_warranty_disclaimer", lambda e: e.get("has_warranty_disclaimer")),
]

_LIABILITY_CAT_FIELDS = [
    ("cap_type", lambda e: e.get("liability_cap", {}).get("cap_type")),
]

# Termination
_TERMINATION_BOOL_FIELDS = [
    ("has_termination_for_cause", lambda e: e.get("has_termination_for_cause")),
    ("has_termination_for_convenience", lambda e: e.get("has_termination_for_convenience")),
    ("has_cure_period", lambda e: e.get("cure_period", {}).get("has_cure_period")),
    ("has_notice_period", lambda e: e.get("notice_period", {}).get("has_notice_period")),
    ("has_auto_renewal", lambda e: e.get("has_auto_renewal")),
    ("has_survival_clause", lambda e: e.get("has_survival_clause")),
    ("has_post_termination_obligations", lambda e: e.get("has_post_termination_obligations")),
    ("has_termination_fee", lambda e: e.get("has_termination_fee")),
]

_TERMINATION_CAT_FIELDS = [
    ("convenience_termination_who", lambda e: e.get("convenience_termination_who")),
]

# Registry: clause_type → (bool_fields, cat_fields)
_FIELD_REGISTRY = {
    "liability": (_LIABILITY_BOOL_FIELDS, _LIABILITY_CAT_FIELDS),
    "termination": (_TERMINATION_BOOL_FIELDS, _TERMINATION_CAT_FIELDS),
}


def _compute_bool_distribution(
    field_name: str,
    extractor,
    extractions: list[dict],
) -> FieldDistribution:
    """Compute true/false distribution for a boolean field."""
    true_count = 0
    false_count = 0
    total = 0

    for ext in extractions:
        val = extractor(ext)
        if val is None:
            continue
        total += 1
        if val:
            true_count += 1
        else:
            false_count += 1

    return FieldDistribution(
        field_name=field_name,
        true_count=true_count,
        false_count=false_count,
        total=total,
        true_pct=round(true_count / total * 100, 1) if total > 0 else 0.0,
    )


def _compute_cat_distribution(
    field_name: str,
    extractor,
    extractions: list[dict],
) -> FieldDistribution:
    """Compute value distribution for a categorical field."""
    value_counts: dict[str, int] = {}
    total = 0

    for ext in extractions:
        val = extractor(ext)
        if val is None:
            continue
        total += 1
        value_counts[val] = value_counts.get(val, 0) + 1

    return FieldDistribution(
        field_name=field_name,
        total=total,
        value_counts=value_counts,
    )


def _compute_percentile(user_val: Optional[bool], market_true_pct: float) -> Optional[float]:
    """
    Compute where the user's boolean value falls in the market.

    If user has X and market_true_pct% also have X, the user is in the majority.
    Returns a percentile (0-100) where higher = more protective/favorable.
    """
    if user_val is None:
        return None
    if user_val:
        # User has this protection; percentile = % of market that also has it
        return round(market_true_pct, 1)
    else:
        # User lacks this protection; percentile = % of market that also lacks it
        return round(100.0 - market_true_pct, 1)


def aggregate_market_stats(
    user_extraction: Optional[dict],
    market_extractions: list[dict],
    cited_clauses: list[dict],
    clause_type: str = "liability",
) -> BenchmarkResult:
    """
    Compute market benchmark statistics.

    Args:
        user_extraction: Structured extraction of the user's clause (or None).
        market_extractions: List of extracted_data dicts from similar corpus clauses.
        cited_clauses: List of dicts with clause metadata for citation
                       (contract_id, company, filed_date, exhibit_url, text, similarity, extracted_data).
        clause_type: The clause category being benchmarked.

    Returns:
        BenchmarkResult with distributions, percentiles, and cited examples.
    """
    # Look up field definitions for this clause type
    bool_fields, cat_fields = _FIELD_REGISTRY.get(
        clause_type, (_LIABILITY_BOOL_FIELDS, _LIABILITY_CAT_FIELDS)
    )

    # Compute field distributions
    distributions: dict[str, FieldDistribution] = {}

    for field_name, extractor in bool_fields:
        distributions[field_name] = _compute_bool_distribution(
            field_name, extractor, market_extractions,
        )

    for field_name, extractor in cat_fields:
        distributions[field_name] = _compute_cat_distribution(
            field_name, extractor, market_extractions,
        )

    # Compute user percentiles
    percentiles: dict[str, Optional[float]] = {}
    if user_extraction:
        for field_name, extractor in bool_fields:
            user_val = extractor(user_extraction)
            market_dist = distributions[field_name]
            percentiles[field_name] = _compute_percentile(user_val, market_dist.true_pct)
    else:
        for field_name, _ in bool_fields:
            percentiles[field_name] = None

    # Build cited examples (top 5)
    examples = []
    for c in cited_clauses[:5]:
        examples.append(CitedExample(
            contract_id=c["contract_id"],
            company=c.get("company", ""),
            filed_date=c.get("filed_date"),
            exhibit_url=c.get("exhibit_url", ""),
            text_snippet=c["text"][:300],
            similarity=c["similarity"],
            extracted_data=c.get("extracted_data"),
        ))

    return BenchmarkResult(
        clause_type=clause_type,
        user_extraction=user_extraction,
        sample_size=len(market_extractions),
        field_distributions=distributions,
        cited_examples=examples,
        user_percentiles=percentiles,
    )
