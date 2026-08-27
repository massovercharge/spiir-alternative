from typing import Any

from fastapi import APIRouter

from app.services.notification_service import get_household_notifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications() -> dict[str, Any]:
    """List all active proactive notifications and warnings for the household."""
    notifications = get_household_notifications()
    return {
        "count": len(notifications),
        "notifications": notifications,
    }
