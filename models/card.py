"""
Verilay — TruthCard & NewsLink Models
Truth cards are the core content unit: a person's response to a rumour/claim.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID

from database import Base


class CardStatus(str, enum.Enum):
    """How the person responded to the claim."""
    DENIED = "DENIED"
    ACCEPTED = "ACCEPTED"
    MODIFIED = "MODIFIED"


class TruthCard(Base):
    """
    A truth card — the person's official response to a news claim/rumour.
    Displayed in the Feed tab and in Profile > Cards.
    """
    __tablename__ = "truth_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Optional link back to the Radar mention this card responds to ──
    # SET NULL so deleting a mention keeps the published card intact.
    mention_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mentions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Card Content ──
    status: Mapped[CardStatus] = mapped_column(Enum(CardStatus), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    # The person's actual quote / statement

    # ── Linked News Article ──
    news_headline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    news_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    news_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ── Trust Metrics (denormalized for fast feed rendering) ──
    vouch_count: Mapped[int] = mapped_column(Integer, default=0)
    counter_count: Mapped[int] = mapped_column(Integer, default=0)
    trust_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="truth_cards")
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    news_links: Mapped[list["NewsLink"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TruthCard {self.status} by {self.user_id}>"


class NewsLink(Base):
    """
    Additional news articles linked to a truth card.
    A card can reference multiple news sources.
    """
    __tablename__ = "news_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("truth_cards.id", ondelete="CASCADE"), nullable=False
    )
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # ── Relationships ──
    card: Mapped["TruthCard"] = relationship(back_populates="news_links")

    def __repr__(self) -> str:
        return f"<NewsLink {self.source}: {self.headline[:40]}>"
