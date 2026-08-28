from typing import Any

from fastapi import APIRouter
from sqlmodel import Session

from app.models import current_household_id, engine
from app.services.notification_service import get_household_notifications
from app.services.reconciliation_service import resolve_all_household_duplicates

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications() -> dict[str, Any]:
    """List all active proactive notifications and warnings for the household."""
    notifications = get_household_notifications()
    return {
        "count": len(notifications),
        "notifications": notifications,
    }


@router.post("/resolve-duplicates")
def resolve_duplicates() -> dict[str, Any]:
    """Automatically resolve and consolidate all duplicate transaction pairs for the active household."""
    try:
        hh_id = current_household_id.get()
    except LookupError:
        from app.services.notification_service import _get_default_household_id
        hh_id = _get_default_household_id()

    with Session(engine) as session:
        result = resolve_all_household_duplicates(session, hh_id)
    return result
