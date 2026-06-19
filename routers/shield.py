"""
Verilay — Shield Router
Advanced protection tools: response cards, denial statements, takedowns, exports, alerts.
"""

from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.mention import Mention, MentionAction, MentionStatus
from models.card import TruthCard, CardStatus
from models.notification import Notification, NotificationType
from models.user import User
from schemas.card import CardResponse, CardUserInfo
from routers.auth import get_current_user

router = APIRouter(prefix="/api/shield", tags=["Shield"])


# ── Helper: Get mention for current user ──
async def _get_user_mention(
    mention_id: UUID, current_user: User, db: AsyncSession
) -> Mention:
    result = await db.execute(
        select(Mention)
        .where(Mention.id == mention_id)
        .where(Mention.user_id == current_user.id)
    )
    mention = result.scalar_one_or_none()
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")
    return mention


# ─────────────────────────────────────────────
# POST /api/shield/response-card
# ─────────────────────────────────────────────
@router.post("/response-card", response_model=CardResponse)
async def generate_response_card(
    mention_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Auto-generate a Truth Card from a radar mention.
    Creates a DENIED card with the mention's headline as the linked news.
    """
    mention = await _get_user_mention(mention_id, current_user, db)

    # Create a truth card
    card = TruthCard(
        user_id=current_user.id,
        mention_id=mention.id,
        status=CardStatus.DENIED,
        statement=f"This claim is false. I deny the allegations made in this report.",
        news_headline=mention.headline,
        news_source=mention.source,
        news_url=mention.url,
        image_url=mention.image_url,
        trust_percentage=0.0,
    )
    db.add(card)

    # Mark mention as denied
    mention.status = MentionStatus.DENIED
    mention.responded_at = datetime.now(timezone.utc)

    # Log action
    action = MentionAction(mention_id=mention.id, action_type="RESPONSE_CARD_CREATED")
    db.add(action)

    await db.flush()
    await db.refresh(card)

    return CardResponse(
        id=card.id,
        user=CardUserInfo.model_validate(current_user),
        status=card.status.value,
        statement=card.statement,
        news_headline=card.news_headline,
        news_source=card.news_source,
        news_url=card.news_url,
        vouch_count=0,
        counter_count=0,
        trust_percentage=0.0,
        share_count=0,
        created_at=card.created_at,
        user_reaction=None,
    )


# ─────────────────────────────────────────────
# POST /api/shield/denial-statement
# ─────────────────────────────────────────────
@router.post("/denial-statement")
async def draft_denial_statement(
    mention_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a drafted denial statement for a mention.
    Returns a template the user can edit before publishing.
    """
    mention = await _get_user_mention(mention_id, current_user, db)

    statement = (
        f"I, {current_user.full_name}, categorically deny the claims made in the article "
        f"titled \"{mention.headline}\" published by {mention.source}. "
        f"These allegations are factually incorrect and misleading. "
        f"I reserve the right to take appropriate legal action against "
        f"the publication and distribution of this false information."
    )

    return {
        "mention_id": str(mention.id),
        "headline": mention.headline,
        "source": mention.source,
        "drafted_statement": statement,
    }


# ─────────────────────────────────────────────
# POST /api/shield/takedown
# ─────────────────────────────────────────────
@router.post("/takedown")
async def file_takedown(
    mention_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """File a takedown request for a mention."""
    mention = await _get_user_mention(mention_id, current_user, db)

    # Log takedown action
    action = MentionAction(mention_id=mention.id, action_type="TAKEDOWN_FILED")
    db.add(action)
    await db.flush()

    return {
        "message": "Takedown request filed successfully",
        "mention_id": str(mention.id),
        "headline": mention.headline,
        "source": mention.source,
        "status": "TAKEDOWN_FILED",
    }


# ─────────────────────────────────────────────
# POST /api/shield/export-pdf
# ─────────────────────────────────────────────
@router.post("/export-pdf")
async def export_evidence_pdf(
    mention_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export evidence as a PDF report (placeholder for v2)."""
    mention = await _get_user_mention(mention_id, current_user, db)

    return {
        "message": "PDF export feature coming soon in v2",
        "mention_id": str(mention.id),
        "headline": mention.headline,
    }


# ─────────────────────────────────────────────
# POST /api/shield/alert
# ─────────────────────────────────────────────
@router.post("/alert")
async def set_alert(
    mention_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set an alert to monitor a mention for further spread."""
    mention = await _get_user_mention(mention_id, current_user, db)

    # Log alert action
    action = MentionAction(mention_id=mention.id, action_type="ALERT_SET")
    db.add(action)

    # Create notification
    notif = Notification(
        user_id=current_user.id,
        title="Alert Set",
        message=f"You\'ll be notified about updates on: {mention.headline[:80]}",
        type=NotificationType.ALERT,
        related_id=mention.id,
    )
    db.add(notif)
    await db.flush()

    return {
        "message": "Alert set successfully. You'll be notified of changes.",
        "mention_id": str(mention.id),
        "headline": mention.headline,
    }
