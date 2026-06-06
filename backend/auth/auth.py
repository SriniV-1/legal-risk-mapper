"""
JWT token creation/validation and in-memory user storage.

- HS256 signing with configurable JWT_SECRET env var
- 1-hour token expiry
- bcrypt password hashing
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
import bcrypt as _bcrypt

# ── Configuration ────────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 3600  # 1 hour

if JWT_SECRET == "dev-secret-change-me":
    import logging as _logging
    _logging.getLogger("alrm.auth").warning(
        "JWT_SECRET is using the default value. Set JWT_SECRET env var in production."
    )

# ── In-memory user store ────────────────────────────────────────────────────
# Maps user_id -> {"user_id", "email", "hashed_password", "role"}
_users: dict[str, dict] = {}
# Maps email -> user_id for lookup
_email_index: dict[str, str] = {}


def reset_users() -> None:
    """Clear all users. Used by tests."""
    _users.clear()
    _email_index.clear()


def create_user(email: str, password: str, role: str = "free") -> dict:
    """Register a new user. Returns user dict (no password). Raises ValueError on duplicate."""
    if email in _email_index:
        raise ValueError("Email already registered")
    user_id = str(uuid.uuid4())
    _users[user_id] = {
        "user_id": user_id,
        "email": email,
        "hashed_password": _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode(),
        "role": role,
    }
    _email_index[email] = user_id
    return {"user_id": user_id, "email": email, "role": role}


def authenticate_user(email: str, password: str) -> dict | None:
    """Validate credentials. Returns user dict (no password) or None."""
    user_id = _email_index.get(email)
    if user_id is None:
        return None
    user = _users[user_id]
    if not _bcrypt.checkpw(password.encode(), user["hashed_password"].encode()):
        return None
    return {"user_id": user["user_id"], "email": user["email"], "role": user["role"]}


def create_token(user_id: str, email: str, role: str) -> str:
    """Create a signed JWT with 1-hour expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": now + timedelta(seconds=TOKEN_EXPIRE_SECONDS),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises JWTError on invalid/expired."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
