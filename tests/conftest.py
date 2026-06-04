"""Shared test fixtures."""
import pytest

from backend.main import app, limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Disable rate limiting during tests to avoid cross-test interference."""
    limiter.enabled = False
    yield
    limiter.enabled = True
