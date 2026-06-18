"""
Verilay — Feed Router
Following and Trending feeds with paginated truth cards.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.card import TruthCard
from models.follower import Follower
from models.reaction import Reaction
from models.user import User
from schemas.card import CardResponse, CardUserInfo, FeedResponse
from routers.auth import get_current_user

router = APIRouter(prefix="/api/feed", tags=["Feed"])


def build_card_response(card: TruthCard, user_reaction: str | None = None) -> CardResponse:
    """Convert a TruthCard ORM object to a CardResponse schema."""
    return CardResponse(
        id=card.id,
        user=CardUserInfo.model_validate(card.user),
        mention_id=card.mention_id,
        status=card.status.value if hasattr(card.status, "value") else card.status,
        statement=card.statement,
        news_headline=card.news_headline,
        news_source=card.news_source,
        news_url=card.news_url,
        image_url=card.image_url,
        vouch_count=card.vouch_count,
        counter_count=card.counter_count,
        trust_percentage=card.trust_percentage,
        share_count=card.share_count,
        created_at=card.created_at,
        user_reaction=user_reaction,
    )


# ─────────────────────────────────────────────
# GET /api/feed/following
# ─────────────────────────────────────────────
@router.get("/following", response_model=FeedResponse)
async def feed_following(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get truth cards from users the current user follows.
    Sorted by most recent first. Includes the current user's reaction.
    """
    # Get list of followed user IDs
    followed_q = await db.execute(
        select(Follower.following_id).where(Follower.follower_id == current_user.id)
    )
    followed_ids = [row[0] for row in followed_q.all()]

    # Include own cards in the feed
    followed_ids.append(current_user.id)

    # Count total
    count_result = await db.execute(
        select(func.count(TruthCard.id)).where(TruthCard.user_id.in_(followed_ids))
    )
    total = count_result.scalar() or 0

    # Fetch cards with user relationship
    offset = (page - 1) * page_size
    result = await db.execute(
        select(TruthCard)
        .options(selectinload(TruthCard.user))
        .where(TruthCard.user_id.in_(followed_ids))
        .order_by(desc(TruthCard.created_at))
        .offset(offset)
        .limit(page_size)
    )
    cards = result.scalars().all()

    # Get current user's reactions for these cards
    card_ids = [c.id for c in cards]
    reactions_q = await db.execute(
        select(Reaction.card_id, Reaction.reaction_type)
        .where(Reaction.user_id == current_user.id)
        .where(Reaction.card_id.in_(card_ids))
    )
    reaction_map = {row[0]: row[1].value for row in reactions_q.all()}

    # Build response
    card_responses = [
        build_card_response(card, reaction_map.get(card.id))
        for card in cards
    ]

    return FeedResponse(
        cards=card_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


# ─────────────────────────────────────────────
# GET /api/feed/trending
# ─────────────────────────────────────────────
@router.get("/trending", response_model=FeedResponse)
async def feed_trending(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get trending truth cards sorted by total engagement (vouch + counter count).
    Public endpoint — no auth required.
    """
    # Count total
    count_result = await db.execute(select(func.count(TruthCard.id)))
    total = count_result.scalar() or 0

    # Fetch cards sorted by engagement
    offset = (page - 1) * page_size
    result = await db.execute(
        select(TruthCard)
        .options(selectinload(TruthCard.user))
        .order_by(desc(TruthCard.vouch_count + TruthCard.counter_count))
        .offset(offset)
        .limit(page_size)
    )
    cards = result.scalars().all()

    card_responses = [build_card_response(card) for card in cards]

    return FeedResponse(
        cards=card_responses,
        total=total,
        page=page,
        page_size=page_size,
    )
