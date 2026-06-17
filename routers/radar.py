"""
Verilay — Radar Router
News scanning, mention management, risk scoring, velocity, and weekly stats.
"""
from uuid import UUID
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.mention import Mention, MentionAction, SeverityLevel, MentionStatus
from models.card import TruthCard, CardStatus
from models.user import User
from schemas.radar import (
    MentionResponse,
    RiskScoreResponse,
    MentionRespondRequest,
    WeeklyStatsResponse,
    ScanResponse,
    VelocityResponse,
)
from services.news_scanner import news_scanner
from services.risk_engine import calculate_risk, get_level, get_spike
from services.intelligence import analyze_sentiment, credibility_for, compute_velocity
from routers.auth import get_current_user

router = APIRouter(prefix="/api/radar", tags=["Radar"])
settings = get_settings()


# Keywords that suggest a reputationally risky / negative mention.
RISK_KEYWORDS = {
    "fraud", "scam", "arrest", "arrested", "fake", "controversy", "allegation",
    "allegations", "accused", "lawsuit", "banned", "leak", "leaked", "scandal",
    "fired", "probe", "raid", "fir", "defamation", "hoax", "misleading",
    "investigation", "fine", "penalty", "ban", "sue", "sued", "fraudulent",
}


def _severity_for(headline: str, reach: int = 0) -> SeverityLevel:
    """Severity from BOTH risk keywords AND engagement reach."""
    text = (headline or "").lower()
    hits = sum(1 for kw in RISK_KEYWORDS if kw in text)

    level = 0  # 0=LOW, 1=MODERATE, 2=URGENT
    if hits >= 2:
        level = 2
    elif hits == 1:
        level = 1

    if reach >= 5000:
        level += 1
    elif reach >= 1000 and level == 0:
        level = 1

    level = min(level, 2)
    return [SeverityLevel.LOW, SeverityLevel.MODERATE, SeverityLevel.URGENT][level]


# ─────────────────────────────────────────────
# GET /api/radar/scan
# ─────────────────────────────────────────────
@router.get("/scan", response_model=ScanResponse)
async def scan_news(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a real-time news scan. Hardened so it never 500s."""
    scan_start = datetime.now(timezone.utc)

    try:
        raw_articles = await news_scanner.scan_all(
            current_user.full_name,
            settings.NEWSDATA_API_KEY,
            settings.GNEWS_API_KEY,
        )
    except Exception as e:
        print(f"[Radar] scan_all failed: {e}")
        raw_articles = []

    new_count = 0
    for article in raw_articles:
        try:
            headline = (article.get("headline") or "").strip()
            if not headline:
                continue

            existing = await db.execute(
                select(Mention.id).where(
                    Mention.user_id == current_user.id,
                    Mention.headline == headline,
                )
            )
            if existing.scalar_one_or_none():
                continue

            reach = int(article.get("reach", 0) or 0)
            platform = article.get("platform", "google")
            engagement = article.get("engagement") or {}

            mention = Mention(
                user_id=current_user.id,
                source=article.get("source", "Unknown"),
                headline=headline,
                url=article.get("url") or None,
                reach=reach,
                share_count=int(article.get("share_count", 0) or 0),
                platform_spread={platform: {"reach": reach, **engagement}},
                severity=_severity_for(headline, reach),
                status=MentionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            db.add(mention)
            new_count += 1
        except Exception as e:
            print(f"[Radar] skipped one article: {e}")
            continue

    await db.commit()

    total = await db.execute(
        select(func.count()).select_from(Mention).where(
            Mention.user_id == current_user.id
        )
    )

    duration_ms = int((datetime.now(timezone.utc) - scan_start).total_seconds() * 1000)

    return ScanResponse(
        new_mentions=new_count,
        total_mentions=total.scalar() or 0,
        scan_duration_ms=duration_ms,
    )


# ─────────────────────────────────────────────
# GET /api/radar/mentions
# ─────────────────────────────────────────────
@router.get("/mentions", response_model=list[MentionResponse])
async def get_mentions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """All mentions for the user, enriched with sentiment + source credibility."""
    result = await db.execute(
        select(Mention)
        .where(Mention.user_id == current_user.id)
        .order_by(desc(Mention.created_at))
    )
    mentions = result.scalars().all()

    out: list[MentionResponse] = []
    for m in mentions:
        mr = MentionResponse.model_validate(m)
        sent = analyze_sentiment(m.headline)
        mr.sentiment = sent["label"]
        mr.sentiment_score = sent["score"]
        mr.credibility = credibility_for(m.source)["tier"]
        out.append(mr)
    return out


# ─────────────────────────────────────────────
# GET /api/radar/velocity
# ─────────────────────────────────────────────
@router.get("/velocity", response_model=VelocityResponse)
async def get_velocity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Is coverage accelerating? Mentions-per-hour over the last 12 hours."""
    result = await db.execute(
        select(Mention).where(Mention.user_id == current_user.id)
    )
    mentions = result.scalars().all()
    return VelocityResponse(**compute_velocity(mentions))


# ─────────────────────────────────────────────
# GET /api/radar/risk-score
# ─────────────────────────────────────────────
@router.get("/risk-score", response_model=RiskScoreResponse)
async def get_risk_score(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate the current risk score for the Radar circle."""
    result = await db.execute(
        select(Mention).where(Mention.user_id == current_user.id)
    )
    mentions = result.scalars().all()
    score = calculate_risk(mentions)
    level = get_level(score)
    spike = get_spike(mentions)

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
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
    """Respond to a mention: Accept, Deny, or Modify (also publishes a Truth Card)."""
    try:
        mention_status = MentionStatus(data.action)
        card_status = CardStatus(data.action)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid action. Must be ACCEPTED, DENIED, or MODIFIED.",
        )

    result = await db.execute(
        select(Mention)
        .where(Mention.id == mention_id)
        .where(Mention.user_id == current_user.id)
    )
    mention = result.scalar_one_or_none()
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")

    if data.statement and data.statement.strip():
        statement = data.statement.strip()
    else:
        defaults = {
            "DENIED": "This claim is false. I deny the allegations made in this report.",
            "MODIFIED": "The facts in this report are partially incorrect. See my correction.",
            "ACCEPTED": "I confirm the accuracy of this report.",
        }
        statement = defaults[data.action]

    mention.status = mention_status
    mention.response_statement = statement
    mention.responded_at = datetime.now(timezone.utc)

    db.add(MentionAction(mention_id=mention.id, action_type=data.action))

    existing_card = await db.execute(
        select(TruthCard)
        .where(TruthCard.user_id == current_user.id)
        .where(TruthCard.mention_id == mention.id)
    )
    card = existing_card.scalar_one_or_none()

    if card:
        card.statement = statement
        card.status = card_status
    else:
        card = TruthCard(
            user_id=current_user.id,
            mention_id=mention.id,
            status=card_status,
            statement=statement,
            news_headline=mention.headline,
            news_source=mention.source,
            news_url=mention.url,
            trust_percentage=0.0,
        )
        db.add(card)

    await db.commit()
    await db.refresh(mention)

    mr = MentionResponse.model_validate(mention)
    sent = analyze_sentiment(mention.headline)
    mr.sentiment = sent["label"]
    mr.sentiment_score = sent["score"]
    mr.credibility = credibility_for(mention.source)["tier"]
    return mr


# ─────────────────────────────────────────────
# GET /api/radar/weekly-stats
# ─────────────────────────────────────────────
@router.get("/weekly-stats", response_model=WeeklyStatsResponse)
async def get_weekly_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the 'This Week' stats for the Radar tab."""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    prev_week_start = now - timedelta(days=14)

    result = await db.execute(
        select(Mention).where(Mention.user_id == current_user.id)
    )
    all_mentions = result.scalars().all()

    this_week = [m for m in all_mentions if m.created_at >= week_start]
    prev_week = [m for m in all_mentions if prev_week_start <= m.created_at < week_start]

    positive = sum(
        1 for m in this_week
        if m.status in (MentionStatus.ACCEPTED, MentionStatus.PENDING)
        and m.severity == SeverityLevel.LOW
    )
    total_tw = len(this_week) or 1
    sentiment_pct = round((positive / total_tw) * 100)

    tw_count = len(this_week)
    pw_count = len(prev_week) or 1
    mention_change = round(((tw_count - pw_count) / pw_count) * 100)

    source_counts: dict[str, int] = {}
    for m in this_week:
        source_counts[m.source] = source_counts.get(m.source, 0) + 1
    top_source = max(source_counts, key=source_counts.get) if source_counts else "N/A"

    return WeeklyStatsResponse(
        sentiment_positive_pct=sentiment_pct,
        mention_change_pct=mention_change,
        top_source=top_source,
    )
