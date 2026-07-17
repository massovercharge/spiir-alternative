"""Posting service — CRUD for bank postings and their allocations.

Replaces the V2 transaction_service. The key change is that monetary
amounts are now integers in minor units (øre/cents) via ``amount_minor``,
and API responses return amounts as strings (e.g. ``"100.50"``).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, delete, select

from .database import (
    Account,
    CategorizationRule,
    Category,
    CategoryOverrideLog,
    Posting,
    PostingAllocation,
    PostingAllocationTagLink,
    Tag,
    engine,
)
from .money import format_amount


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

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
    with Session(engine) as db:
        eff_date = func.coalesce(Posting.custom_date, Posting.booking_date)

        query = select(Posting).distinct().order_by(
            eff_date.desc(),
            col(Posting.id).desc(),
        )

        if account_uid:
            query = query.where(Posting.account_uid == account_uid)

        if search:
            pattern = f"%{search}%"
            query = query.where(col(Posting.original_description).ilike(pattern))

        if start_date:
            query = query.where(eff_date >= start_date)
        if end_date:
            query = query.where(eff_date <= end_date)

        if amount_op and amount_value is not None:
            amount_minor = int(amount_value * 100)
            if amount_op == "gt":
                query = query.where(Posting.amount_minor > amount_minor)
            elif amount_op == "lt":
                query = query.where(Posting.amount_minor < amount_minor)
            elif amount_op == "eq":
                query = query.where(Posting.amount_minor == amount_minor)

        # Joins for filtering
        needs_alloc = filter_type in ("regninger", "forbrug", "ukategoriseret", "ekstraordinær") or tag or category_id
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

        # Get total count
        count_query = select(func.count(Posting.id.distinct()))
        count_query = count_query.select_from(Posting)

        if account_uid:
            count_query = count_query.where(Posting.account_uid == account_uid)
        if search:
            count_query = count_query.where(col(Posting.original_description).ilike(f"%{search}%"))
        if start_date:
            count_query = count_query.where(eff_date >= start_date)
        if end_date:
            count_query = count_query.where(eff_date <= end_date)

        if amount_op and amount_value is not None:
            amount_minor = int(amount_value * 100)
            if amount_op == "gt":
                count_query = count_query.where(Posting.amount_minor > amount_minor)
            elif amount_op == "lt":
                count_query = count_query.where(Posting.amount_minor < amount_minor)
            elif amount_op == "eq":
                count_query = count_query.where(Posting.amount_minor == amount_minor)

        if needs_alloc:
            count_query = count_query.join(PostingAllocation, PostingAllocation.posting_id == Posting.id, isouter=True)
            if filter_type == "ukategoriseret":
                count_query = count_query.where(
                    PostingAllocation.category_id.is_(None) |
                    PostingAllocation.category_id.in_(["diverse|ikke-kategoriseret", "diverse|ukategoriseret"])
                )
            elif filter_type == "ekstraordinær":
                count_query = count_query.where(PostingAllocation.is_extraordinary)
            elif filter_type in ("regninger", "forbrug"):
                count_query = count_query.join(Category, PostingAllocation.category_id == Category.id, isouter=True)
                if filter_type == "regninger":
                    count_query = count_query.where(Category.expense_type == "Fixed")
                else:
                    count_query = count_query.where(Category.expense_type == "Variable")
            if tag:
                count_query = count_query.join(PostingAllocationTagLink, PostingAllocationTagLink.allocation_id == PostingAllocation.id)
                count_query = count_query.join(Tag, Tag.id == PostingAllocationTagLink.tag_id)
                count_query = count_query.where(Tag.name == tag)
            if category_id:
                if "|" in category_id:
                    count_query = count_query.where(PostingAllocation.category_id == category_id)
                else:
                    count_query = count_query.where(PostingAllocation.category_id.startswith(f"{category_id}|"))

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
            _serialize_posting(p, accounts.get(p.account_uid), allocation_map.get(p.id, []), tags_map)
            for p in postings
        ],
    }


def get_transaction(transaction_id: str) -> dict[str, Any] | None:
    """Return a single posting by ID with its allocations."""
    with Session(engine) as db:
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

    return _serialize_posting(posting, account, list(allocs), tags_map)


# ---------------------------------------------------------------------------
# Write (overrides via allocations)
# ---------------------------------------------------------------------------

def list_tags() -> list[Tag]:
    """Return all tags ordered by name."""
    with Session(engine) as db:
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

    with Session(engine) as db:
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
                alloc = PostingAllocation(
                    posting_id=posting_id,
                    amount_minor=posting.amount_minor,
                )
                db.add(alloc)

            if "category_id" in patch:
                new_cat = patch["category_id"] or None
                old_cat = alloc.category_id

                # Log the override for ML training
                if new_cat != old_cat:
                    db.add(CategoryOverrideLog(
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

    with Session(engine) as db:
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
            alloc = PostingAllocation(
                posting_id=posting_id,
                household_id=posting.household_id,
                category_id=s.get("category_id"),
                amount_minor=int(s.get("amount_minor", 0)),
                note=s.get("note"),
                item_name=s.get("item_name"),
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
) -> dict[str, Any]:
    """Serialize a Posting + its allocations to the API JSON shape.

    Amount is returned as a string (§7 rule).
    """
    # Get the primary allocation (first one, or None)
    primary = allocations[0] if allocations else None

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
    with Session(engine) as db:
        alloc = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == posting_id)).first()
        if not alloc:
            return False

        alloc.category_id = category_id
        alloc.updated_at = _utcnow_iso()
        db.add(alloc)
        db.commit()
        return True

def apply_rule_retroactively(rule_id: str) -> int:
    """Find all postings that match a categorization rule and update them.

    Returns the number of updated postings.
    """
    from app.rules_service import get_compiled_regex, preprocess_description

    updated_count = 0
    with Session(engine) as db:
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

    with Session(engine) as db:
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

        splits = []
        sum_items = 0

        # Most receipts are positive totals. If posting is a negative expense, invert signs
        receipt_total = receipt_data["receipt"].get("receipt_total_minor", 0)
        multiplier = -1 if posting.amount_minor < 0 and receipt_total > 0 else 1

        from app.rules_service import evaluate_text

        for occ in occurrences:
            # net_total_minor is the item's total including item-level discounts
            amt = occ.get("net_total_minor", 0) * multiplier
            sum_items += amt

            item_name = occ.get("display_name")
            category_id = None
            if item_name:
                category_id = evaluate_text(item_name)

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

        if sum_items != abs(posting.amount_minor):
            diff = abs(posting.amount_minor) - sum_items
            splits.append({
                "amount_minor": diff * multiplier,
                "item_name": "Difference / Gebyr",
                "item_cluster_id": None,
                "category_id": None,
                "note": "Automatisk difference (fra kvittering)"
            })

        return split_allocation(posting_id, splits)


def auto_link_receipts(min_date: str | None = None, max_date: str | None = None) -> int:
    """
    Scans un-split Postings for matches with imported receipts and automatically links and splits them.
    """
    from .kvitteringer_service import link_peng_transaction_to_receipt
    linked_count = 0

    with Session(engine) as db:
        query = select(Posting).where(col(Posting.amount_minor) < 0)
        
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
                if result.get("linked") and not result.get("cached"):
                    # We found a new match!
                    receipt_id = str(result.get("receipt_id"))
                    link_receipt_to_transaction(posting.id, receipt_id, is_auto=True)
                    linked_count += 1
            except Exception as e:
                print(f"Error auto-linking posting {posting.id}: {e}")
                
    return linked_count
