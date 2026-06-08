"""
Verilay — Risk Engine
Calculates risk scores for the Radar tab.
"""

from datetime import datetime, timezone, timedelta

SEVERITY_WEIGHTS = {
    "URGENT": 30,
    "MODERATE": 15,
    "LOW": 5,
}


def calculate_risk(mentions) -> int:
    if not mentions:
        return 0
    mentions = list(mentions)
    total_score = 0
    now = datetime.now(timezone.utc)

    for m in mentions:
        severity = getattr(m, "severity", None) or "LOW"
        if hasattr(severity, "value"):
            severity = severity.value
        reach = getattr(m, "reach", 0) or 0
        created_at = getattr(m, "created_at", None)

        base = SEVERITY_WEIGHTS.get(severity, 5)

        if reach > 10000:
            reach_mult = 2.0
        elif reach > 5000:
            reach_mult = 1.5
        elif reach > 1000:
            reach_mult = 1.2
        else:
            reach_mult = 1.0

        recency_mult = 1.0
        if created_at:
            try:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if (now - created_at) < timedelta(hours=6):
                    recency_mult = 1.5
            except Exception:
                pass

        total_score += base * reach_mult * recency_mult

    normalised = min(int(total_score / 1.5), 100)
    return max(normalised, 0)


def get_level(score: int) -> str:
    if score >= 60:
        return "High Risk"
    elif score >= 30:
        return "Medium Risk"
    else:
        return "Low Risk"


def get_spike(mentions, hours: int = 2) -> str:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    recent_count = 0

    for m in mentions:
        created_at = getattr(m, "created_at", None)
        if created_at:
            try:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if created_at >= cutoff:
                    recent_count += 1
            except Exception:
                continue

    return f"+{recent_count} in {hours} hours"