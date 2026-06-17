"""
Verilay — Intelligence Service
Free, dependency-free signal enrichment for the Radar tab:
  • Sentiment   — lexicon-based (upgradeable to Claude later, key-gated)
  • Credibility — source authority tiering
  • Velocity    — acceleration of mentions over time

Everything here is computed at read-time, so it needs no database columns
and no migration.
"""

from datetime import datetime, timezone


# ─────────────────────────────────────────────
# SENTIMENT (lexicon-based)
# ─────────────────────────────────────────────
NEGATIVE_WORDS = {
    "fraud", "fraudulent", "scam", "scandal", "controversy", "accused", "accuse",
    "allegation", "allegations", "lawsuit", "sue", "sued", "fake", "hoax",
    "misleading", "banned", "ban", "fired", "arrest", "arrested", "probe",
    "raid", "investigation", "fine", "penalty", "defamation", "crisis", "loss",
    "losses", "slump", "decline", "criticism", "criticised", "criticized",
    "backlash", "fail", "failure", "fraudster", "illegal", "violation",
    "misconduct", "leak", "leaked", "controversial", "denies", "denied",
    "plunge", "crash", "scrutiny", "warning", "alleged",
}

POSITIVE_WORDS = {
    "backs", "back", "invests", "investing", "investment", "launches", "launch",
    "wins", "win", "award", "awarded", "growth", "profit", "profits", "success",
    "successful", "partnership", "partners", "expands", "expansion", "raises",
    "raised", "milestone", "praised", "praise", "top", "best", "surges", "surge",
    "gains", "gain", "record", "boost", "breakthrough", "honoured", "honored",
    "celebrates", "leads", "leading", "innovation", "innovative", "approval",
    "approved", "strong", "rally", "soars",
}


def analyze_sentiment(text: str) -> dict:
    """Return {'label': positive|negative|neutral, 'score': -1..1}."""
    t = (text or "").lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    total = pos + neg
    norm = round((pos - neg) / total, 2) if total else 0.0
    if pos > neg:
        label = "positive"
    elif neg > pos:
        label = "negative"
    else:
        label = "neutral"
    return {"label": label, "score": norm}


# ─────────────────────────────────────────────
# SOURCE CREDIBILITY
# ─────────────────────────────────────────────
HIGH_CREDIBILITY = {
    "reuters", "associated press", " ap ", "bbc", "the hindu", "indian express",
    "the new york times", "new york times", "bloomberg", "economic times",
    "the economic times", "mint", "livemint", "business standard",
    "hindustan times", "times of india", "ndtv", "cnbc", "the wall street journal",
    "wall street journal", "the guardian", "financial times", "moneycontrol",
    "press trust of india", "pti", "the print", "scroll.in", "the wire",
}
MEDIUM_CREDIBILITY = {
    "google news", "news18", "firstpost", "the quint", "yahoo", "hacker news",
    "india today", "republic", "zee", "abp", "deccan", "telegraph", "forbes",
    "techcrunch", "the verge", "wired",
}


def credibility_for(source: str) -> dict:
    """Return {'tier': high|medium|low, 'weight': float}."""
    s = (source or "").lower()
    if any(h in s for h in HIGH_CREDIBILITY):
        return {"tier": "high", "weight": 1.0}
    if "reddit" in s or "twitter" in s or "/x" in s or s.strip() == "x":
        return {"tier": "low", "weight": 0.5}
    if any(m in s for m in MEDIUM_CREDIBILITY):
        return {"tier": "medium", "weight": 0.75}
    return {"tier": "low", "weight": 0.5}


# ─────────────────────────────────────────────
# VELOCITY (acceleration of mentions)
# ─────────────────────────────────────────────
def compute_velocity(mentions, hours: int = 12) -> dict:
    """
    Bucket mentions into the last `hours` one-hour windows (oldest → newest)
    and report whether coverage is accelerating, steady, or cooling.
    """
    now = datetime.now(timezone.utc)
    buckets = [0] * hours

    for m in mentions:
        ts = getattr(m, "created_at", None)
        if not ts:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta_h = int((now - ts).total_seconds() // 3600)
        if 0 <= delta_h < hours:
            buckets[hours - 1 - delta_h] += 1  # newest in the last slot

    last_hour = buckets[-1] if buckets else 0
    prev_hour = buckets[-2] if len(buckets) >= 2 else 0

    if last_hour > prev_hour:
        trend = "accelerating"
    elif last_hour < prev_hour:
        trend = "cooling"
    else:
        trend = "steady"

    return {
        "buckets": buckets,
        "last_hour": last_hour,
        "prev_hour": prev_hour,
        "trend": trend,
        "window_hours": hours,
    }
