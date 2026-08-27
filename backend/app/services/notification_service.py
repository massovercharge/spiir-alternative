"""Notification service — Proactive household notifications and duplicate detection."""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
from typing import Any, Optional

from sqlalchemy import func
from sqlmodel import Session, col, select

import app.models as models
from app.core.money import format_amount
from app.models import (
    Account,
    BankConnection,
    CategorizationRule,
    Category,
    Posting,
    PostingAllocation,
)
from app.models.all_models import Household, current_household_id

logger = logging.getLogger("peng.notification_service")

engine = models.engine


def _get_engine():
    return globals().get("engine") or models.engine or models.all_models.engine


def _clean_description_for_grouping(desc: str) -> str:
    """Normalize descriptions for duplicate detection and rule suggestions."""
    if not desc:
        return ""
    text = desc.strip().lower()
    # Normalize multiple whitespace
    text = re.sub(r"\s+", " ", text)
    return text


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def detect_duplicate_payments(db: Session, household_id: str) -> list[dict[str, Any]]:
    """Find transactions on the same date with the same amount and recipient."""
    notifications: list[dict[str, Any]] = []

    # Get effective date for all postings in the household
    eff_date_col = func.coalesce(Posting.custom_date, Posting.booking_date)
    query = (
        select(Posting)
        .where(Posting.household_id == household_id)
        .where(col(Posting.amount_minor) != 0)
        .order_by(eff_date_col.desc())
    )
    postings = db.exec(query).all()

    # Group postings by (effective_date, amount_minor, cleaned_desc)
    groups: dict[tuple[str, int, str], list[Posting]] = {}
    for p in postings:
        eff_date = p.custom_date or p.booking_date or ""
        clean_desc = _clean_description_for_grouping(p.original_description)
        if not eff_date or not clean_desc:
            continue
        key = (eff_date, p.amount_minor, clean_desc)
        groups.setdefault(key, []).append(p)

    for (eff_date, amount_minor, clean_desc), group in groups.items():
        if len(group) < 2:
            continue

        rep = group[0]
        desc_display = rep.original_description or clean_desc
        formatted_amount = format_amount(abs(amount_minor))
        group_hash = hashlib.md5(f"{eff_date}:{amount_minor}:{clean_desc}".encode("utf-8")).hexdigest()[:10]

        notifications.append({
            "id": f"dup:{eff_date}:{group_hash}",
            "type": "duplicate_payment",
            "severity": "warning",
            "title": "Mulig dobbeltbetaling",
            "message": f"{len(group)} transaktioner til '{desc_display}' på {formatted_amount} kr. den {eff_date}.",
            "created_at": max(p.created_at for p in group if p.created_at) if any(p.created_at for p in group) else f"{eff_date}T00:00:00Z",
            "metadata": {
                "transaction_ids": [p.id for p in group],
                "date": eff_date,
                "amount_minor": amount_minor,
                "amount": formatted_amount,
                "description": desc_display,
                "count": len(group),
            },
            "action_type": "filter_transactions",
            "action_payload": {
                "search": desc_display,
                "date": eff_date,
            },
        })

    return notifications


def detect_expiring_consents(db: Session, household_id: str) -> list[dict[str, Any]]:
    """Detect bank connections with expiring or expired PSD2 consents."""
    notifications: list[dict[str, Any]] = []
    connections = db.exec(
        select(BankConnection)
        .where(BankConnection.household_id == household_id)
        .where(BankConnection.status == "active")
    ).all()

    now_utc = dt.datetime.now(dt.UTC)

    for conn in connections:
        if not conn.consent_expires_at:
            continue

        try:
            # Parse ISO or date string
            exp_str = conn.consent_expires_at.replace("Z", "+00:00")
            exp_dt = dt.datetime.fromisoformat(exp_str)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=dt.UTC)
            
            delta = exp_dt - now_utc
            days_left = delta.days

            bank_label = conn.bank_name or "Bankforbindelse"

            if days_left <= 0:
                notifications.append({
                    "id": f"consent_expired:{conn.id}",
                    "type": "consent_expiring",
                    "severity": "danger",
                    "title": "Banksamtykke er udløbet",
                    "message": f"Samtykket til {bank_label} er udløbet. Forny forbindelsen for at fortsætte synkronisering.",
                    "created_at": conn.consent_expires_at,
                    "metadata": {
                        "connection_id": conn.id,
                        "bank_name": bank_label,
                        "expires_at": conn.consent_expires_at,
                        "days_left": days_left,
                    },
                    "action_type": "navigate",
                    "action_payload": {"to": "/accounts"},
                })
            elif days_left <= 7:
                notifications.append({
                    "id": f"consent_expiring:{conn.id}:{days_left}",
                    "type": "consent_expiring",
                    "severity": "warning",
                    "title": "Banksamtykke udløber snart",
                    "message": f"Samtykket til {bank_label} udløber om {days_left} {'dag' if days_left == 1 else 'dage'}.",
                    "created_at": conn.created_at,
                    "metadata": {
                        "connection_id": conn.id,
                        "bank_name": bank_label,
                        "expires_at": conn.consent_expires_at,
                        "days_left": days_left,
                    },
                    "action_type": "navigate",
                    "action_payload": {"to": "/accounts"},
                })
        except Exception as e:
            logger.warning("Failed to parse consent_expires_at '%s': %s", conn.consent_expires_at, e)

    return notifications


def detect_recent_linked_receipts(db: Session, household_id: str) -> list[dict[str, Any]]:
    """Detect recently auto-linked Storebox receipts."""
    notifications: list[dict[str, Any]] = []

    # Check for postings with receipt allocations in this household
    query = (
        select(PostingAllocation)
        .join(Posting, PostingAllocation.posting_id == Posting.id)
        .where(Posting.household_id == household_id)
        .where(col(PostingAllocation.item_name).is_not(None))
        .order_by(col(PostingAllocation.id).desc())
        .limit(20)
    )
    allocs = db.exec(query).all()

    if allocs:
        # Group by posting_id to count distinct matched transactions
        distinct_postings = {a.posting_id for a in allocs}
        count = len(distinct_postings)
        if count > 0:
            notifications.append({
                "id": f"receipts_linked:{count}",
                "type": "receipts_linked",
                "severity": "info",
                "title": "Digitale kvitteringer matchet",
                "message": f"{count} transaktioner har modtaget specificerede kvitteringslinjer fra Storebox.",
                "created_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
                "metadata": {"count": count, "posting_ids": list(distinct_postings)[:5]},
                "action_type": "navigate",
                "action_payload": {"to": "/transactions"},
            })

    return notifications


def detect_rule_suggestions(db: Session, household_id: str) -> list[dict[str, Any]]:
    """Find consistent categorization patterns (>= 3 times) that don't have an automated rule yet."""
    notifications: list[dict[str, Any]] = []

    # Get active custom rules
    existing_rules = db.exec(
        select(CategorizationRule)
        .where(CategorizationRule.household_id == household_id)
        .where(CategorizationRule.is_active == True)  # noqa: E712
    ).all()
    existing_patterns = {r.pattern.lower().strip() for r in existing_rules if r.pattern}

    # Fetch categorized postings
    postings_with_alloc = db.exec(
        select(Posting.original_description, PostingAllocation.category_id)
        .join(PostingAllocation, PostingAllocation.posting_id == Posting.id)
        .where(Posting.household_id == household_id)
        .where(col(PostingAllocation.category_id).is_not(None))
        .where(col(PostingAllocation.category_id) != "diverse|ikke-kategoriseret")
        .where(col(PostingAllocation.category_id) != "diverse|ukategoriseret")
    ).all()

    # Tally counts per (pattern, category_id)
    tallies: dict[tuple[str, str], int] = {}
    for orig_desc, cat_id in postings_with_alloc:
        if not orig_desc or not cat_id:
            continue
        clean = _clean_description_for_grouping(orig_desc)
        # Skip if too short or purely numeric
        if len(clean) < 3 or clean.isdigit():
            continue
        # If already covered by an exact rule, skip
        if clean in existing_patterns:
            continue
        tallies[(clean, cat_id)] = tallies.get((clean, cat_id), 0) + 1

    # Fetch category names lookup
    all_categories = {c.id: c.sub_name or c.main_name for c in db.exec(select(Category)).all()}

    # Propose top suggestions (with count >= 3)
    sorted_tallies = sorted(
        [(k, v) for k, v in tallies.items() if v >= 3],
        key=lambda item: item[1],
        reverse=True,
    )

    for (pattern, cat_id), count in sorted_tallies[:5]:
        cat_name = all_categories.get(cat_id, cat_id.replace("|", " > "))
        pattern_hash = hashlib.md5(pattern.encode("utf-8")).hexdigest()[:8]

        notifications.append({
            "id": f"rule_sug:{pattern_hash}",
            "type": "rule_suggestion",
            "severity": "suggestion",
            "title": "Forslag til regel",
            "message": f"Du har kategoriseret '{pattern}' som '{cat_name}' {count} gange. Vil du oprette en automatisk regel?",
            "created_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
            "metadata": {
                "match_pattern": pattern,
                "category_id": cat_id,
                "category_name": cat_name,
                "count": count,
            },
            "action_type": "create_rule",
            "action_payload": {
                "match_pattern": pattern,
                "category_id": cat_id,
            },
        })

    return notifications


# ---------------------------------------------------------------------------
# Public Aggregation API
# ---------------------------------------------------------------------------

def get_household_notifications(household_id: str | None = None) -> list[dict[str, Any]]:
    """Aggregate all notifications and warnings for the active household."""
    if not household_id:
        try:
            household_id = current_household_id.get()
        except LookupError:
            household_id = None

    if not household_id:
        # Fallback to first household in DB if no tenant context is set
        with Session(_get_engine()) as db:
            hh = db.exec(select(Household)).first()
            if hh:
                household_id = hh.id

    if not household_id:
        return []

    notifications: list[dict[str, Any]] = []
    with Session(_get_engine()) as db:
        notifications.extend(detect_duplicate_payments(db, household_id))
        notifications.extend(detect_expiring_consents(db, household_id))
        notifications.extend(detect_recent_linked_receipts(db, household_id))
        notifications.extend(detect_rule_suggestions(db, household_id))

    # Sort: danger/warnings first, then suggestions, then info, then by date desc
    severity_order = {"danger": 0, "warning": 1, "suggestion": 2, "info": 3}
    notifications.sort(
        key=lambda n: (severity_order.get(n.get("severity", "info"), 99), n.get("created_at", "")),
        reverse=False,
    )

    return notifications
