"""Comprehensive tests for the V3 backend models and services."""
import pytest
from conftest import TEST_HOUSEHOLD_ID
from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    Account,
    BankConnection,
    Budget,
    Category,
    CategoryOverrideLog,
    Household,
    Payee,
    Posting,
    PostingAllocation,
    SyncJob,
    Tag,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="engine")
def engine_fixture():
    """Create an in-memory SQLite engine for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(test_engine)
    return test_engine


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        # Ensure the test household exists
        session.add(Household(id=TEST_HOUSEHOLD_ID, name="Test Husstand"))
        session.commit()
        yield session


@pytest.fixture(name="seeded_session")
def seeded_session_fixture(engine):
    """Session with pre-populated test data using V3 models."""
    with Session(engine) as session:
        # Create household
        session.add(Household(id=TEST_HOUSEHOLD_ID, name="Test Husstand"))

        # Create accounts
        session.add(Account(uid="acc-1", household_id=TEST_HOUSEHOLD_ID, session_name="test", iban="DK1234567890", name="Lønkonto"))
        session.add(Account(uid="acc-2", household_id=TEST_HOUSEHOLD_ID, session_name="test", iban="DK0987654321", name="Opsparingskonto"))

        # Create categories
        session.add(Category(id="husholdning|dagligvarer", main_name="Husholdning", sub_name="Dagligvarer"))
        session.add(Category(id="transport|braendstof", main_name="Transport", sub_name="Brændstof"))
        session.add(Category(id="indkomst|loen", main_name="Indkomst", sub_name="Løn", category_type="Income"))
        session.add(Category(id="diverse|ikke-kategoriseret", main_name="Diverse", sub_name="Ikke kategoriseret"))

        # Create postings (amounts in minor units — øre)
        session.add(Posting(
            id="tx-1", household_id=TEST_HOUSEHOLD_ID, account_uid="acc-1", booking_date="2026-06-01",
            amount_minor=-15000, currency="DKK", original_description="Netto",
        ))
        session.add(Posting(
            id="tx-2", household_id=TEST_HOUSEHOLD_ID, account_uid="acc-1", booking_date="2026-06-01",
            amount_minor=-45000, currency="DKK", original_description="Circle K benzin",
        ))
        session.add(Posting(
            id="tx-3", household_id=TEST_HOUSEHOLD_ID, account_uid="acc-1", booking_date="2026-06-02",
            amount_minor=2500000, currency="DKK", original_description="Løn juni",
        ))
        session.add(Posting(
            id="tx-4", household_id=TEST_HOUSEHOLD_ID, account_uid="acc-2", booking_date="2026-06-02",
            amount_minor=-9900, currency="DKK", original_description="Netflix",
        ))
        session.add(Posting(
            id="tx-5", household_id=TEST_HOUSEHOLD_ID, account_uid="acc-1", booking_date="2026-05-15",
            amount_minor=-20000, currency="DKK", original_description="Transfer",
            is_excluded=True,
        ))

        # Create allocations for categorized postings
        session.add(PostingAllocation(
            id="alloc-1", posting_id="tx-1", category_id="husholdning|dagligvarer",
            amount_minor=-15000,
        ))
        session.add(PostingAllocation(
            id="alloc-2", posting_id="tx-2", category_id="transport|braendstof",
            amount_minor=-45000,
        ))
        session.add(PostingAllocation(
            id="alloc-3", posting_id="tx-3", category_id="indkomst|loen",
            amount_minor=2500000,
        ))

        session.commit()
        yield session


# ---------------------------------------------------------------------------
# Database Model Tests
# ---------------------------------------------------------------------------

class TestAccount:
    def test_create(self, session: Session):
        acc = Account(uid="a1", household_id=TEST_HOUSEHOLD_ID, session_name="s1", name="Test")
        session.add(acc)
        session.commit()
        assert session.get(Account, "a1") is not None

    def test_defaults(self, session: Session):
        acc = Account(uid="a2", household_id=TEST_HOUSEHOLD_ID, session_name="s1")
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


class TestPosting:
    def test_create_with_minor_units(self, session: Session):
        session.add(Account(uid="a1", household_id=TEST_HOUSEHOLD_ID, session_name="s1"))
        session.commit()

        posting = Posting(
            id="p1", household_id=TEST_HOUSEHOLD_ID, account_uid="a1",
            booking_date="2026-01-01", amount_minor=-5000,
            original_description="Test",
        )
        session.add(posting)
        session.commit()

        fetched = session.get(Posting, "p1")
        assert fetched.amount_minor == -5000
        assert fetched.is_excluded is False

    def test_amount_is_integer(self, session: Session):
        session.add(Account(uid="a1", household_id=TEST_HOUSEHOLD_ID, session_name="s1"))
        session.commit()

        posting = Posting(
            id="p1", household_id=TEST_HOUSEHOLD_ID, account_uid="a1",
            booking_date="2026-01-01", amount_minor=10050,
        )
        session.add(posting)
        session.commit()

        fetched = session.get(Posting, "p1")
        assert isinstance(fetched.amount_minor, int)
        assert fetched.amount_minor == 10050  # 100.50 kr


class TestPostingAllocation:
    def test_create_allocation(self, session: Session):
        session.add(Account(uid="a1", household_id=TEST_HOUSEHOLD_ID, session_name="s1"))
        session.add(Posting(id="p1", household_id=TEST_HOUSEHOLD_ID, account_uid="a1", booking_date="2026-01-01", amount_minor=-5000))
        session.add(Category(id="c1", main_name="M", sub_name="S"))
        session.commit()

        alloc = PostingAllocation(
            posting_id="p1", category_id="c1", amount_minor=-5000,
        )
        session.add(alloc)
        session.commit()

        fetched = session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(PostingAllocation)
            .where(PostingAllocation.posting_id == "p1")
        ).first()
        assert fetched.category_id == "c1"
        assert fetched.amount_minor == -5000

    def test_split_allocations_sum(self, session: Session):
        """Split allocations must sum to the parent posting amount."""
        session.add(Account(uid="a1", household_id=TEST_HOUSEHOLD_ID, session_name="s1"))
        session.add(Category(id="food|groceries", main_name="Food", sub_name="Groceries"))
        session.add(Category(id="household|cleaning", main_name="Household", sub_name="Cleaning"))
        session.add(Posting(id="p1", household_id=TEST_HOUSEHOLD_ID, account_uid="a1", booking_date="2026-01-01", amount_minor=-10000))
        session.commit()

        # Split: -70.00 groceries + -30.00 cleaning = -100.00 total
        session.add(PostingAllocation(posting_id="p1", category_id="food|groceries", amount_minor=-7000))
        session.add(PostingAllocation(posting_id="p1", category_id="household|cleaning", amount_minor=-3000))
        session.commit()

        from sqlmodel import select
        allocs = session.exec(
            select(PostingAllocation).where(PostingAllocation.posting_id == "p1")
        ).all()
        assert sum(a.amount_minor for a in allocs) == -10000


class TestPayee:
    def test_create(self, session: Session):
        payee = Payee(household_id=TEST_HOUSEHOLD_ID, display_name="Amazon", raw_names="AMAZON.COM*5C7QC\nAMAZON.COM*9X2PK")
        session.add(payee)
        session.commit()

        from sqlmodel import select
        fetched = session.exec(select(Payee)).first()
        assert fetched.display_name == "Amazon"
        assert "AMAZON.COM*5C7QC" in fetched.raw_names


class TestBudget:
    def test_create(self, session: Session):
        session.add(Category(id="c1", main_name="M", sub_name="S"))
        session.commit()

        budget = Budget(
            household_id=TEST_HOUSEHOLD_ID,
            category_id="c1", year=2026, month=7,
            amount_minor=500000, budget_type="limit",
        )
        session.add(budget)
        session.commit()

        from sqlmodel import select
        fetched = session.exec(select(Budget)).first()
        assert fetched.amount_minor == 500000  # 5000.00 kr
        assert fetched.budget_type == "limit"
        assert fetched.rollover is False


class TestBankConnection:
    def test_create(self, session: Session):
        conn = BankConnection(household_id=TEST_HOUSEHOLD_ID, provider="enablebanking", bank_name="Nordea")
        session.add(conn)
        session.commit()

        from sqlmodel import select
        fetched = session.exec(select(BankConnection)).first()
        assert fetched.provider == "enablebanking"
        assert fetched.status == "active"


class TestTag:
    def test_create(self, session: Session):
        tag = Tag(household_id=TEST_HOUSEHOLD_ID, name="sommerferie2026")
        session.add(tag)
        session.commit()

        from sqlmodel import select
        fetched = session.exec(select(Tag)).first()
        assert fetched.name == "sommerferie2026"


class TestCategoryOverrideLog:
    def test_create(self, session: Session):
        log = CategoryOverrideLog(
            household_id=TEST_HOUSEHOLD_ID,
            original_description="Netflix",
            old_category_id=None,
            new_category_id="privatforbrug|online-services-software",
        )
        session.add(log)
        session.commit()

        from sqlmodel import select
        fetched = session.exec(select(CategoryOverrideLog)).first()
        assert fetched.original_description == "Netflix"
        assert fetched.old_category_id is None
        assert fetched.new_category_id == "privatforbrug|online-services-software"


class TestSyncJob:
    def test_create(self, session: Session):
        job = SyncJob(id="job1", household_id=TEST_HOUSEHOLD_ID)
        session.add(job)
        session.commit()
        assert session.get(SyncJob, "job1").status == "queued"

    def test_update_status(self, session: Session):
        job = SyncJob(id="job2", household_id=TEST_HOUSEHOLD_ID)
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
        import app.services.category_service as cs
        from app.services.category_service import DEFAULT_TAXONOMY, seed_categories
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
        from app.services.category_service import make_category_id
        assert make_category_id("Bolig", "Boliglån/husleje") == "bolig|boliglån-husleje"
        assert make_category_id("Indkomst", "Løn") == "indkomst|løn"


# ---------------------------------------------------------------------------
# Transaction Service Tests (using V3 Posting model)
# ---------------------------------------------------------------------------

class TestTransactionService:
    def test_list_transactions(self, seeded_session, engine):
        import app.services.transaction_service as ts
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

    def test_amount_is_string_in_response(self, seeded_session, engine):
        """§7: API amounts must be strings, not floats."""
        import app.services.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.list_transactions()
            for tx in result["transactions"]:
                assert isinstance(tx["amount"], str), f"amount should be str, got {type(tx['amount'])}"
                assert isinstance(tx["amount_minor"], int), "amount_minor should be int"
        finally:
            ts.engine = original_engine

    def test_list_with_pagination(self, seeded_session, engine):
        import app.services.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.list_transactions(limit=2, offset=0)
            assert len(result["transactions"]) == 2
            assert result["transaction_count"] == 5
        finally:
            ts.engine = original_engine

    def test_list_with_search(self, seeded_session, engine):
        import app.services.transaction_service as ts
        original_engine = ts.engine
        ts.engine = engine
        try:
            result = ts.list_transactions(search="Netto")
            assert result["transaction_count"] == 1
            assert result["transactions"][0]["description"] == "Netto"
        finally:
            ts.engine = original_engine

    def test_update_transactions_logs_override(self, seeded_session, engine):
        """Updating a category should log the override."""
        import app.services.transaction_service as ts
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

            # Verify the override was logged
            from sqlmodel import select
            with Session(engine) as db:
                logs = db.exec(select(CategoryOverrideLog)).all()
                assert len(logs) >= 1
                log = logs[-1]
                assert log.original_description == "Netflix"
                assert log.new_category_id == "husholdning|dagligvarer"
        finally:
            ts.engine = original_engine

    def test_income_expense_series(self, seeded_session, engine):
        import app.services.insights_service as ins
        original_engine = ins.engine
        ins.engine = engine
        try:
            result = ins.income_expense_series()
            assert "series" in result
            months = {s["month"] for s in result["series"]}
            assert "2026-06" in months
            # Amounts should be strings
            for s in result["series"]:
                assert isinstance(s["income"], str)
                assert isinstance(s["expense"], str)
        finally:
            ins.engine = original_engine

    def test_income_expense_excludes_excluded(self, seeded_session, engine):
        import app.services.insights_service as ins
        original_engine = ins.engine
        ins.engine = engine
        try:
            result = ins.income_expense_series()
            # tx-5 is excluded (-200 on 2026-05-15), so May should not appear
            may_data = [s for s in result["series"] if s["month"] == "2026-05"]
            assert len(may_data) == 0
        finally:
            ins.engine = original_engine
