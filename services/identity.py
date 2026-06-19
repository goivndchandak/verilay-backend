"""
Verilay — Identity & Classification Service (Phase 1 foundation)

Free, dependency-free building blocks that turn Radar from a flat name-search
into a categorized threat radar:

  • classify_category() — buckets each mention into a threat/reputation category
  • match_confidence()  — rough 0-100 "is this really about THIS user?" score

Both are heuristic today and upgradeable to an LLM (Claude) later, key-gated —
exactly like the sentiment engine. The category set IS the subcategory taxonomy
the Radar UI groups by.
"""

# Ordered by priority: the first category whose keywords hit wins.
CATEGORY_KEYWORDS = {
    "deepfake": [
        "deepfake", "deep fake", "ai-generated", "ai generated", "morphed",
        "synthetic media", "doctored", "fake video", "fake image", "face swap",
        "cloned voice", "voice clone", "manipulated video",
    ],
    "scam": [
        "scam", "fraud", "ponzi", "phishing", "fake endorsement",
        "crypto giveaway", "investment scam", "duped", "cheated", "fraudulent",
        "fake scheme", "lottery", "impersonation scam",
    ],
    "impersonation": [
        "impersonat", "fake account", "fake profile", "posing as",
        "pretending to be", "fake handle", "parody account", "fake page",
    ],
    "legal": [
        "court", "lawsuit", "sued", "fir ", "arrest", "summon", "probe",
        "sebi", " cbi", " ed ", "case filed", "charges", "verdict", "bail",
        "tribunal", "notice issued", "investigation",
    ],
    "financial": [
        "loan", "default", "npa", "insolvency", "ipo", "funding round",
        "stake", "acquisition", "merger", "bankruptcy", "creditor",
    ],
    "defamation": [
        "accused", "allegation", "scandal", "controversy", "slammed",
        "backlash", "criticised", "criticized", "defam", "trolled", "row over",
    ],
    "positive": [
        "award", "wins", " won ", "honoured", "honored", "launches", "backs",
        "invests", "growth", "success", "milestone", "praised", "felicitated",
        "appointed", "partnership",
    ],
}
CATEGORY_PRIORITY = [
    "deepfake", "scam", "impersonation", "legal",
    "financial", "defamation", "positive",
]

SOCIAL_HINTS = (
    "reddit", "twitter", "/x", " x ", "bluesky", "mastodon",
    "instagram", "facebook", "youtube", "tiktok", "threads",
)


def classify_category(headline: str, source: str = "", platform: str = "") -> str:
    """Return one category from the taxonomy."""
    text = (headline or "").lower()
    for cat in CATEGORY_PRIORITY:
        if any(kw in text for kw in CATEGORY_KEYWORDS[cat]):
            return cat

    blob = f"{platform} {source}".lower()
    if any(h in blob for h in SOCIAL_HINTS):
        return "social"
    return "news"


def match_confidence(
    full_name: str,
    headline: str,
    source: str = "",
    social_links: dict | None = None,
    keywords: list | None = None,
) -> int:
    """
    Rough 0-100 "is this mention actually about the user?" score.

    Heuristic v1 — gets sharper as the user's monitoring context (employer,
    city, aliases, handles) grows, which feeds the `keywords` argument.
    """
    text = (headline or "").lower()
    name = (full_name or "").lower().strip()
    conf = 0

    if name and name in text:
        conf += 55
    else:
        tokens = [t for t in name.split() if len(t) > 2]
        if tokens and all(t in text for t in tokens):
            conf += 45
        else:
            conf += 25  # found by search but full name not in the title

    # A linked social handle appearing in the text is a strong signal.
    for value in (social_links or {}).values():
        handle = str(value or "").lower().strip().lstrip("@")
        if handle and len(handle) > 2 and handle in text:
            conf += 20
            break

    # Context keywords (employer, city, project, aliases) — disambiguates
    # people who share the same name.
    for kw in (keywords or []):
        k = str(kw or "").lower().strip()
        if k and len(k) > 2 and k in text:
            conf += 10

    return min(conf, 100)
