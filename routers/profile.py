"""
Verilay — Profile Router
User profiles, trust stats, truth logs, follow/unfollow.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.user import User
from models.card import TruthCard
from models.follower import Follower
from models.notification import Notification, NotificationType
from schemas.user import UserProfile, UserUpdate, FollowResponse
from schemas.card import CardResponse, CardUserInfo
from services.trust_engine import (
    calculate_vouch_rate,
    calculate_user_trust_score,
)
from routers.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["Profile"])


# ── Helper: Build user stats ──
async def _build_profile(user: User, db: AsyncSession) -> UserProfile:
    """Build a full UserProfile with aggregated stats."""
    # Claims resolved (total cards)
    cards_q = await db.execute(
        select(func.count(TruthCard.id)).where(TruthCard.user_id == user.id)
    )
    claims_resolved = cards_q.scalar() or 0

    # Vouch rate
    vouch_rate = await calculate_vouch_rate(user.id, db)

    # Trust score
    trust_score = await calculate_user_trust_score(user.id, db)

    # Followers count
    followers_q = await db.execute(
        select(func.count(Follower.id)).where(Follower.following_id == user.id)
    )
    followers_count = followers_q.scalar() or 0

    # Following count
    following_q = await db.execute(
        select(func.count(Follower.id)).where(Follower.follower_id == user.id)
    )
    following_count = following_q.scalar() or 0

    return UserProfile(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        bio=user.bio,
        profile_picture_url=user.profile_picture_url,
        social_links=user.social_links,
        is_verified=user.is_verified,
        verification_tier=user.verification_tier,
        claims_resolved=claims_resolved,
        vouch_rate=vouch_rate,
        trust_score=trust_score,
        followers_count=followers_count,
        following_count=following_count,
        created_at=user.created_at,
    )


# ─────────────────────────────────────────────
# GET /api/users/me/stats
# ─────────────────────────────────────────────
@router.get("/me/stats")
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's trust stats (for profile header)."""
    profile = await _build_profile(current_user, db)
    return {
        "claims_resolved": profile.claims_resolved,
        "vouch_rate": profile.vouch_rate,
        "trust_score": profile.trust_score,
        "followers_count": profile.followers_count,
        "following_count": profile.following_count,
    }


# ─────────────────────────────────────────────
# GET /api/users/{username}
# ─────────────────────────────────────────────
@router.get("/{username}", response_model=UserProfile)
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a user's public profile by username."""
    result = await db.execute(
        select(User).where(User.username == username.lower())
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return await _build_profile(user, db)


# ─────────────────────────────────────────────
# PUT /api/users/me
# ─────────────────────────────────────────────
@router.put("/me", response_model=UserProfile)
async def update_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile fields."""
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.bio is not None:
        current_user.bio = data.bio
    if data.profile_picture_url is not None:
        current_user.profile_picture_url = data.profile_picture_url
    if data.social_links is not None:
        current_user.social_links = data.social_links

    await db.flush()
    await db.refresh(current_user)

    return await _build_profile(current_user, db)


# ─────────────────────────────────────────────
# GET /api/users/{username}/truth-log
# ─────────────────────────────────────────────
@router.get("/{username}/truth-log", response_model=list[CardResponse])
async def get_truth_log(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a user's truth log (all cards, most recent first)."""
    result = await db.execute(
        select(User).where(User.username == username.lower())
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cards_q = await db.execute(
        select(TruthCard)
        .options(selectinload(TruthCard.user))
        .where(TruthCard.user_id == user.id)
        .order_by(desc(TruthCard.created_at))
    )
    cards = cards_q.scalars().all()

    return [
        CardResponse(
            id=c.id,
            user=CardUserInfo.model_validate(c.user),
            mention_id=c.mention_id,
            status=c.status.value,
            statement=c.statement,
            news_headline=c.news_headline,
            news_source=c.news_source,
            news_url=c.news_url,
            image_url=c.image_url,
            vouch_count=c.vouch_count,
            counter_count=c.counter_count,
            trust_percentage=c.trust_percentage,
            share_count=c.share_count,
            created_at=c.created_at,
            user_reaction=None,
        )
        for c in cards
    ]


# ─────────────────────────────────────────────
# GET /api/users/{username}/cards
# ─────────────────────────────────────────────
@router.get("/{username}/cards", response_model=list[CardResponse])
async def get_user_cards(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """Get shareable truth cards for the Cards tab."""
    # Same data as truth-log — frontend renders differently
    return await get_truth_log(username, db)


# ─────────────────────────────────────────────
# POST /api/users/{username}/follow
# ─────────────────────────────────────────────
@router.post("/{username}/follow", response_model=FollowResponse)
async def follow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow a user."""
    # Find target user
    result = await db.execute(
        select(User).where(User.username == username.lower())
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    # Check if already following
    existing = await db.execute(
        select(Follower)
        .where(Follower.follower_id == current_user.id)
        .where(Follower.following_id == target.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already following this user")

    # Create follow
    follow = Follower(follower_id=current_user.id, following_id=target.id)
    db.add(follow)

    # Notify the followed user
    notif = Notification(
        user_id=target.id,
        title="New Follower",
        message=f"{current_user.full_name} started following you",
        type=NotificationType.FOLLOW,
        related_id=current_user.id,
    )
    db.add(notif)
    await db.flush()

    # Get new follower count
    count_q = await db.execute(
        select(func.count(Follower.id)).where(Follower.following_id == target.id)
    )
    followers_count = count_q.scalar() or 0

    return FollowResponse(
        message=f"Now following {target.username}",
        followers_count=followers_count,
    )


# ─────────────────────────────────────────────
# DELETE /api/users/{username}/follow
# ─────────────────────────────────────────────
@router.delete("/{username}/follow", response_model=FollowResponse)
async def unfollow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unfollow a user."""
    result = await db.execute(
        select(User).where(User.username == username.lower())
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await db.execute(
        select(Follower)
        .where(Follower.follower_id == current_user.id)
        .where(Follower.following_id == target.id)
    )
    follow = existing.scalar_one_or_none()
    if not follow:
        raise HTTPException(status_code=404, detail="Not following this user")

    await db.delete(follow)
    await db.flush()

    count_q = await db.execute(
        select(func.count(Follower.id)).where(Follower.following_id == target.id)
    )
    followers_count = count_q.scalar() or 0

    return FollowResponse(
        message=f"Unfollowed {target.username}",
        followers_count=followers_count,
    )
