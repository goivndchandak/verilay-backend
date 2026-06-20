"""Verilay — Public shareable Truth Card page (Open Graph tagged)."""

import html as _html
from uuid import UUID
from urllib.parse import quote as _q

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.card import TruthCard
from models.user import User

router = APIRouter(tags=["Public"])

_STATUS = {
    "DENIED": ("#EF4444", "rgba(239,68,68,.10)"),
    "ACCEPTED": ("#22C55E", "rgba(34,197,94,.10)"),
    "MODIFIED": ("#EAB308", "rgba(234,179,8,.12)"),
}


def _initials(name):
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


@router.get("/card/{card_id}", response_class=HTMLResponse)
async def public_card(card_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(TruthCard).where(TruthCard.id == card_id))
    card = res.scalar_one_or_none()
    if not card:
        return HTMLResponse("<h1 style='text-align:center;padding:60px;font-family:sans-serif'>Card not found</h1>", status_code=404)

    ures = await db.execute(select(User).where(User.id == card.user_id))
    user = ures.scalar_one_or_none()

    name = user.full_name if user else "Verilay user"
    username = user.username if user else ""
    verified = ' <span style="color:#FF9933">&#10004;</span>' if (user and user.is_verified) else ""
    status = card.status.value if hasattr(card.status, "value") else str(card.status)
    statement = card.statement or ""
    headline = card.news_headline or ""
    source = card.news_source or ""
    image = card.image_url or ""
    color, tint = _STATUS.get(status, ("#FF9933", "rgba(255,153,51,.12)"))
    canonical = str(request.base_url).rstrip("/") + "/card/" + str(card_id)
    desc = statement[:180] if statement else (name + " responded to a claim on Verilay")
    og_image = image or "https://verilay.co.in/cover.png"

    e = _html.escape
    hero = (
        '<div style="position:relative;height:200px;background:#0A1628">'
        + ('<img src="' + e(image) + '" style="width:100%;height:100%;object-fit:cover" alt="">' if image else '')
        + '<div style="position:absolute;top:14px;right:12px;transform:rotate(-11deg);border:3px solid ' + color
        + ';color:' + color + ';background:rgba(255,255,255,.92);font-weight:800;font-size:18px;letter-spacing:2px;padding:6px 14px;border-radius:8px">' + e(status) + '</div></div>'
    )
    news = ''
    if headline:
        news = ('<div style="background:#F1F3F5;border-radius:12px;padding:12px 14px;margin-top:4px">'
                '<div style="font-size:13px;color:#4B5563">&ldquo;' + e(headline) + '&rdquo;</div>'
                '<div style="font-size:11px;color:#9CA3AF;margin-top:3px;font-weight:600">' + e(source) + '</div></div>')
    share = _q('"' + statement[:120] + '" — verified on Verilay\n' + canonical)

    page = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>' + e(name) + ' &mdash; Verilay</title>'
        '<meta name="description" content="' + e(desc) + '">'
        '<meta property="og:type" content="article"><meta property="og:site_name" content="Verilay">'
        '<meta property="og:title" content="' + e(name) + ': ' + e(status) + '">'
        '<meta property="og:description" content="' + e(desc) + '">'
        '<meta property="og:url" content="' + e(canonical) + '">'
        '<meta property="og:image" content="' + e(og_image) + '">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<meta name="twitter:title" content="' + e(name) + ': ' + e(status) + '">'
        '<meta name="twitter:description" content="' + e(desc) + '">'
        '<meta name="twitter:image" content="' + e(og_image) + '">'
        '<style>body{margin:0;font-family:-apple-system,Segoe UI,Inter,sans-serif;background:#0A1628;'
        'display:flex;justify-content:center;padding:18px}.w{width:100%;max-width:460px}'
        '.br{text-align:center;font-size:25px;font-weight:800;color:#fff;margin:6px 0 14px}.br span{color:#FF9933}'
        '.c{background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.45)}'
        '.bd{padding:20px}.av{width:46px;height:46px;border-radius:50%;background:linear-gradient(135deg,#FF9933,#FF6B00);'
        'color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800}'
        '.st{font-size:21px;line-height:1.4;color:#0A1628;font-weight:600;margin:14px 0}'
        '.sb{flex:1;text-align:center;padding:13px;border-radius:12px;font-size:13px;font-weight:700;'
        'color:#fff;text-decoration:none;border:none;cursor:pointer;font-family:inherit}'
        '.cta{display:block;text-align:center;margin-top:14px;padding:14px;border-radius:100px;'
        'background:#fff;color:#0A1628;font-weight:700;text-decoration:none}</style></head><body><div class="w">'
        '<div class="br">Veri<span>lay</span></div><div class="c">' + hero + '<div class="bd">'
        '<div style="display:flex;align-items:center;gap:11px"><div class="av">' + e(_initials(name)) + '</div>'
        '<div><div style="font-weight:700;font-size:15px">' + e(name) + verified + '</div>'
        '<div style="font-size:12px;color:#9CA3AF">@' + e(username) + '</div></div></div>'
        '<div style="display:inline-block;margin-top:12px;padding:5px 12px;border-radius:100px;font-size:11px;'
        'font-weight:800;letter-spacing:.5px;color:' + color + ';background:' + tint + '">' + e(status) + ' &middot; VERIFIED ON VERILAY</div>'
        '<div class="st">&ldquo;' + e(statement) + '&rdquo;</div>' + news +
        '<div style="display:flex;gap:10px;margin-top:16px">'
        '<a class="sb" style="background:#25D366" href="https://wa.me/?text=' + share + '" target="_blank">WhatsApp</a>'
        '<a class="sb" style="background:#0A1628" href="https://twitter.com/intent/tweet?text=' + share + '" target="_blank">Post</a>'
        '<button class="sb" style="background:#FF9933" onclick="cp()">Copy</button></div></div></div>'
        '<a class="cta" href="https://verilay.co.in">Verify your own truth on Verilay &rarr;</a>'
        '<div style="text-align:center;font-size:12px;color:rgba(255,255,255,.5);margin-top:12px">The Layer of Truth the Internet Needs</div>'
        '</div><script>function cp(){var u="' + e(canonical) + '";if(navigator.clipboard){navigator.clipboard.writeText(u);alert("Link copied!");}else{prompt("Copy link:",u);}}</script>'
        '</body></html>'
    )
    return HTMLResponse(page)
