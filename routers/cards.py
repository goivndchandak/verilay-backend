"""
Verilay — Cards Router
CRUD for truth cards, vouch/counter reactions, and sharing.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.card import TruthCard, CardStatus
from models.reaction import Reaction, ReactionType
from models.user import User
from models.notification import Notification, NotificationType
from schemas.card import (
    CardCreate,
    CardResponse,
    CardUserInfo,
    ReactionResponse,
    ShareResponse,
)
from services.trust_engine import calculate_trust_percentage
from routers.auth import get_current_user

router = APIRouter(prefix="/api/cards", tags=["Cards"])


# ─────────────────────────────────────────────
# POST /api/cards/
# ─────────────────────────────────────────────
@router.post("/", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    data: CardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new truth card (respond to a claim)."""
    # Validate status
    try:
        card_status = CardStatus(data.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in CardStatus]}",
        )

    new_card = TruthCard(
        user_id=current_user.id,
        status=card_status,
        statement=data.statement,
        news_headline=data.news_headline,
        news_source=data.news_source,
        news_url=data.news_url,
        trust_percentage=0.0,
    )
    db.add(new_card)
    await db.flush()
    await db.refresh(new_card)

    return CardResponse(
        id=new_card.id,
        user=CardUserInfo.model_validate(current_user),
        status=new_card.status.value,
        statement=new_card.statement,
        news_headline=new_card.news_headline,
        news_source=new_card.news_source,
        news_url=new_card.news_url,
        vouch_count=0,
        counter_count=0,
        trust_percentage=0.0,
        share_count=0,
        created_at=new_card.created_at,
        user_reaction=None,
    )


# ─────────────────────────────────────────────
# GET /api/cards/{card_id}
# ─────────────────────────────────────────────
@router.get("/{card_id}", response_model=CardResponse)
async def get_card(card_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single truth card by ID."""
    result = await db.execute(
        select(TruthCard)
        .options(selectinload(TruthCard.user))
        .where(TruthCard.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return CardResponse(
        id=card.id,
        user=CardUserInfo.model_validate(card.user),
        status=card.status.value,
        statement=card.statement,
        news_headline=card.news_headline,
        news_source=card.news_source,
        news_url=card.news_url,
        vouch_count=card.vouch_count,
        counter_count=card.counter_count,
        trust_percentage=card.trust_percentage,
        share_count=card.share_count,
        created_at=card.created_at,
        user_reaction=None,
    )


# ── Helper: Process Reaction ──
async def _process_reaction(
    card_id: UUID,
    reaction_type: ReactionType,
    current_user: User,
    db: AsyncSession,
) -> ReactionResponse:
    """Handle vouch/counter logic with toggle support."""
    # Get the card
    result = await db.execute(select(TruthCard).where(TruthCard.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check existing reaction
    result = await db.execute(
        select(Reaction)
        .where(Reaction.user_id == current_user.id)
        .where(Reaction.card_id == card_id)
    )
    existing = result.scalar_one_or_none()

    message = ""

    if existing:
        if existing.reaction_type == reaction_type:
            # Same reaction — toggle OFF (remove it)
            await db.delete(existing)
            if reaction_type == ReactionType.VOUCH:
                card.vouch_count = max(0, card.vouch_count - 1)
            else:
                card.counter_count = max(0, card.counter_count - 1)
            message = f"{reaction_type.value} removed"
        else:
            # Different reaction — switch it
            old_type = existing.reaction_type
            existing.reaction_type = reaction_type
            if old_type == ReactionType.VOUCH:
                card.vouch_count = max(0, card.vouch_count - 1)
                card.counter_count += 1
            else:
                card.counter_count = max(0, card.counter_count - 1)
                card.vouch_count += 1
            message = f"Changed to {reaction_type.value}"
    else:
        # New reaction
        new_reaction = Reaction(
            user_id=current_user.id,
            card_id=card_id,
            reaction_type=reaction_type,
        )
        db.add(new_reaction)
        if reaction_type == ReactionType.VOUCH:
            card.vouch_count += 1
        else:
            card.counter_count += 1
        message = f"{reaction_type.value} recorded"

        # Create notification for card owner
        if card.user_id != current_user.id:
            notif = Notification(
                user_id=card.user_id,
                title=f"New {reaction_type.value.lower()}",
                message=f"{current_user.full_name} {reaction_type.value.lower()}ed your truth card",
                type=NotificationType.VOUCH if reaction_type == ReactionType.VOUCH else NotificationType.COUNTER,
                related_id=card.id,
            )
            db.add(notif)

    # Recalculate trust percentage
    card.trust_percentage = calculate_trust_percentage(
        card.vouch_count, card.counter_count
    )
    await db.flush()

    return ReactionResponse(
        message=message,
        vouch_count=card.vouch_count,
        counter_count=card.counter_count,
        trust_percentage=card.trust_percentage,
    )


# ─────────────────────────────────────────────
# POST /api/cards/{card_id}/vouch
# ─────────────────────────────────────────────
@router.post("/{card_id}/vouch", response_model=ReactionResponse)
async def vouch_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Vouch for a truth card (agree with the person's statement)."""
    return await _process_reaction(card_id, ReactionType.VOUCH, current_user, db)


# ─────────────────────────────────────────────
# POST /api/cards/{card_id}/counter
# ─────────────────────────────────────────────
@router.post("/{card_id}/counter", response_model=ReactionResponse)
async def counter_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Counter a truth card (disagree with the person's statement)."""
    return await _process_reaction(card_id, ReactionType.COUNTER, current_user, db)


# ─────────────────────────────────────────────
# DELETE /api/cards/{card_id}/reaction
# ─────────────────────────────────────────────
@router.delete("/{card_id}/reaction", response_model=ReactionResponse)
async def remove_reaction(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the current user's reaction from a card."""
    result = await db.execute(select(TruthCard).where(TruthCard.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    result = await db.execute(
        select(Reaction)
        .where(Reaction.user_id == current_user.id)
        .where(Reaction.card_id == card_id)
    )
    reaction = result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=404, detail="No reaction to remove")

    # Decrement count
    if reaction.reaction_type == ReactionType.VOUCH:
        card.vouch_count = max(0, card.vouch_count - 1)
    else:
        card.counter_count = max(0, card.counter_count - 1)

    await db.delete(reaction)
    card.trust_percentage = calculate_trust_percentage(
        card.vouch_count, card.counter_count
    )
    await db.flush()

    return ReactionResponse(
        message="Reaction removed",
        vouch_count=card.vouch_count,
        counter_count=card.counter_count,
        trust_percentage=card.trust_percentage,
    )


# ─────────────────────────────────────────────
# POST /api/cards/{card_id}/share
# ─────────────────────────────────────────────
@router.post("/{card_id}/share", response_model=ShareResponse)
async def share_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Track a card share action."""
    result = await db.execute(select(TruthCard).where(TruthCard.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    card.share_count += 1
    await db.flush()

    return ShareResponse(message="Shared successfully", share_count=card.share_count)
