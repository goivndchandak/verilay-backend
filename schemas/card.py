"""
Verilay — Card Schemas
Truth card creation, responses, feed pagination, and reactions.
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CardCreate(BaseModel):
    """Request body to create a new truth card."""
    status: str  # "DENIED", "ACCEPTED", or "MODIFIED"
    statement: str
    news_headline: str | None = None
    news_source: str | None = None
    news_url: str | None = None


class CardUserInfo(BaseModel):
    """Embedded user info shown on each card in the feed."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    username: str
    is_verified: bool
    profile_picture_url: str | None = None


class CardResponse(BaseModel):
    """Full truth card response for feed/detail views."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user: CardUserInfo
    status: str
    statement: str
    news_headline: str | None = None
    news_source: str | None = None
    news_url: str | None = None
    vouch_count: int
    counter_count: int
    trust_percentage: float
    share_count: int
    created_at: datetime
    user_reaction: str | None = None
    # "VOUCH", "COUNTER", or None if the requesting user hasn't reacted


class FeedResponse(BaseModel):
    """Paginated feed response."""
    cards: list[CardResponse]
    total: int
    page: int
    page_size: int


class ReactionResponse(BaseModel):
    """Response after performing a vouch/counter action."""
    message: str
    vouch_count: int
    counter_count: int
    trust_percentage: float


class ShareResponse(BaseModel):
    """Response after sharing a card."""
    message: str
    share_count: int
