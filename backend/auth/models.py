"""
Pydantic models for authentication and user management.
"""
from pydantic import BaseModel, Field, field_validator
import re


class UserCreate(BaseModel):
    """Registration request body."""
    email: str = Field(description="User email address")
    password: str = Field(min_length=8, description="Password (8+ characters)")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email address")
        return v.lower()


class UserResponse(BaseModel):
    """User info returned after registration (no password)."""
    user_id: str
    email: str
    role: str


class TokenResponse(BaseModel):
    """JWT token returned after login or refresh."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")
