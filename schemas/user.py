"""
Verilay — User / Profile Schemas
Profile responses, updates, follow actions, and search results.
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserProfile(BaseModel):
    """Full profile response (Profile tab)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    username: str
    email: str
    bio: str | None = None
    profile_picture_url: str | None = None
    social_links: dict | None = None
    is_verified: bool
    verification_tier: int

    # ── Aggregated Stats ──
    claims_resolved: int = 0
    vouch_rate: float = 0.0
    trust_score: int = 0
    followers_count: int = 0
    following_count: int = 0

    created_at: datetime


class UserUpdate(BaseModel):
    """Request to update profile fields."""
    full_name: str | None = None
    bio: str | None = None
    profile_picture_url: str | None = None
    social_links: dict | None = None


class FollowResponse(BaseModel):
    """Response after follow/unfollow action."""
    message: str
    followers_count: int


class UserSearchResult(BaseModel):
    """Search result item for users."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    username: str
    is_verified: bool
    profile_picture_url: str | None = None
