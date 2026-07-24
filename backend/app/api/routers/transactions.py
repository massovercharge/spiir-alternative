from typing import Any, Annotated, Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from app.auth import get_auth_dependency
from app.transaction_service import (
    get_transaction,
    list_transactions,
    split_allocation,
    update_transactions,
    update_transaction_category,
    link_receipt_to_transaction,
    list_tags
)
from app.schemas.requests import (
    TransactionsUpdateRequest,
    TransactionCategoryUpdateRequest,
    TransactionSplitRequest,
    TransactionLinkReceiptRequest
)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

@router.get("")
def transactions_list(
    limit: Annotated[Optional[int], Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    account_uid: Optional[str] = None,
    search: Optional[str] = None,
    filter_type: Optional[str] = None,
    tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    amount_op: Optional[str] = None,
    amount_value: Optional[float] = None,
    category_id: Optional[str] = None,
) -> dict[str, Any]:
    """List transactions with optional filtering and pagination."""
    return list_transactions(
        limit=limit, offset=offset, account_uid=account_uid, search=search,
        filter_type=filter_type, tag=tag, start_date=start_date, end_date=end_date,
        amount_op=amount_op, amount_value=amount_value, category_id=category_id
    )

@router.get("/{transaction_id}")
def transaction_detail(transaction_id: str) -> dict[str, Any]:
    """Get a single transaction by ID."""
    result = get_transaction(transaction_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result

@router.patch("")
def transactions_update(payload: TransactionsUpdateRequest) -> dict[str, Any]:
    """Apply overrides (category, note, flags) to one or more transactions."""
    ids = [str(x) for x in payload.transaction_ids if str(x).strip()]
    return update_transactions(ids, payload.patch.model_dump(exclude_unset=True))

@router.put("/{transaction_id}/category")
def update_single_transaction_category_endpoint(transaction_id: str, payload: TransactionCategoryUpdateRequest) -> dict[str, Any]:
    """Update category for a single transaction."""
    success = update_transaction_category(transaction_id, payload.category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"success": True}

@router.post("/{transaction_id}/split")
def transaction_split(transaction_id: str, payload: TransactionSplitRequest) -> dict[str, Any]:
    """Split a transaction into multiple allocations."""
    splits = [s.model_dump() for s in payload.splits]
    return split_allocation(transaction_id, splits)

@router.post("/{transaction_id}/link-receipt")
def transaction_link_receipt(transaction_id: str, payload: TransactionLinkReceiptRequest) -> dict[str, Any]:
    """Link a receipt to a transaction and automatically split it into items."""
    return link_receipt_to_transaction(transaction_id, payload.receipt_id)

@router.get("/tags")
def tags_list_endpoint() -> dict[str, list[dict[str, str]]]:
    """Get all tags created by the user."""
    tags = list_tags()
    return {"tags": [{"id": t.id, "name": t.name} for t in tags]}
