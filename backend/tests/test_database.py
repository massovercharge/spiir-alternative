"""Comprehensive tests for the V2 backend."""
import pytest
from datetime import date
from sqlmodel import Session, SQLModel, create_engine

from app.database import Account, Category, Transaction, SyncJob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="engine")
def engine_fixture():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="seeded_session")
def seeded_session_fixture(engine):
    """Session with pre-populated test data."""
    with Session(engine) as session:
        # Create accounts
        session.add(Account(uid="acc-1", session_name="test", iban="DK1234567890", name="Lønkonto"))
        session.add(Account(uid="acc-2", session_name="test", iban="DK0987654321", name="Opsparingskonto"))

        # Create categories
        session.add(Category(id="husholdning|dagligvarer", main_name="Husholdning", sub_name="Dagligvarer"))
        session.add(Category(id="transport|braendstof", main_name="Transport", sub_name="Brændstof"))
        session.add(Category(id="indkomst|loen", main_name="Indkomst", sub_name="Løn", category_type="Income"))
        session.add(Category(id="diverse|ikke-kategoriseret", main_name="Diverse", sub_name="Ikke kategoriseret"))

        # Create transactions
        session.add(Transaction(
            id="tx-1", account_uid="acc-1", booking_date="2026-06-01",
            amount=-150.0, currency="DKK", original_description="Netto",
            category_id="husholdning|dagligvarer",
        ))
        session.add(Transaction(
            id="tx-2", account_uid="acc-1", booking_date="2026-06-01",
            amount=-450.0, currency="DKK", original_description="Circle K benzin",
            category_id="transport|braendstof",
        ))
        session.add(Transaction(
            id="tx-3", account_uid="acc-1", booking_date="2026-06-02",
            amount=25000.0, currency="DKK", original_description="Løn juni",
            category_id="indkomst|loen",
        ))
        session.add(Transaction(
            id="tx-4", account_uid="acc-2", booking_date="2026-06-02",
            amount=-99.0, currency="DKK", original_description="Netflix",
        ))
        session.add(Transaction(
            id="tx-5", account_uid="acc-1", booking_date="2026-05-15",
            amount=-200.0, currency="DKK", original_description="Transfer",
            is_excluded=True,
        ))

        session.commit()
        yield session


# ---------------------------------------------------------------------------
# Database Model Tests
# ---------------------------------------------------------------------------

class TestAccount:
    def test_create(self, session: Session):
        acc = Account(uid="a1", session_name="s1", name="Test")
        session.add(acc)
        session.commit()
        assert session.get(Account, "a1") is not None

    def test_defaults(self, session: Session):
        acc = Account(uid="a2", session_name="s1")
        session.add(acc)
        session.commit()
        fetched = session.get(Account, "a2")
        assert fetched.currency == "DKK"
        assert fetched.source == "enablebanking"


class TestCategory:
    def test_create(self, session: Session):
        cat = Category(id="food|groceries", main_name="Food", sub_name="Groceries")
        session.add(cat)
        session.commit()
        assert session.get(Category, "food|groceries") is not None

    def test_category_type_default(self, session: Session):
        cat = Category(id="x|y", main_name="X", sub_name="Y")
        session.add(cat)
        session.commit()
        assert session.get(Category, "x|y").category_type == "Expense"


class TestTransaction:
    def test_create_minimal(self, session: Session):
        session.add(Account(uid="a1", session_name="s1"))
        session.commit()

        tx = Transaction(
            id="tx1", account_uid="a1",
            booking_date="2026-01-01", amount=-50.0,
            original_description="Test",
        )
        session.add(tx)
        session.commit()

        fetched = session.get(Transaction, "tx1")
        assert fetched.amount == -50.0
        assert fetched.is_extraordinary is False
        assert fetched.is_excluded is False
        assert fetched.category_id is None

    def test_update_category(self, session: Session):
        session.add(Account(uid="a1", session_name="s1"))
        session.add(Category(id="c1", main_name="M", sub_name="S"))
        session.add(Transaction(
            id="tx1", account_uid="a1",
            booking_date="2026-01-01", amount=-50.0,
            original_description="Test",
        ))
        session.commit()

        tx = session.get(Transaction, "tx1")
        tx.category_id = "c1"
        session.commit()

        assert session.get(Transaction, "tx1").category_id == "c1"


class TestSyncJob:
    def test_create(self, session: Session):
        job = SyncJob(id="job1")
        session.add(job)
        session.commit()
        assert session.get(SyncJob, "job1").status == "queued"

    def test_update_status(self, session: Session):
        job = SyncJob(id="job2")
        session.add(job)
        session.commit()

        job.status = "succeeded"
        job.progress = 100
        session.commit()

        fetched = session.get(SyncJob, "job2")
        assert fetched.status == "succeeded"
        assert fetched.progress == 100


# ---------------------------------------------------------------------------
# Category Service Tests
# ---------------------------------------------------------------------------

class TestCategoryService:
    def test_seed_categories(self, engine):
        """Test that seeding populates the Category table."""
        from app.category_service import seed_categories, DEFAULT_TAXONOMY
        # Monkey-patch engine
        import app.category_service as cs
        original_engine = cs.engine
        cs.engine = engine
        try:
            count = seed_categories()
            total_expected = sum(len(subs) for subs in DEFAULT_TAXONOMY.values())
            assert count == total_expected

            # Idempotent: second seed adds nothing
            count2 = seed_categories()
            assert count2 == 0
        finally:
            cs.engine = original_engine

    def test_make_category_id(self):
        from app.category_service import make_category_id
        assert make_category_id("Bolig", "Boliglån/husleje") == "bolig|boliglån-husleje"
        assert make_category_id("Indkomst", "Løn") == "indkomst|løn"


# ---------------------------------------------------------------------------
# Transaction Service Tests
# ---------------------------------------------------------------------------

class TestTransactionService:
    def test_list_transactions(self, seeded_session, engine):
        import app.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.list_transactions()
            assert result["transaction_count"] == 5
            assert len(result["transactions"]) == 5
            # Should be sorted by date desc
            dates = [tx["booking_date"] for tx in result["transactions"]]
            assert dates == sorted(dates, reverse=True)
        finally:
            ts.engine = original_engine

    def test_list_with_pagination(self, seeded_session, engine):
        import app.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.list_transactions(limit=2, offset=0)
            assert len(result["transactions"]) == 2
            assert result["transaction_count"] == 5
        finally:
            ts.engine = original_engine

    def test_list_with_search(self, seeded_session, engine):
        import app.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.list_transactions(search="Netto")
            assert result["transaction_count"] == 1
            assert result["transactions"][0]["description"] == "Netto"
        finally:
            ts.engine = original_engine

    def test_update_transactions(self, seeded_session, engine):
        import app.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.update_transactions(
                ["tx-4"],
                {"category_id": "husholdning|dagligvarer", "custom_note": "Streaming"},
            )
            assert result["updated_count"] == 1

            tx = ts.get_transaction("tx-4")
            assert tx["category_id"] == "husholdning|dagligvarer"
            assert tx["note"] == "Streaming"
        finally:
            ts.engine = original_engine

    def test_income_expense_series(self, seeded_session, engine):
        import app.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.income_expense_series()
            assert "series" in result
            # tx-5 is excluded, so we should only see 2 months
            months = {s["month"] for s in result["series"]}
            assert "2026-06" in months
        finally:
            ts.engine = original_engine

    def test_income_expense_excludes_excluded(self, seeded_session, engine):
        import app.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.income_expense_series()
            # tx-5 is excluded (-200 on 2026-05-15), so May should not appear
            may_data = [s for s in result["series"] if s["month"] == "2026-05"]
            assert len(may_data) == 0
        finally:
            ts.engine = original_engine
