"""
Tests for extraction schemas — validates Pydantic models, defaults, and constraints.
"""
import pytest
from pydantic import ValidationError

from backend.extraction.schemas import (
    LiabilityExtraction, TerminationExtraction, PaymentExtraction,
    ConfidentialityExtraction, IPExtraction, GoverningLawExtraction,
    EXTRACTION_SCHEMAS,
)


class TestSchemaRegistry:
    """All 6 clause types are registered."""

    def test_all_six_types_registered(self):
        assert set(EXTRACTION_SCHEMAS.keys()) == {
            "liability", "termination", "payment",
            "confidentiality", "ip", "governing_law",
        }

    def test_each_schema_is_base_model(self):
        for name, cls in EXTRACTION_SCHEMAS.items():
            assert hasattr(cls, "model_fields"), f"{name} schema is not a Pydantic model"


class TestLiabilitySchema:
    def test_defaults(self):
        ext = LiabilityExtraction()
        assert ext.liability_cap.has_cap is False
        assert ext.is_mutual is None
        assert ext.extraction_confidence == 0.0

    def test_full_extraction(self):
        ext = LiabilityExtraction(
            is_mutual=True,
            mutuality_source_text="Both parties agree...",
            has_carve_outs=True,
            carve_outs=["IP infringement", "willful misconduct"],
            has_indemnification=True,
            has_warranty_disclaimer=False,
            extraction_confidence=0.92,
        )
        assert ext.is_mutual is True
        assert len(ext.carve_outs) == 2
        assert ext.extraction_confidence == 0.92

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            LiabilityExtraction(extraction_confidence=1.5)


class TestTerminationSchema:
    def test_defaults(self):
        ext = TerminationExtraction()
        assert ext.has_termination_for_cause is None
        assert ext.cure_period.has_cure_period is False
        assert ext.notice_period.has_notice_period is False

    def test_nested_cure_period(self):
        ext = TerminationExtraction(
            cure_period={"has_cure_period": True, "cure_days": 30, "cure_source_text": "30 days to cure"}
        )
        assert ext.cure_period.has_cure_period is True
        assert ext.cure_period.cure_days == 30


class TestPaymentSchema:
    def test_defaults(self):
        ext = PaymentExtraction()
        assert ext.has_payment_terms is None
        assert ext.late_fee.has_late_fee is False

    def test_payment_days(self):
        ext = PaymentExtraction(has_payment_terms=True, payment_days=30)
        assert ext.payment_days == 30


class TestConfidentialitySchema:
    def test_defaults(self):
        ext = ConfidentialityExtraction()
        assert ext.has_broad_definition is None
        assert ext.exclusions == []

    def test_exclusions_list(self):
        ext = ConfidentialityExtraction(
            has_standard_exclusions=True,
            exclusions=["public domain", "independent development"],
        )
        assert len(ext.exclusions) == 2


class TestIPSchema:
    def test_defaults(self):
        ext = IPExtraction()
        assert ext.has_customer_owns_deliverables is None
        assert ext.has_work_for_hire is None

    def test_assignment_direction(self):
        ext = IPExtraction(
            has_ip_assignment=True,
            assignment_direction="provider_to_customer",
        )
        assert ext.assignment_direction == "provider_to_customer"


class TestGoverningLawSchema:
    def test_defaults(self):
        ext = GoverningLawExtraction()
        assert ext.has_governing_law is None
        assert ext.has_arbitration is None

    def test_jurisdiction(self):
        ext = GoverningLawExtraction(
            has_governing_law=True,
            governing_law_jurisdiction="State of Delaware",
        )
        assert ext.governing_law_jurisdiction == "State of Delaware"
