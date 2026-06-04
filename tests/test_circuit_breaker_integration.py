"""
Integration tests for circuit breaker wiring.

Verifies that:
  1. The circuit breaker instance is used in the extractor module.
  2. After simulated failures, the circuit opens and extraction returns None.
  3. The /health endpoint exposes circuit breaker state.
"""
from __future__ import annotations

import importlib
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.services.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


# ── 1. Verify the breaker instance exists in extractor ────────────────────────

def test_extractor_imports_groq_breaker():
    """The extractor module should reference the shared groq_breaker instance."""
    from backend.extraction import extractor
    from backend.services.circuit_breaker import groq_breaker

    assert hasattr(extractor, "groq_breaker"), (
        "extractor module does not have groq_breaker attribute"
    )
    assert extractor.groq_breaker is groq_breaker, (
        "extractor.groq_breaker is not the same shared instance from circuit_breaker module"
    )


def test_benchmarker_imports_groq_breaker():
    """The benchmarker module should reference the shared groq_breaker instance."""
    from backend.benchmarking import benchmarker
    from backend.services.circuit_breaker import groq_breaker

    assert hasattr(benchmarker, "groq_breaker"), (
        "benchmarker module does not have groq_breaker attribute"
    )
    assert benchmarker.groq_breaker is groq_breaker, (
        "benchmarker.groq_breaker is not the same shared instance from circuit_breaker module"
    )


# ── 2. After failures, circuit opens and extraction returns None ──────────────

def test_circuit_opens_after_threshold_failures():
    """Simulate consecutive LLM failures; the breaker should transition to OPEN."""
    breaker = CircuitBreaker("test-llm", failure_threshold=3, recovery_timeout=60)

    def failing_call():
        raise RuntimeError("LLM service unavailable")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            breaker.call(failing_call)

    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3


def test_open_circuit_rejects_calls_immediately():
    """Once OPEN, the breaker should raise CircuitOpenError without executing the function."""
    breaker = CircuitBreaker("test-reject", failure_threshold=2, recovery_timeout=60)

    def failing_call():
        raise RuntimeError("boom")

    # Trip the breaker
    for _ in range(2):
        with pytest.raises(RuntimeError):
            breaker.call(failing_call)

    assert breaker.state == CircuitState.OPEN

    # Now further calls should be rejected immediately
    call_executed = False

    def should_not_run():
        nonlocal call_executed
        call_executed = True

    with pytest.raises(CircuitOpenError):
        breaker.call(should_not_run)

    assert not call_executed, "Function was called even though circuit is OPEN"


def test_extraction_returns_none_when_circuit_open():
    """extract_clause should return None when the circuit breaker is OPEN."""
    from backend.services.circuit_breaker import groq_breaker

    # Save original state so we can restore it
    original_state = groq_breaker._state
    original_failures = groq_breaker._failure_count
    original_last_failure = groq_breaker._last_failure_time

    try:
        # Manually trip the breaker by simulating enough failures
        import time
        groq_breaker._state = CircuitState.OPEN
        groq_breaker._failure_count = groq_breaker.failure_threshold
        groq_breaker._last_failure_time = time.monotonic()

        from backend.extraction.extractor import extract_clause
        result = extract_clause(
            "This is a test liability clause with no real content.",
            clause_type="liability",
        )

        assert result is None, (
            "extract_clause should return None when circuit breaker is OPEN"
        )
    finally:
        # Restore breaker state
        groq_breaker._state = original_state
        groq_breaker._failure_count = original_failures
        groq_breaker._last_failure_time = original_last_failure


def test_successful_call_resets_breaker():
    """A successful call after failures should reset the breaker to CLOSED."""
    breaker = CircuitBreaker("test-reset", failure_threshold=5, recovery_timeout=60)

    def failing_call():
        raise RuntimeError("fail")

    # Accumulate some failures (below threshold)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            breaker.call(failing_call)

    assert breaker.failure_count == 3
    assert breaker.state == CircuitState.CLOSED

    # A successful call resets the count
    result = breaker.call(lambda: "ok")
    assert result == "ok"
    assert breaker.failure_count == 0
    assert breaker.state == CircuitState.CLOSED


# ── 3. Health endpoint exposes circuit breaker state ──────────────────────────

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from backend.main import app
    return TestClient(app)


def test_health_endpoint_includes_circuit_breaker(client):
    """GET /health should include circuit_breaker.llm in its response."""
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert "circuit_breaker" in data, (
        "/health response missing 'circuit_breaker' key"
    )
    assert "llm" in data["circuit_breaker"], (
        "/health circuit_breaker missing 'llm' key"
    )

    llm_status = data["circuit_breaker"]["llm"]
    assert "state" in llm_status, "LLM circuit breaker status missing 'state'"
    assert "failure_count" in llm_status, "LLM circuit breaker status missing 'failure_count'"
    assert "failure_threshold" in llm_status, "LLM circuit breaker status missing 'failure_threshold'"


def test_health_reflects_open_circuit(client):
    """When the breaker is OPEN, /health should report 'open' state."""
    from backend.services.circuit_breaker import groq_breaker

    original_state = groq_breaker._state
    original_failures = groq_breaker._failure_count
    original_last_failure = groq_breaker._last_failure_time

    try:
        import time
        groq_breaker._state = CircuitState.OPEN
        groq_breaker._failure_count = groq_breaker.failure_threshold
        groq_breaker._last_failure_time = time.monotonic()

        resp = client.get("/health")
        assert resp.status_code == 200

        data = resp.json()
        llm_status = data["circuit_breaker"]["llm"]
        assert llm_status["state"] == "open", (
            f"Expected state 'open', got '{llm_status['state']}'"
        )
        assert "retry_after_seconds" in llm_status, (
            "OPEN circuit should include retry_after_seconds"
        )
    finally:
        groq_breaker._state = original_state
        groq_breaker._failure_count = original_failures
        groq_breaker._last_failure_time = original_last_failure


def test_health_reflects_closed_circuit(client):
    """When the breaker is CLOSED (default), /health should report 'closed' state."""
    from backend.services.circuit_breaker import groq_breaker

    # Ensure breaker is in default state
    groq_breaker.reset()

    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    llm_status = data["circuit_breaker"]["llm"]
    assert llm_status["state"] == "closed"
    assert llm_status["failure_count"] == 0
