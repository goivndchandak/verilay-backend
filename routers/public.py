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

# status -> (main color, light tint, label)
_STATUS = {
    "DENIED":   ("#EF4444", "rgba(239,68,68,.10)",  "DENIED"),
    "ACCEPTED": ("#22C55E", "rgba(34,197,94,.10)",  "ACCEPTED"),
    "MODIFIED": ("#EAB308", "rgba(234,179,8,.12)",  "MODIFIED"),
}

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{{TITLE}} — Verilay</title>
<meta name="description" content="{{DESC}}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Verilay">
<meta property="og:title" content="{{TITLE}}">
<meta property="og:description" content="{{DESC}}">
<meta property="og:url" content="{{URL}}">
<meta property="og:image" content="{{OG_IMAGE}}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{TITLE}}">
<meta name="twitter:description" content="{{DESC}}">
<meta name="twitter:image" content="{{OG_IMAGE}}">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:#0A1628;color:#0A1628;display:flex;justify-content:center;padding:18px;min-height:100vh}
.wrap{width:100%;max-width:480px}
.br:-.5px}.brand span{color:#FF9933}
.card{position:relative;background:#fff;border-radius:20hero.noimg{height:96px;background:linear-gradient(135deg,#0A1628,#152238)}
.stamp{position:absolutedisplay:flex;align-items:center;gap:5px}
.vb{display:inline-flex;width:16px;height:16px;background:#FF9933;border-radius:50%;color:#fff;align-items:center;justify-content:center;font-size:10px}
.un{font-size:12px;color:#9CA3AF;margin-top:1px}
.label{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:100px;font-size:11px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:{{COLOR}};background:{{COLOR_LIGHT}};margin-bottom:12px}
.stmt{font-family:'DM Serif Display',serif;font-size:21px;line-height:1.4;color:#0A1628;margin-bottom:16px}
.news{displayin-top:16px}
.sb{flex:1;display:flex;align-items:center;justify-content:center;gap:7px;padding:13px;border-radius:12px;font-size:13px-align:center;font-size:12px;color:rgba(255,255,255,.5);margin-top:14px}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">Veri<span>lay</span></div>
  <div class="card">
    <div class="hero {{HERO_CLS}}">{{IMG_TAG}}<div class="stamp">{{STATUS_UPPER}}</div></div>
    <div class="body">
      <div class="who"><div class="av">{{INITIALS}}</div><div><div class="nm">{{NAME}}{{VERIFIED}}</div><div class="un">@{{USERNAME}}</div></div></div>
      <div class="label">{{STATUS_UPPER}} · Verified on Verilay</div>
      <div class="stmt">&ldquo;{{STATEMENT}}&rdquo;</div>
      {{NEWS_BLOCK}}
      <div class="tag"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 13c0 5-3.5 7.5-7.66 81 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg> Truth verified &amp; rec>
</div>
<script>
function copyLink(){var u="{{URL}}";if(navigator.clipboard){navigator.clipboard.writeText(u).then(ponse)
async def public_card(card_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(TruthCard).where(TruthCard.id == card_id))
    card = res.scalar_one_or_none()
    if not card:
        return HTMLResponse(
            "<h1 style='font-family:sans-serif;text-align:center;padding:60px;color:#0A1628'>Truth Card not found</h1>",
            status_code=404,
        )

    ures = await db.execute(select(User).where(User.id == card.user_id))
    user = ures.scalar_one_or_none()

    name = user.full_name if user else "Verilay user"
    username = user.username if user else ""
    is_verified = bool(user.is_verified) if user else False
    status = card.status.value if hasattr(card.status, "value") else str(card.status)
    statement = card.statement or ""
    head0 1-2 2Z"/><path d="M18 14h-8"/><path d="M15 18h-5"/></svg>'n{canonical}')

    repl = {
        "{{TITLE}}": _html.escape(f"{name}: {status_upper}"),
        "{{DESC}}": _html.escape(desc),
        "{{URL}}": _html.escape(canonical),
        "{{OG_IMAGE}}": _html.escape(og_image),
        "{{IMG_TAG}}": img_tag,
        "{{HERO_CLS}}": hero_cls,
        "{{INITIALS}}": _html.escape(_initials(name)),
        "{{NAME}}": _html.escape(name),
        "{{VERIFIED}}": verified,
        "{{USERNAME}}": _html.escape(username),
        "{{COLOR}}": color,
        "{{COLOR_LIGHT}}": color_light,
        "{{STATUS_UPPER}}": _html.escape(status_upper),
        "{{STATEMENT}}": _html.escape(statement),
        "{{NEWS_BLOCK}}": news_block,
        "{{SHARE_ENC}}": share_text,
    }
    page = _PAGE
    for k, v in repl.items():
        page = page.replace(k, v)
    return HTMLResponse(page)
