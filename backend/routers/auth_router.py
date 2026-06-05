"""
Authentication endpoints: register, login, refresh.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.models import UserCreate, UserResponse, TokenResponse
from backend.auth.auth import (
    create_user,
    authenticate_user,
    create_token,
    TOKEN_EXPIRE_SECONDS,
)
from backend.auth.middleware import get_current_user

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/register", response_model=UserResponse, status_code=201)
def register(body: UserCreate):
    """Create a new user account. Default role is 'free'."""
    try:
        user = create_user(body.email, body.password)
        return UserResponse(**user)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@auth_router.post("/login", response_model=TokenResponse)
def login(body: UserCreate):
    """Validate credentials and return a JWT access token."""
    user = authenticate_user(body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_token(user["user_id"], user["email"], user["role"])
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=TOKEN_EXPIRE_SECONDS,
    )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user: dict = Depends(get_current_user)):
    """Exchange a valid token for a fresh one with a new expiry."""
    token = create_token(
        current_user["user_id"],
        current_user["email"],
        current_user["role"],
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=TOKEN_EXPIRE_SECONDS,
    )
