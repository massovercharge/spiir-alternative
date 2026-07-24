from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.account_service import list_accounts_with_balances, update_account, get_account_balance_history
from app.auth import get_auth_dependency
from app.schemas.requests import AccountUpdateRequest

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

@router.get("")
def accounts_list() -> list[dict[str, Any]]:
    """List accounts with their real-time calculated balances."""
    return list_accounts_with_balances()

@router.patch("/{account_uid}")
def account_update(account_uid: str, payload: AccountUpdateRequest) -> dict[str, Any]:
    """Update an account."""
    result = update_account(account_uid, payload.name, payload.account_type, payload.savings_category_id)
    if not result:
        raise HTTPException(status_code=404, detail="Account not found")
    return result

@router.get("/{account_uid}/balance_history")
def account_balance_history(account_uid: str, days: int = 365) -> list[dict[str, Any]]:
    """Get the daily balance history for an account."""
    return get_account_balance_history(account_uid, days)
