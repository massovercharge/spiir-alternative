from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_auth_dependency
from app.recurring_service import (
    create_recurring,
    delete_recurring,
    detect_recurring,
    list_recurring,
)
from app.schemas.requests import RecurringCreateRequest

router = APIRouter(prefix="/api/recurring", tags=["recurring"])

@router.get("")
def recurring_list() -> list[dict[str, Any]]:
    """List all recurring transactions."""
    return list_recurring()

@router.post("")
def recurring_create(payload: RecurringCreateRequest) -> dict[str, Any]:
    """Create a manual recurring transaction."""
    return create_recurring(payload.model_dump())

@router.delete("/{rtx_id}")
def recurring_delete(rtx_id: str) -> dict[str, str]:
    """Delete/deactivate a recurring transaction."""
    if not delete_recurring(rtx_id):
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    return {"status": "deleted"}

@router.post("/detect")
def recurring_detect() -> list[dict[str, Any]]:
    """Detect and propose recurring transactions based on history."""
    return detect_recurring()
