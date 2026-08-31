from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session

from app.models import current_household_id, engine
from app.schemas.requests import AccountUpdateRequest
from app.services.account_service import (
    get_account_balance_history,
    list_accounts_with_balances,
    update_account,
)
from app.services.reconciliation_service import merge_accounts

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("")
def accounts_list() -> list[dict[str, Any]]:
    """List accounts with their real-time calculated balances."""
    return list_accounts_with_balances()


@router.patch("/{account_uid}")
def account_update(account_uid: str, payload: AccountUpdateRequest) -> dict[str, Any]:
    """Update an account."""
    result = update_account(
        account_uid, payload.name, payload.account_type, payload.savings_category_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Account not found")
    return result


@router.get("/{account_uid}/balance_history")
def account_balance_history(account_uid: str, days: int = 365) -> list[dict[str, Any]]:
    """Get the daily balance history for an account."""
    return get_account_balance_history(account_uid, days)


@router.post("/{target_uid}/merge-from/{source_uid}")
def account_merge(target_uid: str, source_uid: str) -> dict[str, Any]:
    """Merge historical postings from source_uid into target_uid and reconcile duplicates."""
    try:
        hh_id = current_household_id.get()
    except LookupError:
        from app.services.notification_service import _get_default_household_id

        hh_id = _get_default_household_id()

    with Session(engine) as session:
        try:
            return merge_accounts(
                session, hh_id, source_account_uid=source_uid, target_account_uid=target_uid
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
