"""Transaction service — CRUD for transactions, fully backed by SQLite."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select, col

from .database import Account, Transaction, engine


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_transactions(
    *,
    limit: int | None = None,
    offset: int = 0,
    account_uid: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Return paginated transactions with optional filters."""
    with Session(engine) as db:
        query = select(Transaction).order_by(
            col(Transaction.booking_date).desc(),
            col(Transaction.id).desc(),
        )

        if account_uid:
            query = query.where(Transaction.account_uid == account_uid)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                col(Transaction.original_description).ilike(pattern)
                | col(Transaction.custom_note).ilike(pattern)
            )

        # Get total count (before pagination)
        count_query = select(Transaction)
        if account_uid:
            count_query = count_query.where(Transaction.account_uid == account_uid)
        if search:
            count_query = count_query.where(
                col(Transaction.original_description).ilike(f"%{search}%")
                | col(Transaction.custom_note).ilike(f"%{search}%")
            )
        total_count = len(db.exec(count_query).all())

        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        transactions = db.exec(query).all()
        accounts = {acc.uid: acc for acc in db.exec(select(Account)).all()}

    return {
        "generated_at": _utcnow_iso(),
        "transaction_count": total_count,
        "transactions": [
            _serialize_transaction(tx, accounts.get(tx.account_uid))
            for tx in transactions
        ],
        "limit": limit,
        "offset": offset,
    }


def get_transaction(transaction_id: str) -> dict[str, Any] | None:
    """Return a single transaction by ID."""
    with Session(engine) as db:
        tx = db.get(Transaction, transaction_id)
        if tx is None:
            return None
        account = db.get(Account, tx.account_uid)
    return _serialize_transaction(tx, account)


# ---------------------------------------------------------------------------
# Write (overrides)
# ---------------------------------------------------------------------------

def update_transactions(transaction_ids: list[str], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a patch (category, note, etc.) to one or more transactions."""
    if not transaction_ids:
        raise ValueError("No transactions selected")

    now = _utcnow_iso()
    updated = 0

    with Session(engine) as db:
        for tx_id in transaction_ids:
            tx = db.get(Transaction, tx_id)
            if tx is None:
                continue

            if "category_id" in patch:
                tx.category_id = patch["category_id"] or None

            if "custom_note" in patch:
                tx.custom_note = patch["custom_note"] or None

            if "is_extraordinary" in patch:
                tx.is_extraordinary = bool(patch["is_extraordinary"])

            if "is_excluded" in patch:
                tx.is_excluded = bool(patch["is_excluded"])

            tx.updated_at = now
            updated += 1

        db.commit()

    return {"updated_count": updated, "updated_at": now}


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def income_expense_series() -> dict[str, Any]:
    """Build monthly income/expense aggregates for charts."""
    with Session(engine) as db:
        transactions = db.exec(
            select(Transaction)
            .where(Transaction.is_excluded == False)  # noqa: E712
            .order_by(col(Transaction.booking_date).asc())
        ).all()

    months: dict[str, dict[str, float]] = {}
    for tx in transactions:
        month_key = tx.booking_date[:7] if tx.booking_date else "unknown"
        bucket = months.setdefault(month_key, {"income": 0.0, "expense": 0.0})
        if tx.amount >= 0:
            bucket["income"] += tx.amount
        else:
            bucket["expense"] += tx.amount

    series = [
        {
            "month": month,
            "income": round(data["income"], 2),
            "expense": round(data["expense"], 2),
            "net": round(data["income"] + data["expense"], 2),
        }
        for month, data in sorted(months.items())
    ]

    return {
        "generated_at": _utcnow_iso(),
        "series": series,
    }


def sunburst_data() -> dict[str, Any]:
    """Build hierarchical sunburst chart data grouped by category."""
    from .category_service import list_categories

    with Session(engine) as db:
        transactions = db.exec(
            select(Transaction)
            .where(Transaction.is_excluded == False)  # noqa: E712
            .where(Transaction.amount < 0)  # expenses only for sunburst
        ).all()

    # Build category lookup
    categories = {cat["id"]: cat for cat in list_categories()}

    # Aggregate by category
    totals: dict[str, float] = {}
    for tx in transactions:
        cat_id = tx.category_id or "diverse|ikke-kategoriseret"
        totals[cat_id] = totals.get(cat_id, 0) + abs(tx.amount)

    labels = ["Total"]
    parents = [""]
    values = [0.0]
    seen_mains: set[str] = set()

    for cat_id, total in sorted(totals.items(), key=lambda x: -x[1]):
        cat = categories.get(cat_id) or {"mainCategoryName": "Diverse", "categoryName": "Ukendt"}
        main = cat["mainCategoryName"]

        if main not in seen_mains:
            labels.append(main)
            parents.append("Total")
            values.append(0.0)
            seen_mains.add(main)

        # Add to main category total
        main_idx = labels.index(main)
        values[main_idx] += total
        values[0] += total

        labels.append(cat.get("categoryName", cat_id))
        parents.append(main)
        values.append(round(total, 2))

    return {
        "labels": labels,
        "parents": parents,
        "values": [round(v, 2) for v in values],
    }


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_transaction(tx: Transaction, account: Account | None) -> dict[str, Any]:
    """Serialize a Transaction row to the frontend-expected JSON shape."""
    return {
        "id": tx.id,
        "entry_reference": tx.entry_reference,
        "booking_date": tx.booking_date,
        "value_date": tx.value_date,
        "amount": tx.amount,
        "currency": tx.currency,
        "credit_debit_indicator": tx.credit_debit_indicator,
        "description": tx.original_description,
        "remittance_information": tx.remittance_information,
        "creditor_name": tx.creditor_name,
        "debtor_name": tx.debtor_name,
        "merchant_category_code": tx.merchant_category_code,
        "account_iban": account.iban if account else None,
        "account_name": account.name if account else None,
        "category_id": tx.category_id,
        "note": tx.custom_note or "",
        "is_extraordinary": tx.is_extraordinary,
        "is_excluded": tx.is_excluded,
        "source": account.source if account else "unknown",
        "created_at": tx.created_at,
        "updated_at": tx.updated_at,
    }
