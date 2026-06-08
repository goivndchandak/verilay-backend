"""
Verilay — User & SocialAccount Models
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid as UUID

from database import Base


class PlatformEnum(str, enum.Enum):
    """Supported social platforms for account linking."""
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"


class User(Base):
    """
    Core user table.
    Each verified person/entity on Verilay has one User record.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_tier: Mapped[int] = mapped_column(Integer, default=0)
    # 0 = unverified, 1 = email verified, 2 = identity verified, 3 = org verified

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    truth_cards: Mapped[list["TruthCard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    mentions: Mapped[list["Mention"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class SocialAccount(Base):
    """
    Linked social-media accounts for a user.
    Shown in the Profile > About tab.
    """
    __tablename__ = "social_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[PlatformEnum] = mapped_column(
        Enum(PlatformEnum), nullable=False
    )
    platform_username: Mapped[str] = mapped_column(String(100), nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="social_accounts")

    def __repr__(self) -> str:
        return f"<SocialAccount {self.platform}:{self.platform_username}>"
