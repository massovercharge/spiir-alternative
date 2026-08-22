"""Recurring transactions service.

Handles tracking, auto-detection, and linking of fixed expenses and income.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlmodel import Session, select

from app.models import (
    Posting,
    PostingAllocation,
    RecurringTransaction,
    engine,
)
from app.core.money import format_amount
from app.services.rules_service import preprocess_description


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Matching Logic
# ---------------------------------------------------------------------------

def match_posting_to_recurring(
    posting: Posting,
    alloc: PostingAllocation,
    recurring_txs: list[RecurringTransaction] | None = None,
) -> RecurringTransaction | None:
    """Find a matching recurring transaction for a posting.

    If a match is found, updates the recurring transaction's next_date
    and links the allocation to it.
    """
    raw_desc = posting.original_description or ""
    if not raw_desc.strip():
        return None

    cleaned = preprocess_description(raw_desc)
    extra_text = " ".join(filter(None, [
        posting.creditor_name,
        posting.remittance_information,
    ])).lower()

    search_text = f"{cleaned} {extra_text}".strip()

    if recurring_txs is None:
        with Session(engine) as db:
            recurring_txs = db.exec(
                select(RecurringTransaction)
                .where(RecurringTransaction.status == "active")
            ).all()

    best_match = None
    for rtx in recurring_txs:
        # Simple substring match for now
        if rtx.match_pattern.lower() in search_text:
            best_match = rtx
            break

    if best_match:
        # We found a match! Link the allocation
        alloc.recurring_transaction_id = best_match.id

        # Advance the expected next date
        if posting.booking_date:
            try:
                date_obj = datetime.fromisoformat(posting.booking_date[:10])
                if best_match.interval == "monthly":
                    next_date_obj = date_obj + relativedelta(months=1)
                    best_match.next_date = next_date_obj.date().isoformat()
            except ValueError:
                pass

    return best_match


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_recurring() -> list[dict[str, Any]]:
    with Session(engine) as db:
        txs = db.exec(select(RecurringTransaction)).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "amount": format_amount(r.amount_minor),
            "amount_minor": r.amount_minor,
            "interval": r.interval,
            "category_id": r.category_id,
            "next_date": r.next_date,
            "match_pattern": r.match_pattern,
            "status": r.status,
        }
        for r in txs
    ]


def create_recurring(payload: dict[str, Any]) -> dict[str, Any]:
    with Session(engine) as db:
        rtx = RecurringTransaction(
            name=payload["name"],
            amount_minor=payload["amount_minor"],
            interval=payload.get("interval", "monthly"),
            category_id=payload.get("category_id"),
            next_date=payload.get("next_date"),
            match_pattern=payload["match_pattern"],
        )
        db.add(rtx)
        db.commit()
        db.refresh(rtx)
        return {
            "id": rtx.id,
            "name": rtx.name,
            "match_pattern": rtx.match_pattern,
            "status": rtx.status,
        }


def delete_recurring(rtx_id: str) -> bool:
    with Session(engine) as db:
        rtx = db.get(RecurringTransaction, rtx_id)
        if not rtx:
            return False
        db.delete(rtx)
        db.commit()
        return True


# ---------------------------------------------------------------------------
# Auto-Detection
# ---------------------------------------------------------------------------

def detect_recurring() -> list[dict[str, Any]]:
    """Scan history and propose recurring transactions.

    Finds descriptions that appear multiple times with similar amounts.
    """
    with Session(engine) as db:
        postings = db.exec(select(Posting)).all()

    groups = defaultdict(list)
    for p in postings:
        cleaned = preprocess_description(p.original_description or "")
        if not cleaned:
            continue
        words = cleaned.split()
        if not words:
            continue
        key = " ".join(words[:2])
        groups[key].append(p)

    suggestions = []
    for key, group_postings in groups.items():
        if len(group_postings) >= 3:
            amounts = [p.amount_minor for p in group_postings]
            avg_amount = sum(amounts) / len(amounts)

            import statistics
            stddev = statistics.stdev(amounts) if len(amounts) > 1 else 0
            if abs(stddev) < abs(avg_amount) * 0.1:  # 10% tolerance
                suggestions.append({
                    "name": key.title(),
                    "match_pattern": key,
                    "avg_amount_minor": int(avg_amount),
                    "avg_amount": format_amount(int(avg_amount)),
                    "occurrences": len(group_postings),
                    "interval": "monthly"
                })

    suggestions.sort(key=lambda x: abs(x["avg_amount_minor"]), reverse=True)
    return suggestions
