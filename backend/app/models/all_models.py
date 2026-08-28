"""Peng database schema — V3 normalized, bank-agnostic models.

All monetary values are stored as ``int`` in minor units (øre/cents).
See ``app.money`` for conversion helpers.

Key concepts:

- **Posting**: An immutable bank transaction record from a sync source.
- **PostingAllocation**: A mutable categorization/split of a posting.
  Each posting has at least one allocation; splits create multiple.
- **Payee**: A consolidated merchant/recipient. Raw bank descriptions
  like "AMAZON.COM*5C7QC" are mapped to a clean "Amazon" payee.
- **Budget**: Monthly spending limits per category with rollover.
- **CategoryOverrideLog**: Anonymous log of user category corrections,
  used as training data for future ML-based auto-categorization.
"""
import contextvars
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import bindparam, event
from sqlalchemy.orm import Mapper, with_loader_criteria
from sqlalchemy.orm import Session as SASession
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine

from app.core.config import get_data_dir

# Context var for multi-tenancy
current_household_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_household_id")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

if "pytest" in sys.modules or os.environ.get("TESTING") == "1":
    sqlite_url = "sqlite:///:memory:"
    engine = create_engine(
        sqlite_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    sqlite_file_name = get_data_dir() / "peng.sqlite"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    engine = create_engine(sqlite_url, echo=False)


def _utcnow_iso() -> str:
    """Return the current UTC timestamp as an ISO string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite foreign keys and WAL mode for high concurrency."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_db_and_tables() -> None:
    """Create all SQLModel tables if they don't already exist."""
    SQLModel.metadata.create_all(engine)

    # Run automatic migrations
    with Session(engine) as session:
        import contextlib

        from sqlalchemy import text
        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE posting ADD COLUMN custom_date VARCHAR;"))
            session.commit()

        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE category ADD COLUMN expense_type VARCHAR DEFAULT 'Variable';"))
            session.commit()

        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE account ADD COLUMN owner_name VARCHAR;"))
            session.commit()

        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE categorizationrule ADD COLUMN partial_match BOOLEAN DEFAULT 0;"))
            session.commit()

        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE postingallocation ADD COLUMN item_name VARCHAR;"))
            session.commit()

        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE postingallocation ADD COLUMN item_cluster_id VARCHAR;"))
            session.commit()

        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE household ADD COLUMN inbound_email_token VARCHAR;"))
            session.commit()

        with contextlib.suppress(Exception):
            session.exec(text("ALTER TABLE household ADD COLUMN deleted_at VARCHAR;"))
            session.commit()

        with contextlib.suppress(Exception):
            from sqlmodel import select
            households = session.exec(select(Household).where(Household.inbound_email_token == None)).all()  # noqa: E711
            for hh in households:
                hh.inbound_email_token = _generate_inbound_token()
                session.add(hh)
            session.commit()

        # PSD2 Posting fields
        for col_def in [
            "booking_date_time VARCHAR",
            "transaction_type VARCHAR",
            "transaction_type_code VARCHAR",
            "creditor_account VARCHAR",
            "debtor_account VARCHAR",
            "balance_after_transaction_minor INTEGER",
        ]:
            col_def.split()[0]
            with contextlib.suppress(Exception):
                session.exec(text(f"ALTER TABLE posting ADD COLUMN {col_def};"))
                session.commit()

        try:
            # Data migration for category expense_type
            from sqlalchemy import text
            fixed_categories = [
                ("indkomst", "løn"), ("indkomst", "pensionsudbetaling"), ("indkomst", "dagpenge/overførselsindkomst"),
                ("indkomst", "su & studielån"), ("indkomst", "børnepenge"), ("indkomst", "underholds- & børnebidrag"),
                ("bolig", "boliglån/husleje"), ("bolig", "el, vand, varme & renovation"), ("bolig", "ejerforening"),
                ("bolig", "ejendomsskat"), ("bolig", "husforsikring"), ("bolig", "indbo- & familieforsikring"),
                ("bolig", "alarmsystem"), ("bolig", "udgifter fritidshus"), ("transport", "bil-, mc-, bådlån o.l."),
                ("transport", "bilforsikring & autohjælp"), ("transport", "ejerafgift/grøn afgift"),
                ("andre leveomkostninger", "underholds- & børnebidrag"), ("andre leveomkostninger", "institution"),
                ("andre leveomkostninger", "fagforening & a-kasse"), ("andre leveomkostninger", "livs- & ulykkesforsikring"),
                ("andre leveomkostninger", "sundheds- & sygeforsikring"), ("andre leveomkostninger", "tv & streaming"),
                ("andre leveomkostninger", "telefoni & internet"), ("lån & gæld", "studielån"),
                ("lån & gæld", "forbrugslån"), ("lån & gæld", "private lån (venner & familie)"),
                ("pension & opsparing", "pensionsopsparing"), ("pension & opsparing", "børneopsparing"),
                ("pension & opsparing", "anden opsparing"), ("indkomst", "boligstøtte"),
                ("andre leveomkostninger", "foreninger & kontingenter"),
            ]
            for main_name, sub_name in fixed_categories:
                session.exec(
                    text(f"UPDATE category SET expense_type = 'Fixed' WHERE lower(main_name) = '{main_name}' AND lower(sub_name) = '{sub_name}'")
                )
        except Exception:
            pass
        session.commit()


def get_session():
    """Yield a SQLModel session for dependency injection."""
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Multi-Tenant Isolation Hooks
# ---------------------------------------------------------------------------

@event.listens_for(SASession, "do_orm_execute")
def _add_tenant_filter(execute_state):
    """Automatically filter SELECT queries by the active household."""
    try:
        current_household_id.get()
    except LookupError:
        return

    if execute_state.is_select:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SQLModel,
                lambda cls: cls.household_id == bindparam("hh_id", callable_=lambda: current_household_id.get()) if hasattr(cls, "household_id") and cls.__name__ != "HouseholdMember" else True,
                include_aliases=True
            )
        )

@event.listens_for(Mapper, "before_insert")
def _receive_before_insert(mapper, connection, target):
    """Automatically assign the active household_id to new records."""
    if hasattr(target, "household_id"):
        try:
            hh_id = current_household_id.get()
            if not getattr(target, "household_id", None):
                target.household_id = hh_id
        except LookupError:
            pass


# ---------------------------------------------------------------------------
# Link tables (must be defined before models that reference them)
# ---------------------------------------------------------------------------

class PostingAllocationTagLink(SQLModel, table=True):
    """Link table for the many-to-many relationship between allocations and tags."""
    allocation_id: str = Field(foreign_key="postingallocation.id", ondelete="CASCADE", primary_key=True)
    tag_id: str = Field(foreign_key="tag.id", ondelete="CASCADE", primary_key=True)


# ---------------------------------------------------------------------------
# Models: Multi-Tenant Identity
# ---------------------------------------------------------------------------

def _generate_inbound_token() -> str:
    return uuid.uuid4().hex[:12]


class Household(SQLModel, table=True):
    """A Household groups multiple users and their financial data."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    inbound_email_token: str = Field(default_factory=_generate_inbound_token, unique=True, index=True)
    created_at: str = Field(default_factory=_utcnow_iso)
    deleted_at: Optional[str] = Field(default=None)


class User(SQLModel, table=True):
    """A registered user mapped to Logto."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    logto_id: str = Field(index=True, unique=True)
    email: str = Field(index=True)
    name: Optional[str] = None
    created_at: str = Field(default_factory=_utcnow_iso)


class HouseholdMember(SQLModel, table=True):
    """Membership mapping a User to a Household."""
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", primary_key=True)
    user_id: str = Field(foreign_key="user.id", ondelete="CASCADE", primary_key=True)
    role: str = Field(default="owner")  # owner, member
    created_at: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# Models: Category (no FK dependencies — define early)
# ---------------------------------------------------------------------------

class Category(SQLModel, table=True):
    """A category from the taxonomy (e.g. 'Bolig|Boliglån/husleje').

    Categories are organized into main categories and subcategories.
    The ``id`` format is ``main_slug|sub_slug``.

    Attributes:
        id: Composite slug ID (e.g. "bolig|boliglån-husleje").
        main_name: Main category display name (e.g. "Bolig").
        sub_name: Subcategory display name (e.g. "Boliglån/husleje").
        category_type: Either "Expense" or "Income".
    """
    id: str = Field(primary_key=True)
    main_name: str = Field(index=True)
    sub_name: str = Field(index=True)
    category_type: str = Field(default="Expense")  # "Expense" or "Income"
    expense_type: str = Field(default="Variable")  # "Fixed" or "Variable"

    # Relationships (back-populated by PostingAllocation and Budget)
    allocations: list["PostingAllocation"] = Relationship(back_populates="category")
    budgets: list["Budget"] = Relationship(back_populates="category")
    bills: list["BudgetBill"] = Relationship(back_populates="category")


# ---------------------------------------------------------------------------
# Models: Tag
# ---------------------------------------------------------------------------

class Tag(SQLModel, table=True):
    """A user-defined tag for organizing allocations.

    Tags provide a flexible, cross-category grouping mechanism
    (e.g. "#sommerferie2026", "#bryllup").

    Attributes:
        id: Auto-generated UUID.
        name: Display name (without the ``#`` prefix).
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    name: str = Field(index=True)
    created_at: str = Field(default_factory=_utcnow_iso)

    # Relationships
    allocations: list["PostingAllocation"] = Relationship(
        back_populates="tags", link_model=PostingAllocationTagLink
    )


# ---------------------------------------------------------------------------
# Models: Bank Infrastructure
# ---------------------------------------------------------------------------

class BankConnection(SQLModel, table=True):
    """A configured connection to a bank via Enable Banking or other provider.

    Tracks the PSD2 consent lifecycle: when it was granted, when it expires,
    and which accounts it gives access to.

    Attributes:
        id: Auto-generated UUID.
        provider: Sync provider identifier (e.g. "enablebanking", "csv").
        bank_name: Human-readable bank name (e.g. "Nordea", "Danske Bank").
        consent_id: External consent/session identifier from the provider.
        consent_expires_at: ISO timestamp when the consent expires.
        status: Connection lifecycle status.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    provider: str = Field(default="enablebanking", index=True)
    bank_name: Optional[str] = None
    consent_id: Optional[str] = None
    consent_expires_at: Optional[str] = None
    status: str = Field(default="active")  # active, expired, revoked
    created_at: str = Field(default_factory=_utcnow_iso)

    # Relationships
    accounts: list["Account"] = Relationship(back_populates="bank_connection")


class Account(SQLModel, table=True):
    """A bank account linked via a BankConnection.

    Attributes:
        uid: Unique identifier (account hash or IBAN from Enable Banking).
        bank_connection_id: FK to the BankConnection that provides this account.
        session_name: Legacy session file name (kept for migration compatibility).
        iban: International Bank Account Number (if available).
        name: Human-readable account name (e.g. "Lønkonto").
        currency: ISO 4217 currency code.
        source: Data source identifier (e.g. "enablebanking", "csv").
    """
    uid: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    bank_connection_id: Optional[str] = Field(
        default=None, foreign_key="bankconnection.id", ondelete="SET NULL", index=True
    )
    session_name: str = Field(default="", index=True)  # legacy compatibility
    iban: Optional[str] = None
    name: Optional[str] = None
    currency: str = Field(default="DKK")
    source: str = Field(default="enablebanking")
    account_type: str = Field(default="Indlån")
    balance_minor: int = Field(default=0)
    owner_name: Optional[str] = None
    savings_category_id: Optional[str] = Field(
        default=None, foreign_key="category.id", index=True
    )

    # Relationships
    bank_connection: Optional[BankConnection] = Relationship(back_populates="accounts")
    postings: list["Posting"] = Relationship(back_populates="account")

    @property
    def id(self) -> str:
        return self.uid


# ---------------------------------------------------------------------------
# Models: Payee
# ---------------------------------------------------------------------------

class Payee(SQLModel, table=True):
    """A consolidated payment recipient or sender.

    Multiple raw bank descriptions (e.g. "AMAZON.COM*5C7QC", "AMAZON.COM*9X2PK")
    map to a single Payee ("Amazon"). This enables meaningful aggregation
    and statistics.

    Attributes:
        id: Auto-generated UUID.
        display_name: Clean, user-facing name (e.g. "Amazon").
        raw_names: Newline-separated list of raw bank descriptions that map here.
        default_category_id: Suggested category for new transactions from this payee.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    display_name: str = Field(index=True)
    raw_names: str = Field(default="")  # newline-separated raw bank names
    default_category_id: Optional[str] = Field(default=None, index=True)
    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)

    # Relationships
    postings: list["Posting"] = Relationship(back_populates="payee")


# ---------------------------------------------------------------------------
# Models: Posting (immutable bank data)
# ---------------------------------------------------------------------------

class Posting(SQLModel, table=True):
    """An immutable bank transaction record.

    This model stores the raw data as received from the bank sync.
    User modifications (categorization, notes, splits) are stored
    in the related ``PostingAllocation`` records.

    .. important::
        ``amount_minor`` is an integer in minor units (øre/cents).
        Use ``app.money.from_minor()`` to convert to Decimal for display.

    Attributes:
        id: Unique ID (format: ``eb:<account_uid>:<entry_reference>``).
        account_uid: FK to the Account that owns this posting.
        payee_id: FK to the consolidated Payee (nullable until matched).
        booking_date: ISO date string when the transaction was booked.
        amount_minor: Transaction amount in minor units (negative = debit).
        currency: ISO 4217 currency code.
    """
    id: str = Field(primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    account_uid: str = Field(foreign_key="account.uid", ondelete="CASCADE", index=True)
    payee_id: Optional[str] = Field(default=None, foreign_key="payee.id", ondelete="SET NULL", index=True)

    booking_date: str = Field(index=True)
    booking_date_time: Optional[str] = None
    value_date: Optional[str] = None
    custom_date: Optional[str] = Field(default=None, index=True)

    amount_minor: int  # §7: Always integer minor units
    currency: str = Field(default="DKK")
    credit_debit_indicator: Optional[str] = None  # CRDT / DBIT

    original_description: str = Field(default="", index=True)
    remittance_information: Optional[str] = None
    creditor_name: Optional[str] = None
    debtor_name: Optional[str] = None
    creditor_account: Optional[str] = None
    debtor_account: Optional[str] = None
    merchant_category_code: Optional[str] = None
    entry_reference: Optional[str] = None

    transaction_type: Optional[str] = None
    transaction_type_code: Optional[str] = None
    balance_after_transaction_minor: Optional[int] = None

    is_excluded: bool = Field(default=False)

    created_at: str = Field(default_factory=_utcnow_iso)

    # Relationships
    account: Account = Relationship(back_populates="postings")
    payee: Optional[Payee] = Relationship(back_populates="postings")
    allocations: list["PostingAllocation"] = Relationship(back_populates="posting")


# ---------------------------------------------------------------------------
# Models: PostingAllocation (mutable categorization / splits)
# ---------------------------------------------------------------------------

class PostingAllocation(SQLModel, table=True):
    """A mutable categorization record for a posting.

    Each posting has at least one allocation (1:1 for simple transactions).
    Split transactions have multiple allocations whose ``amount_minor``
    values must sum to the parent posting's ``amount_minor``.

    Attributes:
        id: Auto-generated UUID.
        posting_id: FK to the parent Posting.
        category_id: FK to the Category taxonomy.
        amount_minor: Allocated amount in minor units (must sum to posting total).
        note: User-provided note or memo.
        is_extraordinary: Excluded from budget calculations.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    posting_id: str = Field(foreign_key="posting.id", ondelete="CASCADE", index=True)
    category_id: Optional[str] = Field(default=None, foreign_key="category.id", ondelete="SET NULL", index=True)

    amount_minor: int  # Must sum to parent posting's amount_minor
    note: Optional[str] = None
    item_name: Optional[str] = None
    item_cluster_id: Optional[str] = Field(default=None, index=True)
    is_extraordinary: bool = Field(default=False)

    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)

    recurring_transaction_id: Optional[str] = Field(default=None, foreign_key="recurringtransaction.id", index=True)

    # Relationships
    posting: Posting = Relationship(back_populates="allocations")
    category: Optional[Category] = Relationship(back_populates="allocations")
    recurring_transaction: Optional["RecurringTransaction"] = Relationship(back_populates="allocations")
    tags: list[Tag] = Relationship(
        back_populates="allocations", link_model=PostingAllocationTagLink
    )


# ---------------------------------------------------------------------------
# Models: RecurringTransaction (faste udgifter / løn)
# ---------------------------------------------------------------------------

class RecurringTransaction(SQLModel, table=True):
    """A recurring fixed expense or income (e.g. rent, Netflix, salary).

    Attributes:
        id: Auto-generated UUID.
        name: Human-readable name (e.g. "Netflix").
        amount_minor: Expected amount in minor units (negative for expenses).
        interval: e.g. "monthly", "yearly", "quarterly", "weekly".
        category_id: FK to the expected Category.
        account_uid: FK to Account (optional, if tied to a specific account).
        next_date: ISO date string for when the next transaction is expected.
        match_pattern: Pattern used to auto-match future postings (like rules).
        status: "active" or "inactive".
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    name: str
    amount_minor: int
    interval: str = Field(default="monthly")
    category_id: Optional[str] = Field(default=None, foreign_key="category.id", ondelete="SET NULL", index=True)
    account_uid: Optional[str] = Field(default=None, foreign_key="account.uid", ondelete="CASCADE", index=True)

    next_date: Optional[str] = None
    match_pattern: str = Field(index=True)
    status: str = Field(default="active")

    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)

    # Relationships
    category: Optional[Category] = Relationship()
    account: Optional[Account] = Relationship()
    allocations: list[PostingAllocation] = Relationship(back_populates="recurring_transaction")


# ---------------------------------------------------------------------------
# Models: Budget
# ---------------------------------------------------------------------------

class Budget(SQLModel, table=True):
    """Monthly budget configuration for a category.

    Supports both fixed bills (``budget_type='bill'``) and spending limits
    (``budget_type='limit'``). When ``rollover=True``, unused budget
    carries forward to the next month.

    Attributes:
        id: Auto-generated UUID.
        category_id: FK to the Category this budget applies to.
        year: Budget year (e.g. 2026).
        month: Budget month (1-12).
        amount_minor: Budgeted amount in minor units.
        budget_type: 'bill' (fixed, predictable) or 'limit' (spending cap).
        rollover: Whether unused budget rolls forward.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    category_id: str = Field(foreign_key="category.id", ondelete="CASCADE", index=True)

    year: int
    month: int  # 1-12

    amount_minor: int  # §7: Always integer minor units
    budget_type: str = Field(default="limit")  # "bill" or "limit"
    rollover: bool = Field(default=False)

    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)

    # Relationships
    category: Category = Relationship(back_populates="budgets")


class BudgetBill(SQLModel, table=True):
    """A specific recurring bill within a budget category.

    For fixed expenses ("regninger"), users can add multiple bills
    per category that apply to specific months.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    category_id: str = Field(foreign_key="category.id", ondelete="CASCADE", index=True)

    year: int
    name: str
    amount_minor: int
    months: str  # Comma separated list of month numbers, e.g. "1,4,7,10"

    created_at: str = Field(default_factory=_utcnow_iso)

    # Relationships
    category: Category = Relationship(back_populates="bills")

# ---------------------------------------------------------------------------
# Models: CategoryOverrideLog (anonymous learning data)
# ---------------------------------------------------------------------------

class CategoryOverrideLog(SQLModel, table=True):
    """Anonymous log of user category corrections.

    When a user changes or assigns a category, we log the original
    description and the category change. This data is used for offline
    ML training to improve auto-categorization over time.

    No personal data is stored — only the transaction description
    and category IDs.

    Attributes:
        id: Auto-generated UUID.
        original_description: The bank transaction description.
        old_category_id: Previous category (None if uncategorized).
        new_category_id: The category the user chose.
        merchant_category_code: MCC from the bank (if available).
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    original_description: str = Field(index=True)
    old_category_id: Optional[str] = None
    new_category_id: str
    merchant_category_code: Optional[str] = None
    created_at: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# Models: Document (placeholder for receipts/attachments)
# ---------------------------------------------------------------------------

class Document(SQLModel, table=True):
    """A receipt or document attached to a posting allocation.

    Attributes:
        id: Auto-generated UUID.
        allocation_id: FK to the PostingAllocation this document belongs to.
        filename: Original filename.
        content_type: MIME type.
        storage_path: Path to the file on disk (relative to data dir).
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    allocation_id: str = Field(foreign_key="postingallocation.id", ondelete="CASCADE", index=True)
    filename: str
    content_type: str = Field(default="application/octet-stream")
    storage_path: str
    created_at: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# Models: SyncJob (unchanged from V2)
# ---------------------------------------------------------------------------

class SyncJob(SQLModel, table=True):
    """Tracks the status of an Enable Banking retrieval job.

    Attributes:
        id: UUID hex string.
        status: One of "queued", "running", "succeeded", "failed".
        progress: Integer percentage (0-100).
        current_phase: Human-readable description of the current step.
        error_message: Error details if the job failed.
        result_json: JSON blob with the final result payload.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    status: str = Field(default="queued")  # queued, running, succeeded, failed
    started_at: str = Field(default_factory=_utcnow_iso)
    completed_at: Optional[str] = None
    progress: int = Field(default=0)
    current_phase: Optional[str] = None
    error_message: Optional[str] = None
    result_json: Optional[str] = None


# ---------------------------------------------------------------------------
# Models: CategorizationRule (rule-based auto-categorization)
# ---------------------------------------------------------------------------

class CategorizationRule(SQLModel, table=True):
    """A keyword or regex rule for automatic transaction categorization.

    The rules engine evaluates these in priority order (lower = higher priority)
    against pre-processed transaction descriptions. This model ports the entire
    Spiir "hints" system — 324 keywords across 69 subcategories tuned to the
    Danish market.

    Attributes:
        id: Auto-generated UUID.
        category_id: FK to the target Category (slug format).
        match_pattern: The keyword or regex pattern to match against.
        is_regex: If True, match_pattern is evaluated as a regex.
        priority: Lower number = evaluated first. System-seeded rules
                  start at 1000; user rules default to 500 (higher priority).
        source: Origin of the rule — "system" (seeded from Spiir) or "user".
        is_active: Whether the rule is currently enabled.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: Optional[str] = Field(default=None, foreign_key="household.id", ondelete="CASCADE", index=True)
    category_id: str = Field(foreign_key="category.id", ondelete="CASCADE", index=True)
    match_pattern: str = Field(index=True)
    is_regex: bool = Field(default=False)
    partial_match: bool = Field(default=False)
    priority: int = Field(default=500)
    source: str = Field(default="user")  # "system" or "user"
    is_active: bool = Field(default=True)
    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# Models: InboundEmail (Receipt Email Ingestion Log)
# ---------------------------------------------------------------------------

class InboundEmail(SQLModel, table=True):
    """Log of incoming forwarded receipt emails for a household."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    received_at: str = Field(default_factory=_utcnow_iso)
    sender: str = Field(default="")
    recipient: Optional[str] = Field(default=None)
    subject: Optional[str] = Field(default=None)
    status: str = Field(default="pending")  # "success", "failed", "pending", "no_link", "invalid_file"
    download_url: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    raw_receipt_count: int = Field(default=0)
    deduplicated_receipt_count: int = Field(default=0)
    auto_linked_count: int = Field(default=0)
    source_type: str = Field(default="webhook")  # "webhook", "imap", "simulation"
    created_at: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# Models: DismissedDuplicate (Explicit User Not-Duplicate Approvals)
# ---------------------------------------------------------------------------

class DismissedDuplicate(SQLModel, table=True):
    """Stores pairs of postings that the user has explicitly dismissed as NOT being duplicates."""
    __tablename__ = "dismissed_duplicate"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    household_id: str = Field(foreign_key="household.id", ondelete="CASCADE", index=True)
    posting_id_1: str = Field(index=True)
    posting_id_2: str = Field(index=True)
    created_at: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# Legacy alias (for migration compatibility)
# ---------------------------------------------------------------------------

# The V2 code used `Transaction` — this alias allows old service code
# to keep working during the gradual migration. Remove after Phase 1 is complete.
Transaction = Posting

