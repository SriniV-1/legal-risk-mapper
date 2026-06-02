"""
Circuit Breaker Pattern
───────────────────────
Prevents cascading failures when external APIs (Groq, Supabase) are down.

States:
  CLOSED   → Normal operation. Failures are counted.
  OPEN     → After `failure_threshold` consecutive failures, all calls are
             rejected immediately (503) without hitting the external service.
  HALF_OPEN → After `recovery_timeout` seconds, one probe request is allowed
              through. If it succeeds, the breaker resets to CLOSED. If it
              fails, the breaker returns to OPEN.

Usage:
    breaker = CircuitBreaker("groq", failure_threshold=5, recovery_timeout=30)

    with breaker:
        response = call_external_api()

    # Or functional style:
    result = breaker.call(call_external_api, arg1, arg2)
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an open circuit breaker."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. Retry after {retry_after:.1f}s."
        )


class CircuitBreaker:
    """Thread-safe circuit breaker for wrapping external API calls."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        """Current state, accounting for recovery timeout transitions."""
        with self._lock:
            return self._effective_state()

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* through the circuit breaker."""
        self._before_call()
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info("Circuit breaker '%s' manually reset to CLOSED", self.name)

    def status(self) -> dict:
        """Return a dict suitable for inclusion in /health responses."""
        with self._lock:
            state = self._effective_state()
            info: dict = {
                "state": state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
            }
            if state == CircuitState.OPEN and self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                info["retry_after_seconds"] = round(
                    max(0, self.recovery_timeout - elapsed), 1
                )
            return info

    # ── Context manager support ─────────────────────────────────────────────

    def __enter__(self):
        self._before_call()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._on_success()
        else:
            self._on_failure()
        return False  # don't suppress the exception

    # ── Internal helpers ────────────────────────────────────────────────────

    def _effective_state(self) -> CircuitState:
        """Compute the logical state (must be called under lock)."""
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    def _before_call(self) -> None:
        with self._lock:
            state = self._effective_state()
            if state == CircuitState.OPEN:
                elapsed = time.monotonic() - (self._last_failure_time or 0)
                retry_after = max(0, self.recovery_timeout - elapsed)
                raise CircuitOpenError(self.name, retry_after)
            if state == CircuitState.HALF_OPEN:
                # Allow exactly one probe — transition to half-open officially
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker '%s' allowing HALF_OPEN probe", self.name
                )

    def _on_success(self) -> None:
        with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
                if self._failure_count > 0 or self._state == CircuitState.HALF_OPEN:
                    logger.info(
                        "Circuit breaker '%s' → CLOSED (success after %d failures)",
                        self.name,
                        self._failure_count,
                    )
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._last_failure_time = None

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s' → OPEN (half-open probe failed)",
                    self.name,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s' → OPEN (threshold %d reached)",
                    self.name,
                    self.failure_threshold,
                )


# ── Shared instances ────────────────────────────────────────────────────────
# Imported by other modules so that the same breaker state is used everywhere.

groq_breaker = CircuitBreaker("groq", failure_threshold=5, recovery_timeout=30)
supabase_breaker = CircuitBreaker("supabase", failure_threshold=5, recovery_timeout=30)
