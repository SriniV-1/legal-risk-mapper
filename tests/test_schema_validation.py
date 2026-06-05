"""
OpenAPI schema validation tests.

Validates that API responses conform to the schemas documented in
FastAPI's auto-generated OpenAPI specification.
"""
import pytest
from fastapi.testclient import TestClient
from jsonschema import validate, RefResolver

from backend.main import app

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _openapi_spec():
    """Return the full OpenAPI spec dict (cached by FastAPI)."""
    return app.openapi()


def _response_schema(path: str, method: str = "get", status: str = "200"):
    """
    Extract the JSON response schema for a given path/method/status from
    the OpenAPI spec.  Resolves top-level $ref if present.

    Returns (schema_dict, resolver) or (None, None) if no schema is declared.
    """
    spec = _openapi_spec()
    path_item = spec.get("paths", {}).get(path, {})
    operation = path_item.get(method, {})
    response_obj = operation.get("responses", {}).get(status, {})
    content = response_obj.get("content", {}).get("application/json", {})
    schema = content.get("schema")
    if schema is None:
        return None, None

    resolver = RefResolver.from_schema(spec)

    # If schema is just a $ref, resolve it
    if "$ref" in schema:
        _, schema = resolver.resolve(schema["$ref"])

    return schema, resolver


# ── Tests: /health ───────────────────────────────────────────────────────────

class TestHealthSchema:
    """GET /health — no response_model declared, so validate fields manually."""

    def test_health_in_openapi_paths(self):
        spec = _openapi_spec()
        assert "/health" in spec["paths"], "Missing /health in OpenAPI paths"

    def test_health_response_fields(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["nlp_engine"], str)
        # Extra fields present in the actual implementation
        assert "cache" in data
        assert "circuit_breaker" in data


# ── Tests: /ready ────────────────────────────────────────────────────────────

class TestReadySchema:
    """GET /ready — has response_model=ReadyResponse, validate against OpenAPI."""

    def test_ready_in_openapi_paths(self):
        spec = _openapi_spec()
        assert "/ready" in spec["paths"]

    def test_ready_response_matches_schema(self):
        schema, resolver = _response_schema("/ready", "get", "200")
        assert schema is not None, "No schema found for GET /ready 200"

        r = client.get("/ready")
        # May be 200 or 503 depending on environment, but body structure is same
        assert r.status_code in (200, 503)
        data = r.json()

        validate(instance=data, schema=schema, resolver=resolver)

    def test_ready_field_types(self):
        r = client.get("/ready")
        assert r.status_code in (200, 503)
        data = r.json()
        assert isinstance(data["ready"], bool)
        assert isinstance(data["checks"], dict)
        for key, value in data["checks"].items():
            assert isinstance(key, str)
            assert isinstance(value, str)


# ── Tests: /analyze ──────────────────────────────────────────────────────────

class TestAnalyzeSchema:
    """POST /analyze — has response_model=AnalyzeResponse, validate against OpenAPI."""

    SAMPLE_TEXT = (
        "Company is not liable for any damages whatsoever. "
        "No warranty is provided, express or implied. "
        "Client shall indemnify Company against all claims."
    )

    def test_analyze_in_openapi_paths(self):
        spec = _openapi_spec()
        assert "/analyze" in spec["paths"]
        assert "post" in spec["paths"]["/analyze"]

    def test_analyze_response_matches_schema(self):
        schema, resolver = _response_schema("/analyze", "post", "200")
        assert schema is not None, "No schema found for POST /analyze 200"

        r = client.post("/analyze", json={"text": self.SAMPLE_TEXT})
        assert r.status_code == 200
        data = r.json()

        validate(instance=data, schema=schema, resolver=resolver)

    def test_analyze_response_required_fields(self):
        r = client.post("/analyze", json={
            "text": self.SAMPLE_TEXT,
            "document_title": "Test Contract",
        })
        assert r.status_code == 200
        data = r.json()

        assert isinstance(data["total_risks"], int)
        assert isinstance(data["risks"], list)
        assert data["overall_risk_level"] in ("High", "Medium", "Low")
        assert isinstance(data["risk_summary"], dict)
        assert isinstance(data["severity_breakdown"], dict)
        assert isinstance(data["analysis_notes"], str)

    def test_analyze_risk_items_match_schema(self):
        """Each item in the risks list should match the RiskItem schema."""
        spec = _openapi_spec()
        risk_item_schema = spec["components"]["schemas"]["RiskItem"]
        resolver = RefResolver.from_schema(spec)

        r = client.post("/analyze", json={"text": self.SAMPLE_TEXT})
        assert r.status_code == 200
        data = r.json()

        for risk in data["risks"]:
            validate(instance=risk, schema=risk_item_schema, resolver=resolver)

    def test_analyze_clean_text_returns_valid_schema(self):
        """Even clean text with zero risks should match the response schema."""
        schema, resolver = _response_schema("/analyze", "post", "200")

        r = client.post("/analyze", json={
            "text": "Both parties agree to collaborate in good faith for the duration of this project."
        })
        assert r.status_code == 200
        data = r.json()

        validate(instance=data, schema=schema, resolver=resolver)


# ── Tests: /metrics ──────────────────────────────────────────────────────────

class TestMetricsSchema:
    """GET /metrics — returns text/plain Prometheus exposition format."""

    def test_metrics_in_openapi_paths(self):
        spec = _openapi_spec()
        assert "/metrics" in spec["paths"]

    def test_metrics_content_type(self):
        r = client.get("/metrics")
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        assert content_type.startswith("text/plain"), (
            f"Expected text/plain content type, got {content_type!r}"
        )

    def test_metrics_body_is_text(self):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert len(r.text) > 0


# ── Tests: /cache/clear ─────────────────────────────────────────────────────

class TestCacheClearSchema:
    """POST /cache/clear — no response_model, validate fields manually."""

    def test_cache_clear_in_openapi_paths(self):
        spec = _openapi_spec()
        assert "/cache/clear" in spec["paths"]

    def test_cache_clear_response_fields(self):
        r = client.post("/cache/clear")
        assert r.status_code == 200
        data = r.json()
        assert "evicted" in data
        assert isinstance(data["evicted"], int)
        assert data["evicted"] >= 0


# ── Tests: OpenAPI Spec Integrity ────────────────────────────────────────────

class TestOpenAPISpecIntegrity:
    """General checks on the OpenAPI spec structure."""

    def test_spec_has_info(self):
        spec = _openapi_spec()
        assert "info" in spec
        assert spec["info"]["title"] == "ALRM — Automated Legal Risk Monitor"
        assert spec["info"]["version"] == "1.0.0"

    def test_spec_has_components_schemas(self):
        spec = _openapi_spec()
        schemas = spec.get("components", {}).get("schemas", {})
        assert "AnalyzeResponse" in schemas
        assert "RiskItem" in schemas
        assert "ReadyResponse" in schemas
        assert "AnalyzeRequest" in schemas

    def test_all_documented_paths_exist(self):
        spec = _openapi_spec()
        paths = spec["paths"]
        expected = ["/health", "/ready", "/analyze", "/metrics", "/cache/clear"]
        for path in expected:
            assert path in paths, f"Missing expected path {path} in OpenAPI spec"
