"""
Verilay — Auth Router
Email OTP authentication with JWT tokens.
Endpoints: send-otp, verify-otp, register, me
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.user import User
from schemas.auth import (
    SendOTPRequest,
    VerifyOTPRequest,
    RegisterCompleteRequest,
    TokenResponse,
    UserMinimal,
)
from services.otp_service import otp_service

router = APIRouter(prefix="/api/auth", tags=["Auth"])
settings = get_settings()
security = HTTPBearer()


# ── Helper: Create JWT Token ──
def create_access_token(data: dict) -> str:
    """Create a JWT access token with expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Dependency: Get Current User ──
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT from the Authorization header.
    Returns the authenticated User ORM object.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


# ─────────────────────────────────────────────
# POST /api/auth/send-otp
# ─────────────────────────────────────────────
@router.post("/send-otp")
async def send_otp(request: SendOTPRequest):
    """Send a 6-digit OTP to the provided email address."""
    otp = otp_service.send_otp(request.email)
    return {"message": "OTP sent successfully", "email": request.email}


# ─────────────────────────────────────────────
# POST /api/auth/verify-otp
# ─────────────────────────────────────────────
@router.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify the OTP. If user exists, return a JWT token.
    If user doesn't exist, return needs_registration flag.
    """
    if not otp_service.verify_otp(request.email, request.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    # Check if user exists
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None:
        return {"needs_registration": True, "email": request.email}

    # User exists — issue JWT
    token = create_access_token(data={"sub": user.email})
    return TokenResponse(
        access_token=token,
        user=UserMinimal.model_validate(user),
    )


# ─────────────────────────────────────────────
# POST /api/auth/register
# ─────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterCompleteRequest, db: AsyncSession = Depends(get_db)
):
    """
    Register a new user after OTP verification.
    Creates the user and returns a JWT token.
    """
    # Verify OTP again (user must verify before registering)
    if not otp_service.verify_otp(request.email, request.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one.",
        )

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == request.username.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken.",
        )

    # Create new user
    new_user = User(
        full_name=request.full_name,
        username=request.username.lower(),
        email=request.email.lower(),
        is_verified=True,
        verification_tier=1,  # Email verified
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    # Issue JWT
    token = create_access_token(data={"sub": new_user.email})
    return TokenResponse(
        access_token=token,
        user=UserMinimal.model_validate(new_user),
    )


# ─────────────────────────────────────────────
# GET /api/auth/me
# ─────────────────────────────────────────────
@router.get("/me", response_model=UserMinimal)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's basic info."""
    return UserMinimal.model_validate(current_user)
