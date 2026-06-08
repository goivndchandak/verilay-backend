"""
Verilay — Search Router
Search people, truth claims, and topics across the platform.
"""

from fastapi import APIRouter, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from database import get_db
from models.user import User
from models.card import TruthCard
from schemas.user import UserSearchResult
from schemas.card import CardResponse, CardUserInfo

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/")
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for users and truth cards matching the query.
    Uses case-insensitive partial matching (ILIKE).
    """
    search_term = f"%{q}%"

    # Search users by full_name or username
    user_result = await db.execute(
        select(User)
        .where(
            or_(
                User.full_name.ilike(search_term),
                User.username.ilike(search_term),
            )
        )
        .limit(20)
    )
    users = user_result.scalars().all()

    # Search cards by statement or news_headline
    from sqlalchemy.orm import selectinload

    card_result = await db.execute(
        select(TruthCard)
        .options(selectinload(TruthCard.user))
        .where(
            or_(
                TruthCard.statement.ilike(search_term),
                TruthCard.news_headline.ilike(search_term),
            )
        )
        .limit(20)
    )
    cards = card_result.scalars().all()

    return {
        "users": [UserSearchResult.model_validate(u) for u in users],
        "cards": [
            CardResponse(
                id=c.id,
                user=CardUserInfo.model_validate(c.user),
                status=c.status.value,
                statement=c.statement,
                news_headline=c.news_headline,
                news_source=c.news_source,
                news_url=c.news_url,
                vouch_count=c.vouch_count,
                counter_count=c.counter_count,
                trust_percentage=c.trust_percentage,
                share_count=c.share_count,
                created_at=c.created_at,
                user_reaction=None,
            )
            for c in cards
        ],
    }
