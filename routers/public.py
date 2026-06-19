"""
Verilay — Public Router
Server-rendered, shareable Truth Card pages with Open Graph tags, so links
pasted into WhatsApp / Instagram / X / etc. show a rich preview (title, image,
description). Social scrapers don't run JavaScript, so these tags MUST be in the
server's initial HTML — which is exactly what this page provides.

Public (no auth): anyone with the link can view the card.
"""

import html as _html
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.card import TruthCard
from models.user import User

router = APIRouter(tags=["Public"])

_STATUS_COLOR = {"DENIED": "#EF4444", "ACCEPTED": "#22C55E", "MODIFIED": "#EAB308"}
_STATUS_LABEL = {"DENIED": "Denied", "ACCEPTED": "Confirmed", "MODIFIED": "Clarified"}

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — Verilay</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Verilay">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{image}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;background:#F7F8FA;color:#0A1628;display:flex;justify-content:center;padding:20px;min-height:100vh}}
.wrap{{width:100%;max-width:480px}}
.brand{{text-align:center;font-size:24px;font-weight:800;margin:8px 0 18px}}.brand span{{color:#FF9933}}
.card{{background:#fff;border-radius:18px;box-shadow:0 8px 30px rgba(10,22,40,.10);overflow:hidden;border:1px solid #EEF0F3}}
.card img{{width:100%;height:200px;object-fit:cover;display:block}}
.body{{padding:20px}}
.who{{display:flex;align-items:center;gap:10px;margin-bottom:14px}}
.av{{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#FF9933,#FF6B00);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700}}
.nm{{font-weight:700;font-size:15px}}.un{{font-size:12px;color:#9CA3AF}}
.badge{{display:inline-block;padding:5px 12px;border-radius:100px;font-size:11px;font-weight:800;letter-spacing:.4px;text-transform:uppercase;color:#fff;margin-bottom:12px}}
.stmt{{font-size:16px;line-height:1.55;margin-bottom:14px}}
.news{{background:#F1F3F5;border-radius:12px;padding:12px 14px;font-size:13px;color:#4B5563}}
.news .src{{font-size:11px;color:#9CA3AF;margin-top:3px}}
.cta{{display:block;text-align:center;margin-top:18px;padding:14px;border-radius:100px;background:#FF9933;color:#fff;font-weight:700;text-decoration:none}}
.foot{{text-align:center;font-size:12px;color:#9CA3AF;margin-top:14px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">Veri<span>lay</span></div>
  <div class="card">
    {img_tag}
    <div class="body">
      <div class="who"><div class="av">{initials}</div><div><div class="nm">{name}{verified}</div><div class="un">@{username}</div></div></div>
      <div class="badge" style="background:{color}">{status_label}</div>
      <div class="stmt">&ldquo;{statement}&rdquo;</div>
      {news_block}
    </div>
  </div>
  <a class="cta" href="https://verilay.co.in">Verify your own truth on Verilay →</a>
  <div class="foot">The Layer of Truth the Internet Needs</div>
</div>
</body>
</html>"""


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@router.get("/card/{card_id}", response_class=HTMLResponse)
async def public_card(card_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(TruthCard).where(TruthCard.id == card_id))
    card = res.scalar_one_or_none()
    if not card:
        return HTMLResponse(
            "<h1 style='font-family:sans-serif;text-align:center;padding:60px'>Truth Card not found</h1>",
            status_code=404,
        )

    ures = await db.execute(select(User).where(User.id == card.user_id))
    user = ures.scalar_one_or_none()

    name = (user.full_name if user else "Verilay user")
    username = (user.username if user else "")
    is_verified = bool(user.is_verified) if user else False
    status = card.status.value if hasattr(card.status, "value") else str(card.status)
    statement = card.statement or ""
    headline = card.news_headline or ""
    source = card.news_source or ""
    image = card.image_url or ""

    canonical = str(request.base_url).rstrip("/") + f"/card/{card_id}"
    color = _STATUS_COLOR.get(status, "#FF9933")
    status_label = _STATUS_LABEL.get(status, status.title())
    desc = (statement[:180] if statement else f"{name} responded to a claim on Verilay")

    img_tag = f'<img src="{_html.escape(image)}" alt="">' if image else ""
    og_image = image or "https://verilay.co.in/cover.png"
    verified = ' <span style="color:#FF9933">✔</span>' if is_verified else ""
    news_block = ""
    if headline:
        news_block = (
            f'<div class="news">&ldquo;{_html.escape(headline)}&rdquo;'
            f'<div class="src">{_html.escape(source)}</div></div>'
        )

    page = _PAGE.format(
        title=_html.escape(f"{name}: {status_label}"),
        desc=_html.escape(desc),
        url=_html.escape(canonical),
        image=_html.escape(og_image),
        img_tag=img_tag,
        initials=_html.escape(_initials(name)),
        name=_html.escape(name),
        verified=verified,
        username=_html.escape(username),
        color=color,
        status_label=_html.escape(status_label),
        statement=_html.escape(statement),
        news_block=news_block,
    )
    return HTMLResponse(page)
