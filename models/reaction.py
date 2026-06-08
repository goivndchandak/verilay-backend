"""
Verilay — Reaction Model
Users can Vouch (agree) or Counter (disagree) on truth cards.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID

from database import Base


class ReactionType(str, enum.Enum):
    """Type of reaction a user can leave on a card."""
    VOUCH = "VOUCH"
    COUNTER = "COUNTER"


class Reaction(Base):
    """
    A user's reaction (vouch or counter) on a truth card.
    Each user can only have ONE reaction per card (enforced by unique constraint).
    """
    __tablename__ = "reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_user_card_reaction"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("truth_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reaction_type: Mapped[ReactionType] = mapped_column(
        Enum(ReactionType), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="reactions")
    card: Mapped["TruthCard"] = relationship(back_populates="reactions")

    def __repr__(self) -> str:
        return f"<Reaction {self.reaction_type} by {self.user_id} on {self.card_id}>"
