"""
Verilay — Mention & MentionAction Models
Radar tab: tracks news mentions about a user and their responses.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID

from database import Base


class SeverityLevel(str, enum.Enum):
    """How urgent a mention is."""
    URGENT = "URGENT"
    MODERATE = "MODERATE"
    LOW = "LOW"


class MentionStatus(str, enum.Enum):
    """User's response status to a mention."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DENIED = "DENIED"
    MODIFIED = "MODIFIED"


class Mention(Base):
    """
    A news mention detected by the Radar.
    Represents a claim/article about the user found online.
    """
    __tablename__ = "mentions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Mention Details ──
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    # e.g. "Indian Express", "Twitter / X"
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ── Metrics ──
    reach: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel), default=SeverityLevel.LOW
    )

    # ── Platform Spread (JSON: {"twitter": 840, "reddit": 320, "linkedin": 95}) ──
    platform_spread: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Response ──
    status: Mapped[MentionStatus] = mapped_column(
        Enum(MentionStatus), default=MentionStatus.PENDING
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    response_statement: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="mentions")
    actions: Mapped[list["MentionAction"]] = relationship(
        back_populates="mention", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Mention {self.source}: {self.headline[:40]}>"


class MentionAction(Base):
    """
    Audit log of actions taken on a mention (accept, deny, modify, etc.).
    """
    __tablename__ = "mention_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mentions.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "ACCEPTED", "DENIED", "MODIFIED", "TAKEDOWN_FILED", "ALERT_SET"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ──
    mention: Mapped["Mention"] = relationship(back_populates="actions")

    def __repr__(self) -> str:
        return f"<MentionAction {self.action_type} on {self.mention_id}>"
