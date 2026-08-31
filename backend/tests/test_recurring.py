"""Tests for recurring transactions (fixed expenses/income) logic."""

import pytest
from conftest import TEST_HOUSEHOLD_ID
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Account,
    Household,
    Posting,
    PostingAllocation,
    RecurringTransaction,
)
from app.services.recurring_service import (
    create_recurring,
    delete_recurring,
    detect_recurring,
    list_recurring,
    match_posting_to_recurring,
)


@pytest.fixture()
def engine():
    """Create an in-memory SQLite engine with StaticPool."""
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
    """Patch service modules to use the test engine."""
    import app.services.recurring_service as rs

    monkeypatch.setattr(rs, "engine", engine)


@pytest.fixture()
def seeded_db(engine, _patch_engine):
    """Seed postings for detection tests."""
    with Session(engine) as db:
        db.add(Household(id=TEST_HOUSEHOLD_ID, name="Test Husstand"))
        db.add(Account(uid="acc1", household_id=TEST_HOUSEHOLD_ID, session_name="test"))

        # 3 Netflix payments (~ 30 days apart)
        db.add(
            Posting(
                id="p1",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc1",
                amount_minor=-9900,
                booking_date="2026-05-01",
                original_description="NETFLIX.COM",
            )
        )
        db.add(
            Posting(
                id="p2",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc1",
                amount_minor=-9900,
                booking_date="2026-06-01",
                original_description="NETFLIX.COM",
            )
        )
        db.add(
            Posting(
                id="p3",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc1",
                amount_minor=-9900,
                booking_date="2026-07-01",
                original_description="NETFLIX.COM",
            )
        )

        # 2 Spotify payments (not enough for recurring detection which requires 3)
        db.add(
            Posting(
                id="p4",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc1",
                amount_minor=-10900,
                booking_date="2026-06-05",
                original_description="Spotify AB",
            )
        )
        db.add(
            Posting(
                id="p5",
                household_id=TEST_HOUSEHOLD_ID,
                account_uid="acc1",
                amount_minor=-10900,
                booking_date="2026-07-05",
                original_description="Spotify AB",
            )
        )

        db.commit()
    return engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecurringDetection:
    def test_detect_recurring(self, seeded_db):
        suggestions = detect_recurring()

        assert len(suggestions) == 1
        sug = suggestions[0]
        assert sug["match_pattern"] == "netflix com"
        assert sug["avg_amount_minor"] == -9900
        assert sug["occurrences"] == 3


class TestRecurringMatching:
    def test_match_and_advance_date(self, seeded_db):
        # Create a recurring transaction
        rtx = create_recurring(
            {
                "name": "Netflix",
                "amount_minor": -9900,
                "match_pattern": "netflix com",
                "next_date": "2026-07-01",
                "interval": "monthly",
            }
        )

        # Process a new posting that matches
        posting = Posting(
            id="p_new",
            household_id=TEST_HOUSEHOLD_ID,
            account_uid="acc1",
            amount_minor=-9900,
            booking_date="2026-07-01T10:00:00Z",
            original_description="VISA KØB NETFLIX.COM",
        )
        alloc = PostingAllocation(posting_id="p_new", amount_minor=-9900)

        # Match it
        with Session(seeded_db) as db:
            active_txs = db.exec(select(RecurringTransaction)).all()

        matched = match_posting_to_recurring(posting, alloc, recurring_txs=active_txs)

        assert matched is not None
        assert matched.id == rtx["id"]
        assert alloc.recurring_transaction_id == rtx["id"]
        # Next date should advance to next month
        assert matched.next_date == "2026-08-01"


class TestRecurringCRUD:
    def test_create_and_list(self, seeded_db):
        rtx = create_recurring(
            {
                "name": "Husleje",
                "amount_minor": -850000,
                "match_pattern": "husleje",
                "category_id": "bolig|husleje",
            }
        )

        assert rtx["name"] == "Husleje"

        lst = list_recurring()
        assert any(r["id"] == rtx["id"] for r in lst)

    def test_delete(self, seeded_db):
        rtx = create_recurring(
            {"name": "Delete Me", "amount_minor": -100, "match_pattern": "delete"}
        )

        assert delete_recurring(rtx["id"]) is True
        assert delete_recurring(rtx["id"]) is False
