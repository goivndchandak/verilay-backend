"""
Verilay — Auth Schemas
OTP send/verify, registration, and token responses.
"""

from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict


class SendOTPRequest(BaseModel):
    """Request to send a one-time password to an email."""
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    """Request to verify an OTP (for existing users)."""
    email: EmailStr
    otp: str


class RegisterCompleteRequest(BaseModel):
    """Request to register a new user and verify OTP in one step."""
    email: EmailStr
    otp: str
    full_name: str
    username: str


class UserMinimal(BaseModel):
    """Minimal user info returned with token."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    username: str
    email: str
    is_verified: bool
    profile_picture_url: str | None = None


class TokenResponse(BaseModel):
    """JWT token response after successful auth."""
    access_token: str
    token_type: str = "bearer"
    user: UserMinimal
