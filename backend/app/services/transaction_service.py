"""Posting service — CRUD for bank postings and their allocations.

Replaces the V2 transaction_service. The key change is that monetary
amounts are now integers in minor units (øre/cents) via ``amount_minor``,
and API responses return amounts as strings (e.g. ``"100.50"``).
"""
from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, delete, or_, select

import app.models as models
from app.core.item_utils import clean_item_name
from app.core.money import format_amount, to_minor
from app.models import (
    Account,
    CategorizationRule,
    Category,
    CategoryOverrideLog,
    DismissedDuplicate,
    Posting,
    PostingAllocation,
    PostingAllocationTagLink,
    Tag,
)
from app.models.all_models import Household, current_household_id

logger = logging.getLogger("peng.transaction_service")

engine = None


def _get_engine():
    return engine or models.all_models.engine


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

STATUTORY_SPLIT_KEYWORDS = (
    "børne- og ungeydelse",
    "børneydelse",
    "børnepenge",
    "børnecheck",
    "børnetilskud",
    "ungeydelse",
)


def list_transactions(
    *,
    limit: int | None = None,
    offset: int = 0,
    account_uid: str | None = None,
    search: str | None = None,
    filter_type: str | None = None,
    tag: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    amount_op: str | None = None,
    amount_value: float | None = None,
    category_id: str | None = None,
) -> dict[str, Any]:
    """Return paginated postings with optional filters."""
    with Session(_get_engine()) as db:
        eff_date = func.coalesce(Posting.custom_date, Posting.booking_date)

        # Pre-compute duplicate map for outgoing expenses in the household
        all_postings_for_dups = db.exec(
            select(Posting.id, Posting.booking_date, Posting.custom_date, Posting.amount_minor, Posting.original_description)
            .where(col(Posting.amount_minor) < 0)
        ).all()

        dup_groups: dict[tuple[str, int, str], list[str]] = {}
        for p_id, b_date, c_date, amt, desc in all_postings_for_dups:
            e_date = c_date or b_date or ""
            cdesc = (desc or "").strip().lower()
            if e_date and cdesc:
                if any(kw in cdesc for kw in STATUTORY_SPLIT_KEYWORDS):
                    continue
                dup_groups.setdefault((e_date, amt, cdesc), []).append(p_id)

        dismissed = db.exec(select(DismissedDuplicate)).all()
        dismissed_pairs = {(min(d.posting_id_1, d.posting_id_2), max(d.posting_id_1, d.posting_id_2)) for d in dismissed}

        import itertools
        dup_info_map: dict[str, tuple[int, list[str]]] = {}
        dup_posting_ids: set[str] = set()
        for group in dup_groups.values():
            if len(group) >= 2:
                # Check if all pairs in group are dismissed
                all_dismissed = True
                for p1, p2 in itertools.combinations(group, 2):
                    if (min(p1, p2), max(p1, p2)) not in dismissed_pairs:
                        all_dismissed = False
                        break
                if all_dismissed:
                    continue

                for p_id in group:
                    # Only include siblings that are not dismissed with this p_id
                    siblings = [other_id for other_id in group if other_id != p_id and (min(p_id, other_id), max(p_id, other_id)) not in dismissed_pairs]
                    if siblings:
                        dup_posting_ids.add(p_id)
                        dup_info_map[p_id] = (len(siblings) + 1, siblings)

        query = select(Posting).distinct().order_by(
            eff_date.desc(),
            col(Posting.id).desc(),
        )

        if account_uid:
            query = query.where(Posting.account_uid == account_uid)

        if start_date:
            query = query.where(eff_date >= start_date)
        if end_date:
            query = query.where(eff_date <= end_date)

        if filter_type and filter_type.lower() in ("dubletter", "mulige-dubletter", "dublet", "mulige dubletter"):
            query = query.where(col(Posting.id).in_(dup_posting_ids))

        if amount_op and amount_value is not None:
            amount_minor = to_minor(str(amount_value))
            if amount_op == "gt":
                query = query.where(Posting.amount_minor > amount_minor)
            elif amount_op == "lt":
                query = query.where(Posting.amount_minor < amount_minor)
            elif amount_op == "eq":
                query = query.where(Posting.amount_minor == amount_minor)

        # Joins for filtering
        needs_alloc = filter_type in ("regninger", "forbrug", "ukategoriseret", "ekstraordinær") or tag or category_id or bool(search)
        if needs_alloc:
            query = query.join(PostingAllocation, PostingAllocation.posting_id == Posting.id, isouter=True)

            if filter_type == "ukategoriseret":
                query = query.where(
                    PostingAllocation.category_id.is_(None) |
                    PostingAllocation.category_id.in_(["diverse|ikke-kategoriseret", "diverse|ukategoriseret"])
                )
            elif filter_type == "ekstraordinær":
                query = query.where(PostingAllocation.is_extraordinary)
            elif filter_type in ("regninger", "forbrug"):
                query = query.join(Category, PostingAllocation.category_id == Category.id, isouter=True)
                if filter_type == "regninger":
                    query = query.where(Category.expense_type == "Fixed")
                else:
                    query = query.where(Category.expense_type == "Variable")

            if tag:
                query = query.join(PostingAllocationTagLink, PostingAllocationTagLink.allocation_id == PostingAllocation.id)
                query = query.join(Tag, Tag.id == PostingAllocationTagLink.tag_id)
                query = query.where(Tag.name == tag)

            if category_id:
                if "|" in category_id:
                    query = query.where(PostingAllocation.category_id == category_id)
                else:
                    query = query.where(PostingAllocation.category_id.startswith(f"{category_id}|"))

        if search:
            pattern = f"%{search}%"
            if needs_alloc:
                query = query.where(
                    col(Posting.original_description).ilike(pattern) |
                    col(PostingAllocation.item_name).ilike(pattern) |
                    col(PostingAllocation.note).ilike(pattern)
                )
            else:
                query = query.where(col(Posting.original_description).ilike(pattern))

        # Get total count using the same base query
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total_count = db.exec(count_query).one_or_none() or 0

        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        postings = db.exec(query).all()
        accounts = {acc.uid: acc for acc in db.exec(select(Account)).all()}

        # Fetch allocations and tags
        allocation_map: dict[str, list[PostingAllocation]] = {}
        tags_map: dict[str, list[str]] = {}
        if postings:
            posting_ids = [p.id for p in postings]
            allocs = db.exec(
                select(PostingAllocation).where(
                    PostingAllocation.posting_id.in_(posting_ids)  # type: ignore[union-attr]
                )
            ).all()
            for alloc in allocs:
                allocation_map.setdefault(alloc.posting_id, []).append(alloc)

            if allocs:
                alloc_ids = [a.id for a in allocs]
                links = db.exec(
                    select(PostingAllocationTagLink.allocation_id, Tag.name)
                    .join(Tag, Tag.id == PostingAllocationTagLink.tag_id)
                    .where(PostingAllocationTagLink.allocation_id.in_(alloc_ids))
                ).all()
                for alloc_id, tag_name in links:
                    tags_map.setdefault(alloc_id, []).append(tag_name)

    return {
        "generated_at": _utcnow_iso(),
        "transaction_count": total_count,
        "offset": offset,
        "transactions": [
            _serialize_posting(
                p,
                accounts.get(p.account_uid),
                allocation_map.get(p.id, []),
                tags_map,
                duplicate_info=dup_info_map.get(p.id),
            )
            for p in postings
        ],
    }


def get_transaction(transaction_id: str) -> dict[str, Any] | None:
    """Return a single posting by ID with its allocations."""
    with Session(_get_engine()) as db:
        posting = db.get(Posting, transaction_id)
        if posting is None:
            return None
        account = db.get(Account, posting.account_uid)
        allocs = db.exec(
            select(PostingAllocation).where(
                PostingAllocation.posting_id == transaction_id
            )
        ).all()

        tags_map = {}
        if allocs:
            alloc_ids = [a.id for a in allocs]
            links = db.exec(
                select(PostingAllocationTagLink.allocation_id, Tag.name)
                .join(Tag, Tag.id == PostingAllocationTagLink.tag_id)
                .where(PostingAllocationTagLink.allocation_id.in_(alloc_ids))
            ).all()
            for alloc_id, tag_name in links:
                tags_map.setdefault(alloc_id, []).append(tag_name)

        # Check for duplicate siblings on same effective date and amount and description for expenses
        eff_date = posting.custom_date or posting.booking_date
        cdesc = (posting.original_description or "").strip().lower()
        siblings = []
        is_statutory = any(kw in cdesc for kw in STATUTORY_SPLIT_KEYWORDS)
        if eff_date and cdesc and posting.amount_minor < 0 and not is_statutory:
            siblings_query = (
                select(Posting.id)
                .where(Posting.id != transaction_id)
                .where(func.coalesce(Posting.custom_date, Posting.booking_date) == eff_date)
                .where(Posting.amount_minor == posting.amount_minor)
                .where(func.lower(func.trim(Posting.original_description)) == cdesc)
            )
            raw_siblings = list(db.exec(siblings_query).all())
            # Exclude siblings that are dismissed with this transaction
            dismissed = db.exec(
                select(DismissedDuplicate).where(
                    (DismissedDuplicate.posting_id_1 == transaction_id) | (DismissedDuplicate.posting_id_2 == transaction_id)
                )
            ).all()
            dismissed_with_this = {
                d.posting_id_2 if d.posting_id_1 == transaction_id else d.posting_id_1
                for d in dismissed
            }
            siblings = [s for s in raw_siblings if s not in dismissed_with_this]

        dup_info = (len(siblings) + 1, siblings) if siblings else (0, [])

    return _serialize_posting(posting, account, list(allocs), tags_map, duplicate_info=dup_info)


# ---------------------------------------------------------------------------
# Write (overrides via allocations)
# ---------------------------------------------------------------------------

def list_tags() -> list[Tag]:
    """Return all tags ordered by name."""
    with Session(_get_engine()) as db:
        return db.exec(select(Tag).order_by(Tag.name)).all()

def update_transactions(transaction_ids: list[str], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a patch (category, note, etc.) to one or more postings.

    Creates or updates the default PostingAllocation for each posting.
    Also logs category changes to CategoryOverrideLog for ML training.
    """
    if not transaction_ids:
        raise ValueError("No transactions selected")

    now = _utcnow_iso()
    updated = 0

    with Session(_get_engine()) as db:
        for posting_id in transaction_ids:
            posting = db.get(Posting, posting_id)
            if posting is None:
                continue

            # Find or create the default allocation (first one)
            alloc = db.exec(
                select(PostingAllocation)
                .where(PostingAllocation.posting_id == posting_id)
                .limit(1)
            ).first()

            if alloc is None:
                from app.models.all_models import current_household_id
                alloc = PostingAllocation(
                    posting_id=posting_id,
                    household_id=current_household_id.get(),
                    amount_minor=posting.amount_minor,
                )
                db.add(alloc)

            if "category_id" in patch:
                new_cat = patch["category_id"] or None
                old_cat = alloc.category_id

                # Log the override for ML training
                if new_cat != old_cat:
                    from app.models.all_models import current_household_id
                    db.add(CategoryOverrideLog(
                        household_id=current_household_id.get(),
                        original_description=posting.original_description,
                        old_category_id=old_cat,
                        new_category_id=new_cat or "",
                        merchant_category_code=posting.merchant_category_code,
                    ))

                alloc.category_id = new_cat

            if "custom_note" in patch:
                alloc.note = patch["custom_note"] or None

            if "is_extraordinary" in patch:
                alloc.is_extraordinary = bool(patch["is_extraordinary"])

            if "is_excluded" in patch:
                posting.is_excluded = bool(patch["is_excluded"])

            if "custom_date" in patch:
                posting.custom_date = patch["custom_date"] or None

            if "tags" in patch:
                tag_names = patch["tags"]
                if isinstance(tag_names, list):
                    # Delete existing tags for this allocation
                    db.exec(
                        delete(PostingAllocationTagLink)
                        .where(PostingAllocationTagLink.allocation_id == alloc.id)
                    )
                    # Create or fetch tags
                    for name in tag_names:
                        name = str(name).strip()
                        if not name:
                            continue
                        tag_obj = db.exec(select(Tag).where(Tag.name == name)).first()
                        if not tag_obj:
                            tag_obj = Tag(name=name)
                            db.add(tag_obj)
                            db.commit() # commit to get tag_obj.id
                        link = PostingAllocationTagLink(allocation_id=alloc.id, tag_id=tag_obj.id)
                        db.add(link)

            alloc.updated_at = now
            updated += 1

        db.commit()

    return {"updated_count": updated, "updated_at": now}


def split_allocation(posting_id: str, splits: list[dict[str, Any]]) -> dict[str, Any]:
    """Split a posting into multiple allocations.

    Validates that the sum of the split amounts equals the parent posting's amount_minor.
    Deletes existing allocations and replaces them with the new splits.
    """
    if not splits:
        raise ValueError("Must provide at least one split")

    now = _utcnow_iso()

    with Session(_get_engine()) as db:
        posting = db.get(Posting, posting_id)
        if posting is None:
            raise ValueError(f"Posting {posting_id} not found")

        # Sum validation
        total_split = sum(int(s.get("amount_minor", 0)) for s in splits)
        if total_split != posting.amount_minor:
            raise ValueError(
                f"Split sum ({total_split}) does not match posting amount ({posting.amount_minor})"
            )

        # Delete existing allocations
        old_allocs = db.exec(
            select(PostingAllocation).where(PostingAllocation.posting_id == posting_id)
        ).all()
        for alloc in old_allocs:
            db.delete(alloc)

        # Create new splits
        new_allocs = []
        for s in splits:
            raw_item_name = s.get("item_name")
            cleaned_item_name = clean_item_name(raw_item_name) if raw_item_name else None
            alloc = PostingAllocation(
                posting_id=posting_id,
                household_id=posting.household_id,
                category_id=s.get("category_id"),
                amount_minor=int(s.get("amount_minor", 0)),
                note=s.get("note"),
                item_name=cleaned_item_name,
                item_cluster_id=s.get("item_cluster_id"),
                is_extraordinary=bool(s.get("is_extraordinary", False)),
                created_at=now,
                updated_at=now,
            )
            db.add(alloc)
            new_allocs.append(alloc)

        db.commit()

        # Serialize the updated posting to return it
        account = db.get(Account, posting.account_uid)
        return _serialize_posting(posting, account, new_allocs)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_posting(
    posting: Posting,
    account: Account | None,
    allocations: list[PostingAllocation],
    tags_map: dict[str, list[str]] | None = None,
    duplicate_info: tuple[int, list[str]] | None = None,
) -> dict[str, Any]:
    """Serialize a Posting + its allocations to the API JSON shape.

    Amount is returned as a string (§7 rule).
    """
    # Get the primary allocation (first one, or None)
    primary = allocations[0] if allocations else None
    dup_count, dup_siblings = duplicate_info if duplicate_info else (0, [])
    has_dup = dup_count >= 2

    return {
        "id": posting.id,
        "entry_reference": posting.entry_reference,
        "booking_date": posting.booking_date,
        "value_date": posting.value_date,
        "amount": format_amount(posting.amount_minor),
        "amount_minor": posting.amount_minor,
        "currency": posting.currency,
        "credit_debit_indicator": posting.credit_debit_indicator,
        "description": posting.original_description,
        "remittance_information": posting.remittance_information,
        "creditor_name": posting.creditor_name,
        "debtor_name": posting.debtor_name,
        "merchant_category_code": posting.merchant_category_code,
        "account_iban": account.iban if account else None,
        "account_name": account.name if account else None,
        "category_id": primary.category_id if primary else None,
        "note": (primary.note or "") if primary else "",
        "tags": (tags_map or {}).get(primary.id, []) if primary else [],
        "custom_date": posting.custom_date,
        "is_extraordinary": primary.is_extraordinary if primary else False,
        "is_excluded": posting.is_excluded,
        "source": account.source if account else "unknown",
        "has_duplicate_warning": has_dup,
        "duplicate_count": dup_count,
        "duplicate_sibling_ids": dup_siblings,
        "created_at": posting.created_at,
        "updated_at": (primary.updated_at if primary else posting.created_at),
        "allocations": [
            {
                "id": a.id,
                "category_id": a.category_id,
                "amount": format_amount(a.amount_minor),
                "amount_minor": a.amount_minor,
                "note": a.note or "",
                "item_name": a.item_name,
                "item_cluster_id": a.item_cluster_id,
                "tags": (tags_map or {}).get(a.id, []),
                "is_extraordinary": a.is_extraordinary,
            }
            for a in allocations
        ],
    }

def update_transaction_category(posting_id: str, category_id: str) -> bool:
    """Update the primary category of a single transaction."""
    with Session(_get_engine()) as db:
        posting = db.get(Posting, posting_id)
        if not posting:
            return False

        alloc = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == posting_id)).first()
        old_cat = alloc.category_id if alloc else None

        if not alloc:
            alloc = PostingAllocation(
                posting_id=posting_id,
                household_id=posting.household_id,
                amount_minor=posting.amount_minor,
                category_id=category_id,
            )
            db.add(alloc)
        else:
            alloc.category_id = category_id
            alloc.updated_at = _utcnow_iso()
            db.add(alloc)

        # Log category override for ML/rules
        if category_id != old_cat:
            db.add(CategoryOverrideLog(
                household_id=posting.household_id,
                original_description=posting.original_description,
                old_category_id=old_cat,
                new_category_id=category_id or "",
                merchant_category_code=posting.merchant_category_code,
            ))

        db.commit()
        return True

def apply_rule_retroactively(rule_id: str) -> int:
    """Find all postings that match a categorization rule and update them.

    Returns the number of updated postings.
    """
    from app.services.rules_service import get_compiled_regex, preprocess_description

    updated_count = 0
    with Session(_get_engine()) as db:
        rule = db.get(CategorizationRule, rule_id)
        if not rule:
            return 0

        compiled = get_compiled_regex(rule)
        if compiled is not None:
            # We fetch all postings and evaluate them against this specific rule.
            postings = db.exec(select(Posting)).all()
            for p in postings:
                cleaned = preprocess_description(p.original_description or "")
                extra_text = " ".join(filter(None, [
                    p.creditor_name,
                    p.remittance_information,
                ])).lower()
                search_text = f"{cleaned} {extra_text}".strip()

                if search_text and compiled.search(search_text):
                    # Update it!
                    alloc = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == p.id)).first()
                    if alloc:
                        alloc.category_id = rule.category_id
                        alloc.updated_at = _utcnow_iso()
                        db.add(alloc)
                        updated_count += 1

        if updated_count > 0:
            db.commit()

    return updated_count

def link_receipt_to_transaction(posting_id: str, receipt_id: str, is_auto: bool = False) -> dict[str, Any]:
    from .kvitteringer_service import get_receipt, link_peng_transaction_to_receipt

    receipt_data = get_receipt(receipt_id)
    if not receipt_data:
        raise ValueError(f"Receipt {receipt_id} not found in Storebox DB")

    with Session(_get_engine()) as db:
        posting = db.get(Posting, posting_id)
        if not posting:
            raise ValueError(f"Posting {posting_id} not found")

        # Save the link in the kvitteringer db using existing function
        if not is_auto:
            link_peng_transaction_to_receipt({
                "transaction_id": posting_id,
                "receipt_id": receipt_id,
                "confidence": "manual",
                "reason": "user_linked",
                "transaction_payload_json": "{}"
            })

        # Calculate splits
        occurrences = receipt_data.get("occurrences", [])
        if not occurrences:
            raise ValueError("Receipt has no items to split")

        # Preserve the original allocation's category as fallback for each split
        existing_alloc = db.exec(
            select(PostingAllocation)
            .where(PostingAllocation.posting_id == posting_id)
            .limit(1)
        ).first()
        fallback_category_id = existing_alloc.category_id if existing_alloc else None
        # If there's no existing category, try the bank description via rules
        if not fallback_category_id or fallback_category_id in (
            "diverse|ikke-kategoriseret", "diverse|ukategoriseret"
        ):
            from app.services.rules_service import evaluate_posting
            fallback_category_id = evaluate_posting(posting) or fallback_category_id

        # Also try merchant from receipt metadata if still unknown
        receipt_info = receipt_data.get("receipt", {})
        if not fallback_category_id or fallback_category_id in (
            "diverse|ikke-kategoriseret", "diverse|ukategoriseret"
        ):
            from app.services.rules_service import evaluate_text
            merchant_name = receipt_info.get("merchant_name")
            merchant_key = str(receipt_info.get("merchant_key", "")).lower()
            if merchant_name:
                fallback_category_id = evaluate_text(merchant_name) or fallback_category_id
            if not fallback_category_id or fallback_category_id in (
                "diverse|ikke-kategoriseret", "diverse|ukategoriseret"
            ):
                if merchant_key in (
                    "aldi", "bilka", "foetex", "fakta", "irma", "kvickly",
                    "lidl", "meny", "nemlig", "netto", "rema1000", "rema",
                    "superbrugsen", "daglibrugsen", "spar", "min koebmand", "min købmand",
                    "coop", "coop365", "365discount", "loevbjerg", "løvbjerg"
                ):
                    fallback_category_id = "husholdning|dagligvarer"

        splits = []
        sum_items = 0

        # Most receipts are positive totals. If posting is a negative expense, invert signs
        receipt_total = receipt_data["receipt"].get("receipt_total_minor", 0)
        multiplier = -1 if posting.amount_minor < 0 and receipt_total > 0 else 1

        from app.services.rules_service import evaluate_text

        for occ in occurrences:
            # net_total_minor is the item's total including item-level discounts
            amt = occ.get("net_total_minor", 0) * multiplier
            sum_items += amt

            raw_item_name = occ.get("display_name")
            item_name = clean_item_name(raw_item_name) if raw_item_name else None
            # Try item-specific categorization first, but force Dagligvarer if transaction is Dagligvarer
            category_id = None
            if fallback_category_id and fallback_category_id == "husholdning|dagligvarer":
                category_id = fallback_category_id
            elif item_name:
                category_id = evaluate_text(item_name)

            if not category_id:
                category_id = fallback_category_id

            splits.append({
                "amount_minor": amt,
                "item_name": item_name,
                "item_cluster_id": occ.get("cluster_id"),
                "category_id": category_id,
                "note": None
            })

        # Distribute unassigned discounts
        unassigned_discount = receipt_data["receipt"].get("unassigned_discount_total_minor", 0) * multiplier
        if unassigned_discount != 0 and splits:
            total_abs = sum(abs(s["amount_minor"]) for s in splits)
            if total_abs != 0:
                distributed_sum = 0
                for i, s in enumerate(splits):
                    if i == len(splits) - 1:
                        dist_amt = unassigned_discount - distributed_sum
                    else:
                        dist_amt = int(unassigned_discount * (abs(s["amount_minor"]) / total_abs))
                    s["amount_minor"] += dist_amt
                    distributed_sum += dist_amt
                    sum_items += dist_amt

        if abs(sum_items) != abs(posting.amount_minor):
            diff = abs(posting.amount_minor) - abs(sum_items)
            diff_category_id = fallback_category_id
            if not diff_category_id or diff_category_id in (
                "diverse|ikke-kategoriseret", "diverse|ukategoriseret"
            ):
                valid_split_cats = [
                    s["category_id"]
                    for s in splits
                    if s.get("category_id")
                    and s["category_id"] not in ("diverse|ikke-kategoriseret", "diverse|ukategoriseret")
                ]
                if valid_split_cats:
                    diff_category_id = max(set(valid_split_cats), key=valid_split_cats.count)

            splits.append({
                "amount_minor": diff * multiplier,
                "item_name": "Difference / Gebyr",
                "item_cluster_id": None,
                "category_id": diff_category_id,
                "note": "Automatisk difference (fra kvittering)"
            })

        return split_allocation(posting_id, splits)


def fix_receipt_difference_categories() -> int:
    """Backfill / fix existing 'Difference / Gebyr' posting allocations that have no category.

    Assigns the sibling allocation's category, or falls back to evaluate_posting on the parent posting,
    or 'husholdning|dagligvarer' for grocery receipts/descriptions.
    """
    updated_count = 0
    with Session(_get_engine()) as db:
        diff_allocs = db.exec(
            select(PostingAllocation).where(
                PostingAllocation.item_name == "Difference / Gebyr",
                or_(
                    PostingAllocation.category_id == None,  # noqa: E711
                    PostingAllocation.category_id == "diverse|ikke-kategoriseret",
                    PostingAllocation.category_id == "diverse|ukategoriseret",
                ),
            )
        ).all()

        if not diff_allocs:
            return 0

        for alloc in diff_allocs:
            # 1. Look for sibling allocations on the same posting with a valid category
            sibling_allocs = db.exec(
                select(PostingAllocation).where(
                    PostingAllocation.posting_id == alloc.posting_id,
                    PostingAllocation.id != alloc.id,
                    PostingAllocation.category_id != None,  # noqa: E711
                    PostingAllocation.category_id != "diverse|ikke-kategoriseret",
                    PostingAllocation.category_id != "diverse|ukategoriseret",
                )
            ).all()

            target_cat = None
            if sibling_allocs:
                cats = [s.category_id for s in sibling_allocs if s.category_id]
                if cats:
                    target_cat = max(set(cats), key=cats.count)

            # 2. If no sibling category, evaluate the parent posting
            if not target_cat:
                posting = db.get(Posting, alloc.posting_id)
                if posting:
                    from app.services.rules_service import evaluate_posting
                    target_cat = evaluate_posting(posting)
                    if not target_cat and posting.original_description:
                        desc_lower = posting.original_description.lower()
                        if any(
                            k in desc_lower
                            for k in (
                                "coop", "netto", "rema", "foetex", "bilka", "meny",
                                "lidl", "aldi", "brugsen", "365", "spar", "købmand",
                            )
                        ):
                            target_cat = "husholdning|dagligvarer"

            if target_cat:
                alloc.category_id = target_cat
                alloc.updated_at = _utcnow_iso()
                updated_count += 1

        if updated_count > 0:
            db.commit()

    return updated_count


def auto_link_receipts(
    min_date: str | None = None,
    max_date: str | None = None,
    household_id: str | None = None,
) -> int:
    """
    Scans un-split Postings for matches with imported receipts and automatically links and splits them.
    """
    from sqlalchemy.orm import selectinload

    from .kvitteringer_service import link_peng_transaction_to_receipt

    linked_count = 0

    target_households: list[str] = []
    if household_id:
        target_households = [household_id]
    else:
        try:
            active_hh = current_household_id.get()
            if active_hh:
                target_households = [active_hh]
        except LookupError:
            pass

        if not target_households:
            with Session(_get_engine()) as db:
                hhs = db.exec(select(Household.id)).all()
                target_households = list(hhs)

    for hh_id in target_households:
        token = current_household_id.set(hh_id)
        try:
            with Session(_get_engine()) as db:
                query = select(Posting).where(col(Posting.amount_minor) < 0).options(selectinload(Posting.allocations))

                if min_date:
                    query = query.where(col(Posting.booking_date) >= min_date)
                if max_date:
                    query = query.where(col(Posting.booking_date) <= max_date)

                postings = db.exec(query).all()

                for posting in postings:
                    # Check if it already has more than 1 allocation or any allocation with an item_name
                    if len(posting.allocations) > 1 or any(a.item_name is not None for a in posting.allocations):
                        continue

                    payload = {
                        "transaction_id": posting.id,
                        "booking_date": posting.booking_date,
                        "amount": posting.amount_minor / 100.0,
                        "description": posting.original_description,
                    }

                    try:
                        result = link_peng_transaction_to_receipt(payload)
                        if result.get("linked"):
                            receipt_id = str(result.get("receipt_id"))
                            link_receipt_to_transaction(posting.id, receipt_id, is_auto=True)
                            linked_count += 1
                    except Exception as e:
                        logger.warning("Error auto-linking posting %s: %s", posting.id, e)
        finally:
            current_household_id.reset(token)

    return linked_count


def get_suggested_receipts_for_transaction(posting_id: str) -> list[dict[str, Any]]:
    """Find candidate Storebox receipts that potentially match a given posting."""
    from datetime import date

    from .kvitteringer_service import find_suggested_receipts

    with Session(_get_engine()) as db:
        posting = db.get(Posting, posting_id)
        if not posting:
            return []

        p_date = None
        if posting.booking_date:
            with contextlib.suppress(Exception):
                p_date = date.fromisoformat(posting.booking_date[:10])

        target_amount_minor = abs(posting.amount_minor)
        return find_suggested_receipts(
            target_amount_minor=target_amount_minor,
            transaction_date=p_date,
            description=posting.original_description,
            limit=10,
        )

