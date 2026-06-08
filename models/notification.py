"""
Verilay — Notification Model
Bell icon notifications for vouches, counters, mentions, follows, and alerts.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID

from database import Base


class NotificationType(str, enum.Enum):
    """Categories of notifications shown in the bell dropdown."""
    VOUCH = "VOUCH"
    COUNTER = "COUNTER"
    MENTION = "MENTION"
    FOLLOW = "FOLLOW"
    ALERT = "ALERT"


class Notification(Base):
    """
    A single notification for a user.
    The badge count in the UI shows unread count.
    """
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType), nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    related_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # Points to the related entity (card_id, mention_id, user_id, etc.)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.type}: {self.title}>"
