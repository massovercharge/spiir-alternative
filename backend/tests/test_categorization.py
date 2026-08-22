"""Tests for manual categorization and user rules."""

import pytest
from conftest import TEST_HOUSEHOLD_ID
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Account, Household, Posting, PostingAllocation
from app.services.rules_service import create_rule
from app.services.transaction_service import apply_rule_retroactively, update_transaction_category


@pytest.fixture()
def engine():
    from sqlalchemy.pool import StaticPool
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    SQLModel.metadata.create_all(eng)
    return eng

@pytest.fixture()
def _patch_engine(engine, monkeypatch):
    import app.services.category_service as cs
    import app.models as db_mod
    import app.services.rules_service as rs
    import app.services.transaction_service as ts
    monkeypatch.setattr(db_mod, "engine", engine)
    monkeypatch.setattr(ts, "engine", engine)
    monkeypatch.setattr(rs, "engine", engine)
    monkeypatch.setattr(cs, "engine", engine)

@pytest.fixture()
def seeded_db(engine, _patch_engine):
    from app.services.category_service import seed_categories
    seed_categories()

    with Session(engine) as db:
        db.add(Household(id=TEST_HOUSEHOLD_ID, name="Test Husstand"))
        acc = Account(uid="test-acc", household_id=TEST_HOUSEHOLD_ID, name="Test Account", source="test")
        db.add(acc)

        # Add some postings
        p1 = Posting(id="p1", household_id=TEST_HOUSEHOLD_ID, account_uid="test-acc", booking_date="2026-07-01", amount_minor=-5000, original_description="Kaffebaren aps", currency="DKK")
        p2 = Posting(id="p2", household_id=TEST_HOUSEHOLD_ID, account_uid="test-acc", booking_date="2026-07-02", amount_minor=-3000, original_description="Kaffebaren aps", currency="DKK")
        p3 = Posting(id="p3", household_id=TEST_HOUSEHOLD_ID, account_uid="test-acc", booking_date="2026-07-03", amount_minor=-20000, original_description="Netto", currency="DKK")

        db.add_all([p1, p2, p3])

        # Allocations
        db.add(PostingAllocation(posting_id="p1", amount_minor=-5000, category_id="diverse|ikke-kategoriseret"))
        db.add(PostingAllocation(posting_id="p2", amount_minor=-3000, category_id="diverse|ikke-kategoriseret"))
        db.add(PostingAllocation(posting_id="p3", amount_minor=-20000, category_id="dagligvarer|supermarked"))

        db.commit()
    return engine

def test_update_transaction_category(seeded_db):
    """Test that we can manually update a single transaction's category."""
    updated = update_transaction_category("p1", "privatforbrug|cafe-restaurant")
    assert updated is True

    with Session(seeded_db) as db:
        alloc = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == "p1")).first()
        assert alloc.category_id == "privatforbrug|cafe-restaurant"

        # Ensure p2 is untouched
        alloc2 = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == "p2")).first()
        assert alloc2.category_id == "diverse|ikke-kategoriseret"

def test_apply_rule_retroactively(seeded_db):
    """Test that creating a user rule and applying it retroactively updates matching transactions."""
    # 1. Create a user rule
    rule = create_rule(
        match_pattern="kaffebaren",
        category_id="privatforbrug|cafe-restaurant",
        is_regex=False,
        priority=500  # User priority
    )

    # 2. Apply it retroactively
    count = apply_rule_retroactively(rule["id"])

    assert count == 2  # p1 and p2 should match "kaffebaren"

    with Session(seeded_db) as db:
        a1 = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == "p1")).first()
        a2 = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == "p2")).first()
        a3 = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == "p3")).first()

        assert a1.category_id == "privatforbrug|cafe-restaurant"
        assert a2.category_id == "privatforbrug|cafe-restaurant"
        assert a3.category_id == "dagligvarer|supermarked"  # Unchanged
