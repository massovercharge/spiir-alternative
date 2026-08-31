"""Service for parsing and importing Spiir CSV exports."""

import csv
import datetime
import io
import re
import uuid
from typing import Any

from sqlmodel import Session, select

from app.core.money import to_minor
from app.models import (
    Account,
    Posting,
    PostingAllocation,
    PostingAllocationTagLink,
    Tag,
    engine,
)
from app.services.category_service import list_categories


def _slugify(text: str) -> str:
    if not text:
        return ""
    s = text.lower()
    s = re.sub(r"[^a-z0-9æøå/]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def _parse_amount(amount_str: str) -> int:
    """Parse Spiir amount ('-5231,28') to minor units (-523128)."""
    if not amount_str:
        return 0
    clean = amount_str.replace(".", "").replace(",", ".")
    try:
        return to_minor(clean)
    except (ValueError, TypeError):
        return 0


def _parse_date(date_str: str) -> str:
    """Parse Spiir date ('04-10-2019') to ISO ('2019-10-04')."""
    try:
        dt = datetime.datetime.strptime(date_str, "%d-%m-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def import_spiir_csv(file_content: str) -> dict[str, Any]:
    """Parse and merge Spiir CSV into the database."""
    reader = csv.DictReader(io.StringIO(file_content), delimiter=";")

    with Session(engine) as db:
        # Pre-fetch all categories for fast mapping
        all_cats = list_categories()
        # Create a mapping: "bolig|boliglån/husleje" -> "cat_id"
        cat_map: dict[str, str] = {}
        for cat in all_cats:
            slug = f"{_slugify(cat['mainCategoryName'])}|{_slugify(cat['categoryName'])}"
            cat_map[slug] = cat["id"]

        fallback_cat = None

        stats = {
            "total_rows": 0,
            "imported_new": 0,
            "merged_existing": 0,
            "skipped": 0,
            "accounts_created": 0,
        }

        # Cache accounts by Spiir AccountId
        spiir_accounts: dict[str, str] = {}

        for row in reader:
            stats["total_rows"] += 1

            # Extract fields
            date_str = _parse_date(row.get("Date", ""))
            amount_minor = _parse_amount(row.get("Amount", "0"))
            description = row.get("Description", "")
            orig_desc = row.get("OriginalDescription", "")

            main_cat = row.get("MainCategoryName", "")
            sub_cat = row.get("CategoryName", "")

            spiir_acc_id = row.get("AccountId", "")
            spiir_acc_name = row.get("AccountName", "")

            if not date_str or not spiir_acc_id:
                stats["skipped"] += 1
                continue

            # Determine category
            cat_id = None
            if main_cat and sub_cat:
                slug = f"{_slugify(main_cat)}|{_slugify(sub_cat)}"
                cat_id = cat_map.get(slug, fallback_cat)

            # Find matching existing transaction (Date + Amount)
            # We look across all accounts because we don't know the mapping.
            # To be safe, we only match if there is EXACTLY one match.
            existing_postings = db.exec(
                select(Posting)
                .where(Posting.booking_date == date_str)
                .where(Posting.amount_minor == amount_minor)
            ).all()

            if existing_postings:
                # Merge! Update category if we have a valid one from Spiir
                # and if it doesn't already have a valid category
                for ep in existing_postings:
                    alloc = db.exec(
                        select(PostingAllocation).where(PostingAllocation.posting_id == ep.id)
                    ).first()

                    if alloc:
                        if cat_id and cat_id != fallback_cat:
                            alloc.category_id = cat_id

                        # Merge Note, Extraordinary, Custom Date
                        if row.get("Comment"):
                            alloc.note = row.get("Comment", "")
                        if row.get("Extraordinary", "No").lower() == "yes":
                            alloc.is_extraordinary = True

                        db.add(alloc)
                        db.flush()

                        custom_date_str = _parse_date(row.get("CustomDate", ""))
                        if custom_date_str and custom_date_str != date_str:
                            ep.custom_date = custom_date_str
                            db.add(ep)

                        # Merge Tags
                        tags_str = row.get("Tags", "")
                        if tags_str:
                            tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
                            for tname in tag_names:
                                tag = db.exec(select(Tag).where(Tag.name == tname)).first()
                                if not tag:
                                    tag = Tag(name=tname)
                                    db.add(tag)
                                    db.flush()

                                # Check if link already exists
                                existing_link = db.exec(
                                    select(PostingAllocationTagLink)
                                    .where(PostingAllocationTagLink.allocation_id == alloc.id)
                                    .where(PostingAllocationTagLink.tag_id == tag.id)
                                ).first()
                                if not existing_link:
                                    link = PostingAllocationTagLink(
                                        allocation_id=alloc.id, tag_id=tag.id
                                    )
                                    db.add(link)

                stats["merged_existing"] += 1
                continue

            # No existing match, so this is a purely historical transaction.
            # Ensure the Spiir account exists as an archive account.
            if spiir_acc_id not in spiir_accounts:
                acc_uid = f"csv:{spiir_acc_id}"
                acc = db.exec(select(Account).where(Account.uid == acc_uid)).first()
                if not acc:
                    acc = Account(uid=acc_uid, name=f"{spiir_acc_name} (Spiir)", source="csv")
                    db.add(acc)
                    stats["accounts_created"] += 1
                spiir_accounts[spiir_acc_id] = acc_uid

            acc_uid = spiir_accounts[spiir_acc_id]

            # Create Posting
            posting_id = f"csv:{spiir_acc_id}:{row.get('Id', uuid.uuid4().hex)}"
            posting = Posting(
                id=posting_id,
                account_uid=acc_uid,
                booking_date=date_str,
                amount_minor=amount_minor,
                original_description=orig_desc or description,
                currency=row.get("Currency", "DKK"),
            )
            db.add(posting)

            # Create Allocation
            alloc = PostingAllocation(
                posting_id=posting_id,
                amount_minor=amount_minor,
                category_id=cat_id,
                note=row.get("Comment", ""),
                is_extraordinary=(row.get("Extraordinary", "No").lower() == "yes"),
            )
            db.add(alloc)
            db.flush()  # Need to flush to get alloc.id for tags

            # Custom date
            custom_date_str = _parse_date(row.get("CustomDate", ""))
            if custom_date_str and custom_date_str != date_str:
                posting.custom_date = custom_date_str

            # Tags
            tags_str = row.get("Tags", "")
            if tags_str:
                tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
                for tname in tag_names:
                    tag = db.exec(select(Tag).where(Tag.name == tname)).first()
                    if not tag:
                        tag = Tag(name=tname)
                        db.add(tag)
                        db.flush()

                    link = PostingAllocationTagLink(allocation_id=alloc.id, tag_id=tag.id)
                    db.add(link)

            stats["imported_new"] += 1

        db.commit()
        return stats
