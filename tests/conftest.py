"""Shared test fixtures."""
import pytest

from backend.main import app, limiter
from backend.auth.middleware import get_current_user


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Disable rate limiting during tests to avoid cross-test interference."""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def _bypass_auth():
    """Bypass JWT auth in all tests by default. Auth tests override this."""
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-user",
        "email": "test@test.com",
        "role": "admin",
    }
    yield
    app.dependency_overrides.pop(get_current_user, None)
