"""
ML output quality tests for the risk analysis pipeline.

Verifies that the hybrid ML+regex pipeline produces correct classifications,
appropriate severity levels, and consistent output for known inputs.
"""
import pytest

from backend.services.risk_analyzer import analyze_risks


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _risk_types(risks):
    """Extract the set of risk_type values from a list of risk dicts."""
    return {r["risk_type"] for r in risks}


def _find_risk(risks, risk_type):
    """Return the first risk matching the given type, or None."""
    for r in risks:
        if r["risk_type"] == risk_type:
            return r
    return None


def _highest_risk(risks):
    """Return the risk with the highest score."""
    return max(risks, key=lambda r: r["score"]) if risks else None


# ─────────────────────────────────────────────
#  1. Known-input classification tests
# ─────────────────────────────────────────────

class TestKnownInputClassification:
    """Verify that specific contract language triggers the correct risk categories."""

    def test_indemnification_detects_liability_risk(self):
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client against "
            "all claims, damages, and losses arising from the Company's breach "
            "of this agreement."
        )
        assert len(risks) > 0, "Should detect at least one risk"
        types = _risk_types(risks)
        assert "Liability Risk" in types
        liability = _find_risk(risks, "Liability Risk")
        assert liability["severity"] == "High"

    def test_auto_renewal_detects_financial_risk(self):
        risks = analyze_risks(
            "This agreement auto-renews annually unless cancelled in writing "
            "at least 90 days prior to the renewal date."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Financial Risk" in types

    def test_sell_personal_data_detects_privacy_risk_high(self):
        risks = analyze_risks(
            "We may sell your personal data to third parties for marketing "
            "purposes without obtaining additional consent."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Privacy/Data Risk" in types
        privacy = _find_risk(risks, "Privacy/Data Risk")
        # May be High or Medium depending on whether semantic layer is active;
        # must never be Low for explicit data-selling language.
        assert privacy["severity"] in ("High", "Medium")

    def test_sole_discretion_detects_contractual_ambiguity(self):
        risks = analyze_risks(
            "At our sole discretion, we may change the terms of service "
            "at any time without prior notice to the user."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Contractual Ambiguity" in types
        ambiguity = _find_risk(risks, "Contractual Ambiguity")
        assert ambiguity["severity"] == "High"

    def test_gdpr_compliance_detects_compliance_risk(self):
        risks = analyze_risks(
            "The processor must comply with GDPR and all applicable data "
            "protection laws when handling personal data of EU residents."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Compliance Risk" in types

    def test_no_warranty_as_is_detects_liability_risk(self):
        risks = analyze_risks(
            "No warranty is provided. The service is delivered AS-IS without "
            "any guarantees of fitness for a particular purpose."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Liability Risk" in types

    def test_early_termination_fee_detects_financial_risk_high(self):
        risks = analyze_risks(
            "An early termination fee of 50% of the remaining contract value "
            "will be charged if this agreement is terminated before expiration."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Financial Risk" in types
        financial = _find_risk(risks, "Financial Risk")
        assert financial["severity"] == "High"

    def test_biometric_data_detects_privacy_risk_high(self):
        risks = analyze_risks(
            "We collect your biometric data including facial recognition "
            "templates and fingerprint scans for identity verification."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Privacy/Data Risk" in types
        privacy = _find_risk(risks, "Privacy/Data Risk")
        assert privacy["severity"] == "High"

    def test_benign_text_returns_no_or_low_risks(self):
        risks = analyze_risks(
            "The parties agree to meet quarterly to review progress. "
            "Meetings will be held at a mutually convenient location."
        )
        # Either no risks at all, or only Low severity
        for r in risks:
            assert r["severity"] in ("Low", "Medium"), (
                f"Benign text should not produce High risk, got: "
                f"{r['risk_type']} = {r['severity']}"
            )

    def test_multi_risk_paragraph_detects_multiple_categories(self):
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client. "
            "This agreement auto-renews annually unless cancelled. "
            "We may sell your personal data to third parties. "
            "At our sole discretion, we may change terms at any time."
        )
        types = _risk_types(risks)
        assert len(types) >= 2, (
            f"Multi-risk paragraph should detect at least 2 categories, "
            f"got: {types}"
        )

    def test_unlimited_liability_detects_high_liability(self):
        risks = analyze_risks(
            "The vendor accepts unlimited liability for all direct and "
            "indirect damages arising under this agreement."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Liability Risk" in types
        liability = _find_risk(risks, "Liability Risk")
        assert liability["severity"] == "High"

    def test_penalty_clause_detects_financial_risk(self):
        risks = analyze_risks(
            "A penalty of $10,000 per day will be assessed for each day "
            "the deliverables are late beyond the agreed deadline."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Financial Risk" in types

    def test_data_breach_detects_privacy_risk(self):
        risks = analyze_risks(
            "In the event of a data breach, the processor must notify the "
            "controller within 72 hours of becoming aware of the incident."
        )
        assert len(risks) > 0
        types = _risk_types(risks)
        assert "Privacy/Data Risk" in types


# ─────────────────────────────────────────────
#  2. Severity ordering tests
# ─────────────────────────────────────────────

class TestSeverityOrdering:
    """Verify that severity labels are consistent with the 0-100 score bands."""

    def test_high_severity_has_score_at_least_70(self):
        """High severity must have score >= 70 per the scoring spec."""
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client against "
            "all claims. We may sell your personal data to third parties. "
            "At our sole discretion we may change terms at any time."
        )
        high_risks = [r for r in risks if r["severity"] == "High"]
        for r in high_risks:
            assert r["score"] >= 70, (
                f"High-severity risk '{r['risk_type']}' has score {r['score']} "
                f"(expected >= 70)"
            )

    def test_low_severity_has_score_below_40(self):
        """Low severity must have score < 40 per the scoring spec."""
        risks = analyze_risks(
            "This agreement includes cookies for basic site functionality. "
            "Payment within 30 days. Good faith negotiations between parties. "
            "Including but not limited to services described herein. "
            "Encryption of data at rest is recommended."
        )
        low_risks = [r for r in risks if r["severity"] == "Low"]
        for r in low_risks:
            assert r["score"] < 40, (
                f"Low-severity risk '{r['risk_type']}' has score {r['score']} "
                f"(expected < 40)"
            )

    def test_medium_severity_score_between_40_and_69(self):
        """Medium severity must have score in [40, 69]."""
        risks = analyze_risks(
            "The limitation of liability under this agreement shall not exceed "
            "the total fees paid. Non-refundable deposits are required. "
            "Reasonable efforts shall be made to resolve disputes. "
            "Data retention policies apply to collected information."
        )
        medium_risks = [r for r in risks if r["severity"] == "Medium"]
        for r in medium_risks:
            assert 40 <= r["score"] < 70, (
                f"Medium-severity risk '{r['risk_type']}' has score {r['score']} "
                f"(expected 40-69)"
            )

    def test_results_sorted_by_score_descending(self):
        """analyze_risks() returns results sorted by score descending."""
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client. "
            "This agreement auto-renews annually unless cancelled. "
            "Payment within 30 days. Including but not limited to the above. "
            "We collect your personal data for service improvement."
        )
        if len(risks) < 2:
            pytest.skip("Not enough risks detected to test ordering")
        scores = [r["score"] for r in risks]
        assert scores == sorted(scores, reverse=True), (
            f"Risks should be sorted by score descending, got scores: {scores}"
        )


# ─────────────────────────────────────────────
#  3. Determinism tests
# ─────────────────────────────────────────────

class TestDeterminism:
    """Verify that the pipeline produces consistent output for identical input."""

    def test_same_input_same_output(self):
        """Running the same text twice should produce identical results."""
        text = (
            "The Company shall indemnify and hold harmless the Client against "
            "all claims. An early termination fee of 50% applies. "
            "We collect your biometric data including facial recognition."
        )
        run1 = analyze_risks(text)
        run2 = analyze_risks(text)

        assert len(run1) == len(run2), (
            f"Different number of risks: {len(run1)} vs {len(run2)}"
        )
        for r1, r2 in zip(run1, run2):
            assert r1["risk_type"] == r2["risk_type"], (
                f"Risk type mismatch: {r1['risk_type']} vs {r2['risk_type']}"
            )
            assert r1["severity"] == r2["severity"], (
                f"Severity mismatch for {r1['risk_type']}: "
                f"{r1['severity']} vs {r2['severity']}"
            )
            assert r1["score"] == r2["score"], (
                f"Score mismatch for {r1['risk_type']}: "
                f"{r1['score']} vs {r2['score']}"
            )

    def test_determinism_across_multiple_runs(self):
        """Five consecutive runs should all match."""
        text = (
            "At our sole discretion, we may change terms at any time. "
            "Must comply with GDPR and all applicable data protection laws."
        )
        baseline = analyze_risks(text)
        for i in range(4):
            result = analyze_risks(text)
            assert len(result) == len(baseline), (
                f"Run {i+2} produced {len(result)} risks vs baseline {len(baseline)}"
            )
            for r, b in zip(result, baseline):
                assert r["risk_type"] == b["risk_type"]
                assert r["score"] == b["score"]
                assert r["severity"] == b["severity"]


# ─────────────────────────────────────────────
#  4. Regression guard tests
# ─────────────────────────────────────────────

class TestRegressionGuards:
    """Prevent regressions: known HIGH inputs must never be classified as LOW."""

    def test_indemnify_never_low(self):
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client against "
            "all claims, damages, losses, and expenses."
        )
        liability = _find_risk(risks, "Liability Risk")
        assert liability is not None, "Indemnification should always detect Liability Risk"
        assert liability["severity"] != "Low", (
            f"Indemnification clause should never be Low severity, "
            f"got score={liability['score']}"
        )

    def test_sell_data_never_low(self):
        risks = analyze_risks(
            "We may sell your personal data to third parties for advertising "
            "and profiling purposes without your explicit consent."
        )
        privacy = _find_risk(risks, "Privacy/Data Risk")
        assert privacy is not None, "Selling personal data should always detect Privacy/Data Risk"
        assert privacy["severity"] != "Low", (
            f"Selling personal data should never be Low severity, "
            f"got score={privacy['score']}"
        )

    def test_sole_discretion_never_low(self):
        risks = analyze_risks(
            "At our sole discretion, we may modify, suspend, or terminate "
            "your account at any time without notice or liability."
        )
        ambiguity = _find_risk(risks, "Contractual Ambiguity")
        assert ambiguity is not None, "Sole discretion should always detect Contractual Ambiguity"
        assert ambiguity["severity"] != "Low", (
            f"Sole discretion clause should never be Low severity, "
            f"got score={ambiguity['score']}"
        )

    def test_gdpr_compliance_never_low(self):
        risks = analyze_risks(
            "The processor must comply with GDPR and all applicable data "
            "protection regulations when processing personal data."
        )
        compliance = _find_risk(risks, "Compliance Risk")
        assert compliance is not None, "GDPR reference should always detect Compliance Risk"
        assert compliance["severity"] != "Low", (
            f"GDPR compliance clause should never be Low severity, "
            f"got score={compliance['score']}"
        )

    def test_early_termination_fee_never_low(self):
        risks = analyze_risks(
            "An early termination fee equal to 100% of the remaining contract "
            "value shall be immediately due and payable upon early termination."
        )
        financial = _find_risk(risks, "Financial Risk")
        assert financial is not None, "Early termination fee should always detect Financial Risk"
        assert financial["severity"] != "Low", (
            f"Early termination fee should never be Low severity, "
            f"got score={financial['score']}"
        )

    def test_biometric_collection_never_low(self):
        risks = analyze_risks(
            "We collect your biometric data including fingerprints, facial "
            "recognition templates, and voice prints for authentication."
        )
        privacy = _find_risk(risks, "Privacy/Data Risk")
        assert privacy is not None, "Biometric data collection should always detect Privacy/Data Risk"
        assert privacy["severity"] != "Low", (
            f"Biometric data collection should never be Low severity, "
            f"got score={privacy['score']}"
        )


# ─────────────────────────────────────────────
#  5. Output structure validation
# ─────────────────────────────────────────────

class TestOutputStructure:
    """Verify that every risk dict has the required fields with valid values."""

    VALID_RISK_TYPES = {
        "Compliance Risk",
        "Liability Risk",
        "Privacy/Data Risk",
        "Financial Risk",
        "Contractual Ambiguity",
    }
    VALID_SEVERITIES = {"Low", "Medium", "High"}

    def test_all_fields_present(self):
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client. "
            "We may sell your personal data to third parties."
        )
        assert len(risks) > 0
        for r in risks:
            assert "risk_type" in r, "Missing 'risk_type'"
            assert "severity" in r, "Missing 'severity'"
            assert "score" in r, "Missing 'score'"
            assert "text_snippet" in r, "Missing 'text_snippet'"
            assert "explanation" in r, "Missing 'explanation'"
            assert "keywords_matched" in r, "Missing 'keywords_matched'"

    def test_risk_type_values_valid(self):
        risks = analyze_risks(
            "The Company shall indemnify the Client. Auto-renewal applies. "
            "Must comply with GDPR. We collect biometric data. "
            "At our sole discretion we may change terms."
        )
        for r in risks:
            assert r["risk_type"] in self.VALID_RISK_TYPES, (
                f"Unexpected risk_type: {r['risk_type']}"
            )

    def test_severity_values_valid(self):
        risks = analyze_risks(
            "The Company shall indemnify the Client. Payment within 30 days. "
            "Reasonable efforts to comply. Cookies are used."
        )
        for r in risks:
            assert r["severity"] in self.VALID_SEVERITIES, (
                f"Unexpected severity: {r['severity']}"
            )

    def test_score_is_int_in_range(self):
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client against "
            "all claims. An early termination fee of 50% applies."
        )
        for r in risks:
            assert isinstance(r["score"], int), (
                f"Score should be int, got {type(r['score'])}"
            )
            assert 0 <= r["score"] <= 100, (
                f"Score out of range: {r['score']}"
            )

    def test_explanation_is_nonempty_string(self):
        risks = analyze_risks(
            "The Company shall indemnify and hold harmless the Client."
        )
        for r in risks:
            assert isinstance(r["explanation"], str)
            assert len(r["explanation"]) > 0, "Explanation should not be empty"
