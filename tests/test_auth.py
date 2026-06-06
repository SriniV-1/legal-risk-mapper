"""
Tests for JWT authentication, registration, login, and role-based access control.
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from jose import jwt

from backend.main import app
from backend.auth.auth import (
    JWT_SECRET,
    JWT_ALGORITHM,
    reset_users,
)
from backend.auth.middleware import get_current_user


@pytest.fixture(autouse=True)
def _clear_auth_state():
    """Reset in-memory users and remove auth bypass before each test."""
    reset_users()
    app.dependency_overrides.pop(get_current_user, None)
    yield
    app.dependency_overrides.pop(get_current_user, None)


client = TestClient(app)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _register(email="user@example.com", password="securepass123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(email="user@example.com", password="securepass123"):
    return client.post("/auth/login", json={"email": email, "password": password})


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(email="user@example.com", password="securepass123"):
    _register(email, password)
    r = _login(email, password)
    return r.json()["access_token"]


# ── Registration ─────────────────────────────────────────────────────────────

class TestRegistration:
    def test_register_success(self):
        r = _register()
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == "user@example.com"
        assert data["role"] == "free"
        assert "user_id" in data

    def test_register_duplicate_email(self):
        _register()
        r = _register()
        assert r.status_code == 409

    def test_register_short_password(self):
        r = _register(password="short")
        assert r.status_code == 422

    def test_register_invalid_email(self):
        r = client.post("/auth/register", json={"email": "not-an-email", "password": "securepass123"})
        assert r.status_code == 422


# ── Login ────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self):
        _register()
        r = _login()
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600

    def test_login_wrong_password(self):
        _register()
        r = _login(password="wrongpassword")
        assert r.status_code == 401

    def test_login_nonexistent_user(self):
        r = _login(email="nobody@example.com")
        assert r.status_code == 401


# ── Register -> Login -> Token Flow ──────────────────────────────────────────

class TestFullFlow:
    def test_register_login_access(self):
        _register()
        r = _login()
        token = r.json()["access_token"]

        # Use token to access protected endpoint
        r = client.post(
            "/analyze",
            json={"text": "Company is not liable for any damages whatsoever under this agreement."},
            headers=_auth_header(token),
        )
        assert r.status_code == 200


# ── Token Refresh ────────────────────────────────────────────────────────────

class TestRefresh:
    def test_refresh_returns_new_token(self):
        token = _register_and_login()
        r = client.post("/auth/refresh", headers=_auth_header(token))
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_without_token_fails(self):
        r = client.post("/auth/refresh")
        assert r.status_code in (401, 403)


# ── Expired Token ────────────────────────────────────────────────────────────

class TestExpiredToken:
    def test_expired_token_returns_401(self):
        expired = jwt.encode(
            {
                "user_id": "some-id",
                "email": "user@example.com",
                "role": "free",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        r = client.post(
            "/analyze",
            json={"text": "Company is not liable for any damages whatsoever under this agreement."},
            headers=_auth_header(expired),
        )
        assert r.status_code == 401


# ── Invalid Token ────────────────────────────────────────────────────────────

class TestInvalidToken:
    def test_garbage_token_returns_401(self):
        r = client.post(
            "/analyze",
            json={"text": "Company is not liable for any damages whatsoever under this agreement."},
            headers=_auth_header("not.a.real.token"),
        )
        assert r.status_code == 401

    def test_wrong_secret_returns_401(self):
        bad_token = jwt.encode(
            {
                "user_id": "some-id",
                "email": "user@example.com",
                "role": "free",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "wrong-secret",
            algorithm=JWT_ALGORITHM,
        )
        r = client.post(
            "/analyze",
            json={"text": "Company is not liable for any damages whatsoever under this agreement."},
            headers=_auth_header(bad_token),
        )
        assert r.status_code == 401


# ── Role-Based Access ────────────────────────────────────────────────────────

class TestRoleAccess:
    def test_free_user_can_analyze(self):
        token = _register_and_login()  # default role is "free"
        r = client.post(
            "/analyze",
            json={"text": "Company is not liable for any damages whatsoever under this agreement."},
            headers=_auth_header(token),
        )
        assert r.status_code == 200

    def test_free_user_cannot_benchmark(self):
        token = _register_and_login()
        r = client.post(
            "/benchmark",
            json={
                "text": "The total aggregate liability of the Provider under this Agreement shall not exceed the total fees paid by Customer in the twelve months preceding the claim.",
                "clause_type": "liability",
            },
            headers=_auth_header(token),
        )
        assert r.status_code == 403

    def test_free_user_cannot_redline(self):
        token = _register_and_login()
        r = client.post(
            "/redline",
            json={
                "text": "The total aggregate liability of the Provider under this Agreement shall not exceed the total fees paid.",
                "clause_type": "liability",
            },
            headers=_auth_header(token),
        )
        assert r.status_code == 403

    def test_free_user_cannot_clear_cache(self):
        token = _register_and_login()
        r = client.post("/cache/clear", headers=_auth_header(token))
        assert r.status_code == 403


# ── Exempt Endpoints ─────────────────────────────────────────────────────────

class TestExemptEndpoints:
    def test_health_no_auth(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_ready_no_auth(self):
        r = client.get("/ready")
        assert r.status_code in (200, 503)  # may be 503 if deps missing

    def test_metrics_no_auth(self):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_docs_no_auth(self):
        r = client.get("/docs")
        assert r.status_code == 200

    def test_openapi_no_auth(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200

    def test_auth_register_no_auth(self):
        r = _register()
        assert r.status_code == 201


# ── Protected Endpoints Require Auth ─────────────────────────────────────────

class TestProtectedEndpoints:
    def test_analyze_requires_auth(self):
        r = client.post(
            "/analyze",
            json={"text": "Company is not liable for any damages whatsoever under this agreement."},
        )
        assert r.status_code == 401

    def test_analyze_upload_requires_auth(self):
        r = client.post(
            "/analyze/upload",
            files={"file": ("test.txt", b"This agreement is provided AS-IS. No warranties. Client shall indemnify.", "text/plain")},
        )
        assert r.status_code == 401

    def test_benchmark_requires_auth(self):
        r = client.post(
            "/benchmark",
            json={
                "text": "The total aggregate liability of the Provider under this Agreement shall not exceed the total fees paid by Customer in the twelve months preceding the claim.",
                "clause_type": "liability",
            },
        )
        assert r.status_code == 401

    def test_redline_requires_auth(self):
        r = client.post(
            "/redline",
            json={
                "text": "The total aggregate liability of the Provider under this Agreement shall not exceed the total fees paid.",
                "clause_type": "liability",
            },
        )
        assert r.status_code == 401

    def test_cache_clear_requires_auth(self):
        r = client.post("/cache/clear")
        assert r.status_code == 401

    def test_compare_requires_auth(self):
        r = client.post(
            "/compare",
            json={
                "contracts": [
                    {"name": "A", "text": "x" * 50},
                    {"name": "B", "text": "y" * 50},
                ],
                "clause_type": "liability",
            },
        )
        assert r.status_code == 401
