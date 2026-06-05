"""
FastAPI dependencies for JWT authentication and role-based access control.

Usage:
    from backend.auth.middleware import get_current_user, require_role

    @app.get("/protected", dependencies=[Depends(get_current_user)])
    def protected(): ...

    @app.post("/admin-only", dependencies=[Depends(require_role("admin"))])
    def admin_only(): ...
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError

from backend.auth.auth import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)

# ── Role hierarchy ───────────────────────────────────────────────────────────
ROLE_HIERARCHY = {"free": 0, "pro": 1, "admin": 2}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    Validate the Authorization: Bearer <token> header.
    Returns the decoded user claims dict.
    Raises 401 if missing, invalid, or expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_token(credentials.credentials)
        return claims
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(minimum_role: str):
    """
    Returns a FastAPI dependency that enforces a minimum role level.

    Role hierarchy: free < pro < admin
    """
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def _check_role(current_user: dict = Depends(get_current_user)) -> dict:
        user_level = ROLE_HIERARCHY.get(current_user.get("role", "free"), 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.get('role')}' insufficient. Requires '{minimum_role}' or higher.",
            )
        return current_user

    return _check_role
