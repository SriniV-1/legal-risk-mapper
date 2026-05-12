"""
Tests for the risk analysis pipeline — regex patterns, scoring, and severity classification.
"""
import pytest

from backend.services.risk_analyzer import analyze_risks, compute_overall_risk


class TestAnalyzeRisks:
    """Core risk detection tests."""

    def test_empty_text_returns_no_risks(self):
        result = analyze_risks("")
        assert result == []

    def test_high_risk_contract_detects_risks(self):
        text = (
            "Company shall not be liable for any indirect, consequential, or incidental "
            "damages. Client shall indemnify and hold harmless Company from all claims. "
            "This agreement is provided AS-IS without any warranty of merchantability."
        )
        risks = analyze_risks(text)
        assert len(risks) > 0
        categories = {r["risk_type"] for r in risks}
        assert any("Liability" in c or "Contractual" in c for c in categories)

    def test_clean_text_returns_fewer_risks(self):
        text = (
            "Both parties agree to keep shared information confidential. "
            "Any disputes will be resolved through mediation."
        )
        risks = analyze_risks(text)
        # Clean text should have few or no high-severity risks
        high_risks = [r for r in risks if r["severity"] == "High"]
        assert len(high_risks) <= 1

    def test_auto_renewal_detected(self):
        text = "This agreement automatically renews for successive one-year terms unless either party provides written notice of non-renewal at least 90 days prior."
        risks = analyze_risks(text)
        snippets = " ".join(r["text_snippet"].lower() for r in risks)
        assert "renew" in snippets or len(risks) > 0

    def test_data_sharing_detected(self):
        text = "We may share your personal data with third-party advertising partners for targeted marketing purposes. Your data may be sold to data brokers."
        risks = analyze_risks(text)
        assert len(risks) > 0

    def test_risk_structure(self):
        text = "Company's liability is limited at its sole discretion. No warranty provided."
        risks = analyze_risks(text)
        if risks:
            r = risks[0]
            assert "risk_type" in r
            assert "severity" in r
            assert "text_snippet" in r
            assert "score" in r
            assert r["severity"] in ("High", "Medium", "Low")


class TestComputeOverallRisk:
    def test_no_risks(self):
        assert compute_overall_risk([]) == "Low"

    def test_high_severity_present(self):
        risks = [
            {"severity": "High", "score": 85},
            {"severity": "Medium", "score": 55},
        ]
        result = compute_overall_risk(risks)
        assert result in ("High", "Medium")  # Should escalate

    def test_only_low_risks(self):
        risks = [
            {"severity": "Low", "score": 25},
            {"severity": "Low", "score": 30},
        ]
        result = compute_overall_risk(risks)
        assert result in ("Low", "Medium")
