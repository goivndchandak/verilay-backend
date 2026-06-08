"""
Verilay — Trust Engine
Calculates trust percentages for cards and aggregate trust scores for users.
"""

from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


def calculate_trust_percentage(vouch_count: int, counter_count: int) -> float:
    """
    Calculate the trust percentage for a single truth card.
    Formula: vouches / (vouches + counters) * 100
    Returns 0.0 if there are no reactions at all.
    """
    total = vouch_count + counter_count
    if total == 0:
        return 0.0
    return round((vouch_count / total) * 100, 1)


async def calculate_vouch_rate(user_id: UUID, db: AsyncSession) -> float:
    """
    Calculate the user's average vouch rate across all their truth cards.
    This is the "Vouch Rate" shown on the profile — the avg trust_percentage.
    """
    from models.card import TruthCard

    result = await db.execute(
        select(func.avg(TruthCard.trust_percentage))
        .where(TruthCard.user_id == user_id)
    )
    avg = result.scalar()
    return round(avg, 1) if avg else 0.0


async def calculate_user_trust_score(user_id: UUID, db: AsyncSession) -> int:
    """
    Calculate an overall trust score (0-100) for a user.
    Based on: vouch rate, number of cards, and verification tier.
    """
    from models.card import TruthCard
    from models.user import User

    # Get vouch rate
    vouch_rate = await calculate_vouch_rate(user_id, db)

    # Get card count
    result = await db.execute(
        select(func.count(TruthCard.id)).where(TruthCard.user_id == user_id)
    )
    card_count = result.scalar() or 0

    # Get verification tier
    result = await db.execute(
        select(User.verification_tier).where(User.id == user_id)
    )
    tier = result.scalar() or 0

    # ── Score formula ──
    # Base: vouch rate contributes up to 60 points
    base_score = (vouch_rate / 100) * 60

    # Activity bonus: up to 20 points (1 point per card, max 20)
    activity_bonus = min(card_count, 20)

    # Verification bonus: up to 20 points
    verification_bonus = tier * 5  # Tier 0=0, 1=5, 2=10, 3=15, 4=20

    total = base_score + activity_bonus + verification_bonus
    return min(int(round(total)), 100)
