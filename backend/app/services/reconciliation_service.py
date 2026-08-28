"""Reconciliation Service — Automatic deduplication, overlap merge, and cross-account reconciliation."""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from sqlmodel import Session, select

from app.models import (
    Account,
    Document,
    Posting,
    PostingAllocation,
    PostingAllocationTagLink,
)

logger = logging.getLogger("peng.reconciliation_service")

UNCATEGORIZED_SLUGS = {
    "diverse|ikke-kategoriseret",
    "diverse|ukategoriseret",
    "none",
    "",
    None,
}


def clean_description_for_matching(s: Optional[str]) -> str:
    """Normalize text by stripping common payment prefixes and non-alphanumeric chars."""
    if not s:
        return ""
    text = s.lower()
    prefixes = [
        "mobilepay:",
        "mobilepay køb",
        "mobilepay",
        "dankort-nota",
        "dankort",
        "visa køb",
        "visa",
        "betalingsservice",
        "overførsel",
        "nota",
    ]
    for prefix in prefixes:
        text = text.replace(prefix, "")
    return re.sub(r"[^a-z0-9æøå]", "", text).strip()


def descriptions_match(desc1: Optional[str], desc2: Optional[str]) -> bool:
    """Check whether two descriptions refer to the same payee or transaction."""
    c1 = clean_description_for_matching(desc1)
    c2 = clean_description_for_matching(desc2)
    if not c1 or not c2:
        return True  # If one description is blank, allow date+amount match

    if c1 == c2 or c1 in c2 or c2 in c1:
        return True

    # Check words overlap
    words1 = set(re.findall(r"[a-z0-9æøå]{3,}", c1))
    words2 = set(re.findall(r"[a-z0-9æøå]{3,}", c2))
    if words1 and words2 and len(words1 & words2) > 0:
        return True

    # Prefix overlap (e.g. nettopk vs nettopr)
    if len(c1) >= 4 and len(c2) >= 4 and c1[:5] == c2[:5]:
        return True

    return False


def find_duplicate_candidate_in_db(
    session: Session,
    household_id: str,
    target_posting: Posting,
    exclude_account_uid: Optional[str] = None,
) -> Optional[Posting]:
    """Find an existing duplicate posting in the household matching date, amount, and description."""
    eff_date = target_posting.custom_date or target_posting.booking_date
    if not eff_date or target_posting.amount_minor == 0:
        return None

    query = (
        select(Posting)
        .where(Posting.household_id == household_id)
        .where(Posting.id != target_posting.id)
        .where(Posting.amount_minor == target_posting.amount_minor)
    )

    if exclude_account_uid:
        query = query.where(Posting.account_uid != exclude_account_uid)

    candidates = session.exec(query).all()

    for cand in candidates:
        cand_date = cand.custom_date or cand.booking_date
        if cand_date == eff_date:
            if descriptions_match(target_posting.original_description, cand.original_description):
                return cand

    return None


def consolidate_posting_pair(
    session: Session,
    kept_posting_id: str,
    removed_posting_id: str,
) -> dict[str, Any]:
    """Consolidate metadata (categories, notes, splits, tags, receipts) from removed_posting into kept_posting, then delete removed_posting."""
    stats = {
        "categories_migrated": False,
        "notes_migrated": False,
        "splits_migrated": False,
        "tags_migrated": 0,
        "documents_migrated": 0,
        "extraordinary_migrated": False,
    }

    kp = session.get(Posting, kept_posting_id)
    rp = session.get(Posting, removed_posting_id)

    if not kp or not rp:
        return stats

    # Allocations
    k_allocs = session.exec(
        select(PostingAllocation).where(PostingAllocation.posting_id == kept_posting_id)
    ).all()
    r_allocs = session.exec(
        select(PostingAllocation).where(PostingAllocation.posting_id == removed_posting_id)
    ).all()

    # 1. Custom Date & Excluded
    if rp.custom_date and not kp.custom_date:
        kp.custom_date = rp.custom_date
    if rp.is_excluded and not kp.is_excluded:
        kp.is_excluded = True

    # 2. Case: Removed posting has SPLITS (multiple allocations)
    if len(r_allocs) > 1:
        stats["splits_migrated"] = True
        # Delete default kept allocations
        for ka in k_allocs:
            tag_links = session.exec(
                select(PostingAllocationTagLink).where(
                    PostingAllocationTagLink.allocation_id == ka.id
                )
            ).all()
            for tl in tag_links:
                session.delete(tl)
            docs = session.exec(
                select(Document).where(Document.allocation_id == ka.id)
            ).all()
            for doc in docs:
                session.delete(doc)
            session.delete(ka)

        # Clone each removed allocation onto kept posting
        for ra in r_allocs:
            new_alloc_id = uuid.uuid4().hex
            new_alloc = PostingAllocation(
                id=new_alloc_id,
                household_id=kp.household_id,
                posting_id=kept_posting_id,
                category_id=ra.category_id,
                amount_minor=ra.amount_minor,
                note=ra.note,
                is_extraordinary=ra.is_extraordinary,
                item_name=ra.item_name,
                item_cluster_id=ra.item_cluster_id,
                recurring_transaction_id=ra.recurring_transaction_id,
            )
            session.add(new_alloc)

            # Re-link tags
            r_tags = session.exec(
                select(PostingAllocationTagLink).where(
                    PostingAllocationTagLink.allocation_id == ra.id
                )
            ).all()
            for tl in r_tags:
                session.add(PostingAllocationTagLink(allocation_id=new_alloc_id, tag_id=tl.tag_id))
                session.delete(tl)

            # Re-link docs
            r_docs = session.exec(
                select(Document).where(Document.allocation_id == ra.id)
            ).all()
            for doc in r_docs:
                doc.allocation_id = new_alloc_id
                session.add(doc)

            session.delete(ra)

    # 3. Case: 1:1 allocation consolidation
    elif len(k_allocs) >= 1 and len(r_allocs) >= 1:
        ka = k_allocs[0]
        ra = r_allocs[0]

        # Category
        ra_cat = ra.category_id
        ka_cat = ka.category_id
        if (
            ra_cat
            and ra_cat not in UNCATEGORIZED_SLUGS
            and (not ka_cat or ka_cat in UNCATEGORIZED_SLUGS)
        ):
            ka.category_id = ra_cat
            stats["categories_migrated"] = True

        # Note
        ra_note = (ra.note or "").strip()
        ka_note = (ka.note or "").strip()
        if ra_note:
            if not ka_note:
                ka.note = ra_note
                stats["notes_migrated"] = True
            elif ra_note != ka_note:
                ka.note = f"{ka_note} | {ra_note}"
                stats["notes_migrated"] = True

        # Extraordinary
        if ra.is_extraordinary and not ka.is_extraordinary:
            ka.is_extraordinary = True
            stats["extraordinary_migrated"] = True

        # Item Name
        if not ka.item_name and ra.item_name:
            ka.item_name = ra.item_name

        session.add(ka)

        # Re-link tags
        r_tags = session.exec(
            select(PostingAllocationTagLink).where(
                PostingAllocationTagLink.allocation_id == ra.id
            )
        ).all()
        for tl in r_tags:
            existing = session.exec(
                select(PostingAllocationTagLink)
                .where(PostingAllocationTagLink.allocation_id == ka.id)
                .where(PostingAllocationTagLink.tag_id == tl.tag_id)
            ).first()
            if not existing:
                session.add(
                    PostingAllocationTagLink(allocation_id=ka.id, tag_id=tl.tag_id)
                )
                stats["tags_migrated"] += 1
            session.delete(tl)

        # Re-link documents
        r_docs = session.exec(
            select(Document).where(Document.allocation_id == ra.id)
        ).all()
        for doc in r_docs:
            doc.allocation_id = ka.id
            session.add(doc)
            stats["documents_migrated"] += 1

        # Delete removed allocation
        session.delete(ra)

    # Delete the removed posting
    session.delete(rp)
    session.flush()

    return stats


def reconcile_incoming_postings(
    session: Session,
    household_id: str,
    incoming_posting_ids: list[str],
) -> dict[str, Any]:
    """Scan newly ingested postings and reconcile them against any existing duplicate history in the household."""
    summary = {
        "checked_count": len(incoming_posting_ids),
        "reconciled_count": 0,
        "categories_migrated": 0,
        "splits_migrated": 0,
    }

    for pid in incoming_posting_ids:
        posting = session.get(Posting, pid)
        if not posting:
            continue

        duplicate_candidate = find_duplicate_candidate_in_db(
            session,
            household_id=household_id,
            target_posting=posting,
            exclude_account_uid=posting.account_uid,
        )

        if duplicate_candidate:
            # If incoming is live bank sync and candidate is CSV -> keep incoming bank, merge candidate CSV
            is_incoming_bank = posting.id.startswith("eb:")
            is_cand_bank = duplicate_candidate.id.startswith("eb:")

            if is_incoming_bank and not is_cand_bank:
                kept_id = posting.id
                removed_id = duplicate_candidate.id
            elif not is_incoming_bank and is_cand_bank:
                kept_id = duplicate_candidate.id
                removed_id = posting.id
            else:
                # Same source or default -> keep the newly ingested one
                kept_id = posting.id
                removed_id = duplicate_candidate.id

            stats = consolidate_posting_pair(session, kept_id, removed_id)
            summary["reconciled_count"] += 1
            if stats.get("categories_migrated"):
                summary["categories_migrated"] += 1
            if stats.get("splits_migrated"):
                summary["splits_migrated"] += 1

    return summary


def merge_accounts(
    session: Session,
    household_id: str,
    source_account_uid: str,
    target_account_uid: str,
) -> dict[str, Any]:
    """Merge all postings from source_account into target_account, reconcile overlapping transactions, and remove source account."""
    src_acc = session.get(Account, source_account_uid)
    tgt_acc = session.get(Account, target_account_uid)

    if not src_acc or not tgt_acc:
        raise ValueError("Source or target account not found")

    if src_acc.household_id != household_id or tgt_acc.household_id != household_id:
        raise ValueError("Accounts do not belong to the active household")

    # 1. Fetch all postings on source account
    src_postings = session.exec(
        select(Posting).where(Posting.account_uid == source_account_uid)
    ).all()

    migrated_count = len(src_postings)
    reconciled_duplicates = 0

    # 2. Re-point postings to target account and reconcile duplicates
    for p in src_postings:
        p.account_uid = target_account_uid
        session.add(p)

    session.flush()

    # Reconcile any duplicates that now exist on target_account or cross-account
    tgt_postings = session.exec(
        select(Posting).where(Posting.account_uid == target_account_uid)
    ).all()

    seen_pairs: set[tuple[str, int, str]] = set()
    to_check_ids = [p.id for p in tgt_postings]

    for pid in to_check_ids:
        p = session.get(Posting, pid)
        if not p:
            continue
        key = (p.custom_date or p.booking_date, p.amount_minor, clean_description_for_matching(p.original_description))
        if key in seen_pairs:
            # Duplicate found
            cand = find_duplicate_candidate_in_db(session, household_id, p)
            if cand and cand.id != p.id:
                consolidate_posting_pair(session, kept_posting_id=cand.id, removed_posting_id=p.id)
                reconciled_duplicates += 1
        else:
            seen_pairs.add(key)

    # Delete source account
    session.delete(src_acc)
    session.commit()

    return {
        "success": True,
        "source_account_uid": source_account_uid,
        "target_account_uid": target_account_uid,
        "postings_migrated": migrated_count,
        "duplicates_reconciled": reconciled_duplicates,
    }


def resolve_all_household_duplicates(
    session: Session,
    household_id: str,
) -> dict[str, Any]:
    """Find and automatically resolve all current duplicate candidate pairs in the household."""
    from app.services.notification_service import _get_duplicate_transactions_for_household

    duplicates = _get_duplicate_transactions_for_household(household_id)
    resolved_count = 0
    categories_migrated = 0
    splits_migrated = 0

    # Pair duplicates by date & amount
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for d in duplicates:
        key = (d["date"], d["amount_minor"])
        groups.setdefault(key, []).append(d)

    for (date_str, amt), tx_list in groups.items():
        if len(tx_list) >= 2:
            # Prefer keeping the live bank post (eb:...) if present
            bank_item = next((tx for tx in tx_list if tx["id"].startswith("eb:")), tx_list[0])
            csv_items = [tx for tx in tx_list if tx["id"] != bank_item["id"]]

            for csv_item in csv_items:
                stats = consolidate_posting_pair(
                    session,
                    kept_posting_id=bank_item["id"],
                    removed_posting_id=csv_item["id"],
                )
                resolved_count += 1
                if stats.get("categories_migrated"):
                    categories_migrated += 1
                if stats.get("splits_migrated"):
                    splits_migrated += 1

    session.commit()

    return {
        "success": True,
        "resolved_duplicates_count": resolved_count,
        "categories_migrated": categories_migrated,
        "splits_migrated": splits_migrated,
    }
