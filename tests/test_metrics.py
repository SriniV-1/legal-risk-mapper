"""
Tests for Prometheus metrics module and /metrics endpoint.
"""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.metrics import (
    record_analysis,
    record_error,
    get_metrics_text,
)
from backend.routers.metrics_router import metrics_router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_risk(risk_type: str = "Liability Risk", severity: str = "High"):
    """Return a lightweight object that quacks like a RiskItem."""
    return SimpleNamespace(risk_type=risk_type, severity=severity)


# ---------------------------------------------------------------------------
# Unit tests — metrics module
# ---------------------------------------------------------------------------

class TestRecordAnalysis:
    """Verify that record_analysis updates the relevant counters."""

    def test_increments_success_counter(self):
        record_analysis(duration_sec=0.5, risks=[], cache_hit=False)
        text = get_metrics_text()
        assert 'alrm_analysis_requests_total{status="success"}' in text

    def test_records_duration(self):
        record_analysis(duration_sec=1.23, risks=[], cache_hit=False)
        text = get_metrics_text()
        assert "alrm_analysis_duration_seconds" in text

    def test_records_cache_hit(self):
        record_analysis(duration_sec=0.1, risks=[], cache_hit=True)
        text = get_metrics_text()
        assert "alrm_cache_hits_total" in text
        # Ensure at least one hit is counted (value > 0)
        for line in text.splitlines():
            if line.startswith("alrm_cache_hits_total "):
                assert float(line.split()[-1]) >= 1.0
                break

    def test_records_cache_miss(self):
        record_analysis(duration_sec=0.1, risks=[], cache_hit=False)
        text = get_metrics_text()
        assert "alrm_cache_misses_total" in text
        for line in text.splitlines():
            if line.startswith("alrm_cache_misses_total "):
                assert float(line.split()[-1]) >= 1.0
                break

    def test_records_risk_detections(self):
        risks = [
            _make_risk("Liability Risk", "High"),
            _make_risk("Compliance Risk", "Medium"),
        ]
        record_analysis(duration_sec=0.2, risks=risks, cache_hit=False)
        text = get_metrics_text()
        assert 'alrm_risk_detections_total{category="Liability Risk",severity="High"}' in text
        assert 'alrm_risk_detections_total{category="Compliance Risk",severity="Medium"}' in text

    def test_increments_clauses_processed(self):
        risks = [_make_risk(), _make_risk(), _make_risk()]
        record_analysis(duration_sec=0.1, risks=risks, cache_hit=False)
        text = get_metrics_text()
        assert "alrm_clauses_processed_total" in text
        for line in text.splitlines():
            if line.startswith("alrm_clauses_processed_total "):
                assert float(line.split()[-1]) >= 3.0
                break


class TestRecordError:
    def test_increments_error_counter(self):
        record_error()
        text = get_metrics_text()
        assert 'alrm_analysis_requests_total{status="error"}' in text


class TestGetMetricsText:
    """Verify the output conforms to Prometheus text exposition format."""

    def test_contains_help_and_type_lines(self):
        text = get_metrics_text()
        assert "# HELP alrm_analysis_duration_seconds" in text
        assert "# TYPE alrm_analysis_duration_seconds histogram" in text
        assert "# HELP alrm_analysis_requests_total" in text
        assert "# TYPE alrm_analysis_requests_total counter" in text

    def test_returns_string(self):
        text = get_metrics_text()
        assert isinstance(text, str)
        assert len(text) > 0


# ---------------------------------------------------------------------------
# Integration test — /metrics endpoint
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    """Test the FastAPI router without importing backend.main."""

    def setup_method(self):
        self.app = FastAPI()
        self.app.include_router(metrics_router)
        self.client = TestClient(self.app)

    def test_returns_200(self):
        resp = self.client.get("/metrics")
        assert resp.status_code == 200

    def test_content_type(self):
        resp = self.client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]
        assert "version=0.0.4" in resp.headers["content-type"]

    def test_body_contains_metrics(self):
        # Ensure at least one recording so we have non-empty output
        record_analysis(duration_sec=0.05, risks=[], cache_hit=False)
        resp = self.client.get("/metrics")
        body = resp.text
        assert "alrm_analysis_duration_seconds" in body
        assert "alrm_analysis_requests_total" in body
