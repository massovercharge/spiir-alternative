"""Tests for internal transfer auto-detection."""
from sqlmodel import Session, select

from app.models import (
    Account,
    Category,
    Posting,
    PostingAllocation,
    engine,
)
from app.services.transfer_service import detect_internal_transfers


def test_detect_internal_transfers_creates_category_and_links():
    # Verify no transfer category initially exists
    with Session(engine) as db:
        cat = db.get(Category, "vis-ikke|kontooverforsel")
        assert cat is None

        # Create two accounts
        acc1 = Account(uid="acc_checking", name="Lønkonto", account_type="Indlån", source="bank")
        acc2 = Account(uid="acc_budget", name="Budgetkonto", account_type="Indlån", source="bank")
        db.add(acc1)
        db.add(acc2)

        # Create transfer postings: -1000 DKK on acc1, +1000 DKK on acc2 on same date
        p1 = Posting(
            id="p_out",
            account_uid="acc_checking",
            booking_date="2026-01-10",
            amount_minor=-100000,
            original_description="Overførsel",
        )
        p2 = Posting(
            id="p_in",
            account_uid="acc_budget",
            booking_date="2026-01-10",
            amount_minor=100000,
            original_description="Overførsel",
        )
        db.add(p1)
        db.add(p2)

        a1 = PostingAllocation(posting_id="p_out", amount_minor=-100000, category_id="diverse|ikke-kategoriseret")
        a2 = PostingAllocation(posting_id="p_in", amount_minor=100000, category_id="diverse|ikke-kategoriseret")
        db.add(a1)
        db.add(a2)
        db.commit()

    result = detect_internal_transfers()
    assert result["matched_pairs"] == 1

    with Session(engine) as db:
        # Category was created automatically without crashing
        cat = db.get(Category, "vis-ikke|kontooverførsel")
        assert cat is not None
        assert cat.main_name == "Vis ikke"
        assert cat.sub_name == "Kontooverførsel"

        # Both allocations were updated to transfer category
        allocs = db.exec(select(PostingAllocation)).all()
        for alloc in allocs:
            assert alloc.category_id == cat.id
