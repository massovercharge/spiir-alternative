from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session

import app.models as models
from app.models import current_household_id
from app.services.notification_service import get_household_notifications
from app.services.reconciliation_service import (
    dismiss_all_same_account_duplicates,
    dismiss_duplicate_pair,
    get_duplicate_groups_preview,
    resolve_all_household_duplicates,
)


class DismissDuplicateRequest(BaseModel):
    transaction_ids: list[str]


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _get_active_household_id() -> str:
    try:
        return current_household_id.get()
    except LookupError:
        from app.services.notification_service import _get_default_household_id

        return _get_default_household_id()


@router.get("")
def list_notifications() -> dict[str, Any]:
    """List all active proactive notifications and warnings for the household."""
    notifications = get_household_notifications()
    return {
        "count": len(notifications),
        "notifications": notifications,
    }


@router.get("/duplicate-preview")
def preview_duplicates() -> dict[str, Any]:
    """Return all duplicate candidates with metadata on whether they can be merged."""
    hh_id = _get_active_household_id()
    with Session(models.all_models.engine) as session:
        groups = get_duplicate_groups_preview(session, hh_id)

    mergeable_count = sum(1 for g in groups if g.get("can_auto_merge"))
    return {
        "total_groups": len(groups),
        "mergeable_groups_count": mergeable_count,
        "groups": groups,
    }


@router.post("/resolve-duplicates")
def resolve_duplicates() -> dict[str, Any]:
    """Automatically resolve and consolidate all cross-account duplicate transaction pairs."""
    hh_id = _get_active_household_id()
    with Session(models.all_models.engine) as session:
        result = resolve_all_household_duplicates(session, hh_id)
    return result


@router.post("/dismiss-duplicate")
def dismiss_duplicate(body: DismissDuplicateRequest) -> dict[str, Any]:
    """Dismiss a group of transactions as NOT being duplicates."""
    hh_id = _get_active_household_id()
    with Session(models.all_models.engine) as session:
        dismissed_count = dismiss_duplicate_pair(session, hh_id, body.transaction_ids)
    return {
        "status": "success",
        "dismissed_count": dismissed_count,
    }


@router.post("/dismiss-all-duplicates")
def dismiss_all_duplicates() -> dict[str, Any]:
    """Dismiss all current non-mergeable same-account duplicate groups in bulk."""
    hh_id = _get_active_household_id()
    with Session(models.all_models.engine) as session:
        dismissed_count = dismiss_all_same_account_duplicates(session, hh_id)
    return {
        "status": "success",
        "dismissed_count": dismissed_count,
    }
