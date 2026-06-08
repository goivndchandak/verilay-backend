"""
Verilay — Radar Router
News scanning, mention management, risk scoring, and weekly stats.
"""
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from config import get_settings
from database import get_db
from models.mention import Mention, MentionAction, SeverityLevel, MentionStatus
from models.user import User
from schemas.radar import (
    MentionResponse,
    RiskScoreResponse,
    MentionRespondRequest,
    WeeklyStatsResponse,
    ScanResponse,
)
from services.news_scanner import news_scanner
from services.risk_engine import calculate_risk, get_level, get_spike
from routers.auth import get_current_user

# Try importing Card model for feed integration
try:
    from models.card import Card
except ImportError:
    Card = None

router = APIRouter(prefix="/api/radar", tags=["Radar"])
settings = get_settings()


# ─────────────────────────────────────────────
# GET /api/radar/scan
# ─────────────────────────────────────────────

@router.get("/scan", response_model=ScanResponse)
async def scan_news(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a real-time news scan for the current user.
    Searches Google News, Reddit, and optional paid APIs.
    """
    scan_start = datetime.now(timezone.utc)
    raw_articles = await news_scanner.scan(current_user.full_name)

    new_count = 0
    for article in raw_articles:
        existing = await db.execute(
            select(Mention).where(
                Mention.user_id == current_user.id,
                Mention.url == article.get("url", ""),
            )
        )
        if existing.scalar_one_or_none():
            continue

        mention = Mention(
            user_id=current_user.id,
            source=article.get("source", "Unknown"),
            headline=article.get("title", ""),
            url=article.get("url", ""),
            reach=article.get("reach", 0),
            severity=SeverityLevel.LOW,
            status=MentionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        db.add(mention)
        new_count += 1

    await db.commit()

    total = await db.execute(
        select(func.count()).select_from(Mention).where(Mention.user_id == current_user.id)
    )

    return ScanResponse(
        new_mentions=new_count,
        total_mentions=total.scalar() or 0,
        scan_duration_ms=int((datetime.now(timezone.utc) - scan_start).total_seconds() * 1000),
    )


# ─────────────────────────────────────────────
# GET /api/radar/mentions
# ─────────────────────────────────────────────

@router.get("/mentions", response_model=list[MentionResponse])
async def get_mentions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    "Get all mentions for the current user, sorted by most recent."
    result = await db.execute(
        select(Mention)
        .where(Mention.user_id == current_user.id)
        .order_by(desc(Mention.created_at))
    )
    mentions = result.scalars().all()
    return [MentionResponse.model_validate(m) for m in mentions]


# ─────────────────────────────────────────────
# GET /api/radar/risk-score
# ─────────────────────────────────────────────

@router.get("/risk-score", response_model=RiskScoreResponse)
async def get_risk_score(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    "Calculate the current risk score for the Radar circle."
    result = await db.execute(
        select(Mention).where(Mention.user_id == current_user.id)
    )
    mentions = result.scalars().all()
    score = calculate_risk(mentions)
    level = get_level(score)
    spike = get_spike(mentions)

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    mentions_today = sum(1 for m in mentions if m.created_at >= today_start)

    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    reach_this_week = sum(m.reach for m in mentions if m.created_at >= week_start)

    return RiskScoreResponse(
        score=score,
        level=level,
        spike=spike,
        mentions_today=mentions_today,
        reach_this_week=reach_this_week,
    )


# ─────────────────────────────────────────────
# POST /api/radar/mentions/{mention_id}/respond
# ─────────────────────────────────────────────

@router.post("/mentions/{mention_id}/respond", response_model=MentionResponse)
async def respond_to_mention(
    mention_id: UUID,
    data: MentionRespondRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    "Respond to a mention: Accept, Deny, or Modify."
    result = await db.execute(
        select(Mention)
        .where(Mention.id == mention_id)
        .where(Mention.user_id == current_user.id)
    )
    mention = result.scalar_one_or_none()
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")

    # Update status
    mention.status = data.action

    # ── FIX: Use user's custom statement, fallback to default only if empty ──
    if data.statement and data.statement.strip():
        custom_statement = data.statement.strip()
    else:
        defaults = {
            "DENIED": "This claim is false. I deny the allegations made in this report.",
            "MODIFIED": "The facts in this report are partially incorrect. See my correction.",
            "ACCEPTED": None,
        }
        custom_statement = defaults.get(data.action)

    mention.response_statement = custom_statement
    mention.responded_at = datetime.now(timezone.utc)

    # ── Create / update truth card for the Feed ──
    if Card is not None:
        try:
            # Check if a card already exists for this mention
            existing_card = await db.execute(
                select(Card).where(Card.mention_id == mention.id)
            )
            card = existing_card.scalar_one_or_none()

            if card:
                # Update existing card with new statement
                card.statement = custom_statement
                card.status = data.action
            else:
                # Create new card
                card = Card(
                    user_id=current_user.id,
                    statement=custom_statement,
                    status=data.action,
                    news_headline=mention.headline,
                    news_source=mention.source,
                    news_url=mention.url,
                    mention_id=mention.id,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(card)
        except Exception:
            pass  # Card creation is best-effort

    await db.commit()
    await db.refresh(mention)

    return MentionResponse.model_validate(mention)


# ─────────────────────────────────────────────
# GET /api/radar/weekly-stats
# ─────────────────────────────────────────────

@router.get("/weekly-stats", response_model=WeeklyStatsResponse)
async def get_weekly_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    "Return the 'This Week' stats for the Radar tab."
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    prev_week_start = now - timedelta(days=14)

    result = await db.execute(
        select(Mention).where(Mention.user_id == current_user.id)
    )
    all_mentions = result.scalars().all()

    this_week = [m for m in all_mentions if m.created_at >= week_start]
    prev_week = [m for m in all_mentions if prev_week_start <= m.created_at < week_start]

    positive = sum(1 for m in this_week if m.status in ("ACCEPTED", "PENDING") and m.severity == SeverityLevel.LOW)
    total_tw = len(this_week) or 1
    sentiment_pct = round((positive / total_tw) * 100)

    tw_count = len(this_week)
    pw_count = len(prev_week) or 1
    mention_change = round(((tw_count - pw_count) / pw_count) * 100)

    source_counts = {}
    for m in this_week:
        source_counts[m.source] = source_counts.get(m.source, 0) + 1
    top_source = max(source_counts, key=source_counts.get) if source_counts else "N/A"

    return WeeklyStatsResponse(
        sentiment_positive_pct=sentiment_pct,
        mention_change_pct=mention_change,
        top_source=top_source,
    )
