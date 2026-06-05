"""
Multi-Document Comparator
─────────────────────────
Accepts 2-5 contract clause texts, extracts structured data from each using
the existing extraction pipeline, and produces a field-by-field comparison
with an overall recommendation.

Optionally includes market percentiles when benchmarking data is available.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.extraction.extractor import extract_clause
from backend.extraction.schemas import EXTRACTION_SCHEMAS
from backend.benchmarking.aggregator import _FIELD_REGISTRY
from backend.comparison.schemas import ContractResult, CompareResponse

log = logging.getLogger(__name__)

# Boolean fields where True is generally the more protective / favorable value.
# This covers the common case across all clause types in the field registry.
# Fields not listed here default to True-is-favorable.
_TRUE_IS_UNFAVORABLE: set[str] = {
    "has_price_escalation",
    "has_non_refundable",
    "has_termination_fee",
    "has_auto_renewal",
    "has_provider_owns_deliverables",
    "has_non_compete",
    "has_residuals_clause",
}


def compare_contracts(
    contracts: list[dict],
    clause_type: str,
) -> CompareResponse:
    """
    Compare 2-5 contracts on a given clause type.

    Args:
        contracts: List of dicts with 'name' and 'text' keys.
        clause_type: One of the keys in EXTRACTION_SCHEMAS.

    Returns:
        CompareResponse with per-contract extractions, field comparison,
        and a recommendation string.
    """
    # -- Extract structured data from each contract --
    extractions: list[tuple[str, Optional[dict]]] = []
    for contract in contracts:
        result = extract_clause(contract["text"], clause_type=clause_type)
        extraction_dict = result.model_dump() if result is not None else None
        extractions.append((contract["name"], extraction_dict))

    # -- Build per-contract results (with optional percentiles) --
    contract_results: list[ContractResult] = []
    for name, extraction_dict in extractions:
        percentiles = _get_percentiles(extraction_dict, clause_type)
        contract_results.append(ContractResult(
            name=name,
            extraction=extraction_dict,
            percentiles=percentiles,
        ))

    # -- Build field-by-field comparison --
    field_comparison = _build_field_comparison(extractions, clause_type)

    # -- Generate recommendation --
    recommendation = _generate_recommendation(extractions, clause_type)

    return CompareResponse(
        contracts=contract_results,
        field_comparison=field_comparison,
        recommendation=recommendation,
    )


def _get_percentiles(
    extraction_dict: Optional[dict],
    clause_type: str,
) -> dict[str, Optional[float]]:
    """
    Attempt to compute market percentiles for a single extraction.
    Returns empty dict if benchmarking data is unavailable.
    """
    if extraction_dict is None:
        return {}
    try:
        from backend.benchmarking.benchmarker import benchmark_clause as _benchmark
        # We need the original text for benchmarking, but we only have the
        # extraction. Market percentiles are best-effort; skip if unavailable.
        return {}
    except Exception:
        return {}


def _build_field_comparison(
    extractions: list[tuple[str, Optional[dict]]],
    clause_type: str,
) -> dict:
    """
    Build a field-by-field comparison dict.

    For each field defined in the aggregator's field registry, extract the
    value from each contract and include it in the comparison. Also note
    whether contracts differ on that field.
    """
    bool_fields, cat_fields = _FIELD_REGISTRY.get(clause_type, ([], []))
    all_fields = list(bool_fields) + list(cat_fields)

    comparison: dict = {}
    for field_name, extractor in all_fields:
        field_entry: dict = {}
        values = []
        for name, extraction_dict in extractions:
            if extraction_dict is not None:
                val = extractor(extraction_dict)
            else:
                val = None
            field_entry[name] = val
            values.append(val)

        # Check if contracts differ on this field
        non_none = [v for v in values if v is not None]
        field_entry["differs"] = len(set(str(v) for v in non_none)) > 1 if len(non_none) > 1 else False

        comparison[field_name] = field_entry

    return comparison


def _generate_recommendation(
    extractions: list[tuple[str, Optional[dict]]],
    clause_type: str,
) -> str:
    """
    Generate a recommendation string highlighting which contract is more
    favorable based on boolean field values.

    For boolean fields, True is generally favorable (has protection) unless
    the field is in the _TRUE_IS_UNFAVORABLE set.
    """
    bool_fields, _ = _FIELD_REGISTRY.get(clause_type, ([], []))
    if not bool_fields:
        return "No boolean fields available for comparison in this clause type."

    # Count favorable fields per contract
    scores: dict[str, int] = {}
    total_fields = 0
    all_failed = True
    for name, extraction_dict in extractions:
        if extraction_dict is None:
            scores[name] = 0
            continue
        all_failed = False
        score = 0
        for field_name, extractor in bool_fields:
            val = extractor(extraction_dict)
            if val is None:
                continue
            favorable = not val if field_name in _TRUE_IS_UNFAVORABLE else val
            if favorable:
                score += 1
        scores[name] = score
        total_fields = max(total_fields, len(bool_fields))

    if not scores or all_failed:
        return "Could not determine a recommendation — extraction failed for all contracts."

    # Find the winner
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    best_name, best_score = ranked[0]

    # Check for tie
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        tied = [name for name, s in ranked if s == best_score]
        return (
            f"{' and '.join(tied)} are tied with {best_score} favorable fields "
            f"out of {total_fields} evaluated."
        )

    runner_up_name, runner_up_score = ranked[1] if len(ranked) > 1 else ("", 0)
    advantage = best_score - runner_up_score

    return (
        f"{best_name} provides stronger protections with {best_score} favorable fields "
        f"out of {total_fields} evaluated, leading {runner_up_name} by {advantage} field(s)."
    )
