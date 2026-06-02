"""
Tests for the circuit breaker pattern.

Covers:
  - State transitions: CLOSED → OPEN → HALF_OPEN → CLOSED / OPEN
  - Threshold counting
  - Timeout reset (half-open probe)
  - Fast rejection when open (< 10ms)
  - Context manager interface
  - Status reporting for /health
"""
from __future__ import annotations

import time

import pytest

from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ok():
    """A function that succeeds."""
    return "ok"


def _fail():
    """A function that always raises."""
    raise RuntimeError("boom")


def _trip_breaker(cb: CircuitBreaker, n: int | None = None) -> None:
    """Record *n* failures (defaults to the failure threshold)."""
    n = n or cb.failure_threshold
    for _ in range(n):
        try:
            cb.call(_fail)
        except RuntimeError:
            pass


# ── State transition tests ───────────────────────────────────────────────────


class TestStateTransitions:
    def test_starts_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        _trip_breaker(cb, 4)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 4

    def test_opens_at_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        _trip_breaker(cb, 5)
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        _trip_breaker(cb, 3)
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.call(_ok)
        assert "OPEN" in str(exc_info.value)

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.05)
        _trip_breaker(cb, 2)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.05)
        _trip_breaker(cb, 2)
        time.sleep(0.06)
        result = cb.call(_ok)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.05)
        _trip_breaker(cb, 2)
        time.sleep(0.06)
        with pytest.raises(RuntimeError):
            cb.call(_fail)
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        _trip_breaker(cb, 3)
        assert cb.failure_count == 3
        cb.call(_ok)
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED


# ── Threshold counting ───────────────────────────────────────────────────────


class TestThresholdCounting:
    def test_exact_threshold_trips(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        _trip_breaker(cb, 5)
        assert cb.state == CircuitState.OPEN

    def test_failures_counted_accurately(self):
        cb = CircuitBreaker("test", failure_threshold=10)
        _trip_breaker(cb, 7)
        assert cb.failure_count == 7
        assert cb.state == CircuitState.CLOSED

    def test_default_threshold_is_five(self):
        cb = CircuitBreaker("test")
        assert cb.failure_threshold == 5


# ── Timeout reset ────────────────────────────────────────────────────────────


class TestTimeoutReset:
    def test_recovery_timeout_respected(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        _trip_breaker(cb, 2)
        # Still open immediately after tripping
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            cb.call(_ok)
        # Wait for recovery
        time.sleep(0.12)
        assert cb.state == CircuitState.HALF_OPEN

    def test_default_recovery_timeout(self):
        cb = CircuitBreaker("test")
        assert cb.recovery_timeout == 30.0


# ── Fast rejection ───────────────────────────────────────────────────────────


class TestFastRejection:
    def test_open_circuit_rejects_under_10ms(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60)
        _trip_breaker(cb, 2)

        start = time.monotonic()
        with pytest.raises(CircuitOpenError):
            cb.call(_ok)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 10, f"Rejection took {elapsed_ms:.2f}ms, expected < 10ms"


# ── Context manager ──────────────────────────────────────────────────────────


class TestContextManager:
    def test_context_manager_success(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        with cb:
            result = "inside"
        assert result == "inside"
        assert cb.state == CircuitState.CLOSED

    def test_context_manager_failure_counts(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                with cb:
                    raise RuntimeError("boom")
        assert cb.state == CircuitState.OPEN

    def test_context_manager_rejects_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60)
        _trip_breaker(cb, 2)
        with pytest.raises(CircuitOpenError):
            with cb:
                pass  # should never get here


# ── Status reporting ─────────────────────────────────────────────────────────


class TestStatusReporting:
    def test_status_closed(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        status = cb.status()
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 5
        assert "retry_after_seconds" not in status

    def test_status_open_has_retry_after(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30)
        _trip_breaker(cb, 2)
        status = cb.status()
        assert status["state"] == "open"
        assert status["failure_count"] == 2
        assert "retry_after_seconds" in status
        assert status["retry_after_seconds"] > 0

    def test_status_after_partial_failures(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        _trip_breaker(cb, 3)
        status = cb.status()
        assert status["state"] == "closed"
        assert status["failure_count"] == 3


# ── Manual reset ─────────────────────────────────────────────────────────────


class TestManualReset:
    def test_reset_from_open(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        _trip_breaker(cb, 2)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_allows_calls(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60)
        _trip_breaker(cb, 2)
        cb.reset()
        result = cb.call(_ok)
        assert result == "ok"
