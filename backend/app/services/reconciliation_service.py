"""Reconciliation Service — Automatic deduplication, overlap merge, and cross-account reconciliation."""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.money import format_amount
from app.models import (
    Account,
    DismissedDuplicate,
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
    return bool(len(c1) >= 4 and len(c2) >= 4 and c1[:5] == c2[:5])


def are_accounts_duplicate_pair(
    session: Session,
    acc_uid1: str,
    acc_uid2: str,
    allow_same_account: bool = False,
) -> bool:
    """Check if two accounts represent the same physical account (e.g. CSV archive + Bank sync)."""
    if acc_uid1 == acc_uid2:
        return allow_same_account
    acc1 = session.get(Account, acc_uid1)
    acc2 = session.get(Account, acc_uid2)
    if not acc1 or not acc2:
        return False

    is_csv_bank_pair = (acc1.source == "csv" and acc2.source == "enablebanking") or (
        acc1.source == "enablebanking" and acc2.source == "csv"
    )
    name1 = acc1.name.replace("(Spiir)", "").replace("(CSV)", "").strip().lower()
    name2 = acc2.name.replace("(Spiir)", "").replace("(CSV)", "").strip().lower()

    if name1 == name2:
        return True

    return bool(is_csv_bank_pair and (name1 in name2 or name2 in name1))


def find_duplicate_candidate_in_db(
    session: Session,
    household_id: str,
    target_posting: Posting,
    exclude_account_uid: Optional[str] = None,
    allow_same_account: bool = False,
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
            if not are_accounts_duplicate_pair(
                session,
                target_posting.account_uid,
                cand.account_uid,
                allow_same_account=allow_same_account,
            ):
                continue
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
            cand = find_duplicate_candidate_in_db(session, household_id, p, allow_same_account=True)
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


def get_dismissed_duplicate_pairs(session: Session, household_id: str) -> set[tuple[str, str]]:
    """Return set of normalized (id1, id2) pairs that have been marked as not duplicate."""
    dismissed = session.exec(
        select(DismissedDuplicate).where(DismissedDuplicate.household_id == household_id)
    ).all()
    pairs = set()
    for d in dismissed:
        p1, p2 = min(d.posting_id_1, d.posting_id_2), max(d.posting_id_1, d.posting_id_2)
        pairs.add((p1, p2))
    return pairs


def dismiss_duplicate_pair(
    session: Session,
    household_id: str,
    posting_ids: list[str],
) -> int:
    """Mark a set of postings as NOT being duplicates of each other."""
    if len(posting_ids) < 2:
        return 0
    existing = get_dismissed_duplicate_pairs(session, household_id)
    added_count = 0
    import itertools
    for p1, p2 in itertools.combinations(posting_ids, 2):
        pair = (min(p1, p2), max(p1, p2))
        if pair not in existing:
            session.add(DismissedDuplicate(
                household_id=household_id,
                posting_id_1=pair[0],
                posting_id_2=pair[1],
            ))
            existing.add(pair)
            added_count += 1
    session.commit()
    return added_count


def dismiss_all_same_account_duplicates(
    session: Session,
    household_id: str,
) -> int:
    """Find all same-account duplicate groups and dismiss them in bulk."""
    groups = get_duplicate_groups_preview(session, household_id)
    total_dismissed = 0
    for g in groups:
        if not g["can_auto_merge"]:
            pids = [p["id"] for p in g["postings"]]
            total_dismissed += dismiss_duplicate_pair(session, household_id, pids)
    return total_dismissed


def get_duplicate_groups_preview(
    session: Session,
    household_id: str,
) -> list[dict[str, Any]]:
    """Return structured preview of all potential duplicate groups for user review."""
    eff_date_col = func.coalesce(Posting.custom_date, Posting.booking_date)
    query = (
        select(Posting)
        .where(Posting.household_id == household_id)
        .where(col(Posting.amount_minor) != 0)
        .order_by(eff_date_col.desc())
    )
    postings = session.exec(query).all()
    accounts_by_uid = {
        a.uid: a
        for a in session.exec(select(Account).where(Account.household_id == household_id)).all()
    }
    dismissed_pairs = get_dismissed_duplicate_pairs(session, household_id)

    groups: dict[tuple[str, int, str], list[Posting]] = {}
    statutory_keywords = ("børne- og ungeydelse", "børneydelse", "børnepenge", "børnecheck", "børnetilskud", "ungeydelse")
    for p in postings:
        eff_date = p.custom_date or p.booking_date or ""
        clean_desc = clean_description_for_matching(p.original_description)
        if not eff_date or not clean_desc:
            continue
        # Exclude known statutory child allowance / split benefits across parents
        lower_desc = (p.original_description or "").lower()
        if any(kw in lower_desc for kw in statutory_keywords):
            continue
        key = (eff_date, p.amount_minor, clean_desc)
        groups.setdefault(key, []).append(p)

    preview_groups = []
    import itertools
    for (eff_date, amount_minor, clean_desc), plist in groups.items():
        if len(plist) < 2:
            continue

        # Skip group if all pairs in plist are already dismissed as not duplicate
        all_dismissed = True
        for p1, p2 in itertools.combinations(plist, 2):
            if (min(p1.id, p2.id), max(p1.id, p2.id)) not in dismissed_pairs:
                all_dismissed = False
                break
        if all_dismissed:
            continue

        # Check if this pair is a cross-account archive duplicate pair that can safely be merged
        can_auto_merge = False
        if len(plist) == 2:
            acc1 = accounts_by_uid.get(plist[0].account_uid)
            acc2 = accounts_by_uid.get(plist[1].account_uid)
            if acc1 and acc2 and are_accounts_duplicate_pair(session, acc1.uid, acc2.uid, allow_same_account=False):
                can_auto_merge = True

        postings_data = []
        for p in plist:
            acc = accounts_by_uid.get(p.account_uid)
            allocs = session.exec(
                select(PostingAllocation).where(PostingAllocation.posting_id == p.id)
            ).all()
            category_id = allocs[0].category_id if allocs else None
            note = allocs[0].note if allocs else None
            postings_data.append({
                "id": p.id,
                "account_uid": p.account_uid,
                "account_name": acc.name if acc else p.account_uid,
                "account_source": acc.source if acc else "unknown",
                "original_description": p.original_description,
                "amount_minor": p.amount_minor,
                "amount": format_amount(abs(p.amount_minor)),
                "date": eff_date,
                "category_id": category_id,
                "note": note,
                "split_count": len(allocs),
            })

        preview_groups.append({
            "group_id": f"{eff_date}_{amount_minor}_{clean_desc[:12]}",
            "date": eff_date,
            "amount_minor": amount_minor,
            "amount": format_amount(abs(amount_minor)),
            "description": plist[0].original_description,
            "can_auto_merge": can_auto_merge,
            "postings": postings_data,
        })

    return preview_groups


def resolve_all_household_duplicates(
    session: Session,
    household_id: str,
) -> dict[str, Any]:
    """Find and automatically resolve ONLY cross-account archive duplicate pairs (Spiir/CSV vs EnableBanking)."""
    groups = get_duplicate_groups_preview(session, household_id)
    resolved_count = 0
    categories_migrated = 0
    splits_migrated = 0

    for g in groups:
        if not g["can_auto_merge"]:
            continue
        plist = g["postings"]
        if len(plist) == 2:
            p1_id = plist[0]["id"]
            p2_id = plist[1]["id"]
            if p2_id.startswith("eb:") and not p1_id.startswith("eb:"):
                kept_id, removed_id = p2_id, p1_id
            else:
                kept_id, removed_id = p1_id, p2_id

            stats = consolidate_posting_pair(
                session, kept_posting_id=kept_id, removed_posting_id=removed_id
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
