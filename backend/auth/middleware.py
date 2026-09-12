"""
FastAPI dependencies for JWT authentication and role-based access control.

Usage:
    from backend.auth.middleware import get_current_user, require_role, require_authenticated

    @app.get("/protected", dependencies=[Depends(get_current_user)])
    def protected(): ...

    @app.post("/admin-only", dependencies=[Depends(require_role("admin"))])
    def admin_only(): ...
"""
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError

from backend.auth.auth import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)

# ── Role hierarchy ───────────────────────────────────────────────────────────
ROLE_HIERARCHY = {"free": 0, "pro": 1, "admin": 2}

# ── Public mode ──────────────────────────────────────────────────────────────
# The live demo serves anonymous visitors: the frontend never sends a token. So
# by default the public routes accept requests with no Authorization header.
# Set LRM_REQUIRE_AUTH=1 to make them demand a JWT. Admin-only routes require a
# real token regardless. Read per request so tests can flip it with monkeypatch.
ANONYMOUS_USER = {"user_id": None, "email": None, "role": "anonymous", "anonymous": True}


def auth_required() -> bool:
    return os.environ.get("LRM_REQUIRE_AUTH", "").strip().lower() in ("1", "true", "yes", "on")


def _unauthenticated(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    Validate the Authorization: Bearer <token> header and return the claims dict.

    No header: 401 when LRM_REQUIRE_AUTH is on, otherwise the ANONYMOUS_USER
    claims (public mode). A header that is present but invalid/expired is
    always a 401 — a bad token is never treated as anonymous.
    """
    if credentials is None:
        if auth_required():
            raise _unauthenticated("Missing authentication token")
        return dict(ANONYMOUS_USER)
    try:
        return decode_token(credentials.credentials)
    except JWTError:
        raise _unauthenticated("Invalid or expired token")


async def require_authenticated(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Like get_current_user but never accepts anonymous, even in public mode.
    For routes that act on a specific account (token refresh, admin ops)."""
    if current_user.get("anonymous"):
        raise _unauthenticated("Authentication required")
    return current_user


def require_role(minimum_role: str):
    """
    Returns a FastAPI dependency that enforces a minimum role level.

    Role hierarchy: free < pro < admin
    """
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def _check_role(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("anonymous"):
            # Public mode: anonymous callers get everything below admin.
            if min_level >= ROLE_HIERARCHY["admin"]:
                raise _unauthenticated("Authentication required")
            return current_user
        user_level = ROLE_HIERARCHY.get(current_user.get("role", "free"), 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.get('role')}' insufficient. Requires '{minimum_role}' or higher.",
            )
        return current_user

    return _check_role
