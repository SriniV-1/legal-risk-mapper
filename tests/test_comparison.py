"""
Tests for the multi-document comparison endpoint (POST /compare).
"""
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend.main import app
from backend.extraction.schemas import LiabilityExtraction, LiabilityCapInfo, ConsequentialDamagesInfo


client = TestClient(app)

# ── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_LIABILITY_TEXT_A = (
    "The total aggregate liability of Provider under this Agreement shall not "
    "exceed the fees paid by Customer in the twelve months preceding the claim. "
    "This limitation applies equally to both parties. Neither party shall be "
    "liable for any indirect, incidental, or consequential damages."
)

SAMPLE_LIABILITY_TEXT_B = (
    "Provider's liability shall be unlimited. Customer assumes all risk. "
    "Provider makes no warranties express or implied. Consequential damages "
    "are not excluded under this agreement."
)


def _make_extraction_a():
    """Return a LiabilityExtraction representing a protective clause."""
    return LiabilityExtraction(
        liability_cap=LiabilityCapInfo(
            has_cap=True,
            cap_amount="fees paid in prior 12 months",
            cap_type="fees_paid_period",
        ),
        is_mutual=True,
        has_carve_outs=False,
        consequential_damages=ConsequentialDamagesInfo(
            excluded=True,
            exclusion_is_mutual=True,
        ),
        has_indemnification=False,
        has_warranty_disclaimer=False,
        extraction_confidence=0.9,
    )


def _make_extraction_b():
    """Return a LiabilityExtraction representing a less protective clause."""
    return LiabilityExtraction(
        liability_cap=LiabilityCapInfo(
            has_cap=False,
        ),
        is_mutual=False,
        has_carve_outs=False,
        consequential_damages=ConsequentialDamagesInfo(
            excluded=False,
        ),
        has_indemnification=False,
        has_warranty_disclaimer=True,
        extraction_confidence=0.85,
    )


def _mock_extract_clause(text, clause_type="liability", **kwargs):
    """Return different mock extractions based on text content."""
    if "twelve months" in text or "Text A" in text:
        return _make_extraction_a()
    elif "unlimited" in text or "Text B" in text:
        return _make_extraction_b()
    # Default fallback
    return _make_extraction_a()


# ── Tests ───────────────────────────────────────────────────────────────────


@patch("backend.comparison.comparator.extract_clause", side_effect=_mock_extract_clause)
def test_compare_two_contracts(mock_extract):
    """Two contracts should produce a valid comparison with field diffs."""
    resp = client.post("/compare", json={
        "contracts": [
            {"name": "Vendor A", "text": SAMPLE_LIABILITY_TEXT_A},
            {"name": "Vendor B", "text": SAMPLE_LIABILITY_TEXT_B},
        ],
        "clause_type": "liability",
    })
    assert resp.status_code == 200
    data = resp.json()

    # Structure checks
    assert "contracts" in data
    assert "field_comparison" in data
    assert "recommendation" in data
    assert len(data["contracts"]) == 2

    # Verify contract results
    assert data["contracts"][0]["name"] == "Vendor A"
    assert data["contracts"][1]["name"] == "Vendor B"
    assert data["contracts"][0]["extraction"] is not None
    assert data["contracts"][1]["extraction"] is not None

    # Field comparison should include known liability fields
    fc = data["field_comparison"]
    assert "has_cap" in fc
    assert "is_mutual" in fc

    # has_cap should differ (A=True, B=False)
    assert fc["has_cap"]["Vendor A"] is True
    assert fc["has_cap"]["Vendor B"] is False
    assert fc["has_cap"]["differs"] is True

    # Recommendation should mention one of the vendors
    assert "Vendor A" in data["recommendation"] or "Vendor B" in data["recommendation"]


@patch("backend.comparison.comparator.extract_clause", side_effect=_mock_extract_clause)
def test_compare_response_structure(mock_extract):
    """Verify the full response structure matches the schema."""
    resp = client.post("/compare", json={
        "contracts": [
            {"name": "Contract 1", "text": SAMPLE_LIABILITY_TEXT_A},
            {"name": "Contract 2", "text": SAMPLE_LIABILITY_TEXT_B},
        ],
        "clause_type": "liability",
    })
    assert resp.status_code == 200
    data = resp.json()

    # Top-level keys
    assert set(data.keys()) == {"contracts", "field_comparison", "recommendation"}

    # Each contract result has name, extraction, percentiles
    for contract in data["contracts"]:
        assert "name" in contract
        assert "extraction" in contract
        assert "percentiles" in contract

    # field_comparison values have contract names + differs flag
    for field_name, field_data in data["field_comparison"].items():
        assert "Contract 1" in field_data
        assert "Contract 2" in field_data
        assert "differs" in field_data

    # recommendation is a non-empty string
    assert isinstance(data["recommendation"], str)
    assert len(data["recommendation"]) > 0


def test_compare_invalid_clause_type():
    """Invalid clause_type should return 400."""
    resp = client.post("/compare", json={
        "contracts": [
            {"name": "A", "text": SAMPLE_LIABILITY_TEXT_A},
            {"name": "B", "text": SAMPLE_LIABILITY_TEXT_B},
        ],
        "clause_type": "invalid_type",
    })
    assert resp.status_code == 400
    assert "Invalid clause_type" in resp.json()["detail"]


def test_compare_too_few_contracts():
    """Submitting 1 contract should return 400."""
    resp = client.post("/compare", json={
        "contracts": [
            {"name": "Solo", "text": SAMPLE_LIABILITY_TEXT_A},
        ],
        "clause_type": "liability",
    })
    assert resp.status_code == 400
    assert "At least 2" in resp.json()["detail"]


def test_compare_too_many_contracts():
    """Submitting 6 contracts should return 400."""
    contracts = [
        {"name": f"Contract {i}", "text": SAMPLE_LIABILITY_TEXT_A}
        for i in range(6)
    ]
    resp = client.post("/compare", json={
        "contracts": contracts,
        "clause_type": "liability",
    })
    assert resp.status_code == 400
    assert "At most 5" in resp.json()["detail"]


@patch("backend.comparison.comparator.extract_clause", return_value=None)
def test_compare_extraction_failure(mock_extract):
    """When extraction fails for all contracts, response should still be valid."""
    resp = client.post("/compare", json={
        "contracts": [
            {"name": "A", "text": SAMPLE_LIABILITY_TEXT_A},
            {"name": "B", "text": SAMPLE_LIABILITY_TEXT_B},
        ],
        "clause_type": "liability",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["contracts"][0]["extraction"] is None
    assert data["contracts"][1]["extraction"] is None
    assert "failed" in data["recommendation"].lower() or "could not" in data["recommendation"].lower()


@patch("backend.comparison.comparator.extract_clause", side_effect=_mock_extract_clause)
def test_compare_field_differs_flag(mock_extract):
    """Fields that are the same across contracts should have differs=False."""
    resp = client.post("/compare", json={
        "contracts": [
            {"name": "A", "text": SAMPLE_LIABILITY_TEXT_A},
            {"name": "B", "text": SAMPLE_LIABILITY_TEXT_B},
        ],
        "clause_type": "liability",
    })
    data = resp.json()
    fc = data["field_comparison"]

    # has_carve_outs is False for both → differs should be False
    assert fc["has_carve_outs"]["A"] is False
    assert fc["has_carve_outs"]["B"] is False
    assert fc["has_carve_outs"]["differs"] is False
