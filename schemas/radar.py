"""
Verilay — Radar Schemas
Mention responses, risk scores, scanning results, and weekly stats.
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PlatformSpread(BaseModel):
    """Breakdown of mention spread across platforms."""
    twitter: int = 0
    reddit: int = 0
    linkedin: int = 0


class MentionResponse(BaseModel):
    """Full mention data for Radar display."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    headline: str
    url: str | None = None
    reach: int
    share_count: int
    severity: str
    platform_spread: dict | None = None
    status: str
    responded_at: datetime | None = None
    response_statement: str | None = None
    created_at: datetime


class RiskScoreResponse(BaseModel):
    """Risk score circle data for the Radar tab."""
    score: int
    level: str       # "High Risk", "Medium Risk", "Low Risk"
    spike: str       # e.g. "+49 in 2 hours"
    mentions_today: int
    reach_this_week: int


class MentionRespondRequest(BaseModel):
    """Request to respond to a mention (Accept/Deny/Modify)."""
    action: str      # "ACCEPTED", "DENIED", or "MODIFIED"
    statement: str | None = None
    # Optional — a sensible default is used when omitted.


class WeeklyStatsResponse(BaseModel):
    """This Week panel in the Radar tab."""
    sentiment_positive_pct: float
    mention_change_pct: float
    top_source: str


class ScanResponse(BaseModel):
    """Response after triggering a news scan."""
    new_mentions: int
    total_mentions: int
    scan_duration_ms: int
