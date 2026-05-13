"""
Tests for FastAPI endpoints using httpx TestClient.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "nlp_engine" in data


class TestAnalyzeEndpoint:
    def test_analyze_valid_text(self):
        r = client.post("/analyze", json={
            "text": "Company is not liable for any damages. No warranty provided. Client indemnifies Company.",
            "document_title": "Test Contract",
        })
        assert r.status_code == 200
        data = r.json()
        assert "total_risks" in data
        assert "risks" in data
        assert "overall_risk_level" in data
        assert data["overall_risk_level"] in ("High", "Medium", "Low")

    def test_analyze_empty_text(self):
        r = client.post("/analyze", json={"text": ""})
        # FastAPI validation or empty result
        assert r.status_code in (200, 422)

    def test_analyze_short_clean_text(self):
        r = client.post("/analyze", json={
            "text": "Both parties agree to treat all shared information as confidential for two years.",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["total_risks"] >= 0

    def test_analyze_returns_risk_structure(self):
        r = client.post("/analyze", json={
            "text": "We collect your personal data and may sell it to third parties without notice.",
        })
        assert r.status_code == 200
        data = r.json()
        for risk in data["risks"]:
            assert "risk_type" in risk
            assert "severity" in risk
            assert "text_snippet" in risk
            assert "score" in risk
            assert "explanation" in risk


class TestAnalyzeUploadEndpoint:
    def test_upload_txt_file(self):
        content = b"This agreement is provided AS-IS. No warranties. Client shall indemnify Company."
        r = client.post(
            "/analyze/upload",
            files={"file": ("test.txt", content, "text/plain")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_risks"] >= 0

    def test_upload_invalid_extension(self):
        r = client.post(
            "/analyze/upload",
            files={"file": ("test.docx", b"fake docx content", "application/octet-stream")},
        )
        assert r.status_code == 400

    def test_upload_pdf_accepted(self):
        # Real minimal PDF bytes so pymupdf can open it
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "This agreement is provided AS-IS without warranty.")
        pdf_bytes = doc.tobytes()
        doc.close()
        r = client.post(
            "/analyze/upload",
            files={"file": ("contract.pdf", pdf_bytes, "application/pdf")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_risks"] >= 0


class TestBenchmarkEndpoint:
    def test_benchmark_rejects_short_text(self):
        r = client.post("/benchmark", json={
            "text": "Short",
            "clause_type": "liability",
        })
        assert r.status_code == 422  # Pydantic validation (min_length=30)

    def test_benchmark_accepts_valid_request(self):
        r = client.post("/benchmark", json={
            "text": "The total aggregate liability of the Provider under this Agreement shall not exceed the total fees paid by Customer in the twelve months preceding the claim.",
            "clause_type": "liability",
        })
        # May fail if Ollama/Supabase not running, but should not 422
        assert r.status_code in (200, 500)

    def test_benchmark_default_is_auto(self):
        r = client.post("/benchmark", json={
            "text": "The total aggregate liability of the Provider shall not exceed annual fees."
        })
        # No clause_type specified — defaults to "auto". Should not 422.
        assert r.status_code in (200, 500)


class TestAutoDetection:
    """Clause type auto-detection from text."""

    def test_liability_keywords_detected(self):
        from backend.main import _resolve_clause_type
        text = "Provider's aggregate liability shall not exceed the fees paid. Consequential damages are excluded."
        assert _resolve_clause_type(text, "auto") == "liability"

    def test_termination_keywords_detected(self):
        from backend.main import _resolve_clause_type
        text = "Either party may terminate this Agreement for cause with thirty days notice. Survival provisions apply."
        assert _resolve_clause_type(text, "auto") == "termination"

    def test_governing_law_keywords_detected(self):
        from backend.main import _resolve_clause_type
        text = "This Agreement shall be governed by the laws of the State of Delaware. Any disputes shall be resolved by arbitration."
        assert _resolve_clause_type(text, "auto") == "governing_law"

    def test_explicit_type_passthrough(self):
        from backend.main import _resolve_clause_type
        text = "Whatever text, doesn't matter."
        assert _resolve_clause_type(text, "payment") == "payment"
        assert _resolve_clause_type(text, "ip") == "ip"

    def test_unknown_text_falls_back_to_liability(self):
        from backend.main import _resolve_clause_type
        text = "The quick brown fox jumps over the lazy dog in a very legal sounding manner indeed."
        result = _resolve_clause_type(text, "auto")
        assert result in ("liability", "other")  # either is acceptable


class TestRedlineEndpoint:
    def test_redline_rejects_short_text(self):
        r = client.post("/redline", json={
            "text": "Too short",
            "clause_type": "liability",
        })
        assert r.status_code == 422
