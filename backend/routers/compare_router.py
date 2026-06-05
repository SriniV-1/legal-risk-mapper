"""
Compare Router
──────────────
POST /compare — compare 2-5 contract clauses side by side.
"""
from fastapi import APIRouter, HTTPException

from backend.comparison.schemas import CompareRequest, CompareResponse
from backend.comparison.comparator import compare_contracts
from backend.extraction.schemas import EXTRACTION_SCHEMAS

compare_router = APIRouter()


@compare_router.post("/compare", response_model=CompareResponse, tags=["Comparison"])
def compare_clauses(body: CompareRequest):
    """
    Compare 2-5 contract clauses of the same type.

    Extracts structured data from each contract using the LLM extraction
    pipeline, then produces a field-by-field comparison and recommendation.
    """
    # Validate contract count
    if len(body.contracts) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 contracts are required for comparison.",
        )
    if len(body.contracts) > 5:
        raise HTTPException(
            status_code=400,
            detail="At most 5 contracts can be compared at once.",
        )

    # Validate clause type
    if body.clause_type not in EXTRACTION_SCHEMAS:
        valid = ", ".join(sorted(EXTRACTION_SCHEMAS.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid clause_type '{body.clause_type}'. Valid types: {valid}.",
        )

    contracts = [{"name": c.name, "text": c.text} for c in body.contracts]
    result = compare_contracts(contracts, body.clause_type)
    return result
