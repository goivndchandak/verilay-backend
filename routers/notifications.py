"""
Verilay — Notifications Router
Bell icon notifications: list, mark read, unread count.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.notification import Notification
from models.user import User
from routers.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# ─────────────────────────────────────────────
# GET /api/notifications/
# ─────────────────────────────────────────────
@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's notifications (most recent 50)."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(desc(Notification.created_at))
        .limit(50)
    )
    notifications = result.scalars().all()

    return [
        {
            "id": str(n.id),
            "title": n.title,
            "message": n.message,
            "type": n.type.value,
            "is_read": n.is_read,
            "related_id": str(n.related_id) if n.related_id else None,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


# ─────────────────────────────────────────────
# GET /api/notifications/unread-count
# ─────────────────────────────────────────────
@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the count of unread notifications (for the badge)."""
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
    )
    count = result.scalar() or 0
    return {"unread_count": count}


# ─────────────────────────────────────────────
# PUT /api/notifications/read
# ─────────────────────────────────────────────
@router.put("/read")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
        .values(is_read=True)
    )
    await db.flush()
    return {"message": "All notifications marked as read"}


# ─────────────────────────────────────────────
# PUT /api/notifications/{notification_id}/read
# ─────────────────────────────────────────────
@router.put("/{notification_id}/read")
async def mark_one_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    await db.flush()
    return {"message": "Notification marked as read"}
